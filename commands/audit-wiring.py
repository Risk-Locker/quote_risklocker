"""House-Inspector Wiring & DB Persistence Auditor (`commands/audit-wiring.py`).

Checks:
  1. Mutating FastAPI routes (`POST`/`PUT`/`PATCH`/`DELETE`) for:
     - `MISSING_COMMIT`: router directly calls `db.flush`/`db.add`/`db.delete`/`setattr`/attribute mutation without `db.commit()`.
     - `JSON_NO_FLAG_MODIFIED`: direct subscript mutation of JSON/JSONB fields without `flag_modified`.
     - `MISSING_RBAC`: mutating route missing `require_role` / `current_user` / `current_auth` (outside public auth routes).
  2. Frontend `api(...)` / `apiRaw(...)` calls (`frontend/src/**/*.{ts,tsx}`) for:
     - `DEAD_FRONTEND_API_CALL`: frontend calls a path+method not registered in any FastAPI router.
     - `SILENT_CATCH_ON_MUTATION`: `try { ... api(..., { method: "POST"|... }) } catch { console.error(...) }` without UI error state or toast.

Usage:
  python commands/audit-wiring.py [--strict] [--json]
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]
ROUTERS_DIR = ROOT / "backend" / "app" / "api" / "routers"
FRONTEND_SRC = ROOT / "frontend" / "src"

MUTATING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
HTTP_METHODS = {"GET", "POST", "PUT", "PATCH", "DELETE"}
JSON_COLUMNS = frozenset(
    {
        "display_options",
        "fields",
        "scalar_decisions",
        "typed_value_override",
        "evidence_snapshot",
        "layout_override",
        "policy_rules",
        "review_flags",
        "metadata",
    }
)
PUBLIC_EXEMPT_PREFIXES = ("/auth/login", "/auth/logout", "/auth/refresh", "/auth/csrf")

API_CALL_START_RE = re.compile(
    r"""\b(?:api|apiRaw)\s*(?:<[^>;()]{1,120}>)?\s*\(""",
    re.MULTILINE,
)
METHOD_OPT_RE = re.compile(r"""\bmethod\s*:\s*['"]([A-Za-z]+)['"]""", re.IGNORECASE)
TRY_CATCH_RE = re.compile(
    r"""\btry\s*\{([\s\S]{0,2500}?)\}\s*catch\s*(?:\([^)]*\))?\s*\{([\s\S]{0,600}?)\}""",
    re.MULTILINE,
)
VISIBLE_ERR_RE = re.compile(
    r"""(?:toast|setToast|setError|setActionError|setSaveError|setMsg|setNotice|alert|throw\b|return\b)""",
    re.IGNORECASE,
)


@dataclass
class Finding:
    severity: str
    code: str
    file: str
    line: int
    message: str


@dataclass
class RouteEntry:
    method: str
    path: str
    file: str
    line: int
    func_name: str


def _normalize_backend_path(prefix: str, sub_path: str) -> str:
    joined = f"{prefix.rstrip('/')}/{sub_path.lstrip('/')}" if sub_path else (prefix or "/")
    if not joined.startswith("/"):
        joined = "/" + joined
    joined = re.sub(r"/{2,}", "/", joined)
    if len(joined) > 1 and joined.endswith("/"):
        joined = joined.rstrip("/")
    return joined


def _split_api_call(text: str, open_paren: int) -> tuple[str, str] | None:
    """Extract (first_url_arg_literal_without_quotes, second_arg_source) from api(...)."""
    n = len(text)
    i = open_paren + 1
    while i < n and text[i].isspace():
        i += 1
    if i >= n or text[i] not in ("'", '"', "`"):
        return None
    quote = text[i]
    i += 1
    url_start = i
    expr_depth = 0
    while i < n:
        ch = text[i]
        if ch == "\\":
            i += 2
            continue
        if quote == "`" and ch == "$" and i + 1 < n and text[i + 1] == "{":
            expr_depth += 1
            i += 2
            continue
        if expr_depth > 0:
            if ch == "{":
                expr_depth += 1
            elif ch == "}":
                expr_depth -= 1
            i += 1
            continue
        if ch == quote:
            url_val = text[url_start:i]
            i += 1
            break
        i += 1
    else:
        return None

    while i < n and text[i].isspace():
        i += 1
    if i >= n or text[i] != ",":
        return url_val, ""
    i += 1
    arg2_start = i
    depth = 1
    in_q: str | None = None
    while i < n and depth > 0:
        ch = text[i]
        if in_q:
            if ch == "\\":
                i += 2
                continue
            if ch == in_q:
                in_q = None
            i += 1
            continue
        if ch in ("'", '"', "`"):
            in_q = ch
        elif ch in ("(", "{", "["):
            depth += 1
        elif ch in (")", "}", "]"):
            depth -= 1
            if depth == 0:
                return url_val, text[arg2_start:i]
        i += 1
    return url_val, ""


def _normalize_frontend_path(raw: str) -> tuple[str, bool]:
    """Return (normalized_path, fully_static_prefix)."""
    s = raw.strip()
    if "${" in s and not s.startswith("/"):
        return s, False
    # Collapse nested template interpolations like ${path ? `/${path}` : ""} cleanly.
    out: list[str] = []
    i = 0
    while i < len(s):
        if s[i : i + 2] == "${":
            depth = 1
            i += 2
            while i < len(s) and depth > 0:
                if s[i] == "\\":
                    i += 2
                    continue
                if s[i] == "{":
                    depth += 1
                elif s[i] == "}":
                    depth -= 1
                i += 1
            out.append("{param}")
        else:
            out.append(s[i])
            i += 1
    s = "".join(out).split("?", 1)[0]
    if s.startswith("/api/"):
        s = s[4:]
    elif s == "/api":
        s = "/"
    if not s.startswith("/"):
        s = "/" + s
    s = re.sub(r"/{2,}", "/", s)
    if len(s) > 1 and s.endswith("/"):
        s = s.rstrip("/")
    return s, True


def _route_matches(fe_path: str, be_path: str) -> bool:
    raw_fe_parts = [p for p in fe_path.strip("/").split("/") if p]
    be_parts = [p for p in be_path.strip("/").split("/") if p]

    # Expand optional mid-segment interpolations like "trash{param}" -> ["trash"] or ["trash", "{param}"]
    candidates: list[list[str]] = [[]]
    for seg in raw_fe_parts:
        if "{param}" in seg and seg != "{param}":
            prefix = seg.replace("{param}", "")
            candidates = [c + [prefix] for c in candidates] + [c + [prefix, "{param}"] for c in candidates]
        else:
            candidates = [c + [seg] for c in candidates]

    for fe_parts in candidates:
        if be_parts and be_parts[-1].endswith(":path}"):
            prefix = be_parts[:-1]
            if len(fe_parts) >= len(prefix) and all(
                (bp.startswith("{") and bp.endswith("}")) or bp == fp for fp, bp in zip(fe_parts, prefix)
            ):
                return True
        elif len(fe_parts) == len(be_parts) and all(
            (bp.startswith("{") and bp.endswith("}")) or (fp.startswith("{") and fp.endswith("}")) or bp == fp
            for fp, bp in zip(fe_parts, be_parts)
        ):
            return True
    return False


def _attr_chain(node: ast.AST) -> str:
    parts: list[str] = []
    cur = node
    while isinstance(cur, ast.Attribute):
        parts.append(cur.attr)
        cur = cur.value
    if isinstance(cur, ast.Name):
        parts.append(cur.id)
        return ".".join(reversed(parts))
    return ""


def _parse_router_file(path: Path) -> tuple[list[RouteEntry], list[Finding]]:
    rel = path.relative_to(ROOT).as_posix()
    source = path.read_text(encoding="utf-8-sig", errors="replace")
    tree = ast.parse(source, filename=rel)

    prefix = ""
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "router" for t in node.targets):
            if isinstance(node.value, ast.Call):
                for kw in node.value.keywords:
                    if kw.arg == "prefix" and isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, str):
                        prefix = kw.value.value

    routes: list[RouteEntry] = []
    findings: list[Finding] = []

    for node in tree.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        endpoint_specs: list[tuple[str, str, bool]] = []
        for dec in node.decorator_list:
            if not isinstance(dec, ast.Call) or not isinstance(dec.func, ast.Attribute):
                continue
            chain = _attr_chain(dec.func)
            if not chain.startswith("router."):
                continue
            method_name = dec.func.attr.upper()
            sub_path = ""
            if dec.args and isinstance(dec.args[0], ast.Constant) and isinstance(dec.args[0].value, str):
                sub_path = dec.args[0].value
            has_dep_auth = False
            for kw in dec.keywords:
                if kw.arg == "dependencies" and "require_role" in ast.unparse(kw.value):
                    has_dep_auth = True
            if method_name in HTTP_METHODS:
                endpoint_specs.append((method_name, _normalize_backend_path(prefix, sub_path), has_dep_auth))
            elif method_name == "API_ROUTE":
                methods: list[str] = ["GET"]
                for kw in dec.keywords:
                    if kw.arg == "methods" and isinstance(kw.value, (ast.List, ast.Tuple, ast.Set)):
                        methods = [str(elt.value).upper() for elt in kw.value.elts if isinstance(elt, ast.Constant)]
                for m in methods:
                    if m in HTTP_METHODS:
                        endpoint_specs.append((m, _normalize_backend_path(prefix, sub_path), has_dep_auth))

        if not endpoint_specs:
            continue

        for method, full_path, _ in endpoint_specs:
            routes.append(RouteEntry(method=method, path=full_path, file=rel, line=node.lineno, func_name=node.name))

        is_mutating = any(m in MUTATING_METHODS for m, _, _ in endpoint_specs)
        if not is_mutating:
            continue

        arg_src = ast.unparse(node.args)
        body_calls: set[str] = set()
        direct_orm_writes = False
        subscript_json_writes = False
        has_flag_modified = False

        for sub in ast.walk(node):
            if isinstance(sub, ast.Call):
                c_name = _attr_chain(sub.func) or (sub.func.id if isinstance(sub.func, ast.Name) else "")
                if c_name:
                    body_calls.add(c_name)
                if c_name in {"db.flush", "db.add", "db.add_all", "db.delete", "setattr"}:
                    direct_orm_writes = True
                if c_name == "flag_modified" or c_name.endswith(".flag_modified"):
                    has_flag_modified = True
            elif isinstance(sub, ast.Assign):
                for tgt in sub.targets:
                    if isinstance(tgt, ast.Subscript) and isinstance(tgt.value, ast.Attribute) and tgt.value.attr in JSON_COLUMNS:
                        subscript_json_writes = True
                    elif isinstance(tgt, ast.Attribute) and tgt.attr in JSON_COLUMNS:
                        direct_orm_writes = True

        has_commit = any(c in {"db.commit", "session.commit"} or c.endswith(".commit") for c in body_calls)
        if direct_orm_writes and not has_commit:
            m0, p0, _ = endpoint_specs[0]
            findings.append(
                Finding(
                    severity="HIGH",
                    code="MISSING_COMMIT",
                    file=rel,
                    line=node.lineno,
                    message=f"{m0} {p0} ({node.name}) performs direct DB flush/ORM mutation without db.commit().",
                )
            )

        if subscript_json_writes and not has_flag_modified:
            m0, p0, _ = endpoint_specs[0]
            findings.append(
                Finding(
                    severity="HIGH",
                    code="JSON_NO_FLAG_MODIFIED",
                    file=rel,
                    line=node.lineno,
                    message=f"{m0} {p0} ({node.name}) mutates a JSON column key in-place without flag_modified().",
                )
            )

        is_public = all(any(p.startswith(pub) for pub in PUBLIC_EXEMPT_PREFIXES) for _, p, _ in endpoint_specs)
        has_auth = (
            any(dep for _, _, dep in endpoint_specs)
            or any(tok in arg_src for tok in ("current_user", "current_auth", "require_role", "AuthContext"))
            or any("require_role" in c for c in body_calls)
        )
        if not is_public and not has_auth:
            m0, p0, _ = endpoint_specs[0]
            findings.append(
                Finding(
                    severity="CRITICAL",
                    code="MISSING_RBAC",
                    file=rel,
                    line=node.lineno,
                    message=f"{m0} {p0} ({node.name}) mutates state without explicit auth/role dependency.",
                )
            )

    return routes, findings


def _audit_frontend(routes: list[RouteEntry]) -> list[Finding]:
    findings: list[Finding] = []
    if not FRONTEND_SRC.exists():
        return findings

    by_method: dict[str, list[str]] = {m: [] for m in HTTP_METHODS}
    for r in routes:
        by_method.setdefault(r.method, []).append(r.path)

    for file_path in sorted(FRONTEND_SRC.rglob("*.ts*")):
        rel = file_path.relative_to(ROOT).as_posix()
        text = file_path.read_text(encoding="utf-8", errors="replace")

        for match in API_CALL_START_RE.finditer(text):
            extracted = _split_api_call(text, match.end() - 1)
            if not extracted:
                continue
            raw_url, opts = extracted
            fe_path, is_static = _normalize_frontend_path(raw_url)
            if not is_static or fe_path.startswith("http"):
                continue
            m_opt = METHOD_OPT_RE.search(opts)
            method = m_opt.group(1).upper() if m_opt else "GET"
            candidates = by_method.get(method, [])
            if not any(_route_matches(fe_path, be_path) for be_path in candidates):
                line = text[: match.start()].count("\n") + 1
                findings.append(
                    Finding(
                        severity="HIGH",
                        code="DEAD_FRONTEND_API_CALL",
                        file=rel,
                        line=line,
                        message=f"Frontend calls {method} /api{fe_path} which has no matching FastAPI router endpoint.",
                    )
                )

        for match in TRY_CATCH_RE.finditer(text):
            try_body = match.group(1)
            catch_body = match.group(2).strip()
            if not re.search(r"\b(?:api|apiRaw)\s*(?:<[^>]*>)?\s*\(", try_body):
                continue
            m_opt = METHOD_OPT_RE.search(try_body)
            if not m_opt or m_opt.group(1).upper() not in MUTATING_METHODS:
                continue
            if not VISIBLE_ERR_RE.search(catch_body):
                line = text[: match.start(2)].count("\n") + 1
                findings.append(
                    Finding(
                        severity="MEDIUM",
                        code="SILENT_CATCH_ON_MUTATION",
                        file=rel,
                        line=line,
                        message="Mutating API call catch block logs/ignores error with no visible UI feedback (toast/error/throw).",
                    )
                )

    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description="House-Inspector API commit, RBAC & frontend wiring auditor.")
    parser.add_argument("--strict", action="store_true", help="Exit non-zero if CRITICAL/HIGH findings exist.")
    parser.add_argument("--json", action="store_true", help="Emit JSON report.")
    args = parser.parse_args()

    all_routes: list[RouteEntry] = []
    findings: list[Finding] = []
    for router_file in sorted(ROUTERS_DIR.glob("*.py")):
        if router_file.name == "__init__.py":
            continue
        r_entries, r_findings = _parse_router_file(router_file)
        all_routes.extend(r_entries)
        findings.extend(r_findings)

    findings.extend(_audit_frontend(all_routes))

    if args.json:
        print(json.dumps({"routes": len(all_routes), "findings": [asdict(f) for f in findings]}, indent=2))
    else:
        print(f"House-Inspector Wiring Audit: scanned {len(all_routes)} FastAPI routes + frontend/src api() calls.")
        counts: dict[str, int] = {}
        for f in findings:
            counts[f.code] = counts.get(f.code, 0) + 1
        print(f"Findings total={len(findings)} breakdown={counts}")
        for f in findings:
            print(f"  [{f.severity}] {f.code} @ {f.file}:{f.line} — {f.message}")

    if args.strict and any(f.severity in {"CRITICAL", "HIGH"} for f in findings):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
