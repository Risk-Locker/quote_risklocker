# Local Pre-Commit & Pre-Push Verification Gate (10/10 Checks)
# Steps [1/10]–[3/10] execute the exact CI build/test stages in .github/workflows/deploy.yml.
# Steps [4/10]–[10/10] enforce local hermetic DB migration, Knowledge Base, bridge,
# skill-vault, automated SAST (--strict), and harness freshness gates (queued for Phase B CI parity).
param(
    [switch]$LiveDb,
    [switch]$RequireExternal,
    [switch]$RunE2E
)

$ErrorActionPreference = "Stop"

$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$npxCmd = if ($env:OS -eq "Windows_NT") { "npx.cmd" } else { "npx" }
$npmCmd = if ($env:OS -eq "Windows_NT") { "npm.cmd" } else { "npm" }

Push-Location $root
try {
    Write-Host "========================================================" -ForegroundColor Cyan
    Write-Host "Running 10/10 Enterprise Pre-Deployment Verification Gate..." -ForegroundColor Cyan
    Write-Host "========================================================" -ForegroundColor Cyan

    # Step 1: Backend tests in isolated CI environment (guarded by RISKLOCKER_SKIP_DOTENV=1)
    Write-Host "`n[1/10] Running Backend Pytest under CI Environment..." -ForegroundColor Yellow
    $origAppEnv = $env:APP_ENV
    $origDbUrl = $env:DATABASE_URL
    $origAuthSec = $env:AUTH_HASH_SECRET
    $origSkipDotenv = $env:RISKLOCKER_SKIP_DOTENV

    $env:APP_ENV = "production"
    $env:DATABASE_URL = "postgresql://postgres:ci@db.ci.supabase.co:5432/postgres?sslmode=require"
    $env:AUTH_HASH_SECRET = "ci_test_secret_at_least_32_characters_long"
    $env:RISKLOCKER_SKIP_DOTENV = "1"

    try {
        & .\.venv\Scripts\python.exe -m pytest -q
        if ($LASTEXITCODE -ne 0) { throw "Backend pytest failed!" }
        Write-Host "[PASS] Backend tests passed (100% hermetic CI parity)." -ForegroundColor Green
    } finally {
        $env:APP_ENV = $origAppEnv
        $env:DATABASE_URL = $origDbUrl
        $env:AUTH_HASH_SECRET = $origAuthSec
        $env:RISKLOCKER_SKIP_DOTENV = $origSkipDotenv
    }

    # Step 2: Frontend type check
    Write-Host "`n[2/10] Running Frontend Type-Check (tsc --noEmit)..." -ForegroundColor Yellow
    Push-Location frontend
    try {
        & $npxCmd tsc --noEmit
        if ($LASTEXITCODE -ne 0) { throw "Frontend TypeScript check failed!" }
        Write-Host "[PASS] Frontend type check clean (0 errors)." -ForegroundColor Green
    } finally {
        Pop-Location
    }

    # Step 3: Frontend production build
    Write-Host "`n[3/10] Running Frontend Production Build (npm run build)..." -ForegroundColor Yellow
    Push-Location frontend
    try {
        & $npmCmd run build
        if ($LASTEXITCODE -ne 0) { throw "Frontend build failed!" }
        Write-Host "[PASS] Frontend build compiled cleanly." -ForegroundColor Green
    } finally {
        Pop-Location
    }

    # Step 4: Database migration integrity (offline hermetic default; live DB check only with -LiveDb)
    Write-Host "`n[4/10] Verifying Migration Integrity (offline hermetic)..." -ForegroundColor Yellow
    $migrationScript = @'
import hashlib, re
from pathlib import Path
root = Path("migrations")
pattern = re.compile(r"^(?P<version>\d{3})_[a-z0-9][a-z0-9_-]*\.sql$")
files = sorted(root.glob("*.sql"), key=lambda p: p.name)
if not files:
    raise SystemExit("No SQL migration files found under migrations/")
seen = set()
versions = []
ledger_hasher = hashlib.sha256()
for p in files:
    m = pattern.fullmatch(p.name)
    if not m:
        raise SystemExit(f"Invalid migration filename: {p.name}")
    v = int(m.group("version"))
    if v in seen:
        raise SystemExit(f"Duplicate migration version: {v:03d}")
    seen.add(v)
    versions.append(v)
    raw = p.read_bytes()
    if not raw.strip():
        raise SystemExit(f"Empty migration SQL file: {p.name}")
    try:
        raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise SystemExit(f"Invalid UTF-8 encoding in migration {p.name}: {exc}")
    norm = re.sub(rb"\r\n|\r", b"\n", raw)
    file_hash = hashlib.sha256(norm).hexdigest()
    ledger_hasher.update(f"{p.name}:{file_hash}\n".encode("utf-8"))
if versions != list(range(1, len(files) + 1)):
    raise SystemExit(f"Migration versions must be contiguous from 001; found {versions}")
ledger_digest = ledger_hasher.hexdigest()[:16]
print(f"[PASS] Verified {len(files)} contiguous migrations (001..{len(files):03d}) & SHA-256 ledger digest ({ledger_digest}).")
'@
    $migrationScript | & .\.venv\Scripts\python.exe -
    if ($LASTEXITCODE -ne 0) { throw "Offline migration integrity check failed!" }

    if ($LiveDb) {
        Write-Host "[4b/10] Checking live database schema_migrations ledger (-LiveDb)..." -ForegroundColor Yellow
        $backend = Join-Path $root "backend"
        $origPythonPath = $env:PYTHONPATH
        $env:PYTHONPATH = $backend
        try {
            & .\.venv\Scripts\python.exe -c "from app.db.session import verify_schema_version; verify_schema_version()"
            if ($LASTEXITCODE -ne 0) { throw "Live database schema version check failed!" }
            Write-Host "[PASS] Live database schema matches application version." -ForegroundColor Green
        } finally {
            $env:PYTHONPATH = $origPythonPath
        }
    }

    # Step 5: Codebase map check
    Write-Host "`n[5/10] Checking Codebase Map Freshness..." -ForegroundColor Yellow
    & .\.venv\Scripts\python.exe commands/update-code-map.py --check
    if ($LASTEXITCODE -ne 0) { throw "Codebase map is stale! Run: python commands/update-code-map.py --write" }
    Write-Host "[PASS] Codebase map is current." -ForegroundColor Green

    # Step 6: Project Knowledge Base integrity
    Write-Host "`n[6/10] Verifying Project Knowledge Base Integrity..." -ForegroundColor Yellow
    & .\.venv\Scripts\python.exe commands/verify-brain.py
    if ($LASTEXITCODE -ne 0) { throw "Project Knowledge Base verification failed!" }
    Write-Host "[PASS] Project Knowledge Base integrity verified." -ForegroundColor Green

    # Step 7: Agent Harness IDE bridge sync
    Write-Host "`n[7/10] Checking Universal Bridges (AGENTS.md & Copilot)..." -ForegroundColor Yellow
    & .\.venv\Scripts\python.exe commands/sync-agent-bridges.py --check
    if ($LASTEXITCODE -ne 0) { throw "Universal bridge drift detected! Run: python commands/sync-agent-bridges.py --write" }
    Write-Host "[PASS] Universal bridges clean." -ForegroundColor Green

    # Step 8: Agent Skills Vault hygiene & lockfile parity
    Write-Host "`n[8/10] Auditing Repo-Local Agent Skills Vault..." -ForegroundColor Yellow
    & .\.venv\Scripts\python.exe commands/skills-manager.py doctor --check
    if ($LASTEXITCODE -ne 0) { throw "Agent Skills Vault check failed! Run: python commands/skills-manager.py doctor" }
    Write-Host "[PASS] Agent Skills Vault verified." -ForegroundColor Green

    # Step 9: Automated SAST, RBAC, Middleware, Storage, PII & Tripwire Alert Log audit
    Write-Host "`n[9/10] Running Automated SAST & RBAC Audit (security-audit.py --strict)..." -ForegroundColor Yellow
    $sastArgs = @("commands/security-audit.py", "--strict", "--with-external")
    if ($RequireExternal) { $sastArgs += "--require-external" }
    & .\.venv\Scripts\python.exe @sastArgs
    if ($LASTEXITCODE -ne 0) { throw "Security/SAST audit found CRITICAL or HIGH issues! Fix before commit/deploy." }
    $tripwireLog = Join-Path $root ".agents\logs\tripwire-alerts.log"
    if (Test-Path -LiteralPath $tripwireLog) {
        $pendingAlerts = @(Get-Content -LiteralPath $tripwireLog | Where-Object { $_.Trim() -ne "" })
        if ($pendingAlerts.Count -gt 0) {
            throw "Unresolved PostToolUse tripwire alert(s) in .agents/logs/tripwire-alerts.log ($($pendingAlerts.Count)). Fix and clear before commit."
        }
    }
    Write-Host "[PASS] Security & static audit passed (0 CRITICAL/HIGH findings; tripwire log clean)." -ForegroundColor Green

    # Step 10: Harness Freshness & Daily Radar check (--strict exits 1 on harness_signals_count > 0)
    Write-Host "`n[10/10] Checking Agent Harness Freshness (daily_radar.py --strict)..." -ForegroundColor Yellow
    & .\.venv\Scripts\python.exe .agents/hooks/daily_radar.py --offline --dry-run --strict
    if ($LASTEXITCODE -ne 0) { throw "Daily radar hygiene check detected harness drift/stale signals!" }
    Write-Host "[PASS] Daily radar check passed cleanly." -ForegroundColor Green

    Write-Host "`n========================================================" -ForegroundColor Green
    Write-Host "[SUCCESS] All 10 Pre-Deployment Verification Checks Passed!" -ForegroundColor Green
    Write-Host "Safe to commit, push, and deploy to VPS." -ForegroundColor Green
    Write-Host "========================================================" -ForegroundColor Green
} finally {
    Pop-Location
}
