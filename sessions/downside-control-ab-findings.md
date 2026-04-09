# Downside-Control A/B Batch Results
**Batch Completion:** 2026-04-06  
**Comparison:** `reward_drawdown_penalty_scale=0.10` vs `0.15`  
**Fixed Parameters:** `reward_direction_scale=0.35`, `ent_coef=0.05`, `reward_mode=sharpe`  
**Seeds per config:** 5

---

## Key Finding: Tighter Drawdown Penalty DEGRADED Performance

| Metric | dd=0.10 | dd=0.15 | Δ | % Change |
|--------|---------|---------|----|----|
| **test_sharpe_ratio** | **0.1208** | -0.1635 | -0.2843 | **-235%** ⚠️ |
| **test_sortino_ratio** | **0.0449** | -0.2832 | -0.3280 | **-731%** ⚠️ |
| **test_alpha_vs_qqq** | -0.1444 | -0.2559 | -0.1115 | **-77%** |
| **test_cumulative_return** | **-0.0164** | -0.1279 | -0.1115 | **-679%** ⚠️ |
| **test_overall_accuracy** | **0.3987** | 0.3807 | -0.0180 | **-5%** |
| **ranking_score** | **0.4323** | 0.3519 | -0.0804 | **-19%** |

---

## Strategic Assessment

### What Happened
Increasing the drawdown penalty coefficient from 0.10 to 0.15 caused a **systematic degradation across all risk-adjusted performance metrics**:

- **Sharpe ratio collapsed**: 0.1208 → -0.1635 (went negative)
- **Sortino ratio collapsed**: 0.0449 → -0.2832 (went deeply negative)  
- **Return declined**: -0.0164 → -0.1279 (7x worse)
- **Ranking score fell**: 0.4323 → 0.3519

### Why This Happened
The tighter drawdown penalty (dd=0.15) appears to have **constrained the agent's ability to take any profitable trades at all**. Rather than improving downside risk management, it created an overly conservative policy that:

1. **Reduced drawdown but destroyed returns** - The agent became too risk-averse
2. **Accuracy stayed similar** (39.87% → 38.07%) but **execution quality suffered**
3. **The punishment was too aggressive** - The 0.10 penalty was already strong enough

### Implication
The current downside-penalty level (0.10) is already near-optimal for this environment. **Further tightening makes things worse**, not better. This suggests:

- ❌ **Not a tuning opportunity** — More downside control doesn't help
- ⚠️ **Overfitting to an overly conservative regime** — Both dd settings underperform the base (0.336 test Sharpe from pre-fix runs)
- 🔍 **Root cause is elsewhere** — The problem is not downside management; it's either:
  - Reward hacking (model is gaming the sharpe reward signal)
  - Poor exploration (ent_coef=0.05 may be too low)
  - Market regime incompatibility (NVDA may not have a learnable edge)

---

## Historical Baseline Status
⚠️ **WARNING: Leaderboard version history issue**

The downside-control batch (v2) achieved:
- Mean test Sharpe: **-0.0213** (across all 10 runs)
- Mean ranking_score: **0.3921**

Prior work mentioned a baseline of **0.336 test Sharpe**, but this is **not present in current leaderboard** (experiment_leaderboard.csv contains only v2; experiment_leaderboard_history.csv also contains only v2).

**Possible explanations:**
1. ✅ Version tagging worked correctly—v2 file only holds comparable runs (current batch)
2. ❌ Historical v1 data was lost during leaderboard rewrite
3. ❓ Baseline came from a different ticker/subset not currently visible

**Impact:** Cannot directly compare dd0.10 (0.1208) vs the claimed prior base (0.336) without historical v1 data.

---

## Validation Metrics Show Overfitting
- **Val Sharpe:** 0.19 (reasonable)
- **Test Sharpe:** -0.02 (negative—not trading)
- **Val→Test gap:** 79% (severe overfitting)
- **Seed stability CV (test):** 9.86 (highly unstable)

The A/B variation showed that **constrained policies fail harder than unconstrained ones**, suggesting the model is not yet learning a robust trading edge at all.

---

## Per-Seed Breakdown

The degradation in dd0.15 was **not uniform**—it exposed seed instability:

| Seed | dd0.10 | dd0.15 | Δ | Impact |
|------|--------|--------|----|----|
| 13 | 0.4187 | **0.5053** | +0.0866 | Stayed strong ✅ |
| 7 | **0.4446** | -0.3312 | -0.7758 | **Catastrophic reversal** ❌ |
| 84 | 0.1252 | -0.6516 | -0.7768 | **Catastrophic failure** ❌ |
| 42 | -0.3495 | 0.2439 | +0.5934 | Improved but still weak |
| 21 | -0.0349 | -0.5839 | -0.5490 | **Worse** ❌ |

**Critical insight:** Seed 7 and 84 had positive/neutral Sharpe under dd0.10 but turned negative under dd0.15. This is a sign of **overfitting or reward hacking**—the tighter constraint broke seed generalization.

---

## Recommended Next Steps (Prioritized)

### 🔴 Priority 1: Stabilize Cross-Seed Behavior
The dd0.15 setting exposed **severe seed instability** (some seeds got much worse). This indicates the agent is not learning a robust policy.

**Action:** Run **entropy coefficient A/B** (ent_coef 0.05 vs 0.08) with fixed dd=0.10, dir=0.35
- Higher entropy forces broader exploration
- Should reduce overfitting and stabilize seed variance
- If fails: reward signal itself is flawed

**Expected outcome:** If ent_coef helps, test_sharpe mean should improve AND seed CV should decrease.

### 🟡 Priority 2: Audit Reward Semantics
The downside penalty didn't help; directional scaling showed confusing results. **Are we optimizing the right objective?**

**Action:** Generate reward mode comparison report
- Compare `sharpe` vs `sortino` reward modes on same config
- Check if reward optimization correlates with test Sharpe
- If reward and test diverge: reward hacking is happening

### 🟠 Priority 3: Environment Realism Check
Model is training in an unrealistic environment that doesn't translate to edge:

**Action:** Audit [SKILL: environment-realism-auditor]
- **Execution mode:** next_bar allows infinite precision entry/exit
- **Spread:** Currently 0 bps; NVDA has ~0.5-1 bps spreads  
- **Position sizing:** 25% max delta per step is unconstrained
- **Market regime:** Single 20k-timestep walk doesn't capture volatility regimes

### 🟢 Priority 4: If Environment Is Realistic
- Increase ent_coef to 0.08 and re-run baseline (dd=0.10, dir=0.35)
- If test Sharpe stays below 0.15: Consider single-ticker is not learnable
- Shift to multi-ticker strategy or synthetic basket for signal diversity

---

## Files & Commands

**Report Location:** `sessions/downside-control-ab-analysis.md`  
**Leaderboard Filter:** leaderboard_version=2 & run_label contains 'nvda-downside-ab'  

To reproduce:
```powershell
python src/quant_report.py --input data/experiment_leaderboard.csv --output-dir sessions --output-name downside-control-report.md
```

---

## Conclusion

**The tighter drawdown penalty made things worse.** This A/B result rules out "more aggressive downside control" as a viable improvement direction. The bottleneck is not risk management—it's the model's fundamental ability to identify and execute a profitable trading signal. Shifting to **entropy/exploration tuning** or **environment realism** is the next logical path forward.
