# BlueShield Governance Framework (2021-2025)
**High-Level Data Governance & Resilient Analytics Pipeline**

## Context
This project demonstrates a production-grade Data Governance integration within a Data Science pipeline for the **Sustainable Fishing Industry**. It features automated quality gates, schema enforcement, and a resilient ingestion layer with synthetic fallback.

## Governance Features
- **Data Quality (DQ):** Automated validation for null values and logical consistency (e.g., Fishing hours ≤ Total hours).
- **Resilience:** Fallback mechanism to generate compliant synthetic data if external APIs (Global Fishing Watch) are unavailable.
- **Audit Trail:** Metadata logging for every stage of the pipeline (Ingestion, Quality, Transformation).

## Tech Stack
- **Language:** Python 3.x
- **Core Libs:** Pandas, Seaborn, Matplotlib, Requests.
- **Architecture:** Medallion-style processing (Bronze/Silver/Gold).
