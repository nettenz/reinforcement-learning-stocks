# Option A — Exit Signal Layer Plan
**Date:** 2026-04-30  
**Status:** Planning  
**Scope:** Add exit/sell signal on top of existing buy/hold agents. No architecture rewrite.

---

## Objective
The current ensemble agents produce strong entry signals (55%+ accuracy) but never explicitly
exit positions. Adding a rule-based or learned exit layer will capture realized gains rather
than holding through reversals.

**Current behavior:** Agent buys, holds indefinitely until episode ends.  
**Target behavior:** Agent buys, holds while thesis holds, exits when exit condition triggers.

---

## Why Option A over Option B (full long/short)

- Entry signal is already validated (6/6 gates, Exp 9 passed for NVDA and AMD)
- Rebuilding for long/short requires new reward terms, new position manager logic, and
  retraining from scratch — all three tickers blocked until AAPL leakage audit clears
- Exit rules can be added as a post-processing layer without touching training pipeline
- If exit layer improves P&L, it validates the approach before investing in Option B

---

## Architecture

```
EnsembleAgent.step()        ← existing, unchanged
    └→ buy / hold signal + confidence

ExitManager (new)
    └→ monitors open position
    └→ triggers exit when condition met
    └→ overrides hold → sell when exit fires

Dashboard
    └→ shows buy signals (existing)
    └→ shows exit signals (new overlay)
```

The `ExitManager` sits between the agent and execution. It receives the agent's signal
and the current position state, and can override a hold signal with an exit.

---

## Phase 1 — Rule-Based Exit (2 weeks)

Implement three rule-based exit strategies. Test each independently on NVDA and AMD
historical test data. Pick the best one or combine.

### Rule 1 — Time-based exit
Exit after holding for N bars regardless of P&L.

```python
if time_in_position >= MAX_HOLD_BARS:
    exit = True
```

**Rationale:** Prevents the agent from holding through full reversals. Simple baseline.
**Parameter to tune:** `MAX_HOLD_BARS` — start with 20 bars (1 month).

### Rule 2 — Trailing stop
Exit when unrealized P&L drops X% from peak.

```python
if unrealized_pnl < peak_pnl - TRAILING_STOP_PCT:
    exit = True
```

**Rationale:** Locks in gains, cuts losses. Classic risk management.
**Parameter to tune:** `TRAILING_STOP_PCT` — start with 0.05 (5%).

### Rule 3 — Agent confidence exit
Exit when ensemble confidence drops below threshold for N consecutive bars.

```python
if avg_confidence < CONFIDENCE_THRESHOLD for N bars:
    exit = True
```

**Rationale:** Uses the agent's own uncertainty as an exit signal. Most aligned with
the existing system.
**Parameters:** `CONFIDENCE_THRESHOLD=0.60`, `N=3` bars.

---

## Phase 2 — Backtested Exit Optimization (2 weeks)

Run each rule against the NVDA and AMD test splits. Measure:

| Metric | Baseline (hold only) | With exit rule |
|--------|---------------------|----------------|
| Sharpe ratio | | |
| Max drawdown | | |
| Avg hold duration | | |
| Win rate on closed trades | | |
| Alpha vs QQQ | | |

Use walk-forward validation — don't optimize exit parameters on the test split directly.
Tune on val, evaluate on test.

---

## Phase 3 — Dashboard Integration (1 week)

Wire exit signals into the existing dashboard:

- Exit markers on chart (red triangle or X on the candle where exit fires)
- Position P&L tracker — shows entry price, current price, unrealized P&L
- Exit rule selector in the UI (dropdown: time-based / trailing stop / confidence)
- Exit parameter controls (sliders for MAX_HOLD_BARS, TRAILING_STOP_PCT, etc.)

The dashboard already has the `EnsembleAgent` signal overlay foundation from the
Alpaca integration plan — exit signals are an additional layer on top.

---

## Implementation Files

| File | Change |
|------|--------|
| `src/exit_manager.py` | New file — `ExitManager` class with all three rule implementations |
| `src/trading_agent.py` | `EnsembleAgent.step()` returns exit signal alongside buy/hold |
| `backend/signals/agent.py` | New dashboard backend file — wires agent + exit manager to Alpaca data |
| `frontend/src/components/TradingChart.jsx` | Exit signal overlay markers |
| `frontend/src/components/ExitControls.jsx` | New UI component — exit rule selector + parameter sliders |

---

## ExitManager Interface

```python
class ExitManager:
    def __init__(self, rule='confidence', **kwargs):
        # rule: 'time', 'trailing_stop', 'confidence'
        self.rule = rule
        self.params = kwargs
        self.reset()

    def reset(self):
        self.entry_price = None
        self.peak_pnl = 0.0
        self.bars_held = 0
        self.low_conf_streak = 0

    def should_exit(self, position_state: dict, agent_confidence: float) -> bool:
        """
        position_state: {
            'in_position': bool,
            'unrealized_pnl': float,
            'bars_held': int,
            'entry_price': float,
            'current_price': float
        }
        Returns True if exit should fire.
        """
        if not position_state['in_position']:
            return False

        if self.rule == 'time':
            return position_state['bars_held'] >= self.params.get('max_bars', 20)

        if self.rule == 'trailing_stop':
            pnl = position_state['unrealized_pnl']
            self.peak_pnl = max(self.peak_pnl, pnl)
            return pnl < self.peak_pnl - self.params.get('stop_pct', 0.05)

        if self.rule == 'confidence':
            threshold = self.params.get('threshold', 0.60)
            n_bars    = self.params.get('n_bars', 3)
            if agent_confidence < threshold:
                self.low_conf_streak += 1
            else:
                self.low_conf_streak = 0
            return self.low_conf_streak >= n_bars

        return False
```

---

## Success Criteria

- Sharpe improves or holds vs baseline (no regression)
- Max drawdown reduces by at least 10% relative
- Average hold duration drops from near-infinite to meaningful (target: 10–30 bars)
- Win rate on closed trades ≥ current win rate (54–55%)
- Exit signals visible on dashboard and correctly timed vs price action

---

## Failure Criteria / When to Stop

- If all three exit rules reduce Sharpe below baseline → exit layer is adding noise, not signal
- If confidence-based exit fires too frequently → agent confidence is not a reliable exit proxy
- In either case, move to Option B (full long/short retraining) rather than continuing to tune

---

## Next Steps

1. Complete `market_feature_columns` fix (Claude Code prompt above)
2. Verify NVDA and AMD Exp 9 both pass cleanly
3. Start `src/exit_manager.py` implementation (Phase 1)
4. Backtest on NVDA test split before touching AMD or dashboard
