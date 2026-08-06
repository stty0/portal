"""클러스터 등록·자격증명 테스트 (A-CL-01~04, C-03).

Secret 취급이 핵심이다 — 값은 Secret 저장소에만 있고 DB·응답에는 참조만 남는다.
"""

import pytest

from tests.conftest import auth_headers


def _create(client, token, **overrides):
    body = {
        "name": "pangyo-gpu",
        "slurmrestd_url": "http://pangyo:6820",
        "api_version": "v0.0.41",
        "login_node": "login.pangyo",
        "ssh_account": "svc-portal",
        **overrides,
    }
    return client.post("/api/v1/clusters", json=body, headers=auth_headers(token))


def test_user_can_list_but_not_create(client, cluster, user_token):
    assert client.get("/api/v1/clusters", headers=auth_headers(user_token)).status_code == 200
    assert _create(client, user_token).status_code == 403


def test_admin_creates_cluster(client, admin_token):
    resp = _create(client, admin_token)
    assert resp.status_code == 201
    assert resp.json()["name"] == "pangyo-gpu"


def test_duplicate_name_conflicts(client, cluster, admin_token):
    resp = _create(client, admin_token, name="seoul-hpc")
    assert resp.status_code == 409


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

    created = _create(client, admin_token, name="typo-cluster").json()
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
    assert entry.target == "typo-cluster"
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


def test_desktop_image_ref_round_trips(client, admin_token, cluster):
    """U-IA-02 세션 이미지는 관리자가 설정한다 — 이 값 하나로 레지스트리 전환이 끝난다."""
    ref = "oras://reg.example.com/hpc/rocky9-mate:1.0"
    resp = client.patch(
        f"/api/v1/clusters/{cluster.id}",
        json={"desktop_image_ref": ref},
        headers=auth_headers(admin_token),
    )
    assert resp.status_code == 200
    assert resp.json()["desktop_image_ref"] == ref
    assert client.get(
        f"/api/v1/clusters/{cluster.id}", headers=auth_headers(admin_token)
    ).json()["desktop_image_ref"] == ref
