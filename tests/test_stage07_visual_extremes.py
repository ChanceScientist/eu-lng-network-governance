"""
test_stage07_visual_extremes.py — v1.0 (2026-03-22)
Purpose:
    Render the smallest and largest normalized LNG trade networks side‑by‑side
    to evaluate Stage 07 visualization behavior under extreme graph sizes.
    This script provides a fast diagnostic for tuning:
        • node size scaling
        • edge width scaling
        • gravity layout curvature
        • radial vs. FA2 blending
        • community coloring
        • label density and interpretive clarity

Responsibilities:
    - Load all normalized graphs
    - Identify smallest and largest networks by node count
    - Run only the node‑link visualizer (fast, layout‑focused)
    - Save two PNGs for visual comparison
    - Support visualization tuning without running full Stage 07 scripts

Inputs:
    graphs/ (via tools.graph_loader.load_all_graphs)
    plot_nodelink_centrality_gravity() and CONFIG_VIS from stage07_helpers.py

Outputs:
    figures_test/nodelink_smallest.png
    figures_test/nodelink_largest.png

Dependencies:
    - tools.graph_loader.load_all_graphs
    - stage07_helpers.plot_nodelink_centrality_gravity
    - stage07_helpers.CONFIG_VIS
    - os
    - networkx
    - community_louvain (indirectly via visualizer)

Notes:
    - This script is a developer utility for tuning Stage 07 visualization
      parameters across sparse and dense networks.
    - Not part of the production pipeline; included for transparency and
      reproducibility of layout and scaling tests.
    - AI Assistance:
    This script was drafted with support from Microsoft Copilot. All conceptual
    framing, methodological design, and analytical and interpretive decisions
    were made by the author. The author reviewed, edited, and validated all code.
"""


import os
from tools.graph_loader import load_all_graphs
from stage07_helpers import plot_nodelink_centrality_gravity, CONFIG_VIS

# Load graphs
graphs = load_all_graphs(normalized=True)

# Sort by node count
period_sizes = [(p, G.number_of_nodes()) for p, G in graphs.items()]
period_sizes.sort(key=lambda x: x[1])

smallest_period = period_sizes[0][0]
largest_period = period_sizes[-1][0]

print(f" \n gravity_exponent = {CONFIG_VIS["gravity_exponent"]}")
print(f" gravity_alpha = {CONFIG_VIS["gravity_alpha"]}")
print(f" radial_weight = {CONFIG_VIS["radial_weight"]}")
print(f" spring_weight = {CONFIG_VIS["spring_weight"]}")
print(f" clamp_radius = {CONFIG_VIS["clamp_radius"]}")
print(f" \n Smallest network: {smallest_period}")
print(f" Largest network:  {largest_period}")

# Prepare output directory
os.makedirs("figures_test", exist_ok=True)

# Dummy accumulator for edge centrality rows
dummy_edges = []

# Render smallest
plot_nodelink_centrality_gravity(
    graphs[smallest_period],
    smallest_period,
    f"figures_test/nodelink_smallest.png",
    dummy_edges
)
print("\nSaved: figures_test/nodelink_smallest.png")

# Render largest
plot_nodelink_centrality_gravity(
    graphs[largest_period],
    largest_period,
    f"figures_test/nodelink_largest.png",
    dummy_edges
)
print("Saved: figures_test/nodelink_largest.png \n===Test Complete.===")