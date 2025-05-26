import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from vaccine_module import simulate_vaccine_effect
from sirna_module import simulate_sirna_effect
from ifna_blockade_module import simulate_ifna_blockade
from exosome_module import simulate_exosome_therapy
from plot_generator import plot_individual_modules, plot_results
from plot_therapy_suspension import plot_suspension_therapy
from plot_article_multipanel import plot_article_multipanel  # <--- NUEVO

def run_simulation():
    # Ruta del script y carpeta de resultados
    script_dir = os.path.dirname(os.path.abspath(__file__))
    results_dir = os.path.join(script_dir, "results")
    os.makedirs(results_dir, exist_ok=True)

    SIMULATION_DAYS = 30
    days = list(range(SIMULATION_DAYS))

    # Obtener datos de cada módulo
    vaccine = simulate_vaccine_effect(SIMULATION_DAYS)
    sirna = simulate_sirna_effect(SIMULATION_DAYS)
    ifna = simulate_ifna_blockade(SIMULATION_DAYS)
    exosomes = simulate_exosome_therapy(SIMULATION_DAYS)

    # Combinar todos los datos en un solo diccionario
    data = {
        "Día": days,
        "IL10": vaccine["IL10"],
        "IL6": vaccine["IL6"],
        "IL17": vaccine["IL17"],
        "Treg_Th": vaccine["Treg_Th"],
        "BAFF": sirna["BAFF"],
        "IL10 (siRNA)": sirna["IL10 (siRNA)"],
        "IFNA (siRNA)": sirna["IFNA (siRNA)"],
        "IFNA": ifna["IFNA"],
        "DCs": ifna["DCs"],
        "TNF_α (IFNA)": ifna["TNF_α (IFNA)"],
        "IL10 (Exosomas)": exosomes["IL10"],
        "M1/M2": exosomes["M1_M2_ratio"]
    }

    df = pd.DataFrame(data)

    # Guardar resultados como CSV
    csv_path = os.path.join(results_dir, "simulation_output.csv")
    df.to_csv(csv_path, index=False)
    print(f"[✔] Resultados guardados en: {csv_path}")

    # Generar gráficas individuales y combinadas
    plot_individual_modules(df, results_dir)
    plot_results(df, filepath=os.path.join(results_dir, "combined_response.png"))

    # Gráfica de suspensión de terapia
    plot_suspension_therapy(results_dir)

    # Gráfica multipanel tipo artículo
    plot_article_multipanel(results_dir)

if __name__ == "__main__":
    run_simulation()
