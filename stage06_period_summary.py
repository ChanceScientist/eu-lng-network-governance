"""
stage06_period_summary.py — v4.8 (2026-04-19)
Purpose:
Compute period-level structural metrics and temporal metrics for normalized
LNG trade graphs, producing tidy summaries for applied governance analysis.

Inputs:
- Normalized graphs:
    graphs_normalized/graph_<YYYY-MM>_normalized.gpickle
    graphs_normalized/graph_<YYYY>_normalized.gpickle
- Utility modules:
    load_all_graphs(), system_metrics(), compute_top_edges()
- Configuration:
    CONFIG_SUMMARY["rolling_window"] for rolling averages and volatility

Responsibilities:
- Load all normalized graphs (monthly and yearly)
- Compute structural metrics for each period via system_metrics()
- Extract top edges per period for interpretability
- Compute temporal metrics:
    - deltas (monthly and yearly)
    - total_flow_ratio
    - rolling averages (monthly only)
    - volatility (monthly only)
- Export tidy CSVs for downstream governance and narrative analysis

Outputs:
- Period-level structural metrics:
    summaries/period_summary.csv
- System-level temporal metrics:
    summaries/period_temporal_metrics.csv
- Top-edge tables:
    summaries/top_edges.csv
- Log file:
    logs/stage06_period_summary_<timestamp>.log

Notes:
- Uses a tunable rolling window (default: 3 periods)
- Handles both monthly and yearly graphs, recombining results cleanly
- Produces analysis-ready tables for visualization and interpretation
- AI Assistance:
    This script was drafted with support from Microsoft Copilot. All conceptual
    framing, methodological design, and analytical and interpretive decisions
    were made by the author. The author reviewed, edited, and validated all code.
"""

SCRIPT_VERSION = "v4.8 (2026-04-19)"

# ============================================================
# Configuration (v4.7)
# ============================================================

CONFIG_SUMMARY = {
    "rolling_window": 3,   # periods for rolling averages and volatility
}

# ============================================================
# Setup
# ============================================================

import os
import logging
import pandas as pd
from tqdm import tqdm
from datetime import datetime

from tools.graph_loader import load_all_graphs
from tools.metrics_structural import (
    system_metrics,
    compute_top_edges,
)

SUMMARY_DIR = "summaries"
LOG_DIR = "logs"

os.makedirs(SUMMARY_DIR, exist_ok=True)
os.makedirs(LOG_DIR, exist_ok=True)

timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
LOG_FILE = os.path.join(LOG_DIR, f"stage06_period_summary_{timestamp}.log")

# Reset handlers
for h in logging.root.handlers[:]:
    logging.root.removeHandler(h)

logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    encoding="utf-8"
)

logging.info("=== Starting Period Summary Pipeline ===")
logging.info(f"Script version: {SCRIPT_VERSION}")
logging.info("Loading normalized graphs via load_all_graphs()")

# ============================================================
# Load normalized graphs
# ============================================================

graphs = load_all_graphs(normalized=True)

if not graphs:
    print("No normalized graphs found. Exiting.")
    raise SystemExit

periods = sorted(graphs.keys())

logging.info(f"Summarizing {len(periods)} periods")
print(f"Loaded {len(periods)} normalized graphs.")

# ============================================================
# 1. Period-level structural metrics
# ============================================================

summary_rows = []
top_edge_rows = []

for p in tqdm(periods, desc="Summarizing periods"):
    G = graphs[p]

    metrics = system_metrics(G)
    metrics["period"] = p
    summary_rows.append(metrics)

    top_edge_rows.append(compute_top_edges(G, p))

period_summary_df = pd.DataFrame(summary_rows)

# Remove empty/all-NA columns (prevents concat warnings later)
period_summary_df = period_summary_df.dropna(axis=1, how="all")

period_summary_df.to_csv(
    os.path.join(SUMMARY_DIR, "period_summary.csv"),
    index=False
)

# Filter out empty frames to avoid FutureWarning
top_edges_clean = [df for df in top_edge_rows if not df.empty]

if top_edges_clean:
    pd.concat(top_edges_clean, ignore_index=True).to_csv(
        os.path.join(SUMMARY_DIR, "top_edges.csv"),
        index=False
    )
else:
    # Write an empty file with correct columns
    pd.DataFrame().to_csv(
        os.path.join(SUMMARY_DIR, "top_edges.csv"),
        index=False
    )


# ============================================================
# 2. System-level temporal metrics
# ============================================================

def compute_period_temporal_metrics(df):
    """
    Compute temporal metrics for system-level summaries:
        - deltas (yearly and monthly separately)
        - rolling averages (monthly only)
        - volatility (monthly only)
        - total_flow_ratio (yearly and monthly separately)
    """

    df = df.copy()

    # Identify period types
    df["is_year"] = df["period"].str.len() == 4
    df["is_month"] = df["period"].str.len() == 7

    # Split into yearly and monthly sequences
    yearly = df[df["is_year"]].sort_values("period").copy()
    monthly = df[df["is_month"]].sort_values("period").copy()

    # -----------------------------
    # YEARLY TEMPORAL METRICS
    # -----------------------------
    yearly["delta_total_flow"] = yearly["total_flow"].diff()
    yearly["delta_density"] = yearly["density"].diff()
    yearly["delta_nodes"] = yearly["nodes"].diff()
    yearly["delta_edges"] = yearly["edges"].diff()

    # Ratio: current year / previous year
    yearly["total_flow_ratio"] = (
        yearly["total_flow"] / yearly["total_flow"].shift(1)
    )

    # No rolling metrics for yearly data
    yearly["rolling_total_flow"] = None
    yearly["rolling_density"] = None
    yearly["volatility_total_flow"] = None
    yearly["volatility_density"] = None

    # -----------------------------
    # MONTHLY TEMPORAL METRICS
    # -----------------------------
    monthly["delta_total_flow"] = monthly["total_flow"].diff()
    monthly["delta_density"] = monthly["density"].diff()
    monthly["delta_nodes"] = monthly["nodes"].diff()
    monthly["delta_edges"] = monthly["edges"].diff()

    # Ratio: current month / previous month
    monthly["total_flow_ratio"] = (
        monthly["total_flow"] / monthly["total_flow"].shift(1)
    )

    # Rolling metrics (3‑month window)
    w = CONFIG_SUMMARY["rolling_window"]
    monthly["rolling_total_flow"] = monthly["total_flow"].rolling(w).mean()
    monthly["rolling_density"] = monthly["density"].rolling(w).mean()
    monthly["volatility_total_flow"] = monthly["total_flow"].rolling(w).std()
    monthly["volatility_density"] = monthly["density"].rolling(w).std()

    # -----------------------------
    # RECOMBINE
    # -----------------------------
    frames = []

    if not yearly.empty:
        frames.append(yearly)
    
    if not monthly.empty:
        frames.append(monthly)

    # Drop all-NA columns inside each frame to avoid dtype inference warnings
    clean_frames = []
    for df_part in frames:
        df_clean = df_part.dropna(axis=1, how="all")
        clean_frames.append(df_clean)
    
    out = pd.concat(clean_frames, ignore_index=True).sort_values("period")

    return out


period_temporal_df = compute_period_temporal_metrics(period_summary_df)

period_temporal_df.to_csv(
    os.path.join(SUMMARY_DIR, "period_temporal_metrics.csv"),
    index=False
)

logging.info("=== Period Summary Pipeline Complete ===")
print("=== Period Summary Pipeline Complete ===")