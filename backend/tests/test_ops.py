"""포털 운영 설정 (A-OP-01·02·03·04).

읽기 권한이 항목마다 다르다는 점, 설정 값이 비기능 요구(C-04)를 지키는지가 핵심이다.
"""

import pytest

from tests.conftest import auth_headers

API = "/api/v1"


# --- A-OP-04 설정 -----------------------------------------------------------


def test_settings_require_admin(client, user_token):
    # 로그인은 쿠키를 남긴다 — 익명 상태를 보려면 명시적으로 비워야 한다.
    client.cookies.clear()
    assert client.get(f"{API}/settings").status_code == 401
    assert client.get(f"{API}/settings", headers=auth_headers(user_token)).status_code == 403


def test_settings_are_created_with_defaults_on_first_read(client, admin_token):
    body = client.get(f"{API}/settings", headers=auth_headers(admin_token)).json()
    # "설정 없음"과 "기본값"을 구분할 이유가 없어 조회 시점에 만든다.
    assert body["poll_interval_sec"] == 30
    assert body["session_timeout_min"] == 480
    assert body["smtp_host"] is None


def test_settings_round_trip(client, admin_token):
    resp = client.put(
        f"{API}/settings",
        json={"poll_interval_sec": 10, "smtp_host": "smtp.dt-hpc.net", "smtp_port": 587},
        headers=auth_headers(admin_token),
    )
    assert resp.status_code == 200
    assert resp.json()["poll_interval_sec"] == 10
    again = client.get(f"{API}/settings", headers=auth_headers(admin_token)).json()
    assert again["smtp_host"] == "smtp.dt-hpc.net"
    assert again["session_timeout_min"] == 480  # 안 보낸 값은 유지된다


def test_poll_interval_is_bounded_by_c04(client, admin_token):
    """C-04: 실시간성 요구가 30초 이하다. 넘기면 화면이 요구를 못 지킨다."""
    resp = client.put(
        f"{API}/settings", json={"poll_interval_sec": 300}, headers=auth_headers(admin_token)
    )
    assert resp.status_code == 422


def test_setting_change_is_audited_without_values(client, admin_token):
    """SMTP 호스트·웹훅 URL이 감사 로그로 새면 안 된다 — 필드 이름만 남긴다."""
    client.put(
        f"{API}/settings",
        json={"webhook_url": "https://hooks.example.com/secret-path"},
        headers=auth_headers(admin_token),
    )
    logs = client.get(
        f"{API}/audit-logs?action=SETTING_UPDATE", headers=auth_headers(admin_token)
    ).json()
    assert logs["total"] == 1
    entry = logs["items"][0]
    assert entry["target"] == "webhook_url"
    assert "secret-path" not in str(entry)


def test_unchanged_settings_are_not_audited(client, admin_token):
    client.get(f"{API}/settings", headers=auth_headers(admin_token))
    client.put(f"{API}/settings", json={"poll_interval_sec": 30}, headers=auth_headers(admin_token))
    logs = client.get(
        f"{API}/audit-logs?action=SETTING_UPDATE", headers=auth_headers(admin_token)
    ).json()
    assert logs["total"] == 0


# --- A-OP-01 공지 -----------------------------------------------------------


def test_notice_crud(client, admin_token):
    created = client.post(
        f"{API}/notices",
        json={"title": "정기 점검", "body": "토요일 02:00~04:00", "banner_enabled": True},
        headers=auth_headers(admin_token),
    )
    assert created.status_code == 201
    nid = created.json()["id"]

    client.patch(f"{API}/notices/{nid}", json={"title": "점검 연기"}, headers=auth_headers(admin_token))
    assert client.get(f"{API}/notices", headers=auth_headers(admin_token)).json()[0]["title"] == "점검 연기"

    assert client.delete(f"{API}/notices/{nid}", headers=auth_headers(admin_token)).status_code == 200
    assert client.get(f"{API}/notices", headers=auth_headers(admin_token)).json() == []


def test_notices_are_readable_by_users_but_writable_by_admin(client, user_token):
    # 배너(U-CL-03)를 일반 사용자가 봐야 하므로 읽기는 열려 있다.
    assert client.get(f"{API}/notices", headers=auth_headers(user_token)).status_code == 200
    assert client.post(
        f"{API}/notices", json={"title": "x"}, headers=auth_headers(user_token)
    ).status_code == 403


def test_cluster_notice_includes_global_ones(client, admin_token, cluster):
    """전체 공지가 클러스터를 고른 사용자에게 안 보이면 공지의 의미가 없다."""
    client.post(f"{API}/notices", json={"title": "전체"}, headers=auth_headers(admin_token))
    client.post(
        f"{API}/notices",
        json={"title": "이 클러스터", "target_cluster_id": cluster.id},
        headers=auth_headers(admin_token),
    )
    titles = [
        n["title"]
        for n in client.get(
            f"{API}/notices?cluster_id={cluster.id}", headers=auth_headers(admin_token)
        ).json()
    ]
    assert set(titles) == {"전체", "이 클러스터"}


def test_banner_filter_respects_period(client, admin_token):
    client.post(
        f"{API}/notices",
        json={"title": "지난 공지", "banner_enabled": True, "end_at": "2020-01-01T00:00:00"},
        headers=auth_headers(admin_token),
    )
    client.post(
        f"{API}/notices", json={"title": "상시", "banner_enabled": True}, headers=auth_headers(admin_token)
    )
    client.post(f"{API}/notices", json={"title": "배너 아님"}, headers=auth_headers(admin_token))
    titles = [
        n["title"]
        for n in client.get(f"{API}/notices?banner=true", headers=auth_headers(admin_token)).json()
    ]
    assert titles == ["상시"]


def test_reversed_period_is_rejected(client, admin_token):
    resp = client.post(
        f"{API}/notices",
        json={"title": "x", "start_at": "2026-08-10T00:00:00", "end_at": "2026-08-01T00:00:00"},
        headers=auth_headers(admin_token),
    )
    assert resp.status_code == 422


# --- A-OP-03 감사 로그 -------------------------------------------------------


def test_audit_log_requires_admin(client, user_token):
    assert client.get(f"{API}/audit-logs", headers=auth_headers(user_token)).status_code == 403


def test_audit_log_resolves_actor_name(client, admin_token):
    client.post(f"{API}/notices", json={"title": "감사 확인"}, headers=auth_headers(admin_token))
    entry = client.get(
        f"{API}/audit-logs?action=NOTICE_CREATE", headers=auth_headers(admin_token)
    ).json()["items"][0]
    # GUID는 화면에서 쓸모가 없다.
    assert entry["actor"] and "-" not in str(entry["actor"])[:8]
    assert entry["target"] == "감사 확인"


def test_unknown_actor_filter_returns_nothing(client, admin_token):
    """없는 사용자로 걸렀는데 전체가 나오면 필터가 무시된 것이다."""
    client.post(f"{API}/notices", json={"title": "x"}, headers=auth_headers(admin_token))
    body = client.get(
        f"{API}/audit-logs?actor_username=nobody", headers=auth_headers(admin_token)
    ).json()
    assert body["total"] == 0 and body["items"] == []


def test_audit_actions_come_from_recorded_data(client, admin_token):
    client.post(f"{API}/notices", json={"title": "x"}, headers=auth_headers(admin_token))
    actions = client.get(f"{API}/audit-logs/actions", headers=auth_headers(admin_token)).json()
    assert "NOTICE_CREATE" in actions


def test_audit_log_pagination(client, admin_token):
    for i in range(5):
        client.post(f"{API}/notices", json={"title": f"n{i}"}, headers=auth_headers(admin_token))
    body = client.get(
        f"{API}/audit-logs?action=NOTICE_CREATE&size=2&page=2", headers=auth_headers(admin_token)
    ).json()
    assert body["total"] == 5
    assert len(body["items"]) == 2
    assert body["page"] == 2
