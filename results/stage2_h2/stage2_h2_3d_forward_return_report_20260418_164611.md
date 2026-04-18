# Stage 2 H2 Results Report

Project: reinforcement-learning-stocks  
Date: 2026-04-18  
Hypothesis: H2 — Longer-Horizon Targets  
Run ID: 3d_forward_return  
Status: kill

---

## 1. Run Metadata

- **Dataset version**: tech_training_data_stationary.csv
- **Feature set version**: stationary_features_v1
- **Target variant**: 3d_forward_return
- **Model family**: linear
- **Rolling-window scheme**: train=20%, val=20%, test=20%, slide=33%
- **Cost assumptions**: transaction_cost=0.0005, slippage=0.0002, turnover_rule=position_change
- **Recent window included**: yes

## 2. Thesis Being Tested

> Longer-horizon targets may reduce noise sensitivity and improve stability versus short-horizon targets.

## 3. Benchmarks

- buy-hold
- naive momentum
- flat/no-trade baseline

## 4. Window-Level Metrics

| Window | Period | Gross Return | Net Return | Buy-Hold Return | Momentum Return | Net Benchmark Gap | Net Sharpe | Benchmark Sharpe Gap | Max DD | Turnover | Predictive Metric | Verdict |
|--------|--------|--------------|------------|-----------------|-----------------|-------------------|------------|----------------------|--------|----------|-------------------|---------|
| 0 | 2019-12-20 to 2022-12-02 | +0.2518 | +0.1376 | +0.4948 | -0.3075 | -0.3572 | +0.299 | -0.260 | -0.3167 | 0.184 | -0.0492 | fail |
| 1 | 2021-08-06 to 2024-07-23 | +0.9576 | +0.7045 | +0.3976 | -0.2373 | +0.3070 | +0.808 | +0.285 | -0.3294 | 0.266 | -0.0162 | pass |
| 2 | 2023-03-23 to 2026-03-11 | +0.2563 | +0.0801 | +1.2864 | -0.0034 | -1.2063 | +0.235 | -0.997 | -0.1840 | 0.291 | -0.0465 | fail |

## 5. Aggregate Metrics

- **Mean gross return**: +0.4886
- **Mean net return**: +0.3074
- **Mean net benchmark gap**: -0.4188
- **Mean net Sharpe**: +0.447
- **Mean benchmark Sharpe gap**: -0.324
- **Primary predictive metric (mean)**: -0.0373
- **Stability CV**: 0.917
- **2/3 benchmark pass achieved**: no
- **Recent window pass**: no

## 6. Gate Check

### Global Gates

- **G1 Benchmark Superiority**: FAIL
- **G2 Economic Robustness**: FAIL
- **G3 Stability**: PASS
- **G4 Predictive Support**: PASS
- **G5 Cost Survivability**: FAIL

### Hard Stop Conditions Triggered

- [x] only one window positive
- [ ] buy hold cleanly dominates
- [x] net edge non positive after costs
- [x] recent window fails severely
- [ ] leakage or benchmark inconsistency

## 7. Interpretation

### What worked

[fill after reviewing the sweep output]

### What failed

[fill after reviewing the sweep output]

### Is the edge real or likely artifact?

[fill after reviewing the sweep output]

### Does this justify another H2 iteration?

[yes/no and why]

## 8. Final Verdict

**Verdict**: KILL

**Reason**:  
H2 target variant '3d_forward_return' with best family 'linear' produced mean net benchmark gap -0.4188 and recent-window gap -1.2063.

**Next action**:
- move_to_h1

## 9. Notes

Add anomalies, caveats, leakage checks, or benchmark interpretation notes here.