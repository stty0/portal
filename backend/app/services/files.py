"""파일 브라우저·스토리지 현황 서비스 (U-FM-01, A-DB-05).

**대상 사용자는 언제나 요청자 본인이다.** 클라이언트가 사용자명을 넘길 수 없게 하여
경로 조작으로 남의 홈을 읽는 경로를 원천 차단한다(Job 임퍼소네이션과 같은 원칙).
"""

from __future__ import annotations

from typing import Any, BinaryIO, Iterator

from sqlalchemy.orm import Session

from app.clients.ssh.client import LoginNodeClient, SshTarget
from app.core.config import Settings
from app.core.errors import ValidationFailed
from app.core.secrets import SecretStore, build_secret_ref
from app.models import User
from app.repositories.cluster import ClusterCredentialRepository
from app.services.audit import AuditService
from app.services.cluster import KIND_SSH_KEY, ClusterService


class FileService:
    def __init__(
        self,
        session: Session,
        clusters: ClusterService,
        *,
        settings: Settings,
        secrets: SecretStore,
    ):
        self.session = session
        self.clusters = clusters
        self.settings = settings
        self.secrets = secrets
        self.credentials = ClusterCredentialRepository(session)
        self.audit = AuditService(session)

    def _target(self, cluster_id: int) -> SshTarget:
        return ssh_target_for(
            self.clusters.get(cluster_id), secrets=self.secrets, credentials=self.credentials
        )

    def _connect(self, cluster_id: int) -> LoginNodeClient:
        return LoginNodeClient(
            self._target(cluster_id),
            known_hosts=self.settings.ssh_known_hosts,
            timeout=self.settings.ssh_timeout_seconds,
        )

    def _roots(self, ssh, cluster_id: int, user: User) -> tuple[str, list[str]]:
        """홈과 **탐색·변경이 허용된 최상위 목록**.

        조회와 변경이 **같은 범위**를 써야 한다 — 한쪽만 넓으면 목록에 안 보이는 곳을
        지울 수 있게 된다. 그래서 한곳에서만 계산한다.
        """
        home = home_dir_for(self.clusters.get(cluster_id), ssh, user.username)
        return home, [home]

    def browse(self, cluster_id: int, *, user: User, path: str | None) -> dict[str, Any]:
        with self._connect(cluster_id) as ssh:
            # 탐색 범위는 홈으로 한정한다. 상위로 올라가면 다른 사용자 계정명이
            # 그대로 드러난다(/home 목록).
            home, roots = self._roots(ssh, cluster_id, user)
            resolved, entries = ssh.list_dir(
                user.username, path or home, allowed_roots=roots
            )
            return {
                "path": resolved,
                "home": home,
                "roots": roots,
                "entries": [e.__dict__ for e in entries],
            }

    # --- 파일 조작 (U-FM-02 업/다운로드, U-FM-04 조작) --------------------
    def _record(self, action: str, target: str, *, user: User, cluster_id: int, detail=None) -> None:
        """파일 변경은 남긴다 — 사라진 파일의 경위를 나중에 확인할 수 있어야 한다."""
        self.audit.record(
            actor=user, action=action, target=target[:255], cluster_id=cluster_id, detail=detail
        )
        self.session.commit()

    def make_dir(self, cluster_id: int, *, user: User, path: str) -> dict[str, Any]:
        with self._connect(cluster_id) as ssh:
            _, roots = self._roots(ssh, cluster_id, user)
            created = ssh.make_dir(user.username, path, allowed_roots=roots)
        self._record("FILE_MKDIR", created, user=user, cluster_id=cluster_id)
        return {"path": created}

    def create_file(self, cluster_id: int, *, user: User, path: str) -> dict[str, Any]:
        with self._connect(cluster_id) as ssh:
            _, roots = self._roots(ssh, cluster_id, user)
            created = ssh.create_file(user.username, path, allowed_roots=roots)
        self._record("FILE_CREATE", created, user=user, cluster_id=cluster_id)
        return {"path": created}

    def move(self, cluster_id: int, *, user: User, path: str, to: str) -> dict[str, Any]:
        with self._connect(cluster_id) as ssh:
            _, roots = self._roots(ssh, cluster_id, user)
            source, target = ssh.move(user.username, path, to, allowed_roots=roots)
        self._record("FILE_MOVE", source, user=user, cluster_id=cluster_id, detail=f"→ {target}")
        return {"path": target, "from": source}

    def remove(
        self, cluster_id: int, *, user: User, path: str, recursive: bool = False
    ) -> dict[str, Any]:
        with self._connect(cluster_id) as ssh:
            _, roots = self._roots(ssh, cluster_id, user)
            removed = ssh.remove(
                user.username, path, allowed_roots=roots, recursive=recursive
            )
        self._record(
            "FILE_DELETE",
            removed,
            user=user,
            cluster_id=cluster_id,
            detail="recursive" if recursive else None,
        )
        return {"path": removed}

    def upload(
        self, cluster_id: int, *, user: User, directory: str, filename: str, source: BinaryIO
    ) -> dict[str, Any]:
        if "/" in filename or filename in ("", ".", ".."):
            raise ValidationFailed("파일 이름이 올바르지 않습니다.", detail={"name": filename})
        limit = self.settings.file_upload_max_mb * 1024 * 1024
        with self._connect(cluster_id) as ssh:
            _, roots = self._roots(ssh, cluster_id, user)
            target, written = ssh.upload(
                user.username,
                f"{directory.rstrip('/')}/{filename}",
                source,
                allowed_roots=roots,
                max_bytes=limit,
            )
        self._record("FILE_UPLOAD", target, user=user, cluster_id=cluster_id, detail=f"{written}B")
        return {"path": target, "size": written}

    def download(
        self, cluster_id: int, *, user: User, path: str
    ) -> tuple[str, int, Iterator[bytes]]:
        """검증까지 마친 뒤 **연결을 연 채로** 반복자를 돌려준다.

        스트림이 시작된 뒤에는 오류를 HTTP 상태로 바꿀 수 없으므로, 경로 검사와 stat은
        여기서 끝낸다. 연결은 반복자가 끝날 때 닫힌다.
        """
        ssh = self._connect(cluster_id)
        ssh.__enter__()
        try:
            _, roots = self._roots(ssh, cluster_id, user)
            target, size, chunks = ssh.open_read(user.username, path, allowed_roots=roots)
        except BaseException:
            ssh.__exit__(None, None, None)
            raise

        def stream() -> Iterator[bytes]:
            try:
                yield from chunks
            finally:
                ssh.__exit__(None, None, None)

        self._record("FILE_DOWNLOAD", target, user=user, cluster_id=cluster_id)
        return target, size, stream()

    def storage(self, cluster_id: int, *, user: User) -> dict[str, Any]:
        """홈만 보여준다.

        `df` 원본에는 tmpfs·/boot 처럼 사용자와 무관한 마운트가 대부분이라
        그대로 내보내면 정작 봐야 할 홈 사용량이 묻힌다.
        """
        with self._connect(cluster_id) as ssh:
            home, _ = self._roots(ssh, cluster_id, user)
            mounts = ssh.filesystems(user.username)
            target = {"label": "홈", "path": home, "exists": True, **_mount_for(home, mounts)}
            return {"targets": [target], "quota": ssh.quota(user.username)}


def home_dir_for(cluster, ssh, username: str) -> str:
    """사용자 홈의 절대 경로.

    파일 브라우저(U-FM-01)·웹 터미널·인터랙티브 세션(U-IA-01)이 **같은 해석**을 써야
    한다 — 갈리면 세션 산출물이 브라우저에 안 보이는 곳에 쌓인다. 그래서 함수로 뺐다.

    클러스터에 홈 상위 경로가 설정돼 있으면 `{설정}/{사용자명}`, 비어 있으면
    NSS(`getent passwd`)로 읽는다. **사용자명은 인증된 본인이며 클라이언트가 넘길 수
    없다** — 그래서 설정에 자리표시자를 두지 않는다.
    """
    if cluster.home_base:
        return f"{cluster.home_base.rstrip('/')}/{username}"
    return ssh.home_dir(username)


def ssh_target_for(
    cluster, *, secrets: SecretStore, credentials: ClusterCredentialRepository
) -> SshTarget:
    """클러스터 등록 정보 + Secret 저장소 → SSH 접속 대상.

    파일 브라우저(U-FM-01)와 웹 터미널(U-SH-01)이 **같은 해석**을 써야 해서 함수로 뺐다.
    """
    if not cluster.login_node:
        raise ValidationFailed(
            "클러스터에 로그인 노드가 설정되어 있지 않습니다.", detail={"cluster_id": cluster.id}
        )
    if not cluster.ssh_account:
        raise ValidationFailed(
            "클러스터에 SSH 서비스 계정이 설정되어 있지 않습니다.", detail={"cluster_id": cluster.id}
        )
    credential = credentials.get_active(cluster.id, KIND_SSH_KEY)
    ref = credential.secret_ref if credential else build_secret_ref(
        f"cluster/{cluster.id}", KIND_SSH_KEY
    )
    return SshTarget(
        host=cluster.login_node,
        port=cluster.ssh_port or 22,
        account=cluster.ssh_account,
        private_key=secrets.get(ref),
    )


def _mount_for(path: str, mounts: list[dict[str, Any]]) -> dict[str, Any]:
    """경로를 담고 있는 마운트를 찾는다. 겹치면 더 깊은 쪽이 실제 담당이다."""
    candidates = [
        m for m in mounts if path == m["mount"] or path.startswith(m["mount"].rstrip("/") + "/")
    ]
    if not candidates:
        return {}
    return max(candidates, key=lambda m: len(m["mount"]))
