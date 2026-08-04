"""클러스터별 client 구성 (Architecture.md §3).

slurm client는 클러스터 단위로 구성된다(클러스터별 독립 slurmdbd·독립 JWT).
등록 정보(cluster)와 자격증명(cluster_credential.secret_ref → Secret 저장소)으로
클러스터별 인스턴스를 만들어 **재사용**한다(keep-alive, backend-design §2.1).
"""

from typing import Callable

import httpx

from app.clients.slurm.client import SlurmrestdClient
from app.clients.token_provider import SlurmTokenProvider
from app.core.config import Settings
from app.core.errors import ValidationFailed
from app.models import Cluster


class ClusterClientFactory:
    def __init__(
        self,
        settings: Settings,
        token_provider: SlurmTokenProvider,
        *,
        transport_factory: Callable[[], httpx.BaseTransport] | None = None,
    ):
        self._settings = settings
        self._tokens = token_provider
        self._transport_factory = transport_factory
        self._pool: dict[int, SlurmrestdClient] = {}

    def slurm(self, cluster: Cluster, secret_ref: str) -> SlurmrestdClient:
        # 풀은 앱 lifespan 동안 살아남지만 `cluster`는 **요청 단위 세션**의 ORM 객체다.
        # 클로저에 엔티티를 그대로 가두면, 앞선 요청이 rollback(오류 경로)하며 속성을
        # 만료시킨 뒤 세션이 닫히는 순간 캐시된 client가 죽은 인스턴스를 참조하게 되어
        # 이후 모든 호출이 DetachedInstanceError로 터진다. 세션이 살아 있는 지금
        # 평범한 값으로 복사해 두고, 클로저는 그 값만 붙잡는다.
        cluster_id = cluster.id
        client = self._pool.get(cluster_id)
        if client is not None:
            return client
        base_url = cluster.slurmrestd_url
        if not base_url:
            raise ValidationFailed(
                "클러스터에 slurmrestd 엔드포인트가 설정되어 있지 않습니다.",
                detail={"cluster_id": cluster_id},
            )
        api_version = cluster.api_version or self._settings.slurm_api_version

        client = SlurmrestdClient(
            base_url,
            token_provider=lambda: self._tokens.token(cluster_id, secret_ref),
            api_version=api_version,
            timeout=self._settings.http_timeout_seconds,
            max_retries=self._settings.http_max_retries,
            transport=self._transport_factory() if self._transport_factory else None,
        )
        self._pool[cluster_id] = client
        return client

    def invalidate(self, cluster_id: int) -> None:
        """엔드포인트·자격증명 변경 시 호출 — 다음 사용에서 새 인스턴스가 만들어진다."""
        client = self._pool.pop(cluster_id, None)
        if client is not None:
            client.close()
        self._tokens.invalidate(cluster_id)

    def close_all(self) -> None:
        for client in self._pool.values():
            client.close()
        self._pool.clear()
