"""웹 터미널 웹소켓 (U-SH-01).

인증: 브라우저 웹소켓은 Authorization 헤더를 붙일 수 없다. 토큰을 쿼리스트링에 실으면
접근 로그·리퍼러에 남으므로 **subprotocol**로 받는다(`portal.token.<jwt>`).
"""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.config import get_settings
from app.core.errors import PortalError
from app.db.session import get_session_factory
from app.services.terminal import TerminalService

router = APIRouter(tags=["terminal"])

TOKEN_PREFIX = "portal.token."
# 읽을 게 없을 때의 대기. 너무 짧으면 CPU를 태우고 너무 길면 입력 반응이 굼뜨다.
POLL_SECONDS = 0.02


def _offered_token(websocket: WebSocket) -> tuple[str | None, str | None]:
    for offered in websocket.scope.get("subprotocols") or []:
        if offered.startswith(TOKEN_PREFIX):
            return offered[len(TOKEN_PREFIX) :], offered
    return None, None


@router.websocket("/clusters/{cid}/terminal")
async def terminal(websocket: WebSocket, cid: int) -> None:
    settings = get_settings()
    token, protocol = _offered_token(websocket)
    if not token:
        await websocket.close(code=4401)
        return

    db = get_session_factory()()
    # 싱글턴 자원은 app.state에서 꺼낸다 — 웹소켓마다 Redis 연결을 새로 만들지 않는다.
    service = TerminalService(
        db,
        settings=settings,
        secrets=websocket.app.state.secret_store,
        sessions=websocket.app.state.session_store,
    )
    try:
        user = service.authenticate(token)
        pty = await asyncio.to_thread(service.open, cid, user=user)
    except PortalError as exc:
        # 접속은 받아들이고 사유를 화면에 찍어 준다 — 코드만 닫으면 원인을 알 수 없다.
        await websocket.accept(subprotocol=protocol)
        await websocket.send_bytes(f"\r\n\x1b[31m{exc.message}\x1b[0m\r\n".encode())
        await websocket.close(code=4400)
        db.close()
        return
    except Exception:
        await websocket.close(code=4500)
        db.close()
        return

    await websocket.accept(subprotocol=protocol)
    service.record("TERMINAL_OPEN", user=user, cluster_id=cid)

    async def pump_output() -> None:
        """PTY → 브라우저. paramiko는 동기라 스레드에서 읽어 루프를 막지 않는다."""
        while True:
            chunk = await asyncio.to_thread(pty.read)
            if chunk is None:
                break
            if chunk:
                await websocket.send_bytes(chunk)
            else:
                await asyncio.sleep(POLL_SECONDS)

    output = asyncio.create_task(pump_output())
    try:
        while True:
            message = await websocket.receive_json()
            if not isinstance(message, dict):
                continue
            if "i" in message:
                await asyncio.to_thread(pty.write, str(message["i"]))
            elif "resize" in message:
                cols, rows = message["resize"]
                await asyncio.to_thread(pty.resize, int(cols), int(rows))
    except (WebSocketDisconnect, ValueError):
        pass
    finally:
        output.cancel()
        await asyncio.to_thread(pty.close)
        service.record("TERMINAL_CLOSE", user=user, cluster_id=cid)
        db.close()
