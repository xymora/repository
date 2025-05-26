# Archivo: exosome_module.py
# Descripción: Simula la acción de exosomas de MSCs sobre IL-10 y la polarización M1/M2.

from math import exp
from constants import SIMULATION_DAYS

# Simula el impacto de los exosomas en la producción de IL-10 y la polarización macrofágica.
# Retorna un diccionario con listas de IL10 y M1/M2_ratio a lo largo de los días simulados.
def simulate_exosome_therapy(days=SIMULATION_DAYS):
    IL10 = []
    M1_M2_ratio = []

    for t in range(days):
        # IL-10 se incrementa progresivamente (acción inmunoreguladora)
        il10_val = 10 + 20 * (1 - exp(-0.25 * t))
        IL10.append(il10_val)

        # La relación M1/M2 disminuye conforme se promueve el fenotipo M2
        m1m2_val = max(0.5, 3.0 * exp(-0.15 * t))
        M1_M2_ratio.append(m1m2_val)

    return {
        "IL10": IL10,
        "M1_M2_ratio": M1_M2_ratio
    }
