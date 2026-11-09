# Enterprise Data Governance Framework
## Quality & Integrity Audit for Strategic Decision Making

### 1. Overview
This project implements a high-level Data Governance (DG) practice focused on **Data Quality Management (DQM)**. In modern organizations, data is a strategic asset. However, without a governance framework, data-driven decisions are risky. This framework automates the auditing of raw datasets to ensure they meet corporate standards before reaching executive dashboards.

### 2. Objectives
* **Data Profiling:** Systematic analysis of data sources to understand structure and content.
* **Quality Metrics:** Implementation of the "6 Dimensions of Data Quality" (Accuracy, Completeness, Consistency, Timeliness, Validity, and Uniqueness).
* **Governance Reporting:** Generation of high-level insights for Data Stewards and Stakeholders.

### 3. Business Use Case
The script downloads retail customer data to identify "Data Debt"—missing or inconsistent information that prevents accurate customer lifetime value (CLV) calculations.

### 4. Components
* `governance_audit.py`: Main engine for data profiling and visualization.
* `requirements.txt`: Environment dependencies.
* `LICENSE`: MIT License for corporate compliance.
