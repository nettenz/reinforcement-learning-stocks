from __future__ import annotations

import pandas as pd
import altair as alt
import streamlit as st

from src.dashboard.config import (
    ROOT_DIR,
    RECOMMENDED_THRESHOLD,
    RECOMMENDED_HORIZON,
    RECOMMENDED_CHART_WINDOW,
)
from src.dashboard.model_utils import (
    _validate_model_shape,
)
from src.dashboard.data_utils import (
    load_market_data,
    evaluate_signals,
    _apply_split_filter,
)
from src.dashboard.analytics import (
    add_cumulative_pnl,
    build_action_mix_table,
)
from src.dashboard.components.charts import render_charts, render_roc_curves
from src.dashboard.components.metrics import (
    render_metrics,
    render_theoretical_headroom,
    render_confusion_heatmap,
)
from src.dashboard.components.ensemble import display_ensemble_config
from src.signal_analytics import ACTION_LABELS, confusion_matrix


def render_signal_analytics_page(
    ticker: str,
    data_path: str,
    model_path: str,
    threshold: float,
    horizon_steps: int,
    deterministic_policy: bool,
) -> None:
    st.header(f"Signal Analytics - {ticker.upper()}")
    st.caption("Evaluate one trained policy or the multi-seed ensemble against forward-move truth labels.")
    st.info(
        "Recommended dashboard settings: "
        f"threshold={RECOMMENDED_THRESHOLD:.4f}, horizon={RECOMMENDED_HORIZON}, "
        f"chart window={RECOMMENDED_CHART_WINDOW} rows."
    )
    
    with st.sidebar:
        st.subheader("Simulation Controls")
        
        is_sac = "sac" in model_path.lower()
        
        use_ensemble = st.toggle(
            "Use Ensemble", 
            value=False,
            help="Evaluate the top seeds ensemble defined in staging/models/ensemble_config.json."
        )
        
        binary_actions = False
        if not use_ensemble:
            binary_actions = st.checkbox(
                "Binary Actions (SAC)", 
                value=is_sac,
                help="If enabled, policy output > 0.0 is mapped to Buy (1.0). Matches Fork B training."
            )
            
        data_split = st.selectbox(
            "Data Split",
            options=["Full", "Train", "Val", "Test"],
            index=3, # Default to Test for historical validation
            help="70/15/15 split. Select 'Test' to see historical forward-look results."
        )

        # Audit P1 Fix: Ticker-specific min-hold-bars defaults
        # NVDA = 1, AMD = 3, MU = 1, GOOGL = 3, AMZN = 3
        t_lower = ticker.lower()
        if "googl" in t_lower or "amzn" in t_lower or "amd" in t_lower:
            default_sim_hold = 3
        elif "nvda" in t_lower or "mu" in t_lower:
            default_sim_hold = 1
        else:
            default_sim_hold = 0

        min_sim_hold = st.number_input(
            "Min Hold Bars (Sim)", 
            min_value=0, 
            max_value=20, 
            value=default_sim_hold,
            help="Enforces a minimum holding period in the simulation. Automatically synchronized for PPO."
        )
        
        run = st.button("Run analytics", type="primary", use_container_width=True, key="run_signal_analytics")
        
        st.divider()
        st.subheader("Display Controls")
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
        if use_ensemble:
            st.divider()
            ensemble_config_path = str(ROOT_DIR / "staging" / "models" / "ensemble_config.json")
            display_ensemble_config(ticker, ensemble_config_path)
        return

    try:
        with st.spinner("⏳ Running agent simulation..."):
            df_full = load_market_data(data_path)
            df_split = _apply_split_filter(df_full, data_split)

            if not use_ensemble:
                _validate_model_shape(model_path, df_split)

            ensemble_config_path = str(ROOT_DIR / "staging" / "models" / "ensemble_config.json")

            enriched, conf = evaluate_signals(
                data_path=data_path,
                model_path=model_path,
                threshold=threshold,
                horizon_steps=horizon_steps,
                deterministic_policy=deterministic_policy,
                binary_actions=binary_actions,
                min_hold_bars=min_sim_hold,
                use_ensemble=use_ensemble,
                ticker=ticker,
                ensemble_config_path=ensemble_config_path,
            )
            
            enriched = _apply_split_filter(enriched, data_split)
            conf = confusion_matrix(enriched)

    except (FileNotFoundError, ValueError) as exc:
        st.error(str(exc))
        st.stop()

    enriched_view = add_cumulative_pnl(enriched)

    if use_ensemble:
        ensemble_config_path = str(ROOT_DIR / "staging" / "models" / "ensemble_config.json")
        display_ensemble_config(ticker, ensemble_config_path)
        st.divider()

    st.markdown(f"### 📊 Performance Summary - {data_split} Split")
    if use_ensemble:
        st.caption("🚀 **Ensemble Mode Active** (Top seed voting)")
    
    m1, m2, m3, m4 = st.columns(4)
    acc = float(enriched_view["is_correct"].mean())
    actionable_df = enriched_view[enriched_view["action_label"].isin([ACTION_LABELS[1], ACTION_LABELS[2]])]
    act_acc = float(actionable_df["is_correct"].mean()) if not actionable_df.empty else 0.0
    total_pnl = float(enriched_view["cumulative_pnl"].iloc[-1]) if not enriched_view.empty else 0.0
    
    net_worth_series = enriched_view["net_worth"]
    max_dd = float((net_worth_series / net_worth_series.cummax() - 1).min()) if not net_worth_series.empty else 0.0

    m1.metric("Overall Accuracy", f"{acc:.1%}", help="Percentage of correctly predicted high-conviction moves.")
    m2.metric("Actionable Accuracy", f"{act_acc:.1%}", delta=f"{act_acc - 0.5:.1%}" if act_acc > 0 else None, help="Accuracy on Buy/Sell signals only (ignores Hold).")
    m3.metric("Total P&L", f"${total_pnl:.2f}", help="Cumulative profit/loss over the evaluated period.")
    m4.metric("Max Drawdown", f"{max_dd:.1%}", delta_color="inverse", help="Deepest peak-to-trough drop in net worth.")

    if use_ensemble and "confidence" in enriched_view.columns:
        st.markdown("---")
        c1, c2, c3 = st.columns(3)
        avg_conf = enriched_view["confidence"].mean()
        high_conf_rate = (enriched_view["confidence"] >= 1.0 - 1e-9).mean()
        majority_rate = (enriched_view["confidence"] > 0.5).mean()
        
        c1.metric("Avg Confidence", f"{avg_conf:.1%}")
        c2.metric("Majority Agreement", f"{majority_rate:.1%}")
        c3.metric("Unanimous Rate", f"{high_conf_rate:.1%}")

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
    col1, col2 = st.columns([1, 1])
    with col1:
        render_confusion_heatmap(conf)
    with col2:
        render_roc_curves(enriched_view)

    st.subheader("5) Action Mix and P&L")
    st.write("Action distribution and P&L contribution by action")
    action_distribution = build_action_mix_table(enriched_view)
    st.dataframe(action_distribution, use_container_width=True)

    st.subheader("6) Signal Quality Diagnostics")
    st.caption("Visualizing the relationship between market returns and agent rewards/confidence.")

    scatter_df = enriched_view.copy()
    if len(scatter_df) > 5000:
        scatter_df = scatter_df.sample(5000).sort_values("step")
        st.caption("Note: Chart is sampled to 5,000 points for performance.")

    y_field = "reward:Q"
    y_title = "Reward"
    size_field = alt.value(60)
    size_title = ""

    if "confidence" in scatter_df.columns:
        has_conf = True
        size_field = "confidence:Q"
        size_title = "Ensemble Confidence"
    else:
        has_conf = False

    scatter = (
        alt.Chart(scatter_df)
        .mark_circle(opacity=0.6, stroke="white", strokeWidth=0.5)
        .encode(
            x=alt.X("horizon_return:Q", title=f"Horizon Return ({horizon_steps} steps)", axis=alt.Axis(format=".1%")),
            y=alt.Y(y_field, title=y_title),
            color=alt.Color(
                "action_label:N",
                title="Action",
                scale=alt.Scale(
                    domain=[ACTION_LABELS[0], ACTION_LABELS[1], ACTION_LABELS[2]],
                    range=["#94a3b8", "#10b981", "#ef4444"],
                ),
            ),
            size=alt.Size(size_field, title=size_title) if has_conf else size_field,
            tooltip=[
                "step:Q",
                "date:T",
                alt.Tooltip("price:Q", format=".2f"),
                alt.Tooltip("horizon_return:Q", format=".2%"),
                alt.Tooltip("reward:Q", format=".4f"),
                "action_label:N",
                "true_label:N",
                "is_correct:N",
            ],
        )
    )

    vline = alt.Chart(pd.DataFrame({"x": [0]})).mark_rule(color="#94a3b8", strokeDash=[4, 4]).encode(x="x:Q")
    hline = alt.Chart(pd.DataFrame({"y": [0]})).mark_rule(color="#94a3b8", strokeDash=[4, 4]).encode(y="y:Q")

    st.altair_chart((scatter + vline + hline).interactive(), use_container_width=True)

    st.subheader("7) Detailed Signal Log")
    log_cols = [
        "step", "date", "price", "action_label", "true_label",
        "reward", "net_worth", "cumulative_pnl", "horizon_return", "trade_edge", "is_correct"
    ]
    if "confidence" in enriched_view.columns:
        log_cols.insert(4, "confidence")

    st.dataframe(enriched_view[log_cols], use_container_width=True)
