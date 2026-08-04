"""REST 공통 베이스 (Architecture.md §3).

base_url·타임아웃·재시도(멱등 op 한정)·TLS 검증·keep-alive 세션 풀·
상태코드→도메인 예외 매핑을 여기에 집약한다.
`SlurmrestdClient`(slurmrestd)와 `ScpBillingClient`(SCP Billing API)가 공유한다 —
AdClient(LDAP)·SshClient(SSH)는 프로토콜이 달라 상속하지 않는다(투기적 추상화 배제).
"""

from typing import Any

import httpx

from app.core.errors import ExternalServiceError, NotFound, PortalError

IDEMPOTENT_METHODS = frozenset({"GET", "HEAD", "OPTIONS", "PUT", "DELETE"})


class BaseHttpClient:
    def __init__(
        self,
        base_url: str,
        *,
        timeout: float = 10.0,
        max_retries: int = 2,
        verify: bool = True,
        transport: httpx.BaseTransport | None = None,
    ):
        self.base_url = base_url.rstrip("/")
        self._max_retries = max_retries
        # keep-alive 커넥션 풀 — 앱 lifespan 동안 재사용(backend-design §2.1)
        self._client = httpx.Client(
            base_url=self.base_url, timeout=timeout, verify=verify, transport=transport
        )

    # --- 서브클래스 훅 -------------------------------------------------
    def _headers(self) -> dict[str, str]:
        """매 호출 헤더. 인증 헤더는 서브클래스가 구성한다."""
        return {}

    def _map_status(self, response: httpx.Response) -> PortalError | None:
        """상태코드 → 도메인 예외. 서브클래스가 확장한다."""
        if response.status_code == 404:
            return NotFound("외부 서비스에서 대상을 찾을 수 없습니다.", detail=_safe_body(response))
        if response.status_code >= 400:
            return ExternalServiceError(
                "외부 서비스 호출이 실패했습니다.",
                detail={"status": response.status_code, "body": _safe_body(response)},
            )
        return None

    # --- 호출 ----------------------------------------------------------
    def request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: Any = None,
        headers: dict[str, str] | None = None,
    ) -> Any:
        merged = {**self._headers(), **(headers or {})}
        # 재시도는 멱등 op에 한정한다 — POST 재시도는 중복 제출을 만든다.
        attempts = self._max_retries + 1 if method.upper() in IDEMPOTENT_METHODS else 1
        last_exc: Exception | None = None

        for attempt in range(attempts):
            try:
                response = self._client.request(
                    method, path, params=params, json=json, headers=merged
                )
            except httpx.TimeoutException as exc:
                last_exc = exc
                continue
            except httpx.HTTPError as exc:
                raise ExternalServiceError(
                    "외부 서비스에 연결할 수 없습니다.", detail=str(exc)
                ) from exc

            error = self._map_status(response)
            if error is not None:
                # 5xx만 재시도 가치가 있다. 4xx는 재시도해도 같은 결과다.
                if response.status_code >= 500 and attempt < attempts - 1:
                    last_exc = error
                    continue
                raise error
            return _parse_body(response)

        raise ExternalServiceError(
            "외부 서비스 응답이 없습니다(타임아웃).", detail=str(last_exc) if last_exc else None
        )

    def close(self) -> None:
        self._client.close()


def _parse_body(response: httpx.Response) -> Any:
    if not response.content:
        return None
    try:
        return response.json()
    except ValueError:
        return response.text


def _safe_body(response: httpx.Response) -> Any:
    """오류 상세를 제한된 크기로만 노출한다(민감정보·대용량 방지)."""
    try:
        return response.json()
    except ValueError:
        return response.text[:500]
