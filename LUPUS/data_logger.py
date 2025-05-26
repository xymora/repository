# Archivo: data_logger.py
# Descripción: Guarda los resultados de simulación en formato CSV.

import pandas as pd
import os

# Guarda un diccionario de listas en un archivo CSV.
# simulation_results: diccionario con claves como variables y listas como valores diarios.
# filename: nombre del archivo de salida (por defecto 'simulation_output.csv').
def save_simulation_data(simulation_results: dict, filename: str = "simulation_output.csv"):
    try:
        df = pd.DataFrame(simulation_results)
        df.to_csv(filename, index=False)
        print(f"[✔] Resultados guardados en: {os.path.abspath(filename)}")
    except Exception as e:
        print(f"[✘] Error al guardar los datos: {e}")
