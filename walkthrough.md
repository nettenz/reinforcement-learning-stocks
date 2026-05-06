Updating the todo list to mark NVDA tuning complete and AMD tuning in-progress. Then I'll provide the experiment commands and plan.

Starting: *Repeat tuning on AMD* (10/12)

**Research summary**
- ExitManager implemented (exit_manager.py) and unit-tested (test_exit_manager.py).  
- NVDA backtest sweep ran; val favored `trailing_8pct` (highest val Sharpe) but selection logic chose `trailing_5pct`; final test evaluation for `trailing_5pct` failed success gates. See backtest_summary.md.

**What improved**
- Val split Sharpe improved for several exit rules vs no-exit; `trailing_8pct` achieved the highest val Sharpe (2.648).  
- Exit rules produced non-zero exit rates (previously 0% for NVDA) — so ExitManager produces explicit exits.

**What degraded or remains weak**
- Test performance (NVDA, `trailing_5pct`) fell: Sharpe 0.666, max_dd -0.352, exit_rate 10.5%, avg_hold 8.2 — all outside the success gates.  
- Val→test gap indicates selection overfitting or regime shift; exit rate slightly above preferred range.

**Most likely explanations**
- Selection on val Sharpe alone favored rules that reduce in-sample variance but over-exited on out-of-sample regime.  
- Ensemble unanimous buy bias means exit rules have outsized impact on realized trades, magnifying test instability.  
- `trailing_stop` variants can shorten holds and raise realized volatility if the market regime changed.

**Confidence level for current conclusions**
- Medium-low: conclusions are supported by the `backtest_exit_rules` sweep artifacts, but are single-ticker (NVDA) + limited seed set evidence; need AMD and per-seed checks.

**Recommended next experiment batch**
1. Evaluate top val configs on test individually (no re-selection) to check selection fragility.
   - Command:
```bash
python scripts/backtest_exit_rules.py --ticker nvda --config trailing_8pct --test-only
python scripts/backtest_exit_rules.py --ticker nvda --config trailing_5pct --test-only
```
2. Re-run full sweep but enforce exit-rate bounds during selection (pick best-val sharpe subject to exit_rate in [0.02,0.10]) — quick approach: run the full sweep and post-filter the CSV; to evaluate candidate config(s) on test:
```bash
python scripts/backtest_exit_rules.py --ticker nvda
# then evaluate chosen config from the printed val ranking:
python scripts/backtest_exit_rules.py --ticker nvda --config trailing_8pct --test-only
```
3. Repeat full sweep for AMD (use its active seeds).
```bash
python scripts/backtest_exit_rules.py --ticker amd
```
4. Per-seed sensitivity: run backtest_exit_rules.py but temporarily set `--config no_exit` vs a selected rule for each individual seed model (modify ensemble_config.json or create a tmp leaderboard) — quick test:
```bash
python scripts/backtest_exit_rules.py --ticker nvda --config trailing_8pct --test-only
# to approximate per-seed, build a tmp leaderboard as in script _load_ensemble and call the script similarly
```
5. If a candidate passes test gates, run longer robustness checks: rolling-window backtests and bootstrap per-seed returns (scripts/notebook or a new script).

**Priority order**
- 1st: Evaluate `trailing_8pct` and `trailing_5pct` on the test split (commands above).  
- 2nd: Full AMD sweep.  
- 3rd: Per-seed sensitivity and rolling-window robustness.  
- 4th: If any candidate passes, run multi-regime stress tests and produce `backtest_summary.md` for review.

**Success/failure interpretation plan**
- Success if test sharpe ≥ baseline (NVDA 1.828), max_dd > -0.045, exit_rate in [0.05,0.10], avg_hold in [10,30].  
- If a rule improves test sharpe but violates exit-rate bounds, mark as "operationally marginal" — consider slight param tweaks (e.g., trailing 6–8%).  
- If val→test gap persists across configs and tickers, escalate to ensemble diversification (add seeds/models) or retraining with drawdown/take-profit penalties.

**Leaderboard comparability impact (REQUIRED)**
- Applying ExitManager is an export-layer change: it does not modify training or leaderboard artifacts (experiment_leaderboard.csv), so ledger comparability of model training remains intact.  
- However, realized returns used in backtests will differ from leaderboard "signal-only" metrics — when reporting comparisons, always state “post-export exit rule applied” and include both signal-only and realized-with-exits metrics.

**Promotion readiness assessment**
- Not ready for NVDA: selected config fails test gates.  
- AMD: not yet evaluated end-to-end (run sweep).  
- Next promotion criteria: candidate must pass test gates across tickers and show per-seed robustness (low config CV) before production/monitoring deployment.

Would you like me to (A) run the two `--test-only` commands for NVDA now, (B) run the AMD sweep next, or (C) produce a small script to automate selection-by-exit-rate + val-sharpe and re-evaluate the chosen config on test?