#!/usr/bin/env python3
"""
Analyze Exit Signals — Convert per-bar audit CSVs into seed-level metrics.

Reads CSV output from audit_exit_signals.py and produces a summary CSV
with aggregated metrics (exit_rate, confidence stats, buy/hold/exit distribution)
compatible with eval_sweep leaderboard format.

Usage:
    python scripts/analyze_exit_signals.py
    python scripts/analyze_exit_signals.py --input-dir data/audit/exit_signal_sweep
    python scripts/analyze_exit_signals.py --input-dir data/audit/exit_signal_sweep --output summary_exit_signals.csv
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

console = Console()


def analyze_audit_csv(csv_path: Path) -> dict:
    """
    Read a per-bar exit audit CSV and produce seed-level summary metrics.
    
    Returns dict with aggregated metrics:
      - exit_signal_rate_pct: % of bars where exit signal fired
      - avg_confidence: average ensemble vote share (buy votes / total votes)
      - buy_rate_pct: % of bars with BUY signal
      - hold_rate_pct: % of bars with HOLD signal
      - exit_rate_pct: % of bars with EXIT signal
      - high_confidence_rate_pct: % of bars with >0.67 confidence
    """
    df = pd.read_csv(csv_path)
    
    if df.empty:
        return {
            "file": csv_path.name,
            "bars": 0,
            "exit_signal_rate_pct": 0.0,
            "avg_confidence": 0.0,
            "buy_rate_pct": 0.0,
            "hold_rate_pct": 0.0,
            "exit_rate_pct": 0.0,
            "high_confidence_rate_pct": 0.0,
        }
    
    total_bars = len(df)
    
    # Exit signal rate
    exit_signals = df["exit_signal_fired"].sum()
    exit_rate = 100.0 * exit_signals / max(total_bars, 1)
    
    # Confidence stats
    avg_confidence = df["vote_share_buy"].mean()
    high_conf = (df["vote_share_buy"] > 0.67).sum()
    high_conf_rate = 100.0 * high_conf / max(total_bars, 1)
    
    # Action distribution
    action_counts = df["action_label"].value_counts()
    buy_count = action_counts.get("BUY", 0)
    hold_count = action_counts.get("HOLD", 0)
    exit_count = action_counts.get("SELL/EXIT", 0)
    
    buy_rate = 100.0 * buy_count / max(total_bars, 1)
    hold_rate = 100.0 * hold_count / max(total_bars, 1)
    exit_action_rate = 100.0 * exit_count / max(total_bars, 1)
    
    return {
        "file": csv_path.name,
        "bars": total_bars,
        "exit_signal_rate_pct": round(exit_rate, 2),
        "avg_confidence": round(avg_confidence, 4),
        "buy_rate_pct": round(buy_rate, 2),
        "hold_rate_pct": round(hold_rate, 2),
        "exit_signal_count": int(exit_count),
        "exit_rate_pct": round(exit_action_rate, 2),
        "high_confidence_rate_pct": round(high_conf_rate, 2),
    }


def main():
    parser = argparse.ArgumentParser(
        description="Summarize per-bar exit signal audit CSVs into seed-level metrics."
    )
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=ROOT / "data" / "audit" / "exit_signal_sweep",
        help="Directory containing *_exit_audit.csv files from audit_exit_signals.py",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "data" / "audit" / "exit_signal_summary.csv",
        help="Output CSV path for aggregated metrics",
    )
    
    args = parser.parse_args()
    
    if not args.input_dir.exists():
        console.print(f"[red]ERROR:[/red] input directory not found: {args.input_dir}")
        sys.exit(1)
    
    # Find all audit CSVs
    audit_csvs = sorted(args.input_dir.glob("*_exit_audit.csv"))
    
    if not audit_csvs:
        console.print(f"[red]ERROR:[/red] no *_exit_audit.csv files found in {args.input_dir}")
        sys.exit(1)
    
    console.print()
    console.rule("[bold cyan]EXIT SIGNAL ANALYSIS[/bold cyan]")
    console.print(f"  Input dir: {args.input_dir.relative_to(ROOT)}")
    console.print(f"  Found [bold]{len(audit_csvs)}[/bold] audit CSV(s)")
    
    results = []
    
    for csv_path in audit_csvs:
        console.print(f"\n  [cyan]Processing:[/cyan] {csv_path.name}")
        metrics = analyze_audit_csv(csv_path)
        
        # Extract ticker from filename (e.g., "nvda_exit_audit.csv" → "nvda")
        ticker = csv_path.stem.replace("_exit_audit", "").upper()
        metrics["ticker"] = ticker
        
        results.append(metrics)
        
        # Inline summary with colors
        exit_rate = metrics['exit_signal_rate_pct']
        exit_emoji = "⚠️ " if exit_rate < 1.0 else "✅"
        conf_emoji = "✅" if metrics['avg_confidence'] > 0.5 else "⚠️ "
        
        console.print(f"    Bars analyzed: [bold]{metrics['bars']}[/bold]")
        console.print(f"    {exit_emoji} Exit signal rate: [bold]{metrics['exit_signal_rate_pct']:.2f}%[/bold] ({metrics['exit_signal_count']} exits)")
        console.print(f"    {conf_emoji} Avg confidence: [bold]{metrics['avg_confidence']:.4f}[/bold]")
        
        # Action distribution bar
        buy_pct = metrics['buy_rate_pct']
        hold_pct = metrics['hold_rate_pct']
        exit_pct = metrics['exit_rate_pct']
        
        buy_bar = "█" * int(buy_pct / 2)
        hold_bar = "░" * int(hold_pct / 2)
        exit_bar = "▓" * max(1, int(exit_pct / 2))
        
        console.print(f"    Action distribution: [green]{buy_bar}[/green] BUY {buy_pct:.1f}% | [yellow]{hold_bar}[/yellow] HOLD {hold_pct:.1f}% | [red]{exit_bar}[/red] EXIT {exit_pct:.1f}%")
        console.print(f"    High confidence (>0.67): [cyan]{metrics['high_confidence_rate_pct']:.2f}%[/cyan]")
    
    # Create summary dataframe
    summary_df = pd.DataFrame(results)
    
    # Reorder columns for clarity
    col_order = [
        "ticker", "bars", "exit_signal_rate_pct", "exit_signal_count", 
        "avg_confidence", "high_confidence_rate_pct",
        "buy_rate_pct", "hold_rate_pct", "exit_rate_pct", "file"
    ]
    summary_df = summary_df[[c for c in col_order if c in summary_df.columns]]
    
    # Write output
    args.output.parent.mkdir(parents=True, exist_ok=True)
    summary_df.to_csv(args.output, index=False)
    
    # Rich table output
    console.print()
    console.rule("[bold cyan]SUMMARY TABLE[/bold cyan]")
    
    table = Table(title="Exit Signal Metrics", show_header=True, header_style="bold magenta")
    table.add_column("Ticker", style="cyan", width=10)
    table.add_column("Bars", justify="right", width=8)
    table.add_column("Exit Signal %", justify="right", width=14)
    table.add_column("Exits Count", justify="right", width=12)
    table.add_column("Avg Confidence", justify="right", width=14)
    table.add_column("High Conf %", justify="right", width=12)
    table.add_column("Buy %", justify="right", width=8)
    table.add_column("Hold %", justify="right", width=8)
    table.add_column("Exit %", justify="right", width=8)
    
    for _, row in summary_df.iterrows():
        exit_rate = row['exit_signal_rate_pct']
        exit_color = "green" if exit_rate > 5.0 else ("yellow" if exit_rate > 1.0 else "red")
        
        conf_val = row['avg_confidence']
        conf_color = "green" if conf_val > 0.6 else ("yellow" if conf_val > 0.4 else "red")
        
        table.add_row(
            f"[bold]{row['ticker']}[/bold]",
            f"{int(row['bars'])}",
            f"[{exit_color}]{row['exit_signal_rate_pct']:.2f}%[/{exit_color}]",
            f"{int(row['exit_signal_count'])}",
            f"[{conf_color}]{row['avg_confidence']:.4f}[/{conf_color}]",
            f"{row['high_confidence_rate_pct']:.2f}%",
            f"{row['buy_rate_pct']:.2f}%",
            f"{row['hold_rate_pct']:.2f}%",
            f"{row['exit_rate_pct']:.2f}%",
        )
    
    console.print(table)
    
    console.print(f"\n  [bold green]✓[/bold green] Output written to: {args.output.relative_to(ROOT)}")
    
    # Interpretation guide as panel
    interpretation = """[bold cyan]EXIT SIGNAL RATE[/bold cyan]
  <1%   : [red]Stuck in buy/hold mode (no exits)[/red]
  1-5%  : [yellow]Weak exits (consider exit manager layer)[/yellow]
  >5%   : [green]Healthy exit signals[/green]

[bold cyan]AVERAGE CONFIDENCE[/bold cyan]
  1.0   : Unanimous bullish
  0.5   : Neutral ensemble
  0.33  : Lean towards hold

[bold cyan]HIGH CONFIDENCE RATE[/bold cyan]
  >60%  : [green]Ensemble is coherent[/green]
  <30%  : [yellow]Ensemble is split (healthy diversity)[/yellow]

[bold cyan]ACTION DISTRIBUTION[/bold cyan]
  Healthy: Buy ~25-35%, Hold ~60-70%, Exit ~1-5%"""
    
    console.print(Panel(interpretation, title="[bold]Interpretation Guide[/bold]", expand=False))
    console.print()


if __name__ == "__main__":
    main()
