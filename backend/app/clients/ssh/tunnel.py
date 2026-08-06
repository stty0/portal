"""로그인 노드 경유 TCP 터널 (U-IA-02 원격 데스크톱).

포털은 **로그인 노드 자격증명만** 가진다. 컨테이너는 워커 노드에서 돌기 때문에
워커의 VNC 포트에 붙어야 하는데, SSH `direct-tcpip`의 **목적지는 로그인 노드의
sshd가 해석**한다(`ssh -L 5901:worker:5901 login`과 같은 원리). 그래서 워커 자격증명
없이 도달한다 — 실측 확인: 포털 → slurm01 경유 → 다른 노드 22번 도달.

이 클래스는 목적지를 **인자로만** 받는다. `SshTarget.host`(로그인 노드)에서 유도하지
않는다 — 개발 환경은 둘이 같지만 노드가 분리되면 갈라진다(docs/plan.md §3.2).

PtySession과 같은 이유로 비블로킹으로 읽는다: 동기 paramiko를 async 웹소켓에 잇는다.
"""

from __future__ import annotations

import socket
from typing import Any

import paramiko

from app.clients.ssh.client import SshTarget, _load_key
from app.core.errors import ExternalServiceError, ValidationFailed


class TcpTunnel:
    """로그인 노드를 거쳐 `(host, port)`로 가는 TCP 스트림."""

    def __init__(
        self,
        target: SshTarget,
        *,
        dest_host: str,
        dest_port: int,
        known_hosts: str | None,
        timeout: float = 10.0,
    ):
        if not dest_host:
            raise ValidationFailed("터널 목적지 호스트가 필요합니다.")
        self._t = target
        self._dest = (dest_host, int(dest_port))
        self._known_hosts = known_hosts
        self._timeout = timeout
        self._ssh: paramiko.SSHClient | None = None
        self._chan: paramiko.Channel | None = None

    @property
    def dest(self) -> tuple[str, int]:
        return self._dest

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
            client.close()
            raise ExternalServiceError("SSH 전송이 열려 있지 않습니다.")
        try:
            # 목적지 이름은 **로그인 노드가** 해석한다. 포털에서 풀 필요가 없다.
            chan = transport.open_channel(
                "direct-tcpip", self._dest, ("127.0.0.1", 0), timeout=self._timeout
            )
        except paramiko.SSHException as exc:
            client.close()
            raise ExternalServiceError(
                f"세션 노드에 연결할 수 없습니다({self._dest[0]}:{self._dest[1]}): {exc}"
            ) from exc
        chan.settimeout(0.0)  # 비블로킹 — 읽기 루프가 스레드를 붙잡지 않게
        self._ssh, self._chan = client, chan

    # --- 입출력 --------------------------------------------------------
    def read(self, size: int = 65536) -> bytes | None:
        """읽을 게 없으면 b"", 상대가 끊었으면 None."""
        chan = self._chan
        if chan is None or chan.closed:
            return None
        try:
            if chan.recv_ready():
                data = chan.recv(size)
                # 빈 바이트는 EOF다 — b""(읽을 것 없음)와 구분해야 한다.
                return data if data else None
            if chan.eof_received:
                return None
        except (OSError, socket.timeout):
            return None
        return b""

    def write(self, data: bytes) -> None:
        if self._chan is not None and not self._chan.closed:
            self._chan.sendall(data)

    def close(self) -> None:
        for closable in (self._chan, self._ssh):
            try:
                if closable is not None:
                    closable.close()
            except Exception:  # pragma: no cover - 종료 경로는 조용히 정리한다
                pass
        self._chan = self._ssh = None

    def __enter__(self) -> "TcpTunnel":
        self.open()
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()
