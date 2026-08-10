"""앱 이미지 해석 — 앱 → apptainer에 넘길 이미지 경로 (A-OP-02, U-IA-01·02, U-JB-13).

"어떤 파일"은 앱 카탈로그(`app_catalog.image_file`)가 정하고 — 아이콘과 같은 모양이다,
등록이 없으면 코드 카탈로그의 기본 파일명으로 떨어진다 — **"어디에"는 클러스터가 정한다.**

## 위치는 `home_base`에서 파생한다

이미지는 계산 노드가 볼 수 있는 곳에 있어야 하고, 그건 클러스터마다 다른 NFS일 수 있다.
그렇다고 "이미지 디렉터리" 칸을 따로 만들지는 않는다 — 클러스터마다의 공유 경로가
**이미 있다**(`cluster.home_base`, SCR-18 "홈 상위 경로"). 파생시키면 설정이 늘지 않고,
무엇보다 **공유되지 않는 경로가 들어갈 여지가 없다**: `home_base`는 파일 관리자가 매일
쓰는 값이라 "모든 노드가 보는 경로"임이 계속 검증된다.

`.portal`에 점이 붙은 이유는 그 아래가 **사용자명이 오는 자리**여서다. `portal`은 유효한
사용자명이라 AD에 그 계정이 생기면 홈 프로비저닝이 이미지 저장소 위로 떨어진다.

경로는 **워커 노드 기준**이다 — apptainer가 거기서 실행한다. 포털 백엔드가 같은 경로를
읽을 수 있는지는 무관하다.
"""

from __future__ import annotations

import re

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import ValidationFailed
from app.models import Cluster
from app.repositories.content import AppCatalogRepository
from app.services import batch_apps, session_apps

KIND_INTERACTIVE = "interactive"
KIND_BATCH = "batch"

#: 파일명만 받는다 — 경로 요소가 되면 공용 디렉터리 밖을 가리킬 수 있다.
IMAGE_FILE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")

#: 공유 홈 아래 이미지가 놓이는 자리. 점이 붙은 이유는 모듈 머리말 참조.
IMAGE_SUBDIR = ".portal/images"


def image_dir(cluster: Cluster, settings: Settings) -> str:
    """이 클러스터의 이미지 디렉터리.

    `home_base`가 비면 파생할 상위가 없다 — 그 모드는 `getent passwd`로 **사용자별**
    홈을 찾는 것이라 공용 자리가 정해지지 않는다. 그때만 포털 기본값으로 떨어진다.
    """
    if cluster.home_base:
        return f"{cluster.home_base.rstrip('/')}/{IMAGE_SUBDIR}"
    return settings.app_image_dir.rstrip("/")


def _code_image(kind: str, app_id: str) -> tuple[str, str, bool]:
    """코드 카탈로그의 (표시 이름, 기본 이미지 파일명, 제공 여부)."""
    if kind == KIND_INTERACTIVE:
        app = session_apps.get(app_id)
    else:
        app = batch_apps.get(app_id)
    return app.name, app.image, app.ready


def resolve(
    session: Session, settings: Settings, cluster: Cluster, kind: str, app_id: str
) -> str:
    """앱이 쓸 이미지 경로. **제출 전에 막는다** — 워커까지 가서 죽으면 원인이 안 보인다."""
    name, default_image, ready = _code_image(kind, app_id)
    row = AppCatalogRepository(session).get_by_app(kind, app_id)
    image = (row.image_file if row and row.image_file else default_image) or ""

    if not ready:
        raise ValidationFailed(
            f"'{name}'은(는) 아직 제공되지 않습니다.", detail={"app": app_id}
        )
    if not image:
        raise ValidationFailed(
            f"'{name}'에 이미지 파일이 지정되어 있지 않습니다. 앱 관리에서 등록하세요.",
            detail={"app": app_id, "field": "image_file"},
        )
    if not IMAGE_FILE.match(image):
        # 등록 시에도 막지만, 옛 데이터가 남아 있을 수 있어 쓰기 직전에 한 번 더 본다.
        raise ValidationFailed(
            "이미지 파일명이 올바르지 않습니다.", detail={"image_file": image}
        )
    return f"{image_dir(cluster, settings)}/{image}"
