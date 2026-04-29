"""
stage00_ingest_raw.py — v4.7 (2026-03-22)
Purpose:
Ingest and validate monthly raw EU‑LNG data, ensuring period‑correct,
schema‑consistent inputs for stage01_clean_edges.py.

Inputs:
- Directory: data_raw/Monthly/
- Files: Monthly CSVs with Comtrade-style fields
- Required columns (if present): refYear, refMonth, period, reporterISO,
  partnerISO, partner2ISO, qty, isQtyEstimated, qtyUnitAbbr, cmdCode, flowCode
- Filename must encode period (YYYY-MM) for validation
- Utility modules: extract_period()

Responsibilities:
- Scan data_raw/Monthly/ for monthly CSV files
- Load raw files with robust UTF‑8‑SIG → Latin‑1 fallback
- Validate temporal integrity (refYear, refMonth, period vs. filename)
- Detect mixed‑period or misnamed files
- Standardize ingestion schema and normalize ISO codes
- Convert qty to numeric
- Export canonical raw files to data_ingested/
- Produce ingestion diagnostics and logs

Outputs:
- Canonical monthly CSVs: data_ingested/raw_<YYYY-MM>.csv
- Diagnostics summary: diagnostics/raw_ingestion_summary.csv
- Log file: logs/stage00_ingest_raw_<timestamp>.log

Notes:
- This stage performs no cleaning, filtering, or aggregation
- Ensures downstream stages receive validated, period‑correct inputs
AI Assistance:
    This script was drafted with support from Microsoft Copilot. All conceptual
    framing, methodological design, and analytical and interpretive decisions
    were made by the author. The author reviewed, edited, and validated all code.
"""

SCRIPT_VERSION = "v4.7 (2026-03-22)"

# ============================================================
# Setup
# ============================================================

import os
import logging
import pandas as pd
from tqdm import tqdm
from datetime import datetime

from tools.periods import extract_period

RAW_DIR = "data_raw/Monthly"
OUTPUT_DIR = "data_ingested"
DIAG_DIR = "diagnostics"
LOG_DIR = "logs"

os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(DIAG_DIR, exist_ok=True)
os.makedirs(LOG_DIR, exist_ok=True)

timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
LOG_FILE = os.path.join(LOG_DIR, f"stage00_ingest_raw_{timestamp}.log")

# Reset handlers
for h in logging.root.handlers[:]:
    logging.root.removeHandler(h)

logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    encoding="utf-8"
)

logging.info("=== Starting Raw Ingestion Pipeline ===")
logging.info(f"Script version: {SCRIPT_VERSION}")

# ============================================================
# Loader (lean)
# ============================================================

def load_raw_file(path: str):
    """
    Robust CSV loader for Comtrade-style files.
    Tries UTF-8-SIG first, falls back to Latin-1 if needed.
    """

    try:
        return pd.read_csv(
            path,
            sep=",",
            quotechar='"',
            engine="python",
            encoding="utf-8-sig",
            index_col=False
        )
    except UnicodeDecodeError:
        logging.warning(f"UTF-8 decode failed for {path}, falling back to Latin-1")

        return pd.read_csv(
            path,
            sep=",",
            quotechar='"',
            engine="python",
            encoding="latin-1",
            index_col=False
        )

# ============================================================
# Column Standardization
# ============================================================

KEEP_COLS = [
    "reporterISO",
    "partnerISO",
    "partner2ISO",
    "qty",
    "isQtyEstimated",
    "qtyUnitAbbr",
    "cmdCode",
    "flowCode",
]

def standardize_columns(df: pd.DataFrame) -> pd.DataFrame:
    # Enforce ingestion schema: ensure all required columns exist

    for col in KEEP_COLS:
        if col not in df.columns:
            df[col] = None
    return df[KEEP_COLS]

def normalize_iso(code):
    if pd.isna(code):
        return None
    code = str(code).strip().upper()
    return None if code in ["", "NONE", "NAN"] else code

# ============================================================
# Ingestion Logic (v4.7 — fail-soft, skip file, print-to-screen)
# ============================================================

def ingest_file(path: str, period: str):
    df = load_raw_file(path)
    if df is None or df.empty:
        logging.warning(f"Loaded empty dataframe from {path}")
        print(f"[WARN] Loaded empty dataframe from {path}")
        return None, None

    # ------------------------------------------------------------
    # Validate that file contents match the file's period (v4.7)
    # ------------------------------------------------------------
    validation_failed = False

    try:
        year_str, month_str = period.split("-")
        year_expected = int(year_str)
        month_expected = int(month_str)
        period_expected = int(year_str + month_str)
    except Exception:
        msg = f"{path}: Invalid period format from filename: {period}"
        logging.error(msg)
        print(f"[ERROR] {msg}")
        return None, None

    # Validate refYear BEFORE dropping columns
    if "refYear" in df.columns:
        years = df["refYear"].dropna().astype(int).unique()
        if len(years) > 1:
            msg = f"{path} contains multiple refYear values: {years}"
            logging.error(msg)
            print(f"[ERROR] {msg}")
            validation_failed = True
        elif len(years) == 1 and years[0] != year_expected:
            msg = f"{path} refYear mismatch: file={year_expected}, data={years[0]}"
            logging.error(msg)
            print(f"[ERROR] {msg}")
            validation_failed = True

    # Validate refMonth BEFORE dropping columns
    if "refMonth" in df.columns:
        months = df["refMonth"].dropna().astype(int).unique()
        if len(months) > 1:
            msg = f"{path} contains multiple refMonth values: {months}"
            logging.error(msg)
            print(f"[ERROR] {msg}")
            validation_failed = True
        elif len(months) == 1 and months[0] != month_expected:
            msg = f"{path} refMonth mismatch: file={month_expected}, data={months[0]}"
            logging.error(msg)
            print(f"[ERROR] {msg}")
            validation_failed = True

    # Validate period column (YYYYMM) BEFORE dropping columns
    if "period" in df.columns:
        periods = df["period"].dropna().astype(int).unique()
        if len(periods) > 1:
            msg = f"{path} contains multiple period values: {periods}"
            logging.error(msg)
            print(f"[ERROR] {msg}")
            validation_failed = True
        elif len(periods) == 1 and periods[0] != period_expected:
            msg = f"{path} period mismatch: file={period_expected}, data={periods[0]}"
            logging.error(msg)
            print(f"[ERROR] {msg}")
            validation_failed = True

    # If any validation failed, skip ingestion
    if validation_failed:
        msg = f"{path}: validation failed — skipping file"
        logging.error(msg)
        print(f"[SKIP] {msg}")
        return None, None

    # ------------------------------------------------------------
    # Now it is safe to standardize columns
    # ------------------------------------------------------------
    df = standardize_columns(df)

    # Normalize ISO codes
    df["partnerISO"] = df["partnerISO"].apply(normalize_iso)
    df["reporterISO"] = df["reporterISO"].apply(normalize_iso)
    df["partner2ISO"] = df["partner2ISO"].apply(normalize_iso)

    # Convert qty
    df["qty"] = pd.to_numeric(df["qty"], errors="coerce")

    # Assign canonical period from filename
    df["period"] = period

    # Export canonical file
    out_path = os.path.join(OUTPUT_DIR, f"raw_{period}.csv")
    df.to_csv(out_path, index=False)

    # Ingestion diagnostics
    summary = {
        "period": period,
        "rows_raw": len(df),
        "missing_partnerISO": df["partnerISO"].isna().sum(),
        "missing_reporterISO": df["reporterISO"].isna().sum(),
        "missing_qty": df["qty"].isna().sum(),
        "unique_exporters": df["partnerISO"].nunique(),
        "unique_importers": df["reporterISO"].nunique(),
    }

    return df, summary
    
# ============================================================
# Main Loop
# ============================================================

def main():
    summary_rows = []

    file_paths = [os.path.join(RAW_DIR, f)
        for f in os.listdir(RAW_DIR)
        if f.endswith(".csv")
    ]
    
    for path in tqdm(file_paths, desc="Ingesting monthly raw files"):
        file = os.path.basename(path)

        # ============================================================
        # Extract period from filename (simple extractor)
        # ============================================================
        
        try:
            period = extract_period(file)   # <-- using the original extractor
        except ValueError as e:
            logging.error(f"{path}: {e}")
            continue  # skip this file
        
        # Parse expected year/month for downstream validation
        try:
            year_str, month_str = period.split("-")
            year_expected = int(year_str)
            month_expected = int(month_str)
            period_expected = int(year_str + month_str)
        except Exception:
            logging.error(f"{path}: Invalid period format extracted from filename: {period}")
            continue  # skip this file
        
        # Ingest the file using the extracted period
        df, summary = ingest_file(path, period)
        if df is None:
            continue  # skip invalid file
        summary_rows.append(summary)

    if summary_rows:
        summary_df = pd.DataFrame(summary_rows)
        summary_df.to_csv(
            os.path.join(DIAG_DIR, "raw_ingestion_summary.csv"),
            index=False
        )

        logging.info("=== Raw Ingestion Summary ===")
        logging.info(f"Periods ingested: {summary_df['period'].tolist()}")
        logging.info(f"Total rows: {summary_df['rows_raw'].sum()}")

    logging.info("=== Raw Ingestion Pipeline Complete ===")


if __name__ == "__main__":
    main()