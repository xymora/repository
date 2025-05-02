import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.preprocessing import StandardScaler
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score

# Cargar datos
df = pd.read_csv('customers.csv')

# Seleccionar características numéricas para el clustering
features = ['Age', 'AnnualIncome', 'SpendingScore', 'Recency', 'Frequency', 'TotalSpent']
X = df[features]

# Escalado de características
scaler = StandardScaler()
X_scaled = scaler.fit_transform(X)

# Determinar el número óptimo de clústeres con el método del codo
wcss = []
for k in range(2, 11):
    kmeans = KMeans(n_clusters=k, random_state=42)
    kmeans.fit(X_scaled)
    wcss.append(kmeans.inertia_)

plt.figure(figsize=(8, 4))
plt.plot(range(2, 11), wcss, marker='o')
plt.title('Elbow Method for Optimal k')
plt.xlabel('Number of clusters')
plt.ylabel('WCSS')
plt.grid(True)
plt.tight_layout()
plt.savefig('elbow_plot.png')
plt.show()

# Seleccionar número óptimo y entrenar modelo final
optimal_k = 4
kmeans = KMeans(n_clusters=optimal_k, random_state=42)
clusters = kmeans.fit_predict(X_scaled)

# Asignar clústeres al DataFrame original
df['Cluster'] = clusters

# Guardar resultados
df.to_csv('clustered_customers.csv', index=False)
print("Clustered data saved to 'clustered_customers.csv'")

# Visualizar clústeres en 2D (usando dos dimensiones clave)
plt.figure(figsize=(8,6))
sns.scatterplot(x='AnnualIncome', y='SpendingScore', hue='Cluster', data=df, palette='Set2')
plt.title('Customer Segments: Income vs Spending Score')
plt.tight_layout()
plt.savefig('clusters_income_spending.png')
plt.show()
