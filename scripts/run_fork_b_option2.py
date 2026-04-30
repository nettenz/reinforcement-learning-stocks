"""
Fork B — Option 2: Sparse Episodic RL

Hypothesis being tested:
  If Fork B Option 1 showed test-period activity but poor variance, replace dense
  reward shaping with sparse episodic rewards to prevent step-level reward hacking.
  The agent only receives a signal at the end of a fixed episode based on final equity vs buy-hold.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

os.environ.setdefault("PYTHONUTF8", "1")
os.environ["TQDM_DISABLE"] = "1"
if hasattr(sys.stdout, "reconfigure"):

    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import pandas as pd
from rich.console import Console
from rich.panel import Panel
from rich.progress import BarColumn, MofNCompleteColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich.table import Table

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.experiments import build_parser, run_experiments, write_experiment_outputs

console = Console()

DEFAULT_LEADERBOARD  = ROOT_DIR / "data"  / "fork_b_option2_leaderboard.csv"
DEFAULT_REWARD_LB    = ROOT_DIR / "data"  / "fork_b_option2_reward_leaderboard.csv"
DEFAULT_SUMMARY      = ROOT_DIR / "data"  / "fork_b_option2_summary.json"
DEFAULT_LEDGER       = ROOT_DIR / "logs"  / "fork_b_option2_ledger.json"
DEFAULT_SNAPSHOT_DIR = ROOT_DIR / "data"  / "fork_b_option2_snapshots"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Fork B Option 2 — Sparse episodic RL runner with rich progress"
    )
    p.add_argument("--ticker",    default="nvda", help="Ticker preset (default: nvda — best Stage 1 performer)")
    p.add_argument("--seeds",     default="7,13,21,42,99", help="Comma-separated seeds (5 recommended for CV check)")
    p.add_argument("--timesteps", default="50000", help="Training timesteps per run")
    p.add_argument("--ent-coef", "--entropy-coef", default="0.05", help="Single entropy coefficient")
    p.add_argument("--max-episode-steps", type=int, default=60, help="Episode length for sparse rewards")
    p.add_argument("--run-label", default="fork_b_option2", help="Label for output artifacts")
    p.add_argument("--append", action="store_true", help="Append to existing leaderboards instead of overwriting")
    p.add_argument("--ledger-out", type=Path, default=DEFAULT_LEDGER)
    return p.parse_args()


def _build_experiment_args(cli: argparse.Namespace) -> argparse.Namespace:
    """Construct the full experiments.py argparse namespace with Option 1 settings."""
    exp_parser = build_parser()

    data_dir = ROOT_DIR / "data"
    leaderboard_path = data_dir / f"{cli.run_label}_leaderboard.csv"
    reward_lb_path = data_dir / f"{cli.run_label}_reward_leaderboard.csv"
    summary_path = data_dir / f"{cli.run_label}_summary.json"
    snapshot_dir = data_dir / f"{cli.run_label}_snapshots"

    argv = [
        "--ticker",                      cli.ticker,
        "--seeds",                       cli.seeds,
        "--timesteps",                   cli.timesteps,
        "--ent-coefs",                   cli.ent_coef,
        "--learning-rates",              "0.0003",
        "--gammas",                      "0.99",
        # Sparse Episodic Reward
        "--reward-mode",                 "sparse",
        "--max-episode-steps",           str(cli.max_episode_steps),
        "--random-start",
        "--reward-return-scale",         "1.0",
        "--reward-direction-scale",      "0.0",
        "--reward-hold-penalty-scale",   "0.0",
        "--reward-drawdown-penalty-scale","0.0",
        "--reward-action-bonus-scale",   "0.0",
        "--reward-turnover-penalty-scale","0.0",
        "--reward-pnl-scale",            "0.0",
        "--rolling-reward-window",       "60",
        "--reward-clip",                 "1.0",
        # Binary long/flat, no shorts
        "--binary-actions",
        "--long-only",
        # Execution realism
        "--execution-mode",   "next_bar",
        "--spread-bps",       "1.0",
        "--slippage-bps",     "1.0",
        "--transaction-cost-rate", "0.001",
        # Features
        "--use-stationary-features",
        # Split
        "--train-ratio", "0.70",
        "--val-ratio",   "0.15",
        # Output routing — separate from the main leaderboard
        "--leaderboard-path",        str(leaderboard_path),
        "--reward-leaderboard-path", str(reward_lb_path),
        "--summary-path",            str(summary_path),
        "--snapshot-dir",            str(snapshot_dir),
        "--run-label",               cli.run_label,
        "--compact-output",
        # No gate enforcement during the run itself — we apply our own gate below
        "--no-promote-require-gates",
    ]

    return exp_parser.parse_args(argv)


def _gate_check(leaderboard: pd.DataFrame) -> dict:
    """Apply the Option 1 gate: test trades > 0, mean test Sharpe > 0."""
    if leaderboard.empty:
        return {"error": "empty leaderboard", "pass": False}

    seeds_with_trades = int((leaderboard["test_trade_count"] > 0).sum())
    n_seeds = len(leaderboard)
    mean_test_sharpe = float(leaderboard["test_sharpe_ratio"].mean()) if "test_sharpe_ratio" in leaderboard.columns else 0.0
    mean_test_trades = float(leaderboard["test_trade_count"].mean())
    mean_val_acc = float(leaderboard["val_actionable_accuracy"].mean()) if "val_actionable_accuracy" in leaderboard.columns else 0.0
    mean_test_acc = float(leaderboard["test_actionable_accuracy"].mean()) if "test_actionable_accuracy" in leaderboard.columns else 0.0

    # CV of test returns across seeds
    if "test_cumulative_signal_return" in leaderboard.columns:
        rets = leaderboard["test_cumulative_signal_return"]
        cv = float(rets.std(ddof=0) / abs(rets.mean())) if abs(rets.mean()) > 1e-8 else float("inf")
    else:
        cv = float("inf")

    g1_pass = seeds_with_trades >= max(3, int(n_seeds * 0.6))
    g2_pass = mean_test_sharpe > 0.0

    return {
        "n_seeds": n_seeds,
        "seeds_with_test_trades": seeds_with_trades,
        "mean_test_trade_count": mean_test_trades,
        "mean_test_sharpe": mean_test_sharpe,
        "mean_val_actionable_accuracy": mean_val_acc,
        "mean_test_actionable_accuracy": mean_test_acc,
        "test_return_cv": cv,
        "g1_test_activity": {"result": "PASS" if g1_pass else "FAIL", "detail": f"{seeds_with_trades}/{n_seeds} seeds traded in test"},
        "g2_positive_sharpe": {"result": "PASS" if g2_pass else "FAIL", "detail": f"mean test Sharpe = {mean_test_sharpe:+.3f}"},
        "overall": "PASS" if (g1_pass and g2_pass) else "FAIL",
        "recommendation": (
            "Review performance — sparse episodes should yield strong Sharpe/activity."
        ),
    }


def _print_results_table(leaderboard: pd.DataFrame) -> None:
    tbl = Table(title="Fork B Option 2 — Per-Seed Results", show_lines=True)
    tbl.add_column("Seed", justify="center", style="dim")
    tbl.add_column("Val Acc", justify="right")
    tbl.add_column("Test Acc", justify="right")
    tbl.add_column("Test Trades", justify="right")
    tbl.add_column("Test Sharpe", justify="right")
    tbl.add_column("Test Return", justify="right")
    tbl.add_column("Val/Test Gap", justify="right")

    for _, row in leaderboard.iterrows():
        seed = str(int(row.get("seed", 0)))
        val_acc  = float(row.get("val_actionable_accuracy",  0.0))
        test_acc = float(row.get("test_actionable_accuracy", 0.0))
        trades   = int(row.get("test_trade_count", 0))
        sharpe   = float(row.get("test_sharpe_ratio", 0.0))
        ret      = float(row.get("test_cumulative_signal_return", 0.0))
        gap      = abs(val_acc - test_acc)

        trade_color  = "green" if trades > 0  else "red"
        sharpe_color = "green" if sharpe > 0  else "red"
        gap_color    = "green" if gap <= 0.05 else "red"

        tbl.add_row(
            seed,
            f"{val_acc:.3f}",
            f"{test_acc:.3f}",
            f"[{trade_color}]{trades}[/{trade_color}]",
            f"[{sharpe_color}]{sharpe:+.3f}[/{sharpe_color}]",
            f"{ret:+.4f}",
            f"[{gap_color}]{gap:.3f}[/{gap_color}]",
        )

    console.print(tbl)


def _print_gate_table(gates: dict) -> None:
    tbl = Table(title="Option 2 Gates", show_lines=False)
    tbl.add_column("Gate", style="bold")
    tbl.add_column("Result", justify="center")
    tbl.add_column("Detail")

    for key in ("g1_test_activity", "g2_positive_sharpe"):
        g = gates[key]
        color = "green" if g["result"] == "PASS" else "red"
        tbl.add_row(
            key.replace("_", " ").title(),
            f"[{color}]{g['result']}[/{color}]",
            g["detail"],
        )

    tbl.add_row("Test return CV", "", f"{gates['test_return_cv']:.3f}  (gate threshold < 3.0 for any signal)")
    console.print(tbl)

    color = "green" if gates["overall"] == "PASS" else "red"
    console.print(Panel(
        f"[{color}][bold]{gates['overall']}[/bold][/{color}]\n\n"
        f"{gates['recommendation']}",
        title="[bold]Fork B Option 2 — Verdict[/bold]",
        expand=False,
    ))


def main() -> int:
    cli = _parse_args()
    
    data_dir = ROOT_DIR / "data"
    leaderboard_path = data_dir / f"{cli.run_label}_leaderboard.csv"
    reward_lb_path = data_dir / f"{cli.run_label}_reward_leaderboard.csv"
    summary_path = data_dir / f"{cli.run_label}_summary.json"
    snapshot_dir = data_dir / f"{cli.run_label}_snapshots"
    ledger_out = cli.ledger_out.parent / f"{cli.run_label}_ledger.json" if cli.ledger_out == DEFAULT_LEDGER else cli.ledger_out
    
    ledger_out.parent.mkdir(parents=True, exist_ok=True)
    leaderboard_path.parent.mkdir(parents=True, exist_ok=True)

    seeds = [s.strip() for s in cli.seeds.split(",")]
    n_seeds = len(seeds)
    timesteps = int(cli.timesteps)

    console.rule("[bold blue]Fork B · Option 2 — Sparse Episodic RL[/bold blue]")
    console.print(f"  [dim]Ticker:[/dim]       {cli.ticker.upper()}")
    console.print(f"  [dim]Seeds:[/dim]        {cli.seeds}  ({n_seeds} runs)")
    console.print(f"  [dim]Timesteps:[/dim]    {timesteps:,}")
    console.print(f"  [dim]Ent coef:[/dim]     {cli.ent_coef}")
    console.print(f"  [dim]Reward:[/dim]       sparse (end of episode equity vs buy-hold)")
    console.print(f"  [dim]Episode:[/dim]      {cli.max_episode_steps} steps (random start)")
    console.print(f"  [dim]Actions:[/dim]      binary long/flat only (no shorts, no sizing)")
    console.print(f"  [dim]Execution:[/dim]    next_bar | 10bp round-trip cost")
    console.print()

    exp_args = _build_experiment_args(cli)

    total_steps = n_seeds * timesteps
    ledger: dict = {
        "run_id": f"{cli.run_label}-{datetime.now().strftime('%Y%m%d-%H%M%S')}",
        "created_at": _utc_now(),
        "config": {
            "ticker": cli.ticker,
            "seeds": cli.seeds,
            "timesteps": timesteps,
            "ent_coef": cli.ent_coef,
            "reward_mode": "sparse",
            "max_episode_steps": cli.max_episode_steps,
            "random_start": True,
            "binary_actions": True,
            "long_only": True,
        },
    }

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        TimeElapsedColumn(),
        console=console,
        transient=False,
    ) as progress:
        task = progress.add_task(
            f"[cyan]Training {n_seeds} seeds × {timesteps:,} steps[/cyan]",
            total=n_seeds,
        )

        # Monkey-patch the per-run print so we can advance the progress bar
        import src.experiments as exp_module
        _orig_print = print

        completed = [0]

        def _tracking_print(*args, **kwargs):
            _orig_print(*args, **kwargs)
            msg = " ".join(str(a) for a in args)
            if msg.startswith("Run ") and "completed" in msg:
                completed[0] += 1
                progress.advance(task)
                progress.update(task, description=f"[cyan]Seed {completed[0]}/{n_seeds} done[/cyan]")

        import builtins
        builtins.print = _tracking_print
        try:
            leaderboard = run_experiments(exp_args)
        finally:
            builtins.print = _orig_print

        progress.update(task, description="[green]Training complete[/green]")

    console.print()

    _, summary = write_experiment_outputs(
        leaderboard=leaderboard,
        leaderboard_path=leaderboard_path,
        reward_leaderboard_path=reward_lb_path,
        summary_path=summary_path,
        snapshot_dir=snapshot_dir,
        run_label=cli.run_label,
        append_results=cli.append,
    )

    _print_results_table(leaderboard)
    gates = _gate_check(leaderboard)
    _print_gate_table(gates)

    ledger["gates"] = gates
    ledger["completed_at"] = _utc_now()
    ledger["leaderboard_rows"] = len(leaderboard)
    ledger_out.write_text(json.dumps(ledger, indent=2, default=str), encoding="utf-8")

    console.print(f"\n  [dim]Ledger  -> {ledger_out.relative_to(ROOT_DIR)}[/dim]")
    console.print(f"  [dim]Results -> {leaderboard_path.relative_to(ROOT_DIR)}[/dim]")

    return 0 if gates["overall"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
