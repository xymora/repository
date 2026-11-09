import os

RAIZ = os.path.dirname(os.path.abspath(__file__))
DATOS = os.path.join(RAIZ, "datos")
SHOWS = os.path.join(RAIZ, "shows")
EJEMPLOS = os.path.join(RAIZ, "ejemplos")
EXPORTACIONES = os.path.join(RAIZ, "exportaciones")
PLAN_ACTUAL = os.path.join(DATOS, "plan_actual.npz")
SHOW_ACTUAL = os.path.join(DATOS, "show_actual.json")

DRONES_DEF = 300
DRONES_MIN = 30
DRONES_MAX = 1500

SEPARACION = 2.2
SEP_PADS = 3.0
ALTURA_DESPEGUE = 10.0
ALTURA_CENTRO = 55.0
ALTURA_MIN_FORMACION = 22.0

VEL_H = 7.0
VEL_SUBIDA = 4.5
VEL_BAJADA = 3.0
T_MIN_TRANSICION = 4.0
T_TIERRA = 3.0
T_ARMADO = 4.0
T_PAUSA = 1.5
T_APAGADO = 4.0

FACTOR_MINJERK = 1.875
SEP_SEGURA = 1.2
MUESTRAS_VERIFICACION = 48

PUBLICO_Y = -170.0

FUENTES = {
    "Arial Black": "ariblk.ttf",
    "Bahnschrift": "bahnschrift.ttf",
    "Impact": "impact.ttf",
    "Segoe UI Black": "seguibl.ttf",
    "Segoe UI Negrita": "segoeuib.ttf",
    "Arial Negrita": "arialbd.ttf",
    "Georgia Negrita": "georgiab.ttf",
    "Cambria Negrita": "cambriab.ttf",
    "Verdana Negrita": "verdanab.ttf",
    "Trebuchet Negrita": "trebucbd.ttf",
    "Consolas Negrita": "consolab.ttf",
    "Segoe Script": "segoescb.ttf",
    "Segoe Print": "segoeprb.ttf",
    "Comic Negrita": "comicbd.ttf",
}

FIGURAS = {
    "esfera": "Esfera",
    "toro": "Dona (toro)",
    "cubo": "Cubo",
    "corazon": "Corazón 3D",
    "adn": "Hélice de ADN",
    "estrella": "Estrella 3D",
    "piramide": "Pirámide",
    "planeta": "Planeta con anillo",
    "galaxia": "Galaxia espiral",
    "arbol": "Árbol navideño",
    "atomo": "Átomo",
    "onda": "Superficie de onda",
    "mariposa": "Mariposa",
    "cohete": "Cohete",
}

MODOS_COLOR = {
    "unico": "Un solo color",
    "degradado": "Degradado (2 colores)",
    "tres": "Tres franjas",
    "vertical": "Degradado vertical",
    "arcoiris": "Arcoíris",
    "por_letra": "Un color por letra",
    "imagen": "Colores de la imagen",
    "figura": "Colores de la figura",
}

MOVIMIENTOS = {
    "fija": "Fija",
    "girar": "Girar sobre su eje",
    "vaiven": "Vaivén",
    "latido": "Latido",
    "ola": "Ola",
}

EFECTOS = {
    "ninguno": "Ninguno",
    "arcoiris": "Arcoíris en movimiento",
    "destellos": "Destellos",
    "respirar": "Respirar",
    "barrido": "Barrido de luz",
}

FASES = {
    "tierra": ("En tierra", "#7d8596"),
    "armado": ("Armado y prueba de luces", "#ffa04d"),
    "despegue": ("Despegue", "#4ea4ff"),
    "transicion": ("Transición", "#b48cff"),
    "formacion": ("Escena", "#f5b400"),
    "regreso": ("Regreso a la base", "#3dd6f5"),
    "aterrizaje": ("Aterrizaje", "#38d39f"),
    "fin": ("Show terminado", "#7d8596"),
}
