# Setup and Deployment Runbook

Production deployment for the Risklocker Quotation Converter on the VPS. This file records the real, chosen infrastructure (nginx + PM2 + certbot on one VPS, Supabase cloud). Update it whenever infrastructure changes.

## 1. Hosting and Domain

- VPS: Ubuntu 24.04 LTS (ships Python 3.12, required by the pinned requirements).
- DNS A record: `quote.risklocker.com -> <VPS_IP>`.
- HTTPS is terminated at nginx with a Let's Encrypt certificate (certbot). The app REQUIRES HTTPS: `SESSION_COOKIE_SECURE=true` and trusted-host validation fail over plain HTTP.

## 2. Runtime Processes (PM2)

Three processes run under PM2 (see `ecosystem.config.cjs`; paths derive from `RL_DEPLOY_PATH`):

| PM2 app | What it runs | Port |
| --- | --- | --- |
| `rl-quote-api` | FastAPI/uvicorn (`app.main:app`) | 127.0.0.1:8100 |
| `rl-quote-worker` | `commands/run-worker.py` (extraction + Playwright PDF render) | — |
| `rl-quote-frontend` | Next.js `next start` | 127.0.0.1:3000 |

- The API runs with `ENABLE_EMBEDDED_WORKER=0`; exactly one dedicated worker claims jobs.
- The backend reads the root `.env` itself (python-dotenv walks up from `backend/app/core/config.py`); no secrets are passed via PM2.

## 3. Reverse Proxy Layout (nginx)

- `deploy/nginx-quote-risklocker.conf` is the checked-in template (port 80). certbot adds the 443 block + redirect.
- Proxy rules: `/api/ -> 127.0.0.1:8100/api/`, `/ -> 127.0.0.1:3000`. The browser always uses same-origin `/api`; a separate public backend origin is not supported.
- `client_max_body_size 25m` (uploads cap at 20MB).
- Security headers incl. a pragmatic CSP for Next.js (inline scripts/styles for hydration; `img-src data: blob:` for the canvas renderer).

## 4. Environment Configuration

- Copy `.env.example` to `.env` on the VPS; the variable matrix lives in `docs/OPERATIONS.md`.
- Production values: `APP_ORIGIN`/`TRUSTED_HOSTS`/`CORS_ORIGINS=https://quote.risklocker.com`, `TRUSTED_PROXY_IPS=127.0.0.1` (nginx is on the same host), `SESSION_COOKIE_SECURE=true`.
- Secrets stay backend-only: `AUTH_HASH_SECRET`, `SUPABASE_SERVICE_ROLE_KEY`, `GEMINI_API_KEY`. CI never writes secrets; `.env` exists only on the VPS.

## 5. Database

- Supabase/Postgres (`DATABASE_URL` points at Supabase). No local Postgres on the VPS.
- Migrations are applied with `PYTHONPATH=backend .venv/bin/python -m app.db.migrations` (ledger-based, checksummed, idempotent — safe on every deploy).
- Bootstrap Primary Admin once: `PYTHONPATH=backend .venv/bin/python commands/create_admin.py first.last@risklocker.com` (interactive password).
- Backups: `pg_dump` nightly to off-server storage; test a restore at least monthly.

## 6. PDF Storage

- Private Supabase Storage bucket, created/checked at backend startup; backend uses the service-role key only. Never persist PDFs in the repo or public directories.

## 7. PDF Rendering Runtime

- Playwright + Chromium are pinned in `requirements.txt`. `deploy/setup-vps.sh` installs Chromium with system deps once (`playwright install --with-deps chromium`); deploys run plain `playwright install chromium` (no-op when present). Renderer unavailability is a retryable failure; no fallback PDF is allowed.

## 8. CI/CD (GitHub Actions)

- `.github/workflows/deploy.yml`: on push to `main` (or manual dispatch) it runs backend tests + frontend type-check/build on GitHub, then SSHes to the VPS, rsync-mirrors the repo (excluding `.env`, `.venv`, `node_modules`, `.next`, `.qc-tmp`, etc.), installs deps, builds, runs migrations, and `pm2 startOrReload`.
- The test job installs Playwright Chromium (`python -m playwright install --with-deps chromium`) so `test_pdf_generation_smoke` renders a real PDF instead of skipping; `tests/conftest.py` creates `.qc-tmp/pytest` (the pytest `--basetemp`) because the gitignored folder does not exist on a clean runner.
- Secrets required in the repo: `VPS_HOST`, `VPS_PORT`, `VPS_USER`, `VPS_SSH_KEY_B64` (base64 of the deploy SSH private key).

## 9. One-Time VPS Setup

Run `deploy/setup-vps.sh` (as root, from the cloned repo at `/var/www/html/quote_risklocker`). It installs nginx/git/python3.12-venv/Node 22/PM2/certbot, creates the venv, installs deps + Chromium, builds the frontend, applies migrations, installs the nginx site, requests the TLS cert (if `RL_CERTBOT_EMAIL` is set), and configures `pm2 startup`. Full manual steps are in the script header.

## 10. Monitoring and Alerts

- Health: `curl http://127.0.0.1:8100/health` (backend readiness incl. schema-ledger validation).
- Options: Uptime Kuma, Prometheus + Grafana, or platform built-ins.
- Alert on: readiness failure, queue age, repeated render/scanner/storage failures, backup failure, database exhaustion.
- Logging: PM2 writes stdout/stderr to `~/.pm2/logs/`; optionally `pm2 install pm2-logrotate`; keep at least 30 days.

## 11. When to Update This File

- Any infrastructure change: new subdomain, VPS move, database/storage provider change, monitoring/HTTPS change.
- Update `docs/OPERATIONS.md` env tables in the same change and log it in `docs/MEMORY.md`.
