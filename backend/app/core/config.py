"""애플리케이션 설정 (backend-design §1.3 core).

값은 환경변수로 주입한다. 접두사 `PORTAL_` 사용.
"""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="PORTAL_", env_file=".env", extra="ignore")

    # --- 앱 ---
    app_name: str = "Slurm HPC Portal API"
    api_prefix: str = "/api/v1"
    debug: bool = False

    # --- DB (backend-design §5.3: 소규모 단일 RDS/MySQL) ---
    # URL 안에 비밀번호가 들어 있다 — `repr`에서 뺀다(SshTarget과 같은 이유).
    database_url: str = Field(
        default="mysql+pymysql://portal:portal@localhost:3306/portal", repr=False
    )

    # --- Redis (§4: 세션·권한 캐시·분산락) ---
    redis_url: str = Field(default="redis://localhost:6379/0", repr=False)
    permission_cache_ttl_seconds: int = 300

    # --- 포털 세션 JWT (Slurm JWT와 별개) ---
    jwt_secret: str = Field(default="change-me-in-production", repr=False)
    jwt_algorithm: str = "HS256"
    #: 액세스 토큰 수명. **짧게 잡는다** — 유출돼도 창이 좁다. 갱신은 refresh가 맡는다.
    access_token_ttl_seconds: int = 30 * 60
    #: refresh 토큰 수명. 세션 레코드가 죽으면 어차피 갱신이 안 되므로(refresh가 세션을
    #: 다시 확인한다) 이 값이 실질 상한은 아니다 — 넉넉히 둔다.
    refresh_token_ttl_seconds: int = 14 * 24 * 3600

    #: **절대 상한.** 유휴 연장으로 젊어지지 않는다. 이 시간이 지나면 아무리 활발히
    #: 써도 재로그인을 요구한다 — 비밀번호를 다시 확인하는 지점이 필요하다.
    session_absolute_ttl_seconds: int = 14 * 24 * 3600

    #: **유휴 타임아웃의 기본값(분).** 실제 값은 관리자가 화면에서 정한다
    #: (`portal_setting.session_timeout_min`, A-OP-04). 설정 행이 아직 없을 때만 쓰인다.
    session_idle_default_minutes: int = 480

    #: 세션 레코드를 처음 만들 때의 TTL. 이후 요청마다 유휴 값으로 되감긴다.
    @property
    def session_ttl_seconds(self) -> int:
        return self.session_idle_default_minutes * 60

    # --- 쿠키 전송(브라우저) ---
    #: HTTPS 배포에서는 반드시 True. 로컬 http 개발에서만 끈다.
    cookie_secure: bool = True
    cookie_domain: str | None = None

    # --- 부트스트랩 (C-02: 1회용 setup 토큰) ---
    setup_token: str = Field(default="", repr=False)

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
    # 앱 아이콘 파일이 있는 디렉터리 (A-OP-02). 파드에 읽기 전용으로 마운트한다.
    # DB에는 파일명만 남고 실제 경로는 여기서 정해진다 — 배포 위치가 바뀌어도 DB는 그대로다.
    app_icon_dir: str = "/home/.portal/app-icons"
    # 앱 컨테이너 이미지(SIF) 디렉터리의 **폴백**. 평소에는 클러스터의 `home_base`에서
    # 파생하고(`services/app_images.py`), 그 값이 비었을 때만 여기로 떨어진다.
    # **워커 노드 기준 경로**다 — apptainer가 거기서 실행한다.
    app_image_dir: str = "/home/.portal/images"

    # --- Secret 저장소 (§9 미확정 — 현재 환경변수 구현) ---
    secret_env_prefix: str = "PORTAL_SECRET_"

    # --- 배치 (§5.5) ---
    ad_sync_interval_seconds: int = 3600
    scheduler_enabled: bool = False


@lru_cache
def get_settings() -> Settings:
    return Settings()
