"""포털 운영 설정 스키마 (api.md §9, A-OP-01·02·03·04)."""

from datetime import datetime

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
    banner_enabled: bool
    start_at: datetime | None
    end_at: datetime | None
    created_at: datetime


class NoticeCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    body: str | None = None
    banner_enabled: bool = False
    start_at: datetime | None = None
    end_at: datetime | None = None


class NoticeUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    body: str | None = None
    banner_enabled: bool | None = None
    start_at: datetime | None = None
    end_at: datetime | None = None


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


# --- A-OP-02 앱 카탈로그 ----------------------------------------------------
APP_KIND = "^(interactive|batch)$"

class AppCatalogOut(BaseModel):
    """코드 카탈로그의 앱과 등록된 메타데이터를 겹친 한 줄."""

    model_config = ConfigDict(from_attributes=True)

    #: 등록 행의 PK. **None이면 아직 등록되지 않은 코드 앱**이다(수정이 아니라 등록 대상).
    id: int | None
    #: 코드 카탈로그(`session_apps`·`batch_apps`)에 있는 앱인가.
    in_code: bool = False
    kind: str
    app_id: str
    name: str
    vendor: str | None
    version: str | None
    image_file: str | None
    #: 이미지의 출처(OCI 참조). **어디서 왔는지**를 아는 유일한 자리다.
    image_ref: str | None = None
    #: 아이콘 파일명(등록 폼이 고르는 값). 파일이 없으면 None.
    icon_file: str | None = None
    #: 화면이 그대로 <img src>에 넣는 주소. 서버가 파일명으로 만든다.
    icon_url: str | None = None
    description: str | None
    updated_at: datetime | None = None


class AppCatalogCreate(BaseModel):
    kind: str = Field(..., pattern=APP_KIND)
    app_id: str = Field(..., min_length=1, max_length=32)
    name: str = Field(..., min_length=1, max_length=128)
    vendor: str | None = Field(default=None, max_length=128)
    version: str | None = Field(default=None, max_length=32)
    image_file: str | None = Field(default=None, max_length=128)
    #: 모양 검사는 **서비스**가 한다(`app_images.IMAGE_REF`) — 정규식 정본이 거기 있고,
    #: 스키마가 서비스를 import하는 전례를 만들지 않는다.
    image_ref: str | None = Field(default=None, max_length=255)
    icon_file: str | None = Field(default=None, max_length=64)
    description: str | None = None


class AppCatalogUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    vendor: str | None = Field(default=None, max_length=128)
    version: str | None = Field(default=None, max_length=32)
    image_file: str | None = Field(default=None, max_length=128)
    #: 모양 검사는 **서비스**가 한다(`app_images.IMAGE_REF`) — 정규식 정본이 거기 있고,
    #: 스키마가 서비스를 import하는 전례를 만들지 않는다.
    image_ref: str | None = Field(default=None, max_length=255)
    icon_file: str | None = Field(default=None, max_length=64)
    description: str | None = None
