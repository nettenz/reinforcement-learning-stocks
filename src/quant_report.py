"""
Quant Professional Report Generator — Updated May 2026

Reads experiment leaderboard CSVs and generates a professional terminal-formatted
analysis with 6-gate evaluation, clean CV diagnostics, overtrade detection,
regime analysis, and prioritized next-step recommendations.

Usage:
    python src/quant_report.py
    python src/quant_report.py --input data/experiment_leaderboard.csv
    python src/quant_report.py --input data/experiment_leaderboard.csv --label sweep_amd_baseline_v5
    python src/quant_report.py --input data/experiment_leaderboard.csv --ticker nvda
    python src/quant_report.py --stage1-gate-json logs/stage1_gate_report.json
"""
from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
import sys
from urllib import error, request

import numpy as np
import pandas as pd
from dotenv import load_dotenv

# Load .env from project root regardless of working directory
_ENV_PATH = Path(__file__).resolve().parents[1] / ".env"
load_dotenv(dotenv_path=_ENV_PATH)

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

DEFAULT_LEADERBOARD = ROOT_DIR / "data" / "experiment_leaderboard.csv"
DEFAULT_OUTPUT_DIR  = ROOT_DIR / "sessions"

# ---------------------------------------------------------------------------
# Terminal formatting helpers — matches evaluate_sweep.py aesthetic
# ---------------------------------------------------------------------------

SEP  = "=" * 70
LINE = "─" * 70

def _bar(value: float, width: int = 20, max_val: float = 1.0) -> str:
    filled = int(min(value / max_val, 1.0) * width)
    return "█" * filled + "░" * (width - filled)

def _gate_sym(passed: bool) -> str:
    return "✅" if passed else "❌"

def _trend(val: float, threshold: float = 0.0, higher_is_better: bool = True) -> str:
    if higher_is_better:
        return "✅" if val >= threshold else "❌"
    return "✅" if val <= threshold else "❌"

def _fmt(val, fmt=".4f") -> str:
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return "N/A"
    return format(val, fmt)


# ---------------------------------------------------------------------------
# Gate definitions — 6/6 required
# ---------------------------------------------------------------------------

GATES = [
    {"id": 1, "name": "Actionable Accuracy",  "col": "test_actionable_accuracy",    "op": ">=", "threshold": 0.53},
    {"id": 2, "name": "Trade Win Rate",        "col": "test_trade_win_rate",          "op": ">=", "threshold": 0.52},
    {"id": 3, "name": "Alpha vs QQQ",          "col": "test_alpha_vs_qqq",            "op": ">=", "threshold": 0.00},
    {"id": 4, "name": "Val/Test Drift",        "col": None,                           "op": "<=", "threshold": 0.05},
    {"id": 5, "name": "CV Stability",          "col": "clean_cv",                     "op": "<",  "threshold": 1.00},
    {"id": 6, "name": "Trade Rate",            "col": "test_trade_rate",              "op": "between", "threshold": (0.40, 0.80)},
]

TRADE_RATE_LOW  = 0.60
TRADE_RATE_HIGH = 0.75

# Active seed filter for clean CV
ACTIVE_SHARPE_MIN = 0.0
ACTIVE_TRADE_MIN  = 0.10


# ---------------------------------------------------------------------------
# Core analysis
# ---------------------------------------------------------------------------

def _safe(df: pd.DataFrame, col: str, default=0.0) -> pd.Series:
    if col in df.columns:
        return pd.to_numeric(df[col], errors="coerce").fillna(default)
    return pd.Series([default] * len(df), index=df.index)


def _find_col(columns, candidates):
    for c in candidates:
        if c in columns:
            return c
    return None


def _compute_clean_cv(df: pd.DataFrame) -> pd.DataFrame:
    """Recompute CV over active seeds only. Mutates df to add clean_cv column."""
    ret_col = _find_col(df.columns, ["test_cumulative_return", "test_return"])
    shr_col = _find_col(df.columns, ["test_sharpe_ratio", "test_sharpe"])
    tr_col  = _find_col(df.columns, ["test_trade_rate", "trade_rate"])

    if not (ret_col and shr_col and tr_col):
        df["clean_cv"] = df.get("test_return_cv_by_config", np.nan)
        return df

    active_mask = (
        (pd.to_numeric(df[shr_col], errors="coerce") > ACTIVE_SHARPE_MIN) &
        (pd.to_numeric(df[tr_col],  errors="coerce") > ACTIVE_TRADE_MIN)
    )
    active_df = df[active_mask]

    config_keys = [c for c in ["run_label", "ent_coef"] if c in df.columns]
    if config_keys and not active_df.empty:
        cv_map = (
            active_df.groupby(config_keys)[ret_col]
            .apply(lambda x: x.std() / x.mean() if len(x) > 1 and x.mean() != 0 else np.nan)
            .reset_index()
            .rename(columns={ret_col: "clean_cv"})
        )
        df = df.merge(cv_map, on=config_keys, how="left")
    else:
        if not active_df.empty and ret_col in active_df.columns:
            ret_vals  = pd.to_numeric(active_df[ret_col], errors="coerce")
            single_cv = ret_vals.std() / ret_vals.mean() if ret_vals.mean() != 0 else np.nan
        else:
            single_cv = np.nan
        df["clean_cv"] = single_cv

    return df


def _gate_pass(row: pd.Series, gate: dict) -> bool:
    if gate["id"] == 4:
        val_col  = _find_col(row.index, ["val_actionable_accuracy",  "val_accuracy"])
        test_col = _find_col(row.index, ["test_actionable_accuracy", "test_accuracy"])
        if not (val_col and test_col):
            return False
        drift = abs(float(row[val_col]) - float(row[test_col]))
        return drift <= gate["threshold"]
    col = gate.get("col")
    if not col or col not in row.index or pd.isna(row[col]):
        return False
    v = float(row[col])
    op = gate["op"]
    if op == ">=":    return v >= gate["threshold"]
    if op == "<=":    return v <= gate["threshold"]
    if op == "<":     return v <  gate["threshold"]
    if op == ">":     return v >  gate["threshold"]
    if op == "between": return gate["threshold"][0] <= v <= gate["threshold"][1]
    return False


def _apply_gates(df: pd.DataFrame) -> pd.DataFrame:
    df = _compute_clean_cv(df)
    gate_cols = []
    for gate in GATES:
        col_name = f"gate_{gate['id']}_pass"
        df[col_name] = df.apply(lambda row, g=gate: _gate_pass(row, g), axis=1)
        gate_cols.append(col_name)
    df["gates_passed"] = df[gate_cols].sum(axis=1).astype(int)
    df["all_gates"]    = df["gates_passed"] == len(GATES)
    return df


def _overtrade_check(df: pd.DataFrame) -> dict:
    tr_col = _find_col(df.columns, ["test_trade_rate", "trade_rate"])
    cap_col = _find_col(df.columns, ["max_weight_delta_per_step"])

    result = {
        "trade_rate_col": tr_col,
        "cap_set": False,
        "cap_value": None,
        "median_trade_rate": None,
        "pct_target": 0.0,
        "pct_overtrade": 0.0,
        "pct_undertrade": 0.0,
    }

    if cap_col and cap_col in df.columns:
        cap_vals = pd.to_numeric(df[cap_col], errors="coerce")
        result["cap_set"]   = bool((cap_vals > 0).any())
        result["cap_value"] = float(cap_vals.max()) if result["cap_set"] else 0.0

    if tr_col:
        tr = pd.to_numeric(df[tr_col], errors="coerce")
        result["median_trade_rate"] = float(tr.median())
        n = len(df)
        result["pct_target"]    = float((tr.between(TRADE_RATE_LOW, TRADE_RATE_HIGH)).mean() * 100)
        result["pct_overtrade"] = float((tr > TRADE_RATE_HIGH).mean() * 100)
        result["pct_undertrade"] = float((tr < TRADE_RATE_LOW).mean() * 100)

    return result


def _generalization_gap(df: pd.DataFrame) -> dict:
    val_acc  = _safe(df, "val_actionable_accuracy")
    test_acc = _safe(df, "test_actionable_accuracy")
    val_sh   = _safe(df, "val_sharpe_ratio")
    test_sh  = _safe(df, "test_sharpe_ratio")
    val_al   = _safe(df, "val_alpha_vs_qqq")
    test_al  = _safe(df, "test_alpha_vs_qqq")
    val_ret  = _safe(df, "val_cumulative_return", default=np.nan)
    test_ret = _safe(df, "test_cumulative_return", default=np.nan)

    return {
        "acc_drift_mean":     float((val_acc - test_acc).mean()),
        "sharpe_gap_mean":    float((val_sh  - test_sh).mean()),
        "alpha_gap_mean":     float((val_al  - test_al).mean()),
        "val_sharpe_mean":    float(val_sh.mean()),
        "test_sharpe_mean":   float(test_sh.mean()),
        "val_alpha_mean":     float(val_al.mean()),
        "test_alpha_mean":    float(test_al.mean()),
        "val_ret_mean":       float(val_ret.mean()),
        "test_ret_mean":      float(test_ret.mean()),
        "pct_positive_alpha": float((test_al > 0).mean() * 100),
    }


def _seed_stability(df: pd.DataFrame) -> dict:
    if "seed" not in df.columns or df["seed"].nunique() < 2:
        return {"seed_count": 1, "rating": "INSUFFICIENT"}

    test_sh = _safe(df, "test_sharpe_ratio")
    cv_sh   = float(test_sh.std() / max(abs(test_sh.mean()), 1e-8))

    raw_cv  = _safe(df, "test_return_cv_by_config", default=np.nan)
    clean_cv = _safe(df, "clean_cv", default=np.nan)

    if cv_sh < 0.3:
        rating = "HIGH"
    elif cv_sh < 0.7:
        rating = "MODERATE"
    else:
        rating = "LOW"

    active_count = int(
        ((pd.to_numeric(df.get("test_sharpe_ratio", pd.Series([])), errors="coerce") > ACTIVE_SHARPE_MIN) &
         (pd.to_numeric(df.get("test_trade_rate",   pd.Series([])), errors="coerce") > ACTIVE_TRADE_MIN)).sum()
    ) if "test_sharpe_ratio" in df.columns else 0

    return {
        "seed_count":    int(df["seed"].nunique()),
        "active_seeds":  active_count,
        "sharpe_cv":     cv_sh,
        "raw_cv_mean":   float(raw_cv.mean()),
        "clean_cv_mean": float(clean_cv.mean()),
        "rating":        rating,
    }


def _parameter_impact(df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    params  = ["ent_coef", "timesteps", "learning_rate",
               "max_weight_delta_per_step", "reward_hold_penalty_scale",
               "reward_turnover_penalty_scale"]
    varying = [p for p in params if p in df.columns and df[p].nunique() > 1]
    metrics = [m for m in [
        "test_sharpe_ratio", "test_alpha_vs_qqq",
        "test_actionable_accuracy", "test_trade_rate",
        "clean_cv",
    ] if m in df.columns]
    results = {}
    for p in varying:
        results[p] = (
            df.groupby(p)[metrics]
            .mean()
            .round(4)
            .sort_index()
        )
    return results


def _ticker_summary(df: pd.DataFrame) -> pd.DataFrame:
    if "ticker" not in df.columns:
        return pd.DataFrame()
    metrics = [m for m in [
        "test_sharpe_ratio", "test_alpha_vs_qqq",
        "test_actionable_accuracy", "test_trade_rate",
        "gates_passed",
    ] if m in df.columns]
    return (
        df.groupby("ticker")[metrics]
        .agg(["mean", "max"])
        .round(4)
    )


def _champion_block(df: pd.DataFrame) -> dict | None:
    champions = df[df["all_gates"] == True]  # noqa: E712
    if champions.empty:
        return None
    rank_col = _find_col(df.columns, ["test_sharpe_ratio", "test_sharpe"])
    if rank_col:
        champions = champions.sort_values(rank_col, ascending=False)
    row = champions.iloc[0]

    label_col = _find_col(df.columns, ["run_label", "label"])
    seed_col  = _find_col(df.columns, ["seed"])
    tick_col  = _find_col(df.columns, ["ticker", "symbol"])

    return {
        "label":      row[label_col] if label_col else "unknown",
        "seed":       int(row[seed_col]) if seed_col and not pd.isna(row[seed_col]) else "?",
        "ticker":     row[tick_col].upper() if tick_col and not pd.isna(row[tick_col]) else "?",
        "sharpe":     float(row[rank_col]) if rank_col else np.nan,
        "alpha":      float(row["test_alpha_vs_qqq"]) if "test_alpha_vs_qqq" in row.index else np.nan,
        "accuracy":   float(row["test_actionable_accuracy"]) if "test_actionable_accuracy" in row.index else np.nan,
        "win_rate":   float(row["test_trade_win_rate"]) if "test_trade_win_rate" in row.index else np.nan,
        "trade_rate": float(row["test_trade_rate"]) if "test_trade_rate" in row.index else np.nan,
        "clean_cv":   float(row["clean_cv"]) if "clean_cv" in row.index and not pd.isna(row["clean_cv"]) else np.nan,
        "n_champions": len(champions),
        "row": row,
    }


def _next_steps(df: pd.DataFrame, gap: dict, stab: dict, overtrade: dict, champion: dict | None) -> list[str]:
    steps = []

    # Cap not set
    if not overtrade["cap_set"]:
        steps.append(
            "CRITICAL — max_weight_delta_per_step not set (0.0). "
            "This is the root cause of 99%+ trade rates. Add --max-weight-delta-per-step 0.10 "
            "to all sweeps. Reward penalty tuning has zero effect without this cap."
        )

    # Overtrade
    if overtrade["median_trade_rate"] and overtrade["median_trade_rate"] > 0.80:
        steps.append(
            f"Overtrade detected (median {overtrade['median_trade_rate']:.1%}). "
            "Verify --max-weight-delta-per-step 0.10 is in the sweep command and check leaderboard column."
        )

    # Under-trade / inactivity collapse
    if overtrade["median_trade_rate"] is not None and overtrade["median_trade_rate"] < 0.10:
        steps.append(
            "Inactivity collapse — agent is not trading. "
            "If penalties are 0, the reward signal may be too weak for this ticker. "
            "Try higher ent_coef (0.05, 0.08) and more timesteps (60k) before changing reward config."
        )

    # CV instability
    if stab["rating"] == "LOW" and stab["seed_count"] < 5:
        steps.append(
            f"CV instability with only {stab['seed_count']} seeds. "
            "CV gate requires ≥ 5 seeds to produce a stable estimate. Add more seeds before diagnosing."
        )
    elif stab["rating"] == "LOW":
        steps.append(
            f"Structural CV instability (CV={stab['sharpe_cv']:.2f}). "
            "Check val vs test regime returns — if val return << train return, parquet may start too late (AMD pattern). "
            "Delete cache and rebuild from 2015."
        )

    # Alpha deficit
    if gap["pct_positive_alpha"] < 40:
        steps.append(
            f"Alpha gate failing on {100 - gap['pct_positive_alpha']:.0f}% of configs. "
            "If trade rate is in range, the signal is real but transaction costs are eating alpha. "
            "Check reward_ignore_transaction_cost setting."
        )

    # Drift
    if gap["acc_drift_mean"] > 0.08:
        steps.append(
            f"Val→test accuracy drift is {gap['acc_drift_mean']:.3f} (threshold 0.05). "
            "Run regime analysis: compare val vs test period returns and volatility. "
            "If val return >> test return, this is regime overfitting — not leakage."
        )

    # Stationary features
    if "use_stationary_features" in df.columns:
        raw_runs = (pd.to_numeric(df["use_stationary_features"], errors="coerce") == 0).sum()
        if raw_runs > 0:
            steps.append(
                f"{raw_runs} runs used raw feature space (use_stationary_features=False). "
                "All new sweeps must use --use-stationary-features. Raw 10-feature space is deprecated."
            )

    # Champion found — promotion steps
    if champion:
        steps.append(
            f"Champion found (seed={champion['seed']}, Sharpe={champion['sharpe']:.3f}). "
            "Run promotion pipeline: sanity_scan.py → manually write ensemble_config.json "
            "(generate_ensemble_config.py label filter is unreliable) → run_exp9_walkforward.py "
            "(update TICKER_CONFIG first)."
        )
    elif not steps:
        steps.append(
            "No champion and no clear blocker identified. "
            "Review the gate breakdown above and check which gate is failing most consistently."
        )

    return steps


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------

def generate_report(df: pd.DataFrame, label_filter: str | None = None, ticker_filter: str | None = None) -> str:
    lines = []

    # Filter
    total_rows = len(df)
    if label_filter:
        label_col = _find_col(df.columns, ["run_label", "label"])
        if label_col:
            df = df[df[label_col].str.contains(label_filter, na=False)]
    if ticker_filter:
        tick_col = _find_col(df.columns, ["ticker", "symbol"])
        if tick_col:
            df = df[df[tick_col].str.upper() == ticker_filter.upper()]

    if df.empty:
        return f"\n{SEP}\n  No rows match the filter criteria.\n{SEP}\n"

    df = _apply_gates(df)

    gap       = _generalization_gap(df)
    stab      = _seed_stability(df)
    overtrade = _overtrade_check(df)
    champion  = _champion_block(df)
    params    = _parameter_impact(df)
    tickers   = _ticker_summary(df)
    steps     = _next_steps(df, gap, stab, overtrade, champion)

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    # Header
    lines += [
        f"\n{SEP}",
        f"  QUANT PROFESSIONAL REPORT",
        f"{SEP}",
        f"  Generated : {timestamp}",
        f"  Rows      : {len(df)} / {total_rows} total",
    ]
    if label_filter:
        lines.append(f"  Label     : '{label_filter}'")
    if ticker_filter:
        lines.append(f"  Ticker    : {ticker_filter.upper()}")
    lines += [
        f"  Seeds     : {stab['seed_count']} unique  ({stab['active_seeds']} active)",
        f"  Algorithm : SAC (Stable Baselines3)",
        "",
    ]

    # Gate pass rates
    lines += [LINE, "  GATE PASS RATES (6/6 required for promotion)", LINE]
    for gate in GATES:
        col_name = f"gate_{gate['id']}_pass"
        rate = df[col_name].mean() if col_name in df.columns else 0.0
        bar  = _bar(rate)
        note = ""
        if gate["id"] == 5:
            note = "  ← uses clean_cv (active seeds only)"
        if gate["id"] == 6:
            note = "  ← blocks degenerate always-long"
        lines.append(f"  Gate {gate['id']} ({gate['name']:<22})  [{bar}]  {rate:.0%}{note}")
    n_champ = df["all_gates"].sum()
    lines += [f"\n  Configs with 6/6 gates : {n_champ} / {len(df)}", ""]

    # CV diagnostic
    lines += [LINE, "  CV STABILITY DIAGNOSTIC", LINE]
    raw_cv_mean   = df["test_return_cv_by_config"].mean() if "test_return_cv_by_config" in df.columns else np.nan
    clean_cv_mean = df["clean_cv"].mean() if "clean_cv" in df.columns else np.nan
    lines += [
        f"  Raw CV (all seeds)     : {_fmt(raw_cv_mean)}  {'← INFLATED by collapsed seeds' if raw_cv_mean > 1.0 else ''}",
        f"  Clean CV (active only) : {_fmt(clean_cv_mean)}  {_gate_sym(clean_cv_mean < 1.0) if not np.isnan(clean_cv_mean) else ''}",
        f"  Active seeds           : {stab['active_seeds']} / {len(df)} rows  (Sharpe > 0, trade_rate > 10%)",
        f"  Stability rating       : {stab['rating']}",
        "",
    ]

    # Overtrade diagnostic
    tr_col = overtrade["trade_rate_col"]
    if tr_col:
        lines += [LINE, f"  TRADE RATE DISTRIBUTION  (target: {TRADE_RATE_LOW:.0%}–{TRADE_RATE_HIGH:.0%})", LINE]
        for label, pct in [
            (f"Overtrade   (> {TRADE_RATE_HIGH:.0%})",                      overtrade["pct_overtrade"]),
            (f"Target zone ({TRADE_RATE_LOW:.0%}–{TRADE_RATE_HIGH:.0%})", overtrade["pct_target"]),
            (f"Under-trade (< {TRADE_RATE_LOW:.0%})",                       overtrade["pct_undertrade"]),
        ]:
            count = int(pct / 100 * len(df))
            bar   = _bar(pct / 100)
            lines.append(f"  {label:<40}  [{bar}]  {count:3d} rows  ({pct:.0f}%)")

        cap_status = (
            f"cap=0.0 ← STRUCTURAL BUG" if not overtrade["cap_set"]
            else f"cap={overtrade['cap_value']:.2f} ✅"
        )
        lines += [
            f"\n  Median trade rate          : {_fmt(overtrade['median_trade_rate'], '.1%') if overtrade['median_trade_rate'] is not None else 'N/A'}",
            f"  max_weight_delta_per_step  : {cap_status}",
            "",
        ]

    # Generalization
    lines += [LINE, "  GENERALIZATION  (val → test)", LINE]
    acc_sym    = _gate_sym(abs(gap["acc_drift_mean"]) <= 0.05)
    sharpe_sym = _gate_sym(gap["test_sharpe_mean"] > 0)
    alpha_sym  = _gate_sym(gap["pct_positive_alpha"] >= 50)
    lines += [
        f"  Val Sharpe (mean)     : {_fmt(gap['val_sharpe_mean'], '.3f')}",
        f"  Test Sharpe (mean)    : {_fmt(gap['test_sharpe_mean'], '.3f')}  {sharpe_sym}",
        f"  Val Alpha (mean)      : {_fmt(gap['val_alpha_mean'], '.4f')}",
        f"  Test Alpha (mean)     : {_fmt(gap['test_alpha_mean'], '.4f')}  {alpha_sym}  ({gap['pct_positive_alpha']:.0f}% configs positive)",
        f"  Accuracy drift (mean) : {_fmt(gap['acc_drift_mean'], '.4f')}  {acc_sym}  (gate threshold 0.05)",
        f"  Sharpe gap (mean)     : {_fmt(gap['sharpe_gap_mean'], '.3f')}",
        "",
    ]

    # Ticker breakdown
    if not tickers.empty:
        lines += [LINE, "  TICKER BREAKDOWN", LINE]
        try:
            lines.append(tickers.to_string())
        except Exception:
            pass
        lines.append("")

    # Parameter impact
    if params:
        lines += [LINE, "  PARAMETER IMPACT ANALYSIS", LINE]
        for param, table in params.items():
            lines.append(f"\n  — {param} —")
            try:
                lines.append(table.to_string())
            except Exception:
                pass
        lines.append("")

    # Top configs
    rank_col = _find_col(df.columns, ["test_sharpe_ratio", "test_sharpe"])
    sort_cols = ["all_gates", rank_col] if rank_col else ["gates_passed"]
    sort_asc  = [False, False] if rank_col else [False]
    ranked    = df.sort_values(sort_cols, ascending=sort_asc).head(10)

    display_cols = [c for c in [
        _find_col(df.columns, ["run_label", "label"]),
        _find_col(df.columns, ["ticker", "symbol"]),
        "seed",
        "test_actionable_accuracy",
        "test_trade_win_rate",
        "test_alpha_vs_qqq",
        "clean_cv",
        rank_col,
        _find_col(df.columns, ["test_trade_rate", "trade_rate"]),
        "gates_passed",
    ] if c and c in df.columns]

    lines += [LINE, "  TOP 10 CONFIGS  (6/6 gates first, then Sharpe)", LINE]
    try:
        pd.set_option("display.max_columns", None)
        pd.set_option("display.width", 160)
        pd.set_option("display.float_format", "{:.4f}".format)
        lines.append(ranked[display_cols].to_string(index=False))
    except Exception:
        pass
    lines.append("")

    # Gate breakdown — top 3
    lines += [LINE, "  GATE BREAKDOWN — TOP 3", LINE]
    label_col = _find_col(df.columns, ["run_label", "label"])
    seed_col  = _find_col(df.columns, ["seed"])
    tr_col2   = _find_col(df.columns, ["test_trade_rate", "trade_rate"])

    for _, row in ranked.head(3).iterrows():
        row_label = row[label_col] if label_col else "?"
        seed_val  = f"  seed={int(row[seed_col])}" if seed_col and not pd.isna(row.get(seed_col, None)) else ""
        gates_n   = int(row["gates_passed"])
        bar_g     = "█" * gates_n + "░" * (len(GATES) - gates_n)

        lines.append(f"\n  [{row_label}{seed_val}]  [{bar_g}] {gates_n}/{len(GATES)}")
        for gate in GATES:
            passed = bool(row[f"gate_{gate['id']}_pass"])
            sym    = _gate_sym(passed)
            if gate["id"] == 4:
                vc = _find_col(row.index, ["val_actionable_accuracy", "val_accuracy"])
                tc = _find_col(row.index, ["test_actionable_accuracy", "test_accuracy"])
                drift = abs(float(row[vc]) - float(row[tc])) if (vc and tc) else np.nan
                detail = f"drift={_fmt(drift)}"
            elif gate["id"] == 5:
                raw_cv   = row.get("test_return_cv_by_config", np.nan)
                clean_cv = row.get("clean_cv", np.nan)
                detail   = f"clean_cv={_fmt(clean_cv)}  (raw_cv={_fmt(raw_cv)})"
            else:
                col = gate.get("col")
                val = row[col] if col and col in row.index else np.nan
                detail = f"value={_fmt(val)}"
            lines.append(f"    {sym}  Gate {gate['id']}: {gate['name']:<22}  {detail}  ({gate['op']} {gate['threshold']})")

        if tr_col2 and tr_col2 in row.index:
            tr_val = float(row[tr_col2])
            if TRADE_RATE_LOW <= tr_val <= TRADE_RATE_HIGH:
                tr_sym = f"✅ {tr_val:.1%}"
            elif tr_val < TRADE_RATE_LOW:
                tr_sym = f"⚠️  {tr_val:.1%}  (under-trade)"
            else:
                tr_sym = f"❌ {tr_val:.1%}  (overtrade)"
            lines.append(f"    🔁  Trade rate: {tr_sym}")

    lines.append("")

    # Champion or no champion
    lines += [SEP]
    if champion:
        lines += [
            "  ✅  CHAMPION IDENTIFIED",
            SEP,
            f"  Label       : {champion['label']}",
            f"  Ticker      : {champion['ticker']}   Seed : {champion['seed']}",
            f"  Sharpe      : {_fmt(champion['sharpe'], '.4f')}",
            f"  Alpha vs QQQ: {_fmt(champion['alpha'], '.4f')}",
            f"  Accuracy    : {_fmt(champion['accuracy'], '.4f')}   Win Rate : {_fmt(champion['win_rate'], '.4f')}",
            f"  Trade Rate  : {_fmt(champion['trade_rate'], '.1%')}",
            f"  Clean CV    : {_fmt(champion['clean_cv'], '.4f')}",
            f"  Champions   : {champion['n_champions']} configs pass all 6 gates",
        ]
    else:
        lines += [
            "  ⚠️  NO CHAMPION — no config passed all 6 gates.",
        ]
        # Closest near-miss
        if "gates_passed" in df.columns:
            best_gates = int(df["gates_passed"].max())
            near_miss  = df[df["gates_passed"] == best_gates]
            failing    = [g for g in GATES if not near_miss.iloc[0].get(f"gate_{g['id']}_pass", False)]
            if failing:
                lines.append(f"  Closest     : {best_gates}/6 gates. Failing: {', '.join(g['name'] for g in failing)}")

    # Next steps
    lines += [
        "",
        LINE,
        "  RECOMMENDED NEXT STEPS",
        LINE,
        "",
    ]
    for i, step in enumerate(steps, 1):
        lines.append(f"  {i}. {step}")
    lines.append("")

    # Promotion pipeline reminder if champion
    if champion:
        lines += [
            LINE,
            "  PROMOTION PIPELINE",
            LINE,
            "",
            "  1. python scripts/sanity_scan.py",
            f"  2. Manually write staging/models/ensemble_config.json",
            f"     (generate_ensemble_config.py label filter is unreliable — always verify seeds)",
            f"  3. Update TICKER_CONFIG in scripts/run_exp9_walkforward.py",
            f"     — leaderboard: data/experiment_leaderboard.csv",
            f"     — top_seeds: [champion seeds from this sweep]",
            f"     — sweep_label: '{champion['label']}'",
            f"  4. python scripts/run_exp9_walkforward.py --ticker {champion['ticker'].lower()}",
            "",
        ]

    lines.append(SEP + "\n")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Stage 1 gate report (unchanged interface, improved output)
# ---------------------------------------------------------------------------

def generate_stage1_gate_report(gate_payload: dict, source_path: Path | None = None) -> str:
    timestamp   = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    source_text = str(source_path) if source_path else "(in-memory)"

    verdict       = str(gate_payload.get("verdict", "unknown"))
    baseline_pass = bool(gate_payload.get("baseline_gate_passed", False))
    trading_pass  = bool(gate_payload.get("trading_gate_passed", False))
    baseline_chks = gate_payload.get("baseline_checks", []) or []
    trading_chks  = gate_payload.get("trading_checks", []) or []

    lines = [
        f"\n{SEP}",
        f"  STAGE 1 GATE REPORT",
        f"{SEP}",
        f"  Generated : {timestamp}",
        f"  Source    : {source_text}",
        f"  Verdict   : {verdict.upper()}",
        f"  Baseline  : {_gate_sym(baseline_pass)}  Trading : {_gate_sym(trading_pass)}",
        "",
        LINE,
        "  BASELINE GATE  (supervised directional accuracy > NVDA reference 50.5%)",
        LINE,
    ]

    if baseline_chks:
        lines.append(f"  {'Ticker':<8} {'Passed':<8} {'Model':<6} {'Val Acc':>8} {'Test Acc':>8} {'vs NVDA':>8}")
        lines.append(f"  {'-'*7} {'-'*7} {'-'*5} {'-'*8} {'-'*8} {'-'*8}")
        nvda_ref = 0.505
        for chk in baseline_chks:
            best    = chk.get("best_run", {}) if isinstance(chk, dict) else {}
            ticker  = chk.get("ticker", "N/A")
            passed  = chk.get("passed", False)
            model   = best.get("model_type", "N/A")
            val_acc = best.get("val_class_accuracy", best.get("val_r2", np.nan))
            tst_acc = best.get("test_class_accuracy", best.get("test_r2", np.nan))
            delta   = tst_acc - nvda_ref if not np.isnan(tst_acc) else np.nan
            lines.append(
                f"  {ticker:<8} {_gate_sym(passed):<8} {model:<6} "
                f"{_fmt(val_acc, '.3f'):>8} {_fmt(tst_acc, '.3f'):>8} "
                f"{('+' if delta >= 0 else '') + _fmt(delta, '.3f') if not np.isnan(delta) else 'N/A':>8}"
            )
    else:
        lines.append("  No baseline checks found.")

    lines += ["", LINE, "  TRADING GATE", LINE]
    if trading_chks:
        for chk in trading_chks:
            s = chk.get("summary", {}) if isinstance(chk, dict) else {}
            lines += [
                f"  Ticker : {chk.get('ticker', 'N/A')}  Passed : {_gate_sym(chk.get('passed', False))}",
                f"  Policy     : {s.get('supervised_policy_name', 'N/A')}",
                f"  Supervised : {_fmt(s.get('supervised_return', np.nan), '.4f')}  "
                f"Flat : {_fmt(s.get('flat_return', np.nan), '.4f')}  "
                f"Buy&Hold : {_fmt(s.get('buy_hold_return', np.nan), '.4f')}",
                "",
            ]
    else:
        lines.append("  No trading checks found.")

    lines += ["", LINE, "  INTERPRETATION", LINE, ""]
    if verdict == "signal_exists":
        lines.append("  Stage 1 gate clears. Proceed to Stage 2 RL sweep.")
        lines.append("  Run: python src/supervised_baseline_classification.py --ticker <TICKER>")
        lines.append("  Reference: NVDA baseline test_acc=50.5% on 3-class (random=33.3%)")
    else:
        if trading_pass and not baseline_pass:
            lines.append("  Trading behavior looks promising but baseline predictive gate fails.")
            lines.append("  Focus on baseline accuracy before RL escalation.")
        elif baseline_pass and not trading_pass:
            lines.append("  Baseline gate passes but trading execution gate fails.")
            lines.append("  Focus on trade mapping calibration.")
        else:
            lines.append("  Both gates failing. Continue Stage 1 diagnosis.")
            lines.append("  Do not escalate to RL until baseline accuracy > NVDA reference (50.5%).")

    lines += ["", SEP, ""]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# AI interpretation (Gemini)
# ---------------------------------------------------------------------------

def _http_json_post(url: str, payload: dict, headers: dict | None = None, timeout_seconds: int = 45) -> dict:
    raw = json.dumps(payload).encode("utf-8")
    req = request.Request(url=url, data=raw, method="POST")
    req.add_header("Content-Type", "application/json")
    if headers:
        for k, v in headers.items():
            req.add_header(k, v)
    try:
        with request.urlopen(req, timeout=timeout_seconds) as resp:
            body = resp.read().decode("utf-8")
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code}: {detail}") from exc
    except error.URLError as exc:
        raise RuntimeError(f"URL error: {exc.reason}") from exc
    return json.loads(body)


def _generate_ai_interpretation(report_text: str) -> str:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return (
            f"\n{LINE}\n  AI INTERPRETATION — UNAVAILABLE\n{LINE}\n"
            "  Set GEMINI_API_KEY in .env to enable AI analysis.\n"
        )

    model = "gemini-3-flash-preview"
    url   = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"

    # Truncate to avoid Gemini 400 token limit error
    max_chars = 6000
    if len(report_text) > max_chars:
        report_text = report_text[:max_chars] + "\n...[truncated]"

        prompt = (
        "You are a Senior Quantitative Research Lead at a top-tier hedge fund specializing in RL trading systems.\n\n"
        "Review the following SAC RL trading experiment report. The system uses:\n"
        "- SAC (Soft Actor-Critic) algorithm, next_bar execution, max_weight_delta_per_step=0.10 structural cap\n"
        "- 6-gate promotion framework (accuracy, win rate, alpha, drift, CV, trade rate)\n"
        "- Clean CV computed over active seeds only (Sharpe > 0, trade_rate > 10%)\n"
        "- NVDA and AMD currently promoted; AAPL/GOOGL/TSLA failed hold-bias collapse\n\n"
        "Provide a concise professional analysis (2-3 paragraphs):\n"
        "1. STRATEGIC PIVOT: What exactly should change in the next experiment?\n"
        "2. HIDDEN RISK: The most dangerous non-obvious risk in this data.\n"
        "3. CONFIDENCE SCORE: 0-100% confidence this strategy will beat QQQ benchmark.\n\n"
        "Be specific and technical. Reference exact metrics and gate values from the report.\n\n"
        f"REPORT:\n{report_text}"
    )

    payload = {"contents": [{"parts": [{"text": prompt}]}]}

    try:
        print("  Consulting AI Strategic Analyst (Gemini)...")
        response = _http_json_post(url=url, payload=payload)
        candidates = response.get("candidates", [])
        if not candidates:
            return f"\n{LINE}\n  AI INTERPRETATION — No response returned.\n"
        text = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
        return f"\n{LINE}\n  AI STRATEGIC ANALYST INTERPRETATION\n{LINE}\n\n{text}\n"
    except Exception as exc:
        return f"\n{LINE}\n  AI INTERPRETATION — Failed: {exc}\n"


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Quant Professional Report Generator")
    parser.add_argument("--input",           default=str(DEFAULT_LEADERBOARD), help="Path to leaderboard CSV")
    parser.add_argument("--label",           default="",  help="Filter by run_label substring")
    parser.add_argument("--ticker",          default="",  help="Filter by ticker (e.g. NVDA)")
    parser.add_argument("--stage1-gate-json", default="", help="Stage 1 gate JSON path (generates Stage 1 report)")
    parser.add_argument("--output-dir",      default=str(DEFAULT_OUTPUT_DIR), help="Output directory")
    parser.add_argument("--output-name",     default="",  help="Custom filename (default: auto-timestamped)")
    parser.add_argument("--no-ai",           action="store_true", help="Skip AI interpretation")
    args = parser.parse_args()

    stage1_json = str(args.stage1_gate_json).strip()
    if stage1_json:
        gate_path = Path(stage1_json)
        if not gate_path.is_absolute():
            gate_path = ROOT_DIR / gate_path
        if not gate_path.exists():
            print(f"ERROR: Stage 1 gate JSON not found at {gate_path}")
            sys.exit(1)
        gate_payload = json.loads(gate_path.read_text(encoding="utf-8"))
        report = generate_stage1_gate_report(gate_payload=gate_payload, source_path=gate_path)
    else:
        input_path = Path(args.input)
        if not input_path.is_absolute():
            input_path = ROOT_DIR / input_path
        if not input_path.exists():
            print(f"ERROR: Leaderboard not found at {input_path}")
            sys.exit(1)

        df = pd.read_csv(input_path)
        if "leaderboard_version" in df.columns:
            ver = pd.to_numeric(df["leaderboard_version"], errors="coerce")
            if ver.notna().any():
                df = df[ver == ver.max()].copy()

        if df.empty:
            print("ERROR: Leaderboard is empty.")
            sys.exit(1)

        report = generate_report(
            df,
            label_filter=args.label.strip() or None,
            ticker_filter=args.ticker.strip() or None,
        )

        if not args.no_ai:
            report += _generate_ai_interpretation(report)

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    ts       = datetime.now().strftime("%Y-%m-%d-%H%M")
    filename = args.output_name if args.output_name else f"quant-report-{ts}.md"
    out_path = output_dir / filename
    out_path.write_text(report, encoding="utf-8")

    print(report)
    print(f"\nReport saved: {out_path}")


if __name__ == "__main__":
    main()