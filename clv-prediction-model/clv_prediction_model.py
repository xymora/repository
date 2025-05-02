import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.linear_model import LinearRegression
from sklearn.model_selection import train_test_split
from sklearn.metrics import r2_score, mean_absolute_error

# Cargar datos
df = pd.read_csv('customer_lifetime_value.csv')

# Separar variables
X = df[['PurchaseFrequency', 'AvgOrderValue', 'CustomerLifespanYears']]
y = df['CLV']

# División de datos
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.25, random_state=42)

# Modelo
model = LinearRegression()
model.fit(X_train, y_train)

# Predicciones
y_pred = model.predict(X_test)
r2 = r2_score(y_test, y_pred)
mae = mean_absolute_error(y_test, y_pred)

print(f'R² Score: {r2:.3f}')
print(f'MAE: {mae:.2f}')

# Visualización: CLV real vs predicho
plt.figure(figsize=(8,5))
sns.scatterplot(x=y_test, y=y_pred)
plt.plot([y.min(), y.max()], [y.min(), y.max()], '--', color='red')
plt.xlabel('Actual CLV')
plt.ylabel('Predicted CLV')
plt.title('Actual vs Predicted Customer Lifetime Value')
plt.tight_layout()
plt.savefig('clv_prediction_plot.png')
plt.show()
