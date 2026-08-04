"""인증 스키마 (api.md §1)."""

from pydantic import BaseModel, Field


class SetupStatus(BaseModel):
    bootstrap_required: bool


class SetupProbeRequest(BaseModel):
    """부트스트랩 1단계 — AD 연결만 검증한다(저장 없음)."""

    setup_token: str = Field(..., min_length=1)
    ldaps_url: str
    base_dn: str
    bind_account: str
    bind_password: str = Field(..., min_length=1)
    allowed_group: str | None = None
    id_attribute: str = "sAMAccountName"


class AdCandidate(BaseModel):
    """seed ADMIN 후보. AD에서 실제로 조회된 계정만 나온다."""

    object_guid: str
    username: str
    display_name: str | None = None
    email: str | None = None


class SetupProbeResponse(BaseModel):
    ok: bool
    users: list[AdCandidate]


class SetupRequest(BaseModel):
    setup_token: str = Field(..., min_length=1)
    ldaps_url: str
    base_dn: str
    bind_account: str
    bind_password: str = Field(..., min_length=1)  # Secret 저장소로만 흘러간다
    allowed_group: str | None = None
    id_attribute: str = "sAMAccountName"
    seed_admin_username: str = Field(..., min_length=1)


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1)
    password: str = Field(..., min_length=1)


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class MeResponse(BaseModel):
    username: str
    display_name: str | None
    role: str | None
    permissions: list[str]
    default_cluster_id: int | None
