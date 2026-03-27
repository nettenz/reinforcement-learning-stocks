from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd
import streamlit as st

from src.experiments import DEFAULT_LEADERBOARD_PATH, DEFAULT_SUMMARY_PATH, run_experiments
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
) -> tuple[pd.DataFrame, pd.DataFrame]:
    df = load_market_data(data_path)
    signals = simulate_agent_signals(df=df, model_path=model_path)
    enriched = enrich_with_truth_labels(signals, threshold=threshold, horizon_steps=horizon_steps)
    conf = confusion_matrix(enriched)
    return enriched, conf


def render_metrics(enriched: pd.DataFrame) -> None:
    metrics = compute_metrics(enriched)
    col1, col2, col3 = st.columns(3)
    col1.metric("Overall Accuracy", f"{metrics.overall_accuracy * 100:.2f}%")
    col2.metric("Actionable Accuracy", f"{metrics.actionable_accuracy * 100:.2f}%")
    col3.metric("Trade Win Rate", f"{metrics.trade_win_rate * 100:.2f}%")

    col4, col5, col6 = st.columns(3)
    col4.metric("Buy Precision / Recall", f"{metrics.buy_precision:.2f} / {metrics.buy_recall:.2f}")
    col5.metric("Sell Precision / Recall", f"{metrics.sell_precision:.2f} / {metrics.sell_recall:.2f}")
    col6.metric("Signal Cumulative Return", f"{metrics.cumulative_signal_return * 100:.2f}%")

    st.caption(f"Average trade edge: {metrics.mean_trade_edge * 100:.3f}% per signal.")


def render_charts(enriched: pd.DataFrame) -> None:
    st.subheader("Price and agent actions")
    chart_df = enriched[["date", "price", "action_label"]].copy()
    if "date" not in chart_df.columns or chart_df["date"].isna().all():
        chart_df["date"] = chart_df["step"]
    chart_df = chart_df.set_index("date")

    st.line_chart(chart_df["price"])

    buy_points = chart_df[chart_df["action_label"] == ACTION_LABELS[1]][["price"]]
    sell_points = chart_df[chart_df["action_label"] == ACTION_LABELS[2]][["price"]]

    buy_col, sell_col = st.columns(2)
    with buy_col:
        st.write("Recent Buy signals")
        st.dataframe(buy_points.tail(20), use_container_width=True)
    with sell_col:
        st.write("Recent Sell signals")
        st.dataframe(sell_points.tail(20), use_container_width=True)


def render_signal_analytics_page(
    data_path: str,
    model_path: str,
    threshold: float,
    horizon_steps: int,
) -> None:
    st.header("Signal Analytics")
    st.caption("Evaluate one trained policy against forward-move labels.")
    with st.sidebar:
        run = st.button("Run analytics", type="primary", use_container_width=True, key="run_signal_analytics")

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
            )
    except (FileNotFoundError, ValueError) as exc:
        st.error(str(exc))
        st.stop()

    st.subheader("1) Performance Summary")
    render_metrics(enriched)

    st.subheader("2) Classification Quality")
    st.subheader("Confusion matrix (true signal vs predicted action)")
    st.dataframe(conf, use_container_width=True)

    st.subheader("3) Action Mix")
    st.write("Action distribution")
    action_distribution = enriched["action_label"].value_counts().rename_axis("action").reset_index(name="count")
    st.dataframe(action_distribution, use_container_width=True)

    st.subheader("4) Price and Signals")
    render_charts(enriched)

    st.subheader("5) Detailed Signal Log")
    st.dataframe(
        enriched[
            [
                "step",
                "date",
                "price",
                "action_label",
                "true_label",
                "horizon_return",
                "trade_edge",
                "is_correct",
            ]
        ],
        use_container_width=True,
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
        max_runs = st.number_input("Max runs (0=all)", min_value=0, max_value=200, value=10, step=1)
        run_experiment = st.button("Run experiments", type="primary", use_container_width=True, key="run_experiments")

    leaderboard_path = DEFAULT_LEADERBOARD_PATH
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
            max_runs=int(max_runs),
            leaderboard_path=str(leaderboard_path),
            summary_path=str(summary_path),
        )
        with st.spinner("Running experiments..."):
            leaderboard = run_experiments(args)
            leaderboard_path.parent.mkdir(parents=True, exist_ok=True)
            summary_path.parent.mkdir(parents=True, exist_ok=True)
            leaderboard.to_csv(leaderboard_path, index=False)
            summary = {
                "rows": int(len(leaderboard)),
                "leaderboard_path": str(leaderboard_path),
                "top3": leaderboard.head(3).to_dict(orient="records"),
            }
            summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
        st.success(f"Experiments completed. Saved to `{leaderboard_path}`.")

    if not leaderboard_path.exists():
        st.info("No leaderboard found yet. Run experiments from the sidebar.")
        return

    leaderboard = pd.read_csv(leaderboard_path)
    st.subheader("1) Leaderboard")
    st.dataframe(leaderboard, use_container_width=True)

    if len(leaderboard):
        st.subheader("2) Best Run Snapshot")
        best = leaderboard.iloc[0]
        c1, c2, c3 = st.columns(3)
        c1.metric("Best ranking score", f"{best['ranking_score']:.4f}")
        c2.metric("Best val actionable acc", f"{best['val_actionable_accuracy'] * 100:.2f}%")
        c3.metric("Best test cumulative return", f"{best['test_cumulative_signal_return'] * 100:.2f}%")

    if summary_path.exists():
        st.subheader("3) Summary JSON")
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

    if page == "Signal Analytics":
        render_signal_analytics_page(
            data_path=data_path,
            model_path=model_path,
            threshold=threshold,
            horizon_steps=horizon_steps,
        )
        return

    render_experiments_page()


if __name__ == "__main__":
    main()

