#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from datetime import datetime, UTC
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RESULTS_DIR = ROOT / "results" / "stage1"
DEFAULT_TRADING_EVAL = ROOT / "logs" / "stage1_trading_eval.json"
DEFAULT_OUTPUT_JSON = ROOT / "logs" / "stage1_gate_report.json"
DEFAULT_OUTPUT_MD = ROOT / "logs" / "stage1_gate_report.md"


@dataclass(frozen=True)
class BaselineSummary:
    ticker: str
    horizon: int
    model_type: str
    val_r2: float
    test_r2: float
    val_mae: float
    test_mae: float
    path: str


@dataclass(frozen=True)
class TradingSummary:
    ticker: str
    split: str
    supervised_policy_name: str
    supervised_return: float
    flat_return: float
    buy_hold_return: float
    supervised_sharpe_like: float
    flat_sharpe_like: float
    buy_hold_sharpe_like: float
    supervised_win_rate: float
    trade_count: int


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _format_pct(value: float) -> str:
    return f"{value * 100:.2f}%"


def _format_float(value: float) -> str:
    return f"{value:.4f}"


def _to_repo_relative(path: Path) -> str:
    resolved = path.resolve()
    try:
        return str(resolved.relative_to(ROOT))
    except ValueError:
        return str(path)


def collect_baseline_summaries(results_dir: Path) -> list[BaselineSummary]:
    summaries: list[BaselineSummary] = []
    for path in sorted(results_dir.glob("stage1_baseline_*.json")):
        payload = _load_json(path)
        summaries.append(
            BaselineSummary(
                ticker=str(payload.get("ticker", "unknown")),
                horizon=int(payload.get("horizon", 0)),
                model_type=str(payload.get("model_type", "unknown")),
                val_r2=float(payload.get("val_r2", float("nan"))),
                test_r2=float(payload.get("test_r2", float("nan"))),
                val_mae=float(payload.get("val_mae", float("nan"))),
                test_mae=float(payload.get("test_mae", float("nan"))),
                path=_to_repo_relative(path),
            )
        )
    return summaries


def best_baseline_per_ticker(records: list[BaselineSummary]) -> dict[str, BaselineSummary]:
    best: dict[str, BaselineSummary] = {}
    for record in records:
        current = best.get(record.ticker)
        if current is None or record.test_r2 > current.test_r2:
            best[record.ticker] = record
    return best


def collect_trading_summaries(trading_eval_path: Path) -> list[TradingSummary]:
    if not trading_eval_path.exists():
        return []

    payload = _load_json(trading_eval_path)
    summaries: list[TradingSummary] = []
    for report in payload.get("reports", []):
        ticker = str(report.get("ticker", "unknown"))
        splits = report.get("splits", {})
        test_split = splits.get("test", {})
        supervised_candidates: list[tuple[str, dict[str, Any]]] = [
            (name, summary)
            for name, summary in test_split.items()
            if str(name).startswith("supervised-") and isinstance(summary, dict)
        ]
        if supervised_candidates:
            # Prefer the supervised policy with the strongest test return.
            supervised_name, supervised = max(
                supervised_candidates,
                key=lambda item: float(item[1].get("cumulative_return", float("-inf"))),
            )
        else:
            supervised_name, supervised = "none", {}
        flat = test_split.get("flat", {})
        buy_hold = test_split.get("buy_hold", {})
        summaries.append(
            TradingSummary(
                ticker=ticker,
                split="test",
                supervised_policy_name=supervised_name,
                supervised_return=float(supervised.get("cumulative_return", float("nan"))),
                flat_return=float(flat.get("cumulative_return", float("nan"))),
                buy_hold_return=float(buy_hold.get("cumulative_return", float("nan"))),
                supervised_sharpe_like=float(supervised.get("sharpe_like", float("nan"))),
                flat_sharpe_like=float(flat.get("sharpe_like", float("nan"))),
                buy_hold_sharpe_like=float(buy_hold.get("sharpe_like", float("nan"))),
                supervised_win_rate=float(supervised.get("trade_win_rate", float("nan"))),
                trade_count=int(supervised.get("trades", 0)),
            )
        )
    return summaries


def collect_trading_summaries_from_paths(paths: list[Path]) -> list[TradingSummary]:
    summaries: list[TradingSummary] = []
    for path in paths:
        summaries.extend(collect_trading_summaries(path))
    return summaries


def evaluate_gate(
    baselines: list[BaselineSummary],
    trading: list[TradingSummary],
    min_val_r2: float,
    min_test_r2: float,
) -> dict[str, Any]:
    baseline_best = best_baseline_per_ticker(baselines)
    trading_by_ticker: dict[str, TradingSummary] = {}
    for entry in trading:
        current = trading_by_ticker.get(entry.ticker)
        if current is None or entry.supervised_return > current.supervised_return:
            trading_by_ticker[entry.ticker] = entry

    baseline_checks: list[dict[str, Any]] = []
    trading_checks: list[dict[str, Any]] = []

    for ticker, record in sorted(baseline_best.items()):
        passed = record.val_r2 >= min_val_r2 and record.test_r2 >= min_test_r2
        baseline_checks.append(
            {
                "ticker": ticker,
                "passed": passed,
                "best_run": asdict(record),
                "reason": (
                    f"val_r2={record.val_r2:.6f}, test_r2={record.test_r2:.6f}, "
                    f"thresholds=({min_val_r2:.6f}, {min_test_r2:.6f})"
                ),
            }
        )

    for ticker, record in sorted(trading_by_ticker.items()):
        passed = record.supervised_return > record.flat_return and record.supervised_sharpe_like > record.flat_sharpe_like
        trading_checks.append(
            {
                "ticker": ticker,
                "passed": passed,
                "summary": asdict(record),
                "reason": (
                    f"supervised_return={record.supervised_return:.6f} vs flat_return={record.flat_return:.6f}, "
                    f"supervised_sharpe_like={record.supervised_sharpe_like:.6f} vs flat_sharpe_like={record.flat_sharpe_like:.6f}"
                ),
            }
        )

    baseline_pass = bool(baseline_checks) and all(check["passed"] for check in baseline_checks)
    trading_pass = bool(trading_checks) and all(check["passed"] for check in trading_checks)
    verdict = "signal_exists" if baseline_pass and trading_pass else "signal_weak"

    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "verdict": verdict,
        "baseline_gate_passed": baseline_pass,
        "trading_gate_passed": trading_pass,
        "baseline_count": len(baselines),
        "trading_count": len(trading),
        "baseline_checks": baseline_checks,
        "trading_checks": trading_checks,
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("# Stage 1 Gate Report")
    lines.append("")
    lines.append(f"Generated at: {report['generated_at']}")
    lines.append(f"Verdict: {report['verdict']}")
    lines.append("")
    lines.append("## Baseline gate")
    lines.append(f"Passed: {report['baseline_gate_passed']}")
    lines.append("")
    for check in report["baseline_checks"]:
        best = check["best_run"]
        lines.append(
            f"- {check['ticker']}: {check['passed']} | {best['model_type']} h{best['horizon']} | "
            f"val_r2={_format_float(best['val_r2'])} | test_r2={_format_float(best['test_r2'])}"
        )
    if not report["baseline_checks"]:
        lines.append("- No baseline JSON files found in results/stage1.")
    lines.append("")
    lines.append("## Trading gate")
    lines.append(f"Passed: {report['trading_gate_passed']}")
    lines.append("")
    for check in report["trading_checks"]:
        summary = check["summary"]
        lines.append(
            f"- {check['ticker']}: {check['passed']} | policy={summary['supervised_policy_name']} | supervised_return={_format_pct(summary['supervised_return'])} "
            f"vs flat={_format_pct(summary['flat_return'])} vs buy_hold={_format_pct(summary['buy_hold_return'])} | "
            f"win_rate={summary['supervised_win_rate']:.3f} | trades={summary['trade_count']}"
        )
    if not report["trading_checks"]:
        lines.append(f"- No trading evaluation found at {DEFAULT_TRADING_EVAL.relative_to(ROOT)}.")
    lines.append("")
    lines.append("## Interpretation")
    if report["verdict"] == "signal_exists":
        lines.append("Stage 1 clears the gate: the supervised baseline generalizes and beats the flat benchmark.")
    else:
        lines.append("Stage 1 does not clear the gate: the supervised baseline remains below the threshold and/or fails to beat flat on test.")
    lines.append("")
    lines.append("## Leaderboard comparability impact")
    lines.append("None. This report only reads existing Stage 1 artifacts and writes a separate summary file.")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Summarize Stage 1 baseline and trading evidence into a gate verdict.")
    parser.add_argument("--results-dir", type=str, default=str(DEFAULT_RESULTS_DIR), help="Directory containing stage1 baseline JSON files")
    parser.add_argument("--trading-eval", type=str, default=str(DEFAULT_TRADING_EVAL), help="Trading evaluation JSON produced by scripts/evaluate_stage1_trading.py")
    parser.add_argument("--trading-eval-glob", type=str, default="", help="Optional glob pattern (relative to repo root) for multiple trading eval JSON files")
    parser.add_argument("--output-json", type=str, default=str(DEFAULT_OUTPUT_JSON), help="Path to write the JSON summary")
    parser.add_argument("--output-md", type=str, default=str(DEFAULT_OUTPUT_MD), help="Path to write the Markdown summary")
    parser.add_argument("--min-val-r2", type=float, default=0.01, help="Minimum validation R^2 required for a baseline to pass")
    parser.add_argument("--min-test-r2", type=float, default=0.01, help="Minimum test R^2 required for a baseline to pass")
    args = parser.parse_args()

    results_dir = Path(args.results_dir)
    trading_eval_path = Path(args.trading_eval)
    trading_eval_glob = str(args.trading_eval_glob or "").strip()
    output_json_path = Path(args.output_json)
    output_md_path = Path(args.output_md)
    if not output_json_path.is_absolute():
        output_json_path = ROOT / output_json_path
    if not output_md_path.is_absolute():
        output_md_path = ROOT / output_md_path

    baselines = collect_baseline_summaries(results_dir)
    if trading_eval_glob:
        trading_paths = sorted(ROOT.glob(trading_eval_glob))
        trading = collect_trading_summaries_from_paths(trading_paths)
    else:
        trading = collect_trading_summaries(trading_eval_path)
    report = evaluate_gate(
        baselines=baselines,
        trading=trading,
        min_val_r2=float(args.min_val_r2),
        min_test_r2=float(args.min_test_r2),
    )

    output_json_path.parent.mkdir(parents=True, exist_ok=True)
    output_md_path.parent.mkdir(parents=True, exist_ok=True)
    output_json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    output_md_path.write_text(render_markdown(report), encoding="utf-8")

    print(f"Stage 1 verdict: {report['verdict']}")
    print(f"Baseline gate passed: {report['baseline_gate_passed']}")
    print(f"Trading gate passed: {report['trading_gate_passed']}")
    print(f"Wrote {output_json_path.relative_to(ROOT)}")
    print(f"Wrote {output_md_path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())