# run_reward_calibration_manual.ps1
# Reward Calibration: Realism Fix Batch (2026-04-10)
# Purpose: Address cost-blindness and drawdown-paralysis.

$Python = ".venv/Scripts/python.exe"
$BaseCmd = "src/experiments.py"

# Common configuration for all variants
$Common = @(
    "--ticker", "nvda",
    "--timesteps", "20000",
    "--learning-rates", "0.0003",
    "--ent-coefs", "0.07",
    "--reward-mode", "sortino",
    "--rolling-reward-window", "100",
    "--transaction-cost-rate", "0.001",
    "--no-reward-ignore-transaction-cost",
    "--n-envs", "4",
    "--seeds", "10"
)

Write-Host "`n--- Starting Reward Calibration Batch ---" -ForegroundColor Cyan

# Step 1: Variant A - Conservative
# Goal: zero action bonus, higher penalties to force cost-avoidance.
Write-Host "`nStep 1/3: Variant A - Conservative (Safety First)" -ForegroundColor Yellow
& $Python $BaseCmd @Common `
    --run-label "nvda-reward-realism-A-cons" `
    --reward-drawdown-penalty-scale 0.10 `
    --reward-action-bonus-scale 0.0 `
    --reward-turnover-penalty-scale 0.10 `
    --reward-return-scale 1.0

# Step 2: Variant B - Balanced
# Goal: target model with minimal bonus and lighter drawdown control.
Write-Host "`nStep 2/3: Variant B - Balanced (Target Model)" -ForegroundColor Yellow
& $Python $BaseCmd @Common `
    --run-label "nvda-reward-realism-B-bal" `
    --reward-drawdown-penalty-scale 0.05 `
    --reward-action-bonus-scale 0.005 `
    --reward-turnover-penalty-scale 0.05 `
    --reward-return-scale 1.2 `
    --reward-direction-scale 0.50

# Step 3: Variant C - Aggressive
# Goal: maximize alpha-seeking by minimizing drawdown penalties.
Write-Host "`nStep 3/3: Variant C - Aggressive (Alpha Seeking)" -ForegroundColor Yellow
& $Python $BaseCmd @Common `
    --run-label "nvda-reward-realism-C-agg" `
    --reward-drawdown-penalty-scale 0.02 `
    --reward-action-bonus-scale 0.01 `
    --reward-turnover-penalty-scale 0.02 `
    --reward-return-scale 1.5 `
    --reward-direction-scale 0.60

Write-Host "`n--- Calibration Complete. ---" -ForegroundColor Green
Write-Host "Next Step: Analyze snapshots in data/experiment_snapshots/ using research scripts." -ForegroundColor Cyan
