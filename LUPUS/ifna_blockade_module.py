# Archivo: ifna_blockade_module.py
# Descripción: Simula la inhibición de IFN-α por un anticuerpo monoclonal y sus efectos inmunológicos.

from math import exp
from constants import DEFAULT_IFNA, SIMULATION_DAYS

# Simula el bloqueo de IFN-α y las consecuencias sobre DCs y TNF-α
def simulate_ifna_blockade(days=SIMULATION_DAYS):
    IFNA = []
    DCs = []
    TNF_ifna = []

    for t in range(days):
        # IFN-α: disminución exponencial fuerte por acción del anticuerpo
        ifna_val = DEFAULT_IFNA * exp(-0.15 * t)
        IFNA.append(ifna_val)

        # DCs: dependen de IFN-α → simulan su reducción con una curva más suave
        dcs_val = 80 * exp(-0.10 * t) + 20
        DCs.append(dcs_val)

        # TNF-α: cae de forma paralela al ambiente proinflamatorio
        tnf_val = 120 * exp(-0.08 * t) + 15
        TNF_ifna.append(tnf_val)

    return {
        "IFNA": IFNA,
        "DCs": DCs,
        "TNF_α (IFNA)": TNF_ifna
    }
