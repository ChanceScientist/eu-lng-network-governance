"""
stage02_build_graphs.py — v4.1 (2026-03-15)
Purpose:
Construct directed, weighted LNG trade graphs from cleaned edge lists produced
by stage01_clean_edges.py, and generate diagnostics for structural consistency
and reproducibility.

Inputs:
- Directory: edges_clean/
- Files: edges_<YYYY-MM>_clean.csv
- Required columns: partnerISO, reporterISO, qty
- Utility modules: extract_period(), file_checksum()

Responsibilities:
- Load cleaned edge lists for each period
- Build directed, weighted DiGraph objects (partnerISO → reporterISO)
- Compute graph diagnostics (nodes, edges, isolates, density, total flow)
- Save graphs as .gpickle for deterministic downstream analysis
- Generate per‑period diagnostics and multi‑period summaries
- Compute checksums for reproducibility

Outputs:
- Graph objects: graphs/graph_<YYYY-MM>.gpickle
- Per‑period diagnostics: diagnostics/graphs_diagnostics_<YYYY-MM>.csv
- Multi‑period diagnostics: diagnostics/graphs_diagnostics_all_periods.csv
- Summary table: diagnostics/graphs_summary_all_periods.csv
- Checksums: diagnostics/graphs_checksums.csv
- Log file: logs/stage02_build_graphs_<timestamp>.log

Notes:
- Direction is exporter → importer (partnerISO → reporterISO)
- Graphs preserve full structure and edge weights for downstream modeling
- Assumes cleaned, aggregated edges from stage01
- AI Assistance:
    This script was drafted with support from Microsoft Copilot. All conceptual
    framing, methodological design, and analytical and interpretive decisions
    were made by the author. The author reviewed, edited, and validated all code.
"""

SCRIPT_VERSION = "v4.1 (2026-03-15)"

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

from tools.periods import extract_period
from tools.io_utils import file_checksum

EDGES_DIR = "edges_clean"
GRAPH_DIR = "graphs"
DIAG_DIR = "diagnostics"
LOG_DIR = "logs"

os.makedirs(GRAPH_DIR, exist_ok=True)
os.makedirs(DIAG_DIR, exist_ok=True)
os.makedirs(LOG_DIR, exist_ok=True)

timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
LOG_FILE = os.path.join(LOG_DIR, f"stage02_build_graphs_{timestamp}.log")

# Reset handlers
for h in logging.root.handlers[:]:
    logging.root.removeHandler(h)

logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    encoding="utf-8"
)

logging.info("=== Starting Graph Construction Pipeline ===")
logging.info(f"Script version: {SCRIPT_VERSION}")

# ============================================================
# Graph Construction
# ============================================================

def build_graph(df, period):
    """
    Construct a directed, weighted DiGraph for a given period.
    Direction: partnerISO → reporterISO (exporter → importer).
    This preserves the physical flow of LNG and ensures downstream
    metrics (e.g., in-degree = import dependence) remain interpretable.
    """
    G = nx.DiGraph(period=period)

    # Add weighted edges
    for _, row in df.iterrows():
        G.add_edge(row["partnerISO"], row["reporterISO"], weight=row["qty"])

    # Graph-level diagnostics support reproducibility and help identify
    # structural anomalies (e.g., missing nodes, unexpected isolates).
    isolates = list(nx.isolates(G))
    diag = {
        "period": period,
        "nodes": G.number_of_nodes(),
        "edges": G.number_of_edges(),
        "isolates": len(isolates),
        "density": nx.density(G),
        "total_flow": sum(nx.get_edge_attributes(G, "weight").values())
    }

    logging.info(
        f"{period}: graph built "
        f"({diag['nodes']} nodes, {diag['edges']} edges, "
        f"isolates={diag['isolates']}, density={diag['density']:.4f})"
    )

    return G, diag

# ============================================================
# Main Loop
# ============================================================

def main():
    summary_rows = []
    checksum_rows = []

    files = sorted(f for f in os.listdir(EDGES_DIR) if f.endswith("_clean.csv"))

    for file in tqdm(files, desc="Building graphs"):
        try:
            period = extract_period(file)
        except ValueError:
            logging.warning(f"Skipping file with no valid period: {file}")
            continue

        path = os.path.join(EDGES_DIR, file)
        df = pd.read_csv(path)
        logging.info(f"Loaded cleaned edges for {period} ({len(df)} rows)")

        G, diag = build_graph(df, period)
        summary_rows.append(diag)

        # Save as .gpickle to preserve full graph structure and attributes
        # for deterministic, reproducible downstream analysis.
        graph_path = os.path.join(GRAPH_DIR, f"graph_{period}.gpickle")
        with open(graph_path, "wb") as f:
            pickle.dump(G, f)

        checksum = file_checksum(graph_path)
        checksum_rows.append({
            "period": period,
            "filename": f"graph_{period}.gpickle",
            "checksum": checksum
        })

        logging.info(f"{period}: saved graph to {graph_path} (checksum: {checksum})")

        # Write per-period diagnostics
        pd.DataFrame([diag]).to_csv(
            os.path.join(DIAG_DIR, f"graphs_diagnostics_{period}.csv"),
            index=False
        )

    # Summary table across all periods
    summary_df = pd.DataFrame(summary_rows)
    summary_df.to_csv(
        os.path.join(DIAG_DIR, "graphs_summary_all_periods.csv"),
        index=False
    )

    pd.DataFrame(checksum_rows).to_csv(
        os.path.join(DIAG_DIR, "graphs_checksums.csv"),
        index=False
    )

    logging.info("=== Graph Construction Pipeline Complete ===")

if __name__ == "__main__":
    main()