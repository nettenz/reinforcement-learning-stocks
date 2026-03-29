# Gemini CLI Delegation — Accuracy Optimization

## Mission
Improve RL model **actionable accuracy** and **stability across seeds** for this repository.

Primary objective:
- Maximize `test_actionable_accuracy` without sacrificing `test_trade_win_rate` and `test_cumulative_signal_return`.

Secondary objective:
- Reduce cross-seed collapse/variance.

---

## Repository context
- Project root: `D:\code\agentic-development\reinforcement-learning-stocks`
- Core files:
  - `src\trading_env.py`
  - `src\experiments.py`
  - `src\signal_analytics.py`
  - `src\analytics_dashboard.py`
- Recent session context:
  - `sessions\session-2026-03-29-c.md`

Recent reward-fix already applied:
- In `trading_env.py`, directional reward + action bonus only apply when a trade executes.
- Invalid Buy/Sell attempts are treated like Hold for reward shaping.

---

## Current baseline snapshots
Use these as the immediate comparison baseline:

- Post-fix bonus `0.02`:
  - `data\experiment_snapshots\experiment_leaderboard_20260329-075808Z_win-20k-bonus-0p02-postfix.csv`
- Post-fix bonus `0.05`:
  - `data\experiment_snapshots\experiment_leaderboard_20260329-075929Z_win-20k-bonus-0p05-postfix-ab.csv`

Known A/B mean delta (`0.05 - 0.02`, seeds `7,13,21,34,55`):
- `val_actionable_accuracy`: `+0.007547`
- `test_actionable_accuracy`: `+0.000000`
- `val_trade_win_rate`: `+0.013592`
- `test_trade_win_rate`: `-0.001935`
- `val_cumulative_signal_return`: `+0.059229`
- `test_cumulative_signal_return`: `+0.059168`
- `ranking_score`: `+0.019697`

Interpretation: `0.05` helps validation/returns but test actionable is tied; stability is mixed.

---

## Constraints and guardrails
1. Do **not** break existing scripts, dashboard, or data pipelines.
2. Keep code changes surgical and focused on accuracy.
3. Preserve cross-platform behavior (Windows + macOS/Linux).
4. Any behavior-changing code update must be validated with:
   - `python tests\test_script.py`
   - At least one experiment smoke run.
5. Do not remove existing snapshot history files.

---

## Required workflow

### Phase 1 — Reproduce and characterize
1. Run controlled 20k experiments for both bonus settings with the existing seeds:
   - `7,13,21,34,55`
2. Add replication seeds:
   - `89,144,233`
3. Compute for each config:
   - mean, std, min, max for:
     - `val_actionable_accuracy`
     - `test_actionable_accuracy`
     - `val_trade_win_rate`
     - `test_trade_win_rate`
     - `val_cumulative_signal_return`
     - `test_cumulative_signal_return`

### Phase 2 — Improve accuracy
Explore a **small, controlled** set of changes with clear hypotheses:

1. Reward shaping (preferred first):
   - tune `reward_direction_scale`
   - tune `reward_hold_penalty_scale`
   - tune `reward_drawdown_penalty_scale`
   - keep action-bonus comparison (`0.02` vs `0.05`)

2. Training robustness:
   - verify whether `timesteps 20k vs 30k` improves test metrics consistently
   - avoid broad sweeps; use focused candidate runs

3. Evaluation robustness:
   - ensure no metric inflation due to invalid actions
   - verify seed-level consistency (not just top-1 seed)

### Phase 3 — Select winner
Use this tie-break order:
1. Highest mean `test_actionable_accuracy`
2. Then highest mean `test_trade_win_rate`
3. Then highest mean `test_cumulative_signal_return`
4. Then lowest std of `test_actionable_accuracy`

---

## Commands you can use

### Baseline-style 20k run (example)
```powershell
python src\experiments.py --include-news --seeds 7,13,21,34,55 --timesteps 20000 --learning-rates 0.0003 --gammas 0.99 --ent-coefs 0.01 --reward-action-bonus-scale 0.05 --max-runs 5 --run-label gemini-20k-b05
```

### Extended seed run (replication)
```powershell
python src\experiments.py --include-news --seeds 7,13,21,34,55,89,144,233 --timesteps 20000 --learning-rates 0.0003 --gammas 0.99 --ent-coefs 0.01 --reward-action-bonus-scale 0.05 --max-runs 8 --run-label gemini-20k-b05-repl
```

### Smoke validation
```powershell
python tests\test_script.py
```

---

## Deliverables (must provide all)
1. Updated code (if any) with concise rationale for each change.
2. New snapshot files under `data\experiment_snapshots\`.
3. A short results summary including:
   - best config
   - metric table (means/std across seeds)
   - why winner was selected
4. Recommended default runtime config for next production run.
5. Explicit “what to run next” command list (3–5 commands max).

---

## Success criteria
A handoff is successful only if:
1. `test_actionable_accuracy` improves **meaningfully and consistently** across seeds, or
2. If tied, winner shows better stability and/or better trade-win/return profile with evidence.

If no config wins robustly, return a “no clear winner” conclusion with the most promising two candidates and a minimal next experiment plan.
