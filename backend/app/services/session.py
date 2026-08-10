"""인터랙티브 세션 서비스 (U-IA-01·02·04).

세션은 **Slurm 배치 Job**이다. 제출은 slurmrestd, 접속 정보는 Job이 워커에 기록한
`connection.json`을 로그인 노드 경유 SFTP로 읽는다(docs/plan.md §3.1).

두 가지 출처를 섞지 않는다.
  - **살아 있는가** → Slurm Job 상태가 권위 있는 출처다. 노드가 죽으면 정리 훅이
    돌지 않아 `connection.json`이 남기 때문이다(T-02 실측).
  - **어디로 붙는가** → `connection.json`만이 출처다. 포트·비밀번호를 DB에 복제하지 않는다.

**대상 사용자는 언제나 요청자 본인이다**(FileService와 같은 원칙). 클라이언트가
사용자명을 넘길 수 없고, 세션 조회는 소유자 조건을 붙여서 한다.
"""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session

from app.clients.ssh.client import LoginNodeClient
from app.clients.ssh.tunnel import TcpTunnel
from app.core.config import Settings
from app.core.errors import (
    ExternalServiceError,
    NotFound,
    Unauthenticated,
    ValidationFailed,
)
from app.core.redis_client import SessionStore
from app.core.secrets import SecretStore
from app.db.base import utcnow
from app.models import Cluster, InteractiveSession, User
from app.repositories.cluster import ClusterCredentialRepository
from app.repositories.session import (
    STATUS_ACTIVE,
    STATUS_ENDED,
    InteractiveSessionRepository,
)
from app.services.audit import AuditService
from app.services.cluster import ClusterService
from app.services.files import home_dir_for, ssh_target_for
from app.services.ws_auth import authenticate_ws_token
# Job 응답 파싱은 JobService에서 이미 slurmrestd 버전별 형태를 흡수해 두었다.
# 같은 응답을 다루므로 재사용한다 — 복제하면 한쪽만 고쳐지는 버그가 난다.
from app.services.job import _as_job_list, _extract_job_id, _state_of, walltime_minutes
from app.services import app_images
from app.services.session_script import (
    LOG_SUBDIR,
    SessionSpec,
    build_session_script,
    log_path,
    session_dir,
)

#: Slurm에서 이 상태면 세션이 끝난 것으로 본다.
TERMINAL_STATES = {
    "COMPLETED", "CANCELLED", "FAILED", "TIMEOUT",
    "NODE_FAIL", "PREEMPTED", "BOOT_FAIL", "DEADLINE", "OUT_OF_MEMORY",
}


class SessionService:
    def __init__(
        self,
        session: Session,
        clusters: ClusterService,
        *,
        settings: Settings,
        secrets: SecretStore,
        session_store: SessionStore | None = None,
    ):
        self.session = session
        self.clusters = clusters
        self.settings = settings
        self.secrets = secrets
        #: 웹소켓 인증용. HTTP 경로에서는 필요 없어 선택 인자다.
        self.store = session_store
        self.sessions = InteractiveSessionRepository(session)
        self.credentials = ClusterCredentialRepository(session)
        self.audit = AuditService(session)

    # --- SSH ------------------------------------------------------------
    def _connect(self, cluster: Cluster) -> LoginNodeClient:
        return LoginNodeClient(
            ssh_target_for(cluster, secrets=self.secrets, credentials=self.credentials),
            known_hosts=self.settings.ssh_known_hosts,
            timeout=self.settings.ssh_timeout_seconds,
        )

    # --- 제출 (U-IA-01) --------------------------------------------------
    def image_ref(self, cluster: Cluster, app: str) -> str:
        """앱이 쓸 이미지. 있는 곳은 클러스터가, 어떤 파일인지는 앱 카탈로그가 안다."""
        return app_images.resolve(
            self.session, self.settings, cluster, app_images.KIND_INTERACTIVE, app
        )

    def create(self, cluster: Cluster, spec: SessionSpec, *, user: User) -> InteractiveSession:
        script = build_session_script(spec)

        with self._connect(cluster) as ssh:
            # 파일 브라우저와 **같은 해석**을 쓴다 — 갈리면 세션 산출물이 브라우저에
            # 안 보이는 곳에 쌓인다.
            home = home_dir_for(cluster, ssh, user.username)
            # Slurm은 로그 파일만 만들고 상위 디렉터리는 만들지 않는다.
            # 홈 자체는 만들지 않는다 — 없으면 그 사실이 오류로 올라온다.
            ssh.makedirs(user.username, home, LOG_SUBDIR)

        payload = {
            "script": script,
            "job": _job_properties(spec, home=home, username=user.username),
        }
        client = self.clusters.slurm_client(cluster)
        # as_user는 항상 인증된 본인 — 호출자가 지정할 수 없다.
        result = client.submit_job(payload, as_user=user.username)
        job_id = _extract_job_id(result)
        if not job_id:
            raise ExternalServiceError("세션 Job 제출 결과에서 Job ID를 찾지 못했습니다.")

        record = InteractiveSession(
            user_guid=user.ad_object_guid,
            cluster_id=cluster.id,
            app_type=spec.app,
            slurm_job_id=str(job_id),
            status=STATUS_ACTIVE,
        )
        self.session.add(record)
        self.audit.record(
            actor=user,
            action="SESSION_CREATE",
            target=str(job_id),
            cluster_id=cluster.id,
            detail=f"app={spec.app} geometry={spec.geometry}",
        )
        self.session.commit()
        return record

    # --- 조회 (U-IA-04) --------------------------------------------------
    def list(self, *, user: User, cluster_id: int | None = None) -> list[dict[str, Any]]:
        records = self.sessions.list_for_user(user.ad_object_guid, cluster_id=cluster_id)
        if not records:
            return []
        # 클러스터마다 Job 목록을 한 번씩만 조회한다.
        by_cluster: dict[int, dict[str, str]] = {}
        for record in records:
            if record.cluster_id not in by_cluster:
                by_cluster[record.cluster_id] = self._job_states(record.cluster_id, user=user)
        views = [self._view(r, by_cluster.get(r.cluster_id, {})) for r in records]
        self._persist_state()
        return views

    def get(self, session_id: int, *, user: User) -> dict[str, Any]:
        record = self._owned(session_id, user=user)
        states = self._job_states(record.cluster_id, user=user)
        view = self._view(record, states)
        self._persist_state()
        return view

    def connection(self, session_id: int, *, user: User) -> dict[str, Any]:
        """접속 대상. 세션이 실행 중이 아니면 거부한다.

        여기서 돌려주는 host는 **`connection.json`의 워커 노드**다 —
        `cluster.login_node`가 아니다. 개발 환경은 둘이 같지만 분리되면 갈라진다
        (docs/plan.md §3.2).
        """
        return self._connection_for(self._owned(session_id, user=user), user=user)

    def _connection_for(self, record: InteractiveSession, *, user: User) -> dict[str, Any]:
        """소유권이 **이미 확인된** 레코드로 접속 대상을 읽는다.

        `connection()`과 `open_stream()`이 같은 세션을 두 번 조회하지 않도록 분리해 둔다.
        """
        state = self._job_states(record.cluster_id, user=user).get(record.slurm_job_id or "", "")
        if state.upper() in TERMINAL_STATES:
            raise ValidationFailed("이미 종료된 세션입니다.", detail={"state": state})

        info = self._connection_file(record, user=user)
        if info is None:
            # Slurm이 RUNNING으로 바꾸는 순간과 컨테이너가 접속 정보를 쓰는 순간 사이에
            # 10~20초가 있다(데스크톱은 Xvnc+MATE 기동). 그 사이의 접속은 **실패가 아니라
            # 기다릴 일**이다 — 화면이 구분할 수 있게 표식을 붙인다.
            raise ValidationFailed(
                "세션이 아직 준비 중입니다.",
                detail={"state": state or "PENDING", "reason": "starting"},
            )
        host = info.get("node") or info.get("ip")
        port = info.get("port")
        if not host or not isinstance(port, int):
            raise ExternalServiceError("세션 접속 정보가 올바르지 않습니다.")
        return {
            "host": str(host),
            "port": port,
            "password": info.get("password"),
            "view_password": info.get("view_password"),
            "geometry": info.get("geometry"),
            # HTTP 앱(JupyterLab)에만 있는 값들. **브라우저로 나가지 않는다** —
            # 라우터가 `SessionConnectInfo`로 추려서 password·geometry만 내보낸다.
            "scheme": info.get("scheme"),
            "token": info.get("token"),
            "base_url": info.get("base_url"),
        }

    # --- 웹소켓 (U-IA-02) ------------------------------------------------
    def authenticate(self, token: str) -> User:
        if self.store is None:
            raise Unauthenticated("웹소켓 인증을 사용할 수 없습니다.")
        return authenticate_ws_token(
            self.session, settings=self.settings, sessions=self.store, token=token
        )

    def open_stream(self, session_id: int, *, user: User) -> TcpTunnel:
        """세션의 VNC 포트로 가는 TCP 스트림.

        목적지는 `connection()`이 돌려주는 워커 노드다 — 로그인 노드가 아니다.
        호스트·포트는 여기서만 알고 **브라우저에 내보내지 않는다**(OnDemand의
        `/node/<host>/<port>/`와 달리 열린 프록시가 되지 않게).
        """
        record = self._owned(session_id, user=user)
        target = self._connection_for(record, user=user)
        cluster = self.clusters.get(record.cluster_id)
        tunnel = TcpTunnel(
            ssh_target_for(cluster, secrets=self.secrets, credentials=self.credentials),
            dest_host=target["host"],
            dest_port=target["port"],
            known_hosts=self.settings.ssh_known_hosts,
            timeout=self.settings.ssh_timeout_seconds,
        )
        tunnel.open()
        return tunnel

    def record(self, action: str, *, user: User, session_id: int, cluster_id: int) -> None:
        self.audit.record(
            actor=user, action=action, target=str(session_id), cluster_id=cluster_id
        )
        self.session.commit()

    # --- 종료 (U-IA-04) --------------------------------------------------
    def terminate(self, session_id: int, *, user: User) -> None:
        record = self._owned(session_id, user=user)
        cluster = self.clusters.get(record.cluster_id)
        if record.slurm_job_id:
            self.clusters.slurm_client(cluster).cancel_job(
                record.slurm_job_id, as_user=user.username
            )
        record.status = STATUS_ENDED
        record.terminated_at = utcnow()
        self.audit.record(
            actor=user,
            action="SESSION_TERMINATE",
            target=record.slurm_job_id or str(record.id),
            cluster_id=record.cluster_id,
        )
        self.session.commit()

    # --- 내부 ------------------------------------------------------------
    def _owned(self, session_id: int, *, user: User) -> InteractiveSession:
        record = self.sessions.owned(session_id, user.ad_object_guid)
        if record is None:
            # 남의 세션과 없는 세션을 구분해 주지 않는다.
            raise NotFound("세션을 찾을 수 없습니다.", detail={"session_id": session_id})
        return record

    def _job_states(self, cluster_id: int, *, user: User) -> dict[str, str]:
        """Job ID → 상태. 조회에 실패해도 세션 목록 자체는 보여준다."""
        try:
            cluster = self.clusters.get(cluster_id)
            jobs = _as_job_list(
                self.clusters.slurm_client(cluster).get_jobs(as_user=user.username)
            )
        except Exception:  # noqa: BLE001 — 상태를 못 읽어도 목록은 나와야 한다
            return {}
        return {str(j.get("job_id")): _state_of(j) for j in jobs if j.get("job_id") is not None}

    def _connection_file(self, record: InteractiveSession, *, user: User) -> dict[str, Any] | None:
        cluster = self.clusters.get(record.cluster_id)
        with self._connect(cluster) as ssh:
            home = home_dir_for(cluster, ssh, user.username)
            path = f"{session_dir(home, record.slurm_job_id)}/connection.json"
            raw = ssh.read_text(user.username, path)
        if not raw:
            return None
        try:
            info = json.loads(raw)
        except ValueError:
            # 원자적 교체(mv)를 쓰므로 정상적으로는 안 나온다.
            return None
        return info if isinstance(info, dict) else None

    def _persist_state(self) -> None:
        """`_view`가 되돌려 놓은 대장 상태를 **확정한다**.

        `session_scope()`는 정상 종료 시 커밋하지 않는다(커밋은 서비스가 정한다). 이걸
        부르지 않으면 상태 변경이 조용히 버려지고, 뒤에 다른 커밋이 따라오는 경로
        (웹소켓 접속 등)에서만 **우연히** 저장된다 — 저장 여부가 무관한 코드에 달리게 된다.
        """
        if self.session.dirty:
            self.session.commit()

    def _view(self, record: InteractiveSession, states: dict[str, str]) -> dict[str, Any]:
        state = states.get(record.slurm_job_id or "", "")
        # Slurm이 모르는 Job은 이미 정리된 것이다(대장에는 남아 있어도).
        ended = (not state) or state.upper() in TERMINAL_STATES
        if ended and record.status == STATUS_ACTIVE:
            record.status = STATUS_ENDED
            if record.terminated_at is None:
                record.terminated_at = utcnow()
        return {
            "id": record.id,
            "cluster_id": record.cluster_id,
            "app": record.app_type,
            "job_id": record.slurm_job_id,
            "state": state or ("ENDED" if ended else "PENDING"),
            "is_running": state.upper() == "RUNNING",
            "created_at": record.created_at,
            "terminated_at": record.terminated_at,
        }


def _job_properties(spec: SessionSpec, *, home: str, username: str) -> dict[str, Any]:
    """slurmrestd job 속성. `#SBATCH`는 REST 제출에서 무시되므로 여기가 실제 자원이다."""
    props: dict[str, Any] = {
        "name": f"portal-{spec.app}",
        # 비우면 Slurm이 2019(I/O error)로 제출을 거부한다(JobService 실측).
        # **HOME을 반드시 넣는다** — REST 제출은 환경을 통째로 교체해서 수동 sbatch와 달리
        # HOME이 비고, 스크립트가 set -u 아래에서 즉시 죽는다(실측: FAILED 1:0).
        "environment": [
            "PATH=/usr/local/bin:/usr/bin:/bin",
            f"HOME={home}",
            f"USER={username}",
            f"LOGNAME={username}",
        ],
        "current_working_directory": home,
        "standard_output": log_path(home),
        "standard_error": log_path(home),
    }
    # 노드 독점이면 자원 지정을 **하지 않는다**. Slurm이 노드의 CPU를 통째로 할당하므로
    # 코어 수는 의미가 없고, `ConstrainCores` 설정에 따라서는 오히려 그 값으로 cpuset이
    # 좁혀져 16코어 노드를 잡아놓고 2코어만 쓰게 된다.
    # 메모리는 더 분명하다 — `--mem`은 독점과 무관하게 하드 캡이라 그냥 두면 노드를
    # 막아놓고 일부만 쓴다. 0이 "노드 메모리 전체"다.
    cpus = None if spec.exclusive else spec.cpus
    memory_mb = 0 if spec.exclusive else (spec.memory_gb * 1024 if spec.memory_gb else None)
    for key, value in (
        ("partition", spec.partition),
        ("account", spec.account),
        ("qos", spec.qos),
        ("cpus_per_task", cpus),
        # 메모리는 MB 정수
        ("memory_per_node", memory_mb),
        # time_limit은 분 단위 정수 — 문자열이면 9202로 거부된다.
        ("time_limit", walltime_minutes(spec.walltime) if spec.walltime else None),
    ):
        if value is not None:
            props[key] = value
    if spec.exclusive:
        props["exclusive"] = "true"
    return props
