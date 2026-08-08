"""인증 서비스 — 부트스트랩·AD 로그인·JIT 프로비저닝 (C-01·C-02, A-US-01).

신원 매칭 규칙(backend-design §3.2·§3.3):
  - objectGUID로 조회 → 있으면 동일인. username만 달라졌으면 **개명**이므로 role 유지.
  - GUID가 다르면 sAMAccountName 재사용이므로 **다른 사람** — 신규 프로비저닝.
이 규칙이 없으면 삭제 후 재생성된 계정이 전임자의 role을 물려받는다.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from hmac import compare_digest

from sqlalchemy.orm import Session

from app.clients.ad.client import AdClient, AdSettings, AdUser
from app.core.config import Settings
from app.core.errors import (
    AdError,
    BootstrapLocked,
    Forbidden,
    NotFound,
    Unauthenticated,
    ValidationFailed,
)
from app.core.redis_client import RefreshTokenStore, SessionStore
from app.core.secrets import SecretStore
from app.core.security import create_session_token
from app.models import AdConnection, User
from app.repositories.cluster import AdConnectionRepository
from app.repositories.identity import RoleRepository, UserRepository
from app.services.audit import AuditService

ROLE_USER = "USER"
ROLE_ADMIN = "ADMIN"
AD_BIND_SECRET_REF = "ad/bind"


@dataclass
class LoginResult:
    token: str
    user: User
    #: refresh 토큰. 브라우저는 쿠키로, 기계 클라이언트는 응답 본문으로 받는다.
    refresh_token: str | None = None


class AuthService:
    def __init__(
        self,
        session: Session,
        settings: Settings,
        *,
        secrets: SecretStore,
        sessions: SessionStore,
        refresh_tokens: "RefreshTokenStore | None" = None,
        ad_client_factory=None,
    ):
        self.session = session
        self.settings = settings
        self.secrets = secrets
        self.sessions = sessions
        self.refresh_tokens = refresh_tokens
        self.users = UserRepository(session)
        self.roles = RoleRepository(session)
        self.ad_conns = AdConnectionRepository(session)
        self.audit = AuditService(session)
        # 테스트에서 fake AD를 주입하기 위한 훅
        self._ad_client_factory = ad_client_factory or self._default_ad_client

    # --- AD client 구성 -------------------------------------------------
    def _default_ad_client(self, conn: AdConnection, password: str) -> AdClient:
        return AdClient(
            AdSettings(
                ldaps_url=conn.ldaps_url or "",
                base_dn=conn.base_dn or "",
                bind_account=conn.bind_account or "",
                bind_password=password,
                allowed_group=conn.allowed_group,
                id_attribute=conn.id_attribute or "sAMAccountName",
                timeout=self.settings.ad_timeout_seconds,
                tls_verify=self.settings.ad_tls_verify,
                ca_cert_file=self.settings.ad_ca_cert_file,
            )
        )

    def ad_client(self, conn: AdConnection | None = None) -> AdClient:
        """저장된 AD 연결로 client를 만든다. 암호는 Secret 저장소에서 해석한다."""
        conn = conn or self.ad_conns.get_single()
        if conn is None:
            raise NotFound("AD 연결이 설정되어 있지 않습니다.")
        password = self.secrets.get(conn.bind_secret_ref) if conn.bind_secret_ref else ""
        return self._ad_client_factory(conn, password)

    # --- 부트스트랩 (C-02) ---------------------------------------------
    def is_bootstrapped(self) -> bool:
        """seed ADMIN 지정 여부가 곧 부트스트랩 완료 여부다."""
        conn = self.ad_conns.get_single()
        return bool(conn and conn.seed_admin_guid)

    def _assert_setup_allowed(self, setup_token: str) -> None:
        """부트스트랩 화면은 미인증 상태로 열리므로, 진입 조건을 한 곳에서 강제한다."""
        if self.is_bootstrapped():
            # 재실행은 서버측에서 하드 거부한다 — 클라이언트 분기에 의존하지 않는다.
            raise BootstrapLocked("이미 부트스트랩이 완료되었습니다. setup은 재실행할 수 없습니다.")
        expected = self.settings.setup_token
        # 문자열 비교는 일치 길이만큼 시간이 달라져 토큰을 한 글자씩 추측할 여지를 준다.
        if not expected or not compare_digest(setup_token, expected):
            raise Forbidden("setup 토큰이 유효하지 않습니다.")

    def probe_ad(
        self,
        *,
        setup_token: str,
        ldaps_url: str,
        base_dn: str,
        bind_account: str,
        bind_password: str,
        allowed_group: str | None,
        id_attribute: str,
    ) -> list[AdUser]:
        """부트스트랩 1단계 — AD에 bind해서 **선택 가능한 사용자 목록**을 돌려준다.

        관리자 계정명을 손으로 받아치면 오타 하나로 실패하고, 무엇보다 그 계정이 실제로
        조회되는지(허용 그룹 안에 있는지) 확인할 방법이 없다. 연결을 먼저 검증하고
        실제 목록에서 고르게 한다. **DB·Secret 저장소에 아무것도 쓰지 않는다** — 검증 전용이다.
        """
        self._assert_setup_allowed(setup_token)
        transient = AdConnection(
            ldaps_url=ldaps_url,
            base_dn=base_dn,
            bind_account=bind_account,
            allowed_group=allowed_group,
            id_attribute=id_attribute or "sAMAccountName",
        )
        return self._ad_client_factory(transient, bind_password).list_users()

    def setup(
        self,
        *,
        setup_token: str,
        ldaps_url: str,
        base_dn: str,
        bind_account: str,
        bind_password: str,
        allowed_group: str | None,
        id_attribute: str,
        seed_admin_username: str,
    ) -> User:
        """최초 AD 연결 + seed ADMIN 1명 지정. 성공 후 영구 잠금(1회용)."""
        self._assert_setup_allowed(setup_token)

        conn = self.ad_conns.get_single() or AdConnection()
        conn.ldaps_url = ldaps_url
        conn.base_dn = base_dn
        conn.bind_account = bind_account
        conn.allowed_group = allowed_group
        conn.id_attribute = id_attribute or "sAMAccountName"
        conn.bind_secret_ref = AD_BIND_SECRET_REF
        self.secrets.put(AD_BIND_SECRET_REF, bind_password)  # 실값은 Secret 저장소에만
        if conn.id is None:
            self.ad_conns.add(conn)
        self.session.flush()

        # AD 검증: 지정한 사용자가 실제로 존재(+허용 그룹 소속)해야 seed 가능
        ad_user = self.ad_client(conn).find_user(seed_admin_username)
        if ad_user is None:
            raise ValidationFailed(
                "AD에서 지정한 사용자를 찾을 수 없습니다.",
                detail={"username": seed_admin_username},
            )

        user = self.provision(ad_user, role_code=ROLE_ADMIN)
        # provision()은 **기존 사용자의 role을 보존한다**(개명이 권한을 바꾸면 안 되므로).
        # 하지만 부트스트랩은 "이 계정을 관리자로 만든다"가 목적이라, 이미 USER로
        # 등록돼 있던 계정이라도 여기서는 ADMIN으로 승격시켜야 한다.
        admin_role = self.roles.get_by_code(ROLE_ADMIN)
        if admin_role is None:
            raise ValidationFailed("ADMIN 역할이 없습니다. 마이그레이션(RBAC seed)을 확인하세요.")
        user.role_id = admin_role.id
        user.is_active = True
        user.deleted_at = None

        conn.seed_admin_guid = user.ad_object_guid
        self.audit.record(
            actor=user, action="BOOTSTRAP_SETUP", target=user.username, detail="seed ADMIN 지정"
        )
        self.session.commit()
        return user

    # --- 로그인 ---------------------------------------------------------
    def login(self, username: str, password: str, *, ip: str | None = None) -> LoginResult:
        conn = self.ad_conns.get_single()
        if conn is None or not conn.seed_admin_guid:
            raise Forbidden("포털 초기 설정이 완료되지 않았습니다.")
        try:
            ad_user = self.ad_client(conn).authenticate(username, password)
        except AdError as exc:
            # AD 실패 사유를 그대로 노출하면 계정 존재 여부가 새어 나간다.
            raise Unauthenticated("사용자명 또는 비밀번호가 올바르지 않습니다.", detail=None) from exc

        user = self.provision(ad_user, role_code=ROLE_USER)
        if not user.is_active or user.deleted_at is not None:
            raise Forbidden("비활성화된 계정입니다.")

        user.last_login_at = datetime.now(timezone.utc)
        # 세션을 먼저 만들고 그 sid를 토큰에 담는다 — 토큰은 세션을 가리키는 표일 뿐이다.
        session = self.sessions.create(user_guid=user.ad_object_guid, username=user.username)
        token = create_session_token(
            self.settings,
            sid=session.sid,
            username=user.username,
            guid=user.ad_object_guid,
            role=user.role.code if user.role else ROLE_USER,
        )
        refresh = self.refresh_tokens.issue(sid=session.sid) if self.refresh_tokens else None
        self.audit.record(actor=user, action="LOGIN", target=user.username, ip=ip)
        self.session.commit()
        return LoginResult(token=token, user=user, refresh_token=refresh)

    def refresh(self, refresh_token: str) -> LoginResult:
        """refresh 토큰 → 새 액세스 토큰(+ 회전된 refresh).

        **회전한다.** 쓴 토큰은 즉시 폐기하고 새것을 준다. 이미 쓴 토큰이 다시 오면
        탈취로 보고 **그 세션 전체를 끊는다** — 정상 클라이언트는 같은 토큰을 두 번 쓰지
        않으므로, 재사용은 사본이 돌아다닌다는 뜻이다.
        """
        if self.refresh_tokens is None:
            raise Unauthenticated("refresh를 사용할 수 없습니다.")
        sid = self.refresh_tokens.consume(refresh_token)
        if sid is None:
            raise Unauthenticated("세션이 만료되었습니다. 다시 로그인하세요.")
        session = self.sessions.get(sid)
        if session is None:
            raise Unauthenticated("세션이 만료되었거나 로그아웃되었습니다.")
        user = self.users.get_by_guid(session.user_guid)
        if user is None or user.deleted_at is not None or not user.is_active:
            # 계정이 막힌 뒤에도 갱신되면 안 된다 — 세션까지 끊는다.
            self.sessions.revoke(sid)
            raise Unauthenticated("사용자를 찾을 수 없거나 비활성화되었습니다.")
        token = create_session_token(
            self.settings,
            sid=sid,
            username=user.username,
            guid=user.ad_object_guid,
            role=user.role.code if user.role else ROLE_USER,
        )
        return LoginResult(
            token=token, user=user, refresh_token=self.refresh_tokens.issue(sid=sid)
        )

    def logout(self, user: User, sid: str) -> None:
        """요청에 쓰인 세션만 종료한다 — 다른 기기의 로그인은 유지된다."""
        self.sessions.revoke(sid)
        self.audit.record(actor=user, action="LOGOUT", target=user.username)
        self.session.commit()

    # --- JIT 프로비저닝 (A-US-01) ---------------------------------------
    def provision(self, ad_user: AdUser, *, role_code: str) -> User:
        """GUID 기준 매칭. 없으면 생성, 있으면 AD 신원 필드만 갱신(role 유지)."""
        user = self.users.get_by_guid(ad_user.object_guid)
        if user is not None:
            # 개명 처리: username이 바뀌어도 동일인이므로 role을 유지한다.
            user.username = ad_user.username
            user.display_name = ad_user.display_name
            user.email = ad_user.email
            if user.deleted_at is not None:
                # AD에 다시 나타났으므로 soft delete 복구
                user.deleted_at = None
                user.is_active = True
            return user

        # GUID가 없는데 username이 점유돼 있다면 sAMAccountName 재사용 건이다.
        # 이전 사용자의 role을 물려주지 않도록 기존 행을 soft delete하고 자리를 비운다.
        stale = self.users.get_by_username(ad_user.username)
        if stale is not None:
            stale.username = f"{stale.username}#retired-{stale.ad_object_guid[:8]}"
            stale.is_active = False
            stale.deleted_at = datetime.now(timezone.utc)
            self.session.flush()

        role = self.roles.get_by_code(role_code)
        user = User(
            ad_object_guid=ad_user.object_guid,
            username=ad_user.username,
            display_name=ad_user.display_name,
            email=ad_user.email,
            role_id=role.id if role else None,
            is_active=True,
        )
        return self.users.add(user)
