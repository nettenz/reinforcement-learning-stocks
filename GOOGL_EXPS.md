# GOOGL Experiment Log

## Strategy: PPO Binary + Min-Hold (Champion Architecture)
- **Architecture**: PPO
- **Action Space**: Discrete(2) [Binary Actions]
- **Feature Set**: Stationary (14-col) + use_stationary_features=True

---

## [2026-05-08] Sweep 1: Stage 1 Pilot (Windows, min_hold=3)
**Label**: `googl_ppo_pilot`  
**Machine**: Windows (D:\code\...)  
**Config**: seeds 7,13,42 | ent 0.05,0.08 | 60k steps | min_hold=3 | default penalties

### Results
Model files NOT transferred to Mac (Windows paths, gitignored).  
Ensemble config showed: seed 13 only, Sharpe 1.67, alpha +0.66, val_test_gap 0.013.  
Cannot be reproduced on Mac without the original .zip files.

---

## [2026-05-14] Sweep 2: Mac Retrain (min_hold=3)
**Label**: `googl-ppo-retrain`  
**Config**: seeds 3,7,13,21,42 | ent 0.02,0.05 | 50k steps | min_hold=3 | default penalties | use_stationary

### Results
- Seeds 7, 13: drift=0.5726, 0.0% test trade rate → val trades, test collapses (NVDA pre-fix pattern)
- Seeds 3, 21, 42: drift=0.0, 0.0% everywhere → total inaction
- **0/10 configs passed any gate (except Gate 4 at 60%)**

**Diagnosis**: min_hold=3 causes test-period generalization failure for high-momentum seeds.

---

## [2026-05-14] Sweep 3: min_hold=1 (no penalty change)
**Label**: `googl-ppo-minhold1`  
**Config**: seeds 3,7,13,21,42 | ent 0.02,0.05 | 80k steps | **min_hold=1** | default penalties | use_stationary

### Results
- Seeds 7, 13, 21: drift=0.5696 → still val-only trading, test collapse persists
- Seeds 3, 42: mixed drift=0/0.57
- **0/10 gates passed (0-1 gates per seed)**

**Diagnosis**: min_hold=1 alone insufficient. Needs penalty loosening too (same as NVDA full fix).

---

## [2026-05-14] Sweep 4: Full NVDA Fix Package (min_hold=1 + loose penalties) ❌
**Label**: `googl-ppo-minhold1-loosen`  
**Config**: seeds 3,7,13,21,42 | ent 0.05,0.08 | 80k steps | min_hold=1 | hold_penalty=0.01 | turnover_penalty=0.01 | stationary

### Results
- All seeds: drift=0.5654-0.5696, 0.0% test trade rate
- Val period shows ~57% accuracy signal; test period collapses completely
- **0/10 gates passed**

---

## [2026-05-14] Sweep 5: Raw Features (no stationary) ❌
**Label**: `googl-ppo-raw-features`  
**Config**: seeds 3,7,13,21,42 | ent 0.05,0.08 | 80k steps | min_hold=1 | hold_penalty=0.01 | turnover_penalty=0.01 | **no use_stationary_features**

### Results
- All seeds: drift=0.554-0.5696, 0.0% test trade rate
- Same drift wall regardless of feature space
- **0/10 gates passed**

---

## ❌ FINAL VERDICT: FORMALLY DEFERRED

5 sweeps across all architectural levers:
- min_hold_bars: 1 and 3 both fail
- Penalty scaling: default and 0.01/0.01 both fail
- Feature space: stationary and raw both fail
- Entropy: 0.02, 0.05, 0.08 all fail
- Timesteps: 50k, 60k, 80k all fail

The consistent drift=0.55-0.57 across all configs means GOOGL's val regime (2021-2024 AI bull)  
generates a learnable signal, but the test period (2024-2026 post-peak) does not support  
a selective binary strategy at any explored hyperparameter.

The original Windows champion (+0.665 alpha) was an always-long (90%+ trade rate) model  
that rode the 2024 AI bull run. That regime is now inside the training window, not the test split.

**Do not run further GOOGL sweeps under Binary PPO.** May revisit with a different  
architecture (long/short binary, or sector-relative features) in a future phase.

---

## Gate Checklist (Promotion Criteria)
- [ ] **Gate 1: Actionable Accuracy** (> 52.5%)
- [ ] **Gate 2: Trade Win Rate** (> 50%)
- [ ] **Gate 3: Alpha vs QQQ** (> 0.0)
- [ ] **Gate 4: Val/Test Drift** (< 5%)
- [ ] **Gate 5: CV Stability** (< 1.0)
- [ ] **Gate 6: Trade Rate** (0.4 - 1.0 [Relaxed])
