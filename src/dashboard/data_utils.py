from __future__ import annotations

from pathlib import Path
import pandas as pd
import streamlit as st

from src.dashboard.config import DEFAULT_DATA_PATH
from src.market_data import get_cache_path_for_ticker
from src.signal_analytics import (
    confusion_matrix,
    enrich_with_truth_labels,
    simulate_agent_signals,
    simulate_ensemble_signals,
)


def get_data_path_for_ticker(ticker: str, use_stationary: bool = False, interval: str = "1d") -> Path:
    """Get the appropriate data path for a given ticker."""
    return get_cache_path_for_ticker(ticker, stationary=use_stationary, interval=interval)


@st.cache_data(show_spinner=False)
def load_market_data(data_path: str) -> pd.DataFrame:
    path = Path(data_path)
    if not path.exists():
        raise FileNotFoundError(f"Data file not found: {path}")
    if path.suffix == ".parquet":
        return pd.read_parquet(path)
    parse_dates = ["Date"] if "Date" in pd.read_csv(path, nrows=0).columns else None
    df = pd.read_csv(path, parse_dates=parse_dates)

    required = {"Open", "High", "Low", "Close", "Volume"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Data file is missing required columns: {sorted(missing)}")
    return df


@st.cache_data(show_spinner=False)
def evaluate_signals(
    data_path: str,
    model_path: str,
    threshold: float,
    horizon_steps: int,
    deterministic_policy: bool,
    binary_actions: bool = False,
    min_hold_bars: int = 0,
    use_ensemble: bool = False,
    ticker: str = "",
    ensemble_config_path: str = "",
) -> tuple[pd.DataFrame, pd.DataFrame]:
    df = load_market_data(data_path)
    
    if use_ensemble:
        signals = simulate_ensemble_signals(
            df=df,
            ticker=ticker,
            ensemble_config_path=ensemble_config_path,
        )
    else:
        signals = simulate_agent_signals(
            df=df, 
            model_path=model_path, 
            deterministic=deterministic_policy,
            binary_actions=binary_actions,
            min_hold_bars=min_hold_bars
        )
        
    enriched = enrich_with_truth_labels(signals, threshold=threshold, horizon_steps=horizon_steps)
    conf = confusion_matrix(enriched)
    return enriched, conf


def _apply_split_filter(df: pd.DataFrame, split: str) -> pd.DataFrame:
    """Filter DataFrame to specific Train/Val/Test split based on 70/15/15 ratio."""
    if split == "Full" or df.empty:
        return df
    
    n = len(df)
    train_end = int(n * 0.70)
    val_end = int(n * (0.70 + 0.15))
    
    if split == "Train":
        return df.iloc[:train_end].reset_index(drop=True)
    elif split == "Val":
        return df.iloc[train_end:val_end].reset_index(drop=True)
    elif split == "Test":
        return df.iloc[val_end:].reset_index(drop=True)
    return df
