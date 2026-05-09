# GOOGL Experiment Log

## Strategy: PPO Binary + Min-Hold (Champion Architecture)
- **Architecture**: PPO
- **Action Space**: Discrete(2) [Binary Actions]
- **Structural Constraints**: `min_hold_bars=3`
- **Feature Set**: Stationary + Tech News (Sentimen)

---

## [2026-05-08] Stage 1 Pilot: High Entropy Calibration
**Goal**: Test if GOOGL can generate alpha with high exploration and institutional hold periods.

### Config
```powershell
python src/experiments.py --ticker googl --seeds 7,13,42 --timesteps 60000 --ent-coefs 0.05,0.08 --binary-actions --min-hold-bars 3 --run-label googl_ppo_pilot
```

### Results
*Pending execution...*

---

## Gate Checklist (Promotion Criteria)
- [ ] **Gate 1: Actionable Accuracy** (> 52.5%)
- [ ] **Gate 2: Trade Win Rate** (> 50%)
- [ ] **Gate 3: Alpha vs QQQ** (> 0.0)
- [ ] **Gate 4: Val/Test Drift** (< 5%)
- [ ] **Gate 5: CV Stability** (< 1.0)
- [ ] **Gate 6: Trade Rate** (0.4 - 1.0 [Relaxed])
