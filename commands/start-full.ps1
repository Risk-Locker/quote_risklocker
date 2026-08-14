$ErrorActionPreference = "Stop"

$root = Resolve-Path (Join-Path $PSScriptRoot "..")
$backendScript = Join-Path $root "commands\start-backend.ps1"
$frontendScript = Join-Path $root "commands\start-frontend.ps1"
$workerScript = Join-Path $root "commands\start-worker.ps1"

Start-Process powershell.exe -ArgumentList @(
    "-NoExit",
    "-NoProfile",
    "-ExecutionPolicy",
    "Bypass",
    "-File",
    "`"$backendScript`""
) -WindowStyle Hidden

$backendPortFile = Join-Path $root ".qc-tmp\backend-port.txt"
foreach ($attempt in 1..30) {
    if (Test-Path $backendPortFile) {
        $backendPort = (Get-Content $backendPortFile -Raw).Trim()
        try {
            $health = Invoke-RestMethod -Uri "http://127.0.0.1:$backendPort/health" -TimeoutSec 2
            if ($health.status -eq "Ready" -and [string]$health.app -match "Risklocker") {
                break
            }
        } catch {
            Start-Sleep -Seconds 1
        }
    } else {
        Start-Sleep -Seconds 1
    }
}

Start-Process powershell.exe -ArgumentList @(
    "-NoExit",
    "-NoProfile",
    "-ExecutionPolicy",
    "Bypass",
    "-File",
    "`"$workerScript`""
) -WindowStyle Hidden

Start-Process powershell.exe -ArgumentList @(
    "-NoExit",
    "-NoProfile",
    "-ExecutionPolicy",
    "Bypass",
    "-File",
    "`"$frontendScript`""
) -WindowStyle Hidden

Write-Host "Started Risklocker backend, worker, and frontend as background processes."
Write-Host "Backend:  auto-selected from http://127.0.0.1:8100 through http://127.0.0.1:8110"
Write-Host "Frontend: http://127.0.0.1:3000/login"
Write-Host "To stop cleanly: run npm run stop from the project root."
