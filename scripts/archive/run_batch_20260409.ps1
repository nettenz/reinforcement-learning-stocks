#!/usr/bin/env pwsh

$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

$pythonExe = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $pythonExe)) {
    throw "Python executable not found at $pythonExe"
}

. (Join-Path $PSScriptRoot ".venv\Scripts\Activate.ps1")

Write-Host "--- April 9, 2026 Experiment Batch ---" -ForegroundColor Green
Write-Host "Target: Stabilize Val-Test gap and improve generalization." -ForegroundColor Yellow

$ticker = "nvda"
$seeds = "7,13,21,42,84,101,123,256,512,777"
$timesteps = "20000"
$device = "cuda"
$executionMode = "next_bar"
$ddPenalty = "0.15"  # Best from April 6th runs

# --- Phase 1: Entropy Calibration Sweep ---
Write-Host "`n[Phase 1] Entropy Calibration Sweep (dd_penalty=$ddPenalty)" -ForegroundColor Cyan
$ent_coefs = @("0.05", "0.07", "0.10")
$baseTurnover = "0.05"

foreach ($ent in $ent_coefs) {
    $run_label = "nvda-phase1-entropy-$ent"
    Write-Host "  Running: $run_label (ent=$ent, turnover=$baseTurnover)" -ForegroundColor DarkCyan

    $args = @(
        "src/experiments.py",
        "--device", $device,
        "--ticker", $ticker,
        "--seeds", $seeds,
        "--timesteps", $timesteps,
        "--ent-coefs", $ent,
        "--reward-turnover-penalty-scale", $baseTurnover,
        "--reward-drawdown-penalty-scale", $ddPenalty,
        "--execution-mode", $executionMode,
        "--reward-mode", "sharpe",
        "--append",
        "--run-label", $run_label
    )

    & $pythonExe @args
}

# --- Phase 2: Turnover Normalization Sweep ---
Write-Host "`n[Phase 2] Turnover Normalization Sweep (ent_coef=0.07)" -ForegroundColor Cyan
$turnovers = @("0.05", "0.10", "0.15")
$fixedEnt = "0.07"

foreach ($turnover in $turnovers) {
    $run_label = "nvda-phase2-turnover-$turnover"
    Write-Host "  Running: $run_label (ent=$fixedEnt, turnover=$turnover)" -ForegroundColor DarkCyan

    $args = @(
        "src/experiments.py",
        "--device", $device,
        "--ticker", $ticker,
        "--seeds", $seeds,
        "--timesteps", $timesteps,
        "--ent-coefs", $fixedEnt,
        "--reward-turnover-penalty-scale", $turnover,
        "--reward-drawdown-penalty-scale", $ddPenalty,
        "--execution-mode", $executionMode,
        "--reward-mode", "sharpe",
        "--append",
        "--run-label", $run_label
    )

    & $pythonExe @args
}

# --- Phase 3: Baselines & Risk Objective Swaps ---
Write-Host "`n[Phase 3] Baselines & Risk Objective Swaps" -ForegroundColor Cyan
$bestEnt = "0.07"
$bestTurnover = "0.10"

# 3a. Stationary Feature Baseline
$run_label_stat = "nvda-phase3-stationary-baseline"
Write-Host "  Running: $run_label_stat (Stationary=True)" -ForegroundColor DarkCyan
$args_stat = @(
    "src/experiments.py",
    "--device", $device,
    "--ticker", $ticker,
    "--seeds", $seeds,
    "--timesteps", $timesteps,
    "--ent-coefs", $bestEnt,
    "--reward-turnover-penalty-scale", $bestTurnover,
    "--reward-drawdown-penalty-scale", $ddPenalty,
    "--execution-mode", $executionMode,
    "--reward-mode", "sharpe",
    "--use-stationary-features",
    "--append",
    "--run-label", $run_label_stat
)
& $pythonExe @args_stat

# 3b. Sortino Reward Mode Swap
$run_label_sort = "nvda-phase3-sortino-swap"
Write-Host "  Running: $run_label_sort (Mode=Sortino)" -ForegroundColor DarkCyan
$args_sort = @(
    "src/experiments.py",
    "--device", $device,
    "--ticker", $ticker,
    "--seeds", $seeds,
    "--timesteps", $timesteps,
    "--ent-coefs", $bestEnt,
    "--reward-turnover-penalty-scale", $bestTurnover,
    "--reward-drawdown-penalty-scale", $ddPenalty,
    "--execution-mode", $executionMode,
    "--reward-mode", "sortino",
    "--append",
    "--run-label", $run_label_sort
)
& $pythonExe @args_sort

Write-Host "`n--- Experiment Batch 20260409 Complete ---" -ForegroundColor Green
Write-Host "Please check the leaderboard and snapshots for results." -ForegroundColor Gray
