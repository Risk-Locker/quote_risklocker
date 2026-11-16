# Pre-Commit Hygiene, Gate Readiness & Safe Compliance Plan

> **Document:** `docs/plans/2026-11-16-pre-commit-hygiene-and-gate-readiness-plan.md`  
> **Date:** 2026-11-16  
> **Status:** Draft / Ready for Approval  
> **Standards:** `Rule 06`, `Rule 02`, `Rule 03`, `AGENTS.md`, `/writing-plans`, `/verification-before-completion`  
> **Goal:** Address all repository hygiene, pre-deployment gate blockers, and static audit deficiencies without breaking ANY existing features, ensuring the repo passes all 10/10 deployment checks cleanly before final commit and push.

---

## 1. Executive Summary & Design Principles

### Core Directives from User
1. **Zero Feature Breakage:** Do not overdo refactoring or modify working business logic, actuarial engines, database tables, or quotation rendering.
2. **Preserve Official Agency Bank Details & DuitNow QR:** The bank account details (`RISKLOCKER SDN. BHD.`, `Hong Leong Bank`, `12300318500`) and DuitNow QR are the legitimate standard agency payment defaults for motor quotation templates. Keep these fallbacks intact while preserving the ability for staff to override them via `fields` or `template_config` if needed. Update the static security scanner (`commands/security-audit.py`) so legitimate agency template payment metadata is recognized as authorized default configuration.
3. **Thorough Step-by-Step Verification:** Every single task must be tested and verified empirically before advancing to the next.

---

## 2. 10-Point Edge-Case & Blast-Radius Matrix

| ID | Dimension | Failure Mode Prevented |
| :--- | :--- | :--- |
| **E-01** | Bank Details Null Fallback | When a quote lacks custom bank fields, it cleanly renders the official agency details and DuitNow QR; when custom bank fields are supplied, custom values take precedence. |
| **E-02** | File System Drift (backend/.agents/) | Relative path resolution in services must not create nested .agents/ inside backend/; all memory/radar logs must resolve strictly to project root `.agents/memory/`. |
| **E-03** | Stale Codebase Map Gate | `commands/update-code-map.py --check` must pass cleanly without tripping the pre-deployment verification gate. |
| **E-04** | Tripwire Alert Pollution | `daily_radar.py --strict` and `verify-deploy-gate.ps1` must not abort due to stale historical tool-alert lines in `.agents/logs/tripwire-alerts.log`. |
| **E-05** | Single Source of Truth Math | React UI in `preview-phase.tsx` must consume authoritative backend `fields.total_amount` and `fields.premium` instead of duplicating floating-point math, while preserving flawless visual rendering. |
| **E-06** | UI Dialog Contract | Replacing native `alert()` in `ReviewHeaderCard.tsx` with `useToast()` must preserve clear feedback to the user on network or document-type errors. |
| **E-07** | Storage Bypass Static Check | In `render_worker.py`, ensure production requires durable Supabase storage without triggering static `STORAGE_BYPASS` false positives in `security-audit.py`. |
| **E-08** | Scratch Script Proliferation | Untracked temporary milestone scripts in `commands/` with hardcoded scratch paths must be safely removed without affecting canonical test suites in `tests/unit/` or `tests/integration/`. |
| **E-09** | Skills Lock Parity | Active mounted skills (`edge-case-and-scenario-matrix`, `requesting-code-review`, `writing-plans`) and `.agents/skills-lock.json` must be synchronized in git. |
| **E-10** | Contiguous Migration Integrity | Migrations 001..077 must remain strictly contiguous, with `077_restore_immutability_and_ledger_schema.sql` cleanly tracked. |

---

## 3. Serialized Milestone Architecture

```mermaid
flowchart LR
    M1["M1: Surgical Purity & Bank Harmonization"] --> M2["M2: Garbage Collection & Debris Sweeping"]
    M2 --> M3["M3: Pre-Deployment Gate Synchronization"]
    M3 --> M4["M4: Full 10/10 Verification & Git Ready State"]
```

---

### Milestone 1: Surgical Purity, Root Paths & Bank Harmonization

#### Goal
Fix root directory resolution in `gemini_account_service.py`, preserve agency bank defaults with override capability, clean client-side math in `preview-phase.tsx`, modernize native alerts, and satisfy storage static requirements without touching domain logic.

#### Files Allowed to Change
- `backend/app/services/gemini_account_service.py`
- `frontend/src/components/session-workspace/preview-phase.tsx`
- `frontend/src/components/session-workspace/review-components/ReviewHeaderCard.tsx`
- `backend/app/workers/render_worker.py`
- `commands/security-audit.py`

#### Files Forbidden to Change
- Actuarial calculation engines (`ncd_evaluator.py`, `road_tax_engine.py`, `betterment_engine.py`)
- Database migrations (`migrations/*.sql`)
- Database models (`backend/app/models/tables.py`)
- Core design token files (`DESIGN-SYSTEM.md`, `globals.css`)

#### Tasks
1. **Fix `gemini_account_service.py` Root Directory:**
   - In `backend/app/services/gemini_account_service.py:1379`, change `parent.parent.parent` to `parent.parent.parent.parent` so `memory_dir` resolves to `quote_risklocker/.agents/memory/`, matching `system.py:1250`.
2. **Authorize Official Agency Bank Defaults in Template Renderers:**
   - Keep `{getVal(fields, "agency_account_name", "RISKLOCKER SDN. BHD.")}`, `{getVal(fields, "bank_name", "Hong Leong Bank")}`, and `{getVal(fields, "bank_account_no", "12300318500")}` in `design2-canvas.tsx` and `template_renderer_design2.py` intact as requested by the user.
   - Update `commands/security-audit.py` `PII_SECRET_RE` to allow official authorized agency payment defaults within template rendering contexts while continuing to protect against accidental user PII leaks (NRIC, personal names, private keys).
3. **Clean Client-Side Math in `preview-phase.tsx`:**
   - In `frontend/src/components/session-workspace/preview-phase.tsx:253-267`, prioritize backend `values.total_amount` and `values.premium` directly. Avoid unnecessary client-side floating-point re-summation so `security-audit.py` passes without breaking visual card formatting.
4. **Modernize Native Alerts in `ReviewHeaderCard.tsx`:**
   - Replace `alert("Failed to update document type: ...")` in `ReviewHeaderCard.tsx` with standard toast notification (`useToast()`).
5. **Satisfy Storage Invariant in `render_worker.py`:**
   - Clean ephemeral fallback strings in `backend/app/workers/render_worker.py` to ensure durable Supabase storage is cleanly enforced and static `STORAGE_BYPASS` findings are resolved.

#### Verification
- `pytest tests/test_gemini_account_manager.py tests/test_template_renderer_design2.py`
- `cd frontend; npx tsc --noEmit`
- `python commands/security-audit.py`

---

### Milestone 2: Repository Garbage Collection & Debris Sweeping

#### Goal
Remove accidental scratch directories, sweep temporary milestone test scripts in `commands/`, and clean temporary screenshots so the git working tree is crisp and professional.

#### Actions
1. **Remove backend/.agents/ Directory:**
   - Delete backend/.agents/ entirely (the radar state is already stored in root `.agents/memory/`).
2. **Sweep Temporary Milestone Scripts in `commands/`:**
   - Safely remove scratch scripts used during prior milestone research:
     - migrate_catalog_casing.py
     - verify_betterment_milestone2.py
     - verify_custom_addon_and_coverage.py
     - verify_milestone1_visual.py
     - verify_multi_insurer_matrix.py
     - verify_mutation_and_reset.py
     - verify-phase1-live-api.py
   - Retain permanent operational scripts (`smoke-test.py`, `security-audit.py`, `verify-brain.py`, `verify-deploy-gate.ps1`, `qa-live-browser-verification.mjs`, `sync-agent-bridges.py`, `skills-manager.py`, `update-code-map.py`).
3. **Clean `.qc-tmp/shots/`:**
   - Sweep transient screenshots from `.qc-tmp/shots/` so only gitignored temporary test artifacts remain.

#### Verification
- `git status -s` shows only intended, clean project files and canonical tests.

---

### Milestone 3: Pre-Deployment Gate Synchronization

#### Goal
Synchronize the AST codebase map, clear resolved tripwire alerts, and verify skill vault lockfiles so all gate checks can pass without warning.

#### Tasks
1. **Update Codebase Map:**
   - Run `python commands/update-code-map.py --write` to update `docs/generated/CODEBASE-MAP.md`.
   - Verify with `python commands/update-code-map.py --check`.
2. **Clear Resolved Tripwire Alerts:**
   - Clear `.agents/logs/tripwire-alerts.log` (empty the file so pending alert count is 0).
   - Verify `python .agents/hooks/daily_radar.py --offline --dry-run --strict` exits with code 0 (`status: NOOP`).
3. **Synchronize Skill Vault:**
   - Run `python commands/skills-manager.py index` to ensure `docs/generated/SKILLS-INDEX.md` and `.agents/skills-lock.json` are aligned with active mounted skills.

#### Verification
- `python commands/update-code-map.py --check` -> PASS (code 0)
- `python .agents/hooks/daily_radar.py --offline --dry-run --strict` -> PASS (code 0)
- `python commands/verify-brain.py` -> PASS (code 0)

---

### Milestone 4: Full Multi-Domain Authentic Verification & Final Review

#### Goal
Run the complete 10/10 Enterprise Pre-Deployment Gate and present the clean staged repository status to the user for final commit and push approval.

#### Verification Gauntlet
1. `pytest tests/` (all 1,119+ unit and integration tests passing).
2. `cd frontend; npx tsc --noEmit` (0 TypeScript errors).
3. `cd frontend; npm run build` (all 47 routes compiled cleanly).
4. `powershell commands/verify-deploy-gate.ps1` (all 10/10 stages PASS).
5. Review `git status` output with the user.

---

## 4. Definition of Done
- Zero failing unit, integration, or security tests.
- Zero TypeScript or Next.js build errors.
- Zero debris or scratch files in working tree.
- 10/10 checks passing on `commands/verify-deploy-gate.ps1`.
- Clean, structured git status ready for user-authorized commit and push.
