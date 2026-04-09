# Quick Reference: Next Batch Execution

## Summary of Downside-Control Results
- ❌ **dd_penalty=0.15 (tighter) degraded ALL metrics**
- ✅ **dd_penalty=0.10 (current) is better**
- 🔴 **Seed stability issue:** Seeds 7 & 84 flipped from +0.44 to -0.33 Sharpe with tighter penalty

---

## Run Entropy A/B (Priority 1)

```powershell
# Navigate to project root
cd d:\code\agentic-development\reinforcement-learning-stocks

# Activate venv (if not already)
. .\.venv\Scripts\Activate.ps1

# Run entropy experiment (10 runs: ent_coef 0.05 vs 0.08)
.\run_entropy_ablation.ps1

# After batch completes, generate analysis
python src/quant_report.py --input data/experiment_leaderboard.csv --output-dir sessions --output-name entropy-ab-analysis.md

# View results
cat sessions\entropy-ab-analysis.md
```

**Expected time:** 5-10 mins  
**Expected output:** 10 new rows in leaderboard.csv (v2, entropy configs)

---

## Diagnostic Reports Generated

✅ `sessions/DOWNSIDE_CONTROL_BATCH_SUMMARY.md` — This summary  
✅ `sessions/downside-control-ab-findings.md` — Detailed findings + per-seed breakdown  
✅ `sessions/downside-control-ab-analysis.md` — Quant report on all 10 runs  

---

## If Entropy A/B Succeeds
(If mean test Sharpe improves to >0.15 and seed CV drops)

Next: Run environment realism audit
```bash
python src/environment_realism_audit.py --config dd0.10 --output sessions/env-realism-audit.md
```

---

## If Entropy A/B Fails
(If mean test Sharpe stays <0.10 or seeds still unstable)

Next: Shift to multi-ticker strategy
- Modify `src/market_data.py` to load AAPL, MSFT, AMD alongside NVDA
- Update `run_entropy_ablation.ps1` ticker field to support multi-ticker
- Re-run with `--ticker multi` option

---

## Key Metrics to Watch

| Metric | Target | Current |
|--------|--------|---------|
| mean test Sharpe | >0.15 | -0.02 |
| Sharpe CV (cross-seed) | <1.5 | 9.86 (very high) |
| Seed 7 behavior | Stable | Reversed +0.44→-0.33 |
| Seed 84 behavior | Stable | Reversed +0.13→-0.65 |

---

## File Locations

| File | Purpose |
|------|---------|
| `run_entropy_ablation.ps1` | ✅ Ready to run |
| `data/experiment_leaderboard.csv` | Current results (10 v2 rows) |
| `data/experiment_leaderboard_history.csv` | Archive (10 v2 rows) |
| `sessions/downside-control-ab-findings.md` | Detailed analysis |
| `src/quant_report.py` | Report generator |

---

## Next Decision Point

After entropy A/B completes:

1. **If entropy helps:** Proceed to environment realism audit
2. **If entropy doesn't help:** Pivot to multi-ticker or reward redesign
3. **If results are inconclusive:** Run larger batch (10 seeds each) to confirm

---

## Status Tracker
- [x] Downside-control batch complete (10 runs)
- [x] Results analyzed and findings documented
- [x] Entropy A/B script prepared
- [ ] Entropy A/B batch pending execution
- [ ] Environment realism audit pending (if entropy succeeds)
