import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.linear_model import LinearRegression
from sklearn.model_selection import train_test_split
from sklearn.metrics import r2_score

# Cargar datos
df = pd.read_csv('dynamic_pricing_data.csv')
df['PriceGap'] = df['OurPrice'] - df['CompetitorPrice']

# Crear variable objetivo: demanda futura estimada
df['FutureDemand'] = df['UnitsSold'].shift(-1)
df.dropna(inplace=True)

# Entrenamiento del modelo
features = ['OurPrice', 'CompetitorPrice', 'PriceGap', 'Inventory']
X = df[features]
y = df['FutureDemand']

X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
model = LinearRegression()
model.fit(X_train, y_train)

# Evaluación
y_pred = model.predict(X_test)
r2 = r2_score(y_test, y_pred)
print(f"Model R^2 Score: {r2:.3f}")

# Simulación: nuevo precio para un producto dado
example = pd.DataFrame([{
    'OurPrice': 50,
    'CompetitorPrice': 48,
    'PriceGap': 2,
    'Inventory': 120
}])
predicted_demand = model.predict(example)[0]
print(f"Predicted demand with OurPrice=50 and CompetitorPrice=48: {predicted_demand:.2f}")

# Visualización: sensibilidad de precio
sns.lmplot(data=df, x='OurPrice', y='UnitsSold', aspect=1.5, line_kws={'color': 'red'})
plt.title('Price Elasticity: Units Sold vs Our Price')
plt.savefig('price_elasticity.png')
plt.show()
