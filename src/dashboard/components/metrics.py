from __future__ import annotations

import pandas as pd
import numpy as np
import altair as alt
import streamlit as st

from src.dashboard.analytics import compute_pnl_summary
from src.signal_analytics import ACTION_LABELS, compute_metrics


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


def render_confusion_heatmap(conf: pd.DataFrame) -> None:
    """Renders a normalized confusion matrix as an Altair heatmap."""
    conf_melted = conf.reset_index().melt(id_vars="True", var_name="Predicted", value_name="count")
    
    # Normalize by row (True class) to show Recall distribution
    conf_melted["row_total"] = conf_melted.groupby("True")["count"].transform("sum")
    conf_melted["percentage"] = (conf_melted["count"] / conf_melted["row_total"]).fillna(0)
    
    # Label: count (percentage)
    conf_melted["label"] = conf_melted.apply(
        lambda r: f"{int(r['count'])}\n({r['percentage']:.0%})" if r["row_total"] > 0 else "0", 
        axis=1
    )
    
    sort_order = [ACTION_LABELS[0], ACTION_LABELS[1], ACTION_LABELS[2]]
    base = alt.Chart(conf_melted).encode(
        x=alt.X("Predicted:N", sort=sort_order, title="Predicted Action"),
        y=alt.Y("True:N", sort=sort_order, title="True Signal")
    )
    
    heatmap = base.mark_rect().encode(
        color=alt.Color(
            "percentage:Q", 
            scale=alt.Scale(scheme="blues"), 
            legend=alt.Legend(title="Recall %", format=".0%")
        ),
        tooltip=[
            "True:N", 
            "Predicted:N", 
            alt.Tooltip("count:Q", title="Absolute Count"),
            alt.Tooltip("percentage:Q", title="Recall %", format=".1%")
        ]
    )
    
    text = base.mark_text(fontSize=13, fontWeight="bold", lineBreak="\n").encode(
        text="label:N",
        color=alt.condition(
            alt.datum.percentage > 0.5,
            alt.value("white"),
            alt.value("black")
        )
    )
    
    chart = (heatmap + text).properties(
        title="Normalized Confusion Matrix (Recall)",
        height=300
    )
    st.altair_chart(chart, use_container_width=True)


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
