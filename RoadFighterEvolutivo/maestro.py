import numpy as np

import cerebro as B
import config as C
from pista import Pista
from simulacion import Carrera

S = len(C.SONDAS)
_OFF = np.array(C.SONDAS)
I_OBS = 6 + 2 * len(C.MIRADAS)
I_REL = I_OBS + S
I_ORI = I_OBS + 2 * S
I_ARC_X, I_ARC_D = I_ORI + S, I_ORI + S + 1
FRENADA = 7.5


def _vlat(v):
    return np.minimum(C.VLAT_MAX, C.VLAT_BASE + C.VLAT_POR_V * v) * np.minimum(v / 3.0, 1.0)


def experto(obs, sim=None):
    o = np.atleast_2d(obs)
    n = len(o)
    v = o[:, 0] * C.VMAX_HIGH
    alto = o[:, 1] > 0
    derrapa = o[:, 3] > 0.5
    vx = o[:, 4] * 10.0
    combustible = o[:, 2]
    cx = o[:, 6:6 + len(C.MIRADAS)] * 10.0
    al = C.ALCANCE
    d_obs = (1.0 - o[:, I_OBS:I_OBS + S]) * al
    hay_obs = o[:, I_OBS:I_OBS + S] > 1e-6
    v_obs = v[:, None] + o[:, I_REL:I_REL + S] * 40.0
    d_ori = (1.0 - o[:, I_ORI:I_ORI + S]) * al
    se_aleja = np.where(hay_obs, np.maximum(v_obs - v[:, None], 0.0) * 3.0, 0.0)
    orilla = np.where(d_ori < 40.0, d_ori, al)
    libre = np.minimum(orilla, np.where(hay_obs, d_obs + se_aleja, al))
    t_lat = np.abs(_OFF)[None, :] / np.maximum(_vlat(v), 1.0)[:, None]
    necesita = np.minimum(30.0, v[:, None] * t_lat + 9.0)
    ok = np.ones((n, S), dtype=bool)
    centro = S // 2
    for k in range(S):
        if k == centro:
            continue
        tramo = libre[:, k:centro] if k < centro else libre[:, centro + 1:k + 1]
        ok[:, k] = (tramo >= necesita[:, k:k + 1]).all(axis=1)
    puntaje = libre - 2.0 * np.abs(_OFF)[None, :]
    ancho_c = 2.0 * (o[:, 10] * 10.0 - C.BORDILLO) / 3.0
    hay_arc = o[:, I_ARC_D] > 0
    x_arc = o[:, I_ARC_X] * ancho_c
    cerca_arc = np.abs(_OFF[None, :] - x_arc[:, None]) < np.maximum(ancho_c / 2, 1.2)[:, None]
    bono = np.where(combustible < 0.35, 60.0, 30.0)
    puntaje = puntaje + np.where(hay_arc[:, None] & cerca_arc & (libre > 25), bono[:, None], 0.0)
    puntaje = np.where(ok, puntaje, -1e9)
    k = np.argmax(puntaje, axis=1)
    destino = _OFF[k]
    pendiente = (cx[:, 1] - cx[:, 0]) / (C.MIRADAS[1] - C.MIRADAS[0])
    vx_obj = pendiente * v + destino / 0.6
    volante = np.clip(vx_obj / np.maximum(_vlat(v), 1.0), -1.0, 1.0)
    def v_segura(kk):
        d = d_obs[np.arange(n), kk]
        vo = np.where(hay_obs[np.arange(n), kk], np.maximum(v_obs[np.arange(n), kk], 0.0), C.VMAX_HIGH)
        dd = np.maximum(d - 10.0, 0.0)
        return vo + np.sqrt(2 * FRENADA * dd)
    v_obj = np.minimum(v_segura(k), v_segura(np.full(n, centro)) + np.where(k != centro, 8.0, 0.0))
    for (a, b, dist) in ((0, 1, 0.0), (1, 2, 40.0), (2, 3, 80.0)):
        s = np.abs(cx[:, b] - cx[:, a]) / (C.MIRADAS[b] - C.MIRADAS[a])
        v_curva = 0.8 * C.VLAT_MAX / np.maximum(s, 1e-3)
        v_obj = np.minimum(v_obj, np.sqrt(v_curva ** 2 + 2 * FRENADA * dist))
    v_obj = np.minimum(v_obj, C.VMAX_HIGH)
    acel = np.clip(0.3 * (v_obj - v), -1.0, 1.0)
    marcha = np.where(alto, np.where(v < 30.0, -1.0, 1.0), np.where(v > 36.0, 1.0, -1.0))
    pegado = (d_obs[:, centro] < 2.5) & hay_obs[:, centro] & (v < 1.5)
    lado_libre = np.where(destino != 0, np.sign(destino),
                          np.sign(libre[:, centro + 1:].max(axis=1) - libre[:, :centro].max(axis=1)))
    lado_libre = np.where(lado_libre == 0, 1.0, lado_libre)
    acel = np.where(pegado, -1.0, acel)
    volante = np.where(pegado, lado_libre, volante)
    marcha = np.where(pegado, -1.0, marcha)
    volante = np.where(derrapa, -np.sign(vx), volante)
    acel = np.where(derrapa, np.minimum(acel, 0.3), acel)
    return np.stack([volante, acel, marcha], axis=1)


def recolectar(niveles=(1, 2, 3, 4, 2, 3, 4), autos=12, ruido=0.35, cada=2, semilla=0, avisar=None):
    rng = np.random.default_rng(semilla)
    X, Y = [], []
    for i, nv in enumerate(niveles):
        sigma = np.linspace(0.0, ruido, autos)[:, None]
        paso = {"k": 0}

        def ctrl(obs, sim):
            a = experto(obs)
            paso["k"] += 1
            if paso["k"] % cada == 0:
                vivos = sim.vivo
                X.append(obs[vivos].copy())
                Y.append(a[vivos].copy())
            return np.clip(a + rng.normal(0, 1, a.shape) * sigma[:len(a)], -1, 1)

        c = Carrera(Pista(int(nv), int(rng.integers(1 << 30))), None, controlador=ctrl, n=autos)
        while not c.terminado:
            c.paso()
        if avisar:
            avisar(f"El maestro manejó {C.NIVELES[int(nv) - 1][0]} ({i + 1}/{len(niveles)})")
    return np.concatenate(X), np.concatenate(Y)


def ensenar(avisar=None, semilla=0):
    X, Y = recolectar(semilla=semilla, avisar=avisar)
    if avisar:
        avisar(f"La red está aprendiendo de {len(X):,} situaciones del maestro...".replace(",", " "))
    return clonar(X, Y, semilla=semilla, avisar=avisar)


def clonar(X, Y, epocas=60, lr=3e-3, semilla=0, avisar=None):
    rng = np.random.default_rng(semilla)
    norm = B.Normalizador()
    norm.actualizar(X)
    Xn = norm.aplicar(X)
    theta = B.aleatorios(1, rng)[0]
    red = {k: v[0].copy() for k, v in B.desempacar(theta[None]).items()}
    red["Wh"][:] = 0.0
    nombres = ("Wx", "b1", "W2", "b2", "W3", "b3")
    m = {k: np.zeros_like(red[k]) for k in nombres}
    vv = {k: np.zeros_like(red[k]) for k in nombres}
    t = 0
    lote = 512
    peso = np.array([1.0, 1.0, 0.5])
    for ep in range(epocas):
        orden = rng.permutation(len(Xn))
        perdida = 0.0
        for i in range(0, len(orden), lote):
            idx = orden[i:i + lote]
            x, y = Xn[idx], Y[idx]
            h1 = np.tanh(x @ red["Wx"] + red["b1"])
            h2 = np.tanh(h1 @ red["W2"] + red["b2"])
            out = np.tanh(h2 @ red["W3"] + red["b3"])
            err = (out - y) * peso
            perdida += float((err ** 2).sum())
            g3 = 2 * err * (1 - out ** 2) / len(idx)
            g = {"W3": h2.T @ g3, "b3": g3.sum(0)}
            g2 = (g3 @ red["W3"].T) * (1 - h2 ** 2)
            g["W2"], g["b2"] = h1.T @ g2, g2.sum(0)
            g1 = (g2 @ red["W2"].T) * (1 - h1 ** 2)
            g["Wx"], g["b1"] = x.T @ g1, g1.sum(0)
            t += 1
            for k in nombres:
                m[k] = 0.9 * m[k] + 0.1 * g[k]
                vv[k] = 0.999 * vv[k] + 0.001 * g[k] ** 2
                red[k] -= lr * (m[k] / (1 - 0.9 ** t)) / (np.sqrt(vv[k] / (1 - 0.999 ** t)) + 1e-8)
        if avisar and (ep % 10 == 9 or ep == epocas - 1):
            avisar(f"imitación: época {ep + 1}/{epocas} · error {perdida / len(Xn):.4f}")
    plano = np.concatenate([red[k].reshape(-1) for k, _ in B.BLOQUES])
    return plano, norm
