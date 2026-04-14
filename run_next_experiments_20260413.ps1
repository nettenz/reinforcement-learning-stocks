#!/usr/bin/env pwsh

$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

$pythonExe = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $pythonExe)) {
    throw "Python executable not found at $pythonExe"
}

. (Join-Path $PSScriptRoot ".venv\Scripts\Activate.ps1")

Write-Host "Next Experiment Batch (2026-04-13)" -ForegroundColor Green
Write-Host "Purpose: Follow up BC-bridge with stability, alpha-lift, and timesteps checks." -ForegroundColor Yellow

$ticker = "nvda"
$seeds = "7,13,21,42,84,101,123,256,512,777"
$device = "cuda"

$common = @(
    "src/experiments.py",
    "--device", $device,
    "--ticker", $ticker,
    "--seeds", $seeds,
    "--learning-rates", "0.0003",
    "--gammas", "0.99",
    "--ent-coefs", "0.07",
    "--threshold", "0.002",
    "--horizon", "1",
    "--transaction-cost-rate", "0.001",
    "--trade-penalty", "0.05",
    "--reward-mode", "sortino",
    "--rolling-reward-window", "100",
    "--reward-epsilon", "1e-06",
    "--reward-pnl-scale", "0.0",
    "--reward-hold-penalty-scale", "0.1",
    "--reward-clip", "1.0",
    "--no-reward-ignore-transaction-cost",
    "--n-envs", "4",
    "--append"
)

function Invoke-Experiment {
    param(
        [Parameter(Mandatory = $true)] [string]$RunLabel,
        [Parameter(Mandatory = $true)] [string]$Timesteps,
        [Parameter(Mandatory = $true)] [string]$ExecutionMode,
        [Parameter(Mandatory = $true)] [double]$SpreadBps,
        [Parameter(Mandatory = $true)] [double]$SlippageBps,
        [Parameter(Mandatory = $true)] [double]$MaxWeightDelta,
        [Parameter(Mandatory = $true)] [double]$RewardReturnScale,
        [Parameter(Mandatory = $true)] [double]$RewardDirectionScale,
        [Parameter(Mandatory = $true)] [double]$RewardDrawdownPenaltyScale,
        [Parameter(Mandatory = $true)] [double]$RewardActionBonusScale,
        [Parameter(Mandatory = $true)] [double]$RewardTurnoverPenaltyScale
    )

    $args = $common + @(
        "--run-label", $RunLabel,
        "--timesteps", $Timesteps,
        "--execution-mode", $ExecutionMode,
        "--spread-bps", "$SpreadBps",
        "--slippage-bps", "$SlippageBps",
        "--max-weight-delta-per-step", "$MaxWeightDelta",
        "--reward-return-scale", "$RewardReturnScale",
        "--reward-direction-scale", "$RewardDirectionScale",
        "--reward-drawdown-penalty-scale", "$RewardDrawdownPenaltyScale",
        "--reward-action-bonus-scale", "$RewardActionBonusScale",
        "--reward-turnover-penalty-scale", "$RewardTurnoverPenaltyScale"
    )

    Write-Host "Running $RunLabel" -ForegroundColor Cyan
    & $pythonExe @args
    if ($LASTEXITCODE -ne 0) {
        throw "Experiment failed: $RunLabel"
    }

    Write-Host "Completed $RunLabel" -ForegroundColor Green
    Write-Host ""
}

# Arm 1: BC stability check (increase turnover penalty only).
Invoke-Experiment `
    -RunLabel "nvda-next2-bc-stability-nextbar-20k" `
    -Timesteps "20000" `
    -ExecutionMode "next_bar" `
    -SpreadBps 1.0 `
    -SlippageBps 1.0 `
    -MaxWeightDelta 0.25 `
    -RewardReturnScale 1.3 `
    -RewardDirectionScale 0.55 `
    -RewardDrawdownPenaltyScale 0.04 `
    -RewardActionBonusScale 0.007 `
    -RewardTurnoverPenaltyScale 0.05

# Arm 2: BC alpha-lift check (higher direction, lower action bonus).
Invoke-Experiment `
    -RunLabel "nvda-next2-bc-alphalift-nextbar-20k" `
    -Timesteps "20000" `
    -ExecutionMode "next_bar" `
    -SpreadBps 1.0 `
    -SlippageBps 1.0 `
    -MaxWeightDelta 0.25 `
    -RewardReturnScale 1.3 `
    -RewardDirectionScale 0.58 `
    -RewardDrawdownPenaltyScale 0.04 `
    -RewardActionBonusScale 0.005 `
    -RewardTurnoverPenaltyScale 0.04

# Arm 3: BC baseline at 20k for timesteps comparability.
Invoke-Experiment `
    -RunLabel "nvda-next2-bc-baseline-nextbar-20k" `
    -Timesteps "20000" `
    -ExecutionMode "next_bar" `
    -SpreadBps 1.0 `
    -SlippageBps 1.0 `
    -MaxWeightDelta 0.25 `
    -RewardReturnScale 1.3 `
    -RewardDirectionScale 0.55 `
    -RewardDrawdownPenaltyScale 0.04 `
    -RewardActionBonusScale 0.007 `
    -RewardTurnoverPenaltyScale 0.04

# Arm 4: BC baseline at 40k to test under-training vs instability.
Invoke-Experiment `
    -RunLabel "nvda-next2-bc-baseline-nextbar-40k" `
    -Timesteps "40000" `
    -ExecutionMode "next_bar" `
    -SpreadBps 1.0 `
    -SlippageBps 1.0 `
    -MaxWeightDelta 0.25 `
    -RewardReturnScale 1.3 `
    -RewardDirectionScale 0.55 `
    -RewardDrawdownPenaltyScale 0.04 `
    -RewardActionBonusScale 0.007 `
    -RewardTurnoverPenaltyScale 0.04

Write-Host "Batch complete." -ForegroundColor Green
Write-Host "Next: .venv/Scripts/python.exe src/quant_report.py --input data/experiment_leaderboard.csv --output-dir sessions --output-name next-batch-analysis-20260413.md" -ForegroundColor DarkYellow
