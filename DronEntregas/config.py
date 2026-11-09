import math

ZONAS = {
    "Monterrey · Centro": (25.6790, -100.3070),
    "CDMX · Roma–Condesa": (19.4170, -99.1660),
    "CDMX · Polanco": (19.4330, -99.1960),
    "Guadalajara · Centro": (20.6740, -103.3530),
    "Puebla · Centro": (19.0440, -98.2000),
    "Querétaro · Centro": (20.5930, -100.3920),
    "Mérida · Centro": (20.9720, -89.6230),
    "Madrid · Centro": (40.4200, -3.7000),
}
ZONA = "Monterrey · Centro"
ANCHO_ZONA = 5200.0
ALTO_ZONA = 3600.0
TAMANOS_ZONA = {
    "5 × 3.6 km": 1.0,
    "10 × 7 km": 2.0,
    "16 × 11 km": 3.0,
}
SERVIDORES_OVERPASS = ("https://overpass-api.de/api/interpreter",
                       "https://overpass.kumi.systems/api/interpreter")
URL_SATELITE = ("https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/"
                "MapServer/tile/{z}/{y}/{x}")
ATRIBUCION = "Imagen: Esri, Maxar, Earthstar Geographics · Datos: © colaboradores de OpenStreetMap"
SATELITE_ZOOM = 17
SATELITE_M_POR_PX = 1.0
DISTANCIA_ENTREGA = (2500.0, 3500.0)
NUM_ORIGENES = 8
NUM_DESTINOS = 8
SEMILLA_CIUDAD = 7

ALTURA_PISO = 3.2
ALTURAS_TIPO = {
    "house": (4, 7), "detached": (4, 7), "residential": (5, 9), "terrace": (5, 8),
    "apartments": (12, 30), "commercial": (6, 14), "retail": (5, 10), "office": (18, 50),
    "industrial": (8, 14), "warehouse": (7, 12), "church": (12, 25), "cathedral": (25, 45),
    "school": (7, 12), "university": (10, 20), "hospital": (20, 35), "hotel": (20, 45),
    "parking": (8, 15), "public": (8, 16), "government": (10, 25), "civic": (8, 18),
    "garage": (3, 4), "roof": (4, 6), "shed": (3, 4), "yes": (4, 9),
}
CARGAS = {
    "farmacia": ("Medicamentos", 0.8),
    "restaurante": ("Comida", 2.0),
}
CARGA_GENERICA = ("Paquete", 1.0)
RADIO_HELIPUERTO = 300.0
ALTURA_CABLE = {"line": 30.0, "minor_line": 11.0}
ALTURA_ANTENA = 40.0
ALTURA_SIN_MAPEAR = 8.0
ANCHO_CALLE = 16.0
AREA_ZONA_ABIERTA = 1500.0

VEHICULOS = {
    "multirotor": dict(
        nombre="Hexacóptero", masa=7.5, motores=6, empuje_motor=34.0, helice=0.56,
        cda=0.12, bateria_wh=222.0, v_crucero=16.0, v_max=18.0, a_lateral=2.5,
        v_subida=4.0, v_bajada=3.0, v_degradado=9.0),
    "avion": dict(
        nombre="Avión VTOL", masa=8.5, motores=8, empuje_motor=24.0, helice=0.38,
        cda=0.25, bateria_wh=300.0, v_crucero=24.0, v_max=28.0, a_lateral=5.0,
        v_subida=5.0, v_bajada=4.0, v_degradado=20.0,
        v_perdida=15.0,
        v_rotor=10.0,
        empuje_avance=45.0,
        ala=0.65, alargamiento=9.0, cd0=0.035, oswald=0.8,
        inclinacion_ala=math.radians(35)),
}
VEHICULO = "multirotor"

EFICIENCIA = 0.62
CONSUMO_AVIONICA = 35.0
CELDAS = 6
RESISTENCIA_BATERIA = 0.04
RESERVA = 0.08
INCLINACION_MAX = math.radians(35)
A_MAX = 3.5
PARACAIDAS_CDA = 5.0
RHO = 1.2
G = 9.81

TECHO = 120.0
ALTURA_CRUCERO = 50.0
SEPARACION_VERTICAL = 20.0
SEPARACION_HORIZONTAL = 15.0
SEPARACION_CABLES = 15.0
RADIO_ANTENA = 25.0
MARGEN_ZONA = 25.0
ALTURA_DESPEGUE = 25.0
ALTURA_APROX = 20.0
V_ZONA = 10.0
V_CABLES = 11.0
A_ACELERAR = 1.5
A_FRENAR = 1.2
PENDIENTE_SUBIDA = 0.22
PENDIENTE_BAJADA = 0.16
CELDA = 10.0
PESO_ALTURA = 1.0
DS = 5.0

V_DESCENSO = ((15.0, 2.0), (4.0, 0.8), (0.0, 0.3))
TOL_PLATAFORMA = 0.30
RAFAGA_ABORTO = 6.5

VIENTO = 5.0
VIENTO_DIRECCION = 225.0
RAFAGAS = True
RAFAGA_CADA = 35.0
RAFAGA_MAX = 9.0
AVES = True
NUM_PARVADAS = 8
PARVADAS_EN_RUTA = 4
RADIO_SENSOR = 60.0

GPS_DURACION = (25.0, 80.0)
FACTOR_SIN_GPS = 0.6
FIX_VISUAL_CADA = 15.0
BATERIA_FALLA = 0.20
MAX_FALLAS_MOTOR = 1

CURSO = ("despegue", "crucero", "aterrizaje", "esquivar", "entrega")
ESCENARIOS_POR_LECCION = 3
NEURONAS_OCULTAS = 10
ESCALA_PESOS = 1.5
DT_ESCUELA = 0.1
APROBAR_SEGUIDAS = 2
POBLACION = 40
ELITE = 3
TORNEO = 3
PROB_CRUCE = 0.7
PROB_MUTACION = 0.10
SIGMA_MUTACION = 0.25
FRACCION_NUEVOS = 0.05
FRACCION_AFINADOS = 0.3
SIGMA_AFINADO = 0.04
ESTANCAMIENTO = 15
EXTINCION = 60
MEJORA_NOTABLE = 10.0

DT = 0.05
TIEMPO_MAX = 1800.0
FPS_MS = 33
