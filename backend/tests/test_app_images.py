"""클러스터에 있는 이미지 파일 목록 (A-OP-02).

파드의 파일시스템을 읽던 것을 클러스터 SSH로 옮겼다. 여기서 고정하는 것은 **어디를
읽는가**(클러스터마다 다른 경로)와 **실패했을 때 무엇이 되는가**(빈 목록)다.
"""

import paramiko
import pytest

from app.clients.ssh.client import FileEntry
from app.core.errors import ExternalServiceError, ValidationFailed
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
        #: `(사용자, argv)` 기록. **누가** 실행했는지가 핵심이라 사용자도 함께 남긴다.
        self.ran: list[tuple[str, list[str]]] = []

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

    def home_dir(self, user):
        return f"/home/{user}"

    def _run_as(self, user, argv):
        self.ran.append((user, list(argv)))
        return ""


def _entry(name, is_dir=False):
    return FileEntry(name=name, is_dir=is_dir, size=1, mtime=None, mode="-rw-r--r--", uid=0, gid=0)


@pytest.fixture
def fake_images(monkeypatch):
    """기본 목록. 테스트마다 `.entries`/`.error`를 갈아 끼운다."""
    fake = FakeSftp([_entry("b.sif"), _entry("a.sif"), _entry("sub", is_dir=True)])
    monkeypatch.setattr(AppImageService, "_connect", lambda self, cluster: fake)
    return fake


def _list(client, cluster, token):
    return client.get(
        f"{API}/clusters/{cluster.id}/app-images", headers=auth_headers(token)
    ).json()


def test_lists_only_files_sorted(client, cluster, admin_token, fake_images):
    assert _list(client, cluster, admin_token) == ["a.sif", "b.sif"]  # 디렉터리는 빠지고 정렬


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


def _apps(client, cluster, token, *, refresh=False):
    """사용자 앱 목록 — **캐시를 쓰는 쪽**이다(관리자 드롭다운과 다르다)."""
    query = "?refresh=true" if refresh else ""
    return client.get(
        f"{API}/clusters/{cluster.id}/interactive-apps{query}", headers=auth_headers(token)
    )


def test_second_call_does_not_reopen_ssh(client, cluster, user_token, fake_images):
    """앱 목록을 그릴 때마다 물으면 화면 한 번에 SSH가 여러 번 열린다.

    SSH 왕복이 300~430ms(실측)라 이 캐시가 앱 화면 체감 속도를 그대로 정한다.
    """
    for _ in range(3):
        _apps(client, cluster, user_token)
    assert fake_images.opened == 1


def test_empty_result_is_cached_too(client, cluster, user_token, fake_images):
    """디렉터리가 없는 클러스터에 매번 SSH를 여는 것이 제일 아깝다."""
    fake_images.entries = []
    for _ in range(3):
        _apps(client, cluster, user_token)
    assert fake_images.opened == 1


def test_refresh_bypasses_the_cache(client, cluster, user_token, fake_images):
    """`↻ 새로고침`은 **클러스터에 다시 묻는다.**

    SIF는 포털을 거치지 않고 놓이므로 서버가 새 파일을 알 방법이 없다 — 사람이 눌러
    알려주는 것이 유일한 즉시 반영 수단이다. 이걸 잃으면 방금 올린 이미지가
    캐시 TTL(10분)이 끝날 때까지 안 보인다.
    """
    _apps(client, cluster, user_token)
    assert fake_images.opened == 1

    fake_images.entries = [_entry("newly-uploaded.sif")]
    body = _apps(client, cluster, user_token, refresh=True).json()

    assert fake_images.opened == 2, "refresh=true인데 SSH를 다시 열지 않았다"
    assert all(not a["installed"] for a in body), "카탈로그에 없는 파일이라 설치로 잡히면 안 된다"
    # 새로 읽은 결과가 캐시에 남아야 한다 — 안 그러면 다음 요청이 또 SSH를 연다.
    _apps(client, cluster, user_token)
    assert fake_images.opened == 2


def test_admin_image_dropdown_never_serves_a_stale_list(client, cluster, admin_token, fake_images):
    """관리자가 **방금 올린** SIF를 고르는 자리다 — 캐시를 타면 등록을 못 한다.

    호출이 드물고 관리자 전용이라 매번 SSH를 열어도 된다.
    """
    for _ in range(3):
        client.get(f"{API}/clusters/{cluster.id}/app-images", headers=auth_headers(admin_token))
    assert fake_images.opened == 3


# --- 등록 화면의 진단 (A-CL-02) ---------------------------------------------
# 목록은 실패를 삼키지만 여기는 **무엇을 해야 하는지** 말해야 한다.


def _check(client, cluster, token):
    return client.get(
        f"{API}/clusters/{cluster.id}/image-dir", headers=auth_headers(token)
    ).json()


def test_check_reports_the_path_and_count(client, cluster, admin_token, fake_images):
    body = _check(client, cluster, admin_token)
    assert body["ok"] is True
    assert body["path"] == "/home/.portal/images"
    assert body["images"] == 2  # 디렉터리는 세지 않는다


def test_missing_directory_is_a_warning_not_an_error(
    client, cluster, admin_token, fake_images
):
    """등록 순서를 강요하면 클러스터를 먼저 등록할 수 없다 — 200으로 알리기만 한다."""
    fake_images.error = ValidationFailed("경로를 찾을 수 없습니다.")
    resp = client.get(
        f"{API}/clusters/{cluster.id}/image-dir", headers=auth_headers(admin_token)
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is False
    # 경로와 **할 일**이 함께 있어야 관리자가 움직일 수 있다.
    assert "/home/.portal/images" in body["message"]
    assert "SIF를 넣어" in body["message"]
    # **쓰기 권한을 주라고 하면 안 된다** — 이 클러스터에 관리자 그룹이 없어서 그 말은
    # `domain users`에 여는 것이고, 그러면 아무나 남이 실행할 이미지를 바꿀 수 있다.
    assert "쓰기 권한은 필요하지 않습니다" in body["message"]


def test_unreachable_login_node_says_something_different(
    client, cluster, admin_token, fake_images
):
    """디렉터리가 없는 것과 못 붙는 것은 **할 일이 다르다** — 뭉뚱그리면 엉뚱한 데를 고친다."""
    fake_images.error = paramiko.SSHException("EOF during negotiation")
    body = _check(client, cluster, admin_token)
    assert body["ok"] is False
    assert "확인할 수 없습니다" in body["message"]
    assert "SIF를 넣어" not in body["message"]


def test_check_does_not_use_the_cache(client, cluster, admin_token, fake_images):
    """진단은 항상 지금을 봐야 한다 — 고친 뒤 다시 눌렀는데 옛 답이 나오면 안 된다."""
    for _ in range(2):
        _check(client, cluster, admin_token)
    assert fake_images.opened == 2


# --- 잠금 셋: ready · installed · allowed (T-06) ------------------------------
# `ready`는 **실행 방식이 확정됐나**(코드), `installed`는 **파일이 거기 있나**(클러스터),
# `allowed`는 **이 사람이 쓸 수 있나**(계정 배정). 셋은 서로 다른 질문이다.


def test_apps_report_installed_per_cluster(client, cluster, user_token, fake_images):
    """놓아 둔 이미지를 쓰는 앱만 `installed`가 된다.

    **앱 이름을 박아 두지 않는다.** 전에는 desktop·jupyter가 서로 다른 SIF를 쓴다는
    전제로 짰는데, 두 앱이 같은 이미지로 합쳐지자(1.5·1.6 → 1.7) 깨졌다. 실제 불변은
    "이미지가 있으면 그 이미지를 쓰는 앱 전부가 열린다"이므로 그대로 검사한다.
    """
    from app.services import session_apps

    target = session_apps.get("desktop").image
    others = {a.id for a in session_apps.APPS if a.ready and a.image and a.image != target}
    assert others, "이미지가 다른 앱이 하나는 있어야 이 테스트가 의미를 갖는다"

    fake_images.entries = [_entry(target)]
    body = client.get(
        f"{API}/clusters/{cluster.id}/interactive-apps", headers=auth_headers(user_token)
    ).json()
    installed = {a["id"]: a["installed"] for a in body}

    for app in session_apps.APPS:
        if app.ready and app.image == target:
            assert installed[app.id] is True, f"{app.id}: 이미지가 있는데 잠겼다"
    for app_id in others:
        assert installed[app_id] is False, f"{app_id}: 이미지가 없는데 열렸다"


def test_missing_image_locks_the_app_but_keeps_it_listed(
    client, cluster, user_token, fake_images
):
    """숨기면 '왜 없지'에 답할 방법이 사라진다 — 남겨 두고 잠근다."""
    fake_images.entries = []
    body = client.get(
        f"{API}/clusters/{cluster.id}/batch-apps", headers=auth_headers(user_token)
    ).json()
    assert {a["id"] for a in body}  # 목록은 그대로다
    assert all(a["installed"] is False for a in body)


def test_submitting_an_app_without_its_image_is_blocked(
    client, cluster, user_token, fake_images
):
    """목록에서 잠그는 것만으로는 제한이 아니다 — 화면을 거치지 않는 호출이 있다."""
    fake_images.entries = []
    resp = client.post(
        f"{API}/clusters/{cluster.id}/batch-apps/openfoam/jobs",
        json={"name": "run", "params": {"case": "/home/jrpark/pitz"}},
        headers=auth_headers(user_token),
    )
    assert resp.status_code == 422
    body = resp.json()
    assert "이 클러스터에 없습니다" in body["message"]
    assert "openfoam-2512.sif" in body["message"]  # 무엇을 넣어야 하는지 말한다


def test_dropping_a_sif_in_opens_the_app_without_a_code_deploy(
    client, cluster, user_token, fake_images, redis
):
    """이 에픽의 핵심. `ready` 상수를 고쳐 재배포하던 것을 파일 존재로 바꿨다.

    **캐시 TTL만큼(60초) 늦게 열린다.** 아래에서 키를 지우는 것이 그 시간 경과다 —
    안 지우면 이 테스트는 통과하지 않는다. 목록 캐시를 둔 대가이고, 관리자가 파일을
    넣은 뒤 1분 안에 보이는 것은 감수할 만하다고 판단했다.
    """
    from app.services import batch_apps

    image = batch_apps.get("openfoam").image
    fake_images.entries = []
    before = client.get(
        f"{API}/clusters/{cluster.id}/batch-apps", headers=auth_headers(user_token)
    ).json()
    assert next(a for a in before if a["id"] == "openfoam")["installed"] is False

    fake_images.entries = [_entry(image)]  # SIF를 디렉터리에 넣었다
    redis.delete(f"appImages:{cluster.id}")  # TTL 경과
    after = client.get(
        f"{API}/clusters/{cluster.id}/batch-apps", headers=auth_headers(user_token)
    ).json()
    assert next(a for a in after if a["id"] == "openfoam")["installed"] is True


def test_ready_and_installed_are_different_questions(client, cluster, user_token, fake_images):
    """Isaac Sim은 이미지가 생겨도 `ready=False`다 — 커맨드가 아직 실측이 아니다."""
    from app.services import batch_apps

    fake_images.entries = [_entry(batch_apps.get("isaac-sim").image)]
    body = client.get(
        f"{API}/clusters/{cluster.id}/batch-apps", headers=auth_headers(user_token)
    ).json()
    isaac = next(a for a in body if a["id"] == "isaac-sim")
    assert isaac["installed"] is True and isaac["ready"] is False


def test_failure_is_not_cached_so_one_broken_user_cannot_lock_everyone(
    client, cluster, admin_token, fake_images
):
    """캐시 키가 클러스터라 여러 사용자가 나눠 쓴다. 실패를 캐시하면 프로비저닝되지
    않은 사용자 하나가 60초 동안 모두의 앱을 잠근다."""
    fake_images.error = paramiko.SSHException("EOF")
    assert _list(client, cluster, admin_token) == []

    fake_images.error = None
    assert _list(client, cluster, admin_token) == ["a.sif", "b.sif"]






















def test_requires_admin(client, cluster, user_token, fake_images):
    resp = client.get(
        f"{API}/clusters/{cluster.id}/app-images", headers=auth_headers(user_token)
    )
    assert resp.status_code == 403
    assert fake_images.opened == 0  # 권한을 보기 전에 SSH를 열지 않는다


def test_requires_auth(client, cluster):
    assert client.get(f"{API}/clusters/{cluster.id}/app-images").status_code == 401


# --- 이미지로 인정하는 확장자 ------------------------------------------------
# `IMAGE_FILE`은 **경로 안전성**만 본다(`../` 차단). 형식은 다른 질문이고, 둘을 한
# 정규식이 겸하던 탓에 이미지 디렉터리의 `README.txt`가 선택지에 떴다.


def test_only_container_images_are_listed(client, cluster, admin_token, fake_images):
    """디렉터리에 문서를 같이 둘 수 있다 — 그게 이미지로 보이면 안 된다."""
    fake_images.entries = [
        _entry("openfoam-2512.sif"),
        _entry("isaac.sqsh"),          # enroot(향후) — 목록에는 올린다
        _entry("README.txt"),
        _entry("notes.md"),
        _entry("archive.tar.gz"),
    ]
    assert _list(client, cluster, admin_token) == ["isaac.sqsh", "openfoam-2512.sif"]


def test_image_suffix_is_case_insensitive(client, cluster, admin_token, fake_images):
    """대문자 확장자가 디렉터리에 있는데 목록에만 없으면 원인을 찾기 어렵다."""
    fake_images.entries = [_entry("Rocky9-MATE.SIF")]
    assert _list(client, cluster, admin_token) == ["Rocky9-MATE.SIF"]  # 이름은 그대로


def test_non_image_files_are_not_counted_in_the_directory_check(
    client, cluster, admin_token, fake_images
):
    """등록 화면의 '파일 N개'도 같은 기준이어야 한다 — 아니면 숫자가 거짓말을 한다."""
    fake_images.entries = [_entry("a.sif"), _entry("README.txt")]
    assert _check(client, cluster, admin_token)["images"] == 1
