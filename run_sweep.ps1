$ErrorActionPreference = "Stop"

Set-Location -Path $PSScriptRoot

$pythonExe = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $pythonExe)) {
    throw "Python executable not found at $pythonExe"
}

$tickers = @("aapl", "nvda", "amd")
$rewardModes = @("sharpe", "sortino")

# Medium-long sweep profile:
# - More seeds for stability
# - 10k/20k timesteps for longer training horizon
# - Moderate exploration + anti-collapse variants
$seeds = "7,13,21,34,55"
$timesteps = "10000,20000"
$learningRates = "0.0003"
$gammas = "0.99"
$entCoefs = "0.02,0.05"
$actionBonuses = "0.02,0.08"
$tradePenalty = "0.05"
$executionMode = "next_bar"
$turnoverPenaltyScales = "0.01,0.03"

Write-Host "Starting medium-long next_bar validation sweep (AAPL/NVDA/AMD)..." -ForegroundColor Cyan

foreach ($ticker in $tickers) {
    foreach ($mode in $rewardModes) {
        $runLabel = "$ticker-medium-long-$mode-nextbar"

        $args = @(
            "src/experiments.py",
            "--ticker", $ticker,
            "--include-news",
            "--use-stationary-features",
            "--seeds", $seeds,
            "--timesteps", $timesteps,
            "--learning-rates", $learningRates,
            "--gammas", $gammas,
            "--ent-coefs", $entCoefs,
            "--threshold", "0.002",
            "--horizon", "1",
            "--transaction-cost-rate", "0.001",
            "--trade-penalty", $tradePenalty,
            "--execution-mode", $executionMode,
            "--reward-action-bonus-scale", $actionBonuses,
            "--reward-turnover-penalty-scale", $turnoverPenaltyScales,
            "--reward-mode", $mode,
            "--max-runs", "24",
            "--append",
            "--run-label", $runLabel,
            "--compact-output"
        )

        Write-Host "Running: $pythonExe $($args -join ' ')" -ForegroundColor Yellow
        & $pythonExe @args

        if ($LASTEXITCODE -ne 0) {
            throw "Sweep failed for ticker=$ticker mode=$mode"
        }
    }
}

Write-Host "Medium-long sweep complete. Review leaderboard and dashboard for results." -ForegroundColor Green
