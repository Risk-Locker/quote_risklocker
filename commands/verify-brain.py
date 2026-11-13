"""Verify integrity, link health, registry coverage, and skill-budget sync of `docs/` and `.agents/`."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]
DOCS_DIR = ROOT / "docs"
AGENTS_DIR = ROOT / ".agents"
START_HERE = DOCS_DIR / "core" / "START-HERE.md"
STATE_FILE = DOCS_DIR / "core" / "STATE.md"
AGENTS_FILE = ROOT / "AGENTS.md"
SKILLS_LOCK = AGENTS_DIR / "skills-lock.json"
SKILLS_INDEX = DOCS_DIR / "generated" / "SKILLS-INDEX.md"
SKILLS_DOC = DOCS_DIR / "core" / "SKILLS.md"
VAULT_README = AGENTS_DIR / "skills-vault" / "README.md"
STRUCTURE_DOC = DOCS_DIR / "architecture" / "STRUCTURE.md"

MAX_STATE_LINES = 80

BACKTICK_PATH_RE = re.compile(
    r"`((?:docs|\.agents|commands|backend|frontend|migrations|tests)/[A-Za-z0-9_./:-]+|(?:requirements\.txt|package\.json|pytest\.ini|AGENTS\.md))`"
)
SKIP_BACKTICK_TOKENS = (
    "*",
    "<",
    ">",
    "{",
    "}",
    "YYYY",
    "XXX",
    "075+",
    "...",
    "://",
    "stateless_generated",
    "research-browser-profile",
    "skill-stage",
    "new-project",
    "pytest-run",
    "file_a",
    "file_b",
    ".agents/logs/",
    ".freeze.lock",
)


def _iter_canonical_docs() -> list[Path]:
    files: list[Path] = []
    if not DOCS_DIR.exists():
        return files
    for path in sorted(DOCS_DIR.rglob("*.md")):
        rel_path = path.relative_to(ROOT).as_posix()
        if "docs/history/" in rel_path or "docs/generated/" in rel_path or "docs/superpowers/" in rel_path:
            continue
        files.append(path)
    return files


def _iter_harness_markdown() -> list[Path]:
    files: list[Path] = []
    for folder in (
        AGENTS_DIR / "agents",
        AGENTS_DIR / "rules",
        AGENTS_DIR / "guides",
    ):
        if folder.exists():
            files.extend(sorted(folder.glob("*.md")))
    skills_dir = AGENTS_DIR / "skills"
    if skills_dir.exists():
        for skill_md in sorted(skills_dir.glob("*/SKILL.md")):
            files.append(skill_md)
        for ref_md in sorted(skills_dir.glob("*/references/*.md")):
            files.append(ref_md)
    if VAULT_README.exists():
        files.append(VAULT_README)
    return files


def check_registered_docs() -> list[str]:
    """Ensure all canonical markdown docs are explicitly registered in START-HERE.md."""
    errors: list[str] = []
    if not START_HERE.exists():
        return [f"Missing master routing file: {START_HERE.relative_to(ROOT).as_posix()}"]

    content = START_HERE.read_text(encoding="utf-8-sig")

    for path in _iter_canonical_docs():
        rel_path = path.relative_to(ROOT).as_posix()
        exact_pat = re.compile(rf"(?<![A-Za-z0-9_./-]){re.escape(rel_path)}(?![A-Za-z0-9_./-])")
        if exact_pat.search(content):
            continue
        # Allow grouped underwriter specs covered by explicit `docs/benefits/expanded/` + basename listing
        if rel_path.startswith("docs/benefits/expanded/") and "docs/benefits/expanded/" in content:
            name_pat = re.compile(rf"(?<![A-Za-z0-9_.-]){re.escape(path.name)}(?![A-Za-z0-9_.-])")
            if name_pat.search(content):
                continue
        errors.append(f"Unregistered document: {rel_path} is not listed by exact path in docs/core/START-HERE.md")

    return errors


def check_state_size() -> list[str]:
    """Check that STATE.md remains a lean working memory snapshot (<= 80 lines)."""
    errors: list[str] = []
    if not STATE_FILE.exists():
        return [f"Missing active working memory file: {STATE_FILE.relative_to(ROOT).as_posix()}"]

    lines = STATE_FILE.read_text(encoding="utf-8-sig").splitlines()
    if len(lines) > MAX_STATE_LINES:
        errors.append(
            f"STATE.md exceeds limit ({len(lines)} > {MAX_STATE_LINES} lines). "
            "Archive older entries to docs/history/MEMORY-YYYY-MM.md to prevent context rot."
        )
    return errors


def _strip_fenced_code(text: str) -> str:
    out: list[str] = []
    in_fence = False
    for line in text.splitlines():
        if line.lstrip().startswith(("```", "````")):
            in_fence = not in_fence
            out.append("")
            continue
        out.append("" if in_fence else line)
    return "\n".join(out)


def check_markdown_links() -> list[str]:
    """Check relative/file links and concrete inline backticked repo paths across docs/ and .agents/."""
    errors: list[str] = []
    link_pattern = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")

    canonical_docs = _iter_canonical_docs()
    harness_docs = _iter_harness_markdown()
    files_to_check: list[Path] = [AGENTS_FILE] + canonical_docs + harness_docs

    for doc in files_to_check:
        if not doc.exists():
            continue
        rel_doc = doc.relative_to(ROOT).as_posix()
        text = doc.read_text(encoding="utf-8-sig")

        # 1. Markdown [label](url) links
        for match in link_pattern.finditer(text):
            url = match.group(2).strip()
            if url.startswith("file:///"):
                clean_path = url.replace("file:///", "").split("#")[0]
                target = Path(clean_path)
                if not target.exists() and f"/{ROOT.name}/" in f"/{clean_path}":
                    target = ROOT / clean_path.split(f"{ROOT.name}/", 1)[1]
                if not target.exists():
                    errors.append(f"{rel_doc}: Broken file:// link to {url}")
            elif not url.startswith(("http://", "https://", "#", "mailto:")):
                clean_rel = url.split("#")[0]
                if clean_rel:
                    target = (doc.parent / clean_rel).resolve()
                    if not target.exists():
                        errors.append(f"{rel_doc}: Broken relative link to {url}")

        # 2. Concrete backticked repo paths outside code fences & historical forensic dumps
        if rel_doc.startswith("docs/change/"):
            continue
        prose = _strip_fenced_code(text)
        for m in BACKTICK_PATH_RE.finditer(prose):
            raw_token = m.group(1).strip().rstrip(".,;:")
            if any(skip in raw_token for skip in SKIP_BACKTICK_TOKENS):
                continue
            # Ignore numeric range shorthands (e.g. `.agents/agents/01..09.md`) and generic placeholders
            if re.search(r"\d\.\.\d", raw_token):
                continue
            if raw_token.endswith("/dir") or "/<topic>" in raw_token or "/<name>" in raw_token:
                continue
            clean_token = raw_token.split(":", 1)[0].split("#", 1)[0].rstrip("/")
            if not clean_token:
                continue
            # Ignore illustrative examples of forbidden/legacy paths documented cleanly as non-existent
            line_start = prose.rfind("\n", 0, m.start()) + 1
            line_end = prose.find("\n", m.end())
            line_ctx = prose[line_start : (len(prose) if line_end == -1 else line_end)].lower()
            if any(w in line_ctx for w in ("never ", "banned", "missing", "deleted", "legacy ", "not ")):
                if "requirements" not in raw_token and not raw_token.startswith("docs/"):
                    continue
            target = ROOT / clean_token
            if not target.exists():
                errors.append(f"{rel_doc}: Dead repo path reference `{raw_token}`")

    return errors


def check_skills_docs_sync() -> list[str]:
    """Verify docs/core/SKILLS.md, SKILLS-INDEX.md, STRUCTURE.md & skills-vault/README.md match skills-lock.json."""
    errors: list[str] = []
    if not SKILLS_LOCK.exists():
        return [".agents/skills-lock.json missing (run commands/skills-manager.py index)"]

    try:
        lock = json.loads(SKILLS_LOCK.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return [f"Malformed .agents/skills-lock.json: {exc}"]

    soft_cap = int(lock.get("active_soft_limit", 50))
    skills = lock.get("skills") or {}
    active_count = sum(1 for v in skills.values() if v.get("location") == "active")
    vault_count = sum(1 for v in skills.values() if str(v.get("location", "")).startswith("vault/"))

    if SKILLS_INDEX.exists():
        idx_text = SKILLS_INDEX.read_text(encoding="utf-8-sig")
        expected_snippet = f"`{active_count}` / `{soft_cap}`"
        if expected_snippet not in idx_text or f"`{vault_count}`" not in idx_text:
            errors.append(
                f"docs/generated/SKILLS-INDEX.md count mismatch vs .agents/skills-lock.json ({active_count}/{soft_cap} active, {vault_count} cold)"
            )
    else:
        errors.append("docs/generated/SKILLS-INDEX.md missing (run commands/skills-manager.py index)")

    for doc in (SKILLS_DOC, VAULT_README, STRUCTURE_DOC):
        if not doc.exists():
            continue
        rel = doc.relative_to(ROOT).as_posix()
        txt = doc.read_text(encoding="utf-8-sig")
        if re.search(r"<=\s*35\b|35\s*(?:recommended\s+)?active\s+cap", txt, re.IGNORECASE):
            errors.append(f"{rel}: Stale 35-skill cap reference (canonical active_soft_limit={soft_cap})")
        m_cap = re.search(r"<=\s*(\d+)\s*(?:soft\s+)?cap", txt, re.IGNORECASE)
        if m_cap and int(m_cap.group(1)) != soft_cap:
            errors.append(f"{rel}: Cap '<= {m_cap.group(1)}' != active_soft_limit ({soft_cap})")
        # Catch stale hardcoded Active/Cold counts when skills-lock count changes
        m_act = re.search(r"(?<![.\w])`?(\d+)`?\s+Active(?:\s+Deep)?\s+Skills?", txt, re.IGNORECASE)
        if m_act and int(m_act.group(1)) != active_count:
            errors.append(f"{rel}: Hardcoded active skill count ({m_act.group(1)}) != lockfile ({active_count}); defer count to SKILLS-INDEX.md")
        m_cold = re.search(r"(?<![.\w])`?(\d+)`?\+?\s+Cold\s+Vault", txt, re.IGNORECASE)
        if m_cold and int(m_cold.group(1)) != vault_count:
            errors.append(f"{rel}: Hardcoded cold skill count ({m_cold.group(1)}) != lockfile ({vault_count}); defer count to SKILLS-INDEX.md")

    return errors


def main() -> int:
    print("Verifying Project Knowledge Base Integrity...")
    all_errors: list[str] = []

    all_errors.extend(check_registered_docs())
    all_errors.extend(check_state_size())
    all_errors.extend(check_markdown_links())
    all_errors.extend(check_skills_docs_sync())

    if all_errors:
        print("\n[FAIL] Project Knowledge Base Verification Failed:")
        for err in all_errors:
            print(f"  - {err}")
        return 1

    print("\n[PASS] Project Knowledge Base Verification Passed:")
    print("  - All canonical topic docs are registered by exact path in docs/core/START-HERE.md")
    print(f"  - docs/core/STATE.md working memory is lean (<={MAX_STATE_LINES} lines)")
    print("  - Markdown & inline repo links across AGENTS.md, docs/, and .agents/ resolve cleanly")
    print("  - Skill Vault docs/SKILLS-INDEX.md parity verified cleanly")
    return 0


if __name__ == "__main__":
    sys.exit(main())
