"""코드 카탈로그의 앱에 대한 기본 등록 정보 seed (A-OP-02).

아이콘 파일은 `settings.app_icon_dir`(기본 `/home/.portal/app-icons`)에 이미 있어야 한다.
**없는 파일은 건너뛴다** — 파일이 없는데 파일명만 넣으면 화면에 깨진 아이콘이 남는다.

벤더는 사실 관계이고, 버전은 **코드 카탈로그가 이미 말하고 있는 값만** 옮긴다
(설명·이미지 파일명에 드러난 것). 모르는 값은 비워 둔다 — 지어내면 화면이 거짓말한다.

    python -m scripts.seed_app_catalog          # 없는 것만 등록
    python -m scripts.seed_app_catalog --force  # 이미 있으면 덮어쓴다
"""

from __future__ import annotations

import argparse
from pathlib import Path

from app.core.config import get_settings
from app.db.session import get_session_factory, init_engine
from app.models import AppCatalog
from app.services import batch_apps, session_apps

#: (kind, app_id, vendor, version, 아이콘 파일, 이미지 파일).
#: name·description은 코드 카탈로그가 정본이라 넣지 않는다. 이미지 파일을 비우면
#: 코드 카탈로그의 기본값이 그대로 쓰인다.
SEED = [
    ("interactive", "desktop", "MATE Desktop", None, "desktop.svg", "rocky9-mate-1.5.sif"),
    ("interactive", "paraview", "Kitware", "5.11", "paraview.png", "rocky9-mate-1.5.sif"),
    ("interactive", "jupyter", "Project Jupyter", None, "jupyter.svg", "rocky9-mate-1.6.sif"),
    ("interactive", "code-server", "Microsoft", None, "code-server.svg", None),
    ("batch", "openfoam", "OpenCFD (ESI)", "v2512", "openfoam.svg", "openfoam-2512.sif"),
    ("batch", "isaac-sim", "NVIDIA", None, "isaac-sim.svg", None),
]


def _code_name(kind: str, app_id: str) -> str:
    catalog = session_apps.APPS if kind == "interactive" else batch_apps.APPS
    app = next((a for a in catalog if a.id == app_id), None)
    return app.name if app else app_id


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true", help="이미 등록된 앱도 덮어쓴다")
    args = parser.parse_args()

    settings = get_settings()
    init_engine(settings.database_url)
    icon_dir = Path(settings.app_icon_dir)
    image_dir = Path(settings.app_image_dir)
    session = get_session_factory()()
    try:
        for kind, app_id, vendor, version, icon, image in SEED:
            if not (icon_dir / icon).is_file():
                print(f"skip  {kind}/{app_id} — 아이콘 파일 없음: {icon_dir / icon}")
                continue
            row = (
                session.query(AppCatalog)
                .filter_by(kind=kind, app_id=app_id)
                .one_or_none()
            )
            if row and not args.force:
                print(f"keep  {kind}/{app_id} — 이미 등록됨")
                continue
            if row is None:
                # 이름은 코드 카탈로그 값을 그대로 옮긴다 — 등록 이름이 코드 이름을 덮으므로
                # 여기서 app_id 같은 임시값을 넣으면 화면 이름이 나빠진다.
                row = AppCatalog(kind=kind, app_id=app_id, name=_code_name(kind, app_id))
                session.add(row)
            row.vendor = vendor
            row.version = version
            row.icon_file = icon
            # 이미지 파일이 실제로 없으면 넣지 않는다 — 없는 파일을 가리키면 제출이 막힌다.
            if image and (image_dir / image).is_file():
                row.image_file = image
            elif image:
                print(f"      (이미지 파일 없음, 코드 기본값 유지: {image})")
            print(f"seed  {kind}/{app_id} — {vendor} {version or ''} {icon} {image or ''}")
        session.commit()
    finally:
        session.close()


if __name__ == "__main__":
    main()
