"""비용/Billing 서비스 (A-BL-01·02·03).

키는 **SCP 계정 단위 전역 설정 1건**이다(클러스터별 아님).
실값은 Secret 저장소에만 두고 DB(`billing_config`)에는 참조와 메타만 남긴다.
"""

from __future__ import annotations

import collections
from datetime import date, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.clients.scp.client import (
    COST_API,
    ScpBillingClient,
    ScpCredentials,
    normalize_resource_id,
)
from app.core.errors import SecretNotFound, ValidationFailed
from app.core.secrets import SecretStore
from app.db.base import utcnow
from app.models import BillingConfig, BillingRule, User
from app.services.audit import AuditService

SCP_ACCESS_KEY_REF = "scp/access_key"
SCP_SECRET_KEY_REF = "scp/secret_key"


class BillingService:
    def __init__(self, session: Session, *, secrets: SecretStore):
        self.session = session
        self.secrets = secrets
        self.audit = AuditService(session)

    # --- 설정 (A-BL-01) --------------------------------------------------
    def _config(self) -> BillingConfig | None:
        return self.session.scalar(select(BillingConfig).limit(1))

    def config(self) -> dict[str, Any]:
        """연동 상태만 돌려준다 — **키 값은 어떤 경로로도 응답에 넣지 않는다**."""
        conf = self._config()
        return {
            "configured": self._has_credentials(),
            "scp_account_id": conf.scp_account_id if conf else None,
            "api_endpoint": conf.api_endpoint if conf else None,
            "monthly_alert_krw": conf.monthly_alert_krw if conf else None,
            "last_verified_at": conf.last_verified_at if conf else None,
        }

    def _has_credentials(self) -> bool:
        try:
            return bool(self.secrets.get(SCP_ACCESS_KEY_REF) and self.secrets.get(SCP_SECRET_KEY_REF))
        except SecretNotFound:
            return False

    def _client(self) -> ScpBillingClient:
        if not self._has_credentials():
            raise ValidationFailed(
                "SCP 자격증명이 설정되어 있지 않습니다. "
                "Secret 저장소에 SCP access/secret key를 등록하세요."
            )
        return ScpBillingClient(
            ScpCredentials(
                access_key=self.secrets.get(SCP_ACCESS_KEY_REF),
                secret_key=self.secrets.get(SCP_SECRET_KEY_REF),
            )
        )

    def save_credentials(
        self, *, actor: User, access_key: str, secret_key: str, monthly_alert_krw: int | None
    ) -> dict[str, Any]:
        """키를 저장하기 전에 **실제로 조회해 본다**.

        틀린 키를 그대로 받으면 화면은 "설정됨"인데 조회만 계속 실패해 원인을 찾기 어렵다.
        클러스터 등록의 REST 연결 테스트와 같은 태도다.
        """
        probe = ScpBillingClient(ScpCredentials(access_key=access_key, secret_key=secret_key))
        today = date.today()
        rows = probe.usages(
            start_date=str(today - timedelta(days=1)), end_date=str(today), max_pages=1
        )

        self.secrets.put(SCP_ACCESS_KEY_REF, access_key)
        self.secrets.put(SCP_SECRET_KEY_REF, secret_key)

        conf = self._config() or BillingConfig()
        conf.access_key = access_key  # 식별용 — 서명에 쓰는 secret은 DB에 없다
        conf.secret_ref = SCP_SECRET_KEY_REF
        conf.api_endpoint = f"https://{COST_API}.e.samsungsdscloud.com"
        conf.last_verified_at = utcnow()
        if monthly_alert_krw is not None:
            conf.monthly_alert_krw = monthly_alert_krw
        if rows:
            conf.scp_account_id = str(rows[0].get("account_id") or "") or None
        if conf.id is None:
            self.session.add(conf)
        # 감사 로그에 키를 남기지 않는다 — 계정 ID와 검증 결과만.
        self.audit.record(
            actor=actor,
            action="BILLING_CONFIG_UPDATE",
            target=conf.scp_account_id or "scp",
            detail=f"verified records={len(rows)}",
        )
        self.session.commit()
        return self.config()

    # --- 사용 내역·추이 (A-BL-03) ---------------------------------------
    def trend(
        self, *, days: int = 30, tag: str | None = None, actor: User | None = None
    ) -> dict[str, Any]:
        end = date.today()
        start = end - timedelta(days=days)
        client = self._client()
        rows = client.usages(start_date=str(start), end_date=str(end))

        # 태그 필터 (A-BL-02) — 비용 응답에는 태그가 없어 자원 목록을 따로 받아 걸러낸다.
        matched: int | None = None
        if tag:
            key, _, value = tag.partition("=")
            ids = client.tagged_resource_ids(key=key.strip(), value=value.strip() or None)
            rows = [r for r in rows if normalize_resource_id(r.get("resource_id")) in ids]
            matched = len(ids)

        by_day: dict[str, float] = collections.defaultdict(float)
        by_category: dict[str, float] = collections.defaultdict(float)
        by_item: dict[str, float] = collections.defaultdict(float)
        for u in rows:
            krw = _krw(u)
            by_day[str(u.get("usage_date", ""))[:10]] += krw
            by_category[str(u.get("service_category") or "UNKNOWN")] += krw
            by_item[str(u.get("billing_item_id") or "UNKNOWN")] += krw

        # 계정 ID·엔드포인트는 손 입력이 아니라 **응답에서 확인된 값**을 정본으로 삼는다
        # (클러스터 이름을 slurm.conf에서 가져오는 것과 같은 원칙).
        conf = self._config() or BillingConfig()
        conf.last_verified_at = utcnow()
        conf.api_endpoint = f"https://{COST_API}.e.samsungsdscloud.com"
        if rows:
            conf.scp_account_id = str(rows[0].get("account_id") or "") or None
        if conf.id is None:
            self.session.add(conf)
        self.session.commit()

        return {
            "start": str(start),
            "end": str(end),
            "total_krw": round(sum(by_category.values())),
            "daily": [{"date": d, "krw": round(v)} for d, v in sorted(by_day.items()) if d],
            "by_category": _top(by_category),
            "by_item": _top(by_item),
            "record_count": len(rows),
            "tag": tag,
            "tagged_resource_count": matched,
        }

    # --- 자원 식별 규칙 (A-BL-02) ---------------------------------------
    def rules(self) -> list[BillingRule]:
        return list(
            self.session.scalars(
                select(BillingRule).order_by(BillingRule.sort_order, BillingRule.id)
            )
        )

    def add_rule(self, *, actor: User, kind: str, condition: str, mapping_label: str | None) -> BillingRule:
        rule = BillingRule(
            kind=kind, condition=condition, mapping_label=mapping_label, is_active=True
        )
        self.session.add(rule)
        self.audit.record(actor=actor, action="BILLING_RULE_ADD", target=condition)
        self.session.commit()
        return rule

    def delete_rule(self, rule_id: int, *, actor: User) -> None:
        rule = self.session.get(BillingRule, rule_id)
        if rule is None:
            raise ValidationFailed("규칙을 찾을 수 없습니다.", detail={"rule_id": rule_id})
        self.session.delete(rule)
        self.audit.record(actor=actor, action="BILLING_RULE_DELETE", target=rule.condition)
        self.session.commit()


def _krw(usage: dict[str, Any]) -> float:
    """금액은 문자열로 온다(`"106.3225806452"`). 빈 값·None을 0으로 흡수한다."""
    amounts = usage.get("amounts") or {}
    try:
        return float(amounts.get("krw") or 0)
    except (TypeError, ValueError):
        return 0.0


def _top(values: dict[str, float], limit: int = 12) -> list[dict[str, Any]]:
    ordered = sorted(values.items(), key=lambda kv: kv[1], reverse=True)[:limit]
    return [{"label": k, "krw": round(v)} for k, v in ordered]
