"""AD 동기화 배치 (backend-design §5.5).

K8s CronJob 대신 앱 내장 스케줄러(APScheduler)로 돌린다. 멀티 replica에서
중복 실행되지 않도록 Redis 분산락으로 감싼다.
"""

import logging

from app.core.config import Settings
from app.core.redis_client import RedisLike, SessionStore, redis_lock
from app.core.secrets import SecretStore
from app.db.session import session_scope
from app.services.ad import AdService
from app.services.auth import AuthService

logger = logging.getLogger(__name__)

SYNC_LOCK_KEY = "sync:lock:ad"


def run_ad_sync(settings: Settings, redis: RedisLike, secrets: SecretStore) -> None:
    with redis_lock(redis, SYNC_LOCK_KEY, timeout=600) as acquired:
        if not acquired:
            logger.info("AD 동기화: 다른 replica가 실행 중이므로 건너뜀")
            return
        for session in session_scope():
            auth = AuthService(
                session,
                settings,
                secrets=secrets,
                sessions=SessionStore(redis, settings.session_ttl_seconds),
            )
            try:
                result = AdService(session, auth).sync()
            except Exception:
                logger.exception("AD 동기화 실패")
                raise
            logger.info("AD 동기화 완료 — %s", result.summary())


def schedule(scheduler, settings: Settings, redis: RedisLike, secrets: SecretStore) -> None:
    scheduler.add_job(
        run_ad_sync,
        "interval",
        seconds=settings.ad_sync_interval_seconds,
        args=[settings, redis, secrets],
        id="ad_sync",
        replace_existing=True,
    )
