#!/usr/bin/env pwsh

$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

$pythonExe = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $pythonExe)) {
    throw "Python executable not found at $pythonExe"
}

. (Join-Path $PSScriptRoot ".venv\Scripts\Activate.ps1")

Write-Host "Confirmatory Follow-Up Batch (2026-04-13)" -ForegroundColor Green
Write-Host "Purpose: Confirm the NVDA champion on fresh seeds and test transfer to other tickers." -ForegroundColor Yellow

$device = "cuda"
$freshSeeds = "202,303,404,505,606"
$timesteps = "20000"

$common = @(
    "src/experiments.py",
    "--device", $device,
    "--seeds", $freshSeeds,
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

function Invoke-ConfirmatoryRun {
    param(
        [Parameter(Mandatory = $true)] [string]$Ticker,
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
        "--ticker", $Ticker,
        "--timesteps", $Timesteps,
        "--run-label", $RunLabel,
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

# Champion confirmation: same settings that were promoted for NVDA, with fresh seeds.
Invoke-ConfirmatoryRun `
    -Ticker "nvda" `
    -RunLabel "nvda-confirm-champion-nextbar-20k" `
    -Timesteps $timesteps `
    -ExecutionMode "next_bar" `
    -SpreadBps 1.0 `
    -SlippageBps 1.0 `
    -MaxWeightDelta 0.25 `
    -RewardReturnScale 1.3 `
    -RewardDirectionScale 0.55 `
    -RewardDrawdownPenaltyScale 0.04 `
    -RewardActionBonusScale 0.007 `
    -RewardTurnoverPenaltyScale 0.05

# Matched baseline for NVDA to judge whether the champion remains better than the prior BC baseline.
Invoke-ConfirmatoryRun `
    -Ticker "nvda" `
    -RunLabel "nvda-confirm-baseline-nextbar-20k" `
    -Timesteps $timesteps `
    -ExecutionMode "next_bar" `
    -SpreadBps 1.0 `
    -SlippageBps 1.0 `
    -MaxWeightDelta 0.25 `
    -RewardReturnScale 1.3 `
    -RewardDirectionScale 0.55 `
    -RewardDrawdownPenaltyScale 0.04 `
    -RewardActionBonusScale 0.007 `
    -RewardTurnoverPenaltyScale 0.04

# Transfer checks on other supported tickers using the same champion settings.
Invoke-ConfirmatoryRun `
    -Ticker "aapl" `
    -RunLabel "aapl-confirm-champion-nextbar-20k" `
    -Timesteps $timesteps `
    -ExecutionMode "next_bar" `
    -SpreadBps 1.0 `
    -SlippageBps 1.0 `
    -MaxWeightDelta 0.25 `
    -RewardReturnScale 1.3 `
    -RewardDirectionScale 0.55 `
    -RewardDrawdownPenaltyScale 0.04 `
    -RewardActionBonusScale 0.007 `
    -RewardTurnoverPenaltyScale 0.05

Invoke-ConfirmatoryRun `
    -Ticker "amd" `
    -RunLabel "amd-confirm-champion-nextbar-20k" `
    -Timesteps $timesteps `
    -ExecutionMode "next_bar" `
    -SpreadBps 1.0 `
    -SlippageBps 1.0 `
    -MaxWeightDelta 0.25 `
    -RewardReturnScale 1.3 `
    -RewardDirectionScale 0.55 `
    -RewardDrawdownPenaltyScale 0.04 `
    -RewardActionBonusScale 0.007 `
    -RewardTurnoverPenaltyScale 0.05

Write-Host "Batch complete." -ForegroundColor Green
Write-Host "Next: .venv/Scripts/python.exe src/quant_report.py --input data/experiment_leaderboard.csv --output-dir sessions --output-name confirmatory-followup-analysis-20260413.md" -ForegroundColor DarkYellow