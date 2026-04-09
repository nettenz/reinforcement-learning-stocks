$ErrorActionPreference = "Stop"

Set-Location -Path $PSScriptRoot

$pythonExe = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $pythonExe)) {
    throw "Python executable not found at $pythonExe"
}

. (Join-Path $PSScriptRoot ".venv\Scripts\Activate.ps1")

function Get-AccelerationDevice {
    param(
        [Parameter(Mandatory = $true)]
        [string]$PythonExe
    )

    $deviceProbe = @"
import torch
if torch.cuda.is_available():
    print('cuda')
elif hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
    print('mps')
else:
    print('cpu')
"@

    $detected = (& $PythonExe -c $deviceProbe).Trim().ToLower()
    if (-not $detected) {
        return "cpu"
    }

    return $detected
}

$ticker = "nvda"
$seeds = "7,13,21,42,84"
$timesteps = "20000"
$learningRates = "0.0003"
$gammas = "0.99"
$threshold = "0.002"
$transactionCostRate = "0.001"
$tradePenalty = "0.05"
$rewardReturnScale = "1.0"
$rewardActionBonusScale = "0.02"
$rewardHoldPenaltyScale = "0.10"
$rewardDrawdownPenaltyScales = @("0.10", "0.15")
$rewardTurnoverPenaltyScale = "0.05"
$rewardClip = "1.0"
$maxWeightDeltaPerStep = "0.25"
$rewardMode = "sharpe"
$executionMode = "next_bar"
$device = Get-AccelerationDevice -PythonExe $pythonExe

Write-Host "Acceleration device detected: $device" -ForegroundColor DarkCyan

function Invoke-Experiment {
    param(
        [Parameter(Mandatory = $true)]
        [string]$RunLabel,
        [Parameter(Mandatory = $true)]
        [string[]]$Args
    )

    Write-Host "Running: $pythonExe $($Args -join ' ')" -ForegroundColor Yellow
    & $pythonExe @Args
    if ($LASTEXITCODE -ne 0) {
        throw "Experiment failed: $RunLabel"
    }
}

function New-ExperimentArgs {
    param(
        [Parameter(Mandatory = $true)]
        [string]$DirectionScale,
        [Parameter(Mandatory = $true)]
        [string]$DrawdownPenaltyScale,
        [Parameter(Mandatory = $true)]
        [string]$RunLabel
    )

    return @(
        "src/experiments.py",
        "--device", $device,
        "--ticker", $ticker,
        "--seeds", $seeds,
        "--timesteps", $timesteps,
        "--learning-rates", $learningRates,
        "--gammas", $gammas,
        "--ent-coefs", "0.05",
        "--threshold", $threshold,
        "--horizon", "1",
        "--transaction-cost-rate", $transactionCostRate,
        "--trade-penalty", $tradePenalty,
        "--execution-mode", $executionMode,
        "--spread-bps", "0.0",
        "--slippage-bps", "0.0",
        "--reward-mode", $rewardMode,
        "--reward-return-scale", $rewardReturnScale,
        "--reward-direction-scale", $DirectionScale,
        "--reward-hold-penalty-scale", $rewardHoldPenaltyScale,
        "--reward-drawdown-penalty-scale", $DrawdownPenaltyScale,
        "--reward-action-bonus-scale", $rewardActionBonusScale,
        "--reward-turnover-penalty-scale", $rewardTurnoverPenaltyScale,
        "--reward-clip", $rewardClip,
        "--reward-ignore-transaction-cost",
        "--max-weight-delta-per-step", $maxWeightDeltaPerStep,
        "--append",
        "--run-label", $RunLabel
    )
}

Write-Host "Starting NVDA downside-control batch..." -ForegroundColor Cyan

foreach ($drawdownScale in $rewardDrawdownPenaltyScales) {
    $runLabel = "nvda-downside-ab-20k-ent05-bonus002-dd$($drawdownScale -replace '\\.', '')"
    $args = New-ExperimentArgs -DirectionScale "0.35" -DrawdownPenaltyScale $drawdownScale -RunLabel $runLabel
    Invoke-Experiment -RunLabel $runLabel -Args $args
}

Write-Host "Downside-control batch complete." -ForegroundColor Green
