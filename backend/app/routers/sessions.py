"""인터랙티브 세션 라우터 (U-IA-01·02·04).

REST는 세션 생명주기, 웹소켓은 RFB 바이트 중계만 한다. 인증·목적지 해석·터널 개설은
`SessionService`가 갖는다(backend-design §1.2 router → service → client).
"""

from __future__ import annotations

import asyncio
from contextlib import suppress
from typing import Annotated

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect

from app.core.config import get_settings
from app.core.cookies import ACCESS_COOKIE
from app.core.deps import (
    AppImageCacheDep,
    AppSettings,
    ClientFactoryDep,
    CurrentUser,
    DbSession,
    SecretStoreDep,
)
from app.core.errors import PortalError
from app.db.session import get_session_factory
from app.schemas.common import OkResponse
from app.schemas.session import (
    InteractiveAppOut,
    SessionConnectInfo,
    SessionCreate,
    SessionOut,
)
from app.services.app_access import KIND_INTERACTIVE, AppAccessService
from app.services.app_images import AppImageService
from app.services.cluster import ClusterService
from app.services.session import SessionService
from app.services.session_apps import APPS
from app.services.session_apps import get as session_app
from app.services.session_script import SessionSpec

router = APIRouter(tags=["sessions"])

TOKEN_PREFIX = "portal.token."
# 읽을 게 없을 때의 대기. 화면 갱신 반응성과 CPU 사용의 절충(터미널과 같은 값).
POLL_SECONDS = 0.02


def _service(
    db: DbSession, secrets: SecretStoreDep, clients: ClientFactoryDep
) -> SessionService:
    clusters = ClusterService(db, secrets=secrets, client_factory=clients)
    return SessionService(db, clusters, settings=get_settings(), secrets=secrets)


SessionServiceDep = Annotated[SessionService, Depends(_service)]


def _access(
    db: DbSession, secrets: SecretStoreDep, clients: ClientFactoryDep
) -> AppAccessService:
    return AppAccessService(db, ClusterService(db, secrets=secrets, client_factory=clients))


AppAccessServiceDep = Annotated[AppAccessService, Depends(_access)]


def _images(
    db: DbSession,
    secrets: SecretStoreDep,
    clients: ClientFactoryDep,
    settings: AppSettings,
    cache: AppImageCacheDep,
) -> AppImageService:
    clusters = ClusterService(db, secrets=secrets, client_factory=clients)
    return AppImageService(db, clusters, settings=settings, secrets=secrets, cache=cache)


AppImageServiceDep = Annotated[AppImageService, Depends(_images)]


@router.get(
    "/clusters/{cid}/interactive-apps",
    response_model=list[InteractiveAppOut],
    summary="인터랙티브 앱 목록 (U-IA-01)",
)
def list_interactive_apps(
    cid: int,
    user: CurrentUser,
    access: AppAccessServiceDep,
    images: AppImageServiceDep,
    refresh: bool = False,
) -> list[InteractiveAppOut]:
    """앱 목록의 단일 출처. 프론트엔드가 같은 배열을 또 갖지 않게 한다.

    예정된 앱(`ready=false`)도 함께 내려보낸다 — 런처가 보여주되 고를 수 없게 한다.

    **클러스터에 매인 목록이다.** 앱마다 쓸 수 있는 계정이 정해질 수 있고 계정은
    클러스터별 slurmdbd 소유라, 같은 앱이 클러스터마다 다르게 잠긴다.

    `refresh=true`는 **이미지 목록 캐시를 건너뛴다**(화면의 `↻ 새로고침`이 쓴다).
    SIF는 포털 밖에서 놓이므로 서버가 변화를 알 수 없다 — 방금 올린 이미지를 바로
    보려면 사람이 눌러 알려주는 수밖에 없다. 대가는 SSH 왕복 300~430ms다.
    """
    cluster = access.clusters.get(cid)
    verdict = access.allowances(cluster, KIND_INTERACTIVE, user=user)
    present = images.installed_map(
        cluster, KIND_INTERACTIVE, username=user.username, refresh=refresh
    )
    return [
        InteractiveAppOut(
            id=a.id, name=a.name, description=a.description, fid=a.fid,
            ready=a.ready, transport=a.transport, note=a.note,
            installed=present.get(a.id, False),
            allowed=verdict[a.id].allowed, accounts=verdict[a.id].accounts,
        )
        for a in APPS
    ]


@router.post(
    "/clusters/{cid}/sessions",
    response_model=SessionOut,
    status_code=201,
    summary="인터랙티브 세션 시작 (U-IA-01·02)",
)
def create_session(
    cid: int,
    payload: SessionCreate,
    user: CurrentUser,
    service: SessionServiceDep,
    access: AppAccessServiceDep,
    images: AppImageServiceDep,
) -> SessionOut:
    cluster = service.clusters.get(cid)
    catalog = session_app(payload.app)
    # 목록에서 잠그는 것만으로는 제한이 되지 않는다 — 여기서 막고, 배정된 앱이면
    # **어느 계정으로 돌지도 여기서 정해진다**(안 골랐으면 서버가 채운다).
    account = access.resolve_account(
        cluster, KIND_INTERACTIVE, payload.app, user=user, account=payload.account
    )
    spec = SessionSpec(
        image_ref=images.resolve_installed(
            cluster, KIND_INTERACTIVE, payload.app, username=user.username
        ),
        app=payload.app,
        entry=catalog.entry,
        partition=payload.partition,
        account=account,
        qos=payload.qos,
        cpus=payload.cpus,
        memory_gb=payload.memory_gb,
        walltime=payload.walltime,
        geometry=payload.geometry,
        exclusive=payload.exclusive,
    )
    record = service.create(cluster, spec, user=user)
    return SessionOut(**service.get(record.id, user=user))


@router.get(
    "/clusters/{cid}/sessions",
    response_model=list[SessionOut],
    summary="내 세션 목록 (U-IA-04)",
)
def list_sessions(cid: int, user: CurrentUser, service: SessionServiceDep) -> list[SessionOut]:
    # 대상 사용자는 언제나 요청자 본인 — 클라이언트가 지정할 수 없다.
    return [SessionOut(**s) for s in service.list(user=user, cluster_id=cid)]


@router.get("/sessions/{sid}", response_model=SessionOut, summary="세션 상태 (U-IA-04)")
def get_session(sid: int, user: CurrentUser, service: SessionServiceDep) -> SessionOut:
    return SessionOut(**service.get(sid, user=user))


@router.get(
    "/sessions/{sid}/connection",
    response_model=SessionConnectInfo,
    summary="RFB 접속 정보 (U-IA-02)",
)
def session_connection(
    sid: int, user: CurrentUser, service: SessionServiceDep
) -> SessionConnectInfo:
    info = service.connection(sid, user=user)
    # host·port는 응답에 담지 않는다 — 백엔드만 알면 된다.
    return SessionConnectInfo(password=info.get("password"), geometry=info.get("geometry"))


@router.delete("/sessions/{sid}", response_model=OkResponse, summary="세션 종료 (U-IA-04)")
def terminate_session(sid: int, user: CurrentUser, service: SessionServiceDep) -> OkResponse:
    service.terminate(sid, user=user)
    return OkResponse(message="세션을 종료했습니다.")

def ws_access_token(websocket: WebSocket) -> tuple[str | None, str | None]:
    """웹소켓 인증 토큰 — (토큰, 되돌려줄 subprotocol).

    브라우저는 **쿠키**로 보낸다. 웹소켓 handshake도 같은 오리진이면 쿠키가 실리므로
    JS가 토큰을 읽을 필요가 없다 — 그게 HttpOnly로 옮긴 이유다.

    subprotocol·Authorization 경로도 남긴다. **기계 클라이언트는 쿠키 항아리를 쓰지
    않기 때문**이고, 배포 중에 열려 있던 예전 탭도 이 경로로 살아 있다.
    """
    cookie = websocket.cookies.get(ACCESS_COOKIE)
    if cookie:
        return cookie, None
    header = websocket.headers.get("authorization", "")
    scheme, _, token = header.partition(" ")
    if scheme.lower() == "bearer" and token:
        return token, None
    for offered in websocket.scope.get("subprotocols") or []:
        if offered.startswith(TOKEN_PREFIX):
            return offered[len(TOKEN_PREFIX) :], offered
    return None, None


@router.websocket("/sessions/{sid}/connect")
async def session_connect(websocket: WebSocket, sid: int) -> None:
    """브라우저 noVNC ↔ 워커 노드 Xvnc 사이의 RFB 바이트 중계.

    websockify를 쓰지 않는 이유가 여기 있다 — WebSocket↔TCP 변환이 곧 이 루프다
    (docs/plan.md §3.3).
    """
    settings = get_settings()
    token, protocol = ws_access_token(websocket)
    if not token:
        await websocket.close(code=4401)
        return

    db = get_session_factory()()
    clusters = ClusterService(
        db,
        secrets=websocket.app.state.secret_store,
        client_factory=websocket.app.state.client_factory,
    )
    service = SessionService(
        db,
        clusters,
        settings=settings,
        secrets=websocket.app.state.secret_store,
        session_store=websocket.app.state.session_store,
    )
    try:
        user = service.authenticate(token)
        tunnel = await asyncio.to_thread(service.open_stream, sid, user=user)
    except PortalError:
        # RFB는 텍스트 오류를 표시할 방법이 없다 — 코드로만 알린다.
        # 사유는 REST(GET /sessions/{sid})로 확인한다.
        await websocket.close(code=4400)
        db.close()
        return
    except Exception:
        await websocket.close(code=4500)
        db.close()
        return

    await websocket.accept(subprotocol=protocol)
    cluster_id = service.get(sid, user=user)["cluster_id"]
    service.record("SESSION_CONNECT", user=user, session_id=sid, cluster_id=cluster_id)

    async def pump_output() -> None:
        """VNC → 브라우저. paramiko는 동기라 스레드에서 읽어 루프를 막지 않는다.

        **원격이 EOF를 주면 웹소켓도 닫는다.** 세션 Job이 끝나면(앱 종료·scancel)
        워커의 Xvnc가 사라지는데, 닫아 주지 않으면 브라우저는 멈춘 화면을 붙잡고
        끊긴 줄 모른다 — 프론트가 세션 종료를 알아채려면 이 신호가 필요하다.
        """
        while True:
            chunk = await asyncio.to_thread(tunnel.read)
            if chunk is None:
                break
            if chunk:
                await websocket.send_bytes(chunk)
            else:
                await asyncio.sleep(POLL_SECONDS)
        # 이미 닫힌 뒤일 수 있다(브라우저가 먼저 나간 경우) — 그건 오류가 아니다.
        with suppress(Exception):
            await websocket.close(code=1000)

    output = asyncio.create_task(pump_output())
    try:
        while True:
            data = await websocket.receive_bytes()
            await asyncio.to_thread(tunnel.write, data)
    # RuntimeError: 위에서 닫은 뒤 receive를 부르면 starlette이 이걸 낸다.
    except (WebSocketDisconnect, RuntimeError, ValueError, KeyError):
        pass
    finally:
        output.cancel()
        await asyncio.to_thread(tunnel.close)
        service.record("SESSION_DISCONNECT", user=user, session_id=sid, cluster_id=cluster_id)
        db.close()
