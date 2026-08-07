"""인터랙티브 세션 서비스 (T-04, U-IA-01·02·04).

핵심은 두 가지다.
  - 남의 세션에 손댈 수 없다.
  - 접속 대상은 `connection.json`의 워커 노드에서 오고 `cluster.login_node`가 아니다.
"""

import json

import pytest

from app.core.errors import NotFound, ValidationFailed
from app.models import InteractiveSession, User
from app.repositories.session import STATUS_ACTIVE, STATUS_ENDED
from app.services.cluster import ClusterService
from app.services.session import SessionService
from app.services.session_script import SessionSpec

IMAGE = "/home/portal/images/rocky9-mate-1.0.sif"
# 워커는 로그인 노드와 다른 기계다. 개발 환경에서 둘이 같아 놓치기 쉬운 지점.
WORKER = "node012"
CONNECTION = {
    "app": "desktop", "node": WORKER, "ip": "10.0.3.12", "port": 5903,
    "password": "s3cret12", "view_password": "v13w0nly", "geometry": "1280x800",
}


class FakeSsh:
    def __init__(self, connection: dict | None = None):
        self.connection = connection
        self.as_users: list[str] = []
        self.made_dirs: list[str] = []
        self.read_paths: list[str] = []

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return None

    def home_dir(self, user):
        self.as_users.append(user)
        return f"/home/{user}"

    def makedirs(self, user, base, relative, *, mode=0o700):
        self.as_users.append(user)
        self.made_dirs.append(f"{base}/{relative}")

    def read_text(self, user, path, *, max_bytes=65536):
        self.as_users.append(user)
        self.read_paths.append(path)
        return json.dumps(self.connection) if self.connection else None


@pytest.fixture
def owner(db) -> User:
    u = User(ad_object_guid="guid-owner", username="jrpark", display_name="박정렬", is_active=True)
    db.add(u)
    db.commit()
    return u


@pytest.fixture
def intruder(db) -> User:
    u = User(ad_object_guid="guid-other", username="someone", display_name="타인", is_active=True)
    db.add(u)
    db.commit()
    return u


def build(db, settings, secret_store, slurm_client, ssh) -> SessionService:
    from tests.fakes import FakeClientFactory

    clusters = ClusterService(db, secrets=secret_store, client_factory=FakeClientFactory(slurm_client))
    service = SessionService(db, clusters, settings=settings, secrets=secret_store)
    service._connect = lambda cluster: ssh  # type: ignore[method-assign]
    return service


@pytest.fixture
def service(db, settings, secret_store, slurm_client):
    return build(db, settings, secret_store, slurm_client, FakeSsh(CONNECTION))


def make_session(db, cluster, user, job_id="90001") -> InteractiveSession:
    s = InteractiveSession(
        user_guid=user.ad_object_guid, cluster_id=cluster.id,
        app_type="desktop", slurm_job_id=job_id, status=STATUS_ACTIVE,
    )
    db.add(s)
    db.commit()
    return s


# --- 제출 -----------------------------------------------------------------


def test_create_submits_as_the_requesting_user(service, cluster, owner, slurm_client):
    record = service.create(cluster, SessionSpec(image_ref=IMAGE, cpus=2), user=owner)
    submit = [c for c in slurm_client.calls if c[0] == "submit_job"][0][1]
    assert submit["as_user"] == "jrpark"
    assert record.slurm_job_id == "90001"
    assert record.status == STATUS_ACTIVE


def test_create_sends_resources_in_the_rest_payload(service, cluster, owner, slurm_client):
    # #SBATCH는 slurmrestd 제출에서 무시된다 — 자원은 REST 속성이 정한다.
    service.create(
        cluster,
        SessionSpec(image_ref=IMAGE, partition="cpu", cpus=2, memory_gb=3, walltime="02:00:00"),
        user=owner,
    )
    job = [c for c in slurm_client.calls if c[0] == "submit_job"][0][1]["spec"]["job"]
    assert job["partition"] == "cpu"
    assert job["cpus_per_task"] == 2
    assert job["memory_per_node"] == 3072  # MB 정수
    assert job["time_limit"] == 120  # 분 정수
    assert job["environment"]  # 비우면 Slurm이 2019로 거부한다
    # REST 제출은 환경을 통째로 교체한다 — HOME이 없으면 Job이 즉시 죽는다.
    assert "HOME=/home/jrpark" in job["environment"]
    assert "USER=jrpark" in job["environment"]


def test_exclusive_asks_for_the_whole_node(service, cluster, owner, slurm_client):
    """독점은 노드 전체를 쓰겠다는 뜻이다 — 폼의 CPU·메모리 값이 그걸 깎으면 안 된다.

    `--mem`은 독점과 무관하게 하드 캡이라, 그냥 두면 16코어 64GB 노드를 막아놓고
    2코어 3GB만 쓰는 결과가 된다.
    """
    service.create(
        cluster,
        SessionSpec(image_ref=IMAGE, cpus=2, memory_gb=3, exclusive=True),
        user=owner,
    )
    job = [c for c in slurm_client.calls if c[0] == "submit_job"][0][1]["spec"]["job"]
    assert job["exclusive"] == "true"
    assert "cpus_per_task" not in job
    assert job["memory_per_node"] == 0  # 0 = 노드 메모리 전체


def test_create_prepares_the_log_directory_under_the_home(service, cluster, owner):
    """Slurm은 로그 파일만 만들고 상위 디렉터리는 만들지 않는다.

    홈은 **base로 넘긴다** — 포털이 사용자 홈을 만들어서는 안 된다(pam_mkhomedir의 몫).
    """
    service.create(cluster, SessionSpec(image_ref=IMAGE), user=owner)
    assert service._connect(cluster).made_dirs == ["/home/jrpark/.portal/logs"]


def test_create_requires_an_image(service, cluster, owner):
    with pytest.raises(ValidationFailed):
        service.create(cluster, SessionSpec(image_ref=""), user=owner)


# --- 소유자 검증 ----------------------------------------------------------


def test_other_users_cannot_read_a_session(service, db, cluster, owner, intruder):
    s = make_session(db, cluster, owner)
    with pytest.raises(NotFound):
        service.get(s.id, user=intruder)


def test_other_users_cannot_connect_to_a_session(service, db, cluster, owner, intruder):
    s = make_session(db, cluster, owner)
    with pytest.raises(NotFound):
        service.connection(s.id, user=intruder)


def test_other_users_cannot_terminate_a_session(service, db, cluster, owner, intruder, slurm_client):
    s = make_session(db, cluster, owner)
    with pytest.raises(NotFound):
        service.terminate(s.id, user=intruder)
    assert slurm_client.cancelled == []


def test_listing_only_returns_own_sessions(service, db, cluster, owner, intruder):
    make_session(db, cluster, owner, job_id="1")
    make_session(db, cluster, intruder, job_id="2")
    assert [s["job_id"] for s in service.list(user=owner)] == ["1"]


# --- 접속 대상 ------------------------------------------------------------


def test_connection_target_is_the_worker_node_not_the_login_node(
    service, db, cluster, owner, slurm_client
):
    """분리 대비의 핵심 — 목적지는 connection.json에서만 온다."""
    cluster.login_node = "login01"
    db.commit()
    slurm_client.jobs = [{"job_id": 90001, "job_state": ["RUNNING"], "user_name": "jrpark"}]
    s = make_session(db, cluster, owner)

    target = service.connection(s.id, user=owner)

    assert target["host"] == WORKER
    assert target["host"] != cluster.login_node
    assert target["port"] == 5903
    assert target["password"] == "s3cret12"


def test_connection_reads_the_session_file_under_the_home(service, db, cluster, owner, slurm_client):
    slurm_client.jobs = [{"job_id": 90001, "job_state": ["RUNNING"]}]
    s = make_session(db, cluster, owner)
    service.connection(s.id, user=owner)
    assert service._connect(cluster).read_paths == [
        "/home/jrpark/.portal/sessions/90001/connection.json"
    ]


def test_connection_is_refused_while_still_starting(
    db, settings, secret_store, slurm_client, cluster, owner
):
    # connection.json이 아직 없다 = 준비 중. 오류가 아니라 상태다.
    service = build(db, settings, secret_store, slurm_client, FakeSsh(None))
    slurm_client.jobs = [{"job_id": 90001, "job_state": ["PENDING"]}]
    s = make_session(db, cluster, owner)
    with pytest.raises(ValidationFailed) as exc:
        service.connection(s.id, user=owner)
    assert "준비 중" in str(exc.value.message)


def test_connection_is_refused_for_a_finished_session(service, db, cluster, owner, slurm_client):
    slurm_client.jobs = [{"job_id": 90001, "job_state": ["COMPLETED"]}]
    s = make_session(db, cluster, owner)
    with pytest.raises(ValidationFailed):
        service.connection(s.id, user=owner)


# --- 상태의 출처 ----------------------------------------------------------


def test_slurm_state_wins_over_the_ledger(service, db, cluster, owner, slurm_client):
    """노드가 죽으면 정리 훅이 안 돌아 파일이 남는다 — 생사는 Slurm이 정한다."""
    s = make_session(db, cluster, owner)
    slurm_client.jobs = [{"job_id": 90001, "job_state": ["COMPLETED"]}]

    view = service.get(s.id, user=owner)

    assert view["state"] == "COMPLETED"
    assert view["is_running"] is False
    assert s.status == STATUS_ENDED  # 대장도 따라간다


def test_job_unknown_to_slurm_counts_as_ended(service, db, cluster, owner, slurm_client):
    s = make_session(db, cluster, owner)
    slurm_client.jobs = []
    assert service.get(s.id, user=owner)["state"] == "ENDED"


def test_listing_survives_a_slurm_outage(service, db, cluster, owner, slurm_client):
    def boom(*a, **kw):
        raise RuntimeError("slurmrestd down")

    slurm_client.get_jobs = boom
    make_session(db, cluster, owner)
    # 상태를 못 읽어도 세션 목록 자체는 보여준다.
    assert len(service.list(user=owner)) == 1


def test_terminate_cancels_the_job_as_the_owner(service, db, cluster, owner, slurm_client):
    s = make_session(db, cluster, owner)
    service.terminate(s.id, user=owner)
    assert slurm_client.cancelled == ["90001"]
    assert [c for c in slurm_client.calls if c[0] == "cancel_job"][0][1]["as_user"] == "jrpark"
    assert s.status == STATUS_ENDED
    assert s.terminated_at is not None


def test_home_permission_problem_is_reported_as_a_setup_issue(
    db, settings, secret_store, slurm_client, cluster, owner
):
    """홈 소유권이 AD UID와 어긋나면 세션이 뜰 수 없다 — 포털 장애처럼 보이면 안 된다.

    실측: `/home`을 로컬 계정과 AD 계정이 함께 쓰는 환경에서 홈 소유자가 로컬 UID였다.
    """

    class DeniedSsh(FakeSsh):
        def makedirs(self, user, base, relative, *, mode=0o700):
            raise ValidationFailed(
                f"{base} 을(를) 만들 권한이 없습니다.", detail={"path": base, "user": user}
            )

    service = build(db, settings, secret_store, slurm_client, DeniedSsh(CONNECTION))
    with pytest.raises(ValidationFailed) as exc:
        service.create(cluster, SessionSpec(image_ref=IMAGE), user=owner)
    assert "권한이 없습니다" in str(exc.value.message)
    # 권한 문제라면 Job을 제출하지 않는다 — 어차피 로그도 못 쓴다.
    assert [c for c in slurm_client.calls if c[0] == "submit_job"] == []


def test_missing_home_is_reported_not_created(
    db, settings, secret_store, slurm_client, cluster, owner
):
    """홈이 없으면 **만들지 않고 알린다.**

    포털이 홈을 만들면 소유권·권한이 사이트 정책과 어긋난다 — pam_mkhomedir의 몫이다.
    실측: 한 번도 로그인하지 않은 AD 계정은 홈이 없고 `/home`은 root 소유 755다.
    """

    class NoHomeSsh(FakeSsh):
        def makedirs(self, user, base, relative, *, mode=0o700):
            self.made_dirs.append(f"{base}/{relative}")
            raise ValidationFailed(
                f"홈 디렉터리가 아직 없습니다: {base}.", detail={"path": base, "user": user}
            )

    ssh = NoHomeSsh(CONNECTION)
    service = build(db, settings, secret_store, slurm_client, ssh)
    with pytest.raises(ValidationFailed) as exc:
        service.create(cluster, SessionSpec(image_ref=IMAGE), user=owner)
    assert "홈 디렉터리가 아직 없습니다" in str(exc.value.message)
    assert [c for c in slurm_client.calls if c[0] == "submit_job"] == []
