# Staging Ready
**Signed off:** 2026-04-30  
**Deployment scope:** NVDA + AMD (paper trade), AAPL monitor-only

---

## Exp 9 Gate Results

### NVDA — PASS

| Seed | Buys | Accuracy |
|------|------|----------|
| 4 | 222 | 0.527 |
| 6 | 295 | 0.525 |
| 8 | 300 | 0.527 |
| **Ensemble** | **309** | **0.521** |

`agreement=1.00  avg_conf=0.75  unanimous_rate=0.24`

| Gate | Result |
|------|--------|
| G1 ensemble_acc >= min_seed_acc − 0.5% (0.521 >= 0.520) | PASS |
| G2 majority_agreement >= 60% (1.00 >= 0.60) | PASS |
| G3 unanimous_rate >= 20% (0.24 >= 0.20) | PASS |

### AMD — PASS

| Seed | Buys | Accuracy |
|------|------|----------|
| 5 | 309 | 0.528 |
| 2 | 284 | 0.521 |
| 10 | 311 | 0.524 |
| **Ensemble** | **311** | **0.524** |

`agreement=1.00  avg_conf=1.00  unanimous_rate=0.99`

| Gate | Result |
|------|--------|
| G1 ensemble_acc >= min_seed_acc − 0.5% (0.524 >= 0.516) | PASS |
| G2 majority_agreement >= 60% (1.00 >= 0.60) | PASS |
| G3 unanimous_rate >= 20% (0.99 >= 0.20) | PASS |

---

## Staging Package Contents

```
staging/
├── models/
│   ├── ensemble_config.json
│   ├── nvda/  nvda_seed4.zip  nvda_seed6.zip  nvda_seed8.zip
│   ├── aapl/  aapl_seed6.zip  aapl_seed8.zip  aapl_seed1.zip
│   └── amd/   amd_seed5.zip   amd_seed2.zip   amd_seed10.zip
├── src/
│   ├── ensemble.py
│   ├── trading_agent.py
│   ├── feature_engineering.py
│   └── trading_env.py
├── metrics/
│   ├── nvda_leaderboard.csv
│   ├── aapl_leaderboard.csv
│   └── amd_leaderboard.csv
└── STAGING_READY.md
```

---

## Next Milestone — Paper Trade

- **Tickers:** NVDA, AMD
- **Duration:** 2 weeks from start date
- **Acceptance criterion:** cumulative return > +5% over the 2-week window
- **If passed:** escalate to live capital (start at 1% of portfolio per signal)
- **If failed:** investigate market regime shift vs. test period (2025-01-03 – 2026-04-02)
