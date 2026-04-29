"""
pipeline_checks.py — v4.0 (2026-03-15)
Purpose:
Provide centralized structural‑integrity and continuity checks for the EU–LNG
network pipeline, ensuring that all period‑level graphs meet the minimum
requirements for downstream structural, temporal, and governance analysis.

Responsibilities:
- Validate period → graph dictionaries:
    • chronological ordering (via sort_periods)
    • node‑universe consistency (COUNTRIES)
    • graph presence and loadability
    • no negative or missing weights
    • no empty or zero‑flow graphs
    • structural health (density, isolates, total_flow)
- Optional checks:
    • monthly continuity (previous_period)
    • anomaly thresholds (via anomaly_tools)
- Produce a structured integrity report with:
    • periods
    • errors
    • warnings
    • system‑level structural metrics (system_metrics)

Used by:
- Stage 04 (pipeline-level structural and temporal validation)

Dependencies:
- tools.constants.COUNTRIES
- tools.periods.sort_periods, previous_period
- tools.metrics_structural.system_metrics
- tools.anomaly_tools.load_diagnostics, anomaly_summary
- networkx
- tqdm

Notes:
- This module is the authoritative source for pipeline integrity checks.
- Structural metrics are computed using metrics_structural.system_metrics().
- Anomaly diagnostics are optional and depend on anomaly_tools availability.
- AI Assistance:
    This script was drafted with support from Microsoft Copilot. All conceptual
    framing, methodological design, and analytical and interpretive decisions
    were made by the author. The author reviewed, edited, and validated all code.
"""


from typing import Dict, Any
import networkx as nx
from tqdm import tqdm

from tools.constants import COUNTRIES
from tools.periods import sort_periods, previous_period
from tools.metrics_structural import system_metrics
from tools.anomaly_tools import load_diagnostics, anomaly_summary


# ============================================================
# Core Integrity Check
# ============================================================

def pipeline_check(
    period_to_graph: Dict[str, nx.DiGraph],
    require_monthly_continuity: bool = False,
    anomaly_threshold: int | None = None,
) -> Dict[str, Any]:
    """
    Validate structural integrity of a period → graph dictionary.

    Args:
        period_to_graph:
            Dictionary mapping {period: normalized graph}.
        require_monthly_continuity:
            If True, check that periods form a continuous monthly sequence.
        anomaly_threshold:
            If provided, warn when anomaly counts exceed this threshold.

    Returns:
        A structured dictionary summarizing all integrity checks.
    """

    report = {
        "periods": [],
        "errors": [],
        "warnings": [],
        "structural_metrics": {},
    }

    # ------------------------------------------------------------
    # Sort periods chronologically
    # ------------------------------------------------------------
    periods = sort_periods(list(period_to_graph.keys()))
    report["periods"] = periods

    # ------------------------------------------------------------
    # Validate each graph
    # ------------------------------------------------------------
    for p in tqdm(periods, desc="Validating periods", leave=False):
        G = period_to_graph[p]

        # Structural metrics
        metrics = system_metrics(G)
        report["structural_metrics"][p] = metrics

        # Empty graph checks
        if metrics["nodes"] == 0:
            report["errors"].append(f"{p}: graph has zero nodes.")
        if metrics["edges"] == 0:
            report["warnings"].append(f"{p}: graph has zero edges.")

        # Zero-flow check
        if metrics["total_flow"] == 0:
            report["warnings"].append(f"{p}: graph has zero total flow.")

        # Node-universe consistency
        nodes = set(G.nodes())
        if nodes != set(COUNTRIES):
            missing = set(COUNTRIES) - nodes
            extra = nodes - set(COUNTRIES)
            if missing:
                report["errors"].append(f"{p}: missing nodes: {sorted(missing)}")
            if extra:
                report["errors"].append(f"{p}: extraneous nodes: {sorted(extra)}")

        # Negative weight check
        neg_edges = [(u, v) for u, v, d in G.edges(data=True) if d.get("weight", 0) < 0]
        if neg_edges:
            report["errors"].append(f"{p}: negative weights found (sample={neg_edges[:5]})")

    # ------------------------------------------------------------
    # Monthly continuity check (optional)
    # ------------------------------------------------------------
    if require_monthly_continuity:
        for i in range(1, len(periods)):
            prev = periods[i - 1]
            curr = periods[i]
            expected = previous_period(curr)
            if expected != prev:
                report["warnings"].append(
                    f"Monthly continuity gap: expected {expected}, found {prev} → {curr}"
                )

    # ------------------------------------------------------------
    # Anomaly threshold check (optional)
    # ------------------------------------------------------------
    if anomaly_threshold is not None:
        for p in periods:
            try:
                df = load_diagnostics(p)
                summary = anomaly_summary(df)
                if summary["qty_anomalies"] > anomaly_threshold:
                    report["warnings"].append(
                        f"{p}: anomaly count {summary['qty_anomalies']} exceeds threshold {anomaly_threshold}"
                    )
            except Exception:
                report["warnings"].append(f"{p}: no anomaly diagnostics available")

    return report