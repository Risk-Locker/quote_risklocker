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
- Proxy rules: `/ -> :3000`, `/api -> :8100` (or a dedicated backend subdomain). CORS origins must list the real public origin.

## 3. Environment Configuration

- Copy `.env.example` to `.env`; every variable table lives in `docs/OPERATIONS.md` (env matrix).
- Secrets stay backend-only: `AUTH_HASH_SECRET`, `SMTP_PASSWORD`, `SUPABASE_SERVICE_ROLE_KEY`. Never put them in frontend env vars.
- Only `NEXT_PUBLIC_API_BASE_URL` belongs in frontend configuration; it is derived from `window.location.hostname` in dev.

## 4. Database

- CURRENT: Supabase/Postgres (`DATABASE_URL` points at Supabase).
- MIGRATION PATH (if Supabase is replaced by self-hosted Postgres on the VPS):
  1. Install PostgreSQL on the VPS; create a database and an app user with least privilege.
  2. Point `DATABASE_URL` at the self-hosted server (placeholder connection string, sslmode as configured).
  3. Apply ordered migrations: `commands/apply-migrations.ps1` (uses `migrations/*.sql`).
  4. Initialize defaults and create the Admin: `python commands/init_db.py`, `python commands/create_admin.py first.last@risklocker.com`.
  5. Schedule backups: `pg_dump` nightly to off-server storage; test a restore at least monthly.
- Retention jobs run daily in the backend; manual triggers exist under `commands/`.

## 5. PDF Storage

- CURRENT: private Supabase Storage bucket, created/checked at backend startup.
- The bucket is private; the backend uses the service-role key only.
- If self-hosting everything, storage must remain private and HTTPS-only; never persist PDFs in repo or public directories.

## 6. PDF Rendering Runtime

- Deterministic PDF generation needs Playwright Chromium installed on the VPS: `python -m playwright install chromium` (plus OS deps).

## 7. Optional Integrations

- Microsoft 365 archive: optional, backend-only. Requires an app registration + delegated permission flow (placeholders for tenant/app IDs). Keep disabled until credentials and the archive worker are deliberately configured.
- SMTP relay: production requires a real relay; `SMTP_STARTTLS`/`SMTP_USE_SSL` as per provider.

## 8. Monitoring and Alerts

- Health endpoint: backend `GET /health` (returns `{"status":"Ready",...}`); frontend `/login` 200 check.
- Options (choose per environment): Uptime Kuma, Prometheus + Grafana, or platform built-ins (placeholders).
- Alert on: health check failure, disk usage, failed login spikes, expired-PDF purge errors.
- Logging: capture backend and frontend stdout to files; rotate weekly; keep at least 30 days.

## 9. When to Update This File

- Any infrastructure change: new subdomain, VPS move, database provider change (e.g., Supabase -> self-hosted Postgres), storage provider change, monitoring tool change, HTTPS/termination change.
- Update `docs/OPERATIONS.md` env tables in the same change, and log it in `docs/MEMORY.md`.
