#!/usr/bin/env python3
"""
Exit Signal Audit — Separate buy/hold/sell bias from true signal capability.

Runs the current ensemble (from ensemble_config.json) over NVDA and AMD test splits
and reports:
  - Vote distribution (how many models vote buy vs hold per bar)
  - 3-way action interpretation (buy, hold, sell/exit)
  - Exit signal frequency (when does ensemble signal to exit a position?)

Output: CSV + JSON summary to data/audit/exit_signal_sweep/

Usage:
    python scripts/audit_exit_signals.py
    python scripts/audit_exit_signals.py --ticker nvda amd
    python scripts/audit_exit_signals.py --ticker amd --output-dir /path/to/audit
"""

from __future__ import annotations

import argparse
import json
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

warnings.filterwarnings("ignore")

from src.ensemble import SparseEnsemble
from src.market_data import get_tech_training_data
from src.trading_env import TradingEnv

console = Console()

STATIONARY_COLS = [
    "LogReturn", "VolLogDiff", "RelRange", "RelOpen", "RelMACD", "RSI_Centered",
    "RelATR", "BB_Width", "BB_Upper_Dist", "BB_Lower_Dist", "SMA_Trend",
    "RelVWAP", "MACD_Signal_Rel", "MACD_Hist_Rel",
]

NEWS_COLS = [
    "NewsCount", "SentimentMean", "SentimentStd", "SentimentMin", "SentimentMax",
    "SentimentConfidenceMean", "SentimentGeminiShare", "SentimentOllamaShare",
]


def _fit_obs(obs: np.ndarray, size: int) -> np.ndarray:
    """Pad or trim observation to match expected size."""
    if obs.shape[0] < size:
        return np.concatenate([obs, np.zeros(size - obs.shape[0], dtype=np.float32)])
    if obs.shape[0] > size:
        return obs[:size]
    return obs


def _pick_cols(
    df: pd.DataFrame, expected_total: int
) -> tuple[list[str], list[str]]:
    """Select market and news columns to match model's expected obs shape."""
    state_count = 5  # [balance, shares_held, weight, unrealized_pnl, time_in_position]
    market_plus_news = expected_total - state_count

    # Prioritize stationary; fall back to OHLCV
    market = [c for c in STATIONARY_COLS if c in df.columns]
    if not market:
        market = [c for c in ["Open", "High", "Low", "Close", "Volume"] if c in df.columns]

    news = [c for c in NEWS_COLS if c in df.columns]

    # If we have plenty, take only what we need
    if len(market) + len(news) > market_plus_news:
        market = market[: min(len(market), market_plus_news)]
        remaining = market_plus_news - len(market)
        news = news[: max(0, remaining)]

    return market, news


def _test_split(df: pd.DataFrame) -> pd.DataFrame:
    """Extract test split (last 15% after val ends at 85%)."""
    n = len(df)
    val_end = int(n * 0.85)
    return df.iloc[val_end:].reset_index(drop=True)


def audit_ticker(ticker: str, output_dir: Path, config_path: Path) -> dict:
    """
    Run exit signal audit for one ticker.
    Returns summary dict with vote distribution and 3-way action counts.
    """
    console.rule(f"[bold cyan]{ticker.upper()} — EXIT SIGNAL AUDIT[/bold cyan]")

    # Load config
    config = json.loads(config_path.read_text())
    if ticker not in config:
        console.print(f"[yellow]SKIP[/yellow] Ticker not in ensemble_config.json: {ticker}")
        return {"ticker": ticker, "status": "skip", "reason": "not in config"}

    t_cfg = config[ticker]
    
    # Load leaderboard (use main experiment leaderboard)
    leaderboard_path = ROOT / "data" / "experiment_leaderboard.csv"
    if not leaderboard_path.exists():
        console.print(f"[yellow]SKIP[/yellow] Leaderboard not found: {leaderboard_path}")
        return {"ticker": ticker, "status": "skip", "reason": "leaderboard not found"}

    # Load leaderboard and get best config from active seeds
    leaderboard = pd.read_csv(leaderboard_path)
    ticker_rows = leaderboard[leaderboard["ticker"].str.lower() == ticker].copy()
    ticker_rows = ticker_rows[ticker_rows["seed"].isin(t_cfg["active_seeds"])].copy()

    if ticker_rows.empty:
        console.print(f"[yellow]SKIP[/yellow] No active seeds found for {ticker}")
        return {"ticker": ticker, "status": "skip", "reason": "no active seeds"}

    best = ticker_rows.sort_values("test_sharpe_ratio", ascending=False).iloc[0]
    include_news = bool(int(best.get("include_news", 0)))
    use_stationary = bool(int(best.get("use_stationary_features", 0)))

    console.print(f"  [cyan]Leaderboard:[/cyan] {leaderboard_path.name}")
    console.print(f"  [cyan]Active seeds:[/cyan] {t_cfg['active_seeds']}")
    console.print(f"  [cyan]Best config:[/cyan] seed=[bold]{int(best['seed'])}[/bold], news={include_news}, stationary={use_stationary}")

    # Load data
    df = get_tech_training_data(
        ticker_preset=ticker,
        interval="1d",
        include_news=include_news,
        use_stationary_features=use_stationary,
        refresh=False,
    )
    test_df = _test_split(df)
    console.print(f"  [cyan]Test split:[/cyan] {len(test_df)} bars ({test_df['Date'].iloc[0]} to {test_df['Date'].iloc[-1]})")

    # Load ensemble
    ensemble = SparseEnsemble(str(leaderboard_path))
    ensemble.active_seeds_df = ensemble.active_seeds_df[
        (ensemble.active_seeds_df["ticker"].str.lower() == ticker)
        & (ensemble.active_seeds_df["seed"].isin(t_cfg["active_seeds"]))
    ]
    ensemble.load_top_n_models(
        n=len(t_cfg["active_seeds"]), seed_filter=t_cfg["active_seeds"]
    )
    console.print(f"  [cyan]Loaded:[/cyan] {len(ensemble.models)} models")

    # Determine expected obs shape
    expected_obs_shape = max(
        model.observation_space.shape[0] for model in ensemble.models.values()
    )
    console.print(f"  [cyan]Obs shape:[/cyan] {expected_obs_shape}")

    # Pick feature columns
    market_cols, news_cols = _pick_cols(test_df, expected_obs_shape)
    console.print(f"  [cyan]Features:[/cyan] {len(market_cols)} market + {len(news_cols)} news")

    # Initialize env
    env = TradingEnv(
        test_df,
        execution_mode="next_bar",
        include_position_in_observation=True,
        market_feature_columns=market_cols,
    )

    obs, _ = env.reset()
    obs = _fit_obs(obs, expected_obs_shape)

    # Run audit
    rows = []
    buy_count = 0
    hold_count = 0
    exit_count = 0
    vote_share_sum = 0.0

    for _ in range(len(test_df)):
        step_idx = env.current_step
        row = test_df.iloc[step_idx]
        pre_pos = int(env.pm.shares_held > 0)

        # Collect votes from all models
        votes = []
        for model in ensemble.models.values():
            model_obs = _fit_obs(obs, model.observation_space.shape[0])
            raw, _ = model.predict(model_obs, deterministic=True)
            raw_val = raw.item() if hasattr(raw, "item") else float(raw)
            votes.append(1 if raw_val > 0.0 else 0)

        buy_votes = int(sum(votes))
        hold_votes = int(len(votes) - buy_votes)
        action = 1 if buy_votes > hold_votes else 0
        confidence = buy_votes / max(len(votes), 1)

        # 3-way interpretation: buy, hold, or explicit exit signal
        # Exit signal fires only if: we were in position AND the ensemble votes to hold (action=0)
        exit_signal_fired = bool(action == 0 and pre_pos == 1)
        
        if action == 1:
            action_3way = "BUY"
            buy_count += 1
        elif exit_signal_fired:
            action_3way = "SELL/EXIT"
            exit_count += 1
        else:
            action_3way = "HOLD"
            hold_count += 1

        vote_share_sum += confidence

        rows.append({
            "step": int(step_idx),
            "date": pd.to_datetime(row["Date"]),
            "price": float(row[env.price_column]),
            "buy_votes": buy_votes,
            "hold_votes": hold_votes,
            "vote_share_buy": confidence,
            "ensemble_action_binary": int(action),
            "action_label": action_3way,
            "exit_signal_fired": int(exit_signal_fired),
            "in_position_before": pre_pos,
        })

        obs, _, terminated, truncated, _ = env.step(
            np.array([1.0 if action == 1 else -1.0], dtype=np.float32)
        )
        obs = _fit_obs(obs, expected_obs_shape)

        if terminated or truncated:
            break

    out = pd.DataFrame(rows)
    out_path = output_dir / f"{ticker}_exit_audit.csv"
    out.to_csv(out_path, index=False)
    console.print(f"\n  [green][OK][/green] Audit CSV: {out_path.relative_to(ROOT)}")

    summary = {
        "ticker": ticker.upper(),
        "status": "complete",
        "bars": int(len(out)),
        "buy_count": int(buy_count),
        "hold_count": int(hold_count),
        "exit_signal_count": int(exit_count),
        "buy_rate_pct": round(100.0 * buy_count / max(len(out), 1), 2),
        "hold_rate_pct": round(100.0 * hold_count / max(len(out), 1), 2),
        "exit_signal_rate_pct": round(100.0 * exit_count / max(len(out), 1), 2),
        "avg_buy_vote_share": round(vote_share_sum / max(len(out), 1), 4),
        "active_seeds": t_cfg["active_seeds"],
        "include_news": include_news,
        "use_stationary_features": use_stationary,
        "output_csv": str(out_path.relative_to(ROOT)),
    }

    summary_path = output_dir / f"{ticker}_exit_audit_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2))
    console.print(f"  [green][OK][/green] Summary JSON: {summary_path.relative_to(ROOT)}")

    exit_rate = summary['exit_signal_rate_pct']
    buy_bar = "=" * int(summary['buy_rate_pct'] / 3)
    hold_bar = "-" * int(summary['hold_rate_pct'] / 3)
    exit_bar = "*" * max(1, int(exit_rate / 3))
    
    console.print(f"\n  [bold]Signal Distribution:[/bold]")
    console.print(f"    [green]{buy_bar}[/green] BUY:  {summary['buy_rate_pct']:>6.2f}%")
    console.print(f"    [yellow]{hold_bar}[/yellow] HOLD: {summary['hold_rate_pct']:>6.2f}%")
    exit_color = "green" if exit_rate > 5.0 else ("yellow" if exit_rate > 1.0 else "red")
    console.print(f"    [{exit_color}]{exit_bar}[/{exit_color}] EXIT: {exit_rate:>6.2f}%")
    console.print(f"\n  [bold]Ensemble Health:[/bold]")
    console.print(f"    Avg vote share (buy): {summary['avg_buy_vote_share']:.4f} (1.0=unanimous bullish, 0.5=neutral)")

    return summary


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Audit exit signal distribution from ensemble votes. "
        "Focus on production-ready tickers (NVDA, AMD) to evaluate when ensembles explicitly signal to sell/exit."
    )
    parser.add_argument(
        "--ticker",
        nargs="+",
        choices=["nvda", "amd", "aapl"],
        default=["nvda", "amd"],
        help="Tickers to audit. Default: nvda amd (production_ready=true). AAPL is marginal (production_ready='monitor').",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ROOT / "data" / "audit" / "exit_signal_sweep",
        help="Output directory for CSV and JSON",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=ROOT / "staging" / "models" / "ensemble_config.json",
        help="Path to ensemble_config.json",
    )

    args = parser.parse_args()
    
    if not args.config.exists():
        console.print(f"[red]ERROR:[/red] ensemble_config.json not found: {args.config}")
        sys.exit(1)

    # Create output dir
    args.output_dir.mkdir(parents=True, exist_ok=True)

    console.rule("[bold cyan]EXIT SIGNAL AUDIT[/bold cyan]")
    console.print(f"  Output dir: {args.output_dir.relative_to(ROOT)}")
    console.print(f"  Config: {args.config.relative_to(ROOT)}\n")

    results = []
    for ticker in args.ticker:
        r = audit_ticker(ticker, args.output_dir, args.config)
        results.append(r)

    console.rule("[bold cyan]SUMMARY[/bold cyan]")
    
    table = Table(title="Exit Signal Audit Results", show_header=True, header_style="bold magenta")
    table.add_column("Ticker", style="cyan", width=10)
    table.add_column("Bars", justify="right", width=8)
    table.add_column("Exit Rate %", justify="right", width=12)
    table.add_column("Exits", justify="right", width=8)
    table.add_column("Avg Confidence", justify="right", width=16)
    table.add_column("Buy %", justify="right", width=8)
    table.add_column("Hold %", justify="right", width=8)
    table.add_column("Exit %", justify="right", width=8)
    
    for r in results:
        status = r.get("status", "unknown")
        if status == "complete":
            exit_rate = r['exit_signal_rate_pct']
            exit_color = "green" if exit_rate > 5.0 else ("yellow" if exit_rate > 1.0 else "red")
            
            conf_val = r['avg_buy_vote_share']
            conf_color = "green" if conf_val > 0.6 else ("yellow" if conf_val > 0.4 else "red")
            
            table.add_row(
                f"[bold]{r['ticker']}[/bold]",
                f"{int(r['bars'])}",
                f"[{exit_color}]{exit_rate:.2f}%[/{exit_color}]",
                f"{r['exit_signal_count']}",
                f"[{conf_color}]{conf_val:.4f}[/{conf_color}]",
                f"{r['buy_rate_pct']:.2f}%",
                f"{r['hold_rate_pct']:.2f}%",
                f"{r['exit_signal_rate_pct']:.2f}%",
            )
        else:
            table.add_row(
                f"[yellow]{r['ticker']}[/yellow]",
                "-", "-", "-", "-", "-", "-", "-"
            )
    
    console.print(table)
    
    console.print(f"\n  Key metric: EXIT signal rate (%)")
    console.print(f"    [red]<1%[/red]   → stuck in buy/hold mode")
    console.print(f"    [yellow]1-5%[/yellow]  → weak exits, consider exit manager")
    console.print(f"    [green]>5%[/green]   → healthy exit signals\n")

if __name__ == "__main__":
    main()
