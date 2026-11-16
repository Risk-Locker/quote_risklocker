# Phase 5: AI Pipeline Hardening, Model Lockdown & 10/10 Verification Gauntlet

> **Document:** `docs/plans/2026-11-15-phase-5-ai-pipeline-hardening-and-verification.md`  
> **Status:** Verified & Completed (All 5 Tasks Passed)  
> **Prerequisites:** Phase 1, Phase 2, Phase 3 & Phase 4 100% Verified  
> **Owners:** 08-ai-extraction-lead & 09-qa-and-janitor-gate  

---

## 1. Executive Summary & Forensic Context

In Phases 1–4, we successfully:
- Patched P0 security exploits, AST math evaluator, Supabase storage persistence, and RBAC (`Phase 1`).
- Established the double-entry financial ledger and PostgreSQL schema triggers (`migrations/077+`) (`Phase 2`).
- Enforced single source of truth in backend `Decimal` engines, indexed SQL queries, and leap-safe calendar date arithmetic (`Phase 3`).
- Cleansed 100% of hardcoded PII/bank literals, eliminated raster screenshot PDFs in favor of native Playwright vector export, modernized browser dialogs, and decomposed frontend monoliths (`Phase 4`).

**Phase 5** completes the 5-phase master remediation roadmap by hardening the AI extraction pipeline, locking down Gemini models, eliminating copy-pasted router boilerplate, and executing the full 10/10 deployment verification gate:

1. **Gemini Model Lockdown & Deprecation Remediation (`F-14`):**  
   Google AI Studio retired legacy preview endpoints (`gemini-3.1-flash-lite-preview` shut down; `gemini-3.5-flash` deprecated; `gemini-3.8-flash` dangerous with 20 RPD cap). We strictly lock down the model pool to verified active Google AI Studio production tiers:
   - Default primary: `gemini-3.1-flash-lite`
   - Secondary parallel tier: `gemini-3.5-flash-lite`
   - Safe ceilings: 13 RPM, 480 RPD, 200k TPM per slot.
   - Centralize model resolution via `resolve_active_gemini_model()` in `backend/app/core/config.py`.
   - Purge deprecated strings across all 13 locations in `backend/app/` (`copilot.py`, `sessions.py`, `system.py`, `gemini_account_service.py`, `catalog_operations_service.py`, `grounding_assistant.py`, `system_checks.py`, `vehicle_simplifier_service.py`).

2. **AI Extraction Prompt Sandboxing & Confidence Calibration (`AI-01`, `AI-02`, `AI-03`):**  
   - Untrusted PDF document text inside prompts is sandboxed within `<untrusted_document_content>` tags to prevent prompt injection.
   - Stop blindly injecting `score=0.99` in `orchestrator.py:97`. Replace with calibrated confidence scoring based on extracted field validity and agreement with native PDF text.
   - Enforce pre-flight token weighing (`token_preflight_service.py`) and adaptive request pacing (`pacer_sentinel.py`) to prevent account bans.

3. **Router Import Header De-Slop:**  
   Strip copy-pasted 140-line unused import headers from `copilot.py` and `insights.py`, keeping only the imports actually used.

4. **Template Standardization Completion (Design 1 & Design 2):**  
   Standardize Design 1 and Design 2 names and dynamic towing upgrade / betterment age calculations in template configuration.

5. **Exhaustive 10/10 Verification Gauntlet (`commands/verify-deploy-gate.ps1`):**  
   Run the complete 10-step enterprise gate: hermetic pytest suite, TypeScript check, Next.js build, migration ledger, codebase map freshness, Knowledge Base integrity (`verify-brain.py`), agent bridges sync, skills manager check, strict security audit (`security-audit.py --strict`), and daily radar.

---

## 2. 10-Point Edge-Case & Failure-Mode Matrix

| ID | Dimension | Specific Failure Mode Prevented in Phase 5 |
| :--- | :--- | :--- |
| **E-01** | Missing / Empty Gemini Key | System gracefully falls back to deterministic PyMuPDF regex extraction without crashing or 500. |
| **E-02** | Retired Model Invocation | Calling Gemini never hits 404/410 retired endpoints (`gemini-3.1-flash-lite-preview`); all routes route to active verified models. |
| **E-03** | 20 RPD Cap Trap | High-risk `gemini-3.8-flash` is strictly banned; requests route only through `gemini-3.1-flash-lite` / `gemini-3.5-flash-lite` (480 RPD). |
| **E-04** | Over-Capacity PDF Upload | Multi-page PDS / manual (>200,000 tokens) is flagged in preflight and disqualified before hitting Google API. |
| **E-05** | Prompt Injection via PDF | Malicious text in uploaded PDF attempting to alter JSON schema or leak prompt is contained in `<untrusted_document_content>`. |
| **E-06** | Blind 0.99 Confidence Hallucination | Extracted candidates from Gemini are calibrated against native regex; discrepancies trigger `check_needed` status. |
| **E-07** | Rate Limit Burst Pacing | Rapid upload of staged PDFs is paced via `PacerSentinel` to stay strictly $\le 13$ RPM per slot, avoiding 429 errors. |
| **E-08** | Unused Import Bloat | Router files compile with clean, minimal imports without circular dependency risks or linter warnings. |
| **E-09** | Betterment Exact Date Math | Vehicle age calculation uses calendar `relativedelta.years` so 9y 11m 29d resolves to 9 completed years (35% scale), not 10. |
| **E-10** | Towing Dynamic Upgrade Parity | Activating rider PA (Plan 4 / OTO 360) upgrades the top perk to "UNLIMITED TOWING" in-place without duplicate cards. |

---

## 3. Serialized Implementation Tasks

### Task 1: Gemini Model Lockdown & Deprecation Remediation (F-14)
- Add helper `resolve_active_gemini_model()` in `backend/app/core/config.py`.
- Purge deprecated model strings across `backend/app/`:
  - `backend/app/api/routers/copilot.py`
  - `backend/app/api/routers/sessions.py`
  - `backend/app/api/routers/system.py`
  - `backend/app/services/gemini_account_service.py`
  - `backend/app/services/catalog_operations_service.py`
  - `backend/app/services/grounding_assistant.py`
  - `backend/app/services/system_checks.py`
  - `backend/app/services/vehicle_simplifier_service.py`
- Verify with `tests/unit/test_gemini_model_lockdown.py`.

### Task 2: AI Extraction Prompt Sandboxing & Confidence Calibration (AI-01, AI-02, AI-03)
- Sandbox untrusted PDF text with `<untrusted_document_content>` tags in `backend/app/extraction/gemini_extractor.py` and `copilot_chat_service.py`.
- Update `orchestrator.py` candidate scoring: replace unconditional `score=0.99` with calibrated confidence based on field extraction validity and regex agreement.
- Verify preflight token and pacer sentinel tests: `test_token_preflight.py`, `test_pacer_sentinel.py`.

### Task 3: Router Import Header De-Slop (Kill Copy-Pasted 140-Line Import Blocks)
- Clean up unused import headers in:
  - `backend/app/api/routers/copilot.py`
  - `backend/app/api/routers/insights.py`

### Task 4: Template Standardization Completion (Design 1 & Design 2)
- Standardize template naming in `backend/app/services/template_config.py` and `backend/app/rendering/template_renderer_design2.py`.
- Verify passing tests for `tests/unit/test_towing_dynamic_upgrade.py` and `tests/unit/test_betterment_exact_age.py`.

### Task 5: Full 10/10 Enterprise Pre-Deployment Gate
- Run all 10 checks in `commands/verify-deploy-gate.ps1`.
- Update `docs/core/STATE.md` with the Phase 5 completion record.
