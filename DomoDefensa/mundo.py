import math

import numpy as np

import config as C


class Zona:
    __slots__ = ("nombre", "x", "y", "r", "valor", "tipo", "activa")

    def __init__(self, nombre, x, y, r, valor=2, tipo="area", activa=True):
        self.nombre, self.x, self.y, self.r = nombre, float(x), float(y), float(r)
        self.valor, self.tipo, self.activa = float(valor), tipo, activa

    def contiene(self, x, y, margen=0.0):
        return (x - self.x) ** 2 + (y - self.y) ** 2 <= (self.r + margen) ** 2

    def distancia_borde(self, x, y):
        return math.hypot(x - self.x, y - self.y) - self.r

    def copia(self):
        return Zona(self.nombre, self.x, self.y, self.r, self.valor, self.tipo, self.activa)

    def a_dict(self):
        return {"nombre": self.nombre, "x": self.x, "y": self.y, "r": self.r, "valor": self.valor,
                "tipo": self.tipo, "activa": self.activa}


PUEBLOS = [
    ("Valle Alto", 22, 40, 2.2, 2), ("San Ciro", 40, 44, 2.8, 3), ("Mirasol", 58, 38, 2.0, 2),
    ("Cerro Verde", 30, 26, 2.0, 2), ("Puerto Lumen", 52, 14, 3.0, 3), ("Nueva Aurora", 66, 24, 2.2, 2),
    ("Las Brisas", 12, 18, 1.6, 1), ("Roca Blanca", 45, 30, 1.5, 1), ("Puesto Norte", 34, 50, 1.6, 2),
]

FRENTES = {
    "norte": (5000.0, 55000.0, 75000.0, 60000.0),
    "este": (75000.0, 5000.0, 80000.0, 50000.0),
    "noreste": (60000.0, 50000.0, 80000.0, 60000.0),
    "sur": (5000.0, 0.0, 75000.0, 5000.0),
    "oeste": (0.0, 5000.0, 5000.0, 55000.0),
}
NOMBRES_FRENTES = {"norte": "Norte", "este": "Este", "sur": "Sur", "oeste": "Oeste", "noreste": "Noreste"}


def pueblos():
    return [Zona(n, x * 1000, y * 1000, r * 1000, v, "pueblo") for n, x, y, r, v in PUEBLOS]


def pueblo(nombre):
    for z in pueblos():
        if z.nombre == nombre:
            return z
    raise KeyError(nombre)


def en_frente(x, y, frentes=None):
    for nombre, (x0, y0, x1, y1) in FRENTES.items():
        if frentes is not None and nombre not in frentes:
            continue
        if x0 <= x <= x1 and y0 <= y <= y1:
            return True
    return False


def distancia_frente(x, y, frentes=None):
    d = math.inf
    for nombre, (x0, y0, x1, y1) in FRENTES.items():
        if frentes is not None and nombre not in frentes:
            continue
        dx = max(x0 - x, 0, x - x1)
        dy = max(y0 - y, 0, y - y1)
        d = min(d, math.hypot(dx, dy))
    return d


def _muestras_zona(z, n=24):
    pts = [(z.x, z.y)]
    for k in range(n):
        a = 2 * math.pi * k / n
        for f in (0.5, 1.0):
            pts.append((z.x + z.r * f * math.cos(a), z.y + z.r * f * math.sin(a)))
    return np.array(pts)


def cobertura(z, x, y):
    p = _muestras_zona(z)
    d = np.hypot(p[:, 0] - x, p[:, 1] - y)
    return float(np.mean(d <= C.INT_ALCANCE * 0.8))


def posicion_optima(zonas, frentes=None):
    activas = [z for z in zonas if z.activa]
    if not activas:
        return C.MAPA_W / 2, C.MAPA_H / 2
    xs = np.arange(2000, C.MAPA_W - 1999, 1000.0)
    ys = np.arange(2000, C.MAPA_H - 1999, 1000.0)
    X, Y = np.meshgrid(xs, ys)
    X, Y = X.ravel(), Y.ravel()
    puntaje = np.zeros_like(X)
    peso = sum(z.valor for z in activas)
    cx = sum(z.x * z.valor for z in activas) / peso
    cy = sum(z.y * z.valor for z in activas) / peso
    for z in activas:
        p = _muestras_zona(z)
        d = np.hypot(p[:, 0][None, :] - X[:, None], p[:, 1][None, :] - Y[:, None])
        puntaje += z.valor * np.mean(d <= C.INT_ALCANCE * 0.8, axis=1)
        dentro = np.hypot(X - z.x, Y - z.y) < z.r + 600
        puntaje -= dentro * 0.3
    df = np.array([distancia_frente(x, y, frentes) for x, y in zip(X, Y)])
    puntaje -= np.where(df < C.DISTANCIA_FRENTE_MIN, 5.0, 0.0)
    mejor = None
    for nombre, (x0, y0, x1, y1) in FRENTES.items():
        if frentes is not None and nombre not in frentes:
            continue
        px, py = min(max(cx, x0), x1), min(max(cy, y0), y1)
        d = math.hypot(px - cx, py - cy)
        if mejor is None or d < mejor[0]:
            mejor = (d, px, py)
    tx, ty = cx, cy
    if mejor is not None and mejor[0] > 1:
        tx = cx + (mejor[1] - cx) / mejor[0] * 4000
        ty = cy + (mejor[2] - cy) / mejor[0] * 4000
    puntaje -= np.hypot(X - tx, Y - ty) * 2e-5
    i = int(np.argmax(puntaje))
    return float(X[i]), float(Y[i])


def _rejilla(paso=1500.0):
    xs = np.arange(2000, C.MAPA_W - 1999, paso)
    ys = np.arange(2000, C.MAPA_H - 1999, paso)
    X, Y = np.meshgrid(xs, ys)
    return X.ravel(), Y.ravel()


def siguiente_posicion(zonas, existentes, frentes=None, X=None, Y=None):
    activas = [z for z in zonas if z.activa]
    if X is None:
        X, Y = _rejilla()
    if not activas:
        if not existentes:
            return C.MAPA_W / 2, C.MAPA_H / 2
        ang = len(existentes) * 2.4
        x0, y0 = existentes[0]
        return (min(max(x0 + 9000 * math.cos(ang), 3000), C.MAPA_W - 3000),
                min(max(y0 + 9000 * math.sin(ang), 3000), C.MAPA_H - 3000))
    puntos, pesos = [], []
    for z in activas:
        p = _muestras_zona(z)
        puntos.append(p)
        pesos.append(np.full(len(p), z.valor / len(p)))
    P = np.vstack(puntos)
    w = np.concatenate(pesos)
    alcance = C.INT_ALCANCE * 0.8
    cubiertos = np.zeros(len(P))
    for ex, ey in existentes:
        cubiertos += np.hypot(P[:, 0] - ex, P[:, 1] - ey) <= alcance
    D = np.hypot(P[:, 0][None, :] - X[:, None], P[:, 1][None, :] - Y[:, None]) <= alcance
    puntaje = (D * w * (cubiertos == 0)).sum(1) + 0.25 * (D * w * (cubiertos == 1)).sum(1)
    for z in activas:
        puntaje -= (np.hypot(X - z.x, Y - z.y) < z.r + 600) * 0.3
    df = np.array([distancia_frente(x, y, frentes) for x, y in zip(X, Y)])
    puntaje -= np.where(df < C.DISTANCIA_FRENTE_MIN, 50.0, 0.0)
    for ex, ey in existentes:
        puntaje -= np.where(np.hypot(X - ex, Y - ey) < C.SEPARACION_BATERIAS, 20.0, 0.0)
    cx = float(np.sum(P[:, 0] * w * (cubiertos == 0)) / max(np.sum(w * (cubiertos == 0)), 1e-9)) if (cubiertos == 0).any() else float(np.mean(P[:, 0]))
    cy = float(np.sum(P[:, 1] * w * (cubiertos == 0)) / max(np.sum(w * (cubiertos == 0)), 1e-9)) if (cubiertos == 0).any() else float(np.mean(P[:, 1]))
    puntaje -= np.hypot(X - cx, Y - cy) * 2e-5
    i = int(np.argmax(puntaje))
    return float(X[i]), float(Y[i])


def posiciones_optimas(zonas, n, frentes=None):
    if n <= 1:
        return [posicion_optima(zonas, frentes)]
    X, Y = _rejilla()
    pos = []
    for _ in range(int(n)):
        pos.append(siguiente_posicion(zonas, pos, frentes, X, Y))
    return pos


def asignar(actuales, objetivos):
    libres = list(range(len(objetivos)))
    plan = [None] * len(actuales)
    pares = sorted((math.dist(a, objetivos[j]), i, j) for i, a in enumerate(actuales) for j in libres)
    usados_i, usados_j = set(), set()
    for d, i, j in pares:
        if i in usados_i or j in usados_j:
            continue
        plan[i] = objetivos[j]
        usados_i.add(i)
        usados_j.add(j)
    return plan


def terreno(ancho=320, alto=240, semilla=11):
    rng = np.random.default_rng(semilla)
    fx = np.fft.fftfreq(ancho)[None, :]
    fy = np.fft.fftfreq(alto)[:, None]
    f = np.sqrt(fx ** 2 + fy ** 2)
    f[0, 0] = 1
    ruido = np.fft.ifft2(np.fft.fft2(rng.normal(size=(alto, ancho))) / f ** 1.9).real
    ruido = (ruido - ruido.min()) / np.ptp(ruido)
    yy = np.linspace(0, 1, alto)[:, None]
    h = ruido * 650 + yy * 220
    h = np.flipud(h)
    for n, x, y, r, v in PUEBLOS:
        ix, iy = x * 1000 / C.MAPA_W * ancho, (1 - y * 1000 / C.MAPA_H) * alto
        gy, gx = np.mgrid[0:alto, 0:ancho]
        w = np.exp(-((gx - ix) ** 2 + (gy - iy) ** 2) / (2 * (r * 1000 / C.MAPA_W * ancho * 1.6) ** 2))
        h = h * (1 - w) + np.median(h) * 0.6 * w
    return h


def caminos():
    pts = [(x * 1000, y * 1000) for _, x, y, _, _ in PUEBLOS]
    n = len(pts)
    usados = {0}
    aristas = []
    while len(usados) < n:
        mejor = None
        for i in usados:
            for j in range(n):
                if j in usados:
                    continue
                d = math.dist(pts[i], pts[j])
                if mejor is None or d < mejor[0]:
                    mejor = (d, i, j)
        aristas.append((pts[mejor[1]], pts[mejor[2]]))
        usados.add(mejor[2])
    aristas.append((pts[1], pts[2]))
    aristas.append((pts[3], pts[7]))
    return aristas
