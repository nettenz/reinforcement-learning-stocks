# Entropy Schedule Ablation Experiment
# Purpose: Test whether fixed entropy (no decay) vs current decay improves seed stability
# Target: Reduce test_return_cv_by_config from 9.43 to < 3.0
# Duration: ~2.5-3.5 hours, 15 GPU hours

param(
    [string]$Ticker = "nvda",
    [int[]]$Seeds = @(7, 13, 21, 27, 123),
    [int]$Timesteps = 20000,
    [string]$RewardMode = "sharpe",
    [double]$Entropy_Fixed = 0.06
)

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "ENTROPY SCHEDULE ABLATION EXPERIMENT" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Config:" -ForegroundColor Yellow
Write-Host "  Ticker:           $Ticker"
Write-Host "  Seeds:            $($Seeds -join ',')"
Write-Host "  Timesteps:        $Timesteps"
Write-Host "  Reward Mode:      $RewardMode"
Write-Host "  Entropy (fixed):  $Entropy_Fixed"
Write-Host ""

# Activate venv
& .\.venv\Scripts\Activate.ps1

$treatments = @(
    @{
        name = "A_NoDecay_Ent06"
        ent_coef = 0.06
        label = "no-decay-ent-0.06"
        description = "Fixed entropy 0.06, no schedule decay"
    },
    @{
        name = "B_Control_Ent06"
        ent_coef = 0.06
        label = "control-ent-0.06"
        description = "Current linear decay entropy 0.06 (control)"
    },
    @{
        name = "C_MoreExplore_Ent08"
        ent_coef = 0.08
        label = "no-decay-ent-0.08"
        description = "Fixed entropy 0.08, no schedule decay"
    }
)

$results = @()

foreach ($treatment in $treatments) {
    Write-Host "========================================" -ForegroundColor Green
    Write-Host "Treatment: $($treatment.name)" -ForegroundColor Green
    Write-Host "Description: $($treatment.description)" -ForegroundColor Green
    Write-Host "========================================" -ForegroundColor Green
    Write-Host ""

    $treatmentResults = @()
    
    foreach ($seed in $Seeds) {
        Write-Host "  Running seed=$seed..."
        
        # Construct command
        $cmd = @(
            "python", "src/experiments.py",
            "--ticker", $Ticker,
            "--seeds", $seed.ToString(),
            "--timesteps", $Timesteps.ToString(),
            "--ent-coefs", $treatment.ent_coef.ToString(),
            "--reward-mode", $RewardMode,
            "--learning-rates", "0.0003",
            "--gammas", "0.99",
            "--threshold", "0.002",
            "--horizon", "1",
            "--transaction-cost-rate", "0.001",
            "--trade-penalty", "0.05",
            "--execution-mode", "next_bar",
            "--spread-bps", "0.0",
            "--slippage-bps", "0.0",
            "--max-weight-delta-per-step", "0.0",
            "--rolling-reward-window", "100",
            "--reward-epsilon", "1e-6",
            "--reward-return-scale", "1.0",
            "--reward-direction-scale", "0.35",
            "--reward-hold-penalty-scale", "0.1",
            "--reward-drawdown-penalty-scale", "0.15",
            "--reward-action-bonus-scale", "0.02",
            "--reward-turnover-penalty-scale", "0.05",
            "--reward-clip", "1.0",
            "--reward-ignore-transaction-cost",
            "--max-runs", "1",
            "--run-label", "$($treatment.label)-seed$seed",
            "--append"
        )
        
        & $cmd[0] $cmd[1..($cmd.Length-1)]
        
        if ($LASTEXITCODE -eq 0) {
            Write-Host "    ✓ Completed" -ForegroundColor Green
        } else {
            Write-Host "    ✗ Failed (exit code $LASTEXITCODE)" -ForegroundColor Red
        }
    }
    
    Write-Host ""
}

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "EXPERIMENT COMPLETE" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Next Steps:" -ForegroundColor Yellow
Write-Host "1. Check leaderboard: data/experiment_leaderboard.csv"
Write-Host "2. Compare test_return_cv_by_config for each treatment"
Write-Host "3. Pick treatment with lowest CV (target: < 3.0)"
Write-Host "4. Use best entropy schedule for Experiment 3 (reward calibration)"
Write-Host ""
Write-Host "Success Criteria:" -ForegroundColor Yellow
Write-Host "  [ ] Best treatment: test_return_cv_by_config < 3.0 (vs current 9.43)"
Write-Host "  [ ] All 5 seeds cluster within ±10% test_actionable_accuracy"
Write-Host "  [ ] Test alpha improves to >= -50bp (from current -150bp)"
Write-Host ""
