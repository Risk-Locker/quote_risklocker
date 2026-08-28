$ErrorActionPreference = "Stop"

$root = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $root

$tmpDir = Join-Path $root ".qc-tmp"
New-Item -ItemType Directory -Force -Path $tmpDir | Out-Null
$workerLog = Join-Path $tmpDir "worker.log"

$env:PYTHONPATH = "backend"
$env:PYTHONDONTWRITEBYTECODE = "1"
$env:PYTHONUNBUFFERED = "1"
Write-Host "Starting one bounded Risklocker extraction/render worker ..."
& ".\.venv\Scripts\python.exe" -u "commands/run-worker.py" 2>&1 | Tee-Object -FilePath $workerLog -Append
