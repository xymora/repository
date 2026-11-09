import math

import config as C

FONDO, VEHICULO, BORDE, NADA = "fondo", "vehículo", "borde", "nada"


def _cruce(ox, oy, dx, dy, ax, ay, bx, by):
    ex, ey = bx - ax, by - ay
    den = dx * ey - dy * ex
    if abs(den) < 1e-12:
        return None
    qx, qy = ax - ox, ay - oy
    t = (qx * ey - qy * ex) / den
    u = (qx * dy - qy * dx) / den
    return t if t > 0 and 0 <= u <= 1 else None


def lanzar(escenario, ox, oy, ang, alcance):
    dx, dy = math.cos(ang), math.sin(ang)
    mejor, tipo = alcance, NADA
    if dy < 0:
        t = -oy / dy
        if t < mejor:
            mejor, tipo = t, FONDO
    elif dy > 0:
        t = (C.LOTE_ALTO - oy) / dy
        if t < mejor:
            mejor, tipo = t, BORDE
    if dx < 0:
        t = -ox / dx
        if t < mejor:
            mejor, tipo = t, BORDE
    elif dx > 0:
        t = (C.LOTE_ANCHO - ox) / dx
        if t < mejor:
            mejor, tipo = t, BORDE
    fx, fy = ox + dx * mejor, oy + dy * mejor
    for poli, (bx0, by0, bx1, by1) in escenario.obstaculos:
        if max(ox, fx) < bx0 or min(ox, fx) > bx1 or max(oy, fy) < by0 or min(oy, fy) > by1:
            continue
        for i in range(len(poli)):
            (ax, ay), (bx, by) = poli[i], poli[(i + 1) % len(poli)]
            t = _cruce(ox, oy, dx, dy, ax, ay, bx, by)
            if t is not None and t < mejor:
                mejor, tipo = t, VEHICULO
                fx, fy = ox + dx * mejor, oy + dy * mejor
    return mejor, tipo


def franja_central(escenario, x):
    for i, (x0, _, x1, _) in enumerate(escenario.cajones):
        media = (x1 - x0) / 2 - escenario.hueco - 0.3
        if abs(x - (x0 + x1) / 2) <= media:
            return i
    return None


class Camara:

    def __init__(self):
        self.evidencia = {}
        self.lecturas = []
        self.encontrado = None

    def observar(self, escenario, x, y, ang):
        cfg = C.CAMARA
        n = cfg["rayos"]
        self.lecturas = []
        for k in range(n):
            a = ang + math.radians(cfg["desde"] + (cfg["hasta"] - cfg["desde"]) * k / (n - 1))
            d, tipo = lanzar(escenario, x, y, a, cfg["alcance"])
            hx, hy = x + d * math.cos(a), y + d * math.sin(a)
            cajon = franja_central(escenario, hx) if tipo == FONDO else None
            if cajon is not None:
                self.evidencia[cajon] = self.evidencia.get(cajon, 0) + 1
            self.lecturas.append((x, y, hx, hy, d, tipo, cajon is not None))
        if self.encontrado is None and self.evidencia:
            cajon, votos = max(self.evidencia.items(), key=lambda e: e[1])
            if votos >= C.EVIDENCIA_LUGAR:
                self.encontrado = cajon
        return self.encontrado
