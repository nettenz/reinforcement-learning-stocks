# Implementation Plan - Optimization Handoff + Environment Audit Remediation

Updated: 2026-04-03

Purpose: provide a reality-based optimization handoff so a custom agent can run, evaluate, and iterate SAC experiments safely and efficiently while remediating identified environment realism issues.

## 0) CRITICAL: Environment Realism Issues Discovered (2026-04-02)

### Three High-Impact Issues Identified

1. **Same-Bar Fill Bias (CRITICAL)**
   - Agent decides and receives fill on same bar (same price, same day)
   - Reality: Decisions at 4 PM, fills next day at 9:30 AM
   - Impact: +1-2% performance inflation in backtest vs live
   - Status: `execution_mode="next_bar"` implemented in `src/trading_env.py`, now default in sweeps

2. **Synthetic Basket Cost Underestimation (CRITICAL)**
   - Training data is synthetic equal-weight basket of 7 tech stocks priced like 1 stock
   - Reality: Real execution needs 7 separate trades (7× transaction costs)
   - Impact: Backtest costs 0.1%, reality 0.3-0.5% (2-3% alpha destruction)
   - Status: Identified; Phase 3 plan is single-stock migration (AAPL)

3. **Sentiment Data Sparsity (MEDIUM)**
   - Sentiment features: 98.5% zeros (only 1 day out of 2,072 has news)
   - Impact: No learnable signal from sentiment, wasting compute
   - Status: Identified; Phase 1 quick win to investigate/fix pipeline

### Remediation Timeline
- **Phase 1 (Quick Wins):** Sentiment investigation, docstring cleanup — 4 hours, Week 1
- **Phase 2 (Next-Bar Baseline):** Verify next-bar execution works, re-baseline 10 seeds — 8 hours, Week 2-3
- **Phase 3 (Single-Stock Migration):** Move to AAPL-only training (estimated 0-1% perf delta)

### Current Mitigation Status
- ✅ Corrupted CSV deleted
- ✅ Next-bar execution enabled in `run_sweep.ps1` and experiments
- 🔲 Phase 1 quick wins queued (sentiment investigation)
- 🔲 Phase 2/3 decision gate: only proceed if Phase 2 baseline passes (no >1.5% performance drop)

---

### Training and Sweep Pipeline
- Main optimizer entrypoint is `src/experiments.py`.
- Single-run trainer entrypoint is `src/train_bot.py`.
- Environment and reward logic are in `src/trading_env.py`.

### Reward and Objective Options (Already Implemented)
- `reward_mode` supports: `legacy`, `sharpe`, `sortino`.
- Rolling risk-adjusted reward controls exist:
  - `rolling_reward_window`
  - `reward_epsilon`
- Reward shaping controls exist:
  - `reward_return_scale`
  - `reward_direction_scale`
  - `reward_hold_penalty_scale`
  - `reward_drawdown_penalty_scale`
  - `reward_action_bonus_scale`
  - `reward_clip`
  - `reward_ignore_transaction_cost`

### Stability and Generalization Signals (Already Implemented)
- Per-run metrics: return, actionable accuracy, win rate, Sharpe/Sortino, max drawdown.
- Cross-config seed stability fields in leaderboard:
  - `test_return_mean_by_config`
  - `test_return_std_by_config`
  - `test_return_cv_by_config`
  - `high_return_cv_risk`
- Benchmark-relative metrics exist:
  - `val_alpha_vs_qqq`
  - `test_alpha_vs_qqq`

### Artifacts and Reporting (Already Implemented)
- Canonical outputs:
  - `data/experiment_leaderboard.csv`
  - `data/experiment_reward_leaderboard.csv`
  - `data/experiment_summary.json`
- Timestamped snapshots in `data/experiment_snapshots/`.
- Automated interpretation in `src/quant_report.py` and `sessions/quant-report-*.md`.

### Known Operational Constraint
- `src/experiments.py` defaults to `n_envs=8`, while dashboard-triggered runs force `n_envs=1`.
- Parallel envs can improve throughput but also increase resource pressure and variance in runtime behavior.

## 2) Optimization Objectives (What the Agent Should Optimize For)

Primary objective:
- Improve out-of-sample quality with honest (next-bar) execution.
- Do NOT promote configs that pass validation but fail test (AAPL collapse detected).

Optimization scorecard (priority order):
1. Maximize `test_actionable_accuracy` (now with next-bar fill realism).
2. Maximize `test_trade_win_rate` (measure of signal quality).
3. Keep `test_alpha_vs_qqq >= 0.00` (vs passive benchmark, currently weak).
4. Keep generalization gap small: `abs(val_actionable_accuracy - test_actionable_accuracy) <= 0.05` **← GATING (AAPL -45% failed)**.
5. Minimize instability: `test_return_cv_by_config < 1.0`.

Tie-breakers:
- Higher `test_sharpe_ratio`.
- Lower absolute `test_max_drawdown`.
- Shorter `run_duration_seconds` for equivalent quality.

## 3) Guardrails and Promotion Policy

A run/config is promotion-eligible only if all pass:
1. `test_actionable_accuracy >= 0.53` (20+ seeds in leaderboard pass this)
2. `test_trade_win_rate >= 0.52` (consistent with accuracy ~53%)
3. `test_alpha_vs_qqq >= 0.00` (weak but non-negative; current max 0.0306)
4. `abs(val_actionable_accuracy - test_actionable_accuracy) <= 0.05` **← ENFORCED (catches AAPL-style collapse)**
5. `test_return_cv_by_config < 1.0` (limits seed variance)

**Current Status (2026-04-02 Multi-Ticker):**
- 44.6% pass rate (66 of 148 runs)
- NVDA: 0.6578 max (PROMOTABLE if gate 4 passes)
- AAPL: 0.5828 validation score, BUT validation→test gap -45% (GATED OUT)
- AMD: 0.4318 max (all fail gate 1)

If no config passes all gates, promote none and run focused re-audit (see Experiment A).

## 4) Recommended Iteration Workflow (Sequential Experiments)

### Priority 1 (URGENT): Experiment A — AAPL Leakage Audit
**Goal:** Determine if -45% val→test accuracy collapse is data leakage or regime mismatch

**Design:**
- Re-run best AAPL (seed 21, timesteps 20k, ent 0.05, bonus 0.02) with diagnostic logging
- Plot decision timeseries against AAPL price chart (visual sanity check)
- Verify train/val/test date split (no lookahead)
- Check market microstructure (vol, bid-ask spread) between validation and test periods

**Hold constant:** All hyperparams, training data, reward function

**Success criteria:**
- If val/test accuracy gap closes below 10% → data issue found and fixed
- If gap persists → regime shift confirmed, document and continue

**Command:**
```powershell
.\.venv\Scripts\python.exe src\experiments.py --ticker aapl --seeds 21 --timesteps 20000 --learning-rates 0.0003 --gammas 0.99 --ent-coefs 0.05 --reward-mode sharpe --reward-action-bonus-scale 0.02 --append --run-label aapl-audit-seed21
```

### Priority 2 (HIGH): Experiment C — NVDA Lock-In (10-Seed Confirmation)
**Goal:** Validate that NVDA seed 13 config generalizes (deployment readiness check)

**Design:**
- Lock: NVDA, timesteps 20k, ent 0.02, bonus 0.08, sharpe
- Vary: seeds {34, 55, 89, 144, 233, 377, 610, 987, 1597, 2584}
- Measure: ranking_score distribution, test accuracy consistency, drawdown control

**Success criteria:**
- Mean ranking_score ≥ 0.60
- 95% CI for test accuracy includes 0.54 or higher
- Max drawdown <25% on test set
- If met → NVDA ready for deployment gate review

**Command:**
```powershell
.\.venv\Scripts\python.exe src\experiments.py --ticker nvda --seeds 34,55,89,144,233,377,610,987,1597,2584 --timesteps 20000 --learning-rates 0.0003 --gammas 0.99 --ent-coefs 0.02 --reward-mode sharpe --reward-action-bonus-scale 0.08 --append --run-label nvda-multiSeed-confirm
```

### Priority 3 (MEDIUM): Experiment B — AMD Recalibration
**Goal:** Unlock AMD by tuning for higher volatility regime

**Hypothesis:** AMD's high volatility requires different penalty scaling

**Design:**
- Ablate: trade_penalty (3 separate sweeps: 0.02, 0.05, 0.10)
- Ablate: reward_drawdown_penalty_scale ∈ {0.05, 0.15, 0.25} (within each sweep)
- Fixed: seed 7 (AMD's best seed), timesteps 20k, ent 0.02, sharpe
- Total: 3 sweeps × 3 penalty scales = 9 configs

**Success criteria:** Best config ranking_score > 0.45 (above current 0.4318 max)

**Commands (run all 3 sequentially):**

Sweep 1 (trade_penalty = 0.02):
```powershell
.\.venv\Scripts\python.exe src\experiments.py --ticker amd --seeds 7 --timesteps 20000 --learning-rates 0.0003 --gammas 0.99 --ent-coefs 0.02 --reward-mode sharpe --trade-penalty 0.02 --reward-drawdown-penalty-scale 0.05,0.15,0.25 --append --run-label amd-penalty-sweep-tp02
```

Sweep 2 (trade_penalty = 0.05):
```powershell
.\.venv\Scripts\python.exe src\experiments.py --ticker amd --seeds 7 --timesteps 20000 --learning-rates 0.0003 --gammas 0.99 --ent-coefs 0.02 --reward-mode sharpe --trade-penalty 0.05 --reward-drawdown-penalty-scale 0.05,0.15,0.25 --append --run-label amd-penalty-sweep-tp05
```

Sweep 3 (trade_penalty = 0.10):
```powershell
.\.venv\Scripts\python.exe src\experiments.py --ticker amd --seeds 7 --timesteps 20000 --learning-rates 0.0003 --gammas 0.99 --ent-coefs 0.02 --reward-mode sharpe --trade-penalty 0.10 --reward-drawdown-penalty-scale 0.05,0.15,0.25 --append --run-label amd-penalty-sweep-tp10
```

### Phase A: Baseline Lock (Post-Audit)
- After Experiment A clears AAPL, run compact baseline (2-3 seeds) with next-bar default
- Save snapshot (`--run-label baseline-post-audit`)
- Compute baseline medians for test metrics and gap/cv risk

### Phase B: Coarse Sweep (High-Leverage Knobs)
- Sweep these first (with gating enforced):
  - `reward_mode`: `sharpe` vs `sortino`
  - `ent_coef`: broaden around `0.02, 0.05`
  - `timesteps`: compare shorter vs longer (`20000` vs `40000`)
- Keep all other parameters fixed.
- Goal: identify 2-3 regimes worth deeper search.

### Phase C: Focused Local Search
- For top regimes, run multi-seed confirmations across 5+ seeds
- Tune secondary knobs:
  - `learning_rate`
  - `gamma`
  - reward shaping scales (especially hold, drawdown, action bonus)
- Reject any regime that improves val but worsens test consistency.

### Phase D: Promotion and Evidence Pack
- Apply promotion gates.
- Generate an evidence block containing:
  - exact command(s)
  - top 3 configs with metrics
  - pass/fail per gate
  - recommended next command

## 5) Command Reference

All priority experiment commands are defined in Section 4 above with full context and success criteria.

**Quick Copy-Paste References:**

Experiment A (AAPL Audit):
```powershell
.\.venv\Scripts\python.exe src\experiments.py --ticker aapl --seeds 21 --timesteps 20000 --learning-rates 0.0003 --gammas 0.99 --ent-coefs 0.05 --reward-mode sharpe --reward-action-bonus-scale 0.02 --append --run-label aapl-audit-seed21
```

Experiment C (NVDA Multi-Seed):
```powershell
.\.venv\Scripts\python.exe src\experiments.py --ticker nvda --seeds 34,55,89,144,233,377,610,987,1597,2584 --timesteps 20000 --learning-rates 0.0003 --gammas 0.99 --ent-coefs 0.02 --reward-mode sharpe --reward-action-bonus-scale 0.08 --append --run-label nvda-multiSeed-confirm
```

Experiment B (AMD Penalty Sweep - Run all 3 sequentially):
```powershell
# Sweep 1
.\.venv\Scripts\python.exe src\experiments.py --ticker amd --seeds 7 --timesteps 20000 --learning-rates 0.0003 --gammas 0.99 --ent-coefs 0.02 --reward-mode sharpe --trade-penalty 0.02 --reward-drawdown-penalty-scale 0.05,0.15,0.25 --append --run-label amd-penalty-sweep-tp02

# Sweep 2
.\.venv\Scripts\python.exe src\experiments.py --ticker amd --seeds 7 --timesteps 20000 --learning-rates 0.0003 --gammas 0.99 --ent-coefs 0.02 --reward-mode sharpe --trade-penalty 0.05 --reward-drawdown-penalty-scale 0.05,0.15,0.25 --append --run-label amd-penalty-sweep-tp05

# Sweep 3
.\.venv\Scripts\python.exe src\experiments.py --ticker amd --seeds 7 --timesteps 20000 --learning-rates 0.0003 --gammas 0.99 --ent-coefs 0.02 --reward-mode sharpe --trade-penalty 0.10 --reward-drawdown-penalty-scale 0.05,0.15,0.25 --append --run-label amd-penalty-sweep-tp10
```

## 7) Handoff Checklist (For Every Optimization Session)

1. Confirm environment health:
   - `python -m py_compile src\analytics_dashboard.py src\signal_analytics.py src\trading_env.py src\experiments.py`
   - `python tests\test_script.py`
2. Run planned sweep with explicit `--run-label`.
3. Verify output files updated in `data/` and `data/experiment_snapshots/`.
4. Validate promotion gates against top config(s).
5. Produce concise summary in `sessions/` with:
   - what changed
   - what improved
   - what regressed
   - exact next command

## 8) Custom Agent Instruction Seed (Copy/Paste Template)

Use this as the base instruction for a dedicated optimization agent:

```md
# Role
You are the Optimization Agent for this RL trading codebase.

# Mission
Run safe, evidence-driven SAC optimization cycles that improve out-of-sample performance while controlling overfit and instability.

# Required Inputs
- Current leaderboard: data/experiment_leaderboard.csv
- Recent snapshots: data/experiment_snapshots/
- Core modules: src/experiments.py, src/trading_env.py, src/train_bot.py, src/analytics_dashboard.py

# Optimization Priorities (in order)
1) test_actionable_accuracy (maximize)
2) test_trade_win_rate (maximize)
3) test_alpha_vs_qqq (must be >= 0 where possible)
4) |val_actionable_accuracy - test_actionable_accuracy| <= 0.05
5) test_return_cv_by_config < 1.0

# Hard Guardrails
- Do not claim improvements from validation-only gains.
- Do not promote configs that fail any gate.
- Keep commands reproducible and fully explicit.
- Always include run labels and append mode for traceability.

# Promotion Gates
- test_actionable_accuracy >= 0.53
- test_trade_win_rate >= 0.52
- test_alpha_vs_qqq >= 0.00
- abs(val_actionable_accuracy - test_actionable_accuracy) <= 0.05
- test_return_cv_by_config < 1.0

# Execution Loop
1. Read latest leaderboard and quantify failure mode (collapse, overfit, instability, alpha deficit).
2. Propose one focused sweep addressing that failure mode.
3. Run sweep and collect top 3 configs.
4. Evaluate each config against promotion gates.
5. Emit a handoff block with:
   - exact command run
   - metric deltas vs previous baseline
   - gate pass/fail table
   - recommended next command

# Output Format
Always end with:
- Best config summary (single line)
- Gate evaluation table
- Next command (single copy/paste command)
```

## 9) Definition of Done for This Plan

This handoff plan is complete when a custom optimization agent can:
1. Decide what to sweep next from current metrics.
2. Execute reproducible commands.
3. Reject false-positive improvements.
4. Recommend only gate-compliant promotions.
5. Produce a compact evidence summary for human review.
