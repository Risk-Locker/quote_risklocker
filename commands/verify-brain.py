"""Verify the integrity, links, and registry coverage of the 3-tier agent documentation system."""

from __future__ import annotations

import re
import sys
from pathlib import Path

# Ensure UTF-8 output on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]
DOCS_DIR = ROOT / "docs"
START_HERE = DOCS_DIR / "core" / "START-HERE.md"
STATE_FILE = DOCS_DIR / "core" / "STATE.md"
AGENTS_FILE = ROOT / "AGENTS.md"

MAX_STATE_LINES = 100


def check_registered_docs() -> list[str]:
    """Ensure all canonical markdown docs are registered in START-HERE.md."""
    errors: list[str] = []
    if not START_HERE.exists():
        return [f"Missing master routing file: {START_HERE.relative_to(ROOT)}"]

    content = START_HERE.read_text(encoding="utf-8-sig")

    # Find all canonical md files
    for path in DOCS_DIR.rglob("*.md"):
        rel_path = path.relative_to(ROOT).as_posix()
        # Skip history logs, generated maps, and temporary superpowers plans
        if "docs/history/" in rel_path or "docs/generated/" in rel_path or "docs/superpowers/" in rel_path:
            continue
        
        # Check if file name or relative path is mentioned in START-HERE.md
        if path.name not in content and rel_path not in content:
            errors.append(f"Unregistered document: {rel_path} is not listed in docs/core/START-HERE.md")

    return errors


def check_state_size() -> list[str]:
    """Check that STATE.md remains a lean working memory snapshot."""
    errors: list[str] = []
    if not STATE_FILE.exists():
        return [f"Missing active working memory file: {STATE_FILE.relative_to(ROOT)}"]

    lines = STATE_FILE.read_text(encoding="utf-8-sig").splitlines()
    if len(lines) > MAX_STATE_LINES:
        errors.append(
            f"STATE.md exceeds limit ({len(lines)} > {MAX_STATE_LINES} lines). "
            "Archive older entries to docs/history/MEMORY-YYYY-MM.md to prevent context rot."
        )
    return errors


def check_markdown_links() -> list[str]:
    """Check that relative and file:// links in core documentation resolve."""
    errors: list[str] = []
    link_pattern = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
    
    files_to_check = [AGENTS_FILE, START_HERE, STATE_FILE]
    for doc in files_to_check:
        if not doc.exists():
            continue
        text = doc.read_text(encoding="utf-8-sig")
        for match in link_pattern.finditer(text):
            url = match.group(2).strip()
            # Handle file:/// URLs
            if url.startswith("file:///"):
                clean_path = url.replace("file:///", "").split("#")[0]
                # Handle Windows drive letters like c:/
                target = Path(clean_path)
                if not target.exists():
                    errors.append(f"{doc.relative_to(ROOT)}: Broken link to {url}")
            # Handle relative paths
            elif not url.startswith("http://") and not url.startswith("https://") and not url.startswith("#"):
                clean_rel = url.split("#")[0]
                if clean_rel:
                    target = (doc.parent / clean_rel).resolve()
                    if not target.exists():
                        errors.append(f"{doc.relative_to(ROOT)}: Broken relative link to {url}")

    return errors


def main() -> int:
    print("Verifying Agent Brain & Documentation Integrity...")
    all_errors: list[str] = []

    reg_errors = check_registered_docs()
    state_errors = check_state_size()
    link_errors = check_markdown_links()

    all_errors.extend(reg_errors)
    all_errors.extend(state_errors)
    all_errors.extend(link_errors)

    if all_errors:
        print("\n[FAIL] Brain Verification Failed:")
        for err in all_errors:
            print(f"  - {err}")
        return 1

    print("\n[PASS] Agent Brain Verification Passed:")
    print("  - All canonical topic docs are registered in docs/core/START-HERE.md")
    print(f"  - docs/core/STATE.md is lean working memory (<{MAX_STATE_LINES} lines)")
    print("  - Markdown links in core files resolve successfully")
    return 0


if __name__ == "__main__":
    sys.exit(main())
