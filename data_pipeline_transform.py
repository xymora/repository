import pandas as pd
import glob
import concurrent.futures
from datetime import datetime

# Función para cargar y transformar cada archivo
def process_file(filepath):
    df = pd.read_csv(filepath, parse_dates=["Timestamp"])
    df["Hour"] = df["Timestamp"].dt.hour
    df["DayOfWeek"] = df["Timestamp"].dt.day_name()
    df["AmountCategory"] = pd.cut(df["Amount"], bins=[0, 50, 200, 500, 1000], labels=["Low", "Medium", "High", "Very High"])
    return df

# Obtener todos los archivos de datos distribuidos
files = glob.glob("data_part_*.csv")

# Procesamiento paralelo
with concurrent.futures.ThreadPoolExecutor() as executor:
    dfs = list(executor.map(process_file, files))

# Concatenar los resultados
full_df = pd.concat(dfs, ignore_index=True)

# Agregar resumen por categoría y día
summary = full_df.groupby(["AmountCategory", "DayOfWeek"]).agg({
    "Amount": ["count", "mean", "sum"]
}).round(2)

print("Aggregated Summary:")
print(summary)

# Guardar salida transformada
full_df.to_csv("processed_transactions.csv", index=False)
summary.to_csv("summary_by_category_day.csv")
