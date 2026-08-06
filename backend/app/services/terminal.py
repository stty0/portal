"""웹 터미널 서비스 (U-SH-01).

라우터는 웹소켓 프레임만 다루고, **세션 인증·대상 해석·PTY 개설은 여기서** 한다
(backend-design §1.2 router → service → client).
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.clients.ssh.pty import PtySession
from app.core.config import Settings
from app.core.errors import Unauthenticated
from app.core.redis_client import SessionStore
from app.core.secrets import SecretStore
from app.models import User
from app.repositories.cluster import ClusterCredentialRepository, ClusterRepository
from app.services.audit import AuditService
from app.services.files import ssh_target_for
from app.services.ws_auth import authenticate_ws_token


class TerminalService:
    def __init__(
        self,
        session: Session,
        *,
        settings: Settings,
        secrets: SecretStore,
        sessions: SessionStore,
    ):
        self.session = session
        self.settings = settings
        self.secrets = secrets
        self.sessions = sessions
        self.audit = AuditService(session)

    def authenticate(self, token: str) -> User:
        """세션 토큰 → 사용자. HTTP와 같은 규칙(서명 + Redis 세션 존재)을 적용한다."""
        return authenticate_ws_token(
            self.session, settings=self.settings, sessions=self.sessions, token=token
        )

    def open(self, cluster_id: int, *, user: User) -> PtySession:
        """로그인 노드에 사용자 권한 PTY를 연다.

        대상 사용자는 **인증된 본인 고정** — 클라이언트가 누구의 셸인지 고를 수 없다.
        """
        cluster = ClusterRepository(self.session).get(cluster_id)
        if cluster is None:
            raise Unauthenticated("클러스터를 찾을 수 없습니다.")
        target = ssh_target_for(
            cluster,
            secrets=self.secrets,
            credentials=ClusterCredentialRepository(self.session),
        )
        pty = PtySession(
            target,
            username=user.username,
            known_hosts=self.settings.ssh_known_hosts,
            timeout=self.settings.ssh_timeout_seconds,
        )
        pty.open()
        return pty

    def record(self, action: str, *, user: User, cluster_id: int) -> None:
        self.audit.record(actor=user, action=action, target=user.username, cluster_id=cluster_id)
        self.session.commit()
