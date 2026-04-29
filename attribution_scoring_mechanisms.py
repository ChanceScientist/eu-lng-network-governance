"""
attribution_scoring_mechanisms.py — v[none]
Purpose:
Compute mechanism‑specific attribution scores for all attribution indicator
files by evaluating directional consistency of STRONG deviations and
aggregating results to governance‑aligned dimensions.

Inputs:
- Attribution indicators:
    signatures/attribution_indicator_<YYYY-MM>.csv
- Configuration:
    expected_gsr (Gas Storage Regulation)
    expected_rep (REPowerEU)

Responsibilities:
- Load all attribution_indicator_*.csv files
- For each month:
    • classify metric‑level direction (up / down / stable)
    • compare direction to mechanism‑specific expectations
    • evaluate only STRONG deviations
    • assign metric‑level outcomes: aligns / contradicts / none
- Aggregate metric‑level outcomes to dimension‑level scores:
    +1 → at least one metric aligns
     0 → no strong deviations OR only neutral outcomes
    –1 → at least one metric contradicts
- Produce separate score tables for:
    • GSR (governance‑stabilizing regime)
    • REP (re‑prioritization / re‑patterning regime)

Outputs:
- Mechanism‑specific attribution scores:
    signatures/mechanism_attribution_scores_gsr.csv
    signatures/mechanism_attribution_scores_rep.csv

Notes:
- Only STRONG deviations influence scoring; MILD/MODERATE/NORMAL are ignored
- Directional logic is metric‑specific and defined in expected_gsr / expected_rep
- Dimension‑level scores follow the standardized +1 / 0 / –1 scheme used in
  Section IV.H and mechanism‑specific attribution tables
- AI Assistance:
    This script was drafted with support from Microsoft Copilot. All conceptual
    framing, methodological design, and analytical and interpretive decisions
    were made by the author. The author reviewed, edited, and validated all code.
AI Assistance:
    This script was drafted with support from Microsoft Copilot. All conceptual
    framing, methodological design, and analytical and interpretive decisions
    were made by the author. The author reviewed, edited, and validated all code.
"""


import os
import glob
import pandas as pd

SIGN_DIR = "signatures"

# ------------------------------------------------------------
# Load indicator files
# ------------------------------------------------------------

def load_indicator_files():
    pattern = os.path.join(SIGN_DIR, "attribution_indicator_*.csv")
    return sorted(glob.glob(pattern))

# ------------------------------------------------------------
# Expected directions
# ------------------------------------------------------------

expected_gsr = {
    "modularity": "down_or_stable",
    "stability_index": "up",
    "largest_share": "stable_or_down",
    "top3_share": "stable",
    "stability_volatility_yearly": "down",
    "composite_structural_change_index": "down",
    "max_edge_change": "down",
    "mean_edge_change": "down",
    "delta_strength_max": "stable",
    "delta_flow_centrality_max": "stable",
    "delta_flow_share_max": "stable",
    "community_count": "stable",
    "mean_strength": "up_or_stable",
    "active_edges": "up",
}

expected_rep = {
    "modularity": "any",
    "stability_index": "down",
    "largest_share": "down",
    "top3_share": "down",
    "stability_volatility_yearly": "up",
    "composite_structural_change_index": "up",
    "max_edge_change": "up",
    "mean_edge_change": "up",
    "delta_strength_max": "up",
    "delta_flow_centrality_max": "up",
    "delta_flow_share_max": "up",
    "community_count": "up",
    "mean_strength": "up",
    "active_edges": "up",
}

# ------------------------------------------------------------
# Direction helpers
# ------------------------------------------------------------

def classify_direction(diff):
    if diff > 0:
        return "up"
    if diff < 0:
        return "down"
    return "stable"


def direction_matches(direction, expected):
    if expected == "any":
        return True
    if expected == "up_or_stable":
        return direction in ("up", "stable")
    if expected == "down_or_stable":
        return direction in ("down", "stable")
    if expected == "stable":
        return direction == "stable"
    return direction == expected

# ------------------------------------------------------------
# Metric‑level scoring
# ------------------------------------------------------------

def score_metric(row, expected_dict):
    metric = row["metric"]
    deviation = row["deviation"]
    diff = row["diff"]

    if deviation != "STRONG":
        return "none"

    direction = classify_direction(diff)
    expected = expected_dict.get(metric, "any")

    return "aligns" if direction_matches(direction, expected) else "contradicts"

# ------------------------------------------------------------
# Dimension‑level scoring
# ------------------------------------------------------------

def score_dimension(df, expected_dict):
    required = {"metric", "dimension", "diff", "deviation"}
    if not required.issubset(df.columns):
        missing = required - set(df.columns)
        raise ValueError(f"Indicator file missing required columns: {missing}")

    results = {}

    for dim in df["dimension"].unique():
        subset = df[df["dimension"] == dim]
        metric_scores = subset.apply(lambda r: score_metric(r, expected_dict), axis=1)

        if "aligns" in metric_scores.values:
            results[dim] = 1
        elif "contradicts" in metric_scores.values:
            results[dim] = -1
        else:
            results[dim] = 0

    return results

# ------------------------------------------------------------
# Main
# ------------------------------------------------------------

def main():
    files = load_indicator_files()

    gsr_rows = []
    rep_rows = []

    for file in files:
        df = pd.read_csv(file, dtype={"metric": str})
        month = os.path.basename(file).replace("attribution_indicator_", "").replace(".csv", "")

        gsr_scores = score_dimension(df, expected_gsr)
        rep_scores = score_dimension(df, expected_rep)

        for dim in df["dimension"].unique():
            gsr_rows.append({
                "month": month,
                "dimension": dim,
                "score": gsr_scores[dim],
            })
            rep_rows.append({
                "month": month,
                "dimension": dim,
                "score": rep_scores[dim],
            })

    pd.DataFrame(gsr_rows).to_csv(
        os.path.join(SIGN_DIR, "mechanism_attribution_scores_gsr.csv"),
        index=False
    )
    pd.DataFrame(rep_rows).to_csv(
        os.path.join(SIGN_DIR, "mechanism_attribution_scores_rep.csv"),
        index=False
    )

    print("✓ mechanism_attribution_scores_gsr.csv written")
    print("✓ mechanism_attribution_scores_rep.csv written")


if __name__ == "__main__":
    main()