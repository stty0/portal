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
    permission_cache_ttl_seconds: int = 300

    # --- 포털 세션 JWT (Slurm JWT와 별개) ---
    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    #: 액세스 토큰 수명. **짧게 잡는다** — 유출돼도 창이 좁다. 갱신은 refresh가 맡는다.
    access_token_ttl_seconds: int = 30 * 60
    #: refresh 토큰 수명 = 재로그인 없이 유지되는 기간. 세션 레코드도 이 값을 따른다.
    refresh_token_ttl_seconds: int = 14 * 24 * 3600

    #: 세션 레코드 TTL. refresh가 살아 있는 동안 세션도 살아야 하므로 같은 값을 쓴다.
    @property
    def session_ttl_seconds(self) -> int:
        return self.refresh_token_ttl_seconds

    # --- 쿠키 전송(브라우저) ---
    #: HTTPS 배포에서는 반드시 True. 로컬 http 개발에서만 끈다.
    cookie_secure: bool = True
    cookie_domain: str | None = None

    # --- 부트스트랩 (C-02: 1회용 setup 토큰) ---
    setup_token: str = ""

    # --- 외부 연동 ---
    slurm_api_version: str = "v0.0.43"  # 정의서 §4.1 각주: 버전 고정
    http_timeout_seconds: float = 10.0
    http_max_retries: int = 2  # 멱등 op 한정
    ad_timeout_seconds: float = 10.0
    # DC 인증서가 사설 CA/자체서명이면 CA 파일을 지정한다. 검증 해제는 개발 환경 한정.
    ad_tls_verify: bool = True
    ad_ca_cert_file: str | None = None
    # 로그인 노드 SSH (U-FM-01·A-DB-05). 호스트키 파일이 없으면 접속을 거부한다 —
    # 자동 수락은 중간자 공격을 그대로 통과시킨다.
    ssh_known_hosts: str | None = None
    ssh_timeout_seconds: float = 10.0
    # 업로드 상한 (U-FM-02). 스트리밍이라 메모리는 안 늘지만, 실수로 홈을 채우는 것과
    # 무한 전송을 막는다. 대용량은 여전히 scp/rsync가 맞다.
    file_upload_max_mb: int = 2048

    # --- Secret 저장소 (§9 미확정 — 현재 환경변수 구현) ---
    secret_env_prefix: str = "PORTAL_SECRET_"

    # --- 배치 (§5.5) ---
    ad_sync_interval_seconds: int = 3600
    scheduler_enabled: bool = False


@lru_cache
def get_settings() -> Settings:
    return Settings()
