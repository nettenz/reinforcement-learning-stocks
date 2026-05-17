from __future__ import annotations

import re
import streamlit as st

from src.dashboard.config import (
    DEFAULT_TICKER,
    DEFAULT_DATA_PATH,
    FALLBACK_DATA_PATH,
    DEFAULT_LEADERBOARD_PATH,
    INTRADAY_5M_LEADERBOARD_PATH,
    RECOMMENDED_THRESHOLD,
    RECOMMENDED_HORIZON,
    RECOMMENDED_CHART_WINDOW,
)
from src.market_data import TICKER_PRESETS
from src.dashboard.model_utils import (
    _list_available_models,
    _curate_model_choices,
    _format_model_label,
    _expected_observation_dim,
    _load_model,
    _normalize_dashboard_interval,
    _preferred_data_path_for_model,
    build_model_cache_buster,
    _infer_recent_interval_for_ticker,
    _ticker_symbol_from_key,
    _infer_interval_from_model_path,
    _data_path_is_compatible_with_expected_shape,
)
from src.dashboard.leaderboard import _detect_leaderboard_tickers

from src.dashboard.pages.signal_analytics import render_signal_analytics_page
from src.dashboard.pages.experiments import render_experiments_page
from src.dashboard.pages.experiment_insights import render_experiment_insights_page
from src.dashboard.pages.performance_analytics import render_performance_analytics_page


def main() -> None:
    st.set_page_config(page_title="RL Signal Analytics Dashboard", layout="wide")
    st.title("RL Buy/Sell Signal Analytics")
    st.write("Analyze signal quality and run aggressive hyperparameter experiments.")

    default_data = DEFAULT_DATA_PATH if DEFAULT_DATA_PATH.exists() else FALLBACK_DATA_PATH

    # Intelligence Synchronization: Model Discovery
    available_models = _list_available_models(cache_buster=build_model_cache_buster())

    with st.sidebar:
        st.header("Global inputs")

        page = st.radio("Section", options=["Signal Analytics", "Experiments", "Experiment Insights", "Performance Analytics"], index=0)
        
        # Ticker selector
        available_tickers: set[str] = set()
        for discovery_path in [DEFAULT_LEADERBOARD_PATH, INTRADAY_5M_LEADERBOARD_PATH]:
            available_tickers.update(_detect_leaderboard_tickers(str(discovery_path)))
        
        supported_ticker_options = sorted(list(TICKER_PRESETS.keys()))
        prioritized = [t for t in supported_ticker_options if t in available_tickers]
        remaining = [t for t in supported_ticker_options if t not in available_tickers]
        ticker_options = prioritized + remaining
        default_index = ticker_options.index(DEFAULT_TICKER) if DEFAULT_TICKER in ticker_options else 0
        
        ticker = st.selectbox(
            "Ticker",
            options=ticker_options,
            index=default_index,
            format_func=lambda k: str(TICKER_PRESETS.get(k, (k.upper(),))[0]),
            help="Select ticker preset for this session. Supported: AAPL, NVDA, AMD, MU, GOOGL, AMZN."
        )
        
        if available_tickers:
            detected_symbols = [str(TICKER_PRESETS.get(k, (k.upper(),))[0]) for k in ticker_options if k in available_tickers]
            st.caption(f"Detected in leaderboard: {', '.join(detected_symbols)}")

        model_interval_key = "signal_dashboard_model_interval"
        interval_mode_key = "signal_dashboard_interval_mode"
        auto_interval = _infer_recent_interval_for_ticker(ticker_key=ticker, all_models=available_models)
        previous_mode = str(st.session_state.get(interval_mode_key, "Auto"))
        interval_mode_options = ["Auto", "5m", "1d"]
        mode_default_idx = interval_mode_options.index(previous_mode) if previous_mode in interval_mode_options else 0
        
        interval_mode = st.selectbox(
            "Model/Data interval",
            options=interval_mode_options,
            index=mode_default_idx,
            help="Auto uses the most recent ticker-matching snapshot family. Set 5m or 1d to force interval selection.",
        )
        st.session_state[interval_mode_key] = interval_mode
        preferred_interval = auto_interval if interval_mode == "Auto" else _normalize_dashboard_interval(interval_mode)
        curation_interval_hint: str | None = preferred_interval
        
        if interval_mode == "Auto":
            st.caption(f"Auto interval resolved to: {preferred_interval}")

        # Model Selection Dropdown
        if not available_models:
            st.sidebar.error("No .zip models found in `models/` or `snapshots/`.")
            model_path = ""
            selected_interval = preferred_interval
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

            model_choices = _curate_model_choices(
                available_models,
                max_count=int(model_limit),
                ticker_key=ticker,
                interval_hint=curation_interval_hint,
            )
            model_labels = [_format_model_label(p) for p in model_choices]

            # Try to find default interval-matching model first, then promoted champion.
            default_idx = 0
            ticker_symbol = _ticker_symbol_from_key(ticker)
            for idx, name in enumerate(model_labels):
                name_lower = name.lower()
                name_interval = "5m" if ("intraday_5m" in name_lower or re.search(r"(^|[/_\-.])5m($|[/_\-.])", name_lower)) else "1d"
                if name_interval == preferred_interval:
                    default_idx = idx
                    break
            if default_idx == 0:
                for idx, name in enumerate(model_labels):
                    if f"sac_trading_bot_{ticker_symbol.lower()}.zip" in name.lower():
                        default_idx = idx
                        break

            model_select_key = "signal_dashboard_model_path"
            model_last_ticker_key = "signal_dashboard_model_last_ticker"
            model_last_interval_key = "signal_dashboard_model_last_interval_pref"
            model_state_ticker_changed = st.session_state.get(model_last_ticker_key) != ticker
            model_state_interval_changed = st.session_state.get(model_last_interval_key) != preferred_interval
            model_state_missing = st.session_state.get(model_select_key) not in model_labels
            if model_state_ticker_changed or model_state_interval_changed or model_state_missing:
                st.session_state[model_select_key] = model_labels[default_idx]
                st.session_state[model_last_ticker_key] = ticker
                st.session_state[model_last_interval_key] = preferred_interval

            selected_model_name = st.selectbox(
                "Model weights (.zip)",
                options=model_labels,
                index=default_idx,
                key=model_select_key,
                help="Choose a specific model snapshot or the latest promoted champion."
            )
            model_path = str(model_choices[model_labels.index(selected_model_name)])
            selected_interval = _infer_interval_from_model_path(model_path)
            st.session_state[model_interval_key] = selected_interval
            st.caption(f"Showing {len(model_choices)} of {total_models} discovered models.")

        expected_obs_dim = None
        if model_path:
            try:
                expected_obs_dim = _expected_observation_dim(_load_model(model_path)[0])
            except Exception:
                expected_obs_dim = None

        selected_default_data = _preferred_data_path_for_model(
            ticker,
            expected_obs_dim,
            interval_hint=selected_interval,
        )
        if not selected_default_data.exists():
            selected_default_data = default_data

        data_path_key = "signal_dashboard_data_path"
        last_ticker_key = "signal_dashboard_last_ticker"
        last_interval_key = "signal_dashboard_last_interval"

        # Update data path if ticker/interval changed OR if there's a shape mismatch.
        ticker_changed = st.session_state.get(last_ticker_key) != ticker
        interval_changed = st.session_state.get(last_interval_key) != selected_interval
        shape_mismatch = (
            expected_obs_dim is not None
            and data_path_key in st.session_state
            and not _data_path_is_compatible_with_expected_shape(st.session_state[data_path_key], expected_obs_dim)
        )

        if data_path_key not in st.session_state or ticker_changed or interval_changed or shape_mismatch:
            st.session_state[data_path_key] = str(selected_default_data)
            st.session_state[last_ticker_key] = ticker
            st.session_state[last_interval_key] = selected_interval

        data_path = st.text_input("Data CSV path", key=data_path_key)
        st.caption(
            f"Detected interval: {selected_interval} | Suggested compatible data path for this model: {selected_default_data}"
        )

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
            ticker=ticker,
            data_path=data_path,
            model_path=model_path,
            threshold=threshold,
            horizon_steps=horizon_steps,
            deterministic_policy=deterministic_policy,
        )
        return

    if page == "Experiment Insights":
        render_experiment_insights_page(ticker=ticker, interval=selected_interval)
        return

    if page == "Performance Analytics":
        render_performance_analytics_page(ticker=ticker, interval=selected_interval)
        return

    render_experiments_page(ticker=ticker, interval=selected_interval)


if __name__ == "__main__":
    main()
