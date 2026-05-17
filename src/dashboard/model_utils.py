from __future__ import annotations

import re
from pathlib import Path
import pandas as pd
import streamlit as st

from src.dashboard.config import (
    ROOT_DIR,
    DEFAULT_DATA_PATH,
    STATIONARY_DATA_PATH,
    DEFAULT_LEADERBOARD_PATH,
    DEFAULT_SNAPSHOT_DIR,
    INTRADAY_5M_LEADERBOARD_PATH,
    INTRADAY_5M_SNAPSHOT_DIR,
    DEFAULT_REWARD_LEADERBOARD_PATH,
    DEFAULT_SUMMARY_PATH,
    INTRADAY_5M_REWARD_LEADERBOARD_PATH,
    INTRADAY_5M_SUMMARY_PATH,
)
from src.market_data import TICKER_PRESETS, get_cache_path_for_ticker
from src.signal_analytics import (
    _align_features_to_model,
    _expected_observation_dim,
    _load_model,
)
from src.trading_env import TradingEnv

# Helper to get cached data without introducing circular imports
def _load_market_data_internal(data_path: str) -> pd.DataFrame:
    from src.dashboard.data_utils import load_market_data
    return load_market_data(data_path)


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


def _data_path_is_compatible_with_expected_shape(data_path: str | Path, expected_obs_dim: int) -> bool:
    try:
        data_df = _load_market_data_internal(str(data_path))
        aligned_df, include_position, market_feature_columns = _align_features_to_model(
            data_df,
            expected_obs_dim=expected_obs_dim,
        )
        temp_env = TradingEnv(
            aligned_df,
            include_position_in_observation=include_position,
            market_feature_columns=market_feature_columns,
        )
        return int(temp_env.observation_space.shape[0]) == expected_obs_dim
    except Exception:
        return False


def _normalize_dashboard_interval(interval: str | None) -> str:
    raw = str(interval or "1d").strip().lower()
    return "5m" if raw in {"5m", "intraday_5m"} else "1d"


def _infer_interval_from_model_path(model_path: str | Path | None) -> str:
    if not model_path:
        return "1d"
    text = str(model_path).lower().replace("\\", "/")
    if "intraday_5m" in text:
        return "5m"
    if re.search(r"(^|[/_\-.])5m($|[/_\-.])", text):
        return "5m"
    return "1d"


def build_model_cache_buster() -> str:
    files: list[Path] = []
    for root in [ROOT_DIR / "models", ROOT_DIR / "data" / "experiment_snapshots"]:
        if not root.exists():
            continue
        files.extend(sorted(root.rglob("*.zip")))

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


def _artifact_paths_for_interval(interval: str | None) -> tuple[Path, Path, Path, Path]:
    if _normalize_dashboard_interval(interval) == "5m":
        return (
            INTRADAY_5M_LEADERBOARD_PATH,
            INTRADAY_5M_REWARD_LEADERBOARD_PATH,
            INTRADAY_5M_SUMMARY_PATH,
            INTRADAY_5M_SNAPSHOT_DIR,
        )
    return (
        DEFAULT_LEADERBOARD_PATH,
        DEFAULT_REWARD_LEADERBOARD_PATH,
        DEFAULT_SUMMARY_PATH,
        DEFAULT_SNAPSHOT_DIR,
    )


def _leaderboard_paths_for_interval_hint(interval_hint: str | None) -> list[Path]:
    raw_hint = str(interval_hint).strip().lower() if interval_hint is not None else ""
    if raw_hint in {"1d", "5m", "intraday_5m"}:
        preferred, _, _, _ = _artifact_paths_for_interval(raw_hint)
        ordered: list[Path] = [preferred]
    else:
        ordered = [DEFAULT_LEADERBOARD_PATH, INTRADAY_5M_LEADERBOARD_PATH]

    # Dynamically pick up custom run leaderboards
    data_dir = ROOT_DIR / "data"
    if data_dir.exists():
        dynamic_lbs = list(data_dir.glob("*leaderboard*.csv"))
        # Also check snapshots directory
        snapshots_dir = data_dir / "experiment_snapshots"
        if snapshots_dir.exists():
            dynamic_lbs.extend(list(snapshots_dir.glob("*leaderboard*.csv")))
            
        dynamic_lbs.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        ordered.extend(dynamic_lbs)
    resolved: set[Path] = set()
    paths: list[Path] = []
    for candidate in ordered:
        key = candidate.resolve() if candidate.exists() else candidate
        if key in resolved:
            continue
        resolved.add(key)
        paths.append(candidate)
    return paths


def _list_available_models(cache_buster: str = "") -> list[Path]:
    """Scans for all .zip model files in models/, experiment snapshots, and staging."""
    _ = cache_buster
    model_paths: list[Path] = []
    
    search_dirs = [
        ROOT_DIR / "models",
        ROOT_DIR / "data" / "experiment_snapshots",
        ROOT_DIR / "staging" / "models"
    ]
    
    for directory in search_dirs:
        if directory.exists():
            model_paths.extend(list(directory.rglob("*.zip")))

    model_paths.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return model_paths


def _preferred_data_path_for_model(ticker: str, expected_obs_dim: int | None, interval_hint: str | None = None) -> Path:
    from src.dashboard.data_utils import get_data_path_for_ticker
    interval = _normalize_dashboard_interval(interval_hint)
    ticker_non_stationary = get_data_path_for_ticker(ticker, use_stationary=False, interval=interval)
    ticker_stationary = get_data_path_for_ticker(ticker, use_stationary=True, interval=interval)
    fallback_candidates = [ticker_non_stationary, ticker_stationary, DEFAULT_DATA_PATH, STATIONARY_DATA_PATH]

    preferred_candidates = (
        [ticker_stationary, ticker_non_stationary]
        if expected_obs_dim is not None and expected_obs_dim >= 16
        else [ticker_non_stationary, ticker_stationary]
    )

    ordered_candidates: list[Path] = []
    seen: set[Path] = set()
    for candidate in [*preferred_candidates, *fallback_candidates]:
        resolved = candidate.resolve() if candidate.exists() else candidate
        if resolved in seen:
            continue
        seen.add(resolved)
        ordered_candidates.append(candidate)

    if expected_obs_dim is not None:
        for candidate in ordered_candidates:
            if candidate.exists() and _data_path_is_compatible_with_expected_shape(candidate, expected_obs_dim):
                return candidate

    for candidate in ordered_candidates:
        if candidate.exists():
            return candidate

    return DEFAULT_DATA_PATH if DEFAULT_DATA_PATH.exists() else STATIONARY_DATA_PATH


def _ticker_symbol_from_key(ticker_key: str) -> str:
    symbols = TICKER_PRESETS.get(ticker_key, (ticker_key.upper(),))
    return str(symbols[0]).upper()


def _ticker_match_mask(series: pd.Series, ticker_key: str) -> pd.Series:
    ticker_symbol = _ticker_symbol_from_key(ticker_key)
    normalized = series.astype(str).str.strip()
    return normalized.str.lower().eq(ticker_key.lower()) | normalized.str.upper().eq(ticker_symbol)


def _latest_comparable_leaderboard(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty or "leaderboard_version" not in df.columns:
        return df
    version_series = pd.to_numeric(df["leaderboard_version"], errors="coerce")
    if version_series.notna().any():
        latest_version = int(version_series.max())
        filtered = df[version_series.fillna(-1).astype(int) == latest_version].copy()
        if not filtered.empty:
            return filtered
    return df


def _top_ranked_models_from_leaderboard(max_count: int, ticker_key: str, interval_hint: str | None = None) -> list[Path]:
    """Returns top model paths by leaderboard rank, filtered to existing files."""
    if max_count <= 0:
        return []

    ranked: list[Path] = []
    seen: set[Path] = set()
    for leaderboard_path in _leaderboard_paths_for_interval_hint(interval_hint):
        if not leaderboard_path.exists():
            continue

        try:
            leaderboard = pd.read_csv(leaderboard_path)
        except Exception:
            continue

        leaderboard = _latest_comparable_leaderboard(leaderboard)
        if leaderboard.empty or "model_path" not in leaderboard.columns:
            continue

        if "ticker" in leaderboard.columns:
            ticker_mask = _ticker_match_mask(leaderboard["ticker"], ticker_key=ticker_key)
            leaderboard = leaderboard[ticker_mask].copy()
        if leaderboard.empty:
            continue

        if "ranking_score" in leaderboard.columns:
            leaderboard = leaderboard.sort_values("ranking_score", ascending=False)
        elif "test_sharpe_ratio" in leaderboard.columns:
            leaderboard = leaderboard.sort_values("test_sharpe_ratio", ascending=False)
        elif "test_actionable_accuracy" in leaderboard.columns:
            leaderboard = leaderboard.sort_values("test_actionable_accuracy", ascending=False)

        for raw_path in leaderboard["model_path"].dropna().tolist():
            candidate = _resolve_model_path(raw_path)
            if candidate is None:
                continue
            resolved = candidate.resolve()
            if resolved in seen:
                continue
            ranked.append(candidate)
            seen.add(resolved)
            if len(ranked) >= max_count:
                break
        if len(ranked) >= max_count:
            break

    return ranked


def _format_model_label(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT_DIR).as_posix()
    except Exception:
        return path.as_posix()


_CROSS_OS_ANCHORS = [
    "data/experiment_snapshots/",
    "staging/models/",
    "models/",
    "data/",
]

def _resolve_model_path(raw_path: str | Path) -> Path | None:
    # Normalize to forward slashes so macOS paths work on Windows and vice versa
    raw_str = str(raw_path).replace("\\", "/")
    candidate = Path(raw_str)

    if candidate.exists():
        return candidate

    # Relative path — try anchored at project root
    if not candidate.is_absolute():
        rooted = ROOT_DIR / candidate
        if rooted.exists():
            return rooted

    # Cross-OS: strip the foreign machine prefix by finding a known subdir anchor
    for anchor in _CROSS_OS_ANCHORS:
        idx = raw_str.find(anchor)
        if idx != -1:
            rel = raw_str[idx:]
            rooted = ROOT_DIR / rel
            if rooted.exists():
                return rooted

    # Last resort: match by filename in local snapshot dirs
    filename = Path(raw_str).name
    if filename:
        for search_dir in [
            ROOT_DIR / "data" / "experiment_snapshots",
            ROOT_DIR / "staging" / "models",
            ROOT_DIR / "models",
        ]:
            if search_dir.exists():
                for match in search_dir.rglob(filename):
                    return match

    return None


def _model_path_matches_ticker(path: Path, ticker_key: str) -> bool:
    ticker_symbol = _ticker_symbol_from_key(ticker_key)
    text = path.as_posix().lower()
    return ticker_key.lower() in text or ticker_symbol.lower() in text


def _infer_recent_interval_for_ticker(ticker_key: str, all_models: list[Path]) -> str:
    # Prefer recently-created snapshot models because promoted champions may be stale.
    for candidate in all_models:
        text = candidate.as_posix().lower()
        if "experiment_snapshots" not in text:
            continue
        if _model_path_matches_ticker(candidate, ticker_key=ticker_key):
            return _infer_interval_from_model_path(candidate)
    for candidate in all_models:
        if _model_path_matches_ticker(candidate, ticker_key=ticker_key):
            return _infer_interval_from_model_path(candidate)
    return "1d"


def _curate_model_choices(
    all_models: list[Path],
    max_count: int,
    ticker_key: str,
    interval_hint: str | None = None,
) -> list[Path]:
    if max_count <= 0:
        return []

    curated: list[Path] = []
    seen: set[Path] = set()
    ticker_symbol = _ticker_symbol_from_key(ticker_key)
    requested_interval = _normalize_dashboard_interval(interval_hint)

    leaderboard_model_set: set[Path] = set()
    for leaderboard_path in _leaderboard_paths_for_interval_hint(interval_hint):
        if not leaderboard_path.exists():
            continue
        try:
            lb = pd.read_csv(leaderboard_path)
            lb = _latest_comparable_leaderboard(lb)
            if "model_path" in lb.columns and "ticker" in lb.columns:
                lb = lb[_ticker_match_mask(lb["ticker"], ticker_key=ticker_key)]
                for raw in lb["model_path"].dropna().tolist():
                    candidate = _resolve_model_path(raw)
                    if candidate is not None:
                        leaderboard_model_set.add(candidate.resolve())
        except Exception:
            continue

    for p in _top_ranked_models_from_leaderboard(
        max_count=max_count,
        ticker_key=ticker_key,
        interval_hint=interval_hint,
    ):
        resolved = p.resolve()
        if resolved in seen:
            continue
        curated.append(p)
        seen.add(resolved)

    champion_path = ROOT_DIR / "models" / f"sac_trading_bot_{ticker_symbol}.zip"
    if champion_path.exists() and _infer_interval_from_model_path(champion_path) == requested_interval:
        resolved = champion_path.resolve()
        if resolved not in seen:
            curated.append(champion_path)
            seen.add(resolved)

    for p in all_models:
        if len(curated) >= max_count:
            break
        resolved = p.resolve()
        if resolved in seen:
            continue
        name = p.name.lower()
        if leaderboard_model_set and resolved not in leaderboard_model_set:
            continue
        if not leaderboard_model_set:
            # Fallback heuristic when leaderboard has no usable model paths for this ticker.
            if ticker_key.lower() not in name and ticker_symbol.lower() not in name:
                continue
        curated.append(p)
        seen.add(resolved)

    if not curated:
        # Last-resort fallback: keep previous behavior to avoid an empty selector.
        for p in all_models:
            if len(curated) >= max_count:
                break
            resolved = p.resolve()
            if resolved in seen:
                continue
            curated.append(p)
            seen.add(resolved)

    return curated
