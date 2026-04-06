$ErrorActionPreference = "Stop"

Set-Location -Path $PSScriptRoot

$pythonExe = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $pythonExe)) {
    throw "Python executable not found at $pythonExe"
}

. (Join-Path $PSScriptRoot ".venv\Scripts\Activate.ps1")

$ticker = "nvda"
$seeds = "7,13,21,42,84"
$timesteps = "12000"
$learningRates = "0.0001"
$gammas = "0.99"
$threshold = "0.002"
$transactionCostRate = "0.001"
$tradePenalty = "0.05"
$rewardReturnScale = "1.0"
$rewardHoldPenaltyScale = "0.10"
$rewardClip = "1.0"
$nEnvs = "8"
$runLabelPrefix = "nvda-rw-v1"

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

Write-Host "Starting NVDA reward-calibration batch in the local Windows .venv..." -ForegroundColor Cyan

$balancedArgs = @(
    "src/experiments.py",
    "--ticker", $ticker,
    "--include-news",
    "--use-stationary-features",
    "--seeds", $seeds,
    "--timesteps", $timesteps,
    "--learning-rates", $learningRates,
    "--gammas", $gammas,
    "--ent-coefs", "0.05",
    "--threshold", $threshold,
    "--horizon", "1",
    "--transaction-cost-rate", $transactionCostRate,
    "--trade-penalty", $tradePenalty,
    "--execution-mode", "next_bar",
    "--reward-mode", "sharpe",
    "--reward-return-scale", $rewardReturnScale,
    "--reward-direction-scale", "0.30",
    "--reward-hold-penalty-scale", $rewardHoldPenaltyScale,
    "--reward-drawdown-penalty-scale", "0.12",
    "--reward-action-bonus-scale", "0.005",
    "--reward-turnover-penalty-scale", "0.01",
    "--reward-clip", $rewardClip,
    "--no-reward-ignore-transaction-cost",
    "--n-envs", $nEnvs,
    "--append",
    "--run-label", "$runLabelPrefix-balanced"
)
Invoke-Experiment -RunLabel "$runLabelPrefix-balanced" -Args $balancedArgs

$conservativeArgs = @(
    "src/experiments.py",
    "--ticker", $ticker,
    "--include-news",
    "--use-stationary-features",
    "--seeds", $seeds,
    "--timesteps", $timesteps,
    "--learning-rates", $learningRates,
    "--gammas", $gammas,
    "--ent-coefs", "0.05",
    "--threshold", $threshold,
    "--horizon", "1",
    "--transaction-cost-rate", $transactionCostRate,
    "--trade-penalty", $tradePenalty,
    "--execution-mode", "next_bar",
    "--reward-mode", "sharpe",
    "--reward-return-scale", $rewardReturnScale,
    "--reward-direction-scale", "0.20",
    "--reward-hold-penalty-scale", "0.15",
    "--reward-drawdown-penalty-scale", "0.20",
    "--reward-action-bonus-scale", "0.00",
    "--reward-turnover-penalty-scale", "0.03",
    "--reward-clip", $rewardClip,
    "--no-reward-ignore-transaction-cost",
    "--n-envs", $nEnvs,
    "--append",
    "--run-label", "$runLabelPrefix-conservative"
)
Invoke-Experiment -RunLabel "$runLabelPrefix-conservative" -Args $conservativeArgs

$aggressiveArgs = @(
    "src/experiments.py",
    "--ticker", $ticker,
    "--include-news",
    "--use-stationary-features",
    "--seeds", $seeds,
    "--timesteps", $timesteps,
    "--learning-rates", $learningRates,
    "--gammas", $gammas,
    "--ent-coefs", "0.05",
    "--threshold", $threshold,
    "--horizon", "1",
    "--transaction-cost-rate", $transactionCostRate,
    "--trade-penalty", $tradePenalty,
    "--execution-mode", "next_bar",
    "--reward-mode", "sharpe",
    "--reward-return-scale", $rewardReturnScale,
    "--reward-direction-scale", "0.50",
    "--reward-hold-penalty-scale", "0.05",
    "--reward-drawdown-penalty-scale", "0.08",
    "--reward-action-bonus-scale", "0.01",
    "--reward-turnover-penalty-scale", "0.005",
    "--reward-clip", $rewardClip,
    "--no-reward-ignore-transaction-cost",
    "--n-envs", $nEnvs,
    "--append",
    "--run-label", "$runLabelPrefix-aggressive"
)
Invoke-Experiment -RunLabel "$runLabelPrefix-aggressive" -Args $aggressiveArgs

Write-Host "NVDA reward-calibration batch complete." -ForegroundColor Green