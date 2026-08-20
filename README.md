# Risklocker Quotation Converter

Private internal application for converting insurer motor quotations into reviewed, versioned Risklocker PDFs.

The staff workflow is: **Upload -> Check Values -> Generate PDF**.

## Stack

- FastAPI, SQLAlchemy, Supabase/Postgres
- Private Supabase Storage for source and generated PDFs
- PyMuPDF, pdfplumber, pikepdf, and optional enhanced-reading tools
- Next.js, React, TypeScript, and Tailwind CSS
- Playwright for deterministic HTML/CSS PDF rendering

## Required Setup

1. Create and activate the Python environment:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install -r requirements-optional.txt
python -m playwright install chromium
```

2. Install frontend dependencies:

```powershell
cd frontend
npm install
cd ..
```

3. Create `.env` from `.env.example` and set the real Supabase and backend SMTP values:

- `DATABASE_URL`: Supabase/Postgres connection string, including `sslmode=require`.
- `AUTH_HASH_SECRET`: long random backend secret used only to hash login challenges.
- `SMTP_HOST`, `SMTP_PORT`, `SMTP_FROM_EMAIL`, and relay credentials: backend-only delivery settings for one-time login codes.
- `SUPABASE_URL`: project URL such as `https://PROJECT_REF.supabase.co`.
- `SUPABASE_SERVICE_ROLE_KEY`: backend-only service-role key.

Never put the authentication hash secret, SMTP credentials, or service-role key in `frontend/.env*` or a `NEXT_PUBLIC_*` variable.

4. Apply the ordered database migrations and seed defaults:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File commands/apply-migrations.ps1
.\.venv\Scripts\python.exe commands/init_db.py
```

5. Create or promote a named employee Admin account:

```powershell
.\.venv\Scripts\python.exe commands/create_admin.py first.last@risklocker.com
```

The Admin signs in by requesting a one-time code from the configured SMTP relay. There is no password login or public registration.

## Run

Manual two-terminal method from the project root:

```powershell
npm run backend
```

```powershell
npm run frontend
```

Open `http://127.0.0.1:3000/login`. The backend selects the first available port from `8100` through `8110`, and the frontend discovers it automatically.

Other commands:

```powershell
npm run full          # opens backend and frontend PowerShell windows
npm run stop          # stops this project's development servers
npm run test          # backend tests, then frontend production build
npm run code-map      # refresh docs/generated/CODEBASE-MAP.md
npm run code-map:check
```

In VS Code, run the task **Risklocker: Start Full App** to use two dedicated integrated terminals.

## PDF Storage

- The backend creates/uses the private bucket `risklocker-pdfs`.
- Original filenames are display metadata only; object paths use database IDs and UUIDs.
- The browser receives authenticated Risklocker content endpoints, never provider URLs or credentials.
- Source and generated PDFs use rolling 30-day retention.
- Expiry removes only the PDF binary. Database history, extracted text, reviewed values, templates, and generated-version snapshots remain.
- Expired generated PDFs can be regenerated as a new version. Expired source PDFs cannot be reconstructed.
- OS temporary directories are used for quarantine, scanning, extraction, and rendering and are deleted after each operation.

Run one retention cycle manually with:

```powershell
.\.venv\Scripts\python.exe commands/purge-expired-pdfs.py
```

## Microsoft 365 Archive

SharePoint/OneDrive is an optional permanent archive. Supabase Storage works without it.

To activate the Microsoft connection, an administrator must first register a Microsoft Entra application and provide backend deployment credentials. The preferred permission model is `Sites.Selected` for the isolated Risklocker SharePoint site, with admin consent. The Admin Storage page intentionally reports setup required until those credentials and the Microsoft Graph archive worker are configured.

## Deployment

Production runs on a VPS under PM2 + nginx (full runbook in `docs/SETUP.md`):

- Three PM2 processes (`ecosystem.config.cjs`): `rl-quote-api` (uvicorn :8100), `rl-quote-worker` (extraction + PDF render), `rl-quote-frontend` (Next.js :3000).
- nginx reverse proxy for `quote.risklocker.com` (`deploy/nginx-quote-risklocker.conf`), HTTPS via certbot.
- CI/CD: `.github/workflows/deploy.yml` runs tests + build on GitHub and auto-deploys to the VPS on every push to `main`.
- One-time VPS bootstrap: `deploy/setup-vps.sh`.

## Repository Guide

Codex, other repository-capable AI agents, and maintainers start with [docs/START-HERE.md](docs/START-HERE.md). Product behavior, design rules, code mapping, template references, and operational guidance live under `docs/`. Operational scripts live under `commands/`.

Private customer/process references are outside this repository at:

`C:\Users\user\Desktop\dev\quote\risklocker-reference-archive`
