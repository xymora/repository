import numpy as np

import config as C

N_IN, N_H1, N_H2, N_OUT = C.N_ENTRADAS, C.OCULTAS_REC, C.OCULTAS_2, C.SALIDAS
N_SD, N_C = C.SENSORES_DIR, C.OCULTAS_COMPARTIDA
BLOQUES = (("Wx", (N_IN, N_H1)), ("Wh", (N_H1, N_H1)), ("b1", (N_H1,)),
           ("W2", (N_H1, N_H2)), ("b2", (N_H2,)), ("W3", (N_H2, N_OUT)), ("b3", (N_OUT,)),
           ("U", (N_SD, N_C)), ("c", (N_C,)), ("v", (N_C,)))
N_PARAM = int(sum(np.prod(f) for _, f in BLOQUES))


def desempacar(theta):
    theta = np.atleast_2d(theta)
    n, i, out = theta.shape[0], 0, {}
    for nombre, forma in BLOQUES:
        k = int(np.prod(forma))
        out[nombre] = theta[:, i:i + k].reshape((n,) + forma)
        i += k
    return out


def aleatorios(n, rng):
    partes = []
    for nombre, forma in BLOQUES:
        if nombre.startswith("b") or nombre == "c":
            p = np.zeros((n,) + forma)
        elif nombre == "v":
            p = rng.normal(0, 1 / np.sqrt(forma[0]), (n,) + forma)
        elif nombre == "Wh":
            p = rng.normal(0, 0.3 / np.sqrt(forma[0]), (n,) + forma)
        else:
            p = rng.normal(0, 1 / np.sqrt(forma[0]), (n,) + forma)
        partes.append(p.reshape(n, -1))
    return np.concatenate(partes, axis=1)


def adelante(red, x, h):
    h = np.tanh(np.einsum("ni,nio->no", x, red["Wx"]) + np.einsum("ni,nio->no", h, red["Wh"])
                + red["b1"])
    h2 = np.tanh(np.einsum("ni,nio->no", h, red["W2"]) + red["b2"])
    xd = x[:, :4 * N_SD].reshape(len(x), 4, N_SD)
    s = np.einsum("ndc,nc->nd", np.tanh(np.einsum("nde,nec->ndc", xd, red["U"]) + red["c"][:, None, :]),
                  red["v"])
    y = np.tanh(np.einsum("ni,nio->no", h2, red["W3"]) + red["b3"] + s)
    return y, h, h2


class Normalizador:

    def __init__(self, n=N_IN):
        self.n_obs = 0.0
        self.media = np.zeros(n)
        self.m2 = np.ones(n)

    @property
    def desv(self):
        if self.n_obs < 2:
            return np.ones_like(self.media)
        return np.sqrt(np.maximum(self.m2 / self.n_obs, 1e-4))

    def aplicar(self, obs):
        return np.clip((obs - self.media) / self.desv, -5.0, 5.0)

    def actualizar(self, muestra):
        muestra = np.asarray(muestra, dtype=float)
        if muestra.ndim != 2 or len(muestra) == 0:
            return
        k = len(muestra)
        mu_b = muestra.mean(0)
        m2_b = ((muestra - mu_b) ** 2).sum(0)
        total = self.n_obs + k
        delta = mu_b - self.media
        self.media = self.media + delta * k / total
        self.m2 = self.m2 + m2_b + delta ** 2 * self.n_obs * k / total
        self.n_obs = total

    def estado(self):
        return np.concatenate([[self.n_obs], self.media, self.m2])

    @classmethod
    def desde(cls, arr):
        z = cls(len(arr) // 2)
        z.n_obs = float(arr[0])
        n = (len(arr) - 1) // 2
        z.media, z.m2 = np.array(arr[1:1 + n]), np.array(arr[1 + n:])
        return z


class NormalizadorPorIndividuo:

    def __init__(self, normalizadores):
        self.media = np.stack([z.media for z in normalizadores])
        self.desv_ = np.stack([z.desv for z in normalizadores])
        self.n_obs = 0.0

    def aplicar(self, obs):
        return np.clip((obs - self.media[:len(obs)]) / self.desv_[:len(obs)], -5.0, 5.0)

    def actualizar(self, muestra):
        pass
