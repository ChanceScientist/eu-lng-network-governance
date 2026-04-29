"""
stage04_validate_pipeline.py — v4.3 (2026-03-22)
Purpose:
Validate the structural and temporal integrity of the normalized EU–LNG
network, ensuring that monthly and yearly graphs are complete, consistent,
and aligned with ingestion results before downstream analysis.

Inputs:
- Normalized graphs:
    graphs_normalized/graph_<YYYY-MM>_normalized.gpickle
    graphs_normalized/graph_<YYYY>_normalized.gpickle
- Ingestion summary:
    diagnostics/raw_ingestion_summary.csv
- Optional anomaly diagnostics:
    diagnostics/edges_diagnostics_all_periods.csv
    or individual per-period diagnostics
- Utility modules:
    load_all_graphs(), pipeline_check(), load_all_diagnostics(),
    compare_anomalies_across_periods(), COUNTRIES

Responsibilities:
- Load all normalized monthly and yearly graphs
- Validate structural integrity:
    - fixed 47-node universe (COUNTRIES)
    - no extraneous or missing nodes
    - no negative weights or empty graphs
    - zero-flow and zero-edge warnings
- Validate temporal integrity:
    - all normalized periods must appear in ingestion summary
    - no normalized graph may exist for a failed-ingestion period
    - no ingested period may be missing a normalized graph
- Run pipeline-level structural checks via pipeline_check()
- Optionally validate monthly continuity and anomaly thresholds
- Integrate anomaly diagnostics when available
- Produce consolidated validation summaries and warnings

Outputs:
- Validation summary:
    diagnostics/pipeline_validation_summary.csv
- Warnings and anomaly context:
    diagnostics/pipeline_validation_warnings.txt
- Log file:
    logs/stage04_validate_pipeline_<timestamp>.log

Notes:
- This script does not modify graphs
- Ensures the full graph sequence is structurally aligned and temporally correct
- Required before break detection, visualization, and governance interpretation
- AI Assistance:
    This script was drafted with support from Microsoft Copilot. All conceptual
    framing, methodological design, and analytical and interpretive decisions
    were made by the author. The author reviewed, edited, and validated all code.
"""

SCRIPT_VERSION = "v4.3 (2026-03-22)"

# ============================================================
# Setup
# ============================================================

import os
import logging
import pandas as pd
from datetime import datetime

from tools.constants import COUNTRIES
from tools.graph_loader import load_all_graphs
from tools.pipeline_checks import pipeline_check
from tools.anomaly_tools import load_all_diagnostics, compare_anomalies_across_periods

DIAG_DIR = "diagnostics"
LOG_DIR = "logs"

os.makedirs(DIAG_DIR, exist_ok=True)
os.makedirs(LOG_DIR, exist_ok=True)

timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
LOG_FILE = os.path.join(LOG_DIR, f"stage04_validate_pipeline_{timestamp}.log")

# Reset handlers
for h in logging.root.handlers[:]:
    logging.root.removeHandler(h)

logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    encoding="utf-8"
)

logging.info("=== Starting Pipeline Validation ===")
logging.info(f"Script version: {SCRIPT_VERSION}")


# ============================================================
# Node Universe Check
# ============================================================

def check_node_universe(graphs: dict, level: str) -> list:
    errors = []
    for period, G in graphs.items():
        nodes = set(G.nodes())
        missing = set(COUNTRIES) - nodes
        extra = nodes - set(COUNTRIES)

        if missing:
            errors.append(f"[{level}] {period}: missing nodes: {sorted(missing)}")
        if extra:
            errors.append(f"[{level}] {period}: extraneous nodes: {sorted(extra)}")

    return errors


# ============================================================
# Main Validation Logic
# ============================================================

def main(
    require_monthly_continuity: bool = True,
    anomaly_threshold: int | None = None,
) -> None:

    # --------------------------------------------------------
    # Load all normalized graphs
    # --------------------------------------------------------
    print("Loading normalized graphs...")
    logging.info("Loading all normalized graphs")

    graphs = load_all_graphs(normalized=True)

    monthly_graphs = {p: G for p, G in graphs.items() if len(p) == 7}
    yearly_graphs  = {p: G for p, G in graphs.items() if len(p) == 4}

    print(f"Loaded {len(monthly_graphs)} monthly graphs, {len(yearly_graphs)} yearly graphs.")
    logging.info(f"Loaded {len(monthly_graphs)} monthly graphs")
    logging.info(f"Loaded {len(yearly_graphs)} yearly graphs")

    # --------------------------------------------------------
    # Run integrity checks
    # --------------------------------------------------------
    print("Running integrity checks...")
    monthly_report = None
    yearly_report = None

    if monthly_graphs:
        monthly_report = pipeline_check(
            monthly_graphs,
            require_monthly_continuity=require_monthly_continuity,
            anomaly_threshold=anomaly_threshold,
        )
    else:
        logging.warning("No monthly graphs found — skipping monthly validation.")

    if yearly_graphs:
        yearly_report = pipeline_check(
            yearly_graphs,
            require_monthly_continuity=False,
            anomaly_threshold=anomaly_threshold,
        )
    else:
        logging.warning("No yearly graphs found — skipping yearly validation.")

    print("Integrity checks complete.")

    # --------------------------------------------------------
    # Explicit node-universe validation
    # --------------------------------------------------------
    node_errors_monthly = check_node_universe(monthly_graphs, "MONTHLY")
    node_errors_yearly  = check_node_universe(yearly_graphs, "YEARLY")

    # --------------------------------------------------------
    # Temporal integrity check (v4.3)
    # --------------------------------------------------------
    temporal_errors = []

    ingestion_summary_path = os.path.join("diagnostics", "raw_ingestion_summary.csv")
    if os.path.exists(ingestion_summary_path):
        try:
            df_ingest = pd.read_csv(ingestion_summary_path)

            # Periods that were successfully ingested
            ingested_periods = set(df_ingest["period"].astype(str).unique())

            # Periods for which normalized graphs exist
            normalized_periods = set(monthly_graphs.keys()) | set(yearly_graphs.keys())

            # Detect mismatches
            missing_from_ingest = normalized_periods - ingested_periods
            missing_from_normalized = ingested_periods - normalized_periods

            if missing_from_ingest:
                temporal_errors.append(
                    f"[TEMPORAL][ERROR] Normalized graphs exist for periods not in ingestion summary: {sorted(missing_from_ingest)}"
                )

            if missing_from_normalized:
                temporal_errors.append(
                    f"[TEMPORAL][WARNING] Periods ingested but no normalized graph produced: {sorted(missing_from_normalized)}"
                )

        except Exception as e:
            temporal_errors.append(f"[TEMPORAL][ERROR] Failed to validate temporal integrity: {e}")
    else:
        temporal_errors.append("[TEMPORAL][WARNING] No raw_ingestion_summary.csv found — cannot validate temporal integrity.")
    
    # --------------------------------------------------------
    # Anomaly context (optional)
    # --------------------------------------------------------
    print("Loading anomaly diagnostics (if available)...")
    anomaly_summary_df = None

    try:
        diagnostics_unified_path = os.path.join(DIAG_DIR, "edges_diagnostics_all_periods.csv")

        if os.path.exists(diagnostics_unified_path):
            df_all = pd.read_csv(diagnostics_unified_path)
            logging.info("Loaded anomaly diagnostics from edges_diagnostics_all_periods.csv")
        else:
            df_all = load_all_diagnostics()
            logging.info("Loaded anomaly diagnostics from individual period files")

        anomaly_summary_df = compare_anomalies_across_periods(df_all)

    except FileNotFoundError:
        logging.info("No anomaly diagnostics found — skipping anomaly summary.")
    except Exception as e:
        logging.warning(f"Unexpected anomaly diagnostics error: {e}")

    # --------------------------------------------------------
    # Persist validation summary
    # --------------------------------------------------------
    print("Writing validation summary...")
    rows = []

    if monthly_report:
        for period, metrics in monthly_report["structural_metrics"].items():
            rows.append({"period": period, "level": "monthly", **metrics})

    if yearly_report:
        for period, metrics in yearly_report["structural_metrics"].items():
            rows.append({"period": period, "level": "yearly", **metrics})

    summary_df = pd.DataFrame(rows)
    summary_path = os.path.join(DIAG_DIR, "pipeline_validation_summary.csv")
    summary_df.to_csv(summary_path, index=False)

    # --------------------------------------------------------
    # Persist warnings and errors
    # --------------------------------------------------------
    print("Writing warnings and anomaly summary...")
    warnings_errors = []

    if monthly_report:
        warnings_errors += [f"[MONTHLY][ERROR] {m}" for m in monthly_report["errors"]]
        warnings_errors += [f"[MONTHLY][WARNING] {m}" for m in monthly_report["warnings"]]

    if yearly_report:
        warnings_errors += [f"[YEARLY][ERROR] {m}" for m in yearly_report["errors"]]
        warnings_errors += [f"[YEARLY][WARNING] {m}" for m in yearly_report["warnings"]]

    warnings_errors.extend(node_errors_monthly)
    warnings_errors.extend(node_errors_yearly)

    warnings_errors.extend(temporal_errors)

    if anomaly_summary_df is not None:
        warnings_errors.append("\n[ANOMALY_SUMMARY]")
        warnings_errors.append(anomaly_summary_df.to_csv(index=False))

    warnings_path = os.path.join(DIAG_DIR, "pipeline_validation_warnings.txt")
    with open(warnings_path, "w", encoding="utf-8") as f:
        for line in warnings_errors:
            f.write(str(line) + "\n")

    print("04_validate_pipeline.py complete.")
    logging.info("=== Pipeline Validation Complete ===")


if __name__ == "__main__":
    main()