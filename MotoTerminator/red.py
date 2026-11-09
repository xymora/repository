import numpy as np


def n_parametros(capas):
    return sum(a * b + b for a, b in zip(capas[:-1], capas[1:]))


def desempacar(pesos, capas):
    pesos = np.atleast_2d(pesos)
    n, i = pesos.shape[0], 0
    out = []
    for a, b in zip(capas[:-1], capas[1:]):
        W = pesos[:, i:i + a * b].reshape(n, a, b)
        i += a * b
        out.append((W, pesos[:, i:i + b]))
        i += b
    return out


def adelante(red, x):
    for W, b in red:
        x = np.tanh(np.einsum("ni,nio->no", x, W) + b)
    return x


def aleatorios(n, capas, rng):
    partes = []
    for a, b in zip(capas[:-1], capas[1:]):
        partes.append(rng.normal(0, 1 / np.sqrt(a), (n, a * b)))
        partes.append(rng.normal(0, 0.2, (n, b)))
    pesos = np.concatenate(partes, axis=1)
    pesos[:, -capas[-1]] += 0.6
    return pesos
