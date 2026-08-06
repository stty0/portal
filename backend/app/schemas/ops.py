"""포털 운영 설정 스키마 (api.md §9, A-OP-01·02·03·04)."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


# --- A-OP-04 시스템 설정 ---------------------------------------------------
class SettingsOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    #: C-04 — 실시간성 요구가 30초 이하다.
    poll_interval_sec: int
    session_timeout_min: int
    smtp_host: str | None
    smtp_port: int | None
    smtp_sender: str | None
    webhook_url: str | None
    updated_at: datetime | None = None


class SettingsUpdate(BaseModel):
    poll_interval_sec: int | None = Field(default=None, ge=5, le=30)
    session_timeout_min: int | None = Field(default=None, ge=5, le=10080)
    smtp_host: str | None = None
    smtp_port: int | None = Field(default=None, ge=1, le=65535)
    smtp_sender: str | None = None
    webhook_url: str | None = None


# --- A-OP-01 공지 -----------------------------------------------------------
class NoticeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    body: str | None
    target_cluster_id: int | None
    banner_enabled: bool
    start_at: datetime | None
    end_at: datetime | None
    created_at: datetime


class NoticeCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    body: str | None = None
    #: NULL = 전체 클러스터 대상
    target_cluster_id: int | None = None
    banner_enabled: bool = False
    start_at: datetime | None = None
    end_at: datetime | None = None


class NoticeUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    body: str | None = None
    target_cluster_id: int | None = None
    banner_enabled: bool | None = None
    start_at: datetime | None = None
    end_at: datetime | None = None


# --- A-OP-02 템플릿 ---------------------------------------------------------
class TemplateOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    type: str | None
    version: str | None
    params: dict[str, Any] | None
    is_public: bool
    created_at: datetime
    updated_at: datetime


class TemplateCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    type: str | None = Field(default="batch", pattern="^(batch|interactive)$")
    version: str | None = Field(default=None, max_length=16)
    #: 템플릿 본문·기본값. JobService가 `script`/치환 파라미터로 해석한다.
    params: dict[str, Any] | None = None
    is_public: bool = True


class TemplateUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    type: str | None = Field(default=None, pattern="^(batch|interactive)$")
    version: str | None = Field(default=None, max_length=16)
    params: dict[str, Any] | None = None
    is_public: bool | None = None


# --- A-OP-03 감사 로그 ------------------------------------------------------
class AuditLogOut(BaseModel):
    id: int
    at: datetime
    #: 표시용 이름. GUID는 화면에서 쓸모가 없어 서버가 바꿔 준다.
    actor: str | None
    actor_role: str | None
    action: str
    cluster_id: int | None
    target: str | None
    detail: str | None
    ip: str | None
