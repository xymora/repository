import os

RAIZ = os.path.dirname(os.path.abspath(__file__))
CARPETA_DATOS = "datos"

MAPA_W = 80000.0
MAPA_H = 60000.0
DT = 0.25
DECIDIR_CADA = 2

RADAR_ALCANCE = 70000.0
RADAR_PERIODO = 1.0
RADIO_TIERRA_EF = 8.5e6

INT_VEL = 760.0
INT_VMAX = 1100.0
INT_ALCANCE = 15000.0
INT_TECHO = 10000.0
INT_ALT_MIN = 250.0
INT_RETARDO = 1.2
RADIO_CORRECCION = 260.0

LANZADORES = 3
MISILES_POR_LANZADOR = 26
RECARGA = 120.0
SEPARACION_LANZADORES = 1400.0
SEPARACION_BATERIAS = 6000.0
MAX_BATERIAS = 6

T_PLEGAR = 60.0
T_DESPLEGAR = 90.0
VEL_CONVOY = 70.0 / 3.6
RADIO_BATERIA_PELIGRO = 500.0
MARGEN_SOBREVUELO = 2500.0
DISTANCIA_FRENTE_MIN = 7000.0

TIPOS = {
    "corto": {"nombre": "Cohete corto", "vel": 320.0, "rango": (5000.0, 20000.0), "apogeo_k": 0.24,
              "apogeo_max": 6000.0, "retardo": (2.0, 4.0), "sigma0": 1400.0, "pk": 0.90},
    "medio": {"nombre": "Cohete medio", "vel": 560.0, "rango": (20000.0, 45000.0), "apogeo_k": 0.2,
              "apogeo_max": 9500.0, "retardo": (2.5, 5.0), "sigma0": 2200.0, "pk": 0.86},
    "mortero": {"nombre": "Mortero", "vel": 170.0, "rango": (2500.0, 7500.0), "apogeo_k": 0.32,
                "apogeo_max": 2600.0, "retardo": (1.5, 3.0), "sigma0": 700.0, "pk": 0.78},
    "dron": {"nombre": "Dron de ataque", "vel": 48.0, "rango": (8000.0, 40000.0), "altitud": 280.0,
             "retardo": (4.0, 9.0), "sigma0": 900.0, "pk": 0.93},
}
ORDEN_TIPOS = ("corto", "medio", "mortero", "dron")

POBLACION = 48
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
DESPERDICIO_MAX = 0.3

PREMIO_SALVADO = 10.0
CASTIGO_DANO = 12.0
COSTO_INTERCEPTOR = 0.45
CASTIGO_BATERIA = 60.0
