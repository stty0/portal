"""포털 세션 JWT 발급/검증 (backend-design §4).

Slurm JWT(`X-SLURM-USER-TOKEN`)와는 별개다 — 이쪽은 브라우저↔포털 세션용.
"""

from datetime import datetime, timedelta, timezone
from typing import Any

from jose import JWTError, jwt

from app.core.config import Settings
from app.core.errors import Unauthenticated


def create_session_token(
    settings: Settings, *, sid: str, username: str, guid: str, role: str
) -> str:
    """포털 세션 JWT.

    권한의 근거는 `sid`뿐이다 — `sub`/`guid`/`role`은 로그·디버깅용 부가 정보이며
    인가 판단에 쓰지 않는다(세션 레코드와 DB가 정본).
    """
    now = datetime.now(timezone.utc)
    payload = {
        "sid": sid,  # 세션 레코드 키 (신원 조회의 유일한 출처)
        "sub": username,  # 참고용 — sAMAccountName은 변경·재사용될 수 있다
        "guid": guid,
        "role": role,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=settings.jwt_ttl_seconds)).timestamp()),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_session_token(settings: Settings, token: str) -> dict[str, Any]:
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except JWTError as exc:
        raise Unauthenticated("세션 토큰이 유효하지 않거나 만료되었습니다.", detail=str(exc)) from exc


def decode_slurm_token_exp(token: str) -> datetime | None:
    """Slurm JWT의 `exp`만 서명 검증 없이 읽는다 (backend-design §2.2).

    포털은 Slurm JWT의 서명키를 갖지 않으므로 만료 시각 파악 용도로만 디코드한다.
    """
    try:
        claims = jwt.get_unverified_claims(token)
    except JWTError:
        return None
    exp = claims.get("exp")
    if not exp:
        return None
    return datetime.fromtimestamp(int(exp), tz=timezone.utc)
