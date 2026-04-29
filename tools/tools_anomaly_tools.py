"""
anomaly_tools.py — v4.2 (2026-03-16)
Purpose:
Load, filter, and summarize anomaly diagnostics produced during Stage 01
(01_clean_edges), supporting pipeline‑level data‑quality validation.

Responsibilities:
- Load diagnostics for a single period or all periods
- Provide anomaly‑type filters:
    • quantity anomalies
    • routing‑only duplicates
    • partner2ISO variant detection
- Summarize anomaly counts for:
    • pipeline integrity checks
    • break‑detection QA
    • governance‑signature validation
- Support period parsing via extract_period()

Used by:
- Stage 01 cleaning (diagnostic generation)
- Stage 04 validation (indirectly via pipeline_checks)
- tools.pipeline_checks (anomaly threshold checks)

Dependencies:
- tools.periods.extract_period
- pandas
- os
- ast.literal_eval

Notes:
- Operates on diagnostic CSVs, not graphs.
- partner2ISO_values is parsed safely using literal_eval.
- AI Assistance:
    This script was drafted with support from Microsoft Copilot. All conceptual
    framing, methodological design, and analytical and interpretive decisions
    were made by the author. The author reviewed, edited, and validated all code.
"""


from typing import Dict, Any
import os
import pandas as pd
from ast import literal_eval
from tools.periods import extract_period


# ============================================================
# Loading Diagnostics
# ============================================================

def load_diagnostics(period: str, diag_dir: str = "diagnostics") -> pd.DataFrame:
    """
    Load anomaly diagnostics for a specific period (YYYY or YYYY-MM).

    Raises:
        FileNotFoundError if the diagnostics file is missing.
    """
    period = extract_period(period)
    path = f"{diag_dir}/edges_diagnostics_{period}.csv"
    return pd.read_csv(path)


def load_all_diagnostics(diag_dir: str = "diagnostics") -> pd.DataFrame:
    """
    Load all anomaly diagnostics across all periods.

    This version does NOT rely on a master file.
    It dynamically loads every file matching:
        edges_diagnostics_<period>.csv

    Returns:
        A pandas DataFrame with all periods combined.
    """
    frames = []

    for file in os.listdir(diag_dir):
        if file.startswith("edges_diagnostics_") and file.endswith(".csv"):
            path = os.path.join(diag_dir, file)
            try:
                df = pd.read_csv(path)
                frames.append(df)
            except Exception:
                continue

    if not frames:
        raise FileNotFoundError("No anomaly diagnostics found in diagnostics/")

    return pd.concat(frames, ignore_index=True)


# ============================================================
# Anomaly Filters
# ============================================================

def qty_anomalies(df: pd.DataFrame) -> pd.DataFrame:
    """Return rows flagged as quantity anomalies."""
    return df[df["anomaly_qty"] == True]


def routing_only(df: pd.DataFrame) -> pd.DataFrame:
    """Return rows flagged as routing-only duplicates."""
    return df[df["routing_only"] == True]


def partner2_variants(df: pd.DataFrame) -> pd.DataFrame:
    """
    Return rows where partner2ISO has multiple variants.
    partner2ISO_values is stored as a stringified list.
    literal_eval is used for safety (no eval).
    """
    return df[df["partner2ISO_values"].apply(
        lambda x: len(literal_eval(x)) > 1
    )]


# ============================================================
# Summary Utilities
# ============================================================

def anomaly_summary(df: pd.DataFrame) -> Dict[str, Any]:
    """
    Summarize anomaly counts for a single period.
    """
    return {
        "qty_anomalies": int((df["anomaly_qty"] == True).sum()),
        "routing_only": int((df["routing_only"] == True).sum()),
        "partner2_variants": int(
            df["partner2ISO_values"].apply(lambda x: len(literal_eval(x)) > 1).sum()
        ),
        "total_rows": len(df),
    }


def compare_anomalies_across_periods(df_all: pd.DataFrame) -> pd.DataFrame:
    """
    Group anomaly counts by period (year or month).
    """
    if "period" not in df_all.columns:
        raise ValueError("Diagnostics table must contain a 'period' column.")

    grouped = df_all.groupby("period").apply(
        lambda g: pd.Series({
            "qty_anomalies": int((g["anomaly_qty"] == True).sum()),
            "routing_only": int((g["routing_only"] == True).sum()),
            "partner2_variants": int(
                g["partner2ISO_values"].apply(lambda x: len(literal_eval(x)) > 1).sum()
            ),
        })
    )

    return grouped.reset_index()