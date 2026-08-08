"""Redis 래퍼 — 세션·권한 캐시·분산락 (backend-design §4, §5.5).

`RedisLike`는 실제 redis 클라이언트와 테스트 fake가 공유하는 최소 인터페이스다.
Pod 로컬 캐시는 멀티 replica에서 불일치를 만들므로 사용하지 않는다(§4.2).
"""

import hashlib
import json
import secrets
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Protocol


class RedisLike(Protocol):
    def setex(self, name: str, time: int, value: str) -> object: ...
    def get(self, name: str) -> object: ...
    def exists(self, *names: str) -> int: ...
    def delete(self, *names: str) -> int: ...
    def set(self, name: str, value: str, nx: bool = False, ex: int | None = None) -> object: ...
    def sadd(self, name: str, *values: str) -> int: ...
    def srem(self, name: str, *values: str) -> int: ...
    def smembers(self, name: str) -> set: ...
    def expire(self, name: str, time: int) -> object: ...


@dataclass(frozen=True)
class SessionData:
    """세션 레코드 — **신원의 정본**.

    사용자 조회는 이 레코드의 `user_guid`로만 한다. JWT의 `sub`(username)를 키로
    쓰면 sAMAccountName이 재사용될 때 옛 토큰이 동명이인의 세션에 올라탈 수 있다.
    """

    sid: str
    user_guid: str
    username: str


class SessionStore:
    """세션 ID 기반 저장소.

    키를 username이 아니라 **난수 sid**로 잡아서 (1) 이름 재사용 충돌을 원천 제거하고
    (2) 기기별 개별 로그아웃을 가능하게 한다. 사용자 단위 강제 로그아웃(§4.1)은
    `user_sessions:{guid}` 역인덱스로 지원한다.
    """

    def __init__(self, redis: RedisLike, ttl_seconds: int):
        self._redis = redis
        self._ttl = ttl_seconds

    @staticmethod
    def _key(sid: str) -> str:
        return f"session:{sid}"

    @staticmethod
    def _index_key(user_guid: str) -> str:
        return f"user_sessions:{user_guid}"

    def create(self, *, user_guid: str, username: str) -> SessionData:
        sid = secrets.token_urlsafe(32)
        data = SessionData(sid=sid, user_guid=user_guid, username=username)
        self._redis.setex(
            self._key(sid), self._ttl, json.dumps({"guid": user_guid, "username": username})
        )
        index = self._index_key(user_guid)
        self._redis.sadd(index, sid)
        # 역인덱스도 세션과 함께 늙게 한다 — 무한정 자라지 않도록.
        self._redis.expire(index, self._ttl)
        return data

    def get(self, sid: str) -> SessionData | None:
        raw = self._redis.get(self._key(sid))
        if raw is None:
            return None
        if isinstance(raw, bytes):
            raw = raw.decode()
        try:
            payload = json.loads(raw)
        except ValueError:
            return None
        return SessionData(sid=sid, user_guid=payload["guid"], username=payload["username"])

    def revoke(self, sid: str) -> None:
        """단일 세션 종료(해당 기기만 로그아웃)."""
        data = self.get(sid)
        self._redis.delete(self._key(sid))
        if data is not None:
            self._redis.srem(self._index_key(data.user_guid), sid)

    def revoke_all(self, user_guid: str) -> int:
        """이 사용자의 모든 세션 종료 — 강제 로그아웃·비활성화 시 사용(§4.1)."""
        index = self._index_key(user_guid)
        members = {m.decode() if isinstance(m, bytes) else str(m) for m in self._redis.smembers(index)}
        for sid in members:
            self._redis.delete(self._key(sid))
        self._redis.delete(index)
        return len(members)


class RefreshTokenStore:
    """refresh 토큰 저장소 — **원문을 저장하지 않는다.**

    Redis가 새어도 토큰을 되살릴 수 없도록 해시만 둔다(세션 sid와 같은 취급).
    쓰면 **회전한다**: 옛 토큰을 지우고 새 토큰을 발급한다. 이미 쓴 토큰이 다시 오면
    **탈취 신호**로 보고 그 세션 전체를 끊는다 — 정상 클라이언트는 같은 토큰을 두 번
    쓰지 않는다.
    """

    def __init__(self, redis: RedisLike, ttl_seconds: int):
        self._redis = redis
        self._ttl = ttl_seconds

    @staticmethod
    def _key(token: str) -> str:
        return f"refresh:{hashlib.sha256(token.encode()).hexdigest()}"

    def issue(self, *, sid: str) -> str:
        token = secrets.token_urlsafe(48)
        self._redis.setex(self._key(token), self._ttl, sid)
        return token

    def consume(self, token: str) -> str | None:
        """유효하면 sid를 돌려주고 **그 토큰은 즉시 폐기**한다. 아니면 None."""
        key = self._key(token)
        raw = self._redis.get(key)
        if raw is None:
            return None
        self._redis.delete(key)
        return raw.decode() if isinstance(raw, bytes) else str(raw)

    def revoke(self, token: str) -> None:
        self._redis.delete(self._key(token))


class PermissionCache:
    """role → permission 매핑 캐시. 거의 불변이라 TTL + 명시적 무효화(§4.1)."""

    def __init__(self, redis: RedisLike, ttl_seconds: int):
        self._redis = redis
        self._ttl = ttl_seconds

    @staticmethod
    def _key(role_code: str) -> str:
        return f"rolePerm:{role_code}"

    def get(self, role_code: str) -> set[str] | None:
        raw = self._redis.get(self._key(role_code))
        if raw is None:
            return None
        if isinstance(raw, bytes):
            raw = raw.decode()
        return set(filter(None, str(raw).split(",")))

    def put(self, role_code: str, permissions: set[str]) -> None:
        self._redis.setex(self._key(role_code), self._ttl, ",".join(sorted(permissions)))

    def invalidate(self, role_code: str) -> None:
        self._redis.delete(self._key(role_code))


@contextmanager
def redis_lock(redis: RedisLike, key: str, timeout: int = 300):
    """배치 중복 실행 방지용 분산락 (§5.5, 멀티 replica 대응)."""
    acquired = bool(redis.set(key, "locked", nx=True, ex=timeout))
    try:
        yield acquired
    finally:
        if acquired:
            redis.delete(key)


def build_redis(url: str) -> RedisLike:
    import redis as redis_lib

    return redis_lib.Redis.from_url(url, decode_responses=True)
