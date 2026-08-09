"""HTTP 인터랙티브 앱 프록시 지원 (U-IA-01 JupyterLab).

VNC 세션과 **접속 경로가 다르다**. 데스크톱은 RFB 바이트를 웹소켓으로 중계하지만
(`sessions/{sid}/connect`), JupyterLab은 HTTP 서비스라 브라우저가 평범한 요청을 보낸다.
그래서 포털이 리버스 프록시가 된다.

세 가지를 여기서 정한다.

1. **누구의 세션인가** — 경로에 실려 오는 것은 Slurm Job ID다. 컨테이너가 자기 base_url을
   정할 때 아는 것이 그것뿐이기 때문이다(포털 세션 ID는 Job 제출 *뒤에* 생긴다).
   소유자 조건을 조회에 붙여 찾는다 — 남의 Job ID를 넣어도 세션이 안 나온다.

2. **어디에 붙는가** — `connection.json`이 유일한 출처다(VNC와 같은 규칙). 워커 노드
   주소와 포트는 **브라우저에 내보내지 않는다**.

3. **어떻게 붙는가** — 로그인 노드를 거치는 로컬 포트포워딩을 세션마다 하나 띄우고
   재사용한다. 요청마다 SSH를 새로 열면 페이지 한 장에 핸드셰이크가 수십 번이다.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.clients.ssh.forward import LocalPortForward
from app.core.config import Settings
from app.core.errors import NotFound, ValidationFailed
from app.core.secrets import SecretStore
from app.models import User
from app.repositories.cluster import ClusterCredentialRepository
from app.repositories.session import InteractiveSessionRepository
from app.services.cluster import ClusterService
from app.services.files import ssh_target_for

#: 이만큼 아무도 안 쓰면 포워딩을 거둔다. 브라우저 탭을 닫아도 세션 Job은 살아 있으므로
#: 포워딩만 정리한다 — 다시 열면 새로 뜬다.
IDLE_TIMEOUT_SECONDS = 300

#: 해석 결과를 이만큼 재사용한다.
#:
#: **이게 없으면 요청마다 DB 조회 + SSH 접속 + SFTP 읽기가 붙는다.** JupyterLab은 한 페이지에
#: 요청을 수십 개 동시에 던지므로, 실측에서 커넥션 풀이 말라
#: `QueuePool limit of size 5 overflow 10 reached`가 나고 화면 전체가 느려졌다.
#:
#: 인증은 캐시와 무관하게 **매 요청 확인한다**(JWT 서명 + Redis 세션) — 여기 담기는 것은
#: "이 세션이 어디에 붙는가"뿐이다. 로그아웃은 즉시 먹는다.
TARGET_TTL_SECONDS = 60


@dataclass(frozen=True)
class AppTarget:
    """프록시가 붙을 곳 + 앱이 요구하는 자격증명."""

    session_id: int
    cluster_id: int
    #: 백엔드 로컬 포트. 여기로 보내면 로그인 노드를 거쳐 워커의 앱 포트로 간다.
    local_port: int
    #: 앱 자체의 접속 토큰(JupyterLab). **브라우저에 내보내지 않는다** — 포털이 붙인다.
    token: str | None
    base_url: str


class _ForwardRegistry:
    """세션 ID → 포워딩. 프로세스 안에서만 산다(단일 replica 전제).

    replica를 늘리면 요청이 다른 프로세스로 가서 포워딩이 없을 수 있는데, 그때는
    그 프로세스가 새로 띄운다 — 비용만 늘고 틀리지는 않는다.
    """

    def __init__(self) -> None:
        self._items: dict[int, LocalPortForward] = {}
        self._lock = threading.Lock()

    def get_or_create(self, session_id: int, factory) -> LocalPortForward:
        with self._lock:
            self._reap_locked()
            existing = self._items.get(session_id)
            if existing is not None and existing.alive:
                existing.last_used = time.monotonic()
                return existing
            if existing is not None:
                existing.close()
            forward = factory()
            self._items[session_id] = forward
            return forward

    def drop(self, session_id: int) -> None:
        with self._lock:
            forward = self._items.pop(session_id, None)
        if forward is not None:
            forward.close()

    def _reap_locked(self) -> None:
        now = time.monotonic()
        for sid, forward in list(self._items.items()):
            if not forward.alive or now - forward.last_used > IDLE_TIMEOUT_SECONDS:
                self._items.pop(sid, None)
                forward.close()

    def close_all(self) -> None:
        with self._lock:
            items = list(self._items.values())
            self._items.clear()
        for forward in items:
            forward.close()
        TARGETS.clear()


FORWARDS = _ForwardRegistry()


class _TargetCache:
    """(Job ID, 소유자) → 붙을 곳. **소유자를 키에 넣는다** — 남의 캐시를 타지 못한다."""

    def __init__(self) -> None:
        self._items: dict[tuple[str, str], tuple[float, AppTarget]] = {}
        self._lock = threading.Lock()

    def get(self, job_id: str, user_guid: str) -> AppTarget | None:
        key = (str(job_id), user_guid)
        with self._lock:
            found = self._items.get(key)
            if found is None:
                return None
            expires, target = found
            if time.monotonic() > expires:
                self._items.pop(key, None)
                return None
        return target

    def put(self, job_id: str, user_guid: str, target: AppTarget) -> None:
        with self._lock:
            self._items[(str(job_id), user_guid)] = (
                time.monotonic() + TARGET_TTL_SECONDS,
                target,
            )

    def clear(self) -> None:
        with self._lock:
            self._items.clear()


TARGETS = _TargetCache()


class SessionProxyService:
    def __init__(
        self,
        session: Session,
        clusters: ClusterService,
        *,
        settings: Settings,
        secrets: SecretStore,
    ):
        self.session = session
        self.clusters = clusters
        self.settings = settings
        self.secrets = secrets
        self.sessions = InteractiveSessionRepository(session)
        self.credentials = ClusterCredentialRepository(session)

    def target(self, job_id: str, *, user: User) -> AppTarget:
        """Job ID + 요청자 → 붙을 곳. 남의 것이면 **없는 것으로 답한다**.

        **느린 경로다** — DB 조회 + SSH 접속 + `connection.json` 읽기가 들어 있다.
        캐시(`TARGETS`)가 있을 때는 라우터가 여기까지 오지 않는다.
        """
        from app.services.session import SessionService  # 순환 import 회피

        record = self.sessions.owned_by_job(str(job_id), user.ad_object_guid)
        if record is None:
            raise NotFound("세션을 찾을 수 없습니다.", detail={"job_id": job_id})

        sessions = SessionService(
            self.session, self.clusters, settings=self.settings, secrets=self.secrets
        )
        info = sessions.connection(record.id, user=user)
        if not info.get("token") and info.get("scheme") != "http":
            # VNC 세션에 HTTP로 붙으려 한 것이다 — 경로를 잘못 찾았다.
            raise ValidationFailed(
                "이 세션은 웹 앱이 아닙니다.", detail={"session_id": record.id}
            )

        cluster = self.clusters.get(record.cluster_id)
        target = ssh_target_for(cluster, secrets=self.secrets, credentials=self.credentials)

        def build() -> LocalPortForward:
            forward = LocalPortForward(
                target,
                dest_host=str(info["host"]),
                dest_port=int(info["port"]),
                known_hosts=self.settings.ssh_known_hosts,
                timeout=self.settings.ssh_timeout_seconds,
            )
            forward.open()
            return forward

        forward = FORWARDS.get_or_create(record.id, build)
        resolved = AppTarget(
            session_id=record.id,
            cluster_id=record.cluster_id,
            local_port=forward.port,
            token=info.get("token"),
            base_url=str(info.get("base_url") or ""),
        )
        TARGETS.put(job_id, user.ad_object_guid, resolved)
        return resolved
