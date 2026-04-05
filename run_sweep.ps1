$ErrorActionPreference = "Stop"

Set-Location -Path $PSScriptRoot

# Activate virtual environment
& "$PSScriptRoot\.venv\Scripts\Activate.ps1"

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

# ============================================================================
# AMD UNLOCK EXPERIMENTS (Exp 2a/2b/2c - Sequential)
# Current: 0.5226 accuracy vs 0.5300 gate (0.18% short = ~2 samples)
# Strategy: Run sequentially, stop on first success
# ============================================================================

Write-Host "`nAMD UNLOCK SEQUENCE (Sequential - Stop on Success)" -ForegroundColor Magenta
Write-Host "Current AMD Test Accuracy: 0.5226 (0.18% short of 0.5300 gate)" -ForegroundColor Yellow

# Fix 1a: Lower Action Bonus (0.01) - Reduce trading noise
Write-Host "`n[1a] Running AMD Fix: Lower Action Bonus (0.01)..." -ForegroundColor Cyan
$args = @(
    "src/experiments.py",
    "--ticker", "amd",
    "--seeds", "7,21,13",
    "--timesteps", "20000",
    "--reward-mode", "sharpe",
    "--reward-action-bonus-scale", "0.01",
    "--append",
    "--run-label", "amd-sharpe-bonus-001"
)
Write-Host "Command: $pythonExe $($args -join ' ')" -ForegroundColor Yellow
& $pythonExe @args
if ($LASTEXITCODE -eq 0) {
    Write-Host "Fix 1a potential success! Check leaderboard for accuracy >= 0.5300" -ForegroundColor Green
    Write-Host "If successful, promote AMD with: Copy-Item data\experiment_snapshots\model_*amd-sharpe-bonus-001*.zip -Destination models\sac_trading_bot_amd.zip -Force" -ForegroundColor Green
} else {
    Write-Host "Fix 1a did not reach threshold, trying Fix 1b..." -ForegroundColor Yellow
}

# Fix 1b: Higher Entropy (0.10) - More exploration, better decision boundary
Write-Host "`n[1b] Running AMD Fix: Higher Entropy (0.10)..." -ForegroundColor Cyan
$args = @(
    "src/experiments.py",
    "--ticker", "amd",
    "--seeds", "7",
    "--timesteps", "20000",
    "--reward-mode", "sharpe",
    "--ent-coefs", "0.10",
    "--append",
    "--run-label", "amd-sharpe-entropy-010"
)
Write-Host "Command: $pythonExe $($args -join ' ')" -ForegroundColor Yellow
& $pythonExe @args
if ($LASTEXITCODE -eq 0) {
    Write-Host "Fix 1b potential success! Check leaderboard for accuracy >= 0.5300" -ForegroundColor Green
    Write-Host "If successful, promote AMD with: Copy-Item data\experiment_snapshots\model_*amd-sharpe-entropy-010*.zip -Destination models\sac_trading_bot_amd.zip -Force" -ForegroundColor Green
} else {
    Write-Host "Fix 1b did not reach threshold, trying Fix 1c..." -ForegroundColor Yellow
}

# Fix 1c: Longer Rolling Window (200 bars) - More stable Sharpe in early episodes
Write-Host "`n[1c] Running AMD Fix: Longer Rolling Window (200)..." -ForegroundColor Cyan
$args = @(
    "src/experiments.py",
    "--ticker", "amd",
    "--seeds", "7",
    "--timesteps", "20000",
    "--reward-mode", "sharpe",
    "--rolling-reward-window", "200",
    "--append",
    "--run-label", "amd-sharpe-window-200"
)
Write-Host "Command: $pythonExe $($args -join ' ')" -ForegroundColor Yellow
& $pythonExe @args
if ($LASTEXITCODE -eq 0) {
    Write-Host "Fix 1c potential success! Check leaderboard for accuracy >= 0.5300" -ForegroundColor Green
    Write-Host "If successful, promote AMD with: Copy-Item data\experiment_snapshots\model_*amd-sharpe-window-200*.zip -Destination models\sac_trading_bot_amd.zip -Force" -ForegroundColor Green
}
else {
    Write-Host "All AMD fixes attempted. If none succeeded, NVDA-only deployment is conservative option." -ForegroundColor Yellow
}

Write-Host "`nAMD UNLOCK SEQUENCE COMPLETE" -ForegroundColor Magenta
