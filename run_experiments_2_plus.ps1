$ErrorActionPreference = "Stop"

Set-Location -Path $PSScriptRoot

$pythonExe = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $pythonExe)) {
    throw "Python executable not found at $pythonExe"
}

. (Join-Path $PSScriptRoot ".venv\Scripts\Activate.ps1")

$ticker = "nvda"
$seeds = "7,13,21,42,84"
$timesteps = "40000"
$learningRates = "0.0003"
$gammas = "0.99"
$threshold = "0.002"
$transactionCostRate = "0.001"
$tradePenalty = "0.05"
$rewardReturnScale = "1.0"
$rewardDirectionScale = "0.35"
$rewardHoldPenaltyScale = "0.10"
$rewardDrawdownPenaltyScale = "0.10"
$rewardActionBonusScale = "0.02"
$rewardTurnoverPenaltyScale = "0.05"
$rewardClip = "1.0"
$maxWeightDeltaPerStep = "0.25"
$runLabel = "nvda-rx-v2-maxdelta-025"

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

Write-Host "Starting NVDA realism baseline batch in the local Windows .venv..." -ForegroundColor Cyan

$baselineArgs = @(
    "src/experiments.py",
    "--ticker", $ticker,
    "--seeds", $seeds,
    "--timesteps", $timesteps,
    "--learning-rates", $learningRates,
    "--gammas", $gammas,
    "--ent-coefs", "0.02",
    "--threshold", $threshold,
    "--horizon", "1",
    "--transaction-cost-rate", $transactionCostRate,
    "--trade-penalty", $tradePenalty,
    "--execution-mode", "next_bar",
    "--spread-bps", "0.0",
    "--slippage-bps", "0.0",
    "--reward-mode", "sharpe",
    "--reward-return-scale", $rewardReturnScale,
    "--reward-direction-scale", $rewardDirectionScale,
    "--reward-hold-penalty-scale", $rewardHoldPenaltyScale,
    "--reward-drawdown-penalty-scale", $rewardDrawdownPenaltyScale,
    "--reward-action-bonus-scale", $rewardActionBonusScale,
    "--reward-turnover-penalty-scale", $rewardTurnoverPenaltyScale,
    "--reward-clip", $rewardClip,
    "--reward-ignore-transaction-cost",
    "--max-weight-delta-per-step", $maxWeightDeltaPerStep,
    "--append",
    "--run-label", $runLabel
)

Invoke-Experiment -RunLabel $runLabel -Args $baselineArgs

Write-Host "NVDA realism baseline batch complete." -ForegroundColor Green