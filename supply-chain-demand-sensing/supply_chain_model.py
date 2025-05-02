import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.linear_model import LinearRegression
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error

# Cargar datos
df = pd.read_csv('supply_chain_data.csv')
df['Date'] = pd.to_datetime(df['Date'])

# Agregar medias móviles para suavizar la demanda
df['RollingDemand'] = df.groupby('ProductID')['Demand'].transform(lambda x: x.rolling(window=7, min_periods=1).mean())

# Modelo de predicción de demanda por producto
predictions = []

for product in df['ProductID'].unique():
    product_df = df[df['ProductID'] == product].copy()
    product_df['DayIndex'] = (product_df['Date'] - product_df['Date'].min()).dt.days
    X = product_df[['DayIndex']]
    y = product_df['RollingDemand']
    
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    model = LinearRegression()
    model.fit(X_train, y_train)
    y_pred = model.predict(X_test)
    
    mse = mean_squared_error(y_test, y_pred)
    print(f"Product: {product} - MSE: {mse:.2f}")
    
    latest_day = product_df['DayIndex'].max() + 1
    next_day_demand = model.predict([[latest_day]])[0]
    predictions.append({'ProductID': product, 'PredictedDemand': round(next_day_demand, 2)})

# Exportar predicciones
pred_df = pd.DataFrame(predictions)
pred_df.to_csv('predicted_demand.csv', index=False)

# Visualización de demanda real vs predicha (último producto)
last_product = df['ProductID'].unique()[-1]
df_plot = df[df['ProductID'] == last_product].copy()
df_plot['DayIndex'] = (df_plot['Date'] - df_plot['Date'].min()).dt.days
X_plot = df_plot[['DayIndex']]
y_plot = df_plot['RollingDemand']
model = LinearRegression().fit(X_plot, y_plot)
y_fit = model.predict(X_plot)

plt.figure(figsize=(10,5))
plt.plot(df_plot['Date'], y_plot, label='Actual Demand', marker='o')
plt.plot(df_plot['Date'], y_fit, label='Predicted Trend', linestyle='--')
plt.title(f'Demand Sensing for {last_product}')
plt.xlabel('Date')
plt.ylabel('Smoothed Demand')
plt.legend()
plt.tight_layout()
plt.savefig('demand_trend.png')
plt.show()
