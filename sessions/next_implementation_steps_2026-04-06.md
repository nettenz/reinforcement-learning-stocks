# Next Implementation Steps
**Date:** 2026-04-06
**Purpose:** Convert the realism-audit verdict into a small, testable implementation sequence.

## Current decision
Proceed with realism-first implementation before any more reward tuning.

Reason:
- Latest realism phase showed performance degrades materially once fills/costs are tightened.
- Current gains are not yet robust enough to trust under live-like assumptions.
- The next highest-value work is to harden execution, turnover, and cost semantics.

---

## Priority 1: Execution realism baseline
### Goal
Validate that the current edge survives realistic spread and slippage assumptions.

### Files to inspect/update
- [src/trading_env.py](../src/trading_env.py)
- [src/experiments.py](../src/experiments.py)
- [run_realism_phase.ps1](../run_realism_phase.ps1)

### Implementation steps
1. Keep `execution_mode=next_bar` as the default realism-safe timing model.
2. Run 3 arms only:
   - Control: `spread_bps=0.0`, `slippage_bps=0.0`, `reward_ignore_transaction_cost=true`
   - Realistic: `spread_bps=1.0`, `slippage_bps=1.0`, `reward_ignore_transaction_cost=false`
   - Stress: `spread_bps=2.0`, `slippage_bps=2.0`, `reward_ignore_transaction_cost=false`
3. Hold constant:
   - `ent_coef=0.10`
   - `reward_mode=sharpe`
   - `reward_direction_scale=0.35`
   - `reward_return_scale=1.0`
   - `reward_turnover_penalty_scale=0.05`
   - `reward_drawdown_penalty_scale=0.10`
   - `ticker=nvda`
   - `timesteps=20000`
   - same seeds
4. Generate the report after the run.

### Acceptance criteria
- Alpha remains near the control arm, or degrades only modestly.
- CV stays manageable.
- Ranking order is stable enough to interpret.

### If it fails
- Stop reward tuning.
- Move to realism implementation changes below.

---

## Priority 2: Turnover realism correction
### Goal
Make turnover penalties reflect actual execution pressure, not just target-weight change.

### Files to inspect/update
- [src/trading_env.py](../src/trading_env.py)
- [src/experiments.py](../src/experiments.py)
- tests tied to env reward semantics

### Implementation steps
1. Add an optional turnover penalty mode that can use executed notional or share turnover.
2. Keep the current weight-delta penalty as the default path for compatibility.
3. Wire the new mode through `experiments.py`.
4. Add unit coverage for both modes.

### Acceptance criteria
- Existing experiments still run with default behavior unchanged.
- New mode is explicitly enabled and visible in outputs.
- Reward decomposition remains interpretable.

### Comparability note
Impact level: High.
Reason: reward semantics change in a way that weakens historical comparison unless versioned or cohort-split.

---

## Priority 3: Short-side realism
### Goal
Reduce inflated alpha from frictionless short exposure.

### Files to inspect/update
- [src/trading_env.py](../src/trading_env.py)
- [src/experiments.py](../src/experiments.py)

### Implementation steps
1. Add an optional borrow fee for negative exposure.
2. Keep borrow fee default at 0.0 so old runs remain compatible.
3. Wire the toggle through experiment configs.
4. Confirm short paths still work in training and evaluation.

### Acceptance criteria
- Short-cost toggle is visible and functional.
- No regression in baseline control runs when the feature is disabled.

### Comparability note
Impact level: High.
Reason: short economics materially change behavior and benchmark interpretation.

---

## Priority 4: Position sizing and debounce review
### Goal
Reduce simulator-specific threshold artifacts.

### Files to inspect/update
- [src/trading_env.py](../src/trading_env.py)

### Implementation steps
1. Re-check the 5% debounce rule in `PositionManager.step`.
2. Evaluate whether the threshold should be configurable or lower for realism tests.
3. Confirm integer share rounding is not masking excessive micro-rebalancing.

### Acceptance criteria
- The debounce rule is clearly documented or configurable.
- No hidden behavior changes in default runs.

### Comparability note
Impact level: Medium.
Reason: sizing behavior changes can alter turnover and fill frequency without changing input space.

---

## Priority 5: Proxy semantics clarification
### Goal
Make it explicit whether the training frame is a single tradable instrument or a proxy/basket.

### Files to inspect/update
- [src/market_data.py](../src/market_data.py)
- [src/experiments.py](../src/experiments.py)

### Implementation steps
1. Document the current single-ticker assumption in the realism notes.
2. If basket mode is later reintroduced, label it as a proxy and separate it from direct-trading experiments.
3. Avoid mixing proxy and direct-trade results in the same promotion lane.

### Acceptance criteria
- Benchmark interpretation is explicit.
- No silent assumption drift between proxy and directly tradable data.

### Comparability note
Impact level: Medium to High depending on whether basket mode is used.

---

## Suggested execution order
1. Run the realism-phase batch as-is.
2. If realism materially hurts alpha, implement turnover realism and short-side cost toggles.
3. Re-run the smallest realism batch after each change.
4. Only then return to reward refinement if realism survives.

---

## Stop / pivot rule
Pivot fully to realism-first if any of these happen:
- mean test alpha collapses under modest friction
- CV spikes materially under realistic fills
- ranking order becomes unstable across seeds
- performance depends heavily on `reward_ignore_transaction_cost=true`

If realism survives, return to reward tuning with the realism baseline locked.

---

## Current handoff targets
- [sessions/handoff_to_environment_realism_auditor_2026-04-06.md](handoff_to_environment_realism_auditor_2026-04-06.md)
- [sessions/environment-realism-first-plan-2026-04-06.md](environment-realism-first-plan-2026-04-06.md)
