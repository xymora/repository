import io
import json
import math
import os
import re
import threading
import time
import urllib.parse
import urllib.request

import config as C

AGENTE = "DomoDefensaSim/1.0 (simulador educativo)"
URL_SATELITE = "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
URL_CALLES = "https://tile.openstreetmap.org/{z}/{x}/{y}.png"
URL_TRANSPORTE = "https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Transportation/MapServer/tile/{z}/{y}/{x}"
URL_NOMBRES = "https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}"
URL_PHOTON = "https://photon.komoot.io/api/?limit=1{f}&q={q}"
URL_BUSQUEDA = "https://nominatim.openstreetmap.org/search?format=json&limit=1&accept-language=es&q={q}"
ATRIBUCION = "Imagen: Esri, Maxar, Earthstar Geographics · Búsqueda: © colaboradores de OpenStreetMap"
VISTAS = ("terreno", "hibrido", "calles")
NOMBRES_VISTA = {"terreno": "Terreno", "hibrido": "Híbrido", "calles": "Calles y casas"}
CAPAS = {"terreno": (URL_SATELITE,), "hibrido": (URL_SATELITE, URL_TRANSPORTE, URL_NOMBRES), "calles": (URL_CALLES,)}
ZOOM_MAX = {"terreno": 18, "hibrido": 18, "calles": 19}
ATRIBUCIONES = {
    "terreno": "Imagen: Esri, Maxar, Earthstar Geographics",
    "hibrido": "Imagen y referencias: Esri, Maxar, Earthstar Geographics, HERE, Garmin",
    "calles": "Mapa: © colaboradores de OpenStreetMap",
}
_LIMITE = {"calles": threading.Semaphore(2)}
M_POR_GRADO = 6378137.0 * math.pi / 180
M_POR_PX_Z0 = 2 * math.pi * 6378137.0 / 256
ZOOM = 12
CARPETA = os.path.join(C.RAIZ, "mapas")

_NUMERO = re.compile(
    r"(?<![\w.])(?P<signo>[-+−])?\s*(?P<grados>\d{1,3}(?:\.\d+)?)\s*(?P<marca>°|º|˚|grados)?"
    r"(?:\s*(?P<min>\d{1,2}(?:\.\d+)?)\s*['′’])?"
    r"(?:\s*(?P<seg>\d{1,2}(?:\.\d+)?)\s*(?:\"|″|”|''))?"
    r"(?:\s*(?P<hemi>[NSEOW](?![a-zA-Z])|(?i:norte|sur|este|oeste|north|south|east|west)\b))?")
_LATITUD = {"N", "S", "NORTE", "SUR", "NORTH", "SOUTH"}
_NEGATIVO = {"S", "O", "W", "SUR", "OESTE", "SOUTH", "WEST"}


def leer_coordenadas(texto):
    texto = (texto or "").strip()
    m = (re.search(r"!3d(-?\d+\.\d+)!4d(-?\d+\.\d+)", texto) or
         re.search(r"@(-?\d+\.\d+),\s*(-?\d+\.\d+)", texto))
    if m:
        return _validar(float(m.group(1)), float(m.group(2)))
    candidatos = []
    for m in _NUMERO.finditer(texto):
        valor = float(m["grados"]) + float(m["min"] or 0) / 60 + float(m["seg"] or 0) / 3600
        hemi = (m["hemi"] or "").upper()
        if m["signo"] in ("-", "−") or hemi in _NEGATIVO:
            valor = -valor
        fuerte = "." in m["grados"] or bool(m["marca"] or m["min"] or hemi)
        candidatos.append((valor, hemi, fuerte))
    fuertes = [c for c in candidatos if c[2]]
    elegidos = fuertes if len(fuertes) >= 2 else candidatos
    if len(elegidos) < 2:
        return None
    (a, hemi_a, _), (b, hemi_b, _) = elegidos[:2]
    if (hemi_a and hemi_a not in _LATITUD) or (hemi_b in _LATITUD) or \
            (not hemi_a and not hemi_b and abs(a) > 90 >= abs(b)):
        a, b = b, a
    return _validar(a, b)


def _validar(lat, lon):
    return (lat, lon) if -85 < lat < 85 and -180 <= lon <= 180 else None


def _descargar(url, intentos=3, espera=1.5):
    ultimo = None
    for k in range(intentos):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": AGENTE})
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.read()
        except Exception as error:
            ultimo = error
            time.sleep(espera * (k + 1))
    raise RuntimeError(f"No se pudo descargar {url.split('?')[0]}: {ultimo}")


def _radio(lat, s, n, o, e):
    alto = (n - s) * M_POR_GRADO
    ancho = (e - o) * M_POR_GRADO * math.cos(math.radians(lat))
    return max(alto, ancho) / 2


def _nominatim(texto):
    datos = json.loads(_descargar(URL_BUSQUEDA.format(q=urllib.parse.quote(texto)), intentos=1).decode("utf-8"))
    if not datos:
        return None
    d = datos[0]
    lat, lon = float(d["lat"]), float(d["lon"])
    radio = _radio(lat, *(float(v) for v in d["boundingbox"])) if d.get("boundingbox") else None
    nombre = d.get("name") or d.get("display_name", texto).split(",")[0]
    return {"lat": lat, "lon": lon, "nombre": nombre, "radio": radio}


def _palabras(texto):
    import unicodedata
    plano = unicodedata.normalize("NFKD", texto.lower()).encode("ascii", "ignore").decode()
    return [w for w in re.findall(r"[a-z0-9]+", plano) if len(w) >= 4]


def _photon(texto):
    pedido = set(_palabras(texto))
    f = None
    for filtro in ("&osm_tag=place", ""):
        datos = json.loads(_descargar(URL_PHOTON.format(f=filtro, q=urllib.parse.quote(texto)), intentos=2).decode("utf-8"))
        if datos.get("features"):
            f = datos["features"][0]
            if pedido & set(_palabras(f.get("properties", {}).get("name", ""))):
                break
    if f is None:
        return None
    lon, lat = (float(v) for v in f["geometry"]["coordinates"])
    pr = f.get("properties", {})
    radio = None
    if pr.get("extent") and len(pr["extent"]) == 4:
        o, n, e, s = (float(v) for v in pr["extent"])
        radio = _radio(lat, min(s, n), max(s, n), min(o, e), max(o, e))
    return {"lat": lat, "lon": lon, "nombre": pr.get("name") or texto.split(",")[0], "radio": radio}


def _cache_busquedas():
    ruta = os.path.join(CARPETA, "busquedas.json")
    try:
        with open(ruta, encoding="utf-8") as f:
            return ruta, json.load(f)
    except Exception:
        return ruta, {}


def buscar_lugar(texto):
    c = leer_coordenadas(texto)
    if c is not None:
        return {"lat": c[0], "lon": c[1], "nombre": f"{c[0]:.4f}, {c[1]:.4f}", "radio": None}
    texto = " ".join(texto.split())
    clave = texto.lower()
    ruta, cache = _cache_busquedas()
    if clave in cache:
        return dict(cache[clave])
    res, errores = None, []
    for buscador in (_nominatim, _photon):
        try:
            res = buscador(texto)
        except Exception as ex:
            errores.append(str(ex))
            continue
        if res is not None:
            break
    if res is None:
        if errores and len(errores) == 2:
            raise RuntimeError("No se pudo buscar el lugar (¿sin internet?): " + errores[-1])
        raise ValueError(f"No se encontró «{texto}»")
    cache[clave] = res
    try:
        os.makedirs(CARPETA, exist_ok=True)
        with open(ruta, "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False)
    except Exception:
        pass
    return dict(res)


def atribucion(vista):
    return ATRIBUCIONES.get(vista, ATRIBUCIONES["terreno"]) + " · Búsqueda: © colaboradores de OpenStreetMap"


def url_google_maps(lat, lon):
    return (f"https://www.google.com/maps/@?api=1&map_action=map&center={lat:.6f},{lon:.6f}"
            f"&zoom=11&basemap=satellite")


def _tesela(lat, lon, z):
    n = 2 ** z
    x = (lon + 180) / 360 * n
    y = (1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * n
    return x, y


def limites_tesela(z, x, y):
    n = 2 ** z
    oeste, este = x / n * 360 - 180, (x + 1) / n * 360 - 180
    norte = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * y / n))))
    sur = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * (y + 1) / n))))
    return sur, oeste, norte, este


def zoom_para(m_por_px, lat, vista="terreno"):
    z = math.log2(M_POR_PX_Z0 * math.cos(math.radians(lat)) / max(m_por_px, 1e-6))
    return max(0, min(int(round(z)), ZOOM_MAX.get(vista, 18)))


def tesela(vista, z, x, y, carpeta=None):
    from PIL import Image
    ruta = os.path.join(carpeta or CARPETA, "teselas", vista, str(z), f"{x}_{y}.jpg")
    if os.path.exists(ruta):
        try:
            return Image.open(ruta).convert("RGB")
        except Exception:
            pass
    img = None
    limite = _LIMITE.get(vista)
    for url in CAPAS[vista]:
        if limite is not None:
            with limite:
                datos = _descargar(url.format(z=z, x=x, y=y), intentos=2, espera=0.5)
        else:
            datos = _descargar(url.format(z=z, x=x, y=y), intentos=2, espera=0.5)
        capa = Image.open(io.BytesIO(datos)).convert("RGBA")
        if capa.size != (256, 256):
            capa = capa.resize((256, 256))
        img = capa if img is None else Image.alpha_composite(img, capa)
    img = img.convert("RGB")
    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    img.save(ruta, quality=90)
    return img


class CargadorTeselas:
    def __init__(self, carpeta=None, hilos=4, maximo=240):
        self.carpeta = carpeta
        self.maximo = maximo
        self.pendientes = []
        self.encolados = set()
        self.fallidas = {}
        self.listas = []
        self.cv = threading.Condition()
        for _ in range(hilos):
            threading.Thread(target=self._trabajar, daemon=True).start()

    def pedir(self, clave):
        with self.cv:
            if clave in self.encolados or time.time() - self.fallidas.get(clave, -1e9) < 30:
                return
            self.encolados.add(clave)
            self.pendientes.append(clave)
            if len(self.pendientes) > self.maximo:
                self.encolados.discard(self.pendientes.pop(0))
            self.cv.notify()

    def recoger(self, n=24):
        with self.cv:
            listas, self.listas = self.listas[:n], self.listas[n:]
        return listas

    def en_curso(self):
        with self.cv:
            return len(self.encolados)

    def _trabajar(self):
        while True:
            with self.cv:
                while not self.pendientes:
                    self.cv.wait()
                clave = self.pendientes.pop()
            img = None
            try:
                img = tesela(*clave, carpeta=self.carpeta)
            except Exception:
                pass
            with self.cv:
                self.encolados.discard(clave)
                if img is None:
                    self.fallidas[clave] = time.time()
                else:
                    self.listas.append((clave, img))


class MapaReal:
    def __init__(self, lat, lon, nombre="", clave=None):
        self.lat, self.lon, self.nombre = float(lat), float(lon), nombre
        self.k_lon = M_POR_GRADO * math.cos(math.radians(lat))
        self.k_lat = M_POR_GRADO
        self.sur = lat - C.MAPA_H / 2 / self.k_lat
        self.norte = lat + C.MAPA_H / 2 / self.k_lat
        self.oeste = lon - C.MAPA_W / 2 / self.k_lon
        self.este = lon + C.MAPA_W / 2 / self.k_lon
        self.clave = clave or f"{lat:.3f}_{lon:.3f}".replace("-", "m").replace(".", "p")

    @classmethod
    def anclado(cls, lat, lon, x, y, nombre=""):
        lat_c = round(lat - (y - C.MAPA_H / 2) / M_POR_GRADO, 4)
        lon_c = round(lon - (x - C.MAPA_W / 2) / (M_POR_GRADO * math.cos(math.radians(lat_c))), 4)
        clave = "a" + f"{lat_c:.4f}_{lon_c:.4f}".replace("-", "m").replace(".", "p")
        return cls(lat_c, lon_c, nombre, clave)

    def a_metros(self, lat, lon):
        return (lon - self.oeste) * self.k_lon, (lat - self.sur) * self.k_lat

    def a_latlon(self, x, y):
        return self.sur + y / self.k_lat, self.oeste + x / self.k_lon

    def contiene(self, lat, lon, margen=8000.0):
        x, y = self.a_metros(lat, lon)
        return margen <= x <= C.MAPA_W - margen and margen <= y <= C.MAPA_H - margen

    def archivo(self, vista="terreno", carpeta=None):
        sufijo = "" if vista == "terreno" else f"_{vista}"
        return os.path.join(carpeta or CARPETA, f"mapa_{self.clave}{sufijo}.jpg")

    def imagen(self, avisar=print, carpeta=None, vista="terreno"):
        from PIL import Image
        carpeta = carpeta or CARPETA
        os.makedirs(carpeta, exist_ok=True)
        final = self.archivo(vista, carpeta)
        if os.path.exists(final):
            return Image.open(final).convert("RGB")
        z = ZOOM
        x0, y0 = _tesela(self.norte, self.oeste, z)
        x1, y1 = _tesela(self.sur, self.este, z)
        tx0, ty0, tx1, ty1 = int(x0), int(y0), int(x1), int(y1)
        total = (tx1 - tx0 + 1) * (ty1 - ty0 + 1)
        mosaico = Image.new("RGB", ((tx1 - tx0 + 1) * 256, (ty1 - ty0 + 1) * 256), (30, 34, 30))
        hechas = fallas = 0
        for tx in range(tx0, tx1 + 1):
            for ty in range(ty0, ty1 + 1):
                try:
                    mosaico.paste(tesela(vista, z, tx, ty, carpeta), ((tx - tx0) * 256, (ty - ty0) * 256))
                except Exception:
                    fallas += 1
                hechas += 1
                if hechas % 6 == 0:
                    avisar(f"Descargando mapa ({NOMBRES_VISTA.get(vista, vista).lower()})… {hechas}/{total}")
        if fallas == total:
            raise RuntimeError("No se pudo descargar el mapa (¿sin internet?)")
        caja = ((x0 - tx0) * 256, (y0 - ty0) * 256, (x1 - tx0) * 256, (y1 - ty0) * 256)
        img = mosaico.crop(tuple(round(v) for v in caja)).resize((1600, 1200), Image.LANCZOS)
        if fallas == 0:
            img.save(final, quality=88)
        return img
