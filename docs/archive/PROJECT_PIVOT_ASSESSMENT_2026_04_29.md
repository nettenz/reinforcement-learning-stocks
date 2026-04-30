# Project Pivot Assessment — reinforcement-learning-stocks

**Date:** 2026-04-29
**Author:** Opus (claude-opus-4-7)
**Companion to:** `PROJECT_STATE_2026_04_29.md`
**Purpose:** Independent assessment of where the project stands after Stage 3 Option A, and a structured set of probable pivots — ranked by evidence strength, cost, and time-to-falsification.

---

## 1. Executive Take

After three stages of structured research the original hypothesis — *"a machine-learning system can extract alpha in tech equities (AAPL, AMD, NVDA) from stationary price/volume/sentiment features"* — is **substantially falsified**. Two independent tracks (RL agents and supervised baselines) have failed on the same dataset, with the same root signature: signal present in validation, signal absent in test, recent windows worst.

The decision now is not "tune harder." The decision is **which dimension to change** — features, universe, target, horizon, or architecture — to test whether the failure is local to this specific setup or general to the entire research direction.

This document lays out six pivots. Three are evidence-aligned and cheap (≤1 week). Three are larger commitments (2–8 weeks). The goal here is to give you a defensible decision tree, not to push any single direction.

---

## 2. Where We Are — Factually

| Stage | Track | Method | Verdict | Decisive Evidence |
|---|---|---|---|---|
| 1 | RL | SAC/PPO sweeps with shaped reward | KILL | 0% test trades on best run; CV 53.5 across seeds; -12.8bp test alpha |
| 2 H1 | Supervised | Event-driven classifier | KILL | Insufficient real event labels; market-proxy tags too coarse |
| 2 H2 | Supervised | 1/3/5d return regression | KILL | R² universally negative across all horizons and windows |
| 2 H3 | Supervised | Cross-sectional ranking (uncapped) | KILL | NVDA captured 63–85% of returns; rank IC near zero |
| 2 H4 | Supervised | Cross-sectional ranking (capped) | KILL | Capping killed gains without recovering rank quality |
| 3 A  | Supervised | Directional classifier with abstain band | KILL | AUC ~0.50 both models; recent window catastrophic (BH +127.7% vs model -1.3% to +28%) |

**The signature in every result is identical:** validation looks plausible (logistic 0.555 mean accuracy, regression R² near zero, RL val_actionable 66%), test breaks down badly, and the most recent window — the one closest to live trading — is the worst performer.

---

## 3. Root-Cause Hypotheses (Ranked by Posterior)

Three explanations are consistent with the evidence. They are not mutually exclusive, but they imply different pivots.

### H-A: The features have no learnable directional content at daily horizons. *(Posterior: high)*
The Stage 2 H2 negative R² and Stage 3 AUC ≈ 0.50 are direct evidence. Stationary technical indicators (LogReturn, VolLogDiff, RelMACD, RSI_Centered) plus aggregated daily news sentiment are well-trodden ground; if they had durable predictive content for next-3d returns, retail and academic literature would have found it long ago. The features may capture *contemporaneous* state but not *forward* signal.

### H-B: The universe is too small and too correlated. *(Posterior: medium-high)*
Three tech stocks plus QQQ/SPY share most of their daily variance. Cross-sectional ranking devolved into "long whatever NVDA has been doing." A universe with genuinely independent return drivers (sector rotation, factor exposure, asset class) might surface signal that this universe cannot.

### H-C: The target is wrong. *(Posterior: medium)*
Predicting next-N-day returns is one of the noisiest possible targets. Volatility, regime state, and drawdown probability have far stronger autocorrelation. The features may contain real *risk* signal that's invisible when the loss function is keyed to *return*.

### H-D: The reward shaping was the problem. *(Posterior: low — already partially tested by Stage 3)*
Plausible before Stage 2, but Stage 2's clean supervised baselines also failed. If the features themselves had no signal, no reward function will recover one. **The currently-running Fork B Option 1 is the falsifying test.** If a stripped-down Sharpe reward with binary actions still produces zero test trades, H-D is dead.

---

## 4. Probable Pivots — Ranked

Each pivot is rated on three axes:
- **Cost**: developer-weeks to a falsifiable result
- **Evidence**: how well the existing data supports the pivot's hypothesis
- **Risk of repeat failure**: probability the pivot hits the same signature

### Pivot 1 — Intraday microstructure (5-minute NVDA)

**Hypothesis:** Daily bars destroy the order-flow information that drives intraday alpha. The repo already contains `data/tech_training_data_nvda_5m_stationary.parquet`. Switching horizons from 3d to 30–120min targets a fundamentally different mechanism: short-term mean reversion, opening auction effects, lunchtime drift, vol clustering — all of which have published academic evidence and far higher signal-to-noise than daily directional prediction.

| Cost | Evidence | Repeat-failure risk |
|---|---|---|
| ~1 week | High — data exists, mechanism well-documented | Medium — execution costs are punishing at 5m |

**Why this should be the front-runner:** the data is already loaded, the failure mode (no signal at 3d) doesn't transfer to 30min, and a clean 1-week test gives a definitive answer.

**Falsifiable gate:** directional accuracy > 52% on 30–60min targets, net Sharpe > 0 after 5–10bp round-trip costs across 3 walk-forward windows.

---

### Pivot 2 — Universe expansion (cross-asset, not cross-tech)

**Hypothesis:** Stage 2 H3's "alpha" was NVDA beta in disguise because AAPL/AMD/NVDA share too much variance. A genuinely heterogeneous universe (sector ETFs: XLK/XLF/XLE/XLV/XLU + factor ETFs: MTUM/QUAL/VLUE + macro: TLT/GLD) gives the cross-sectional ranker something to actually rank. If the features capture *relative* information (which is what RSI/MACD/return are), a heterogeneous universe is where they should shine.

| Cost | Evidence | Repeat-failure risk |
|---|---|---|
| ~3–5 days | Medium — H3 hinted at this but was confounded by NVDA | Medium — the features may still be too generic |

**Falsifiable gate:** rank IC > 0.05 in 2/3 windows AND dominant-ticker share < 30% AND net edge > equal-weight in recent window.

This is **Option B** from the original PROJECT_STATE doc, lifted as-is.

---

### Pivot 3 — Target reformulation (regime / vol / drawdown)

**Hypothesis:** Returns are noise; risk is signal. Predict (a) vol regime (low/med/high) using realized vol percentiles, (b) drawdown-onset probability over next 5 days, or (c) regime-transition events. Then build the trading strategy on top: scale exposure inversely to predicted vol, exit on drawdown-onset signal. This converts the project from "alpha generation" to "risk-managed buy-and-hold," which has a much weaker null hypothesis and a more tractable target.

| Cost | Evidence | Repeat-failure risk |
|---|---|---|
| ~1–2 weeks | High for vol prediction (academic consensus); moderate for drawdown | Low for vol; medium for drawdown |

**Falsifiable gate:** predicted-vol model R² > 0.10 (vs returns' negative R²); risk-managed strategy net Sharpe > buy-hold Sharpe in recent window.

This is the most intellectually honest pivot — it admits the original target was wrong and chooses a target the field knows is learnable.

---

### Pivot 4 — Architecture: regime-conditional ensemble

**Hypothesis:** The Stage 1 RL collapse and Stage 2 unstable rankings both look like single models trying to fit incompatible regimes (the 2019–2021 grind, 2022 selloff, 2023–2026 NVDA boom). Train regime-specific sub-models gated by an unsupervised regime detector (HMM on volatility + correlation matrix). Each sub-model has a smaller, more learnable problem.

| Cost | Evidence | Repeat-failure risk |
|---|---|---|
| ~2–3 weeks | Low-medium — circumstantial from window-level instability | High — adds complexity without addressing feature signal absence |

**Honest tradeoff:** this only helps if the *features* contain regime-specific signal that's averaged out by single-model fitting. Given Stage 2's near-zero AUCs, that's not strongly supported.

---

### Pivot 5 — Reward architecture rebuild (Option 2 of the current Fork B path)

**Hypothesis:** If Fork B Option 1 (currently running) shows test-period activity but poor Sharpe, replace dense reward shaping with sparse episodic rewards: agent receives one signal at the end of a 60-day episode, equal to (final_equity / buy_hold_equity) - 1. No per-step reward at all. This is the cleanest possible reward and the hardest to hack.

| Cost | Evidence | Repeat-failure risk |
|---|---|---|
| ~1 week | Conditional on Option 1 outcome | High if Option 1 shows zero test trades — feature absence is the deeper problem |

**Verdict:** valuable only if Option 1's results are ambiguous (some activity, poor Sharpe). If Option 1 shows zero trades, skip this pivot.

---

### Pivot 6 — Honest project exit

**Hypothesis:** The original research question has been answered, and the answer is "no — not with this universe, this feature set, and these horizons." Repurpose the codebase as a research framework template. The infrastructure (gate contracts, walk-forward windows, supervised baselines, RL harness, leaderboards) is genuinely good even though the alpha quest failed.

| Cost | Evidence | Repeat-failure risk |
|---|---|---|
| ~2 days (write-up + archive) | Highest — three independent failures | None |

**Why this is on the list:** sunk-cost fallacy is real, and pivots 1–5 each carry meaningful additional cost. If the goal of this project was *learning whether ML alpha exists in tech equities at daily horizons*, that goal has been achieved. The answer is just "no."

---

## 5. Recommended Decision Tree

The decision tree below assumes you want **maximum information per developer-week** and **fastest possible falsification**.

```
Currently running: Fork B Option 1 (simplified RL)
│
├── Test trades > 0 AND mean Sharpe > 0
│   └── Run Pivot 5 (Option 2 sparse episodic) — already planned
│
├── Test trades > 0 AND mean Sharpe ≤ 0
│   └── Run Pivot 5, but in parallel start Pivot 1 (intraday)
│
└── Test trades = 0 (collapse to hold)
    │
    ├── Have appetite for one more pivot?
    │   ├── YES, want highest-evidence shot     →  Pivot 1 (intraday 5m)
    │   ├── YES, want target reformulation      →  Pivot 3 (vol/regime)
    │   └── YES, want universe expansion        →  Pivot 2 (cross-asset)
    │
    └── NO appetite for further pivots          →  Pivot 6 (honest exit)
```

**Hierarchy of evidence value if exactly one pivot is chosen after Fork B closes:**
1. **Pivot 1 (intraday 5m)** — best ratio of evidence-to-cost. Data exists. Mechanism is published. One week to a verdict.
2. **Pivot 3 (regime/vol target)** — most intellectually honest. Highest probability of finding *some* signal, but it's a different project at that point.
3. **Pivot 2 (universe expansion)** — cheap, but moderate odds of repeating Stage 2's outcome. Worth running in parallel with Pivot 1, not instead of it.

---

## 6. What Would Make Each Pivot Worth Doing

A pivot is only worth running if you can **state in advance what result would change your mind**. Concrete falsifiers for each:

- **Pivot 1 (intraday):** ≥52% directional accuracy on 30min targets across 3 windows after 10bp costs, OR clean exit.
- **Pivot 2 (universe):** Rank IC > 0.05 with dominant-ticker share < 30%, OR clean exit.
- **Pivot 3 (vol target):** Vol-prediction R² > 0.10 AND risk-managed strategy beats buy-hold in recent window, OR clean exit.
- **Pivot 4 (regime ensemble):** Regime-conditional models beat unconditional baseline by ≥30% in net Sharpe, OR no further architectural pivots.
- **Pivot 5 (sparse RL):** Conditional on Option 1; same gate as Stage 1 (test_actionable > 53%, CV < 1.0).

Without these gates, any pivot becomes another tuning loop.

---

## 7. What I Would Caution Against

- **Adding more features to the daily setup.** This is the failure mode the project has been in for months. Stage 2's negative R² across multiple feature configurations is strong evidence that more features will not move the needle.
- **Returning to the original RL reward shaping with more parameters.** Fork B Option 1 is already testing whether *less* is more. If it fails, *more* will not succeed.
- **Tuning hyperparameters without changing the problem.** Learning rate, gamma, ent_coef, and timesteps sweeps are exhausted territory in this codebase (136+ runs, no winners).
- **Treating Stage 2's "best" hypothesis (H2-3d linear, Window 1: +30pp over BH) as a starting point.** That result was a single window in a sweep that explicitly killed at 2/3 windows. It is one positive draw from a process that is mostly negative.

---

## 8. Closing Frame

The project was set up correctly. The gate contracts, the staged escalation, the supervised-before-RL discipline — these are the right scaffolding for honest research, and they did exactly what they were designed to do: they **stopped the project from declaring premature victory** at Stage 1, and they're now stopping it from declaring premature victory at Stage 3.

The harder skill — the one being exercised right now — is treating "no signal" as a real, valid finding. Every pivot above is a way of asking "did we look in the wrong place?" rather than "did we look hard enough?" Both questions are valid. Only the first is likely to produce a different answer.

If the current Fork B Option 1 run also fails, my recommendation is **Pivot 1 (intraday 5m)**: it has the strongest mechanistic prior, the data is already on disk, and one week from now you will have a definitive answer about whether high-frequency structure exists in this same universe. After that, the choice between continuing (Pivot 3) and exiting (Pivot 6) becomes a much easier call.

---

*Signed by Opus (claude-opus-4-7), 2026-04-29*
*Companion to PROJECT_STATE_2026_04_29.md*
