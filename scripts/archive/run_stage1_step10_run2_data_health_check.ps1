Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Resolve-Path (Join-Path $scriptDir "..")
Push-Location $repoRoot

try {
    $venvActivate = Join-Path $repoRoot ".venv\Scripts\Activate.ps1"
    if (-not (Test-Path $venvActivate)) {
        throw "Missing virtual environment activation script: $venvActivate"
    }

    . $venvActivate

    $diagStamp = Get-Date -Format "yyyyMMdd-HHmmss"
    $jobs = @(
        @{ Ticker = "AAPL"; Horizon = 1 },
        @{ Ticker = "AAPL"; Horizon = 2 },
        @{ Ticker = "NVDA"; Horizon = 1 },
        @{ Ticker = "NVDA"; Horizon = 2 },
        @{ Ticker = "AMD"; Horizon = 2 },
        @{ Ticker = "AMD"; Horizon = 3 },
        @{ Ticker = "AMD"; Horizon = 4 }
    )

    foreach ($job in $jobs) {
        $outputJson = "logs/stage1_data_health_step10_$($job.Ticker)_h$($job.Horizon)_$diagStamp.json"

        Write-Host "Inspecting data health: ticker=$($job.Ticker), horizon=$($job.Horizon)"

        & python.exe scripts/inspect_stage1_data_health.py `
            --ticker $job.Ticker `
            --horizon $job.Horizon `
            --train-ratio 0.70 `
            --val-ratio 0.15 `
            --output-json $outputJson

        if ($LASTEXITCODE -ne 0) {
            throw "inspect_stage1_data_health.py failed for $($job.Ticker) h$($job.Horizon)"
        }
    }

    Write-Host "Run 2 complete. Outputs written to logs/"
}
finally {
    Pop-Location
}
