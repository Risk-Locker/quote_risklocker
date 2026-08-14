$ErrorActionPreference = "Stop"

$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$escapedRoot = [regex]::Escape($root)
$frontendRoot = Join-Path $root "frontend"
$escapedFrontendRoot = [regex]::Escape($frontendRoot)
$stoppedProcessIds = New-Object System.Collections.Generic.HashSet[int]

function Stop-ProcessTree {
    param([int]$TargetProcessId)

    $output = & cmd.exe /c "taskkill /PID $TargetProcessId /T /F 2>&1"
    return @{
        Success = ($LASTEXITCODE -eq 0)
        Output = (($output | Out-String).Trim())
    }
}

$processes = Get-CimInstance Win32_Process |
    Where-Object {
        $_.CommandLine -match $escapedRoot -and
        (
            $_.CommandLine -match "uvicorn" -or
            $_.CommandLine -match "run-worker.py" -or
            $_.CommandLine -match "next dev" -or
            $_.CommandLine -match "next start" -or
            ($_.Name -eq "node.exe" -and $_.CommandLine -match $escapedFrontendRoot -and $_.CommandLine -match "next")
        )
    }

foreach ($process in $processes) {
    [void]$stoppedProcessIds.Add([int]$process.ProcessId)
    $running = Get-Process -Id $process.ProcessId -ErrorAction SilentlyContinue
    if ($running) {
        $result = Stop-ProcessTree -TargetProcessId $process.ProcessId
        if ($result.Success) {
            Write-Host "Stopped process tree $($process.ProcessId)."
        } else {
            Write-Host "Could not stop process tree $($process.ProcessId): $($result.Output)" -ForegroundColor Yellow
        }
    } else {
        Write-Host "Process $($process.ProcessId) was already stopped."
    }
}

$appPorts = @(3000..3005) + @(8100..8110)
$listeners = Get-NetTCPConnection -LocalAddress 127.0.0.1 -State Listen -ErrorAction SilentlyContinue |
    Where-Object { $appPorts -contains $_.LocalPort } |
    Sort-Object LocalPort, OwningProcess -Unique

foreach ($listener in $listeners) {
    $processId = [int]$listener.OwningProcess
    if ($processId -le 0 -or $stoppedProcessIds.Contains($processId)) {
        continue
    }
    $process = Get-CimInstance Win32_Process -Filter "ProcessId = $processId" -ErrorAction SilentlyContinue
    $name = if ($process) { $process.Name } else { "unknown" }
    $commandLine = if ($process) { [string]$process.CommandLine } else { "" }
    $looksLikeDevServer =
        $name -in @("python.exe", "node.exe", "powershell.exe", "cmd.exe") -or
        $commandLine -match "uvicorn" -or
        $commandLine -match "next"

    if ($looksLikeDevServer -or -not $process) {
        $result = Stop-ProcessTree -TargetProcessId $processId
        if ($result.Success) {
            Write-Host "Stopped leftover listener on port $($listener.LocalPort) process $processId."
        } else {
            Write-Host "Port $($listener.LocalPort) still reports stale process $processId, but Windows cannot find that process." -ForegroundColor Yellow
        }
        [void]$stoppedProcessIds.Add($processId)
    }
}

if ($stoppedProcessIds.Count -eq 0) {
    Write-Host "No Risklocker backend/worker/frontend processes found for this project."
}
