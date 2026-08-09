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
from app.core.errors import ExternalServiceError, SlurmUnauthorized


class SlurmrestdClient(BaseHttpClient):
    def __init__(
        self,
        base_url: str,
        *,
        token_provider,
        api_version: str = "v0.0.43",
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
        if response.status_code >= 400:
            # **Slurm은 거절 사유를 본문에 정확히 적어 준다.** 그걸 버리고 "외부 서비스
            # 호출이 실패했습니다"만 올리면, 화면에는 응답 원문이 통째로 찍히고 사용자는
            # 무엇을 고쳐야 할지 알 수 없다(실측: 자원 초과 제출이 그렇게 보였다).
            failure = _slurm_error(response)
            if failure is not None:
                return failure
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

    def update_node(self, name: str, patch: dict[str, Any]) -> Any:
        """노드 상태 변경 (A-ND-01).

        **사용자로 위장하지 않는다** — 노드 제어는 운영자 권한이 필요해서 일반 사용자로
        위장하면 거부된다(계정 쓰기와 같은 이유). 토큰 소유자 권한으로 수행하고
        "누가 시켰는가"는 포털 RBAC(ADMIN 전용)와 감사 로그가 남긴다.
        """
        return self._call("POST", "slurm", f"/node/{name}", as_user=None, json=patch)

    def get_partitions(self, *, as_user: str | None = None) -> Any:
        return self._call("GET", "slurm", "/partitions", as_user=as_user)

    def get_reservations(self, *, as_user: str | None = None) -> Any:
        return self._call("GET", "slurm", "/reservations", as_user=as_user)

    def create_reservation(self, desc: dict[str, Any]) -> Any:
        """예약 생성 (A-ND-04). **v0.0.43에만 있는 엔드포인트다** — 0.0.40~0.0.42는
        조회·삭제만 연다(실측). 포털이 0.0.43에 고정된 이유가 이것이다.

        노드 제어와 같이 **위장하지 않는다** — 운영자 권한이 필요하다.
        """
        return self._call("POST", "slurm", "/reservation", as_user=None, json=desc)

    def delete_reservation(self, name: str) -> Any:
        return self._call("DELETE", "slurm", f"/reservation/{name}", as_user=None)

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


#: 사용자가 스스로 고칠 수 있는 거절에 붙이는 안내. Slurm의 원문만으로는 **무엇을**
#: 줄여야 하는지 알 수 없다 — 특히 2014는 CPU·메모리·GPU 중 무엇이 넘쳤는지 말해 주지 않는다.
_SLURM_HINTS = {
    2014: "요청한 CPU·메모리·GPU가 이 파티션의 노드 한 대보다 큽니다 — 자원 값을 줄여 보세요.",
    2015: "요청한 파티션이 없거나 쓸 수 없습니다.",
    # 실측: 없는 Job 번호에 `afterok`을 걸면 **제출 자체가 거부된다**(대기 상태로도 안 간다).
    2038: "의존성 표기가 잘못됐거나 대상 Job이 없습니다 — 예: afterok:1234",
    2043: "요청한 파티션에 접근 권한이 없습니다.",
    2072: "이 클러스터에 요청한 GRES(GPU 등)가 없습니다.",
    2115: "TRES 표기가 올바르지 않습니다.",
    5005: "이 계정·QOS로는 제출할 수 없습니다.",
}


def _slurm_error(response: httpx.Response) -> ExternalServiceError | None:
    """slurmrestd 오류 본문 → 읽을 수 있는 예외. 형태가 다르면 None(상위 기본 처리)."""
    try:
        body = response.json()
    except ValueError:
        return None
    errors = body.get("errors") if isinstance(body, dict) else None
    first = errors[0] if isinstance(errors, list) and errors and isinstance(errors[0], dict) else None
    if first is None:
        return None
    number = first.get("error_number")
    reason = first.get("description") or first.get("error") or "요청이 거부되었습니다."
    detail_text = first.get("error")
    if detail_text and detail_text != reason:
        reason = f"{reason} ({detail_text})"
    hint = _SLURM_HINTS.get(number if isinstance(number, int) else -1)
    return ExternalServiceError(
        f"Slurm이 요청을 거부했습니다: {reason}" + (f" — {hint}" if hint else ""),
        detail={"status": response.status_code, "error_number": number, "body": body},
    )
