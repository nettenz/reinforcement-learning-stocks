# Reward Calibration Sweep Experiment
# Purpose: Test reward_clip and penalty scale variations to reduce config CV
# Target: Reduce test_return_cv_by_config from 9.43 to < 2.5
# Uses: Best entropy schedule from Experiment 1
# Duration: ~2.5-3.5 hours, 15-18 GPU hours

param(
    [string]$Ticker = "nvda",
    [int[]]$Seeds = @(7, 13, 21, 27, 123),
    [int]$Timesteps = 20000,
    [string]$RewardMode = "sharpe",
    [double]$EntCoef = 0.06,
    [string]$EntropySchedule = "fixed"  # "fixed" or "decay" - from Exp 1 best
)

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "REWARD CALIBRATION SWEEP EXPERIMENT" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Config:" -ForegroundColor Yellow
Write-Host "  Ticker:              $Ticker"
Write-Host "  Seeds:               $($Seeds -join ',')"
Write-Host "  Timesteps:           $Timesteps"
Write-Host "  Reward Mode:         $RewardMode"
Write-Host "  Entropy Coef:        $EntCoef"
Write-Host "  Entropy Schedule:    $EntropySchedule"
Write-Host ""
Write-Host "Treatments:" -ForegroundColor Yellow
Write-Host "  A: reward_clip=2.0 (higher tolerance)"
Write-Host "  B: drawdown_penalty=0.10 (lower penalty, was 0.15)"
Write-Host "  C: turnover_penalty=0.02 (lower penalty, was 0.05)"
Write-Host "  D: Control (clip=1.0, dd=0.15, to=0.05)"
Write-Host ""

# Activate venv
& .\.venv\Scripts\Activate.ps1

$treatments = @(
    @{
        name = "A_HigherClip"
        reward_clip = 2.0
        drawdown_penalty = 0.15
        turnover_penalty = 0.05
        label = "clip-2.0"
        description = "Higher reward clip (2.0 vs 1.0)"
    },
    @{
        name = "B_LowerDrawdownPenalty"
        reward_clip = 1.0
        drawdown_penalty = 0.10
        turnover_penalty = 0.05
        label = "dd-penalty-0.10"
        description = "Lower drawdown penalty (0.10 vs 0.15)"
    },
    @{
        name = "C_LowerTurnoverPenalty"
        reward_clip = 1.0
        drawdown_penalty = 0.15
        turnover_penalty = 0.02
        label = "to-penalty-0.02"
        description = "Lower turnover penalty (0.02 vs 0.05)"
    },
    @{
        name = "D_Control"
        reward_clip = 1.0
        drawdown_penalty = 0.15
        turnover_penalty = 0.05
        label = "control"
        description = "Control (current settings)"
    }
)

$results = @()

foreach ($treatment in $treatments) {
    Write-Host "========================================" -ForegroundColor Green
    Write-Host "Treatment: $($treatment.name)" -ForegroundColor Green
    Write-Host "Description: $($treatment.description)" -ForegroundColor Green
    Write-Host "========================================" -ForegroundColor Green
    Write-Host ""

    foreach ($seed in $Seeds) {
        Write-Host "  Running seed=$seed..."
        
        # Construct command
        $cmd = @(
            "python", "src/experiments.py",
            "--ticker", $Ticker,
            "--seeds", $seed.ToString(),
            "--timesteps", $Timesteps.ToString(),
            "--ent-coefs", $EntCoef.ToString(),
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
            "--reward-drawdown-penalty-scale", $treatment.drawdown_penalty.ToString(),
            "--reward-action-bonus-scale", "0.02",
            "--reward-turnover-penalty-scale", $treatment.turnover_penalty.ToString(),
            "--reward-clip", $treatment.reward_clip.ToString(),
            "--reward-ignore-transaction-cost",
            "--max-runs", "1",
            "--run-label", "reward-calib-$($treatment.label)-seed$seed",
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
Write-Host "2. Filter to runs starting with 'reward-calib-'"
Write-Host "3. For each treatment, calculate:"
Write-Host "   - test_return_cv_by_config (target: < 2.5)"
Write-Host "   - test_alpha_vs_qqq (target: >= -100bp)"
Write-Host "   - test_actionable_accuracy (must maintain >= 50%)"
Write-Host "4. Pick treatment with lowest CV and highest alpha"
Write-Host "5. Use best reward params for Experiment 4 (timesteps optimization)"
Write-Host ""
Write-Host "Success Criteria:" -ForegroundColor Yellow
Write-Host "  [ ] Best treatment: test_return_cv_by_config < 2.5 (vs current 9.43)"
Write-Host "  [ ] Test alpha improves to >= -100bp (from current -150bp)"
Write-Host "  [ ] Test accuracy maintained >= 50%"
Write-Host ""
