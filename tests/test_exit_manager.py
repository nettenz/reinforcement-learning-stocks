"""Boundary-condition tests for ExitManager.

These tests focus on the contract that matters for Phase 3 wiring:
- no-position short-circuiting
- exact rule thresholds
- per-position state reset
- composite rule precedence and validation
- rule-name normalization
"""
from __future__ import annotations

import pytest

from src.exit_manager import ExitManager


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


@pytest.mark.parametrize(
    "rule_name, expected",
    [
        (" time ", "time"),
        ("TRAILING_STOP", "trailing_stop"),
        ("Profit_Take", "profit_take"),
    ],
)
def test_rule_name_is_normalized(rule_name: str, expected: str) -> None:
    mgr = ExitManager(rule_name)
    assert mgr.rule == expected


def test_no_position_short_circuits_all_rules() -> None:
    mgr = ExitManager("profit_take", {"threshold": 0.03})

    fired, rule = mgr.should_exit(_pos(shares=0.0, upnl=0.50, bars=999), confidence=0.0)

    assert fired is False
    assert rule == ""


# ---------------------------------------------------------------------------
# Profit take boundaries
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
# Trailing stop boundaries
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


def test_trailing_stop_no_fire_without_prior_peak() -> None:
    mgr = ExitManager("trailing_stop", {"stop_pct": 0.05})

    # pnl goes directly negative — peak floor = 0, drawdown = 0 - (-0.02) = 0.02 < 0.05
    fired, rule = mgr.should_exit(_pos(upnl=-0.02), confidence=0.9)
    assert fired is False
    assert rule == ""


# ---------------------------------------------------------------------------
# Time boundaries
# ---------------------------------------------------------------------------

def test_time_fires_at_max_bars() -> None:
    mgr = ExitManager("time", {"max_bars": 20})

    fired, _ = mgr.should_exit(_pos(bars=19), confidence=0.9)
    assert fired is False

    fired, rule = mgr.should_exit(_pos(bars=20), confidence=0.9)
    assert fired is True
    assert rule == "time"


# ---------------------------------------------------------------------------
# Confidence boundaries
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
# Composite boundaries
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
# Reset boundaries
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


def test_composite_prefers_first_triggered_subrule() -> None:
    mgr = ExitManager(
        "composite",
        {
            "rules": [
                {"rule": "profit_take", "params": {"threshold": 0.03}},
                {"rule": "trailing_stop", "params": {"stop_pct": 0.05}},
            ]
        },
    )

    fired, rule = mgr.should_exit(_pos(upnl=0.04), confidence=0.9)

    assert fired is True
    assert rule == "profit_take"


def test_composite_with_no_subrules_never_fires() -> None:
    mgr = ExitManager("composite", {"rules": []})

    fired, rule = mgr.should_exit(_pos(upnl=0.50), confidence=0.1)

    assert fired is False
    assert rule == ""


def test_composite_rejects_invalid_subrule_at_init() -> None:
    with pytest.raises(ValueError, match="Unknown exit rule"):
        ExitManager(
            "composite",
            {
                "rules": [
                    {"rule": "profit_take", "params": {"threshold": 0.03}},
                    {"rule": "not_a_rule", "params": {}},
                ]
            },
        )


# ---------------------------------------------------------------------------
# Unknown rule handling
# ---------------------------------------------------------------------------

def test_unknown_rule_raises_at_init() -> None:
    with pytest.raises(ValueError, match="Unknown exit rule"):
        ExitManager(rule="garbage", params={})
