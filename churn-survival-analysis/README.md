# 📉 Customer Churn Survival Analysis Model

This project implements a survival analysis model using Kaplan-Meier estimators and Cox proportional hazards regression to understand time-to-attrition patterns in subscription-based services.

## 🎯 Objective

To analyze customer churn behavior over time and quantify the impact of customer features (such as plan type, age, and region) on the likelihood of churn using survival analysis techniques.

## 🧠 Techniques Used

- Kaplan-Meier survival curves for subscription duration
- Cox proportional hazards regression model
- Survival object creation using `Surv()`
- Visualization of survival probability and hazard ratios

## 🛠️ Technologies

- R (base)
- survival
- survminer
- dplyr

## 📁 Project Structure

churn-survival-analysis/
├── customer_churn_survival.csv     # Simulated subscription data with censoring  
├── churn_survival_analysis.R       # R script for survival analysis and plots  
└── README.md                       # Full project description and methodology

## 🚀 Pipeline

1. Load customer dataset with churn flags and subscription lengths  
2. Create survival objects using time-to-event and event indicator  
3. Fit Kaplan-Meier estimator by PlanType  
4. Plot survival curves with confidence intervals and p-value  
5. Fit Cox regression model with Age, PlanType, and Region as covariates  
6. Summarize and visualize hazard ratios via forest plot

## 📊 Outputs

- Kaplan-Meier survival curves per subscription plan
- Cox regression summary with hazard ratios and significance
- Forest plot of predictors' impact on churn risk

## 📌 Future Enhancements

- Stratify by engagement metrics (logins, purchases)
- Integrate time-varying covariates for dynamic hazard modeling
- Validate model with real customer lifecycle datasets
