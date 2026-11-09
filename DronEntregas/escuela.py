import csv
import json
import math
import os
import random
import zlib

import config as C
from ambiente import Aves, Viento, vector_rumbo
from cerebro import (TAM_GENOMA, Cerebro, Entorno, genoma_aleatorio, sensores,
                     velocidad_deseada)
from dron import Dron

CARPETA = os.path.dirname(os.path.abspath(__file__))
ARCHIVO_HISTORIAL = os.path.join(CARPETA, "historial.csv")
NOMBRE_LECCION = {"despegue": "Despegue", "crucero": "Volar a un punto",
                  "aterrizaje": "Aterrizaje de precisión", "esquivar": "Esquivar obstáculos",
                  "entrega": "Entrega completa"}
T_MAX = {"despegue": 25.0, "crucero": 70.0, "aterrizaje": 60.0, "esquivar": 90.0,
         "entrega": 300.0}
VOLANDO, EXITO, CHOQUE, TIEMPO = "volando", "aprobó", "chocó", "sin tiempo"
VERSION_CURSO = 3


def archivo_mejor(vehiculo):
    return os.path.join(CARPETA, f"mejor_cerebro_{vehiculo}.json")


def archivo_progreso(vehiculo):
    return os.path.join(CARPETA, f"progreso_escuela_{vehiculo}.json")


class Escenario:

    def __init__(self, leccion, indice, ciudad, plan, vehiculo):
        self.leccion, self.indice = leccion, indice
        self.ciudad, self.plan, self.vehiculo = ciudad, plan, vehiculo
        self.semilla = zlib.crc32(f"{leccion}|{indice}|{ciudad.zona.clave}".encode())
        rnd = random.Random(self.semilla)
        self.t_max = T_MAX[leccion]
        self.obstaculos = []
        self.aves_cruce = None
        self.viento_cfg = (rnd.uniform(2, 6), rnd.uniform(0, 360), False)
        self.ruta = None
        self.pad = None
        self.en_tierra = False
        self.falla_motor = None
        getattr(self, "_" + leccion)(rnd)
        self.nombre = f"{NOMBRE_LECCION[leccion]} {indice + 1}"

    def _azotea(self, rnd, cerca_de=None, dist=None):
        c = self.ciudad
        cands = [e for e in c.edificios if 6 <= e.h <= 45 and (e.x1 - e.x0) * (e.y1 - e.y0) > 150
                 and 300 < e.x0 and e.x1 < c.ancho - 300 and 300 < e.y0 and e.y1 < c.alto - 300]
        rnd.shuffle(cands)
        for e in cands:
            cx, cy = e.centro
            if cerca_de is not None:
                dd = math.hypot(cx - cerca_de[0], cy - cerca_de[1])
                if not dist[0] <= dd <= dist[1]:
                    continue
            if c.zona_prohibida(cx, cy, 150):
                continue
            if any(o is not e and o.h > e.h + 3 and o.contiene(cx, cy, 25)
                   for o in c.edificios_cerca(cx, cy, 30)):
                continue
            return e
        return cands[0]

    def _linea(self, rnd, largo, max_req, alto_medio=None):
        c, m = self.ciudad, self.plan.mapa
        for _ in range(3000):
            x, y = rnd.uniform(400, c.ancho - 400), rnd.uniform(400, c.alto - 400)
            dx, dy = vector_rumbo(rnd.uniform(0, 360))
            x1, y1 = x + dx * largo, y + dy * largo
            if not (200 < x1 < c.ancho - 200 and 200 < y1 < c.alto - 200):
                continue
            ok, maximo = True, 0.0
            for k in range(0, int(largo) + 1, 5):
                px, py = x + dx * k, y + dy * k
                cel = m.celda(px, py)
                medio = 0.25 * largo < k < 0.75 * largo
                if m.bloq[cel] or c.zona_prohibida(px, py, 60):
                    ok = False
                    break
                if medio and alto_medio:
                    maximo = max(maximo, m.altura_sensor(px, py))
                    if m.req[cel] > alto_medio[1] + C.SEPARACION_VERTICAL:
                        ok = False
                        break
                elif m.req[cel] > max_req:
                    ok = False
                    break
            if ok and alto_medio and not alto_medio[0] <= maximo <= alto_medio[1]:
                ok = False
            if ok:
                return (x, y), (x1, y1), (dx, dy)
        if alto_medio:
            return self._linea(rnd, largo, max_req)
        raise RuntimeError("No se encontró un tramo libre para la lección.")

    def _despegue(self, rnd):
        e = self._azotea(rnd)
        self.pad = e
        self.inicio = (*e.centro, e.h)
        self.en_tierra = True
        self.meta = (*e.centro, e.h + 25)
        self.radio_meta = 2.0
        vel = (3, 6, 9)[self.indice % 3]
        self.viento_cfg = (vel, rnd.uniform(0, 360), self.indice >= 1)

    def _crucero(self, rnd):
        z0, z1 = ((50.0, 50.0), (35.0, 80.0), (80.0, 40.0))[self.indice % 3]
        a, b, _ = self._linea(rnd, rnd.uniform(400, 550), min(z0, z1) - 12)
        self.inicio = (*a, z0)
        self.meta = (*b, z1)
        self.radio_meta = 4.0
        self.viento_cfg = (rnd.uniform(3, 8), rnd.uniform(0, 360), self.indice == 2)

    def _aterrizaje(self, rnd):
        e = self._azotea(rnd)
        self.pad = e
        dx, dy = vector_rumbo(rnd.uniform(0, 360))
        off = (10, 18, 28)[self.indice % 3]
        cx, cy = e.centro
        self.inicio = (cx + dx * off, cy + dy * off, e.h + (20, 28, 35)[self.indice % 3])
        self.meta = (cx, cy, e.h)
        self.viento_cfg = (rnd.uniform(3, 8), rnd.uniform(0, 360), self.indice >= 1)

    def _esquivar(self, rnd):
        k = self.indice % 3
        if k == 2:
            a, b, (dx, dy) = self._linea(rnd, rnd.uniform(380, 480), 22, (55, 95))
            z = 40.0
        else:
            a, b, (dx, dy) = self._linea(rnd, rnd.uniform(380, 480), 30)
            z = 50.0
        self.inicio = (*a, z)
        self.meta = (*b, z)
        self.radio_meta = 4.0
        largo = math.hypot(b[0] - a[0], b[1] - a[1])
        if k == 0 or (k == 2 and not any(
                self.plan.mapa.altura_sensor(a[0] + dx * t, a[1] + dy * t) > z
                for t in range(0, int(largo), 5))):
            m = rnd.uniform(0.4, 0.6)
            self.obstaculos.append((a[0] + dx * largo * m, a[1] + dy * largo * m, 9.0, 100.0))
        elif k == 1:
            for m, lado in ((0.4, rnd.uniform(-4, 4)), (0.55, rnd.choice((-14, 14)))):
                gx, gy = a[0] + dx * largo * m, a[1] + dy * largo * m
                self.obstaculos.append((gx - dy * lado, gy + dx * lado, 7.0, 95.0))
            px, py = a[0] + dx * largo * 0.8, a[1] + dy * largo * 0.8
            rumbo = math.degrees(math.atan2(dx, -dy))
            self.aves_cruce = (px, py, z, rumbo, 0.8 * largo / 9)
        self.viento_cfg = (rnd.uniform(3, 7), rnd.uniform(0, 360), k == 1)

    def _entrega(self, rnd):
        lo, hi = ((700, 1000), (1000, 1400), (1300, 1800))[self.indice % 3]
        ruta = None
        for _ in range(40):
            a = self._azotea(rnd)
            b = self._azotea(rnd, a.centro, (lo, hi))
            if b is a:
                continue
            o = dict(nombre="cliente", tipo="plataforma", x=b.centro[0], y=b.centro[1], z=b.h,
                     es_destino=True)
            ruta = self.plan.ruta_auto(*a.centro, a.h + C.ALTURA_DESPEGUE, o,
                                       vehiculo=self.vehiculo)
            if not ruta.prohibida and ruta.longitud < hi * 1.4:
                break
        self.pad, self.origen, self.ruta = b, a, ruta
        self.inicio = (*a.centro, a.h)
        self.en_tierra = True
        self.meta = (b.centro[0], b.centro[1], b.h)
        self.t_max = 60 + ruta.longitud / 5
        self.viento_cfg = (rnd.uniform(3, 7), rnd.uniform(0, 360), self.indice >= 1)
        if self.indice % 3 >= 1:
            i = int(len(ruta.x) * 0.6)
            j = min(i + 1, len(ruta.x) - 1)
            rumbo = math.degrees(math.atan2(ruta.x[j] - ruta.x[i], -(ruta.y[j] - ruta.y[i])))
            self.aves_cruce = (ruta.x[i], ruta.y[i], ruta.alt[i], rumbo, 15 + ruta.s[i] / 11)
        if self.indice % 3 == 2:
            self.falla_motor = 0.45

    def ambiente(self):
        rnd = random.Random(self.semilla + 1)
        vel, dire, rafagas = self.viento_cfg
        viento = Viento(rnd, vel, dire, rafagas)
        aves = Aves(rnd, self.ciudad, activas=False)
        if self.aves_cruce:
            aves.cruce(*self.aves_cruce)
        entorno = Entorno(self.ciudad, self.plan.mapa, aves, viento, self.obstaculos)
        xs = [self.inicio[0], self.meta[0]] + (self.ruta.x if self.ruta else [])
        ys = [self.inicio[1], self.meta[1]] + (self.ruta.y if self.ruta else [])
        caja = (min(xs) - 80, min(ys) - 80, max(xs) + 80, max(ys) + 80)
        entorno.lineas_cerca = [l for l in self.ciudad.lineas
                                if not (max(l.x0, l.x1) < caja[0] or min(l.x0, l.x1) > caja[2]
                                        or max(l.y0, l.y1) < caja[1] or min(l.y0, l.y1) > caja[3])]
        entorno.antenas_cerca = [a for a in self.ciudad.antenas
                                 if caja[0] < a.x < caja[2] and caja[1] < a.y < caja[3]]
        entorno.caja = caja
        return entorno


class Alumno:

    def __init__(self, genoma, vehiculo):
        self.genoma = genoma
        self.cerebro = Cerebro(genoma)
        self.vehiculo = vehiculo
        self.puntajes = []
        self.dron = None

    def empezar(self, esc):
        self.esc = esc
        x, y, z = esc.inicio
        self.dron = Dron(x, y, z, 0.8, random.Random(1), 1.0, self.vehiculo)
        self.dron.en_tierra = False
        self.estado = VOLANDO
        self.t = 0.0
        self.t_meta = 0.0
        self.t_cerca = 0.0
        self.suma_cerca = 0.0
        self.d0 = math.dist(esc.inicio, esc.meta) if esc.leccion != "entrega" else esc.ruta.longitud
        self.dmin = self.d0
        self.idx = 0
        self.progreso = 0.0
        self.detalle = ""
        self.toque = None
        self.aterrizando = esc.leccion == "aterrizaje"
        self.motor_fallado = False
        self.subio = esc.leccion != "entrega"
        self.estela = [(x, y, z)]

    def objetivo(self):
        esc, d = self.esc, self.dron
        if esc.leccion != "entrega":
            return esc.meta, self.aterrizando
        r = esc.ruta
        x, y, z = d.pos
        if not self.subio:
            if z >= r.alt[0] - 2:
                self.subio = True
            return (r.x[0], r.y[0], r.alt[0]), False
        self.idx = r.proyectar(x, y, self.idx)
        s = r.s[self.idx]
        self.progreso = max(self.progreso, s / r.longitud)
        if r.longitud - s < 40 or self.aterrizando:
            self.aterrizando = True
            return esc.meta, True
        j = r.indice(s + 30)
        return (r.x[j], r.y[j], r.alt[j]), False

    def paso(self, entorno, dt):
        d = self.dron
        meta, aterrizar = self.objetivo()
        x, marco = sensores(d.pos, d.vel, d.pos, meta, aterrizar, entorno, d.viento_est)
        salida = self.cerebro.decidir(x)
        if esc_falla := self.esc.falla_motor:
            if not self.motor_fallado and self.progreso >= esc_falla:
                self.motor_fallado = True
                d.fallar_motor()
        v_max = d.spec["v_max"] if not d.es_avion else 26.0
        if self.motor_fallado and not d.es_avion:
            v_max = d.spec["v_degradado"]
        vx, vy, vz = velocidad_deseada(salida, marco, v_max,
                                       math.hypot(meta[0] - d.pos[0], meta[1] - d.pos[1]),
                                       meta[2] - d.pos[2])
        if d.es_avion:
            self._modo_avion(entorno, meta, aterrizar)
        ax, ay = 1.8 * (vx - d.vel[0]), 1.8 * (vy - d.vel[1])
        ah = math.hypot(ax, ay)
        a_max = 6.5 if d.modo == "ala" else C.A_MAX
        if ah > a_max:
            ax, ay = ax * a_max / ah, ay * a_max / ah
        az = max(-4.0, min(4.0, 2.5 * (vz - d.vel[2])))
        d.paso((ax, ay, az), entorno.viento.en(*d.pos), dt)
        self.t += dt
        self._revisar(entorno, meta, aterrizar, dt)

    def _modo_avion(self, entorno, meta, aterrizar):
        d = self.dron
        w = entorno.viento.en(*d.pos)
        va = math.hypot(d.vel[0] - w[0], d.vel[1] - w[1])
        lejos = math.hypot(meta[0] - d.pos[0], meta[1] - d.pos[1]) > 260
        if d.modo == "rotor" and va > d.spec["v_perdida"] + 1 and lejos and not aterrizar:
            d.cambiar_modo("ala")
        elif d.modo == "ala" and (not lejos or aterrizar or va < d.spec["v_perdida"] + 1):
            d.cambiar_modo("rotor")

    def _fin(self, estado, detalle):
        self.estado, self.detalle = estado, detalle

    def _revisar(self, entorno, meta, aterrizar, dt):
        d, esc, c = self.dron, self.esc, self.esc.ciudad
        x, y, z = d.pos
        if len(self.estela) < 2000 and int(self.t / dt) % 5 == 0:
            self.estela.append((x, y, z))
        dist = math.dist((x, y, z), meta)
        self.suma_cerca += dt / (1 + dist / (1.5 if aterrizar else 8))
        self.dmin = min(self.dmin, dist if esc.leccion != "entrega" or aterrizar else self.dmin)
        for ox, oy, r, h in entorno.obstaculos:
            if z < h and (x - ox) ** 2 + (y - oy) ** 2 < r * r:
                return self._fin(CHOQUE, "chocó con la grúa")
        for a in entorno.antenas_cerca:
            if z < a.h and math.hypot(x - a.x, y - a.y) < 2.5:
                return self._fin(CHOQUE, "chocó con una antena")
        for l in entorno.lineas_cerca:
            dh, s = l.cercania(x, y)
            if dh < 4.0 and abs(z - l.altura_cable(s)) < 1.2:
                return self._fin(CHOQUE, "se enredó en cables")
        if entorno.aves.parvadas:
            for _ in entorno.aves.cercanas(x, y, z, 1.5):
                return self._fin(CHOQUE, "chocó con un ave")
        if z > C.TECHO:
            return self._fin(CHOQUE, "rebasó el techo legal")
        if c.zona_prohibida(x, y):
            return self._fin(CHOQUE, "entró a zona prohibida")
        e = c.edificio_en(x, y)
        sup = e.h if e else 0.0
        if z < sup:
            if d.pos_prev[2] < sup - 0.3:
                return self._fin(CHOQUE, "chocó contra un edificio")
            vz = d.vel[2]
            d.pos[2] = sup
            err = math.hypot(x - meta[0], y - meta[1])
            if aterrizar and e is esc.pad and vz > -1.5:
                self.toque = (err, vz)
                if err <= 0.5:
                    return self._fin(EXITO, f"aterrizó a {err * 100:.0f} cm del centro")
                return self._fin(TIEMPO, f"aterrizó a {err:.1f} m del centro")
            if esc.en_tierra and self.t < 3 and e is not None and e is (esc.origen if esc.ruta
                                                                       else esc.pad):
                d.vel[2] = max(0.0, d.vel[2])
                return
            return self._fin(CHOQUE, "golpeó el suelo" if not e else "golpeó una azotea")
        if not aterrizar and esc.leccion != "entrega":
            if dist < 3 * esc.radio_meta and math.hypot(*d.vel) < 3.0:
                self.t_cerca += dt
            if dist < esc.radio_meta if esc.leccion != "entrega" else False:
                if math.hypot(*d.vel) < 1.5:
                    self.t_meta += dt
                    if self.t_meta >= 2.0:
                        return self._fin(EXITO, f"llegó en {self.t:.0f} s")
                else:
                    self.t_meta = 0.0
            else:
                self.t_meta = 0.0
        if self.t >= esc.t_max:
            return self._fin(TIEMPO, "se le acabó el tiempo")
        if dist > self.d0 * 2.5 + 150:
            return self._fin(TIEMPO, "se alejó demasiado")

    def calificar(self):
        esc = self.esc
        cerca = max(0.0, 1 - self.dmin / max(self.d0, 1.0))
        resto = esc.t_max - self.t if self.estado == EXITO else 0.0
        estancia = (self.suma_cerca + resto) / esc.t_max
        if esc.leccion in ("despegue", "crucero", "esquivar"):
            pts = 30 * cerca + 40 * estancia
            if self.estado == EXITO:
                pts += 20 + 10 * max(0.0, 1 - self.t / esc.t_max)
            if esc.leccion == "despegue":
                deriva = math.hypot(self.dron.pos[0] - esc.meta[0], self.dron.pos[1] - esc.meta[1])
                pts -= min(15.0, deriva)
        else:
            if esc.leccion == "entrega":
                pts = 40 * self.progreso + 20 * (cerca if self.aterrizando else 0)
            else:
                pts = 25 * cerca + 25 * estancia
            if self.toque:
                err, vz = self.toque
                pts += 20 * max(0.0, 1 - err / 2) + 15 * max(0.0, 1 - abs(vz) / 1.5)
                if self.estado == EXITO:
                    pts += 15 + 10 * max(0.0, 1 - self.t / esc.t_max)
        if self.estado == CHOQUE:
            pts -= 40
        self.puntajes.append((esc.nombre, pts, self.estado, self.detalle))
        return pts

    @property
    def aptitud(self):
        return sum(p[1] for p in self.puntajes)

    @property
    def aprobados(self):
        return sum(1 for p in self.puntajes if p[2] == EXITO)


class Generacion:

    def __init__(self, genomas, escenarios, vehiculo):
        self.alumnos = [Alumno(g, vehiculo) for g in genomas]
        self.escenarios = escenarios
        self.i_esc = -1
        self.terminada = False
        self._siguiente()

    @property
    def escenario(self):
        return self.escenarios[self.i_esc]

    def _siguiente(self):
        self.i_esc += 1
        if self.i_esc >= len(self.escenarios):
            self.terminada = True
            return
        self.entorno = self.escenario.ambiente()
        self.t = 0.0
        for a in self.alumnos:
            a.empezar(self.escenario)

    def paso(self):
        if self.terminada:
            return
        dt = C.DT_ESCUELA
        self.t += dt
        self.entorno.viento.actualizar(dt, self.t)
        self.entorno.aves.actualizar(dt, self.escenario.ciudad)
        activos = 0
        for a in self.alumnos:
            if a.estado == VOLANDO:
                a.paso(self.entorno, dt)
                activos += 1
                if a.estado != VOLANDO:
                    a.calificar()
        if activos == 0:
            self._siguiente()

    def correr(self):
        while not self.terminada:
            self.paso()

    def conteo(self):
        c = {EXITO: 0, CHOQUE: 0, TIEMPO: 0, VOLANDO: 0}
        for a in self.alumnos:
            c[a.estado] += 1
        return c


_TRABAJADOR = {}


def _iniciar_trabajador(zona_nombre, centro, vehiculo, tamano=1.0):
    from ciudad import Ciudad
    from geo import Zona
    from navegacion import Planificador
    ciudad = Ciudad(Zona(zona_nombre, centro, tamano), avisar=lambda *a: None)
    _TRABAJADOR.update(ciudad=ciudad, plan=Planificador(ciudad), vehiculo=vehiculo, esc={})


def _evaluar_lote(args):
    genomas, claves = args
    t = _TRABAJADOR
    escenarios = []
    for clave in claves:
        if clave not in t["esc"]:
            t["esc"][clave] = Escenario(clave[0], clave[1], t["ciudad"], t["plan"], t["vehiculo"])
        escenarios.append(t["esc"][clave])
    gen = Generacion(genomas, escenarios, t["vehiculo"])
    gen.correr()
    return [a.puntajes for a in gen.alumnos]


class Paralelo:

    def __init__(self, ciudad, vehiculo, procesos=None):
        import multiprocessing
        n = procesos or max(1, (os.cpu_count() or 2) - 1)
        z = ciudad.zona
        self.n = n
        self.pool = multiprocessing.Pool(n, _iniciar_trabajador, (z.nombre, z.centro, vehiculo,
                                                                    z.tamano))

    def evaluar(self, generacion):
        claves = [(e.leccion, e.indice) for e in generacion.escenarios]
        alumnos = generacion.alumnos
        tam = max(1, math.ceil(len(alumnos) / self.n))
        lotes = [alumnos[i:i + tam] for i in range(0, len(alumnos), tam)]
        resultados = self.pool.map(_evaluar_lote, [([a.genoma for a in l], claves) for l in lotes])
        for lote, res in zip(lotes, resultados):
            for a, puntajes in zip(lote, res):
                a.puntajes = puntajes
                a.estado = puntajes[-1][2] if puntajes else TIEMPO
        generacion.terminada = True

    def cerrar(self):
        self.pool.terminate()


def _recortar(g):
    return [max(-1.0, min(1.0, w)) for w in g]


class AlgoritmoGenetico:
    def __init__(self, tam=C.POBLACION):
        self.tam = tam
        self.sigma = C.SIGMA_MUTACION

    def _torneo(self, evaluados):
        return max(random.sample(evaluados, C.TORNEO), key=lambda e: e[0])[1]

    def _cruzar(self, a, b):
        if random.random() > C.PROB_CRUCE:
            return list(a)
        if random.random() < 0.5:
            corte = list(range(0, len(a), 27))
            hijo = []
            for i in corte:
                hijo.extend((a if random.random() < 0.5 else b)[i:i + 27])
            return hijo[:len(a)]
        alfa = random.random()
        return [alfa * x + (1 - alfa) * y for x, y in zip(a, b)]

    def _mutar(self, g):
        for i in range(len(g)):
            r = random.random()
            if r < C.PROB_MUTACION:
                g[i] += random.gauss(0, self.sigma)
            elif r < C.PROB_MUTACION + 0.005:
                g[i] = random.uniform(-1, 1)
        return _recortar(g)

    def siguiente(self, evaluados):
        evaluados = sorted(evaluados, key=lambda e: e[0], reverse=True)
        nuevos = [list(g) for _, g in evaluados[:C.ELITE]]
        for i in range(int(self.tam * C.FRACCION_AFINADOS)):
            base = evaluados[i % C.ELITE][1]
            nuevos.append(_recortar([w + random.gauss(0, C.SIGMA_AFINADO) for w in base]))
        n_frescos = int(self.tam * C.FRACCION_NUEVOS)
        while len(nuevos) < self.tam - n_frescos:
            nuevos.append(self._mutar(self._cruzar(self._torneo(evaluados),
                                                   self._torneo(evaluados))))
        while len(nuevos) < self.tam:
            nuevos.append(genoma_aleatorio())
        return nuevos


class Entrenador:

    def __init__(self, ciudad, plan, vehiculo=C.VEHICULO, tam=C.POBLACION, continuar=False):
        self.ciudad, self.plan, self.vehiculo = ciudad, plan, vehiculo
        self.ag = AlgoritmoGenetico(tam)
        self.num = 1
        self.nivel = 1
        self.historial = []
        self.record = None
        self.mensajes = []
        self.extinciones = 0
        self._seguidas = 0
        self._sin_mejora = 0
        self._atascado = 0
        self._mejor = float("-inf")
        self._referencia = float("-inf")
        self._cache_escenarios = {}

        genomas = [genoma_aleatorio() for _ in range(tam)]
        guardado = cargar_mejor(vehiculo)
        if guardado and guardado.get("version") != VERSION_CURSO:
            guardado = dict(guardado, clave=[0, 0, float("-inf")])
        self._guardado = guardado
        progreso = cargar_progreso(vehiculo) if continuar else None
        if progreso:
            genomas = self._restaurar(progreso, tam)
        elif continuar and guardado:
            self.record = guardado if guardado.get("version") == VERSION_CURSO else None
            self.nivel = guardado.get("nivel", 1)
            self.num = guardado.get("generacion", 0) + 1
            base = guardado["genoma"]
            genomas = [list(base)] + [self.ag._mutar(list(base)) for _ in range(tam // 2)]
            genomas += [genoma_aleatorio() for _ in range(tam - len(genomas))]
        self.generacion = Generacion(genomas, self.escenarios(), vehiculo)
        if progreso and os.path.exists(ARCHIVO_HISTORIAL):
            return
        with open(ARCHIVO_HISTORIAL, "w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(["generacion", "nivel", "leccion_nueva", "mejor_aptitud",
                                    "aptitud_promedio", "mejor_aprobados", "escenarios",
                                    "chocaron", "sigma", "extincion"])

    def _restaurar(self, p, tam):
        self.num = p["num"]
        self.nivel = min(p["nivel"], len(C.CURSO))
        self.historial = p.get("historial", [])
        self.record = p.get("record")
        self.extinciones = p.get("extinciones", 0)
        self._seguidas = p.get("seguidas", 0)
        self._sin_mejora = p.get("sin_mejora", 0)
        self._atascado = p.get("atascado", 0)
        self._mejor = p.get("mejor", float("-inf"))
        self._referencia = p.get("referencia", float("-inf"))
        self.ag.sigma = p.get("sigma", self.ag.sigma)
        genomas = [list(g) for g in p["genomas"] if len(g) == TAM_GENOMA][:tam]
        return genomas + [genoma_aleatorio() for _ in range(tam - len(genomas))]

    def guardar_progreso(self):
        datos = dict(version=VERSION_CURSO, tam_genoma=TAM_GENOMA, num=self.num,
                     nivel=self.nivel, sigma=self.ag.sigma, extinciones=self.extinciones,
                     seguidas=self._seguidas, sin_mejora=self._sin_mejora,
                     atascado=self._atascado, mejor=self._mejor, referencia=self._referencia,
                     record=self.record, historial=self.historial[-2000:],
                     genomas=[a.genoma for a in self.generacion.alumnos])
        archivo = archivo_progreso(self.vehiculo)
        with open(archivo + ".tmp", "w", encoding="utf-8") as f:
            json.dump(datos, f, ensure_ascii=False)
        os.replace(archivo + ".tmp", archivo)

    @property
    def lecciones(self):
        return C.CURSO[:self.nivel]

    @property
    def graduado(self):
        return bool(self.record and self.record.get("graduado"))

    def escenarios(self):
        res = []
        for lec in self.lecciones:
            for k in range(C.ESCENARIOS_POR_LECCION):
                clave = (lec, k)
                if clave not in self._cache_escenarios:
                    self._cache_escenarios[clave] = Escenario(lec, k, self.ciudad, self.plan,
                                                              self.vehiculo)
                res.append(self._cache_escenarios[clave])
        return res

    def cerrar_generacion(self):
        alumnos = self.generacion.alumnos
        evaluados = [(a.aptitud, a.genoma) for a in alumnos]
        mejor = max(alumnos, key=lambda a: (a.aprobados, a.aptitud))
        total = len(self.generacion.escenarios)
        choques = sum(1 for a in alumnos for p in a.puntajes if p[2] == CHOQUE)
        stats = dict(generacion=self.num, nivel=self.nivel,
                     leccion=NOMBRE_LECCION[self.lecciones[-1]],
                     mejor=max(e[0] for e in evaluados),
                     promedio=sum(e[0] for e in evaluados) / len(evaluados),
                     aprobados=mejor.aprobados, escenarios=total,
                     chocaron=choques / len(alumnos), sigma=self.ag.sigma, extincion=False,
                     subio=None)
        if mejor.aptitud > self._mejor + 1e-6:
            self._mejor = mejor.aptitud
            self._sin_mejora = 0
            self.ag.sigma = max(0.06, self.ag.sigma * 0.95)
        else:
            self._sin_mejora += 1
            if self._sin_mejora >= C.ESTANCAMIENTO:
                self.ag.sigma = min(0.8, self.ag.sigma * 1.4)
                self._sin_mejora = 0
        self._registrar(mejor, total)
        if mejor.aprobados == total:
            self._seguidas += 1
        else:
            self._seguidas = 0
        nuevos = None
        if self._seguidas >= C.APROBAR_SEGUIDAS:
            self._seguidas = 0
            if self.nivel < len(C.CURSO):
                self.nivel += 1
                stats["subio"] = NOMBRE_LECCION[self.lecciones[-1]]
                self._mejor = self._referencia = float("-inf")
                self._atascado = 0
                self.ag.sigma = C.SIGMA_MUTACION * 0.6
        if mejor.aptitud > self._referencia + C.MEJORA_NOTABLE:
            self._referencia = mejor.aptitud
            self._atascado = 0
        else:
            self._atascado += 1
        if self.nivel == 1 and self._atascado >= C.EXTINCION:
            stats["extincion"] = True
            self.extinciones += 1
            self._atascado = 0
            self.ag.sigma = C.SIGMA_MUTACION
            self._mejor = self._referencia = float("-inf")
            nuevos = [genoma_aleatorio() for _ in range(self.ag.tam)]
        if nuevos is None:
            nuevos = self.ag.siguiente(evaluados)
        self.historial.append(stats)
        with open(ARCHIVO_HISTORIAL, "a", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow([stats["generacion"], stats["nivel"], stats["subio"] or "",
                                    round(stats["mejor"], 1), round(stats["promedio"], 1),
                                    stats["aprobados"], total, round(stats["chocaron"], 2),
                                    round(stats["sigma"], 3), "sí" if stats["extincion"] else ""])
        self.num += 1
        self.generacion = Generacion(nuevos, self.escenarios(), self.vehiculo)
        self.guardar_progreso()
        return stats

    def _puntaje_record(self, nivel, aprobados, total, aptitud):
        return (nivel, aprobados / total, aptitud / total)

    def _registrar(self, alumno, total):
        clave = self._puntaje_record(self.nivel, alumno.aprobados, total, alumno.aptitud)
        previo = self.record
        if previo and tuple(previo["clave"]) >= clave:
            return
        graduado = self.nivel == len(C.CURSO) and alumno.aprobados == total
        self.record = dict(
            clave=list(clave), generacion=self.num, nivel=self.nivel,
            leccion=NOMBRE_LECCION[self.lecciones[-1]], aprobados=alumno.aprobados,
            escenarios=total, aptitud=round(alumno.aptitud, 1), graduado=graduado,
            vehiculo=self.vehiculo, tam_genoma=TAM_GENOMA,
            resultados=[f"{n}: {e} ({d}) {p:.0f} pts" for n, p, e, d in alumno.puntajes],
            genoma=alumno.genoma, version=VERSION_CURSO)
        g = self._guardado
        if not g or tuple(g.get("clave", (0, 0, 0))) < clave:
            self._guardado = self.record
            guardar_mejor(self.record, self.vehiculo)


def guardar_mejor(record, vehiculo):
    with open(archivo_mejor(vehiculo), "w", encoding="utf-8") as f:
        json.dump(record, f, ensure_ascii=False)


def cargar_mejor(vehiculo):
    archivo = archivo_mejor(vehiculo)
    if not os.path.exists(archivo):
        return None
    with open(archivo, encoding="utf-8") as f:
        datos = json.load(f)
    if datos.get("tam_genoma") != TAM_GENOMA:
        return None
    return datos


def cargar_progreso(vehiculo):
    try:
        with open(archivo_progreso(vehiculo), encoding="utf-8") as f:
            datos = json.load(f)
    except (OSError, ValueError):
        return None
    if datos.get("tam_genoma") != TAM_GENOMA or datos.get("version") != VERSION_CURSO:
        return None
    return datos


def borrar_progreso(vehiculo):
    try:
        os.remove(archivo_progreso(vehiculo))
    except OSError:
        pass


def resumen_generacion(s):
    extra = ""
    if s["subio"]:
        extra = f"  << ¡APROBÓ! Nueva lección: {s['subio']}"
    elif s["extincion"]:
        extra = "  << EXTINCIÓN: población renovada"
    return (f"Gen {s['generacion']:4d} | nivel {s['nivel']} ({s['leccion']}) | "
            f"mejor {s['mejor']:7.1f} | prom {s['promedio']:7.1f} | "
            f"aprobó {s['aprobados']}/{s['escenarios']} | choques/alumno "
            f"{s['chocaron']:.1f}{extra}")
