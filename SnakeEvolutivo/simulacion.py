import numpy as np

import cerebro as B
import config as C
from niveles import ESTE

PASOS4 = np.array([(-1, 0), (0, 1), (1, 0), (0, -1)])
PASOS8 = np.array([(-1, 0), (-1, 1), (0, 1), (1, 1), (1, 0), (1, -1), (0, -1), (-1, -1)])
VIVA, CHOCO_MURO, CHOCO_CUERPO, HAMBRE, TIEMPO = range(5)
MOTIVOS = {
    VIVA: "jugando",
    CHOCO_MURO: "chocó con un muro",
    CHOCO_CUERPO: "se mordió",
    HAMBRE: "murió de hambre",
    TIEMPO: "tiempo agotado",
}
VACIO = -10 ** 9


class Partida:
    def __init__(self, nivel, pesos, semilla):
        self.nivel = nivel
        self.capas = B.desempacar(pesos)
        self.n = n = self.capas[0][0].shape[0]
        self.muros = nivel.muros
        self.hambre_max = nivel.hambre_max
        self.marca = np.full((n, nivel.alto, nivel.ancho), VACIO, dtype=np.int64)
        fila, col = nivel.inicio
        largo = C.LONGITUD_INICIAL
        for k in range(largo):
            self.marca[:, fila, col - largo + 1 + k] = k - largo + 1
        self.cabeza = np.tile(np.array([fila, col]), (n, 1))
        self.dir = np.full(n, ESTE)
        self.largo = np.full(n, largo)
        self.t = 0
        self.t_fin = np.zeros(n, dtype=np.int64)
        self.vivo = np.ones(n, dtype=bool)
        self.motivo = np.full(n, VIVA)
        self.frutas = np.zeros(n, dtype=int)
        self.hambre = np.zeros(n, dtype=int)
        self.pasos = np.zeros(n, dtype=int)
        self.acercamiento = np.zeros(n)
        self.entradas = np.zeros((n, B.N_ENTRADAS))
        self.salidas = np.zeros((n, B.N_SALIDAS))
        rng = np.random.default_rng(semilla)
        libres = np.argwhere(~self.muros)
        self.candidatas = libres[rng.integers(0, len(libres), 4096)]
        self.puntero = np.zeros(n, dtype=int)
        self.fruta = np.zeros((n, 2), dtype=int)
        self._poner_frutas(np.arange(n))
        self.terminada = False

    def _ocupada(self, idx, filas, cols, t=None):
        t = self.t if t is None else t
        return self.muros[filas, cols] | (self.marca[idx, filas, cols] > t - self.largo[idx])

    def _poner_frutas(self, idx):
        pendientes = np.asarray(idx)
        total = len(self.candidatas)
        for _ in range(total):
            if pendientes.size == 0:
                return
            cand = self.candidatas[self.puntero[pendientes] % total]
            self.puntero[pendientes] += 1
            libre = ~self._ocupada(pendientes, cand[:, 0], cand[:, 1])
            self.fruta[pendientes[libre]] = cand[libre]
            pendientes = pendientes[~libre]
        self.fruta[pendientes] = 0

    def sensores(self, idx):
        alto, ancho = self.muros.shape
        cabeza = self.cabeza[idx]
        giro = (2 * self.dir[idx][:, None] + np.arange(8)) % 8
        d = PASOS8[giro]
        m = len(idx)
        distancia = np.ones((m, 8))
        es_muro = np.zeros((m, 8), dtype=bool)
        golpe = np.zeros((m, 8), dtype=bool)
        fruta = np.zeros((m, 8), dtype=bool)
        filas = idx[:, None]
        umbral = (self.t - self.largo[idx])[:, None]
        fy, fx = self.fruta[idx, 0][:, None], self.fruta[idx, 1][:, None]
        for s in range(1, max(alto, ancho)):
            y = np.clip(cabeza[:, None, 0] + s * d[..., 0], 0, alto - 1)
            x = np.clip(cabeza[:, None, 1] + s * d[..., 1], 0, ancho - 1)
            activo = ~golpe
            fruta |= activo & (y == fy) & (x == fx)
            muro = self.muros[y, x]
            choque = activo & (muro | (self.marca[filas, y, x] > umbral))
            distancia[choque] = s
            es_muro[choque] = muro[choque]
            golpe |= choque
            if golpe.all():
                break
        inversa = 1.0 / distancia
        frente = PASOS4[self.dir[idx]]
        derecha = np.stack([frente[:, 1], -frente[:, 0]], axis=1)
        delta = self.fruta[idx] - cabeza
        escala = max(alto, ancho)
        return np.column_stack([
            np.where(es_muro, inversa, 0.0),
            np.where(golpe & ~es_muro, inversa, 0.0),
            fruta.astype(float),
            (delta * frente).sum(1) / escala,
            (delta * derecha).sum(1) / escala,
            self.largo[idx] / self.nivel.libres,
            self.hambre[idx] / self.hambre_max,
        ])

    def paso(self):
        if self.terminada:
            return
        idx = np.nonzero(self.vivo)[0]
        entradas = self.sensores(idx)
        salidas = B.activar(B.subconjunto(self.capas, idx), entradas)
        self.entradas[idx] = entradas
        self.salidas[idx] = salidas
        self.dir[idx] = (self.dir[idx] + salidas.argmax(1) - 1) % 4
        antes = np.abs(self.fruta[idx] - self.cabeza[idx]).sum(1)
        nueva = self.cabeza[idx] + PASOS4[self.dir[idx]]
        y, x = nueva[:, 0], nueva[:, 1]
        self.t += 1
        choca_muro = self.muros[y, x]
        choca_cuerpo = ~choca_muro & (self.marca[idx, y, x] > self.t - self.largo[idx])
        self._morir(idx[choca_muro], CHOCO_MURO)
        self._morir(idx[choca_cuerpo], CHOCO_CUERPO)

        sigue = ~(choca_muro | choca_cuerpo)
        vivas, nueva, antes = idx[sigue], nueva[sigue], antes[sigue]
        self.cabeza[vivas] = nueva
        self.marca[vivas, nueva[:, 0], nueva[:, 1]] = self.t
        self.pasos[vivas] += 1

        come = (nueva == self.fruta[vivas]).all(1)
        comen = vivas[come]
        self.largo[comen] += 1
        self.frutas[comen] += 1
        self.hambre[comen] = 0
        self._poner_frutas(comen)

        resto = vivas[~come]
        self.hambre[resto] += 1
        despues = np.abs(self.fruta[resto] - self.cabeza[resto]).sum(1)
        self.acercamiento[resto] += np.where(despues < antes[~come], C.PREMIO_ACERCARSE,
                                             -C.CASTIGO_ALEJARSE)
        self._morir(resto[self.hambre[resto] > self.hambre_max], HAMBRE)

        if not self.vivo.any() or self.t >= C.PASOS_MAX:
            self._morir(np.nonzero(self.vivo)[0], TIEMPO)
            self.terminada = True

    def _morir(self, idx, motivo):
        self.vivo[idx] = False
        self.motivo[idx] = motivo
        self.t_fin[idx] = self.t - (motivo in (CHOCO_MURO, CHOCO_CUERPO))

    def aptitud(self):
        choque = np.isin(self.motivo, (CHOCO_MURO, CHOCO_CUERPO))
        return (self.frutas * C.PREMIO_FRUTA + self.acercamiento + self.pasos * C.PREMIO_PASO
                - choque * C.CASTIGO_CHOQUE)

    def cuerpo(self, p):
        t = self.t if self.vivo[p] else self.t_fin[p]
        marca = self.marca[p]
        filas, cols = np.nonzero((marca > t - self.largo[p]) & (marca <= t))
        orden = np.argsort(-marca[filas, cols])
        return np.column_stack([filas[orden], cols[orden]])

    def lider(self, actual=None):
        vivas = np.nonzero(self.vivo)[0]
        grupo = vivas if vivas.size else np.arange(self.n)
        mejor = grupo[np.argmax(self.frutas[grupo] * 100000 + self.pasos[grupo])]
        if actual is not None and (vivas.size == 0 or self.vivo[actual]) \
                and self.frutas[actual] >= self.frutas[mejor]:
            return actual
        return int(mejor)
