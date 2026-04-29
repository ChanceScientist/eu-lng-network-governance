"""
stage01_clean_edges.py — v4.0 (2026-03-15)
Purpose:
Clean and validate canonical raw LNG trade edges produced by stage00_ingest_raw.py,
ensuring consistent ISO codes, positive quantities, and aggregated exporter→importer edges.

Inputs:
- Directory: data_ingested/
- Files: raw_<YYYY-MM>.csv produced by stage00_ingest_raw.py
- Required columns: partnerISO, reporterISO, qty, partner2ISO
- Reference data: COUNTRIES (valid ISO codes)
- Utility modules: extract_period(), file_checksum()

Responsibilities:
- Validate ISO codes against COUNTRIES
- Remove rows with invalid, missing, or non‑positive quantities
- Detect and log duplicate exporter→importer pairs
- Diagnose routing variants and quantity anomalies
- Aggregate duplicates into unique edges with summed quantities
- Generate per‑period diagnostics and multi‑period summaries
- Compute checksums for reproducibility
- Export cleaned edge lists to edges_clean/

Outputs:
- Cleaned edges: edges_clean/edges_<YYYY-MM>_clean.csv
- Per‑period diagnostics: diagnostics/edges_diagnostics_<YYYY-MM>.csv
- Multi‑period diagnostics: diagnostics/edges_diagnostics_all_periods.csv
- Summary table: diagnostics/edges_summary_all_periods.csv
- Checksums: diagnostics/edges_checksums.csv
- Log file: logs/stage01_clean_edges_<timestamp>.log

Notes:
- This stage assumes ingestion‑stage schema from stage00
- partner2ISO is retained only for diagnostics; not included in final edges
- Aggregation is performed at (partnerISO, reporterISO) level
- AI Assistance:
    This script was drafted with support from Microsoft Copilot. All conceptual
    framing, methodological design, and analytical and interpretive decisions
    were made by the author. The author reviewed, edited, and validated all code.
"""

SCRIPT_VERSION = "v4.0 (2026-03-15)"

# ============================================================
# Setup
# ============================================================

import os
import logging
import pandas as pd
from tqdm import tqdm
from datetime import datetime

from tools.periods import extract_period
from tools.io_utils import file_checksum
from tools.constants import COUNTRIES

INGESTED_DIR = "data_ingested"
OUTPUT_DIR = "edges_clean"
DIAG_DIR = "diagnostics"
LOG_DIR = "logs"

os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(DIAG_DIR, exist_ok=True)
os.makedirs(LOG_DIR, exist_ok=True)

timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
LOG_FILE = os.path.join(LOG_DIR, f"stage01_clean_edges_{timestamp}.log")

# Reset handlers
for h in logging.root.handlers[:]:
    logging.root.removeHandler(h)

logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    encoding="utf-8"
)

logging.info("=== Starting Clean Edge List Pipeline ===")
logging.info(f"Script version: {SCRIPT_VERSION}")

# ============================================================
# Cleaning Logic
# ============================================================

def clean_edges(df, period):
    logging.info(f"-- {period}: initial rows = {len(df)}")

    # Keep only ingestion-stage columns
    df = df[["partnerISO", "reporterISO", "qty", "partner2ISO"]].copy()

    # Remove rows with invalid ISO codes
    before = len(df)
    df = df[df.partnerISO.isin(COUNTRIES) & df.reporterISO.isin(COUNTRIES)]
    invalid_iso_removed = before - len(df)

    # Remove missing or non-positive quantities
    before = len(df)
    df = df[df.qty.notna() & (df.qty > 0)]
    missing_zero_removed = before - len(df)

    # Identify duplicate exporter→importer pairs
    dup_mask = df.duplicated(subset=["partnerISO", "reporterISO"], keep=False)
    dup_count = dup_mask.sum()
    dups = df[dup_mask]

    # Duplicate diagnostics
    diag_rows = []
    if not dups.empty:
        for (src, dst), group in dups.groupby(["partnerISO", "reporterISO"]):
            p2_vals = sorted(group["partner2ISO"].dropna().unique().tolist())
            qty_vals = sorted(group["qty"].unique().tolist())
            anomaly = len(qty_vals) > 1

            diag_rows.append({
                "period": period,
                "exporter": src,
                "importer": dst,
                "rows": len(group),
                "partner2ISO_values": p2_vals,
                "qty_values": qty_vals,
                "difference_qty": max(qty_vals) - min(qty_vals),
                "routing_only": not anomaly,
                "anomaly_qty": anomaly,
                "all_W00": all(v == "W00" for v in p2_vals),
                "sum_qty_before_agg": group["qty"].sum()
            })

    diag_df = pd.DataFrame(diag_rows)
    diag_df.to_csv(os.path.join(DIAG_DIR, f"edges_diagnostics_{period}.csv"), index=False)

    # Aggregate duplicates
    total_pre_agg_qty = df["qty"].sum()
    df_clean = df.groupby(["partnerISO", "reporterISO"], as_index=False)["qty"].sum()
    total_post_agg_qty = df_clean["qty"].sum()

    # Summary row for this period
    summary_row = {
        "period": period,
        "raw_rows": len(df) + invalid_iso_removed + missing_zero_removed,
        "invalid_iso_removed": invalid_iso_removed,
        "missing_zero_removed": missing_zero_removed,
        "duplicate_pairs": dup_count,
        "routing_only_duplicates": diag_df["routing_only"].sum() if not diag_df.empty else 0,
        "true_multi_shipment_duplicates": diag_df["anomaly_qty"].sum() if not diag_df.empty else 0,
        "routing_variants": diag_df["partner2ISO_values"].apply(len).sum() if not diag_df.empty else 0,
        "total_pre_agg_qty": total_pre_agg_qty,
        "total_post_agg_qty": total_post_agg_qty,
        "final_unique_edges": len(df_clean)
    }

    return df_clean, summary_row, diag_df

# ============================================================
# Main Loop
# ============================================================

def main():
    summary_rows = []
    checksum_rows = []
    all_diag_rows = []

    files = sorted(f for f in os.listdir(INGESTED_DIR) if f.startswith("raw_"))

    for file in tqdm(files, desc="Cleaning ingested edge lists"):
        try:
            period = extract_period(file)
        except ValueError:
            logging.warning(f"Skipping file with no valid period: {file}")
            continue

        path = os.path.join(INGESTED_DIR, file)

        try:
            df = pd.read_csv(path)
            df_clean, summary_row, diag_df = clean_edges(df, period)
            summary_rows.append(summary_row)

            if not diag_df.empty:
                all_diag_rows.append(diag_df)

            out_path = os.path.join(OUTPUT_DIR, f"edges_{period}_clean.csv")
            df_clean.to_csv(out_path, index=False)

            checksum_rows.append({
                "period": period,
                "filename": f"edges_{period}_clean.csv",
                "checksum": file_checksum(out_path)
            })

        except Exception as e:
            logging.error(f"Error processing {file}: {e}")

    # Write summaries
    pd.DataFrame(summary_rows).to_csv(
        os.path.join(DIAG_DIR, "edges_summary_all_periods.csv"), index=False
    )

    pd.DataFrame(checksum_rows).to_csv(
        os.path.join(DIAG_DIR, "edges_checksums.csv"), index=False
    )

    if all_diag_rows:
        pd.concat(all_diag_rows, ignore_index=True).to_csv(
            os.path.join(DIAG_DIR, "edges_diagnostics_all_periods.csv"),
            index=False
        )

    logging.info("=== Clean Edge List Pipeline Complete ===")

if __name__ == "__main__":
    main()