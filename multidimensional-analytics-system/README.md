# 📊 Multidimensional Data Analytics System

This project implements a data analytics system for identifying patterns, generating insights, and visualizing structured datasets across multiple dimensions such as region, product category, and time.

## 🎯 Objective

To explore and analyze high-dimensional structured business data to uncover trends, relationships, and performance metrics useful for data-driven decision-making.

## 🧠 Techniques Used

- Pivot tables and aggregation by multiple features
- Heatmaps for category-level comparisons
- Interactive scatter plots for multidimensional exploration
- Summary statistics and descriptive analytics

## 🛠️ Technologies

- Python 3.x
- pandas
- seaborn
- matplotlib
- plotly.express

## 📁 Project Structure

multidimensional-analytics-system/
├── multidimensional_data.csv         # Structured simulated dataset  
├── multidimensional_analysis.py      # Full Python script with analysis and visualizations  
├── sales_heatmap.png                 # Heatmap: Sales by region and category  
├── scatter_insights.html             # Interactive scatter plot with multiple dimensions  
└── README.md                         # Documentation and project overview

## 🚀 Pipeline

1. Load structured dataset containing customer, sales, and product data  
2. Generate summary statistics for global understanding  
3. Group data by region and product category  
4. Create heatmap of total sales across dimensions  
5. Generate an interactive scatter plot for profit margin vs sales, sized by units sold

## 📊 Outputs

- `sales_heatmap.png`: visual heatmap for category-region sales patterns  
- `scatter_insights.html`: interactive plot for deep insight exploration  
- Printed summary statistics and multidimensional aggregation

## 📌 Future Enhancements

- Integrate with SQL backend and replace CSV loader  
- Add support for time-series trend lines per region or product  
- Enable dashboard mode with Streamlit or Dash for live updates
