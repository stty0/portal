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
    assert "쓰기 권한" in body["message"]


def test_unreachable_login_node_says_something_different(
    client, cluster, admin_token, fake_images
):
    """디렉터리가 없는 것과 못 붙는 것은 **할 일이 다르다** — 뭉뚱그리면 엉뚱한 데를 고친다."""
    fake_images.error = paramiko.SSHException("EOF during negotiation")
    body = _check(client, cluster, admin_token)
    assert body["ok"] is False
    assert "확인할 수 없습니다" in body["message"]
    assert "쓰기 권한" not in body["message"]


def test_check_does_not_use_the_cache(client, cluster, admin_token, fake_images):
    """진단은 항상 지금을 봐야 한다 — 고친 뒤 다시 눌렀는데 옛 답이 나오면 안 된다."""
    for _ in range(2):
        _check(client, cluster, admin_token)
    assert fake_images.opened == 2


# --- 잠금 셋: ready · installed · allowed (T-06) ------------------------------
# `ready`는 **실행 방식이 확정됐나**(코드), `installed`는 **파일이 거기 있나**(클러스터),
# `allowed`는 **이 사람이 쓸 수 있나**(계정 배정). 셋은 서로 다른 질문이다.


def test_apps_report_installed_per_cluster(client, cluster, user_token, fake_images):
    """desktop의 이미지만 놓아 두면 그것만 `installed`가 된다."""
    from app.services import session_apps

    fake_images.entries = [_entry(session_apps.get("desktop").image)]
    body = client.get(
        f"{API}/clusters/{cluster.id}/interactive-apps", headers=auth_headers(user_token)
    ).json()
    installed = {a["id"]: a["installed"] for a in body}
    assert installed["desktop"] is True
    assert installed["jupyter"] is False


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


# --- 변환: 빌드 → 배치 (T-08) -------------------------------------------------
# 빌드는 **Slurm 잡**(관리자 홈에 SIF가 떨어진다), 배치는 **포털이 sudo로 하는 mv 하나**다.
# 목적지가 root 소유인 이유는 컨테이너 이미지가 **모든 사용자가 실행하는 코드**여서다 —
# 디렉터리를 사용자 그룹에 열면 아무나 남이 실행할 이미지를 바꿔 놓을 수 있다.


def _build(client, cluster, token, app_id="openfoam", kind="batch"):
    return client.post(
        f"{API}/clusters/{cluster.id}/app-images/{kind}/{app_id}/build",
        headers=auth_headers(token),
    )


def test_build_submits_a_job_whose_script_pins_the_caches(
    client, cluster, admin_token, fake_images, slurm_client
):
    """캐시를 홈 밖에 두면 노드가 찬다 — dev01이 실제로 그렇게 죽은 적이 있다(11GB)."""
    assert _build(client, cluster, admin_token).status_code == 200
    spec = [kw["spec"] for name, kw in slurm_client.calls if name == "submit_job"][0]
    script = spec["script"]
    # 작업 디렉터리가 없으면 **Slurm이 제출을 거부한다**(실측). 잡을 만들어 놓고
    # 거부당하는 것을 테스트가 잡아야 한다.
    assert spec["job"]["current_working_directory"] == "/home/opadmin"
    assert "base=/home/opadmin/.portal/build" in script
    assert 'APPTAINER_CACHEDIR="$base/cache"' in script
    assert 'APPTAINER_TMPDIR="$base/tmp"' in script
    # **$HOME을 쓰면 안 된다** — Slurm 배치 환경에 없어서 `set -u`와 만나 첫 줄에서 죽는다.
    assert "$HOME" not in script


def test_build_uses_the_registered_ref_and_writes_to_a_temp_name(
    client, cluster, admin_token, fake_images, slurm_client
):
    """중간에 죽은 빌드가 완성된 파일처럼 보이면 `installed`가 앱을 열어 버린다."""
    _build(client, cluster, admin_token)
    script = [kw["spec"] for n, kw in slurm_client.calls if n == "submit_job"][0]["script"]
    # IMAGE_REF가 셸 메타문자를 애초에 막아서 shlex.quote가 따옴표를 붙이지 않는다 —
    # 그래도 quote를 통과시키는 이유는 정규식이 느슨해질 때의 안전망이다.
    assert "apptainer build \"$out.tmp\" docker://opencfd/openfoam-default:2512" in script
    assert 'mv "$out.tmp" "$out"' in script


def test_build_is_refused_when_the_app_has_no_source(
    client, cluster, admin_token, fake_images, monkeypatch
):
    """출처가 없으면 만들 수가 없다 — 잡을 던져 놓고 워커에서 죽게 두지 않는다."""
    from app.services import session_apps

    # jupyter가 쓰는 1.6은 아직 레지스트리에 없다(1.5만 올라가 있다).
    assert session_apps.get("jupyter").image_ref == ""
    resp = _build(client, cluster, admin_token, app_id="jupyter", kind="interactive")
    assert resp.status_code == 422
    assert "출처" in resp.json()["message"]


def test_build_requires_admin(client, cluster, user_token, fake_images):
    assert _build(client, cluster, user_token).status_code == 403


def test_install_moves_the_built_file_as_root(client, cluster, admin_token, fake_images):
    """포털이 권한을 올리는 **유일한** 지점이라, 무엇을 어떻게 부르는지 고정한다."""
    resp = client.post(
        f"{API}/clusters/{cluster.id}/app-images/batch/openfoam/install",
        headers=auth_headers(admin_token),
    )
    assert resp.status_code == 200, resp.text
    # 존재 확인은 **본인 계정**으로, 옮기기는 root로. 경로는 셋 다 서버가 만든다.
    source = "/home/opadmin/.portal/build/openfoam-2512.sif"
    assert ("opadmin", ["test", "-f", source]) in fake_images.ran
    target = "/home/.portal/images/openfoam-2512.sif"
    assert ("root", ["mv", source, target]) in fake_images.ran
    # `mv`는 소유자를 가져온다 — 뺏지 않으면 빌드한 사용자가 **모두가 실행하는 이미지**를
    # 계속 덮어쓸 수 있다. 디렉터리를 root 소유로 둔 이유가 여기서 무너진다.
    assert ("root", ["chown", "root:root", target]) in fake_images.ran
    assert ("root", ["chmod", "0644", target]) in fake_images.ran


def test_install_invalidates_the_cache_so_the_app_opens_at_once(
    client, cluster, admin_token, fake_images
):
    """포털이 **직접 넣은** 경우다 — 여기서만은 TTL을 기다릴 이유가 없다."""
    fake_images.entries = []
    assert _list(client, cluster, admin_token) == []  # 빈 목록이 캐시된다

    fake_images.entries = [_entry("openfoam-2512.sif")]
    client.post(
        f"{API}/clusters/{cluster.id}/app-images/batch/openfoam/install",
        headers=auth_headers(admin_token),
    )
    assert _list(client, cluster, admin_token) == ["openfoam-2512.sif"]


def test_install_requires_admin(client, cluster, user_token, fake_images):
    resp = client.post(
        f"{API}/clusters/{cluster.id}/app-images/batch/openfoam/install",
        headers=auth_headers(user_token),
    )
    assert resp.status_code == 403
    assert fake_images.ran == []  # 권한을 보기 전에 아무것도 실행하지 않는다


def test_catalog_refs_are_shaped_so_the_build_job_can_use_them():
    """카탈로그에 적힌 출처는 **그대로 `apptainer build`로 넘어간다.**

    오타나 스킴 누락은 잡을 던져 놓고 워커에서 죽는 것으로만 드러난다 — 여기서 막는다.
    """
    from app.services import batch_apps, session_apps
    from app.services.app_images import IMAGE_REF

    for app in list(session_apps.APPS) + list(batch_apps.APPS):
        if app.image_ref:
            assert IMAGE_REF.match(app.image_ref), f"{app.id}: {app.image_ref}"


def test_apps_without_a_registry_source_say_so_by_being_empty():
    """비어 있는 것이 정보다 — 레지스트리에서 오지 않는 이미지가 있다는 사실.

    jupyter가 쓰는 1.6은 아직 안 올라갔고, code-server는 포털이 호스팅하지 않는다.
    비어 있으면 화면에 [변환]이 뜨지 않는다.
    """
    from app.services import session_apps

    empty = {a.id for a in session_apps.APPS if not a.image_ref}
    assert empty == {"jupyter", "code-server"}


def test_requires_admin(client, cluster, user_token, fake_images):
    resp = client.get(
        f"{API}/clusters/{cluster.id}/app-images", headers=auth_headers(user_token)
    )
    assert resp.status_code == 403
    assert fake_images.opened == 0  # 권한을 보기 전에 SSH를 열지 않는다


def test_requires_auth(client, cluster):
    assert client.get(f"{API}/clusters/{cluster.id}/app-images").status_code == 401
