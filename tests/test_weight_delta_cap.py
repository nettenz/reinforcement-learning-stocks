"""Regression tests for per-step exposure change capping."""
import sys
from pathlib import Path

import pandas as pd

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from src.trading_env import TradingEnv


def _make_test_frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Date": pd.date_range("2024-01-01", periods=4, freq="D"),
            "Open": [100.0, 100.0, 100.0, 100.0],
            "High": [100.0, 100.0, 100.0, 100.0],
            "Low": [100.0, 100.0, 100.0, 100.0],
            "Close": [100.0, 100.0, 100.0, 100.0],
            "Volume": [1000, 1000, 1000, 1000],
        }
    )


def test_same_bar_target_weight_is_capped():
    env = TradingEnv(
        df=_make_test_frame(),
        execution_mode="same_bar",
        max_weight_delta_per_step=0.25,
        transaction_cost_rate=0.0,
        trade_penalty=0.0,
    )

    env.reset()
    _, _, _, _, info = env.step(1.0)

    assert info["execution_target_weight_pre_cap"] == 1.0
    assert info["execution_target_weight"] == 0.25
    assert info["execution_weight_delta_limited"] == 1
    assert env.pm.current_weight == 0.25


def test_next_bar_pending_target_weight_is_capped_on_execution():
    env = TradingEnv(
        df=_make_test_frame(),
        execution_mode="next_bar",
        max_weight_delta_per_step=0.25,
        transaction_cost_rate=0.0,
        trade_penalty=0.0,
    )

    env.reset()
    env.step(1.0)
    _, _, _, _, info = env.step(0.0)

    assert info["execution_target_weight_pre_cap"] == 1.0
    assert info["execution_target_weight"] == 0.25
    assert info["execution_weight_delta_limited"] == 1
    assert env.pm.current_weight == 0.25