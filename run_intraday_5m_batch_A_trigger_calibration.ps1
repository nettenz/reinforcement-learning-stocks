#!/usr/bin/env pwsh

$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

$pythonExe = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $pythonExe)) {
    throw "Python executable not found at $pythonExe"
}

. (Join-Path $PSScriptRoot ".venv\Scripts\Activate.ps1")

Write-Host "Batch A: Intraday 5m Trigger Calibration" -ForegroundColor Green
Write-Host "Goal: Sweep threshold x horizon under fixed triggered realism settings." -ForegroundColor Yellow

$ticker = "nvda"
$seeds = "7,13,21,42,84,101,123,256,512,777"
$device = "cuda"

$thresholds = @("0.001", "0.0015", "0.002")
$horizons = @("3", "5")

foreach ($threshold in $thresholds) {
    foreach ($horizon in $horizons) {
        $runLabel = "nvda-intraday-5m-A-thr$($threshold.Replace('.', 'p'))-h$horizon-20k"

        $args = @(
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
            "--trade-penalty", "0.08",
            "--execution-mode", "next_bar",
            "--spread-bps", "1.0",
            "--slippage-bps", "1.0",
            "--max-weight-delta-per-step", "0.15",

            "--reward-mode", "sortino",
            "--reward-direction-scale", "0.30",
            "--reward-hold-penalty-scale", "0.12",
            "--reward-drawdown-penalty-scale", "0.12",
            "--reward-action-bonus-scale", "0.00",
            "--reward-turnover-penalty-scale", "0.10",
            "--no-reward-ignore-transaction-cost",

            "--leaderboard-path", "data\experiment_leaderboard_intraday_5m_batch_a.csv",
            "--reward-leaderboard-path", "data\experiment_reward_leaderboard_intraday_5m_batch_a.csv",
            "--summary-path", "data\experiment_summary_intraday_5m_batch_a.json",
            "--snapshot-dir", "data\experiment_snapshots\intraday_5m_batch_a"
        )

        Write-Host "Running $runLabel" -ForegroundColor Cyan
        & $pythonExe @args
        if ($LASTEXITCODE -ne 0) {
            throw "Batch A run failed: $runLabel"
        }
    }
}

Write-Host "Batch A complete." -ForegroundColor Green
