# Enterprise Data Lineage & Integrity Framework
## Data Governance & Audit Trail Practice (2021 Standard)

### Overview
This project implements a high-level Data Governance framework focused on **Technical Lineage** and **Audit Trails**. It demonstrates the lifecycle of regulated data from raw ingestion to a "Gold" business-ready zone, ensuring every transformation is logged with cryptographic integrity and metadata validation.

### Key Governance Pillars
* **Data Provenance:** Automated logging of source origins and ingestion timestamps.
* **Schema Drift Protection:** Dynamic column detection to prevent pipeline failures due to source changes.
* **Cryptographic Integrity:** SHA-256 hashing to ensure data hasn't been tampered with during transit.
* **Automated Reporting:** Instant visual delivery of Data Quality KPIs (Data Loss %, Null Distribution, and Lineage Flow).

### Architecture
The engine follows the **Medallion Architecture** (Bronze → Silver → Gold) with an integrated Audit Engine that records every state change in a persistent log file.

### Execution
1. Install dependencies: `pip install -r requirements.txt`
2. Run the engine: `python governance_engine.py`
3. Review the `governance_dashboard_premium.png` for executive insights.
