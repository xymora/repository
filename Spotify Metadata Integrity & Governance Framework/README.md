# Spotify Metadata Integrity & Governance Framework (2021 Edition)

## Overview
This project implements a high-level Data Governance workflow focused on **Data Quality Assurance (DQA)** and **Metadata Management** for streaming services. Based on industry standards established between 2015-2021, it ensures that data assets are reliable, traceability, and ready for strategic decision-making.

## Governance Objectives
* **Data Consistency:** Validate audio features across different genres.
* **Completeness:** Identify and mitigate missing values in critical track metadata.
* **Strategic Insights:** Provide a dashboard for executive stakeholders to monitor catalog health.

## Project Structure
* `governance_audit.py`: Main execution script for data profiling and auditing.
* `requirements.txt`: Environment dependencies.
* `.gitignore`: Sensitive and temporary file exclusions.
* `LICENSE`: Standard MIT licensing for open collaboration.

## Setup
1. Install dependencies: `pip install -r requirements.txt`
2. Run the audit: `python governance_audit.py`
