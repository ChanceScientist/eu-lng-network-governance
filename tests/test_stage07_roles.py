"""
test_stage07_roles.py — v1.0 (2026-03-22)
Purpose:
    Provide a fast diagnostic environment for tuning Stage 07 role‑classification
    thresholds (hub_eigenvector_threshold and broker_betweenness_threshold)
    without running full Stage 07 visualization or interpretation scripts.

Responsibilities:
    - Load all normalized graphs
    - Identify smallest and largest networks in the dataset
    - Compute eigenvector and betweenness centrality for each
    - Apply CONFIG_ROLES thresholds to classify hubs and brokers
    - Print:
        • hub count and list
        • broker count and list
        • node/edge counts for each test period
    - Support threshold tuning and interpretability checks across sparse and dense networks

Inputs:
    graphs/ (via tools.graph_loader.load_all_graphs)
    CONFIG_ROLES from stage07_helpers.py

Outputs:
    Console diagnostics only (no CSVs, no figures)

Dependencies:
    - tools.graph_loader.load_all_graphs
    - tools.metrics_structural.node_centrality_metrics
    - community_louvain (python-louvain)
    - stage07_helpers.CONFIG_ROLES
    - networkx

Notes:
    - This script is a developer utility for tuning Stage 07 role thresholds.
    - Not part of the production pipeline; included for transparency and
      reproducibility of configuration testing.
    - AI Assistance:
    This script was drafted with support from Microsoft Copilot. All conceptual
    framing, methodological design, and analytical and interpretive decisions
    were made by the author. The author reviewed, edited, and validated all code.
"""


from tools.graph_loader import load_all_graphs
from tools.metrics_structural import node_centrality_metrics
from community import community_louvain
from stage07_helpers import CONFIG_ROLES

# Load graphs
graphs = load_all_graphs(normalized=True)

# Identify smallest and largest networks
period_sizes = [(p, G.number_of_nodes()) for p, G in graphs.items()]
period_sizes.sort(key=lambda x: x[1])

smallest = period_sizes[0][0]
largest = period_sizes[-1][0]

for period in [smallest, largest]:
    G = graphs[period]
    print(f"\n=== Testing roles for {period} ===")
    print(f"Nodes: {G.number_of_nodes()}, Edges: {G.number_of_edges()}")

    # Compute metrics
    cent = node_centrality_metrics(G)
    eig = cent["eigenvector_norm"]
    bet = cent["betweenness_norm"]

    # Apply thresholds
    hubs = [n for n in G.nodes() if eig[n] >= CONFIG_ROLES["hub_eigenvector_threshold"]]
    brokers = [n for n in G.nodes() if bet[n] >= CONFIG_ROLES["broker_betweenness_threshold"]]

    print(f"Hub threshold = {CONFIG_ROLES['hub_eigenvector_threshold']}")
    print(f"  Hubs ({len(hubs)}): {hubs}")

    print(f"Broker threshold = {CONFIG_ROLES['broker_betweenness_threshold']}")
    print(f"  Brokers ({len(brokers)}): {brokers}")

print("===Test Complete.===")