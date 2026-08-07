"""SSH 파일 조작의 **경로 관문** (U-FM-02·04).

라우터 테스트(test_files.py)는 서비스가 허용 루트를 넘기는지를 본다. 여기는 그 루트를
받아 실제로 판정하는 부분 — **보안 경계 그 자체**를 본다.
"""

import posixpath

import pytest

from app.clients.ssh.client import LoginNodeClient
from app.core.errors import Forbidden, ValidationFailed

ROOTS = ["/home/jrpark", "/scratch/jrpark"]


class FakeSftp:
    """서버의 realpath를 흉내낸다 — 정규화하고 심볼릭 링크를 해석한다."""

    def __init__(self, links: dict[str, str] | None = None):
        self.links = links or {}

    def normalize(self, path: str) -> str:
        resolved = posixpath.normpath(path)
        return self.links.get(resolved, resolved)


def guard(path, roots=ROOTS, **kw):
    return LoginNodeClient._guard(FakeSftp(**kw), path, roots)


def guard_new(path, roots=ROOTS, **kw):
    return LoginNodeClient._guard_new(FakeSftp(**kw), path, roots)


def test_paths_inside_the_roots_pass():
    assert guard("/home/jrpark") == "/home/jrpark"
    assert guard("/home/jrpark/data/run.sh") == "/home/jrpark/data/run.sh"
    assert guard("/scratch/jrpark/tmp") == "/scratch/jrpark/tmp"


def test_paths_outside_the_roots_are_refused():
    for path in ("/etc/passwd", "/home", "/home/someone-else", "/"):
        with pytest.raises(Forbidden):
            guard(path)


def test_prefix_alone_is_not_enough():
    """`/home/jrpark2`는 `/home/jrpark`의 하위가 아니다 — 구분자까지 봐야 한다."""
    with pytest.raises(Forbidden):
        guard("/home/jrpark2/secret")


def test_dotdot_is_resolved_before_the_check():
    """문자열 접두사만 보면 통과하는 경로다. 정규화 뒤에 판정해야 걸린다."""
    with pytest.raises(Forbidden):
        guard("/home/jrpark/../../etc/passwd")


def test_symlink_pointing_outside_is_refused():
    """홈 안의 링크가 밖을 가리키면 따라가서는 안 된다(서버가 realpath로 해석해 준다)."""
    links = {"/home/jrpark/escape": "/etc"}
    with pytest.raises(Forbidden):
        guard("/home/jrpark/escape", links=links)


# --- 새로 만들 경로 -------------------------------------------------------
# 없는 경로는 정규화 결과를 믿을 수 없어 **부모까지만** 서버에 묻는다.


def test_new_path_is_built_from_a_checked_parent():
    assert guard_new("/home/jrpark/new-dir") == "/home/jrpark/new-dir"
    assert guard_new("/home/jrpark/a/b.txt") == "/home/jrpark/a/b.txt"


def test_new_path_with_an_outside_parent_is_refused():
    with pytest.raises(Forbidden):
        guard_new("/etc/evil")


def test_new_path_cannot_escape_through_its_parent():
    with pytest.raises(Forbidden):
        guard_new("/home/jrpark/../../etc/evil")


def test_dotdot_as_the_name_is_refused():
    """마지막 조각의 `..`는 부모를 검사해도 밖으로 나간다 — 이름 단계에서 막는다."""
    for path in ("/home/jrpark/..", "/home/jrpark/.", "/home/jrpark/"):
        with pytest.raises((ValidationFailed, Forbidden)):
            guard_new(path)


def test_root_itself_cannot_be_removed_or_moved():
    """홈을 통째로 지우는 사고를 막는다. 후행 슬래시 표기도 같이 막아야 한다."""
    for root in ("/home/jrpark", "/scratch/jrpark"):
        with pytest.raises(ValidationFailed):
            LoginNodeClient._reject_root(root, ROOTS)
    # 하위 항목은 정상적으로 지워진다.
    LoginNodeClient._reject_root("/home/jrpark/data", ROOTS)
