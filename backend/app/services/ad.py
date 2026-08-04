"""AD 연결 설정 + 동기화 서비스 (A-US-01).

동기화 원칙(backend-design §3.3):
  - AD에 없는 사용자 → **soft delete**(이력·FK 무결성 보존, 오탐 복구 가능)
  - **AD 조회 실패(네트워크 장애) ≠ 진짜 삭제** — 실패 시 아무도 지우지 않고 중단
  - objectGUID 불일치 → 재사용으로 판단해 재프로비저닝
"""

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.errors import AdError, NotFound
from app.models import AdConnection, User
from app.repositories.cluster import AdConnectionRepository
from app.repositories.identity import UserRepository
from app.services.audit import AuditService
from app.services.auth import AD_BIND_SECRET_REF, AuthService


@dataclass
class SyncResult:
    created: int = 0
    updated: int = 0
    deactivated: int = 0
    skipped_reason: str | None = None

    @property
    def ok(self) -> bool:
        return self.skipped_reason is None

    def summary(self) -> str:
        if self.skipped_reason:
            return f"중단: {self.skipped_reason}"
        return f"신규 {self.created} · 갱신 {self.updated} · 비활성 {self.deactivated}"


class AdService:
    def __init__(self, session: Session, auth: AuthService):
        self.session = session
        self.auth = auth
        self.conns = AdConnectionRepository(session)
        self.users = UserRepository(session)
        self.audit = AuditService(session)

    def get_connection(self) -> AdConnection:
        conn = self.conns.get_single()
        if conn is None:
            raise NotFound("AD 연결이 설정되어 있지 않습니다.")
        return conn

    def upsert_connection(self, *, actor: User, bind_password: str | None = None, **fields) -> AdConnection:
        conn = self.conns.get_single() or AdConnection()
        for key, value in fields.items():
            if value is not None:
                setattr(conn, key, value)
        if bind_password:
            # 실값은 Secret 저장소에만. DB엔 참조만 남는다.
            self.auth.secrets.put(AD_BIND_SECRET_REF, bind_password)
            conn.bind_secret_ref = AD_BIND_SECRET_REF
        if conn.id is None:
            self.conns.add(conn)
        self.audit.record(actor=actor, action="AD_CONNECTION_UPDATE", target=conn.ldaps_url)
        self.session.commit()
        return conn

    def test_connection(self) -> bool:
        return self.auth.ad_client(self.get_connection()).test_connection()

    def sync(self, *, actor: User | None = None) -> SyncResult:
        conn = self.get_connection()
        client = self.auth.ad_client(conn)
        result = SyncResult()

        try:
            ad_users = client.list_users()
        except AdError as exc:
            # 장애를 삭제로 오인하면 전 사용자가 비활성화된다. 아무것도 지우지 않는다.
            result.skipped_reason = f"AD 조회 실패 — {exc.message}"
            conn.last_sync_at = datetime.now(timezone.utc)
            conn.last_sync_result = result.summary()
            self.session.commit()
            return result

        seen_guids: set[str] = set()
        for ad_user in ad_users:
            seen_guids.add(ad_user.object_guid)
            existed = self.users.get_by_guid(ad_user.object_guid) is not None
            self.auth.provision(ad_user, role_code="USER")
            if existed:
                result.updated += 1
            else:
                result.created += 1

        now = datetime.now(timezone.utc)
        for user in self.users.list():
            if user.deleted_at is not None or user.ad_object_guid in seen_guids:
                continue
            user.is_active = False
            user.deleted_at = now  # soft delete — hard delete 지양
            result.deactivated += 1

        conn.last_sync_at = now
        conn.last_sync_result = result.summary()
        self.audit.record(actor=actor, action="AD_SYNC", target=conn.ldaps_url, detail=result.summary())
        self.session.commit()
        return result
