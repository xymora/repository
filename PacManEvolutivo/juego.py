import math
import os
import time

import numpy as np
import pygame

import cerebro as B
import config as C
import sprites as SP
from evolucion import Entrenador, cargar_mejor, cargar_salon, elegir_generaciones, resumen_generacion
from laberinto import DIRS, TEMAS, Nivel
from grabador import GrabadorPygame
from sonido import Sonido
from simulacion import (ATASCADO, CASA, FUERA, META, MOTIVOS, OJOS, SALIENDO, SIN_VIDAS, TIEMPO,
                        VIVO, Partida)

BASE_W, BASE_H = 1280, 760
TS = 10
HUD_ARR, HUD_ABA = 18, 14
VW, VH = C.ANCHO * TS, C.ALTO * TS + HUD_ARR + HUD_ABA
EV = 2
VISTA_X, VISTA_Y = 16, 40
VELOCIDADES = (1, 2, 4, 8, 16)
SEGUIR_TRAS_FIN = 1.8

FONDO = (14, 16, 20)
TARJETA = (22, 25, 32)
BORDE = (38, 43, 54)
TEXTO = (232, 235, 241)
TENUE = (138, 147, 166)
REJILLA = (35, 40, 53)
ROJO = (255, 64, 64)
ORO = (255, 214, 50)
VERDE = (61, 220, 132)
AZUL = (79, 179, 255)
MAGENTA = (232, 92, 200)
NARANJA = (255, 140, 66)
COLORES_GEN = ((255, 226, 30), (255, 64, 64), (61, 220, 132), (79, 179, 255), (199, 125, 255),
               (255, 140, 66), (240, 240, 240), (46, 230, 214))
ESTADO_COLOR = {VIVO: (150, 168, 192), META: VERDE, SIN_VIDAS: ROJO, ATASCADO: (90, 98, 112),
                TIEMPO: (150, 110, 220)}
NOMBRES_DIR = ("ARRIBA", "IZQUIERDA", "ABAJO", "DERECHA")
_SENS = ("libre", "punto", "densid", "peligro", "escape", "comible", "energ", "fruta")
NOMBRES_ENTRADAS = ([f"{s} {d}" for d in ("ar", "iz", "ab", "de") for s in _SENS]
                    + ["va ar", "va iz", "va ab", "va de", "susto", "quedan", "persec", "en casa"])
ESTADO_FANT = {CASA: "en casa", SALIENDO: "saliendo", FUERA: "afuera", OJOS: "ojos"}

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



def _a_px(fila, col):
    return col * TS + TS / 2, HUD_ARR + fila * TS + TS / 2


class Juego:
    def __init__(self, entrenador=None, demo=False, generaciones=False):
        os.environ.setdefault("SDL_VIDEO_CENTERED", "1")
        pygame.mixer.pre_init(44100, -16, 2, 512)
        pygame.init()
        info = pygame.display.Info()
        f = min(1.0, (info.current_w - 40) / BASE_W, (info.current_h - 90) / BASE_H)
        self.ventana = pygame.display.set_mode((int(BASE_W * f), int(BASE_H * f)), pygame.RESIZABLE)
        pygame.display.set_caption("Pac-Man evolutivo — comecocos que aprenden por generaciones")
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
        self._paredes = {}
        self._prev = None
        self.e = entrenador or Entrenador()
        self.pausa = False
        self.turbo = False
        self.i_vel = 0
        self.ver_sensores = True
        self.ver_red = True
        self.seguir = None
        self._auto = None
        self._auto_partida = None
        self.aviso = ("", 0.0)
        self.carrera_gen = None
        self.etiquetas = []
        self.resultado = None
        self.particulas = []
        self.flotantes = []
        self._cache_red = (None, None)
        self.banner = ("", "", 0.0)
        self.confirmar_reinicio = 0.0
        self.acum = 0.0
        self.botones = []
        self.ultimo_resumen = None
        self.registro = []
        self.rapido_t0 = time.perf_counter()
        self.rapido_gens = 0
        self.record = 0
        self._anunciar_generacion()
        if demo or generaciones:
            self.carrera_generaciones(solo_mejor=demo)

    def _sprites(self):
        self.spr_pac = SP.cuadros_comecocos()
        self.spr_muerte = SP.cuadros_muerte()
        self.spr_pac_gen = [SP.cuadros_comecocos(c) for c in COLORES_GEN]
        self.spr_fant = [[[SP.fantasma(col, d, k) for k in range(2)] for d in range(4)]
                         for col in SP.COLORES_FANTASMA]
        self.spr_susto = [[SP.fantasma_susto(k, blanco) for k in range(2)] for blanco in (False, True)]
        self.spr_ojos = [SP.solo_ojos(d) for d in range(4)]
        self.spr_frutas = SP.frutas()
        self.spr_vida = SP.comecocos(0.6, 1, tam=9)
        sombra = pygame.Surface((9, 9), pygame.SRCALPHA)
        pygame.draw.circle(sombra, (255, 230, 120, 70), (4, 4), 4)
        self.spr_sombra = sombra

    def paredes(self, lab):
        clave = (lab.semilla, lab.tema)
        if clave not in self._paredes:
            col, claro, _, _ = TEMAS[lab.tema]
            if len(self._paredes) > 12:
                self._paredes.clear()
            self._paredes[clave] = SP.paredes(lab.grid, TS, col, claro)
        return self._paredes[clave]

    def brillo(self, lab):
        clave = ("brillo", lab.semilla, lab.tema)
        if clave not in self._paredes:
            s = self.paredes(lab)
            w, h = s.get_size()
            halo = pygame.Surface((w, h))
            for k, f in ((3, 140), (7, 120)):
                borroso = pygame.transform.smoothscale(pygame.transform.smoothscale(s, (w // k, h // k)), (w, h))
                borroso.fill((f, f, f), special_flags=pygame.BLEND_MULT)
                halo.blit(borroso, (0, 0), special_flags=pygame.BLEND_ADD)
            self._paredes[clave] = halo
        return self._paredes[clave]

    def fruta_de(self, nivel):
        return self.spr_frutas[min(nivel, len(self.spr_frutas)) - 1]

    def carrera(self):
        return self.carrera_gen if self.carrera_gen is not None else self.e.partida

    def seguido(self, c):
        if self.seguir is not None and self.seguir < c.n:
            if self._sigue_visible(c, self.seguir):
                return self.seguir
            self.seguir = None
        i = self._auto
        if i is not None and self._auto_partida == id(c) and i < c.n and self._sigue_visible(c, i):
            return i
        nuevo = c.lider()
        if i is not None and self._auto_partida == id(c) and nuevo != i:
            self.aviso = (f"la cámara pasa a la líder (#{nuevo})", 2.0)
        self._auto, self._auto_partida = nuevo, id(c)
        self._prev = None
        return nuevo

    def _sigue_visible(self, c, i):
        return bool(c.vivo[i]) or (c.t - float(c.t_fin[i]) < SEGUIR_TRAS_FIN) or not c.vivo.any()

    def _anunciar_generacion(self):
        p = self.e.niv
        self.banner = (f"NIVEL {p.nivel}  {p.nombre}", f"GENERACION {self.e.generacion}   READY!", 2.2)
        self.particulas.clear()
        self.flotantes.clear()
        self._prev = None
        self._cache_red = (None, None)

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
            pesos, normas = m[0][None], [m[2]]
            self.etiquetas = [f"G{m[1].get('generacion', '?')}"]
            nivel = int(m[1].get("nivel", 1))
        else:
            idx = elegir_generaciones(salon, len(COLORES_GEN))
            pesos = salon["pesos"][idx]
            normas = [B.Normalizador.desde(salon["normalizador"][i]) for i in idx]
            self.etiquetas = [f"G{int(salon['generacion'][i])}" for i in idx]
            nivel = int(np.max(salon["nivel"]))
        self.turbo = False
        niv = Nivel(nivel, int(time.time()) % 100000)
        self.carrera_gen = Partida(niv, pesos, normalizador=B.NormalizadorPorIndividuo(normas))
        self.resultado = None
        self.seguir = None
        self.particulas.clear()
        self.flotantes.clear()
        self._prev = None
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
                        break
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
                    self._auto = None
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
                    self.registro.clear()
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
            if self.turbo:
                self.sonido.fondo(False)

    def cambiar_seguido(self):
        c = self.carrera()
        vivos = [int(i) for i in np.argsort(-c.aptitud()) if c.vivo[i]] or list(range(c.n))
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
        self._prev = (id(c), c.pos_pac(), c.pos_fant())

    def _paso_visible(self, c):
        c.paso()
        j = self.seguido(c)
        for tipo, i, dato in c.eventos:
            if i != j:
                continue
            self._evento(c, tipo, i, dato)

    def _avanzar(self, dt):
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
                    self._paso_visible(c)
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
            return
        self.acum += dt * VELOCIDADES[self.i_vel] / C.DT
        pasos = min(int(self.acum), 80)
        self.acum -= pasos
        for k in range(pasos):
            c = self.e.partida
            if k == pasos - 1:
                self._foto(c)
            if c.terminado:
                r = self.e.avanzar(0)
            else:
                self._paso_visible(c)
                r = self.e.avanzar(0) if c.terminado else None
            if r is not None:
                self._fin_generacion(r)
                self._prev = None
                break

    def _interpolado(self, c):
        pp, pf = c.pos_pac(), c.pos_fant()
        p = self._prev
        if p is None or p[0] != id(c) or p[1].shape != pp.shape or self.pausa:
            return pp, pf
        a = float(min(max(self.acum, 0.0), 1.0))
        out = []
        for viejo, nuevo in ((p[1], pp), (p[2], pf)):
            salto = (np.abs(nuevo - viejo) > 1.5).any(-1, keepdims=True)
            out.append(np.where(salto, nuevo, viejo + (nuevo - viejo) * a))
        return out[0], out[1]

    def _fin_generacion(self, r):
        print(resumen_generacion(r), flush=True)
        self.ultimo_resumen = r
        self.registro.append(r)
        del self.registro[:-14]
        self.record = max(self.record, int(r["puntos_lider"]))
        self._anunciar_generacion()
        if r.get("subio"):
            self.banner = ("SUBE DE NIVEL!", C.NIVELES[r["nivel_nuevo"] - 1][0], 3.0)
            self.sonido.tocar("sube")
        elif not self.turbo:
            self.sonido.tocar("gen")

    def _fin_carrera_gen(self):
        c = self.carrera_gen
        llego = c.motivo == META
        orden = sorted(range(c.n), key=lambda i: (0 if llego[i] else 1,
                                                  float(c.t_fin[i]) if llego[i] else -float(c.marcador[i])))
        self.resultado = []
        for pos, i in enumerate(orden, 1):
            if llego[i]:
                dato = f"LIMPIO {c.t_fin[i]:.0f}S {int(c.marcador[i])}"
            else:
                dato = f"{MOTIVOS[c.motivo[i]]} {c.progreso()[i]:.0f}% {int(c.marcador[i])}"
            self.resultado.append((pos, i, dato))
        self.sonido.tocar("meta")

    def _evento(self, c, tipo, i, dato):
        x, y = _a_px(*c.pos_pac()[i])
        if tipo == "punto":
            self.sonido.tocar("punto")
        elif tipo == "energ":
            self.sonido.tocar("energ")
            for k in range(16):
                a = 2 * math.pi * k / 16
                self.particulas.append([x, y, math.cos(a) * 60, math.sin(a) * 60, 0.45, (255, 220, 160)])
        elif tipo == "fantasma":
            g, pts = dato
            gx, gy = _a_px(*c.pos_fant()[i, g])
            self.flotantes.append([gx, gy, str(pts), 1.1, (60, 230, 255)])
            self.sonido.tocar("fantasma")
        elif tipo == "fruta":
            self.flotantes.append([x, y, str(dato), 1.4, (255, 150, 220)])
            self.sonido.tocar("fruta")
        elif tipo == "muerte":
            self.sonido.tocar("muerte")
        elif tipo == "meta":
            self.sonido.tocar("meta")
            self.banner = ("LABERINTO LIMPIO!", f"{int(c.marcador[i])} PUNTOS", 2.0)

    def _efectos(self, dt):
        nombre, sub, tb = self.banner
        self.banner = (nombre, sub, max(0.0, tb - dt))
        self.confirmar_reinicio = max(0.0, self.confirmar_reinicio - dt)
        self.aviso = (self.aviso[0], max(0.0, self.aviso[1] - dt))
        vivas = []
        for p in self.particulas:
            p[0] += p[2] * dt
            p[1] += p[3] * dt
            p[4] -= dt
            if p[4] > 0:
                vivas.append(p)
        self.particulas = vivas[-300:]
        for f in self.flotantes:
            f[1] -= 8 * dt
            f[3] -= dt
        self.flotantes = [f for f in self.flotantes if f[3] > 0]
        c = self.carrera()
        if not (self.turbo and self.carrera_gen is None) and not self.pausa:
            j = self.seguido(c)
            self.sonido.fondo(c.vivo[j] and c.t_susto[j] > 0)
        else:
            self.sonido.fondo(False)

    def _blit_centro(self, spr, x, y):
        w, h = spr.get_size()
        self.vista.blit(spr, (round(x - w / 2), round(y - h / 2)))
        if x < w:
            self.vista.blit(spr, (round(x + VW - w / 2), round(y - h / 2)))
        elif x > VW - w:
            self.vista.blit(spr, (round(x - VW - w / 2), round(y - h / 2)))

    def _dibujar_vista(self, c, t):
        v = self.vista
        lab = c.lab
        v.fill((0, 0, 0))
        v.blit(self.brillo(lab), (0, HUD_ARR), special_flags=pygame.BLEND_ADD)
        v.blit(self.paredes(lab), (0, HUD_ARR), special_flags=pygame.BLEND_MAX)
        j = self.seguido(c)
        _, _, col_punto, _ = TEMAS[lab.tema]
        rc = lab.rc
        for k in np.flatnonzero(c.puntos[j]):
            x, y = _a_px(*rc[k])
            pygame.draw.rect(v, col_punto, (int(x) - 1, int(y) - 1, 2, 2))
        if int(t * 4) % 2 == 0 or c.espera[j] > 0:
            for k in np.flatnonzero(c.energ[j]):
                x, y = _a_px(*rc[k])
                pygame.draw.circle(v, _mezcla((0, 0, 0), col_punto, 0.22), (int(x), int(y)), 7)
                pygame.draw.circle(v, _mezcla((0, 0, 0), col_punto, 0.45), (int(x), int(y)), 5)
                pygame.draw.circle(v, col_punto, (int(x), int(y)), 4)
        if c.fruta_t[j] > 0:
            x, y = _a_px(*rc[lab.t_fruta])
            self._blit_centro(self.fruta_de(c.niv.nivel), x, y)
        pp, pf = self._interpolado(c)
        en_gen = self.carrera_gen is not None
        for i in range(c.n):
            if i == j or not c.vivo[i]:
                continue
            x, y = _a_px(*pp[i])
            if en_gen:
                spr = self.spr_pac_gen[i % len(COLORES_GEN)][int(c.pac_d[i])][1].copy()
                spr.set_alpha(110)
                self._blit_centro(spr, x, y)
            else:
                self._blit_centro(self.spr_sombra, x, y)
        muriendo = c.espera[j] > 0 and c.pendiente[j]
        if self.ver_sensores and not muriendo and c.vivo[j]:
            self._objetivos(c, j)
        if not muriendo or c.espera[j] > C.MUERTE_ESPERA - 0.5:
            cuadro = int(t * 8) % 2
            for g in range(4):
                if not c.activo[g]:
                    continue
                e = int(c.fant_e[j, g])
                x, y = _a_px(*pf[j, g])
                if e == CASA:
                    y += math.sin(t * 7 + g * 1.7) * 2.5
                d = int(c.fant_d[j, g])
                if e == OJOS:
                    spr = self.spr_ojos[d]
                elif c.asustado[j, g]:
                    blanco = c.t_susto[j] < C.PARPADEO and int(t * 5) % 2 == 0
                    spr = self.spr_susto[blanco][cuadro]
                else:
                    spr = self.spr_fant[g][d][cuadro]
                self._blit_centro(spr, x, y)
        if self.ver_sensores and c.vivo[j] and not muriendo:
            self._dibujar_sensores(c, j, pp[j])
        x, y = _a_px(*pp[j])
        if muriendo:
            avance = 1.0 - c.espera[j] / C.MUERTE_ESPERA
            k = int(np.clip((avance - 0.3) / 0.6, 0, 0.999) * len(self.spr_muerte))
            if avance < 0.9:
                self._blit_centro(self.spr_muerte[k], x, y)
        elif c.vivo[j] or c.motivo[j] == META:
            hojas = self.spr_pac_gen[j % len(COLORES_GEN)] if en_gen else self.spr_pac
            quieto = c.parado[j] or not c.vivo[j]
            k = 0 if quieto else int(c.t * 18) % 4
            self._blit_centro(hojas[int(c.pac_d[j])][k], x, y)
        for p in self.particulas:
            a = max(0.0, min(1.0, p[4] / 0.45))
            pygame.draw.rect(v, _mezcla((0, 0, 0), p[5], a), (int(p[0]), int(p[1]), 2, 2))
        for f in self.flotantes:
            img = self.fp.texto(f[2], f[4])
            v.blit(img, (int(f[0] - img.get_width() / 2), int(f[1] - 4)))
        self._hud(c, j)

    def _objetivos(self, c, j):
        g_activos = [g for g in range(4) if c.activo[g] and c.fant_e[j, g] == FUERA and not c.asustado[j, g]]
        if not g_activos:
            return
        idx = np.full(len(g_activos), j)
        obj = c._objetivos(idx, np.array(g_activos))
        for g, (r, col) in zip(g_activos, obj):
            x, y = _a_px(r, col)
            x = min(max(x, 3), VW - 4)
            y = min(max(y, HUD_ARR + 3), VH - HUD_ABA - 4)
            color = SP.COLORES_FANTASMA[g]
            pygame.draw.line(self.vista, color, (x - 3, y), (x + 3, y))
            pygame.draw.line(self.vista, color, (x, y - 3), (x, y + 3))
            pygame.draw.rect(self.vista, color, (int(x) - 5, int(y) - 5, 11, 11), 1)

    def _dibujar_sensores(self, c, j, pos):
        x, y = _a_px(*pos)
        f = c.obs[j, :4 * C.SENSORES_DIR].reshape(4, C.SENSORES_DIR)
        deseo = int(c.deseo[j])
        for d in range(4):
            if f[d, 0] < 0.5:
                continue
            margen = float(f[d, 4])
            col = _mezcla((255, 60, 60), (80, 255, 140), (margen + 1) / 2)
            largo = 8 + 16 * (1 - min(f[d, 1], 1.0))
            dy, dx = DIRS[d]
            x1, y1 = x + dx * largo, y + dy * largo
            pygame.draw.line(self.vista, col, (x + dx * 8, y + dy * 8), (x1, y1), 2 if d == deseo else 1)
            if d == deseo:
                pygame.draw.circle(self.vista, col, (int(x1), int(y1)), 2)

    def _hud(self, c, j):
        v = self.vista
        fp = self.fp
        pygame.draw.rect(v, (0, 0, 0), (0, 0, VW, HUD_ARR))
        v.blit(fp.texto("1UP", (255, 255, 255)), (6, 1))
        v.blit(fp.texto(f"{int(c.marcador[j]):6d}", (255, 255, 255)), (6, 9))
        self.record = max(self.record, int(c.marcador.max()))
        t1 = fp.texto("RECORD", (255, 255, 255))
        v.blit(t1, ((VW - t1.get_width()) // 2, 1))
        t2 = fp.texto(f"{self.record:6d}", (255, 255, 255))
        v.blit(t2, ((VW - t2.get_width()) // 2, 9))
        t3 = fp.texto(f"NIVEL {c.niv.nivel}", ORO)
        v.blit(t3, (VW - t3.get_width() - 6, 1))
        t4 = fp.texto(f"{c.progreso()[j]:3.0f}%", (180, 200, 255))
        v.blit(t4, (VW - t4.get_width() - 6, 9))
        y0 = VH - HUD_ABA + 2
        pygame.draw.rect(v, (0, 0, 0), (0, VH - HUD_ABA, VW, HUD_ABA))
        for k in range(max(0, int(c.vidas[j]) - (0 if c.espera[j] > 0 and c.pendiente[j] else 1))):
            v.blit(self.spr_vida, (8 + k * 12, y0 + 1))
        for k in range(min(c.niv.nivel, 7)):
            spr = self.spr_frutas[min(c.niv.nivel - k, len(self.spr_frutas)) - 1]
            v.blit(spr, (VW - 18 - k * 14, y0 - 1))
        b = self.banner
        if b[2] > 0 and b[0]:
            alfa = min(1.0, b[2] / 0.5)
            caja = pygame.Surface((VW, 44), pygame.SRCALPHA)
            caja.fill((0, 0, 0, int(190 * alfa)))
            yb = HUD_ARR + 17 * TS - 8
            v.blit(caja, (0, yb))
            t1 = fp.texto(b[0], ORO, 2)
            v.blit(t1, ((VW - t1.get_width()) / 2, yb + 6))
            t2 = fp.texto(b[1], (255, 255, 255))
            v.blit(t2, ((VW - t2.get_width()) / 2, yb + 28))
        if self.aviso[1] > 0 and not (b[2] > 0 and b[0]):
            t = fp.texto(self.aviso[0], (150, 200, 255))
            caja = pygame.Surface((t.get_width() + 8, 11), pygame.SRCALPHA)
            caja.fill((0, 0, 0, 200))
            v.blit(caja, ((VW - t.get_width()) / 2 - 4, HUD_ARR + 2))
            v.blit(t, ((VW - t.get_width()) / 2, HUD_ARR + 3))
        if self.pausa:
            t = fp.texto("PAUSA", (255, 255, 255), 3)
            v.blit(t, ((VW - t.get_width()) / 2, VH / 2 - 10))
        if self.resultado and self.carrera_gen is not None and c.terminado:
            alto = 22 + 11 * len(self.resultado)
            caja = pygame.Surface((VW - 20, alto), pygame.SRCALPHA)
            caja.fill((0, 0, 0, 225))
            v.blit(caja, (10, 60))
            t = fp.texto("RESULTADOS", ORO)
            v.blit(t, ((VW - t.get_width()) / 2, 64))
            for k, (pos, i, dato) in enumerate(self.resultado):
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
        titulo = self.fp.texto("PAC-MAN", ORO, 3)
        b.blit(titulo, (x0, 8))
        self._txt("EVOLUTIVO · neuroevolución", (x0 + titulo.get_width() + 12, 6), self.f_titulo, TEXTO)
        alg = "estrategias evolutivas (Adam, especular)" if self.e.algoritmo == "es" else "algoritmo genético"
        self._txt(f"Cerebro recurrente {B.N_IN} > {B.N_H1} (memoria) > {B.N_H2} > {B.N_OUT} + cabeza "
                  f"compartida por dirección  ·  {alg}",
                  (x0 + titulo.get_width() + 12, 30), self.f_peq, TENUE)
        self._txt(f"{fps:4.0f} fps · x{VELOCIDADES[self.i_vel]}{' · MODO RÁPIDO' if self.turbo else ''}",
                  (BASE_W - 16, 10), self.f_mono, TENUE, "tr")
        ancho_a = 340
        xa, xb = x0, x0 + ancho_a + 12
        ancho_b = BASE_W - 16 - xb
        y = 56
        self._tarjeta(xa, y, ancho_a, 168, "carrera de generaciones" if en_gen else "generación")
        if en_gen:
            self._txt(c.niv.nombre.upper(), (xa + 12, y + 28), self.f_med, ORO)
            for k, et in enumerate(self.etiquetas):
                col = COLORES_GEN[k % len(COLORES_GEN)]
                estado = "LIMPIO" if c.motivo[k] == META else ("en juego" if c.vivo[k] else MOTIVOS[c.motivo[k]].lower())
                self._txt(f"{et}", (xa + 14 + (k % 2) * 165, y + 58 + (k // 2) * 22), self.f_med, col)
                self._txt(f"{c.progreso()[k]:3.0f} % · {estado}", (xa + 64 + (k % 2) * 165, y + 60 + (k // 2) * 22),
                          self.f_peq, TEXTO)
        else:
            self._txt(f"{self.e.generacion}", (xa + 12, y + 24), self.f_num, ORO)
            p = self.e.niv
            self._txt(f"{p.nombre}", (xa + 110, y + 24), self.f_med, TEXTO)
            for k in range(C.NIVEL_MAX):
                col = ORO if k < p.nivel else BORDE
                pygame.draw.circle(b, col, (xa + 116 + k * 14, y + 52), 5)
            self._txt(f"racha {self.e.racha}/{C.RACHA_PARA_SUBIR}", (xa + 236, y + 46), self.f_peq, TENUE)
            vivos = int(c.vivo.sum())
            self._txt(f"jugando {vivos}/{c.n}", (xa + 12, y + 68), self.f, TEXTO)
            pygame.draw.rect(b, (30, 38, 54), (xa + 130, y + 72, ancho_a - 144, 8), border_radius=4)
            pygame.draw.rect(b, AZUL, (xa + 130, y + 72, int((ancho_a - 144) * vivos / c.n), 8), border_radius=4)
            h = self.e.historial[-1] if self.e.historial else None
            filas = [("mejor recompensa (gen. anterior)", f"{h['mejor']:.0f}" if h else "—", ORO),
                     ("promedio", f"{h['promedio']:.0f}" if h else "—", AZUL),
                     ("limpiaron el laberinto", f"{h['llegaron']:.0f} %" if h else "—", VERDE),
                     ("puntos comidos (líder · promedio)",
                      f"{h.get('progreso_lider', 0):.0f} · {h.get('progreso_prom', 0):.0f} %" if h else "—", TEXTO),
                     ("fantasmas comidos (líder · prom.)",
                      f"{h.get('fantasmas_lider', 0)} · {h.get('fantasmas_prom', 0):.1f}" if h else "—", MAGENTA)]
            for k, (et, val, col) in enumerate(filas):
                self._txt(et, (xa + 12, y + 88 + k * 15), self.f_peq, TENUE)
                self._txt(val, (xa + ancho_a - 12, y + 86 + k * 15), self.f_mono, col, "tr")
        y = 232
        self._tarjeta(xa, y, ancho_a, 196, "evolución de la recompensa")
        self._grafica(xa + 8, y + 26, ancho_a - 16, 162)
        y = 436
        self._tarjeta(xa, y, ancho_a, 128, "población (cada cuadro es un comecocos)")
        n = c.n
        cols = 20
        lado = min(14, (ancho_a - 24) // cols - 2)
        filas_pob = max(1, math.ceil(n / cols))
        lado = min(lado, max(4, 72 // filas_pob - 2))
        for i in range(n):
            px = xa + 12 + (i % cols) * (lado + 2)
            py = y + 28 + (i // cols) * (lado + 2)
            col = ESTADO_COLOR.get(int(c.motivo[i]), TENUE)
            if en_gen:
                col = COLORES_GEN[i % len(COLORES_GEN)]
            frac = float(np.clip(c.progreso()[i] / 100, 0, 1))
            pygame.draw.rect(b, (40, 48, 64), (px, py, lado, lado))
            pygame.draw.rect(b, col, (px, py + lado - max(1, int(lado * frac)), lado, max(1, int(lado * frac))))
            if i == j:
                pygame.draw.rect(b, (255, 255, 255), (px - 1, py - 1, lado + 2, lado + 2), 1)
        ley = [("jugando", ESTADO_COLOR[VIVO]), ("limpió", VERDE), ("sin vidas", ROJO),
               ("atascado", ESTADO_COLOR[ATASCADO])]
        for k, (et, col) in enumerate(ley):
            pygame.draw.rect(b, col, (xa + 12 + k * 82, y + 108, 8, 8))
            self._txt(et, (xa + 24 + k * 82, y + 104), self.f_peq, TENUE)
        self.botones = []
        y = 572
        self._tarjeta(xa, y, ancho_a, 132, "controles")
        self._boton(xa + 12, y + 28, 100, "Pausa" if not self.pausa else "Seguir",
                    lambda: setattr(self, "pausa", not self.pausa), self.pausa)
        self._boton(xa + 118, y + 28, 100, "Animar" if self.turbo else "Modo rápido", self.alternar_turbo,
                    self.turbo)
        self._boton(xa + 224, y + 28, 32, "−", lambda: setattr(self, "i_vel", max(0, self.i_vel - 1)))
        self._txt(f"x{VELOCIDADES[self.i_vel]}", (xa + 280, y + 42), self.f_mono, TEXTO, "c")
        self._boton(xa + 300, y + 28, 32, "+",
                    lambda: setattr(self, "i_vel", min(len(VELOCIDADES) - 1, self.i_vel + 1)))
        self._boton(xa + 12, y + 62, 176, "Volver al entrenamiento" if en_gen else "Carrera de generaciones",
                    self.carrera_generaciones, en_gen)
        self._boton(xa + 194, y + 62, 66, "Guardar", self.guardar)
        self._boton(xa + 266, y + 62, 66, "Reiniciar", self.pedir_reinicio)
        self._boton(xa + 12, y + 96, 104, "Sensores", lambda: setattr(self, "ver_sensores", not self.ver_sensores),
                    self.ver_sensores)
        self._boton(xa + 122, y + 96, 104, "Red neuronal", lambda: setattr(self, "ver_red", not self.ver_red),
                    self.ver_red)
        texto_son = "Sonido" if self.sonido.activo else "Sin audio"
        self._boton(xa + 232, y + 96, 100, texto_son, self.sonido.alternar,
                    not self.sonido.mudo and self.sonido.activo)
        self._txt("ESPACIO pausa · T modo rápido / animar · +/− velocidad · G generaciones · "
                  "TAB/L comecocos seguido · S sensores · N red · M sonido · F5 guardar · F11", (xa, y + 140), self.f_peq, TENUE)
        if not self.sonido.activo:
            self._txt(f"Sin audio: {self.sonido.error or 'no hay dispositivo de sonido'}",
                      (xa, BASE_H - 40), self.f_peq, NARANJA)
        if self.confirmar_reinicio > 0:
            self._txt("¿Borrar lo aprendido? Pulsa Y para confirmar", (xa, BASE_H - 22), self.f_med, ROJO)
        y = 56
        alto_red = 452
        self._tarjeta(xb, y, ancho_b, alto_red, "red neuronal del comecocos seguido (en vivo)")
        if self.ver_red:
            self._red(c, j, xb + 8, y + 24, ancho_b - 16, alto_red - 44)
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
                self._txt(f"N{hist[i + 1]['nivel']}", (xx + 2, y1), self.f_peq, TENUE)
        linea = [pt(i, v) for i, v in enumerate(mejor)]
        capa = pygame.Surface((w, h), pygame.SRCALPHA)
        pygame.draw.polygon(capa, (*ORO, 34), [(x0 - x, y0 - y)] + [(px - x, py - y) for px, py in linea]
                            + [(x1 - x, y0 - y)])
        b.blit(capa, (x, y))
        pygame.draw.lines(b, AZUL, False, [pt(i, v) for i, v in enumerate(prom)], 1)
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
        if c.red is None:
            return
        n_in, n1, n2, n3 = B.N_IN, B.N_H1, B.N_H2, B.N_OUT
        cols = (x + 66, x + w * 0.46, x + w * 0.68, x + w - 78)

        def ys(n, margen=6):
            return [y + margen + (h - 2 * margen) * (k + 0.5) / n for k in range(n)]

        pos = [list(zip([cols[0]] * n_in, ys(n_in))), list(zip([cols[1]] * n1, ys(n1, 20))),
               list(zip([cols[2]] * n2, ys(n2, 60))), list(zip([cols[3]] * n3, ys(n3, 130)))]
        clave = (id(c), j, c.pesos[j].tobytes()[:64])
        if self._cache_red[0] != clave:
            capa = pygame.Surface((int(w) + 2, int(h) + 2), pygame.SRCALPHA)
            red = {k: v[j] for k, v in c.red.items()}
            for (Wm, a, bb, top) in ((red["Wx"], 0, 1, 260), (red["W2"], 1, 2, 300), (red["W3"], 2, 3, 64)):
                pesos = np.abs(Wm).ravel()
                umbral = np.sort(pesos)[-min(top, len(pesos))]
                wmax = pesos.max() + 1e-9
                for p_i, p_o in zip(*np.nonzero(np.abs(Wm) >= umbral)):
                    val = Wm[p_i, p_o]
                    alfa = int(30 + 170 * abs(val) / wmax)
                    col = (61, 220, 132, alfa) if val > 0 else (232, 92, 200, alfa)
                    (ax_, ay_), (bx_, by_) = pos[a][p_i], pos[bb][p_o]
                    pygame.draw.aaline(capa, col, (ax_ - x, ay_ - y), (bx_ - x, by_ - y))
            self._cache_red = (clave, capa)
        b.blit(self._cache_red[1], (x, y))
        norm = c.norm
        o = c.obs[j:j + 1]
        if isinstance(norm, B.NormalizadorPorIndividuo):
            xin = np.clip((o - norm.media[j]) / norm.desv_[j], -5, 5)[0]
        else:
            xin = norm.aplicar(o)[0]
        act = [np.tanh(xin / 2), c.h[j], c.h2[j], c.ctrl[j]]
        for capa_i, (puntos, valores) in enumerate(zip(pos, act)):
            for (px, py), val in zip(puntos, valores):
                col = _mezcla((60, 140, 255), (255, 160, 60), (val + 1) / 2)
                r = 3 if capa_i == 0 else 6 if capa_i < 3 else 9
                pygame.draw.circle(b, col, (int(px), int(py)), r)
                pygame.draw.circle(b, (12, 14, 20), (int(px), int(py)), r, 1)
        for k, ((px, py), nombre) in enumerate(zip(pos[0], NOMBRES_ENTRADAS)):
            col = TENUE if (k // C.SENSORES_DIR) % 2 == 0 or k >= 4 * C.SENSORES_DIR else (150, 160, 190)
            self._txt(nombre, (px - 6, py), self.f_peq, col, "mr")
        for (px, py) in pos[1]:
            pygame.draw.arc(b, (120, 140, 170), (px + 3, py - 6, 10, 12), -1.6, 1.6, 1)
        elegido = int(np.argmax(c.ctrl[j]))
        for k, ((px, py), nombre, val) in enumerate(zip(pos[3], NOMBRES_DIR, c.ctrl[j])):
            self._txt(nombre, (px + 14, py - 8), self.f_peq, ORO if k == elegido else TEXTO)
            self._txt(f"{val:+.2f}", (px + 14, py + 4), self.f_mono, ORO if k == elegido else TENUE)
        self._txt("sensores", (cols[0], y + h + 2), self.f_peq, TENUE, "c")
        self._txt("memoria (recurrente)", (cols[1], y + h + 2), self.f_peq, TENUE, "c")
        self._txt("densa", (cols[2], y + h + 2), self.f_peq, TENUE, "c")

    def _telemetria(self, c, j, x, y, w):
        b = self.base
        self._txt(f"{int(c.marcador[j])}", (x + 14, y + 24), self.f_num, ORO)
        self._txt("puntos", (x + 14, y + 54), self.f_peq, TENUE)
        for k in range(int(c.vidas[j])):
            b.blit(pygame.transform.scale(self.spr_vida, (14, 14)), (x + 120 + k * 17, y + 32))
        estado = MOTIVOS[int(c.motivo[j])]
        if c.vivo[j] and c.espera[j] > 0 and c.pendiente[j]:
            estado = "ATRAPADO"
        self._txt(estado, (x + w - 12, y + 30), self.f_mono, ESTADO_COLOR.get(int(c.motivo[j]), TEXTO), "tr")
        frac = float(np.clip(c.progreso()[j] / 100, 0, 1))
        self._txt(f"puntos comidos {c.lab.n_puntos - int(c.restantes[j])}/{c.lab.n_puntos}",
                  (x + 14, y + 70), self.f_peq, TENUE)
        pygame.draw.rect(b, (30, 38, 54), (x + 150, y + 74, w - 164, 8), border_radius=4)
        pygame.draw.rect(b, ORO, (x + 150, y + 74, int((w - 164) * frac), 8), border_radius=4)
        if c.t_susto[j] > 0:
            fs = float(c.t_susto[j] / max(c.niv.t_susto, 1e-3))
            self._txt(f"susto {c.t_susto[j]:.1f} s", (x + 14, y + 88), self.f_peq, AZUL)
            pygame.draw.rect(b, (30, 38, 54), (x + 150, y + 92, w - 164, 8), border_radius=4)
            pygame.draw.rect(b, (60, 80, 255), (x + 150, y + 92, int((w - 164) * fs), 8), border_radius=4)
        else:
            modo = "PERSECUCIÓN" if c.persecucion()[j] else "DISPERSIÓN"
            self._txt(f"modo de los fantasmas: {modo}", (x + 14, y + 88), self.f_peq,
                      ROJO if c.persecucion()[j] else TENUE)
        for g in range(4):
            gx = x + 14 + g * ((w - 28) // 4)
            gy = y + 110
            if not c.activo[g]:
                self._txt("—", (gx + 7, gy + 7), self.f_peq, BORDE, "c")
                continue
            e = int(c.fant_e[j, g])
            spr = (self.spr_ojos[1] if e == OJOS else self.spr_susto[0][0] if c.asustado[j, g]
                   else self.spr_fant[g][1][0])
            b.blit(pygame.transform.scale(spr, (28, 28)), (gx, gy))
            self._txt(C.NOMBRES_FANTASMAS[g], (gx + 32, gy), self.f_peq, SP.COLORES_FANTASMA[g])
            self._txt("asustado" if c.asustado[j, g] else ESTADO_FANT[e], (gx + 32, gy + 13), self.f_peq, TENUE)
        datos = [("fantasmas", f"{int(c.fant_comidos[j])}"), ("frutas", f"{int(c.frutas[j])}"),
                 ("muertes", f"{int(c.muertes[j])}"), ("recompensa", f"{c.aptitud()[j]:.0f}")]
        for k, (et, val) in enumerate(datos):
            xx = x + 14 + k * ((w - 28) // 4)
            self._txt(et, (xx, y + 148), self.f_peq, TENUE)
            self._txt(val, (xx, y + 162), self.f_mono, TEXTO)
        seg = f"#{j} (auto)" if self.seguir is None else f"#{j} (elegido)"
        if self.carrera_gen is not None:
            seg += f" ({self.etiquetas[j]})"
        self._txt(f"siguiendo: {seg}", (x + w - 12, y + 8), self.f_peq, AZUL, "tr")

    def _dibujar(self, dt):
        c = self.carrera()
        t = time.perf_counter()
        self.base.fill(FONDO)
        rapido = self.turbo and self.carrera_gen is None
        if not rapido:
            self._dibujar_vista(c, t)
            grande = pygame.transform.scale(self.vista, (VW * EV, VH * EV))
            self.base.blit(grande, (VISTA_X, VISTA_Y))
            self._txt("vista del comecocos seguido · los círculos tenues son los demás (cada uno en su laberinto)"
                      if self.carrera_gen is None
                      else "cada campeona juega en su propio laberinto (con sus propios fantasmas)",
                      (VISTA_X, VISTA_Y - 22), self.f_peq, TENUE)
        pygame.draw.rect(self.base, BORDE, (VISTA_X - 1, VISTA_Y - 1, VW * EV + 2, VH * EV + 2), 1)
        self._paneles(c, self.reloj.get_fps())
        if rapido:
            self._pantalla_rapida(c)
        self._grabacion()
        w, h = self.ventana.get_size()
        if (w, h) == (BASE_W, BASE_H):
            self.ventana.blit(self.base, (0, 0))
        else:
            self.ventana.blit(pygame.transform.smoothscale(self.base, (w, h)), (0, 0))
        pygame.display.flip()

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
        self._txt("Sólo juego y aprendizaje: el laberinto no se dibuja.", (x0 + w / 2, y0 + 82),
                  self.f, TEXTO, "c")
        r = pygame.Rect(x0 + w / 2 - 110, y0 + 104, 220, 40)
        mx, my = self._a_base(pygame.mouse.get_pos())
        pygame.draw.rect(b, (60, 90, 140) if r.collidepoint(mx, my) else (38, 60, 98), r, border_radius=8)
        pygame.draw.rect(b, AZUL, r, 1, border_radius=8)
        self._txt("Animar  (T)", r.center, self.f_titulo, TEXTO, "c")
        self.botones.append((r, self.alternar_turbo))
        y = y0 + 168
        p = c.niv
        avance = float(c.progreso().max()) / 100
        self._txt(f"Generación {self.e.generacion}  ·  {p.nombre} (nivel {p.nivel}/{C.NIVEL_MAX})",
                  (x0 + 24, y), self.f_med, ORO)
        pygame.draw.rect(b, (30, 38, 54), (x0 + 24, y + 28, w - 48, 14), border_radius=6)
        pygame.draw.rect(b, ORO, (x0 + 24, y + 28, int((w - 48) * avance), 14), border_radius=6)
        self._txt(f"la mejor lleva {100 * avance:.0f} % de los puntos  ·  {int(c.vivo.sum())}/{c.n} jugando  ·  "
                  f"t = {c.t:.0f} s", (x0 + 24, y + 48), self.f, TEXTO)
        seg = max(time.perf_counter() - self.rapido_t0, 1e-6)
        ritmo = self.rapido_gens / seg * 60
        self._txt(f"en modo rápido: {self.rapido_gens} generaciones en {seg / 60:.1f} min"
                  f"  ·  {ritmo:.1f} gen/min", (x0 + 24, y + 70), self.f, AZUL)
        y += 110
        self._txt("ÚLTIMAS GENERACIONES", (x0 + 24, y), self.f_peq, TENUE)
        cols = (("gen", 24), ("laberinto", 70), ("mejor", 200), ("limpiaron", 262), ("puntos líder", 340),
                ("fantasmas", 440))
        for nombre, dx in cols:
            self._txt(nombre, (x0 + dx, y + 18), self.f_peq, TENUE)
        for k, r_ in enumerate(reversed(self.registro[-12:])):
            yy = y + 38 + k * 22
            col = VERDE if r_.get("lider_llego") else TEXTO
            vals = (str(r_["generacion"]), r_["laberinto"][:16], f"{r_['mejor']:.0f}", f"{r_['llegaron']:.0f} %",
                    f"{r_['progreso_lider']:.0f} %", f"{r_['fantasmas_lider']}")
            for (nombre, dx), val in zip(cols, vals):
                self._txt(val, (x0 + dx, yy), self.f_mono, col)
            if r_.get("subio"):
                self._txt("sube", (x0 + 500, yy), self.f_peq, ORO)
        if not self.registro:
            self._txt("(aparecen aquí al terminar cada generación)", (x0 + w / 2, y + 60), self.f_peq, TENUE, "c")


def ejecutar(entrenador=None, demo=False, generaciones=False, rapido=False):
    j = Juego(entrenador, demo=demo, generaciones=generaciones)
    if rapido:
        j.alternar_turbo()
    j.correr()
