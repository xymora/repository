import os

RAIZ = os.path.dirname(os.path.abspath(__file__))
CARPETA_PROYECTOS = os.path.join(RAIZ, "proyectos")
CARPETA_MAPAS = os.path.join(RAIZ, "mapas")
CARPETA_EXPORTACIONES = os.path.join(RAIZ, "exportaciones")

AGENTE = "MineriaDronesSim/1.0 (simulador educativo)"
URL_SATELITE = "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
URL_ELEVACION = "https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png"
URL_BUSQUEDA = "https://nominatim.openstreetmap.org/search?format=json&limit=1&accept-language=es&q={q}"
SERVIDORES_OVERPASS = ("https://overpass-api.de/api/interpreter", "https://overpass.kumi.systems/api/interpreter")
ATRIBUCION = ("Imagen: Esri, Maxar, Earthstar Geographics · Elevación: Mapzen/AWS Terrain Tiles · "
              "Datos: © colaboradores de OpenStreetMap")
ZOOM_SATELITE = 17
ZOOM_ELEVACION = 15

CELDAS = 1600
TAMANOS = {"1 × 1 km": 1000.0, "1.6 × 1.6 km": 1600.0, "2.5 × 2.5 km": 2500.0, "4 × 4 km": 4000.0}
TAMANO_DEFECTO = "1.6 × 1.6 km"

MINAS = {
    "Mina demostración (sintética)": None,
    "La Caridad, Sonora": (30.3120, -109.5450, "2.5 × 2.5 km"),
    "Bingham Canyon, Utah (EE. UU.)": (40.5230, -112.1500, "4 × 4 km"),
    "Chuquicamata, Chile": (-22.2910, -68.9020, "4 × 4 km"),
}
DEMO_LATLON = (23.300, -102.600)

DENSIDAD_ROCA = 2.6
BANCO_ALTURA = 10.0
BANCO_BERMA = 8.0
CARA_ANGULO = 70.0
TALUD_DISENO = 55.0

CAMARAS = {
    "RGB 20 MP (1\")": {"sensor_w": 13.2, "sensor_h": 8.8, "focal": 8.8, "px_w": 5472, "px_h": 3648, "tipo": "rgb"},
    "RGB 45 MP (full frame)": {"sensor_w": 35.9, "sensor_h": 24.0, "focal": 35.0, "px_w": 8192, "px_h": 5460, "tipo": "rgb"},
    "Térmica 640 (13 mm)": {"sensor_w": 7.68, "sensor_h": 6.14, "focal": 13.0, "px_w": 640, "px_h": 512, "tipo": "termica",
                            "netd": 0.05},
}
LIDAR = {
    "LiDAR 240 kHz (70°)": {"fov": 70.0, "pps": 240000, "alcance": 450.0, "sigma": 0.03, "retornos": 3},
    "LiDAR 480 kHz (110°)": {"fov": 110.0, "pps": 480000, "alcance": 300.0, "sigma": 0.04, "retornos": 5},
}
POSICIONAMIENTO = {
    "RTK": {"h": 0.02, "v": 0.03, "sesgo_h": 0.0, "sesgo_v": 0.0},
    "PPK": {"h": 0.03, "v": 0.05, "sesgo_h": 0.0, "sesgo_v": 0.0},
    "GNSS estándar": {"h": 0.4, "v": 0.6, "sesgo_h": 1.2, "sesgo_v": 1.8},
}
MISIONES = {
    "fotogrametria": "Fotogrametría (topografía + ortomosaico)",
    "lidar": "Mapeo LiDAR",
    "termica": "Inspección térmica",
    "visual": "Inspección visual de seguridad",
}
DRON = {"velocidad": 10.0, "bateria_min": 32.0, "reserva": 0.2, "ascenso": 5.0, "giro_s": 6.0}

TIPOS_ZONA = {
    "extraccion": ("Extracción autorizada", "#38d39f"),
    "restringida": ("Zona restringida", "#ff5f5f"),
    "exclusion": ("Exclusión de personal", "#ff78c8"),
    "acopio": ("Acopio / patio", "#f5b400"),
    "vuelo": ("Área de vuelo", "#4ea4ff"),
}
