"""사용자별 API 토큰 (C-01) — 기계 클라이언트용 장수명 자격증명.

브라우저는 HttpOnly 쿠키를, 사람이 붙어 있는 CLI는 로그인 토큰을 쓴다. 그런데
**자동화는 둘 다 못 쓴다** — 액세스 토큰은 30분이고, AD 비밀번호를 스크립트에 박으면
반복 실패로 계정이 잠긴다. 그래서 세 번째 자격증명을 둔다.

설계에서 지킨 것:
  - **원문을 저장하지 않는다.** sha256만 둔다. 분실하면 재발급이지 복구가 아니다.
  - **접두사로 구분한다.** `hpcp_`로 시작하므로 JWT 해독을 시도하지 않아도 되고,
    시크릿 스캐너도 잡을 수 있다.
  - **폐기가 즉시 먹는다.** 조회 때마다 `revoked_at`·`expires_at`을 본다.
"""

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import NotFound, ValidationFailed
from app.models import ApiToken, User
from app.services.audit import AuditService

#: 토큰 접두사. 값이 아니라 **종류**를 알리는 표식이다.
TOKEN_PREFIX = "hpcp_"

#: `last_used_at`을 매 요청 쓰면 요청마다 DB 쓰기가 생긴다. 이 간격보다 최근이면 건너뛴다.
_TOUCH_INTERVAL = timedelta(minutes=5)

#: 한 사람이 무한정 만들지 못하게 한다 — 목록이 관리 불가능해지면 폐기도 안 한다.
MAX_TOKENS_PER_USER = 20


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class ApiTokenService:
    def __init__(self, session: Session):
        self.session = session
        self.audit = AuditService(session)

    def list_for(self, user: User) -> list[ApiToken]:
        """**본인 것만.** 폐기된 것도 보여 준다 — 언제 없앴는지가 정보다."""
        stmt = (
            select(ApiToken)
            .where(ApiToken.user_guid == user.ad_object_guid)
            .order_by(ApiToken.id.desc())
        )
        return list(self.session.scalars(stmt))

    def create(self, *, user: User, name: str, expires_in_days: int | None) -> tuple[ApiToken, str]:
        """(레코드, **원문 토큰**)을 돌려준다. 원문은 여기서만 존재한다."""
        active = [t for t in self.list_for(user) if t.revoked_at is None]
        if len(active) >= MAX_TOKENS_PER_USER:
            raise ValidationFailed(
                f"토큰은 최대 {MAX_TOKENS_PER_USER}개까지 만들 수 있습니다. 쓰지 않는 것을 폐기하세요.",
                detail={"active": len(active)},
            )
        raw = TOKEN_PREFIX + secrets.token_urlsafe(32)
        record = ApiToken(
            user_guid=user.ad_object_guid,
            name=name,
            token_hash=_hash(raw),
            prefix=raw[: len(TOKEN_PREFIX) + 6],
            expires_at=_now() + timedelta(days=expires_in_days) if expires_in_days else None,
        )
        self.session.add(record)
        self.audit.record(actor=user, action="API_TOKEN_CREATE", target=name)
        self.session.commit()
        return record, raw

    def revoke(self, token_id: int, *, user: User) -> ApiToken:
        record = self.session.get(ApiToken, token_id)
        # 남의 토큰은 **없는 것으로 답한다** — 존재 여부가 새면 안 된다.
        if record is None or record.user_guid != user.ad_object_guid:
            raise NotFound("토큰을 찾을 수 없습니다.", detail={"id": token_id})
        if record.revoked_at is None:
            record.revoked_at = _now()
            self.audit.record(actor=user, action="API_TOKEN_REVOKE", target=record.name)
            self.session.commit()
        return record

    def resolve(self, raw: str) -> ApiToken | None:
        """원문 토큰 → 살아 있는 레코드. 폐기·만료면 None."""
        record = self.session.scalars(
            select(ApiToken).where(ApiToken.token_hash == _hash(raw))
        ).first()
        if record is None or record.revoked_at is not None:
            return None
        if record.expires_at is not None and record.expires_at <= _now():
            return None
        self._touch(record)
        return record

    def _touch(self, record: ApiToken) -> None:
        now = _now()
        if record.last_used_at is not None and now - record.last_used_at < _TOUCH_INTERVAL:
            return
        record.last_used_at = now
        self.session.commit()
