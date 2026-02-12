# 🛡️ Project Sentinel: Data Masking & Privacy Engine

### Overview
Project Sentinel is a high-performance Python utility designed to secure PII (Personally Identifiable Information) through advanced anonymization techniques. It ensures compliance with global standards like **GDPR** and **CCPA** by transforming sensitive datasets into privacy-compliant versions without losing analytical value.

### Key Features
* **Multi-Strategy Masking**: Supports Hashing (SHA-256), Synthetic Data Generation, and Redaction.
* **Dynamic Mapping**: Maintains consistency across datasets using deterministic masking.
* **Lightweight & Scalable**: Optimized for large CSV/Parquet files using Pandas.

### 🚀 Quick Start
1. **Install dependencies**: `pip install -r requirements.txt`
2. **Configure your schema**: Edit the `masking_rules` in `sentinel.py`.
3. **Execute**: `python sentinel.py --input data.csv --output secure_data.csv`

---
