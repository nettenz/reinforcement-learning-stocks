from __future__ import annotations

import pandas as pd
import numpy as np
from datetime import datetime

from src.dashboard.config import (
    PROMOTION_GATE_DEFAULTS,
    G6_RELAXED_TICKERS,
    G6_RELAXED_MAX,
)
from src.dashboard.leaderboard import _make_command_from_config
from src.signal_analytics import ACTION_LABELS


def summarize_snapshot_bests(history: pd.DataFrame) -> pd.DataFrame:
    if history.empty:
        return history
    if "ranking_score" in history.columns:
        idx = history.groupby("snapshot_id")["ranking_score"].idxmax()
    else:
        idx = history.groupby("snapshot_id")["row_rank"].idxmin()
    bests = history.loc[idx].copy().sort_values("snapshot_time").reset_index(drop=True)
    bests["val_test_gap"] = bests["val_actionable_accuracy"] - bests["test_actionable_accuracy"]
    return bests


def _safe_get(row: pd.Series, key: str, default: object) -> object:
    val = row.get(key, default)
    return default if pd.isna(val) else val


def _evaluate_promotion_gates(row: pd.Series) -> dict[str, object]:
    test_actionable = float(_safe_get(row, "test_actionable_accuracy", 0.0))
    test_win_rate = float(_safe_get(row, "test_trade_win_rate", 0.0))
    test_alpha = float(_safe_get(row, "test_alpha_vs_qqq", float("-inf")))
    val_actionable = float(_safe_get(row, "val_actionable_accuracy", 0.0))
    test_cv_raw = row.get("test_return_cv_by_config", np.inf)
    test_cv = float(pd.to_numeric(pd.Series([test_cv_raw]), errors="coerce").fillna(np.inf).iloc[0])
    test_trade_rate = float(_safe_get(row, "test_trade_rate", np.nan))

    gate_6_min = PROMOTION_GATE_DEFAULTS["test_trade_rate_min"]
    gate_6_max = PROMOTION_GATE_DEFAULTS["test_trade_rate_max"]

    # Retrieve ticker name and resolve Gate 6 Waiver status
    ticker = str(_safe_get(row, "ticker", "")).lower()
    is_relaxed = ticker in G6_RELAXED_TICKERS
    max_trade_rate = G6_RELAXED_MAX if is_relaxed else gate_6_max

    checks = {
        "test_actionable": test_actionable >= PROMOTION_GATE_DEFAULTS["min_test_actionable"],
        "test_win_rate": test_win_rate >= PROMOTION_GATE_DEFAULTS["min_test_win_rate"],
        "test_alpha": test_alpha >= PROMOTION_GATE_DEFAULTS["min_test_alpha"],
        "val_test_gap": abs(val_actionable - test_actionable) <= PROMOTION_GATE_DEFAULTS["max_val_test_gap"],
        "test_cv": test_cv < PROMOTION_GATE_DEFAULTS["max_test_cv"],
        "test_trade_rate": (gate_6_min <= test_trade_rate <= max_trade_rate) if not np.isnan(test_trade_rate) else False,
    }
    return {
        "pass": all(checks.values()),
        "checks": checks,
        "values": {
            "test_actionable": test_actionable,
            "test_win_rate": test_win_rate,
            "test_alpha": test_alpha,
            "val_test_gap": abs(val_actionable - test_actionable),
            "test_cv": test_cv,
            "test_trade_rate": test_trade_rate,
        },
        "is_relaxed": is_relaxed,
    }


def _config_from_row(row: pd.Series) -> dict[str, float | int | bool | str]:
    return {
        "include_news": bool(int(_safe_get(row, "include_news", 1))),
        "use_stationary_features": bool(int(_safe_get(row, "use_stationary_features", 1))),
        "timesteps": int(_safe_get(row, "timesteps", 20000)),
        "learning_rate": float(_safe_get(row, "learning_rate", 0.0003)),
        "gamma": float(_safe_get(row, "gamma", 0.99)),
        "ent_coef": float(_safe_get(row, "ent_coef", 0.02)),
        "threshold": float(_safe_get(row, "threshold", 0.002)),
        "horizon": int(_safe_get(row, "horizon", 1)),
        "transaction_cost_rate": float(_safe_get(row, "transaction_cost_rate", 0.001)),
        "trade_penalty": float(_safe_get(row, "trade_penalty", 0.05)),
        "execution_mode": str(_safe_get(row, "execution_mode", "next_bar")),
        "spread_bps": float(_safe_get(row, "spread_bps", 0.0)),
        "slippage_bps": float(_safe_get(row, "slippage_bps", 0.0)),
        "max_weight_delta_per_step": float(_safe_get(row, "max_weight_delta_per_step", 0.0)),
        "reward_mode": str(_safe_get(row, "reward_mode", "sharpe")),
        "rolling_reward_window": int(_safe_get(row, "rolling_reward_window", 100)),
        "reward_epsilon": float(_safe_get(row, "reward_epsilon", 1e-6)),
        "reward_return_scale": float(_safe_get(row, "reward_return_scale", 1.0)),
        "reward_direction_scale": float(_safe_get(row, "reward_direction_scale", 0.35)),
        "reward_hold_penalty_scale": float(_safe_get(row, "reward_hold_penalty_scale", 0.05)),
        "reward_drawdown_penalty_scale": float(_safe_get(row, "reward_drawdown_penalty_scale", 0.10)),
        "reward_pnl_scale": float(_safe_get(row, "reward_pnl_scale", 0.0)),
        "reward_action_bonus_scale": float(_safe_get(row, "reward_action_bonus_scale", 0.02)),
        "reward_turnover_penalty_scale": float(_safe_get(row, "reward_turnover_penalty_scale", 0.05)),
        "reward_clip": float(_safe_get(row, "reward_clip", 1.0)),
        "reward_ignore_transaction_cost": bool(int(_safe_get(row, "reward_ignore_transaction_cost", 1))),
        "binary_actions": bool(int(_safe_get(row, "binary_actions", 0))),
        "min_hold_bars": int(_safe_get(row, "min_hold_bars", 0)),
    }


def build_next_step_recommendations(
    history: pd.DataFrame,
    target: float,
    seeds: str,
    ticker: str,
) -> list[dict[str, object]]:
    if history.empty:
        return []

    best_row = history.sort_values("ranking_score", ascending=False).iloc[0]
    recent = history.sort_values("snapshot_time").tail(min(30, len(history)))
    recent_bests = summarize_snapshot_bests(history).tail(min(6, max(1, history["snapshot_id"].nunique())))

    avg_val = float(recent_bests["val_actionable_accuracy"].mean())
    avg_test = float(recent_bests["test_actionable_accuracy"].mean())
    collapse_rate = float((recent["val_actionable_accuracy"] <= 0.01).mean())
    avg_gap = float((recent_bests["val_actionable_accuracy"] - recent_bests["test_actionable_accuracy"]).mean())

    base_cfg = _config_from_row(best_row)
    recs: list[dict[str, object]] = []

    stability_cfg = base_cfg.copy()
    stability_cfg["timesteps"] = int(max(10000, int(base_cfg["timesteps"] * 0.8)))
    stability_cfg["ent_coef"] = max(float(base_cfg["ent_coef"]), 0.03)
    stability_cfg["reward_mode"] = "sharpe"
    stability_cfg["reward_direction_scale"] = min(float(base_cfg["reward_direction_scale"]), 0.40)
    stability_cfg["reward_hold_penalty_scale"] = min(float(base_cfg["reward_hold_penalty_scale"]), 0.03)
    stability_cfg["reward_drawdown_penalty_scale"] = max(float(base_cfg["reward_drawdown_penalty_scale"]), 0.10)
    stability_cfg["reward_action_bonus_scale"] = max(float(base_cfg["reward_action_bonus_scale"]), 0.03)
    recs.append(
        {
            "title": "Stability-first retry",
            "why": f"Recent collapse rate is {collapse_rate:.1%}; this setup pushes exploration and softer directional pressure.",
            "steps": [
                "Inspect the latest snapshot's action mix and confirm which seeds collapsed into low-action behavior.",
                "Re-run with higher exploration and stronger anti-collapse bonus while keeping directional pressure capped.",
                "Compare collapse rate and test actionable accuracy against the previous latest snapshot.",
            ],
            "command": _make_command_from_config(stability_cfg, seeds=seeds, run_label="insights-stability", ticker=ticker),
        }
    )

    accuracy_cfg = base_cfg.copy()
    accuracy_cfg["timesteps"] = int(max(12000, int(base_cfg["timesteps"])))
    accuracy_cfg["reward_return_scale"] = min(2.0, float(base_cfg["reward_return_scale"]) + 0.10)
    accuracy_cfg["reward_direction_scale"] = min(0.50, float(base_cfg["reward_direction_scale"]) + 0.05)
    accuracy_cfg["ent_coef"] = max(0.02, float(base_cfg["ent_coef"]))
    accuracy_cfg["reward_mode"] = "sharpe"
    recs.append(
        {
            "title": "Accuracy push",
            "why": (
                f"Recent best means are val={avg_val:.3f}, test={avg_test:.3f}; "
                f"target is {target:.2f}. This extends training while nudging directional signal weight."
            ),
            "steps": [
                "Increase training horizon and slightly up-weight return/directional reward components.",
                "Run the updated config on the same seed set for an apples-to-apples comparison.",
                "Accept this path only if test actionable moves closer to target without widening the val/test gap.",
            ],
            "command": _make_command_from_config(accuracy_cfg, seeds=seeds, run_label="insights-accuracy", ticker=ticker),
        }
    )

    generalization_cfg = base_cfg.copy()
    generalization_cfg["ent_coef"] = max(0.03, float(base_cfg["ent_coef"]))
    generalization_cfg["timesteps"] = int(max(10000, int(base_cfg["timesteps"] * 0.8)))
    generalization_cfg["reward_mode"] = "sharpe"
    if avg_gap > 0.05:
        generalization_cfg["reward_direction_scale"] = max(0.25, float(base_cfg["reward_direction_scale"]) - 0.05)
        generalization_cfg["reward_drawdown_penalty_scale"] = min(0.30, float(base_cfg["reward_drawdown_penalty_scale"]) + 0.03)
        why_text = f"Val-test gap is {avg_gap:.3f}; this reduces likely overfit to validation dynamics."
    else:
        generalization_cfg["gamma"] = min(0.995, float(base_cfg["gamma"]) + 0.002)
        generalization_cfg["reward_hold_penalty_scale"] = max(0.01, float(base_cfg["reward_hold_penalty_scale"]) - 0.01)
        why_text = "Val/test are similarly low; this broadens credit assignment and avoids over-penalizing Hold."
    recs.append(
        {
            "title": "Generalization check",
            "why": why_text,
            "steps": [
                "Adjust generalization-sensitive knobs (gamma/hold penalty or directional/drawdown balance).",
                "Re-evaluate val/test drift over the newest snapshots instead of single-run results.",
                "Promote this profile only if transfer improves while keeping stability metrics intact.",
            ],
            "command": _make_command_from_config(generalization_cfg, seeds=seeds, run_label="insights-generalization", ticker=ticker),
        }
    )

    unique_recs: list[dict[str, object]] = []
    seen_cmds: set[str] = set()
    for rec in recs:
        if rec["command"] in seen_cmds:
            continue
        unique_recs.append(rec)
        seen_cmds.add(rec["command"])
    return unique_recs


def build_experiment_interpretation(history: pd.DataFrame, target: float) -> dict[str, object]:
    bests = summarize_snapshot_bests(history)
    if bests.empty:
        return {
            "stage": "insufficient-history",
            "summary": "Not enough experiment snapshots to infer trends.",
            "findings": [],
            "focus": "Run more snapshots before interpreting model behavior.",
        }

    recent_bests = bests.tail(min(6, len(bests)))
    recent_rows = history.tail(min(30, len(history)))

    latest = recent_bests.iloc[-1]
    avg_val = float(recent_bests["val_actionable_accuracy"].mean())
    avg_test = float(recent_bests["test_actionable_accuracy"].mean())
    avg_gap = float((recent_bests["val_actionable_accuracy"] - recent_bests["test_actionable_accuracy"]).mean())
    test_std = float(recent_bests["test_actionable_accuracy"].std(ddof=0)) if len(recent_bests) > 1 else 0.0
    collapse_rate = float((recent_rows["val_actionable_accuracy"] <= 0.01).mean())

    findings: list[str] = [
        f"Recent best mean accuracy: val={avg_val:.3f}, test={avg_test:.3f}.",
        f"Latest snapshot accuracy: val={float(latest['val_actionable_accuracy']):.3f}, test={float(latest['test_actionable_accuracy']):.3f}.",
        f"Recent val-test gap: {avg_gap:+.3f}.",
        f"Recent test stability (std): {test_std:.3f}.",
    ]

    if "test_return_cv_by_config" in recent_rows.columns:
        recent_cv = (
            pd.to_numeric(recent_rows["test_return_cv_by_config"], errors="coerce")
            .replace([np.inf, -np.inf], np.nan)
            .dropna()
        )
        if not recent_cv.empty:
            findings.append(f"Recent config-level Test Return CV: {float(recent_cv.iloc[-1]):.2f}.")

    if collapse_rate > 0:
        findings.append(f"Collapse signatures (val actionable <= 1%) appeared in {collapse_rate:.1%} of recent runs.")

    if avg_test >= target and abs(avg_gap) <= 0.03 and test_std <= 0.05:
        stage = "healthy"
        summary = "Model behavior looks healthy: near-target accuracy with stable generalization."
        focus = "Prioritize scale-up (more timesteps/seeds) and stress-test across market regimes."
    elif collapse_rate >= 0.20:
        stage = "collapse-risk"
        summary = "Model behavior suggests collapse risk: actionable decisions are dropping too often."
        focus = "Run the stability-focused recommendation first, then re-check action mix."
    elif "test_return_cv_by_config" in recent_rows.columns and float(
        pd.to_numeric(recent_rows["test_return_cv_by_config"], errors="coerce")
        .replace([np.inf, -np.inf], np.nan)
        .fillna(0.0)
        .max()
    ) >= PROMOTION_GATE_DEFAULTS["max_test_cv"]:
        stage = "stability-risk"
        summary = "Returns are unstable across seeds for similar configs (high CV risk)."
        focus = f"Shorten timesteps, raise entropy, and keep Sharpe reward while rechecking CV by config below {PROMOTION_GATE_DEFAULTS['max_test_cv']}."
    elif avg_gap > 0.05:
        stage = "overfit-risk"
        summary = "Validation outperforms test by a meaningful margin; likely overfitting to split dynamics."
        focus = "Run the generalization-focused recommendation first and tighten drawdown controls."
    elif avg_test < target:
        stage = "under-target"
        summary = "Model is below target actionable accuracy and needs stronger signal extraction."
        focus = "Run the accuracy-push recommendation first, then compare win-rate drift."
    else:
        stage = "mixed"
        summary = "Signals are mixed: some progress, but stability and transfer are inconsistent."
        focus = "Alternate stability and generalization recommendations before larger sweeps."

    return {
        "stage": stage,
        "summary": summary,
        "findings": findings,
        "focus": focus,
    }


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
