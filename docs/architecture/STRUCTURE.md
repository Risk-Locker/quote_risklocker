# Repository Structure

## Top-Level Ownership

| Path | Purpose |
| --- | --- |
| `backend/` | FastAPI application, extraction, services, rendering, and storage adapter |
| `frontend/` | Next.js application, routes, shared UI components, and API client |
| `migrations/` | Ordered Supabase/Postgres schema migrations |
| `tests/` | Backend regression, security, storage, configuration, and extraction coverage |
| `commands/` | Local run, migration, maintenance, smoke-test, and code-map scripts |
| `docs/` | Governed project knowledge base, logbook, and generated code map |
| `.qc-tmp/` | Gitignored in-project scratch space: QA/E2E scripts, logs, screenshots, port file (see OPERATIONS.md) |
| `.github/workflows/` | CI/CD: test + build gate and SSH deploy to the VPS (`deploy.yml`) |
| `deploy/` | Production deployment assets: nginx site config, one-time VPS bootstrap script |
| `ecosystem.config.cjs` | PM2 process definitions (api, worker, frontend) |

The repository root holds only `AGENTS.md`, `README.md`, config files, and the doc system — no stray Markdown files. Any temporary file or folder goes into `/.qc-tmp/` (append its name to `.gitignore` only if a new folder is needed).

## Notable Changes (v6)

- Removed: `frontend/src/app/history/` (folded into Sessions search), `frontend/src/app/sessions/[id]/publish/` (merged into Preview & Edit).
- Added: `migrations/021_template_groups.sql`, `migrations/022_session_layout_override.sql`, `backend/app/services/import_export.py`, `frontend/src/middleware.ts`, `tests/test_v6_features.py`.

## v7 Core Additions

- Plan: `docs/superpowers/plans/2026-08-13-quote-risklocker-v7-core.md`.
- HTTP security: `backend/app/core/http_security.py`, `client_address.py`, `rate_limit.py`.
- Migration safety: `backend/app/db/migrations.py`, `migrations/023_v7_security_foundation.sql`.
- Same-origin frontend proxy: `frontend/src/app/api/[...path]/route.ts`.
- Tests: `test_app_lifecycle.py`, `test_http_security.py`, `test_migration_runner.py`, `test_rate_limits.py`, `test_shared_access.py`.
- v7 catalog/review/template schema: `migrations/024_v7_business_catalog.sql` through `migrations/027_v7_template_publication.sql`.
- Canonical review/template services: `backend/app/services/workspace_service.py`, `workspace_source_service.py`, `template_revision_service.py`, `generation_service.py`.
- Fixed-grid renderer: `backend/app/rendering/grid_layout.py`, `render_context.py`, and dynamic-grid handling in `template_renderer.py`.
- Persistent session workspace: `frontend/src/app/sessions/[id]/layout.tsx`, `frontend/src/components/session-workspace/`.
- Template publication coverage: `tests/test_template_publication.py`, `tests/test_template_revision_validation.py`, `tests/test_dynamic_grid_renderer.py`, `tests/test_frontend_template_publication_contract.py`.
- DB recovery for pre-ledger databases: `commands/backfill-ledger.py` (records already-applied migrations into `schema_migrations`; runner executes SQL via raw DBAPI cursor for psycopg3 `%I`/JSON-literal compatibility).
- Company detection (alias-aware, AMGEN/AmGeneral/auto365 → AmAssurance): `backend/app/extraction/company_resolution.py` (normalize + compact matching + db_companies payload), wired in `candidate_finder.py`, `upload_service.py`, `routes.py`, `extraction_worker.py`; tests in `tests/test_company_resolution.py`.
- Package catalog repair (one-off, idempotent): `commands/repair-amassurance-catalog.py` — publishes the AmAssurance draft revision and aligns `catalog.package_id` to the Lite tier (dry-run by default).
- Package tier edits: `PUT /business/catalogs/{id}/packages/{pid}` rename route; tier-scoped add-on assignment fix in `business_setup_service.py:_validate_assignment_context`; tests in `tests/test_benefit_setup_api.py`, `tests/test_catalog_review_initialization.py`.

## Benefit Packs (v8) Additions

- Migration `migrations/036_package_plans.sql`: `draft_benefit_selections.package_plan_id` + `price` columns (plan tables already exist from 024).
- Migration `migrations/037_draft_package_pin.sql`: `quotation_drafts.package_id` column + index for persisting active comprehensive package tier per draft.
- Plan CRUD: `backend/app/services/benefit_setup_service.py` (`save_plan`, `retire_plan`, `save_plan_items`), routes in `backend/app/api/routes.py`, schemas in `backend/app/api/schemas.py`.
- Workspace ops: `select_package_plan` / `remove_package_plan` / `select_package_tier` in `backend/app/services/workspace_service.py`; multi-package revision tier resolution in `_workspace_package_tiers`; AI auto-apply in `backend/app/services/catalog_review_service.py` (`_apply_detected_packs`).
- Rendering: group borders + corner badge in `backend/app/rendering/template_renderer.py`; new `premium-info-block` element type; extras/adjusted-total helpers in `backend/app/rendering/render_context.py`.
- Frontend: plan manager in `frontend/src/app/builder/benefits/page.tsx` (Bundles tab); pack selector + tier switcher (`pinPackageTier` via `select_package_tier`) + custom-addon price in `frontend/src/components/session-workspace/review-phase.tsx`; group border + premium block in `frontend/src/components/template-canvas/shared.tsx`.
- Data repair command: `commands/repin-amassurance-sessions.py` (idempotent, dry-run default, `--apply`) — re-pins drafts with stale revisions or missing `package_id` to the latest published revision (e.g. rev 3) and re-seeds tier defaults.
- Template update commands: `commands/update-template-header-customer.py` and `commands/update-template-header-quotation-ref.py` (idempotent, dry-run default, `--apply`) — updates existing template revisions with separated header variables and publishes clean revisions.

## Benefit Presets (v10) & Database Persistence (v21) Additions

- Centralized Presets: `frontend/src/lib/benefit-presets.ts` (`SYSTEM_BENEFIT_PRESETS`, `getBenefitPreset`, `applyPresetToCanvasElement`). 7 presets: Masonry Flow, Compact Minimalist, Signature 2-Col, Elevated 3D, Grid Tile, Dark Luxury, Dynamic Masonry.
- Database Persistence: Migration `migrations/048_benefit_card_presets.sql` + model `BenefitCardPreset` (`backend/app/models/tables.py`) with single-default partial unique index `uq_single_default_benefit_card_preset`.
- Backend Service & API: `backend/app/services/benefit_template_preset_service.py` provides CRUD, atomic default selection, and factory resets; REST API at `/business/benefit-card-presets`; tests in `tests/test_benefit_template_presets.py`.
- Template Designer: `frontend/src/app/builder/templates/benefit-templates/page.tsx` loads directly from DB, defaults immediately to Masonry Flow (44px icon, subtle 3D lift, auto uniform height), and writes updates permanently to PostgreSQL.
- Template Builder: Preset selector in `frontend/src/app/builder/templates/[id]/builder/page.tsx` (`Dynamic benefit grid` inspector), Quotation Templates manager at `frontend/src/app/builder/templates/quotation-templates/page.tsx`, and dedicated Benefit Templates designer at `frontend/src/app/builder/templates/benefit-templates/page.tsx` (with automatic sub-tab routing and redirects at `/builder/templates` and `/builder/templates/benefits`).
- Review Workspace: Interactive Benefit Template Switcher in `frontend/src/components/session-workspace/review-phase.tsx` (sidebar + canvas toolbar) with live preview updates.
- Rendering: Double RM fix in `shared.tsx:765`, dynamic row height allocation (~66px standard, 40px minimal) and dynamic footer shifting (`footer_shift`) in `shared.tsx` and `template_renderer.py`. PDF generator applies preset in `generation_service.py:_template_config`.

## System-Generated Quotation Reference (v14) Additions

- Migration `migrations/039_quotation_sequences.sql`: `quotation_sequences` table (`year INT PRIMARY KEY, current_val BIGINT`) and backfill for all existing sessions (`RL260000001`+).
- Migration `migrations/038_quotation_display_and_sequence.sql`: `display_options` JSONB and `display_overrides` columns.
- Service: `backend/app/services/quotation_reference_service.py` provides atomic year-partitioned reference generation (`RL{YY}{SEQ:07d}`) using dynamic real-time `Asia/Kuala_Lumpur` business clock.
- Extraction Shield: Prohibited quotation reference extraction from insurer documents in `gemini_extractor.py`, `candidate_finder.py`, and `draft_mapper.py`; preserved internal sequence in `extraction_worker.py` and `workspace_service.py`.
- Tests: `tests/test_quotation_reference_service.py`.

## EV & Official 2026 JPJ Road Tax Engine (v16) Additions

- Entity & EV Classifier: `backend/app/extraction/entity_classifier.py` canonical model/brand matching (`TESLA`, `BYD`, `ORA GOOD CAT`, `TAYCAN`, etc.), vehicle category assignment (`EVSaloonCar`, `EVNonSaloonCar`, `EVMotorcycle`), and power normalization (kW / Watts).
- Official 2026 JPJ ZEV Rates: `backend/app/services/road_tax_service.py` implements the official power-band rate schedule announced by MOT Malaysia / Anthony Loke (effective Jan 1, 2026). Identical rates for private/company ownership; 50% discount for Sabah/Sarawak and Labuan (> 100 kW).
- Quotation Template Decoupling: Template row 4 label updated to `Engine Capacity/发动机排量 : `, rendering either `cc` for ICE or `kW` for EV (never both) in `backend/app/rendering/template_renderer.py` and `frontend/src/components/template-canvas/shared.tsx`.
- Road Tax Tester & Admin Preview: `frontend/src/app/extraction/road-tax/page.tsx` supports kW testing and displays kW units for EV rules.
- Tests: `backend/tests/test_ev_road_tax.py` covering classification, power normalization, official 2026 power-band calculations, and template renderer string formatting.

## Global Benefit Titles & Correction Memory Decommission (v17) Additions

- Global Benefit Titles Decoupling: In `backend/app/rendering/render_context.py`, extras display titles resolve to canonical Global Benefit Titles (English and Chinese) via standard benefit ID and concept code lookup, providing clean customer-facing quotation presentation without mutating raw policy codes.
- Staff Manual Edits Preservation: Explicit staff overrides during quotation review in `backend/app/services/workspace_service.py` and `backend/app/services/catalog_review_service.py` are prioritized and preserved.
- AI Correction Memory Decommission: Decommissioned noisy machine learning `CorrectionMemory` lookup/persistence from `backend/app/extraction/gemini_extractor.py` and `backend/app/extraction/db_lookups.py` to prevent cascading hallucinated prompts.
- Database Maintenance: `commands/purge-invalid-correction-memory.py` safely purges historical invalid correction memory records from Postgres.
- Tests: `tests/test_template_renderer.py`, `tests/test_extraction_pipeline.py`, and `tests/test_extraction_regression.py` validating canonical benefit title resolution and clean extraction.

## Sessions Dossier, Dual Upload, and Benefit Architecture (v18) Additions

- Sessions Dossier & Multi-Staff Tracking: Migration `migrations/040_user_name_and_session_edit_tracking.sql`, vehicle grouping dossiers, timestamps down to second, duplicate vehicle quote detection, toolbar filtering/sorting, and fast copy actions in `frontend/src/app/sessions/page.tsx` and `backend/app/services/session_service.py`.
- Dual-Mode Intake & Configurable Batch Limits: Single and Bulk upload tabs with live multi-file progress, batch size limits managed via `/builder/uploads` (`frontend/src/app/builder/uploads/page.tsx`), and multi-tab opening.
- Global Benefit Lifecycle & Invariant Cascade: Soft-delete trash/restore pattern replacing retire, active-status filtering cascade across database seeding, runtime queries, and builder canvas in `business_setup_service.py` and `catalog_review_service.py`. Maintenance script in `commands/clean_test_concepts_and_update_descriptions.py`.
- Benefit Template Typography & Description Expansion: Custom font sizes, colors, and weights for benefit templates; full 3-line short descriptions with auto-fitting row heights in `frontend/src/components/template-canvas/shared.tsx` and `backend/app/rendering/template_renderer.py`.
- Extraction Robustness & Vehicle Normalization: Resilient Gemini multi-model fallback rotation, scoped native benefit line extraction in `backend/app/extraction/gemini_extractor.py` and `backend/app/extraction/benefit_lines.py`, and canonical `brand + model` normalization in `backend/app/extraction/draft_mapper.py`.
- Pre-Deployment Gate & CI Parity Script: `commands/verify-deploy-gate.ps1` runs backend pytest under sealed dummy CI environment, frontend tsc, build, schema, and brain verification mirroring `.github/workflows/deploy.yml` 1:1.
- Tests: `tests/test_sessions_upgrade.py`, `tests/test_upload_limits.py`, `tests/test_global_benefit_retirement_cascade.py` (hermetic in-memory SQLite), `tests/test_benefit_line_extraction.py`.

## Benefit Cockpit Tabs, Dynamic Conditions & EV/ICE Engine Type (v20) Additions

- **Catalog Applies Check Fix**: `backend/app/services/business_setup_service.py` ensures assignment targets for product/package scope are cleanly resolved before checking `catalog_offerings_applies_check` constraint.
- **4-Tab Benefits Cockpit**: `frontend/src/app/builder/benefits/page.tsx` splits configuration into 4 tabs:
  1. *Company Benefits*: Master pool selection and insurer baseline short descriptions (`company_benefit_configs`).
  2. *Company Catalogs*: Scenario allocation across Segment, Engine Type (ICE/EV), Vehicle Type, and Coverage.
  3. *Benefit Conditions*: Dynamic conditional upgrade logic rules (`company_benefit_conditions`).
  4. *Overview Matrix*: Underwriting matrix table with Word/Excel export.
- **Dynamic Precedence Hierarchy**: `backend/app/rendering/render_context.py` evaluates 7-tier description precedence: selection override -> dynamic conditional upgrade -> catalog offering override -> company baseline description -> matrix fallback -> concept default -> fallback.
- **Engine Type Architecture**: Decoupled monolithic vehicle type selector into Engine Type toggle (`ICE` | `EV`) + filtered vehicle type dropdown in `frontend/src/components/session-workspace/review-phase.tsx` and scenario bar in `builder/benefits`.
- **Migrations**: `migrations/041_catalog_offering_description_override.sql`, `migrations/042_company_benefit_conditions_and_engine_type.sql`, and `migrations/043_add_tuition_purpose_concept.sql`.
- **Benefit Artworks, Canonical Catalogs & Short Descriptions**: 11 new benefit artworks ingested into Supabase (`assets/benefits/new/` via `commands/ingest-new-benefit-artwork.py`), 63 active canonical benefits calibrated (<80 chars) across 7 insurers seeded into company configs and catalog overrides (`commands/seed-canonical-79-benefits.py`, `commands/seed-company-benefit-descriptions.py`, `docs/benefits/concise/`, `docs/benefits/expanded/`).
- **Template Row Height Calibrations**: `_balance_benefit_grid_elements` calibrated to 74px/84px in `backend/app/rendering/template_renderer.py` and `frontend/src/components/template-canvas/shared.tsx`, eliminating multi-row card overlap and footer clipping.
- **Tests**: `tests/test_catalog_offering_description_override.py`, `tests/test_company_benefit_conditions.py`, and `tests/test_template_renderer.py`.

## Unified Global Benefit Profile Architecture (v21) Additions

- **Unified Global Profile Governance**: Migration `migrations/045_unified_benefit_profiles.sql` replaces legacy per-company profiles with unified global `benefit_profiles` (`id`, `name`, `version_number`, `is_active`, `status`, `notes`) with partial unique index `uq_single_active_benefit_profile` enforcing exactly one active profile platform-wide across all insurance companies simultaneously.
- **Scoped Configs & Conditions**: `company_benefit_configs` and `company_benefit_conditions` re-scoped with `profile_id` foreign keys to `benefit_profiles(id)` with compound unique constraint `uq_company_profile_concept_config` on `(company_id, profile_id, concept_id)`.
- **Service Layer & Immutability**: `backend/app/services/business_setup_service.py` provides global profile CRUD, multi-company deep-clone (`clone_benefit_profile` copies all configs and conditions across all insurers), atomic activation (`activate_benefit_profile`), and strict immutability checks on archived profiles.
- **Global Cascade Exclusions**:
  1. *Review Seeding*: `backend/app/services/catalog_review_service.py:seed_base_benefits` omits disabled concepts for that company under the active global profile.
  2. *Workspace Suggestions*: `backend/app/services/workspace_service.py:suggest_workspace_actions` scopes configs to active global profile.
  3. *Available Cards Suppression*: `backend/app/rendering/render_context.py:resolve_benefit_cards` suppresses disabled concepts from available cards/add-ons while strictly preserving customer-purchased extras (`item_kind == 'extra'`, `state == 'current'`).
  4. *PDF Generation*: `backend/app/services/generation_service.py:generate_quotation_pdf` scopes to active global profile.
- **Frontend Cockpit**: Top Profile Bar in `frontend/src/app/builder/benefits/page.tsx` acts as global version switcher across all 4 cockpit tabs and all insurers, with status badges (`Active Master`, `Draft`, `Archived`), atomic activation button, clone modal dialog, draft deletion, amber `"Excluded"` badge on Tab 2 offerings, and editable `"Default Price / Cost"` column with FOC badges and dynamic formula rate display.
- **Hermetic Test Suite**: `tests/test_company_benefit_profiles.py` covering global profile schemas, auto-provisioning, multi-company deep-clone, lifecycle CRUD, atomic activation, archived immutability, review seeding cascade exclusion, render context suppression, and baseline cost CRUD/sanitization/fallback.

## Global Benefit Visual Profile & Asset Category System (v21) Additions

- **Category-Bound Visual Themes**: Migration `migrations/047_global_benefit_visual_profiles.sql` introduces `global_benefit_profiles` and `global_benefit_profile_assets` tables along with `category` column on `business_assets`.
- **Folder / Category Management**: `frontend/src/app/builder/assets/page.tsx` organizes assets into computer-style folders with direct multi-file batch upload (up to 75 files; no ZIP required) via `POST /business/assets/batch` and folder counts via `GET /business/assets/categories`.
- **Category Exclusivity Invariant**: Each `GlobalBenefitProfile` is strictly bound to one asset folder/category. Both frontend asset selector and backend service (`backend/app/services/global_benefit_profile_service.py:save_global_benefit_profile_assets`) enforce that all mapped icons belong to the assigned category.
- **Missing Asset Health Monitoring**: Non-destructive missing asset detection in `global_benefit_profile_service.py` flags missing/deleted images with `⚠️ Missing Image` warnings without breaking drafts, quotations, or review workflows.
- **Smart Self-Assigning & Review Screen**: Fuzzy name matcher in `global_benefit_profile_service.py:auto_assign_category_assets` matches filenames to the 63 global benefits, presenting the interactive **Assigned Situation Review Screen** modal in `frontend/src/app/builder/global-benefits/page.tsx` for manual fine-tuning and one-click saving.
- **Quotation Render Overlay**: `backend/app/rendering/render_context.py:resolve_benefit_cards` overlays active visual profile assets onto quotation cards and PDF generation.
- **Tests**: `tests/test_global_benefit_profiles.py` covering profile CRUD, deep-cloning, atomic activation, category exclusivity enforcement, missing image health monitoring, and fuzzy auto-matching.

## Benefit Configuration Matrix

- `docs/domain/benefits/BENEFITS-CONFIGURATION.md` — canonical per-insurer benefits/add-on matrix: global benefit library (51 concepts), dimensions, and every company × coverage type × vehicle category row including add-on system (`single` vs `package`), package tiers, and seed status (seeded / draft / pending). Registered in `docs/core/START-HERE.md`.
- `docs/domain/benefits/INSURER-CATALOG-DETAILS.md` — exhaustive per-insurer plan and rider specifications.

## 3-Tier Agent Brain Documentation System

- `docs/core/` — Universal portable agent engine (`START-HERE.md`, `INSTRUCTIONS.md`, `SKILLS.md`, `STATE.md`).
- `docs/architecture/` — System boundaries, API contracts, design tokens, operations, structure, testing.
- `docs/domain/` — Insurance catalogs, benefit matrices, business rules, diagrams.
- `docs/history/` — Monthly cold logbook archives (`MEMORY-YYYY-MM.md`).
- `docs/generated/` — AST symbol, route, and line mapping (`CODEBASE-MAP.md`).
- Verification: `commands/verify-brain.py` ensures 100% link validity and doc registry synchronization.


## Company Seeding (v8)

- `commands/seed-companies.py` (idempotent, dry-run/apply): creates the 3 additional insurers (Lonpac, Berjaya Sompo, Tune Protect) as active with linked company-logo assets and detection aliases. Alias map is loaded from `commands/seed-demo.py` (`COMPANY_ALIASES_MAP`) via importlib because the hyphenated filename cannot be imported by name.
- AI Grounding page moved to `frontend/src/app/ai-context/page.tsx` (own left-sidebar tab, admin/super_admin only).
- Tests: `tests/test_package_plans.py`.

## Builder UX & Onboarding (v8) Additions

- Editable AI system prompt: `GET/PUT /settings/ai-prompt` in `backend/app/api/routes.py`; `prompt_override` support in `backend/app/extraction/gemini_extractor.py`, threaded through `orchestrator.py`, `sandbox.py`, `upload_service.py`, and the re-extract route. Editor tab in `frontend/src/app/ai-context/page.tsx`.
- AI Grounding Chatbot & Assistant: `backend/app/services/grounding_assistant.py` with `POST /settings/ai-grounding-chat` endpoint (targeted low-token DB retrieval for vehicles, insurers, concepts, and system stats) + Chatbot UI tab in `frontend/src/app/ai-context/page.tsx`. Tests in `tests/test_grounding_assistant.py`.
- Collapsible Left Sidebar & Mobile Navigation: `frontend/src/components/app-shell.tsx` with collapsible 64px/220px desktop sidebar, `localStorage` persistence, tooltips on collapsed rail, and full slide-out mobile drawer navigation.
- Sessions package tiers: `package_tiers` in the workspace snapshot (`backend/app/services/workspace_service.py`), `catalog_id` support in `_apply_pin_catalog`, role-based `_catalog_overview`, compact tier chips in `frontend/src/components/session-workspace/review-phase.tsx`.
- Builder preview: real template renderer via `CanvasElementView` in `frontend/src/app/builder/benefits/page.tsx` + inline "Show preview" button.
- Guided tours: reusable `frontend/src/components/guided-tour.tsx` added to builder/benefits, builder/global-benefits, sessions workspace, upload, and AI Grounding.

## Insurer Matrix Visualization & Comprehensive Road Tax (v8)

- Matrix service: `backend/app/services/matrix_service.py` provides company catalog aggregation (`get_company_matrix_data`), landscape `.docx` catalog generation (`generate_company_matrix_docx`), multi-sheet `.xlsx` generation (`generate_company_matrix_xlsx`), and non-destructive delta comparison (`diff_company_matrix`).
- Matrix routes: `GET /business/companies/{id}/matrix`, `GET /business/companies/{id}/export-matrix?format=docx|xlsx`, and `POST /business/companies/{id}/diff-matrix` in `backend/app/api/routes.py`. Tests in `tests/test_matrix_service.py`.
- Road tax schedules & dynamic calculation: `backend/app/services/road_tax_service.py` expanded with 120 official JPJ rules covering West Malaysia, Sabah, Sarawak, Labuan (50% scale), and Commercial Lorries. Automatic calculation fallback in `backend/app/extraction/draft_mapper.py`.
- Road tax endpoints: `POST /admin/road-tax-rules/seed-standard` and `POST /admin/road-tax-rules/calculate` in `backend/app/api/routes.py`. Tests in `tests/test_road_tax_service.py`.
- Frontend Benefits Matrix: `frontend/src/app/builder/benefits/page.tsx` updated with view switcher (`Interactive Builder` vs `Company Overview Matrix`), full tabular policy matrix, Word/Excel downloads, and AI Seed & Sync Spec dialog with non-destructive delta tester.
- Frontend Road Tax Cockpit: `frontend/src/app/extraction/road-tax/page.tsx` updated with jurisdiction tabs, live dynamic road tax tester, progressive calculation formulas, and "Seed Standard JPJ Rules" action.

## Bulk Upload & Rate Limit Management Additions

- Backend Limits: `get_bulk_upload_limit` / `set_bulk_upload_limit` in `backend/app/services/admin_service.py` (persisted in `app_settings`), exposed in `GET /settings/limits`, `GET /admin/settings/upload-limits`, and `POST /admin/settings/upload-limits` in `backend/app/api/routes.py`.
- Upload Page: Dual-mode switcher (`[ Single Upload ]` / `[ Bulk Upload ]`) in `frontend/src/app/upload/page.tsx` preserving 100% of the original single-file workflow while providing multi-file staging, batch progress dashboard, and "Open All in New Tabs".
- Builder Upload Settings: Dedicated configuration page at `frontend/src/app/builder/uploads/page.tsx` linked in `frontend/src/components/builder-nav.tsx` (enforcing minimum 3 PDFs limit).
- Tests: `tests/test_upload_limits.py` and `tests/test_frontend_v7_upload_contract.py`.

## Sessions Upgrade & Global Benefit Invariant Additions

- Migration `migrations/040_user_name_and_session_edit_tracking.sql`: adds `users.full_name`, `sessions.last_edited_at`, and `sessions.last_edited_by` for multi-staff attribution.
- Sessions Dossier & Vehicle Grouping: `frontend/src/app/sessions/page.tsx` updated with vehicle dossiers, real statuses, prominent new-tab actions, and duplicate detection; backend endpoints in `backend/app/api/routes.py` and `backend/app/services/session_service.py`.
- Global Benefit Invariant: cascaded retirement across draft catalog offerings, runtime filtering in `get_catalog_workspace`, strict `BenefitConcept.status == 'active'` check in `seed_base_benefits`, dynamic filtering in `workspace_service.py` & `render_context.py`, and canvas preview filtering in `frontend/src/app/builder/benefits/page.tsx`.
- Tests: `tests/test_sessions_upgrade.py` and `tests/test_global_benefit_retirement_cascade.py`.

## Structured Section & Slot-Based Template Builder (v19) Additions

- Section Compiler Engine: `frontend/src/lib/template-section-compiler.ts` providing bidirectional sync between structured visual sections (`VehicleSpecFieldSlot`, `StructuredSections`, `SectionFooterConfig`) and canonical `canvas.elements` with deterministic geometry compilation.
- Server-Side Compiler Mirror: `backend/app/services/template_section_compiler.py` providing hermetic validation and round-trip consistency checks for template section compilation.
- Structured Section UI: `frontend/src/components/template-builder/section-editor/add-field-dialog.tsx` (extracted variable picker and custom text), `vehicle-fields-manager.tsx` (reorderable slots with arrow controls, visibility toggles, inline labels), `footer-section-manager.tsx` (bank accounts, payment notices, terms).
- Builder Integration: `frontend/src/app/builder/templates/[id]/builder/page.tsx` dual-mode switcher (`[ Sections ] | [ Freeform ]`), 3-tab layout, real-time live canvas compilation, and selection-only lock to prevent accidental canvas element shifting in section mode.
- Tests: `tests/test_template_section_compiler.py`.

## Company-Specific Benefit Short Descriptions & Scenario Hierarchy (v20) Additions

- Migration `migrations/041_catalog_offering_description_override.sql`: adds `description_override TEXT` to `catalog_offerings` for company- and vehicle-specific short benefit wording.
- Model & Schema: `CatalogOffering.description_override` in `backend/app/models/tables.py` and `CatalogOfferingSaveRequest.description_override` in `backend/app/api/schemas.py`.
- Lifecycle & Cloning: `save_catalog_offering`, `remove_catalog_offering`, and `new_catalog_draft` in `backend/app/services/business_setup_service.py`, plus `copy_package_offerings` in `backend/app/services/benefit_setup_service.py` preserve description overrides across revisions and package creation.
- 5-Tier Precedence Engine: `resolve_benefit_cards` in `backend/app/rendering/render_context.py` enforces Draft Selection Custom Description -> Catalog Offering Override -> Insurer Matrix Fallback -> Global Master Concept -> Empty fallback, with `is_custom_description` and `description_override` telemetry.
- Matrix Serialization & Export: `backend/app/services/matrix_service.py` exports `description`, `is_custom_description`, and `description_override` in JSON API, Word documents, and multi-sheet Excel workbooks with `Short Description` and `Description Source` audit columns.
- Seeders: `commands/seed-demo.py` and `commands/seed-company-benefits.py` providing curated descriptions across Car, Motorcycle, Commercial Lorry, and EV scenarios for QBE, Etiqa, and Allianz.
- Benefits Builder UI: `frontend/src/app/builder/benefits/page.tsx` with inline description editors on benefit tiles, `Custom (Company)` vs `Global Default` status badges, reset-to-default buttons, and overview matrix display.
- Tests: `tests/test_catalog_offering_description_override.py`.

## Deployment Additions

- `.github/workflows/deploy.yml` — on push to `main`: backend pytest + frontend `tsc --noEmit` + `next build` on GitHub, then rsync to the VPS, install deps, run migrations, `pm2 startOrReload`.
- `ecosystem.config.cjs` — PM2 apps `rl-quote-api`, `rl-quote-worker`, `rl-quote-frontend`; paths from `RL_DEPLOY_PATH`.
- `deploy/setup-vps.sh` — idempotent one-time VPS bootstrap (system packages, venv, Chromium, build, migrations, nginx, certbot, PM2 startup).

## Benefit Profiles v2 & Dedicated EV Catalogs Additions

- Migration `migrations/046_add_baseline_cost_to_company_benefit_configs.sql`: adds `baseline_cost JSONB` to `company_benefit_configs` for baseline rider pricing.
- Seeding & Maintenance: `commands/seed-company-benefit-costs.py` (baseline pricing), `commands/seed-profile-v2-from-current-benefits.py` (active profile v2 sync), `commands/seed-ev-catalogs-and-dedup-sompo.py` (comprehensive EV coverage for all 7 insurers + Sompo product deduplication), and `commands/repair-ev-and-sompo-sessions.py` (session repair and complimentary benefit cost_status fix).
- EV Review Filtering: `frontend/src/components/session-workspace/review-phase.tsx` dynamically filters EV vs ICE products based on session fuel type, engine capacity (kW), and model, preventing product duplication.

## Session Rescan & In-Place Renewal Architecture

- **Backend Rescan Service**: `backend/app/services/session_rescan_service.py` provides `rescan_session()` supporting two operational modes:
  1. `in_place` (renewal): Cleanses stale/empty draft artifacts (`DraftBenefitSelection`, `DraftSourceLineDecision`, `ExtractionBenefitLine`), re-evaluates source PDF with auto or Gemini fallback, re-extracts vehicle/client fields, pins matching catalog, re-seeds baseline benefits, auto-applies detected benefits, and recalculates road tax while strictly preserving the internal quotation sequence reference (`RL...`).
  2. `new_session`: Clones the original source PDF into an entirely new session with a new unique quotation reference, runs the full extraction pipeline, and opens it directly in a new browser tab.
- **Rescan Route & Schema**: `POST /api/sessions/{session_id}/rescan` with `SessionRescanRequest` (`mode`: `in_place` | `new_session`, `engine`: `auto` | `native` | `ai`) in `backend/app/api/routes.py` and `backend/app/api/schemas.py`.
- **Frontend Sessions Cockpit**: Rescan modal dialog and 1-click rescan buttons in `frontend/src/app/sessions/page.tsx` (`QuotationRow`, `QuotationCard`) with visual mode selection, optional Deep AI reading checkbox, and live status spinners.
- **Hermetic Tests**: `tests/test_session_rescan.py` (hermetic in-memory SQLite coverage for in-place renewal, new-session creation, draft cleansing, and RBAC authorization).

## Conversational AI Copilot, Status Checks & Session Deduplication (v22) Additions

- **Conversational Intelligence Service**: `backend/app/services/copilot_chat_service.py` provides `chat_with_copilot()` with intent-scoped fact gathering (`get_catalog_status_facts`, `get_session_hygiene_facts`), guarded mutation parsing (`parse_catalog_intent`), and conversational synthesis with Gemini 2.5 Flash ($0 cost key pool) and deterministic offline fallbacks.
- **Deduplication Engine**: Evaluates SHA-256 file hashes, registration plates, vehicle models, gross premiums, and road tax amounts; separates exact duplicate uploads from legitimate edited quotes (e.g., modified road tax or custom add-ons); soft-deletes redundant copies via `execute_session_cleanup()` (`move_to_trash()`).
- **REST Endpoints & Schemas**: `POST /api/copilot/chat`, `POST /api/copilot/sessions/cleanup-duplicates`, and `POST /api/copilot/profiles/cleanup-dummy` in `backend/app/api/routes.py`; models `CopilotChatRequest`, `CopilotChatResponse`, `SessionCleanupRequest`, and `ProfileCleanupRequest` in `backend/app/api/schemas.py`.
- **Global AI Copilot UI**: `frontend/src/components/global-ai-copilot.tsx` provides an expandable Apple-style monochromatic conversational drawer with auto-scrolling message thread, scope anchors (`⚡ EV Scope`, `🚗 ICE Scope`, `🔍 Check Duplicates`), and interactive in-chat action cards (session duplicate review card with 1-click clean, catalog mutation diff preview with checkboxes, and profile cleanup).
- **Navigation Cleanup**: Obsolete "AI & Memory" sidebar item removed from `frontend/src/components/app-shell.tsx`.
- **Hermetic Tests**: `tests/test_copilot_conversational.py` (hermetic SQLite tests for catalog fact loading, session duplicate separation vs unique edits, and chat conversation).

## Quotation Insights & Analytics, Sequential Vehicle Ownership, and Activity Tracking (v23) Additions

- **Data Models & Migration**: Migration `migrations/050_quotation_insights_and_vehicle_tracking.sql` introduces `tracked_vehicles`, `vehicle_ownerships`, and `quotation_activities` tables; adds `quotation_status`, `closed_at`, `miss_reason`, and `tracked_vehicle_id` columns to `sessions`.
- **Vehicle Tracking Service**: `backend/app/services/vehicle_tracking_service.py` normalizes Malaysian vehicle plates (splitting letters/numbers with regex `([A-Z]+)(\d+)` to `ABC 1234`), evaluates validity dates (`valid_until` / `issue_date`) to track sequential owners (1st Owner, 2nd Owner, etc.), creates transfer audit records, and builds full ownership timeline history.
- **Quotation Activity Ledger & Insights Service**: `backend/app/services/quotation_activity_service.py` logs scan/edit/send/status events, groups activities into a calendar view with time breakdown (`get_calendar_activities`), tracks Hit/Miss conversion metrics, and provides automated historical backfill (`backfill_existing_sessions`).
- **REST Endpoints & Schemas**: `GET /api/insights/calendar`, `POST /api/insights/sessions/{id}/activity`, `POST /api/insights/sessions/{id}/status`, `GET /api/insights/analytics`, `GET /api/insights/vehicles/{no}/history`, `POST /api/insights/backfill`, `GET /api/insights/backfill/preview`, `POST /api/insights/backfill/confirm`, and `GET /api/insights/clients` in `backend/app/api/routes.py`; models `QuotationActivityCreateRequest`, `QuotationStatusUpdateRequest`, and `BackfillConfirmRequest` in `backend/app/api/schemas.py`.
- **Connected Client Dossier Service**: `backend/app/services/client_dossier_service.py` connects client records to tracked vehicles, sequential ownerships, quotation sessions, and win/loss conversion statistics with pagination and search.
- **Frontend Insights Cockpit**: `frontend/src/app/insights/page.tsx` introduces the "Insights & Analytics" page with 4 dedicated tabs:
  1. *Calendar*: Microsoft Teams-style interactive schedule (`teams-calendar-view.tsx`) with Month, Week, and Day hourly zooming (`08:00 AM` to `08:00 PM`) and status/vehicle modals.
  2. *Hit & Miss Ledger*: Chronological activity feed (`hit-miss-calendar.tsx`) with time labels, status badges, diff view, 1-click Hit/Miss status modal with loss reasons.
  3. *Client Records*: Connected CRM client dossier (`connected-client-dossier.tsx`) linking clients with sequential vehicle ownerships, past quotations, and win/loss KPIs. Legacy `/client-records` redirects to `/insights?tab=clients`.
  4. *Analytics & Conversion*: Real-time conversion metrics, month-by-month historical comparison table, and loss reason / insurer breakdown charts (`insights-analytics-view.tsx`).
- **Interactive Two-Step Session Backfill**: `frontend/src/components/insights/sync-sessions-modal.tsx` inspects detected sessions, categorizes them as ready vs ambiguous with issue reasons, allows inline plate/customer edits, and confirms selected sessions.
- **Export Interception & Owner Transfer Banner**:
  - `frontend/src/components/insights/send-to-client-dialog.tsx`: Intercepts "Copy PNG", "Download PNG", and "Download PDF" actions in `review-phase.tsx` prompting *"Are you sending this to client?"* with *"Sent to Client"* vs *"Internal Save Only"*.
  - `frontend/src/components/session-workspace/review-phase.tsx`: Displays sequential owner change alert banner when a quotation is uploaded for an existing vehicle with a newer validity date and different customer name.
- **Global AI Copilot Overhaul & Dataset Intelligence**:
  - `frontend/src/components/global-ai-copilot.tsx`: Circular floating robot trigger button with smooth horizontal hover expand to `"Start Chat"`, expandable drawer width toggle (`w-[480px]` to `w-[780px]`), and `<option value="all">All Companies (Comparative)</option>` in insurer context selector.
  - `backend/app/services/copilot_chat_service.py`: `get_dataset_analytics_facts()` provides live aggregation of engine CC brackets (`<=1,000 cc`, `1,001–1,500 cc`, `1,501–2,000 cc`, `>2,000 cc`), insurer quotation volume and market share % ranking, vehicle make/model frequency, and top optional add-on benefits with structured markdown reporting.
- **Database Hygiene**: `commands/clean-legacy-test-data.py` (idempotent, dry-run default, `--apply`) safely purges legacy prototype test records (`client_records`) and deactivates legacy test users without violating foreign key constraints.
- **Hermetic Tests & A-to-Z Playwright Suite**: `tests/test_copilot_conversational.py` (all 4 tests green), `tests/` total 697 tests passing hermetically in 74s, and full end-to-end browser audit `.qc-tmp/audit_full_system_a_to_z.mjs` verifying authentication, upload, review workspace, insights, builder, and copilot analytics.

## Test Upload Sessions & Isolated Sandbox Mode (v23) Additions

- **Data Models & Migration**: Migration `migrations/052_test_upload_sessions.sql` introduces `is_test BOOLEAN NOT NULL DEFAULT false` column on `sessions`, `uploaded_files`, and `batches`, with an index on `sessions(is_test)`.
- **Intake & Service Pipeline**: `backend/app/services/upload_intake_service.py` and `backend/app/services/upload_service.py` propagate the `is_test` flag from upload intake through asynchronous worker jobs, `Batch`, `UploadedFile`, and `QuotationSession`.
- **Strict Isolation Guarantees**:
  1. *Customer Records (`client_records`)*: `backend/app/services/client_record_service.py:upsert_from_draft` aborts immediately when `session.is_test` is true, ensuring test sessions never taint customer CRM dossiers.
  2. *Hit & Miss Ledger & Calendar (`quotation_activities`)*: `backend/app/services/quotation_activity_service.py:log_quotation_activity` aborts immediately for test sessions; calendar and insights queries filter out `SessionModel.is_test.is_(False)`.
  3. *Vehicle Tracking (`tracked_vehicles`, `vehicle_ownerships`)*: `backend/app/services/vehicle_tracking_service.py:get_or_create_vehicle_tracking` returns `(None, None)` for test sessions, preventing simulated plate numbers from registering as real cars or sequential ownership transfers.
  4. *PDF Export Guard*: `backend/app/services/pdf_service.py` skips client record creation and quotation activity logging during official PDF generation when `session.is_test` is true.
  5. *Copilot & AI Insights*: `copilot_chat_service.py` and `client_dossier_service.py` filter out test sessions from analytical calculations and client history.
- **Frontend Toggle & Sessions Filtering**:
  - `frontend/src/app/upload/page.tsx`: Single and Bulk upload tabs include a distinct "Test Upload Mode" toggle with clear explanation.
  - `frontend/src/app/sessions/page.tsx`: Type filter dropdown (`All Uploads`, `Live Only`, `Test Uploads Only`), and distinctive amber `Test Upload` badge with Sparkle icon on vehicle groups (`QuotationRow`) and timeline cards (`SessionCard`).
  - `frontend/src/components/session-workspace/review-phase.tsx`: Top header bar displays amber `Test Upload (Sandbox)` badge; export dialog skips activity recording.
- **Hermetic Tests**: `tests/test_upload_intake.py` and `tests/test_quotation_activity.py` verifying end-to-end `is_test` propagation, activity suppression, and analytic isolation.

## Corporate Fleet Architecture & Bulk PDF Operations (v23) Additions

- **Corporate Identity & Fleet Resolution**:
  - `backend/app/services/client_dossier_service.py`: `_resolve_session_client_identity` intelligently detects corporate naming suffixes (`Sdn Bhd`, `Bhd`, `Enterprise`, `PLT`, BRN) to unify corporate accounts even when driver names are absent or variable.
  - `_categorize_vehicle`: Categorizes fleet vehicles into `lorry`, `motorcycle`, `suv`, `sedan`, `ev` based on vehicle category and model text.
  - Multi-vehicle simultaneous co-ownership allows single corporate entities (factories, logistics firms) to hold 100+ vehicles simultaneously without triggering false single-owner sequential transfer alerts.
- **Bulk Quotation Status & Deal Cycle Resolution**:
  - `backend/app/services/quotation_activity_service.py:bulk_update_quotation_status`: Atomically applies `hit` or `miss` across selected sessions, updates policy dates, and automatically marks alternative underwriter competitor quotes for the same vehicles as `superseded`.
  - `POST /api/sessions/bulk-status`: Endpoint with `BulkQuotationStatusRequest` validating session IDs and dates.
- **In-Memory ZIP Streaming & Direct PDF Retrieval**:
  - `POST /api/sessions/bulk-download-zip`: Streams a dynamically generated in-memory ZIP archive (`io.BytesIO` + `zipfile.ZipFile`, zero disk footprint) containing all selected quotation PDFs named cleanly as `{Plate}_{Insurer}_{QuoteRef}.pdf`.
  - `GET /api/sessions/{session_id}/pdf`: Canonical permanent direct link to either the latest generated PDF version or the source uploaded file.
- **Upload Intake Limit Scaled**:
  - `backend/app/services/admin_service.py:get_bulk_upload_limit`: Default bulk intake raised from 5 to 10 PDFs (configurable up to 25).
- **Frontend Cockpit & CRM Upgrades**:
  - `frontend/src/app/sessions/page.tsx`: Enhanced bulk action bar when quotations are selected:
    1. *Copy PDF Links*: Copies newline-separated direct URLs.
    2. *Copy Fleet Table*: Copies TSV formatted summary (`Plate | Fleet | Model | Insurer | Premium | Status | Quote Ref | PDF Link`) for direct pasting into Microsoft Excel / Google Sheets or WhatsApp.
    3. *Download ZIP*: 1-click download of all selected quotation PDFs.
    4. *Batch Status*: Modal to mark all selected quotes as HIT (Won) or MISS (Lost) with automatic sibling superseding.
    5. Direct PDF button on every session row.
  - `frontend/src/components/insights/connected-client-dossier.tsx`: Added Client Type filter toggle (`All Account Types`, `Corporate Fleets`, `Private Individuals`), `Corporate Fleet` badge, vehicle mix chips (`🚚 15 Lorries`, `🏍️ 30 Motorcycles`, `🚙 40 SUVs`, `🚗 20 Sedans`, `⚡ 5 EVs`), and 1-click fleet actions (*Copy All PDF Links*, *Copy Fleet Table*, *Download Fleet ZIP*).
- **Hermetic Tests**:
  - `tests/test_corporate_fleet_and_bulk_export.py`: Tests corporate identity resolution, vehicle categorization, bulk status updates with sibling quote superseding, and in-memory zip archive streaming.
  - `tests/test_upload_limits.py`: Updated default bulk limit assertions to 10.

## Debris Pruning, Command Rationalization & Backend Modularization (v24) Additions

- **Commands Architecture**: Top-level `commands/` cleaned down to 22 active operational scripts (`start-*`, `verify-deploy-gate.ps1`, `test-all.ps1`, `init_db.py`, `create_admin.py`, active seeders, code map & brain verifiers). 40 historical one-off migrations, repairs, and backfill scripts moved to `commands/archive/`.
- **Legacy Route Retirement**: Retired obsolete v1-v6 frontend routes `frontend/src/app/batches/` and `frontend/src/app/review/` (fully superseded by unified `/sessions/[id]` workspace since v7); removed route matchers from `frontend/src/middleware.ts`; updated static regression contract in `tests/test_frontend_v7_upload_contract.py`.
- **Workspace & Docs Debris Purge**: Removed 34.7 MB `company_based/` exploratory data, purged 1,160+ scratch files in `/.qc-tmp/`, removed 5.8 MB binary ZIP archive and 7 `.docx` files in `docs/benefits/`, consolidated `amgen.md` into `docs/benefits/concise/amgen.md`, cleaned redundant desktop copy assets (`assets/* - Copy.png`), and removed stray `docs/h.html` & `docs/h.md`.
- **Backend API Modularization (Phase 4A)**:
  - Modularized the monolithic ~3,925-line `backend/app/api/routes.py` into 7 domain `APIRouter` modules under `backend/app/api/routers/`:
    - `routers/auth.py` (8 endpoints): Auth, login, logout, me, user management (`/auth/*`, `/settings/users`).
    - `routers/catalogs.py` (85 endpoints): Insurers, benefit profiles, packages, offerings, conditions, matrix (`/business/*`).
    - `routers/copilot.py` (8 endpoints): Conversational Copilot, session deduplication, AI system prompt, grounding chat (`/copilot/*`, `/settings/ai-*`).
    - `routers/insights.py` (22 endpoints): Hit/Miss calendar, sequential vehicle ownership tracking, client dossier CRM (`/insights/*`, `/client-records/*`).
    - `routers/sessions.py` (33 endpoints): File uploads, ingestion jobs, sessions, quotation drafts, workspace, bulk operations (`/sessions/*`, `/drafts/*`, `/uploads/*`, `/jobs/*`, `/batches/*`).
    - `routers/system.py` (51 endpoints): Health, system checks, road tax rule management, trash, notifications (`/health`, `/system/*`, `/trash/*`, `/notifications/*`, `/admin/*`).
    - `routers/templates.py` (42 endpoints): Quotation templates, benefit card presets, visual asset libraries (`/business/templates/*`, `/business/benefit-card-presets/*`, `/business/assets/*`, `/admin/templates/*`).
    - `routers/common.py`: Shared byte-range PDF response streamer (`_pdf_response`).
  - Master `backend/app/api/routes.py`: Maintains 100% backward compatibility via router aggregation, re-exports, and a dynamic monkeypatch propagation proxy ensuring hermetic unit tests patching `app.api.routes` continue to seamlessly intercept target service calls in subrouters.
- **God Service Modularization (Phase 4B)**:
  - Decomposed `backend/app/services/business_setup_service.py` (~2,958 lines, 79 functions) into 6 domain services + shared common:
    - `business_setup_common.py`: Shared constants (`BUSINESS_ROLES`, `OFFERING_KINDS`, `STATUSES`, `ALIAS_KINDS`, `VARIANT_TYPES`) and validation helpers (`_require_business`, `_slug`, `_require_revision`, `_audit`, `_asset_summary`, `_normalize_string_list`).
    - `company_setup_service.py` (18 functions): Insurer company CRUD, aliases, products, tiers, and workspace.
    - `benefit_concept_service.py` (7 functions): Master benefit concepts, description variants, and display overrides.
    - `business_asset_service.py` (13 functions): Asset library, category folders, batch uploads, file replacement, and move/delete operations.
    - `catalog_lifecycle_service.py` (14 functions): Catalog offerings, package assignments, draft revisions, and publication.
    - `benefit_profile_service.py` (18 functions): Unified global benefit profiles, company baseline configs, costing formula, deep cloning, and activation.
    - `company_benefit_condition_service.py` (3 functions): Conditional benefit upgrade rules engine.
    - `business_setup_service.py`: Preserved as facade with dynamic monkeypatch propagation proxy and complete symbol re-exports.
  - Decomposed `backend/app/services/workspace_service.py` (~2,253 lines, 49 functions) into read/write services + shared common:
    - `workspace_common.py`: Shared constants, validation schemas, and core draft loaders (`_utcnow`, `_session_and_draft`, `_rows_for_draft`, `_template_for_draft`, `_field_summary`, `generation_blockers`).
    - `workspace_snapshot_service.py` (10 functions): Pure read-side snapshot compilation, capability detection, benefit cards, package tiers, and overview matrices.
    - `workspace_patch_service.py` (32 functions): Pure write-side patch mutation engine, catalog pinning, package plan selections, and totals recomputation.
    - `workspace_service.py`: Preserved as facade with complete symbol re-exports and monkeypatch propagation proxy.
- **Frontend Mega-Component Modularization (Phase 4C)**:
  - Decomposed `frontend/src/app/builder/benefits/page.tsx` (from 5,401 lines down to 3,683 lines, ~32% reduction):
    - `types.ts`: Extracted shared UI types, `TourStep` definitions, benefit condition operators, and fallback label maps.
    - `components/benefit-conditions-tab.tsx`: Extracted Tab 3 conditional rules editor, criteria badges, and rule builder.
    - `components/overview-matrix-tab.tsx`: Extracted Tab 4 cross-insurer underwriting benefit comparison matrix table.
    - `components/company-benefits-tab.tsx`: Extracted Tab 1 insurer master benefit pool, company selector, and quick search.
    - `components/benefits-step-navigator.tsx`: Extracted step flow navigator bar with interactive tab transitions.
    - `components/benefits-dialogs.tsx`: Extracted modal dialogs (Add config, clone package, new bundle, AI spec, condition rules, clone profile).
  - Decomposed `frontend/src/components/session-workspace/review-phase.tsx` (from 5,280 lines down to 2,702 lines, ~49% reduction):
    - `review-components/benefit-cards.tsx`: Extracted `IncludedCard` and `AddonCard` components with interactive status toggles and price editing.
    - `review-components/review-header.tsx`: Extracted top header bar, view switchers, PDF toggle, and PNG/PDF export buttons.
    - `review-components/review-banners.tsx`: Extracted ownership conflict gate, resolution alert, and sequential transfer banner.
    - `review-components/review-modals.tsx`: Extracted global benefit library modal, conflict resolution modal, and outbound export prompt.
    - `review-components/extracted-benefits-card.tsx`: Extracted Card 3 (detected package, optional covers, and raw extraction text view).
    - `review-components/benefits-manager-panel.tsx`: Extracted Row 2 benefits manager (defaults, active add-ons, optional covers, and package bundles).
    - `review-components/policy-fields-card.tsx`: Extracted Card 2 policy and vehicle values editor with live CC/kW/EV detection and road tax auto-calculation.




- Start every repository task at [START-HERE.md](START-HERE.md).
- Use [PROJECT-DIAGRAM.md](PROJECT-DIAGRAM.md) for the complete visual workflow and system overview.
- Use [generated/CODEBASE-MAP.md](generated/CODEBASE-MAP.md) to locate routes, symbols, migrations, tests, and commands.
- Inspect current code before editing; the map is a navigation tool, not a source of truth.
- Runtime template assets are under `backend/app/assets/template_assets/` because both the builder and deterministic renderer need deployed access.

## Documentation Ownership

The canonical document for each topic is listed in [START-HERE.md](START-HERE.md). Do not add parallel plans, duplicate maps, or feature-specific Markdown files when the knowledge belongs in an existing document.
