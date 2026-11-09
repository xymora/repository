import bisect

import numpy as np

import config as C

NOMBRES_ENTRADAS = ("valor del blanco", "probabilidad de ojiva", "objetos del racimo", "ojivas a bordo",
                    "fase de impulso", "fase media", "fase terminal", "tiempo al impacto", "ventana de tiro",
                    "Pk estimada", "capa impulso", "capa exo", "capa gran altitud", "capa terminal",
                    "capas posteriores", "calidad de traza", "disparos previos", "interceptores de la capa",
                    "amenazas activas", "amenazas a zonas", "urgencia", "planeador", "solución de tiro", "sesgo")
N_ENTRADAS = 24
NOMBRES_SALIDAS = ("ENFRENTAR", "SALVA DOBLE")
CAPAS = (N_ENTRADAS, *C.CAPAS_OCULTAS, len(NOMBRES_SALIDAS))
FORMAS = list(zip(CAPAS[:-1], CAPAS[1:]))
N_PARAM = sum(a * b + b for a, b in FORMAS)


def caracteristicas(ep, am, sol, ctx):
    val = ep.valor_amenaza(am)
    ti = am.t_impacto - ep.t
    fase = am.fase(ep.t)
    if sol is not None:
        ventana, pk, f = sol["ventana"], sol["pk"], 1.0
        capa = [1.0 if sol["capa"] == c else 0.0 for c in C.ORDEN_CAPAS]
        post = sol["posteriores"]
        stock = ctx["stock"].get(sol["capa"], 0.0)
    else:
        ventana, pk, f, capa, post, stock = -60.0, 0.0, 0.0, [0.0] * 4, 0, 0.0
    urg = bisect.bisect_left(ctx["tis"], ti) if val > 0 else len(ctx["tis"])
    return np.array([
        min(val / 4, 3.0), am.p_ojiva(), (am.racimo[1] if am.racimo else 1) / 8, am.ojivas() / 6,
        1.0 if fase == "impulso" else 0.0, 1.0 if fase == "media" else 0.0, 1.0 if fase == "terminal" else 0.0,
        min(ti / 1800, 1.5), max(-1.0, min(1.0, ventana / 120)), pk, *capa, post / 3, am.calidad(),
        min(am.disparos, 4) / 4, stock, min(ctx["activas"] / 30, 2.0), min(ctx["amenazantes"] / 15, 2.0),
        min(urg / 10, 2.0), 1.0 if am.planeador else 0.0, f, 1.0,
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
