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
class AppStep:
    """실행 단계 하나.

    solver 하나가 명령 하나로 끝나지 않는다. OpenFOAM은 **분해 → 풀이 → 재조합**이고,
    단계마다 컨테이너 안/밖과 병렬 여부가 다르다. 그래서 단계를 목록으로 둔다.
    """

    run: str
    #: `srun`으로 띄운다(MPI). Slurm이 랭크를 만들고 컨테이너는 랭크 하나씩 실행한다 —
    #: 컨테이너 안에서 `mpirun`을 부르면 호스트 Slurm이 랭크를 모른다.
    parallel: bool = False
    #: 컨테이너 안에서 실행하는가. `touch`처럼 호스트에서 해도 되는 일은 밖에서 한다.
    in_container: bool = True
    #: 이 파라미터가 켜졌을 때만 실행한다(체크박스). 비우면 항상 실행.
    when: str | None = None


@dataclass(frozen=True)
class BatchApp:
    id: str
    name: str
    description: str
    #: 저장소 아래의 이미지 이름(SIF 파일명 또는 레지스트리 태그). 준비 전이면 빈 값.
    image: str
    fid: str
    #: 실행 단계. `{{key}}`가 파라미터로 치환된다.
    steps: tuple[AppStep, ...]
    params: tuple[AppParam, ...] = ()
    #: GPU를 쓰는 앱이면 `apptainer exec --nv`가 붙는다.
    needs_gpu: bool = False
    #: 지금 실행할 수 있는가. 목록에는 예정 앱도 보여주되 고를 수 없게 한다.
    ready: bool = True


#: 앱 목록의 **단일 출처**. 화면이 따로 갖고 있으면 실행 가능한 앱이 무엇인지에 대해
#: 앞뒤가 갈린다(인터랙티브 앱과 같은 원칙).
#:
#: OpenFOAM 이미지는 2026-08-08에 만들어 저장소에 넣었다(`openfoam-2512.sif`, 443MB,
#: `docker://opencfd/openfoam-default:2512`). 이미지 안에 solver 5종과 `decomposePar`·
#: `reconstructPar`가 있는 것을 실행으로 확인했다.
#:
#: **다만 커맨드·파라미터는 아직 실측이 아니다.** 실제 케이스로 한 번 돌려보고 맞춰야
#: 한다 — 폼을 확정하기 전에 돌려보지 않으면 `job_template`을 다시 만드는 것과 같다.
APPS: tuple[BatchApp, ...] = (
    BatchApp(
        id="openfoam",
        name="OpenFOAM",
        description="전산유체역학 v2512 — 케이스를 풀고 결과를 ParaView로 본다",
        image="openfoam-2512.sif",
        fid="U-JB-13",
        ready=True,
        params=(
            AppParam(
                key="case",
                label="케이스 디렉터리",
                type="path",
                hint="system/·constant/·0/ 이 들어 있는 폴더. **파일이 아니라 폴더**다.",
            ),
            AppParam(
                key="solver",
                label="Solver",
                type="select",
                default="simpleFoam",
                options=("simpleFoam", "pimpleFoam", "interFoam", "rhoPimpleFoam", "potentialFoam"),
                hint="케이스에 맞는 solver를 고르세요.",
            ),
            AppParam(
                key="decompose",
                label="도메인 분해 (decomposePar)",
                type="bool",
                default="1",
                required=False,
                hint="병렬 실행에 필요합니다. 이미 분해했다면 끄세요.",
            ),
            AppParam(
                key="reconstruct",
                label="결과 재조합 (reconstructPar)",
                type="bool",
                default="1",
                required=False,
                hint="끄면 ParaView가 분해된 상태(processor*)로 읽습니다.",
            ),
        ),
        steps=(
            AppStep(run="cd {{case}} && decomposePar -force", when="decompose"),
            # **랭크 수가 안 맞으면 MPI가 조용히 이상하게 돈다.** decomposeParDict의
            # numberOfSubdomains는 케이스 파일 안에 있어 화면에서 보이지 않으므로,
            # 여기서 세어 보고 다르면 **원인을 적어** 멈춘다.
            AppStep(
                run=(
                    'n=$(ls -d {{case}}/processor* 2>/dev/null | wc -l); '
                    'if [ "$n" -ne {{ntasks}} ]; then '
                    'echo "분해 수($n)와 요청 랭크({{ntasks}})가 다릅니다 — '
                    'system/decomposeParDict의 numberOfSubdomains를 맞추세요"; exit 1; fi'
                ),
                in_container=False,
                when="decompose",
            ),
            AppStep(run="{{solver}} -case {{case}} -parallel", parallel=True),
            AppStep(run="cd {{case}} && reconstructPar", when="reconstruct"),
            # ParaView는 이 표식이 있어야 케이스를 연다. 없으면 결과가 다 나왔는데도
            # "안 열린다"가 된다 — 인터랙티브 앱으로 이어지는 고리의 마지막 한 칸이다.
            AppStep(run="touch {{case}}/case.foam", in_container=False),
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


def _resolved(app: BatchApp, values: dict[str, str]) -> dict[str, str]:
    """파라미터 검사 + 기본값 채우기. 값은 **전부 `shlex.quote`로 감싼다.**

    공백이 든 경로 때문이기도 하고, 값에 `;`나 `$(…)`가 들어와도 명령이 되지 않게
    하기 위해서다. 커맨드 틀은 이 카탈로그에 있고 사용자는 값만 넣는다.
    """
    out: dict[str, str] = {}
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
            # 실제 접근 권한은 Job이 **본인 권한으로** 돌기 때문에 OS가 판정한다.
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
        out[param.key] = shlex.quote(raw) if raw else ""
    return out


def _is_on(values: dict[str, str], key: str) -> bool:
    """체크박스 판정. `_resolved`가 인용한 값이 들어오므로 따옴표를 벗겨 본다."""
    return values.get(key, "").strip("'\"") not in ("", "0", "false", "False")


def _substitute(text: str, values: dict[str, str], app_id: str) -> str:
    for key, value in values.items():
        text = text.replace("{{%s}}" % key, value)
    missing = sorted(set(_PLACEHOLDER.findall(text)))
    if missing:
        # 카탈로그의 커맨드와 파라미터 목록이 어긋난 것이다 — 사용자 잘못이 아니다.
        raise ValidationFailed(
            f"앱 정의에 채우지 못한 값이 있습니다: {', '.join(missing)}",
            detail={"app": app_id, "missing": missing},
        )
    return text


def build_body(
    app: BatchApp, image: str, values: dict[str, str], *, ntasks: int | None = None
) -> str:
    """실행 본문(여러 줄). 폼 모드가 이 위에 `#SBATCH`를 얹는다.

    `ntasks`는 파라미터가 아니라 **자원 입력에서 온다** — MPI 랭크 수는 사용자가 자원
    칸에 넣은 값이 정본이고, 앱은 그것을 참조만 한다.
    """
    resolved = _resolved(app, values)
    resolved["ntasks"] = str(ntasks or 1)

    lines = ["set -euo pipefail"]
    for step in app.steps:
        if step.when and not _is_on(resolved, step.when):
            continue
        run = _substitute(step.run, resolved, app.id)
        if step.in_container:
            flags = "--nv " if app.needs_gpu else ""
            launcher = "srun " if step.parallel else ""
            lines.append(f"{launcher}apptainer exec {flags}{shlex.quote(image)} bash -lc {shlex.quote(run)}")
        else:
            lines.append(run)
    return "\n".join(lines)
