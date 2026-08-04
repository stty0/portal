"""도메인 예외 + 오류 응답 형식 (api.md 공통 규약).

응답 형식: {"code": str, "message": str, "detail": any} + HTTP 상태코드.
"""

from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse


class PortalError(Exception):
    """모든 도메인 예외의 베이스."""

    status_code: int = 500
    code: str = "INTERNAL_ERROR"

    def __init__(self, message: str, detail: Any = None):
        super().__init__(message)
        self.message = message
        self.detail = detail


class NotFound(PortalError):
    status_code = 404
    code = "NOT_FOUND"


class Conflict(PortalError):
    status_code = 409
    code = "CONFLICT"


class ValidationFailed(PortalError):
    status_code = 422
    code = "VALIDATION_FAILED"


class Unauthenticated(PortalError):
    status_code = 401
    code = "UNAUTHENTICATED"


class Forbidden(PortalError):
    status_code = 403
    code = "FORBIDDEN"


class BootstrapLocked(PortalError):
    """C-02: seed ADMIN 지정 후 setup 재실행은 서버측 하드 거부."""

    status_code = 409
    code = "BOOTSTRAP_LOCKED"


class ExternalServiceError(PortalError):
    status_code = 502
    code = "EXTERNAL_SERVICE_ERROR"


class SlurmUnauthorized(PortalError):
    """slurmrestd 401 — 클러스터 JWT 만료/무효 (backend-design §2.2).

    사용자 인증 실패가 아니라 **클러스터 토큰 재등록**이 필요한 상황이다.
    """

    status_code = 502
    code = "SLURM_UNAUTHORIZED"


class AdError(ExternalServiceError):
    code = "AD_ERROR"


class SecretNotFound(PortalError):
    status_code = 500
    code = "SECRET_NOT_FOUND"


async def portal_error_handler(request: Request, exc: PortalError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"code": exc.code, "message": exc.message, "detail": exc.detail},
    )


async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    # 내부 예외 메시지를 그대로 노출하지 않는다.
    return JSONResponse(
        status_code=500,
        content={"code": "INTERNAL_ERROR", "message": "서버 오류가 발생했습니다.", "detail": None},
    )
