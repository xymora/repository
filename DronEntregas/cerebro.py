import math
import random

import config as C

N_ENTRADAS = 27
NEURONAS = C.NEURONAS_OCULTAS
N_SALIDAS = 3
TAM_GENOMA = (N_ENTRADAS * NEURONAS + NEURONAS + NEURONAS * N_SALIDAS + N_SALIDAS
              + N_ENTRADAS * N_SALIDAS)
DIRECCIONES = [k * math.pi / 4 for k in range(8)]
DISTANCIAS_RAYO = (6.0, 12.0, 18.0, 26.0, 34.0, 42.0)
ALCANCE = DISTANCIAS_RAYO[-1]
SALIDAS = ("adelante", "lado", "vertical")


def genoma_aleatorio():
    return [random.uniform(-0.5, 0.5) for _ in range(TAM_GENOMA)]


def _clip(v, lim=1.0):
    return -lim if v < -lim else (lim if v > lim else v)


class Cerebro:
    def __init__(self, genoma):
        k = C.ESCALA_PESOS
        g = [w * k for w in genoma]
        i = 0
        self.w1 = []
        for _ in range(NEURONAS):
            self.w1.append(g[i:i + N_ENTRADAS])
            i += N_ENTRADAS
        self.b1 = g[i:i + NEURONAS]
        i += NEURONAS
        self.w2 = []
        for _ in range(N_SALIDAS):
            self.w2.append(g[i:i + NEURONAS])
            i += NEURONAS
        self.b2 = g[i:i + N_SALIDAS]
        i += N_SALIDAS
        self.directo = []
        for _ in range(N_SALIDAS):
            self.directo.append(g[i:i + N_ENTRADAS])
            i += N_ENTRADAS
        self.oculta = [0.0] * NEURONAS
        self.salida = [0.0] * N_SALIDAS

    def decidir(self, x):
        tanh = math.tanh
        h = [tanh(sum(w * v for w, v in zip(fila, x)) + b) for fila, b in zip(self.w1, self.b1)]
        o = [tanh(sum(w * v for w, v in zip(f2, h)) + sum(w * v for w, v in zip(fd, x)) + b)
             for f2, fd, b in zip(self.w2, self.directo, self.b2)]
        self.oculta, self.salida = h, o
        return o


class Entorno:

    def __init__(self, ciudad, mapa, aves=None, viento=None, obstaculos=()):
        self.ciudad, self.mapa = ciudad, mapa
        self.aves, self.viento = aves, viento
        self.obstaculos = list(obstaculos)

    def obstaculo_en(self, x, y, z, zonas, lineas):
        if self.mapa.altura_sensor(x, y) > z - 3:
            return True
        for ox, oy, r, h in self.obstaculos:
            if z < h + 3 and (x - ox) ** 2 + (y - oy) ** 2 < (r + 2) ** 2:
                return True
        for zp in zonas:
            if zp.distancia(x, y) < 0:
                return True
        for l in lineas:
            d, a = l.cercania(x, y)
            if d < 5 and abs(z - l.altura_cable(a)) < 6:
                return True
        return False


def sensores(dron_pos, vel, est, objetivo, aterrizar, entorno, viento_est):
    ex, ey, ez = est
    tx, ty, tz = objetivo
    dx, dy = tx - ex, ty - ey
    d = math.hypot(dx, dy)
    if d > 1e-3:
        ux, uy = dx / d, dy / d
    else:
        v = math.hypot(vel[0], vel[1])
        ux, uy = (vel[0] / v, vel[1] / v) if v > 0.1 else (1.0, 0.0)
    lx, ly = -uy, ux
    dz = tz - ez
    x, y, z = dron_pos
    sup = entorno.mapa.altura_sensor(x, y)
    zonas = [zp for zp in entorno.ciudad.prohibidas if zp.distancia(x, y) < ALCANCE + 5]
    lineas = [l for l in entorno.ciudad.lineas
              if abs(l.x0 - x) < l.largo + ALCANCE and abs(l.y0 - y) < l.largo + ALCANCE
              and l.cercania(x, y)[0] < ALCANCE + 5]
    rayos = []
    for ang in DIRECCIONES:
        c, s = math.cos(ang), math.sin(ang)
        rx, ry = ux * c + lx * s, uy * c + ly * s
        prox = 0.0
        for dist in DISTANCIAS_RAYO:
            if entorno.obstaculo_en(x + rx * dist, y + ry * dist, z, zonas, lineas):
                prox = 1.0 - dist / (ALCANCE + 6)
                break
        rayos.append(prox)
    alto = 0.0
    for dist in DISTANCIAS_RAYO:
        px, py = x + ux * dist, y + uy * dist
        h = entorno.mapa.altura_sensor(px, py)
        for ox, oy, r, hh in entorno.obstaculos:
            if (px - ox) ** 2 + (py - oy) ** 2 < (r + 2) ** 2:
                h = max(h, hh)
        alto = max(alto, h)
    ave = (0.0, 0.0, 0.0, 0.0)
    if entorno.aves is not None:
        mejor = None
        for _, _, (bx, by, bz) in entorno.aves.cercanas(x, y, z, 50.0):
            dist = (bx - x) ** 2 + (by - y) ** 2 + (bz - z) ** 2
            if mejor is None or dist < mejor[0]:
                mejor = (dist, bx - x, by - y, bz - z)
        if mejor:
            _, bx, by, bz = mejor
            ave = (_clip((bx * ux + by * uy) / 50), _clip((bx * lx + by * ly) / 50),
                   _clip(bz / 20), 1.0)
    wx, wy = viento_est[0], viento_est[1]
    return [1.0,
            math.tanh(d / 3), math.tanh(d / 30), math.tanh(d / 200),
            _clip(dz / 20), math.tanh(dz / 3),
            _clip((vel[0] * ux + vel[1] * uy) / 15), _clip((vel[0] * lx + vel[1] * ly) / 10),
            _clip(vel[2] / 4),
            _clip((z - sup) / 30), math.tanh((z - sup) / 3),
            1.0 if aterrizar else 0.0,
            *rayos,
            _clip((alto - z) / 20),
            *ave,
            _clip((wx * ux + wy * uy) / 10), _clip((wx * lx + wy * ly) / 10)], (ux, uy, lx, ly)


def velocidad_deseada(salida, marco, v_max, dist, dz):
    ux, uy, lx, ly = marco
    v_adelante = min(v_max, math.sqrt(2 * 1.8 * dist), 1.0 * dist + 0.05)
    v_lado = min(8.0, 0.5 + 0.8 * dist)
    v_vert = min(4.0, 0.6 * abs(dz) + 0.35)
    va, vl, vz = salida[0] * v_adelante, salida[1] * v_lado, salida[2] * v_vert
    return va * ux + vl * lx, va * uy + vl * ly, vz
