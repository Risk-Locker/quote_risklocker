"""PreToolUse guardrail hook for Antigravity (.agents/hooks.json) and standalone verification.

Enforces:
  1. Fail-closed parsing on malformed stdin JSON.
  2. AGENTS.md §4 workspace containment across BOTH file-write tools AND shell writes
     (except verified Antigravity conversation artifacts).
  3. Active Code Freeze (.agents/.freeze.lock) blocking edits inside locked source subtrees
     (including shell redirection, cd+write, inline scripts, git apply/checkout, curl -o),
     and prompting confirmation (`force_ask`) for edits outside `allowed_prefixes`.
  4. Repo-local Agent Skills Policy (`Rule 04`) & explicit confirmation on destructive commands.
"""

from __future__ import annotations

import json
import os
import posixpath
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LOCK_FILE = ROOT / ".agents" / ".freeze.lock"

WRITE_TOOLS = {
    "write_file",
    "edit_file",
    "replace_file_content",
    "multi_replace_file_content",
    "write_to_file",
    "create_file",
    "patch_file",
    "delete_file",
    "rename_file",
    "move_file",
    "multi_edit",
    "notebookedit",
}
PATH_ARG_KEYS = (
    "Path",
    "TargetFile",
    "path",
    "file_path",
    "AbsolutePath",
    "target_file",
    "DestinationPath",
    "destination",
    "source",
    "SourcePath",
    "old_path",
    "new_path",
    "OldPath",
    "NewPath",
    "TargetPath",
    "target",
)
LIST_PATH_KEYS = ("paths", "files", "targets", "edits")

DESTRUCTIVE_CMD_PATTERNS = [
    re.compile(r"\bgit\s+push\b[\s\S]*?--force\b", re.IGNORECASE),
    re.compile(r"\bgit\s+reset\s+--hard\b", re.IGNORECASE),
    re.compile(r"\bDROP\s+(?:DATABASE|SCHEMA|TABLE)\b", re.IGNORECASE),
    re.compile(r"\bTRUNCATE\s+TABLE\b", re.IGNORECASE),
]

GLOBAL_INSTALL_PATTERNS = [
    re.compile(r"\b(?:npx(?:\.cmd)?\s+(?:--yes\s+)?)?skills\s+(?:add|install)\b", re.IGNORECASE),
    re.compile(r"\bgraphify\s+install\b", re.IGNORECASE),
    re.compile(
        r"(?:Copy-Item|Move-Item|New-Item|Set-Content|Out-File|cp|mv|mkdir|mklink|tee|>>?)\s*[\s\S]*"
        r"(?:~[\\/]\.|%USERPROFILE%[\\/]\.|\$HOME[\\/]\.|C:\\Users\\[^\\]+\\\.(?:gemini|claude|codex|copilot|agents|cursor))",
        re.IGNORECASE,
    ),
]

SHELL_WRITE_VERBS = re.compile(
    r"(?:Copy-Item|Move-Item|New-Item|Remove-Item|Set-Content|Add-Content|Out-File|Clear-Content|Rename-Item|Tee-Object|"
    r"-OutFile|"
    r"\bcp|\bmv|\brm|\brmdir|\bmkdir|\btee|\btouch|\btruncate|\bchmod|\bchown|\bln\s+-|\bdd\b|\bsed\s+-i|"
    r"\bcopy|\bxcopy|\brobocopy|\bmove|\bdel|\berase|\bren)\b"
    r"|(?<![-=<])>>?(?![=&>])",
    re.IGNORECASE,
)

INLINE_WRITER_PATTERNS = [
    re.compile(
        r"\b(?:python(?:3(?:\.\d+)?)?(?:\.exe)?|py(?:\.exe)?)\b[\s\S]*?(?:\s(?-i:-[BEIOqsSuvP]*c)\b|<<)[\s\S]*?"
        r"(?:open\(|write_text|write_bytes|shutil\.|os\.remove|os\.replace|os\.rename|os\.unlink|os\.mkdir|os\.makedirs|rmtree|mkdir|"
        r"\.(?:unlink|touch|rmdir|rename|replace|chmod|symlink_to|hardlink_to)\()",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:node|bun|deno|tsx|npx)(?:\.exe|\.cmd)?\b[\s\S]*?(?:\s(?:-e|-p|--eval(?:=|\b)|--print(?:=|\b)|eval\b)|<<)[\s\S]*?"
        r"(?:writeFile|appendFile|unlink|rmSync|mkdirSync|Bun\.write|Deno\.(?:writeTextFile|remove|mkdir|rename)|fs\.)",
        re.IGNORECASE,
    ),
    re.compile(r"\[(?:System\.)?IO\.(?:File|Directory)\]::(?:Write|Append|Copy|Move|Delete|Create)", re.IGNORECASE),
    re.compile(
        r"\bgit(?:\.exe)?(?:\s+(?:-[Cc]\s*\S+|-[A-Za-z](?:\s+[^-\s;|&]\S*)?|--[A-Za-z0-9_-]+(?:=\S+|\s+[^-\s;|&]\S*)?))*\s+"
        r"(?:apply\b|checkout\b[^|\r\n;&]*?\s--(?=\s|$)|restore\b|am\b|cherry-pick\b|revert\b|stash\s+pop\b|rm\b|mv\b|clean\b|reset\s+--hard\b)",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bcurl(?:\.exe)?\b[\s\S]*?(?:\s-(?!-)[A-Za-z]*[oO](?:\S*|\s+\S+)|\s--output(?:=|\s)\S+)|\bwget\b[\s\S]*?(?:\s-O\S*|\s--output-document(?:=|\s)\S+)",
        re.IGNORECASE,
    ),
]
INLINE_MUTATOR_EXPR_RE = re.compile(
    r"(?:open\(|write_text\(|write_bytes\(|shutil\.|os\.(?:remove|replace|rename|unlink|mkdir|makedirs)\(|rmtree\(|"
    r"\.(?:unlink|touch|rmdir|rename|replace|chmod|symlink_to|hardlink_to|mkdir)\(|"
    r"writeFile|appendFile|rmSync|mkdirSync|Bun\.write|Deno\.(?:writeTextFile|remove|mkdir|rename)|fs\.|"
    r"\[(?:System\.)?IO\.(?:File|Directory)\]::(?:Write|Append|Copy|Move|Delete|Create))",
    re.IGNORECASE,
)
INLINE_INTERP_BIN_RE = re.compile(
    r"\b(?:python(?:3(?:\.\d+)?)?(?:\.exe)?|py(?:\.exe)?|node|bun|deno|tsx)(?:\.exe|\.cmd)?\b",
    re.IGNORECASE,
)
HEREDOC_START_RE = re.compile(
    r"\b(?:python(?:3(?:\.\d+)?)?(?:\.exe)?|py(?:\.exe)?|node|bun|deno|tsx)(?:\.exe|\.cmd)?\b[^\r\n]*<<-?\s*['\"]?([A-Za-z0-9_]+)['\"]?",
    re.IGNORECASE,
)
QUOTED_URL_RE = re.compile(r"(['\"])([A-Za-z][A-Za-z0-9+.-]*://[^\s'\"\r\n]+)\1")
URL_TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z0-9+.-]*://[^\s;|&\"'`<>()]+(?:&[A-Za-z0-9_.~%-]+=[^\s;|&\"'`<>()]*)*")
ENCODED_PWSH_RE = re.compile(
    r"\b(?:pwsh|powershell)(?:\.exe)?\b[\s\S]*?\s-(?:e|ec|en|enc(?:o(?:d(?:e(?:d(?:c(?:o(?:m(?:m(?:a(?:n(?:d)?)?)?)?)?)?)?)?)?)?)?)\b",
    re.IGNORECASE,
)
EXT_ENV_OR_HOME_WRITE_RE = re.compile(
    r"(?:%(?:TEMP|TMP|USERPROFILE|APPDATA|LOCALAPPDATA|HOMEPATH|PROGRAMDATA|PUBLIC)%|"
    r"\$\{?env:(?:TEMP|TMP|USERPROFILE|APPDATA|LOCALAPPDATA|HOME|HOMEPATH|PROGRAMDATA|PUBLIC)\b\}?|"
    r"(?:^|[\s;|&=(,:>+])~(?:/|\s|$)|"
    r"\$\{?HOME\}?(?:/|$|\b)|"
    r"(?:^|[\s;|&=(,:>+])/(?:tmp|var|etc|Users|home|root|opt|mnt|cygdrive)(?:/[^\s;|&>\"'`(),]*)?)",
    re.IGNORECASE,
)
ABS_DRIVE_PATH_RE = re.compile(r"(?<![A-Za-z0-9_])[A-Za-z]:/(?!/)[^\s;|&>\"'`(),]+")
CD_WRAPPER_PREFIX_RE = re.compile(
    r"^(?:[\(\{&\s]|"
    r"cmd(?:\.exe)?(?:\s+/[A-Za-z0-9:_-]+)*\s+/[ck]\b|"
    r"(?:pwsh|powershell)(?:\.exe)?\b[^\r\n;&|]*?\s-(?:command|c)\b|"
    r"(?:bash|sh|zsh)\b[^\r\n;&|]*?\s-[A-Za-z]*c\b)+",
    re.IGNORECASE,
)
CD_SEGMENT_RE = re.compile(
    r"^\s*(?:cd|chdir|set-location|sl|push-location|pushd)(?:\s+(?:/d|-path|-literalpath|--))?\s+([^\s;|&>]+)",
    re.IGNORECASE,
)
POPD_SEGMENT_RE = re.compile(r"^\s*(?:popd|pop-location)\b", re.IGNORECASE)
FS_MUTATOR_SEGMENT_RE = re.compile(
    r"(?:Copy-Item|Move-Item|New-Item|Remove-Item|Set-Content|Add-Content|Out-File|Clear-Content|Rename-Item|Tee-Object|"
    r"-OutFile|"
    r"\brm|\brmdir|\bmkdir|\bmv|\bcp|\btouch|\btruncate|\bchmod|\bchown|\bdd\b|\bsed\s+-i|\bcopy|\bxcopy|\brobocopy|\bmove|\bdel|\berase|\bren|\bln)\b",
    re.IGNORECASE,
)
REDIR_TARGET_RE = re.compile(r"(?<![-=<])(?:\d|\*)?>>?(?![=&>(])\s*([^\s;|&\"'`<>()]+)")
TEE_CMD_TAIL_RE = re.compile(r"\btee\b([\s\S]*)$", re.IGNORECASE)
OPAQUE_PATCH_GIT_RE = re.compile(
    r"\bgit(?:\.exe)?(?:\s+(?:-[Cc]\s*\S+|-[A-Za-z](?:\s+\S+)?|--[A-Za-z0-9_-]+(?:=\S+)?))*\s+"
    r"(?:apply|am|cherry-pick|stash\s+pop)\b",
    re.IGNORECASE,
)


def _norm_case(s: str) -> str:
    return s.casefold() if os.name == "nt" else s


def load_freeze_config() -> tuple[bool, list[str], list[str]]:
    if not LOCK_FILE.exists():
        return False, [], []
    try:
        data = json.loads(LOCK_FILE.read_text(encoding="utf-8"))
        if not bool(data.get("enabled", True)):
            return False, [], []
        locked = [p.rstrip("/") + "/" for p in data.get("locked_prefixes", [])]
        allowed = [p.rstrip("/") + "/" for p in data.get("allowed_prefixes", [])]
        return True, locked, allowed
    except Exception:
        return True, ["backend/app/", "frontend/src/", "migrations/", "tests/"], []


def is_artifact_dir(target: Path, artifact_dir: str | None) -> bool:
    resolved_target = target.resolve()
    if artifact_dir:
        try:
            return resolved_target.is_relative_to(Path(str(artifact_dir)).resolve())
        except Exception:
            return False
    brain_root = (Path.home() / ".gemini" / "antigravity" / "brain").resolve()
    try:
        return resolved_target.is_relative_to(brain_root)
    except Exception:
        return False


def _extract_all_paths(args: dict, *, _depth: int = 0) -> list[str]:
    paths: list[str] = []
    seen: set[str] = set()

    def _add(val: object) -> None:
        if isinstance(val, str):
            trimmed = val.strip()
            if trimmed and trimmed not in seen:
                seen.add(trimmed)
                paths.append(trimmed)

    for key in PATH_ARG_KEYS:
        _add(args.get(key))

    if _depth < 2:
        for lkey in LIST_PATH_KEYS:
            seq = args.get(lkey)
            if isinstance(seq, (list, tuple)):
                for item in seq:
                    if isinstance(item, str):
                        _add(item)
                    elif isinstance(item, dict):
                        for nested in _extract_all_paths(item, _depth=_depth + 1):
                            _add(nested)
    return paths


def _evaluate_write_path(raw_path: str, artifact_dir: str | None) -> dict | None:
    target = Path(raw_path)
    if not target.is_absolute():
        target = ROOT / target
    resolved = target.resolve()

    if is_artifact_dir(resolved, artifact_dir):
        return None

    try:
        rel = resolved.relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return {
            "decision": "deny",
            "reason": f"AGENTS.md §4 violation: refusing write outside repository ({raw_path}). Use /.qc-tmp/ instead.",
        }

    freeze_enabled, locked_prefixes, allowed_prefixes = load_freeze_config()
    if not freeze_enabled:
        return None

    rel_cmp = _norm_case(rel)
    for prefix in locked_prefixes:
        if rel_cmp.startswith(_norm_case(prefix)) or rel_cmp == _norm_case(prefix.rstrip("/")):
            return {
                "decision": "deny",
                "reason": f"Code freeze active (.agents/.freeze.lock locks '{prefix}'): get explicit plan approval to lift freeze before editing {rel}.",
            }

    if allowed_prefixes and not any(
        rel_cmp.startswith(_norm_case(ap)) or rel_cmp == _norm_case(ap.rstrip("/")) for ap in allowed_prefixes
    ):
        return {
            "decision": "force_ask",
            "reason": f"Code freeze active: '{rel}' is outside allowed_prefixes ({', '.join(allowed_prefixes)}). Confirm edit explicitly.",
        }

    return None


def _collapse_path_token(tok: str) -> str:
    if "://" in tok or "/" not in tok or tok.startswith("//"):
        return tok
    had_trailing = tok.endswith("/")
    lead_redirect = ""
    rest = tok
    m_red = re.match(r"^(>*)(.*)$", tok)
    if m_red and m_red.group(1):
        lead_redirect, rest = m_red.group(1), m_red.group(2)
        if "/" not in rest:
            return tok
    normed = posixpath.normpath(rest)
    if had_trailing and normed not in {"/", ".", ".."} and not normed.endswith("/"):
        normed += "/"
    return f"{lead_redirect}{normed}"


def _normalize_cmd_paths(cmd_norm: str) -> str:
    return re.sub(r"[^\s;|&\"'`<>(),=]+", lambda m: _collapse_path_token(m.group(0)), cmd_norm)


def _has_shell_write_intent(cmd: str) -> bool:
    if SHELL_WRITE_VERBS.search(cmd):
        return True
    return any(p.search(cmd) for p in INLINE_WRITER_PATTERNS)


def _match_prefix_in_segment(seg_cmp: str, prefix: str, root_norm_cmp: str) -> bool:
    p_name = _norm_case(prefix.rstrip("/"))
    root_alt = f"(?:{re.escape(root_norm_cmp)}/)?" if root_norm_cmp else ""
    esc = re.escape(p_name)
    # 1) Explicit slash-bounded path reference (`backend/app`, `tests/foo.py`, `./tests/`, `<ROOT>/tests/`)
    slash_re = re.compile(rf"(?:^|[\s;|&=(,:>+])(?:\./)?{root_alt}{esc}(?:/|(?=$|[\s;|&),]))")
    if "/" in p_name:
        return bool(slash_re.search(seg_cmp))

    # For top-level dirs (`tests/`, `migrations/`), match only `dir/...` or redirect/fs-mutator targets (avoids `.qc-tmp/tests.log` FP)
    dir_path_re = re.compile(rf"(?:^|[\s;|&=(,:>+])(?:\./)?{root_alt}{esc}/")
    if dir_path_re.search(seg_cmp):
        return True
    redirect_dir_re = re.compile(rf">+\s*(?:\./)?{root_alt}{esc}(?=$|[\s;|&])")
    if redirect_dir_re.search(seg_cmp):
        return True
    if (
        FS_MUTATOR_SEGMENT_RE.search(seg_cmp)
        or INLINE_MUTATOR_EXPR_RE.search(seg_cmp)
        or any(p.search(seg_cmp) for p in INLINE_WRITER_PATTERNS)
    ):
        bare_dir_re = re.compile(rf"(?:^|[\s=:,(])(?:\./)?{root_alt}{esc}(?=$|[\s;|&),])")
        if bare_dir_re.search(seg_cmp):
            return True
    return False


VAR_ASSIGN_RE = re.compile(
    r"^\s*(?:\$(?!env[:.])|set\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*([^\s;|&]+)\s*$",
    re.IGNORECASE,
)


_PY_CODE_FLAG_AT_RE = re.compile(
    r"-(?!-)[BEIOqsSuvP]*c(?=$|\s|\$'|\\?['\"]|[rfubRFUB]{1,2}\\?['\"])",
)
_JS_CODE_FLAG_AT_RE = re.compile(
    r"(?:--eval=?|--print=?|-[ep])(?=$|\s|\$'|\\?['\"])",
    re.IGNORECASE,
)
_DENO_EVAL_AT_RE = re.compile(
    r"eval(?=$|\s|\$'|\\?['\"])",
    re.IGNORECASE,
)


def _find_inline_script_quote(cmd_urls: str, bin_end: int, bin_name: str) -> tuple[int, int, str] | None:
    """Advance from interpreter binary end to its inline script opening delimiter."""
    n = len(cmd_urls)
    p = bin_end
    tokens_seen = 0
    bin_low = bin_name.lower()
    is_python = bin_low.startswith("py")
    is_deno = bin_low.startswith("deno")
    while p < n and tokens_seen < 16:
        while p < n and cmd_urls[p] in " \t":
            p += 1
        if p >= n or cmd_urls[p] in ";&|\r\n><":
            return None
        m_flag = (
            _PY_CODE_FLAG_AT_RE.match(cmd_urls, p)
            if is_python
            else (_JS_CODE_FLAG_AT_RE.match(cmd_urls, p) or (_DENO_EVAL_AT_RE.match(cmd_urls, p) if is_deno else None))
        )
        if m_flag:
            qpos = m_flag.end()
            while qpos < n and cmd_urls[qpos] in " \t":
                qpos += 1
            if qpos + 1 < n and cmd_urls[qpos:qpos + 2] == "$'":
                return qpos + 2, 1, "'"
            if is_python:
                m_pref = re.match(r"^[rfub]{1,2}(?=\\?['\"])", cmd_urls[qpos:], re.IGNORECASE)
                if m_pref:
                    qpos += m_pref.end()
            if qpos + 1 < n and cmd_urls[qpos:qpos + 2] in ('\\"', "\\'"):
                return qpos + 2, 2, cmd_urls[qpos:qpos + 2]
            if qpos < n and cmd_urls[qpos] in ("'", '"'):
                return qpos + 1, 1, cmd_urls[qpos]
            return None
        if cmd_urls[p] in ("'", '"'):
            q = cmd_urls[p]
            p += 1
            while p < n:
                if cmd_urls[p] == "\\" and q == '"' and p + 1 < n:
                    p += 2
                    continue
                if cmd_urls[p] == q:
                    p += 1
                    break
                p += 1
        else:
            while p < n and cmd_urls[p] not in " \t;&|\r\n><'\"":
                p += 1
        tokens_seen += 1
    return None


def _sanitize_inline_scripts_and_urls(cmd: str) -> str:
    """Keep multi-statement inline Python/Node scripts and quoted URL query params intact before quote stripping."""
    cmd_urls = QUOTED_URL_RE.sub(lambda m: f"{m.group(1)}{m.group(2).replace('&', '%26')}{m.group(1)}", cmd)

    # Mask `;`, `&`, `|`, and newlines inside quoted args to python/py/node/bun/deno/tsx in linear O(N) time
    pieces: list[str] = []
    cursor = 0
    while cursor < len(cmd_urls):
        m = INLINE_INTERP_BIN_RE.search(cmd_urls, cursor)
        if not m:
            pieces.append(cmd_urls[cursor:])
            break
        found = _find_inline_script_quote(cmd_urls, m.end(), Path(m.group(0)).name)
        if not found:
            pieces.append(cmd_urls[cursor:m.end()])
            cursor = m.end()
            continue

        body_start, delim_len, quote_delim = found
        pieces.append(cmd_urls[cursor:body_start])
        end_pos = body_start
        while end_pos < len(cmd_urls):
            if delim_len == 2 and cmd_urls[end_pos:end_pos + 2] == quote_delim:
                break
            ch = cmd_urls[end_pos]
            if delim_len == 1 and ch == "\\" and quote_delim == '"' and end_pos + 1 < len(cmd_urls):
                end_pos += 2
                continue
            if delim_len == 1 and ch == quote_delim:
                break
            end_pos += 1
        pieces.append(re.sub(r"[;&|\r\n]+", " ", cmd_urls[body_start:end_pos]))
        if end_pos < len(cmd_urls):
            pieces.append(cmd_urls[end_pos:end_pos + delim_len])
            cursor = end_pos + delim_len
        else:
            cursor = len(cmd_urls)
    masked = "".join(pieces)

    # Keep inline heredoc bodies (`python - <<EOF ... EOF`) attached to their launching command
    out: list[str] = []
    hcursor = 0
    for mh in HEREDOC_START_RE.finditer(masked):
        nl = masked.find("\n", mh.end())
        if nl == -1 or nl < hcursor:
            continue
        tag = mh.group(1)
        out.append(masked[hcursor:nl] + " ")
        m_end = re.search(rf"(?m)^[ \t]*{re.escape(tag)}[ \t]*\r?$", masked[nl + 1:])
        body_end = (nl + 1 + m_end.start()) if m_end else len(masked)
        out.append(re.sub(r"[;&|\r\n]+", " ", masked[nl + 1:body_end]))
        hcursor = body_end
    out.append(masked[hcursor:])
    return "".join(out)


def _split_shell_segments(cmd_str: str, *, include_pipe: bool = False) -> list[str]:
    """Split shell chains on `&&`, `||`, `;`, newlines, `&`, and optionally pipes while preserving URL `&` and `2>&1`."""
    cleaned = re.sub(r"(?<![-=<])>\|", ">", cmd_str)
    urls: list[str] = []

    def _stash_url(m: re.Match[str]) -> str:
        idx = len(urls)
        urls.append(m.group(0))
        return f"__RL_URL_{idx}__"

    masked = URL_TOKEN_RE.sub(_stash_url, cleaned)
    delim = r"(?:&&|\|\||\|&|[;\r\n|]|(?<![>&|])&(?![>&]))+" if include_pipe else r"(?:&&|\|\||[;\r\n]|(?<![>&|])&(?![>&]))+"
    out: list[str] = []
    for part in re.split(delim, masked):
        restored = re.sub(r"__RL_URL_(\d+)__", lambda m: urls[int(m.group(1))], part).strip()
        if restored:
            out.append(restored)
    return out


def _expand_shell_vars(seg: str, var_map: dict[str, str]) -> str:
    if not var_map:
        return seg
    expanded = re.sub(
        r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}|\$([A-Za-z_][A-Za-z0-9_]*)|%([A-Za-z_][A-Za-z0-9_]*)%",
        lambda m: var_map.get((m.group(1) or m.group(2) or m.group(3)).lower(), m.group(0)),
        seg,
    )
    return _normalize_cmd_paths(expanded) if expanded != seg else seg


def _resolve_relative_cand(cand: str, base_cwd: list[str]) -> str:
    if not base_cwd or not cand or "://" in cand or re.match(r"^[a-z]:/", cand) or cand.startswith(("/", "~", "%", "$")):
        return cand
    had_trailing = cand.endswith("/")
    normed = posixpath.normpath("/".join([*base_cwd, cand]))
    if had_trailing and normed not in {".", ".."} and not normed.endswith("/"):
        normed += "/"
    return normed


def _resolve_slice_against_cwd(slice_cmp: str, base_cwd: list[str]) -> str:
    def _repl(m: re.Match[str]) -> str:
        tok = m.group(0)
        if "://" in tok or re.match(r"^[a-z]:/", tok) or tok.startswith(("/", "~", "%", "$")):
            return tok
        if tok.startswith("-"):
            m_opt = re.match(r"^(-(?:(?!-)[a-z]*[oO]|(?:path|literalpath|filepath|destination|output):))(.+)$", tok)
            if m_opt and (m_opt.group(1) in {"-o", "-O"} or m_opt.group(1).endswith(":") or "/" in m_opt.group(2)):
                return f"{m_opt.group(1)} {_resolve_relative_cand(m_opt.group(2), base_cwd)}"
            return tok
        stripped = tok.rstrip(")}")
        suffix = tok[len(stripped):]
        return _resolve_relative_cand(stripped, base_cwd) + suffix

    return re.sub(r"[^\s;|&\"'`<>(),=]+", _repl, slice_cmp)


def _segment_write_targets_to_check(seg_cmp: str) -> tuple[list[str], bool]:
    """Return (sub-strings to test against locked prefixes, is_mutator_or_inline).

    Pure redirect/tee segments check only destination tokens against shell CWD so
    read-only args before `>` remain allowed, whereas FS mutators and inline writers
    check the entire segment (and git `-C` targets against git's scoped CWD).
    """
    if (
        FS_MUTATOR_SEGMENT_RE.search(seg_cmp)
        or INLINE_MUTATOR_EXPR_RE.search(seg_cmp)
        or any(p.search(seg_cmp) for p in INLINE_WRITER_PATTERNS)
    ):
        return [seg_cmp], True
    targets: list[str] = REDIR_TARGET_RE.findall(seg_cmp)
    m_tee = TEE_CMD_TAIL_RE.search(seg_cmp)
    if m_tee:
        targets.append(m_tee.group(1).strip())
    return targets, False


def _apply_cwd_step(base_cwd: list[str], raw_dest: str, root_posix: str, root_cmp: str) -> tuple[list[str] | None, bool]:
    dest = raw_dest.strip().rstrip(")}")
    if not dest:
        return base_cwd, False
    dest_cmp = _norm_case(dest)
    if dest_cmp.startswith(root_cmp + "/") or dest_cmp == root_cmp:
        rel = dest[len(root_posix):].lstrip("/")
        normed = posixpath.normpath(rel) if rel else "."
        return ([] if normed == "." else [p for p in normed.split("/") if p]), False
    if re.match(r"^[A-Za-z]:/", dest) or dest.startswith(("/", "~", "%", "$")):
        return None, True
    joined = posixpath.normpath("/".join([*base_cwd, dest])) if base_cwd else posixpath.normpath(dest)
    if joined == ".." or joined.startswith("../"):
        return None, True
    if joined == ".":
        return [], False
    return [p for p in joined.split("/") if p], False


def _matches_locked_dir(rel_parts: list[str], locked_prefixes: list[str]) -> str | None:
    joined_rel = _norm_case("/".join(rel_parts) + "/") if rel_parts else ""
    for prefix in locked_prefixes:
        p_cmp = _norm_case(prefix)
        if joined_rel == p_cmp or joined_rel.startswith(p_cmp):
            return prefix
    return None


def _inspect_shell_segments(
    cmd_norm: str,
    locked_prefixes: list[str],
    root_norm_cmp: str,
    *,
    check_writes: bool,
) -> tuple[str | None, str | None, bool]:
    """Return (cd_locked_prefix, write_locked_prefix, escaped_repo_via_dotdot)."""
    root_posix = ROOT.resolve().as_posix().rstrip("/")
    root_cmp = _norm_case(root_posix)
    cwd_stack: list[list[str]] = [[]]
    var_map: dict[str, str] = {}
    cd_locked_hit: str | None = None
    write_locked_hit: str | None = None
    escaped_repo = False

    for seg in _split_shell_segments(cmd_norm, include_pipe=False):
        seg_expanded = _expand_shell_vars(seg, var_map)
        seg_clean = CD_WRAPPER_PREFIX_RE.sub("", seg_expanded).strip()
        if POPD_SEGMENT_RE.match(seg_clean):
            if len(cwd_stack) > 1:
                cwd_stack.pop()
            continue

        cur_cwd = cwd_stack[-1]
        m_var = VAR_ASSIGN_RE.match(seg_clean)
        if m_var and not seg_clean.startswith("-"):
            val = m_var.group(2)
            if len(var_map) < 32 and val:
                var_map[m_var.group(1).lower()] = val
            continue

        m_cd = CD_SEGMENT_RE.match(seg_clean)
        if m_cd:
            new_cwd, esc = _apply_cwd_step(cur_cwd, m_cd.group(1), root_posix, root_cmp)
            if esc:
                escaped_repo = True
            if new_cwd is not None:
                if "push" in seg_clean.lower().split()[0]:
                    cwd_stack.append(new_cwd)
                else:
                    cwd_stack[-1] = new_cwd
                cd_locked_hit = _matches_locked_dir(new_cwd, locked_prefixes) or cd_locked_hit
            continue

        # Check non-cd write/reference tokens with `..` against current repo depth
        for raw_tok in re.findall(r"[^\s;|&\"'`<>(),=]+", seg_clean):
            tok = raw_tok.rstrip(")}")
            if "://" in tok or not tok:
                continue
            if tok == ".." or "/../" in tok or tok.startswith("../") or tok.endswith("/.."):
                joined = posixpath.normpath("/".join([*cur_cwd, tok])) if cur_cwd else posixpath.normpath(tok)
                if joined == ".." or joined.startswith("../"):
                    escaped_repo = True
                    break

        for part in _split_shell_segments(seg_clean, include_pipe=True):
            part_cmp = _norm_case(part)
            scoped_cwd: list[str] | None = None
            m_git = re.search(r"\bgit(?:\.exe)?\b([\s\S]*)$", part)
            if m_git:
                cur_scoped = list(cur_cwd)
                has_c = False
                for m_c in re.finditer(r"(?:^|\s)-C\s*([^\s;|&>]+)", m_git.group(1)):
                    has_c = True
                    nxt_cwd, esc = _apply_cwd_step(cur_scoped, m_c.group(1), root_posix, root_cmp)
                    if esc:
                        escaped_repo = True
                        break
                    if nxt_cwd is not None:
                        cur_scoped = nxt_cwd
                        cd_locked_hit = _matches_locked_dir(cur_scoped, locked_prefixes) or cd_locked_hit
                if has_c:
                    scoped_cwd = cur_scoped

            if not check_writes or write_locked_hit:
                continue
            targets, is_mutator = _segment_write_targets_to_check(part_cmp)
            eff_cwd = scoped_cwd if (is_mutator and scoped_cwd is not None) else cur_cwd
            for target_slice in targets:
                resolved_slice = _resolve_slice_against_cwd(target_slice, eff_cwd)
                for prefix in locked_prefixes:
                    if _match_prefix_in_segment(resolved_slice, prefix, root_norm_cmp):
                        write_locked_hit = prefix
                        break
                if write_locked_hit:
                    break
            if is_mutator and scoped_cwd is not None and not write_locked_hit:
                for redir_target in REDIR_TARGET_RE.findall(part_cmp):
                    resolved_redir = _resolve_slice_against_cwd(redir_target, cur_cwd)
                    for prefix in locked_prefixes:
                        if _match_prefix_in_segment(resolved_redir, prefix, root_norm_cmp):
                            write_locked_hit = prefix
                            break
                    if write_locked_hit:
                        break

    return cd_locked_hit, write_locked_hit, escaped_repo


def _track_cwd_states_and_traversal(cmd_norm: str, locked_prefixes: list[str]) -> tuple[str | None, bool]:
    """Return (locked_prefix_reached_via_cd, escaped_repo_via_dotdot)."""
    root_norm_cmp = _norm_case(ROOT.resolve().as_posix().rstrip("/"))
    cd_locked_hit, _write_hit, escaped_repo = _inspect_shell_segments(
        cmd_norm, locked_prefixes, root_norm_cmp, check_writes=False
    )
    return cd_locked_hit, escaped_repo


def evaluate_payload(payload: dict) -> dict:
    if not isinstance(payload, dict):
        return {"decision": "deny", "reason": "Malformed hook payload structure rejected (fail-closed)."}

    tool_call = payload.get("toolCall") or {}
    if not isinstance(tool_call, dict):
        return {"decision": "deny", "reason": "Malformed toolCall payload rejected (fail-closed)."}

    tool_name = str(tool_call.get("name", "")).lower()
    args = tool_call.get("args") or {}
    if not isinstance(args, dict):
        args = {}

    if tool_name in WRITE_TOOLS:
        paths = _extract_all_paths(args)
        if not paths:
            return {"decision": "deny", "reason": f"Missing file path argument for write tool '{tool_name}'."}
        deferred_ask: dict | None = None
        for raw_path in paths:
            verdict = _evaluate_write_path(raw_path, payload.get("artifactDirectoryPath"))
            if verdict:
                if verdict["decision"] == "deny":
                    return verdict
                deferred_ask = deferred_ask or verdict
        if deferred_ask:
            return deferred_ask

    if tool_name == "run_command":
        cmd = str(args.get("CommandLine") or args.get("command") or "")
        for pattern in GLOBAL_INSTALL_PATTERNS:
            if pattern.search(cmd):
                return {
                    "decision": "force_ask",
                    "reason": (
                        "Repo-Local Agent Skills Policy (Rule 04): refusing direct/global skill install command. "
                        "Use `commands/skills-manager.py install <source> [--from-npx] [--cold]` instead so skills stay inside `.agents/` without creating root lockfiles or global writes."
                    ),
                }

        cmd_sanitized = _sanitize_inline_scripts_and_urls(cmd)
        cmd_unprefixed = re.sub(r"(?<![A-Za-z0-9_])[rfub]{1,2}(?=['\"])", " ", cmd_sanitized, flags=re.IGNORECASE)
        cmd_norm = _normalize_cmd_paths(re.sub(r"[\"'`]", "", cmd_unprefixed).replace("\\", "/"))
        root_norm_cmp = _norm_case(ROOT.resolve().as_posix().rstrip("/"))
        freeze_enabled, locked_prefixes, _allowed = load_freeze_config()
        has_write = _has_shell_write_intent(cmd_norm) or _has_shell_write_intent(cmd)
        cd_locked_prefix, write_locked_prefix, escaped_repo = _inspect_shell_segments(
            cmd_norm, locked_prefixes, root_norm_cmp, check_writes=freeze_enabled and has_write
        )

        if freeze_enabled and ENCODED_PWSH_RE.search(cmd):
            return {
                "decision": "force_ask",
                "reason": "Obfuscated PowerShell -EncodedCommand blocked during active freeze without human confirmation.",
            }

        if freeze_enabled and has_write:
            if cd_locked_prefix:
                return {
                    "decision": "deny",
                    "reason": f"Code freeze active (.agents/.freeze.lock locks '{cd_locked_prefix}'): shell cd + write into locked directory blocked.",
                }
            if write_locked_prefix:
                return {
                    "decision": "deny",
                    "reason": f"Code freeze active (.agents/.freeze.lock locks '{write_locked_prefix}'): shell write referencing locked subtree blocked.",
                }
            if OPAQUE_PATCH_GIT_RE.search(cmd_norm):
                return {
                    "decision": "force_ask",
                    "reason": "Code freeze active: git patch/apply command can mutate locked files implicitly; confirm before proceeding.",
                }

        if has_write:
            brain_root = (Path.home() / ".gemini" / "antigravity" / "brain").resolve()
            root_resolved = ROOT.resolve()
            for match in ABS_DRIVE_PATH_RE.findall(cmd_norm):
                try:
                    p = Path(match).resolve()
                except Exception:
                    continue
                if not p.is_relative_to(root_resolved) and not p.is_relative_to(brain_root):
                    return {
                        "decision": "force_ask",
                        "reason": f"AGENTS.md §4 containment warning: shell write targets external path '{match}'. Confirm before writing outside repo.",
                    }
            m_env = EXT_ENV_OR_HOME_WRITE_RE.search(cmd_norm)
            if m_env:
                raw_ext = m_env.group(0).strip()
                allow_brain = False
                if raw_ext.startswith("/"):
                    try:
                        allow_brain = Path(raw_ext).resolve().is_relative_to(brain_root)
                    except Exception:
                        allow_brain = False
                if not allow_brain:
                    return {
                        "decision": "force_ask",
                        "reason": f"AGENTS.md §4 containment warning: shell write targets env/home/system path '{raw_ext}'. Confirm before writing outside repo.",
                    }
            if escaped_repo:
                return {
                    "decision": "force_ask",
                    "reason": "AGENTS.md §4 containment warning: relative parent traversal (`../`) escapes repository root.",
                }

        for pattern in DESTRUCTIVE_CMD_PATTERNS:
            if pattern.search(cmd):
                return {
                    "decision": "force_ask",
                    "reason": f"Destructive shell/SQL command matched '{pattern.pattern}'. Explicit human confirmation required.",
                }

    return {"decision": "allow"}


def main() -> int:
    try:
        raw = sys.stdin.read().strip()
        payload = json.loads(raw) if raw else {}
    except Exception as exc:
        result = {"decision": "deny", "reason": f"Malformed PreToolUse stdin JSON rejected (fail-closed): {exc}"}
        sys.stdout.write(json.dumps(result) + "\n")
        return 0

    result = evaluate_payload(payload)
    sys.stdout.write(json.dumps(result) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
