"""
test_stage05_config.py — v2.0 (2026-03-23)
Purpose:
    Provide a fast, isolated testing environment for tuning Stage 05
    configuration thresholds without running the full break‑detection
    pipeline. This script recomputes:
        • big‑edge changes under flow_threshold sweeps
        • role‑diversification flags under centrality_threshold sweeps
    using Stage 05 output tables.

Responsibilities:
    - Load Stage 05 break‑detection outputs
    - Sweep candidate threshold values for each CONFIG parameter
    - Recompute threshold‑based triggers for each period
    - Print trigger counts for rapid diagnostic comparison
    - Support threshold tuning and sensitivity analysis

Inputs:
    breaks/breaks_summary_all_periods.csv
    breaks/breaks_edges.csv
    breaks/breaks_nodes.csv

Outputs:
    Console diagnostics only (no CSVs, no figures)

Dependencies:
    - pandas
    - numpy
    - os

Notes:
    - This script is not part of the production pipeline.
    - Included for transparency and reproducibility of configuration tuning.
    - AI Assistance:
    This script was drafted with support from Microsoft Copilot. All conceptual
    framing, methodological design, and analytical and interpretive decisions
    were made by the author. The author reviewed, edited, and validated all code.
"""


import pandas as pd
import numpy as np
import os

# ------------------------------------------------------------
# Load Stage 05 outputs
# ------------------------------------------------------------
SUMMARY = pd.read_csv("breaks/breaks_summary_all_periods.csv")
EDGES = pd.read_csv("breaks/breaks_edges.csv")
NODES = pd.read_csv("breaks/breaks_nodes.csv")

# Ensure consistent types
SUMMARY["period"] = SUMMARY["period"].astype(str)
EDGES["period"] = EDGES["period"].astype(str)
NODES["period"] = NODES["period"].astype(str)

# ------------------------------------------------------------
# Helper functions
# ------------------------------------------------------------

def recompute_big_edges(period, threshold):
    """Recompute big-edge changes for a given flow_threshold."""
    df = EDGES[EDGES["period"] == period]
    if df.empty:
        return 0
    return (df["rel_change"].abs() >= threshold).sum()


def recompute_role_diversification(period, threshold):
    """Recompute role-diversification flag for a given centrality_threshold."""
    df = NODES[NODES["period"] == period]
    if df.empty:
        return False
    return (df["centrality_delta"].abs() >= threshold).any()


# ------------------------------------------------------------
# Sweep definitions
# ------------------------------------------------------------
SWEEPS = {
    "flow_threshold": [0.0, 0.25, 0.5, 0.75, 1.0],
    "flow_surge_ratio": [2.50, 2.60, 2.70, 2.80],
    "flow_collapse_ratio": [0.76, 0.73, 0.70, 0.67],
    "density_threshold": [0.019, 0.02, 0.021, 0.022],
    "edges_threshold": [30, 35, 40, 45],
    "centrality_threshold": [0.06, 0.07, 0.08, 0.09],
    "min_big_edge_changes": [2, 3, 4, 5],
}

# ------------------------------------------------------------
# Sweep logic
# ------------------------------------------------------------
def run_sweep():
    for param, values in SWEEPS.items():
        print(f"\n--- {param} Sweep ---")

        for v in values:
            triggers = 0

            for _, row in SUMMARY.iterrows():
                period = row["period"]

                # --------------------------------------------------------
                # flow_threshold (requires recomputing big edges)
                # --------------------------------------------------------
                if param == "flow_threshold":
                    num_big = recompute_big_edges(period, v)
                    if num_big >= 1:
                        triggers += 1

                # --------------------------------------------------------
                # flow_surge_ratio
                # --------------------------------------------------------
                elif param == "flow_surge_ratio":
                    if row["total_flow_ratio"] >= v:
                        triggers += 1

                # --------------------------------------------------------
                # flow_collapse_ratio
                # --------------------------------------------------------
                elif param == "flow_collapse_ratio":
                    if row["total_flow_ratio"] <= v:
                        triggers += 1

                # --------------------------------------------------------
                # density_threshold
                # --------------------------------------------------------
                elif param == "density_threshold":
                    if abs(row["density_delta"]) >= v:
                        triggers += 1

                # --------------------------------------------------------
                # edges_threshold
                # --------------------------------------------------------
                elif param == "edges_threshold":
                    if abs(row["edges_delta"]) >= v:
                        triggers += 1

                # --------------------------------------------------------
                # centrality_threshold (requires node-level deltas)
                # --------------------------------------------------------
                elif param == "centrality_threshold":
                    if recompute_role_diversification(period, v):
                        triggers += 1

                # --------------------------------------------------------
                # min_big_edge_changes (count threshold)
                # --------------------------------------------------------
                elif param == "min_big_edge_changes":
                    if row["num_big_edge_changes"] >= v:
                        triggers += 1

            print(f"  {param} = {v}: {triggers} triggers")

print("\nSweep complete.")

# ------------------------------------------------------------
# Run sweeps
# ------------------------------------------------------------
if __name__ == "__main__":
    run_sweep()