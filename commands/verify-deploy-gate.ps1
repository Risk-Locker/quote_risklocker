# Pre-deployment verification script mirroring .github/workflows/deploy.yml 1:1
# All AI agents and maintainers MUST run this before any git commit or push.
$ErrorActionPreference = "Stop"

Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "Running 1:1 CI Pre-Deployment Verification Gate..." -ForegroundColor Cyan
Write-Host "========================================================" -ForegroundColor Cyan

# Step 1: Backend tests in isolated CI environment
Write-Host "`n[1/6] Running Backend Pytest under CI Environment..." -ForegroundColor Yellow
$origAppEnv = $env:APP_ENV
$origDbUrl = $env:DATABASE_URL
$origAuthSec = $env:AUTH_HASH_SECRET

$env:APP_ENV = "production"
$env:DATABASE_URL = "postgresql://postgres:ci@db.ci.supabase.co:5432/postgres?sslmode=require"
$env:AUTH_HASH_SECRET = "ci_test_secret_at_least_32_characters_long"

try {
    & .\.venv\Scripts\python.exe -m pytest -q
    if ($LASTEXITCODE -ne 0) { throw "Backend pytest failed!" }
    Write-Host "[PASS] Backend tests passed (100% hermetic CI parity)." -ForegroundColor Green
} finally {
    $env:APP_ENV = $origAppEnv
    $env:DATABASE_URL = $origDbUrl
    $env:AUTH_HASH_SECRET = $origAuthSec
}

# Step 2: Frontend type check
Write-Host "`n[2/6] Running Frontend Type-Check (tsc --noEmit)..." -ForegroundColor Yellow
Push-Location frontend
try {
    & npx tsc --noEmit
    if ($LASTEXITCODE -ne 0) { throw "Frontend TypeScript check failed!" }
    Write-Host "[PASS] Frontend type check clean (0 errors)." -ForegroundColor Green
} finally {
    Pop-Location
}

# Step 3: Frontend production build
Write-Host "`n[3/6] Running Frontend Production Build (npm run build)..." -ForegroundColor Yellow
Push-Location frontend
try {
    & npm run build
    if ($LASTEXITCODE -ne 0) { throw "Frontend build failed!" }
    Write-Host "[PASS] Frontend build compiled cleanly." -ForegroundColor Green
} finally {
    Pop-Location
}

# Step 4: Database schema verification
Write-Host "`n[4/6] Verifying Database Schema Version..." -ForegroundColor Yellow
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$backend = Join-Path $root "backend"
$origPythonPath = $env:PYTHONPATH
$env:PYTHONPATH = $backend
try {
    & .\.venv\Scripts\python.exe -c "import sys; from pathlib import Path; sys.path.insert(0, str(Path(r'$backend'))); from app.db.session import verify_schema_version; verify_schema_version(); print('schema OK')"
    if ($LASTEXITCODE -ne 0) { throw "Schema version check failed!" }
    Write-Host "[PASS] Database schema matches application version." -ForegroundColor Green
} finally {
    $env:PYTHONPATH = $origPythonPath
}

# Step 5: Codebase map check
Write-Host "`n[5/6] Checking Codebase Map Freshness..." -ForegroundColor Yellow
& .\.venv\Scripts\python.exe commands/update-code-map.py --check
if ($LASTEXITCODE -ne 0) { throw "Codebase map is stale! Run: python commands/update-code-map.py --write" }
Write-Host "[PASS] Codebase map is current." -ForegroundColor Green

# Step 6: Agent brain documentation integrity
Write-Host "`n[6/6] Verifying Agent Brain & Documentation Integrity..." -ForegroundColor Yellow
& .\.venv\Scripts\python.exe commands/verify-brain.py
if ($LASTEXITCODE -ne 0) { throw "Brain verification failed!" }
Write-Host "[PASS] Brain documentation integrity verified." -ForegroundColor Green

Write-Host "`n========================================================" -ForegroundColor Green
Write-Host "[SUCCESS] All 6 Pre-Deployment Verification Checks Passed!" -ForegroundColor Green
Write-Host "Safe to commit, push, and deploy to VPS." -ForegroundColor Green
Write-Host "========================================================" -ForegroundColor Green
