"""클러스터 서비스 (A-CL-01~04, C-03).

자격증명은 값을 받아 **Secret 저장소에만** 넣고 DB에는 `secret_ref`와 만료만 남긴다.
클러스터 이름은 손으로 받지 않고 REST 연결 테스트 시 slurmrestd에서 조회한다
(정의서 A-CL-02: slurm.conf ClusterName과 자동 일치).
"""

# 이 클래스에는 `list()` 메서드가 있어서, 클래스 본문에서 평가되는 어노테이션의
# `list[...]`가 내장 list가 아니라 그 메서드를 가리킨다(TypeError). 어노테이션 평가를
# 미뤄 이름 충돌을 없앤다. Python 3.14는 기본으로 미루지만 런타임 이미지는 3.13이다.
from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.clients.factory import ClusterClientFactory
from app.core.errors import Conflict, ExternalServiceError, NotFound, ValidationFailed
from app.core.secrets import SecretStore, build_secret_ref
from app.core.security import decode_slurm_token_exp
from app.db.base import utcnow
from app.models import Cluster, ClusterCredential, User
from app.repositories.audit import AuditLogRepository
from app.repositories.cluster import ClusterCredentialRepository, ClusterRepository
from app.services.audit import AuditService

KIND_SLURM_JWT = "SLURM_JWT"
KIND_SSH_KEY = "SSH_KEY"


#: 포털이 노출하는 노드 상태 전이. Slurm은 더 많은 값을 받지만, 운영 화면에서 필요한
#: 것만 연다 — 넓게 열면 오타 하나로 노드를 이상한 상태에 빠뜨릴 수 있다.
NODE_STATES = {"DRAIN", "RESUME", "DOWN", "UNDRAIN"}
#: 사유 없이는 나중에 "왜 빠져 있지?"에 답할 수 없는 전이.
NODE_STATES_NEEDING_REASON = {"DRAIN", "DOWN"}


class ClusterService:
    def __init__(
        self,
        session: Session,
        *,
        secrets: SecretStore,
        client_factory: ClusterClientFactory,
    ):
        self.session = session
        self.secrets = secrets
        self.clients = client_factory
        self.clusters = ClusterRepository(session)
        self.credentials = ClusterCredentialRepository(session)
        self.audit = AuditService(session)

    # --- 조회 -----------------------------------------------------------
    def list(self, *, only_active: bool = True) -> list[Cluster]:
        return self.clusters.list_active() if only_active else self.clusters.list()

    def get(self, cluster_id: int) -> Cluster:
        cluster = self.clusters.get(cluster_id)
        if cluster is None:
            raise NotFound("클러스터를 찾을 수 없습니다.", detail={"cluster_id": cluster_id})
        return cluster

    # --- 등록/수정 ------------------------------------------------------
    def create(self, *, actor: User, alias: str, **fields) -> Cluster:
        """이름 없이 등록한다 — slurm.conf `ClusterName`은 REST 연결 테스트가 채운다.

        중복 검사도 그때 걸린다(`name`이 UNIQUE). 등록 시점에 사람이 지은 이름으로
        중복을 판정하면, 정작 실제 이름이 겹치는 경우를 못 잡는다.
        """
        cluster = Cluster(alias=alias, **{k: v for k, v in fields.items() if v is not None})
        self.clusters.add(cluster)
        if cluster.is_default:
            self.clusters.clear_default(except_id=cluster.id)
        self.audit.record(actor=actor, action="CLUSTER_CREATE", target=alias, cluster_id=cluster.id)
        self.session.commit()
        return cluster

    def update(self, cluster_id: int, *, actor: User, **fields) -> Cluster:
        cluster = self.get(cluster_id)
        changed = []
        for key, value in fields.items():
            if value is not None and getattr(cluster, key, None) != value:
                setattr(cluster, key, value)
                changed.append(key)
        if cluster.is_default:
            self.clusters.clear_default(except_id=cluster.id)
        if {"slurmrestd_url", "api_version"} & set(changed):
            # 엔드포인트가 바뀌면 풀에 남은 client는 옛 주소를 가리킨다.
            self.clients.invalidate(cluster.id)
        self.audit.record(
            actor=actor,
            action="CLUSTER_UPDATE",
            target=label_of(cluster),
            cluster_id=cluster.id,
            detail=", ".join(changed),
        )
        self.session.commit()
        return cluster

    def deactivate(self, cluster_id: int, *, actor: User) -> None:
        """삭제는 비활성화로 처리한다 — 감사 로그·이력의 FK를 살려 둔다."""
        cluster = self.get(cluster_id)
        cluster.is_active = False
        cluster.is_default = False
        self.clients.invalidate(cluster.id)
        self.audit.record(
            actor=actor, action="CLUSTER_DEACTIVATE", target=label_of(cluster), cluster_id=cluster.id
        )
        self.session.commit()

    def purge(self, cluster_id: int, *, actor: User) -> None:
        """비활성 클러스터를 실제로 삭제한다 (A-CL-02 확장).

        감사 이력 보존이 우선이므로 다른 테이블이 이 클러스터를 참조하고 있으면 거부한다.
        즉 "잘못 등록해서 쓴 적 없는 클러스터"만 지워진다.
        """
        cluster = self.get(cluster_id)
        if cluster.is_active:
            raise Conflict(
                "활성 클러스터는 삭제할 수 없습니다. 먼저 비활성화하세요.",
                detail={"cluster_id": cluster_id},
            )
        references = self.clusters.count_references(cluster_id)
        if references:
            raise Conflict(
                "이 클러스터를 참조하는 이력이 있어 삭제할 수 없습니다. 비활성 상태로 유지됩니다.",
                detail=references,
            )

        label = label_of(cluster)
        # cluster_credential 행은 관계의 cascade가 지운다. 여기선 Secret 저장소의 실값을 파기한다.
        for credential in self.credentials.list_for_cluster(cluster_id):
            self.secrets.delete(credential.secret_ref)
        self.clients.invalidate(cluster_id)
        self.clusters.delete(cluster)
        # 삭제 기록 자체는 cluster_id를 남기지 않는다 — 방금 지운 행을 가리킬 수 없다.
        self.audit.record(actor=actor, action="CLUSTER_PURGE", target=label)
        self.session.commit()

    # --- 자격증명 -------------------------------------------------------
    def put_credential(
        self, cluster_id: int, *, actor: User, kind: str, value: str
    ) -> ClusterCredential:
        cluster = self.get(cluster_id)
        if kind not in (KIND_SLURM_JWT, KIND_SSH_KEY):
            raise ValidationFailed("지원하지 않는 자격증명 종류입니다.", detail={"kind": kind})

        secret_ref = build_secret_ref(f"cluster/{cluster.id}", kind)
        self.secrets.put(secret_ref, value)  # 실값은 여기까지만
        credential = ClusterCredential(
            cluster_id=cluster.id,
            kind=kind,
            secret_ref=secret_ref,
            expires_at=decode_slurm_token_exp(value) if kind == KIND_SLURM_JWT else None,
        )
        self.credentials.add(credential)
        # 무중단 교체: 캐시만 비우면 다음 호출부터 새 토큰이 쓰인다.
        self.clients.invalidate(cluster.id)
        self.audit.record(
            actor=actor,
            action="CLUSTER_CREDENTIAL_PUT",
            target=label_of(cluster),
            cluster_id=cluster.id,
            detail=f"kind={kind}",  # 값은 기록하지 않는다
        )
        self.session.commit()
        return credential

    def _slurm_secret_ref(self, cluster: Cluster) -> str:
        credential = self.credentials.get_active(cluster.id, KIND_SLURM_JWT)
        if credential is None:
            raise ValidationFailed(
                "클러스터 JWT가 등록되어 있지 않습니다.", detail={"cluster_id": cluster.id}
            )
        return credential.secret_ref

    def slurm_client(self, cluster: Cluster):
        return self.clients.slurm(cluster, self._slurm_secret_ref(cluster))

    # --- 연결 테스트 (A-CL-02) ------------------------------------------
    def test_rest(self, cluster_id: int, *, actor: User) -> dict[str, Any]:
        cluster = self.get(cluster_id)
        try:
            payload = self.slurm_client(cluster).ping()
        except Exception:
            # 실패도 헬스 결과다 — 목록의 상태 컬럼이 이걸 읽는다(A-CL-01).
            self._record_health(cluster, ok=False, actor=actor)
            raise
        detected = _extract_cluster_name(payload)
        if detected and cluster.name != detected:
            # slurm.conf의 ClusterName이 정본이다. 이름은 여기서 처음 정해진다.
            # **중복 판정도 여기다** — 사람이 지은 이름이 아니라 실제 이름이 겹치는지가
            # 문제이고, 그건 연결해 보기 전에는 알 수 없다.
            other = self.clusters.get_by_name(detected)
            if other is not None and other.id != cluster.id:
                self._record_health(cluster, ok=True, actor=actor)
                self.session.commit()
                raise Conflict(
                    f"'{detected}' 클러스터가 이미 등록되어 있습니다.",
                    detail={"cluster_name": detected, "registered_id": other.id},
                )
            cluster.name = detected
        self._record_health(cluster, ok=True, actor=actor)
        return {"ok": True, "cluster_name": cluster.name, "api_version": cluster.api_version}

    # --- 자원 조회 (A-ND-02·03·04, U-CL-02) ------------------------------
    def nodes(self, cluster_id: int) -> list[dict[str, Any]]:
        return _items(self.slurm_client(self.get(cluster_id)).get_nodes(), "nodes")

    def partitions(self, cluster_id: int) -> list[dict[str, Any]]:
        return _items(self.slurm_client(self.get(cluster_id)).get_partitions(), "partitions")

    def reservations(self, cluster_id: int) -> list[dict[str, Any]]:
        return _items(self.slurm_client(self.get(cluster_id)).get_reservations(), "reservations")

    # --- 노드 상태 제어 (A-ND-01) ----------------------------------------
    def set_node_state(
        self, cluster_id: int, name: str, *, actor: User, state: str, reason: str | None
    ) -> dict[str, Any]:
        """노드를 drain / resume / down 시킨다.

        `DRAIN`·`DOWN`은 **사유를 요구한다** — Slurm이 사유를 노드에 붙여 두고,
        나중에 "왜 빠져 있지?"를 답하는 유일한 단서가 된다. 여기서 막지 않으면
        slurmrestd가 거부하거나 빈 사유가 그대로 남는다.
        """
        cluster = self.get(cluster_id)
        target = state.upper()
        if target not in NODE_STATES:
            raise ValidationFailed(
                "지원하지 않는 노드 상태입니다.",
                detail={"state": state, "supported": sorted(NODE_STATES)},
            )
        text = (reason or "").strip()
        if target in NODE_STATES_NEEDING_REASON and not text:
            raise ValidationFailed("사유를 입력하세요.", detail={"state": target})

        patch: dict[str, Any] = {"state": [target]}
        if text:
            patch["reason"] = text
        payload = self.slurm_client(cluster).update_node(name, patch)
        _raise_on_errors(payload)
        self.audit.record(
            actor=actor,
            action="NODE_STATE",
            target=name,
            cluster_id=cluster.id,
            detail=f"{target}{f' — {text}' if text else ''}",
        )
        self.session.commit()
        return {"ok": True, "node": name, "state": target}

    # --- 예약 (A-ND-04) ---------------------------------------------------
    def create_reservation(
        self, cluster_id: int, *, actor: User, name: str, desc: dict[str, Any], summary: str
    ) -> dict[str, Any]:
        """예약 생성. 요청 본문 조립·검증은 스키마가 끝내고 여기는 호출과 기록만 한다."""
        cluster = self.get(cluster_id)
        payload = self.slurm_client(cluster).create_reservation(desc)
        _raise_on_errors(payload)
        self.audit.record(
            actor=actor,
            action="RESERVATION_CREATE",
            target=name,
            cluster_id=cluster.id,
            detail=summary,
        )
        self.session.commit()
        return {"ok": True, "name": name}

    def delete_reservation(self, cluster_id: int, name: str, *, actor: User) -> dict[str, Any]:
        cluster = self.get(cluster_id)
        payload = self.slurm_client(cluster).delete_reservation(name)
        _raise_on_errors(payload)
        self.audit.record(
            actor=actor, action="RESERVATION_DELETE", target=name, cluster_id=cluster.id
        )
        self.session.commit()
        return {"ok": True, "name": name}

    def accounts(self, cluster_id: int) -> list[dict[str, Any]]:
        """Slurm 계정과 소속 사용자 매핑 (A-US-02).

        계정 응답의 `associations`는 비어 오는 경우가 많아(실측) 연결 정보는
        `/associations`에서 따로 받아 계정별로 묶는다. 사용자가 빈 association은
        **계정 자체의 노드**라 사용자 목록에서 제외한다.
        """
        client = self.slurm_client(self.get(cluster_id))
        accounts = _items(client.get_accounts(), "accounts")
        associations = _items(client.get_associations(), "associations")

        account_qos: dict[str, list[str]] = {}
        by_account: dict[str, list[dict[str, Any]]] = {}
        for assoc in associations:
            if not assoc.get("user"):
                # 사용자가 빈 행 = 계정 자체 노드. 계정 단위 QOS가 여기 붙는다.
                account_qos[str(assoc.get("account") or "")] = list(assoc.get("qos") or [])
                continue
            by_account.setdefault(str(assoc.get("account") or ""), []).append(
                {
                    "user": assoc.get("user"),
                    "cluster": assoc.get("cluster"),
                    "partition": assoc.get("partition") or None,
                    "qos": assoc.get("qos") or [],
                    "is_default": bool(assoc.get("is_default")),
                    "shares_raw": assoc.get("shares_raw"),
                }
            )
        return [
            {
                "name": a.get("name"),
                "description": a.get("description"),
                "organization": a.get("organization"),
                "coordinators": a.get("coordinators") or [],
                "qos": account_qos.get(str(a.get("name") or ""), []),
                "users": by_account.get(str(a.get("name") or ""), []),
            }
            for a in accounts
        ]

    # --- 대시보드 (A-DB-02) ----------------------------------------------
    def metrics(self, cluster_id: int) -> dict[str, Any]:
        """클러스터 부하 요약.

        Prometheus 없이 **slurmctld의 노드 상태에서 직접 집계**한다. Slurm이 이미
        노드별 할당 CPU·메모리를 들고 있어서, 별도 수집기 없이도 "지금 얼마나 쓰이는가"는
        답할 수 있다. 시계열·상세 지표가 필요해지면 그때 Prometheus를 붙인다(정의서 A-DB-02).
        """
        nodes = self.nodes(cluster_id)
        states: dict[str, int] = {}
        cpus = alloc_cpus = memory = alloc_memory = 0
        load = 0.0
        for node in nodes:
            for state in node.get("state") or []:
                key = str(state)
                states[key] = states.get(key, 0) + 1
            cpus += int(node.get("cpus") or 0)
            alloc_cpus += int(node.get("alloc_cpus") or 0)
            memory += int(node.get("real_memory") or 0)
            alloc_memory += int(node.get("alloc_memory") or 0)
            load += float(node.get("cpu_load") or 0)

        return {
            "nodes": len(nodes),
            "states": [{"state": k, "count": v} for k, v in sorted(states.items())],
            "cpus": cpus,
            "alloc_cpus": alloc_cpus,
            "cpu_pct": round(alloc_cpus / cpus * 100, 1) if cpus else None,
            "memory_mb": memory,
            "alloc_memory_mb": alloc_memory,
            "memory_pct": round(alloc_memory / memory * 100, 1) if memory else None,
            # cpu_load는 노드별 load average 합이다 — CPU 수로 나눠 1코어 기준으로 본다.
            "load_per_cpu": round(load / cpus, 2) if cpus else None,
        }

    def events(self, cluster_id: int, *, limit: int = 20) -> list[dict[str, Any]]:
        """최근 이벤트 (A-DB-04) = 이 클러스터를 대상으로 한 감사 로그.

        Slurm 자체 이벤트 로그가 아니라 **포털을 통해 일어난 일**이다. 누가 무엇을
        했는지는 이미 C-05로 기록하고 있어 별도 수집 없이 바로 쓸 수 있다.
        """
        self.get(cluster_id)  # 없는 클러스터면 404
        rows, _total = AuditLogRepository(self.session).search(cluster_id=cluster_id, limit=limit)
        return [
            {
                "at": row.at,
                "actor": row.actor_guid,
                "actor_role": row.actor_role,
                "action": row.action,
                "target": row.target,
                "detail": row.detail,
            }
            for row in rows
        ]

    # --- QOS (A-US-03) ---------------------------------------------------
    def qos(self, cluster_id: int) -> list[dict[str, Any]]:
        """QOS 목록. 중첩된 제한값 구조에서 화면이 쓰는 것만 평평하게 편다."""
        rows = _items(self.slurm_client(self.get(cluster_id)).get_qos(), "qos")
        return [
            {
                "name": q.get("name"),
                "description": q.get("description"),
                "priority": _number(q.get("priority")),
                "usage_factor": _number(q.get("usage_factor")),
                "flags": q.get("flags") or [],
                "max_wall_minutes": _number(
                    _dig(q, "limits", "max", "wall_clock", "per", "job")
                ),
                "max_jobs_per_user": _number(
                    _dig(q, "limits", "max", "jobs", "per", "user")
                ),
                "max_submit_per_user": _number(
                    _dig(q, "limits", "max", "active_jobs", "per", "user")
                ),
            }
            for q in rows
        ]

    def create_qos(
        self, cluster_id: int, *, actor: User, name: str, description: str | None,
        priority: int | None, max_wall_minutes: int | None, max_jobs_per_user: int | None,
    ) -> dict[str, Any]:
        cluster = self.get(cluster_id)
        payload: dict[str, Any] = {"name": name}
        if description:
            payload["description"] = description
        if priority is not None:
            payload["priority"] = {"set": True, "number": priority}
        limits: dict[str, Any] = {}
        if max_wall_minutes is not None:
            limits.setdefault("max", {})["wall_clock"] = {
                "per": {"job": {"set": True, "number": max_wall_minutes}}
            }
        if max_jobs_per_user is not None:
            limits.setdefault("max", {})["jobs"] = {
                "per": {"user": {"set": True, "number": max_jobs_per_user}}
            }
        if limits:
            payload["limits"] = limits
        _raise_on_errors(self.slurm_client(cluster).create_qos(payload))
        self.audit.record(
            actor=actor, action="SLURM_QOS_CREATE", target=name, cluster_id=cluster.id
        )
        self.session.commit()
        return {"ok": True, "name": name}

    def delete_qos(self, cluster_id: int, name: str, *, actor: User) -> dict[str, Any]:
        cluster = self.get(cluster_id)
        if name == "normal":
            raise ValidationFailed("기본 QOS(normal)는 삭제할 수 없습니다.")
        try:
            _raise_on_errors(self.slurm_client(cluster).delete_qos(name))
        except ExternalServiceError as exc:
            # 삭제 거부는 5xx로 온다 — 본문 사유를 꺼내 그대로 보여준다(예: 사용 중인 QOS).
            detail = exc.detail if isinstance(exc.detail, dict) else {}
            body = detail.get("body") if isinstance(detail, dict) else None
            _reject(body.get("errors") if isinstance(body, dict) else None)
            raise
        self.audit.record(
            actor=actor, action="SLURM_QOS_DELETE", target=name, cluster_id=cluster.id
        )
        self.session.commit()
        return {"ok": True}

    # --- 계정 쓰기 (A-US-02) ---------------------------------------------
    def create_account(
        self, cluster_id: int, *, actor: User, name: str, description: str | None,
        organization: str | None,
    ) -> dict[str, Any]:
        cluster = self.get(cluster_id)
        payload = {"name": name}
        if description:
            payload["description"] = description
        if organization:
            payload["organization"] = organization
        _raise_on_errors(
            self.slurm_client(cluster).create_account(payload, cluster.name or "")
        )
        self.audit.record(
            actor=actor, action="SLURM_ACCOUNT_CREATE", target=name, cluster_id=cluster.id
        )
        self.session.commit()
        return {"ok": True, "name": name}

    def delete_account(self, cluster_id: int, name: str, *, actor: User) -> dict[str, Any]:
        cluster = self.get(cluster_id)
        if name == "root":
            # root는 Slurm이 만드는 최상위 계정이다. 지우면 accounting 트리가 무너진다.
            raise ValidationFailed("root 계정은 삭제할 수 없습니다.")
        _raise_on_errors(
            self.slurm_client(cluster).delete_account(name)
        )
        self.audit.record(
            actor=actor, action="SLURM_ACCOUNT_DELETE", target=name, cluster_id=cluster.id
        )
        self.session.commit()
        return {"ok": True}

    def add_account_user(
        self, cluster_id: int, *, actor: User, account: str, username: str
    ) -> dict[str, Any]:
        cluster = self.get(cluster_id)
        _raise_on_errors(
            self.slurm_client(cluster).add_user_association(
                username=username, account=account, cluster_name=cluster.name or ""
            )
        )
        self.audit.record(
            actor=actor,
            action="SLURM_ASSOC_ADD",
            target=f"{account}/{username}",
            cluster_id=cluster.id,
        )
        self.session.commit()
        return {"ok": True}

    def set_association_qos(
        self, cluster_id: int, *, actor: User, account: str, username: str | None,
        qos: list[str],
    ) -> dict[str, Any]:
        """계정 또는 사용자 association의 허용 QOS를 지정한다 (A-US-03).

        `username`이 None이면 계정 단위다. 목록을 **덮어쓰므로** 화면은 현재 값을
        먼저 보여주고 전체 집합을 보내야 한다.
        """
        cluster = self.get(cluster_id)
        _raise_on_errors(
            self.slurm_client(cluster).set_association_qos(
                account=account,
                username=username or "",
                cluster_name=cluster.name or "",
                qos=qos,
            )
        )
        self.audit.record(
            actor=actor,
            action="SLURM_ASSOC_QOS_SET",
            target=f"{account}/{username or '(계정)'}",
            cluster_id=cluster.id,
            detail=",".join(qos),
        )
        self.session.commit()
        return {"ok": True, "qos": qos}

    def remove_account_user(
        self, cluster_id: int, *, actor: User, account: str, username: str
    ) -> dict[str, Any]:
        cluster = self.get(cluster_id)
        _raise_on_errors(
            self.slurm_client(cluster).delete_association(
                username=username, account=account, cluster_name=cluster.name or ""
            )
        )
        self.audit.record(
            actor=actor,
            action="SLURM_ASSOC_REMOVE",
            target=f"{account}/{username}",
            cluster_id=cluster.id,
        )
        self.session.commit()
        return {"ok": True}

    def _record_health(self, cluster: Cluster, *, ok: bool, actor: User) -> None:
        cluster.last_health_at = utcnow()
        cluster.last_health_ok = ok
        self.audit.record(
            actor=actor,
            action="CLUSTER_TEST_REST",
            target=label_of(cluster),
            cluster_id=cluster.id,
            detail="ok" if ok else "failed",
        )
        self.session.commit()


def _dig(source: Any, *keys: str) -> Any:
    """중첩 dict를 안전하게 파고든다 — 없으면 None."""
    for key in keys:
        if not isinstance(source, dict):
            return None
        source = source.get(key)
    return source


def label_of(cluster: Cluster) -> str:
    """감사 로그·오류 메시지에 쓸 표시명.

    이름은 REST 연결 테스트 전까지 비어 있으므로 별칭이 대신한다. 둘 다 없으면
    행 번호라도 남긴다 — 감사 기록에 빈 대상이 남으면 나중에 추적할 수 없다.
    """
    return cluster.name or cluster.alias or f"cluster#{cluster.id}"


def _number(value: Any) -> int | float | None:
    """`{set, infinite, number}` 래퍼를 숫자로. 무제한·미설정은 None."""
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, dict):
        if value.get("infinite") or value.get("set") is False:
            return None
        number = value.get("number")
        return number if isinstance(number, (int, float)) else None
    return None


def _raise_on_errors(payload: Any) -> None:
    """slurmdbd 쓰기는 **HTTP 200으로도 실패를 알린다** — 본문 errors를 봐야 한다(실측)."""
    _reject(payload.get("errors") if isinstance(payload, dict) else None)


def _reject(errors: Any) -> None:
    if not errors:
        return
    first = errors[0] if isinstance(errors, list) and errors else {}
    message = first.get("description") or first.get("error") or "요청이 거부되었습니다."
    raise ValidationFailed(f"Slurm 요청이 거부되었습니다: {message}", detail=errors)


def _items(payload: Any, key: str) -> list[dict[str, Any]]:
    """slurmrestd 응답에서 목록만 꺼낸다.

    응답에는 `meta`·`errors`·`warnings`가 함께 실린다. 특히 `errors`는 **비어 있지 않아도
    목록은 정상적으로 오는 경우가 있다**(예: slurmdbd 미연결 시 TRES 조회만 실패).
    그래서 errors를 이유로 실패 처리하지 않고 목록을 그대로 흘려보낸다 — Job 조회와 같은 원칙.
    """
    if not isinstance(payload, dict):
        return []
    items = payload.get(key)
    return [i for i in items if isinstance(i, dict)] if isinstance(items, list) else []


def _extract_cluster_name(payload: Any) -> str | None:
    """slurmrestd ping 응답에서 ClusterName을 방어적으로 뽑는다.

    v0.0.41 응답 스키마가 실물로 확인되지 않아 구조를 단정하지 않는다.
    """
    if not isinstance(payload, dict):
        return None
    meta = payload.get("meta")
    if isinstance(meta, dict):
        for key in ("cluster", "Slurm", "slurm"):
            node = meta.get(key)
            if isinstance(node, str):
                return node
            if isinstance(node, dict):
                name = node.get("cluster") or node.get("name")
                if isinstance(name, str):
                    return name
    pings = payload.get("pings")
    if isinstance(pings, list) and pings and isinstance(pings[0], dict):
        name = pings[0].get("cluster") or pings[0].get("hostname")
        if isinstance(name, str):
            return name
    return None
