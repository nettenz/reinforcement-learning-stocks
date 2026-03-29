from __future__ import annotations

import argparse
import json
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

from src.experiments import (
    DEFAULT_LEADERBOARD_PATH,
    DEFAULT_REWARD_LEADERBOARD_PATH,
    DEFAULT_SUMMARY_PATH,
    run_experiments,
)
from src.signal_analytics import (
    ACTION_LABELS,
    compute_metrics,
    confusion_matrix,
    enrich_with_truth_labels,
    simulate_agent_signals,
)

ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_MODEL_PATH = ROOT_DIR / "models" / "ppo_trading_bot"
DEFAULT_DATA_PATH = ROOT_DIR / "data" / "tech_training_data.csv"
FALLBACK_DATA_PATH = ROOT_DIR / "data" / "mock_data.csv"


@st.cache_data(show_spinner=False)
def load_market_data(data_path: str) -> pd.DataFrame:
    path = Path(data_path)
    if not path.exists():
        raise FileNotFoundError(f"Data file not found: {path}")

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
) -> None:
    st.subheader("Price and agent actions")
    chart_df = enriched[
        [
            "step",
            "date",
            "price",
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
    chart_df["hover_label"] = chart_df.apply(
        lambda row: (
            f"{row['action_label']} @ {row['price']:.4f} | "
            f"true={row['true_label']} | {'correct' if bool(row['is_correct']) else 'wrong'}"
        ),
        axis=1,
    )

    base = alt.Chart(chart_df).encode(
        x=alt.X(x_field, title=x_title),
        y=alt.Y("price:Q", title="Price"),
    )
    line = base.mark_line(color="#7ecbff")

    signal_df = chart_df[chart_df["action_label"].isin([ACTION_LABELS[1], ACTION_LABELS[2]])].copy()
    label_stride = max(1, len(signal_df) // 40) if len(signal_df) else 1
    label_df = signal_df.iloc[::label_stride].copy()
    if len(signal_df):
        label_df = pd.concat([label_df, signal_df.tail(1)], ignore_index=True).drop_duplicates(subset=[x_key], keep="last")

    hover_signal = alt.selection_point(fields=[x_key], nearest=True, on="mouseover", empty=False, clear=False)
    signal_points = (
        alt.Chart(signal_df)
        .mark_circle(size=70)
        .encode(
            x=x_field,
            y="price:Q",
            color=alt.Color(
                "action_label:N",
                title="Signal",
                scale=alt.Scale(domain=[ACTION_LABELS[1], ACTION_LABELS[2]], range=["#2ecc71", "#e74c3c"]),
            ),
            tooltip=[
                tooltip_x,
                alt.Tooltip("price:Q", title="Price", format=".4f"),
                alt.Tooltip("action_label:N", title="Predicted"),
                alt.Tooltip("true_label:N", title="True"),
                alt.Tooltip("is_correct:N", title="Correct"),
                alt.Tooltip("cumulative_pnl:Q", title="Cumulative P&L", format=".2f"),
            ],
        )
        .add_params(hover_signal)
    )
    signal_labels = (
        alt.Chart(label_df)
        .mark_text(dy=-10, fontSize=10)
        .encode(
            x=x_field,
            y="price:Q",
            text="action_label:N",
            color=alt.Color(
                "action_label:N",
                legend=None,
                scale=alt.Scale(domain=[ACTION_LABELS[1], ACTION_LABELS[2]], range=["#2ecc71", "#e74c3c"]),
            ),
        )
    )

    layers: list[alt.Chart] = [line, signal_points, signal_labels]
    if len(signal_df):
        hover_rule = alt.Chart(signal_df).transform_filter(hover_signal).mark_rule(color="#9ca3af", strokeDash=[4, 4]).encode(x=x_field)
        hover_point = (
            alt.Chart(signal_df)
            .transform_filter(hover_signal)
            .mark_circle(size=170, stroke="white", strokeWidth=1.8)
            .encode(
                x=x_field,
                y="price:Q",
                color=alt.Color(
                    "action_label:N",
                    legend=None,
                    scale=alt.Scale(domain=[ACTION_LABELS[1], ACTION_LABELS[2]], range=["#2ecc71", "#e74c3c"]),
                ),
            )
        )
        hover_text = (
            alt.Chart(signal_df)
            .transform_filter(hover_signal)
            .mark_text(align="left", dx=10, dy=-12, fontSize=11, fontWeight="bold", color="#111827")
            .encode(
                x=x_field,
                y="price:Q",
                text="hover_label:N",
            )
        )
        layers.extend([hover_rule, hover_point, hover_text])

    if show_error_markers:
        error_df = chart_df[(chart_df["action_label"].isin([ACTION_LABELS[1], ACTION_LABELS[2]])) & (~chart_df["is_correct"])].copy()
        error_marks = (
            alt.Chart(error_df)
            .mark_point(shape="cross", size=140, color="#f7b6b2")
            .encode(
                x=x_field,
                y="price:Q",
                tooltip=[
                    tooltip_x,
                    alt.Tooltip("price:Q", title="Price", format=".4f"),
                    alt.Tooltip("action_label:N", title="Predicted"),
                    alt.Tooltip("true_label:N", title="True"),
                ],
            )
        )
        layers.append(error_marks)

    st.altair_chart(alt.layer(*layers).interactive(), width="stretch")
    if len(signal_df):
        st.caption("Tip: hover any Buy/Sell marker to pin the annotation; hover another marker to update it.")
    else:
        st.caption("No actionable Buy/Sell markers in the selected chart window.")

    pnl_chart = (
        alt.Chart(chart_df)
        .mark_line(color="#f39c12")
        .encode(
            x=alt.X(x_field, title=x_title),
            y=alt.Y("cumulative_pnl:Q", title="Cumulative P&L"),
            tooltip=[
                tooltip_x,
                alt.Tooltip("cumulative_pnl:Q", title="Cumulative P&L", format=".2f"),
                alt.Tooltip("net_worth:Q", title="Net worth", format=".2f"),
            ],
        )
    )
    st.altair_chart(pnl_chart.interactive(), width="stretch")

    if show_horizon_panel:
        horizon_chart = (
            alt.Chart(chart_df)
            .mark_bar(opacity=0.45)
            .encode(
                x=alt.X(x_field, title=x_title),
                y=alt.Y("horizon_return:Q", title="Horizon return"),
                color=alt.condition("datum.horizon_return >= 0", alt.value("#2ecc71"), alt.value("#e74c3c")),
                tooltip=[
                    tooltip_x,
                    alt.Tooltip("horizon_return:Q", title="Horizon return", format=".4%"),
                    alt.Tooltip("action_label:N", title="Predicted"),
                    alt.Tooltip("true_label:N", title="True"),
                ],
            )
        )
        st.altair_chart(horizon_chart.interactive(), width="stretch")

    display_time_col = "date" if has_valid_dates else "step"
    buy_points = chart_df[chart_df["action_label"] == ACTION_LABELS[1]][[display_time_col, "price"]].tail(20)
    sell_points = chart_df[chart_df["action_label"] == ACTION_LABELS[2]][[display_time_col, "price"]].tail(20)

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
    with st.sidebar:
        run = st.button("Run analytics", type="primary", width="stretch", key="run_signal_analytics")
        chart_window_rows = st.slider("Chart window (latest rows)", min_value=100, max_value=5000, value=1000, step=100)
        show_horizon_panel = st.toggle("Show horizon-return panel", value=True)
        show_error_markers = st.toggle("Highlight incorrect actionable signals", value=True)

    if not run:
        st.info("Set your inputs and click **Run analytics**.")
        return

    try:
        with st.spinner("Evaluating model signals..."):
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

    st.subheader("1) Price and Signals")
    render_charts(
        enriched_view,
        chart_window_rows=chart_window_rows,
        show_horizon_panel=show_horizon_panel,
        show_error_markers=show_error_markers,
    )

    st.subheader("2) Performance Summary")
    policy_label = "Deterministic (argmax)" if deterministic_policy else "Stochastic (sampled)"
    st.caption(f"Policy mode: **{policy_label}**")
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
    st.caption("Run multi-seed PPO sweeps and rank configurations on validation performance.")

    with st.sidebar:
        st.subheader("Experiment runner")
        include_news = st.checkbox("Include sentiment features", value=True)
        seeds = st.text_input("Seeds", value="7,13,21")
        timesteps = st.text_input("Timesteps", value="50000,100000")
        learning_rates = st.text_input("Learning rates", value="0.0003,0.0001")
        gammas = st.text_input("Gammas", value="0.99,0.995")
        ent_coefs = st.text_input("Entropy coeffs", value="0.0,0.01")
        threshold = st.number_input("Eval threshold", min_value=0.0, max_value=0.05, value=0.002, step=0.001)
        horizon = st.number_input("Eval horizon", min_value=1, max_value=10, value=1, step=1)
        transaction_cost_rate = st.number_input("Transaction cost rate", min_value=0.0, max_value=0.02, value=0.001, step=0.0005, format="%.4f")
        trade_penalty = st.number_input("Trade penalty", min_value=0.0, max_value=1.0, value=0.05, step=0.01)
        reward_return_scale = st.number_input("Reward: portfolio-return scale", min_value=0.0, max_value=5.0, value=1.0, step=0.05)
        reward_direction_scale = st.number_input("Reward: directional scale", min_value=0.0, max_value=5.0, value=0.35, step=0.05)
        reward_hold_penalty_scale = st.number_input("Reward: hold penalty scale", min_value=0.0, max_value=5.0, value=0.05, step=0.01)
        reward_drawdown_penalty_scale = st.number_input("Reward: drawdown penalty scale", min_value=0.0, max_value=5.0, value=0.10, step=0.01)
        reward_clip = st.number_input("Reward clip (+/-)", min_value=0.01, max_value=10.0, value=1.0, step=0.05)
        reward_ignore_transaction_cost = st.checkbox("Ignore transaction cost in reward", value=True)
        max_runs = st.number_input("Max runs (0=all)", min_value=0, max_value=200, value=10, step=1)
        run_experiment = st.button("Run experiments", type="primary", width="stretch", key="run_experiments")

    leaderboard_path = DEFAULT_LEADERBOARD_PATH
    reward_leaderboard_path = DEFAULT_REWARD_LEADERBOARD_PATH
    summary_path = DEFAULT_SUMMARY_PATH

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
            reward_clip=float(reward_clip),
            reward_ignore_transaction_cost=bool(reward_ignore_transaction_cost),
            max_runs=int(max_runs),
            leaderboard_path=str(leaderboard_path),
            reward_leaderboard_path=str(reward_leaderboard_path),
            summary_path=str(summary_path),
        )
        with st.spinner("Running experiments..."):
            leaderboard = run_experiments(args)
            leaderboard_path.parent.mkdir(parents=True, exist_ok=True)
            reward_leaderboard_path.parent.mkdir(parents=True, exist_ok=True)
            summary_path.parent.mkdir(parents=True, exist_ok=True)
            leaderboard.to_csv(leaderboard_path, index=False)
            reward_leaderboard = leaderboard.sort_values("val_reward_total_mean", ascending=False).reset_index(drop=True)
            reward_leaderboard.to_csv(reward_leaderboard_path, index=False)
            summary = {
                "rows": int(len(leaderboard)),
                "leaderboard_path": str(leaderboard_path),
                "reward_leaderboard_path": str(reward_leaderboard_path),
                "top3": leaderboard.head(3).to_dict(orient="records"),
            }
            summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
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

    if reward_leaderboard_path.exists():
        reward_leaderboard = pd.read_csv(reward_leaderboard_path)
        st.subheader("3) Reward Leaderboard")
        st.dataframe(reward_leaderboard, width="stretch")
        if len(reward_leaderboard):
            st.subheader("4) Best Reward Snapshot")
            best_reward = reward_leaderboard.iloc[0]
            r1, r2, r3 = st.columns(3)
            r1.metric("Best val reward mean", f"{best_reward['val_reward_total_mean']:.5f}")
            r2.metric("Best val direction reward", f"{best_reward['val_reward_direction_mean']:.5f}")
            r3.metric("Best val drawdown", f"{best_reward['val_reward_drawdown_mean']:.5f}")

    if summary_path.exists():
        st.subheader("5) Summary JSON")
        st.code(summary_path.read_text(encoding="utf-8"), language="json")


def main() -> None:
    st.set_page_config(page_title="RL Signal Analytics Dashboard", layout="wide")
    st.title("RL Buy/Sell Signal Analytics")
    st.write("Analyze signal quality and run aggressive hyperparameter experiments.")

    default_data = DEFAULT_DATA_PATH if DEFAULT_DATA_PATH.exists() else FALLBACK_DATA_PATH
    with st.sidebar:
        st.header("Global inputs")
        page = st.radio("Section", options=["Signal Analytics", "Experiments"], index=0)
        data_path = st.text_input("Data CSV path", value=str(default_data))
        model_path = st.text_input("Model path (.zip optional)", value=str(DEFAULT_MODEL_PATH))
        threshold = st.slider("Movement threshold", min_value=0.0, max_value=0.05, value=0.002, step=0.001)
        horizon_steps = st.slider("Prediction horizon (steps)", min_value=1, max_value=10, value=1, step=1)
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

    render_experiments_page()


if __name__ == "__main__":
    main()
