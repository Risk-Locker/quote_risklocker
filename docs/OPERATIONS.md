# Operations

## Configuration Status

| Category | Variables |
| --- | --- |
| Active application settings | `APP_ENV`, `APP_NAME`, `APP_ORIGIN`, `CORS_ORIGINS`, `TRUSTED_HOSTS`, `TRUSTED_PROXY_IPS` |
| Active database settings | `DATABASE_URL` (any Postgres URI — Supabase or self-hosted VPS; prefer the Supabase pooler host, which is IPv4-reachable), optional `DATABASE_PROVIDER` (auto-detected from the URL: `supabase_postgres` when the host contains "supabase", else `postgres`), optional `TEST_DATABASE_URL` |
| Temporary authentication settings | `AUTH_HASH_SECRET`, `SESSION_IDLE_HOURS`, `SESSION_MAX_DAYS`, `SESSION_COOKIE_NAME`, `CSRF_COOKIE_NAME`, `SESSION_COOKIE_SECURE` |
| Dormant mail seam | `EMAIL_PROVIDER=disabled|test|resend`, optional `RESEND_API_KEY`, `EMAIL_FROM`, `EMAIL_REPLY_TO`, `EMAIL_REQUEST_TIMEOUT_SECONDS`, `RESEND_WEBHOOK_SECRET`; current password auth never invokes mail |
| Active Supabase Storage settings | `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `STORAGE_DRIVER`, `SUPABASE_STORAGE_BUCKET` |
| Active resource limits | `MAX_UPLOAD_FILES=1`, `MAX_SOURCE_PDF_BYTES`, `MAX_PDF_PAGES`, `MAX_GENERATED_PDF_BYTES`, `MAX_ASSET_BYTES`, `MAX_ASSET_PIXELS`, `MAX_CATALOG_IMPORT_BYTES`, `MAX_CATALOG_IMPORT_ROWS`, `MAX_TEMPLATE_JSON_BYTES`, `MAX_TEMPLATE_ELEMENTS` |
| Active abuse limits | `RATE_LIMIT_LOGIN_*`, `RATE_LIMIT_UPLOAD_*`, `RATE_LIMIT_PREVIEW_*`, `RATE_LIMIT_GENERATION_*`, `RATE_LIMIT_DOWNLOAD_*`, `RATE_LIMIT_IMPORT_*` |
| Frontend proxy settings | `BACKEND_API_ORIGIN` (required when `next start` runs with `NODE_ENV=production`), `SESSION_COOKIE_NAME` (must match the backend) |
| Defined but currently inactive settings | `ENHANCED_READING_ENABLED`, `STRICT_NO_GUESSING`, `AUTO_DOWNLOAD_GENERATED_PDF` |
| Initial local setup | `INITIAL_ADMIN_EMAIL` |

Use `.env.example` (local development values) or `.env.production` (production VPS values) as the variable-name templates. Never commit live credentials or expose backend-only values in frontend environment variables.

**The project `.env` is the source of truth:** `backend/app/core/config.py` loads it with `load_dotenv(override=True)`, so variables inherited from the shell (e.g. a stray `APP_ENV=production` in a terminal) can never shadow the project config. Reset a poisoned terminal with `Remove-Item Env:APP_ENV` or open a new one.

**Malware scanner is always required:** the `REQUIRE_MALWARE_SCANNER` env toggle no longer exists (`backend/app/core/config.py` hardcodes it on). Every PDF upload runs the scanner; uploads refuse when no scanner is present. Do not restore the toggle.

**Switching database servers:** the app uses one Postgres database. To move between Supabase and a self-hosted VPS Postgres, change only `DATABASE_URL` in `.env` (and run migrations against the new server). `DATABASE_PROVIDER` is optional and auto-detected from the URL, so no other variable needs to change.

The three inactive settings are loaded by backend configuration but do not change runtime behavior. Do not rely on them, add them to deployment configuration, or describe them as feature controls until they are wired into behavior or removed.

## Local Setup and Run

1. Create the Python **3.12** environment (`py -3.12 -m venv .venv`; the pinned requirements predate Python 3.14 wheels), install `requirements.txt` and optional requirements (`.\.venv\Scripts\python.exe -m pip install -r requirements.txt -r requirements-optional.txt`), then install Playwright Chromium (`.\.venv\Scripts\python.exe -m playwright install chromium`).
2. Install frontend dependencies in `frontend/`.
3. Configure `.env` from `.env.example` (local) or `.env.production` (production); production requires HTTPS origin, exact hosts/proxies, a long hash secret, and Supabase credentials. Malware scanning is always required on uploads — there is no toggle.
4. Apply migrations with `commands/apply-migrations.ps1`, initialize non-credential defaults explicitly, and bootstrap Primary Admin once with `python commands/create_admin.py first.last@risklocker.com`.
5. Use `npm run backend`, `npm run frontend`, or `npm run full` to start development services. `npm run full` starts the API, frontend, and exactly one extraction/render worker. Use `npm run stop` to stop project servers.
6. Port coordination: `commands/start-backend.ps1` writes the chosen port to `.qc-tmp\backend-port.txt`; `start-frontend.ps1` and `start-full.ps1` read it. Backend :8100, frontend :3000.

## QA and E2E Tooling (in-repo, gitignored)

- All QA artifacts live in `/.qc-tmp/` INSIDE the repository (never `%TEMP%` or outside paths).
- Playwright is available from `frontend/node_modules` (require path in scripts: `C:/.../frontend/node_modules/playwright`).
- Scripts: `groups3-e2e.js` (group/marquee E2E — add 3 texts, marquee-select 3, group, drag group, ungroup), `marquee-probe.js` (marquee lifecycle diagnostics with console capture), plus older groups/groups2/debug scripts. Screenshots go to `.qc-tmp/shots/`.
- Run: `node .qc-tmp/groups3-e2e.js` with backend :8100 and frontend :3000 up.
- Dev login for E2E: admin@risklocker.local / admin123. Default motor template: `4a16bc96-7ca1-44db-be1b-c0a462e71e2f` (5 image, 24 text, 11 variable, 4 group elements; no specials — E2E group tests must add text elements first).
- Logs from `commands/start-*.ps1` redirects go to `.qc-tmp/` too.

## Maintenance

- Automatic PDF expiry and Trash purge are disabled. WP9 supplies the reference-aware manual purge workflow; do not schedule legacy expiry commands.
- Run `npm run code-map` after structural changes and `npm run code-map:check` before completing work.
- Migrations are ordered SQL files under `migrations/` and must be applied against Supabase/Postgres only.
- Pre-ledger databases (schema applied before the migration-ledger system existed, so `schema_migrations` is missing/empty): run `python commands/backfill-ledger.py` (`--dry-run` first; defaults to recording versions 001-022, refuses to run if the ledger already has rows) before `commands/apply-migrations.ps1`. The runner executes migration SQL through the raw DBAPI cursor (`backend/app/db/migrations.py` `apply_migrations`) because psycopg3 client-side binding rejects `%I` (Postgres `format()` in `DO` blocks) and SQLAlchemy `text()` misreads `:NN` inside JSON literals.
- `openpyxl` (requirements.txt) powers the settings CSV/Excel imports — road tax export/import, vehicles multi-sheet Excel import, field-alias import. Uploads are validated server-side (extension/size/row caps; Excel read data-only, no formula evaluation).
- Migration checksums are computed from line-ending-normalized bytes (`backend/app/db/migrations.py` `migration_checksums`: CRLF/CR normalized to LF before hashing, plus a CRLF-equivalent hash), so the same SQL yields the same checksum on every OS and git checkout style. New ledger rows record the normalized checksum; historically applied rows are still accepted when their stored checksum equals any line-ending-equivalent representation of the current file (this is why production ledger row 036, recorded from CRLF bytes as `d8fdd09a...`, remains valid after the LF deployment). Genuine content changes still fail drift detection. `.gitattributes` enforces `migrations/*.sql text eol=lf`; do not remove that rule (kept for deterministic diffs).
- Migration `037_draft_package_pin.sql` adds `quotation_drafts.package_id` to persist active comprehensive package tiers per quotation draft.
- Data repair runbook: `commands/repin-amassurance-sessions.py` (idempotent, dry-run default, `--apply` to execute) aligns AmAssurance drafts pinned to older revisions or missing `package_id` to the latest published revision (e.g. rev 3) and re-seeds tier defaults.
- Frontend middleware (`frontend/src/middleware.ts`) guards protected routes by session cookie server-side; the cookie name must match `SESSION_COOKIE_NAME` in the backend `.env`.

## Deployment Boundaries

- The application requires HTTPS Supabase Storage and private backend access to the service-role key.
- Production requires one HTTPS origin, exact host/proxy configuration, secure cookies, CSRF, scanning, and a current migration ledger.
- `SESSION_IDLE_HOURS` is fixed at eight and rolls on authenticated activity; `SESSION_MAX_DAYS` is fixed at 30 as the hard server-side session limit.
- `AUTH_HASH_SECRET`, Supabase credentials, and `BACKEND_API_ORIGIN` are server-only. The browser has no backend-origin environment variable.
- Legacy passwordless structures remain compatibility data but are not active core behavior. WP13 replaces authentication only after core approval.
- The storage bucket is private and created/checked by backend startup.
- Microsoft 365 archive integration stays disabled until backend deployment credentials and its archive worker are deliberately configured.
- The app owns trusted-host/origin validation, CSRF, headers, and Postgres rate limits. Checked-in CI, production observability, backup drills, and alerts are WP11 deliverables.

## Production Deployment (VPS)

- Runtime: three PM2 processes (`ecosystem.config.cjs`) — `rl-quote-api` (uvicorn :8100), `rl-quote-worker` (`commands/run-worker.py`), `rl-quote-frontend` (`next start` :3000). Paths derive from `RL_DEPLOY_PATH`.
- The API must run with `ENABLE_EMBEDDED_WORKER=0` so jobs are claimed only by the dedicated worker.
- nginx (`deploy/nginx-quote-risklocker.conf`): `/api/ -> 127.0.0.1:8100/api/`, `/ -> 127.0.0.1:3000`, `client_max_body_size 25m`, HTTPS via certbot.
- Production `.env` values: `APP_ORIGIN`/`TRUSTED_HOSTS`/`CORS_ORIGINS=https://quote.risklocker.com`, `TRUSTED_PROXY_IPS=127.0.0.1` (nginx on the same host), `SESSION_COOKIE_SECURE=true`.
- Migrations on the VPS: `PYTHONPATH=backend .venv/bin/python -m app.db.migrations` (idempotent; runs on every deploy).
- CI/CD: `.github/workflows/deploy.yml` (tests + build on GitHub, then rsync + install + migrate + `pm2 startOrReload` on the VPS). Secrets: `VPS_HOST`, `VPS_PORT`, `VPS_USER`, `VPS_SSH_KEY_B64`.
- One-time bootstrap: `deploy/setup-vps.sh` (see `docs/SETUP.md`).
