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

## Navigation

- Start every repository task at [START-HERE.md](START-HERE.md).
- Use [PROJECT-DIAGRAM.md](PROJECT-DIAGRAM.md) for the complete visual workflow and system overview.
- Use [generated/CODEBASE-MAP.md](generated/CODEBASE-MAP.md) to locate routes, symbols, migrations, tests, and commands.
- Inspect current code before editing; the map is a navigation tool, not a source of truth.
- Runtime template assets are under `backend/app/assets/template_assets/` because both the builder and deterministic renderer need deployed access.

## Documentation Ownership

The canonical document for each topic is listed in [START-HERE.md](START-HERE.md). Do not add parallel plans, duplicate maps, or feature-specific Markdown files when the knowledge belongs in an existing document.
