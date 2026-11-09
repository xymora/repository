import math

import numpy as np

import config as C
from etapas import AGUA, BARRERA, PINCHO, PLATAFORMA, PUENTE, SOLIDO

T = C.TILE
VALOR_TILE = {SOLIDO: 1.0, BARRERA: 1.0, PLATAFORMA: 0.5, PUENTE: 0.5, AGUA: -0.5, PINCHO: -1.0}
FILAS_TERRENO = range(-3, 4)
COLUMNAS_TERRENO = range(-2, 6)
N_ENEMIGOS = 6
N_BALAS = 6
N_TIRADORES = 3
N_TRAYECTORIAS = 3
HORIZONTE = 45
RADIO_PELIGRO = 28
DISPARO = {"soldado": (50, 25), "francotirador": (45, 20), "torreta": (45, 30), "canon": (45, 30),
           "granadero": (55, 30), "nucleo": (80, 40)}
GRUPOS = (
    ("propio", 15),
    ("terreno", len(FILAS_TERRENO) * len(COLUMNAS_TERRENO)),
    ("enemigos", N_ENEMIGOS * 5),
    ("balas", N_BALAS * 4),
    ("objeto", 3),
    ("jefe", 4),
    ("etapa", 2),
    ("compañero", 4),
    ("linea de fuego", N_TIRADORES * 4),
    ("trayectorias", N_TRAYECTORIAS * 4),
)
N_ENTRADAS = sum(n for _, n in GRUPOS)


def _cercanos(objetos, x, y, n):
    return sorted(objetos, key=lambda o: (o.cx - x) ** 2 + (o.cy - y) ** 2)[:n]


def _turno_disparo(p, e):
    k = p.t - e.t0
    if e.tipo == "parte":
        if e.datos["ataque"] in ("ninguno", "engendrar"):
            return None
        periodo = e.datos["periodo"]
        return (-(k + e.datos["desfase"])) % periodo, periodo
    if e.tipo not in DISPARO:
        return None
    periodo, fase = DISPARO[e.tipo]
    return (fase - k) % periodo, periodo


def _en_linea(e, j):
    dx, dy = j.cx - e.cx, j.cy - e.cy
    if e.tipo in ("torreta", "canon"):
        a = e.angulo * math.pi / 6
        ux, uy = math.cos(a), math.sin(a)
    elif e.tipo == "soldado":
        ux, uy = float(e.mirando), 0.0
    else:
        return 1.0
    if dx * ux + dy * uy <= 0:
        return 0.0
    return max(0.0, 1.0 - abs(dx * uy - dy * ux) / 32)


def linea_de_fuego(p, j):
    tiradores = []
    for e in p.enemigos:
        if not p.en_vista(e):
            continue
        turno = _turno_disparo(p, e)
        if turno is None:
            continue
        linea = _en_linea(e, j)
        inminencia = 1.0 - turno[0] / turno[1]
        tiradores.append((linea * (0.5 + 0.5 * inminencia), e, linea, inminencia))
    tiradores.sort(key=lambda a: -a[0])
    return tiradores[:N_TIRADORES]


def trayectorias(p, j):
    peligrosas = []
    for b in p.balas:
        if b.dueno is not None:
            continue
        rx, ry = b.x - j.cx, b.y - j.cy
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
    m = j.mirando
    v = [j.vx / 3, j.vy / 9, float(j.en_suelo), float(j.en_agua), float(m), float(j.agachado),
         float(j.invulnerable > 0 or j.barrera > 0)]
    v += [float(j.arma == a) for a in "NMSLF"]
    v += [float(j.rapido), j.vidas / C.VIDAS, float(j.cadencia > 0)]

    col0, fila0 = int(j.cx // T), int((j.y + j.h - 1) // T)
    for df in FILAS_TERRENO:
        for dc in COLUMNAS_TERRENO:
            v.append(VALOR_TILE.get(p.tile(fila0 + df, col0 + dc * m), 0.0))

    visibles = [e for e in p.enemigos if p.en_vista(e, 16)]
    cercanos = _cercanos(visibles, j.cx, j.cy, N_ENEMIGOS)
    for e in cercanos:
        v += [(e.cx - j.cx) * m / 128, (e.cy - j.cy) / 112, e.w / 48,
              float(e.vulnerable and e.hp > 0), float(e.contacto)]
    v += [0.0] * (5 * (N_ENEMIGOS - len(cercanos)))

    enemigas = [b for b in p.balas if b.dueno is None]
    cercanas = sorted(enemigas, key=lambda b: (b.x - j.cx) ** 2 + (b.y - j.cy) ** 2)[:N_BALAS]
    for b in cercanas:
        v += [(b.x - j.cx) * m / 128, (b.y - j.cy) / 112, b.vx * m / 6, b.vy / 6]
    v += [0.0] * (4 * (N_BALAS - len(cercanas)))

    items = _cercanos(p.items, j.cx, j.cy, 1)
    if items:
        it = items[0]
        v += [1.0, (it.cx - j.cx) * m / 128, (it.cy - j.cy) / 112]
    else:
        v += [0.0, 0.0, 0.0]

    vitales = [e for e in p.enemigos if e.tipo == "parte" and e.datos["vital"]]
    if vitales:
        e = _cercanos(vitales, j.cx, j.cy, 1)[0]
        vida = sum(o.hp for o in vitales) / max(sum(o.hp_max for o in vitales), 1)
        v += [1.0, (e.cx - j.cx) * m / 128, (e.cy - j.cy) / 112, vida]
    else:
        v += [0.0, 0.0, 0.0, 0.0]

    v += [float(p.vertical), p.t / C.TIEMPO_MAX]

    otros = [o for o in p.jugadores if o is not j]
    if otros:
        o = otros[0]
        v += [1.0, float(o.activo), (o.cx - j.cx) * m / 128, (o.cy - j.cy) / 112]
    else:
        v += [0.0, 0.0, 0.0, 0.0]

    tiradores = linea_de_fuego(p, j)
    for _, e, linea, inminencia in tiradores:
        v += [(e.cx - j.cx) * m / 128, (e.cy - j.cy) / 112, linea, inminencia]
    v += [0.0] * (4 * (N_TIRADORES - len(tiradores)))

    peligrosas = trayectorias(p, j)
    for tca, ox, oy, d in peligrosas:
        v += [1.0 - tca / HORIZONTE, ox * m / RADIO_PELIGRO, oy / RADIO_PELIGRO, d / RADIO_PELIGRO]
    v += [0.0] * (4 * (N_TRAYECTORIAS - len(peligrosas)))
    return np.array(v, dtype=np.float64)

