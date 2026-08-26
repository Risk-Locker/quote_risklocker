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

## Benefit Configuration Matrix

- `docs/BENEFITS-CONFIGURATION.md` — canonical per-insurer benefits/add-on matrix: global benefit library (34 concepts), dimensions, and every company × coverage type × vehicle category row including add-on system (`single` vs `package`), package tiers, and seed status (seeded / draft / pending). Registered in `docs/START-HERE.md`.

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
