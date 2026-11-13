"""Automated repository-wide SAST, RBAC, middleware, SSRF, PII, storage & anti-slop auditor.

Runs deterministically across `backend/app/` and `frontend/src/` using module-qualified
Python AST analysis (import-alias resolution, router prefix/dependency parsing, 4-hop call
graph for RBAC and mutating GET checks, SQLi taint analysis, Playwright/HTTP SSRF checks)
plus multi-line TypeScript sink/middleware audits and optional external scanners (`ruff`,
`bandit`, `mypy`, `pip-audit`, `npm lint`, `npm audit`).

Usage:
  python commands/security-audit.py [--strict] [--json] [--with-external] [--require-external]
"""

from __future__ import annotations

import argparse
import ast
import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]
BACKEND_APP = ROOT / "backend" / "app"
FRONTEND_SRC = ROOT / "frontend" / "src"

PUBLIC_NEXT_ROUTES = {"api", "login"}
DEPRECATED_GEMINI_RE = re.compile(
    r"\b("
    r"gemini-" r"3\.1-flash-lite(?:-preview)?|"
    r"gemini-" r"3\.5-flash(?!-lite)|"
    r"gemini-2\.[05]-[A-Za-z0-9_.-]+|"
    r"gemini-1\.[05]-[A-Za-z0-9_.-]+"
    r")\b"
)
NRIC_RE = re.compile(r"\b\d{6}-\d{2}-\d{4}\b")
PII_SECRET_RE = re.compile(
    r"(?:"
    r"AIza[0-9A-Za-z_-]{20,}|"
    r"sk-[A-Za-z0-9_-]{20,}|"
    r"sb_secret_[A-Za-z0-9_-]{16,}|"
    r"AKIA[0-9A-Z]{16}|"
    r"(?:ghp|gho|ghu|ghs)_[A-Za-z0-9]{20,}|"
    r"github_pat_[A-Za-z0-9_]{20,}|"
    r"re_[A-Za-z0-9]{8,}_[A-Za-z0-9]{12,}|"
    r"eyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}|"
    r"postgres(?:ql)?://(?!postgres:ci@(?:db\.ci\.supabase\.co|127\.0\.0\.1|localhost)\b)[^:\s'\"]+:[^@\s'\"]+@[^\s'\"]+|"
    r"-----BEGIN\s+(?:RSA\s+|EC\s+|OPENSSH\s+)?PRIVATE\s+KEY-----|"
    r"CHENG\s+TECK\s+KIO?I?NG|"
    r"357-"
    r"00105371|"
    r"12300"
    r"318500|"
    r"RISKLOCKER\s+SDN\.?\s*BHD\.?|Hong\s+Leong\s+Bank|"
    r"\bANY\s+368\b|\bJXS\s*2820\b|\bWXY\s*8899\b|\bRL2600003(?:14|41)\b"
    r")",
    re.IGNORECASE,
)

ADMIN_GUARD_NAMES = frozenset({"require_admin"})
BUSINESS_GUARD_NAMES = frozenset({"require_business_setup", "_require_business", "can_view_owner", "can_view_owner_record"})
ROLE_DISPATCH_NAMES = frozenset({"require_role"})
AUTH_DEP_NAMES = frozenset({"current_user", "current_auth"})
COMMIT_CALL_NAMES = frozenset({"commit", "flush"})
SQL_SINK_NAMES = frozenset({"text", "execute", "exec_driver_sql"})
HTTP_CLIENT_METHODS = frozenset({"get", "post", "put", "patch", "delete", "head", "request", "urlopen"})

FINANCIAL_MODULES = (
    "road_tax",
    "ncd_evaluator",
    "towing_evaluator",
    "marketing_comparison",
    "tenure",
    "generation_service",
    "formula_evaluator",
    "windscreen_scraper",
    "render_context",
    "template_renderer",
    "benefit_setup_service",
)
MONOLITH_PY_PREFIXES = (
    "backend/app/services/",
    "backend/app/api/routers/",
    "backend/app/extraction/",
    "backend/app/rendering/",
    "backend/app/workers/",
    "backend/app/models/",
)
ADMIN_ROUTE_PREFIXES = ("/admin", "/settings", "/users")
SENSITIVE_ROUTE_PREFIXES = (
    "/admin",
    "/settings",
    "/users",
    "/business",
    "/copilot",
    "/pics",
    "/comparison",
    "/tenures",
    "/templates",
    "/client-records",
    "/trash",
    "/catalogs",
    "/sessions",
    "/insights",
    "/upload",
    "/jobs",
    "/batches",
    "/drafts",
)
AUTH_SKIP_PREFIXES = ("/login", "/logout", "/auth/login", "/auth/logout", "/health")


@dataclass(frozen=True)
class Finding:
    severity: str  # CRITICAL | HIGH | MEDIUM
    rule_id: str
    location: str
    message: str


@dataclass
class FunctionBehavior:
    admin_rbac: bool = False
    business_rbac: bool = False
    has_auth: bool = False
    direct_commit: bool = False
    calls: set[str] | None = None
    has_untyped_payload: bool = False


def _rel(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def _module_name(path: Path) -> str:
    rel = _rel(path)
    if rel.startswith("backend/"):
        rel = rel[len("backend/"):]
    if rel.endswith("/__init__.py"):
        rel = rel[: -len("/__init__.py")]
    elif rel.endswith(".py"):
        rel = rel[:-3]
    return rel.replace("/", ".")


def _expr_chain(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        prefix = _expr_chain(node.value)
        return f"{prefix}.{node.attr}" if prefix else node.attr
    return ""


def _resolve_symbol(chain: str, aliases: dict[str, str]) -> str:
    if not chain:
        return ""
    head, *rest = chain.split(".")
    mapped = aliases.get(head)
    if not mapped:
        return chain
    return ".".join([mapped, *rest]) if rest else mapped


def _extract_aliases(tree: ast.AST, current_module: str, *, is_package: bool = False) -> dict[str, str]:
    aliases: dict[str, str] = {}
    pkg_parts = current_module.split(".") if is_package else current_module.split(".")[:-1]
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                local = alias.asname or alias.name.split(".")[0]
                aliases[local] = alias.name if alias.asname else local
                if alias.asname and "." in alias.name:
                    aliases[local] = alias.name
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            if node.level > 0:
                up = max(0, len(pkg_parts) - (node.level - 1))
                base = ".".join(pkg_parts[:up])
                mod = f"{base}.{mod}" if (base and mod) else (base or mod)
            for alias in node.names:
                if alias.name == "*":
                    continue
                local = alias.asname or alias.name
                aliases[local] = f"{mod}.{alias.name}" if mod else alias.name
    return aliases


KNOWN_ROLES = frozenset({"SUPER_ADMIN", "ADMIN", "DEV", "STAFF"})
ROLE_SET_CONSTANTS: dict[str, frozenset[str]] = {
    "ADMIN_ROLES": frozenset({"SUPER_ADMIN", "ADMIN"}),
    "PRIVILEGED_ROLES": frozenset({"SUPER_ADMIN", "ADMIN", "DEV"}),
    "BUSINESS_ROLES": frozenset({"SUPER_ADMIN", "ADMIN", "STAFF"}),
}


def _extract_role_tokens(expr: ast.AST) -> set[str] | None:
    """Strictly extract role constant tokens; return None on dynamic/starred/unknown expressions."""
    if isinstance(expr, ast.Starred):
        return None
    if isinstance(expr, (ast.List, ast.Tuple, ast.Set)):
        out: set[str] = set()
        for el in expr.elts:
            sub = _extract_role_tokens(el)
            if sub is None:
                return None
            out |= sub
        return out
    if isinstance(expr, ast.Constant) and isinstance(expr.value, str):
        tok = expr.value.strip().upper()
        return {tok} if tok else None
    if isinstance(expr, ast.Attribute):
        if expr.attr == "value" and isinstance(expr.value, ast.Attribute):
            return {expr.value.attr.upper()}
        if expr.attr != "value":
            return {expr.attr.upper()}
        return None
    if isinstance(expr, ast.Name):
        known_set = ROLE_SET_CONSTANTS.get(expr.id)
        if known_set is not None:
            return set(known_set)
        return None
    return None


def _evaluate_allowed_role_tokens(tokens: set[str] | None) -> tuple[bool, bool]:
    """Return (grants_admin, grants_business) for an explicit allowlist of roles."""
    if not tokens or not (tokens <= KNOWN_ROLES):
        return False, False
    if "STAFF" in tokens:
        return False, True
    if tokens <= {"SUPER_ADMIN", "ADMIN", "DEV"} and bool(tokens & {"SUPER_ADMIN", "ADMIN"}):
        return True, True
    return False, True


def _classify_require_role_call(call_node: ast.Call) -> tuple[bool, bool]:
    """Return (grants_admin, grants_business) for an explicit require_role(...) invocation."""
    if any(isinstance(a, ast.Starred) for a in call_node.args):
        return False, False
    if any(kw.arg not in {"roles", "allowed_roles", "user"} for kw in call_node.keywords):
        return False, False
    role_exprs: list[ast.expr] = list(call_node.args[1:])
    for kw in call_node.keywords:
        if kw.arg in {"roles", "allowed_roles"}:
            role_exprs.append(kw.value)
    if not role_exprs:
        return False, False
    tokens: set[str] = set()
    for expr in role_exprs:
        sub = _extract_role_tokens(expr)
        if sub is None:
            return False, False
        tokens |= sub
    return _evaluate_allowed_role_tokens(tokens)


def _is_role_attr_expr(expr: ast.AST) -> bool:
    chain = _expr_chain(expr)
    return chain == "role" or chain.endswith(".role")


def _allowed_tokens_from_deny_test(test: ast.AST) -> set[str] | None:
    if isinstance(test, ast.Compare) and len(test.ops) == 1 and len(test.comparators) == 1:
        op, comp = test.ops[0], test.comparators[0]
        if isinstance(op, (ast.NotIn, ast.NotEq)) and _is_role_attr_expr(test.left):
            return _extract_role_tokens(comp)
        return None
    if isinstance(test, ast.UnaryOp) and isinstance(test.op, ast.Not):
        inner = test.operand
        if (
            isinstance(inner, ast.Compare)
            and len(inner.ops) == 1
            and len(inner.comparators) == 1
            and isinstance(inner.ops[0], (ast.In, ast.Eq))
            and _is_role_attr_expr(inner.left)
        ):
            return _extract_role_tokens(inner.comparators[0])
        return None
    if isinstance(test, ast.BoolOp) and isinstance(test.op, ast.And):
        combined: set[str] = set()
        for val in test.values:
            if not (
                isinstance(val, ast.Compare)
                and len(val.ops) == 1
                and len(val.comparators) == 1
                and isinstance(val.ops[0], ast.NotEq)
                and _is_role_attr_expr(val.left)
            ):
                return None
            sub = _extract_role_tokens(val.comparators[0])
            if not sub:
                return None
            combined |= sub
        return combined or None
    return None


def _allowed_tokens_from_allow_test(test: ast.AST) -> set[str] | None:
    if isinstance(test, ast.Compare) and len(test.ops) == 1 and len(test.comparators) == 1:
        op, comp = test.ops[0], test.comparators[0]
        if isinstance(op, (ast.In, ast.Eq)) and _is_role_attr_expr(test.left):
            return _extract_role_tokens(comp)
        return None
    if isinstance(test, ast.BoolOp) and isinstance(test.op, ast.Or):
        combined: set[str] = set()
        for val in test.values:
            sub = _allowed_tokens_from_allow_test(val)
            if not sub:
                return None
            combined |= sub
        return combined or None
    return None


def _detect_allowlist_early_return_guard(fn_node: ast.FunctionDef | ast.AsyncFunctionDef) -> tuple[bool, bool]:
    """Recognize fail-closed allowlist helpers ending with `raise ...` after explicit role early-returns."""
    if not fn_node.body or not isinstance(fn_node.body[-1], ast.Raise):
        return False, False
    collected: set[str] = set()
    for stmt in fn_node.body[:-1]:
        if isinstance(stmt, ast.Expr):
            continue
        if isinstance(stmt, ast.If):
            tokens = _allowed_tokens_from_allow_test(stmt.test)
            body_returns_cleanly = (
                bool(stmt.body)
                and isinstance(stmt.body[-1], ast.Return)
                and not any(isinstance(sub, ast.Raise) for sub in stmt.body)
            )
            orelse_returns = any(isinstance(sub, ast.Return) for s in stmt.orelse for sub in ast.walk(s))
            if tokens is not None and body_returns_cleanly and not orelse_returns:
                collected |= tokens
                continue
        if any(isinstance(sub, ast.Return) for sub in ast.walk(stmt)):
            return False, False
    return _evaluate_allowed_role_tokens(collected) if collected else (False, False)


def _is_inline_role_guard(if_node: ast.If) -> tuple[bool, bool]:
    """Detect explicit fail-closed inline guards like `if user.role not in {...}: raise AppError(..., 403)`."""
    if not any(isinstance(stmt, ast.Raise) for stmt in if_node.body):
        return False, False
    tokens = _allowed_tokens_from_deny_test(if_node.test)
    return _evaluate_allowed_role_tokens(tokens)


def _resolve_callee(
    chain: str,
    current_module: str,
    aliases: dict[str, str],
    graph: dict[str, FunctionBehavior],
    reexports: dict[str, str] | None = None,
) -> str:
    reexp = reexports or {}
    resolved = _resolve_symbol(chain, aliases)
    resolved = reexp.get(resolved, resolved)
    if resolved in graph:
        return resolved
    local_candidate = f"{current_module}.{chain}"
    local_candidate = reexp.get(local_candidate, local_candidate)
    if local_candidate in graph:
        return local_candidate
    return resolved


def _iter_non_default_body_nodes(node: ast.FunctionDef | ast.AsyncFunctionDef):
    for stmt in node.body:
        yield from ast.walk(stmt)


def _depends_targets(
    args_nodes: list[ast.expr],
    current_module: str,
    aliases: dict[str, str],
    graph: dict[str, FunctionBehavior],
    reexports: dict[str, str] | None = None,
) -> set[str]:
    targets: set[str] = set()
    for expr in args_nodes:
        if expr is None:
            continue
        for sub in ast.walk(expr):
            if isinstance(sub, ast.Call):
                cname = _expr_chain(sub.func).split(".")[-1]
                if cname == "Depends" and sub.args:
                    dep_chain = _expr_chain(sub.args[0])
                    if dep_chain:
                        targets.add(_resolve_callee(dep_chain, current_module, aliases, graph, reexports))
    return targets


def _analyze_function_node(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
    current_module: str,
    aliases: dict[str, str],
    graph: dict[str, FunctionBehavior] | None = None,
    reexports: dict[str, str] | None = None,
) -> FunctionBehavior:
    g = graph or {}
    calls: set[str] = set()
    admin_rbac = False
    business_rbac = False
    has_auth = False
    direct_commit = False

    # Inspect both default-value Depends(...) and Annotated[..., Depends(...)] parameter annotations
    dep_exprs: list[ast.expr] = (
        [d for d in node.args.defaults if d is not None]
        + [d for d in node.args.kw_defaults if d is not None]
        + [a.annotation for a in (*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs) if a.annotation is not None]
    )
    for opt_arg in (node.args.vararg, node.args.kwarg):
        if opt_arg is not None and opt_arg.annotation is not None:
            dep_exprs.append(opt_arg.annotation)

    for dep_target in _depends_targets(dep_exprs, current_module, aliases, g, reexports):
        leaf = dep_target.split(".")[-1]
        if leaf in ADMIN_GUARD_NAMES:
            admin_rbac = True
            business_rbac = True
            has_auth = True
        elif leaf in BUSINESS_GUARD_NAMES:
            business_rbac = True
            has_auth = True
        elif leaf in AUTH_DEP_NAMES:
            has_auth = True
        elif leaf not in {"current_auth_optional", "get_db", "settings_dep"}:
            calls.add(dep_target)

    g_adm, g_bus = _detect_allowlist_early_return_guard(node)
    admin_rbac = admin_rbac or g_adm
    business_rbac = business_rbac or g_bus

    for child in _iter_non_default_body_nodes(node):
        if isinstance(child, ast.If):
            adm, bus = _is_inline_role_guard(child)
            admin_rbac = admin_rbac or adm
            business_rbac = business_rbac or bus
        elif isinstance(child, ast.Call):
            chain = _expr_chain(child.func)
            resolved = _resolve_callee(chain, current_module, aliases, g, reexports)
            leaf = chain.split(".")[-1] if chain else ""
            if resolved:
                calls.add(resolved)
            if leaf in ADMIN_GUARD_NAMES:
                admin_rbac = True
                business_rbac = True
            elif leaf in BUSINESS_GUARD_NAMES:
                business_rbac = True
            elif leaf in ROLE_DISPATCH_NAMES:
                adm, bus = _classify_require_role_call(child)
                admin_rbac = admin_rbac or adm
                business_rbac = business_rbac or bus
            elif leaf in COMMIT_CALL_NAMES:
                direct_commit = True
            elif leaf in {"execute", "exec_driver_sql"} and child.args:
                arg_src = ast.unparse(child.args[0]).lower() if hasattr(ast, "unparse") else ""
                if re.search(r"\b(?:update|delete|insert|alter|drop)\s*\(|\b(?:insert\s+into|update\s+\w+\s+set|delete\s+from)\b", arg_src):
                    direct_commit = True

    return FunctionBehavior(
        admin_rbac=admin_rbac,
        business_rbac=business_rbac,
        has_auth=has_auth,
        direct_commit=direct_commit,
        calls=calls,
        has_untyped_payload=_has_untyped_dict_payload(node),
    )


def _iter_functions_with_qualname(tree: ast.AST, module_name: str):
    def walk_scope(body: list[ast.stmt], prefix: str):
        for stmt in body:
            if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
                qn = f"{prefix}.{stmt.name}"
                yield qn, stmt
                yield from walk_scope(stmt.body, qn)
            elif isinstance(stmt, ast.ClassDef):
                yield from walk_scope(stmt.body, f"{prefix}.{stmt.name}")

    if isinstance(tree, ast.Module):
        yield from walk_scope(tree.body, module_name)


def _extract_module_reexports(
    tree: ast.AST,
    current_module: str,
    direct_qns: set[str],
    *,
    is_package: bool = False,
) -> dict[str, str]:
    reexports: dict[str, str] = {}
    if not isinstance(tree, ast.Module):
        return reexports
    pkg_parts = current_module.split(".") if is_package else current_module.split(".")[:-1]
    for stmt in tree.body:
        if isinstance(stmt, ast.ImportFrom):
            mod = stmt.module or ""
            if stmt.level > 0:
                up = max(0, len(pkg_parts) - (stmt.level - 1))
                base = ".".join(pkg_parts[:up])
                mod = f"{base}.{mod}" if (base and mod) else (base or mod)
            for alias in stmt.names:
                if alias.name == "*":
                    continue
                local = alias.asname or alias.name
                src_qn = f"{current_module}.{local}"
                if src_qn not in direct_qns and mod:
                    reexports[src_qn] = f"{mod}.{alias.name}"
    return reexports


def _resolve_reexport_chain(sym: str, raw_reexports: dict[str, str]) -> str:
    cur = sym
    for _ in range(6):
        direct = raw_reexports.get(cur)
        if direct and direct != cur:
            cur = direct
            continue
        if "." in cur:
            parts = cur.split(".")
            replaced = False
            for k in range(len(parts) - 1, 0, -1):
                pref = ".".join(parts[:k])
                mapped = raw_reexports.get(pref)
                if mapped and mapped != pref:
                    cur = ".".join([mapped, *parts[k:]])
                    replaced = True
                    break
            if replaced:
                continue
        break
    return cur


def _build_backend_call_graph() -> tuple[dict[str, FunctionBehavior], list[tuple[str, ast.AST, dict[str, str]]], dict[str, str]]:
    """Index backend functions strictly by `module.qualname`, resolving re-export facades."""
    graph: dict[str, FunctionBehavior] = {}
    parsed_files: list[tuple[str, ast.AST, dict[str, str]]] = []
    all_reexports: dict[str, str] = {}
    if not BACKEND_APP.exists():
        return graph, parsed_files, all_reexports

    raw_reexports: dict[str, str] = {}
    parsed_meta: list[tuple[str, ast.AST, dict[str, str], bool]] = []
    for py_file in sorted(BACKEND_APP.rglob("*.py")):
        try:
            tree = ast.parse(py_file.read_text(encoding="utf-8", errors="ignore"), filename=str(py_file))
        except SyntaxError:
            continue
        is_pkg = py_file.name == "__init__.py"
        mod = _module_name(py_file)
        aliases = _extract_aliases(tree, mod, is_package=is_pkg)
        parsed_files.append((mod, tree, aliases))
        parsed_meta.append((mod, tree, aliases, is_pkg))
        for qn, _fn in _iter_functions_with_qualname(tree, mod):
            graph[qn] = FunctionBehavior(calls=set())

    direct_qns = set(graph.keys())
    for mod, tree, _aliases, is_pkg in parsed_meta:
        raw_reexports.update(_extract_module_reexports(tree, mod, direct_qns, is_package=is_pkg))

    resolved_fn_reexports: dict[str, str] = {}
    for src in raw_reexports:
        target = _resolve_reexport_chain(src, raw_reexports)
        all_reexports[src] = target
        if target in direct_qns:
            resolved_fn_reexports[src] = target

    for mod, tree, aliases in parsed_files:
        for qn, fn in _iter_functions_with_qualname(tree, mod):
            graph[qn] = _analyze_function_node(fn, mod, aliases, graph, all_reexports)

    for alias_qn, canon_qn in resolved_fn_reexports.items():
        if canon_qn in graph:
            graph[alias_qn] = graph[canon_qn]

    return graph, parsed_files, all_reexports


def _transitive_flag(
    beh: FunctionBehavior,
    graph: dict[str, FunctionBehavior],
    attr: str,
    depth: int = 4,
    best_depth: dict[str, int] | None = None,
) -> bool:
    if getattr(beh, attr):
        return True
    if depth <= 0 or not beh.calls:
        return False
    seen = best_depth if best_depth is not None else {}
    for callee_qn in beh.calls:
        if seen.get(callee_qn, -1) >= depth:
            continue
        seen[callee_qn] = depth
        callee = graph.get(callee_qn)
        if callee and _transitive_flag(callee, graph, attr, depth - 1, seen):
            return True
    return False


def _has_untyped_dict_payload(node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    skip_names = {"self", "cls", "db", "user", "auth", "settings", "response", "background_tasks", "bg"}
    all_params = [(a, d) for a, d in zip(node.args.args, [None] * (len(node.args.args) - len(node.args.defaults)) + list(node.args.defaults))]
    all_params.extend(zip(node.args.kwonlyargs, node.args.kw_defaults))

    for arg, default in all_params:
        if arg.arg in skip_names:
            continue
        def_src = ast.unparse(default) if (default is not None and hasattr(ast, "unparse")) else ""
        if "Depends(" in def_src or "Query(" in def_src or "Path(" in def_src or "Header(" in def_src or "Cookie(" in def_src or "File(" in def_src:
            continue
        ann_src = ast.unparse(arg.annotation) if (arg.annotation is not None and hasattr(ast, "unparse")) else ""
        if ann_src in {"", "dict", "Dict", "Any"} or re.search(r"\b(?:dict|Dict)\s*[\[\|]|\bOptional\s*\[\s*(?:dict|Dict|Any)", ann_src):
            if ann_src == "UploadFile":
                continue
            if arg.annotation is None and arg.arg.endswith("_id"):
                continue
            return True
        if ann_src == "Request":
            for child in _iter_non_default_body_nodes(node):
                if isinstance(child, ast.Call) and isinstance(child.func, ast.Attribute) and child.func.attr == "json":
                    if getattr(child.func.value, "id", "") == arg.arg:
                        return True
    return False


def _extract_router_metadata(
    tree: ast.AST,
    mod: str,
    aliases: dict[str, str],
    graph: dict[str, FunctionBehavior],
    reexports: dict[str, str] | None = None,
) -> tuple[dict[str, str], dict[str, set[str]], list[tuple[str, str, str, set[str]]]]:
    prefixes: dict[str, str] = {}
    router_deps: dict[str, set[str]] = {}
    intra_edges: list[tuple[str, str, str, set[str]]] = []
    if not isinstance(tree, ast.Module):
        return prefixes, router_deps, intra_edges

    for stmt in ast.walk(tree):
        if isinstance(stmt, ast.Assign) and isinstance(stmt.value, ast.Call):
            resolved_cls = _resolve_symbol(_expr_chain(stmt.value.func), aliases)
            leaf_cls = resolved_cls.split(".")[-1] if resolved_cls else ""
            if leaf_cls in {"APIRouter", "FastAPI"}:
                prefix = ""
                deps_kw: list[ast.expr] = []
                for kw in stmt.value.keywords:
                    if kw.arg == "prefix" and isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, str):
                        prefix = kw.value.value
                    elif kw.arg == "dependencies":
                        deps_kw.append(kw.value)
                dep_set = _depends_targets(deps_kw, mod, aliases, graph, reexports) if deps_kw else set()
                for tgt in stmt.targets:
                    if isinstance(tgt, ast.Name):
                        prefixes[tgt.id] = prefix
                        router_deps[tgt.id] = dep_set
        elif isinstance(stmt, ast.Call) and isinstance(stmt.func, ast.Attribute) and stmt.func.attr == "include_router":
            parent_chain = _expr_chain(stmt.func.value)
            child_chain = _expr_chain(stmt.args[0]) if stmt.args else ""
            if not child_chain:
                for kw in stmt.keywords:
                    if kw.arg == "router":
                        child_chain = _expr_chain(kw.value)
            if not parent_chain or not child_chain:
                continue
            mount_pref = ""
            mount_dep_exprs: list[ast.expr] = []
            for kw in stmt.keywords:
                if kw.arg == "prefix" and isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, str):
                    mount_pref = kw.value.value
                elif kw.arg == "dependencies":
                    mount_dep_exprs.append(kw.value)
            mount_deps = _depends_targets(mount_dep_exprs, mod, aliases, graph, reexports) if mount_dep_exprs else set()
            resolved_child = _resolve_symbol(child_chain, aliases)
            if "." not in resolved_child:
                resolved_child = f"{mod}.{resolved_child}"
            if reexports:
                resolved_child = _resolve_reexport_chain(resolved_child, reexports)
            resolved_parent = _resolve_symbol(parent_chain, aliases)
            if "." not in resolved_parent:
                resolved_parent = f"{mod}.{resolved_parent}"
            if reexports:
                resolved_parent = _resolve_reexport_chain(resolved_parent, reexports)
            intra_edges.append((resolved_parent, resolved_child, mount_pref, mount_deps))

    return prefixes, router_deps, intra_edges


def _build_backend_router_mounts(
    parsed_files: list[tuple[str, ast.AST, dict[str, str]]],
    graph: dict[str, FunctionBehavior],
    reexports: dict[str, str] | None = None,
) -> dict[str, tuple[str, set[str]]]:
    """Resolve cumulative (inherited_prefix, inherited_deps) across module include_router chains."""
    own_meta: dict[str, tuple[str, set[str]]] = {}
    edges: list[tuple[str, str, str, set[str]]] = []

    for mod, tree, aliases in parsed_files:
        prefixes, router_deps, local_edges = _extract_router_metadata(tree, mod, aliases, graph, reexports)
        for var_name, pref in prefixes.items():
            own_meta[f"{mod}.{var_name}"] = (pref, set(router_deps.get(var_name, set())))
        edges.extend(local_edges)

    inherited: dict[str, tuple[str, set[str]]] = {}
    for _ in range(6):
        changed = False
        for parent_key, child_key, m_pref, m_deps in edges:
            p_inh_pref, p_inh_deps = inherited.get(parent_key, ("", set()))
            p_own_pref, p_own_deps = own_meta.get(parent_key, ("", set()))
            new_pref = p_inh_pref + p_own_pref + m_pref
            new_deps = p_inh_deps | p_own_deps | m_deps
            cur_pref, cur_deps = inherited.get(child_key, ("", set()))
            if new_pref != cur_pref or new_deps != cur_deps:
                inherited[child_key] = (new_pref, new_deps)
                changed = True
        if not changed:
            break
    return inherited


def _extract_route_decorator(
    dec: ast.Call,
    prefixes: dict[str, str],
    mod: str,
    aliases: dict[str, str],
    graph: dict[str, FunctionBehavior],
    reexports: dict[str, str] | None = None,
) -> list[tuple[str, str, str, set[str]]]:
    if not isinstance(dec.func, ast.Attribute):
        return []
    router_name = _expr_chain(dec.func.value)
    attr = dec.func.attr.lower()
    if attr not in {"get", "post", "put", "patch", "delete", "api_route"}:
        return []

    sub_path = ""
    if dec.args and isinstance(dec.args[0], ast.Constant) and isinstance(dec.args[0].value, str):
        sub_path = dec.args[0].value
    methods: list[str] = [attr] if attr != "api_route" else []
    dep_exprs: list[ast.expr] = []

    for kw in dec.keywords:
        if kw.arg == "path" and isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, str):
            sub_path = kw.value.value
        elif kw.arg == "methods" and isinstance(kw.value, (ast.List, ast.Tuple, ast.Set)):
            methods = [
                el.value.lower()
                for el in kw.value.elts
                if isinstance(el, ast.Constant) and isinstance(el.value, str)
            ]
        elif kw.arg == "dependencies":
            dep_exprs.append(kw.value)

    if not methods:
        methods = ["get"]
    full_path = prefixes.get(router_name, "") + sub_path
    dec_deps = _depends_targets(dep_exprs, mod, aliases, graph, reexports) if dep_exprs else set()
    return [(router_name, m, full_path, dec_deps) for m in methods]


def _extract_imperative_routes(
    tree: ast.AST,
    prefixes: dict[str, str],
    mod: str,
    aliases: dict[str, str],
    graph: dict[str, FunctionBehavior],
    reexports: dict[str, str] | None = None,
) -> list[tuple[str, str, str, set[str], str, int]]:
    routes: list[tuple[str, str, str, set[str], str, int]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        if node.func.attr != "add_api_route":
            continue
        router_name = _expr_chain(node.func.value)
        sub_path = ""
        if node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
            sub_path = node.args[0].value
        ep_expr: ast.expr | None = node.args[1] if len(node.args) >= 2 else None
        methods: list[str] = []
        dep_exprs: list[ast.expr] = []
        for kw in node.keywords:
            if kw.arg == "path" and isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, str):
                sub_path = kw.value.value
            elif kw.arg == "endpoint":
                ep_expr = kw.value
            elif kw.arg == "methods" and isinstance(kw.value, (ast.List, ast.Tuple, ast.Set)):
                methods = [
                    el.value.lower()
                    for el in kw.value.elts
                    if isinstance(el, ast.Constant) and isinstance(el.value, str)
                ]
            elif kw.arg == "dependencies":
                dep_exprs.append(kw.value)
        if not methods:
            methods = ["get"]
        full_path = prefixes.get(router_name, "") + sub_path
        imp_deps = _depends_targets(dep_exprs, mod, aliases, graph, reexports) if dep_exprs else set()
        ep_chain = _expr_chain(ep_expr) if ep_expr is not None else ""
        ep_qn = _resolve_callee(ep_chain, mod, aliases, graph, reexports) if ep_chain else ""
        for m in methods:
            routes.append((router_name, m, full_path, imp_deps, ep_qn, node.lineno))
    return routes


_STRING_TAINT_WRAPPER_METHODS = frozenset(
    {"strip", "lstrip", "rstrip", "lower", "upper", "title", "casefold", "replace", "removeprefix", "removesuffix", "encode"}
)
_ORM_SAFE_BUILDERS = frozenset({"select", "insert", "update", "delete", "or_", "and_", "not_"})
_ORM_CHAIN_METHODS = frozenset(
    {
        "where",
        "filter",
        "filter_by",
        "order_by",
        "group_by",
        "having",
        "join",
        "outerjoin",
        "options",
        "limit",
        "offset",
        "values",
        "returning",
        "select_from",
        "distinct",
        "cte",
        "subquery",
        "scalar_subquery",
        "correlate",
        "correlate_except",
        "with_for_update",
    }
)


def _check_tainted_sql_expr(expr: ast.AST, tainted_vars: set[str], aliases: dict[str, str] | None = None) -> bool:
    als = aliases or {}
    if isinstance(expr, ast.JoinedStr):
        return any(isinstance(v, ast.FormattedValue) for v in expr.values)
    if isinstance(expr, ast.BinOp) and isinstance(expr.op, (ast.Add, ast.Mod)):
        if not (isinstance(expr.left, ast.Constant) and isinstance(expr.right, ast.Constant)):
            return True
        return _check_tainted_sql_expr(expr.left, tainted_vars, als) or _check_tainted_sql_expr(expr.right, tainted_vars, als)
    if isinstance(expr, ast.IfExp):
        return _check_tainted_sql_expr(expr.body, tainted_vars, als) or _check_tainted_sql_expr(expr.orelse, tainted_vars, als)
    if isinstance(expr, ast.Subscript):
        return _check_tainted_sql_expr(expr.value, tainted_vars, als)
    if isinstance(expr, (ast.List, ast.Tuple, ast.Set)):
        return any(_check_tainted_sql_expr(el, tainted_vars, als) for el in expr.elts)
    if isinstance(expr, ast.Call):
        if isinstance(expr.func, ast.Attribute):
            m = expr.func.attr
            if m == "format":
                return True
            if m == "join":
                recv = expr.func.value
                recv_chain = _expr_chain(recv)
                if recv_chain in {"os.path", "posixpath", "ntpath"} or recv_chain.endswith(".path"):
                    return False
                if isinstance(recv, ast.Constant) and isinstance(recv.value, str):
                    for arg in expr.args:
                        if isinstance(arg, (ast.List, ast.Tuple, ast.Set)):
                            if any(not isinstance(el, ast.Constant) for el in arg.elts):
                                return True
                        else:
                            return True
                    return False
                if _check_tainted_sql_expr(recv, tainted_vars, als):
                    return True
                return any(_check_tainted_sql_expr(a, tainted_vars, als) for a in expr.args)
            if m in _STRING_TAINT_WRAPPER_METHODS:
                return _check_tainted_sql_expr(expr.func.value, tainted_vars, als) or any(
                    _check_tainted_sql_expr(a, tainted_vars, als) for a in expr.args
                )
            if m in _ORM_CHAIN_METHODS:
                return False
            resolved_attr = _resolve_symbol(_expr_chain(expr.func), als)
            if resolved_attr.startswith(("func.", "sqlalchemy.func.")):
                return False
            if resolved_attr.split(".")[-1] in {"text", "literal_column", "str"} or isinstance(expr.func.value, ast.Name):
                return any(_check_tainted_sql_expr(a, tainted_vars, als) for a in expr.args) or any(
                    _check_tainted_sql_expr(kw.value, tainted_vars, als) for kw in expr.keywords
                )
            return False
        resolved_call = _resolve_symbol(_expr_chain(expr.func), als)
        call_leaf = resolved_call.split(".")[-1] if resolved_call else ""
        if call_leaf in _ORM_SAFE_BUILDERS or resolved_call.startswith(("func.", "sqlalchemy.func.")):
            return False
        return any(_check_tainted_sql_expr(a, tainted_vars, als) for a in expr.args) or any(
            _check_tainted_sql_expr(kw.value, tainted_vars, als) for kw in expr.keywords
        )
    if isinstance(expr, ast.Name) and expr.id in tainted_vars:
        return True
    return False


def _iter_scope_dfs_nodes(stmts: list[ast.stmt]):
    """Yield AST nodes in deterministic DFS statement order without descending into nested defs/classes."""
    def _walk_node(n: ast.AST):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            return
        yield n
        for child in ast.iter_child_nodes(n):
            yield from _walk_node(child)

    for stmt in stmts:
        yield from _walk_node(stmt)


def _assign_targets_names(target: ast.AST) -> list[str]:
    if isinstance(target, ast.Name):
        return [target.id]
    if isinstance(target, (ast.Tuple, ast.List)):
        out: list[str] = []
        for el in target.elts:
            out.extend(_assign_targets_names(el))
        return out
    return []


def _scan_scope_sqli(rel: str, stmts: list[ast.stmt], aliases: dict[str, str] | None = None) -> list[Finding]:
    findings: list[Finding] = []
    als = aliases or {}
    tainted_vars: set[str] = set()
    dfs_nodes = list(_iter_scope_dfs_nodes(stmts))

    for _ in range(8):
        prev_count = len(tainted_vars)
        for node in dfs_nodes:
            if isinstance(node, ast.Assign) and _check_tainted_sql_expr(node.value, tainted_vars, als):
                for tgt in node.targets:
                    tainted_vars.update(_assign_targets_names(tgt))
            elif isinstance(node, ast.AnnAssign) and node.value and isinstance(node.target, ast.Name):
                if _check_tainted_sql_expr(node.value, tainted_vars, als):
                    tainted_vars.add(node.target.id)
            elif isinstance(node, ast.AugAssign) and isinstance(node.op, (ast.Add, ast.Mod)) and isinstance(node.target, ast.Name):
                if not isinstance(node.value, ast.Constant) or _check_tainted_sql_expr(node.value, tainted_vars, als):
                    tainted_vars.add(node.target.id)
        if len(tainted_vars) == prev_count:
            break

    sql_sink_leaves = SQL_SINK_NAMES | {"scalars", "scalar", "literal_column"}
    flagged_lines: set[int] = set()
    for node in dfs_nodes:
        if not isinstance(node, ast.Call):
            continue
        raw_chain = _expr_chain(node.func)
        resolved_fn = _resolve_symbol(raw_chain, als)
        leaf = (resolved_fn or raw_chain).split(".")[-1]
        if leaf not in sql_sink_leaves:
            continue
        sql_args: list[ast.expr] = []
        if node.args:
            sql_args.append(node.args[0])
        for kw in node.keywords:
            if kw.arg in {"text", "statement", "sql"}:
                sql_args.append(kw.value)
        for arg in sql_args:
            if _check_tainted_sql_expr(arg, tainted_vars, als) and node.lineno not in flagged_lines:
                flagged_lines.add(node.lineno)
                findings.append(
                    Finding(
                        "CRITICAL",
                        "SQLI_DYNAMIC",
                        f"{rel}:{node.lineno}",
                        f"Dynamic string construction passed to SQL sink {leaf}(); use bound parameters.",
                    )
                )
                break
    return findings


def _is_http_timeout_kw_valid(call: ast.Call) -> bool:
    t_kw = next((kw for kw in call.keywords if kw.arg == "timeout"), None)
    if t_kw is None:
        return False
    if isinstance(t_kw.value, ast.Constant) and t_kw.value.value is None:
        return False
    return True


def _has_explicit_none_timeout(call: ast.Call) -> bool:
    t_kw = next((kw for kw in call.keywords if kw.arg == "timeout"), None)
    return t_kw is not None and isinstance(t_kw.value, ast.Constant) and t_kw.value.value is None


def _node_has_abort_call(node: ast.AST) -> bool:
    return any(
        isinstance(sub, ast.Call) and isinstance(sub.func, ast.Attribute) and sub.func.attr == "abort"
        for sub in ast.walk(node)
    )


def _scope_calls_play_route_abort(
    scope_stmts: list[ast.stmt],
    receiver_src: str,
    parent_ctx: str | None,
    local_fns: dict[str, ast.FunctionDef | ast.AsyncFunctionDef],
    module_fns: dict[str, ast.FunctionDef | ast.AsyncFunctionDef],
    sink_lineno: int,
) -> bool:
    allowed_receivers = {receiver_src}
    if parent_ctx:
        allowed_receivers.add(parent_ctx)
    for node in _iter_scope_dfs_nodes(scope_stmts):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        if node.lineno > sink_lineno:
            continue
        if node.func.attr != "route":
            continue
        route_recv = ast.unparse(node.func.value) if hasattr(ast, "unparse") else _expr_chain(node.func.value)
        if route_recv not in allowed_receivers:
            continue
        handler_expr: ast.expr | None = node.args[1] if len(node.args) >= 2 else None
        if handler_expr is None:
            handler_expr = next((kw.value for kw in node.keywords if kw.arg == "handler"), None)
        if handler_expr is None:
            continue
        if _node_has_abort_call(handler_expr):
            return True
        if isinstance(handler_expr, ast.Name):
            cb = local_fns.get(handler_expr.id) or module_fns.get(handler_expr.id)
            if cb is not None and _node_has_abort_call(cb):
                return True
    return False


def _audit_scope_http_and_playwright(
    rel: str,
    stmts: list[ast.stmt],
    aliases: dict[str, str],
    has_pw_import: bool,
    module_fns: dict[str, ast.FunctionDef | ast.AsyncFunctionDef],
    inherited_clients: dict[str, tuple[str, bool]] | None = None,
) -> list[Finding]:
    findings: list[Finding] = []
    local_fns: dict[str, ast.FunctionDef | ast.AsyncFunctionDef] = {
        s.name: s for s in stmts if isinstance(s, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    dfs_nodes = list(_iter_scope_dfs_nodes(stmts))
    http_clients: dict[str, tuple[str, bool]] = dict(inherited_clients or {})
    pw_page_parent: dict[str, str] = {}

    def _record_client_binding(tgt_node: ast.AST, call_node: ast.Call) -> None:
        resolved_ctor = _resolve_symbol(_expr_chain(call_node.func), aliases)
        names = _assign_targets_names(tgt_node)
        chain_tgt = _expr_chain(tgt_node)
        if chain_tgt and chain_tgt not in names and "." in chain_tgt:
            names.append(chain_tgt)
        if resolved_ctor in {"httpx.Client", "httpx.AsyncClient", "aiohttp.ClientSession"}:
            to_valid = _is_http_timeout_kw_valid(call_node)
            for key in names:
                http_clients[key] = (resolved_ctor, to_valid)
        elif resolved_ctor == "requests.Session":
            for key in names:
                http_clients[key] = (resolved_ctor, False)
        elif isinstance(call_node.func, ast.Attribute) and call_node.func.attr == "new_page":
            parent_src = ast.unparse(call_node.func.value) if hasattr(ast, "unparse") else _expr_chain(call_node.func.value)
            for key in names:
                pw_page_parent[key] = parent_src

    def _check_call(node: ast.Call, flagged_lines: set[tuple[str, int]]) -> None:
        chain = _expr_chain(node.func)
        resolved = _resolve_symbol(chain, aliases)
        leaf = chain.split(".")[-1] if chain else ""

        if resolved in {"httpx.Client", "httpx.AsyncClient", "aiohttp.ClientSession"} and _has_explicit_none_timeout(node):
            if ("SSRF_UNGUARDED_HTTP", node.lineno) not in flagged_lines:
                flagged_lines.add(("SSRF_UNGUARDED_HTTP", node.lineno))
                findings.append(
                    Finding("HIGH", "SSRF_UNGUARDED_HTTP", f"{rel}:{node.lineno}", f"{resolved}(timeout=None) disables outbound HTTP timeout.")
                )

        if resolved in {
            "urllib.request.urlopen",
            "requests.get",
            "requests.post",
            "requests.put",
            "requests.patch",
            "requests.delete",
            "requests.head",
            "requests.request",
            "httpx.get",
            "httpx.post",
            "httpx.put",
            "httpx.patch",
            "httpx.delete",
            "httpx.head",
            "httpx.request",
        }:
            if not _is_http_timeout_kw_valid(node) and ("SSRF_UNGUARDED_HTTP", node.lineno) not in flagged_lines:
                flagged_lines.add(("SSRF_UNGUARDED_HTTP", node.lineno))
                findings.append(
                    Finding(
                        "HIGH",
                        "SSRF_UNGUARDED_HTTP",
                        f"{rel}:{node.lineno}",
                        f"Outbound HTTP call {resolved}() missing explicit non-None timeout= / host allowlist.",
                    )
                )

        if isinstance(node.func, ast.Attribute) and node.func.attr in HTTP_CLIENT_METHODS - {"urlopen"}:
            recv_chain = _expr_chain(node.func.value)
            if recv_chain and recv_chain in http_clients:
                _, client_has_to = http_clients[recv_chain]
                if _has_explicit_none_timeout(node) or not (client_has_to or _is_http_timeout_kw_valid(node)):
                    if ("SSRF_UNGUARDED_HTTP", node.lineno) not in flagged_lines:
                        flagged_lines.add(("SSRF_UNGUARDED_HTTP", node.lineno))
                        findings.append(
                            Finding(
                                "HIGH",
                                "SSRF_UNGUARDED_HTTP",
                                f"{rel}:{node.lineno}",
                                f"HTTP client call `{recv_chain}.{node.func.attr}()` missing explicit non-None timeout=.",
                            )
                        )
            elif isinstance(node.func.value, ast.Call):
                inner_res = _resolve_symbol(_expr_chain(node.func.value.func), aliases)
                if inner_res in {"requests.Session", "httpx.Client", "httpx.AsyncClient", "aiohttp.ClientSession"}:
                    inner_to = (inner_res != "requests.Session") and _is_http_timeout_kw_valid(node.func.value)
                    if _has_explicit_none_timeout(node) or not (inner_to or _is_http_timeout_kw_valid(node)):
                        if ("SSRF_UNGUARDED_HTTP", node.lineno) not in flagged_lines:
                            flagged_lines.add(("SSRF_UNGUARDED_HTTP", node.lineno))
                            findings.append(
                                Finding(
                                    "HIGH",
                                    "SSRF_UNGUARDED_HTTP",
                                    f"{rel}:{node.lineno}",
                                    f"Chained `{inner_res}().{node.func.attr}()` missing explicit non-None timeout=.",
                                )
                            )

        if has_pw_import and isinstance(node.func, ast.Attribute) and leaf in {"set_content", "goto"}:
            recv_src = ast.unparse(node.func.value) if hasattr(ast, "unparse") else _expr_chain(node.func.value)
            parent_ctx = pw_page_parent.get(recv_src)
            if not _scope_calls_play_route_abort(stmts, recv_src, parent_ctx, local_fns, module_fns, node.lineno):
                if ("PLAYWRIGHT_NO_SSRF_GUARD", node.lineno) not in flagged_lines:
                    flagged_lines.add(("PLAYWRIGHT_NO_SSRF_GUARD", node.lineno))
                    findings.append(
                        Finding(
                            "HIGH",
                            "PLAYWRIGHT_NO_SSRF_GUARD",
                            f"{rel}:{node.lineno}",
                            f"Playwright `{recv_src}.{leaf}()` lacks matching preceding `.route()` handler calling `route.abort()`.",
                        )
                    )

    def _collect_class_body_clients(cls_node: ast.ClassDef) -> dict[str, tuple[str, bool]]:
        out: dict[str, tuple[str, bool]] = {}
        for sub_stmt in cls_node.body:
            pairs_cls: list[tuple[ast.AST, ast.Call]] = []
            if isinstance(sub_stmt, ast.Assign) and isinstance(sub_stmt.value, ast.Call):
                for tgt in sub_stmt.targets:
                    pairs_cls.append((tgt, sub_stmt.value))
            elif isinstance(sub_stmt, ast.AnnAssign) and isinstance(sub_stmt.value, ast.Call):
                pairs_cls.append((sub_stmt.target, sub_stmt.value))
            for tgt, call_v in pairs_cls:
                res = _resolve_symbol(_expr_chain(call_v.func), aliases)
                if res in {"httpx.Client", "httpx.AsyncClient", "aiohttp.ClientSession", "requests.Session"}:
                    to_ok = (res != "requests.Session") and _is_http_timeout_kw_valid(call_v)
                    for nm in _assign_targets_names(tgt):
                        out[f"self.{nm}"] = (res, to_ok)
                        out[f"cls.{nm}"] = (res, to_ok)
                        out[f"{cls_node.name}.{nm}"] = (res, to_ok)
        return out

    def _iter_immediate_child_defs(body: list[ast.stmt]):
        for s in body:
            if isinstance(s, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                yield s
            else:
                for child in ast.iter_child_nodes(s):
                    if isinstance(child, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                        yield child
                    elif isinstance(child, ast.stmt):
                        yield from _iter_immediate_child_defs([child])

    for child_def in _iter_immediate_child_defs(stmts):
        if isinstance(child_def, ast.ClassDef):
            for k, v in _collect_class_body_clients(child_def).items():
                if k.startswith(f"{child_def.name}."):
                    http_clients[k] = v

    flagged_lines: set[tuple[str, int]] = set()
    for node in dfs_nodes:
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call):
            for tgt in node.targets:
                _record_client_binding(tgt, node.value)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.value, ast.Call):
            _record_client_binding(node.target, node.value)
        elif isinstance(node, (ast.With, ast.AsyncWith)):
            for item in node.items:
                if isinstance(item.context_expr, ast.Call) and item.optional_vars is not None:
                    _record_client_binding(item.optional_vars, item.context_expr)
        elif isinstance(node, ast.Call):
            _check_call(node, flagged_lines)

    nested_fn_pool = dict(module_fns)
    nested_fn_pool.update(local_fns)

    for stmt in _iter_immediate_child_defs(stmts):
        if isinstance(stmt, ast.ClassDef):
            class_clients = dict(http_clients)
            class_clients.update(_collect_class_body_clients(stmt))
            for mnode in stmt.body:
                if isinstance(mnode, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    for sub in _iter_scope_dfs_nodes(mnode.body):
                        pairs: list[tuple[ast.AST, ast.Call]] = []
                        if isinstance(sub, ast.Assign) and isinstance(sub.value, ast.Call):
                            for tgt in sub.targets:
                                pairs.append((tgt, sub.value))
                        elif isinstance(sub, ast.AnnAssign) and isinstance(sub.value, ast.Call):
                            pairs.append((sub.target, sub.value))
                        for tgt, call_v in pairs:
                            res = _resolve_symbol(_expr_chain(call_v.func), aliases)
                            if res in {"httpx.Client", "httpx.AsyncClient", "aiohttp.ClientSession", "requests.Session"}:
                                to_ok = (res != "requests.Session") and _is_http_timeout_kw_valid(call_v)
                                ch = _expr_chain(tgt)
                                if ch.startswith(("self.", "cls.")):
                                    class_clients[ch] = (res, to_ok)
            findings.extend(_audit_scope_http_and_playwright(rel, stmt.body, aliases, has_pw_import, nested_fn_pool, class_clients))
        elif isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
            findings.extend(_audit_scope_http_and_playwright(rel, stmt.body, aliases, has_pw_import, nested_fn_pool, http_clients))

    return findings


def _strip_api_prefix(route_path: str) -> str:
    if route_path == "/api":
        return "/"
    if route_path.startswith("/api/"):
        return route_path[4:]
    return route_path


def _path_matches_prefix(path: str, prefix: str) -> bool:
    return path == prefix or path.startswith(prefix + "/")


def scan_python_source(
    rel: str,
    text: str,
    call_graph: dict[str, FunctionBehavior] | None = None,
    router_mounts: dict[str, tuple[str, set[str]]] | None = None,
    reexports: dict[str, str] | None = None,
) -> list[Finding]:
    """Audit a single Python source string (used by both full SAST and PostToolUse tripwire)."""
    findings: list[Finding] = []
    lines = text.splitlines()
    graph = call_graph or {}

    try:
        tree = ast.parse(text, filename=rel)
    except SyntaxError as exc:
        return [Finding("CRITICAL", "PY_SYNTAX", f"{rel}:{exc.lineno or 1}", f"Syntax error: {exc.msg}")]

    mod = rel[len("backend/"):] if rel.startswith("backend/") else rel
    is_pkg = mod.endswith("/__init__.py") or mod == "__init__.py"
    if mod.endswith("/__init__.py"):
        mod = mod[: -len("/__init__.py")].replace("/", ".")
    elif mod.endswith(".py"):
        mod = mod[:-3].replace("/", ".")

    aliases = _extract_aliases(tree, mod, is_package=is_pkg)
    prefixes, router_deps, local_edges = _extract_router_metadata(tree, mod, aliases, graph, reexports)
    imperative_routes = _extract_imperative_routes(tree, prefixes, mod, aliases, graph, reexports)
    has_route_decs = bool(imperative_routes) or any(
        isinstance(dec, ast.Call)
        and isinstance(dec.func, ast.Attribute)
        and dec.func.attr.lower() in {"get", "post", "put", "patch", "delete", "api_route"}
        for fn in ast.walk(tree)
        if isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef))
        for dec in fn.decorator_list
    )
    is_router = rel.startswith("backend/app/api/") or (
        rel.startswith("backend/app/") and (bool(prefixes) or has_route_decs)
    )
    is_cli = rel == "backend/app/cli.py" or rel.startswith(("commands/", ".agents/"))
    is_financial = any(k in rel for k in FINANCIAL_MODULES)
    is_formula_ast = "formula_evaluator" in rel or "road_tax" in rel

    has_pw_import = any("playwright" in v for v in aliases.values()) or any(
        (isinstance(n, ast.Import) and any("playwright" in a.name for a in n.names))
        or (isinstance(n, ast.ImportFrom) and n.module and "playwright" in n.module)
        for n in ast.walk(tree)
    )
    module_fns: dict[str, ast.FunctionDef | ast.AsyncFunctionDef] = {
        s.name: s for s in tree.body if isinstance(s, (ast.FunctionDef, ast.AsyncFunctionDef))
    } if isinstance(tree, ast.Module) else {}

    if isinstance(tree, ast.Module):
        findings.extend(_audit_scope_http_and_playwright(rel, tree.body, aliases, has_pw_import, module_fns))
        findings.extend(_scan_scope_sqli(rel, tree.body, aliases))
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            findings.extend(_scan_scope_sqli(rel, node.body, aliases))

    code_exec_seen: set[tuple[str, int]] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and isinstance(node.ctx, ast.Load):
            res_attr = _resolve_symbol(_expr_chain(node), aliases)
            if is_formula_ast and res_attr in {"ast.Pow", "operator.pow"}:
                findings.append(
                    Finding(
                        "HIGH",
                        "FORMULA_POW_DOS",
                        f"{rel}:{node.lineno}",
                        f"Exponentiation ({res_attr}) in formula evaluator allows CPU/memory DoS (e.g. 9**9**9**9).",
                    )
                )
            elif res_attr in {"eval", "exec", "builtins.eval", "builtins.exec", "__builtins__.eval", "__builtins__.exec"}:
                rule_key = f"NO_{res_attr.split('.')[-1].upper()}"
                if (rule_key, node.lineno) not in code_exec_seen:
                    code_exec_seen.add((rule_key, node.lineno))
                    findings.append(Finding("CRITICAL", rule_key, f"{rel}:{node.lineno}", f"Banned {res_attr} reference/call."))
        if isinstance(node, ast.Subscript):
            base_src = ast.unparse(node.value) if hasattr(ast, "unparse") else ""
            slice_src = ast.unparse(node.slice) if hasattr(ast, "unparse") else ""
            if "__builtins__" in base_src and ("eval" in slice_src or "exec" in slice_src):
                findings.append(Finding("CRITICAL", "NO_EVAL_ALIAS", f"{rel}:{node.lineno}", "Obfuscated __builtins__ eval/exec lookup."))

        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
            res_name = _resolve_symbol(node.id, aliases)
            if res_name in {"eval", "exec", "builtins.eval", "builtins.exec"}:
                rule_key = f"NO_{res_name.split('.')[-1].upper()}"
                if (rule_key, node.lineno) not in code_exec_seen:
                    code_exec_seen.add((rule_key, node.lineno))
                    findings.append(Finding("CRITICAL", rule_key, f"{rel}:{node.lineno}", f"Banned {res_name} reference/call."))
        elif isinstance(node, ast.Call):
            chain = _expr_chain(node.func)
            resolved = _resolve_symbol(chain, aliases)
            leaf = chain.split(".")[-1] if chain else ""

            if resolved in {"eval", "exec", "builtins.eval", "builtins.exec", "__builtins__.eval", "__builtins__.exec"}:
                rule_key = f"NO_{resolved.split('.')[-1].upper()}"
                if (rule_key, node.lineno) not in code_exec_seen:
                    code_exec_seen.add((rule_key, node.lineno))
                    findings.append(Finding("CRITICAL", rule_key, f"{rel}:{node.lineno}", f"Banned {resolved}() execution sink."))
            elif resolved in {"__import__", "builtins.__import__"}:
                findings.append(Finding("CRITICAL", "NO_DUNDER_IMPORT", f"{rel}:{node.lineno}", "Dynamic __import__() bypass banned; use static imports."))
            elif leaf == "getattr" and len(node.args) >= 2 and isinstance(node.args[1], ast.Constant) and node.args[1].value in {"eval", "exec", "compile", "system", "__import__"}:
                findings.append(Finding("CRITICAL", "NO_GETATTR_EXEC", f"{rel}:{node.lineno}", f"Dynamic getattr(..., '{node.args[1].value}') code execution bypass."))
            elif resolved in {"os.system", "os.popen"} or resolved.startswith(("os.spawn", "os.exec")):
                findings.append(Finding("CRITICAL", "NO_OS_EXEC", f"{rel}:{node.lineno}", f"Banned OS execution sink {resolved}()."))
            elif resolved in {
                "pickle.load",
                "pickle.loads",
                "_pickle.load",
                "_pickle.loads",
                "cPickle.load",
                "cPickle.loads",
                "marshal.load",
                "marshal.loads",
                "shelve.open",
                "dill.load",
                "dill.loads",
                "jsonpickle.decode",
                "cloudpickle.loads",
            }:
                findings.append(Finding("CRITICAL", "UNSAFE_DESERIALIZATION", f"{rel}:{node.lineno}", f"Insecure deserialization {resolved}()."))
            elif resolved in {"yaml.unsafe_load", "yaml.unsafe_load_all", "yaml.full_load", "yaml.full_load_all"}:
                findings.append(Finding("CRITICAL", "UNSAFE_YAML", f"{rel}:{node.lineno}", f"{resolved}() allows arbitrary object execution; use yaml.safe_load()."))
            elif resolved in {"yaml.load", "yaml.load_all"}:
                loader_kw = next((kw for kw in node.keywords if kw.arg == "Loader"), None)
                loader_node = loader_kw.value if loader_kw else (node.args[1] if len(node.args) >= 2 else None)
                loader_src = ast.unparse(loader_node) if (loader_node and hasattr(ast, "unparse")) else ""
                if "SafeLoader" not in loader_src and "CSafeLoader" not in loader_src:
                    findings.append(Finding("CRITICAL", "UNSAFE_YAML", f"{rel}:{node.lineno}", "yaml.load() without SafeLoader allows arbitrary object execution."))
            elif resolved in {"compile", "builtins.compile"}:
                findings.append(Finding("HIGH", "NO_COMPILE", f"{rel}:{node.lineno}", "Dynamic compile() code generation requires review."))
            elif leaf == "float":
                call_src = ast.unparse(node) if hasattr(ast, "unparse") else ""
                money_hint = re.search(r"(?:amount|price|fee|rate|prem|roadtax|road_tax|sum|commission|total|cost)", call_src, re.IGNORECASE)
                if is_financial or (is_router and money_hint):
                    findings.append(Finding("HIGH", "FLOAT_MONEY", f"{rel}:{node.lineno}", "float() in monetary/actuarial path; migrate to Decimal."))
            elif leaf == "print" and not is_cli:
                findings.append(Finding("MEDIUM", "STDOUT_PRINT", f"{rel}:{node.lineno}", "Raw print() in production app code; use structured logger."))
            elif leaf == "timedelta":
                for kw in node.keywords:
                    if kw.arg == "days" and isinstance(kw.value, ast.Constant) and kw.value.value in {364, 365}:
                        findings.append(Finding("HIGH", "LEAP_YEAR_DAYS", f"{rel}:{node.lineno}", f"timedelta(days={kw.value.value}) breaks on leap years; use relativedelta."))

            for kw in node.keywords:
                if kw.arg == "shell" and isinstance(kw.value, ast.Constant) and bool(kw.value.value):
                    findings.append(Finding("CRITICAL", "SHELL_TRUE", f"{rel}:{node.lineno}", "Subprocess truthy shell= banned."))

    # Check SSRF / Windscreen HTTP scraper calls from pricing/formula modules
    if is_formula_ast:
        for imp in ast.walk(tree):
            if isinstance(imp, ast.ImportFrom) and imp.module and "windscreen_scraper" in imp.module:
                findings.append(Finding("HIGH", "SSRF_IN_FORMULA", f"{rel}:{imp.lineno}", "Formula evaluator triggers live external HTTP scraper; move to seeded DB table."))

    # Router RBAC, auth, untyped payloads, and mutating GET verification
    if is_router and call_graph is not None:
        effective_mounts = dict(router_mounts or {})
        if router_mounts is None and local_edges:
            for _ in range(4):
                for parent_key, child_key, m_pref, m_deps in local_edges:
                    p_var = parent_key.split(".")[-1]
                    p_inh_pref, p_inh_deps = effective_mounts.get(parent_key, ("", set()))
                    p_pref = p_inh_pref + prefixes.get(p_var, "") + m_pref
                    p_deps = p_inh_deps | set(router_deps.get(p_var, set())) | m_deps
                    effective_mounts[child_key] = (p_pref, p_deps)

        qns_to_nodes: dict[str, ast.FunctionDef | ast.AsyncFunctionDef] = dict(_iter_functions_with_qualname(tree, mod))

        def _evaluate_route_binding(
            router_var: str,
            method: str,
            raw_route_path: str,
            dec_deps: set[str],
            beh: FunctionBehavior,
            fn_node: ast.FunctionDef | ast.AsyncFunctionDef | None,
            line_no: int,
        ) -> None:
            resolved_router_sym = _resolve_symbol(router_var, aliases) if router_var else ""
            if resolved_router_sym and "." not in resolved_router_sym:
                resolved_router_sym = f"{mod}.{resolved_router_sym}"
            elif not resolved_router_sym and router_var:
                resolved_router_sym = f"{mod}.{router_var}"
            if reexports and resolved_router_sym:
                resolved_router_sym = _resolve_reexport_chain(resolved_router_sym, reexports)
            mount_pref, mount_deps = effective_mounts.get(
                resolved_router_sym,
                effective_mounts.get(f"{mod}.{router_var}", ("", set())),
            )
            route_path = mount_pref + raw_route_path
            if not route_path:
                return
            check_path = _strip_api_prefix(route_path)
            if any(_path_matches_prefix(check_path, p) for p in AUTH_SKIP_PREFIXES):
                return

            dep_calls = set(beh.calls or set()) | router_deps.get(router_var, set()) | mount_deps | dec_deps
            eff_beh = FunctionBehavior(
                admin_rbac=beh.admin_rbac or any(d.split(".")[-1] in ADMIN_GUARD_NAMES for d in dep_calls),
                business_rbac=beh.business_rbac or any(d.split(".")[-1] in BUSINESS_GUARD_NAMES for d in dep_calls),
                has_auth=(
                    beh.has_auth
                    or beh.admin_rbac
                    or beh.business_rbac
                    or any(d.split(".")[-1] in (AUTH_DEP_NAMES | ADMIN_GUARD_NAMES | BUSINESS_GUARD_NAMES) for d in dep_calls)
                ),
                direct_commit=beh.direct_commit,
                calls=dep_calls,
                has_untyped_payload=beh.has_untyped_payload,
            )
            is_admin_path = any(_path_matches_prefix(check_path, p) for p in ADMIN_ROUTE_PREFIXES)
            is_sensitive_path = any(_path_matches_prefix(check_path, p) for p in SENSITIVE_ROUTE_PREFIXES)
            has_route_auth = (
                _transitive_flag(eff_beh, graph, "has_auth", depth=4)
                or _transitive_flag(eff_beh, graph, "business_rbac", depth=4)
                or _transitive_flag(eff_beh, graph, "admin_rbac", depth=4)
            )
            untyped_payload = _has_untyped_dict_payload(fn_node) if fn_node is not None else beh.has_untyped_payload

            if not has_route_auth:
                findings.append(
                    Finding(
                        "CRITICAL",
                        "MISSING_RBAC",
                        f"{rel}:{line_no}",
                        f"Unauthenticated {method.upper()} {route_path} lacks session authentication dependency.",
                    )
                )
            elif is_admin_path and method in {"get", "post", "put", "patch", "delete"}:
                if not _transitive_flag(eff_beh, graph, "admin_rbac", depth=4):
                    findings.append(
                        Finding(
                            "CRITICAL",
                            "MISSING_RBAC",
                            f"{rel}:{line_no}",
                            f"Privileged {method.upper()} {route_path} lacks admin-tier RBAC guard in router/dependencies/services.",
                        )
                    )
                if method in {"post", "put", "patch"} and untyped_payload:
                    findings.append(
                        Finding(
                            "HIGH",
                            "UNTYPED_ADMIN_PAYLOAD",
                            f"{rel}:{line_no}",
                            f"Mutating {method.upper()} {route_path} accepts untyped/dict/raw payload instead of bounded Pydantic schema.",
                        )
                    )
            elif is_sensitive_path and method in {"post", "put", "patch", "delete"}:
                if not _transitive_flag(eff_beh, graph, "business_rbac", depth=4):
                    findings.append(
                        Finding(
                            "CRITICAL",
                            "MISSING_RBAC",
                            f"{rel}:{line_no}",
                            f"Mutating {method.upper()} {route_path} has no RBAC guard in router or service helpers.",
                        )
                    )

            if method == "get" and _transitive_flag(eff_beh, graph, "direct_commit", depth=4):
                findings.append(
                    Finding(
                        "HIGH",
                        "MUTATING_GET",
                        f"{rel}:{line_no}",
                        f"GET {route_path} mutates DB state (commit/flush/DML directly or via service); GET endpoints must stay read-only.",
                    )
                )

        for qn, fn_node in qns_to_nodes.items():
            beh = graph.get(qn) or _analyze_function_node(fn_node, mod, aliases, graph, reexports)
            for dec in fn_node.decorator_list:
                if not isinstance(dec, ast.Call):
                    continue
                for router_var, method, raw_route_path, dec_deps in _extract_route_decorator(dec, prefixes, mod, aliases, graph, reexports):
                    _evaluate_route_binding(router_var, method, raw_route_path, dec_deps, beh, fn_node, fn_node.lineno)

        for router_var, method, raw_route_path, imp_deps, ep_qn, line_no in imperative_routes:
            ep_fn_node = qns_to_nodes.get(ep_qn)
            beh = graph.get(ep_qn) or (
                _analyze_function_node(ep_fn_node, mod, aliases, graph, reexports)
                if ep_fn_node is not None
                else FunctionBehavior(calls=set())
            )
            _evaluate_route_binding(router_var, method, raw_route_path, imp_deps, beh, ep_fn_node, line_no)

    # Secrets, PII, NRIC, deprecated Gemini & storage bypass scans
    flagged_lines: set[tuple[str, int]] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            val = node.value
            if NRIC_RE.search(val):
                ln = getattr(node, "lineno", 1)
                if ("NRIC_OR_PII", ln) not in flagged_lines:
                    flagged_lines.add(("NRIC_OR_PII", ln))
                    findings.append(Finding("HIGH", "PII_OR_SECRET", f"{rel}:{ln}", "Hardcoded Malaysian NRIC literal in Python source."))

    for idx, line in enumerate(lines, 1):
        if PII_SECRET_RE.search(line) and ("NRIC_OR_PII", idx) not in flagged_lines:
            findings.append(Finding("HIGH", "PII_OR_SECRET", f"{rel}:{idx}", "Hardcoded PII/bank/credential literal detected."))
        if DEPRECATED_GEMINI_RE.search(line):
            findings.append(Finding("HIGH", "DEPRECATED_GEMINI", f"{rel}:{idx}", "Deprecated or shutdown Gemini model string detected."))
        if not rel.startswith(("commands/", ".agents/")) and "config" not in rel and (("stateless_" "generated") in line or ("local_" "ephemeral") in line):
            findings.append(Finding("CRITICAL", "STORAGE_BYPASS", f"{rel}:{idx}", "Ephemeral stateless/local PDF storage fallback violates durable Supabase Storage invariant."))

    if any(rel.startswith(p) for p in MONOLITH_PY_PREFIXES) and len(lines) > 600:
        findings.append(Finding("MEDIUM", "MONOLITH_PY", f"{rel}:1", f"Python module is {len(lines)} lines (>600 line budget); decompose into cohesive slices."))

    return findings


_JS_REGEX_KEYWORDS = frozenset(
    {"return", "typeof", "void", "delete", "throw", "in", "of", "case", "else", "await", "yield", "new"}
)


def _strip_ts_comments_preserving_lines(text: str) -> str:
    """Linear lexer stripping // and /* */ comments while preserving lines, strings, templates, JSX tags & /regex/ literals."""
    out: list[str] = []
    i = 0
    n = len(text)
    regex_allowed = True
    prev_was_dot = False
    template_brace_stack: list[int] = []

    def _scan_template_literal(start_idx: int) -> int:
        out.append("`")
        j = start_idx + 1
        while j < n:
            ch = text[j]
            if ch == "\\" and j + 1 < n:
                out.append(text[j : j + 2])
                j += 2
                continue
            if ch == "`":
                out.append("`")
                return j + 1
            if ch == "$" and j + 1 < n and text[j + 1] == "{":
                out.append("${")
                template_brace_stack.append(0)
                return j + 2
            out.append(ch)
            j += 1
        return n

    while i < n:
        ch = text[i]

        if ch in " \t\r\n":
            out.append(ch)
            i += 1
            continue

        if ch == "/" and i + 1 < n:
            nxt = text[i + 1]
            if nxt == "/":
                j = i + 2
                while j < n and text[j] != "\n":
                    j += 1
                out.append(" ")
                i = j
                continue
            if nxt == "*":
                j = i + 2
                end = text.find("*/", j)
                if end == -1:
                    nl_count = text[j:].count("\n")
                    out.append(" " + ("\n" * nl_count))
                    i = n
                else:
                    nl_count = text[j:end].count("\n")
                    out.append(" " + ("\n" * nl_count))
                    i = end + 2
                continue

            # Regular expression literal only in regex-start positions (never TSX `/>` self-close)
            is_jsx_self_close = nxt == ">" and (i + 2 >= n or text[i + 2] in " \t\r\n},;)<")
            if regex_allowed and not is_jsx_self_close:
                j = i + 1
                in_class = False
                closed = False
                while j < n:
                    rc = text[j]
                    if rc in "\r\n":
                        break
                    if rc == "\\" and j + 1 < n and text[j + 1] not in "\r\n":
                        j += 2
                        continue
                    if rc == "[" and not in_class:
                        in_class = True
                    elif rc == "]" and in_class:
                        in_class = False
                    elif rc == "/" and not in_class:
                        k = j + 1
                        while k < n and text[k].isalpha():
                            k += 1
                        out.append(text[i:k])
                        i = k
                        closed = True
                        regex_allowed = False
                        prev_was_dot = False
                        break
                    j += 1
                if closed:
                    continue

            out.append("/")
            i += 1
            regex_allowed = True
            prev_was_dot = False
            continue

        if ch in ('"', "'"):
            quote = ch
            j = i + 1
            while j < n:
                sc = text[j]
                if sc == "\\" and j + 1 < n:
                    j += 2
                    continue
                if sc == quote:
                    j += 1
                    break
                j += 1
            out.append(text[i:j])
            i = j
            regex_allowed = False
            prev_was_dot = False
            continue

        if ch == "`":
            i = _scan_template_literal(i)
            regex_allowed = bool(template_brace_stack and template_brace_stack[-1] == 0)
            prev_was_dot = False
            continue

        if ch == "<" and i + 1 < n and text[i + 1] == "/":
            out.append("</")
            i += 2
            regex_allowed = False
            prev_was_dot = False
            continue

        if ch == "{":
            if template_brace_stack:
                template_brace_stack[-1] += 1
            out.append(ch)
            i += 1
            regex_allowed = True
            prev_was_dot = False
            continue

        if ch == "}":
            if template_brace_stack:
                if template_brace_stack[-1] == 0:
                    template_brace_stack.pop()
                    out.append("}")
                    i = _scan_template_literal(i)
                    regex_allowed = bool(template_brace_stack and template_brace_stack[-1] == 0)
                    prev_was_dot = False
                    continue
                template_brace_stack[-1] -= 1
            out.append(ch)
            i += 1
            regex_allowed = True
            prev_was_dot = False
            continue

        if ch.isalpha() or ch in ("_", "$"):
            j = i + 1
            while j < n and (text[j].isalnum() or text[j] in ("_", "$")):
                j += 1
            ident = text[i:j]
            out.append(ident)
            regex_allowed = (not prev_was_dot) and (ident in _JS_REGEX_KEYWORDS)
            prev_was_dot = False
            i = j
            continue

        if ch.isdigit():
            j = i + 1
            while j < n and (text[j].isalnum() or text[j] in (".", "_")):
                j += 1
            out.append(text[i:j])
            regex_allowed = False
            prev_was_dot = False
            i = j
            continue

        out.append(ch)
        if ch == ".":
            regex_allowed = False
            prev_was_dot = True
        elif ch in (")", "]"):
            regex_allowed = False
            prev_was_dot = False
        elif ch in "([,:=!&|?~^%*+-<>;" or ch == "/":
            regex_allowed = True
            prev_was_dot = False
        else:
            prev_was_dot = False
        i += 1

    return "".join(out)


def _line_of_offset(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def _decode_quoted_js_strings(raw_block: str) -> list[str]:
    entries: list[str] = []
    i = 0
    n = len(raw_block)
    while i < n:
        ch = raw_block[i]
        if ch in ('"', "'", "`"):
            quote = ch
            i += 1
            buf: list[str] = []
            while i < n:
                cur = raw_block[i]
                if cur == "\\" and i + 1 < n:
                    nxt = raw_block[i + 1]
                    if nxt in ("\\", '"', "'", "`", "/"):
                        buf.append(nxt)
                    else:
                        buf.append(cur)
                        buf.append(nxt)
                    i += 2
                    continue
                if cur == quote:
                    i += 1
                    break
                buf.append(cur)
                i += 1
            entries.append("".join(buf))
        else:
            i += 1
    return entries


def _extract_middleware_matcher_entries(mw_code: str) -> tuple[bool, list[str]]:
    m = re.search(r"\bmatcher\s*:\s*", mw_code)
    if not m:
        return False, []
    i = m.end()
    n = len(mw_code)
    while i < n and mw_code[i].isspace():
        i += 1
    if i >= n:
        return False, []
    if mw_code[i] in ('"', "'", "`"):
        return True, _decode_quoted_js_strings(mw_code[i:])[:1]
    if mw_code[i] != "[":
        return False, []

    depth = 1
    in_quote: str | None = None
    start = i + 1
    i += 1
    while i < n and depth > 0:
        ch = mw_code[i]
        if in_quote:
            if ch == "\\" and i + 1 < n:
                i += 2
                continue
            if ch == in_quote:
                in_quote = None
        else:
            if ch in ('"', "'", "`"):
                in_quote = ch
            elif ch == "[":
                depth += 1
            elif ch == "]":
                depth -= 1
                if depth == 0:
                    return True, _decode_quoted_js_strings(mw_code[start:i])
        i += 1
    return False, []


def _split_top_level_regex_alts(body: str) -> list[str]:
    parts: list[str] = []
    paren = 0
    bracket = 0
    buf: list[str] = []
    i = 0
    n = len(body)
    while i < n:
        ch = body[i]
        if ch == "\\" and i + 1 < n:
            buf.append(ch)
            buf.append(body[i + 1])
            i += 2
            continue
        if bracket > 0:
            if ch == "]":
                bracket = 0
            buf.append(ch)
        elif ch == "[":
            bracket = 1
            buf.append(ch)
        elif ch == "(":
            paren += 1
            buf.append(ch)
        elif ch == ")":
            paren = max(0, paren - 1)
            buf.append(ch)
        elif ch == "|" and paren == 0:
            parts.append("".join(buf))
            buf.clear()
        else:
            buf.append(ch)
        i += 1
    parts.append("".join(buf))
    return parts


def _find_matching_paren(s: str, open_idx: int) -> int:
    if open_idx < 0 or open_idx >= len(s) or s[open_idx] != "(":
        return -1
    depth = 1
    in_class = False
    i = open_idx + 1
    n = len(s)
    while i < n:
        ch = s[i]
        if ch == "\\" and i + 1 < n:
            i += 2
            continue
        if in_class:
            if ch == "]":
                in_class = False
        elif ch == "[":
            in_class = True
        elif ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return -1


def _match_lookahead_alts_at(body: str, rem: str, steps: list[int], max_steps: int = 256) -> bool:
    """Bounded deterministic structural matcher for `(?!...)` regex bodies against a route remainder."""
    branches = _split_top_level_regex_alts(body)
    return any(_match_lookahead_seq(b.strip(), 0, rem, 0, steps, max_steps) for b in branches)


def _char_class_matches(spec: str, ch: str) -> bool:
    neg = spec.startswith("^")
    inner = spec[1:] if neg else spec
    matched = False
    i = 0
    while i < len(inner):
        if inner[i] == "\\" and i + 1 < len(inner):
            c = inner[i + 1]
            if (c == "s" and ch.isspace()) or (c == "d" and ch.isdigit()) or (c == "w" and (ch.isalnum() or ch == "_")) or c == ch:
                matched = True
            i += 2
            continue
        if i + 2 < len(inner) and inner[i + 1] == "-":
            if inner[i] <= ch <= inner[i + 2]:
                matched = True
            i += 3
            continue
        if inner[i] == ch:
            matched = True
        i += 1
    return (not matched) if neg else matched


def _match_lookahead_seq(seq: str, pi: int, rem: str, ri: int, steps: list[int], max_steps: int) -> bool:
    steps[0] += 1
    if steps[0] > max_steps:
        return True  # Fail-closed on overly complex exclusions

    n = len(seq)
    if pi < n and seq[pi] == "^":
        pi += 1

    while pi < n:
        ch = seq[pi]
        if ch == "$":
            if ri != len(rem):
                return False
            pi += 1
            continue

        if ch == "\\" and pi + 1 < n and seq[pi + 1] in ("b", "B"):
            is_prev_w = ri > 0 and (rem[ri - 1].isalnum() or rem[ri - 1] == "_")
            is_curr_w = ri < len(rem) and (rem[ri].isalnum() or rem[ri] == "_")
            is_boundary = is_prev_w != is_curr_w
            ok = is_boundary if seq[pi + 1] == "b" else (not is_boundary)
            if not ok:
                return False
            pi += 2
            continue

        if ch == "(":
            close_i = _find_matching_paren(seq, pi)
            if close_i == -1:
                return True
            inner = seq[pi + 1 : close_i]
            nxt_pi = close_i + 1
            optional = nxt_pi < n and seq[nxt_pi] == "?"
            if optional:
                nxt_pi += 1

            # Positive lookahead / boundary assertions like (?:/|$) or (?=/|$)
            if inner in {"?:/|$", "?:$|/", "?=/|$", "?=$|/"}:
                ok_boundary = ri == len(rem) or (ri < len(rem) and rem[ri] == "/")
                if ok_boundary:
                    pi = nxt_pi
                    continue
                if optional:
                    pi = nxt_pi
                    continue
                return False

            if inner.startswith("?="):
                la_body = inner[2:]
                if _match_lookahead_alts_at(la_body, rem[ri:], steps, max_steps):
                    pi = nxt_pi
                    continue
                return False if not optional else _match_lookahead_seq(seq, nxt_pi, rem, ri, steps, max_steps)

            if inner.startswith("?!"):
                la_body = inner[2:]
                if not _match_lookahead_alts_at(la_body, rem[ri:], steps, max_steps):
                    pi = nxt_pi
                    continue
                return False

            grp_body = inner[2:] if inner.startswith("?:") else inner
            grp_branches = _split_top_level_regex_alts(grp_body)
            tail = seq[nxt_pi:]
            for gb in grp_branches:
                if _match_lookahead_seq(gb.strip() + tail, 0, rem, ri, steps, max_steps):
                    return True
            if optional and _match_lookahead_seq(tail, 0, rem, ri, steps, max_steps):
                return True
            return False

        # Character class `[...]` with optional `*`/`+`/`?`
        if ch == "[":
            j = pi + 1
            while j < n:
                if seq[j] == "\\" and j + 1 < n:
                    j += 2
                    continue
                if seq[j] == "]":
                    break
                j += 1
            if j >= n:
                return True
            spec = seq[pi + 1 : j]
            q_idx = j + 1
            quant = seq[q_idx] if (q_idx < n and seq[q_idx] in "*+?") else ""
            nxt_pi = q_idx + (1 if quant else 0)
            if not quant:
                if ri >= len(rem) or not _char_class_matches(spec, rem[ri]):
                    return False
                pi = nxt_pi
                ri += 1
                continue
            max_k = 0
            while ri + max_k < len(rem) and _char_class_matches(spec, rem[ri + max_k]):
                max_k += 1
            min_k = 1 if quant == "+" else 0
            limit_k = min(max_k, 1) if quant == "?" else max_k
            if max_k < min_k:
                return False
            for k in range(limit_k, min_k - 1, -1):
                if _match_lookahead_seq(seq, nxt_pi, rem, ri + k, steps, max_steps):
                    return True
            return False

        # Wildcard `.` or escaped / literal single atom
        if ch == "\\" and pi + 1 < n:
            lit_ch = seq[pi + 1]
            atom_kind = "special" if lit_ch in {"s", "d", "w", "S", "D", "W"} else "lit"
            pi_after_atom = pi + 2
        elif ch == ".":
            lit_ch = "."
            atom_kind = "any"
            pi_after_atom = pi + 1
        else:
            lit_ch = ch
            atom_kind = "lit"
            pi_after_atom = pi + 1

        quant = seq[pi_after_atom] if (pi_after_atom < n and seq[pi_after_atom] in "*+?") else ""
        nxt_pi = pi_after_atom + (1 if quant else 0)

        def _atom_ok(c: str) -> bool:
            if atom_kind == "any":
                return True
            if atom_kind == "lit":
                return c == lit_ch
            if lit_ch == "s":
                return c.isspace()
            if lit_ch == "d":
                return c.isdigit()
            if lit_ch == "w":
                return c.isalnum() or c == "_"
            if lit_ch == "S":
                return not c.isspace()
            if lit_ch == "D":
                return not c.isdigit()
            return not (c.isalnum() or c == "_")

        if not quant:
            if ri >= len(rem) or not _atom_ok(rem[ri]):
                return False
            pi = nxt_pi
            ri += 1
            continue

        min_k = 1 if quant == "+" else 0
        if nxt_pi >= n:
            if min_k == 0:
                return True
            return ri < len(rem) and _atom_ok(rem[ri])
        max_k = 0
        while ri + max_k < len(rem) and _atom_ok(rem[ri + max_k]):
            max_k += 1
        limit_k = min(max_k, 1) if quant == "?" else max_k
        if max_k < min_k:
            return False
        for k in range(limit_k, min_k - 1, -1):
            if _match_lookahead_seq(seq, nxt_pi, rem, ri + k, steps, max_steps):
                return True
        return False

    # Prefix match succeeds once lookahead branch pattern finishes
    return True


def _split_matcher_segments(path_pattern: str) -> list[str]:
    cleaned = path_pattern.strip().lstrip("/")
    if not cleaned:
        return []
    segs: list[str] = []
    buf: list[str] = []
    paren = 0
    bracket = 0
    i = 0
    n = len(cleaned)
    while i < n:
        ch = cleaned[i]
        if ch == "\\" and i + 1 < n:
            buf.append(ch)
            buf.append(cleaned[i + 1])
            i += 2
            continue
        if bracket:
            if ch == "]":
                bracket = 0
            buf.append(ch)
        elif ch == "[":
            bracket = 1
            buf.append(ch)
        elif ch == "(":
            paren += 1
            buf.append(ch)
        elif ch == ")":
            paren = max(0, paren - 1)
            buf.append(ch)
        elif ch == "/" and paren == 0:
            segs.append("".join(buf))
            buf.clear()
        else:
            buf.append(ch)
        i += 1
    segs.append("".join(buf))
    return [s for s in segs if s]


def _normalize_next_route_sample(route: str) -> str:
    parts: list[str] = []
    for seg in route.split("/"):
        if not seg:
            continue
        if seg.startswith("[[...") and seg.endswith("]]"):
            parts.append("sample")
        elif seg.startswith("[...") and seg.endswith("]"):
            parts.extend(["sample", "sub"])
        elif seg.startswith("[") and seg.endswith("]"):
            parts.append("sample")
        else:
            parts.append(seg)
    return "/".join(parts)


def _match_single_segment(seg_pat: str, actual: str) -> bool:
    if seg_pat == actual:
        return True
    if seg_pat in {".*", ".+", "(.*)", "(.+)"}:
        return True
    if seg_pat.startswith(":") and "(" not in seg_pat and not seg_pat.endswith(("*", "+")):
        return bool(actual)
    if seg_pat.startswith("(") and seg_pat.endswith(")"):
        inner = seg_pat[1:-1]
        if inner.startswith("?:"):
            inner = inner[2:]
        return any(_match_single_segment(alt.strip(), actual) for alt in _split_top_level_regex_alts(inner))
    return False


def _segment_matches_matcher_pattern(route_segs: list[str], pat_segs: list[str], r_idx: int = 0, p_idx: int = 0) -> bool:
    if p_idx == len(pat_segs):
        return r_idx == len(route_segs)
    pat = pat_segs[p_idx]
    if pat in {"(.*)", ":path(.*)"} or (pat.startswith(":") and pat.endswith("*")):
        if p_idx == len(pat_segs) - 1:
            return True
        for take in range(r_idx, len(route_segs) + 1):
            if _segment_matches_matcher_pattern(route_segs, pat_segs, take, p_idx + 1):
                return True
        return False
    if pat == "(.+)" or (pat.startswith(":") and pat.endswith("+")):
        if r_idx >= len(route_segs):
            return False
        if p_idx == len(pat_segs) - 1:
            return True
        for take in range(r_idx + 1, len(route_segs) + 1):
            if _segment_matches_matcher_pattern(route_segs, pat_segs, take, p_idx + 1):
                return True
        return False
    if r_idx >= len(route_segs):
        return False
    if _match_single_segment(pat, route_segs[r_idx]):
        return _segment_matches_matcher_pattern(route_segs, pat_segs, r_idx + 1, p_idx + 1)
    return False


def _find_first_top_level_neg_lookahead_group(entry: str) -> tuple[int, int] | None:
    """Locate outermost group wrapping the first top-level `(?!...)` in a matcher string."""
    pos = entry.find("(?!")
    if pos == -1:
        return None
    # Check if enclosed directly inside `((?!...).*)` after a slash prefix
    prefix_slice = entry[:pos]
    wrapper_start = -1
    if prefix_slice.endswith("("):
        cand = len(prefix_slice) - 1
        close_cand = _find_matching_paren(entry, cand)
        if close_cand != -1:
            wrapper_start = cand
    elif re.search(r"/:[A-Za-z0-9_]+\($", prefix_slice):
        cand = prefix_slice.rfind("(")
        wrapper_start = cand
    if wrapper_start != -1:
        return wrapper_start, pos
    return pos, pos


def _entry_covers_route(entry: str, route: str) -> bool:
    if entry in {"/:path*", "/(.*)", "/(.*)+", "/:path(.*)"}:
        return True
    sample = _normalize_next_route_sample(route)
    route_segs = [s for s in sample.split("/") if s]

    if "(?!" not in entry:
        pat_segs = _split_matcher_segments(entry)
        return _segment_matches_matcher_pattern(route_segs, pat_segs)

    found = _find_first_top_level_neg_lookahead_group(entry)
    if found is None:
        return False
    grp_start, la_start = found

    # Extract path prefix strictly before the negative-lookahead wrapper
    raw_prefix = entry[:grp_start]
    if re.search(r"/:[A-Za-z0-9_]+$", raw_prefix):
        raw_prefix = raw_prefix[: raw_prefix.rfind(":")]
    prefix_segs = _split_matcher_segments(raw_prefix.rstrip("/"))
    if prefix_segs:
        if len(route_segs) <= len(prefix_segs):
            return False
        for i, ps in enumerate(prefix_segs):
            if not _match_single_segment(ps, route_segs[i]):
                return False
        remainder = "/".join(route_segs[len(prefix_segs) :])
    else:
        remainder = sample

    # Inspect all consecutive `(?!...)` assertions in this group & validate remainder
    scan_idx = la_start
    scope_end = _find_matching_paren(entry, grp_start) if grp_start < la_start else len(entry)
    if grp_start < la_start:
        if scope_end == -1:
            return False
        after_scope = entry[scope_end + 1 :].strip()
        if after_scope not in {"", "$"}:
            return False

    while scan_idx < scope_end and entry[scan_idx : scan_idx + 3] == "(?!":
        close_la = _find_matching_paren(entry, scan_idx)
        if close_la == -1:
            return False  # Fail-closed on malformed matcher regex
        body = entry[scan_idx + 3 : close_la]
        if _match_lookahead_alts_at(body, remainder, [0], max_steps=256):
            return False
        scan_idx = close_la + 1

    tail_inside = entry[scan_idx:scope_end].rstrip("$").strip()
    if tail_inside not in {"", ".*", ".+", ".*?", ".+?", "(.*)", "(.+)", "(?:.*)", "(?:/.*)?", "(?:/.*)", "[\\s\\S]*"}:
        return False
    if tail_inside in {".+", ".+?", "(.+)"} and not remainder:
        return False
    return True


def _is_route_covered_by_matcher(route: str, matcher_entries: list[str]) -> bool:
    return any(_entry_covers_route(entry, route) for entry in matcher_entries)


_WIN_GLOBAL_RE = (
    r"(?:\b(?:window|globalThis|self)|"
    r"\(\s*(?:window|globalThis|self)\s+as\s+(?:[^()]|\([^()]*\))+\))"
)


def scan_typescript_source(rel: str, text: str) -> list[Finding]:
    """Audit a single TypeScript/TSX/JS/JSX source string for XSS, native dialogs, jsPDF, client tax math, PII & monoliths."""
    findings: list[Finding] = []
    lines = text.splitlines()
    code_only = _strip_ts_comments_preserving_lines(text)

    multiline_rules: list[tuple[str, str, re.Pattern[str], str]] = [
        ("HIGH", "NATIVE_DIALOG", re.compile(r"\bwindow(?:\s|\n)*\.(?:alert|confirm|prompt)\s*\(|\bwindow\s*\[\s*[\"'](?:alert|confirm|prompt)[\"']\s*\]"), "Native window.alert/confirm/prompt violates enterprise UI dialog contract."),
        ("HIGH", "JSPDF_RASTER", re.compile(r"\bnew\s+jsPDF\b|from\s+[\"']jspdf[\"']"), "Client jsPDF raster export; use backend Chromium PDF stream."),
        ("HIGH", "XSS_DANGEROUS_HTML", re.compile(r"\bdangerouslySetInnerHTML\b"), "dangerouslySetInnerHTML sink requires explicit sanitization review."),
        (
            "HIGH",
            "XSS_DOM_SINK",
            re.compile(
                r"\.(?:innerHTML|outerHTML)\s*=(?!=)|"
                r"\[\s*[\"'](?:innerHTML|outerHTML)[\"']\s*\]\s*=(?!=)|"
                r"\.insertAdjacentHTML\s*\(|"
                r"\bdocument\.(?:write|writeln)\s*\(|"
                r"\bsrcDoc\s*=(?!=)"
            ),
            "Direct DOM HTML injection sink (innerHTML/outerHTML/insertAdjacentHTML/document.write(ln)/srcDoc).",
        ),
        (
            "HIGH",
            "NO_CLIENT_EVAL",
            re.compile(
                r"(?<![\w.$])(?:eval|Function)\s*\(|"
                + _WIN_GLOBAL_RE + r"(?:\s*(?:\?\.)?\s*\.\s*|\s*(?:\?\.)?\s*\[\s*[\"'])(?:eval|Function)(?:[\"']\s*\])?\s*\(|"
                r"\bnew\s+(?:" + _WIN_GLOBAL_RE + r"\s*(?:\?\.)?\s*\.\s*)?Function\s*\(|"
                r"\(\s*0\s*,\s*(?:" + _WIN_GLOBAL_RE + r"\s*\.\s*)?eval\s*\)\s*\("
            ),
            "Dynamic eval()/Function() execution banned in frontend.",
        ),
        ("HIGH", "CLIENT_FINANCIAL_MATH", re.compile(r"\bfunction\s+computeMalaysianRoadTax\b|Math\.round\(\s*rawPremNum\s*\)"), "Duplicated client-side Malaysian road-tax / pricing rounding math; consume authoritative backend Decimal API."),
        ("HIGH", "DEPRECATED_GEMINI", DEPRECATED_GEMINI_RE, "Deprecated or shutdown Gemini model string in frontend."),
    ]
    for severity, rule_id, pattern, message in multiline_rules:
        for match in pattern.finditer(code_only):
            ln = _line_of_offset(code_only, match.start())
            findings.append(Finding(severity, rule_id, f"{rel}:{ln}", message))

    placeholder_span_re = re.compile(r'placeholder\s*=\s*(?:"[^"]*"|\'[^\']*\')', re.IGNORECASE)
    for idx, line in enumerate(lines, 1):
        if PII_SECRET_RE.search(line):
            findings.append(Finding("HIGH", "PII_OR_SECRET", f"{rel}:{idx}", "Hardcoded PII/bank/secret literal in frontend source."))
            continue
        for m_nric in NRIC_RE.finditer(line):
            pos = m_nric.start()
            in_placeholder = any(ps.start() <= pos <= ps.end() for ps in placeholder_span_re.finditer(line))
            if not in_placeholder:
                findings.append(Finding("HIGH", "PII_OR_SECRET", f"{rel}:{idx}", "Hardcoded Malaysian NRIC literal in frontend source."))
                break

    if len(lines) > 600:
        findings.append(Finding("MEDIUM", "MONOLITH_TS", f"{rel}:1", f"Frontend module is {len(lines)} lines (>600 line budget)."))
    return findings


def _audit_frontend() -> list[Finding]:
    findings: list[Finding] = []
    app_dir = FRONTEND_SRC / "app"
    mw_candidates = [
        FRONTEND_SRC / "middleware.ts",
        FRONTEND_SRC / "proxy.ts",
        ROOT / "frontend" / "middleware.ts",
        ROOT / "frontend" / "proxy.ts",
    ]
    middleware_file = next((p for p in mw_candidates if p.exists()), None)

    if app_dir.exists():
        if middleware_file is None:
            findings.append(Finding("CRITICAL", "MISSING_MIDDLEWARE", "frontend/src/middleware.ts:1", "No Next.js auth middleware/proxy.ts found."))
        else:
            mw_text = middleware_file.read_text(encoding="utf-8", errors="ignore")
            mw_code = _strip_ts_comments_preserving_lines(mw_text)
            mw_rel = _rel(middleware_file)
            has_matcher, matcher_entries = _extract_middleware_matcher_entries(mw_code)
            if not has_matcher or not matcher_entries:
                findings.append(Finding("CRITICAL", "MIDDLEWARE_UNPROTECTED", f"{mw_rel}:1", "middleware config.matcher array/string missing."))
            else:
                has_cookie_check = bool(re.search(r"\bcookies\.get\s*\(", mw_code))
                has_redirect = bool(re.search(r"\bredirect\s*\(", mw_code))
                if not (has_cookie_check and has_redirect):
                    findings.append(Finding("CRITICAL", "MIDDLEWARE_NO_AUTH_CHECK", f"{mw_rel}:1", "middleware does not enforce session cookie check + login redirect."))

                m_matcher = re.search(r"\bmatcher\s*:", mw_code)
                mw_line = _line_of_offset(mw_code, m_matcher.start()) if m_matcher else 1
                page_routes: set[str] = set()
                for page_file in app_dir.rglob("*"):
                    if not page_file.is_file() or page_file.name not in {"page.tsx", "page.ts", "page.jsx", "page.js"}:
                        continue
                    rel_parts = page_file.relative_to(app_dir).parts[:-1]
                    url_parts = [p for p in rel_parts if not (p.startswith("(") and p.endswith(")"))]
                    if not url_parts:
                        continue
                    if any(p.startswith(("_", ".", "@")) for p in url_parts) or url_parts[0] in PUBLIC_NEXT_ROUTES:
                        continue
                    page_routes.add("/".join(url_parts))

                for route in sorted(page_routes):
                    if not _is_route_covered_by_matcher(route, matcher_entries):
                        findings.append(
                            Finding(
                                "CRITICAL",
                                "MIDDLEWARE_UNPROTECTED",
                                f"{mw_rel}:{mw_line}",
                                f"Protected app route '/{route}' missing or excluded in Next.js config.matcher.",
                            )
                        )

    for ts_file in sorted(FRONTEND_SRC.rglob("*")):
        if not ts_file.is_file() or ts_file.suffix not in {".ts", ".tsx", ".js", ".jsx"}:
            continue
        rel = _rel(ts_file)
        text = ts_file.read_text(encoding="utf-8", errors="ignore")
        findings.extend(scan_typescript_source(rel, text))

    return findings


def _run_optional_external_tools(*, require_external: bool = False) -> tuple[list[dict], list[Finding]]:
    tool_status: list[dict] = []
    findings: list[Finding] = []
    missing_sev = "HIGH" if require_external else "MEDIUM"
    npm_exe = "npm.cmd" if os.name == "nt" else "npm"

    py_specs: list[tuple[str, str, list[str], Path]] = [
        ("ruff", "ruff", [sys.executable, "-m", "ruff", "check", "backend/app"], ROOT),
        ("bandit", "bandit", [sys.executable, "-m", "bandit", "-r", "backend/app", "-q"], ROOT),
        ("mypy", "mypy", [sys.executable, "-m", "mypy", "backend/app/services/road_tax_engine.py", "backend/app/services/formula_evaluator.py", "backend/app/rendering/pdf_generator.py"], ROOT),
        ("pip-audit", "pip_audit", [sys.executable, "-m", "pip_audit", "-r", "requirements.txt"], ROOT),
    ]
    for label, mod_name, cmd, workdir in py_specs:
        try:
            probe = subprocess.run(
                [sys.executable, "-m", mod_name, "--version"],
                stdin=subprocess.DEVNULL,
                capture_output=True,
                text=True,
                timeout=15,
            )
            exe_ok = probe.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            exe_ok = False
        if not exe_ok:
            tool_status.append({"tool": label, "installed": False, "passed": None})
            findings.append(Finding(missing_sev, "EXT_TOOL_MISSING", "repo", f"Optional scanner '{label}' not installed in active .venv."))
            continue
        timeout_sec = 180 if label == "pip-audit" else 60
        try:
            proc = subprocess.run(cmd, cwd=str(workdir), stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=timeout_sec)
        except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
            tool_status.append({"tool": label, "installed": True, "passed": False})
            sev = "HIGH" if require_external else "MEDIUM"
            findings.append(Finding(sev, f"EXT_{label.upper().replace('-', '_')}", "repo", f"Scanner failed/timed out: {exc}"))
            continue
        passed = proc.returncode == 0
        tool_status.append({"tool": label, "installed": True, "passed": passed})
        if not passed:
            err_text = (proc.stdout + "\n" + proc.stderr).strip()
            summary = err_text.splitlines()[:5]
            is_net_err = any(k in err_text for k in ("HTTPSConnectionPool", "ConnectionError", "gaierror", "NameResolutionError", "timed out"))
            sev = "HIGH" if (require_external or not is_net_err) else "MEDIUM"
            findings.append(Finding(sev, f"EXT_{label.upper().replace('-', '_')}", "repo", "; ".join(summary)))

    if (ROOT / "frontend" / "package.json").exists():
        npm_path = shutil.which(npm_exe)
        for label, npm_args in [("npm-lint", ["run", "lint"]), ("npm-audit", ["audit", "--audit-level=high"])]:
            if not npm_path:
                tool_status.append({"tool": label, "installed": False, "passed": None})
                findings.append(Finding(missing_sev, "EXT_TOOL_MISSING", "frontend", f"'{npm_exe}' missing; cannot run {label}."))
                continue
            try:
                proc = subprocess.run(
                    [npm_path, *npm_args],
                    cwd=str(ROOT / "frontend"),
                    stdin=subprocess.DEVNULL,
                    capture_output=True,
                    text=True,
                    timeout=60,
                )
                passed = proc.returncode == 0
                tool_status.append({"tool": label, "installed": True, "passed": passed})
                if not passed:
                    detail = (proc.stdout + "\n" + proc.stderr).strip().splitlines()[:5]
                    sev = "MEDIUM" if (label == "npm-audit" and "ENOTFOUND" in (proc.stderr or "")) else "HIGH"
                    findings.append(Finding(sev, f"EXT_{label.upper().replace('-', '_')}", "frontend", "; ".join(detail)))
            except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
                tool_status.append({"tool": label, "installed": True, "passed": False})
                findings.append(Finding("HIGH", f"EXT_{label.upper().replace('-', '_')}", "frontend", f"Frontend check error: {exc}"))

    return tool_status, findings


def main() -> int:
    parser = argparse.ArgumentParser(description="Risklocker automated SAST & security audit.")
    parser.add_argument("--strict", action="store_true", help="Exit 1 if any CRITICAL or HIGH findings exist.")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON summary.")
    parser.add_argument("--with-external", action="store_true", help="Run ruff/bandit/mypy/pip-audit/npm checks if installed.")
    parser.add_argument("--require-external", action="store_true", help="Fail HIGH if any external scanner is missing (implies --with-external).")
    args = parser.parse_args()

    call_graph, parsed_files, all_reexports = _build_backend_call_graph()
    router_mounts = _build_backend_router_mounts(parsed_files, call_graph, all_reexports)
    findings: list[Finding] = []
    if BACKEND_APP.exists():
        for py_file in sorted(BACKEND_APP.rglob("*.py")):
            rel = _rel(py_file)
            findings.extend(
                scan_python_source(
                    rel,
                    py_file.read_text(encoding="utf-8", errors="ignore"),
                    call_graph,
                    router_mounts,
                    all_reexports,
                )
            )
    if FRONTEND_SRC.exists():
        findings.extend(_audit_frontend())

    ext_status: list[dict] = []
    if args.with_external or args.require_external:
        ext_status, ext_findings = _run_optional_external_tools(require_external=bool(args.require_external))
        findings.extend(ext_findings)

    counts = {
        "CRITICAL": sum(1 for f in findings if f.severity == "CRITICAL"),
        "HIGH": sum(1 for f in findings if f.severity == "HIGH"),
        "MEDIUM": sum(1 for f in findings if f.severity == "MEDIUM"),
    }

    if args.json:
        print(json.dumps({"counts": counts, "external_tools": ext_status, "findings": [asdict(f) for f in findings]}, indent=2))
    else:
        print(f"Security & Static Audit Summary: CRITICAL={counts['CRITICAL']}, HIGH={counts['HIGH']}, MEDIUM={counts['MEDIUM']}")
        for f in findings:
            print(f"  [{f.severity}] {f.rule_id} @ {f.location} — {f.message}")
        if ext_status:
            print("External scanners:", ", ".join(f"{t['tool']}={'OK' if t['passed'] else ('MISSING' if not t['installed'] else 'FAIL')}" for t in ext_status))

    if args.strict and (counts["CRITICAL"] > 0 or counts["HIGH"] > 0):
        return 1
    if args.require_external and any(not t.get("installed") for t in ext_status):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
