import math

import config as C
from camara import Camara
from fisica import Auto, angulo_normal
from navegacion import MapaRelativo
from plan import decodificar

ACTIVO, CHOQUE, ESTACIONADO, TIEMPO, INMOVIL, TERMINO = (
    "activo", "chocó", "estacionado", "sin tiempo", "inmóvil", "terminó")
BUSCANDO, YENDO, LISTO = "buscando lugar", "yendo al lugar", "en posición"

APTITUD_EXITO = 3000.0


class Conductor:

    def __init__(self, plan):
        self.plan = plan
        self.indice = 0
        self.recorrido = 0.0

    @property
    def maniobra(self):
        return self.plan[self.indice] if self.indice < len(self.plan) else None

    @property
    def termino(self):
        return self.indice >= len(self.plan)

    def controles(self, auto):
        m = self.maniobra
        if m is None:
            return 0.0, 1.0, auto.giro / C.GIRO_MAX, auto.marcha
        frac = self.recorrido / m.distancia
        volante = m.volante_en(frac)
        if auto.marcha != m.marcha:
            return 0.0, 1.0, volante, m.marcha
        if self.recorrido == 0.0 and abs(auto.giro - volante * C.GIRO_MAX) > math.radians(4):
            return 0.0, 1.0, volante, m.marcha
        restante = m.distancia - self.recorrido
        if restante <= C.TOLERANCIA_TRAMO:
            return 0.0, 1.0, volante, m.marcha
        deseada = min(m.velocidad, max(C.V_ARRASTRE, math.sqrt(2 * C.FRENADO_SUAVE * restante)))
        error = deseada - abs(auto.v)
        if error >= 0:
            return min(1.0, error * 2.0), 0.0, volante, m.marcha
        return 0.0, min(1.0, -error * 1.5), volante, m.marcha

    def avanzo(self, auto, distancia):
        m = self.maniobra
        if m is None:
            return
        self.recorrido += distancia
        if m.distancia - self.recorrido <= C.TOLERANCIA_TRAMO and abs(auto.v) < 0.01:
            self.indice += 1
            self.recorrido = 0.0


class Agente:
    def __init__(self, genoma, escenario, mapa, inicio=None):
        self.genoma = genoma
        self.plan = decodificar(genoma)
        self.conductor = Conductor(self.plan)
        self.esc = escenario
        self.mapa = mapa
        self.auto = Auto(*(inicio or escenario.inicio))
        self.estado = ACTIVO
        self.pasos = 0
        self._inmovil = 0
        self.controles = (0.0, 0.0, 0.0, 1)
        self.costo_inicial = mapa.consultar(*self._pose()) or 1.0
        self.costo = self.costo_inicial
        self.costo_min = self.costo
        self.rastro = [(self.auto.x, self.auto.y)]
        if not self.plan:
            self.estado = TERMINO

    @property
    def activo(self):
        return self.estado == ACTIVO

    @property
    def maniobras(self):
        en_curso = 1 if (self.conductor.maniobra and self.conductor.recorrido > 0) else 0
        return self.conductor.indice + en_curso

    def _pose(self):
        return self.auto.x, self.auto.y, self.auto.ang

    def distancia(self):
        cx, cy = self.esc.centro_cajon
        return math.hypot(self.auto.x - cx, self.auto.y - cy)

    def desvio_lateral(self):
        return abs(self.auto.x - self.esc.centro_cajon[0])

    def error_angulo(self):
        return abs(angulo_normal(self.auto.ang - self.esc.angulo_objetivo))

    def esquinas_dentro(self, esquinas=None):
        x0, y0, x1, y1 = self.esc.zona_valida
        return sum(1 for x, y in (esquinas or self.auto.esquinas())
                   if x0 <= x <= x1 and y0 <= y <= y1)

    def espacio_a_lineas(self):
        cx0, _, cx1, _ = self.esc.cajon
        izq, der = cx0 + C.LINEA_ANCHO / 2, cx1 - C.LINEA_ANCHO / 2
        return min(min(x - izq, der - x) for x, _ in self.auto.esquinas())

    def de_frente(self):
        return abs(angulo_normal(self.auto.ang + math.pi / 2)) < math.pi / 2

    def precision(self):
        lateral = max(0.0, 1 - self.desvio_lateral() / C.TOL_CENTRO)
        angular = max(0.0, 1 - self.error_angulo() / C.TOL_ANGULO)
        return (lateral + angular) / 2

    def bien_estacionado(self, esquinas=None):
        return (self.esquinas_dentro(esquinas) == 4
                and self.desvio_lateral() <= C.TOL_CENTRO
                and self.error_angulo() <= C.TOL_ANGULO
                and abs(self.auto.v) <= C.V_ESTACIONADO)

    def paso(self):
        if not self.activo:
            return
        a = self.auto
        self.controles = self.conductor.controles(a)
        x0, y0 = a.x, a.y
        a.mover(*self.controles)
        self.conductor.avanzo(a, math.hypot(a.x - x0, a.y - y0))
        self.pasos += 1
        self._inmovil = self._inmovil + 1 if abs(a.v) < 0.01 else 0
        if self.pasos % 3 == 0:
            self.rastro.append((a.x, a.y))

        esq = a.esquinas()
        if a.choca(self.esc, esq):
            self.estado = CHOQUE
            return
        c = self.mapa.consultar(*self._pose())
        if c is not None:
            self.costo = c
            self.costo_min = min(self.costo_min, c)
        detenido = abs(a.v) <= C.V_ESTACIONADO
        if self.conductor.termino and detenido:
            self.estado = ESTACIONADO if self.bien_estacionado(esq) else TERMINO
        elif self._inmovil >= C.PASOS_INMOVIL:
            self.estado = INMOVIL
        elif self.pasos >= C.PASOS_MAX:
            self.estado = TIEMPO

    def aptitud(self):
        if self.estado == ESTACIONADO:
            return (APTITUD_EXITO
                    + 1000.0 * (1 - self.pasos / C.PASOS_MAX)
                    + 300.0 * (C.MAX_MANIOBRAS - self.maniobras)
                    + 400.0 * self.precision())
        avance = 1 - self.costo / self.costo_inicial
        mejor = 1 - self.costo_min / self.costo_inicial
        dentro = self.esquinas_dentro()
        f = 1200 * avance + 400 * mejor + 60 * dentro
        if dentro == 4:
            lat, ang = self.desvio_lateral(), self.error_angulo()
            f += 300 * max(0.0, 1 - lat / 0.5) + 300 * max(0.0, 1 - ang / math.radians(10))
            f += 150 * (lat <= C.TOL_CENTRO) + 150 * (ang <= C.TOL_ANGULO)
            f += 200 * (1 - min(abs(self.auto.v), 1.0))
        if self.estado == CHOQUE:
            f -= C.CASTIGO_CHOQUE + C.CASTIGO_CHOQUE_VEL * abs(self.auto.v)
        return f


def manejar_recto(vehiculo, objetivo_x, v_max, frenado=C.FRENADO_SUAVE):
    falta = objetivo_x - vehiculo.x
    marcha = 1 if falta > 0 else -1
    if marcha != vehiculo.marcha and abs(vehiculo.v) > C.V_CAMBIO:
        return 0.0, 1.0, 0.0, vehiculo.marcha
    deseada = min(v_max, math.sqrt(2 * frenado * abs(falta)))
    error = deseada - abs(vehiculo.v)
    if error >= 0:
        return min(1.0, error * 2.0), 0.0, 0.0, marcha
    return 0.0, min(1.0, -error * 1.5), 0.0, marcha


class Explorador:

    def __init__(self, escenario, busqueda):
        self.esc = escenario
        self.auto = Auto(*escenario.inicio)
        self.camara = Camara() if busqueda else None
        self.cajon = None if busqueda else escenario.objetivo
        self.estado = BUSCANDO if busqueda else YENDO
        self.pasos = 0
        self.controles = (0.0, 0.0, 0.0, 1)
        self.rastro = [(self.auto.x, self.auto.y)]

    @property
    def listo(self):
        return self.estado == LISTO

    def posicion_camara(self):
        a, cfg = self.auto, C.CAMARA
        c, s = math.cos(a.ang), math.sin(a.ang)
        return a.x + cfg["x"] * c - cfg["y"] * s, a.y + cfg["x"] * s + cfg["y"] * c

    def paso(self):
        a = self.auto
        self.pasos += 1
        if self.estado == BUSCANDO:
            encontrado = self.camara.observar(self.esc, *self.posicion_camara(), a.ang)
            if encontrado is not None:
                self.cajon = encontrado
                self.estado = YENDO
            elif a.x > C.LOTE_ANCHO - C.AUTO_LARGO or self.pasos > C.PASOS_LLEGADA:
                self.cajon = self.esc.objetivo
                self.estado = YENDO
        if self.estado == BUSCANDO:
            self.controles = manejar_recto(a, C.LOTE_ANCHO, C.V_BUSQUEDA)
        else:
            meta = self.esc.pose_referencia[0]
            if abs(meta - a.x) < 0.02 and abs(a.v) < 0.01:
                self.estado = LISTO
                return
            self.controles = manejar_recto(a, meta, C.V_ACERCAMIENTO)
        a.mover(*self.controles)
        if self.pasos % 3 == 0:
            self.rastro.append((a.x, a.y))


class Generacion:
    def __init__(self, genomas, escenario, mapa, busqueda=False):
        self.escenario = escenario
        self.explorador = Explorador(escenario, busqueda)
        relativo = MapaRelativo(mapa, escenario.desplazamiento)
        self.agentes = [Agente(g, escenario, relativo, escenario.pose_referencia)
                        for g in genomas]

    @property
    def llegando(self):
        return not self.explorador.listo

    @property
    def terminada(self):
        return self.explorador.listo and not any(a.activo for a in self.agentes)

    def paso(self):
        if self.llegando:
            self.explorador.paso()
            return
        for a in self.agentes:
            if a.activo:
                a.paso()

    def correr(self):
        while not self.terminada:
            self.paso()

    def conteo(self):
        c = {ACTIVO: 0, CHOQUE: 0, ESTACIONADO: 0, TIEMPO: 0, INMOVIL: 0, TERMINO: 0}
        for a in self.agentes:
            c[a.estado] += 1
        return c
