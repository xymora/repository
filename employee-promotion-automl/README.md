# 🧠 Employee Promotion Prediction System with AutoML

This project implements an end-to-end machine learning pipeline to identify eligible candidates for job promotion. It leverages **AutoML (PyCaret)** to compare multiple algorithms and **AutoEDA** tools to ensure data quality and deep insights.

## 🎯 Objective
To build a high-performance predictive model by:
* Performing automated EDA with **ydata-profiling** and **Sweetviz**.
* Handling class imbalance using **SMOTE** techniques.
* Automating model selection and hyperparameter tuning with **PyCaret**.
* Providing a scalable structure for HR decision-making.

## 🧠 Techniques Used
* **AutoEDA:** Intelligence reporting for data distributions and gender-based comparisons.
* **Data Engineering:** Label Encoding, missing value handling, and feature selection.
* **Imbalanced Learning:** SMOTE (Synthetic Minority Over-sampling Technique).
* **AutoML:** Automated pipeline for model benchmarking and optimization.

## 🛠️ Technologies
* Python 3.x
* Pandas / Scikit-Learn
* PyCaret (Machine Learning Automation)
* Imbalanced-learn
* Ydata-profiling / Sweetviz

## 📁 Project Structure
employee-promotion-ml/ 
├── data/ │ └── EmployeePromotion.csv 
├── notebooks/ │ └── promotion_analysis.ipynb 
├── outputs/ │ ├── best_model.pkl │ └── profiling_report.html 
├── requirements.txt 
└── README.md

## 🚀 Pipeline Overview
1.  **Environment Setup:** Automated dependency verification and installation.
2.  **Data Ingestion:** Remote dataset acquisition from Firebase.
3.  **Intelligence Reporting:** Generation of comprehensive AutoEDA reports.
4.  **ETL & Preprocessing:** Data cleaning and categorical encoding.
5.  **Sampling Strategy:** Dynamic SMOTE application based on class distribution.
6.  **AutoML Execution:** Model comparison, tuning, and final validation.

## 📊 Outputs
* **best_model.pkl:** The most accurate model optimized for the "is_promoted" target.
* **Performance Metrics:** Detailed evaluation including Accuracy, AUC, and Recall.

## 📄 License
This project is licensed under the MIT License.
