"""파일 브라우저·스토리지 테스트 (U-FM-01, A-DB-05).

핵심은 **대상 사용자를 클라이언트가 정할 수 없다**는 점이다.
"""

import pytest

from app.clients.ssh.client import FileEntry
from app.services.files import FileService
from tests.conftest import auth_headers


def _guard(path: str, roots):
    """실제 클라이언트의 경로 관문을 흉내낸다 — 정규화 뒤에 루트를 확인한다."""
    import posixpath

    from app.core.errors import Forbidden

    resolved = posixpath.normpath(path)
    if roots is not None and not any(
        resolved == r or resolved.startswith(r.rstrip("/") + "/") for r in roots
    ):
        raise Forbidden("허용된 디렉터리 밖입니다.", detail={"path": resolved})
    return resolved


class FakeSsh:
    """LoginNodeClient 대역 — 어떤 사용자로 조회했는지 기록한다."""

    def __init__(self):
        self.as_users: list[str] = []
        self.existing: set[str] = set()
        self.ops: list[tuple] = []

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return None

    def home_dir(self, user):
        self.as_users.append(user)
        return f"/home/{user}"

    def exists(self, user, path):
        return path in self.existing

    # --- 조작 (경로 관문은 실제 구현과 같은 규칙으로 흉내낸다) ---
    def make_dir(self, user, path, *, allowed_roots=None):
        self.as_users.append(user)
        target = _guard(path, allowed_roots)
        self.ops.append(("mkdir", target))
        return target

    def create_file(self, user, path, *, allowed_roots=None):
        self.as_users.append(user)
        target = _guard(path, allowed_roots)
        self.ops.append(("touch", target))
        return target

    def move(self, user, src, dst, *, allowed_roots=None):
        self.as_users.append(user)
        source, target = _guard(src, allowed_roots), _guard(dst, allowed_roots)
        self.ops.append(("move", source, target))
        return source, target

    def remove(self, user, path, *, allowed_roots=None, recursive=False):
        self.as_users.append(user)
        target = _guard(path, allowed_roots)
        self.ops.append(("remove", target, recursive))
        return target

    def upload(self, user, path, source, *, allowed_roots=None, max_bytes=None):
        self.as_users.append(user)
        target = _guard(path, allowed_roots)
        data = source.read()
        self.ops.append(("upload", target, len(data)))
        return target, len(data)

    def open_read(self, user, path, *, allowed_roots=None):
        self.as_users.append(user)
        target = _guard(path, allowed_roots)
        self.ops.append(("download", target))
        return target, 5, iter([b"hello"])

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


def test_browsing_is_limited_to_the_home_root(client, cluster, user_token, fake_ssh):
    """허용 루트는 홈 하나다 — 조회와 변경이 같은 범위를 쓴다는 계약의 뿌리."""
    body = client.get(
        f"/api/v1/clusters/{cluster.id}/files", headers=auth_headers(user_token)
    ).json()
    assert body["roots"] == [body["home"]]


# 아래 세 테스트는 **NSS가 돌려주는 값과 다른** 상위 경로를 일부러 쓴다.
# `/home`을 쓰면 대역의 `home_dir()`이 같은 값을 주므로, 설정을 무시하는 구현에서도
# 통과해 아무것도 증명하지 못한다.


def test_configured_home_base_is_used_with_the_session_username(
    client, db, cluster, user_token, fake_ssh
):
    """설정한 상위 경로 + **인증된 본인**의 사용자명. 클라이언트는 관여할 수 없다."""
    cluster.home_base = "/nfs/home"
    db.commit()
    body = client.get(
        f"/api/v1/clusters/{cluster.id}/files", headers=auth_headers(user_token)
    ).json()
    assert body["home"] == "/nfs/home/jrpark"
    # 허용 루트도 함께 옮겨간다 — 조회와 변경이 같은 범위를 쓴다.
    assert body["roots"] == ["/nfs/home/jrpark"]


def test_home_base_trailing_slash_does_not_double_up(client, db, cluster, user_token, fake_ssh):
    cluster.home_base = "/nfs/home/"
    db.commit()
    body = client.get(
        f"/api/v1/clusters/{cluster.id}/files", headers=auth_headers(user_token)
    ).json()
    assert body["home"] == "/nfs/home/jrpark"


def test_home_falls_back_to_nss_when_unset(client, db, cluster, user_token, fake_ssh):
    """설정이 비면 지금까지처럼 `getent passwd`로 읽는다 — 기존 클러스터가 깨지지 않는다."""
    cluster.home_base = None
    db.commit()
    body = client.get(
        f"/api/v1/clusters/{cluster.id}/files", headers=auth_headers(user_token)
    ).json()
    assert body["home"] == "/home/jrpark"  # 대역의 NSS 값


def test_storage_shows_only_user_paths(client, cluster, user_token, fake_ssh):
    """tmpfs·/ 같은 무관한 마운트는 빼고 홈만 보여준다."""
    body = client.get(
        f"/api/v1/clusters/{cluster.id}/storage", headers=auth_headers(user_token)
    ).json()
    rows = {t["label"]: t for t in body["targets"]}
    assert set(rows) == {"홈"}
    # 홈은 자신을 담고 있는 마운트(/home)로 매칭된다 — / 가 아니라
    assert rows["홈"]["mount"] == "/home"
    assert rows["홈"]["used_pct"] == 12.0


# --- 파일 조작 (U-FM-02·04) -------------------------------------------------
# 여기서 지켜야 할 것은 하나다: **조회와 변경이 같은 범위를 쓴다.**
# 목록에 안 보이는 곳을 지울 수 있으면 브라우저의 경계가 무의미해진다.


def test_operations_require_auth(client, cluster):
    cid = cluster.id
    assert client.post(f"/api/v1/clusters/{cid}/files/directory", json={"path": "/x"}).status_code == 401
    assert client.delete(f"/api/v1/clusters/{cid}/files", params={"path": "/x"}).status_code == 401
    assert client.get(f"/api/v1/clusters/{cid}/files/download", params={"path": "/x"}).status_code == 401


@pytest.mark.parametrize(
    "call",
    [
        lambda c, cid, h: c.post(
            f"/api/v1/clusters/{cid}/files/directory", json={"path": "/etc/evil"}, headers=h
        ),
        lambda c, cid, h: c.post(
            f"/api/v1/clusters/{cid}/files/file", json={"path": "/etc/evil"}, headers=h
        ),
        lambda c, cid, h: c.delete(
            f"/api/v1/clusters/{cid}/files", params={"path": "/etc/passwd"}, headers=h
        ),
        lambda c, cid, h: c.get(
            f"/api/v1/clusters/{cid}/files/download", params={"path": "/etc/passwd"}, headers=h
        ),
        lambda c, cid, h: c.post(
            f"/api/v1/clusters/{cid}/files/move",
            json={"path": "/home/jrpark/a", "to": "/etc/evil"},
            headers=h,
        ),
    ],
)
def test_operations_cannot_escape_the_allowed_roots(client, cluster, user_token, fake_ssh, call):
    """홈 밖은 조회뿐 아니라 **생성·삭제·이동·다운로드도** 막혀야 한다."""
    assert call(client, cluster.id, auth_headers(user_token)).status_code == 403


def test_relative_escape_is_normalized_before_the_check(client, cluster, user_token, fake_ssh):
    """`..`로 빠져나가는 경로는 정규화 뒤에 걸러야 한다 — 문자열 접두사만 보면 통과한다."""
    resp = client.post(
        f"/api/v1/clusters/{cluster.id}/files/directory",
        json={"path": "/home/jrpark/../../etc/evil"},
        headers=auth_headers(user_token),
    )
    assert resp.status_code == 403


def test_mkdir_and_touch_use_the_session_user(client, cluster, user_token, fake_ssh):
    headers = auth_headers(user_token)
    cid = cluster.id
    assert client.post(
        f"/api/v1/clusters/{cid}/files/directory", json={"path": "/home/jrpark/new"}, headers=headers
    ).json() == {"path": "/home/jrpark/new"}
    assert client.post(
        f"/api/v1/clusters/{cid}/files/file", json={"path": "/home/jrpark/a.txt"}, headers=headers
    ).json() == {"path": "/home/jrpark/a.txt"}
    assert set(fake_ssh.as_users) == {"jrpark"}
    assert ("mkdir", "/home/jrpark/new") in fake_ssh.ops
    assert ("touch", "/home/jrpark/a.txt") in fake_ssh.ops


def test_delete_passes_the_recursive_flag(client, cluster, user_token, fake_ssh):
    """재귀 삭제는 **명시적으로 요청할 때만** 한다 — 기본값으로 트리를 지우면 안 된다."""
    headers = auth_headers(user_token)
    client.delete(
        f"/api/v1/clusters/{cluster.id}/files", params={"path": "/home/jrpark/x"}, headers=headers
    )
    assert ("remove", "/home/jrpark/x", False) in fake_ssh.ops
    client.delete(
        f"/api/v1/clusters/{cluster.id}/files",
        params={"path": "/home/jrpark/y", "recursive": "true"},
        headers=headers,
    )
    assert ("remove", "/home/jrpark/y", True) in fake_ssh.ops


def test_move_is_rename_and_move_at_once(client, cluster, user_token, fake_ssh):
    body = client.post(
        f"/api/v1/clusters/{cluster.id}/files/move",
        json={"path": "/home/jrpark/a.txt", "to": "/home/jrpark/sub/b.txt"},
        headers=auth_headers(user_token),
    ).json()
    assert body["path"] == "/home/jrpark/sub/b.txt"
    assert ("move", "/home/jrpark/a.txt", "/home/jrpark/sub/b.txt") in fake_ssh.ops


def test_upload_streams_into_the_target_directory(client, cluster, user_token, fake_ssh):
    resp = client.post(
        f"/api/v1/clusters/{cluster.id}/files/upload",
        data={"path": "/home/jrpark"},
        files={"file": ("report.csv", b"a,b,c\n1,2,3\n", "text/csv")},
        headers=auth_headers(user_token),
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["path"] == "/home/jrpark/report.csv"
    assert ("upload", "/home/jrpark/report.csv", 12) in fake_ssh.ops


def test_upload_rejects_a_path_in_the_filename(client, cluster, user_token, fake_ssh):
    """파일명에 경로가 섞여 오면 디렉터리 지정을 우회하게 된다."""
    resp = client.post(
        f"/api/v1/clusters/{cluster.id}/files/upload",
        data={"path": "/home/jrpark"},
        files={"file": ("../../etc/evil", b"x", "text/plain")},
        headers=auth_headers(user_token),
    )
    assert resp.status_code == 422


def test_download_streams_bytes_with_a_filename(client, cluster, user_token, fake_ssh):
    resp = client.get(
        f"/api/v1/clusters/{cluster.id}/files/download",
        params={"path": "/home/jrpark/run.sh"},
        headers=auth_headers(user_token),
    )
    assert resp.status_code == 200
    assert resp.content == b"hello"
    assert "run.sh" in resp.headers["content-disposition"]
