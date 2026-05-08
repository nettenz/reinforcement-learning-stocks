# run_amzn_v2.ps1
# Automates the evaluation of AMZN Pilot and launches the v2 follow-up sweep.

Write-Host "--- STEP 1: Evaluating Pilot with Relaxed G6 ---" -ForegroundColor Cyan
.\.venv\Scripts\python.exe scripts\evaluate_sweep.py `
    --leaderboard data\experiment_leaderboard.csv `
    --label sweep_amzn_stage1_pilot `
    --g6-max-trade-rate 1.00

Write-Host "`n--- STEP 2: Launching AMZN v2 Sweep (Higher Entropy + 60k Steps) ---" -ForegroundColor Cyan
.\.venv\Scripts\python.exe src\experiments.py `
    --ticker amzn `
    --reward-mode sharpe `
    --ent-coefs 0.03,0.05,0.08 `
    --timesteps 60000 `
    --seeds 7,42,13 `
    --execution-mode next_bar `
    --reward-hold-penalty-scale 0.00 `
    --reward-turnover-penalty-scale 0.00 `
    --use-stationary-features `
    --binary-actions `
    --min-hold-bars 3 `
    --run-label "sweep_amzn_stage1_v2" `
    --append

Write-Host "`n--- STEP 3: Evaluating v2 Results ---" -ForegroundColor Cyan
.\.venv\Scripts\python.exe scripts\evaluate_sweep.py `
    --leaderboard data\experiment_leaderboard.csv `
    --label sweep_amzn_stage1_v2 `
    --g6-max-trade-rate 1.00
