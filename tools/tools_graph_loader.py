"""
graph_loader.py — v4.1 (2026-03-15)
Purpose:
Provide centralized, period‑aware graph‑loading utilities for the LNG network
pipeline, ensuring consistent retrieval of monthly and yearly NetworkX graphs
in both normalized and unnormalized form.

Responsibilities:
- load_graph(path):
    • load a pickled NetworkX DiGraph from disk
    • enforce deterministic, explicit error handling
- load_graph_by_period(period, normalized=False):
    • parse period strings or filenames via extract_period()
    • load the corresponding monthly or yearly graph
    • support normalized and unnormalized directories
- load_all_graphs(normalized=False):
    • bulk‑load all graphs from /graphs/ or /graphs_normalized/
    • automatically detect valid period labels
    • return a {period → DiGraph} mapping for downstream stages

Used by:
- Stage 02 (graph construction and validation)
- Stage 03 (normalization)
- Stage 04 (pipeline checks)
- Stage 05 (break detection)
- Stage 06 (period summaries and temporal metrics)
- Stage 07 (governance integration, transitions, per‑period visuals)
- Attribution layer (indirectly, via Stage 07 outputs)
- stage07_helpers (via load_graphs())

Dependencies:
- tools.periods.extract_period
- Standard library: os, pickle
- networkx

Notes:
- This module is the authoritative source for all graph‑loading logic.
- Normalized monthly and yearly graphs share the same directory structure.
- Sorting of periods is handled downstream (e.g., via sort_periods()).
- AI Assistance:
    This script was drafted with support from Microsoft Copilot. All conceptual
    framing, methodological design, and analytical and interpretive decisions
    were made by the author. The author reviewed, edited, and validated all code.
"""


from typing import Dict
import os
import pickle
import networkx as nx

from tools.periods import extract_period


# ============================================================
# Core Loader
# ============================================================

def load_graph(path: str) -> nx.DiGraph:
    """
    Load a pickled NetworkX graph from a full path.

    Args:
        path:
            Full path to a .gpickle file.

    Returns:
        A NetworkX DiGraph.

    Raises:
        FileNotFoundError if the file does not exist.
        pickle.UnpicklingError if the file is malformed.
    """
    if not os.path.exists(path):
        raise FileNotFoundError(f"Graph file not found: {path}")

    with open(path, "rb") as f:
        return pickle.load(f)


# ============================================================
# Period-Aware Loader
# ============================================================

def load_graph_by_period(period: str, normalized: bool = False) -> nx.DiGraph:
    """
    Load a graph for a given period (YYYY or YYYY-MM).

    Args:
        period:
            Period label. Can be a filename or a bare period string.
        normalized:
            If True, load from /graphs_normalized/ using:
                graph_YYYY-MM_normalized.gpickle
            If False, load from /graphs/ using:
                graph_YYYY-MM.gpickle

    Returns:
        A NetworkX DiGraph for the requested period.

    Notes:
        - extract_period() ensures robust parsing from filenames.
        - This function does not perform validation; normalization
          is handled upstream in 03_normalize_network.py.
        - Monthly and yearly normalized graphs both live in
          /graphs_normalized/ and are handled uniformly.
    """
    period = extract_period(period)

    graph_dir = "graphs_normalized" if normalized else "graphs"
    suffix = "_normalized.gpickle" if normalized else ".gpickle"
    filename = f"graph_{period}{suffix}"
    path = os.path.join(graph_dir, filename)

    return load_graph(path)


# ============================================================
# Bulk Loader
# ============================================================

def load_all_graphs(normalized: bool = False) -> Dict[str, nx.DiGraph]:
    """
    Load all graphs in /graphs/ or /graphs_normalized/.

    Args:
        normalized:
            If True, load from /graphs_normalized/.
            If False, load from /graphs/.

    Returns:
        A dictionary mapping:
            { period_string : NetworkX DiGraph }

    Notes:
        - Automatically loads both monthly (YYYY-MM) and yearly (YYYY)
          normalized graphs when normalized=True.
        - Files that do not contain a valid period are skipped.
        - Sorting is handled downstream (e.g., via sort_periods()).
        - This function guarantees deterministic loading order.
    """
    graph_dir = "graphs_normalized" if normalized else "graphs"
    graphs: Dict[str, nx.DiGraph] = {}

    if not os.path.exists(graph_dir):
        raise FileNotFoundError(f"Graph directory not found: {graph_dir}")

    for file in sorted(os.listdir(graph_dir)):
        if not file.endswith(".gpickle"):
            continue

        try:
            period = extract_period(file)
            graphs[period] = load_graph_by_period(period, normalized=normalized)
        except Exception:
            # Skip files that do not match expected patterns
            continue

    return graphs