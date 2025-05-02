import pandas as pd
from datetime import timedelta

# Cargar fuentes
customers = pd.read_csv("source_customers.csv")
transactions = pd.read_csv("source_transactions.csv", parse_dates=["Timestamp"])
stream = pd.read_csv("stream_events.csv", parse_dates=["EventTime"])

# Paso 1: ETL - Integrar clientes y transacciones
etl_merged = transactions.merge(customers, on="CustomerID")
etl_merged["AmountCategory"] = pd.cut(etl_merged["Amount"], bins=[0, 50, 150, 500], labels=["Low", "Medium", "High"])

# Paso 2: Join simulando streaming por cercanía temporal
# Consideramos eventos dentro de ±1 hora de la transacción
stream_joined = pd.merge_asof(
    left=etl_merged.sort_values("Timestamp"),
    right=stream.sort_values("EventTime"),
    by="CustomerID",
    left_on="Timestamp",
    right_on="EventTime",
    direction="nearest",
    tolerance=pd.Timedelta("1H")
)

# Guardar resultados
etl_merged.to_csv("unified_customer_transactions.csv", index=False)
stream_joined.to_csv("real_time_enriched_dataset.csv", index=False)

print("ETL and Stream Processing completed. Outputs saved.")
