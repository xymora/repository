import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

# Cargar datos
expression = pd.read_csv("immuno_gene_expression.csv")
edits = pd.read_csv("gene_edit_predictions.csv")

# Unir datasets
merged = expression.merge(edits, on="Gene")

# Análisis por tipo de edición y expresión promedio
summary = merged.groupby(["EditType", "Condition"])["ExpressionLevel"].mean().unstack()
print("Mean Expression by Edit Type and Condition:")
print(summary.round(3))

# Gráfico de calor de expresión media
plt.figure(figsize=(8, 5))
sns.heatmap(summary, annot=True, fmt=".2f", cmap="coolwarm")
plt.title("Mean Gene Expression by Edit Type and Immune Condition")
plt.tight_layout()
plt.savefig("edit_expression_heatmap.png")
plt.close()

# Distribución de efectos predichos
plt.figure(figsize=(6,4))
sns.countplot(data=edits, x="PredictedEffect", hue="TargetPathway")
plt.title("Predicted Gene Edit Effects Across Immune Pathways")
plt.xlabel("Effect")
plt.ylabel("Count")
plt.tight_layout()
plt.savefig("edit_effects_distribution.png")
plt.close()
