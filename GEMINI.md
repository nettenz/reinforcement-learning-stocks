# Gemini Context

This project is currently focused on stabilizing a Reinforcement Learning architecture (Binary PPO) for stock trading (specifically mega-caps like NVDA, AMD, AAPL, AMZN, GOOGL, MU).

## Current Focus (May 2026)
1. **Binary PPO Retrofit:** Migrating older SAC models (AMD, NVDA) and previously failed tickers (AAPL) to the new Binary PPO + min-hold constraints architecture.
2. **Infrastructure Fixes:** Investigating and fixing an OS-level file descriptor limit ("Too many open files") issue that crashes parallel environment training during these PPO sweeps.
3. **Exit Signal Development:** Deferred but planned. Phase 1 will implement confidence-based, trailing stop, and time-based rules in `src/exit_manager.py`.

Please refer to `PROJECT_STATE.md` and `session.md` for the latest granular details on experiment sweeps, architecture states, and blockages.

---

Ran command: `grep -n "reward-turnover-penalty-scale" src/experiments.py || echo "Not found"`

### 1. Research summary
The `--n-envs 1` bypass successfully completed sweeps without FD leaks. **AMD** successfully adopted the Binary PPO architecture, producing highly profitable (Alpha +1.82) and stable (clean CV 0.14) configs with ideal trade rates (62.3%), missing full promotion only narrowly on val/test drift (0.055 vs 0.050). However, **NVDA** and **AAPL** both suffered complete action collapse (0.0% trade rate), reverting to inaction bias under the default Binary PPO penalty structures.

### 2. What improved
- **Parallel Environment Stability:** The OS-level "Too many open files" FD limit was successfully bypassed using `--n-envs 1`.
- **AMD Architecture Stabilization:** The `amd-ppo-baseline-fd-bypass` sweep successfully placed configs perfectly in the 60-75% trade rate target zone, a major fix from previous 99%+ overtrading. Clean CV is exceptional (0.14 - 0.28) and Alpha is massive (+0.83 to +1.82).

### 3. What degraded or remains weak
- **NVDA and AAPL Action Collapse:** Both tickers exhibited 100% inaction bias (0.0% trade rate across all 15 configs). The models learned that "doing nothing" was the only way to avoid the turnover/transaction penalties.
- **AMD Val/Test Drift:** AMD's drift is marginally high (0.055 vs 0.05 threshold), preventing immediate 6/6 promotion by a very thin margin.

### 4. Most likely explanations
- **Evidence-backed observations:** Binary PPO directly fixes AMD's overtrading while retaining massive alpha. NVDA and AAPL are under-trading to zero, meaning the penalty constraints are too tight for their signal distribution.
- **Plausible hypotheses:** For NVDA and AAPL, the default `reward_turnover_penalty_scale` acts as an insurmountable barrier, preventing exploration out of the flat state. For AMD, the drift (0.055) is likely due to the extreme bull run in its test period vs val period; slightly higher entropy and longer training (more timesteps) may generalize the policy enough to shrink that drift below 0.05.
- **Unknowns requiring additional tests:** What exact turnover penalty threshold allows NVDA and AAPL to trade profitably without reverting to whipsawing? Does AMD's drift shrink with extended timesteps?

### 5. Confidence level for current conclusions
- **High** for AMD's stabilization via Binary PPO. 
- **High** for the inaction bias diagnosis on NVDA/AAPL. 
- **Medium** for the exact penalty and entropy parameters required to resolve these final blockers.

### 6. Recommended next experiment batch
1. **AMD Drift Mitigation:** Extend timesteps and test slightly higher entropy to encourage generalization and pull Val/Test drift below 0.05.
2. **NVDA / AAPL Turnover Penalty Ablation:** Sweep `reward-turnover-penalty-scale` at lower values (0.01, 0.05) to break the 0.0% trade rate collapse and restore trading.

### 7. Next proposed experiments or runs

```zsh
# Activate venv first (if not already active)
source .venv/bin/activate

# Run 1: AMD Drift Mitigation (Extended Timesteps & Entropy)
python src/experiments.py \
    --ticker amd \
    --reward-mode sharpe \
    --ent-coefs 0.02,0.05,0.08 \
    --timesteps 80000 \
    --seeds 3,7,13,21,42 \
    --execution-mode next_bar \
    --binary-actions \
    --min-hold-bars 3 \
    --max-weight-delta-per-step 0.10 \
    --use-stationary-features \
    --n-envs 1 \
    --run-label "amd-ppo-drift-fix" \
    --append

# Run 2: NVDA Inaction Unstick (Turnover Penalty Ablation)
python src/experiments.py \
    --ticker nvda \
    --reward-mode sharpe \
    --ent-coefs 0.02,0.05 \
    --timesteps 50000 \
    --seeds 3,7,13,21,42 \
    --execution-mode next_bar \
    --binary-actions \
    --min-hold-bars 3 \
    --max-weight-delta-per-step 0.10 \
    --use-stationary-features \
    --reward-turnover-penalty-scale 0.01,0.05 \
    --n-envs 1 \
    --run-label "nvda-ppo-unstick" \
    --append

# Run 3: AAPL Inaction Unstick (Turnover Penalty Ablation)
python src/experiments.py \
    --ticker aapl \
    --reward-mode sharpe \
    --ent-coefs 0.02,0.05 \
    --timesteps 50000 \
    --seeds 3,7,13,21,42 \
    --execution-mode next_bar \
    --binary-actions \
    --min-hold-bars 3 \
    --max-weight-delta-per-step 0.10 \
    --use-stationary-features \
    --reward-turnover-penalty-scale 0.01,0.05 \
    --n-envs 1 \
    --run-label "aapl-ppo-unstick" \
    --append
```

**Post-sweep evaluation commands:**
```zsh
python scripts/evaluate_sweep.py --leaderboard data/experiment_leaderboard.csv --label amd-ppo-drift-fix
python scripts/evaluate_sweep.py --leaderboard data/experiment_leaderboard.csv --label nvda-ppo-unstick
python scripts/evaluate_sweep.py --leaderboard data/experiment_leaderboard.csv --label aapl-ppo-unstick
```

### 8. Priority order
1. **`amd-ppo-drift-fix`**: AMD is 0.005 away from full promotion and passed 5/6 gates with incredible Alpha/CV. This is the closest, highest-value win on the board.
2. **`nvda-ppo-unstick`**: NVDA is a known strong asset; fixing the inaction bias here proves our penalty tuning diagnosis works for Binary PPO.
3. **`aapl-ppo-unstick`**: AAPL recovery remains secondary to stabilizing the known mega-cap champions.

### 9. Success/failure interpretation plan
- **For AMD:** *Success* = Val/Test Drift shrinks to `<= 0.05` while retaining 5/5 other gates (full promotion). *Failure* = Drift remains > 0.05 (suggests the regime shift in AMD's recent data is simply too sharp for the 0.05 threshold to capture fairly; may require manual promotion override).
- **For NVDA/AAPL:** *Success* = Trade rate breaks out of 0.0% and enters the `[0.40, 1.00]` range with Alpha > 0. *Failure* = Trade rate bypasses the target zone and spikes directly to 99%+ (whipsaw), meaning the gap between inaction and overtrading is too narrow with the current feature set.

### 10. Leaderboard comparability impact (REQUIRED)
**Medium.** We are retaining the same base Binary PPO architecture (`--n-envs 1`), but shifting reward semantics (`reward_turnover_penalty_scale`) for NVDA/AAPL and training duration (`timesteps`) for AMD. This alters the search space but keeps the underlying action/observation space constant relative to the previous run. 

### 11. Promotion readiness assessment
- **AMD**: Very close. Passed 5/6 gates. Drift is 0.055 (limit 0.050). Not ready for automated script promotion, but qualitatively it is a massive architectural success.
- **NVDA**: Not ready (0/6 gates due to inaction).
- **AAPL**: Not ready (1/6 gates due to inaction).

---

### 12. Update (Double Loosen Phase)
**AMD (`amd-ppo-hold-fix`)** achieved a massive breakthrough. Relaxing the hold penalty to `0.01` made the policy slightly more selective (trade rate dropped from 62.3% to 42.9%), which successfully generalized the policy and pulled the Val/Test drift below the strict 0.05 threshold (0.0484). AMD passed all 6/6 gates and a Champion (Seed 13) was identified! The Binary PPO retrofit for AMD is formally solved and was successfully promoted through the Exp 9 walk-forward gates.

**NVDA** and **AAPL**, however, remain collapsed in inaction bias (0.0% trade rate); lowering the hold penalty alone was insufficient while the turnover penalty remained at 0.10.

### 13. Recommended next experiment batch
1. **NVDA / AAPL Double Loosening:** Run a final sweep for NVDA and AAPL crossing both penalties at their lowest bounds (`0.01` and `0.05`) simultaneously to break the inaction block.

### 14. Next proposed experiments or runs

**NVDA & AAPL Double Loosening Sweeps**
```zsh
# Run 1: NVDA Double Loosen
python src/experiments.py --ticker nvda --reward-mode sharpe --ent-coefs 0.02,0.05 --timesteps 50000 --seeds 3,7,13,21,42 --execution-mode next_bar --binary-actions --min-hold-bars 3 --max-weight-delta-per-step 0.10 --use-stationary-features --reward-hold-penalty-scale 0.01,0.05 --reward-turnover-penalty-scale 0.01,0.05 --n-envs 1 --run-label "nvda-ppo-double-loosen" --append

# Run 2: AAPL Double Loosen
python src/experiments.py --ticker aapl --reward-mode sharpe --ent-coefs 0.02,0.05 --timesteps 50000 --seeds 3,7,13,21,42 --execution-mode next_bar --binary-actions --min-hold-bars 3 --max-weight-delta-per-step 0.10 --use-stationary-features --reward-hold-penalty-scale 0.01,0.05 --reward-turnover-penalty-scale 0.01,0.05 --n-envs 1 --run-label "aapl-ppo-double-loosen" --append
```

**Post-sweep evaluation commands:**
```zsh
python scripts/evaluate_sweep.py --leaderboard data/experiment_leaderboard.csv --label nvda-ppo-double-loosen && python scripts/evaluate_sweep.py --leaderboard data/experiment_leaderboard.csv --label aapl-ppo-double-loosen
```