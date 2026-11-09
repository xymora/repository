import os

RAIZ = os.path.dirname(os.path.abspath(__file__))
CARPETA_DATOS = "datos"

R_TIERRA = 6371.0
DT = 1.0
DECIDIR_CADA = 4.0
RADAR_PERIODO = 2.0
CALMA_MAX = 30.0
ALT_REENTRADA = 90.0
RADIO_ACTIVO_PELIGRO = 15.0
MARGEN_SOBREVUELO = 40.0
MARGEN_CERCA = 60.0
DECIDIR_CERCA = 1.0
SAT_RETARDO = (10.0, 22.0)
SAT_AVANCE = 0.5
SAT_DEFECTO = 2
SAT_GEO_LON = (-140.0, -70.0, 0.0, 70.0, 140.0)
SAT_GEO_ALT = 35786.0
SAT_HEO_LAT = 63.0
SAT_HEO_LON = (40.0, -110.0)
SAT_HEO_ALT = 39000.0
SAT_LEO_PLANOS = 6
SAT_LEO_POR_PLANO = 10
SAT_LEO_ALT = 1200.0
SAT_LEO_INC = 75.0
SAT_LEO_RANGO = 6000.0
SAT_SEG_ALT = 100.0
SAT_SEGUIMIENTO = 0.3
DISC_SAT = 0.012
DISC_RADAR = 0.03
DISC_ESPECIAL = 0.1
P_SENUELO = 0.4
T_REINTENTO = 3.0
ESPERA_MAX = 40.0
RADIO_NUCLEAR = 35.0
FACTOR_NUCLEAR = 3.0
P_NUCLEAR_LIBRE = 0.35
CONTRA_MIN = 0.9
CONTRA_MAX = 12
T_REDESPLIEGUE = 180.0

TIPOS = {
    "corto": {"nombre": "Balístico corto", "rango": (80.0, 1000.0), "vel": 1.6, "motor": 70.0, "apogeo_k": 0.28,
              "apogeo_min": 50.0, "apogeo_max": 300.0, "sigma0": 25.0, "pk": 1.0},
    "medio": {"nombre": "Balístico medio", "rango": (1000.0, 3000.0), "vel": 2.6, "motor": 110.0, "apogeo_k": 0.22,
              "apogeo_min": 200.0, "apogeo_max": 650.0, "sigma0": 40.0, "pk": 0.95},
    "intermedio": {"nombre": "Balístico intermedio", "rango": (3000.0, 5500.0), "vel": 3.6, "motor": 160.0,
                   "apogeo_k": 0.2, "apogeo_min": 600.0, "apogeo_max": 1000.0, "sigma0": 60.0, "pk": 0.9},
    "icbm": {"nombre": "Intercontinental", "rango": (5500.0, 17000.0), "vel": 5.2, "motor": 230.0, "apogeo_k": 0.13,
             "apogeo_min": 900.0, "apogeo_max": 1300.0, "sigma0": 80.0, "pk": 0.85},
    "planeador": {"nombre": "Planeador hipersónico", "rango": (1500.0, 9000.0), "vel": 3.2, "motor": 120.0,
                  "crucero": 45.0, "sigma0": 50.0, "pk": 0.7},
}
ORDEN_TIPOS = ("corto", "medio", "intermedio", "icbm", "planeador")

CAPAS = {
    "impulso": {"nombre": "Fase de impulso", "corto": "Impulso", "vel": 5.5, "alcance": 900.0, "alt": (15.0, 600.0),
                "pk": 0.78, "retardo": 8.0, "costo": 1.0, "correccion": 12.0, "misiles": 6, "recarga": 900.0},
    "exo": {"nombre": "Exoatmosférico", "corto": "Exo", "vel": 7.0, "alcance": 5500.0, "alt": (130.0, 1800.0),
            "pk": 0.75, "retardo": 20.0, "costo": 2.0, "correccion": 20.0, "misiles": 6, "recarga": 1800.0},
    "alta": {"nombre": "Gran altitud", "corto": "Alta", "vel": 2.8, "alcance": 300.0, "alt": (40.0, 150.0),
             "pk": 0.85, "retardo": 6.0, "costo": 0.8, "correccion": 8.0, "misiles": 8, "recarga": 600.0},
    "baja": {"nombre": "Terminal", "corto": "Terminal", "vel": 2.5, "alcance": 60.0, "alt": (1.0, 50.0),
             "pk": 0.8, "retardo": 3.0, "costo": 0.3, "correccion": 3.0, "misiles": 16, "recarga": 300.0},
}
ORDEN_CAPAS = ("impulso", "exo", "alta", "baja")

ACTIVOS = {
    "buque": {"nombre": "Buque de impulso", "corto": "Buque", "capa": "impulso", "radar": 1600.0, "lanzadores": 2},
    "exo": {"nombre": "Base exoatmosférica", "corto": "Base exo", "capa": "exo", "radar": 4500.0, "lanzadores": 2},
    "alta": {"nombre": "Batería de gran altitud", "corto": "Gran alt.", "capa": "alta", "radar": 1000.0,
             "lanzadores": 3},
    "terminal": {"nombre": "Batería terminal", "corto": "Terminal", "capa": "baja", "radar": 180.0, "lanzadores": 3},
    "radar": {"nombre": "Radar de discriminación", "corto": "Radar", "capa": None, "radar": 5000.0, "lanzadores": 0},
}
ORDEN_ACTIVOS = ("buque", "exo", "alta", "terminal", "radar")

POBLACION = 32
SIGMA = 0.06
SIGMA_MIN = 0.012
SIGMA_DECAE = 0.997
SIGMA_REAVIVAR = 0.08
TASA = 0.03
DECAIMIENTO_PESOS = 0.002
CAPAS_OCULTAS = (24, 12)
GENS_SIN_MEJORA = 25
RACHA_PARA_SUBIR = 3
GUARDAR_CADA = 10
HISTORIAL_EN_MEMORIA = 2000
MAX_DEMOS = 120000
EPOCAS_IMITACION = 30
LOTES_REPASO = 6
EPISODIOS_CLASE = 6
GENS_CLASE = 25

PROTECCION_MIN = 0.9
DESPERDICIO_MAX = 0.35

PREMIO_SALVADO = 10.0
CASTIGO_DANO = 12.0
COSTO_INTERCEPTOR = 0.45
CASTIGO_ACTIVO = 60.0
