"""비용/Billing 라우터 (A-BL-01·02·03). 전부 ADMIN 전용."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends

from app.core.deps import AdminUser, DbSession, SecretStoreDep
from app.schemas.billing import BillingCredentialsPut, BillingRuleIn
from app.schemas.common import OkResponse
from app.services.billing import BillingService

router = APIRouter(tags=["billing"])


def _service(db: DbSession, secrets: SecretStoreDep) -> BillingService:
    return BillingService(db, secrets=secrets)


BillingServiceDep = Annotated[BillingService, Depends(_service)]


@router.get("/billing/config", summary="SCP 연동 상태 (A-BL-01)")
def config(actor: AdminUser, service: BillingServiceDep) -> dict[str, Any]:
    # 키 값은 포함하지 않는다 — 설정 여부와 메타만.
    return service.config()


@router.put("/billing/config", summary="SCP 자격증명 등록·변경 (A-BL-01)")
def put_config(
    payload: BillingCredentialsPut, actor: AdminUser, service: BillingServiceDep
) -> dict[str, Any]:
    """키는 Secret 저장소로만 흘러가고 응답에 실리지 않는다. 저장 전 실제 조회로 검증한다."""
    return service.save_credentials(
        actor=actor,
        access_key=payload.access_key,
        secret_key=payload.secret_key,
        monthly_alert_krw=payload.monthly_alert_krw,
    )


@router.get("/billing/trend", summary="비용 추이 (A-BL-03)")
def trend(
    actor: AdminUser, service: BillingServiceDep, days: int = 30, tag: str | None = None
) -> dict[str, Any]:
    """`tag=purpose=hpc` 형태로 태그 필터를 건다(A-BL-02)."""
    return service.trend(days=days, tag=tag, actor=actor)


@router.get("/billing/rules", summary="자원 식별 규칙 목록 (A-BL-02)")
def list_rules(actor: AdminUser, service: BillingServiceDep) -> list[dict[str, Any]]:
    return [
        {
            "id": r.id,
            "kind": r.kind,
            "condition": r.condition,
            "mapping_label": r.mapping_label,
            "is_active": r.is_active,
        }
        for r in service.rules()
    ]


@router.post("/billing/rules", status_code=201, summary="자원 식별 규칙 추가 (A-BL-02)")
def add_rule(
    payload: BillingRuleIn, actor: AdminUser, service: BillingServiceDep
) -> dict[str, Any]:
    rule = service.add_rule(
        actor=actor,
        kind=payload.kind,
        condition=payload.condition,
        mapping_label=payload.mapping_label,
    )
    return {"id": rule.id, "condition": rule.condition, "mapping_label": rule.mapping_label}


@router.delete("/billing/rules/{rule_id}", summary="자원 식별 규칙 삭제 (A-BL-02)")
def delete_rule(rule_id: int, actor: AdminUser, service: BillingServiceDep) -> OkResponse:
    service.delete_rule(rule_id, actor=actor)
    return OkResponse(ok=True)
