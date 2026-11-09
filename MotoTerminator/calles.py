import heapq
import json
import math
import os
import re
import shutil
import time
import urllib.parse
import urllib.request

import numpy as np

import config as C

from terreno import DX, M, MU, RR, RUGO, maximo_adelante

AQUI = os.path.dirname(os.path.abspath(__file__))
CARPETA = os.path.join(AQUI, "datos")
CARPETA_DRON = os.path.join(os.path.dirname(AQUI), "DronEntregas", "datos")
CARPETA_TESELAS = os.path.join(CARPETA, "teselas")
AGENTE = "MotoTerminatorSim/1.0 (simulador educativo)"
M_POR_GRADO = 6378137.0 * math.pi / 180

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
TAM_PROPIO = 2000.0
TAM_DRON = (5200.0, 3600.0)
SERVIDORES_OVERPASS = ("https://overpass-api.de/api/interpreter",
                       "https://overpass.kumi.systems/api/interpreter",
                       "https://overpass.private.coffee/api/interpreter")
URL_SATELITE = ("https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/"
                "MapServer/tile/{z}/{y}/{x}")
ATRIBUCION = "Imagen: Esri, Maxar, Earthstar Geographics · Calles: © colaboradores de OpenStreetMap"
TIPOS = ("motorway", "trunk", "primary", "secondary", "tertiary", "unclassified", "residential",
         "living_street", "motorway_link", "trunk_link", "primary_link", "secondary_link",
         "tertiary_link")
CONSULTA = ('[out:json][timeout:180];way["highway"~"^(' + "|".join(TIPOS) + ')$"]({b});'
            'out geom tags;')


class Zona:

    def __init__(self, nombre, centro, ancho=TAM_PROPIO, alto=TAM_PROPIO, m_por_px=1.0,
                 carpeta=CARPETA):
        lat, lon = centro
        self.nombre, self.centro = nombre, (lat, lon)
        self.ancho, self.alto, self.m_por_px, self.carpeta = ancho, alto, m_por_px, carpeta
        self.k_lon = M_POR_GRADO * math.cos(math.radians(lat))
        self.k_lat = M_POR_GRADO
        self.sur = lat - alto / 2 / self.k_lat
        self.norte = lat + alto / 2 / self.k_lat
        self.oeste = lon - ancho / 2 / self.k_lon
        self.este = lon + ancho / 2 / self.k_lon
        base = "".join(c if c.isalnum() else "_" for c in nombre.lower())
        self.clave = f"{base}_{lat:.4f}_{lon:.4f}".replace("-", "m").replace(".", "p")
        if (ancho, alto) not in ((TAM_PROPIO, TAM_PROPIO), TAM_DRON):
            self.clave += f"_{ancho:.0f}x{alto:.0f}"

    def contiene(self, lat, lon, margen=0.0):
        x, y = self.a_metros(lat, lon)
        return margen <= x <= self.ancho - margen and margen <= y <= self.alto - margen

    def a_metros(self, lat, lon):
        return (lon - self.oeste) * self.k_lon, (self.norte - lat) * self.k_lat

    def a_latlon(self, x, y):
        return self.norte - y / self.k_lat, self.oeste + x / self.k_lon

    def archivo(self, sufijo):
        return os.path.join(self.carpeta, f"{self.clave}_{sufijo}")


ARCHIVO_SESION = os.path.join(AQUI, "sesion.json")


def _dentro(ruta, base=None):
    base = os.path.normcase(os.path.abspath(base or AQUI))
    try:
        r = os.path.normcase(os.path.abspath(ruta))
        return os.path.commonpath([r, base]) == base
    except (ValueError, TypeError):
        return False


def _archivo_meta(clave, carpeta=None):
    return os.path.join(carpeta or CARPETA, f"{clave}_zona.json")


def _leer_meta(clave, carpeta=None):
    try:
        with open(_archivo_meta(clave, carpeta), encoding="utf-8") as f:
            m = json.load(f)
        return m if all(k in m for k in ("ancho", "alto", "m_por_px", "centro")) else None
    except (OSError, ValueError, TypeError):
        return None


def _zona_desde_meta(clave, meta, nombre=None):
    z = Zona(nombre or meta.get("nombre") or clave, tuple(meta["centro"]), float(meta["ancho"]),
             float(meta["alto"]), float(meta["m_por_px"]), carpeta=CARPETA)
    z.clave = clave
    return z


def _copia_local(zona):
    if _dentro(zona.carpeta):
        return zona
    local = Zona(zona.nombre, zona.centro, zona.ancho, zona.alto, zona.m_por_px, carpeta=CARPETA)
    local.clave = zona.clave
    meta = _leer_meta(local.clave)
    if os.path.exists(local.archivo("osm.json")) and meta is None:
        local.clave += "_dron"
        meta = _leer_meta(local.clave)
    try:
        os.makedirs(CARPETA, exist_ok=True)
        for sufijo in ("osm.json", "satelite.jpg"):
            origen, destino = zona.archivo(sufijo), local.archivo(sufijo)
            if os.path.exists(origen) and not os.path.exists(destino):
                tmp = destino + ".tmp"
                shutil.copyfile(origen, tmp)
                os.replace(tmp, destino)
        if meta is None:
            tmp = _archivo_meta(local.clave) + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump({"nombre": zona.nombre, "centro": list(zona.centro), "ancho": zona.ancho,
                           "alto": zona.alto, "m_por_px": zona.m_por_px, "clave": local.clave,
                           "origen": "DronEntregas"}, f, ensure_ascii=False, indent=1)
            os.replace(tmp, _archivo_meta(local.clave))
    except OSError:
        return zona if os.path.exists(zona.archivo("osm.json")) else local
    return local


def guardar_sesion(modo, zona=None, ruta=None):
    datos = {"modo": modo, "superficie": getattr(C, "CALLES_SUPERFICIE", "pavimento"),
             "circuito": getattr(C, "CALLES_CIRCUITO", "no"),
             "plan": "automatico" if getattr(C, "PLAN_AUTOMATICO", True) else "manual",
             "clima": (getattr(C, "CLIMA_MANUAL", None) or
                       ("automatico" if getattr(C, "CLIMA_AUTOMATICO", True) else "despejado"))}
    if ruta is not None:
        datos["ruta"] = [list(ruta[0]), list(ruta[1])]
        vuelta = ruta[2] if len(ruta) > 2 else "no"
        if vuelta in ("misma", "otra"):
            datos["ruta_circuito"] = vuelta
    if zona is not None:
        if not _dentro(zona.carpeta):
            zona = _copia_local(zona)
        datos["zona"] = {"nombre": zona.nombre, "centro": list(zona.centro), "ancho": zona.ancho,
                         "alto": zona.alto, "m_por_px": zona.m_por_px, "clave": zona.clave}
        if _dentro(zona.carpeta):
            datos["zona"]["carpeta"] = os.path.relpath(zona.carpeta, AQUI).replace(os.sep, "/")
    try:
        tmp = ARCHIVO_SESION + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(datos, f, ensure_ascii=False, indent=1)
        os.replace(tmp, ARCHIVO_SESION)
    except OSError:
        pass


def _zona_de_sesion(z):
    zona = Zona(z["nombre"], tuple(z["centro"]), float(z["ancho"]), float(z["alto"]),
                float(z["m_por_px"]), carpeta=CARPETA)
    claves = [z["clave"]] if z.get("clave") else []
    if zona.clave not in claves:
        claves.append(zona.clave)
    x = zona.m_por_px
    sufijo = f"_{zona.ancho:.0f}x{zona.alto:.0f}"
    if (zona.ancho, zona.alto) == (TAM_DRON[0] * x, TAM_DRON[1] * x) and zona.clave.endswith(sufijo):
        claves.append(zona.clave[:-len(sufijo)] + f"_x{x:g}".replace(".", "p"))
    claves += [c + "_dron" for c in list(claves)]
    rel = z.get("carpeta") or "datos"
    carpeta = rel if os.path.isabs(rel) else os.path.join(AQUI, rel)
    for clave in claves:
        for c in ([carpeta] if _dentro(carpeta) else []) + [CARPETA]:
            if os.path.exists(os.path.join(c, f"{clave}_osm.json")):
                zona.clave, zona.carpeta = clave, os.path.abspath(c)
                return zona
    if not _dentro(carpeta) and os.path.isdir(carpeta):
        for clave in claves:
            if os.path.exists(os.path.join(carpeta, f"{clave}_osm.json")):
                zona.clave, zona.carpeta = clave, carpeta
                return _copia_local(zona)
    zona.clave = claves[0]
    return zona


def cargar_sesion():
    try:
        with open(ARCHIVO_SESION, encoding="utf-8") as f:
            d = json.load(f)
        z = d.get("zona")
        zona = _zona_de_sesion(z) if z else None
        if d.get("superficie") in SUPERFICIES:
            C.CALLES_SUPERFICIE = d["superficie"]
        if d.get("circuito") in ("no", "misma", "otra"):
            C.CALLES_CIRCUITO = d["circuito"]
        C.PLAN_AUTOMATICO = d.get("plan", "automatico") != "manual"
        clima = d.get("clima", "automatico")
        if clima == "automatico":
            C.CLIMA_AUTOMATICO, C.CLIMA_MANUAL = True, None
        elif clima == "despejado":
            C.CLIMA_AUTOMATICO, C.CLIMA_MANUAL = False, None
        else:
            C.CLIMA_AUTOMATICO, C.CLIMA_MANUAL = False, clima
        r = d.get("ruta")
        ruta = (tuple(r[0]), tuple(r[1])) if r else None
        if ruta and d.get("ruta_circuito") in ("misma", "otra"):
            ruta = ruta + (d["ruta_circuito"],)
        return d.get("modo", "terreno"), zona, ruta
    except (OSError, ValueError, KeyError, TypeError, IndexError):
        return "terreno", None, None


def _candidata(nombre, centro):
    dron = Zona(nombre, centro, *TAM_DRON, carpeta=CARPETA_DRON)
    for clave in (dron.clave, dron.clave + "_dron"):
        meta = _leer_meta(clave)
        if meta is not None and os.path.exists(os.path.join(CARPETA, f"{clave}_osm.json")):
            return _zona_desde_meta(clave, meta, nombre)
    if os.path.exists(dron.archivo("osm.json")):
        return dron
    return Zona(nombre, centro)


def zona_para(nombre, centro=None):
    centro = centro or ZONAS[nombre]
    return _copia_local(_candidata(nombre, centro))


def _num(t):
    return float(t.replace("m", "-").replace("p", "."))


def zona_para_puntos(a, b, nombre=None):
    for n, centro in ZONAS.items():
        z = _candidata(n, centro)
        if os.path.exists(z.archivo("osm.json")) and z.contiene(*a, 250) and z.contiene(*b, 250):
            return _copia_local(z)
    for arch in (sorted(os.listdir(CARPETA_DRON)) if os.path.isdir(CARPETA_DRON) else ()):
        m = re.match(r"(.+)_(m?\d+p\d+)_(m?\d+p\d+)(?:_x(\d+(?:p\d+)?))?_osm\.json$", arch)
        if not m:
            continue
        clave = arch[:-len("_osm.json")]
        if _leer_meta(clave) is not None:
            continue
        x = _num(m[4]) if m[4] else 1.0
        z = Zona(nombre or f"Zona {_num(m[2]):.4f}, {_num(m[3]):.4f}", (_num(m[2]), _num(m[3])),
                 TAM_DRON[0] * x, TAM_DRON[1] * x, x, carpeta=CARPETA_DRON)
        z.clave = clave
        if (os.path.exists(z.archivo("satelite.jpg")) and z.contiene(*a, 250)
                and z.contiene(*b, 250)):
            return _copia_local(z)
    for arch in (sorted(os.listdir(CARPETA)) if os.path.isdir(CARPETA) else ()):
        if not arch.endswith("_osm.json"):
            continue
        clave = arch[:-len("_osm.json")]
        meta = _leer_meta(clave)
        if meta is not None:
            z = _zona_desde_meta(clave, meta, nombre)
        else:
            m = re.match(r"(.+)_(m?\d+p\d+)_(m?\d+p\d+)(?:_(\d+)x(\d+))?_osm\.json$", arch)
            if not m:
                continue
            ancho, alto = (float(m[4]), float(m[5])) if m[4] else (TAM_PROPIO, TAM_PROPIO)
            z = Zona(nombre or f"Zona {_num(m[2]):.4f}, {_num(m[3]):.4f}", (_num(m[2]), _num(m[3])),
                     ancho, alto, max(1.0, ancho / 2500))
            z.clave = clave
        if z.contiene(*a, 250) and z.contiene(*b, 250):
            return z
    centro = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
    k_lon = M_POR_GRADO * math.cos(math.radians(centro[0]))
    ancho = abs(a[1] - b[1]) * k_lon + 900
    alto = abs(a[0] - b[0]) * M_POR_GRADO + 900
    lado = min(max(TAM_PROPIO, ancho, alto), 8000.0)
    lado = math.ceil(lado / 500) * 500
    if lado == TAM_PROPIO:
        return Zona(nombre or f"Zona {centro[0]:.4f}, {centro[1]:.4f}", centro)
    return Zona(nombre or f"Zona {centro[0]:.4f}, {centro[1]:.4f}", centro, lado, lado,
                max(1.0, lado / 2500))


_COORD_SUFIJO = re.compile(
    r"(?<![\d.])(?P<signo>[-+])?(?P<grados>\d{1,3}(?:\.\d+)?)(?:\s*(?P<marca>°))?"
    r"(?:\s*(?P<min>\d{1,2}(?:\.\d+)?)\s*')?"
    r"(?:\s*(?P<seg>\d{1,2}(?:\.\d+)?)\s*\")?"
    r"(?:\s*(?P<hemi>[NSEW])(?![A-Z]))?")
_COORD_PREFIJO = re.compile(
    r"(?:(?<![A-Z])(?P<hemi>[NSEW])\s*)?(?<![\d.])(?P<signo>[-+])?(?P<grados>\d{1,3}(?:\.\d+)?)"
    r"(?:\s*(?P<marca>°))?"
    r"(?:\s*(?P<min>\d{1,2}(?:\.\d+)?)\s*')?"
    r"(?:\s*(?P<seg>\d{1,2}(?:\.\d+)?)\s*\")?")
_ESPACIOS = re.compile(
    r"(?<![\d.])(?P<grados>\d{1,3})\s+(?P<min>\d{1,2}(?:\.\d+)?)(?:\s+(?P<seg>\d{1,2}(?:\.\d+)?))?"
    r"\s*(?P<hemi>[NSEW])(?![A-Z])")
_LATITUD = {"N", "S"}
_NEGATIVO = {"S", "W"}
_SIMBOLOS = (("′", "'"), ("’", "'"), ("‘", "'"), ("´", "'"), ("`", "'"), ("ʹ", "'"),
             ("″", '"'), ("“", '"'), ("”", '"'), ("ʺ", '"'), ("¨", '"'), ("''", '"'),
             ("º", "°"), ("˚", "°"), ("ᵒ", "°"), ("−", "-"), ("–", "-"), ("—", "-"))
_PALABRAS = ((r"OESTE|WEST", "W"), (r"ESTE|EAST", "E"), (r"NORTE|NORTH", "N"),
             (r"SUR|SOUTH", "S"), (r"GRADOS?|DEG", "°"), (r"MIN(?:UTOS?)?", "'"),
             (r"SEG(?:UNDOS?)?|SEC", '"'))


def _normalizar(texto):
    t = texto.upper()
    for viejo, nuevo in _SIMBOLOS:
        t = t.replace(viejo, nuevo)
    for patron, letra in _PALABRAS:
        t = re.sub(rf"(?<![A-Z]){patron}(?![A-Z])", letra, t)
    t = re.sub(r"(?<![A-Z])O(?![A-Z])", "W", t)
    t = re.sub(r"[A-Z]{2,}", " ", t)
    m = re.fullmatch(r"\s*([-+]?\d{1,3}),(\d+)\s*[;\s]\s*([-+]?\d{1,3}),(\d+)\s*", t)
    if m:
        t = f"{m[1]}.{m[2]} {m[3]}.{m[4]}"
    return t


def leer_coordenadas(texto):
    texto = (texto or "").strip()
    m = (re.search(r"!3d(-?\d+\.\d+)!4d(-?\d+\.\d+)", texto) or
         re.search(r"@(-?\d+\.\d+),\s*(-?\d+\.\d+)", texto) or
         re.search(r"[?&](?:q|query|center|ll)=(-?\d+\.\d+),\s*(-?\d+\.\d+)", texto))
    if m:
        return _validar(float(m.group(1)), float(m.group(2)))
    texto = _normalizar(texto)
    espacios = list(_ESPACIOS.finditer(texto))
    if len(espacios) >= 2 and not re.search(r"[°'\"]", texto):
        vals = []
        for m in espacios[:2]:
            v = float(m["grados"]) + float(m["min"]) / 60 + float(m["seg"] or 0) / 3600
            vals.append((-v if m["hemi"] in _NEGATIVO else v, m["hemi"]))
        (a, ha), (b, hb) = vals
        if ha not in _LATITUD and hb in _LATITUD:
            a, b = b, a
        return _validar(a, b)
    primero = re.search(r"[NSEW\d]", texto)
    patron = _COORD_PREFIJO if primero and primero.group() in "NSEW" else _COORD_SUFIJO
    candidatos = []
    for m in patron.finditer(texto):
        if float(m["min"] or 0) >= 60 or float(m["seg"] or 0) >= 60:
            continue
        valor = float(m["grados"]) + float(m["min"] or 0) / 60 + float(m["seg"] or 0) / 3600
        hemi = m["hemi"] or ""
        if m["signo"] == "-" or hemi in _NEGATIVO:
            valor = -valor
        fuerte = "." in m["grados"] or bool(m["marca"] or m["min"] or hemi)
        candidatos.append((valor, hemi, fuerte))
    fuertes = [c for c in candidatos if c[2]]
    elegidos = fuertes if len(fuertes) >= 2 else candidatos
    if len(elegidos) < 2:
        return None
    (a, hemi_a, _), (b, hemi_b, _) = elegidos[:2]
    if (hemi_a and hemi_a not in _LATITUD) or (hemi_b in _LATITUD) or             (not hemi_a and not hemi_b and abs(a) > 90 >= abs(b)):
        a, b = b, a
    return _validar(a, b)


def _validar(lat, lon):
    return (lat, lon) if -85 < lat < 85 and -180 <= lon <= 180 else None


def url_google_maps(lat, lon):
    return (f"https://www.google.com/maps/@?api=1&map_action=map&center={lat:.6f},{lon:.6f}"
            f"&zoom=18&basemap=satellite")


def _descargar(url, datos=None, intentos=2, espera=3.0):
    ultimo = None
    for k in range(intentos):
        try:
            req = urllib.request.Request(url, data=datos, headers={"User-Agent": AGENTE})
            with urllib.request.urlopen(req, timeout=200) as r:
                return r.read()
        except Exception as error:
            ultimo = error
            time.sleep(espera * (k + 1))
    raise RuntimeError(f"{url.split('?')[0]}: {ultimo}")


def datos_calles(zona, avisar=print):
    ruta = zona.archivo("osm.json")
    if os.path.exists(ruta):
        with open(ruta, encoding="utf-8") as f:
            return json.load(f)
    ruta = _a_datos(zona).archivo("osm.json")
    caja = f"{zona.sur},{zona.oeste},{zona.norte},{zona.este}"
    cuerpo = urllib.parse.urlencode({"data": CONSULTA.replace("{b}", caja)}).encode()
    errores = []
    for servidor in SERVIDORES_OVERPASS:
        avisar(f"Descargando calles de {zona.nombre} ({servidor.split('/')[2]})…")
        try:
            crudo = json.loads(_descargar(servidor, cuerpo))
            break
        except Exception as e:
            errores.append(str(e))
    else:
        raise RuntimeError("Los servidores de OpenStreetMap no respondieron (pueden estar "
                           "saturados; intenta en unos minutos).\n" + "\n".join(errores))
    datos = [{"t": "w", "id": e["id"], "tags": e.get("tags", {}),
              "g": [[round(p["lat"], 6), round(p["lon"], 6)] for p in e.get("geometry", [])]}
             for e in crudo.get("elements", []) if e.get("type") == "way"]
    os.makedirs(zona.carpeta, exist_ok=True)
    with open(ruta + ".tmp", "w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False, separators=(",", ":"))
    os.replace(ruta + ".tmp", ruta)
    return datos


def _a_datos(zona):
    if not _dentro(zona.carpeta):
        zona.carpeta = CARPETA
    return zona


def _tesela(lat, lon, z):
    n = 2 ** z
    return ((lon + 180) / 360 * n,
            (1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * n)


def imagen_satelital(zona, avisar=print):
    try:
        from PIL import Image
    except ImportError:
        return None
    final = zona.archivo("satelite.jpg")
    if os.path.exists(final):
        return Image.open(final).convert("RGB")
    final = _a_datos(zona).archivo("satelite.jpg")
    z = 17 - max(0, round(math.log2(zona.m_por_px)))
    x0, y0 = _tesela(zona.norte, zona.oeste, z)
    x1, y1 = _tesela(zona.sur, zona.este, z)
    tx0, ty0, tx1, ty1 = int(x0), int(y0), int(x1), int(y1)
    total = (tx1 - tx0 + 1) * (ty1 - ty0 + 1)
    mosaico = Image.new("RGB", ((tx1 - tx0 + 1) * 256, (ty1 - ty0 + 1) * 256), (40, 44, 52))
    avisar(f"Descargando imagen satelital ({total} teselas, sólo la primera vez)…")
    import io
    for tx in range(tx0, tx1 + 1):
        for ty in range(ty0, ty1 + 1):
            try:
                datos = _tesela_en_cache(z, tx, ty)
                mosaico.paste(Image.open(io.BytesIO(datos)).convert("RGB"),
                              ((tx - tx0) * 256, (ty - ty0) * 256))
            except Exception:
                continue
    caja = ((x0 - tx0) * 256, (y0 - ty0) * 256, (x1 - tx0) * 256, (y1 - ty0) * 256)
    tam = (round(zona.ancho / zona.m_por_px), round(zona.alto / zona.m_por_px))
    img = mosaico.crop(tuple(round(v) for v in caja)).resize(tam, Image.LANCZOS)
    os.makedirs(zona.carpeta, exist_ok=True)
    img.save(final + ".tmp.jpg", quality=88)
    os.replace(final + ".tmp.jpg", final)
    return img


def _tesela_en_cache(z, tx, ty):
    ruta = os.path.join(CARPETA_TESELAS, str(z), f"{tx}_{ty}.jpg")
    try:
        with open(ruta, "rb") as f:
            return f.read()
    except OSError:
        pass
    datos = _descargar(URL_SATELITE.format(z=z, x=tx, y=ty), espera=1.0)
    try:
        os.makedirs(os.path.dirname(ruta), exist_ok=True)
        with open(ruta + ".tmp", "wb") as f:
            f.write(datos)
        os.replace(ruta + ".tmp", ruta)
    except OSError:
        pass
    return datos


class RedVial:

    def __init__(self, zona, avisar=print):
        self.zona = zona
        self.vecinos = {}
        self.pos = {}
        self.lineas = []
        for e in datos_calles(zona, avisar):
            tags, g = e.get("tags", {}), e.get("g") or []
            if tags.get("highway") not in TIPOS or len(g) < 2:
                continue
            nombre = tags.get("name") or tags.get("ref") or "calle sin nombre"
            sentido = tags.get("oneway", "")
            unico = sentido in ("yes", "1", "true") or tags.get("junction") == "roundabout"
            if sentido == "-1":
                g, unico = g[::-1], True
            nodos = [(round(a, 6), round(b, 6)) for a, b in g]
            for n in nodos:
                if n not in self.pos:
                    self.pos[n] = zona.a_metros(*n)
            pts = [self.pos[n] for n in nodos]
            self.lineas.append(([p[0] for p in pts], [p[1] for p in pts]))
            for a, b in zip(nodos[:-1], nodos[1:]):
                d = math.dist(self.pos[a], self.pos[b])
                if d < 0.01:
                    continue
                self.vecinos.setdefault(a, []).append((b, d, nombre))
                if not unico:
                    self.vecinos.setdefault(b, []).append((a, d, nombre))
        self.principal = self._red_principal()
        m = 150.0
        self.inicios = [n for n in self.principal
                        if m < self.pos[n][0] < zona.ancho - m and m < self.pos[n][1] < zona.alto - m]
        if len(self.inicios) < 10:
            raise RuntimeError(f"No se encontraron suficientes calles en {zona.nombre}.")

    def _red_principal(self):
        nodos = list(self.pos)
        inversa = {}
        for a, vs in self.vecinos.items():
            for b, _, _ in vs:
                inversa.setdefault(b, []).append(a)
        orden, visto = [], set()
        for raiz in nodos:
            if raiz in visto:
                continue
            visto.add(raiz)
            pila = [(raiz, iter(self.vecinos.get(raiz, ())))]
            while pila:
                n, it = pila[-1]
                for v, _, _ in it:
                    if v not in visto:
                        visto.add(v)
                        pila.append((v, iter(self.vecinos.get(v, ()))))
                        break
                else:
                    pila.pop()
                    orden.append(n)
        mejor, asignado = set(), set()
        for raiz in reversed(orden):
            if raiz in asignado:
                continue
            comp, pila = {raiz}, [raiz]
            asignado.add(raiz)
            while pila:
                n = pila.pop()
                for v in inversa.get(n, ()):
                    if v not in asignado:
                        asignado.add(v)
                        comp.add(v)
                        pila.append(v)
            if len(comp) > len(mejor):
                mejor = comp
        return mejor

    def nodo_cercano(self, x, y, salida=True):
        if not hasattr(self, "_claves"):
            self._claves = list(self.principal)
            self._nodos = np.array([self.pos[n] for n in self._claves])
        d = np.hypot(self._nodos[:, 0] - x, self._nodos[:, 1] - y)
        i = int(np.argmin(d))
        return self._claves[i], float(d[i])

    def ruta_entre(self, a, b):
        inicio, da = self.nodo_cercano(*a, salida=True)
        fin, db = self.nodo_cercano(*b, salida=False)
        if max(da, db) > 120:
            raise RuntimeError("El punto de salida o de llegada está a más de 120 m de una "
                               "calle; acércalo a una calle.")
        dist, previo = {inicio: 0.0}, {}
        cola = [(0.0, inicio)]
        while cola:
            d, n = heapq.heappop(cola)
            if n == fin:
                break
            if d > dist.get(n, 1e18):
                continue
            for v, w, nombre in self.vecinos.get(n, ()):
                nd = d + w
                if nd < dist.get(v, 1e18):
                    dist[v], previo[v] = nd, (n, nombre)
                    heapq.heappush(cola, (nd, v))
        if fin not in dist:
            raise RuntimeError("No hay forma de llegar de A a B por calles de esta zona "
                               "respetando los sentidos.")
        nodos, nombres = [fin], []
        while nodos[-1] != inicio:
            n, nombre = previo[nodos[-1]]
            nodos.append(n)
            nombres.append(nombre)
        nodos.reverse()
        nombres.reverse()
        if dist[fin] < 40:
            raise RuntimeError("La salida y la llegada están demasiado cerca (menos de 40 m).")
        if any(self._esquinas_malas(nodos)):
            sano = self._sin_vueltas_u(inicio, fin)
            if sano is None:
                raise RuntimeError("No hay forma de llegar de A a B por calles de esta zona "
                                   "sin dar una vuelta en U o una esquina demasiado cerrada.")
            nodos, nombres = sano
        return [self.pos[n] for n in nodos], nombres

    def ruta(self, rng, largo_min, largo_max):
        for _ in range(60):
            inicio = self.inicios[rng.integers(len(self.inicios))]
            dist, previo = {inicio: 0.0}, {}
            cola = [(0.0, inicio)]
            candidatos = []
            while cola:
                d, n = heapq.heappop(cola)
                if d > dist.get(n, 1e18) or d > largo_max:
                    continue
                if d >= largo_min:
                    candidatos.append(n)
                for v, w, nombre in self.vecinos.get(n, ()):
                    nd = d + w
                    if nd < dist.get(v, 1e18):
                        dist[v], previo[v] = nd, (n, nombre)
                        heapq.heappush(cola, (nd, v))
            if not candidatos:
                continue
            fin = candidatos[rng.integers(len(candidatos))]
            nodos, nombres = [fin], []
            while nodos[-1] != inicio:
                n, nombre = previo[nodos[-1]]
                nodos.append(n)
                nombres.append(nombre)
            nodos.reverse()
            nombres.reverse()
            if any(self._esquinas_malas(nodos)):
                sano = self._sin_vueltas_u(inicio, fin)
                if sano is None:
                    continue
                nodos, nombres = sano
                largo = sum(math.dist(self.pos[a], self.pos[b]) for a, b in zip(nodos[:-1], nodos[1:]))
                if self._esquinas_malas(nodos)[1] or largo > 1.25 * largo_max:
                    continue
            return [self.pos[n] for n in nodos], nombres
        raise RuntimeError("No se encontró una ruta del largo pedido en esta zona.")

    def _sin_vueltas_u(self, inicio, fin):
        prohibidos = set()
        aceptable = None
        for _ in range(40):
            try:
                nodos, nombres = self._buscar(inicio, None, fin, None, prohibidos)
            except RuntimeError:
                break
            malas_u, malas_k = self._esquinas_malas(nodos)
            if not malas_u:
                aceptable = (nodos, nombres)
                if not malas_k:
                    break
            nuevos = [t for t in malas_u + malas_k if t not in prohibidos]
            if not nuevos:
                break
            prohibidos.update(nuevos)
        return aceptable

    def _giro(self, p, n, v):
        (px, py), (nx, ny), (vx, vy) = self.pos[p], self.pos[n], self.pos[v]
        a = math.atan2(ny - py, nx - px)
        b = math.atan2(vy - ny, vx - nx)
        return abs(math.degrees((b - a + math.pi) % (2 * math.pi) - math.pi))

    def _penal_giro(self, p, n, v, prohibidos=()):
        if p is None:
            return 0.0
        if v == p or (p, n, v) in prohibidos:
            return None
        ang = self._giro(p, n, v)
        if ang > U_GRADOS:
            return None
        if ang > 100.0:
            return 40.0 + 6.0 * (ang - 100.0)
        return 8.0 if ang > 60.0 else 0.0

    def _expandir(self, inicio_e, fin=None, mult=None, prohibidos=(), radio=None):
        if fin is not None:
            meta_x, meta_y = self.pos[fin]

            def h(n):
                x, y = self.pos[n]
                return math.hypot(x - meta_x, y - meta_y)
        else:
            def h(n):
                return 0.0
        g = {inicio_e: 0.0}
        padre = {}
        cont = 0
        cola = [(h(inicio_e[1]), cont, inicio_e)]
        while cola:
            f, _, e = heapq.heappop(cola)
            p, n = e
            d = g[e]
            if f > d + h(n) + 1e-9:
                continue
            if n == fin and e != inicio_e:
                return g, padre, e
            for v, w, nombre in self.vecinos.get(n, ()):
                if v == p:
                    continue
                extra = self._penal_giro(p, n, v, prohibidos)
                if extra is None:
                    continue
                nd = d + w * (mult(n, v) if mult else 1.0) + extra
                if radio is not None and nd > radio:
                    continue
                ev = (n, v)
                if nd < g.get(ev, 1e18):
                    g[ev] = nd
                    padre[ev] = (e, nombre)
                    cont += 1
                    heapq.heappush(cola, (nd + h(v), cont, ev))
        return g, padre, None

    @staticmethod
    def _camino(padre, inicio_e, llegada):
        nodos, nombres, e = [llegada[1]], [], llegada
        while e != inicio_e:
            e, nombre = padre[e]
            nodos.append(e[1])
            nombres.append(nombre)
        nodos.reverse()
        nombres.reverse()
        return nodos, nombres

    def _buscar(self, inicio, previo0, fin, mult=None, prohibidos=()):
        inicio_e = (previo0, inicio)
        _, padre, llegada = self._expandir(inicio_e, fin, mult, prohibidos)
        if llegada is None:
            raise RuntimeError("No hay forma de ir y volver por calles de esta zona respetando "
                               "los sentidos y sin dar vueltas en U.")
        return self._camino(padre, inicio_e, llegada)

    def _vuelta_misma(self, ida, prohibidos):
        inversas = {(b, a) for a, b in zip(ida[:-1], ida[1:])}
        mult = lambda a, b: 1.0 if (a, b) in inversas else 20.0
        s = np.r_[0.0, np.cumsum([math.dist(self.pos[a], self.pos[b])
                                  for a, b in zip(ida[:-1], ida[1:])])]
        x_b = s[-1]
        inicio_e = (ida[-2], ida[-1])
        g, padre, _ = self._expandir(inicio_e, None, None, prohibidos, radio=1000.0)
        llegan = {}
        for (p, n), d in g.items():
            if p is not None:
                llegan.setdefault(n, []).append((d, p))
        mejor = None
        for j in range(1, len(ida) - 1):
            sig = ida[j - 1]
            if (ida[j], sig) not in inversas or ida[j] not in llegan:
                continue
            for d, p in llegan[ida[j]]:
                if p == ida[j + 1] and (p, ida[j]) in inversas:
                    continue
                extra = self._penal_giro(p, ida[j], sig, prohibidos)
                if extra is None:
                    continue
                score = d + extra + 3.0 * (x_b - s[j])
                if mejor is None or score < mejor[0]:
                    mejor = (score, (p, ida[j]))
        if mejor is None:
            return self._buscar(ida[-1], ida[-2], ida[0], mult, prohibidos)
        union = mejor[1]
        n1, nom1 = self._camino(padre, inicio_e, union)
        if union[1] == ida[0]:
            return n1, nom1
        n2, nom2 = self._buscar(union[1], union[0], ida[0], mult, prohibidos)
        return n1 + n2[1:], nom1 + nom2

    def _esquinas_malas(self, nodos):
        malas_u, malas_k = [], []
        if len(nodos) < 3:
            return malas_u, malas_k
        pts = [self.pos[n] for n in nodos]
        P, s, total, u, rumbo = _geometria(pts)
        crudo = np.unwrap(np.arctan2(np.gradient(np.interp(u, s, P[:, 1])),
                                     np.gradient(np.interp(u, s, P[:, 0]))))
        w = max(2, int(_U_METROS / 0.5))
        rango = maximo_adelante(crudo, w) + maximo_adelante(-crudo, w)
        zonas_u = u[np.degrees(rango) > U_GRADOS]
        xs = np.arange(0.0, total, DX)
        kappa = np.gradient(np.interp(xs, u, rumbo), DX)
        zonas_k = xs[np.abs(kappa) > limite_kappa_asfalto()]
        for zonas, salida, ancho in ((zonas_u, malas_u, _U_METROS), (zonas_k, malas_k, 0.0)):
            if not len(zonas):
                continue
            cortes = np.flatnonzero(np.diff(zonas) > 5.0)
            for a, b in zip(np.r_[0, cortes + 1], np.r_[cortes, len(zonas) - 1]):
                x0, x1 = zonas[a] - 12.0, zonas[b] + ancho + 12.0
                cand = [j for j in range(1, len(nodos) - 1) if x0 <= s[j] <= x1]
                if not cand:
                    j = int(np.clip(np.searchsorted(s, zonas[a]), 1, len(nodos) - 2))
                    cand = [j]
                j = max(cand, key=lambda j: self._giro(nodos[j - 1], nodos[j], nodos[j + 1]))
                t = (nodos[j - 1], nodos[j], nodos[j + 1])
                if t not in salida:
                    salida.append(t)
        return malas_u, malas_k

    def _circuito_nodos(self, inicio, fin, vuelta):
        if vuelta not in ("misma", "otra"):
            raise ValueError(f"vuelta debe ser 'misma' u 'otra', no {vuelta!r}")
        prohibidos = set()
        aceptable = None
        mult_ida = None
        if vuelta == "misma":
            if not hasattr(self, "_doble"):
                self._doble = {(a, b) for a, vs in self.vecinos.items() for b, _, _ in vs
                               if any(c == a for c, _, _ in self.vecinos.get(b, ()))}
            doble = self._doble
            mult_ida = lambda a, b: 1.0 if (a, b) in doble else _PREF_DOBLE
        for _ in range(30):
            try:
                ida, nom_ida = self._buscar(inicio, None, fin, mult_ida, prohibidos)
                aristas = set(zip(ida[:-1], ida[1:]))
                if vuelta == "otra":
                    usadas = aristas | {(b, a) for a, b in aristas}
                    mult = lambda a, b: 10.0 if (a, b) in usadas else 1.0
                    vta, nom_vta = self._buscar(fin, ida[-2], inicio, mult, prohibidos)
                else:
                    vta, nom_vta = self._vuelta_misma(ida, prohibidos)
            except RuntimeError:
                break
            nodos = ida + vta[1:]
            malas_u, malas_k = self._esquinas_malas(nodos)
            if not malas_u:
                aceptable = (ida, nom_ida, vta, nom_vta, bool(malas_k))
                if not malas_k:
                    break
            nuevos = [t for t in malas_u + malas_k if t not in prohibidos]
            if not nuevos:
                break
            prohibidos.update(nuevos)
        if aceptable is None:
            raise RuntimeError("No se pudo trazar el circuito de ida y vuelta sin dar una "
                               "vuelta en U (las calles alrededor de B o de A no lo permiten); "
                               "mueve B o A a otra esquina.")
        ida, nom_ida, vta, nom_vta, cerrada = aceptable
        nodos = ida + vta[1:]
        pts = [self.pos[n] for n in nodos]
        nombres = list(nom_ida) + ["↩ " + n for n in nom_vta]
        P = np.array(pts)
        s = np.r_[0.0, np.cumsum(np.hypot(*np.diff(P, axis=0).T))]
        x_b = float(s[len(ida) - 1])
        largo_vuelta = float(s[-1]) - x_b
        ida_ar = set(zip(ida[:-1], ida[1:]))
        ida_ambos = ida_ar | {(b, a) for a, b in ida_ar}
        lv = [(a, b, math.dist(self.pos[a], self.pos[b]), nm)
              for (a, b), nm in zip(zip(vta[:-1], vta[1:]), nom_vta)]
        inv = {(b, a) for a, b in ida_ar}
        m_inv = sum(d for a, b, d, _ in lv if (a, b) in inv)
        comp = sum(d for a, b, d, _ in lv if (a, b) in ida_ambos)
        if vuelta == "misma":
            tramos, act = [], None
            for a, b, d, nm in lv:
                if (a, b) in inv:
                    act = None
                    continue
                if act is None:
                    act = [0.0, []]
                    tramos.append(act)
                act[0] += d
                if nm not in act[1]:
                    act[1].append(nm)
            pct = 100 * m_inv / max(x_b, 1e-9)
            txt = f"por la misma ruta al revés (repite {pct:.0f}% de la ida)"
            if tramos and lv and (lv[0][0], lv[0][1]) not in inv:
                d, nm = tramos.pop(0)
                txt += f"; para no dar vuelta en U, en B rodea por {', '.join(nm)} ({d:.0f} m)"
            if tramos:
                txt += ("; desvío por sentido único en " +
                        "; ".join(f"{', '.join(nm)} ({d:.0f} m)" for d, nm in tramos))
            if m_inv < 0.05 * x_b:
                doble = getattr(self, "_doble", set())
                unico = sum(math.dist(self.pos[a], self.pos[b]) for a, b in ida_ar
                            if (a, b) not in doble)
                causa = ("la ida es de sentido único" if unico > 0.5 * x_b else
                         "no hay cómo reincorporarse a la ida sin dar vuelta en U")
                txt = (f"no puede regresar por la misma ruta ({causa}): regresa por la "
                       f"alternativa más corta ({', '.join(dict.fromkeys(nm for *_, nm in lv))})")
        else:
            txt = (f"por otra ruta (comparte {comp:.0f} m con la ida, "
                   f"{100 * comp / max(largo_vuelta, 1e-9):.0f}% del regreso)")
        if cerrada:
            txt += "; alguna esquina es más cerrada que el agarre del asfalto: se suaviza"
        extra = {"modo": vuelta, "x_b": x_b, "vuelta": txt, "largo_ida": x_b,
                 "largo_vuelta": largo_vuelta, "n_ida": len(ida),
                 "comparte_m": comp, "inversa_m": m_inv}
        return pts, nombres, extra

    def ruta_circuito(self, a_xy, b_xy, vuelta="otra"):
        inicio, da = self.nodo_cercano(*a_xy, salida=True)
        fin, db = self.nodo_cercano(*b_xy, salida=False)
        if max(da, db) > 120:
            raise RuntimeError("El punto de salida o de llegada está a más de 120 m de una "
                               "calle; acércalo a una calle.")
        if inicio == fin or math.dist(self.pos[inicio], self.pos[fin]) < 20:
            raise RuntimeError("La salida y la llegada están demasiado cerca (menos de 40 m).")
        pts, nombres, extra = self._circuito_nodos(inicio, fin, vuelta)
        if extra["largo_ida"] < 40:
            raise RuntimeError("La salida y la llegada están demasiado cerca (menos de 40 m).")
        return pts, nombres, extra

    def circuito(self, rng, largo_min, largo_max, vuelta="otra"):
        if not hasattr(self, "_inicios_set"):
            self._inicios_set = set(self.inicios)
        mejor, err_mejor = None, (1e18, 0.0)
        razones = [2.3]
        for intento in range(80):
            if intento >= 30 and mejor is not None and err_mejor[0] == 0.0:
                break
            inicio = self.inicios[rng.integers(len(self.inicios))]
            razon = float(np.median(razones))
            piso, tope = max(40.0, 0.2 * largo_min, 0.9 * largo_min / razon), max(60.0, largo_max / razon)
            tope = max(tope, 1.5 * piso)
            dist = {inicio: 0.0}
            cola = [(0.0, inicio)]
            cand = []
            while cola:
                d, n = heapq.heappop(cola)
                if d > dist.get(n, 1e18):
                    continue
                if d >= piso and n in self._inicios_set:
                    cand.append((n, d))
                for v, w, _ in self.vecinos.get(n, ()):
                    nd = d + w
                    if nd <= tope and nd < dist.get(v, 1e18):
                        dist[v] = nd
                        heapq.heappush(cola, (nd, v))
            if not cand:
                continue
            objetivo = rng.uniform(largo_min, largo_max) / razon
            cand.sort(key=lambda c: abs(c[1] - objetivo))
            fin, d_ab = cand[rng.integers(min(6, len(cand)))]
            try:
                pts, nombres, extra = self._circuito_nodos(inicio, fin, vuelta)
            except RuntimeError:
                continue
            total = extra["largo_ida"] + extra["largo_vuelta"]
            razones.append(total / max(d_ab, 1.0))
            err = max(largo_min - total, total - largo_max, 0.0)
            lv = max(extra["largo_vuelta"], 1e-9)
            fiel = (extra["inversa_m"] / lv if vuelta == "misma"
                    else 1.0 - extra["comparte_m"] / lv)
            if err == 0.0 and fiel >= (0.6 if vuelta == "misma" else 0.9):
                return pts, nombres, extra
            clave = (err, -fiel)
            if clave < err_mejor:
                mejor, err_mejor = (pts, nombres, extra), clave
        if mejor is None:
            raise RuntimeError("No se encontró un circuito de ida y vuelta sin vueltas en U "
                               "en esta zona.")
        total = mejor[2]["largo_ida"] + mejor[2]["largo_vuelta"]
        if not largo_min <= total <= largo_max:
            mejor[2]["aviso"] = (f"no hay circuito de {largo_min:.0f}–{largo_max:.0f} m; se usa "
                                 f"uno de {total:.0f} m")
        return mejor


U_GRADOS = 150.0
_U_METROS = 25.0
_PREF_DOBLE = 1.6


def limite_kappa_asfalto():
    return min(C.A_LAT_MAX, 0.85 * MU[M["asfalto"]] * C.G) / C.V_DISENO ** 2


def _geometria(pts):
    P = np.array(pts)
    P[:, 1] *= -1
    seg = np.hypot(*np.diff(P, axis=0).T)
    s = np.r_[0.0, np.cumsum(seg)]
    total = s[-1]
    u = np.arange(0.0, total, 0.5)
    x, y = np.interp(u, s, P[:, 0]), np.interp(u, s, P[:, 1])
    rumbo = np.unwrap(np.arctan2(np.gradient(y), np.gradient(x)))
    k = 22
    rumbo = np.convolve(np.pad(rumbo, k, mode="edge"), np.ones(2 * k + 1) / (2 * k + 1),
                        mode="same")[k:-k]
    return P, s, total, u, rumbo


def largo_ruta(nivel):
    return min(250.0 + 100.0 * (nivel - 1), 950.0)


def descripcion_nivel_ciudad(nivel):
    return f"Nivel {nivel}: rutas de unos {largo_ruta(nivel):.0f} m entre calles reales"


from superficies import SUPERFICIES, generar as _generar_superficie


class PistaCalle:

    def __init__(self, red, nivel, semilla, ruta=None, superficie=None, circuito=None):
        rng = np.random.default_rng(semilla)
        self.superficie = superficie or getattr(C, "CALLES_SUPERFICIE", "pavimento")
        self.red, self.zona, self.nivel, self.semilla = red, red.zona, nivel, semilla
        self.personalizada = ruta is not None
        modo = circuito or getattr(C, "CALLES_CIRCUITO", "no")
        if ruta is None:
            largo = largo_ruta(nivel)
            if modo in ("misma", "otra"):
                ruta = red.circuito(rng, 0.8 * largo, 1.2 * largo, modo)
            else:
                ruta = red.ruta(rng, 0.8 * largo, 1.2 * largo)
        elif len(ruta) == 2 and circuito in ("misma", "otra"):
            ruta = red.ruta_circuito(ruta[0][0], ruta[0][-1], circuito)
        if len(ruta) > 2:
            pts, nombres, extra = ruta[:3]
        else:
            (pts, nombres), extra = ruta, None
        self.extra = dict(extra) if extra else None
        self.circuito = self.extra.get("modo", "otra") if self.extra else "no"
        self.x_b = float(self.extra["x_b"]) if self.extra else None
        P, s, total, u, rumbo = _geometria(pts)

        self.xs = np.arange(0.0, total, DX)
        n = len(self.xs)
        self.rumbo = np.interp(self.xs, u, rumbo)
        self.kappa = np.gradient(self.rumbo, DX)
        limite = limite_kappa_asfalto()
        self.kappa_recortada = bool(np.abs(self.kappa).max() > limite)
        if self.kappa_recortada:
            self.kappa = np.clip(self.kappa, -limite, limite)
        self.kmax = maximo_adelante(np.abs(self.kappa), int(C.VENTANA_CURVAS / DX))
        self.mapa_x = P[0, 0] + np.cumsum(np.cos(self.rumbo)) * DX
        self.mapa_y = P[0, 1] + np.cumsum(np.sin(self.rumbo)) * DX
        idx = np.searchsorted(s, self.xs, side="right") - 1
        idx = np.clip(idx, 0, len(nombres) - 1)
        calles = []
        a = 0
        for i in range(1, n + 1):
            if i == n or nombres[idx[i]] != nombres[idx[a]]:
                calles.append((self.xs[a], self.xs[i - 1] + DX, nombres[idx[a]], "asfalto"))
                a = i
        self.calles = []
        for _, _, nombre, _ in calles:
            if not self.calles or self.calles[-1] != nombre:
                self.calles.append(nombre)
        self.longitud = self.xs[-1]
        self.salida = 6.0
        self.meta = self.longitud - 8.0
        self.tiempo_max = (self.meta - self.salida) / 3.0 + 20.0
        if self.superficie != "pavimento":
            _generar_superficie(self, rng, nivel, nombres, idx, self.superficie)
            self.mu, self.rr = MU[self.mat], RR[self.mat]
            self.mu_min = -maximo_adelante(-self.mu, int(C.VENTANA_CURVAS / DX))
        else:
            self.hs = np.zeros(n)
            self.mat = np.full(n, M["asfalto"], dtype=np.int64)
            self.mu, self.rr = MU[self.mat], RR[self.mat]
            self.mu_min = self.mu.copy()
            self.rugo = np.full(n, RUGO[M["asfalto"]] * 0.5)
            self.secciones = calles

    def altura(self, x):
        if self.superficie != "pavimento":
            return np.interp(x, self.xs, self.hs)
        return np.zeros_like(np.asarray(x, dtype=float))

    def indice(self, x):
        i = (np.asarray(x) * (1 / DX)).astype(np.int64)
        return np.minimum(np.maximum(i, 0), len(self.xs) - 1)

    def latlon(self, x):
        i = int(self.indice(x))
        return self.zona.a_latlon(self.mapa_x[i], -self.mapa_y[i])

    def resumen(self):
        if self.circuito != "no":
            ida = [c for c in self.calles if not c.startswith("↩ ")]
            vta = [c for c in self.calles if c.startswith("↩ ")]
            texto = " → ".join(ida) + "  → [B] →  " + " → ".join(vta)
        else:
            texto = " → ".join(self.calles)
        if self.superficie != "pavimento":
            vistos = []
            for _, _, r, m in self.secciones:
                t = f"{r.replace('_', ' ')}/{m}"
                if m != "asfalto" and t not in vistos:
                    vistos.append(t)
            texto += ("  ·  " + ", ".join(vistos)) if vistos else ""
        return texto
