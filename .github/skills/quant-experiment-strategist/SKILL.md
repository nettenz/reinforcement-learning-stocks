---
name: quant-experiment-strategist
description: 'Design tightly scoped experiment batches for RL follow-up work after the research question has already been identified. Use to isolate variables, define controls, set success criteria, and produce execution-ready sweep commands. Adapted for SAC multi-seed sweep workflow with 6-gate promotion framework and max_weight_delta structural fix.'
argument-hint: 'What validated research question, failure mode, or follow-up hypothesis should be turned into an experiment batch? (e.g. AAPL post-audit sweep, AMD env-fit diagnosis, stationary feature validation)'
user-invocable: true
---

# Quant Experiment Strategist

Turn a validated research question into a controlled experiment batch.

## Objective
Design the next batch of experiments so the maximum amount can be learned with the minimum compute and noise.

## Project Context (read before designing)
- **Algorithm:** SAC only. PPO deprecated.
- **Standard sweep template:**
  ```powershell
  .\.venv\Scripts\python.exe src\experiments.py `
      --ticker <ticker> `
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
- **Non-negotiable flags:** `--max-weight-delta-per-step 0.10`, `--use-stationary-features`, `--append`, minimum 5 seeds.
- **Post-sweep evaluation:** Always `python scripts/evaluate_sweep.py --leaderboard data/experiment_leaderboard.csv --label <label>`.
- **Promotion pipeline (in order):** evaluate_sweep.py → sanity_scan.py → generate_ensemble_config.py (verify seeds manually) → run_exp9_walkforward.py (update TICKER_CONFIG first).
- **6 promotion gates required.** Gate 6 = `test_trade_rate ∈ [0.40, 0.80]`. Without Gate 6, degenerate always-long passes.
- **CV stability requires ≥ 5 seeds.** CV > 1.0 with 3–4 seeds is a seed count artifact, not structural instability.
- **Ticker status:** NVDA promoted (seeds 13,21,42,7). AAPL blocked (leakage audit first). AMD blocked (CV 4.5+, env fit issue).
- **Known failure modes:**
  - Overtrade (99%+ rate): `max_weight_delta_per_step=0.0` → fix the cap, not the reward
  - Degenerate always-long: high accuracy + bullish test period → Gate 6 catches this
  - CV instability: < 5 seeds → add seeds, not reward changes
  - Seed collapse: some seeds score 0.0/0.0 → expected, filter with `filter_active_seeds`

## Use this skill when
- The next research question is already known
- A follow-up batch needs to be designed
- A ticker needs its first baseline sweep
- A gate failure needs focused diagnosis
- A stationary vs raw feature comparison is needed

## Do not use this skill when
- The main problem is still figuring out what happened (use `strategy-refinement-analyst` first)
- AAPL leakage audit has not been completed (use audit checklist first)
- AMD CV root cause is still unknown

## Core Procedure

### 1. Restate the exact research question
Convert the handoff into one explicit question. Examples:
- Does AAPL pass 6/6 gates post leakage audit?
- Does AMD CV stabilize with a different reward config?
- Does increasing timesteps to 60k help stationary feature convergence?

### 2. Choose the minimum informative batch
Design the smallest clean batch that answers the question.

**Default batch size guidance:**
- Baseline sweep: 2 ent_coefs × 5 seeds = 10 runs
- Variable isolation: fix all but one parameter, 10 runs max
- Timestep comparison: 2–3 timestep values × 5 seeds = 10–15 runs
- Never run > 20 runs without justification

### 3. Define the experiment structure
For each experiment specify:
- goal
- exact variable(s) being changed
- exact variables held constant (always include max_weight_delta, use_stationary_features, seeds)
- evaluation artifacts to inspect

### 4. Define success and failure interpretation

**Universal success criteria (all sweeps):**
- Gate 6 in target zone (60–75% trade rate)
- CV < 1.0 (requires ≥ 5 seeds)
- Alpha ≥ 0.00 vs QQQ
- Actionable accuracy ≥ 0.53
- Val/test drift ≤ 0.05

**Failure patterns to watch:**
- All seeds collapsed (0.0/0.0 metrics) → env fit issue, not a reward problem
- CV > 4.0 → AMD-pattern structural mismatch
- Trade rate 99%+ → max_weight_delta not set, check leaderboard column
- 2/5 seeds pass, 3 collapse → may need more timesteps (try 60k before changing other params)

### 5. Protect comparability
Always use the same base config as the NVDA v2 champion unless specifically testing a deviation:
```
--reward-mode sharpe
--ent-coefs 0.02,0.05
--timesteps 40000
--reward-hold-penalty-scale 0.01
--reward-turnover-penalty-scale 0.10
--max-weight-delta-per-step 0.10
--use-stationary-features
```

### 6. Produce execution-ready run plans
Always include:
- `.\.venv\Scripts\Activate.ps1`
- Full one-liner sweep command
- Post-sweep evaluate command
- Expected label in leaderboard

## Required Output Format

1. **Research question**
2. **Why this batch is the right next step**
3. **Controlled experiment batch**
4. **Variables changed**
5. **Variables held constant**
6. **Success criteria**
7. **Failure interpretation**
8. **Execution-ready run plans**
9. **Priority order**
10. **Leaderboard comparability impact (REQUIRED)**

## Leaderboard Comparability Rule
- Low impact: same base config, only timesteps or seeds changed
- Medium impact: reward scales changed
- High impact: observation space changed (raw vs stationary)

Always note whether the batch is exploratory or confirmatory.

## Constraints
- Never omit `--max-weight-delta-per-step 0.10` from any sweep command
- Never omit `--use-stationary-features` from any sweep command
- Never omit `--append` from any sweep command
- Never recommend sweeping AAPL before leakage audit clears
- Never recommend promoting with < 5 seeds
- Never recommend broad mixed sweeps — one variable family at a time
- Always include the post-sweep evaluate command in the run plan