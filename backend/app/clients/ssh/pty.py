"""로그인 노드 PTY 세션 (U-SH-01 웹 터미널).

파일 브라우저와 같은 경로로 접속한 뒤(`sudo -u <user>`) **대화형 셸**을 띄운다.
SFTP 대신 PTY를 요청한다는 점만 다르다.

동기 라이브러리(paramiko)를 async 웹소켓과 잇기 위해, 읽기는 별도 스레드에서 돌리고
바이트만 큐로 넘긴다 — 이벤트 루프를 블로킹하지 않기 위해서다.
"""

from __future__ import annotations

import shlex
from typing import Any

import paramiko

from app.clients.ssh.client import SshTarget, _load_key
from app.core.errors import ExternalServiceError, ValidationFailed


class PtySession:
    def __init__(
        self,
        target: SshTarget,
        *,
        username: str,
        known_hosts: str | None,
        timeout: float = 10.0,
        term: str = "xterm-256color",
        cols: int = 80,
        rows: int = 24,
    ):
        self._t = target
        self._username = username
        self._known_hosts = known_hosts
        self._timeout = timeout
        self._term = term
        self._size = (cols, rows)
        self._ssh: paramiko.SSHClient | None = None
        self._chan: paramiko.Channel | None = None

    def open(self) -> None:
        if not self._known_hosts:
            raise ValidationFailed(
                "SSH known_hosts가 설정되어 있지 않습니다. "
                "PORTAL_SSH_KNOWN_HOSTS에 로그인 노드 호스트키 파일을 지정하세요."
            )
        client = paramiko.SSHClient()
        client.load_host_keys(self._known_hosts)
        client.set_missing_host_key_policy(paramiko.RejectPolicy())
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

        transport = client.get_transport()
        if transport is None:
            raise ExternalServiceError("SSH 전송이 열려 있지 않습니다.")
        cols, rows = self._size
        chan = transport.open_session(timeout=self._timeout)
        chan.get_pty(term=self._term, width=cols, height=rows)
        # 로그인 셸(-i)로 띄워 프로필·환경변수를 사용자 것 그대로 받는다.
        chan.exec_command(
            " ".join(shlex.quote(a) for a in ["sudo", "-n", "-u", self._username, "-i"])
        )
        chan.settimeout(0.0)  # 비블로킹 — 읽기 루프가 스레드를 붙잡지 않게
        self._ssh, self._chan = client, chan

    # --- 입출력 --------------------------------------------------------
    def read(self, size: int = 65536) -> bytes | None:
        """읽을 게 없으면 b"", 세션이 끝났으면 None."""
        chan = self._chan
        if chan is None or chan.closed:
            return None
        try:
            if chan.recv_ready():
                return chan.recv(size)
            if chan.recv_stderr_ready():
                return chan.recv_stderr(size)
            if chan.exit_status_ready():
                return None
        except OSError:
            return None
        return b""

    def write(self, data: str) -> None:
        if self._chan is not None and not self._chan.closed:
            self._chan.send(data)

    def resize(self, cols: int, rows: int) -> None:
        if self._chan is not None and not self._chan.closed:
            self._chan.resize_pty(width=cols, height=rows)

    def close(self) -> None:
        for closable in (self._chan, self._ssh):
            try:
                if closable is not None:
                    closable.close()
            except Exception:  # pragma: no cover - 종료 경로는 조용히 정리한다
                pass
        self._chan = self._ssh = None

    def __enter__(self) -> "PtySession":
        self.open()
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()
