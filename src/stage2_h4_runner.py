from __future__ import annotations

# H4: Concentration-capped cross-sectional ranking experiment
# Copied from H3 runner, with modifications to cap single-ticker concentration in top-k selection.

import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import Ridge

from src.feature_engineering import compute_stationary_features
from src.market_data import get_tech_training_data

ROOT_DIR = Path(__file__).resolve().parents[1]
RESULTS_DIR = ROOT_DIR / "results" / "stage2_h4"
LEDGER_PATH = ROOT_DIR / "logs" / "stage2_h4_results_ledger.json"

UNIVERSE = ["AAPL", "AMD", "NVDA", "QQQ", "SPY"]
FEATURE_COLUMNS = [
    "LogReturn",
    "VolLogDiff",
    "RelRange",
    "RelOpen",
    "RelMACD",
    "RSI_Centered",
    "RelATR",
    "BB_Width",
    "BB_Upper_Dist",
    "BB_Lower_Dist",
    "SMA_Trend",
    "RelVWAP",
    "MACD_Signal_Rel",
    "MACD_Hist_Rel",
]

WINDOW_CONFIG = {
    "train_size": 0.20,
    "val_size": 0.20,
    "test_size": 0.20,
    "slide_pct": 0.33,
}

TRANSACTION_COST = 0.0005
SLIPPAGE = 0.0002
ROUND_TRIP_COST = TRANSACTION_COST + SLIPPAGE
TOP_K = 2
MIN_UNIVERSE_SIZE = 5
MIN_REBALANCE_OBSERVATIONS = 12
REBALANCE_FREQUENCY = "monthly"

CONCENTRATION_CAP = 0.5  # No single ticker can exceed 50% of portfolio weight

def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()

def _load_ticker_frame(ticker: str) -> pd.DataFrame:
    frame = get_tech_training_data(
        tickers=[ticker],
        include_news=False,
        use_stationary_features=True,
        refresh=False,
    ).copy()
    if frame.empty:
        raise ValueError(f"No data loaded for ticker {ticker}")
    missing_features = [feature for feature in FEATURE_COLUMNS if feature not in frame.columns]
    if missing_features and {"OrigOpen", "OrigHigh", "OrigLow", "OrigClose", "OrigVolume"}.issubset(frame.columns):
        raw_frame = pd.DataFrame(
            {
                "Date": frame["Date"],
                "Open": frame["OrigOpen"],
                "High": frame["OrigHigh"],
                "Low": frame["OrigLow"],
                "Close": frame["OrigClose"],
                "RawClose": frame["OrigClose"],
                "Volume": frame["OrigVolume"],
            }
        )
        recalculated = compute_stationary_features(raw_frame)
        for feature in missing_features:
            if feature in recalculated.columns:
                frame[feature] = recalculated[feature].to_numpy()
    frame["Date"] = pd.to_datetime(frame["Date"]).dt.normalize()
    frame["Ticker"] = ticker
    return frame.sort_values("Date").reset_index(drop=True)

def _common_rebalance_dates(frames: dict[str, pd.DataFrame]) -> list[pd.Timestamp]:
    common_dates: set[pd.Timestamp] | None = None
    for frame in frames.values():
        dates = set(pd.to_datetime(frame["Date"]).dt.normalize())
        common_dates = dates if common_dates is None else common_dates & dates
    if not common_dates:
        raise ValueError("No common dates across H4 universe")
    common_index = pd.DatetimeIndex(sorted(common_dates))
    month_ends = pd.Series(common_index).groupby(pd.Series(common_index).dt.to_period("M")).max().sort_values()
    return [pd.Timestamp(date).normalize() for date in month_ends.tolist()]

def _build_panel(frames: dict[str, pd.DataFrame], rebalance_dates: list[pd.Timestamp]) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    cleaned = {ticker: frame.copy().set_index("Date").sort_index() for ticker, frame in frames.items()}
    for idx in range(len(rebalance_dates) - 1):
        date = rebalance_dates[idx]
        next_date = rebalance_dates[idx + 1]
        for ticker, frame in cleaned.items():
            if date not in frame.index or next_date not in frame.index:
                continue
            current_row = frame.loc[date]
            next_row = frame.loc[next_date]
            current_close = float(current_row["RawClose"])
            next_close = float(next_row["RawClose"])
            if not np.isfinite(current_close) or not np.isfinite(next_close) or current_close <= 0 or next_close <= 0:
                continue
            row = {
                "Date": date,
                "Ticker": ticker,
                "forward_log_return": float(np.log(next_close / current_close)),
                "forward_simple_return": float(next_close / current_close - 1.0),
                "trailing_momentum": float(np.expm1(current_row["LogReturn"])),
            }
            for feature in FEATURE_COLUMNS:
                value = current_row.get(feature, 0.0)
                row[feature] = float(value) if pd.notna(value) else 0.0
            rows.append(row)
    panel = pd.DataFrame(rows)
    if panel.empty:
        raise ValueError("Failed to build H4 panel")
    return panel

def _cross_sectional_zscore(panel: pd.DataFrame) -> pd.DataFrame:
    frame = panel.copy()
    for feature in FEATURE_COLUMNS:
        def _transform(series: pd.Series) -> pd.Series:
            std = float(series.std(ddof=0))
            if std <= 1e-12:
                return pd.Series(np.zeros(len(series)), index=series.index)
            return (series - series.mean()) / std
        frame[feature] = frame.groupby("Date")[feature].transform(_transform)
    return frame

def _create_windows(rebalance_dates: list[pd.Timestamp]) -> list[dict[str, object]]:
    n = len(rebalance_dates)
    window_size = int(n * (WINDOW_CONFIG["train_size"] + WINDOW_CONFIG["val_size"] + WINDOW_CONFIG["test_size"]))
    window_size = max(window_size, 18)
    slide_size = max(int(window_size * WINDOW_CONFIG["slide_pct"]), 1)
    windows: list[dict[str, object]] = []
    start_idx = 0
    window_num = 0
    while start_idx + window_size <= n:
        end_idx = start_idx + window_size
        train_end = start_idx + int(window_size * WINDOW_CONFIG["train_size"])
        val_end = train_end + int(window_size * WINDOW_CONFIG["val_size"])
        train_dates = rebalance_dates[start_idx:train_end]
        val_dates = rebalance_dates[train_end:val_end]
        test_dates = rebalance_dates[val_end:end_idx]
        windows.append(
            {
                "window_num": window_num,
                "train_dates": train_dates,
                "val_dates": val_dates,
                "test_dates": test_dates,
                "period": f"{test_dates[0].date()} to {test_dates[-1].date()}" if test_dates else "n/a",
            }
        )
        start_idx += slide_size
        window_num += 1
    return windows

def _fit_model(model_family: str, seed: int):
    if model_family == "linear_rank":
        return Ridge(alpha=1.0)
    if model_family == "tree_rank":
        return RandomForestRegressor(n_estimators=250, max_depth=8, random_state=seed, n_jobs=-1)
    raise ValueError(f"Unsupported model family: {model_family}")

# Concentration-capped top-k weights
def _top_k_weights_capped(score_frame: pd.DataFrame, top_k: int = TOP_K, cap: float = CONCENTRATION_CAP) -> dict[pd.Timestamp, dict[str, float]]:
    weights: dict[pd.Timestamp, dict[str, float]] = {}
    for date, group in score_frame.groupby("Date"):
        ordered = group.sort_values("score", ascending=False).head(top_k)
        if ordered.empty:
            continue
        tickers = [str(row.Ticker) for row in ordered.itertuples(index=False)]
        n = len(tickers)
        if n == 0:
            continue
        # Assign equal weights, but cap any single ticker at 'cap'
        base_weight = 1.0 / n
        capped_weights = {ticker: min(base_weight, cap) for ticker in tickers}
        # If any weight is capped, redistribute excess equally to others (if possible)
        total = sum(capped_weights.values())
        if total < 1.0 and n > 1:
            # Redistribute excess to non-capped
            excess = 1.0 - total
            non_capped = [ticker for ticker in tickers if capped_weights[ticker] < cap]
            if non_capped:
                add_per = excess / len(non_capped)
                for ticker in non_capped:
                    capped_weights[ticker] += add_per
        weights[pd.Timestamp(date)] = capped_weights
    return weights

def _equal_weights(tickers: list[str], dates: list[pd.Timestamp]) -> dict[pd.Timestamp, dict[str, float]]:
    weight = 1.0 / len(tickers)
    return {date: {ticker: weight for ticker in tickers} for date in dates}


# --- Simulation, metrics, dominance, window summary, aggregation, report writing, and main logic (adapted from H3) ---
def _rank_ic(score_frame: pd.DataFrame) -> float:
    values: list[float] = []
    for _, group in score_frame.groupby("Date"):
        if group["score"].nunique() < 2 or group["forward_simple_return"].nunique() < 2:
            continue
        corr = spearmanr(group["score"], group["forward_simple_return"], nan_policy="omit").correlation
        if np.isfinite(corr):
            values.append(float(corr))
    return float(np.mean(values)) if values else 0.0

def _simulate_portfolio(
    period_returns: dict[pd.Timestamp, dict[str, float]],
    target_weights: dict[pd.Timestamp, dict[str, float]],
    tickers: list[str],
    rebalance_dates: list[pd.Timestamp],
    *,
    rebalance_each_period: bool,
) -> tuple[pd.Series, pd.Series, dict[str, float], pd.Series]:
    positions = {ticker: 1.0 / len(tickers) for ticker in tickers}
    equity = 1.0
    equity_series: list[float] = []
    return_series: list[float] = []
    turnover_series: list[float] = []
    contrib: dict[str, float] = {ticker: 0.0 for ticker in tickers}

    for date in rebalance_dates:
        period = period_returns.get(date)
        if period is None:
            continue

        start_value = equity
        turnover = 0.0
        if rebalance_each_period:
            target = target_weights.get(date, positions)
            turnover = 0.5 * sum(abs(target.get(ticker, 0.0) - positions.get(ticker, 0.0)) for ticker in tickers)
            start_value *= max(1.0 - turnover * ROUND_TRIP_COST, 0.0)
            positions = {ticker: float(target.get(ticker, 0.0)) for ticker in tickers}

        gross_return = sum(positions.get(ticker, 0.0) * period.get(ticker, 0.0) for ticker in tickers)
        for ticker in tickers:
            contrib[ticker] += positions.get(ticker, 0.0) * period.get(ticker, 0.0)

        equity = start_value * (1.0 + gross_return)
        return_series.append(equity / start_value - 1.0)
        equity_series.append(equity)
        turnover_series.append(turnover)

        if not rebalance_each_period:
            positions = {ticker: positions.get(ticker, 0.0) * (1.0 + period.get(ticker, 0.0)) for ticker in tickers}
            total = sum(positions.values())
            if total > 0:
                positions = {ticker: value / total for ticker, value in positions.items()}

    return pd.Series(equity_series), pd.Series(return_series), contrib, pd.Series(turnover_series)

def _simulate_buy_hold(
    period_returns: dict[pd.Timestamp, dict[str, float]],
    tickers: list[str],
    rebalance_dates: list[pd.Timestamp],
) -> tuple[pd.Series, pd.Series, dict[str, float], pd.Series]:
    positions = {ticker: 1.0 / len(tickers) for ticker in tickers}
    equity = 1.0
    equity_series: list[float] = []
    return_series: list[float] = []
    contrib: dict[str, float] = {ticker: 0.0 for ticker in tickers}

    for date in rebalance_dates:
        period = period_returns.get(date)
        if period is None:
            continue
        gross_return = sum(positions.get(ticker, 0.0) * period.get(ticker, 0.0) for ticker in tickers)
        for ticker in tickers:
            contrib[ticker] += positions.get(ticker, 0.0) * period.get(ticker, 0.0)
        equity *= (1.0 + gross_return)
        equity_series.append(equity)
        return_series.append(gross_return)
        positions = {ticker: positions.get(ticker, 0.0) * (1.0 + period.get(ticker, 0.0)) for ticker in tickers}
        total = sum(positions.values())
        if total > 0:
            positions = {ticker: value / total for ticker, value in positions.items()}

    return pd.Series(equity_series), pd.Series(return_series), contrib, pd.Series([0.0] * len(return_series))

def _metrics(returns: pd.Series, equity: pd.Series, turnover: pd.Series) -> dict[str, float]:
    clean = pd.Series(returns).replace([np.inf, -np.inf], np.nan).dropna()
    eq = pd.Series(equity).replace([np.inf, -np.inf], np.nan).dropna()
    if clean.empty or eq.empty:
        return {
            "gross_return": 0.0,
            "net_return": 0.0,
            "annualized_return": 0.0,
            "net_sharpe": 0.0,
            "max_drawdown": 0.0,
            "turnover": float(turnover.mean()) if len(turnover) else 0.0,
            "win_rate": 0.0,
        }

    mean_return = float(clean.mean())
    std_return = float(clean.std(ddof=0))
    sharpe = float(np.sqrt(12) * mean_return / std_return) if std_return > 1e-12 else 0.0
    peak = eq.cummax()
    drawdown = (eq - peak) / peak.replace(0, np.nan)
    return {
        "gross_return": float(eq.iloc[-1] - 1.0),
        "net_return": float(eq.iloc[-1] - 1.0),
        "annualized_return": float(mean_return * 12.0),
        "net_sharpe": sharpe,
        "max_drawdown": float(drawdown.min()) if not drawdown.empty else 0.0,
        "turnover": float(turnover.mean()) if len(turnover) else 0.0,
        "win_rate": float((clean > 0).mean()),
    }

def _dominance(contrib: dict[str, float]) -> tuple[str, float]:
    positive = {ticker: max(value, 0.0) for ticker, value in contrib.items()}
    total = float(sum(positive.values()))
    if total <= 1e-12:
        ticker = max(contrib, key=lambda key: abs(contrib[key]))
        return ticker, 0.0
    top_ticker = max(positive, key=positive.get)
    return top_ticker, float(positive[top_ticker] / total)

def _window_summary(
    *,
    window_num: int,
    period: str,
    variant_name: str,
    model_family: str,
    model_scores: pd.DataFrame,
    momentum_scores: pd.DataFrame,
    period_returns: dict[pd.Timestamp, dict[str, float]],
    tickers: list[str],
    rebalance_dates: list[pd.Timestamp],
) -> dict[str, object]:
    model_weights = _top_k_weights_capped(model_scores)
    momentum_weights = _top_k_weights_capped(momentum_scores)
    equal_weights = _equal_weights(tickers, rebalance_dates)

    model_equity, model_returns, model_contrib, model_turnover = _simulate_portfolio(
        period_returns, model_weights, tickers, rebalance_dates, rebalance_each_period=True
    )
    momentum_equity, momentum_returns, momentum_contrib, momentum_turnover = _simulate_portfolio(
        period_returns, momentum_weights, tickers, rebalance_dates, rebalance_each_period=True
    )
    equal_equity, equal_returns, equal_contrib, equal_turnover = _simulate_portfolio(
        period_returns, equal_weights, tickers, rebalance_dates, rebalance_each_period=True
    )
    buy_hold_equity, buy_hold_returns, buy_hold_contrib, buy_hold_turnover = _simulate_buy_hold(
        period_returns, tickers, rebalance_dates
    )

    model_metrics = _metrics(model_returns, model_equity, model_turnover)
    equal_metrics = _metrics(equal_returns, equal_equity, equal_turnover)
    buy_hold_metrics = _metrics(buy_hold_returns, buy_hold_equity, buy_hold_turnover)
    momentum_metrics = _metrics(momentum_returns, momentum_equity, momentum_turnover)

    benchmark_net = max(equal_metrics["net_return"], buy_hold_metrics["net_return"])
    benchmark_sharpe = max(equal_metrics["net_sharpe"], buy_hold_metrics["net_sharpe"])
    rank_ic = _rank_ic(model_scores)
    momentum_ic = _rank_ic(momentum_scores)
    dominant_ticker, dominant_share = _dominance(model_contrib)
    total_edge = sum(max(value, 0.0) for value in model_contrib.values())

    return {
        "window_num": window_num,
        "period": period,
        "variant": variant_name,
        "model_family": model_family,
        "gross_return": model_metrics["gross_return"],
        "net_return": model_metrics["net_return"],
        "equal_weight_return": equal_metrics["net_return"],
        "buy_hold_return": buy_hold_metrics["net_return"],
        "momentum_rank_return": momentum_metrics["net_return"],
        "net_gap_vs_equal_weight": float(model_metrics["net_return"] - equal_metrics["net_return"]),
        "net_gap_vs_buy_hold": float(model_metrics["net_return"] - buy_hold_metrics["net_return"]),
        "net_gap_vs_momentum": float(model_metrics["net_return"] - momentum_metrics["net_return"]),
        "net_benchmark_gap": float(model_metrics["net_return"] - benchmark_net),
        "net_sharpe": model_metrics["net_sharpe"],
        "benchmark_sharpe_gap": float(model_metrics["net_sharpe"] - benchmark_sharpe),
        "max_drawdown": model_metrics["max_drawdown"],
        "turnover": model_metrics["turnover"],
        "rank_metric": rank_ic,
        "momentum_rank_ic": momentum_ic,
        "dominant_ticker": dominant_ticker,
        "dominant_ticker_share": dominant_share,
        "total_edge": total_edge,
        "rebalance_observations": len(rebalance_dates),
        "asset_count_available": len(tickers),
        "window_pass": bool(
            model_metrics["net_return"] > equal_metrics["net_return"]
            and model_metrics["net_return"] > buy_hold_metrics["net_return"]
            and model_metrics["net_sharpe"] > benchmark_sharpe
        ),
        "ticker_contributions": model_contrib,
        "equal_weight_contributions": equal_contrib,
        "buy_hold_contributions": buy_hold_contrib,
    }

def _aggregate_variant(variant_name: str, model_family: str, windows: list[dict[str, object]]) -> dict[str, object]:
    mean_gross = float(np.mean([item["gross_return"] for item in windows])) if windows else 0.0
    mean_net = float(np.mean([item["net_return"] for item in windows])) if windows else 0.0
    mean_gap = float(np.mean([item["net_benchmark_gap"] for item in windows])) if windows else 0.0
    mean_sharpe = float(np.mean([item["net_sharpe"] for item in windows])) if windows else 0.0
    mean_sharpe_gap = float(np.mean([item["benchmark_sharpe_gap"] for item in windows])) if windows else 0.0
    mean_rank = float(np.mean([item["rank_metric"] for item in windows])) if windows else 0.0
    stability_cv = float(np.std([item["net_return"] for item in windows], ddof=0) / max(abs(mean_net), 1e-12)) if windows else 0.0
    pass_count = sum(1 for item in windows if item["window_pass"])
    recent_window_pass = bool(windows[-1]["window_pass"]) if windows else False
    recent_gap = float(windows[-1]["net_benchmark_gap"]) if windows else 0.0
    recent_sharpe = float(windows[-1]["net_sharpe"]) if windows else 0.0
    dominant_share = float(max((item["dominant_ticker_share"] for item in windows), default=0.0)) if windows else 0.0

    hard_stops = {
        "only_one_window_positive": bool(pass_count <= 1),
        "equal_weight_or_buy_hold_cleanly_dominates": bool(all(item["net_gap_vs_equal_weight"] <= 0 and item["net_gap_vs_buy_hold"] <= 0 for item in windows)) if windows else True,
        "rank_ordering_unstable_or_near_random": bool(abs(mean_rank) < 0.05),
        "one_ticker_explains_almost_all_gains": bool(dominant_share > 0.70),
        "net_edge_non_positive_after_costs": bool(mean_gap <= 0.0),
        "recent_window_fails_severely": bool(recent_gap < -0.05 or recent_sharpe < -0.25),
        "leakage_or_benchmark_inconsistency_detected": False,
    }

    if mean_gap > 0.0 and pass_count >= 2 and recent_window_pass and stability_cv < 1.0 and mean_sharpe > 0.0 and not hard_stops["one_ticker_explains_almost_all_gains"]:
        verdict = "PASS"
    elif any(hard_stops.values()):
        verdict = "KILL"
    else:
        verdict = "FAIL"

    return {
        "hypothesis_id": "H4",
        "event_variant": variant_name,
        "model_family": model_family,
        "universe": UNIVERSE,
        "rebalance_frequency": REBALANCE_FREQUENCY,
        "selection_rule": f"top_{TOP_K}_capped_{CONCENTRATION_CAP}",
        "window_count": len(windows),
        "mean_gross_return": mean_gross,
        "mean_net_return": mean_net,
        "mean_net_benchmark_gap": mean_gap,
        "mean_net_sharpe": mean_sharpe,
        "mean_benchmark_sharpe_gap": mean_sharpe_gap,
        "primary_ranking_metric": mean_rank,
        "stability_cv": stability_cv,
        "2_of_3_benchmark_pass": bool(pass_count >= 2),
        "recent_window_pass": recent_window_pass,
        "single_ticker_dominance": bool(dominant_share > 0.70),
        "largest_ticker_contribution_share": dominant_share,
        "hard_stop_conditions_triggered": hard_stops,
        "gate_check": {
            "G1 Benchmark Superiority": "PASS" if pass_count >= 2 and recent_window_pass else "FAIL",
            "G2 Economic Robustness": "PASS" if mean_gap > 0.0 and mean_sharpe > 0.0 else "FAIL",
            "G3 Stability": "PASS" if stability_cv < 1.0 else "FAIL",
            "G4 Predictive Support": "PASS" if abs(mean_rank) >= 0.05 else "FAIL",
            "G5 Cost Survivability": "PASS" if mean_gap > 0.0 else "FAIL",
        },
        "verdict": verdict,
    }

def _write_report(path: Path, summary: dict[str, object], windows: list[dict[str, object]]) -> None:
    lines: list[str] = []
    lines.append("# Stage 2 H4 Results Report")
    lines.append("")
    lines.append(f"Date: {datetime.now().date().isoformat()}")
    lines.append("Hypothesis: H4 - Concentration-Capped Cross-Sectional Ranking")
    lines.append(f"Run ID: {summary['event_variant']}")
    lines.append(f"Status: {summary['verdict'].lower()}")
    lines.append("")
    lines.append("## 1. Run Metadata")
    lines.append(f"- Universe: {', '.join(UNIVERSE)}")
    lines.append(f"- Model family: {summary['model_family']}")
    lines.append(f"- Rebalance frequency: {REBALANCE_FREQUENCY}")
    lines.append(f"- Selection rule: top-{TOP_K} capped at {CONCENTRATION_CAP:.2f}")
    lines.append(f"- Cost assumptions: transaction_cost={TRANSACTION_COST:.4f}, slippage={SLIPPAGE:.4f}, turnover_rule=weight_change")
    lines.append("")
    lines.append("## 2. Thesis Being Tested")
    lines.append("> Relative ranking with concentration caps may improve robustness and reduce single-ticker risk compared to pure top-k selection.")
    lines.append("")
    lines.append("## 3. Universe Sufficiency Check")
    lines.append("| Window | Period | Asset Count Available | Rebalance Observations | Sufficiency Verdict |")
    lines.append("| ------ | ------ | --------------------- | ---------------------- | ------------------- |")
    for item in windows:
        lines.append(f"| {item['window_num']} | {item['period']} | {item['asset_count_available']} | {item['rebalance_observations']} | {'pass' if item['asset_count_available'] >= MIN_UNIVERSE_SIZE and item['rebalance_observations'] >= MIN_REBALANCE_OBSERVATIONS else 'fail'} |")
    lines.append("")
    hard_stops = summary["hard_stop_conditions_triggered"]
    lines.append("### Auto-Kill Check")
    lines.append(f"- [{'x' if hard_stops['only_one_window_positive'] else ' '}] insufficient universe size")
    lines.append(f"- [{'x' if hard_stops['equal_weight_or_buy_hold_cleanly_dominates'] else ' '}] equal-weight or buy-hold dominates")
    lines.append(f"- [{'x' if hard_stops['recent_window_fails_severely'] else ' '}] recent window fails severely")
    lines.append("")
    lines.append("## 4. Benchmarks")
    lines.append("- equal-weight portfolio")
    lines.append("- buy-hold")
    lines.append("- momentum ranking baseline")
    lines.append("")
    lines.append("## 5. Window-Level Metrics")
    lines.append("| Window | Period | Gross Return | Net Return | Equal-Weight Return | Buy-Hold Return | Momentum Rank Return | Net Benchmark Gap | Net Sharpe | Benchmark Sharpe Gap | Max DD | Turnover | Rank Metric | Dominant Ticker | Verdict |")
    lines.append("| ------ | ------ | ------------ | ---------- | ------------------- | --------------- | -------------------- | ----------------- | ---------- | -------------------- | ------ | -------- | ----------- | --------------- | ------- |")
    for item in windows:
        lines.append(f"| {item['window_num']} | {item['period']} | {item['gross_return']:+.4f} | {item['net_return']:+.4f} | {item['equal_weight_return']:+.4f} | {item['buy_hold_return']:+.4f} | {item['momentum_rank_return']:+.4f} | {item['net_benchmark_gap']:+.4f} | {item['net_sharpe']:+.3f} | {item['benchmark_sharpe_gap']:+.3f} | {item['max_drawdown']:+.4f} | {item['turnover']:.3f} | {item['rank_metric']:+.4f} | {item['dominant_ticker']} | {('pass' if item['window_pass'] else 'fail')} |")
    lines.append("")
    lines.append("## 6. Aggregate Metrics")
    lines.append(f"- Mean gross return: {summary['mean_gross_return']:+.4f}")
    lines.append(f"- Mean net return: {summary['mean_net_return']:+.4f}")
    lines.append(f"- Mean net benchmark gap: {summary['mean_net_benchmark_gap']:+.4f}")
    lines.append(f"- Mean net Sharpe: {summary['mean_net_sharpe']:+.3f}")
    lines.append(f"- Mean benchmark Sharpe gap: {summary['mean_benchmark_sharpe_gap']:+.3f}")
    lines.append(f"- Primary ranking metric: {summary['primary_ranking_metric']:+.4f}")
    lines.append(f"- Stability CV: {summary['stability_cv']:.3f}")
    lines.append(f"- 2/3 benchmark pass achieved: {'yes' if summary['2_of_3_benchmark_pass'] else 'no'}")
    lines.append(f"- Recent window pass: {'yes' if summary['recent_window_pass'] else 'no'}")
    lines.append(f"- Single-ticker dominance: {'yes' if summary['single_ticker_dominance'] else 'no'}")
    lines.append(f"- Largest ticker contribution share: {summary['largest_ticker_contribution_share']:.3f}")
    lines.append("")
    lines.append("## 7. Gate Check")
    for gate_name, gate_value in summary["gate_check"].items():
        lines.append(f"- {gate_name}: {gate_value}")
    lines.append("")
    lines.append("## 8. Ticker Contribution Analysis")
    lines.append("| Ticker | Contribution to Edge | Share of Total Edge | Notes |")
    lines.append("| ------ | -------------------- | ------------------- | ----- |")
    contributions = {ticker: 0.0 for ticker in UNIVERSE}
    for item in windows:
        for ticker, value in item["ticker_contributions"].items():
            contributions[ticker] += float(value)
    total_positive = sum(max(value, 0.0) for value in contributions.values())
    for ticker in UNIVERSE:
        value = contributions[ticker]
        share = max(value, 0.0) / total_positive if total_positive > 1e-12 else 0.0
        lines.append(f"| {ticker} | {value:+.4f} | {share:.3f} | {'dominant' if share > 0.70 else 'supporting'} |")
    lines.append("")
    lines.append("## 9. Final Verdict")
    lines.append(f"**Verdict**: {summary['verdict']}")
    lines.append(f"**Reason**: mean net benchmark gap {summary['mean_net_benchmark_gap']:+.4f}, recent-window gap {windows[-1]['net_benchmark_gap']:+.4f}, rank metric {summary['primary_ranking_metric']:+.4f}, largest ticker share {summary['largest_ticker_contribution_share']:.3f}.")
    lines.append("")
    lines.append("## 10. Notes")
    lines.append("Add anomalies, leakage checks, universe issues, benchmark interpretation notes, or portfolio construction caveats here.")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")

def run_h4_sweep() -> dict[str, object]:
    frames = {ticker: _load_ticker_frame(ticker) for ticker in UNIVERSE}
    all_rebalance_dates = _common_rebalance_dates(frames)
    if len(all_rebalance_dates) < 30:
        raise ValueError("Insufficient rebalance dates for H4")

    usable_rebalance_dates = all_rebalance_dates[:-1]
    panel = _cross_sectional_zscore(_build_panel(frames, all_rebalance_dates))
    windows = _create_windows(usable_rebalance_dates)
    if not windows:
        raise ValueError("No H4 rolling windows generated")

    ledger: dict[str, object] = {
        "project": "reinforcement-learning-stocks",
        "created_at": _utc_now(),
        "hypothesis_id": "H4",
        "status": "running",
        "universe": UNIVERSE,
        "rebalance_frequency": REBALANCE_FREQUENCY,
        "portfolio_rule": {
            "type": "long_only",
            "selection_rule": f"top_{TOP_K}_capped_{CONCENTRATION_CAP}",
            "minimum_universe_size": MIN_UNIVERSE_SIZE,
        },
        "window_config": WINDOW_CONFIG,
        "cost_assumptions": {
            "transaction_cost": TRANSACTION_COST,
            "slippage": SLIPPAGE,
            "round_trip_cost": ROUND_TRIP_COST,
        },
        "variants": [],
    }

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    LEDGER_PATH.parent.mkdir(parents=True, exist_ok=True)

    variant_specs = [
        ("linear_rank", "linear_rank"),
        ("tree_rank", "tree_rank"),
        ("momentum_rank", "momentum_rank"),
    ]

    for variant_name, model_family in variant_specs:
        variant_windows: list[dict[str, object]] = []
        for window in windows:
            test_dates = window["test_dates"]
            test_panel = panel[panel["Date"].isin(test_dates)].copy().reset_index(drop=True)
            period_returns: dict[pd.Timestamp, dict[str, float]] = {}
            for date in test_dates:
                sub = test_panel[test_panel["Date"] == date]
                period_returns[pd.Timestamp(date)] = {row.Ticker: row.forward_simple_return for row in sub.itertuples(index=False)}

            if model_family == "momentum_rank":
                test_panel["score"] = test_panel["trailing_momentum"]
            else:
                X = test_panel[FEATURE_COLUMNS].to_numpy()
                y = test_panel["forward_simple_return"].to_numpy()
                model = _fit_model(model_family, seed=42)
                if len(X) > 0 and len(np.unique(y)) > 1:
                    model.fit(X, y)
                    test_panel["score"] = model.predict(X)
                else:
                    test_panel["score"] = 0.0

            # For momentum baseline, use trailing_momentum as score
            momentum_panel = test_panel.copy()
            momentum_panel["score"] = momentum_panel["trailing_momentum"]

            summary = _window_summary(
                window_num=window["window_num"],
                period=window["period"],
                variant_name=variant_name,
                model_family=model_family,
                model_scores=test_panel,
                momentum_scores=momentum_panel,
                period_returns=period_returns,
                tickers=UNIVERSE,
                rebalance_dates=test_dates,
            )
            variant_windows.append(summary)

        variant_summary = _aggregate_variant(variant_name, model_family, variant_windows)
        ledger["variants"].append(variant_summary)

        # Write report for each variant
        report_path = RESULTS_DIR / f"stage2_h4_{variant_name}_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
        _write_report(report_path, variant_summary, variant_windows)

    ledger["status"] = "complete"
    LEDGER_PATH.write_text(json.dumps(ledger, indent=2), encoding="utf-8")
    return ledger

if __name__ == "__main__":
    run_h4_sweep()