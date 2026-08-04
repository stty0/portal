"""AD(LDAP) 클라이언트 (backend-design §2.1·§2.4).

연결 전략: 조회는 매 요청 open/close(저빈도라 재사용 이점 없음), 로그인 bind는
사용자별 자격증명이 달라 애초에 재사용 불가.

식별자: SSSD 기본값과 맞춰 `sAMAccountName`을 username으로 쓰고, 불변 신원은
`objectGUID`를 쓴다(backend-design §3.2). 별도 매핑 테이블을 두지 않는다.
"""

from dataclasses import dataclass
from typing import Any, Protocol

from app.core.errors import AdError


@dataclass(frozen=True)
class AdUser:
    object_guid: str
    username: str
    display_name: str | None = None
    email: str | None = None


class AdClientProtocol(Protocol):
    def authenticate(self, username: str, password: str) -> AdUser: ...
    def find_user(self, username: str) -> AdUser | None: ...
    def list_users(self) -> list[AdUser]: ...
    def test_connection(self) -> bool: ...


@dataclass
class AdSettings:
    ldaps_url: str  # ldaps://host:636 또는 ldap://host:389 (스킴·포트를 그대로 해석)
    base_dn: str
    bind_account: str
    bind_password: str
    allowed_group: str | None = None
    id_attribute: str = "sAMAccountName"
    timeout: float = 10.0
    tls_verify: bool = True  # 사설 CA·자체서명 DC 인증서면 False + ca_cert_file 권장
    ca_cert_file: str | None = None


class AdClient:
    """ldap3 기반 구현. 서버 객체는 재사용하되 커넥션은 매 호출 open/close.

    전송 보안: `ldap://`(389)로 접속하면 **먼저 StartTLS로 승격을 시도**한다.
    AD는 기본적으로 "SSL/TLS가 아니면 bind에 integrity 필요" 정책이라 평문 simple bind를
    거부하며, 무엇보다 로그인마다 사용자 비밀번호가 평문으로 흐르면 안 된다.
    """

    def __init__(self, settings: AdSettings):
        self._s = settings

    def _tls(self):
        import ssl

        from ldap3 import Tls

        if self._s.tls_verify:
            return Tls(
                validate=ssl.CERT_REQUIRED,
                ca_certs_file=self._s.ca_cert_file,
                version=ssl.PROTOCOL_TLS_CLIENT,
            )
        return Tls(validate=ssl.CERT_NONE)

    def _server(self):
        from ldap3 import Server

        return Server(
            self._s.ldaps_url,
            get_info="NONE",
            connect_timeout=self._s.timeout,
            tls=self._tls(),
        )

    def _person_filter(self, ident: str) -> str:
        """사람 계정만 고른다.

        `(sAMAccountName=*)`만 쓰면 그룹·컴퓨터 계정까지 딸려온다(AD는 이들에도
        sAMAccountName을 부여한다). 또한 **비활성 AD 계정을 자동 활성 사용자로
        프로비저닝하면 안 되므로**(A-US-01) userAccountControl의 ACCOUNTDISABLE(2)
        비트를 제외한다 — `1.2.840.113556.1.4.803`은 AD의 비트 AND 매칭 규칙.
        """
        clauses = [
            "(objectClass=user)",
            "(objectCategory=person)",
            f"({self._s.id_attribute}={ident})",
            "(!(userAccountControl:1.2.840.113556.1.4.803:=2))",
        ]
        if self._s.allowed_group:
            # 허용 그룹 필터 — 정의서 A-US-01(허용 그룹 조건 충족 시 자동 활성화)
            clauses.append(f"(memberOf={self._s.allowed_group})")
        return "(&" + "".join(clauses) + ")"

    def _search_filter(self, username: str) -> str:
        return self._person_filter(_escape(username))

    def _entry_to_user(self, entry: Any) -> AdUser:
        def attr(name: str) -> Any:
            value = entry.get(name) if isinstance(entry, dict) else getattr(entry, name, None)
            if value is None:
                return None
            return getattr(value, "value", value)

        guid = attr("objectGUID")
        if not guid:
            raise AdError("AD 응답에 objectGUID가 없습니다.", detail={"entry": str(entry)[:200]})
        return AdUser(
            # str()로 감싸면 안 된다 — AD는 16바이트 이진값을 주므로 원본을 그대로 넘긴다.
            object_guid=_normalize_guid(guid),
            username=str(attr(self._s.id_attribute) or ""),
            display_name=_opt_str(attr("displayName")),
            email=_opt_str(attr("mail")),
        )

    def _bind(self, user: str | None = None, password: str | None = None):
        from ldap3 import Connection
        from ldap3.core.exceptions import LDAPException, LDAPStartTLSError

        conn = Connection(
            self._server(),
            user=user if user is not None else self._s.bind_account,
            password=password if password is not None else self._s.bind_password,
        )
        try:
            conn.open()
            if not conn.server.ssl:
                # 평문 389 → 가능하면 TLS로 승격한다. 실패해도 bind는 시도하되,
                # DC가 integrity를 요구하면 아래에서 실행 가능한 안내로 변환된다.
                try:
                    conn.start_tls()
                except LDAPStartTLSError:
                    pass
            if not conn.bind():
                raise AdError(
                    "AD 인증에 실패했습니다.", detail=_bind_hint(conn.result, conn.server.ssl)
                )
        except AdError:
            raise
        except LDAPException as exc:
            raise AdError("AD에 연결할 수 없습니다.", detail=str(exc)) from exc
        return conn

    def _search(self, conn, ldap_filter: str) -> list[Any]:
        conn.search(
            self._s.base_dn,
            ldap_filter,
            attributes=["objectGUID", self._s.id_attribute, "displayName", "mail"],
        )
        return list(conn.entries)

    # --- 공개 API -------------------------------------------------------
    def authenticate(self, username: str, password: str) -> AdUser:
        """사용자 자격증명으로 bind. 성공 시 AD 신원을 돌려준다."""
        if not password:
            # 빈 비밀번호는 LDAP에서 anonymous bind로 성공 처리될 수 있다.
            raise AdError("비밀번호가 비어 있습니다.")
        user = self.find_user(username)
        if user is None:
            raise AdError("AD에서 사용자를 찾을 수 없거나 허용 그룹 소속이 아닙니다.")
        conn = self._bind(user=f"{username}@{_domain_of(self._s.base_dn)}", password=password)
        conn.unbind()
        return user

    def find_user(self, username: str) -> AdUser | None:
        conn = self._bind()
        try:
            entries = self._search(conn, self._search_filter(username))
            return self._entry_to_user(entries[0]) if entries else None
        finally:
            conn.unbind()

    def list_users(self) -> list[AdUser]:
        conn = self._bind()
        try:
            return [self._entry_to_user(e) for e in self._search(conn, self._person_filter("*"))]
        finally:
            conn.unbind()

    def test_connection(self) -> bool:
        conn = self._bind()
        conn.unbind()
        return True


def _bind_hint(result: dict, tls_active: bool) -> str:
    """서버 진단 코드를 운영자가 조치 가능한 문장으로 바꾼다.

    `strongerAuthRequired`는 자격증명 오류가 아니라 **전송 보안 설정 문제**다.
    이걸 "비밀번호 틀림"으로 뭉뚱그리면 원인을 찾는 데 시간을 버린다.
    """
    description = (result or {}).get("description", "")
    if description == "strongerAuthRequired" and not tls_active:
        return (
            "DC가 서명(integrity)되지 않은 평문 bind를 거부했습니다. "
            "DC에 LDAPS 서버 인증서를 설치해 ldaps://(636) 또는 StartTLS를 사용하세요."
        )
    if description == "invalidCredentials":
        return "자격증명이 올바르지 않습니다."
    return description or "알 수 없는 오류"


def _escape(value: str) -> str:
    """LDAP 필터 특수문자 이스케이프 (RFC 4515) — 필터 주입 방지."""
    out = []
    for ch in value:
        if ch in "\\*()\0":
            out.append("\\%02x" % ord(ch))
        else:
            out.append(ch)
    return "".join(out)


def _normalize_guid(raw: object) -> str:
    """objectGUID를 표준 36자 문자열로 정규화한다 (`user.ad_object_guid`는 CHAR(36)).

    AD는 objectGUID를 16바이트 이진값으로 돌려주며, 앞 3개 필드가 **리틀엔디언**인
    혼합 바이트 순서다 — `UUID(bytes_le=...)`가 정확히 이 규약이다. 단순 hex 변환이나
    `str(bytes)`로는 Windows가 표시하는 GUID와 다른 값이 나와 신원이 어긋난다.
    ldap3 설정에 따라 이미 `{...}` 문자열로 올 수도 있어 양쪽을 모두 받는다.
    """
    import uuid

    if isinstance(raw, (bytes, bytearray)):
        return str(uuid.UUID(bytes_le=bytes(raw)))
    return str(raw).strip().strip("{}").lower()


def _opt_str(value: Any) -> str | None:
    return str(value) if value else None


def _domain_of(base_dn: str) -> str:
    parts = [p.split("=", 1)[1] for p in base_dn.split(",") if p.strip().lower().startswith("dc=")]
    return ".".join(parts)
