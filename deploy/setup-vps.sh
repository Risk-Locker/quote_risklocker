#!/usr/bin/env bash
#
# One-time VPS bootstrap for the Risklocker Quotation Converter.
#
# Prerequisites:
#   - Ubuntu 24.04 LTS (ships Python 3.12, which the pinned requirements need)
#   - DNS A record for quote.risklocker.com already pointing at this VPS
#   - The repo cloned to /var/www/html/quote_risklocker, e.g.:
#       mkdir -p /var/www/html && cd /var/www/html
#       git clone git@github.com:Risk-Locker/quote_risklocker.git
#       cd quote_risklocker
#       sudo bash deploy/setup-vps.sh
#
# Optional env overrides:
#   RL_CERTBOT_EMAIL=you@example.com   -> requests the TLS cert non-interactively
#   RL_ADMIN_EMAIL=first.last@risklocker.com -> prints the admin-creation command
#   RL_DOMAIN=quote.risklocker.com     -> domain used for nginx + certbot
#
# Idempotent: safe to re-run after fixing a failed step.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DOMAIN="${RL_DOMAIN:-quote.risklocker.com}"
CERTBOT_EMAIL="${RL_CERTBOT_EMAIL:-}"
ADMIN_EMAIL="${RL_ADMIN_EMAIL:-}"

log() { printf '\n\033[1;32m==> %s\033[0m\n' "$*"; }
warn() { printf '\n\033[1;33m!! %s\033[0m\n' "$*"; }

if [ "$(id -u)" -ne 0 ]; then
  echo "Run as root: sudo bash deploy/setup-vps.sh" >&2
  exit 1
fi

if [ ! -d "$ROOT/.git" ]; then
  echo "This script must run from inside the cloned repo (e.g. /var/www/html/quote_risklocker)." >&2
  exit 1
fi

# 1. System packages ---------------------------------------------------------
log "Installing system packages (nginx, git, python3.12-venv, certbot)..."
export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get install -y nginx git python3.12-venv python3-pip build-essential curl ca-certificates certbot python3-certbot-nginx

# 2. Node.js 22 (NodeSource) -------------------------------------------------
if ! command -v node >/dev/null 2>&1 || [ "$(node -p 'process.versions.node.split(".")[0]')" -lt 22 ]; then
  log "Installing Node.js 22 via NodeSource..."
  curl -fsSL https://deb.nodesource.com/setup_22.x | bash -
  apt-get install -y nodejs
fi

# 3. PM2 ---------------------------------------------------------------------
if ! command -v pm2 >/dev/null 2>&1; then
  log "Installing PM2..."
  npm install -g pm2
fi

# 4. .env --------------------------------------------------------------------
if [ ! -f "$ROOT/.env" ]; then
  warn "No .env found. Create it first, then re-run this script:"
  echo "  cp $ROOT/.env.example $ROOT/.env   # then edit to production values,"
  echo "  # or copy the project .env.production from a trusted machine (gitignored, not rsynced)."
  echo "  nano $ROOT/.env"
  echo "  # Required: DATABASE_URL, SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY,"
  echo "  # AUTH_HASH_SECRET, GEMINI_API_KEY, APP_ORIGIN/TRUSTED_HOSTS/CORS_ORIGINS=https://$DOMAIN,"
  echo "  # TRUSTED_PROXY_IPS=127.0.0.1 (nginx is on the same host)"
  exit 1
fi

# 5. Python venv + backend deps + Chromium -----------------------------------
log "Setting up Python 3.12 venv and backend dependencies..."
if [ ! -d "$ROOT/.venv" ]; then
  python3.12 -m venv "$ROOT/.venv"
fi
"$ROOT/.venv/bin/pip" install --upgrade pip
"$ROOT/.venv/bin/pip" install -r "$ROOT/requirements.txt"

log "Installing Playwright Chromium with system dependencies (one-time, needs root)..."
"$ROOT/.venv/bin/playwright" install --with-deps chromium

# 6. Frontend ----------------------------------------------------------------
log "Installing and building the frontend..."
cd "$ROOT/frontend"
npm ci
npm run build

# 7. Database migrations -----------------------------------------------------
log "Applying database migrations..."
cd "$ROOT"
PYTHONPATH=backend "$ROOT/.venv/bin/python" -m app.db.migrations

# 8. Nginx site --------------------------------------------------------------
log "Installing nginx site for $DOMAIN..."
cp "$ROOT/deploy/nginx-quote-risklocker.conf" /etc/nginx/sites-available/quote-risklocker
ln -sf /etc/nginx/sites-available/quote-risklocker /etc/nginx/sites-enabled/quote-risklocker
nginx -t
systemctl reload nginx

# 9. TLS via certbot ---------------------------------------------------------
if [ -n "$CERTBOT_EMAIL" ]; then
  log "Requesting Let's Encrypt certificate for $DOMAIN..."
  certbot --nginx -d "$DOMAIN" --non-interactive --agree-tos -m "$CERTBOT_EMAIL" --redirect
else
  warn "RL_CERTBOT_EMAIL not set — skipping TLS. Run manually:"
  echo "  certbot --nginx -d $DOMAIN"
fi

# 10. PM2 startup + first start ----------------------------------------------
log "Starting PM2 processes..."
cd "$ROOT"
RL_DEPLOY_PATH="$ROOT" pm2 startOrReload ecosystem.config.cjs --update-env
pm2 save
pm2 startup systemd -u root --hp /root || true

# 11. Admin account ----------------------------------------------------------
if [ -n "$ADMIN_EMAIL" ]; then
  warn "Create the admin account now (interactive password prompt):"
  echo "  cd $ROOT && PYTHONPATH=backend .venv/bin/python commands/create_admin.py $ADMIN_EMAIL"
fi

log "Done. Verify:"
echo "  pm2 status"
echo "  curl -s http://127.0.0.1:8100/health"
echo "  curl -sI https://$DOMAIN"