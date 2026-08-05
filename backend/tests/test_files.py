"""파일 브라우저·스토리지 테스트 (U-FM-01, A-DB-05).

핵심은 **대상 사용자를 클라이언트가 정할 수 없다**는 점이다.
"""

import pytest

from app.clients.ssh.client import FileEntry
from app.services.files import FileService
from tests.conftest import auth_headers


class FakeSsh:
    """LoginNodeClient 대역 — 어떤 사용자로 조회했는지 기록한다."""

    def __init__(self):
        self.as_users: list[str] = []
        self.existing: set[str] = set()

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return None

    def home_dir(self, user):
        self.as_users.append(user)
        return f"/home/{user}"

    def exists(self, user, path):
        return path in self.existing

    def list_dir(self, user, path, *, allowed_roots=None):
        self.as_users.append(user)
        if allowed_roots is not None and not any(
            path == r or path.startswith(r.rstrip("/") + "/") for r in allowed_roots
        ):
            from app.core.errors import Forbidden

            raise Forbidden("허용된 디렉터리 밖입니다.", detail={"path": path})
        return path, [
            FileEntry("data", True, 4096, 1, "drwxr-xr-x", 201106, 200513),
            FileEntry("run.sh", False, 120, 2, "-rw-r--r--", 201106, 200513),
        ]

    def filesystems(self, user):
        self.as_users.append(user)
        return [
            {"filesystem": "tmpfs", "mount": "/run", "used_pct": 0.3},
            {"filesystem": "/dev/sda1", "mount": "/", "used_pct": 21.8},
            {"filesystem": "nfs:/vol", "mount": "/home", "used_pct": 12.0},
        ]

    def quota(self, user):
        return []


@pytest.fixture
def fake_ssh(monkeypatch):
    ssh = FakeSsh()
    monkeypatch.setattr(FileService, "_connect", lambda self, cid: ssh)
    return ssh


def test_browse_uses_session_user_not_client_input(client, cluster, user_token, fake_ssh):
    resp = client.get(
        f"/api/v1/clusters/{cluster.id}/files",
        params={"username": "root"},  # 사용자 지정 시도는 무시돼야 한다
        headers=auth_headers(user_token),
    )
    assert resp.status_code == 200
    # username 쿼리는 무시되고 세션 사용자로만 조회된다
    assert set(fake_ssh.as_users) == {"jrpark"}
    assert [e["name"] for e in resp.json()["entries"]] == ["data", "run.sh"]


def test_browse_defaults_to_home(client, cluster, user_token, fake_ssh):
    resp = client.get(
        f"/api/v1/clusters/{cluster.id}/files", headers=auth_headers(user_token)
    )
    body = resp.json()
    assert body["home"] == "/home/jrpark"
    assert body["path"] == "/home/jrpark"


def test_storage_requires_auth(client, cluster):
    assert client.get(f"/api/v1/clusters/{cluster.id}/storage").status_code == 401


def test_missing_login_node_is_rejected_before_connecting(client, db, cluster, user_token):
    cluster.login_node = None
    db.commit()
    resp = client.get(f"/api/v1/clusters/{cluster.id}/files", headers=auth_headers(user_token))
    assert resp.status_code == 422
    assert "로그인 노드" in resp.json()["message"]


def test_cannot_browse_above_home(client, cluster, user_token, fake_ssh):
    """홈 위로는 못 나간다 — /home 목록은 다른 사용자 계정명을 그대로 드러낸다."""
    resp = client.get(
        f"/api/v1/clusters/{cluster.id}/files",
        params={"path": "/home"},
        headers=auth_headers(user_token),
    )
    assert resp.status_code == 403


def test_missing_shortcut_is_reported_not_hidden(client, db, cluster, user_token, fake_ssh):
    """미구축 스크래치/그룹은 '없음'으로 알린다 — 눌러서 실패하게 두지 않는다."""
    cluster.scratch_path_tpl = "/scratch/{user}"
    db.commit()
    resp = client.get(
        f"/api/v1/clusters/{cluster.id}/files", headers=auth_headers(user_token)
    )
    shortcuts = {s["label"]: s["exists"] for s in resp.json()["shortcuts"]}
    assert shortcuts["홈"] is True
    assert shortcuts["스크래치"] is False


def test_storage_shows_only_user_paths(client, db, cluster, user_token, fake_ssh):
    """tmpfs·/ 같은 무관한 마운트는 빼고 홈·스크래치·그룹만 보여준다."""
    cluster.scratch_path_tpl = "/scratch/{user}"
    db.commit()
    body = client.get(
        f"/api/v1/clusters/{cluster.id}/storage", headers=auth_headers(user_token)
    ).json()
    rows = {t["label"]: t for t in body["targets"]}
    assert set(rows) == {"홈", "스크래치"}
    # 홈은 자신을 담고 있는 마운트(/home)로 매칭된다 — / 가 아니라
    assert rows["홈"]["mount"] == "/home"
    assert rows["홈"]["used_pct"] == 12.0
    assert rows["스크래치"]["exists"] is False
    assert "mount" not in rows["스크래치"]
