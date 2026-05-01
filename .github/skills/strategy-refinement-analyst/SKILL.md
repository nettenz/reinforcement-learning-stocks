---
name: strategy-refinement-analyst
description: 'Evaluate completed SAC sweep results to determine what is robust, what failed to generalize, and whether to proceed to promotion or run a follow-up batch. Adapted for 6-gate promotion framework, max_weight_delta structural fix, and current ticker status (NVDA promoted, AAPL/AMD blocked).'
argument-hint: 'What completed sweep, leaderboard label, or gate output should be evaluated? (e.g. sweep_amd_baseline_v1, AAPL post-audit sweep, stationary v3 results)'
user-invocable: true
---

# Strategy Refinement Analyst

Evaluate completed SAC sweep results and decide the next step.

## Objective
Identify which findings are real, robust, and worth promoting. Determine the dominant failure mode and route to the correct next action.

## Project Context (read before evaluating)
- **Evaluation tool:** `scripts/evaluate_sweep.py --leaderboard data/experiment_leaderboard.csv --label <label>`
- **6 promotion gates required.** A "champion" with 5/6 gates is not a champion.
- **Gate 6 = `test_trade_rate ∈ [0.40, 0.80]`.** Without this, degenerate always-long passes Gates 1–5.
- **CV requires ≥ 5 seeds.** CV > 1.0 with 3–4 seeds is a seed artifact — add seeds before acting.
- **NVDA reference champion** (sweep_overtrade_fix_nvda_maxdelta_v2):
  - Sharpe: 1.64, Alpha: 0.514, Accuracy: 56.5%, Trade rate: 62.3%, CV: 0.8926
  - Seeds: 13, 21, 42, 7 — all 6/6 gates
- **Ticker status:** NVDA promoted. AAPL blocked (leakage audit). AMD blocked (CV 4.5+, env fit).
- **Known failure modes by pattern:**

| Pattern | Classification | Route |
|---------|---------------|-------|
| Trade rate 99%+, `max_weight_delta=0.0` | Structural cap bug | Fix cap, re-sweep |
| 18/54 champions, all same trade rate | Degenerate always-long, Gate 6 missing | Add Gate 6, re-evaluate |
| CV > 4.0 across all seeds | Env fit issue (AMD pattern) | Env investigation, not reward tuning |
| CV > 1.0 with 3–4 seeds | Seed count artifact | Re-run with 5 seeds |
| 2/5 seeds pass, 3 collapse | Underfitting | Try 60k timesteps |
| Val accuracy >> test accuracy, drift > 0.10 | Leakage or regime collapse | Audit checklist before sweep |
| `accuracy=1.0, win_rate=1.0, trade_rate≈0` | Collapsed degenerate seed | Filter, do not promote |

## Default Inputs
- `data/experiment_leaderboard.csv` — filter by `run_label`
- Output of `scripts/evaluate_sweep.py`
- `data/experiment_snapshots/` — per-seed model artifacts
- Prior sweep labels for comparison

## Core Procedure

### 1. Confirm Gate 6 is active
Before evaluating any results, verify evaluate_sweep.py has Gate 6. If the output shows "Configs with 5/5 gates" instead of "6/6", Gate 6 is missing.

### 2. Confirm `max_weight_delta` was set
```python
import pandas as pd
lb = pd.read_csv('data/experiment_leaderboard.csv')
sweep = lb[lb['run_label'].str.contains('your_label', na=False)]
print(sweep['max_weight_delta_per_step'].value_counts())
```
If `0.0` → structural bug invalidates all results. Do not evaluate further — fix and re-sweep.

### 3. Evaluate the trade rate distribution
From evaluate_sweep.py output:
- Target zone (60–75%): should contain most configs
- Overtrade (>75%): if dominant → cap may not be effective
- Under-trade (<60%): if dominant → cap + penalty combination too restrictive

### 4. Evaluate generalization
Compare val vs test:
- Accuracy drift threshold: ≤ 0.05
- Drift > 0.10 → leakage or regime collapse (AAPL pattern)
- Sharpe gap val→test is expected but should not be >2x

### 5. Evaluate stability
- CV < 1.0 with ≥ 5 seeds → stable
- CV 1.0–2.0 with 5 seeds → marginal, proceed with caution
- CV > 4.0 → env fit issue (AMD), do not attempt reward tuning

### 6. Identify robust configurations
A promotable config must:
- Pass all 6 gates
- Have trade rate in 60–75% band
- Be supported by ≥ 2 seeds (ideally 4)
- Have alpha > 0.05 (not just barely positive)
- Show val/test drift ≤ 0.05

Do not promote on a single seed or borderline alpha (0.001).

### 7. Classify the dominant failure mode and route

| Failure | Route |
|---------|-------|
| Structural cap missing | Fix cap, re-sweep (no skill needed) |
| Gate 6 missing | Add Gate 6 to evaluate_sweep.py, re-evaluate |
| CV instability (seed count) | Re-sweep with 5 seeds |
| CV instability (structural) | `reward-architect` or env investigation |
| Leakage suspected | `backtest-auditor` |
| Underfitting (seed collapse) | `quant-experiment-strategist` (increase timesteps) |
| All gates green, thin ensemble | Proceed to promotion pipeline |
| All gates green, strong ensemble | Proceed to promotion pipeline |

## Promotion Pipeline Decision
If champion found (6/6 gates, ≥ 2 clean seeds, strong alpha):
```
1. python scripts/sanity_scan.py
2. python scripts/generate_ensemble_config.py --leaderboard data/experiment_leaderboard.csv --ticker <TICKER> --label <label>
3. Manually verify staging/models/ensemble_config.json seeds match champions
4. python scripts/run_exp9_walkforward.py --ticker <ticker>  (update TICKER_CONFIG first)
```

**Warning:** `generate_ensemble_config.py` label filter is unreliable — always manually verify JSON seeds.

## Required Output Format

1. **Gate 6 active confirmation**
2. **Cap verification result**
3. **Batch verdict** (Promotable / Follow-up needed / Blocked / Invalid)
4. **Trade rate distribution assessment**
5. **What passed and is robust**
6. **What failed or did not generalize**
7. **Best configuration summary**
8. **Dominant failure mode**
9. **Comparison to NVDA reference champion** (where applicable)
10. **Recommended next action**
11. **Execution-ready commands** (promotion pipeline or follow-up sweep)
12. **Leaderboard comparability impact (REQUIRED)**

## Batch Verdict Classifications
- **Promotable:** Champion found, 6/6 gates, ≥ 2 clean seeds, proceed to promotion pipeline
- **Follow-up needed:** Near-miss, specific blocker identified, targeted fix available
- **Blocked:** Structural issue (leakage, env fit, cap missing) — do not sweep further until resolved
- **Invalid:** Gate 6 missing or cap was 0.0 — results not trustworthy, re-run required

## Constraints
- Never classify a 5/6 result as a champion
- Never promote with < 5 seeds (CV instability)
- Never recommend reward tuning when cap is 0.0
- Never recommend AAPL sweeps before leakage audit clears
- Never trust generate_ensemble_config.py output without manual seed verification
- Do not treat AMD CV > 4.0 as a reward problem without env fit investigation first
- Always compare against NVDA reference metrics when evaluating a new ticker