"""API 토큰 스키마 (C-01)."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ApiTokenOut(BaseModel):
    """목록·상세. **원문 토큰은 절대 담기지 않는다** — 발급 응답에만 한 번 나온다."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    prefix: str
    created_at: datetime
    expires_at: datetime | None
    last_used_at: datetime | None
    revoked_at: datetime | None


class ApiTokenCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=64)
    #: 비우면 만료 없음. 화면은 기본값을 제안하되 강제하지 않는다.
    expires_in_days: int | None = Field(default=90, ge=1, le=365)


class ApiTokenCreated(ApiTokenOut):
    #: **이 화면을 벗어나면 다시 볼 수 없다.** 서버에는 해시만 남는다.
    token: str
