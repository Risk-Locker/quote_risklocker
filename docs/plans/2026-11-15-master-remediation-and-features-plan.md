# Master Remediation & Strategic Feature Implementation Plan

> **Document:** `docs/plans/2026-11-15-master-remediation-and-features-plan.md`  
> **Date:** 2026-11-15  
> **Status:** Draft / Awaiting User Approval  
> **Standards:** `/writing-plans`, `/subagent-driven-development`, `/verification-before-completion`, `Rule 06`  
> **Goal:** Execute authentic end-to-end remediation of the 7 core architectural domains, fix all 8 User Chronicle steps, implement dynamic Gemini model discovery, build the Conversational Catalog Studio Assistant, and establish response footer token telemetry.

---

## 1. Executive Summary & Grounding

This plan addresses the foundational defects and user requirements identified across the codebase and the user's serial chronicle ([`docs/history/USER-CHRONICLE-IDEA-SPEC.md`](file:///c:/Users/mahmud/Desktop/Code/risklocker/quote_risklocker/docs/history/USER-CHRONICLE-IDEA-SPEC.md)):

1. **The Phantom Pacer & Token Weighing Trap**:
   - `PacerSentinel` is currently never imported or invoked in `extraction_worker.py`.
   - `upload-workspace.tsx:95` still estimates pages as `file.size / 65,000`, causing 4–6 MB scanned 2-page PDFs to be falsely disqualified as 77 pages / 680k tokens.
2. **Actuarial Math & Towing Disconnects**:
   - `ncd_evaluator.py:156` still uses simple year math `(veh_yom + 9) > quote_y` instead of exact calendar `relativedelta.years`.
   - `unified-addon-engine.ts` in the frontend lacks duplicate towing card suppression, causing the live canvas to render conflicting towing cards.
   - `towing_evaluator.py:231` matches digit 4 anywhere in text, falsely promoting cheap Plan 1 policies to "Unlimited".
   - `road_tax_engine.py:41` drops road tax by RM 37.50 at 2501cc compared to 2500cc.
3. **Dynamic Gemini Model Discovery**:
   - Rather than hardcoding static strings, the system will dynamically discover text models meeting the free-tier stability criteria ($\ge 15\text{ RPM}$, $\ge 250\text{k TPM}$, $\ge 500\text{ RPD}$, or highest quota tiers) via Google API discovery and live limits metadata.
4. **Conversational Insurance Catalog Studio Assistant**:
   - Enable staff to use plain English in `/builder/benefits` and the copilot drawer (e.g. "Clone QBE to new insurer XYZ, update logos, map benefits") to generate an interactive visual `CatalogDiffPlan`, review side-by-side differences, and commit safely to database tables through `PacerSentinel` quota protection.
5. **Template as Builder (Bilingual Agency 1-Template Toggle)**:
   - Consolidate the 3 separate database rows in `master_template_service.py` into ONE canonical template with an interactive `[ Itemized | Lump Sum | None ]` toggle on the quotation page.
6. **Token Budget & Response Telemetry ("Caveman Stats")**:
   - Mandate that all agent responses include a concise footer showing tokens consumed, remaining context window headroom, and chat health, with structured handover triggers before context degrades.

---

## 2. 10-Point Edge-Case & Failure-Mode Matrix

| ID | Dimension | Specific Failure Mode Prevented |
| :--- | :--- | :--- |
| **E-01** | Missing / Dynamic Models | When Google deprecates a model or updates endpoints, dynamic model discovery resolves the next qualified model without code redeployment. |
| **E-02** | Google Quota Shield & Pacing | Bursts of uploads or copilot chat requests are paced by a 60-second sliding window sentinel, staying $\le 13$ RPM and $\le 200\text{k TPM}$ per slot to prevent Google account bans. |
| **E-03** | Scanned PDF Token Discrepancy | High-resolution scanned 2-page PDFs (4–6 MB) are not falsely estimated as 70+ pages by naive byte division; page count is determined accurately. |
| **E-04** | Calendar Leap-Day Betterment | A vehicle registered on `2016-06-15` quoted on `2026-06-14` is 9y 11m 29d old $\rightarrow$ accurately evaluated as 9 completed years (35% tariff scale), not 10 years (40%). |
| **E-05** | Towing Keyword False-Positives | The digit `4` in dates (`2024`), plate numbers, or prices (`RM 400`) no longer triggers false promotion of STMB Plan 1 policies to "Unlimited Towing". |
| **E-06** | Canvas Duplicate Towing | In Design 2 live preview, selecting a paid towing rider (`OTO 360`, `Motor PA Plus Plan 4`) upgrades the top card and suppresses the unselected generic towing card in the bottom 24 matrix. |
| **E-07** | Road Tax Continuity | Road tax for 2501cc is strictly greater than or equal to 2500cc (RM 880.00 base), eliminating the inverted RM 842.50 drop. |
| **E-08** | Catalog Diff AI Sandboxing | AI catalog suggestions must produce an immutable `CatalogDiffPlan` that requires explicit user confirmation before touching PostgreSQL tables. |
| **E-09** | Mutating GET Elimination | Navigating to `/comparison` or refreshing workspace pages triggers zero database `commit()` or `flush()` operations. |
| **E-10** | Context Degradation Handover | When context window approaches high watermarks ($\ge 150\text{k}$ tokens), agent provides an explicit handover summary to preserve speed and precision. |

---

## 3. Serialized Milestones & Bite-Sized Task Breakdown

### Milestone 1: Pacer Sentinel Real Worker Wiring, Upload Token Weighing & Analytics Optimization

- [ ] **Task 1.1: Wire `PacerSentinel` into `extraction_worker.py`**
  - **Files:** `backend/app/workers/extraction_worker.py`, `backend/app/extraction/pacer_sentinel.py`
  - **Action:** Import `PacerSentinel` into `extraction_worker.py`. Call `PacerSentinel.acquire(slot_id, estimated_tokens)` before dispatching LLM calls. Enforce the sliding 60-second window delay and dynamic latency backoff (>4.0s latency adds breathing delay).
  - **Test:** Write integration test in new file `tests/integration/test_worker_pacer_integration.py` (not yet created) asserting that rapid sequential job dispatches trigger real pacing delays without exceeding 13 RPM.

- [ ] **Task 1.2: Fix Frontend Upload Token Weighing in `upload-workspace.tsx`**
  - **Files:** `frontend/src/components/upload/upload-workspace.tsx`
  - **Action:** Remove naive lines 95-96 (`file.size / 65_000` and `file.size * 0.4`). Introduce pre-flight page count estimation via fast binary PDF header traversal or call lightweight backend probe `/api/extraction/preflight-probe` so 4–6 MB scanned 2-page PDFs are accurately identified as 2 pages (~15k tokens).
  - **Test:** Verify in browser with a 5 MB sample PDF that page count shows 2 pages and token warning does NOT trigger.

- [ ] **Task 1.3: Optimize 28-Day Analytics Memory Bomb in `gemini_account_service.py`**
  - **Files:** `backend/app/services/gemini_account_service.py:1077-1150`
  - **Action:** Replace `list(db.scalars(stmt).all())` and the $O(N^2)$ nested loop with SQL aggregate queries using PostgreSQL `date_trunc('minute', created_at)` to calculate peak RPM/TPM directly in the database.
  - **Test:** Pytest unit test asserting `get_historical_analytics` returns correct metrics without loading full table rows into RAM.

---

### Milestone 2: Actuarial Math Invariants, Towing Parity & Road Tax

- [x] **Task 2.1: Wire Exact Calendar Betterment Age into `ncd_evaluator.py`**
  - **Files:** `backend/app/services/marketing_comparison/ncd_evaluator.py:154-186`
  - **Action:** Replace year addition `(veh_yom + 9) > quote_y` with `calculate_exact_vehicle_age(reg_date, coverage_start_date)` using `dateutil.relativedelta.years`.
  - **Test:** Unit test with registration `2016-06-15` and inception `2026-06-14` verifying it returns 9 completed years (35% scale), NOT 10 years (40%).
  - **Status:** Completed & verified across 3 unit tests and 40 marketing comparison tests.

- [x] **Task 2.2: Fix STMB Towing Substring False-Positive (`"4" in text`)**
  - **Files:** `backend/app/services/marketing_comparison/towing_evaluator.py:222-242`, `ncd_evaluator.py:287`
  - **Action:** Replace `"4"` substring check with regex word boundary `r"\b(?:plan|pelan)\s*(?:4|iv|d)\b"`. Update unknown towing fallback from `"Unlimited"` to `"Unspecified (Check Policy)"`.
  - **Test:** Regression test with document text containing dates `2024`, `RM 400`, plate `WXY 441` asserting towing stays at Plan 1 limit (100 km) and is not promoted to Unlimited.
  - **Status:** Completed & verified with 3/3 passing tests in `tests/unit/test_towing_regex_hardening.py`.

- [x] **Task 2.3: Port Duplicate Towing Suppression to Frontend Live Canvas**
  - **Files:** `frontend/src/lib/unified-addon-engine.ts`, `frontend/src/components/template-canvas/design2-canvas.tsx`
  - **Action:** Port `detect_towing_upgrade` and duplicate suppression logic to `unified-addon-engine.ts` so that when a paid rider is selected, the unselected generic Unlimited Towing card is suppressed from the bottom 24-card matrix in live browser view.
  - **Test:** Playwright browser test verifying Design 2 live canvas renders exactly one towing indicator.
  - **Status:** Completed & verified with 12/12 passing tests in unified addon engine and Design 2 renderer suites.

- [x] **Task 2.4: Fix 2501cc Road Tax Bracket & Remove Client Duplication**
  - **Files:** `backend/app/services/road_tax_engine.py:41-42`, `frontend/src/components/session-workspace/provider.tsx`, `frontend/src/components/session-workspace/review-components/policy-fields-card.tsx`
  - **Action:** Set 2501–3000cc base rate to RM 880.00 (monotonic progression). Remove duplicate client-side road tax calculation formulas in React components and fetch authoritative values from backend.
  - **Test:** Pytest test verifying `calculate_road_tax(2500) == 880.00` and `calculate_road_tax(2501) >= 880.00`.
  - **Status:** Completed & verified with 18/18 road tax tests and 0 TypeScript compilation errors.

---

### Milestone 3: Dynamic Gemini Model Discovery & Quota Protection Engine

- [x] **Task 3.1: Build `model_discovery_service.py`**
  - **Files:** `backend/app/extraction/model_discovery_service.py`, `backend/app/core/config.py`
  - **Action:** Implement dynamic model capability checking against Google AI Studio API `/v1beta/models` or verified online limits registry. Filter for models satisfying:
    - Text generation support (`generateContent`)
    - $\ge 13\text{ RPM}$
    - $\ge 200,000\text{ TPM}$
    - $\ge 480\text{ RPD}$
    - Exclude high-risk/low-cap models (`gemini-3.8-flash` with 20 RPD cap, preview models).
  - **Test:** Unit test asserting discovery correctly identifies `gemini-3.1-flash-lite` and `gemini-3.5-flash-lite` as eligible and rejects low-cap models.
  - **Status:** Completed & verified via 4/4 passing tests in `tests/unit/test_model_discovery_service.py`.

- [x] **Task 3.2: Expose Dynamic Model Endpoints in `/settings/ai-engine`**
  - **Files:** `backend/app/api/routers/system.py`, `frontend/src/app/settings/ai-engine/page.tsx`, `frontend/src/components/gemini-model-switcher.tsx`
  - **Action:** Provide `GET /api/settings/gemini/eligible-models` returning live qualified models and quotas. Update UI to display active model pool dynamically with Set Primary, Toggle Pool, and Banned Model alerts.
  - **Test:** Live API call test verifying endpoint returns valid JSON with model tiers.
  - **Status:** Completed & verified via live authenticated HTTP tests (HTTP 200) and `tests/integration/test_system_eligible_models_api.py`.

- [x] **Task 3.3: Idle-Period Model & Quota Radar Background Sentinel**
  - **Files:** `backend/app/workers/model_radar_sentinel.py`, `backend/app/api/routers/system.py`, `frontend/src/app/settings/ai-engine/page.tsx`
  - **Action:**
    1. Implement background sentinel scheduled to run during quiet periods (e.g. after $\ge 1\text{ hour}$ without active quotation uploads and when AI extraction worker queue is idle).
    2. Executes a lightweight metadata probe (`GET /v1beta/models?key={API_KEY}`) to inspect Google's live model catalog, version tiers, and input/output token ceilings without consuming generation quota.
    3. Compares detected models against stored baseline in `AppSetting("ai_model_baseline")`.
    4. When changes are detected (new high-capacity Flash-Lite tier released, model deprecation announced, or quota shift):
       - Creates a `Notification` in PostgreSQL for Super Admin accounts (`event_type="ai_model_alert"`).
       - Surfaces an actionable notification card in `app-shell.tsx` and `/settings/ai-engine` with options to: **Review & Switch Active Models**, **Put Account to Rest / Pause**, or **Acknowledge & Dismiss**.
    5. Allows the Super Admin to inspect the analysis, test the new model with a live probe, and switch slot assignments cleanly without manual server restarts.
  - **Test:** Pytest test verifying model radar detects simulated model list updates, writes audit event, and creates unread Super Admin `Notification` row.
  - **Status:** Completed & verified via 2/2 passing tests in `tests/unit/test_model_radar_sentinel.py` and live HTTP sentinel trigger.

---

### Milestone 4: Conversational Insurance Catalog Studio Assistant (`/builder/benefits` + `/copilot`)

- [x] **Task 4.1: Build `catalog_diff_service.py`**
  - **Files:** `backend/app/services/catalog_diff_service.py`
  - **Action:** Implemented underwriter catalog comparison and cloning engine:
    - Compare source company (e.g. QBE) vs target company (e.g. XYZ).
    - Map common benefits vs unique underwriter perils.
    - Generate structured `CatalogDiffPlan` with transactional database application (`apply_catalog_diff_plan`).
  - **Status:** Completed & verified via 3/3 passing unit tests in `tests/unit/test_catalog_diff_service.py`.

- [x] **Task 4.2: Connect Copilot Chat with Quota-Paced Tool Execution**
  - **Files:** `backend/app/services/copilot_chat_service.py`, `backend/app/api/routers/copilot.py`
  - **Action:** Equipped Copilot chat with multi-company catalog diff detection (`_find_multiple_companies`), `generate_clone_diff_plan`, and wrapped Gemini calls in `PacerSentinel.acquire/record_call`. Exposed `POST /copilot/catalog/apply-diff-plan`.
  - **Status:** Completed & verified via 2/2 passing tests in `tests/integration/test_copilot_diff_pacer.py`.

- [x] **Task 4.3: Implement Interactive Diff Preview Card in Benefits Studio / Copilot**
  - **Files:** `frontend/src/components/global-ai-copilot.tsx`
  - **Action:** Render side-by-side comparison in Copilot drawer showing proposed changes (common benefits, concepts to add, update plan items) with selection checkboxes, badges, and "Apply to Database" button calling `/copilot/catalog/apply-diff-plan`.
  - **Status:** Completed & verified via clean Next.js 15 TypeScript check (`tsc --noEmit`).

---

### Milestone 5: Template as Builder & Bilingual Agency 1-Template Toggle

- [x] **Task 5.1: Consolidate Master Templates in Database Seeds**
  - **Files:** `backend/app/services/master_template_service.py`, `backend/app/services/template_revision_service.py`, `backend/app/rendering/template_renderer.py`, `backend/app/rendering/benefit_grid_renderer.py`
  - **Action:** Deprecated `Bilingual Agency Motor v4 (No Extras)` and `(Lump Sum Extras)` variant rows. Retained single canonical `Bilingual Agency Motor v4` (with `is_default: True`) and configured `list_published_templates` to exclude deprecated variant rows. Ensured backend renderer reads `extras_mode` from `display_options`.
  - **Status:** Completed & verified via 3/3 passing tests in `tests/unit/test_master_template_consolidation.py` and 36/36 passing tests in full template test suite.

- [x] **Task 5.2: Add Interactive Extras Display Mode Toggle on Quotation Review Page**
  - **Files:** `frontend/src/components/session-workspace/review-components/useReviewWorkspaceState.ts`, `frontend/src/components/session-workspace/review-components/useReviewCatalogAndTemplate.ts`, `frontend/src/components/session-workspace/review-components/TemplateConfigCard.tsx`, `frontend/src/components/session-workspace/review-phase.tsx`, `frontend/src/components/template-canvas/shared.tsx`
  - **Action:** Added segmented toggle `[ Itemized | Lump Sum | Hide Extras ]` directly in `TemplateConfigCard` ("Template as Builder"). Persists selection to `workspace.display_options.extras_mode` via `queueOperation` and dynamically updates the live preview without page reload.
  - **Status:** Completed & verified via clean Next.js 15 TypeScript check (`tsc --noEmit`).

---

### Milestone 6: Governance, Response Footer Telemetry & Context Handover

- [x] **Task 6.1: Add Response Footer Telemetry ("Caveman Stats") to `AGENTS.md`**
  - **Files:** `AGENTS.md`, `.agents/rules/05-live-reality-and-freshness.md`, `.agents/rules/06-serialized-milestones-and-authentic-verification.md`
  - **Action:** Formalized mandatory response footer telemetry table via `commands/chat-token-telemetry.py` reporting active context, headroom, input/cached breakdown, cumulative session activity, and fleet quota telemetry.
  - **Status:** Completed & verified via `commands/chat-token-telemetry.py`.

- [x] **Task 6.2: Add Context Handover Protocol to `AGENTS.md`**
  - **Files:** `AGENTS.md`, `.agents/rules/06-serialized-milestones-and-authentic-verification.md`
  - **Action:** Added seamless fresh-chat handover protocol for high context (>=250k tokens) and completed milestones with verified recaps and fresh chat commands (`Ctrl+L`).
  - **Status:** Completed & verified via `commands/verify-brain.py`.

---

## 4. Execution Strategy via Subagent-Driven Development

Following the `/subagent-driven-development` skill:
- Each task will be executed by an isolated, fresh subagent (`invoke_subagent` using appropriate specialized persona: `06-backend-ledger-lead`, `07-frontend-ux-lead`, `08-ai-extraction-lead`, `09-qa-and-janitor-gate`).
- After each task, a review check will confirm spec compliance and run red-first verification before marking the task complete.
- Authentic live verification (against `:8100` and `:3000`) will be executed at the end of each milestone before asking to proceed.
