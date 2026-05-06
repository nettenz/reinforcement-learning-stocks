from __future__ import annotations

from typing import Any, Mapping


_VALID_RULES = {"confidence", "trailing_stop", "profit_take", "time", "composite"}

_DEFAULT_PARAMS: dict[str, dict[str, Any]] = {
    "confidence":    {"threshold": 0.67, "n_bars": 1},
    "trailing_stop": {"stop_pct": 0.05},
    "profit_take":   {"threshold": 0.03},
    "time":          {"max_bars": 20},
    "composite":     {"rules": []},
}


class ExitManager:
    """
    Rule-based exit layer applied post-inference over ensemble buy/hold signals.

    Supported rules: confidence, trailing_stop, profit_take, time, composite.
    All state lives in instance variables and is cleared by reset().
    """

    def __init__(self, rule: str, params: Mapping[str, Any] | None = None) -> None:
        normalized = str(rule).strip().lower()
        if normalized not in _VALID_RULES:
            raise ValueError(
                f"Unknown exit rule '{rule}'. Valid: {sorted(_VALID_RULES)}"
            )
        self.rule = normalized
        self.params: dict[str, Any] = {
            **_DEFAULT_PARAMS[self.rule],
            **(dict(params) if params is not None else {}),
        }

        # Build sub-managers eagerly so bad rule names raise at __init__ time.
        if self.rule == "composite":
            self._sub_managers: list[ExitManager] = [
                ExitManager(r["rule"], r["params"])
                for r in self.params.get("rules", [])
            ]
        else:
            self._sub_managers = []

        self.reset()

    # ------------------------------------------------------------------
    # State management
    # ------------------------------------------------------------------

    def reset(self) -> None:
        """Clear all per-position state. Call when a new position opens."""
        self._peak_pnl_pct: float = 0.0
        self._confidence_streak: int = 0
        for sub in self._sub_managers:
            sub.reset()

    def update_peak(self, unrealized_pnl_pct: float) -> None:
        """Update the running peak unrealized P&L. Floor is 0.0."""
        self._peak_pnl_pct = max(self._peak_pnl_pct, unrealized_pnl_pct, 0.0)

    # ------------------------------------------------------------------
    # Core decision
    # ------------------------------------------------------------------

    def should_exit(
        self,
        position_state: Mapping[str, Any],
        confidence: float,
    ) -> tuple[bool, str]:
        """
        Evaluate exit rule for the current bar.

        position_state keys:
            shares_held (float): current shares held; <= 0 means no position.
            entry_price (float): price at position open.
            current_price (float): current bar price.
            unrealized_pnl_pct (float): (current - entry) / entry.
            peak_pnl_pct (float): caller-provided running peak (informational only).
            bars_held (int): bars since entry.

        confidence: ensemble vote_share in [0.5, 1.0].

        Returns:
            (exit_signal, triggered_rule)  — triggered_rule is '' when no exit.
        """
        shares_held = float(position_state.get("shares_held", 0.0))
        if shares_held <= 0:
            return False, ""

        unrealized_pnl_pct = float(position_state.get("unrealized_pnl_pct", 0.0))
        bars_held = int(position_state.get("bars_held", 0))

        # Maintain internal peak every bar, regardless of which rule is active.
        self.update_peak(unrealized_pnl_pct)

        if self.rule == "confidence":
            return self._check_confidence(confidence)

        if self.rule == "trailing_stop":
            return self._check_trailing_stop(unrealized_pnl_pct)

        if self.rule == "profit_take":
            return self._check_profit_take(unrealized_pnl_pct)

        if self.rule == "time":
            return self._check_time(bars_held)

        if self.rule == "composite":
            return self._check_composite(position_state, confidence)

        return False, ""  # unreachable

    # ------------------------------------------------------------------
    # Per-rule helpers
    # ------------------------------------------------------------------

    def _check_confidence(self, confidence: float) -> tuple[bool, str]:
        threshold = float(self.params["threshold"])
        n_bars = int(self.params["n_bars"])
        if confidence < threshold:
            self._confidence_streak += 1
        else:
            self._confidence_streak = 0
        if self._confidence_streak >= n_bars:
            return True, "confidence"
        return False, ""

    def _check_trailing_stop(self, unrealized_pnl_pct: float) -> tuple[bool, str]:
        stop_pct = float(self.params["stop_pct"])
        drawdown = self._peak_pnl_pct - unrealized_pnl_pct
        if drawdown >= stop_pct:
            return True, "trailing_stop"
        return False, ""

    def _check_profit_take(self, unrealized_pnl_pct: float) -> tuple[bool, str]:
        threshold = float(self.params["threshold"])
        if unrealized_pnl_pct >= threshold:
            return True, "profit_take"
        return False, ""

    def _check_time(self, bars_held: int) -> tuple[bool, str]:
        max_bars = int(self.params["max_bars"])
        if bars_held >= max_bars:
            return True, "time"
        return False, ""

    def _check_composite(
        self,
        position_state: Mapping[str, Any],
        confidence: float,
    ) -> tuple[bool, str]:
        for sub in self._sub_managers:
            fired, rule_name = sub.should_exit(position_state, confidence)
            if fired:
                return True, rule_name
        return False, ""
