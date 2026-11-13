---
name: live-reality-and-deprecation-gate
description: Verify active runtime models, SDK/package versions, and live upstream deprecations before writing plans, configs, AI code, or docs, and automatically reconcile stale files so deprecated model IDs or dead guidance never linger.
---

# Live Reality & Deprecation Freshness Gate (`Rule 05`)

Training memory decays quickly — deprecated AI models, removed CLI flags, and changed Next.js/FastAPI/Pydantic APIs cause cascading bugs if left unverified. **Always anchor to live reality first.**

## 1. Mandatory 3-Step Grounding Protocol

Run BEFORE designing plans, editing AI/Gemini pipelines, bumping packages, or citing model/version metadata:

1. **Check Repo Runtime Reality:**
   - Active IDE/Subagent runtime models: call `swarm({action: "models", all: true})` (never invent or echo retired or unverified model labels absent from runtime).
   - Installed backend deps: check `requirements.txt`, `requirements-optional.txt`, & `.venv` (`fastapi`, `pydantic`, `sqlalchemy`, `playwright`, `google-*`).
   - Installed frontend deps: check `frontend/package.json` & `node_modules` (`next`, `react`, `tailwindcss`, `@radix-ui/*`, `playwright`).
   - Hardcoded AI model IDs in repo: grep `gemini-` / `claude-` / `gpt-` across `backend/app/core/config.py`, `backend/app/extraction/`, `backend/app/services/`, `.agents/`, `docs/`.
2. **Verify Live Upstream Status (`Context7 MCP` + `search_web`):**
   - Query version-pinned documentation via **`context7_context7`** (`resolve-library-id` + `query-docs` using the exact Risklocker IDs in `references/verification-checklist.md`, e.g., `/vercel/next.js`, `/pydantic/pydantic`, `/websites/fastapi_tiangolo`).
   - Check official Gemini docs (`ai.google.dev/gemini-api/docs/models` and `ai.google.dev/gemini-api/docs/deprecations`) via `search_web` for the current date (`YYYY-MM-DD`) — **never rely solely on community/DeepWiki examples in Context7 for Gemini model lifecycle status**.
   - Flag ANY model scheduled for shutdown, already retired, or auto-rerouted (e.g., `gemini-3.5-flash` fallback strings still lingering in repo services).
3. **Sync Repo Documentation & Harness Immediately:**
   - **If stale claims exist in `AGENTS.md`, `.agents/`, `commands/`, or `docs/`:** fix them immediately in the current turn so no future agent reads false info.
   - **If stale models/APIs exist inside freeze-locked `backend/app/`, `frontend/src/`, `migrations/`, `tests/`:** respect `.agents/.freeze.lock` and file an actionable remediation entry in `.agents/proposals/YYYY-MM-DD__<topic>.md` + `.agents/memory/digest.json` (and let `.agents/hooks/daily_radar.py` track it!).

## 2. Anti-Staleness Enforcement Table

| Trigger Event | Required Action Before Editing | When Frozen (`.freeze.lock`) |
| :--- | :--- | :--- |
| Selecting agent / worker model | Query live `swarm({action: "models", all: true})` + official docs | Never echo unverified labels inside harness docs |
| Modifying AI extraction / Gemini config | Verify active models on `ai.google.dev` (`deprecations` page) | File freeze-deferred proposal in `.agents/proposals/` + `digest.json` |
| Using Next.js / FastAPI / Pydantic APIs | Verify installed `node_modules` / `.venv` + Context7 / official docs | Sync stale claims inside `docs/` and `.agents/` immediately |
| Daily hygiene sweep | Run `.agents/hooks/daily_radar.py --offline --dry-run` | Verify `harness_signals_count == 0` |

## 3. Concrete Verification Checklist

See `references/verification-checklist.md` for exact PowerShell / Python inspection commands, Gemini live deprecation URLs, and deprecation response patterns.
