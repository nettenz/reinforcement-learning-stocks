Viewed Analyzing%20MU%20Sweep%20Results.md:1-27
Viewed Analyzing%20MU%20Sweep%20Results.md:1-736

Full picture. This is a thorough strategy-refinement-analyst output. Here's what it means for the next experiment batch and how to translate it into compliant one-liners.

---

## Handoff Summary: What Strategy-Refinement Concluded

| Finding | Implication |
|---------|------------|
| Clean pair (seeds 7, 42) has real alpha (+1.26 to +1.40) | Signal exists — don't abandon MU |
| Seed 3 is catastrophic across **all three sweeps** | Must diagnose or formally exclude |
| `turnover_v2` (0.20/0.30) caused collapse | Light penalty (0.005–0.03) is the right next probe |
| The proposed Exp A/B commands use `run_exp9_walkforward.py` | **Wrong script** — use `experiments.py` for sweeps |

---

## Corrected v3 Experiment Batch

### Priority 1 — Light Turnover Penalty (4 values × 5 seeds = 20 runs, two commands)

The analyst proposed 4 penalty values. Per framework, run them in two batches of 10 to keep batch size ≤ 20:

**Batch A-low (0.005 and 0.01):**
```powershell
.\.venv\Scripts\python.exe src\experiments.py --ticker mu --reward-mode sharpe --ent-coefs 0.02 --timesteps 40000 --seeds 3,7,13,21,42 --execution-mode next_bar --reward-hold-penalty-scale 0.01 --reward-turnover-penalty-scale 0.005 --max-weight-delta-per-step 0.10 --use-stationary-features --run-label "sweep_mu_overtrade_fix_v3" --append
```
```powershell
.\.venv\Scripts\python.exe src\experiments.py --ticker mu --reward-mode sharpe --ent-coefs 0.02 --timesteps 40000 --seeds 3,7,13,21,42 --execution-mode next_bar --reward-hold-penalty-scale 0.01 --reward-turnover-penalty-scale 0.01 --max-weight-delta-per-step 0.10 --use-stationary-features --run-label "sweep_mu_overtrade_fix_v3" --append
```

**Evaluate after batch A-low** — if 0.005 or 0.01 resolves trate without alpha collapse, skip A-high:
```powershell
python scripts/evaluate_sweep.py --leaderboard data/experiment_leaderboard.csv --label sweep_mu_overtrade_fix_v3
```

**Batch A-high (0.02 and 0.03) — only if A-low still overtredes:**
```powershell
.\.venv\Scripts\python.exe src\experiments.py --ticker mu --reward-mode sharpe --ent-coefs 0.02 --timesteps 40000 --seeds 3,7,13,21,42 --execution-mode next_bar --reward-hold-penalty-scale 0.01 --reward-turnover-penalty-scale 0.02 --max-weight-delta-per-step 0.10 --use-stationary-features --run-label "sweep_mu_overtrade_fix_v3" --append
```
```powershell
.\.venv\Scripts\python.exe src\experiments.py --ticker mu --reward-mode sharpe --ent-coefs 0.02 --timesteps 40000 --seeds 3,7,13,21,42 --execution-mode next_bar --reward-hold-penalty-scale 0.01 --reward-turnover-penalty-scale 0.03 --max-weight-delta-per-step 0.10 --use-stationary-features --run-label "sweep_mu_overtrade_fix_v3" --append
```

---

### Priority 2 — Seed 3 Diagnostic (run in parallel or after Priority 1)

Single seed, 3 ent_coef values, 3 timestep values = 9 runs. Use two commands to keep each ≤ 5:

```powershell
.\.venv\Scripts\python.exe src\experiments.py --ticker mu --reward-mode sharpe --ent-coefs 0.02,0.05,0.10 --timesteps 40000 --seeds 3 --execution-mode next_bar --reward-hold-penalty-scale 0.01 --reward-turnover-penalty-scale 0.10 --max-weight-delta-per-step 0.10 --use-stationary-features --run-label "sweep_mu_seed3_diag" --append
```
```powershell
.\.venv\Scripts\python.exe src\experiments.py --ticker mu --reward-mode sharpe --ent-coefs 0.02,0.05,0.10 --timesteps 80000 --seeds 3 --execution-mode next_bar --reward-hold-penalty-scale 0.01 --reward-turnover-penalty-scale 0.10 --max-weight-delta-per-step 0.10 --use-stationary-features --run-label "sweep_mu_seed3_diag" --append
```

```powershell
python scripts/evaluate_sweep.py --leaderboard data/experiment_leaderboard.csv --label sweep_mu_seed3_diag
```

> **Experiment C (transaction cost)** — hold until Priority 1 results are in. Only triggers if every penalty value from 0.005–0.03 still shows trate > 80%.