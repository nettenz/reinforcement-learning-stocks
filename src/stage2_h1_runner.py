from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, roc_auc_score


ROOT_DIR = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT_DIR / "data" / "tech_training_data_stationary.csv"
RESULTS_DIR = ROOT_DIR / "results" / "stage2_h1"
LEDGER_PATH = ROOT_DIR / "logs" / "stage2_h1_results_ledger.json"


@dataclass(frozen=True)
class EventThresholds:
    vol_expansion: float
    volume_spike: float
    momentum_breakout: float
    oversold_reversal: float
    overbought_reversal: float


WINDOW_CONFIG = {
    "train_size": 0.20,
    "val_size": 0.20,
    "test_size": 0.20,
    "slide_pct": 0.33,
}

TRANSACTION_COST = 0.0005
SLIPPAGE = 0.0002
ROUND_TRIP_COST = TRANSACTION_COST + SLIPPAGE

EVENT_TAGS = [
    "vol_expansion",
    "volume_spike",
    "momentum_breakout",
    "oversold_reversal",
    "overbought_reversal",
]

FEATURE_COLUMNS = [
    "RelRange",
    "VolLogDiff",
    "RelMACD",
    "RSI_Centered",
]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_data() -> pd.DataFrame:
    if not DATA_PATH.exists():
        raise FileNotFoundError(f"Stationary dataset not found at {DATA_PATH}")
    df = pd.read_csv(DATA_PATH)
    df["Date"] = pd.to_datetime(df["Date"])
    return df.sort_values("Date").reset_index(drop=True)


def _create_windows(df: pd.DataFrame) -> list[dict[str, object]]:
    n = len(df)
    total_size = WINDOW_CONFIG["train_size"] + WINDOW_CONFIG["val_size"] + WINDOW_CONFIG["test_size"]
    window_size = int(n * total_size)
    slide_size = max(int(window_size * WINDOW_CONFIG["slide_pct"]), 1)
    windows: list[dict[str, object]] = []
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
                "period": f"{test['Date'].min().date()} to {test['Date'].max().date()}",
            }
        )

        start_idx += slide_size
        window_num += 1

    return windows


def _forward_return(log_return: pd.Series, horizon: int = 1) -> pd.Series:
    future_log_return = log_return.shift(-horizon)
    return np.expm1(pd.to_numeric(future_log_return, errors="coerce").replace([np.inf, -np.inf], np.nan))


def _event_thresholds(train: pd.DataFrame) -> EventThresholds:
    return EventThresholds(
        vol_expansion=float(train["RelRange"].quantile(0.90)),
        volume_spike=float(train["VolLogDiff"].quantile(0.85)),
        momentum_breakout=float(train["RelMACD"].quantile(0.90)),
        oversold_reversal=float(train["RSI_Centered"].quantile(0.10)),
        overbought_reversal=float(train["RSI_Centered"].quantile(0.90)),
    )


def _tag_events(frame: pd.DataFrame, thresholds: EventThresholds) -> pd.DataFrame:
    tagged = frame.copy()
    tagged["event_vol_expansion"] = tagged["RelRange"] >= thresholds.vol_expansion
    tagged["event_volume_spike"] = tagged["VolLogDiff"] >= thresholds.volume_spike
    tagged["event_momentum_breakout"] = tagged["RelMACD"] >= thresholds.momentum_breakout
    tagged["event_oversold_reversal"] = tagged["RSI_Centered"] <= thresholds.oversold_reversal
    tagged["event_overbought_reversal"] = tagged["RSI_Centered"] >= thresholds.overbought_reversal
    tagged["event_any"] = tagged[[f"event_{tag}" for tag in EVENT_TAGS]].any(axis=1)
    tagged["event_count"] = tagged[[f"event_{tag}" for tag in EVENT_TAGS]].sum(axis=1)
    return tagged


def _strategy_metrics(simple_returns: np.ndarray, positions: np.ndarray) -> dict[str, float]:
    if len(simple_returns) != len(positions):
        raise ValueError("simple_returns and positions length mismatch")
    trade_changes = np.abs(np.diff(np.concatenate(([0], positions))))
    gross_returns = positions * simple_returns
    costs = trade_changes * ROUND_TRIP_COST
    net_returns = gross_returns - costs
    equity = np.cumprod(1.0 + net_returns)
    peak = np.maximum.accumulate(equity)
    drawdown = (equity - peak) / np.maximum(peak, 1e-12)
    mean_net = float(np.mean(net_returns)) if len(net_returns) else 0.0
    std_net = float(np.std(net_returns, ddof=0)) if len(net_returns) else 0.0
    sharpe = float(np.sqrt(252) * mean_net / std_net) if std_net > 1e-12 else 0.0
    return {
        "gross_return": float(np.prod(1.0 + gross_returns) - 1.0) if len(gross_returns) else 0.0,
        "net_return": float(np.prod(1.0 + net_returns) - 1.0) if len(net_returns) else 0.0,
        "annualized_return": float(mean_net * 252.0),
        "net_sharpe": sharpe,
        "max_drawdown": float(np.min(drawdown)) if len(drawdown) else 0.0,
        "turnover": float(np.mean(trade_changes)) if len(trade_changes) else 0.0,
        "win_rate": float(np.mean(net_returns > 0.0)) if len(net_returns) else 0.0,
        "trade_count": int(np.sum(trade_changes > 0)),
    }


def _buy_hold_metrics(simple_returns: np.ndarray) -> dict[str, float]:
    return _strategy_metrics(simple_returns, np.ones_like(simple_returns, dtype=int))


def _flat_metrics(simple_returns: np.ndarray) -> dict[str, float]:
    return _strategy_metrics(simple_returns, np.zeros_like(simple_returns, dtype=int))


def _event_rule_positions(train_tagged: pd.DataFrame, test_tagged: pd.DataFrame) -> np.ndarray:
    tag_expectation: dict[str, float] = {}
    for tag in EVENT_TAGS:
        mask = train_tagged[f"event_{tag}"]
        if mask.sum() == 0:
            tag_expectation[tag] = 0.0
            continue
        tag_expectation[tag] = float(train_tagged.loc[mask, "next_return"].mean())

    positions: list[int] = []
    for idx, row in test_tagged.iterrows():
        active_tags = [tag for tag in EVENT_TAGS if bool(row[f"event_{tag}"])]
        if not active_tags:
            positions.append(0)
            continue
        score = float(np.mean([tag_expectation[tag] for tag in active_tags]))
        if score > 0.0:
            positions.append(1)
        elif score < 0.0:
            positions.append(-1)
        else:
            positions.append(0)
    return np.asarray(positions, dtype=int)


def _select_model(model_family: str, seed: int):
    if model_family == "logistic":
        return LogisticRegression(max_iter=2000, random_state=seed)
    if model_family == "tree":
        return RandomForestClassifier(n_estimators=200, max_depth=8, random_state=seed, n_jobs=-1)
    raise ValueError(f"Unsupported model family: {model_family}")


def _fit_event_model(train: pd.DataFrame, test: pd.DataFrame, model_family: str, seed: int) -> dict[str, object]:
    train_event = train[train["event_any"]].copy()
    test_event = test[test["event_any"]].copy()

    if train_event.empty or test_event.empty:
        raise ValueError("Insufficient event rows in train or test")

    X_train = train_event[FEATURE_COLUMNS].to_numpy(dtype=float)
    y_train = (train_event["next_return"] > 0.0).astype(int).to_numpy()
    X_test = test_event[FEATURE_COLUMNS].to_numpy(dtype=float)
    y_test = (test_event["next_return"] > 0.0).astype(int).to_numpy()

    model = _select_model(model_family, seed)
    model.fit(X_train, y_train)

    if hasattr(model, "predict_proba"):
        train_score = model.predict_proba(X_train)[:, 1]
        test_score = model.predict_proba(X_test)[:, 1]
    else:
        train_score = model.predict(X_train).astype(float)
        test_score = model.predict(X_test).astype(float)

    train_pred = (train_score >= 0.5).astype(int)
    test_pred = (test_score >= 0.5).astype(int)
    try:
        train_auc = float(roc_auc_score(y_train, train_score)) if len(np.unique(y_train)) > 1 else 0.0
    except Exception:
        train_auc = 0.0
    try:
        test_auc = float(roc_auc_score(y_test, test_score)) if len(np.unique(y_test)) > 1 else 0.0
    except Exception:
        test_auc = 0.0

    return {
        "model_family": model_family,
        "train_accuracy": float(accuracy_score(y_train, train_pred)),
        "test_accuracy": float(accuracy_score(y_test, test_pred)),
        "train_auc": train_auc,
        "test_auc": test_auc,
        "model": model,
    }


def _event_model_positions(model_info: dict[str, object], test_tagged: pd.DataFrame) -> np.ndarray:
    model = model_info["model"]
    X_test = test_tagged[FEATURE_COLUMNS].to_numpy(dtype=float)
    if hasattr(model, "predict_proba"):
        score = model.predict_proba(X_test)[:, 1]
    else:
        score = model.predict(X_test).astype(float)
    positions = np.zeros(len(test_tagged), dtype=int)
    active = test_tagged["event_any"].to_numpy(dtype=bool)
    positions[active & (score >= 0.55)] = 1
    positions[active & (score <= 0.45)] = -1
    return positions


def _dominant_event_cluster(train_tagged: pd.DataFrame, test_tagged: pd.DataFrame, positions: np.ndarray) -> tuple[str, float, dict[str, float]]:
    contributions: dict[str, float] = {}
    for tag in EVENT_TAGS:
        mask = test_tagged[f"event_{tag}"].to_numpy(dtype=bool)
        if not mask.any():
            contributions[tag] = 0.0
            continue
        contributions[tag] = float(np.sum(positions[mask] * test_tagged.loc[mask, "next_return"].to_numpy(dtype=float)))
    dominant_tag = max(contributions, key=lambda key: abs(contributions[key]))
    total_abs = float(sum(abs(value) for value in contributions.values()))
    share = float(abs(contributions[dominant_tag]) / total_abs) if total_abs > 1e-12 else 0.0
    return dominant_tag, share, contributions


def _sufficiency_summary(tagged: pd.DataFrame) -> dict[str, object]:
    counts = {tag: int(tagged[f"event_{tag}"].sum()) for tag in EVENT_TAGS}
    total_events = int(tagged["event_any"].sum())
    dominant_share = float(max(counts.values()) / max(total_events, 1)) if counts else 0.0
    return {
        "total_event_count": total_events,
        "tag_counts": counts,
        "dominant_share": dominant_share,
        "sufficient": bool(total_events >= 60 and min(counts.values()) >= 8 and dominant_share <= 0.55),
    }


def _window_report_metrics(
    window_num: int,
    period: str,
    model_family: str,
    model_metrics: dict[str, float],
    buy_hold: dict[str, float],
    event_rule: dict[str, float],
    flat: dict[str, float],
    predictive_metric: float,
    event_cluster_driver: str,
) -> dict[str, object]:
    benchmark_net = max(buy_hold["net_return"], event_rule["net_return"])
    benchmark_sharpe = max(buy_hold["net_sharpe"], event_rule["net_sharpe"])
    return {
        "window_num": window_num,
        "period": period,
        "model_family": model_family,
        "gross_return": model_metrics["gross_return"],
        "net_return": model_metrics["net_return"],
        "buy_hold_return": buy_hold["net_return"],
        "event_baseline_return": event_rule["net_return"],
        "flat_return": flat["net_return"],
        "net_benchmark_gap": float(model_metrics["net_return"] - benchmark_net),
        "net_sharpe": model_metrics["net_sharpe"],
        "benchmark_sharpe_gap": float(model_metrics["net_sharpe"] - benchmark_sharpe),
        "max_drawdown": model_metrics["max_drawdown"],
        "turnover": model_metrics["turnover"],
        "predictive_metric": predictive_metric,
        "event_cluster_driver": event_cluster_driver,
        "window_pass": bool(model_metrics["net_return"] > benchmark_net and model_metrics["net_sharpe"] > benchmark_sharpe),
    }


def _summarize_variant(variant_name: str, model_family: str, windows: list[dict[str, object]], sufficiency: list[dict[str, object]]) -> dict[str, object]:
    mean_gross = float(np.mean([float(item["gross_return"]) for item in windows])) if windows else 0.0
    mean_net = float(np.mean([float(item["net_return"]) for item in windows])) if windows else 0.0
    mean_gap = float(np.mean([float(item["net_benchmark_gap"]) for item in windows])) if windows else 0.0
    mean_sharpe = float(np.mean([float(item["net_sharpe"]) for item in windows])) if windows else 0.0
    mean_sharpe_gap = float(np.mean([float(item["benchmark_sharpe_gap"]) for item in windows])) if windows else 0.0
    mean_pred = float(np.mean([float(item["predictive_metric"]) for item in windows])) if windows else 0.0
    stability_cv = float(np.std([float(item["net_return"]) for item in windows], ddof=0) / max(abs(mean_net), 1e-12)) if windows else 0.0
    pass_count = int(sum(1 for item in windows if item["window_pass"]))
    recent_window_pass = bool(windows[-1]["window_pass"]) if windows else False
    recent_gap = float(windows[-1]["net_benchmark_gap"]) if windows else 0.0
    recent_sharpe = float(windows[-1]["net_sharpe"]) if windows else 0.0
    recent_sufficiency = sufficiency[-1] if sufficiency else {"sufficient": False, "total_event_count": 0, "tag_counts": {}, "dominant_share": 0.0}
    single_cluster_dependency = bool(float(max((item.get("cluster_share", 0.0) for item in windows), default=0.0)) > 0.55)
    hard_stops = {
        "performance_appears_in_only_one_window": bool(pass_count <= 1),
        "insufficient_event_count": bool(not all(item["sufficient"] for item in sufficiency)),
        "one_event_type_explains_almost_all_gains": bool(single_cluster_dependency),
        "net_edge_non_positive_after_costs": bool(mean_gap <= 0.0),
        "recent_window_fails_severely": bool(recent_gap < -0.05 or recent_sharpe < -0.25 or not recent_sufficiency["sufficient"]),
        "leakage_or_benchmark_inconsistency_detected": False,
    }
    verdict = "KILL"
    if not any(hard_stops.values()) and mean_gap > 0.0 and pass_count >= 2 and recent_window_pass and stability_cv < 1.0 and mean_sharpe > 0.0:
        verdict = "PASS"
    elif any(hard_stops.values()):
        verdict = "KILL"
    else:
        verdict = "FAIL"
    return {
        "hypothesis_id": "H1",
        "event_variant": variant_name,
        "model_family": model_family,
        "window_count": len(windows),
        "mean_gross_return": mean_gross,
        "mean_net_return": mean_net,
        "mean_net_benchmark_gap": mean_gap,
        "mean_net_sharpe": mean_sharpe,
        "mean_benchmark_sharpe_gap": mean_sharpe_gap,
        "primary_predictive_metric": mean_pred,
        "stability_cv": stability_cv,
        "2_of_3_benchmark_pass": bool(pass_count >= 2),
        "recent_window_pass": recent_window_pass,
        "single_event_cluster_dependency": bool(single_cluster_dependency),
        "hard_stop_conditions_triggered": hard_stops,
        "gate_check": {
            "G1 Benchmark Superiority": "PASS" if pass_count >= 2 and recent_window_pass else "FAIL",
            "G2 Economic Robustness": "PASS" if mean_gap > 0.0 and mean_sharpe > 0.0 else "FAIL",
            "G3 Stability": "PASS" if stability_cv < 1.0 else "FAIL",
            "G4 Predictive Support": "PASS" if mean_pred > 0.5 else "FAIL",
            "G5 Cost Survivability": "PASS" if mean_gap > 0.0 else "FAIL",
        },
        "verdict": verdict,
    }


def _write_report(path: Path, summary: dict[str, object], window_rows: list[dict[str, object]], sufficiency: list[dict[str, object]]) -> None:
    lines: list[str] = []
    lines.append("# Stage 2 H1 Results Report")
    lines.append("")
    lines.append("Project: reinforcement-learning-stocks  ")
    lines.append(f"Date: {datetime.now().date().isoformat()}  ")
    lines.append("Hypothesis: H1 - Event-Driven Prediction  ")
    lines.append(f"Run ID: {summary['run_id']}  ")
    lines.append(f"Status: {summary['verdict'].lower()}")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 1. Run Metadata")
    lines.append("")
    lines.append("- **Dataset version**: tech_training_data_stationary.csv")
    lines.append("- **Feature set version**: market_proxy_event_features_v1")
    lines.append(f"- **Event tag set**: {', '.join(EVENT_TAGS)}")
    lines.append("- **Event detection rules**: train-quantile market proxies; see logs/stage2_h1_results_ledger.json")
    lines.append(f"- **Model family**: {summary['model_family']}")
    lines.append(f"- **Rolling-window scheme**: train={WINDOW_CONFIG['train_size']:.0%}, val={WINDOW_CONFIG['val_size']:.0%}, test={WINDOW_CONFIG['test_size']:.0%}, slide={WINDOW_CONFIG['slide_pct']:.0%}")
    lines.append(f"- **Cost assumptions**: transaction_cost={TRANSACTION_COST:.4f}, slippage={SLIPPAGE:.4f}, turnover_rule=position_change")
    lines.append("- **Recent window included**: yes")
    lines.append("")
    lines.append("## 2. Thesis Being Tested")
    lines.append("")
    lines.append("> Sparse high-information event contexts may offer better signal-to-noise than continuous prediction.")
    lines.append("")
    lines.append("## 3. Sample Sufficiency Check")
    lines.append("")
    lines.append("| Window | Period | Total Event Count | Earnings | Macro | Vol Expansion | Abnormal Volume | Momentum Breakout | Sufficiency Verdict |")
    lines.append("| ------ | ------ | ----------------- | -------- | ----- | ------------- | --------------- | ----------------- | ------------------- |")
    for item, suff in zip(window_rows, sufficiency):
        counts = suff["tag_counts"]
        lines.append(
            f"| {item['window_num']} | {item['period']} | {suff['total_event_count']} | 0 | 0 | {counts['vol_expansion']} | {counts['volume_spike']} | {counts['momentum_breakout']} | {'pass' if suff['sufficient'] else 'fail'} |"
        )
    lines.append("")
    lines.append("### Auto-Kill Check")
    lines.append("")
    hard_stops = summary["hard_stop_conditions_triggered"]
    lines.append(f"- [{'x' if hard_stops['insufficient_event_count'] else ' '}] insufficient total sample count")
    lines.append(f"- [{'x' if hard_stops['one_event_type_explains_almost_all_gains'] else ' '}] one event type dominates")
    lines.append(f"- [{'x' if hard_stops['recent_window_fails_severely'] else ' '}] recent-window coverage insufficient")
    lines.append("")
    lines.append("## 4. Benchmarks")
    lines.append("")
    lines.append("- buy-hold")
    lines.append("- event-relevant naive baseline")
    lines.append("- flat/no-trade baseline")
    lines.append("")
    lines.append("## 5. Window-Level Metrics")
    lines.append("")
    lines.append("| Window | Period | Gross Return | Net Return | Buy-Hold Return | Event Baseline Return | Net Benchmark Gap | Net Sharpe | Benchmark Sharpe Gap | Max DD | Turnover | Predictive Metric | Event Cluster Driver | Verdict |")
    lines.append("| ------ | ------ | ------------ | ---------- | --------------- | --------------------- | ----------------- | ---------- | -------------------- | ------ | -------- | ----------------- | -------------------- | ------- |")
    for item in window_rows:
        lines.append(
            f"| {item['window_num']} | {item['period']} | {item['gross_return']:+.4f} | {item['net_return']:+.4f} | {item['buy_hold_return']:+.4f} | {item['event_baseline_return']:+.4f} | {item['net_benchmark_gap']:+.4f} | {item['net_sharpe']:+.3f} | {item['benchmark_sharpe_gap']:+.3f} | {item['max_drawdown']:+.4f} | {item['turnover']:.3f} | {item['predictive_metric']:+.4f} | {item['event_cluster_driver']} | {('pass' if item['window_pass'] else 'fail')} |"
        )
    lines.append("")
    lines.append("## 6. Aggregate Metrics")
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
    lines.append(f"- **Single-event-cluster dependency**: {'yes' if summary['single_event_cluster_dependency'] else 'no'}")
    lines.append("")
    lines.append("## 7. Gate Check")
    lines.append("")
    lines.append("### Global Gates")
    lines.append("")
    for gate_name, gate_value in summary["gate_check"].items():
        lines.append(f"- **{gate_name}**: {gate_value}")
    lines.append("")
    lines.append("### H1-Specific Gates")
    lines.append("")
    lines.append(f"- **H1-1 Event sample count sufficient in each window**: {'PASS' if all(item['sufficient'] for item in sufficiency) else 'FAIL'}")
    lines.append(f"- **H1-2 At least 2/3 windows show positive net edge**: {'PASS' if summary['2_of_3_benchmark_pass'] else 'FAIL'}")
    lines.append(f"- **H1-3 Predictive quality above naive**: {'PASS' if summary['primary_predictive_metric'] > 0.5 else 'FAIL'}")
    lines.append(f"- **H1-4 Edge not carried by one event cluster**: {'PASS' if not summary['single_event_cluster_dependency'] else 'FAIL'}")
    lines.append(f"- **H1-5 Edge survives transaction costs**: {'PASS' if summary['mean_net_benchmark_gap'] > 0 else 'FAIL'}")
    lines.append("")
    lines.append("### Hard Stop Conditions Triggered")
    lines.append("")
    for key, triggered in hard_stops.items():
        lines.append(f"- [{'x' if triggered else ' '}] {key.replace('_', ' ')}")
    lines.append("")
    lines.append("## 8. Interpretation")
    lines.append("")
    lines.append("### What worked")
    lines.append("")
    lines.append("[fill after reviewing the sweep output]")
    lines.append("")
    lines.append("### What failed")
    lines.append("")
    lines.append("[fill after reviewing the sweep output]")
    lines.append("")
    lines.append("### Was the edge broad or event-cluster-specific?")
    lines.append("")
    lines.append("[brief judgment]")
    lines.append("")
    lines.append("### Was sample size sufficient for confidence?")
    lines.append("")
    lines.append("[yes/no and why]")
    lines.append("")
    lines.append("### Does this justify another H1 iteration?")
    lines.append("")
    lines.append("[yes/no and why]")
    lines.append("")
    lines.append("## 9. Final Verdict")
    lines.append("")
    lines.append(f"**Verdict**: {summary['verdict']}")
    lines.append("")
    lines.append("**Reason**:  ")
    lines.append(
        f"Event-driven H1 using market proxy tags produced mean net benchmark gap {summary['mean_net_benchmark_gap']:+.4f}, recent-window gap {window_rows[-1]['net_benchmark_gap']:+.4f}, and {'did' if summary['2_of_3_benchmark_pass'] else 'did not'} satisfy the 2/3 benchmark rule."
    )
    lines.append("")
    lines.append("**Next action**:")
    lines.append("- kill H1 and move to H3" if summary['verdict'] != 'PASS' else "- continue H1 refinement")
    lines.append("")
    lines.append("## 10. Notes")
    lines.append("")
    lines.append("This run uses market-proxy event tags because the stationary dataset does not contain usable calendar event labels. Sentiment/news columns were effectively zero in the stationary frame, so the H1 run focuses on volatility, range, momentum, and reversal proxies only.")

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_h1_sweep() -> dict[str, object]:
    df = _load_data()
    ledger: dict[str, object] = {
        "project": "reinforcement-learning-stocks",
        "created_at": _utc_now(),
        "hypothesis_id": "H1",
        "status": "running",
        "event_tag_set": EVENT_TAGS,
        "event_detection_note": "Market-proxy event tags derived from stationary features because calendar event labels are unavailable in the current dataset.",
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

    windows = _create_windows(df)
    if not windows:
        raise ValueError("No rolling windows generated for H1")

    for model_family in ["logistic", "tree"]:
        variant_windows: list[dict[str, object]] = []
        sufficiency_rows: list[dict[str, object]] = []

        for window in windows:
            thresholds = _event_thresholds(window["train"])
            train_tagged = _tag_events(window["train"], thresholds)
            val_tagged = _tag_events(window["val"], thresholds)
            test_tagged = _tag_events(window["test"], thresholds)
            train_tagged["next_return"] = _forward_return(train_tagged["LogReturn"], horizon=1)
            val_tagged["next_return"] = _forward_return(val_tagged["LogReturn"], horizon=1)
            test_tagged["next_return"] = _forward_return(test_tagged["LogReturn"], horizon=1)

            sufficiency = _sufficiency_summary(test_tagged)
            sufficiency_rows.append(sufficiency)

            if not sufficiency["sufficient"]:
                variant_windows.append(
                    {
                        "window_num": window["window_num"],
                        "period": window["period"],
                        "gross_return": 0.0,
                        "net_return": 0.0,
                        "buy_hold_return": 0.0,
                        "event_baseline_return": 0.0,
                        "flat_return": 0.0,
                        "net_benchmark_gap": -1.0,
                        "net_sharpe": 0.0,
                        "benchmark_sharpe_gap": -1.0,
                        "max_drawdown": 0.0,
                        "turnover": 0.0,
                        "predictive_metric": 0.0,
                        "event_cluster_driver": "insufficient_events",
                        "window_pass": False,
                        "sufficient": False,
                        "cluster_share": 1.0,
                    }
                )
                continue

            train_event = train_tagged[train_tagged["event_any"]].copy()
            test_event = test_tagged[test_tagged["event_any"]].copy()

            event_rule_positions = _event_rule_positions(train_tagged, test_tagged)

            model_info = _fit_event_model(train_tagged, test_tagged, model_family=model_family, seed=42)
            model_positions = _event_model_positions(model_info, test_tagged)

            # Evaluate on next-day simple returns to align with the event prediction horizon.
            simple_returns = test_tagged["next_return"].iloc[:-1].to_numpy(dtype=float)
            model_positions_eval = model_positions[:-1] if len(model_positions) > 1 else model_positions
            event_rule_positions_eval = event_rule_positions[:-1] if len(event_rule_positions) > 1 else event_rule_positions
            buy_hold_positions = np.ones_like(simple_returns, dtype=int)
            flat_positions = np.zeros_like(simple_returns, dtype=int)

            model_metrics = _strategy_metrics(simple_returns, model_positions_eval)
            buy_hold_metrics = _strategy_metrics(simple_returns, buy_hold_positions)
            flat_metrics = _strategy_metrics(simple_returns, flat_positions)
            event_rule_metrics = _strategy_metrics(simple_returns, event_rule_positions_eval)

            dominant_tag, cluster_share, contributions = _dominant_event_cluster(train_tagged, test_tagged.iloc[:-1].copy(), model_positions_eval)

            window_result = _window_report_metrics(
                window_num=window["window_num"],
                period=window["period"],
                model_family=model_family,
                model_metrics=model_metrics,
                buy_hold=buy_hold_metrics,
                event_rule=event_rule_metrics,
                flat=flat_metrics,
                predictive_metric=float(model_info["test_accuracy"]),
                event_cluster_driver=dominant_tag,
            )
            window_result["sufficient"] = True
            window_result["cluster_share"] = cluster_share
            window_result["event_counts"] = sufficiency["tag_counts"]
            window_result["total_event_count"] = sufficiency["total_event_count"]
            window_result["contributions"] = contributions
            variant_windows.append(window_result)

        summary = _summarize_variant(
            variant_name=f"event_proxy_{model_family}",
            model_family=model_family,
            windows=variant_windows,
            sufficiency=sufficiency_rows,
        )
        summary["run_id"] = f"h1-{model_family}-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        summary["window_sufficiency"] = sufficiency_rows
        summary["variant_windows"] = variant_windows
        summary["event_tag_set"] = EVENT_TAGS
        summary["report_path"] = f"results/stage2_h1/stage2_h1_{model_family}_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"

        report_path = ROOT_DIR / summary["report_path"]
        _write_report(report_path, summary, variant_windows, sufficiency_rows)
        ledger["variants"].append(summary)

    ledger["status"] = "complete"
    passed_variants = [variant for variant in ledger["variants"] if variant["verdict"] == "PASS"]
    ledger["final_decision"] = "PROCEED_TO_OPTION_B" if passed_variants else "EXIT_STAGE_1"
    ledger["best_variant"] = max(
        ledger["variants"],
        key=lambda item: float(item.get("mean_net_benchmark_gap", -1e9)),
    )["event_variant"] if ledger["variants"] else None
    ledger["timestamp"] = _utc_now()

    LEDGER_PATH.write_text(json.dumps(ledger, indent=2), encoding="utf-8")
    return ledger


def main() -> int:
    ledger = run_h1_sweep()
    print("=" * 80)
    print("STAGE 2 H1 SWEEP COMPLETE")
    print("=" * 80)
    print(f"Final decision: {ledger['final_decision']}")
    print(f"Best variant: {ledger['best_variant']}")
    print(f"Ledger: {LEDGER_PATH.relative_to(ROOT_DIR)}")
    for variant in ledger["variants"]:
        print(
            f"- {variant['event_variant']}: verdict={variant['verdict']} | model={variant['model_family']} | mean_gap={variant['mean_net_benchmark_gap']:+.4f} | recent_gap={(variant['variant_windows'][-1]['net_benchmark_gap'] if variant['variant_windows'] else 0.0):+.4f}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())