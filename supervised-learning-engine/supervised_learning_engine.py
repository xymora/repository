import pandas as pd
import matplotlib.pyplot as plt
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report, confusion_matrix, roc_auc_score, RocCurveDisplay
from sklearn.decomposition import PCA

# Cargar datos
df = pd.read_csv("high_dimensional_data.csv")
X = df.drop("Target", axis=1)
y = df["Target"]

# División de datos
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

# Modelo
clf = RandomForestClassifier(n_estimators=100, random_state=42)
clf.fit(X_train, y_train)

# Predicciones y métricas
y_pred = clf.predict(X_test)
y_prob = clf.predict_proba(X_test)[:, 1]
print("Classification Report:")
print(classification_report(y_test, y_pred))
print("ROC AUC:", roc_auc_score(y_test, y_prob))

# Matriz de confusión
cm = confusion_matrix(y_test, y_pred)
plt.figure(figsize=(5,4))
plt.imshow(cm, cmap='Blues', interpolation='nearest')
plt.title("Confusion Matrix")
plt.colorbar()
plt.xlabel("Predicted")
plt.ylabel("Actual")
plt.savefig("confusion_matrix.png")
plt.close()

# Curva ROC
RocCurveDisplay.from_predictions(y_test, y_prob)
plt.title("ROC Curve")
plt.savefig("roc_curve.png")
plt.close()

# PCA para visualización 2D
pca = PCA(n_components=2)
X_pca = pca.fit_transform(X)
df_pca = pd.DataFrame(X_pca, columns=["PC1", "PC2"])
df_pca["Target"] = y

plt.figure(figsize=(6,5))
for label in df_pca["Target"].unique():
    subset = df_pca[df_pca["Target"] == label]
    plt.scatter(subset["PC1"], subset["PC2"], label=f"Class {label}", alpha=0.6)
plt.legend()
plt.title("PCA of High-Dimensional Data")
plt.xlabel("PC1")
plt.ylabel("PC2")
plt.tight_layout()
plt.savefig("pca_projection.png")
plt.close()
