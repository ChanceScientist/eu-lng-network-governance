"""
stage05_detect_breaks.py — v4.9 (2026-03-23)
Purpose:
Detect governance‑relevant structural breaks in normalized LNG trade graphs by
computing system‑level deltas, node‑level centrality shifts, edge‑level changes,
and governance‑aligned structural signatures.

Inputs:
- Normalized graphs:
    graphs_normalized/graph_<YYYY-MM>_normalized.gpickle
- Utility modules:
    sort_periods(), load_all_graphs(), governance_break_panel(),
    detect_flow_surge(), detect_flow_collapse(),
    detect_connectivity_expansion(), detect_connectivity_contraction(),
    detect_role_diversification(), node_centrality_metrics()

Responsibilities:
- Load all normalized monthly graphs and sort periods
- Compute system‑level deltas vs previous month and previous year
- Compute normalized node‑level centrality deltas
- Identify edge‑level changes:
    - new / dropped edges
    - large relative edge‑weight shifts (“big changes”)
- Classify structural signatures:
    - flow surge / collapse
    - connectivity expansion / contraction
    - role diversification
- Assign governance mechanism labels (e.g., Diversification, Chokepoint Shift)
- Evaluate governance‑relevant break condition (gov_break)
- Compute severity scores combining flow, density, edges, centrality, and big‑edge metrics
- Export per‑period break panels and unified multi‑period summaries

Outputs:
- Per‑period break panels:
    breaks/breaks_panel_<YYYY-MM>.csv
- Unified summaries:
    breaks/breaks_summary_all_periods.csv
    breaks/breaks_edges.csv
    breaks/breaks_nodes.csv
    breaks/breaks_flags.csv
- Log file:
    logs/stage05_detect_breaks_<timestamp>.log

Notes:
- This script does NOT modify graphs
- Converts raw structural deltas into governance‑aligned signatures
- gov_break provides a selective, interpretable indicator of meaningful
  structural change for IRAC‑based analysis and narrative development
- Threshold tuning should be performed using stage05_test_config.py
- AI Assistance:
    This script was drafted with support from Microsoft Copilot. All conceptual
    framing, methodological design, and analytical and interpretive decisions
    were made by the author. The author reviewed, edited, and validated all code.
"""

SCRIPT_VERSION = "v4.9 (2026-03-23)"

# ============================================================
# Configuration: structural signature thresholds
# ============================================================

CONFIG = {
    "flow_threshold": 0.5,          # relative edge-weight change
    "flow_surge_ratio": 2.60,       # 1.30 = +30% system-wide flow increase
    "flow_collapse_ratio": 0.70,    # 0.70 = -30% system-wide flow decrease
    "density_threshold": 0.020,      # absolute density change
    "edges_threshold": 35,           # edge count change
    "centrality_threshold": 0.07,   # normalized centrality shift
    "min_big_edge_changes": 3,      # governance flag threshold
}

# ============================================================
# Setup
# ============================================================

import os
import logging
import pandas as pd
from tqdm import tqdm
from datetime import datetime

from tools.periods import sort_periods
from tools.graph_loader import load_all_graphs
from tools.governance_breaks import governance_break_panel
from tools.metrics_structural import (
    detect_flow_surge,
    detect_flow_collapse,
    detect_connectivity_expansion,
    detect_connectivity_contraction,
    detect_role_diversification,
    node_centrality_metrics,
)

OUT_DIR = "breaks"
LOG_DIR = "logs"

os.makedirs(OUT_DIR, exist_ok=True)
os.makedirs(LOG_DIR, exist_ok=True)

timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
LOG_FILE = os.path.join(LOG_DIR, f"stage05_detect_breaks_{timestamp}.log")

# Reset handlers
for h in logging.root.handlers[:]:
    logging.root.removeHandler(h)

logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    encoding="utf-8"
)

logging.info("=== Starting Break Detection Pipeline ===")
logging.info(f"Script version: {SCRIPT_VERSION}")
logging.info(f"Configuration: {CONFIG}")

# ============================================================
# Load normalized graphs
# ============================================================

graphs = load_all_graphs(normalized=True)

if not graphs:
    logging.error("No normalized graphs found. Exiting.")
    raise SystemExit

periods = sort_periods(list(graphs.keys()))
logging.info(f"Discovered {len(periods)} periods for break detection")
print(f"Loaded {len(periods)} normalized graphs.")

# ============================================================
# Structural Signature Classification
# ============================================================

def classify_signatures(delta: dict, cent_delta: dict) -> dict:
    """Apply threshold logic to classify structural signatures."""
    return {
        "flow_surge": detect_flow_surge(
            delta["total_flow_delta"],
            delta["total_flow_ratio"],
            CONFIG["flow_surge_ratio"],
        ),
        "flow_collapse": detect_flow_collapse(
            delta["total_flow_ratio"],
            CONFIG["flow_collapse_ratio"],
        ),
        "connectivity_expansion": (
            detect_connectivity_expansion(delta["density_delta"], CONFIG["density_threshold"])
            or detect_connectivity_expansion(delta["edges_delta"], CONFIG["edges_threshold"])
        ),
        "connectivity_contraction": (
            detect_connectivity_contraction(delta["density_delta"], CONFIG["density_threshold"])
            or detect_connectivity_contraction(delta["edges_delta"], CONFIG["edges_threshold"])
        ),
        "role_diversification": detect_role_diversification(
            cent_delta,
            CONFIG["centrality_threshold"],
        ),
    }

def classify_governance_mechanism(flags: dict) -> str:
    """
    Map structural signature flags to a governance mechanism label.
    Priority order reflects interpretive salience.
    """
    if flags.get("flow_surge"):
        return "Emergency Procurement / Surge"
    if flags.get("flow_collapse"):
        return "Supply Disruption / Collapse"
    if flags.get("connectivity_expansion"):
        return "Diversification"
    if flags.get("connectivity_contraction"):
        return "Structural Tightening"
    if flags.get("role_diversification"):
        return "Chokepoint Shift / Role Redistribution"
    return "None"
    
# ============================================================
# Break detection
# ============================================================

summary_rows = []
edge_rows = []
node_rows = []
flag_rows = []

for period in tqdm(periods, desc="Detecting breaks"):
    try:
        panel = governance_break_panel(
            period,
            graphs,
            flow_threshold=CONFIG["flow_threshold"],
        )

        for comp_type, result in panel.items():
            delta = result["graph_delta"]
            cent_delta = {
                "betweenness_norm": result["centrality_delta"]["betweenness_norm"],
                "eigenvector_norm": result["centrality_delta"]["eigenvector_norm"],
                "flow_centrality_norm": result["centrality_delta"]["flow_centrality_norm"],
            }

            flags_struct = classify_signatures(delta, cent_delta)
            governance_mechanism = classify_governance_mechanism(flags_struct)
            governance_break = (
                (
                    flags_struct["flow_surge"]
                    or flags_struct["flow_collapse"]
                    or flags_struct["connectivity_expansion"]
                    or flags_struct["connectivity_contraction"]
                )
                and (
                    flags_struct["role_diversification"]
                    or (len(result["big_edge_changes"]) >= CONFIG["min_big_edge_changes"])
                )
            )

            # -----------------------------------------
            # Max centrality delta (absolute) (v4.7)
            # -----------------------------------------
            max_centrality_delta = 0.0
            for metric, nodevals in cent_delta.items():
                for v in nodevals.values():
                    if v is not None:
                        max_centrality_delta = max(max_centrality_delta, abs(v))
            
            # Max edge relative change (v4.6)
            if result["big_edge_changes"]:
                max_edge_rel_change = max(abs(e["rel_change"]) for e in result["big_edge_changes"])
            else:
                max_edge_rel_change = 0.0
            
            # Total magnitude of big edge changes (v4.6)
            total_big_edge_change_weight = sum(abs(e["rel_change"]) for e in result["big_edge_changes"])
            
            # Net edge change (expansion vs contraction) (v4.6)
            net_edge_change = len(result["new_edges"]) - len(result["dropped_edges"])
            
            # -----------------------------------------
            # Severity score (v4.9)
            # -----------------------------------------
            # Flow component: deviation from continuity (ratio-based, 0 = no change)
            flow_ratio = delta.get("total_flow_ratio")
            if flow_ratio is None:
                flow_component = 0.0
            else:
                flow_component = abs(flow_ratio - 1.0)

            # Density component: scaled by configured threshold
            density_component = abs(delta["density_delta"]) / max(CONFIG["density_threshold"], 1e-9)

            # Edge count component: scaled by configured threshold
            edge_component = abs(delta["edges_delta"]) / max(CONFIG["edges_threshold"], 1)

            # Big edge changes: scaled by governance flag threshold
            big_edge_component = len(result["big_edge_changes"]) / max(CONFIG["min_big_edge_changes"], 1)

            # Centrality component: normalized by centrality threshold
            centrality_component = max_centrality_delta / max(CONFIG["centrality_threshold"], 1e-9)

            # Composite severity score (dimensionless, governance-aligned)
            severity = (
                flow_component
                + density_component
                + edge_component
                + big_edge_component
                + centrality_component
            )

            # Unified row for summary_all_periods
            summary_rows.append({
                # --------------------------------------------------------
                # 1. Period & Comparison Context
                # --------------------------------------------------------
                "period": period,
                "comparison": comp_type,
                "period_prev": delta["period_prev"],
              
                # --------------------------------------------------------
                # 2. System-Level Structural Deltas
                # --------------------------------------------------------
                "total_flow_delta": delta["total_flow_delta"],
                "total_flow_ratio": delta["total_flow_ratio"],
                "density_delta": delta["density_delta"],
                "edges_delta": delta["edges_delta"],
                "isolates_delta": delta["isolates_delta"],
            
                # --------------------------------------------------------
                # 3. Structural Signature Flags
                # --------------------------------------------------------
                "flow_surge": flags_struct["flow_surge"],
                "flow_collapse": flags_struct["flow_collapse"],
                "connectivity_expansion": flags_struct["connectivity_expansion"],
                "connectivity_contraction": flags_struct["connectivity_contraction"],
                "role_diversification": flags_struct["role_diversification"],

                # --------------------------------------------------------
                # 4. Governance-Relevant Break Classification
                # -------------------------------------------------------- 
                "gov_break": governance_break,
                "mechanism": governance_mechanism,

                # --------------------------------------------------------
                # 5. Severity & Structural Metrics
                # --------------------------------------------------------
                "max_centrality_delta": max_centrality_delta,
                "severity_score": severity,
                
                # --------------------------------------------------------
                # 6. Edge-Level Change Metrics
                # --------------------------------------------------------
                "num_big_edge_changes": len(result["big_edge_changes"]),
                "num_new_edges": len(result["new_edges"]),
                "num_dropped_edges": len(result["dropped_edges"]),
                "net_edge_change": net_edge_change,
                "max_edge_rel_change": max_edge_rel_change,
                "total_big_edge_change_weight": total_big_edge_change_weight,
                                     
            })
            
            # Node changes
            for n in result["new_nodes"]:
                node_rows.append({
                    "period": period,
                    "comparison": comp_type,
                    "node": n,
                    "type": "new",
                })
            for n in result["dropped_nodes"]:
                node_rows.append({
                    "period": period,
                    "comparison": comp_type,
                    "node": n,
                    "type": "dropped",
                })

            # Normalized centrality deltas for each node
            for metric, nodevals in cent_delta.items():
                for node, val in nodevals.items():
                    node_rows.append({
                        "period": period,
                        "comparison": comp_type,
                        "node": node,
                        "metric": metric,
                        "centrality_delta": val,
                    })

            # Edge changes
            for e in result["big_edge_changes"]:
                edge_rows.append({
                    "period": period,
                    "comparison": comp_type,
                    "edge": str(e["edge"]),
                    "w_prev": e["w_prev"],
                    "w_curr": e["w_curr"],
                    "rel_change": e["rel_change"],
                })

            # Governance flags (v4.1)
            flag_rows.append({
                # 1. Context
                "period": period,
                "comparison": comp_type,
            
                # 2. Raw structural flags
                "large_flow_shift": len(result["big_edge_changes"]) >= CONFIG["min_big_edge_changes"],
                "node_changes": len(result["new_nodes"]) + len(result["dropped_nodes"]) > 0,
                "edge_changes": len(result["new_edges"]) + len(result["dropped_edges"]) > 0,
                "structural_shift": abs(delta["density_delta"]) > CONFIG["density_threshold"],
                "flow_collapse": (
                    delta["total_flow_ratio"] is not None
                    and delta["total_flow_ratio"] < CONFIG["flow_collapse_ratio"]
                ),
            
                # 3. Combined governance-relevant break
                "gov_break": governance_break,
            })

        # Per-period panel output
        panel_df = pd.DataFrame([
            row for row in summary_rows if row["period"] == period
        ])
        panel_df.to_csv(
            os.path.join(OUT_DIR, f"breaks_panel_{period}.csv"),
            index=False
        )

    except Exception as e:
        msg = f"Error processing period {period}: {e}"
        logging.error(msg)
        print(msg)

# ============================================================
# Export unified outputs
# ============================================================

pd.DataFrame(summary_rows).to_csv(
    os.path.join(OUT_DIR, "breaks_summary_all_periods.csv"), index=False
)
pd.DataFrame(edge_rows).to_csv(
    os.path.join(OUT_DIR, "breaks_edges.csv"), index=False
)
pd.DataFrame(node_rows).to_csv(
    os.path.join(OUT_DIR, "breaks_nodes.csv"), index=False
)
pd.DataFrame(flag_rows).to_csv(
    os.path.join(OUT_DIR, "breaks_flags.csv"), index=False
)

logging.info("=== Break Detection Pipeline Complete ===")
print("Structural break detection complete.")