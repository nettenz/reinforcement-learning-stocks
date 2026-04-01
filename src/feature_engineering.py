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
    def _compute_rsi(data, window=14):
        delta = data.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
        rs = gain / (loss + 1e-9)
        return 100 - (100 / (1 + rs))
    
    feat["RSI_Centered"] = (_compute_rsi(close) - 50) / 50.0

    # 6. Additional Indicators
    # ATR (Average True Range) relative to Price
    high = df["High"]
    low = df["Low"]
    tr1 = high - low
    tr2 = abs(high - close.shift(1))
    tr3 = abs(low - close.shift(1))
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.rolling(window=14).mean()
    feat["RelATR"] = (atr / close).fillna(0.0)

    # Bollinger Band Width
    sma20 = close.rolling(window=20).mean()
    std20 = close.rolling(window=20).std()
    feat["BB_Width"] = (4 * std20 / sma20).fillna(0.0)
    feat["BB_Upper_Dist"] = ((sma20 + 2*std20) - close) / close
    feat["BB_Lower_Dist"] = (close - (sma20 - 2*std20)) / close

    # SMA 20/50 Cross (Trend signal)
    sma50 = close.rolling(window=50).mean()
    feat["SMA_Trend"] = np.where(sma20 > sma50, 1.0, -1.0)
    feat["SMA_Trend"] = np.where(sma20.isna() | sma50.isna(), 0.0, feat["SMA_Trend"])

    # 7. VWAP (Volume Weighted Average Price) - Rolling 20-day
    typical_price = (high + low + close) / 3.0
    tp_v = typical_price * volume
    rolling_tp_v = tp_v.rolling(window=20).sum()
    rolling_vol = volume.rolling(window=20).sum()
    vwap = (rolling_tp_v / (rolling_vol + 1e-9)).fillna(close)
    feat["RelVWAP"] = (close - vwap) / (vwap + 1e-9)

    # 8. Enhanced MACD (Signal Line and Histogram)
    # EMA12 and EMA26 already defined above for RelMACD
    # Let's derive them explicitly if needed for clarification
    macd_line = ema12 - ema26
    signal_line = macd_line.ewm(span=9, adjust=False).mean()
    macd_hist = macd_line - signal_line
    
    # Normalize by Price to keep stationary
    feat["MACD_Signal_Rel"] = (signal_line / close).fillna(0.0)
    feat["MACD_Hist_Rel"] = (macd_hist / close).fillna(0.0)
    
    # Final cleanup
    feat = feat.replace([np.inf, -np.inf], np.nan).fillna(0.0)
    
    return feat
