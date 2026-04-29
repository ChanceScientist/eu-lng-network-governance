"""
stage07_transitions_full.py — v[none]
Purpose:
Compute community transition matrices, monthly stability indices, and yearly
stability volatility for normalized LNG trade graphs, and merge these metrics
into governance_report_core.csv with accompanying visualizations.

Inputs:
- Community assignments:
    governance/community_nodes_all_periods.csv
      (via load_community_nodes())
- Governance core:
    governance/governance_report_core.csv
      (via load_governance_core())
- Utility modules:
    sort_periods_yearly_first(), split_periods(),
    styled_plot(), savefig_clean()

Responsibilities:
- Load node→community assignments for all periods
- Split assignments into yearly and monthly sequences
- Compute community transition matrices using Hungarian matching
- Compute:
    - monthly stability index (share of nodes staying in same community)
    - yearly volatility of stability (std of monthly stability)
    - yearly mean stability index
- Export transition matrices (CSV)
- Merge stability metrics into governance_report_core.csv
- Generate visualizations:
    - monthly stability time series
    - yearly stability volatility
    - yearly stability index
    - transition heatmaps
    - stacked transition-share charts

Outputs:
- Transition matrices:
    transitions/transition_<t>_to_<t+1>.csv
- Stability metrics:
    governance/governance_report_core.csv (updated)
- Visualizations:
    transitions/stability_index_monthly.png
    transitions/stability_volatility_yearly.png
    transitions/stability_index_yearly.png
    transitions/heatmap_<t>_to_<t+1>.png
    transitions/stacked_<t>_to_<t+1>.png

Notes:
- Community labels are made persistent across periods via Hungarian matching
- Stability index is computed only for monthly transitions
- Yearly volatility summarizes within‑year variation in monthly stability
- Visual outputs support Appendix E and governance narrative development
- AI Assistance:
    This script was drafted with support from Microsoft Copilot. All conceptual
    framing, methodological design, and analytical and interpretive decisions
    were made by the author. The author reviewed, edited, and validated all code.
"""


import os

import numpy as np
from scipy.optimize import linear_sum_assignment

import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from tqdm import tqdm

# Shared helpers
from stage07_helpers import (
    GOV_DIR,
    TRANS_DIR,
    COMM_TRANS_DIR,
    sort_periods_yearly_first,
    load_community_nodes,
    split_periods,
    load_governance_core,
    styled_plot,
    savefig_clean,
)


# ------------------------------------------------------------
# Community Matching (Persistent Labels Across Periods)
# ------------------------------------------------------------
def match_communities(prev_assign, curr_assign):
    """
    prev_assign: dict node → community at t
    curr_assign: dict node → community at t+1
    Returns: new_curr_assign with relabeled communities
    """

    prev_comms = sorted(set(prev_assign.values()))
    curr_comms = sorted(set(curr_assign.values()))

    # Build overlap matrix
    overlap = np.zeros((len(prev_comms), len(curr_comms)), dtype=int)

    for i, pc in enumerate(prev_comms):
        prev_nodes = {n for n, c in prev_assign.items() if c == pc}
        for j, cc in enumerate(curr_comms):
            curr_nodes = {n for n, c in curr_assign.items() if c == cc}
            overlap[i, j] = len(prev_nodes & curr_nodes)

    # Hungarian assignment (maximize overlap → minimize negative overlap)
    row_ind, col_ind = linear_sum_assignment(-overlap)

    # Build mapping: curr_comm → matched_prev_comm
    mapping = {}
    for i, j in zip(row_ind, col_ind):
        mapping[curr_comms[j]] = prev_comms[i]

    # Any unmatched curr communities get new labels
    next_label = max(prev_comms) + 1
    for cc in curr_comms:
        if cc not in mapping:
            mapping[cc] = next_label
            next_label += 1

    # Apply mapping
    new_curr_assign = {n: mapping[curr_assign[n]] for n in curr_assign}

    return new_curr_assign

# ------------------------------------------------------------
# Compute transitions for a single group (yearly or monthly)
# ------------------------------------------------------------
def compute_transitions_group(df_group, desc_label):
    """
    Compute transition matrices + stability index for either yearly or monthly.
    Expects columns: 'period', 'node', 'community', 'period_dt'.
    """

    df_group = df_group.sort_values("period_dt")
    periods = df_group["period"].unique()

    transition_matrices = {}
    stability_rows = []

    for i in tqdm(range(len(periods) - 1), desc=f"Computing {desc_label} transitions"):

        t = periods[i]
        t_next = periods[i + 1]

        df_t = df_group[df_group["period"] == t]
        df_next = df_group[df_group["period"] == t_next]

        # Only nodes present in both periods
        common_nodes = set(df_t["node"]).intersection(df_next["node"])
        df_t = df_t[df_t["node"].isin(common_nodes)]
        df_next = df_next[df_next["node"].isin(common_nodes)]

        # Build mapping: node → community
        map_t = dict(zip(df_t["node"], df_t["community"]))
        map_next = dict(zip(df_next["node"], df_next["community"]))

        # Community matching for persistent labels
        map_next = match_communities(map_t, map_next)

        # Community sets AFTER matching
        comms_t = sorted(set(map_t.values()))
        comms_next = sorted(set(map_next.values()))

        # Initialize transition matrix
        T = pd.DataFrame(0, index=comms_t, columns=comms_next)

        # Fill transitions
        for n in common_nodes:
            i_c = map_t[n]
            j_c = map_next[n]
            T.loc[i_c, j_c] += 1

        # Save matrix
        out_path = os.path.join(TRANS_DIR, f"transition_{t}_to_{t_next}.csv")
        T.to_csv(out_path)
        transition_matrices[(t, t_next)] = T

        # Stability index
        stable = sum(map_t[n] == map_next[n] for n in common_nodes)
        stability = stable / len(common_nodes) if common_nodes else None

        stability_rows.append({
            "period": t_next,
            "stability_index": stability,
        })

    return transition_matrices, stability_rows


# ------------------------------------------------------------
# Visualization
# ------------------------------------------------------------
def visualize_transitions(transition_matrices, stability_df, stab_vol_yearly, stab_yearly_mean):

    # 1. Stability Index Time-Series (Monthly)
    fig, ax = plt.subplots(figsize=(10, 6))
    
    styled_plot(
        ax,
        stability_df["period"],
        stability_df["stability_index"],
        "stability_index",
        "Stability Index (Monthly)"
    )
    
    ax.set_title("Community Stability Index Over Time (Monthly)")
    ax.set_ylabel("Stability (share of nodes staying in same community)")
    ax.xaxis.set_major_locator(plt.MaxNLocator(nbins=20))
    plt.xticks(rotation=45, ha="right")
    
    savefig_clean(fig, os.path.join(COMM_TRANS_DIR, "stability_index_monthly.png"))

    # 2. Yearly Volatility of Stability
    fig, ax = plt.subplots(figsize=(10, 6))
    
    styled_plot(
        ax,
        stab_vol_yearly["year"],
        stab_vol_yearly["stability_volatility_yearly"],
        "stability_index",   # uses same color family as stability
        "Stability Volatility (Yearly)"
    )
    
    ax.set_title("Yearly Volatility of Community Stability")
    ax.set_ylabel("Volatility (Std of Monthly Stability)")
    ax.set_xticks(stab_vol_yearly["year"])
    ax.set_xticklabels(stab_vol_yearly["year"], rotation=45, ha="right")
    
    savefig_clean(fig, os.path.join(COMM_TRANS_DIR, "stability_volatility_yearly.png"))

    # 3. Yearly Stability Index (Mean of Monthly)
    fig, ax = plt.subplots(figsize=(10, 6))

    styled_plot(
        ax,
        stab_yearly_mean["year"],
        stab_yearly_mean["stability_index"],
        "stability_index",
        "Stability Index (Yearly)"
    )

    ax.set_title("Community Stability Index Over Time (Yearly)")
    ax.set_ylabel("Stability (mean monthly share of nodes staying in same community)")
    ax.set_xticks(stab_yearly_mean["year"])
    ax.set_xticklabels(stab_yearly_mean["year"], rotation=45, ha="right")

    savefig_clean(fig, os.path.join(COMM_TRANS_DIR, "stability_index_yearly.png"))
    
    # 3. Heatmaps
    for (t, t_next), T in tqdm(transition_matrices.items(),
                               desc="Rendering transition heatmaps"):

        fig, ax = plt.subplots(figsize=(8, 6))
        sns.heatmap(T, annot=True, fmt="d", cmap="Blues", ax=ax)
        ax.set_title(f"Community Transition Matrix: {t} → {t_next}")
        ax.set_xlabel(f"Communities at {t_next}")
        ax.set_ylabel(f"Communities at {t}")
        savefig_clean(fig, os.path.join(COMM_TRANS_DIR, f"heatmap_{t}_to_{t_next}.png"))

    # 4. Stacked Column Charts
    for (t, t_next), T in tqdm(transition_matrices.items(),
                               desc="Rendering stacked column charts"):
    
        T_norm = T.div(T.sum(axis=1), axis=0)

        # Relabel communities to consecutive integers
        # Old labels (e.g., [0, 2, 5])
        old_labels = list(T_norm.index)
    
        # New labels (0,1,2,...)
        mapping = {old: new for new, old in enumerate(sorted(old_labels))}
    
        # Apply mapping to the index
        T_norm.index = T_norm.index.map(mapping)

        fig, ax = plt.subplots(figsize=(10, 6))
        bottom = pd.Series([0] * len(T_norm), index=T_norm.index)
    
        for col in T_norm.columns:
            ax.bar(T_norm.index, T_norm[col], bottom=bottom, label=f"→ {col}")
    
            # Add percentage labels
            for x, (b, h) in enumerate(zip(bottom, T_norm[col])):
                if h > 0.02:  # only label segments >2% to avoid clutter
                    ax.text(
                        x,
                        b + h / 2,
                        f"{h:.0%}",
                        ha="center",
                        va="center",
                        fontsize=9,
                        color="white"
                    )
    
            bottom = bottom + T_norm[col]

        # Force integer ticks
        ax.set_xticks(T_norm.index)
        ax.set_xticklabels(T_norm.index.astype(int))

        ax.set_title(f"Community Transition Shares: {t} → {t_next}")
        ax.set_xlabel(f"Communities at {t}")
        ax.set_ylabel("Share of Nodes Transitioning")
        ax.legend(title="Destination Community")
    
        savefig_clean(fig, os.path.join(COMM_TRANS_DIR, f"stacked_{t}_to_{t_next}.png"))
        
    print("Transition visualizations generated.")


# ------------------------------------------------------------
# Main
# ------------------------------------------------------------
def main():

    # 1. Load community assignments
    comm_nodes = load_community_nodes()

    # 2. Split into yearly and monthly
    comm_yearly, comm_monthly = split_periods(comm_nodes)

    # 3. Compute transitions
    yearly_mats, _ = compute_transitions_group(comm_yearly, "yearly")
    monthly_mats, monthly_rows = compute_transitions_group(comm_monthly, "monthly")

    # Combine matrices
    transition_matrices = {**yearly_mats, **monthly_mats}

    # Monthly stability only
    stability_all = pd.DataFrame(monthly_rows)

    # 4. Compute yearly volatility of stability
    stability_all["year"] = stability_all["period"].str.slice(0, 4).astype(int)
    stab_vol_yearly = (
        stability_all.groupby("year")["stability_index"]
        .std()
        .reset_index(name="stability_volatility_yearly")
    )

    # 5. Compute yearly stability_index as mean of monthly stability_index
    stab_yearly_mean = (
        stability_all.assign(year=lambda df: df["period"].str.slice(0, 4).astype(int))
        .groupby("year")["stability_index"]
        .mean()
        .reset_index()
    )
    
    # Convert year → period string (YYYY)
    stab_yearly_mean["period"] = stab_yearly_mean["year"].astype(str)
    stab_yearly_mean = stab_yearly_mean[["year", "period", "stability_index"]]

    # 6. Merge into governance_report_core.csv
    gov = load_governance_core()

    # Combine monthly + yearly stability_index
    stab_combined = pd.concat([
        stability_all[["period", "stability_index"]],  # monthly
        stab_yearly_mean                               # yearly
    ], ignore_index=True)
    
    # Drop duplicates so yearly overwrites monthly-NaN rows
    stab_combined = stab_combined.drop_duplicates(subset=["period"], keep="last")

    gov = gov.merge(stab_combined, on="period", how="left")

    # Merge yearly volatility
    gov["year"] = gov["period"].str.slice(0, 4).astype(int)
    gov = gov.merge(stab_vol_yearly, on="year", how="left")
    gov = gov.drop(columns=["year"])

    gov.to_csv(os.path.join(GOV_DIR, "governance_report_core.csv"), index=False)
    print("Transitions + stability index + yearly volatility merged into governance_report_core.csv")

    # 7. Visualize
    visualize_transitions(transition_matrices, stability_all, stab_vol_yearly, stab_yearly_mean)


if __name__ == "__main__":
    main()