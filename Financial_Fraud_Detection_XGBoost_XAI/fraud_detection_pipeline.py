# ┌────────────────────────────────────────────────────────────────────────────────────┐
# │  Reto: FINANCIAL TRANSACTION FRAUD DETECTION SYSTEM                                │
# │  Desarrollado por: Álvaro Rodrigo Moctezuma Ramírez                                │
# └────────────────────────────────────────────────────────────────────────────────────┘

import subprocess
import sys
import os

# ──── SECCIÓN 0: INFRAESTRUCTURA DE GOBIERNO DE DATOS ───────────────────────────
def initialize_project():
    """Crea automáticamente la estructura de carpetas profesional."""
    folders = ['data/raw', 'data/processed', 'outputs', 'docs']
    print("» INICIALIZANDO ESTRUCTURA DE DIRECTORIOS...")
    for folder in folders:
        if not os.path.exists(folder):
            os.makedirs(folder)
            print(f"  [ CREADO ] : /{folder}")
    print("» ESTRUCTURA LISTA.\n")

initialize_project()

# ──── SECCIÓN 1: GESTIÓN DE DEPENDENCIAS Y ENTORNO ──────────────────────────────
def manage_dependencies(packages):
    print("» VERIFICANDO ENTORNO DE EJECUCIÓN...")
    for package in packages:
        try:
            __import__(package.split('==')[0])
        except ImportError:
            print(f"  [ INSTALANDO ] : {package}...")
            subprocess.check_call([sys.executable, "-m", "pip", "install", package])
    print("» ENTORNO LISTO.\n")

required_packages = [
    "pandas", "numpy", "matplotlib", "seaborn", "scikit-learn", 
    "imblearn", "xgboost", "shap", "plotly"
]
manage_dependencies(required_packages)

# Importaciones tras verificar dependencias
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import joblib
import shap
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import classification_report, confusion_matrix, roc_auc_score, precision_recall_curve, auc
from imblearn.over_sampling import SMOTE
from xgboost import XGBClassifier

plt.style.use('seaborn-v0_8-darkgrid')

# ──── SECCIÓN 2: ADQUISICIÓN Y CALIDAD DE DATOS ────────────────────────────────
print("» CARGANDO DATASET DE TRANSACCIONES...")

# Nota: El dataset debe estar en data/raw/fraudulent_transactions.csv
dataset_path = 'data/raw/fraudulent_transactions.csv'

try:
    df = pd.read_csv(dataset_path)
except FileNotFoundError:
    print(f"ERROR: No se encontró el archivo en {dataset_path}")
    print("Descárgalo de: https://www.kaggle.com/datasets/ealaxi/paysim1")
    sys.exit(1)

# Normalización de nombres (Linaje de Datos)
df.rename(columns={
    'oldbalanceOrg':'oldBalanceOrig', 'newbalanceOrig':'newBalanceOrig',
    'oldbalanceDest':'oldBalanceDest', 'newbalanceDest':'newBalanceDest'
}, inplace=True)

def data_quality_report(data):
    print("\n" + "-"*60)
    print("  REPORTE DE CALIDAD DE DATOS")
    print("-"*60)
    print(f"Registros: {len(data)} | Columnas: {len(data.columns)}")
    print(f"\nDistribución de Fraude:\n{data['isFraud'].value_counts(normalize=True)}")
    print("-"*60 + "\n")

data_quality_report(df)

# ──── SECCIÓN 3: ETL Y PREPROCESAMIENTO ─────────────────────────────────────────
print("» EJECUTANDO PIPELINE DE PREPROCESAMIENTO...")

# Filtrado estratégico para optimizar el modelo
df = df[df['type'].isin(['PAYMENT', 'TRANSFER', 'CASH_OUT'])]
df = pd.get_dummies(df, columns=['type'], drop_first=True)
df = df.drop(['nameOrig', 'nameDest', 'isFlaggedFraud', 'step'], axis=1)

X = df.drop('isFraud', axis=1)
y = df['isFraud']

X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.3, random_state=42, stratify=y)

scaler = StandardScaler()
X_train_scaled = pd.DataFrame(scaler.fit_transform(X_train), columns=X_train.columns)
X_test_scaled = pd.DataFrame(scaler.transform(X_test), columns=X_test.columns)

# Balanceo con SMOTE (Crucial para Fraude)
print("» APLICANDO SMOTE PARA BALANCEO DE CLASES...")
smote = SMOTE(random_state=42)
X_train_res, y_train_res = smote.fit_resample(X_train_scaled, y_train)

# ──── SECCIÓN 4: MODELADO E INTERPRETABILIDAD (XAI) ───────────────────────────
print("\n» ENTRENANDO MODELO XGBOOST...")
model = XGBClassifier(eval_metric='logloss', random_state=42, n_jobs=-1)
model.fit(X_train_res, y_train_res)

# Persistencia del modelo
joblib.dump(model, 'outputs/fraud_detection_model.pkl')

print("\n» GENERANDO EXPLICACIONES SHAP...")
explainer = shap.TreeExplainer(model)
shap_values = explainer.shap_values(X_test_scaled)

# Guardar Importancia de Características
plt.figure(figsize=(10, 6))
shap.summary_plot(shap_values, X_test_scaled, show=False)
plt.title('SHAP Feature Importance')
plt.savefig('outputs/feature_importance_shap.png')
plt.close()

# ──── SECCIÓN 5: EVALUACIÓN PROFESIONAL ────────────────────────────────────────
print("\n» REPORTE DE RENDIMIENTO FINAL:")
y_pred = model.predict(X_test_scaled)
y_proba = model.predict_proba(X_test_scaled)[:, 1]

print(classification_report(y_test, y_pred))

# Curva Precision-Recall (La métrica real en fraude)
precision, recall, _ = precision_recall_curve(y_test, y_proba)
plt.figure(figsize=(8, 5))
plt.plot(recall, precision, label=f'AP (AUC-PR) = {auc(recall, precision):.2f}')
plt.title('Curva Precision-Recall')
plt.xlabel('Recall')
plt.ylabel('Precision')
plt.legend()
plt.savefig('outputs/precision_recall_curve.png')

print("\n» PROCESO FINALIZADO. Resultados en /outputs.")
