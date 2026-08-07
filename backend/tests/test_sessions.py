"""세션 라우터 (T-06, U-IA-01·02·04).

API 경계에서 지켜야 할 것: 인증, 소유자 격리, **접속 위치를 응답에 담지 않기**.
"""

import json

import pytest

from app.models import InteractiveSession, User
from app.repositories.session import STATUS_ACTIVE
from app.core.errors import ValidationFailed
from app.services import session_apps
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
    cluster.image_repository = "/home/portal/images"
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


# --- 앱 → 이미지 (U-IA-01) --------------------------------------------------
# 클러스터는 이미지가 **있는 곳**만 갖고, 어떤 이미지인지는 앱 카탈로그가 정한다.


def test_image_is_resolved_from_the_repository_and_the_app():
    ref = session_apps.image_ref("/home/portal/images", "desktop")
    assert ref == f"/home/portal/images/{session_apps.get('desktop').image}"


def test_repository_trailing_slash_does_not_double_up():
    """`/images/` + 파일명이 `/images//파일`이 되면 레지스트리 참조에서 깨진다."""
    assert "//" not in session_apps.image_ref("/home/portal/images/", "desktop")


def test_registry_repositories_are_joined_the_same_way():
    ref = session_apps.image_ref("docker://reg.example.com/hpc", "desktop")
    assert ref == f"docker://reg.example.com/hpc/{session_apps.get('desktop').image}"


def test_unknown_app_is_rejected():
    """모르는 앱으로 Job을 던지면 워커에서 죽는다 — 제출 전에 막는다."""
    with pytest.raises(ValidationFailed):
        session_apps.image_ref("/home/portal/images", "nope")


def test_submitted_script_uses_the_resolved_image(
    client, desktop_cluster, user_token, fake_ssh, slurm_client
):
    """저장소 + 앱이 실제로 제출되는 스크립트까지 이어지는지 확인한다."""
    client.post(
        f"/api/v1/clusters/{desktop_cluster.id}/sessions",
        json={"app": "paraview"},
        headers=auth_headers(user_token),
    )
    spec = [kw["spec"] for name, kw in slurm_client.calls if name == "submit_job"][0]
    script = json.dumps(spec, ensure_ascii=False)
    assert f"/home/portal/images/{session_apps.get('paraview').image}" in script


def test_each_app_resolves_to_its_own_image(monkeypatch):
    """앱마다 이미지가 갈리는지 확인한다.

    지금은 두 앱이 **같은 이미지**를 쓰므로(하나의 Rocky 9 이미지에 MATE·ParaView가
    함께 들어 있다), 실제 카탈로그로는 '앱을 무시하는 구현'과 구분되지 않는다.
    앱을 나눌 때를 위한 구조가 살아 있는지 여기서 고정한다.
    """
    split = (
        session_apps.InteractiveApp("desktop", "데스크톱", "", "mate.sif", "U-IA-02"),
        session_apps.InteractiveApp("paraview", "ParaView", "", "paraview.sif", "U-IA-02"),
    )
    monkeypatch.setattr(session_apps, "APPS", split)
    assert session_apps.image_ref("/images", "desktop") == "/images/mate.sif"
    assert session_apps.image_ref("/images", "paraview") == "/images/paraview.sif"


def test_app_catalog_is_listed_for_the_launcher(client, user_token):
    body = client.get("/api/v1/interactive-apps", headers=auth_headers(user_token)).json()
    assert {a["id"] for a in body} == {"desktop", "paraview", "jupyter", "code-server"}
    assert {a["id"] for a in body if a["ready"]} == {"desktop", "paraview"}
    # 이미지는 운영 정보다 — 사용자에게 내려보내지 않는다.
    assert all("image" not in a for a in body)


def test_app_catalog_requires_auth(client):
    assert client.get("/api/v1/interactive-apps").status_code == 401


def test_planned_apps_cannot_be_launched(client, desktop_cluster, user_token, fake_ssh):
    """예정된 앱은 이미지가 없다 — 제출되면 워커에서 죽으므로 여기서 막는다."""
    resp = client.post(
        f"/api/v1/clusters/{desktop_cluster.id}/sessions",
        json={"app": "jupyter"},
        headers=auth_headers(user_token),
    )
    assert resp.status_code == 422


def test_create_without_an_image_repository_is_rejected(client, db, cluster, user_token, fake_ssh):
    cluster.image_repository = None
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
