import numpy as np

import config as C

NOMBRES_RAYOS = ("fr", "fr-de", "de", "at-de", "at", "at-iz", "iz", "fr-iz")
NOMBRES_ENTRADAS = (
    [f"muro {n}" for n in NOMBRES_RAYOS]
    + [f"cuerpo {n}" for n in NOMBRES_RAYOS]
    + [f"fruta {n}" for n in NOMBRES_RAYOS]
    + ["fruta adelante", "fruta derecha", "largo", "hambre"]
)
NOMBRES_SALIDAS = ("IZQUIERDA", "RECTO", "DERECHA")
N_ENTRADAS = len(NOMBRES_ENTRADAS)
N_SALIDAS = len(NOMBRES_SALIDAS)
CAPAS = (N_ENTRADAS, *C.CAPAS_OCULTAS, N_SALIDAS)
FORMAS = [((a, b), (b,)) for a, b in zip(CAPAS[:-1], CAPAS[1:])]
N_PARAM = sum(a * b + b for (a, b), _ in FORMAS)


def pesos_iniciales(rng):
    partes = []
    for (a, b), _ in FORMAS:
        partes.append(rng.normal(0.0, 1.0 / np.sqrt(a), a * b))
        partes.append(np.zeros(b))
    return np.concatenate(partes)


def desempacar(theta):
    theta = np.atleast_2d(theta)
    capas, i = [], 0
    for (a, b), _ in FORMAS:
        w = theta[:, i:i + a * b].reshape(-1, a, b)
        i += a * b
        capas.append((w, theta[:, i:i + b]))
        i += b
    return capas


def activar(capas, entradas, con_ocultas=False):
    x = entradas
    ocultas = []
    for k, (w, b) in enumerate(capas):
        x = np.einsum("pi,pij->pj", x, w) + b
        if k < len(capas) - 1:
            x = np.tanh(x)
            ocultas.append(x)
    return (x, ocultas) if con_ocultas else x


def subconjunto(capas, indices):
    return [(w[indices], b[indices]) for w, b in capas]
