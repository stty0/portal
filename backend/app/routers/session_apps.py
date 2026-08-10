"""HTTP 인터랙티브 앱 리버스 프록시 (U-IA-01 JupyterLab).

경로는 컨테이너가 정한 `base_url`과 **글자 하나까지 같아야 한다** —
`start-jupyter.sh`가 `--ServerApp.base_url=/api/v1/session-apps/$SLURM_JOB_ID/`로 띄우고,
Jupyter가 HTML 안의 모든 링크에 그 접두사를 스스로 붙인다(실측). 그래서 이 프록시는
**본문을 고쳐 쓰지 않는다** — 바이트를 그대로 옮긴다.

## CSRF 검사를 하지 않는 이유

포털 API는 쿠키 인증에 double-submit CSRF를 요구한다. 그런데 Jupyter의 자바스크립트는
포털의 `X-CSRF-Token`을 모른다 — 노트북 저장·커널 생성이 전부 401이 된다.

여기서 검사를 빼도 되는 근거는 **`SameSite=Strict`**다. 다른 사이트에서 온 요청에는
액세스 쿠키가 애초에 실리지 않는다(double-submit은 그 위의 두 번째 겹이다). 게다가
Jupyter 자신이 XSRF 검사와 토큰 인증을 따로 갖고 있다.

## 앱 토큰은 브라우저에 내보내지 않는다

JupyterLab 토큰은 `connection.json`에만 있고, 포털이 **요청마다 헤더로 붙인다**. 주소창에
토큰이 실리면 접속 로그·리퍼러·북마크에 남는다(웹 터미널에서 쿼리스트링을 피한 것과 같은 이유).
"""

from __future__ import annotations

import asyncio
from contextlib import suppress
import httpx
from fastapi import APIRouter, Request, Response, WebSocket, WebSocketDisconnect
from starlette.responses import HTMLResponse, StreamingResponse

from app.core.config import Settings
from app.core.deps import AppSettings
from app.core.cookies import ACCESS_COOKIE
from app.core.errors import PortalError, Unauthenticated
from app.core.security import decode_session_token
from app.db.session import get_session_factory
from app.models import User
from app.services.cluster import ClusterService
from app.services.session_proxy import TARGETS, AppTarget, SessionProxyService
from app.services.ws_auth import authenticate_ws_token

router = APIRouter(tags=["session-apps"])

#: 홉 단위 헤더. 프록시가 그대로 옮기면 안 되는 것들(RFC 9110).
HOP_BY_HOP = frozenset(
    {
        "connection", "keep-alive", "proxy-authenticate", "proxy-authorization",
        "te", "trailers", "transfer-encoding", "upgrade",
    }
)

PROXY_METHODS = ["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"]

#: 세션이 아직 뜨는 중일 때 보여 줄 페이지. 2초마다 스스로 다시 시도한다.
#: **외부 자원을 쓰지 않는다** — 아직 붙지도 못한 상태에서 CSS·폰트를 더 부르지 않는다.
_STARTING_PAGE = """<!doctype html>
<html lang="ko"><head><meta charset="utf-8">
<meta http-equiv="refresh" content="2">
<title>세션 준비 중</title>
<style>
  body{margin:0;height:100vh;display:grid;place-items:center;background:#f4f6fa;
       font-family:'Noto Sans KR','Malgun Gothic',system-ui,sans-serif;color:#1a1f36}
  .box{text-align:center}
  h1{font-size:19px;font-weight:700;margin:0 0 8px}
  p{margin:0;color:#4b5468;font-size:14.5px}
</style></head>
<body><div class="box">
  <h1>세션을 준비하는 중입니다</h1>
  <p>앱이 워커 노드에서 뜨는 중입니다. 준비되면 자동으로 열립니다.</p>
</div></body></html>"""


def _clean(headers, *, drop: set[str] = frozenset()) -> dict[str, str]:
    return {
        k: v for k, v in headers.items() if k.lower() not in HOP_BY_HOP and k.lower() not in drop
    }


def _bearer_or_cookie(request_headers, cookies) -> str | None:
    """액세스 토큰. **CSRF 검사는 하지 않는다**(파일 머리말 참조)."""
    scheme, _, token = request_headers.get("authorization", "").partition(" ")
    if scheme.lower() == "bearer" and token:
        return token
    return cookies.get(ACCESS_COOKIE)


async def _resolve(app_state, settings: Settings, token: str, job_id: str) -> AppTarget:
    """토큰 + Job ID → 붙을 곳. **빠른 길과 느린 길이 나뉜다.**

    빠른 길(캐시 적중): JWT 서명 확인 + Redis 세션 조회뿐이다 — DB도 SSH도 건드리지 않는다.
    느린 길(최초 1회): DB에서 세션을 찾고 SSH로 `connection.json`을 읽어 포워딩을 띄운다.

    **인증은 두 길 모두에서 한다.** 캐시가 건너뛰는 것은 "어디에 붙는가"이지 "누구인가"가
    아니다 — 로그아웃하면 Redis 세션이 사라져 그 즉시 막힌다.
    """
    payload = decode_session_token(settings, token)
    sid = str(payload.get("sid") or "")
    data = app_state.session_store.get(sid) if sid else None
    if data is None:
        raise Unauthenticated("세션이 만료되었거나 로그아웃되었습니다.")

    cached = TARGETS.get(job_id, data.user_guid)
    if cached is not None:
        return cached

    ctx = _Context(app_state, settings)
    try:
        user = await asyncio.to_thread(ctx.user, token)
        return await asyncio.to_thread(ctx.service.target, job_id, user=user)
    finally:
        ctx.close()


class _Context:
    """요청 하나가 쓰는 DB 세션 + 서비스. 끝나면 반드시 닫는다.

    설정은 **주입받는다** — 모듈에서 `get_settings()`를 직접 부르면 import 시점에 이름이
    묶여 테스트가 갈아끼운 설정이 안 먹는다(JWT 비밀키가 달라 인증이 통째로 실패한다).
    """

    def __init__(self, app_state, settings: Settings) -> None:
        self.db = get_session_factory()()
        clusters = ClusterService(
            self.db, secrets=app_state.secret_store, client_factory=app_state.client_factory
        )
        self.settings = settings
        self.store = app_state.session_store
        self.service = SessionProxyService(
            self.db, clusters, settings=settings, secrets=app_state.secret_store
        )

    def user(self, token: str) -> User:
        return authenticate_ws_token(
            self.db, settings=self.settings, sessions=self.store, token=token
        )

    def close(self) -> None:
        self.db.close()


@router.api_route("/session-apps/{job_id}/{path:path}", methods=PROXY_METHODS)
async def proxy_http(
    job_id: str, path: str, request: Request, settings: AppSettings
) -> Response:
    token = _bearer_or_cookie(request.headers, request.cookies)
    if not token:
        return Response(status_code=401, content=b"portal: not authenticated")

    try:
        target = await _resolve(request.app.state, settings, token, job_id)
    except PortalError as exc:
        if isinstance(exc.detail, dict) and exc.detail.get("reason") == "starting":
            # **실패가 아니라 기다릴 일이다.** Slurm이 RUNNING으로 바꾼 뒤 컨테이너가
            # 앱을 띄우기까지 시간이 더 걸린다 — 오류 문자열만 던지면 사용자는 세션이
            # 깨진 줄 알고 다시 만든다. 스스로 새로고침하는 대기 화면을 준다.
            return HTMLResponse(_STARTING_PAGE, status_code=503)
        return Response(status_code=exc.status_code, content=exc.message.encode())
    except Exception:
        return Response(status_code=502, content=b"portal: session app unreachable")

    upstream = f"http://127.0.0.1:{target.local_port}/api/v1/session-apps/{job_id}/{path}"
    headers = _clean(request.headers, drop={"host"})
    if target.token:
        # 앱 토큰은 포털이 붙인다 — 브라우저는 모른다.
        headers["authorization"] = f"token {target.token}"

    client = _http_client()
    try:
        req = client.build_request(
            request.method,
            upstream,
            headers=headers,
            params=dict(request.query_params),
            content=await request.body(),
        )
        response = await client.send(req, stream=True, follow_redirects=False)
    except Exception:
        return Response(status_code=502, content=b"portal: session app did not answer")

    async def body():
        try:
            # **원본 바이트 그대로.** 압축을 풀면 Content-Length·Content-Encoding이 어긋난다.
            async for chunk in response.aiter_raw():
                yield chunk
        finally:
            await response.aclose()

    return StreamingResponse(
        body(),
        status_code=response.status_code,
        headers=_clean(response.headers),
        media_type=response.headers.get("content-type"),
    )


@router.websocket("/session-apps/{job_id}/{path:path}")
async def proxy_ws(
    websocket: WebSocket, job_id: str, path: str, settings: AppSettings
) -> None:
    """Jupyter 커널 채널 중계.

    커널은 웹소켓으로 오간다 — HTTP만 프록시하면 노트북이 **열리지만 실행되지 않는다**.

    설정은 HTTP 쪽과 **같이 주입받는다**. 여기서 `get_settings()`를 직접 부르면 import
    시점에 이름이 묶여 테스트가 갈아끼운 설정이 안 먹고, 그러면 이 경로만 검증에서
    빠진다(실제로 그랬다 — 커널 채널이 죽어도 아무도 몰랐을 것이다).
    """
    token = _bearer_or_cookie(websocket.headers, websocket.cookies)
    if not token:
        await websocket.close(code=4401)
        return

    try:
        target = await _resolve(websocket.app.state, settings, token, job_id)
    except PortalError:
        await websocket.close(code=4400)
        return
    except Exception:
        await websocket.close(code=4500)
        return

    # 서버 쪽에서만 쓰는 클라이언트다(uvicorn[standard]가 함께 설치한다).
    from websockets.asyncio.client import connect as ws_connect

    query = websocket.url.query
    upstream = (
        f"ws://127.0.0.1:{target.local_port}/api/v1/session-apps/{job_id}/{path}"
        + (f"?{query}" if query else "")
    )
    headers = {}
    if target.token:
        headers["Authorization"] = f"token {target.token}"
    # Jupyter는 커널 채널에서 subprotocol을 협상한다 — 브라우저가 요청한 것을 그대로 넘긴다.
    offered = websocket.scope.get("subprotocols") or []

    try:
        async with ws_connect(
            upstream, additional_headers=headers, subprotocols=offered or None, max_size=None
        ) as up:
            await websocket.accept(subprotocol=up.subprotocol)

            async def to_upstream() -> None:
                while True:
                    message = await websocket.receive()
                    if message["type"] == "websocket.disconnect":
                        return
                    if (data := message.get("bytes")) is not None:
                        await up.send(data)
                    elif (text := message.get("text")) is not None:
                        await up.send(text)

            async def to_browser() -> None:
                async for message in up:
                    if isinstance(message, bytes):
                        await websocket.send_bytes(message)
                    else:
                        await websocket.send_text(message)

            done, pending = await asyncio.wait(
                [asyncio.create_task(to_upstream()), asyncio.create_task(to_browser())],
                return_when=asyncio.FIRST_COMPLETED,
            )
            for task in pending:
                task.cancel()
    except WebSocketDisconnect:
        pass
    except Exception:
        with suppress(Exception):
            await websocket.close(code=4500)
    finally:
        with suppress(Exception):
            await websocket.close(code=1000)


_CLIENT: httpx.AsyncClient | None = None


def _http_client() -> httpx.AsyncClient:
    """프록시 전용 클라이언트 **하나**를 재사용한다.

    요청마다 만들면 루프백 연결도 매번 새로 맺는다 — 한 페이지에 요청이 수십 개인 앱에서는
    그 비용이 그대로 체감된다. keep-alive 풀은 세션 수만큼만 필요하다.
    """
    global _CLIENT
    if _CLIENT is None or _CLIENT.is_closed:
        _CLIENT = httpx.AsyncClient(
            timeout=httpx.Timeout(30.0, read=None),
            limits=httpx.Limits(max_connections=200, max_keepalive_connections=50),
        )
    return _CLIENT


def close_forwards() -> None:
    """종료 시 포워딩 정리. lifespan이 부른다."""
    from app.services.session_proxy import FORWARDS

    FORWARDS.close_all()
