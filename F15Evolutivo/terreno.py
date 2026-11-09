import math
import os

import numpy as np

import config as C

AQUI = os.path.dirname(os.path.abspath(__file__))
T = C.TAM_MUNDO
N = C.CELDAS
CELDA = T / N
MITAD = T / 2


class Aeropuerto:
    def __init__(self, nombre, siglas, x, z, rumbo, largo, ancho, elev):
        self.nombre, self.siglas = nombre, siglas
        self.cx, self.cz = x, z
        self.rumbo, self.largo, self.ancho, self.elev = rumbo, largo, ancho, elev
        r = math.radians(rumbo)
        self.ux, self.uz = math.sin(r), -math.cos(r)
        self.px, self.pz = -self.uz, self.ux
        self.umbral = (x - self.ux * largo / 2, z - self.uz * largo / 2)
        self.numero = int(round(rumbo / 10)) % 36 or 36

    def local(self, x, z):
        dx, dz = x - self.umbral[0], z - self.umbral[1]
        return dx * self.ux + dz * self.uz, dx * self.px + dz * self.pz

    def mundo(self, s, l, y=None):
        x = self.umbral[0] + self.ux * s + self.px * l
        z = self.umbral[1] + self.uz * s + self.pz * l
        return np.array([x, self.elev if y is None else y, z])

    def en_pista(self, x, z, margen=0.0):
        s, l = self.local(x, z)
        return (s > -margen) & (s < self.largo + margen) & (np.abs(l) < self.ancho / 2 + margen)


AEROPUERTOS = [
    Aeropuerto("Base Aérea Halcón", "BAH", -1800.0, 6200.0, 340.0, 3000.0, 45.0, 62.0),
    Aeropuerto("Aeródromo Cumbre Norte", "ACN", 6800.0, -12600.0, 260.0, 2400.0, 40.0, 410.0),
]
BASE = AEROPUERTOS[0]


def _ruido(rng, n, celdas):
    g = rng.random((celdas + 1, celdas + 1))
    t = np.linspace(0, celdas, n, endpoint=True)
    i = np.minimum(t.astype(int), celdas - 1)
    f = t - i
    f = f * f * (3 - 2 * f)
    a = g[i][:, i] * (1 - f)[None, :] + g[i][:, i + 1] * f[None, :]
    b = g[i + 1][:, i] * (1 - f)[None, :] + g[i + 1][:, i + 1] * f[None, :]
    return a * (1 - f)[:, None] + b * f[:, None]


def _fbm(rng, n, base, octavas, persist=0.5):
    total, amp, suma = np.zeros((n, n)), 1.0, 0.0
    for o in range(octavas):
        total += amp * _ruido(rng, n, base * 2 ** o)
        suma += amp
        amp *= persist
    return total / suma


def _suave(x):
    x = np.clip(x, 0, 1)
    return x * x * (3 - 2 * x)


def generar():
    rng = np.random.default_rng(C.SEMILLA_MUNDO)
    n = N + 1
    eje = np.linspace(-MITAD, MITAD, n)
    X, Z = np.meshgrid(eje, eje)
    base = _fbm(rng, n, 3, 7)
    cresta = 1 - np.abs(2 * _fbm(rng, n, 4, 7, 0.52) - 1)
    costa = _fbm(rng, n, 5, 5)
    r = np.sqrt(X ** 2 + Z ** 2) / MITAD
    isla = _suave((0.9 - r + 0.35 * (costa - 0.5)) / 0.22)
    zona = np.ones_like(X)
    for a in AEROPUERTOS:
        d = np.hypot(X - a.cx, Z - a.cz)
        zona = np.minimum(zona, _suave((d - 2500) / 6000))
    montes = (cresta ** 2.6) * (0.35 + 0.65 * _suave((base - 0.35) / 0.4))
    h = isla * (25 + 260 * base + 2100 * montes * zona) - (1 - isla) * 120
    h += isla * 40 * _fbm(rng, n, 32, 4)
    for a in AEROPUERTOS:
        s, l = a.local(X, Z)
        ds = np.maximum(np.maximum(-s - 500, s - a.largo - 500), 0)
        dl = np.maximum(np.abs(l) - 450, 0)
        d = np.hypot(ds, dl)
        w = 1 - _suave(d / 1800)
        h = h * (1 - w) + a.elev * w
        for lejos in (-s, s - a.largo):
            techo = a.elev + 0.03 * np.maximum(lejos, 0) - 20
            corredor = (lejos > 0) & (lejos < 22000)
            ancho = 1500 + lejos * 0.12
            m = corredor * (1 - _suave((np.abs(l) - ancho) / 2500))
            bajo = np.minimum(h, techo)
            h = h * (1 - m) + bajo * m
    return h.astype(np.float32)


def _cache():
    archivo = os.path.join(AQUI, C.CARPETA_DATOS, f"terreno_{C.SEMILLA_MUNDO}_{N}_v2.npy")
    try:
        h = np.load(archivo)
        if h.shape == (N + 1, N + 1):
            return h
    except (OSError, ValueError):
        pass
    h = generar()
    try:
        os.makedirs(os.path.dirname(archivo), exist_ok=True)
        np.save(archivo, h)
    except OSError:
        pass
    return h


ALTURAS = _cache()


def altura(x, z):
    gx = (np.asarray(x, dtype=np.float64) + MITAD) / CELDA
    gz = (np.asarray(z, dtype=np.float64) + MITAD) / CELDA
    fuera = (gx < 0) | (gz < 0) | (gx >= N) | (gz >= N)
    gx = np.clip(gx, 0, N - 1e-6)
    gz = np.clip(gz, 0, N - 1e-6)
    i, j = gz.astype(int), gx.astype(int)
    fz, fx = gz - i, gx - j
    a = ALTURAS[i, j] * (1 - fx) + ALTURAS[i, j + 1] * fx
    b = ALTURAS[i + 1, j] * (1 - fx) + ALTURAS[i + 1, j + 1] * fx
    return np.where(fuera, -120.0, a * (1 - fz) + b * fz)


def superficie(x, z):
    return np.maximum(altura(x, z), C.NIVEL_MAR)


def normales():
    gz, gx = np.gradient(ALTURAS.astype(np.float64), CELDA)
    nrm = np.stack([-gx, np.ones_like(gx), -gz], -1)
    return (nrm / np.linalg.norm(nrm, axis=-1, keepdims=True)).astype(np.float32)


DENSIDAD = _fbm(np.random.default_rng(C.SEMILLA_MUNDO + 1), N + 1, 6, 4).astype(np.float32)


def arboles(cantidad=22000):
    rng = np.random.default_rng(C.SEMILLA_MUNDO + 11)
    densidad = DENSIDAD
    nrm = normales()
    x = rng.uniform(-MITAD * 0.95, MITAD * 0.95, cantidad * 6)
    z = rng.uniform(-MITAD * 0.95, MITAD * 0.95, cantidad * 6)
    h = altura(x, z)
    i = ((z + MITAD) / CELDA).astype(int)
    j = ((x + MITAD) / CELDA).astype(int)
    ok = (h > 8) & (h < 1250) & (nrm[i, j, 1] > 0.86) & (densidad[i, j] > 0.5 - h / 6000)
    for a in AEROPUERTOS:
        s, l = a.local(x, z)
        ok &= ~((s > -1400) & (s < a.largo + 1400) & (np.abs(l) < 420))
        ok &= np.hypot(x - a.cx, z - a.cz) > 1300
    idx = np.flatnonzero(ok)[:cantidad]
    escala = rng.uniform(0.7, 1.5, len(idx)) * np.where(h[idx] > 700, 0.75, 1.0)
    tono = rng.uniform(0, 1, len(idx))
    return np.stack([x[idx], h[idx], z[idx], escala, tono], -1).astype(np.float32)


def edificios():
    rng = np.random.default_rng(C.SEMILLA_MUNDO + 2)
    lista = []
    for k, a in enumerate(AEROPUERTOS):
        for i in range(6 if k == 0 else 3):
            p = a.mundo(700 + i * 260, -a.ancho / 2 - 330)
            lista.append((p[0], a.elev, p[2], 46, 16, 52, a.rumbo, 1))
        p = a.mundo(a.largo * 0.45, -a.ancho / 2 - 200)
        lista.append((p[0], a.elev, p[2], 7, 32, 7, a.rumbo, 2))
        for i in range(10 if k == 0 else 4):
            p = a.mundo(rng.uniform(500, a.largo - 500), -a.ancho / 2 - rng.uniform(450, 700))
            lista.append((p[0], a.elev, p[2], rng.uniform(15, 40), rng.uniform(5, 12), rng.uniform(15, 30),
                          a.rumbo, 0))
    cx, cz = BASE.mundo(1500, 2600)[[0, 2]]
    for _ in range(260):
        x, z = cx + rng.normal(0, 700), cz + rng.normal(0, 700)
        h = altura(x, z)
        if h < 6:
            continue
        alto = rng.uniform(5, 14) if rng.random() < 0.85 else rng.uniform(20, 55)
        lista.append((x, float(h) - 1, z, rng.uniform(10, 26), alto, rng.uniform(10, 26), rng.uniform(0, 90), 0))
    return np.array(lista, dtype=np.float32)


EDIFICIOS = edificios()
