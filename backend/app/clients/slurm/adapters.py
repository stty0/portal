"""slurmrestd 응답 값 어댑터.

slurmrestd는 숫자를 **두 가지 형태로** 보낸다 — 맨 숫자(`8`)와
`{set, infinite, number}` 래퍼다. 어느 쪽으로 오는지는 필드·엔드포인트·판본마다 다르다.

**해석을 한 곳에 모아 둔다.** 서비스마다 따로 풀면 같은 필드에 대한 답이 갈린다.
실제로 그런 적이 있다: `account.py`는 맨 숫자를 `None`(=한도 없음)으로 접고 `cluster.py`는
그대로 받아서, QOS 한도가 판본에 따라 **"무제한"으로 뒤집혀 보일 수 있었다**.
프론트의 `utils/slurm.ts:num()`도 여기와 같은 규칙이다.
"""

from typing import Any


def number(value: Any) -> int | float | None:
    """`{set, infinite, number}` 래퍼 또는 맨 숫자 → 숫자.

    `set=false`거나 `infinite=true`면 **한도 없음**이므로 `None`이다 — 0으로 접으면
    "0 제한"으로 오해된다. 형태를 알 수 없으면 `None`.

    `bool`은 숫자가 아니다. 파이썬에서 `isinstance(True, int)`가 참이라 걸러내지 않으면
    `True`가 1로 새어 들어온다.
    """
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, dict):
        if value.get("infinite") or value.get("set") is False:
            return None
        inner = value.get("number")
        return inner if isinstance(inner, (int, float)) and not isinstance(inner, bool) else None
    return None


def int_or(value: Any, default: int = 0) -> int:
    """합계처럼 **없으면 0으로 접어도 되는 자리**에서 쓴다.

    한도(`None`=무제한)와 달리 "노드의 CPU 수"는 모르면 세지 않는 편이 맞다.
    """
    resolved = number(value)
    return default if resolved is None else int(resolved)
