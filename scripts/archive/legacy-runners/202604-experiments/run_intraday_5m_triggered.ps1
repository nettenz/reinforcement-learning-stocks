#!/usr/bin/env pwsh

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location -Path $RepoRoot

$pythonExe = Join-Path $RepoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $pythonExe)) {
    throw "Python executable not found at $pythonExe"
}

. (Join-Path $RepoRoot ".venv\Scripts\Activate.ps1")

Write-Host "Intraday 5m Triggered Run Launcher" -ForegroundColor Green
Write-Host "Purpose: Evaluate 5m behavior with stronger trade triggers and execution realism." -ForegroundColor Yellow

$ticker = "nvda"
$seeds = "7,13,21,42,84,101,123,256,512,777"
$device = "cuda"

$commandArgs = @(
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
    "--run-label", "nvda-intraday-5m-triggered-20k",

    # Trade trigger and realism controls
    "--threshold", "0.0008",
    "--horizon", "2",
    "--execution-mode", "next_bar",
    "--spread-bps", "1.0",
    "--slippage-bps", "1.0",
    "--max-weight-delta-per-step", "0.15",
    "--trade-penalty", "0.08",

    # Reward shaping to discourage over-trading
    "--reward-mode", "sortino",
    "--reward-direction-scale", "0.30",
    "--reward-hold-penalty-scale", "0.12",
    "--reward-drawdown-penalty-scale", "0.12",
    "--reward-action-bonus-scale", "0.00",
    "--reward-turnover-penalty-scale", "0.10",
    "--no-reward-ignore-transaction-cost",

    "--leaderboard-path", "data\experiment_leaderboard_intraday_5m_triggered.csv",
    "--reward-leaderboard-path", "data\experiment_reward_leaderboard_intraday_5m_triggered.csv",
    "--summary-path", "data\experiment_summary_intraday_5m_triggered.json",
    "--snapshot-dir", "data\experiment_snapshots\intraday_5m_triggered"
)

Write-Host "Running intraday 5m triggered experiment for ticker $($ticker.ToUpper())" -ForegroundColor Cyan
Write-Host "Command: $pythonExe $($commandArgs -join ' ')" -ForegroundColor DarkGray

& $pythonExe @commandArgs
if ($LASTEXITCODE -ne 0) {
    throw "Intraday 5m triggered run failed."
}

Write-Host "Intraday 5m triggered run complete." -ForegroundColor Green
Write-Host "Outputs:" -ForegroundColor Green
Write-Host "  Leaderboard: data\experiment_leaderboard_intraday_5m_triggered.csv" -ForegroundColor DarkYellow
Write-Host "  Reward leaderboard: data\experiment_reward_leaderboard_intraday_5m_triggered.csv" -ForegroundColor DarkYellow
Write-Host "  Summary: data\experiment_summary_intraday_5m_triggered.json" -ForegroundColor DarkYellow
Write-Host "  Snapshots: data\experiment_snapshots\intraday_5m_triggered" -ForegroundColor DarkYellow
