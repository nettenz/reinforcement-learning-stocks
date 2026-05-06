"""
Unit tests for ExitManager — Phase 1 spec (10 tests).

All tests use the new position_state interface:
    {shares_held, entry_price, current_price, unrealized_pnl_pct, peak_pnl_pct, bars_held}

and the new should_exit() return type: tuple[bool, str].
"""
from __future__ import annotations

import json

import numpy as np
import pytest

from src.exit_manager import ExitManager
from src.trading_agent import EnsembleAgent


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _pos(
    shares=1.0,
    entry=100.0,
    current=100.0,
    upnl=0.0,
    peak=0.0,
    bars=1,
) -> dict:
    return {
        "shares_held": shares,
        "entry_price": entry,
        "current_price": current,
        "unrealized_pnl_pct": upnl,
        "peak_pnl_pct": peak,
        "bars_held": bars,
    }


# ---------------------------------------------------------------------------
# Test 1 — profit_take fires at boundary
# ---------------------------------------------------------------------------

def test_profit_take_fires_at_boundary() -> None:
    mgr = ExitManager("profit_take", {"threshold": 0.03})

    fired, rule = mgr.should_exit(_pos(upnl=0.0300), confidence=0.9)
    assert fired is True
    assert rule == "profit_take"

    mgr.reset()
    fired, rule = mgr.should_exit(_pos(upnl=0.0299), confidence=0.9)
    assert fired is False
    assert rule == ""


# ---------------------------------------------------------------------------
# Test 2 — trailing_stop fires correctly after peak
# ---------------------------------------------------------------------------

def test_trailing_stop_fires_after_peak() -> None:
    mgr = ExitManager("trailing_stop", {"stop_pct": 0.05})

    # pnl rises to 8%
    fired, _ = mgr.should_exit(_pos(upnl=0.08), confidence=0.9)
    assert fired is False

    # pnl drops to 2% — drawdown = 0.08 - 0.02 = 0.06 >= 0.05
    fired, rule = mgr.should_exit(_pos(upnl=0.02), confidence=0.9)
    assert fired is True
    assert rule == "trailing_stop"


# ---------------------------------------------------------------------------
# Test 3 — trailing_stop does NOT fire on drawdown below entry without prior peak
# ---------------------------------------------------------------------------

def test_trailing_stop_no_fire_without_prior_peak() -> None:
    mgr = ExitManager("trailing_stop", {"stop_pct": 0.05})

    # pnl goes directly negative — peak floor = 0, drawdown = 0 - (-0.02) = 0.02 < 0.05
    fired, rule = mgr.should_exit(_pos(upnl=-0.02), confidence=0.9)
    assert fired is False
    assert rule == ""


# ---------------------------------------------------------------------------
# Test 4 — time fires at max_bars, not before
# ---------------------------------------------------------------------------

def test_time_fires_at_max_bars() -> None:
    mgr = ExitManager("time", {"max_bars": 20})

    fired, _ = mgr.should_exit(_pos(bars=19), confidence=0.9)
    assert fired is False

    fired, rule = mgr.should_exit(_pos(bars=20), confidence=0.9)
    assert fired is True
    assert rule == "time"


# ---------------------------------------------------------------------------
# Test 5 — confidence fires after N consecutive bars below threshold
# ---------------------------------------------------------------------------

def test_confidence_fires_after_n_bars() -> None:
    mgr = ExitManager("confidence", {"threshold": 0.67, "n_bars": 3})
    p = _pos()

    # bars 1-2: streak accumulates but < n_bars
    assert mgr.should_exit(p, confidence=0.50) == (False, "")
    assert mgr.should_exit(p, confidence=0.50) == (False, "")
    # bar 3: streak hits n_bars
    fired, rule = mgr.should_exit(p, confidence=0.50)
    assert fired is True
    assert rule == "confidence"


# ---------------------------------------------------------------------------
# Test 6 — confidence streak resets on recovery
# ---------------------------------------------------------------------------

def test_confidence_streak_resets_on_recovery() -> None:
    mgr = ExitManager("confidence", {"threshold": 0.67, "n_bars": 3})
    p = _pos()

    # 2 bars below threshold
    mgr.should_exit(p, confidence=0.50)
    mgr.should_exit(p, confidence=0.50)
    # 1 bar above threshold — streak resets to 0
    mgr.should_exit(p, confidence=0.80)
    # 2 more bars below — streak only at 2, no fire
    assert mgr.should_exit(p, confidence=0.50) == (False, "")
    assert mgr.should_exit(p, confidence=0.50) == (False, "")
    # 3rd consecutive bar below — fires now (n_bars=3)
    fired, rule = mgr.should_exit(p, confidence=0.50)
    assert fired is True
    assert rule == "confidence"


# ---------------------------------------------------------------------------
# Test 7 — composite returns correct triggered_rule
# ---------------------------------------------------------------------------

def test_composite_returns_correct_triggered_rule() -> None:
    mgr = ExitManager("composite", {"rules": [
        {"rule": "profit_take",   "params": {"threshold": 0.03}},
        {"rule": "trailing_stop", "params": {"stop_pct": 0.05}},
    ]})

    # profit_take fires when upnl >= 3%
    fired, rule = mgr.should_exit(_pos(upnl=0.04), confidence=0.9)
    assert fired is True
    assert rule == "profit_take"


# ---------------------------------------------------------------------------
# Test 8 — reset() clears all state
# ---------------------------------------------------------------------------

def test_reset_clears_all_state() -> None:
    mgr = ExitManager("trailing_stop", {"stop_pct": 0.05})

    # Build peak at 8%, confirm trailing stop fires at 2%
    mgr.should_exit(_pos(upnl=0.08), confidence=0.9)
    fired, _ = mgr.should_exit(_pos(upnl=0.02), confidence=0.9)
    assert fired is True

    # After reset(), peak is 0 — a 2% drop from 0 is only 0.02 drawdown < stop_pct=0.05
    mgr.reset()
    assert mgr._peak_pnl_pct == 0.0
    fired, rule = mgr.should_exit(_pos(upnl=0.02), confidence=0.9)
    assert fired is False
    assert rule == ""


# ---------------------------------------------------------------------------
# Test 9 — exit does not block subsequent buy signal when no position open
# ---------------------------------------------------------------------------

class _DummyObsSpace:
    shape = (5,)


class _DummyModel:
    observation_space = _DummyObsSpace()


class _DummyEnsemble:
    def __init__(self, action: int, confidence: float) -> None:
        self.models = {13: _DummyModel()}
        self._action = action
        self._confidence = confidence

    def ensemble_predict(self, _obs: np.ndarray, method: str = "voting"):
        return self._action, self._confidence


def test_exit_does_not_block_buy_on_fresh_position(tmp_path) -> None:
    config = {
        "nvda": {
            "production_ready": True,
            "active_seeds": [13],
            "ensemble_method": "voting",
        }
    }
    config_path = tmp_path / "ensemble_config.json"
    config_path.write_text(json.dumps(config))

    mgr = ExitManager("time", {"max_bars": 3})
    agent = EnsembleAgent(
        ensemble=_DummyEnsemble(action=1, confidence=0.95),
        config_path=str(config_path),
        ticker="NVDA",
        exit_manager=mgr,
    )

    # In position for bars_held=3 — time rule fires (account_state[-1]=3.0 is time_in_position,
    # but bars_held is tracked internally by EnsembleAgent, starting at 1 on first call)
    # We call three times while in position to let internal bars_held reach 3.
    for _ in range(2):
        agent.step(
            market_features=np.array([], dtype=np.float32),
            news_features=np.array([], dtype=np.float32),
            account_state=np.array([1000.0, 5.0, 1.0, 0.01, 1.0], dtype=np.float32),
        )

    action, _, debug = agent.step(
        market_features=np.array([], dtype=np.float32),
        news_features=np.array([], dtype=np.float32),
        account_state=np.array([1000.0, 5.0, 1.0, 0.01, 3.0], dtype=np.float32),
    )
    assert action == 0
    assert debug["exit_fired"] is True
    assert debug["exit_rule"] == "time"

    # No position — ensemble wants to buy, exit must not block it
    action, _, debug = agent.step(
        market_features=np.array([], dtype=np.float32),
        news_features=np.array([], dtype=np.float32),
        account_state=np.array([1000.0, 0.0, 0.0, 0.0, 0.0], dtype=np.float32),
    )
    assert action == 1
    assert debug["exit_fired"] is False


# ---------------------------------------------------------------------------
# Test 10 — unknown rule raises ValueError at __init__
# ---------------------------------------------------------------------------

def test_unknown_rule_raises_at_init() -> None:
    with pytest.raises(ValueError, match="Unknown exit rule"):
        ExitManager(rule="garbage", params={})
