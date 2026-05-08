# AMZN (Amazon) — Experiment Log & Research Findings

> **Status: PROMOTED** — Champion: `seed=7, ent_coef=0.08, binary_actions, min_hold_bars=3, 60k steps`
> **Last updated:** 2026-05-08
> **Seed set:** [7, 13, 42] active — 6/6 Gate pass on Seed 7.
> **Champion config:** `sweep_amzn_stage1_v2`, seed=7, +0.116 Alpha, 0.544 Accuracy.

---

## Experiment History

| Phase | Label | Key Parameters | Result / Observation |
|-------|-------|----------------|----------------------|
| Stage 1 Pilot | `sweep_amzn_stage1_pilot` | ent ∈ [0.01, 0.03, 0.05], min_hold=3 | **G6 Failure (91-99%)**. Accuracy hit **0.528** (near miss). Drift is elite (0.002). |
| Stage 1 v2 | `sweep_amzn_stage1_v2` | ent=0.08, 60k steps | **CHAMPION: seed=7, 6/6 gates.** Accuracy 0.544, Alpha +0.116. Trade rate normalized to 78%. |

---

## Baseline Goals
1. **G1–G3 Stability**: Confirm directional accuracy > 0.53 and Alpha > 0.
2. **G6 Calibration**: Observe if AMZN stays in the [0.4, 0.8] band. Mega-cap tech often has different momentum characteristics than semis.
3. **Entropy Sensitivity**: Identify optimal exploration for AMZN's price action.

---

## Phase 1 Diagnosis: Conviction vs. Steps
AMZN initially exhibited mega-cap index tracking.
- **Breakthrough**: Extending to **60k steps** allowed the agent to resolve the fine-grained predictive signal needed for AMZN.
- **Entropy Effect**: 0.08 entropy successfully forced the agent to diverge from the "hold-forever" bull-bias and find more selective, alpha-positive entries.

## Path Forward
- [x] Promote to production via `generate_ensemble_config.py`
- [x] Validate via `run_exp9_walkforward.py`
