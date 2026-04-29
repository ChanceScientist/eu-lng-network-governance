"""
metrics_structural.py — v4.9 (2026-03-23)
Purpose:
Provide a unified, governance‑aligned structural metrics engine for the LNG
network pipeline, consolidating all node‑, edge‑, community‑, and system‑level
measurements required for break detection, temporal deltas, structural
signatures, governance signatures, and Stage 07 integration.

Responsibilities:
- System‑level metrics:
    • total_flow, density, edges, isolates, zero‑weight edges
- Narrative metrics:
    • top‑k bilateral flows (compute_top_edges)
- Volatility and smoothing:
    • month‑to‑month volatility
    • rolling averages
- Node‑level metrics:
    • betweenness (raw + normalized)
    • eigenvector centrality (safe fallback)
    • flow centrality (raw + normalized)
    • strength (weighted degree)
- Edge‑level metrics:
    • weighted edge betweenness (corridor centrality)
- Community‑level metrics:
    • Louvain partition
    • community sizes and total flow
- Derived structural deltas:
    • Δflow, Δdensity, Δedges, Δisolates, flow ratios
- Structural signature detectors:
    • flow surge / collapse
    • connectivity expansion / contraction
    • role diversification (centrality redistribution)
- Governance signature helpers:
    • corridor dominance
    • concentration index (HHI)

Used by:
- Stage 03 (normalization)
- Stage 05 (break detection + structural signature detection)
- Stage 06 (period summaries + temporal deltas)
- Stage 07 (governance integration, node/edge/community metrics)
- governance_breaks.py (mechanism‑specific panels)
- Attribution layer (indirectly via Stage 07 outputs)
- tools.pipeline_checks
- tools.governance_breaks
- stage07_helpers

Dependencies:
- networkx
- numpy
- pandas
- collections.defaultdict

Notes:
- This module replaces legacy metrics.py and is the authoritative source for
  all governance‑relevant structural measurements.
- Flow centrality (raw) is retained for narrative and community metrics.
- All delta computations use normalized flow centrality where appropriate.
- AI Assistance:
    This script was drafted with support from Microsoft Copilot. All conceptual
    framing, methodological design, and analytical and interpretive decisions
    were made by the author. The author reviewed, edited, and validated all code.
"""


from typing import Dict, Any, List, Tuple
import networkx as nx
import numpy as np
import pandas as pd
from collections import defaultdict


# ============================================================
# System-Level Metrics
# ============================================================

def system_metrics(G: nx.DiGraph, period: str | None = None) -> Dict[str, float]:
    """
    Compute system-level structural metrics for a directed LNG network.

    Metrics:
        - total_flow: aggregate LNG imports
        - density: realized edges / possible edges
        - edges: number of active trade relationships
        - isolates: nodes with no in/out flow
        - zero_weight_edges: sanity check for malformed edges

    Returns:
        A dictionary of system-level metrics.
    """
    weights = [d.get("weight", 0) for _, _, d in G.edges(data=True)]
    total_flow = float(sum(weights))
    zero_edges = sum(1 for w in weights if w == 0)
    isolates = list(nx.isolates(G))
    density = nx.density(G)

    out = {
        "nodes": G.number_of_nodes(),
        "edges": G.number_of_edges(),
        "isolates": len(isolates),
        "density": density,
        "total_flow": total_flow,
        "zero_weight_edges": zero_edges,
    }

    if period is not None:
        out["period"] = period

    return out

# ============================================================
# Optional: Top Edges (for narrative context)
# ============================================================

def compute_top_edges(G: nx.DiGraph, period: str, k: int = 20) -> pd.DataFrame:
    """
    Compute top bilateral flows for narrative or descriptive context.

    Returns:
        DataFrame with columns:
            - period
            - exporter
            - importer
            - flow
    """
    rows = []
    for u, v, data in G.edges(data=True):
        rows.append({
            "period": period,
            "exporter": u,
            "importer": v,
            "flow": data.get("weight", 0),
        })

    df = pd.DataFrame(rows)
    return df.sort_values("flow", ascending=False).head(k)

# ============================================================
# Volatility & Rolling Metrics
# ============================================================

def compute_volatility(series: List[float]) -> float:
    """
    Compute month-to-month volatility for a metric series.

    Returns:
        Standard deviation of first differences.
    """
    if len(series) < 2:
        return 0.0
    diffs = np.diff(series)
    return float(np.std(diffs))


def rolling_average(series: List[float], window: int) -> List[float]:
    """
    Compute rolling average with a fixed window.

    Returns:
        List of smoothed values (same length as input).
    """
    if len(series) == 0:
        return []
    return pd.Series(series).rolling(window=window, min_periods=1).mean().tolist()


# ============================================================
# Node-Level Metrics (Centrality + Strength)
# ============================================================

def node_centrality_metrics(G: nx.DiGraph) -> Dict[str, Dict[str, float]]:
    """
    Compute governance-relevant node-level metrics:
        - betweenness (raw + normalized)
        - eigenvector (raw + normalized)
        - flow centrality (incoming flow, normalized)
        - strength (weighted degree)
    """

    # ------------------------------------------------------------
    # Betweenness (normalized by NetworkX)
    # ------------------------------------------------------------
    bet = nx.betweenness_centrality(G, weight="weight", normalized=True)
    max_bet = max(bet.values()) if bet else 1.0
    bet_norm = {n: (v / max_bet if max_bet > 0 else 0.0) for n, v in bet.items()}

    # ------------------------------------------------------------
    # Eigenvector centrality (safe, ARPACK-free)
    # ------------------------------------------------------------
    try:
        eig = nx.eigenvector_centrality(G, weight="weight", max_iter=500, tol=1e-06)
    except Exception:
        eig = {n: 0.0 for n in G.nodes()}

    max_eig = max(eig.values()) if eig else 1.0
    eig_norm = {n: (v / max_eig if max_eig > 0 else 0.0) for n, v in eig.items()}

    # ------------------------------------------------------------
    # Flow centrality (incoming flow) — NORMALIZED
    # ------------------------------------------------------------
    flow_raw = defaultdict(float)
    for u, v, data in G.edges(data=True):
        flow_raw[v] += data.get("weight", 0)

    total_flow = sum(flow_raw.values()) or 1.0
    flow_norm = {n: (v / total_flow) for n, v in flow_raw.items()}

    # ------------------------------------------------------------
    # Strength (weighted degree)
    # ------------------------------------------------------------
    strength = dict(G.degree(weight="weight"))

    return {
        "betweenness": bet,
        "betweenness_norm": bet_norm,
        "eigenvector": eig,
        "eigenvector_norm": eig_norm,
        "flow_centrality": flow_raw,
        "flow_centrality_norm": flow_norm,
        "strength": strength,
    }

# ============================================================
# Edge-Level Metrics (Corridor Centrality)
# ============================================================

def edge_centrality_metrics(G: nx.DiGraph) -> Dict[tuple, float]:
    """
    Compute weighted edge betweenness centrality.
    Useful for corridor and chokepoint detection.
    """
    return nx.edge_betweenness_centrality(G, weight="weight")


# ============================================================
# Community-Level Metrics
# ============================================================

def community_metrics(G: nx.DiGraph) -> Dict[str, Any]:
    """
    Compute community structure and community-level summaries:
        - communities: node → community ID
        - num_communities
        - community_sizes
        - community_total_flow
    """
    try:
        import community as community_louvain
    except ImportError:
        raise ImportError("community_louvain package is required for community detection.")

    partition = community_louvain.best_partition(G.to_undirected(), weight="weight")
    num_comms = len(set(partition.values()))

    # Community sizes
    sizes = defaultdict(int)
    for n, c in partition.items():
        sizes[c] += 1

    # Community total flow (sum of incoming flow for nodes in each community)
    flow_centrality = defaultdict(float)
    for u, v, data in G.edges(data=True):
        flow_centrality[v] += data.get("weight", 0)

    comm_flow = defaultdict(float)
    for n, c in partition.items():
        comm_flow[c] += flow_centrality.get(n, 0)

    return {
        "communities": partition,
        "num_communities": num_comms,
        "community_sizes": dict(sizes),
        "community_total_flow": dict(comm_flow),
    }


# ============================================================
# Derived Structural Deltas
# ============================================================

def compute_deltas(curr: Dict[str, float], prev: Dict[str, float]) -> Dict[str, float]:
    """
    Compute deltas between two metric dictionaries.

    Metrics:
        - Δflow
        - Δdensity
        - Δedges
        - Δisolates

    Returns:
        A dictionary of deltas.
    """
    return {
        "total_flow_delta": curr["total_flow"] - prev["total_flow"],
        "density_delta": curr["density"] - prev["density"],
        "edges_delta": curr["edges"] - prev["edges"],
        "isolates_delta": curr["isolates"] - prev["isolates"],
        "total_flow_ratio": (
            curr["total_flow"] / prev["total_flow"]
            if prev["total_flow"] > 0 else None
        ),
    }


# ============================================================
# Structural Signature Helpers
# ============================================================

def detect_flow_surge(delta: float, ratio: float, threshold: float) -> bool:
    """Return True if flow surge exceeds threshold."""
    return ratio is not None and ratio >= threshold


def detect_flow_collapse(ratio: float, threshold: float) -> bool:
    """Return True if flow collapse exceeds threshold."""
    return ratio is not None and ratio <= threshold


def detect_connectivity_expansion(delta: float, threshold: float) -> bool:
    """Return True if edge or density expansion exceeds threshold."""
    return delta >= threshold


def detect_connectivity_contraction(delta: float, threshold: float) -> bool:
    """Return True if contraction exceeds threshold."""
    return delta <= -threshold


def detect_role_diversification(cent_deltas: Dict[str, Dict[str, float]],
                                threshold: float) -> bool:
    """
    Detect role diversification via centrality redistribution.

    Returns:
        True if any node's centrality shifts exceed threshold.
    """
    for metric in cent_deltas.values():
        if any(abs(v) >= threshold for v in metric.values()):
            return True
    return False


# ============================================================
# Governance Signature Helpers
# ============================================================

def corridor_dominance(flow_centrality: Dict[str, float]) -> Dict[str, float]:
    """
    Compute corridor dominance index:
        node_flow / total_flow

    Returns:
        A dictionary of dominance scores.
    """
    total = sum(flow_centrality.values())
    if total == 0:
        return {k: 0.0 for k in flow_centrality}
    return {k: v / total for k, v in flow_centrality.items()}


def concentration_index(weights: List[float]) -> float:
    """
    Compute a simple concentration index (Herfindahl-Hirschman).

    Returns:
        HHI score.
    """
    if not weights:
        return 0.0
    w = np.array(weights)
    w = w / w.sum() if w.sum() > 0 else w
    return float(np.sum(w ** 2))