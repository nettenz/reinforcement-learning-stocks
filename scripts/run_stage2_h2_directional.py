"""
Stage 3 / Option A — Directional Classification on 3-day Returns

Tests whether features have any directional content at all, independent of
return magnitude. Uses an abstain band (±direction_threshold) and a minimum
probability threshold so the model only trades on high-conviction signals.

Gate to pass:
  - Directional accuracy > 55% in 2/3 windows
  - Net return > buy-hold in 2/3 windows
"""
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import os
import sys

# Force UTF-8 on Windows terminals that default to cp1252
os.environ.setdefault("PYTHONUTF8", "1")
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import numpy as np
import pandas as pd
from rich.console import Console
from rich.panel import Panel
from rich.progress import BarColumn, MofNCompleteColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich.table import Table
from rich.text import Text
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, roc_auc_score

ROOT_DIR = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT_DIR / "data" / "tech_training_data_stationary.csv"
ROUND_TRIP_COST = 0.0007  # 7bp
WINDOW_CONFIG = {"train_size": 0.20, "val_size": 0.20, "test_size": 0.20, "slide_pct": 0.33}

console = Console()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------

def _load_data() -> pd.DataFrame:
    if not DATA_PATH.exists():
        raise FileNotFoundError(f"Stationary dataset not found: {DATA_PATH}")
    df = pd.read_csv(DATA_PATH)
    df["Date"] = pd.to_datetime(df["Date"])
    return df.sort_values("Date").reset_index(drop=True)


def _feature_columns(df: pd.DataFrame) -> list[str]:
    excluded = {"Date", "RawClose", "OrigOpen", "OrigHigh", "OrigLow", "OrigClose"}
    return [c for c in df.columns if c not in excluded]


def _forward_return(close: pd.Series, horizon: int) -> pd.Series:
    return np.log(close.shift(-horizon) / close).replace([np.inf, -np.inf], np.nan)


# ---------------------------------------------------------------------------
# Windows
# ---------------------------------------------------------------------------

def _make_windows(df: pd.DataFrame) -> list[dict]:
    n = len(df)
    win = int(n * (WINDOW_CONFIG["train_size"] + WINDOW_CONFIG["val_size"] + WINDOW_CONFIG["test_size"]))
    slide = max(int(win * WINDOW_CONFIG["slide_pct"]), 1)
    windows, start, num = [], 0, 0
    while start + win <= n:
        te = start + win
        tr_end = start + int(win * WINDOW_CONFIG["train_size"])
        va_end = tr_end + int(win * WINDOW_CONFIG["val_size"])
        windows.append({
            "window_num": num,
            "train": df.iloc[start:tr_end].copy().reset_index(drop=True),
            "val": df.iloc[tr_end:va_end].copy().reset_index(drop=True),
            "test": df.iloc[va_end:te].copy().reset_index(drop=True),
        })
        start += slide
        num += 1
    return windows


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

def _get_model(name: str, seed: int):
    if name == "logistic":
        return LogisticRegression(max_iter=2000, random_state=seed, C=1.0)
    if name == "xgboost":
        from xgboost import XGBClassifier
        return XGBClassifier(
            n_estimators=200,
            max_depth=4,
            learning_rate=0.05,
            subsample=0.8,
            colsample_bytree=0.8,
            eval_metric="logloss",
            random_state=seed,
            verbosity=0,
        )
    raise ValueError(f"Unknown model: {name}")


# ---------------------------------------------------------------------------
# Strategy simulation
# ---------------------------------------------------------------------------

def _simulate(proba_up: np.ndarray, next_bar_returns: np.ndarray, prob_threshold: float) -> dict:
    positions = np.where(proba_up >= prob_threshold, 1, 0).astype(float)
    transitions = np.abs(np.diff(np.concatenate(([0.0], positions))))
    net = positions * next_bar_returns - transitions * ROUND_TRIP_COST
    equity = np.cumprod(1.0 + net)
    peak = np.maximum.accumulate(equity)
    dd = (equity - peak) / np.maximum(peak, 1e-12)
    mean_net, std_net = float(np.mean(net)), float(np.std(net, ddof=0))
    return {
        "net_return": float(np.prod(1.0 + net) - 1.0),
        "gross_return": float(np.prod(1.0 + positions * next_bar_returns) - 1.0),
        "net_sharpe": float(np.sqrt(252) * mean_net / std_net) if std_net > 1e-12 else 0.0,
        "max_drawdown": float(np.min(dd)),
        "trade_count": int(np.sum(transitions > 0)),
        "active_days": int(np.sum(positions > 0)),
    }


def _buyhold(next_bar_returns: np.ndarray) -> dict:
    net = next_bar_returns.copy().astype(float)
    net[0] -= ROUND_TRIP_COST
    equity = np.cumprod(1.0 + net)
    peak = np.maximum.accumulate(equity)
    dd = (equity - peak) / np.maximum(peak, 1e-12)
    mean_net, std_net = float(np.mean(net)), float(np.std(net, ddof=0))
    return {
        "net_return": float(np.prod(1.0 + net) - 1.0),
        "net_sharpe": float(np.sqrt(252) * mean_net / std_net) if std_net > 1e-12 else 0.0,
        "max_drawdown": float(np.min(dd)),
    }


# ---------------------------------------------------------------------------
# Per-window evaluation
# ---------------------------------------------------------------------------

@dataclass
class WindowResult:
    window_num: int
    test_period: str
    model_name: str
    directional_accuracy: float
    auc: float
    active_rate: float
    model: dict
    buyhold: dict
    beats_buyhold: bool
    accuracy_gate: bool
    window_pass: bool
    n_test: int


def _eval_window(
    window: dict,
    feature_cols: list[str],
    horizon: int,
    direction_threshold: float,
    prob_threshold: float,
    model_name: str,
    seed: int,
) -> WindowResult:
    train, val, test = window["train"], window["val"], window["test"]

    def _prep(split: pd.DataFrame):
        s = split.copy()
        fwd = _forward_return(pd.to_numeric(s["RawClose"], errors="coerce"), horizon)
        s["fwd_ret"] = fwd
        s["label"] = np.where(s["fwd_ret"] > direction_threshold, 1,
                     np.where(s["fwd_ret"] < -direction_threshold, 0, np.nan))
        s = s.dropna(subset=feature_cols + ["label", "fwd_ret"])
        X = s[feature_cols].replace([np.inf, -np.inf], np.nan).dropna(axis=0)
        s = s.loc[X.index]
        return s, X.to_numpy(dtype=float), s["label"].to_numpy(dtype=int)

    _, X_tr, y_tr = _prep(train)
    _, X_va, y_va = _prep(val)
    test_df, X_te, y_te = _prep(test)

    if len(X_tr) < 10 or len(X_te) < 5:
        raise ValueError(f"Window {window['window_num']}: insufficient samples after filtering")

    mdl = _get_model(model_name, seed)
    mdl.fit(X_tr, y_tr)

    proba_up_te = mdl.predict_proba(X_te)[:, 1]
    dir_acc = float(accuracy_score(y_te, (proba_up_te >= 0.5).astype(int)))
    try:
        auc = float(roc_auc_score(y_te, proba_up_te)) if len(np.unique(y_te)) > 1 else 0.5
    except Exception:
        auc = 0.5

    # Simulate on full test slice with next-bar returns
    test_full = test.copy()
    test_full["fwd_ret"] = _forward_return(pd.to_numeric(test_full["RawClose"], errors="coerce"), horizon)
    test_full = test_full.dropna(subset=feature_cols + ["fwd_ret"])
    X_full = test_full[feature_cols].replace([np.inf, -np.inf], np.nan).dropna(axis=0)
    test_full = test_full.loc[X_full.index]

    proba_full = mdl.predict_proba(X_full.to_numpy(dtype=float))[:, 1]
    next_returns = np.expm1(test_full["LogReturn"].shift(-1).iloc[:-1].to_numpy(dtype=float))
    proba_sim = proba_full[:-1]

    model_perf = _simulate(proba_sim, next_returns, prob_threshold)
    bh_perf = _buyhold(next_returns)

    return WindowResult(
        window_num=window["window_num"],
        test_period=f"{test['Date'].min().date()} to {test['Date'].max().date()}",
        model_name=model_name,
        directional_accuracy=dir_acc,
        auc=auc,
        active_rate=float(model_perf["active_days"] / max(len(proba_sim), 1)),
        model=model_perf,
        buyhold=bh_perf,
        beats_buyhold=model_perf["net_return"] > bh_perf["net_return"],
        accuracy_gate=dir_acc > 0.55,
        window_pass=(dir_acc > 0.55) and (model_perf["net_return"] > bh_perf["net_return"]),
        n_test=len(y_te),
    )


# ---------------------------------------------------------------------------
# Gate evaluation
# ---------------------------------------------------------------------------

def _evaluate_gates(results: list[WindowResult]) -> dict:
    n = len(results)
    threshold = max(2, int(np.ceil(n * 2 / 3)))
    bh_passes = sum(1 for r in results if r.beats_buyhold)
    acc_passes = sum(1 for r in results if r.accuracy_gate)
    g1 = bh_passes >= threshold
    g2 = acc_passes >= threshold
    return {
        "n_windows": n,
        "threshold_windows": threshold,
        "g1_beat_buyhold": {"passes": bh_passes, "required": threshold, "result": "PASS" if g1 else "FAIL"},
        "g2_directional_accuracy_55pct": {"passes": acc_passes, "required": threshold, "result": "PASS" if g2 else "FAIL"},
        "window_passes": sum(1 for r in results if r.window_pass),
        "mean_directional_accuracy": float(np.mean([r.directional_accuracy for r in results])),
        "mean_net_return": float(np.mean([r.model["net_return"] for r in results])),
        "mean_buyhold_return": float(np.mean([r.buyhold["net_return"] for r in results])),
        "mean_net_sharpe": float(np.mean([r.model["net_sharpe"] for r in results])),
        "recent_window_pass": results[-1].window_pass if results else False,
        "overall_verdict": "PASS" if (g1 and g2) else "KILL",
    }


# ---------------------------------------------------------------------------
# Rich display helpers
# ---------------------------------------------------------------------------

def _print_window_table(results: list[WindowResult], model_name: str) -> None:
    tbl = Table(title=f"[bold]{model_name}[/bold] — Window Results", show_lines=True)
    tbl.add_column("Win", justify="center", style="dim")
    tbl.add_column("Test Period", style="cyan")
    tbl.add_column("Dir Acc", justify="right")
    tbl.add_column("AUC", justify="right")
    tbl.add_column("Net Ret", justify="right")
    tbl.add_column("Buy-Hold", justify="right")
    tbl.add_column("Gap", justify="right")
    tbl.add_column("Sharpe", justify="right")
    tbl.add_column("Active%", justify="right")
    tbl.add_column("n", justify="right")
    tbl.add_column("Pass?", justify="center")

    for r in results:
        gap = r.model["net_return"] - r.buyhold["net_return"]
        acc_color = "green" if r.accuracy_gate else "red"
        gap_color = "green" if gap > 0 else "red"
        pass_icon = "[green]PASS[/green]" if r.window_pass else "[red]fail[/red]"
        tbl.add_row(
            str(r.window_num),
            r.test_period,
            f"[{acc_color}]{r.directional_accuracy:.3f}[/{acc_color}]",
            f"{r.auc:.3f}",
            f"{r.model['net_return']:+.4f}",
            f"{r.buyhold['net_return']:+.4f}",
            f"[{gap_color}]{gap:+.4f}[/{gap_color}]",
            f"{r.model['net_sharpe']:+.2f}",
            f"{r.active_rate:.1%}",
            str(r.n_test),
            pass_icon,
        )
    console.print(tbl)


def _print_gate_summary(gates: dict, model_name: str) -> None:
    verdict = gates["overall_verdict"]
    color = "green" if verdict == "PASS" else "red"

    tbl = Table(title=f"[bold]{model_name}[/bold] — Gate Summary", show_lines=False)
    tbl.add_column("Gate", style="bold")
    tbl.add_column("Result", justify="center")
    tbl.add_column("Detail")

    g1 = gates["g1_beat_buyhold"]
    g2 = gates["g2_directional_accuracy_55pct"]
    tbl.add_row(
        "G1  Beat buy-hold (2/3 windows)",
        f"[{'green' if g1['result'] == 'PASS' else 'red'}]{g1['result']}[/]",
        f"{g1['passes']}/{gates['n_windows']} windows"
    )
    tbl.add_row(
        "G2  Dir accuracy >55% (2/3 windows)",
        f"[{'green' if g2['result'] == 'PASS' else 'red'}]{g2['result']}[/]",
        f"{g2['passes']}/{gates['n_windows']} windows  (mean {gates['mean_directional_accuracy']:.3f})"
    )
    tbl.add_row("Mean net return", "", f"{gates['mean_net_return']:+.4f}  vs buy-hold {gates['mean_buyhold_return']:+.4f}")
    tbl.add_row("Mean Sharpe", "", f"{gates['mean_net_sharpe']:+.2f}")
    tbl.add_row("Recent window", "", "[green]pass[/green]" if gates["recent_window_pass"] else "[red]fail[/red]")
    console.print(tbl)
    console.print(Panel(f"[{color}][bold]VERDICT: {verdict}[/bold][/{color}]", expand=False))


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Stage 3 Option A — directional classification on N-day returns")
    p.add_argument("--target-horizon", type=int, default=3)
    p.add_argument("--direction-threshold", type=float, default=0.005)
    p.add_argument("--trade-prob-threshold", type=float, default=0.60)
    p.add_argument("--models", nargs="+", default=["logistic", "xgboost"])
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--output-dir", type=Path, default=ROOT_DIR / "results" / "stage3_h2_directional")
    p.add_argument("--ledger-out", type=Path, default=ROOT_DIR / "logs" / "stage3_h2_directional_ledger.json")
    return p.parse_args()


def main() -> int:
    args = _parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    args.ledger_out.parent.mkdir(parents=True, exist_ok=True)

    console.rule("[bold blue]Stage 3 · Option A — Directional Classification (3-day horizon)[/bold blue]")

    with console.status("[cyan]Loading data...[/cyan]"):
        df = _load_data()
        feature_cols = _feature_columns(df)
        windows = _make_windows(df)

    console.print(f"  [dim]Rows:[/dim] {len(df)}  [dim]Features:[/dim] {len(feature_cols)}  "
                  f"[dim]Windows:[/dim] {len(windows)}  "
                  f"[dim]Date range:[/dim] {df['Date'].min().date()} to {df['Date'].max().date()}")
    console.print(f"  [dim]Horizon:[/dim] {args.target_horizon}d  "
                  f"[dim]Abstain band:[/dim] +/-{args.direction_threshold:.1%}  "
                  f"[dim]Prob threshold:[/dim] {args.trade_prob_threshold:.0%}  "
                  f"[dim]Cost:[/dim] {ROUND_TRIP_COST * 10000:.0f}bp round-trip")
    console.print()

    ledger: dict = {
        "run_id": f"stage3-h2-directional-{datetime.now().strftime('%Y%m%d-%H%M%S')}",
        "created_at": _utc_now(),
        "config": {
            "target_horizon": args.target_horizon,
            "direction_threshold": args.direction_threshold,
            "trade_prob_threshold": args.trade_prob_threshold,
            "models": args.models,
            "seed": args.seed,
            "window_config": WINDOW_CONFIG,
            "round_trip_cost_bps": ROUND_TRIP_COST * 10000,
        },
        "models": {},
    }

    all_pass = False
    total_tasks = len(args.models) * len(windows)

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        TimeElapsedColumn(),
        console=console,
        transient=False,
    ) as progress:
        overall = progress.add_task("[cyan]Overall progress[/cyan]", total=total_tasks)

        for model_name in args.models:
            model_task = progress.add_task(f"[yellow]{model_name}[/yellow]", total=len(windows))
            results: list[WindowResult] = []

            for w in windows:
                progress.update(model_task, description=f"[yellow]{model_name}[/yellow]  W{w['window_num']}")
                try:
                    r = _eval_window(
                        window=w,
                        feature_cols=feature_cols,
                        horizon=args.target_horizon,
                        direction_threshold=args.direction_threshold,
                        prob_threshold=args.trade_prob_threshold,
                        model_name=model_name,
                        seed=args.seed,
                    )
                    results.append(r)
                except Exception as exc:
                    console.print(f"  [red]W{w['window_num']} ERROR:[/red] {exc}")
                finally:
                    progress.advance(model_task)
                    progress.advance(overall)

            progress.update(model_task, description=f"[green]{model_name} ✓[/green]")

            if not results:
                console.print(f"[red]No valid windows for {model_name}[/red]")
                continue

            console.print()
            _print_window_table(results, model_name)
            gates = _evaluate_gates(results)
            _print_gate_summary(gates, model_name)
            console.print()

            if gates["overall_verdict"] == "PASS":
                all_pass = True

            ledger["models"][model_name] = {
                "gates": gates,
                "windows": [
                    {
                        "window_num": r.window_num,
                        "test_period": r.test_period,
                        "directional_accuracy": r.directional_accuracy,
                        "auc": r.auc,
                        "active_rate": r.active_rate,
                        "n_labeled_test": r.n_test,
                        "model": r.model,
                        "buyhold": r.buyhold,
                        "beats_buyhold": r.beats_buyhold,
                        "accuracy_gate": r.accuracy_gate,
                        "window_pass": r.window_pass,
                    }
                    for r in results
                ],
            }

    decision = (
        "STAGE3_SUPERVISED_BASELINE_CONFIRMED — RL escalation unlocked"
        if all_pass
        else "KILL — features have no durable directional content at 3d horizon. Confirm exit."
    )
    ledger["final_decision"] = decision
    ledger["completed_at"] = _utc_now()
    args.ledger_out.write_text(json.dumps(ledger, indent=2), encoding="utf-8")

    final_color = "green" if all_pass else "red"
    console.rule()
    console.print(Panel(
        f"[{final_color}][bold]{decision}[/bold][/{final_color}]\n\n"
        f"[dim]Ledger → {args.ledger_out.relative_to(ROOT_DIR)}[/dim]",
        title="[bold]Stage 3 Option A — Final Decision[/bold]",
        expand=False,
    ))

    return 0 if all_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
