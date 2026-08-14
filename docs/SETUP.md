# Setup and Deployment Runbook (Universal)

Template for deploying this project (and any project this folder is copied into). All hosts, domains, IPs, and credentials are PLACEHOLDERS — never write real values into this file. Update this file whenever infrastructure changes (new subdomain, database move, new service, monitoring change).

## 1. Hosting and Domain

- Provision a VPS (placeholder: `vps.example.com`, OS placeholder: Ubuntu 24.04 LTS).
- Create a DNS A record: `app.example.com -> <VPS_IP>` (placeholder).
- Add a subdomain per environment: `staging.app.example.com`, `prod.app.example.com` (placeholders).
- Terminate HTTPS at the edge (Caddy / Nginx / cloud LB — placeholder choice). Both frontend and backend cookies require HTTPS.

## 2. Reverse Proxy Layout

- Frontend: Next.js standalone on `127.0.0.1:3000` (started via `commands/start-frontend.ps1` or the equivalent production runner).
- Backend: FastAPI/uvicorn on `127.0.0.1:8100` (`commands/start-backend.ps1`).
- Proxy rules: `/ -> :3000`, `/api -> :8100` on one HTTPS origin. A separate public backend origin is not supported by v7.

## 3. Environment Configuration

- Copy `.env.example` to `.env`; every variable table lives in `docs/OPERATIONS.md` (env matrix).
- Secrets stay backend-only: `AUTH_HASH_SECRET`, `SUPABASE_SERVICE_ROLE_KEY`, and any optional mail-provider secret. Core defaults `EMAIL_PROVIDER=disabled`; live Resend and authentication use remain post-core work.
- The browser always uses relative `/api`; `BACKEND_API_ORIGIN` is a server-only Next.js proxy setting.

## 4. Database

- CURRENT: Supabase/Postgres (`DATABASE_URL` points at Supabase).
- MIGRATION PATH (if Supabase is replaced by self-hosted Postgres on the VPS):
  1. Install PostgreSQL on the VPS; create a database and an app user with least privilege.
  2. Point `DATABASE_URL` at the self-hosted server (placeholder connection string, sslmode as configured).
  3. Apply ordered migrations with `commands/apply-migrations.ps1`; the runner hashes, ledgers, locks, and transactionally applies SQL.
  4. Initialize non-credential defaults explicitly and bootstrap Primary Admin once with `python commands/create_admin.py first.last@risklocker.com` (interactive password prompts).
  5. Schedule backups: `pg_dump` nightly to off-server storage; test a restore at least monthly.
- Web workers run no retention/purge job. Source/generated PDFs remain until manual deletion and Trash is manually purged.

## 5. PDF Storage

- CURRENT: private Supabase Storage bucket, created/checked at backend startup.
- The bucket is private; the backend uses the service-role key only.
- If self-hosting everything, storage must remain private and HTTPS-only; never persist PDFs in repo or public directories.

## 6. PDF Rendering Runtime

- Production images pin Playwright and Chromium. Renderer unavailability is retryable failure; no fallback PDF is allowed.

## 7. Optional Integrations

- Microsoft 365 archive: optional, backend-only. Requires an app registration + delegated permission flow (placeholders for tenant/app IDs). Keep disabled until credentials and the archive worker are deliberately configured.
- Core may ship a disabled/test/Resend provider adapter that is not called by authentication. Real delivery, domain setup, OTP, and onboarding remain post-core work.

## 8. Monitoring and Alerts

- Health endpoints live under `/api`; readiness includes schema-ledger validation and is expanded in WP11.
- Options (choose per environment): Uptime Kuma, Prometheus + Grafana, or platform built-ins (placeholders).
- Alert on: readiness failure, queue age, repeated render/scanner/storage failures, backup failure, and database exhaustion.
- Logging: capture backend and frontend stdout to files; rotate weekly; keep at least 30 days.

## 9. When to Update This File

- Any infrastructure change: new subdomain, VPS move, database provider change (e.g., Supabase -> self-hosted Postgres), storage provider change, monitoring tool change, HTTPS/termination change.
- Update `docs/OPERATIONS.md` env tables in the same change, and log it in `docs/MEMORY.md`.
