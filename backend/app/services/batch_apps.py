"""Batch 앱(해석 solver) 카탈로그 (U-JB-13).

인터랙티브 앱(`session_apps.py`)과 **같은 모양**이다. 앱 목록이 코드에 있고, 이미지는
클러스터 저장소(`cluster.image_repository`) 아래에서 찾는다. 다른 점은 하나다 —
**앱마다 해석 입력값이 다르므로 파라미터 스키마를 함께 둔다.**

## 왜 DB가 아니라 코드인가

2026-08-07에 `job_template` 표를 지웠다. 그 표에는 `params.script` 문자열과 `{{key}}`
치환만 있었고, **solver 이미지도 입력 인터페이스도 없었다** — 관리자가 등록해도 되는 일이
없었다. 되살리는 지금은 세 가지가 한 몸이어야 한다:

    이미지  +  실행 커맨드  +  파라미터 스키마

이 셋은 함께 바뀐다. 커맨드를 고치면 파라미터가 따라 바뀌고, 이미지를 올리면 둘 다 바뀐다.
DB에 넣으면 코드 배포와 데이터가 따로 놀아 **화면은 새 필드를 묻는데 이미지는 옛 커맨드**인
상태가 생긴다.

## 파라미터에 자유 서식이 없는 이유

`{{key}}` 치환은 `job_template`과 같아 보이지만, **치환 대상이 사용자 입력이 아니다.**
커맨드 틀은 여기 코드에 있고 사용자는 값만 넣는다. 그래서 임의 명령 주입이 성립하지
않는다(값은 `shlex.quote`로 감싼다).
"""

from __future__ import annotations

import re
import shlex
from dataclasses import dataclass

from app.core.errors import ValidationFailed

#: 치환되지 않고 남은 자리표시자. 그대로 실리면 워커에서 `{{case}}`가 인자로 들어가
#: 조용히 엉뚱하게 돈다 — 제출 전에 막는다.
_PLACEHOLDER = re.compile(r"\{\{\s*([A-Za-z0-9_]+)\s*\}\}")


@dataclass(frozen=True)
class AppParam:
    """해석 입력값 하나."""

    key: str
    label: str
    #: `text` · `number` · `path`(홈 하위 경로) · `select`
    type: str = "text"
    required: bool = True
    default: str | None = None
    hint: str = ""
    #: `select`일 때의 선택지.
    options: tuple[str, ...] = ()


@dataclass(frozen=True)
class BatchApp:
    id: str
    name: str
    description: str
    #: 저장소 아래의 이미지 이름(SIF 파일명 또는 레지스트리 태그). 준비 전이면 빈 값.
    image: str
    fid: str
    #: 컨테이너 안에서 실행할 커맨드 틀. `{{key}}`가 파라미터로 치환된다.
    command: str
    params: tuple[AppParam, ...] = ()
    #: GPU를 쓰는 앱이면 `apptainer exec --nv`가 붙는다.
    needs_gpu: bool = False
    #: 지금 실행할 수 있는가. 목록에는 예정 앱도 보여주되 고를 수 없게 한다.
    ready: bool = True


#: 앱 목록의 **단일 출처**. 화면이 따로 갖고 있으면 실행 가능한 앱이 무엇인지에 대해
#: 앞뒤가 갈린다(인터랙티브 앱과 같은 원칙).
#:
#: **지금은 전부 `ready=False`다.** 이미지가 아직 없다. 실제 이미지가 준비되면
#: `image`를 채우고 `ready=True`로 바꾸면 되고, 그때 커맨드·파라미터를 **실측으로**
#: 맞춰야 한다 — 손으로 한 번 돌려보기 전에 폼을 확정하면 `job_template`을 다시 만든다.
APPS: tuple[BatchApp, ...] = (
    BatchApp(
        id="gromacs",
        name="GROMACS",
        description="분자동역학 — mdrun",
        image="",
        fid="U-JB-13",
        needs_gpu=True,
        ready=False,
        command="gmx mdrun -s {{tpr}} -deffnm {{prefix}} -nsteps {{nsteps}}",
        params=(
            AppParam(
                key="tpr",
                label="입력 파일 (.tpr)",
                type="path",
                hint="홈 하위 경로. 파일 관리자나 scp로 미리 올려 두세요.",
            ),
            AppParam(
                key="prefix",
                label="출력 이름",
                default="md",
                hint="결과 파일 접두사 (md.log, md.xtc …)",
            ),
            AppParam(
                key="nsteps",
                label="스텝 수",
                type="number",
                default="-1",
                required=False,
                hint="-1이면 입력 파일의 설정을 따릅니다.",
            ),
        ),
    ),
)


def get(app_id: str) -> BatchApp:
    for app in APPS:
        if app.id == app_id:
            return app
    raise ValidationFailed(
        "지원하지 않는 앱입니다.",
        detail={"app": app_id, "supported": [a.id for a in APPS]},
    )


def image_ref(repository: str | None, app: BatchApp) -> str:
    """저장소 + 앱 → apptainer에 넘길 이미지 참조.

    **제출 전에 막는다.** 저장소가 비었거나 아직 제공하지 않는 앱이면 Job은 워커까지 간
    뒤에 죽고, 사용자에게는 원인이 안 보인다(인터랙티브 앱과 같은 판단).
    """
    if not app.ready or not app.image:
        raise ValidationFailed(
            f"'{app.name}'은(는) 아직 제공되지 않습니다.", detail={"app": app.id}
        )
    if not repository:
        raise ValidationFailed(
            "클러스터에 이미지 저장소가 설정되어 있지 않습니다.",
            detail={"field": "image_repository"},
        )
    return f"{repository.rstrip('/')}/{app.image}"


def render_command(app: BatchApp, values: dict[str, str]) -> str:
    """파라미터 → 실행 커맨드.

    값은 **모두 `shlex.quote`로 감싼다.** 공백이 든 경로 때문이기도 하고, 값에 `;`나
    `$(…)`가 들어와도 명령이 되지 않게 하기 위해서다.
    """
    rendered = app.command
    for param in app.params:
        raw = (values.get(param.key) or "").strip()
        if not raw:
            if param.required and not param.default:
                raise ValidationFailed(
                    f"'{param.label}'은(는) 필수입니다.", detail={"param": param.key}
                )
            raw = param.default or ""
        if param.type == "number" and raw:
            try:
                float(raw)
            except ValueError:
                raise ValidationFailed(
                    f"'{param.label}'은(는) 숫자여야 합니다.",
                    detail={"param": param.key, "value": raw},
                ) from None
        if param.type == "path" and raw:
            # 절대 경로 + `..` 금지. 폼이 홈 하위만 만들지만 API를 직접 부르는 길도
            # 있으므로 서버에서도 막는다(`JobSubmitRequest.work_dir`와 같은 규칙).
            # 실제 접근 권한은 Job이 **본인 권한으로** 돌기 때문에 OS가 판정한다 —
            # 여기서는 오타·경로 조작으로 엉뚱한 곳을 읽는 것을 걸러낸다.
            if not raw.startswith("/"):
                raise ValidationFailed(
                    f"'{param.label}'은(는) 절대 경로여야 합니다.",
                    detail={"param": param.key, "value": raw},
                )
            if ".." in raw.split("/"):
                raise ValidationFailed(
                    f"'{param.label}'에 상위 경로(..)를 쓸 수 없습니다.",
                    detail={"param": param.key},
                )
        if param.options and raw and raw not in param.options:
            raise ValidationFailed(
                f"'{param.label}'의 값이 올바르지 않습니다.",
                detail={"param": param.key, "allowed": list(param.options)},
            )
        rendered = rendered.replace("{{%s}}" % param.key, shlex.quote(raw) if raw else "")

    missing = sorted(set(_PLACEHOLDER.findall(rendered)))
    if missing:
        # 카탈로그의 커맨드와 파라미터 목록이 어긋난 것이다 — 사용자 잘못이 아니다.
        raise ValidationFailed(
            f"앱 정의에 채우지 못한 값이 있습니다: {', '.join(missing)}",
            detail={"app": app.id, "missing": missing},
        )
    return " ".join(rendered.split())


def build_body(app: BatchApp, image: str, values: dict[str, str]) -> str:
    """컨테이너 실행 본문. 폼 모드가 이 위에 `#SBATCH`를 얹는다."""
    flags = "--nv " if app.needs_gpu else ""
    return f"apptainer exec {flags}{shlex.quote(image)} {render_command(app, values)}"
