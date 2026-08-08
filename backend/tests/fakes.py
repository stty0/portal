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
        """만료 시각을 **실제로** 다시 잡는다.

        예전에는 `True`만 돌려주는 껍데기였다. 그 상태로는 세션 유휴 슬라이딩을
        테스트할 수 없다 — 만료가 밀렸는지 확인할 방법이 없기 때문이다.
        """
        if name in self.store:
            value, _ = self.store[name]
            self.store[name] = (value, time.time() + time_)
            return True
        if name in self.sets:
            return True
        return False


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
        #: 테스트가 갈아끼울 수 있게 필드로 둔다(GPU 파티션 판별 등).
        self.nodes_payload: dict[str, Any] = {
            "nodes": [{"name": "cn01", "state": ["IDLE"], "cpus": 8}], "errors": []
        }
        self.next_job_id = "90001"
        # slurmdbd 쓰기는 HTTP 200으로도 본문 errors로 실패를 알린다 — 그 상황 재현용
        self.write_errors: list[dict[str, Any]] = []

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

    def get_nodes(self, *, as_user=None):
        self._record("get_nodes", as_user=as_user)
        return self.nodes_payload

    def update_node(self, name, patch):
        self._record("update_node", node=name, patch=patch)
        return {"errors": [], "warnings": []}

    def create_reservation(self, desc):
        self._record("create_reservation", desc=desc)
        return {"errors": [], "warnings": []}

    def delete_reservation(self, name):
        self._record("delete_reservation", reservation=name)
        return {"errors": [], "warnings": []}

    def get_partitions(self, *, as_user=None):
        self._record("get_partitions", as_user=as_user)
        # slurmdbd 미연결 시 errors가 채워져도 목록은 정상적으로 온다 — 실물 관측 결과.
        return {
            "partitions": [{"name": "debug", "nodes": {"total": 1}}],
            "errors": [{"error": "Connection refused", "source": "slurmdb_tres_get"}],
        }

    def get_reservations(self, *, as_user=None):
        self._record("get_reservations", as_user=as_user)
        return {"reservations": [], "errors": []}

    def get_accounting_jobs(self, *, as_user=None, **params):
        self._record("get_accounting_jobs", as_user=as_user, **params)
        # slurmdbd가 users 필터를 무시하는 상황을 재현 — 서비스가 한 번 더 걸러야 한다.
        return {"jobs": self.jobs}

    def get_accounts(self, *, as_user=None):
        self._record("get_accounts", as_user=as_user)
        # 실물에서도 accounts의 associations는 비어 온다 — 매핑은 /associations로 받아야 한다.
        return {
            "accounts": [
                {"name": "hpc", "description": "HPC", "organization": "org",
                 "coordinators": [], "associations": []}
            ]
        }

    def get_associations(self, *, as_user=None):
        self._record("get_associations", as_user=as_user)
        return {
            "associations": [
                # user가 빈 행 = 계정 자체 노드 — 사용자 목록에 넣으면 안 된다
                {"account": "hpc", "user": "", "cluster": "seoul-hpc", "qos": ["normal", "short"]},
                {"account": "hpc", "user": "jrpark", "cluster": "seoul-hpc", "partition": "",
                 "qos": ["normal"], "is_default": True, "shares_raw": 1},
                # 남의 연결 — 제출 폼 선택지에 섞이면 안 된다
                {"account": "other", "user": "someone-else", "cluster": "seoul-hpc",
                 "qos": ["normal"], "is_default": True, "shares_raw": 1},
            ]
        }

    def get_qos(self, *, as_user=None):
        self._record("get_qos", as_user=as_user)
        return {
            "qos": [
                {
                    "name": "normal",
                    "description": "기본",
                    "priority": {"set": True, "infinite": False, "number": 0},
                    "usage_factor": {"set": True, "infinite": False, "number": 1.0},
                    "flags": [],
                    "limits": {
                        "max": {
                            # 무제한은 infinite=True로 온다 — None으로 접혀야 한다
                            "wall_clock": {"per": {"job": {"set": False, "infinite": True, "number": 0}}},
                            "jobs": {"per": {"user": {"set": True, "infinite": False, "number": 4}}},
                        }
                    },
                }
            ]
        }

    def create_qos(self, qos):
        self._record("create_qos", qos=qos)
        return {"errors": self.write_errors, "warnings": []}

    def delete_qos(self, name):
        self._record("delete_qos", qos_name=name)
        return {"errors": self.write_errors, "warnings": []}

    def create_account(self, account, cluster_name):
        self._record("create_account", account=account, cluster_name=cluster_name)
        return {"errors": self.write_errors, "warnings": []}

    def delete_account(self, name):
        self._record("delete_account", account_name=name)
        return {"errors": self.write_errors, "warnings": []}

    def add_user_association(self, *, username, account, cluster_name):
        self._record("add_user_association", username=username, account=account,
                     cluster_name=cluster_name)
        return {"errors": self.write_errors, "warnings": []}

    def set_association_qos(self, *, account, username, cluster_name, qos):
        self._record("set_association_qos", account=account, username=username,
                     cluster_name=cluster_name, qos=qos)
        return {"errors": self.write_errors, "warnings": []}

    def delete_association(self, *, username, account, cluster_name):
        self._record("delete_association", username=username, account=account,
                     cluster_name=cluster_name)
        return {"errors": self.write_errors, "warnings": []}

    def get_slurm_user(self, username, *, as_user=None):
        self._record("get_slurm_user", username=username, as_user=as_user)
        return {"users": [{"name": username, "associations": [{"account": "hpc"}]}]}


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
