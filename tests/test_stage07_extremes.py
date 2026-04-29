"""
test_stage07_extremes.py — v1.0 (2026-03-22)
Purpose:
    Identify the smallest and largest normalized LNG trade networks in the
    dataset and test Louvain community resolution behavior on both extremes.
    This script provides a fast diagnostic for selecting a stable
    louvain_resolution value that behaves well across sparse and dense periods.

Responsibilities:
    - Load all normalized graphs
    - Identify the periods with the fewest and most nodes
    - Compute Louvain communities for each extreme case
    - Print:
        • period names
        • node/edge counts
        • number of communities at the configured resolution
    - Support Stage 07 visualization tuning without running full Stage 07 scripts

Inputs:
    graphs/ (via tools.graph_loader.load_all_graphs)
    CONFIG_VIS["louvain_resolution"] from stage07_helpers.py

Outputs:
    Console diagnostics only (no CSVs, no figures)

Dependencies:
    - tools.graph_loader.load_all_graphs
    - community_louvain (python-louvain)
    - tools.metrics_structural.node_centrality_metrics
    - stage07_helpers.CONFIG_VIS
    - networkx

Notes:
    - This script is a developer utility for tuning Stage 07 community
      resolution parameters.
    - Not part of the production pipeline; included for transparency and
      reproducibility of configuration testing.
    -AI Assistance:
    This script was drafted with support from Microsoft Copilot. All conceptual
    framing, methodological design, and analytical and interpretive decisions
    were made by the author. The author reviewed, edited, and validated all code.
"""


from tools.graph_loader import load_all_graphs
from community import community_louvain
from tools.metrics_structural import node_centrality_metrics
from stage07_helpers import CONFIG_VIS

# Load all graphs once
graphs = load_all_graphs(normalized=True)

# Sort periods by graph size
period_sizes = [(p, G.number_of_nodes(), G.number_of_edges()) 
                for p, G in graphs.items()]
period_sizes.sort(key=lambda x: x[1])  # sort by node count

smallest_period, _, _ = period_sizes[0]
largest_period, _, _ = period_sizes[-1]

print("Smallest network:", smallest_period)
print("Largest network:", largest_period)

# Extract the graphs
G_small = graphs[smallest_period]
G_large = graphs[largest_period]

# Test Louvain resolution
res = CONFIG_VIS["louvain_resolution"]

def test_resolution(G, label):
    part = community_louvain.best_partition(
        G.to_undirected(),
        weight="weight",
        resolution=res
    )
    print(f"{label}: {len(set(part.values()))} communities at resolution {res}")

test_resolution(G_small, "Smallest")
test_resolution(G_large, "Largest")
print("===Test Complete.===")