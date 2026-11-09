import math

import config as C
from camara import Camara
from fisica import Camion, angulo_normal, choca
from navegacion import MapaRelativo
from plan import decodificar

ACTIVO, CHOQUE, TIJERA, ESTACIONADO, TIEMPO, INMOVIL, TERMINO = (
    "activo", "chocó", "tijera", "estacionado", "sin tiempo", "inmóvil", "terminó")
BUSCANDO, YENDO, LISTO = "buscando lugar", "yendo al lugar", "en posición"

APTITUD_EXITO = 3000.0


def asistente_reversa(camion, objetivo):
    k1, k2 = C.GANANCIAS_ASISTENTE[camion.remolques]
    arts = camion.articulaciones()
    deseado = objetivo
    if len(arts) > 1:
        tope = math.radians(55)
        deseado = max(-tope, min(tope, objetivo + k2 * (arts[1] - objetivo)))
    return max(-1.0, min(1.0, k1 * (arts[0] - deseado) / C.GIRO_MAX))


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

    def controles(self, camion):
        m = self.maniobra
        if m is None:
            return 0.0, 1.0, camion.giro / C.GIRO_MAX, camion.marcha
        frac = self.recorrido / m.distancia
        if m.marcha < 0 and C.ASISTENTE_REVERSA:
            volante = asistente_reversa(camion, m.volante_en(frac) * C.ARTICULACION_PLAN)
        else:
            volante = m.volante_en(frac)
        if camion.marcha != m.marcha:
            return 0.0, 1.0, volante, m.marcha
        if self.recorrido == 0.0 and abs(camion.giro - volante * C.GIRO_MAX) > math.radians(4):
            return 0.0, 1.0, volante, m.marcha
        restante = m.distancia - self.recorrido
        if restante <= C.TOLERANCIA_TRAMO:
            return 0.0, 1.0, volante, m.marcha
        deseada = min(m.velocidad, max(C.V_ARRASTRE, math.sqrt(2 * C.FRENADO_SUAVE * restante)))
        error = deseada - abs(camion.v)
        if error >= 0:
            return min(1.0, error * 2.0), 0.0, volante, m.marcha
        return 0.0, min(1.0, -error * 1.5), volante, m.marcha

    def avanzo(self, camion, distancia):
        m = self.maniobra
        if m is None:
            return
        self.recorrido += distancia
        if m.distancia - self.recorrido <= C.TOLERANCIA_TRAMO and abs(camion.v) < 0.01:
            self.indice += 1
            self.recorrido = 0.0


class Agente:
    def __init__(self, genoma, escenario, mapa, inicio=None):
        self.genoma = genoma
        self.plan = decodificar(genoma)
        self.conductor = Conductor(self.plan)
        self.esc = escenario
        self.mapa = mapa
        self.camion = Camion(*(inicio or escenario.inicio), escenario.remolques)
        self.estado = ACTIVO
        self.pasos = 0
        self._inmovil = 0
        self.controles = (0.0, 0.0, 0.0, 1)
        self.costo_inicial = mapa.consultar(*self._pose_guia()) or 1.0
        self.costo = self.costo_inicial
        self.costo_min = self.costo
        self.rastro = [(self.camion.x, self.camion.y)]
        if not self.plan:
            self.estado = TERMINO

    @property
    def activo(self):
        return self.estado == ACTIVO

    @property
    def maniobras(self):
        en_curso = 1 if (self.conductor.maniobra and self.conductor.recorrido > 0) else 0
        return self.conductor.indice + en_curso

    def _pose_guia(self):
        return self.camion.pose_guia(self.esc.modo)

    def desvio_lateral(self):
        cx = self.esc.centro_cajon[0]
        return max(abs(x - cx) for x, _ in self.camion.centros())

    def error_angulo(self):
        return max(abs(angulo_normal(a - self.esc.angulo_objetivo))
                   for a in self.camion.angulos)

    def fraccion_dentro(self, carrocerias=None):
        x0, y0, x1, y1 = self.esc.zona_valida
        esquinas = [p for esq in (carrocerias or self.camion.carrocerias()) for p in esq]
        return sum(1 for x, y in esquinas if x0 <= x <= x1 and y0 <= y <= y1) / len(esquinas)

    def espacio_a_lineas(self):
        cx0, _, cx1, _ = self.esc.cajon
        izq, der = cx0 + C.LINEA_ANCHO / 2, cx1 - C.LINEA_ANCHO / 2
        return min(min(x - izq, der - x)
                   for esq in self.camion.carrocerias() for x, _ in esq)

    def articulacion_max(self):
        return max(abs(a) for a in self.camion.articulaciones())

    def precision(self):
        lateral = max(0.0, 1 - self.desvio_lateral() / C.TOL_CENTRO)
        angular = max(0.0, 1 - self.error_angulo() / C.TOL_ANGULO)
        return (lateral + angular) / 2

    def bien_estacionado(self, carrocerias=None):
        return (self.fraccion_dentro(carrocerias) == 1.0
                and self.desvio_lateral() <= C.TOL_CENTRO
                and self.error_angulo() <= C.TOL_ANGULO
                and abs(self.camion.v) <= C.V_ESTACIONADO)

    def paso(self):
        if not self.activo:
            return
        cam = self.camion
        self.controles = self.conductor.controles(cam)
        x0, y0 = cam.x, cam.y
        cam.mover(*self.controles)
        self.conductor.avanzo(cam, math.hypot(cam.x - x0, cam.y - y0))
        self.pasos += 1
        self._inmovil = self._inmovil + 1 if abs(cam.v) < 0.01 else 0
        if self.pasos % 2 == 0:
            self.rastro.append((cam.x, cam.y))

        if cam.en_tijera():
            self.estado = TIJERA
            return
        carrocerias = cam.carrocerias()
        if any(choca(self.esc, esq) for esq in carrocerias):
            self.estado = CHOQUE
            return
        c = self.mapa.consultar(*self._pose_guia())
        if c is not None:
            self.costo = c
            self.costo_min = min(self.costo_min, c)
        detenido = abs(cam.v) <= C.V_ESTACIONADO
        if self.conductor.termino and detenido:
            self.estado = ESTACIONADO if self.bien_estacionado(carrocerias) else TERMINO
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
        dentro = self.fraccion_dentro()
        f = 1200 * avance + 400 * mejor + 240 * dentro
        if dentro == 1.0:
            lat, ang = self.desvio_lateral(), self.error_angulo()
            f += 300 * max(0.0, 1 - lat / 0.75) + 300 * max(0.0, 1 - ang / math.radians(10))
            f += 150 * (lat <= C.TOL_CENTRO) + 150 * (ang <= C.TOL_ANGULO)
            f += 200 * (1 - min(abs(self.camion.v), 1.0))
        if self.estado in (CHOQUE, TIJERA):
            f -= C.CASTIGO_CHOQUE + C.CASTIGO_CHOQUE_VEL * abs(self.camion.v)
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
        self.camion = Camion(*escenario.inicio, escenario.remolques)
        self.camara = Camara() if busqueda else None
        self.cajon = None if busqueda else escenario.objetivo
        self.estado = BUSCANDO if busqueda else YENDO
        self.pasos = 0
        self.controles = (0.0, 0.0, 0.0, 1)
        self.rastro = [(self.camion.x, self.camion.y)]

    @property
    def listo(self):
        return self.estado == LISTO

    def posicion_camara(self):
        cam, cfg = self.camion, C.CAMARA
        c, s = math.cos(cam.ang), math.sin(cam.ang)
        return cam.x + cfg["x"] * c - cfg["y"] * s, cam.y + cfg["x"] * s + cfg["y"] * c

    def paso(self):
        cam = self.camion
        self.pasos += 1
        if self.estado == BUSCANDO:
            encontrado = self.camara.observar(self.esc, *self.posicion_camara(), cam.ang)
            if encontrado is not None:
                self.cajon = encontrado
                self.estado = YENDO
            elif cam.x > C.LOTE_ANCHO - 8 or self.pasos > C.PASOS_LLEGADA:
                self.cajon = self.esc.objetivo
                self.estado = YENDO
        if self.estado == BUSCANDO:
            self.controles = manejar_recto(cam, C.LOTE_ANCHO, C.V_BUSQUEDA)
        else:
            meta = self.esc.pose_referencia[0]
            if abs(meta - cam.x) < 0.03 and abs(cam.v) < 0.01:
                self.estado = LISTO
                return
            self.controles = manejar_recto(cam, meta, C.V_ACERCAMIENTO)
        cam.mover(*self.controles)
        if self.pasos % 2 == 0:
            self.rastro.append((cam.x, cam.y))


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
        c = {ACTIVO: 0, CHOQUE: 0, TIJERA: 0, ESTACIONADO: 0, TIEMPO: 0, INMOVIL: 0,
             TERMINO: 0}
        for a in self.agentes:
            c[a.estado] += 1
        return c
