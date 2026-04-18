# Rolling-Window Validation Report

Generated at: 2026-04-18T20:01:15.481564+00:00

## Configuration

- Train/Val/Test split: 20%/20%/20%
- Window slide: 33%
- Number of windows: 3

---

## Results by Window


### Window 0 (2019-12-20 - 2022-12-06)

| Model | Test R² | Test Return | Win Rate |
|-------|---------|-------------|----------|
| linear | -8.4183 | +1.2535 | 54.4% |
| rf | -2.7481 | -0.6775 | 47.1% |

### Window 1 (2021-08-06 - 2024-07-25)

| Model | Test R² | Test Return | Win Rate |
|-------|---------|-------------|----------|
| linear | -0.0399 | -0.3092 | 47.2% |
| rf | -0.5479 | -0.3825 | 47.8% |

### Window 2 (2023-03-23 - 2026-03-13)

| Model | Test R² | Test Return | Win Rate |
|-------|---------|-------------|----------|
| linear | -0.6778 | +0.7025 | 50.9% |
| rf | -0.4934 | -0.2823 | 48.7% |

---

## Aggregate Statistics

### LINEAR

**Test R² Stability**
- Mean: -3.0453
- Std: 3.8082
- CV: 1.250
- Range: [-8.4183, -0.0399]

**Test Return Stability**
- Mean: +0.5490
- Std: 0.6472
- CV: 1.179
- Range: [-0.3092, +1.2535]

**Win Rate**
- Mean: 50.8%
- Std: 2.904%

### RF

**Test R² Stability**
- Mean: -1.2631
- Std: 1.0503
- CV: 0.832
- Range: [-2.7481, -0.4934]

**Test Return Stability**
- Mean: -0.4474
- Std: 0.1678
- CV: 0.375
- Range: [-0.6775, -0.2823]

**Win Rate**
- Mean: 47.9%
- Std: 0.661%


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
