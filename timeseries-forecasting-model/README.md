# 📈 Time-Series Forecasting Model for Operational Metrics

This project implements a forecasting model for time-series data, specifically designed to support strategic planning in data-rich environments. It applies SARIMA modeling to predict operational metrics like revenue and evaluate forecast accuracy.

## 🎯 Objective

To use time-series modeling for anticipating future trends in key business metrics such as revenue, supporting data-driven operational and strategic decisions.

## 🧠 Techniques Used

- SARIMA modeling for seasonal patterns
- Data partitioning into training and testing periods
- Forecast evaluation with mean squared error (MSE)
- Visualization of forecast and confidence intervals

## 🛠️ Technologies

- Python 3.x
- pandas
- matplotlib
- statsmodels
- scikit-learn (for evaluation)

## 📁 Project Structure

timeseries-forecasting-model/
├── operational_timeseries.csv        # Simulated monthly operational data  
├── timeseries_forecasting.py         # Python script with SARIMA modeling and visualization  
├── timeseries_forecast.png           # Forecast plot with confidence intervals  
└── README.md                         # Full documentation and usage guide

## 🚀 Pipeline

1. Load monthly time-series data for revenue, orders, and users  
2. Select a single metric (e.g., Revenue) for forecasting  
3. Split the data into training and test sets (last 12 months as test)  
4. Fit a SARIMA model to the training data  
5. Forecast 12 future periods and evaluate predictions with MSE  
6. Visualize the forecast, actuals, and confidence interval bands

## 📊 Outputs

- Forecast values for the next 12 months  
- `timeseries_forecast.png`: visualization of forecast vs actuals  
- MSE printed in console for model evaluation

## 📌 Future Enhancements

- Add interactive selection for metric and forecast horizon  
- Deploy in a dashboard with Plotly or Streamlit  
- Integrate live data from SQL or time-series API
