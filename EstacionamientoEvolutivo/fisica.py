import hashlib
import math

import config as C


def rectangulo(x0, y0, x1, y1):
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]


def caja(poligono):
    xs = [p[0] for p in poligono]
    ys = [p[1] for p in poligono]
    return min(xs), min(ys), max(xs), max(ys)


def poligonos_chocan(p, q):
    for poli in (p, q):
        n = len(poli)
        for i in range(n):
            x1, y1 = poli[i]
            x2, y2 = poli[(i + 1) % n]
            ax, ay = y1 - y2, x2 - x1
            pp = [ax * x + ay * y for x, y in p]
            pq = [ax * x + ay * y for x, y in q]
            if max(pp) < min(pq) or max(pq) < min(pp):
                return False
    return True


def angulo_normal(a):
    return (a + math.pi) % (2 * math.pi) - math.pi


class Escenario:

    def __init__(self, modo=C.MODO_ESTACIONAR, objetivo=C.CAJON_OBJETIVO, inicio=C.INICIO):
        if modo not in C.MODOS:
            raise ValueError(f"Modo desconocido: {modo!r} (usa {' o '.join(C.MODOS)})")
        self.modo = modo
        self.inicio = inicio
        self.objetivo = objetivo
        self.cajones = cajones()

        holgura = (C.CAJON_ANCHO - C.AUTO_ANCHO) / 2
        frente = C.CAJON_FONDO - 0.4
        self.estacionados = []
        self.ocupados = []
        for i, (x0, _, x1, _) in enumerate(self.cajones):
            if i != objetivo:
                self.estacionados.append(
                    rectangulo(x0 + holgura, frente - C.AUTO_LARGO, x1 - holgura, frente))
                self.ocupados.append(i)

        cx0, cy0, cx1, cy1 = self.cajones[objetivo]
        self.cajon = (cx0, cy0, cx1, cy1)
        self.centro_cajon = ((cx0 + cx1) / 2, (cy0 + cy1) / 2)
        m = C.LINEA_ANCHO / 2 + C.MARGEN_LINEA
        self.zona_valida = (cx0 + m, cy0, cx1 - m, cy1 - m)
        self.angulo_objetivo = -math.pi / 2 if modo == "frente" else math.pi / 2
        self.pose_referencia = (self.centro_cajon[0] + C.REFERENCIA_X[modo], inicio[1], 0.0)
        self.desplazamiento = self.centro_cajon[0] - centro_x(C.CAJON_OBJETIVO)
        self.hueco = holgura

        self.obstaculos = [(p, caja(p)) for p in self.estacionados]


def cajones():
    res = []
    for i in range(C.NUM_CAJONES):
        x0 = C.MARGEN_X + i * C.CAJON_ANCHO
        res.append((x0, 0.0, x0 + C.CAJON_ANCHO, C.CAJON_FONDO))
    return res


def centro_x(i):
    x0, _, x1, _ = cajones()[i]
    return (x0 + x1) / 2


def cajones_posibles(modo):
    mitad = C.AUTO_LARGO / 2 + 0.2
    return [i for i in range(C.NUM_CAJONES)
            if C.INICIO[0] - 1e-6 <= centro_x(i) + C.REFERENCIA_X[modo] <= C.LOTE_ANCHO - mitad]


def huella(modo):
    return hashlib.sha1(repr((
        modo, C.CAJON_ANCHO, C.CAJON_FONDO, C.LOTE_ALTO, C.INICIO[1], C.REFERENCIA_X[modo],
        C.AUTO_LARGO, C.AUTO_ANCHO, C.DIST_EJES, C.GIRO_MAX)).encode()).hexdigest()[:16]


def esquinas_pose(x, y, ang):
    c, s = math.cos(ang), math.sin(ang)
    hl, hw = C.AUTO_LARGO / 2, C.AUTO_ANCHO / 2
    return [(x + lx * c - ly * s, y + lx * s + ly * c)
            for lx, ly in ((hl, -hw), (hl, hw), (-hl, hw), (-hl, -hw))]


def choca(escenario, esquinas):
    for x, y in esquinas:
        if x < 0 or y < 0 or x > C.LOTE_ANCHO or y > C.LOTE_ALTO:
            return True
    bx0, by0, bx1, by1 = caja(esquinas)
    for poli, (ox0, oy0, ox1, oy1) in escenario.obstaculos:
        if bx1 < ox0 or bx0 > ox1 or by1 < oy0 or by0 > oy1:
            continue
        if poligonos_chocan(esquinas, poli):
            return True
    return False


def avanzar_pose(x, y, ang, distancia, giro):
    medio = C.DIST_EJES / 2
    rx, ry = x - medio * math.cos(ang), y - medio * math.sin(ang)
    curvatura = math.tan(giro) / C.DIST_EJES
    if abs(curvatura) < 1e-9:
        rx += distancia * math.cos(ang)
        ry += distancia * math.sin(ang)
    else:
        nuevo = ang + distancia * curvatura
        radio = 1 / curvatura
        rx += radio * (math.sin(nuevo) - math.sin(ang))
        ry -= radio * (math.cos(nuevo) - math.cos(ang))
        ang = nuevo
    ang = angulo_normal(ang)
    return rx + medio * math.cos(ang), ry + medio * math.sin(ang), ang


class Auto:
    __slots__ = ("x", "y", "ang", "v", "giro", "marcha")

    def __init__(self, x, y, ang):
        self.x, self.y, self.ang = x, y, ang
        self.v = 0.0
        self.giro = 0.0
        self.marcha = 1

    def mover(self, acelerador, freno, volante, marcha, dt=C.DT):
        if marcha != self.marcha and abs(self.v) < C.V_CAMBIO:
            self.marcha = marcha
            self.v = 0.0

        objetivo = volante * C.GIRO_MAX
        paso_max = C.VEL_VOLANTE * dt
        self.giro += max(-paso_max, min(paso_max, objetivo - self.giro))

        v = self.v + self.marcha * acelerador * C.ACEL_MAX * dt
        resistencia = (freno * C.FRENO_MAX + C.RODADURA) * dt
        if abs(v) <= resistencia:
            v = 0.0
        else:
            v -= math.copysign(resistencia, v)
        self.v = max(-C.V_REVERSA, min(C.V_MAX, v))

        self.x, self.y, self.ang = avanzar_pose(self.x, self.y, self.ang,
                                                self.v * dt, self.giro)

    def esquinas(self):
        return esquinas_pose(self.x, self.y, self.ang)

    def choca(self, escenario, esquinas=None):
        return choca(escenario, esquinas or self.esquinas())
