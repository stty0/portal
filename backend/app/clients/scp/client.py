"""SCP Billing(costexplorer) client — scpv2-sdk 래퍼 (A-BL-01·03).

**SDK 엔드포인트 규칙 예외**: `scpv2` 는 모든 서비스를
`https://{api}.{region}.{env}.samsungsdscloud.com` 으로 조립하는데,
costexplorer 는 **리전 없는 전역 호스트**라 그대로 쓰면 DNS 해석에 실패한다(실측).
여기서 그 한 서비스만 교정한다.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.core.errors import ExternalServiceError

COST_API = "costexplorer"
TAG_API = "resourcemanager"
# 리전 서브도메인이 없는 전역 서비스들 (실측: kr-west1을 끼우면 DNS 해석 실패)
GLOBAL_APIS = {COST_API, TAG_API}


@dataclass(frozen=True)
class ScpCredentials:
    access_key: str
    secret_key: str
    region: str = "kr-west1"
    environment: str = "e"


class ScpBillingClient:
    def __init__(self, creds: ScpCredentials):
        self._creds = creds

    def _session(self):
        try:
            import scpv2
            from scpv2.session import Session
        except ImportError as exc:  # pragma: no cover - 배포 이미지에는 항상 있다
            raise ExternalServiceError("scpv2-sdk가 설치되어 있지 않습니다.") from exc

        original = Session.endpoint_for

        def endpoint_for(self, api_name: str) -> str:
            if api_name in GLOBAL_APIS:
                return f"https://{api_name}.{self.environment}.samsungsdscloud.com"
            return original(self, api_name)

        Session.endpoint_for = endpoint_for  # type: ignore[method-assign]
        return scpv2.Session(
            access_key=self._creds.access_key,
            secret_key=self._creds.secret_key,
            region=self._creds.region,
            environment=self._creds.environment,
        )

    def usages(self, *, start_date: str, end_date: str, max_pages: int = 20) -> list[dict[str, Any]]:
        """기간 내 사용 내역 전체. marker 기반 페이징을 끝까지 따라간다."""
        client = self._session().client("usage")
        rows: list[dict[str, Any]] = []
        marker: str | None = None
        for _ in range(max_pages):
            params: dict[str, Any] = {
                "start_date": start_date,
                "end_date": end_date,
                "limit": 500,
            }
            if marker:
                params["marker"] = marker
            try:
                page = client.list_usages(**params)
            except Exception as exc:
                raise ExternalServiceError(f"SCP 비용 조회 실패: {exc}") from exc
            items = page.get("usages") or []
            rows.extend(items)
            nxt = [link["href"] for link in page.get("links", []) if link.get("rel") == "next"]
            if not items or not nxt:
                break
            marker = nxt[0].split("marker=")[-1]
        return rows


    def tagged_resource_ids(self, *, key: str, value: str | None = None) -> set[str]:
        """태그가 붙은 자원의 ID 집합 (A-BL-02).

        비용 응답(`usages`)에는 태그가 실리지 않아 여기서 따로 조회해 매칭한다.
        태그 API는 자원을 SRN으로 돌려주므로 마지막 조각만 떼어 `resource_id`와 맞춘다.
        SRN 쪽은 하이픈이 있고(`54fca0ce-ed30-…`) 비용 쪽은 없어서(`4d4c747e42be…`)
        **하이픈을 제거해 정규화**해야 매칭된다(실측).
        """
        client = self._session().client("tag")
        params: dict[str, Any] = {"key": key, "size": 500}
        if value:
            params["value"] = value
        try:
            page = client.list_tags(**params)
        except Exception as exc:
            raise ExternalServiceError(f"SCP 태그 조회 실패: {exc}") from exc
        return {normalize_resource_id(t.get("srn", "").rsplit("/", 1)[-1]) for t in page.get("content") or []}


def normalize_resource_id(value: Any) -> str:
    return str(value or "").replace("-", "").lower()
