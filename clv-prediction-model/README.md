# 💎 Customer Lifetime Value (CLV) Prediction Model

This project implements a regression-based customer lifetime value (CLV) prediction system to support strategic investment in high-value customers and retention campaign optimization.

## 🎯 Objective

To estimate the long-term value of individual customers by modeling the relationship between purchase frequency, order value, and customer lifespan.

## 🧠 Techniques Used

- Linear Regression modeling
- Feature correlation and data preprocessing
- CLV calculation and supervised prediction
- Regression error metrics: MAE, R²
- Actual vs Predicted visualization for performance analysis

## 🛠️ Technologies

- Python 3.x
- pandas, matplotlib, seaborn
- scikit-learn (LinearRegression, train_test_split, metrics)

## 📁 Project Structure

clv-prediction-model/
├── customer_lifetime_value.csv       # Simulated customer behavior dataset  
├── clv_prediction_model.py           # Regression script for CLV estimation  
├── clv_prediction_plot.png           # Scatter plot of predicted vs actual CLV  
└── README.md                         # Project documentation and pipeline

## 🚀 Pipeline

1. Load customer-level behavioral data
2. Train a linear regression model using:
   - Purchase frequency  
   - Average order value  
   - Expected customer lifespan  
3. Predict CLV for test set
4. Evaluate model using MAE and R² score
5. Visualize real vs predicted CLV to assess accuracy

## 📊 Outputs

- Model R² and MAE printed to console
- `clv_prediction_plot.png`: graphical comparison of predicted vs actual CLV

## 📌 Future Enhancements

- Incorporate customer acquisition cost (CAC) and retention cost for net CLV
- Cluster customers based on value tiers
- Integrate time-decay or probabilistic CLV estimation for dynamic prediction
