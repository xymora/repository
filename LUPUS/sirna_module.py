# Archivo: sirna_module.py
# Descripción: Simula el efecto terapéutico de un siRNA dirigido contra el BAFF (BLyS).

from math import exp
from constants import DEFAULT_BAFF, SIMULATION_DAYS

# Simula el silenciamiento progresivo de BAFF por siRNA y efectos inmunomoduladores indirectos.
def simulate_sirna_effect(days=SIMULATION_DAYS, decay_rate=0.1, min_baff=50):
    BAFF = []
    IL10_siRNA = []
    IFNA_siRNA = []

    for t in range(days):
        # BAFF: reducción exponencial hacia un valor mínimo fisiológico
        baff_val = max(min_baff, DEFAULT_BAFF * exp(-decay_rate * t))
        BAFF.append(baff_val)

        # IL-10: leve aumento lineal por efecto compensatorio tolerogénico
        il10_val = 10 + 0.3 * t
        IL10_siRNA.append(il10_val)

        # IFN-α: disminución moderada indirecta (por alivio de activación B)
        ifna_val = 300 * exp(-0.07 * t) + 10
        IFNA_siRNA.append(ifna_val)

    return {
        "BAFF": BAFF,
        "IL10 (siRNA)": IL10_siRNA,
        "IFNA (siRNA)": IFNA_siRNA
    }
