$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

$pythonExe = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $pythonExe)) {
    throw "Python executable not found at $pythonExe"
}

. (Join-Path $PSScriptRoot ".venv\Scripts\Activate.ps1")

$Threshold = if ($env:INTRADAY_C_THRESHOLD) { $env:INTRADAY_C_THRESHOLD } else { "0.0015" }
$Horizon = if ($env:INTRADAY_C_HORIZON) { $env:INTRADAY_C_HORIZON } else { "3" }
$TradePenalty = if ($env:INTRADAY_C_TRADE_PENALTY) { $env:INTRADAY_C_TRADE_PENALTY } else { "0.08" }
$RewardDrawdownPenaltyScale = if ($env:INTRADAY_C_DRAWDOWN_PENALTY) { $env:INTRADAY_C_DRAWDOWN_PENALTY } else { "0.12" }
$RewardTurnoverPenaltyScale = if ($env:INTRADAY_C_TURNOVER_PENALTY) { $env:INTRADAY_C_TURNOVER_PENALTY } else { "0.10" }

Write-Host "Batch C: Intraday 5m Confirmatory Stability" -ForegroundColor Green
Write-Host "Goal: Compare timesteps and entropy for the best A/B candidate settings." -ForegroundColor Yellow
Write-Host "Using threshold=$Threshold horizon=$Horizon trade_penalty=$TradePenalty drawdown=$RewardDrawdownPenaltyScale turnover=$RewardTurnoverPenaltyScale" -ForegroundColor DarkYellow

$ticker = "nvda"
$seeds = "7,13,21,42,84,101,123,256,512,777"
$device = "cuda"

$timestepsGrid = @("20000", "40000")
$entCoefGrid = @("0.07", "0.05")

foreach ($timesteps in $timestepsGrid) {
    foreach ($entCoef in $entCoefGrid) {
        $runLabel = "nvda-intraday-5m-C-thr$($Threshold.Replace('.', 'p'))-h$Horizon-t$timesteps-ent$($entCoef.Replace('.', 'p'))"

        $cli = @(
            "src/experiments.py",
            "--experiment-preset", "intraday_5m",
            "--device", $device,
            "--ticker", $ticker,
            "--seeds", $seeds,
            "--timesteps", $timesteps,
            "--learning-rates", "0.0003",
            "--gammas", "0.99",
            "--ent-coefs", $entCoef,
            "--batch-size", "1024",
            "--n-envs", "4",
            "--append",
            "--run-label", $runLabel,

            "--threshold", $Threshold,
            "--horizon", $Horizon,
            "--transaction-cost-rate", "0.001",
            "--trade-penalty", $TradePenalty,
            "--execution-mode", "next_bar",
            "--spread-bps", "1.0",
            "--slippage-bps", "1.0",
            "--max-weight-delta-per-step", "0.15",

            "--reward-mode", "sortino",
            "--reward-direction-scale", "0.30",
            "--reward-hold-penalty-scale", "0.12",
            "--reward-drawdown-penalty-scale", $RewardDrawdownPenaltyScale,
            "--reward-action-bonus-scale", "0.00",
            "--reward-turnover-penalty-scale", $RewardTurnoverPenaltyScale,
            "--no-reward-ignore-transaction-cost",

            "--leaderboard-path", "data\experiment_leaderboard_intraday_5m_batch_c.csv",
            "--reward-leaderboard-path", "data\experiment_reward_leaderboard_intraday_5m_batch_c.csv",
            "--summary-path", "data\experiment_summary_intraday_5m_batch_c.json",
            "--snapshot-dir", "data\experiment_snapshots\intraday_5m_batch_c"
        )

        Write-Host "Running $runLabel" -ForegroundColor Cyan
        & $pythonExe @cli
        if ($LASTEXITCODE -ne 0) {
            throw "Batch C run failed: $runLabel"
        }
    }
}

Write-Host "Batch C complete." -ForegroundColor Green
