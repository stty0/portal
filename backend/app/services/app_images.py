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

import logging
import re

from sqlalchemy.orm import Session

from app.clients.ssh.client import LoginNodeClient
from app.core.config import Settings
from app.core.errors import ValidationFailed
from app.core.redis_client import AppImageCache
from app.core.secrets import SecretStore
from app.models import Cluster
from app.repositories.cluster import ClusterCredentialRepository
from app.repositories.content import AppCatalogRepository
from app.services import batch_apps, session_apps
from app.services.cluster import ClusterService
from app.services.files import ssh_target_for

logger = logging.getLogger(__name__)

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


class AppImageService:
    """클러스터에 **실제로 있는** 이미지 파일 목록 (A-OP-02).

    전에는 백엔드 파드의 파일시스템을 읽었다. 그게 맞아떨어진 이유는 dev01이 클러스터와
    같은 NFS를 마운트하고 있어서고, 클러스터마다 경로가 갈리면 성립하지 않는다 — **파드
    마운트는 Deployment에 정적으로 박혀 있어 클러스터를 등록해도 생기지 않는다.**

    그래서 클러스터에 직접 묻는다. 파일 관리자가 이미 쓰는 SSH라 새 인프라가 아니다.
    """

    def __init__(
        self,
        session: Session,
        clusters: ClusterService,
        *,
        settings: Settings,
        secrets: SecretStore,
        cache: AppImageCache,
    ):
        self.session = session
        self.clusters = clusters
        self.settings = settings
        self.secrets = secrets
        self.cache = cache
        self.credentials = ClusterCredentialRepository(session)

    def _connect(self, cluster: Cluster) -> LoginNodeClient:
        return LoginNodeClient(
            ssh_target_for(cluster, secrets=self.secrets, credentials=self.credentials),
            known_hosts=self.settings.ssh_known_hosts,
            timeout=self.settings.ssh_timeout_seconds,
        )

    def available(self, cluster: Cluster, *, username: str) -> list[str]:
        """이미지 디렉터리에 있는 파일명.

        **실패를 빈 목록으로 흡수한다.** 디렉터리가 아직 없거나 로그인 노드가 죽어도
        화면은 떠야 한다 — 앱이 잠기는 것과 화면이 안 나오는 것은 다른 일이다.

        예외를 좁혀 잡으면 안 된다. 처음에 `(PortalError, OSError)`로 뒀다가 실 클러스터에서
        새어 나갔다 — paramiko는 `SSHException`을 그대로 던지고 그건 둘 다 아니다. 이
        메서드의 계약이 "무슨 일이 있어도 목록을 돌려준다"이므로 **경계가 예외 종류가
        아니라 이 호출 자체**다. 대신 원인을 삼키지 않도록 로그로 남긴다.
        """
        cached = self.cache.get(cluster.id)
        if cached is not None:
            return cached

        directory = image_dir(cluster, self.settings)
        try:
            with self._connect(cluster) as client:
                _, entries = client.list_dir(username, directory)
            names = sorted(
                e.name for e in entries if not e.is_dir and IMAGE_FILE.match(e.name)
            )
        except Exception:
            logger.warning(
                "이미지 목록 조회 실패 — cluster=%s dir=%s user=%s",
                cluster.id, directory, username, exc_info=True,
            )
            names = []

        self.cache.put(cluster.id, names)
        return names

    def check(self, cluster: Cluster, *, username: str) -> dict[str, object]:
        """등록 화면용 진단 — **캐시를 쓰지 않고** 실패 이유를 말한다.

        `available()`은 목록을 그리는 자리라 실패를 삼키지만, 여기는 관리자가 *무엇을
        해야 하는지* 알아야 하는 자리다. 디렉터리가 없는 것과 로그인 노드에 못 붙는 것은
        할 일이 다르다 — 하나로 뭉뚱그리면 엉뚱한 데를 고치게 된다.

        **포털이 디렉터리를 만들지 않는다.** `{home_base}`는 root 소유라 만들려면 권한
        상승이 필요하고, 그건 "허용 루트는 홈뿐"이라는 경계를 깨는 첫 사례가 된다.
        게다가 만들어 줘도 SIF는 여전히 손으로 넣어야 하고, 변환 잡(T-08)이 쓰려면
        그룹 쓰기 권한까지 필요해서 `mkdir` 한 번으로 끝나지도 않는다.
        """
        directory = image_dir(cluster, self.settings)
        try:
            with self._connect(cluster) as client:
                _, entries = client.list_dir(username, directory)
        except ValidationFailed:
            # 경로 없음·권한 없음 — 클라이언트가 이 둘을 ValidationFailed로 준다.
            return {
                "path": directory,
                "ok": False,
                "images": 0,
                "message": (
                    f"이미지 디렉터리가 없습니다: {directory} — "
                    "클러스터에서 만들고 관리자 그룹에 쓰기 권한을 주세요."
                ),
            }
        except Exception:
            logger.warning("이미지 디렉터리 확인 실패 — cluster=%s", cluster.id, exc_info=True)
            return {
                "path": directory,
                "ok": False,
                "images": 0,
                "message": (
                    f"이미지 디렉터리를 확인할 수 없습니다: {directory} — "
                    f"로그인 노드 접속과 '{username}' 계정을 확인하세요."
                ),
            }

        count = sum(1 for e in entries if not e.is_dir and IMAGE_FILE.match(e.name))
        return {
            "path": directory,
            "ok": True,
            "images": count,
            "message": f"이미지 디렉터리 확인 — {directory} (파일 {count}개)",
        }

    def installed(self, cluster: Cluster, *, username: str, image: str) -> bool:
        """이 클러스터에 그 파일이 있나. 앱 목록의 `installed` 판정(T-06)이 이걸 쓴다."""
        return bool(image) and image in self.available(cluster, username=username)
