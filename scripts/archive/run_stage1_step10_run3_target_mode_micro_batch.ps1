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

    Write-Host "Running Step 10 proxy micro-batch via Step 9 runner"

    & python.exe scripts/run_stage1_step9_split_sensitivity_and_specialization.py `
        --reg-model-types linear,rf `
        --tickers AAPL,NVDA,AMD `
        --ticker-target-modes "AAPL:raw|vol_norm|vol_norm_clipped,NVDA:raw|vol_norm|vol_norm_clipped,AMD:raw|vol_norm|vol_norm_clipped" `
        --ticker-horizons "AAPL:1|2,NVDA:1|2,AMD:2|3|4" `
        --split-settings 0.70:0.15 `
        --base-thresholds AAPL:0.0030,NVDA:0.0010,AMD:0.0010 `
        --threshold-deltas=-0.0005,0.0000,0.0005 `
        --confirmation-seeds 7,13,21,27,123 `
        --results-dir results/stage1_step10_proxy `
        --confirm-results-dir results/stage1_step10_proxy_confirm `
        --logs-dir logs

    if ($LASTEXITCODE -ne 0) {
        throw "run_stage1_step9_split_sensitivity_and_specialization.py failed"
    }

    Write-Host "Run 3 complete. Outputs written to results/stage1_step10_proxy*, logs/"
}
finally {
    Pop-Location
}
