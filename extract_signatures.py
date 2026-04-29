"""
extract_signatures.py — v[none]
Purpose:
Extract structural and governance signatures from Stage 07 outputs and export
them in long‑form (metrics × periods) for interpretation, comparison, and
inclusion in the attribution pipeline.

Inputs:
- Governance core:
    governance/governance_report_core.csv
- Community‑level metrics:
    governance/communities_all_periods.csv
- Node‑level metrics:
    governance/nodes_centrality_all_periods.csv
- Configuration:
    SELECTED_PERIODS (optional filtering)
    FILTER_TO_SELECTED (export full series or subset)

Responsibilities:
- Load Stage 07 outputs (governance core, communities, nodes)
- Construct structural signature:
    • max/mean edge change
    • node‑level delta maxima
    • modularity
    • stability metrics
    • CSCI
- Construct governance signature:
    • modularity, stability, CSCI
    • community count
    • largest community share
    • top‑3 flow share
    • mean strength
    • active edges
- Optionally filter to selected periods
- Export long‑form signatures (metrics as rows, periods as columns)

Outputs:
- Structural signature:
    signatures/structural_signature.csv
- Governance signature:
    signatures/governance_signature.csv

Notes:
- Signatures are exported in long‑form (metric × period) to support
  attribution scoring, mechanism interpretation, and appendix tables.
- No graphs are loaded or modified.
- AI Assistance:
    This script was drafted with support from Microsoft Copilot. All conceptual
    framing, methodological design, and analytical and interpretive decisions
    were made by the author. The author reviewed, edited, and validated all code.
"""


import os
import pandas as pd

from stage07_helpers import GOV_DIR   # ensures correct path resolution

# ------------------------------------------------------------
# Output directory
# ------------------------------------------------------------
SIGNATURE_DIR = "signatures"
os.makedirs(SIGNATURE_DIR, exist_ok=True)


# ------------------------------------------------------------
# Configuration
# ------------------------------------------------------------

# Choose one period or a list of periods
SELECTED_PERIODS = [
    "2018-06",
    "2021-09",
]

# If True → keep only selected periods
# If False → export full time series
FILTER_TO_SELECTED = False


# ------------------------------------------------------------
# Load Stage 07 outputs
# ------------------------------------------------------------

def load_stage07_outputs():
    gov = pd.read_csv(os.path.join(GOV_DIR, "governance_report_core.csv"))
    comm = pd.read_csv(os.path.join(GOV_DIR, "communities_all_periods.csv"))
    nodes = pd.read_csv(os.path.join(GOV_DIR, "nodes_centrality_all_periods.csv"))
    return gov, comm, nodes


# ------------------------------------------------------------
# Structural Signature
# ------------------------------------------------------------

STRUCTURAL_COLS = [
    "period",
    "max_edge_change",
    "mean_edge_change",
    "delta_eigenvector_max",
    "delta_betweenness_max",
    "delta_strength_max",
    "delta_flow_centrality_max",
    "delta_flow_share_max",
    "modularity",
    "stability_index",
    "stability_volatility_yearly",
    "composite_structural_change_index",
]


def build_structural_signature(gov):
    df = gov[STRUCTURAL_COLS].copy()

    if FILTER_TO_SELECTED:
        df = df[df["period"].isin(SELECTED_PERIODS)]

    # LONG FORM: metrics as rows, periods as columns
    df_long = df.set_index("period").T
    df_long.insert(0, "metric", df_long.index)
    df_long = df_long.reset_index(drop=True)

    return df_long


# ------------------------------------------------------------
# Governance Signature
# ------------------------------------------------------------

def build_governance_signature(gov, comm, nodes):
    # Community count
    comm_count = (
        comm.groupby("period")["community"]
        .nunique()
        .reset_index(name="community_count")
    )

    # Largest community share
    largest_share = (
        comm.groupby("period")["flow_share"]
        .max()
        .reset_index(name="largest_share")
    )

    # Top 3 flow share
    top3 = (
        comm.groupby("period")["flow_share"]
        .apply(lambda s: s.nlargest(3).sum())
        .reset_index(name="top3_share")
    )

    # Mean strength
    mean_strength = (
        nodes.groupby("period")["strength"]
        .mean()
        .reset_index(name="mean_strength")
    )

    # Active edges (from governance core)
    active_edges = gov[["period", "edges"]].rename(columns={"edges": "active_edges"})

    # Merge all governance metrics
    df = (
        gov[["period", "modularity", "stability_index", "composite_structural_change_index"]]
        .merge(comm_count, on="period", how="left")
        .merge(largest_share, on="period", how="left")
        .merge(top3, on="period", how="left")
        .merge(mean_strength, on="period", how="left")
        .merge(active_edges, on="period", how="left")
    )

    if FILTER_TO_SELECTED:
        df = df[df["period"].isin(SELECTED_PERIODS)]

    # LONG FORM: metrics as rows, periods as columns
    df_long = df.set_index("period").T
    df_long.insert(0, "metric", df_long.index)
    df_long = df_long.reset_index(drop=True)

    return df_long


# ------------------------------------------------------------
# Main
# ------------------------------------------------------------

def main():
    gov, comm, nodes = load_stage07_outputs()

    structural = build_structural_signature(gov)
    governance = build_governance_signature(gov, comm, nodes)

    structural.to_csv(os.path.join(SIGNATURE_DIR, "structural_signature.csv"), index=False)
    governance.to_csv(os.path.join(SIGNATURE_DIR, "governance_signature.csv"), index=False)

    print(f"✓ structural_signature.csv written to {SIGNATURE_DIR}/")
    print(f"✓ governance_signature.csv written to {SIGNATURE_DIR}/")

if __name__ == "__main__":
    main()
