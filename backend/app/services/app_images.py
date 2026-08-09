"""앱 이미지 해석 — 앱 → apptainer에 넘길 이미지 경로 (A-OP-02, U-IA-01·02, U-JB-13).

이미지는 **포털 공용 디렉터리**(`settings.app_image_dir`, 기본 `/home/portal/images`)에
파일로 두고, 어떤 파일을 쓸지는 앱 카탈로그(`app_catalog.image_file`)가 정한다 —
아이콘과 같은 모양이다. 등록이 없으면 코드 카탈로그의 기본 파일명으로 떨어진다.

## 왜 클러스터 설정이 아닌가

전에는 클러스터마다 `image_repository`(있는 곳)를 받고 파일명만 앱이 가졌다. 그런데
운영 중인 두 클러스터가 같은 경로를 쓰고 있었고, **이미지를 바꾸려면 클러스터를
고쳐야 하는데 정작 바뀌는 것은 앱**이라 자리가 어긋나 있었다. 이제 "있는 곳"은 포털
설정 하나, "무엇을"은 앱 카탈로그가 갖는다.

경로는 **워커 노드 기준**이다 — apptainer가 거기서 실행한다. 포털 백엔드가 같은 경로를
읽을 수 있는지는 무관하다(목록 조회에만 쓴다).
"""

from __future__ import annotations

import re

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import ValidationFailed
from app.repositories.content import AppCatalogRepository
from app.services import batch_apps, session_apps

KIND_INTERACTIVE = "interactive"
KIND_BATCH = "batch"

#: 파일명만 받는다 — 경로 요소가 되면 공용 디렉터리 밖을 가리킬 수 있다.
IMAGE_FILE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


def _code_image(kind: str, app_id: str) -> tuple[str, str, bool]:
    """코드 카탈로그의 (표시 이름, 기본 이미지 파일명, 제공 여부)."""
    if kind == KIND_INTERACTIVE:
        app = session_apps.get(app_id)
    else:
        app = batch_apps.get(app_id)
    return app.name, app.image, app.ready


def resolve(session: Session, settings: Settings, kind: str, app_id: str) -> str:
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
    return f"{settings.app_image_dir.rstrip('/')}/{image}"
