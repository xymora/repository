import bisect
import math

import numpy as np

import config as C

NOMBRES_ENTRADAS = ("valor del blanco", "distancia a zona", "amenaza a la batería", "tiempo al impacto",
                    "ventana de tiro", "Pk estimada", "calidad de traza", "disparos previos", "cohete corto",
                    "cohete medio", "mortero", "dron", "incertidumbre", "interceptores", "amenazas activas",
                    "amenazas a zonas", "urgencia", "solución de tiro", "z1", "sesgo")
N_ENTRADAS = 20
NOMBRES_SALIDAS = ("ENFRENTAR", "SALVA DOBLE")
CAPAS = (N_ENTRADAS, *C.CAPAS_OCULTAS, len(NOMBRES_SALIDAS))
FORMAS = list(zip(CAPAS[:-1], CAPAS[1:]))
N_PARAM = sum(a * b + b for a, b in FORMAS)


def caracteristicas(ep, am, sol, ctx):
    bx, by = am.impacto_est()
    s = am.sigma()
    val = ep.valor_en(bx, by, s * 0.8)
    dz = ep.distancia_zonas(bx, by)
    dbat = ep.distancia_bateria(bx, by)
    ti = am.t_impacto - ep.t
    if sol is not None:
        _, p, ventana, pk = sol
        f = 1.0
        zint = p[2]
    else:
        ventana, pk, f, zint = -30.0, 0.0, 0.0, 0.0
    tipo = [1.0 if am.tipo == k else 0.0 for k in C.ORDEN_TIPOS]
    urg = bisect.bisect_left(ctx["tis"], ti) if val > 0 else len(ctx["tis"])
    return np.array([
        val / 4, max(-1.0, min(1.0, dz / 5000)), 1.0 if dbat < C.RADIO_BATERIA_PELIGRO + s else 0.0,
        min(ti / 60, 2.0), max(-1.0, min(1.0, ventana / 30)), pk, am.calidad(), min(am.disparos, 4) / 4,
        *tipo, min(s / 2000, 1.5), ctx["stock"], min(ctx["activas"] / 20, 2.0), min(ctx["amenazantes"] / 10, 2.0),
        min(urg / 10, 2.0), f, min(zint / 5000, 2.0), 1.0,
    ])


def objetivo(n):
    return [0.8 if n > 0 else -0.8, 0.8 if n > 1 else -0.8]


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


def imitar(theta, X, Y, epocas, rng, lote=256, tasa=0.003, max_lotes=None, W=None):
    theta = np.array(theta, dtype=np.float64)
    m, v, paso = np.zeros_like(theta), np.zeros_like(theta), 0
    if W is None:
        positivos = Y[:, 0] > 0
        frac = max(positivos.mean(), 1e-3)
        W = np.where(positivos, 0.5 / frac, 0.5 / max(1 - frac, 1e-3))
        W = W / W.mean()
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
            delta = (salidas[-1] - Y[idx]) * (1 - salidas[-1] ** 2) * W[idx, None] / len(idx)
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


class ControladorRed:
    nombre = "Red neuronal"

    def __init__(self, pesos):
        self.capas = desempacar(np.asarray(pesos, dtype=np.float64))
        self.ultima = None

    def decidir(self, ep, cands, ctx):
        X = np.array([caracteristicas(ep, am, sol, ctx) for am, sol in cands])
        Y = activar(self.capas, X)
        self.ultima = (cands, X, Y)
        ordenes = []
        for (am, sol), y in zip(cands, Y):
            if sol is not None and y[0] > 0:
                ordenes.append((am, 2 if y[1] > 0 else 1))
        return ordenes
