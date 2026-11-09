import math

import numpy as np

import cerebro as B
import config as C
import misiones as MS
import mundo as M
from doctrina import Doctrina

ROJO, AMBAR, VERDE, CIAN, GRIS, BLANCO = "rojo", "ambar", "verde", "cian", "gris", "blanco"


def distancia_segmento(px, py, x0, y0, x1, y1):
    dx, dy = x1 - x0, y1 - y0
    L2 = dx * dx + dy * dy
    u = 0.0 if L2 <= 0 else min(max(((px - x0) * dx + (py - y0) * dy) / L2, 0.0), 1.0)
    return math.hypot(px - (x0 + u * dx), py - (y0 + u * dy))


class Amenaza:
    def __init__(self, ident, tipo, A, Bp, t0, rng):
        p = C.TIPOS[tipo]
        self.id, self.tipo, self.p = ident, tipo, p
        self.ax, self.ay = A
        self.bx, self.by = Bp
        self.d = max(math.hypot(self.bx - self.ax, self.by - self.ay), 1.0)
        self.T = self.d / p["vel"]
        self.H = min(p.get("apogeo_max", 0.0), p.get("apogeo_k", 0.0) * self.d)
        self.t0 = t0
        self.t_impacto = t0 + self.T
        self.ex, self.ey = rng.normal(size=2)
        self.t_det = t0 + rng.uniform(*p["retardo"])
        self.detectada = False
        self.t_detectada = None
        self.n_act = 0
        self.viva = True
        self.final = None
        self.en_vuelo = 0
        self.disparos = 0
        self.rastro = []
        self.dron = tipo == "dron"
        self.ondas = int(rng.integers(1, 4))
        self.amp = float(rng.uniform(150, 500)) if self.dron else 0.0
        self.valor_real = 0.0
        self.fijada = False
        self.t_fijada = None

    def _pos(self, s, bx, by):
        x = self.ax + (bx - self.ax) * s
        y = self.ay + (by - self.ay) * s
        if self.dron:
            d = math.hypot(bx - self.ax, by - self.ay) or 1.0
            ux, uy = (bx - self.ax) / d, (by - self.ay) / d
            w = self.amp * np.sin(math.pi * self.ondas * s)
            x, y = x - uy * w, y + ux * w
            resto = d * (1 - s)
            alt = self.p["altitud"]
            z = np.where(resto > 2500, alt, alt * resto / 2500)
        else:
            z = 4 * self.H * s * (1 - s)
        return x, y, z

    def pos(self, t, bx=None, by=None):
        if bx is None:
            bx, by = self.bx, self.by
        s = min(max((t - self.t0) / self.T, 0.0), 1.0)
        x, y, z = self._pos(s, bx, by)
        return float(x), float(y), float(z)

    def pos_vec(self, ts, bx, by):
        s = np.clip((ts - self.t0) / self.T, 0.0, 1.0)
        return self._pos(s, bx, by)

    def sigma(self):
        return self.p["sigma0"] / (1 + 0.45 * self.n_act)

    def calidad(self):
        return 1 - 1 / (1 + 0.45 * self.n_act)

    def impacto_est(self):
        s = self.sigma()
        return self.bx + self.ex * s, self.by + self.ey * s

    def pos_est(self, t):
        bx, by = self.impacto_est()
        return self.pos(t, bx, by)

    def pk(self, z):
        return self.p["pk"] * (0.55 + 0.45 * self.calidad()) * (0.82 + 0.18 * min(max(z, 0.0) / 3000, 1.0))


class Interceptor:
    def __init__(self, ident, x, y, am, t_lanz, t_int, lanzador):
        self.id = ident
        self.x, self.y, self.z = x, y, 4.0
        self.am = am
        self.t_lanz = t_lanz
        self.t_int = t_int
        self.lanzador = lanzador
        self.activo = True
        self.rastro = []
        self.resultado = None


class Bateria:
    def __init__(self, x, y, recargas, lanzadores=C.LANZADORES, nombre="B1"):
        self.x, self.y = float(x), float(y)
        self.nombre = nombre
        n = int(max(1, min(lanzadores, 8)))
        self.estado = "operativa"
        self.destino = None
        self.timer = 0.0
        self.misiles = [C.MISILES_POR_LANZADOR] * n
        self.recarga_t = [0.0] * n
        self.recargas = int(recargas) * n
        self.impactos = 0
        angs = [math.pi / 2 + k * 2 * math.pi / n for k in range(n)]
        sep = (C.SEPARACION_LANZADORES * (0.7 if n == 2 else 1.0)) if n > 1 else 0.0
        self.offsets = [(sep * math.cos(a), sep * math.sin(a)) for a in angs]

    @property
    def operativa(self):
        return self.estado == "operativa"

    @property
    def destruida(self):
        return self.estado == "destruida"

    def lanzadores(self):
        return [(self.x + ox, self.y + oy) for ox, oy in self.offsets]

    def stock(self):
        return sum(self.misiles) / (len(self.misiles) * C.MISILES_POR_LANZADOR)

    def capacidad(self):
        return len(self.misiles) * C.MISILES_POR_LANZADOR

    def ordenar(self, x, y):
        if self.destruida:
            return False
        x = min(max(x, 1000.0), C.MAPA_W - 1000)
        y = min(max(y, 1000.0), C.MAPA_H - 1000)
        if math.hypot(x - self.x, y - self.y) < 50 and self.estado == "operativa":
            return False
        self.destino = (x, y)
        if self.estado in ("operativa", "desplegando"):
            self.estado = "plegando"
            self.timer = C.T_PLEGAR
        return True

    def eta(self):
        if self.estado == "plegando":
            d = math.hypot(self.destino[0] - self.x, self.destino[1] - self.y)
            return self.timer + d / C.VEL_CONVOY + C.T_DESPLEGAR
        if self.estado == "en_ruta":
            d = math.hypot(self.destino[0] - self.x, self.destino[1] - self.y)
            return d / C.VEL_CONVOY + C.T_DESPLEGAR
        if self.estado == "desplegando":
            return self.timer
        return 0.0

    def paso(self, dt):
        if self.estado == "plegando":
            self.timer -= dt
            if self.timer <= 0:
                self.estado = "en_ruta"
        elif self.estado == "en_ruta":
            dx, dy = self.destino[0] - self.x, self.destino[1] - self.y
            d = math.hypot(dx, dy)
            paso = C.VEL_CONVOY * dt
            if d <= paso:
                self.x, self.y = self.destino
                self.estado = "desplegando"
                self.timer = C.T_DESPLEGAR
            else:
                self.x += dx / d * paso
                self.y += dy / d * paso
        elif self.estado == "desplegando":
            self.timer -= dt
            if self.timer <= 0:
                self.estado = "operativa"
                self.destino = None
        for i in range(len(self.misiles)):
            if self.recarga_t[i] > 0:
                self.recarga_t[i] -= dt
                if self.recarga_t[i] <= 0:
                    self.recarga_t[i] = 0.0
                    self.misiles[i] = C.MISILES_POR_LANZADOR
            elif self.misiles[i] == 0 and self.recargas > 0 and self.operativa:
                self.recargas -= 1
                self.recarga_t[i] = C.RECARGA


class Episodio:
    def __init__(self, mision, controlador, semilla=0, zonas=None, bateria=None, demos=False, bitacora=False,
                 aleatorio=True, baterias=None, n_baterias=None, lanzadores=None):
        self.m = mision
        self.rng = np.random.default_rng(semilla)
        self.zonas = [z.copia() for z in zonas] if zonas is not None else MS.zonas_de(mision)
        self.frentes = list(mision.get("frentes", ["norte"]))
        fijas = True
        if baterias is not None:
            posiciones = [tuple(p) for p in baterias]
        elif bateria is not None:
            posiciones = [tuple(bateria)]
        else:
            fijas = False
            n = n_baterias or mision.get("n_baterias")
            if n:
                posiciones = M.posiciones_optimas(self.zonas, int(n), self.frentes)
            elif "baterias" in mision:
                posiciones = [(x * 1000, y * 1000) for x, y in mision["baterias"]]
            else:
                posiciones = [(mision["bateria"][0] * 1000, mision["bateria"][1] * 1000)]
        if aleatorio and not fijas:
            posiciones = [(x + self.rng.uniform(-800, 800), y + self.rng.uniform(-800, 800)) for x, y in posiciones]
        lz = lanzadores or mision.get("lanzadores", C.LANZADORES)
        if not isinstance(lz, (list, tuple)):
            lz = [lz] * len(posiciones)
        self.baterias = [Bateria(x, y, mision.get("recargas", 0), lz[i % len(lz)], f"B{i + 1}")
                         for i, (x, y) in enumerate(posiciones)]
        self.controlador = controlador
        self.t = 0.0
        self.amenazas = []
        self.activas = []
        self.interceptores = []
        self.impactos = []
        self.explosiones = []
        self.bitacora = [] if bitacora else None
        self.demos_x = [] if demos else None
        self.demos_y = [] if demos else None
        self.duracion = float(mision["duracion"])
        self.continuo = bool(mision.get("continuo", False))
        self.programa = self._programar()
        self.eventos = sorted(mision.get("eventos", []), key=lambda e: e["t"])
        self.prox_decision = 0.0
        self.prox_radar = 0.0
        self.prox_oleada = 15.0
        self.n_id = 0
        self.n_int = 0
        self.terminado = False
        self.calma = False
        self._obligado = Doctrina()
        self.st = {"lanzadas": 0, "detectadas": 0, "interceptadas": 0, "impactos_zona": 0, "impactos_campo": 0,
                   "ignoradas_bien": 0, "usados": 0, "desperdicio": 0, "fallos": 0, "dano": 0.0, "salvado": 0.0,
                   "potencial": 0.0}

    def _programar(self):
        prog = []
        for o in self.m.get("oleadas", []):
            for k in range(int(o["n"])):
                t = o["t"] + k * o["cada"] + self.rng.uniform(0, o["cada"] * 0.5)
                prog.append((t, o["tipo"], o["modo"], o["p_zona"], o["frente"]))
        prog.sort(key=lambda p: p[0])
        return prog

    def log(self, texto, color=BLANCO):
        if self.bitacora is not None:
            self.bitacora.append((self.t, texto, color))
            if len(self.bitacora) > 300:
                del self.bitacora[:100]

    @property
    def bateria(self):
        return self.baterias[0]

    def vivas(self):
        return [b for b in self.baterias if not b.destruida]

    def operativas(self):
        return [b for b in self.baterias if b.operativa]

    def bateria_cerca(self, x, y, radio):
        for b in self.baterias:
            if not b.destruida and math.hypot(x - b.x, y - b.y) <= radio:
                return b
        return None

    def distancia_bateria(self, x, y):
        vivas = self.vivas() or self.baterias
        return min(math.hypot(x - b.x, y - b.y) for b in vivas)

    def stock(self):
        vivas = self.vivas()
        cap = sum(b.capacidad() for b in vivas)
        return sum(sum(b.misiles) for b in vivas) / cap if cap else 0.0

    def agregar_bateria(self, x, y, lanzadores=C.LANZADORES, recargas=None):
        usados = {b.nombre for b in self.baterias}
        k = 1
        while f"B{k}" in usados:
            k += 1
        rec = self.m.get("recargas", 0) if recargas is None else recargas
        b = Bateria(x, y, rec, lanzadores, f"B{k}")
        self.baterias.append(b)
        return b

    def zonas_activas(self):
        return [z for z in self.zonas if z.activa]

    def valor_en(self, x, y, margen=0.0):
        v = 0.0
        for z in self.zonas:
            if z.activa and z.contiene(x, y, margen):
                v = max(v, z.valor)
        if self.bateria_cerca(x, y, C.RADIO_BATERIA_PELIGRO + margen * 0.5) is not None:
            v = max(v, 4.0)
        return v

    def _ruta(self, am):
        x0, y0, _ = am.pos(self.t)
        bx, by = am.impacto_est()
        return x0, y0, bx, by, C.MARGEN_SOBREVUELO + am.amp + am.sigma() * 0.6

    def valor_ruta(self, am):
        x0, y0, bx, by, m = self._ruta(am)
        v = 0.0
        for z in self.zonas:
            if z.activa and distancia_segmento(z.x, z.y, x0, y0, bx, by) <= z.r + m:
                v = max(v, z.valor)
        for b in self.vivas():
            if distancia_segmento(b.x, b.y, x0, y0, bx, by) <= C.RADIO_BATERIA_PELIGRO + m:
                v = max(v, 4.0)
        return v

    def sobrevuelo(self, am):
        x0, y0, bx, by, m = self._ruta(am)
        mejor = None
        for z in self.zonas:
            if z.activa and distancia_segmento(z.x, z.y, x0, y0, bx, by) <= z.r + m:
                if mejor is None or z.valor > mejor[1]:
                    mejor = (z.nombre, z.valor)
        if mejor is not None:
            return mejor[0]
        for b in self.vivas():
            if distancia_segmento(b.x, b.y, x0, y0, bx, by) <= C.RADIO_BATERIA_PELIGRO + m:
                return f"la batería {b.nombre}"
        return None

    def valor_amenaza(self, am, margen=0.0):
        bx, by = am.impacto_est()
        return max(self.valor_en(bx, by, margen), self.valor_ruta(am))

    def _fijar(self, am):
        if am.fijada:
            return
        if self.valor_amenaza(am, am.sigma() * 0.6) > 0:
            am.fijada = True
            am.t_fijada = self.t
            if self.bitacora is not None:
                sobre = None if self.valor_en(*am.impacto_est(), am.sigma() * 0.6) > 0 else self.sobrevuelo(am)
                extra = f" · sobrevuela {sobre}" if sobre else ""
                self.log(f"OBJETIVO FIJADO #{am.id} {am.p['nombre']}{extra}", ROJO)

    def zona_en(self, x, y):
        for z in self.zonas:
            if z.activa and z.contiene(x, y):
                return z
        return None

    def distancia_zonas(self, x, y):
        d = self.distancia_bateria(x, y) - C.RADIO_BATERIA_PELIGRO
        for z in self.zonas:
            if z.activa:
                d = min(d, z.distancia_borde(x, y))
        return d

    def _objetivo(self, tipo, modo, p_zona):
        activas = self.zonas_activas()
        vivas = self.vivas()
        if modo == "bateria" and vivas:
            b = vivas[int(self.rng.integers(len(vivas)))]
            return b.x + self.rng.normal(0, 250), b.y + self.rng.normal(0, 250)
        if activas and (modo == "zonas" or (modo == "mixto" and self.rng.uniform() < p_zona)):
            pesos = np.array([z.valor for z in activas])
            z = activas[int(self.rng.choice(len(activas), p=pesos / pesos.sum()))]
            r = z.r * 0.85 * math.sqrt(self.rng.uniform())
            a = self.rng.uniform(0, 2 * math.pi)
            return z.x + r * math.cos(a), z.y + r * math.sin(a)
        ref = activas or [M.Zona("c", b.x, b.y, 0) for b in self.baterias]
        for _ in range(60):
            z = ref[int(self.rng.integers(len(ref)))]
            r = self.rng.uniform(z.r + 1500, z.r + 14000)
            a = self.rng.uniform(0, 2 * math.pi)
            x, y = z.x + r * math.cos(a), z.y + r * math.sin(a)
            if not (1000 < x < C.MAPA_W - 1000 and 1000 < y < C.MAPA_H - 1000) or M.en_frente(x, y, self.frentes):
                continue
            if self.valor_en(x, y, 900) > 0:
                continue
            return x, y
        return None

    def _origen(self, tipo, Bp, frente):
        lo, hi = C.TIPOS[tipo]["rango"]
        x0, y0, x1, y1 = M.FRENTES.get(frente, M.FRENTES["norte"])
        for _ in range(80):
            x, y = self.rng.uniform(x0, x1), self.rng.uniform(y0, y1)
            if lo <= math.hypot(x - Bp[0], y - Bp[1]) <= hi:
                return x, y
        return None

    def lanzar(self, tipo, modo="mixto", p_zona=0.5, frente="norte"):
        Bp = self._objetivo(tipo, modo, p_zona)
        if Bp is None:
            return None
        frentes = [frente] + [f for f in self.frentes if f != frente]
        for tp in (tipo, "medio", "corto"):
            for f in frentes:
                A = self._origen(tp, Bp, f)
                if A is not None:
                    self.n_id += 1
                    am = Amenaza(self.n_id, tp, A, Bp, self.t, self.rng)
                    self.amenazas.append(am)
                    self.activas.append(am)
                    self.st["lanzadas"] += 1
                    return am
        return None

    def _oleada_continua(self):
        n = int(self.rng.integers(4, 14))
        tipos = self.rng.choice(C.ORDEN_TIPOS, p=[0.55, 0.25, 0.1, 0.1])
        frente = self.frentes[int(self.rng.integers(len(self.frentes)))]
        cada = float(self.rng.uniform(0.4, 2.5))
        for k in range(n):
            self.programa.append((self.t + k * cada + self.rng.uniform(0, 0.5), str(tipos), "mixto",
                                  float(self.rng.uniform(0.35, 0.7)), frente))
        self.programa.sort(key=lambda p: p[0])
        self.prox_oleada = self.t + n * cada + self.rng.uniform(25, 70)

    def solucion(self, am, L=None):
        if L is None:
            mejor = None
            for b in self.operativas():
                s = self.solucion(am, (b.x, b.y))
                if s is not None and (mejor is None or (s[3], -s[0]) > (mejor[3], -mejor[0])):
                    mejor = s
            return mejor
        t0 = self.t + C.INT_RETARDO
        tf = am.t_impacto - 0.5
        if tf <= t0:
            return None
        ts = np.arange(t0, tf, 0.5)
        bx, by = am.impacto_est()
        x, y, z = am.pos_vec(ts, bx, by)
        z = np.broadcast_to(z, ts.shape)
        h = np.hypot(x - L[0], y - L[1])
        vuelo = np.sqrt(h * h + z * z) / C.INT_VEL + C.INT_RETARDO
        ok = (h <= C.INT_ALCANCE) & (z <= C.INT_TECHO) & (z >= C.INT_ALT_MIN) & (vuelo <= ts - self.t)
        if not ok.any():
            return None
        i = int(np.argmax(ok))
        ventana = float(np.max((ts - vuelo)[ok]) - self.t)
        return float(ts[i]), (float(x[i]), float(y[i]), float(z[i])), ventana, am.pk(float(z[i]))

    def disparar(self, am, n=1):
        if not am.viva:
            return 0
        hechos = 0
        usadas = set()
        for _ in range(int(n)):
            opciones = []
            for b in self.operativas():
                for i, L in enumerate(b.lanzadores()):
                    if b.misiles[i] > 0:
                        opciones.append((math.hypot(L[0] - am.bx, L[1] - am.by), b, i, L))
            if not opciones:
                break
            opciones.sort(key=lambda o: o[0])
            elegido = None
            for _, b, i, L in opciones[:6]:
                sol = self.solucion(am, L)
                if sol is None:
                    continue
                clave = (sol[3] - (0.05 if (b.nombre, i) in usadas else 0.0), -sol[0])
                if elegido is None or clave > elegido[0]:
                    elegido = (clave, b, i, L, sol)
            if elegido is None:
                break
            _, bat, i, L, sol = elegido
            usadas.add((bat.nombre, i))
            bat.misiles[i] -= 1
            self.n_int += 1
            it = Interceptor(self.n_int, L[0], L[1], am, self.t + C.INT_RETARDO * (0.3 + 0.4 * hechos), sol[0], i)
            it.bateria = bat
            self.interceptores.append(it)
            am.en_vuelo += 1
            am.disparos += 1
            self.st["usados"] += 1
            hechos += 1
        if hechos:
            self.log(f"Interceptor{'es' if hechos > 1 else ''} ×{hechos} → {am.p['nombre']} #{am.id}", CIAN)
        return hechos

    def _amenazante(self, am):
        return self.valor_en(am.bx, am.by)

    def _resolver_interceptor(self, it):
        am = it.am
        it.activo = False
        am.en_vuelo -= 1
        if not am.viva:
            it.resultado = "abortado"
            return
        tx, ty, tz = am.pos(self.t)
        ax, ay, az = am.pos_est(it.t_int)
        error = math.sqrt((tx - ax) ** 2 + (ty - ay) ** 2 + (tz - az) ** 2)
        pk = am.pk(tz)
        if error > C.RADIO_CORRECCION:
            pk *= max(0.05, 1 - (error - C.RADIO_CORRECCION) / (2 * C.RADIO_CORRECCION))
        if self.rng.uniform() < pk:
            am.viva = False
            am.final = "interceptada"
            it.resultado = "derribo"
            self.st["interceptadas"] += 1
            v = self._amenazante(am)
            if v > 0:
                self.st["salvado"] += v
                self.st["potencial"] += v
            elif not am.fijada and self.valor_ruta(am) <= 0:
                self.st["desperdicio"] += am.disparos
            self.explosiones.append((tx, ty, tz, self.t, "derribo"))
            self.log(f"Intercepción de #{am.id} a {tz / 1000:.1f} km de altura", VERDE)
        else:
            it.resultado = "fallo"
            self.st["fallos"] += 1
            self.explosiones.append((it.x, it.y, it.z, self.t, "fallo"))
            self.log(f"Fallo contra #{am.id}", AMBAR)

    def _impacto(self, am):
        am.viva = False
        am.final = "impacto"
        v = self._amenazante(am)
        z = self.zona_en(am.bx, am.by)
        bat = self.bateria_cerca(am.bx, am.by, C.RADIO_BATERIA_PELIGRO)
        if v > 0:
            self.st["dano"] += v
            self.st["potencial"] += v
            self.st["impactos_zona"] += 1
            lugar = z.nombre if z is not None else (f"la batería {bat.nombre}" if bat else "la batería")
            self.log(f"IMPACTO en {lugar} ({am.p['nombre']} #{am.id})", ROJO)
            if bat is not None:
                bat.impactos += 1
                if bat.impactos >= 2:
                    bat.estado = "destruida"
                    bat.destino = None
                    self.log(f"La batería {bat.nombre} quedó fuera de combate", ROJO)
        else:
            self.st["impactos_campo"] += 1
            if am.disparos == 0:
                self.st["ignoradas_bien"] += 1
            elif not am.fijada:
                self.st["desperdicio"] += am.disparos
            self.log(f"#{am.id} cayó en campo abierto", GRIS)
        self.impactos.append((am.bx, am.by, self.t, v > 0))
        self.explosiones.append((am.bx, am.by, 0.0, self.t, "impacto"))

    def _eventos_mision(self):
        while self.eventos and self.eventos[0]["t"] <= self.t:
            e = self.eventos.pop(0)
            if e["accion"] in ("activar", "desactivar"):
                for z in self.zonas:
                    if z.nombre == e["zona"]:
                        z.activa = e["accion"] == "activar"
                self.log(("Nueva área a proteger: " if e["accion"] == "activar" else "Área liberada: ") + e["zona"], AMBAR)
            elif e["accion"] == "cubrir":
                vivas = self.vivas()
                objetivos = M.posiciones_optimas(self.zonas, len(vivas), self.frentes)
                for b, p in zip(vivas, M.asignar([(b.x, b.y) for b in vivas], objetivos)):
                    if p is not None and b.ordenar(*p):
                        self.log(f"Orden de reubicación de {b.nombre} a ({p[0] / 1000:.1f}, {p[1] / 1000:.1f}) km", AMBAR)
            elif e["accion"] == "mover":
                self.bateria.ordenar(e["x"] * 1000, e["y"] * 1000)

    def contexto(self, cands):
        tis = []
        for am, sol in cands:
            bx, by = am.impacto_est()
            if self.valor_en(bx, by, am.sigma() * 0.8) > 0:
                tis.append(am.t_impacto - self.t)
        tis.sort()
        return {"stock": self.stock(), "activas": len(self.activas), "amenazantes": len(tis), "tis": tis}

    def _decidir(self):
        cands = []
        for am in self.activas:
            if am.detectada and am.en_vuelo == 0:
                cands.append((am, self.solucion(am)))
        if not cands:
            return
        ctx = self.contexto(cands)
        ordenes = list(self.controlador.decidir(self, cands, ctx) or [])
        auto = getattr(self.controlador, "automatico", True)
        ya = {am.id for am, _ in ordenes}
        pendientes = [(am, sol) for am, sol in cands if am.id not in ya and sol is not None and (auto or am.fijada)]
        if pendientes:
            ordenes += self._obligado.decidir(self, pendientes, ctx)
        if self.demos_x is not None:
            elegido = {am.id: n for am, n in ordenes}
            for am, sol in cands:
                if self.valor_en(*am.impacto_est(), am.sigma() * 0.8) <= 0 and (am.fijada or self.valor_ruta(am) > 0):
                    continue
                self.demos_x.append(B.caracteristicas(self, am, sol, ctx))
                n = elegido.get(am.id, 0)
                self.demos_y.append(B.objetivo(n))
        for am, n in ordenes:
            self.disparar(am, n)

    def proximo_evento(self):
        prox = [self.duracion]
        if self.programa:
            prox.append(self.programa[0][0])
        if self.eventos:
            prox.append(self.eventos[0]["t"])
        if self.continuo:
            prox.append(self.prox_oleada)
        return min(prox)

    def paso(self):
        if self.terminado:
            return
        self.calma = not self.activas and not self.interceptores and self.proximo_evento() - self.t > 4.0
        dt = C.DT
        if self.calma:
            dt = max(C.DT, min(2.0, self.proximo_evento() - self.t - 2.0))
        self.t += dt
        self._eventos_mision()
        if self.continuo and self.t >= self.prox_oleada:
            self._oleada_continua()
        while self.programa and self.programa[0][0] <= self.t:
            _, tipo, modo, pz, fr = self.programa.pop(0)
            self.lanzar(tipo, modo, pz, fr)
        for b in self.baterias:
            b.paso(dt)
        radares = self.operativas()
        if radares and self.t >= self.prox_radar:
            self.prox_radar = self.t + C.RADAR_PERIODO
            for am in self.activas:
                if self.t < am.t_det:
                    continue
                x, y, z = am.pos(self.t)
                visto = False
                for b in radares:
                    d = math.hypot(x - b.x, y - b.y)
                    if d <= C.RADAR_ALCANCE and z >= d * d / (2 * C.RADIO_TIERRA_EF):
                        visto = True
                        break
                if visto:
                    am.n_act += 1
                    if not am.detectada:
                        am.detectada = True
                        am.t_detectada = self.t
                        self.st["detectadas"] += 1
                        if self.bitacora is not None:
                            ix, iy = am.impacto_est()
                            z = self.zona_en(ix, iy)
                            dest = z.nombre if z else ("la batería" if self.valor_en(ix, iy) else "campo abierto")
                            sobre = self.sobrevuelo(am) if dest == "campo abierto" else None
                            if sobre:
                                dest = f"campo abierto, sobrevuela {sobre}"
                            self.log(f"{am.p['nombre']} #{am.id} → {dest} ({am.t_impacto - self.t:.0f} s)",
                                     ROJO if dest != "campo abierto" else GRIS)
                    self._fijar(am)
        if self.t >= self.prox_decision and radares:
            self.prox_decision = self.t + C.DT * C.DECIDIR_CADA
            self._decidir()
        for it in self.interceptores:
            if not it.activo:
                continue
            if not it.am.viva:
                it.activo = False
                it.am.en_vuelo -= 1
                it.resultado = "abortado"
                self.explosiones.append((it.x, it.y, it.z, self.t, "aborto"))
                continue
            if self.t < it.t_lanz:
                continue
            resto = it.t_int - self.t
            if resto <= dt * 0.5:
                self._resolver_interceptor(it)
                continue
            ax, ay, az = it.am.pos_est(it.t_int)
            vx, vy, vz = (ax - it.x) / resto, (ay - it.y) / resto, (az - it.z) / resto
            vel = math.sqrt(vx * vx + vy * vy + vz * vz)
            if vel > C.INT_VMAX:
                f = C.INT_VMAX / vel
                vx, vy, vz = vx * f, vy * f, vz * f
            it.x += vx * dt
            it.y += vy * dt
            it.z += vz * dt
        self.interceptores = [it for it in self.interceptores if it.activo]
        for am in self.activas:
            if am.viva and self.t >= am.t_impacto:
                self._impacto(am)
        self.activas = [am for am in self.activas if am.viva]
        if len(self.explosiones) > 400:
            self.explosiones = [e for e in self.explosiones if self.t - e[3] < 6]
        fin = self.t >= self.duracion and not self.activas and not self.interceptores
        if self.continuo:
            fin = self.t >= self.duracion
        if fin or self.t >= self.duracion + 300:
            self.terminado = True

    def correr(self):
        while not self.terminado:
            self.paso()
        return self.resumen()

    def proteccion(self):
        p = self.st["potencial"]
        return 1.0 if p <= 0 else self.st["salvado"] / p

    def desperdicio(self):
        return self.st["desperdicio"] / max(self.st["usados"], 1)

    def resumen(self):
        st = self.st
        caidas = sum(1 for b in self.baterias if b.destruida)
        destruida = caidas > 0
        aptitud = (C.PREMIO_SALVADO * st["salvado"] - C.CASTIGO_DANO * st["dano"] - C.COSTO_INTERCEPTOR * st["usados"]
                   - C.CASTIGO_BATERIA * caidas)
        prot = self.proteccion()
        superada = prot >= C.PROTECCION_MIN and self.desperdicio() <= C.DESPERDICIO_MAX and not destruida
        r = dict(st)
        r.update({"aptitud": float(aptitud), "proteccion": float(prot), "desperdicio_frac": float(self.desperdicio()),
                  "superada": bool(superada), "destruida": bool(destruida), "t": self.t})
        return r
