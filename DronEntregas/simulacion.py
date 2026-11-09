import math
import random

import config as C
from ambiente import Aves, Viento
from cerebro import Cerebro, Entorno
from dron import Dron
from piloto import Piloto

EVENTOS = ("gps", "motor", "bateria")
NOMBRE_EVENTO = {"gps": "pérdida de GPS", "motor": "falla de motor", "bateria": "batería baja"}


class Mision:
    def __init__(self, ciudad, plan, origen, destino, ruta, viento=C.VIENTO,
                 direccion=C.VIENTO_DIRECCION, rafagas=C.RAFAGAS, aves=C.AVES,
                 eventos=(), semilla=None, bateria=1.0, vehiculo=C.VEHICULO,
                 piloto_ia=False):
        self.rnd = random.Random(semilla)
        self.ciudad, self.plan = ciudad, plan
        self.origen, self.destino = origen, destino
        self.ruta = ruta
        self.t = 0.0
        self.registro = []
        self.nuevos = []
        self.terminada = False
        self.resultado = None
        self.dron = Dron(origen.x, origen.y, origen.h, origen.masa, self.rnd, bateria,
                         vehiculo)
        self.viento = Viento(self.rnd, viento, direccion, rafagas)
        self.aves = Aves(self.rnd, ciudad, aves)
        self.estela = [(origen.x, origen.y)]
        self.traza = [(origen.x, origen.y, origen.h)]
        self.rutas_previas = []
        self.perfil_real = []
        self.distancia = 0.0
        self.infracciones = 0
        self._en_zona = None
        self._t_estela = 0.0
        self._t_zona = 0.0
        self.version_ruta = 0
        self.entorno = Entorno(ciudad, plan.mapa, self.aves, self.viento)
        self.cerebro, self.info_cerebro = None, None
        if piloto_ia:
            from escuela import cargar_mejor
            rec = cargar_mejor(vehiculo)
            if rec:
                self.cerebro, self.info_cerebro = Cerebro(rec["genoma"]), rec
        self.piloto = Piloto(self)
        self.programados = []
        dur = ruta.t[-1] + 20
        rangos = {"gps": (0.25, 0.45), "motor": (0.40, 0.65), "bateria": (0.45, 0.70)}
        for e in eventos:
            self.programados.append([dur * self.rnd.uniform(*rangos[e]), e])
        self.t_gps_vuelve = None
        self.cruces = []
        if aves:
            n = len(ruta.x)
            self.cruces = sorted(int(n * self.rnd.uniform(0.15, 0.85))
                                 for _ in range(C.PARVADAS_EN_RUTA))
        self.log(f"Misión: {origen.nombre} → {destino.nombre} en "
                 f"{self.dron.spec['nombre'].lower()} · {ruta.nombre} de "
                 f"{ruta.longitud / 1000:.2f} km (≈{ruta.t[-1] / 60:.1f} min).")
        if piloto_ia and self.cerebro is None:
            self.log("No hay cerebro entrenado para este vehículo: vuela el piloto clásico. "
                     "Entrénalo en la Escuela de vuelo.", "aviso")
        elif self.cerebro is not None:
            r = self.info_cerebro
            self.log(f"Piloto IA: cerebro de la generación {r['generacion']} (nivel {r['nivel']}: "
                     f"{r['leccion']}, aprobó {r['aprobados']}/{r['escenarios']} pruebas"
                     + (", graduado" if r.get("graduado") else "") + ").", "decision")
        if eventos:
            self.log("Fallas programadas: " + ", ".join(NOMBRE_EVENTO[e] for e in eventos)
                     + " (en un momento al azar del vuelo).", "aviso")

    def log(self, texto, nivel="info"):
        self.registro.append((self.t, texto, nivel))
        self.nuevos.append((self.t, texto, nivel))

    def nueva_ruta(self, ruta):
        if self.ruta is not None:
            self.rutas_previas.append(self.ruta)
        self.ruta = ruta
        self.perfil_real = []
        self.version_ruta += 1

    def provocar(self, evento):
        d, p = self.dron, self.piloto
        if self.terminada or d.en_tierra:
            return
        if evento == "gps":
            if d.gps_ok:
                d.perder_gps()
                self.t_gps_vuelve = self.t + self.rnd.uniform(*C.GPS_DURACION)
                p.gps_perdido()
            else:
                self.t_gps_vuelve = None
                d.recuperar_gps()
                p.gps_recuperado()
        elif evento == "motor":
            self.falla_motor()
        elif evento == "bateria":
            justa = p.energia_necesaria(peor=True) * 1.1 + 0.5 * C.RESERVA * d.capacidad
            nivel = max(C.BATERIA_FALLA * d.capacidad, justa)
            if nivel >= d.bateria_wh:
                nivel = d.bateria_wh * 0.85
            d.bateria_wh = nivel
            p.bateria_falla()
        elif evento == "rafaga":
            self.viento.iniciar_rafaga(C.RAFAGA_MAX * 1.3)
            self.log(f"Ráfaga fuerte de {C.RAFAGA_MAX * 1.3:.0f} m/s.", "aviso")

    def falla_motor(self, causa=""):
        d = self.dron
        if d.fallas() >= C.MAX_FALLAS_MOTOR:
            self.log(f"{causa}El dron ya tiene una falla de motor; su redundancia cubre sólo "
                     "una, así que el simulador no provoca otra.", "aviso")
            return
        cual = d.fallar_motor()
        if cual is not None:
            self.piloto.motor_fallado(cual)

    def paso(self):
        if self.terminada:
            return
        dt = C.DT
        self.t += dt
        d, p = self.dron, self.piloto
        self.viento.actualizar(dt, self.t)
        self.aves.actualizar(dt, self.ciudad)
        if not d.en_tierra:
            self._eventos()
        d.actualizar_estimador(dt, self.ciudad, p.objetivo)
        a = p.paso(dt)
        d.paso(a, self.viento.en(*d.pos), dt)
        if d.apagado and p.fase not in ("paracaidas", "en_tierra", "accidente"):
            p._cambiar("paracaidas")
            self.log("¡Batería agotada! Motores apagados: se despliega el paracaídas.",
                     "peligro")
        if not d.en_tierra:
            self.distancia += math.hypot(d.pos[0] - d.pos_prev[0], d.pos[1] - d.pos_prev[1])
            self._contacto()
            self._vigilar_zonas(dt)
        self._t_estela += dt
        if self._t_estela >= 1.0:
            self._t_estela = 0.0
            self.estela.append((d.pos[0], d.pos[1]))
            self.traza.append(tuple(d.pos))
            if self.ruta is not None and p.fase in ("ruta", "despegue"):
                self.perfil_real.append((self.ruta.s[p.idx], d.pos[2]))
        if self.t > C.TIEMPO_MAX and not self.terminada:
            self._terminar(False, "Se agotó el tiempo máximo de simulación.")

    def _eventos(self):
        d, p = self.dron, self.piloto
        t_vuelo = self.t
        for ev in self.programados:
            if ev[0] is not None and t_vuelo >= ev[0] and p.fase not in ("plataforma",):
                ev[0] = None
                if ev[1] == "gps" and not d.gps_ok:
                    continue
                self.provocar(ev[1])
        if self.t_gps_vuelve is not None and self.t >= self.t_gps_vuelve:
            self.t_gps_vuelve = None
            d.recuperar_gps()
            p.gps_recuperado()
        if self.cruces and self.ruta is not None and p.fase == "ruta":
            i = self.cruces[0]
            r = self.ruta
            if i < len(r.x):
                faltan = r.s[i] - r.s[p.idx]
                if faltan < 0:
                    self.cruces.pop(0)
                elif faltan < 18 * max(4.0, math.hypot(d.vel[0], d.vel[1])):
                    self.cruces.pop(0)
                    seg = faltan / max(4.0, math.hypot(d.vel[0], d.vel[1]))
                    j = min(i + 1, len(r.x) - 1)
                    rumbo = math.degrees(math.atan2(r.x[j] - r.x[i], -(r.y[j] - r.y[i])))
                    self.aves.cruce(r.x[i], r.y[i], r.alt[i] + self.rnd.uniform(-3, 3),
                                    rumbo, seg)
            else:
                self.cruces.pop(0)

    def _vigilar_zonas(self, dt):
        self._t_zona -= dt
        if self._t_zona > 0:
            return
        self._t_zona = 0.5
        x, y, _ = self.dron.pos
        z = self.ciudad.zona_prohibida(x, y)
        if z is not None and self._en_zona is None:
            self.infracciones += 1
            self.log(f"¡Entró a zona prohibida: {z.nombre}!", "peligro")
        self._en_zona = z

    def _contacto(self):
        d, p, ciudad = self.dron, self.piloto, self.ciudad
        x, y, z = d.pos
        for par, k, (bx, by, bz) in self.aves.cercanas(x, y, z, 1.6):
            par.activas[k] = False
            if self.rnd.random() < 0.6 and d.fallas() < C.MAX_FALLAS_MOTOR:
                self.log("¡Choque con un ave! Dañó una hélice.", "peligro")
                self.falla_motor()
            else:
                self.log("Choque con un ave sin daños graves.", "aviso")
        for a in ciudad.antenas:
            if z < a.h and math.hypot(x - a.x, y - a.y) < 2.5:
                return self._accidente(f"Chocó contra una antena de {a.h:.0f} m.")
        for l in ciudad.lineas:
            dh, s = l.cercania(x, y)
            if dh < 4.0 and abs(z - l.altura_cable(s)) < 1.2:
                return self._accidente(f"Se enredó en los cables de la {l.nombre}.")
            if z < l.altura + 3 and any(math.hypot(x - tx, y - ty) < 5 for tx, ty in l.torres):
                return self._accidente(f"Chocó contra una torre de la {l.nombre}.")
        sup = ciudad.altura_superficie(x, y)
        if z >= sup:
            return
        if p.fase == "despegue" and d.pos_prev[2] >= sup - 0.01:
            d.pos[2] = sup
            d.vel[2] = max(0.0, d.vel[2])
            return
        e = ciudad.edificio_en(x, y)
        if sup > 0 and d.pos_prev[2] < sup - 0.3:
            nombre = e.nombre or "un edificio"
            return self._accidente(f"Chocó contra la fachada de {nombre} ({e.h:.0f} m).")
        vz = d.vel[2]
        vh = math.hypot(d.vel[0], d.vel[1])
        d.pos[2] = sup
        d.vel = [0.0, 0.0, 0.0]
        d.en_tierra = True
        calle = ciudad.calle_cercana(x, y, 30.0)
        if calle and calle.split()[0] not in ("Calle", "Avenida", "Calzada", "Boulevard",
                                              "Privada", "Prolongación", "Paseo"):
            calle = "la calle " + calle
        lugar = (e.nombre or "una azotea") if e else (calle or "el suelo")
        if d.paracaidas:
            return self._terminar(False, f"Aterrizó con paracaídas en {lugar} a "
                                         f"{-vz:.1f} m/s.", emergencia=True)
        if p.fase != "descenso" or -vz > 2.5 or vh > 2.0:
            return self._accidente(f"Golpeó {lugar} a {-vz:.1f} m/s.")
        o = p.objetivo
        err = math.hypot(x - o["x"], y - o["y"])
        self.error_final = err
        self._terminar(True, f"¡Entrega completada en {o['nombre']}! Aterrizó a "
                             f"{err * 100:.0f} cm del centro de la plataforma, a "
                             f"{-vz:.2f} m/s.", error=err)

    def _accidente(self, texto):
        d = self.dron
        d.vel = [0.0, 0.0, 0.0]
        d.en_tierra = True
        d.apagado = True
        self.piloto._cambiar("accidente")
        self._terminar(False, texto, accidente=True)

    def _terminar(self, exito, texto, error=None, emergencia=False, accidente=False):
        if self.terminada:
            return
        self.terminada = True
        self.traza.append(tuple(self.dron.pos))
        if self.piloto.fase != "accidente":
            self.piloto._cambiar("en_tierra")
        d = self.dron
        self.resultado = dict(
            exito=exito, texto=texto, accidente=accidente, emergencia=emergencia,
            tiempo=self.t, distancia=self.distancia, energia=d.energia_usada,
            bateria=d.soc * 100, error_cm=None if error is None else error * 100,
            decisiones=len(self.piloto.decisiones), infracciones=self.infracciones)
        nivel = "exito" if exito else ("peligro" if accidente else "aviso")
        self.log(texto, nivel)

    def correr(self, max_pasos=None):
        n = 0
        while not self.terminada and (max_pasos is None or n < max_pasos):
            self.paso()
            n += 1

    def resumen(self):
        r = self.resultado
        if not r:
            return "Misión en curso."
        lineas = [r["texto"],
                  f"Tiempo de vuelo: {r['tiempo'] / 60:.1f} min · recorrido "
                  f"{r['distancia'] / 1000:.2f} km · energía {r['energia']:.0f} Wh · "
                  f"batería final {r['bateria']:.0f} %"]
        if r["error_cm"] is not None:
            lineas.append(f"Precisión del aterrizaje: {r['error_cm']:.0f} cm")
        lineas.append(f"Decisiones ante fallas: {r['decisiones']} · "
                      f"invasiones de zona prohibida: {r['infracciones']}")
        return "\n".join(lineas)
