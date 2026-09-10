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

## Benefit Presets (v10) Additions

- Centralized Presets: `frontend/src/lib/benefit-presets.ts` (`SYSTEM_BENEFIT_PRESETS`, `getBenefitPreset`, `applyPresetToCanvasElement`). 6 presets: Masonry Flow, Compact Minimalist, Signature 2-Col, Elevated 3D, Grid Tile, Dark Luxury.
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

## Deployment Additions

- `.github/workflows/deploy.yml` — on push to `main`: backend pytest + frontend `tsc --noEmit` + `next build` on GitHub, then rsync to the VPS, install deps, run migrations, `pm2 startOrReload`.
- `ecosystem.config.cjs` — PM2 apps `rl-quote-api`, `rl-quote-worker`, `rl-quote-frontend`; paths from `RL_DEPLOY_PATH`.
- `deploy/nginx-quote-risklocker.conf` — nginx reverse proxy template for `quote.risklocker.com` (certbot adds TLS).
- `deploy/setup-vps.sh` — idempotent one-time VPS bootstrap (system packages, venv, Chromium, build, migrations, nginx, certbot, PM2 startup).

## Navigation

- Start every repository task at [START-HERE.md](START-HERE.md).
- Use [PROJECT-DIAGRAM.md](PROJECT-DIAGRAM.md) for the complete visual workflow and system overview.
- Use [generated/CODEBASE-MAP.md](generated/CODEBASE-MAP.md) to locate routes, symbols, migrations, tests, and commands.
- Inspect current code before editing; the map is a navigation tool, not a source of truth.
- Runtime template assets are under `backend/app/assets/template_assets/` because both the builder and deterministic renderer need deployed access.

## Documentation Ownership

The canonical document for each topic is listed in [START-HERE.md](START-HERE.md). Do not add parallel plans, duplicate maps, or feature-specific Markdown files when the knowledge belongs in an existing document.
