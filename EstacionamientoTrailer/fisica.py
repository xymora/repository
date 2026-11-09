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


def caja_orientada(x, y, ang, frente, atras, ancho):
    c, s = math.cos(ang), math.sin(ang)
    hw = ancho / 2
    return [(x + lx * c - ly * s, y + lx * s + ly * c)
            for lx, ly in ((frente, -hw), (frente, hw), (-atras, hw), (-atras, -hw))]


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


class Escenario:

    def __init__(self, modo=C.MODO_ESTACIONAR, remolques=C.NUM_REMOLQUES,
                 objetivo=None, tamano=C.TAMANO, inicio=C.INICIO):
        if modo not in C.MODOS:
            raise ValueError(f"Modo desconocido: {modo!r} (usa {' o '.join(C.MODOS)})")
        if remolques not in C.OPCIONES_REMOLQUES:
            raise ValueError(f"Número de remolques no válido: {remolques!r}")
        self.modo = modo
        self.remolques = remolques
        self.inicio = inicio
        self.tamano = tamano
        self.cajones = cajones(tamano)
        self.objetivo = len(self.cajones) // 2 if objetivo is None else objetivo
        objetivo = self.objetivo

        ancho = 2.6
        holgura = (C.TAMANOS[tamano] - ancho) / 2
        self.hueco = holgura
        self.estacionados = []
        self.lanzas = []
        self.ocupados = []
        for i, (x0, _, x1, _) in enumerate(self.cajones):
            if i == objetivo:
                continue
            y = C.ESTACIONADO_FONDO
            for k, largo in enumerate(C.ESTACIONADO_CAJAS):
                if k:
                    self.lanzas.append(((x0 + x1) / 2, y, (x0 + x1) / 2,
                                        y + C.ESTACIONADO_SEPARACION))
                    y += C.ESTACIONADO_SEPARACION
                self.estacionados.append(rectangulo(x0 + holgura, y, x1 - holgura,
                                                    y + largo))
                self.ocupados.append(i)
                y += largo

        cx0, cy0, cx1, cy1 = self.cajones[objetivo]
        self.cajon = (cx0, cy0, cx1, cy1)
        self.centro_cajon = ((cx0 + cx1) / 2, (cy0 + cy1) / 2)
        m = C.LINEA_ANCHO / 2 + C.MARGEN_LINEA
        self.zona_valida = (cx0 + m, cy0, cx1 - m, cy1 - m)
        self.angulo_objetivo = -math.pi / 2 if modo == "frente" else math.pi / 2
        self.pose_referencia = (self.centro_cajon[0] + C.REFERENCIA_X[modo], inicio[1], 0.0)
        referencia = self.cajones[len(self.cajones) // 2]
        self.desplazamiento = self.centro_cajon[0] - (referencia[0] + referencia[2]) / 2

        self.obstaculos = [(p, caja(p)) for p in self.estacionados]

        self.huella = huella(modo, remolques)


def cajones(tamano=C.TAMANO):
    ancho = C.TAMANOS[tamano]
    n = int((C.LOTE_ANCHO - 2 * C.MARGEN_X) / ancho)
    x0 = (C.LOTE_ANCHO - n * ancho) / 2
    return [(x0 + i * ancho, 0.0, x0 + (i + 1) * ancho, C.CAJON_FONDO) for i in range(n)]


def largo_detras(remolques):
    x = 0.0
    for prev, spec in zip([C.TRACTOR] + C.REMOLQUES[remolques], C.REMOLQUES[remolques]):
        x += -prev["enganche_atras"] + spec["largo_lanza"]
    return x + C.REMOLQUES[remolques][-1]["atras"]


def cajones_posibles(modo, remolques, tamano=C.TAMANO):
    minimo = largo_detras(remolques) + 1.0
    maximo = C.LOTE_ANCHO - C.TRACTOR["frente"] - 1.0
    return [i for i, (x0, _, x1, _) in enumerate(cajones(tamano))
            if minimo <= (x0 + x1) / 2 + C.REFERENCIA_X[modo] <= maximo]


def huella(modo, remolques):
    return hashlib.sha1(repr((
        modo, remolques, C.TRACTOR, C.REMOLQUES[remolques], C.LOTE_ALTO, C.CAJON_FONDO,
        C.INICIO[1], C.REFERENCIA_X[modo], C.GIRO_MAX, C.ASISTENTE_REVERSA,
        "v2")).encode()).hexdigest()[:16]


class Camion:
    __slots__ = ("x", "y", "angulos", "v", "giro", "marcha", "remolques", "specs")

    def __init__(self, x, y, ang, remolques=C.NUM_REMOLQUES):
        self.x, self.y = x, y
        self.remolques = remolques
        self.specs = [C.TRACTOR] + C.REMOLQUES[remolques]
        self.angulos = [ang] * len(self.specs)
        self.v = 0.0
        self.giro = 0.0
        self.marcha = 1

    @property
    def ang(self):
        return self.angulos[0]

    def ejes(self):
        puntos = [(self.x, self.y)]
        for i in range(1, len(self.specs)):
            px, py = puntos[-1]
            a_prev = self.angulos[i - 1]
            m = self.specs[i - 1]["enganche_atras"]
            hx, hy = px - m * math.cos(a_prev), py - m * math.sin(a_prev)
            lanza = self.specs[i]["largo_lanza"]
            a = self.angulos[i]
            puntos.append((hx - lanza * math.cos(a), hy - lanza * math.sin(a)))
        return puntos

    def enganches(self):
        ejes = self.ejes()
        res = []
        for i in range(1, len(self.specs)):
            px, py = ejes[i - 1]
            a = self.angulos[i - 1]
            m = self.specs[i - 1]["enganche_atras"]
            res.append((px - m * math.cos(a), py - m * math.sin(a)))
        return res

    def carrocerias(self):
        return [caja_orientada(x, y, a, s["frente"], s["atras"], s["ancho"])
                for (x, y), a, s in zip(self.ejes(), self.angulos, self.specs)]

    def centros(self):
        return [(x + (s["frente"] - s["atras"]) / 2 * math.cos(a),
                 y + (s["frente"] - s["atras"]) / 2 * math.sin(a))
                for (x, y), a, s in zip(self.ejes(), self.angulos, self.specs)]

    def articulaciones(self):
        return [angulo_normal(self.angulos[i - 1] - self.angulos[i])
                for i in range(1, len(self.angulos))]

    def en_tijera(self):
        return any(abs(a) > C.TIJERA for a in self.articulaciones())

    def choca(self, escenario):
        return any(choca(escenario, esq) for esq in self.carrocerias())

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

        h = dt / C.SUBPASOS
        for _ in range(C.SUBPASOS):
            self._integrar(h)

    def _integrar(self, h):
        angs = self.angulos
        c0, s0 = math.cos(angs[0]), math.sin(angs[0])
        vx, vy = self.v * c0, self.v * s0
        omega = self.v * math.tan(self.giro) / self.specs[0]["dist_ejes"]
        omegas = [omega]
        for i in range(1, len(self.specs)):
            a_prev = angs[i - 1]
            m = self.specs[i - 1]["enganche_atras"]
            hx = vx + omegas[-1] * m * math.sin(a_prev)
            hy = vy - omegas[-1] * m * math.cos(a_prev)
            ci, si = math.cos(angs[i]), math.sin(angs[i])
            omegas.append((-hx * si + hy * ci) / self.specs[i]["largo_lanza"])
            avance = hx * ci + hy * si
            vx, vy = avance * ci, avance * si
        self.x += self.v * c0 * h
        self.y += self.v * s0 * h
        self.angulos = [angulo_normal(a + w * h) for a, w in zip(angs, omegas)]

    def pose_guia(self, modo):
        cx, cy = self.centros()[0 if modo == "frente" else -1]
        a = self.angulos[0] if modo == "frente" else angulo_normal(self.angulos[-1] + math.pi)
        return cx, cy, a
