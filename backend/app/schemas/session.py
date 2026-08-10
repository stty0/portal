"""인터랙티브 세션 스키마 (U-IA-01·02·04).

**호스트·포트는 응답 모델에 필드 자체가 없다.** 백엔드가 터널 목적지를 알고 있으면
되고, 브라우저에 알려주면 열린 프록시로 가는 문이 열린다(docs/plan.md §3.4).
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class SessionCreate(BaseModel):
    """U-IA-01 앱 런처 폼."""

    app: str = Field(default="desktop", pattern="^[a-z0-9][a-z0-9_-]{0,31}$")
    partition: str | None = None
    account: str | None = None
    qos: str | None = None
    cpus: int | None = Field(default=None, ge=1, le=256)
    memory_gb: int | None = Field(default=None, ge=1, le=4096)
    walltime: str | None = None
    geometry: str = Field(default="1920x1080", pattern=r"^\d{3,5}x\d{3,5}$")
    #: 노드 독점(`--exclusive`). **자원 스케줄링 옵션이지 접근 제어가 아니다** —
    #: 다른 사용자의 Job이 같은 노드에 배정되지 않을 뿐이다. 같은 노드 사용자로부터의
    #: 방어는 Xvnc의 X 인증 쿠키가 담당한다(docs/plan.md §3.4).
    #: 켜면 위의 `cpus`·`memory_gb`는 무시하고 노드 전체를 쓴다.
    exclusive: bool = False


class SessionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    cluster_id: int
    app: str
    job_id: str | None
    #: Slurm에서 읽은 실제 상태. 대장(DB)이 아니라 이쪽이 권위 있는 출처다.
    state: str
    is_running: bool
    created_at: datetime | None = None
    terminated_at: datetime | None = None


class SessionConnectInfo(BaseModel):
    """RFB 핸드셰이크에 필요한 값만. 접속 위치는 담지 않는다.

    비밀번호는 세션마다 무작위로 발급되고 소유자에게만 내려간다. 브라우저가 RFB 인증을
    직접 수행하기 때문에 필요하다 — 백엔드가 대신 핸드셰이크를 처리하면 감출 수 있으나
    DES 챌린지 구현이 붙는다(향후 강화 여지).
    """

    password: str | None
    geometry: str | None


class InteractiveAppOut(BaseModel):
    """U-IA-01 앱 런처의 선택지. 목록은 코드 카탈로그가 단일 출처다.

    어떤 이미지를 쓰는지는 담지 않는다 — 운영 정보이고 사용자가 고를 값도 아니다.
    """

    id: str
    name: str
    description: str
    fid: str
    ready: bool
    #: 이 **클러스터에** 이미지 파일이 있는가. `ready`는 실행 방식이 확정됐는지(코드),
    #: `installed`는 파일이 거기 있는지(클러스터)다.
    installed: bool = True
    #: 접속 방식. 화면이 **어디로 보낼지**를 이 값으로 정한다 — `vnc`는 원격 데스크톱
    #: 화면, `http`는 프록시 주소다. 화면이 앱 id로 분기하면 앱을 늘릴 때마다 화면을 고쳐야 한다.
    transport: str = "vnc"
    #: 실행할 수 없는 앱에 붙는 안내. 비어 있으면 화면이 표시하지 않는다.
    note: str = ""
    #: 이 사용자가 쓸 수 있는가. `ready`와 다른 잠금이다 — 앱은 준비됐지만
    #: **계정 배정에서 빠진** 경우다(services/app_access.py).
    allowed: bool = True
    #: 이 앱에 배정된 계정. 비어 있으면 전원 허용이라 화면이 아무 말도 하지 않는다.
    accounts: list[str] = Field(default_factory=list)
