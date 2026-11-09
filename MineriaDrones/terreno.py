import json
import math
import os

import numpy as np
from matplotlib.path import Path
from scipy.ndimage import (binary_dilation, distance_transform_edt, gaussian_filter, label, map_coordinates,
                           maximum_filter, zoom)
from scipy.spatial import cKDTree

import config as C
import geo as G


def fbm(ny, nx, rng, octavas=6, base=4, persistencia=0.5):
    total = np.zeros((ny, nx), dtype=np.float32)
    amp, suma = 1.0, 0.0
    for k in range(octavas):
        n = base * 2 ** k
        rejilla = rng.standard_normal((n + 3, n + 3)).astype(np.float32)
        capa = zoom(rejilla, ((ny + 2 * ny / n) / (n + 3), (nx + 2 * nx / n) / (n + 3)), order=3)
        oy, ox = (capa.shape[0] - ny) // 2, (capa.shape[1] - nx) // 2
        total += amp * capa[oy:oy + ny, ox:ox + nx]
        suma += amp
        amp *= persistencia
    return total / suma


def terrazas(d, piso, h=C.BANCO_ALTURA, berma=C.BANCO_BERMA, angulo=C.CARA_ANGULO):
    cara = h / math.tan(math.radians(angulo))
    paso = berma + cara
    k = np.floor(d / paso)
    s = d - k * paso
    return piso + h * k + h * np.clip(s / cara, 0.0, 1.0)


def pendiente_media(h=C.BANCO_ALTURA, berma=C.BANCO_BERMA, angulo=C.CARA_ANGULO):
    return h / (berma + h / math.tan(math.radians(angulo)))


def poligono_elipse(cx, cy, a, b, rot=0.0, n=28, rng=None, rugosidad=0.0):
    t = np.linspace(0, 2 * np.pi, n, endpoint=False)
    r = 1.0 + (rng.uniform(-rugosidad, rugosidad, n) if rng is not None and rugosidad else 0.0)
    x, y = a * np.cos(t) * r, b * np.sin(t) * r
    c, s = math.cos(rot), math.sin(rot)
    return np.column_stack([cx + x * c - y * s, cy + x * s + y * c]).round(2).tolist()


def area_poligono(pts):
    p = np.asarray(pts, dtype=float)
    return 0.5 * abs(np.dot(p[:, 0], np.roll(p[:, 1], 1)) - np.dot(p[:, 1], np.roll(p[:, 0], 1)))


def recortar(pts, x0, y0, x1, y1):
    p = [tuple(map(float, q)) for q in pts]
    for borde in ((0, x0, 1), (0, x1, -1), (1, y0, 1), (1, y1, -1)):
        eje, lim, sgn = borde
        if not p:
            break
        res = []
        for k in range(len(p)):
            a, b = p[k - 1], p[k]
            da, db = (a[eje] - lim) * sgn, (b[eje] - lim) * sgn
            if db >= 0:
                if da < 0:
                    t = da / (da - db)
                    res.append((a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t))
                res.append(b)
            elif da >= 0:
                t = da / (da - db)
                res.append((a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t))
        p = res
    return [[round(x, 2), round(y, 2)] for x, y in p]


def centroide(pts):
    p = np.asarray(pts, dtype=float)
    return float(p[:, 0].mean()), float(p[:, 1].mean())


class Sitio:
    def __init__(self, nombre, georef, real=False):
        self.nombre = nombre
        self.georef = georef
        self.real = real
        self.ancho = georef.ancho
        self.res = georef.ancho / C.CELDAS
        self.nx = self.ny = C.CELDAS
        self.epocas = {}
        self.zonas = []
        self.caminos = []
        self.osm = {}
        self.base = (self.ancho * 0.5, self.ancho * 0.08)
        self._malla = None
        self.notas = []

    def malla(self):
        if self._malla is None:
            xs = (np.arange(self.nx) + 0.5) * self.res
            ys = self.ancho - (np.arange(self.ny) + 0.5) * self.res
            self._malla = np.meshgrid(xs.astype(np.float32), ys.astype(np.float32))
        return self._malla

    def a_ij(self, x, y):
        return np.asarray(self.ny - np.asarray(y) / self.res - 0.5), np.asarray(np.asarray(x) / self.res - 0.5)

    def a_xy(self, i, j):
        return (np.asarray(j) + 0.5) * self.res, self.ancho - (np.asarray(i) + 0.5) * self.res

    def muestrear(self, arr, x, y, orden=1):
        i, j = self.a_ij(x, y)
        return map_coordinates(arr, [np.atleast_1d(i), np.atleast_1d(j)], order=orden, mode="nearest")

    def mascara(self, puntos, margen=0.0):
        p = np.asarray(puntos, dtype=float)
        x0, y0 = p.min(axis=0) - margen - self.res
        x1, y1 = p.max(axis=0) + margen + self.res
        j0, j1 = max(0, int(x0 / self.res)), min(self.nx, int(x1 / self.res) + 2)
        i0, i1 = max(0, int((self.ancho - y1) / self.res)), min(self.ny, int((self.ancho - y0) / self.res) + 2)
        m = np.zeros((self.ny, self.nx), dtype=bool)
        if j1 <= j0 or i1 <= i0:
            return m
        X, Y = self.malla()
        sub = np.column_stack([X[i0:i1, j0:j1].ravel(), Y[i0:i1, j0:j1].ravel()])
        dentro = Path(p).contains_points(sub).reshape(i1 - i0, j1 - j0)
        m[i0:i1, j0:j1] = dentro
        if margen > 0:
            m = binary_dilation(m, iterations=max(1, int(margen / self.res)))
        return m

    def poligono_de_mascara(self, m, vertices=40):
        import contourpy
        if not m.any():
            return None
        suave = gaussian_filter(m.astype(np.float32), 2.0)
        X, Y = self.malla()
        gen = contourpy.contour_generator(X, Y, suave)
        lineas = gen.lines(0.5)
        if not lineas:
            return None
        l = max(lineas, key=len)
        paso = max(1, len(l) // vertices)
        return l[::paso].round(2).tolist()

    def zonas_de(self, tipo):
        return [z for z in self.zonas if z["tipo"] == tipo]

    def superficie(self, epoca):
        e = self.epocas[epoca]
        return e["dtm"] + e["veg"] + e["objetos_h"]

    def guardar(self, carpeta):
        os.makedirs(carpeta, exist_ok=True)
        arrays = {}
        meta = {"nombre": self.nombre, "georef": self.georef.a_dict(), "real": self.real, "zonas": self.zonas,
                "caminos": self.caminos, "base": self.base, "notas": self.notas, "epocas": {}, "osm": self.osm}
        for k, e in self.epocas.items():
            for campo in ("dtm", "veg", "objetos_h", "color", "agua"):
                arrays[f"{k}_{campo}"] = e[campo]
            meta["epocas"][k] = {"objetos": e["objetos"], "hallazgos": e["hallazgos"], "fecha": e["fecha"]}
        np.savez_compressed(os.path.join(carpeta, "sitio.npz"), **arrays)
        with open(os.path.join(carpeta, "sitio.json"), "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False)

    @staticmethod
    def cargar(carpeta):
        with open(os.path.join(carpeta, "sitio.json"), encoding="utf-8") as f:
            meta = json.load(f)
        s = Sitio(meta["nombre"], G.Georef.de_dict(meta["georef"]), meta["real"])
        s.zonas, s.caminos, s.base, s.notas, s.osm = meta["zonas"], meta["caminos"], tuple(meta["base"]), meta.get("notas", []), meta.get("osm", {})
        d = np.load(os.path.join(carpeta, "sitio.npz"))
        for k, e in meta["epocas"].items():
            s.epocas[k] = {campo: d[f"{k}_{campo}"] for campo in ("dtm", "veg", "objetos_h", "color", "agua")}
            s.epocas[k].update(e)
        return s


def _sombreado(dtm, res, az=315.0, alt=45.0):
    gy, gx = np.gradient(dtm, res)
    pend = np.arctan(np.hypot(gx, gy))
    asp = np.arctan2(-gx, gy)
    a, z = math.radians(az), math.radians(90 - alt)
    return np.clip(np.cos(z) * np.cos(pend) + np.sin(z) * np.sin(pend) * np.cos(a - asp), 0, 1).astype(np.float32)


def _objetos_raster(sitio, objetos):
    h = np.zeros((sitio.ny, sitio.nx), dtype=np.float32)
    X, Y = sitio.malla()
    for o in objetos:
        if o.get("h", 0) <= 0.3:
            continue
        r = math.hypot(o["l"], o["w"]) / 2 + sitio.res
        i, j = sitio.a_ij(o["x"], o["y"])
        i0, i1 = int(max(0, i - r / sitio.res - 1)), int(min(sitio.ny, i + r / sitio.res + 2))
        j0, j1 = int(max(0, j - r / sitio.res - 1)), int(min(sitio.nx, j + r / sitio.res + 2))
        if i1 <= i0 or j1 <= j0:
            continue
        dx, dy = X[i0:i1, j0:j1] - o["x"], Y[i0:i1, j0:j1] - o["y"]
        c, s = math.cos(o.get("rumbo", 0.0)), math.sin(o.get("rumbo", 0.0))
        u, v = dx * c + dy * s, -dx * s + dy * c
        dentro = (np.abs(u) <= o["l"] / 2) & (np.abs(v) <= o["w"] / 2)
        h[i0:i1, j0:j1] = np.where(dentro, np.maximum(h[i0:i1, j0:j1], o["h"]), h[i0:i1, j0:j1])
    return h


def _pintar_objetos(sitio, color, objetos):
    X, Y = sitio.malla()
    tonos = {"edificio": (205, 208, 212), "trituradora": (120, 124, 130), "subestacion": (150, 150, 140),
             "banda": (70, 72, 78), "camion": (235, 190, 40), "pala": (225, 160, 30), "perforadora": (230, 120, 40),
             "camioneta": (240, 240, 240), "tanque": (180, 185, 190), "persona": (255, 120, 20)}
    for o in objetos:
        col = tonos.get(o["tipo"])
        if col is None:
            continue
        r = math.hypot(o["l"], o["w"]) / 2 + sitio.res
        i, j = sitio.a_ij(o["x"], o["y"])
        i0, i1 = int(max(0, i - r / sitio.res - 1)), int(min(sitio.ny, i + r / sitio.res + 2))
        j0, j1 = int(max(0, j - r / sitio.res - 1)), int(min(sitio.nx, j + r / sitio.res + 2))
        if i1 <= i0 or j1 <= j0:
            continue
        dx, dy = X[i0:i1, j0:j1] - o["x"], Y[i0:i1, j0:j1] - o["y"]
        c, s = math.cos(o.get("rumbo", 0.0)), math.sin(o.get("rumbo", 0.0))
        u, v = dx * c + dy * s, -dx * s + dy * c
        dentro = (np.abs(u) <= max(o["l"], sitio.res) / 2) & (np.abs(v) <= max(o["w"], sitio.res) / 2)
        color[i0:i1, j0:j1][dentro] = col


def _vegetacion(sitio, rng, densidad, excluir):
    ny, nx = sitio.ny, sitio.nx
    veg = np.zeros((ny, nx), dtype=np.float32)
    area = sitio.ancho ** 2
    n = int(area / 900 * densidad)
    xs = rng.uniform(0, sitio.ancho, n)
    ys = rng.uniform(0, sitio.ancho, n)
    i, j = sitio.a_ij(xs, ys)
    ii, jj = np.clip(i.astype(int), 0, ny - 1), np.clip(j.astype(int), 0, nx - 1)
    ok = ~excluir[ii, jj]
    xs, ys = xs[ok], ys[ok]
    alturas = rng.gamma(2.2, 1.3, len(xs)).clip(0.6, 9.0)
    radios = (alturas * rng.uniform(0.35, 0.6, len(xs))).clip(0.8, 4.5)
    X, Y = sitio.malla()
    for x, y, h, r in zip(xs, ys, alturas, radios):
        ci, cj = sitio.a_ij(x, y)
        k = int(r / sitio.res) + 1
        i0, i1 = max(0, int(ci) - k), min(ny, int(ci) + k + 2)
        j0, j1 = max(0, int(cj) - k), min(nx, int(cj) + k + 2)
        d2 = ((X[i0:i1, j0:j1] - x) ** 2 + (Y[i0:i1, j0:j1] - y) ** 2) / (r * r)
        copa = np.where(d2 < 1, h * (1 - 0.55 * d2), 0)
        veg[i0:i1, j0:j1] = np.maximum(veg[i0:i1, j0:j1], copa)
    return veg


def _textura_demo(sitio, dtm, base, rng, capas):
    ny, nx = sitio.ny, sitio.nx
    ruido = fbm(ny, nx, rng, 6, 8)[..., None]
    fino = rng.normal(0, 1, (ny, nx)).astype(np.float32)[..., None]
    suelo = np.array([176, 152, 114], np.float32) + ruido * 22 + fino * 5
    rojizo = fbm(ny, nx, rng, 4, 3)[..., None]
    suelo = suelo + np.clip(rojizo, 0, 1) * np.array([14, -6, -16], np.float32)
    col = suelo
    excav = (base - dtm) > 1.5
    banda = np.sin((dtm / 23.0) + fbm(ny, nx, rng, 3, 4) * 2.0)[..., None]
    roca = np.array([138, 128, 118], np.float32) + banda * np.array([22, 10, 2], np.float32) + fino * 7
    gy, gx = np.gradient(dtm, sitio.res)
    pend = np.degrees(np.arctan(np.hypot(gx, gy)))[..., None]
    berma = np.array([194, 180, 156], np.float32) + fino * 5
    pared = np.where(pend > 35, roca, berma)
    col = np.where(excav[..., None], pared, col)
    for mascara, tono, var in capas:
        col = np.where(mascara[..., None], np.array(tono, np.float32) + fino * var + ruido * var, col)
    sombra = _sombreado(dtm, sitio.res)[..., None]
    col = col * (0.55 + 0.6 * sombra)
    return np.clip(col, 0, 255).astype(np.uint8)


def _tintar_vegetacion(color, veg, rng):
    m = veg > 0.4
    if not m.any():
        return color
    c = color.astype(np.float32)
    t = np.clip(veg / 6, 0.25, 1.0)[..., None]
    verde = np.array([74, 92, 52], np.float32) * (1.05 - 0.35 * t)
    c = np.where(m[..., None], c * (1 - 0.75 * t) + verde * 0.75 * t, c)
    return np.clip(c, 0, 255).astype(np.uint8)


def _rampa(sitio, centro, a, b, rot, piso, borde_z, sentido=1.0, theta0=0.0):
    pend = pendiente_media()
    paso_th = 0.004
    th, z = theta0, piso
    pts = []
    while z < borde_z + 2 and len(pts) < 20000:
        d = (z - piso) / pend
        ex, ey = a * math.cos(th), b * math.sin(th)
        r0 = math.hypot(ex, ey)
        rr = r0 + d
        c, s = math.cos(rot), math.sin(rot)
        ux, uy = ex / r0, ey / r0
        x = centro[0] + (ux * rr) * c - (uy * rr) * s
        y = centro[1] + (ux * rr) * s + (uy * rr) * c
        pts.append((x, y, z))
        ds = rr * paso_th
        th += sentido * paso_th
        z += 0.10 * ds
    return np.array(pts)


def _aplanar_camino(sitio, dtm, puntos, ancho, z=None):
    p = np.asarray(puntos, dtype=float)
    seg = []
    for (x0, y0), (x1, y1) in zip(p[:-1, :2], p[1:, :2]):
        n = max(2, int(math.hypot(x1 - x0, y1 - y0) / (sitio.res * 0.7)))
        t = np.linspace(0, 1, n, endpoint=False)
        seg.append(np.column_stack([x0 + (x1 - x0) * t, y0 + (y1 - y0) * t]))
    seg.append(p[-1:, :2])
    q = np.vstack(seg)
    if z is None:
        zq = sitio.muestrear(dtm, q[:, 0], q[:, 1])
        zq = gaussian_filter(zq, max(2.0, 25 / sitio.res))
    else:
        zq = np.interp(np.linspace(0, 1, len(q)), np.linspace(0, 1, len(z)), z)
    arbol = cKDTree(q)
    X, Y = sitio.malla()
    x0, y0 = q.min(axis=0) - ancho
    x1, y1 = q.max(axis=0) + ancho
    j0, j1 = max(0, int(x0 / sitio.res)), min(sitio.nx, int(x1 / sitio.res) + 2)
    i0, i1 = max(0, int((sitio.ancho - y1) / sitio.res)), min(sitio.ny, int((sitio.ancho - y0) / sitio.res) + 2)
    sub = np.column_stack([X[i0:i1, j0:j1].ravel(), Y[i0:i1, j0:j1].ravel()])
    d, k = arbol.query(sub, distance_upper_bound=ancho)
    m = np.isfinite(d)
    bloque = dtm[i0:i1, j0:j1].ravel()
    bloque[m] = zq[k[m]]
    dtm[i0:i1, j0:j1] = bloque.reshape(i1 - i0, j1 - j0)
    mascara = np.zeros_like(dtm, dtype=bool)
    mm = np.zeros(len(sub), bool)
    mm[m] = True
    mascara[i0:i1, j0:j1] = mm.reshape(i1 - i0, j1 - j0)
    return mascara


def _cono(sitio, dtm, x, y, alto, angulo=37.0):
    X, Y = sitio.malla()
    d = np.hypot(X - x, Y - y)
    zb = float(sitio.muestrear(dtm, x, y)[0])
    z = zb + alto - d * math.tan(math.radians(angulo))
    m = z > dtm
    dtm[m] = z[m]
    return m


def _obj(tipo, nombre, x, y, l, w, h, rumbo=0.0, temp=None, **extra):
    o = {"tipo": tipo, "nombre": nombre, "x": float(x), "y": float(y), "l": float(l), "w": float(w), "h": float(h),
         "rumbo": float(rumbo)}
    if temp is not None:
        o["temp"] = float(temp)
    o.update(extra)
    return o


def crear_demo(tamano=1600.0, semilla=7, avisar=print, opciones=None):
    rng = np.random.default_rng(semilla)
    georef = G.Georef(*C.DEMO_LATLON, tamano, tamano, "Mina demostración")
    s = Sitio("Mina demostración (sintética)", georef, real=False)
    s.notas.append("Ubicación ficticia: el terreno es sintético, no corresponde a Google Maps")
    L, ny, nx = tamano, s.ny, s.nx
    X, Y = s.malla()
    avisar("Generando terreno base…")
    base = (2240 + 32 * fbm(ny, nx, rng, 6, 2) + 0.012 * (X - L / 2) - 0.008 * (Y - L / 2)
            + 1.2 * fbm(ny, nx, rng, 3, 64)).astype(np.float32)
    dtm = base.copy()
    avisar("Excavando el tajo (bancos de 10 m, bermas de 8 m)…")
    cx, cy, rot = 0.50 * L, 0.54 * L, math.radians(18)
    a, b = 0.075 * L, 0.05 * L
    c, sn = math.cos(rot), math.sin(rot)
    u, v = (X - cx) * c + (Y - cy) * sn, -(X - cx) * sn + (Y - cy) * c
    piso_m = (u / a) ** 2 + (v / b) ** 2 <= 1
    d = distance_transform_edt(~piso_m) * s.res
    piso = float(base[piso_m].mean()) - 92
    tajo = terrazas(d, piso).astype(np.float32)
    dtm = np.minimum(dtm, tajo)
    borde = float(np.percentile(base[(d > 0) & (d < 200)], 60))
    prueba = _rampa(s, (cx, cy), a, b, rot, piso, borde, 1.0, 0.0)
    barrido = 0.004 * (len(prueba) - 1)
    ux, uy = (0.0 * c + 1.0 * sn), (-0.0 * sn + 1.0 * c)
    objetivo = math.atan2(uy / b, ux / a)
    rampa = _rampa(s, (cx, cy), a, b, rot, piso, borde, 1.0, objetivo - barrido)
    m_rampa = _aplanar_camino(s, dtm, rampa[:, :2], 9.0, rampa[:, 2]) & (dtm <= base + 0.5)
    dtm = np.minimum(dtm, base)
    salida = rampa[-1, :2]
    trit = (0.80 * L, 0.70 * L)
    tir = (0.20 * L, 0.76 * L)
    estanque = (0.78 * L, 0.20 * L)
    pad = [(trit[0] - 60, trit[1] - 45), (trit[0] + 150, trit[1] - 45), (trit[0] + 150, trit[1] + 70), (trit[0] - 60, trit[1] + 70)]
    m_pad = s.mascara(pad)
    zpad = float(np.median(dtm[m_pad]))
    dtm[m_pad] = zpad
    avisar("Trazando caminos de acarreo, tepetatera y acopios…")
    fuera = (salida[0] + (salida[0] - cx) * 0.25, salida[1] + 60)
    camino1 = [tuple(salida), fuera, (trit[0] - 70, trit[1] - 10)]
    camino2 = [tuple(salida), fuera, (tir[0] + 0.1 * L, tir[1] - 0.02 * L)]
    m_c1 = _aplanar_camino(s, dtm, camino1, 10.0)
    m_c2 = _aplanar_camino(s, dtm, camino2, 10.0)
    s.caminos = [{"nombre": "Rampa principal", "puntos": rampa[:, :2][::25].round(1).tolist()},
                 {"nombre": "Camino a trituradora", "puntos": [list(map(float, p)) for p in camino1]},
                 {"nombre": "Camino a tepetatera", "puntos": [list(map(float, p)) for p in camino2]}]
    tu, tv = (X - tir[0]), (Y - tir[1])
    top = (tu / (0.09 * L)) ** 2 + (tv / (0.065 * L)) ** 2 <= 1
    dt = distance_transform_edt(~top) * s.res
    z_top = float(base[top].mean()) + 36
    tepe = z_top - terrazas(dt, 0.0, 10.0, 12.0, 37.0)
    m_tepe = tepe > dtm
    dtm = np.where(m_tepe, tepe, dtm).astype(np.float32)
    acopio1 = (trit[0] - 120, trit[1] + 10)
    acopio2 = (trit[0] - 40, trit[1] + 120)
    m_ac1 = _cono(s, dtm, *acopio1, 16.0)
    m_ac2 = _cono(s, dtm, *acopio2, 11.0)
    eu, ev = X - estanque[0], Y - estanque[1]
    re = np.hypot(eu / 110, ev / 80)
    vaso = np.clip(1 - re, 0, 1)
    dtm = np.where(re < 1.25, dtm - 7 * np.clip((1.05 - re) * 4, 0, 1) + 3 * np.exp(-((re - 1.1) / 0.06) ** 2), dtm).astype(np.float32)
    nivel = float(np.percentile(dtm[re < 0.6], 70))
    agua = (re < 1.0) & (dtm < nivel)
    dtm = gaussian_filter(dtm, 0.6).astype(np.float32)
    disturbado = (base - dtm > 1.0) | m_tepe | m_ac1 | m_ac2 | m_pad | m_c1 | m_c2 | m_rampa | (re < 1.3)
    disturbado = binary_dilation(disturbado, iterations=int(8 / s.res) + 1)
    avisar("Sembrando vegetación…")
    veg = _vegetacion(s, rng, 1.4, disturbado)
    zona_ext = poligono_elipse(cx + 25, cy + 8, a + 270, b + 240, rot, 30, rng, 0.04)
    s.zonas = [
        {"nombre": "Tajo autorizado", "tipo": "extraccion", "puntos": zona_ext, "cota_piso": round(piso - 15, 1)},
        {"nombre": "Presa de jales", "tipo": "restringida", "puntos": poligono_elipse(*estanque, 140, 110, 0, 24)},
        {"nombre": "Área de voladura", "tipo": "exclusion", "puntos": poligono_elipse(cx - 0.04 * L, cy - 0.01 * L, 70, 45, rot, 18)},
        {"nombre": "Acopio mineral ROM", "tipo": "acopio", "puntos": poligono_elipse(*acopio1, 32, 32, 0, 20)},
        {"nombre": "Acopio mineral fino", "tipo": "acopio", "puntos": poligono_elipse(*acopio2, 24, 24, 0, 20)},
    ]
    s.base = (float(0.62 * L), float(0.80 * L))
    objetos = []
    for k, (dx, dy, l, w, h, nombre) in enumerate([(0, 0, 40, 28, 14, "Trituradora primaria"), (90, 30, 60, 30, 12, "Planta de beneficio"),
                                                   (120, -20, 25, 18, 6, "Taller de mantenimiento"),
                                                   (40, 55, 18, 12, 5, "Oficinas")]):
        objetos.append(_obj("trituradora" if k == 0 else "edificio", nombre, trit[0] + dx, trit[1] + dy, l, w, h,
                            temp=48 if k == 0 else 34))
    objetos.append(_obj("subestacion", "Subestación eléctrica", trit[0] + 135, trit[1] + 55, 14, 10, 4, temp=52, falla=False))
    objetos.append(_obj("tanque", "Tanque de diésel", trit[0] - 35, trit[1] - 32, 8, 8, 6, temp=30))
    for k in range(12):
        t = k / 11
        x = trit[0] + 20 + t * 70
        y = trit[1] + 14 + t * 18
        objetos.append(_obj("banda", f"Rodillo de banda {k + 1}", x, y, 6, 2, 2.5, math.atan2(18, 70), temp=38))
    for k, idx in enumerate((0.15, 0.45, 0.7)):
        p = rampa[int(idx * (len(rampa) - 1))]
        objetos.append(_obj("camion", f"Camión de acarreo {k + 1}", p[0], p[1], 12, 7, 6, rng.uniform(0, 6.28), temp=72))
    objetos.append(_obj("pala", "Pala hidráulica", cx + 0.6 * a, cy + 0.1 * b, 14, 8, 9, 0.4, temp=78))
    objetos.append(_obj("perforadora", "Perforadora", cx - 0.5 * a, cy - 0.3 * b, 9, 4, 12, 1.2, temp=70))
    objetos.append(_obj("camioneta", "Camioneta de supervisión", trit[0] - 50, trit[1] + 40, 5, 2, 1.9, 0.3, temp=40))
    for k in range(4):
        objetos.append(_obj("persona", f"Trabajador {k + 1}", trit[0] + rng.uniform(-30, 60), trit[1] + rng.uniform(-40, 40),
                            0.5, 0.5, 1.7, temp=34))
    capas = [(m_tepe & ~m_ac1, (196, 182, 158), 8), (m_ac1, (92, 86, 80), 6), (m_ac2, (132, 104, 78), 6),
             (m_pad, (168, 164, 156), 4), (m_c1 | m_c2 | m_rampa, (205, 194, 172), 3),
             ((re < 1.05) & ~agua, (206, 200, 184), 4), (agua, (62, 98, 92), 2)]
    s._capas_demo = (base, capas)
    color = _textura_demo(s, dtm, base, rng, capas)
    _pintar_objetos(s, color, objetos)
    color = _tintar_vegetacion(color, veg, rng)
    s.epocas["A"] = {"dtm": dtm, "veg": veg, "objetos": objetos, "objetos_h": _objetos_raster(s, objetos),
                     "color": color, "agua": agua, "hallazgos": [], "fecha": "Levantamiento anterior"}
    avance(s, rng, opciones or {}, avisar)
    return s


def _mascara_osm(sitio, lista, margen=0.0):
    m = np.zeros((sitio.ny, sitio.nx), dtype=bool)
    for e in lista:
        if len(e["puntos"]) >= 3:
            m |= sitio.mascara(e["puntos"], margen)
    return m


def crear_real(lat, lon, nombre, tamano=1600.0, semilla=7, avisar=print, opciones=None, usar_osm=True, previa=None):
    from concurrent.futures import ThreadPoolExecutor
    rng = np.random.default_rng(semilla)
    georef = G.Georef(lat, lon, tamano, tamano, nombre)
    s = Sitio(nombre, georef, real=True)
    osm = {"agua": [], "rios": [], "edificios": [], "caminos": [], "tajos": [], "residuos": [], "lineas": []}
    import time as _t
    ex = ThreadPoolExecutor(3)
    f_sat = ex.submit(G.imagen_satelital, georef, s.nx, s.ny, avisar)
    f_dem = ex.submit(G.elevacion, georef, s.nx, s.ny, avisar)
    f_osm = ex.submit(G.datos_osm, georef, lambda m: None) if usar_osm else None
    color = f_sat.result()
    if previa:
        previa(georef, color)
    dtm = f_dem.result()
    listo = _t.time()
    if f_osm is not None:
        try:
            osm = f_osm.result(timeout=max(0.5, 8.0 - (_t.time() - listo)))
        except Exception as error:
            if f_osm.done():
                avisar(f"Sin datos de OpenStreetMap ({error})")
            else:
                avisar("OpenStreetMap no respondió a tiempo: el sitio se arma sin esas capas (se guardan para la próxima vez)")
                s.notas.append("Capas de OpenStreetMap pendientes: vuelve a crear el sitio para agregarlas")
    ex.shutdown(wait=False)
    avisar("Armando el modelo del sitio…")
    dtm = (gaussian_filter(dtm, 1.0) + 0.35 * fbm(s.ny, s.nx, rng, 3, 128)).astype(np.float32)
    s.osm = {k: len(v) for k, v in osm.items()}
    agua = _mascara_osm(s, osm["agua"])
    rgb = color.astype(np.float32)
    exg = (2 * rgb[..., 1] - rgb[..., 0] - rgb[..., 2]) / (rgb.sum(axis=2) + 1)
    lum = rgb.mean(axis=2)
    tajos = _mascara_osm(s, osm["tajos"])
    veg_m = (exg > 0.06) & (lum < 150) & ~tajos & ~agua
    veg = np.where(veg_m, np.clip((exg - 0.04) * 45, 0.6, 9.0), 0).astype(np.float32)
    veg = gaussian_filter(veg, 0.8).astype(np.float32)
    objetos = []
    for k, e in enumerate(osm["edificios"][:400]):
        p = np.asarray(e["puntos"], dtype=float)
        if len(p) < 3:
            continue
        cxe, cye = p[:, 0].mean(), p[:, 1].mean()
        if not (0 < cxe < tamano and 0 < cye < tamano):
            continue
        l = max(4.0, float(np.ptp(p[:, 0])))
        w = max(4.0, float(np.ptp(p[:, 1])))
        niveles = e.get("niveles")
        try:
            h = 3.2 * float(niveles)
        except (TypeError, ValueError):
            h = 7.0
        objetos.append(_obj("edificio", e["nombre"] or f"Edificio {k + 1}", cxe, cye, l, w, h, temp=36))
    for e in osm["caminos"]:
        p = np.asarray(e["puntos"], dtype=float)
        if len(p) >= 2:
            s.caminos.append({"nombre": e["nombre"] or e["tipo"], "puntos": p.round(1).tolist()})
    zonas = []
    for e in osm["tajos"]:
        pts = recortar(e["puntos"], 5, 5, tamano - 5, tamano - 5) if len(e["puntos"]) >= 3 else []
        if len(pts) >= 3 and area_poligono(pts) > 20000:
            zonas.append({"nombre": e["nombre"], "tipo": "extraccion", "puntos": pts})
    if not zonas:
        prof = maximum_filter(gaussian_filter(dtm, 4), size=int(min(400, tamano / 4) / s.res)) - dtm
        m = prof > max(25.0, float(np.percentile(prof, 80)))
        lab, n = label(m)
        if n:
            mayor = np.argmax(np.bincount(lab.ravel())[1:]) + 1
            m = binary_dilation(lab == mayor, iterations=int(40 / s.res))
            pol = s.poligono_de_mascara(m, 36)
            if pol:
                zonas.append({"nombre": "Tajo detectado por elevación", "tipo": "extraccion", "puntos": pol})
                s.notas.append("No hay tajo en OpenStreetMap: la zona de extracción se dedujo de la elevación")
    if not zonas:
        zonas.append({"nombre": "Zona de extracción", "tipo": "extraccion",
                      "puntos": poligono_elipse(tamano / 2, tamano / 2, tamano * 0.22, tamano * 0.18, 0, 24)})
    zonas.sort(key=lambda z: -area_poligono(z["puntos"]))
    for z in zonas:
        m = s.mascara(z["puntos"])
        z["cota_piso"] = round(float(dtm[m].min()) - 15, 1) if m.any() else None
    for k, e in enumerate(osm["agua"][:6]):
        if len(e["puntos"]) >= 3 and area_poligono(e["puntos"]) > 600:
            m = binary_dilation(s.mascara(e["puntos"]), iterations=int(30 / s.res))
            pol = s.poligono_de_mascara(m, 30)
            if pol:
                zonas.append({"nombre": e["nombre"] or f"Cuerpo de agua {k + 1}", "tipo": "restringida", "puntos": pol})
    s.zonas = zonas
    z0 = s.mascara(zonas[0]["puntos"])
    ii, jj = np.nonzero(z0)
    piso_k = np.argmin(dtm[z0])
    px, py = s.a_xy(ii[piso_k], jj[piso_k])
    zmed = np.median(dtm[z0])
    medios = np.flatnonzero(np.abs(dtm[z0] - zmed) < 8)
    for k in range(3):
        if len(medios):
            q = medios[rng.integers(len(medios))]
            qx, qy = s.a_xy(ii[q], jj[q])
            objetos.append(_obj("camion", f"Camión de acarreo {k + 1}", qx, qy, 12, 7, 6, rng.uniform(0, 6.28), temp=72))
    objetos.append(_obj("pala", "Pala hidráulica", px + 20, py + 10, 14, 8, 9, 0.4, temp=78))
    objetos.append(_obj("perforadora", "Perforadora", px - 40, py + 30, 9, 4, 12, 1.2, temp=70))
    zc = centroide(zonas[0]["puntos"])
    exterior = np.flatnonzero(~z0.ravel() & (np.abs(np.gradient(dtm)[0]).ravel() < 0.15 * s.res))
    if len(exterior):
        cand = exterior[np.argsort(np.hypot(*(np.array(s.a_xy(*np.unravel_index(exterior, z0.shape))) - np.array(zc)[:, None])))[:2000]]
        q = cand[rng.integers(len(cand))]
        tx, ty = s.a_xy(*np.unravel_index(q, z0.shape))
        tx, ty = float(tx), float(ty)
    else:
        tx, ty = tamano * 0.85, tamano * 0.85
    objetos.append(_obj("trituradora", "Trituradora primaria", tx, ty, 40, 28, 14, temp=48))
    objetos.append(_obj("subestacion", "Subestación eléctrica", tx + 55, ty + 30, 14, 10, 4, temp=52, falla=False))
    for k in range(10):
        t = k / 9
        objetos.append(_obj("banda", f"Rodillo de banda {k + 1}", tx + 25 + t * 60, ty + 5 + t * 12, 6, 2, 2.5,
                            math.atan2(12, 60), temp=38))
    for k in range(3):
        objetos.append(_obj("persona", f"Trabajador {k + 1}", tx + rng.uniform(-30, 40), ty + rng.uniform(-30, 30), 0.5, 0.5, 1.7, temp=34))
    s.base = (float(tx - 60), float(ty - 50))
    oh = _objetos_raster(s, objetos)
    agua = agua & (oh < 0.5)
    s.epocas["A"] = {"dtm": dtm, "veg": veg, "objetos": objetos, "objetos_h": oh, "color": color, "agua": agua,
                     "hallazgos": [], "fecha": "Levantamiento anterior"}
    avance(s, rng, opciones or {}, avisar)
    return s


def profundidad_cerrada(dtm, paso):
    import heapq
    d = dtm[::paso, ::paso].astype(np.float64)
    ny, nx = d.shape
    lleno = np.full_like(d, np.inf)
    visto = np.zeros(d.shape, bool)
    cola = []
    for i in range(ny):
        for j in (0, nx - 1):
            heapq.heappush(cola, (d[i, j], i, j))
            visto[i, j] = True
    for j in range(1, nx - 1):
        for i in (0, ny - 1):
            heapq.heappush(cola, (d[i, j], i, j))
            visto[i, j] = True
    while cola:
        z, i, j = heapq.heappop(cola)
        lleno[i, j] = z
        for a, b in ((i + 1, j), (i - 1, j), (i, j + 1), (i, j - 1)):
            if 0 <= a < ny and 0 <= b < nx and not visto[a, b]:
                visto[a, b] = True
                heapq.heappush(cola, (max(z, d[a, b]), a, b))
    return lleno - d


def _corte(sitio, X, Y, cx, cy, ra, rb, rot, piso):
    c, s = math.cos(rot), math.sin(rot)
    u, v = (X - cx) * c + (Y - cy) * s, -(X - cx) * s + (Y - cy) * c
    m = (u / ra) ** 2 + (v / rb) ** 2 <= 1
    d = distance_transform_edt(~m) * sitio.res
    return terrazas(d, piso).astype(np.float32), m


def avance(sitio, rng, opciones, avisar=print):
    avisar("Simulando el avance de minado entre levantamientos (época B)…")
    A = sitio.epocas["A"]
    dtm = A["dtm"].copy()
    X, Y = sitio.malla()
    zona = sitio.zonas_de("extraccion")[0]
    mz = sitio.mascara(zona["puntos"])
    interior = distance_transform_edt(mz) * sitio.res
    margen = np.zeros_like(mz)
    b = int(0.14 * sitio.nx)
    margen[b:-b, b:-b] = True
    if (mz & margen).sum() > 2000:
        mz_busqueda = mz & margen
    else:
        mz_busqueda = mz
    hallazgos = []
    paso = max(1, int(10 / sitio.res))
    hondo = profundidad_cerrada(dtm, paso)
    sub = mz_busqueda[::paso, ::paso][:hondo.shape[0], :hondo.shape[1]]
    if sub.any() and float(hondo[sub].max()) > 8:
        hi, hj = np.unravel_index(int(np.argmax(np.where(sub, hondo, -1))), hondo.shape)
        ventana = np.zeros_like(mz_busqueda)
        ventana[max(0, hi * paso - 60):hi * paso + 60, max(0, hj * paso - 60):hj * paso + 60] = True
        zs = np.where(mz_busqueda & ventana, dtm, np.inf)
    else:
        zs = np.where(mz_busqueda, dtm, np.inf)
    k = int(np.argmin(zs))
    fi, fj = np.unravel_index(k, dtm.shape)
    fx, fy = sitio.a_xy(fi, fj)
    fx, fy = float(fx), float(fy)
    zmin = float(dtm[fi, fj])
    ext = min(math.sqrt(mz.sum()) * sitio.res, 0.6 * sitio.ancho)
    rot = rng.uniform(0, math.pi)
    corte1, piso1 = _corte(sitio, X, Y, fx, fy, 0.09 * ext, 0.065 * ext, rot, zmin - C.BANCO_ALTURA)
    dtm = np.where(mz, np.minimum(dtm, corte1), dtm)
    cerca = np.hypot(X - fx, Y - fy) < 0.45 * ext
    alto = np.where(mz_busqueda & cerca & (interior > 0.06 * ext), dtm - zmin, -np.inf)
    k = int(np.argmax(alto))
    pi_, pj = np.unravel_index(k, dtm.shape)
    px, py = sitio.a_xy(pi_, pj)
    px, py = float(px), float(py)
    zp = float(dtm[pi_, pj])
    ang = math.atan2(fy - py, fx - px)
    pcx, pcy = px + math.cos(ang) * 0.05 * ext, py + math.sin(ang) * 0.05 * ext
    corte2, piso2 = _corte(sitio, X, Y, pcx, pcy, 0.07 * ext, 0.04 * ext, ang, zp - 2.5 * C.BANCO_ALTURA)
    dtm = np.where(mz, np.minimum(dtm, corte2), dtm)
    zona.setdefault("cota_piso", round(zmin - 15, 1))
    if zona.get("cota_piso") is None:
        zona["cota_piso"] = round(zmin - 15, 1)
    if opciones.get("fuera_de_zona", True):
        borde = mz & ~binary_dilation(~mz, iterations=1)
        bi, bj = np.nonzero(mz & (distance_transform_edt(mz) <= 1.5))
        bx, by = sitio.a_xy(bi, bj)
        kk = int(np.argmin(np.hypot(bx - px, by - py)))
        nx_, ny_ = float(bx[kk]) - fx, float(by[kk]) - fy
        nn = math.hypot(nx_, ny_) or 1.0
        ox, oy = float(bx[kk]) + nx_ / nn * 45, float(by[kk]) + ny_ / nn * 45
        if 30 < ox < sitio.ancho - 30 and 30 < oy < sitio.ancho - 30:
            zo = float(sitio.muestrear(dtm, ox, oy)[0])
            corte3, _ = _corte(sitio, X, Y, ox, oy, 22, 14, ang, zo - 5)
            dtm = np.minimum(dtm, corte3)
            sitio.notas.append("Época B incluye una excavación fuera de la zona autorizada (para probar el cumplimiento)")
    if opciones.get("sobre_excavacion", False):
        cota = zona["cota_piso"]
        corte4, _ = _corte(sitio, X, Y, fx, fy, 14, 10, rot, cota - 3)
        dtm = np.minimum(dtm, corte4)
    acopios = sitio.zonas_de("acopio")
    if not acopios:
        ax_, ay_ = sitio.base[0] + 80, sitio.base[1] + 60
        acopios = [{"nombre": "Acopio nuevo", "tipo": "acopio", "puntos": poligono_elipse(ax_, ay_, 34, 34, 0, 20)}]
        sitio.zonas.append(acopios[0])
    for k, z in enumerate(acopios):
        cx_, cy_ = centroide(z["puntos"])
        mk = sitio.mascara(z["puntos"])
        cima = float(dtm[mk].max()) - float(sitio.muestrear(A["dtm"], cx_, cy_)[0]) if mk.any() else 0
        _cono(sitio, dtm, cx_ + 3, cy_ - 2, max(cima, 6.0) + (4.0 if k == 0 else -2.5))
        if k > 0:
            m = sitio.mascara(z["puntos"])
            dtm = np.where(m, np.minimum(dtm, A["dtm"] - 1.0 * np.clip((A["dtm"] - A["dtm"][m].min()) / 8, 0, 1)), dtm)
    cambio = (A["dtm"] - dtm) > 0.8
    zona_corte = cambio & mz
    corona = binary_dilation(zona_corte, iterations=int(14 / sitio.res)) & ~binary_dilation(zona_corte, iterations=int(9 / sitio.res))
    corona &= mz
    ci, cj = np.nonzero(corona)
    if len(ci):
        cxs, cys = sitio.a_xy(ci, cj)
        d2 = np.hypot(cxs - px, cys - py)
        cerca = np.argsort(d2)[:max(40, len(d2) // 25)]
        pts = np.column_stack([cxs[cerca], cys[cerca]])
        ang_p = np.arctan2(pts[:, 1] - pcy, pts[:, 0] - pcx)
        orden = np.argsort(ang_p)
        pts = pts[orden][::3]
        if len(pts) >= 4:
            longitud = float(np.sum(np.hypot(*np.diff(pts, axis=0).T)))
            if longitud < 400:
                for (x0, y0), (x1, y1) in zip(pts[:-1], pts[1:]):
                    if math.hypot(x1 - x0, y1 - y0) > 25:
                        continue
                    n = int(math.hypot(x1 - x0, y1 - y0) / (sitio.res * 0.5)) + 2
                    for t in np.linspace(0, 1, n):
                        i, j = sitio.a_ij(x0 + (x1 - x0) * t, y0 + (y1 - y0) * t)
                        i, j = int(i), int(j)
                        if 0 <= i < sitio.ny and 0 <= j < sitio.nx:
                            dtm[i, j] -= 0.9
                mx, my = pts[len(pts) // 2]
                hallazgos.append({"tipo": "grieta", "titulo": "Grieta de tensión detrás de la corona del talud",
                                  "x": float(mx), "y": float(my), "tam": 0.25, "largo": round(longitud, 1),
                                  "severidad": "alta", "puntos": pts.round(1).tolist(),
                                  "detalle": f"Grieta de {longitud:.0f} m a 9–14 m de la corona del corte nuevo"})
    caminos_zona = []
    for cam in sitio.caminos:
        p = np.asarray(cam["puntos"], dtype=float)
        dentro = [q for q in p if mz[int(np.clip(sitio.a_ij(*q)[0], 0, sitio.ny - 1)), int(np.clip(sitio.a_ij(*q)[1], 0, sitio.nx - 1))]]
        caminos_zona += dentro
    if caminos_zona:
        rx, ry = caminos_zona[len(caminos_zona) // 3]
    else:
        rx, ry = pcx + 0.05 * ext, pcy
    rr = np.hypot(X - rx, Y - ry)
    derrumbe = np.clip(1.4 * (1 - rr / 5.0), 0, None) + np.where(rr < 5, rng.uniform(0, 0.3, rr.shape), 0)
    dtm = dtm + derrumbe.astype(np.float32)
    hallazgos.append({"tipo": "derrumbe", "titulo": "Material caído sobre camino/rampa", "x": float(rx), "y": float(ry),
                      "tam": 2.5, "severidad": "media", "detalle": "Bloques de hasta 1.4 m sobre la vía de acarreo"})
    agua = A["agua"].copy()
    charco = piso1 & (dtm < zmin - C.BANCO_ALTURA + 0.6)
    charco &= np.hypot(X - fx, Y - fy) < 0.02 * ext
    agua |= charco
    if charco.any():
        hallazgos.append({"tipo": "agua", "titulo": "Agua acumulada en el piso del tajo", "x": fx, "y": fy, "tam": 6.0,
                          "severidad": "media", "detalle": f"{charco.sum() * sitio.res ** 2:.0f} m² de encharcamiento"})
    gy, gx = np.gradient(gaussian_filter(dtm, 6 / sitio.res), sitio.res)
    inter = np.degrees(np.arctan(np.hypot(gx, gy)))
    objetos = [dict(o) for o in A["objetos"]]
    for o in objetos:
        if o["tipo"] == "camion":
            o["x"] += rng.uniform(-60, 60)
            o["y"] += rng.uniform(-60, 60)
            o["rumbo"] = rng.uniform(0, 6.28)
        if o["tipo"] == "pala":
            o["x"], o["y"] = pcx, pcy
    rest = sitio.zonas_de("exclusion")
    if not rest:
        z = {"nombre": "Área de voladura", "tipo": "exclusion", "puntos": poligono_elipse(pcx, pcy, 0.05 * ext, 0.035 * ext, ang, 18)}
        sitio.zonas.append(z)
        rest = [z]
    vx, vy = centroide(rest[0]["puntos"])
    vx += rng.uniform(-8, 8)
    vy += rng.uniform(-8, 8)
    objetos.append(_obj("persona", "Persona dentro del área de voladura", vx, vy, 0.5, 0.5, 1.7, temp=34, alerta=True))
    objetos.append(_obj("camioneta", "Camioneta en área de voladura", vx + 6, vy + 4, 5, 2, 1.9, ang, temp=45, alerta=True))
    hallazgos.append({"tipo": "persona_exclusion", "titulo": "Persona dentro del área de voladura", "x": vx, "y": vy, "tam": 0.5,
                      "severidad": "crítica", "detalle": f"Trabajador detectado en «{rest[0]['nombre']}» con voladura programada"})
    if len(ci):
        k = int(np.argmin(np.hypot(cxs - px, cys - py)))
        ex_, ey_ = float(cxs[k]) + 4, float(cys[k]) + 3
        objetos.append(_obj("camion", "Camión estacionado junto a la corona", ex_, ey_, 12, 7, 6, ang + 1.57, temp=55, alerta=True))
        hallazgos.append({"tipo": "equipo_corona", "titulo": "Equipo a menos de 10 m de la corona", "x": ex_, "y": ey_, "tam": 7.0,
                          "severidad": "alta", "detalle": "Camión estacionado en zona de posible desprendimiento"})
    for o in objetos:
        if o["tipo"] == "banda" and o["nombre"].endswith(" 7"):
            o["temp"] = 96.0
            hallazgos.append({"tipo": "termico", "titulo": "Rodillo de banda sobrecalentado", "x": o["x"], "y": o["y"], "tam": 0.35,
                              "temp": 96.0, "severidad": "alta", "detalle": "Rodamiento a 96 °C (normal ≈ 38 °C)"})
        if o["tipo"] == "subestacion":
            o["temp"] = 112.0
            o["falla"] = True
            hallazgos.append({"tipo": "termico", "titulo": "Transformador con punto caliente", "x": o["x"] + 3, "y": o["y"], "tam": 0.8,
                              "temp": 112.0, "severidad": "crítica", "detalle": "Conexión del transformador a 112 °C"})
    if acopios:
        ax_, ay_ = centroide(acopios[0]["puntos"])
        hallazgos.append({"tipo": "termico", "titulo": "Autocombustión en acopio de mineral", "x": ax_ + 6, "y": ay_ - 4, "tam": 3.5,
                          "temp": 68.0, "severidad": "media", "detalle": "Zona del acopio a 68 °C por oxidación de sulfuros"})
    oh = _objetos_raster(sitio, objetos)
    veg = np.where(binary_dilation(np.abs(A["dtm"] - dtm) > 0.3, iterations=2), 0, A["veg"]).astype(np.float32)
    if sitio.real:
        color = A["color"].astype(np.float32)
        nuevo = binary_dilation(np.abs(A["dtm"] - dtm) > 0.3, iterations=1)
        sombra = _sombreado(dtm, sitio.res)[..., None]
        fresca = np.array([170, 158, 140], np.float32) * (0.55 + 0.6 * sombra) + rng.normal(0, 6, color.shape)
        color = np.where(nuevo[..., None], fresca, color)
        color = np.where(agua[..., None] & ~A["agua"][..., None], np.array([70, 100, 96], np.float32), color)
        color = np.clip(color, 0, 255).astype(np.uint8)
        _pintar_objetos(sitio, color, [o for o in objetos if o.get("alerta") or o["tipo"] in ("camion", "pala")])
    else:
        base, capas = sitio._capas_demo
        capas = [(m, t, v) for m, t, v in capas]
        capas[-1] = (agua, capas[-1][1], capas[-1][2])
        color = _textura_demo(sitio, dtm, np.maximum(base, dtm), np.random.default_rng(11), capas)
        _pintar_objetos(sitio, color, objetos)
        color = _tintar_vegetacion(color, veg, rng)
    sitio.epocas["B"] = {"dtm": dtm.astype(np.float32), "veg": veg, "objetos": objetos, "objetos_h": oh, "color": color,
                         "agua": agua, "hallazgos": hallazgos, "fecha": "Levantamiento actual"}
    sitio.talud_max_b = float(np.percentile(inter[mz], 99.5))
    return sitio


def temperatura(sitio, epoca, t_aire=24.0):
    e = sitio.epocas[epoca]
    sol = _sombreado(e["dtm"], sitio.res, 135.0, 55.0)
    lum = e["color"].astype(np.float32).mean(axis=2) / 255.0
    T = t_aire + 4 + 16 * sol * (1.15 - 0.6 * lum)
    T = np.where(e["veg"] > 0.5, t_aire + 2.5 - 0.15 * e["veg"], T)
    T = np.where(e["agua"], t_aire - 4.0, T)
    for o in e["objetos"]:
        if "temp" not in o:
            continue
        i, j = sitio.a_ij(o["x"], o["y"])
        r = max(1, int(max(o["l"], o["w"]) / 2 / sitio.res))
        i, j = int(i), int(j)
        i0, i1, j0, j1 = max(0, i - r), min(sitio.ny, i + r + 1), max(0, j - r), min(sitio.nx, j + r + 1)
        if i1 > i0 and j1 > j0:
            T[i0:i1, j0:j1] = np.maximum(T[i0:i1, j0:j1], o["temp"] * 0.85 + t_aire * 0.15 if o["tipo"] != "persona" else o["temp"])
    for h in e["hallazgos"]:
        if h["tipo"] == "termico":
            i, j = sitio.a_ij(h["x"], h["y"])
            r = max(1, int(h["tam"] / sitio.res))
            i, j = int(i), int(j)
            T[max(0, i - r):i + r + 1, max(0, j - r):j + r + 1] = h["temp"]
    return T.astype(np.float32)
