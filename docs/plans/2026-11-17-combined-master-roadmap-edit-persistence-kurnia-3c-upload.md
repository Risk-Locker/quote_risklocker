# Combined Master Roadmap: Edit Persistence, Workspace Save UX, Kurnia, Milestone 3c & Unlimited Upload

> **Status:** Ready to Execute (`v30.4` — Argon `deep` profile enabled).
> **Rules:** `.agents/profiles/deep.md` (Gemini 4 Argon high-capacity execution), `.agents/rules/06-serialized-milestones-and-authentic-verification.md`, `.agents/skills/edge-case-and-scenario-matrix/SKILL.md`.
> **Hard constraint from owner:** Never hand-edit the 50+ affected tenures in the live database. All fixes are deterministic code and idempotent migration fixes that make existing and new rows behave accurately.

## 1. Verified Problem Inventory & Hardened Root Causes (2026-11-17 Audit)

| # | Symptom the owner sees | Verified root cause (with Argon code-audit corrections) | Milestone |
| :-- | :-- | :-- | :-- |
| P1 | Comparison card: cannot change Towing / Special Perils / LLP / anything; edits snap back | Card rows are plain text (`UnderwriterQuoteCard.tsx:428-523`); `UpdateComparisonEntryPatch` (`comparison.py:605`) only accepts `is_hidden`, `manual_rank`, `basic_figure_amount`; and `get_marketing_comparison` overwrites extracted fields (`marketing_comparison_service.py:486-505`, `576-613`) without field-level `manual_overrides` | M4a |
| P2 | Special Perils "Included" when the PDF never mentions it (106 Takaful sessions) | Substring match `"ribut"` hits `"Contribution"` in every Takaful quote (`benefits_extractor.py:389`, `:883`); also duplicated in `backend/app/extraction/benefit_lines.py`. Non-overridden rows must re-evaluate via `resolve_special_perils()` so existing 106 sessions self-heal automatically | M4a |
| P3 | GET of a comparison page returns unsaved cards (`id: null`); editing one creates an orphan row or false 409 | `GET /api/comparison/{id}` runs with `allow_commit=False` (`marketing_comparison_service.py:690`), and line `687` mutates `e.version = max(e.version or 1, company_counts[key])` in-memory without saving, causing version drift | M4a |
| P4 | Towing shows "Emergency towing ... repairer KM"; red/green and `RM 0.2` display errors | `benefits_extractor.py:1046-1049` appends a unit to prose; `UnderwriterQuoteCard.tsx:431` prefers `towing_km` over `towing_limit` and `:512-513` colours any non-empty value green and passes `"RM"` for percentages | M4a |
| P5 | "Save" demanded after every touch; toggling Included twice stays "unsaved" | Dirty = non-empty operation map (`provider.tsx:452-454`), never diffed against the saved value | M4b |
| P6 | Console 422 on `/api/business/dictionaries/learn` | Frontend `LEARNABLE` (`useReviewWorkspaceState.ts:21`) sends plural/unaccepted field names (`car_models`, etc.) while backend accepts only `car_model` / `car_brand` (`admin_service.py:576`) | M4b |
| P7 | Cannot disable/enable Road Tax or Runner Fee reliably | (1) `marketing_comparison_service.py:320-325` and `:2411` forcibly overwrite `tenure.include_road_tax = False` / `include_runner_fee = False` on commercial vehicles even after user edits; (2) `workspace_patch_service.py:1235-1252` reads `fields` before `display_options` | M4b |
| P8 | Kurnia is not a separate company | DB has 7 `InsuranceCompany` rows, no Kurnia. Frontend folds Kurnia into AmAssurance (`company-names.ts:20,68`, `benefit-utils.ts:117`), while backend also references Kurnia in `company_names.py:75`, `candidate_finder.py:952`, `unified_addon_engine.py:914`, `template_renderer_design2.py:190`, `client_dossier_service.py:327`, `generation_service.py:365` | M4c |
| P9 | Box 1 / Design 2 / Comparison towing disagree | Commercial catalog pinning + Box 1 WYSIWYG free coverage + `CompanyBenefitCondition` single source of truth | M3c |
| P10 | Marketing Comparison capped at 30 PDFs | Hardcoded `30` in `upload-workspace.tsx:277`; sequential browser `pollBulkJob` wait loop (`:840`). Batch status route must be registered before `/jobs/{job_id}` (`sessions.py:449`) and query the durable PostgreSQL `Job` table | M4d |

## 2. Execution Order and Model Routing (`deep` Profile on Gemini 4 Argon)

| Order | Milestone | Scope & Argon Execution Mode | Plan file |
| :-- | :-- | :-- | :-- |
| 1 | **M4a** Comparison edit persistence & Special Perils | Pure GET, write-time `materialize`, `078` `manual_overrides` JSONB, extended `PATCH .../entries/{id}`, RBAC on all 5 comparison routes, self-healing `resolve_special_perils()` | `docs/plans/milestone-4a-comparison-edit-persistence-and-special-perils.md` |
| 2 | **M4b** Workspace save semantics, learn 422, fee toggles | Snapshot-diffed `dirtyPaths`, per-edit undo, `car_brand`/`car_model` learn fix, Road Tax & Runner Fee persistence | `docs/plans/milestone-4b-workspace-save-semantics-and-fee-toggles.md` |
| 3 | **M4c** Kurnia as its own company | Migration `079_seed_kurnia_company.sql`, decouple Kurnia from AmAssurance across frontend & backend resolvers | `docs/plans/milestone-4c-kurnia-company.md` |
| 4 | **M3c** Box 1 / Design 2 parity & towing conditions | Commercial catalog pinning, WYSIWYG Box 1 free coverage, DB `CompanyBenefitCondition` evaluation | `docs/plans/milestone-3c-box1-design2-parity-and-towing-conditions.md` |
| 5 | **M4d** Unlimited staged and queued uploads | `comparison_upload_limit` `AppSetting`, `GET /api/jobs/status` (registered before `/jobs/{job_id}`), durable queue polling & upload workspace slicing | `docs/plans/milestone-4d-unlimited-comparison-upload-queue.md` |

> **Argon Execution Note:** Under `.agents/profiles/deep.md`, **M4a + M4b + M4c** can be executed sequentially in a single Argon session (`M4a -> verify -> M4b -> verify -> M4c -> verify`), followed by **M3c** and **M4d**.

## 3. Options Considered (Rule 00)

| Area | Option Chosen | Why |
| :-- | :-- | :-- |
| **Edit persistence (P1–P3)** | Materialize rows at write time + idempotent `POST .../materialize` on load for legacy unlinked sessions; pure read-only `GET`; field-level `manual_overrides` JSONB | Eliminates mutating `GET`, preserves untouched field self-healing on rescan, and never loses human edits |
| **Special Perils (P2)** | Single `resolve_special_perils()` used by comparison, extraction (`benefit_lines.py`), and workspace draft mapper, plus automatic re-evaluation on non-overridden rows | Fixes new uploads AND self-heals the 106 existing Takaful sessions without manual DB edits |
| **Upload queue (P10)** | `comparison_upload_limit` in `AppSetting` (`null` = unlimited), enqueue-all + durable DB `GET /api/jobs/status` batch polling | Zero hardcoded caps; jobs continue server-side even if the browser tab closes or worker restarts |

## 4. Cross-Cutting Contracts

- Zero client-side math or classification truth. React renders what the API returns.
- Monetary columns stay `Numeric(12, 2)`; no new `float`.
- Zero mutating `GET`: M4a cleans both `GET /api/comparison/{tenure_id}` (`comparison.py:169`) and `GET /api/comparison/{tenure_id}/whatsapp-teaser` (`comparison.py:360`).
- All 5 flagged mutating routes in `comparison.py` (`612`, `691`, `743`, `827`, `872`) enforce `require_role(user, Role.SUPER_ADMIN, Role.ADMIN, Role.STAFF, Role.DEV)` and verify `entry.tenure_id == tenure_id`.
- Verification gate per milestone: failing hermetic test first, `pytest`, `npx tsc --noEmit`, `verify-brain.py`, live API/browser verification, and `STATE.md` update.

## 5. 10-Point Edge-Case Matrix

| Dimension | Cases this roadmap covers |
| :-- | :-- |
| Empty / null | Blank special perils, blank towing, entry with `session_id=None`, no sessions at all |
| Decimal bounds | `0.00` excess, `0.20%` rates, negative input rejected, `Numeric(12,2)` round-trip |
| Dates | Feb-29 policy periods unaffected; tenure with superseded sessions only |
| Concurrency | Double-click Save, two tabs editing one entry (true DB `version` without in-memory `GET` drift), upload of 100+ files while editing |
| RBAC / IDOR / CSRF | `require_role` + `entry.tenure_id == tenure_id` across all `comparison.py` write endpoints; CSRF header on all writes |
| Malformed input | Takaful `"Basic Contribution"` vs real `"ribut"`/`"banjir"`, Malay negative terms (`"tidak termasuk"`), `160+` char notes, `String(50)` bounds |
| Timeout / rollback | Materialize and save in one transaction; failed save keeps the unsaved bar and user input intact |
| Zoom / keyboard | Inline card editors reachable by keyboard, `Escape` cancels, `Enter` saves, zero overflow at `1024px` and `80–120%` zoom |
| Legacy rows | 196 unlinked sessions and 5 manual null-session rows materialize cleanly; 106 false-positive Takaful sessions self-heal automatically |
| SQL scale | Comparison load and batch job status (`<= 200` IDs) stay indexed; zero full-table scans |

## 6. Definition of Done for the Whole Roadmap

1. On `JPJ5336` (`19103398-13d0-41e0-8e0e-5c19c9a8ac10`): changing Towing to `Unlimited`, Special Perils to `Not Included`, and LLP survives a reload, a rescan of the other quotes, and a second edit.
2. Any Takaful quote (existing or new) with `"Basic Contribution"` and no actual flood/perils coverage shows `Not Included` in both the quotation workspace and comparison matrix.
3. Clicking `Included` twice in the quotation workspace clears the unsaved indicator (`dirty === false`), and individual edits can be undone from the Unsaved bar.
4. Road Tax and Runner Fee toggles persist across saves, comparison loads, and commercial vehicle rescans, and totals update from backend `Decimal` math.
5. Kurnia appears as its own `InsuranceCompany` in the catalog, `/builder`, and comparison cards, never folded into AmAssurance.
6. Box 1, Design 2 canvas, A4 PDF, and Comparison matrix agree on towing (`Motor PA Plus — Plan 4` in-place upgrade) and Commercial catalog pinning (M3c).
7. 100+ PDFs can be staged and processed on `/upload` in Marketing Comparison without a client-side cap, backed by durable `GET /api/jobs/status` progress polling.
