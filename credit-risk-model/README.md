# 💰 Predictive Credit Risk Scoring Model

This project implements a logistic regression model for credit risk evaluation tailored to small business loan applications. It includes performance metrics such as ROC analysis and AUC evaluation.

## 🎯 Objective

To predict the probability of loan default based on borrower characteristics, providing a data-driven scoring framework for credit decision-making in the small business sector.

## 🧠 Techniques Used

- Logistic regression modeling
- ROC curve generation and analysis
- AUC (Area Under Curve) evaluation
- Model probability scoring

## 🛠️ Technologies

- R (base)
- stats (glm)
- pROC
- ggplot2
- dplyr

## 📁 Project Structure

credit-risk-model/
├── credit_risk_data.csv          # Simulated small business loan application data  
├── credit_risk_model.R           # Logistic regression and ROC evaluation script  
├── credit_risk_roc.png           # ROC curve plot for classification performance  
└── README.md                     # Documentation and usage guide

## 🚀 Pipeline

1. Load credit application data  
2. Train a logistic regression model using financial and operational features  
3. Predict default probabilities  
4. Evaluate model performance using ROC curve and AUC  
5. Export visualization of ROC performance curve

## 📊 Outputs

- Summary of logistic model coefficients and significance  
- AUC score displayed in console  
- `credit_risk_roc.png`: ROC curve plot

## 📌 Future Enhancements

- Add feature selection and regularization (e.g., LASSO)  
- Incorporate credit bureau and banking transactional data  
- Build a credit scoring API for real-time loan evaluation
