"""
stage07_visuals_per_period.py — v[none]
Purpose:
Generate per‑period structural visualizations for normalized LNG trade graphs,
including nodelink layouts, flow matrices, chord diagrams, and top‑edge bar charts.

Inputs:
- Normalized graphs:
    (via load_graphs() → dict[period → DiGraph])
- Top‑edge summaries (optional):
    summaries/top_edges.csv
- Utility modules:
    plot_nodelink_centrality_gravity(),
    plot_flow_matrix(),
    plot_chord(),
    plot_top_edges_bar(),
    FIG_DIR

Responsibilities:
- Load all normalized graphs
- Optionally load top‑edge tables for each period
- Create per‑period output directories under FIG_DIR
- Generate four visualizations per period:
    1. Centrality–gravity nodelink
    2. Flow matrix
    3. Chord diagram
    4. Top‑edges bar chart
- Save all figures with consistent naming conventions

Outputs:
- Per‑period figures:
    figures/nodelink/nodelink_<period>.png
    figures/matrix/matrix_<period>.png
    figures/chord/chord_<period>.png
    figures/top_edges/top_edges_<period>.png

Notes:
- This script produces visual outputs only; no CSVs are written.
- All plotting logic is delegated to shared Stage 07 helper functions.
- Assumes normalized graphs and top‑edge summaries have already been generated.
- AI Assistance:
    This script was drafted with support from Microsoft Copilot. All conceptual
    framing, methodological design, and analytical and interpretive decisions
    were made by the author. The author reviewed, edited, and validated all code.
"""


import os
import pandas as pd
from tqdm import tqdm

# Import shared helpers
from stage07_helpers import (
    FIG_DIR,
    load_graphs,
    plot_nodelink_centrality_gravity,
    plot_flow_matrix,
    plot_chord,
    plot_top_edges_bar,
)


def main():

    # ------------------------------------------------------------
    # Load graphs
    # ------------------------------------------------------------
    period_to_graph = load_graphs()
    periods = sorted(period_to_graph.keys())

    print(f"Loaded {len(periods)} periods for visualization.")

    # ------------------------------------------------------------
    # Load top_edges (optional)
    # ------------------------------------------------------------
    top_edges_path = os.path.join("summaries", "top_edges.csv")
    if os.path.exists(top_edges_path):
        top_edges = pd.read_csv(top_edges_path)
    else:
        top_edges = None

    # ------------------------------------------------------------
    # Output directories
    # ------------------------------------------------------------
    out_nodelink = os.path.join(FIG_DIR, "nodelink")
    out_matrix = os.path.join(FIG_DIR, "matrix")
    out_chord = os.path.join(FIG_DIR, "chord")
    out_top = os.path.join(FIG_DIR, "top_edges")

    for d in [out_nodelink, out_matrix, out_chord, out_top]:
        os.makedirs(d, exist_ok=True)

    # ------------------------------------------------------------
    # Generate visuals
    # ------------------------------------------------------------
    print("Generating per-period visuals...")

    for period in tqdm(periods):

        G = period_to_graph[period]

        # Filter top edges for this period
        edges_df = pd.DataFrame()
        if top_edges is not None:
            edges_df = top_edges[top_edges["period"] == period]

        # 1. Centrality‑gravity nodelink
        plot_nodelink_centrality_gravity(
            G,
            period,
            os.path.join(out_nodelink, f"nodelink_{period}.png"),
            all_edge_centrality_rows=[],
        )

        # 2. Flow matrix
        plot_flow_matrix(
            G,
            period,
            os.path.join(out_matrix, f"matrix_{period}.png"),
        )

        # 3. Chord diagram
        plot_chord(
            edges_df,
            period,
            os.path.join(out_chord, f"chord_{period}.png"),
        )

        # 4. Top edges bar chart
        plot_top_edges_bar(
            edges_df,
            period,
            os.path.join(out_top, f"top_edges_{period}.png"),
        )

    print("Per-period visualizations complete.")


if __name__ == "__main__":
    main()