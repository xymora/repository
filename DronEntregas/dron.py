import math

import config as C

G = C.G


def arrastre(vx, vy, vz, cda):
    v = math.sqrt(vx * vx + vy * vy + vz * vz)
    k = -0.5 * C.RHO * cda * v
    return k * vx, k * vy, k * vz


class Dron:
    def __init__(self, x, y, z, carga_kg, rnd, bateria=1.0, vehiculo=C.VEHICULO):
        self.rnd = rnd
        self.tipo = vehiculo
        self.spec = C.VEHICULOS[vehiculo]
        self.es_avion = vehiculo == "avion"
        self.pos = [x, y, z]
        self.pos_prev = [x, y, z]
        self.vel = [0.0, 0.0, 0.0]
        self.masa = self.spec["masa"] + carga_kg
        self.carga = carga_kg
        self.motores = [1.0] * self.spec["motores"]
        self.empuje_ok = True
        self.modo = "rotor"
        self.capacidad = self.spec["bateria_wh"]
        self.bateria_wh = self.capacidad * bateria
        self.potencia = C.CONSUMO_AVIONICA
        self.empuje = 0.0
        self.voltaje = self._voltaje(0.0)
        self.viento_est = [0.0, 0.0, 0.0]
        self.en_tierra = True
        self.paracaidas = False
        self.apagado = False
        self.rumbo = 0.0
        self.alabeo = 0.0
        self.sacudida = 0.0
        self.energia_usada = 0.0
        self.gps_ok = True
        self.t_sin_gps = 0.0
        self.t_fix = 0.0
        self.fix_visual = None
        self.err = [0.0, 0.0]
        self.deriva = [0.0, 0.0]
        self.incert = 1.5
        self.vision = False
        self.degradado = False
        self.sats = 14
        self._sesgo = None
        self.est = [x, y, z]

    @property
    def soc(self):
        return max(0.0, self.bateria_wh / self.capacidad)

    def fallas(self):
        return sum(1 for m in self.motores if m < 0.5) + (0 if self.empuje_ok else 1)

    def rotores_fallados(self):
        return sum(1 for m in self.motores if m < 0.5)

    def factor_empuje(self):
        n = self.spec["motores"]
        sanos = n - self.rotores_fallados()
        return (sanos / n) * (0.8 if sanos < n else 1.0)

    def empuje_max(self):
        if self.apagado:
            return 0.0
        return self.spec["empuje_motor"] * self.spec["motores"] * self.factor_empuje()

    def relacion_empuje(self):
        return self.empuje_max() / (self.masa * G)

    def energia_disponible(self):
        return self.bateria_wh - C.RESERVA * self.capacidad

    def arrastre_ala(self, v):
        s = self.spec
        q = max(0.5 * C.RHO * v * v, 1.0)
        W = self.masa * G
        return q * s["ala"] * s["cd0"] + W * W / (q * s["ala"] * math.pi * s["oswald"] *
                                                  s["alargamiento"])

    def potencia_modelo(self, T, v_aire_h, vz):
        sanos = max(1, self.spec["motores"] - self.rotores_fallados())
        area = sanos * math.pi * (self.spec["helice"] / 2) ** 2
        T = max(T, 1.0)
        vh = math.sqrt(T / (2 * C.RHO * area))
        mu = v_aire_h / vh
        vi = vh * math.sqrt(-0.5 * mu * mu + math.sqrt(0.25 * mu ** 4 + 1))
        p = (T * (vi + max(vz, 0.0)) + 0.5 * C.RHO * self.spec["cda"] * v_aire_h ** 3) \
            / C.EFICIENCIA
        if self.rotores_fallados():
            p *= 1.12
        return p + C.CONSUMO_AVIONICA

    def potencia_ala(self, v, vz=0.0):
        return ((self.arrastre_ala(v) * v + self.masa * G * max(vz, 0.0)) / C.EFICIENCIA
                + C.CONSUMO_AVIONICA)

    def potencia_crucero(self, v):
        if self.es_avion and self.empuje_ok and v >= self.spec["v_perdida"]:
            return self.potencia_ala(v)
        return self.potencia_modelo(self.masa * G * 1.02, v, 0.0)

    def _voltaje(self, potencia):
        v0 = C.CELDAS * (3.45 + 0.75 * self.soc)
        corriente = potencia / max(v0, 1.0)
        return v0 - corriente * C.RESISTENCIA_BATERIA

    def fallar_motor(self):
        if self.es_avion and self.empuje_ok and self.modo == "ala":
            self.empuje_ok = False
            return "empuje"
        sanos = [i for i, m in enumerate(self.motores) if m >= 0.5]
        if not sanos:
            return None
        i = self.rnd.choice(sanos)
        self.motores[i] = 0.0
        self.sacudida = 0.8
        return i

    def cambiar_modo(self, modo):
        if modo == self.modo:
            return
        self.modo = modo

    def desplegar_paracaidas(self):
        self.paracaidas = True
        self.apagado = True

    def perder_gps(self):
        if self.gps_ok:
            self.gps_ok = False
            self.t_sin_gps = 0.0
            self.t_fix = 0.0
            self.deriva = [self.rnd.gauss(0, 0.12), self.rnd.gauss(0, 0.12)]

    def recuperar_gps(self):
        if not self.gps_ok:
            self.gps_ok = True
            self.err = [self.rnd.gauss(0, 1.0), self.rnd.gauss(0, 1.0)]

    def paso(self, a_cmd, viento, dt):
        self.pos_prev = list(self.pos)
        if self.en_tierra:
            self.potencia = C.CONSUMO_AVIONICA
            self._gastar(dt)
            return
        if self.modo == "ala" and not self.apagado:
            self._paso_ala(a_cmd, viento, dt)
        else:
            self._paso_rotor(a_cmd, viento, dt)
        self._gastar(dt)
        k = min(1.0, dt / 1.5)
        self.viento_est = [self.viento_est[i] + (viento[i] - self.viento_est[i]) * k
                           for i in range(3)]
        if self.modo == "ala":
            va = (self.vel[0] - viento[0], self.vel[1] - viento[1])
            if math.hypot(*va) > 1.0:
                self.rumbo = math.degrees(math.atan2(va[0], -va[1])) % 360
        elif math.hypot(self.vel[0], self.vel[1]) > 1.0:
            self.rumbo = math.degrees(math.atan2(self.vel[0], -self.vel[1])) % 360

    def _paso_rotor(self, a_cmd, viento, dt):
        m = self.masa
        vx, vy, vz = self.vel
        cda = self.spec["cda"]
        if self.apagado:
            T = (0.0, 0.0, 0.0)
            cda = C.PARACAIDAS_CDA if self.paracaidas else cda
        else:
            we = self.viento_est
            dex, dey, dez = arrastre(vx - we[0], vy - we[1], vz - we[2], cda)
            tx = m * a_cmd[0] - dex
            ty = m * a_cmd[1] - dey
            tz = m * (a_cmd[2] + G) - dez
            tmax = self.empuje_max()
            tz = max(0.0, min(tz, tmax))
            th = math.hypot(tx, ty)
            lim = min(tz * math.tan(C.INCLINACION_MAX), math.sqrt(max(tmax * tmax - tz * tz, 0.0)))
            if th > lim and th > 0:
                tx, ty = tx * lim / th, ty * lim / th
            T = (tx, ty, tz)
        wx, wy, wz = viento
        dx, dy, dz = arrastre(vx - wx, vy - wy, vz - wz, cda)
        ax = (T[0] + dx) / m
        ay = (T[1] + dy) / m
        az = (T[2] + dz) / m - G
        if self.sacudida > 0:
            self.sacudida -= dt
            ax += self.rnd.gauss(0, 4.0)
            ay += self.rnd.gauss(0, 4.0)
            az -= 5.0
        self.vel = [vx + ax * dt, vy + ay * dt, vz + az * dt]
        self.pos = [self.pos[i] + self.vel[i] * dt for i in range(3)]
        self.empuje = math.sqrt(T[0] ** 2 + T[1] ** 2 + T[2] ** 2)
        self.alabeo = 0.0
        v_aire_h = math.hypot(self.vel[0] - wx, self.vel[1] - wy)
        self.potencia = (self.potencia_modelo(self.empuje, v_aire_h, self.vel[2])
                         if not self.apagado else C.CONSUMO_AVIONICA)

    def _paso_ala(self, a_cmd, viento, dt):
        s, m = self.spec, self.masa
        wx, wy, wz = viento
        va = [self.vel[0] - wx, self.vel[1] - wy, self.vel[2] - wz]
        v = max(math.hypot(va[0], va[1]), 0.1)
        ux, uy = va[0] / v, va[1] / v
        a_par = a_cmd[0] * ux + a_cmd[1] * uy
        lx, ly = a_cmd[0] - a_par * ux, a_cmd[1] - a_par * uy
        D = self.arrastre_ala(v)
        tmax = s["empuje_avance"] if self.empuje_ok else 0.0
        T = max(0.0, min(m * a_par + D, tmax))
        a_par = (T - D) / m
        lat = math.hypot(lx, ly)
        lim = G * math.tan(s["inclinacion_ala"])
        if lat > lim:
            lx, ly = lx * lim / lat, ly * lim / lat
        self.alabeo = math.degrees(math.atan2(lx * uy - ly * ux, G))
        exceso = (tmax - D) * v / (m * G)
        az = max(-4.0, min(a_cmd[2], 3.0))
        if va[2] > exceso and az > 0:
            az = min(az, 0.0)
        sust = min(1.0, (v / s["v_perdida"]) ** 2)
        az -= G * (1 - sust)
        va = [va[0] + (a_par * ux + lx) * dt, va[1] + (a_par * uy + ly) * dt, va[2] + az * dt]
        self.vel = [va[0] + wx, va[1] + wy, va[2] + wz]
        self.pos = [self.pos[i] + self.vel[i] * dt for i in range(3)]
        self.empuje = T
        self.potencia = ((T * v + m * G * max(va[2], 0.0)) / C.EFICIENCIA
                         + C.CONSUMO_AVIONICA)

    def _gastar(self, dt):
        e = self.potencia * dt / 3600
        self.bateria_wh -= e
        self.energia_usada += e
        self.voltaje = self._voltaje(self.potencia)
        if self.bateria_wh <= 0 and not self.apagado:
            self.bateria_wh = 0.0
            if not self.en_tierra:
                self.desplegar_paracaidas()

    def actualizar_estimador(self, dt, ciudad, objetivo):
        x, y, z = self.pos
        self.vision = False
        if objetivo is not None:
            dh = math.hypot(x - objetivo["x"], y - objetivo["y"])
            if dh < 25 and z - objetivo["z"] < 45:
                self.vision = True
        self.degradado = any(e.h > z + 5 for e in ciudad.edificios_cerca(x, y, 40))
        r = self.rnd
        if self.vision:
            obj = 0.06
            if not self._sesgo or self._sesgo[2] != objetivo["nombre"]:
                self._sesgo = [r.gauss(0, obj), r.gauss(0, obj), objetivo["nombre"]]
            self._sesgo[0] += r.gauss(0, 0.2 * obj) * math.sqrt(dt)
            self._sesgo[1] += r.gauss(0, 0.2 * obj) * math.sqrt(dt)
            k = min(1.0, dt / 0.5)
            self.err = [e + (b - e) * k for e, b in zip(self.err, self._sesgo)]
            self.incert = obj * 2
        elif self.gps_ok:
            f = 2.5 if self.degradado else 1.0
            k = math.exp(-dt / 5.0)
            self.err = [e * k + r.gauss(0, 0.35 * f) * math.sqrt(dt) for e in self.err]
            lim = 3.0 * f
            self.err = [max(-lim, min(lim, e)) for e in self.err]
            self.incert = 1.5 * f
            if r.random() < dt / 3:
                self.sats = max(5, min(18, (7 if self.degradado else 14) + r.randint(-1, 2)))
        else:
            self.t_sin_gps += dt
            self.t_fix += dt
            self.deriva = [max(-0.6, min(0.6, d + r.gauss(0, 0.02) * math.sqrt(dt)))
                           for d in self.deriva]
            self.err = [e + d * dt for e, d in zip(self.err, self.deriva)]
            t = self.t_fix
            self.incert = 2.0 + 0.3 * t + 0.004 * t * t
            self.sats = 0
            if self.t_sin_gps > 8 and self.t_fix >= C.FIX_VISUAL_CADA:
                antes = math.hypot(*self.err)
                self.err = [r.gauss(0, 1.5), r.gauss(0, 1.5)]
                self.t_fix = 0.0
                self.incert = 4.0
                self.fix_visual = (antes, math.hypot(*self.err))
        self.est = [x + self.err[0], y + self.err[1], z + r.gauss(0, 0.05)]

    def estado_gps(self):
        if self.vision:
            return "VISIÓN" if self.gps_ok else "SIN GPS · VISIÓN"
        if not self.gps_ok:
            return "SIN SEÑAL"
        return "DEGRADADO" if self.degradado else "OK"
