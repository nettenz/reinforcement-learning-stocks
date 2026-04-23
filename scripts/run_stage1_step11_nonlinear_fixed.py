#!/usr/bin/env python3
"""Stage 1 Step 11 — non-linear baseline sweep (RF + XGB) on AMD and NVDA.

Runs RF and XGBoost at horizons 1, 2, 3 with a fixed 70/15/15 split and raw
target mode, then evaluates the gate. This directly addresses the blocking
issue: linear models produce negative val_r2 across all tickers and steps.
"""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, UTC
from pathlib import Path

from tqdm import tqdm

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.baseline_agents import get_acceleration_report

TICKERS = ["AMD", "NVDA"]
MODELS = ["rf", "xgb"]
HORIZONS = [1, 2, 3]
TARGET_MODE = "raw"
TRAIN_RATIO = 0.70
VAL_RATIO = 0.15
SEED = 42
RESULTS_DIR = ROOT / "results" / "stage1_step11_nonlinear_fixed"
LOGS_DIR = ROOT / "logs"
MIN_R2 = 0.01


def run_cmd(cmd: list[str], desc: str) -> None:
    result = subprocess.run(cmd, cwd=ROOT)
    if result.returncode != 0:
        raise RuntimeError(f"Command failed ({desc}): {' '.join(cmd)}")


def main() -> int:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    LOGS_DIR.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%SZ")

    print("\n========================================")
    print("Stage 1 Step 11: Non-linear Baseline Sweep (RF + XGB)")
    print("========================================")
    print(f"Tickers:     {', '.join(TICKERS)}")
    print(f"Models:      {', '.join(MODELS)}")
    print(f"Horizons:    {HORIZONS}")
    print(f"Target mode: {TARGET_MODE}")
    print(f"Split:       train={TRAIN_RATIO} / val={VAL_RATIO}")
    print(f"Output:      {RESULTS_DIR.relative_to(ROOT)}\n")

    accel_report = get_acceleration_report()
    accel_path = LOGS_DIR / f"stage1_step11_hardware_{timestamp}.json"
    accel_path.write_text(
        json.dumps(
            {
                "generated_at": datetime.now(UTC).isoformat(),
                "python_executable": sys.executable,
                "acceleration": accel_report,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"Hardware: xgb_cuda={accel_report['xgboost_cuda_enabled']}  torch_cuda={accel_report['torch_cuda_available']}\n")

    tasks = [
        (ticker, model, horizon)
        for ticker in TICKERS
        for model in MODELS
        for horizon in HORIZONS
    ]

    with tqdm(tasks, desc="Baseline runs", unit="run") as pbar:
        for ticker, model, horizon in pbar:
            pbar.set_postfix_str(f"{ticker}:{model}:h{horizon}")
            output_name = f"stage1_baseline_{ticker}_{model}_{TARGET_MODE}_{horizon}h_tr{int(TRAIN_RATIO*10000)}_vr{int(VAL_RATIO*10000)}_seed{SEED}.json"
            run_cmd(
                [
                    sys.executable,
                    "src/supervised_baseline.py",
                    "--ticker", ticker,
                    "--horizon", str(horizon),
                    "--model-type", model,
                    "--target-mode", TARGET_MODE,
                    "--train-ratio", f"{TRAIN_RATIO:.4f}",
                    "--val-ratio", f"{VAL_RATIO:.4f}",
                    "--seed", str(SEED),
                    "--output-dir", str(RESULTS_DIR),
                    "--output-name", output_name,
                ],
                desc=f"baseline {ticker}/{model}/h{horizon}",
            )

    gate_json = LOGS_DIR / f"stage1_gate_report_step11_{timestamp}.json"
    gate_md = LOGS_DIR / f"stage1_gate_report_step11_{timestamp}.md"
    run_cmd(
        [
            sys.executable,
            "scripts/stage1_gate.py",
            "--results-dir", str(RESULTS_DIR),
            "--output-json", str(gate_json),
            "--output-md", str(gate_md),
            "--min-val-r2", str(MIN_R2),
            "--min-test-r2", str(MIN_R2),
        ],
        desc="step11 gate",
    )

    print("\n========================================")
    print("Step 11 Complete")
    print("========================================")
    print(f"Baseline artifacts: {RESULTS_DIR.relative_to(ROOT)}/")
    print(f"Gate JSON:          {gate_json.relative_to(ROOT)}")
    print(f"Gate Markdown:      {gate_md.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
