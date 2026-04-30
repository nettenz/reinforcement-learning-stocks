# run_maxdelta_loosen_sweep.ps1
# Sweep to fix overtrading using environmental hard caps via max-weight-delta-per-step
# Adjusted to loosen the cap and remove the turnover penalty confound

$PythonExec = ".\.venv\Scripts\python.exe"

Write-Host "======================================================" -ForegroundColor Cyan
Write-Host "Running NVDA Overtrade Fix Sweep (Loosened Cap + Low Penalty)" -ForegroundColor Cyan
Write-Host "======================================================" -ForegroundColor Cyan

& $PythonExec src\experiments.py `
    --ticker nvda `
    --reward-mode sharpe `
    --ent-coefs 0.02,0.05 `
    --timesteps 40000 `
    --seeds 3,7,13 `
    --execution-mode next_bar `
    --reward-hold-penalty-scale 0.01 `
    --reward-turnover-penalty-scale 0.01 `
    --max-weight-delta-per-step 0.15 `
    --run-label "sweep_overtrade_fix_nvda_maxdelta_loosen" `
    --append

Write-Host "`nSweep completed. Evaluate results with evaluate_sweep.py" -ForegroundColor Green
