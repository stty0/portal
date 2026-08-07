"""인터랙티브 앱 카탈로그 (U-IA-01·02).

**앱 목록은 코드에 있다.** 앱을 하나 늘리려면 이미지 안의 기동 경로(`PORTAL_APP` 분기,
`deploy/images/rocky9-mate/start-desktop.sh`)도 함께 만들어야 하므로, 목록을 DB로 빼도
코드 배포는 어차피 따라온다. 대신 목록을 **여기 한 곳에만** 두고 API로 내려보내
프론트엔드가 같은 배열을 또 갖지 않게 한다.

이미지는 클러스터의 **저장소**(`cluster.image_repository`) 아래에서 찾는다. 앱마다
이미지가 다를 수 있고, 저장소만 클러스터 설정으로 받는다. 저장소는 두 형식을 모두 받는다:

- 공유 SIF 디렉터리 — `/home/portal/images`
- OCI 레지스트리 — `docker://reg.example.com/hpc`, `oras://…`

apptainer가 둘 다 그대로 실행하므로 포털은 구분하지 않는다. 다만 레지스트리는 기동마다
pull + SIF 변환이 일어나고 그 캐시가 사용자 홈(NFS)에 쌓인다 — 운영 판단이 필요하다.
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
    #: 지금 실행할 수 있는가. 런처는 예정된 앱도 보여주되 고를 수 없게 한다.
    ready: bool = True


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
    InteractiveApp(
        id="jupyter",
        name="JupyterLab",
        description="노트북 세션",
        image="",
        fid="U-IA-01",
        ready=False,
    ),
    InteractiveApp(
        id="code-server",
        name="VS Code Server",
        description="웹 코드 편집",
        image="",
        fid="U-IA-03",
        ready=False,
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


def image_ref(repository: str | None, app_id: str) -> str:
    """저장소 + 앱 → apptainer에 넘길 이미지 참조.

    **제출 전에 막는다.** 저장소가 비었거나 아직 제공하지 않는 앱이면 Job은 워커까지
    간 뒤에 죽고, 사용자에게는 원인이 안 보인다.
    """
    app = get(app_id)
    if not app.ready or not app.image:
        raise ValidationFailed(
            f"'{app.name}'은(는) 아직 제공되지 않습니다.", detail={"app": app_id}
        )
    if not repository:
        raise ValidationFailed(
            "클러스터에 이미지 저장소가 설정되어 있지 않습니다.",
            detail={"field": "image_repository"},
        )
    return f"{repository.rstrip('/')}/{app.image}"
