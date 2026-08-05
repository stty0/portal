"""로그인 노드 SSH/SFTP client (정의서 §4.1 ② 보조 경로, U-FM-01·A-DB-05).

**사용자 impersonation 방식**: 포털 서비스 계정으로 접속한 뒤 `sudo -u <user>` 로
사용자 권한에 내려가 SFTP 서브시스템을 띄운다. 파일 권한 판정을 포털이 흉내내지 않고
**OS에 그대로 맡기기 위해서다** — 경로 검사 로직에 구멍이 나도 남의 파일은 열리지 않는다.

정의서 §4.1: "포털 서비스 계정 + SSH 개인키(Secret 저장) 사용, 제한적 sudo(least
privilege)로 사용자 impersonation — 전체 root sudo 지양".
"""

from __future__ import annotations

import io
import shlex
import stat as stat_module
from dataclasses import dataclass
from typing import Any, Sequence

import paramiko

from app.core.errors import ExternalServiceError, Forbidden, ValidationFailed

# 배포판별 sftp-server 위치. sudoers에 등록한 경로와 일치해야 한다.
SFTP_SERVER_CANDIDATES = (
    "/usr/lib/openssh/sftp-server",  # Debian/Ubuntu
    "/usr/libexec/openssh/sftp-server",  # RHEL/Rocky
)


@dataclass(frozen=True)
class SshTarget:
    host: str
    port: int
    account: str
    private_key: str
    sftp_server: str = SFTP_SERVER_CANDIDATES[0]


@dataclass(frozen=True)
class FileEntry:
    name: str
    is_dir: bool
    size: int
    mtime: int | None
    mode: str
    uid: int | None
    gid: int | None


def _within(path: str, roots: Sequence[str]) -> bool:
    """path가 roots 중 하나이거나 그 하위인가.

    문자열 prefix만 보면 `/home/ab`가 `/home/a`의 하위로 잡힌다 — 구분자까지 확인한다.
    """
    return any(path == r or path.startswith(r.rstrip("/") + "/") for r in roots)


def _load_key(pem: str) -> paramiko.PKey:
    for cls in (paramiko.Ed25519Key, paramiko.ECDSAKey, paramiko.RSAKey):
        try:
            return cls.from_private_key(io.StringIO(pem))
        except paramiko.SSHException:
            continue
    raise ValidationFailed("SSH 개인키 형식을 인식할 수 없습니다(Ed25519/ECDSA/RSA).")


class LoginNodeClient:
    """요청 단위로 연결을 열고 닫는다.

    연결을 풀링하지 않는 이유: 채널이 `sudo -u <user>` 로 **특정 사용자에 묶이므로**
    다른 사용자 요청에 재사용할 수 없다. 재사용하면 남의 세션에 파일을 노출하게 된다.
    """

    def __init__(self, target: SshTarget, *, known_hosts: str | None, timeout: float = 10.0):
        self._t = target
        self._known_hosts = known_hosts
        self._timeout = timeout
        self._ssh: paramiko.SSHClient | None = None

    def __enter__(self) -> "LoginNodeClient":
        client = paramiko.SSHClient()
        if self._known_hosts:
            client.load_host_keys(self._known_hosts)
            # 미등록 호스트는 거부한다 — 자동 수락은 중간자 공격을 그대로 통과시킨다.
            client.set_missing_host_key_policy(paramiko.RejectPolicy())
        else:
            raise ValidationFailed(
                "SSH known_hosts가 설정되어 있지 않습니다. "
                "PORTAL_SSH_KNOWN_HOSTS에 로그인 노드 호스트키 파일을 지정하세요."
            )
        try:
            client.connect(
                hostname=self._t.host,
                port=self._t.port,
                username=self._t.account,
                pkey=_load_key(self._t.private_key),
                timeout=self._timeout,
                allow_agent=False,
                look_for_keys=False,
            )
        except paramiko.SSHException as exc:
            raise ExternalServiceError(f"로그인 노드 SSH 접속 실패: {exc}") from exc
        except OSError as exc:
            raise ExternalServiceError(f"로그인 노드에 연결할 수 없습니다: {exc}") from exc
        self._ssh = client
        return self

    def __exit__(self, *exc_info) -> None:
        if self._ssh is not None:
            self._ssh.close()
            self._ssh = None

    # --- 내부 --------------------------------------------------------
    def _transport(self) -> paramiko.Transport:
        if self._ssh is None:
            raise RuntimeError("with 블록 안에서만 사용할 수 있습니다.")
        transport = self._ssh.get_transport()
        if transport is None:
            raise ExternalServiceError("SSH 전송이 열려 있지 않습니다.")
        return transport

    def _run_as(self, user: str, argv: list[str]) -> str:
        """사용자 권한으로 명령 실행. **인자는 리스트로만 받는다** — 셸 문자열 조립 금지."""
        command = " ".join(shlex.quote(a) for a in ["sudo", "-n", "-u", user, *argv])
        _, stdout, stderr = self._ssh.exec_command(command, timeout=self._timeout)  # type: ignore[union-attr]
        out = stdout.read().decode("utf-8", "replace")
        rc = stdout.channel.recv_exit_status()
        if rc != 0:
            err = stderr.read().decode("utf-8", "replace").strip()
            raise ExternalServiceError(f"명령 실행 실패(rc={rc}): {err[:200]}")
        return out

    def _sftp_as(self, user: str) -> paramiko.SFTPClient:
        """`sudo -u <user> sftp-server` 채널 위에 SFTP를 얹는다.

        표준 SFTP 서브시스템은 접속 계정(서비스 계정) 권한으로 열리므로 쓸 수 없다.
        """
        channel = self._transport().open_session(timeout=self._timeout)
        command = " ".join(
            shlex.quote(a) for a in ["sudo", "-n", "-u", user, self._t.sftp_server]
        )
        channel.exec_command(command)
        return paramiko.SFTPClient(channel)

    # --- 공개 API ----------------------------------------------------
    def home_dir(self, user: str) -> str:
        """홈 경로는 설정으로 받지 않고 NSS에서 읽는다(정의서 §4.1 경로 인식)."""
        out = self._run_as(user, ["getent", "passwd", user]).strip()
        parts = out.split(":")
        if len(parts) < 6 or not parts[5]:
            raise ExternalServiceError(f"{user}의 홈 디렉터리를 확인할 수 없습니다.")
        return parts[5]

    def exists(self, user: str, path: str) -> bool:
        sftp = self._sftp_as(user)
        try:
            sftp.stat(path)
            return True
        except OSError:
            return False
        finally:
            sftp.close()

    def list_dir(
        self, user: str, path: str, *, allowed_roots: Sequence[str] | None = None
    ) -> tuple[str, list[FileEntry]]:
        sftp = self._sftp_as(user)
        try:
            # 상대 경로·심볼릭 링크를 서버가 해석한 절대 경로로 정규화한다.
            # 검사는 **정규화 뒤에** 해야 한다 — `..`나 링크로 우회하는 경로를 막는다.
            resolved = sftp.normalize(path)
            if allowed_roots is not None and not _within(resolved, allowed_roots):
                raise Forbidden(
                    "허용된 디렉터리 밖입니다.", detail={"path": resolved}
                )
            entries = [
                FileEntry(
                    name=a.filename,
                    is_dir=stat_module.S_ISDIR(a.st_mode or 0),
                    size=a.st_size or 0,
                    mtime=a.st_mtime,
                    mode=stat_module.filemode(a.st_mode or 0),
                    uid=a.st_uid,
                    gid=a.st_gid,
                )
                for a in sftp.listdir_attr(resolved)
            ]
        except FileNotFoundError as exc:
            raise ValidationFailed("경로를 찾을 수 없습니다.", detail={"path": path}) from exc
        except PermissionError as exc:
            raise ValidationFailed("접근 권한이 없습니다.", detail={"path": path}) from exc
        except OSError as exc:
            raise ExternalServiceError(f"디렉터리 조회 실패: {exc}") from exc
        finally:
            sftp.close()
        entries.sort(key=lambda e: (not e.is_dir, e.name.lower()))
        return resolved, entries

    def filesystems(self, user: str) -> list[dict[str, Any]]:
        """`df -P` — 이식 가능한 출력 형식이라 열 위치가 고정된다."""
        rows: list[dict[str, Any]] = []
        for line in self._run_as(user, ["df", "-P", "-k"]).splitlines()[1:]:
            cols = line.split(None, 5)
            if len(cols) < 6:
                continue
            total, used, avail = (int(c) * 1024 for c in cols[1:4])
            rows.append(
                {
                    "filesystem": cols[0],
                    "mount": cols[5],
                    "total_bytes": total,
                    "used_bytes": used,
                    "avail_bytes": avail,
                    "used_pct": round(used / total * 100, 1) if total else None,
                }
            )
        return rows

    def quota(self, user: str) -> list[dict[str, Any]]:
        """쿼터는 미설정 환경이 흔하다 — 실패를 오류로 올리지 않고 빈 목록으로 둔다."""
        try:
            out = self._run_as(user, ["quota", "-w", "-u", user])
        except ExternalServiceError:
            return []
        rows: list[dict[str, Any]] = []
        for line in out.splitlines():
            cols = line.split()
            if len(cols) >= 4 and cols[0].startswith("/"):
                rows.append(
                    {
                        "filesystem": cols[0],
                        "used_bytes": int(cols[1].rstrip("*")) * 1024,
                        "soft_bytes": int(cols[2]) * 1024,
                        "hard_bytes": int(cols[3]) * 1024,
                    }
                )
        return rows
