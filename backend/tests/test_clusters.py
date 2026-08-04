"""클러스터 등록·자격증명 테스트 (A-CL-01~04, C-03).

Secret 취급이 핵심이다 — 값은 Secret 저장소에만 있고 DB·응답에는 참조만 남는다.
"""

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
