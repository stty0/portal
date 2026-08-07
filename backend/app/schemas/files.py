"""파일 조작 요청 스키마 (U-FM-02·04).

**사용자는 받지 않는다** — 대상 사용자는 세션에서 정한다(U-FM-01과 같은 원칙).
경로 검증은 스키마가 아니라 SSH 클라이언트의 경로 관문이 한다. 문자열만 보고
판단할 수 없고(심볼릭 링크·`..`), 정규화는 서버에 물어봐야 하기 때문이다.
"""

from pydantic import BaseModel, Field


class PathIn(BaseModel):
    """만들거나 지울 대상 하나."""

    path: str = Field(min_length=1, max_length=4096)


class MoveIn(BaseModel):
    """이름 변경과 이동은 같은 연산이다 — 목적지 경로만 다르다."""

    path: str = Field(min_length=1, max_length=4096)
    to: str = Field(min_length=1, max_length=4096)


class PathOut(BaseModel):
    """조작 결과. 서버가 정규화한 경로를 돌려줘 화면이 그 자리로 이동할 수 있게 한다."""

    path: str
