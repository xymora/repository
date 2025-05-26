# Archivo: constants.py
# Descripción: Define constantes globales usadas en todo el modelo.

# Citoquinas (niveles basales simulados)
DEFAULT_IFNA = 500       # Interferón alfa tipo I (pg/mL)
DEFAULT_BAFF = 1000      # BAFF / BLyS (ng/mL)
DEFAULT_IL6 = 300        # Interleucina 6 (pg/mL)
DEFAULT_IL10 = 10        # Interleucina 10 (pg/mL)

# Proporciones inmunológicas iniciales
DEFAULT_TREG_RATIO = 0.8         # Proporción Treg/Th17
DEFAULT_M1_M2_RATIO = 3.0        # Polarización macrofágica inicial M1/M2

# Niveles normales de complemento
NORMAL_C3 = 90           # C3 basal (mg/dL)
NORMAL_C4 = 20           # C4 basal (mg/dL)

# Tiempo total de simulación (en días)
SIMULATION_DAYS = 30
