import math
import os
import time

import numpy as np
import pygame

import cerebro as B
import config as C
import sprites as SP
from grabador import GrabadorPygame
from sonido import Sonido
from aprendizaje import (Entrenador, cargar_mejor, cargar_salon, elegir_generaciones, vista_red,
                         carrera_campeonas,
                       resumen_generacion)
from pista import Pista
from simulacion import ATASCADO, META, MOTIVOS, SIN_COMBUSTIBLE, TIEMPO, VIVO, Carrera

BASE_W, BASE_H = 1280, 760
VW, VH = 256, 352
EV = 2
VISTA_X, VISTA_Y = 16, 40
PX_M = 6.0
Y_JUG = int(VH * 0.72)
BLOQUE = 256
ANCHO_SUELO = VW + 96
VELOCIDADES = (1, 2, 4, 8, 16)

FONDO = (14, 16, 20)
TARJETA = (22, 25, 32)
BORDE = (38, 43, 54)
TEXTO = (232, 235, 241)
TENUE = (138, 147, 166)
REJILLA = (35, 40, 53)
ROJO = (255, 64, 64)
ORO = (255, 201, 64)
VERDE = (61, 220, 132)
AZUL = (79, 179, 255)
MAGENTA = (232, 92, 200)
NARANJA = (255, 140, 66)
COLORES_GEN = ((255, 64, 64), (255, 201, 64), (61, 220, 132), (79, 179, 255), (199, 125, 255),
               (255, 140, 66), (240, 240, 240), (46, 230, 214))
ESTADO_COLOR = {VIVO: (150, 168, 192), META: VERDE, SIN_COMBUSTIBLE: NARANJA, ATASCADO: (90, 98, 112),
                TIEMPO: (150, 110, 220)}

TEMAS = {1: ((58, 150, 52), (50, 136, 46)), 2: ((58, 150, 52), (50, 136, 46)),
         3: ((52, 104, 50), (46, 94, 44)), 4: ((216, 196, 128), (206, 186, 118))}
NOMBRES_ENTRADAS = (["vel", "marcha", "comb", "derr", "vlat", "pos"]
                    + [f"cx{int(d)}" for d in C.MIRADAS] + [f"an{int(d)}" for d in C.MIRADAS]
                    + [f"ob{int(s):+d}" for s in C.SONDAS] + [f"vr{int(s):+d}" for s in C.SONDAS]
                    + [f"or{int(s):+d}" for s in C.SONDAS] + ["arc carr", "arc dist"])


_ANCLAS = {"tl": "topleft", "tr": "topright", "c": "center", "ml": "midleft", "mr": "midright"}


def _lerp(a, b, t):
    return a + (b - a) * t


def _mezcla(c1, c2, t):
    t = max(0.0, min(1.0, t))
    return tuple(int(_lerp(a, b, t)) for a, b in zip(c1, c2))

def _paso_eje(rango, divisiones=4):
    bruto = max(rango, 1e-9) / divisiones
    mag = 10 ** math.floor(math.log10(bruto))
    for m in (1, 2, 2.5, 5, 10):
        if bruto <= m * mag:
            return m * mag
    return 10 * mag



class Juego:
    def __init__(self, entrenador=None, demo=False, generaciones=False):
        os.environ.setdefault("SDL_VIDEO_CENTERED", "1")
        pygame.mixer.pre_init(44100, -16, 2, 512)
        pygame.init()
        info = pygame.display.Info()
        f = min(1.0, (info.current_w - 40) / BASE_W, (info.current_h - 90) / BASE_H)
        self.ventana = pygame.display.set_mode((int(BASE_W * f), int(BASE_H * f)), pygame.RESIZABLE)
        pygame.display.set_caption("Road Fighter evolutivo 2 — refuerzo profundo (PPO) + imitación")
        self.base = pygame.Surface((BASE_W, BASE_H))
        self.vista = pygame.Surface((VW, VH))
        self.reloj = pygame.time.Clock()
        self.grabar = GrabadorPygame()
        self.fp = SP.FuentePixel()
        self.f_titulo = pygame.font.SysFont("segoeui", 20, bold=True)
        self.f_med = pygame.font.SysFont("segoeui", 15, bold=True)
        self.f = pygame.font.SysFont("segoeui", 13)
        self.f_peq = pygame.font.SysFont("segoeui", 11)
        self.f_num = pygame.font.SysFont("consolas", 26, bold=True)
        self.f_mono = pygame.font.SysFont("consolas", 13, bold=True)
        self.sonido = Sonido()
        self._sprites()
        rng = np.random.default_rng(7)
        self.ruido32 = rng.uniform(-1, 1, (64, 64)).astype(np.float32)
        self._filas = np.arange(VH)
        self._X = np.arange(VW, dtype=np.float32)[None, :]
        self._Xm = (np.arange(VW) % 64)[None, :]
        self._Xm2 = ((np.arange(VW) // 2) % 64)[None, :]
        self._img = np.empty((VH, VW, 3), dtype=np.float32)
        self._bloques = {}
        self._prev = None
        suave = rng.uniform(-1, 1, (64, 64))
        for _ in range(6):
            suave = (suave + np.roll(suave, 1, 0) + np.roll(suave, -1, 0) + np.roll(suave, 1, 1)
                     + np.roll(suave, -1, 1)) / 5
        self.ruido_suave = (suave / np.abs(suave).max()).astype(np.float32)
        self.e = entrenador or Entrenador()
        self.pausa = False
        self.turbo = False
        self.i_vel = 0
        self.ver_sensores = True
        self.ver_red = True
        self.seguir = None
        self.carrera_gen = None
        self.etiquetas = []
        self.resultado = None
        self.particulas = []
        self.marcas = []
        self.flotantes = []
        self.sacudida = 0.0
        self.cam_x = None
        self.cam_y = 0.0
        self._estado_previo = None
        self._cache_red = (None, None)
        self._deco = (None, [])
        self.banner = ("", "", 0.0)
        self.confirmar_reinicio = 0.0
        self.acum = 0.0
        self.botones = []
        self.ultimo_resumen = None
        self.registro = []
        self.rapido_t0 = time.perf_counter()
        self.rapido_gens = 0
        self._anunciar_generacion()
        self.ensenando = None
        self.msgs_maestro = []
        if self.e.necesita_maestro and not (demo or generaciones):
            self._empezar_maestro()
        if demo or generaciones:
            self.carrera_generaciones(solo_mejor=demo)

    def _sprites(self):
        self.spr_jugador = SP.construir(SP.JUGADOR, SP.PAL_JUGADOR)
        self.spr_fantasma = SP.fantasma(self.spr_jugador, alfa=80)
        self.spr_sedan = {k: SP.sedan(k) for k in ("amarillo", "azul", "rojo")}
        arco = [(255, 77, 77), (255, 200, 60), (61, 220, 132), (79, 179, 255), (199, 125, 255)]
        self.spr_arcoiris = [SP.sedan_color(c, _mezcla(c, (0, 0, 0), 0.4), _mezcla(c, (255, 255, 255), 0.6))
                             for c in arco]
        self.spr_camion = SP.construir(SP.CAMION, SP.PAL_CAMION)
        self.spr_deco = {"arbol": SP.construir(SP.ARBOL, SP.PAL_ARBOL),
                         "pino": SP.construir(SP.PINO, SP.PAL_PINO),
                         "palmera": SP.construir(SP.PALMERA, SP.PAL_PALMERA),
                         "arbusto": SP.construir(SP.ARBUSTO, SP.PAL_ARBUSTO),
                         "roca": SP.construir(SP.ROCA, SP.PAL_ROCA),
                         "flor": SP.construir(SP.FLOR, SP.PAL_FLOR),
                         "bote": SP.construir(SP.BOTE, SP.PAL_BOTE)}
        self.spr_aceite = SP.construir(SP.ACEITE, SP.PAL_ACEITE)
        self.spr_obst = [SP.construir(SP.BARRERA, SP.PAL_BARRERA), SP.construir(SP.CONOS, SP.PAL_CONOS),
                         SP.construir(SP.ROCA_GRANDE, SP.PAL_ROCA)]
        self.spr_gen = [SP.tenir(self.spr_jugador, c) for c in COLORES_GEN]
        self.sombra = {}

    def _sombra(self, w, h):
        k = (w, h)
        if k not in self.sombra:
            s = pygame.Surface((w, h), pygame.SRCALPHA)
            pygame.draw.ellipse(s, (0, 0, 0, 80), s.get_rect())
            self.sombra[k] = s
        return self.sombra[k]

    def carrera(self):
        return self.carrera_gen if self.carrera_gen is not None else self.e.carrera

    def seguido(self, c):
        if self.seguir is not None and self.seguir < c.n:
            return self.seguir
        return c.lider()

    def _anunciar_generacion(self):
        p = self.e.pista
        self.banner = (f"STAGE {p.nivel}  {p.nombre}", f"GENERACION {self.e.generacion}", 2.2)
        self.particulas.clear()
        self.marcas.clear()
        self._estado_previo = None
        self._cache_red = (None, None)

    def _empezar_maestro(self):
        import threading
        self.turbo = False
        resultado = {}

        def trabajo():
            try:
                self.e.preentrenar(avisar=self.msgs_maestro.append)
                resultado["clon"] = ()
            except Exception as ex:
                resultado["error"] = repr(ex)

        self._res_maestro = resultado
        self.ensenando = threading.Thread(target=trabajo, daemon=True)
        self.ensenando.start()

    def _revisar_maestro(self):
        if self.ensenando is None or self.ensenando.is_alive():
            return
        r = self._res_maestro
        self.ensenando = None
        if "clon" in r:
            self.e.aplicar_maestro(*r["clon"])
            self._anunciar_generacion()
            self.banner = ("APRENDIO DEL MAESTRO", "AHORA MEJORA POR REFUERZO", 3.0)
            self.sonido.tocar("sube")
        else:
            self.banner = ("NO SE PUDO ENSEÑAR", r.get("error", "")[:30], 4.0)

    def carrera_generaciones(self, solo_mejor=False):
        if self.carrera_gen is not None:
            self.carrera_gen = None
            self.resultado = None
            self._anunciar_generacion()
            return
        salon = cargar_salon(self.e.dir)
        if solo_mejor or salon is None or len(salon["generacion"]) < 2:
            m = cargar_mejor(self.e.dir)
            if m is None:
                self.banner = ("SIN CAMPEONAS", "ENTRENA UNAS GENERACIONES", 2.5)
                return
            actores, normas = [m[0]], [m[2]]
            self.etiquetas = [f"G{m[1].get('generacion', '?')}"]
            nivel = int(m[1].get("nivel", 1))
        else:
            idx = elegir_generaciones(salon, len(COLORES_GEN))
            actores = [salon["actor"][i] for i in idx]
            normas = [B.Normalizador.desde(salon["normalizador"][i]) for i in idx]
            self.etiquetas = [f"G{int(salon['generacion'][i])}" for i in idx]
            nivel = int(np.max(salon["nivel"]))
        self.turbo = False
        pista = Pista(nivel, int(time.time()) % 100000)
        self.carrera_gen = carrera_campeonas(pista, actores, normas)
        self.resultado = None
        self.seguir = None
        self.particulas.clear()
        self.marcas.clear()
        self._estado_previo = None
        self._cache_red = (None, None)
        self.banner = ("CARRERA DE GENERACIONES", "  ".join(self.etiquetas), 2.5)

    def correr(self):
        while True:
            dt = min(self.reloj.tick(60) / 1000.0, 0.1)
            if not self._eventos():
                break
            self._avanzar(dt)
            self._efectos(dt)
            self._dibujar(dt)
        try:
            self.e.guardar_avance()
        except OSError:
            pass
        self.grabar.cerrar()
        pygame.quit()

    def _eventos(self):
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                return False
            if ev.type == pygame.VIDEORESIZE:
                self.ventana = pygame.display.set_mode(ev.size, pygame.RESIZABLE)
            if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
                mx, my = self._a_base(ev.pos)
                for rect, accion in self.botones:
                    if rect.collidepoint(mx, my):
                        accion()
            if ev.type == pygame.KEYDOWN:
                k = ev.key
                if k == pygame.K_ESCAPE:
                    if self.carrera_gen is not None:
                        self.carrera_generaciones()
                    else:
                        return False
                elif k == pygame.K_SPACE:
                    self.pausa = not self.pausa
                elif k == pygame.K_t:
                    self.alternar_turbo()
                elif k in (pygame.K_PLUS, pygame.K_KP_PLUS, pygame.K_EQUALS):
                    self.i_vel = min(len(VELOCIDADES) - 1, self.i_vel + 1)
                elif k in (pygame.K_MINUS, pygame.K_KP_MINUS):
                    self.i_vel = max(0, self.i_vel - 1)
                elif k == pygame.K_g:
                    self.carrera_generaciones()
                elif k == pygame.K_s:
                    self.ver_sensores = not self.ver_sensores
                elif k == pygame.K_n:
                    self.ver_red = not self.ver_red
                elif k == pygame.K_m:
                    self.sonido.alternar()
                elif k == pygame.K_l:
                    self.seguir = None
                elif k == pygame.K_TAB:
                    self.cambiar_seguido()
                elif k == pygame.K_F5:
                    self.guardar()
                elif k == pygame.K_F11:
                    pygame.display.toggle_fullscreen()
                elif k == pygame.K_r:
                    self.pedir_reinicio()
                elif k == pygame.K_y and self.confirmar_reinicio > 0:
                    self.e.reiniciar()
                    self.carrera_gen = None
                    self.confirmar_reinicio = 0
                    self._anunciar_generacion()
        return True

    def _a_base(self, pos):
        w, h = self.ventana.get_size()
        return pos[0] * BASE_W / w, pos[1] * BASE_H / h

    def alternar_turbo(self):
        if self.carrera_gen is None:
            self.turbo = not self.turbo
            self.rapido_t0 = time.perf_counter()
            self.rapido_gens = 0

    def cambiar_seguido(self):
        c = self.carrera()
        vivos = [int(i) for i in np.argsort(-c.y) if c.vivo[i]] or list(range(c.n))
        actual = self.seguido(c)
        self.seguir = vivos[(vivos.index(actual) + 1) % len(vivos)] if actual in vivos else vivos[0]

    def guardar(self):
        try:
            self.e.guardar_avance()
        except OSError as err:
            self.banner = ("NO SE PUDO GUARDAR", str(err)[:30], 3.0)
            return
        self.banner = ("AVANCE GUARDADO", f"GENERACION {self.e.generacion}", 2.5)

    def pedir_reinicio(self):
        self.confirmar_reinicio = 4.0

    def _foto(self, c):
        self._prev = (id(c), c.x.copy(), c.y.copy(), c.t, c.f.copy())

    def _avanzar(self, dt):
        if self.ensenando is not None:
            self._revisar_maestro()
            return
        if self.pausa:
            return
        if self.carrera_gen is not None:
            c = self.carrera_gen
            if not c.terminado:
                self.acum += dt * VELOCIDADES[self.i_vel] / C.DT
                pasos = min(int(self.acum), 60)
                self.acum -= pasos
                for k in range(pasos):
                    if k == pasos - 1:
                        self._foto(c)
                    c.paso()
                    if c.terminado:
                        self._fin_carrera_gen()
                        break
            return
        if self.turbo:
            self._prev = None
            limite = time.perf_counter() + 0.20
            while time.perf_counter() < limite:
                r = self.e.avanzar(20)
                if r is not None:
                    self._fin_generacion(r)
                    self.rapido_gens += 1
                elif self.e.actualizando:
                    break
            return
        self.acum += dt * VELOCIDADES[self.i_vel] / C.DT
        pasos = min(int(self.acum), 80)
        self.acum -= pasos
        for k in range(pasos):
            if k == pasos - 1:
                self._foto(self.e.carrera)
            r = self.e.avanzar(1)
            if r is not None:
                self._fin_generacion(r)
                self._prev = None
                break

    def _interpolado(self, c):
        p = self._prev
        if p is None or p[0] != id(c) or p[1].shape != c.x.shape or self.pausa:
            return c.x, c.y, c.t, c.f
        a = float(min(max(self.acum, 0.0), 1.0))
        salto = np.abs(c.x - p[1]) > 3.0
        x = np.where(salto, c.x, p[1] + (c.x - p[1]) * a)
        y = np.where(salto, c.y, p[2] + (c.y - p[2]) * a)
        return x, y, p[3] + (c.t - p[3]) * a, p[4] + (c.f - p[4]) * a

    def _fin_generacion(self, r):
        print(resumen_generacion(r), flush=True)
        self.ultimo_resumen = r
        self.registro.append(r)
        del self.registro[:-14]
        self._anunciar_generacion()
        if r.get("subio"):
            self.banner = ("SUBE DE NIVEL!", C.NIVELES[r["nivel_nuevo"] - 1][0], 3.0)
            self.sonido.tocar("sube")
        else:
            self.sonido.tocar("gen")

    def _fin_carrera_gen(self):
        c = self.carrera_gen
        llego = c.motivo == META
        orden = sorted(range(c.n), key=lambda i: (0 if llego[i] else 1,
                                                  float(c.t_fin[i]) if llego[i] else -float(c.y[i])))
        self.resultado = []
        for pos, i in enumerate(orden, 1):
            if llego[i]:
                dato = f"META {c.t_fin[i]:.1f} s  {c.velocidad_media_kmh()[i]:.0f} KM/H"
            else:
                dato = f"{MOTIVOS[c.motivo[i]]} {c.progreso()[i]:.0f} M"
            self.resultado.append((pos, i, dato, int(c.choques[i])))
        self.sonido.tocar("sube")

    def _efectos(self, dt):
        c = self.carrera()
        j = self.seguido(c)
        estado = (int(c.choques[j]), int(c.derrapes[j]), float(c.combustible[j]), j, id(c))
        if self._estado_previo is not None and self._estado_previo[3:] == estado[3:]:
            if estado[0] > self._estado_previo[0]:
                self._explosion(c.x[j], c.y[j])
                self.sacudida = 0.45
                self.sonido.tocar("choque")
            if estado[1] > self._estado_previo[1]:
                self._chispas(c.x[j], c.y[j] + 2.0)
                self.sonido.tocar("derrape")
            if estado[2] > self._estado_previo[2] + 5:
                self.flotantes.append([c.x[j], c.y[j] + 3, "+FUEL", 1.2])
                self.sonido.tocar("fuel")
        self._estado_previo = estado
        if c.derrape_t[j] > 0 and not self.pausa:
            for lado in (-0.6, 0.6):
                self.particulas.append([c.x[j] + lado, c.y[j] - 1.8, np.random.uniform(-1, 1),
                                        np.random.uniform(-2, 0), 0.6, 0.6, "humo", (200, 200, 205), 2])
                self.marcas.append([c.x[j] + lado, c.y[j] - 1.6, 4.0])
        elif not self.pausa and c.v[j] > 1 and c.choque_t[j] <= 0:
            p = c.pista
            if abs(c.x[j] - p.centro(c.y[j])) > p.semiancho(c.y[j]) - 1.4:
                self.particulas.append([c.x[j], c.y[j] - 2, np.random.uniform(-1, 1), -1, 0.4, 0.4,
                                        "polvo", (170, 140, 100), 2])
        paso = 0 if self.pausa else dt
        vivas = []
        for q in self.particulas:
            q[0] += q[2] * paso
            q[1] += q[3] * paso
            q[4] -= paso
            if q[4] > 0:
                vivas.append(q)
        self.particulas = vivas[-500:]
        self.marcas = [m for m in self.marcas if (m.__setitem__(2, m[2] - paso) or m[2] > 0)][-400:]
        self.flotantes = [f for f in self.flotantes if (f.__setitem__(3, f[3] - paso) or f[3] > 0)]
        self.sacudida = max(0.0, self.sacudida - dt)
        b = self.banner
        if b[2] > 0:
            self.banner = (b[0], b[1], b[2] - dt)
        self.confirmar_reinicio = max(0.0, self.confirmar_reinicio - dt)
        self.sonido.motor_vel(c.v[j], float(c.ctrl[j, 1]), bool(c.alto[j]),
                              c.vivo[j] and c.choque_t[j] <= 0 and not self.pausa and not self.turbo)

    def _explosion(self, x, y):
        rng = np.random.default_rng()
        for _ in range(36):
            a, v = rng.uniform(0, 2 * np.pi), rng.uniform(2, 14)
            col = (255, int(rng.uniform(80, 220)), 30)
            self.particulas.append([x, y, v * math.cos(a), v * math.sin(a), rng.uniform(0.4, 0.9),
                                    0.9, "fuego", col, int(rng.integers(2, 5))])
        for _ in range(16):
            a, v = rng.uniform(0, 2 * np.pi), rng.uniform(6, 20)
            self.particulas.append([x, y, v * math.cos(a), v * math.sin(a), rng.uniform(0.6, 1.2),
                                    1.2, "escombro", (40, 40, 44), 2])
        for _ in range(10):
            self.particulas.append([x + rng.uniform(-1, 1), y + rng.uniform(-1, 1), rng.uniform(-1, 1),
                                    rng.uniform(0, 3), 1.6, 1.6, "humo", (90, 90, 96), 4])

    def _chispas(self, x, y):
        rng = np.random.default_rng()
        for _ in range(14):
            a, v = rng.uniform(0, 2 * np.pi), rng.uniform(4, 16)
            self.particulas.append([x, y, v * math.cos(a), v * math.sin(a), 0.35, 0.35, "chispa",
                                    (255, 240, 140), 1])

    def _decoracion(self, p):
        if self._deco[0] is p:
            return self._deco[1]
        rng = np.random.default_rng(p.semilla + 11)
        deco = []
        tipos = {1: (("arbol", 0.5), ("arbusto", 0.3), ("flor", 0.2)),
                 2: (("bote", 1.0),),
                 3: (("pino", 0.55), ("roca", 0.35), ("arbusto", 0.1)),
                 4: (("palmera", 0.6), ("arbusto", 0.25), ("roca", 0.15))}[p.nivel]
        nombres = [t for t, _ in tipos]
        probs = np.array([w for _, w in tipos])
        for y in np.arange(0.0, p.largo + C.LARGO_EXTRA, 4.5):
            if rng.random() > (0.12 if p.nivel == 2 else 0.75):
                continue
            lado = rng.choice((-1, 1))
            if p.nivel == 4 and lado < 0:
                continue
            off = rng.uniform(6.0, 20.0) if p.nivel == 2 else rng.uniform(2.2, 18.0)
            deco.append((y + rng.uniform(-2, 2), lado, off, nombres[int(rng.choice(len(nombres), p=probs / probs.sum()))]))
        self._deco = (p, deco)
        return deco

    def _a_vista(self, x, y):
        return (VW / 2 + (x - self.cam_x) * PX_M + self._sx, Y_JUG - (y - self.cam_y) * PX_M + self._sy)

    def _bloque(self, p, kb):
        clave = (id(p), kb)
        if clave in self._bloques:
            return self._bloques[clave]
        gi = kb * BLOQUE + (BLOQUE - 1 - np.arange(BLOQUE))
        yw = gi / PX_M
        hpx = (p.semiancho(yw) * PX_M).astype(np.float32)
        u = np.arange(ANCHO_SUELO, dtype=np.float32)[None, :]
        d = u - ANCHO_SUELO / 2
        ad = np.abs(d)
        H = hpx[:, None]
        iy = gi % 64
        um = (np.arange(ANCHO_SUELO) % 64)[None, :]
        ruido = self.ruido32[iy[:, None], um]
        img = np.empty((BLOQUE, ANCHO_SUELO, 3), dtype=np.float32)
        banda = (np.floor(yw / 5.0) % 2).astype(bool)
        g1, g2 = TEMAS[p.nivel]
        img[:] = g1
        img[banda] = g2
        img += (ruido * 7)[..., None]
        R3 = ruido[..., None]

        def pintar(m, color, amp=0.0):
            if amp:
                img[m] = np.asarray(color, dtype=np.float32) + R3[m] * amp
            else:
                img[m] = color

        if p.nivel == 3:
            iy2 = (gi // 3) % 64
            mancha = self.ruido_suave[iy2[:, None], ((np.arange(ANCHO_SUELO) // 3) % 64)[None, :]]
            pintar((mancha > 0.35) & (ad > H + 3), (110, 98, 74), 8)
            pintar((mancha > 0.62) & (ad > H + 3), (132, 124, 112), 6)
        if p.nivel == 2:
            ola = np.sin(u * 0.35 + yw[:, None] * 1.3) * np.sin(u * 0.11 - yw[:, None] * 0.4)
            agua = ad > H + 5
            pintar(agua, (30, 86, 168), 6)
            pintar(agua & (ola > 0.72), (110, 170, 235))
            pintar((ad > H) & (ad <= H + 5), (150, 152, 160), 8)
            pintar((ad > H + 4) & (ad <= H + 5.5), (70, 72, 80))
        if p.nivel == 4:
            borde = -H - 14 - 4 * np.sin(yw[:, None] * 0.25) - 2 * ruido
            mar = d < borde
            pintar(mar, (36, 110, 190), 8)
            pintar(mar & (np.sin(u * 0.2 + yw[:, None] * 0.9) > 0.85), (90, 160, 230))
            pintar((d >= borde) & (d < borde + 3), (240, 245, 250))
        if p.nivel != 2:
            pintar((ad > H) & (ad <= H + 3), (150, 138, 116), 10)
        bordillo = (ad > H - 3) & (ad <= H)
        blanco = (np.floor(yw / 1.5) % 2 > 0)[:, None]
        pintar(bordillo & blanco, (236, 236, 236))
        pintar(bordillo & ~blanco, (214, 44, 44))
        asf = ad <= H - 3
        pintar(asf, (82, 84, 92), 5)
        pintar(asf & (np.abs(ad - H * 0.42) < 3), (76, 78, 86), 5)
        pintar((ad > H - 6) & (ad <= H - 5), (226, 226, 226))
        guion = (np.floor(yw / 3.0) % 2 == 0)[:, None]
        carriles = np.zeros(asf.shape, dtype=bool)
        for f in C.LINEAS_CARRIL:
            carriles |= np.abs(d - f * (H - C.BORDILLO * PX_M)) < 0.8
        pintar(carriles & guion & asf, (240, 240, 240))
        meta = (np.abs(yw - p.largo) < 1.6)[:, None] & asf
        cuad = ((u.astype(np.int64) // 4 + gi[:, None] // 4) % 2 == 0)
        pintar(meta & cuad, (250, 250, 250))
        pintar(meta & ~cuad, (20, 20, 20))
        np.clip(img, 0, 255, out=img)
        surf = pygame.Surface((ANCHO_SUELO, BLOQUE))
        pygame.surfarray.blit_array(surf, img.astype(np.uint8).transpose(1, 0, 2))
        if len(self._bloques) > 24:
            self._bloques.pop(next(iter(self._bloques)))
        self._bloques[clave] = surf
        return surf

    def _suelo(self, c, t):
        p = c.pista
        v = self.vista
        g0 = int(round(self.cam_y * PX_M - self._sy))
        filas = np.arange(VH)
        gi = g0 + Y_JUG - filas
        yw = gi / PX_M
        cpx = VW / 2 + (p.centro(yw) - self.cam_x) * PX_M + self._sx
        ox = np.round(ANCHO_SUELO / 2 - cpx).astype(np.int64)
        kb = np.floor_divide(gi, BLOQUE)
        r = 0
        while r < VH:
            e = r + 1
            while e < VH and ox[e] == ox[r] and kb[e] == kb[r]:
                e += 1
            bloque = self._bloque(p, int(kb[r]))
            fila_src = BLOQUE - 1 - (gi[r] - kb[r] * BLOQUE)
            v.blit(bloque, (0, r), (int(ox[r]), int(fila_src), VW, e - r))
            r = e
        if p.nivel in (2, 4):
            rng = np.random.default_rng(int(t * 4) + p.semilla)
            for _ in range(26):
                x0 = int(rng.uniform(0, VW))
                y0 = int(rng.uniform(14, VH))
                yy = self.cam_y + (Y_JUG - y0) / PX_M
                d = x0 - (VW / 2 + (p.centro(yy) - self.cam_x) * PX_M)
                h = p.semiancho(yy) * PX_M
                es_agua = (abs(d) > h + 7) if p.nivel == 2 else (d < -h - 22)
                if es_agua:
                    largo = 3 + int(3 * (0.5 + 0.5 * math.sin(t * 3 + x0)))
                    pygame.draw.line(v, (170, 210, 250), (x0, y0), (x0 + largo, y0))

    def _dibujar_vista(self, c, t):
        p = c.pista
        j = self.seguido(c)
        X, Y, T, F = self._interpolado(c)
        objetivo_x = p.centro(Y[j]) + (X[j] - p.centro(Y[j])) * 0.35
        self.cam_x = objetivo_x if self.cam_x is None else _lerp(self.cam_x, objetivo_x, 0.12)
        self.cam_y = Y[j]
        s = self.sacudida
        self._sx = np.random.uniform(-3, 3) * s / 0.45 if s > 0 else 0.0
        self._sy = np.random.uniform(-3, 3) * s / 0.45 if s > 0 else 0.0
        self._suelo(c, t)
        v = self.vista
        y_min = self.cam_y - (VH - Y_JUG) / PX_M - 6
        y_max = self.cam_y + Y_JUG / PX_M + 6
        for mx, my, vida in self.marcas:
            sx, sy = self._a_vista(mx, my)
            if 0 <= sy < VH:
                pygame.draw.rect(v, (40, 40, 44), (sx - 1, sy, 2, 2))
        for (yd, lado, off, tipo) in self._decoracion(p):
            if not (y_min < yd < y_max + 3):
                continue
            xd = p.centro(yd) + lado * (p.semiancho(yd) + off)
            spr = self.spr_deco[tipo]
            sx, sy = self._a_vista(xd, yd)
            if tipo not in ("flor", "bote"):
                v.blit(self._sombra(spr.get_width(), 5), (sx - spr.get_width() / 2 + 2, sy - 2))
            v.blit(spr, (sx - spr.get_width() / 2, sy - spr.get_height()))
        for xa, ya in zip(c.ax, c.ay):
            if y_min < ya < y_max:
                sx, sy = self._a_vista(xa, ya)
                v.blit(self.spr_aceite, (sx - 7, sy - 4))
        for xo, yo, to in zip(c.ox, c.oy, p.o_tipo):
            if y_min < yo < y_max:
                spr = self.spr_obst[int(to)]
                sx, sy = self._a_vista(xo, yo)
                v.blit(self._sombra(spr.get_width(), 4), (sx - spr.get_width() / 2 + 2, sy + spr.get_height() / 2 - 2))
                v.blit(spr, (sx - spr.get_width() / 2, sy - spr.get_height() / 2))
        yt = p.y_transito(T)
        xt_j = p.centro(yt) + F[j] * p.util(yt)
        k_arc = int(t * 10) % len(self.spr_arcoiris)
        for k in np.flatnonzero((yt > y_min) & (yt < y_max) & ~c.tomado[j]):
            tipo = p.t_tipo[k]
            if tipo == C.CAMION:
                spr = self.spr_camion
            elif tipo == C.ARCOIRIS:
                spr = self.spr_arcoiris[k_arc]
            else:
                spr = self.spr_sedan[C.TIPOS[tipo][0]]
            sx, sy = self._a_vista(xt_j[k], yt[k])
            v.blit(self._sombra(spr.get_width(), 6), (sx - spr.get_width() / 2 + 2, sy + spr.get_height() / 2 - 3))
            v.blit(spr, (sx - spr.get_width() / 2, sy - spr.get_height() / 2))
        if self.ver_sensores and c.vivo[j] and c.choque_t[j] <= 0:
            self._dibujar_sensores(c, j)
        en_gen = self.carrera_gen is not None
        for i in np.flatnonzero((Y > y_min) & (Y < y_max)):
            if i == j or (not c.vivo[i] and c.motivo[i] != META and not en_gen):
                continue
            sx, sy = self._a_vista(X[i], Y[i])
            spr = self.spr_gen[i % len(self.spr_gen)] if en_gen else self.spr_fantasma
            if en_gen:
                spr = pygame.transform.rotate(spr, -math.degrees(self._angulo(c, i)))
                v.blit(spr, (sx - spr.get_width() / 2, sy - spr.get_height() / 2))
                et = self.fp.texto(self.etiquetas[i], COLORES_GEN[i % len(COLORES_GEN)])
                v.blit(et, (sx - et.get_width() / 2, sy - 22))
            else:
                v.blit(spr, (sx - spr.get_width() / 2, sy - spr.get_height() / 2))
        sx, sy = self._a_vista(X[j], Y[j])
        if c.choque_t[j] <= 0:
            spr = self.spr_gen[j % len(self.spr_gen)] if en_gen else self.spr_jugador
            ang = self._angulo(c, j)
            v.blit(self._sombra(13, 7), (sx - 5, sy + 9))
            rot = pygame.transform.rotate(spr, -math.degrees(ang))
            v.blit(rot, (sx - rot.get_width() / 2, sy - rot.get_height() / 2))
            if en_gen:
                et = self.fp.texto(self.etiquetas[j] + " *", COLORES_GEN[j % len(COLORES_GEN)])
                v.blit(et, (sx - et.get_width() / 2, sy - 22))
        for q in self.particulas:
            sx, sy = self._a_vista(q[0], q[1])
            if not (-8 < sx < VW + 8 and -8 < sy < VH + 8):
                continue
            vida = q[4] / q[5]
            if q[6] == "humo":
                r = int(q[8] + (1 - vida) * 5)
                col = _mezcla((120, 120, 126), q[7], vida)
                pygame.draw.circle(v, col, (int(sx), int(sy)), max(1, r))
            elif q[6] == "fuego":
                col = _mezcla((120, 30, 20), q[7], vida)
                pygame.draw.circle(v, col, (int(sx), int(sy)), max(1, int(q[8] * vida + 1)))
            else:
                pygame.draw.rect(v, q[7], (int(sx), int(sy), q[8] + 1, q[8] + 1))
        if c.choque_t[j] > 0:
            r = int(6 + 8 * (c.choque_t[j] / C.CHOQUE_ESPERA))
            pygame.draw.circle(v, (255, 130, 30), (int(sx), int(sy)), r + 3)
            pygame.draw.circle(v, (255, 230, 90), (int(sx), int(sy)), r)
        for fx, fy, txt, vida in self.flotantes:
            sx, sy = self._a_vista(fx, fy + (1.2 - vida) * 6)
            v.blit(self.fp.texto(txt, (120, 255, 160)), (sx - 12, sy))
        if c.v[j] > 60:
            rng = np.random.default_rng(int(t * 30))
            for _ in range(int((c.v[j] - 60) / 6)):
                x = int(rng.uniform(0, VW))
                y = int(rng.uniform(0, VH))
                pygame.draw.line(v, (235, 240, 245), (x, y), (x, y + int(rng.uniform(6, 16))))
        self._hud(c, j)

    def _angulo(self, c, i):
        if c.derrape_t[i] > 0:
            return c.derrape_dir[i] * (0.5 * math.sin(c.t * 14) + 0.3)
        return float(np.clip(c.vx[i] / 25.0, -0.3, 0.3))

    def _dibujar_sensores(self, c, j):
        v = self.vista
        o = c.obs[j]
        i0 = 6 + 2 * len(C.MIRADAS)
        S = len(C.SONDAS)
        X, Y, _, _ = self._interpolado(c)
        sx0, sy0 = self._a_vista(X[j], Y[j] + C.AUTO_LARGO / 2)
        capa = pygame.Surface((VW, VH), pygame.SRCALPHA)
        for k, dx in enumerate(C.SONDAS):
            prox = max(o[i0 + k], o[i0 + 2 * S + k])
            dist = (1 - prox) * C.ALCANCE
            ex, ey = self._a_vista(X[j] + dx, Y[j] + C.AUTO_LARGO / 2 + dist)
            col = _mezcla((90, 255, 140), (255, 70, 70), prox ** 0.7)
            pygame.draw.line(capa, col + (110,), (sx0 + dx * PX_M * 0.25, sy0), (ex, ey), 1)
            if prox > 0.02:
                pygame.draw.circle(capa, col + (220,), (int(ex), int(ey)), 2)
        for d in C.MIRADAS:
            yy = Y[j] + d
            px, py = self._a_vista(c.pista.centro(yy), yy)
            pygame.draw.circle(capa, (255, 210, 80, 160), (int(px), int(py)), 2, 1)
        v.blit(capa, (0, 0))

    def _hud(self, c, j):
        v = self.vista
        fp = self.fp
        pygame.draw.rect(v, (0, 0, 0), (0, 0, VW, 12))
        puntos = max(0, int(c.aptitud()[j] * 10))
        v.blit(fp.texto(f"SCORE {puntos:06d}", (255, 255, 255)), (3, 2))
        v.blit(fp.texto("FUEL", (255, 210, 80)), (100, 2))
        comb = float(np.clip(c.combustible[j] / C.COMBUSTIBLE_INICIAL, 0, 1))
        pygame.draw.rect(v, (50, 50, 60), (126, 3, 40, 5))
        pygame.draw.rect(v, (80, 230, 120) if comb > 0.3 else (255, 90, 60), (126, 3, int(40 * comb), 5))
        v.blit(fp.texto(f"{c.v[j] * 3.6:3.0f}KM/H", (255, 255, 255)), (174, 2))
        v.blit(fp.texto("HI" if c.alto[j] else "LO", (255, 200, 60) if c.alto[j] else (110, 230, 140)), (238, 2))
        x = VW - 9
        top, bot = 34, VH - 12
        pygame.draw.rect(v, (0, 0, 0), (x - 4, top - 16, 9, bot - top + 22))
        pygame.draw.line(v, (90, 100, 120), (x, top), (x, bot), 1)
        v.blit(fp.texto("G", (255, 210, 80)), (x - 2, top - 14))
        frac = np.clip(c.y / c.pista.largo, 0, 1)
        en_gen = self.carrera_gen is not None
        for i in range(c.n):
            if i == j:
                continue
            yy = bot - (bot - top) * frac[i]
            col = COLORES_GEN[i % len(COLORES_GEN)] if en_gen else ((120, 135, 160) if c.vivo[i] else (55, 60, 72))
            pygame.draw.rect(v, col, (x - 1, int(yy), 3, 1))
        yy = bot - (bot - top) * frac[j]
        pygame.draw.rect(v, (255, 60, 60), (x - 3, int(yy) - 2, 7, 5))
        pygame.draw.rect(v, (255, 255, 255), (x - 3, int(yy) - 2, 7, 5), 1)
        b = self.banner
        if b[2] > 0 and b[0]:
            alfa = min(1.0, b[2] / 0.5)
            caja = pygame.Surface((VW, 44), pygame.SRCALPHA)
            caja.fill((0, 0, 0, int(170 * alfa)))
            v.blit(caja, (0, 120))
            t1 = fp.texto(b[0], (255, 210, 80), 2)
            v.blit(t1, ((VW - t1.get_width()) / 2, 126))
            t2 = fp.texto(b[1], (255, 255, 255))
            v.blit(t2, ((VW - t2.get_width()) / 2, 148))
        if self.turbo:
            t = fp.texto(">> TURBO", (255, 210, 80))
            v.blit(t, (4, VH - 12))
        if self.pausa:
            t = fp.texto("PAUSA", (255, 255, 255), 3)
            v.blit(t, ((VW - t.get_width()) / 2, VH / 2 - 10))
        if self.resultado and self.carrera_gen is not None and c.terminado:
            alto = 22 + 11 * len(self.resultado)
            caja = pygame.Surface((VW - 20, alto), pygame.SRCALPHA)
            caja.fill((0, 0, 0, 215))
            v.blit(caja, (10, 60))
            v.blit(fp.texto("RESULTADOS", (255, 210, 80)), (VW / 2 - 29, 64))
            for k, (pos, i, dato, ch) in enumerate(self.resultado):
                col = COLORES_GEN[i % len(COLORES_GEN)]
                v.blit(fp.texto(f"{pos}. {self.etiquetas[i]:<5} {dato}", col), (16, 78 + 11 * k))

    def _tarjeta(self, x, y, w, h, titulo=None):
        b = self.base
        sombra = pygame.Surface((w, h), pygame.SRCALPHA)
        pygame.draw.rect(sombra, (0, 0, 0, 90), (0, 0, w, h), border_radius=10)
        b.blit(sombra, (x + 2, y + 3))
        pygame.draw.rect(b, TARJETA, (x, y, w, h), border_radius=10)
        pygame.draw.rect(b, BORDE, (x, y, w, h), 1, border_radius=10)
        pygame.draw.line(b, _mezcla(TARJETA, (255, 255, 255), 0.06), (x + 10, y + 1), (x + w - 10, y + 1))
        if titulo:
            pygame.draw.circle(b, ORO, (x + 15, y + 15), 3)
            self.base.blit(self.f_peq.render(titulo.upper(), True, TENUE), (x + 24, y + 7))

    def _txt(self, s, pos, fuente=None, color=TEXTO, ancla="tl"):
        img = (fuente or self.f).render(str(s), True, color)
        r = img.get_rect(**{_ANCLAS[ancla]: pos})
        self.base.blit(img, r)
        return r

    def _boton(self, x, y, w, texto, accion, activo=False):
        r = pygame.Rect(x, y, w, 28)
        mx, my = self._a_base(pygame.mouse.get_pos())
        sobre = r.collidepoint(mx, my)
        if activo:
            col = _mezcla(TARJETA, ORO, 0.32 if sobre else 0.24)
            borde = _mezcla(BORDE, ORO, 0.55)
        else:
            col = _mezcla(TARJETA, (255, 255, 255), 0.09 if sobre else 0.045)
            borde = _mezcla(BORDE, (255, 255, 255), 0.12 if sobre else 0.0)
        pygame.draw.rect(self.base, col, r, border_radius=7)
        pygame.draw.rect(self.base, borde, r, 1, border_radius=7)
        self._txt(texto, r.center, self.f, ORO if activo else TEXTO, "c")
        self.botones.append((r, accion))

    def _paneles(self, c, fps):
        b = self.base
        j = self.seguido(c)
        en_gen = self.carrera_gen is not None
        x0 = VISTA_X + VW * EV + 16
        titulo = self.fp.texto("ROAD FIGHTER", ROJO, 3)
        b.blit(titulo, (x0, 8))
        self._txt("EVOLUTIVO 2 · PPO", (x0 + titulo.get_width() + 12, 6), self.f_titulo, TEXTO)
        self._txt(f"Política {C.N_ENTRADAS} > {C.PPO_OCULTAS[0]} > {C.PPO_OCULTAS[1]} > {C.SALIDAS}  ·  "
                  f"PPO actor-crítico + imitación DAgger (β {self.e.beta:.2f})",
                  (x0 + titulo.get_width() + 12, 30), self.f_peq, TENUE)
        self._txt(f"{fps:4.0f} fps · x{VELOCIDADES[self.i_vel]}{' · MODO RÁPIDO' if self.turbo else ''}",
                  (BASE_W - 16, 10), self.f_mono, TENUE, "tr")
        ancho_a, ancho_b = 340, BASE_W - 16 - (x0 + 340 + 12)
        xa, xb = x0, x0 + ancho_a + 12
        y = 56
        self._tarjeta(xa, y, ancho_a, 168, "carrera de generaciones" if en_gen else "generación")
        if en_gen:
            self._txt(c.pista.nombre.upper(), (xa + 12, y + 28), self.f_num, ORO)
            for k, et in enumerate(self.etiquetas):
                col = COLORES_GEN[k % len(COLORES_GEN)]
                estado = "META" if c.motivo[k] == META else ("en carrera" if c.vivo[k] else MOTIVOS[c.motivo[k]])
                self._txt(f"{et}", (xa + 14 + (k % 2) * 165, y + 66 + (k // 2) * 22), self.f_med, col)
                self._txt(f"{c.progreso()[k]:5.0f} m · {estado}", (xa + 60 + (k % 2) * 165, y + 68 + (k // 2) * 22),
                          self.f_peq, TEXTO)
        else:
            self._txt(f"{self.e.generacion}", (xa + 12, y + 24), self.f_num, ORO)
            p = self.e.pista
            self._txt(f"{p.nombre}", (xa + 110, y + 24), self.f_med, TEXTO)
            for k in range(C.NIVEL_MAX):
                col = ORO if k < p.nivel else BORDE
                pygame.draw.circle(b, col, (xa + 116 + k * 16, y + 52), 5)
            self._txt(f"racha {self.e.racha}/{C.RACHA_PARA_SUBIR}", (xa + 186, y + 46), self.f_peq, TENUE)
            vivos = int(c.vivo.sum())
            self._txt(f"en carrera {vivos}/{c.n}", (xa + 12, y + 68), self.f, TEXTO)
            pygame.draw.rect(b, (30, 38, 54), (xa + 130, y + 72, ancho_a - 144, 8), border_radius=4)
            pygame.draw.rect(b, AZUL, (xa + 130, y + 72, int((ancho_a - 144) * vivos / c.n), 8), border_radius=4)
            h = self.e.historial[-1] if self.e.historial else None
            filas = [("mejor (gen. anterior)", f"{h['mejor']:.0f}" if h else "—", ORO),
                     ("promedio", f"{h['promedio']:.0f}" if h else "—", AZUL),
                     ("llegaron a la meta", f"{h['llegaron']:.0f} %" if h else "—", VERDE),
                     ("arcoíris (líder · promedio)",
                      f"{h.get('arcoiris_lider', 0)} · {h.get('arcoiris_prom', 0):.1f}" if h else "—", MAGENTA)]
            for k, (et, val, col) in enumerate(filas):
                self._txt(et, (xa + 12, y + 92 + k * 18), self.f_peq, TENUE)
                self._txt(val, (xa + ancho_a - 12, y + 90 + k * 18), self.f_mono, col, "tr")
        y = 232
        self._tarjeta(xa, y, ancho_a, 196, "evolución de la recompensa")
        self._grafica(xa + 8, y + 26, ancho_a - 16, 162)
        y = 436
        self._tarjeta(xa, y, ancho_a, 128, "población (cada cuadro es un auto)")
        n = c.n
        cols = 20
        lado = min(14, (ancho_a - 24) // cols - 2)
        for i in range(n):
            px = xa + 12 + (i % cols) * (lado + 2)
            py = y + 28 + (i // cols) * (lado + 2)
            col = ESTADO_COLOR.get(int(c.motivo[i]), TENUE)
            if en_gen:
                col = COLORES_GEN[i % len(COLORES_GEN)]
            frac = float(np.clip(c.y[i] / c.pista.largo, 0, 1))
            pygame.draw.rect(b, (40, 48, 64), (px, py, lado, lado))
            pygame.draw.rect(b, col, (px, py + lado - max(1, int(lado * frac)), lado, max(1, int(lado * frac))))
            if i == j:
                pygame.draw.rect(b, (255, 255, 255), (px - 1, py - 1, lado + 2, lado + 2), 1)
        ley = [("en carrera", ESTADO_COLOR[VIVO]), ("meta", VERDE), ("sin comb.", NARANJA), ("atascado", ESTADO_COLOR[ATASCADO])]
        for k, (et, col) in enumerate(ley):
            pygame.draw.rect(b, col, (xa + 12 + k * 82, y + 108, 8, 8))
            self._txt(et, (xa + 24 + k * 82, y + 104), self.f_peq, TENUE)
        self.botones = []
        y = 572
        self._tarjeta(xa, y, ancho_a, 132, "controles")
        self._boton(xa + 12, y + 28, 100, "Pausa" if not self.pausa else "Seguir", lambda: setattr(self, "pausa", not self.pausa), self.pausa)
        self._boton(xa + 118, y + 28, 100, "Animar" if self.turbo else "Modo rápido", self.alternar_turbo,
                    self.turbo)
        self._boton(xa + 224, y + 28, 32, "−", lambda: setattr(self, "i_vel", max(0, self.i_vel - 1)))
        self._txt(f"x{VELOCIDADES[self.i_vel]}", (xa + 280, y + 42), self.f_mono, TEXTO, "c")
        self._boton(xa + 300, y + 28, 32, "+", lambda: setattr(self, "i_vel", min(len(VELOCIDADES) - 1, self.i_vel + 1)))
        self._boton(xa + 12, y + 62, 176, "Volver al entrenamiento" if en_gen else "Carrera de generaciones",
                    self.carrera_generaciones, en_gen)
        self._boton(xa + 194, y + 62, 66, "Guardar", self.guardar)
        self._boton(xa + 266, y + 62, 66, "Reiniciar", self.pedir_reinicio)
        self._boton(xa + 12, y + 96, 104, "Sensores", lambda: setattr(self, "ver_sensores", not self.ver_sensores), self.ver_sensores)
        self._boton(xa + 122, y + 96, 104, "Red neuronal", lambda: setattr(self, "ver_red", not self.ver_red), self.ver_red)
        texto_son = "Sonido" if self.sonido.activo else "Sin audio"
        self._boton(xa + 232, y + 96, 100, texto_son, self.sonido.alternar,
                    not self.sonido.mudo and self.sonido.activo)
        self._txt("ESPACIO pausa · T modo rápido / animar · +/− velocidad · G generaciones · "
                  "TAB/L auto seguido · S sensores · N red · M sonido · F5 guardar · F11", (xa, y + 140), self.f_peq, TENUE)
        if not self.sonido.activo:
            self._txt(f"Sin audio: {self.sonido.error or 'no hay dispositivo de sonido'}",
                      (xa, BASE_H - 40), self.f_peq, NARANJA)
        if self.confirmar_reinicio > 0:
            self._txt("¿Borrar lo aprendido? Pulsa Y para confirmar", (xa, BASE_H - 22), self.f_med, ROJO)
        y = 56
        alto_red = 452
        self._tarjeta(xb, y, ancho_b, alto_red, "red neuronal del auto seguido (en vivo)")
        if self.ver_red:
            self._red(c, j, xb + 8, y + 24, ancho_b - 16, alto_red - 30)
        else:
            self._txt("(oculta: N)", (xb + ancho_b / 2, y + alto_red / 2), self.f, TENUE, "c")
        y = 516
        self._tarjeta(xb, y, ancho_b, 188, "telemetría")
        self._telemetria(c, j, xb, y, ancho_b)

    def _grafica(self, x, y, w, h):
        b = self.base
        hist = self.e.historial[-240:]
        if len(hist) < 2:
            self._txt("(aparece al terminar la primera generación)", (x + w / 2, y + h / 2), self.f_peq, TENUE, "c")
            return
        mejor = np.array([q["mejor"] for q in hist])
        prom = np.array([q["promedio"] for q in hist])
        lo, hi = min(prom.min(), 0.0), mejor.max() * 1.02 + 1
        paso = _paso_eje(hi - lo, 4)
        lo, hi = math.floor(lo / paso) * paso, math.ceil(hi / paso) * paso
        x0, x1, y0, y1 = x + 34, x + w - 4, y + h - 16, y + 6

        def pt(i, val):
            return x0 + (x1 - x0) * i / (len(hist) - 1), y0 - (y0 - y1) * (val - lo) / (hi - lo)

        val = lo
        while val <= hi + 1e-9:
            _, yy = pt(0, val)
            pygame.draw.line(b, REJILLA, (x0, yy), (x1, yy))
            self._txt(f"{val:,.0f}".replace(",", " "), (x0 - 4, yy), self.f_peq, TENUE, "mr")
            val += paso
        for i in range(len(hist) - 1):
            if hist[i]["nivel"] != hist[i + 1]["nivel"]:
                xx, _ = pt(i + 0.5, 0)
                for yy in range(int(y1), int(y0), 6):
                    pygame.draw.line(b, (70, 80, 100), (xx, yy), (xx, min(yy + 2, y0)))
                self._txt(C.NIVELES[hist[i + 1]["nivel"] - 1][0][:3], (xx + 2, y1), self.f_peq, TENUE)
        linea = [pt(i, v) for i, v in enumerate(mejor)]
        capa = pygame.Surface((w, h), pygame.SRCALPHA)
        pygame.draw.polygon(capa, (*ORO, 34), [(x0 - x, y0 - y)] + [(px - x, py - y) for px, py in linea]
                            + [(x1 - x, y0 - y)])
        b.blit(capa, (x, y))
        area = [pt(i, v) for i, v in enumerate(prom)]
        pygame.draw.lines(b, AZUL, False, area, 1)
        pygame.draw.lines(b, ORO, False, linea, 2)
        pygame.draw.circle(b, ORO, (int(linea[-1][0]), int(linea[-1][1])), 4)
        pygame.draw.circle(b, TARJETA, (int(linea[-1][0]), int(linea[-1][1])), 4, 1)
        self._txt(f"gen {hist[0]['generacion']}", (x0, y0 + 2), self.f_peq, TENUE)
        self._txt(f"gen {hist[-1]['generacion']}", (x1, y0 + 2), self.f_peq, TENUE, "tr")
        r = self._txt("promedio", (x + w - 4, y - 18), self.f_peq, TENUE, "tr")
        pygame.draw.line(b, AZUL, (r.left - 18, r.centery), (r.left - 5, r.centery), 2)
        r = self._txt("mejor", (r.left - 26, y - 18), self.f_peq, TENUE, "tr")
        pygame.draw.line(b, ORO, (r.left - 18, r.centery), (r.left - 5, r.centery), 2)

    def _red(self, c, j, x, y, w, h):
        b = self.base
        if getattr(c, "politicas", None) is not None:
            red, norm = c.politicas.redes[j], c.politicas.normas[j]
        else:
            pol = self.e.pol
            red, norm = pol._red_actor(), pol.norm
        vista = vista_red(red, norm, c.obs[j])
        capas = vista["capas"]
        cols = (x + 58, x + w * 0.46, x + w * 0.72, x + w - 70)

        def ys(n, margen=8):
            return [y + margen + (h - 2 * margen) * (k_ + 0.5) / n for k_ in range(n)]

        pos = [list(zip([cols[0]] * capas[0], ys(capas[0]))), list(zip([cols[1]] * capas[1], ys(capas[1], 20))),
               list(zip([cols[2]] * capas[2], ys(capas[2], 60))), list(zip([cols[3]] * capas[3], ys(capas[3], 150)))]
        clave = (id(c), j, self.e.generacion, float(red["W0"][0, 0]))
        if self._cache_red[0] != clave:
            capa = pygame.Surface((int(w) + 2, int(h) + 2), pygame.SRCALPHA)
            for li, (W, top) in enumerate(zip(vista["pesos"], (260, 300, 48))):
                pesos = np.abs(W).ravel()
                umbral = np.sort(pesos)[-min(top, len(pesos))]
                wmax = pesos.max() + 1e-9
                for p_i, p_o in zip(*np.nonzero(np.abs(W) >= umbral)):
                    val = W[p_i, p_o]
                    alfa = int(30 + 170 * abs(val) / wmax)
                    col = (61, 220, 132, alfa) if val > 0 else (232, 92, 200, alfa)
                    (ax_, ay_), (bx_, by_) = pos[li][p_i], pos[li + 1][p_o]
                    pygame.draw.aaline(capa, col, (ax_ - x, ay_ - y), (bx_ - x, by_ - y))
            self._cache_red = (clave, capa)
        b.blit(self._cache_red[1], (x, y))
        for capa_i, (puntos, valores) in enumerate(zip(pos, vista["act"])):
            for (px, py), val in zip(puntos, valores):
                col = _mezcla((60, 140, 255), (255, 160, 60), (float(val) + 1) / 2)
                r = 4 if capa_i == 0 else 6 if capa_i < 3 else 9
                pygame.draw.circle(b, col, (int(px), int(py)), r)
                pygame.draw.circle(b, (12, 14, 20), (int(px), int(py)), r, 1)
        for (px, py), nombre in zip(pos[0], NOMBRES_ENTRADAS):
            self._txt(nombre, (px - 7, py), self.f_peq, TENUE, "mr")
        for (px, py), nombre, val in zip(pos[3], ("VOLANTE", "ACELERADOR", "MARCHA"), c.ctrl[j]):
            extra = ("HIGH" if val > 0 else "LOW") if nombre == "MARCHA" else f"{val:+.2f}"
            self._txt(nombre, (px + 14, py - 8), self.f_peq, TEXTO)
            self._txt(extra, (px + 14, py + 4), self.f_mono, ORO)
        self._txt("sensores", (cols[0], y + h + 2), self.f_peq, TENUE, "c")
        self._txt("capa 1 (24 de 64)", (cols[1], y + h + 2), self.f_peq, TENUE, "c")
        self._txt("capa 2 (16 de 64)", (cols[2], y + h + 2), self.f_peq, TENUE, "c")

    def _telemetria(self, c, j, x, y, w):
        b = self.base
        cx, cy, r = x + 78, y + 104, 56
        rect = pygame.Rect(cx - r, cy - r, 2 * r, 2 * r)
        pygame.draw.arc(b, (34, 44, 62), rect, math.radians(-30), math.radians(210), 9)
        frac = float(np.clip(c.v[j] / C.VMAX_HIGH, 0, 1))
        if frac > 0.005:
            pygame.draw.arc(b, ROJO if frac > 0.8 else ORO, rect, math.radians(210 - 240 * frac),
                            math.radians(210), 9)
        self._txt(f"{c.v[j] * 3.6:.0f}", (cx, cy - 4), self.f_num, TEXTO, "c")
        self._txt("km/h", (cx, cy + 20), self.f_peq, TENUE, "c")
        alto = bool(c.alto[j])
        pygame.draw.rect(b, (74, 58, 12) if alto else (23, 58, 36), (cx - 28, cy + 36, 56, 20), border_radius=5)
        self._txt("HIGH" if alto else "LOW", (cx, cy + 46), self.f_mono, ORO if alto else VERDE, "c")
        x1 = x + 160
        comb = float(np.clip(c.combustible[j] / C.COMBUSTIBLE_INICIAL, 0, 1))
        self._txt("combustible", (x1, y + 28), self.f_peq, TENUE)
        pygame.draw.rect(b, (30, 38, 54), (x1, y + 44, w - 176, 10), border_radius=4)
        pygame.draw.rect(b, VERDE if comb > 0.35 else ORO if comb > 0.15 else ROJO,
                         (x1, y + 44, int((w - 176) * comb), 10), border_radius=4)
        datos = [("avance", f"{c.progreso()[j]:.0f} / {c.pista.largo:.0f} m"),
                 ("choques · derrapes", f"{int(c.choques[j])} · {int(c.derrapes[j])}"),
                 ("arcoíris · rebases", f"{int(c.arcoiris_n[j])} · {int(c.rebases[j])}"),
                 ("recompensa", f"{c.aptitud()[j]:.0f}"),
                 ("estado", MOTIVOS[int(c.motivo[j])])]
        for k, (et, val) in enumerate(datos):
            self._txt(et, (x1, y + 60 + k * 17), self.f_peq, TENUE)
            self._txt(val, (x + w - 12, y + 58 + k * 17), self.f_mono, TEXTO, "tr")
        seg = "líder" if self.seguir is None else f"auto #{j}"
        self._txt(f"siguiendo: {seg}" + (f" ({self.etiquetas[j]})" if self.carrera_gen is not None else ""),
                  (x1, y + 150), self.f_peq, AZUL)
        ang = float(c.ctrl[j, 0]) * 1.2
        vx, vy, rv = x + w - 34, y + 160, 14
        pygame.draw.circle(b, (120, 130, 150), (vx, vy), rv, 2)
        pygame.draw.line(b, ORO, (vx, vy), (vx + rv * math.sin(ang), vy - rv * math.cos(ang)), 2)

    def _dibujar(self, dt):
        c = self.carrera()
        t = time.perf_counter()
        self.base.fill(FONDO)
        rapido = self.turbo and self.carrera_gen is None
        if self.ensenando is not None:
            self._paneles(c, self.reloj.get_fps())
            self._pantalla_maestro()
            self._grabacion()
            w, h = self.ventana.get_size()
            self.ventana.blit(self.base if (w, h) == (BASE_W, BASE_H)
                              else pygame.transform.smoothscale(self.base, (w, h)), (0, 0))
            pygame.display.flip()
            return
        if not rapido:
            self._dibujar_vista(c, t)
            grande = pygame.transform.scale(self.vista, (VW * EV, VH * EV))
            self.base.blit(grande, (VISTA_X, VISTA_Y))
            self._txt("vista del auto seguido · los demás autos de la generación son fantasmas"
                      if self.carrera_gen is None
                      else "cada campeona corre en su propio mundo (no chocan entre ellas)",
                      (VISTA_X, VISTA_Y - 22), self.f_peq, TENUE)
        pygame.draw.rect(self.base, BORDE, (VISTA_X - 1, VISTA_Y - 1, VW * EV + 2, VH * EV + 2), 1)
        self._paneles(c, self.reloj.get_fps())
        if rapido:
            self._pantalla_rapida(c)
        if self.e.actualizando and self.carrera_gen is None:
            self._caja_aprendiendo()
        self._grabacion()
        w, h = self.ventana.get_size()
        if (w, h) == (BASE_W, BASE_H):
            self.ventana.blit(self.base, (0, 0))
        else:
            self.ventana.blit(pygame.transform.smoothscale(self.base, (w, h)), (0, 0))
        pygame.display.flip()


    def _caja_aprendiendo(self):
        b = self.base
        x0, w = VISTA_X + 30, VW * EV - 60
        y0 = VISTA_Y + 250
        caja = pygame.Surface((w, 190), pygame.SRCALPHA)
        caja.fill((8, 12, 20, 235))
        b.blit(caja, (x0, y0))
        pygame.draw.rect(b, ORO, (x0, y0, w, 190), 2, border_radius=6)
        t = self.fp.texto("APRENDIENDO", ORO, 3)
        b.blit(t, (x0 + (w - t.get_width()) / 2, y0 + 14))
        self._txt("PPO: la red repasa cada decisión de la carrera y refuerza lo que salió mejor",
                  (x0 + w / 2, y0 + 52), self.f_peq, TEXTO, "c")
        ang = time.perf_counter() * 5
        for k in range(8):
            a = ang + k * 0.785
            pygame.draw.circle(b, _mezcla((40, 50, 70), ORO, k / 7),
                               (int(x0 + w / 2 + 16 * math.cos(a)), int(y0 + 82 + 16 * math.sin(a))), 3)
        for k, m in enumerate(self.e.msgs[-4:]):
            self._txt(m, (x0 + 16, y0 + 108 + k * 18), self.f_peq, VERDE if k == len(self.e.msgs[-4:]) - 1 else TENUE)

    def _pantalla_maestro(self):
        b = self.base
        x0, y0, w, h = VISTA_X, VISTA_Y, VW * EV, VH * EV
        for k in range(16):
            pygame.draw.rect(b, _mezcla((12, 18, 26), (16, 30, 30), k / 15), (x0, y0 + h * k / 16, w, h / 16 + 1))
        t1 = self.fp.texto("EL MAESTRO", ORO, 4)
        t2 = self.fp.texto("ENSENA A MANEJAR", ORO, 3)
        b.blit(t1, (x0 + (w - t1.get_width()) / 2, y0 + 40))
        b.blit(t2, (x0 + (w - t2.get_width()) / 2, y0 + 84))
        lineas = ["Un piloto programado con las estrategias de Road Fighter maneja los",
                  "4 recorridos; la red aprende a hacer lo mismo (imitación). Después",
                  "el refuerzo profundo (PPO) la sigue mejorando. Se hace una sola vez."]
        for k, txt in enumerate(lineas):
            self._txt(txt, (x0 + w / 2, y0 + 140 + k * 20), self.f, TEXTO, "c")
        ang = time.perf_counter() * 4
        cx, cy = x0 + w / 2, y0 + 250
        for k in range(10):
            a = ang + k * 0.628
            col = _mezcla((40, 50, 70), ORO, k / 9)
            pygame.draw.circle(b, col, (int(cx + 26 * math.cos(a)), int(cy + 26 * math.sin(a))), 4)
        for k, m in enumerate(self.msgs_maestro[-10:]):
            self._txt(m, (x0 + 40, y0 + 310 + k * 22), self.f, VERDE if k == len(self.msgs_maestro[-10:]) - 1 else TENUE)

    def _grabacion(self):
        g = self.grabar
        r = pygame.Rect(VISTA_X + VW * EV - 136, 8, 136, 26)
        mx, my = self._a_base(pygame.mouse.get_pos())
        sobre = r.collidepoint(mx, my)
        if g.grabando:
            col = (176, 40, 44) if sobre else (150, 30, 34)
        else:
            col = (38, 50, 72) if sobre else (27, 36, 51)
        pygame.draw.rect(self.base, col, r, border_radius=6)
        pygame.draw.rect(self.base, (239, 83, 80), r, 1, border_radius=6)
        if g.grabando:
            if int(time.perf_counter() * 2) % 2 == 0:
                pygame.draw.rect(self.base, (255, 255, 255), (r.x + 11, r.centery - 5, 10, 10))
        else:
            pygame.draw.circle(self.base, (239, 83, 80), (r.x + 16, r.centery), 6)
        self._txt(g.texto(), (r.x + 30, r.centery), self.f, TEXTO, "ml")
        self.botones.append((r, lambda: g.alternar(self.base)))
        texto, t0 = g.mensaje
        if texto and time.perf_counter() - t0 < 5:
            img = self.f_peq.render(texto, True, TEXTO)
            caja = img.get_rect(topright=(r.right - 6, r.bottom + 12)).inflate(14, 8)
            pygame.draw.rect(self.base, (10, 12, 18), caja, border_radius=5)
            pygame.draw.rect(self.base, (239, 83, 80), caja, 1, border_radius=5)
            self.base.blit(img, img.get_rect(center=caja.center))
        g.cuadro(self.base)

    def _pantalla_rapida(self, c):
        b = self.base
        x0, y0, w, h = VISTA_X, VISTA_Y, VW * EV, VH * EV
        for k in range(16):
            col = _mezcla((12, 15, 24), (22, 18, 34), k / 15)
            pygame.draw.rect(b, col, (x0, y0 + h * k / 16, w, h / 16 + 1))
        self._txt("entrenando sin animación · la ventana sigue abierta", (x0, y0 - 22), self.f_peq, TENUE)
        titulo = self.fp.texto("MODO RAPIDO", ORO, 4)
        b.blit(titulo, (x0 + (w - titulo.get_width()) / 2, y0 + 30))
        self._txt("Sólo física y aprendizaje: la carretera no se dibuja.", (x0 + w / 2, y0 + 82),
                  self.f, TEXTO, "c")
        r = pygame.Rect(x0 + w / 2 - 110, y0 + 104, 220, 40)
        mx, my = self._a_base(pygame.mouse.get_pos())
        pygame.draw.rect(b, (60, 90, 140) if r.collidepoint(mx, my) else (38, 60, 98), r, border_radius=8)
        pygame.draw.rect(b, AZUL, r, 1, border_radius=8)
        self._txt("Animar  (T)", r.center, self.f_titulo, TEXTO, "c")
        self.botones.append((r, self.alternar_turbo))
        y = y0 + 168
        p = c.pista
        avance = float(c.progreso().max()) / p.largo
        self._txt(f"Generación {self.e.generacion}  ·  {p.nombre} (nivel {p.nivel}/{C.NIVEL_MAX})",
                  (x0 + 24, y), self.f_med, ORO)
        pygame.draw.rect(b, (30, 38, 54), (x0 + 24, y + 28, w - 48, 14), border_radius=6)
        pygame.draw.rect(b, ORO, (x0 + 24, y + 28, int((w - 48) * avance), 14), border_radius=6)
        self._txt(f"líder al {100 * avance:.0f} %  ·  {int(c.vivo.sum())}/{c.n} autos en carrera  ·  "
                  f"t = {c.t:.0f} s", (x0 + 24, y + 48), self.f, TEXTO)
        seg = max(time.perf_counter() - self.rapido_t0, 1e-6)
        ritmo = self.rapido_gens / seg * 60
        self._txt(f"en modo rápido: {self.rapido_gens} generaciones en {seg / 60:.1f} min"
                  f"  ·  {ritmo:.1f} gen/min", (x0 + 24, y + 70), self.f, AZUL)
        y += 110
        self._txt("ÚLTIMAS GENERACIONES", (x0 + 24, y), self.f_peq, TENUE)
        cols = (("gen", 24), ("recorrido", 70), ("mejor", 168), ("llegaron", 232), ("rebases", 312),
                ("arcoíris", 388))
        for nombre, dx in cols:
            self._txt(nombre, (x0 + dx, y + 18), self.f_peq, TENUE)
        for k, r_ in enumerate(reversed(self.registro[-12:])):
            yy = y + 38 + k * 22
            col = VERDE if r_.get("lider_llego") else TEXTO
            vals = (str(r_["generacion"]), r_["pista"], f"{r_['mejor']:.0f}", f"{r_['llegaron']:.0f} %",
                    f"{r_.get('rebases_lider', 0)}", f"{r_.get('arcoiris_lider', 0)}/{r_.get('arcoiris_pista', 0)}")
            for (nombre, dx), val in zip(cols, vals):
                self._txt(val, (x0 + dx, yy), self.f_mono, col)
            if r_.get("subio"):
                self._txt("sube de nivel", (x0 + 440, yy), self.f_peq, ORO)
        if not self.registro:
            self._txt("(aparecen aquí al terminar cada generación)", (x0 + w / 2, y + 60), self.f_peq, TENUE, "c")


def ejecutar(entrenador=None, demo=False, generaciones=False, rapido=False):
    j = Juego(entrenador, demo=demo, generaciones=generaciones)
    if rapido:
        j.alternar_turbo()
    j.correr()
