"""slurmrestd 클라이언트 (Architecture.md §2).

slurmctld(`/slurm/{ver}`)와 slurmdbd(`/slurmdb/{ver}`)는 경로 접두만 다른 동일
엔드포인트·동일 JWT라 client는 하나로 통합한다. 도메인 분리는 service 계층이 한다.

보안(backend-design §2.3): `X-SLURM-USER-NAME`은 "누구로든 위장 가능한" 헤더다.
호출자는 이 값을 문자열로 직접 넘길 수 없고, 서버가 인증한 주체를 나타내는
`as_user`로만 전달된다 — 라우터/스키마에서 사용자명을 받지 않는다.
"""

from typing import Any

import httpx

from app.clients.base_http import BaseHttpClient
from app.core.errors import SlurmUnauthorized


class SlurmrestdClient(BaseHttpClient):
    def __init__(
        self,
        base_url: str,
        *,
        token_provider,
        api_version: str = "v0.0.41",
        timeout: float = 10.0,
        max_retries: int = 2,
        transport: httpx.BaseTransport | None = None,
    ):
        super().__init__(
            base_url, timeout=timeout, max_retries=max_retries, transport=transport
        )
        self._token_provider = token_provider
        self.api_version = api_version

    # --- 헤더 / 예외 매핑 ---------------------------------------------
    def _headers(self) -> dict[str, str]:
        return {"X-SLURM-USER-TOKEN": self._token_provider(), "Accept": "application/json"}

    def _map_status(self, response: httpx.Response) -> Exception | None:
        if response.status_code == 401:
            # 사용자 인증 실패가 아니라 클러스터 JWT 문제다 → 토큰 재등록 안내(§2.2)
            return SlurmUnauthorized(
                "클러스터 JWT가 만료되었거나 유효하지 않습니다. 토큰을 재등록하세요.",
                detail={"status": 401},
            )
        return super()._map_status(response)

    def _call(self, method: str, group: str, path: str, *, as_user: str | None, **kw) -> Any:
        headers = {"X-SLURM-USER-NAME": as_user} if as_user else {}
        return self.request(method, f"/{group}/{self.api_version}{path}", headers=headers, **kw)

    # --- slurmctld 그룹 (Architecture.md §2.1) -------------------------
    def ping(self) -> Any:
        return self._call("GET", "slurm", "/ping", as_user=None)

    def diag(self) -> Any:
        return self._call("GET", "slurm", "/diag", as_user=None)

    def get_jobs(self, *, as_user: str | None = None, **params) -> Any:
        return self._call("GET", "slurm", "/jobs", as_user=as_user, params=params or None)

    def get_job(self, job_id: str, *, as_user: str | None = None) -> Any:
        return self._call("GET", "slurm", f"/job/{job_id}", as_user=as_user)

    def submit_job(self, spec: dict[str, Any], *, as_user: str) -> Any:
        return self._call("POST", "slurm", "/job/submit", as_user=as_user, json=spec)

    def cancel_job(self, job_id: str, *, as_user: str) -> Any:
        return self._call("DELETE", "slurm", f"/job/{job_id}", as_user=as_user)

    def update_job(self, job_id: str, patch: dict[str, Any], *, as_user: str) -> Any:
        return self._call("POST", "slurm", f"/job/{job_id}", as_user=as_user, json=patch)

    def get_nodes(self, *, as_user: str | None = None) -> Any:
        return self._call("GET", "slurm", "/nodes", as_user=as_user)

    def get_node(self, name: str, *, as_user: str | None = None) -> Any:
        return self._call("GET", "slurm", f"/node/{name}", as_user=as_user)

    def get_partitions(self, *, as_user: str | None = None) -> Any:
        return self._call("GET", "slurm", "/partitions", as_user=as_user)

    def get_reservations(self, *, as_user: str | None = None) -> Any:
        return self._call("GET", "slurm", "/reservations", as_user=as_user)

    # --- slurmdbd 그룹 (Architecture.md §2.2, = sacct/sacctmgr/sreport) --
    def get_accounting_jobs(self, *, as_user: str | None = None, **params) -> Any:
        return self._call("GET", "slurmdb", "/jobs", as_user=as_user, params=params or None)

    def get_accounts(self, *, as_user: str | None = None) -> Any:
        return self._call("GET", "slurmdb", "/accounts", as_user=as_user)

    def get_associations(self, *, as_user: str | None = None) -> Any:
        return self._call("GET", "slurmdb", "/associations", as_user=as_user)

    # --- 계정·연결 쓰기 (A-US-02) ---------------------------------------
    # 이 조작들은 **사용자로 위장하지 않는다**(as_user 없음). slurmdbd 쓰기에는 AdminLevel이
    # 필요해서, 일반 사용자로 위장하면 `Access/permission denied`(2002)가 난다(실측).
    # 토큰 소유자(SlurmUser) 권한으로 수행하고, "누가 시켰는가"는 포털 RBAC(ADMIN 전용)와
    # 감사 로그가 남긴다. Job 조작이 임퍼소네이션을 쓰는 것과 목적이 다르다.
    def create_account(self, account: dict[str, Any], cluster_name: str) -> Any:
        """계정 생성 + 클러스터 association 노드 생성.

        `/accounts/`만 호출하면 계정 레코드는 생기지만 클러스터 association이 없어
        사용자를 붙일 수 없다(users_association이 304를 돌려준다 — 실측).
        `/accounts_association/`이 둘을 한 번에 만든다.
        """
        return self._call(
            "POST",
            "slurmdb",
            "/accounts_association/",
            as_user=None,
            json={
                "accounts": [account],
                "association_condition": {
                    "accounts": [account["name"]],
                    "clusters": [cluster_name],
                },
            },
        )

    def delete_account(self, name: str) -> Any:
        return self._call("DELETE", "slurmdb", f"/account/{name}", as_user=None)

    def add_user_association(self, *, username: str, account: str, cluster_name: str) -> Any:
        return self._call(
            "POST",
            "slurmdb",
            "/users_association/",
            as_user=None,
            json={
                "association_condition": {
                    "accounts": [account],
                    "clusters": [cluster_name],
                    "users": [username],
                },
                "user": {"name": username},
            },
        )

    def set_association_qos(
        self, *, account: str, username: str, cluster_name: str, qos: list[str]
    ) -> Any:
        """association의 허용 QOS 목록을 덮어쓴다 (A-US-03).

        `username=""`이면 **계정 단위** association(계정 노드)이 대상이다.
        """
        return self._call(
            "POST",
            "slurmdb",
            "/associations/",
            as_user=None,
            json={
                "associations": [
                    {
                        "account": account,
                        "user": username,
                        "cluster": cluster_name,
                        "partition": "",
                        "qos": qos,
                    }
                ]
            },
        )

    def delete_association(self, *, username: str, account: str, cluster_name: str) -> Any:
        return self._call(
            "DELETE",
            "slurmdb",
            "/association/",
            as_user=None,
            params={"account": account, "user": username, "cluster": cluster_name},
        )

    def get_qos(self, *, as_user: str | None = None) -> Any:
        return self._call("GET", "slurmdb", "/qos", as_user=as_user)

    def create_qos(self, qos: dict[str, Any]) -> Any:
        return self._call("POST", "slurmdb", "/qos/", as_user=None, json={"qos": [qos]})

    def delete_qos(self, name: str) -> Any:
        return self._call("DELETE", "slurmdb", f"/qos/{name}", as_user=None)

    def get_slurm_user(self, username: str, *, as_user: str | None = None) -> Any:
        return self._call("GET", "slurmdb", f"/user/{username}", as_user=as_user)
