# Quick Reference Card — RL Trading System

**Last updated:** 2026-04-30  
**Current phase:** Stationary feature validation (NVDA) → Exp 10 → Cross-ticker expansion

---

## Standard Sweep Command (NVDA Template)

```powershell
.\.venv\Scripts\python.exe src\experiments.py `
    --ticker nvda `
    --reward-mode sharpe `
    --ent-coefs 0.02,0.05 `
    --timesteps 40000 `
    --seeds 3,7,13,21,42 `
    --execution-mode next_bar `
    --reward-hold-penalty-scale 0.01 `
    --reward-turnover-penalty-scale 0.10 `
    --max-weight-delta-per-step 0.10 `
    --use-stationary-features `
    --run-label "your_label_here" `
    --append
```

**Critical flags:**
- `--max-weight-delta-per-step 0.10` — always include. Without this, agent overtraded at 99.5% rate.
- `--use-stationary-features` — always include. Raw 10-feature space is deprecated.
- `--append` — always include. Omitting this overwrites the leaderboard.
- Minimum 5 seeds — CV gate requires enough seeds to produce a stable estimate.

---

## Post-Sweep Evaluation

```powershell
# Evaluate a specific sweep
python scripts/evaluate_sweep.py --leaderboard data/experiment_leaderboard.csv --label your_label_here

# With auto-promote on champion found
python scripts/evaluate_sweep.py --leaderboard data/experiment_leaderboard.csv --label your_label_here --promote
```

**What to look for:**
- Trade rate distribution — target zone (60–75%) should have most configs
- CV gate — needs ≥ 5 seeds to stabilize below 1.0
- Champion identified with all 6 gates green before proceeding to promotion steps

---

## Promotion Pipeline (run in order, only after champion found)

```powershell
# 1. Sanity scan (cleanup — does not accept --leaderboard flag)
python scripts/sanity_scan.py

# 2. Regenerate ensemble config (verify output seeds match champions)
python scripts/generate_ensemble_config.py --leaderboard data/experiment_leaderboard.csv --ticker NVDA --label your_label_here

# 3. Verify config was written correctly
cat staging/models/ensemble_config.json

# 4. Walk-forward validation (update TICKER_CONFIG seeds in script first)
python scripts/run_exp9_walkforward.py --ticker nvda
```

**Warning:** `generate_ensemble_config.py` label filtering may not work reliably. Always verify that the seeds in the JSON match your champion seeds before proceeding to Exp 9.

---

## Promotion Gates (6/6 required)

| Gate | Metric | Threshold | Notes |
|------|--------|-----------|-------|
| 1 | `test_actionable_accuracy` | ≥ 0.53 | |
| 2 | `test_trade_win_rate` | ≥ 0.52 | |
| 3 | `test_alpha_vs_qqq` | ≥ 0.00 | Previously blocked by overtrade drag |
| 4 | `\|val_acc - test_acc\|` | ≤ 0.05 | |
| 5 | `test_return_cv_by_config` | < 1.0 | Requires ≥ 5 seeds |
| 6 | `test_trade_rate` | ∈ [0.40, 0.80] | Blocks degenerate always-long policies |

---

## Exp 9 Walk-Forward Gates (3/3 required)

| Gate | Metric | Threshold |
|------|--------|-----------|
| G1 | `ensemble_acc >= min_seed_acc - 0.5%` | Ensemble must not degrade vs worst individual seed |
| G2 | `majority_agreement_rate` | ≥ 0.60 |
| G3 | `unanimous_rate (high_conf)` | ≥ 0.20 |

**Before running Exp 9:** Update `TICKER_CONFIG` in `scripts/run_exp9_walkforward.py` to point to the correct leaderboard and champion seeds for the ticker being validated.

---

## Diagnosing Sweep Problems

| Symptom | Diagnosis | Fix |
|---------|-----------|-----|
| Trade rate 99%+ despite penalty tuning | `max_weight_delta_per_step=0.0` — cap not set | Add `--max-weight-delta-per-step 0.10` |
| Trade rate < 40% | Over-constrained — cap + penalty both suppressing | Drop turnover penalty to 0.01, keep cap |
| CV > 1.0 | Too few seeds for stable estimate | Run with ≥ 5 seeds |
| Alpha fails, accuracy passes | Regime-dependent alpha (overtrade or always-long) | Check trade rate — Gate 6 should catch this |
| 18 champions from 54 configs, all same trade rate | Degenerate always-long — Gate 6 was missing | Add Gate 6, rerun evaluate_sweep.py |
| Duplicate seed rows in leaderboard | `load_top_n_models` pulling same seed multiple times | Fixed in `src/ensemble.py` via `drop_duplicates(subset=["seed"])` |
| `generate_ensemble_config.py` writes wrong seeds | Label filter not working | Manually write `staging/models/ensemble_config.json` |

---

## Key Metrics Snippet

```python
import pandas as pd

lb = pd.read_csv('data/experiment_leaderboard.csv')
label = 'your_label_here'
sweep = lb[lb['run_label'].str.contains(label, na=False)]

print(f"Rows: {len(sweep)}")
print(f"Acc  (mean/std): {sweep['test_actionable_accuracy'].mean():.3f} ± {sweep['test_actionable_accuracy'].std():.3f}")
print(f"CV   (mean):     {sweep['test_return_cv_by_config'].mean():.3f}")
print(f"Alpha(mean):     {sweep['test_alpha_vs_qqq'].mean():.4f}")
print(f"Sharpe(mean):    {sweep['test_sharpe_ratio'].mean():.3f}")
print(f"Trade rate(med): {sweep['test_trade_rate'].median():.1%}")
print(f"Gates 6/6:       {(sweep['test_trade_rate'].between(0.40, 0.80)).sum()} configs in trade rate range")
```

---

## NVDA Champion Reference (sweep_overtrade_fix_nvda_maxdelta_v2)

| Metric | Value |
|--------|-------|
| Seeds promoted | 13, 21, 42, 7 |
| Sharpe | 1.64 |
| Alpha vs QQQ | 0.514 |
| Actionable Accuracy | 56.5% |
| Trade Win Rate | 54.9% |
| Val/Test Drift | 0.0073 |
| CV (cross-seed) | 0.8926 |
| Trade Rate | 62.3% |
| `max_weight_delta_per_step` | 0.10 |
| `use_stationary_features` | False ← upgrading via stationary sweep |

---

## Ticker Status

| Ticker | Status | Next Action |
|--------|--------|-------------|
| NVDA | ✅ Promoted | Stationary sweep in progress → Exp 10 |
| AAPL | ❌ Blocked | Leakage audit first |
| AMD | ❌ Blocked | Environment fit investigation first |

---

## Common Pitfalls

- **Never promote without Gate 6** — a bullish test period can make an always-long agent look like a champion on Gates 1–5
- **Never run Exp 9 before verifying loaded seeds** — check `Loaded seeds:` in output matches your champion seeds
- **Never use `sanity_scan.py --leaderboard`** — that flag doesn't exist; it operates on results directory
- **Always deduplicate before a new sweep** — stale duplicate rows inflate CV estimates and corrupt gate counts
- **Raw features for now** — Stationary features are deferred until after Exp 10. Use `--use-stationary-features False` (default) for current production-aligned sweeps.