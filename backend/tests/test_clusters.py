"""클러스터 등록·자격증명 테스트 (A-CL-01~04, C-03).

Secret 취급이 핵심이다 — 값은 Secret 저장소에만 있고 DB·응답에는 참조만 남는다.
"""

import pytest

from tests.conftest import auth_headers


def _create(client, token, **overrides):
    body = {
        "alias": "판교 GPU",
        "slurmrestd_url": "http://pangyo:6820",
        "api_version": "v0.0.43",
        "login_node": "login.pangyo",
        "ssh_account": "svc-portal",
        **overrides,
    }
    return client.post("/api/v1/clusters", json=body, headers=auth_headers(token))


def test_user_can_list_but_not_create(client, cluster, user_token):
    assert client.get("/api/v1/clusters", headers=auth_headers(user_token)).status_code == 200
    assert _create(client, user_token).status_code == 403


def test_admin_creates_cluster_without_a_name(client, admin_token):
    """이름은 받지 않는다 — slurm.conf ClusterName이 정본이고 REST 테스트가 채운다."""
    resp = _create(client, admin_token)
    assert resp.status_code == 201
    body = resp.json()
    assert body["alias"] == "판교 GPU"
    assert body["name"] is None


def test_alias_is_required(client, admin_token):
    """이름이 없는 동안 클러스터를 가리킬 값이 하나는 있어야 한다."""
    resp = client.post("/api/v1/clusters", json={}, headers=auth_headers(admin_token))
    assert resp.status_code == 422


def test_credential_value_never_returned_or_stored_in_db(client, db, cluster, admin_token, secret_store):
    from app.models import ClusterCredential

    jwt_value = "super.secret.jwt"
    resp = client.put(
        f"/api/v1/clusters/{cluster.id}/credentials",
        json={"kind": "SLURM_JWT", "value": jwt_value},
        headers=auth_headers(admin_token),
    )
    assert resp.status_code == 200
    assert jwt_value not in resp.text  # 응답에 원문 없음

    rows = db.query(ClusterCredential).filter_by(cluster_id=cluster.id).all()
    latest = rows[-1]
    assert latest.secret_ref and jwt_value not in latest.secret_ref
    # DB 어느 컬럼에도 원문이 없다
    assert all(jwt_value not in str(getattr(latest, c.name)) for c in latest.__table__.columns)
    # 실값은 Secret 저장소에만
    assert secret_store.get(latest.secret_ref) == jwt_value


def test_credential_audit_does_not_record_value(client, db, cluster, admin_token):
    from app.models import AuditLog

    client.put(
        f"/api/v1/clusters/{cluster.id}/credentials",
        json={"kind": "SLURM_JWT", "value": "leaky.jwt.value"},
        headers=auth_headers(admin_token),
    )
    entry = db.query(AuditLog).filter_by(action="CLUSTER_CREDENTIAL_PUT").one()
    assert "leaky" not in (entry.detail or "")
    assert entry.detail == "kind=SLURM_JWT"


def test_cluster_detail_has_no_secret_fields(client, cluster, admin_token):
    resp = client.get(f"/api/v1/clusters/{cluster.id}", headers=auth_headers(admin_token))
    body = resp.json()
    for forbidden in ("jwt", "secret", "private_key", "password"):
        assert not any(forbidden in key.lower() for key in body)


def test_api_version_choices_come_from_the_server(client, admin_token, user_token):
    """등록 폼의 선택지는 서버가 준다 — 화면이 목록을 따로 갖지 않는다."""
    resp = client.get("/api/v1/cluster-api-versions", headers=auth_headers(admin_token))
    assert resp.status_code == 200
    assert resp.json() == ["v0.0.43"]
    # 클러스터 설정이므로 관리자만 본다.
    assert client.get(
        "/api/v1/cluster-api-versions", headers=auth_headers(user_token)
    ).status_code == 403


def test_unsupported_api_version_is_rejected(client, cluster, admin_token):
    """드롭다운으로 좁혀도 API가 열려 있으면 반쪽이다.

    응답 파싱이 버전에 묶여 있어(`time_limit`은 분 단위 정수) 다른 버전을
    저장하면 호출이 조용히 404를 맞거나 잘못 파싱된다.
    """
    assert _create(client, admin_token, api_version="v0.0.40").status_code == 422
    resp = client.patch(
        f"/api/v1/clusters/{cluster.id}",
        json={"api_version": "v0.0.40"},
        headers=auth_headers(admin_token),
    )
    assert resp.status_code == 422


def test_munge_auth_is_rejected(client, cluster, admin_token):
    """고를 수 있는데 안 되는 값은 API도 받지 않는다.

    munge는 포털 파드가 클러스터의 `munge.key`를 갖게 되어 범위 밖이다. 화면에서만
    빼면 PATCH로 여전히 넣을 수 있고, 그러면 저장은 되는데 호출은 JWT로 나가는
    앞뒤 안 맞는 상태가 된다 — 클라이언트는 `auth_method`를 읽지 않는다.
    """
    assert _create(client, admin_token, auth_method="munge").status_code == 422
    resp = client.patch(
        f"/api/v1/clusters/{cluster.id}",
        json={"auth_method": "munge"},
        headers=auth_headers(admin_token),
    )
    assert resp.status_code == 422


def test_rest_test_syncs_cluster_name(client, db, cluster, admin_token, slurm_client):
    """이름은 손 입력이 아니라 slurmrestd에서 조회한 값이 정본이다(A-CL-02)."""
    cluster.name = "wrong-name"
    db.commit()

    resp = client.post(
        f"/api/v1/clusters/{cluster.id}/test-rest", headers=auth_headers(admin_token)
    )
    assert resp.status_code == 200
    assert resp.json()["cluster_name"] == "seoul-hpc"
    assert any(call[0] == "ping" for call in slurm_client.calls)


def test_rest_test_names_a_cluster_registered_without_one(
    client, db, cluster, admin_token, slurm_client
):
    """등록 직후 이름이 없다가 REST 연결로 정해진다."""
    cluster.name = None
    db.commit()
    resp = client.post(
        f"/api/v1/clusters/{cluster.id}/test-rest", headers=auth_headers(admin_token)
    )
    assert resp.status_code == 200
    assert resp.json()["cluster_name"] == "seoul-hpc"


def test_rest_test_rejects_a_cluster_that_is_already_registered(
    client, db, cluster, admin_token, slurm_client
):
    """중복 판정은 **여기서** 일어난다.

    이름을 등록 폼에서 받지 않게 되면서 중복 검사가 이 시점으로 옮겨왔다. 사람이 지은
    별칭이 아니라 실제 ClusterName이 겹치는지가 문제이고, 그건 연결해 보기 전에는
    알 수 없다. 놓치면 UNIQUE 제약에 걸려 500이 난다.
    """
    duplicate = _create(client, admin_token, alias="같은 클러스터를 또 등록").json()
    client.put(
        f"/api/v1/clusters/{duplicate['id']}/credentials",
        json={"kind": "SLURM_JWT", "value": "dup.jwt"},
        headers=auth_headers(admin_token),
    )
    resp = client.post(
        f"/api/v1/clusters/{duplicate['id']}/test-rest", headers=auth_headers(admin_token)
    )
    assert resp.status_code == 409
    assert "seoul-hpc" in resp.json()["message"]
    # 헬스 결과는 남는다 — 연결 자체는 성공했다.
    db.expire_all()
    from app.models import Cluster

    assert db.get(Cluster, duplicate["id"]).last_health_ok is True


# --- 노드 상태 제어 (A-ND-01) -----------------------------------------------
# 계정 쓰기와 같은 원칙이다: **사용자로 위장하지 않는다.** 노드 제어는 운영자 권한이라
# 위장하면 거부되고, "누가 시켰는가"는 포털 RBAC와 감사 로그가 남긴다.


def test_drain_sends_state_and_reason_without_impersonation(
    client, db, cluster, admin_token, slurm_client
):
    resp = client.post(
        f"/api/v1/clusters/{cluster.id}/nodes/cn01/state",
        json={"state": "drain", "reason": "디스크 교체"},
        headers=auth_headers(admin_token),
    )
    assert resp.status_code == 200
    call = [kw for name, kw in slurm_client.calls if name == "update_node"][0]
    assert call["node"] == "cn01"
    assert call["patch"] == {"state": ["DRAIN"], "reason": "디스크 교체"}
    # 감사 로그에 사유까지 남는다 — 나중에 "왜 빠져 있지?"를 답할 단서다.
    from app.models import AuditLog

    entry = db.query(AuditLog).filter_by(action="NODE_STATE").one()
    assert entry.target == "cn01" and "디스크 교체" in entry.detail


def test_drain_without_a_reason_is_rejected(client, cluster, admin_token, slurm_client):
    """사유 없이 빼면 나중에 왜 빠졌는지 아무도 모른다."""
    resp = client.post(
        f"/api/v1/clusters/{cluster.id}/nodes/cn01/state",
        json={"state": "drain"},
        headers=auth_headers(admin_token),
    )
    assert resp.status_code == 422
    assert not [kw for name, kw in slurm_client.calls if name == "update_node"]


def test_resume_does_not_require_a_reason(client, cluster, admin_token, slurm_client):
    resp = client.post(
        f"/api/v1/clusters/{cluster.id}/nodes/cn01/state",
        json={"state": "resume"},
        headers=auth_headers(admin_token),
    )
    assert resp.status_code == 200
    assert [kw for name, kw in slurm_client.calls if name == "update_node"][0]["patch"] == {
        "state": ["RESUME"]
    }


def test_unsupported_node_state_is_rejected(client, cluster, admin_token, slurm_client):
    """Slurm은 더 많은 값을 받지만 화면이 여는 것만 허용한다."""
    resp = client.post(
        f"/api/v1/clusters/{cluster.id}/nodes/cn01/state",
        json={"state": "future"},
        headers=auth_headers(admin_token),
    )
    assert resp.status_code == 422


def test_node_state_requires_admin(client, cluster, user_token):
    assert client.post(
        f"/api/v1/clusters/{cluster.id}/nodes/cn01/state",
        json={"state": "resume"},
        headers=auth_headers(user_token),
    ).status_code == 403


# --- 예약 (A-ND-04) ---------------------------------------------------------
# 생성은 **v0.0.43에만 있는 엔드포인트**다(0.0.40~0.0.42는 조회·삭제만 — 실측).
# 포털이 0.0.43에 고정된 이유가 이것이다.


def test_reservation_numbers_use_the_no_val_wrapper(
    client, db, cluster, admin_token, slurm_client
):
    """맨 숫자를 보내면 slurmrestd가 거부한다 — 요청 스키마가 `{set,infinite,number}`다."""
    resp = client.post(
        f"/api/v1/clusters/{cluster.id}/reservations",
        json={
            "name": "maint-1", "start_time": 1786147200, "duration_minutes": 120,
            "node_list": "slurm[01-02]", "flags": ["maint"], "users": "root",
        },
        headers=auth_headers(admin_token),
    )
    assert resp.status_code == 201, resp.text
    desc = [kw["desc"] for name, kw in slurm_client.calls if name == "create_reservation"][0]
    assert desc["start_time"] == {"set": True, "infinite": False, "number": 1786147200}
    assert desc["duration"] == {"set": True, "infinite": False, "number": 120}
    # 스펙은 배열을 요구한다 — 문자열을 보내면 경고가 붙는다(실측).
    assert desc["node_list"] == ["slurm[01-02]"]
    assert desc["flags"] == ["MAINT"]  # 대문자로 정규화된다

    from app.models import AuditLog

    entry = db.query(AuditLog).filter_by(action="RESERVATION_CREATE").one()
    assert entry.target == "maint-1" and "MAINT" in entry.detail


def test_reservation_requires_an_owner(client, cluster, admin_token, slurm_client):
    """Slurm이 요구한다 — 없으면 2053으로 거부된다(실측). 서버까지 가기 전에 막는다."""
    resp = client.post(
        f"/api/v1/clusters/{cluster.id}/reservations",
        json={"name": "no-owner", "start_time": 1786147200, "duration_minutes": 60,
              "node_count": 1},
        headers=auth_headers(admin_token),
    )
    assert resp.status_code == 422
    assert not [1 for n, _ in slurm_client.calls if n == "create_reservation"]


def test_reservation_requires_nodes(client, cluster, admin_token, slurm_client):
    """둘 다 없으면 Slurm이 클러스터 전체를 잡아 버릴 수 있다."""
    resp = client.post(
        f"/api/v1/clusters/{cluster.id}/reservations",
        json={"name": "maint-2", "start_time": 1786147200, "duration_minutes": 60,
              "users": "root"},
        headers=auth_headers(admin_token),
    )
    assert resp.status_code == 422
    assert not [kw for name, kw in slurm_client.calls if name == "create_reservation"]


def test_unknown_reservation_flag_is_rejected(client, cluster, admin_token, slurm_client):
    resp = client.post(
        f"/api/v1/clusters/{cluster.id}/reservations",
        json={"name": "m3", "start_time": 1786147200, "duration_minutes": 60,
              "node_count": 1, "flags": ["NUKE"], "users": "root"},
        headers=auth_headers(admin_token),
    )
    assert resp.status_code == 422


def test_reservation_delete_is_audited(client, db, cluster, admin_token, slurm_client):
    resp = client.delete(
        f"/api/v1/clusters/{cluster.id}/reservations/maint-1",
        headers=auth_headers(admin_token),
    )
    assert resp.status_code == 200
    assert [kw["reservation"] for n, kw in slurm_client.calls if n == "delete_reservation"] == [
        "maint-1"
    ]
    from app.models import AuditLog

    assert db.query(AuditLog).filter_by(action="RESERVATION_DELETE").one().target == "maint-1"


def test_reservation_writes_require_admin(client, cluster, user_token):
    cid = cluster.id
    assert client.post(
        f"/api/v1/clusters/{cid}/reservations",
        json={"name": "x", "start_time": 1, "duration_minutes": 1, "node_count": 1,
              "users": "root"},
        headers=auth_headers(user_token),
    ).status_code == 403
    assert client.delete(
        f"/api/v1/clusters/{cid}/reservations/x", headers=auth_headers(user_token)
    ).status_code == 403


def test_deactivate_keeps_row_and_is_audited(client, db, cluster, admin_token):
    from app.models import AuditLog, Cluster

    resp = client.delete(f"/api/v1/clusters/{cluster.id}", headers=auth_headers(admin_token))
    assert resp.status_code == 200
    db.expire_all()
    # 하드 삭제하면 감사 로그의 FK가 깨진다 — 행은 남아야 한다.
    assert db.get(Cluster, cluster.id).is_active is False
    entry = db.query(AuditLog).filter_by(action="CLUSTER_DEACTIVATE").one()
    assert entry.target_cluster_id == cluster.id


def test_missing_credential_is_rejected(client, db, admin_token):
    from app.models import Cluster

    bare = Cluster(name="bare", slurmrestd_url="http://bare:6820", is_active=True)
    db.add(bare)
    db.commit()

    resp = client.post(f"/api/v1/clusters/{bare.id}/test-rest", headers=auth_headers(admin_token))
    assert resp.status_code == 422


def _deactivate(client, cid, token):
    return client.delete(f"/api/v1/clusters/{cid}", headers=auth_headers(token))


def test_purge_requires_deactivation_first(client, cluster, admin_token):
    resp = client.delete(f"/api/v1/clusters/{cluster.id}/purge", headers=auth_headers(admin_token))
    assert resp.status_code == 409


def test_purge_refused_while_audit_log_references_cluster(client, db, cluster, admin_token):
    """감사 이력 보존이 우선 — 참조가 남아 있으면 삭제하지 않는다(C-05)."""
    from app.models import Cluster

    _deactivate(client, cluster.id, admin_token)  # 이 액션 자체가 감사 로그를 남긴다
    resp = client.delete(f"/api/v1/clusters/{cluster.id}/purge", headers=auth_headers(admin_token))
    assert resp.status_code == 409
    assert "감사 로그" in resp.text
    db.expire_all()
    assert db.get(Cluster, cluster.id) is not None


def test_purge_removes_unreferenced_cluster_and_its_secrets(
    client, db, admin_token, secret_store
):
    from app.models import AuditLog, Cluster, ClusterCredential

    created = _create(client, admin_token, alias="오타 클러스터").json()
    cid = created["id"]
    client.put(
        f"/api/v1/clusters/{cid}/credentials",
        json={"kind": "SLURM_JWT", "value": "throwaway.jwt"},
        headers=auth_headers(admin_token),
    )
    secret_ref = db.query(ClusterCredential).filter_by(cluster_id=cid).one().secret_ref

    # 등록·자격증명 감사 로그는 이 클러스터를 참조하므로 먼저 끊어 준다(테스트 목적).
    db.query(AuditLog).filter_by(target_cluster_id=cid).delete()
    db.commit()
    _deactivate(client, cid, admin_token)
    db.query(AuditLog).filter_by(target_cluster_id=cid).delete()
    db.commit()

    resp = client.delete(f"/api/v1/clusters/{cid}/purge", headers=auth_headers(admin_token))
    assert resp.status_code == 200
    db.expire_all()
    assert db.get(Cluster, cid) is None
    assert db.query(ClusterCredential).filter_by(cluster_id=cid).count() == 0

    # Secret 저장소의 실값까지 파기된다
    from app.core.errors import SecretNotFound

    with pytest.raises(SecretNotFound):
        secret_store.get(secret_ref)

    # 삭제 기록은 남되, 방금 지운 행을 FK로 가리키지 않는다
    entry = db.query(AuditLog).filter_by(action="CLUSTER_PURGE").one()
    # 이름이 아직 없으므로 별칭이 표시명이 된다 — 빈 대상은 추적이 안 된다.
    assert entry.target == "오타 클러스터"
    assert entry.target_cluster_id is None


def test_inactive_clusters_hidden_from_users_but_visible_to_admin(
    client, cluster, admin_token, user_token
):
    _deactivate(client, cluster.id, admin_token)

    for token in (user_token, admin_token):
        plain = client.get("/api/v1/clusters", headers=auth_headers(token)).json()
        assert all(c["id"] != cluster.id for c in plain)

    # 관리 화면만 비활성 행을 본다
    admin_all = client.get(
        "/api/v1/clusters?include_inactive=true", headers=auth_headers(admin_token)
    ).json()
    assert any(c["id"] == cluster.id for c in admin_all)

    user_all = client.get(
        "/api/v1/clusters?include_inactive=true", headers=auth_headers(user_token)
    ).json()
    assert all(c["id"] != cluster.id for c in user_all)


def test_rest_test_records_health_result(client, db, cluster, admin_token, slurm_client):
    """A-CL-01: 상태 컬럼이 읽을 '마지막 헬스체크'가 클러스터 행에 남는다."""
    assert cluster.last_health_at is None

    client.post(f"/api/v1/clusters/{cluster.id}/test-rest", headers=auth_headers(admin_token))
    db.expire_all()
    row = client.get(f"/api/v1/clusters/{cluster.id}", headers=auth_headers(admin_token)).json()
    assert row["last_health_ok"] is True
    assert row["last_health_at"] is not None


def test_failed_rest_test_is_recorded_as_unhealthy(client, db, cluster, admin_token, slurm_client):
    from app.core.errors import ExternalServiceError

    def boom(*a, **kw):
        raise ExternalServiceError("slurmrestd 응답 없음")

    slurm_client.ping = boom
    resp = client.post(
        f"/api/v1/clusters/{cluster.id}/test-rest", headers=auth_headers(admin_token)
    )
    assert resp.status_code >= 400
    db.expire_all()
    row = client.get(f"/api/v1/clusters/{cluster.id}", headers=auth_headers(admin_token)).json()
    assert row["last_health_ok"] is False
    assert row["last_health_at"] is not None


def test_cluster_detail_lists_credential_refs_without_values(client, cluster, admin_token):
    """폼 헤더가 '등록됨/만료일'을 보여주려면 참조 정보가 필요하다 — 값은 여전히 없다."""
    client.put(
        f"/api/v1/clusters/{cluster.id}/credentials",
        json={"kind": "SLURM_JWT", "value": "header.payload.sig"},
        headers=auth_headers(admin_token),
    )
    body = client.get(f"/api/v1/clusters/{cluster.id}", headers=auth_headers(admin_token)).json()
    kinds = [c["kind"] for c in body["credentials"]]
    assert "SLURM_JWT" in kinds
    assert "header.payload.sig" not in client.get(
        f"/api/v1/clusters/{cluster.id}", headers=auth_headers(admin_token)
    ).text
    assert all("value" not in c and "secret_ref" not in c for c in body["credentials"])


# --- 자원 조회 (A-ND-02·03·04, U-CL-02) -----------------------------------


def test_admin_lists_nodes_and_reservations(client, cluster, admin_token, slurm_client):
    nodes = client.get(f"/api/v1/clusters/{cluster.id}/nodes", headers=auth_headers(admin_token))
    assert nodes.status_code == 200
    assert nodes.json()[0]["name"] == "cn01"

    resv = client.get(
        f"/api/v1/clusters/{cluster.id}/reservations", headers=auth_headers(admin_token)
    )
    assert resv.status_code == 200
    assert resv.json() == []
    assert {c[0] for c in slurm_client.calls} >= {"get_nodes", "get_reservations"}


def test_partitions_open_to_user_but_nodes_are_admin_only(client, cluster, user_token):
    """파티션은 사용자 화면(U-CL-02)도 쓰지만, 노드·예약은 관리 화면 전용이다."""
    parts = client.get(
        f"/api/v1/clusters/{cluster.id}/partitions", headers=auth_headers(user_token)
    )
    assert parts.status_code == 200
    assert parts.json()[0]["name"] == "debug"

    assert (
        client.get(
            f"/api/v1/clusters/{cluster.id}/nodes", headers=auth_headers(user_token)
        ).status_code
        == 403
    )
    assert (
        client.get(
            f"/api/v1/clusters/{cluster.id}/reservations", headers=auth_headers(user_token)
        ).status_code
        == 403
    )


def test_partition_cpu_usage_is_summed_from_nodes(client, cluster, admin_token, slurm_client):
    """파티션 응답에는 CPU 총량만 있어서 할당/가용은 노드를 더해 채운다."""
    slurm_client.nodes_payload = {
        "nodes": [
            {"name": "cn01", "state": ["MIXED"], "cpus": 8, "alloc_cpus": 3, "partitions": ["debug"],
             "real_memory": 8000, "alloc_memory": 3000, "gres": "gpu:a100:2", "gres_used": "gpu:a100:1(IDX:0)"},
            {"name": "cn02", "state": ["IDLE"], "cpus": 8, "alloc_cpus": 0, "partitions": ["debug"],
             "real_memory": 8000, "alloc_memory": 0, "gres": "gpu:a100:2", "gres_used": "gpu:a100:0(IDX:N/A)"},
            # 빠져 있는 노드: 돌던 Job은 할당으로 세지만 남은 몫은 가용이 아니다.
            {"name": "cn03", "state": ["ALLOCATED", "DRAIN"], "cpus": 8, "alloc_cpus": 2, "partitions": ["debug"],
             "real_memory": 8000, "alloc_memory": 0, "gres": "gpu:a100:2", "gres_used": ""},
        ],
        "errors": [],
    }
    resp = client.get(
        f"/api/v1/clusters/{cluster.id}/partitions", headers=auth_headers(admin_token)
    )
    assert resp.status_code == 200
    body = resp.json()[0]
    assert body["cpu_usage"] == {"allocated": 5, "available": 13, "total": 24}
    # 메모리·GPU도 같은 셈법으로 함께 센다 — 따로 돌면 offline 판정이 갈릴 수 있다.
    assert body["memory_usage"] == {"allocated": 3000, "available": 13000, "total": 24000}
    assert body["gpu_usage"] == {"allocated": 1, "available": 3, "total": 6}


def test_partition_carries_its_nodes_for_the_user_view(client, cluster, user_token, slurm_client):
    """파티션을 펼치면 노드가 보여야 한다 (U-CL-02).

    `/nodes`는 관리자 전용이라 사용자 화면이 부를 수 없다 — 파티션 응답에 **필요한 필드만**
    추려 싣는다. `reason`(운영자가 적는 drain 사유) 같은 운영 정보는 넣지 않는다.
    """
    slurm_client.nodes_payload = {
        "nodes": [
            {
                "name": "cn02", "state": ["MIXED"], "cpus": 8, "alloc_cpus": 3,
                "real_memory": 16000, "alloc_memory": 4000, "gres": "gpu:a100:2",
                "partitions": ["debug"], "reason": "관리자 메모",
            },
            {"name": "cn01", "state": ["IDLE"], "cpus": 2, "partitions": ["debug", "gpu"]},
        ],
        "errors": [],
    }
    body = client.get(
        f"/api/v1/clusters/{cluster.id}/partitions", headers=auth_headers(user_token)
    ).json()
    rows = next(p for p in body if p["name"] == "debug")["node_list"]
    # 이름순이다 — 매번 순서가 흔들리면 화면이 깜빡인다.
    assert [n["name"] for n in rows] == ["cn01", "cn02"]

    nodes = {n["name"]: n for n in rows}
    # **파티션 요약과 같은 모양**이다 — 화면이 같은 컬럼에 나란히 그린다.
    assert nodes["cn02"]["cpu_usage"] == {"allocated": 3, "available": 5, "total": 8}
    assert nodes["cn02"]["memory_usage"] == {"allocated": 4000, "available": 12000, "total": 16000}
    assert nodes["cn02"]["gpu_usage"] == {"allocated": 0, "available": 2, "total": 2}
    assert nodes["cn02"]["gres"] == "gpu:a100:2"
    # 운영 정보는 새어 나가지 않는다.
    assert all("reason" not in n for n in nodes.values())


def test_partition_list_survives_partial_slurmdbd_error(client, cluster, admin_token):
    """slurmdbd가 끊겨 errors가 실려 와도 목록 자체는 그대로 보여준다(실물 관측 상황)."""
    resp = client.get(
        f"/api/v1/clusters/{cluster.id}/partitions", headers=auth_headers(admin_token)
    )
    assert resp.status_code == 200
    assert len(resp.json()) == 1


def test_accounts_map_users_from_associations(client, cluster, admin_token):
    """계정 응답의 associations는 비어 오므로 /associations로 매핑을 채운다(실측)."""
    rows = client.get(
        f"/api/v1/clusters/{cluster.id}/accounts", headers=auth_headers(admin_token)
    ).json()
    assert [r["name"] for r in rows] == ["hpc"]
    # user가 빈 association(계정 자체 노드)은 사용자 목록에서 빠진다
    assert [u["user"] for u in rows[0]["users"]] == ["jrpark"]
    assert rows[0]["users"][0]["is_default"] is True


def test_accounts_are_admin_only(client, cluster, user_token):
    assert client.get(
        f"/api/v1/clusters/{cluster.id}/accounts", headers=auth_headers(user_token)
    ).status_code == 403


def test_account_crud(client, cluster, admin_token, slurm_client):
    created = client.post(
        f"/api/v1/clusters/{cluster.id}/accounts",
        json={"name": "hpc-team", "description": "팀 계정", "organization": "dt-hpc"},
        headers=auth_headers(admin_token),
    )
    assert created.status_code == 201
    call = next(c for c in slurm_client.calls if c[0] == "create_account")
    # 계정만 만들면 사용자 연결이 붙지 않는다 — 클러스터 이름이 함께 가야 한다
    assert call[1]["cluster_name"] == "seoul-hpc"

    linked = client.post(
        f"/api/v1/clusters/{cluster.id}/accounts/hpc-team/users",
        json={"username": "jrpark"},
        headers=auth_headers(admin_token),
    )
    assert linked.status_code == 201

    assert client.delete(
        f"/api/v1/clusters/{cluster.id}/accounts/hpc-team/users/jrpark",
        headers=auth_headers(admin_token),
    ).status_code == 200
    assert client.delete(
        f"/api/v1/clusters/{cluster.id}/accounts/hpc-team", headers=auth_headers(admin_token)
    ).status_code == 200


def test_root_account_cannot_be_deleted(client, cluster, admin_token):
    """root는 Slurm이 만드는 최상위 계정 — 지우면 accounting 트리가 무너진다."""
    resp = client.delete(
        f"/api/v1/clusters/{cluster.id}/accounts/root", headers=auth_headers(admin_token)
    )
    assert resp.status_code == 422


def test_write_errors_in_200_body_are_surfaced(client, cluster, admin_token, slurm_client):
    """slurmdbd 쓰기는 HTTP 200으로도 실패를 알린다 — 본문 errors를 봐야 한다(실측)."""
    slurm_client.write_errors = [{"description": "Invalid account name"}]
    resp = client.post(
        f"/api/v1/clusters/{cluster.id}/accounts",
        json={"name": "bad"},
        headers=auth_headers(admin_token),
    )
    assert resp.status_code == 422
    assert "Invalid account name" in resp.json()["message"]


def test_account_write_is_admin_only(client, cluster, user_token):
    assert client.post(
        f"/api/v1/clusters/{cluster.id}/accounts",
        json={"name": "x"},
        headers=auth_headers(user_token),
    ).status_code == 403


def test_account_writes_do_not_impersonate(client, cluster, admin_token, slurm_client):
    """slurmdbd 쓰기는 AdminLevel이 필요하다 — 사용자로 위장하면 2002 거부된다(실측).

    책임 추적은 포털 RBAC(ADMIN 전용)와 감사 로그가 담당한다.
    """
    client.post(
        f"/api/v1/clusters/{cluster.id}/accounts",
        json={"name": "no-impersonation"},
        headers=auth_headers(admin_token),
    )
    call = next(c for c in slurm_client.calls if c[0] == "create_account")
    assert "as_user" not in call[1]


def test_qos_list_flattens_limits(client, cluster, admin_token):
    """중첩된 제한값을 화면이 쓰는 형태로 편다. 무제한은 None으로 접힌다."""
    rows = client.get(
        f"/api/v1/clusters/{cluster.id}/qos", headers=auth_headers(admin_token)
    ).json()
    assert rows[0]["name"] == "normal"
    assert rows[0]["priority"] == 0
    assert rows[0]["max_wall_minutes"] is None      # infinite
    assert rows[0]["max_jobs_per_user"] == 4


def test_qos_create_maps_limits_to_slurm_shape(client, cluster, admin_token, slurm_client):
    resp = client.post(
        f"/api/v1/clusters/{cluster.id}/qos",
        json={"name": "short", "description": "짧은 작업", "priority": 10,
              "max_wall_minutes": 60, "max_jobs_per_user": 2},
        headers=auth_headers(admin_token),
    )
    assert resp.status_code == 201
    sent = next(c for c in slurm_client.calls if c[0] == "create_qos")[1]["qos"]
    assert sent["priority"] == {"set": True, "number": 10}
    assert sent["limits"]["max"]["wall_clock"]["per"]["job"]["number"] == 60
    assert sent["limits"]["max"]["jobs"]["per"]["user"]["number"] == 2


def test_default_qos_cannot_be_deleted(client, cluster, admin_token):
    assert client.delete(
        f"/api/v1/clusters/{cluster.id}/qos/normal", headers=auth_headers(admin_token)
    ).status_code == 422


def test_qos_is_admin_only(client, cluster, user_token):
    assert client.get(
        f"/api/v1/clusters/{cluster.id}/qos", headers=auth_headers(user_token)
    ).status_code == 403


def test_account_level_qos_is_exposed(client, cluster, admin_token):
    """계정 단위 QOS는 user가 빈 association에 붙는다."""
    rows = client.get(
        f"/api/v1/clusters/{cluster.id}/accounts", headers=auth_headers(admin_token)
    ).json()
    assert rows[0]["qos"] == ["normal", "short"]


def test_set_user_qos(client, cluster, admin_token, slurm_client):
    resp = client.put(
        f"/api/v1/clusters/{cluster.id}/accounts/hpc/users/jrpark/qos",
        json={"qos": ["normal", "short"]},
        headers=auth_headers(admin_token),
    )
    assert resp.status_code == 200
    call = next(c for c in slurm_client.calls if c[0] == "set_association_qos")[1]
    assert call["account"] == "hpc" and call["username"] == "jrpark"
    assert call["qos"] == ["normal", "short"]


def test_set_account_qos_uses_empty_username(client, cluster, admin_token, slurm_client):
    """계정 단위는 user=""로 보내야 계정 노드가 대상이 된다."""
    client.put(
        f"/api/v1/clusters/{cluster.id}/accounts/hpc/qos",
        json={"qos": ["normal"]},
        headers=auth_headers(admin_token),
    )
    call = next(c for c in slurm_client.calls if c[0] == "set_association_qos")[1]
    assert call["username"] == ""


def test_qos_assign_is_admin_only(client, cluster, user_token):
    assert client.put(
        f"/api/v1/clusters/{cluster.id}/accounts/hpc/qos",
        json={"qos": []},
        headers=auth_headers(user_token),
    ).status_code == 403


def test_metrics_aggregate_node_state(client, cluster, admin_token):
    """Prometheus 없이 노드 상태에서 부하를 집계한다 (A-DB-02)."""
    body = client.get(
        f"/api/v1/clusters/{cluster.id}/metrics", headers=auth_headers(admin_token)
    ).json()
    assert body["nodes"] == 1
    assert body["cpus"] == 8
    assert body["states"] == [{"state": "IDLE", "count": 1}]


def test_metrics_handle_zero_capacity(client, cluster, admin_token, slurm_client):
    """CPU가 0인(=조회 실패) 상황에서 0으로 나누지 않는다."""
    slurm_client.get_nodes = lambda *, as_user=None: {"nodes": []}
    body = client.get(
        f"/api/v1/clusters/{cluster.id}/metrics", headers=auth_headers(admin_token)
    ).json()
    assert body["nodes"] == 0 and body["cpu_pct"] is None


def test_events_are_cluster_scoped(client, db, cluster, admin_token):
    """이벤트는 이 클러스터를 대상으로 한 감사 로그다 (A-DB-04)."""
    from app.models import AuditLog

    db.add(AuditLog(action="JOB_SUBMIT", target="1", target_cluster_id=cluster.id))
    db.add(AuditLog(action="OTHER_CLUSTER", target="x", target_cluster_id=None))
    db.commit()
    rows = client.get(
        f"/api/v1/clusters/{cluster.id}/events", headers=auth_headers(admin_token)
    ).json()
    actions = [r["action"] for r in rows]
    assert "JOB_SUBMIT" in actions
    assert "OTHER_CLUSTER" not in actions


def test_dashboard_endpoints_are_admin_only(client, cluster, user_token):
    for path in ("metrics", "events"):
        assert client.get(
            f"/api/v1/clusters/{cluster.id}/{path}", headers=auth_headers(user_token)
        ).status_code == 403