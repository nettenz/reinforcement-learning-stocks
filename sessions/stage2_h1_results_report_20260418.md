# Stage 2 H1 Results Report

Project: reinforcement-learning-stocks  
Date: 2026-04-18  
Hypothesis: H1 - Event-Driven Prediction  
Run ID: h1-event-proxy-sweep-20260418  
Status: killed

---

## 1. Run Metadata

- **Dataset version**: tech_training_data_stationary.csv
- **Feature set version**: market_proxy_event_features_v1
- **Event tag set**: vol_expansion, volume_spike, momentum_breakout, oversold_reversal, overbought_reversal
- **Event detection rules**: train-quantile market proxies derived from stationary features; calendar event labels were not available in the dataset
- **Model family**: logistic, random_forest
- **Rolling-window scheme**: train 20%, validation 20%, test 20%, slide 33%
- **Cost assumptions**: transaction cost 0.0005, slippage 0.0002, turnover rule based on position change
- **Recent window included**: yes

---

## 2. Thesis Being Tested

> Sparse high-information event contexts may offer better signal-to-noise than continuous prediction.

This run used market-proxy event tags because the stationary dataset does not contain usable calendar event labels.

---

## 3. Sample Sufficiency Check

| Window | Period | Total Event Count | Earnings | Macro | Vol Expansion | Abnormal Volume | Momentum Breakout | Sufficiency Verdict |
| ------ | ------ | ----------------- | -------- | ----- | ------------- | --------------- | ----------------- | ------------------- |
| 0 | 2019-12-20 to 2022-12-06 | 458 | 0 | 0 | 13 | 117 | 257 | fail |
| 1 | 2021-08-06 to 2024-07-25 | 302 | 0 | 0 | 0 | 83 | 29 | fail |
| 2 | 2023-03-23 to 2026-03-13 | 310 | 0 | 0 | 13 | 135 | 113 | pass |

### Auto-Kill Check

- [x] insufficient total sample count
- [x] one event type dominates
- [x] recent-window coverage insufficient

---

## 4. Benchmarks

This run was compared against:

- buy-hold
- event-relevant naive baseline
- flat/no-trade baseline

---

## 5. Window-Level Metrics

| Window | Period | Gross Return | Net Return | Buy-Hold Return | Event Baseline Return | Net Benchmark Gap | Net Sharpe | Benchmark Sharpe Gap | Max DD | Turnover | Predictive Metric | Event Cluster Driver | Verdict |
| ------ | ------ | ------------ | ---------- | --------------- | --------------------- | ----------------- | ---------- | -------------------- | ------ | -------- | ----------------- | -------------------- | ------- |
| 0 | 2019-12-20 to 2022-12-06 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | -1.0000 | 0.000 | -1.000 | 0.0000 | 0.000 | 0.0000 | insufficient_events | fail |
| 1 | 2021-08-06 to 2024-07-25 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | -1.0000 | 0.000 | -1.000 | 0.0000 | 0.000 | 0.0000 | insufficient_events | fail |
| 2 | 2023-03-23 to 2026-03-13 | 0.1176 | 0.0434 | 1.1972 | -0.1690 | -1.1538 | 0.189 | -0.986 | -0.1817 | 0.132 | 0.5516 | oversold_reversal | fail |

---

## 6. Aggregate Metrics

- **Mean gross return**: +0.0392
- **Mean net return**: +0.0145
- **Mean net benchmark gap**: -1.0513
- **Mean net Sharpe**: +0.063
- **Mean benchmark Sharpe gap**: -0.995
- **Primary predictive metric (mean)**: 0.1839
- **Stability CV**: 1.414
- **2/3 benchmark pass achieved**: no
- **Recent window pass**: no
- **Single-event-cluster dependency**: yes

---

## 7. Gate Check

### Global Gates

- **G1 Benchmark Superiority**: FAIL
- **G2 Economic Robustness**: FAIL
- **G3 Stability**: FAIL
- **G4 Predictive Support**: FAIL
- **G5 Cost Survivability**: FAIL

### H1-Specific Gates

- **H1-1 Event sample count sufficient in each window**: FAIL
- **H1-2 At least 2/3 windows show positive net edge**: FAIL
- **H1-3 Predictive quality above naive**: FAIL
- **H1-4 Edge not carried by one event cluster**: FAIL
- **H1-5 Edge survives transaction costs**: FAIL

### Hard Stop Conditions Triggered

- [x] performance appears in only one window
- [x] insufficient event count
- [x] one event type explains almost all gains
- [x] net edge non-positive after costs
- [x] recent window fails severely
- [ ] leakage or benchmark inconsistency detected

---

## 8. Interpretation

### What worked

- The 2023-2026 window produced usable event counts and the logistic classifier produced the best predictive score in the sweep.
- The event-rule baseline made the regime dependence visible rather than hiding it in the model.

### What failed

- Two of three windows failed the sample sufficiency check before modeling.
- The remaining window did not clear the benchmark contract.
- The result was carried mostly by oversold_reversal, which is a single-cluster dependency.
- Predictive accuracy stayed weak and did not translate into economic edge.

### Was the edge broad or event-cluster-specific?

Event-cluster-specific. The positive contribution was concentrated in oversold_reversal rather than broad event coverage.

### Was sample size sufficient for confidence?

No. Two windows failed minimum event coverage and the dominant tag share was too high.

### Does this justify another H1 iteration?

No. The current H1 design does not clear the gate contract and should not be tuned further before moving to H3.

---

## 9. Final Verdict

**Verdict**: KILL

**Reason**:  
The event-driven proxy setup failed the H1 contract on sample sufficiency, benchmark superiority, predictive support, and cost survivability. Only one window had enough events to evaluate, and that window still lost decisively to buy-hold. The evidence is not broad enough to support another H1 iteration. The correct next action is to stop H1 and move to H3.

**Next action**:

- kill H1 and move to H3

---

## 10. Notes

This run uses market-proxy event tags because the stationary dataset does not contain usable calendar event labels. Sentiment/news columns in the stationary frame were effectively zero, so the H1 run focused on volatility, range, momentum, and reversal proxies only.

Ledger: [logs/stage2_h1_results_ledger.json](../logs/stage2_h1_results_ledger.json)

Generated reports:

- [results/stage2_h1/stage2_h1_logistic_report_20260418_170747.md](../results/stage2_h1/stage2_h1_logistic_report_20260418_170747.md)
- [results/stage2_h1/stage2_h1_tree_report_20260418_170747.md](../results/stage2_h1/stage2_h1_tree_report_20260418_170747.md)
