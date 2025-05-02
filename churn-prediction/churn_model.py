import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns

from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from xgboost import XGBClassifier
from sklearn.metrics import classification_report, confusion_matrix, roc_auc_score, roc_curve

# Cargar datos
df = pd.read_csv('churn_data.csv')

# Preprocesamiento
df_encoded = pd.get_dummies(df, columns=['Gender', 'Region', 'DeviceType'], drop_first=True)
X = df_encoded.drop(['CustomerID', 'Churned'], axis=1)
y = df_encoded['Churned']

# Dividir los datos
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.25, random_state=42)

# Escalado para regresión logística
scaler = StandardScaler()
X_train_scaled = scaler.fit_transform(X_train)
X_test_scaled = scaler.transform(X_test)

# 1. Modelo de Regresión Logística
log_model = LogisticRegression(max_iter=1000)
log_model.fit(X_train_scaled, y_train)
y_pred_log = log_model.predict(X_test_scaled)
y_proba_log = log_model.predict_proba(X_test_scaled)[:, 1]

# 2. Modelo XGBoost (no requiere escalado)
xgb_model = XGBClassifier(use_label_encoder=False, eval_metric='logloss', random_state=42)
xgb_model.fit(X_train, y_train)
y_pred_xgb = xgb_model.predict(X_test)
y_proba_xgb = xgb_model.predict_proba(X_test)[:, 1]

# Reportes
print("\nLogistic Regression Report:")
print(classification_report(y_test, y_pred_log))

print("\nXGBoost Report:")
print(classification_report(y_test, y_pred_xgb))

# Matriz de confusión combinada
fig, axs = plt.subplots(1, 2, figsize=(12, 4))
sns.heatmap(confusion_matrix(y_test, y_pred_log), annot=True, fmt='d', ax=axs[0], cmap='Blues')
axs[0].set_title('Confusion Matrix - Logistic')
sns.heatmap(confusion_matrix(y_test, y_pred_xgb), annot=True, fmt='d', ax=axs[1], cmap='Greens')
axs[1].set_title('Confusion Matrix - XGBoost')
plt.tight_layout()
plt.savefig('churn_confusion_matrices.png')
plt.show()

# Curva ROC comparada
fpr_log, tpr_log, _ = roc_curve(y_test, y_proba_log)
fpr_xgb, tpr_xgb, _ = roc_curve(y_test, y_proba_xgb)
plt.figure(figsize=(6, 5))
plt.plot(fpr_log, tpr_log, label=f'LogReg AUC = {roc_auc_score(y_test, y_proba_log):.2f}')
plt.plot(fpr_xgb, tpr_xgb, label=f'XGBoost AUC = {roc_auc_score(y_test, y_proba_xgb):.2f}')
plt.plot([0, 1], [0, 1], linestyle='--', color='gray')
plt.xlabel('False Positive Rate')
plt.ylabel('True Positive Rate')
plt.title('ROC Curve Comparison')
plt.legend()
plt.tight_layout()
plt.savefig('churn_roc_comparison.png')
plt.show()

# Guardar predicciones
results = pd.DataFrame({
    'CustomerID': df.loc[y_test.index, 'CustomerID'],
    'LogReg_Pred': y_pred_log,
    'XGBoost_Pred': y_pred_xgb,
    'Churned': y_test.values
})
results.to_csv('predictions.csv', index=False)
print("Predictions saved to 'predictions.csv'")
