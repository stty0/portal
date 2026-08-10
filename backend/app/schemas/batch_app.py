"""Batch 앱 스키마 (U-JB-13)."""

from typing import Any

from pydantic import BaseModel, Field

from app.schemas.job import JobSubmitRequest


class AppParamOut(BaseModel):
    key: str
    label: str
    type: str
    required: bool
    default: str | None
    hint: str
    options: list[str]


class BatchAppOut(BaseModel):
    id: str
    name: str
    description: str
    fid: str
    needs_gpu: bool
    ready: bool
    params: list[AppParamOut]
    #: 이 **클러스터에** 이미지 파일이 있는가. `ready`와 다르다 — `ready`는 실행 방식이
    #: 확정됐는지(코드), `installed`는 파일이 거기 있는지(클러스터)다. SIF를 디렉터리에
    #: 넣으면 코드 배포 없이 이 값이 참이 된다.
    installed: bool = True
    #: 이 사용자가 쓸 수 있는가. 세 번째 잠금이다 — 이미지도 있고 실행 방식도 있지만
    #: **계정 배정에서 빠진** 경우다(services/app_access.py).
    allowed: bool = True
    #: 이 앱에 배정된 계정. 비어 있으면 전원 허용이다.
    accounts: list[str] = Field(default_factory=list)


class BatchAppSubmitRequest(JobSubmitRequest):
    """자원 입력은 Job 제출과 **같은 스키마를 물려받는다**.

    파티션·노드·GPU·walltime·배열·의존성이 여기서도 그대로 필요하다. 따로 정의하면
    한쪽에만 필드가 추가되어 화면이 갈린다.

    `script`·`mode`는 **서버가 정한다** — 본문은 앱 카탈로그가 만든다.
    """

    #: 앱 파라미터. 키·형식은 `GET /clusters/{cid}/batch-apps`가 알려 준다
    #: (`text`·`number`·`path`·`select`·`bool`).
    params: dict[str, Any] = Field(default_factory=dict)
