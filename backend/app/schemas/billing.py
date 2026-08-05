"""비용/Billing 스키마 (A-BL-01·02).

키는 요청으로만 들어오고 응답 모델에는 **존재하지 않는다** — 실수로 흘리지 않도록
아예 필드를 두지 않는다(클러스터 자격증명과 같은 방식).
"""

from datetime import datetime

from pydantic import BaseModel, Field


class BillingCredentialsPut(BaseModel):
    access_key: str = Field(..., min_length=8)
    secret_key: str = Field(..., min_length=8)
    monthly_alert_krw: int | None = Field(default=None, ge=0)


class BillingConfigOut(BaseModel):
    configured: bool
    scp_account_id: str | None = None
    api_endpoint: str | None = None
    monthly_alert_krw: int | None = None
    last_verified_at: datetime | None = None


class BillingRuleIn(BaseModel):
    kind: str = Field(default="tag", pattern="^(tag|resource_id|billing_item_id|service_category)$")
    condition: str = Field(..., min_length=1, max_length=255)
    mapping_label: str | None = Field(default=None, max_length=128)
