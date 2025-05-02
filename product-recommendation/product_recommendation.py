import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import TruncatedSVD

# Cargar datos
df = pd.read_csv('retail_transactions.csv')

# Crear matriz cliente-producto
pivot = df.pivot_table(index='CustomerID', columns='ProductID', values='Quantity', aggfunc='sum', fill_value=0)

# Reducción de dimensionalidad para mejorar similitud
svd = TruncatedSVD(n_components=12, random_state=42)
matrix_reduced = svd.fit_transform(pivot)

# Calcular similitud de clientes
similarity = cosine_similarity(matrix_reduced)

# Elegir cliente base
customer_index = 0
similar_customers = np.argsort(similarity[customer_index])[::-1][1:6]

# Recomendaciones basadas en promedio de similares
mean_purchases = pivot.iloc[similar_customers].mean()
already_bought = pivot.iloc[customer_index][pivot.iloc[customer_index] > 0].index
recommendations = mean_purchases.drop(labels=already_bought).sort_values(ascending=False).head(5)

# Mostrar recomendaciones
print(f"Top product recommendations for {pivot.index[customer_index]}:")
print(recommendations)

# Visualización: Productos más vendidos por temporada
seasonal_sales = df.groupby(['Season', 'ProductID'])['Quantity'].sum().reset_index()
top_seasonal = seasonal_sales.sort_values(['Season', 'Quantity'], ascending=[True, False]).groupby('Season').head(1)

plt.figure(figsize=(8,5))
sns.barplot(data=top_seasonal, x='Season', y='Quantity', hue='ProductID')
plt.title('Top-Selling Product per Season')
plt.ylabel('Units Sold')
plt.tight_layout()
plt.savefig('seasonal_top_products.png')
plt.show()
