# Proposal `F-14`: Remediate Deprecated / Shutdown Gemini Model Strings in `backend/app/`

> **Status:** `FREEZE-DEFERRED` under `.agents/.freeze.lock` (`enabled: true`, `v30.1` baseline `f8c410a`). **Zero frozen backend code was edited.** Apply this diff cleanly as soon as the production code freeze is lifted for Phase 1.

## 1. Live Upstream Evidence Verified (`2026-11-11` via `ai.google.dev` + `search_web`)

| Model String Found in Repo | Live Google Gemini API Status (`2026-11-11`) | Impact if Unpatched |
| :--- | :--- | :--- |
| `gemini-3.1-flash-lite-preview` | **DEPRECATED & SHUT DOWN** (`May 25, 2026`) | Direct calls fail against retired preview endpoint unless overridden by env `GEMINI_MODEL`. |
| `gemini-3.5-flash` | **DEPRECATED** (removed from AI Studio; auto-routes) | Unpredictable auto-routing / latency drift; should migrate to verified active Flash tier. |
| `gemini-3.1-flash-lite` | Earlier Gen-3 Flash-Lite release | Prefer current stable Flash-Lite / Flash generation where supported. |
| **`gemini-3.5-flash-lite`** | **ACTIVE / GA** (released `Jul 21, 2026`; min EOL `>= Jul 21, 2027`) | Recommended low-latency high-volume default replacement. |
| **`gemini-3.8-flash`** | **ACTIVE / GA Frontier Flash** (released `Sep 2026`) | Recommended high-intelligence extraction / complex reasoning escalation model. |

## 2. Exact Frozen Locations Requiring Update (`21` Deprecated/Shutdown Hits Across `10` Files)

1. **`backend/app/core/config.py:65,311`** (`3` hits): default `gemini_model: str = "gemini-3.1-flash-lite-preview"` & `os.getenv` fallback -> switch default to active **`"gemini-3.5-flash-lite"`** (optional `gemini-3.8-flash` env override) and expose one authoritative helper `resolve_active_gemini_model()`.
2. **`backend/app/api/routers/copilot.py:483`** (`2` hits): `"gemini-3.1-flash-lite-preview"` fallback -> delegate to `resolve_active_gemini_model()`.
3. **`backend/app/api/routers/sessions.py:1107`** (`2` hits): `"gemini-3.5-flash"` fallback (`lines 852` is only `"gemini-re-extract-"` prefix) -> delegate to `resolve_active_gemini_model()`.
4. **`backend/app/api/routers/system.py:886,946`** (`2` hits): `"gemini-3.1-flash-lite-preview"` fallbacks -> delegate to `resolve_active_gemini_model()`.
5. **`backend/app/extraction/gemini_extractor.py:420,522-525`** (`2` deprecated hits + `gemini-3.1-flash-lite` / alias): remove `"gemini-3.1-flash-lite-preview"`, prioritize active **`"gemini-3.5-flash-lite"`** -> **`"gemini-3.8-flash"`** cascade cleanly.
6. **`backend/app/services/gemini_account_service.py:126,739,741,742,745,841,953`** (`6` deprecated hits + `PARALLEL_MODELS`): update `PARALLEL_MODELS`, mock/live `probe_single_key` defaults, and `get_quota_stats()` model list to verified active models (`gemini-3.5-flash-lite`, `gemini-3.8-flash`).
7. **`backend/app/services/catalog_operations_service.py:243`** (`1` hit): `"gemini-3.5-flash"` fallback -> call central config helper.
8. **`backend/app/services/grounding_assistant.py:190`** (`1` hit): `"gemini-3.5-flash"` fallback -> call central config helper.
9. **`backend/app/services/system_checks.py:76`** (`1` hit): `"gemini-3.1-flash-lite-preview"` fallback -> call central config helper.
10. **`backend/app/services/vehicle_simplifier_service.py:216`** (`1` hit): `"gemini-3.1-flash-lite-preview"` fallback -> call central config helper.
11. **`backend/app/services/copilot_chat_service.py:1104`** (companion cleanup): unify `"gemini-3.1-flash-lite"` fallback onto central `resolve_active_gemini_model()`.

## 3. Mandatory TDD Execution When Unfrozen (`08-ai-extraction-lead` + `09-qa-and-janitor-gate`)

1. Re-verify live `ai.google.dev/gemini-api/docs/models` & `deprecations` on the unfreeze date (`Rule 05`).
2. Add a hermetic `pytest` test asserting ZERO deprecated/shutdown model strings remain inside `backend/app/core/config.py`, `backend/app/extraction/`, and `backend/app/services/`.
3. Update files, run full hermetic `pytest -q`, and clear `F-14` from `.agents/memory/digest.json`.
