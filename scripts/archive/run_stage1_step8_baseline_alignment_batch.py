#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, UTC
from pathlib import Path

from tqdm import tqdm

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.baseline_agents import get_acceleration_report


@dataclass(frozen=True)
class BaselineResult:
    ticker: str
    model_type: str
    target_mode: str
    horizon: int
    seed: int
    val_r2: float
    test_r2: float
    path: Path


def parse_csv(raw: str, cast=str) -> list:
    values: list = []
    for part in raw.split(","):
        token = part.strip()
        if token:
            values.append(cast(token))
    return values


def parse_threshold_map(raw: str) -> dict[str, float]:
    mapping: dict[str, float] = {}
    for token in parse_csv(raw, str):
        if ":" not in token:
            raise ValueError(f"Invalid threshold entry '{token}'. Expected TICKER:value")
        ticker, value = token.split(":", 1)
        mapping[ticker.strip().upper()] = float(value.strip())
    return mapping


def parse_finalists(raw: str) -> list[tuple[str, str, int, str, float]]:
    if not raw.strip():
        return []
    finalists: list[tuple[str, str, int, str, float]] = []
    for token in parse_csv(raw, str):
        parts = token.split(":")
        if len(parts) != 5:
            raise ValueError(f"Invalid finalist '{token}'. Expected TICKER:model:horizon:target_mode:threshold")
        finalists.append((parts[0].strip().upper(), parts[1].strip().lower(), int(parts[2].strip()), parts[3].strip(), float(parts[4].strip())))
    return finalists


def safe_threshold_text(value: float) -> str:
    return f"{value:.4f}".replace("-", "m").replace(".", "p")


def run_cmd(cmd: list[str], desc: str) -> None:
    result = subprocess.run(cmd, cwd=ROOT)
    if result.returncode != 0:
        raise RuntimeError(f"Command failed ({desc}): {' '.join(cmd)}")


def load_baseline_result(path: Path) -> BaselineResult:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return BaselineResult(
        ticker=str(payload.get("ticker", "unknown")).upper(),
        model_type=str(payload.get("model_type", "unknown")).lower(),
        target_mode=str(payload.get("target_mode", "raw")),
        horizon=int(payload.get("horizon", 0)),
        seed=int(payload.get("seed", 42)),
        val_r2=float(payload.get("val_r2", float("nan"))),
        test_r2=float(payload.get("test_r2", float("nan"))),
        path=path,
    )


def pick_best_target_mode(results_dir: Path, target_modes: list[str]) -> str:
    scores: dict[str, list[float]] = {mode: [] for mode in target_modes}
    for path in results_dir.glob("stage1_baseline_*.json"):
        record = load_baseline_result(path)
        if record.target_mode in scores:
            scores[record.target_mode].append(record.test_r2)

    best_mode = target_modes[0]
    best_score = float("-inf")
    for mode in target_modes:
        values = scores.get(mode, [])
        score = sum(values) / len(values) if values else float("-inf")
        if score > best_score:
            best_score = score
            best_mode = mode
    return best_mode


def pick_finalists(results_dir: Path, tickers: list[str], default_thresholds: dict[str, float], fallback_target_mode: str) -> list[tuple[str, str, int, str, float]]:
    best_by_ticker: dict[str, BaselineResult] = {}
    for path in results_dir.glob("stage1_baseline_*.json"):
        record = load_baseline_result(path)
        current = best_by_ticker.get(record.ticker)
        if current is None or record.test_r2 > current.test_r2:
            best_by_ticker[record.ticker] = record

    finalists: list[tuple[str, str, int, str, float]] = []
    for ticker in tickers:
        best = best_by_ticker.get(ticker)
        if best is None:
            finalists.append((ticker, "linear", 1, fallback_target_mode, default_thresholds[ticker]))
        else:
            finalists.append((ticker, best.model_type, best.horizon, best.target_mode, default_thresholds[ticker]))
    return finalists


def main() -> int:
    parser = argparse.ArgumentParser(description="Stage 1 Step 8 baseline-alignment experiment runner")
    parser.add_argument("--tickers", type=str, default="AAPL,NVDA,AMD")
    parser.add_argument("--reg-model-types", type=str, default="linear,rf,xgb")
    parser.add_argument("--base-horizon", type=int, default=1)
    parser.add_argument("--horizon-sweep", type=str, default="1,2,3")
    parser.add_argument("--target-modes", type=str, default="raw,vol_norm,vol_norm_clipped")
    parser.add_argument("--base-thresholds", type=str, default="AAPL:0.0030,NVDA:0.0010,AMD:0.0010")
    parser.add_argument("--threshold-deltas", type=str, default="-0.0005,0.0000,0.0005")
    parser.add_argument("--confirmation-seeds", type=str, default="7,13,21,27,123")
    parser.add_argument("--finalists", type=str, default="", help="Optional TICKER:model:horizon:target_mode:threshold list")
    parser.add_argument("--include-news", action="store_true")
    parser.add_argument("--results-dir", type=str, default="results/stage1_step8")
    parser.add_argument("--confirm-results-dir", type=str, default="results/stage1_step8_confirm")
    parser.add_argument("--logs-dir", type=str, default="logs")
    args = parser.parse_args()

    tickers = [t.upper() for t in parse_csv(args.tickers, str)]
    reg_models = [m.lower() for m in parse_csv(args.reg_model_types, str)]
    target_modes = [m.strip() for m in parse_csv(args.target_modes, str)]
    horizons = [int(h) for h in parse_csv(args.horizon_sweep, str)]
    threshold_map = parse_threshold_map(args.base_thresholds)
    threshold_deltas = [float(v) for v in parse_csv(args.threshold_deltas, str)]
    confirm_seeds = [int(v) for v in parse_csv(args.confirmation_seeds, str)]

    results_dir = ROOT / args.results_dir
    confirm_results_dir = ROOT / args.confirm_results_dir
    logs_dir = ROOT / args.logs_dir
    for path in (results_dir, confirm_results_dir, logs_dir):
        path.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")

    for ticker in tickers:
        if ticker not in threshold_map:
            raise ValueError(f"Missing base threshold for ticker {ticker}")

    threshold_grid: dict[str, list[float]] = {}
    for ticker in tickers:
        base = threshold_map[ticker]
        threshold_grid[ticker] = sorted({round(max(base + delta, 0.0), 6) for delta in threshold_deltas})

    requests_xgb = "xgb" in reg_models
    phase_names = [
        "Hardware acceleration profile",
        "Experiment A: target engineering ablation",
        "Experiment B: horizon mini-sweep",
        "Trading eval sweep for selected configs",
        "Main gate",
        "Experiment C: 5-seed confirmatory check",
        "Confirmation gate",
    ]

    print("\n========================================")
    print("Stage 1 Step 8: Baseline Alignment Batch")
    print("========================================\n")
    print(f"Tickers: {', '.join(tickers)}")
    print(f"Regression models: {', '.join(reg_models)}")
    print(f"Target modes: {', '.join(target_modes)}")
    print(f"Base horizon: {args.base_horizon}")
    print(f"Horizon sweep: {', '.join(str(h) for h in horizons)}")
    print(f"Include news: {bool(args.include_news)}")
    print(f"Threshold deltas: {', '.join(f'{x:.4f}' for x in threshold_deltas)}")

    phase_bar = tqdm(total=len(phase_names), desc="Step 8 phases", unit="phase", position=0)

    # Phase 1: hardware profile.
    accel_report = get_acceleration_report()
    accel_payload = {
        "generated_at": datetime.now(UTC).isoformat(),
        "python_executable": sys.executable,
        "requested_models": {
            "regression": reg_models,
            "target_modes": target_modes,
            "requests_xgb": requests_xgb,
        },
        "acceleration": accel_report,
    }
    accel_path = logs_dir / f"stage1_step8_hardware_{timestamp}.json"
    accel_path.write_text(json.dumps(accel_payload, indent=2), encoding="utf-8")
    phase_bar.set_postfix_str(f"xgb_cuda={accel_report['xgboost_cuda_enabled']}")
    phase_bar.update(1)

    # Phase 2: experiment A target ablation at base horizon.
    a_tasks = [(ticker, model, target_mode) for ticker in tickers for model in reg_models for target_mode in target_modes]
    with tqdm(a_tasks, desc="ExpA target ablation", unit="run", position=1, leave=False) as pbar:
        for ticker, model, target_mode in pbar:
            pbar.set_postfix_str(f"{ticker}:{model}:{target_mode}")
            output_name = f"stage1_baseline_{ticker}_{model}_{target_mode}_{args.base_horizon}h.json"
            cmd = [
                sys.executable,
                "src/supervised_baseline.py",
                "--ticker",
                ticker,
                "--horizon",
                str(args.base_horizon),
                "--model-type",
                model,
                "--target-mode",
                target_mode,
                "--output-dir",
                str(results_dir),
                "--output-name",
                output_name,
                "--seed",
                "42",
            ]
            if args.include_news:
                cmd.append("--use-news")
            run_cmd(cmd, desc=f"expA baseline {ticker}/{model}/{target_mode}")
    selected_target_mode = pick_best_target_mode(results_dir=results_dir, target_modes=target_modes)
    phase_bar.update(1)

    # Phase 3: experiment B horizon mini-sweep for selected target mode.
    b_tasks = [(ticker, model, horizon) for ticker in tickers for model in reg_models for horizon in horizons]
    with tqdm(b_tasks, desc="ExpB horizon sweep", unit="run", position=1, leave=False) as pbar:
        for ticker, model, horizon in pbar:
            pbar.set_postfix_str(f"{ticker}:{model}:h{horizon}")
            output_name = f"stage1_baseline_{ticker}_{model}_{selected_target_mode}_{horizon}h.json"
            cmd = [
                sys.executable,
                "src/supervised_baseline.py",
                "--ticker",
                ticker,
                "--horizon",
                str(horizon),
                "--model-type",
                model,
                "--target-mode",
                selected_target_mode,
                "--output-dir",
                str(results_dir),
                "--output-name",
                output_name,
                "--seed",
                "42",
            ]
            if args.include_news:
                cmd.append("--use-news")
            run_cmd(cmd, desc=f"expB baseline {ticker}/{model}/h{horizon}")
    phase_bar.update(1)

    finalists = parse_finalists(args.finalists)
    if not finalists:
        finalists = pick_finalists(
            results_dir=results_dir,
            tickers=tickers,
            default_thresholds=threshold_map,
            fallback_target_mode=selected_target_mode,
        )

    # Phase 4: trading eval sweep for selected configs.
    trading_tasks: list[tuple[str, str, int, str, float]] = []
    for ticker, model, horizon, target_mode, _default_thr in finalists:
        for threshold in threshold_grid[ticker]:
            trading_tasks.append((ticker, model, horizon, target_mode, threshold))

    with tqdm(trading_tasks, desc="Trading sweep", unit="run", position=1, leave=False) as pbar:
        for ticker, model, horizon, target_mode, threshold in pbar:
            pbar.set_postfix_str(f"{ticker}:{model}:h{horizon}:{threshold:.4f}")
            out_path = logs_dir / (
                f"stage1_trading_eval_step8_{ticker}_{model}_{target_mode}_h{horizon}_thr{safe_threshold_text(threshold)}_{timestamp}.json"
            )
            cmd = [
                sys.executable,
                "scripts/evaluate_stage1_trading.py",
                "--tickers",
                ticker,
                "--horizon",
                str(horizon),
                "--model-type",
                model,
                "--target-mode",
                target_mode,
                "--seed",
                "42",
                "--threshold",
                f"{threshold:.6f}",
                "--include-simple-rules",
                "--output",
                str(out_path),
            ]
            if args.include_news:
                cmd.append("--include-news")
            run_cmd(cmd, desc=f"trading sweep {ticker}/{model}/h{horizon}/{target_mode}")
    phase_bar.update(1)

    # Phase 5: main gate.
    gate_json = logs_dir / f"stage1_gate_report_step8_{timestamp}.json"
    gate_md = logs_dir / f"stage1_gate_report_step8_{timestamp}.md"
    run_cmd(
        [
            sys.executable,
            "scripts/stage1_gate.py",
            "--results-dir",
            str(results_dir),
            "--trading-eval-glob",
            f"logs/stage1_trading_eval_step8_*_{timestamp}.json",
            "--output-json",
            str(gate_json),
            "--output-md",
            str(gate_md),
        ],
        desc="main stage1 gate",
    )
    phase_bar.update(1)

    # Phase 6: experiment C 5-seed confirmatory checks.
    confirm_tasks = [(ticker, model, horizon, target_mode, threshold, seed) for ticker, model, horizon, target_mode, threshold in finalists for seed in confirm_seeds]
    with tqdm(confirm_tasks, desc="ExpC confirmation", unit="run", position=1, leave=False) as pbar:
        for ticker, model, horizon, target_mode, threshold, seed in pbar:
            pbar.set_postfix_str(f"{ticker}:{model}:h{horizon}:seed{seed}")
            baseline_output_name = f"stage1_baseline_{ticker}_{model}_{target_mode}_{horizon}h_seed{seed}.json"
            run_cmd(
                [
                    sys.executable,
                    "src/supervised_baseline.py",
                    "--ticker",
                    ticker,
                    "--horizon",
                    str(horizon),
                    "--model-type",
                    model,
                    "--target-mode",
                    target_mode,
                    "--output-dir",
                    str(confirm_results_dir),
                    "--output-name",
                    baseline_output_name,
                    "--seed",
                    str(seed),
                ],
                desc=f"confirm baseline {ticker}/{model}/h{horizon}/seed{seed}",
            )

            out_path = logs_dir / (
                f"stage1_trading_eval_step8_confirm_{ticker}_{model}_{target_mode}_h{horizon}_seed{seed}_thr{safe_threshold_text(threshold)}_{timestamp}.json"
            )
            cmd = [
                sys.executable,
                "scripts/evaluate_stage1_trading.py",
                "--tickers",
                ticker,
                "--horizon",
                str(horizon),
                "--model-type",
                model,
                "--target-mode",
                target_mode,
                "--seed",
                str(seed),
                "--threshold",
                f"{threshold:.6f}",
                "--include-simple-rules",
                "--output",
                str(out_path),
            ]
            if args.include_news:
                cmd.append("--include-news")
            run_cmd(cmd, desc=f"confirm trading {ticker}/{model}/h{horizon}/seed{seed}")
    phase_bar.update(1)

    # Phase 7: confirmation gate.
    confirm_gate_json = logs_dir / f"stage1_gate_report_step8_confirm_{timestamp}.json"
    confirm_gate_md = logs_dir / f"stage1_gate_report_step8_confirm_{timestamp}.md"
    run_cmd(
        [
            sys.executable,
            "scripts/stage1_gate.py",
            "--results-dir",
            str(confirm_results_dir),
            "--trading-eval-glob",
            f"logs/stage1_trading_eval_step8_confirm_*_{timestamp}.json",
            "--output-json",
            str(confirm_gate_json),
            "--output-md",
            str(confirm_gate_md),
        ],
        desc="confirmation stage1 gate",
    )
    phase_bar.update(1)

    phase_bar.close()

    print("\n========================================")
    print("Step 8 Batch Complete")
    print("========================================")
    print(f"Hardware report: {accel_path}")
    print(f"Selected target mode: {selected_target_mode}")
    print(f"Main gate JSON:  {gate_json}")
    print(f"Main gate MD:    {gate_md}")
    print(f"Confirm gate:    {confirm_gate_json}")
    print(f"Confirm gate MD: {confirm_gate_md}")
    print("\nHardware acceleration summary:")
    print(f"  xgboost installed:   {accel_report['xgboost_installed']}")
    print(f"  xgboost CUDA active: {accel_report['xgboost_cuda_enabled']}")
    print(f"  torch CUDA active:   {accel_report['torch_cuda_available']}")
    print(f"  torch CUDA devices:  {accel_report['torch_cuda_device_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
