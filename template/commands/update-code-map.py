"""Generate or check the project codebase symbol and route map for ANY project language or stack."""

from __future__ import annotations

import argparse
import ast
import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "docs" / "generated" / "CODEBASE-MAP.md"
START = "<!-- GENERATED:START -->"
END = "<!-- GENERATED:END -->"

# Supported file extensions across all languages
EXTENSIONS = {
    ".py", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".vue", ".svelte",
    ".go", ".rs", ".java", ".kt", ".swift", ".dart", ".c", ".cpp",
    ".h", ".hpp", ".cs", ".php", ".rb", ".sql", ".sh", ".bash", ".ps1", ".html"
}

# Directories to ignore during scanning
IGNORE_DIRS = {
    "node_modules", ".git", ".venv", "venv", "env", "dist", "build", "out",
    "target", "vendor", "__pycache__", ".next", ".nuxt", ".turbo", ".gradle",
    ".idea", ".vscode", ".qc-tmp", ".tmp", "coverage", ".pub-cache", "Pods",
    "docs", "template", ".agents"
}


def responsibility(relative: str) -> str:
    path = relative.replace("\\", "/").lower()
    rules = [
        ("api", "HTTP routes and API handlers"),
        ("auth", "Authentication, authorization and security"),
        ("db", "Database models, schemas and migrations"),
        ("services", "Business logic and service workflows"),
        ("components", "UI components and visual elements"),
        ("views", "Pages and UI views"),
        ("pages", "Application routing and pages"),
        ("routes", "Route handlers and endpoints"),
        ("lib", "Shared utilities and helper libraries"),
        ("utils", "Utility functions and helpers"),
        ("models", "Data models and entity definitions"),
        ("controllers", "Controller logic and request routing"),
        ("handlers", "Event and request handlers"),
        ("tests", "Automated regression and unit coverage"),
        ("commands", "Operations and maintenance automation"),
        ("scripts", "Build and operational scripts"),
        ("config", "Configuration and environment settings"),
    ]
    for prefix, label in rules:
        if prefix in path:
            return label
    return "Application source file"


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
        re.compile(r"^(?:export\s+)?(?:const|type|interface|class|enum)\s+([A-Za-z0-9_]+)"),
        re.compile(r"^func\s+(?:\([^)]+\)\s+)?([A-Za-z0-9_]+)"),
        re.compile(r"^pub\s+(?:fn|struct|enum|trait)\s+([A-Za-z0-9_]+)"),
        re.compile(r"^(?:public|private|protected)?\s*(?:class|interface|record|enum)\s+([A-Za-z0-9_]+)"),
        re.compile(r"^(?:public|private|protected)?\s*(?:static\s+)?(?:async\s+)?[A-Za-z0-9_<>\[\]]+\s+([A-Za-z0-9_]+)\s*\("),
        re.compile(r"^CREATE\s+(?:TABLE|INDEX|VIEW|FUNCTION|TRIGGER)\s+(?:IF\s+NOT\s+EXISTS\s+)?([^\s(]+)", re.IGNORECASE),
        re.compile(r"^def\s+([A-Za-z0-9_]+)"),
    ]
    for number, line in enumerate(lines, 1):
        stripped = line.strip()
        for pattern in patterns:
            match = pattern.match(stripped)
            if match:
                symbols.append(f"`{match.group(1)}` L{number}")
                break
    return symbols[:12]


def generate() -> str:
    lines: list[str] = ["| Path | Purpose | Key Symbols |", "| --- | --- | --- |"]
    found_any = False

    # Scan the entire repository dynamically
    for root_dir, dirs, files in os.walk(ROOT):
        # Filter out ignored directories in-place
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS and not d.startswith(".")]
        
        for file in sorted(files):
            file_path = Path(root_dir) / file
            if file_path.suffix.lower() not in EXTENSIONS:
                continue
                
            rel = file_path.relative_to(ROOT).as_posix()
            resp = responsibility(rel)
            
            if file_path.suffix.lower() == ".py":
                syms = python_symbols(file_path)
            else:
                syms = text_symbols(file_path)
                
            sym_text = ", ".join(syms) if syms else "—"
            lines.append(f"| `{rel}` | {resp} | {sym_text} |")
            found_any = True

    if not found_any:
        lines.append("| `(empty repository or no supported files)` | Initial project state | — |")

    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Update or check codebase map.")
    parser.add_argument("--write", action="store_true", help="Write generated map to file")
    parser.add_argument("--check", action="store_true", help="Check if map is current")
    args = parser.parse_args()

    table = generate()
    if not TARGET.exists():
        TARGET.parent.mkdir(parents=True, exist_ok=True)
        TARGET.write_text(f"# Generated Codebase Map\n\n{START}\n{table}\n{END}\n", encoding="utf-8")
        print(f"Created {TARGET.relative_to(ROOT)}")
        return 0

    content = TARGET.read_text(encoding="utf-8-sig")
    if START not in content or END not in content:
        print(f"Missing generation markers in {TARGET.relative_to(ROOT)}")
        return 1

    pre = content.split(START)[0]
    post = content.split(END)[1]
    updated = f"{pre}{START}\n{table}\n{END}{post}"

    if args.write:
        TARGET.write_text(updated, encoding="utf-8")
        print(f"Updated {TARGET.relative_to(ROOT)}")
        return 0

    if args.check:
        if content != updated:
            print(f"Code map out of date. Run 'python {Path(__file__).name} --write'")
            return 1
        print("Code map is current.")
        return 0

    TARGET.write_text(updated, encoding="utf-8")
    print(f"Updated {TARGET.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
