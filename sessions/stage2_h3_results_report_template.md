# Stage 2 H3 Results Report Template

Project: reinforcement-learning-stocks  
Date: [YYYY-MM-DD]  
Hypothesis: H3 — Cross-Sectional Ranking  
Run ID: [run_id_here]  
Status: [planned | running | pass | fail | killed]

---

## 1. Run Metadata

- **Dataset version**: [dataset_version]
- **Feature set version**: [feature_set_version]
- **Universe**: [list assets]
- **Ranking target**: [definition]
- **Model family**: [linear_rank | tree_rank | momentum_rank]
- **Rolling-window scheme**: [describe windows]
- **Rebalance frequency**: [weekly | monthly | other]
- **Portfolio rule**: [long-only | long/short]
- **Selection rule**: [top-1 | top-bucket | other]
- **Weighting rule**: [equal weight | other]
- **Cost assumptions**: [transaction cost, slippage, turnover rule]
- **Recent window included**: [yes/no]

---

## 2. Thesis Being Tested

State the exact H3 thesis for this run:

> Relative ranking may be more learnable than absolute direction and may reveal durable relative-strength structure.

Any deviation from the Stage 2 brief must be explicitly stated here.

---

## 3. Universe Sufficiency Check

| Window | Period | Asset Count Available | Rebalance Observations | Sufficiency Verdict |
|--------|--------|-----------------------|------------------------|--------------------|
| 0 | [period] | [x] | [x] | [pass/fail] |
| 1 | [period] | [x] | [x] | [pass/fail] |
| 2 | [period] | [x] | [x] | [pass/fail] |

### Auto-Kill Check
- [ ] insufficient universe size
- [ ] missing assets break ranking consistency
- [ ] recent-window coverage insufficient

---

## 4. Benchmarks

This run must be compared against:

- equal-weight portfolio
- buy-hold
- momentum ranking baseline

---

## 5. Window-Level Metrics

| Window | Period | Gross Return | Net Return | Equal-Weight Return | Buy-Hold Return | Momentum Rank Return | Net Benchmark Gap | Net Sharpe | Benchmark Sharpe Gap | Max DD | Turnover | Rank Metric | Dominant Ticker | Verdict |
|--------|--------|--------------|------------|---------------------|-----------------|----------------------|-------------------|------------|----------------------|--------|----------|-------------|-----------------|---------|
| 0 | [period] | [x] | [x] | [x] | [x] | [x] | [x] | [x] | [x] | [x] | [x] | [x] | [ticker] | [pass/fail] |
| 1 | [period] | [x] | [x] | [x] | [x] | [x] | [x] | [x] | [x] | [x] | [x] | [x] | [ticker] | [pass/fail] |
| 2 | [period] | [x] | [x] | [x] | [x] | [x] | [x] | [x] | [x] | [x] | [x] | [x] | [ticker] | [pass/fail] |

---

## 6. Aggregate Metrics

- **Mean gross return**: [value]
- **Mean net return**: [value]
- **Mean net benchmark gap**: [value]
- **Mean net Sharpe**: [value]
- **Mean benchmark Sharpe gap**: [value]
- **Primary ranking metric (mean)**: [value]
- **Stability CV**: [value]
- **2/3 benchmark pass achieved**: [yes/no]
- **Recent window pass**: [yes/no]
- **Single-ticker dominance**: [yes/no]
- **Largest ticker contribution share**: [value]

---

## 7. Gate Check

### Global Gates

- **G1 Benchmark Superiority**: [PASS/FAIL]
- **G2 Economic Robustness**: [PASS/FAIL]
- **G3 Stability**: [PASS/FAIL]
- **G4 Predictive Support**: [PASS/FAIL]
- **G5 Cost Survivability**: [PASS/FAIL]

### H3-Specific Gates

- **H3-1 At least 2/3 windows outperform equal-weight and buy-hold**: [PASS/FAIL]
- **H3-2 Ranking quality persists across windows**: [PASS/FAIL]
- **H3-3 Performance is not explained by one ticker**: [PASS/FAIL]
- **H3-4 Turnover-adjusted net edge remains positive**: [PASS/FAIL]

### Hard Stop Conditions Triggered

- [ ] only one window positive
- [ ] equal-weight or buy-hold cleanly dominates
- [ ] rank ordering unstable or near random
- [ ] one ticker explains almost all gains
- [ ] net edge non-positive after costs
- [ ] recent window fails severely
- [ ] leakage or benchmark inconsistency detected

---

## 8. Ticker Contribution Analysis

| Ticker | Contribution to Edge | Share of Total Edge | Notes |
|--------|----------------------|---------------------|-------|
| [ticker] | [value] | [value] | [notes] |
| [ticker] | [value] | [value] | [notes] |
| [ticker] | [value] | [value] | [notes] |

### Dominance Verdict
[Does one ticker dominate the result? yes/no and why]

---

## 9. Interpretation

### What worked
[brief summary]

### What failed
[brief summary]

### Was the ranking edge broad or ticker-specific?
[brief judgment]

### Was the rank quality stable enough to trust?
[yes/no and why]

### Does this justify another H3 iteration?
[yes/no and why]

---

## 10. Final Verdict

**Verdict**: [PASS | FAIL | KILL]

**Reason**:  
[one-paragraph decision summary tied directly to the gate contract]

**Next action**:
- [continue H3 refinement]
- [run next H3 variant]
- [kill H3 and exit Stage 2]

---

## 11. Notes

Add any anomalies, leakage checks, universe issues, benchmark interpretation notes, or portfolio construction caveats here.