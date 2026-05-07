# MU Sweep v3 — Experiment Strategist Report

> **Track:** RL track | **Delivery:** Analysis + concrete proposed runs  
> **Batch:** `sweep_mu_overtrade_fix_v3` (10 rows, turnover_penalty ∈ [0.005, 0.01])  
> **Status: 0/10 configs passed all 6 gates. Not promotable.**

---

## 1. Research Summary

`sweep_mu_overtrade_fix_v3` ran the first two priority-1 turnover penalty values (0.005 and 0.01) across 5 seeds [3, 7, 13, 21, 42] at ent_coef=0.02, 40k steps. The underlying directional signal (Gates G1/G2) remains intact in the clean pair (seeds 7, 42, 13 on one config). However, the overtrade failure from `baseline_v1` is **completely unresolved** — every high-alpha seed still trades at 98.6%, and the batch-level CV remains at 2.30. Neither penalty value shifted behavior.

---

## 2. What Improved

| Metric | v3 result | vs baseline_v1 |
|--------|-----------|---------------|
| G1 (acc ≥ 0.53) pass rate | 50% | ~30% |
| G2 (twr ≥ 0.52) pass rate | 60% | ~30% |
| G3 (alpha > 0) pass rate | 40% | ~30% |
| Median test Sharpe | 1.23 | ~0.50 |
| Seed 42 best alpha | +2.59 | +1.40 |

- Seeds 7, 13, 42 show strong, consistent Sharpe (1.80–2.15) under both penalty values — signal is **reproducible**
- Seed 42 with 0.01 penalty produced the highest alpha yet seen: **+2.59**
- Accuracy and win rate are locked in at 0.5553/0.5521 across seeds 7, 13, 42 — stable convergence

---

## 3. What Degraded or Remains Weak

| Gate | v3 Pass Rate | Status |
|------|-------------|--------|
| G4 (Val/Test drift ≤ 0.05) | 20% | Only low-Sharpe seeds pass |
| G5 (CV < 1.0) | 0% | CV = 2.30 clean across all configs |
| G6 (Trade rate 0.40–0.80) | 20% | High-Sharpe seeds at 98.6% unchanged |

**Critical observations:**
- **The penalty had zero effect on trade rate.** Seeds 7, 13, 42 trade at exactly 98.6% whether the penalty is 0.005 or 0.01. This is the same rate as `baseline_v1`. The penalty is being learned around, not responded to.
- **Seed 3 remains binary catastrophic:** 0 trades and 0.0 accuracy at penalty=0.005, partial recover at 0.01 (but -1.45 alpha, 0.88 trate). Serial failure across all 4 sweeps.
- **Seed 21 underperforms clean pair significantly:** Sharpe 0.22–0.29, mixed alpha. May reflect a regime mismatch rather than a policy problem.
- **Val alpha is consistently negative** for all seeds (range: -1.30 to -0.05). Test alpha diverges strongly upward for clean pair — test period appears to coincide with a favorable MU regime.

---

## 4. Most Likely Explanations

**Evidence-backed:**
- **Overtrade is feature-driven, not reward-driven.** Two distinct penalty values (0.005 and 0.01) produced identical trade rates (98.6%) for the high-Sharpe seeds. The model is not perceiving the penalty as a meaningful deterrent against the signal reward it's extracting. The stationary features likely create high-frequency directionality that dominates the cost signal.
- **Seed 3 has an unresolvable initialization for MU.** Four sweeps, multiple configs, same catastrophe. No evidence of any sensitivity to penalty or entropy at this step count.
- **CV gate failure is seed-3-driven.** Clean-seed CV is 2.30 even with seed 3's zero-trade result partially excluded — the variance between seeds 7/42 (~2.0 Sharpe) and seeds 13/21 (0.23–0.74 Sharpe) is structurally high.

**Plausible hypotheses:**
- The 0.005–0.01 penalty range is simply below the agent's effective learning threshold — it may require a full order-of-magnitude jump (to 0.10–0.20) to even register as meaningful. Except that `turnover_v2` at high values caused collapse. There may be a narrow viable window that hasn't been found.
- The `max_weight_delta_per_step=0.10` cap is insufficient to limit effective turnover — the agent achieves 98.6% trade rate within that constraint, meaning it moves the full 10% every bar. A tighter cap (0.05) may force fewer "material" position changes.
- The binary action space idea (from the last conversation) may be the correct structural fix — removing the continuous weight target and forcing hold/trade decisions directly.

---

## 5. Confidence Level for Current Conclusions

| Claim | Confidence |
|-------|-----------|
| Directional alpha in seeds 7/42 is real (not noise) | **Medium-High** — three sweeps, stable G1/G2, positive alpha |
| Overtrade is feature-frequency driven, not reward-calibration driven | **High** — penalty-invariant at 0.005 and 0.01, same 98.6% |
| Penalty range 0.005–0.01 is ineffective | **High** — confirmed by identical trate |
| Penalty range 0.03–0.10 will cause collapse (per turnover_v2 history) | **Medium** — turnover_v2 config details unclear |
| Seed 3 is formally unresolvable | **Medium** — seed3_diag was never run; this is an untested assumption |
| Binary action space could resolve overtrade | **Low** — untested hypothesis |

---

## 6. Recommended Next Experiment Batch

Three experiments in strict priority order. Do **not** run a broader sweep before completing Exp A:

1. **Exp A — Structural turnover fix (max_weight_delta tighten + high penalty):** Test whether the trate comes down if position-change magnitude is constrained more tightly *and* penalty is stepped up to 0.05–0.10. This is the last reward-side approach before abandoning it.
2. **Exp B — Seed 3 formal diagnostic:** Run the seed3_diag that was never executed. Required to make CV interpretable.
3. **Exp C — Binary action space pilot:** If Exp A fails, test the binary action architecture (long/hold/cash) on seeds 7 and 42 only as a structural overtrade fix.

---

## 7. Next Proposed Experiments

### **Experiment A — Structural Turnover Fix (Priority 1)**

**Goal:** Reduce trate from 98.6% into [0.40, 0.80] gate band by combining a tighter position-change cap with a higher (but not collapse-inducing) turnover penalty.

**Why it matters:** Two distinct penalties showed zero trate response. This suggests the agent's reward for each directional step exceeds the penalty cost. Narrowing `max_weight_delta` forces fewer effective position changes per bar; a moderate penalty jump tests whether the learning threshold is simply at a higher value.

**Variables to change:**
- `reward_turnover_penalty_scale` ∈ [0.03, 0.05, 0.10]
- `max_weight_delta_per_step` ∈ [0.05, 0.10] (test both to isolate which lever matters)

**Hold constant:** seeds [7, 42, 13], ent_coef=0.02, timesteps=40000, use_stationary_features=True

**Success criteria:** trate ∈ [0.40, 0.80] AND test_Sharpe > 1.0 AND test_alpha > 0.0 for seeds 7 and 42

**Failure interpretation:** If trate remains > 0.80 at penalty=0.10 AND max_delta=0.05 — overtrade is feature-driven; escalate to Exp C (binary action space). If trate drops but alpha collapses — penalty sweet spot between 0.01 and collapse is narrower than the step size; try 0.02 and 0.025.

```powershell
# Batch A1: tight cap + moderate penalty
.\.venv\Scripts\python.exe src\experiments.py --ticker mu --reward-mode sharpe --ent-coefs 0.02 --timesteps 40000 --seeds 7,42,13 --execution-mode next_bar --reward-hold-penalty-scale 0.01 --reward-turnover-penalty-scale 0.03 --max-weight-delta-per-step 0.05 --use-stationary-features --run-label "sweep_mu_overtrade_fix_v4" --append
```
```powershell
# Batch A2: standard cap + moderate penalty
.\.venv\Scripts\python.exe src\experiments.py --ticker mu --reward-mode sharpe --ent-coefs 0.02 --timesteps 40000 --seeds 7,42,13 --execution-mode next_bar --reward-hold-penalty-scale 0.01 --reward-turnover-penalty-scale 0.05 --max-weight-delta-per-step 0.10 --use-stationary-features --run-label "sweep_mu_overtrade_fix_v4" --append
```
```powershell
# Batch A3: tight cap + higher penalty
.\.venv\Scripts\python.exe src\experiments.py --ticker mu --reward-mode sharpe --ent-coefs 0.02 --timesteps 40000 --seeds 7,42,13 --execution-mode next_bar --reward-hold-penalty-scale 0.01 --reward-turnover-penalty-scale 0.10 --max-weight-delta-per-step 0.05 --use-stationary-features --run-label "sweep_mu_overtrade_fix_v4" --append
```
```powershell
# Evaluate after all A batches
.\.venv\Scripts\python.exe scripts\evaluate_sweep.py --leaderboard data\experiment_leaderboard.csv --label sweep_mu_overtrade_fix_v4
```

---

### **Experiment B — Seed 3 Formal Diagnostic (Priority 2)**

**Goal:** Determine whether seed 3's serial failure (4 sweeps, multiple configs) is resolvable with longer training or different entropy, or is a structural MU initialization problem.

**Why it matters:** Seed 3 inflates CV and destroys comparability. Either fix it or formally exclude it with documented rationale (like AMD's known-bad seeds). Until this is resolved, the clean_cv value is meaningless.

**Variables to change:** `timesteps` ∈ [40000, 80000, 120000], `ent_coef` ∈ [0.02, 0.05, 0.10]

**Hold constant:** seeds [3], use_stationary_features=True, max_weight_delta=0.10, no turnover penalty

**Success criteria:** Seed 3 achieves test_Sharpe > 0.0 AND trate > 0.10 in at least one config

**Failure interpretation:** If seed 3 fails all 9 combos — formally exclude; re-compute CV over 4-seed set [7, 13, 21, 42]

```powershell
.\.venv\Scripts\python.exe src\experiments.py --ticker mu --reward-mode sharpe --ent-coefs 0.02,0.05,0.10 --timesteps 40000 --seeds 3 --execution-mode next_bar --reward-hold-penalty-scale 0.01 --max-weight-delta-per-step 0.10 --use-stationary-features --run-label "sweep_mu_seed3_diag" --append
```
```powershell
.\.venv\Scripts\python.exe src\experiments.py --ticker mu --reward-mode sharpe --ent-coefs 0.02,0.05,0.10 --timesteps 80000 --seeds 3 --execution-mode next_bar --reward-hold-penalty-scale 0.01 --max-weight-delta-per-step 0.10 --use-stationary-features --run-label "sweep_mu_seed3_diag" --append
```
```powershell
.\.venv\Scripts\python.exe src\experiments.py --ticker mu --reward-mode sharpe --ent-coefs 0.02,0.05,0.10 --timesteps 120000 --seeds 3 --execution-mode next_bar --reward-hold-penalty-scale 0.01 --max-weight-delta-per-step 0.10 --use-stationary-features --run-label "sweep_mu_seed3_diag" --append
```
```powershell
.\.venv\Scripts\python.exe scripts\evaluate_sweep.py --leaderboard data\experiment_leaderboard.csv --label sweep_mu_seed3_diag
```

---

### **Experiment C — Binary Action Space Pilot (Priority 3, conditional on Exp A failure)**

**Goal:** Test whether replacing continuous weight targets with a discrete {hold, long} action space eliminates structural overtrade by removing the agent's ability to micro-adjust every bar.

**Why it matters:** If overtrade is feature-frequency driven (high-frequency autocorrelation in stationary features driving near-constant action), a binary action space changes the behavioral cliff entirely — the agent can only be in or out, removing the partial-position micro-adjustment pattern.

**Variables to change:** action space architecture (binary), seeds [7, 42]

**Hold constant:** all other hyperparameters from the best baseline config

> **Note:** This requires an architecture change to `src/trading_env.py`. See the binary action space plan from the previous conversation (conversation 608e2cff). Run only after Exp A confirms the reward-penalty approach is exhausted.

**Success criteria:** trate ∈ [0.40, 0.80], test_Sharpe > 1.0

**Failure interpretation:** Overtrade is driven by the signal landscape itself (MU's features are simply high-frequency tradeable) — park MU pending feature redesign

---

## 8. Priority Order

| # | Experiment | Rationale | Est. Runs |
|---|-----------|-----------|-----------|
| 1 | **A — Structural turnover fix** | Penalty-invariant overtrade requires a structural lever change (cap tighter + penalty jump). Last reward-side option. | 9 runs (3 seeds × 3 configs) |
| 2 | **B — Seed 3 diagnostic** | CV is uninterpretable until seed 3 is formally classified. Can run in parallel with A. | 9 runs (1 seed × 9 combos) |
| 3 | **C — Binary action space** | Architecture change; only justified if A fails | 4 runs (2 seeds × 2 configs) |

---

## 9. Success/Failure Interpretation Plan

| Outcome | Interpretation | Next Step |
|---------|---------------|-----------|
| Exp A: trate drops into [0.40, 0.80] with alpha intact | Penalty sweet spot found — structural lever combo worked | Expand to 5-seed confirmation |
| Exp A: trate drops but alpha collapses | Penalty is too aggressive — try 0.02–0.025 intermediate values | Narrow search |
| Exp A: trate stays at 98%+ at all penalty/cap values | Overtrade is feature-frequency driven | Escalate to Exp C |
| Exp B: seed 3 recovers at higher timesteps | Training length was the issue | Add to confirmation set at that step count |
| Exp B: seed 3 fails all 9 combos | Formally exclude seed 3 | Re-compute CV on 4-seed set; reassess G5 |
| Exp A + B both succeed | Re-run baseline with winning config + 4-seed set | Assess promotion readiness |
| Exp A + B + C all fail | MU is not viable under current architecture | Park pending feature redesign or architecture rewrite |

---

## 10. Leaderboard Comparability Impact

> **REQUIRED SECTION**

- **Medium-High impact.** `sweep_mu_overtrade_fix_v3` and `v4` are directly comparable to each other (same ent_coef, timesteps, feature space, seed set). However, they are **not comparable to NVDA/AMD rows** because:
  - MU has no Stage 1 baseline gate (went directly to RL)
  - MU clean_cv is computed on a different effective seed set (seed 3 artificially inflating variance)
  - The val period alpha is negative across all MU configs — a known structural difference from NVDA/AMD
- **Intraday 5m rows** (batch_a leaderboard) use a different interval and are not comparable to daily MU rows
- Any CV-based comparison between MU and NVDA/AMD requires re-running MU CV on the 4-clean-seed set after seed 3 is formally classified

---

## 11. Promotion Readiness Assessment

**Status: Not promotable. Blocked by G5, G6, and partial G3/G4.**

| Gate | Current Status | Blocker Severity |
|------|---------------|-----------------|
| G1 (acc ≥ 0.53) | ✅ Passes for clean seeds | Not a blocker |
| G2 (twr ≥ 0.52) | ✅ Passes for clean seeds | Not a blocker |
| G3 (alpha > 0) | ⚠️ Passes for seeds 7, 42 only | Config-level — needs multi-seed confirmation |
| G4 (drift ≤ 0.05) | ❌ Fails for high-Sharpe seeds | Secondary — likely improvable with fix |
| G5 (CV < 1.0) | ❌ CV = 2.30 | Hard blocker — seed 3 diagnostic required |
| G6 (trate 0.40–0.80) | ❌ 98.6% for all high-Sharpe seeds | Hard blocker — primary research focus |

**Path to promotion:**
1. Exp A resolves G6 without destroying G1/G2/G3
2. Exp B resolves G5 (either fixes seed 3 or enables CV recomputation on 4-seed set)
3. G4 drift likely improves once trate is controlled (overtrading inflates val-test acc divergence)
4. Run 5-seed confirmation on the winning config — target 3/5 seeds passing all 6 gates
