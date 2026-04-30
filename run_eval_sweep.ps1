# run_eval_sweep.ps1
# Script to run the evaluation commands from EVAL_SWEEP.md sequentially

$PythonExec = ".\.venv\Scripts\python.exe"

Write-Host "======================================================" -ForegroundColor Cyan
Write-Host "1. Inspect the full sweep results" -ForegroundColor Cyan
Write-Host "======================================================" -ForegroundColor Cyan
& $PythonExec scripts/evaluate_sweep.py --leaderboard data/experiment_leaderboard.csv --label sweep_overtrade_fix_nvda

Write-Host "`n======================================================" -ForegroundColor Cyan
Write-Host "2. Champion found - auto-trigger ensemble config regeneration" -ForegroundColor Cyan
Write-Host "======================================================" -ForegroundColor Cyan
& $PythonExec scripts/evaluate_sweep.py --leaderboard data/experiment_leaderboard.csv --label sweep_overtrade_fix_nvda --promote

Write-Host "`n======================================================" -ForegroundColor Cyan
Write-Host "3. Full leaderboard view for NVDA" -ForegroundColor Cyan
Write-Host "======================================================" -ForegroundColor Cyan
& $PythonExec scripts/evaluate_sweep.py --leaderboard data/experiment_leaderboard.csv --ticker NVDA --top 20

Write-Host "`nSweep evaluation completed." -ForegroundColor Green
