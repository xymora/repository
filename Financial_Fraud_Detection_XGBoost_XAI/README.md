# 🛡️ Financial Fraud Detection System with XGBoost & SHAP

This project implements a high-performance machine learning pipeline designed to detect fraudulent transactions in financial datasets. It addresses complex challenges such as extreme class imbalance and model interpretability (XAI) for regulatory compliance.

## 🎯 Objective
To build a robust fraud detection engine by:
* **Advanced Preprocessing:** Handling multi-million record datasets with focused feature engineering.
* **Imbalance Management:** Implementing **SMOTE** (Synthetic Minority Over-sampling Technique) to address the 0.1% fraud prevalence.
* **Model Optimization:** Utilizing **XGBoost** for high-speed, high-accuracy binary classification.
* **Explainable AI (XAI):** Leveraging **SHAP** (Lundberg et al.) to provide transparency in model decision-making.

## 🧠 Techniques Used
* **Supervised Learning:** Gradient Boosted Decision Trees (XGBoost).
* **Sampling:** SMOTE for class balancing.
* **Interpretabilidad:** SHAP TreeExplainer for global and local feature importance.
* **Metrics:** Precision-Recall AUC (more critical than ROC-AUC for imbalanced fraud data).

## 🛠️ Technologies
* **Python 3.x**
* **XGBoost** (Core Engine)
* **SHAP** (Interpretability)
* **Imbalanced-learn** (Sampling)
* **Scikit-Learn** (Pipeline & Evaluation)

## 📁 Project Structure
financial-fraud-detection/
├── data/raw/           # Source: Kaggle PaySim Dataset
├── docs/               # Data Dictionary & Governance
├── outputs/            # Serialized models and evaluation plots
├── requirements.txt    # Project dependencies
└── README.md           # Project documentation

## 🚀 Pipeline Overview
1. **Data Governance:** Initial quality report and data type validation.
2. **Feature Engineering:** One-Hot Encoding for transaction types and numerical scaling.
3. **Resampling:** Balancing the training set to prevent model bias towards legitimate transactions.
4. **Training:** XGBoost implementation with logloss optimization.
5. **Evaluation:** Detailed analysis via Confusion Matrix and Precision-Recall curves.
6. **XAI:** Global importance summary and individual transaction "Force Plots".

## 📊 Outputs
* **fraud_detection_model.pkl:** Production-ready serialized model.
* **feature_importance_shap.png:** Visualization of factors most influencing fraud detection.

## 📄 License
This project is licensed under the MIT License.
