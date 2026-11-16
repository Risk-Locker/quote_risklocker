"""Hermetic unit tests for commands/security-audit.py and .agents/hooks/static_security_tripwire.py."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "commands"))

import importlib.util

spec = importlib.util.spec_from_file_location("security_audit", str(ROOT / "commands" / "security-audit.py"))
assert spec is not None and spec.loader is not None
audit = importlib.util.module_from_spec(spec)
sys.modules["security_audit"] = audit
spec.loader.exec_module(audit)


def test_python_source_scanner_flags_eval_and_exec():
    py_code = """
def bad_calculator(expr: str):
    return eval(expr)

def bad_runner(cmd: str):
    exec(cmd)
"""
    findings = audit.scan_python_source("backend/app/services/calc.py", py_code, None)
    rule_ids = {f.rule_id for f in findings}
    assert "NO_EVAL" in rule_ids
    assert "NO_EXEC" in rule_ids


def test_python_source_scanner_flags_dynamic_sql():
    py_code = """
from sqlalchemy import text

def unsafe_query(db, user_input):
    return db.execute(text(f"SELECT * FROM users WHERE id = '{user_input}'"))
"""
    findings = audit.scan_python_source("backend/app/services/user.py", py_code, None)
    rule_ids = {f.rule_id for f in findings}
    assert "SQLI_DYNAMIC" in rule_ids


def test_typescript_source_scanner_flags_dangerous_html_and_alerts():
    ts_code = """
export function UnsafeView({ content }: { content: string }) {
    window.alert("Notification");
    return <div dangerouslySetInnerHTML={{ __html: content }} />;
}
"""
    findings = audit.scan_typescript_source("frontend/src/components/UnsafeView.tsx", ts_code)
    rule_ids = {f.rule_id for f in findings}
    assert "XSS_DANGEROUS_HTML" in rule_ids
    assert "NATIVE_DIALOG" in rule_ids


def test_security_audit_catch_proof_on_pre_phase_c_defects():
    """Verify that commands/security-audit.py actively flags open P0 defects F-01..F-04."""
    call_graph, parsed_files, all_reexports = audit._build_backend_call_graph()
    router_mounts = audit._build_backend_router_mounts(parsed_files, call_graph, all_reexports)

    # F-01 Catch Proof (render_worker.py STORAGE_BYPASS)
    render_worker_path = ROOT / "backend" / "app" / "workers" / "render_worker.py"
    if render_worker_path.is_file():
        findings = audit.scan_python_source(
            "backend/app/workers/render_worker.py",
            render_worker_path.read_text(encoding="utf-8"),
            call_graph,
            router_mounts,
            all_reexports,
        )
        assert any(f.rule_id == "STORAGE_BYPASS" for f in findings), "Expected F-01 STORAGE_BYPASS to be flagged"

    # F-03 Catch Proof (road_tax_engine.py NO_EVAL on legacy eval formula)
    eval_snippet = """
def _eval_formula(self, formula: str, cc: float) -> float:
    return float(eval(formula, {"__builtins__": {}}, {"cc": cc}))
"""
    findings = audit.scan_python_source(
        "backend/app/services/road_tax_engine.py",
        eval_snippet,
        call_graph,
        router_mounts,
        all_reexports,
    )
    assert any(f.rule_id == "NO_EVAL" for f in findings), "Expected F-03 NO_EVAL to be flagged"

    # F-04 Verification (middleware.ts fully covers protected routes post-Phase 1)
    mw_findings = audit._audit_frontend()
    unprotected_routes = {
        f.message.split("'")[1] for f in mw_findings if f.rule_id == "MIDDLEWARE_UNPROTECTED" and "'" in f.message
    }
    for route in ["/comparison", "/ledger", "/insights", "/ai-context"]:
        assert route not in unprotected_routes and route.lstrip("/") not in unprotected_routes, (
            f"F-04 route '{route}' must be protected in Next.js middleware"
        )
