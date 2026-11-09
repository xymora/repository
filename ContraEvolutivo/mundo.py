import math
import random

import config as C
from etapas import AGUA, BARRERA, PINCHO, PLATAFORMA, PUENTE, SOLIDO, VACIO, cargar_etapa
from jefes import PARTES

T = C.TILE
SOLIDOS = (SOLIDO, BARRERA)
PISABLES = (PLATAFORMA, PUENTE)
DE_PIE = (SOLIDO, PLATAFORMA)
ARMAS = "NMSLF"
ESPECS_ARMA = {"N": (8, 4), "M": (4, 6), "S": (11, 10), "L": (16, 1), "F": (10, 3)}
NADA = (0, False, False, False, False)

TIPOS = {
    "soldado": (12, 28, 1, True, 100, True),
    "francotirador": (14, 26, 1, True, 200, True),
    "torreta": (16, 16, 8, False, 500, False),
    "canon": (20, 16, 10, False, 500, False),
    "capsula": (22, 12, 1, False, 300, False),
    "caja": (22, 22, 3, False, 400, False),
    "roca": (16, 16, 3, True, 200, True),
    "granadero": (14, 26, 2, True, 300, True),
    "llama": (12, 16, 0, False, 0, False),
    "prensa": (30, 24, 0, True, 0, False),
    "nucleo": (16, 32, 12, False, 1000, False),
    "larva": (12, 8, 1, True, 100, True),
    "boca": (24, 24, 12, False, 800, False),
}


class Cuerpo:
    def __init__(self, x, y, w, h):
        self.x, self.y, self.w, self.h = x, y, w, h
        self.vx = self.vy = 0.0
        self.en_suelo = False
        self.choco_x = False
        self.piso = VACIO

    @property
    def cx(self):
        return self.x + self.w / 2

    @property
    def cy(self):
        return self.y + self.h / 2

    def toca(self, o):
        return self.x < o.x + o.w and o.x < self.x + self.w and self.y < o.y + o.h and o.y < self.y + self.h


class Jugador(Cuerpo):
    def __init__(self, indice, cx, pies):
        super().__init__(cx - 5, pies - 30, 10, 30)
        self.indice = indice
        self.vidas = C.VIDAS
        self.arma = "N"
        self.rapido = False
        self.mirando = 1
        self.apunte = (1, 0)
        self.agachado = self.en_agua = self.buceando = self.girando = False
        self.invulnerable = C.INVULNERABLE
        self.barrera = 0
        self.cadencia = 0
        self.balas_vivas = 0
        self.salto_previo = False
        self.ignorar_plataforma = 0
        self.muerto = False
        self.fuera = False
        self.espera = 0
        self.muertes = self.bajas = self.puntos = 0
        self.premiadas = 0
        self.ticks_agua = self.agua_seguidos = 0
        self.dano_jefe = 0
        self.seguro = (cx, pies)
        self.paso_anim = 0.0

    @property
    def activo(self):
        return not self.muerto and not self.fuera

    @property
    def vulnerable(self):
        return self.activo and self.invulnerable <= 0 and self.barrera <= 0 and not self.buceando


class Bala:
    __slots__ = ("x", "y", "vx", "vy", "w", "h", "tipo", "dueno", "dano", "vida", "t", "bx", "by", "cerca", "pego")

    def __init__(self, x, y, vx, vy, tipo, dueno=None, dano=1, lado=4):
        self.x = self.bx = x
        self.y = self.by = y
        self.vx, self.vy = vx, vy
        self.w = self.h = lado
        self.tipo, self.dueno, self.dano = tipo, dueno, dano
        self.vida = 90
        self.t = 0
        self.cerca = 1e9
        self.pego = False

    def toca(self, o):
        m = self.w / 2
        return self.x - m < o.x + o.w and o.x < self.x + m and self.y - m < o.y + o.h and o.y < self.y + m


class Item(Cuerpo):
    def __init__(self, cx, cy, letra):
        super().__init__(cx - 8, cy - 6, 16, 12)
        self.letra = letra
        self.vx = 1.0
        self.vy = -5.0
        self.vida = 600


class Enemigo(Cuerpo):
    def __init__(self, tipo, cx, pies, datos, t):
        if tipo == "parte":
            w, h, hp = datos["w"], datos["h"], datos["hp"]
            contacto, puntos, gravedad = datos["mov"] != "fijo", 2000, False
        else:
            w, h, hp, contacto, puntos, gravedad = TIPOS[tipo]
        super().__init__(cx - w / 2, pies - h, w, h)
        self.tipo = tipo
        self.hp = self.hp_max = hp
        self.contacto = contacto
        self.puntos = puntos
        self.gravedad = gravedad
        self.vulnerable = hp > 0
        self.datos = datos
        self.t0 = t
        self.x0, self.y0 = self.x, self.y
        self.mirando = -1
        self.angulo = 6
        self.vivo = True
        self.rebotes = 0


class Partida:
    def __init__(self, numero, controladores, semilla, limites=True):
        self.etapa = e = cargar_etapa(numero)
        self.numero = e.numero
        self.vertical = e.vertical
        self.mapa = e.tiles.tolist()
        self.filas, self.columnas = e.tiles.shape
        self.rng = random.Random(semilla)
        self.controladores = list(controladores)
        self.jugadores = [Jugador(i, e.inicio[0] + 22 * i, e.inicio[1]) for i in range(len(self.controladores))]
        self.acciones = [NADA] * len(self.jugadores)
        self.limites = limites
        self.cam_x = 0.0
        self.cam_y = float(e.alto_px - C.ALTO_VISTA) if e.vertical else 0.0
        self.enemigos, self.balas, self.items, self.efectos = [], [], [], []
        self.grupos = {k: list(v) for k, v in e.grupos.items()}
        self.explotando = {}
        self.siguiente = 0
        self.t = 0
        self.jefe_activo = self.jefe_vencido = False
        self.t_vencido = 0
        self.ultimo_dano_jefe = 0
        self.dano_jefe_total = 0
        self.progreso_px = 0.0
        self.esquives = 0
        self.ultimo_avance = 0
        self.terminada = self.superada = False
        self.motivo = ""

    def tile(self, fila, col):
        if col < 0 or col >= self.columnas:
            return SOLIDO
        if fila < 0 or fila >= self.filas:
            return VACIO
        return self.mapa[fila][col]

    def tile_en(self, x, y):
        return self.tile(int(y // T), int(x // T))

    def en_vista(self, c, margen=0):
        return (c.x + c.w > self.cam_x - margen and c.x < self.cam_x + C.ANCHO_VISTA + margen
                and c.y + c.h > self.cam_y - margen and c.y < self.cam_y + C.ALTO_VISTA + margen)

    def mover(self, c, plataformas=True, nadador=False):
        c.choco_x = False
        if c.vx:
            c.x += c.vx
            f0, f1 = int(c.y // T), int((c.y + c.h - 1) // T)
            col = int((c.x + c.w - 1) // T) if c.vx > 0 else int(c.x // T)
            for f in range(f0, f1 + 1):
                if self.tile(f, col) in SOLIDOS:
                    c.x = col * T - c.w if c.vx > 0 else (col + 1) * T
                    c.choco_x = True
                    break
        previo = c.y + c.h
        c.y += c.vy
        c.en_suelo = False
        c0, c1 = int(c.x // T), int((c.x + c.w - 1) // T)
        if c.vy >= 0:
            fila = int((c.y + c.h) // T)
            tope = fila * T
            for col in range(c0, c1 + 1):
                t = self.tile(fila, col)
                if t in SOLIDOS or (plataformas and t in PISABLES and previo <= tope + 0.01):
                    c.y, c.vy, c.en_suelo, c.piso = tope - c.h, 0.0, True, t
                    return
                if nadador and t == AGUA and c.y + c.h >= tope + 2 and previo <= tope + 2 + C.CAIDA_MAX:
                    c.y, c.vy, c.en_suelo, c.piso = tope + 2 - c.h, 0.0, True, AGUA
                    return
        else:
            fila = int(c.y // T)
            for col in range(c0, c1 + 1):
                if self.tile(fila, col) in SOLIDOS:
                    c.y, c.vy = (fila + 1) * T, 0.0
                    return

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
        self._camara()
        self._aparecer()
        for e in self.enemigos:
            self._enemigo(e)
        self._balas()
        self._items()
        self._puentes()
        self._colisiones()
        self.enemigos = [e for e in self.enemigos if e.vivo]
        self.efectos = [f for f in self.efectos if self.t - f[3] < 24]
        self.t += 1
        self._fin()

    def _fin(self):
        if self.jefe_vencido and self.t - self.t_vencido > 45:
            self._terminar("etapa superada", True)
        elif all(j.fuera for j in self.jugadores):
            self._terminar("sin vidas")
        elif not self.limites:
            return
        elif self.t >= C.TIEMPO_MAX:
            self._terminar("tiempo agotado")
        elif not self.jefe_activo and self.t - self.ultimo_avance > C.ESTANCADO_MAX:
            self._terminar("se quedaron atorados")
        elif all(j.agua_seguidos > C.AGUA_MAX for j in self.jugadores if j.activo) and any(
                j.activo for j in self.jugadores):
            self._terminar("se quedaron en el agua")
        elif self.jefe_activo and not self.jefe_vencido and self.t - self.ultimo_dano_jefe > C.JEFE_SIN_DANO_MAX:
            self._terminar("no dañaron al jefe")

    def _terminar(self, motivo, superada=False):
        self.terminada, self.superada, self.motivo = True, superada, motivo

    def _jugador(self, j, acciones):
        if j.fuera:
            return
        if j.muerto:
            j.espera -= 1
            if j.espera <= 0:
                if j.vidas > 0:
                    self._reaparecer(j)
                else:
                    j.fuera = True
            return
        mov, salto, disparo, arriba, abajo = acciones
        j.invulnerable = max(0, j.invulnerable - 1)
        j.barrera = max(0, j.barrera - 1)
        j.cadencia = max(0, j.cadencia - 1)
        j.ignorar_plataforma = max(0, j.ignorar_plataforma - 1)
        if mov:
            j.mirando = mov
        j.en_agua = j.en_suelo and j.piso == AGUA
        j.buceando = j.en_agua and abajo
        if j.en_agua:
            j.ticks_agua += 1
            j.agua_seguidos += 1
        else:
            j.agua_seguidos = 0
        j.agachado = abajo and j.en_suelo and not j.en_agua and mov == 0
        quieto = j.agachado or j.buceando
        j.vx = 0.0 if quieto else mov * C.VEL_CORRER * (0.7 if j.en_agua else 1.0)
        if salto and not j.salto_previo and j.en_suelo and not j.buceando:
            if abajo and j.piso in PISABLES:
                j.ignorar_plataforma = 6
                j.en_suelo = False
            else:
                j.vy = C.VEL_SALTO
                j.girando = True
        j.salto_previo = salto
        j.vy = min(j.vy + C.GRAVEDAD, C.CAIDA_MAX)
        if j.girando and not j.en_suelo:
            alto = 16
        elif j.agachado:
            alto = 12
        elif j.buceando:
            alto = 6
        elif j.en_agua:
            alto = 18
        else:
            alto = 30
        if alto != j.h:
            j.y += j.h - alto
            j.h = alto
        self.mover(j, plataformas=j.ignorar_plataforma == 0, nadador=True)
        if j.en_suelo:
            j.girando = False
            if j.piso in DE_PIE:
                j.seguro = (j.cx, j.y + j.h)
        if self.vertical:
            j.x = min(max(j.x, T), C.ANCHO_VISTA - T - j.w)
        else:
            j.x = min(max(j.x, self.cam_x), self.cam_x + C.ANCHO_VISTA - j.w)
        if arriba and mov:
            j.apunte = (mov, -1)
        elif arriba:
            j.apunte = (0, -1)
        elif abajo and not j.en_suelo:
            j.apunte = (0, 1)
        elif abajo and mov and not j.en_agua:
            j.apunte = (mov, 1)
        else:
            j.apunte = (j.mirando, 0)
        if disparo and not j.buceando:
            self._disparar(j)
        j.paso_anim += abs(j.vx)
        limite = self.cam_y + C.ALTO_VISTA + 8 if self.vertical else self.etapa.alto_px
        if j.y > limite or self.tile_en(j.cx, j.y + j.h - 2) == PINCHO:
            self._morir(j)

    def _boca(self, j):
        dx, dy = j.apunte
        if j.agachado:
            return j.cx + j.mirando * 14, j.y + 4
        if j.en_agua:
            return j.cx + dx * 10, j.y + 5 + dy * 6
        if j.girando and not j.en_suelo:
            return j.cx + dx * 8, j.cy + dy * 8
        return j.cx + dx * 12, j.y + 9 + (dy * 10 if dy > 0 else dy * 12)

    def _disparar(self, j):
        cadencia, maximo = ESPECS_ARMA[j.arma]
        if j.cadencia > 0 or j.balas_vivas >= maximo:
            return
        dx, dy = j.apunte
        angulo = math.atan2(dy, dx)
        vel = C.VEL_BALA * (1.3 if j.rapido else 1.0)
        x, y = self._boca(j)
        if j.arma == "S":
            for k in (-2, -1, 0, 1, 2):
                self._bala_jugador(j, x, y, angulo + k * 0.17, vel, "S", 1, 5)
        elif j.arma == "L":
            self._bala_jugador(j, x, y, angulo, vel * 1.4, "L", 3, 8)
        elif j.arma == "F":
            self._bala_jugador(j, x, y, angulo, vel * 0.75, "F", 2, 8)
        else:
            self._bala_jugador(j, x, y, angulo, vel, j.arma, 1, 4)
        j.cadencia = max(2, int(cadencia * (0.7 if j.rapido else 1.0)))

    def _bala_jugador(self, j, x, y, angulo, vel, tipo, dano, lado):
        self.balas.append(Bala(x, y, math.cos(angulo) * vel, math.sin(angulo) * vel, tipo, j, dano, lado))
        j.balas_vivas += 1

    def _bala_enemiga(self, x, y, angulo, vel, tipo="e", lado=4):
        self.balas.append(Bala(x, y, math.cos(angulo) * vel, math.sin(angulo) * vel, tipo, None, 1, lado))

    def _disparar_a(self, x, y, objetivo, vel, abanico=0):
        base = math.atan2(objetivo.cy - y, objetivo.cx - x)
        for k in range(-abanico, abanico + 1):
            self._bala_enemiga(x, y, base + k * 0.3, vel)

    def _granada(self, x, y, objetivo, tipo="g"):
        b = Bala(x, y, max(-4.0, min(4.0, (objetivo.cx - x) / 30)), -6.0, tipo, None, 1, 6)
        if tipo == "d":
            b.vx, b.vy, b.w, b.h = (3.2 if objetivo.cx > x else -3.2), -3.0, 10, 10
            b.vida = 160
        self.balas.append(b)

    def _morir(self, j):
        if not j.activo:
            return
        j.vidas -= 1
        j.muertes += 1
        j.muerto = True
        j.espera = C.ESPERA_REAPARECER
        self.efectos.append([j.cx, j.cy, "muerte", self.t])

    def _reaparecer(self, j):
        cx, pies = self._punto_seguro(j.seguro[0])
        j.h = 30
        j.x, j.y = cx - j.w / 2, pies - j.h
        j.vx = j.vy = 0.0
        j.muerto = j.girando = j.agachado = j.en_agua = j.buceando = False
        j.invulnerable = C.INVULNERABLE
        j.arma, j.rapido = "N", False

    def _puede_pararse(self, fila, col):
        return (self.tile(fila, col) in DE_PIE and self.tile(fila - 1, col) in (VACIO, AGUA)
                and self.tile(fila - 2, col) in (VACIO, AGUA))

    def _punto_seguro(self, x_pref):
        if self.vertical:
            columnas = sorted(range(1, self.columnas - 1), key=lambda c: abs(c * T + 8 - x_pref))
            f0 = int(self.cam_y // T) + 3
            f1 = int((self.cam_y + C.ALTO_VISTA) // T)
            for fila in range(f1 - 1, f0 - 1, -1):
                for col in columnas:
                    if self._puede_pararse(fila, col):
                        return col * T + 8, fila * T
            return C.ANCHO_VISTA / 2, self.cam_y + 60
        c0, c1 = int((self.cam_x + 16) // T), int((self.cam_x + C.ANCHO_VISTA - 16) // T)
        x_pref = min(max(x_pref, self.cam_x + 24), self.cam_x + C.ANCHO_VISTA - 24)
        for col in sorted(range(c0, c1), key=lambda c: abs(c * T + 8 - x_pref)):
            for fila in range(2, self.filas):
                if self._puede_pararse(fila, col):
                    return col * T + 8, fila * T
        return self.cam_x + 40, 40

    def _camara(self):
        activos = [j for j in self.jugadores if j.activo]
        if activos:
            if self.vertical:
                frente = min(j.y for j in activos)
                atras = max(j.y + j.h for j in activos)
                deseado = max(frente - 80, atras - C.ALTO_VISTA + 8)
                self.cam_y = max(min(self.cam_y, deseado), 0.0)
            else:
                frente = max(j.x for j in activos)
                atras = min(j.x for j in activos)
                deseado = min(frente - 110, atras - 2)
                self.cam_x = min(max(self.cam_x, deseado), float(self.etapa.ancho_px - C.ANCHO_VISTA))
        avance = self.avance_camara()
        if avance > self.progreso_px + 0.5:
            self.progreso_px = avance
            self.ultimo_avance = self.t
        if not self.jefe_activo and avance >= self.etapa.recorrido - 1:
            self._activar_jefe()

    def avance_camara(self):
        if self.vertical:
            return self.etapa.alto_px - C.ALTO_VISTA - self.cam_y
        return self.cam_x

    def _activar_jefe(self):
        self.jefe_activo = True
        self.ultimo_dano_jefe = self.t
        ox = 0 if self.vertical else self.etapa.ancho_px - C.ANCHO_VISTA
        for spec in PARTES[self.etapa.jefe]:
            e = Enemigo("parte", ox + spec["x"] + spec["w"] / 2, spec["y"] + spec["h"], dict(spec), self.t)
            e.datos["ox"] = ox
            self.enemigos.append(e)

    def _aparecer(self):
        avance = self.avance_camara()
        apariciones = self.etapa.apariciones
        while self.siguiente < len(apariciones) and apariciones[self.siguiente].activar <= avance:
            a = apariciones[self.siguiente]
            self.siguiente += 1
            e = Enemigo(a.tipo, a.x, a.y, dict(a.datos), self.t)
            if a.tipo == "capsula":
                e.x = self.cam_x - e.w - 4 if not self.vertical else -e.w
                e.y0 = e.y
                e.vx = 2.0
            elif a.tipo == "llama":
                e.y0 = a.y
            elif a.tipo == "prensa":
                e.y = e.y0 = a.y
            self.enemigos.append(e)
        if self.jefe_activo:
            return
        for k, o in enumerate(self.etapa.oleadas):
            if o.desde <= avance <= o.hasta and (self.t + k * 17) % o.periodo == 0:
                if sum(1 for e in self.enemigos if e.tipo == o.tipo) < 4:
                    self._oleada(o)

    def _oleada(self, o):
        if o.tipo == "roca":
            e = Enemigo("roca", self.rng.uniform(32, C.ANCHO_VISTA - 32), self.cam_y - 4, {"oleada": True}, self.t)
            e.vx = self.rng.choice((-1.2, 1.2))
            self.enemigos.append(e)
            return
        x = self.cam_x + C.ANCHO_VISTA + 6 if o.lado > 0 else self.cam_x - 6
        col = int(x // T)
        for fila in range(2, self.filas):
            if self._puede_pararse(fila, col):
                e = Enemigo(o.tipo, x, fila * T, {"oleada": True}, self.t)
                e.mirando = -o.lado
                self.enemigos.append(e)
                return

    def objetivo(self, e):
        mejor, distancia = None, 1e18
        for j in self.jugadores:
            if j.activo:
                d = (j.cx - e.cx) ** 2 + (j.cy - e.cy) ** 2
                if d < distancia:
                    mejor, distancia = j, d
        return mejor

    def _enemigo(self, e):
        getattr(self, "_ia_" + e.tipo)(e)
        if e.tipo == "parte":
            return
        if self.vertical:
            fuera = e.y > self.cam_y + C.ALTO_VISTA + 48
        else:
            fuera = e.x + e.w < self.cam_x - 48 or e.x > self.cam_x + C.ANCHO_VISTA + 96 or e.y > self.etapa.alto_px
        if fuera:
            e.vivo = False

    def _caer(self, e):
        e.vy = min(e.vy + C.GRAVEDAD, C.CAIDA_MAX)
        self.mover(e)
        if self.tile_en(e.cx, e.y + e.h - 1) == AGUA:
            e.vivo = False

    def _ia_soldado(self, e):
        if e.en_suelo:
            e.vx = e.mirando * 1.9
            delante = e.x + e.w + 2 if e.mirando > 0 else e.x - 2
            debajo = self.tile(int((e.y + e.h + 2) // T), int(delante // T))
            if debajo not in SOLIDOS and debajo not in PISABLES and self.rng.random() < 0.35:
                e.vy = -6.5
        self._caer(e)
        if e.choco_x:
            e.mirando = -e.mirando
        if (self.t - e.t0) % 50 == 25 and self.en_vista(e) and self.rng.random() < 0.3:
            obj = self.objetivo(e)
            if obj and (obj.cx - e.cx) * e.mirando > 0:
                self._bala_enemiga(e.cx + e.mirando * 8, e.y + 10, 0.0 if e.mirando > 0 else math.pi, 3.4)

    def _ia_francotirador(self, e):
        obj = self.objetivo(e)
        if obj:
            e.mirando = 1 if obj.cx > e.cx else -1
        e.vx = 0.0
        self._caer(e)
        if obj and (self.t - e.t0) % 45 == 20 and self.en_vista(e):
            self._disparar_a(e.cx + e.mirando * 8, e.y + 8, obj, 3.2)

    def _ia_torreta(self, e, angulos=range(12)):
        obj = self.objetivo(e)
        e.vulnerable = self.en_vista(e)
        if not obj or not e.vulnerable:
            return
        deseado = round(math.atan2(obj.cy - e.cy, obj.cx - e.cx) / (math.pi / 6)) % 12
        if deseado not in angulos:
            deseado = min(angulos, key=lambda a: min(abs(a - deseado), 12 - abs(a - deseado)))
        if (self.t - e.t0) % 8 == 0 and e.angulo != deseado:
            diferencia = (deseado - e.angulo) % 12
            e.angulo = (e.angulo + (1 if diferencia < 6 else -1)) % 12
        if (self.t - e.t0) % 45 == 30 and e.angulo == deseado:
            angulo = e.angulo * math.pi / 6
            self._bala_enemiga(e.cx + math.cos(angulo) * 10, e.cy + math.sin(angulo) * 10, angulo, 3.5)

    def _ia_canon(self, e):
        self._ia_torreta(e, angulos=(5, 6, 7))

    def _ia_capsula(self, e):
        e.x += e.vx
        e.y = e.y0 + 18 * math.sin((self.t - e.t0) * 0.1)
        if e.x > self.cam_x + C.ANCHO_VISTA + 30:
            e.vivo = False

    def _ia_caja(self, e):
        e.vulnerable = (self.t - e.t0) % 100 >= 55 and self.en_vista(e)

    def _ia_roca(self, e):
        self._caer(e)
        if e.en_suelo:
            if e.rebotes < 2:
                e.vy = -4.0
                e.rebotes += 1
        if e.choco_x:
            e.vx = -e.vx

    def _ia_granadero(self, e):
        obj = self.objetivo(e)
        if obj:
            e.mirando = 1 if obj.cx > e.cx else -1
        self._caer(e)
        if obj and (self.t - e.t0) % 55 == 30 and self.en_vista(e):
            self._granada(e.cx, e.y + 4, obj)

    def _ia_llama(self, e):
        largo = e.datos.get("largo", 4) * T
        encendida = (self.t + e.datos.get("desfase", 0)) % 80 < 32
        e.contacto = encendida
        if e.datos.get("orientacion") == "arriba":
            e.h = largo if encendida else 4
            e.y = e.y0 - e.h
        else:
            e.y = e.y0
            e.h = largo if encendida else 4

    def _ia_prensa(self, e):
        fase = (self.t + e.datos.get("desfase", 0)) % 120
        recorrido = 168 - e.y0
        if fase < 45:
            avance = 0.0
        elif fase < 58:
            avance = (fase - 45) / 13
        elif fase < 80:
            avance = 1.0
        else:
            avance = 1 - (fase - 80) / 40
        e.y = e.y0 + recorrido * avance

    def _ia_nucleo(self, e):
        obj = self.objetivo(e)
        if obj and (self.t - e.t0) % 80 == 40 and self.en_vista(e):
            self._disparar_a(e.cx, e.cy, obj, 2.5)

    def _ia_larva(self, e):
        obj = self.objetivo(e)
        if e.en_suelo:
            if obj:
                e.mirando = 1 if obj.cx > e.cx else -1
            e.vx = e.mirando * 1.5
            if self.rng.random() < 0.03:
                e.vy = -5.0
        self._caer(e)

    def _ia_boca(self, e):
        if (self.t - e.t0) % 70 == 35 and self.en_vista(e):
            self._engendrar(e)

    def _engendrar(self, e):
        if sum(1 for o in self.enemigos if o.tipo == "larva") < 6:
            larva = Enemigo("larva", e.cx, e.y + e.h + 8, {"oleada": True}, self.t)
            larva.vy = 1.0
            self.enemigos.append(larva)

    def _ia_parte(self, e):
        s = e.datos
        k = self.t - e.t0
        if s["mov"] == "vaiven":
            e.x = e.x0 + s["a"] * math.sin(s["s"] * k + s["fase"])
        elif s["mov"] == "flota":
            e.y = e.y0 + s["a"] * math.sin(s["s"] * k + s["fase"])
        elif s["mov"] == "circulo":
            cx, cy = s["ox"] + s["centro"][0], s["centro"][1]
            e.x = cx + s["a"] * math.cos(s["s"] * k + s["fase"]) - e.w / 2
            e.y = cy + s["a"] * math.sin(s["s"] * k + s["fase"]) - e.h / 2
        if k < 20 or (k + s["desfase"]) % s["periodo"] != 0:
            return
        obj = self.objetivo(e)
        if not obj:
            return
        ataque = s["ataque"]
        if ataque == "apuntado":
            self._disparar_a(e.cx, e.cy, obj, 3.4)
        elif ataque == "abanico":
            self._disparar_a(e.cx, e.cy + e.h / 4, obj, 3.2, abanico=1)
        elif ataque == "anillo":
            for i in range(8):
                self._bala_enemiga(e.cx, e.cy, i * math.pi / 4 + k * 0.01, 2.6)
        elif ataque == "granada":
            self._granada(e.x, e.cy, obj)
        elif ataque == "disco":
            self._granada(e.cx, e.y + e.h - 6, obj, "d")
        elif ataque == "engendrar":
            self._engendrar(e)

    def _balas(self):
        vivas = []
        for b in self.balas:
            b.t += 1
            b.vida -= 1
            if b.tipo in ("g", "d"):
                b.vy = min(b.vy + 0.35, C.CAIDA_MAX)
            b.bx += b.vx
            b.by += b.vy
            if b.tipo == "F":
                rapidez = math.hypot(b.vx, b.vy) or 1.0
                onda = 7 * math.sin(b.t * 0.7)
                b.x, b.y = b.bx - b.vy / rapidez * onda, b.by + b.vx / rapidez * onda
            else:
                b.x, b.y = b.bx, b.by
            if b.tipo in ("g", "d"):
                t = self.tile_en(b.x, b.y + b.h / 2)
                if t in SOLIDOS or t in PISABLES:
                    if b.tipo == "g":
                        self.efectos.append([b.x, b.y, "chispa", self.t])
                        b.vida = 0
                    else:
                        b.by = int((b.y + b.h / 2) // T) * T - b.h / 2
                        b.vy = -4.5
            if b.dueno is None:
                for j in self.jugadores:
                    if j.vulnerable:
                        b.cerca = min(b.cerca, math.hypot(b.x - j.cx, b.y - j.cy))
            dentro = (self.cam_x - 24 < b.x < self.cam_x + C.ANCHO_VISTA + 24
                      and self.cam_y - 40 < b.y < self.cam_y + C.ALTO_VISTA + 24)
            if b.vida > 0 and dentro:
                vivas.append(b)
            elif b.dueno is not None:
                b.dueno.balas_vivas -= 1
            elif not b.pego and b.cerca < C.DISTANCIA_ESQUIVE:
                self.esquives += 1
        self.balas = vivas

    def _items(self):
        vivos = []
        for it in self.items:
            it.vida -= 1
            it.vy = min(it.vy + 0.35, 4.0)
            self.mover(it, nadador=True)
            if it.en_suelo:
                it.vx = 0.0
            for j in self.jugadores:
                if j.activo and j.toca(it):
                    self._recoger(j, it.letra)
                    it.vida = 0
                    break
            if it.vida > 0 and self.en_vista(it, 32):
                vivos.append(it)
        self.items = vivos

    def _recoger(self, j, letra):
        if letra in ARMAS:
            j.arma = letra
        elif letra == "R":
            j.rapido = True
        elif letra == "B":
            j.barrera = 300
        j.puntos += 1000
        self.efectos.append([j.cx, j.y, "recoger", self.t])

    def _puentes(self):
        for j in self.jugadores:
            if j.activo and j.en_suelo and j.piso == PUENTE:
                fila, col = int((j.y + j.h) // T), int(j.cx // T)
                for grupo, celdas in self.grupos.items():
                    if (fila, col) in celdas and grupo not in self.explotando:
                        self.explotando[grupo] = self.t
        for grupo, inicio in list(self.explotando.items()):
            celdas = self.grupos.get(grupo, [])
            if celdas and (self.t - inicio) % 7 == 0:
                fila, col = celdas.pop(0)
                self.mapa[fila][col] = VACIO
                self.efectos.append([col * T + 8, fila * T + 4, "explosion", self.t])
            if not celdas:
                del self.explotando[grupo]

    def abrir_barrera(self, grupo):
        for fila, col in self.grupos.pop(grupo, []):
            self.mapa[fila][col] = VACIO
            self.efectos.append([col * T + 8, fila * T + 8, "explosion", self.t])

    def _colisiones(self):
        objetivos = [e for e in self.enemigos if e.vulnerable and e.hp > 0]
        for b in self.balas:
            if b.vida <= 0:
                continue
            if b.dueno is not None:
                for e in objetivos:
                    if e.hp > 0 and b.toca(e):
                        self._herir(e, b.dano, b.dueno)
                        b.vida = 0
                        break
            else:
                for j in self.jugadores:
                    if j.vulnerable and b.toca(j):
                        self._morir(j)
                        b.vida = 0
                        b.pego = True
                        break
        for e in self.enemigos:
            if e.contacto and e.vivo:
                for j in self.jugadores:
                    if j.vulnerable and j.toca(e):
                        self._morir(j)

    def _herir(self, e, dano, autor):
        e.hp -= dano
        if e.tipo == "parte":
            autor.dano_jefe += dano
            self.dano_jefe_total += dano
            self.ultimo_dano_jefe = self.t
        if e.hp > 0:
            return
        e.vivo = False
        autor.bajas += 1
        if not e.datos.get("oleada"):
            autor.premiadas += 1
        autor.puntos += e.puntos
        self.efectos.append([e.cx, e.cy, "explosion", self.t])
        if "letra" in e.datos:
            self.items.append(Item(e.cx, e.cy, e.datos["letra"]))
        if e.tipo == "nucleo":
            self.abrir_barrera(e.datos["grupo"])
        if e.tipo == "parte" and e.datos["vital"]:
            if not any(o.vivo and o.tipo == "parte" and o.datos["vital"] for o in self.enemigos):
                self.jefe_vencido = True
                self.t_vencido = self.t
                for o in self.enemigos:
                    if o.vivo:
                        o.vivo = False
                        self.efectos.append([o.cx, o.cy, "explosion", self.t])
                self.balas = [b for b in self.balas if b.dueno is not None]

    def progreso(self):
        return min(1.0, self.progreso_px / max(self.etapa.recorrido, 1))

    def resumen(self):
        bajas = sum(j.bajas for j in self.jugadores)
        premiadas = sum(j.premiadas for j in self.jugadores)
        muertes = sum(j.muertes for j in self.jugadores)
        vidas = sum(max(j.vidas, 0) for j in self.jugadores)
        aptitud = (C.PREMIO_PROGRESO * self.progreso() + C.PREMIO_BAJA * premiadas
                   + C.PREMIO_DANO_JEFE * self.dano_jefe_total - C.CASTIGO_MUERTE * muertes
                   + C.PREMIO_ESQUIVE * min(self.esquives, C.MAX_ESQUIVES)
                   - C.CASTIGO_AGUA * sum(j.ticks_agua for j in self.jugadores) / C.TICKS_POR_SEGUNDO)
        if self.motivo in ("se quedaron atorados", "se quedaron en el agua"):
            aptitud -= C.CASTIGO_ATORADO
        if self.superada:
            aptitud += C.PREMIO_ETAPA + C.PREMIO_VIDA_RESTANTE * vidas
        return {
            "aptitud": aptitud, "progreso": self.progreso(), "superada": self.superada, "bajas": bajas,
            "muertes": muertes, "dano_jefe": self.dano_jefe_total, "ticks": self.t, "motivo": self.motivo,
            "esquives": self.esquives,
            "puntos": sum(j.puntos for j in self.jugadores),
        }
