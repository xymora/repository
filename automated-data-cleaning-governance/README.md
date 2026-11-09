# Automated Data Cleaning Pipeline: Governance Framework

## 📌 Description
This project implements a high-level Data Governance practice focused on **Data Quality Management**. It automates the detection and treatment of missing values (nulls) and statistical outliers (atypicals) using robust scaling and imputation techniques.

## 🛠️ Governance Standards Applied
* **Integrity:** Automated null-handling with mean/median/mode strategies based on distribution.
* **Consistency:** Outlier detection using the Interquartile Range (IQR) method.
* **Transparency:** Automated generation of a Data Quality Dashboard for executive decision-making.

## 🚀 Execution
1. Install dependencies: `pip install -r requirements.txt`
2. Run the notebook or script: `python data_cleaning_pipeline.py`
