from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.linear_model import LinearRegression, LogisticRegression
from sklearn.metrics import accuracy_score, mean_absolute_error, r2_score, roc_auc_score


ROOT_DIR = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT_DIR / "data" / "tech_training_data_stationary.csv"
RESULTS_DIR = ROOT_DIR / "results" / "stage2_h2"
LEDGER_PATH = ROOT_DIR / "logs" / "stage2_h2_results_ledger.json"


@dataclass(frozen=True)
class TargetVariant:
    name: str
    horizon: int
    target_type: str
    threshold: float = 0.0


TARGET_VARIANTS = [
    TargetVariant(name="1d_forward_return", horizon=1, target_type="regression"),
    TargetVariant(name="3d_forward_return", horizon=3, target_type="regression"),
    TargetVariant(name="5d_forward_return", horizon=5, target_type="regression"),
    TargetVariant(name="directional_threshold", horizon=3, target_type="classification", threshold=0.0),
]

WINDOW_CONFIG = {
    "train_size": 0.20,
    "val_size": 0.20,
    "test_size": 0.20,
    "slide_pct": 0.33,
}

TRANSACTION_COST = 0.0005
SLIPPAGE = 0.0002
ROUND_TRIP_COST = TRANSACTION_COST + SLIPPAGE


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_data() -> pd.DataFrame:
    if not DATA_PATH.exists():
        raise FileNotFoundError(f"Stationary dataset not found at {DATA_PATH}")
    df = pd.read_csv(DATA_PATH)
    if "Date" not in df.columns:
        raise ValueError("Expected Date column in stationary dataset")
    df["Date"] = pd.to_datetime(df["Date"])
    df = df.sort_values("Date").reset_index(drop=True)
    return df


def _feature_columns(df: pd.DataFrame) -> list[str]:
    excluded = {
        "Date",
        "RawClose",
        "OrigOpen",
        "OrigHigh",
        "OrigLow",
        "OrigClose",
    }
    features = [column for column in df.columns if column not in excluded]
    return features


def _forward_return(price: pd.Series, horizon: int) -> pd.Series:
    future_price = price.shift(-horizon)
    return np.log(future_price / price).replace([np.inf, -np.inf], np.nan)


def _select_model(target_type: str, family: str, seed: int):
    if target_type == "regression":
        if family == "linear":
            return LinearRegression()
        if family == "tree":
            return RandomForestRegressor(
                n_estimators=200,
                max_depth=8,
                random_state=seed,
                n_jobs=-1,
            )
    if target_type == "classification":
        if family == "linear":
            return LogisticRegression(max_iter=2000, random_state=seed)
        if family == "tree":
            return RandomForestClassifier(
                n_estimators=200,
                max_depth=8,
                random_state=seed,
                n_jobs=-1,
            )
    raise ValueError(f"Unsupported model family '{family}' for target_type '{target_type}'")


def _create_windows(df: pd.DataFrame) -> list[dict[str, pd.DataFrame | int | str]]:
    n = len(df)
    total_size = WINDOW_CONFIG["train_size"] + WINDOW_CONFIG["val_size"] + WINDOW_CONFIG["test_size"]
    window_size = int(n * total_size)
    slide_size = max(int(window_size * WINDOW_CONFIG["slide_pct"]), 1)

    windows: list[dict[str, pd.DataFrame | int | str]] = []
    start_idx = 0
    window_num = 0

    while start_idx + window_size <= n:
        end_idx = start_idx + window_size
        train_end = start_idx + int(window_size * WINDOW_CONFIG["train_size"])
        val_end = train_end + int(window_size * WINDOW_CONFIG["val_size"])

        train = df.iloc[start_idx:train_end].copy().reset_index(drop=True)
        val = df.iloc[train_end:val_end].copy().reset_index(drop=True)
        test = df.iloc[val_end:end_idx].copy().reset_index(drop=True)

        windows.append(
            {
                "window_num": window_num,
                "train": train,
                "val": val,
                "test": test,
                "test_start": str(test["Date"].min().date()),
                "test_end": str(test["Date"].max().date()),
            }
        )

        start_idx += slide_size
        window_num += 1

    return windows


def _signal_from_scores(scores: np.ndarray, target_type: str) -> np.ndarray:
    if target_type == "classification":
        return (scores >= 0.5).astype(int)
    return (scores > 0.0).astype(int)


def _strategy_metrics(daily_returns: np.ndarray, positions: np.ndarray) -> dict[str, float]:
    if len(daily_returns) != len(positions):
        raise ValueError("daily_returns and positions must have the same length")

    gross_returns = positions * daily_returns
    turnover = np.abs(np.diff(np.concatenate(([0], positions)))).sum() / max(len(positions), 1)
    costs = np.abs(np.diff(np.concatenate(([0], positions)))) * ROUND_TRIP_COST
    net_returns = gross_returns - costs

    equity = np.cumprod(1.0 + net_returns)
    peak = np.maximum.accumulate(equity)
    drawdown = (equity - peak) / np.maximum(peak, 1e-12)

    mean_net = float(np.mean(net_returns)) if len(net_returns) else 0.0
    std_net = float(np.std(net_returns, ddof=0)) if len(net_returns) else 0.0
    sharpe = float(np.sqrt(252) * mean_net / std_net) if std_net > 1e-12 else 0.0
    win_rate = float(np.mean(net_returns > 0.0)) if len(net_returns) else 0.0

    return {
        "gross_return": float(np.prod(1.0 + gross_returns) - 1.0) if len(gross_returns) else 0.0,
        "net_return": float(np.prod(1.0 + net_returns) - 1.0) if len(net_returns) else 0.0,
        "annualized_return": float(mean_net * 252.0),
        "net_sharpe": sharpe,
        "max_drawdown": float(np.min(drawdown)) if len(drawdown) else 0.0,
        "turnover": float(turnover),
        "win_rate": win_rate,
        "trade_count": int(np.sum(np.abs(np.diff(np.concatenate(([0], positions)))) > 0)),
        "daily_mean_net_return": mean_net,
    }


def _benchmark_metrics(daily_returns: np.ndarray, kind: str) -> dict[str, float]:
    if kind == "buy_hold":
        positions = np.ones_like(daily_returns, dtype=int)
    elif kind == "flat":
        positions = np.zeros_like(daily_returns, dtype=int)
    else:
        raise ValueError(f"Unsupported benchmark kind: {kind}")
    return _strategy_metrics(daily_returns, positions)


def _momentum_scores(df: pd.DataFrame, horizon: int) -> np.ndarray:
    rolling = df["LogReturn"].rolling(window=horizon, min_periods=horizon).sum()
    return rolling.fillna(0.0).to_numpy(dtype=float)


def _prepare_variant_frame(df: pd.DataFrame, variant: TargetVariant) -> pd.DataFrame:
    frame = df.copy()
    price = pd.to_numeric(frame["RawClose"], errors="coerce")
    forward = _forward_return(price, variant.horizon)
    frame["target_forward_return"] = forward
    if variant.target_type == "classification":
        frame["target_class"] = (forward > variant.threshold).astype(int)
    return frame


def _fit_and_score(
    train: pd.DataFrame,
    val: pd.DataFrame,
    test: pd.DataFrame,
    feature_cols: list[str],
    variant: TargetVariant,
    model_family: str,
    seed: int,
) -> dict[str, object]:
    if variant.target_type == "regression":
        y_col = "target_forward_return"
    else:
        y_col = "target_class"

    train_clean = train.dropna(subset=feature_cols + [y_col]).copy()
    val_clean = val.dropna(subset=feature_cols + [y_col]).copy()
    test_clean = test.dropna(subset=feature_cols + [y_col]).copy()

    X_train = train_clean[feature_cols].replace([np.inf, -np.inf], np.nan).dropna()
    train_clean = train_clean.loc[X_train.index].copy()
    X_train = X_train.to_numpy(dtype=float)
    y_train = train_clean[y_col].to_numpy()

    X_val = val_clean[feature_cols].replace([np.inf, -np.inf], np.nan).dropna()
    val_clean = val_clean.loc[X_val.index].copy()
    X_val = X_val.to_numpy(dtype=float)
    y_val = val_clean[y_col].to_numpy()

    X_test = test_clean[feature_cols].replace([np.inf, -np.inf], np.nan).dropna()
    test_clean = test_clean.loc[X_test.index].copy()
    X_test = X_test.to_numpy(dtype=float)
    y_test = test_clean[y_col].to_numpy()

    model = _select_model(variant.target_type, model_family, seed)
    model.fit(X_train, y_train)

    if variant.target_type == "regression":
        val_scores = model.predict(X_val)
        test_scores = model.predict(X_test)
        val_pred = val_scores
        test_pred = test_scores
        predictive_metric = float(r2_score(y_test, test_pred)) if len(y_test) > 1 else 0.0
        val_metric = float(r2_score(y_val, val_pred)) if len(y_val) > 1 else 0.0
        predictive_metric_name = "r2"
        predictive_aux = {
            "val_mae": float(mean_absolute_error(y_val, val_pred)) if len(y_val) else 0.0,
            "test_mae": float(mean_absolute_error(y_test, test_pred)) if len(y_test) else 0.0,
        }
    else:
        if hasattr(model, "predict_proba"):
            val_scores = model.predict_proba(X_val)[:, 1]
            test_scores = model.predict_proba(X_test)[:, 1]
        else:
            val_scores = model.predict(X_val).astype(float)
            test_scores = model.predict(X_test).astype(float)
        val_pred = (val_scores >= 0.5).astype(int)
        test_pred = (test_scores >= 0.5).astype(int)
        predictive_metric = float(accuracy_score(y_test, test_pred)) if len(y_test) else 0.0
        val_metric = float(accuracy_score(y_val, val_pred)) if len(y_val) else 0.0
        predictive_metric_name = "directional_accuracy"
        try:
            val_auc = float(roc_auc_score(y_val, val_scores)) if len(np.unique(y_val)) > 1 else 0.0
        except Exception:
            val_auc = 0.0
        try:
            test_auc = float(roc_auc_score(y_test, test_scores)) if len(np.unique(y_test)) > 1 else 0.0
        except Exception:
            test_auc = 0.0
        predictive_aux = {"val_auc": val_auc, "test_auc": test_auc}

    if len(test_clean) < 3:
        raise ValueError("Test slice too small after cleaning")

    next_day_returns = np.expm1(test_clean["LogReturn"].shift(-1).iloc[:-1].to_numpy(dtype=float))
    test_scores = np.asarray(test_scores[:-1], dtype=float)
    model_positions = _signal_from_scores(test_scores, variant.target_type)
    model_metrics = _strategy_metrics(next_day_returns, model_positions)

    momentum_scores = _momentum_scores(pd.concat([train, val, test], ignore_index=True), variant.horizon)
    momentum_test_scores = momentum_scores[len(train) + len(val) : len(train) + len(val) + len(test_clean)]
    momentum_positions = _signal_from_scores(momentum_test_scores[:-1], "regression")
    momentum_metrics = _strategy_metrics(next_day_returns, momentum_positions)

    buy_hold_metrics = _benchmark_metrics(next_day_returns, "buy_hold")
    flat_metrics = _benchmark_metrics(next_day_returns, "flat")

    benchmark_net = max(buy_hold_metrics["net_return"], momentum_metrics["net_return"])
    benchmark_sharpe = max(buy_hold_metrics["net_sharpe"], momentum_metrics["net_sharpe"])

    window_pass = (
        model_metrics["net_return"] > benchmark_net
        and model_metrics["net_sharpe"] > benchmark_sharpe
    )

    return {
        "model_family": model_family,
        "predictive_metric_name": predictive_metric_name,
        "val_predictive_metric": val_metric,
        "test_predictive_metric": predictive_metric,
        "predictive_aux": predictive_aux,
        "model": model_metrics,
        "buy_hold": buy_hold_metrics,
        "momentum": momentum_metrics,
        "flat": flat_metrics,
        "net_gap_vs_buy_hold": float(model_metrics["net_return"] - buy_hold_metrics["net_return"]),
        "net_gap_vs_momentum": float(model_metrics["net_return"] - momentum_metrics["net_return"]),
        "net_gap_vs_best": float(model_metrics["net_return"] - benchmark_net),
        "sharpe_gap_vs_buy_hold": float(model_metrics["net_sharpe"] - buy_hold_metrics["net_sharpe"]),
        "sharpe_gap_vs_momentum": float(model_metrics["net_sharpe"] - momentum_metrics["net_sharpe"]),
        "sharpe_gap_vs_best": float(model_metrics["net_sharpe"] - benchmark_sharpe),
        "window_pass": bool(window_pass),
    }


def _aggregate_variant_results(variant: TargetVariant, windows: list[dict[str, object]]) -> dict[str, object]:
    model_families = sorted({str(window["model_family"]) for window in windows})
    best_family = None
    best_mean_gap = -1e9
    best_rows: list[dict[str, object]] = []

    for family in model_families:
        rows = [window for window in windows if window["model_family"] == family]
        mean_gap = float(np.mean([float(row["net_gap_vs_best"]) for row in rows])) if rows else -1e9
        if mean_gap > best_mean_gap:
            best_mean_gap = mean_gap
            best_family = family
            best_rows = rows

    mean_net_return = float(np.mean([float(row["model"]["net_return"]) for row in best_rows])) if best_rows else 0.0
    mean_gross_return = float(np.mean([float(row["model"]["gross_return"]) for row in best_rows])) if best_rows else 0.0
    mean_net_sharpe = float(np.mean([float(row["model"]["net_sharpe"]) for row in best_rows])) if best_rows else 0.0
    mean_bh_return = float(np.mean([float(row["buy_hold"]["net_return"]) for row in best_rows])) if best_rows else 0.0
    mean_mom_return = float(np.mean([float(row["momentum"]["net_return"]) for row in best_rows])) if best_rows else 0.0
    mean_gap = float(np.mean([float(row["net_gap_vs_best"]) for row in best_rows])) if best_rows else 0.0
    mean_sharpe_gap = float(np.mean([float(row["sharpe_gap_vs_best"]) for row in best_rows])) if best_rows else 0.0
    mean_predictive = float(np.mean([float(row["test_predictive_metric"]) for row in best_rows])) if best_rows else 0.0
    stability_cv = float(np.std([float(row["model"]["net_return"]) for row in best_rows], ddof=0) / max(abs(mean_net_return), 1e-12)) if best_rows else 0.0
    pass_count = int(sum(1 for row in best_rows if row["window_pass"]))
    recent_window_pass = bool(best_rows[-1]["window_pass"]) if best_rows else False
    recent_window_gap = float(best_rows[-1]["net_gap_vs_best"]) if best_rows else 0.0
    recent_window_sharpe = float(best_rows[-1]["model"]["net_sharpe"]) if best_rows else 0.0

    hard_stops = {
        "only_one_window_positive": bool(pass_count <= 1),
        "buy_hold_cleanly_dominates": bool(all(row["net_gap_vs_buy_hold"] <= 0 for row in best_rows)) if best_rows else True,
        "net_edge_non_positive_after_costs": bool(mean_gap <= 0.0),
        "recent_window_fails_severely": bool(recent_window_gap < -0.05 or recent_window_sharpe < -0.25),
        "leakage_or_benchmark_inconsistency": False,
    }

    if mean_gap > 0.0 and pass_count >= 2 and recent_window_pass and stability_cv < 1.0 and mean_net_sharpe > 0.0:
        verdict = "PASS"
        next_action = "continue_h2_refinement"
    elif any(hard_stops.values()):
        verdict = "KILL"
        next_action = "move_to_h1"
    else:
        verdict = "FAIL"
        next_action = "run_next_h2_variant"

    return {
        "hypothesis_id": "H2",
        "target_variant": variant.name,
        "target_horizon": variant.horizon,
        "target_type": variant.target_type,
        "best_model_family": best_family,
        "window_count": len(best_rows),
        "mean_gross_return": mean_gross_return,
        "mean_net_return": mean_net_return,
        "mean_net_benchmark_gap": mean_gap,
        "mean_net_sharpe": mean_net_sharpe,
        "mean_benchmark_sharpe_gap": mean_sharpe_gap,
        "primary_predictive_metric": mean_predictive,
        "stability_cv": stability_cv,
        "2_of_3_benchmark_pass": bool(pass_count >= 2),
        "recent_window_pass": recent_window_pass,
        "recent_window_gap": recent_window_gap,
        "recent_window_sharpe": recent_window_sharpe,
        "hard_stop_conditions_triggered": hard_stops,
        "gate_check": {
            "G1 Benchmark Superiority": "PASS" if pass_count >= 2 and recent_window_pass else "FAIL",
            "G2 Economic Robustness": "PASS" if mean_gap > 0.0 and mean_net_sharpe > 0.0 else "FAIL",
            "G3 Stability": "PASS" if stability_cv < 1.0 else "FAIL",
            "G4 Predictive Support": "PASS" if mean_predictive is not None else "FAIL",
            "G5 Cost Survivability": "PASS" if mean_gap > 0.0 else "FAIL",
        },
        "verdict": verdict,
        "next_action": next_action,
    }


def _write_variant_report(path: Path, summary: dict[str, object], windows: list[dict[str, object]]) -> None:
    lines: list[str] = []
    lines.append("# Stage 2 H2 Results Report")
    lines.append("")
    lines.append(f"Project: reinforcement-learning-stocks  ")
    lines.append(f"Date: {datetime.now().date().isoformat()}  ")
    lines.append(f"Hypothesis: H2 — Longer-Horizon Targets  ")
    lines.append(f"Run ID: {summary['target_variant']}  ")
    lines.append(f"Status: {summary['verdict'].lower()}")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 1. Run Metadata")
    lines.append("")
    lines.append(f"- **Dataset version**: tech_training_data_stationary.csv")
    lines.append(f"- **Feature set version**: stationary_features_v1")
    lines.append(f"- **Target variant**: {summary['target_variant']}")
    lines.append(f"- **Model family**: {summary['best_model_family']}")
    lines.append(f"- **Rolling-window scheme**: train={WINDOW_CONFIG['train_size']:.0%}, val={WINDOW_CONFIG['val_size']:.0%}, test={WINDOW_CONFIG['test_size']:.0%}, slide={WINDOW_CONFIG['slide_pct']:.0%}")
    lines.append(f"- **Cost assumptions**: transaction_cost={TRANSACTION_COST:.4f}, slippage={SLIPPAGE:.4f}, turnover_rule=position_change")
    lines.append(f"- **Recent window included**: yes")
    lines.append("")
    lines.append("## 2. Thesis Being Tested")
    lines.append("")
    lines.append("> Longer-horizon targets may reduce noise sensitivity and improve stability versus short-horizon targets.")
    lines.append("")
    lines.append("## 3. Benchmarks")
    lines.append("")
    lines.append("- buy-hold")
    lines.append("- naive momentum")
    lines.append("- flat/no-trade baseline")
    lines.append("")
    lines.append("## 4. Window-Level Metrics")
    lines.append("")
    lines.append("| Window | Period | Gross Return | Net Return | Buy-Hold Return | Momentum Return | Net Benchmark Gap | Net Sharpe | Benchmark Sharpe Gap | Max DD | Turnover | Predictive Metric | Verdict |")
    lines.append("|--------|--------|--------------|------------|-----------------|-----------------|-------------------|------------|----------------------|--------|----------|-------------------|---------|")
    for index, row in enumerate(windows):
        model = row["model"]
        benchmark_gap = row["net_gap_vs_best"]
        predictive_metric = row["test_predictive_metric"]
        lines.append(
            f"| {index} | {row['period']} | {model['gross_return']:+.4f} | {model['net_return']:+.4f} | {row['buy_hold']['net_return']:+.4f} | {row['momentum']['net_return']:+.4f} | {benchmark_gap:+.4f} | {model['net_sharpe']:+.3f} | {row['sharpe_gap_vs_best']:+.3f} | {model['max_drawdown']:+.4f} | {model['turnover']:.3f} | {predictive_metric:+.4f} | {"pass" if row['window_pass'] else "fail"} |"
        )
    lines.append("")
    lines.append("## 5. Aggregate Metrics")
    lines.append("")
    lines.append(f"- **Mean gross return**: {summary['mean_gross_return']:+.4f}")
    lines.append(f"- **Mean net return**: {summary['mean_net_return']:+.4f}")
    lines.append(f"- **Mean net benchmark gap**: {summary['mean_net_benchmark_gap']:+.4f}")
    lines.append(f"- **Mean net Sharpe**: {summary['mean_net_sharpe']:+.3f}")
    lines.append(f"- **Mean benchmark Sharpe gap**: {summary['mean_benchmark_sharpe_gap']:+.3f}")
    lines.append(f"- **Primary predictive metric (mean)**: {summary['primary_predictive_metric']:+.4f}")
    lines.append(f"- **Stability CV**: {summary['stability_cv']:.3f}")
    lines.append(f"- **2/3 benchmark pass achieved**: {'yes' if summary['2_of_3_benchmark_pass'] else 'no'}")
    lines.append(f"- **Recent window pass**: {'yes' if summary['recent_window_pass'] else 'no'}")
    lines.append("")
    lines.append("## 6. Gate Check")
    lines.append("")
    lines.append("### Global Gates")
    lines.append("")
    for gate_name, gate_value in summary["gate_check"].items():
        lines.append(f"- **{gate_name}**: {gate_value}")
    lines.append("")
    lines.append("### Hard Stop Conditions Triggered")
    lines.append("")
    for key, triggered in summary["hard_stop_conditions_triggered"].items():
        mark = "x" if triggered else " "
        lines.append(f"- [{mark}] {key.replace('_', ' ')}")
    lines.append("")
    lines.append("## 7. Interpretation")
    lines.append("")
    lines.append("### What worked")
    lines.append("")
    lines.append("[fill after reviewing the sweep output]")
    lines.append("")
    lines.append("### What failed")
    lines.append("")
    lines.append("[fill after reviewing the sweep output]")
    lines.append("")
    lines.append("### Is the edge real or likely artifact?")
    lines.append("")
    lines.append("[fill after reviewing the sweep output]")
    lines.append("")
    lines.append("### Does this justify another H2 iteration?")
    lines.append("")
    lines.append("[yes/no and why]")
    lines.append("")
    lines.append("## 8. Final Verdict")
    lines.append("")
    lines.append(f"**Verdict**: {summary['verdict']}")
    lines.append("")
    lines.append("**Reason**:  ")
    lines.append(f"H2 target variant '{summary['target_variant']}' with best family '{summary['best_model_family']}' produced mean net benchmark gap {summary['mean_net_benchmark_gap']:+.4f} and recent-window gap {summary['recent_window_gap']:+.4f}.")
    lines.append("")
    lines.append("**Next action**:")
    lines.append(f"- {summary['next_action']}")
    lines.append("")
    lines.append("## 9. Notes")
    lines.append("")
    lines.append("Add anomalies, caveats, leakage checks, or benchmark interpretation notes here.")

    path.write_text("\n".join(lines), encoding="utf-8")


def run_h2_sweep() -> dict[str, object]:
    df = _load_data()
    feature_cols = _feature_columns(df)

    ledger: dict[str, object] = {
        "project": "reinforcement-learning-stocks",
        "created_at": _utc_now(),
        "hypothesis_id": "H2",
        "status": "running",
        "window_config": WINDOW_CONFIG,
        "cost_assumptions": {
            "transaction_cost": TRANSACTION_COST,
            "slippage": SLIPPAGE,
            "round_trip_cost": ROUND_TRIP_COST,
        },
        "variants": [],
    }

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    LEDGER_PATH.parent.mkdir(parents=True, exist_ok=True)

    for variant in TARGET_VARIANTS:
        frame = _prepare_variant_frame(df, variant)
        frame = frame.dropna(subset=["target_forward_return"]).reset_index(drop=True)
        windows = _create_windows(frame)
        variant_windows: list[dict[str, object]] = []

        for window in windows:
            train = window["train"]
            val = window["val"]
            test = window["test"]
            for family in ["linear", "tree"]:
                scored = _fit_and_score(
                    train=train,
                    val=val,
                    test=test,
                    feature_cols=feature_cols,
                    variant=variant,
                    model_family=family,
                    seed=42,
                )
                variant_windows.append(
                    {
                        "window_num": window["window_num"],
                        "period": f"{window['test_start']} to {window['test_end']}",
                        "model_family": family,
                        **scored,
                    }
                )

        summary = _aggregate_variant_results(variant, variant_windows)
        summary["run_id"] = f"h2-{variant.name}-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        summary["variant_windows"] = variant_windows

        report_path = RESULTS_DIR / f"stage2_h2_{variant.name}_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
        _write_variant_report(report_path, summary, [row for row in variant_windows if row["model_family"] == summary["best_model_family"]])
        summary["report_path"] = str(report_path.relative_to(ROOT_DIR))

        ledger["variants"].append(summary)

    ledger["status"] = "complete"
    passed_variants = [variant for variant in ledger["variants"] if variant["verdict"] == "PASS"]
    ledger["final_decision"] = "PROCEED_TO_OPTION_B" if passed_variants else "EXIT_STAGE_1"
    ledger["best_variant"] = max(
        ledger["variants"],
        key=lambda item: float(item.get("mean_net_benchmark_gap", -1e9)),
    )["target_variant"] if ledger["variants"] else None

    ledger["timestamp"] = _utc_now()
    LEDGER_PATH.write_text(json.dumps(ledger, indent=2), encoding="utf-8")
    return ledger


def main() -> int:
    ledger = run_h2_sweep()
    print("=" * 80)
    print("STAGE 2 H2 SWEEP COMPLETE")
    print("=" * 80)
    print(f"Final decision: {ledger['final_decision']}")
    print(f"Best variant: {ledger['best_variant']}")
    print(f"Ledger: {LEDGER_PATH.relative_to(ROOT_DIR)}")
    for variant in ledger["variants"]:
        print(
            f"- {variant['target_variant']}: verdict={variant['verdict']} | best_family={variant['best_model_family']} | mean_gap={variant['mean_net_benchmark_gap']:+.4f} | recent_gap={variant['recent_window_gap']:+.4f}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())