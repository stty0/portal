"""API 토큰 라우터 (C-01) — 기계 클라이언트용 자격증명.

**대상은 언제나 요청자 본인이다.** 사용자명을 받지 않으며, 남의 토큰은 조회도 폐기도
할 수 없다(존재 여부조차 알리지 않는다).
"""

from typing import Annotated

from fastapi import APIRouter, Depends

from app.core.deps import CurrentUser, DbSession
from app.schemas.api_token import ApiTokenCreate, ApiTokenCreated, ApiTokenOut
from app.schemas.common import OkResponse
from app.services.api_token import ApiTokenService

router = APIRouter(tags=["api-tokens"])


def _service(db: DbSession) -> ApiTokenService:
    return ApiTokenService(db)


ApiTokenServiceDep = Annotated[ApiTokenService, Depends(_service)]


@router.get("/me/api-tokens", response_model=list[ApiTokenOut], summary="내 API 토큰 목록")
def list_tokens(user: CurrentUser, service: ApiTokenServiceDep) -> list[ApiTokenOut]:
    return [ApiTokenOut.model_validate(t) for t in service.list_for(user)]


@router.post(
    "/me/api-tokens",
    response_model=ApiTokenCreated,
    status_code=201,
    summary="API 토큰 발급 (원문은 이때만 반환)",
)
def create_token(
    payload: ApiTokenCreate, user: CurrentUser, service: ApiTokenServiceDep
) -> ApiTokenCreated:
    record, raw = service.create(
        user=user, name=payload.name, expires_in_days=payload.expires_in_days
    )
    return ApiTokenCreated(**ApiTokenOut.model_validate(record).model_dump(), token=raw)


@router.delete("/me/api-tokens/{token_id}", response_model=OkResponse, summary="API 토큰 폐기")
def revoke_token(token_id: int, user: CurrentUser, service: ApiTokenServiceDep) -> OkResponse:
    record = service.revoke(token_id, user=user)
    return OkResponse(message=f"'{record.name}' 토큰을 폐기했습니다.")
