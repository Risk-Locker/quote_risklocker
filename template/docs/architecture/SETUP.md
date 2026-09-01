# Setup & Deployment Runbook

## 1. Local Development Setup

### Prerequisites
- Language Runtime (e.g. Node.js 20+, Python 3.11+, Go, Rust)
- Database (e.g. PostgreSQL, Redis)
- Package Manager (e.g. `npm`, `pnpm`, `uv`, `pip`)

### Step-by-Step Installation
1. **Clone repository**:
   ```bash
   git clone <repo_url>
   cd <repo_dir>
   ```
2. **Configure environment**:
   ```bash
   cp .env.example .env
   # Update .env with your local credentials
   ```
3. **Install dependencies**:
   ```bash
   npm install # or pip install -r requirements.txt
   ```
4. **Run migrations & seed initial data**:
   ```bash
   npm run db:migrate
   ```
5. **Start servers**:
   ```bash
   npm run dev
   ```

## 2. Production Deployment Runbook

- **Hosting Environment**: VPS / Cloud Platform (AWS, GCP, Vercel, Railway).
- **Process Manager**: PM2 / Docker / Systemd.
- **Reverse Proxy**: Nginx / Caddy with automated Let's Encrypt SSL.
- **CI/CD Pipeline**: GitHub Actions running automated test and build gates before deployment.
