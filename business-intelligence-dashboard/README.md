# 📊 Business Intelligence Dashboard with Shiny

This project delivers an interactive business intelligence dashboard built with R Shiny to visualize KPIs, client segmentation, and regional sales performance in real time.

## 🎯 Objective

To provide a user-friendly and dynamic interface for exploring sales data, analyzing profitability, and supporting business decisions through key performance metrics.

## 🧠 Techniques Used

- Shiny for interactive web application
- ggplot2 for custom visualizations
- dplyr for efficient data filtering and summarization
- Reactive components for real-time updates

## 🛠️ Technologies

- R (base)
- shiny
- ggplot2
- dplyr

## 📁 Project Structure

business-intelligence-dashboard/
├── sales_dashboard_data.csv             # Simulated sales dataset with segments and regions  
├── business_intelligence_dashboard.R    # Full Shiny app code for real-time dashboard  
└── README.md                            # Project overview and deployment instructions

## 🚀 Pipeline

1. Load regional sales dataset with client segmentation  
2. Enable user input for dynamic filters (segment and region)  
3. Display KPIs: total sales, total profit, number of orders, average order value  
4. Visualize:
   - Orders vs Sales scatter plot  
   - Sales vs Profit scatter plot  
5. Provide real-time interactivity through reactive inputs

## 📊 Outputs

- KPI summary of filtered dataset  
- Interactive visualizations by segment and region  
- Fully deployable R Shiny dashboard interface

## 📌 Future Enhancements

- Add time series input and trend analysis  
- Incorporate product category breakdown  
- Connect to live SQL backend for real operational data
