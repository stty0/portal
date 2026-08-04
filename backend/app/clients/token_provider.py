"""Slurm JWT 공급자 (backend-design §2.2, Architecture.md §3).

slurmrestd에는 자동 갱신 API가 없다(재발급만). 외부 소유 클러스터라 scontrol
접근도 불가하므로, 관리자가 등록한 JWT를 Secret 저장소에서 읽어 쓰고
`exp`를 디코드해 만료를 사전에 알린다. 401 발생 시 재등록 안내가 필요하다.
"""

from datetime import datetime, timezone

from app.core.errors import SecretNotFound, SlurmUnauthorized
from app.core.secrets import SecretStore
from app.core.security import decode_slurm_token_exp


class SlurmTokenProvider:
    def __init__(self, secrets: SecretStore):
        self._secrets = secrets
        self._cache: dict[int, str] = {}
        self._unauthorized: set[int] = set()

    def token(self, cluster_id: int, secret_ref: str) -> str:
        if cluster_id not in self._cache:
            try:
                self._cache[cluster_id] = self._secrets.get(secret_ref)
            except SecretNotFound as exc:
                raise SlurmUnauthorized(
                    "클러스터 JWT가 등록되어 있지 않습니다. 자격증명을 등록하세요.",
                    detail={"cluster_id": cluster_id},
                ) from exc
        return self._cache[cluster_id]

    def expires_at(self, cluster_id: int, secret_ref: str) -> datetime | None:
        return decode_slurm_token_exp(self.token(cluster_id, secret_ref))

    def is_expired(self, cluster_id: int, secret_ref: str) -> bool:
        exp = self.expires_at(cluster_id, secret_ref)
        return exp is not None and exp <= datetime.now(timezone.utc)

    def on_unauthorized(self, cluster_id: int) -> None:
        """401 감지 — 캐시를 버리고 재등록 필요 상태로 표시(반자동 플로우, §2.2)."""
        self._cache.pop(cluster_id, None)
        self._unauthorized.add(cluster_id)

    def needs_reregistration(self, cluster_id: int) -> bool:
        return cluster_id in self._unauthorized

    def invalidate(self, cluster_id: int) -> None:
        """무중단 교체: 새 토큰 등록 시 캐시만 비우면 다음 호출부터 신규 토큰."""
        self._cache.pop(cluster_id, None)
        self._unauthorized.discard(cluster_id)
