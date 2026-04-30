# Project State — reinforcement-learning-stocks
**Date:** 2026-04-29  
**Purpose:** Authoritative handoff. Read this before any other document in the repository.  
**Supersedes:** `CLAUDE_HANDOFFV2.md`, `HANDOFF_SUMMARY.md`, `README_HANDOFF.md`

---

## TL;DR

The project has completed two full research stages. **Both failed their promotion gates.** A third stage (reframing) is now the only valid next step. Do not run any RL experiments until a Stage 3 hypothesis passes supervised baseline gates.

---

## 1. Project Architecture

This repository tests whether a machine-learning system can generate alpha in tech equities (AAPL, AMD, NVDA) using an RL agent trained on stationary price/volume/sentiment features.

The research is governed by a **staged gate contract** defined in `stages.md` and `stage2_gate_definitions.md`:

- **Each stage must earn the right to the next.**
- **RL escalation is explicitly blocked** until a supervised baseline demonstrates durable forward-looking economic edge.
- Gate violations are not advisory — they are hard stops.

---

## 2. Stage 1 — RL Track (Completed, Failed)

**Period:** Early 2026 through ~2026-04-13  
**Approach:** Train SAC/PPO agents (`src/experiments.py`) directly on AAPL, AMD, NVDA with walk-forward validation.  
**Leaderboard:** 136+ rows across multiple tickers and reward modes (legacy, sharpe, sortino).

### What was tried
- Multiple reward configurations: PnL scale, return scale, direction scale, hold penalty, drawdown penalty, action bonus, turnover penalty
- Multiple entropy coefficients (0.02–0.10)
- Multiple timesteps (20k–40k)
- Multiple seeds (5–10 per config)
- Next-bar execution mode with realistic costs (10bp transaction, 1bp spread, 1bp slippage)
- Stationary vs raw features
- News sentiment ablation

### Best RL result (from `data/experiment_summary.json`, dated 2026-04-13)
| Metric | Value | Gate Threshold | Status |
|---|---|---|---|
| `test_actionable_accuracy` | 0.0% (no test trades) | ≥ 53% | ❌ FAIL |
| `test_alpha_vs_qqq` | -12.8bp | ≥ 0bp | ❌ FAIL |
| `test_return_cv_by_config` | 53.54 (10 seeds) | < 1.0 | ❌ FAIL |
| `val_actionable_accuracy` | 66.0% | — | — |
| `val/test gap` | 66pp gap | ≤ 5% | ❌ FAIL |

The best run by ranking score produced **zero test trades** — the agent collapsed to a hold policy in the test period. The val/test gap was catastrophically large (validation appeared to work, test failed entirely).

### RL track diagnosis
The `assessment.md` file in the repository correctly identified the root cause:
> "The agent is learning policy behavior that scores well on proxy objectives while failing to uncover a durable market edge. The main issue is not lack of effort or infrastructure. The issue is that the current RL problem definition is too ambitious and too shaped."

**Key structural problems identified:**
1. Reward function doing too much simultaneously (return shaping + direction + hold penalty + action bonus + turnover + drawdown)
2. Continuous target weights make sizing and forecasting entangled
3. Evaluation metrics (actionable accuracy, win rate) are proxies, not economic performance
4. Seed instability (CV > 50) indicates the policy is not learning — it is finding lucky trajectories

**Gate verdict:** Stage 1 RL track — NOT PROMOTABLE. 0/5 promotion gates pass.

---

## 3. Stage 2 — Signal-First Supervised Pivot (Completed, All Killed)

**Period:** 2026-04-18  
**Approach:** Before rerunning RL, prove that the features contain any learnable predictive signal using supervised baselines with strict gate enforcement.  
**Framework:** 3 rolling windows (20% train / 20% val / 20% test / 33% slide), 7bp round-trip cost model, buy-hold and momentum benchmarks.

Four hypotheses were defined, executed, and evaluated. **All four received KILL verdicts.**

### H1 — Event-Driven Prediction
**Thesis:** Sparse high-information event contexts offer better signal-to-noise than continuous prediction.  
**Implementation:** Market-proxy event tags (vol expansion, volume spike, momentum breakout, oversold/overbought reversal) used as event labels since real calendar events are unavailable.

| Metric | Result |
|---|---|
| Windows with sufficient event counts | 1/3 |
| Gates passed | 0/5 (both logistic and tree variants) |
| Mean net return | 1.4% (logistic), -6.5% (tree) |
| Buy-hold in same windows | 0–120% |

**Hard stops triggered:** Insufficient event count (2/3 windows), single event cluster dependency, net edge negative after costs, recent window fails severely.

**Root cause:** The dataset does not contain real calendar event labels. Market-proxy tags are too coarse and too dominated by one event type (`oversold_reversal`). Even in the one valid window, buy-hold returned 120% vs model's 4.3%.

**Verdict: KILL — H1 is not viable with the current dataset's event tagging.**

---

### H2 — Longer-Horizon Targets
**Thesis:** Targets of 1-day, 3-day, and 5-day forward returns are more stable than 1-step ahead.  
**Implementation:** Linear regression and tree regression on all three horizons, 3 rolling windows.

| Variant | Mean Net Return | Mean R² | Gates Passed | Verdict |
|---|---|---|---|---|
| 1d linear/tree | 27% | -0.26 (all negative) | 2/5 (G3, G4) | KILL |
| 3d linear/tree | 31% | -0.04 to -0.47 | 2/5 (G3, G4) | KILL |
| 5d linear/tree | 13% | -0.05 to -0.85 | 1/5 (G4) | KILL |

**Key finding:** R² values are **universally negative** across all horizons and all windows. The models are not forecasting returns — they are trading correlated noise. The one bright spot (H2-3d linear, Window 1: +30.7pp over buy-hold, Sharpe 0.81) does not generalize to the other two windows and fails the 2-of-3 gate.

**Hard stops triggered:** Only one window positive, buy-hold dominates in recent window (buy-hold +120–128% vs model +3–45% net), net edge non-positive after costs in recent window.

**Verdict: KILL — H2 has no durable predictive quality at any tested horizon.**

---

### H3 — Cross-Sectional Ranking (uncapped)
**Thesis:** Ranking assets (AAPL, AMD, NVDA, QQQ, SPY) by predicted forward return and holding top-2 generates edge where single-asset direction fails.  
**Implementation:** Linear rank model, tree rank model, momentum rank — monthly rebalancing, top-2 equal weight.

| Variant | Mean Net Return | G1 (Benchmark) | Dominant Ticker Share | Rank IC | Verdict |
|---|---|---|---|---|---|
| linear_rank | 160% | FAIL | NVDA 85% (W1) | -0.04 to +0.12 | KILL |
| tree_rank | 159% | FAIL | NVDA 73% (W1) | -0.10 to +0.07 | KILL |
| **momentum_rank** | **184%** | **FAIL** | NVDA 63% (W1) | **-0.14 to +0.11** | **KILL** |

**Momentum_rank** was the best variant: passed G1 in 2/3 windows, lowest stability CV (0.153). However:
- Recent window (2023–2026): buy-hold returned **306%**, momentum_rank returned **220%** — severely underperforms
- NVDA dominated 63–85% of total gains — the "ranking" is capturing NVDA beta, not cross-sectional skill
- Rank IC (information coefficient) is near zero or negative — rankings are essentially random

**Hard stops triggered:** Rank ordering unstable, single ticker dominates, net edge non-positive in recent window.

**Verdict: KILL — H3 gains are a NVDA concentration artifact, not cross-sectional alpha.**

---

### H4 — Cross-Sectional Ranking (0.5 concentration cap)
**Thesis:** Capping any single position at 50% removes NVDA concentration bias from H3.  
**Implementation:** Same as H3 but with 50% max weight per asset.

All three variants (linear_rank, tree_rank, momentum_rank) received KILL verdicts. Capping reduced returns without recovering rank quality. All failed G1, G2, and G5.

**Verdict: KILL — Concentration cap did not resolve the underlying lack of rank signal.**

---

### Stage 2 Summary Table

| Hypothesis | Best Variant | Gates Passed | Verdict |
|---|---|---|---|
| H1 Event-Driven | logistic | 0/5 | KILL |
| H2 Longer-Horizon | 3d linear | 2/5 | KILL |
| H3 Cross-Sectional | momentum_rank | 1/5 (G1 only, 2/3 windows) | KILL |
| H4 Capped Ranking | linear_rank | 1/5 | KILL |

**Stage 2 gate contract outcome:** *"Exit predictive alpha exploration for this dataset/setup if no hypothesis passes."*  
This condition is formally triggered. Stage 3 requires a **reframing**, not more tuning.

---

## 4. RL Escalation Status

**RL escalation is BLOCKED.**

The gate contract (`stage2_gate_definitions.md`, Section 7.3) states:
> "RL is allowed only when at least one Stage 2 hypothesis demonstrates durable forward economic edge, acceptable cross-window stability, and superiority versus trivial baselines. Otherwise RL escalation remains blocked."

Running `experiments.py` for more RL reward sweeps right now would be working around this contract, not resolving the underlying problem.

**This means CLAUDE_HANDOFFV2.md is premature.** Its Tier 1–3 experiment suite (Exp A–K) all operate on the assumption that RL is the correct next track. That assumption is not supported by the Stage 2 evidence.

---

## 5. Why the RL Leaderboard Numbers in CLAUDE_HANDOFFV2.md May Look Encouraging

CLAUDE_HANDOFFV2.md references:
- "54.3% test accuracy (NVDA)"
- "NVDA: CONDITIONAL at 0.6578"
- "AAPL: HOLD at 0.5828"

These numbers come from a **different leaderboard slice** than `data/experiment_summary.json` (which is the most recent confirmed state). The `experiment_summary.json` shows the actual top-3 runs including the best NVDA run with `test_actionable_accuracy: 0.0%` and `test_return_cv_by_config: 53.5`. The apparent 54.3% figure likely comes from a specific seed that happened to trade in the test period — seed instability makes these numbers meaningless without CV < 1.0.

Even if taken at face value:
- A `test_return_cv_by_config` of ~3.41 (still cited in CLAUDE_HANDOFFV2.md) is 3x above the 1.0 threshold — not promotable
- AAPL's leakage flag is a structural data integrity concern, not a reward tuning issue
- AMD at 43% is well below any promotable threshold

---

## 6. What Is Valid to Run Right Now

The following work is within the gate contract without needing a formal override:

### Option A — Directional Classification on 3d Returns (Low cost, high info)
Convert H2's regression target into a binary classifier (predict direction above ±0.5% threshold, abstain otherwise). Tests whether the features have directional content at all, independent of return magnitude.

```powershell
.\.venv\Scripts\Activate.ps1

python scripts/run_stage2_h2_directional.py `
  --target-horizon 3 `
  --target-type directional_threshold `
  --direction-threshold 0.005 `
  --trade-prob-threshold 0.60 `
  --models logistic xgboost `
  --output-dir results/stage3_h2_directional/ `
  --ledger-out logs/stage3_h2_directional_ledger.json
```

**Gate to pass:** Directional accuracy > 55% in 2/3 windows AND net return > buy-hold in 2/3 windows.

**If this fails:** Features have no directional content at 3d horizon. Confirm exit.

---

### Option B — Universe Expansion for H3 Momentum Rank (Medium cost, high info)
Retest H3 momentum_rank with a more heterogeneous universe that includes non-tech assets (e.g., XLK, XLF, XLE, XLV, JPM). If NVDA concentration was the only driver, this will fail. If there is real cross-sectional structure, it will survive.

```powershell
.\.venv\Scripts\Activate.ps1

python scripts/run_stage2_h3.py `
  --universe AAPL AMD NVDA QQQ SPY XLK XLF XLE XLV JPM `
  --window-config 0.20 0.20 0.20 0.33 `
  --cost-bps 7 `
  --output-dir results/stage3_h3_expanded/ `
  --ledger-out logs/stage3_h3_expanded_ledger.json
```

**Gate to pass:** Passes G1 (2/3 windows beat equal-weight) AND dominant ticker share < 40% AND rank IC > 0.05 in 2/3 windows.

**If this fails:** No cross-sectional alpha in this feature set. Confirm exit.

---

### Option C — NVDA 5-Minute Microstructure (Medium cost, new hypothesis)
The repository already contains `data/tech_training_data_nvda_5m_stationary.parquet`. This is a fundamentally different alpha source (intraday order-flow patterns, not daily direction). Requires a new script.

**Gate to pass:** Directional accuracy > 52% in 2/3 windows, net Sharpe > 0.

---

## 7. What Requires a Gate Override to Run

The following experiments from `CLAUDE_HANDOFFV2.md` require explicit acknowledgment that you are bypassing the Stage 2 gate contract:

| Experiment | Why It Needs Override |
|---|---|
| Exp A — AAPL Leakage Audit | Valid diagnostic, but AAPL's RL results are secondary to no-signal problem |
| Exp C — NVDA 10-Seed Lock-In | RL reward sweep; Stage 2 gate blocks this |
| Exp E — Learning Rate Sweep | RL hyperparameter; blocked |
| Exp F — Gamma Sweep | RL hyperparameter; blocked |
| Exp G — Extended Timesteps | RL hyperparameter; blocked |
| Exp H — Feature Ablation | Diagnostic value only if run as supervised baseline, not RL |
| Exp I — SAC vs PPO | Algorithm comparison; blocked |
| Exp J — News Sentiment Ablation | Has value as supervised feature test (align with Option A format) |
| Exp K — Dollar-Neutral Pilot | Architectural change; far downstream of current blockers |

**If you want to override:** State it explicitly and acknowledge that RL results may not improve the fundamental signal absence problem.

---

## 8. Decision Point

You are at a fork. Both paths are defensible, but they have different cost/risk profiles:

### Fork A — Follow the gate contract (Recommended)
Run Option A and/or Option B above. Takes ~1–3 hours. If they pass → Stage 3 supervised baseline confirmed → RL escalation unlocked. If they fail → formal project exit with full evidence.

### Fork B — Override gates and return to RL tuning
Run CLAUDE_HANDOFFV2.md's Tier 1–3 suite. Takes ~2 weeks. The risk is that the RL results improve proxy metrics (actionable accuracy, win rate) without resolving the underlying supervised signal absence — the same failure mode as Stage 1.

### Fork C — Formal project exit
Accept Stage 2 results as conclusive. Archive the codebase. Redirect effort.

---

## 9. Repository Files Reference

| File | Purpose | Trust Level |
|---|---|---|
| `stages.md` | Stage gate definitions | Authoritative |
| `stage2_gate_definitions.md` | Gate thresholds and contract | Authoritative |
| `stage2_experiment_brief.md` | H1–H3 hypothesis specs | Authoritative |
| `logs/stage2_h*.json` | H1–H4 results ledgers | Authoritative (2026-04-18) |
| `assessment.md` | Honest project diagnosis | Authoritative |
| `data/experiment_summary.json` | RL leaderboard top-3 snapshot | Authoritative (2026-04-13) |
| `data/experiment_leaderboard.csv` | Full RL leaderboard | Reference (pre-Stage 2) |
| `CLAUDE_HANDOFFV2.md` | RL experiment suite | **Outdated — does not reflect Stage 2 results** |
| `HANDOFF_SUMMARY.md` | April 10 RL handoff | **Outdated — pre-Stage 2** |
| `README_HANDOFF.md` | April 10 RL index | **Outdated — pre-Stage 2** |

---

## 10. Hard Rules (Standing)

1. Do not run `experiments.py` for RL sweeps until at least one Stage 3 supervised hypothesis passes G1–G5.
2. Do not promote on validation-only results. Test gate is binary.
3. Do not treat the best single seed as representative of a config. CV < 1.0 across ≥5 seeds is required.
4. Do not merge Stage 2 ledger evidence with RL leaderboard evidence without explicit comparability notes.
5. Any gate override must be stated explicitly and logged in a decision record.
6. The most recent window (2023–2026) must not fail severely in any promoted hypothesis.

---

*Prepared: 2026-04-29 | Replaces all prior handoff documents*  
*Track: Stage 2 → Stage 3 transition | RL escalation: BLOCKED*
