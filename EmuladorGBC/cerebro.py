import numpy as np

PIXELES = 18 * 20
RADIO = 4
LADO = 2 * RADIO + 1
BRUJULA = 4
RASGOS = LADO * LADO * 2 + 2 + BRUJULA
FUERZA_BRUJULA = 2.0


def entradas(n_acciones, rasgos=RASGOS):
    return PIXELES * 2 + n_acciones + 1 + rasgos


def tamano(n_acciones, ocultas):
    e = entradas(n_acciones)
    return e * ocultas + ocultas + ocultas * n_acciones + n_acciones + BRUJULA * n_acciones


def brujula_inicial(n_acciones, direcciones=None):
    w3 = np.zeros((BRUJULA, n_acciones), np.float32)
    for a, (h, v) in enumerate(direcciones or []):
        w3[0, a] = w3[2, a] = h * FUERZA_BRUJULA
        w3[1, a] = w3[3, a] = v * FUERZA_BRUJULA
    return w3


def inicial(n_acciones, ocultas, rng, direcciones=None):
    e = entradas(n_acciones)
    w1 = rng.standard_normal((e, ocultas)) / np.sqrt(e)
    w2 = rng.standard_normal((ocultas, n_acciones)) * 0.1 / np.sqrt(ocultas)
    return np.concatenate([w1.ravel(), np.zeros(ocultas), w2.ravel(), np.zeros(n_acciones),
                           brujula_inicial(n_acciones, direcciones).ravel()]).astype(np.float32)


def desempacar(theta, n_acciones, ocultas):
    e = entradas(n_acciones)
    i = 0
    w1 = theta[i:i + e * ocultas].reshape(e, ocultas)
    i += e * ocultas
    b1 = theta[i:i + ocultas]
    i += ocultas
    w2 = theta[i:i + ocultas * n_acciones].reshape(ocultas, n_acciones)
    i += ocultas * n_acciones
    b2 = theta[i:i + n_acciones]
    i += n_acciones
    return w1, b1, w2, b2, theta[i:i + BRUJULA * n_acciones].reshape(BRUJULA, n_acciones)


def migrar(theta, n_acciones, ocultas, direcciones=None):
    if len(theta) == tamano(n_acciones, ocultas):
        return theta
    fijo = ocultas + ocultas * n_acciones + n_acciones
    resto = len(theta) - fijo
    if resto > 0 and resto % ocultas == 0:
        con_w3 = False
        viejo = resto // ocultas
    elif resto - BRUJULA * n_acciones > 0 and (resto - BRUJULA * n_acciones) % ocultas == 0:
        con_w3 = True
        viejo = (resto - BRUJULA * n_acciones) // ocultas
    else:
        return None
    nuevo = entradas(n_acciones)
    if viejo < entradas(n_acciones, 0) or viejo > nuevo:
        return None
    w1 = theta[:viejo * ocultas].reshape(viejo, ocultas)
    w1 = np.vstack([w1, np.zeros((nuevo - viejo, ocultas), np.float32)])
    medio = theta[viejo * ocultas:viejo * ocultas + fijo]
    w3 = theta[viejo * ocultas + fijo:] if con_w3 else brujula_inicial(n_acciones, direcciones).ravel()
    return np.concatenate([w1.ravel(), medio, w3]).astype(np.float32)


def vector(obs, previo, ultima, n_acciones, quieto=0.0, rasgos=None):
    x = np.empty(entradas(n_acciones), dtype=np.float32)
    o = obs.ravel()
    x[:PIXELES] = o - 0.5
    x[PIXELES:2 * PIXELES] = (o - previo.ravel()) * 4.0
    x[2 * PIXELES:2 * PIXELES + n_acciones] = 0.0
    if ultima >= 0:
        x[2 * PIXELES + ultima] = 1.0
    i = 2 * PIXELES + n_acciones
    x[i] = quieto
    if rasgos is None:
        x[i + 1:] = 0.0
    else:
        x[i + 1:] = rasgos
    return x


class Politica:
    def __init__(self, theta, n_acciones, ocultas):
        self.n, self.h = n_acciones, ocultas
        self.w1, self.b1, self.w2, self.b2, self.w3 = desempacar(theta, n_acciones, ocultas)

    def logits(self, x):
        return np.tanh(x @ self.w1 + self.b1) @ self.w2 + self.b2 + x[-BRUJULA:] @ self.w3

    def probabilidades(self, x):
        z = self.logits(x)
        z = np.exp(z - z.max())
        return z / z.sum()


def paso_imitacion(theta, X, Y, n_acciones, ocultas, tasa, adam=None):
    w1, b1, w2, b2, w3 = desempacar(theta, n_acciones, ocultas)
    h = np.tanh(X @ w1 + b1)
    B = X[:, -BRUJULA:]
    z = h @ w2 + b2 + B @ w3
    z = z - z.max(1, keepdims=True)
    p = np.exp(z)
    p /= p.sum(1, keepdims=True)
    perdida = -np.log(p[np.arange(len(Y)), Y] + 1e-9).mean()
    acierto = float((p.argmax(1) == Y).mean())
    dz = p.copy()
    dz[np.arange(len(Y)), Y] -= 1
    dz /= len(Y)
    gw2 = h.T @ dz
    gb2 = dz.sum(0)
    gw3 = B.T @ dz
    dh = (dz @ w2.T) * (1 - h * h)
    gw1 = X.T @ dh
    gb1 = dh.sum(0)
    g = np.concatenate([gw1.ravel(), gb1, gw2.ravel(), gb2, gw3.ravel()]).astype(np.float32)
    if adam is None:
        theta -= tasa * g
    else:
        theta -= adam.paso(g, tasa)
    return float(perdida), acierto


class Adam:
    def __init__(self, n, b1=0.9, b2=0.999):
        self.m = np.zeros(n, dtype=np.float32)
        self.v = np.zeros(n, dtype=np.float32)
        self.t = 0
        self.b1, self.b2 = b1, b2

    def paso(self, g, tasa):
        self.t += 1
        self.m = self.b1 * self.m + (1 - self.b1) * g
        self.v = self.b2 * self.v + (1 - self.b2) * g * g
        mh = self.m / (1 - self.b1 ** self.t)
        vh = self.v / (1 - self.b2 ** self.t)
        return (tasa * mh / (np.sqrt(vh) + 1e-8)).astype(np.float32)
