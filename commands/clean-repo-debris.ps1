<#
.SYNOPSIS
    clean-repo-debris.ps1 - Repository Janitor & Debris Cleaner for Risklocker.
.DESCRIPTION
    1. Cleans stale debug logs, traces, screenshots, and empty dirs from /.qc-tmp/ and /backend/.qc-tmp/
       (preserving graphify-out/, research-browser-profile/, backend-port.txt, and .gitignore).
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

# 1. Clean /.qc-tmp/ and /backend/.qc-tmp/ debris (preserving graphify-out/, research-browser-profile/, backend-port.txt, .gitignore)
$QcTmp = Join-Path $RepoRoot ".qc-tmp"
$BackendQcTmp = Join-Path $RepoRoot "backend\.qc-tmp"
$ProtectedSubtrees = @(
    (Join-Path $QcTmp "graphify-out"),
    (Join-Path $QcTmp "research-browser-profile")
)

function Test-ProtectedPath([string]$FullPath, [string]$Name) {
    if ($Name -eq "backend-port.txt" -or $Name -eq ".gitignore") { return $true }
    foreach ($pDir in $ProtectedSubtrees) {
        if ($FullPath.Equals($pDir, [System.StringComparison]::OrdinalIgnoreCase) -or
            $FullPath.StartsWith($pDir + [System.IO.Path]::DirectorySeparatorChar, [System.StringComparison]::OrdinalIgnoreCase)) {
            return $true
        }
    }
    return $false
}

$FileCount = 0
$DirCount = 0
foreach ($TargetRoot in @($QcTmp, $BackendQcTmp)) {
    if (-not (Test-Path $TargetRoot)) { continue }
    $ItemsToRemove = Get-ChildItem -Path $TargetRoot -Recurse -File -Force -ErrorAction SilentlyContinue | Where-Object {
        -not (Test-ProtectedPath $_.FullName $_.Name)
    }
    foreach ($Item in $ItemsToRemove) {
        if (-not $DryRun) {
            Remove-Item -LiteralPath $Item.FullName -Force -ErrorAction SilentlyContinue
        }
        $FileCount++
    }
    $DirsBottomUp = Get-ChildItem -Path $TargetRoot -Recurse -Directory -Force -ErrorAction SilentlyContinue |
        Sort-Object { $_.FullName.Length } -Descending
    foreach ($Dir in $DirsBottomUp) {
        if (Test-ProtectedPath $Dir.FullName $Dir.Name) { continue }
        $Remaining = Get-ChildItem -LiteralPath $Dir.FullName -Force -ErrorAction SilentlyContinue
        if ($null -eq $Remaining -or $Remaining.Count -eq 0) {
            if (-not $DryRun) {
                Remove-Item -LiteralPath $Dir.FullName -Force -ErrorAction SilentlyContinue
            }
            $DirCount++
        }
    }
}

$Verb1 = if ($DryRun) { "[DRY-RUN] Would remove" } else { "OK: Removed" }
Write-Host "[1/3] Cleaning /.qc-tmp/ and /backend/.qc-tmp/ debris..." -ForegroundColor Yellow
Write-Host "   $Verb1 $FileCount temporary files and $DirCount empty directories." -ForegroundColor Green

# 2. Clean Python __pycache__
Write-Host "[2/3] Cleaning __pycache__ directories..." -ForegroundColor Yellow
$PyCaches = Get-ChildItem -Path $RepoRoot -Recurse -Directory -Filter "__pycache__" -ErrorAction SilentlyContinue | Where-Object {
    $_.FullName -notmatch "\\.venv\\" -and $_.FullName -notmatch "\\node_modules\\"
}
$PyCount = 0
foreach ($Cache in $PyCaches) {
    if (-not $DryRun) {
        Remove-Item -Path $Cache.FullName -Recurse -Force -ErrorAction SilentlyContinue
    }
    $PyCount++
}
$Verb2 = if ($DryRun) { "[DRY-RUN] Would remove" } else { "OK: Removed" }
Write-Host "   $Verb2 $PyCount stale __pycache__ directories." -ForegroundColor Green

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
