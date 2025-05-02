import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import classification_report

# Cargar datos
df = pd.read_csv('fraud_detection_data.csv')

# Preprocesamiento
df_encoded = pd.get_dummies(df, columns=['DeviceType', 'Location'], drop_first=True)
X = df_encoded.drop(['UserID', 'IsFraud'], axis=1)
y = df_encoded['IsFraud']

scaler = StandardScaler()
X_scaled = scaler.fit_transform(X)

# Modelo de detección de anomalías
model = IsolationForest(n_estimators=100, contamination=0.02, random_state=42)
df['AnomalyScore'] = model.decision_function(X_scaled)
df['Predicted'] = model.predict(X_scaled)
df['Predicted'] = df['Predicted'].map({1: 0, -1: 1})  # 1=fraude, 0=no

# Reporte
print("Classification Report:")
print(classification_report(y, df['Predicted']))

# Visualización
plt.figure(figsize=(8, 5))
sns.histplot(data=df, x='TransactionAmount', hue='Predicted', element='step', kde=True)
plt.title('Transaction Amount Distribution by Prediction')
plt.savefig('fraud_amount_distribution.png')
plt.tight_layout()
plt.show()
