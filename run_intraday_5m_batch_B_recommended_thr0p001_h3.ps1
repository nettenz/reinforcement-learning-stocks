#!/usr/bin/env pwsh

$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

$pythonExe = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $pythonExe)) {
    throw "Python executable not found at $pythonExe"
}

. (Join-Path $PSScriptRoot ".venv\Scripts\Activate.ps1")

Write-Host "Batch B (Recommended): Intraday 5m Penalty Rebalance" -ForegroundColor Green
Write-Host "Fixed trigger pair: threshold=0.001, horizon=3" -ForegroundColor Yellow

$ticker = "nvda"
$seeds = "7,13,21,42,84,101,123,256,512,777"
$device = "cuda"

$threshold = "0.001"
$horizon = "3"

$turnoverPenaltyScales = @("0.10", "0.15", "0.20")
$drawdownPenaltyScales = @("0.12", "0.16")
$tradePenalties = @("0.08", "0.10")

foreach ($turnover in $turnoverPenaltyScales) {
    foreach ($drawdown in $drawdownPenaltyScales) {
        foreach ($tradePenalty in $tradePenalties) {
            $runLabel = "nvda-intraday-5m-B-rec-thr0p001-h3-to$($turnover.Replace('.', 'p'))-dd$($drawdown.Replace('.', 'p'))-tp$($tradePenalty.Replace('.', 'p'))-20k"

            Write-Host "Running $runLabel" -ForegroundColor Cyan
            & $pythonExe @(
                "src/experiments.py",
                "--experiment-preset", "intraday_5m",
                "--device", $device,
                "--ticker", $ticker,
                "--seeds", $seeds,
                "--timesteps", "20000",
                "--learning-rates", "0.0003",
                "--gammas", "0.99",
                "--ent-coefs", "0.07",
                "--batch-size", "1024",
                "--n-envs", "4",
                "--append",
                "--run-label", $runLabel,
                "--threshold", $threshold,
                "--horizon", $horizon,
                "--transaction-cost-rate", "0.001",
                "--trade-penalty", $tradePenalty,
                "--execution-mode", "next_bar",
                "--spread-bps", "1.0",
                "--slippage-bps", "1.0",
                "--max-weight-delta-per-step", "0.15",
                "--reward-mode", "sortino",
                "--reward-direction-scale", "0.30",
                "--reward-hold-penalty-scale", "0.12",
                "--reward-drawdown-penalty-scale", $drawdown,
                "--reward-action-bonus-scale", "0.00",
                "--reward-turnover-penalty-scale", $turnover,
                "--no-reward-ignore-transaction-cost",
                "--leaderboard-path", "data\experiment_leaderboard_intraday_5m_batch_b_recommended.csv",
                "--reward-leaderboard-path", "data\experiment_reward_leaderboard_intraday_5m_batch_b_recommended.csv",
                "--summary-path", "data\experiment_summary_intraday_5m_batch_b_recommended.json",
                "--snapshot-dir", "data\experiment_snapshots\intraday_5m_batch_b_recommended"
            )
            if ($LASTEXITCODE -ne 0) {
                throw "Batch B recommended run failed: $runLabel"
            }
        }
    }
}

Write-Host "Batch B (Recommended) complete." -ForegroundColor Green
Write-Host "Outputs:" -ForegroundColor Green
Write-Host "  data\experiment_leaderboard_intraday_5m_batch_b_recommended.csv" -ForegroundColor DarkYellow
Write-Host "  data\experiment_reward_leaderboard_intraday_5m_batch_b_recommended.csv" -ForegroundColor DarkYellow
Write-Host "  data\experiment_summary_intraday_5m_batch_b_recommended.json" -ForegroundColor DarkYellow
Write-Host "  data\experiment_snapshots\intraday_5m_batch_b_recommended" -ForegroundColor DarkYellow
