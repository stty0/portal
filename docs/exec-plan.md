# Exec Plan: 앱 이미지를 클러스터별로

- 근거 plan: [docs/plan.md](plan.md)
- 담당: 구현·검증 Claude
- 이전 에픽 exec-plan은 git 이력 참조

> **상태: T-01~T-06 완료(배포·실측까지) · T-07·T-08 철회.**
> 아래 수용 기준은 T-06까지 충족 확인된 것이다. T-07·T-08은 만들었다가 걷어냈고
> (마이그레이션 `0019`), 경위와 실측은 [progress.md](progress.md)에 있다.

순차 진행한다. 각 Task는 **단독으로 배포 가능한 상태**로 끝난다 — 중간에 멈춰도
반쪽이 남지 않게.

## Task 목록

### T-01 이미지 경로를 `home_base`에서 파생
- 대상 파일: `backend/app/services/app_images.py`, `backend/app/services/session.py`,
  `backend/app/routers/batch_apps.py`, `backend/app/core/config.py`
- 내용:
  - `image_dir(cluster, settings) -> str` 신설 — `{home_base}/.portal/images`,
    `home_base`가 비면 `settings.app_image_dir`
  - `resolve(...)`에 `cluster` 인자 추가. **호출부는 둘 다 이미 cluster를 들고 있다** —
    `session.py:93 image_ref(self, cluster, app)`는 받아 놓고 안 쓰고 있고,
    `routers/batch_apps.py:95`는 바로 윗줄에서 `clusters.get(cid)`를 한다
  - `settings.app_image_dir` 기본값을 `/home/.portal/images`로
- 의존성: 없음
- 수용 기준:
  - [x] `home_base='/nfs/home'` → `/nfs/home/.portal/images/<파일>`
  - [x] `home_base=None` → `settings.app_image_dir` 폴백
  - [x] `home_base='/home/'`(꼬리 슬래시) → 슬래시가 겹치지 않는다
  - [x] 기존 테스트 전부 통과

### T-02 `/home/portal` → `/home/.portal` 이동
- 대상 파일: `deploy/k8s/30-backend.yaml`, `docs/progress.md`
- 내용:
  - 클러스터에서 `mv /home/portal /home/.portal` (같은 FS라 즉시)
  - Deployment의 **hostPath 두 개**를 `.portal`로. **mountPath는 그대로 둔다** —
    컨테이너 안 `/home/portal`은 컨테이너 사용자의 홈이지 클러스터 네임스페이스가
    아니다. 그래서 `settings.app_icon_dir`도 안 바뀐다
  - `type: Directory`라 경로가 틀리면 파드가 안 뜬다 — **이동과 롤아웃을 한 번에**
- 의존성: T-01 (기본값이 먼저 바뀌어야 한다)
- 수용 기준:
  - [x] 파드 안에서 `ls /home/portal/images`에 SIF가 그대로 보인다
  - [x] 아이콘 업로드가 여전히 된다
  - [x] 돌고 있는 세션이 죽지 않는다 (SIF를 mmap 중 — `mv`는 inode 유지라 안전)

### T-03 클러스터별 이미지 목록 (SSH)
- 대상 파일: `backend/app/services/app_images.py`(또는 신규 `AppImageService`),
  `backend/app/routers/clusters.py`, `backend/app/core/redis_client.py`
- 내용:
  - `GET /clusters/{cid}/app-images` — 로그인 노드에서 `ls`. `FileService`의
    `_target`/`_connect` 패턴을 그대로 따른다(라우터에서 client 직접 호출 금지)
  - 파일명 필터는 기존 `IMAGE_FILE` 정규식 재사용
  - Redis 60초 캐시. 키 `cluster:{id}:app-images`
  - **실패는 빈 목록으로 흡수한다** — 로그인 노드가 죽어도 화면은 떠야 한다
- 의존성: T-01
- 수용 기준:
  - [x] 목록이 그 클러스터의 파생 경로를 읽는다
  - [x] SSH 실패 시 500이 아니라 빈 목록
  - [x] 두 번째 호출이 SSH를 다시 열지 않는다(캐시)
  - [x] `test_layering.py` 통과

### T-04 관리 화면 전환 + 파드 마운트 제거
- 대상 파일: `frontend/src/views/admin/AppsCatalogView.vue`,
  `frontend/src/api/ops.ts`·`clusters.ts`, `backend/app/routers/ops.py`,
  `deploy/k8s/30-backend.yaml`
- 내용:
  - 이미지 파일 선택기가 **활성 클러스터 전체의 합집합**을 보여준다. 앱 관리는 포탈
    스코프 화면이라 클러스터 선택기가 없다 — 선택기의 목적은 *유효한 파일명을 고르게
    돕는 것*이고, 어느 클러스터에 있는지는 T-06이 사용자 화면에서 답한다
  - `GET /ops/app-images` **제거**
  - Deployment의 `app-images` hostPath 마운트 **제거** — 파드가 더는 안 읽는다
- 의존성: T-03
- 수용 기준:
  - [x] 선택기에 SIF 목록이 뜬다
  - [x] 파드에 이미지 디렉터리가 마운트되지 않아도 목록이 나온다
  - [x] `/ops/app-images` 참조가 코드·문서에 남아 있지 않다

### T-05 클러스터 등록 시 디렉터리 확인
- 대상 파일: `backend/app/services/cluster.py`, `backend/app/schemas/cluster.py`,
  `frontend/src/views/admin/ClustersView.vue`
- 내용: 등록·수정 뒤 이어지는 확인에 이미지 디렉터리를 더한다. 없으면 **경고**를
  응답에 실어 화면에 띄우되 **등록은 성공시킨다**
- 의존성: T-03
- 수용 기준:
  - [x] 없는 경로로 등록하면 경고가 뜨고 클러스터는 등록된다
  - [x] 경고 문구에 **경로와 할 일**(경로 생성 + SIF 배치)이 들어 있다.
        **쓰기 권한을 주라고 하지 않는다** — 포털은 여기 쓰지 않고, 이 클러스터엔 관리자
        그룹이 없어 그 말은 곧 `domain users`에 여는 것이다(2026-08-10 감사에서 정정)

### T-06 `installed` 판정 → 잠금 셋
- 대상 파일: `backend/app/services/app_images.py`,
  `backend/app/routers/sessions.py`·`batch_apps.py`, `backend/app/schemas/*`,
  `frontend/src/views/user/AppsView.vue`·`BatchAppsView.vue`
- 내용:
  - 목록 응답에 `installed: bool`
  - `usable = ready && installed && allowed`. **숨기지 않고 잠그며 사유를 말한다**
  - `resolve()`의 "아직 제공되지 않습니다"를 둘로 가른다 — 실행 방식 미확정(`ready`)과
    이미지 없음(`installed`)은 다른 문장이어야 한다
  - `ready` 주석을 "실행 방식이 확정됐나"로 좁힌다. **Isaac Sim은 `ready=False` 유지** —
    커맨드가 아직 실측이 아니다(카탈로그 주석에 근거가 적혀 있다)
- 의존성: T-03
- 수용 기준:
  - [x] SIF를 디렉터리에 넣으면 **코드 배포 없이** 앱이 열린다
  - [x] 이미지 없는 앱이 목록에 남고 사유가 보인다
  - [x] 잠긴 앱을 API로 직접 제출하면 422로 끊긴다(화면 잠금만으로는 제한이 아니다)

### ~~T-07 `app_catalog.image_ref` — 이미지의 출처~~ — **철회**
- 대상 파일: `backend/alembic/versions/0018_app_image_ref.py`,
  `backend/app/models/content.py`, `backend/app/schemas/ops.py`,
  `frontend/src/views/admin/AppsCatalogView.vue`
- 내용: OCI 참조를 담는 nullable 컬럼(`docker://opencfd/openfoam-default:2512`).
  **T-08 없이도 값이 있다** — 지금 그 출처는 `progress.md` 본문에만 있어서, 버전을
  올리려면 문서를 뒤져야 한다
- 의존성: T-04
- 수용 기준:
  - ~~앱 관리에서 입력·수정된다~~ (철회 전 충족)
  - ~~마이그레이션 up/down 확인 (MySQL DDL은 트랜잭션이 아니다 — down은 최소로)~~ (철회 전 충족)

### ~~T-08 변환을 Slurm 잡으로~~ — **철회**
- 대상 파일: `backend/app/services/app_images.py`, `backend/app/routers/clusters.py`,
  `frontend/src/views/admin/AppsCatalogView.vue`, `docs/progress.md`
- 내용:
  - 관리자 액션 "이 클러스터에 설치" → `apptainer build`를 배치 잡으로 제출
  - 스크립트: `APPTAINER_CACHEDIR`·`APPTAINER_TMPDIR`을 **둘 다** 홈 아래로,
    `<이름>.sif.tmp`로 빌드 후 `mv`
  - 진행 상황은 기존 Job 화면이 보여준다 — 새 상태 모델을 만들지 않는다
  - 디렉터리 그룹 쓰기 권한 절차를 문서에 남긴다
- 의존성: T-06, T-07
- 수용 기준:
  - ~~실제 클러스터에서 한 이미지를 변환해 앱이 열리는 것까지 확인~~ (철회 전 충족)
  - ~~빌드 실패 시 `.sif`가 남지 않는다~~ (철회 전 충족)
  - ~~변환 뒤 캐시가 `/home` 아래에만 있다 (root 홈에 blob 없음)~~ (철회 전 충족)

## 검증 (매 Task)

```bash
cd backend  && .venv/bin/python -m pytest -q
cd frontend && npm run build
```

배포가 따르는 Task는 **파드 안에서** 확인한다 — 태그(`:0.1.0`)와 번들 문자열까지.
이미지 빌드 뒤 `docker builder prune -af`.
