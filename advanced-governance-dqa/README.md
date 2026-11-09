# AG-DQA: Advanced Governance & Data Quality Assurance Engine
## Data Quality Framework - High-Level Practice (2005-2021)

### Executive Overview
This framework implements a robust Data Quality policy based on DAMA-DMBOK standards. It is designed to automate the auditing of corporate datasets, ensuring that decision-making is based on accurate, consistent, and complete information.

### Key Governance Dimensions
* **Accuracy:** Detects financial anomalies and price outliers using IQR (Interquartile Range) methods.
* **Consistency:** Evaluates data uniformity across geographical regions (Countries).
* **Completeness:** Monitors missing identity records (CustomerIDs) and critical field nulls.
* **Integrity Score:** A weighted algorithm that calculates a "Reliability Index" per record.

### Installation & Usage
1. **Environment:** Ensure Python 3.9+ is installed.
2. **Dependencies:** Run `pip install -r requirements.txt`.
3. **Execution:** Run `python main.py`.
4. **Output:** An interactive HTML dashboard (`Data_Quality_Report.html`) and an executive console summary.
