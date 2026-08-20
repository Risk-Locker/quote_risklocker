/**
 * PM2 process configuration for the Risklocker Quotation Converter.
 *
 * Runs three processes (this project's architecture differs from RLTS's
 * single Node server):
 *   1. rl-quote-api      — FastAPI/uvicorn backend on 127.0.0.1:8100
 *   2. rl-quote-worker   — extraction + Playwright PDF render worker
 *   3. rl-quote-frontend — Next.js server on 127.0.0.1:3000
 *
 * Paths are derived from RL_DEPLOY_PATH (set on the VPS, e.g.
 * `RL_DEPLOY_PATH=/var/www/html/quote_risklocker pm2 startOrReload ...`),
 * mirroring the RLTS_DEPLOY_PATH pattern. When run locally it defaults to
 * the repo root.
 *
 * The backend reads the root `.env` itself (python-dotenv walks up from
 * backend/app/core/config.py), so no secrets are passed here.
 */
const path = require("path");

const ROOT = process.env.RL_DEPLOY_PATH || __dirname;
const PYTHON = path.join(ROOT, ".venv", "bin", "python");
const BACKEND = path.join(ROOT, "backend");
const FRONTEND = path.join(ROOT, "frontend");
const APP_ENV = process.env.APP_ENV || "production";

module.exports = {
  apps: [
    {
      name: "rl-quote-api",
      cwd: BACKEND,
      script: PYTHON,
      args: "-m uvicorn app.main:app --host 127.0.0.1 --port 8100",
      interpreter: "none",
      env: {
        PYTHONPATH: BACKEND,
        PYTHONDONTWRITEBYTECODE: "1",
        APP_ENV,
        // Jobs are claimed by the dedicated worker below; keep the API from
        // running its own embedded worker loop (avoids double-processing).
        ENABLE_EMBEDDED_WORKER: "0",
      },
      max_memory_restart: "600M",
      kill_timeout: 15000,
      listen_timeout: 30000,
      autorestart: true,
      time: true,
    },
    {
      name: "rl-quote-worker",
      cwd: ROOT,
      script: PYTHON,
      args: "commands/run-worker.py",
      interpreter: "none",
      env: {
        PYTHONPATH: BACKEND,
        PYTHONDONTWRITEBYTECODE: "1",
        APP_ENV,
      },
      max_memory_restart: "1G",
      kill_timeout: 30000,
      autorestart: true,
      time: true,
    },
    {
      name: "rl-quote-frontend",
      cwd: FRONTEND,
      script: "node_modules/next/dist/bin/next",
      args: "start --hostname 127.0.0.1 --port 3000",
      interpreter: "none",
      env: {
        NODE_ENV: "production",
        PORT: "3000",
        // Used by the Next.js /api proxy route when nginx routes /api to the
        // frontend instead of directly to the backend.
        BACKEND_API_ORIGIN: "http://127.0.0.1:8100",
      },
      max_memory_restart: "600M",
      kill_timeout: 15000,
      autorestart: true,
      time: true,
    },
  ],
};