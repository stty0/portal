"""외부 의존 fake — 실제 Redis·AD·slurmrestd 없이 전 계층을 검증한다."""

import time
from typing import Any

from app.clients.ad.client import AdUser
from app.core.errors import AdError


class FakeRedis:
    """SessionStore·PermissionCache·redis_lock이 쓰는 최소 명령만 구현."""

    def __init__(self):
        self.store: dict[str, tuple[str, float | None]] = {}
        self.sets: dict[str, set[str]] = {}

    def _alive(self, name: str) -> bool:
        item = self.store.get(name)
        if item is None:
            return False
        _, expires = item
        if expires is not None and expires <= time.time():
            del self.store[name]
            return False
        return True

    def setex(self, name: str, time_: int, value: str):
        self.store[name] = (value, time.time() + time_)
        return True

    def get(self, name: str):
        return self.store[name][0] if self._alive(name) else None

    def exists(self, *names: str) -> int:
        return sum(1 for n in names if self._alive(n))

    def delete(self, *names: str) -> int:
        removed = sum(1 for n in names if self.store.pop(n, None) is not None)
        removed += sum(1 for n in names if self.sets.pop(n, None) is not None)
        return removed

    def set(self, name: str, value: str, nx: bool = False, ex: int | None = None):
        if nx and self._alive(name):
            return None
        self.store[name] = (value, time.time() + ex if ex else None)
        return True

    # --- set 연산 (세션 역인덱스용) ---
    def sadd(self, name: str, *values: str) -> int:
        members = self.sets.setdefault(name, set())
        before = len(members)
        members.update(values)
        return len(members) - before

    def srem(self, name: str, *values: str) -> int:
        members = self.sets.get(name, set())
        before = len(members)
        members.difference_update(values)
        return before - len(members)

    def smembers(self, name: str) -> set:
        return set(self.sets.get(name, set()))

    def expire(self, name: str, time_: int):
        return True


class FakeAdClient:
    """AD 디렉터리를 메모리로 흉내낸다. `fail`을 켜면 네트워크 장애를 재현한다."""

    def __init__(self, users: list[AdUser] | None = None, passwords: dict[str, str] | None = None):
        self.users = list(users or [])
        self.passwords = dict(passwords or {})
        self.fail = False

    def _guard(self):
        if self.fail:
            raise AdError("AD 서버에 연결할 수 없습니다.")

    def find_user(self, username: str) -> AdUser | None:
        self._guard()
        return next((u for u in self.users if u.username == username), None)

    def authenticate(self, username: str, password: str) -> AdUser:
        self._guard()
        user = self.find_user(username)
        if user is None or not password or self.passwords.get(username) != password:
            raise AdError("자격증명이 올바르지 않습니다.")
        return user

    def list_users(self) -> list[AdUser]:
        self._guard()
        return list(self.users)

    def test_connection(self) -> bool:
        self._guard()
        return True


class FakeSlurmClient:
    """SlurmrestdClient 대역. 호출 인자를 기록해 impersonation을 검증한다."""

    def __init__(self, jobs: list[dict[str, Any]] | None = None):
        self.jobs = list(jobs or [])
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.cancelled: list[str] = []
        self.next_job_id = "90001"

    def _record(self, name: str, **kw):
        self.calls.append((name, kw))

    def ping(self):
        self._record("ping")
        return {"meta": {"cluster": "seoul-hpc"}}

    def get_jobs(self, *, as_user=None, **params):
        self._record("get_jobs", as_user=as_user, **params)
        return {"jobs": self.jobs}

    def get_job(self, job_id, *, as_user=None):
        self._record("get_job", job_id=job_id, as_user=as_user)
        return {"jobs": [j for j in self.jobs if str(j.get("job_id")) == str(job_id)]}

    def submit_job(self, spec, *, as_user):
        self._record("submit_job", spec=spec, as_user=as_user)
        return {"job_id": self.next_job_id}

    def cancel_job(self, job_id, *, as_user):
        self._record("cancel_job", job_id=job_id, as_user=as_user)
        self.cancelled.append(str(job_id))
        return {"ok": True}

    def update_job(self, job_id, patch, *, as_user):
        self._record("update_job", job_id=job_id, patch=patch, as_user=as_user)
        return {"ok": True}

    def get_accounting_jobs(self, *, as_user=None, **params):
        self._record("get_accounting_jobs", as_user=as_user, **params)
        # slurmdbd가 users 필터를 무시하는 상황을 재현 — 서비스가 한 번 더 걸러야 한다.
        return {"jobs": self.jobs}


class FakeClientFactory:
    """ClusterClientFactory 대역 — 클러스터와 무관하게 같은 fake를 돌려준다."""

    def __init__(self, client: FakeSlurmClient):
        self.client = client
        self.invalidated: list[int] = []

    def slurm(self, cluster, secret_ref):
        return self.client

    def invalidate(self, cluster_id: int) -> None:
        self.invalidated.append(cluster_id)

    def close_all(self) -> None:
        pass
