from __future__ import annotations

import pandas as pd
import altair as alt
import streamlit as st

from src.dashboard.config import (
    DEFAULT_TICKER,
    DEFAULT_ACTIONABLE_TARGET,
    PROMOTION_GATE_DEFAULTS,
)
from src.dashboard.model_utils import _artifact_paths_for_interval
from src.dashboard.leaderboard import (
    build_history_cache_buster,
    load_experiment_history,
    _latest_comparable_leaderboard,
    _ticker_match_mask,
)
from src.dashboard.analytics import (
    _evaluate_promotion_gates,
    summarize_snapshot_bests,
    build_experiment_interpretation,
    build_next_step_recommendations,
)
from src.dashboard.components.gates import (
    render_promotion_gate_cards,
    render_trade_rate_histogram,
)


def render_experiment_insights_page(ticker: str = DEFAULT_TICKER, interval: str = "1d") -> None:
    st.header("Experiment Insights")
    st.caption("Visualize snapshot history and generate next experiment commands to improve actionable accuracy.")

    leaderboard_path, _, _, snapshot_dir = _artifact_paths_for_interval(interval)

    with st.sidebar:
        st.subheader("Insights controls")
        target_actionable = st.slider(
            "Target actionable accuracy",
            min_value=0.40,
            max_value=0.80,
            value=DEFAULT_ACTIONABLE_TARGET,
            step=0.01,
        )
        recommendation_seeds = st.text_input("Recommendation seeds", value="3,7,13,21,42")

    history_cache_buster = build_history_cache_buster(snapshot_dir=str(snapshot_dir), leaderboard_path=str(leaderboard_path))
    history = load_experiment_history(
        snapshot_dir=str(snapshot_dir),
        leaderboard_path=str(leaderboard_path),
        cache_buster=history_cache_buster,
    )
    if "ticker" in history.columns:
        history = history[_ticker_match_mask(history["ticker"], ticker_key=ticker)].copy()
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
    st.altair_chart((trend_chart + target_rule).interactive(), use_container_width=True)

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
    st.altair_chart(stability_chart.interactive(), use_container_width=True)

    st.subheader("3) Generalization Scatter (Val vs Test)")
    st.caption("Visualizing drift between validation and test performance across all snapshots.")

    gen_scatter_df = bests.copy()
    if "val_actionable_accuracy" in gen_scatter_df.columns and "test_actionable_accuracy" in gen_scatter_df.columns:
        gen_scatter = (
            alt.Chart(gen_scatter_df)
            .mark_circle(size=100, opacity=0.7, stroke="white", strokeWidth=0.5)
            .encode(
                x=alt.X("val_actionable_accuracy:Q", title="Val Actionable Accuracy", scale=alt.Scale(domain=[0.4, 0.7])),
                y=alt.Y("test_actionable_accuracy:Q", title="Test Actionable Accuracy", scale=alt.Scale(domain=[0.4, 0.7])),
                color=alt.Color("snapshot_label:N", title="Snapshot"),
                size=alt.Size("ranking_score:Q", title="Ranking Score"),
                tooltip=[
                    alt.Tooltip("snapshot_time:T", title="Time"),
                    alt.Tooltip("snapshot_label:N", title="Label"),
                    alt.Tooltip("val_actionable_accuracy:Q", title="Val Acc", format=".4f"),
                    alt.Tooltip("test_actionable_accuracy:Q", title="Test Acc", format=".4f"),
                    alt.Tooltip("ranking_score:Q", title="Score", format=".4f"),
                ],
            )
        )

        identity_line = (
            alt.Chart(pd.DataFrame({"x": [0, 1], "y": [0, 1]}))
            .mark_line(color="#94a3b8", strokeDash=[5, 5], opacity=0.5)
            .encode(x="x:Q", y="y:Q")
        )

        st.altair_chart((gen_scatter + identity_line).interactive(), use_container_width=True)
    else:
        st.info("Insufficient data for generalization scatter.")

    st.subheader("4) Recent Best Configs")
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
        "reward_action_bonus_scale",
        "reward_turnover_penalty_scale",
        "val_actionable_accuracy",
        "test_actionable_accuracy",
        "val_trade_rate",
        "test_trade_rate",
        "ranking_score",
    ]
    visible_cols = [c for c in display_cols if c in bests.columns]
    st.dataframe(bests[visible_cols].sort_values("snapshot_time", ascending=False), use_container_width=True)

    st.subheader("5) Model Interpretation")
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

    st.subheader("6) Recommended Next Steps")
    recs = build_next_step_recommendations(
        history=history,
        target=target_actionable,
        seeds=recommendation_seeds,
        ticker=ticker,
    )
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
