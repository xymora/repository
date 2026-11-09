import math

import numpy as np

import config as C

R = C.R_TIERRA


def unitario(lat, lon):
    la, lo = math.radians(lat), math.radians(lon)
    return np.array([math.cos(la) * math.cos(lo), math.cos(la) * math.sin(lo), math.sin(la)])


def ecef(lat, lon, alt=0.0):
    return unitario(lat, lon) * (R + alt)


def latlon(v):
    v = np.asarray(v, dtype=float)
    r = float(np.linalg.norm(v))
    return math.degrees(math.asin(max(-1.0, min(1.0, v[2] / r)))), math.degrees(math.atan2(v[1], v[0])), r - R


def latlon_vec(P):
    r = np.linalg.norm(P, axis=-1)
    lat = np.degrees(np.arcsin(np.clip(P[..., 2] / r, -1, 1)))
    lon = np.degrees(np.arctan2(P[..., 1], P[..., 0]))
    return lat, lon, r - R


def distancia(lat1, lon1, lat2, lon2):
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(min(1.0, math.sqrt(a)))


def distancia_u(u1, u2):
    return R * math.atan2(float(np.linalg.norm(np.cross(u1, u2))), float(np.dot(u1, u2)))


def destino(lat, lon, rumbo, d):
    la, lo, b, a = math.radians(lat), math.radians(lon), math.radians(rumbo), d / R
    la2 = math.asin(math.sin(la) * math.cos(a) + math.cos(la) * math.sin(a) * math.cos(b))
    lo2 = lo + math.atan2(math.sin(b) * math.sin(a) * math.cos(la), math.cos(a) - math.sin(la) * math.sin(la2))
    return math.degrees(la2), (math.degrees(lo2) + 540) % 360 - 180


def rumbo(lat1, lon1, lat2, lon2):
    p1, p2, dl = math.radians(lat1), math.radians(lat2), math.radians(lon2 - lon1)
    y = math.sin(dl) * math.cos(p2)
    x = math.cos(p1) * math.sin(p2) - math.sin(p1) * math.cos(p2) * math.cos(dl)
    return math.degrees(math.atan2(y, x)) % 360


def hacia(lat1, lon1, lat2, lon2, d):
    return destino(lat1, lon1, rumbo(lat1, lon1, lat2, lon2), d)


def centroide(puntos, pesos=None):
    pesos = pesos or [1.0] * len(puntos)
    v = sum(w * unitario(la, lo) for (la, lo), w in zip(puntos, pesos))
    la, lo, _ = latlon(v / max(np.linalg.norm(v), 1e-9) * R)
    return la, lo


def centro_origen(clave):
    la0, la1, lo0, lo1 = ORIGENES[clave]["caja"]
    return (la0 + la1) / 2, (lo0 + lo1) / 2


def tipo_para(d, preferido=None):
    if preferido and C.TIPOS[preferido]["rango"][0] <= d <= C.TIPOS[preferido]["rango"][1]:
        return preferido
    for t in ("corto", "medio", "intermedio", "icbm"):
        lo, hi = C.TIPOS[t]["rango"]
        if lo <= d <= hi:
            return t
    return "corto" if d < C.TIPOS["corto"]["rango"][0] else None


def desplazar(lat, lon, este, norte):
    d = math.hypot(este, norte)
    if d < 1e-9:
        return lat, lon
    return destino(lat, lon, math.degrees(math.atan2(este, norte)), d)


class Zona:
    __slots__ = ("nombre", "lat", "lon", "r", "valor", "activa", "u", "bando")

    def __init__(self, nombre, lat, lon, r, valor=2, activa=True, bando=""):
        self.nombre, self.lat, self.lon, self.r = nombre, float(lat), float(lon), float(r)
        self.valor, self.activa, self.bando = float(valor), activa, bando
        self.u = unitario(self.lat, self.lon)

    def distancia(self, lat, lon):
        return distancia(self.lat, self.lon, lat, lon)

    def contiene(self, lat, lon, margen=0.0):
        return self.distancia(lat, lon) <= self.r + margen

    def copia(self):
        return Zona(self.nombre, self.lat, self.lon, self.r, self.valor, self.activa, self.bando)

    def a_dict(self):
        return {"nombre": self.nombre, "lat": self.lat, "lon": self.lon, "r": self.r, "valor": self.valor,
                "activa": self.activa}


CIUDADES = {
    "Seúl": (37.5665, 126.9780, 25, 3), "Busan": (35.1796, 129.0756, 18, 2), "Tokio": (35.6762, 139.6503, 30, 3),
    "Osaka": (34.6937, 135.5023, 22, 2), "Sapporo": (43.0618, 141.3545, 15, 1), "Naha": (26.2124, 127.6809, 12, 2),
    "Guam": (13.4443, 144.7937, 15, 3), "Honolulu": (21.3069, -157.8583, 15, 3),
    "Anchorage": (61.2181, -149.9003, 15, 2), "Seattle": (47.6062, -122.3321, 20, 2),
    "San Francisco": (37.7749, -122.4194, 20, 3), "Los Ángeles": (34.0522, -118.2437, 28, 3),
    "San Diego": (32.7157, -117.1611, 15, 2), "Tijuana": (32.5149, -117.0382, 12, 2),
    "Ciudad de México": (19.4326, -99.1332, 30, 3), "Pachuca": (20.1011, -98.7591, 12, 2),
    "Guadalajara": (20.6597, -103.3496, 20, 3), "Monterrey": (25.6866, -100.3161, 20, 3),
    "Manila": (14.5995, 120.9842, 22, 2), "Taipéi": (25.0330, 121.5654, 18, 2),
    "Moscú": (55.7558, 37.6173, 30, 3), "San Petersburgo": (59.9343, 30.3351, 22, 3),
    "Kaliningrado": (54.7104, 20.4522, 12, 2), "Novosibirsk": (55.0084, 82.9357, 18, 2),
    "Londres": (51.5074, -0.1278, 28, 3), "París": (48.8566, 2.3522, 25, 3), "Berlín": (52.5200, 13.4050, 22, 3),
    "Varsovia": (52.2297, 21.0122, 18, 2), "Roma": (41.9028, 12.4964, 20, 2), "Madrid": (40.4168, -3.7038, 20, 2),
    "Bruselas": (50.8503, 4.3517, 12, 2), "Vilna": (54.6872, 25.2797, 10, 2), "Riga": (56.9496, 24.1052, 10, 2),
    "Tallin": (59.4370, 24.7536, 10, 2), "Helsinki": (60.1699, 24.9384, 12, 2), "Oslo": (59.9139, 10.7522, 12, 1),
    "Bucarest": (44.4268, 26.1025, 15, 2), "Ankara": (39.9334, 32.8597, 18, 2),
    "Washington": (38.9072, -77.0369, 18, 3), "Nueva York": (40.7128, -74.0060, 25, 3),
    "Chicago": (41.8781, -87.6298, 22, 2), "Ottawa": (45.4215, -75.6972, 12, 1),
    "Delhi": (28.6139, 77.2090, 30, 3), "Bombay": (19.0760, 72.8777, 28, 3), "Islamabad": (33.6844, 73.0479, 15, 3),
    "Karachi": (24.8607, 67.0011, 25, 3), "Lahore": (31.5204, 74.3587, 22, 2), "Pyongyang": (39.0392, 125.7625, 15, 3),
    "Pekín": (39.9042, 116.4074, 30, 3), "Shanghái": (31.2304, 121.4737, 30, 3), "Teherán": (35.6892, 51.3890, 25, 3),
}

ORIGENES = {
    "corea": {"nombre": "Corea del Norte", "caja": (38.9, 41.3, 125.0, 129.3), "mar": False},
    "iran": {"nombre": "Irán", "caja": (29.0, 36.0, 50.0, 58.0), "mar": False},
    "pac_norte": {"nombre": "Submarino · Pacífico Norte", "caja": (40.0, 48.0, 160.0, 175.0), "mar": True},
    "pac_este": {"nombre": "Submarino · Pacífico Oriental", "caja": (10.0, 18.0, -122.0, -110.0), "mar": True},
    "rusia_oeste": {"nombre": "Rusia occidental", "caja": (52.0, 58.5, 38.5, 50.0), "mar": False},
    "siberia": {"nombre": "Siberia", "caja": (51.5, 56.0, 60.0, 80.0), "mar": False},
    "barents": {"nombre": "Submarino · Mar de Barents", "caja": (69.5, 74.0, 30.0, 50.0), "mar": True},
    "eeuu": {"nombre": "EE.UU. · silos", "caja": (41.0, 48.0, -106.0, -97.0), "mar": False},
    "atlantico": {"nombre": "Submarino · Atlántico Norte", "caja": (50.0, 60.0, -35.0, -20.0), "mar": True},
    "europa": {"nombre": "Europa occidental", "caja": (44.0, 47.5, -0.5, 6.0), "mar": False},
    "india": {"nombre": "India", "caja": (21.0, 26.5, 75.0, 82.0), "mar": False},
    "pakistan": {"nombre": "Pakistán", "caja": (27.0, 30.5, 66.5, 70.5), "mar": False},
    "china": {"nombre": "China", "caja": (34.0, 40.0, 100.0, 110.0), "mar": False},
}
ORDEN_ORIGENES = tuple(ORIGENES)

PAISES = {
    "Afganistán": (33.9, 67.7, 400), "Alemania": (51.2, 10.4, 300), "Arabia Saudita": (24.0, 45.0, 600),
    "Argelia": (28.0, 2.6, 600), "Argentina": (-34.6, -64.0, 700), "Australia": (-25.3, 133.8, 700),
    "Bielorrusia": (53.7, 28.0, 250), "Brasil": (-10.0, -52.0, 700), "Canadá": (56.1, -106.3, 700),
    "China": (36.0, 104.0, 700), "Colombia": (4.6, -74.1, 400), "Corea del Norte": (40.1, 127.2, 200),
    "Corea del Sur": (36.5, 127.8, 150), "Cuba": (21.5, -79.0, 300), "Egipto": (26.8, 30.8, 400),
    "Emiratos Árabes": (24.0, 54.0, 150), "España": (40.3, -3.7, 350), "Estados Unidos": (39.8, -98.6, 700),
    "Etiopía": (9.1, 40.5, 400), "Filipinas": (12.9, 121.8, 400), "Francia": (46.6, 2.2, 350),
    "India": (22.0, 79.0, 700), "Indonesia": (-2.5, 118.0, 700), "Irak": (33.2, 43.7, 300),
    "Irán": (32.4, 53.7, 500), "Israel": (31.0, 34.9, 120), "Italia": (42.8, 12.6, 300), "Japón": (36.2, 138.3, 350),
    "Kazajistán": (48.0, 67.0, 600), "Libia": (26.3, 17.2, 500), "México": (23.6, -102.5, 600),
    "Nigeria": (9.1, 8.7, 400), "Pakistán": (29.5, 69.0, 400), "Polonia": (52.1, 19.4, 250),
    "Reino Unido": (54.0, -2.0, 250), "Rusia": (56.0, 45.0, 700), "Siria": (35.0, 38.5, 200),
    "Sudáfrica": (-30.6, 22.9, 500), "Taiwán": (23.7, 121.0, 150), "Turquía": (39.0, 35.2, 400),
    "Ucrania": (49.0, 31.4, 400), "Venezuela": (7.1, -66.2, 400), "Vietnam": (16.0, 107.8, 400),
    "Yemen": (15.6, 48.5, 300),
}
ZONAS_PAIS = {"Rusia": ["rusia_oeste", "siberia"], "Corea del Norte": ["corea"], "Irán": ["iran"], "India": ["india"],
              "Pakistán": ["pakistan"], "China": ["china"], "Estados Unidos": ["eeuu"]}


def clave_origen(o):
    return o if isinstance(o, str) else o["clave"]


def registrar_origen(o):
    if isinstance(o, str):
        return o
    ORIGENES[o["clave"]] = {"nombre": o["nombre"], "caja": tuple(o["caja"]), "mar": False, "propio": True}
    return o["clave"]


def origen_propio(nombre, lat, lon, radio_km=300.0):
    r = min(max(radio_km, 150.0), 700.0)
    dlat = r / 111.32
    dlon = r / (111.32 * max(math.cos(math.radians(lat)), 0.2))
    plano = "".join(ch for ch in nombre.lower() if ch.isalnum())[:24] or f"{lat:.1f}_{lon:.1f}"
    return {"clave": "x_" + plano, "nombre": nombre,
            "caja": [round(max(lat - dlat, -80.0), 3), round(min(lat + dlat, 80.0), 3), round(lon - dlon, 3), round(lon + dlon, 3)]}


def ciudad(nombre, valor=None, activa=True):
    lat, lon, r, v = CIUDADES[nombre]
    return Zona(nombre, lat, lon, r, v if valor is None else valor, activa)


def todas_ciudades():
    return [ciudad(n, activa=False) for n in CIUDADES]


def en_origen(lat, lon, origenes=None):
    for k, o in ORIGENES.items():
        if origenes is not None and k not in origenes:
            continue
        la0, la1, lo0, lo1 = o["caja"]
        if la0 <= lat <= la1 and lo0 <= lon <= lo1:
            return k
    return None


def punto_origen(rng, clave):
    la0, la1, lo0, lo1 = ORIGENES[clave]["caja"]
    return float(rng.uniform(la0, la1)), float(rng.uniform(lo0, lo1))


def circulo(lat, lon, d, n=72):
    return [destino(lat, lon, 360.0 * i / n, d) for i in range(n + 1)]


def merc_y(lat):
    lat = max(-84.0, min(84.0, lat))
    return math.degrees(math.asinh(math.tan(math.radians(lat))))


def merc_y_vec(lat):
    return np.degrees(np.arcsinh(np.tan(np.radians(np.clip(lat, -84.0, 84.0)))))


def lat_de_y(y):
    return math.degrees(math.atan(math.sinh(math.radians(y))))


def desenvolver(lon, ref):
    return ref + ((lon - ref + 180.0) % 360.0 - 180.0)


def desenvolver_seq(lons, ref):
    salida = []
    prev = ref
    for lo in lons:
        prev = desenvolver(lo, prev)
        salida.append(prev)
    return salida


def visible(P, S):
    return float(np.dot(P - S, S)) >= 0.0
