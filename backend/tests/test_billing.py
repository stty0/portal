"""비용/Billing 테스트 (A-BL-01·02·03).

핵심은 **키 값이 응답에 절대 실리지 않는다**는 점이다.
"""

import pytest

from datetime import date, timedelta

from app.services.billing import SCP_ACCESS_KEY_REF, SCP_SECRET_KEY_REF, BillingService
from tests.conftest import auth_headers

# 조회 구간은 `오늘 − N일`이라 **고정 날짜를 쓰면 언젠가 구간 밖으로 밀려난다.**
# 오늘 기준 상대 날짜로 둬야 시간이 지나도 같은 것을 검증한다.
PAID_DAY = str(date.today() - timedelta(days=2))
FREE_DAY = str(date.today() - timedelta(days=1))

USAGES = [
    {"usage_date": f"{PAID_DAY}T00:00:00", "service_category": "COMPUTE",
     "billing_item_id": "VM", "amounts": {"krw": "1000.5"}, "account_id": "acct-1"},
    {"usage_date": f"{PAID_DAY}T00:00:00", "service_category": "STORAGE",
     "billing_item_id": "BLOCK_STORAGE", "amounts": {"krw": "500"}, "account_id": "acct-1"},
    {"usage_date": f"{FREE_DAY}T00:00:00", "service_category": "COMPUTE",
     "billing_item_id": "VM", "amounts": {"krw": None}, "account_id": "acct-1"},
]


@pytest.fixture
def scp(monkeypatch, secret_store):
    secret_store.put(SCP_ACCESS_KEY_REF, "ak")
    secret_store.put(SCP_SECRET_KEY_REF, "sk")

    class FakeClient:
        def usages(self, *, start_date, end_date, max_pages=20):
            return USAGES

    monkeypatch.setattr(BillingService, "_client", lambda self: FakeClient())


def test_config_never_exposes_keys(client, admin_token, scp):
    body = client.get("/api/v1/billing/config", headers=auth_headers(admin_token)).json()
    assert body["configured"] is True
    assert "ak" not in str(body) and "sk" not in str(body)
    assert not any("key" in k and k != "access_key_configured" for k in body if "secret" in k)


def test_config_reports_unconfigured_without_secret(client, admin_token):
    body = client.get("/api/v1/billing/config", headers=auth_headers(admin_token)).json()
    assert body["configured"] is False


def test_trend_aggregates_by_day_and_category(client, admin_token, scp):
    body = client.get("/api/v1/billing/trend", headers=auth_headers(admin_token)).json()
    # 1000.5 + 500 + (null→0) = 1500.5 → 파이썬 round는 짝수로 내림(1500)
    assert body["total_krw"] == 1500
    # 구간의 모든 날짜가 채워진다 — 청구가 없던 날은 0이다.
    # 데이터 있는 날만 주면 "30일"을 골랐는데 차트 가로축이 9칸만 그려진다.
    days = {d["date"]: d["krw"] for d in body["daily"]}
    assert len(body["daily"]) == 31  # start~end 포함
    assert body["daily"][0]["date"] == body["start"]
    assert body["daily"][-1]["date"] == body["end"]
    assert days[PAID_DAY] == 1500
    assert days[FREE_DAY] == 0
    assert sum(days.values()) == 1500  # 나머지 날은 전부 0
    assert body["by_category"][0] == {"label": "COMPUTE", "krw": 1000}
    assert body["record_count"] == 3


def test_trend_requires_admin(client, user_token, scp):
    assert client.get("/api/v1/billing/trend", headers=auth_headers(user_token)).status_code == 403


def test_trend_without_credentials_is_rejected(client, admin_token):
    resp = client.get("/api/v1/billing/trend", headers=auth_headers(admin_token))
    assert resp.status_code == 422
    assert "SCP 자격증명" in resp.json()["message"]


def test_rule_crud(client, admin_token):
    created = client.post(
        "/api/v1/billing/rules",
        json={"kind": "resource_id", "condition": "4d4c747e", "mapping_label": "slurm-cluster-1"},
        headers=auth_headers(admin_token),
    )
    assert created.status_code == 201
    rid = created.json()["id"]
    rules = client.get("/api/v1/billing/rules", headers=auth_headers(admin_token)).json()
    assert [r["mapping_label"] for r in rules] == ["slurm-cluster-1"]
    assert client.delete(f"/api/v1/billing/rules/{rid}", headers=auth_headers(admin_token)).status_code == 200
    assert client.get("/api/v1/billing/rules", headers=auth_headers(admin_token)).json() == []


def test_account_id_comes_from_api_not_manual_input(client, db, admin_token, scp):
    """seed/손 입력 값이 남아 있어도 응답에서 확인된 계정 ID로 정정된다."""
    from app.models import BillingConfig

    db.add(BillingConfig(scp_account_id="REPLACE_ME", api_endpoint="https://old.example"))
    db.commit()
    client.get("/api/v1/billing/trend", headers=auth_headers(admin_token))
    body = client.get("/api/v1/billing/config", headers=auth_headers(admin_token)).json()
    assert body["scp_account_id"] == "acct-1"
    assert "costexplorer" in body["api_endpoint"]


def test_trend_filters_by_tag(client, admin_token, monkeypatch, secret_store):
    """비용 응답에는 태그가 없다 — 태그 API로 자원 ID를 받아 걸러낸다."""
    secret_store.put(SCP_ACCESS_KEY_REF, "ak")
    secret_store.put(SCP_SECRET_KEY_REF, "sk")

    class FakeClient:
        def usages(self, *, start_date, end_date, max_pages=20):
            return [
                {"usage_date": "2026-08-01T00:00:00", "service_category": "COMPUTE",
                 "billing_item_id": "VM", "amounts": {"krw": "1000"},
                 "resource_id": "54fca0ceed3045949409", "account_id": "acct-1"},
                {"usage_date": "2026-08-01T00:00:00", "service_category": "STORAGE",
                 "billing_item_id": "BS", "amounts": {"krw": "500"},
                 "resource_id": "otherresource", "account_id": "acct-1"},
            ]

        def tagged_resource_ids(self, *, key, value=None):
            assert (key, value) == ("purpose", "hpc")
            # SRN 쪽은 하이픈이 있고 비용 쪽은 없다 — 정규화 후 매칭돼야 한다
            return {"54fca0ceed3045949409"}

    monkeypatch.setattr(BillingService, "_client", lambda self: FakeClient())
    body = client.get(
        "/api/v1/billing/trend?tag=purpose%3Dhpc", headers=auth_headers(admin_token)
    ).json()
    assert body["record_count"] == 1
    assert body["total_krw"] == 1000
    assert body["tag"] == "purpose=hpc"
    assert body["tagged_resource_count"] == 1


def test_put_config_validates_before_saving(client, admin_token, monkeypatch, secret_store):
    """검증에 실패하면 키를 저장하지 않는다 — '설정됨'인데 조회만 실패하는 상태를 막는다."""
    from app.clients.scp import client as scp_client
    from app.core.errors import ExternalServiceError

    class Bad:
        def __init__(self, creds): ...
        def usages(self, **kw):
            raise ExternalServiceError("SCP 비용 조회 실패: 403")

    monkeypatch.setattr("app.services.billing.ScpBillingClient", Bad)
    resp = client.put(
        "/api/v1/billing/config",
        json={"access_key": "bad-access-key", "secret_key": "bad-secret-key"},
        headers=auth_headers(admin_token),
    )
    assert resp.status_code == 502
    assert client.get("/api/v1/billing/config", headers=auth_headers(admin_token)).json()[
        "configured"
    ] is False


def test_put_config_saves_and_never_echoes_keys(client, admin_token, monkeypatch):
    class Good:
        def __init__(self, creds): ...
        def usages(self, **kw):
            return [{"account_id": "acct-9", "amounts": {"krw": "1"}}]

    monkeypatch.setattr("app.services.billing.ScpBillingClient", Good)
    resp = client.put(
        "/api/v1/billing/config",
        json={"access_key": "real-access-key", "secret_key": "real-secret-key",
              "monthly_alert_krw": 1000000},
        headers=auth_headers(admin_token),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["configured"] is True
    assert body["scp_account_id"] == "acct-9"
    assert body["monthly_alert_krw"] == 1000000
    # 어떤 경로로도 키가 응답에 실리면 안 된다
    assert "real-secret-key" not in str(body) and "real-access-key" not in str(body)


def test_put_config_requires_admin(client, user_token):
    assert client.put(
        "/api/v1/billing/config",
        json={"access_key": "aaaaaaaa", "secret_key": "bbbbbbbb"},
        headers=auth_headers(user_token),
    ).status_code == 403
