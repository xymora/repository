import math

LOTE_ANCHO = 100.0
LOTE_ALTO = 56.0
CAJON_FONDO = 25.0
MARGEN_X = 11.0
TAMANOS = {"chico": 3.8, "normal": 4.4, "grande": 5.2}
OPCIONES_TAMANO = ("chico", "normal", "grande", "azar")
TAMANO = "normal"
CAJON_ANCHO = TAMANOS["normal"]
LINEA_ANCHO = 0.15
MARGEN_LINEA = 0.10
ESTACIONADO_CAJAS = (8.5, 8.5)
ESTACIONADO_SEPARACION = 1.6
ESTACIONADO_FONDO = 0.6

TRACTOR = dict(dist_ejes=3.8, frente=5.2, atras=1.0, ancho=2.5, enganche_atras=-0.3)
REMOLQUES = {
    1: [dict(largo_lanza=11.0, frente=12.2, atras=1.4, ancho=2.6, enganche_atras=0.0)],
    2: [dict(largo_lanza=6.5, frente=7.4, atras=1.1, ancho=2.6, enganche_atras=1.5),
        dict(largo_lanza=8.6, frente=7.4, atras=1.1, ancho=2.6, enganche_atras=0.0)],
}
OPCIONES_REMOLQUES = (1, 2)
NUM_REMOLQUES = 1

GIRO_MAX = math.radians(40)
VEL_VOLANTE = math.radians(30)
ACEL_MAX = 1.2
FRENO_MAX = 4.0
RODADURA = 0.2
V_MAX = 4.0
V_REVERSA = 2.0
V_CAMBIO = 0.05
TIJERA = math.radians(75)
SUBPASOS = 4

ASISTENTE_REVERSA = True
ARTICULACION_PLAN = math.radians(45)
GANANCIAS_ASISTENTE = {1: (4.0, 0.0), 2: (2.0, 2.0)}

MODOS = ("frente", "reversa")
MODO_ESTACIONAR = "reversa"

INICIO = (20.0, 42.0, 0.0)

LUGARES = ("asignado", "camara")
LUGAR = "camara"
REFERENCIA_X = {"frente": -6.0, "reversa": 8.0}
V_BUSQUEDA = 2.5
V_ACERCAMIENTO = 3.0
PASOS_LLEGADA = 900

CAMARA = dict(x=4.0, y=-1.3, desde=-160.0, hasta=-25.0, rayos=41, alcance=60.0)
EVIDENCIA_LUGAR = 6

DT = 0.2
PASOS_MAX = 1000
PASOS_INMOVIL = 25

TOL_ANGULO = math.radians(2.5)
TOL_CENTRO = 0.15
V_ESTACIONADO = 0.02
CASTIGO_CHOQUE = 150
CASTIGO_CHOQUE_VEL = 60

MAPA_RES = 0.8
MAPA_ANGULOS = 48
MAPA_PASO = 1.4
MAPA_RADIO = {"frente": 7.0, "reversa": 9.0}
MAPA_COSTO_REVERSA = 1.3

MAX_MANIOBRAS = 6
PUNTOS_VOLANTE = 3
DIST_MIN = 0.5
DIST_MAX = 45.0
V_MIN_MANIOBRA = 0.6

FRENADO_SUAVE = 0.8
V_ARRASTRE = 0.15
TOLERANCIA_TRAMO = 0.03

POBLACION = 200
ELITE = 3
TORNEO = 3
PROB_CRUCE = 0.85
PROB_MUTACION = 0.15
SIGMA_MUTACION = 0.30
FRACCION_NUEVOS = 0.05
FRACCION_AFINADOS = 0.3
SIGMA_AFINADO = 0.04
ESTANCAMIENTO = 15
EXTINCION = 20
MEJORA_NOTABLE = 25.0

ESCALA = 8
FPS_MS = 16
