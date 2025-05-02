import pandas as pd

# Cargar datasets
profiles = pd.read_csv("user_profiles.csv")
finance = pd.read_csv("financial_history.csv")
events = pd.read_csv("risk_events.csv")

# Combinar todos los datos
df = profiles.merge(finance, on="UserID").merge(events, on="UserID")

# Reglas de riesgo basadas en perfil
def assess_risk(row):
    score = 0
    if row["CreditScore"] < 600:
        score += 2
    if row["LoanDefaults"] > 0:
        score += 2
    if row["HighRiskAlerts"] == 1:
        score += 3
    if row["MonthlySpending"] > 2000:
        score += 1
    if row["ReportedIncidents"] > 0:
        score += 2
    if row["OnlineActivityScore"] > 0.8:
        score += 1
    if row["EmploymentStatus"] in ["Unemployed", "Student"]:
        score += 1
    return "High" if score >= 6 else "Moderate" if score >= 3 else "Low"

# Aplicar lógica de inferencia
df["RiskCategory"] = df.apply(assess_risk, axis=1)

# Guardar salida
df.to_csv("inference_risk_output.csv", index=False)

# Resumen visual
summary = df["RiskCategory"].value_counts().sort_index()
print("Risk Assessment Summary:")
print(summary)
