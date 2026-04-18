#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, UTC
from pathlib import Path

from tqdm import tqdm

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.baseline_agents import get_acceleration_report


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


def parse_finalists(raw: str) -> list[tuple[str, str, float]]:
    if not raw.strip():
        return []
    finalists: list[tuple[str, str, float]] = []
    for token in parse_csv(raw, str):
        parts = token.split(":")
        if len(parts) != 3:
            raise ValueError(f"Invalid finalist '{token}'. Expected TICKER:model:threshold")
        finalists.append((parts[0].strip().upper(), parts[1].strip().lower(), float(parts[2].strip())))
    return finalists


def safe_threshold_text(value: float) -> str:
    return f"{value:.4f}".replace("-", "m").replace(".", "p")


def run_cmd(cmd: list[str], desc: str) -> None:
    result = subprocess.run(cmd, cwd=ROOT)
    if result.returncode != 0:
        raise RuntimeError(f"Command failed ({desc}): {' '.join(cmd)}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Stage 1 Step 7 recommended experiment batch runner")
    parser.add_argument("--tickers", type=str, default="AAPL,NVDA,AMD")
    parser.add_argument("--reg-model-types", type=str, default="linear,rf")
    parser.add_argument("--clf-model-types", type=str, default="rf")
    parser.add_argument("--horizon", type=int, default=1)
    parser.add_argument("--class-threshold", type=float, default=0.0005)
    parser.add_argument("--base-thresholds", type=str, default="AAPL:0.0030,NVDA:0.0010,AMD:0.0010")
    parser.add_argument("--threshold-deltas", type=str, default="-0.0005,0.0000,0.0005")
    parser.add_argument("--confirmation-seeds", type=str, default="7,13,21")
    parser.add_argument("--finalists", type=str, default="", help="Optional TICKER:model:threshold list")
    parser.add_argument("--include-news", action="store_true")
    parser.add_argument("--results-dir", type=str, default="results/stage1_step7")
    parser.add_argument("--confirm-results-dir", type=str, default="results/stage1_step7_confirm")
    parser.add_argument("--logs-dir", type=str, default="logs")
    parser.add_argument("--sessions-dir", type=str, default="sessions")
    args = parser.parse_args()

    tickers = [t.upper() for t in parse_csv(args.tickers, str)]
    reg_models = [m.lower() for m in parse_csv(args.reg_model_types, str)]
    clf_models = [m.lower() for m in parse_csv(args.clf_model_types, str)]
    threshold_map = parse_threshold_map(args.base_thresholds)
    threshold_deltas = [float(v) for v in parse_csv(args.threshold_deltas, str)]
    confirm_seeds = [int(v) for v in parse_csv(args.confirmation_seeds, str)]

    results_dir = ROOT / args.results_dir
    confirm_results_dir = ROOT / args.confirm_results_dir
    logs_dir = ROOT / args.logs_dir
    sessions_dir = ROOT / args.sessions_dir
    for path in (results_dir, confirm_results_dir, logs_dir, sessions_dir):
        path.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")

    for ticker in tickers:
        if ticker not in threshold_map:
            raise ValueError(f"Missing base threshold for ticker {ticker}")

    threshold_grid: dict[str, list[float]] = {}
    for ticker in tickers:
        base = threshold_map[ticker]
        grid = sorted({round(max(base + delta, 0.0), 6) for delta in threshold_deltas})
        threshold_grid[ticker] = grid

    finalists = parse_finalists(args.finalists)
    if not finalists:
        finalists = [(t, reg_models[0], threshold_map[t]) for t in tickers]
    requests_xgb = ("xgb" in reg_models) or ("xgb" in clf_models)

    phase_names = [
        "Hardware acceleration profile",
        "Regression baselines",
        "Classification baselines",
        "Narrow trading sweep (+simple rules)",
        "Main gate",
        "3-seed finalist confirmation",
    ]

    print("\n========================================")
    print("Stage 1 Step 7: Recommended Batch")
    print("========================================\n")
    print(f"Tickers: {', '.join(tickers)}")
    print(f"Regression models: {', '.join(reg_models)}")
    print(f"Classification models: {', '.join(clf_models)}")
    print(f"Horizon: {args.horizon}")
    print(f"Include news: {bool(args.include_news)}")
    print(f"Threshold deltas: {', '.join(f'{x:.4f}' for x in threshold_deltas)}")
    print(f"GPU-capable model requested (xgb): {requests_xgb}")

    phase_bar = tqdm(total=len(phase_names), desc="Step 7 phases", unit="phase", position=0)

    # Phase 1: hardware profile.
    accel_report = get_acceleration_report()
    accel_payload = {
        "generated_at": datetime.now(UTC).isoformat(),
        "python_executable": sys.executable,
        "requested_models": {
            "regression": reg_models,
            "classification": clf_models,
            "requests_xgb": requests_xgb,
        },
        "acceleration": accel_report,
        "notes": {
            "xgboost_models": "rf uses CPU only; xgb may use CUDA when available",
            "sklearn_models": "linear/rf/svm/mlp use CPU",
        },
    }
    accel_path = logs_dir / f"stage1_step7_hardware_{timestamp}.json"
    accel_path.write_text(json.dumps(accel_payload, indent=2), encoding="utf-8")
    phase_bar.set_postfix_str(f"xgb_cuda={accel_report['xgboost_cuda_enabled']}")
    phase_bar.update(1)

    # Phase 2: regression baselines.
    reg_tasks = [(ticker, model) for ticker in tickers for model in reg_models]
    with tqdm(reg_tasks, desc="Regression baselines", unit="run", position=1, leave=False) as pbar:
        for ticker, model in pbar:
            pbar.set_postfix_str(f"{ticker}:{model}")
            cmd = [
                sys.executable,
                "src/supervised_baseline.py",
                "--ticker",
                ticker,
                "--horizon",
                str(args.horizon),
                "--model-type",
                model,
                "--output-dir",
                str(results_dir),
                "--seed",
                "42",
            ]
            if args.include_news:
                cmd.append("--use-news")
            run_cmd(cmd, desc=f"regression baseline {ticker}/{model}")
    phase_bar.update(1)

    # Phase 3: classification baselines.
    clf_tasks = [(ticker, model) for ticker in tickers for model in clf_models]
    with tqdm(clf_tasks, desc="Classification baselines", unit="run", position=1, leave=False) as pbar:
        for ticker, model in pbar:
            pbar.set_postfix_str(f"{ticker}:{model}")
            cmd = [
                sys.executable,
                "src/supervised_baseline_classification.py",
                "--ticker",
                ticker,
                "--horizon",
                str(args.horizon),
                "--model-type",
                model,
                "--class-threshold",
                str(args.class_threshold),
                "--output-dir",
                str(results_dir),
                "--seed",
                "42",
            ]
            if args.include_news:
                cmd.append("--use-news")
            run_cmd(cmd, desc=f"classification baseline {ticker}/{model}")
    phase_bar.update(1)

    # Phase 4: narrow trading sweep with simple rules included.
    trading_outputs: list[Path] = []
    sweep_tasks: list[tuple[str, str, float]] = []
    for ticker in tickers:
        for model in reg_models:
            for threshold in threshold_grid[ticker]:
                sweep_tasks.append((ticker, model, threshold))

    with tqdm(sweep_tasks, desc="Trading sweep", unit="run", position=1, leave=False) as pbar:
        for ticker, model, threshold in pbar:
            pbar.set_postfix_str(f"{ticker}:{model}:{threshold:.4f}")
            safe_thr = safe_threshold_text(threshold)
            out_path = logs_dir / f"stage1_trading_eval_step7_{ticker}_{model}_h{args.horizon}_thr{safe_thr}_{timestamp}.json"
            cmd = [
                sys.executable,
                "scripts/evaluate_stage1_trading.py",
                "--tickers",
                ticker,
                "--horizon",
                str(args.horizon),
                "--model-type",
                model,
                "--threshold",
                f"{threshold:.6f}",
                "--include-simple-rules",
                "--output",
                str(out_path),
            ]
            if args.include_news:
                cmd.append("--include-news")
            run_cmd(cmd, desc=f"trading sweep {ticker}/{model}/{threshold:.4f}")
            trading_outputs.append(out_path)
    phase_bar.update(1)

    # Phase 5: gate for main batch.
    gate_json = logs_dir / f"stage1_gate_report_step7_{timestamp}.json"
    gate_md = logs_dir / f"stage1_gate_report_step7_{timestamp}.md"

    run_cmd(
        [
            sys.executable,
            "scripts/stage1_gate.py",
            "--results-dir",
            str(results_dir),
            "--trading-eval-glob",
            f"logs/stage1_trading_eval_step7_*_{timestamp}.json",
            "--output-json",
            str(gate_json),
            "--output-md",
            str(gate_md),
        ],
        desc="main stage1 gate",
    )

    phase_bar.update(1)

    # Phase 6: seed confirmation for finalists.
    confirm_outputs: list[Path] = []
    confirm_tasks = [(ticker, model, threshold, seed) for ticker, model, threshold in finalists for seed in confirm_seeds]
    with tqdm(confirm_tasks, desc="Finalist confirmation", unit="run", position=1, leave=False) as pbar:
        for ticker, model, threshold, seed in pbar:
            pbar.set_postfix_str(f"{ticker}:{model}:seed{seed}")
            baseline_output_name = f"stage1_baseline_{ticker}_{model}_{args.horizon}h_seed{seed}.json"
            run_cmd(
                [
                    sys.executable,
                    "src/supervised_baseline.py",
                    "--ticker",
                    ticker,
                    "--horizon",
                    str(args.horizon),
                    "--model-type",
                    model,
                    "--output-dir",
                    str(confirm_results_dir),
                    "--output-name",
                    baseline_output_name,
                    "--seed",
                    str(seed),
                ],
                desc=f"confirm baseline {ticker}/{model}/seed{seed}",
            )

            out_path = logs_dir / (
                f"stage1_trading_eval_step7_confirm_{ticker}_{model}_seed{seed}_thr{safe_threshold_text(threshold)}_{timestamp}.json"
            )
            cmd = [
                sys.executable,
                "scripts/evaluate_stage1_trading.py",
                "--tickers",
                ticker,
                "--horizon",
                str(args.horizon),
                "--model-type",
                model,
                "--threshold",
                f"{threshold:.6f}",
                "--include-simple-rules",
                "--output",
                str(out_path),
            ]
            if args.include_news:
                cmd.append("--include-news")
            run_cmd(cmd, desc=f"confirm trading {ticker}/{model}/seed{seed}")
            confirm_outputs.append(out_path)

    confirm_gate_json = logs_dir / f"stage1_gate_report_step7_confirm_{timestamp}.json"
    confirm_gate_md = logs_dir / f"stage1_gate_report_step7_confirm_{timestamp}.md"

    run_cmd(
        [
            sys.executable,
            "scripts/stage1_gate.py",
            "--results-dir",
            str(confirm_results_dir),
            "--trading-eval-glob",
            f"logs/stage1_trading_eval_step7_confirm_*_{timestamp}.json",
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
    print("Step 7 Batch Complete")
    print("========================================")
    print(f"Hardware report: {accel_path}")
    print(f"Main gate JSON:  {gate_json}")
    print(f"Main gate MD:    {gate_md}")
    print(f"Confirm gate:    {confirm_gate_json}")
    print("\nHardware acceleration summary:")
    print(f"  xgboost installed:   {accel_report['xgboost_installed']}")
    print(f"  xgboost CUDA active: {accel_report['xgboost_cuda_enabled']}")
    print(f"  torch CUDA active:   {accel_report['torch_cuda_available']}")
    print(f"  torch CUDA devices:  {accel_report['torch_cuda_device_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
