# Rolling-Window Validation Report

Generated at: 2026-04-18T20:00:19.771727+00:00

## Configuration

- Train/Val/Test split: 40%/30%/30%
- Window slide: 33%
- Number of windows: 1

---

## Results by Window


### Window 0 (2023-10-05 - 2026-03-27)

| Model | Test R² | Test Return | Win Rate |
|-------|---------|-------------|----------|
| linear | -0.0190 | +0.0362 | 53.2% |
| rf | -0.2242 | -0.6088 | 51.3% |

---

## Aggregate Statistics

### LINEAR

**Test R² Stability**
- Mean: -0.0190
- Std: 0.0000
- CV: 0.000
- Range: [-0.0190, -0.0190]

**Test Return Stability**
- Mean: +0.0362
- Std: 0.0000
- CV: 0.000
- Range: [+0.0362, +0.0362]

**Win Rate**
- Mean: 53.2%
- Std: 0.000%

### RF

**Test R² Stability**
- Mean: -0.2242
- Std: 0.0000
- CV: 0.000
- Range: [-0.2242, -0.2242]

**Test Return Stability**
- Mean: -0.6088
- Std: 0.0000
- CV: 0.000
- Range: [-0.6088, -0.6088]

**Win Rate**
- Mean: 51.3%
- Std: 0.000%


---

## Interpretation

**Stability Criteria**:
- **Good**: CV < 0.5 (consistent across windows)
- **Acceptable**: CV < 1.0 (moderate variation)
- **Poor**: CV > 1.0 or negative mean R² (unstable or no signal)

**Decision**:
- If R² mean > 0.01 AND CV < 1.0 → Signal robust, ready for RL escalation
- If R² mean ≤ 0.01 OR CV > 1.0 → Signal not regime-stable, need feature engineering
- If win_rate near 50% across windows → Trading success may be random luck
