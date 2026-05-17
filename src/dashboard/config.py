from pathlib import Path

# Resolve root directory relative to this file
ROOT_DIR = Path(__file__).resolve().parents[2]

# Tickers supported in the system
DEFAULT_TICKER = "nvda"

# Data and artifact paths
DEFAULT_DATA_PATH = ROOT_DIR / "data" / "tech_training_data.parquet"
STATIONARY_DATA_PATH = ROOT_DIR / "data" / "tech_training_data_stationary.parquet"
FALLBACK_DATA_PATH = ROOT_DIR / "data" / "tech_training_data.csv"
DEFAULT_LEADERBOARD_PATH = ROOT_DIR / "data" / "experiment_leaderboard.csv"
DEFAULT_REWARD_LEADERBOARD_PATH = ROOT_DIR / "data" / "experiment_reward_leaderboard.csv"
DEFAULT_SUMMARY_PATH = ROOT_DIR / "data" / "experiment_summary.json"
DEFAULT_SNAPSHOT_DIR = ROOT_DIR / "data" / "experiment_snapshots"

INTRADAY_5M_LEADERBOARD_PATH = ROOT_DIR / "data" / "experiment_leaderboard_intraday_5m.csv"
INTRADAY_5M_REWARD_LEADERBOARD_PATH = ROOT_DIR / "data" / "experiment_reward_leaderboard_intraday_5m.csv"
INTRADAY_5M_SUMMARY_PATH = ROOT_DIR / "data" / "experiment_summary_intraday_5m.json"
INTRADAY_5M_SNAPSHOT_DIR = ROOT_DIR / "data" / "experiment_snapshots" / "intraday_5m"

STAGE1_RESULTS_DIR = ROOT_DIR / "results" / "stage1"
STAGE1_CONFIRMATION_DIR = ROOT_DIR / "results" / "stage1_confirmation_3seed"
STAGE1_PIVOT_REPORT_PATH = ROOT_DIR / "sessions" / "stage1-step4-quant-report-smoketest.md"

# Recommendation & Evaluation parameters
DEFAULT_ACTIONABLE_TARGET = 0.55
RECOMMENDED_THRESHOLD = 0.0020
RECOMMENDED_HORIZON = 1
RECOMMENDED_CHART_WINDOW = 2000

# Promotion Gate Requirements (PPO Aligned)
PROMOTION_GATE_DEFAULTS = {
    "min_test_actionable": 0.525,
    "min_test_win_rate": 0.50,
    "min_test_alpha": 0.0005,
    "max_val_test_gap": 0.05,
    "max_test_cv": 0.50,          # Tightened target for stability
    "test_trade_rate_min": 0.40,
    "test_trade_rate_max": 0.80,  # Baseline upper limit
}

# Tickers that are allowed to 'over-trade' or 'hold' in high-momentum regimes
G6_RELAXED_TICKERS = {"amzn", "mu", "msft", "googl"}
G6_RELAXED_MAX = 1.0
