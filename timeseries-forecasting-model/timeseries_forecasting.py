import pandas as pd
import matplotlib.pyplot as plt
from statsmodels.tsa.statespace.sarimax import SARIMAX
from sklearn.metrics import mean_squared_error

# Cargar datos
df = pd.read_csv("operational_timeseries.csv", parse_dates=["Date"])
df.set_index("Date", inplace=True)

# Elegir variable a modelar
series = df["Revenue"]

# Separar en entrenamiento y prueba
train = series[:-12]
test = series[-12:]

# Modelo SARIMA
model = SARIMAX(train, order=(1,1,1), seasonal_order=(1,1,1,12), enforce_stationarity=False, enforce_invertibility=False)
results = model.fit(disp=False)

# Predicción
forecast = results.get_forecast(steps=12)
forecast_mean = forecast.predicted_mean
forecast_ci = forecast.conf_int()

# Evaluación
mse = mean_squared_error(test, forecast_mean)
print(f"Test MSE: {mse:.2f}")

# Visualización
plt.figure(figsize=(10,6))
plt.plot(train.index, train, label='Train')
plt.plot(test.index, test, label='Test')
plt.plot(forecast_mean.index, forecast_mean, label='Forecast', color='green')
plt.fill_between(forecast_ci.index, forecast_ci.iloc[:, 0], forecast_ci.iloc[:, 1], color='green', alpha=0.2)
plt.title("Time Series Forecasting - Revenue")
plt.xlabel("Date")
plt.ylabel("Revenue")
plt.legend()
plt.tight_layout()
plt.savefig("timeseries_forecast.png")
plt.show()
