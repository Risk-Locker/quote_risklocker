$ErrorActionPreference = "Stop"

$root = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $root

$candidatePorts = if ($env:BACKEND_PORT) { @([int]$env:BACKEND_PORT) } else { 8100..8110 }
$port = $null
foreach ($candidatePort in $candidatePorts) {
    $listener = Get-NetTCPConnection -LocalAddress 127.0.0.1 -LocalPort $candidatePort -State Listen -ErrorAction SilentlyContinue
    if (-not $listener) {
        $port = $candidatePort
        break
    }
}

if (-not $port) {
    Write-Host "Backend cannot start because ports $($candidatePorts -join ', ') are already in use." -ForegroundColor Red
    Write-Host "Close old backend terminals, press Ctrl+C there, or run: npm run stop" -ForegroundColor Yellow
    exit 1
}

$tmpDir = Join-Path $root ".qc-tmp"
New-Item -ItemType Directory -Force -Path $tmpDir | Out-Null
Set-Content -Path (Join-Path $tmpDir "backend-port.txt") -Value $port -Encoding ASCII

Write-Host "Starting Risklocker backend on http://127.0.0.1:$port ..."

$env:PYTHONPATH = "backend"
$env:PYTHONDONTWRITEBYTECODE = "1"
if ($env:BACKEND_RELOAD -eq "1" -or $env:BACKEND_RELOAD -eq "true") {
    Write-Host "Backend reload mode is enabled. If a port is left open, run: npm run stop"
    & ".\.venv\Scripts\python.exe" -m uvicorn app.main:app --reload --host 127.0.0.1 --port $port
} else {
    & ".\.venv\Scripts\python.exe" -m uvicorn app.main:app --host 127.0.0.1 --port $port
}
