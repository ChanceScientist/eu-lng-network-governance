"""
stage07_timeseries.py — v3.0 (2026-04-03)
Purpose:
Generate time‑series visualizations for structural‑delta, community‑structure,
concentration, network‑intensity, and CSCI metrics using consistent styling
and governance‑aligned period ordering.

Inputs:
- Governance core:
    governance/governance_report_core.csv
- Community‑level metrics:
    governance/communities_all_periods.csv
- Node‑level metrics:
    governance/nodes_centrality_all_periods.csv
- Utility modules:
    sort_periods_yearly_first(), split_periods(), normalize(),
    STYLE, styled_plot(), styled_dual_plot(),
    format_year_axis(), format_month_axis(), savefig_clean()

Responsibilities:
- Load governance core and split into yearly + monthly subsets
- Load community and node‑level datasets
- Precompute aggregates for:
    - community count (monthly + yearly)
    - modularity (monthly + yearly)
    - largest community share
    - top‑3 flow share
    - mean strength (normalized)
    - active edges (normalized)
    - CSCI (monthly + yearly)
- Generate time‑series charts for:
    • Structural‑delta metrics (yearly)
    • Community structure metrics (monthly + yearly)
    • Concentration metrics (monthly + yearly)
    • Network intensity metrics (monthly + yearly)
    • Transitional metrics (rolling deltas)
    • CSCI (monthly + yearly)
    • CSCI combined with modularity, concentration, intensity, stability
- Save all figures to TS_DIR with consistent styling

Outputs:
- Time‑series visualizations (PNG), including:
    ts/edge_change_dual_axis.png
    ts/edge_change_normalized.png
    ts/community_count_monthly.png
    ts/community_count_yearly.png
    ts/modularity_monthly.png
    ts/modularity_yearly.png
    ts/community_modularity_monthly.png
    ts/community_modularity_yearly.png
    ts/largest_community_share_monthly.png
    ts/largest_community_share_yearly.png
    ts/top3_flow_share_monthly.png
    ts/top3_flow_share_yearly.png
    ts/mean_strength_norm_monthly.png
    ts/mean_strength_norm_yearly.png
    ts/active_edges_norm_monthly.png
    ts/active_edges_norm_yearly.png
    ts/delta_comm_modularity_roll3.png
    ts/csci_monthly.png
    ts/csci_yearly.png
    ts/csci_modularity_monthly.png
    ts/csci_modularity_yearly.png
    ts/csci_largestshare_monthly.png
    ts/csci_largestshare_yearly.png
    ts/csci_meanstrength_monthly.png
    ts/csci_meanstrength_yearly.png
    ts/csci_stability_monthly.png
    ts/csci_stability_yearly.png

Notes:
- This script produces visual outputs only; no CSVs are written.
- All charts use the global STYLE dictionary for consistent color and typography.
- Period ordering is governance‑aligned (yearly first, then monthly).
- AI Assistance:
    This script was drafted with support from Microsoft Copilot. All conceptual
    framing, methodological design, and analytical and interpretive decisions
    were made by the author. The author reviewed, edited, and validated all code.
"""


import os
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from tqdm import tqdm

# Shared helpers
from stage07_helpers import (
    GOV_DIR,
    TS_DIR,
    sort_periods_yearly_first,
    normalize,
    split_periods,
    STYLE,
    styled_plot,
    styled_dual_plot,
    format_year_axis,
    format_month_axis,
    savefig_clean,
)

# ============================================================
# Load and preprocess data
# ============================================================

def load_data():
    """Load governance core and split into yearly + monthly subsets."""
    gov_path = os.path.join(GOV_DIR, "governance_report_core.csv")
    gov = pd.read_csv(gov_path)
    gov = sort_periods_yearly_first(gov)
    gov_yearly, gov_monthly = split_periods(gov)
    return gov, gov_yearly, gov_monthly


def load_community_data():
    """Load community-level datasets."""
    comm_df = pd.read_csv(os.path.join(GOV_DIR, "communities_all_periods.csv"))
    nodes_df = pd.read_csv(os.path.join(GOV_DIR, "nodes_centrality_all_periods.csv"))
    return comm_df, nodes_df


# ============================================================
# Precompute aggregates used across charts
# ============================================================

def compute_aggregates(gov_yearly, gov_monthly, comm_df, nodes_df):
    """Compute all monthly + yearly aggregates needed for charts."""

    # ------------------------------
    # Community Count (Monthly)
    # ------------------------------
    comm_count = (
        comm_df.groupby("period")["community"]
        .nunique()
        .reset_index(name="community_count")
    )
    comm_count = comm_count[comm_count["period"].str.len() == 7].copy()
    comm_count["period_dt"] = pd.to_datetime(comm_count["period"], format="%Y-%m")
    comm_count = comm_count.sort_values("period_dt")

    # ------------------------------
    # Community Count (Yearly)
    # ------------------------------
    comm_yearly = (
        comm_count.assign(year=lambda df: df["period_dt"].dt.year)
        .groupby("year")["community_count"]
        .mean()
        .reset_index(name="community_count_yearly")
    )

    # ------------------------------
    # Modularity (Yearly)
    # ------------------------------
    mod_yearly = (
        gov_monthly.assign(year=lambda df: df["period_dt"].dt.year)
        .groupby("year")["modularity"]
        .mean()
        .reset_index(name="modularity_yearly")
    )

    # ------------------------------
    # Largest Community Share
    # ------------------------------
    comm_summary = comm_df[comm_df["period"].str.len() == 7].copy()

    largest_share_monthly = (
        comm_summary.groupby("period")["flow_share"]
        .max()
        .reset_index(name="largest_share")
    )
    largest_share_monthly["period_dt"] = pd.to_datetime(
        largest_share_monthly["period"], format="%Y-%m"
    )

    largest_share_yearly = (
        largest_share_monthly.assign(year=lambda df: df["period_dt"].dt.year)
        .groupby("year")["largest_share"]
        .mean()
        .reset_index(name="largest_share_yearly")
    )

    # ------------------------------
    # Mean Strength (Normalized)
    # ------------------------------
    nodes_monthly = nodes_df[nodes_df["period"].str.len() == 7].copy()

    mean_strength_monthly = (
        nodes_monthly.groupby("period")["strength"]
        .mean()
        .reset_index(name="mean_strength")
    )
    mean_strength_monthly["mean_strength_norm"] = normalize(
        mean_strength_monthly["mean_strength"]
    )
    mean_strength_monthly["period_dt"] = pd.to_datetime(
        mean_strength_monthly["period"], format="%Y-%m"
    )

    mean_strength_yearly = (
        mean_strength_monthly.assign(year=lambda df: df["period_dt"].dt.year)
        .groupby("year")["mean_strength_norm"]
        .mean()
        .reset_index(name="mean_strength_norm_yearly")
    )

    # ------------------------------
    # Top 3 Flow Share
    # ------------------------------
    top3_monthly = (
        comm_summary.groupby("period")["flow_share"]
        .apply(lambda s: s.nlargest(3).sum())
        .reset_index(name="top3_share")
    )
    top3_monthly["period_dt"] = pd.to_datetime(
        top3_monthly["period"], format="%Y-%m"
    )

    top3_yearly = (
        top3_monthly.assign(year=lambda df: df["period_dt"].dt.year)
        .groupby("year")["top3_share"]
        .mean()
        .reset_index(name="top3_share_yearly")
    )

    # ------------------------------
    # Active Edges (Normalized)
    # ------------------------------
    active_edges_monthly = gov_monthly[["period_dt", "edges"]].copy()
    active_edges_monthly["edges_norm"] = normalize(active_edges_monthly["edges"])

    active_edges_yearly = (
        active_edges_monthly.assign(year=lambda df: df["period_dt"].dt.year)
        .groupby("year")["edges_norm"]
        .mean()
        .reset_index(name="active_edges_norm_yearly")
    )

    # ------------------------------
    # CSCI (Monthly + Yearly)
    # ------------------------------
    csci_monthly = gov_monthly[
        ["period_dt", "composite_structural_change_index"]
    ].copy()

    csci_yearly = (
        gov_yearly.assign(year=lambda df: df["period_dt"].dt.year)
        .groupby("year")["composite_structural_change_index"]
        .mean()
        .reset_index(name="csci_yearly")
    )

    return {
        "comm_count": comm_count,
        "comm_yearly": comm_yearly,
        "mod_yearly": mod_yearly,
        "largest_share_monthly": largest_share_monthly,
        "largest_share_yearly": largest_share_yearly,
        "mean_strength_monthly": mean_strength_monthly,
        "mean_strength_yearly": mean_strength_yearly,
        "top3_monthly": top3_monthly,
        "top3_yearly": top3_yearly,
        "active_edges_monthly": active_edges_monthly,
        "active_edges_yearly": active_edges_yearly,
        "csci_monthly": csci_monthly,
        "csci_yearly": csci_yearly,
    }


# ============================================================
# Structural Delta Charts
# ============================================================

def plot_structural_delta_dual(gov_yearly):
    """Max vs Mean Edge Change (Yearly, Dual-Axis)."""
    fig, ax1 = plt.subplots(figsize=(10, 6))

    styled_plot(
        ax1,
        gov_yearly["period_dt"],
        gov_yearly["max_edge_change"],
        "max_edge_change",
        "Max Edge Change"
    )
    ax1.set_ylabel("Max Edge Change", color=STYLE["max_edge_change"]["color"])

    ax2 = ax1.twinx()
    styled_plot(
        ax2,
        gov_yearly["period_dt"],
        gov_yearly["mean_edge_change"],
        "mean_edge_change",
        "Mean Edge Change"
    )
    ax2.set_ylabel("Mean Edge Change", color=STYLE["mean_edge_change"]["color"])

    format_year_axis(ax1)
    ax1.legend(loc="upper left")
    ax2.legend(loc="upper right")

    plt.title("Max vs Mean Edge Change (Yearly, Dual-Axis)")
    savefig_clean(fig, os.path.join(TS_DIR, "edge_change_dual_axis.png"))


def plot_structural_delta_normalized(gov_yearly):
    """Max vs Mean Edge Change (Yearly, Normalized)."""
    fig, ax = plt.subplots(figsize=(10, 6))

    styled_plot(
        ax,
        gov_yearly["period_dt"],
        normalize(gov_yearly["max_edge_change"]),
        "max_edge_change",
        "Max Edge Change (normalized)"
    )

    styled_plot(
        ax,
        gov_yearly["period_dt"],
        normalize(gov_yearly["mean_edge_change"]),
        "mean_edge_change",
        "Mean Edge Change (normalized)"
    )

    format_year_axis(ax)
    plt.title("Max vs Mean Edge Change (Yearly, Normalized)")
    plt.legend(loc="upper left")
    savefig_clean(fig, os.path.join(TS_DIR, "edge_change_normalized.png"))


def plot_delta_comm_mod_yearly(comm_yearly, mod_yearly):
    """Δ Community Count vs Δ Modularity (Yearly)."""
    comm_yearly = comm_yearly.copy()
    mod_yearly = mod_yearly.copy()

    comm_yearly["delta_comm_yearly"] = comm_yearly["community_count_yearly"].diff()
    mod_yearly["delta_mod_yearly"] = mod_yearly["modularity_yearly"].diff()

    fig, ax1 = plt.subplots(figsize=(10, 6))

    styled_plot(
        ax1,
        comm_yearly["year"],
        comm_yearly["delta_comm_yearly"],
        "community_count",
        "Δ Community Count (Yearly)"
    )
    ax1.set_ylabel("Δ Community Count (Yearly)", color=STYLE["community_count"]["color"])

    ax2 = ax1.twinx()
    styled_plot(
        ax2,
        mod_yearly["year"],
        mod_yearly["delta_mod_yearly"],
        "modularity",
        "Δ Modularity (Yearly)"
    )
    ax2.set_ylabel("Δ Modularity (Yearly)", color=STYLE["modularity"]["color"])

    ax1.set_xticks(comm_yearly["year"])
    ax1.set_xticklabels(comm_yearly["year"], rotation=45, ha="right")

    ax1.legend(loc="upper left")
    ax2.legend(loc="upper right")

    plt.title("Δ Community Count vs Δ Modularity (Yearly)")
    savefig_clean(fig, os.path.join(TS_DIR, "delta_comm_modularity_yearly.png"))


def plot_comm_volatility_yearly(comm_count):
    """Volatility of Community Count (Yearly)."""
    comm_vol_yearly = (
        comm_count.assign(year=lambda df: df["period_dt"].dt.year)
        .groupby("year")["community_count"]
        .std()
        .reset_index(name="community_count_volatility")
    )

    fig, ax = plt.subplots(figsize=(10, 6))

    styled_plot(
        ax,
        comm_vol_yearly["year"],
        comm_vol_yearly["community_count_volatility"],
        "community_count",
        "Community Count Volatility (Yearly)"
    )

    ax.set_ylabel("Community Count Volatility (Yearly)", color=STYLE["community_count"]["color"])
    ax.set_xticks(comm_vol_yearly["year"])
    ax.set_xticklabels(comm_vol_yearly["year"], rotation=45, ha="right")

    plt.title("Volatility of Community Count (Yearly)")
    savefig_clean(fig, os.path.join(TS_DIR, "community_count_volatility_yearly.png"))


def plot_modularity_volatility_yearly(gov_monthly):
    """Volatility of Modularity (Yearly)."""
    mod_vol_yearly = (
        gov_monthly.assign(year=lambda df: df["period_dt"].dt.year)
        .groupby("year")["modularity"]
        .std()
        .reset_index(name="modularity_volatility")
    )

    fig, ax = plt.subplots(figsize=(10, 6))

    styled_plot(
        ax,
        mod_vol_yearly["year"],
        mod_vol_yearly["modularity_volatility"],
        "modularity",
        "Modularity Volatility (Yearly)"
    )

    ax.set_ylabel("Modularity Volatility (Yearly)", color=STYLE["modularity"]["color"])
    ax.set_xticks(mod_vol_yearly["year"])
    ax.set_xticklabels(mod_vol_yearly["year"], rotation=45, ha="right")

    plt.title("Volatility of Modularity (Yearly)")
    savefig_clean(fig, os.path.join(TS_DIR, "modularity_volatility_yearly.png"))


# ============================================================
# Community Structure Charts
# ============================================================

def plot_community_count_monthly(comm_count):
    """Community Count (Monthly)."""
    fig, ax = plt.subplots(figsize=(10, 6))

    styled_plot(
        ax,
        comm_count["period_dt"],
        comm_count["community_count"],
        "community_count",
        "Community Count"
    )

    format_month_axis(ax)
    plt.title("Community Count Over Time (Monthly)")
    savefig_clean(fig, os.path.join(TS_DIR, "community_count_monthly.png"))


def plot_community_count_yearly(comm_yearly):
    """Community Count (Yearly)."""
    fig, ax = plt.subplots(figsize=(10, 6))

    styled_plot(
        ax,
        comm_yearly["year"],
        comm_yearly["community_count_yearly"],
        "community_count",
        "Community Count (Yearly)"
    )

    ax.set_ylabel("Community Count (Yearly)", color=STYLE["community_count"]["color"])
    ax.set_xticks(comm_yearly["year"])
    ax.set_xticklabels(comm_yearly["year"], rotation=45, ha="right")

    plt.title("Community Count Over Time (Yearly)")
    savefig_clean(fig, os.path.join(TS_DIR, "community_count_yearly.png"))


def plot_modularity_monthly(gov_monthly):
    """Modularity (Monthly)."""
    fig, ax = plt.subplots(figsize=(10, 6))

    styled_plot(
        ax,
        gov_monthly["period_dt"],
        gov_monthly["modularity"],
        "modularity",
        "Modularity"
    )

    format_month_axis(ax)
    plt.title("Modularity Over Time (Monthly)")
    savefig_clean(fig, os.path.join(TS_DIR, "modularity_monthly.png"))


def plot_modularity_yearly(mod_yearly):
    """Modularity (Yearly)."""
    fig, ax = plt.subplots(figsize=(10, 6))

    styled_plot(
        ax,
        mod_yearly["year"],
        mod_yearly["modularity_yearly"],
        "modularity",
        "Modularity (Yearly)"
    )

    ax.set_ylabel("Modularity (Yearly)", color=STYLE["modularity"]["color"])
    ax.set_xticks(mod_yearly["year"])
    ax.set_xticklabels(mod_yearly["year"], rotation=45, ha="right")

    plt.title("Modularity Over Time (Yearly)")
    savefig_clean(fig, os.path.join(TS_DIR, "modularity_yearly.png"))


def plot_comm_modularity_monthly(comm_count, gov_monthly):
    """Community Count + Modularity (Monthly, Dual-Axis)."""
    fig, ax1 = plt.subplots(figsize=(10, 6))

    styled_plot(
        ax1,
        comm_count["period_dt"],
        comm_count["community_count"],
        "community_count",
        "Community Count"
    )
    ax1.set_ylabel("Community Count", color=STYLE["community_count"]["color"])

    ax2 = ax1.twinx()
    styled_plot(
        ax2,
        gov_monthly["period_dt"],
        gov_monthly["modularity"],
        "modularity",
        "Modularity"
    )
    ax2.set_ylabel("Modularity", color=STYLE["modularity"]["color"])

    format_month_axis(ax1)
    ax1.legend(loc="upper left")
    ax2.legend(loc="upper right")

    plt.title("Community Count + Modularity (Dual-Axis, Monthly)")
    savefig_clean(fig, os.path.join(TS_DIR, "community_modularity_monthly.png"))


def plot_comm_modularity_yearly(comm_yearly, mod_yearly):
    """Community Count + Modularity (Yearly, Dual-Axis)."""
    fig, ax1 = plt.subplots(figsize=(10, 6))

    styled_plot(
        ax1,
        comm_yearly["year"],
        comm_yearly["community_count_yearly"],
        "community_count",
        "Community Count (Yearly)"
    )
    ax1.set_ylabel("Community Count (Yearly)", color=STYLE["community_count"]["color"])

    ax2 = ax1.twinx()
    styled_plot(
        ax2,
        mod_yearly["year"],
        mod_yearly["modularity_yearly"],
        "modularity",
        "Modularity (Yearly)"
    )
    ax2.set_ylabel("Modularity (Yearly)", color=STYLE["modularity"]["color"])

    ax1.set_xticks(comm_yearly["year"])
    ax1.set_xticklabels(comm_yearly["year"], rotation=45, ha="right")

    ax1.legend(loc="upper left")
    ax2.legend(loc="upper right")

    plt.title("Community Count + Modularity (Dual-Axis, Yearly)")
    savefig_clean(fig, os.path.join(TS_DIR, "community_modularity_yearly.png"))


# ============================================================
# Concentration Metrics
# ============================================================

def plot_largest_share_monthly(largest_share_monthly):
    """Largest Community Share (Monthly)."""
    fig, ax = plt.subplots(figsize=(10, 6))

    styled_plot(
        ax,
        largest_share_monthly["period_dt"],
        largest_share_monthly["largest_share"],
        "largest_share",
        "Largest Community Share"
    )

    format_month_axis(ax)
    plt.title("Largest Community Share (Monthly)")
    savefig_clean(fig, os.path.join(TS_DIR, "largest_community_share_monthly.png"))


def plot_largest_share_yearly(largest_share_yearly):
    """Largest Community Share (Yearly)."""
    fig, ax = plt.subplots(figsize=(10, 6))

    styled_plot(
        ax,
        largest_share_yearly["year"],
        largest_share_yearly["largest_share_yearly"],
        "largest_share",
        "Largest Community Share (Yearly)"
    )

    ax.set_ylabel("Largest Community Share (Yearly)", color=STYLE["largest_share"]["color"])
    ax.set_xticks(largest_share_yearly["year"])
    ax.set_xticklabels(largest_share_yearly["year"], rotation=45, ha="right")

    plt.title("Largest Community Share (Yearly)")
    savefig_clean(fig, os.path.join(TS_DIR, "largest_community_share_yearly.png"))


def plot_modularity_largestshare_yearly(mod_yearly, largest_share_yearly):
    """Modularity + Largest Community Share (Yearly, Dual-Axis)."""
    fig, ax1 = plt.subplots(figsize=(10, 6))

    # Modularity (Yearly)
    styled_plot(
        ax1,
        mod_yearly["year"],
        mod_yearly["modularity_yearly"],
        "modularity",
        "Modularity (Yearly)"
    )
    ax1.set_ylabel("Modularity (Yearly)", color=STYLE["modularity"]["color"])

    # Largest Community Share (Yearly)
    ax2 = ax1.twinx()
    styled_plot(
        ax2,
        largest_share_yearly["year"],
        largest_share_yearly["largest_share_yearly"],
        "largest_share",
        "Largest Community Share (Yearly)"
    )
    ax2.set_ylabel("Largest Community Share (Yearly)", color=STYLE["largest_share"]["color"])

    # Formatting
    ax1.set_xticks(mod_yearly["year"])
    ax1.set_xticklabels(mod_yearly["year"], rotation=45, ha="right")

    ax1.legend(loc="upper left")
    ax2.legend(loc="upper right")

    plt.title("Modularity + Largest Community Share (Dual-Axis, Yearly)")
    savefig_clean(fig, os.path.join(TS_DIR, "modularity_largestshare_yearly.png"))
def plot_top3_share_monthly(top3_monthly):
    """Top 3 Flow Share (Monthly)."""
    fig, ax = plt.subplots(figsize=(10, 6))

    styled_plot(
        ax,
        top3_monthly["period_dt"],
        top3_monthly["top3_share"],
        "top3_share",
        "Top 3 Flow Share"
    )

    format_month_axis(ax)
    plt.title("Top 3 Flow Share (Monthly)")
    savefig_clean(fig, os.path.join(TS_DIR, "top3_flow_share_monthly.png"))


def plot_top3_share_yearly(top3_yearly):
    """Top 3 Flow Share (Yearly)."""
    fig, ax = plt.subplots(figsize=(10, 6))

    styled_plot(
        ax,
        top3_yearly["year"],
        top3_yearly["top3_share_yearly"],
        "top3_share",
        "Top 3 Flow Share (Yearly)"
    )

    ax.set_ylabel("Top 3 Flow Share (Yearly)", color=STYLE["top3_share"]["color"])
    ax.set_xticks(top3_yearly["year"])
    ax.set_xticklabels(top3_yearly["year"], rotation=45, ha="right")

    plt.title("Top 3 Flow Share (Yearly)")
    savefig_clean(fig, os.path.join(TS_DIR, "top3_flow_share_yearly.png"))


# ============================================================
# Network Intensity Metrics
# ============================================================

def plot_mean_strength_monthly(mean_strength_monthly):
    """Mean Strength (Normalized, Monthly)."""
    fig, ax = plt.subplots(figsize=(10, 6))

    styled_plot(
        ax,
        mean_strength_monthly["period_dt"],
        mean_strength_monthly["mean_strength_norm"],
        "mean_strength_norm",
        "Mean Strength (normalized)"
    )

    format_month_axis(ax)
    plt.title("Mean Strength (Normalized, Monthly)")
    savefig_clean(fig, os.path.join(TS_DIR, "mean_strength_norm_monthly.png"))


def plot_mean_strength_yearly(mean_strength_yearly):
    """Mean Strength (Normalized, Yearly)."""
    fig, ax = plt.subplots(figsize=(10, 6))

    styled_plot(
        ax,
        mean_strength_yearly["year"],
        mean_strength_yearly["mean_strength_norm_yearly"],
        "mean_strength_norm",
        "Mean Strength (Normalized, Yearly)"
    )

    ax.set_ylabel("Mean Strength (Normalized, Yearly)", color=STYLE["mean_strength_norm"]["color"])
    ax.set_xticks(mean_strength_yearly["year"])
    ax.set_xticklabels(mean_strength_yearly["year"], rotation=45, ha="right")

    plt.title("Mean Strength (Normalized, Yearly)")
    savefig_clean(fig, os.path.join(TS_DIR, "mean_strength_norm_yearly.png"))


def plot_active_edges_monthly(active_edges_monthly):
    """Active Edges (Normalized, Monthly)."""
    fig, ax = plt.subplots(figsize=(10, 6))

    styled_plot(
        ax,
        active_edges_monthly["period_dt"],
        active_edges_monthly["edges_norm"],
        "active_edges_norm",
        "Active Edges (normalized)"
    )

    format_month_axis(ax)
    plt.title("Active Edges (Normalized, Monthly)")
    savefig_clean(fig, os.path.join(TS_DIR, "active_edges_norm_monthly.png"))


def plot_active_edges_yearly(active_edges_yearly):
    """Active Edges (Normalized, Yearly)."""
    fig, ax = plt.subplots(figsize=(10, 6))

    styled_plot(
        ax,
        active_edges_yearly["year"],
        active_edges_yearly["active_edges_norm_yearly"],
        "active_edges_norm",
        "Active Edges (Normalized, Yearly)"
    )

    ax.set_ylabel("Active Edges (Normalized, Yearly)", color=STYLE["active_edges_norm"]["color"])
    ax.set_xticks(active_edges_yearly["year"])
    ax.set_xticklabels(active_edges_yearly["year"], rotation=45, ha="right")

    plt.title("Active Edges (Normalized, Yearly)")
    savefig_clean(fig, os.path.join(TS_DIR, "active_edges_norm_yearly.png"))


# ============================================================
# Transitional Metrics
# ============================================================

def plot_delta_comm_mod_roll3(comm_count, gov_monthly):
    """Δ Community Count vs Δ Modularity (3-Month Rolling)."""
    comm = comm_count.copy()
    comm["delta_comm"] = comm["community_count"].diff()
    comm["delta_comm_roll3"] = comm["delta_comm"].rolling(window=3).mean()

    mod = gov_monthly[["period_dt", "modularity"]].copy()
    mod = mod.sort_values("period_dt")
    mod["delta_mod"] = mod["modularity"].diff()
    mod["delta_mod_roll3"] = mod["delta_mod"].rolling(window=3).mean()

    fig, ax1 = plt.subplots(figsize=(10, 6))

    styled_plot(
        ax1,
        comm["period_dt"],
        comm["delta_comm_roll3"],
        "community_count",
        "Δ Community Count (3-month rolling)"
    )
    ax1.set_ylabel("Δ Community Count (3-month rolling)", color=STYLE["community_count"]["color"])

    ax2 = ax1.twinx()
    styled_plot(
        ax2,
        mod["period_dt"],
        mod["delta_mod_roll3"],
        "modularity",
        "Δ Modularity (3-month rolling)"
    )
    ax2.set_ylabel("Δ Modularity (3-month rolling)", color=STYLE["modularity"]["color"])

    format_month_axis(ax1)
    ax1.legend(loc="upper left")
    ax2.legend(loc="upper right")

    plt.title("Δ Community Count vs Δ Modularity (3-Month Rolling)")
    savefig_clean(fig, os.path.join(TS_DIR, "delta_comm_modularity_roll3.png"))


# ============================================================
# Composite Structural Change Index (CSCI)
# ============================================================

def plot_csci_monthly(csci_monthly):
    """CSCI (Monthly)."""
    fig, ax = plt.subplots(figsize=(10, 6))

    styled_plot(
        ax,
        csci_monthly["period_dt"],
        csci_monthly["composite_structural_change_index"],
        "csci",
        "CSCI (Monthly)"
    )

    format_month_axis(ax)
    plt.title("Composite Structural Change Index (Monthly)")
    savefig_clean(fig, os.path.join(TS_DIR, "csci_monthly.png"))


def plot_csci_yearly(csci_yearly):
    """CSCI (Yearly)."""
    fig, ax = plt.subplots(figsize=(10, 6))

    styled_plot(
        ax,
        csci_yearly["year"],
        csci_yearly["csci_yearly"],
        "csci",
        "CSCI (Yearly)"
    )

    ax.set_ylabel("CSCI (Yearly)", color=STYLE["csci"]["color"])
    ax.set_xticks(csci_yearly["year"])
    ax.set_xticklabels(csci_yearly["year"], rotation=45, ha="right")

    plt.title("Composite Structural Change Index (Yearly)")
    savefig_clean(fig, os.path.join(TS_DIR, "csci_yearly.png"))


def plot_csci_modularity_monthly(csci_monthly, gov_monthly):
    fig, ax = plt.subplots(figsize=(10, 6))

    styled_plot(
        ax,
        csci_monthly["period_dt"],
        csci_monthly["composite_structural_change_index"],
        "csci",
        "CSCI (Monthly)"
    )

    styled_plot(
        ax,
        gov_monthly["period_dt"],
        gov_monthly["modularity"],
        "modularity",
        "Modularity (Monthly)"
    )

    format_month_axis(ax)
    ax.legend()
    ax.set_title("CSCI + Modularity (Monthly)")

    savefig_clean(fig, os.path.join(TS_DIR, "csci_modularity_monthly.png"))


def plot_csci_modularity_yearly(csci_yearly, mod_yearly):
    fig, ax = plt.subplots(figsize=(10, 6))

    styled_plot(
        ax,
        csci_yearly["year"],
        csci_yearly["csci_yearly"],
        "csci",
        "CSCI (Yearly)"
    )

    styled_plot(
        ax,
        mod_yearly["year"],
        mod_yearly["modularity_yearly"],
        "modularity",
        "Modularity (Yearly)"
    )

    ax.set_xticks(csci_yearly["year"])
    ax.set_xticklabels(csci_yearly["year"], rotation=45, ha="right")
    ax.legend()
    ax.set_title("CSCI + Modularity (Yearly)")

    savefig_clean(fig, os.path.join(TS_DIR, "csci_modularity_yearly.png"))


# ============================================================
# CSCI + Concentration / Intensity / Stability
# ============================================================

def plot_csci_largest_share_monthly(csci_monthly, largest_share_monthly):
    fig, ax = plt.subplots(figsize=(10, 6))

    styled_plot(
        ax,
        csci_monthly["period_dt"],
        csci_monthly["composite_structural_change_index"],
        "csci",
        "CSCI (Monthly)"
    )

    styled_plot(
        ax,
        largest_share_monthly["period_dt"],
        largest_share_monthly["largest_share"],
        "largest_share",
        "Largest Community Share (Monthly)"
    )

    format_month_axis(ax)
    ax.legend()
    ax.set_title("CSCI + Largest Community Share (Monthly)")

    savefig_clean(fig, os.path.join(TS_DIR, "csci_largestshare_monthly.png"))


def plot_csci_largest_share_yearly(csci_yearly, largest_share_yearly):
    fig, ax = plt.subplots(figsize=(10, 6))

    styled_plot(
        ax,
        csci_yearly["year"],
        csci_yearly["csci_yearly"],
        "csci",
        "CSCI (Yearly)"
    )

    styled_plot(
        ax,
        largest_share_yearly["year"],
        largest_share_yearly["largest_share_yearly"],
        "largest_share",
        "Largest Community Share (Yearly)"
    )

    ax.set_xticks(csci_yearly["year"])
    ax.set_xticklabels(csci_yearly["year"], rotation=45, ha="right")
    ax.legend()
    ax.set_title("CSCI + Largest Community Share (Yearly)")

    savefig_clean(fig, os.path.join(TS_DIR, "csci_largestshare_yearly.png"))


def plot_csci_mean_strength_monthly(csci_monthly, mean_strength_monthly):
    fig, ax = plt.subplots(figsize=(10, 6))

    styled_plot(
        ax,
        csci_monthly["period_dt"],
        csci_monthly["composite_structural_change_index"],
        "csci",
        "CSCI (Monthly)"
    )

    styled_plot(
        ax,
        mean_strength_monthly["period_dt"],
        mean_strength_monthly["mean_strength_norm"],
        "mean_strength_norm",
        "Mean Strength (Monthly)"
    )

    format_month_axis(ax)
    ax.legend()
    ax.set_title("CSCI + Mean Strength (Monthly)")

    savefig_clean(fig, os.path.join(TS_DIR, "csci_meanstrength_monthly.png"))


def plot_csci_mean_strength_yearly(csci_yearly, mean_strength_yearly):
    fig, ax = plt.subplots(figsize=(10, 6))

    styled_plot(
        ax,
        csci_yearly["year"],
        csci_yearly["csci_yearly"],
        "csci",
        "CSCI (Yearly)"
    )

    styled_plot(
        ax,
        mean_strength_yearly["year"],
        mean_strength_yearly["mean_strength_norm_yearly"],
        "mean_strength_norm",
        "Mean Strength (Yearly)"
    )

    ax.set_xticks(csci_yearly["year"])
    ax.set_xticklabels(csci_yearly["year"], rotation=45, ha="right")
    ax.legend()
    ax.set_title("CSCI + Mean Strength (Yearly)")

    savefig_clean(fig, os.path.join(TS_DIR, "csci_meanstrength_yearly.png"))


def plot_csci_stability_monthly(csci_monthly, gov_monthly):
    fig, ax = plt.subplots(figsize=(10, 6))

    styled_plot(
        ax,
        csci_monthly["period_dt"],
        csci_monthly["composite_structural_change_index"],
        "csci",
        "CSCI (Monthly)"
    )

    styled_plot(
        ax,
        gov_monthly["period_dt"],
        gov_monthly["stability_index"],
        "stability_index",
        "Stability Index (Monthly)"
    )

    format_month_axis(ax)
    ax.legend()
    ax.set_title("CSCI + Stability Index (Monthly)")

    savefig_clean(fig, os.path.join(TS_DIR, "csci_stability_monthly.png"))


def plot_csci_stability_yearly(csci_yearly, gov_yearly):
    fig, ax = plt.subplots(figsize=(10, 6))

    gov_yearly = gov_yearly.copy()
    gov_yearly["year"] = gov_yearly["period_dt"].dt.year

    styled_plot(
        ax,
        csci_yearly["year"],
        csci_yearly["csci_yearly"],
        "csci",
        "CSCI (Yearly)"
    )

    styled_plot(
        ax,
        gov_yearly["year"],
        gov_yearly["stability_index"],
        "stability_index",
        "Stability Index (Yearly)"
    )

    ax.set_xticks(csci_yearly["year"])
    ax.set_xticklabels(csci_yearly["year"], rotation=45, ha="right")
    ax.legend()
    ax.set_title("CSCI + Stability Index (Yearly)")

    savefig_clean(fig, os.path.join(TS_DIR, "csci_stability_yearly.png"))
    

def plot_csci_stability_volatility_yearly(csci_yearly, gov_yearly):
    fig, ax = plt.subplots(figsize=(10, 6))

    gov_yearly = gov_yearly.copy()
    gov_yearly["year"] = gov_yearly["period_dt"].dt.year

    styled_plot(
        ax,
        csci_yearly["year"],
        csci_yearly["csci_yearly"],
        "csci",
        "CSCI (Yearly)"
    )

    styled_plot(
        ax,
        gov_yearly["year"],
        gov_yearly["stability_volatility_yearly"],
        "stability_index",
        "Stability Volatility (Yearly)"
    )

    ax.set_xticks(csci_yearly["year"])
    ax.set_xticklabels(csci_yearly["year"], rotation=45, ha="right")
    ax.legend()
    ax.set_title("CSCI + Stability Volatility (Yearly)")

    savefig_clean(fig, os.path.join(TS_DIR, "csci_stability_volatility_yearly.png"))


# ============================================================
# Chart Orchestration
# ============================================================

CHARTS = [
    # Structural Delta
    plot_structural_delta_dual,
    plot_structural_delta_normalized,
    plot_delta_comm_mod_yearly,
    plot_comm_volatility_yearly,
    plot_modularity_volatility_yearly,

    # Community Structure
    plot_community_count_monthly,
    plot_community_count_yearly,
    plot_modularity_monthly,
    plot_modularity_yearly,
    plot_comm_modularity_monthly,
    plot_comm_modularity_yearly,

    # Concentration
    plot_largest_share_monthly,
    plot_largest_share_yearly,
    plot_modularity_largestshare_yearly,
    plot_top3_share_monthly,
    plot_top3_share_yearly,

    # Intensity
    plot_mean_strength_monthly,
    plot_mean_strength_yearly,
    plot_active_edges_monthly,
    plot_active_edges_yearly,

    # Transitional
    plot_delta_comm_mod_roll3,

    # CSCI
    plot_csci_monthly,
    plot_csci_yearly,
    plot_csci_modularity_monthly,
    plot_csci_modularity_yearly,
    plot_csci_largest_share_monthly,
    plot_csci_largest_share_yearly,
    plot_csci_mean_strength_monthly,
    plot_csci_mean_strength_yearly,
    plot_csci_stability_monthly,
    plot_csci_stability_yearly,
    plot_csci_stability_volatility_yearly,
]


# ============================================================
# Main Orchestration
# ============================================================

def main():
    print("Loading data...")
    gov, gov_yearly, gov_monthly = load_data()
    comm_df, nodes_df = load_community_data()

    print("Computing aggregates...")
    agg = compute_aggregates(gov_yearly, gov_monthly, comm_df, nodes_df)

    print("Generating time-series visualizations...")
    for chart in tqdm(CHARTS):
        # Each chart function receives only what it needs
        params = chart.__code__.co_varnames
        kwargs = {k: agg[k] for k in agg if k in params}

        # Add gov_yearly / gov_monthly if needed
        if "gov_yearly" in params:
            kwargs["gov_yearly"] = gov_yearly
        if "gov_monthly" in params:
            kwargs["gov_monthly"] = gov_monthly

        chart(**kwargs)

    print("All time-series charts generated.")


if __name__ == "__main__":
    main()