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
# 있는 곳은 **클러스터**(`home_base`에서 파생), 어떤 파일인지는 앱 카탈로그가 정한다.


def _resolve(db, settings, app_id, image_dir="/home/.portal/images", home_base=None):
    from app.models import Cluster
    from app.services import app_images

    object.__setattr__(settings, "app_image_dir", image_dir)
    return app_images.resolve(
        db, settings, Cluster(home_base=home_base), app_images.KIND_INTERACTIVE, app_id
    )


def test_image_is_resolved_from_the_cluster_home_and_the_app(db, settings):
    """클러스터가 홈 상위를 갖고 있으면 그 아래 `.portal/images`에서 찾는다."""
    assert _resolve(db, settings, "desktop", home_base="/nfs/home") == (
        f"/nfs/home/.portal/images/{session_apps.get('desktop').image}"
    )


def test_image_dir_differs_per_cluster(db, settings):
    """같은 앱이라도 클러스터가 다르면 다른 NFS를 본다 — 이 에픽의 이유다."""
    a = _resolve(db, settings, "desktop", home_base="/nfs/a")
    b = _resolve(db, settings, "desktop", home_base="/nfs/b")
    assert a.startswith("/nfs/a/.portal/") and b.startswith("/nfs/b/.portal/")


def test_image_dir_falls_back_to_the_portal_setting_when_home_base_is_empty(db, settings):
    """`home_base`가 비면 사용자별 자동 인식 모드라 공용 자리가 없다 — 폴백이 필요하다."""
    assert _resolve(db, settings, "desktop") == (
        f"/home/.portal/images/{session_apps.get('desktop').image}"
    )


def test_image_dir_trailing_slash_does_not_double_up(db, settings):
    """`/images/` + 파일명이 `/images//파일`이 되면 apptainer가 못 연다."""
    assert "//" not in _resolve(db, settings, "desktop", "/home/.portal/images/")
    assert "//" not in _resolve(db, settings, "desktop", home_base="/nfs/home/")


def test_registered_image_file_wins_over_the_code_default(db, settings):
    """앱 관리에서 이미지를 바꾸면 코드 배포 없이 그 파일이 쓰인다."""
    from app.models import AppCatalog

    db.add(AppCatalog(kind="interactive", app_id="desktop", name="d", image_file="custom.sif"))
    db.commit()
    assert _resolve(db, settings, "desktop") == "/home/.portal/images/custom.sif"


def test_registered_image_file_with_a_path_is_rejected(db, settings):
    """파일명만 받는다 — 경로가 섞이면 공용 디렉터리 밖을 가리킬 수 있다."""
    from app.models import AppCatalog

    db.add(AppCatalog(kind="interactive", app_id="desktop", name="d", image_file="../x.sif"))
    db.commit()
    with pytest.raises(ValidationFailed):
        _resolve(db, settings, "desktop")


def test_unknown_app_is_rejected(db, settings):
    """모르는 앱으로 Job을 던지면 워커에서 죽는다 — 제출 전에 막는다."""
    with pytest.raises(ValidationFailed):
        _resolve(db, settings, "nope")


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
    assert f"/home/.portal/images/{session_apps.get('paraview').image}" in script


def test_each_app_resolves_to_its_own_image(db, settings, monkeypatch):
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
    assert _resolve(db, settings, "desktop", "/images") == "/images/mate.sif"
    assert _resolve(db, settings, "paraview", "/images") == "/images/paraview.sif"


def test_app_catalog_is_listed_for_the_launcher(client, desktop_cluster, user_token):
    body = client.get(
        f"/api/v1/clusters/{desktop_cluster.id}/interactive-apps",
        headers=auth_headers(user_token),
    ).json()
    assert {a["id"] for a in body} == {"desktop", "paraview", "jupyter", "code-server"}
    # JupyterLab은 2026-08-08부터 실행된다(HTTP 프록시 경로).
    assert {a["id"] for a in body if a["ready"]} == {"desktop", "paraview", "jupyter"}
    # code-server는 **포털이 호스팅하지 않는다** — 하위 경로 서비스가 불가능해서
    # Remote-SSH를 안내한다. 안내 문구가 없으면 "준비 중" 카드만 남아 물어볼 데가 없다.
    guide = next(a for a in body if a["id"] == "code-server")
    assert guide["ready"] is False and "Remote - SSH" in guide["note"]
    # 이미지는 운영 정보다 — 사용자에게 내려보내지 않는다.
    assert all("image" not in a for a in body)


def test_app_catalog_requires_auth(client, desktop_cluster):
    url = f"/api/v1/clusters/{desktop_cluster.id}/interactive-apps"
    assert client.get(url).status_code == 401


def test_planned_apps_cannot_be_launched(client, desktop_cluster, user_token, fake_ssh):
    """예정된 앱은 이미지가 없다 — 제출되면 워커에서 죽으므로 여기서 막는다."""
    resp = client.post(
        f"/api/v1/clusters/{desktop_cluster.id}/sessions",
        json={"app": "code-server"},
        headers=auth_headers(user_token),
    )
    assert resp.status_code == 422


def test_http_apps_start_a_different_container_entry(client, desktop_cluster, user_token, fake_ssh, slurm_client):
    """JupyterLab은 X 서버가 없다 — VNC 기동 스크립트를 부르면 Xvnc부터 띄운다."""
    resp = client.post(
        f"/api/v1/clusters/{desktop_cluster.id}/sessions",
        json={"app": "jupyter"},
        headers=auth_headers(user_token),
    )
    assert resp.status_code == 201, resp.text
    script = [kw["spec"] for n, kw in slurm_client.calls if n == "submit_job"][0]["script"]
    assert "/opt/portal/start-jupyter.sh" in script
    assert "start-desktop.sh" not in script


def test_create_without_an_image_file_is_rejected(client, db, cluster, user_token, fake_ssh, monkeypatch):
    """코드 기본값도 등록도 없으면 제출을 막는다 — 워커까지 가서 죽으면 원인이 안 보인다."""
    from app.services import session_apps as sa

    monkeypatch.setattr(
        sa, "APPS", (sa.InteractiveApp("desktop", "데스크톱", "", "", "U-IA-02"),)
    )
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


# --- HTTP 앱 리버스 프록시 (U-IA-01) ---------------------------------------
# 경로가 컨테이너의 base_url과 **글자 하나까지** 같아야 한다. 어긋나면 Jupyter가 HTML에
# 박아 넣은 링크가 포털 SPA로 떨어지고, 화면은 흰 페이지가 된다.


def test_proxy_path_matches_the_container_base_url():
    """`start-jupyter.sh`가 쓰는 접두사와 라우터 경로가 같아야 한다."""
    import pathlib
    import re

    from app.routers.session_apps import router

    script = (
        pathlib.Path(__file__).resolve().parents[2]
        / "deploy/images/rocky9-mate/start-jupyter.sh"
    ).read_text(encoding="utf-8")
    found = re.search(r'BASE_URL="([^"]+)"', script)
    assert found, "start-jupyter.sh에서 BASE_URL을 찾지 못했다"
    # 스크립트: /api/v1/session-apps/$JOB_ID/  · 라우터: /session-apps/{job_id}/{path}
    assert found.group(1).startswith("/api/v1/session-apps/")
    assert any("/session-apps/{job_id}/{path:path}" in r.path for r in router.routes)


def test_proxy_rejects_anonymous_requests(client):
    """프록시도 포털 인증을 지난다 — 세션 앱이 인증 우회로가 되면 안 된다."""
    assert client.get("/api/v1/session-apps/12345/lab").status_code == 401


def test_proxy_hides_other_peoples_sessions(client, user_token):
    """남의 Job ID를 넣어도 **없는 것으로 답한다**(세션 조회와 같은 규칙)."""
    resp = client.get(
        "/api/v1/session-apps/999999/lab", headers=auth_headers(user_token)
    )
    assert resp.status_code == 404


def test_proxy_reuses_the_resolved_target(client, user_token, monkeypatch):
    """요청마다 DB+SSH를 다시 타면 한 페이지에 수십 번이다.

    실측(2026-08-08): 캐시가 없을 때 JupyterLab 한 페이지가 커넥션 풀을 말려
    `QueuePool limit of size 5 overflow 10 reached`가 났고 화면 전체가 느려졌다.
    """
    from app.services import session_proxy

    session_proxy.TARGETS.clear()
    calls: list[str] = []
    original = session_proxy.SessionProxyService.target

    def counted(self, job_id, *, user):
        calls.append(job_id)
        return original(self, job_id, user=user)

    monkeypatch.setattr(session_proxy.SessionProxyService, "target", counted)
    for _ in range(3):
        client.get("/api/v1/session-apps/999999/lab", headers=auth_headers(user_token))
    # 세션이 없어 캐시에 담기지 않는 경우다 — **인증은 매번 지나야 한다**는 것만 확인한다.
    assert len(calls) == 3

    # 담긴 뒤에는 느린 길을 타지 않는다.
    target = session_proxy.AppTarget(
        session_id=1, cluster_id=1, local_port=1, token="t", base_url="/b/"
    )
    from app.core.security import decode_session_token
    from app.core.config import get_settings

    session_proxy.TARGETS.put("999999", "guid-does-not-match", target)
    assert session_proxy.TARGETS.get("999999", "guid-does-not-match") is target
    # **소유자가 키에 들어 있다** — 남의 캐시를 타지 못한다.
    assert session_proxy.TARGETS.get("999999", "other-guid") is None


def test_starting_session_is_a_wait_not_an_error(client, db, desktop_cluster, user_token, fake_ssh, slurm_client):
    """Slurm의 RUNNING과 "붙을 수 있다"는 같지 않다.

    Job이 시작된 뒤 컨테이너가 connection.json을 쓰기까지 10~20초가 더 걸린다(실측).
    그 사이를 오류로 던지면 사용자는 세션이 깨진 줄 알고 다시 만든다 — 화면이 "기다릴 일"과
    "실패"를 구분할 수 있게 표식을 붙인다.
    """
    fake_ssh.connection = None  # 아직 안 쓰인 상태
    resp = client.post(
        f"/api/v1/clusters/{desktop_cluster.id}/sessions",
        json={"app": "desktop"},
        headers=auth_headers(user_token),
    )
    sid = resp.json()["id"]
    info = client.get(f"/api/v1/sessions/{sid}/connection", headers=auth_headers(user_token))
    assert info.status_code == 422
    assert info.json()["detail"]["reason"] == "starting"


def _ws_close_code(client, path, **kw) -> int:
    """웹소켓이 **어떤 코드로** 닫혔는지. 그냥 예외만 보면 아무 이유로 실패해도 통과한다."""
    from starlette.websockets import WebSocketDisconnect

    try:
        with client.websocket_connect(path, **kw) as ws:
            ws.receive()
    except WebSocketDisconnect as exc:
        return exc.code
    raise AssertionError("닫히지 않았다")


def test_proxy_websocket_rejects_anonymous(client):
    """커널 채널도 포털 인증을 지난다 — HTTP만 막으면 우회로가 남는다."""
    assert _ws_close_code(client, "/api/v1/session-apps/12345/api/kernels") == 4401


def test_proxy_websocket_hides_other_peoples_sessions(client, user_token):
    """남의 Job ID로 커널 채널을 열 수 없다(HTTP 프록시와 같은 규칙).

    **이 테스트가 없어서 `proxy_ws`가 검증 밖에 있었다.** 설정을 주입받지 않아 테스트의
    JWT 비밀키가 안 먹었고, 인증이 통째로 실패해 경로를 덮을 수 없었다. 4401(인증 없음)이
    아니라 **4400**이 나와야 "인증은 지났고 대상이 없다"는 뜻이다.
    """
    code = _ws_close_code(
        client, "/api/v1/session-apps/999999/api/kernels", headers=auth_headers(user_token)
    )
    assert code == 4400


def test_proxy_websocket_uses_injected_settings(client):
    """설정 주입이 풀리면 이 경로만 조용히 검증에서 빠진다 — 서명으로 못 박는다."""
    import inspect

    from app.routers.session_apps import proxy_ws

    assert "settings" in inspect.signature(proxy_ws).parameters
