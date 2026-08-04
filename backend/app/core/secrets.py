"""Secret 저장소 (backend-design §6, Architecture.md §3).

DB에는 `secret_ref`만 저장하고 실값은 이 저장소에서 해석한다.
구체 구현은 §9 미확정(K8s Secret / Vault / SCP Secret Manager) — 호출부는
`SecretStore` 인터페이스에만 의존하므로 저장소 교체 시 영향이 없다.
"""

import os
from abc import ABC, abstractmethod

from app.core.config import Settings
from app.core.errors import SecretNotFound


class SecretStore(ABC):
    @abstractmethod
    def get(self, secret_ref: str) -> str:
        """참조를 실값으로 해석한다. 없으면 SecretNotFound."""

    @abstractmethod
    def put(self, secret_ref: str, value: str) -> None:
        """실값을 저장한다. DB에는 secret_ref만 남는다."""

    @abstractmethod
    def delete(self, secret_ref: str) -> None: ...


class EnvSecretStore(SecretStore):
    """환경변수 기반 구현.

    K8s Secret을 env/volume으로 주입하는 배포 형태를 그대로 수용한다.
    `put`은 프로세스 내 오버레이에만 쓴다(런타임 등록분) — 영속화는 배포 수단이 담당.
    """

    def __init__(self, settings: Settings):
        self._prefix = settings.secret_env_prefix
        self._overlay: dict[str, str] = {}

    def _key(self, secret_ref: str) -> str:
        return self._prefix + secret_ref.replace("/", "_").replace("-", "_").upper()

    def get(self, secret_ref: str) -> str:
        if secret_ref in self._overlay:
            return self._overlay[secret_ref]
        value = os.environ.get(self._key(secret_ref))
        if value is None:
            raise SecretNotFound(
                "Secret 참조를 해석할 수 없습니다.", detail={"secret_ref": secret_ref}
            )
        return value

    def put(self, secret_ref: str, value: str) -> None:
        self._overlay[secret_ref] = value

    def delete(self, secret_ref: str) -> None:
        self._overlay.pop(secret_ref, None)


def build_secret_ref(kind: str, owner: str | int) -> str:
    """일관된 참조 문자열 생성. 예: cluster/3/SLURM_JWT."""
    return f"{kind}/{owner}"
