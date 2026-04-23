from __future__ import annotations

import json
from pathlib import Path
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
LOGS = ROOT / "logs"
OUT = ROOT / "artifacts"
OUT.mkdir(exist_ok=True)


def latest_file(pattern: str) -> Path | None:
    matches = sorted(LOGS.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
    return matches[0] if matches else None


def load_json(path: Path | None) -> dict:
    if not path or not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def safe_read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path)


def dedup_leaderboard(df: pd.DataFrame) -> pd.DataFrame:
    """Keep the highest-ranking_score row per (run_label, seed)."""
    if df.empty or "ranking_score" not in df.columns:
        return df
    return (
        df.sort_values("ranking_score", ascending=False)
        .drop_duplicates(subset=["run_label", "seed"])
        .reset_index(drop=True)
    )


def compute_gaps(df: pd.DataFrame) -> pd.DataFrame:
    """Add val-vs-test gap columns."""
    if df.empty:
        return df
    if "val_alpha_vs_qqq" in df.columns and "test_alpha_vs_qqq" in df.columns:
        df = df.copy()
        df["alpha_gap"] = (df["val_alpha_vs_qqq"] - df["test_alpha_vs_qqq"]).round(4)
    if "val_cumulative_return" in df.columns and "test_cumulative_return" in df.columns:
        df["return_gap"] = (df["val_cumulative_return"] - df["test_cumulative_return"]).round(4)
    return df


def summarize_top_configs(df: pd.DataFrame, top_n: int = 8) -> list[dict]:
    if df.empty:
        return []

    preferred_cols = [
        c for c in [
            "config_id",
            "run_label",
            "reward_mode",
            "val_actionable_accuracy",
            "test_actionable_accuracy",
            "test_trade_win_rate",
            "test_alpha_vs_qqq",
            "test_cumulative_return",
            "test_return_cv_by_config",
            "robustness_score",
            "alpha_gap",
            "return_gap",
        ]
        if c in df.columns
    ]

    sort_col = next(
        (c for c in ["test_alpha_vs_qqq", "test_cumulative_return", "test_actionable_accuracy"]
         if c in df.columns),
        None,
    )
    if sort_col:
        df = df.sort_values(sort_col, ascending=False)

    return df[preferred_cols].head(top_n).to_dict(orient="records")


def best_robust_candidate(df: pd.DataFrame) -> dict | None:
    """Return the config with lowest CV among the top-16 by test alpha."""
    if df.empty:
        return None
    cv_col = "test_return_cv_by_config"
    alpha_col = "test_alpha_vs_qqq"
    if cv_col not in df.columns or alpha_col not in df.columns:
        return None
    pool = df.sort_values(alpha_col, ascending=False).head(16)
    best = pool.sort_values(cv_col).iloc[0]
    return {
        "run_label": best.get("run_label", "?"),
        "reward_mode": best.get("reward_mode", "?"),
        "test_alpha_vs_qqq": round(best[alpha_col], 4),
        cv_col: round(best[cv_col], 4),
        "robustness_score": round(best.get("robustness_score", float("nan")), 4),
        "high_return_cv_risk": best.get("high_return_cv_risk", "?"),
    }


def stage1_verdict(
    df: pd.DataFrame,
    gate_report: dict,
    robust: dict | None,
) -> list[str]:
    lines = []

    # Gate report verdict
    if gate_report:
        verdict_str = gate_report.get("verdict")
        if verdict_str:
            lines.append(f"Gate verdict: {verdict_str}")
        for key in ("baseline_gate_passed", "trading_gate_passed", "passed", "gate_passed"):
            val = gate_report.get(key)
            if val is not None:
                lines.append(f"{key}: {val}")

    # Best test alpha
    if not df.empty and "test_alpha_vs_qqq" in df.columns:
        best_alpha = df["test_alpha_vs_qqq"].max()
        lines.append(f"Best test alpha vs QQQ: {best_alpha:.4f}")

    # CV risk
    if not df.empty and "high_return_cv_risk" in df.columns:
        n_high_cv = int(df["high_return_cv_risk"].sum())
        total = len(df)
        lines.append(f"High CV risk configs: {n_high_cv}/{total}")

    # Robust candidate summary
    if robust:
        cv = robust.get("test_return_cv_by_config", "?")
        label = robust.get("run_label", "?")
        lines.append(f"Best robust candidate: {label} (CV={cv})")

    # Alpha gap: large gap → val-only winner
    if not df.empty and "alpha_gap" in df.columns:
        max_gap = df["alpha_gap"].max()
        lines.append(f"Max val-test alpha gap: {max_gap:.4f}")
        if max_gap > 0.15:
            lines.append("WARNING: large val-test gap detected — potential overfitting to val set")

    if not lines:
        lines.append("Insufficient data for verdict.")
    return lines


def render_md(
    top_configs: list[dict],
    reward_top_configs: list[dict],
    summary: dict,
    gate_report: dict,
    trading_eval: dict,
    robust: dict | None,
    verdict_lines: list[str],
) -> str:
    lines = []
    lines.append("## Context")
    lines.append("- Track: Stage 1 / RL / Mixed")
    lines.append("- Goal: decide whether RL escalation is justified")
    lines.append("")

    lines.append("## Top Configs (by test alpha vs QQQ)")
    if top_configs:
        for row in top_configs:
            parts = [f"{k}={v}" for k, v in row.items()]
            lines.append(f"- {' | '.join(parts)}")
    else:
        lines.append("- No leaderboard data found.")
    lines.append("")

    lines.append("## Top Configs by Reward Leaderboard")
    if reward_top_configs:
        for row in reward_top_configs:
            parts = [f"{k}={v}" for k, v in row.items()]
            lines.append(f"- {' | '.join(parts)}")
    else:
        lines.append("- No reward leaderboard data found.")
    lines.append("")

    lines.append("## Best Robust Candidate")
    if robust:
        for k, v in robust.items():
            lines.append(f"- {k}: {v}")
    else:
        lines.append("- Could not determine robust candidate.")
    lines.append("")

    lines.append("## Stage 1 Verdict")
    for v in verdict_lines:
        lines.append(f"- {v}")
    lines.append("")

    lines.append("## Experiment Summary")
    if summary:
        for k, v in summary.items():
            lines.append(f"- {k}: {v}")
    else:
        lines.append("- No experiment_summary.json found.")
    lines.append("")

    lines.append("## Stage 1 Gate")
    if gate_report:
        for k, v in gate_report.items():
            lines.append(f"- {k}: {v}")
    else:
        lines.append("- No stage1 gate report found.")
    lines.append("")

    lines.append("## Stage 1 Trading Eval")
    if trading_eval:
        for k, v in trading_eval.items():
            lines.append(f"- {k}: {v}")
    else:
        lines.append("- No stage1 trading eval found.")
    lines.append("")

    lines.append("## Analyst Focus")
    lines.append("- Determine whether signal is robust enough to justify RL follow-up.")
    lines.append("- Reject validation-only or seed-fragile winners.")
    return "\n".join(lines)


def main() -> None:
    leaderboard = dedup_leaderboard(
        compute_gaps(safe_read_csv(DATA / "experiment_leaderboard.csv"))
    )
    reward_leaderboard = dedup_leaderboard(
        compute_gaps(safe_read_csv(DATA / "experiment_reward_leaderboard.csv"))
    )
    summary = load_json(DATA / "experiment_summary.json")
    gate_report = load_json(latest_file("stage1_gate_report*.json"))
    trading_eval = load_json(latest_file("stage1_trading_eval*.json"))

    top_configs = summarize_top_configs(leaderboard)
    reward_top_configs = summarize_top_configs(reward_leaderboard)
    robust = best_robust_candidate(leaderboard)
    verdict = stage1_verdict(leaderboard, gate_report, robust)

    md = render_md(top_configs, reward_top_configs, summary, gate_report, trading_eval, robust, verdict)

    out_path = OUT / "refinement_context.md"
    out_path.write_text(md, encoding="utf-8")
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
