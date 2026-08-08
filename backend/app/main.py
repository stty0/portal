"""FastAPI 앱 조립 (backend-design §1.1: JSON API 전용, View 계층 없음)."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.clients.factory import ClusterClientFactory
from app.clients.token_provider import SlurmTokenProvider
from app.core.config import Settings, get_settings
from fastapi.exceptions import RequestValidationError

from app.core.errors import (
    PortalError,
    portal_error_handler,
    unhandled_error_handler,
    validation_error_handler,
)
from app.core.redis_client import (
    PermissionCache,
    RefreshTokenStore,
    SessionStore,
    build_redis,
)
from app.core.secrets import EnvSecretStore
from app.db.session import dispose_engine, init_engine
from app.routers import (
    account,
    api_tokens,
    auth,
    billing,
    clusters,
    files,
    health,
    jobs,
    ops,
    reports,
    sessions,
    terminal,
    users,
)

logger = logging.getLogger(__name__)


def bootstrap_state(app: FastAPI, settings: Settings) -> None:
    """싱글턴 자원을 app.state에 심는다 — 라우터는 Depends로만 접근한다.

    Pod 로컬 캐시는 멀티 replica에서 불일치를 만들므로 세션·권한 캐시는
    반드시 Redis를 거친다(backend-design §4.2).
    """
    redis = build_redis(settings.redis_url)
    app.state.redis = redis
    app.state.session_store = SessionStore(redis, settings.session_ttl_seconds)
    app.state.refresh_token_store = RefreshTokenStore(redis, settings.refresh_token_ttl_seconds)
    app.state.permission_cache = PermissionCache(redis, settings.permission_cache_ttl_seconds)
    app.state.secret_store = EnvSecretStore(settings)
    app.state.token_provider = SlurmTokenProvider(app.state.secret_store)
    app.state.client_factory = ClusterClientFactory(settings, app.state.token_provider)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    init_engine(settings.database_url)
    bootstrap_state(app, settings)

    scheduler = None
    if settings.scheduler_enabled:
        # 배치는 K8s CronJob 대신 앱 내장 스케줄러 + Redis 분산락(§5.5)
        from apscheduler.schedulers.background import BackgroundScheduler

        from app.jobs.ad_sync import schedule as schedule_ad_sync

        scheduler = BackgroundScheduler()
        schedule_ad_sync(scheduler, settings, app.state.redis, app.state.secret_store)
        scheduler.start()

    try:
        yield
    finally:
        if scheduler is not None:
            scheduler.shutdown(wait=False)
        app.state.client_factory.close_all()
        dispose_engine()


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    # 프론트엔드와 같은 도메인을 쓰므로 백엔드가 노출하는 경로를 전부 API 프리픽스
    # 아래로 모은다 — 리버스 프록시는 `/api` 하나만 백엔드로 넘기면 된다.
    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        lifespan=lifespan,
        docs_url=f"{settings.api_prefix}/docs",
        openapi_url=f"{settings.api_prefix}/openapi.json",
        redoc_url=f"{settings.api_prefix}/redoc",
    )

    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.add_exception_handler(PortalError, portal_error_handler)
    app.add_exception_handler(Exception, unhandled_error_handler)

    app.include_router(health.router)
    for module in (
        auth, users, clusters, jobs, files, billing,
        terminal, reports, sessions, account, ops, api_tokens,
    ):
        app.include_router(module.router, prefix=settings.api_prefix)

    return app


app = create_app()
