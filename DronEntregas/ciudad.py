import math
import random

import config as C
from geo import Zona, datos_osm

HASH = 100.0


def dentro(x, y, pts):
    res = False
    j = len(pts) - 1
    for i in range(len(pts)):
        xi, yi = pts[i]
        xj, yj = pts[j]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
            res = not res
        j = i
    return res


def dist_segmento(x, y, ax, ay, bx, by):
    dx, dy = bx - ax, by - ay
    L2 = dx * dx + dy * dy
    t = 0.0 if L2 == 0 else max(0.0, min(1.0, ((x - ax) * dx + (y - ay) * dy) / L2))
    return math.hypot(x - ax - dx * t, y - ay - dy * t), t


def dist_borde(x, y, pts):
    return min(dist_segmento(x, y, *pts[i - 1], *pts[i])[0] for i in range(len(pts)))


def area(pts):
    return abs(sum(pts[i - 1][0] * pts[i][1] - pts[i][0] * pts[i - 1][1]
                   for i in range(len(pts)))) / 2


def punto_interior(pts, paso=4.0):
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    cx, cy = sum(xs) / len(xs), sum(ys) / len(ys)
    mejor, mejor_d = (cx, cy), dist_borde(cx, cy, pts) if dentro(cx, cy, pts) else -1.0
    paso = max(paso, (max(xs) - min(xs) + max(ys) - min(ys)) / 60)
    x = min(xs) + paso / 2
    while x < max(xs):
        y = min(ys) + paso / 2
        while y < max(ys):
            if dentro(x, y, pts):
                d = dist_borde(x, y, pts)
                if d > mejor_d:
                    mejor, mejor_d = (x, y), d
            y += paso
        x += paso
    return mejor, max(0.0, mejor_d)


class Poligono:
    def _init_poligono(self, pts):
        self.pts = pts
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        self.x0, self.y0, self.x1, self.y1 = min(xs), min(ys), max(xs), max(ys)

    def contiene(self, x, y, m=0.0):
        if not (self.x0 - m <= x <= self.x1 + m and self.y0 - m <= y <= self.y1 + m):
            return False
        if dentro(x, y, self.pts):
            return True
        return m > 0 and dist_borde(x, y, self.pts) <= m

    def cruza(self, x0, y0, x1, y1):
        return not (self.x1 < x0 or self.x0 > x1 or self.y1 < y0 or self.y0 > y1)


class Edificio(Poligono):
    def __init__(self, pts, h, tipo, nombre="", estimada=True, osm=0):
        self._init_poligono(pts)
        self.h, self.tipo, self.nombre = h, tipo, nombre
        self.estimada = estimada
        self.osm = osm
        self._centro = None

    @property
    def centro(self):
        if self._centro is None:
            self._centro = punto_interior(self.pts, 2.0)[0]
        return self._centro


class ZonaSegura(Poligono):

    def __init__(self, nombre, tipo, pts, punto):
        self._init_poligono(pts)
        self.nombre, self.tipo = nombre, tipo
        self.x, self.y = punto


class ZonaProhibida:
    def __init__(self, nombre, motivo, centro=None, radio=0.0, pts=None):
        self.nombre, self.motivo = nombre, motivo
        if pts is None:
            self.forma = "circulo"
            self.cx, self.cy = centro
            self.radio = radio
        else:
            self.forma = "poligono"
            self.pts = pts
            self.cx = sum(p[0] for p in pts) / len(pts)
            self.cy = sum(p[1] for p in pts) / len(pts)

    def distancia(self, x, y):
        if self.forma == "circulo":
            return math.hypot(x - self.cx, y - self.cy) - self.radio
        d = dist_borde(x, y, self.pts)
        return -d if dentro(x, y, self.pts) else d

    def caja(self, m=0.0):
        if self.forma == "circulo":
            return (self.cx - self.radio - m, self.cy - self.radio - m,
                    self.cx + self.radio + m, self.cy + self.radio + m)
        xs, ys = [p[0] for p in self.pts], [p[1] for p in self.pts]
        return min(xs) - m, min(ys) - m, max(xs) + m, max(ys) + m

    def anillo(self):
        if self.forma == "circulo":
            return [(self.cx + self.radio * math.cos(a * math.pi / 18),
                     self.cy + self.radio * math.sin(a * math.pi / 18)) for a in range(36)]
        return list(self.pts)


class Antena:
    __slots__ = ("x", "y", "h")

    def __init__(self, x, y, h):
        self.x, self.y, self.h = x, y, h


class Linea:

    def __init__(self, nombre, a, b, altura, flecha):
        self.nombre = nombre
        (self.x0, self.y0), (self.x1, self.y1) = a, b
        self.altura, self.flecha = altura, flecha
        self.largo = max(1.0, math.hypot(self.x1 - self.x0, self.y1 - self.y0))
        self.torres = [a, b]

    def cercania(self, x, y):
        d, t = dist_segmento(x, y, self.x0, self.y0, self.x1, self.y1)
        return d, t * self.largo

    def altura_cable(self, a):
        u = max(0.0, min(1.0, a / self.largo))
        return self.altura - self.flecha * 4 * u * (1 - u)


class Lugar:

    def __init__(self, nombre, tipo, rol, x, y, h, detalle=""):
        self.nombre, self.tipo, self.rol = nombre, tipo, rol
        self.x, self.y, self.h = x, y, float(h)
        self.detalle = detalle
        self.carga, self.masa = C.CARGAS.get(tipo, ("", 0.0))

    def objetivo(self, es_destino):
        return dict(nombre=self.nombre, tipo="plataforma", x=self.x, y=self.y, z=self.h,
                    es_destino=es_destino)


def _numero(texto):
    try:
        return float(str(texto).replace(",", ".").split(";")[0].strip().split(" ")[0])
    except ValueError:
        return None


TIPO_ZONA = {"park": "Parque", "garden": "Jardín", "pitch": "Cancha",
             "playground": "Juegos infantiles", "sports_centre": "Deportivo",
             "grass": "Área verde", "recreation_ground": "Área recreativa",
             "village_green": "Plaza"}


class Ciudad:
    def __init__(self, zona=None, avisar=print):
        self.zona = zona or Zona()
        z = self.zona
        self.ancho, self.alto = z.ancho, z.alto
        self.edificios, self.zonas_seguras, self.prohibidas = [], [], []
        self.antenas, self.lineas, self.calles = [], [], []
        self.origenes, self.destinos = [], []
        datos = datos_osm(z, avisar=avisar)
        self._cargar(datos)
        self._indexar()
        self._lugares(datos)

    def _m(self, lat, lon):
        return self.zona.a_metros(lat, lon)

    def _altura(self, tags, osm):
        h = _numero(tags.get("height", "")) if "height" in tags else None
        if h is not None and h > 1:
            return round(h, 1), False
        pisos = _numero(tags.get("building:levels", "")) if "building:levels" in tags else None
        if pisos:
            return round(pisos * C.ALTURA_PISO + 1.0, 1), False
        lo, hi = C.ALTURAS_TIPO.get(tags.get("building"), C.ALTURAS_TIPO["yes"])
        rnd = random.Random(osm * 7919 + C.SEMILLA_CIUDAD)
        return round(rnd.uniform(lo, hi), 1), True

    def _cargar(self, datos):
        helipuertos, hospitales = [], []
        for e in datos:
            t = e["tags"]
            geo = None
            if e["t"] == "w":
                geo = [self._m(*p) for p in e["g"]]
            elif e["t"] == "r":
                anillos = [[self._m(*p) for p in m] for m in e.get("m", [])]
                geo = max(anillos, key=len) if anillos else None
            punto = self._m(*e["p"]) if e["t"] == "n" else (
                tuple(sum(c) / len(geo) for c in zip(*geo)) if geo else None)
            if punto is None:
                continue
            if t.get("amenity") == "hospital" or t.get("building") == "hospital" and t.get("name"):
                hospitales.append((punto, t.get("name", "")))
            if "building" in t and geo and len(geo) >= 4:
                h, estimada = self._altura(t, e["id"])
                self.edificios.append(Edificio(geo[:-1] if geo[0] == geo[-1] else geo, h,
                                               t["building"], t.get("name", ""), estimada,
                                               e["id"]))
            elif t.get("aeroway") == "helipad":
                helipuertos.append(punto)
            elif t.get("amenity") == "prison" and geo and len(geo) >= 4:
                self.prohibidas.append(ZonaProhibida(t.get("name", "Centro penitenciario"),
                                                     "penal", pts=geo))
            elif t.get("landuse") == "military" and geo and len(geo) >= 4:
                self.prohibidas.append(ZonaProhibida(t.get("name", "Zona militar"),
                                                     "militar", pts=geo))
            elif t.get("leisure") == "stadium" and geo and len(geo) >= 4:
                self.prohibidas.append(ZonaProhibida(t.get("name", "Estadio") + " (eventos)",
                                                     "estadio", pts=geo))
            elif (t.get("leisure") in TIPO_ZONA or t.get("landuse") in TIPO_ZONA) and geo \
                    and len(geo) >= 4:
                tipo = t.get("leisure") or t.get("landuse")
                if area(geo) >= C.AREA_ZONA_ABIERTA:
                    p, holgura = punto_interior(geo)
                    if holgura >= 8:
                        nombre = t.get("name") or TIPO_ZONA[tipo]
                        self.zonas_seguras.append(ZonaSegura(nombre, tipo, geo, p))
            elif t.get("power") in C.ALTURA_CABLE and geo:
                altura = C.ALTURA_CABLE[t["power"]]
                volt = t.get("voltage", "").split(";")[0]
                kv = f" {int(volt) // 1000} kV" if volt.isdigit() else ""
                nombre = ("Línea de alta tensión" if t["power"] == "line"
                          else "Línea de media tensión") + kv
                flecha = 4.0 if t["power"] == "line" else 1.5
                for a, b in zip(geo, geo[1:]):
                    self.lineas.append(Linea(nombre, a, b, altura, flecha))
            elif t.get("man_made") in ("mast", "tower", "communications_tower"):
                h = _numero(t.get("height", "")) or C.ALTURA_ANTENA
                self.antenas.append(Antena(*punto, h))
            elif "highway" in t and geo:
                for a, b in zip(geo, geo[1:]):
                    self.calles.append((a[0], a[1], b[0], b[1], t.get("name", "")))
        juntos = []
        for p in helipuertos:
            for g in juntos:
                if math.dist(p, g[0]) < 150:
                    g.append(p)
                    break
            else:
                juntos.append([p])
        for g in juntos:
            cx, cy = sum(p[0] for p in g) / len(g), sum(p[1] for p in g) / len(g)
            cerca = [h for h in hospitales if h[1] and math.dist(h[0], (cx, cy)) < 300]
            nombre = (min(cerca, key=lambda h: math.dist(h[0], (cx, cy)))[1] + " (helipuerto)"
                      if cerca else "Helipuerto")
            self.prohibidas.append(ZonaProhibida(nombre, "helipuerto",
                                                 centro=(cx, cy), radio=C.RADIO_HELIPUERTO))
        self.zonas_seguras = [z for z in self.zonas_seguras
                              if 30 < z.x < self.ancho - 30 and 30 < z.y < self.alto - 30
                              and all(p.distancia(z.x, z.y) > C.MARGEN_ZONA
                                     for p in self.prohibidas)]

    def _indexar(self):
        self._indice = {}
        for e in self.edificios:
            for i in range(int(e.x0 // HASH), int(e.x1 // HASH) + 1):
                for j in range(int(e.y0 // HASH), int(e.y1 // HASH) + 1):
                    self._indice.setdefault((i, j), []).append(e)
        self._indice_calles = {}
        for c in self.calles:
            for i in range(int(min(c[0], c[2]) // HASH), int(max(c[0], c[2]) // HASH) + 1):
                for j in range(int(min(c[1], c[3]) // HASH), int(max(c[1], c[3]) // HASH) + 1):
                    self._indice_calles.setdefault((i, j), []).append(c)

    def calle_cercana(self, x, y, r=120.0):
        mejor, mejor_d = "", r
        for i in range(int((x - r) // HASH), int((x + r) // HASH) + 1):
            for j in range(int((y - r) // HASH), int((y + r) // HASH) + 1):
                for c in self._indice_calles.get((i, j), ()):
                    if c[4]:
                        d = dist_segmento(x, y, *c[:4])[0]
                        if d < mejor_d:
                            mejor, mejor_d = c[4], d
        return mejor

    def _sobre_edificio(self, x, y):
        e = self.edificio_en(x, y)
        if e:
            return e
        cerca = [(dist_borde(x, y, e.pts), e) for e in self.edificios_cerca(x, y, 25)]
        cerca = [c for c in cerca if c[0] < 25]
        return min(cerca, key=lambda c: c[0])[1] if cerca else None

    def lugar_de_edificio(self, e, rol="destino"):
        calle = self.calle_cercana(*e.centro)
        pisos = max(1, round((e.h - 1) / C.ALTURA_PISO))
        if e.nombre:
            nombre = e.nombre
        elif e.h < 10:
            nombre = f"Casa en {calle}" if calle else "Casa"
        else:
            nombre = f"Edificio de {pisos} pisos en {calle}" if calle else f"Edificio de {pisos} pisos"
        tipo = "casa" if e.h < 10 else "edificio"
        return Lugar(nombre, tipo, rol, *e.centro, e.h,
                     detalle="altura estimada" if e.estimada else "altura del mapa")

    def lugar_en(self, x, y, rol):
        if self.zona_prohibida(x, y, C.MARGEN_ZONA):
            return None
        e = self.edificio_en(x, y)
        if e is not None:
            if self.zona_prohibida(*e.centro, C.MARGEN_ZONA):
                return None
            lugar = self.lugar_de_edificio(e, rol)
        else:
            calle = self.calle_cercana(x, y, 60)
            lat, lon = self.zona.a_latlon(x, y)
            lugar = Lugar(f"Punto en {calle}" if calle else f"Punto {lat:.5f}, {lon:.5f}",
                          "punto", rol, x, y, 0.0, detalle="en el suelo")
        if rol == "origen":
            lugar.carga, lugar.masa = C.CARGA_GENERICA
        return lugar

    def _lugares(self, datos):
        candidatos = []
        for e in datos:
            t = e["tags"]
            am = t.get("amenity")
            if am not in ("pharmacy", "restaurant", "fast_food") or not t.get("name"):
                continue
            if e["t"] == "n":
                x, y = self._m(*e["p"])
            elif e["t"] == "w":
                pts = [self._m(*p) for p in e["g"]]
                x, y = sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts)
            else:
                continue
            if not (60 < x < self.ancho - 60 and 60 < y < self.alto - 60):
                continue
            if self.zona_prohibida(x, y, C.MARGEN_ZONA):
                continue
            ed = self._sobre_edificio(x, y)
            tipo = "farmacia" if am == "pharmacy" else "restaurante"
            if ed is None:
                lado = 7.0
                ed = Edificio([(x - lado, y - lado), (x + lado, y - lado), (x + lado, y + lado),
                               (x - lado, y + lado)], 6.0, "commercial", "", True, e["id"])
                self.edificios.append(ed)
                self._agregar_indice(ed)
            nombre = t["name"]
            if tipo == "farmacia" and "farmacia" not in nombre.lower():
                nombre = "Farmacia " + nombre
            candidatos.append(Lugar(nombre, tipo, "origen", *ed.centro, ed.h,
                                    detalle=self.calle_cercana(x, y)))
        vistos, origenes = set(), []
        for l in sorted(candidatos, key=lambda l: (l.tipo != "farmacia", l.x)):
            if l.nombre in vistos or any(math.hypot(l.x - o.x, l.y - o.y) < 40 for o in origenes):
                continue
            vistos.add(l.nombre)
            origenes.append(l)
        farm = [l for l in origenes if l.tipo == "farmacia"][:C.NUM_ORIGENES // 2]
        rest = [l for l in origenes if l.tipo == "restaurante"][:C.NUM_ORIGENES - len(farm)]
        self.origenes = sorted(farm, key=lambda l: l.x) + sorted(rest, key=lambda l: l.x)
        if not self.origenes:
            raise RuntimeError("No hay farmacias ni restaurantes en la zona elegida.")
        self.destinos = self.destinos_sugeridos(self.origenes[0])

    def destinos_sugeridos(self, origen):
        lo, hi = C.DISTANCIA_ENTREGA
        hi *= self.zona.tamano
        rnd = random.Random(C.SEMILLA_CIUDAD)
        res = [e for e in self.edificios
               if e.tipo in ("house", "detached", "residential", "apartments", "terrace", "yes")
               and lo <= math.hypot(e.x1 / 2 + e.x0 / 2 - origen.x, e.y1 / 2 + e.y0 / 2 - origen.y) <= hi
               and 4 <= e.h <= 90 and area(e.pts) > 60
               and (not e.nombre or e.tipo == "apartments")
               and not self.zona_prohibida(e.x0, e.y0, C.MARGEN_ZONA + 20)]
        res = [e for e in res if 100 < e.x0 and e.x1 < self.ancho - 100
               and 100 < e.y0 and e.y1 < self.alto - 100]
        rnd.shuffle(res)
        altos = [e for e in res if e.h >= 12]
        bajos = [e for e in res if e.h < 12 and e.tipo != "yes"] +             [e for e in res if e.h < 12 and e.tipo == "yes"]
        lugares, nombres = [], set()
        for grupo, cupo in ((altos, C.NUM_DESTINOS // 2), (bajos, C.NUM_DESTINOS)):
            for e in grupo:
                if len(lugares) >= cupo:
                    break
                l = self.lugar_de_edificio(e)
                if l.nombre in nombres or any(math.hypot(l.x - o.x, l.y - o.y) < 300
                                              for o in lugares):
                    continue
                nombres.add(l.nombre)
                lugares.append(l)
        return sorted(lugares, key=lambda l: -l.h)

    def _agregar_indice(self, e):
        for i in range(int(e.x0 // HASH), int(e.x1 // HASH) + 1):
            for j in range(int(e.y0 // HASH), int(e.y1 // HASH) + 1):
                self._indice.setdefault((i, j), []).append(e)

    def edificio_en(self, x, y):
        for e in self._indice.get((int(x // HASH), int(y // HASH)), ()):
            if e.contiene(x, y):
                return e
        return None

    def altura_superficie(self, x, y):
        e = self.edificio_en(x, y)
        return e.h if e else 0.0

    def edificios_cerca(self, x, y, r):
        vistos, res = set(), []
        for i in range(int((x - r) // HASH), int((x + r) // HASH) + 1):
            for j in range(int((y - r) // HASH), int((y + r) // HASH) + 1):
                for e in self._indice.get((i, j), ()):
                    if id(e) not in vistos and e.cruza(x - r, y - r, x + r, y + r):
                        vistos.add(id(e))
                        res.append(e)
        return res

    def zona_prohibida(self, x, y, m=0.0):
        for z in self.prohibidas:
            if z.distancia(x, y) < m:
                return z
        return None

    def zona_segura_en(self, x, y):
        return next((z for z in self.zonas_seguras if z.contiene(x, y)), None)

    def punto_abierto(self, x, y, radio):
        mejor, mejor_d = None, float("inf")
        for i in range(int((x - radio) // HASH), int((x + radio) // HASH) + 1):
            for j in range(int((y - radio) // HASH), int((y + radio) // HASH) + 1):
                for c in self._indice_calles.get((i, j), ()):
                    L = math.hypot(c[2] - c[0], c[3] - c[1])
                    for k in range(int(L // 5) + 1):
                        f = 5 * k / L if L else 0
                        px, py = c[0] + (c[2] - c[0]) * f, c[1] + (c[3] - c[1]) * f
                        d = math.hypot(px - x, py - y)
                        if d >= mejor_d or d > radio:
                            continue
                        if any(e.contiene(px, py, 6.0) for e in self.edificios_cerca(px, py, 8)):
                            continue
                        if self.zona_prohibida(px, py, 10.0):
                            continue
                        if any(math.hypot(px - a.x, py - a.y) < 15 for a in self.antenas):
                            continue
                        if any(l.cercania(px, py)[0] < 15 for l in self.lineas
                               if abs(l.x0 - px) < l.largo + 20 and abs(l.y0 - py) < l.largo + 20):
                            continue
                        mejor, mejor_d = (px, py), d
        return mejor
