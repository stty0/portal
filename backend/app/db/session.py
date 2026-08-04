"""DB 엔진/세션 팩토리 (backend-design §2.1: DB 세션은 매 요청 open/close)."""

from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

_engine: Engine | None = None
_session_factory: sessionmaker[Session] | None = None


def init_engine(database_url: str, **kwargs) -> Engine:
    global _engine, _session_factory
    connect_args = {}
    if database_url.startswith("sqlite"):
        connect_args["check_same_thread"] = False
    else:
        # 커넥션이 죽어 있을 때 조용히 실패하지 않도록 (MySQL wait_timeout 대응)
        kwargs.setdefault("pool_pre_ping", True)
    _engine = create_engine(database_url, connect_args=connect_args, **kwargs)
    _session_factory = sessionmaker(bind=_engine, autoflush=False, expire_on_commit=False)
    return _engine


def get_engine() -> Engine:
    if _engine is None:
        raise RuntimeError("DB 엔진이 초기화되지 않았습니다. init_engine()을 먼저 호출하세요.")
    return _engine


def get_session_factory() -> sessionmaker[Session]:
    if _session_factory is None:
        raise RuntimeError("DB 엔진이 초기화되지 않았습니다. init_engine()을 먼저 호출하세요.")
    return _session_factory


def session_scope() -> Iterator[Session]:
    """요청 단위 세션. 예외 시 롤백, 정상 종료 시 커밋은 service(트랜잭션 경계)가 결정."""
    session = get_session_factory()()
    try:
        yield session
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def dispose_engine() -> None:
    global _engine, _session_factory
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _session_factory = None
