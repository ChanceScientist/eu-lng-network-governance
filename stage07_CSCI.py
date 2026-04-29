"""
stage07_csci.py — v[none]
Purpose:
Compute the Composite Structural Change Index (CSCI) using governance‑aligned
weights and min–max normalization, separately for yearly and monthly periods,
and merge the resulting CSCI values into governance_report_core.csv.

Inputs:
- Governance core:
    governance/governance_report_core.csv
- Utility modules:
    load_governance_core(), split_periods(), normalize(),
    sort_periods_yearly_first(), CONFIG_CSCI
- CONFIG_CSCI:
    - metric_cols: list of structural‑delta metrics to include
    - weights: governance‑aligned weights for each metric
    - output_col (optional): name of CSCI output column

Responsibilities:
- Load governance_report_core.csv
- Split rows into yearly and monthly groups (datetime‑aware)
- Normalize each metric within each group using min–max scaling
- Apply governance‑aligned weights to compute CSCI
- Construct a clean period→CSCI table
- Merge CSCI back into governance_report_core.csv
- Preserve canonical period ordering

Outputs:
- Updated governance core:
    governance/governance_report_core.csv
      (with new CSCI column)
- No additional files are created

Notes:
- Yearly and monthly CSCI are computed independently to avoid scale mixing
- Only the CSCI column is merged back; no other fields are modified
AI Assistance:
    This script was drafted with support from Microsoft Copilot. All conceptual
    framing, methodological design, and analytical and interpretive decisions
    were made by the author. The author reviewed, edited, and validated all code.
"""


import os
import pandas as pd
import numpy as np

from stage07_helpers import (
    GOV_DIR,
    sort_periods_yearly_first,
    load_governance_core,
    normalize,
    split_periods,
    CONFIG_CSCI,
)


# ------------------------------------------------------------
# Core computation for a single group (monthly or yearly)
# ------------------------------------------------------------
def compute_csci_group(df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute CSCI for either monthly or yearly rows.
    Normalization is applied only within this group.
    """

    metric_cols = CONFIG_CSCI["metric_cols"]
    weights = CONFIG_CSCI["weights"]
    output_col = CONFIG_CSCI.get("output_col", "composite_structural_change_index")

    # Ensure all required columns exist
    missing = [c for c in metric_cols if c not in df.columns]
    if missing:
        raise KeyError(f"Missing required CSCI columns: {missing}")

    # 1. Min–max scale each metric using shared normalize()
    scaled_cols = {}
    for col in metric_cols:
        scaled_name = f"{col}__scaled"
        df[scaled_name] = normalize(df[col])
        scaled_cols[col] = scaled_name

    # 2. Weighted composite
    composite = np.zeros(len(df), dtype=float)
    for col in metric_cols:
        w = weights[col]
        composite += w * df[scaled_cols[col]].to_numpy()

    df[output_col] = composite

    return df


def main():
    print("Loading governance_report_core.csv ...")
    gov = load_governance_core()
    df = gov.copy()
    
    # --------------------------------------------------------
    # Split into yearly and monthly using datetime-aware helper
    # --------------------------------------------------------
    print("Splitting into yearly and monthly subsets ...")
    df_yearly, df_monthly = split_periods(df)

    print(f"Yearly rows:  {len(df_yearly)}")
    print(f"Monthly rows: {len(df_monthly)}")

    # --------------------------------------------------------
    # Compute CSCI separately for each group
    # --------------------------------------------------------
    print("Computing yearly CSCI ...")
    df_yearly = compute_csci_group(df_yearly)

    print("Computing monthly CSCI ...")
    df_monthly = compute_csci_group(df_monthly)

    # --------------------------------------------------------
    # Build a clean 2‑column CSCI table (like stability_index)
    # --------------------------------------------------------
    output_col = CONFIG_CSCI.get("output_col", "composite_structural_change_index")

    csci_yearly_only = df_yearly[["period", output_col]].copy()
    csci_monthly_only = df_monthly[["period", output_col]].copy()

    csci_only = pd.concat([csci_yearly_only, csci_monthly_only], ignore_index=True)
    csci_only = csci_only.drop_duplicates(subset=["period"], keep="last")

    # --------------------------------------------------------
    # Merge ONLY the CSCI column into the original governance core
    # --------------------------------------------------------
    print("Merging CSCI into governance_report_core.csv ...")
    gov_merged = gov.merge(csci_only, on="period", how="left", sort=False)
     
    # Optional: keep canonical period ordering if desired
    gov_merged = sort_periods_yearly_first(gov_merged)

    # --------------------------------------------------------
    # Write updated governance_report_core.csv
    # --------------------------------------------------------
    outpath = os.path.join(GOV_DIR, "governance_report_core.csv")
    print(f"Writing updated file to: {outpath}")
    gov_merged.to_csv(outpath, index=False)

    print("Done.")


if __name__ == "__main__":
    main()