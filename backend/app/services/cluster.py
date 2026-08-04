"""클러스터 서비스 (A-CL-01~04, C-03).

자격증명은 값을 받아 **Secret 저장소에만** 넣고 DB에는 `secret_ref`와 만료만 남긴다.
클러스터 이름은 손으로 받지 않고 REST 연결 테스트 시 slurmrestd에서 조회한다
(정의서 A-CL-02: slurm.conf ClusterName과 자동 일치).
"""

from typing import Any

from sqlalchemy.orm import Session

from app.clients.factory import ClusterClientFactory
from app.core.errors import Conflict, NotFound, ValidationFailed
from app.core.secrets import SecretStore, build_secret_ref
from app.core.security import decode_slurm_token_exp
from app.models import Cluster, ClusterCredential, User
from app.repositories.cluster import ClusterCredentialRepository, ClusterRepository
from app.services.audit import AuditService

KIND_SLURM_JWT = "SLURM_JWT"
KIND_SSH_KEY = "SSH_KEY"


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
    def create(self, *, actor: User, name: str, **fields) -> Cluster:
        if self.clusters.get_by_name(name):
            raise Conflict("같은 이름의 클러스터가 이미 등록되어 있습니다.", detail={"name": name})
        cluster = Cluster(name=name, **{k: v for k, v in fields.items() if v is not None})
        self.clusters.add(cluster)
        if cluster.is_default:
            self.clusters.clear_default(except_id=cluster.id)
        self.audit.record(actor=actor, action="CLUSTER_CREATE", target=name, cluster_id=cluster.id)
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
            target=cluster.name,
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
            actor=actor, action="CLUSTER_DEACTIVATE", target=cluster.name, cluster_id=cluster.id
        )
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
            target=cluster.name,
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
        payload = self.slurm_client(cluster).ping()
        detected = _extract_cluster_name(payload)
        if detected and cluster.name != detected:
            # 손 입력 불일치 제거: slurm.conf의 ClusterName을 정본으로 삼는다.
            cluster.name = detected
        self.audit.record(
            actor=actor, action="CLUSTER_TEST_REST", target=cluster.name, cluster_id=cluster.id
        )
        self.session.commit()
        return {"ok": True, "cluster_name": cluster.name, "api_version": cluster.api_version}


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
