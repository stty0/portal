"""파일 브라우저·스토리지 현황 서비스 (U-FM-01, A-DB-05).

**대상 사용자는 언제나 요청자 본인이다.** 클라이언트가 사용자명을 넘길 수 없게 하여
경로 조작으로 남의 홈을 읽는 경로를 원천 차단한다(Job 임퍼소네이션과 같은 원칙).
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.clients.ssh.client import LoginNodeClient, SshTarget
from app.core.config import Settings
from app.core.errors import ValidationFailed
from app.core.secrets import SecretStore, build_secret_ref
from app.models import User
from app.repositories.cluster import ClusterCredentialRepository
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

    def browse(self, cluster_id: int, *, user: User, path: str | None) -> dict[str, Any]:
        cluster = self.clusters.get(cluster_id)
        with self._connect(cluster_id) as ssh:
            home = ssh.home_dir(user.username)
            # 그룹·스크래치는 클러스터 등록 시 템플릿으로 받는다(정의서 §4.1 경로 인식).
            # 미구축 환경이 흔하므로 실제 존재 여부를 확인해 화면에 그대로 알린다.
            shortcuts = _resolve_shortcuts(ssh, cluster, user.username, home)
            # 탐색 범위는 홈 + 실제로 존재하는 바로가기로 한정한다.
            # 상위로 올라가면 다른 사용자 계정명이 그대로 드러난다(/home 목록).
            roots = [s["path"] for s in shortcuts if s["exists"]]
            resolved, entries = ssh.list_dir(
                user.username, path or home, allowed_roots=roots
            )
            return {
                "path": resolved,
                "home": home,
                "roots": roots,
                "shortcuts": shortcuts,
                "entries": [e.__dict__ for e in entries],
            }

    def storage(self, cluster_id: int, *, user: User) -> dict[str, Any]:
        """홈·스크래치·그룹 세 곳만 보여준다.

        `df` 원본에는 tmpfs·/boot 처럼 사용자와 무관한 마운트가 대부분이라
        그대로 내보내면 정작 봐야 할 홈 사용량이 묻힌다.
        """
        cluster = self.clusters.get(cluster_id)
        with self._connect(cluster_id) as ssh:
            home = ssh.home_dir(user.username)
            mounts = ssh.filesystems(user.username)
            targets = [
                {**s, **(_mount_for(s["path"], mounts) if s["exists"] else {})}
                for s in _resolve_shortcuts(ssh, cluster, user.username, home)
            ]
            return {"targets": targets, "quota": ssh.quota(user.username)}


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


def _resolve_shortcuts(ssh, cluster, username: str, home: str) -> list[dict[str, Any]]:
    """홈·스크래치·그룹 경로와 **실제 존재 여부**. 미구축 환경이 흔해 숨기지 않고 알린다."""
    items: list[dict[str, Any]] = [{"label": "홈", "path": home, "exists": True}]
    for label, template in (("스크래치", cluster.scratch_path_tpl), ("그룹", cluster.group_path_tpl)):
        if not template:
            continue
        path = template.replace("{user}", username)
        items.append({"label": label, "path": path, "exists": ssh.exists(username, path)})
    return items


def _mount_for(path: str, mounts: list[dict[str, Any]]) -> dict[str, Any]:
    """경로를 담고 있는 마운트를 찾는다. 겹치면 더 깊은 쪽이 실제 담당이다."""
    candidates = [
        m for m in mounts if path == m["mount"] or path.startswith(m["mount"].rstrip("/") + "/")
    ]
    if not candidates:
        return {}
    return max(candidates, key=lambda m: len(m["mount"]))
