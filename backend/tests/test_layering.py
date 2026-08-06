"""계층 규약 검증 (backend-design §1.2).

`router → service → repository/client` 방향을 코드로 강제한다. 문서로만 둔 규약은
도메인이 늘면서 조용히 무너진다.
"""

import ast
import re
import pathlib

APP = pathlib.Path(__file__).resolve().parent.parent / "app"


def _imports(path: pathlib.Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
        elif isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
    return names


def _modules(package: str) -> list[pathlib.Path]:
    return [p for p in (APP / package).rglob("*.py") if p.name != "__init__.py"]


def _violations(package: str, forbidden_prefixes: tuple[str, ...]) -> list[str]:
    out = []
    for path in _modules(package):
        for imported in _imports(path):
            if imported.startswith(forbidden_prefixes):
                out.append(f"{path.relative_to(APP.parent)} → {imported}")
    return out


def test_routers_do_not_touch_repositories_or_clients():
    """라우터는 service만 호출한다 — 비즈니스 로직·외부 연동이 새어 들어오면 안 된다."""
    assert _violations("routers", ("app.repositories", "app.clients")) == []


def test_services_do_not_import_routers():
    assert _violations("services", ("app.routers",)) == []


def test_repositories_do_not_import_services_or_clients():
    assert _violations("repositories", ("app.services", "app.clients", "app.routers")) == []


def test_clients_do_not_import_db_layers():
    """client는 외부 연동만 — DB·service를 알면 경계가 무너진다."""
    assert _violations("clients", ("app.services", "app.repositories", "app.db", "app.routers")) == []


def test_models_do_not_import_upper_layers():
    assert _violations("models", ("app.services", "app.repositories", "app.routers", "app.clients")) == []


def test_routers_use_permission_syntax_not_role_checks():
    """권한은 `require_permission("...")`로만 표현한다(backend-design §3.4).

    라우터가 role 문자열을 직접 비교하기 시작하면 permission 세분화 시 전부 고쳐야 한다.
    """
    offenders = []
    for path in _modules("routers"):
        source = path.read_text(encoding="utf-8")
        if 'role == "ADMIN"' in source or "role == 'ADMIN'" in source:
            offenders.append(path.name)
    assert offenders == []


def test_no_raw_sql_outside_repositories():
    """text() 원문 SQL은 repository 밖에서 쓰지 않는다.

    단어 경계로 찾는다 — 단순 부분 문자열이면 `read_text(` 같은 정상 호출까지 잡는다.
    """
    offenders = []
    for package in ("routers", "services"):
        for path in _modules(package):
            if re.search(r"\btext\(", path.read_text(encoding="utf-8")):
                offenders.append(path.name)
    assert offenders == []
