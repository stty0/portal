"""클러스터에 있는 이미지 파일 목록 (A-OP-02).

파드의 파일시스템을 읽던 것을 클러스터 SSH로 옮겼다. 여기서 고정하는 것은 **어디를
읽는가**(클러스터마다 다른 경로)와 **실패했을 때 무엇이 되는가**(빈 목록)다.
"""

import paramiko
import pytest

from app.clients.ssh.client import FileEntry
from app.core.errors import ExternalServiceError
from app.services.app_images import AppImageService
from tests.conftest import auth_headers

API = "/api/v1"


class FakeSftp:
    """`list_dir`만 흉내 낸다. 어떤 경로로 불렸는지 기록한다."""

    def __init__(self, entries, error=None):
        self.entries = entries
        self.error = error
        self.paths: list[str] = []
        self.opened = 0

    def __enter__(self):
        self.opened += 1
        return self

    def __exit__(self, *a):
        return None

    def list_dir(self, user, path, **kw):
        self.paths.append(path)
        if self.error:
            raise self.error
        return path, self.entries


def _entry(name, is_dir=False):
    return FileEntry(name=name, is_dir=is_dir, size=1, mtime=None, mode="-rw-r--r--", uid=0, gid=0)


@pytest.fixture
def fake_images(monkeypatch):
    """기본 목록. 테스트마다 `.entries`/`.error`를 갈아 끼운다."""
    fake = FakeSftp([_entry("b.sif"), _entry("a.sif"), _entry("sub", is_dir=True)])
    monkeypatch.setattr(AppImageService, "_connect", lambda self, cluster: fake)
    return fake


def test_lists_only_files_sorted(client, cluster, admin_token, fake_images):
    body = client.get(
        f"{API}/clusters/{cluster.id}/app-images", headers=auth_headers(admin_token)
    ).json()
    assert body == ["a.sif", "b.sif"]  # 디렉터리는 빠지고 정렬된다


def test_reads_the_directory_derived_from_the_cluster_home(
    client, db, cluster, admin_token, fake_images
):
    """클러스터마다 다른 NFS를 본다 — 이 엔드포인트가 존재하는 이유다."""
    cluster.home_base = "/nfs/home"
    db.commit()
    client.get(f"{API}/clusters/{cluster.id}/app-images", headers=auth_headers(admin_token))
    assert fake_images.paths == ["/nfs/home/.portal/images"]


@pytest.mark.parametrize(
    "error",
    [
        ExternalServiceError("로그인 노드 접속 실패"),
        # paramiko는 자기 예외를 그대로 던진다. **PortalError도 OSError도 아니다** —
        # 처음 구현이 그 둘만 잡아서 실 클러스터에서 500으로 새어 나갔다.
        paramiko.SSHException("EOF during negotiation"),
        # sudo로 사용자를 못 찾는 등 예상 못 한 것도 화면을 깨뜨리면 안 된다.
        RuntimeError("예상 못 한 무엇"),
    ],
    ids=["portal-error", "paramiko", "unexpected"],
)
def test_any_ssh_failure_becomes_an_empty_list_not_an_error(
    client, cluster, admin_token, fake_images, error
):
    """로그인 노드가 죽어도 화면은 떠야 한다 — 앱이 잠기는 것과는 다른 일이다."""
    fake_images.error = error
    resp = client.get(
        f"{API}/clusters/{cluster.id}/app-images", headers=auth_headers(admin_token)
    )
    assert resp.status_code == 200
    assert resp.json() == []


def test_second_call_does_not_reopen_ssh(client, cluster, admin_token, fake_images):
    """앱 목록을 그릴 때마다 물으면 화면 한 번에 SSH가 여러 번 열린다."""
    for _ in range(3):
        client.get(f"{API}/clusters/{cluster.id}/app-images", headers=auth_headers(admin_token))
    assert fake_images.opened == 1


def test_empty_result_is_cached_too(client, cluster, admin_token, fake_images):
    """디렉터리가 없는 클러스터에 매번 SSH를 여는 것이 제일 아깝다."""
    fake_images.entries = []
    for _ in range(3):
        client.get(f"{API}/clusters/{cluster.id}/app-images", headers=auth_headers(admin_token))
    assert fake_images.opened == 1


def test_requires_admin(client, cluster, user_token, fake_images):
    resp = client.get(
        f"{API}/clusters/{cluster.id}/app-images", headers=auth_headers(user_token)
    )
    assert resp.status_code == 403
    assert fake_images.opened == 0  # 권한을 보기 전에 SSH를 열지 않는다


def test_requires_auth(client, cluster):
    assert client.get(f"{API}/clusters/{cluster.id}/app-images").status_code == 401
