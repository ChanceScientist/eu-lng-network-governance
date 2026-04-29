"""
stage07_helpers.py — v[none]
Purpose:
Provide shared utilities, loaders, configuration dictionaries, period‑handling
helpers, and visualization engines for all Stage 07 scripts. This module is the
central infrastructure for governance‑aligned interpretation, community
transition analysis, and high‑fidelity network visualization.

Responsibilities:
- Directory management:
    • governance inputs (GOV_DIR)
    • figure outputs (FIG_DIR, TS_DIR)
    • community transition matrices (TRANS_DIR, COMM_TRANS_DIR)

- Configuration dictionaries:
    • CONFIG_VIS — ForceAtlas2, radial blending, gravity, community resolution
    • CONFIG_ROLES — hub/broker thresholds
    • CONFIG_CSCI — composite structural change index weights + required metrics
    • STYLE + PALETTE — consistent time‑series styling

- Period utilities:
    • sort_periods_yearly_first()
    • filter_monthly(), filter_yearly()
    • split_periods() with period_dt attachment

- Governance + community loaders:
    • governance core
    • community assignments
    • transition matrices
    • stability index

- Graph loading:
    • load_graphs() wrapper around tools.graph_loader.load_all_graphs()

- Shared utilities:
    • normalize() — min–max normalization
    • deterministic seeds for reproducibility

- Visualization engines:
    • plot_nodelink_centrality_gravity()
        – ForceAtlas2 backbone + radial orientation
        – eigenvector‑gravity curvature
        – Louvain communities
        – edge betweenness widths
        – isolate removal, clamping, deterministic layout
    • plot_flow_matrix()
    • plot_chord()
    • plot_top_edges_bar()
    • styled_plot(), styled_dual_plot()
    • format_year_axis(), format_month_axis()
    • savefig_clean()

Used by:
- stage07_timeseries.py
- stage07_visuals_per_period.py
- stage07_network_interpretation.py (if present)
- extract_signatures.py (indirectly via governance outputs)
- attribution_indicator_range.py (indirectly)
- attribution_scoring_mechanisms.py (indirectly)

Dependencies:
- tools.metrics_structural:
    • node_centrality_metrics, edge_centrality_metrics
- tools.graph_loader:
    • load_all_graphs (normalized=True)
- External libraries:
    • NetworkX, pandas, numpy, seaborn, matplotlib
    • community_louvain (Louvain clustering)
    • fa2 (ForceAtlas2 layout)

Notes:
- This module defines the canonical visualization and interpretation logic for
  Stage 07. All Stage 07 scripts rely on these helpers for deterministic,
  governance‑aligned outputs.
- All layouts are seeded for reproducibility.
- AI Assistance:
    This script was drafted with support from Microsoft Copilot. All conceptual
    framing, methodological design, and analytical and interpretive decisions
    were made by the author. The author reviewed, edited, and validated all code.
"""


# ============================================================
# Imports & Seeds
# ============================================================

import os
import pandas as pd
import numpy as np
import networkx as nx
import matplotlib
import matplotlib.pyplot as plt
import seaborn as sns
from community import community_louvain
from fa2 import ForceAtlas2

from tools.metrics_structural import (
    node_centrality_metrics,
    edge_centrality_metrics,
)
    
# Global seeds for reproducibility
import random
random.seed(42)
np.random.seed(42)

# ============================================================
# Directory Constants
# ============================================================

GOV_DIR = "governance"
FIG_DIR = "figures"

TS_DIR = os.path.join(FIG_DIR, "timeseries")
TRANS_DIR = os.path.join(GOV_DIR, "community_transition_matrices")
COMM_TRANS_DIR = os.path.join(FIG_DIR, "community_transitions")

# Ensure directories exist
for d in [GOV_DIR, FIG_DIR, TS_DIR, TRANS_DIR, COMM_TRANS_DIR]:
    os.makedirs(d, exist_ok=True)

# ============================================================
# Visualization & Interpretation Parameters
# ============================================================

CONFIG_VIS = {
    # ForceAtlas2 core
    "fa2_gravity": 3.0,          # stronger inward pull; prevents isolate drift
    "fa2_scaling_ratio": 1.4,    # moderate repulsion; keeps core readable

    # Radial + FA2 blending
    "radial_weight": 0.20,       # stronger radial anchor for interpretive orientation
    "spring_weight": 0.80,       # FA2 still drives structure

    # Centrality gravity (your custom inward curvature)
    "gravity_exponent": 0.55,    # gentle curvature; avoids collapse
    "gravity_alpha": 0.32,       # bounded influence; keeps core stable

    # Outlier control
    "clamp_radius": 1.0,         # prevents any node from dominating scale

    # Louvain resolution for community detection
    "louvain_resolution": 1.0,   # stable across sparse/dense networks

    # Chord and Bar visuals
    "top_edges_chord": 40,    # number of edges shown in chord diagrams
    "top_edges_bar": 40,      # number of edges shown in top-edges bar charts
}

CONFIG_ROLES = {
    "hub_eigenvector_threshold": 0.16,
    "broker_betweenness_threshold": 0.09,
}

CONFIG_CSCI = {
    # Columns required for the composite index
    "metric_cols": [
        "delta_total_flow",
        "delta_density",
        "delta_edges",
        "delta_eigenvector_max",
        "modularity",
        "stability_index",
    ],

    # Governance‑aligned weights (must sum to 1.0)
    "weights": {
        "delta_eigenvector_max": 0.35,   # systemic influence shifts
        "delta_total_flow":      0.20,   # macro structural shocks
        "delta_density":         0.10,   # connectivity changes
        "delta_edges":           0.10,   # corridor formation/dissolution
        "stability_index":       0.15,   # community cohesion/fragmentation
        "modularity":            0.10,   # structural polarization
    }
}

# ============================================================
# Period Sorting Helpers
# ============================================================

def sort_periods_yearly_first(df):
    """
    Sorts periods so that:
        YYYY (yearly) come first in chronological order,
        YYYY-MM (monthly) come after, also chronologically.
    """
    df = df.copy()

    # Identify period types
    df["is_year"] = df["period"].str.len() == 4
    df["is_month"] = df["period"].str.len() == 7

    # Convert datetimes separately for each type
    df.loc[df["is_year"], "period_dt"] = pd.to_datetime(
        df.loc[df["is_year"], "period"], format="%Y"
    )
    df.loc[df["is_month"], "period_dt"] = pd.to_datetime(
        df.loc[df["is_month"], "period"], format="%Y-%m"
    )

    # Sort: yearly first, then monthly
    df = df.sort_values(
        by=["is_year", "period_dt"],
        ascending=[False, True]
    )

    return df


def filter_monthly(df):
    """Return only YYYY-MM periods."""
    return df[df["period"].str.len() == 7].copy()


def filter_yearly(df):
    """Return only YYYY periods."""
    return df[df["period"].str.len() == 4].copy()

# ============================================================
# Governance + Community Loaders
# ============================================================

def load_governance_core():
    """Load governance_report_core.csv."""
    path = os.path.join(GOV_DIR, "governance_report_core.csv")
    return pd.read_csv(path)


def load_community_nodes():
    """Load node → community assignments."""
    path = os.path.join(GOV_DIR, "community_nodes_all_periods.csv")
    return pd.read_csv(path)


def load_transition_matrices():
    """Load all transition matrices into a dict keyed by (t, t_next)."""
    matrices = {}
    for fname in os.listdir(TRANS_DIR):
        if fname.startswith("transition_") and fname.endswith(".csv"):
            parts = fname.replace("transition_", "").replace(".csv", "")
            t, t_next = parts.split("_to_")
            df = pd.read_csv(os.path.join(TRANS_DIR, fname), index_col=0)
            matrices[(t, t_next)] = df
    return matrices


def load_stability_index():
    """Load stability index CSV."""
    path = os.path.join(GOV_DIR, "community_stability_index.csv")
    return pd.read_csv(path)

# ============================================================
# Graph Loader Wrapper
# ============================================================

def load_graphs():
    """Wrapper for loading all graphs."""
    from tools.graph_loader import load_all_graphs
    return load_all_graphs(normalized=True)

# ============================================================
# Shared Utility Functions
# ============================================================

def normalize(s):
    """
    Min–max normalize a pandas Series.
    Returns values in [0, 1].
    If the series has no variation, returns zeros.
    """
    s_min = s.min()
    s_max = s.max()
    return (s - s_min) / (s_max - s_min) if s_max != s_min else s * 0

def split_periods(df):
    """
    Split into yearly and monthly subsets AND attach period_dt.
    Ensures correct chronological behavior for Stage 07.
    """
    df = df.copy()

    # Identify period types
    is_year = df["period"].str.len() == 4
    is_month = df["period"].str.len() == 7

    # Yearly
    df_yearly = df[is_year].copy()
    df_yearly["period_dt"] = pd.to_datetime(df_yearly["period"], format="%Y")

    # Monthly
    df_monthly = df[is_month].copy()
    df_monthly["period_dt"] = pd.to_datetime(df_monthly["period"], format="%Y-%m")

    return df_yearly, df_monthly

# ============================================================
# Visualization Helpers (imported by other scripts)
# ============================================================

def plot_nodelink_centrality_gravity(G, period, outpath, all_edge_centrality_rows):
    """
    Centrality-gravity visualization with:
        - eigenvector gravity
        - strength-based node size
        - Louvain communities
        - edge betweenness widths
        - curved edges
    """

    if G.number_of_nodes() == 0:
        return

    # ---------------------------------------------------------
    # 1. Remove isolates (countries with no trade flows)
    # ---------------------------------------------------------
    isolates = list(nx.isolates(G))
    if isolates:
        G = G.copy()
        G.remove_nodes_from(isolates)

    if G.number_of_nodes() == 0:
        return

    # ---------------------------------------------------------
    # 2. Node-level metrics
    # ---------------------------------------------------------
    cent = node_centrality_metrics(G)
    eig = {n: max(0, v) for n, v in cent["eigenvector_norm"].items()}
    strength = cent["strength"]
    flow_centrality = cent["flow_centrality"] 

    # Edge-level metrics
    edge_bet = edge_centrality_metrics(G)
    # Edge centrality summary (v4.10)
    for (u, v), val in edge_bet.items():
        all_edge_centrality_rows.append({
            "period": period,
            "exporter": u,
            "importer": v,
            "edge_betweenness": val,
            "weight": G[u][v].get("weight", 0),
        })
    max_edge_bet = max(edge_bet.values()) if edge_bet else 1.0

    # ---------------------------------------------------------
    # 3. Tuned community detection (collapse micro-communities)
    # ---------------------------------------------------------
    partition = community_louvain.best_partition(
        G.to_undirected(),
        weight="weight",
        resolution=CONFIG_VIS["louvain_resolution"],
        random_state=42
    )
        
    comm = partition
    unique_comms = sorted(set(comm.values()))
    comm_to_color = {c: i for i, c in enumerate(unique_comms)}

    # Categorical palette
    cmap = matplotlib.colormaps["tab20"]

    # ---------------------------------------------------------
    # 4. Layout: ForceAtlas2 backbone + radial blend + bounded gravity (v4.14)
    # ---------------------------------------------------------
    # Base radial layout (for interpretive orientation)
    radial = nx.circular_layout(G)
    
    # ---------------------------------------------------------
    # Deterministic node ordering
    # ---------------------------------------------------------
    G = nx.relabel_nodes(G, {n: n for n in sorted(G.nodes())})
    
    # ---------------------------------------------------------
    # Deterministic initial layout
    # ---------------------------------------------------------
    initial_pos = nx.spring_layout(G, seed=42)
    
    # ---------------------------------------------------------
    # Deterministic undirected graph for FA2
    # ---------------------------------------------------------
    G_und = nx.Graph()
    G_und.add_nodes_from(sorted(G.nodes()))
    G_und.add_edges_from(sorted(G.edges()))
    
    # ---------------------------------------------------------
    # Deterministic ForceAtlas2 configuration
    # ---------------------------------------------------------
    fa2 = ForceAtlas2(
        outboundAttractionDistribution=True,
        linLogMode=False,
        adjustSizes=False,
        edgeWeightInfluence=1.0,
        gravity=CONFIG_VIS.get("fa2_gravity", 2.0),
        scalingRatio=CONFIG_VIS.get("fa2_scaling_ratio", 1.8),
        strongGravityMode=False,
        verbose=False,
    )
    
    # Compute deterministic FA2 layout
    fa2_pos = fa2.forceatlas2_networkx_layout(
        G_und,
        pos=initial_pos,
        iterations=2000
    )

    # ---------------------------------------------------------
    # Contract FA2 layout before blending
    # ---------------------------------------------------------
    # Compute radius of FA2 layout
    fa2_radii = [(x**2 + y**2)**0.5 for x, y in fa2_pos.values()]
    fa2_max_r = max(fa2_radii) or 1.0
    
    # Target radius for FA2 before blending
    TARGET_R = 0.6
    
    fa2_contracted = {
        n: (x / fa2_max_r * TARGET_R, y / fa2_max_r * TARGET_R)
        for n, (x, y) in fa2_pos.items()
    }

    # Visualization parameters
    exp_g = CONFIG_VIS["gravity_exponent"]
    alpha  = CONFIG_VIS["gravity_alpha"]
    rw = CONFIG_VIS["radial_weight"]
    sw = CONFIG_VIS["spring_weight"] 
   
    blended = {}

    for n in G.nodes():
        # 1. Base positions
        x_rad, y_rad = radial[n]
        x_fa2, y_fa2 = fa2_contracted[n]
    
        # 2. Degree-aware blending (isolates get more radial)
        deg = G.degree(n)
        if deg <= 1:
            local_rw = rw * 1.5
            local_sw = sw * 0.35
        else:
            local_rw = rw
            local_sw = sw
    
        # 3. Blend radial + FA2
        x = x_rad * local_rw + x_fa2 * local_sw
        y = y_rad * local_rw + y_fa2 * local_sw
    
        # 4. Apply bounded gravity
        g = eig.get(n, 0)
        gravity = (g ** exp_g) * alpha
        x *= (1 - gravity)
        y *= (1 - gravity)
    
        blended[n] = (x, y)


    # ---------------------------------------------------------
    # 5. Center the layout
    # ---------------------------------------------------------
    xs = [p[0] for p in blended.values()]
    ys = [p[1] for p in blended.values()]
    x_center = (max(xs) + min(xs)) / 2
    y_center = (max(ys) + min(ys)) / 2

    centered = {n: (x - x_center, y - y_center) for n, (x, y) in blended.items()}

    # ---------------------------------------------------------
    # 5b. Clamp outlier nodes before normalization (v4.13)
    # ---------------------------------------------------------
    CLAMP_RADIUS = CONFIG_VIS["clamp_radius"]
    
    clamped = {}
    for n, (x, y) in centered.items():
        r = (x*x + y*y)**0.5
        if r > CLAMP_RADIUS:
            scale = CLAMP_RADIUS / r
            clamped[n] = (x * scale, y * scale)
        else:
            clamped[n] = (x, y)

    # ---------------------------------------------------------
    # 6. Normalize radius AFTER blending
    # ---------------------------------------------------------
    max_radius = max((x**2 + y**2)**0.5 for x, y in clamped.values()) or 1
    pos = {n: (x / max_radius, y / max_radius) for n, (x, y) in clamped.items()}

    # ---------------------------------------------------------
    # 7. Node sizes and colors
    # ---------------------------------------------------------
    max_strength = max(strength.values()) if strength else 1.0
    sizes = [260 * (strength[n] / max_strength)**0.5 for n in G.nodes()]
    node_colors = [cmap(comm_to_color[comm[n]] % 20) for n in G.nodes()]

    # Edge widths
    widths = [
        0.5 + 6.0 * (edge_bet.get((u, v), 0) / max_edge_bet)
        for u, v in G.edges()
    ]

    # ---------------------------------------------------------
    # 8. Remove self-loops + degenerate edges
    # ---------------------------------------------------------
    G_no_self = G.copy()
    G_no_self.remove_edges_from(nx.selfloop_edges(G_no_self))
    safe_edges = [(u, v) for u, v in G_no_self.edges() if pos[u] != pos[v]]

    # ---------------------------------------------------------
    # 9. Figure
    # ---------------------------------------------------------
    fig, (ax_net, ax_leg) = plt.subplots(
        1, 2,
        figsize=(14, 8),
        gridspec_kw={"width_ratios": [3, 1]}
    )

    ax_net.set_aspect("equal")

    # Network edges
    nx.draw_networkx_edges(
        G_no_self, pos, ax=ax_net,
        edgelist=safe_edges,
        alpha=0.25, width=widths,
        edge_color="grey",
        connectionstyle="arc3,rad=0.2"
    )

    # Nodes
    nx.draw_networkx_nodes(
        G, pos, ax=ax_net,
        node_size=sizes,
        node_color=node_colors,
        alpha=0.9,
    )

    # Light inline labels
    for n, (x, y) in pos.items():
        ax_net.text(x, y, n, fontsize=7, ha="center", va="center")

    ax_net.set_title(f"Centrality‑Gravity LNG Trade Network — {period}")
    ax_net.axis("off")

    # ---------------------------------------------------------
    # 10. Legend panel
    # ---------------------------------------------------------
    ax_leg.axis("off")
    ax_leg.set_title("Node Legend", fontsize=12)

    nodes_sorted = sorted(G.nodes())
    num_nodes = len(nodes_sorted)

    num_cols = 2 if num_nodes <= 40 else 3
    col_height = int(np.ceil(num_nodes / num_cols))

    for col in range(num_cols):
        start = col * col_height
        end = min(start + col_height, num_nodes)
        subset = nodes_sorted[start:end]

        y = 0.98
        for n in subset:
            c = comm[n]
            color = cmap(comm_to_color[c] % 20)

            ax_leg.add_patch(plt.Rectangle(
                (0.05 + col * 0.30, y - 0.015),
                0.02, 0.02,
                color=color,
                transform=ax_leg.transAxes,
                clip_on=False
            ))

            ax_leg.text(
                0.08 + col * 0.30, y,
                f"{n}  (Comm {c})",
                ha="left", va="top",
                fontsize=8,
                family="monospace",
            )
            y -= 0.035

    plt.tight_layout()
    plt.savefig(outpath, dpi=300)
    plt.close()


def plot_flow_matrix(G, period, outpath):
    if G.number_of_nodes() == 0:
        return

    nodes = sorted(G.nodes())
    A = nx.to_pandas_adjacency(G, nodelist=nodes, weight="weight")

    fig, ax = plt.subplots(figsize=(10, 8))
    sns.heatmap(A, cmap="Blues", ax=ax)

    ax.set_title(f"Flow Matrix — {period}")
    ax.set_xticklabels(ax.get_xticklabels(), rotation=90)
    ax.set_yticklabels(ax.get_yticklabels(), rotation=0)

    savefig_clean(fig, outpath)


def plot_chord(edges_df, period, outpath, top_n=40):
    if edges_df is None or edges_df.empty:
        return

    df = edges_df.sort_values("flow", ascending=False).head(top_n)
    actors = sorted(set(df["exporter"]).union(df["importer"]))
    n = len(actors)
    if n == 0:
        return

    angle = {a: i * 2 * np.pi / n for i, a in enumerate(actors)}

    fig, ax = plt.subplots(figsize=(8, 8))
    ax.set_aspect("equal")
    ax.axis("off")

    # Nodes
    for a in actors:
        x = np.cos(angle[a])
        y = np.sin(angle[a])
        ax.scatter(x, y, s=50, color="black")
        ax.text(x * 1.1, y * 1.1, a, ha="center", va="center", fontsize=8)

    # Edges
    max_flow = df["flow"].max()
    for _, row in df.iterrows():
        u, v, w = row["exporter"], row["importer"], row["flow"]
        x1, y1 = np.cos(angle[u]), np.sin(angle[u])
        x2, y2 = np.cos(angle[v]), np.sin(angle[v])
        lw = 0.5 + 4.5 * (w / max_flow) if max_flow > 0 else 1.0
        ax.plot([x1, x2], [y1, y2], color="steelblue", alpha=0.6, linewidth=lw)

    ax.set_title(f"Chord Diagram — {period}")

    savefig_clean(fig, outpath)


def plot_top_edges_bar(edges_df, period, outpath, top_n=40):
    if edges_df is None or edges_df.empty:
        return

    sub = edges_df.sort_values("flow", ascending=False).head(top_n).copy()
    sub["pair"] = sub["exporter"] + " → " + sub["importer"]

    fig, ax = plt.subplots(figsize=(10, 6))
    sns.barplot(data=sub, x="flow", y="pair", color="steelblue", ax=ax)

    ax.set_title(f"Top Bilateral Flows — {period}")
    ax.set_xlabel("Flow")
    ax.set_ylabel("Exporter → Importer")

    savefig_clean(fig, outpath)

# ============================================================
# Timeseries Visualization Helpers
# ============================================================

# ------------------------------------------------------------
# Consistent color palette
# ------------------------------------------------------------
PALETTE = {
    "structural_primary": "tab:red",
    "structural_secondary": "tab:blue",

    "community_primary": "tab:purple",
    "community_secondary": "tab:green",

    "concentration_primary": "tab:orange",
    "concentration_secondary": "tab:brown",

    "intensity_primary": "tab:cyan",
    "intensity_secondary": "tab:pink",

    "csci": "tab:red",
    "stability": "tab:blue",
}

# ------------------------------------------------------------
# Global line/marker style mapping
# ------------------------------------------------------------
STYLE = {
    "max_edge_change":      {"linestyle": "-",  "marker": "o", "color": PALETTE["structural_primary"]},
    "mean_edge_change":     {"linestyle": "--", "marker": "s", "color": PALETTE["structural_secondary"]},

    "community_count":      {"linestyle": "-",  "marker": "^", "color": PALETTE["community_primary"]},
    "modularity":           {"linestyle": "--", "marker": "D", "color": PALETTE["community_secondary"]},

    "largest_share":        {"linestyle": "-.", "marker": "o", "color": PALETTE["concentration_primary"]},
    "top3_share":           {"linestyle": ":",  "marker": "s", "color": PALETTE["concentration_secondary"]},

    "mean_strength_norm":   {"linestyle": "-",  "marker": "x", "color": PALETTE["intensity_primary"]},
    "active_edges_norm":    {"linestyle": "--", "marker": "o", "color": PALETTE["intensity_secondary"]},

    "csci":                 {"linestyle": "-",  "marker": "o", "color": PALETTE["csci"]},
    "stability_index":      {"linestyle": "--", "marker": "s", "color": PALETTE["stability"]},
}

# ------------------------------------------------------------
# Single-axis styled plot
# ------------------------------------------------------------
def styled_plot(ax, x, y, key, label):
    style = STYLE[key]
    ax.plot(
        x, y,
        linestyle=style["linestyle"],
        marker=style["marker"],
        color=style["color"],
        linewidth=2,
        label=label,
    )

# ------------------------------------------------------------
# Dual-axis styled plot
# ------------------------------------------------------------
def styled_dual_plot(ax1, ax2, x, y1, y2, key1, key2, label1, label2):
    styled_plot(ax1, x, y1, key1, label1)
    styled_plot(ax2, x, y2, key2, label2)

    ax1.legend(loc="upper left")
    ax2.legend(loc="upper right")

# ------------------------------------------------------------
# Axis formatting helpers
# ------------------------------------------------------------
def format_year_axis(ax):
    ax.xaxis.set_major_formatter(matplotlib.dates.DateFormatter("%Y"))
    ax.xaxis.set_major_locator(matplotlib.dates.YearLocator())
    for label in ax.get_xticklabels():
        label.set_rotation(45)
        label.set_ha("right")

def format_month_axis(ax):
    ax.xaxis.set_major_formatter(matplotlib.dates.DateFormatter("%Y-%m"))
    ax.xaxis.set_major_locator(matplotlib.dates.MonthLocator(interval=6))
    for label in ax.get_xticklabels():
        label.set_rotation(45)
        label.set_ha("right")

# ------------------------------------------------------------
# Clean save helper
# ------------------------------------------------------------
def savefig_clean(fig, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fig.tight_layout()
    fig.savefig(path, dpi=300)
    plt.close(fig)