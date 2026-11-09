import math

import numpy as np

from misiones import ARRANQUE, BLANCO, DESPEGUE, DETENER, PENDIENTE, PUNTO, TOQUE
from catalogo import TIPO_SENSOR
from terreno import superficie

N_ENTRADAS = 39
GRUPOS = (("rotación", 0, 3), ("gravedad", 3, 6), ("aire", 6, 9), ("altura", 9, 12), ("motor y tren", 12, 17),
          ("objetivo", 17, 24), ("tipo", 24, 29), ("pista", 29, 34), ("combate", 34, 36), ("terreno", 36, 39))


def datos_pista(ep):
    n = ep.n
    rel = np.zeros(n)
    s = np.zeros(n)
    l = np.zeros(n)
    hay = np.zeros(n, bool)
    rumbo, _, _ = ep.f.euler()
    for k, o in enumerate(ep.obj):
        sel = ep.i == k
        if not sel.any():
            continue
        a = o["pista"]
        cerca = o["tipo"] in (DESPEGUE, TOQUE, DETENER, ARRANQUE) or (o["tren"] is True and o["tipo"] == PUNTO)
        if not cerca:
            continue
        si, li = a.local(ep.f.pos[sel, 0], ep.f.pos[sel, 2])
        s[sel], l[sel] = si, li
        rel[sel] = (math.radians(a.rumbo) - rumbo[sel] + np.pi) % (2 * np.pi) - np.pi
        hay[sel] = True
    return hay, rel, s, l


def elevacion_pista(ep):
    e = np.zeros(ep.n)
    for k, o in enumerate(ep.obj):
        e[ep.i == k] = o["pista"].elev
    return e


def observar(ep):
    f = ep.f
    n = ep.n
    x = np.zeros((n, N_ENTRADAS))
    R = f.R
    x[:, 0:3] = np.tanh(f.w * np.array([0.6, 2.0, 2.0]))
    x[:, 3:6] = -R[:, 1, :]
    V = f.v_aire
    x[:, 6] = V / 200 - 1
    x[:, 7] = np.tanh(f.alfa * 3)
    x[:, 8] = np.tanh(f.beta * 4)
    agl = f.agl()
    x[:, 9] = np.tanh(agl / 300)
    x[:, 10] = np.tanh(agl / 30)
    x[:, 11] = np.tanh(f.vel[:, 1] / 30)
    x[:, 12] = f.entrada["gases"]
    x[:, 13] = f.motor + f.pq
    x[:, 14] = f.tren
    x[:, 15] = f.en_suelo
    x[:, 16] = f.mach
    p = ep.punto_obj()
    rel = p - f.pos
    d = np.linalg.norm(rel, axis=1) + 1e-6
    rb = np.einsum("nji,nj->ni", R, rel)
    x[:, 17:20] = rb / d[:, None]
    x[:, 20] = np.tanh(d / 4000)
    x[:, 21] = np.tanh(d / 400)
    x[:, 22] = np.tanh(rel[:, 1] / 400)
    vel_obj = np.array([o["vel"] if o["vel"] is not None else 200.0 for o in ep.obj])[np.minimum(ep.i, ep.k - 1)]
    x[:, 23] = np.tanh((vel_obj - V) / 40)
    tipos = ep._tipos()
    x[np.arange(n), 24 + TIPO_SENSOR[tipos]] = 1
    hay, rel_r, s, l = datos_pista(ep)
    x[:, 29] = np.sin(rel_r) * hay
    x[:, 30] = np.cos(rel_r) * hay
    x[:, 31] = np.tanh(l / 40) * hay
    x[:, 32] = np.tanh(s / 2000) * hay
    sobre = f.pos[:, 1] - elevacion_pista(ep)
    senda = 15 + np.maximum(-s, 0) * PENDIENTE
    x[:, 33] = np.tanh((sobre - senda) / 40) * hay
    if ep.drones.m:
        x[:, 34] = getattr(ep, "fijado_radar", np.zeros(n)) * 0.5 + getattr(ep, "fijado_ir", np.zeros(n)) * 0.5
        vr = ep.drones.vel[np.arange(n), ep.blanco_idx] - f.vel
        x[:, 35] = np.tanh(-np.einsum("ni,ni->n", vr, rel / d[:, None]) / 200) * (tipos == BLANCO)
    vh = f.vel.copy()
    vh[:, 1] = 0
    vn = np.linalg.norm(vh, axis=1, keepdims=True) + 1e-3
    adelante = vh / vn * np.clip(vn, 60, 300)
    h1 = superficie(f.pos[:, 0] + adelante[:, 0] * 6, f.pos[:, 2] + adelante[:, 2] * 6)
    h2 = superficie(f.pos[:, 0] + adelante[:, 0] * 14, f.pos[:, 2] + adelante[:, 2] * 14)
    x[:, 36] = np.tanh((f.pos[:, 1] - np.maximum(h1, h2)) / 400)
    tren_obj = np.array([0 if o["tren"] is None else (1 if o["tren"] else -1) for o in ep.obj])
    x[:, 37] = tren_obj[np.minimum(ep.i, ep.k - 1)]
    x[:, 38] = 1.0
    return x
