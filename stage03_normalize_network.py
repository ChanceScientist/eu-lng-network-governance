"""
stage03_normalize_network.py — v4.2 (2026-03-15)
Purpose:
Normalize monthly LNG trade graphs to enforce a fixed country universe,
valid edge weights, and structural comparability across periods, then
aggregate normalized monthly graphs into yearly graphs with diagnostics
and reproducibility checks.

Inputs:
- Directory: graphs/
- Files: graph_<YYYY-MM>.gpickle produced by stage02_build_graphs.py
- Required graph attributes: directed edges with numeric "weight"
- Reference data: COUNTRIES (valid node universe)
- Utility modules: extract_period(), is_month(), load_graph_by_period(),
  file_checksum(), system_metrics()

Responsibilities:
- Load monthly graphs and validate period format
- Normalize graph structure:
  - enforce fixed node universe (COUNTRIES)
  - add missing nodes, remove extraneous nodes
  - ensure non-negative numeric weights
  - remove self-loops
- Compute structural diagnostics for each monthly graph
- Save normalized monthly graphs to graphs_normalized/
- Aggregate normalized monthly graphs into yearly graphs
- Compute diagnostics and checksums for yearly graphs
- Produce summary tables across all periods

Outputs:
- Normalized monthly graphs:
    graphs_normalized/graph_<YYYY-MM>_normalized.gpickle
- Normalized yearly graphs:
    graphs_normalized/graph_<YYYY>_normalized.gpickle
- Monthly diagnostics:
    diagnostics/normalized_graphs_diagnostics_<YYYY-MM>.csv
- Yearly diagnostics:
    diagnostics/normalized_graphs_diagnostics_<YYYY>.csv
- Summary across all periods:
    diagnostics/normalized_graphs_summary_all_periods.csv
- Checksums for reproducibility:
    diagnostics/normalized_graphs_checksums.csv
- Log file:
    logs/stage03_normalize_network_<timestamp>.log

Notes:
- Normalization ensures comparability across months and years
- Yearly graphs sum monthly edge weights across the calendar year
- system_metrics() provides structural indicators for QA and reproducibility
- AI Assistance:
    This script was drafted with support from Microsoft Copilot. All conceptual
    framing, methodological design, and analytical and interpretive decisions
    were made by the author. The author reviewed, edited, and validated all code.
"""

SCRIPT_VERSION = "v4.2 (2026-03-15)"

# ============================================================
# Setup
# ============================================================

import os
import logging
import pickle
import pandas as pd
import networkx as nx
from tqdm import tqdm
from datetime import datetime

from tools.constants import COUNTRIES
from tools.periods import extract_period, is_month
from tools.graph_loader import load_graph_by_period
from tools.io_utils import file_checksum
from tools.metrics_structural import system_metrics

GRAPH_DIR = "graphs"
NORM_DIR = "graphs_normalized"
DIAG_DIR = "diagnostics"
LOG_DIR = "logs"

os.makedirs(NORM_DIR, exist_ok=True)
os.makedirs(DIAG_DIR, exist_ok=True)
os.makedirs(LOG_DIR, exist_ok=True)

timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
LOG_FILE = os.path.join(LOG_DIR, f"stage03_normalize_network_{timestamp}.log")

# Reset handlers
for h in logging.root.handlers[:]:
    logging.root.removeHandler(h)

logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    encoding="utf-8"
)

logging.info("=== Starting Network Normalization Pipeline ===")
logging.info(f"Script version: {SCRIPT_VERSION}")


# ============================================================
# Normalization Logic
# ============================================================

def normalize_graph(G: nx.DiGraph, period: str) -> nx.DiGraph:
    """
    Normalize graph structure to ensure:
        - fixed country universe
        - no missing or negative weights
        - structural comparability across periods
    """

    # Add missing nodes
    missing = [n for n in COUNTRIES if n not in G.nodes()]
    for n in missing:
        G.add_node(n)

    # Remove extraneous nodes
    extraneous = [n for n in G.nodes() if n not in COUNTRIES]
    G.remove_nodes_from(extraneous)

    # Ensure all weights are valid numeric values
    for _, _, data in G.edges(data=True):
        w = data.get("weight", 0)
        if w is None or w < 0:
            data["weight"] = 0

    logging.info(
        f"{period}: normalized graph "
        f"(missing added={len(missing)}, extraneous removed={len(extraneous)})"
    )

    # Remove self-loops (countries reporting imports from themselves)
    num_self_loops = len(list(nx.selfloop_edges(G)))
    if num_self_loops > 0:
        G.remove_edges_from(nx.selfloop_edges(G))
        logging.info(f"{period}: removed {num_self_loops} self-loop edges")

    return G


# ============================================================
# Main Loop — Normalize Monthly Graphs
# ============================================================

def main():
    summary_rows = []
    checksum_rows = []
    yearly_accumulator = {}  # year → list of monthly graphs

    files = sorted(f for f in os.listdir(GRAPH_DIR) if f.startswith("graph_"))

    for file in tqdm(files, desc="Normalizing monthly graphs"):
        try:
            period = extract_period(file)
        except ValueError:
            logging.warning(f"Skipping file with no valid period: {file}")
            continue

        if not is_month(period):
            logging.warning(f"Skipping non-monthly file: {file}")
            continue

        G = load_graph_by_period(period)
        G_norm = normalize_graph(G, period)

        # Diagnostics after normalization
        diag = system_metrics(G_norm)
        diag["period"] = period
        diag["level"] = "monthly"
        summary_rows.append(diag)

        # Save normalized graph
        out_path = os.path.join(NORM_DIR, f"graph_{period}_normalized.gpickle")
        with open(out_path, "wb") as f:
            pickle.dump(G_norm, f)

        checksum_rows.append({
            "period": period,
            "filename": f"graph_{period}_normalized.gpickle",
            "checksum": file_checksum(out_path),
            "level": "monthly",
        })

        # Per-period diagnostics
        pd.DataFrame([diag]).to_csv(
            os.path.join(DIAG_DIR, f"normalized_graphs_diagnostics_{period}.csv"),
            index=False
        )

        # Accumulate for yearly aggregation
        year = period[:4]
        yearly_accumulator.setdefault(year, []).append(G_norm)

    # ============================================================
    # Aggregate Yearly Graphs (with diagnostics + checksums)
    # ============================================================

    for year, graphs in yearly_accumulator.items():
        G_year = nx.DiGraph()
        G_year.add_nodes_from(COUNTRIES)

        # Sum weights across all months
        for Gm in graphs:
            for u, v, data in Gm.edges(data=True):
                w = data.get("weight", 0)
                if G_year.has_edge(u, v):
                    G_year[u][v]["weight"] += w
                else:
                    G_year.add_edge(u, v, weight=w)

        # Save yearly graph
        out_path = os.path.join(NORM_DIR, f"graph_{year}_normalized.gpickle")
        with open(out_path, "wb") as f:
            pickle.dump(G_year, f)

        # Yearly diagnostics
        diag = system_metrics(G_year)
        diag["period"] = year
        diag["level"] = "yearly"
        summary_rows.append(diag)

        pd.DataFrame([diag]).to_csv(
            os.path.join(DIAG_DIR, f"normalized_graphs_diagnostics_{year}.csv"),
            index=False
        )

        # Yearly checksum
        checksum_rows.append({
            "period": year,
            "filename": f"graph_{year}_normalized.gpickle",
            "checksum": file_checksum(out_path),
            "level": "yearly",
        })

    # ============================================================
    # Summary across all periods (monthly + yearly)
    # ============================================================

    pd.DataFrame(summary_rows).to_csv(
        os.path.join(DIAG_DIR, "normalized_graphs_summary_all_periods.csv"),
        index=False
    )

    pd.DataFrame(checksum_rows).to_csv(
        os.path.join(DIAG_DIR, "normalized_graphs_checksums.csv"),
        index=False
    )

    logging.info("=== Network Normalization Pipeline Complete ===")


if __name__ == "__main__":
    main()