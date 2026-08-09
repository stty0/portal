"""로그인 노드 경유 **로컬 포트포워딩** (U-IA-01 JupyterLab).

`TcpTunnel`은 스트림 하나를 브라우저 웹소켓에 잇는 용도다(VNC). HTTP 앱은 사정이 다르다 —
**페이지 한 장에 요청이 수십 개**고 브라우저가 동시에 연다. 요청마다 SSH 연결을 새로 열면
핸드셰이크만 수십 번이라 못 쓴다.

그래서 `ssh -L`과 같은 구조를 만든다: SSH 연결을 하나 잡아 두고 백엔드의
`127.0.0.1:<임시포트>`로 받아, 들어온 소켓마다 `direct-tcpip` 채널을 연다. 채널 여는
비용은 밀리초 단위이고 핸드셰이크는 한 번뿐이다.

**127.0.0.1에만 bind한다.** 0.0.0.0에 열면 같은 네트워크에서 남의 세션 포트에 인증 없이
닿는다 — 포털이 앞에서 소유자를 확인하는 의미가 없어진다.
"""

from __future__ import annotations

import socket
import threading
import time
from typing import Any

import paramiko

from app.clients.ssh.client import SshTarget, _load_key
from app.core.errors import ExternalServiceError, ValidationFailed

#: 한 방향으로 한 번에 옮기는 바이트. SFTP 청크와 같은 크기.
CHUNK = 65536
#: 상대가 조용할 때 루프가 CPU를 태우지 않게 하는 대기.
IDLE_SLEEP = 0.02


class LocalPortForward:
    """`127.0.0.1:port` → (로그인 노드 경유) → `dest_host:dest_port`."""

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
        self._listener: socket.socket | None = None
        self._port = 0
        self._stop = threading.Event()
        self._threads: list[threading.Thread] = []
        #: 마지막 사용 시각. 오래 안 쓴 포워딩을 거두는 기준이다.
        self.last_used = time.monotonic()

    # --- 수명 ----------------------------------------------------------
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

        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        # **루프백에만.** 포트 번호는 커널이 고른다(0) — 고정하면 세션끼리 부딪힌다.
        listener.bind(("127.0.0.1", 0))
        listener.listen(16)
        listener.settimeout(0.5)

        self._ssh = client
        self._listener = listener
        self._port = listener.getsockname()[1]
        self._spawn(self._accept_loop)

    @property
    def port(self) -> int:
        return self._port

    @property
    def alive(self) -> bool:
        transport = self._ssh.get_transport() if self._ssh else None
        return bool(transport and transport.is_active() and not self._stop.is_set())

    def close(self) -> None:
        self._stop.set()
        for closable in (self._listener, self._ssh):
            try:
                if closable is not None:
                    closable.close()
            except Exception:  # pragma: no cover - 종료 경로는 조용히 정리한다
                pass
        self._listener = self._ssh = None

    def __enter__(self) -> "LocalPortForward":
        self.open()
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()

    # --- 내부 ----------------------------------------------------------
    def _spawn(self, fn, *args) -> None:
        thread = threading.Thread(target=fn, args=args, daemon=True)
        thread.start()
        self._threads.append(thread)

    def _accept_loop(self) -> None:
        while not self._stop.is_set():
            listener = self._listener
            if listener is None:
                return
            try:
                client_sock, _ = listener.accept()
            except socket.timeout:
                continue
            except OSError:
                return  # 닫혔다
            self.last_used = time.monotonic()
            self._spawn(self._serve, client_sock)

    def _serve(self, client_sock: socket.socket) -> None:
        """받은 소켓 하나를 SSH 채널에 잇는다."""
        chan = None
        try:
            ssh = self._ssh
            transport = ssh.get_transport() if ssh else None
            if transport is None:
                return
            # 목적지 이름은 **로그인 노드가** 해석한다(TcpTunnel과 같은 원리).
            chan = transport.open_channel(
                "direct-tcpip", self._dest, client_sock.getpeername(), timeout=self._timeout
            )
            self._pump(client_sock, chan)
        except Exception:  # noqa: BLE001 — 연결 하나가 죽어도 포워딩은 살아 있어야 한다
            pass
        finally:
            for closable in (chan, client_sock):
                try:
                    if closable is not None:
                        closable.close()
                except Exception:  # pragma: no cover
                    pass

    def _pump(self, sock: socket.socket, chan: paramiko.Channel) -> None:
        """양방향 중계. 어느 한쪽이 끊기면 둘 다 닫는다."""
        sock.settimeout(0.0)
        chan.settimeout(0.0)
        while not self._stop.is_set():
            moved = False
            try:
                data = sock.recv(CHUNK)
                if not data:
                    return  # 브라우저 쪽이 닫았다
                chan.sendall(data)
                moved = True
            except (BlockingIOError, socket.timeout):
                pass
            except OSError:
                return
            try:
                if chan.recv_ready():
                    data = chan.recv(CHUNK)
                    if not data:
                        return  # 앱 쪽이 닫았다
                    sock.sendall(data)
                    moved = True
                elif chan.eof_received or chan.closed:
                    return
            except (BlockingIOError, socket.timeout):
                pass
            except OSError:
                return
            if moved:
                self.last_used = time.monotonic()
            else:
                time.sleep(IDLE_SLEEP)
