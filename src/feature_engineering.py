from __future__ import annotations
import numpy as np
import pandas as pd

def compute_stationary_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Computes stationary features from OHLCV data to reduce overfitting.

    IMPORTANT — input contract:
    This function receives the output of build_training_frame(), where:
        df["Open"]   = OpenNorm  = (RawOpen / PrevRawClose) - 1   (a return, ~0.005)
        df["High"]   = HighNorm  = (RawHigh / RawClose) - 1        (a ratio deviation, ~0.02)
        df["Low"]    = LowNorm   = (RawLow  / RawClose) - 1        (a ratio deviation, ~-0.01)
        df["Volume"] = VolumeNorm = ln(V_t+1) - ln(V_{t-1}+1)     (already a log-diff)
        df["RawClose"] = raw closing price in dollars              (used as price anchor)

    Raw H/L are reconstructed from normalized columns:
        RawHigh = RawClose * (1 + HighNorm)
        RawLow  = RawClose * (1 + LowNorm)

    Features included (14 total):
        1.  LogReturn       — ln(Close_t / Close_{t-1})
        2.  VolLogDiff      — VolumeNorm passed through directly (already log-diff)
        3.  RelRange        — (RawHigh - RawLow) / RawClose
        4.  RelOpen         — OpenNorm passed through directly (already a gap return)
        5.  RelMACD         — (EMA12 - EMA26) / RawClose
        6.  RSI_Centered    — (RSI - 50) / 50
        7.  RelATR          — ATR(14) / RawClose, using reconstructed raw H/L
        8.  BB_Width        — 4 * std20 / sma20
        9.  BB_Upper_Dist   — (Upper Band - Close) / Close
        10. BB_Lower_Dist   — (Close - Lower Band) / Close
        11. SMA_Trend       — +1.0 / -1.0 / 0.0 crossover signal
        12. RelVWAP         — (Close - VWAP20) / VWAP20, using reconstructed raw H/L
        13. MACD_Signal_Rel — Signal line / RawClose
        14. MACD_Hist_Rel   — MACD histogram / RawClose

    Returns:
        DataFrame with 14 stationary feature columns (+ Date if present).
    """
    feat = pd.DataFrame(index=df.index)
    if "Date" in df.columns:
        feat["Date"] = df["Date"]

    # --- Price anchor: always use RawClose as the price denominator ---
    close_col = "RawClose" if "RawClose" in df.columns else "Close"
    close = df[close_col]

    # Reconstruct raw High and Low from normalized columns.
    # HighNorm = (RawHigh / RawClose) - 1  =>  RawHigh = RawClose * (1 + HighNorm)
    # LowNorm  = (RawLow  / RawClose) - 1  =>  RawLow  = RawClose * (1 + LowNorm)
    raw_high = close * (1.0 + df["High"])
    raw_low  = close * (1.0 + df["Low"])

    # Volume is already VolumeNorm = ln(V_t+1) - ln(V_{t-1}+1), pass through directly.
    volume_norm = df["Volume"]

    # ------------------------------------------------------------------ #
    # 1. Log Returns (stationary price proxy)
    # ------------------------------------------------------------------ #
    feat["LogReturn"] = np.log(close / close.shift(1)).fillna(0.0)

    # ------------------------------------------------------------------ #
    # 2. Volume Log Diff
    #    df["Volume"] IS already the log-diff; do NOT apply log1p().diff() again.
    # ------------------------------------------------------------------ #
    feat["VolLogDiff"] = volume_norm.fillna(0.0)

    # ------------------------------------------------------------------ #
    # 3. Relative Range (intraday volatility proxy)
    #    Uses reconstructed raw H/L so the ratio is meaningful.
    # ------------------------------------------------------------------ #
    feat["RelRange"] = ((raw_high - raw_low) / close).fillna(0.0)

    # ------------------------------------------------------------------ #
    # 4. Relative Open (overnight gap proxy)
    #    df["Open"] IS already OpenNorm = (RawOpen/PrevClose) - 1;
    #    pass through directly — no further normalization needed.
    # ------------------------------------------------------------------ #
    feat["RelOpen"] = df["Open"].fillna(0.0)

    # ------------------------------------------------------------------ #
    # 5. MACD relative to price
    # ------------------------------------------------------------------ #
    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    feat["RelMACD"] = ((ema12 - ema26) / close).fillna(0.0)

    # ------------------------------------------------------------------ #
    # 6. RSI centered around zero
    # ------------------------------------------------------------------ #
    def _compute_rsi(data: pd.Series, window: int = 14) -> pd.Series:
        delta = data.diff()
        gain = delta.where(delta > 0, 0.0).rolling(window=window).mean()
        loss = (-delta.where(delta < 0, 0.0)).rolling(window=window).mean()
        rs = gain / (loss + 1e-9)
        return 100.0 - (100.0 / (1.0 + rs))

    feat["RSI_Centered"] = (_compute_rsi(close) - 50.0) / 50.0

    # ------------------------------------------------------------------ #
    # 7. ATR relative to price
    #    True Range requires raw H/L and raw previous close.
    # ------------------------------------------------------------------ #
    prev_close = close.shift(1)
    tr1 = raw_high - raw_low
    tr2 = (raw_high - prev_close).abs()
    tr3 = (raw_low  - prev_close).abs()
    tr  = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.rolling(window=14).mean()
    feat["RelATR"] = (atr / close).fillna(0.0)

    # ------------------------------------------------------------------ #
    # 8-10. Bollinger Bands (all computed on RawClose — correct)
    # ------------------------------------------------------------------ #
    sma20 = close.rolling(window=20).mean()
    std20 = close.rolling(window=20).std()
    feat["BB_Width"]     = (4.0 * std20 / sma20).fillna(0.0)
    feat["BB_Upper_Dist"] = ((sma20 + 2.0 * std20) - close) / close
    feat["BB_Lower_Dist"] = (close - (sma20 - 2.0 * std20)) / close

    # ------------------------------------------------------------------ #
    # 11. SMA 20/50 trend signal
    # ------------------------------------------------------------------ #
    sma50 = close.rolling(window=50).mean()
    feat["SMA_Trend"] = np.where(sma20 > sma50, 1.0, -1.0)
    feat["SMA_Trend"] = np.where(sma20.isna() | sma50.isna(), 0.0, feat["SMA_Trend"])

    # ------------------------------------------------------------------ #
    # 12. VWAP deviation (rolling 20-day)
    #     Typical price requires raw H/L.
    # ------------------------------------------------------------------ #
    typical_price = (raw_high + raw_low + close) / 3.0
    tp_v         = typical_price * volume_norm.clip(lower=0.0)  # clip: log-diff can be negative
    rolling_tp_v = tp_v.rolling(window=20).sum()
    rolling_vol  = volume_norm.clip(lower=0.0).rolling(window=20).sum()
    vwap         = (rolling_tp_v / (rolling_vol + 1e-9)).fillna(close)
    feat["RelVWAP"] = ((close - vwap) / (vwap + 1e-9)).fillna(0.0)

    # ------------------------------------------------------------------ #
    # 13-14. MACD Signal Line and Histogram relative to price
    # ------------------------------------------------------------------ #
    macd_line   = ema12 - ema26
    signal_line = macd_line.ewm(span=9, adjust=False).mean()
    macd_hist   = macd_line - signal_line
    feat["MACD_Signal_Rel"] = (signal_line / close).fillna(0.0)
    feat["MACD_Hist_Rel"]   = (macd_hist   / close).fillna(0.0)

    # ------------------------------------------------------------------ #
    # Final cleanup: catch any residual inf / nan
    # ------------------------------------------------------------------ #
    feat = feat.replace([np.inf, -np.inf], np.nan).fillna(0.0)

    return feat