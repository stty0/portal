"""AD 연결 진단 (A-US-01 '연결 테스트'의 CLI 판).

포털이 AD에 붙기까지 실제로 깨지는 지점을 순서대로 짚는다:
도달성 → RootDSE → 전송 보안(StartTLS/LDAPS) → bind → 검색 → objectGUID 형식.

DB의 `ad_connection` 설정을 그대로 쓰므로, 운영 중 "로그인이 안 된다"를
포털 밖에서 재현·격리하는 용도로도 쓸 수 있다.

사용:
    set -a && . ./.env.dev && set +a
    .venv/bin/python scripts/check_ad.py [--user <sAMAccountName>]
"""

from __future__ import annotations

import argparse
import socket
import ssl
import sys
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ldap3 import ALL, Connection, Server, Tls

from app.core.config import get_settings
from app.core.errors import AdError, SecretNotFound
from app.core.secrets import EnvSecretStore
from app.db.session import get_session_factory, init_engine
from app.repositories.cluster import AdConnectionRepository
from app.services.auth import AuthService

OK, FAIL, WARN = "  OK  ", " FAIL ", " WARN "


def line(status: str, label: str, detail: str = "") -> None:
    print(f"[{status}] {label}" + (f" — {detail}" if detail else ""))


def main() -> None:
    parser = argparse.ArgumentParser(description="AD 연결 진단")
    parser.add_argument("--user", help="검색·조회를 시험할 sAMAccountName")
    args = parser.parse_args()

    settings = get_settings()
    init_engine(settings.database_url)
    session = get_session_factory()()
    conn_row = AdConnectionRepository(session).get_single()
    if conn_row is None:
        line(FAIL, "ad_connection", "DB에 AD 연결 설정이 없습니다. seed_dev.py를 먼저 실행하세요.")
        sys.exit(1)

    url = conn_row.ldaps_url or ""
    parsed = urlparse(url)
    host = parsed.hostname or url
    use_ssl = parsed.scheme == "ldaps"
    port = parsed.port or (636 if use_ssl else 389)
    print(f"대상: {url}  (host={host} port={port} ssl={use_ssl})")
    print(f"base_dn={conn_row.base_dn}  bind={conn_row.bind_account}  id_attr={conn_row.id_attribute}")
    print(f"allowed_group={conn_row.allowed_group or '(없음 — 전 사용자 허용)'}\n")

    # 1) TCP 도달성
    try:
        with socket.create_connection((host, port), timeout=5):
            line(OK, f"TCP {host}:{port}")
    except OSError as exc:
        line(FAIL, f"TCP {host}:{port}", str(exc))
        sys.exit(1)

    # 2) RootDSE (익명)
    try:
        server = Server(host, port=port, use_ssl=use_ssl, get_info=ALL, connect_timeout=5)
        anon = Connection(server, auto_bind=True)
        naming = (server.info.other or {}).get("defaultNamingContext")
        line(OK, "RootDSE", f"defaultNamingContext={naming}")
        if conn_row.base_dn and naming and conn_row.base_dn.lower() not in str(naming).lower():
            line(WARN, "base_dn", f"RootDSE({naming})와 설정({conn_row.base_dn})이 다릅니다")
        anon.unbind()
    except Exception as exc:
        line(WARN, "RootDSE", f"{type(exc).__name__}: {str(exc)[:80]}")

    # 3) 전송 보안 — 사용자 비밀번호가 평문으로 흐르는지가 여기서 갈린다
    if use_ssl:
        try:
            s = Server(host, port=port, use_ssl=True, tls=Tls(validate=ssl.CERT_NONE), connect_timeout=5)
            Connection(s).open()
            line(OK, "LDAPS 핸드셰이크")
        except Exception as exc:
            line(FAIL, "LDAPS 핸드셰이크", f"{str(exc)[:90]} (DC에 서버 인증서가 없을 수 있음)")
    else:
        try:
            s = Server(host, port=port, tls=Tls(validate=ssl.CERT_NONE), connect_timeout=5)
            c = Connection(s)
            c.open()
            c.start_tls()
            line(OK, "StartTLS 승격", "전송 암호화됨")
            c.unbind()
        except Exception as exc:
            line(
                WARN,
                "StartTLS 승격 불가",
                f"{str(exc)[:70]} — 평문 전송이므로 사용자 비밀번호가 네트워크에 노출됩니다",
            )

    # 4) bind + 5) 검색 — 포털이 실제로 쓰는 경로(AdClient) 그대로
    secrets = EnvSecretStore(settings)
    try:
        secrets.get(conn_row.bind_secret_ref or "")
    except SecretNotFound:
        line(FAIL, "bind 암호", f"환경변수 PORTAL_SECRET_AD_BIND 가 없습니다 (ref={conn_row.bind_secret_ref})")
        sys.exit(1)

    auth = AuthService(session, settings, secrets=secrets, sessions=None)
    client = auth.ad_client(conn_row)
    try:
        client.test_connection()
        line(OK, "bind (서비스 계정)")
    except AdError as exc:
        line(FAIL, "bind (서비스 계정)", f"{exc.message} / {exc.detail}")
        sys.exit(1)

    try:
        users = client.list_users()
        line(OK, "사용자 검색", f"{len(users)}명")
        for u in users[:10]:
            print(f"        {u.username:<20} {u.display_name or '':<16} guid={u.object_guid}")
        if users:
            guid = users[0].object_guid
            if len(guid) == 36 and guid.count("-") == 4:
                line(OK, "objectGUID 형식", guid)
            else:
                line(WARN, "objectGUID 형식", f"{guid!r} — user.ad_object_guid는 CHAR(36) 기대")
    except AdError as exc:
        line(FAIL, "사용자 검색", f"{exc.message} / {exc.detail}")

    if args.user:
        try:
            found = client.find_user(args.user)
            if found:
                line(OK, f"조회 {args.user}", f"guid={found.object_guid} name={found.display_name}")
            else:
                line(FAIL, f"조회 {args.user}", "허용 그룹 밖이거나 존재하지 않음")
        except AdError as exc:
            line(FAIL, f"조회 {args.user}", str(exc.detail))

    session.close()


if __name__ == "__main__":
    main()
