"""기반 계층 단위 테스트 — client·Secret·모델 경계."""

import httpx
import pytest

from app.clients.base_http import BaseHttpClient
from app.clients.slurm.client import SlurmrestdClient
from app.core.errors import ExternalServiceError, NotFound, SecretNotFound, SlurmUnauthorized
from app.core.redis_client import redis_lock
from app.core.secrets import EnvSecretStore
from tests.fakes import FakeRedis


def _transport(handler):
    return httpx.MockTransport(handler)


def test_slurm_headers_carry_token_and_impersonation():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.update(request.headers)
        return httpx.Response(200, json={"jobs": []})

    client = SlurmrestdClient(
        "http://slurm:6820",
        token_provider=lambda: "jwt-abc",
        api_version="v0.0.43",
        transport=_transport(handler),
    )
    client.get_jobs(as_user="jrpark")
    assert seen["x-slurm-user-token"] == "jwt-abc"
    assert seen["x-slurm-user-name"] == "jrpark"


def test_slurm_omits_impersonation_when_not_user_scoped():
    seen = {}

    def handler(request):
        seen.update(request.headers)
        return httpx.Response(200, json={})

    client = SlurmrestdClient(
        "http://slurm:6820", token_provider=lambda: "t", transport=_transport(handler)
    )
    client.ping()
    assert "x-slurm-user-name" not in seen


def test_slurm_401_maps_to_token_reregistration():
    client = SlurmrestdClient(
        "http://slurm:6820",
        token_provider=lambda: "expired",
        transport=_transport(lambda r: httpx.Response(401, json={"error": "invalid token"})),
    )
    with pytest.raises(SlurmUnauthorized) as exc:
        client.ping()
    assert "재등록" in exc.value.message


def test_api_version_is_pinned_in_path():
    paths = []

    def handler(request):
        paths.append(request.url.path)
        return httpx.Response(200, json={})

    client = SlurmrestdClient(
        "http://slurm:6820",
        token_provider=lambda: "t",
        api_version="v0.0.43",
        transport=_transport(handler),
    )
    client.ping()
    client.get_accounting_jobs()
    assert paths == ["/slurm/v0.0.43/ping", "/slurmdb/v0.0.43/jobs"]


def test_retry_only_for_idempotent_methods():
    calls = {"GET": 0, "POST": 0}

    def handler(request):
        calls[request.method] += 1
        return httpx.Response(500, json={"error": "boom"})

    client = BaseHttpClient("http://x", max_retries=2, transport=_transport(handler))
    with pytest.raises(ExternalServiceError):
        client.request("GET", "/a")
    with pytest.raises(ExternalServiceError):
        client.request("POST", "/a")
    assert calls["GET"] == 3  # 최초 + 재시도 2
    assert calls["POST"] == 1  # 중복 제출 방지 — 재시도하지 않는다


def test_4xx_is_not_retried():
    calls = []

    def handler(request):
        calls.append(1)
        return httpx.Response(404, json={})

    client = BaseHttpClient("http://x", max_retries=3, transport=_transport(handler))
    with pytest.raises(NotFound):
        client.request("GET", "/missing")
    assert len(calls) == 1


def test_secret_store_roundtrip_and_missing(settings):
    store = EnvSecretStore(settings)
    store.put("cluster/1/SLURM_JWT", "value")
    assert store.get("cluster/1/SLURM_JWT") == "value"
    with pytest.raises(SecretNotFound):
        store.get("cluster/9/SLURM_JWT")


def test_redis_lock_prevents_concurrent_batch():
    redis = FakeRedis()
    with redis_lock(redis, "sync:lock:ad") as first:
        assert first is True
        with redis_lock(redis, "sync:lock:ad") as second:
            assert second is False  # 다른 replica는 건너뛴다
    with redis_lock(redis, "sync:lock:ad") as third:
        assert third is True  # 해제 후 재획득 가능


def test_client_factory_survives_detached_cluster(db, settings, secret_store):
    """풀에 캐시된 client가 요청 단위 세션의 ORM 객체를 붙잡으면 안 된다.

    실환경에서 발견된 결함: 한 요청이 오류로 rollback되면 ORM 속성이 만료되고 세션이
    닫히는데, 캐시된 client의 token_provider가 그 인스턴스를 참조하고 있어 **그 클러스터의
    이후 모든 요청이 500(DetachedInstanceError)** 이 됐다. 앱 재시작 전까지 복구되지 않는다.
    """
    from app.clients.factory import ClusterClientFactory
    from app.clients.token_provider import SlurmTokenProvider
    from app.models import Cluster

    cluster = Cluster(name="c1", slurmrestd_url="http://slurm:6820", api_version="v0.0.43")
    db.add(cluster)
    db.commit()
    secret_store.put("cluster/1/SLURM_JWT", "jwt-value")

    factory = ClusterClientFactory(
        settings,
        SlurmTokenProvider(secret_store),
        transport_factory=lambda: _transport(lambda r: httpx.Response(200, json={"ok": True})),
    )
    client = factory.slurm(cluster, "cluster/1/SLURM_JWT")

    # 오류 경로 재현: session_scope의 rollback은 열린 트랜잭션의 ORM 속성을 **만료**시키고,
    # 이어서 세션이 닫히면 인스턴스가 detached가 된다. 그 상태를 그대로 만든다.
    db.expire_all()
    db.close()

    assert client.ping() == {"ok": True}


def test_models_match_erd_entity_count():
    """db-erd.md의 엔티티 수와 일치해야 한다.

    20 = 초기 21개 - `user_ssh_key`(U-AC-03, 0005) - `job_template`(U-JB-03/A-OP-02, 0012)
    + `api_token`(C-01 기계 자격증명, 0013).
    """
    from app.models import Base

    assert len(Base.metadata.tables) == 20


def test_slurm_owned_entities_are_not_portal_tables():
    """account·QOS·association은 slurmdbd 소유 — Portal DB에 있으면 경계 위반."""
    from app.models import Base

    names = set(Base.metadata.tables)
    assert not names & {"account", "qos", "association", "slurm_user"}
