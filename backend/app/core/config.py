"""애플리케이션 설정 (backend-design §1.3 core).

값은 환경변수로 주입한다. 접두사 `PORTAL_` 사용.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="PORTAL_", env_file=".env", extra="ignore")

    # --- 앱 ---
    app_name: str = "Slurm HPC Portal API"
    api_prefix: str = "/api/v1"
    debug: bool = False

    # --- DB (backend-design §5.3: 소규모 단일 RDS/MySQL) ---
    database_url: str = "mysql+pymysql://portal:portal@localhost:3306/portal"

    # --- Redis (§4: 세션·권한 캐시·분산락) ---
    redis_url: str = "redis://localhost:6379/0"
    session_ttl_seconds: int = 8 * 3600  # §9 미확정 — 기본 8h
    permission_cache_ttl_seconds: int = 300

    # --- 포털 세션 JWT (Slurm JWT와 별개) ---
    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_ttl_seconds: int = 8 * 3600

    # --- 부트스트랩 (C-02: 1회용 setup 토큰) ---
    setup_token: str = ""

    # --- 외부 연동 ---
    slurm_api_version: str = "v0.0.41"  # 정의서 §4.1 각주: 버전 고정
    http_timeout_seconds: float = 10.0
    http_max_retries: int = 2  # 멱등 op 한정
    ad_timeout_seconds: float = 10.0
    # DC 인증서가 사설 CA/자체서명이면 CA 파일을 지정한다. 검증 해제는 개발 환경 한정.
    ad_tls_verify: bool = True
    ad_ca_cert_file: str | None = None

    # --- Secret 저장소 (§9 미확정 — 현재 환경변수 구현) ---
    secret_env_prefix: str = "PORTAL_SECRET_"

    # --- 배치 (§5.5) ---
    ad_sync_interval_seconds: int = 3600
    scheduler_enabled: bool = False


@lru_cache
def get_settings() -> Settings:
    return Settings()
