"""
stage07_network_interpretation.py — v6.0 (2026-04-03)
Purpose:
Integrate structural, temporal, and break‑detection outputs into a unified
governance dataset, and compute node‑, edge‑, and community‑level metrics
for governance‑ready analysis.

Inputs:
- Period‑level summaries:
    summaries/period_summary.csv
    summaries/period_temporal_metrics.csv
    summaries/top_edges.csv (optional)
- Break‑detection outputs:
    breaks/breaks_summary_all_periods.csv (optional)
    breaks/breaks_flags.csv (optional)
    breaks/breaks_edges.csv (optional; corridor change metrics)
- Normalized graphs:
    graphs_normalized/graph_<YYYY-MM>_normalized.gpickle
- Utility modules:
    load_csv(), load_all_graphs(),
    node_centrality_metrics(), edge_centrality_metrics()

Responsibilities:
- Load period‑level summaries, temporal metrics, and break‑detection outputs
- Build unified governance core dataset (period‑level integration)
- Compute:
    - node‑level metrics (centrality, flow share)
    - edge‑level metrics (edge betweenness, corridor dominance, break deltas)
    - community structure (Louvain partitions, modularity)
    - governance mechanism timeline (episodes)
- Export:
    - node‑, edge‑, and community‑level metrics across all periods
    - governance mechanism timeline
    - modularity values per period
- Compute structural deltas (yearly and monthly separately):
    - total_flow, density, nodes, edges
    - node‑level deltas (centrality, flow share)
    - edge‑level deltas (abs/relative change)
- Merge all deltas and modularity into governance_report_core

Outputs:
- Governance core dataset:
    governance/governance_report_core.csv
- Node‑level metrics:
    governance/nodes_centrality_all_periods.csv
- Edge‑level metrics:
    governance/edges_centrality_all_periods.csv
- Community‑level metrics:
    governance/communities_all_periods.csv
    governance/community_nodes_all_periods.csv
- Governance mechanism timeline:
    governance/governance_mechanisms_timeline.csv
- Log file:
    logs/stage07_network_interpretation_<timestamp>.log

Notes:
- Stage 07 integrates all upstream outputs into a governance‑ready dataset
- No graphs are modified; all metrics are computed on copies
- Community detection uses Louvain on the active‑flow subgraph
- Structural deltas are computed separately for yearly and monthly sequences
- AI Assistance:
    This script was drafted with support from Microsoft Copilot. All conceptual
    framing, methodological design, and analytical and interpretive decisions
    were made by the author. The author reviewed, edited, and validated all code.
"""


import os
import logging
from datetime import datetime

import pandas as pd
import numpy as np
import networkx as nx
from community import community_louvain
from tqdm import tqdm

from tools.io_utils import load_csv
from tools.graph_loader import load_all_graphs
from tools.metrics_structural import (
    node_centrality_metrics,
    edge_centrality_metrics,
)

# ============================================================
# Setup
# ============================================================

SCRIPT_VERSION = "v6.0 (2026-04-03)"

GOV_DIR = "governance"
os.makedirs(GOV_DIR, exist_ok=True)

LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)

timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
LOG_FILE = os.path.join(LOG_DIR, f"stage07_network_interpretation_{timestamp}.log")

# Reset handlers
for h in logging.root.handlers[:]:
    logging.root.removeHandler(h)

logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    encoding="utf-8"
)

logging.info("=== Starting Stage 07: Governance Integration ===")
logging.info(f"Script version: {SCRIPT_VERSION}")

# ============================================================
# Governance dataset integration
# ============================================================

def load_governance_inputs():
    period_summary = load_csv(os.path.join("summaries", "period_summary.csv"))
    period_temporal = load_csv(os.path.join("summaries", "period_temporal_metrics.csv"))
    top_edges = load_csv(os.path.join("summaries", "top_edges.csv"), required=False)

    breaks_summary = load_csv(
        os.path.join("breaks", "breaks_summary_all_periods.csv"),
        required=False,
    )
    breaks_flags = load_csv(
        os.path.join("breaks", "breaks_flags.csv"),
        required=False,
    )

    return period_summary, period_temporal, top_edges, breaks_summary, breaks_flags


def build_governance_core(period_summary, period_temporal,
                          breaks_summary, breaks_flags) -> pd.DataFrame:
    """
    Build unified governance dataset at period level.
    """

    core = period_summary.merge(
        period_temporal,
        on="period",
        how="left",
        suffixes=("", "_tmp"),
    )

    # Break flags → detect boolean columns
    if breaks_flags is not None and not breaks_flags.empty:

        bf = breaks_flags.copy()

        flag_cols = [
            c for c in bf.columns
            if c not in ("period", "comparison") and bf[c].dtype == bool
        ]

        if flag_cols:
            bf["any_break_flag"] = bf[flag_cols].max(axis=1)

            bf_period = (
                bf.groupby("period")["any_break_flag"]
                .max()
                .reset_index()
            )

            core = core.merge(bf_period, on="period", how="left")
        else:
            core["any_break_flag"] = None

    else:
        core["any_break_flag"] = None

    return core.sort_values("period")


def write_governance_core(df: pd.DataFrame):
    out_path = os.path.join(GOV_DIR, "governance_report_core.csv")
    df.to_csv(out_path, index=False)
    print(f"Governance core written to {out_path}")
    logging.info(f"Governance core written to {out_path}")


# ============================================================
# Node, Edge, and Community Metrics Export
# ============================================================

# Load corridor change metrics from Stage 05 updated 4.14.26
BREAKS_EDGES_PATH = os.path.join("breaks", "breaks_edges.csv")
if os.path.exists(BREAKS_EDGES_PATH):
    breaks_edges_df = pd.read_csv(BREAKS_EDGES_PATH)
    # Parse edge tuple strings like "('TTO','ESP')" into exporter/importer
    breaks_edges_df["exporter"] = breaks_edges_df["edge"].apply(lambda x: eval(x)[0])
    breaks_edges_df["importer"] = breaks_edges_df["edge"].apply(lambda x: eval(x)[1])
else:
    breaks_edges_df = pd.DataFrame()


def compute_and_export_metrics(period_to_graph, top_edges, breaks_summary):

    all_nodes_rows = []
    all_communities_rows = []
    all_period_modularity = []
    all_community_nodes_rows = []
    all_edge_centrality_rows = []
    governance_timeline_rows = []

    last_mechanism = None
    episode_id = 0

    for period, G in tqdm(period_to_graph.items(), desc="Computing metrics"):

        # Governance mechanism timeline
        if breaks_summary is not None and not breaks_summary.empty:
            sub = breaks_summary[breaks_summary["period"] == period]
            for _, row in sub.iterrows():
                mech = row.get("mechanism", None)

                if mech != last_mechanism:
                    episode_id += 1
                    last_mechanism = mech

                governance_timeline_rows.append({
                    "period": row["period"],
                    "comparison": row["comparison"],
                    "mechanism": mech,
                    "severity_score": row.get("severity_score", None),
                    "episode_id": episode_id,
                })

        # Remove isolates for metrics
        G_clean = G.copy()
        G_clean.remove_nodes_from(list(nx.isolates(G_clean)))

        if G_clean.number_of_nodes() == 0:
            continue

        # Node-level metrics
        cent = node_centrality_metrics(G_clean)
        eig = cent["eigenvector_norm"]
        bet = cent["betweenness_norm"]
        strength = cent["strength"]
        flow_centrality = cent["flow_centrality"]

        nodes_metrics = list(flow_centrality.keys())
        total_flow = sum(flow_centrality.values()) or 1.0

        node_flow_share = {
            n: flow_centrality[n] / total_flow
            for n in nodes_metrics
        }

        # ------------------------------------------------------------
        # Community detection + modularity on the active-flow subgraph
        # ------------------------------------------------------------
        
        # Restrict graph to nodes with defined flow_centrality
        H = G_clean.subgraph(nodes_metrics).copy()
        
        # If no edges, modularity is defined as 0 (no structure)
        if H.number_of_edges() == 0:
            modularity_value = 0.0
        else:
            # Run Louvain on the active subgraph only
            partition = community_louvain.best_partition(
                H.to_undirected(),
                weight="weight",
                resolution=1.0,
                random_state=42
            )
        
            # Compute modularity on the same subgraph
            modularity_value = community_louvain.modularity(
                partition,
                H.to_undirected(),
                weight="weight"
            )

        all_period_modularity.append({
            "period": period,
            "modularity": modularity_value,
        })

        # Community aggregates
        comm_size = {}
        comm_flow = {}

        for n in nodes_metrics:
            c = partition.get(n)
            if c is None:
                continue
            comm_size[c] = comm_size.get(c, 0) + 1
            comm_flow[c] = comm_flow.get(c, 0) + flow_centrality[n]

        for c in comm_size:
            flow_share = comm_flow[c] / total_flow
            all_communities_rows.append({
                "period": period,
                "community": c,
                "size": comm_size[c],
                "total_flow": comm_flow[c],
                "flow_share": flow_share,
            })

        # Node → community assignments
        for n in nodes_metrics:
            c = partition.get(n)
            if c is None:
                continue
            all_community_nodes_rows.append({
                "period": period,
                "node": n,
                "community": c,
            })

        # Node-level export
        df_nodes = pd.DataFrame({
            "period": period,
            "node": nodes_metrics,
            "community": [partition.get(n) for n in nodes_metrics],
            "eigenvector": [eig.get(n, 0) for n in nodes_metrics],
            "betweenness": [bet.get(n, 0) for n in nodes_metrics],
            "strength": [strength.get(n, 0) for n in nodes_metrics],
            "flow_centrality": [flow_centrality[n] for n in nodes_metrics],
            "flow_share": [node_flow_share[n] for n in nodes_metrics],
        })

        all_nodes_rows.extend(df_nodes.to_dict("records"))

        # Edge-level metrics
        edge_bet = edge_centrality_metrics(G_clean)
        
        # Total flow for corridor dominance (flow share)
        total_flow_period = sum(
            nx.get_edge_attributes(G_clean, "weight").values()
        ) or 0.0
        
        for (u, v), val in edge_bet.items():
        
            # Base row from Stage 07 metrics
            row = {
                "period": period,
                "exporter": u,
                "importer": v,
                "edge_betweenness": val,
                "weight": G_clean[u][v].get("weight", 0),
            }
        
            # ------------------------------------------------------------
            # Merge corridor change metrics from Stage 05 (breaks_edges.csv)
            # ------------------------------------------------------------
            if not breaks_edges_df.empty:
                match = breaks_edges_df[
                    (breaks_edges_df["period"] == period) &
                    (breaks_edges_df["exporter"] == u) &
                    (breaks_edges_df["importer"] == v)
                ]
        
                if not match.empty:
                    row["w_prev"] = match["w_prev"].values[0]
                    row["w_curr"] = match["w_curr"].values[0]
                    row["rel_change"] = match["rel_change"].values[0]
                else:
                    row["w_prev"] = None
                    row["w_curr"] = None
                    row["rel_change"] = None
        
            # ------------------------------------------------------------
            # Corridor dominance (flow share)
            # ------------------------------------------------------------
            if total_flow_period > 0:
                row["flow_share"] = row["weight"] / total_flow_period
            else:
                row["flow_share"] = None
        
            # Append final row
            all_edge_centrality_rows.append(row)
            
    # Write outputs
    pd.DataFrame(all_nodes_rows).to_csv(
        os.path.join(GOV_DIR, "nodes_centrality_all_periods.csv"), index=False
    )
    pd.DataFrame(all_communities_rows).to_csv(
        os.path.join(GOV_DIR, "communities_all_periods.csv"), index=False
    )
    pd.DataFrame(all_community_nodes_rows).to_csv(
        os.path.join(GOV_DIR, "community_nodes_all_periods.csv"), index=False
    )
    pd.DataFrame(all_edge_centrality_rows).to_csv(
        os.path.join(GOV_DIR, "edges_centrality_all_periods.csv"), index=False
    )
    pd.DataFrame(governance_timeline_rows).to_csv(
        os.path.join(GOV_DIR, "governance_mechanisms_timeline.csv"), index=False
    )

    print("Governance metrics exported.")
    logging.info("Governance metrics exported.")

    return all_period_modularity
# ============================================================
# Structural Delta Metrics (yearly vs monthly)
# ============================================================

def compute_period_deltas(df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute period-level deltas separately for yearly and monthly rows.
    No cross-contamination between sequences.
    """

    df = df.copy()

    # Ensure delta columns exist
    for col in ["delta_total_flow", "delta_density", "delta_nodes", "delta_edges"]:
        df[col] = np.nan

    # ---------- YEARLY ----------
    yearly = df[df["is_year"]].sort_values("period").copy()
    yearly["delta_total_flow"] = yearly["total_flow"].diff()
    yearly["delta_density"] = yearly["density"].diff()
    yearly["delta_nodes"] = yearly["nodes"].diff()
    yearly["delta_edges"] = yearly["edges"].diff()

    # ---------- MONTHLY ----------
    monthly = df[df["is_month"]].sort_values("period").copy()
    monthly["delta_total_flow"] = monthly["total_flow"].diff()
    monthly["delta_density"] = monthly["density"].diff()
    monthly["delta_nodes"] = monthly["nodes"].diff()
    monthly["delta_edges"] = monthly["edges"].diff()

    # Write back
    df.loc[yearly.index, ["delta_total_flow","delta_density","delta_nodes","delta_edges"]] = \
        yearly[["delta_total_flow","delta_density","delta_nodes","delta_edges"]]

    df.loc[monthly.index, ["delta_total_flow","delta_density","delta_nodes","delta_edges"]] = \
        monthly[["delta_total_flow","delta_density","delta_nodes","delta_edges"]]

    return df


def compute_node_edge_deltas(governance_core: pd.DataFrame):

    nodes_all = pd.read_csv(os.path.join(GOV_DIR, "nodes_centrality_all_periods.csv"))
    edges_all = pd.read_csv(os.path.join(GOV_DIR, "edges_centrality_all_periods.csv"))

    flags = governance_core[["period","is_year","is_month"]]
    nodes_all = nodes_all.merge(flags, on="period", how="left")
    edges_all = edges_all.merge(flags, on="period", how="left")

    # ---------- EDGE DELTAS ----------
    def edge_deltas(sub):
        sub = sub.sort_values(["exporter","importer","period"])
        sub["prev_weight"] = sub.groupby(["exporter","importer"])["weight"].shift(1)
        sub["edge_abs_change"] = sub["weight"] - sub["prev_weight"]
        sub["edge_rel_change"] = sub["edge_abs_change"] / sub["prev_weight"]
        sub["edge_rel_change"] = sub["edge_rel_change"].replace([np.inf,-np.inf], np.nan).fillna(0)
        return sub

    edges_yearly = edge_deltas(edges_all[edges_all["is_year"]].copy())
    edges_monthly = edge_deltas(edges_all[edges_all["is_month"]].copy())

    edges_clean = pd.concat([edges_yearly, edges_monthly], ignore_index=True)

    edge_delta_summary = edges_clean.groupby("period").agg(
        max_edge_change=("edge_rel_change","max"),
        mean_edge_change=("edge_rel_change","mean"),
    ).reset_index()

    # ---------- NODE DELTAS ----------
    def node_deltas(sub):
        sub = sub.sort_values(["node","period"])
        for col in ["eigenvector","betweenness","strength","flow_centrality","flow_share"]:
            sub[f"delta_{col}"] = sub.groupby("node")[col].diff()
        return sub

    nodes_yearly = node_deltas(nodes_all[nodes_all["is_year"]].copy())
    nodes_monthly = node_deltas(nodes_all[nodes_all["is_month"]].copy())

    nodes_clean = pd.concat([nodes_yearly, nodes_monthly], ignore_index=True)

    node_delta_summary = nodes_clean.groupby("period").agg(
        delta_eigenvector_max=("delta_eigenvector","max"),
        delta_betweenness_max=("delta_betweenness","max"),
        delta_strength_max=("delta_strength","max"),
        delta_flow_centrality_max=("delta_flow_centrality","max"),
        delta_flow_share_max=("delta_flow_share","max"),
    ).reset_index()

    return edge_delta_summary, node_delta_summary


# ============================================================
# Main
# ============================================================

def main():

    # Load inputs
    (period_summary,
     period_temporal,
     top_edges,
     breaks_summary,
     breaks_flags) = load_governance_inputs()

    # Build governance core (no deltas yet)
    governance_core = build_governance_core(
        period_summary,
        period_temporal,
        breaks_summary,
        breaks_flags,
    )
    write_governance_core(governance_core)

    # Load graphs
    period_to_graph = load_all_graphs(normalized=True)

    # Compute and export metrics (nodes, edges, communities, modularity)
    all_period_modularity = compute_and_export_metrics(period_to_graph, top_edges, breaks_summary)

    # ============================================================
    # Structural-delta metrics (v6.0, yearly vs monthly)
    # ============================================================

    print("Computing structural-delta metrics for governance_report_core...")
    logging.info("Computing structural-delta metrics (yearly vs monthly)...")

    # Reload governance core to ensure we start from the written version
    governance_core = pd.read_csv(os.path.join(GOV_DIR, "governance_report_core.csv"))

    # Infer yearly vs monthly from period string
    governance_core["period"] = governance_core["period"].astype(str)
    governance_core["is_month"] = governance_core["period"].str.contains("-")
    governance_core["is_year"] = ~governance_core["is_month"]

    # 1. Recompute period-level deltas (total_flow, density, nodes, edges)
    governance_core = compute_period_deltas(governance_core)

    # 2. Compute node- and edge-level deltas separately for yearly/monthly
    edge_delta_summary, node_delta_summary = compute_node_edge_deltas(governance_core)

    # 3. Merge deltas and modularity into governance_report_core
    governance_core = governance_core.merge(edge_delta_summary, on="period", how="left")
    governance_core = governance_core.merge(node_delta_summary, on="period", how="left")

    mod_df = pd.DataFrame(all_period_modularity)
    governance_core = governance_core.merge(mod_df, on="period", how="left")

    # Final write
    governance_core.to_csv(os.path.join(GOV_DIR, "governance_report_core.csv"), index=False)

    print("Structural-delta metrics added to governance_report_core.")
    logging.info("Structural-delta metrics merged.")

    print("Stage 07 (governance integration) complete.")
    logging.info("Stage 07 (governance integration) complete.")


if __name__ == "__main__":
    main()