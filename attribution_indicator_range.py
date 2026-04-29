"""
attribution_indicator_range.py — v[none]
Purpose:
Construct long‑form attribution indicators for each target month by combining
structural and governance signatures, computing baseline statistics, deviation
categories, and governance‑aligned dimensions.

Inputs:
- Structural signature:
    signatures/structural_signature.csv
- Governance signature:
    signatures/governance_signature.csv
- Configuration:
    • Baseline window (START_PERIOD → END_PERIOD)
    • Target evaluation window (TARGET_START → TARGET_END)
    • METRIC_ORDER (export order)
    • DIMENSION_MAP (metric → dimension(s))
    • DIMENSION_ORDER (sorting)

Responsibilities:
- Load structural and governance signatures
- Combine signatures (structural overrides governance when both exist)
- Identify baseline periods and compute:
    • mean
    • standard deviation
    • 10th percentile
    • 90th percentile
- Extract target‑month values and compute:
    • diff from baseline mean
    • deviation category:
        NORMAL, MILD, MODERATE, STRONG
- Expand metrics into governance‑aligned dimensions
- Produce long‑form attribution indicator tables (metric × dimension)

Outputs:
- Per‑month attribution indicators:
    signatures/attribution_indicator_<YYYY-MM>.csv

Notes:
- Baseline and target windows are inclusive and string‑sorted (YYYY‑MM)
- Structural signature values override governance signature values when both exist
- Deviation categories use combined percentile‑band and standard‑deviation logic
- Output is long‑form to support narrative attribution and mechanism scoring
- AI Assistance:
    This script was drafted with support from Microsoft Copilot. All conceptual
    framing, methodological design, and analytical and interpretive decisions
    were made by the author. The author reviewed, edited, and validated all code.
"""


import os
import pandas as pd
import numpy as np

SIGN_DIR = "signatures"

# ------------------------------------------------------------
# Configuration
# ------------------------------------------------------------

# Baseline
START_PERIOD = "2017-01" 
END_PERIOD   = "2019-12" 

# Evaluation period
TARGET_START = "2022-01" 
TARGET_END   = "2025-05" 

METRIC_ORDER = [
    "modularity",
    "stability_index",
    "largest_share",
    "top3_share",
    "stability_volatility_yearly",
    "composite_structural_change_index",
    "max_edge_change",
    "mean_edge_change",
    "delta_strength_max",
    "delta_flow_centrality_max",
    "delta_flow_share_max",
    "community_count",
    "mean_strength",
    "active_edges",
]

DIMENSION_MAP = {
    "modularity": ["system_cohesion"],
    "stability_index": ["system_cohesion", "structural_continuity"],
    "largest_share": ["corridor_concentration"],
    "top3_share": ["corridor_concentration"],
    "stability_volatility_yearly": ["structural_continuity"],
    "composite_structural_change_index": ["structural_change"],
    "max_edge_change": ["structural_change"],
    "mean_edge_change": ["structural_change"],
    "delta_strength_max": ["structural_change"],
    "delta_flow_centrality_max": ["structural_change"],
    "delta_flow_share_max": ["structural_change"],
    "community_count": ["community_prominence"],
    "mean_strength": ["community_prominence"],
    "active_edges": ["community_prominence"],
}

DIMENSION_ORDER = [
    "system_cohesion",
    "corridor_concentration",
    "structural_continuity",
    "structural_change",
    "community_prominence",
]

# ------------------------------------------------------------
# Helpers
# ------------------------------------------------------------

def load_signatures():
    gov = pd.read_csv(os.path.join(SIGN_DIR, "governance_signature.csv"))
    struct = pd.read_csv(os.path.join(SIGN_DIR, "structural_signature.csv"))
    return gov, struct


def filter_period_columns(df):
    period_cols = [
        c for c in df.columns
        if len(str(c)) == 7 and START_PERIOD <= str(c) <= END_PERIOD
    ]
    return df[["metric"] + period_cols]


def get_target_months(df):
    return [
        c for c in df.columns
        if len(str(c)) == 7 and TARGET_START <= c <= TARGET_END
    ]


def classify_deviation(diff, std, p10, p90, value):
    if pd.isna(value):
        return "NORMAL"

    in_band = (p10 <= value <= p90)
    within_1sd = abs(diff) <= std
    within_2sd = abs(diff) <= 2 * std

    if within_1sd and in_band:
        return "NORMAL"
    if (not within_1sd) and in_band:
        return "MILD"
    if (not in_band) and within_2sd:
        return "MODERATE"
    return "STRONG"

# ------------------------------------------------------------
# Indicator construction
# ------------------------------------------------------------

def build_attribution_indicator(gov, struct, month):

    gov_f = filter_period_columns(gov).set_index("metric")
    struct_f = filter_period_columns(struct).set_index("metric")

    # struct overrides gov
    combined = struct_f.combine_first(gov_f)

    # baseline statistics
    combined["mean"] = combined.mean(axis=1)
    combined["std"]  = combined.std(axis=1)
    combined["p10"]  = combined.quantile(0.10, axis=1)
    combined["p90"]  = combined.quantile(0.90, axis=1)

    # target values (struct overrides gov)
    struct_target = struct.set_index("metric")[month] if month in struct.columns else pd.Series()
    gov_target    = gov.set_index("metric")[month]    if month in gov.columns    else pd.Series()
    target_values = struct_target.combine_first(gov_target)

    value_col = f"value_{month}"
    combined[value_col] = combined.index.map(target_values.to_dict())

    # diff + deviation
    combined["diff"] = combined[value_col] - combined["mean"]
    combined["deviation"] = combined.apply(
        lambda r: classify_deviation(r["diff"], r["std"], r["p10"], r["p90"], r[value_col]),
        axis=1
    )

    # expand to long form
    rows = []
    for metric in METRIC_ORDER:
        if metric not in combined.index:
            continue
        for dim in DIMENSION_MAP.get(metric, [""]):
            r = combined.loc[metric].copy()
            r["metric"] = metric
            r["dimension"] = dim
            rows.append(r)

    out = pd.DataFrame(rows)

    # dimension ordering
    out["dimension"] = pd.Categorical(out["dimension"], categories=DIMENSION_ORDER, ordered=True)
    out = out.sort_values("dimension")

    # stable column order
    col_order = ["metric", "dimension", "mean", "std", "p10", "p90", value_col, "diff", "deviation"]
    return out[col_order]

# ------------------------------------------------------------
# Main
# ------------------------------------------------------------

def main():
    gov, struct = load_signatures()
    months = sorted(set(get_target_months(gov) + get_target_months(struct)))

    for month in months:
        out = build_attribution_indicator(gov, struct, month)
        out.to_csv(os.path.join(SIGN_DIR, f"attribution_indicator_{month}.csv"), index=False)
        print(f"✓ attribution_indicator_{month}.csv written to {SIGN_DIR}/")


if __name__ == "__main__":
    main()