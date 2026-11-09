import numpy as np

NOMBRES = "IOTSZJL"
COLORES = ("#000000", "#2fd3f5", "#ffd23f", "#b065ff", "#3fe08a", "#ff4f64", "#4683ff", "#ff9a36", "#5d6577")
BASURA = 8

_BASE = {
    "I": ((1, 0), (1, 1), (1, 2), (1, 3)),
    "O": ((0, 1), (0, 2), (1, 1), (1, 2)),
    "T": ((0, 1), (1, 0), (1, 1), (1, 2)),
    "S": ((0, 1), (0, 2), (1, 0), (1, 1)),
    "Z": ((0, 0), (0, 1), (1, 1), (1, 2)),
    "J": ((0, 0), (1, 0), (1, 1), (1, 2)),
    "L": ((0, 2), (1, 0), (1, 1), (1, 2)),
}
CAJA = {"I": 4, "O": 4}


def _rotar(celdas, n):
    return tuple(sorted((c, n - 1 - r) for r, c in celdas))


def _rotaciones(nombre):
    n = CAJA.get(nombre, 3)
    estados = [tuple(sorted(_BASE[nombre]))]
    for _ in range(3):
        estados.append(estados[-1] if nombre == "O" else _rotar(estados[-1], n))
    return estados


ROTACIONES = {p: _rotaciones(p) for p in NOMBRES}
MIN_FILA = {p: [min(r for r, _ in e) for e in ROTACIONES[p]] for p in NOMBRES}
MIN_COL = {p: [min(c for _, c in e) for e in ROTACIONES[p]] for p in NOMBRES}
COL_SALIDA = 3


class Forma:
    def __init__(self, nombre, rot):
        celdas = ROTACIONES[nombre][rot]
        r0, c0 = MIN_FILA[nombre][rot], MIN_COL[nombre][rot]
        self.rot = rot
        self.dr = np.array([r - r0 for r, _ in celdas])
        self.dc = np.array([c - c0 for _, c in celdas])
        self.ancho = int(self.dc.max()) + 1
        self.fondo = np.array([self.dr[self.dc == k].max() for k in range(self.ancho)])
        self.x_salida = COL_SALIDA + c0
        self.clave = tuple(zip(self.dr.tolist(), self.dc.tolist()))


def _formas(nombre):
    vistas, formas = set(), []
    for rot in range(4):
        f = Forma(nombre, rot)
        if f.clave not in vistas:
            vistas.add(f.clave)
            formas.append(f)
    return formas


FORMAS = {p: _formas(p) for p in NOMBRES}


def celdas(nombre, rot, bx, by):
    return [(by + r, bx + c) for r, c in ROTACIONES[nombre][rot]]
