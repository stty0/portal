"""사용자·AD 스키마 (api.md §2)."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    ad_object_guid: str
    username: str
    display_name: str | None
    email: str | None
    is_active: bool
    default_cluster_id: int | None
    last_login_at: datetime | None
    role: str | None = None

    @field_validator("role", mode="before")
    @classmethod
    def _role_code(cls, value):
        return getattr(value, "code", value)


class UserUpdate(BaseModel):
    """AD 신원 필드(username·display_name·email)는 의도적으로 없다 — 수정 불가."""

    role: str | None = None
    is_active: bool | None = None


class AdConnectionOut(BaseModel):
    """bind 암호는 참조 여부만 노출하고 값은 절대 내보내지 않는다."""

    model_config = ConfigDict(from_attributes=True)

    ldaps_url: str | None
    base_dn: str | None
    bind_account: str | None
    allowed_group: str | None
    id_attribute: str | None
    sync_interval: str | None
    last_sync_at: datetime | None
    last_sync_result: str | None
    bind_secret_configured: bool = False
    bootstrap_completed: bool = False


class AdConnectionUpdate(BaseModel):
    ldaps_url: str | None = None
    base_dn: str | None = None
    bind_account: str | None = None
    bind_password: str | None = Field(None, min_length=1)  # 재입력 시에만 변경
    allowed_group: str | None = None
    id_attribute: str | None = None
    sync_interval: str | None = None


class AdSyncResult(BaseModel):
    ok: bool
    created: int
    updated: int
    deactivated: int
    message: str
