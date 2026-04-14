#!/usr/bin/env pwsh

$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

$pythonExe = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $pythonExe)) {
    throw "Python executable not found at $pythonExe"
}

. (Join-Path $PSScriptRoot ".venv\Scripts\Activate.ps1")

Write-Host "Intraday 5m Run Launcher" -ForegroundColor Green
Write-Host "Purpose: Produce a dedicated 5m intraday leaderboard for dashboard comparison." -ForegroundColor Yellow

$ticker = "nvda"
$seeds = "7,13,21,42,84,101,123,256,512,777"
$device = "cuda"

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
    "--run-label", "nvda-intraday-5m-baseline-20k",
    "--leaderboard-path", "data\experiment_leaderboard_intraday_5m.csv",
    "--reward-leaderboard-path", "data\experiment_reward_leaderboard_intraday_5m.csv",
    "--summary-path", "data\experiment_summary_intraday_5m.json",
    "--snapshot-dir", "data\experiment_snapshots\intraday_5m"
)

Write-Host "Running intraday 5m baseline for ticker $($ticker.ToUpper())" -ForegroundColor Cyan
Write-Host "Command: $pythonExe $($args -join ' ')" -ForegroundColor DarkGray

& $pythonExe @args
if ($LASTEXITCODE -ne 0) {
    throw "Intraday 5m run failed."
}

Write-Host "Intraday 5m run complete." -ForegroundColor Green
Write-Host "Outputs:" -ForegroundColor Green
Write-Host "  Leaderboard: data\experiment_leaderboard_intraday_5m.csv" -ForegroundColor DarkYellow
Write-Host "  Reward leaderboard: data\experiment_reward_leaderboard_intraday_5m.csv" -ForegroundColor DarkYellow
Write-Host "  Summary: data\experiment_summary_intraday_5m.json" -ForegroundColor DarkYellow
Write-Host "  Snapshots: data\experiment_snapshots\intraday_5m" -ForegroundColor DarkYellow