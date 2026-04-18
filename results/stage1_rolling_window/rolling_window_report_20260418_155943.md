# Rolling-Window Validation Report

Generated at: 2026-04-18T19:59:42.881748+00:00

## Configuration

- Train/Val/Test split: 60%/20%/20%
- Window slide: 25%
- Number of windows: 1

---

## Results by Window


### Window 0 (2024-08-02 - 2026-03-27)

| Model | Test R² | Test Return | Win Rate |
|-------|---------|-------------|----------|
| linear | -0.0393 | +0.1471 | 49.6% |
| rf | -0.2853 | -0.1083 | 48.2% |

---

## Aggregate Statistics

### LINEAR

**Test R² Stability**
- Mean: -0.0393
- Std: 0.0000
- CV: 0.000
- Range: [-0.0393, -0.0393]

**Test Return Stability**
- Mean: +0.1471
- Std: 0.0000
- CV: 0.000
- Range: [+0.1471, +0.1471]

**Win Rate**
- Mean: 49.6%
- Std: 0.000%

### RF

**Test R² Stability**
- Mean: -0.2853
- Std: 0.0000
- CV: 0.000
- Range: [-0.2853, -0.2853]

**Test Return Stability**
- Mean: -0.1083
- Std: 0.0000
- CV: 0.000
- Range: [-0.1083, -0.1083]

**Win Rate**
- Mean: 48.2%
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
