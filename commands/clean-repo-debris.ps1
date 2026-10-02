<#
.SYNOPSIS
    clean-repo-debris.ps1 - Repository Janitor & Debris Cleaner for Risklocker.
.DESCRIPTION
    1. Cleans stale debug logs, traces, and screenshots from /.qc-tmp/ (preserving backend-port.txt).
    2. Scans frontend/src/components/ for orphaned .tsx files that have 0 references across the frontend.
    3. Cleans stale Python bytecode cache files (__pycache__).
#>

param(
    [switch]$PruneOrphans = $false,
    [switch]$DryRun = $false
)

$ErrorActionPreference = "Continue"
$RepoRoot = Split-Path -Parent $PSScriptRoot

Write-Host ""
Write-Host "======================================================" -ForegroundColor Cyan
Write-Host "[JANITOR] Running Repository Debris & Hygiene Sweep" -ForegroundColor Cyan
Write-Host "======================================================" -ForegroundColor Cyan
Write-Host ""

# 1. Clean /.qc-tmp/ debris
$QcTmp = Join-Path $RepoRoot ".qc-tmp"
if (Test-Path $QcTmp) {
    Write-Host "[1/3] Cleaning /.qc-tmp/ debris..." -ForegroundColor Yellow
    $ItemsToRemove = Get-ChildItem -Path $QcTmp -Recurse -File | Where-Object {
        $_.Name -ne "backend-port.txt" -and $_.Name -ne ".gitignore"
    }

    $Count = 0
    foreach ($Item in $ItemsToRemove) {
        if (-not $DryRun) {
            Remove-Item -Path $Item.FullName -Force -ErrorAction SilentlyContinue
        }
        $Count++
    }
    Write-Host "   OK: Removed $Count temporary run logs, traces, and screenshots from /.qc-tmp/." -ForegroundColor Green
} else {
    Write-Host "[1/3] /.qc-tmp/ is already clean." -ForegroundColor Green
}

# 2. Clean Python __pycache__
Write-Host "[2/3] Cleaning __pycache__ directories..." -ForegroundColor Yellow
$PyCaches = Get-ChildItem -Path $RepoRoot -Recurse -Directory -Filter "__pycache__" | Where-Object {
    $_.FullName -notmatch "\\.venv\\" -and $_.FullName -notmatch "\\node_modules\\"
}
$PyCount = 0
foreach ($Cache in $PyCaches) {
    if (-not $DryRun) {
        Remove-Item -Path $Cache.FullName -Recurse -Force -ErrorAction SilentlyContinue
    }
    $PyCount++
}
Write-Host "   OK: Removed $PyCount stale __pycache__ directories." -ForegroundColor Green

# 3. Detect Orphaned Component Files (.tsx in frontend/src/components/)
Write-Host "[3/3] Scanning for orphaned/unreferenced frontend components..." -ForegroundColor Yellow
$ComponentsDir = Join-Path $RepoRoot "frontend\src\components"
$FrontendSrc = Join-Path $RepoRoot "frontend\src"

$AllComponents = Get-ChildItem -Path $ComponentsDir -Recurse -File -Filter "*.tsx"
$AllSrcFiles = Get-ChildItem -Path $FrontendSrc -Recurse -File | Where-Object {
    $_.Extension -match "\.(tsx|ts|jsx|js)$"
}

$Orphans = @()

foreach ($Comp in $AllComponents) {
    $BaseName = [System.IO.Path]::GetFileNameWithoutExtension($Comp.Name)
    
    # Check if the component name is mentioned anywhere outside itself
    $MatchCount = 0
    foreach ($File in $AllSrcFiles) {
        if ($File.FullName -eq $Comp.FullName) { continue }
        
        try {
            $Content = [System.IO.File]::ReadAllText($File.FullName)
            if ($Content -and $Content.Contains($BaseName)) {
                $MatchCount++
                break
            }
        } catch {}
    }

    if ($MatchCount -eq 0) {
        $Orphans += $Comp
    }
}

if ($Orphans.Count -gt 0) {
    Write-Host ""
    Write-Host "[WARN] Found $($Orphans.Count) potentially orphaned components (0 imports found):" -ForegroundColor Magenta
    foreach ($Orphan in $Orphans) {
        $RelPath = $Orphan.FullName.Substring($RepoRoot.Length).TrimStart('\', '/')
        Write-Host "   - $RelPath" -ForegroundColor DarkYellow
    }

    if ($PruneOrphans -and -not $DryRun) {
        Write-Host ""
        Write-Host "   [--PruneOrphans active] Pruning unreferenced components..." -ForegroundColor Red
        foreach ($Orphan in $Orphans) {
            Remove-Item -Path $Orphan.FullName -Force
            Write-Host "   DELETED: $($Orphan.Name)" -ForegroundColor Red
        }
    } else {
        Write-Host "   (Run with -PruneOrphans to automatically delete unreferenced components)" -ForegroundColor DarkGray
    }
} else {
    Write-Host "   [OK] Zero orphaned components found. All components are actively referenced!" -ForegroundColor Green
}

Write-Host ""
Write-Host "======================================================" -ForegroundColor Cyan
Write-Host "[JANITOR] Repository hygiene sweep complete." -ForegroundColor Cyan
Write-Host "======================================================" -ForegroundColor Cyan
Write-Host ""
