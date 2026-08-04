"""사용자 서비스 (A-US-01, C-02).

AD가 소유하는 신원 필드(username·display_name·email)는 포털에서 수정하지 않는다.
포털이 관리하는 것은 역할(role)과 활성 여부뿐이다(정의서 §1.2).
"""

from sqlalchemy.orm import Session

from app.core.errors import Conflict, NotFound, ValidationFailed
from app.core.redis_client import PermissionCache, SessionStore
from app.models import User
from app.repositories.identity import RoleRepository, UserRepository
from app.services.audit import AuditService


class UserService:
    def __init__(
        self,
        session: Session,
        *,
        permission_cache: PermissionCache | None = None,
        sessions: SessionStore | None = None,
    ):
        self.session = session
        self.users = UserRepository(session)
        self.roles = RoleRepository(session)
        self.audit = AuditService(session)
        self.permission_cache = permission_cache
        self.sessions = sessions

    def search(self, **kwargs) -> tuple[list[User], int]:
        return self.users.search(**kwargs)

    def get(self, guid: str) -> User:
        user = self.users.get_by_guid(guid)
        if user is None or user.deleted_at is not None:
            raise NotFound("사용자를 찾을 수 없습니다.", detail={"guid": guid})
        return user

    def update(
        self,
        guid: str,
        *,
        actor: User,
        role_code: str | None = None,
        is_active: bool | None = None,
    ) -> User:
        user = self.get(guid)
        changes: list[str] = []

        if role_code is not None:
            role = self.roles.get_by_code(role_code)
            if role is None:
                raise ValidationFailed("존재하지 않는 역할입니다.", detail={"role": role_code})
            if user.role_id != role.id:
                # 마지막 ADMIN의 역할을 내리면 아무도 관리할 수 없게 된다.
                self._guard_last_admin(user, new_role_code=role_code)
                changes.append(f"role={role_code}")
                user.role_id = role.id

        if is_active is not None and user.is_active != is_active:
            if not is_active:
                self._guard_last_admin(user, new_role_code=None)
                # 비활성화는 즉시 효력이 있어야 한다 — 이미 발급된 세션을 모두 끊는다(§4.1).
                if self.sessions is not None:
                    self.sessions.revoke_all(user.ad_object_guid)
            changes.append(f"is_active={is_active}")
            user.is_active = is_active

        if changes:
            self.audit.record(
                actor=actor,
                action="USER_UPDATE",
                target=user.username,
                detail=", ".join(changes),
            )
        self.session.commit()
        # role_id만 바꾸면 이미 로드된 role 관계가 옛 값을 들고 있어 응답이 어긋난다.
        self.session.refresh(user)
        return user

    def _guard_last_admin(self, user: User, *, new_role_code: str | None) -> None:
        current = user.role.code if user.role else None
        if current != "ADMIN" or new_role_code == "ADMIN":
            return
        if self.users.count_by_role("ADMIN") <= 1:
            raise Conflict("마지막 관리자의 권한은 해제할 수 없습니다.")
