import numpy as np

import config as C
from sensores import N_ENTRADAS, observar

NOMBRES_SALIDAS = ("PROFUNDIDAD", "ALABEO", "TIMÓN", "GASES", "FRENOS", "TREN", "FUEGO")
N_SALIDAS = len(NOMBRES_SALIDAS)
CAPAS = (N_ENTRADAS, *C.CAPAS_OCULTAS, N_SALIDAS)
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


def desempacar_lote(thetas):
    capas, i = [], 0
    p = thetas.shape[0]
    for a, b in FORMAS:
        w = thetas[:, i:i + a * b].reshape(p, a, b)
        i += a * b
        capas.append((w, thetas[:, i:i + b]))
        i += b
    return capas


def activar_lote(capas, x):
    ocultas = []
    for w, b in capas:
        x = np.tanh(np.einsum("pi,pij->pj", x, w) + b)
        ocultas.append(x)
    return x, ocultas


def acciones(salida):
    return {"elev": salida[:, 0], "alabeo": salida[:, 1], "timon": salida[:, 2],
            "gases": (salida[:, 3] + 1) / 2, "freno": np.clip(salida[:, 4], 0, 1),
            "aerofreno": (salida[:, 4] > 0.3).astype(float), "tren": salida[:, 5] > 0, "fuego": salida[:, 6] > 0}


def objetivo_imitacion(acc):
    def b(v):
        return np.where(np.asarray(v, dtype=bool), 0.8, -0.8)
    fr = np.maximum(np.asarray(acc["freno"], dtype=float), np.asarray(acc.get("aerofreno", 0), dtype=float) * 0.6)
    return np.stack([np.clip(acc["elev"], -0.95, 0.95), np.clip(acc["alabeo"], -0.95, 0.95),
                     np.clip(acc["timon"], -0.95, 0.95), np.clip(np.asarray(acc["gases"]) * 2 - 1, -0.95, 0.95),
                     np.where(fr > 0.05, np.clip(fr, 0.4, 0.95), -0.6), b(acc["tren"]), b(acc["fuego"])], 1)


def imitar(theta, X, Y, epocas, rng, lote=256, tasa=0.003, max_lotes=None):
    theta = np.array(theta, dtype=np.float64)
    m, v, paso = np.zeros_like(theta), np.zeros_like(theta), 0
    peso = np.array([1.5, 1.5, 0.6, 1.0, 0.8, 0.8, 0.6])
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
            delta = (salidas[-1] - Y[idx]) * peso * (1 - salidas[-1] ** 2) / len(idx)
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


class Pilotos:
    def __init__(self, thetas):
        thetas = np.atleast_2d(np.asarray(thetas, dtype=np.float64))
        self.capas = desempacar_lote(thetas)
        self.p = thetas.shape[0]
        self.entradas = np.zeros((self.p, N_ENTRADAS))
        self.salida = np.zeros((self.p, N_SALIDAS))
        self.ocultas = []

    def decidir(self, ep):
        self.entradas = observar(ep)
        self.salida, self.ocultas = activar_lote(self.capas, self.entradas)
        acc = acciones(self.salida)
        acc["bengala"] = ep.enemigos.alerta & (ep.t % 1.0 < C.PASO * 1.5)
        return acc


def perdida(theta, X, Y, rng=None, muestra=1024):
    if not len(X):
        return None
    if rng is not None and len(X) > muestra:
        idx = rng.choice(len(X), muestra, replace=False)
        X, Y = X[idx], Y[idx]
    salida = X
    for w, b in desempacar(theta):
        salida = np.tanh(salida @ w + b)
    peso = np.array([1.5, 1.5, 0.6, 1.0, 0.8, 0.8, 0.6])
    return float(np.mean((salida - Y) ** 2 * peso))
