"""Unified repo-local Skill Vault Manager for 100+ scale without token bloat.

Enforces ONE canonical skills ecosystem inside `.agents/`:
  - `.agents/skills/<name>/`                Active skills (discovered at session boot)
  - `.agents/skills-vault/<cat>/<name>/`    Cold vault (zero boot-token cost while unmounted)
  - `.agents/skills-lock.json`              Provenance, scope (`universal`|`project`), category & token budget
  - `docs/generated/SKILLS-INDEX.md`        Auto-generated inventory (zero manual SKILLS.md tables)

Usage:
  python commands/skills-manager.py list
  python commands/skills-manager.py index
  python commands/skills-manager.py doctor [--check]
  python commands/skills-manager.py mount <name_or_category...>
  python commands/skills-manager.py unmount <name_or_category...> [--category <cat>]
  python commands/skills-manager.py install <local_path_or_npx_pkg> [--category general] [--scope universal|project] [--cold] [--from-npx]
  python commands/skills-manager.py set-scope <skill_name> <universal|project>
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ACTIVE_DIR = ROOT / ".agents" / "skills"
VAULT_DIR = ROOT / ".agents" / "skills-vault"
LOCK_FILE = ROOT / ".agents" / "skills-lock.json"
INDEX_FILE = ROOT / "docs" / "generated" / "SKILLS-INDEX.md"
STAGE_ROOT = ROOT / ".qc-tmp" / "skill-stage"

ACTIVE_SOFT_LIMIT = 50
MAX_DESC_CHARS = 300
CATEGORIES = ["architecture", "frontend", "backend-db", "testing-browser", "security", "design", "domain", "vendor", "general"]

PROJECT_SPECIFIC_DEFAULTS = {
    "malaysian-motor-insurance",
    "postgres-ledger-migrations",
    "design2-pdf-parity",
}

DEFAULT_CATEGORIES = {
    "system-design-and-architecture": "architecture",
    "clean-code-and-refactoring": "architecture",
    "domain-interrogation-and-reality-gate": "architecture",
    "parallel-variant-tournament": "architecture",
    "postgres-ledger-migrations": "backend-db",
    "agent-browser": "testing-browser",
    "playwright": "testing-browser",
    "playwright-automation-fill-in-form": "testing-browser",
    "playwright-best-practices": "testing-browser",
    "playwright-cli": "testing-browser",
    "playwright-explore-website": "testing-browser",
    "webapp-testing": "testing-browser",
    "python-testing": "testing-browser",
    "test-driven-development": "testing-browser",
    "edge-case-and-scenario-matrix": "testing-browser",
    "enterprise-product-ui": "design",
    "apple-design": "design",
    "web-design-guidelines": "design",
    "frontend-design": "frontend",
    "design-taste-frontend": "frontend",
    "gsap-framer-scroll-animation": "frontend",
    "shadcn": "frontend",
    "design2-pdf-parity": "domain",
    "malaysian-motor-insurance": "domain",
    "security-best-practices": "security",
    "security-threat-model": "security",
    "company-dispatch": "general",
    "using-superpowers": "general",
    "brainstorming": "general",
    "systematic-debugging": "general",
    "writing-plans": "general",
    "verification-before-completion": "general",
    "requesting-code-review": "general",
    "receiving-code-review": "general",
    "finishing-a-development-branch": "general",
    "dispatching-parallel-agents": "general",
    "live-reality-and-deprecation-gate": "general",
}

DEFAULT_SOURCES = {
    "company-dispatch": "risklocker-custom",
    "enterprise-product-ui": "risklocker-custom",
    "malaysian-motor-insurance": "risklocker-custom",
    "postgres-ledger-migrations": "risklocker-custom",
    "design2-pdf-parity": "risklocker-custom",
    "system-design-and-architecture": "risklocker-custom",
    "clean-code-and-refactoring": "risklocker-custom",
    "domain-interrogation-and-reality-gate": "risklocker-custom",
    "parallel-variant-tournament": "risklocker-custom",
    "edge-case-and-scenario-matrix": "risklocker-custom",
    "live-reality-and-deprecation-gate": "risklocker-custom",
    "python-testing": "risklocker-custom",
    "playwright-best-practices": "risklocker-custom",
    "agent-browser": "risklocker-custom",
    "shadcn": "risklocker-custom+radix",
    "web-design-guidelines": "vercel+risklocker",
    "using-superpowers": "obra/superpowers+risklocker",
    "brainstorming": "obra/superpowers+risklocker",
    "writing-plans": "obra/superpowers+risklocker",
    "systematic-debugging": "obra/superpowers",
    "test-driven-development": "obra/superpowers",
    "verification-before-completion": "obra/superpowers",
    "requesting-code-review": "obra/superpowers",
    "receiving-code-review": "obra/superpowers",
    "finishing-a-development-branch": "obra/superpowers",
    "dispatching-parallel-agents": "obra/superpowers",
    "security-best-practices": "curated-global",
    "security-threat-model": "curated-global",
    "webapp-testing": "curated-global+risklocker",
    "playwright": "curated-global+risklocker",
    "frontend-design": "curated-global",
    "apple-design": "curated-global",
    "design-taste-frontend": "curated-global",
    "gsap-framer-scroll-animation": "curated-global",
}

JUNK_DIRS = {"node_modules", ".venv", ".git", "__pycache__", ".cache"}
STRAY_SKILL_PARENTS = [
    ROOT / ".claude" / "skills",
    ROOT / ".cursor" / "skills",
    ROOT / ".codex" / "skills",
    ROOT / ".opencode" / "skills",
]


def is_reparse_or_link(path: Path) -> bool:
    if path.is_symlink():
        return True
    try:
        return bool(os.lstat(path).st_file_attributes & 0x0400)
    except (AttributeError, OSError):
        return False


def remove_safe(path: Path) -> None:
    if not path.exists() and not is_reparse_or_link(path):
        return
    if is_reparse_or_link(path):
        try:
            path.rmdir()
        except OSError:
            path.unlink()
        return
    if path.is_file():
        path.unlink()
        return
    for child in list(path.iterdir()):
        remove_safe(child)
    path.rmdir()


def parse_frontmatter(skill_md: Path) -> tuple[dict[str, str], list[str]]:
    errors: list[str] = []
    if not skill_md.exists():
        return {}, ["Missing SKILL.md"]
    text = skill_md.read_text(encoding="utf-8-sig", errors="replace")
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, ["Missing YAML frontmatter opening '---'"]

    end_idx = None
    for idx in range(1, len(lines)):
        if lines[idx].strip() == "---":
            end_idx = idx
            break
    if end_idx is None:
        return {}, ["Unterminated YAML frontmatter"]

    fm_lines = lines[1:end_idx]
    meta: dict[str, str] = {}
    i = 0
    while i < len(fm_lines):
        line = fm_lines[i]
        m = re.match(r"^([A-Za-z0-9_-]+)\s*:\s*(.*)$", line)
        if not m:
            i += 1
            continue
        key, raw_val = m.group(1).strip(), m.group(2).strip()
        if raw_val in {">-", ">", "|-", "|"}:
            block: list[str] = []
            i += 1
            while i < len(fm_lines) and (fm_lines[i].startswith((" ", "\t")) or not fm_lines[i].strip()):
                if fm_lines[i].strip():
                    block.append(fm_lines[i].strip())
                i += 1
            meta[key] = " ".join(block).strip()
            continue
        meta[key] = raw_val.strip("\"'")
        i += 1

    folder_name = skill_md.parent.name
    if not meta.get("name"):
        errors.append("Missing frontmatter 'name'")
    elif meta["name"] != folder_name:
        errors.append(f"Frontmatter name '{meta['name']}' != folder '{folder_name}'")

    desc = meta.get("description", "")
    if not desc:
        errors.append("Missing frontmatter 'description'")
    elif len(desc) > MAX_DESC_CHARS:
        errors.append(f"Description too long ({len(desc)} > {MAX_DESC_CHARS} chars; bloats boot tokens)")

    return meta, errors


def load_lock() -> dict:
    if LOCK_FILE.exists():
        try:
            data = json.loads(LOCK_FILE.read_text(encoding="utf-8"))
            if isinstance(data, dict) and isinstance(data.get("skills"), dict):
                return data
        except json.JSONDecodeError:
            pass
    return {"schema_version": "1.0", "active_soft_limit": ACTIVE_SOFT_LIMIT, "skills": {}}


def scan_skills_on_disk() -> list[tuple[str, str, str, Path, dict[str, str], list[str]]]:
    """Return [(name, tier='active'|'vault', category, path, meta, errors)]."""
    results: list[tuple[str, str, str, Path, dict[str, str], list[str]]] = []

    if ACTIVE_DIR.exists():
        for d in sorted(ACTIVE_DIR.iterdir()):
            if not d.is_dir() or d.name.startswith("."):
                continue
            meta, errs = parse_frontmatter(d / "SKILL.md")
            results.append((d.name, "active", DEFAULT_CATEGORIES.get(d.name, "general"), d, meta, errs))

    if VAULT_DIR.exists():
        for cat_dir in sorted(VAULT_DIR.iterdir()):
            if not cat_dir.is_dir() or cat_dir.name.startswith("."):
                continue
            if (cat_dir / "SKILL.md").exists():
                # Direct folder under skills-vault treated as category 'general'
                meta, errs = parse_frontmatter(cat_dir / "SKILL.md")
                results.append((cat_dir.name, "vault", "general", cat_dir, meta, errs))
                continue
            for skill_dir in sorted(cat_dir.iterdir()):
                if not skill_dir.is_dir() or skill_dir.name.startswith("."):
                    continue
                meta, errs = parse_frontmatter(skill_dir / "SKILL.md")
                results.append((skill_dir.name, "vault", cat_dir.name, skill_dir, meta, errs))

    return results


def build_lock_payload(existing_lock: dict) -> dict:
    now = datetime.datetime.now().astimezone().isoformat(timespec="seconds")
    old_skills = existing_lock.get("skills") or {}
    new_skills: dict[str, dict] = {}

    for name, tier, disk_cat, path, meta, _errs in scan_skills_on_disk():
        prev = old_skills.get(name) or {}
        cat = disk_cat if tier == "vault" else str(DEFAULT_CATEGORIES.get(name) or prev.get("category") or "general")
        default_scope = "project" if name in PROJECT_SPECIFIC_DEFAULTS else "universal"
        scope = str(prev.get("scope") or meta.get("scope") or default_scope)
        prev_src = str(prev.get("source") or "")
        if name in DEFAULT_SOURCES and prev_src in {"", "local-repo", "superpowers"}:
            source = DEFAULT_SOURCES[name]
        else:
            source = str(prev_src or DEFAULT_SOURCES.get(name, "local-repo"))
        desc = meta.get("description", "")
        desc_chars = len(desc)
        est_tokens = max(12, round((len(name) + desc_chars + 24) / 4)) if tier == "active" else 0
        rel_path = path.relative_to(ROOT).as_posix()
        entry = {
            "location": "active" if tier == "active" else f"vault/{cat}",
            "path": rel_path,
            "category": cat,
            "scope": scope,
            "source": source,
            "description_chars": desc_chars,
            "est_boot_tokens": est_tokens,
            "updated_at": str(prev.get("updated_at") or now),
        }
        if prev and (
            prev.get("location") != entry["location"]
            or prev.get("description_chars") != desc_chars
            or prev.get("scope") != scope
        ):
            entry["updated_at"] = now
        new_skills[name] = entry

    return {
        "schema_version": "1.0",
        "active_soft_limit": ACTIVE_SOFT_LIMIT,
        "skills": new_skills,
    }


def render_index_markdown(lock_data: dict) -> str:
    skills = lock_data.get("skills") or {}
    active = [(k, v) for k, v in sorted(skills.items()) if v["location"] == "active"]
    vault = [(k, v) for k, v in sorted(skills.items()) if v["location"].startswith("vault/")]
    total_tokens = sum(int(v.get("est_boot_tokens", 0)) for _, v in active)

    lines = [
        "# Auto-Generated Skill Inventory (`docs/generated/SKILLS-INDEX.md`)",
        "",
        "> Managed automatically by [`commands/skills-manager.py`](../../commands/skills-manager.py). Never edit manually.",
        "",
        "## Budget Snapshot",
        "",
        f"- **Active Mounted Skills (`.agents/skills/`):** `{len(active)}` / `{ACTIVE_SOFT_LIMIT}` soft budget (`~{total_tokens}` estimated boot prompt tokens)",
        f"- **Cold Vault Skills (`.agents/skills-vault/`):** `{len(vault)}` (`0` boot prompt tokens until mounted)",
        f"- **Universal Scope Skills (`init-ai-factory.py`):** `{sum(1 for v in skills.values() if v.get('scope') == 'universal')}`",
        "",
        "## Active Mounted Skills",
        "",
        "| Skill | Category | Scope | Source | Est. Tokens |",
        "| :--- | :--- | :--- | :--- | ---: |",
    ]
    for name, info in active:
        lines.append(
            f"| `{name}` | `{info['category']}` | `{info['scope']}` | `{info['source']}` | ~{info['est_boot_tokens']} |"
        )

    lines.extend(["", "## Cold Vault Skills", ""])
    if not vault:
        lines.append("_No skills currently parked in `.agents/skills-vault/`. Use `unmount` or `install --cold` to store extra packs here with zero boot token cost._")
    else:
        lines.extend([
            "| Skill | Category | Scope | Source | Location |",
            "| :--- | :--- | :--- | :--- | :--- |",
        ])
        for name, info in vault:
            lines.append(
                f"| `{name}` | `{info['category']}` | `{info['scope']}` | `{info['source']}` | `{info['path']}` |"
            )

    lines.append("")
    return "\n".join(lines)


def write_lock_and_index(lock_data: dict) -> None:
    LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)
    LOCK_FILE.write_text(json.dumps(lock_data, indent=2) + "\n", encoding="utf-8")
    INDEX_FILE.parent.mkdir(parents=True, exist_ok=True)
    INDEX_FILE.write_text(render_index_markdown(lock_data), encoding="utf-8")


def sanitize_skill_tree(skill_dir: Path) -> list[str]:
    removed: list[str] = []
    for root_dir, dirs, _files in os.walk(skill_dir, topdown=True):
        keep: list[str] = []
        for d in dirs:
            if d in JUNK_DIRS:
                target = Path(root_dir) / d
                remove_safe(target)
                removed.append(d)
            else:
                keep.append(d)
        dirs[:] = keep
    return removed


def cmd_list(_args: argparse.Namespace) -> int:
    lock = build_lock_payload(load_lock())
    skills = lock["skills"]
    active = [(k, v) for k, v in sorted(skills.items()) if v["location"] == "active"]
    vault = [(k, v) for k, v in sorted(skills.items()) if v["location"].startswith("vault/")]
    tokens = sum(int(v.get("est_boot_tokens", 0)) for _, v in active)

    print(f"Active Mounted ({len(active)}/{ACTIVE_SOFT_LIMIT} soft cap, ~{tokens} est. boot tokens):")
    for name, info in active:
        print(f"  [active] {name:<38} cat={info['category']:<16} scope={info['scope']:<10} (~{info['est_boot_tokens']} tok)")
    if len(active) > ACTIVE_SOFT_LIMIT:
        print(f"\n[WARN] Active skills ({len(active)}) exceed soft cap ({ACTIVE_SOFT_LIMIT}). Unmount unused packs to .agents/skills-vault/ to protect model reasoning.")

    print(f"\nCold Vault ({len(vault)}, 0 boot tokens):")
    if not vault:
        print("  (empty)")
    else:
        for name, info in vault:
            print(f"  [vault ] {name:<38} cat={info['category']:<16} scope={info['scope']:<10} {info['path']}")
    return 0


def cmd_index(_args: argparse.Namespace) -> int:
    lock = build_lock_payload(load_lock())
    write_lock_and_index(lock)
    print(f"[PASS] Indexed {len(lock['skills'])} skills -> .agents/skills-lock.json & docs/generated/SKILLS-INDEX.md")
    return 0


def cmd_doctor(args: argparse.Namespace) -> int:
    issues: list[str] = []
    fixed: list[str] = []
    check_only = bool(args.check)

    # 1. Detect stray non-junction skills or dangling links in IDE skill folders
    for parent in STRAY_SKILL_PARENTS:
        if not parent.exists() and not is_reparse_or_link(parent):
            continue
        if is_reparse_or_link(parent):
            try:
                if parent.resolve() != ACTIVE_DIR.resolve():
                    msg = f"Invalid top-level skill junction {parent.relative_to(ROOT).as_posix()}"
                    if check_only:
                        issues.append(msg)
                    else:
                        remove_safe(parent)
                        fixed.append(f"Removed {msg}")
            except OSError:
                msg = f"Dangling top-level skill junction {parent.relative_to(ROOT).as_posix()}"
                if check_only:
                    issues.append(msg)
                else:
                    remove_safe(parent)
                    fixed.append(f"Removed {msg}")
            continue

        for entry in list(parent.iterdir()):
            rel = entry.relative_to(ROOT).as_posix()
            if is_reparse_or_link(entry):
                if not entry.exists():
                    if check_only:
                        issues.append(f"Dangling skill junction: {rel}")
                    else:
                        remove_safe(entry)
                        fixed.append(f"Cleaned dangling junction {rel}")
                continue
            if entry.is_dir() and (entry / ".managed-by-sync-agent-bridges").exists():
                if check_only:
                    issues.append(f"Legacy copied skill mirror: {rel}")
                else:
                    remove_safe(entry)
                    fixed.append(f"Removed duplicate bridge copy {rel}")
                continue
            if entry.is_dir() and (entry / "SKILL.md").exists():
                dst = ACTIVE_DIR / entry.name
                if check_only:
                    issues.append(f"Stray skill outside .agents/skills/: {rel} (run skills-manager.py doctor to consolidate)")
                else:
                    if not dst.exists():
                        ACTIVE_DIR.mkdir(parents=True, exist_ok=True)
                        shutil.move(str(entry), str(dst))
                        sanitize_skill_tree(dst)
                        fixed.append(f"Consolidated stray skill {rel} -> .agents/skills/{entry.name}")
                    else:
                        issues.append(f"Duplicate stray skill {rel} conflicts with .agents/skills/{entry.name}")

    # 2. Validate SKILL.md frontmatter + sanitize junk inside .agents/
    scanned = scan_skills_on_disk()
    seen_names: dict[str, Path] = {}
    active_count = 0
    for name, tier, _cat, path, _meta, errs in scanned:
        if tier == "active":
            active_count += 1
        if name in seen_names:
            issues.append(f"Duplicate skill '{name}' in both {seen_names[name].relative_to(ROOT)} and {path.relative_to(ROOT)}")
        seen_names[name] = path
        for err in errs:
            issues.append(f"{path.relative_to(ROOT).as_posix()}: {err}")
        if not check_only:
            removed = sanitize_skill_tree(path)
            if removed:
                fixed.append(f"Stripped vendor junk ({', '.join(removed)}) inside {path.relative_to(ROOT).as_posix()}")

    # 3. Verify lockfile & index freshness
    expected_lock = build_lock_payload(load_lock())
    expected_index = render_index_markdown(expected_lock).replace("\r\n", "\n")

    if check_only:
        cur_lock = LOCK_FILE.read_text(encoding="utf-8") if LOCK_FILE.exists() else ""
        # Compare ignoring updated_at timestamp noise if same keys/locations
        cur_parsed = load_lock() if LOCK_FILE.exists() else {}
        if cur_parsed.get("active_soft_limit") != ACTIVE_SOFT_LIMIT:
            issues.append(
                f".agents/skills-lock.json active_soft_limit ({cur_parsed.get('active_soft_limit')}) != {ACTIVE_SOFT_LIMIT} (run skills-manager.py index)"
            )
        if cur_parsed.get("skills", {}).keys() != expected_lock["skills"].keys():
            issues.append(".agents/skills-lock.json skill set is out of sync (run skills-manager.py index)")
        else:
            for k, v in expected_lock["skills"].items():
                cur_v = cur_parsed["skills"].get(k, {})
                if (
                    cur_v.get("location") != v["location"]
                    or cur_v.get("scope") != v["scope"]
                    or cur_v.get("category") != v["category"]
                    or cur_v.get("path") != v["path"]
                ):
                    issues.append(f".agents/skills-lock.json drift for '{k}' (run skills-manager.py index)")
        cur_idx = INDEX_FILE.read_text(encoding="utf-8").replace("\r\n", "\n") if INDEX_FILE.exists() else ""
        if cur_idx != expected_index:
            issues.append("docs/generated/SKILLS-INDEX.md is stale (run skills-manager.py index)")
    else:
        write_lock_and_index(expected_lock)

    for item in fixed:
        print(f"[FIXED] {item}")
    if active_count > ACTIVE_SOFT_LIMIT:
        print(f"[WARN] Active skills ({active_count}) exceed soft limit ({ACTIVE_SOFT_LIMIT}); unmount dormant skills into .agents/skills-vault/.")

    if issues:
        print("[FAIL] Skill Vault Doctor found issues:")
        for err in issues:
            print(f"  - {err}")
        return 1

    print(f"[PASS] Skill Vault clean ({len(expected_lock['skills'])} skills indexed; {active_count}/{ACTIVE_SOFT_LIMIT} active).")
    return 0


def cmd_mount(args: argparse.Namespace) -> int:
    lock = load_lock()
    skills = lock.get("skills") or {}
    moved: list[str] = []

    for target in args.targets:
        cat_dir = VAULT_DIR / target
        if cat_dir.exists() and cat_dir.is_dir() and not (cat_dir / "SKILL.md").exists():
            # Mount whole category
            for skill_dir in sorted(cat_dir.iterdir()):
                if skill_dir.is_dir() and (skill_dir / "SKILL.md").exists():
                    dst = ACTIVE_DIR / skill_dir.name
                    if dst.exists():
                        raise RuntimeError(f"Cannot mount '{skill_dir.name}': already exists in .agents/skills/")
                    ACTIVE_DIR.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(skill_dir), str(dst))
                    if skill_dir.name in skills:
                        skills[skill_dir.name]["category"] = target
                    moved.append(f"{target}/{skill_dir.name}")
            if not any(cat_dir.iterdir()):
                cat_dir.rmdir()
            continue

        # Mount single skill by name
        found: Path | None = None
        found_cat = "general"
        if VAULT_DIR.exists():
            for match in VAULT_DIR.rglob("SKILL.md"):
                if match.parent.name == target:
                    found = match.parent
                    rel_parts = match.parent.relative_to(VAULT_DIR).parts
                    found_cat = rel_parts[0] if len(rel_parts) >= 2 else "general"
                    break
        if not found:
            if (ACTIVE_DIR / target).exists():
                print(f"[INFO] '{target}' is already mounted in .agents/skills/.")
                continue
            print(f"[FAIL] Skill or category '{target}' not found in .agents/skills-vault/.")
            return 1

        dst = ACTIVE_DIR / found.name
        if dst.exists():
            print(f"[FAIL] Conflict: .agents/skills/{found.name} already exists.")
            return 1
        ACTIVE_DIR.mkdir(parents=True, exist_ok=True)
        shutil.move(str(found), str(dst))
        skills.setdefault(found.name, {})["category"] = found_cat
        moved.append(f"{found_cat}/{found.name}")

    updated = build_lock_payload(lock)
    write_lock_and_index(updated)
    print(f"[PASS] Mounted {len(moved)} skill(s) into .agents/skills/: {', '.join(moved) if moved else 'none'}")
    return 0


def cmd_unmount(args: argparse.Namespace) -> int:
    lock = load_lock()
    skills = lock.get("skills") or {}
    moved: list[str] = []

    for target in args.targets:
        src = ACTIVE_DIR / target
        if not src.exists():
            # Allow unmounting by category tag recorded in lockfile
            cat_matches = [
                name for name, info in skills.items()
                if info.get("location") == "active" and info.get("category") == target and (ACTIVE_DIR / name).exists()
            ]
            if not cat_matches:
                print(f"[FAIL] Active skill or category '{target}' not found in .agents/skills/.")
                return 1
            for name in cat_matches:
                s_src = ACTIVE_DIR / name
                cat = args.category or target
                dst = VAULT_DIR / cat / name
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(s_src), str(dst))
                moved.append(f"{name} -> {cat}")
            continue

        cat = args.category or str((skills.get(target) or {}).get("category") or DEFAULT_CATEGORIES.get(target, "general"))
        if cat not in CATEGORIES:
            cat = re.sub(r"[^a-z0-9_-]", "-", cat.lower()).strip("-") or "general"
        dst = VAULT_DIR / cat / target
        if dst.exists():
            print(f"[FAIL] Conflict: {dst.relative_to(ROOT)} already exists.")
            return 1
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dst))
        moved.append(f"{target} -> {cat}")

    updated = build_lock_payload(lock)
    write_lock_and_index(updated)
    print(f"[PASS] Unmounted {len(moved)} skill(s) to .agents/skills-vault/: {', '.join(moved)}")
    return 0


def cmd_install(args: argparse.Namespace) -> int:
    raw_src = args.source.strip()
    if any(flag in raw_src.split() for flag in ("-g", "--global")):
        print("[DENY] Repo-Local Policy: global installs (-g / --global) are forbidden by default.")
        return 1

    stage_dir = STAGE_ROOT / datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    stage_dir.mkdir(parents=True, exist_ok=True)
    installed_names: list[str] = []
    source_label = raw_src

    try:
        src_path = Path(raw_src)
        candidates: list[Path] = []
        if args.from_npx:
            npx_cmd = ["npx.cmd" if os.name == "nt" else "npx", "--yes", "skills", "add", raw_src, "-y", "--agent", "universal"]
            proc = subprocess.run(npx_cmd, cwd=str(stage_dir), capture_output=True, text=True)
            if proc.returncode != 0:
                print(proc.stdout)
                print(proc.stderr, file=sys.stderr)
                return proc.returncode
            staged_skills = stage_dir / ".agents" / "skills"
            if staged_skills.exists():
                candidates = [p for p in staged_skills.iterdir() if p.is_dir() and (p / "SKILL.md").exists()]
            source_label = f"skills-cli:{raw_src}"
        elif src_path.exists():
            if (src_path / "SKILL.md").exists():
                candidates = [src_path]
            else:
                candidates = [p for p in src_path.rglob("SKILL.md")]
                candidates = [p.parent for p in candidates]
            source_label = f"local:{src_path.name}"
        else:
            print(f"[FAIL] Source path '{raw_src}' not found. Pass an existing local folder or pass --from-npx <owner/repo>.")
            return 1

        if not candidates:
            print("[FAIL] No valid SKILL.md directories discovered in source.")
            return 1

        if args.name and len(candidates) > 1:
            print("[FAIL] --name can only be passed when installing a single skill.")
            return 1

        lock = load_lock()
        for cand in candidates:
            skill_name = args.name if (args.name and len(candidates) == 1) else cand.name
            meta, errs = parse_frontmatter(cand / "SKILL.md")
            if args.name and len(candidates) == 1:
                if meta.get("name") == args.name:
                    errs = [e for e in errs if "!= folder" not in e]
                else:
                    errs = [
                        *(e for e in errs if "!= folder" not in e),
                        f"SKILL.md frontmatter name '{meta.get('name', '')}' != --name '{args.name}'",
                    ]
            if errs:
                print(f"[FAIL] {cand.name}: {'; '.join(errs)}")
                return 1

            dest = (VAULT_DIR / args.category / skill_name) if args.cold else (ACTIVE_DIR / skill_name)
            dest.parent.mkdir(parents=True, exist_ok=True)
            if dest.exists():
                remove_safe(dest)
            shutil.copytree(cand, dest, ignore=shutil.ignore_patterns(*JUNK_DIRS))
            sanitize_skill_tree(dest)

            lock.setdefault("skills", {})[skill_name] = {
                "location": f"vault/{args.category}" if args.cold else "active",
                "category": args.category,
                "scope": args.scope,
                "source": source_label,
                "description_chars": len(meta.get("description", "")),
            }
            installed_names.append(skill_name)

        updated = build_lock_payload(lock)
        write_lock_and_index(updated)
    finally:
        if stage_dir.exists():
            remove_safe(stage_dir)

    target_tier = f".agents/skills-vault/{args.category}/" if args.cold else ".agents/skills/"
    print(f"[PASS] Installed {len(installed_names)} skill(s) into {target_tier}: {', '.join(installed_names)}")
    return 0


def cmd_set_scope(args: argparse.Namespace) -> int:
    lock = build_lock_payload(load_lock())
    if args.skill not in lock["skills"]:
        print(f"[FAIL] Skill '{args.skill}' not found in repository.")
        return 1
    lock["skills"][args.skill]["scope"] = args.scope
    write_lock_and_index(lock)
    print(f"[PASS] Updated scope for '{args.skill}' -> '{args.scope}'")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Manage Risklocker's unified repo-local Skill Vault.")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("list", help="Show active mounted skills, cold vault skills, and boot token estimate.")
    sub.add_parser("index", help="Regenerate .agents/skills-lock.json and docs/generated/SKILLS-INDEX.md.")

    doc_p = sub.add_parser("doctor", help="Audit/repair stray skill copies, broken junctions, YAML, and index drift.")
    doc_p.add_argument("--check", action="store_true", help="Report issues without mutating files.")

    mnt_p = sub.add_parser("mount", help="Move skill(s) or whole vault category into .agents/skills/.")
    mnt_p.add_argument("targets", nargs="+", help="Skill name(s) or vault category name(s).")

    unm_p = sub.add_parser("unmount", help="Park active skill(s) into .agents/skills-vault/ (zero boot tokens).")
    unm_p.add_argument("targets", nargs="+", help="Skill name(s) or category name.")
    unm_p.add_argument("--category", default=None, help="Target vault category folder.")

    inst_p = sub.add_parser("install", help="Install local or staged npx skills strictly into this repository.")
    inst_p.add_argument("source", help="Local skill directory/bundle path, or package spec with --from-npx.")
    inst_p.add_argument("--name", default=None, help="Override skill name (single-skill source only).")
    inst_p.add_argument("--category", default="general", choices=CATEGORIES, help="Category metadata / cold vault folder.")
    inst_p.add_argument("--scope", default="universal", choices=["universal", "project"], help="Portability scope for init-ai-factory.py.")
    inst_p.add_argument("--cold", action="store_true", help="Install directly into cold .agents/skills-vault/ (0 boot tokens).")
    inst_p.add_argument("--from-npx", action="store_true", help="Stage via sandboxed `npx skills add` in .qc-tmp/ without global writes.")

    scp_p = sub.add_parser("set-scope", help="Mark an indexed skill as 'universal' or 'project'.")
    scp_p.add_argument("skill", help="Skill folder name.")
    scp_p.add_argument("scope", choices=["universal", "project"], help="Portability classification.")

    args = parser.parse_args()
    handlers = {
        "list": cmd_list,
        "index": cmd_index,
        "doctor": cmd_doctor,
        "mount": cmd_mount,
        "unmount": cmd_unmount,
        "install": cmd_install,
        "set-scope": cmd_set_scope,
    }
    return handlers[args.command](args)


if __name__ == "__main__":
    raise SystemExit(main())

