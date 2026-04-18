1. **Research summary**  
Stage 1 remains blocked at signal_weak after Step 9 main and confirmation, with the same structural pattern as Step 8: baseline gate fails on all three tickers while trading gate passes against flat. Evidence: stage1_gate_report_step9_20260418-150930.json, stage1_gate_report_step9_confirm_20260418-150930.json, stage1_gate_report_step8_20260418-145345.json, stage1_gate_report_step8_confirm_20260418-145345.json.

2. **What improved**  
- Execution-quality signal vs flat remained robust across all three tickers in both Step 9 reports.  
- AAPL main baseline test R2 moved from negative in Step 8 to slightly positive in Step 9, but still under gate threshold.  
- AMD trading return increased versus Step 8 in both main and confirmation comparisons.

3. **What degraded or remains weak**  
- Baseline predictive gate still fails for AAPL, AMD, NVDA in both Step 9 reports.  
- Validation R2 remains negative across best-per-ticker baseline selections, indicating weak generalization.  
- NVDA and AAPL trading strength softened versus Step 8 in confirmation context, so gains are not uniformly improving.

4. **Most likely explanations**  
- Evidence-backed observations: persistent negative validation R2 with only marginal test positives indicates predictive signal quality is still below gate standard.  
- Plausible hypotheses: target construction still mixes weak alpha with market/sector drift, and feature timing/lag alignment may be suppressing genuine short-horizon signal.  
- Unknowns needing tests: whether minor threshold relaxation reveals near-pass structure by ticker, and whether strict lag audits plus residualized targets can shift validation R2 from negative to non-negative.

5. **Confidence level for current conclusions**  
Medium-high. Confidence is high on the top-line decision (stay in Stage 1) because main and confirmation agree; medium on causal diagnosis until target-residualization and lag-integrity tests are run.

6. **Recommended next experiment batch**  
This is justified because Step 9 already exhausted split sensitivity and ticker specialization without clearing the baseline gate.

1. Threshold criterion stress-test (diagnostic only, not promotion).  
Goal: quantify margin-to-pass by ticker.  
Variables: baseline gate validation/test R2 threshold sweep around current cutoff.  
Hold constant: Step 9 best configs, same data/splits.  
Success: clear near-pass map that identifies realistic threshold distance by ticker.  
Failure: no near-pass even under mild relaxation, implying deeper signal issue.

2. Target redesign micro-batch (residualized + robust scaling).  
Goal: isolate idiosyncratic predictive content.  
Variables: add market/sector-demeaned return targets and robust scaling variants.  
Hold constant: model families, split protocol, horizons.  
Success: validation R2 improves to non-negative with stable test behavior on at least 2 tickers.  
Failure: no meaningful lift, implying target redesign alone is insufficient.

3. Feature timing integrity check + minimal rerun.  
Goal: eliminate leakage/misalignment and recover signal consistency.  
Variables: strict lag audit of engineered features for 1h/2h/3h and corrected feature set rerun.  
Hold constant: small baseline model set, same gate logic.  
Success: validation R2 shift toward non-negative and reduced val/test inconsistency.  
Failure: unchanged negative validation R2, indicating feature timing is not the primary blocker.

7. **Priority order**  
1. Feature timing integrity check first (highest information gain, low implementation risk).  
2. Target redesign micro-batch second (highest potential performance impact if timing is clean).  
3. Threshold stress-test third (diagnostic framing tool for decision clarity, not optimization target).

8. **Success/failure interpretation plan**  
- If timing audit plus rerun materially lifts validation R2: proceed with a focused confirmation batch before any broader expansion.  
- If residualized targets lift validation and test together across seeds: treat as a valid baseline-signal lead and run confirmation gates.  
- If only threshold relaxation enables pass: classify as criterion sensitivity, not robust signal discovery.  
- If all three fail: conclude current feature/target stack is insufficient and pivot to deeper signal-engineering diagnostics rather than RL escalation.

9. **Leaderboard comparability impact (REQUIRED)**  
Medium. Step 9 changed split settings and ticker-specific target/horizon mapping, so direct rank comparability to Step 8 is partial; gate outcome comparability remains high because pass/fail logic is unchanged.

10. **Promotion readiness assessment**  
Not ready for promotion. Stage 1 remains signal_weak, baseline gate is still the blocker, and RL escalation should remain paused until baseline predictive evidence clears with confirmation stability.