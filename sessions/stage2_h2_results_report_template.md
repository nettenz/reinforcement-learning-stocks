# Stage 2 H2 Results Report Template

Project: reinforcement-learning-stocks  
Date: [YYYY-MM-DD]  
Hypothesis: H2 — Longer-Horizon Targets  
Run ID: [run_id_here]  
Status: [planned | running | pass | fail | killed]

---

## 1. Run Metadata

- **Dataset version**: [dataset_version]
- **Feature set version**: [feature_set_version]
- **Target variant**: [1d | 3d | 5d | directional_threshold]
- **Model family**: [linear/logistic | tree-based | naive_momentum]
- **Rolling-window scheme**: [describe windows]
- **Cost assumptions**: [transaction cost, slippage, turnover rule]
- **Recent window included**: [yes/no]

---

## 2. Thesis Being Tested

State the exact H2 thesis for this run:

> Longer-horizon targets may reduce noise sensitivity and improve stability versus short-horizon targets.

Any deviation from the Stage 2 brief must be explicitly stated here.

---

## 3. Benchmarks

This run must be compared against:

- buy-hold
- naive momentum
- flat/no-trade baseline (when relevant)

---

## 4. Window-Level Metrics

| Window | Period | Gross Return | Net Return | Buy-Hold Return | Momentum Return | Net Benchmark Gap | Net Sharpe | Benchmark Sharpe Gap | Max DD | Turnover | Predictive Metric | Verdict |
|--------|--------|--------------|------------|-----------------|-----------------|-------------------|------------|----------------------|--------|----------|-------------------|---------|
| 0 | [period] | [x] | [x] | [x] | [x] | [x] | [x] | [x] | [x] | [x] | [x] | [pass/fail] |
| 1 | [period] | [x] | [x] | [x] | [x] | [x] | [x] | [x] | [x] | [x] | [x] | [pass/fail] |
| 2 | [period] | [x] | [x] | [x] | [x] | [x] | [x] | [x] | [x] | [x] | [x] | [pass/fail] |

---

## 5. Aggregate Metrics

- **Mean gross return**: [value]
- **Mean net return**: [value]
- **Mean net benchmark gap**: [value]
- **Mean net Sharpe**: [value]
- **Mean benchmark Sharpe gap**: [value]
- **Primary predictive metric (mean)**: [value]
- **Stability CV**: [value]
- **2/3 benchmark pass achieved**: [yes/no]
- **Recent window pass**: [yes/no]

---

## 6. Gate Check

### Global Gates

- **G1 Benchmark Superiority**: [PASS/FAIL]
- **G2 Economic Robustness**: [PASS/FAIL]
- **G3 Stability**: [PASS/FAIL]
- **G4 Predictive Support**: [PASS/FAIL]
- **G5 Cost Survivability**: [PASS/FAIL]

### H2-Specific Gates

- **H2-1 Positive mean net edge for at least one horizon**: [PASS/FAIL]
- **H2-2 2/3 windows beat buy-hold or momentum**: [PASS/FAIL]
- **H2-3 Recent window does not collapse**: [PASS/FAIL]

### Hard Stop Conditions Triggered

- [ ] only one window positive
- [ ] buy-hold cleanly dominates
- [ ] net edge non-positive after costs
- [ ] recent window fails severely
- [ ] leakage or benchmark inconsistency detected

---

## 7. Interpretation

### What worked
[brief summary]

### What failed
[brief summary]

### Is the edge real or likely artifact?
[brief judgment]

### Does this justify another H2 iteration?
[yes/no and why]

---

## 8. Final Verdict

**Verdict**: [PASS | FAIL | KILL]

**Reason**:  
[one-paragraph decision summary tied directly to the gate contract]

**Next action**:
- [continue H2 refinement]
- [run next H2 variant]
- [kill H2 and move to H1]

---

## 9. Notes

Add any anomalies, caveats, leakage checks, or benchmark interpretation notes here.
