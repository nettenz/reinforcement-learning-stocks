---
name: quant-experiment-strategist
description: >
  Design tightly scoped experiment batches for RL-based stock trading follow-up work after
  the research question has already been identified. Use to isolate variables, define controls,
  set success criteria, and produce execution-ready sweep commands. Adapted for the Binary PPO
  gold-standard architecture with 6-gate promotion framework. Trigger this skill whenever the
  user asks to plan, design, or scope an experiment sweep, a hyperparameter search, a new ticker
  baseline, a gate failure diagnosis, or any follow-up RL training batch — even if phrased
  informally ("what should I run next?", "AAPL sweep plan", "what's the next experiment?").
  Also trigger when comparing Binary PPO vs SAC retrofits, designing ablation batches, or
  scoping cross-ticker validation runs.
---

# Quant Experiment Strategist

Turn a validated research question into a controlled, execution-ready experiment batch.

## Objective
Design the next batch of experiments so the maximum information is extracted with the minimum compute and noise. Every output from this skill must include an execution-ready run plan — no partial designs.

---

## Architecture Ground Truth (read before designing anything)

**Current gold standard:** Binary PPO — `--binary-actions` + `--min-hold-bars 3`  
**SAC status:** Legacy. NVDA and AMD champions were trained on SAC; both flagged for Binary PPO retrofit.  
**DO NOT design SAC sweeps** unless the explicit goal is a head-to-head comparison against an existing SAC champion for retrofit validation.

### Why Binary PPO is the Gold Standard
PPO + `--binary-actions` (long/flat only, no continuous sizing) + `--min-hold-bars 3` solves two core failure modes that killed SAC on mega-caps:
- **Whipsaw noise:** Continuous SAC traded every bar; transaction cost leakage collapsed returns.
- **Inaction bias (Sortino-trained SAC):** Model learned "do nothing" was safer. Binary hold constraint breaks this.

GOOGL (+0.66 alpha), AMZN (+0.11), MU (+0.15) all revived exclusively via this switch.

---

## Pipeline Architecture (critical — read before designing any experiment)

```
experiments.py (sweep)
    → evaluate_sweep.py (cross-seed gate evaluation)
    → sanity_scan.py
    → generate_ensemble_config.py (verify seeds manually)
    → run_exp9_walkforward.py (walkforward confirmation — post-promotion only)
```

**`experiments.py` is the sweep entry point** for all training runs, both SAC and PPO.  
**`run_exp9_walkforward.py` is NOT a sweep runner.** It is a walkforward confirmation step executed after a champion is promoted through all 6 gates. Do not reference it in sweep run plans.

---

## Standard Sweep Template (Binary PPO)

```powershell
# Activate venv first
.\.venv\Scripts\Activate.ps1

.\.venv\Scripts\python.exe src\experiments.py `
    --ticker <TICKER> `
    --reward-mode sharpe `
    --ent-coefs 0.01,0.02,0.05 `
    --timesteps 50000 `
    --seeds 3,7,13,21,42 `
    --execution-mode next_bar `
    --binary-actions `
    --min-hold-bars 3 `
    --max-weight-delta-per-step 0.10 `
    --use-stationary-features `
    --n-envs 4 `
    --run-label "<sweep_label>" `
    --append
```

**Non-negotiable flags:**

| Flag | Value | Reason |
|---|---|---|
| `--binary-actions` | (flag) | Enables long/flat discrete action space — core Binary PPO constraint |
| `--min-hold-bars` | `3` | Minimum cooldown between flips; prevents whipsaw |
| `--max-weight-delta-per-step` | `0.10` | Position size cap; removing causes 99%+ trade rate |
| `--use-stationary-features` | (flag) | All new sweeps use 27-feature stationary obs space |
| `--append` | (flag) | Never overwrite leaderboard |
| `--seeds` | ≥ 5 seeds | CV is meaningless below 5 seeds |

**`--n-envs` guidance:** Default in `experiments.py` is 8 (SubprocVecEnv). Use `--n-envs 4` as a safe default. Use `--n-envs 1` (DummyVecEnv, single process) as an emergency workaround if sweeps crash mid-run with "Too many open files". Always be explicit — never rely on the default.

**Post-sweep evaluation (always run after every sweep):**
```powershell
python scripts/evaluate_sweep.py --leaderboard data/experiment_leaderboard.csv --label <sweep_label>
```

---

## Ticker Status Reference

| Ticker | Status | Architecture | Alpha vs QQQ | Notes |
|--------|--------|--------------|--------------|-------|
| NVDA | Promoted | SAC → PPO Retrofit pending | +0.41 | Seeds 7, 13; raw 10-feature obs |
| AMD | Promoted | SAC → PPO Retrofit pending | +1.37 | Seeds 7, 13; stationary 27-feature |
| GOOGL | Promoted | Binary PPO | +0.66 | Seed 13 |
| AMZN | Promoted | Binary PPO | +0.11 | Stage 1 v2 |
| MU | Promoted | Binary PPO | +0.15 | Stage 1 v2 |
| AAPL | Re-screening | Binary PPO | — | Pending; was blocked on leakage audit |
| ALAB | Future | XGB/RF | — | Re-screen mid-2027 (~1500+ rows) |

**NVDA/AMD SAC note:** Both champions pass all gates and remain in the ensemble. Retrofit is stabilization, not emergency replacement.

---

## 6-Gate Promotion Framework

All 6 gates required for promotion. Primary evaluation tool: `evaluate_sweep.py` (cross-seed).
`experiments.py` also runs per-run gates (single seed), but those are not sufficient alone.

| Gate | Metric | Threshold | Notes |
|------|--------|-----------|-------|
| G1 | `test_actionable_accuracy` | >= 0.525 | Lowered for Binary models |
| G2 | `test_trade_win_rate` | >= 0.50 | Lowered for Binary models |
| G3 | `test_alpha_vs_qqq` | >= 0.0005 | Alpha-first |
| G4 | `|val_acc - test_acc|` | <= 0.05 | Drift check |
| G5 | `test_return_cv_by_config` (clean seeds only) | < 0.50 | Active seeds only; Sharpe > 0, trade_rate > 10% |
| G6 | `test_trade_rate` | [0.40, 1.00] | Relaxed; 90%+ OK for momentum hold regimes |

**G5 note:** CV computed over active seeds only. Collapsed seeds inflate raw CV. `evaluate_sweep.py` reports `clean_cv` — always use that, not raw CV.

**CLI gate defaults differ from evaluate_sweep thresholds.** The `--promote-min-test-actionable` etc. flags in `experiments.py` control single-run promotion only. The authoritative 6-gate check is always `evaluate_sweep.py`.

---

## Exit Signal Layer Status

`src/exit_manager.py` is **implemented**. Rules available: `confidence`, `trailing_stop`, `profit_take`, `time`, `composite`. This is not deferred — it is ready for backtesting integration. Next step: backtest on NVDA test split before enabling in dashboard. See `EXIT_SIGNAL_TODO.md`.

---

## Core Design Procedure

### Step 1 — Restate the research question precisely
Convert the handoff into one explicit, falsifiable question. Examples:
- "Does AAPL pass 6/6 gates under Binary PPO with stationary features?"
- "Does raising `ent_coef` to 0.10 recover NVDA trade rate collapse in PPO retrofit?"
- "Does `--min-hold-bars 5` vs `3` improve G5 CV for AAPL?"

### Step 2 — Choose the minimum informative batch

| Scenario | Batch size |
|---|---|
| New ticker baseline | 3 ent_coefs x 5 seeds = 15 runs |
| Variable isolation | Fix all but 1 param, 10 runs max |
| Timestep comparison | 2-3 values x 5 seeds = 10-15 runs |
| Retrofit head-to-head | PPO vs SAC champion, 5 seeds each = 10 runs |

Never run >20 runs without written justification. If you want >20 runs, the hypothesis is too broad.

### Step 3 — Define the experiment structure
For each experiment specify:
- Goal (one sentence)
- Variable(s) being changed
- Variables held constant (always include the non-negotiable flags)
- Evaluation artifacts to inspect after the run

### Step 4 — Define success and failure interpretation

**Universal success criteria:**
- G6: trade rate in [0.40, 1.00]
- G5: clean CV < 0.50
- G3: alpha >= 0.0005 vs QQQ
- G1: actionable accuracy >= 0.525
- G4: val/test drift <= 0.05

**Known failure patterns:**

| Symptom | Root Cause | Fix |
|---|---|---|
| All seeds collapsed (0.0/0.0) | Env fit / obs space mismatch | Check `market_feature_columns`; not a reward problem |
| CV > 4.0 | Missing regime diversity in training data | Rebuild parquet from 2015; re-run |
| Trade rate 99%+ | `--max-weight-delta-per-step` missing or zero | Fix the cap; do not touch reward scales |
| Trade rate < 5% | Entropy too low or hold penalty too high | Increase `ent_coef`; reduce `hold_penalty_scale` |
| 2/5 seeds pass, 3 collapse | Insufficient timesteps | Try 60k before changing other params |
| High accuracy + bullish period + G6 fail | Degenerate always-long policy | G6 catches this; do not promote |
| Sweep crashes with "Too many open files" | SubprocVecEnv FD leak (n-envs=8 default) | Set `--n-envs 1`; see fd-leak-diagnosis.md |
| PPO retrofit lower alpha than SAC champion | Expected — PPO trades less frequently | Evaluate on stability (CV, drift), not raw alpha |

### Step 5 — Protect comparability
Declare leaderboard comparability impact for every batch:

| Impact level | When it applies |
|---|---|
| Low | Same base config; only timesteps or seeds changed |
| Medium | Reward scales or `--min-hold-bars` changed |
| High | Obs space changed (raw vs stationary); `--binary-actions` toggled |

High-impact changes create a new comparability group. Document this in the run label.

---

## Promotion Pipeline (in order)

```
1. experiments.py sweep          — generates leaderboard rows
2. evaluate_sweep.py             — cross-seed gate evaluation (authoritative)
3. sanity_scan.py                — signal integrity check
4. generate_ensemble_config.py   — verify seeds MANUALLY after generation
5. run_exp9_walkforward.py       — walkforward confirmation (post-promotion only)
```

**ensemble_config.json:** `generate_ensemble_config.py` label filter is unreliable. Always manually verify seed pins. AMD pinned to bridge-c seeds [13, 7].

**Model naming:** `experiments.py` saves champions as `sac_trading_bot_<ticker>.zip` regardless of algorithm. Legacy naming — not a bug. Do not rename.

---

## Required Output Format

Every response must include:

1. **Research question** — one explicit, falsifiable sentence
2. **Why this batch is the right next step** — 2-3 sentences connecting to current project state
3. **Controlled experiment batch** — table: name, goal, variable changed, held constant
4. **Success criteria** — gate thresholds and what passing looks like
5. **Failure interpretation** — symptom to root cause mapping
6. **Execution-ready run plans** — full PowerShell commands, no placeholders
7. **Post-sweep evaluation command**
8. **Priority order** — which run goes first and why
9. **Leaderboard comparability impact** — Low / Medium / High + justification

---

## Constraints (non-negotiable)

- Never omit `--binary-actions` from any Binary PPO sweep command
- Never omit `--min-hold-bars 3` from any Binary PPO sweep command
- Never omit `--max-weight-delta-per-step 0.10` from any sweep command
- Never omit `--use-stationary-features` from any sweep command
- Never omit `--append` from any sweep command
- Always be explicit about `--n-envs`; never rely on the default of 8 until FD leak is confirmed patched
- Never promote with < 5 seeds
- Never design SAC sweeps unless explicitly doing a retrofit head-to-head
- Never recommend broad mixed sweeps — one variable family at a time
- Never reference `run_exp9_walkforward.py` in a sweep run plan
- Always include the post-sweep evaluate command
- Always use a unique, descriptive `--run-label` (e.g. `aapl-binary-baseline-a`)
