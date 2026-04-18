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
    train_ratio: float
    val_ratio: float
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


def parse_ticker_mode_map(raw: str) -> dict[str, list[str]]:
    mapping: dict[str, list[str]] = {}
    for token in parse_csv(raw, str):
        if ":" not in token:
            raise ValueError(f"Invalid ticker target-mode map entry '{token}'. Expected TICKER:mode1|mode2")
        ticker, modes_raw = token.split(":", 1)
        modes = [m.strip() for m in modes_raw.split("|") if m.strip()]
        if not modes:
            raise ValueError(f"No target modes specified for ticker {ticker}")
        mapping[ticker.strip().upper()] = modes
    return mapping


def parse_ticker_horizon_map(raw: str) -> dict[str, list[int]]:
    mapping: dict[str, list[int]] = {}
    for token in parse_csv(raw, str):
        if ":" not in token:
            raise ValueError(f"Invalid ticker horizon map entry '{token}'. Expected TICKER:h1|h2")
        ticker, horizons_raw = token.split(":", 1)
        horizons = [int(h.strip()) for h in horizons_raw.split("|") if h.strip()]
        if not horizons:
            raise ValueError(f"No horizons specified for ticker {ticker}")
        mapping[ticker.strip().upper()] = horizons
    return mapping


def parse_split_settings(raw: str) -> list[tuple[float, float]]:
    settings: list[tuple[float, float]] = []
    for token in parse_csv(raw, str):
        if ":" not in token:
            raise ValueError(f"Invalid split setting '{token}'. Expected train_ratio:val_ratio")
        train_raw, val_raw = token.split(":", 1)
        train_ratio = float(train_raw.strip())
        val_ratio = float(val_raw.strip())
        if train_ratio <= 0 or val_ratio <= 0 or (train_ratio + val_ratio) >= 1.0:
            raise ValueError(f"Invalid split setting {token}; require train>0, val>0, train+val<1")
        settings.append((train_ratio, val_ratio))
    return settings


def parse_finalists(raw: str) -> list[tuple[str, str, int, str, float, float, float]]:
    if not raw.strip():
        return []
    finalists: list[tuple[str, str, int, str, float, float, float]] = []
    for token in parse_csv(raw, str):
        parts = token.split(":")
        if len(parts) != 7:
            raise ValueError(
                f"Invalid finalist '{token}'. Expected TICKER:model:horizon:target_mode:threshold:train_ratio:val_ratio"
            )
        finalists.append(
            (
                parts[0].strip().upper(),
                parts[1].strip().lower(),
                int(parts[2].strip()),
                parts[3].strip(),
                float(parts[4].strip()),
                float(parts[5].strip()),
                float(parts[6].strip()),
            )
        )
    return finalists


def safe_num_text(value: float) -> str:
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
        train_ratio=float(payload.get("train_ratio", 0.70)),
        val_ratio=float(payload.get("val_ratio", 0.15)),
        seed=int(payload.get("seed", 42)),
        val_r2=float(payload.get("val_r2", float("nan"))),
        test_r2=float(payload.get("test_r2", float("nan"))),
        path=path,
    )


def pick_finalists(results_dir: Path, tickers: list[str], threshold_map: dict[str, float]) -> list[tuple[str, str, int, str, float, float, float]]:
    best_by_ticker: dict[str, BaselineResult] = {}
    for path in results_dir.glob("stage1_baseline_*.json"):
        record = load_baseline_result(path)
        current = best_by_ticker.get(record.ticker)
        score = (record.val_r2 + record.test_r2) / 2.0
        if current is None:
            best_by_ticker[record.ticker] = record
            continue
        current_score = (current.val_r2 + current.test_r2) / 2.0
        if score > current_score:
            best_by_ticker[record.ticker] = record

    finalists: list[tuple[str, str, int, str, float, float, float]] = []
    for ticker in tickers:
        best = best_by_ticker.get(ticker)
        if best is None:
            finalists.append((ticker, "linear", 1, "raw", threshold_map[ticker], 0.70, 0.15))
        else:
            finalists.append((ticker, best.model_type, best.horizon, best.target_mode, threshold_map[ticker], best.train_ratio, best.val_ratio))
    return finalists


def main() -> int:
    parser = argparse.ArgumentParser(description="Stage 1 Step 9 split-sensitivity and ticker-specialization runner")
    parser.add_argument("--tickers", type=str, default="AAPL,NVDA,AMD")
    parser.add_argument("--reg-model-types", type=str, default="linear,rf,xgb")
    parser.add_argument("--ticker-target-modes", type=str, default="AAPL:raw|vol_norm,NVDA:raw|vol_norm,AMD:vol_norm_clipped")
    parser.add_argument("--ticker-horizons", type=str, default="AAPL:1|2,NVDA:1|2,AMD:2|3|4")
    parser.add_argument("--split-settings", type=str, default="0.70:0.15,0.75:0.10,0.65:0.20")
    parser.add_argument("--base-thresholds", type=str, default="AAPL:0.0030,NVDA:0.0010,AMD:0.0010")
    parser.add_argument("--threshold-deltas", type=str, default="-0.0005,0.0000,0.0005")
    parser.add_argument("--confirmation-seeds", type=str, default="7,13,21,27,123")
    parser.add_argument(
        "--finalists",
        type=str,
        default="",
        help="Optional TICKER:model:horizon:target_mode:threshold:train_ratio:val_ratio list",
    )
    parser.add_argument("--include-news", action="store_true")
    parser.add_argument("--results-dir", type=str, default="results/stage1_step9")
    parser.add_argument("--confirm-results-dir", type=str, default="results/stage1_step9_confirm")
    parser.add_argument("--logs-dir", type=str, default="logs")
    args = parser.parse_args()

    tickers = [t.upper() for t in parse_csv(args.tickers, str)]
    reg_models = [m.lower() for m in parse_csv(args.reg_model_types, str)]
    ticker_target_modes = parse_ticker_mode_map(args.ticker_target_modes)
    ticker_horizons = parse_ticker_horizon_map(args.ticker_horizons)
    split_settings = parse_split_settings(args.split_settings)
    threshold_map = parse_threshold_map(args.base_thresholds)
    threshold_deltas = [float(v) for v in parse_csv(args.threshold_deltas, str)]
    confirm_seeds = [int(v) for v in parse_csv(args.confirmation_seeds, str)]

    results_dir = ROOT / args.results_dir
    confirm_results_dir = ROOT / args.confirm_results_dir
    logs_dir = ROOT / args.logs_dir
    for path in (results_dir, confirm_results_dir, logs_dir):
        path.mkdir(parents=True, exist_ok=True)

    for ticker in tickers:
        if ticker not in threshold_map:
            raise ValueError(f"Missing base threshold for ticker {ticker}")
        if ticker not in ticker_target_modes:
            raise ValueError(f"Missing target modes for ticker {ticker}")
        if ticker not in ticker_horizons:
            raise ValueError(f"Missing horizons for ticker {ticker}")

    threshold_grid: dict[str, list[float]] = {}
    for ticker in tickers:
        base = threshold_map[ticker]
        threshold_grid[ticker] = sorted({round(max(base + delta, 0.0), 6) for delta in threshold_deltas})

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    requests_xgb = "xgb" in reg_models

    phase_names = [
        "Hardware acceleration profile",
        "Split-sensitivity baseline runs",
        "Ticker-specialized baseline runs",
        "Trading eval sweep",
        "Main gate",
        "5-seed confirmation runs",
        "Confirmation gate",
    ]

    print("\n========================================")
    print("Stage 1 Step 9: Split Sensitivity + Specialization")
    print("========================================\n")
    print(f"Tickers: {', '.join(tickers)}")
    print(f"Regression models: {', '.join(reg_models)}")
    print(f"Split settings: {', '.join(f'{tr:.2f}:{vr:.2f}' for tr, vr in split_settings)}")

    phase_bar = tqdm(total=len(phase_names), desc="Step 9 phases", unit="phase", position=0)

    # Phase 1: hardware profile.
    accel_report = get_acceleration_report()
    accel_payload = {
        "generated_at": datetime.now(UTC).isoformat(),
        "python_executable": sys.executable,
        "requested_models": {
            "regression": reg_models,
            "ticker_target_modes": ticker_target_modes,
            "ticker_horizons": ticker_horizons,
            "requests_xgb": requests_xgb,
        },
        "acceleration": accel_report,
    }
    accel_path = logs_dir / f"stage1_step9_hardware_{timestamp}.json"
    accel_path.write_text(json.dumps(accel_payload, indent=2), encoding="utf-8")
    phase_bar.set_postfix_str(f"xgb_cuda={accel_report['xgboost_cuda_enabled']}")
    phase_bar.update(1)

    # Phase 2: split-sensitivity control runs with shared base config.
    split_tasks: list[tuple[str, str, float, float]] = []
    for ticker in tickers:
        for model in reg_models:
            for train_ratio, val_ratio in split_settings:
                split_tasks.append((ticker, model, train_ratio, val_ratio))

    with tqdm(split_tasks, desc="Split sensitivity", unit="run", position=1, leave=False) as pbar:
        for ticker, model, train_ratio, val_ratio in pbar:
            pbar.set_postfix_str(f"{ticker}:{model}:{train_ratio:.2f}/{val_ratio:.2f}")
            output_name = (
                f"stage1_baseline_{ticker}_{model}_raw_h1_tr{safe_num_text(train_ratio)}_vr{safe_num_text(val_ratio)}.json"
            )
            cmd = [
                sys.executable,
                "src/supervised_baseline.py",
                "--ticker",
                ticker,
                "--horizon",
                "1",
                "--model-type",
                model,
                "--target-mode",
                "raw",
                "--train-ratio",
                f"{train_ratio:.4f}",
                "--val-ratio",
                f"{val_ratio:.4f}",
                "--output-dir",
                str(results_dir),
                "--output-name",
                output_name,
                "--seed",
                "42",
            ]
            if args.include_news:
                cmd.append("--use-news")
            run_cmd(cmd, desc=f"split baseline {ticker}/{model}")
    phase_bar.update(1)

    # Phase 3: ticker-specialized target/horizon runs.
    spec_tasks: list[tuple[str, str, str, int]] = []
    for ticker in tickers:
        for model in reg_models:
            for target_mode in ticker_target_modes[ticker]:
                for horizon in ticker_horizons[ticker]:
                    spec_tasks.append((ticker, model, target_mode, horizon))

    base_train_ratio, base_val_ratio = split_settings[0]
    with tqdm(spec_tasks, desc="Ticker specialization", unit="run", position=1, leave=False) as pbar:
        for ticker, model, target_mode, horizon in pbar:
            pbar.set_postfix_str(f"{ticker}:{model}:{target_mode}:h{horizon}")
            output_name = f"stage1_baseline_{ticker}_{model}_{target_mode}_{horizon}h.json"
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
                target_mode,
                "--train-ratio",
                f"{base_train_ratio:.4f}",
                "--val-ratio",
                f"{base_val_ratio:.4f}",
                "--output-dir",
                str(results_dir),
                "--output-name",
                output_name,
                "--seed",
                "42",
            ]
            if args.include_news:
                cmd.append("--use-news")
            run_cmd(cmd, desc=f"specialized baseline {ticker}/{model}/{target_mode}/h{horizon}")
    phase_bar.update(1)

    finalists = parse_finalists(args.finalists)
    if not finalists:
        finalists = pick_finalists(results_dir=results_dir, tickers=tickers, threshold_map=threshold_map)

    # Phase 4: trading eval sweep for finalists.
    trading_tasks: list[tuple[str, str, int, str, float, float, float]] = []
    for ticker, model, horizon, target_mode, _default_thr, train_ratio, val_ratio in finalists:
        for threshold in threshold_grid[ticker]:
            trading_tasks.append((ticker, model, horizon, target_mode, threshold, train_ratio, val_ratio))

    with tqdm(trading_tasks, desc="Trading sweep", unit="run", position=1, leave=False) as pbar:
        for ticker, model, horizon, target_mode, threshold, train_ratio, val_ratio in pbar:
            pbar.set_postfix_str(f"{ticker}:{model}:h{horizon}:{threshold:.4f}")
            out_path = logs_dir / (
                f"stage1_trading_eval_step9_{ticker}_{model}_{target_mode}_h{horizon}_tr{safe_num_text(train_ratio)}_vr{safe_num_text(val_ratio)}_thr{safe_num_text(threshold)}_{timestamp}.json"
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
                "--train-ratio",
                f"{train_ratio:.4f}",
                "--val-ratio",
                f"{val_ratio:.4f}",
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
    gate_json = logs_dir / f"stage1_gate_report_step9_{timestamp}.json"
    gate_md = logs_dir / f"stage1_gate_report_step9_{timestamp}.md"
    run_cmd(
        [
            sys.executable,
            "scripts/stage1_gate.py",
            "--results-dir",
            str(results_dir),
            "--trading-eval-glob",
            f"logs/stage1_trading_eval_step9_*_{timestamp}.json",
            "--output-json",
            str(gate_json),
            "--output-md",
            str(gate_md),
        ],
        desc="main stage1 gate",
    )
    phase_bar.update(1)

    # Phase 6: 5-seed confirmation on finalists.
    confirm_tasks = [
        (ticker, model, horizon, target_mode, threshold, train_ratio, val_ratio, seed)
        for ticker, model, horizon, target_mode, threshold, train_ratio, val_ratio in finalists
        for seed in confirm_seeds
    ]

    with tqdm(confirm_tasks, desc="Confirmation", unit="run", position=1, leave=False) as pbar:
        for ticker, model, horizon, target_mode, threshold, train_ratio, val_ratio, seed in pbar:
            pbar.set_postfix_str(f"{ticker}:{model}:h{horizon}:seed{seed}")
            baseline_output_name = (
                f"stage1_baseline_{ticker}_{model}_{target_mode}_{horizon}h_tr{safe_num_text(train_ratio)}_vr{safe_num_text(val_ratio)}_seed{seed}.json"
            )
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
                    "--train-ratio",
                    f"{train_ratio:.4f}",
                    "--val-ratio",
                    f"{val_ratio:.4f}",
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
                f"stage1_trading_eval_step9_confirm_{ticker}_{model}_{target_mode}_h{horizon}_tr{safe_num_text(train_ratio)}_vr{safe_num_text(val_ratio)}_seed{seed}_thr{safe_num_text(threshold)}_{timestamp}.json"
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
                "--train-ratio",
                f"{train_ratio:.4f}",
                "--val-ratio",
                f"{val_ratio:.4f}",
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
    confirm_gate_json = logs_dir / f"stage1_gate_report_step9_confirm_{timestamp}.json"
    confirm_gate_md = logs_dir / f"stage1_gate_report_step9_confirm_{timestamp}.md"
    run_cmd(
        [
            sys.executable,
            "scripts/stage1_gate.py",
            "--results-dir",
            str(confirm_results_dir),
            "--trading-eval-glob",
            f"logs/stage1_trading_eval_step9_confirm_*_{timestamp}.json",
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
    print("Step 9 Batch Complete")
    print("========================================")
    print(f"Hardware report: {accel_path}")
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
