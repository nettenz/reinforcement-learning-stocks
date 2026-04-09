#!/usr/bin/env pwsh

$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

$pythonExe = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $pythonExe)) {
    throw "Python executable not found at $pythonExe"
}

. (Join-Path $PSScriptRoot ".venv\Scripts\Activate.ps1")

Write-Host "Entropy Coefficient A/B" -ForegroundColor Green

$ticker = "nvda"
$seeds = "7,13,21,42,84,101,123,256,512,777"
$timesteps = "20000"
$device = "cuda"
$rewardMode = "sharpe"
$executionMode = "next_bar"
$ent_coefs = @("0.05", "0.08")

Write-Host "Experiment A: 10-seed robustness check (ent 0.05 vs 0.08)" -ForegroundColor Yellow
Write-Host "Seeds: $seeds" -ForegroundColor Yellow

foreach ($ent in $ent_coefs) {
    $run_label = "nvda-entropy-ab-20k-ent{0}-bonus002-dd10-10seed" -f $ent
    Write-Host "Batch: ent_coef=$ent ($run_label)" -ForegroundColor Cyan

    $args = @(
        "src/experiments.py",
        "--device", $device,
        "--ticker", $ticker,
        "--seeds", $seeds,
        "--timesteps", $timesteps,
        "--learning-rates", "0.0003",
        "--gammas", "0.99",
        "--ent-coefs", $ent,
        "--threshold", "0.002",
        "--horizon", "1",
        "--transaction-cost-rate", "0.001",
        "--trade-penalty", "0.05",
        "--execution-mode", $executionMode,
        "--spread-bps", "0.0",
        "--slippage-bps", "0.0",
        "--reward-mode", $rewardMode,
        "--reward-return-scale", "1.0",
        "--reward-direction-scale", "0.35",
        "--reward-hold-penalty-scale", "0.1",
        "--reward-drawdown-penalty-scale", "0.10",
        "--reward-action-bonus-scale", "0.02",
        "--reward-turnover-penalty-scale", "0.05",
        "--reward-clip", "1.0",
        "--reward-ignore-transaction-cost",
        "--max-weight-delta-per-step", "0.25",
        "--append",
        "--run-label", $run_label
    )

    Write-Host "  Running: $pythonExe $($args -join ' ')" -ForegroundColor DarkGray
    & $pythonExe @args
    
    if ($LASTEXITCODE -ne 0) {
        Write-Host "  ERROR in batch $ent" -ForegroundColor Red
    } else {
        Write-Host "  OK" -ForegroundColor Green
    }
}

Write-Host ""
Write-Host "Entropy A/B batch complete!" -ForegroundColor Green
