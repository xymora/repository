import math

import numpy as np

import config as C

W, H = C.ANCHO_VISTA, C.ALTO_VISTA
N_ENEMIGOS = 6
N_BALAS = 6
N_TRAYECTORIAS = 4
HORIZONTE = 40
RADIO_PELIGRO = 26
RADAR = 5
CELDA_RADAR = 22
GRUPOS = (
    ("propio", 12),
    ("enemigos", N_ENEMIGOS * 6),
    ("balas", N_BALAS * 4),
    ("trayectorias", N_TRAYECTORIAS * 4),
    ("radar", RADAR * RADAR),
    ("pow", 4),
    ("jefe", 4),
    ("misión", 2),
)
N_ENTRADAS = sum(n for _, n in GRUPOS)
TAMANO = {"caza": 0.2, "bombardero": 0.5, "pesado": 0.8, "torreta": 0.3, "jefe": 1.0}


def trayectorias(p, j):
    peligrosas = []
    for b in p.balas:
        if b.dueno is not None:
            continue
        rx, ry = b.x - j.x, b.y - j.y
        vx, vy = b.vx - j.vx, b.vy - j.vy
        vv = vx * vx + vy * vy
        tca = max(0.0, -(rx * vx + ry * vy) / vv) if vv > 1e-6 else 0.0
        ox, oy = rx + vx * tca, ry + vy * tca
        d = math.hypot(ox, oy)
        if tca < HORIZONTE and d < RADIO_PELIGRO:
            peligrosas.append((tca, ox, oy, d))
    peligrosas.sort()
    return peligrosas[:N_TRAYECTORIAS]


def observar(p, j):
    v = [j.x / W * 2 - 1, j.y / H * 2 - 1, j.vx / 3, j.vy / 3, (j.arma - 1) / 2, j.escoltas / 2,
         min(j.rizos, 5) / 5, float(j.rodando > 0), float(j.invulnerable > 0), float(j.cadencia == 0),
         j.vidas / C.VIDAS, min(j.x, W - j.x) / (W / 2) - min(j.y, H - j.y) / (H / 2)]

    enemigos = sorted((e for e in p.enemigos if e.vivo and p.en_pantalla(e, 20)),
                      key=lambda e: (e.x - j.x) ** 2 + (e.y - j.y) ** 2)[:N_ENEMIGOS]
    for e in enemigos:
        v += [1.0, (e.x - j.x) / 150, (e.y - j.y) / 160, e.vx / 4, e.vy / 4, TAMANO[e.tipo]]
    v += [0.0] * (6 * (N_ENEMIGOS - len(enemigos)))

    enemigas = sorted((b for b in p.balas if b.dueno is None),
                      key=lambda b: (b.x - j.x) ** 2 + (b.y - j.y) ** 2)[:N_BALAS]
    for b in enemigas:
        v += [(b.x - j.x) / 100, (b.y - j.y) / 100, b.vx / 4, b.vy / 4]
    v += [0.0] * (4 * (N_BALAS - len(enemigas)))

    peligrosas = trayectorias(p, j)
    for tca, ox, oy, d in peligrosas:
        v += [1.0 - tca / HORIZONTE, ox / RADIO_PELIGRO, oy / RADIO_PELIGRO, d / RADIO_PELIGRO]
    v += [0.0] * (4 * (N_TRAYECTORIAS - len(peligrosas)))

    radar = np.zeros((RADAR, RADAR))
    mitad = RADAR * CELDA_RADAR / 2
    for b in p.balas:
        if b.dueno is None:
            cx, cy = int((b.x - j.x + mitad) // CELDA_RADAR), int((b.y - j.y + mitad) // CELDA_RADAR)
            if 0 <= cx < RADAR and 0 <= cy < RADAR:
                radar[cy, cx] += 0.5
    for e in p.enemigos:
        if e.vivo and e.tipo != "torreta":
            for cy in range(RADAR):
                for cx in range(RADAR):
                    x0 = j.x - mitad + cx * CELDA_RADAR
                    y0 = j.y - mitad + cy * CELDA_RADAR
                    if e.x + e.hw > x0 and e.x - e.hw < x0 + CELDA_RADAR and e.y + e.hh > y0 and e.y - e.hh < y0 + CELDA_RADAR:
                        radar[cy, cx] += 1.0
    v += np.minimum(radar, 1.5).ravel().tolist()

    if p.items:
        it = min(p.items, key=lambda i: (i.x - j.x) ** 2 + (i.y - j.y) ** 2)
        v += [1.0, (it.x - j.x) / 150, (it.y - j.y) / 160, {"A": 1.0, "E": 0.0, "R": -1.0}[it.letra]]
    else:
        v += [0.0, 0.0, 0.0, 0.0]

    jefes = [e for e in p.enemigos if e.tipo == "jefe" and e.vivo]
    if jefes:
        e = jefes[0]
        v += [1.0, (e.x - j.x) / 150, (e.y - j.y) / 160, e.hp / e.hp_max]
    else:
        v += [0.0, 0.0, 0.0, 0.0]
    v += [p.progreso(), float(p.jefe_activo)]
    return np.array(v, dtype=np.float64)
