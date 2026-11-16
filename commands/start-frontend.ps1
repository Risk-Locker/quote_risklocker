$ErrorActionPreference = "Stop"

$root = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location (Join-Path $root "frontend")

$backendPortFile = Join-Path $root ".qc-tmp\backend-port.txt"

function Add-PortCandidate {
    param(
        [System.Collections.Generic.List[int]]$Candidates,
        [object]$Value
    )

    if (-not $Value) {
        return
    }

    $text = ([string]$Value).Trim()
    $parsed = 0
    if ([int]::TryParse($text, [ref]$parsed) -and -not $Candidates.Contains($parsed)) {
        $Candidates.Add($parsed) | Out-Null
    }
}

function Get-BackendPortCandidates {
    $candidates = New-Object System.Collections.Generic.List[int]

    # The backend script writes the actual selected port here. Prefer it over
    # shell environment variables because VS Code terminals can keep stale env.
    if (Test-Path $backendPortFile) {
        Add-PortCandidate -Candidates $candidates -Value (Get-Content $backendPortFile -Raw)
    }
    Add-PortCandidate -Candidates $candidates -Value $env:BACKEND_PORT
    foreach ($candidate in 8100..8110) {
        Add-PortCandidate -Candidates $candidates -Value $candidate
    }

    return $candidates
}

function Test-BackendHealth {
    param([int]$Port)

    $listener = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue |
        Where-Object { $_.LocalAddress -in @("127.0.0.1", "0.0.0.0", "::", "::1") } |
        Select-Object -First 1
    if (-not $listener) {
        return $false
    }

    try {
        $response = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/api/health" -TimeoutSec 2
        return ($response.status -eq "Ready" -and [string]$response.app -match "Risklocker")
    } catch {
        return $false
    }
}

$backendPort = $null
foreach ($attempt in 1..20) {
    foreach ($candidate in Get-BackendPortCandidates) {
        if (Test-BackendHealth -Port $candidate) {
            $backendPort = $candidate
            break
        }
    }
    if ($backendPort) {
        break
    }
    Start-Sleep -Seconds 1
}

if (-not $backendPort) {
    Write-Host "Frontend cannot find a running Risklocker backend on http://127.0.0.1:8100 through http://127.0.0.1:8110." -ForegroundColor Red
    Write-Host "Start the backend first with: npm run backend" -ForegroundColor Yellow
    Write-Host "If old ports look stuck, close old backend terminals or run: npm run stop" -ForegroundColor Yellow
    exit 1
}

Set-Content -Path $backendPortFile -Value $backendPort -Encoding ASCII
$env:BACKEND_API_ORIGIN = "http://127.0.0.1:$backendPort"

$candidatePorts = if ($env:FRONTEND_PORT) { @([int]$env:FRONTEND_PORT) } else { 3000..3010 }
$port = $null
foreach ($candidatePort in $candidatePorts) {
    $listener = Get-NetTCPConnection -LocalPort $candidatePort -State Listen -ErrorAction SilentlyContinue |
        Where-Object { $_.LocalAddress -in @("127.0.0.1", "0.0.0.0", "::", "::1") } |
        Select-Object -First 1
    if (-not $listener) {
        $port = $candidatePort
        break
    }
}

if (-not $port) {
    Write-Host "Frontend cannot start because ports $($candidatePorts -join ', ') are already in use." -ForegroundColor Red
    Write-Host "Close the old frontend terminal, press Ctrl+C there, or run from project root: npm run stop" -ForegroundColor Yellow
    exit 1
}

Write-Host "Starting Risklocker frontend in lightweight dev mode on http://127.0.0.1:$port ..." -ForegroundColor Cyan
Set-Location (Join-Path $root "frontend")
npm.cmd run dev -- -p $port -H 127.0.0.1
