# Operations

## Configuration Status

| Category | Variables |
| --- | --- |
| Active application settings | `APP_ENV`, `APP_NAME`, `CORS_ORIGINS` |
| Active database settings | `DATABASE_PROVIDER`, `DATABASE_URL`, optional `TEST_DATABASE_URL` |
| Active authentication settings | `AUTH_HASH_SECRET`, `AUTH_CODE_EXPIRE_MINUTES`, `AUTH_CODE_MAX_ATTEMPTS`, `AUTH_CODE_RESEND_SECONDS`, `SESSION_IDLE_HOURS`, `SESSION_MAX_DAYS`, `SESSION_COOKIE_NAME`, `SESSION_COOKIE_SECURE` |
| Active backend mail settings | `SMTP_HOST`, `SMTP_PORT`, optional `SMTP_USERNAME`, backend-only `SMTP_PASSWORD`, `SMTP_FROM_EMAIL`, `SMTP_STARTTLS`, `SMTP_USE_SSL` |
| Active Supabase Storage settings | `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `STORAGE_DRIVER`, `SUPABASE_STORAGE_BUCKET` |
| Active processing and retention settings | `PDF_RETENTION_DAYS`, `TRASH_RETENTION_DAYS`, `MAX_UPLOAD_BYTES`, `REQUIRE_MALWARE_SCANNER` |
| Defined but currently inactive settings | `ENHANCED_READING_ENABLED`, `STRICT_NO_GUESSING`, `AUTO_DOWNLOAD_GENERATED_PDF` |
| Initial local setup | `INITIAL_ADMIN_EMAIL` |

Use `.env.example` as a variable-name template. Never commit live credentials or expose backend-only values in frontend environment variables.

The three inactive settings are loaded by backend configuration but do not change runtime behavior. Do not rely on them, add them to deployment configuration, or describe them as feature controls until they are wired into behavior or removed.

## Local Setup and Run

1. Create the Python environment, install `requirements.txt` and optional requirements, then install Playwright Chromium.
2. Install frontend dependencies in `frontend/`.
3. Configure `.env` with a Supabase/Postgres database URL, long authentication hash secret, backend SMTP relay, Supabase URL, and backend-only service-role key.
4. Apply ordered migrations with `commands/apply-migrations.ps1`, initialize defaults with `commands/init_db.py`, and create/promote a named employee Admin with `commands/create_admin.py first.last@risklocker.com`.
5. Use `npm run backend`, `npm run frontend`, or `npm run full` to start development services. Use `npm run stop` to stop project servers.
6. Port coordination: `commands/start-backend.ps1` writes the chosen port to `.qc-tmp\backend-port.txt`; `start-frontend.ps1` and `start-full.ps1` read it. Backend :8100, frontend :3000.

## QA and E2E Tooling (in-repo, gitignored)

- All QA artifacts live in `/.qc-tmp/` INSIDE the repository (never `%TEMP%` or outside paths).
- Playwright is available from `frontend/node_modules` (require path in scripts: `C:/.../frontend/node_modules/playwright`).
- Scripts: `groups3-e2e.js` (group/marquee E2E — add 3 texts, marquee-select 3, group, drag group, ungroup), `marquee-probe.js` (marquee lifecycle diagnostics with console capture), plus older groups/groups2/debug scripts. Screenshots go to `.qc-tmp/shots/`.
- Run: `node .qc-tmp/groups3-e2e.js` with backend :8100 and frontend :3000 up.
- Dev login for E2E: admin@risklocker.local / admin123. Default motor template: `4a16bc96-7ca1-44db-be1b-c0a462e71e2f` (5 image, 24 text, 11 variable, 4 group elements; no specials — E2E group tests must add text elements first).
- Logs from `commands/start-*.ps1` redirects go to `.qc-tmp/` too.

## Maintenance

- Run `commands/purge-expired-pdfs.py` for a manual PDF-retention cycle; the backend also schedules daily retention.
- Run `commands/purge_trash.py` for scheduled trash maintenance where needed.
- Run `npm run code-map` after structural changes and `npm run code-map:check` before completing work.
- Migrations are ordered SQL files under `migrations/` and must be applied against Supabase/Postgres only.
- `openpyxl` (requirements.txt) powers the settings CSV/Excel imports — road tax export/import, vehicles multi-sheet Excel import, field-alias import. Uploads are validated server-side (extension/size/row caps; Excel read data-only, no formula evaluation).
- Frontend middleware (`frontend/src/middleware.ts`) guards protected routes by session cookie server-side; the cookie name must match `SESSION_COOKIE_NAME` in the backend `.env`.

## Deployment Boundaries

- The application requires HTTPS Supabase Storage and private backend access to the service-role key.
- Production requires the configured SMTP relay and `SESSION_COOKIE_SECURE=true`. HTTPS termination must cover both frontend and backend cookie traffic.
- `SESSION_IDLE_HOURS` is fixed at eight and rolls on authenticated activity; `SESSION_MAX_DAYS` is fixed at 30 as the hard server-side session limit.
- SMTP credentials and `AUTH_HASH_SECRET` are backend-only secrets. Only `NEXT_PUBLIC_API_BASE_URL` belongs in frontend configuration.
- Migration `008_passwordless_auth_sessions.sql` removes password hashes, adds the exact employee-domain database constraint, and creates the login-code and session tables with Data API access revoked.
- Migration 008 is transactional and intentionally stops if a legacy user has a non-normalized, external-domain, or shared/group address. An operator must correct those accounts to confirmed named employee addresses before retrying; the migration never guesses or rewrites identities.
- The storage bucket is private and created/checked by backend startup.
- Microsoft 365 archive integration stays disabled until backend deployment credentials and its archive worker are deliberately configured.
- The repository has no checked-in CI workflow, in-app rate limiter, or HTTP security-header policy. Before production deployment, document the hosting platform, HTTPS termination, rate-limiting owner, security-header owner, logging, and alerting policy. Do not assume an external gateway provides them without verification.
