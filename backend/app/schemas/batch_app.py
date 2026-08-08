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


class BatchAppSubmitRequest(JobSubmitRequest):
    """자원 입력은 Job 제출과 **같은 스키마를 물려받는다**.

    파티션·노드·GPU·walltime·배열·의존성이 여기서도 그대로 필요하다. 따로 정의하면
    한쪽에만 필드가 추가되어 화면이 갈린다.

    `script`·`mode`는 **서버가 정한다** — 본문은 앱 카탈로그가 만든다.
    """

    #: 앱 파라미터. 키·형식은 `GET /batch-apps`가 알려 준다
    #: (`text`·`number`·`path`·`select`·`bool`).
    params: dict[str, Any] = Field(default_factory=dict)
