import io
import json
import math
import os
import re
import time
import urllib.parse
import urllib.request

import numpy as np

import config as C

A_WGS = 6378137.0
F_WGS = 1 / 298.257223563
E2 = F_WGS * (2 - F_WGS)
EP2 = E2 / (1 - E2)

_NUMERO = re.compile(
    r"(?<![\w.])(?P<signo>[-+−])?\s*(?P<grados>\d{1,3}(?:\.\d+)?)\s*(?P<marca>°|º|˚|grados)?"
    r"(?:\s*(?P<min>\d{1,2}(?:\.\d+)?)\s*['′’])?"
    r"(?:\s*(?P<seg>\d{1,2}(?:\.\d+)?)\s*(?:\"|″|”|''))?"
    r"(?:\s*(?P<hemi>[NSEOW](?![a-zA-Z])|(?i:norte|sur|este|oeste|north|south|east|west)\b))?")
_LATITUD = {"N", "S", "NORTE", "SUR", "NORTH", "SOUTH"}
_NEGATIVO = {"S", "O", "W", "SUR", "OESTE", "SOUTH", "WEST"}


def _arco_meridiano(phi):
    e4, e6 = E2 * E2, E2 * E2 * E2
    return A_WGS * ((1 - E2 / 4 - 3 * e4 / 64 - 5 * e6 / 256) * phi
                    - (3 * E2 / 8 + 3 * e4 / 32 + 45 * e6 / 1024) * np.sin(2 * phi)
                    + (15 * e4 / 256 + 45 * e6 / 1024) * np.sin(4 * phi)
                    - (35 * e6 / 3072) * np.sin(6 * phi))


class TransversaMercator:
    def __init__(self, lat0, lon0, k0=1.0, fe=0.0, fn=0.0):
        self.lat0, self.lon0, self.k0, self.fe, self.fn = float(lat0), float(lon0), float(k0), float(fe), float(fn)
        self.m0 = float(_arco_meridiano(math.radians(lat0)))

    def adelante(self, lat, lon):
        phi = np.radians(np.asarray(lat, dtype=float))
        lam = np.radians(np.asarray(lon, dtype=float) - self.lon0)
        s, c = np.sin(phi), np.cos(phi)
        n = A_WGS / np.sqrt(1 - E2 * s * s)
        t = np.tan(phi) ** 2
        cc = EP2 * c * c
        a = lam * c
        m = _arco_meridiano(phi)
        x = self.k0 * n * (a + (1 - t + cc) * a ** 3 / 6 + (5 - 18 * t + t * t + 72 * cc - 58 * EP2) * a ** 5 / 120)
        y = self.k0 * (m - self.m0 + n * np.tan(phi) * (a * a / 2 + (5 - t + 9 * cc + 4 * cc * cc) * a ** 4 / 24
                                                        + (61 - 58 * t + t * t + 600 * cc - 330 * EP2) * a ** 6 / 720))
        return x + self.fe, y + self.fn

    def inversa(self, x, y):
        x = np.asarray(x, dtype=float) - self.fe
        y = np.asarray(y, dtype=float) - self.fn
        e4, e6 = E2 * E2, E2 * E2 * E2
        m = self.m0 + y / self.k0
        mu = m / (A_WGS * (1 - E2 / 4 - 3 * e4 / 64 - 5 * e6 / 256))
        e1 = (1 - math.sqrt(1 - E2)) / (1 + math.sqrt(1 - E2))
        p1 = (mu + (3 * e1 / 2 - 27 * e1 ** 3 / 32) * np.sin(2 * mu) + (21 * e1 ** 2 / 16 - 55 * e1 ** 4 / 32) * np.sin(4 * mu)
              + (151 * e1 ** 3 / 96) * np.sin(6 * mu) + (1097 * e1 ** 4 / 512) * np.sin(8 * mu))
        s, c = np.sin(p1), np.cos(p1)
        c1 = EP2 * c * c
        t1 = np.tan(p1) ** 2
        n1 = A_WGS / np.sqrt(1 - E2 * s * s)
        r1 = A_WGS * (1 - E2) / (1 - E2 * s * s) ** 1.5
        d = x / (n1 * self.k0)
        lat = p1 - (n1 * np.tan(p1) / r1) * (d * d / 2 - (5 + 3 * t1 + 10 * c1 - 4 * c1 * c1 - 9 * EP2) * d ** 4 / 24
                                              + (61 + 90 * t1 + 298 * c1 + 45 * t1 * t1 - 252 * EP2 - 3 * c1 * c1) * d ** 6 / 720)
        lon = (d - (1 + 2 * t1 + c1) * d ** 3 / 6 + (5 - 2 * c1 + 28 * t1 - 3 * c1 * c1 + 8 * EP2 + 24 * t1 * t1) * d ** 5 / 120) / c
        return np.degrees(lat), self.lon0 + np.degrees(lon)


def zona_utm(lat, lon):
    return int((lon + 180) // 6) + 1, lat >= 0


def utm(lat, lon, zona=None):
    if zona is None:
        zona = zona_utm(float(np.mean(lat)), float(np.mean(lon)))
    numero, norte = zona
    tm = TransversaMercator(0.0, numero * 6 - 183, 0.9996, 500000.0, 0.0 if norte else 10000000.0)
    e, n = tm.adelante(lat, lon)
    return e, n, zona


def epsg_utm(zona):
    numero, norte = zona
    return (32600 if norte else 32700) + numero


class Georef:
    def __init__(self, lat, lon, ancho, alto, nombre=""):
        self.lat, self.lon, self.ancho, self.alto, self.nombre = float(lat), float(lon), float(ancho), float(alto), nombre
        self.tm = TransversaMercator(lat, lon, 1.0, ancho / 2, alto / 2)
        self.zona_utm = zona_utm(lat, lon)

    def a_latlon(self, x, y):
        return self.tm.inversa(x, y)

    def a_local(self, lat, lon):
        return self.tm.adelante(lat, lon)

    def a_utm(self, x, y):
        lat, lon = self.a_latlon(x, y)
        e, n, _ = utm(lat, lon, self.zona_utm)
        return e, n

    def caja(self):
        lats, lons = self.a_latlon(np.array([0, self.ancho, 0, self.ancho]), np.array([0, 0, self.alto, self.alto]))
        return float(lats.min()), float(lons.min()), float(lats.max()), float(lons.max())

    def wkt(self):
        return ('PROJCS["Local TM",GEOGCS["WGS 84",DATUM["WGS_1984",SPHEROID["WGS 84",6378137,298.257223563]],'
                'PRIMEM["Greenwich",0],UNIT["degree",0.0174532925199433]],PROJECTION["Transverse_Mercator"],'
                f'PARAMETER["latitude_of_origin",{self.lat:.8f}],PARAMETER["central_meridian",{self.lon:.8f}],'
                f'PARAMETER["scale_factor",1],PARAMETER["false_easting",{self.ancho / 2:.3f}],'
                f'PARAMETER["false_northing",{self.alto / 2:.3f}],UNIT["metre",1]]')

    def a_dict(self):
        return {"lat": self.lat, "lon": self.lon, "ancho": self.ancho, "alto": self.alto, "nombre": self.nombre}

    @staticmethod
    def de_dict(d):
        return Georef(d["lat"], d["lon"], d["ancho"], d["alto"], d.get("nombre", ""))


def leer_coordenadas(texto):
    texto = (texto or "").strip()
    m = (re.search(r"!3d(-?\d+\.\d+)!4d(-?\d+\.\d+)", texto) or re.search(r"@(-?\d+\.\d+),\s*(-?\d+\.\d+)", texto))
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
    if (hemi_a and hemi_a not in _LATITUD) or (hemi_b in _LATITUD) or (not hemi_a and not hemi_b and abs(a) > 90 >= abs(b)):
        a, b = b, a
    return _validar(a, b)


def _validar(lat, lon):
    return (lat, lon) if -85 < lat < 85 and -180 <= lon <= 180 else None


def _descargar(url, datos=None, intentos=3, espera=1.5, tiempo=60):
    ultimo = None
    for k in range(intentos):
        try:
            req = urllib.request.Request(url, data=datos, headers={"User-Agent": C.AGENTE})
            with urllib.request.urlopen(req, timeout=tiempo) as r:
                return r.read()
        except Exception as error:
            ultimo = error
            time.sleep(espera * (k + 1))
    raise RuntimeError(f"No se pudo descargar {url.split('?')[0]}: {ultimo}")


def buscar_lugar(texto):
    c = leer_coordenadas(texto)
    if c is not None:
        return {"lat": c[0], "lon": c[1], "nombre": f"{c[0]:.5f}, {c[1]:.5f}"}
    datos = json.loads(_descargar(C.URL_BUSQUEDA.format(q=urllib.parse.quote(texto.strip()))).decode("utf-8"))
    if not datos:
        raise ValueError(f"No se encontró «{texto}»")
    d = datos[0]
    nombre = d.get("name") or d.get("display_name", texto).split(",")[0]
    return {"lat": float(d["lat"]), "lon": float(d["lon"]), "nombre": nombre}


def url_google_maps(lat, lon, zoom=16):
    return (f"https://www.google.com/maps/@?api=1&map_action=map&center={lat:.6f},{lon:.6f}"
            f"&zoom={zoom}&basemap=satellite")


def url_google_earth(lat, lon, elevacion=0.0, distancia=2500.0):
    return f"https://earth.google.com/web/@{lat:.6f},{lon:.6f},{elevacion:.0f}a,{distancia:.0f}d,35y,0h,45t,0r"


def _mercator(lat, lon, z):
    n = 2.0 ** z
    x = (np.asarray(lon) + 180.0) / 360.0 * n
    y = (1 - np.arcsinh(np.tan(np.radians(lat))) / math.pi) / 2 * n
    return x, y


def _mosaico(geo, url, z, carpeta, ext, avisar, modo="RGB"):
    from PIL import Image
    from scipy.ndimage import map_coordinates
    s, o, n, e = geo.caja()
    x0, y0 = _mercator(n, o, z)
    x1, y1 = _mercator(s, e, z)
    tx0, ty0, tx1, ty1 = int(x0) - 0, int(y0), int(x1), int(y1)
    total = (tx1 - tx0 + 1) * (ty1 - ty0 + 1)
    os.makedirs(carpeta, exist_ok=True)
    mosaico = np.zeros(((ty1 - ty0 + 1) * 256, (tx1 - tx0 + 1) * 256, 3), dtype=np.uint8)
    falta = np.ones(((ty1 - ty0 + 1), (tx1 - tx0 + 1)), dtype=bool)
    from concurrent.futures import ThreadPoolExecutor

    def bajar(t):
        tx, ty = t
        arch = os.path.join(carpeta, f"{z}_{tx}_{ty}.{ext}")
        try:
            if not os.path.exists(arch):
                datos = _descargar(url.format(z=z, x=tx, y=ty), intentos=3, espera=0.4, tiempo=20)
                with open(arch + ".tmp", "wb") as f:
                    f.write(datos)
                os.replace(arch + ".tmp", arch)
            return tx, ty, np.asarray(Image.open(arch).convert("RGB")), None
        except Exception as ex:
            return tx, ty, None, ex

    tareas = [(tx, ty) for tx in range(tx0, tx1 + 1) for ty in range(ty0, ty1 + 1)]
    with ThreadPoolExecutor(12) as ex:
        for hechas, (tx, ty, img, error) in enumerate(ex.map(bajar, tareas), 1):
            if img is not None:
                mosaico[(ty - ty0) * 256:(ty - ty0 + 1) * 256, (tx - tx0) * 256:(tx - tx0 + 1) * 256] = img
                falta[ty - ty0, tx - tx0] = False
            else:
                avisar(f"  tesela {tx},{ty} sin descargar: {error}")
            if hechas % 25 == 0 or hechas == total:
                avisar(f"  {hechas}/{total} teselas")
    if falta.all():
        raise RuntimeError("No se pudo descargar ninguna tesela (¿sin internet?)")
    return mosaico, tx0, ty0


def _malla_latlon(geo, nx, ny):
    res_x, res_y = geo.ancho / nx, geo.alto / ny
    xs = (np.arange(nx) + 0.5) * res_x
    ys = geo.alto - (np.arange(ny) + 0.5) * res_y
    X, Y = np.meshgrid(xs, ys)
    return geo.a_latlon(X, Y)


def _muestrear_mosaico(mosaico, tx0, ty0, z, lat, lon, orden=1):
    from scipy.ndimage import map_coordinates
    px, py = _mercator(lat, lon, z)
    cols = (px - tx0) * 256 - 0.5
    filas = (py - ty0) * 256 - 0.5
    if mosaico.ndim == 2:
        return map_coordinates(mosaico, [filas, cols], order=orden, mode="nearest")
    return np.stack([map_coordinates(mosaico[..., k].astype(np.float32), [filas, cols], order=orden, mode="nearest")
                     for k in range(mosaico.shape[2])], axis=-1)


def imagen_satelital(geo, nx, ny, avisar=print):
    carpeta = os.path.join(C.CARPETA_MAPAS, "satelite")
    z = C.ZOOM_SATELITE
    while z > 12:
        s, o, n, e = geo.caja()
        x0, y0 = _mercator(n, o, z)
        x1, y1 = _mercator(s, e, z)
        if (int(x1) - int(x0) + 1) * (int(y1) - int(y0) + 1) <= 120:
            break
        z -= 1
    avisar(f"Descargando imagen satelital (zoom {z})…")
    mosaico, tx0, ty0 = _mosaico(geo, C.URL_SATELITE, z, carpeta, "jpg", avisar)
    lat, lon = _malla_latlon(geo, nx, ny)
    rgb = _muestrear_mosaico(mosaico, tx0, ty0, z, lat, lon)
    return np.clip(rgb, 0, 255).astype(np.uint8)


def elevacion(geo, nx, ny, avisar=print):
    carpeta = os.path.join(C.CARPETA_MAPAS, "elevacion")
    z = C.ZOOM_ELEVACION
    avisar(f"Descargando elevación real (Terrain Tiles, zoom {z})…")
    mosaico, tx0, ty0 = _mosaico(geo, C.URL_ELEVACION, z, carpeta, "png", avisar)
    m = mosaico.astype(np.float64)
    alturas = m[..., 0] * 256 + m[..., 1] + m[..., 2] / 256 - 32768
    lat, lon = _malla_latlon(geo, nx, ny)
    return _muestrear_mosaico(alturas, tx0, ty0, z, lat, lon, orden=3).astype(np.float32)


CONSULTA_OSM = """[out:json][timeout:120];
(
  nwr["natural"="water"]({b});
  way["waterway"]({b});
  way["building"]({b});
  way["highway"]({b});
  nwr["landuse"="quarry"]({b});
  nwr["man_made"~"^(spoil_heap|mineshaft|adit|tailings_pond)$"]({b});
  nwr["landuse"="landfill"]({b});
  way["power"="line"]({b});
);
out geom tags;"""


def datos_osm(geo, avisar=print):
    s, o, n, e = geo.caja()
    clave = f"{geo.lat:.4f}_{geo.lon:.4f}_{geo.ancho:.0f}".replace("-", "m").replace(".", "p")
    ruta = os.path.join(C.CARPETA_MAPAS, "osm", f"osm_{clave}.json")
    if os.path.exists(ruta):
        with open(ruta, encoding="utf-8") as f:
            crudo = json.load(f)
    else:
        cuerpo = urllib.parse.urlencode({"data": CONSULTA_OSM.replace("{b}", f"{s},{o},{n},{e}")}).encode()
        crudo = None
        for servidor in C.SERVIDORES_OVERPASS:
            avisar(f"Descargando datos geoespaciales de OpenStreetMap ({servidor.split('/')[2]})…")
            try:
                crudo = json.loads(_descargar(servidor, cuerpo, intentos=1, tiempo=25))
                break
            except Exception as ex:
                avisar(f"  falló: {ex}")
        if crudo is None:
            raise RuntimeError("No se pudieron descargar los datos de OpenStreetMap")
        os.makedirs(os.path.dirname(ruta), exist_ok=True)
        with open(ruta + ".tmp", "w", encoding="utf-8") as f:
            json.dump(crudo, f)
        os.replace(ruta + ".tmp", ruta)
    return _osm_local(geo, crudo)


def _osm_local(geo, crudo):
    res = {"agua": [], "rios": [], "edificios": [], "caminos": [], "tajos": [], "residuos": [], "lineas": []}
    for el in crudo.get("elements", []):
        tags = el.get("tags", {})
        geoms = []
        if el["type"] == "way" and el.get("geometry"):
            geoms = [el["geometry"]]
        elif el["type"] == "relation":
            geoms = [m["geometry"] for m in el.get("members", []) if m.get("role") == "outer" and m.get("geometry")]
        for g in geoms:
            lat = np.array([p["lat"] for p in g])
            lon = np.array([p["lon"] for p in g])
            x, y = geo.a_local(lat, lon)
            pts = np.column_stack([x, y]).round(2).tolist()
            if len(pts) < 2:
                continue
            nombre = tags.get("name", "")
            if tags.get("natural") == "water" or tags.get("man_made") == "tailings_pond":
                res["agua"].append({"puntos": pts, "nombre": nombre})
            elif "waterway" in tags:
                res["rios"].append({"puntos": pts, "nombre": nombre})
            elif "building" in tags:
                res["edificios"].append({"puntos": pts, "nombre": nombre, "niveles": tags.get("building:levels")})
            elif "highway" in tags:
                res["caminos"].append({"puntos": pts, "nombre": nombre, "tipo": tags["highway"]})
            elif tags.get("landuse") == "quarry":
                res["tajos"].append({"puntos": pts, "nombre": nombre or "Tajo (OSM)"})
            elif tags.get("man_made") == "spoil_heap" or tags.get("landuse") == "landfill":
                res["residuos"].append({"puntos": pts, "nombre": nombre})
            elif tags.get("power") == "line":
                res["lineas"].append({"puntos": pts, "nombre": nombre})
    return res


def _coords_kml(geo, puntos, z=None):
    p = np.asarray(puntos, dtype=float)
    lat, lon = geo.a_latlon(p[:, 0], p[:, 1])
    zs = p[:, 2] if p.shape[1] > 2 else np.zeros(len(p))
    return " ".join(f"{b:.7f},{a:.7f},{c:.1f}" for a, b, c in zip(lat, lon, zs))


def _esc(t):
    return str(t).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def exportar_kml(geo, archivo, titulo, zonas=(), rutas=(), alertas=(), superposicion=None):
    estilos = {
        "extraccion": "ff9fd338", "restringida": "ff5f5fff", "acopio": "ff00b4f5", "vuelo": "ffffa44e",
    }
    partes = [f'<?xml version="1.0" encoding="UTF-8"?>\n<kml xmlns="http://www.opengis.net/kml/2.2"><Document><name>{_esc(titulo)}</name>']
    for t, col in estilos.items():
        partes.append(f'<Style id="z_{t}"><LineStyle><color>{col}</color><width>3</width></LineStyle>'
                      f'<PolyStyle><color>40{col[2:]}</color></PolyStyle></Style>')
    partes.append('<Style id="ruta"><LineStyle><color>ff3dd6f5</color><width>2</width></LineStyle></Style>')
    partes.append('<Style id="alerta"><IconStyle><color>ff5f5fff</color><scale>1.1</scale><Icon><href>'
                  'http://maps.google.com/mapfiles/kml/shapes/caution.png</href></Icon></IconStyle></Style>')
    if superposicion:
        img, nombre = superposicion
        s, o, n, e = geo.caja()
        partes.append(f'<GroundOverlay><name>{_esc(nombre)}</name><Icon><href>{_esc(img)}</href></Icon>'
                      f'<LatLonBox><north>{n}</north><south>{s}</south><east>{e}</east><west>{o}</west></LatLonBox></GroundOverlay>')
    if zonas:
        partes.append("<Folder><name>Zonas</name>")
        for z in zonas:
            pts = list(z["puntos"]) + [z["puntos"][0]]
            partes.append(f'<Placemark><name>{_esc(z["nombre"])}</name><styleUrl>#z_{z["tipo"]}</styleUrl><Polygon>'
                          f'<tessellate>1</tessellate><outerBoundaryIs><LinearRing><coordinates>{_coords_kml(geo, pts)}'
                          '</coordinates></LinearRing></outerBoundaryIs></Polygon></Placemark>')
        partes.append("</Folder>")
    if rutas:
        partes.append("<Folder><name>Vuelos</name>")
        for nombre, pts in rutas:
            partes.append(f'<Placemark><name>{_esc(nombre)}</name><styleUrl>#ruta</styleUrl><LineString>'
                          f'<altitudeMode>absolute</altitudeMode><coordinates>{_coords_kml(geo, pts)}</coordinates>'
                          '</LineString></Placemark>')
        partes.append("</Folder>")
    if alertas:
        partes.append("<Folder><name>Alertas</name>")
        for a in alertas:
            partes.append(f'<Placemark><name>{_esc(a["titulo"])}</name><description>{_esc(a.get("detalle", ""))}'
                          f'</description><styleUrl>#alerta</styleUrl><Point><coordinates>'
                          f'{_coords_kml(geo, [[a["x"], a["y"], 0]])}</coordinates></Point></Placemark>')
        partes.append("</Folder>")
    partes.append("</Document></kml>")
    with open(archivo, "w", encoding="utf-8") as f:
        f.write("".join(partes))
    return archivo


URL_GOOGLE_SESION = "https://tile.googleapis.com/v1/createSession?key={clave}"
URL_GOOGLE_TESELA = "https://tile.googleapis.com/v1/2dtiles/{z}/{x}/{y}?session={sesion}&key={clave}"
URL_GOOGLE_VISTA = ("https://tile.googleapis.com/tile/v1/viewport?session={sesion}&key={clave}&zoom={z}"
                    "&north={n}&south={s}&east={e}&west={o}")
ARCHIVO_CLAVE = os.path.join(C.RAIZ, "config_local.json")


def clave_google():
    try:
        with open(ARCHIVO_CLAVE, encoding="utf-8") as f:
            return json.load(f).get("google_maps_clave", "").strip() or os.environ.get("GOOGLE_MAPS_API_KEY", "")
    except (OSError, ValueError):
        return os.environ.get("GOOGLE_MAPS_API_KEY", "")


def guardar_clave_google(clave):
    datos = {}
    try:
        with open(ARCHIVO_CLAVE, encoding="utf-8") as f:
            datos = json.load(f)
    except (OSError, ValueError):
        pass
    datos["google_maps_clave"] = clave.strip()
    with open(ARCHIVO_CLAVE, "w", encoding="utf-8") as f:
        json.dump(datos, f)


def _google(url, cuerpo=None):
    import urllib.error
    datos = json.dumps(cuerpo).encode() if cuerpo is not None else None
    req = urllib.request.Request(url, data=datos, headers={"User-Agent": C.AGENTE, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.read()
    except urllib.error.HTTPError as ex:
        try:
            msj = json.loads(ex.read().decode("utf-8")).get("error", {}).get("message", "")
        except Exception:
            msj = ""
        raise RuntimeError(f"Google respondió {ex.code}: {msj or ex.reason}. Revisa que la clave sea válida y que "
                           "«Map Tiles API» esté activada en tu proyecto de Google Cloud")


def imagen_google(geo, nx, ny, clave, avisar=print):
    from concurrent.futures import ThreadPoolExecutor
    from PIL import Image
    if not clave:
        raise RuntimeError("Falta la clave de Google Maps Platform")
    avisar("Abriendo sesión de Google Maps (satélite)…")
    sesion = json.loads(_google(URL_GOOGLE_SESION.format(clave=clave),
                                {"mapType": "satellite", "language": "es-MX", "region": "MX"}))["session"]
    s, o, n, e = geo.caja()
    z = 20
    while z > 12:
        x0, y0 = _mercator(n, o, z)
        x1, y1 = _mercator(s, e, z)
        if (int(x1) - int(x0) + 1) * (int(y1) - int(y0) + 1) <= 160:
            break
        z -= 1
    x0, y0 = _mercator(n, o, z)
    x1, y1 = _mercator(s, e, z)
    tx0, ty0, tx1, ty1 = int(x0), int(y0), int(x1), int(y1)
    tareas = [(tx, ty) for tx in range(tx0, tx1 + 1) for ty in range(ty0, ty1 + 1)]
    mosaico = np.zeros(((ty1 - ty0 + 1) * 256, (tx1 - tx0 + 1) * 256, 3), dtype=np.uint8)
    avisar(f"Descargando satélite de Google (zoom {z}, {len(tareas)} teselas)…")

    def bajar(t):
        tx, ty = t
        datos = _google(URL_GOOGLE_TESELA.format(z=z, x=tx, y=ty, sesion=sesion, clave=clave))
        return tx, ty, np.asarray(Image.open(io.BytesIO(datos)).convert("RGB").resize((256, 256)))

    with ThreadPoolExecutor(8) as ex:
        for k, (tx, ty, img) in enumerate(ex.map(bajar, tareas)):
            mosaico[(ty - ty0) * 256:(ty - ty0 + 1) * 256, (tx - tx0) * 256:(tx - tx0 + 1) * 256] = img
            if (k + 1) % 20 == 0:
                avisar(f"  {k + 1}/{len(tareas)} teselas de Google")
    lat, lon = _malla_latlon(geo, nx, ny)
    rgb = np.clip(_muestrear_mosaico(mosaico, tx0, ty0, z, lat, lon), 0, 255).astype(np.uint8)
    try:
        vista = json.loads(_google(URL_GOOGLE_VISTA.format(sesion=sesion, clave=clave, z=z, n=n, s=s, e=e, o=o)))
        derechos = vista.get("copyright") or "Google"
    except Exception:
        derechos = "Google"
    return rgb, f"Imágenes © {derechos}" if "©" not in derechos else derechos


def google_earth_pro():
    rutas = [os.path.join(os.environ.get(v, ""), "Google", "Google Earth Pro", "client", "googleearth.exe")
             for v in ("ProgramFiles", "ProgramFiles(x86)", "LOCALAPPDATA")]
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\googleearth.exe") as k:
            rutas.insert(0, winreg.QueryValue(k, None))
    except Exception:
        pass
    return next((r for r in rutas if r and os.path.exists(r)), None)
