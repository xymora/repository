import math

import numpy as np

import cerebro as B
import config as C
import misiones as MS
import mundo as M
from doctrina import Doctrina
from satelites import Constelacion

ROJO, AMBAR, VERDE, CIAN, GRIS, BLANCO = "rojo", "ambar", "verde", "cian", "gris", "blanco"
R = C.R_TIERRA


def _angulo(a, b):
    a0, a1, a2 = float(a[0]), float(a[1]), float(a[2])
    b0, b1, b2 = float(b[0]), float(b[1]), float(b[2])
    cx, cy, cz = a1 * b2 - a2 * b1, a2 * b0 - a0 * b2, a0 * b1 - a1 * b0
    return math.atan2(math.sqrt(cx * cx + cy * cy + cz * cz), a0 * b0 + a1 * b1 + a2 * b2)


class Amenaza:
    def __init__(self, ident, tipo, A, Bp, t0, rng, objetivo="", origen="", padre=None, senuelo=False,
                 bando_atk="", bando_obj=""):
        p = C.TIPOS[tipo]
        self.id, self.tipo, self.p = ident, tipo, p
        self.bando_atk = padre.bando_atk if padre is not None else bando_atk
        self.bando_obj = padre.bando_obj if padre is not None else bando_obj
        self.A, self.B = (float(A[0]), float(A[1])), (float(Bp[0]), float(Bp[1]))
        self.a = M.unitario(*self.A)
        self.b = M.unitario(*self.B)
        self.om = max(_angulo(self.a, self.b), 1e-6)
        self.d = R * self.om
        self.padre = padre
        self.planeador = tipo == "planeador"
        if padre is None:
            self.t0 = t0
            self.motor = p["motor"]
            self.T = self.d / p["vel"] + 0.5 * self.motor
            if self.planeador:
                self.H = 80.0
            else:
                self.H = min(max(p["apogeo_k"] * self.d, p["apogeo_min"]), p["apogeo_max"])
                self.H = min(self.H, max(0.5 * self.d, 40.0))
        else:
            self.t0 = padre.t0
            self.motor = padre.motor
            self.T = padre.T * self.d / max(padre.d, 1.0)
            self.H = padre.H
        self.t_impacto = self.t0 + self.T
        self.sb = min(0.45, self.motor / self.T)
        self.t_motor_fin = self.t0 + self.motor
        if self.planeador:
            self.t_reentrada = self.t0 + 0.92 * self.T
        else:
            self.t_reentrada = self.t0 + self.T * (1 - math.asin(min(1.0, C.ALT_REENTRADA / self.H)) / math.pi)
        self.ex, self.ey = rng.normal(size=2)
        self.t_sat = self.t0 + rng.uniform(*C.SAT_RETARDO)
        self.n_act = 0.0
        self.detectada = False
        self.t_detectada = None
        self.viva = True
        self.final = None
        self.en_vuelo = 0
        self.disparos = 0
        self.rastro = []
        self.fijada = False
        self.t_fijada = None
        self.disc = 0.0
        self.sat_vis = None
        self.nuclear = bool(padre.nuclear and not senuelo) if padre is not None else False
        self.respuesta = padre.respuesta if padre is not None else False
        self.sesgo = float(rng.normal(0, 0.22))
        self.senuelo = senuelo
        self.racimo = None
        self.mirv = None
        self.t_sep = None
        self.objetivo, self.origen = objetivo, origen
        self.ondas = int(rng.integers(1, 4))
        self.amp = float(rng.uniform(40, 120)) if self.planeador else 0.0
        n = np.cross(self.a, self.b)
        nn = float(np.linalg.norm(n))
        self.n = n / nn if nn > 1e-9 else np.array([0.0, 0.0, 1.0])
        self._b_est = None
        self._clave_est = None
        self.p_sep = None
        if padre is not None:
            self.t_sep = padre.t_sep
            self.p_sep = padre.pos(padre.t_sep)

    def _s(self, t):
        return min(max((t - self.t0) / self.T, 0.0), 1.0)

    def _g(self, s):
        sb = self.sb
        g = s * s / (2 * sb) if s < sb else sb / 2 + s - sb
        return g / (1 - sb / 2)

    def _h(self, s):
        if self.planeador:
            sb = self.sb
            cr = self.p["crucero"]
            if s < sb:
                return self.H * math.sin(math.pi / 2 * s / sb)
            h92 = cr + (self.H - cr) * math.exp(-(0.92 - sb) * 25)
            if s < 0.92:
                return cr + (self.H - cr) * math.exp(-(s - sb) * 25)
            return h92 * (1 - s) / 0.08
        return self.H * math.sin(math.pi * s)

    def _datos_b(self, b):
        cache = self.__dict__.setdefault("_cache_b", {})
        e = cache.get(id(b))
        if e is None or e[0] is not b:
            if len(cache) > 6:
                cache.clear()
            e = [b, max(_angulo(self.a, b), 1e-6), None]
            cache[id(b)] = e
        return e

    def _delta(self, b):
        e = self._datos_b(b)
        if e[2] is None:
            e[2] = self.p_sep - self._crudo(self.t_sep, b)
        return e[2]

    def _crudo(self, t, b):
        s = self._s(t)
        g = self._g(s)
        om = self._datos_b(b)[1]
        u = (math.sin((1 - g) * om) * self.a + math.sin(g * om) * b) / math.sin(om)
        if self.planeador and self.sb < s < 0.92:
            u = u + self.n * (self.amp / R * math.sin(math.pi * self.ondas * g))
        u = u / np.linalg.norm(u)
        return u * (R + self._h(s))

    def _crudo_vec(self, ts, b):
        s = np.clip((ts - self.t0) / self.T, 0.0, 1.0)
        sb = self.sb
        g = np.where(s < sb, s * s / (2 * sb), sb / 2 + s - sb) / (1 - sb / 2)
        om = self._datos_b(b)[1]
        u = (np.sin((1 - g) * om)[:, None] * self.a + np.sin(g * om)[:, None] * b) / math.sin(om)
        if self.planeador:
            m = (s > sb) & (s < 0.92)
            u = u + self.n[None, :] * (m * self.amp / R * np.sin(math.pi * self.ondas * g))[:, None]
            cr = self.p["crucero"]
            h92 = cr + (self.H - cr) * math.exp(-(0.92 - sb) * 25)
            h = np.where(s < sb, self.H * np.sin(np.pi / 2 * s / sb),
                         np.where(s < 0.92, cr + (self.H - cr) * np.exp(-(s - sb) * 25), h92 * (1 - s) / 0.08))
        else:
            h = self.H * np.sin(np.pi * s)
        u = u / np.linalg.norm(u, axis=1)[:, None]
        return u * (R + h)[:, None]

    def _tray(self, t, b):
        P = self._crudo(t, b)
        if self.p_sep is not None:
            delta = self._delta(b)
            w = min(max((t - self.t_sep) / max(self.t_impacto - self.t_sep, 1.0), 0.0), 1.0)
            P = P + delta * (1 - w)
        return P

    def _tray_vec(self, ts, b):
        P = self._crudo_vec(ts, b)
        if self.p_sep is not None:
            delta = self._delta(b)
            w = np.clip((ts - self.t_sep) / max(self.t_impacto - self.t_sep, 1.0), 0.0, 1.0)
            P = P + delta[None, :] * (1 - w)[:, None]
        return P

    def pos(self, t):
        return self._tray(t, self.b)

    def b_est(self):
        clave = round(self.n_act, 1)
        if clave != self._clave_est:
            s = self.sigma()
            la, lo = M.desplazar(self.B[0], self.B[1], self.ex * s, self.ey * s)
            self._b_est = (M.unitario(la, lo), (la, lo))
            self._clave_est = clave
        return self._b_est

    def impacto_est(self):
        return self.b_est()[1]

    def pos_est(self, t):
        return self._tray(t, self.b_est()[0])

    def pos_vec(self, ts, est=True):
        return self._tray_vec(ts, self.b_est()[0] if est else self.b)

    def latlon(self, t):
        return M.latlon(self.pos(t))

    def alt(self, t):
        return float(np.linalg.norm(self.pos(t))) - R

    def sigma(self):
        return self.p["sigma0"] / (1 + 0.3 * self.n_act)

    def calidad(self):
        return 1 - 1 / (1 + 0.3 * self.n_act)

    def fase(self, t):
        if self.padre is None and t < self.t_motor_fin:
            return "impulso"
        if t >= self.t_reentrada:
            return "terminal"
        return "media"

    def p_ojiva(self):
        if self.racimo is None:
            return 1.0
        prior = self.racimo[0] / self.racimo[1]
        p = prior + self.disc * ((0.0 if self.senuelo else 1.0) - prior) + (1 - self.disc) * self.sesgo
        return min(max(p, 0.02), 0.98)

    def ojivas(self):
        return self.mirv[0] if (self.mirv and self.viva and self.final != "separada") else 1

    def pk(self, capa):
        return C.CAPAS[capa]["pk"] * self.p["pk"] * (0.55 + 0.45 * self.calidad())

    def nombre(self):
        if self.racimo is not None:
            p = self.p_ojiva()
            if self.final == "quemado":
                return "Señuelo"
            if p >= 0.8:
                return "Ojiva nuclear" if self.nuclear else "Ojiva"
            if p <= 0.25:
                return "Posible señuelo"
            return "Objeto"
        if self.respuesta:
            return "Contraataque " + self.p["nombre"].lower()
        extra = " nuclear" if self.nuclear else ""
        if self.mirv:
            return self.p["nombre"] + extra + " (ojivas múltiples)"
        return self.p["nombre"] + extra


class Interceptor:
    def __init__(self, ident, activo, am, t_lanz, t_int, apunte, capa):
        self.id = ident
        self.activo_lanz = activo
        self.am = am
        self.t_lanz = t_lanz
        self.t_int = t_int
        self.apunte = apunte
        self.capa = capa
        self.activo = True
        self.rastro = []
        self.resultado = None
        self.S = activo.S.copy()
        self.h0 = 0.0
        self.redirigido = 0

    def pos(self, t):
        f = min(max((t - self.t_lanz) / max(self.t_int - self.t_lanz, 1e-6), 0.0), 1.0)
        a = self.S / np.linalg.norm(self.S)
        b = self.apunte / np.linalg.norm(self.apunte)
        om = max(_angulo(a, b), 1e-9)
        u = (math.sin((1 - f) * om) * a + math.sin(f * om) * b) / math.sin(om) if om > 1e-6 else a
        h_fin = float(np.linalg.norm(self.apunte)) - R
        h = self.h0 + (h_fin - self.h0) * (1 - (1 - f) ** 2) + (0.12 if self.h0 <= 0 else 0.03) * R * om * math.sin(math.pi * f)
        return u / np.linalg.norm(u) * (R + max(h, 0.0))


class Activo:
    def __init__(self, tipo, lat, lon, lanzadores=None, recargas=0, nombre="A1", bando=""):
        q = C.ACTIVOS[tipo]
        self.tipo, self.q, self.nombre, self.bando = tipo, q, nombre, bando
        self.capa = q["capa"]
        self.radar = q["radar"]
        self.lat, self.lon = float(lat), float(lon)
        self.S = M.ecef(self.lat, self.lon)
        n = q["lanzadores"] if lanzadores is None else int(lanzadores)
        n = 0 if self.capa is None else max(1, min(n, 8))
        self.por_lanzador = C.CAPAS[self.capa]["misiles"] if self.capa else 0
        self.misiles = [self.por_lanzador] * n
        self.recarga_t = [0.0] * n
        self.recargas = int(recargas) * n
        self.estado = "operativa"
        self.timer = 0.0
        self.impactos = 0

    @property
    def operativa(self):
        return self.estado == "operativa"

    @property
    def destruida(self):
        return self.estado == "destruida"

    def mover(self, lat, lon, inmediato=False):
        if self.destruida:
            return False
        self.lat, self.lon = float(lat), float(lon)
        self.S = M.ecef(self.lat, self.lon)
        if inmediato:
            self.estado, self.timer = "operativa", 0.0
        else:
            self.estado, self.timer = "desplegando", C.T_REDESPLIEGUE
        return True

    def stock(self):
        return sum(self.misiles) / max(len(self.misiles) * self.por_lanzador, 1)

    def capacidad(self):
        return len(self.misiles) * self.por_lanzador

    def paso(self, dt):
        if self.estado == "desplegando":
            self.timer -= dt
            if self.timer <= 0:
                self.estado = "operativa"
        for i in range(len(self.misiles)):
            if self.recarga_t[i] > 0:
                self.recarga_t[i] -= dt
                if self.recarga_t[i] <= 0:
                    self.recarga_t[i] = 0.0
                    self.misiles[i] = self.por_lanzador
            elif self.misiles[i] == 0 and self.recargas > 0 and self.operativa:
                self.recargas -= 1
                self.recarga_t[i] = C.CAPAS[self.capa]["recarga"]


class Episodio:
    def __init__(self, mision, controlador, semilla=0, demos=False, bitacora=False, lanzadores=None):
        self.m = dict(mision)
        self.rng = np.random.default_rng(semilla)
        self.bandos = MS.bandos_de(mision)
        self.zonas = []
        self.activos = []
        self.origen_bando = {}
        self.ataca = {}
        for b in self.bandos:
            self.ataca[b["nombre"]] = list(b["ataca"])
            self.zonas.extend(MS.zonas_lista(b["ciudades"], b["nombre"]))
            for o in b["origenes"]:
                self.origen_bando[M.registrar_origen(o)] = b["nombre"]
            for spec in b["activos"]:
                tipo, lat, lon, lz = spec[0], spec[1], spec[2], spec[3]
                if lanzadores and C.ACTIVOS[tipo]["capa"] is not None:
                    lz = lanzadores
                self.agregar_activo(tipo, lat, lon, lz, bando=b["nombre"])
        self.origenes = list(self.origen_bando)
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
        self.poner_satelites(mision.get("satelites", C.SAT_DEFECTO))
        self.programa = self._programar()
        self.prox_decision = 0.0
        self.prox_radar = 0.0
        self.prox_oleada = 30.0
        self.n_id = 0
        self.n_int = 0
        self.terminado = False
        self.calma = False
        self._obligado = Doctrina()
        self.st = {"lanzadas": 0, "detectadas": 0, "interceptadas": 0, "impactos_zona": 0, "impactos_campo": 0,
                   "ignoradas_bien": 0, "usados": 0, "desperdicio": 0, "fallos": 0, "dano": 0.0, "salvado": 0.0,
                   "potencial": 0.0, "senuelos": 0, "senuelos_derribados": 0, "quemados": 0, "separaciones": 0,
                   "costo": 0.0, "por_capa": {c: 0 for c in C.ORDEN_CAPAS}, "nucleares": 0, "nucleares_impacto": 0,
                   "contra_lanzados": 0, "contra_impactos": 0}
        self.contra_hecho = False

    def agregar_activo(self, tipo, lat, lon, lanzadores=None, recargas=None, bando=None):
        usados = {a.nombre for a in self.activos}
        k = 1
        while f"A{k}" in usados:
            k += 1
        rec = self.m.get("recargas", 0) if recargas is None else recargas
        if bando is None:
            bando = self.bandos[0]["nombre"] if self.bandos else ""
        a = Activo(tipo, lat, lon, lanzadores, rec, f"A{k}", bando)
        self.activos.append(a)
        return a

    def _programar(self):
        prog = []
        for o in self.m.get("oleadas", []):
            for k in range(int(o["n"])):
                t = o["t"] + k * o["cada"] + self.rng.uniform(0, o["cada"] * 0.5)
                prog.append((t, o))
        prog.sort(key=lambda p: p[0])
        return prog

    def log(self, texto, color=BLANCO):
        if self.bitacora is not None:
            self.bitacora.append((self.t, texto, color))
            if len(self.bitacora) > 300:
                del self.bitacora[:100]

    def poner_satelites(self, modo):
        self.sats = Constelacion(modo)
        self.satelites = self.sats.modo
        self.m["satelites"] = self.sats.modo

    def vivos(self):
        return [a for a in self.activos if not a.destruida]

    def operativos(self):
        return [a for a in self.activos if a.operativa]

    def zonas_activas(self):
        return [z for z in self.zonas if z.activa]

    def stock(self, capa=None):
        tot = cap = 0
        for a in self.vivos():
            if a.capa is None or (capa is not None and a.capa != capa):
                continue
            tot += sum(a.misiles)
            cap += a.capacidad()
        return tot / cap if cap else 0.0

    def activo_cerca(self, lat, lon, radio, bando=None):
        for a in self.activos:
            if not a.destruida and (bando is None or a.bando == bando) and M.distancia(lat, lon, a.lat, a.lon) <= radio:
                return a
        return None

    def valor_en(self, lat, lon, margen=0.0, bando=None):
        v = 0.0
        for z in self.zonas:
            if z.activa and z.valor > v and (bando is None or z.bando == bando) and z.contiene(lat, lon, margen):
                v = z.valor
        if self.activo_cerca(lat, lon, C.RADIO_ACTIVO_PELIGRO + margen * 0.5, bando) is not None:
            v = max(v, 4.0)
        return v

    def zona_en(self, lat, lon, margen=0.0, bando=None):
        mejor = None
        for z in self.zonas:
            if (z.activa and (bando is None or z.bando == bando) and z.contiene(lat, lon, margen)
                    and (mejor is None or z.valor > mejor.valor)):
                mejor = z
        return mejor

    def enemigas(self, atacante, contra=None):
        objetivos = contra or self.ataca.get(atacante, [])
        return [z for z in self.zonas if z.activa and z.bando in objetivos]

    def atacantes(self):
        return [b["nombre"] for b in self.bandos if b["ataca"] and b["origenes"] and self.enemigas(b["nombre"])]

    def sobrevuelo(self, am):
        if not (am.planeador or self.t >= am.t_reentrada - 60):
            return None
        t1 = am.t_impacto
        t0 = max(self.t, am.t_reentrada - 60 if not am.planeador else self.t)
        if t1 - t0 < 2:
            return None
        ts = np.linspace(t0, t1, 24)
        P = am.pos_vec(ts)
        alt = np.linalg.norm(P, axis=1) - R
        P = P[alt < 100]
        if not len(P):
            return None
        U = P / np.linalg.norm(P, axis=1)[:, None]
        mejor = None
        for z in self.zonas:
            if not z.activa or z.bando != am.bando_obj:
                continue
            ang = np.arccos(np.clip(U @ z.u, -1, 1))
            if float(ang.min()) * R <= z.r + C.MARGEN_SOBREVUELO and (mejor is None or z.valor > mejor.valor):
                mejor = z
        return mejor

    def valor_amenaza(self, am, margen=None):
        lat, lon = am.impacto_est()
        if am.respuesta:
            return 0.0
        m = max(am.sigma() * 1.5, C.MARGEN_CERCA) if margen is None else margen
        if am.nuclear:
            m += C.RADIO_NUCLEAR
        v = self.valor_en(lat, lon, m, am.bando_obj)
        if am.mirv and am.final != "separada":
            v = max(v, self.valor_en(lat, lon, m + 150.0, am.bando_obj)) * am.mirv[0]
        if v <= 0:
            z = self.sobrevuelo(am)
            if z is not None:
                v = z.valor
        return v * (C.FACTOR_NUCLEAR if am.nuclear else 1.0)

    def _amenazante(self, am):
        if am.respuesta:
            return 0.0
        v = self.valor_en(*am.B, C.RADIO_NUCLEAR if am.nuclear else 0.0, am.bando_obj)
        if am.mirv and am.final != "separada":
            v *= am.mirv[0]
        return v * (C.FACTOR_NUCLEAR if am.nuclear else 1.0)

    def _objetivo_campo(self, centro=None, rmin=60.0, rmax=400.0, activas=None):
        activas = self.zonas_activas() if activas is None else activas
        for _ in range(60):
            if centro is None:
                if not activas:
                    return None
                z = activas[int(self.rng.integers(len(activas)))]
                c = (z.lat, z.lon)
            else:
                c = centro
            d = float(self.rng.uniform(rmin, rmax))
            la, lo = M.destino(c[0], c[1], float(self.rng.uniform(0, 360)), d)
            if self.valor_en(la, lo, 25.0) <= 0:
                return la, lo
        return None

    def _atacante_de(self, o):
        b = o.get("bando")
        if b in self.ataca and self.enemigas(b, o.get("contra")):
            return b
        lista = self.atacantes()
        return lista[int(self.rng.integers(len(lista)))] if lista else None

    def _objetivo(self, o, atacante):
        activas = self.enemigas(atacante, o.get("contra"))
        if o.get("objetivos"):
            activas = [z for z in activas if z.nombre in o["objetivos"]] or activas
        if not activas:
            return None, None, None
        modo = o.get("modo", "mixto")
        if modo == "activo":
            bandos = {z.bando for z in activas}
            fijos = [a for a in self.vivos() if a.tipo != "buque" and a.bando in bandos]
            if fijos:
                a = fijos[int(self.rng.integers(len(fijos)))]
                return M.desplazar(a.lat, a.lon, *self.rng.normal(0, 3, 2)), a.nombre, a.bando
        pesos = np.array([z.valor for z in activas])
        z = activas[int(self.rng.choice(len(activas), p=pesos / pesos.sum()))]
        if modo == "zonas" or self.rng.uniform() < o.get("p_zona", 0.6):
            r = z.r * 0.8 * math.sqrt(self.rng.uniform())
            return M.destino(z.lat, z.lon, float(self.rng.uniform(0, 360)), r), z.nombre, z.bando
        p = self._objetivo_campo(centro=(z.lat, z.lon))
        return (p, "campo abierto", z.bando) if p is not None else (None, None, None)

    def _origen(self, tipo, Bp, origen):
        lo, hi = C.TIPOS[tipo]["rango"]
        for _ in range(60):
            la, lon = M.punto_origen(self.rng, origen)
            if lo <= M.distancia(la, lon, *Bp) <= hi:
                return la, lon
        return None

    def _crear(self, o, tp, A, Bp, nombre, org, atacante="", objetivo=""):
        self.n_id += 1
        am = Amenaza(self.n_id, tp, A, Bp, self.t, self.rng, nombre, M.ORIGENES[org]["nombre"], bando_atk=atacante,
                     bando_obj=objetivo)
        oj, sen = int(o.get("ojivas", 1)), int(o.get("senuelos", 0))
        if (oj > 1 or sen > 0) and tp not in ("corto", "planeador"):
            am.mirv = (max(oj, 1), sen)
            am.t_sep = am.t_motor_fin + float(self.rng.uniform(30, 90))
            am.t_sep = min(am.t_sep, am.t0 + 0.35 * am.T)
        p_nuc = float(o.get("nuclear", self.m.get("nuclear", 0.0)) or 0.0)
        if p_nuc > 0 and self.rng.uniform() < p_nuc:
            am.nuclear = True
            self.st["nucleares"] += 1
        self.amenazas.append(am)
        self.activas.append(am)
        self.st["lanzadas"] += 1
        return am

    def lanzar(self, o):
        atacante = self._atacante_de(o)
        if atacante is None:
            return None
        Bp, nombre, objetivo = self._objetivo(o, atacante)
        if Bp is None:
            return None
        propios = [x for x, b in self.origen_bando.items() if b == atacante]
        if not propios:
            return None
        if o.get("auto_tipo") or o.get("origen") not in propios:
            org = propios[int(self.rng.integers(len(propios)))]
            A = M.punto_origen(self.rng, org)
            tp = M.tipo_para(M.distancia(*A, *Bp), o["tipo"])
            return self._crear(o, tp, A, Bp, nombre, org, atacante, objetivo) if tp else None
        origenes = [o["origen"]] + [x for x in propios if x != o["origen"]]
        preferido = o["tipo"]
        tipos = [preferido] + [t for t in ("medio", "intermedio", "icbm", "corto") if t != preferido]
        for tp in tipos:
            for org in origenes:
                A = self._origen(tp, Bp, org)
                if A is not None:
                    return self._crear(o, tp, A, Bp, nombre, org, atacante, objetivo)
        return None

    def _oleada_continua(self):
        lista = self.atacantes()
        if not lista:
            self.prox_oleada = self.t + 60
            return
        atacante = lista[int(self.rng.integers(len(lista)))]
        activas = self.enemigas(atacante)
        propios = [x for x, b in self.origen_bando.items() if b == atacante]
        n = int(self.rng.integers(2, 7))
        origen = propios[int(self.rng.integers(len(propios)))]
        cada = float(self.rng.uniform(5, 30))
        z = activas[int(self.rng.integers(len(activas)))]
        la, lo = M.punto_origen(self.rng, origen)
        d = M.distancia(la, lo, z.lat, z.lon)
        tipo = M.tipo_para(d) or "icbm"
        if self.rng.uniform() < 0.15 and C.TIPOS["planeador"]["rango"][0] <= d <= C.TIPOS["planeador"]["rango"][1]:
            tipo = "planeador"
        mirv = self.m.get("mirv", True) and tipo in ("medio", "intermedio", "icbm") and self.rng.uniform() < 0.4
        o = {"tipo": tipo, "origen": origen, "p_zona": float(self.rng.uniform(0.5, 0.9)), "auto_tipo": True,
             "bando": atacante,
             "ojivas": int(self.rng.integers(2, 5)) if mirv else 1, "senuelos": int(self.rng.integers(1, 4)) if mirv else 0}
        for k in range(n):
            self.programa.append((self.t + k * cada + self.rng.uniform(0, 3), o))
        self.programa.sort(key=lambda p: p[0])
        self.prox_oleada = self.t + n * cada + self.rng.uniform(240, 900) / max(len(lista), 1) ** 0.5

    def _separar(self, am):
        oj, sen = am.mirv
        hijos = []
        for k in range(oj + sen):
            senuelo = k >= oj
            if k == 0:
                destino = (M.desplazar(am.B[0], am.B[1], *self.rng.normal(0, 4, 2)), am.objetivo)
            elif not senuelo:
                cerca = [z for z in self.zonas_activas() if z.bando == am.bando_obj and M.distancia(z.lat, z.lon, *am.B) < 700]
                if cerca and self.rng.uniform() < 0.6:
                    z = cerca[int(self.rng.integers(len(cerca)))]
                    destino = (M.destino(z.lat, z.lon, float(self.rng.uniform(0, 360)), z.r * 0.7 * math.sqrt(self.rng.uniform())), z.nombre)
                else:
                    p = self._objetivo_campo(am.B, 40, 220) or M.destino(am.B[0], am.B[1], float(self.rng.uniform(0, 360)), 150)
                    destino = (p, "campo abierto")
            else:
                destino = (M.destino(am.B[0], am.B[1], float(self.rng.uniform(0, 360)), float(self.rng.uniform(0, 160))), "")
            self.n_id += 1
            h = Amenaza(self.n_id, am.tipo, am.A, destino[0], am.t0, self.rng, destino[1], am.origen, padre=am,
                        senuelo=senuelo)
            h.racimo = (oj, oj + sen)
            h.detectada = am.detectada
            h.t_detectada = self.t if am.detectada else None
            h.n_act = am.n_act * 0.5
            hijos.append(h)
        am.viva = False
        am.final = "separada"
        self.st["separaciones"] += 1
        self.st["senuelos"] += sen
        self.amenazas.extend(hijos)
        self.activas.extend(hijos)
        libres = sorted(hijos, key=lambda h: h.senuelo)
        for it in self.interceptores:
            if it.activo and it.am is am:
                am.en_vuelo -= 1
                if libres:
                    nuevo = libres.pop(0)
                    it.am = nuevo
                    nuevo.en_vuelo += 1
                    nuevo.disparos += 1
                elif not self._redirigir(it):
                    it.activo = False
                    it.resultado = "abortado"
        if am.detectada:
            self.log(f"¡#{am.id} se dividió en {oj} ojiva{'s' if oj > 1 else ''}"
                     f"{f' y {sen} señuelo' + ('s' if sen > 1 else '') if sen else ''}!", ROJO)

    def _fijar(self, am):
        if am.fijada:
            return
        if self.valor_amenaza(am) > 0:
            am.fijada = True
            am.t_fijada = self.t
            if self.bitacora is not None:
                z = self.sobrevuelo(am)
                extra = f" · sobrevuela {z.nombre}" if z is not None and self.valor_en(*am.impacto_est(), am.sigma() * 0.6, am.bando_obj) <= 0 else ""
                self.log(f"OBJETIVO FIJADO #{am.id} {am.nombre()}{extra}", ROJO)

    def ayudan(self, am):
        clave = (am.bando_obj, am.bando_atk)
        cache = self.__dict__.setdefault("_ayudan", {})
        if clave not in cache:
            cache[clave] = {b["nombre"] for b in self.bandos if b["nombre"] == am.bando_obj or (
                b["nombre"] != am.bando_atk and am.bando_obj not in b["ataca"])}
        return cache[clave]

    def _grupos(self, bando=None, ayudan=None):
        grupos = {}
        for a in self.operativos():
            if a.capa is None or sum(a.misiles) <= 0:
                continue
            if ayudan is not None and a.bando not in ayudan:
                continue
            if ayudan is None and bando is not None and a.bando != bando:
                continue
            grupos.setdefault(a.capa, []).append(a)
        return {c: (np.array([a.S for a in acts]), acts) for c, acts in grupos.items()}

    def solucion(self, am, grupos=None):
        if grupos is None:
            grupos = self._grupos(ayudan=self.ayudan(am))
        t = self.t
        tf = am.t_impacto - 2.0
        if am.mirv and am.final is None and am.t_sep:
            tf = min(tf, am.t_sep - 1.0)
        if tf - t < 6 or not grupos:
            return None
        n = int(min(max((tf - t) / 4.0, 10), 140))
        ts = np.linspace(t + 2.0, tf, n)
        if tf - t > 100:
            ts = np.union1d(ts, np.arange(tf - 90.0, tf, 1.5))
        P = am.pos_vec(ts)
        alt = np.linalg.norm(P, axis=1) - R
        opciones = []
        futuras = {}
        mallas = []
        for capa, (S, acts) in grupos.items():
            c = C.CAPAS[capa]
            D = np.linalg.norm(P[None, :, :] - S[:, None, :], axis=2)
            geo = (D <= c["alcance"]) & (alt >= c["alt"][0]) & (alt <= c["alt"][1])
            if capa == "impulso":
                if am.padre is not None:
                    continue
                geo &= (ts < am.t_motor_fin)[None, :]
            col = geo.any(0)
            if not col.any():
                continue
            futuras[capa] = float(ts[col].max())
            vuelo = D / c["vel"] + c["retardo"]
            mallas.append((geo, vuelo))
            ok = geo & (vuelo <= (ts - t)[None, :])
            if not ok.any():
                continue
            pk = am.pk(capa)
            for j in range(len(acts)):
                if not ok[j].any():
                    continue
                i = int(np.argmax(ok[j]))
                ventana = float(np.max((ts - vuelo[j])[ok[j]]) - t)
                opciones.append({"t": float(ts[i]), "p": P[i].copy(), "ventana": ventana, "pk": pk, "capa": capa,
                                 "activo": acts[j], "vuelo": float(vuelo[j, i])})
        if not opciones:
            return None
        tope = 0.75 * max(o["pk"] for o in opciones)
        buenas = [o for o in opciones if o["pk"] >= tope]
        primera = min(buenas, key=lambda o: (o["t"], -o["pk"]))
        holgura = min(max(8.0, 0.08 * (primera["t"] - t)), 40.0)
        cercanas = [o for o in buenas if o["capa"] == primera["capa"] and o["t"] <= primera["t"] + holgura]
        carga = self._carga()
        sol = min(cercanas, key=lambda o: (carga.get(id(o["activo"]), 0), -round(o["activo"].stock(), 1), o["t"]))
        sol["posteriores"] = sum(1 for cp, tmax in futuras.items() if cp != sol["capa"] and tmax > sol["t"] + 10)
        sol["capas"] = tuple(futuras)
        t_look = sol["t"] + 2.0
        resto = 0.0
        for geo, vuelo in mallas:
            ok2 = geo & (vuelo <= (ts - t_look)[None, :]) & (ts > t_look)[None, :]
            if ok2.any():
                resto = max(resto, float(ts[ok2.any(0)].max()) - sol["t"])
        sol["resto"] = resto
        return sol

    def _redirigir(self, it):
        c = C.CAPAS[it.capa]
        t = self.t
        lanzado = t >= it.t_lanz
        P0 = it.pos(t) if lanzado else it.S
        h0 = float(np.linalg.norm(P0)) - R
        viejo = it.am
        mejor = None
        for am in self.activas:
            if not am.viva or not am.detectada or am.en_vuelo > 0 or am is viejo:
                continue
            if it.activo_lanz.bando not in self.ayudan(am) or am.p_ojiva() < C.P_SENUELO:
                continue
            if not am.fijada and self.valor_amenaza(am) <= 0:
                continue
            tf = am.t_impacto - 2.0
            if am.mirv and am.final is None and am.t_sep:
                tf = min(tf, am.t_sep - 1.0)
            if tf - t < 4:
                continue
            ts = np.linspace(t + 2.0, tf, int(min(max((tf - t) / 3.0, 8), 160)))
            P = am.pos_vec(ts)
            alt = np.linalg.norm(P, axis=1) - R
            D = np.linalg.norm(P - P0[None, :], axis=1)
            ok = (alt >= c["alt"][0]) & (alt <= c["alt"][1]) & (D / c["vel"] + (0.0 if lanzado else c["retardo"]) <= ts - t)
            ok &= D <= (0.6 if lanzado else 1.0) * c["alcance"]
            if not ok.any():
                continue
            i = int(np.argmax(ok))
            clave = (-self.valor_amenaza(am), float(ts[i]))
            if mejor is None or clave < mejor[0]:
                mejor = (clave, am, float(ts[i]), float(D[i]))
        if mejor is None:
            if not lanzado:
                act = it.activo_lanz
                j = int(np.argmin(act.misiles)) if act.misiles else None
                if j is not None and act.misiles[j] < act.por_lanzador:
                    act.misiles[j] += 1
                    self.st["usados"] -= 1
                    self.st["costo"] -= C.CAPAS[it.capa]["costo"]
                    self.st["por_capa"][it.capa] -= 1
                    viejo.disparos = max(0, viejo.disparos - 1)
                    it.resultado = "cancelado"
                    return False
            if lanzado:
                self.log(f"{it.activo_lanz.nombre}: #{viejo.id} ya cayó y no hay otro blanco a su alcance, el interceptor se autodestruye", GRIS)
            return False
        _, am, t_int, d = mejor
        if lanzado:
            it.S = P0.copy()
            it.h0 = max(h0, 0.0)
            it.t_lanz = t
        else:
            it.t_lanz = max(t + 0.5, t_int - d / c["vel"] - c["retardo"])
        it.am = am
        it.t_int = t_int
        it.apunte = am.pos_est(t_int)
        it.redirigido += 1
        am.en_vuelo += 1
        am.disparos += 1
        self.log(f"{it.activo_lanz.nombre} avisa: #{viejo.id} ya no es amenaza → su interceptor {C.CAPAS[it.capa]['corto']} "
                 f"se redirige a {am.nombre()} #{am.id}", CIAN)
        return True

    def salva_max(self, sol=None):
        return 2 if self.m.get("salva", "una") == "doble" else 1

    def _carga(self):
        if getattr(self, "_carga_t", None) != (self.t, self.n_int):
            carga = {}
            for it in self.interceptores:
                if it.activo:
                    carga[id(it.activo_lanz)] = carga.get(id(it.activo_lanz), 0) + 1
            self._carga_cache = carga
            self._carga_t = (self.t, self.n_int)
        return self._carga_cache

    def disparar(self, am, n=1, sol=None):
        if not am.viva:
            return 0
        if self.salva_max() == 1:
            if am.en_vuelo > 0:
                return 0
            n = min(int(n), 1)
        hechos = 0
        for k in range(int(n)):
            if sol is None or sum(sol["activo"].misiles) <= 0 or not sol["activo"].operativa:
                sol = self.solucion(am)
            if sol is None:
                break
            act = sol["activo"]
            i = int(np.argmax(act.misiles))
            if act.misiles[i] <= 0:
                sol = None
                continue
            act.misiles[i] -= 1
            self.n_int += 1
            t_int = sol["t"] + 2.0 * hechos
            capa = sol["capa"]
            t_lanz = max(self.t + 0.5 + 1.5 * hechos, t_int - sol.get("vuelo", 0.0))
            it = Interceptor(self.n_int, act, am, t_lanz, t_int, am.pos_est(t_int), capa)
            self.interceptores.append(it)
            am.en_vuelo += 1
            am.disparos += 1
            self.st["usados"] += 1
            self.st["costo"] += C.CAPAS[capa]["costo"]
            self.st["por_capa"][capa] += 1
            hechos += 1
        if hechos:
            capa = C.CAPAS[sol["capa"]]["corto"] if sol else ""
            self.log(f"Interceptor{'es' if hechos > 1 else ''} {capa} ×{hechos} → {am.nombre()} #{am.id}", CIAN)
        return hechos

    def _muerte_senuelo(self, am):
        self.st["desperdicio"] += am.disparos

    def _resolver_interceptor(self, it):
        am = it.am
        it.activo = False
        am.en_vuelo -= 1
        if not am.viva:
            if self._redirigir(it):
                it.activo = True
                return
            it.resultado = "abortado"
            return
        real = am.pos(it.t_int)
        apunte = am.pos_est(it.t_int)
        error = float(np.linalg.norm(real - apunte))
        c = C.CAPAS[it.capa]
        pk = am.pk(it.capa)
        if error > c["correccion"]:
            pk *= max(0.05, 1 - (error - c["correccion"]) / (2 * c["correccion"]))
        la, lo, alt = M.latlon(real)
        if self.rng.uniform() < pk:
            am.viva = False
            am.final = "interceptada"
            it.resultado = "derribo"
            self.st["interceptadas"] += 1
            self.explosiones.append((la, lo, alt, self.t, "derribo"))
            if am.senuelo:
                self.st["senuelos_derribados"] += 1
                self._muerte_senuelo(am)
                self.log(f"Se destruyó un señuelo (#{am.id}) a {alt:.0f} km", AMBAR)
                return
            v = self._amenazante(am)
            if v > 0:
                self.st["salvado"] += v
                self.st["potencial"] += v
            elif not am.fijada:
                self.st["desperdicio"] += am.disparos
            if am.mirv and am.final == "interceptada" and am.t_sep and self.t < am.t_sep:
                self.log(f"¡Intercepción de #{am.id} antes de separarse: {am.mirv[0]} ojivas eliminadas a {alt:.0f} km!", VERDE)
            else:
                self.log(f"Intercepción {c['corto']} de #{am.id} a {alt:.0f} km de altura", VERDE)
        else:
            it.resultado = "fallo"
            self.st["fallos"] += 1
            am.fallos = getattr(am, "fallos", 0) + 1
            if am.fijada and am.en_vuelo == 0:
                self.prox_decision = self.t
                if am.t_impacto - self.t > 3:
                    self.log(f"#{am.id} sigue fijado: nuevo disparo", ROJO)
            la2, lo2, alt2 = M.latlon(it.pos(it.t_int))
            self.explosiones.append((la2, lo2, alt2, self.t, "fallo"))
            self.log(f"Fallo {c['corto']} contra #{am.id}", AMBAR)

    def _reentrada(self, am):
        if am.senuelo:
            am.viva = False
            am.final = "quemado"
            self.st["quemados"] += 1
            self._muerte_senuelo(am)
            if am.detectada:
                self.log(f"El señuelo #{am.id} se desintegró al reentrar en la atmósfera", GRIS)
        else:
            am.disc = 1.0

    def _impacto_respuesta(self, am):
        self.st["contra_impactos"] += 1
        self.impactos.append((am.B[0], am.B[1], self.t, False))
        self.explosiones.append((am.B[0], am.B[1], 0.0, self.t, "contra"))
        self.log(f"CONTRAATAQUE de {am.bando_atk}: impacto en {am.objetivo} de {am.bando_obj} (#{am.id})", VERDE)

    def _detonacion(self, am):
        self.st["nucleares_impacto"] += 1
        self.explosiones.append((am.B[0], am.B[1], 0.0, self.t, "nuclear"))
        arrasadas = [z for z in self.zonas if z.activa and z.bando == am.bando_obj and z.contiene(*am.B, C.RADIO_NUCLEAR)]
        for z in arrasadas:
            z.activa = False
        for a in self.vivos():
            if a.bando == am.bando_obj and M.distancia(a.lat, a.lon, *am.B) <= C.RADIO_NUCLEAR:
                a.estado = "destruida"
                a.impactos += 1
        if arrasadas:
            self.log(f"DETONACIÓN NUCLEAR: {', '.join(z.nombre for z in arrasadas)} quedó arrasada", ROJO)
        else:
            self.log(f"Detonación nuclear en campo abierto (#{am.id})", AMBAR)

    def _impacto(self, am):
        am.viva = False
        am.final = "impacto"
        if am.respuesta:
            self._impacto_respuesta(am)
            return
        v = self._amenazante(am)
        z = self.zona_en(*am.B, 0.0, am.bando_obj)
        act = self.activo_cerca(am.B[0], am.B[1], C.RADIO_ACTIVO_PELIGRO, am.bando_obj)
        if v > 0:
            self.st["dano"] += v
            self.st["potencial"] += v
            self.st["impactos_zona"] += 1
            lugar = z.nombre if z is not None else (f"el activo {act.nombre}" if act else "un activo")
            self.log(f"IMPACTO en {lugar} ({am.nombre()} #{am.id})", ROJO)
            if act is not None:
                act.impactos += 1
                act.estado = "destruida"
                self.log(f"El activo {act.nombre} ({act.q['nombre']}) quedó fuera de combate", ROJO)
        else:
            self.st["impactos_campo"] += 1
            if am.disparos == 0:
                self.st["ignoradas_bien"] += 1
            elif not am.fijada:
                self.st["desperdicio"] += am.disparos
            self.log(f"#{am.id} cayó en campo abierto", GRIS)
        self.impactos.append((am.B[0], am.B[1], self.t, v > 0))
        self.explosiones.append((am.B[0], am.B[1], 0.0, self.t, "impacto"))
        if am.nuclear:
            self._detonacion(am)

    def _contraatacar(self):
        lanzados = 0
        for b in self.bandos:
            nombre = b["nombre"]
            recibidos = [am for am in self.amenazas if am.bando_obj == nombre and not am.senuelo and not am.respuesta
                         and am.final in ("interceptada", "impacto") and (am.fijada or am.final == "interceptada")]
            if len(recibidos) < 3:
                continue
            tasa = sum(1 for am in recibidos if am.final == "interceptada") / len(recibidos)
            atacantes = sorted({am.bando_atk for am in recibidos if am.bando_atk and am.bando_atk != nombre})
            if not atacantes:
                continue
            if tasa < C.CONTRA_MIN:
                self.log(f"{nombre} derribó el {100 * tasa:.0f} % de los misiles: no llega al 90 %, no puede contraatacar", GRIS)
                continue
            propias = [z for z in self.zonas if z.bando == nombre and z.activa] or [z for z in self.zonas if z.bando == nombre]
            if not propias:
                continue
            self.log(f"{nombre} derribó el {100 * tasa:.0f} % de los misiles: CONTRAATAQUE AUTOMÁTICO contra "
                     f"{', '.join(atacantes)}", VERDE)
            for atk in atacantes:
                blancos = [(M.centro_origen(o), "base de lanzamiento") for o, bb in self.origen_bando.items() if bb == atk]
                blancos += [((z.lat, z.lon), z.nombre) for z in self.zonas if z.bando == atk and z.activa]
                if not blancos:
                    continue
                suyos = sum(1 for am in recibidos if am.bando_atk == atk)
                n = int(min(C.CONTRA_MAX, max(2, round(suyos / 3))))
                for k in range(n):
                    z = propias[k % len(propias)]
                    A = M.destino(z.lat, z.lon, float(self.rng.uniform(0, 360)), float(self.rng.uniform(40, 160)))
                    (bl, bo), etiqueta = blancos[k % len(blancos)]
                    Bp = M.destino(bl, bo, float(self.rng.uniform(0, 360)), float(self.rng.uniform(0, 50)))
                    tp = M.tipo_para(M.distancia(*A, *Bp), "icbm")
                    if tp is None:
                        continue
                    self.n_id += 1
                    am = Amenaza(self.n_id, tp, A, Bp, self.t + 3.0 * k, self.rng, etiqueta, nombre,
                                 bando_atk=nombre, bando_obj=atk)
                    am.respuesta = True
                    am.detectada = True
                    am.t_detectada = self.t
                    self.amenazas.append(am)
                    self.activas.append(am)
                    self.st["contra_lanzados"] += 1
                    lanzados += 1
        return lanzados

    def contexto(self, cands):
        tis = []
        for am, sol in cands:
            if self.valor_amenaza(am) > 0:
                tis.append(am.t_impacto - self.t)
        tis.sort()
        return {"stock": {c: self.stock(c) for c in C.ORDEN_CAPAS}, "activas": len(self.activas),
                "amenazantes": len(tis), "tis": tis}

    def _decidir(self):
        cache = {}
        cands = []
        for am in self.activas:
            if am.detectada and am.en_vuelo == 0 and not am.respuesta:
                clave = (am.bando_obj, am.bando_atk)
                if clave not in cache:
                    cache[clave] = self._grupos(ayudan=self.ayudan(am))
                cands.append((am, self.solucion(am, cache[clave])))
        if not cands:
            return
        ctx = self.contexto(cands)
        ordenes = list(self.controlador.decidir(self, cands, ctx) or [])
        ya = {am.id for am, _ in ordenes}
        auto = getattr(self.controlador, "automatico", True)
        pendientes = [(am, sol) for am, sol in cands if am.id not in ya and sol is not None and (auto or am.fijada)]
        if pendientes:
            ordenes += self._obligado.decidir(self, pendientes, ctx)
        sols = {am.id: sol for am, sol in cands}
        if self.demos_x is not None:
            elegido = {am.id: n for am, n in ordenes}
            for am, sol in cands:
                if sol is None:
                    continue
                self.demos_x.append(B.caracteristicas(self, am, sol, ctx))
                self.demos_y.append(B.objetivo(elegido.get(am.id, 0)))
        for am, n in ordenes:
            sol = sols.get(am.id)
            if sol is not None and sol["t"] - sol.get("vuelo", 0.0) - self.t > C.ESPERA_MAX:
                continue
            self.disparar(am, min(int(n), self.salva_max(sol)), sol)

    def _radar(self):
        radares = [a for a in self.operativos() if a.radar > 0]
        if not self.activas:
            return
        S = np.array([a.S for a in radares]) if radares else np.zeros((0, 3))
        alc = np.array([a.radar for a in radares])
        esp = np.array([a.tipo == "radar" for a in radares])
        rb = [a.bando for a in radares]
        P = np.array([am.pos(self.t) for am in self.activas])
        if len(radares):
            V = P[:, None, :] - S[None, :, :]
            D = np.linalg.norm(V, axis=2)
            arriba = np.einsum("ijk,jk->ij", V, S) >= 0
            ve = (D <= alc[None, :]) & arriba & np.array([[b in self.ayudan(am) for b in rb] for am in self.activas])
        else:
            ve = np.zeros((len(P), 0), dtype=bool)
        hay_ir, ir, hay_lo, lo = self.sats.ver(P, self.t)
        for k, am in enumerate(self.activas):
            visto = bool(ve[k].any()) if ve.shape[1] else False
            sat = bool(hay_ir[k]) and am.padre is None and am.t_sat <= self.t < am.t_motor_fin
            seg = bool(hay_lo[k]) and float(np.linalg.norm(P[k])) - R >= C.SAT_SEG_ALT
            if sat:
                am.sat_vis = ("ir", int(ir[k]), self.t)
            elif seg:
                am.sat_vis = ("leo", int(lo[k]), self.t)
            if visto:
                am.n_act += 1
                am.disc = min(1.0, am.disc + C.DISC_RADAR + (C.DISC_ESPECIAL if (ve[k] & esp).any() else 0.0))
            elif sat:
                am.n_act += C.SAT_AVANCE
            elif seg:
                am.n_act += C.SAT_SEGUIMIENTO
            if seg and not visto:
                am.disc = min(1.0, am.disc + C.DISC_SAT)
            if (visto or sat or seg) and not am.detectada:
                am.detectada = True
                am.t_detectada = self.t
                self.st["detectadas"] += 1
                if self.bitacora is not None:
                    la, lo_ = am.impacto_est()
                    z = self.zona_en(la, lo_, am.sigma() * 0.6, am.bando_obj)
                    dest = z.nombre if z else ("un activo" if self.valor_en(la, lo_, 0.0, am.bando_obj) else "campo abierto")
                    fuente = "radar" if visto else ("satélite infrarrojo" if sat else "satélite de seguimiento")
                    quien = f"{am.bando_atk} ({am.origen})" if am.bando_atk and am.bando_atk != am.origen else am.origen
                    self.log(f"Lanzamiento de {quien}: {am.nombre()} #{am.id} → {dest} "
                             f"({(am.t_impacto - self.t) / 60:.0f} min · {fuente})", ROJO if dest != "campo abierto" else GRIS)
            if am.detectada:
                self._fijar(am)

    def proximo_evento(self):
        prox = [self.duracion]
        if self.programa:
            prox.append(self.programa[0][0])
        if self.continuo:
            prox.append(self.prox_oleada)
        return min(prox)

    def paso(self):
        if self.terminado:
            return
        self.calma = not self.activas and not self.interceptores and self.proximo_evento() - self.t > 8.0
        dt = C.DT
        if self.calma:
            dt = max(C.DT, min(C.CALMA_MAX, self.proximo_evento() - self.t - 4.0))
        self.t += dt
        if self.continuo and self.t >= self.prox_oleada and self.t < self.duracion:
            self._oleada_continua()
        while self.programa and self.programa[0][0] <= self.t:
            _, o = self.programa.pop(0)
            self.lanzar(o)
        for a in self.activos:
            a.paso(dt)
        for am in list(self.activas):
            if am.viva and am.mirv and am.final is None and self.t >= am.t_sep:
                self._separar(am)
        for am in self.activas:
            if am.viva and self.t >= am.t_reentrada and not getattr(am, "_reentro", False):
                am._reentro = True
                self._reentrada(am)
        self.activas = [am for am in self.activas if am.viva]
        if self.t >= self.prox_radar:
            self.prox_radar = self.t + C.RADAR_PERIODO
            self._radar()
            for it in self.interceptores:
                if it.activo and it.am.viva and it.am.detectada and self.t < it.t_int:
                    it.apunte = it.am.pos_est(it.t_int)
        if self.t >= self.prox_decision:
            cerca = any(am.detectada and am.t_impacto - self.t < 150 for am in self.activas)
            self.prox_decision = self.t + (C.DECIDIR_CERCA if cerca else C.DECIDIR_CADA)
            self._decidir()
        for it in self.interceptores:
            if not it.activo:
                continue
            if not it.am.viva:
                it.am.en_vuelo -= 1
                if self._redirigir(it):
                    continue
                it.activo = False
                it.resultado = "abortado"
                la, lo, alt = M.latlon(it.pos(self.t))
                self.explosiones.append((la, lo, alt, self.t, "aborto"))
                continue
            if self.t >= it.t_int:
                self._resolver_interceptor(it)
        self.interceptores = [it for it in self.interceptores if it.activo]
        for am in self.activas:
            if am.viva and self.t >= am.t_impacto:
                self._impacto(am)
        self.activas = [am for am in self.activas if am.viva]
        if len(self.explosiones) > 400:
            self.explosiones = [e for e in self.explosiones if self.t - e[3] < 30]
        fin = self.t >= self.duracion and not self.activas and not self.interceptores
        if self.continuo:
            fin = self.t >= self.duracion
        if fin and not self.contra_hecho and self.bitacora is not None and self.m.get("contraataque", True):
            self.contra_hecho = True
            if self._contraatacar():
                self.duracion = self.t
        if any(am.respuesta for am in self.activas) and self.t < self.duracion + 3600:
            fin = False
        if fin or self.t >= self.duracion + 3600:
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
        caidos = sum(1 for a in self.activos if a.destruida)
        aptitud = (C.PREMIO_SALVADO * st["salvado"] - C.CASTIGO_DANO * st["dano"]
                   - C.COSTO_INTERCEPTOR * st["costo"] - C.CASTIGO_ACTIVO * caidos)
        prot = self.proteccion()
        superada = prot >= C.PROTECCION_MIN and self.desperdicio() <= C.DESPERDICIO_MAX and not caidos
        r = {k: v for k, v in st.items() if k != "por_capa"}
        r.update({"aptitud": float(aptitud), "proteccion": float(prot), "desperdicio_frac": float(self.desperdicio()),
                  "superada": bool(superada), "destruida": bool(caidos), "t": self.t})
        return r
