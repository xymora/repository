# 💎 Enterprise Data Governance & ML-Ops with DVC

## 🚀 Project Overview
This practice implements a high-level **Data Governance** framework focused on **Data Lineage**, **Schema Integrity**, and **Automated Versioning**. Using a Credit/Risk simulation (based on the Penguin dataset for stability), it demonstrates how to decouple large data artifacts from source code using **DVC (Data Versioning Control)**.

## 🛠 Key Governance Features
- **Resilient Data Ingestion:** Automated fetching with fallback logic.
- **Audit Logging:** Every transformation is timestamped for compliance.
- **Model Lineage:** Tracks which version of data produced which model version.

## 📁 Repository Structure
- `data/`: Ingested and processed datasets (Tracked by DVC).
- `models/`: Serialized ML artifacts (Tracked by DVC).
- `enterprise_pipeline.py`: Main governance orchestrator.

## ⚙️ Execution
1. Install dependencies: `pip install -r requirements.txt`
2. Initialize DVC: `dvc init`
3. Run Pipeline: `python enterprise_pipeline.py`
4. Commit to DVC: `dvc add data/raw_enterprise_data.csv models/risk_model_v1.joblib`
