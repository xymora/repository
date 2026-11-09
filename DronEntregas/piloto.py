import math

import config as C
from cerebro import sensores, velocidad_deseada

G = C.G
KV, KVZ = 1.8, 2.5

FASES = {
    "plataforma": "En plataforma", "despegue": "Despegue vertical", "ruta": "En ruta",
    "aproximacion": "Aproximación", "descenso": "Descenso de precisión",
    "abortado": "Aterrizaje en espera (ráfaga)", "paracaidas": "Paracaídas desplegado",
    "en_tierra": "En tierra", "accidente": "Accidente",
}
TERMINALES = ("en_tierra", "accidente")


class Piloto:
    def __init__(self, mision):
        self.m = mision
        d = mision.dron
        self.veh = d.spec
        self.fase = "plataforma"
        self.t_fase = 0.0
        self.ruta = mision.ruta
        self.objetivo = mision.destino.objetivo(True)
        self.emergencia = None
        self.idx = 0
        self.v_max = self.veh["v_crucero"]
        self.v_subida = self.veh["v_subida"]
        self.solo_rotor = False
        self.cola = 0.0
        self.eco = None
        self.evasion = None
        self.t_aviso_ave = -99.0
        self.intentos = 0
        self.t_calma = 0.0
        self.z_aprox = 0.0
        self.alt_seg = 0.0
        self._t_alt = 0.0
        self.avisos_bat = set()
        self.i_pos = [0.0, 0.0]
        self.decisiones = []
        self.cerebro = mision.cerebro

    def nombre_fase(self):
        d = self.m.dron
        n = FASES[self.fase]
        if self.fase == "ruta":
            if d.es_avion:
                n = ("En ruta · como avión" if d.modo == "ala" else
                     "En ruta · como multirrotor" if self.solo_rotor else
                     "Transición" if self.restante() > self.ruta.d_llegada else
                     "Transición a vuelo vertical")
            if not d.gps_ok:
                n += " · sin GPS"
            if self.evasion:
                n += " · esquivando aves"
        return n

    def _cambiar(self, fase):
        self.fase, self.t_fase = fase, 0.0

    def _decision(self, texto):
        self.decisiones.append((self.m.t, texto))
        self.m.log("DECISIÓN: " + texto, "decision")

    def _vmax(self):
        d = self.m.dron
        if d.es_avion and d.modo == "ala":
            v = self.veh["v_max"] if self.eco is None else max(self.eco, self.veh["v_perdida"] + 4)
            return v + self.cola
        if d.es_avion:
            v = self.veh["v_rotor"] if self.solo_rotor else 26.0
        else:
            v = self.v_max
        if not d.gps_ok:
            v *= C.FACTOR_SIN_GPS
        return v if self.eco is None else min(v, self.eco)

    def s_actual(self):
        return self.ruta.s[self.idx]

    def restante(self):
        return self.ruta.longitud - self.s_actual()

    def paso(self, dt):
        d = self.m.dron
        self.t_fase += dt
        if self.fase in TERMINALES or d.apagado:
            return 0.0, 0.0, 0.0
        self._vigilar(dt)
        f = self.fase
        if f == "plataforma":
            if self.t_fase > 1.5:
                self._cambiar("despegue")
                d.en_tierra = False
                self.m.log(f"Despegue vertical del {self.veh['nombre'].lower()} desde "
                           f"{self.m.origen.nombre} con {self.m.origen.carga.lower()} "
                           f"({d.carga:.1f} kg).")
            return 0.0, 0.0, 0.0
        if self.cerebro is not None:
            return self._acel(*self._con_cerebro())
        if f == "despegue":
            v = self._despegue()
        elif f == "ruta":
            v = self._seguir()
        elif f == "aproximacion":
            v = self._aproximar()
        elif f == "descenso":
            v = self._descender(dt)
        else:
            v = self._esperar(dt)
        return self._acel(*v)

    def _acel(self, vx, vy, vz):
        d = self.m.dron
        ala = d.modo == "ala"
        vh = math.hypot(vx, vy)
        lim = self._vmax() if self.fase == "ruta" else (
            12.0 if self.cerebro is not None and self.fase == "despegue" else 6.0)
        if vh > lim:
            vx, vy = vx * lim / vh, vy * lim / vh
        vz = max(-self.veh["v_bajada"] if self.fase != "descenso" else -2.5,
                 min(self.v_subida, vz))
        ax, ay = KV * (vx - d.vel[0]), KV * (vy - d.vel[1])
        ah = math.hypot(ax, ay)
        a_max = 6.5 if ala else C.A_MAX
        if ah > a_max:
            ax, ay = ax * a_max / ah, ay * a_max / ah
        az = max(-4.0, min(4.0, KVZ * (vz - d.vel[2])))
        return ax, ay, az

    def _despegue(self):
        d = self.m.dron
        ex, ey, ez = d.est
        x0, y0 = self.ruta.x[0], self.ruta.y[0]
        h = ez - self.m.origen.h
        vz = 1.0 if h < 3 else self.v_subida
        objetivo = self.ruta.alt[0]
        if ez >= objetivo - 1.0:
            self._cambiar("ruta")
            self.m.log(f"Altura de salida alcanzada ({ez:.0f} m). Inicia: {self.ruta.nombre}.")
        return 0.8 * (x0 - ex), 0.8 * (y0 - ey), min(vz, 1.2 * (objetivo + 0.5 - ez) + 0.3)

    def _seguir(self):
        d, r, m = self.m.dron, self.ruta, self.m
        ex, ey, ez = d.est
        self.idx = r.proyectar(ex, ey, self.idx)
        s = r.s[self.idx]
        vh = math.hypot(d.vel[0], d.vel[1])
        rem = r.longitud - s
        v_ref = min(r.vel[self.idx], self._vmax())
        z_ref = max(r.alt[self.idx], r.alt[r.indice(s + max(vh, 3.0) * 1.5)])
        z_ref = min(C.TECHO, max(z_ref, self.alt_seg))
        mira = max(10.0, 1.5 * vh)
        if d.es_avion:
            wx, wy, _ = m.viento.en(*d.pos)
            v_aire = math.hypot(d.vel[0] - wx, d.vel[1] - wy)
            if d.modo == "rotor" and not self.solo_rotor and rem > r.d_llegada:
                j = r.indice(s + 20.0)
                ux, uy = r.x[j] - ex, r.y[j] - ey
                L = math.hypot(ux, uy) or 1.0
                cola = (wx * ux + wy * uy) / L
                v_ref = self.veh["v_perdida"] + 3 + max(0.0, cola)
                if v_aire >= self.veh["v_perdida"] + 1 and ez >= z_ref - 4:
                    d.cambiar_modo("ala")
                    m.log(f"Transición completada a {v_aire:.0f} m/s: apaga los rotores y "
                          "vuela como avión con la hélice trasera.")
            if d.modo == "ala" and v_aire < self.veh["v_perdida"] + 1:
                d.cambiar_modo("rotor")
                m.log(f"Velocidad respecto al aire baja ({v_aire:.0f} m/s): enciende los "
                      "rotores para no perder sustentación.", "aviso")
            if d.modo == "ala":
                if rem <= r.d_llegada:
                    d.cambiar_modo("rotor")
                    m.log(f"A {rem:.0f} m del cliente: transición a vuelo vertical (enciende "
                          "los rotores y frena).")
                else:
                    j = r.indice(s + 30.0)
                    ux, uy = r.x[j] - ex, r.y[j] - ey
                    L = math.hypot(ux, uy) or 1.0
                    self.cola = max(0.0, (wx * ux + wy * uy) / L)
                    v_ref = max(v_ref, self.veh["v_perdida"] + 4 + self.cola)
                    mira = max(30.0, 3.0 * vh)
        if d.modo != "ala":
            v_ref = min(v_ref, math.sqrt(2 * C.A_FRENAR * max(rem - 1.0, 0.0)) + 0.4)
        j = r.indice(s + mira)
        dx, dy = r.x[j] - ex, r.y[j] - ey
        dist = math.hypot(dx, dy) or 1.0
        vx, vy = dx / dist * v_ref, dy / dist * v_ref
        vz = 0.8 * (z_ref - ez)
        deficit = z_ref - ez
        if deficit > 4 and d.modo != "ala":
            f = max(0.15, 1 - (deficit - 4) / 12)
            vx, vy = vx * f, vy * f
        vx, vy, vz = self._evadir(vx, vy, vz)
        dobj = math.hypot(self.objetivo["x"] - ex, self.objetivo["y"] - ey)
        if d.modo != "ala" and (rem < 6.0 or (dobj < 10.0 and rem < 40)):
            self._iniciar_aproximacion()
        return vx, vy, vz

    def _con_cerebro(self):
        d, r, m = self.m.dron, self.ruta, self.m
        ex, ey, ez = d.est
        aterrizar = False
        if self.fase == "despegue":
            meta = (r.x[0], r.y[0], r.alt[0])
            if ez >= r.alt[0] - 2:
                self._cambiar("ruta")
                m.log(f"Altura de salida alcanzada ({ez:.0f} m). El cerebro sigue la "
                      f"{r.nombre.lower()}.")
        if self.fase == "ruta":
            self.idx = r.proyectar(ex, ey, self.idx)
            s = r.s[self.idx]
            if r.longitud - s < 40:
                self._cambiar("descenso")
                m.log(f"Orden al cerebro: aterrizar en {self.objetivo['nombre']}.")
            else:
                j = r.indice(s + 30)
                meta = (r.x[j], r.y[j], min(C.TECHO, max(r.alt[j], self.alt_seg)))
        if self.fase in ("descenso", "aproximacion", "abortado"):
            o = self.objetivo
            meta, aterrizar = (o["x"], o["y"], o["z"]), True
        x, marco = sensores(d.pos, d.vel, d.est, meta, aterrizar, m.entorno, d.viento_est)
        salida = self.cerebro.decidir(x)
        if d.es_avion:
            w = m.viento.en(*d.pos)
            va = math.hypot(d.vel[0] - w[0], d.vel[1] - w[1])
            lejos = math.hypot(meta[0] - d.pos[0], meta[1] - d.pos[1]) > 260
            if d.modo == "rotor" and va > self.veh["v_perdida"] + 1 and lejos and \
                    not aterrizar and not self.solo_rotor:
                d.cambiar_modo("ala")
            elif d.modo == "ala" and (not lejos or aterrizar or va < self.veh["v_perdida"] + 1):
                d.cambiar_modo("rotor")
        v_max = 26.0 if d.es_avion else self.veh["v_max"]
        if self.fase == "ruta":
            v_max = min(v_max, self._vmax(), r.vel[self.idx] + 2)
        return velocidad_deseada(salida, marco, v_max,
                                 math.hypot(meta[0] - ex, meta[1] - ey), meta[2] - ez)

    def _iniciar_aproximacion(self):
        ez = self.m.dron.est[2]
        self.z_aprox = max(self.objetivo["z"] + C.ALTURA_APROX, ez)
        self.i_pos = [0.0, 0.0]
        self._cambiar("aproximacion")

    def _aproximar(self):
        d, o = self.m.dron, self.objetivo
        ex, ey, ez = d.est
        dx, dy = o["x"] - ex, o["y"] - ey
        dist = math.hypot(dx, dy)
        v = min(5.0, math.sqrt(2 * 1.2 * dist), 0.8 * dist)
        vx, vy = (dx / dist * v, dy / dist * v) if dist > 1e-6 else (0.0, 0.0)
        vz = 0.8 * (self.z_aprox - ez)
        if dist < 1.0 and math.hypot(d.vel[0], d.vel[1]) < 0.7:
            self._cambiar("descenso")
            self.m.log(f"Sobre la plataforma de {o['nombre']}: la cámara ve el marcador; "
                       f"inicia descenso de precisión desde {ez - o['z']:.0f} m.")
        return vx, vy, vz

    def _descender(self, dt):
        d, o, m = self.m.dron, self.objetivo, self.m
        ex, ey, ez = d.est
        dx, dy = o["x"] - ex, o["y"] - ey
        err = math.hypot(dx, dy)
        self.i_pos = [max(-3, min(3, self.i_pos[0] + dx * dt)),
                      max(-3, min(3, self.i_pos[1] + dy * dt))]
        vx = max(-1.5, min(1.5, 0.9 * dx + 0.12 * self.i_pos[0]))
        vy = max(-1.5, min(1.5, 0.9 * dy + 0.12 * self.i_pos[1]))
        h = ez - o["z"]
        tol = C.TOL_PLATAFORMA * (2.0 if h > 5 else 1.0)
        vz = 0.0
        if err <= tol:
            for altura, vel in C.V_DESCENSO:
                if h > altura:
                    vz = -vel
                    break
        rafaga = m.viento.intensidad_rafaga()
        if h < 10 and (rafaga > C.RAFAGA_ABORTO or err > 1.2):
            self.intentos += 1
            motivo = f"ráfaga de {rafaga:.1f} m/s" if rafaga > C.RAFAGA_ABORTO \
                else f"el viento lo movió {err:.1f} m"
            m.log(f"Aterrizaje pausado ({motivo}) a {h:.1f} m de la azotea: sube un poco y "
                  f"espera a que se calme (intento {self.intentos}).", "aviso")
            self.t_calma = 0.0
            self._cambiar("abortado")
        return vx, vy, vz

    def _esperar(self, dt):
        d, o, m = self.m.dron, self.objetivo, self.m
        ex, ey, ez = d.est
        dx, dy = o["x"] - ex, o["y"] - ey
        vz = 0.8 * (o["z"] + 12 - ez)
        if m.viento.intensidad_rafaga() < 3.0:
            self.t_calma += dt
        else:
            self.t_calma = 0.0
        espera = 4.0 + 2.0 * min(self.intentos, 5)
        if self.t_calma > espera and ez > o["z"] + 9:
            m.log("El viento se calmó: reintenta el aterrizaje.")
            self._cambiar("descenso")
        return 0.9 * dx, 0.9 * dy, vz

    def _evadir(self, vx, vy, vz):
        m, d = self.m, self.m.dron
        if self.evasion and m.t < self.evasion["fin"]:
            e = self.evasion
            return vx * 0.6 + e["vx"], vy * 0.6 + e["vy"], vz + e["vz"]
        self.evasion = None
        x, y, z = d.pos
        for p, k, (bx, by, bz) in m.aves.cercanas(x, y, z, C.RADIO_SENSOR):
            rx, ry, rz = bx - x, by - y, bz - z
            wx, wy, wz = p.vx - d.vel[0], p.vy - d.vel[1], -d.vel[2]
            vv = wx * wx + wy * wy + wz * wz
            tca = -(rx * wx + ry * wy + rz * wz) / vv if vv > 0.01 else 0.0
            if tca < 0 or tca > 4.5:
                if math.sqrt(rx * rx + ry * ry + rz * rz) > 12:
                    continue
                tca = 0.0
            mx, my, mz = rx + wx * tca, ry + wy * tca, rz + wz * tca
            if math.sqrt(mx * mx + my * my + mz * mz) > 12:
                continue
            sube = bz <= z and z + 10 < C.TECHO
            if not sube and z - 12 < self.alt_seg:
                sube = True
            lh = math.hypot(mx, my) or 1.0
            lat = 4.0
            self.evasion = dict(fin=m.t + 3.0, vz=3.0 if sube else -3.0,
                                vx=-mx / lh * lat, vy=-my / lh * lat)
            if m.t - self.t_aviso_ave > 8:
                self.t_aviso_ave = m.t
                lado = "derecha" if (d.vel[0] * (-my) - d.vel[1] * (-mx)) > 0 else "izquierda"
                m.log(f"Parvada detectada a {math.sqrt(rx*rx + ry*ry + rz*rz):.0f} m "
                      f"(choque en {tca:.1f} s): maniobra evasiva, "
                      f"{'sube' if sube else 'baja'} y se abre a la {lado}.", "aviso")
            e = self.evasion
            return vx * 0.6 + e["vx"], vy * 0.6 + e["vy"], vz + e["vz"]
        return vx, vy, vz

    def _vigilar(self, dt):
        m, d = self.m, self.m.dron
        ex, ey, _ = d.est
        self._t_alt -= dt
        if self._t_alt <= 0:
            self._t_alt = 0.5
            if d.incert > 3.0 and self.fase in ("ruta", "despegue"):
                self.alt_seg = m.plan.altura_segura(ex, ey, 2 * d.incert + 5)
            else:
                self.alt_seg = 0.0
        if d.fix_visual is not None:
            antes, despues = d.fix_visual
            d.fix_visual = None
            m.log(f"Sin GPS: comparó la cámara con el mapa satelital y corrigió su posición "
                  f"(error {antes:.0f} m → {despues:.0f} m).", "info")
        if self.fase in ("plataforma", "paracaidas") or d.en_tierra:
            return
        nuevos = [u for u in (0.30, 0.20, 0.12) if d.soc < u and u not in self.avisos_bat]
        if nuevos:
            self.avisos_bat.update(nuevos)
            m.log(f"Batería al {d.soc * 100:.0f} %.", "aviso")
            self.evaluar_bateria()

    def energia_necesaria(self, peor=False):
        d, m = self.m.dron, self.m
        W = d.masa * G
        rem = self.restante() if self.fase in ("ruta", "despegue", "plataforma") else \
            math.hypot(self.objetivo["x"] - d.pos[0], self.objetivo["y"] - d.pos[1])
        w = m.viento.velocidad * 1.3
        e = 0.0
        if peor:
            v_rot = self.veh["v_rotor"] if d.es_avion else self.veh["v_degradado"]
            v_rot *= C.FACTOR_SIN_GPS if not d.es_avion else 1.0
            p = d.potencia_crucero(v_rot) * 1.15
            e = p * rem / max(3.0, v_rot - 0.7 * w)
            rem = 0.0
        elif d.es_avion and not self.solo_rotor:
            ala = max(0.0, rem - self.ruta.d_llegada)
            v = self.eco or self.veh["v_crucero"]
            e += d.potencia_ala(v) * ala / max(5.0, v - 0.7 * w)
            rem -= ala
            v_rot = 12.0
        else:
            v_rot = min(self._vmax(), self.eco or 99, self.veh["v_crucero"])
        e += d.potencia_crucero(v_rot) * rem / max(3.0, v_rot - 0.7 * w)
        ph = d.potencia_modelo(W, 0.0, 0.0)
        z = d.pos[2] - self.objetivo["z"]
        e += ph * (max(0.0, z) / 1.6 + 30.0)
        return e / 3600

    def evaluar_bateria(self):
        d = self.m.dron
        if self.fase not in ("despegue", "ruta", "aproximacion", "descenso", "abortado"):
            return
        nec = self.energia_necesaria()
        disp = d.energia_disponible()
        txt = f"necesita ≈{nec:.0f} Wh para llegar y aterrizar; tiene {disp:.0f} Wh + reserva"
        if self.fase in ("aproximacion", "descenso", "abortado"):
            self._decision(f"ya está sobre el cliente: termina el aterrizaje ({txt}).")
            return
        if nec * 1.15 <= disp:
            self._decision(f"SIGUE al cliente sin cambios: {txt}.")
            return
        self.eco = 20.0 if (d.es_avion and not self.solo_rotor) else 12.0
        self.v_subida = min(self.v_subida, 3.0)
        usa_reserva = nec > disp
        self._decision(f"SIGUE al cliente a velocidad de máximo alcance ({self.eco:.0f} m/s) y "
                       f"sin subidas innecesarias: {txt}"
                       + (" → usará parte de la reserva." if usa_reserva else "."))

    def motor_fallado(self, cual):
        d, m = self.m.dron, self.m
        if cual == "empuje":
            m.log("¡Falla de la hélice trasera! Ya no puede volar como avión.", "peligro")
            self.solo_rotor = True
            d.cambiar_modo("rotor")
            self.v_max = self.veh["v_rotor"]
            self._decision(f"enciende los rotores y SIGUE al cliente como multirrotor a "
                           f"{self.veh['v_rotor']:.0f} m/s (más lento y gasta más, pero llega). "
                           f"Energía: necesita ≈{self.energia_necesaria():.0f} Wh de "
                           f"{d.energia_disponible():.0f} Wh.")
            return
        n = self.veh["motores"]
        m.log(f"¡Falla del rotor {cual + 1}! Quedan {n - d.rotores_fallados()} de {n}; "
              f"empuje/peso {d.relacion_empuje():.2f}.", "peligro")
        if self.fase == "plataforma":
            return
        if not d.es_avion:
            self.v_max = min(self.v_max, self.veh["v_degradado"])
        self.v_subida = min(self.v_subida, 2.0)
        modo = ("los rotores sólo se usan para despegar y aterrizar, así que sigue como "
                "avión" if d.es_avion and d.modo == "ala" else
                f"reparte el empuje entre los rotores sanos y baja a {self._vmax():.0f} m/s")
        self._decision(f"SIGUE al cliente: {modo} (empuje/peso {d.relacion_empuje():.2f}, "
                       f"necesita ≈{self.energia_necesaria():.0f} Wh de "
                       f"{d.energia_disponible():.0f} Wh).")

    def gps_perdido(self):
        d = self.m.dron
        self.m.log("Se perdió la señal GPS.", "peligro")
        if self.fase in ("ruta", "despegue"):
            vel = ("mantiene su velocidad de avión" if d.es_avion and d.modo == "ala" else
                   f"baja la velocidad al {C.FACTOR_SIN_GPS * 100:.0f} %")
            self._decision(f"SIGUE al cliente con navegación inercial (IMU + flujo óptico), "
                           f"{vel}, sube a una altura que libre todo en su radio de "
                           f"incertidumbre y cada {C.FIX_VISUAL_CADA:.0f} s compara la cámara "
                           "con el mapa satelital para corregir la deriva.")

    def gps_recuperado(self):
        d = self.m.dron
        self.m.log(f"Señal GPS recuperada tras {d.t_sin_gps:.0f} s (error de la estimación: "
                   f"{math.hypot(*d.err):.1f} m).", "info")

    def bateria_falla(self):
        d = self.m.dron
        self.m.log(f"¡Falla de una celda de la batería! La carga cae al {d.soc * 100:.0f} %.",
                   "peligro")
        self.avisos_bat.update(u for u in (0.30, 0.20, 0.12) if d.soc < u + 0.01)
        self.evaluar_bateria()
