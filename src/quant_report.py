"""
Automated Quant Professional Interpretation Report Generator.

Reads experiment leaderboard CSVs and generates a professional markdown
analysis with statistical diagnostics, regime insights, and next-step recommendations.

Usage:
    python src/quant_report.py                              # uses default leaderboard
    python src/quant_report.py --input data/experiment_leaderboard.csv
    python src/quant_report.py --input data/experiment_snapshots/some_snapshot.csv
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
import sys

import numpy as np
import pandas as pd

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

DEFAULT_LEADERBOARD = ROOT_DIR / "data" / "experiment_leaderboard.csv"
DEFAULT_OUTPUT_DIR = ROOT_DIR / "sessions"


# ---------------------------------------------------------------------------
# Core analysis functions
# ---------------------------------------------------------------------------

def _safe_col(df: pd.DataFrame, col: str, default=0.0) -> pd.Series:
    """Safely retrieve a column, returning a default-filled Series if missing."""
    if col in df.columns:
        return df[col].fillna(default)
    return pd.Series([default] * len(df), index=df.index)


def _generalization_gap(df: pd.DataFrame) -> dict:
    """Measure how well validation performance carries over to test."""
    val_ret = _safe_col(df, "val_cumulative_signal_return")
    test_ret = _safe_col(df, "test_cumulative_signal_return")
    val_acc = _safe_col(df, "val_actionable_accuracy")
    test_acc = _safe_col(df, "test_actionable_accuracy")
    val_sharpe = _safe_col(df, "val_sharpe_ratio")
    test_sharpe = _safe_col(df, "test_sharpe_ratio")

    return {
        "return_gap_mean": float((val_ret - test_ret).mean()),
        "return_gap_std": float((val_ret - test_ret).std()),
        "accuracy_gap_mean": float((val_acc - test_acc).mean()),
        "sharpe_gap_mean": float((val_sharpe - test_sharpe).mean()),
        "val_return_mean": float(val_ret.mean()),
        "test_return_mean": float(test_ret.mean()),
        "val_sharpe_mean": float(val_sharpe.mean()),
        "test_sharpe_mean": float(test_sharpe.mean()),
    }


def _action_collapse_check(df: pd.DataFrame) -> dict:
    """Check if the agent is collapsing to a single action."""
    val_wr = _safe_col(df, "val_trade_win_rate")
    test_wr = _safe_col(df, "test_trade_win_rate")
    val_action_bonus = _safe_col(df, "val_reward_action_bonus_mean")

    # If action bonus is near zero, the agent rarely trades → potential collapse to Hold
    low_activity_pct = float((val_action_bonus < 0.001).mean()) * 100

    return {
        "val_win_rate_mean": float(val_wr.mean()),
        "test_win_rate_mean": float(test_wr.mean()),
        "low_activity_pct": low_activity_pct,
    }


def _reward_mode_comparison(df: pd.DataFrame) -> pd.DataFrame:
    """Compare performance across reward modes."""
    if "reward_mode" not in df.columns:
        return pd.DataFrame()

    metrics = ["val_sharpe_ratio", "test_sharpe_ratio", "val_sortino_ratio", "test_sortino_ratio",
               "val_cumulative_signal_return", "test_cumulative_signal_return",
               "val_max_drawdown", "test_max_drawdown",
               "val_actionable_accuracy", "test_actionable_accuracy",
               "val_trade_win_rate", "test_trade_win_rate",
               "ranking_score"]

    available = [m for m in metrics if m in df.columns]
    if not available:
        return pd.DataFrame()

    grouped = df.groupby("reward_mode")[available].agg(["mean", "std"])
    return grouped


def _seed_stability(df: pd.DataFrame) -> dict:
    """Measure cross-seed variance to assess robustness."""
    if "seed" not in df.columns or df["seed"].nunique() < 2:
        return {"seed_count": 1, "verdict": "Insufficient seeds for stability analysis."}

    val_ret = _safe_col(df, "val_cumulative_signal_return")
    test_ret = _safe_col(df, "test_cumulative_signal_return")
    val_sharpe = _safe_col(df, "val_sharpe_ratio")

    cv_val = float(val_ret.std() / max(abs(val_ret.mean()), 1e-8))
    cv_test = float(test_ret.std() / max(abs(test_ret.mean()), 1e-8))

    if cv_val < 0.3:
        stability = "HIGH"
    elif cv_val < 0.7:
        stability = "MODERATE"
    else:
        stability = "LOW"

    return {
        "seed_count": int(df["seed"].nunique()),
        "val_return_cv": cv_val,
        "test_return_cv": cv_test,
        "val_sharpe_std": float(val_sharpe.std()),
        "stability_rating": stability,
    }


def _benchmark_analysis(df: pd.DataFrame) -> dict:
    """Compare strategy alpha vs QQQ benchmark."""
    val_alpha = _safe_col(df, "val_alpha_vs_qqq")
    test_alpha = _safe_col(df, "test_alpha_vs_qqq")

    return {
        "val_alpha_mean": float(val_alpha.mean()),
        "test_alpha_mean": float(test_alpha.mean()),
        "pct_positive_test_alpha": float((test_alpha > 0).mean()) * 100,
    }


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------

def _signal_verdict(gap: dict, stability: dict, benchmark: dict, collapse: dict) -> str:
    """Generate a professional one-line signal verdict."""
    score = 0
    if gap["test_return_mean"] > 0:
        score += 1
    if gap["return_gap_mean"] < 0.05:
        score += 1
    if stability.get("stability_rating") in ("HIGH", "MODERATE"):
        score += 1
    if benchmark["pct_positive_test_alpha"] > 50:
        score += 1
    if collapse["low_activity_pct"] < 30:
        score += 1

    if score >= 4:
        return "**BULLISH** — Strategy shows robust generalization and positive alpha."
    elif score >= 3:
        return "**NEUTRAL/BULLISH** — Promising signals but further validation needed."
    elif score >= 2:
        return "**NEUTRAL** — Mixed results. Hyperparameter tuning or architecture changes recommended."
    else:
        return "**BEARISH** — Strategy is not yet investable. Fundamental changes required."


def _next_steps(gap: dict, stability: dict, benchmark: dict, collapse: dict, mode_comparison: pd.DataFrame) -> list[str]:
    """Generate prioritized next-step recommendations."""
    steps = []

    if collapse["low_activity_pct"] > 50:
        steps.append("**CRITICAL — Action Collapse:** The agent is inactive in >50% of runs. Increase `reward_action_bonus_scale` or reduce `trade_penalty`.")

    if gap["return_gap_mean"] > 0.10:
        steps.append("**Overfitting Detected:** Val→Test return gap is %.1f%%. Reduce timesteps, increase regularization, or diversify training data." % (gap["return_gap_mean"] * 100))

    if stability.get("stability_rating") == "LOW":
        steps.append("**Seed Instability:** Cross-seed variance is high (CV=%.2f). The strategy is not robust — increase seed count and consider ensemble averaging." % stability.get("val_return_cv", 0))

    if benchmark["pct_positive_test_alpha"] < 50:
        steps.append("**Alpha Deficit:** Only %.0f%% of runs beat the QQQ benchmark. The agent is underperforming passive buy-and-hold." % benchmark["pct_positive_test_alpha"])

    if gap["test_sharpe_mean"] < 0.5:
        steps.append("**Low Risk-Adjusted Returns:** Test Sharpe (%.2f) is below institutional threshold (1.0). Focus on drawdown management and reward stability." % gap["test_sharpe_mean"])

    if not mode_comparison.empty and "reward_mode" in mode_comparison.index.names:
        steps.append("**Compare Reward Modes:** Multiple reward modes were tested. Use the dashboard to evaluate which mode produces the smoothest equity curve.")

    if not steps:
        steps.append("**Continue Scaling:** Results look solid. Consider increasing timesteps to 100k+ and adding more diverse market data.")

    return steps


def generate_report(df: pd.DataFrame) -> str:
    """Generate the full markdown report from a leaderboard DataFrame."""
    gap = _generalization_gap(df)
    collapse = _action_collapse_check(df)
    stability = _seed_stability(df)
    benchmark = _benchmark_analysis(df)
    mode_comparison = _reward_mode_comparison(df)
    verdict = _signal_verdict(gap, stability, benchmark, collapse)
    steps = _next_steps(gap, stability, benchmark, collapse, mode_comparison)

    top_run = df.iloc[0] if len(df) > 0 else pd.Series()

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    lines = []
    lines.append(f"# Quant Professional Interpretation: Automated Analysis")
    lines.append(f"**Generated:** {timestamp}  ")
    lines.append(f"**Runs Analyzed:** {len(df)}  ")
    lines.append(f"**Unique Seeds:** {stability.get('seed_count', 'N/A')}  ")
    lines.append(f"**Algorithm:** SAC (Continuous Action Space)")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Executive Summary
    lines.append("## Executive Summary")
    lines.append(f"- **Signal Verdict:** {verdict}")
    lines.append(f"- **Val Return (mean):** {gap['val_return_mean']:.4f}")
    lines.append(f"- **Test Return (mean):** {gap['test_return_mean']:.4f}")
    lines.append(f"- **Val→Test Gap:** {gap['return_gap_mean']:.4f}")
    lines.append(f"- **Val Sharpe (mean):** {gap['val_sharpe_mean']:.2f}")
    lines.append(f"- **Test Sharpe (mean):** {gap['test_sharpe_mean']:.2f}")
    lines.append("")

    # Top Run
    if not top_run.empty:
        lines.append("---")
        lines.append("")
        lines.append("## Top Run (by Ranking Score)")
        lines.append("")
        lines.append("| Metric | Value |")
        lines.append("|---|---|")
        key_metrics = [
            ("Seed", "seed"), ("Timesteps", "timesteps"), ("Learning Rate", "learning_rate"),
            ("Reward Mode", "reward_mode"), ("Rolling Window", "rolling_reward_window"),
            ("Ranking Score", "ranking_score"),
            ("Val Accuracy", "val_actionable_accuracy"), ("Test Accuracy", "test_actionable_accuracy"),
            ("Val Win Rate", "val_trade_win_rate"), ("Test Win Rate", "test_trade_win_rate"),
            ("Val Sharpe", "val_sharpe_ratio"), ("Test Sharpe", "test_sharpe_ratio"),
            ("Val Sortino", "val_sortino_ratio"), ("Test Sortino", "test_sortino_ratio"),
            ("Val Max DD", "val_max_drawdown"), ("Test Max DD", "test_max_drawdown"),
            ("Val Alpha vs QQQ", "val_alpha_vs_qqq"), ("Test Alpha vs QQQ", "test_alpha_vs_qqq"),
        ]
        for label, col in key_metrics:
            val = top_run.get(col, "N/A")
            if isinstance(val, float):
                val = f"{val:.4f}"
            lines.append(f"| {label} | {val} |")
        lines.append("")

    # Generalization Analysis
    lines.append("---")
    lines.append("")
    lines.append("## Generalization Analysis (Val → Test)")
    lines.append(f"- **Return Gap (mean):** {gap['return_gap_mean']:.4f} ± {gap['return_gap_std']:.4f}")
    lines.append(f"- **Accuracy Gap (mean):** {gap['accuracy_gap_mean']:.4f}")
    lines.append(f"- **Sharpe Gap (mean):** {gap['sharpe_gap_mean']:.2f}")
    if gap["return_gap_mean"] > 0.10:
        lines.append(f"- ⚠️ **WARNING:** Significant overfitting detected. Val massively outperforms test.")
    elif gap["return_gap_mean"] < -0.05:
        lines.append(f"- ✅ Test outperforms validation — rare and encouraging signal.")
    else:
        lines.append(f"- ✅ Gap is within acceptable bounds.")
    lines.append("")

    # Seed Stability
    lines.append("---")
    lines.append("")
    lines.append("## Seed Stability")
    lines.append(f"- **Seeds Tested:** {stability.get('seed_count', 'N/A')}")
    lines.append(f"- **Stability Rating:** {stability.get('stability_rating', 'N/A')}")
    if "val_return_cv" in stability:
        lines.append(f"- **Val Return CV:** {stability['val_return_cv']:.2f}")
        lines.append(f"- **Test Return CV:** {stability['test_return_cv']:.2f}")
        lines.append(f"- **Val Sharpe σ:** {stability['val_sharpe_std']:.2f}")
    lines.append("")

    # Benchmark
    lines.append("---")
    lines.append("")
    lines.append("## Benchmark Comparison (vs QQQ)")
    lines.append(f"- **Val Alpha (mean):** {benchmark['val_alpha_mean']:.4f}")
    lines.append(f"- **Test Alpha (mean):** {benchmark['test_alpha_mean']:.4f}")
    lines.append(f"- **% Runs Beating QQQ (test):** {benchmark['pct_positive_test_alpha']:.0f}%")
    lines.append("")

    # Action Collapse
    lines.append("---")
    lines.append("")
    lines.append("## Agent Behavior")
    lines.append(f"- **Val Win Rate (mean):** {collapse['val_win_rate_mean']:.4f}")
    lines.append(f"- **Test Win Rate (mean):** {collapse['test_win_rate_mean']:.4f}")
    lines.append(f"- **Low Activity Runs:** {collapse['low_activity_pct']:.0f}%")
    if collapse["low_activity_pct"] > 50:
        lines.append(f"- ⚠️ **WARNING:** Agent is collapsing to inactivity in most runs.")
    lines.append("")

    # Reward Mode Comparison
    if not mode_comparison.empty:
        lines.append("---")
        lines.append("")
        lines.append("## Reward Mode Comparison")
        lines.append("")
        lines.append(mode_comparison.to_markdown())
        lines.append("")

    # Next Steps
    lines.append("---")
    lines.append("")
    lines.append("## Recommended Next Steps")
    lines.append("")
    for i, step in enumerate(steps, 1):
        lines.append(f"{i}. {step}")
    lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Generate a Quant Professional Interpretation report from experiment results.")
    parser.add_argument("--input", default=str(DEFAULT_LEADERBOARD), help="Path to leaderboard CSV.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR), help="Directory to write the report.")
    parser.add_argument("--output-name", default="", help="Custom filename (default: auto-timestamped).")
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"ERROR: Leaderboard not found at {input_path}")
        sys.exit(1)

    df = pd.read_csv(input_path)
    if df.empty:
        print("ERROR: Leaderboard is empty.")
        sys.exit(1)

    df = df.sort_values("ranking_score", ascending=False).reset_index(drop=True)

    report = generate_report(df)

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    if args.output_name:
        filename = args.output_name
    else:
        ts = datetime.now().strftime("%Y-%m-%d-%H%M")
        filename = f"quant-report-{ts}.md"

    output_path = output_dir / filename
    output_path.write_text(report, encoding="utf-8")
    print(f"Report generated: {output_path}")
    print(report)


if __name__ == "__main__":
    main()
