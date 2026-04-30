# EXPERIMENT SUITE v2.0
**Date:** April 29, 2026  
**State:** Post 148-run multi-ticker sweep · Global ceiling: 54.3% · Deployment floor: >55%  
**Objective:** Resolve all open blockers + push accuracy ceiling past deployment threshold

---

## CURRENT SNAPSHOT

| Ticker | Status | Best Score | Blocker |
|--------|--------|------------|---------|
| NVDA | CONDITIONAL | 0.6578 | 10-seed CV gate |
| AAPL | HOLD | 0.5828 | Leakage audit unresolved |
| AMD  | NOT READY | 0.4318 | Structural env fit |

**Global ceiling:** 54.3% test accuracy (NVDA)  
**Deployment floor:** >55%  
**Gap to close:** ~0.7 percentage points minimum

---

## SUITE STRUCTURE

```
Tier 1 — BLOCKERS      (run first, gates everything else)
  Exp A  AAPL Leakage Audit
  Exp C  NVDA 10-Seed Lock-In

Tier 2 — CEILING PUSH  (run in parallel after Tier 1)
  Exp E  Learning Rate Sweep
  Exp F  Gamma Sweep
  Exp G  Extended Timesteps
  Exp H  Feature Ablation

Tier 3 — STRUCTURAL    (run last, lower time priority)
  Exp B  AMD Env Recalibration
  Exp I  SAC vs PPO on NVDA
  Exp J  News Sentiment Ablation
  Exp K  Dollar-Neutral Pilot
```

---

## TIER 1 — BLOCKERS

### Exp A — AAPL Leakage Audit
**Priority:** URGENT  
**Failure mode addressed:** OVERFIT (suspected leakage)  
**Time estimate:** ~2h diagnostic + 1 rerun  
**Success criteria:** val/test gap < 10% on rerun

**Step 1 — Diagnostic rerun with date logging**
```powershell
.\.venv\Scripts\python.exe experiments.py `
  --ticker AAPL `
  --reward-mode sharpe `
  --ent-coefs 0.05 `
  --timesteps 20000 `
  --seeds 21 `
  --run-label "exp_a_aapl_audit_s21" `
  --append `
  --log-split-dates
```

**Step 2 — Boundary check (run after Step 1)**  
Manually inspect the printed train/val/test date ranges. Confirm:
- Train end date < Val start date (no overlap)
- Val end date < Test start date (no overlap)
- No future data in observation window at split boundaries

**Step 3 — Rerun with strict date enforcement**
```powershell
.\.venv\Scripts\python.exe experiments.py `
  --ticker AAPL `
  --reward-mode sharpe `
  --ent-coefs 0.02,0.05 `
  --timesteps 20000,40000 `
  --seeds 21,7,13 `
  --run-label "exp_a_aapl_clean_rerun" `
  --append
```

**Gate check:** If val/test gap collapses below 10% → data bug confirmed, proceed to promotion. If gap persists → regime mismatch, park AAPL pending robustness work.

---

### Exp C — NVDA 10-Seed Lock-In
**Priority:** HIGH  
**Failure mode addressed:** INSTABILITY (single-seed dominance)  
**Time estimate:** ~3-4h  
**Success criteria:** mean ranking_score ≥ 0.60, 95% CI includes test_acc ≥ 0.54

**Locked config:** 20k timesteps · ent_coef=0.02 · action_bonus=0.08 · reward-mode=sharpe

```powershell
.\.venv\Scripts\python.exe experiments.py `
  --ticker NVDA `
  --reward-mode sharpe `
  --ent-coefs 0.02 `
  --timesteps 20000 `
  --reward-action-bonus-scale 0.08 `
  --seeds 1,2,3,4,5,6,8,9,10,11 `
  --run-label "exp_c_nvda_10seed_lockin" `
  --append
```

**What to watch for:**
- CV gate: `test_return_cv_by_config` must drop below 1.0 across 10 seeds
- Seed distribution: if seeds 13 and 7 were dominant, new seeds should still cluster above 0.54
- Outlier seeds: flag any seed where test_acc < 0.51 — these indicate the policy is not robust

**Decision tree:**
- All seeds pass CV gate → PROMOTE to staging checkpoint ✅
- CV gate passes, 2+ seeds below 0.51 → one more focused Phase C sweep before promotion
- CV gate fails → diagnose instability, run Exp E (learning rate reduction) first

---

## TIER 2 — CEILING PUSH

*Goal: break through 54.3% global ceiling → target 55.5%+*  
*Run these concurrently after Tier 1 is in flight*

---

### Exp E — Learning Rate Sweep
**Priority:** HIGH  
**Rationale:** Learning rate has never been varied. Default SB3 lr=3e-4 may be too aggressive for the financial reward signal — lower lr often yields more stable, generalizable policies.  
**Time estimate:** ~2-3h  

```powershell
.\.venv\Scripts\python.exe experiments.py `
  --ticker NVDA `
  --reward-mode sharpe `
  --ent-coefs 0.02 `
  --timesteps 20000,40000 `
  --learning-rates 0.0001,0.0003,0.001 `
  --seeds 7,13,3 `
  --run-label "exp_e_lr_sweep" `
  --append
```

**Expected outcome:** lr=1e-4 should show lower variance across seeds. If test_acc improves >0.5% at lr=1e-4 → lock it in as new default for all subsequent sweeps.

**Kill signal:** If all three LRs produce equivalent results (within 0.005) → learning rate is not the ceiling bottleneck, skip to Exp F.

---

### Exp F — Gamma (Discount Factor) Sweep
**Priority:** MEDIUM-HIGH  
**Rationale:** Default gamma=0.99 is very long-horizon. For intraday/daily equity trading, shorter gamma (0.95-0.97) forces the agent to prioritize near-term returns, which may better align with how alpha is actually generated.  
**Time estimate:** ~2h  

```powershell
.\.venv\Scripts\python.exe experiments.py `
  --ticker NVDA `
  --reward-mode sharpe `
  --ent-coefs 0.02 `
  --timesteps 20000 `
  --gamma 0.95,0.97,0.99 `
  --seeds 7,13,3 `
  --run-label "exp_f_gamma_sweep" `
  --append
```

**What to watch for:**
- Lower gamma → more reactive policy (could improve win rate but increase drawdowns)
- Check `test_trade_win_rate` delta alongside `test_actionable_accuracy`
- If gamma=0.95 wins on accuracy but loses on alpha → not a net improvement

---

### Exp G — Extended Timesteps
**Priority:** MEDIUM  
**Rationale:** All competitive configs used 20k-40k steps. Testing 80k-100k checks whether the policy is simply undertrained or whether longer training actively overfits.  
**Time estimate:** ~2-3h  

```powershell
.\.venv\Scripts\python.exe experiments.py `
  --ticker NVDA `
  --reward-mode sharpe `
  --ent-coefs 0.02 `
  --timesteps 40000,80000,100000 `
  --seeds 7,13 `
  --run-label "exp_g_extended_timesteps" `
  --append
```

**Decision tree:**
- 80k > 40k on test metrics → the agent benefits from longer training, scale up Tier 3
- 80k ≈ 40k → diminishing returns, optimization axis is elsewhere
- 80k < 40k on test (val still high) → classic overfitting signal, enforce 20k as ceiling

---

### Exp H — Observation Space Feature Ablation
**Priority:** MEDIUM  
**Rationale:** It's unknown which features are driving the 54.3% ceiling. Some features may be adding noise rather than signal. A systematic ablation identifies which to keep and which to drop or transform.  
**Time estimate:** ~3-4h (multiple reruns)  

**Ablation A — No news sentiment:**
```powershell
.\.venv\Scripts\python.exe experiments.py `
  --ticker NVDA `
  --reward-mode sharpe `
  --ent-coefs 0.02 `
  --timesteps 20000 `
  --no-news `
  --seeds 7,13,3 `
  --run-label "exp_h_ablation_no_news" `
  --append
```

**Ablation B — Raw OHLCV only (strip all engineered features):**
```powershell
.\.venv\Scripts\python.exe experiments.py `
  --ticker NVDA `
  --reward-mode sharpe `
  --ent-coefs 0.02 `
  --timesteps 20000 `
  --features ohlcv_only `
  --seeds 7,13,3 `
  --run-label "exp_h_ablation_ohlcv_only" `
  --append
```

**Ablation C — Technical indicators only (no price levels):**
```powershell
.\.venv\Scripts\python.exe experiments.py `
  --ticker NVDA `
  --reward-mode sharpe `
  --ent-coefs 0.02 `
  --timesteps 20000 `
  --features ta_only `
  --seeds 7,13,3 `
  --run-label "exp_h_ablation_ta_only" `
  --append
```

**Read the results:** Feature set with highest test_acc at lowest val/test gap = the optimal observation space. Lock this before running Tier 3.

---

## TIER 3 — STRUCTURAL

*Run after Tier 1 + 2 analysis is complete. These are higher-risk, higher-reward experiments.*

---

### Exp B — AMD Env Recalibration
**Priority:** MEDIUM  
**Failure mode addressed:** ENV_FIT (structural, not reward-specific)  
**Time estimate:** ~2h  

AMD's failure is identical across sharpe and sortino — pointing to trade_penalty and drawdown scale mismatched to AMD's volatility regime.

```powershell
.\.venv\Scripts\python.exe experiments.py `
  --ticker AMD `
  --reward-mode sharpe,sortino `
  --ent-coefs 0.02,0.05 `
  --timesteps 20000,40000 `
  --reward-trade-penalty 0.0005,0.001,0.002 `
  --reward-drawdown-penalty-scale 0.5,1.0,2.0 `
  --seeds 7,13,3 `
  --run-label "exp_b_amd_env_recalib" `
  --append
```

**Kill signal:** If 9+ configs with AMD-specific scaling still can't clear ranking_score 0.45 → park AMD for Q2. Allocate experiment budget to NVDA and new tickers.

---

### Exp I — SAC vs PPO on NVDA
**Priority:** MEDIUM  
**Rationale:** SAC's continuous action space may allow finer position sizing than discrete PPO (Hold/Buy/Sell). If SAC can produce portfolio weights rather than binary signals, it may break the 55% ceiling.  
**Time estimate:** ~3-4h  
**Prerequisite:** Exp C completed and NVDA locked in

```powershell
.\.venv\Scripts\python.exe experiments.py `
  --ticker NVDA `
  --algorithm sac `
  --reward-mode sharpe `
  --ent-coefs 0.02,0.05 `
  --timesteps 20000,40000 `
  --seeds 7,13,3 `
  --run-label "exp_i_sac_vs_ppo_nvda" `
  --append
```

**What to compare:**
- test_actionable_accuracy: SAC vs PPO at same timestep budget
- test_trade_win_rate: SAC should improve this via partial position sizing
- test_return_cv_by_config: SAC is theoretically more stable (off-policy)

---

### Exp J — News Sentiment Impact (Full Ablation)
**Priority:** MEDIUM  
**Rationale:** Exp H runs the no-news ablation on NVDA. This experiment specifically targets whether sentiment signal quality varies by ticker — AMD and AAPL may respond differently to news than NVDA.

```powershell
# AMD without news
.\.venv\Scripts\python.exe experiments.py `
  --ticker AMD `
  --reward-mode sharpe `
  --ent-coefs 0.02 `
  --timesteps 20000 `
  --no-news `
  --seeds 7,13,3 `
  --run-label "exp_j_amd_no_news" `
  --append

# AAPL without news (run only after Exp A clears)
.\.venv\Scripts\python.exe experiments.py `
  --ticker AAPL `
  --reward-mode sharpe `
  --ent-coefs 0.02 `
  --timesteps 20000 `
  --no-news `
  --seeds 21,7,13 `
  --run-label "exp_j_aapl_no_news" `
  --append
```

**Decision rule:** If no-news consistently matches or beats news-enabled across all tickers → the NewsAPI signal is not adding value and can be removed, simplifying the observation space and reducing look-ahead bias risk.

---

### Exp K — Dollar-Neutral Long/Short Pilot
**Priority:** LOW (architectural change)  
**Rationale:** The current strategy is long-only (Hold/Buy/Sell). A dollar-neutral long/short approach generates alpha independently of market direction, which should dramatically improve `test_alpha_vs_qqq`.  
**Note:** This requires a code change to `trading_env.py` — escalate to Copilot before running.  
**Prerequisite:** All Tier 1 and Tier 2 experiments complete

```
# Copilot handoff prompt:
# "Add a dollar-neutral mode to trading_env.py. When --dollar-neutral is passed,
#  the agent can go long one position while simultaneously shorting another.
#  Portfolio value should remain cash-neutral. Reward function stays unchanged."
```

```powershell
# After Copilot implements --dollar-neutral:
.\.venv\Scripts\python.exe experiments.py `
  --ticker NVDA `
  --reward-mode sharpe `
  --ent-coefs 0.02 `
  --timesteps 40000 `
  --dollar-neutral `
  --seeds 7,13,3 `
  --run-label "exp_k_dollar_neutral_pilot" `
  --append
```

---

## EXECUTION SCHEDULE

```
Day 1 AM   Exp A  (AAPL audit diagnostic — ~2h)
Day 1 PM   Exp C  (NVDA 10-seed — ~3h, run overnight if needed)

Day 2 AM   Exp E  + Exp F  (LR + gamma sweeps — run in parallel if 2 terminals available)
Day 2 PM   Exp G  (extended timesteps — kick off, runs overnight)

Day 3 AM   Exp H  (feature ablation — 3 ablation runs sequentially)
Day 3 PM   Analyze Tier 1 + 2 results; determine if NVDA is promotable

Day 4 AM   Exp B  (AMD recalibration)
Day 4 PM   Exp I  (SAC vs PPO — only if Exp C promoted NVDA)

Day 5       Exp J  (sentiment ablation — all tickers)
            Exp K  (dollar-neutral pilot — only if Copilot change is ready)
```

---

## MASTER GATE EVALUATION

After all experiments complete, re-run gate evaluation on the best config from each experiment:

| Gate | Threshold | Current Best | Target |
|------|-----------|-------------|--------|
| test_actionable_accuracy | ≥ 0.53 | 0.543 (NVDA) | ≥ 0.555 |
| test_trade_win_rate | ≥ 0.52 | ~0.52 | ≥ 0.54 |
| test_alpha_vs_qqq | ≥ 0.00 | +0.031 (NVDA) | ≥ 0.05 |
| val/test gap | ≤ 0.05 | -0.036 (NVDA) | ≤ 0.03 |
| test_return_cv_by_config | < 1.00 | ~3.41 (pre-Exp C) | < 0.60 |

**Deployment checkpoint:** All 5 gates pass on NVDA with CV < 0.60 across 10+ seeds → staging promotion.

---

## HARD RULES (STANDING)

1. Always `--append` and `--run-label` on every sweep. No exceptions.
2. Never promote on val-only gains. Test gate is binary.
3. Never run Tier 3 structural experiments before Tier 1 blockers are resolved.
4. Never touch `trading_env.py` or `experiments.py` without explicit Copilot handoff.
5. Never infer seed stability from fewer than 3 seeds.
6. Kill AMD experiments after 9+ failed configs — reallocate budget to NVDA expansion or new ticker (MSFT/META candidates).

---

*Generated: April 29, 2026 · Project: reinforcement-learning-stocks*