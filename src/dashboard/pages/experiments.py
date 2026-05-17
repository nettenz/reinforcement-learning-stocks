from __future__ import annotations

import argparse
import pandas as pd
import numpy as np
import streamlit as st

from src.dashboard.config import (
    DEFAULT_TICKER,
    PROMOTION_GATE_DEFAULTS,
    RECOMMENDED_THRESHOLD,
)
from src.dashboard.model_utils import (
    _normalize_dashboard_interval,
    _artifact_paths_for_interval,
)
from src.dashboard.leaderboard import (
    _latest_comparable_leaderboard,
    _ticker_match_mask,
)
from src.dashboard.components.gates import render_trade_rate_histogram


def render_experiments_page(ticker: str = DEFAULT_TICKER, interval: str = "1d") -> None:
    st.header(f"Experiments - {ticker.upper()}")
    st.caption("Run multi-seed sweeps (Binary PPO / SAC) and rank configurations on validation performance.")

    with st.sidebar:
        st.subheader("Experiment runner")
        include_news = st.checkbox("Include sentiment features", value=True)
        use_stationary_features = st.checkbox(
            "Use stationary features",
            value=True,
            help="Use log-return and normalized technical indicators instead of raw OHLCV schemas.",
        )
        
        # PPO / SAC options integration
        binary_actions = st.checkbox(
            "Binary Actions (PPO)", 
            value=True,
            help="Required for Binary PPO. Maps continuous outputs to binary buy/sell thresholds."
        )
        min_hold_bars = st.number_input(
            "Min Hold Bars", 
            min_value=0, 
            max_value=20, 
            value=3 if "googl" in ticker.lower() or "amzn" in ticker.lower() or "amd" in ticker.lower() else 0,
            help="Minimum holding period constraints enforced during training."
        )

        seeds = st.text_input("Seeds", value="3,7,13,21,42")
        timesteps = st.text_input("Timesteps", value="50000")
        learning_rates = st.text_input("Learning rates", value="0.0003")
        gammas = st.text_input("Gammas", value="0.99")
        ent_coefs = st.text_input("Entropy coeffs", value="0.02,0.05")
        
        threshold = st.number_input(
            "Eval threshold",
            min_value=0.0,
            max_value=0.05,
            value=RECOMMENDED_THRESHOLD,
            step=0.0001,
            format="%.4f",
            help="Price movement threshold for labeling actionable signals.",
        )
        horizon = st.number_input(
            "Eval horizon",
            min_value=1,
            max_value=10,
            value=1,
            step=1,
            help="Horizon bars to look ahead for profit/risk evaluation.",
        )
        transaction_cost_rate = st.number_input("Transaction cost rate", min_value=0.0, max_value=0.01, value=0.001, format="%.4f")
        trade_penalty = st.number_input("Trade penalty", min_value=0.0, max_value=0.5, value=0.05, format="%.3f")
        execution_mode = st.selectbox("Execution mode", options=["legacy", "next_bar", "instant"], index=1)
        spread_bps = st.number_input("Spread (bps)", min_value=0.0, max_value=100.0, value=0.0, step=0.5)
        slippage_bps = st.number_input("Slippage (bps)", min_value=0.0, max_value=100.0, value=0.0, step=0.5)
        
        max_weight_delta_per_step = st.number_input(
            "Max weight delta / step",
            min_value=0.0,
            max_value=2.0,
            value=0.10,
            step=0.05,
            help="Caps exposure changes. Set to 0.10 for stable Binary PPO sweeps.",
        )
        
        reward_return_scale = st.number_input("Reward: portfolio-return scale", min_value=0.0, max_value=5.0, value=1.0, step=0.05)
        reward_direction_scale = st.number_input("Reward: directional scale", min_value=0.0, max_value=5.0, value=0.35, step=0.05)
        reward_hold_penalty_scale = st.number_input("Reward: hold penalty scale", min_value=0.0, max_value=5.0, value=0.01, step=0.01)
        reward_drawdown_penalty_scale = st.number_input("Reward: drawdown penalty scale", min_value=0.0, max_value=5.0, value=0.10, step=0.01)
        reward_pnl_scale = st.number_input("Reward: PnL scale", min_value=0.0, max_value=5.0, value=0.0, step=0.01)
        reward_action_bonus_scale = st.number_input("Reward: action bonus (anti-collapse)", min_value=0.0, max_value=1.0, value=0.02, step=0.01)
        reward_turnover_penalty_scale = st.number_input("Reward: turnover penalty scale", min_value=0.0, max_value=2.0, value=0.05, step=0.01)
        reward_mode = st.selectbox("Reward mode", options=["legacy", "sharpe", "sortino", "sparse"], index=1)
        rolling_reward_window = st.number_input("Rolling reward window", min_value=5, max_value=1000, value=100, step=5)
        reward_epsilon = st.number_input("Reward epsilon", min_value=1e-9, max_value=1e-3, value=1e-6, format="%.9f")
        reward_clip = st.number_input("Reward clip (+/-)", min_value=0.01, max_value=10.0, value=1.0, step=0.05)
        reward_ignore_transaction_cost = st.checkbox("Ignore transaction cost in reward", value=True)
        
        run_label = st.text_input(
            "Run label (for snapshot naming)",
            value="dashboard-sweep",
            help="Used in snapshot filenames to keep experiment themes clear.",
        )
        max_runs = st.number_input("Max runs (0=all)", min_value=0, max_value=200, value=15, step=1)
        run_experiment = st.button("Run experiments", type="primary", use_container_width=True, key="run_experiments")

    interval_key = _normalize_dashboard_interval(interval)
    experiment_preset = "intraday_5m" if interval_key == "5m" else "daily"
    leaderboard_path, reward_leaderboard_path, summary_path, snapshot_dir = _artifact_paths_for_interval(interval_key)

    if run_experiment:
        from src.experiments import run_experiments, write_experiment_outputs

        args = argparse.Namespace(
            ticker=ticker,
            interval=interval_key,
            experiment_preset=experiment_preset,
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
            execution_mode=str(execution_mode),
            spread_bps=float(spread_bps),
            slippage_bps=float(slippage_bps),
            max_weight_delta_per_step=str(max_weight_delta_per_step),
            reward_pnl_scale=str(reward_pnl_scale),
            reward_return_scale=str(reward_return_scale),
            reward_direction_scale=str(reward_direction_scale),
            reward_hold_penalty_scale=str(reward_hold_penalty_scale),
            reward_drawdown_penalty_scale=str(reward_drawdown_penalty_scale),
            reward_action_bonus_scale=str(reward_action_bonus_scale),
            reward_turnover_penalty_scale=str(reward_turnover_penalty_scale),
            reward_mode=reward_mode,
            rolling_reward_window=str(rolling_reward_window),
            reward_epsilon=float(reward_epsilon),
            reward_clip=float(reward_clip),
            reward_ignore_transaction_cost=bool(reward_ignore_transaction_cost),
            use_stationary_features=bool(use_stationary_features),
            long_only=False,
            binary_actions=bool(binary_actions),
            min_hold_bars=int(min_hold_bars),
            max_episode_steps=0,
            random_start=False,
            batch_size=1024,
            max_runs=int(max_runs),
            leaderboard_path=str(leaderboard_path),
            reward_leaderboard_path=str(reward_leaderboard_path),
            summary_path=str(summary_path),
            disable_snapshots=False,
            snapshot_dir=str(snapshot_dir),
            run_label=run_label.strip(),
            device="cpu",
            use_lr_schedule=False,
            n_envs=1, # Bypasses OS file descriptor limit leak
            append=True,
        )
        with st.spinner("⏳ Running experiments sweep (n_envs=1 for stability)..."):
            leaderboard = run_experiments(args)
            leaderboard_path.parent.mkdir(parents=True, exist_ok=True)
            reward_leaderboard_path.parent.mkdir(parents=True, exist_ok=True)
            summary_path.parent.mkdir(parents=True, exist_ok=True)
            write_experiment_outputs(
                leaderboard=leaderboard,
                leaderboard_path=leaderboard_path,
                reward_leaderboard_path=reward_leaderboard_path,
                summary_path=summary_path,
                snapshot_dir=snapshot_dir,
                run_label=run_label.strip() or "dashboard",
                append_results=True,
            )
        st.success(f"Sweep completed. Saved to `{leaderboard_path}`.")

    if not leaderboard_path.exists():
        st.info("No leaderboard found yet. Run a sweep from the sidebar to populate.")
        return

    leaderboard = pd.read_csv(leaderboard_path)
    leaderboard = _latest_comparable_leaderboard(leaderboard)
    if "ticker" in leaderboard.columns:
        leaderboard = leaderboard[_ticker_match_mask(leaderboard["ticker"], ticker_key=ticker)].copy()
    st.subheader("1) Leaderboard")
    st.dataframe(leaderboard, use_container_width=True)

    render_trade_rate_histogram(
        leaderboard, 
        run_label=leaderboard.iloc[0].get("run_label", "") if len(leaderboard) > 0 else ""
    )

    if len(leaderboard):
        st.subheader("2) Best Run Snapshot")
        best = leaderboard.iloc[0]
        c1, c2, c3 = st.columns(3)
        c1.metric("Best ranking score", f"{best['ranking_score']:.4f}")
        test_actionable = best.get('test_actionable_accuracy', 0.0)
        c2.metric(
            "Best test actionable acc",
            f"{test_actionable * 100:.2f}%",
            delta=f"{(test_actionable - PROMOTION_GATE_DEFAULTS['min_test_actionable']) * 100:.2f}%",
            delta_color="normal"
        )
        c3.metric("Best test cumulative return", f"{best['test_cumulative_signal_return'] * 100:.2f}%")

        r1, r2, r3, r4 = st.columns(4)
        val_sharpe = best.get('val_sharpe_ratio', 0)
        test_sharpe = best.get('test_sharpe_ratio', 0)
        r1.metric("Val Sharpe", f"{val_sharpe:.2f}")
        r2.metric("Test Sharpe", f"{test_sharpe:.2f}")
        r3.metric("Val Max DD", f"{best.get('val_max_drawdown', 0) * 100:.2f}%")
        r4.metric("Test Max DD", f"{best.get('test_max_drawdown', 0) * 100:.2f}%")

        if "test_return_cv_by_config" in leaderboard.columns:
            cv_col, risk_col = st.columns(2)
            config_cv = float(best.get('test_return_cv_by_config', 0.0))
            cv_col.metric(
                "Config Test Return CV",
                f"{config_cv:.2f}",
                delta=f"{(PROMOTION_GATE_DEFAULTS['max_test_cv'] - config_cv):.2f}" if np.isfinite(config_cv) else "N/A",
                delta_color="inverse" if np.isfinite(config_cv) else "off"
            )
            risk_col.metric(
                "High CV Risk (CV >= 0.50)",
                "YES" if int(float(best.get("high_return_cv_risk", 0))) == 1 or config_cv >= 0.50 else "NO",
            )
