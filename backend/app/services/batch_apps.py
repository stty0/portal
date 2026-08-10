"""Batch 앱(해석 solver) 카탈로그 (U-JB-13).

인터랙티브 앱(`session_apps.py`)과 **같은 모양**이다. 앱 목록이 코드에 있고, 이미지는
포털 공용 디렉터리(`settings.app_image_dir`) 아래에서 찾는다. 다른 점은 하나다 —
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
    #: 이 파라미터가 켜졌을 때만 실행한다(체크박스·값 있음). 비우면 항상 실행.
    when: str | None = None
    #: 반대로 이 파라미터가 꺼졌을 때만 실행한다. 직렬/병렬처럼 **둘 중 하나**인 갈래에 쓴다.
    unless: str | None = None


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
    #: 이미지의 **출처**(OCI 참조). 등록(`app_catalog.image_ref`)이 이기고 없으면 이 값이다 —
    #: `image`와 같은 모양이다. 이 SIF를 어떻게 만들었는지 아는 유일한 자리다.
    image_ref: str = ""
    #: 컨테이너에 넣을 환경변수(`--env K=V`). **라이선스 동의처럼 앱이 정하는 값**이지
    #: 사용자 입력이 아니다 — Isaac Sim은 `ACCEPT_EULA` 없이는 시작하지 않는다.
    env: tuple[tuple[str, str], ...] = ()
    #: **실행 방식**(기동 커맨드·파라미터)이 확정됐는가. 이미지가 거기 있는지는 별개
    #: 질문이고(`installed`, 클러스터가 답한다) 이 값은 코드가 답한다. 목록에는 예정
    #: 앱도 보여주되 고를 수 없게 한다.
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
#: OpenFOAM 이미지는 2026-08-08에 만들어 저장소에 넣었다(`openfoam-2512.sif`, 443MB,
#: `docker://opencfd/openfoam-default:2512` = ESI 계열, solver 139종).
#:
#: 아래 파라미터는 **추측이 아니라 실제 케이스(`pitzDaily`)를 돌려 보고 정했다.** 그때
#: 확인한 것들:
#:
#:   1. `foamDictionary <파일> -entry X -set V`로 케이스 설정을 고칠 수 있다. 그래서
#:      시간·저장 간격을 화면에서 받아 케이스에 **주입**한다.
#:   2. **격자 해상도는 이 방식으로 못 바꾼다.** `blockMeshDict`의 `blocks`가
#:      `( hex (...) (18 30 1) simpleGrading (...) )` 같은 **중첩 리스트**여서 단순
#:      치환 대상이 아니다. 격자는 케이스 파일이 정한다 — 포털은 `blockMesh` 실행
#:      여부만 다룬다.
#:   3. **튜토리얼 케이스에 `decomposeParDict`가 없는 경우가 흔하다**(pitzDaily가 그렇다).
#:      그래서 없으면 만들고, `numberOfSubdomains`를 **자원 칸의 랭크 수로 맞춘다**.
#:      `method scotch`는 계수 없이 임의 개수를 분해하므로 안전하다.
#:   4. **`writeInterval > endTime`이면 결과가 하나도 안 나온다.** 조용히 끝나고
#:      `reconstructPar`가 "No times selected"로 실패한다. 실제로 그렇게 당했다 —
#:      그래서 저장 간격을 화면에 노출하고 힌트로 경고한다.
APPS: tuple[BatchApp, ...] = (
    BatchApp(
        id="openfoam",
        name="OpenFOAM",
        description="전산유체역학 v2512 — 케이스를 풀고 결과를 ParaView로 본다",
        image="openfoam-2512.sif",
        image_ref="docker://opencfd/openfoam-default:2512",
        fid="U-JB-13",
        ready=True,
        params=(
            AppParam(
                key="case",
                label="케이스 디렉터리",
                type="path",
                hint="system/·constant/·0/ 이 들어 있는 폴더. **파일이 아니라 폴더**입니다.",
            ),
            AppParam(
                key="solver",
                label="Solver",
                type="select",
                default="simpleFoam",
                options=(
                    "simpleFoam", "pimpleFoam", "pisoFoam", "icoFoam", "potentialFoam",
                    "interFoam", "compressibleInterFoam", "multiphaseInterFoam",
                    "rhoSimpleFoam", "rhoPimpleFoam", "sonicFoam",
                    "buoyantSimpleFoam", "buoyantPimpleFoam", "chtMultiRegionFoam",
                    "scalarTransportFoam", "laplacianFoam", "XiFoam", "reactingFoam",
                ),
                hint="케이스의 물리에 맞는 solver. 이미지에 139종이 있고 대표만 골라 뒀습니다.",
            ),
            # --- 격자 -------------------------------------------------------
            AppParam(
                key="block_mesh",
                label="격자 생성 (blockMesh)",
                type="bool",
                default="1",
                required=False,
                hint="격자 **해상도는 system/blockMeshDict가 정합니다** — 여기서는 생성 여부만 고릅니다.",
            ),
            AppParam(
                key="check_mesh",
                label="격자 검사 (checkMesh)",
                type="bool",
                default="1",
                required=False,
                hint="나쁜 격자로 몇 시간 계산한 뒤 알게 되는 것보다 낫습니다.",
            ),
            # --- 시간 제어 (비우면 케이스 설정을 그대로 쓴다) ----------------
            AppParam(
                key="end_time",
                label="종료 시간 (endTime)",
                type="number",
                required=False,
                hint="비우면 케이스의 controlDict를 따릅니다.",
            ),
            AppParam(
                key="delta_t",
                label="시간 간격 (deltaT)",
                type="number",
                required=False,
                hint="비우면 케이스 설정.",
            ),
            AppParam(
                key="write_interval",
                label="결과 저장 간격 (writeInterval)",
                type="number",
                required=False,
                hint="⚠️ 종료 시간보다 크면 **결과가 하나도 저장되지 않습니다**(실측).",
            ),
            AppParam(
                key="restart",
                label="최신 시간부터 이어서 계산",
                type="bool",
                default="0",
                required=False,
                hint="켜면 startFrom=latestTime. 끄면 케이스 설정 그대로입니다.",
            ),
            # --- 병렬 -------------------------------------------------------
            AppParam(
                key="decompose",
                label="병렬 분해 (decomposePar)",
                type="bool",
                default="1",
                required=False,
                hint="끄면 단일 프로세스로 풉니다. 켜면 위 MPI 랭크 수로 분해합니다.",
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
            # --- 케이스 설정 주입 (빈 값은 단계 자체가 빠진다) ---------------
            AppStep(run="cd {{case}} && foamDictionary system/controlDict -entry endTime -set {{end_time}}",
                    when="end_time"),
            AppStep(run="cd {{case}} && foamDictionary system/controlDict -entry deltaT -set {{delta_t}}",
                    when="delta_t"),
            AppStep(run="cd {{case}} && foamDictionary system/controlDict -entry writeInterval -set {{write_interval}}",
                    when="write_interval"),
            AppStep(run="cd {{case}} && foamDictionary system/controlDict -entry startFrom -set latestTime",
                    when="restart"),
            # --- 격자 -------------------------------------------------------
            AppStep(run="cd {{case}} && blockMesh", when="block_mesh"),
            AppStep(run="cd {{case}} && checkMesh", when="check_mesh"),
            # --- 분해: 딕셔너리가 없는 케이스가 흔하므로 없으면 만든다 -------
            AppStep(
                run=(
                    # 역슬래시 이스케이프를 쓰지 않는다 — 여러 겹을 지나며 한 겹씩 잃는다.
                    # 실제로 printf "\\n" 판본이 스크립트를 줄바꿈으로 깨뜨렸다.
                    'D={{case}}/system/decomposeParDict; if [ ! -f "$D" ]; then '
                    '{ echo "FoamFile { version 2.0; format ascii; class dictionary; '
                    'object decomposeParDict; }"; '
                    'echo "numberOfSubdomains 1;"; '
                    'echo "method scotch;"; } > "$D"; fi'
                ),
                in_container=False,
                when="decompose",
            ),
            AppStep(
                run=(
                    "cd {{case}} && "
                    "foamDictionary system/decomposeParDict -entry numberOfSubdomains -set {{ntasks}} && "
                    "foamDictionary system/decomposeParDict -entry method -set scotch && "
                    "decomposePar -force"
                ),
                when="decompose",
            ),
            # --- 풀이: 분해했으면 병렬, 아니면 직렬 -------------------------
            AppStep(run="{{solver}} -case {{case}} -parallel", parallel=True, when="decompose"),
            AppStep(run="{{solver}} -case {{case}}", unless="decompose"),
            AppStep(run="cd {{case}} && reconstructPar", when="reconstruct"),
            # ParaView는 이 표식이 있어야 케이스를 연다. 없으면 결과가 다 나왔는데도
            # "안 열린다"가 된다 — 인터랙티브 앱으로 이어지는 고리의 마지막 한 칸이다.
            AppStep(run="touch {{case}}/case.foam", in_container=False),
        ),
    ),
    # --- Isaac Sim — 합성 데이터 생성(SDG) ---------------------------------
    #
    # **data factory 관점의 앱이다.** 물리를 푸는 solver가 아니라 학습 데이터를 찍어내는
    # 도구이고, 그래서 이 앱이 노리는 실행 형태는 하나다 —
    # *Replicator 스크립트 하나를 GPU 노드에서 헤드리스로 돌려 데이터셋을 디스크에 쌓는다.*
    #
    # ## 왜 파라미터가 둘뿐인가
    #
    # 표준 SDG 진입점은 `python.sh <스크립트> [--config <파일>]`이고, **프레임 수·해상도·
    # 출력 경로·렌더러는 전부 config 파일의 키다**(`num_frames`·`resolution`·`rt_subframes`·
    # `backend_params.output_dir`·`launch_config`). CLI 인자가 아니다 — 내장 예제
    # `scene_based_sdg.py`의 argparse에는 `--config` 하나뿐이다. 그러니 포털이 프레임 수
    # 칸을 만들어 봐야 넘길 자리가 없다. 값을 넣고 싶으면 config 파일을 고치는 것이 정본이고,
    # 포털은 그 파일을 가리키게만 한다.
    #
    # ## 샤딩은 포털이 규약을 만들지 않는다 (data factory의 핵심)
    #
    # 데이터셋 10만 장은 한 Job으로 찍지 않는다 — 배열 잡으로 쪼갠다. **Apptainer는 호스트
    # 환경변수를 컨테이너로 그대로 넘긴다(실측 2026-08-08).** 그래서 사용자의 SDG 스크립트가
    # `os.environ["SLURM_ARRAY_TASK_ID"]`를 읽어 시드와 출력 폴더를 가르면 그만이고,
    # 포털이 `--shard` 같은 인자 규약을 발명할 이유가 없다. 자원 칸의 **배열 인덱스**가
    # 그대로 샤딩 손잡이다.
    #
    # ## bind mount가 목록에 없는 이유 (문서의 가장 큰 불확실성이 하나 걷혔다)
    #
    # NVIDIA의 `docker run` 예시는 캐시 6개를 `/isaac-sim/...`에 마운트한다. Docker에서는
    # 그 경로가 컨테이너의 HOME(`/isaac-sim`, rootless uid 1234)이라 쓰기가 막히기 때문이다.
    # **Apptainer에서는 필요 없다 — 이미지에 `ENV HOME`이 박혀 있어도 Apptainer가 호출한
    # 사용자의 홈으로 덮어쓴다(실측 2026-08-08: `ENV HOME=/opt/fakehome` 이미지를 만들어
    # 확인 → 컨테이너 안에서 `HOME=/home/jrpark`).** 홈은 쓰기 가능하므로 Omniverse 캐시가
    # 자연히 홈에 쌓인다. 비공식 클러스터 가이드가 bind 없이 `--env ACCEPT_EULA=Y --nv`만으로
    # 도는 것과 일치한다.
    #
    # 대신 **홈에 캐시가 수~수십 GB씩 쌓인다**(gpu-simulation.md §4의 경고 그대로). 쿼터는
    # 운영 쪽 숙제다.
    #
    # ## 아직 실측이 아닌 것 — 그래서 ready=False
    #
    # **이미지가 없다는 것은 더 이상 이 플래그의 이유가 아니다** — 그건 클러스터를 보고
    # `installed`가 답한다. 남은 이유는 커맨드다. NVIDIA 문서와 비공식 클러스터 가이드에서
    # 가져온 것이고, **L40 노드가 들어와 SIF로 한 번 돌려 본 뒤에 확정해야 한다**
    # (gpu-simulation.md §8의 2단계). 특히 Kit이 `$HOME` 밖 절대경로(`/isaac-sim/kit/cache`
    # 등)에 쓰려 드는지가 남은 확인이다 — 그러면 그때 `binds`를 더한다.
    BatchApp(
        id="isaac-sim",
        name="Isaac Sim (합성 데이터)",
        description="Omniverse Replicator로 학습용 합성 데이터셋을 생성한다 — 배열 잡으로 샤딩",
        image="isaac-sim-5.1.0.sif",
        # nvcr.io는 익명 pull이 안 된다(NGC 계정 + API 키) — gpu-simulation.md §5.
        image_ref="docker://nvcr.io/nvidia/isaac-sim:5.1.0",
        fid="U-JB-13",
        needs_gpu=True,
        ready=False,
        # 없으면 Kit이 EULA를 물으며 멈춘다 — 배치에는 대답할 사람이 없다.
        env=(("ACCEPT_EULA", "Y"), ("PRIVACY_CONSENT", "Y")),
        params=(
            AppParam(
                key="script",
                label="SDG 스크립트",
                type="path",
                default="/isaac-sim/standalone_examples/replicator/scene_based_sdg/scene_based_sdg.py",
                hint=(
                    "Replicator standalone 파이썬 스크립트. 기본값은 **컨테이너에 들어 있는 "
                    "예제**이고, 직접 만든 스크립트는 홈 아래 경로로 지정합니다. "
                    "`SLURM_ARRAY_TASK_ID`를 읽어 샤드별로 시드·출력 폴더를 가르면 "
                    "배열 잡으로 데이터셋을 나눠 찍을 수 있습니다."
                ),
            ),
            AppParam(
                key="config",
                label="설정 파일 (--config)",
                type="path",
                required=False,
                hint=(
                    "프레임 수·해상도·출력 경로·렌더러는 **이 파일이 정합니다**(JSON/YAML). "
                    "⚠️ `launch_config.headless`가 반드시 `true`여야 합니다 — 배치 노드에는 "
                    "화면이 없습니다. 비우면 스크립트의 기본 설정을 씁니다."
                ),
            ),
        ),
        steps=(
            # `-u`: 버퍼링을 끈다. 켜 두면 Job이 끝날 때까지 로그가 한 줄도 안 보인다.
            AppStep(run="/isaac-sim/python.sh -u {{script}} --config {{config}}", when="config"),
            AppStep(run="/isaac-sim/python.sh -u {{script}}", unless="config"),
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
        if step.unless and _is_on(resolved, step.unless):
            continue
        run = _substitute(step.run, resolved, app.id)
        if step.in_container:
            flags = "--nv " if app.needs_gpu else ""
            flags += "".join(f"--env {shlex.quote(f'{k}={v}')} " for k, v in app.env)
            launcher = "srun " if step.parallel else ""
            lines.append(f"{launcher}apptainer exec {flags}{shlex.quote(image)} bash -lc {shlex.quote(run)}")
        else:
            lines.append(run)
    return "\n".join(lines)
