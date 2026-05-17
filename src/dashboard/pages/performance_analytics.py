from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import pandas as pd
import numpy as np
import altair as alt
import streamlit as st

from src.dashboard.config import (
    ROOT_DIR,
    DEFAULT_TICKER,
    RECOMMENDED_THRESHOLD,
    RECOMMENDED_HORIZON,
    RECOMMENDED_CHART_WINDOW,
)
from src.dashboard.model_utils import (
    _artifact_paths_for_interval,
    _leaderboard_paths_for_interval_hint,
    build_model_cache_buster,
    _preferred_data_path_for_model,
    _top_ranked_models_from_leaderboard,
    _list_available_models,
    _curate_model_choices,
    _format_model_label,
    _load_model,
)
from src.dashboard.leaderboard import (
    build_history_cache_buster,
    load_experiment_history,
    _latest_comparable_leaderboard,
    _ticker_match_mask,
)
from src.dashboard.analytics import (
    add_cumulative_pnl,
    summarize_snapshot_bests,
)
from src.dashboard.data_utils import evaluate_signals
from src.signal_analytics import calculate_rolling_sharpe, calculate_rolling_sortino


def render_performance_analytics_page(ticker: str = DEFAULT_TICKER, interval: str = "1d") -> None:
    st.header("Performance Analytics")
    st.caption("Freshness indicator and quick equity-curve diagnostics for the selected model or ensemble.")

    leaderboard_path, _, _, snapshot_dir = _artifact_paths_for_interval(interval)

    with st.sidebar:
        st.subheader("Performance controls")
        choose_leaderboard = st.selectbox(
            "Leaderboard file", 
            options=_leaderboard_paths_for_interval_hint(interval), 
            index=0
        )
        use_ensemble = st.toggle(
            "Use Ensemble (fast, top seed voting)", 
            value=False, 
            help="Use the combined ensemble simulation path when available."
        )
        show_seed_overlays = st.checkbox(
            "Show per-seed overlays (slow)", 
            value=False, 
            help="Simulate top-N models individually and overlay their equity curves."
        )
        seed_overlay_count = st.number_input("Per-seed overlay count", min_value=1, max_value=10, value=3, step=1)
        normalize_equity = st.checkbox(
            "Normalize equity (index to 100)", 
            value=False, 
            help="Index net worth to 100 for relative comparison against benchmarks."
        )
        show_kpis = st.checkbox("Show KPI summary above chart", value=True)
        refresh_now = st.button("Refresh metrics", type="primary", use_container_width=True, key="perf_refresh")

    model_candidates = _top_ranked_models_from_leaderboard(max_count=1, ticker_key=ticker, interval_hint=interval)
    if model_candidates:
        model_path = model_candidates[0]
    else:
        all_models = _list_available_models(cache_buster=build_model_cache_buster())
        curated = _curate_model_choices(all_models, max_count=1, ticker_key=ticker, interval_hint=interval)
        model_path = curated[0] if curated else None

    if not model_path:
        st.info("No model snapshots found for this ticker. Run sweeps to produce snapshots.")
        return

    model_file = Path(model_path)
    try:
        mtime = datetime.fromtimestamp(model_file.stat().st_mtime, tz=timezone.utc)
        st.metric("Model snapshot last modified (UTC)", mtime.strftime("%Y-%m-%d %H:%M:%SZ"))
    except Exception:
        st.warning("Unable to stat model snapshot file for freshness check")

    if refresh_now:
        data_path = str(_preferred_data_path_for_model(ticker, expected_obs_dim=None, interval_hint=interval))
        try:
            with st.spinner("⏳ Running quick simulation..."):
                enriched, _ = evaluate_signals(
                    data_path=data_path,
                    model_path=str(model_path),
                    threshold=RECOMMENDED_THRESHOLD,
                    horizon_steps=RECOMMENDED_HORIZON,
                    deterministic_policy=True,
                    binary_actions=True,  # Default to True to align with PPO
                    use_ensemble=use_ensemble,
                    ticker=ticker,
                    ensemble_config_path=str(ROOT_DIR / "staging" / "models" / "ensemble_config.json"),
                )
        except Exception as e:
            st.error(f"Simulation failed: {e}")
            return

        if enriched.empty:
            st.info("Simulation returned no rows; check data/model compatibility.")
            return

        enriched = add_cumulative_pnl(enriched)
        enriched["date"] = pd.to_datetime(enriched["date"], errors="coerce")

        chart_df = enriched[["date", "step", "net_worth", "cumulative_pnl"]].copy()
        if "price" in enriched.columns and not enriched["price"].isna().all():
            price = enriched["price"].astype(float)
            initial_balance = float(enriched["net_worth"].iloc[0])
            benchmark_net = initial_balance * (price / float(price.iloc[0]))
            chart_df["benchmark_net_worth"] = benchmark_net.values

        chart_df["cummax"] = chart_df["net_worth"].cummax()
        chart_df["drawdown_pct"] = ((chart_df["cummax"] - chart_df["net_worth"]) / chart_df["cummax"]).fillna(0.0)

        if "benchmark_net_worth" in chart_df.columns:
            chart_df["benchmark_cummax"] = chart_df["benchmark_net_worth"].cummax()
            chart_df["benchmark_drawdown_pct"] = (
                (chart_df["benchmark_cummax"] - chart_df["benchmark_net_worth"]) / chart_df["benchmark_cummax"]
            ).fillna(0.0)

        y_title = "Net worth ($)"
        strategy_col = "net_worth"
        benchmark_col = "benchmark_net_worth"
        if normalize_equity and not chart_df.empty:
            base = float(chart_df["net_worth"].iloc[0]) if float(chart_df["net_worth"].iloc[0]) != 0.0 else 1.0
            chart_df["net_worth_index"] = (chart_df["net_worth"] / base) * 100.0
            strategy_col = "net_worth_index"
            y_title = "Equity Index (start = 100)"
            if "benchmark_net_worth" in chart_df.columns:
                base_b = float(chart_df["benchmark_net_worth"].iloc[0]) if float(chart_df["benchmark_net_worth"].iloc[0]) != 0.0 else 1.0
                chart_df["benchmark_index"] = (chart_df["benchmark_net_worth"] / base_b) * 100.0
                benchmark_col = "benchmark_index"

        final_net = float(chart_df["net_worth"].iloc[-1])
        start_net = float(chart_df["net_worth"].iloc[0])
        total_return = (final_net / max(start_net, 1e-8)) - 1.0
        max_drawdown = float(chart_df["drawdown_pct"].max())
        trade_rate = float(enriched["action"].isin([1, 2]).mean()) if "action" in enriched.columns else 0.0

        bench_return = np.nan
        alpha_vs_bench = np.nan
        if "benchmark_net_worth" in chart_df.columns and len(chart_df):
            bench_start = float(chart_df["benchmark_net_worth"].iloc[0])
            bench_end = float(chart_df["benchmark_net_worth"].iloc[-1])
            bench_return = (bench_end / max(bench_start, 1e-8)) - 1.0
            alpha_vs_bench = total_return - bench_return

        returns = chart_df["net_worth"].pct_change().fillna(0.0)
        risk_window = min(60, max(20, int(len(returns) / 8)))
        rolling_sharpe = calculate_rolling_sharpe(returns, window=risk_window)
        rolling_sortino = calculate_rolling_sortino(returns, window=risk_window)
        latest_sharpe = float(rolling_sharpe.dropna().iloc[-1]) if not rolling_sharpe.dropna().empty else np.nan

        if show_kpis:
            k1, k2, k3, k4, k5 = st.columns(5)
            k1.metric("Final Net Worth", f"${final_net:,.0f}")
            k2.metric("Total Return", f"{total_return:.2%}")
            k3.metric("Alpha vs Benchmark", "N/A" if pd.isna(alpha_vs_bench) else f"{alpha_vs_bench:.2%}")
            k4.metric("Max Drawdown", f"{max_drawdown:.2%}", delta_color="inverse")
            k5.metric("Trade Rate", f"{trade_rate:.1%}", delta="Latest Sharpe: n/a" if pd.isna(latest_sharpe) else f"Latest Sharpe: {latest_sharpe:.2f}")

        st.subheader("Equity Curve")
        x_field = "date" if chart_df["date"].notna().any() else "step"

        layers: list[alt.Chart] = []

        strategy_line = (
            alt.Chart(chart_df)
            .mark_line(color="#38bdf8", strokeWidth=2.5)
            .encode(
                x=(x_field + ":T") if x_field == "date" else x_field + ":Q",
                y=alt.Y(strategy_col + ":Q", title=y_title),
                tooltip=[
                    alt.Tooltip("date:T", title="Date"),
                    alt.Tooltip("net_worth:Q", title="Strategy Net", format=",.2f"),
                    alt.Tooltip("drawdown_pct:Q", title="Strategy Drawdown", format=".2%"),
                    alt.Tooltip("cumulative_pnl:Q", title="Cumulative PnL", format=",.2f"),
                ] if x_field == "date" else [
                    alt.Tooltip("step:Q", title="Step"),
                    alt.Tooltip("net_worth:Q", title="Strategy Net", format=",.2f"),
                    alt.Tooltip("drawdown_pct:Q", title="Strategy Drawdown", format=".2%"),
                    alt.Tooltip("cumulative_pnl:Q", title="Cumulative PnL", format=",.2f"),
                ],
            )
        )
        layers.append(strategy_line)

        if benchmark_col in chart_df.columns:
            benchmark_line = (
                alt.Chart(chart_df)
                .mark_line(color="#f59e0b", strokeWidth=1.8, strokeDash=[6, 4])
                .encode(
                    x=(x_field + ":T") if x_field == "date" else x_field + ":Q",
                    y=alt.Y(benchmark_col + ":Q"),
                    tooltip=[
                        alt.Tooltip("date:T", title="Date"),
                        alt.Tooltip("benchmark_net_worth:Q", title="Benchmark Net", format=",.2f"),
                        alt.Tooltip("benchmark_drawdown_pct:Q", title="Benchmark Drawdown", format=".2%"),
                    ] if x_field == "date" else [
                        alt.Tooltip("step:Q", title="Step"),
                        alt.Tooltip("benchmark_net_worth:Q", title="Benchmark Net", format=",.2f"),
                        alt.Tooltip("benchmark_drawdown_pct:Q", title="Benchmark Drawdown", format=".2%"),
                    ],
                )
            )
            layers.append(benchmark_line)

        if normalize_equity:
            reference_line = (
                alt.Chart(pd.DataFrame({"reference": [100.0]}))
                .mark_rule(color="#64748b", strokeDash=[3, 3], opacity=0.5)
                .encode(y="reference:Q")
            )
            layers.append(reference_line)

        seed_lines: list[alt.Chart] = []
        if show_seed_overlays:
            top_models = _top_ranked_models_from_leaderboard(max_count=int(seed_overlay_count), ticker_key=ticker, interval_hint=interval)
            for idx, mpath in enumerate(top_models, start=1):
                try:
                    m_enriched, _ = evaluate_signals(
                        data_path=data_path,
                        model_path=str(mpath),
                        threshold=RECOMMENDED_THRESHOLD,
                        horizon_steps=RECOMMENDED_HORIZON,
                        deterministic_policy=True,
                        binary_actions=True,
                        use_ensemble=False,
                        ticker=ticker,
                        ensemble_config_path=str(ROOT_DIR / "staging" / "models" / "ensemble_config.json"),
                    )
                except Exception:
                    continue
                if m_enriched.empty:
                    continue
                m_enriched["date"] = pd.to_datetime(m_enriched["date"], errors="coerce")
                m_df = m_enriched[["date", "step", "net_worth"]].copy()
                if normalize_equity and not m_df.empty:
                    m_base = float(m_df["net_worth"].iloc[0]) if float(m_df["net_worth"].iloc[0]) != 0.0 else 1.0
                    m_df["net_plot"] = (m_df["net_worth"] / m_base) * 100.0
                else:
                    m_df["net_plot"] = m_df["net_worth"]
                m_df["seed_label"] = f"Seed {idx}"
                seed_lines.append(
                    alt.Chart(m_df)
                    .mark_line(opacity=0.28, color="#10b981")
                    .encode(
                        x=(x_field + ":T") if x_field == "date" else x_field + ":Q",
                        y=alt.Y("net_plot:Q"),
                        tooltip=["seed_label:N", "date:T", "net_worth:Q"] if x_field == "date" else ["seed_label:N", "step:Q", "net_worth:Q"],
                    )
                )

        combined = None
        for layer in [*layers, *seed_lines]:
            combined = layer if combined is None else (combined + layer)

        if combined is not None and not chart_df.empty:
            dd_idx = int(chart_df["drawdown_pct"].idxmax())
            dd_row = chart_df.iloc[[dd_idx]]
            dd_marker = (
                alt.Chart(dd_row)
                .mark_point(color="#ef4444", size=110, shape="triangle-down")
                .encode(
                    x=(x_field + ":T") if x_field == "date" else x_field + ":Q",
                    y=alt.Y(strategy_col + ":Q"),
                    tooltip=[
                        alt.Tooltip("date:T", title="Max DD Date"),
                        alt.Tooltip("net_worth:Q", title="Strategy Net", format=",.2f"),
                        alt.Tooltip("drawdown_pct:Q", title="Max Drawdown", format=".2%"),
                    ] if x_field == "date" else [
                        alt.Tooltip("step:Q", title="Max DD Step"),
                        alt.Tooltip("net_worth:Q", title="Strategy Net", format=",.2f"),
                        alt.Tooltip("drawdown_pct:Q", title="Max Drawdown", format=".2%"),
                    ],
                )
            )
            st.altair_chart((combined + dd_marker).interactive(), use_container_width=True)

        risk_col_left, risk_col_right = st.columns(2)

        with risk_col_left:
            st.subheader("Drawdown")
            dd_long = chart_df[["date", "step", "drawdown_pct"]].copy()
            dd_long["series"] = "Strategy"
            if "benchmark_drawdown_pct" in chart_df.columns:
                bench_dd = chart_df[["date", "step", "benchmark_drawdown_pct"]].rename(columns={"benchmark_drawdown_pct": "drawdown_pct"})
                bench_dd["series"] = "Benchmark"
                dd_long = pd.concat([dd_long, bench_dd], ignore_index=True)

            dd_chart = (
                alt.Chart(dd_long)
                .mark_area(opacity=0.18)
                .encode(
                    x=(x_field + ":T") if x_field == "date" else x_field + ":Q",
                    y=alt.Y("drawdown_pct:Q", title="Drawdown", axis=alt.Axis(format=".0%")),
                    color=alt.Color("series:N", scale=alt.Scale(domain=["Strategy", "Benchmark"], range=["#ef4444", "#f59e0b"])),
                    tooltip=["series:N", "date:T", alt.Tooltip("drawdown_pct:Q", format=".2%")]
                    if x_field == "date"
                    else ["series:N", "step:Q", alt.Tooltip("drawdown_pct:Q", format=".2%")],
                )
            )
            st.altair_chart(dd_chart.interactive(), use_container_width=True)

        with risk_col_right:
            st.subheader(f"Rolling Risk Ratios (window={risk_window})")
            risk_df = pd.DataFrame(
                {
                    "date": chart_df["date"],
                    "step": chart_df["step"],
                    "Rolling Sharpe": rolling_sharpe,
                    "Rolling Sortino": rolling_sortino,
                }
            )
            risk_long = risk_df.melt(id_vars=["date", "step"], var_name="metric", value_name="value").dropna()
            if not risk_long.empty:
                risk_chart = (
                    alt.Chart(risk_long)
                    .mark_line()
                    .encode(
                        x=(x_field + ":T") if x_field == "date" else x_field + ":Q",
                        y=alt.Y("value:Q", title="Ratio"),
                        color=alt.Color("metric:N", scale=alt.Scale(domain=["Rolling Sharpe", "Rolling Sortino"], range=["#22d3ee", "#a78bfa"])),
                        tooltip=["metric:N", "date:T", alt.Tooltip("value:Q", format=".3f")]
                        if x_field == "date"
                        else ["metric:N", "step:Q", alt.Tooltip("value:Q", format=".3f")],
                    )
                )
                zero_rule = alt.Chart(pd.DataFrame({"zero": [0.0]})).mark_rule(color="#94a3b8", strokeDash=[3, 3]).encode(y="zero:Q")
                st.altair_chart((risk_chart + zero_rule).interactive(), use_container_width=True)
            else:
                st.info("Not enough rows for rolling risk metrics yet.")

    else:
        st.info("Press 'Refresh metrics' to run a quick simulation and view equity curve.")

    # Load history for the snapshot comparison table
    history_cache_buster = build_history_cache_buster(snapshot_dir=str(snapshot_dir), leaderboard_path=str(leaderboard_path))
    try:
        history = load_experiment_history(snapshot_dir=str(snapshot_dir), leaderboard_path=str(leaderboard_path), cache_buster=history_cache_buster)
    except Exception:
        history = pd.DataFrame()

    if "ticker" in history.columns:
        history = history[_ticker_match_mask(history["ticker"], ticker_key=ticker)].copy()

    best_runs = summarize_snapshot_bests(history) if not history.empty else pd.DataFrame()
    best = best_runs.iloc[0] if (not best_runs.empty) else {}

    best_visible_cols = [c for c in ["ticker", "horizon", "val_sharpe_ratio", "test_sharpe_ratio", "val_max_drawdown", "test_max_drawdown", "val_actionable_accuracy", "test_actionable_accuracy", "source_path"] if c in best_runs.columns]
    
    st.subheader("3) Historical Sweeps Performance")
    st.dataframe(best_runs[best_visible_cols], use_container_width=True)

    st.subheader("4) Interpretation")
    test_sharpe_val = float(best.get("test_sharpe_ratio", np.nan))
    if test_sharpe_val > 1.0:
        st.success("✅ At least one configuration is highly optimal, maintaining a forward test Sharpe Ratio above 1.0.")
    elif test_sharpe_val > 0.0:
        st.info("ℹ️ Performance is positive but modest. Consider tuning reward_turnover_penalty_scale to optimize signal selection.")
    else:
        st.warning("⚠️ Configurations have negative or sub-optimal forward Sharpe returns. Adjust exploration coefficients and timesteps to improve policy stability.")
