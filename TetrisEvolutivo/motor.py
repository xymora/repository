import numpy as np

import config as C
from piezas import BASURA, FORMAS, MIN_COL, MIN_FILA, NOMBRES, ROTACIONES, COL_SALIDA

CARACTERISTICAS = ("altura de aterrizaje", "celdas erosionadas", "transiciones en filas",
                   "transiciones en columnas", "huecos", "pozos acumulados", "profundidad de huecos",
                   "filas con huecos")
N_CARACT = len(CARACTERISTICAS)
PUNTOS_LINEAS = (0, 100, 300, 500, 800)
PATADAS = ((0, 0), (0, -1), (0, 1), (0, -2), (0, 2), (-1, 0), (-1, -1), (-1, 1))


def caracteristicas(tableros, filas, cols):
    n, alto, ancho = tableros.shape
    fila_n = np.arange(n)[:, None]
    tableros[fila_n, filas, cols] = True
    llenas = tableros.all(2)
    lineas = llenas.sum(1)
    erosion = lineas * llenas[fila_n, filas].sum(1)
    aterrizaje = alto - (filas.min(1) + filas.max(1)) / 2 - 0.5
    if lineas.any():
        orden = np.argsort(~llenas, axis=1, kind="stable")
        tableros = np.take_along_axis(tableros, orden[:, :, None], 1)
        tableros[np.arange(alto)[None, :] < lineas[:, None]] = False
    cubierto = np.logical_or.accumulate(tableros, axis=1)
    huecos_m = cubierto & ~tableros
    huecos = huecos_m.sum((1, 2))
    filas_huecos = huecos_m.any(2).sum(1)
    encima = np.cumsum(tableros, axis=1, dtype=np.int32)
    profundidad = (encima * huecos_m).sum((1, 2))
    con_muros = np.pad(tableros, ((0, 0), (0, 0), (1, 1)), constant_values=True)
    trans_filas = (con_muros[:, :, 1:] != con_muros[:, :, :-1]).sum((1, 2))
    con_piso = np.concatenate([tableros, np.ones((n, 1, ancho), bool)], axis=1)
    trans_cols = (con_piso[:, 1:] != con_piso[:, :-1]).sum((1, 2))
    pozo = ~cubierto & con_muros[:, :, :-2] & con_muros[:, :, 2:]
    acum = np.cumsum(pozo, axis=1, dtype=np.int32)
    reinicio = np.maximum.accumulate(np.where(pozo, 0, acum), axis=1)
    pozos = ((acum - reinicio) * pozo).sum((1, 2))
    feats = np.stack([aterrizaje, erosion, trans_filas, trans_cols, huecos, pozos, profundidad, filas_huecos], 1)
    return feats.astype(np.float64), lineas


def colocaciones(tablero, pieza):
    alto, ancho = tablero.shape
    lleno = tablero.any(0)
    tope = np.where(lleno, tablero.argmax(0), alto)
    rots, xs, ys, filas, cols = [], [], [], [], []
    for f in FORMAS[pieza]:
        x = np.arange(ancho - f.ancho + 1)
        y = (tope[x[:, None] + np.arange(f.ancho)[None, :]] - 1 - f.fondo[None, :]).min(1)
        if f.x_salida >= len(x) or y[f.x_salida] < 0:
            continue
        izq = f.x_salida
        while izq > 0 and y[izq - 1] >= 0:
            izq -= 1
        der = f.x_salida
        while der < len(x) - 1 and y[der + 1] >= 0:
            der += 1
        xv, yv = x[izq:der + 1], y[izq:der + 1]
        rots += [f.rot] * len(xv)
        xs.append(xv)
        ys.append(yv)
        filas.append(yv[:, None] + f.dr[None, :])
        cols.append(xv[:, None] + f.dc[None, :])
    if not rots:
        return None
    filas, cols = np.concatenate(filas), np.concatenate(cols)
    tableros = np.repeat(tablero[None], len(filas), 0)
    feats, lineas = caracteristicas(tableros, filas, cols)
    return {"rot": np.array(rots), "x": np.concatenate(xs), "y": np.concatenate(ys), "filas": filas,
            "cols": cols, "feats": feats, "lineas": lineas}


class Juego:
    def __init__(self, nivel, semilla):
        self.nivel = nivel
        self.alto, self.ancho = nivel.filas, C.ANCHO
        self.tablero = np.zeros((self.alto, self.ancho), bool)
        self.color = np.zeros((self.alto, self.ancho), np.int8)
        self.rng = np.random.default_rng(semilla)
        self.cola = []
        self.lineas = self.piezas = self.puntos = self.tetris = 0
        self.basura_puesta = 0
        self.terminado = self.superado = False
        self.motivo = ""
        self.ultimas = []
        self._cand = None
        for _ in range(nivel.basura_inicial):
            self._fila_basura(huecos=int(self.rng.integers(1, 3)))
        self.actual = self._sacar()
        if self.candidatos() is None:
            self._terminar("tablero lleno")

    def _sacar(self):
        while len(self.cola) < 8:
            self.cola += [NOMBRES[i] for i in self.rng.permutation(7)]
        return self.cola.pop(0)

    def proximas(self, n=3):
        return self.cola[:n]

    def candidatos(self):
        if self._cand is None:
            self._cand = colocaciones(self.tablero, self.actual)
        return self._cand

    def elegir(self, pesos):
        c = self.candidatos()
        if c is None:
            return None
        return int(np.argmax(c["feats"] @ pesos))

    def destino(self, i):
        c = self.candidatos()
        rot = int(c["rot"][i])
        return rot, int(c["x"][i]) - MIN_COL[self.actual][rot], int(c["y"][i]) - MIN_FILA[self.actual][rot]

    def colocar(self, i):
        c = self.candidatos()
        self.fijar(c["filas"][i], c["cols"][i])

    def fijar(self, filas, cols):
        self.tablero[filas, cols] = True
        self.color[filas, cols] = NOMBRES.index(self.actual) + 1
        llenas = self.tablero.all(1)
        self.ultimas = np.flatnonzero(llenas).tolist()
        n = len(self.ultimas)
        if n:
            quedan = ~llenas
            self.tablero = np.vstack([np.zeros((n, self.ancho), bool), self.tablero[quedan]])
            self.color = np.vstack([np.zeros((n, self.ancho), np.int8), self.color[quedan]])
        self.lineas += n
        self.puntos += PUNTOS_LINEAS[n]
        self.tetris += n == 4
        self.piezas += 1
        self._cand = None
        if self.nivel.basura_cada and self.piezas % self.nivel.basura_cada == 0:
            if not self._fila_basura():
                return self._terminar("la basura lo sepultó")
        if self.lineas >= self.nivel.meta:
            return self._terminar("meta alcanzada", True)
        if self.piezas >= self.nivel.max_piezas:
            return self._terminar("se acabaron las piezas")
        self.actual = self._sacar()
        if self.candidatos() is None:
            self._terminar("tablero lleno")

    def _fila_basura(self, huecos=1):
        if self.tablero[0].any():
            return False
        fila = np.ones(self.ancho, bool)
        fila[self.rng.choice(self.ancho, huecos, replace=False)] = False
        self.tablero = np.vstack([self.tablero[1:], fila[None]])
        self.color = np.vstack([self.color[1:], np.where(fila, BASURA, 0).astype(np.int8)[None]])
        self.basura_puesta += 1
        self._cand = None
        return True

    def _terminar(self, motivo, superado=False):
        self.terminado, self.superado, self.motivo = True, superado, motivo

    def jugar(self, pesos):
        while not self.terminado:
            i = self.elegir(pesos)
            if i is None:
                self._terminar("tablero lleno")
                break
            self.colocar(i)
        return self.resumen()

    def aptitud(self):
        return self.lineas + C.PREMIO_PIEZA * self.piezas + (C.PREMIO_META * self.nivel.meta if self.superado else 0)

    def resumen(self):
        return {"aptitud": self.aptitud(), "lineas": self.lineas, "piezas": self.piezas, "superado": self.superado,
                "motivo": self.motivo, "tetris": self.tetris, "puntos": self.puntos}

    def libre(self, rot, bx, by):
        for r, c in ROTACIONES[self.actual][rot]:
            f, k = by + r, bx + c
            if f < 0 or f >= self.alto or k < 0 or k >= self.ancho or self.tablero[f, k]:
                return False
        return True

    def salida(self):
        return 0, COL_SALIDA, -MIN_FILA[self.actual][0]

    def girar(self, rot, bx, by, sentido):
        nueva = (rot + sentido) % 4
        for dy, dx in PATADAS:
            if self.libre(nueva, bx + dx, by + dy):
                return nueva, bx + dx, by + dy
        return None

    def caida(self, rot, bx, by):
        while self.libre(rot, bx, by + 1):
            by += 1
        return by

    def indice_de(self, filas, cols):
        c = self.candidatos()
        if c is None:
            return None
        clave = sorted(zip(filas, cols))
        for i in range(len(c["rot"])):
            if sorted(zip(c["filas"][i].tolist(), c["cols"][i].tolist())) == clave:
                return i
        return None
