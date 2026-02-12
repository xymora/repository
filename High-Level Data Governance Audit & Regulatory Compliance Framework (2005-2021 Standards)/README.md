# Enterprise Data Governance & Risk Framework (EDGRF)

## 1. Executive Vision
This framework establishes a high-level auditing protocol for financial institutions. It focuses on the **Triple Pillar of Data Governance**: Quality, Security (PII detection), and Regulatory Alignment (SOX/GDPR/Basel II-III).

## 2. Methodology
The engine performs a multi-stage audit:
* **Stage 1: Ingestion & Integrity:** Validates structural consistency from raw sources.
* **Stage 2: DQ Audit:** Evaluates Completeness, Consistency, and Accuracy via statistical entropy.
* **Stage 3: Compliance Scan:** Heuristic identification of sensitive information (PII).
* **Stage 4: Strategic Reporting:** Provides a Risk Scorecard for C-Suite decision-making.

## 3. Deployment
Execute the `governance_core.py` to generate the interactive audit dashboard. Ensure you have a stable internet connection to pull the 200MB+ financial data repository.
