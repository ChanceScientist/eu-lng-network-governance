"""
io_utils.py — v4.0 (2026-03-15)
Purpose:
Centralize low‑level I/O utilities for the LNG network pipeline, providing
deterministic file‑integrity hashing and safe CSV loading with consistent
error‑handling semantics.

Responsibilities:
- file_checksum(path):
    • compute deterministic MD5 checksums for reproducibility diagnostics
    • support pipeline integrity checks and advisor‑ready transparency
- load_csv(path, required=True):
    • load CSVs with explicit required/optional behavior
    • raise errors for missing required files
    • log warnings and return None for optional files
    • ensure consistent CSV‑loading behavior across all stages

Used by:
- Stage 01–03 (checksum)
- Stage 07 (safe CSV loading)

Dependencies:
- Standard library: os, hashlib, logging
- pandas

Notes:
- This module defines the canonical CSV‑loading behavior for the pipeline.
- All file‑integrity checks should use file_checksum() for reproducibility.
- AI Assistance:
    This script was drafted with support from Microsoft Copilot. All conceptual
    framing, methodological design, and analytical and interpretive decisions
    were made by the author. The author reviewed, edited, and validated all code.
"""


from typing import Optional
import os
import hashlib
import pandas as pd
import logging


# ============================================================
# File Integrity
# ============================================================

def file_checksum(path: str) -> str:
    """
    Compute an MD5 checksum for a file.

    Used for:
        - reproducibility diagnostics
        - pipeline integrity checks
        - advisor-ready transparency

    Args:
        path:
            Path to the file.

    Returns:
        Hexadecimal MD5 checksum string.

    Raises:
        FileNotFoundError if the file does not exist.
    """
    if not os.path.exists(path):
        raise FileNotFoundError(f"Cannot compute checksum; file not found: {path}")

    with open(path, "rb") as f:
        return hashlib.md5(f.read()).hexdigest()


# ============================================================
# Safe CSV Loading
# ============================================================

def load_csv(path: str, required: bool = True) -> Optional[pd.DataFrame]:
    """
    Load a CSV file safely with optional required/optional semantics.

    Args:
        path:
            Path to the CSV file.
        required:
            If True:
                - missing file triggers FileNotFoundError
            If False:
                - missing file logs a warning and returns None

    Returns:
        A pandas DataFrame if the file exists.
        None if the file is optional and missing.

    Notes:
        - This function avoids silent failures and ensures consistent error handling.
    """
    if not os.path.exists(path):
        msg = f"Missing required file: {path}"
        if required:
            logging.error(msg)
            raise FileNotFoundError(msg)
        else:
            logging.warning(msg)
            return None

    return pd.read_csv(path)