"""웹 터미널 웹소켓 인증 (U-SH-01).

**이 파일이 없어서 사고가 났다.** 쿠키 인증으로 옮기면서 `terminal.py`에 `ACCESS_COOKIE`
import가 빠졌는데, 세션 WS만 테스트가 있어 아무도 잡지 못했다. 배포된 뒤에야
`NameError: name 'ACCESS_COOKIE' is not defined`로 500이 났다.
"""

import pytest

from app.core.cookies import ACCESS_COOKIE
from tests.conftest import login

WS = "/api/v1/clusters/{cid}/terminal"


def test_websocket_without_credentials_is_rejected(client, cluster, bootstrapped):
    client.cookies.clear()
    with pytest.raises(Exception):
        with client.websocket_connect(WS.format(cid=cluster.id)):
            pass


def test_cookie_is_accepted_on_the_handshake(client, cluster, bootstrapped):
    """브라우저는 토큰을 읽을 수 없다 — 쿠키가 handshake에 실려야 붙는다.

    SSH가 없어 연결은 실패하지만, **인증을 통과했는지**가 여기서 볼 것이다.
    인증 실패(4401)면 사유가 오지 않고, 통과하면 서비스 오류 사유가 온다.
    """
    client.post("/api/v1/auth/login", json={"username": "jrpark", "password": "pw-user"})
    assert client.cookies.get(ACCESS_COOKIE) is not None

    try:
        with client.websocket_connect(WS.format(cid=cluster.id)) as ws:
            # 인증을 통과했으므로 사유 메시지가 오거나 정상 종료된다.
            ws.receive()
    except Exception as exc:  # noqa: BLE001 — 종료 코드만 본다
        assert "4401" not in str(exc), "쿠키가 인증에 쓰이지 않았다"


def test_bearer_header_still_works_for_machine_clients(client, cluster, bootstrapped):
    """기계 클라이언트는 쿠키 항아리를 쓰지 않는다 — 헤더 경로를 남겨 뒀다."""
    token = login(client, "jrpark", "pw-user")
    try:
        with client.websocket_connect(
            WS.format(cid=cluster.id), headers={"Authorization": f"Bearer {token}"}
        ) as ws:
            ws.receive()
    except Exception as exc:  # noqa: BLE001
        assert "4401" not in str(exc), "Bearer 헤더가 인증에 쓰이지 않았다"


def test_routers_that_authenticate_websockets_import_what_they_use(client):
    """import 누락은 **요청이 올 때까지** 드러나지 않는다 — 미리 부딪혀 본다."""
    from app.routers import sessions, terminal

    for module in (terminal, sessions):
        assert module.ws_access_token.__module__ == module.__name__
        # 이름 해석이 실패하면 여기서 NameError가 난다.
        assert module.ACCESS_COOKIE
