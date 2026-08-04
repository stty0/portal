"""공통 스키마 (api.md 공통 규약)."""

from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class ErrorResponse(BaseModel):
    code: str
    message: str
    detail: Any = None


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int = 1
    size: int = 50


class PageParams(BaseModel):
    page: int = Field(1, ge=1)
    size: int = Field(50, ge=1, le=200)

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.size


class OkResponse(BaseModel):
    ok: bool = True
    message: str | None = None
