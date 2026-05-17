from __future__ import annotations

import re
import json
from datetime import datetime, timezone
from pathlib import Path
import pandas as pd
import numpy as np
import streamlit as st

from src.dashboard.config import (
    ROOT_DIR,
    STAGE1_RESULTS_DIR,
    STAGE1_CONFIRMATION_DIR,
    STAGE1_PIVOT_REPORT_PATH,
)
from src.dashboard.model_utils import (
    _latest_comparable_leaderboard,
    _ticker_match_mask,
)
from src.market_data import TICKER_PRESETS


def _parse_snapshot_timestamp(path: Path) -> datetime:
    match = re.search(r"(\d{8}-\d{6}Z?)", path.stem)
    if match:
        raw = match.group(1)
        parsed_with_zone = pd.to_datetime(raw, format="%Y%m%d-%H%M%SZ", utc=True, errors="coerce")
        if pd.notna(parsed_with_zone):
            return parsed_with_zone.to_pydatetime()
        parsed_without_zone = pd.to_datetime(raw, format="%Y%m%d-%H%M%S", utc=True, errors="coerce")
        if pd.notna(parsed_without_zone):
            return parsed_without_zone.to_pydatetime()
    try:
        return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
    except OSError:
        return datetime.now(timezone.utc)


def _extract_snapshot_label(path: Path) -> str:
    """Helper to extract a clean snapshot theme/run label from the filename."""
    name = path.stem
    if name.startswith("leaderboard_"):
        name = name[len("leaderboard_"):]
    # Strip interval suffixes like _daily, _intraday_5m
    name = name.replace("daily_", "").replace("intraday_5m_", "").replace("_daily", "").replace("_intraday_5m", "")
    # Remove timestamps like _20260516-225000Z
    name = re.sub(r"[_\-]\d{8}-\d{6}Z?", "", name)
    name = re.sub(r"\d{8}-\d{6}Z?[_\-]", "", name)
    return name.strip("_ -") or "baseline"


def _format_float(val: float) -> str:
    """Safely formats float values to clean CLI-compatible representations."""
    if abs(val) < 1e-4 and val != 0.0:
        return f"{val:.8f}".rstrip("0").rstrip(".")
    # Avoid trailing dot on whole numbers
    s = str(val)
    if s.endswith(".0"):
        return s[:-2]
    return s


def _make_command_from_config(
    config: dict[str, float | int | bool | str],
    seeds: str,
    run_label: str,
    ticker: str = "nvda",
) -> str:
    seed_count = max(1, len([s for s in seeds.split(",") if s.strip()]))
    include_news_flag = "--include-news" if bool(config.get("include_news", True)) else ""
    stationary_flag = "--use-stationary-features" if bool(config.get("use_stationary_features", True)) else ""
    ignore_cost_flag = (
        "--reward-ignore-transaction-cost"
        if bool(config.get("reward_ignore_transaction_cost", True))
        else "--no-reward-ignore-transaction-cost"
    )
    
    parts = [
        "python src/experiments.py",
        f"--ticker {ticker}",
        f"{include_news_flag}",
        f"{stationary_flag}",
        f"--seeds {seeds}",
        f"--timesteps {int(config.get('timesteps', 50000))}",
        f"--learning-rates {_format_float(float(config.get('learning_rate', 0.0003)))}",
        f"--gammas {_format_float(float(config.get('gamma', 0.99)))}",
        f"--ent-coefs {_format_float(float(config.get('ent_coef', 0.05)))}",
        f"--threshold {_format_float(float(config.get('threshold', 0.002)))}",
        f"--horizon {int(config.get('horizon', 1))}",
        f"--transaction-cost-rate {_format_float(float(config.get('transaction_cost_rate', 0.001)))}",
        f"--trade-penalty {_format_float(float(config.get('trade_penalty', 0.05)))}",
        f"--execution-mode {str(config.get('execution_mode', 'next_bar'))}",
        f"--spread-bps {_format_float(float(config.get('spread_bps', 0.0)))}",
        f"--slippage-bps {_format_float(float(config.get('slippage_bps', 0.0)))}",
        f"--max-weight-delta-per-step {_format_float(float(config.get('max_weight_delta_per_step', 0.0)))}",
        f"--reward-mode {str(config.get('reward_mode', 'sharpe'))}",
        f"--rolling-reward-window {int(config.get('rolling_reward_window', 100))}",
        f"--reward-epsilon {_format_float(float(config.get('reward_epsilon', 1e-6)))}",
        f"--reward-return-scale {_format_float(float(config.get('reward_return_scale', 1.0)))}",
        f"--reward-direction-scale {_format_float(float(config.get('reward_direction_scale', 0.40)))}",
        f"--reward-hold-penalty-scale {_format_float(float(config.get('reward_hold_penalty_scale', 0.05)))}",
        f"--reward-drawdown-penalty-scale {_format_float(float(config.get('reward_drawdown_penalty_scale', 0.10)))}",
        f"--reward-pnl-scale {_format_float(float(config.get('reward_pnl_scale', 0.0)))}",
        f"--reward-action-bonus-scale {_format_float(float(config.get('reward_action_bonus_scale', 0.02)))}",
        f"--reward-turnover-penalty-scale {_format_float(float(config.get('reward_turnover_penalty_scale', 0.05)))}",
        f"--reward-clip {_format_float(float(config.get('reward_clip', 1.0)))}",
        f"{ignore_cost_flag}",
        "--append",
        f"--max-runs {seed_count}",
        f"--run-label {run_label}",
        "--n-envs 1",  # CRITICAL FD leak bypass for Windows parallel environments
    ]
    
    if config.get("binary_actions"):
        parts.append("--binary-actions")
    if int(config.get("min_hold_bars", 0)) > 0:
        parts.append(f"--min-hold-bars {config['min_hold_bars']}")
        
    return " ".join(parts)


def _detect_leaderboard_tickers(leaderboard_path: str) -> set[str]:
    """Detect supported ticker preset keys present in the leaderboard."""
    if not Path(leaderboard_path).exists():
        return set()
    try:
        df = pd.read_csv(leaderboard_path)
        if "ticker" in df.columns:
            symbol_to_key = {
                str(symbols[0]).upper(): key
                for key, symbols in TICKER_PRESETS.items()
                if symbols
            }
            supported_keys = set(TICKER_PRESETS.keys())
            detected: set[str] = set()
            for raw in df["ticker"].dropna().unique():
                text = str(raw).strip()
                if not text:
                    continue
                key_candidate = text.lower()
                symbol_candidate = text.upper()
                if key_candidate in supported_keys:
                    detected.add(key_candidate)
                    continue
                mapped = symbol_to_key.get(symbol_candidate)
                if mapped is not None:
                    detected.add(mapped)
            return detected
    except Exception:
        pass
    return set()


@st.cache_data(show_spinner=False)
def load_experiment_history(snapshot_dir: str, leaderboard_path: str, cache_buster: str = "") -> pd.DataFrame:
    _ = cache_buster
    snapshot_root = Path(snapshot_dir)
    current_leaderboard_path = Path(leaderboard_path)
    files: list[Path] = []

    if snapshot_root.exists():
        files.extend(sorted(snapshot_root.glob("*leaderboard*.csv")))
    if current_leaderboard_path.exists():
        files.append(current_leaderboard_path)

    seen: set[Path] = set()
    rows: list[pd.DataFrame] = []
    for file_path in files:
        if "reward" in file_path.name.lower():
            continue
        resolved = file_path.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)

        try:
            run_df = pd.read_csv(file_path)
        except Exception:
            continue
        if run_df.empty:
            continue
        if "ranking_score" in run_df.columns:
            run_df = run_df.sort_values("ranking_score", ascending=False).reset_index(drop=True)

        snapshot_time = _parse_snapshot_timestamp(file_path)
        run_df["snapshot_id"] = file_path.name
        run_df["snapshot_time"] = snapshot_time
        run_df["snapshot_label"] = _extract_snapshot_label(file_path)
        run_df["source_path"] = str(file_path)
        run_df["row_rank"] = range(1, len(run_df) + 1)
        rows.append(run_df)

    if not rows:
        return pd.DataFrame()

    history = pd.concat(rows, ignore_index=True, sort=False)
    history["snapshot_time"] = pd.to_datetime(history["snapshot_time"], utc=True, errors="coerce")
    history = history.sort_values(["snapshot_time", "row_rank"], ascending=[True, True]).reset_index(drop=True)
    return history


def build_history_cache_buster(snapshot_dir: str, leaderboard_path: str) -> str:
    snapshot_root = Path(snapshot_dir)
    leaderboard_file = Path(leaderboard_path)
    files: list[Path] = []

    if snapshot_root.exists():
        files.extend(sorted(snapshot_root.glob("*leaderboard*.csv")))
    if leaderboard_file.exists():
        files.append(leaderboard_file)

    fingerprints: list[str] = []
    seen: set[Path] = set()
    for file_path in files:
        if "reward" in file_path.name.lower():
            continue
        resolved = file_path.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        try:
            stat = file_path.stat()
        except OSError:
            continue
        fingerprints.append(f"{resolved}:{int(stat.st_mtime_ns)}:{stat.st_size}")
    return "|".join(fingerprints)


def build_stage1_cache_buster() -> str:
    files: list[Path] = []
    for root in [STAGE1_RESULTS_DIR, STAGE1_CONFIRMATION_DIR]:
        if not root.exists():
            continue
        files.extend(sorted(root.glob("stage1_baseline_*.json")))

    fingerprints: list[str] = []
    seen: set[Path] = set()
    for file_path in files:
        resolved = file_path.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        try:
            stat = file_path.stat()
        except OSError:
            continue
        fingerprints.append(f"{resolved}:{int(stat.st_mtime_ns)}:{stat.st_size}")
    return "|".join(fingerprints)


@st.cache_data(show_spinner=False)
def load_stage1_snapshot_history(results_dir: str, confirmation_dir: str, cache_buster: str = "") -> pd.DataFrame:
    _ = cache_buster
    files: list[Path] = []
    for directory in [Path(results_dir), Path(confirmation_dir)]:
        if directory.exists():
            files.extend(sorted(directory.glob("stage1_baseline_*.json")))

    seen: set[Path] = set()
    rows: list[dict[str, object]] = []
    for file_path in files:
        resolved = file_path.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        try:
            payload = json.loads(file_path.read_text(encoding="utf-8"))
        except Exception:
            continue

        row = dict(payload)
        row["source_path"] = str(file_path)
        row["source_family"] = "confirmation" if "stage1_confirmation_3seed" in file_path.as_posix() else "stage1"
        row["snapshot_time"] = pd.to_datetime(row.get("timestamp"), utc=True, errors="coerce")
        row["ticker"] = str(row.get("ticker", "")).upper()
        row["model_type"] = str(row.get("model_type", "")).lower()
        row["horizon"] = int(row.get("horizon", 0) or 0)
        row["val_test_r2_gap"] = float(row.get("test_r2", np.nan)) - float(row.get("val_r2", np.nan))
        row["val_test_mae_gap"] = float(row.get("test_mae", np.nan)) - float(row.get("val_mae", np.nan))
        rows.append(row)

    if not rows:
        return pd.DataFrame()

    history = pd.DataFrame(rows)
    if "snapshot_time" in history.columns:
        history["snapshot_time"] = pd.to_datetime(history["snapshot_time"], utc=True, errors="coerce")
    sort_cols = [c for c in ["ticker", "horizon", "model_type", "test_r2", "snapshot_time"] if c in history.columns]
    if sort_cols:
        ascending = [True, True, True, False, False][: len(sort_cols)]
        history = history.sort_values(sort_cols, ascending=ascending).reset_index(drop=True)
    return history


@st.cache_data(show_spinner=False)
def load_stage1_gate_summary(report_path: str = str(STAGE1_PIVOT_REPORT_PATH)) -> dict[str, object]:
    candidates: list[Path] = []
    for pattern in ["stage1*.md", "stage1_gate_report*.json"]:
        for root in [ROOT_DIR / "sessions", ROOT_DIR / "logs"]:
            if root.exists():
                candidates.extend(sorted(root.glob(pattern)))

    if report_path:
        explicit = Path(report_path)
        if explicit.exists():
            candidates.insert(0, explicit)

    chosen: Path | None = None
    if candidates:
        seen: set[Path] = set()
        unique_candidates: list[Path] = []
        for candidate in candidates:
            resolved = candidate.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)
            unique_candidates.append(candidate)
        try:
            chosen = max(unique_candidates, key=lambda p: p.stat().st_mtime)
        except OSError:
            chosen = unique_candidates[0]

    if chosen is None or not chosen.exists():
        return {}

    if chosen.suffix.lower() == ".json":
        try:
            payload = json.loads(chosen.read_text(encoding="utf-8"))
        except Exception:
            return {"source_path": str(chosen)}
        return {
            "source_path": str(chosen),
            "generated": payload.get("generated_at"),
            "verdict": payload.get("verdict"),
            "baseline_passed": str(payload.get("baseline_gate_passed")),
            "trading_passed": str(payload.get("trading_gate_passed")),
        }

    text = chosen.read_text(encoding="utf-8", errors="replace")

    def _match(pattern: str) -> str | None:
        match = re.search(pattern, text, flags=re.MULTILINE)
        return match.group(1).strip() if match else None

    return {
        "source_path": str(chosen),
        "generated": _match(r"\*\*Generated:\*\*\s*(.+)$"),
        "verdict": _match(r"\*\*Overall Verdict:\*\* `([^`]+)`"),
        "baseline_passed": _match(r"\*\*Baseline Gate Passed:\*\* `([^`]+)`"),
        "trading_passed": _match(r"\*\*Trading Gate Passed:\*\* `([^`]+)`"),
    }
