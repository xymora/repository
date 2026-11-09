import math

import numpy as np

import config as C

DX = 0.1

MATERIALES = (
    ("asfalto", 1.00, 0.015, 0.05, "#4a4f57"),
    ("tierra",  0.75, 0.030, 0.15, "#8b5a2b"),
    ("pasto",   0.55, 0.050, 0.10, "#4f7f3a"),
    ("grava",   0.60, 0.045, 0.30, "#9c9283"),
    ("arena",   0.45, 0.140, 0.20, "#d8b56a"),
    ("lodo",    0.32, 0.170, 0.25, "#5b4227"),
    ("roca",    0.85, 0.035, 0.45, "#77736d"),
    ("nieve",   0.28, 0.090, 0.15, "#e6edf5"),
    ("hielo",   0.12, 0.010, 0.05, "#9fd3ec"),
)
NOMBRES_MAT = tuple(m[0] for m in MATERIALES)
MU = np.array([m[1] for m in MATERIALES])
RR = np.array([m[2] for m in MATERIALES])
RUGO = np.array([m[3] for m in MATERIALES])
COLORES = tuple(m[4] for m in MATERIALES)
M = {n: i for i, n in enumerate(NOMBRES_MAT)}

_NIVELES = (
    (("plano", "colinas_suaves"),           ("asfalto", "tierra", "pasto"), 0.6, 0.000, 160),
    (("baches", "colinas"),                 ("grava",),                     0.8, 0.020, 190),
    (("rocas", "troncos"),                  ("arena", "lodo", "roca"),      1.0, 0.030, 220),
    (("escalones", "zanja"),                (),                             1.1, 0.040, 240),
    (("rampa", "pendiente"),                ("nieve",),                     1.2, 0.050, 260),
    ((),                                    ("hielo",),                     1.3, 0.055, 280),
    ((),                                    (),                             1.45, 0.060, 300),
    ((),                                    (),                             1.6, 0.065, 320),
)


def datos_nivel(nivel):
    nivel = max(1, min(nivel, len(_NIVELES)))
    rasgos, mats = [], []
    for r, m, *_ in _NIVELES[:nivel]:
        rasgos += r
        mats += m
    _, _, amp, curva, largo = _NIVELES[nivel - 1]
    return rasgos, mats, amp, curva, largo


def descripcion_nivel(nivel):
    rasgos, mats, *_ = datos_nivel(nivel)
    nuevos_r, nuevos_m = _NIVELES[max(1, min(nivel, len(_NIVELES))) - 1][:2]
    nuevo = ", ".join(n.replace("_", " ") for n in nuevos_r + nuevos_m) or "más difícil"
    return f"Nivel {nivel}: {nuevo}"



def _u(largo):
    return np.arange(1, int(largo / DX) + 1) * DX


def _plano(rng, amp):
    u = _u(rng.uniform(15, 30))
    off = np.zeros_like(u)
    for _ in range(3):
        a, lam, f = rng.uniform(0.01, 0.04) * amp, rng.uniform(4, 12), rng.uniform(0, 6.3)
        off += a * (np.sin(2 * math.pi * u / lam + f) - math.sin(f))
    return off


def _colinas(rng, amp, suaves=False):
    lam = rng.uniform(22, 40) if suaves else rng.uniform(16, 30)
    a = rng.uniform(0.3, 0.8) * amp if suaves else rng.uniform(0.8, 1.8) * amp
    a = min(a, (0.25 if suaves else 0.45) * lam / (2 * math.pi))
    f = rng.uniform(0, 2 * math.pi)
    u = _u(lam * rng.uniform(1.0, 2.0))
    return a * (np.sin(2 * math.pi * u / lam + f) - math.sin(f))


def _baches(rng, amp):
    u = _u(rng.uniform(20, 35))
    off = np.zeros_like(u)
    for c in np.arange(3, u[-1] - 3, rng.uniform(2.5, 4.5)):
        a = rng.uniform(-0.18, 0.14) * amp
        w = rng.uniform(0.4, 1.4)
        off += a * np.exp(-((u - c) / w) ** 2)
    return off


def _rocas(rng, amp):
    u = _u(rng.uniform(18, 30))
    off = _plano(rng, amp * 2)[: len(u)]
    off = np.pad(off, (0, len(u) - len(off)), mode="edge")
    rocas = np.zeros_like(u)
    c = 2.0
    while c < u[-1] - 2:
        h = min(rng.uniform(0.06, 0.24) * amp, 0.32)
        w = rng.uniform(0.25, 0.8)
        rocas = np.maximum(rocas, h * np.sqrt(np.clip(1 - ((u - c) / w) ** 2, 0, None)))
        c += rng.uniform(0.9, 3.0)
    return off + rocas


def _troncos(rng, amp):
    u = _u(rng.uniform(20, 32))
    off = np.zeros_like(u)
    c = rng.uniform(3, 5)
    while c < u[-1] - 3:
        h = min(rng.uniform(0.12, 0.24) * amp, 0.32)
        w = h * 0.9
        off = np.maximum(off, h * np.sqrt(np.clip(1 - ((u - c) / w) ** 2, 0, None)))
        c += rng.uniform(4, 8)
    return off


def _escalones(rng, amp):
    n = rng.integers(2, 5)
    alt = min(rng.uniform(0.10, 0.20) * amp, 0.28)
    descanso = rng.uniform(2.5, 4.0)
    perfil = [0.0] * int(3 / DX)
    for i in range(1, n + 1):
        perfil += [i * alt] * int(descanso / DX)
    for i in range(n - 1, -1, -1):
        perfil += [i * alt] * int(descanso / DX)
    perfil += [0.0] * int(3 / DX)
    return np.array(perfil)


def _zanja(rng, amp):
    prof = min(rng.uniform(0.3, 0.7) * amp, 1.0)
    ancho = rng.uniform(1.5, 3.0)
    u = _u(6 + ancho)
    off = np.zeros_like(u)
    dentro = (u > 3) & (u < 3 + ancho)
    off[dentro] = -prof * 0.5 * (1 - np.cos(2 * math.pi * (u[dentro] - 3) / ancho))
    return off


def _rampa(rng, amp):
    alt = min(rng.uniform(0.6, 1.2) * amp, 1.8)
    largo_rampa = alt / 0.35
    u = _u(4 + largo_rampa + rng.uniform(12, 18))
    off = np.zeros_like(u)
    en = (u > 4) & (u <= 4 + largo_rampa)
    s = (u[en] - 4) / largo_rampa
    off[en] = alt * (0.6 * s + 0.4 * s ** 2)
    return off


def _pendiente(rng, amp):
    p = min(rng.uniform(0.2, 0.32) * amp, 0.5)
    subida = rng.uniform(10, 18)
    tramos = [(3, 0.0), (subida, p), (rng.uniform(3, 6), 0.0),
              (subida * rng.uniform(0.6, 1.2), -p), (3, 0.0)]
    pend = np.concatenate([np.full(int(l / DX), q) for l, q in tramos])
    k = int(2.0 / DX)
    pend = np.convolve(pend, np.ones(k) / k, mode="same")
    return np.cumsum(pend) * DX


RASGOS = {
    "plano": _plano,
    "colinas_suaves": lambda rng, amp: _colinas(rng, amp, suaves=True),
    "colinas": _colinas,
    "baches": _baches,
    "rocas": _rocas,
    "troncos": _troncos,
    "escalones": _escalones,
    "zanja": _zanja,
    "rampa": _rampa,
    "pendiente": _pendiente,
}

_MATERIAL_FIJO = {"rocas": ("roca", "grava"), "escalones": ("asfalto", "roca"),
                  "rampa": ("tierra", "asfalto")}


def maximo_adelante(valores, n):
    from numpy.lib.stride_tricks import sliding_window_view
    relleno = np.concatenate([valores, np.full(n - 1, valores[-1])])
    return sliding_window_view(relleno, n).max(axis=1)


class Pista:
    def __init__(self, nivel, semilla):
        rng = np.random.default_rng(semilla)
        self.nivel = nivel
        self.semilla = semilla
        rasgos, mats, amp, curva_max, largo = datos_nivel(nivel)

        alturas, materiales, curvas = [], [], []
        self.secciones = []
        h = 0.0

        def agregar(off, rasgo, mat, kappa):
            nonlocal h
            x0 = len(alturas) * DX
            alturas.extend(h + off)
            materiales.extend([M[mat]] * len(off))
            curvas.extend([kappa] * len(off))
            h += off[-1]
            self.secciones.append((x0, len(alturas) * DX, rasgo, mat))

        agregar(np.zeros(int(15 / DX)), "salida", "asfalto", 0.0)
        while len(alturas) * DX < largo:
            rasgo = rasgos[rng.integers(len(rasgos))]
            off = RASGOS[rasgo](rng, amp)
            n3 = int(3 / DX)
            pend = float(np.max(np.abs(off[n3:] - off[:-n3])) / 3) if len(off) > n3 else 0.0
            opciones = [m for m in _MATERIAL_FIJO.get(rasgo, mats) if m in mats] or mats
            viables = [m for m in opciones if MU[M[m]] * 0.5 >= pend]
            if not viables:
                viables = [max(set(opciones) | set(mats), key=lambda m: MU[M[m]])]
            mat = viables[rng.integers(len(viables))]
            k_max = curva_max * min(1.0, MU[M[mat]] / 0.6)
            kappa = 0.0 if rng.random() < 0.35 else rng.uniform(-k_max, k_max)
            agregar(off, rasgo, mat, kappa)
        agregar(np.zeros(int(25 / DX)), "meta", "asfalto", 0.0)

        self.hs = np.array(alturas)
        self.xs = np.arange(len(self.hs)) * DX
        self.mat = np.array(materiales, dtype=np.int64)
        k = int(8 / DX)
        self.kappa = np.convolve(np.array(curvas), np.ones(k) / k, mode="same")
        agarre = np.minimum(C.A_LAT_MAX, 0.85 * MU[np.array(materiales, dtype=np.int64)] * C.G)
        limite = agarre / C.V_DISENO ** 2
        self.kappa = np.clip(self.kappa, -limite, limite)
        self.kmax = maximo_adelante(np.abs(self.kappa), int(C.VENTANA_CURVAS / DX))
        self.rumbo = np.cumsum(self.kappa) * DX
        self.mapa_x = np.cumsum(np.cos(self.rumbo)) * DX
        self.mapa_y = np.cumsum(np.sin(self.rumbo)) * DX
        self.mu = MU[self.mat]
        self.mu_min = -maximo_adelante(-self.mu, int(C.VENTANA_CURVAS / DX))
        self.rr = RR[self.mat]
        self.rugo = RUGO[self.mat]
        self.longitud = self.xs[-1]
        self.salida = 6.0
        self.meta = self.longitud - 15.0
        self.tiempo_max = (self.meta - self.salida) / 3.0 + 15.0

    def altura(self, x):
        return np.interp(x, self.xs, self.hs)

    def indice(self, x):
        i = (np.asarray(x) * (1 / DX)).astype(np.int64)
        return np.minimum(np.maximum(i, 0), len(self.xs) - 1)

    def resumen(self):
        vistos = []
        for _, _, r, m in self.secciones[1:-1]:
            t = f"{r.replace('_', ' ')}/{m}"
            if t not in vistos:
                vistos.append(t)
        return ", ".join(vistos)
