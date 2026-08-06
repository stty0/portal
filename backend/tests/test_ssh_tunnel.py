"""로그인 노드 경유 TCP 터널 (T-05, U-IA-02).

핵심은 **목적지가 로그인 노드에서 유도되지 않는다**는 것이다. 개발 환경은 로그인 노드와
워커가 같은 기계라 잘못 짜도 동작한다 — 분리되는 날 깨진다(docs/plan.md §3.2).
"""

import pytest

from app.clients.ssh.client import SshTarget
from app.clients.ssh.tunnel import TcpTunnel
from app.core.errors import ValidationFailed

LOGIN = SshTarget(host="login01", port=22, account="svc", private_key="KEY")
WORKER = "node012"


class FakeChannel:
    def __init__(self, chunks=()):
        self.closed = False
        self.eof_received = False
        self.sent = bytearray()
        self._chunks = list(chunks)
        self.timeout = None

    def settimeout(self, t):
        self.timeout = t

    def recv_ready(self):
        return bool(self._chunks)

    def recv(self, size):
        return self._chunks.pop(0)

    def sendall(self, data):
        self.sent.extend(data)

    def close(self):
        self.closed = True


class FakeTransport:
    def __init__(self, channel):
        self.channel = channel
        self.opened: list[tuple] = []

    def open_channel(self, kind, dest, src, timeout=None):
        self.opened.append((kind, dest, src))
        return self.channel


class FakeSshClient:
    last: "FakeSshClient | None" = None

    def __init__(self, channel=None):
        self.transport = FakeTransport(channel or FakeChannel())
        self.connected: dict = {}
        self.host_keys_loaded = None
        self.policy = None
        FakeSshClient.last = self

    def load_host_keys(self, path):
        self.host_keys_loaded = path

    def set_missing_host_key_policy(self, policy):
        self.policy = policy

    def connect(self, **kw):
        self.connected = kw

    def get_transport(self):
        return self.transport

    def close(self):
        pass


@pytest.fixture
def fake_ssh(monkeypatch):
    channel = FakeChannel()

    def factory():
        return FakeSshClient(channel)

    monkeypatch.setattr("app.clients.ssh.tunnel.paramiko.SSHClient", factory)
    monkeypatch.setattr("app.clients.ssh.tunnel._load_key", lambda pem: "PKEY")
    return channel


def open_tunnel(known_hosts="/etc/portal/ssh/known_hosts", **kw) -> TcpTunnel:
    t = TcpTunnel(LOGIN, dest_host=WORKER, dest_port=5903, known_hosts=known_hosts, **kw)
    t.open()
    return t


def test_ssh_connects_to_the_login_node(fake_ssh):
    open_tunnel()
    assert FakeSshClient.last.connected["hostname"] == "login01"
    assert FakeSshClient.last.connected["username"] == "svc"


def test_tunnel_destination_is_the_worker_not_the_login_node(fake_ssh):
    """분리 대비의 핵심 — 목적지는 인자로 받은 워커여야 한다."""
    open_tunnel()
    kind, dest, _src = FakeSshClient.last.transport.opened[0]
    assert kind == "direct-tcpip"
    assert dest == (WORKER, 5903)
    assert dest[0] != LOGIN.host


def test_destination_is_not_resolved_locally(fake_ssh):
    # 이름 해석은 로그인 노드가 한다 — 포털이 풀지 못하는 이름도 그대로 넘긴다.
    t = TcpTunnel(LOGIN, dest_host="node-only-known-in-cluster", dest_port=5901,
                  known_hosts="/etc/portal/ssh/known_hosts")
    t.open()
    assert FakeSshClient.last.transport.opened[0][1][0] == "node-only-known-in-cluster"


def test_empty_destination_is_rejected():
    with pytest.raises(ValidationFailed):
        TcpTunnel(LOGIN, dest_host="", dest_port=5901, known_hosts="/k")


def test_missing_known_hosts_is_rejected(fake_ssh):
    # 호스트키 검증 없이 붙지 않는다(웹 터미널과 같은 규칙).
    with pytest.raises(ValidationFailed):
        open_tunnel(known_hosts=None)


def test_host_keys_are_verified(fake_ssh):
    open_tunnel()
    assert FakeSshClient.last.host_keys_loaded == "/etc/portal/ssh/known_hosts"
    assert type(FakeSshClient.last.policy).__name__ == "RejectPolicy"


def test_reads_are_non_blocking(fake_ssh):
    open_tunnel()
    assert fake_ssh.timeout == 0.0


def test_read_distinguishes_idle_from_eof(fake_ssh):
    t = open_tunnel()
    assert t.read() == b""  # 읽을 것 없음
    fake_ssh._chunks.append(b"RFB 003.008\n")
    assert t.read() == b"RFB 003.008\n"
    fake_ssh.eof_received = True
    assert t.read() is None  # 상대가 끊음


def test_read_after_close_returns_none(fake_ssh):
    t = open_tunnel()
    t.close()
    assert t.read() is None


def test_write_passes_bytes_through(fake_ssh):
    t = open_tunnel()
    t.write(b"RFB 003.008\n")
    assert bytes(fake_ssh.sent) == b"RFB 003.008\n"
