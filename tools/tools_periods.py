"""
periods.py — v4.0 (2026-03-15)
Purpose:
Centralized temporal utilities for the LNG network pipeline, providing a single,
authoritative source for period validation, parsing, arithmetic, comparison, and
chronological ordering across all stages.

Supported formats:
- Yearly periods:  "YYYY"
- Monthly periods: "YYYY-MM"

Responsibilities:
- Validate and classify period strings (year vs month)
- Extract periods from filenames and arbitrary text
- Perform temporal arithmetic:
    • previous/next month
    • previous/next year
    • previous/next period (type‑aware)
- Provide seasonal comparison helpers:
    • previous_year(), next_year()
- Provide related_periods() for break detection and reporter panels
- Sort and group periods chronologically for mixed YYYY / YYYY‑MM sequences

Used by:
- Stage 02 (graph construction)
- Stage 04 (pipeline validation)
- Stage 05 (break detection)
- Stage 06 (temporal metrics)
- Stage 07 (governance integration, transitions, CSCI, timeseries)
- Attribution layer (signatures, indicators, scoring)
- tools.graph_loader
- tools.anomaly_tools
- tools.pipeline_checks
- stage07_helpers

Dependencies:
- Standard library: re, datetime
- dateutil.relativedelta

Notes:
- This module defines the canonical temporal logic for the entire pipeline.
- All period handling in downstream modules should rely on these utilities.
- AI Assistance:
    This script was drafted with support from Microsoft Copilot. All conceptual
    framing, methodological design, and analytical and interpretive decisions
    were made by the author. The author reviewed, edited, and validated all code.
"""


from typing import List, Dict
import re
from datetime import datetime
from dateutil.relativedelta import relativedelta


# ============================================================
# Validation & Type Detection
# ============================================================

YEAR_PATTERN = re.compile(r"^\d{4}$")
MONTH_PATTERN = re.compile(r"^\d{4}-\d{2}$")


def is_year(period: str) -> bool:
    """Return True if the period is a valid YYYY string."""
    return bool(YEAR_PATTERN.fullmatch(period))


def is_month(period: str) -> bool:
    """Return True if the period is a valid YYYY-MM string."""
    return bool(MONTH_PATTERN.fullmatch(period))


def period_type(period: str) -> str:
    """Return 'year' or 'month' depending on the period format."""
    if is_month(period):
        return "month"
    if is_year(period):
        return "year"
    raise ValueError(f"Invalid period format: {period!r}")


def validate_period(period: str) -> str:
    """Ensure the period is valid; return it unchanged if so."""
    if is_year(period) or is_month(period):
        return period
    raise ValueError(f"Invalid period: {period!r}")

        
# ============================================================
# Parsing from Filenames
# ============================================================

def extract_period(text: str) -> str:
    """
    Extract a period (YYYY or YYYY-MM) from a filename or string.

    Monthly patterns take precedence over yearly patterns.

    Raises:
        ValueError if no valid period is found.
    """
    m = re.search(r"(\d{4})-(\d{2})", text)
    if m:
        return f"{m.group(1)}-{m.group(2)}"

    y = re.search(r"(\d{4})", text)
    if y:
        return y.group(1)

    raise ValueError(f"Could not extract period from: {text!r}")

    
# ============================================================
# Period Arithmetic
# ============================================================

def previous_period(period: str) -> str:
    """Return the previous month or previous year, depending on type."""
    period = validate_period(period)

    if is_month(period):
        dt = datetime.strptime(period, "%Y-%m")
        return (dt - relativedelta(months=1)).strftime("%Y-%m")

    dt = datetime.strptime(period, "%Y")
    return (dt - relativedelta(years=1)).strftime("%Y")


def next_period(period: str) -> str:
    """Return the next month or next year, depending on type."""
    period = validate_period(period)

    if is_month(period):
        dt = datetime.strptime(period, "%Y-%m")
        return (dt + relativedelta(months=1)).strftime("%Y-%m")

    dt = datetime.strptime(period, "%Y")
    return (dt + relativedelta(years=1)).strftime("%Y")


def previous_month(period: str) -> str:
    """Return the previous month (YYYY-MM)."""
    if not is_month(period):
        raise ValueError("previous_month() requires a YYYY-MM period")
    dt = datetime.strptime(period, "%Y-%m")
    return (dt - relativedelta(months=1)).strftime("%Y-%m")


def next_month(period: str) -> str:
    """Return the next month (YYYY-MM)."""
    if not is_month(period):
        raise ValueError("next_month() requires a YYYY-MM period")
    dt = datetime.strptime(period, "%Y-%m")
    return (dt + relativedelta(months=1)).strftime("%Y-%m")


def previous_year(period: str) -> str:
    """
    Return the same month in the previous year (if monthly),
    or the previous year (if yearly).
    """
    period = validate_period(period)

    if is_month(period):
        dt = datetime.strptime(period, "%Y-%m")
        return (dt - relativedelta(years=1)).strftime("%Y-%m")

    dt = datetime.strptime(period, "%Y")
    return (dt - relativedelta(years=1)).strftime("%Y")


def next_year(period: str) -> str:
    """
    Return the same month next year (if monthly),
    or the next year (if yearly).
    """
    period = validate_period(period)

    if is_month(period):
        dt = datetime.strptime(period, "%Y-%m")
        return (dt + relativedelta(years=1)).strftime("%Y-%m")

    dt = datetime.strptime(period, "%Y")
    return (dt + relativedelta(years=1)).strftime("%Y")


# ============================================================
# Related Periods (for Break Detection, Reporter Panels)
# ============================================================

def related_periods(period: str) -> Dict[str, str]:
    """
    Return a dictionary of related periods for temporal comparison.

    Always includes:
        - prev_period
        - next_period

    If monthly, also includes:
        - prev_month
        - next_month
        - prev_year
        - next_year
    """
    period = validate_period(period)

    result = {
        "prev_period": previous_period(period),
        "next_period": next_period(period),
    }

    if is_month(period):
        result.update({
            "prev_month": previous_month(period),
            "next_month": next_month(period),
            "prev_year": previous_year(period),
            "next_year": next_year(period),
        })

    return result


# ============================================================
# Sorting & Grouping
# ============================================================

def sort_periods(periods: List[str]) -> List[str]:
    """Sort periods chronologically, handling YYYY and YYYY-MM."""
    def key(p: str):
        if is_month(p):
            y, m = p.split("-")
            return (int(y), int(m))
        return (int(p), 0)

    return sorted(periods, key=key)


def group_by_year(periods: List[str]) -> Dict[str, List[str]]:
    """Group periods by their YYYY prefix."""
    groups: Dict[str, List[str]] = {}
    for p in periods:
        year = p[:4]
        groups.setdefault(year, []).append(p)
    return groups