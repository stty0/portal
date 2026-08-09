"""앱 사용 허용 — 앱마다 쓸 수 있는 Slurm 계정 (U-IA-01 · U-JB-13, A-US-02).

여기서 지키는 것 셋:
  1. **배정이 없으면 지금까지처럼 전원이 쓴다.** 표를 만든 것만으로 앱이 잠기면 안 된다.
  2. 목록에서 잠그는 것으로 끝내지 않는다 — **제출에서 막는다.**
  3. 배정된 앱은 **그 계정으로 돈다.** 기본 계정으로 돌면 배정이 이름뿐이 된다.

fake slurmdbd에서 `jrpark`는 `hpc` 계정에만 속한다(tests/fakes.py).
"""

import pytest

from app.services import batch_apps as B
from tests.conftest import auth_headers

# 세션 제출은 워커의 connection.json을 읽는다 — 세션 테스트가 이미 갖고 있는 fake를 쓴다.
from tests.test_sessions import fake_ssh  # noqa: F401

API = "/api/v1"


@pytest.fixture
def apps_cluster(db, cluster):
    """앱을 실제로 띄울 수 있는 클러스터 — 이미지 저장소가 있어야 제출이 이미지에서 막히지 않는다."""
    db.commit()
    return cluster


def assign(client, cid, kind, app_id, accounts, token):
    return client.put(
        f"{API}/clusters/{cid}/app-access/{kind}/{app_id}",
        json={"accounts": accounts},
        headers=auth_headers(token),
    )


def interactive(client, cid, token):
    resp = client.get(f"{API}/clusters/{cid}/interactive-apps", headers=auth_headers(token))
    assert resp.status_code == 200, resp.text
    return {a["id"]: a for a in resp.json()}


def batch(client, cid, token):
    resp = client.get(f"{API}/clusters/{cid}/batch-apps", headers=auth_headers(token))
    assert resp.status_code == 200, resp.text
    return {a["id"]: a for a in resp.json()}


# --- 기본은 열려 있다 -------------------------------------------------------


def test_apps_are_open_to_everyone_until_they_are_assigned(
    client, apps_cluster, user_token, slurm_client
):
    """배정이 하나도 없으면 **slurmdbd를 부르지도 않는다** — 소속을 볼 이유가 없다."""
    apps = interactive(client, apps_cluster.id, user_token)
    assert all(a["allowed"] for a in apps.values())
    assert all(a["accounts"] == [] for a in apps.values())
    assert not [n for n, _ in slurm_client.calls if n == "get_associations"]


def test_assigning_one_app_does_not_lock_the_others(
    client, apps_cluster, user_token, admin_token
):
    """허용 목록은 앱마다 독립이다 — 하나를 잠갔다고 나머지가 따라 잠기면 못 쓴다."""
    assign(client, apps_cluster.id, "interactive", "desktop", ["nobody"], admin_token)

    apps = interactive(client, apps_cluster.id, user_token)
    assert apps["desktop"]["allowed"] is False
    assert apps["desktop"]["accounts"] == ["nobody"]
    assert apps["paraview"]["allowed"] is True


# --- 소속 판정 --------------------------------------------------------------


def test_member_of_the_assigned_account_keeps_the_app(
    client, apps_cluster, user_token, admin_token
):
    assign(client, apps_cluster.id, "interactive", "jupyter", ["hpc"], admin_token)
    assert interactive(client, apps_cluster.id, user_token)["jupyter"]["allowed"] is True


def test_apps_stay_locked_when_the_membership_lookup_fails(
    client, apps_cluster, user_token, admin_token, slurm_client
):
    """소속을 모르는데 열어 주면 배정이 무의미해진다 — 모를 때는 잠근다.

    다만 목록 전체가 실패하지는 않는다(화면이 통째로 비면 이유를 알 수 없다).
    """
    assign(client, apps_cluster.id, "interactive", "desktop", ["hpc"], admin_token)

    def boom(*, as_user=None):
        raise RuntimeError("slurmdbd down")

    slurm_client.get_associations = boom
    apps = interactive(client, apps_cluster.id, user_token)
    assert apps["desktop"]["allowed"] is False
    assert apps["paraview"]["allowed"] is True  # 배정이 없는 앱은 영향받지 않는다


# --- 제출에서 막는다 --------------------------------------------------------


def test_locked_interactive_app_cannot_be_launched(
    client, apps_cluster, user_token, admin_token, fake_ssh
):
    """목록에서 감추는 것만으로는 제한이 아니다 — 화면을 거치지 않는 호출이 있다."""
    assign(client, apps_cluster.id, "interactive", "desktop", ["cfd"], admin_token)

    resp = client.post(
        f"{API}/clusters/{apps_cluster.id}/sessions",
        json={"app": "desktop"},
        headers=auth_headers(user_token),
    )
    assert resp.status_code == 422
    assert "cfd" in resp.json()["message"]


def test_locked_batch_app_cannot_be_submitted(
    client, apps_cluster, user_token, admin_token, monkeypatch
):
    monkeypatch.setattr(B, "APPS", (_demo(),))
    assign(client, apps_cluster.id, "batch", "demo", ["cfd"], admin_token)

    resp = client.post(
        f"{API}/clusters/{apps_cluster.id}/batch-apps/demo/jobs",
        json={"name": "run", "params": {"input": "/home/jrpark/a"}},
        headers=auth_headers(user_token),
    )
    assert resp.status_code == 422
    assert "cfd" in resp.json()["message"]


def test_an_account_the_user_does_not_belong_to_is_refused(
    client, apps_cluster, user_token, admin_token, fake_ssh
):
    """배정된 계정이라도 **내 계정이 아니면** 안 된다 — Slurm이 거부할 값이다."""
    assign(client, apps_cluster.id, "interactive", "desktop", ["hpc", "cfd"], admin_token)

    resp = client.post(
        f"{API}/clusters/{apps_cluster.id}/sessions",
        json={"app": "desktop", "account": "cfd"},
        headers=auth_headers(user_token),
    )
    assert resp.status_code == 422


# --- 배정된 앱은 그 계정으로 돈다 -------------------------------------------


def test_assigned_app_runs_under_the_assigned_account(
    client, apps_cluster, user_token, admin_token, slurm_client, fake_ssh
):
    """계정을 안 골랐으면 서버가 채운다. 기본 계정으로 돌면 배정이 이름뿐이 된다."""
    assign(client, apps_cluster.id, "interactive", "desktop", ["hpc"], admin_token)

    resp = client.post(
        f"{API}/clusters/{apps_cluster.id}/sessions",
        json={"app": "desktop"},
        headers=auth_headers(user_token),
    )
    assert resp.status_code == 201, resp.text

    spec = [kw["spec"] for n, kw in slurm_client.calls if n == "submit_job"][0]
    assert "--account=hpc" in spec["script"]


def test_assigned_batch_app_runs_under_the_assigned_account(
    client, apps_cluster, user_token, admin_token, slurm_client, monkeypatch
):
    monkeypatch.setattr(B, "APPS", (_demo(),))
    assign(client, apps_cluster.id, "batch", "demo", ["hpc"], admin_token)

    resp = client.post(
        f"{API}/clusters/{apps_cluster.id}/batch-apps/demo/jobs",
        json={"name": "run", "params": {"input": "/home/jrpark/a"}},
        headers=auth_headers(user_token),
    )
    assert resp.status_code == 200, resp.text

    spec = [kw["spec"] for n, kw in slurm_client.calls if n == "submit_job"][0]
    assert spec["job"]["account"] == "hpc"


# --- 관리 (A-US-02) ---------------------------------------------------------


def test_assignment_is_an_overwrite_and_empty_reopens_the_app(
    client, apps_cluster, user_token, admin_token
):
    """QOS 배정과 같은 규칙 — 화면이 전체를 보낸다. 비우면 다시 전원이 쓴다."""
    assign(client, apps_cluster.id, "interactive", "desktop", ["hpc", "cfd"], admin_token)
    assign(client, apps_cluster.id, "interactive", "desktop", ["cfd"], admin_token)

    rows = client.get(
        f"{API}/clusters/{apps_cluster.id}/app-access", headers=auth_headers(admin_token)
    ).json()
    desktop = next(r for r in rows if r["kind"] == "interactive" and r["app_id"] == "desktop")
    assert desktop["accounts"] == ["cfd"]
    # 배정하지 않은 앱도 행으로 온다 — 관리 화면이 무엇을 배정할 수 있는지 알아야 한다.
    assert any(r["kind"] == "batch" for r in rows)

    assign(client, apps_cluster.id, "interactive", "desktop", [], admin_token)
    assert interactive(client, apps_cluster.id, user_token)["desktop"]["allowed"] is True


def test_users_cannot_assign_accounts_to_apps(client, apps_cluster, user_token):
    assert assign(client, apps_cluster.id, "interactive", "desktop", ["hpc"], user_token).status_code == 403


def test_unknown_app_is_refused(client, apps_cluster, admin_token):
    """카탈로그에 없는 앱에 배정하면 아무 효력이 없는 행이 남는다 — 만들 때 막는다."""
    assert assign(client, apps_cluster.id, "interactive", "nope", ["hpc"], admin_token).status_code == 422
    assert assign(client, apps_cluster.id, "nope", "desktop", ["hpc"], admin_token).status_code == 422


def _demo() -> B.BatchApp:
    return B.BatchApp(
        id="demo",
        name="데모",
        description="",
        image="demo.sif",
        fid="U-JB-13",
        steps=(B.AppStep(run="solve {{input}}"),),
        params=(B.AppParam(key="input", label="입력", type="path"),),
    )
