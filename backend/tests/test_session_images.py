"""세션 컨테이너 이미지 정의의 정합성 (U-IA-02).

이미지가 **두 개**가 되면서 생긴 위험을 잠근다. M-Star는 Ubuntu 24.04 빌드라
`GLIBC_2.38`을 요구하고 Rocky 9(glibc 2.34)에서는 실행 자체가 안 되므로
`deploy/images/ubuntu24-mstar`를 따로 만들었는데, 그 과정에서 **VNC 부트스트랩
스크립트가 복사**됐다. 그 앞부분은 보안과 직결되고(비밀번호·xauth 쿠키·포트 경쟁)
실측으로 다듬은 부분이라 두 벌이 갈라지면 한쪽만 고쳐지는 버그가 난다.
"""

import pathlib

import pytest

from app.services import session_apps

IMAGES = pathlib.Path(__file__).resolve().parents[2] / "deploy/images"
ROCKY = IMAGES / "rocky9-mate"
MSTAR = IMAGES / "ubuntu24-mstar"

#: 비교 구간의 양끝. **머리말은 뺀다** — 이미지마다 자기 사정을 적는 자리고(하나는
#: "복사본이니 갈라지지 마라"라고 경고한다), 문서가 다른 것은 버그가 아니다.
#: 잠그려는 것은 그 아래 **실행되는 코드**다.
BODY_START = "set -euo pipefail"
DISPATCH_MARKER = "# --- 앱 실행 -"


def _bootstrap_body(path: pathlib.Path) -> str:
    """머리말과 앱 분기를 뺀 가운데 — 두 이미지가 반드시 같아야 하는 부분."""
    text = path.read_text(encoding="utf-8")
    _, started, rest = text.partition(BODY_START)
    assert started, f"{path}에서 `{BODY_START}`를 찾지 못했다"
    body, sep, _ = rest.partition(DISPATCH_MARKER)
    assert sep, f"{path}에서 앱 분기 표시를 찾지 못했다"
    return body


@pytest.mark.parametrize("name", ["start-mate.sh", "reset-window-policy.sh", "tint2rc"])
def test_shared_session_files_are_identical_between_images(name):
    """두 이미지가 **같은 파일**을 갖는다. 갈라지면 한쪽만 고쳐진다."""
    assert (ROCKY / name).read_bytes() == (MSTAR / name).read_bytes(), (
        f"{name}이 두 이미지에서 갈라졌다 — 한쪽만 고치면 세션 동작이 이미지마다 달라진다"
    )


def test_vnc_bootstrap_prologue_is_identical_between_images():
    """`start-desktop.sh`의 **앱 분기 앞부분**은 글자까지 같아야 한다.

    거기에 VNC 비밀번호 발급·X 접근 제어 쿠키·포트 경쟁 회피·`connection.json`
    원자적 기록이 들어 있다. 한쪽에서만 고치면 그 이미지의 세션만 조용히 약해진다.
    """
    assert _bootstrap_body(ROCKY / "start-desktop.sh") == _bootstrap_body(
        MSTAR / "start-desktop.sh"
    ), "VNC 부트스트랩이 두 이미지에서 갈라졌다 — 한쪽 세션만 조용히 약해진다"


def test_every_app_entry_script_exists_in_its_image():
    """카탈로그의 `entry`가 가리키는 스크립트가 이미지 정의에 실제로 있어야 한다."""
    # 이미지 파일명 → 그 이미지를 만드는 디렉터리
    source_of = {"rocky9-mate": ROCKY, "ubuntu24-mstar": MSTAR}
    for app in session_apps.APPS:
        if not app.ready or not app.image:
            continue
        prefix = app.image.rsplit("-", 1)[0]
        directory = source_of.get(prefix)
        assert directory, f"{app.id}: 이미지 {app.image}를 만드는 디렉터리를 모른다"
        script = directory / pathlib.Path(app.entry).name
        assert script.is_file(), f"{app.id}: {app.entry}가 {directory.name}에 없다"


def test_mstar_uses_its_own_image_because_rocky_cannot_run_it():
    """M-Star를 rocky9-mate로 되돌리면 워커에서 실행 자체가 실패한다.

    실측: `bin/mstar`가 GLIBC_2.38·GLIBCXX_3.4.32를 요구하고 Rocky 9는 glibc 2.34다.
    되돌리려면 그 사실이 바뀌었는지 먼저 확인해야 한다.
    """
    mstar = session_apps.get("mstar")
    assert mstar.image.startswith("ubuntu24-mstar"), (
        "M-Star는 Ubuntu 24.04 이미지여야 한다 — Rocky 9는 glibc가 낮아 못 띄운다"
    )
    assert mstar.transport == "vnc"


def test_mstar_card_warns_about_the_missing_gpu():
    """GPU가 없어 해석이 안 된다는 사실은 **카드에 적혀 있어야 한다.**

    화면은 `note`를 그대로 띄운다. 여기가 비면 사용자는 Solve를 눌러 보고 나서야 안다.
    """
    note = session_apps.get("mstar").note
    assert "GPU" in note and "라이선스" in note


def test_dockerfile_installs_vncpasswd_tools():
    """`tigervnc-tools`가 빠지면 세션이 비밀번호 발급 줄에서 죽는다.

    Rocky는 서버 패키지에 `vncpasswd`가 들어 있지만 Ubuntu는 따로 뗀다. 이미지는
    멀쩡히 빌드되고 `Xvnc`도 있어서 **빌드로는 안 잡힌다**(실제로 SIF 스모크
    테스트에서야 잡혔다).
    """
    dockerfile = (MSTAR / "Dockerfile").read_text(encoding="utf-8")
    assert "tigervnc-tools" in dockerfile
