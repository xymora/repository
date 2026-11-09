import numpy as np

import config as C
from sensores import N_ENTRADAS, observar

NOMBRES_SALIDAS = ("AVANZAR", "SALTAR", "DISPARAR", "ARRIBA", "ABAJO")
CAPAS = (N_ENTRADAS, *C.CAPAS_OCULTAS, len(NOMBRES_SALIDAS))
FORMAS = list(zip(CAPAS[:-1], CAPAS[1:]))
N_PARAM = sum(a * b + b for a, b in FORMAS)


def pesos_iniciales(rng):
    partes = []
    for a, b in FORMAS:
        partes.append(rng.normal(0.0, 1.0 / np.sqrt(a), a * b))
        partes.append(np.zeros(b))
    return np.concatenate(partes)


def desempacar(theta):
    capas, i = [], 0
    for a, b in FORMAS:
        w = theta[i:i + a * b].reshape(a, b)
        i += a * b
        capas.append((w, theta[i:i + b]))
        i += b
    return capas


def activar(capas, x, con_ocultas=False):
    ocultas = []
    for w, b in capas:
        x = np.tanh(x @ w + b)
        ocultas.append(x)
    return (x, ocultas[:-1]) if con_ocultas else x


def migrar(theta, jugadores):
    theta = np.asarray(theta, dtype=np.float64)
    resto = N_PARAM - CAPAS[0] * CAPAS[1]
    viejo = len(theta) // jugadores
    entradas = (viejo - resto) / CAPAS[1]
    if len(theta) % jugadores or entradas != int(entradas) or not 0 < entradas < CAPAS[0]:
        return None
    entradas = int(entradas)
    partes = []
    for k in range(jugadores):
        w = theta[k * viejo:(k + 1) * viejo]
        primera = np.zeros((CAPAS[0], CAPAS[1]))
        primera[:entradas] = w[:entradas * CAPAS[1]].reshape(entradas, CAPAS[1])
        partes += [primera.ravel(), w[entradas * CAPAS[1]:]]
    return np.concatenate(partes)


def imitar(theta, X, Y, epocas, rng, lote=256, tasa=0.003, max_lotes=None):
    theta = np.array(theta, dtype=np.float64)
    m, v, paso = np.zeros_like(theta), np.zeros_like(theta), 0
    for _ in range(epocas):
        orden = rng.permutation(len(X))
        for i in range(0, len(X), lote):
            if max_lotes is not None and paso >= max_lotes:
                return theta
            idx = orden[i:i + lote]
            capas = desempacar(theta)
            salidas = [X[idx]]
            for w, b in capas:
                salidas.append(np.tanh(salidas[-1] @ w + b))
            delta = (salidas[-1] - Y[idx]) * (1 - salidas[-1] ** 2) / len(idx)
            partes = []
            for k in range(len(capas) - 1, -1, -1):
                partes = [(salidas[k].T @ delta).ravel(), delta.sum(0)] + partes
                if k:
                    delta = (delta @ capas[k][0].T) * (1 - salidas[k] ** 2)
            g = np.concatenate(partes)
            paso += 1
            m = 0.9 * m + 0.1 * g
            v = 0.999 * v + 0.001 * g ** 2
            theta -= tasa * (m / (1 - 0.9 ** paso)) / (np.sqrt(v / (1 - 0.999 ** paso)) + 1e-8)
    return theta


def objetivo_imitacion(accion, mirando):
    mov, salto, disparo, arriba, abajo = accion
    return [0.8 * mov * mirando] + [0.8 if b else -0.8 for b in (salto, disparo, arriba, abajo)]


def acciones(salida, mirando):
    avance = salida[0]
    mov = mirando if avance > 0.33 else (-mirando if avance < -0.33 else 0)
    return mov, salida[1] > 0, salida[2] > 0, salida[3] > 0, salida[4] > 0


class ControladorRed:
    def __init__(self, pesos):
        self.capas = desempacar(np.asarray(pesos, dtype=np.float64))
        self.entradas = np.zeros(N_ENTRADAS)
        self.salida = np.zeros(len(NOMBRES_SALIDAS))

    def decidir(self, partida, jugador):
        self.entradas = observar(partida, jugador)
        self.salida = activar(self.capas, self.entradas)
        return acciones(self.salida, jugador.mirando)


class ControladorTeclado:
    cada = 1

    def __init__(self, teclas):
        self.teclas = teclas
        self.demo = []

    def decidir(self, partida, jugador):
        t = self.teclas
        mov = (1 if "derecha" in t else 0) - (1 if "izquierda" in t else 0)
        accion = mov, "saltar" in t, "disparar" in t, "arriba" in t, "abajo" in t
        if partida.t % C.DECIDIR_CADA == 0:
            self.demo.append((partida.t, jugador.muertes, observar(partida, jugador),
                              objetivo_imitacion(accion, jugador.mirando)))
        return accion

    def muestras(self, termino_sin_vidas=False, margen=45):
        muertes = [a[0] for a, b in zip(self.demo, self.demo[1:]) if b[1] > a[1]]
        if termino_sin_vidas and self.demo:
            muertes.append(self.demo[-1][0])
        buenas = [d for d in self.demo if not any(0 <= m - d[0] < margen for m in muertes)]
        self.demo = []
        if not buenas:
            return None
        return np.array([d[2] for d in buenas]), np.array([d[3] for d in buenas])
