#!/usr/bin/env python
"""
plot_divergence.py — Reward Divergence Diagnostic Dashboard
============================================================
Produces a 6-panel dark-themed figure saved to:
    data/audit/divergence_dashboard.png

Panels:
  1  NVDA vs AMD cumulative return (test period price action / regime)
  2  Daily return distribution comparison (violin + box)
  3  Ensemble confidence distribution (NVDA vs AMD, from exit audit CSVs)
  4  Exit rule val→test Sharpe ablation (NVDA Phase 2B configs)
  5  no_exit vs profit_take_2pct metric scorecard (Phase 2B baseline delta)
  6  Voting suppression breakdown (per-ticker bar)

Usage:
    source .venv/bin/activate
    python scripts/plot_divergence.py
"""
import json
import sys
import warnings
from pathlib import Path

import matplotlib
matplotlib.use("Agg")  # headless safe
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import matplotlib.patches as mpatches
from matplotlib.ticker import FuncFormatter
import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

ROOT = Path(__file__).parent.parent
AUDIT_DIR = ROOT / "data" / "audit" / "exit_signal_sweep"
OUT_PATH   = ROOT / "data" / "audit" / "divergence_dashboard.png"
OUT_PATH.parent.mkdir(parents=True, exist_ok=True)

# ── Design tokens ────────────────────────────────────────────────────────────
BG      = "#0d1117"
PANEL   = "#161b22"
BORDER  = "#30363d"
TEXT    = "#e6edf3"
MUTED   = "#8b949e"
GREEN   = "#3fb950"
RED     = "#f85149"
AMBER   = "#d29922"
BLUE    = "#58a6ff"
PURPLE  = "#bc8cff"
NVDA_C  = "#76b900"   # NVDA green
AMD_C   = "#ed1c24"   # AMD red

PCTS = dict(left=0.07, right=0.96, top=0.91, bottom=0.07, wspace=0.38, hspace=0.52)

plt.rcParams.update({
    "figure.facecolor":  BG,
    "axes.facecolor":    PANEL,
    "axes.edgecolor":    BORDER,
    "axes.labelcolor":   TEXT,
    "axes.titlecolor":   TEXT,
    "xtick.color":       MUTED,
    "ytick.color":       MUTED,
    "text.color":        TEXT,
    "grid.color":        BORDER,
    "grid.alpha":        0.5,
    "legend.facecolor":  PANEL,
    "legend.edgecolor":  BORDER,
    "legend.labelcolor": TEXT,
    "font.family":       "DejaVu Sans",
    "font.size":         9,
})

# ── Helpers ───────────────────────────────────────────────────────────────────
def _ax_style(ax, title, xlabel="", ylabel=""):
    ax.set_title(title, fontsize=9, fontweight="bold", color=TEXT, pad=6)
    ax.set_xlabel(xlabel, fontsize=8, color=MUTED)
    ax.set_ylabel(ylabel, fontsize=8, color=MUTED)
    ax.tick_params(labelsize=7.5)
    ax.spines[["top", "right"]].set_visible(False)
    ax.spines[["left", "bottom"]].set_color(BORDER)
    ax.grid(True, axis="y", alpha=0.35)

def _pct(x, _): return f"{x:.0%}"
def _pct1(x, _): return f"{x:.1%}"

def _load_parquet(ticker: str):
    candidates = [
        ROOT / "data" / f"tech_training_data_{ticker}.parquet",
        ROOT / "data" / f"tech_training_data_{ticker}_stationary.parquet",
    ]
    for p in candidates:
        if p.exists():
            return pd.read_parquet(p)
    return None

def _test_split(df):
    n = len(df)
    val_end = int(n * 0.85)
    return df.iloc[val_end:].copy().reset_index(drop=True)

def _price_series(df):
    for col in ("RawClose", "Close", "close"):
        if col in df.columns:
            return df[col].values.astype(float)
    return None

# ── Phase 2B data (hard-coded from backtest results) ─────────────────────────
VAL_CONFIGS = [
    ("profit_take_8pct", 0.673, 0.005, False),
    ("profit_take_2pct", 0.636, 0.061, True),   # selected
    ("profit_take_3pct", 0.636, 0.038, False),
    ("profit_take_5pct", 0.600, 0.012, False),
    ("no_exit",          0.588, 0.000, False),
    ("trailing_3pct",    0.345, 0.038, False),
    ("trailing_5pct",    0.270, 0.016, False),
]
# (config, test_sharpe, test_max_dd, test_cum_ret, test_exit_rate, test_win_rate)
TEST_RESULTS = {
    "profit_take_2pct": (0.061, -0.159, -0.007, 0.044, 0.537),
    "no_exit":          (0.301, -0.161,  0.066, 0.000, 0.561),
}

# ── Build figure ──────────────────────────────────────────────────────────────
fig = plt.figure(figsize=(18, 11), facecolor=BG)
fig.suptitle(
    "NVDA / AMD Exit Signal Divergence  ·  Diagnostic Dashboard  ·  Binary PPO (May 2026)",
    fontsize=13, fontweight="bold", color=TEXT, y=0.97,
)

gs = gridspec.GridSpec(2, 3, figure=fig, **PCTS)
ax1 = fig.add_subplot(gs[0, 0])  # cumulative return (regime)
ax2 = fig.add_subplot(gs[0, 1])  # daily return violin
ax3 = fig.add_subplot(gs[0, 2])  # confidence distribution
ax4 = fig.add_subplot(gs[1, 0])  # val Sharpe ablation (exit configs)
ax5 = fig.add_subplot(gs[1, 1])  # Phase 2B metric scorecard
ax6 = fig.add_subplot(gs[1, 2])  # voting suppression

# ── Panel 1: Cumulative return (regime comparison) ────────────────────────────
regime_loaded = False
for ticker, color, label in [("nvda", NVDA_C, "NVDA"), ("amd", AMD_C, "AMD")]:
    df = _load_parquet(ticker)
    if df is None:
        continue
    test_df = _test_split(df)
    px = _price_series(test_df)
    if px is None or len(px) == 0:
        continue
    cum = px / px[0] - 1.0
    ax1.plot(cum, color=color, linewidth=1.6, label=label)
    regime_loaded = True

if regime_loaded:
    ax1.axhline(0, color=MUTED, linewidth=0.8, linestyle="--", alpha=0.6)
    ax1.yaxis.set_major_formatter(FuncFormatter(_pct1))
    ax1.legend(fontsize=8, framealpha=0.3)
    _ax_style(ax1, "Regime: Cumulative Return (test split)",
              xlabel="Bar index (test period)", ylabel="Cum return")
else:
    ax1.text(0.5, 0.5, "Parquet not found\nRun data pipeline first",
             ha="center", va="center", color=MUTED, fontsize=9, transform=ax1.transAxes)
    _ax_style(ax1, "Regime: Cumulative Return (test split)")

# ── Panel 2: Daily return distribution ───────────────────────────────────────
daily_returns = {}
for ticker, label in [("nvda", "NVDA"), ("amd", "AMD")]:
    df = _load_parquet(ticker)
    if df is None:
        continue
    test_df = _test_split(df)
    px = _price_series(test_df)
    if px is None or len(px) < 2:
        continue
    rets = np.diff(px) / px[:-1]
    daily_returns[label] = rets

if daily_returns:
    labels = list(daily_returns.keys())
    colors = [NVDA_C, AMD_C][:len(labels)]
    data   = [daily_returns[l] for l in labels]

    parts = ax2.violinplot(data, positions=range(len(labels)), showmedians=True,
                           showextrema=False, widths=0.65)
    for pc, c in zip(parts["bodies"], colors):
        pc.set_facecolor(c)
        pc.set_alpha(0.55)
        pc.set_edgecolor(c)
    parts["cmedians"].set_color(TEXT)
    parts["cmedians"].set_linewidth(1.5)

    ax2.set_xticks(range(len(labels)))
    ax2.set_xticklabels(labels, fontsize=8)
    ax2.yaxis.set_major_formatter(FuncFormatter(_pct1))
    ax2.axhline(0, color=MUTED, linewidth=0.8, linestyle="--", alpha=0.6)

    # Annotate std dev
    for i, (lbl, d) in enumerate(zip(labels, data)):
        ax2.text(i, np.percentile(d, 97),
                 f"σ={d.std():.2%}", ha="center", va="bottom",
                 fontsize=7, color=TEXT)
else:
    ax2.text(0.5, 0.5, "No data", ha="center", va="center",
             color=MUTED, transform=ax2.transAxes)

_ax_style(ax2, "Daily Return Distribution (test split)",
          ylabel="Daily return")

# ── Panel 3: Confidence distribution ─────────────────────────────────────────
conf_data = {}
for ticker, label in [("nvda", "NVDA"), ("amd", "AMD")]:
    csv_path = AUDIT_DIR / f"{ticker}_exit_audit.csv"
    if not csv_path.exists():
        continue
    df_a = pd.read_csv(csv_path)
    conf_col = next((c for c in ["confidence", "vote_share", "ensemble_confidence"]
                     if c in df_a.columns), None)
    if conf_col:
        conf_data[label] = df_a[conf_col].dropna().values

if conf_data:
    labels = list(conf_data.keys())
    colors = [NVDA_C, AMD_C][:len(labels)]
    for i, (lbl, color) in enumerate(zip(labels, colors)):
        vals = conf_data[lbl]
        ax3.hist(vals, bins=20, color=color, alpha=0.65, label=lbl,
                 edgecolor=color, linewidth=0.5, density=True)
    ax3.axvline(0.60, color=AMBER, linewidth=1.2, linestyle="--",
                label="Exit threshold (0.60)", alpha=0.85)
    ax3.legend(fontsize=7.5, framealpha=0.3)
else:
    # Fallback: draw from known summary data
    ax3.bar(["NVDA (1.0000)", "AMD (0.9578)"], [1.0, 0.9578],
            color=[NVDA_C, AMD_C], alpha=0.7, edgecolor=BORDER)
    ax3.axhline(0.60, color=AMBER, linewidth=1.2, linestyle="--",
                label="Exit threshold (0.60)")
    ax3.set_ylim(0.5, 1.05)
    ax3.legend(fontsize=7.5)
    ax3.text(0.5, 0.15, "Audit CSVs not found\n(showing summary stats)",
             ha="center", va="bottom", fontsize=7.5, color=MUTED,
             transform=ax3.transAxes)

_ax_style(ax3, "Ensemble Confidence Distribution",
          xlabel="Confidence (vote share)", ylabel="Density")

# ── Panel 4: Val Sharpe ablation ──────────────────────────────────────────────
cfg_labels  = [r[0].replace("_", " ") for r in VAL_CONFIGS]
val_sharpes = [r[1] for r in VAL_CONFIGS]
exit_rates  = [r[2] for r in VAL_CONFIGS]
selected    = [r[3] for r in VAL_CONFIGS]

colors_bar = []
for s, er, sel in zip(val_sharpes, exit_rates, selected):
    if sel:
        colors_bar.append(BLUE)
    elif 0.02 <= er <= 0.15:
        colors_bar.append(GREEN)
    else:
        colors_bar.append(MUTED)

bars = ax4.barh(range(len(cfg_labels)), val_sharpes, color=colors_bar,
                edgecolor=BORDER, linewidth=0.5, height=0.65)
ax4.set_yticks(range(len(cfg_labels)))
ax4.set_yticklabels(cfg_labels, fontsize=7.5)
ax4.axvline(TEST_RESULTS["no_exit"][0], color=AMBER, linewidth=1.2,
            linestyle="--", label=f"no_exit test={TEST_RESULTS['no_exit'][0]:.3f}")
ax4.axvline(TEST_RESULTS["profit_take_2pct"][0], color=RED, linewidth=1.2,
            linestyle=":", label=f"pt_2pct test={TEST_RESULTS['profit_take_2pct'][0]:.3f}")

# Annotate exit rate on bar
for i, (bar, er) in enumerate(zip(bars, exit_rates)):
    ax4.text(bar.get_width() + 0.005, bar.get_y() + bar.get_height() / 2,
             f"er={er:.1%}", va="center", fontsize=6.5, color=MUTED)

# Legend patches
ax4.legend(fontsize=7.5, framealpha=0.3, loc="lower right")
patch_sel  = mpatches.Patch(color=BLUE,  label="Selected (val)")
patch_ok   = mpatches.Patch(color=GREEN, label="er in [0.02,0.15]")
patch_out  = mpatches.Patch(color=MUTED, label="Outside er gate")
ax4.legend(handles=[patch_sel, patch_ok, patch_out],
           fontsize=7, framealpha=0.3, loc="lower right")
_ax_style(ax4, "Val Sharpe — Exit Config Ablation (NVDA Phase 2B)",
          xlabel="Val Sharpe")

# ── Panel 5: Phase 2B metric scorecard ───────────────────────────────────────
metrics     = ["Sharpe", "MaxDD", "CumRet", "WinRate"]
no_exit_v   = [TEST_RESULTS["no_exit"][0], TEST_RESULTS["no_exit"][1],
               TEST_RESULTS["no_exit"][2], TEST_RESULTS["no_exit"][4]]
pt2pct_v    = [TEST_RESULTS["profit_take_2pct"][0], TEST_RESULTS["profit_take_2pct"][1],
               TEST_RESULTS["profit_take_2pct"][2], TEST_RESULTS["profit_take_2pct"][4]]
deltas      = [pt2pct_v[i] - no_exit_v[i] for i in range(len(metrics))]

x = np.arange(len(metrics))
w = 0.32
bars_no  = ax5.bar(x - w/2, no_exit_v, w, label="no_exit", color=MUTED, alpha=0.85, edgecolor=BORDER)
bars_pt  = ax5.bar(x + w/2, pt2pct_v,  w, label="profit_take_2pct", color=BLUE, alpha=0.85, edgecolor=BORDER)

# Color bars red if pt2pct is worse
for bar, d in zip(bars_pt, deltas):
    bar.set_facecolor(RED if d < 0 else GREEN)

# Delta annotations above bars
for i, (d, xpos) in enumerate(zip(deltas, x)):
    y_top = max(no_exit_v[i], pt2pct_v[i])
    arrow_c = RED if d < 0 else GREEN
    sign = "+" if d >= 0 else ""
    ax5.annotate(f"{sign}{d:.3f}", xy=(xpos, y_top),
                 xytext=(xpos, y_top + abs(max(no_exit_v) - min(no_exit_v)) * 0.06),
                 ha="center", fontsize=7, color=arrow_c, fontweight="bold")

ax5.axhline(0, color=BORDER, linewidth=0.8)
ax5.set_xticks(x)
ax5.set_xticklabels(metrics, fontsize=8)
ax5.legend(fontsize=7.5, framealpha=0.3)
_ax_style(ax5, "Phase 2B Scorecard: no_exit vs profit_take_2pct (test split)",
          ylabel="Value")

# ── Panel 6: Voting suppression ───────────────────────────────────────────────
# Use known summary data; enrich from CSVs if available
suppression_data = {
    "NVDA": {"exit_rate": 0.00, "buy_rate": 1.00, "hold_rate": 0.00},
    "AMD":  {"exit_rate": 0.0703, "buy_rate": 0.8649, "hold_rate": 0.0648},
}

for ticker, lbl in [("nvda", "NVDA"), ("amd", "AMD")]:
    summary_json = AUDIT_DIR / f"{ticker}_exit_audit_summary.json"
    if summary_json.exists():
        s = json.loads(summary_json.read_text())
        suppression_data[lbl] = {
            "exit_rate": s.get("exit_signal_rate_pct", 0) / 100,
            "buy_rate":  s.get("buy_rate_pct", 0) / 100,
            "hold_rate": s.get("hold_rate_pct", 0) / 100,
        }

tickers  = list(suppression_data.keys())
exits    = [suppression_data[t]["exit_rate"] for t in tickers]
buys     = [suppression_data[t]["buy_rate"]  for t in tickers]
holds    = [suppression_data[t]["hold_rate"] for t in tickers]

x6 = np.arange(len(tickers))
ax6.bar(x6, buys,  label="BUY",  color=GREEN,  alpha=0.8, edgecolor=BORDER)
ax6.bar(x6, holds, label="HOLD", color=MUTED,  alpha=0.8, edgecolor=BORDER, bottom=buys)
ax6.bar(x6, exits, label="EXIT", color=RED,    alpha=0.9, edgecolor=BORDER,
        bottom=[b + h for b, h in zip(buys, holds)])

ax6.set_xticks(x6)
colors_tick = [NVDA_C, AMD_C][:len(tickers)]
ax6.set_xticklabels(tickers, fontsize=9)
for tick, c in zip(ax6.get_xticklabels(), colors_tick):
    tick.set_color(c)

ax6.yaxis.set_major_formatter(FuncFormatter(_pct))
ax6.set_ylim(0, 1.08)
ax6.legend(fontsize=7.5, framealpha=0.3)

# Annotate exit % on bar
for xi, er in zip(x6, exits):
    ax6.text(xi, 1.01, f"exit={er:.1%}", ha="center", fontsize=7.5,
             color=RED if er > 0.01 else MUTED, fontweight="bold")
_ax_style(ax6, "Signal Composition: BUY / HOLD / EXIT (val period)",
          ylabel="Fraction of bars")

# ── Footer annotation ─────────────────────────────────────────────────────────
fig.text(
    0.5, 0.012,
    "⚠  profit_take_2pct (val-selected) DEGRADES vs no_exit on test  "
    "| Δ Sharpe −0.240  | Δ CumRet −7.3pp  | Δ WinRate −2.4pp  "
    "| Source: backtest_exit_rules.py (Binary PPO, May 2026)",
    ha="center", fontsize=7.5, color=AMBER,
)

# ── Save ──────────────────────────────────────────────────────────────────────
fig.savefig(OUT_PATH, dpi=160, bbox_inches="tight", facecolor=BG)
plt.close(fig)
print(f"✅  Dashboard saved → {OUT_PATH}")
