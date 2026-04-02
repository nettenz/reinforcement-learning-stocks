from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
import re

import altair as alt
import numpy as np
import pandas as pd
import streamlit as st

from src.experiments import (
    DEFAULT_LEADERBOARD_PATH,
    DEFAULT_REWARD_LEADERBOARD_PATH,
    DEFAULT_SNAPSHOT_DIR,
    DEFAULT_SUMMARY_PATH,
    run_experiments,
    write_experiment_outputs,
)
from src.signal_analytics import (
    ACTION_LABELS,
    _align_features_to_model,
    _expected_observation_dim,
    _load_model,
    compute_metrics,
    confusion_matrix,
    enrich_with_truth_labels,
    simulate_agent_signals,
)
from src.trading_env import TradingEnv

ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_DATA_PATH = ROOT_DIR / "data" / "tech_training_data.parquet"
STATIONARY_DATA_PATH = ROOT_DIR / "data" / "tech_training_data_stationary.parquet"
FALLBACK_DATA_PATH = ROOT_DIR / "data" / "tech_training_data.csv"
DEFAULT_ACTIONABLE_TARGET = 0.55
RECOMMENDED_THRESHOLD = 0.0020
RECOMMENDED_HORIZON = 1
RECOMMENDED_CHART_WINDOW = 2000
PROMOTION_GATE_DEFAULTS = {
    "min_test_actionable": 0.53,
    "min_test_win_rate": 0.52,
    "min_test_alpha": 0.00,
    "max_val_test_gap": 0.05,
    "max_test_cv": 1.0,
}

def _validate_model_shape(model_path: str, data_df: pd.DataFrame) -> None:
    """Checks if the data feature dimensions match what the model policy expects."""
    try:
        model, _ = _load_model(model_path)
        expected_shape = _expected_observation_dim(model)
        aligned_df, include_position, market_feature_columns = _align_features_to_model(
            data_df,
            expected_obs_dim=expected_shape,
        )
        temp_env = TradingEnv(
            aligned_df,
            include_position_in_observation=include_position,
            market_feature_columns=market_feature_columns,
        )
        actual_shape = int(temp_env.observation_space.shape[0])

        if expected_shape != actual_shape:
            account_position_dim = 5 if include_position else 2
            st.error(
                f"**Shape Mismatch Detected!**\n\n"
                f"Model expects **{expected_shape}** features, "
                f"but aligned environment provides **{actual_shape}** features.\n\n"
                f"Aligned schema: market={len(temp_env.market_feature_columns)}, "
                f"news={len(temp_env.active_news_columns)}, account+position={account_position_dim}."
            )
            st.stop()
    except ValueError as exc:
        st.error(str(exc))
        st.stop()
    except Exception as exc:
        # If it's not a structural issue, let the simulation path attempt a full run.
        st.sidebar.warning(f"Structural validation skipped: {str(exc)}")

def _list_available_models() -> list[Path]:
    """Scans for all .zip model files in models/ and experiment snapshots."""
    model_paths = []
    models_dir = ROOT_DIR / "models"
    if models_dir.exists():
        model_paths.extend(list(models_dir.glob("*.zip")))
    
    snapshots_dir = ROOT_DIR / "data" / "experiment_snapshots"
    if snapshots_dir.exists():
        model_paths.extend(list(snapshots_dir.glob("*.zip")))
    
    # Sort by mtime (newest first)
    model_paths.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return model_paths


def _top_ranked_models_from_leaderboard(max_count: int) -> list[Path]:
    """Returns top model paths by leaderboard rank, filtered to existing files."""
    if max_count <= 0 or not DEFAULT_LEADERBOARD_PATH.exists():
        return []

    try:
        leaderboard = pd.read_csv(DEFAULT_LEADERBOARD_PATH)
    except Exception:
        return []

    if leaderboard.empty or "model_path" not in leaderboard.columns:
        return []

    if "ranking_score" in leaderboard.columns:
        leaderboard = leaderboard.sort_values("ranking_score", ascending=False)
    elif "test_actionable_accuracy" in leaderboard.columns:
        leaderboard = leaderboard.sort_values("test_actionable_accuracy", ascending=False)

    ranked: list[Path] = []
    seen: set[Path] = set()
    for raw_path in leaderboard["model_path"].dropna().tolist():
        candidate = Path(str(raw_path))
        if not candidate.exists():
            continue
        resolved = candidate.resolve()
        if resolved in seen:
            continue
        ranked.append(candidate)
        seen.add(resolved)
        if len(ranked) >= max_count:
            break

    return ranked


def _format_model_label(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT_DIR).as_posix()
    except Exception:
        return path.as_posix()


def _curate_model_choices(all_models: list[Path], max_count: int) -> list[Path]:
    if max_count <= 0:
        return []

    curated: list[Path] = []
    seen: set[Path] = set()

    for p in _top_ranked_models_from_leaderboard(max_count=max_count):
        resolved = p.resolve()
        if resolved in seen:
            continue
        curated.append(p)
        seen.add(resolved)

    for p in all_models:
        if len(curated) >= max_count:
            break
        resolved = p.resolve()
        if resolved in seen:
            continue
        curated.append(p)
        seen.add(resolved)

    return curated


@st.cache_data(show_spinner=False)
def load_market_data(data_path: str) -> pd.DataFrame:
    path = Path(data_path)
    if not path.exists():
        raise FileNotFoundError(f"Data file not found: {path}")
    if path.suffix == ".parquet":
        return pd.read_parquet(path)
    parse_dates = ["Date"] if "Date" in pd.read_csv(path, nrows=0).columns else None
    df = pd.read_csv(path, parse_dates=parse_dates)

    required = {"Open", "High", "Low", "Close", "Volume"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Data file is missing required columns: {sorted(missing)}")
    return df


@st.cache_data(show_spinner=False)
def evaluate_signals(
    data_path: str,
    model_path: str,
    threshold: float,
    horizon_steps: int,
    deterministic_policy: bool,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    df = load_market_data(data_path)
    signals = simulate_agent_signals(df=df, model_path=model_path, deterministic=deterministic_policy)
    enriched = enrich_with_truth_labels(signals, threshold=threshold, horizon_steps=horizon_steps)
    conf = confusion_matrix(enriched)
    return enriched, conf


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
    return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)


def _extract_snapshot_label(path: Path) -> str:
    stem = path.stem
    for prefix in ("experiment_leaderboard_", "leaderboard_"):
        if stem.startswith(prefix):
            stem = stem[len(prefix) :]
            break
    stem = re.sub(r"^\d{8}-\d{6}Z?_?", "", stem)
    stem = stem.strip("_-")
    return stem if stem else "unlabeled"


def _format_float(value: float) -> str:
    text = f"{float(value):.6f}".rstrip("0").rstrip(".")
    return text if text else "0"


def _make_command_from_config(
    config: dict[str, float | int | bool | str],
    seeds: str,
    run_label: str,
) -> str:
    seed_count = max(1, len([s for s in seeds.split(",") if s.strip()]))
    ignore_cost_flag = (
        "--reward-ignore-transaction-cost"
        if bool(config["reward_ignore_transaction_cost"])
        else "--no-reward-ignore-transaction-cost"
    )
    return (
        "python src/experiments.py "
        f"--include-news --use-stationary-features --seeds {seeds} "
        f"--timesteps {int(config['timesteps'])} "
        f"--learning-rates {_format_float(float(config['learning_rate']))} "
        f"--gammas {_format_float(float(config['gamma']))} "
        f"--ent-coefs {_format_float(float(config['ent_coef']))} "
        f"--threshold {_format_float(float(config['threshold']))} "
        f"--horizon {int(config['horizon'])} "
        f"--transaction-cost-rate {_format_float(float(config['transaction_cost_rate']))} "
        f"--trade-penalty {_format_float(float(config['trade_penalty']))} "
        f"--reward-mode {str(config.get('reward_mode', 'legacy'))} "
        f"--rolling-reward-window {int(config.get('rolling_reward_window', 100))} "
        f"--reward-epsilon {_format_float(float(config.get('reward_epsilon', 1e-6)))} "
        f"--reward-return-scale {_format_float(float(config['reward_return_scale']))} "
        f"--reward-direction-scale {_format_float(float(config['reward_direction_scale']))} "
        f"--reward-hold-penalty-scale {_format_float(float(config['reward_hold_penalty_scale']))} "
        f"--reward-drawdown-penalty-scale {_format_float(float(config['reward_drawdown_penalty_scale']))} "
        f"--reward-action-bonus-scale {_format_float(float(config['reward_action_bonus_scale']))} "
        f"--reward-clip {_format_float(float(config['reward_clip']))} "
        f"{ignore_cost_flag} "
        f"--append "
        f"--max-runs {seed_count} "
        f"--run-label {run_label}"
    )


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


def summarize_snapshot_bests(history: pd.DataFrame) -> pd.DataFrame:
    if history.empty:
        return history
    if "ranking_score" in history.columns:
        idx = history.groupby("snapshot_id")["ranking_score"].idxmax()
    else:
        idx = history.groupby("snapshot_id")["row_rank"].idxmin()
    bests = history.loc[idx].copy().sort_values("snapshot_time").reset_index(drop=True)
    bests["val_test_gap"] = bests["val_actionable_accuracy"] - bests["test_actionable_accuracy"]
    return bests


def _safe_get(row: pd.Series, key: str, default: object) -> object:
    val = row.get(key, default)
    return default if pd.isna(val) else val


def _evaluate_promotion_gates(row: pd.Series) -> dict[str, object]:
    test_actionable = float(_safe_get(row, "test_actionable_accuracy", 0.0))
    test_win_rate = float(_safe_get(row, "test_trade_win_rate", 0.0))
    test_alpha = float(_safe_get(row, "test_alpha_vs_qqq", float("-inf")))
    val_actionable = float(_safe_get(row, "val_actionable_accuracy", 0.0))
    test_cv_raw = row.get("test_return_cv_by_config", np.inf)
    test_cv = float(pd.to_numeric(pd.Series([test_cv_raw]), errors="coerce").fillna(np.inf).iloc[0])

    checks = {
        "test_actionable": test_actionable >= PROMOTION_GATE_DEFAULTS["min_test_actionable"],
        "test_win_rate": test_win_rate >= PROMOTION_GATE_DEFAULTS["min_test_win_rate"],
        "test_alpha": test_alpha >= PROMOTION_GATE_DEFAULTS["min_test_alpha"],
        "val_test_gap": abs(val_actionable - test_actionable) <= PROMOTION_GATE_DEFAULTS["max_val_test_gap"],
        "test_cv": test_cv < PROMOTION_GATE_DEFAULTS["max_test_cv"],
    }
    return {
        "pass": all(checks.values()),
        "checks": checks,
        "values": {
            "test_actionable": test_actionable,
            "test_win_rate": test_win_rate,
            "test_alpha": test_alpha,
            "val_test_gap": abs(val_actionable - test_actionable),
            "test_cv": test_cv,
        },
    }


def _config_from_row(row: pd.Series) -> dict[str, float | int | bool | str]:
    return {
        "timesteps": int(_safe_get(row, "timesteps", 20000)),
        "learning_rate": float(_safe_get(row, "learning_rate", 0.0003)),
        "gamma": float(_safe_get(row, "gamma", 0.99)),
        "ent_coef": float(_safe_get(row, "ent_coef", 0.02)),
        "threshold": float(_safe_get(row, "threshold", 0.002)),
        "horizon": int(_safe_get(row, "horizon", 1)),
        "transaction_cost_rate": float(_safe_get(row, "transaction_cost_rate", 0.001)),
        "trade_penalty": float(_safe_get(row, "trade_penalty", 0.05)),
        "reward_mode": str(_safe_get(row, "reward_mode", "sharpe")),
        "rolling_reward_window": int(_safe_get(row, "rolling_reward_window", 100)),
        "reward_epsilon": float(_safe_get(row, "reward_epsilon", 1e-6)),
        "reward_return_scale": float(_safe_get(row, "reward_return_scale", 1.0)),
        "reward_direction_scale": float(_safe_get(row, "reward_direction_scale", 0.35)),
        "reward_hold_penalty_scale": float(_safe_get(row, "reward_hold_penalty_scale", 0.05)),
        "reward_drawdown_penalty_scale": float(_safe_get(row, "reward_drawdown_penalty_scale", 0.10)),
        "reward_action_bonus_scale": float(_safe_get(row, "reward_action_bonus_scale", 0.02)),
        "reward_clip": float(_safe_get(row, "reward_clip", 1.0)),
        "reward_ignore_transaction_cost": bool(int(_safe_get(row, "reward_ignore_transaction_cost", 1))),
    }


def build_next_step_recommendations(history: pd.DataFrame, target: float, seeds: str) -> list[dict[str, object]]:
    if history.empty:
        return []

    best_row = history.sort_values("ranking_score", ascending=False).iloc[0]
    recent = history.sort_values("snapshot_time").tail(min(30, len(history)))
    recent_bests = summarize_snapshot_bests(history).tail(min(6, max(1, history["snapshot_id"].nunique())))

    avg_val = float(recent_bests["val_actionable_accuracy"].mean())
    avg_test = float(recent_bests["test_actionable_accuracy"].mean())
    collapse_rate = float((recent["val_actionable_accuracy"] <= 0.01).mean())
    avg_gap = float((recent_bests["val_actionable_accuracy"] - recent_bests["test_actionable_accuracy"]).mean())

    base_cfg = _config_from_row(best_row)
    recs: list[dict[str, object]] = []

    stability_cfg = base_cfg.copy()
    stability_cfg["timesteps"] = int(max(10000, int(base_cfg["timesteps"] * 0.8)))
    stability_cfg["ent_coef"] = max(float(base_cfg["ent_coef"]), 0.03)
    stability_cfg["reward_mode"] = "sharpe"
    stability_cfg["reward_direction_scale"] = min(float(base_cfg["reward_direction_scale"]), 0.40)
    stability_cfg["reward_hold_penalty_scale"] = min(float(base_cfg["reward_hold_penalty_scale"]), 0.03)
    stability_cfg["reward_drawdown_penalty_scale"] = max(float(base_cfg["reward_drawdown_penalty_scale"]), 0.10)
    stability_cfg["reward_action_bonus_scale"] = max(float(base_cfg["reward_action_bonus_scale"]), 0.03)
    recs.append(
        {
            "title": "Stability-first retry",
            "why": f"Recent collapse rate is {collapse_rate:.1%}; this setup pushes exploration and softer directional pressure.",
            "steps": [
                "Inspect the latest snapshot's action mix and confirm which seeds collapsed into low-action behavior.",
                "Re-run with higher exploration and stronger anti-collapse bonus while keeping directional pressure capped.",
                "Compare collapse rate and test actionable accuracy against the previous latest snapshot.",
            ],
            "command": _make_command_from_config(stability_cfg, seeds=seeds, run_label="insights-stability"),
        }
    )

    accuracy_cfg = base_cfg.copy()
    accuracy_cfg["timesteps"] = int(max(12000, int(base_cfg["timesteps"])))
    accuracy_cfg["reward_return_scale"] = min(2.0, float(base_cfg["reward_return_scale"]) + 0.10)
    accuracy_cfg["reward_direction_scale"] = min(0.50, float(base_cfg["reward_direction_scale"]) + 0.05)
    accuracy_cfg["ent_coef"] = max(0.02, float(base_cfg["ent_coef"]))
    accuracy_cfg["reward_mode"] = "sharpe"
    recs.append(
        {
            "title": "Accuracy push",
            "why": (
                f"Recent best means are val={avg_val:.3f}, test={avg_test:.3f}; "
                f"target is {target:.2f}. This extends training while nudging directional signal weight."
            ),
            "steps": [
                "Increase training horizon and slightly up-weight return/directional reward components.",
                "Run the updated config on the same seed set for an apples-to-apples comparison.",
                "Accept this path only if test actionable moves closer to target without widening the val/test gap.",
            ],
            "command": _make_command_from_config(accuracy_cfg, seeds=seeds, run_label="insights-accuracy"),
        }
    )

    generalization_cfg = base_cfg.copy()
    generalization_cfg["ent_coef"] = max(0.03, float(base_cfg["ent_coef"]))
    generalization_cfg["timesteps"] = int(max(10000, int(base_cfg["timesteps"] * 0.8)))
    generalization_cfg["reward_mode"] = "sharpe"
    if avg_gap > 0.05:
        generalization_cfg["reward_direction_scale"] = max(0.25, float(base_cfg["reward_direction_scale"]) - 0.05)
        generalization_cfg["reward_drawdown_penalty_scale"] = min(0.30, float(base_cfg["reward_drawdown_penalty_scale"]) + 0.03)
        why_text = f"Val-test gap is {avg_gap:.3f}; this reduces likely overfit to validation dynamics."
    else:
        generalization_cfg["gamma"] = min(0.995, float(base_cfg["gamma"]) + 0.002)
        generalization_cfg["reward_hold_penalty_scale"] = max(0.01, float(base_cfg["reward_hold_penalty_scale"]) - 0.01)
        why_text = "Val/test are similarly low; this broadens credit assignment and avoids over-penalizing Hold."
    recs.append(
        {
            "title": "Generalization check",
            "why": why_text,
            "steps": [
                "Adjust generalization-sensitive knobs (gamma/hold penalty or directional/drawdown balance).",
                "Re-evaluate val/test drift over the newest snapshots instead of single-run results.",
                "Promote this profile only if transfer improves while keeping stability metrics intact.",
            ],
            "command": _make_command_from_config(generalization_cfg, seeds=seeds, run_label="insights-generalization"),
        }
    )

    unique_recs: list[dict[str, object]] = []
    seen_cmds: set[str] = set()
    for rec in recs:
        if rec["command"] in seen_cmds:
            continue
        unique_recs.append(rec)
        seen_cmds.add(rec["command"])
    return unique_recs


def build_experiment_interpretation(history: pd.DataFrame, target: float) -> dict[str, object]:
    bests = summarize_snapshot_bests(history)
    if bests.empty:
        return {
            "stage": "insufficient-history",
            "summary": "Not enough experiment snapshots to infer trends.",
            "findings": [],
            "focus": "Run more snapshots before interpreting model behavior.",
        }

    recent_bests = bests.tail(min(6, len(bests)))
    recent_rows = history.tail(min(30, len(history)))

    latest = recent_bests.iloc[-1]
    avg_val = float(recent_bests["val_actionable_accuracy"].mean())
    avg_test = float(recent_bests["test_actionable_accuracy"].mean())
    avg_gap = float((recent_bests["val_actionable_accuracy"] - recent_bests["test_actionable_accuracy"]).mean())
    test_std = float(recent_bests["test_actionable_accuracy"].std(ddof=0)) if len(recent_bests) > 1 else 0.0
    collapse_rate = float((recent_rows["val_actionable_accuracy"] <= 0.01).mean())

    findings: list[str] = [
        f"Recent best mean accuracy: val={avg_val:.3f}, test={avg_test:.3f}.",
        f"Latest snapshot accuracy: val={float(latest['val_actionable_accuracy']):.3f}, test={float(latest['test_actionable_accuracy']):.3f}.",
        f"Recent val-test gap: {avg_gap:+.3f}.",
        f"Recent test stability (std): {test_std:.3f}.",
    ]

    if "test_return_cv_by_config" in recent_rows.columns:
        recent_cv = (
            pd.to_numeric(recent_rows["test_return_cv_by_config"], errors="coerce")
            .replace([np.inf, -np.inf], np.nan)
            .dropna()
        )
        if not recent_cv.empty:
            findings.append(f"Recent config-level Test Return CV: {float(recent_cv.iloc[-1]):.2f}.")

    if collapse_rate > 0:
        findings.append(f"Collapse signatures (val actionable <= 1%) appeared in {collapse_rate:.1%} of recent runs.")

    if avg_test >= target and abs(avg_gap) <= 0.03 and test_std <= 0.05:
        stage = "healthy"
        summary = "Model behavior looks healthy: near-target accuracy with stable generalization."
        focus = "Prioritize scale-up (more timesteps/seeds) and stress-test across market regimes."
    elif collapse_rate >= 0.20:
        stage = "collapse-risk"
        summary = "Model behavior suggests collapse risk: actionable decisions are dropping too often."
        focus = "Run the stability-focused recommendation first, then re-check action mix."
    elif "test_return_cv_by_config" in recent_rows.columns and float(
        pd.to_numeric(recent_rows["test_return_cv_by_config"], errors="coerce")
        .replace([np.inf, -np.inf], np.nan)
        .fillna(0.0)
        .max()
    ) >= 1.0:
        stage = "stability-risk"
        summary = "Returns are unstable across seeds for similar configs (high CV risk)."
        focus = "Shorten timesteps, raise entropy, and keep Sharpe reward while rechecking CV by config."
    elif avg_gap > 0.05:
        stage = "overfit-risk"
        summary = "Validation outperforms test by a meaningful margin; likely overfitting to split dynamics."
        focus = "Run the generalization-focused recommendation first and tighten drawdown controls."
    elif avg_test < target:
        stage = "under-target"
        summary = "Model is below target actionable accuracy and needs stronger signal extraction."
        focus = "Run the accuracy-push recommendation first, then compare win-rate drift."
    else:
        stage = "mixed"
        summary = "Signals are mixed: some progress, but stability and transfer are inconsistent."
        focus = "Alternate stability and generalization recommendations before larger sweeps."

    return {
        "stage": stage,
        "summary": summary,
        "findings": findings,
        "focus": focus,
    }


def compute_pnl_summary(enriched: pd.DataFrame) -> tuple[float, float]:
    if enriched.empty:
        return 0.0, 0.0
    first_net_worth = float(enriched["net_worth"].iloc[0])
    first_reward = float(enriched["reward"].iloc[0])
    initial_balance = first_net_worth - first_reward
    total_pnl = float(enriched["net_worth"].iloc[-1] - initial_balance)
    pnl_return = float(total_pnl / initial_balance) if initial_balance != 0 else 0.0
    return total_pnl, pnl_return


def add_cumulative_pnl(enriched: pd.DataFrame) -> pd.DataFrame:
    enriched_view = enriched.copy()
    if not len(enriched_view):
        enriched_view["cumulative_pnl"] = 0.0
        return enriched_view

    first_net_worth = float(enriched_view["net_worth"].iloc[0])
    first_reward = float(enriched_view["reward"].iloc[0])
    initial_balance = first_net_worth - first_reward
    enriched_view["cumulative_pnl"] = enriched_view["net_worth"] - initial_balance
    return enriched_view


def build_action_mix_table(enriched: pd.DataFrame) -> pd.DataFrame:
    action_distribution = (
        enriched.groupby("action_label", as_index=False)
        .agg(
            count=("action_label", "size"),
            total_pnl=("reward", "sum"),
            avg_trade_edge=("trade_edge", "mean"),
        )
        .rename(columns={"action_label": "action"})
    )
    order = [ACTION_LABELS[0], ACTION_LABELS[1], ACTION_LABELS[2]]
    action_distribution["action"] = pd.Categorical(action_distribution["action"], categories=order, ordered=True)
    action_distribution = action_distribution.sort_values("action").reset_index(drop=True)
    action_distribution["avg_trade_edge"] = action_distribution["avg_trade_edge"].fillna(0.0)
    return action_distribution


def render_theoretical_headroom(enriched: pd.DataFrame) -> None:
    overall_accuracy = float(enriched["is_correct"].mean()) if len(enriched) else 0.0
    oracle_accuracy = 1.0
    accuracy_headroom = max(0.0, oracle_accuracy - overall_accuracy)

    oracle_edge = pd.Series(0.0, index=enriched.index, dtype="float64")
    oracle_edge = oracle_edge.mask(enriched["true_signal"] == 1, enriched["horizon_return"])
    oracle_edge = oracle_edge.mask(enriched["true_signal"] == 2, -enriched["horizon_return"])

    oracle_return = float((1.0 + oracle_edge).cumprod().iloc[-1] - 1.0) if len(enriched) else 0.0
    model_return = float((1.0 + enriched["trade_edge"]).cumprod().iloc[-1] - 1.0) if len(enriched) else 0.0
    return_headroom = oracle_return - model_return

    c1, c2, c3 = st.columns(3)
    c1.metric("Theoretical Max Accuracy", f"{oracle_accuracy * 100:.2f}%")
    c2.metric("Accuracy Headroom", f"{accuracy_headroom * 100:.2f} pp")
    c3.metric("Oracle-vs-Model Return Gap", f"{return_headroom * 100:.2f}%")


def render_metrics(enriched: pd.DataFrame) -> None:
    metrics = compute_metrics(enriched)
    total_pnl, pnl_return = compute_pnl_summary(enriched)
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Overall Accuracy", f"{metrics.overall_accuracy * 100:.2f}%")
    col2.metric("Actionable Accuracy", f"{metrics.actionable_accuracy * 100:.2f}%")
    col3.metric("Trade Win Rate", f"{metrics.trade_win_rate * 100:.2f}%")
    col4.metric("Total P&L", f"${total_pnl:,.2f}", delta=f"{pnl_return * 100:.2f}%")

    col5, col6, col7 = st.columns(3)
    col5.metric("Buy Precision / Recall", f"{metrics.buy_precision:.2f} / {metrics.buy_recall:.2f}")
    col6.metric("Sell Precision / Recall", f"{metrics.sell_precision:.2f} / {metrics.sell_recall:.2f}")
    col7.metric("Signal Cumulative Return", f"{metrics.cumulative_signal_return * 100:.2f}%")

    st.caption(f"Average trade edge: {metrics.mean_trade_edge * 100:.3f}% per signal.")


def render_charts(
    enriched: pd.DataFrame,
    chart_window_rows: int,
    show_horizon_panel: bool,
    show_error_markers: bool,
    show_signal_labels: bool,
    signal_label_budget: int,
) -> None:
    st.subheader("Price, Signals, and Market Velocity")
    if "volume" not in enriched.columns:
        enriched["volume"] = 0.0

    chart_df = enriched[
        [
            "step",
            "date",
            "price",
            "volume",
            "net_worth",
            "cumulative_pnl",
            "action_label",
            "true_label",
            "is_correct",
            "horizon_return",
        ]
    ].copy()
    chart_df["date"] = pd.to_datetime(chart_df["date"], errors="coerce")
    if chart_window_rows > 0:
        chart_df = chart_df.tail(chart_window_rows).reset_index(drop=True)

    has_valid_dates = not chart_df["date"].isna().all()
    x_field = "date:T" if has_valid_dates else "step:Q"
    x_title = "Date" if has_valid_dates else "Step"
    tooltip_x = "date:T" if has_valid_dates else "step:Q"
    x_key = "date" if has_valid_dates else "step"

    if has_valid_dates:
        chart_df = chart_df.sort_values("date").reset_index(drop=True)
        chart_df["x2_value"] = chart_df["date"].shift(-1)
        if len(chart_df):
            fallback = chart_df["date"].iloc[-1] + pd.Timedelta(days=1)
            chart_df["x2_value"] = chart_df["x2_value"].fillna(fallback)
        x2_field = "x2_value:T"
    else:
        chart_df = chart_df.sort_values("step").reset_index(drop=True)
        chart_df["x2_value"] = chart_df["step"].shift(-1)
        if len(chart_df):
            chart_df.loc[chart_df.index[-1], "x2_value"] = float(chart_df.loc[chart_df.index[-1], "step"]) + 1.0
        x2_field = "x2_value:Q"
    
    # Pre-select shared scale/selection for all sub-charts
    brush = alt.selection_interval(encodings=['x'])
    
    chart_df["hover_label"] = chart_df.apply(
        lambda row: (
            f"{row['action_label']} @ {row['price']:.4f} | "
            f"true={row['true_label']} | {'correct' if bool(row['is_correct']) else 'wrong'}"
        ),
        axis=1,
    )

    # 1. PRICE & SIGNAL BKG ZONES
    background_zones = (
        alt.Chart(chart_df)
        .mark_rect(opacity=0.08)
        .encode(
            x=alt.X(x_field),
            x2=alt.X2(x2_field),
            color=alt.Color(
                "action_label:N",
                scale=alt.Scale(
                    domain=[ACTION_LABELS[0], ACTION_LABELS[1], ACTION_LABELS[2]],
                    range=["transparent", "#10b981", "#ef4444"], 
                ),
                legend=None
            )
        )
    )

    chart_df["price_legend"] = "Market Price"
    base = alt.Chart(chart_df).encode(
        x=alt.X(x_field, title=None, axis=alt.Axis(labels=False, ticks=False)),
        y=alt.Y("price:Q", title="Price ($)", scale=alt.Scale(zero=False)),
        color=alt.Color(
            "price_legend:N",
            title="Asset",
            scale=alt.Scale(domain=["Market Price"], range=["#3b82f6"])
        )
    )
    price_area = base.mark_area(opacity=0.25, interpolate="monotone")
    line = base.mark_line(strokeWidth=2.5, interpolate="monotone")

    signal_df = chart_df[chart_df["action_label"].isin([ACTION_LABELS[1], ACTION_LABELS[2]])].copy()
    hover_signal = alt.selection_point(fields=[x_key], nearest=True, on="mouseover", empty=False, clear=False)
    signal_points = (
        alt.Chart(signal_df)
        .mark_circle(size=65, opacity=1.0, stroke="white", strokeWidth=1)
        .encode(
            x=x_field,
            y="price:Q",
            color=alt.Color(
                "action_label:N",
                title="Signal",
                scale=alt.Scale(domain=[ACTION_LABELS[1], ACTION_LABELS[2]], range=["#059669", "#dc2626"]),
            ),
            tooltip=[
                tooltip_x,
                alt.Tooltip("price:Q", title="Price", format=".4f"),
                alt.Tooltip("action_label:N", title="Agent Decision"),
                alt.Tooltip("true_label:N", title="Ideal Signal"),
                alt.Tooltip("cumulative_pnl:Q", title="P&L", format=".2f"),
            ],
        )
        .add_params(hover_signal)
    )

    # 2. VOLUME SUB-CHART
    volume_chart = (
        alt.Chart(chart_df)
        .mark_bar(opacity=0.4, color="#94a3b8")
        .encode(
            x=alt.X(x_field, title=x_title),
            y=alt.Y("volume:Q", title="Vol", axis=alt.Axis(format=".2s")),
            tooltip=[tooltip_x, alt.Tooltip("volume:Q", title="Volume", format=",")],
        )
        .properties(height=80, width="container")
    )

    # Errors as sharp markers
    error_df = chart_df[(chart_df["action_label"].isin([ACTION_LABELS[1], ACTION_LABELS[2]])) & (~chart_df["is_correct"])].copy()
    error_marks = alt.Chart(pd.DataFrame()) # Empty default
    if not error_df.empty:
        error_df["error_y"] = error_df.apply(lambda r: r["price"] * 1.025 if r["action_label"] == ACTION_LABELS[2] else r["price"] * 0.975, axis=1)
        error_marks = (
            alt.Chart(error_df)
            .mark_point(shape="x", size=110, opacity=1.0, strokeWidth=2.5, color="#f43f5e")
            .encode(x=x_field, y="error_y:Q")
        )

    # Layer and stack
    price_main = (
        alt.layer(background_zones, price_area, line, signal_points, error_marks)
        .properties(height=350, width="container")
        .resolve_scale(color='independent')
    )
    
    # Combined dashboard with VConcat
    combined = alt.vconcat(price_main, volume_chart).resolve_scale(x='shared').configure_view(stroke=None)
    
    st.altair_chart(combined, width="stretch")
    if len(signal_df):
        st.caption("Tip: hover any Buy/Sell marker to pin the annotation; hover another marker to update it.")
    else:
        st.caption("No actionable Buy/Sell markers in the selected chart window.")

    # P&L chart with persistent hover label
    chart_df["pnl_label"] = chart_df.apply(
        lambda row: f"P&L: ${row['cumulative_pnl']:.2f} | Net worth: ${row['net_worth']:.2f}",
        axis=1,
    )
    chart_df["cumulative_pnl_visual"] = chart_df["cumulative_pnl"].astype(float)
    chart_df["cumulative_pnl_positive"] = chart_df["cumulative_pnl_visual"].clip(lower=0)
    chart_df["cumulative_pnl_negative"] = chart_df["cumulative_pnl_visual"].clip(upper=0)
    hover_pnl = alt.selection_point(fields=[x_key], nearest=True, on="mouseover", empty=False, clear=False)

    pnl_area_positive = (
        alt.Chart(chart_df)
        .mark_area(color="#2ecc71", opacity=0.28, interpolate="monotone")
        .encode(
            x=alt.X(x_field, title=x_title),
            y=alt.Y("cumulative_pnl_positive:Q", title="Cumulative P&L"),
        )
    )
    pnl_area_negative = (
        alt.Chart(chart_df)
        .mark_area(color="#e74c3c", opacity=0.20, interpolate="monotone")
        .encode(
            x=alt.X(x_field, title=x_title),
            y=alt.Y("cumulative_pnl_negative:Q", title="Cumulative P&L"),
        )
    )
    pnl_line = (
        alt.Chart(chart_df)
        .mark_line(color="#27ae60", strokeWidth=2, interpolate="monotone")
        .encode(
            x=alt.X(x_field, title=x_title),
            y=alt.Y("cumulative_pnl_visual:Q", title="Cumulative P&L"),
        )
    )
    pnl_zero = (
        alt.Chart(pd.DataFrame({"zero": [0]}))
        .mark_rule(color="#9ca3af", opacity=0.45, strokeDash=[5, 4])
        .encode(y="zero:Q")
    )
    pnl_points = (
        alt.Chart(chart_df)
        .mark_circle(size=0, opacity=0)
        .encode(
            x=x_field,
            y="cumulative_pnl_visual:Q",
            tooltip=[
                tooltip_x,
                alt.Tooltip("cumulative_pnl:Q", title="Cumulative P&L", format=".2f"),
                alt.Tooltip("net_worth:Q", title="Net worth", format=".2f"),
                alt.Tooltip("action_label:N", title="Action"),
            ],
        )
        .add_params(hover_pnl)
    )
    pnl_hover_rule = (
        alt.Chart(chart_df)
        .transform_filter(hover_pnl)
        .mark_rule(color="#9ca3af", strokeDash=[4, 4])
        .encode(x=x_field)
    )
    pnl_hover_point = (
        alt.Chart(chart_df)
        .transform_filter(hover_pnl)
        .mark_circle(size=120, color="#27ae60", stroke="white", strokeWidth=1.5)
        .encode(x=x_field, y="cumulative_pnl_visual:Q")
    )
    pnl_hover_text = (
        alt.Chart(chart_df)
        .transform_filter(hover_pnl)
        .mark_text(align="left", dx=10, dy=-12, fontSize=11, fontWeight="bold", color="#111827")
        .encode(x=x_field, y="cumulative_pnl_visual:Q", text="pnl_label:N")
    )
    pnl_chart = alt.layer(
        pnl_zero,
        pnl_area_negative,
        pnl_area_positive,
        pnl_line,
        pnl_points,
        pnl_hover_rule,
        pnl_hover_point,
        pnl_hover_text,
    ).properties(width="container")
    st.altair_chart(pnl_chart.interactive(), width="stretch")

    if show_horizon_panel:
        st.subheader("2) Horizon Return Analysis")
        horizon_chart = (
            alt.Chart(chart_df)
            .mark_bar(opacity=0.7)
            .encode(
                x=alt.X(x_field, title=x_title),
                y=alt.Y("horizon_return:Q", title="Horizon Return", axis=alt.Axis(format=".1%")),
                color=alt.condition(
                    "datum.horizon_return >= 0",
                    alt.value("#2ecc71"),  # Vibrant Green
                    alt.value("#e74c3c"),  # Vibrant Red
                ),
                tooltip=[
                    tooltip_x,
                    alt.Tooltip("horizon_return:Q", title="Horizon Return", format=".4%"),
                    alt.Tooltip("action_label:N", title="Predicted Action"),
                    alt.Tooltip("true_label:N", title="Market Reality"),
                ],
            )
        ).properties(width="container")
        st.altair_chart(horizon_chart.interactive(), width="stretch")

    # Keep recent-signal tables based on the full evaluated run, not the chart window slice.
    recent_df = enriched[["step", "date", "price", "action_label"]].copy()
    recent_df["date"] = pd.to_datetime(recent_df["date"], errors="coerce")
    recent_has_valid_dates = not recent_df["date"].isna().all()
    display_time_col = "date" if recent_has_valid_dates else "step"
    buy_points = recent_df[recent_df["action_label"] == ACTION_LABELS[1]][[display_time_col, "price"]].tail(20)
    sell_points = recent_df[recent_df["action_label"] == ACTION_LABELS[2]][[display_time_col, "price"]].tail(20)

    buy_col, sell_col = st.columns(2)
    with buy_col:
        st.write("Recent Buy signals")
        if buy_points.empty:
            st.info("No Buy signals were produced for this run.")
        else:
            st.dataframe(buy_points, width="stretch")
    with sell_col:
        st.write("Recent Sell signals")
        if sell_points.empty:
            st.info("No Sell signals were produced for this run.")
        else:
            st.dataframe(sell_points, width="stretch")


def render_signal_analytics_page(
    data_path: str,
    model_path: str,
    threshold: float,
    horizon_steps: int,
    deterministic_policy: bool,
) -> None:
    st.header("Signal Analytics")
    st.caption("Evaluate one trained policy against forward-move labels.")
    st.info(
        "Recommended dashboard settings: "
        f"threshold={RECOMMENDED_THRESHOLD:.4f}, horizon={RECOMMENDED_HORIZON}, "
        f"chart window={RECOMMENDED_CHART_WINDOW} rows."
    )
    with st.sidebar:
        run = st.button("Run analytics", type="primary", width="stretch", key="run_signal_analytics")
        chart_window_rows = st.slider(
            "Chart window (latest rows)",
            min_value=100,
            max_value=5000,
            value=RECOMMENDED_CHART_WINDOW,
            step=100,
        )
        show_signal_labels = st.toggle("Show Buy/Sell text labels", value=False)
        signal_label_budget = st.slider("Signal label density", min_value=4, max_value=40, value=12, step=2)
        show_horizon_panel = st.toggle("Show horizon-return panel", value=True)
        show_error_markers = st.toggle("Highlight incorrect actionable signals", value=True)

    if not run:
        st.info("Set your inputs and click **Run analytics** in the sidebar to begin.")
        return

    try:
        with st.spinner("🚀 Running agent simulation..."):
            # Intelligence Synchronization: Shape Validation
            _validate_model_shape(model_path, load_market_data(data_path))
            
            enriched, conf = evaluate_signals(
                data_path=data_path,
                model_path=model_path,
                threshold=threshold,
                horizon_steps=horizon_steps,
                deterministic_policy=deterministic_policy,
            )
    except (FileNotFoundError, ValueError) as exc:
        st.error(str(exc))
        st.stop()

    enriched_view = add_cumulative_pnl(enriched)

    # PREMIUM KPI ROW
    st.markdown("### 📊 Performance Summary")
    m1, m2, m3, m4 = st.columns(4)
    # Calculate summary stats
    acc = float(enriched_view["is_correct"].mean())
    actionable_df = enriched_view[enriched_view["action_label"].isin([ACTION_LABELS[1], ACTION_LABELS[2]])]
    act_acc = float(actionable_df["is_correct"].mean()) if not actionable_df.empty else 0.0
    total_pnl = float(enriched_view["cumulative_pnl"].iloc[-1])
    max_dd = float((enriched_view["net_worth"] / enriched_view["net_worth"].cummax() - 1).min())

    m1.metric("Overall Accuracy", f"{acc:.1%}", help="Percentage of correctly predicted high-conviction moves.")
    m2.metric("Actionable Accuracy", f"{act_acc:.1%}", delta=f"{act_acc - 0.5:.1%}" if act_acc > 0 else None, help="Accuracy on Buy/Sell signals only (ignores Hold).")
    m3.metric("Total P&L", f"${total_pnl:.2f}", help="Cumulative profit/loss over the evaluated period.")
    m4.metric("Max Drawdown", f"{max_dd:.1%}", delta_color="inverse", help="Deepest peak-to-trough drop in net worth.")

    st.divider()

    st.subheader("1) Price and Signals Visualization")
    with st.container():
        render_charts(
            enriched_view,
            chart_window_rows=chart_window_rows,
            show_horizon_panel=show_horizon_panel,
            show_error_markers=show_error_markers,
            show_signal_labels=show_signal_labels,
            signal_label_budget=signal_label_budget,
        )

    st.subheader("2) Agent Policy Diagnostics")
    policy_label = "Deterministic (argmax)" if deterministic_policy else "Stochastic (sampled)"
    st.caption(f"Current Policy mode: **{policy_label}**")
    render_metrics(enriched_view)

    st.subheader("3) Theoretical Improvement Headroom")
    render_theoretical_headroom(enriched_view)

    st.subheader("4) Classification Quality")
    st.subheader("Confusion matrix (true signal vs predicted action)")
    st.dataframe(conf, width="stretch")

    st.subheader("5) Action Mix and P&L")
    st.write("Action distribution and P&L contribution by action")
    action_distribution = build_action_mix_table(enriched_view)
    st.dataframe(action_distribution, width="stretch")

    st.subheader("6) Detailed Signal Log")
    st.dataframe(
        enriched_view[
            [
                "step",
                "date",
                "price",
                "action_label",
                "true_label",
                "reward",
                "net_worth",
                "cumulative_pnl",
                "horizon_return",
                "trade_edge",
                "is_correct",
            ]
        ],
        width="stretch",
    )


def render_experiments_page() -> None:
    st.header("Experiments")
    st.caption("Run multi-seed SAC (continuous) sweeps and rank configurations on validation performance.")

    with st.sidebar:
        st.subheader("Experiment runner")
        include_news = st.checkbox("Include sentiment features", value=True)
        seeds = st.text_input("Seeds", value="7,13,21")
        timesteps = st.text_input("Timesteps", value="20000,40000")
        learning_rates = st.text_input("Learning rates", value="0.0003,0.0001")
        gammas = st.text_input("Gammas", value="0.99,0.995")
        ent_coefs = st.text_input("Entropy coeffs", value="0.02,0.05")
        threshold = st.number_input(
            "Eval threshold",
            min_value=0.0,
            max_value=0.05,
            value=RECOMMENDED_THRESHOLD,
            step=0.0001,
            format="%.4f",
        )
        horizon = st.number_input("Eval horizon", min_value=1, max_value=10, value=1, step=1)
        transaction_cost_rate = st.number_input("Transaction cost rate", min_value=0.0, max_value=0.02, value=0.001, step=0.0005, format="%.4f")
        trade_penalty = st.number_input("Trade penalty", min_value=0.0, max_value=1.0, value=0.05, step=0.01)
        reward_return_scale = st.number_input("Reward: portfolio-return scale", min_value=0.0, max_value=5.0, value=1.0, step=0.05)
        reward_direction_scale = st.number_input(
            "Reward: directional scale", 
            min_value=0.0, 
            max_value=5.0, 
            value=0.40, 
            step=0.05,
            help="Weights reward based on realized return alignment with position (no look-ahead bias). Tuned to 0.40 after bias fix."
        )
        reward_hold_penalty_scale = st.number_input("Reward: hold penalty scale", min_value=0.0, max_value=5.0, value=0.05, step=0.01)
        reward_drawdown_penalty_scale = st.number_input("Reward: drawdown penalty scale", min_value=0.0, max_value=5.0, value=0.10, step=0.01)
        reward_action_bonus_scale = st.number_input("Reward: action bonus (anti-collapse)", min_value=0.0, max_value=1.0, value=0.02, step=0.01)
        reward_mode = st.selectbox("Reward mode", options=["legacy", "sharpe", "sortino"], index=1)
        rolling_reward_window = st.number_input("Rolling reward window", min_value=5, max_value=1000, value=100, step=5)
        reward_epsilon = st.number_input("Reward epsilon", min_value=1e-9, max_value=1e-3, value=1e-6, format="%.9f")
        reward_clip = st.number_input("Reward clip (+/-)", min_value=0.01, max_value=10.0, value=1.0, step=0.05)
        reward_ignore_transaction_cost = st.checkbox("Ignore transaction cost in reward", value=True)
        run_label = st.text_input(
            "Run label (for snapshot naming)",
            value="dashboard",
            help="Used in snapshot filenames to keep experiment themes clear (example: stability-ent001).",
        )
        max_runs = st.number_input("Max runs (0=all)", min_value=0, max_value=200, value=10, step=1)
        run_experiment = st.button("Run experiments", type="primary", width="stretch", key="run_experiments")

    leaderboard_path = DEFAULT_LEADERBOARD_PATH
    reward_leaderboard_path = DEFAULT_REWARD_LEADERBOARD_PATH
    summary_path = DEFAULT_SUMMARY_PATH
    snapshot_dir = DEFAULT_SNAPSHOT_DIR

    if run_experiment:
        args = argparse.Namespace(
            include_news=include_news,
            refresh_data=False,
            refresh_news=False,
            seeds=seeds,
            timesteps=timesteps,
            learning_rates=learning_rates,
            gammas=gammas,
            ent_coefs=ent_coefs,
            threshold=float(threshold),
            horizon=int(horizon),
            train_ratio=0.70,
            val_ratio=0.15,
            transaction_cost_rate=float(transaction_cost_rate),
            trade_penalty=float(trade_penalty),
            reward_return_scale=float(reward_return_scale),
            reward_direction_scale=float(reward_direction_scale),
            reward_hold_penalty_scale=float(reward_hold_penalty_scale),
            reward_drawdown_penalty_scale=float(reward_drawdown_penalty_scale),
            reward_action_bonus_scale=float(reward_action_bonus_scale),
            reward_mode=reward_mode,
            rolling_reward_window=int(rolling_reward_window),
            reward_epsilon=float(reward_epsilon),
            reward_clip=float(reward_clip),
            reward_ignore_transaction_cost=bool(reward_ignore_transaction_cost),
            use_stationary_features=True,  # SAC models are trained with stationary features
            max_runs=int(max_runs),
            leaderboard_path=str(leaderboard_path),
            reward_leaderboard_path=str(reward_leaderboard_path),
            summary_path=str(summary_path),
            disable_snapshots=False,
            snapshot_dir=str(snapshot_dir),
            run_label=run_label.strip(),
            device="cuda" if __import__('torch').cuda.is_available() else "cpu",
            use_lr_schedule=False,
            n_envs=1,
            append=True,
        )
        with st.spinner("Running experiments..."):
            leaderboard = run_experiments(args)
            leaderboard_path.parent.mkdir(parents=True, exist_ok=True)
            reward_leaderboard_path.parent.mkdir(parents=True, exist_ok=True)
            summary_path.parent.mkdir(parents=True, exist_ok=True)
            write_experiment_outputs(
                leaderboard=leaderboard,
                leaderboard_path=leaderboard_path,
                reward_leaderboard_path=reward_leaderboard_path,
                summary_path=summary_path,
                snapshot_dir=snapshot_dir,
                run_label=run_label.strip() or "dashboard",
                append_results=True,
            )
        st.success(f"Experiments completed. Saved to `{leaderboard_path}`.")

    if not leaderboard_path.exists():
        st.info("No leaderboard found yet. Run experiments from the sidebar.")
        return

    leaderboard = pd.read_csv(leaderboard_path)
    st.subheader("1) Leaderboard")
    st.dataframe(leaderboard, width="stretch")

    if len(leaderboard):
        st.subheader("2) Best Run Snapshot")
        best = leaderboard.iloc[0]
        c1, c2, c3 = st.columns(3)
        c1.metric("Best ranking score", f"{best['ranking_score']:.4f}")
        c2.metric("Best val actionable acc", f"{best['val_actionable_accuracy'] * 100:.2f}%")
        c3.metric("Best test cumulative return", f"{best['test_cumulative_signal_return'] * 100:.2f}%")

        # Risk-adjusted metrics row
        r1, r2, r3, r4 = st.columns(4)
        r1.metric("Val Sharpe", f"{best.get('val_sharpe_ratio', 0):.2f}")
        r2.metric("Test Sharpe", f"{best.get('test_sharpe_ratio', 0):.2f}")
        r3.metric("Val Max DD", f"{best.get('val_max_drawdown', 0) * 100:.2f}%")
        r4.metric("Test Max DD", f"{best.get('test_max_drawdown', 0) * 100:.2f}%")

        if "test_return_cv_by_config" in leaderboard.columns:
            cv_col, risk_col = st.columns(2)
            cv_col.metric("Config Test Return CV", f"{float(best.get('test_return_cv_by_config', 0.0)):.2f}")
            risk_col.metric(
                "High CV Risk",
                "YES" if int(float(best.get("high_return_cv_risk", 0))) == 1 else "NO",
            )

        gate_eval = _evaluate_promotion_gates(best)
        st.markdown("**Promotion Gate Check (Best Run)**")
        if bool(gate_eval["pass"]):
            st.success("PASS: Best run satisfies all promotion gates.")
        else:
            st.error("FAIL: Best run does not satisfy all promotion gates.")

        gate_values = gate_eval["values"]
        gate_checks = gate_eval["checks"]
        gate_table = pd.DataFrame(
            [
                {
                    "gate": "test_actionable_accuracy >= 0.53",
                    "value": f"{gate_values['test_actionable']:.4f}",
                    "status": "PASS" if gate_checks["test_actionable"] else "FAIL",
                },
                {
                    "gate": "test_trade_win_rate >= 0.52",
                    "value": f"{gate_values['test_win_rate']:.4f}",
                    "status": "PASS" if gate_checks["test_win_rate"] else "FAIL",
                },
                {
                    "gate": "test_alpha_vs_qqq >= 0.00",
                    "value": f"{gate_values['test_alpha']:.4f}",
                    "status": "PASS" if gate_checks["test_alpha"] else "FAIL",
                },
                {
                    "gate": "|val_actionable - test_actionable| <= 0.05",
                    "value": f"{gate_values['val_test_gap']:.4f}",
                    "status": "PASS" if gate_checks["val_test_gap"] else "FAIL",
                },
                {
                    "gate": "test_return_cv_by_config < 1.0",
                    "value": "inf" if not np.isfinite(gate_values["test_cv"]) else f"{gate_values['test_cv']:.4f}",
                    "status": "PASS" if gate_checks["test_cv"] else "FAIL",
                },
            ]
        )
        st.dataframe(gate_table, width="stretch", hide_index=True)

    # Leaderboard Performance Charts
    if len(leaderboard) > 1:
        st.subheader("3) Leaderboard Performance")

        chart_cols = []
        if "val_sharpe_ratio" in leaderboard.columns:
            chart_cols.extend(["val_sharpe_ratio", "test_sharpe_ratio"])
        if "val_cumulative_signal_return" in leaderboard.columns:
            chart_cols.extend(["val_cumulative_signal_return", "test_cumulative_signal_return"])
        if "ranking_score" in leaderboard.columns:
            chart_cols.append("ranking_score")

        if chart_cols:
            chart_df = leaderboard[chart_cols].reset_index()
            chart_df = chart_df.rename(columns={"index": "run"})
            chart_long = chart_df.melt(id_vars=["run"], var_name="metric", value_name="value")

            # Standardize colors for better differentiation: Validation = Sky, Test = Emerald/Green
            metric_colors = {
                "val_sharpe_ratio": "#38bdf8",      # Sky 400
                "test_sharpe_ratio": "#10b981",     # Emerald 500
                "val_cumulative_signal_return": "#7dd3fc", 
                "test_cumulative_signal_return": "#34d399",
                "ranking_score": "#818cf8"          # Indigo
            }

            perf_chart = (
                alt.Chart(chart_long)
                .mark_area(opacity=0.25, interpolate="monotone")
                .encode(
                    x=alt.X("run:Q", title="Ranked Performance (Best to Worst)"),
                    y=alt.Y("value:Q", title="Metric Value"),
                    color=alt.Color(
                        "metric:N", 
                        title="Performance Metric",
                        scale=alt.Scale(
                            domain=list(metric_colors.keys()),
                            range=list(metric_colors.values())
                        )
                    ),
                    tooltip=[
                        alt.Tooltip("run:Q", title="Rank"),
                        alt.Tooltip("metric:N", title="Metric"),
                        alt.Tooltip("value:Q", title="Value", format=".4f"),
                    ],
                )
            )
            perf_line = (
                alt.Chart(chart_long)
                .mark_line(interpolate="monotone", strokeWidth=2.5)
                .encode(
                    x="run:Q",
                    y="value:Q",
                    color=alt.Color("metric:N", scale=alt.Scale(domain=list(metric_colors.keys()), range=list(metric_colors.values()))),
                )
            )
            st.altair_chart((perf_chart + perf_line).interactive(), width="stretch")

        # 4) Seed comparison scatter
        if "seed" in leaderboard.columns and "reward_mode" in leaderboard.columns:
            st.subheader("4) Seed Stability & Reward Efficiency")
            scatter = (
                alt.Chart(leaderboard)
                .mark_circle(size=100, opacity=0.8, stroke="white", strokeWidth=0.5)
                .encode(
                    x=alt.X("val_sharpe_ratio:Q", title="Validation Sharpe"),
                    y=alt.Y("test_sharpe_ratio:Q", title="Test (Forward-Look) Sharpe"),
                    color=alt.Color("reward_mode:N", title="Reward Strategy", scale=alt.Scale(scheme="set1")),
                    size=alt.Size("ranking_score:Q", title="Ranking Score"),
                    tooltip=[
                        alt.Tooltip("seed:Q", title="Seed"),
                        alt.Tooltip("reward_mode:N", title="Strategy"),
                        alt.Tooltip("val_sharpe_ratio:Q", title="Val Sharpe", format=".2f"),
                        alt.Tooltip("test_sharpe_ratio:Q", title="Test Sharpe", format=".2f"),
                        alt.Tooltip("ranking_score:Q", title="Overall Score", format=".4f"),
                    ],
                )
            )
            zero_line_y = alt.Chart(pd.DataFrame({"zero": [0]})).mark_rule(color="#f43f5e", strokeDash=[4, 4]).encode(y="zero:Q")
            zero_line_x = alt.Chart(pd.DataFrame({"zero": [0]})).mark_rule(color="#f43f5e", strokeDash=[4, 4]).encode(x="zero:Q")
            st.altair_chart((scatter + zero_line_y + zero_line_x).interactive(), width="stretch")

    if reward_leaderboard_path.exists():
        reward_leaderboard = pd.read_csv(reward_leaderboard_path)
        st.subheader("5) Reward Leaderboard")
        st.dataframe(reward_leaderboard, width="stretch")
        if len(reward_leaderboard):
            st.subheader("6) Best Reward Snapshot")
            best_reward = reward_leaderboard.iloc[0]
            r1, r2, r3 = st.columns(3)
            r1.metric("Best val reward mean", f"{best_reward['val_reward_total_mean']:.5f}")
            r2.metric("Best val direction reward", f"{best_reward['val_reward_direction_mean']:.5f}")
            r3.metric("Best val drawdown", f"{best_reward['val_reward_drawdown_mean']:.5f}")

    if summary_path.exists():
        st.subheader("7) Summary JSON")
        st.code(summary_path.read_text(encoding="utf-8"), language="json")


def render_experiment_insights_page() -> None:
    st.header("Experiment Insights")
    st.caption("Visualize snapshot history and generate next experiment commands to improve actionable accuracy.")

    leaderboard_path = DEFAULT_LEADERBOARD_PATH
    snapshot_dir = DEFAULT_SNAPSHOT_DIR

    with st.sidebar:
        st.subheader("Insights controls")
        target_actionable = st.slider(
            "Target actionable accuracy",
            min_value=0.40,
            max_value=0.80,
            value=DEFAULT_ACTIONABLE_TARGET,
            step=0.01,
        )
        recommendation_seeds = st.text_input("Recommendation seeds", value="7,13,21")

    history_cache_buster = build_history_cache_buster(snapshot_dir=str(snapshot_dir), leaderboard_path=str(leaderboard_path))
    history = load_experiment_history(
        snapshot_dir=str(snapshot_dir),
        leaderboard_path=str(leaderboard_path),
        cache_buster=history_cache_buster,
    )
    if history.empty:
        st.info("No experiment history found yet. Run experiments first to populate snapshots.")
        return

    bests = summarize_snapshot_bests(history)
    if bests.empty:
        st.info("History is present but no ranked rows were found.")
        return

    latest = bests.iloc[-1]
    best_global = history.sort_values("ranking_score", ascending=False).iloc[0]

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Snapshots loaded", f"{bests['snapshot_id'].nunique()}")
    c2.metric("Best val actionable", f"{float(best_global['val_actionable_accuracy']) * 100:.2f}%")
    c3.metric("Best test actionable", f"{float(best_global['test_actionable_accuracy']) * 100:.2f}%")
    c4.metric("Latest val/test", f"{float(latest['val_actionable_accuracy']) * 100:.2f}% / {float(latest['test_actionable_accuracy']) * 100:.2f}%")

    trend_df = bests[
        [
            "snapshot_time",
            "snapshot_label",
            "val_actionable_accuracy",
            "test_actionable_accuracy",
            "ranking_score",
            "val_trade_win_rate",
            "test_trade_win_rate",
        ]
    ].copy()
    trend_long = trend_df.melt(
        id_vars=["snapshot_time", "snapshot_label"],
        value_vars=["val_actionable_accuracy", "test_actionable_accuracy"],
        var_name="split",
        value_name="actionable_accuracy",
    )
    trend_long["split"] = trend_long["split"].map(
        {
            "val_actionable_accuracy": "Validation",
            "test_actionable_accuracy": "Test",
        }
    )

    st.subheader("1) Actionable Accuracy Trend (Best per Snapshot)")
    trend_chart = (
        alt.Chart(trend_long)
        .mark_line(point=True)
        .encode(
            x=alt.X("snapshot_time:T", title="Snapshot time (UTC)"),
            y=alt.Y("actionable_accuracy:Q", title="Actionable accuracy", scale=alt.Scale(domain=[0, 1])),
            color=alt.Color("split:N", title="Split"),
            tooltip=[
                alt.Tooltip("snapshot_time:T", title="Snapshot"),
                alt.Tooltip("snapshot_label:N", title="Label"),
                alt.Tooltip("split:N", title="Split"),
                alt.Tooltip("actionable_accuracy:Q", title="Accuracy", format=".4f"),
            ],
        )
    )
    target_rule = (
        alt.Chart(pd.DataFrame({"target": [target_actionable]}))
        .mark_rule(color="#e74c3c", strokeDash=[4, 4])
        .encode(y="target:Q")
    )
    st.altair_chart((trend_chart + target_rule).interactive(), width="stretch")

    st.subheader("2) Ranking and Win-Rate Stability")
    stability_long = trend_df.melt(
        id_vars=["snapshot_time", "snapshot_label"],
        value_vars=["ranking_score", "val_trade_win_rate", "test_trade_win_rate"],
        var_name="metric",
        value_name="value",
    )
    stability_chart = (
        alt.Chart(stability_long)
        .mark_line(point=True)
        .encode(
            x=alt.X("snapshot_time:T", title="Snapshot time (UTC)"),
            y=alt.Y("value:Q", title="Metric value"),
            color=alt.Color("metric:N", title="Metric"),
            tooltip=[
                alt.Tooltip("snapshot_time:T", title="Snapshot"),
                alt.Tooltip("snapshot_label:N", title="Label"),
                alt.Tooltip("metric:N", title="Metric"),
                alt.Tooltip("value:Q", title="Value", format=".4f"),
            ],
        )
    )
    st.altair_chart(stability_chart.interactive(), width="stretch")

    st.subheader("3) Recent Best Configs")
    display_cols = [
        "snapshot_time",
        "snapshot_label",
        "seed",
        "timesteps",
        "learning_rate",
        "gamma",
        "ent_coef",
        "reward_return_scale",
        "reward_direction_scale",
        "reward_hold_penalty_scale",
        "reward_drawdown_penalty_scale",
        "val_actionable_accuracy",
        "test_actionable_accuracy",
        "ranking_score",
    ]
    visible_cols = [c for c in display_cols if c in bests.columns]
    st.dataframe(bests[visible_cols].sort_values("snapshot_time", ascending=False), width="stretch")

    st.subheader("4) Model Interpretation")
    interpretation = build_experiment_interpretation(history=history, target=target_actionable)
    stage = str(interpretation["stage"])
    summary = str(interpretation["summary"])
    if stage == "healthy":
        st.success(summary)
    elif stage in {"collapse-risk", "overfit-risk"}:
        st.warning(summary)
    else:
        st.info(summary)

    for finding in interpretation["findings"]:
        st.write(f"- {finding}")
    st.caption(f"Recommended focus: {interpretation['focus']}")

    st.subheader("5) Recommended Next Steps")
    recs = build_next_step_recommendations(history=history, target=target_actionable, seeds=recommendation_seeds)
    if not recs:
        st.info("Not enough history to generate recommendations yet.")
        return
    for idx, rec in enumerate(recs, start=1):
        st.markdown(f"**{idx}. {rec['title']}**")
        st.write(rec["why"])
        steps = rec.get("steps", [])
        if isinstance(steps, list):
            for step_idx, step in enumerate(steps, start=1):
                st.write(f"{step_idx}. {step}")
        with st.expander("Optional: run generated command"):
            st.code(str(rec["command"]), language="bash")


def main() -> None:
    st.set_page_config(page_title="RL Signal Analytics Dashboard", layout="wide")
    st.title("RL Buy/Sell Signal Analytics")
    st.write("Analyze signal quality and run aggressive hyperparameter experiments.")

    default_data = DEFAULT_DATA_PATH if DEFAULT_DATA_PATH.exists() else FALLBACK_DATA_PATH
    
    # Intelligence Synchronization: Model Discovery
    available_models = _list_available_models()
    
    with st.sidebar:
        st.header("Global inputs")
        page = st.radio("Section", options=["Signal Analytics", "Experiments", "Experiment Insights"], index=0)
        
        data_path = st.text_input("Data CSV path", value=str(default_data))
        
        # Model Selection Dropdown
        if not available_models:
            st.sidebar.error("No .zip models found in `models/` or `snapshots/`.")
            model_path = ""
        else:
            total_models = len(available_models)
            if total_models >= 10:
                model_limit = st.slider(
                    "Top models shown",
                    min_value=10,
                    max_value=min(20, total_models),
                    value=min(15, total_models),
                    step=1,
                    help="Curate the model picker to top-ranked snapshots first, then recent models.",
                )
            else:
                model_limit = total_models
                st.caption(f"Showing all available models ({total_models}).")

            model_choices = _curate_model_choices(available_models, max_count=int(model_limit))
            model_labels = [_format_model_label(p) for p in model_choices]

            # Try to find default promoted champion
            default_idx = 0
            for idx, name in enumerate(model_labels):
                if "sac_trading_bot.zip" in name:
                    default_idx = idx
                    break
            
            selected_model_name = st.selectbox(
                "Model weights (.zip)",
                options=model_labels,
                index=default_idx,
                help="Choose a specific model snapshot or the latest promoted champion."
            )
            model_path = str(model_choices[model_labels.index(selected_model_name)])
            st.caption(f"Showing {len(model_choices)} of {total_models} discovered models.")
        
        threshold = st.number_input(
            "Movement threshold",
            min_value=0.0,
            max_value=0.05,
            value=RECOMMENDED_THRESHOLD,
            step=0.0001,
            format="%.4f",
            help="Higher precision enabled for threshold tuning.",
        )
        horizon_steps = st.slider("Prediction horizon (steps)", min_value=1, max_value=10, value=RECOMMENDED_HORIZON, step=1)
        st.caption(
            f"Recommended settings: threshold={RECOMMENDED_THRESHOLD:.4f}, "
            f"horizon={RECOMMENDED_HORIZON}, chart window={RECOMMENDED_CHART_WINDOW}."
        )
        deterministic_policy = st.toggle(
            "Deterministic policy (argmax action)",
            value=True,
            help="Turn off to sample actions from policy probabilities for diagnostics.",
        )

    if page == "Signal Analytics":
        render_signal_analytics_page(
            data_path=data_path,
            model_path=model_path,
            threshold=threshold,
            horizon_steps=horizon_steps,
            deterministic_policy=deterministic_policy,
        )
        return

    if page == "Experiment Insights":
        render_experiment_insights_page()
        return

    render_experiments_page()


if __name__ == "__main__":
    main()
