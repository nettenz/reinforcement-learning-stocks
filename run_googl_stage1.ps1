# run_googl_stage1.ps1
# Automates the GOOGL PPO Pilot Sweep and Evaluation using the .venv

$LABEL = "googl_ppo_pilot"
$PYTHON = "./.venv/Scripts/python.exe"

# Set UTF-8 encoding for Python to avoid UnicodeEncodeError in Windows terminal
$env:PYTHONUTF8 = 1

Write-Host "Starting GOOGL PPO Pilot Sweep using .venv..." -ForegroundColor Cyan
& $PYTHON src/experiments.py `
    --ticker googl `
    --seeds 7,13,42 `
    --timesteps 60000 `
    --ent-coefs 0.05,0.08 `
    --binary-actions `
    --min-hold-bars 3 `
    --run-label $LABEL `
    --append

Write-Host "Running Automated Gate Evaluation..." -ForegroundColor Yellow
# Using evaluate_sweep.py with relaxed G6 thresholds for GOOGL bull-regime tracking
& $PYTHON scripts/evaluate_sweep.py `
    --leaderboard data/experiment_leaderboard.csv `
    --label $LABEL `
    --ticker googl `
    --g6-max-trade-rate 1.00

Write-Host "Pipeline Complete. Check GOOGL_EXPS.md and experiment_leaderboard.csv" -ForegroundColor Green
