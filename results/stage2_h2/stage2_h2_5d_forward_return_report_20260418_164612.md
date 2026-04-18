# Stage 2 H2 Results Report

Project: reinforcement-learning-stocks  
Date: 2026-04-18  
Hypothesis: H2 — Longer-Horizon Targets  
Run ID: 5d_forward_return  
Status: kill

---

## 1. Run Metadata

- **Dataset version**: tech_training_data_stationary.csv
- **Feature set version**: stationary_features_v1
- **Target variant**: 5d_forward_return
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
| 0 | 2019-12-18 to 2022-12-01 | -0.0703 | -0.1343 | +0.5127 | +0.2739 | -0.6469 | -0.107 | -0.677 | -0.2753 | 0.137 | -0.0714 | fail |
| 1 | 2021-08-03 to 2024-07-19 | +0.3628 | +0.2461 | +0.3780 | +0.1558 | -0.1319 | +0.422 | -0.085 | -0.3619 | 0.172 | -0.0201 | fail |
| 2 | 2023-03-17 to 2026-03-06 | +0.4313 | +0.2653 | +1.3116 | +0.1368 | -1.0463 | +0.525 | -0.718 | -0.1968 | 0.237 | -0.0707 | fail |

## 5. Aggregate Metrics

- **Mean gross return**: +0.2412
- **Mean net return**: +0.1257
- **Mean net benchmark gap**: -0.6084
- **Mean net Sharpe**: +0.280
- **Mean benchmark Sharpe gap**: -0.493
- **Primary predictive metric (mean)**: -0.0540
- **Stability CV**: 1.464
- **2/3 benchmark pass achieved**: no
- **Recent window pass**: no

## 6. Gate Check

### Global Gates

- **G1 Benchmark Superiority**: FAIL
- **G2 Economic Robustness**: FAIL
- **G3 Stability**: FAIL
- **G4 Predictive Support**: PASS
- **G5 Cost Survivability**: FAIL

### Hard Stop Conditions Triggered

- [x] only one window positive
- [x] buy hold cleanly dominates
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
H2 target variant '5d_forward_return' with best family 'linear' produced mean net benchmark gap -0.6084 and recent-window gap -1.0463.

**Next action**:
- move_to_h1

## 9. Notes

Add anomalies, caveats, leakage checks, or benchmark interpretation notes here.