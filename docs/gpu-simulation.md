# GPU 시뮬레이션·렌더링 도입 (Isaac Sim / Omniverse) — 결정 기록

작성 2026-08-08 · 대상 U-JB-01·02(Job 제출), A-ND(파티션), 향후 solver 카탈로그

> **결론**: 이 포털은 **Isaac Sim을 배치 solver로만** 제공한다. 화면(GUI·스트리밍)은
> 포털이 하지 않고, Omniverse/Nucleus는 **별도 k8s**에 두며 두 시스템을 **묶지 않는다**
> (데이터는 사람이 복사한다).
>
> **포털 쪽 1단계(GPU 요청·배열 잡·의존성)는 2026-08-08 구현·배포했다.** 나머지는 결정과
> 근거의 기록이며 장비 도입 후 진행한다.

---

## 1. 확정된 구성

| 영역 | 결정 | 근거 |
|---|---|---|
| Omniverse + Nucleus | **별도 k8s** | 상시 서비스라 배치 스케줄러와 성격이 다르다 |
| Isaac Sim | **포털의 배치 solver 전용** | GUI를 포털이 중계하면 프록시·GL 문제가 따라온다 |
| 사용자 접점 | local workstation — WebRTC로 k8s에, CLI/API로 포털에 | 화면은 사용자 기계가 담당 |
| 데이터 | **공유하지 않는다. 복사한다** | §5 참조 |
| 파이프라인 | Slurm 배열·의존성 + 필요시 Snakemake | 엔진을 직접 만들지 않는다 |

```
[local workstation]  ──WebRTC──→  [k8s: Omniverse + Nucleus]   (별개 시스템)
        │
        │ 파일 복사 (scp/rsync · 포털 파일 관리자 U-FM-02)
        ↓
[이 포털] ──slurmrestd──→ [Slurm: viz=L40 / gpu=A100] → Isaac Sim SIF (배치)
                                                        결과는 홈 디렉터리로
```

---

## 2. 제품 지형 — 무엇이 필요하고 무엇이 아닌가

**Isaac Sim은 Omniverse Kit 위에 만들어진 앱이다.** RTX 렌더러·USD·PhysX가 그 컨테이너 안에
들어 있다. 시뮬레이션과 렌더링에 **필요한 것은 Isaac Sim 이미지 하나**이고, "Omniverse를 따로
설치"하는 단계가 없다.

| 구성요소 | 이 프로젝트에서 |
|---|---|
| Isaac Sim (`nvcr.io/nvidia/isaac-sim`) | **필요.** 시뮬레이션·렌더링 모두 여기서 |
| Omniverse Kit SDK | Isaac Sim에 **포함** — 따로 받지 않는다 |
| Nucleus (에셋 서버) | **별도 k8s.** 협업·버전 관리용. HPC로 갈 자산은 복사한다 |
| Kit App Streaming | **미채택.** 화면은 사용자 workstation이 담당 |
| 렌더 팜 오케스트레이터 | **채택 금지.** Slurm과 정면으로 겹친다 (§6) |

---

## 3. GPU 선택 — RT 코어가 갈림길

**A100·H100·H200은 Isaac Sim이 공식 미지원이다.** 연산 성능과 무관하게 **RT 코어가 없어서**다 —
Omniverse RTX 렌더러가 하드웨어 레이트레이싱을 전제한다.

| 용도 | GPU |
|---|---|
| Isaac Sim / 렌더링 | **L40 · L40S · RTX 6000 Ada · RTX PRO 6000** (48GB급) |
| 학습·HPC 연산 | A100 / H100 / H200 |

검토 중인 구성은 **L40 1노드 + A100 1노드**다.

### 파티션 분리는 선택이 아니라 필수다

포털의 GPU 판별(`gpu_partitions`)은 노드 `gres`를 보고 **"이 파티션에 GPU가 있다/없다"만**
말한다. **종류를 구분하지 못한다.** 두 노드를 한 파티션에 넣으면 사용자가 GPU를 요청했다가
A100에 배정돼 Isaac Sim이 실패한다 — 화면에는 "GPU 있음"이라고 뜬 채로.

```
NodeName=viz01     Gres=gpu:l40:1
NodeName=compute01 Gres=gpu:a100:N
PartitionName=viz  Nodes=viz01        # Isaac Sim
PartitionName=gpu  Nodes=compute01    # 학습·연산
```

**파티션 이름이 지금 구조에서 GPU 종류를 표현하는 유일한 수단이다.**

L40 1장 = **Isaac Sim 세션/Job 1개**(Slurm이 `gres=gpu:1`을 통째로 준다). 동시 사용자가
여럿이면 부족하다.

---

## 4. 이미지 반입

`nvcr.io`는 익명 pull이 안 된다(NGC 계정 + API 키). 그런데 클러스터 설정에 **레지스트리
자격증명 자리가 없다.** 개발 단계에는 자격증명이 있는 기계에서 받아 SIF로 넣는다 —
`app_image_dir`가 경로 접두사라 **포털 변경이 필요 없다** — 이미지 파일을 넣고 앱 관리에서 고르면 된다.

```bash
docker login nvcr.io                      # Username: $oauthtoken / Password: NGC API key
docker pull nvcr.io/nvidia/isaac-sim:5.1.0

export APPTAINER_TMPDIR=/home/apptainer/tmp      # 둘 다 /home 아래로!
export APPTAINER_CACHEDIR=/home/apptainer/cache
apptainer build /home/images/isaac-sim-5.1.0.sif docker-daemon://nvcr.io/nvidia/isaac-sim:5.1.0
```

**변환 중 순간 사용량이 최종 SIF보다 훨씬 크다(이미지의 3~4배).** tmpdir이 `/home` 밖이면
용량과 무관하게 터진다 — 전에 dev01이 DiskPressure에 걸려 포털 pod이 evict된 사고가 바로
이 경우다(progress.md 참조).

> **남은 최대 불확실성은 포털이 아니라 Apptainer 패키징이다.** NVIDIA가 지원하는 것은
> Docker이고, **SIF는 읽기 전용인데 Isaac Sim은 `~/.cache/ov`·셰이더 캐시·Kit 캐시에 계속
> 쓴다.** bind mount를 잡아야 하고, 5.1의 rootless 전제와 맞물려 권한 문제가 난다.
>
> **장비 발주 전에 SIF 빌드만 먼저 해보라** — 빌드에는 GPU가 필요 없다. 실제 용량과 변환
> 가능 여부라는 가장 큰 불확실성을 가장 싸게 걷어낸다.

용량 계획: 1TB면 이미지 보관은 충분하다. 진짜 변수는 두 가지다 — **변환 중 순간 사용량**과
**사용자별 Omniverse 캐시**(`~/.cache/ov`, 셰이더 캐시가 사람마다 수~수십 GB씩 홈에 쌓인다).
이미지 저장소와 빌드 스크래치를 분리하고 홈에 쿼터를 걸어야 한다. SIF를 NFS에서 직접
실행하면 시작이 느리므로 노드 로컬 복사도 검토한다.

---

## 5. 데이터를 공유하지 않기로 한 이유 (한 번 뒤집힌 결정)

처음에는 홈 NFS를 k8s 노드에 마운트해 공유하는 안을 검토했다. **철회했다.**

- **UID/GID 정합** — Slurm 노드는 AD/SSSD uid를 쓰는데 k8s 파드가 다른 uid로 뜨면 소유권이
  어긋난다. 사용자마다 파드 uid를 동적으로 맞춰야 한다. 이 구성에서 가장 손이 많이 간다.
- **격리 약화** — k8s 노드에 홈 전체를 마운트하면 그 노드의 파드가 남의 홈까지 본다.
- **Nucleus는 파일시스템이 아니다** — 자체 저장소에 `omniverse://`로 접근한다. NFS를 공유해도
  **Nucleus 안의 에셋은 홈에 보이지 않는다.** 공유의 이득이 기대만큼 크지 않다.
- **장애 전파** — 묶으면 한쪽 스토리지 문제가 양쪽을 멈춘다.

복사 수단은 **이미 있다**(파일 관리자 U-FM-02, 로그인 노드 scp/rsync). 복사가 실제로
아파지면 그때 공유 스토리지를 검토한다. **지금 안 묶는 쪽이 선택지를 남긴다.**

---

## 6. 파이프라인 — 엔진을 만들지 않는다

시뮬레이션 → 렌더링(프레임 N장) → 재조합은 3단계 파이프라인이다. **배열 잡과 파이프라인은
다르다.**

| | 하는 일 |
|---|---|
| **배열 잡** `--array` | 독립 작업 N개를 팬아웃. **순서 없음** |
| **의존성** `--dependency` | 앞이 끝나야 다음 시작. ← 이것이 파이프라인 |

```bash
SIM=$(sbatch --parsable sim.sh)
RENDER=$(sbatch --parsable --dependency=afterok:$SIM --array=1-240 render.sh)
sbatch --dependency=afterok:$RENDER composite.sh
```

`afterok`(성공 시), `afterany`, `afternotok`(실패 시 — 정리·알림), `aftercorr`(배열 대 배열,
같은 인덱스끼리 — 프레임별 후처리).

**Slurm은 워크플로 엔진이 아니다.** 재시도 정책·DAG 시각화·조건 분기·실패 지점 재개가 없다.
그 위가 필요해지면 **Snakemake**를 얹는다 — Python이고, `snakemake-executor-plugin-slurm`으로
Slurm에 제출하며, 규칙별 `container:`로 Apptainer(SIF)를 지원한다(`--sdm apptainer`).
입력·출력 관계에서 DAG를 스스로 만들므로 의존성을 손으로 쓰지 않는다.

대안: Parsl(Python 함수 중심), submitit(얇은 sbatch 래퍼), dask-jobqueue(Python 데이터 처리),
Nextflow(널리 쓰이지만 Groovy). Airflow/Prefect는 서버가 필요해 이 규모엔 과하다.

**포털은 파이프라인을 알 필요가 없다.** Snakemake는 드라이버 Job 안에서 스스로 `sbatch`를
부른다 — DAG UI를 만들지 않는다. 다만 자식 Job은 포털을 거치지 않으므로 **감사 로그에
드라이버 1건만 남는다.** 드라이버는 컨테이너 밖(호스트)에서 돌리고 각 규칙만 SIF를 쓰는
구성이 간단하다(컨테이너 안에서 돌리면 Slurm 명령·라이브러리를 bind mount 해야 한다).

---

## 7. 포털에 필요한 개발

| # | 항목 | 없으면 생기는 일 | 시점 |
|---|---|---|---|
| 1 | ~~GPU 요청~~ — `tres_per_node` | GPU 노드를 사도 Job이 GPU를 요청하지 않는다 | **2026-08-08 완료** |
| 2 | ~~배열 잡~~ — `array` | 240 프레임 렌더를 냈는데 **1장만 나온다** | **2026-08-08 완료** |
| 3 | ~~의존성~~ — `dependency` | 단계가 이어지지 않는다 | **2026-08-08 완료** |
| 4 | ~~사용자 API 토큰~~ | 외부 자동화가 AD 비밀번호를 스크립트에 박아야 한다 | **2026-08-08 완료** |

1~3은 전부 `#SBATCH` 지시자가 `ignored_directives`로 빠지는 형태로 드러났다 — 스크립트 모드를
고치며 넣은 그 경고가 아니었으면 원인을 한참 찾았을 것들이다.

### 실측이 남은 부분

v0.0.43 `job_desc_msg`에서 확인된 후보(2026-08-08 실측):

```
cpus_per_tres  memory_per_tres  tres_bind  tres_freq
tres_per_job   tres_per_node    tres_per_socket  tres_per_task   ntasks_per_tres
```

`--gres=gpu:N` ↔ **`tres_per_node`**가 대응한다(`build_script`가 만드는 `#SBATCH --gres`와 같은
의미라 미리보기와 실제 적용이 어긋나지 않는다).

**문자열 형식은 실측으로 확정했다(2026-08-08).** GPU가 없는 클러스터에서도 **에러 번호가
갈려** 구분됐다 — 세 후보를 실제로 제출해 봤다:

| 보낸 값 | 에러 | 해석 |
|---|---|---|
| `gpu:1` | **2115** `Invalid Trackable RESource (TRES) specification` | TRES 파서가 못 알아봄 |
| `gres:gpu:1` | **2072** `Invalid generic resource (gres) specification` | **gres 파서까지 도달**, `gpu` 자원이 없을 뿐 |
| `gres/gpu:1` | 2072 | 위와 동일 |

`--gres=gpu:N`이 노리는 gres 경로에 닿는 것은 **`gres:` 접두사 형식**이다(`sbatch --gres=gpu:N`도
`TresPerNode=gres:gpu:N`으로 남긴다). 그래서 `gres_gpu()`가 `gres:gpu:N`을 만든다.

> **남은 확인**: 지금은 "형식이 맞다"까지만 확인됐다. **실제로 GPU가 할당되는지는 L40 노드가
> 들어온 뒤 성공 제출로 재확인해야 한다.** 2072와 2115가 갈린 이유가 "형식 차이"가 아니라
> "이 클러스터에 gres/gpu TRES 자체가 정의돼 있지 않아서"일 가능성도 완전히 배제하지는
> 못했다.

지시자 → 필드 매핑(구현됨):

| `#SBATCH` | REST 필드 |
|---|---|
| `--gres=gpu:N` · `--gpus-per-node=N` | `tres_per_node` |
| `--gpus=N` | `tres_per_job` |
| `--gpus-per-task=N` | `tres_per_task` |
| `--array=1-240%4` | `array` |
| `--dependency=afterok:123` | `dependency` |

`--gres`는 `gpu` 외의 자원(license·mps 등)도 받는다. 포털이 옮기는 것은 **gpu뿐**이고,
나머지는 추측하지 않고 `ignored_directives`로 알린다.

### 외부 API 제출은 이미 된다

`POST /auth/login`(AD 계정) → Bearer 토큰 → `POST /clusters/{cid}/jobs`. **오늘도 동작한다.**
다만 정착시키면 안 된다 — AD 비밀번호가 스크립트에 박히고, 자동화가 반복 실패하면 **AD 계정이
잠긴다**. 액세스 토큰은 2026-08-08부터 **30분**이라 장시간 작업은 `POST /auth/refresh`로
갱신해야 한다(refresh 2주, 회전). **2026-08-08부터는 API 토큰을 쓴다** — 화면(`/api-tokens`)에서 발급하고,
`Authorization: Bearer hpcp_…`로 보낸다. 장수명이고 폐기가 즉시 먹으며, 권한은 소유자의
역할을 그대로 따른다("대상 사용자는 언제나 요청자 본인" 규칙과 충돌하지 않는다).

---

## 8. 진행 순서 — solver 카탈로그를 먼저 설계하지 않는다

**1단계 — 2026-08-08 완료.** 1~3번을 고쳤다. 이제 스크립트 모드로 Isaac Sim이 돈다:

```bash
#!/bin/bash
#SBATCH --partition=viz
#SBATCH --gres=gpu:1
#SBATCH --array=1-240
apptainer exec --nv --env ACCEPT_EULA=Y /home/portal/images/isaac-sim-5.1.0.sif \
  /isaac-sim/python.sh -u sdg.py --config shard.yaml
```

> 이 예시는 2026-08-08에 §8-1의 실측으로 고쳤다. 원래는
> `-B $HOME/.cache/ov:/root/.cache/ov`가 붙어 있었는데 **그 경로는 Isaac Sim 4.x의 것이고**
> (5.1은 rootless라 캐시가 `/isaac-sim/` 아래다), Apptainer에서는 애초에 bind가 필요 없다.

**2단계 (L40 도입 후)** — 위 스크립트를 **손으로 한 번 돌린다.** 여기서 bind mount가 몇 개
필요한지, Isaac Sim이 실제로 받는 인자가 무엇인지, **사용자가 매번 바꾸는 값이 무엇인지**를
알게 된다.

**3단계 — 골격은 2026-08-08 완료.** `batch_apps.py`에 카탈로그·파라미터 스키마·제출 경로를
만들었고 화면은 `/batch-apps`(SCR-21)다. 인터랙티브 앱 카탈로그와 같은 모양이며 **이미지·실행
커맨드·파라미터가 한 몸**이다.

**카탈로그 상태(2026-08-08 기준)**: OpenFOAM은 `ready=True`다 — 이미지를 만들고
실제 케이스(`pitzDaily`)를 돌려 파라미터를 확정했다. Isaac Sim은 `ready=False`다(§8-1).
2단계(손으로 한 번 돌려보기)를 건너뛰고 카탈로그를 확정하면 `job_template`을 다시 만드는 것과 같다.

> **2단계를 건너뛰고 3단계를 설계하면 2026-08-07에 지운 `job_template` 표를 다시 만들게 된다.**
> 그 표가 지워진 이유가 정확히 "solver 컨테이너 이미지도, 입력 인터페이스도 없이 만들어졌기
> 때문"이다. 무엇을 입력받아야 하는지 모르는 채로 만든 폼이었다.

solver 카탈로그가 더하는 것은 "SIF 경로와 `--nv`, bind mount를 사용자가 몰라도 되게 하는 것"
— **편의이지 능력이 아니다.** 1단계만으로 실행은 가능하다.

---

## 8-1. Batch 앱에 Isaac Sim을 넣었다 — data factory용 (2026-08-08)

`batch_apps.py`에 `isaac-sim` 항목을 더했다. **`ready=False`다** — 이미지도 GPU 노드도 없다.
아래는 넣기 전에 조사·실측한 것과, 그 결과 카탈로그가 왜 이 모양인지에 대한 기록이다.

### Apptainer에서는 bind mount가 필요 없다 (§4의 최대 불확실성이 하나 걷혔다)

§4는 "SIF는 읽기 전용인데 Isaac Sim은 캐시에 계속 쓴다 — bind mount를 잡아야 한다"를
남은 최대 위험으로 적었다. **적어도 캐시 경로 문제는 Apptainer에서 성립하지 않는다.**

NVIDIA의 `docker run` 예시가 캐시 6개를 마운트하는 이유는 5.1 컨테이너가 **rootless(uid
1234)이고 그 HOME이 `/isaac-sim`** 이기 때문이다 — 즉 컨테이너 HOME이 이미지 안에 있어서
쓰기가 막힌다. Apptainer는 사정이 다르다:

```bash
# 실측 2026-08-08 — ENV HOME=/opt/fakehome 을 박은 이미지를 만들어 SIF로 변환
$ apptainer exec test.sif sh -lc 'echo $HOME'
HOME=/home/jrpark        # ← 이미지의 ENV HOME이 아니라 호출한 사용자의 홈
```

**Apptainer가 이미지의 `ENV HOME`을 사용자 홈으로 덮어쓴다.** 홈은 쓰기 가능하므로
Omniverse 캐시·로그·데이터가 자연히 홈에 떨어진다. 비공식 클러스터 가이드가 bind 없이
`--env ACCEPT_EULA=Y --nv`만으로 도는 것과 일치한다.

그래서 카탈로그에 `binds`를 넣지 않았다. **대가는 §4가 이미 경고한 그것이다** — 캐시가
사용자 홈에 수~수십 GB씩 쌓인다. 홈 쿼터는 운영 쪽 숙제로 남는다.

> **남은 확인**: Kit이 `$HOME` 밖 절대경로(`/isaac-sim/kit/cache` 등)에도 쓰려 드는지는
> 실제 이미지로만 알 수 있다. 그러면 그때 `binds`를 더한다 — 이번에 `BatchApp`에 `env`를
> 더한 것과 같은 크기의 변경이다.

### 파라미터가 둘뿐인 이유 — 프레임 수는 CLI 인자가 아니다

표준 SDG 진입점은 `python.sh <스크립트> [--config <파일>]`이다. 내장 예제
`scene_based_sdg.py`의 argparse에는 **`--config` 하나뿐이고**, 프레임 수·해상도·출력
경로·렌더러·헤드리스는 전부 config 파일의 키다:

```python
config = {
    "launch_config": {"renderer": "RealTimePathTracing", "headless": False},
    "resolution": [512, 512], "rt_subframes": 32, "num_frames": 10,
    "env_url": "/Isaac/Environments/Simple_Warehouse/full_warehouse.usd",
    "writer": "BasicWriter", "backend_params": {"output_dir": "_out_scene_based_sdg"},
}
```

포털에 "프레임 수" 칸을 만들어 봐야 **넘길 자리가 없다.** 값을 바꾸는 정본은 config
파일이고, 포털은 그 파일을 가리키게만 한다. 여기서 폼을 더 만들면 §8이 경고한
`job_template` 재생산이다.

`headless` 기본값이 **`False`** 라는 점이 함정이다 — config 없이 내장 예제를 그대로 돌리면
배치 노드에서 창을 열려다 실패한다. 그래서 config 칸 힌트에 경고를 박았다.

### 샤딩 — 포털이 인자 규약을 발명하지 않는다

데이터셋을 배열 잡으로 쪼개는 것이 data factory의 핵심인데, 여기에 포털이 할 일이 없다:

```bash
# 실측 2026-08-08
$ SLURM_ARRAY_TASK_ID=7 apptainer exec openfoam-2512.sif bash -lc 'echo $SLURM_ARRAY_TASK_ID'
7                        # ← Apptainer가 호스트 환경변수를 그대로 넘긴다
```

사용자 스크립트가 `os.environ["SLURM_ARRAY_TASK_ID"]`로 시드와 출력 폴더를 가르면 된다.
`--shard` 같은 인자를 포털이 정의하면 **사용자 스크립트가 그 규약을 따라야 하는데**,
그건 능력이 아니라 족쇄다. 자원 칸의 **배열 인덱스**가 그대로 샤딩 손잡이다.

### 판본 — 5.1.0을 고른다

6.0은 2026-08 현재 GA 발표와 early developer 배포가 섞여 있고 컨테이너 태그도
`6.0.0-dev2` 같은 형태다. **Python이 3.11 → 3.12로 바뀐다.** 안정판은 5.1.0이고
§4가 정한 그대로 간다.

### 카탈로그가 실제로 만드는 것

```bash
apptainer exec --nv --env ACCEPT_EULA=Y --env PRIVACY_CONSENT=Y \
  /home/portal/images/isaac-sim-5.1.0.sif \
  bash -lc '/isaac-sim/python.sh -u <스크립트> [--config <설정>]'
```

`-u`가 있는 이유: 버퍼링을 끄지 않으면 Job이 끝날 때까지 로그가 한 줄도 안 보인다.
`ACCEPT_EULA` 없이는 Kit이 동의를 물으며 멈추는데 **배치에는 대답할 사람이 없다.**

`--env`·환경변수 전달·커맨드 형태는 openfoam SIF로 실행해 확인했다(apptainer 1.5.3).
**확인하지 못한 것은 Isaac Sim 자체뿐이다** — 이미지가 없다.

### 다음에 할 일 (순서대로)

1. NGC 계정이 있는 기계에서 `isaac-sim:5.1.0` → SIF 변환. **GPU 없이 된다**(§4).
   이때 실제 용량과 변환 가능 여부가 확정된다.
2. L40 노드에서 내장 예제를 **손으로 한 번** 돌린다 — `launch_config.headless: true`인
   config로. 여기서 bind가 더 필요한지, 캐시가 어디에 쌓이는지가 드러난다.
3. 그 결과로 카탈로그를 맞추고 `ready=True`로 바꾼다.

---

## 9. 확인이 필요한 전제

- **workstation·k8s가 `www.dt-hpc.net:9443`에 닿는가.** 사내망 안이면 된다.
  **공인 IP로는 hairpin NAT 때문에 안 닿는다**(CLAUDE.md).
- Isaac Sim 라이브스트림 포트는 판본마다 다르다 — WebRTC를 쓸 때 실측이 필요하다.
- 컨테이너 라이선스: 사내 내부 사용과 재배포는 조건이 다르다. Isaac Sim과 Omniverse
  Enterprise 제품군도 조건이 다르다.

---

## 참고

- [NGC Catalog — Isaac Sim](https://catalog.ngc.nvidia.com/orgs/nvidia/containers/isaac-sim)
- [Isaac Sim 5.1 Requirements](https://docs.isaacsim.omniverse.nvidia.com/5.1.0/installation/requirements.html) — RT 코어 요구·미지원 GPU
- [NVIDIA-Omniverse/IsaacSim-dockerfiles](https://github.com/NVIDIA-Omniverse/IsaacSim-dockerfiles)
- [Isaac Lab Docker Guide](https://isaac-sim.github.io/IsaacLab/main/source/deployment/docker.html)
- [Omniverse Kit App Streaming collection](https://catalog.ngc.nvidia.com/orgs/nvidia/omniverse/collections/kit-appstreaming-collection/-)
- [Snakemake executor plugin: slurm](https://snakemake.github.io/snakemake-plugin-catalog/plugins/executor/slurm.html)
- [Snakemake 9 — executor plugins](https://snakemake.readthedocs.io/en/v9.18.1/executing/executors.html)
- [Isaac Sim 5.1 — Container Installation](https://docs.isaacsim.omniverse.nvidia.com/5.1.0/installation/install_container.html) — rootless uid 1234·캐시 마운트 6개
- [Isaac Sim 5.1 — Scene Based SDG](https://docs.isaacsim.omniverse.nvidia.com/5.1.0/replicator_tutorials/tutorial_replicator_scene_based_sdg.html) — `--config`만 받는 진입점
- [scene_based_sdg.py 소스](https://github.com/isaac-sim/IsaacSim/blob/main/source/standalone_examples/replicator/scene_based_sdg/scene_based_sdg.py) — 기본 config 키
- [j3soon/singularity-isaac-sim](https://github.com/j3soon/singularity-isaac-sim) — bind 없이 `--env ACCEPT_EULA=Y --nv`로 도는 비공식 클러스터 가이드
- [Isaac Lab — Cluster Guide](https://isaac-sim.github.io/IsaacLab/main/source/deployment/cluster.html) — 캐시를 계산 노드로 복사하는 구성
