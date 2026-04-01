param(
    [ValidateSet("start", "stop", "status")]
    [string]$Action = "start",
    [int]$Port = 8501
)

$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$VenvPython = Join-Path $Root ".venv\Scripts\python.exe"
$DashboardScript = Join-Path $Root "src\analytics_dashboard.py"
$PidFile = Join-Path $Root ".streamlit_dashboard.pid"

function Get-DashboardProcess {
    $matches = Get-CimInstance Win32_Process |
        Where-Object {
            $_.Name -eq "python.exe" -and
            $_.CommandLine -like "*streamlit*" -and
            $_.CommandLine -like "*analytics_dashboard.py*" -and
            $_.CommandLine -like "*$Port*"
        }
    return $matches
}

if ($Action -eq "status") {
    $proc = Get-DashboardProcess
    if ($proc) {
        Write-Host "Dashboard is running on port $Port. PID(s): $($proc.ProcessId -join ', ')"
        exit 0
    }
    Write-Host "Dashboard is not running on port $Port."
    exit 1
}

if ($Action -eq "stop") {
    $proc = Get-DashboardProcess
    if (-not $proc) {
        Write-Host "No dashboard process found on port $Port."
        if (Test-Path $PidFile) { Remove-Item $PidFile -Force }
        exit 0
    }

    foreach ($dashboardPid in ($proc.ProcessId | Select-Object -Unique)) {
        $existingProc = Get-Process -Id $dashboardPid -ErrorAction SilentlyContinue
        if (-not $existingProc) {
            Write-Host "Skipping stale dashboard PID $dashboardPid (already exited)."
            continue
        }

        Stop-Process -Id $dashboardPid
        Write-Host "Stopped dashboard process PID $dashboardPid."
    }
    if (Test-Path $PidFile) { Remove-Item $PidFile -Force }
    exit 0
}

if (-not (Test-Path $VenvPython)) {
    throw "Virtual environment Python not found at '$VenvPython'. Create .venv first."
}

if (-not (Test-Path $DashboardScript)) {
    throw "Dashboard script not found at '$DashboardScript'."
}

$existing = Get-DashboardProcess
if ($existing) {
    Write-Host "Dashboard already running on port $Port. PID(s): $($existing.ProcessId -join ', ')"
    exit 0
}

$proc = Start-Process -FilePath $VenvPython `
    -ArgumentList "-m streamlit run `"$DashboardScript`" --server.headless true --server.port $Port" `
    -WorkingDirectory $Root `
    -PassThru

Set-Content -Path $PidFile -Value $proc.Id
Write-Host "Dashboard started on http://127.0.0.1:$Port (PID $($proc.Id))."

