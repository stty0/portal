"""앱 사용 허용 — 앱마다 쓸 수 있는 Slurm 계정을 정한다 (U-IA-01 · U-JB-13).

배정은 관리자가 계정 관리 화면(SCR-13, A-US-02)에서 하고, 소속 판정은 **slurmdbd의
association**이 정본이다. 포털은 소속을 저장하지 않는다 — 저장하면 `sacctmgr`로 바뀐
소속과 어긋난다.

## 기본은 열려 있다

**어떤 앱에 배정이 하나도 없으면 그 앱은 전원이 쓴다.** 기본을 잠김으로 두면 표를 만든
순간 모든 앱이 멈추고, 앱을 새로 넣을 때마다 배정이 따라와야 한다. 배정된 앱만 잠긴다.

## 포털 밖은 막지 못한다

여기서 거르는 것은 **화면에서 고를 수 있는 것**이다. 사용자는 웹 터미널이나 SSH로
`sbatch`를 직접 칠 수 있고 그건 포털의 범위가 아니다. 진짜 강제가 필요하면 Slurm 쪽
(파티션 `AllowAccounts`, 정의서 A-US-05)이 맡아야 한다.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.orm import Session

from app.core.errors import ValidationFailed
from app.models import Cluster, User
from app.repositories.access import AppAccessRepository
from app.services import batch_apps, session_apps
from app.services.audit import AuditService
from app.services.cluster import ClusterService

KIND_INTERACTIVE = "interactive"
KIND_BATCH = "batch"
KINDS = (KIND_INTERACTIVE, KIND_BATCH)


def user_accounts(client: Any, username: str) -> list[str]:
    """**이 사용자에게 연결된 계정만** 돌려준다.

    전체 계정 목록으로 대체하면 안 된다 — 소속되지 않은 계정을 골라 제출하면 Slurm이
    거부한다. 고를 수 없는 값을 보여주는 화면이 더 나쁘다.

    출처는 `/associations`다. `/user/{name}`은 응답에 associations를 채워주지 않아
    (항상 빈 배열 — 실측) 소속을 알 수 없다.
    """
    payload = client.get_associations(as_user=username)
    associations = payload.get("associations") if isinstance(payload, dict) else None
    found: list[str] = []
    for assoc in associations or []:
        if not isinstance(assoc, dict) or assoc.get("user") != username:
            continue
        account = assoc.get("account")
        if account and str(account) not in found:
            found.append(str(account))
    return found


@dataclass(frozen=True)
class Allowance:
    """한 앱에 대한 판정."""

    #: 이 사용자가 지금 쓸 수 있는가.
    allowed: bool
    #: 배정된 계정. **비어 있으면 전원 허용**이라 화면이 아무 말도 하지 않는다.
    accounts: list[str] = field(default_factory=list)


def _catalog(kind: str) -> dict[str, str]:
    """`app_id → 표시 이름`. 배정 대상이 실제 앱인지 여기로 판정한다."""
    if kind == KIND_INTERACTIVE:
        return {a.id: a.name for a in session_apps.APPS}
    if kind == KIND_BATCH:
        return {a.id: a.name for a in batch_apps.APPS}
    raise ValidationFailed("알 수 없는 앱 종류입니다.", detail={"kind": kind, "supported": list(KINDS)})


class AppAccessService:
    def __init__(self, session: Session, clusters: ClusterService):
        self.session = session
        self.clusters = clusters
        self.access = AppAccessRepository(session)
        self.audit = AuditService(session)

    # --- 사용자 쪽 -------------------------------------------------------
    def allowances(self, cluster: Cluster, kind: str, *, user: User) -> dict[str, Allowance]:
        """앱 목록 화면용 판정. 배정이 하나도 없으면 **slurmdbd를 부르지 않는다.**"""
        assigned = {
            app_id: accounts
            for (k, app_id), accounts in self.access.by_app(cluster.id).items()
            if k == kind
        }
        catalog = _catalog(kind)
        if not assigned:
            return {app_id: Allowance(True) for app_id in catalog}

        mine = self._my_accounts(cluster, user, quiet=True)
        return {
            app_id: self._judge(assigned.get(app_id) or [], mine)
            for app_id in catalog
        }

    def resolve_account(
        self, cluster: Cluster, kind: str, app_id: str, *, user: User, account: str | None
    ) -> str | None:
        """제출을 막거나, 통과시키며 **쓸 계정을 정한다.**

        목록에서 잠그는 것만으로는 제한이 되지 않는다 — 화면을 거치지 않는 호출이
        있고, 무엇보다 **Job이 어느 계정에 붙어 도는지가 배정의 목적**이다. 배정된
        앱인데 계정을 안 골랐으면 여기서 채운다.
        """
        assigned = self.access.accounts_for(cluster.id, kind, app_id)
        if not assigned:
            return account

        name = _catalog(kind).get(app_id, app_id)
        usable = [a for a in assigned if a in self._my_accounts(cluster, user)]
        if not usable:
            raise ValidationFailed(
                f"'{name}'은(는) {', '.join(assigned)} 계정에 소속된 사용자만 사용할 수 있습니다.",
                detail={"app": app_id, "accounts": assigned},
            )
        if account and account not in usable:
            raise ValidationFailed(
                f"'{name}'은(는) '{account}' 계정으로 실행할 수 없습니다.",
                detail={"app": app_id, "accounts": usable},
            )
        # 안 골랐으면 서버가 채운다. 기본 계정으로 돌면 배정이 이름뿐이 된다.
        return account or usable[0]

    # --- 관리자 쪽 (A-US-02) --------------------------------------------
    def assignments(self, cluster_id: int) -> list[dict[str, Any]]:
        """카탈로그 전체 + 각 앱의 배정. **배정이 없는 앱도 행으로 내려보낸다** —
        관리 화면이 "무엇을 배정할 수 있나"를 알아야 한다."""
        assigned = self.access.by_app(cluster_id)
        return [
            {
                "kind": kind,
                "app_id": app_id,
                "name": name,
                "accounts": assigned.get((kind, app_id), []),
            }
            for kind in KINDS
            for app_id, name in _catalog(kind).items()
        ]

    def assign(
        self, cluster_id: int, kind: str, app_id: str, *, accounts: list[str], actor: User
    ) -> dict[str, Any]:
        cluster = self.clusters.get(cluster_id)
        catalog = _catalog(kind)
        if app_id not in catalog:
            raise ValidationFailed(
                "알 수 없는 앱입니다.", detail={"kind": kind, "app": app_id}
            )
        cleaned = [a.strip() for a in accounts if a and a.strip()]
        self.access.replace(cluster.id, kind, app_id, cleaned)
        self.audit.record(
            actor=actor,
            action="APP_ACCESS_SET",
            target=f"{kind}/{app_id}",
            cluster_id=cluster.id,
            detail=", ".join(cleaned) or "(전원 허용)",
        )
        self.session.commit()
        return {
            "kind": kind, "app_id": app_id, "name": catalog[app_id], "accounts": cleaned
        }

    # --- 내부 -----------------------------------------------------------
    def _my_accounts(self, cluster: Cluster, user: User, *, quiet: bool = False) -> list[str]:
        client = self.clusters.slurm_client(cluster)
        try:
            return user_accounts(client, user.username)
        except Exception:  # noqa: BLE001
            if not quiet:
                raise
            # 목록 화면에서는 조회 실패로 화면 전체를 막지 않는다. 대신 **잠근 채로**
            # 둔다 — 소속을 모르는데 열어 주면 배정이 무의미해진다.
            return []

    @staticmethod
    def _judge(assigned: list[str], mine: list[str]) -> Allowance:
        if not assigned:
            return Allowance(True)
        return Allowance(any(a in mine for a in assigned), assigned)
