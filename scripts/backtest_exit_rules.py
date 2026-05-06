#!/usr/bin/env python3
"""
ExitManager ablation study.

Sweeps a set of rule configs over the val split, selects the best config
(by Sharpe, subject to exit_rate in [0.02, 0.15]), then evaluates once on
the test split.

Usage:
    python scripts/backtest_exit_rules.py --ticker nvda
    python scripts/backtest_exit_rules.py --ticker amd
    python scripts/backtest_exit_rules.py --ticker nvda amd
    python scripts/backtest_exit_rules.py --ticker nvda --config composite_nvda --test-only
"""
from __future__ import annotations

import argparse
import json
import sys
import warnings
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

warnings.filterwarnings("ignore")

from src.ensemble import SparseEnsemble
from src.exit_manager import ExitManager
from src.trading_env import TradingEnv

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

LEADERBOARD_PATH = ROOT / "data" / "experiment_leaderboard.csv"
ENSEMBLE_CONFIG_PATH = ROOT / "staging" / "models" / "ensemble_config.json"
OUTPUT_DIR = ROOT / "data" / "audit" / "exit_backtest"

BARS_PER_YEAR = 252
TRAIN_RATIO = 0.70
VAL_RATIO = 0.15

STATIONARY_COLS = [
    "LogReturn", "VolLogDiff", "RelRange", "RelOpen", "RelMACD", "RSI_Centered",
    "RelATR", "BB_Width", "BB_Upper_Dist", "BB_Lower_Dist", "SMA_Trend",
    "RelVWAP", "MACD_Signal_Rel", "MACD_Hist_Rel",
]
NEWS_COLS = [
    "NewsCount", "SentimentMean", "SentimentStd", "SentimentMin", "SentimentMax",
    "SentimentConfidenceMean", "SentimentGeminiShare", "SentimentOllamaShare",
]
RAW_MARKET_COLS = [
    "LogReturn", "VolLogDiff", "RelRange", "RelOpen", "RelMACD", "RSI_Centered",
    "RelATR", "BB_Width", "BB_Upper_Dist", "BB_Lower_Dist",
]

# Confirmed audit baselines — used for success gate evaluation only.
BASELINES: Dict[str, Dict[str, float]] = {
    "nvda": {
        "sharpe": 1.828,
        "max_drawdown": -0.0569,
        "cumulative_return": 0.2725,
        "exit_rate": 0.0,
    },
    "amd": {
        "sharpe": 1.995,
        "max_drawdown": -0.0565,
        "cumulative_return": 0.4469,
        "exit_rate": 0.0703,
    },
}

CONFIGS: List[Dict[str, Any]] = [
    {"name": "no_exit",          "rule": None,             "params": {}},
    {"name": "profit_take_2pct", "rule": "profit_take",    "params": {"threshold": 0.02}},
    {"name": "profit_take_3pct", "rule": "profit_take",    "params": {"threshold": 0.03}},
    {"name": "profit_take_5pct", "rule": "profit_take",    "params": {"threshold": 0.05}},
    {"name": "profit_take_8pct", "rule": "profit_take",    "params": {"threshold": 0.08}},
    {"name": "trailing_3pct",    "rule": "trailing_stop",  "params": {"stop_pct": 0.03}},
    {"name": "trailing_5pct",    "rule": "trailing_stop",  "params": {"stop_pct": 0.05}},
    {"name": "trailing_8pct",    "rule": "trailing_stop",  "params": {"stop_pct": 0.08}},
    {"name": "trailing_10pct",   "rule": "trailing_stop",  "params": {"stop_pct": 0.10}},
    {"name": "time_10bars",      "rule": "time",           "params": {"max_bars": 10}},
    {"name": "time_20bars",      "rule": "time",           "params": {"max_bars": 20}},
    {"name": "time_30bars",      "rule": "time",           "params": {"max_bars": 30}},
    {"name": "time_45bars",      "rule": "time",           "params": {"max_bars": 45}},
    {"name": "composite_nvda",   "rule": "composite",      "params": {"rules": [
        {"rule": "profit_take",  "params": {"threshold": 0.03}},
        {"rule": "trailing_stop","params": {"stop_pct": 0.05}},
    ]}},
]

# ---------------------------------------------------------------------------
# Data loading and splitting
# ---------------------------------------------------------------------------

def _split(df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Split into (val, test) using 70/15/15 walk-forward ratios."""
    n = len(df)
    train_end = int(n * TRAIN_RATIO)
    val_end = int(n * (TRAIN_RATIO + VAL_RATIO))
    val_df = df.iloc[train_end:val_end].reset_index(drop=True)
    test_df = df.iloc[val_end:].reset_index(drop=True)
    return val_df, test_df


def _data_path(ticker: str, use_stationary: bool) -> Path:
    suffix = "_stationary" if use_stationary else ""
    return ROOT / "data" / f"tech_training_data_{ticker}{suffix}.parquet"


def _load_data(ticker: str, use_stationary: bool, include_news: bool) -> pd.DataFrame:
    path = _data_path(ticker, use_stationary)
    if not path.exists():
        # Fall back to raw if stationary not found
        path = ROOT / "data" / f"tech_training_data_{ticker}.parquet"
    df = pd.read_parquet(path)
    # Note: the stationary parquets already embed news features from preprocessing.
    # include_news=0 in the leaderboard means "don't fetch fresh news", NOT "exclude from obs".
    # We keep all columns so TradingEnv's auto-detection matches the training obs shape.
    return df


def _pick_market_cols(df: pd.DataFrame) -> List[str]:
    """Return stationary market cols present in df; fall back to raw."""
    cols = [c for c in STATIONARY_COLS if c in df.columns]
    if not cols:
        cols = [c for c in RAW_MARKET_COLS if c in df.columns]
    return cols


def _active_news_cols(df: pd.DataFrame) -> List[str]:
    return [c for c in NEWS_COLS if c in df.columns]

# ---------------------------------------------------------------------------
# Ensemble loading
# ---------------------------------------------------------------------------

def _load_ensemble(
    ticker: str,
    ensemble_cfg: Dict,
    leaderboard: pd.DataFrame,
    run_label_filter: Optional[str] = None,
) -> Tuple[SparseEnsemble, bool, bool]:
    """
    Load ensemble for ticker, return (ensemble, use_stationary, include_news).
    Filters leaderboard to active seeds and takes best model per seed by Sharpe.
    """
    active_seeds = ensemble_cfg[ticker.lower()]["active_seeds"]
    method = ensemble_cfg[ticker.lower()].get("ensemble_method", "voting")

    ticker_rows = leaderboard[
        leaderboard["ticker"].str.lower() == ticker.lower()
    ].copy()
    ticker_rows = ticker_rows[ticker_rows["seed"].isin(active_seeds)].copy()

    if ticker_rows.empty:
        raise ValueError(f"No leaderboard rows for {ticker} with seeds {active_seeds}")

    if run_label_filter:
        filtered = ticker_rows[ticker_rows["run_label"] == run_label_filter]
        if not filtered.empty:
            ticker_rows = filtered

    # Best by test_sharpe_ratio; one model per seed
    ticker_rows = ticker_rows.sort_values("test_sharpe_ratio", ascending=False)
    ticker_rows = ticker_rows.drop_duplicates(subset=["seed"], keep="first")

    best_row = ticker_rows.iloc[0]
    use_stationary = bool(int(best_row.get("use_stationary_features", 0)))
    include_news = bool(int(best_row.get("include_news", 0)))

    print(f"  [{ticker.upper()}] best row: seed={int(best_row['seed'])}, "
          f"run={best_row['run_label']}, Sharpe={best_row['test_sharpe_ratio']:.3f}, "
          f"stationary={use_stationary}, news={include_news}")

    # Build a temporary leaderboard for SparseEnsemble
    tmp_lb_path = ROOT / "data" / f"_backtest_tmp_{ticker}.csv"
    ticker_rows.to_csv(tmp_lb_path, index=False)

    ensemble = SparseEnsemble(str(tmp_lb_path), ranking_metric="test_sharpe_ratio")
    ensemble.active_seeds_df = ticker_rows.copy()
    n_loaded = ensemble.load_top_n_models(
        n=len(active_seeds), seed_filter=active_seeds
    )
    tmp_lb_path.unlink(missing_ok=True)

    print(f"  [{ticker.upper()}] loaded {n_loaded} models")
    return ensemble, use_stationary, include_news

# ---------------------------------------------------------------------------
# Portfolio simulation
# ---------------------------------------------------------------------------

def _fit_obs(obs: np.ndarray, size: int) -> np.ndarray:
    if obs.shape[0] < size:
        return np.concatenate([obs, np.zeros(size - obs.shape[0], dtype=np.float32)])
    if obs.shape[0] > size:
        return obs[:size]
    return obs


def _run_one_config(
    ensemble: SparseEnsemble,
    method: str,
    exit_manager: Optional[ExitManager],
    df: pd.DataFrame,
    market_cols: List[str],
    debug: bool = False,
) -> Dict[str, float]:
    """
    Run portfolio simulation on df with the given exit_manager (or None).
    Returns metrics dict.
    """
    price_col = "RawClose" if "RawClose" in df.columns else "Close"
    df_env = df.reset_index(drop=True)

    env = TradingEnv(
        df_env,
        execution_mode="next_bar",
        include_position_in_observation=True,
            market_feature_columns=market_cols,
        initial_balance=10_000,
        transaction_cost_rate=0.001,
        trade_penalty=0.05,
        spread_bps=1.0,
        slippage_bps=1.0,
    )

    obs, _ = env.reset()

    if exit_manager is not None:
        exit_manager.reset()

    # Fix RNG for deterministic model.predict() behavior during inference
    try:
        import random as _random
        import numpy as _np
        _random.seed(42)
        _np.random.seed(42)
        import torch as _torch
        _torch.manual_seed(42)
        if _torch.cuda.is_available():
            _torch.cuda.manual_seed_all(42)
    except Exception:
        pass

    # Determine expected obs size from largest model
    expected_obs_size = max(
        m.observation_space.shape[0] for m in ensemble.models.values()
    )

    net_worths: List[float] = [env.pm.initial_balance]
    trade_pnls: List[float] = []
    hold_bars_list: List[int] = []
    exit_fired_bars = 0
    total_bars = 0

    in_position = False
    entry_price_tracker = 0.0
    bars_at_exit_decision = 0
    prev_shares = 0.0

    done = False
    debug_actions: List[Tuple[int, float, int]] = []
    while not done:
        step_idx = env.current_step
        if step_idx >= len(df_env):
            break

        total_bars += 1
        shares_held = env.pm.shares_held

        # Detect position transition (from previous execution)
        just_opened = (not in_position) and shares_held > 0
        just_closed = in_position and shares_held <= 0

        if just_closed:
            in_position = False

        if just_opened:
            in_position = True
            entry_price_tracker = max(env.pm.entry_price, 1e-8)
            bars_at_exit_decision = 0
            if exit_manager is not None:
                exit_manager.reset()

        if in_position:
            bars_at_exit_decision += 1

        # Ensemble prediction
        obs_fit = _fit_obs(obs, expected_obs_size)
        action, confidence = ensemble.ensemble_predict(obs_fit, method=method)
        if debug and len(debug_actions) < 50:
            # Print per-model raw outputs for diagnostic visibility
            for info in ensemble.top_models_info:
                seed = int(info["seed"])
                model = ensemble.models[seed]
                m_obs = _fit_obs(obs, model.observation_space.shape[0])
                raw, _ = model.predict(m_obs, deterministic=True)
                raw_val = raw.item() if hasattr(raw, "item") else float(raw)
                print(f"[DEBUG RAW] step={env.current_step:04d} seed={seed} raw={raw_val:+.6f}")
            debug_actions.append((env.current_step, float(confidence), int(action)))

        # ExitManager override (only when in position)
        exit_fired = False
        if in_position and exit_manager is not None:
            current_price = float(df_env.iloc[step_idx][price_col])
            ep = env.pm.entry_price
            upnl = (current_price / max(ep, 1e-8)) - 1.0 if ep > 0 else 0.0
            pos_state = {
                "shares_held": shares_held,
                "entry_price": ep,
                "current_price": current_price,
                "unrealized_pnl_pct": upnl,
                "peak_pnl_pct": 0.0,  # tracked internally by ExitManager
                "bars_held": env.pm.time_in_position,
            }
            fired, _ = exit_manager.should_exit(pos_state, confidence)
            if fired:
                action = 0
                exit_fired = True
                exit_fired_bars += 1

        target_weight = 1.0 if action == 1 else 0.0
        obs, _reward, terminated, truncated, info = env.step(target_weight)

        new_shares = env.pm.shares_held

        # Record completed trade (position just closed after execution)
        if prev_shares > 0 and new_shares <= 0:
            exec_price = float(info.get("execution_price", entry_price_tracker))
            pnl = (exec_price / max(entry_price_tracker, 1e-8)) - 1.0
            trade_pnls.append(pnl)
            hold_bars_list.append(bars_at_exit_decision)

        prev_shares = new_shares
        net_worths.append(env.pm.net_worth)

        done = terminated or truncated

    # Close open position at end (if any) — mark as incomplete trade, do not
    # include in win_rate but note in trade_count
    if prev_shares > 0:
        last_price = float(df_env.iloc[-1][price_col])
        pnl = (last_price / max(entry_price_tracker, 1e-8)) - 1.0
        trade_pnls.append(pnl)
        hold_bars_list.append(bars_at_exit_decision)

    result = _compute_metrics(
        np.array(net_worths, dtype=np.float64),
        trade_pnls,
        hold_bars_list,
        exit_fired_bars,
        total_bars,
        df_env,
        price_col,
    )
    if debug and debug_actions:
        print("\n[DEBUG] First ensemble actions (step, confidence, action):")
        for s, conf, a in debug_actions:
            print(f"  step={s:04d} conf={conf:.3f} action={a}")
        print()
    return result


def _compute_metrics(
    net_worths: np.ndarray,
    trade_pnls: List[float],
    hold_bars_list: List[int],
    exit_fired_bars: int,
    total_bars: int,
    df: pd.DataFrame,
    price_col: str,
) -> Dict[str, float]:
    cum_return = float((net_worths[-1] / max(net_worths[0], 1e-8)) - 1.0)

    returns = np.diff(net_worths) / np.maximum(net_worths[:-1], 1e-8)
    if len(returns) > 1 and np.std(returns) > 1e-10:
        sharpe = float(np.mean(returns) / np.std(returns)) * np.sqrt(BARS_PER_YEAR)
    else:
        sharpe = 0.0

    # Max drawdown (negative value convention)
    peak = net_worths[0]
    max_dd = 0.0
    for nw in net_worths:
        peak = max(peak, nw)
        dd = (peak - nw) / max(peak, 1e-8)
        max_dd = max(max_dd, dd)
    max_drawdown = -max_dd

    # Buy-hold return over same period (proxy for alpha vs benchmark)
    try:
        bh_return = float(df.iloc[-1][price_col]) / float(df.iloc[0][price_col]) - 1.0
    except Exception:
        bh_return = 0.0
    alpha_vs_bh = cum_return - bh_return

    return {
        "sharpe": round(sharpe, 4),
        "alpha_vs_qqq": round(alpha_vs_bh, 4),   # vs buy-hold (QQQ unavailable)
        "max_drawdown": round(max_drawdown, 4),
        "cumulative_return": round(cum_return, 4),
        "avg_hold_bars": round(float(np.mean(hold_bars_list)) if hold_bars_list else 0.0, 2),
        "exit_rate": round(exit_fired_bars / max(total_bars, 1), 4),
        "trade_count": len(trade_pnls),
        "win_rate": round(
            sum(1 for p in trade_pnls if p > 0) / max(len(trade_pnls), 1), 4
        ),
    }

# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

def _print_table(rows: List[Dict], title: str = "") -> None:
    if not rows:
        return
    if title:
        print(f"\n{title}")
    keys = [
        "name", "sharpe", "max_drawdown", "cumulative_return",
        "exit_rate", "avg_hold_bars", "trade_count", "win_rate",
    ]
    hdr = f"{'name':<22} {'sharpe':>7} {'max_dd':>9} {'cum_ret':>9} {'exit%':>7} {'hold':>6} {'trades':>7} {'win%':>6}"
    print(hdr)
    print("-" * len(hdr))
    for r in rows:
        name = r.get("name", "?")
        sharpe = r.get("sharpe", 0.0)
        mdd = r.get("max_drawdown", 0.0)
        cr = r.get("cumulative_return", 0.0)
        er = r.get("exit_rate", 0.0)
        avgh = r.get("avg_hold_bars", 0.0)
        tc = r.get("trade_count", 0)
        wr = r.get("win_rate", 0.0)
        print(f"{name:<22} {sharpe:>7.3f} {mdd:>9.3f} {cr:>9.3f} {er:>7.3f} {avgh:>6.1f} {tc:>7d} {wr:>6.3f}")


def _check_criteria(ticker: str, test_metrics: Dict, config_name: str) -> List[str]:
    """Return list of pass/fail strings for each success criterion."""
    results = []
    m = test_metrics

    if ticker == "nvda":
        results.append(
            f"NVDA sharpe >= 1.828:     {'PASS' if m['sharpe'] >= 1.828 else 'FAIL'} "
            f"(actual={m['sharpe']:.3f})"
        )
        results.append(
            f"NVDA max_dd > -0.045:     {'PASS' if m['max_drawdown'] > -0.045 else 'FAIL'} "
            f"(actual={m['max_drawdown']:.3f})"
        )
        er = m["exit_rate"]
        results.append(
            f"NVDA exit_rate in [0.05,0.10]: {'PASS' if 0.05 <= er <= 0.10 else 'FAIL'} "
            f"(actual={er:.3f})"
        )
        avgh = m["avg_hold_bars"]
        results.append(
            f"NVDA avg_hold in [10,30]: {'PASS' if 10 <= avgh <= 30 else 'FAIL'} "
            f"(actual={avgh:.1f})"
        )
    elif ticker == "amd":
        results.append(
            f"AMD  sharpe >= 1.995:     {'PASS' if m['sharpe'] >= 1.995 else 'FAIL'} "
            f"(actual={m['sharpe']:.3f})"
        )
        results.append(
            f"AMD  max_dd > -0.0565:    {'PASS' if m['max_drawdown'] > -0.0565 else 'FAIL'} "
            f"(actual={m['max_drawdown']:.3f})"
        )
        er = m["exit_rate"]
        results.append(
            f"AMD  exit_rate >= 0.07:   {'PASS' if er >= 0.07 else 'FAIL'} "
            f"(actual={er:.3f})"
        )
    return results

# ---------------------------------------------------------------------------
# Main ticker runner
# ---------------------------------------------------------------------------

def run_ticker(
    ticker: str,
    leaderboard: pd.DataFrame,
    ensemble_cfg: Dict,
    output_dir: Path,
    test_only_config: Optional[str] = None,
    debug: bool = False,
    voting_method: str = "voting",
) -> Dict:
    print(f"\n{'='*60}")
    print(f"  {ticker.upper()} — ExitManager Backtest")
    print(f"{'='*60}")

    ensemble, use_stationary, include_news = _load_ensemble(
        ticker, ensemble_cfg, leaderboard
    )
    method = voting_method  # Use CLI arg if provided; otherwise falls back to config
    if method == "voting":
        method = ensemble_cfg[ticker.lower()].get("ensemble_method", "voting")

    df = _load_data(ticker, use_stationary, include_news)
    val_df, test_df = _split(df)
    market_cols = _pick_market_cols(df)

    print(f"  Data: {_data_path(ticker, use_stationary).name} "
          f"({len(df)} total, val={len(val_df)}, test={len(test_df)})")
    print(f"  Market cols: {len(market_cols)}, News: {include_news}")
    if "Date" in val_df.columns:
        print(f"  Val:  {val_df['Date'].iloc[0]} to {val_df['Date'].iloc[-1]}")
        print(f"  Test: {test_df['Date'].iloc[0]} to {test_df['Date'].iloc[-1]}")

    output_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Val sweep (or test-only mode)
    # ------------------------------------------------------------------
    if test_only_config:
        configs_to_run = [c for c in CONFIGS if c["name"] == test_only_config]
        if not configs_to_run:
            raise ValueError(f"Config '{test_only_config}' not found in CONFIGS list")
        print(f"  --test-only mode: skipping val sweep, evaluating '{test_only_config}' on test split")
        best_cfg_name = test_only_config
        val_rows: List[Dict] = []
    else:
        print(f"\n  Running val sweep ({len(CONFIGS)} configs)...")
        val_rows = []
        for cfg in CONFIGS:
            em = ExitManager(cfg["rule"], cfg["params"]) if cfg["rule"] else None
            metrics = _run_one_config(ensemble, method, em, val_df, market_cols, debug=(debug and cfg == CONFIGS[0]))
            row = {"name": cfg["name"], **metrics}
            val_rows.append(row)
            marker = f"  [exit={metrics['exit_rate']:.3f}] {cfg['name']:<22} Sharpe={metrics['sharpe']:.3f}"
            print(marker)

        val_df_out = pd.DataFrame(val_rows).sort_values("sharpe", ascending=False)
        val_df_out.to_csv(output_dir / f"{ticker}_val_results.csv", index=False)

        _print_table(val_df_out.to_dict("records"), title=f"\nVal ranking ({ticker.upper()}):")

        # Select best config: highest Sharpe with exit_rate in [0.02, 0.15]
        eligible = val_df_out[
            (val_df_out["exit_rate"] >= 0.02) & (val_df_out["exit_rate"] <= 0.15)
        ]
        if eligible.empty:
            print("\n  WARNING: no config with exit_rate in [0.02, 0.15]; "
                  "using overall best Sharpe")
            best_cfg_name = val_df_out.iloc[0]["name"]
        else:
            best_cfg_name = eligible.iloc[0]["name"]

        print(f"\n  Selected best config: {best_cfg_name}")

    # ------------------------------------------------------------------
    # Test evaluation — single shot
    # ------------------------------------------------------------------
    best_cfg = next(c for c in CONFIGS if c["name"] == best_cfg_name)
    em_test = ExitManager(best_cfg["rule"], best_cfg["params"]) if best_cfg["rule"] else None
    print(f"\n  Evaluating '{best_cfg_name}' on test split with voting_method='{method}'...")
    test_metrics = _run_one_config(ensemble, method, em_test, test_df, market_cols, debug=debug)
    test_row = {"name": best_cfg_name, **test_metrics}

    pd.DataFrame([test_row]).to_csv(output_dir / f"{ticker}_test_result.csv", index=False)

    _print_table([test_row], title=f"Test result ({ticker.upper()}) — {best_cfg_name}:")

    criteria = _check_criteria(ticker, test_metrics, best_cfg_name)
    print(f"\n  Success criteria ({ticker.upper()}):")
    for line in criteria:
        print(f"    {line}")

    return {
        "ticker": ticker,
        "best_config": best_cfg_name,
        "val_rows": val_rows,
        "test_metrics": test_metrics,
        "criteria": criteria,
    }

# ---------------------------------------------------------------------------
# Markdown report
# ---------------------------------------------------------------------------

def _write_summary(results: List[Dict], output_dir: Path) -> None:
    lines = ["# ExitManager Backtest Summary\n"]

    for r in results:
        ticker = r["ticker"]
        best = r["best_config"]
        tm = r["test_metrics"]
        baseline = BASELINES.get(ticker, {})

        lines.append(f"## {ticker.upper()}\n")

        if r["val_rows"]:
            lines.append("### Val ranking (all configs)\n")
            lines.append("| Config | Sharpe | MaxDD | CumRet | ExitRate | AvgHold | Trades | WinRate |")
            lines.append("|--------|--------|-------|--------|----------|---------|--------|---------|")
            sorted_rows = sorted(r["val_rows"], key=lambda x: x["sharpe"], reverse=True)
            for row in sorted_rows:
                marker = " ← **selected**" if row["name"] == best else ""
                lines.append(
                    f"| {row['name']}{marker} | {row['sharpe']:.3f} | {row['max_drawdown']:.3f} | "
                    f"{row['cumulative_return']:.3f} | {row['exit_rate']:.3f} | "
                    f"{row['avg_hold_bars']:.1f} | {row['trade_count']} | {row['win_rate']:.3f} |"
                )
            lines.append("")

        lines.append(f"### Selected config: `{best}`\n")
        lines.append("**Rationale:** Highest val Sharpe with exit_rate in [0.02, 0.15].\n")

        lines.append("### Test split results\n")
        lines.append("| Metric | Baseline | Best Config |")
        lines.append("|--------|----------|-------------|")
        for key in ["sharpe", "max_drawdown", "cumulative_return", "exit_rate",
                    "avg_hold_bars", "trade_count", "win_rate"]:
            bval = baseline.get(key, "—")
            tval = tm.get(key, "—")
            bval_str = f"{bval:.3f}" if isinstance(bval, float) else str(bval)
            tval_str = f"{tval:.3f}" if isinstance(tval, float) else str(tval)
            lines.append(f"| {key} | {bval_str} | {tval_str} |")
        lines.append("")

        lines.append("### Success criteria\n")
        for crit in r["criteria"]:
            status = "[PASS]" if "PASS" in crit else "[FAIL]"
            lines.append(f"- {status} {crit}")
        lines.append("")

        # Phase 3 recommendation
        cfg_obj = next((c for c in CONFIGS if c["name"] == best), None)
        if cfg_obj and cfg_obj["rule"]:
            lines.append(f"### Phase 3 recommendation\n")
            lines.append(f"Wire `ExitManager(rule='{cfg_obj['rule']}', params={cfg_obj['params']})` "
                         f"into `backend/signals/agent.py` for `{ticker.upper()}`.\n")
        lines.append("---\n")

    (output_dir / "backtest_summary.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"\nSummary written to {output_dir / 'backtest_summary.md'}")

# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="ExitManager ablation: val sweep + test evaluation."
    )
    parser.add_argument(
        "--ticker", nargs="+", default=["nvda"],
        choices=["nvda", "amd"],
        help="Ticker(s) to run. E.g. --ticker nvda amd",
    )
    parser.add_argument(
        "--config", default=None,
        help="Config name to evaluate directly on test split (skips val sweep).",
    )
    parser.add_argument(
        "--test-only", action="store_true",
        help="If set with --config, skip val sweep and evaluate config on test only.",
    )
    parser.add_argument(
        "--debug", action="store_true",
        help="Print debug info (first 50 ensemble actions) during simulation.",
    )
    parser.add_argument(
        "--voting-method", default="voting", choices=["voting", "weighted", "mean"],
        help="Ensemble voting method: 'voting' (majority), 'weighted' (by Sharpe), or 'mean' (average continuous outputs).",
    )
    args = parser.parse_args()

    test_only_config = args.config if (args.test_only and args.config) else None

    leaderboard = pd.read_csv(LEADERBOARD_PATH)
    ensemble_cfg = json.loads(ENSEMBLE_CONFIG_PATH.read_text())

    all_results = []
    for ticker in args.ticker:
        result = run_ticker(
            ticker=ticker,
            leaderboard=leaderboard,
            ensemble_cfg=ensemble_cfg,
            output_dir=OUTPUT_DIR,
            test_only_config=test_only_config,
            debug=args.debug,
            voting_method=args.voting_method,
        )
        all_results.append(result)

    _write_summary(all_results, OUTPUT_DIR)

    print("\nDone. Output in:", OUTPUT_DIR)


if __name__ == "__main__":
    main()
