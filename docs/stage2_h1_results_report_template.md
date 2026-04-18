# Stage 2 H1 Results Report Template

Project: reinforcement-learning-stocks  
Date: [YYYY-MM-DD]  
Hypothesis: H1 — Event-Driven Prediction  
Run ID: [run_id_here]  
Status: [planned | running | pass | fail | killed]

---

## 1. Run Metadata

- **Dataset version**: [dataset_version]
- **Feature set version**: [feature_set_version]
- **Event tag set**: [list tags]
- **Event detection rules**: [brief summary or file path]
- **Model family**: [logistic | random_forest | gradient_boosting | threshold_rule]
- **Rolling-window scheme**: [describe windows]
- **Cost assumptions**: [transaction cost, slippage, turnover rule]
- **Recent window included**: [yes/no]

---

## 2. Thesis Being Tested

State the exact H1 thesis for this run:

> Sparse high-information event contexts may offer better signal-to-noise than continuous prediction.

Any deviation from the Stage 2 brief must be explicitly stated here.

---

## 3. Sample Sufficiency Check

| Window | Period | Total Event Count | Earnings | Macro | Vol Expansion | Abnormal Volume | Sentiment Shock | Sufficiency Verdict |
|--------|--------|-------------------|----------|-------|---------------|-----------------|-----------------|--------------------|
| 0 | [period] | [x] | [x] | [x] | [x] | [x] | [x] | [pass/fail] |
| 1 | [period] | [x] | [x] | [x] | [x] | [x] | [x] | [pass/fail] |
| 2 | [period] | [x] | [x] | [x] | [x] | [x] | [x] | [pass/fail] |

### Auto-Kill Check
- [ ] insufficient total sample count
- [ ] one event type dominates
- [ ] recent-window coverage insufficient

---

## 4. Benchmarks

This run must be compared against:

- buy-hold
- event-relevant naive baseline
- flat/no-trade baseline

---

## 5. Window-Level Metrics

| Window | Period | Gross Return | Net Return | Buy-Hold Return | Event Baseline Return | Net Benchmark Gap | Net Sharpe | Benchmark Sharpe Gap | Max DD | Turnover | Predictive Metric | Event Cluster Driver | Verdict |
|--------|--------|--------------|------------|-----------------|-----------------------|-------------------|------------|----------------------|--------|----------|-------------------|----------------------|---------|
| 0 | [period] | [x] | [x] | [x] | [x] | [x] | [x] | [x] | [x] | [x] | [x] | [cluster] | [pass/fail] |
| 1 | [period] | [x] | [x] | [x] | [x] | [x] | [x] | [x] | [x] | [x] | [x] | [cluster] | [pass/fail] |
| 2 | [period] | [x] | [x] | [x] | [x] | [x] | [x] | [x] | [x] | [x] | [x] | [cluster] | [pass/fail] |

---

## 6. Aggregate Metrics

- **Mean gross return**: [value]
- **Mean net return**: [value]
- **Mean net benchmark gap**: [value]
- **Mean net Sharpe**: [value]
- **Mean benchmark Sharpe gap**: [value]
- **Primary predictive metric (mean)**: [value]
- **Stability CV**: [value]
- **2/3 benchmark pass achieved**: [yes/no]
- **Recent window pass**: [yes/no]
- **Single-event-cluster dependency**: [yes/no]

---

## 7. Gate Check

### Global Gates

- **G1 Benchmark Superiority**: [PASS/FAIL]
- **G2 Economic Robustness**: [PASS/FAIL]
- **G3 Stability**: [PASS/FAIL]
- **G4 Predictive Support**: [PASS/FAIL]
- **G5 Cost Survivability**: [PASS/FAIL]

### H1-Specific Gates

- **H1-1 Event sample count sufficient in each window**: [PASS/FAIL]
- **H1-2 At least 2/3 windows show positive net edge**: [PASS/FAIL]
- **H1-3 Predictive quality above naive**: [PASS/FAIL]
- **H1-4 Edge not carried by one event cluster**: [PASS/FAIL]
- **H1-5 Edge survives transaction costs**: [PASS/FAIL]

### Hard Stop Conditions Triggered

- [ ] performance appears in only one window
- [ ] insufficient event count
- [ ] one event type explains almost all gains
- [ ] net edge non-positive after costs
- [ ] recent window fails severely
- [ ] leakage or benchmark inconsistency detected

---

## 8. Interpretation

### What worked
[brief summary]

### What failed
[brief summary]

### Was the edge broad or event-cluster-specific?
[brief judgment]

### Was sample size sufficient for confidence?
[yes/no and why]

### Does this justify another H1 iteration?
[yes/no and why]

---

## 9. Final Verdict

**Verdict**: [PASS | FAIL | KILL]

**Reason**:  
[one-paragraph decision summary tied directly to the gate contract]

**Next action**:
- [continue H1 refinement]
- [run next H1 variant]
- [kill H1 and move to H3]

---

## 10. Notes

Add any anomalies, caveats, leakage checks, benchmark interpretation notes, or event-labeling concerns here.
