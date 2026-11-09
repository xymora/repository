# Enterprise Energy Metadata & Lineage Framework
**Sector:** Energy & Utilities (CENACE - Mexico)  
**Maturity Level:** High (Level 4 - Managed & Measurable)

## Executive Summary
This project implements a robust Data Governance practice for Power Market Data. It ensures that critical information assets, such as Local Marginal Prices (LMP), are cataloged, traceable, and ready for executive decision-making through automated lineage and metadata documentation.

## Governance Pillars
* **Metadata Cataloging:** Automated generation of technical data dictionaries.
* **Data Lineage:** Full traceability from the CENACE source to the final Dashboard.
* **Schema Enforcement:** Ensuring data integrity regardless of source file fluctuations.
* **Auditability:** Standardized execution logs for compliance monitoring.

## Setup & Execution
1. Create a virtual environment: `python -m venv .venv`
2. Install dependencies: `pip install -r requirements.txt`
3. Run the framework: `python governance_framework.py`

## Deliverables
- **Data Dictionary:** Console-printed technical metadata.
- **Interactive Dashboard:** Auto-generated HTML report (`governance_report.html`) featuring 4 high-level analytics charts.
