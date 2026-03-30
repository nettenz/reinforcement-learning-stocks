from __future__ import annotations
import numpy as np
import pandas as pd

def compute_stationary_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Computes stationary features from OHLCV data to reduce overfitting.
    
    Features included:
    1. Log Returns: ln(Close_t / Close_{t-1})
    2. Normalized Volume: ln(Volume_t + 1) diff
    3. Relative Range: (High - Low) / Close
    4. Relative Open: (Open - PrevClose) / PrevClose
    5. Z-scored Moving Average Deviations (if enough data)
    
    Args:
        df: DataFrame containing at least ['Open', 'High', 'Low', 'Close', 'Volume']
            Expects columns to be raw or already normalized, but will re-derive
            stationary versions for consistency.
            
    Returns:
        DataFrame with stationary features.
    """
    feat = pd.DataFrame(index=df.index)
    if "Date" in df.columns:
        feat["Date"] = df["Date"]
    
    # Use 'RawClose' if available, else 'Close'
    close_col = "RawClose" if "RawClose" in df.columns else "Close"
    close = df[close_col]
    
    # 1. Log Returns (Stationary price proxy)
    feat["LogReturn"] = np.log(close / close.shift(1)).fillna(0.0)
    
    # 2. Normalized Volume (Log diff)
    volume = df["Volume"]
    feat["VolLogDiff"] = np.log1p(volume).diff().fillna(0.0)
    
    # 3. Relative Range (Volatility proxy, stationary)
    feat["RelRange"] = ((df["High"] - df["Low"]) / close).fillna(0.0)
    
    # 4. Relative Open (Gap proxy, stationary)
    prev_close = close.shift(1)
    feat["RelOpen"] = ((df["Open"] - prev_close) / prev_close).fillna(0.0)
    
    # 5. Technical Indicators (Stationary versions)
    # Moving Average Convergence Divergence (MACD) relative to price
    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    feat["RelMACD"] = (ema12 - ema26) / close
    
    # RSI (Already bounded 0-100, fairly stationary, but we can center it)
    def compute_rsi(data, window=14):
        delta = data.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
        rs = gain / loss
        return 100 - (100 / (1 + rs))
    
    feat["RSI_Centered"] = (compute_rsi(close) - 50) / 50.0
    feat["RSI_Centered"] = feat["RSI_Centered"].fillna(0.0)
    
    # Final cleanup
    feat = feat.replace([np.inf, -np.inf], np.nan).fillna(0.0)
    
    return feat
