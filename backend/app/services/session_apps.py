"""인터랙티브 앱 카탈로그 (U-IA-01·02).

**앱 목록은 코드에 있다.** 앱을 하나 늘리려면 이미지 안의 기동 경로(`PORTAL_APP` 분기,
`deploy/images/rocky9-mate/start-desktop.sh`)도 함께 만들어야 하므로, 목록을 DB로 빼도
코드 배포는 어차피 따라온다. 대신 목록을 **여기 한 곳에만** 두고 API로 내려보내
프론트엔드가 같은 배열을 또 갖지 않게 한다.

이미지는 포털 공용 디렉터리(`settings.app_image_dir`) 아래에서 찾는다. 여기 `image`는
**기본 파일명**이고, 앱 카탈로그(`app_catalog.image_file`)에 등록이 있으면 그쪽이 이긴다 —
해석은 `services/app_images.py`가 한 곳에서 한다.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.core.errors import ValidationFailed


@dataclass(frozen=True)
class InteractiveApp:
    id: str
    name: str
    description: str
    #: 저장소 아래의 이미지 이름. SIF 파일명 또는 레지스트리 태그.
    #: 아직 제공하지 않는 앱은 비어 있다.
    image: str
    #: 기능 정의서 ID (화면의 `<Fid>` 매핑).
    fid: str
    #: **실행 방식**(기동 커맨드·파라미터)이 확정됐는가. 이미지가 거기 있는지는 별개
    #: 질문이고(`installed`, 클러스터가 답한다) 이 값은 코드가 답한다. 목록에는 예정
    #: 앱도 보여주되 고를 수 없게 한다.
    ready: bool = True
    #: 컨테이너 안의 기동 스크립트. VNC 앱과 HTTP 앱이 서로 다른 경로를 쓴다.
    entry: str = "/opt/portal/start-desktop.sh"
    #: 접속 방식. `vnc`는 RFB 바이트 중계, `http`는 리버스 프록시다 — **화면이
    #: 어디로 보낼지 정하는 값**이라 카탈로그가 알려 준다.
    transport: str = "vnc"
    #: 카드에 함께 띄우는 안내. 원래는 **준비되지 않은 앱**의 "언젠가 되나?"에 답하는
    #: 자리였는데(`ready=False`), 화면이 `ready`와 무관하게 띄우므로 **제약이 있는 채로
    #: 제공하는 앱**의 안내도 여기 적는다(M-Star: GPU·라이선스 없음).
    note: str = ""


#: 앱 목록의 **단일 출처**. 예정된 앱까지 여기 둔다 — 화면이 따로 갖고 있으면
#: 실행 가능한 앱이 무엇인지에 대해 앞뒤가 갈린다.
#:
#: `desktop`과 `paraview`는 지금 **같은 이미지**를 쓴다. 하나의 Rocky 9 이미지에 MATE와
#: ParaView가 함께 들어 있고 `PORTAL_APP`으로 갈린다. 앱마다 이미지를 나눌 때는 이 표의
#: `image`만 바꾸면 된다.
APPS: tuple[InteractiveApp, ...] = (
    InteractiveApp(
        id="desktop",
        name="원격 데스크톱",
        description="MATE 데스크톱 (Rocky 9)",
        image="rocky9-mate-1.5.sif",
        fid="U-IA-02",
    ),
    InteractiveApp(
        id="paraview",
        name="ParaView",
        description="과학 시각화 5.11 (소프트웨어 렌더링)",
        image="rocky9-mate-1.5.sif",
        fid="U-IA-02",
    ),
    # **이미지가 다른 첫 VNC 앱이다.** M-Star 4.1.15는 Ubuntu 24.04 빌드라
    # `GLIBC_2.38`·`GLIBCXX_3.4.32`를 요구하고, Rocky 9는 glibc 2.34라 실행 자체가
    # 안 된다(실측). 그래서 `deploy/images/ubuntu24-mstar`로 따로 만든다 —
    # 세션 계약(Xvnc·connection.json·PORTAL_APP)은 같아서 여기 한 줄이면 붙는다.
    InteractiveApp(
        id="mstar",
        name="M-Star CFD",
        description="M-Star Pre 4.1.15 — 모델 작성·시각화 (해석은 GPU 노드 필요)",
        image="ubuntu24-mstar-1.0.sif",
        fid="U-IA-02",
        entry="/opt/portal/start-desktop.sh",
        note=(
            "**GPU가 없어 해석(Solve)은 돌지 않습니다.** 화면은 소프트웨어 렌더링"
            "(Mesa llvmpipe)이라 회전·확대가 느립니다. 라이선스가 등록되지 않은 "
            "상태에서는 상태 표시줄에 'No license'가 뜨며 모델 작성·저장만 됩니다."
        ),
    ),
    # JupyterLab은 **VNC를 쓰지 않는 첫 앱이다**. X 서버 없이 HTTP로 뜨고, 포털이
    # `session-apps/{job_id}/**`로 리버스 프록시한다. 컨테이너가 자기 base_url을 그
    # 경로로 맞춰 띄우므로(start-jupyter.sh) 포털은 본문을 고쳐 쓰지 않는다.
    InteractiveApp(
        id="jupyter",
        name="JupyterLab",
        description="노트북 세션 (Python 3.11)",
        image="rocky9-mate-1.6.sif",
        fid="U-IA-01",
        entry="/opt/portal/start-jupyter.sh",
        transport="http",
    ),
    # **code-server는 포털이 호스팅하지 않는다.**
    #
    # 하위 경로로 서비스할 수 없기 때문이다 — code-server는 base path 지원을 제거했고,
    # 에셋 일부가 절대 경로로 링크돼 접두사 프록시에서 루트로 새어 나간다(Jupyter의
    # `--ServerApp.base_url`에 해당하는 것이 없다). 세션마다 서브도메인을 주면 되지만
    # 와일드카드 DNS와 인증서가 필요해 포털 밖 결정이다.
    #
    # HPC에서 가장 흔한 구성인 **VS Code Remote-SSH**를 안내한다 — 사용자 기계의 VS Code가
    # 로그인 노드로 붙는다. 포털이 만들 것이 없고, 확장·설정도 사용자 것을 그대로 쓴다.
    InteractiveApp(
        id="code-server",
        name="VS Code (Remote-SSH)",
        description="사용자 기계의 VS Code로 로그인 노드에 접속합니다",
        image="",
        fid="U-IA-03",
        ready=False,
        note=(
            "포털이 호스팅하지 않습니다. VS Code에 **Remote - SSH** 확장을 설치하고 "
            "로그인 노드로 접속하세요 — 확장·설정이 그대로 따라오고, 터미널에서 "
            "srun·sbatch를 바로 쓸 수 있습니다."
        ),
    ),
)


def get(app_id: str) -> InteractiveApp:
    for app in APPS:
        if app.id == app_id:
            return app
    raise ValidationFailed(
        "지원하지 않는 앱입니다.",
        detail={"app": app_id, "supported": [a.id for a in APPS]},
    )
