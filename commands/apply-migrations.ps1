$ErrorActionPreference = "Stop"

$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$envFile = Join-Path $root ".env"
if (-not (Test-Path -LiteralPath $envFile)) {
    throw ".env was not found in the project root."
}

$python = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $python)) {
    throw "Project Python virtual environment was not found at .venv."
}

$backend = Join-Path $root "backend"
if ($env:PYTHONPATH) {
    $env:PYTHONPATH = "$backend;$env:PYTHONPATH"
} else {
    $env:PYTHONPATH = $backend
}
& $python -m app.db.migrations --allow-local
if ($LASTEXITCODE -ne 0) {
    throw "Migration runner failed."
}
