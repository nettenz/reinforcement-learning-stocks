#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Iterable

import pandas as pd

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table

    HAS_RICH = True
except Exception:
    HAS_RICH = False

ROOT = Path(__file__).resolve().parent
LOGS_DIR = ROOT / "logs"
DATA_DIR = ROOT / "data"
SNAPSHOT_DIR = DATA_DIR / "experiment_snapshots"
LEADERBOARD_PATH = DATA_DIR / "experiment_leaderboard.csv"
SUPPORTED_TICKERS = ("aapl", "nvda", "amd")

NUMERIC_COLUMNS = [
    "seed",
    "timesteps",
    "learning_rate",
    "gamma",
    "ent_coef",
    "threshold",
    "horizon",
    "transaction_cost_rate",
    "trade_penalty",
    "reward_action_bonus_scale",
    "reward_turnover_penalty_scale",
    "test_trade_count",
    "test_trade_win_rate",
    "test_actionable_accuracy",
    "ranking_score",
]

TEXT_COLUMNS = [
    "ticker",
    "run_label",
    "execution_mode",
    "reward_mode",
    "model_path",
]


class RunLogger:
    def __init__(self, log_path: Path) -> None:
        self.log_path = log_path
        self._fh = log_path.open("a", encoding="utf-8", newline="\n")

    def close(self) -> None:
        self._fh.close()

    def log(self, message: str = "") -> None:
        if message:
            line = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {message}"
        else:
            line = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}]"
        print(line)
        self._fh.write(line + "\n")
        self._fh.flush()

    def write_raw(self, line: str) -> None:
        print(line, end="")
        self._fh.write(line)
        self._fh.flush()


def find_python_executable() -> Path:
    candidates = [
        ROOT / ".venv" / "Scripts" / "python.exe",
        ROOT / ".venv" / "bin" / "python3",
        ROOT / ".venv" / "bin" / "python",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return Path(sys.executable)


def sanitize_frame(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out.columns = [str(c).strip() for c in out.columns]
    out = out.loc[:, ~out.columns.duplicated()]

    for col in TEXT_COLUMNS:
        if col not in out.columns:
            out[col] = ""
        out[col] = out[col].astype("string").fillna("").str.strip()

    if "ticker" in out.columns:
        out["ticker"] = out["ticker"].str.upper()

    for col in NUMERIC_COLUMNS:
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce")

    return out


def consolidate_snapshots(logger: RunLogger) -> None:
    logger.log("")
    logger.log("========== STEP 1: CONSOLIDATE VALIDATION SNAPSHOTS ==========")
    logger.log("Running consolidation...")

    frames: list[pd.DataFrame] = []

    if LEADERBOARD_PATH.exists():
        try:
            main_df = pd.read_csv(LEADERBOARD_PATH, low_memory=False)
            main_df = sanitize_frame(main_df)
            logger.log(f"Main leaderboard: {len(main_df)} rows")
            frames.append(main_df)
        except Exception as exc:
            logger.log(f"WARNING: Could not read main leaderboard: {exc}")
    else:
        logger.log("Main leaderboard missing; a new one will be created")

    snapshot_files = sorted(SNAPSHOT_DIR.glob("experiment_leaderboard_*validation*.csv"))
    logger.log(f"Found {len(snapshot_files)} validation snapshot files")

    for snap_file in snapshot_files:
        try:
            snap_df = pd.read_csv(snap_file, low_memory=False)
            snap_df = sanitize_frame(snap_df)
            frames.append(snap_df)
            logger.log(f"  Added {snap_file.name}: {len(snap_df)} rows")
        except Exception as exc:
            logger.log(f"  Skipped {snap_file.name}: {exc}")

    if not frames:
        consolidated = pd.DataFrame(columns=["ticker", "run_label", "ranking_score"])
    else:
        consolidated = pd.concat(frames, ignore_index=True, sort=False)
        consolidated = sanitize_frame(consolidated)

    if "model_path" in consolidated.columns:
        model_mask = consolidated["model_path"].astype(str).str.strip() != ""
        deduped_models = consolidated[model_mask].drop_duplicates(subset=["model_path"], keep="last")
        consolidated = pd.concat([consolidated[~model_mask], deduped_models], ignore_index=True, sort=False)

    if "ranking_score" in consolidated.columns:
        consolidated = consolidated.sort_values("ranking_score", ascending=False, na_position="last").reset_index(drop=True)

    LEADERBOARD_PATH.parent.mkdir(parents=True, exist_ok=True)
    consolidated.to_csv(LEADERBOARD_PATH, index=False)

    tickers = sorted({t for t in consolidated.get("ticker", pd.Series(dtype="string")).dropna().astype(str) if t.strip()})
    logger.log(f"Consolidated: {len(consolidated)} total rows in {LEADERBOARD_PATH.relative_to(ROOT)}")
    logger.log(f"Tickers present: {tickers}")
    logger.log("Step 1 complete.")


def run_command(cmd: list[str], logger: RunLogger) -> int:
    proc = subprocess.Popen(
        cmd,
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    assert proc.stdout is not None
    for line in proc.stdout:
        logger.write_raw(line)
    return proc.wait()


def diagnostic_runs(python_exec: Path) -> Iterable[tuple[str, list[str]]]:
    base = [
        str(python_exec),
        "src/experiments.py",
        "--compact-output",
        "--include-news",
        "--use-stationary-features",
        "--seeds",
        "7",
        "--timesteps",
        "5000",
        "--learning-rates",
        "0.0003",
        "--gammas",
        "0.99",
        "--threshold",
        "0.002",
        "--horizon",
        "1",
        "--transaction-cost-rate",
        "0.001",
        "--execution-mode",
        "next_bar",
        "--reward-mode",
        "sharpe",
        "--max-runs",
        "1",
        "--append",
    ]

    step = 2
    for ticker in SUPPORTED_TICKERS:
        ticker_upper = ticker.upper()
        yield (
            f"STEP {step}: {ticker_upper} DIAGNOSTIC 1 - BALANCED",
            base
            + [
                "--ticker",
                ticker,
                "--ent-coefs",
                "0.05",
                "--trade-penalty",
                "0.05",
                "--reward-action-bonus-scale",
                "0.02",
                "--reward-turnover-penalty-scale",
                "0.05",
                "--run-label",
                f"{ticker}-diagnostic-1-balanced",
            ],
        )
        step += 1

        yield (
            f"STEP {step}: {ticker_upper} DIAGNOSTIC 2 - CONSERVATIVE",
            base
            + [
                "--ticker",
                ticker,
                "--ent-coefs",
                "0.05",
                "--trade-penalty",
                "0.08",
                "--reward-action-bonus-scale",
                "0.00",
                "--reward-turnover-penalty-scale",
                "0.10",
                "--reward-drawdown-penalty-scale",
                "0.15",
                "--run-label",
                f"{ticker}-diagnostic-2-conservative",
            ],
        )
        step += 1

        yield (
            f"STEP {step}: {ticker_upper} DIAGNOSTIC 3 - AGGRESSIVE",
            base
            + [
                "--ticker",
                ticker,
                "--ent-coefs",
                "0.10",
                "--trade-penalty",
                "0.03",
                "--reward-action-bonus-scale",
                "0.08",
                "--reward-turnover-penalty-scale",
                "0.02",
                "--run-label",
                f"{ticker}-diagnostic-3-aggressive",
            ],
        )
        step += 1


def safe_percent(value: float | int | None) -> str:
    try:
        return f"{float(value):.2%}"
    except Exception:
        return "N/A"


def analyze_results(logger: RunLogger) -> None:
    logger.log("")
    logger.log("========== STEP 5: CHECK RESULTS ==========")
    logger.log("Analyzing diagnostic results...")

    if not LEADERBOARD_PATH.exists():
        logger.log("No leaderboard found; skipping analysis")
        return

    try:
        df = sanitize_frame(pd.read_csv(LEADERBOARD_PATH, low_memory=False))
    except Exception as exc:
        logger.log(f"Failed to read leaderboard for analysis: {exc}")
        return

    if "run_label" not in df.columns:
        df["run_label"] = ""
    if "model_path" not in df.columns:
        df["model_path"] = ""

    run_label_mask = df["run_label"].astype(str).str.contains("diagnostic", case=False, na=False)
    model_path_mask = df["model_path"].astype(str).str.contains("diagnostic", case=False, na=False)
    diag = df[run_label_mask | model_path_mask].copy()

    if "run_label" in diag.columns and "model_path" in diag.columns:
        missing_label = diag["run_label"].astype(str).str.strip() == ""
        diag.loc[missing_label, "run_label"] = (
            diag.loc[missing_label, "model_path"]
            .astype(str)
            .str.extract(r"(diagnostic-[^_\\/.]+)", expand=False)
            .fillna("diagnostic-legacy")
        )

    if diag.empty:
        # Fallback to recent rows from currently supported tickers.
        ticker_series = df.get("ticker", pd.Series(["" for _ in range(len(df))]))
        diag = df[ticker_series.astype(str).str.upper().isin([t.upper() for t in SUPPORTED_TICKERS])].tail(20).copy()

    if diag.empty:
        logger.log("No diagnostic runs found yet")
        return

    diag["ranking_score"] = pd.to_numeric(diag.get("ranking_score", 0), errors="coerce")
    diag = diag.sort_values("ranking_score", ascending=False, na_position="last").reset_index(drop=True)

    result_cols = [
        "run_label",
        "ticker",
        "seed",
        "execution_mode",
        "trade_penalty",
        "reward_action_bonus_scale",
        "reward_turnover_penalty_scale",
        "test_trade_count",
        "test_trade_win_rate",
        "test_actionable_accuracy",
        "ranking_score",
    ]
    available = [c for c in result_cols if c in diag.columns]
    display = diag[available].copy()
    rename_map = {
        "run_label": "Config",
        "ticker": "Ticker",
        "seed": "Seed",
        "execution_mode": "Execution",
        "trade_penalty": "Trade Penalty",
        "reward_action_bonus_scale": "Action Bonus",
        "reward_turnover_penalty_scale": "Turnover Pen",
        "test_trade_count": "Trades",
        "test_trade_win_rate": "Win Rate",
        "test_actionable_accuracy": "Accuracy",
        "ranking_score": "Score",
    }
    display = display.rename(columns=rename_map)

    if "Win Rate" in display.columns:
        display["Win Rate"] = display["Win Rate"].map(safe_percent)
    if "Accuracy" in display.columns:
        display["Accuracy"] = display["Accuracy"].map(safe_percent)
    if "Score" in display.columns:
        display["Score"] = pd.to_numeric(display["Score"], errors="coerce").map(
            lambda x: f"{x:.6f}" if pd.notna(x) else "N/A"
        )

    print()
    if HAS_RICH:
        console = Console()
        console.print(Panel("DIAGNOSTIC RESULTS", border_style="cyan", title="Summary"))
        table = Table(show_header=True, header_style="bold magenta")
        for col in display.columns:
            justify = "right" if col in {"Seed", "Trade Penalty", "Action Bonus", "Turnover Pen", "Trades", "Score"} else "left"
            table.add_column(col, justify=justify)
        for _, row in display.iterrows():
            table.add_row(*[str(row[c]) for c in display.columns])
        console.print(table)
    else:
        print("DIAGNOSTIC RESULTS")
        print(display.to_string(index=False))

    winner = diag.iloc[0]
    winner_label = str(winner.get("run_label", "(unknown)"))
    logger.log(f"Best config: {winner_label}")
    logger.log(f"  Score: {float(winner.get('ranking_score', 0.0)):.6f}")
    logger.log(f"  Trade penalty: {winner.get('trade_penalty', 'N/A')}")
    logger.log(f"  Action bonus: {winner.get('reward_action_bonus_scale', 'N/A')}")
    logger.log(f"  Turnover penalty: {winner.get('reward_turnover_penalty_scale', 'N/A')}")
    logger.log(f"  Trades: {int(float(winner.get('test_trade_count', 0) or 0))}")
    logger.log(f"  Accuracy: {safe_percent(winner.get('test_actionable_accuracy', 0))}")


def run_all(continue_on_error: bool) -> int:
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    log_path = LOGS_DIR / f"diagnostic_run_{timestamp}.log"
    logger = RunLogger(log_path)

    exit_code = 0
    try:
        logger.log("=== DIAGNOSTIC RUN STARTED ===")
        logger.log(f"Log file: {log_path}")
        logger.log(f"Working directory: {ROOT}")

        python_exec = find_python_executable()
        logger.log(f"Python executable: {python_exec}")

        consolidate_snapshots(logger)

        for step_name, command in diagnostic_runs(python_exec):
            logger.log("")
            logger.log(f"========== {step_name} ==========")
            logger.log(f"Starting {step_name.lower()}...")
            rc = run_command(command, logger)
            if rc != 0:
                logger.log(f"ERROR: Step failed with exit code {rc}")
                exit_code = rc
                if not continue_on_error:
                    break
            else:
                logger.log("Step complete.")

        analyze_results(logger)

        logger.log("")
        logger.log("=== DIAGNOSTIC RUN COMPLETE ===")
        logger.log(f"Results saved to: {log_path}")
    finally:
        logger.close()

    return exit_code


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Robust diagnostic runner with sanitized outputs")
    parser.add_argument(
        "--continue-on-error",
        action="store_true",
        help="Continue remaining steps if one diagnostic command fails",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    code = run_all(continue_on_error=args.continue_on_error)
    raise SystemExit(code)


if __name__ == "__main__":
    main()
