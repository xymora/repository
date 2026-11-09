import math
import random

import config as C
from misiones import cargar_mision

W, H = C.ANCHO_VISTA, C.ALTO_VISTA
NADA = (0, 0, False, False)
TIPOS = {
    "caza": (8, 7, 1, 100),
    "bombardero": (15, 11, 10, 800),
    "pesado": (26, 18, 30, 2000),
    "torreta": (7, 7, 12, 500),
    "jefe": (40, 22, 60, 5000),
}
POWS = ("A", "A", "E", "R")


class Jugador:
    def __init__(self):
        self.x, self.y = W / 2, H - 40
        self.vx = self.vy = 0.0
        self.vidas = C.VIDAS
        self.rizos = C.RIZOS
        self.arma = 1
        self.escoltas = 0
        self.rodando = 0
        self.invulnerable = C.INVULNERABLE
        self.cadencia = 0
        self.rizo_previo = False
        self.muerto = self.fuera = False
        self.espera = 0
        self.muertes = self.bajas = self.puntos = self.dano_jefe = 0
        self.rizos_usados = 0

    @property
    def activo(self):
        return not self.muerto and not self.fuera

    @property
    def vulnerable(self):
        return self.activo and self.invulnerable <= 0 and self.rodando <= 0

    def posiciones_escoltas(self):
        return [(self.x + d, self.y + 5) for d in (-20, 20)[:self.escoltas]]


class Bala:
    __slots__ = ("x", "y", "vx", "vy", "dueno", "dano", "radio", "vida", "cerca", "pego", "tipo")

    def __init__(self, x, y, vx, vy, dueno=None, dano=1, radio=2.5, tipo="e"):
        self.x, self.y, self.vx, self.vy = x, y, vx, vy
        self.dueno, self.dano, self.radio, self.tipo = dueno, dano, radio, tipo
        self.vida = 260
        self.cerca = 1e9
        self.pego = False


class Enemigo:
    def __init__(self, tipo, x, y, patron, t, datos=None, hp=None):
        hw, hh, vida, puntos = TIPOS[tipo]
        self.tipo, self.x, self.y, self.patron = tipo, x, y, patron
        self.hw, self.hh = hw, hh
        self.hp = self.hp_max = hp or vida
        self.puntos = puntos
        self.vx = self.vy = 0.0
        self.t0 = t
        self.datos = datos or {}
        self.vivo = True
        self.entro = False
        self.golpe = 0

    @property
    def angulo(self):
        if abs(self.vx) + abs(self.vy) < 1e-6:
            return math.pi / 2
        return math.atan2(self.vy, self.vx)


class Item:
    def __init__(self, x, y, letra):
        self.x, self.y, self.x0, self.letra = x, y, x, letra
        self.t = 0


class Partida:
    def __init__(self, numero, controladores, semilla, limites=True):
        self.mision = m = cargar_mision(numero)
        self.numero = m.numero
        self.rng = random.Random(semilla)
        self.controladores = list(controladores)
        self.jugadores = [Jugador() for _ in self.controladores]
        self.acciones = [NADA] * len(self.jugadores)
        self.limites = limites
        self.enemigos, self.balas, self.items, self.efectos = [], [], [], []
        self.siguiente = 0
        self.t = 0
        self.scroll = 0.0
        self.escuadras = {}
        self.n_escuadra = 0
        self.jefe_activo = self.jefe_vencido = False
        self.jefe = None
        self.t_jefe = self.t_vencido = self.ultimo_dano_jefe = 0
        self.dano_jefe_total = 0
        self.esquives = 0
        self.terminada = self.superada = False
        self.motivo = ""

    def paso(self):
        if self.terminada:
            return
        if self.t % C.DECIDIR_CADA == 0:
            for i, (j, control) in enumerate(zip(self.jugadores, self.controladores)):
                if j.activo and getattr(control, "cada", C.DECIDIR_CADA) != 1:
                    self.acciones[i] = control.decidir(self, j)
        for i, (j, control) in enumerate(zip(self.jugadores, self.controladores)):
            if j.activo and getattr(control, "cada", C.DECIDIR_CADA) == 1:
                self.acciones[i] = control.decidir(self, j)
            self._jugador(j, self.acciones[i] if j.activo else NADA)
        self._aparecer()
        for e in self.enemigos:
            if e.vivo:
                getattr(self, "_ia_" + e.tipo)(e)
                e.golpe = max(0, e.golpe - 1)
        self._balas()
        self._items()
        self._colisiones()
        self.enemigos = [e for e in self.enemigos if e.vivo]
        self.efectos = [f for f in self.efectos if self.t - f[3] < 30]
        self.t += 1
        self.scroll += C.VEL_FONDO
        self._fin()

    def _fin(self):
        if self.jefe_vencido and self.t - self.t_vencido > 60:
            self._terminar("misión cumplida", True)
        elif all(j.fuera for j in self.jugadores):
            self._terminar("derribado")
        elif not self.limites:
            return
        elif self.jefe_activo and not self.jefe_vencido and self.t - self.ultimo_dano_jefe > C.JEFE_SIN_DANO_MAX:
            self._terminar("no dañaron al jefe")
        elif self.t > self.mision.duracion + C.TIEMPO_EXTRA_JEFE:
            self._terminar("tiempo agotado")

    def _terminar(self, motivo, superada=False):
        self.terminada, self.superada, self.motivo = True, superada, motivo

    def _jugador(self, j, acciones):
        if j.fuera:
            return
        if j.muerto:
            j.espera -= 1
            if j.espera <= 0:
                if j.vidas > 0:
                    j.muerto = False
                    j.x, j.y = W / 2, H - 40
                    j.invulnerable = C.INVULNERABLE
                    j.rizos = max(j.rizos, C.RIZOS)
                else:
                    j.fuera = True
            return
        mx, my, disparo, rizo = acciones
        j.invulnerable = max(0, j.invulnerable - 1)
        j.cadencia = max(0, j.cadencia - 1)
        j.rodando = max(0, j.rodando - 1)
        factor = 0.7071 if mx and my else 1.0
        j.vx, j.vy = mx * C.VEL_JUGADOR * factor, my * C.VEL_JUGADOR * factor
        j.x = min(max(j.x + j.vx, 12), W - 12)
        j.y = min(max(j.y + j.vy, 24), H - 14)
        if rizo and not j.rizo_previo and j.rizos > 0 and j.rodando == 0:
            j.rizos -= 1
            j.rizos_usados += 1
            j.rodando = C.DURACION_RIZO
        j.rizo_previo = rizo
        if disparo and j.cadencia == 0 and j.rodando == 0:
            self._disparar(j)

    def _disparar(self, j):
        v = -C.VEL_BALA
        salidas = [(-3, 0.0), (3, 0.0)]
        if j.arma >= 2:
            salidas += [(-9, 0.0), (9, 0.0)]
        if j.arma >= 3:
            salidas += [(-6, -0.22), (6, 0.22)]
        for dx, ang in salidas:
            self.balas.append(Bala(j.x + dx, j.y - 10, v * math.sin(ang) * -1, v * math.cos(ang), j, 1, 3, "j"))
        for ex, ey in j.posiciones_escoltas():
            self.balas.append(Bala(ex, ey - 6, 0.0, v, j, 1, 3, "j"))
        j.cadencia = C.CADENCIA

    def _aparecer(self):
        m = self.mision
        if not self.jefe_activo:
            while self.siguiente < len(m.oleadas) and m.oleadas[self.siguiente].t <= self.t:
                self._oleada(m.oleadas[self.siguiente])
                self.siguiente += 1
            if self.t >= m.duracion:
                self._activar_jefe()

    def _oleada(self, o):
        m = self.mision
        x = min(max(o.x + self.rng.uniform(-18, 18), 30), W - 30)
        if o.patron in ("bombardero", "pesado"):
            for i in range(o.n):
                hp = round(TIPOS[o.patron][2] * (1 + 0.1 * m.numero))
                y = -20 if o.patron == "bombardero" else H + 30
                xi = min(max(x + i * 70 * o.lado, 30), W - 30)
                e = Enemigo(o.patron, xi, y - i * 30, o.patron, self.t, {"x0": xi}, hp)
                self.enemigos.append(e)
            return
        self.n_escuadra += 1
        grupo = self.n_escuadra
        if o.roja:
            self.escuadras[grupo] = o.n
        for i in range(o.n):
            datos = {"x0": x, "i": i, "lado": o.lado, "grupo": grupo if o.roja else 0, "roja": o.roja}
            if o.patron == "picada":
                e = Enemigo("caza", min(max(x + (i - o.n / 2) * 22, 12), W - 12), -12 - i * 6, "picada", self.t, datos)
            elif o.patron == "curva":
                e = Enemigo("caza", x, -12 - i * 20, "curva", self.t, datos)
            elif o.patron == "rizo":
                datos["giro"] = 80 + self.rng.uniform(0, 50)
                e = Enemigo("caza", x, -12 - i * 18, "rizo", self.t, datos)
            elif o.patron == "trasera":
                e = Enemigo("caza", min(max(x + i * 16 * o.lado, 12), W - 12), H + 14 + i * 18, "trasera", self.t, datos)
            else:
                xi = -12 - i * 20 if o.lado > 0 else W + 12 + i * 20
                datos["y0"] = 40 + self.rng.uniform(0, 70)
                e = Enemigo("caza", xi, datos["y0"], "lateral", self.t, datos)
            self.enemigos.append(e)

    def _activar_jefe(self):
        self.jefe_activo = True
        self.t_jefe = self.ultimo_dano_jefe = self.t
        spec = self.mision.jefe
        jefe = Enemigo("jefe", W / 2, -60, "jefe", self.t, dict(spec), spec["hp"])
        self.jefe = jefe
        self.enemigos.append(jefe)
        n = spec["torretas"]
        offsets = [(-34, 4), (34, 4), (-18, -10), (18, -10), (-50, 10), (50, 10)][:n]
        for k, (dx, dy) in enumerate(offsets):
            self.enemigos.append(Enemigo("torreta", jefe.x + dx, jefe.y + dy, "torreta", self.t,
                                         {"jefe": jefe, "dx": dx, "dy": dy, "desfase": k * 9}))

    def objetivo(self):
        for j in self.jugadores:
            if j.activo:
                return j
        return None

    def _apuntar(self, e, vel, abanico=0, paso=0.28, tipo="e"):
        obj = self.objetivo()
        if obj is None:
            return
        if (obj.x - e.x) ** 2 + (obj.y - e.y) ** 2 < 30 ** 2:
            return
        base = math.atan2(obj.y - e.y, obj.x - e.x)
        for k in range(-abanico, abanico + 1):
            a = base + k * paso
            self.balas.append(Bala(e.x, e.y, math.cos(a) * vel, math.sin(a) * vel, tipo=tipo))

    def _anillo(self, e, n, vel, giro=0.0):
        for k in range(n):
            a = giro + 2 * math.pi * k / n
            self.balas.append(Bala(e.x, e.y, math.cos(a) * vel, math.sin(a) * vel))

    def en_pantalla(self, e, margen=0):
        return -margen < e.x < W + margen and -margen < e.y < H + margen

    def _fuera(self, e):
        if e.entro and not self.en_pantalla(e, 40):
            e.vivo = False
        elif self.en_pantalla(e):
            e.entro = True
        elif self.t - e.t0 > 600:
            e.vivo = False

    def _ia_caza(self, e):
        m = self.mision
        d = e.datos
        k = self.t - e.t0
        obj = self.objetivo()
        if e.patron == "picada":
            e.vy = 2.6 * m.vel
            if k < 45 and obj:
                e.vx = max(-1.3, min(1.3, (obj.x - e.x) * 0.03))
        elif e.patron == "curva":
            e.vy = 1.8 * m.vel
            nx = d["x0"] + 70 * d["lado"] * math.sin(k * 0.045 * m.vel + d["i"] * 0.25)
            e.vx = nx - e.x
        elif e.patron == "rizo":
            if "centro" not in d:
                e.vx, e.vy = 0.0, 2.4 * m.vel
                if e.y >= d["giro"]:
                    d["centro"] = (e.x + 34 * d["lado"], e.y)
                    d["fase"] = math.pi if d["lado"] > 0 else 0.0
                    d["vuelta"] = 0.0
            elif d["vuelta"] < 2 * math.pi:
                w = 0.075 * m.vel
                d["vuelta"] += w
                a = d["fase"] + d["lado"] * d["vuelta"]
                cx, cy = d["centro"]
                nx, ny = cx + 34 * math.cos(a), cy - 34 * math.sin(a)
                e.vx, e.vy = nx - e.x, ny - e.y
            else:
                e.vx, e.vy = 0.0, -2.8 * m.vel
        elif e.patron == "trasera":
            e.vy = -3.3 * m.vel
            e.vx = 0.5 * d["lado"]
        else:
            e.vx = 2.4 * m.vel * d["lado"]
            e.vy = 0.35
        e.x += e.vx
        e.y += e.vy
        if obj and self.en_pantalla(e, -6) and self.rng.random() < 0.016 * m.fuego and (
                e.patron == "trasera" or e.y < obj.y - 30):
            self._apuntar(e, 2.6 * m.vel)
        self._fuera(e)

    def _ia_bombardero(self, e):
        m = self.mision
        k = self.t - e.t0
        alto = 70 + (e.datos["x0"] % 40)
        if e.y < alto and k < 400:
            e.vx, e.vy = 0.0, 0.9 * m.vel
        elif k < 400:
            e.vx, e.vy = 0.7 * math.sin(k * 0.02), 0.0
        else:
            e.vx, e.vy = 0.0, 1.2 * m.vel
        e.x = min(max(e.x + e.vx, 20), W - 20)
        e.y += e.vy
        if self.en_pantalla(e, -10) and k % max(20, int(50 / m.fuego)) == 25:
            self._apuntar(e, 2.4 * m.vel, abanico=1)
        self._fuera(e)

    def _ia_pesado(self, e):
        m = self.mision
        k = self.t - e.t0
        if e.y > 75 and k < 520:
            e.vx, e.vy = 0.0, -0.9
        elif k < 520:
            e.vx, e.vy = 0.8 * math.sin(k * 0.015), 0.0
        else:
            e.vx, e.vy = 0.0, -1.0
        e.x = min(max(e.x + e.vx, 30), W - 30)
        e.y += e.vy
        if self.en_pantalla(e, -14):
            periodo = max(18, int(40 / m.fuego))
            if k % periodo == 10:
                self._apuntar(e, 2.3 * m.vel, abanico=2, paso=0.22)
            if k % (periodo * 4) == 30:
                self._anillo(e, 10, 1.9, k * 0.1)
        if e.entro and e.y < -60:
            e.vivo = False
        elif self.en_pantalla(e):
            e.entro = True

    def _ia_jefe(self, e):
        m = self.mision
        k = self.t - e.t0
        if k < 90:
            e.y += 1.4
            e.vy = 1.4
            return
        e.vx = 0.0
        e.x = W / 2 + 75 * math.sin((k - 90) * 0.012 * m.vel)
        e.y = 66 + 10 * math.sin((k - 90) * 0.03)
        s = e.datos
        if (k + 7) % s["periodo"] == 0:
            if s["ataque"] == "apuntado":
                self._apuntar(e, 3.0 * m.vel, abanico=0)
            elif s["ataque"] == "abanico":
                self._apuntar(e, 2.6 * m.vel, abanico=2, paso=0.2)
            else:
                self._anillo(e, 12, 2.0, k * 0.07)
        if k % (s["periodo"] * 3) == 15 and e.hp < e.hp_max / 2:
            self._anillo(e, 16, 1.7, -k * 0.05)

    def _ia_torreta(self, e):
        jefe = e.datos["jefe"]
        if not jefe.vivo:
            e.vivo = False
            return
        e.x, e.y = jefe.x + e.datos["dx"], jefe.y + e.datos["dy"]
        k = self.t - e.t0
        periodo = max(26, int(60 / self.mision.fuego))
        if k > 90 and (k + e.datos["desfase"]) % periodo == 0:
            self._apuntar(e, 2.7 * self.mision.vel)

    def _balas(self):
        vivas = []
        jugadores = [j for j in self.jugadores if j.vulnerable]
        for b in self.balas:
            b.x += b.vx
            b.y += b.vy
            b.vida -= 1
            if b.dueno is None:
                for j in jugadores:
                    d = math.hypot(b.x - j.x, b.y - j.y)
                    if d < b.cerca:
                        b.cerca = d
            dentro = -10 < b.x < W + 10 and -14 < b.y < H + 10
            if b.vida > 0 and dentro:
                vivas.append(b)
            elif b.dueno is None and not b.pego and b.cerca < C.DISTANCIA_ESQUIVE:
                self.esquives += 1
        self.balas = vivas

    def _items(self):
        vivos = []
        for it in self.items:
            it.t += 1
            it.y += 0.7
            it.x = it.x0 + 14 * math.sin(it.t * 0.06)
            tomado = False
            for j in self.jugadores:
                if j.activo and abs(j.x - it.x) < 14 and abs(j.y - it.y) < 14:
                    self._recoger(j, it.letra)
                    tomado = True
                    break
            if not tomado and it.y < H + 12:
                vivos.append(it)
        self.items = vivos

    def _recoger(self, j, letra):
        if letra == "A":
            j.arma = min(3, j.arma + 1)
        elif letra == "E":
            j.escoltas = 2
        else:
            j.rizos = min(5, j.rizos + 1)
        j.puntos += 500
        self.efectos.append([j.x, j.y, "recoger", self.t])

    def _morir(self, j):
        if not j.vulnerable:
            return
        j.vidas -= 1
        j.muertes += 1
        j.muerto = True
        j.espera = C.ESPERA_REAPARECER
        j.arma, j.escoltas = 1, 0
        self.efectos.append([j.x, j.y, "grande", self.t])

    def _colisiones(self):
        objetivos = [e for e in self.enemigos if e.vivo and (e.tipo != "jefe" or self.t - e.t0 >= 90)]
        for b in self.balas:
            if b.vida <= 0:
                continue
            if b.dueno is not None:
                for e in objetivos:
                    if e.hp > 0 and abs(b.x - e.x) < e.hw + 2 and abs(b.y - e.y) < e.hh + 4:
                        self._herir(e, b.dano, b.dueno)
                        b.vida = 0
                        break
                continue
            for j in self.jugadores:
                if not j.vulnerable:
                    continue
                if abs(b.x - j.x) < 4 + b.radio and abs(b.y - j.y) < 4 + b.radio:
                    self._morir(j)
                    b.vida, b.pego = 0, True
                    break
                for k, (ex, ey) in enumerate(j.posiciones_escoltas()):
                    if abs(b.x - ex) < 4 + b.radio and abs(b.y - ey) < 4 + b.radio:
                        j.escoltas -= 1
                        b.vida, b.pego = 0, True
                        self.efectos.append([ex, ey, "chica", self.t])
                        break
        self.balas = [b for b in self.balas if b.vida > 0]
        for e in self.enemigos:
            if not e.vivo or e.tipo == "torreta":
                continue
            for j in self.jugadores:
                if j.vulnerable and abs(j.x - e.x) < e.hw + 3 and abs(j.y - e.y) < e.hh + 3:
                    self._morir(j)
                    if e.tipo == "caza":
                        self._herir(e, e.hp, j)

    def _herir(self, e, dano, autor):
        e.hp -= dano
        e.golpe = 3
        if e.tipo in ("jefe", "torreta"):
            autor.dano_jefe += dano
            self.dano_jefe_total += dano
            self.ultimo_dano_jefe = self.t
        if e.hp > 0:
            return
        e.vivo = False
        autor.bajas += 1
        autor.puntos += e.puntos
        tam = {"caza": "chica", "torreta": "chica"}.get(e.tipo, "grande")
        self.efectos.append([e.x, e.y, tam, self.t])
        grupo = e.datos.get("grupo", 0)
        if grupo and grupo in self.escuadras:
            self.escuadras[grupo] -= 1
            if self.escuadras[grupo] <= 0:
                del self.escuadras[grupo]
                autor.puntos += 1000
                self.items.append(Item(e.x, e.y, self.rng.choice(POWS)))
        if e.tipo == "bombardero" and self.rng.random() < 0.35 or e.tipo == "pesado":
            self.items.append(Item(e.x, e.y, self.rng.choice(POWS)))
        if e.tipo == "jefe":
            self.jefe_vencido = True
            self.t_vencido = self.t
            for o in self.enemigos:
                if o.vivo:
                    o.vivo = False
                    self.efectos.append([o.x, o.y, "grande", self.t])
            self.balas = [b for b in self.balas if b.dueno is not None]

    def progreso(self):
        if self.superada:
            return 1.0
        if self.jefe is None:
            return 0.75 * min(1.0, self.t / self.mision.duracion)
        return 0.75 + 0.25 * min(1.0, max(0.0, 1 - self.jefe.hp / self.jefe.hp_max))

    def resumen(self):
        bajas = sum(j.bajas for j in self.jugadores)
        muertes = sum(j.muertes for j in self.jugadores)
        vidas = sum(max(j.vidas, 0) for j in self.jugadores)
        aptitud = (C.PREMIO_PROGRESO * self.progreso() + C.PREMIO_BAJA * bajas
                   + C.PREMIO_DANO_JEFE * self.dano_jefe_total - C.CASTIGO_MUERTE * muertes
                   + C.PREMIO_ESQUIVE * min(self.esquives, C.MAX_ESQUIVES))
        if self.superada:
            aptitud += C.PREMIO_MISION + C.PREMIO_VIDA_RESTANTE * vidas
        return {
            "aptitud": aptitud, "progreso": self.progreso(), "superada": self.superada, "bajas": bajas,
            "muertes": muertes, "dano_jefe": self.dano_jefe_total, "ticks": self.t, "motivo": self.motivo,
            "puntos": sum(j.puntos for j in self.jugadores), "esquives": self.esquives,
        }
