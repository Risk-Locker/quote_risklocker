<#
.SYNOPSIS
Register or unregister the conditional daily self-improvement radar in Windows Task Scheduler.

.EXAMPLE
.\commands\register-daily-radar.ps1 -DryRun
.\commands\register-daily-radar.ps1
.\commands\register-daily-radar.ps1 -Unregister
#>
param(
    [string]$TaskName = "RisklockerDailyAgentRadar",
    [string]$At = "09:00",
    [switch]$Unregister,
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$PythonExe = Join-Path $RepoRoot ".venv\Scripts\python.exe"
$RadarScript = Join-Path $RepoRoot ".agents\hooks\daily_radar.py"

if (-not (Test-Path $PythonExe)) {
    throw "Missing virtual environment python at $PythonExe"
}
if (-not (Test-Path $RadarScript)) {
    throw "Missing daily radar script at $RadarScript"
}

if ($Unregister) {
    if ($DryRun) {
        Write-Host "[DRY-RUN] Would unregister scheduled task '$TaskName'."
        exit 0
    }
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
    Write-Host "[OK] Unregistered scheduled task '$TaskName'."
    exit 0
}

$Arguments = "`"$RadarScript`""
if ($DryRun) {
    Write-Host "[DRY-RUN] TaskName : $TaskName"
    Write-Host "[DRY-RUN] Schedule : Daily at $At"
    Write-Host "[DRY-RUN] Action   : $PythonExe $Arguments"
    Write-Host "[DRY-RUN] WorkDir  : $RepoRoot"
    exit 0
}

$Action = New-ScheduledTaskAction -Execute $PythonExe -Argument $Arguments -WorkingDirectory $RepoRoot
$Trigger = New-ScheduledTaskTrigger -Daily -At $At
$Settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries

Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Settings $Settings -Force | Out-Null
Write-Host "[OK] Registered daily conditional radar '$TaskName' at $At (WorkDir: $RepoRoot)."

