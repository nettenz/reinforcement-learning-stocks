from __future__ import annotations

import pandas as pd
import numpy as np
import altair as alt
import streamlit as st

from src.dashboard.config import PROMOTION_GATE_DEFAULTS


def render_trade_rate_histogram(leaderboard: pd.DataFrame, run_label: str = "") -> None:
    """Render histogram of test_trade_rate with Gate 6 band overlay.
    
    Gate 6 (test_trade_rate) passes if value is in [0.40, 0.80].
    """
    if "test_trade_rate" not in leaderboard.columns:
        st.warning("test_trade_rate column not found in leaderboard.")
        return

    trade_rates = leaderboard["test_trade_rate"].dropna()
    if len(trade_rates) == 0:
        st.info("No test_trade_rate data available.")
        return

    gate_min = PROMOTION_GATE_DEFAULTS["test_trade_rate_min"]
    gate_max = PROMOTION_GATE_DEFAULTS["test_trade_rate_max"]

    in_zone = (trade_rates >= gate_min) & (trade_rates <= gate_max)
    count_pass = int(in_zone.sum())
    count_total = len(trade_rates)

    df = pd.DataFrame({
        "test_trade_rate": trade_rates.values,
        "in_zone": in_zone.values
    })

    histogram = (
        alt.Chart(df)
        .mark_bar(opacity=0.7)
        .encode(
            x=alt.X("test_trade_rate:Q", title="Test Trade Rate", bin=alt.Bin(step=0.05)),
            y=alt.Y("count():Q", title="Config Count"),
            color=alt.Color(
                "in_zone:N",
                scale=alt.Scale(domain=[False, True], range=["#ef4444", "#10b981"]),
                legend=alt.Legend(title="Gate 6 Zone", labelExpr="datum.value == 'true' ? 'Pass (0.40-0.80)' : 'Fail (outside)'")
            ),
            tooltip=[
                alt.Tooltip("test_trade_rate:Q", title="Trade Rate", format=".3f"),
                alt.Tooltip("count():Q", title="Count")
            ]
        )
    )

    lower_rule = alt.Chart(pd.DataFrame({"x": [gate_min]})).mark_rule(
        color="#10b981", strokeDash=[2, 2], size=2
    ).encode(x="x:Q")

    upper_rule = alt.Chart(pd.DataFrame({"x": [gate_max]})).mark_rule(
        color="#10b981", strokeDash=[2, 2], size=2
    ).encode(x="x:Q")

    title = f"Trade Rate Distribution: {count_pass} / {count_total} in healthy zone"
    if run_label:
        title += f" (run: {run_label})"

    chart = (histogram + lower_rule + upper_rule).properties(
        title=title,
        height=300
    )

    st.altair_chart(chart, use_container_width=True)


def render_promotion_gate_cards(gate_eval: dict[str, object]) -> None:
    """Render 6 promotion gate status cards with threshold awareness.
    
    Each card shows gate name, current value, threshold, and color-coded PASS/FAIL state.
    """
    gate_values = gate_eval["values"]
    gate_checks = gate_eval["checks"]
    is_relaxed = gate_eval.get("is_relaxed", False)
    
    gate_6_threshold_str = "0.40 - 1.00 (Waiver)" if is_relaxed else f"{PROMOTION_GATE_DEFAULTS['test_trade_rate_min']:.0%} - {PROMOTION_GATE_DEFAULTS['test_trade_rate_max']:.0%}"

    gates_info = [
        {
            "name": "Gate 1: Test Accuracy",
            "value": gate_values["test_actionable"],
            "format": ".1%",
            "threshold": f">= {PROMOTION_GATE_DEFAULTS['min_test_actionable']:.1%}",
            "key": "test_actionable",
        },
        {
            "name": "Gate 2: Win Rate",
            "value": gate_values["test_win_rate"],
            "format": ".1%",
            "threshold": f">= {PROMOTION_GATE_DEFAULTS['min_test_win_rate']:.1%}",
            "key": "test_win_rate",
        },
        {
            "name": "Gate 3: Alpha",
            "value": gate_values["test_alpha"],
            "format": ".4f",
            "threshold": f">= {PROMOTION_GATE_DEFAULTS['min_test_alpha']:.4f}",
            "key": "test_alpha",
        },
        {
            "name": "Gate 4: Val-Test Gap",
            "value": gate_values["val_test_gap"],
            "format": ".1%",
            "threshold": f"<= {PROMOTION_GATE_DEFAULTS['max_val_test_gap']:.1%}",
            "key": "val_test_gap",
        },
        {
            "name": "Gate 5: Config CV",
            "value": gate_values["test_cv"],
            "format": ".2f",
            "threshold": f"< {PROMOTION_GATE_DEFAULTS['max_test_cv']:.2f}",
            "key": "test_cv",
        },
        {
            "name": "Gate 6: Trade Rate",
            "value": gate_values["test_trade_rate"],
            "format": ".1%",
            "threshold": gate_6_threshold_str,
            "key": "test_trade_rate",
        },
    ]
    
    cols = st.columns(3)
    for idx, gate in enumerate(gates_info):
        col = cols[idx % 3]
        is_pass = gate_checks.get(gate["key"], False)
        status_color = "#10b981" if is_pass else "#ef4444"
        status_text = "✔ PASS" if is_pass else "✘ FAIL"
        
        with col:
            st.markdown(
                f"""
                <div style="border: 2px solid {status_color}; border-radius: 8px; padding: 16px; margin-bottom: 16px; background-color: {'rgba(16,185,129,0.05)' if is_pass else 'rgba(239,68,68,0.05)'};">
                    <div style="font-weight: bold; color: #1f2937; margin-bottom: 8px;">{gate['name']}</div>
                    <div style="font-size: 24px; font-weight: bold; color: {status_color}; margin-bottom: 4px;">
                        {format(gate["value"], gate["format"]) if isinstance(gate["value"], (int, float)) and not np.isnan(gate["value"]) and np.isfinite(gate["value"]) else "N/A"}
                    </div>
                    <div style="font-size: 12px; color: #6b7280;">
                        Threshold: {gate["threshold"]}
                    </div>
                    <div style="font-size: 12px; font-weight: bold; color: {status_color}; margin-top: 8px;">
                        {status_text}
                    </div>
                </div>
                """,
                unsafe_allow_html=True
            )
