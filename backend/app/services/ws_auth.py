"""웹소켓 토큰 인증 (U-SH-01 터미널, U-IA-02 데스크톱 공용).

브라우저 웹소켓은 Authorization 헤더를 붙일 수 없어 토큰을 subprotocol로 받는다.
검증 규칙은 **HTTP와 같아야 한다**(서명 + Redis 세션 존재 + 계정 활성) — 웹소켓만
느슨해지면 그쪽이 우회 경로가 된다. 그래서 한 곳에 둔다.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import Unauthenticated
from app.core.redis_client import SessionStore
from app.core.security import decode_session_token
from app.models import User
from app.repositories.identity import UserRepository


def authenticate_ws_token(
    session: Session, *, settings: Settings, sessions: SessionStore, token: str
) -> User:
    payload = decode_session_token(settings, token)
    sid = str(payload.get("sid") or "")
    data = sessions.get(sid) if sid else None
    if data is None:
        raise Unauthenticated("세션이 만료되었거나 로그아웃되었습니다.")
    user = UserRepository(session).get_by_guid(data.user_guid)
    if user is None or not user.is_active or user.deleted_at is not None:
        raise Unauthenticated("비활성화된 계정입니다.")
    return user
