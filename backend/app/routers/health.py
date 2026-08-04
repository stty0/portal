"""헬스체크 — 인증 없이 접근 가능(K8s probe 대상)."""

from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/healthz", summary="liveness")
def healthz() -> dict:
    return {"status": "ok"}
