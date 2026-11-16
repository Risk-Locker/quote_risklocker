"""Generate or check the concise project code map."""

from __future__ import annotations

import argparse
import ast
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "docs" / "generated" / "CODEBASE-MAP.md"
START = "<!-- GENERATED:START -->"
END = "<!-- GENERATED:END -->"
SCAN_ROOTS = [ROOT / "backend" / "app", ROOT / "frontend" / "src", ROOT / "migrations", ROOT / "tests", ROOT / "commands"]
EXTENSIONS = {".py", ".ts", ".tsx", ".sql", ".ps1", ".cmd"}


def responsibility(relative: str) -> str:
    path = relative.replace("\\", "/")
    rules = [
        ("backend/app/api", "HTTP routes and request dependencies"),
        ("backend/app/auth", "authentication authorization and RBAC"),
        ("backend/app/core", "runtime configuration security and API errors"),
        ("backend/app/db", "Postgres engine sessions and seed data"),
        ("backend/app/extraction", "PDF layout extraction candidate mapping and validation"),
        ("backend/app/models", "SQLAlchemy tables and shared enums"),
        ("backend/app/rendering", "deterministic template HTML and PDF rendering"),
        ("backend/app/services", "application workflows and provider orchestration"),
        ("backend/app/storage", "private PDF object storage providers"),
        ("backend/app/assets", "runtime template images and SVG assets"),
        ("frontend/src/app/admin/templates", "template list and A4 builder routes"),
        ("frontend/src/app/admin", "admin settings routes"),
        ("frontend/src/app/review", "staff PDF comparison and draft review"),
        ("frontend/src/app", "Next.js application route"),
        ("frontend/src/components", "shared dashboard and template components"),
        ("frontend/src/lib", "frontend API and shared helpers"),
        ("migrations", "ordered Supabase/Postgres schema migration"),
        ("tests", "automated regression coverage"),
        ("commands", "developer operations and maintenance command"),
    ]
    for prefix, label in rules:
        if path.startswith(prefix):
            return label
    return "project file"


def python_symbols(path: Path) -> list[str]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8-sig"))
    except (OSError, SyntaxError, UnicodeDecodeError):
        return []
    symbols: list[str] = []
    for node in tree.body:
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            end = getattr(node, "end_lineno", node.lineno)
            symbols.append(f"`{node.name}` L{node.lineno}-{end}")
    return symbols[:12]


def text_symbols(path: Path) -> list[str]:
    try:
        lines = path.read_text(encoding="utf-8-sig").splitlines()
    except (OSError, UnicodeDecodeError):
        return []
    symbols: list[str] = []
    patterns = [
        re.compile(r"^export\s+(?:default\s+)?function\s+([A-Za-z0-9_]+)"),
        re.compile(r"^(?:export\s+)?(?:const|type|interface|class)\s+([A-Za-z0-9_]+)"),
        re.compile(r"^CREATE\s+(?:TABLE|INDEX)\s+(?:IF\s+NOT\s+EXISTS\s+)?([^\s(]+)", re.IGNORECASE),
    ]
    for number, line in enumerate(lines, 1):
        stripped = line.strip()
        for pattern in patterns:
            match = pattern.match(stripped)
            if match:
                symbols.append(f"`{match.group(1)}` L{number}")
                break
    return symbols[:12]


def route_symbols(path: Path) -> list[str]:
    if path.name != "routes.py":
        return []
    lines = path.read_text(encoding="utf-8-sig").splitlines()
    routes = []
    for number, line in enumerate(lines, 1):
        match = re.search(r"@router\.(get|post|patch|delete|put)\(\"([^\"]+)\"", line)
        if match:
            routes.append(f"`{match.group(1).upper()} {match.group(2)}` L{number}")
    return routes


def generate() -> str:
    grouped: dict[str, list[str]] = {"Backend": [], "Frontend": [], "Migrations": [], "Tests": [], "Commands": []}
    for scan_root in SCAN_ROOTS:
        if not scan_root.exists():
            continue
        candidates = [
            p for p in scan_root.rglob("*")
            if p.is_file() and p.suffix.lower() in EXTENSIONS and "__pycache__" not in p.parts
        ]
        candidates.sort(key=lambda p: p.relative_to(ROOT).as_posix())
        for path in candidates:
            relative = path.relative_to(ROOT).as_posix()
            if relative.startswith("backend/"):
                group = "Backend"
            elif relative.startswith("frontend/"):
                group = "Frontend"
            elif relative.startswith("migrations/"):
                group = "Migrations"
            elif relative.startswith("tests/"):
                group = "Tests"
            else:
                group = "Commands"
            line_count = len(path.read_bytes().splitlines())
            symbols = python_symbols(path) if path.suffix == ".py" else text_symbols(path)
            symbols.extend(route_symbols(path))
            detail = "; ".join(dict.fromkeys(symbols))
            suffix = f" Symbols: {detail}." if detail else ""
            grouped[group].append(f"- `{relative}` L1-{line_count}: {responsibility(relative)}.{suffix}")

    sections = [
        "Generated file map. Line spans are navigational hints and are refreshed by the map command.",
        "",
        "## Entry Points",
        "",
        "- Backend: `backend/app/main.py` and `backend/app/api/routes.py`.",
        "- Frontend: `frontend/src/app/` with shared shell/API code under `frontend/src/components/` and `frontend/src/lib/`.",
        "- Database: `backend/app/models/tables.py` plus ordered SQL in `migrations/`.",
        "- Operations: `commands/` and root `package.json` scripts.",
    ]
    for group, entries in grouped.items():
        sections.extend(["", f"## {group}", "", *entries])
    return "\n".join(sections).rstrip() + "\n"


def rendered_document(body: str) -> str:
    existing = TARGET.read_text(encoding="utf-8") if TARGET.exists() else "# Codebase Map\n\n"
    existing = existing.replace("\r\n", "\n")
    if START in existing and END in existing:
        prefix = existing.split(START, 1)[0]
        suffix = existing.split(END, 1)[1]
        return f"{prefix}{START}\n{body}{END}{suffix}"
    return f"# Codebase Map\n\n{START}\n{body}{END}\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    args = parser.parse_args()
    expected = rendered_document(generate())
    if args.write:
        TARGET.parent.mkdir(parents=True, exist_ok=True)
        TARGET.write_text(expected.replace("\r\n", "\n"), encoding="utf-8", newline="\n")
        print(f"Updated {TARGET.relative_to(ROOT)}")
        return 0
    current = TARGET.read_text(encoding="utf-8") if TARGET.exists() else ""
    if current.replace("\r\n", "\n") != expected.replace("\r\n", "\n"):
        print("Code map is stale. Run: python commands/update-code-map.py --write")
        return 1
    print("Code map is current.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
