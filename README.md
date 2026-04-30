# README

**DOI:** https://doi.org/10.5281/zenodo.19924877

## 1. Project Overview
This repository contains a full computational pipeline for constructing, validating, and interpreting monthly EU‑27 LNG trade networks using UN Comtrade data (HS 271111). The pipeline ingests raw monthly CSVs, standardizes and cleans flows, builds directed weighted graphs, normalizes structural metrics, detects structural breaks, and produces governance‑oriented summaries and visualizations.

### What this framework enables
This pipeline provides a reproducible framework for evaluating how governance mechanisms shape complex systems by quantifying structural evolution and contextualizing those patterns with publicly available regulatory and market evidence. It enables analysts to identify governance‑relevant structural shifts—such as changes in cohesion, concentration, continuity, and community prominence—without inferring intent or causality.

Applied to the EU LNG network, the framework shows how system‑scale interventions (e.g., diversification measures) and corridor‑scale interventions (e.g., storage mandates) leave distinct structural imprints. Because the method relies on structural metrics and temporal comparability, it can be extended to other governance‑relevant systems that can be represented as temporal networks, including maritime shipping, waste‑flow systems, and cross‑border energy infrastructures.

### What the outputs represent
The pipeline produces normalized graphs, break‑detection diagnostics, period‑level summaries, community transitions, governance metrics, CSCI stability indicators, and a suite of visualizations. These outputs collectively form a governance‑signature framework for interpreting structural change in energy trade networks.

### AI‑Assisted Code Generation
All Python scripts in this repository were drafted with assistance from Microsoft Copilot. All conceptual framing, methodological design, and analytical and interpretive decisions were made by the author. The author reviewed, edited, and validated all code.

---

## 2. Pipeline Execution Order

- stage00_ingest_raw.py
- stage01_clean_edges.py
- stage02_build_graphs.py
- stage03_normalize_network.py
- stage04_validate_pipeline.py
- stage05_detect_breaks.py
- stage06_period_summary.py
- stage07_network_interpretation.py
- stage07_transitions_full.py
- stage07_csci.py
- stage07_timeseries.py
- stage07_visuals_per_period.py
- extract_signatures.py
- attribution_indicator_range.py
- attribution_scoring_mechanisms.py

### Supporting Tools
The `tools/` directory contains helper modules used throughout the pipeline
(e.g., period extraction, graph loading, structural metrics, integrity checks,
and attribution utilities). These scripts are imported by the main pipeline
stages and are required for full reproducibility, but they are not intended to
be run directly.

---

## 3. Installation / Environment Setup

pip install -r requirements.txt

---

## 4. Data Requirements
The pipeline ingests monthly UN Comtrade CSV files from `data_raw/Monthly`.

Filenames **must contain a monthly period in `YYYY-MM` format** (e.g., `2015-01`).  
The ingestion stage extracts this substring using a strict pattern match and validates it against the file contents (`refYear`, `refMonth`, and `period` columns). Files without a valid `YYYY-MM` substring are skipped.

**Example filename:**

Data_EU-LNG-EnergyShift_2015-01_LNG-Imports.csv

Additional numbers or text in the filename are allowed as long as the `YYYY-MM` pattern appears exactly once and corresponds to the file’s actual month.

---

## 5. Outputs
The pipeline produces a set of validated, normalized, and analysis‑ready outputs:

- **Canonical monthly ingested files** (`raw_YYYY-MM.csv`)
- **Cleaned and filtered edge lists**
- **Monthly and yearly normalized graphs**
- **Break‑detection diagnostics** (flow surges/collapses, density shifts, edge changes, role diversification)
- **Period‑level summaries** (structural metrics, flow metrics, governance indicators)
- **Community transitions** (monthly and yearly)
- **CSCI stability indicators** (Community Stability & Change Index)
- **Time‑series metrics** (centrality, density, flow, community size)
- **Visualizations** (node‑link diagrams, transitions, temporal metrics)
- **Structural signatures** (complete structural representation of each period)
- **Governance signatures** (governance‑relevant structural summaries)
- **Attribution indicators** (standardized evaluative indicators derived from signatures)
- **Attribution scores** (alignment‑based assessments integrating structural signatures, governance signatures, and external evidence)

These outputs collectively support a reproducible framework for evaluating governance‑relevant structural evolution in LNG trade networks.

---

## 6. Developer Utilities (Optional)
The `/tests` directory contains optional scripts used during development to tune thresholds, visualization parameters, and configuration settings for Stage 05 and Stage 07. These scripts are not required to run the pipeline but are included for transparency and reproducibility.

---

## 7. Citation & Acknowledgements

### Data Source
**UN Comtrade Database**  
United Nations. (n.d.). *UN Comtrade Database: Trade Data*. Retrieved March 25, 2026, from  
https://comtradeplus.un.org/TradeFlow

### Library Citations
This project uses several open‑source libraries whose authors request or recommend citation in academic work:

**Louvain community detection**  
Blondel, V. D., Guillaume, J.-L., Lambiotte, R., & Lefebvre, R. (2008).  
*Fast unfolding of communities in large networks.* Journal of Statistical Mechanics: Theory and Experiment, 2008(10), P10008.

**ForceAtlas2 layout**  
Jacomy, M., Venturini, T., Heymann, S., & Bastian, M. (2014).  
*ForceAtlas2, a continuous graph layout algorithm for handy network visualization designed for the Gephi software.* PLoS ONE, 9(6), e98679.

**NetworkX**  
Hagberg, A., Swart, P., & S Chult, D. (2008).  
*Exploring network structure, dynamics, and function using NetworkX.*  
In Proceedings of the 7th Python in Science Conference (SciPy2008).


### Institutional Acknowledgement
This work was completed as part of the author's graduate research in the  
School of Complex Adaptive Systems at Arizona State University.

---

## 8. License
MIT License.
