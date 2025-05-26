# Archivo: vaccine_module.py
# Descripción: Simula el efecto inmunológico de una vacuna tolerogénica para LES.

from math import exp
from constants import SIMULATION_DAYS

# Simula la respuesta inmunológica inducida por vacuna tolerogénica.
def simulate_vaccine_effect(days=SIMULATION_DAYS):
    IL10 = []       # Inductor de tolerancia
    IL6 = []        # Citoquina proinflamatoria
    IL17 = []       # Subtipo Th17
    Treg_Th = []    # Índice regulador (Treg/Th)

    for t in range(days):
        # IL-10: curva logística hacia estado tolerante
        il10_val = 25 / (1 + exp(-0.2 * (t - 5)))
        IL10.append(il10_val)

        # IL-6: decaimiento exponencial asociado a reducción inflamatoria
        il6_val = 2.0 * exp(-0.05 * t) + 1.2
        IL6.append(il6_val)

        # IL-17: leve descenso lineal (estabilización de Th17)
        il17_val = max(1.0, 1.4 - 0.005 * t)
        IL17.append(il17_val)

        # Índice Treg/Th: aumento lento hacia tolerancia
        treg_th_val = 1.2 + 0.01 * t
        Treg_Th.append(treg_th_val)

    return {
        "IL10": IL10,
        "IL6": IL6,
        "IL17": IL17,
        "Treg_Th": Treg_Th
    }
