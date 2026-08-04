"""사용자·역할·권한 repository (db-erd.md 신원/인가)."""

from sqlalchemy import func, select

from app.models import Permission, Role, RolePermission, User
from app.repositories.base import BaseRepository


class UserRepository(BaseRepository[User]):
    model = User

    def get_by_guid(self, guid: str) -> User | None:
        return self.session.get(User, guid)

    def get_by_username(self, username: str) -> User | None:
        return self.session.scalar(select(User).where(User.username == username))

    def search(
        self,
        *,
        q: str | None = None,
        role_code: str | None = None,
        is_active: bool | None = None,
        include_deleted: bool = False,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[User], int]:
        stmt = select(User)
        if not include_deleted:
            stmt = stmt.where(User.deleted_at.is_(None))
        if q:
            like = f"%{q}%"
            stmt = stmt.where(User.username.like(like) | User.display_name.like(like))
        if role_code:
            stmt = stmt.join(Role, User.role_id == Role.id).where(Role.code == role_code)
        if is_active is not None:
            stmt = stmt.where(User.is_active.is_(is_active))
        total = self.session.scalar(select(func.count()).select_from(stmt.subquery())) or 0
        rows = list(self.session.scalars(stmt.order_by(User.username).limit(limit).offset(offset)))
        return rows, total

    def count_by_role(self, role_code: str) -> int:
        stmt = (
            select(func.count())
            .select_from(User)
            .join(Role, User.role_id == Role.id)
            .where(Role.code == role_code, User.deleted_at.is_(None), User.is_active.is_(True))
        )
        return self.session.scalar(stmt) or 0

    def all_usernames(self) -> set[str]:
        return set(self.session.scalars(select(User.username).where(User.deleted_at.is_(None))))


class RoleRepository(BaseRepository[Role]):
    model = Role

    def get_by_code(self, code: str) -> Role | None:
        return self.session.scalar(select(Role).where(Role.code == code))

    def permissions_of(self, role_code: str) -> set[str]:
        stmt = (
            select(Permission.code)
            .join(RolePermission, RolePermission.permission_id == Permission.id)
            .join(Role, Role.id == RolePermission.role_id)
            .where(Role.code == role_code)
        )
        return set(self.session.scalars(stmt))


class PermissionRepository(BaseRepository[Permission]):
    model = Permission

    def get_by_code(self, code: str) -> Permission | None:
        return self.session.scalar(select(Permission).where(Permission.code == code))
