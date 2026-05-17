from __future__ import annotations

import pandas as pd
import numpy as np
import altair as alt
import streamlit as st

from src.signal_analytics import ACTION_LABELS


def render_roc_curves(enriched: pd.DataFrame) -> None:
    """Renders multi-class ROC curves using Model Skill (confidence) or Oracle (returns)."""
    try:
        from sklearn.metrics import roc_curve, auc
    except ImportError:
        st.warning("scikit-learn required for ROC curves")
        return

    has_confidence = "confidence" in enriched.columns
    
    if has_confidence:
        scores = {
            ACTION_LABELS[1]: np.where(enriched["action"] == 1, enriched["confidence"], 0.0),
            ACTION_LABELS[2]: np.where(enriched["action"] == 2, enriched["confidence"], 0.0),
            ACTION_LABELS[0]: np.where(enriched["action"] == 0, enriched["confidence"], 0.0)
        }
        title_prefix = "Model Skill"
    else:
        scores = {
            ACTION_LABELS[1]: enriched["horizon_return"],
            ACTION_LABELS[2]: -enriched["horizon_return"],
            ACTION_LABELS[0]: -(enriched["horizon_return"].abs())
        }
        title_prefix = "Theoretical Oracle"
    
    roc_data = []
    labels_with_auc = []
    actual_colors = []
    color_map = {
        ACTION_LABELS[0]: "#94a3b8",
        ACTION_LABELS[1]: "#10b981",
        ACTION_LABELS[2]: "#ef4444"
    }

    for k in range(3):
        label = ACTION_LABELS[k]
        y_true = (enriched["true_signal"] == k).astype(int)
        score = scores[label]
        
        if len(np.unique(y_true)) < 2:
            continue
            
        fpr, tpr, _ = roc_curve(y_true, score)
        roc_auc = auc(fpr, tpr)
        
        legend_label = f"{label} (AUC={roc_auc:.2f})"
        labels_with_auc.append(legend_label)
        actual_colors.append(color_map[label])
        
        df = pd.DataFrame({
            "fpr": fpr,
            "tpr": tpr,
            "class_label": legend_label
        })
        roc_data.append(df)
        
    if not roc_data:
        st.info("Insufficient signal diversity to compute ROC curves.")
        return
        
    roc_df = pd.concat(roc_data)
    
    line_chart = alt.Chart(roc_df).mark_line(strokeWidth=2.5).encode(
        x=alt.X("fpr:Q", title="False Positive Rate", axis=alt.Axis(format=".0%")),
        y=alt.Y("tpr:Q", title="True Positive Rate", axis=alt.Axis(format=".0%")),
        color=alt.Color(
            "class_label:N", 
            title="Class",
            scale=alt.Scale(
                domain=labels_with_auc,
                range=actual_colors
            )
        ),
        tooltip=[
            alt.Tooltip("class_label:N", title="Class"),
            alt.Tooltip("fpr:Q", title="FPR", format=".1%"),
            alt.Tooltip("tpr:Q", title="TPR", format=".1%")
        ]
    )
    
    diagonal = alt.Chart(pd.DataFrame({"x": [0, 1], "y": [0, 1]})).mark_line(
        color="#9ca3af", strokeDash=[4, 4], opacity=0.5
    ).encode(x="x:Q", y="y:Q")
    
    chart = (line_chart + diagonal).properties(
        title=f"One-vs-Rest ROC Curves ({title_prefix})",
        height=300
    )
    st.altair_chart(chart, use_container_width=True)


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
    
    hover_signal = alt.selection_point(name="hover_signal", fields=[x_key], nearest=True, on="mouseover", empty=False, clear=False)
    
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
    error_marks = None
    if show_error_markers:
        error_df = chart_df[(chart_df["action_label"].isin([ACTION_LABELS[1], ACTION_LABELS[2]])) & (~chart_df["is_correct"])].copy()
        if not error_df.empty:
            error_df["error_y"] = error_df.apply(lambda r: r["price"] * 1.025 if r["action_label"] == ACTION_LABELS[2] else r["price"] * 0.975, axis=1)
            error_marks = (
                alt.Chart(error_df)
                .mark_point(shape="x", size=110, opacity=1.0, strokeWidth=2.5, color="#f43f5e")
                .encode(x=x_field, y="error_y:Q")
            )

    # Layer and stack
    layer_components = [background_zones, price_area, line, signal_points]
    if error_marks is not None:
        layer_components.append(error_marks)

    if show_signal_labels and not signal_df.empty:
        label_step = max(1, len(signal_df) // max(1, signal_label_budget))
        label_df = signal_df.iloc[::label_step].copy()
        label_df["signal_text"] = label_df["action_label"].apply(
            lambda a: "B" if a == ACTION_LABELS[1] else "S"
        )
        signal_label_layer = (
            alt.Chart(label_df)
            .mark_text(dy=-14, fontSize=10, fontWeight="bold")
            .encode(
                x=x_field,
                y="price:Q",
                text="signal_text:N",
                color=alt.Color(
                    "action_label:N",
                    scale=alt.Scale(
                        domain=[ACTION_LABELS[1], ACTION_LABELS[2]],
                        range=["#059669", "#dc2626"],
                    ),
                    legend=None,
                ),
            )
        )
        layer_components.append(signal_label_layer)

    price_main = (
        alt.layer(*layer_components)
        .properties(height=350, width="container")
        .resolve_scale(color='independent')
    )

    # Combined dashboard with VConcat
    combined = alt.vconcat(price_main, volume_chart).resolve_scale(x='shared').configure_view(stroke=None)

    # Keep y-scales stable while allowing horizontal zoom/pan
    st.altair_chart(combined.interactive(bind_y=False), use_container_width=True)
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
    ).properties(height=420, width="container")
    st.altair_chart(pnl_chart.interactive(), use_container_width=True)

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
        st.altair_chart(horizon_chart.interactive(), use_container_width=True)

    # Display recent signal lists
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
            st.dataframe(buy_points, use_container_width=True)
    with sell_col:
        st.write("Recent Sell signals")
        if sell_points.empty:
            st.info("No Sell signals were produced for this run.")
        else:
            st.dataframe(sell_points, use_container_width=True)
