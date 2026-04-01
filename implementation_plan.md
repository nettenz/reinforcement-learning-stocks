# Implementation Plan - Optimization Handoff

Updated: 2026-04-01

Purpose: provide a reality-based optimization handoff so a custom agent can run, evaluate, and iterate SAC experiments safely and efficiently.

## 1) Current State (Codebase Reality)

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
- Improve out-of-sample quality, not just validation ranking.

Optimization scorecard (priority order):
1. Maximize `test_actionable_accuracy`.
2. Maximize `test_trade_win_rate`.
3. Keep `test_alpha_vs_qqq >= 0` where possible.
4. Keep generalization gap small:
   - `abs(val_actionable_accuracy - test_actionable_accuracy) <= 0.05`.
5. Minimize instability:
   - `test_return_cv_by_config < 1.0`.

Tie-breakers:
- Higher `test_sharpe_ratio`.
- Lower absolute `test_max_drawdown`.
- Shorter `run_duration_seconds` for equivalent quality.

## 3) Guardrails and Promotion Policy

A run/config is promotion-eligible only if all pass:
1. `test_actionable_accuracy >= 0.53`
2. `test_trade_win_rate >= 0.52`
3. `test_alpha_vs_qqq >= 0.00`
4. `abs(val_actionable_accuracy - test_actionable_accuracy) <= 0.05`
5. `test_return_cv_by_config < 1.0`

If no config passes all gates, promote none and run another focused sweep.

## 4) Recommended Iteration Workflow

### Phase A: Baseline Lock
- Run a compact baseline sweep (2-3 seeds, limited timesteps) with current defaults.
- Save as a labeled snapshot (`--run-label baseline-lock`).
- Compute baseline medians for test metrics and gap/cv risk.

### Phase B: Coarse Sweep (High-Leverage Knobs)
- Sweep these first:
  - `reward_mode`: `sharpe` vs `sortino`
  - `ent_coef`: broaden around `0.02, 0.05`
  - `timesteps`: compare shorter vs longer (`20000` vs `40000`)
- Keep all other parameters fixed.
- Goal: identify 2-3 regimes worth deeper search.

### Phase C: Focused Local Search
- For top regimes, run multi-seed confirmations.
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

## 5) Concrete Command Templates (Windows)

Baseline smoke:

```powershell
.\.venv\Scripts\python.exe src\experiments.py --include-news --use-stationary-features --seeds 7,13 --timesteps 20000 --learning-rates 0.0003 --gammas 0.99 --ent-coefs 0.02,0.05 --reward-mode sharpe --rolling-reward-window 100 --max-runs 4 --append --run-label baseline-lock
```

Coarse reward-mode comparison:

```powershell
.\.venv\Scripts\python.exe src\experiments.py --include-news --use-stationary-features --seeds 7,13,21 --timesteps 20000,40000 --learning-rates 0.0003 --gammas 0.99 --ent-coefs 0.02,0.05 --reward-mode sortino --rolling-reward-window 100 --append --run-label coarse-sortino
```

Focused confirmation pass:

```powershell
.\.venv\Scripts\python.exe src\experiments.py --include-news --use-stationary-features --seeds 7,13,21,42,84 --timesteps 20000,40000 --learning-rates 0.0003,0.0001 --gammas 0.99,0.995 --ent-coefs 0.02,0.05 --threshold 0.002 --horizon 1 --transaction-cost-rate 0.001 --trade-penalty 0.05 --reward-mode sharpe --reward-return-scale 1.0 --reward-direction-scale 0.35 --reward-hold-penalty-scale 0.10 --reward-drawdown-penalty-scale 0.10 --reward-action-bonus-scale 0.02 --reward-clip 1.0 --reward-ignore-transaction-cost --append --run-label focused-confirm
```

## 6) Handoff Checklist (For Every Optimization Session)

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

## 7) Custom Agent Instruction Seed (Copy/Paste Template)

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

## 8) Definition of Done for This Plan

This handoff plan is complete when a custom optimization agent can:
1. Decide what to sweep next from current metrics.
2. Execute reproducible commands.
3. Reject false-positive improvements.
4. Recommend only gate-compliant promotions.
5. Produce a compact evidence summary for human review.
