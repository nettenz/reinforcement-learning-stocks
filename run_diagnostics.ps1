# PowerShell Script: Run All Diagnostics with Logging
# Usage: .\run_diagnostics.ps1

$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$logfile = "diagnostic_run_${timestamp}.log"

function Log-Message {
    param([string]$message)
    $msg = "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] $message"
    Write-Host $msg
    Add-Content -Path $logfile -Value $msg
}

Log-Message "=== DIAGNOSTIC RUN STARTED ==="
Log-Message "Log file: $logfile"

# Set working directory
Set-Location "d:\code\agentic-development\reinforcement-learning-stocks"
Log-Message "Working directory: $(Get-Location)"

# Activate virtual environment
& ".\.venv\Scripts\Activate.ps1"
Log-Message "Virtual environment activated"

# ============================================================================
# STEP 1: Consolidate Validation Snapshots
# ============================================================================
Log-Message ""
Log-Message "========== STEP 1: CONSOLIDATE VALIDATION SNAPSHOTS =========="
Log-Message "Running consolidation..."

$consolidateCmd = @'
import pandas as pd
from pathlib import Path

main_csv = Path("data/experiment_leaderboard.csv")
snapshot_dir = Path("data/experiment_snapshots")

# Read main leaderboard
main_df = pd.read_csv(main_csv)
print(f"Main leaderboard: {len(main_df)} rows")

# Find all validation snapshot CSVs
snapshot_files = sorted(snapshot_dir.glob("experiment_leaderboard_*validation*.csv"))
print(f"Found {len(snapshot_files)} validation snapshot files")

# Consolidate
all_rows = [main_df]
for snap_file in snapshot_files:
    try:
        snap_df = pd.read_csv(snap_file)
        all_rows.append(snap_df)
        print(f"  Added {snap_file.name}: {len(snap_df)} rows")
    except Exception as e:
        print(f"  Skipped {snap_file.name}: {e}")

consolidated = pd.concat(all_rows, ignore_index=True, sort=False)
consolidated.to_csv(main_csv, index=False)
print(f"\nConsolidated → {len(consolidated)} total rows in {main_csv}")
print(f"Tickers present: {sorted(consolidated['ticker'].unique())}")
'@

$consolidateCmd | python3 2>&1 | Tee-Object -FilePath $logfile -Append | Log-Message

Log-Message "Step 1 complete."

# ============================================================================
# STEP 2: Diagnostic 1 - Baseline
# ============================================================================
Log-Message ""
Log-Message "========== STEP 2: DIAGNOSTIC 1 - BASELINE =========="
Log-Message "Starting diagnostic 1..."

python src/experiments.py --ticker riot --include-news --use-stationary-features --seeds 7 --timesteps 5000 --learning-rates 0.0003 --gammas 0.99 --ent-coefs 0.05 --threshold 0.002 --horizon 1 --transaction-cost-rate 0.001 --trade-penalty 0.05 --reward-mode sharpe --max-runs 1 --append --run-label diagnostic-1-baseline 2>&1 | Tee-Object -FilePath $logfile -Append

Log-Message "Step 2 complete."

# ============================================================================
# STEP 3: Diagnostic 2 - Lower Trade Penalty
# ============================================================================
Log-Message ""
Log-Message "========== STEP 3: DIAGNOSTIC 2 - LOWER TRADE PENALTY =========="
Log-Message "Starting diagnostic 2..."

python src/experiments.py --ticker riot --include-news --use-stationary-features --seeds 7 --timesteps 5000 --learning-rates 0.0003 --gammas 0.99 --ent-coefs 0.05 --threshold 0.002 --horizon 1 --transaction-cost-rate 0.001 --trade-penalty 0.01 --reward-mode sharpe --max-runs 1 --append --run-label diagnostic-2-low-trade-penalty 2>&1 | Tee-Object -FilePath $logfile -Append

Log-Message "Step 3 complete."

# ============================================================================
# STEP 4: Diagnostic 3 - Higher Entropy + Action Bonus
# ============================================================================
Log-Message ""
Log-Message "========== STEP 4: DIAGNOSTIC 3 - HIGH ENTROPY + ACTION BONUS =========="
Log-Message "Starting diagnostic 3..."

python src/experiments.py --ticker riot --include-news --use-stationary-features --seeds 7 --timesteps 5000 --learning-rates 0.0003 --gammas 0.99 --ent-coefs 0.10 --threshold 0.002 --horizon 1 --transaction-cost-rate 0.001 --trade-penalty 0.05 --reward-action-bonus-scale 0.15 --reward-mode sharpe --max-runs 1 --append --run-label diagnostic-3-high-entropy-action-bonus 2>&1 | Tee-Object -FilePath $logfile -Append

Log-Message "Step 4 complete."

# ============================================================================
# STEP 5: Check Results
# ============================================================================
Log-Message ""
Log-Message "========== STEP 5: CHECK RESULTS =========="
Log-Message "Analyzing diagnostic results..."

$resultCmd = @'
import pandas as pd

df = pd.read_csv("data/experiment_leaderboard.csv")

# Filter to diagnostic runs only
diag = df[df['run_label'].str.contains('diagnostic', case=False, na=False)].copy()

if len(diag) > 0:
    print("\n=== DIAGNOSTIC RESULTS ===\n")
    cols = ['run_label', 'seed', 'trade_penalty', 'reward_action_bonus_scale', 'test_trade_count', 'test_trade_win_rate', 'test_actionable_accuracy', 'ranking_score']
    available = [c for c in cols if c in diag.columns]
    print(diag[available].tail(10).to_string(index=False))
    print("\n=== INTERPRETATION ===")
    for _, row in diag.tail(3).iterrows():
        label = row['run_label']
        trades = row.get('test_trade_count', 0)
        acc = row.get('test_actionable_accuracy', 0)
        score = row.get('ranking_score', 0)
        print(f"{label}: {int(trades)} trades, {acc:.2%} accuracy, {score:.4f} score")
    print("\n=== RECOMMENDATION ===")
    best_row = diag.sort_values('ranking_score', ascending=False).iloc[0]
    print(f"Best config: {best_row['run_label']}")
    print(f"  Trade penalty: {best_row.get('trade_penalty', 'N/A')}")
    print(f"  Action bonus scale: {best_row.get('reward_action_bonus_scale', 'N/A')}")
    print(f"  Trades: {int(best_row.get('test_trade_count', 0))}")
    print(f"  Accuracy: {best_row.get('test_actionable_accuracy', 0):.2%}")
    print(f"  Ranking Score: {best_row['ranking_score']:.4f}")
else:
    print("No diagnostic runs found yet")
'@

$resultCmd | python3 2>&1 | Tee-Object -FilePath $logfile -Append

Log-Message ""
Log-Message "=== DIAGNOSTIC RUN COMPLETE ==="
Log-Message "Results saved to: $logfile"
Log-Message ""
Log-Message "Next steps:"
Log-Message "1. Review the diagnostic results in the log file above"
Log-Message "2. Identify which diagnostic had the best ranking_score with trades > 0"
Log-Message "3. Return to provide Phase 2 sweep with winning configuration"

Write-Host ""
Write-Host "[OK] All diagnostics complete! Log saved to: $logfile" -ForegroundColor Green
Write-Host "[INFO] Review the output above and return with results." -ForegroundColor Cyan
