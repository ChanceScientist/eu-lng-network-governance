"""
constants.py — v4.0 (2026-03-15)
Purpose:
Provide a centralized, authoritative definition of the fixed 47‑country
node universe used throughout the EU–LNG network pipeline. Ensures structural
comparability across all periods, stages, and analyses.

Responsibilities:
- Define COUNTRIES:
    • EU‑27 Member States
    • 20 external LNG suppliers
- Maintain alphabetized ordering for readability and reproducibility
- Serve as the unified reference list for:
    • graph construction (Stage 02)
    • normalization (Stage 03)
    • validation (Stage 04)
    • break detection (Stage 05)
    • structural and temporal metrics (Stage 06)
    • governance integration and community analysis (Stage 07)
    • attribution signatures and indicators

Used by:
- tools.pipeline_checks
- Stage 03 normalization (node-universe enforcement)

Notes:
- COUNTRIES is the canonical node set; all graph‑based operations assume
  this fixed universe for consistent panel construction.
- AI Assistance:
    This script was drafted with support from Microsoft Copilot. All conceptual
    framing, methodological design, and analytical and interpretive decisions
    were made by the author. The author reviewed, edited, and validated all code.
"""


# Fixed node universe for structural comparability across periods.
# Alphabetized for readability and maintainability.
COUNTRIES = [
    # EU‑27
    "AUT","BEL","BGR","HRV","CYP","CZE","DNK","EST","FIN","FRA","DEU","GRC",
    "HUN","IRL","ITA","LVA","LTU","LUX","MLT","NLD","POL","PRT","ROU","SVK",
    "SVN","ESP","SWE",

    # External LNG suppliers (20)
    "AGO","ARE","ARG","AUS","CMR","DZA","EGY","GBR","GNQ","IDN","MOZ","NGA",
    "NOR","OMN","PER","PNG","QAT","RUS","TTO","USA",
]