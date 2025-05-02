import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import plotly.express as px

# Cargar datos
df = pd.read_csv("multidimensional_data.csv")

# Análisis básico
summary = df.describe(include="all")
print("Dataset Summary:")
print(summary)

# Agrupación por región y categoría de producto
pivot = df.groupby(["Region", "ProductCategory"]).agg({
    "Sales": "sum",
    "UnitsSold": "sum",
    "ProfitMargin": "mean"
}).reset_index()

# Gráfica de calor: ventas por región y categoría
heatmap_data = pivot.pivot(index="Region", columns="ProductCategory", values="Sales")
plt.figure(figsize=(10,6))
sns.heatmap(heatmap_data, annot=True, fmt=".0f", cmap="YlGnBu")
plt.title("Total Sales by Region and Product Category")
plt.savefig("sales_heatmap.png")
plt.close()

# Gráfico de dispersión interactivo con Plotly
fig = px.scatter(df, x="Sales", y="ProfitMargin", color="ProductCategory",
                 size="UnitsSold", hover_data=["Region", "Year"],
                 title="Sales vs Profit Margin by Product Category")
fig.write_html("scatter_insights.html")
