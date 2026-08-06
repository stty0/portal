"""세션 라우터 (T-06, U-IA-01·02·04).

API 경계에서 지켜야 할 것: 인증, 소유자 격리, **접속 위치를 응답에 담지 않기**.
"""

import json

import pytest

from app.models import InteractiveSession, User
from app.repositories.session import STATUS_ACTIVE
from app.services.session import SessionService
from tests.conftest import auth_headers

CONNECTION = {
    "app": "desktop", "node": "node012", "ip": "10.0.3.12", "port": 5903,
    "password": "s3cret12", "view_password": "v13w0nly", "geometry": "1280x800",
}


class FakeSsh:
    def __init__(self, connection=None):
        self.connection = connection

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return None

    def home_dir(self, user):
        return f"/home/{user}"

    def makedirs(self, user, base, relative, *, mode=0o700):
        pass

    def read_text(self, user, path, *, max_bytes=65536):
        return json.dumps(self.connection) if self.connection else None


@pytest.fixture
def fake_ssh(monkeypatch):
    ssh = FakeSsh(CONNECTION)
    monkeypatch.setattr(SessionService, "_connect", lambda self, cluster: ssh)
    return ssh


@pytest.fixture
def user(db, user_token) -> User:
    """로그인한 본인. user_token이 프로비저닝을 끝낸 뒤에 꺼낸다."""
    return db.query(User).filter(User.username == "jrpark").one()


@pytest.fixture
def other_user(db) -> User:
    """다른 사용자. FK가 걸려 있어 실제 행이 있어야 한다."""
    u = User(ad_object_guid="guid-someone-else", username="someone", display_name="타인", is_active=True)
    db.add(u)
    db.commit()
    return u


@pytest.fixture
def desktop_cluster(db, cluster):
    cluster.desktop_image_ref = "/home/portal/images/rocky9-mate-1.0.sif"
    cluster.login_node = "login01"
    cluster.ssh_account = "svc"
    db.commit()
    return cluster


def owned_session(db, cluster, guid, job_id="90001") -> InteractiveSession:
    s = InteractiveSession(
        user_guid=guid, cluster_id=cluster.id, app_type="desktop",
        slurm_job_id=job_id, status=STATUS_ACTIVE,
    )
    db.add(s)
    db.commit()
    return s


def test_create_requires_auth(client, desktop_cluster):
    assert client.post(f"/api/v1/clusters/{desktop_cluster.id}/sessions", json={}).status_code == 401


def test_create_submits_and_returns_state(
    client, desktop_cluster, user_token, fake_ssh, slurm_client
):
    slurm_client.jobs = [{"job_id": 90001, "job_state": ["PENDING"]}]
    resp = client.post(
        f"/api/v1/clusters/{desktop_cluster.id}/sessions",
        json={"cpus": 2, "memory_gb": 3, "walltime": "02:00:00", "geometry": "1280x800"},
        headers=auth_headers(user_token),
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["app"] == "desktop"
    assert body["job_id"] == "90001"
    assert body["state"] == "PENDING"


def test_create_without_an_image_is_rejected(client, db, cluster, user_token, fake_ssh):
    cluster.desktop_image_ref = None
    cluster.login_node = "login01"
    cluster.ssh_account = "svc"
    db.commit()
    resp = client.post(
        f"/api/v1/clusters/{cluster.id}/sessions", json={}, headers=auth_headers(user_token)
    )
    assert resp.status_code == 422
    assert "이미지" in resp.json()["message"]


def test_invalid_geometry_is_rejected_by_the_schema(client, desktop_cluster, user_token):
    resp = client.post(
        f"/api/v1/clusters/{desktop_cluster.id}/sessions",
        json={"geometry": "1280x800; rm -rf /"},
        headers=auth_headers(user_token),
    )
    assert resp.status_code == 422


def test_listing_hides_other_users_sessions(
    client, db, desktop_cluster, user_token, user, other_user, fake_ssh, slurm_client
):
    owned_session(db, desktop_cluster, user.ad_object_guid, job_id="1")
    owned_session(db, desktop_cluster, other_user.ad_object_guid, job_id="2")
    resp = client.get(
        f"/api/v1/clusters/{desktop_cluster.id}/sessions", headers=auth_headers(user_token)
    )
    assert [s["job_id"] for s in resp.json()] == ["1"]


def test_other_users_session_is_not_found(
    client, db, desktop_cluster, user_token, other_user, fake_ssh
):
    other = owned_session(db, desktop_cluster, other_user.ad_object_guid)
    assert client.get(f"/api/v1/sessions/{other.id}", headers=auth_headers(user_token)).status_code == 404
    assert client.delete(f"/api/v1/sessions/{other.id}", headers=auth_headers(user_token)).status_code == 404


def test_connection_response_never_exposes_the_location(
    client, db, desktop_cluster, user_token, user, fake_ssh, slurm_client
):
    """호스트·포트를 브라우저에 주면 열린 프록시로 가는 문이 열린다."""
    slurm_client.jobs = [{"job_id": 90001, "job_state": ["RUNNING"]}]
    s = owned_session(db, desktop_cluster, user.ad_object_guid)
    body = client.get(
        f"/api/v1/sessions/{s.id}/connection", headers=auth_headers(user_token)
    ).json()

    assert body["password"] == "s3cret12"
    assert body["geometry"] == "1280x800"
    assert set(body) == {"password", "geometry"}
    raw = json.dumps(body)
    assert "node012" not in raw and "10.0.3.12" not in raw and "5903" not in raw


def test_terminate_cancels_the_job(
    client, db, desktop_cluster, user_token, user, fake_ssh, slurm_client
):
    s = owned_session(db, desktop_cluster, user.ad_object_guid)
    resp = client.delete(f"/api/v1/sessions/{s.id}", headers=auth_headers(user_token))
    assert resp.status_code == 200
    assert slurm_client.cancelled == ["90001"]


def test_websocket_without_a_token_is_closed(client, db, desktop_cluster, user):
    s = owned_session(db, desktop_cluster, user.ad_object_guid)
    with pytest.raises(Exception):
        with client.websocket_connect(f"/api/v1/sessions/{s.id}/connect"):
            pass


class DeadTunnel:
    """열자마자 EOF를 주는 터널 — 세션 Job이 끝난 상태를 흉내낸다."""

    def read(self, size: int = 65536):
        return None

    def write(self, data: bytes) -> None:  # pragma: no cover - 여기까지 오면 안 된다
        raise AssertionError("끊긴 터널에 쓰면 안 된다")

    def close(self) -> None:
        pass


def test_websocket_closes_when_the_session_dies(
    client, db, desktop_cluster, user_token, user, fake_ssh, slurm_client, monkeypatch
):
    """워커의 Xvnc가 사라지면 웹소켓도 닫아야 한다.

    안 닫으면 브라우저는 멈춘 화면을 붙잡고 세션이 끝난 줄 모른다 — 프론트가
    목록으로 돌려보내는 동작이 이 신호에 걸려 있다.
    """
    slurm_client.jobs = [{"job_id": 90001, "job_state": ["RUNNING"]}]
    s = owned_session(db, desktop_cluster, user.ad_object_guid)
    monkeypatch.setattr(SessionService, "authenticate", lambda self, token: user)
    monkeypatch.setattr(SessionService, "open_stream", lambda self, sid, *, user: DeadTunnel())

    from starlette.websockets import WebSocketDisconnect

    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect(
            f"/api/v1/sessions/{s.id}/connect", subprotocols=[f"portal.token.{user_token}"]
        ) as ws:
            ws.receive_bytes()
