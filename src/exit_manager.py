from __future__ import annotations

import math
from typing import Any, Mapping


DEFAULT_EXIT_PARAMS: dict[str, dict[str, float | int]] = {
    "confidence": {"threshold": 0.60, "n_bars": 3},
    "trailing_stop": {"stop_pct": 0.05},
    "time": {"max_bars": 20},
}


class ExitManager:
    """Rule-based exit layer for buy/hold ensemble inference."""

    def __init__(self, rule: str = "confidence", params: Mapping[str, Any] | None = None):
        normalized_rule = str(rule).strip().lower()
        if normalized_rule not in DEFAULT_EXIT_PARAMS:
            raise ValueError(
                f"Unsupported exit rule '{rule}'. Expected one of: {list(DEFAULT_EXIT_PARAMS)}"
            )

        self.rule = normalized_rule
        self.params: dict[str, Any] = {
            **DEFAULT_EXIT_PARAMS[self.rule],
            **(dict(params) if params is not None else {}),
        }
        self.reset()

    def reset(self) -> None:
        """Reset all rule state, typically between positions or sessions."""
        self._low_confidence_streak = 0
        self._peak_unrealized_pnl = 0.0
        self._prev_in_position = False

    def should_exit(self, position_state: Mapping[str, Any], confidence: float) -> bool:
        """
        Return True when the configured exit rule is triggered.

        position_state keys:
            in_position (bool): whether a position is currently open
            unrealized_pnl (float): current unrealized pnl ratio (e.g. 0.03 = +3%)
            time_in_position (int): bars since position entry
        """
        in_position = bool(position_state.get("in_position", False))
        if not in_position:
            self._low_confidence_streak = 0
            self._peak_unrealized_pnl = 0.0
            self._prev_in_position = False
            return False

        if not self._prev_in_position:
            self._low_confidence_streak = 0
            self._peak_unrealized_pnl = 0.0
            self._prev_in_position = True

        if self.rule == "confidence":
            threshold = float(self.params["threshold"])
            n_bars = int(self.params["n_bars"])
            self._low_confidence_streak = (
                self._low_confidence_streak + 1 if confidence < threshold else 0
            )
            return self._low_confidence_streak >= n_bars

        if self.rule == "trailing_stop":
            stop_pct = float(self.params["stop_pct"])
            unrealized_pnl = float(position_state.get("unrealized_pnl", 0.0))
            self._peak_unrealized_pnl = max(self._peak_unrealized_pnl, unrealized_pnl, 0.0)
            drawdown_from_peak = self._peak_unrealized_pnl - unrealized_pnl
            return drawdown_from_peak > stop_pct or math.isclose(
                drawdown_from_peak, stop_pct, rel_tol=0.0, abs_tol=1e-12
            )

        max_bars = int(self.params["max_bars"])
        time_in_position = int(position_state.get("time_in_position", 0))
        return time_in_position >= max_bars
