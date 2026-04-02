import pandas as pd
import pytest

from src.signal_analytics import _align_features_to_model, NEWS_FEATURE_COLUMNS


def _df_with_ohlcv_and_stationary() -> pd.DataFrame:
    # Includes both schemas: OHLCV(5) and a 6-feature stationary subset.
    return pd.DataFrame(
        {
            "Open": [100.0, 101.0],
            "High": [101.0, 102.0],
            "Low": [99.0, 100.0],
            "Close": [100.5, 101.5],
            "Volume": [1000.0, 1100.0],
            "LogReturn": [0.01, 0.02],
            "VolLogDiff": [0.03, 0.04],
            "RelRange": [0.05, 0.06],
            "RelOpen": [0.07, 0.08],
            "RelMACD": [0.09, 0.10],
            "RSI_Centered": [0.11, 0.12],
        }
    )


def test_align_chooses_stationary_schema_when_ohlcv_cannot_match() -> None:
    df = _df_with_ohlcv_and_stationary()

    # 19 is impossible with OHLCV (5) but possible with stationary(6) + 8 news + 5 account/position.
    aligned, include_position, market_features = _align_features_to_model(df, expected_obs_dim=19)

    assert include_position is True
    assert market_features == [
        "LogReturn",
        "VolLogDiff",
        "RelRange",
        "RelOpen",
        "RelMACD",
        "RSI_Centered",
    ]
    assert all(col in aligned.columns for col in NEWS_FEATURE_COLUMNS)


def test_align_keeps_ohlcv_priority_when_it_matches() -> None:
    df = _df_with_ohlcv_and_stationary()

    # 18 is valid for OHLCV + 8 news + 5 account/position, so preserve OHLCV-first behavior.
    _, include_position, market_features = _align_features_to_model(df, expected_obs_dim=18)

    assert include_position is True
    assert market_features == ["Open", "High", "Low", "Close", "Volume"]


def test_align_raises_for_incompatible_expected_dim() -> None:
    df = pd.DataFrame(
        {
            "Open": [100.0, 101.0],
            "High": [101.0, 102.0],
            "Low": [99.0, 100.0],
            "Close": [100.5, 101.5],
            "Volume": [1000.0, 1100.0],
        }
    )

    with pytest.raises(ValueError, match="Model expects observation size 19"):
        _align_features_to_model(df, expected_obs_dim=19)
