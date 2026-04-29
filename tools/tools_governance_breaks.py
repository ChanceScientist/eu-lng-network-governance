"""
governance_breaks.py — v4.3 (2026-03-23)
Purpose:
Provide governance‑relevant comparison tools for temporal LNG trade networks,
including structural deltas, normalized centrality shifts, and edge‑level
change detection. Supports both temporal continuity (t–1) and seasonal
continuity (t–12 for monthly periods).

Responsibilities:
- compare_graphs(G_curr, G_prev, p_curr, p_prev):
    • compute system‑level deltas (flow, density, edges, isolates)
    • compute normalized centrality deltas (betweenness, eigenvector, flow)
    • detect new/dropped nodes and edges
    • identify large relative edge‑weight changes
- governance_break_panel(period, graphs):
    • wrapper for period‑aware comparisons
    • compare current period to:
        – previous period (temporal continuity)
        – same month previous year (seasonal continuity, monthly only)
    • return structured governance‑relevant deltas

Used by:
- Stage 05 (break detection and structural‑signature diagnostics)
- Stage 07 (governance interpretation and transition analysis)
- Mechanism‑specific panels and narrative diagnostics

Dependencies:
- tools.periods:
    • is_month, previous_period, previous_year
- tools.metrics_structural:
    • system_metrics, node_centrality_metrics, compute_deltas

Notes:
- All metric computation is delegated to metrics_structural.py.
- Centrality deltas use normalized metrics only.
- This module does not load graphs; it operates on already‑normalized inputs.
- AI Assistance:
    This script was drafted with support from Microsoft Copilot. All conceptual
    framing, methodological design, and analytical and interpretive decisions
    were made by the author. The author reviewed, edited, and validated all code.
"""


from typing import Dict, Any
import networkx as nx

from tools.periods import is_month, previous_period, previous_year
from tools.metrics_structural import (
    system_metrics,
    node_centrality_metrics,
    compute_deltas,
)


# ============================================================
# Compare Two Graphs
# ============================================================

def compare_graphs(
    G_curr: nx.DiGraph,
    G_prev: nx.DiGraph,
    p_curr: str,
    p_prev: str,
    flow_threshold: float = 0.5,
) -> Dict[str, Any]:
    """
    Compare two normalized LNG trade graphs and compute:
        - system-level deltas (flow, density, edges, isolates)
        - normalized centrality deltas (v4.11)
        - new/dropped nodes
        - new/dropped edges
        - large relative edge-weight changes
    """

    # ------------------------------------------------------------
    # System-level metrics and deltas
    # ------------------------------------------------------------
    m_curr = system_metrics(G_curr)
    m_prev = system_metrics(G_prev)
    graph_delta = compute_deltas(m_curr, m_prev)

    # ------------------------------------------------------------
    # Normalized centrality metrics (v4.3)
    # ------------------------------------------------------------
    cent_curr = node_centrality_metrics(G_curr)
    cent_prev = node_centrality_metrics(G_prev)

    cent_delta = {
        "betweenness_norm": {
            n: cent_curr["betweenness_norm"].get(n, 0)
            - cent_prev["betweenness_norm"].get(n, 0)
            for n in cent_curr["betweenness_norm"]
        },
        "eigenvector_norm": {
            n: cent_curr["eigenvector_norm"].get(n, 0)
            - cent_prev["eigenvector_norm"].get(n, 0)
            for n in cent_curr["eigenvector_norm"]
        },
        "flow_centrality_norm": {
            n: cent_curr["flow_centrality_norm"].get(n, 0)
            - cent_prev["flow_centrality_norm"].get(n, 0)
            for n in cent_curr["flow_centrality_norm"]
        },
    }

    # ------------------------------------------------------------
    # Node-level changes
    # ------------------------------------------------------------
    nodes_curr = set(G_curr.nodes())
    nodes_prev = set(G_prev.nodes())

    new_nodes = sorted(nodes_curr - nodes_prev)
    dropped_nodes = sorted(nodes_prev - nodes_curr)

    # ------------------------------------------------------------
    # Edge-level changes
    # ------------------------------------------------------------
    edges_curr = {(u, v): d.get("weight", 0) for u, v, d in G_curr.edges(data=True)}
    edges_prev = {(u, v): d.get("weight", 0) for u, v, d in G_prev.edges(data=True)}

    edge_keys_curr = set(edges_curr.keys())
    edge_keys_prev = set(edges_prev.keys())

    new_edges = sorted(edge_keys_curr - edge_keys_prev)
    dropped_edges = sorted(edge_keys_prev - edge_keys_curr)
    common_edges = edge_keys_curr & edge_keys_prev

    # ------------------------------------------------------------
    # Large relative edge-weight changes
    # ------------------------------------------------------------
    big_changes = []
    for e in common_edges:
        w_curr = edges_curr[e]
        w_prev = edges_prev[e]

        if w_prev == 0 and w_curr == 0:
            continue
        if w_prev == 0:
            rel_change = float("inf")
        else:
            rel_change = (w_curr - w_prev) / abs(w_prev)

        if abs(rel_change) >= flow_threshold:
            big_changes.append({
                "edge": e,
                "w_prev": w_prev,
                "w_curr": w_curr,
                "rel_change": rel_change,
            })

    big_changes = sorted(big_changes, key=lambda x: abs(x["rel_change"]), reverse=True)

    graph_delta["period_prev"] = p_prev

    return {
        "graph_delta": graph_delta,
        "centrality_delta": cent_delta,   # normalized-only
        "new_nodes": new_nodes,
        "dropped_nodes": dropped_nodes,
        "new_edges": new_edges,
        "dropped_edges": dropped_edges,
        "big_edge_changes": big_changes,
    }


# ============================================================
# Governance Break Panel
# ============================================================

def governance_break_panel(
    period: str,
    graphs: Dict[str, nx.DiGraph],
    flow_threshold: float = 0.5,
) -> Dict[str, Dict[str, Any]]:
    """
    Compute governance-relevant comparisons for a given period.

    For each period, compare:
        - current vs previous period (temporal continuity)
        - current vs same month previous year (seasonal continuity)
    """

    if period not in graphs:
        raise ValueError(f"No graph available for period {period}")

    G_curr = graphs[period]
    results: Dict[str, Dict[str, Any]] = {}

    # Precompute normalized centrality metrics for current period
    curr_cent = node_centrality_metrics(G_curr)

    # ------------------------------------------------------------
    # Helper: run comparison with normalized centrality deltas
    # ------------------------------------------------------------
    def run_comparison(label: str, G_prev: nx.DiGraph, prev_period: str):
        prev_cent = node_centrality_metrics(G_prev)

        # Compute deltas for normalized metrics only
        cent_delta = {
            "betweenness_norm": {
                n: curr_cent["betweenness_norm"].get(n, 0)
                - prev_cent["betweenness_norm"].get(n, 0)
                for n in curr_cent["betweenness_norm"]
            },
            "eigenvector_norm": {
                n: curr_cent["eigenvector_norm"].get(n, 0)
                - prev_cent["eigenvector_norm"].get(n, 0)
                for n in curr_cent["eigenvector_norm"]
            },
            "flow_centrality_norm": {
                n: curr_cent["flow_centrality_norm"].get(n, 0)
                - prev_cent["flow_centrality_norm"].get(n, 0)
                for n in curr_cent["flow_centrality_norm"]
            },
        }

        # Use existing compare_graphs for structural deltas + edge changes
        base = compare_graphs(G_curr, G_prev, period, prev_period, flow_threshold)

        # Inject normalized centrality deltas
        base["centrality_delta"] = cent_delta

        return base

    # ------------------------------------------------------------
    # Temporal continuity
    # ------------------------------------------------------------
    p_prev = previous_period(period)
    if p_prev in graphs:
        results["prev_period"] = run_comparison("prev_period", graphs[p_prev], p_prev)

    # ------------------------------------------------------------
    # Seasonal continuity (monthly only)
    # ------------------------------------------------------------
    if is_month(period):
        p_prev_year = previous_year(period)
        if p_prev_year in graphs:
            results["prev_year"] = run_comparison("prev_year", graphs[p_prev_year], p_prev_year)

    return results