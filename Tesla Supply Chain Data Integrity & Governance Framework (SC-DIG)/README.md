# Tesla Supply Chain Data Integrity & Governance Framework (SC-DIG)

## Project Overview
This practice establishes a high-level Data Governance workflow for Tesla's Supply Chain analytics. In an environment where data drives autonomous manufacturing, ensuring the **Accuracy, Completeness, and Consistency** of supplier data is mission-critical.

## Governance Objectives
* **Data Quality Profiling:** Automated validation of incoming manufacturing telemetry.
* **Stewardship:** Implementation of business rules to flag anomalies in battery cell production metrics.
* **Decision Support:** A professional dashboard for executive-level insights into "Data Health vs. Production Yield."

## Tech Stack
* **Language:** Python 3.9+
* **Libraries:** Pandas, Great Expectations (logic), Plotly, Scikit-learn.
* **Framework:** Data Governance Maturity Model (Level 4: Managed).

## Setup
1. Install dependencies: `pip install -r requirements.txt`
2. Run the notebook: `jupyter notebook governance_tesla_analysis.ipynb`
