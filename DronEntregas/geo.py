import io
import json
import math
import os
import re
import time
import urllib.parse
import urllib.request

import config as C

CARPETA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "datos")
AGENTE = "DronEntregasSim/1.0 (simulador educativo)"
M_POR_GRADO = 6378137.0 * math.pi / 180


class Zona:

    def __init__(self, nombre=None, centro=None, tamano=1.0):
        nombre = nombre or C.ZONA
        lat, lon = centro or C.ZONAS[nombre]
        self.nombre, self.centro, self.tamano = nombre, (lat, lon), tamano
        self.lat0 = lat
        self.k_lon = M_POR_GRADO * math.cos(math.radians(lat))
        self.k_lat = M_POR_GRADO
        self.ancho, self.alto = C.ANCHO_ZONA * tamano, C.ALTO_ZONA * tamano
        self.m_por_px = C.SATELITE_M_POR_PX * tamano
        self.sur = lat - self.alto / 2 / self.k_lat
        self.norte = lat + self.alto / 2 / self.k_lat
        self.oeste = lon - self.ancho / 2 / self.k_lon
        self.este = lon + self.ancho / 2 / self.k_lon
        base = "".join(c if c.isalnum() else "_" for c in nombre.lower())
        self.clave = f"{base}_{lat:.4f}_{lon:.4f}".replace("-", "m").replace(".", "p")
        if tamano != 1.0:
            self.clave += f"_x{tamano:g}".replace(".", "p")

    def descargada(self):
        return (os.path.exists(self.archivo("osm.json"), ) and
                os.path.exists(self.archivo("satelite.jpg")))

    def a_metros(self, lat, lon):
        return (lon - self.oeste) * self.k_lon, (self.norte - lat) * self.k_lat

    def a_latlon(self, x, y):
        return self.norte - y / self.k_lat, self.oeste + x / self.k_lon

    def archivo(self, sufijo):
        os.makedirs(CARPETA, exist_ok=True)
        return os.path.join(CARPETA, f"{self.clave}_{sufijo}")


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


def distancia_m(lat1, lon1, lat2, lon2):
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = (math.sin((p2 - p1) / 2) ** 2 +
         math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2)
    return 2 * 6371008.8 * math.asin(math.sqrt(a))


CONSULTA = """[out:json][timeout:240];
(
  way["building"]({b});
  nwr["amenity"~"^(pharmacy|restaurant|fast_food|hospital|prison)$"]({b});
  nwr["aeroway"="helipad"]({b});
  nwr["leisure"~"^(park|garden|pitch|stadium|playground|sports_centre)$"]({b});
  nwr["landuse"~"^(military|grass|recreation_ground|village_green)$"]({b});
  way["power"~"^(line|minor_line)$"]({b});
  node["power"="tower"]({b});
  nwr["man_made"~"^(mast|tower|communications_tower)$"]({b});
  way["highway"]["name"]({b});
);
out geom tags;"""


def _descargar(url, datos=None, intentos=3, espera=5.0):
    ultimo = None
    for k in range(intentos):
        try:
            req = urllib.request.Request(url, data=datos, headers={"User-Agent": AGENTE})
            with urllib.request.urlopen(req, timeout=300) as r:
                return r.read()
        except Exception as error:
            ultimo = error
            time.sleep(espera * (k + 1))
    raise RuntimeError(f"No se pudo descargar {url.split('?')[0]}: {ultimo}")


def datos_osm(zona, forzar=False, avisar=print):
    ruta = zona.archivo("osm.json")
    if os.path.exists(ruta) and not forzar:
        with open(ruta, encoding="utf-8") as f:
            return json.load(f)
    caja = f"{zona.sur},{zona.oeste},{zona.norte},{zona.este}"
    consulta = CONSULTA.replace("{b}", caja)
    cuerpo = urllib.parse.urlencode({"data": consulta}).encode()
    error = None
    for servidor in C.SERVIDORES_OVERPASS:
        avisar(f"Descargando datos de OpenStreetMap de {zona.nombre} ({servidor.split('/')[2]})...")
        try:
            crudo = json.loads(_descargar(servidor, cuerpo, intentos=2))
            break
        except Exception as e:
            error = e
            avisar(f"  falló: {e}")
    else:
        raise RuntimeError(f"No se pudieron descargar los datos de OpenStreetMap: {error}")
    datos = _simplificar(crudo)
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False, separators=(",", ":"))
    avisar(f"  {len(datos)} elementos guardados en {ruta}")
    return datos


def _simplificar(crudo):
    res = []
    for e in crudo.get("elements", []):
        d = {"t": e["type"][0], "id": e["id"], "tags": e.get("tags", {})}
        if e["type"] == "node":
            d["p"] = [round(e["lat"], 6), round(e["lon"], 6)]
        elif e["type"] == "way":
            d["g"] = [[round(p["lat"], 6), round(p["lon"], 6)] for p in e.get("geometry", [])]
        else:
            d["m"] = [[[round(p["lat"], 6), round(p["lon"], 6)] for p in m.get("geometry", [])]
                      for m in e.get("members", []) if m.get("role") == "outer" and m.get("geometry")]
        res.append(d)
    return res


def _tesela(lat, lon, z):
    n = 2 ** z
    x = (lon + 180) / 360 * n
    y = (1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * n
    return x, y


def imagen_satelital(zona, avisar=print):
    from PIL import Image

    final = zona.archivo("satelite.jpg")
    if os.path.exists(final):
        return Image.open(final).convert("RGB")
    z = C.SATELITE_ZOOM - round(math.log2(zona.tamano))
    x0, y0 = _tesela(zona.norte, zona.oeste, z)
    x1, y1 = _tesela(zona.sur, zona.este, z)
    tx0, ty0, tx1, ty1 = int(x0), int(y0), int(x1), int(y1)
    total = (tx1 - tx0 + 1) * (ty1 - ty0 + 1)
    carpeta = os.path.join(CARPETA, "teselas", str(z))
    os.makedirs(carpeta, exist_ok=True)
    mosaico = Image.new("RGB", ((tx1 - tx0 + 1) * 256, (ty1 - ty0 + 1) * 256), (40, 44, 52))
    avisar(f"Descargando imagen satelital ({total} teselas, sólo la primera vez)...")
    hechas = 0
    for tx in range(tx0, tx1 + 1):
        for ty in range(ty0, ty1 + 1):
            arch = os.path.join(carpeta, f"{tx}_{ty}.jpg")
            if not os.path.exists(arch):
                try:
                    datos = _descargar(C.URL_SATELITE.format(z=z, x=tx, y=ty), intentos=2,
                                       espera=1.0)
                    with open(arch, "wb") as f:
                        f.write(datos)
                except Exception as e:
                    avisar(f"  tesela {tx},{ty} sin descargar: {e}")
                    continue
            try:
                mosaico.paste(Image.open(arch).convert("RGB"), ((tx - tx0) * 256, (ty - ty0) * 256))
            except Exception:
                pass
            hechas += 1
            if hechas % 40 == 0:
                avisar(f"  {hechas}/{total}")
    caja = ((x0 - tx0) * 256, (y0 - ty0) * 256, (x1 - tx0) * 256, (y1 - ty0) * 256)
    tam = (round(zona.ancho / zona.m_por_px), round(zona.alto / zona.m_por_px))
    img = mosaico.crop(tuple(round(v) for v in caja)).resize(tam, Image.LANCZOS)
    img.save(final, quality=90)
    for tx in range(tx0, tx1 + 1):
        for ty in range(ty0, ty1 + 1):
            try:
                os.remove(os.path.join(carpeta, f"{tx}_{ty}.jpg"))
            except OSError:
                pass
    return img


def url_google_maps(lat, lon, satelite=True):
    capa = "&basemap=satellite" if satelite else ""
    return (f"https://www.google.com/maps/@?api=1&map_action=map&center={lat:.6f},{lon:.6f}"
            f"&zoom=18{capa}")


def _coords(zona, puntos):
    res = []
    for x, y, z in puntos:
        lat, lon = zona.a_latlon(x, y)
        res.append(f"{lon:.7f},{lat:.7f},{z:.1f}")
    return " ".join(res)


def _escapar(t):
    return t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def exportar_kml(zona, archivo, titulo, ruta=None, rutas_previas=(), vuelo=(), lugares=(),
                 zonas=(), descripcion=""):
    p = ['<?xml version="1.0" encoding="UTF-8"?>',
         '<kml xmlns="http://www.opengis.net/kml/2.2"><Document>',
         f"<name>{_escapar(titulo)}</name>",
         f"<description>{_escapar(descripcion)}</description>",
         '<Style id="plan"><LineStyle><color>ff00d7ff</color><width>3</width></LineStyle>'
         '<PolyStyle><color>3300d7ff</color></PolyStyle></Style>',
         '<Style id="previa"><LineStyle><color>99aaaaaa</color><width>2</width></LineStyle></Style>',
         '<Style id="vuelo"><LineStyle><color>fff7c34f</color><width>4</width></LineStyle>'
         '<PolyStyle><color>55f7c34f</color></PolyStyle></Style>',
         '<Style id="zona"><LineStyle><color>ff3d3def</color><width>2</width></LineStyle>'
         '<PolyStyle><color>553d3def</color></PolyStyle></Style>']

    def linea(nombre, estilo, pts):
        if len(pts) < 2:
            return
        p.append(f"<Placemark><name>{_escapar(nombre)}</name><styleUrl>#{estilo}</styleUrl>"
                 "<LineString><extrude>1</extrude><tessellate>1</tessellate>"
                 "<altitudeMode>relativeToGround</altitudeMode>"
                 f"<coordinates>{_coords(zona, pts)}</coordinates></LineString></Placemark>")

    if ruta is not None:
        linea(ruta.nombre + " (plan)", "plan", list(zip(ruta.x, ruta.y, ruta.alt)))
    for r in rutas_previas:
        linea(r.nombre + " (abandonada)", "previa", list(zip(r.x, r.y, r.alt)))
    linea("Vuelo real del dron", "vuelo", list(vuelo))
    for nombre, x, y, z in lugares:
        lat, lon = zona.a_latlon(x, y)
        p.append(f"<Placemark><name>{_escapar(nombre)}</name><Point>"
                 "<altitudeMode>relativeToGround</altitudeMode>"
                 f"<coordinates>{lon:.7f},{lat:.7f},{z:.1f}</coordinates></Point></Placemark>")
    for nombre, anillo in zonas:
        pts = anillo + anillo[:1]
        p.append(f"<Placemark><name>{_escapar(nombre)}</name><styleUrl>#zona</styleUrl>"
                 "<Polygon><extrude>1</extrude><altitudeMode>relativeToGround</altitudeMode>"
                 "<outerBoundaryIs><LinearRing><coordinates>"
                 f"{_coords(zona, [(x, y, C.TECHO) for x, y in pts])}"
                 "</coordinates></LinearRing></outerBoundaryIs></Polygon></Placemark>")
    p.append("</Document></kml>")
    os.makedirs(os.path.dirname(archivo), exist_ok=True)
    with open(archivo, "w", encoding="utf-8") as f:
        f.write("\n".join(p))
    return archivo
