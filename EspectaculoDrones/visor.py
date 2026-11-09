import argparse
import ctypes
import math
import os
import sys
import time

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import moderngl
import numpy as np
import pygame
from scipy.spatial import cKDTree

import config as C
import planificador as PL
from grabador import Grabador, CARPETA_GRABACIONES
from hud import Hud
from render import Render

MODOS = ["publico", "orbita", "cine", "libre", "dron"]
NOMBRES = {"publico": "Vista del público", "orbita": "Órbita", "cine": "Cinemática automática",
           "libre": "Libre (mouse)", "dron": "Desde un dron"}


def _suave(a, b, dt, tau):
    return a + (b - a) * (1 - math.exp(-dt / max(tau, 1e-6)))


class Camara:
    def __init__(self, modo="cine"):
        self.modo = modo
        self.ojo = np.array([0.0, C.PUBLICO_Y, 2.0])
        self.obj = np.array([0.0, 0.0, 30.0])
        self.fov = math.radians(50)
        self.yaw, self.pitch, self.dist = -math.pi / 2, 0.25, 160.0
        self.libre_obj = np.array([0.0, 0.0, 40.0])
        self.ang = 0.0
        self.toma = 0
        self.t_toma = 0.0
        self.dron = 0
        self.primera = True

    def nombre(self):
        n = NOMBRES[self.modo]
        if self.modo == "dron":
            n += f" #{self.dron + 1}"
        return n

    def siguiente(self):
        self.modo = MODOS[(MODOS.index(self.modo) + 1) % len(MODOS)]

    def a_libre(self):
        if self.modo == "libre":
            return
        d = self.ojo - self.obj
        self.dist = float(np.linalg.norm(d))
        self.yaw = math.atan2(d[1], d[0])
        self.pitch = math.asin(max(-0.99, min(0.99, d[2] / max(self.dist, 1e-6))))
        self.libre_obj = self.obj.copy()
        self.modo = "libre"

    def actualizar(self, dt, foco, radio, pos, plan, t, fase):
        R = max(radio, 12.0)
        objetivo = foco.copy()
        fov = math.radians(50)
        if self.modo == "publico":
            d = max(abs(C.PUBLICO_Y), R * 3.2)
            ojo = np.array([22 * math.sin(t * 0.03), -d, 1.7])
            fov = float(np.clip(2 * math.atan(R * 1.35 / d), math.radians(24), math.radians(62)))
            objetivo = foco + [0, 0, 0]
        elif self.modo == "orbita":
            self.ang += dt * 0.07
            r = max(70.0, R * 2.9)
            ojo = foco + [r * math.cos(self.ang - math.pi / 2), r * math.sin(self.ang - math.pi / 2), 0]
            ojo[2] = max(4.0, foco[2] * 0.55)
        elif self.modo == "cine":
            self.t_toma += dt
            if self.t_toma > 13.0:
                self.t_toma = 0.0
                self.toma = (self.toma + 1) % 6
            u = self.t_toma / 13.0
            if fase in ("tierra", "armado", "despegue", "aterrizaje", "fin"):
                tomas = [(np.array([-38 + 20 * u, -48, 2.2]), 46), (np.array([30 * math.cos(u), -30, 14 - 6 * u]), 55),
                         (np.array([-25, -60, 35]), 50)]
                o, fv = tomas[self.toma % 3]
                ojo, fov = o, math.radians(fv)
            else:
                k = self.toma
                if k == 0:
                    d = max(abs(C.PUBLICO_Y), R * 3.0)
                    ojo = np.array([-30 + 60 * u, -d, 1.8])
                elif k == 1:
                    a = -math.pi / 2 + (u - 0.5) * 1.6
                    r = R * 2.1 + 25
                    ojo = foco + [r * math.cos(a), r * math.sin(a), -foco[2] * 0.75]
                elif k == 2:
                    ojo = foco + [R * 1.1 * (1 - 2 * u), -R * 1.6, R * 0.9]
                elif k == 3:
                    ojo = np.array([R * 0.4, -R * 0.6, 1.5])
                    fov = math.radians(70)
                elif k == 4:
                    a = math.pi * 0.25 + u * 0.9
                    r = R * 2.4 + 20
                    ojo = foco + [r * math.cos(a), r * math.sin(a) - r * 0.9, R * 0.3]
                else:
                    d = R * 1.5 + 18
                    ojo = foco + [0, -d * (1.1 - 0.35 * u), -foco[2] * 0.4]
            ojo[2] = max(ojo[2], 1.2)
        elif self.modo == "libre":
            cp = math.cos(self.pitch)
            ojo = self.libre_obj + self.dist * np.array([cp * math.cos(self.yaw), cp * math.sin(self.yaw), math.sin(self.pitch)])
            ojo[2] = max(ojo[2], 0.8)
            self.ojo, self.obj, self.fov = ojo, self.libre_obj.copy(), math.radians(50)
            return self.ojo, self.obj, self.fov
        else:
            self.dron %= plan.n
            p = pos[self.dron]
            ojo = p + [0, -1.2, 0.35]
            objetivo = foco if np.linalg.norm(foco - p) > 3 else p + [0, 30, 0]
            fov = math.radians(75)
            self.ojo, self.obj, self.fov = ojo, objetivo, fov
            return self.ojo, self.obj, self.fov
        if self.primera:
            self.ojo, self.obj, self.fov = ojo, objetivo, fov
            self.primera = False
        tau = 1.6
        self.ojo = _suave(self.ojo, ojo, dt, tau)
        self.obj = _suave(self.obj, objetivo, dt, 0.8)
        self.fov = _suave(self.fov, fov, dt, tau)
        return self.ojo, self.obj, self.fov


class Visor:
    def __init__(self, plan, tam=None, modo="cine"):
        pygame.init()
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass
        info = pygame.display.Info()
        if tam is None:
            tam = (min(1600, info.current_w - 80), min(900, info.current_h - 120))
        self.tam = tam
        pygame.display.set_caption(f"Espectáculo de drones — {plan.show.get('nombre', '')}")
        pygame.display.gl_set_attribute(pygame.GL_CONTEXT_MAJOR_VERSION, 3)
        pygame.display.gl_set_attribute(pygame.GL_CONTEXT_MINOR_VERSION, 3)
        pygame.display.gl_set_attribute(pygame.GL_CONTEXT_PROFILE_MASK, pygame.GL_CONTEXT_PROFILE_CORE)
        pygame.display.set_mode(tam, pygame.OPENGL | pygame.DOUBLEBUF | pygame.RESIZABLE)
        self.ctx = moderngl.create_context()
        self.plan = plan
        self.render = Render(self.ctx, tam, plan)
        self.hud = Hud(tam)
        self.camara = Camara(modo)
        self.grabador = Grabador()
        self.t = 0.0
        self.velocidad = 1.0
        self.pausa = False
        self.hud_visible = True
        self.seg_i = 0
        self.reloj = time.perf_counter()
        self.fase_ruido = np.random.default_rng(5).uniform(0, 2 * math.pi, (plan.n, 3))
        self.yaw = np.random.default_rng(6).uniform(0, 2 * math.pi, plan.n)
        self.foco = np.array([0.0, 0.0, 10.0])
        self.radio = 20.0
        self.telemetria = {"aire": 0, "alt_media": 0, "alt_max": 0, "vel": 0, "sep": 1e9, "viento": 2.0, "bateria": 100}
        self._sep_cuadro = 0
        self._hud_t = 0.0
        self.arrastre = None
        self.buscando = False
        self.fps = 0.0

    def _ruido(self, pos, t):
        en_aire = np.clip((pos[:, 2] - 0.3) / 2.0, 0, 1)
        f = self.fase_ruido
        r = np.column_stack([np.sin(t * 1.3 + f[:, 0]) + 0.5 * np.sin(t * 3.1 + f[:, 1] * 2),
                             np.sin(t * 1.1 + f[:, 1]) + 0.5 * np.sin(t * 2.7 + f[:, 2] * 2),
                             0.6 * np.sin(t * 1.7 + f[:, 2])]) * 0.045
        return pos + r * en_aire[:, None]

    def _ejes(self, t, pos):
        h = 0.12
        a = (self.plan.posiciones(t + h) - 2 * self.plan.posiciones(t) + self.plan.posiciones(max(t - h, 0))) / (h * h)
        empuje = a + [0, 0, 9.81]
        empuje[:, 2] = np.maximum(empuje[:, 2], 2.0)
        z = empuje / np.linalg.norm(empuje, axis=1, keepdims=True)
        en_aire = pos[:, 2] > 0.25
        z[~en_aire] = (0, 0, 1)
        yd = np.column_stack([np.cos(self.yaw), np.sin(self.yaw), np.zeros(self.plan.n)])
        x = yd - (np.sum(yd * z, axis=1, keepdims=True)) * z
        x /= np.linalg.norm(x, axis=1, keepdims=True)
        y = np.cross(z, x)
        return x, y, z

    def _telemetria(self, pos, t, dt):
        p = self.plan
        aire = pos[:, 2] > 0.3
        n_aire = int(aire.sum())
        tel = self.telemetria
        tel["aire"] = n_aire
        tel["alt_media"] = float(pos[aire, 2].mean()) if n_aire else 0.0
        tel["alt_max"] = float(pos[:, 2].max())
        v = np.linalg.norm(p.posiciones(t + 0.05) - p.posiciones(max(t - 0.05, 0)), axis=1) / 0.1
        tel["vel"] = float(v.max())
        self._sep_cuadro += 1
        if self._sep_cuadro % 8 == 0:
            tel["sep"] = float(cKDTree(pos).query(pos, k=2)[0][:, 1].min()) if p.n > 1 else 1e9
        tel["viento"] = 2.2 + 0.8 * math.sin(t * 0.13) + 0.4 * math.sin(t * 0.71)
        frac = min(t / max(p.duracion, 1e-6), 1.0)
        tel["bateria"] = PL.bateria(t, p.stats.get("recorrido_max", 0.0) * frac) if t > C.T_TIERRA + C.T_ARMADO else 100.0

    def _foco(self, pos, b, dt):
        vivos = b > 0.02
        p = pos[vivos] if vivos.any() else pos
        c = (p.min(0) + p.max(0)) / 2
        r = float(np.percentile(np.linalg.norm(p - c, axis=1), 97)) + 4
        self.foco = _suave(self.foco, c, dt, 1.2)
        self.radio = _suave(self.radio, r, dt, 1.2)

    def _buscar(self, mx):
        r = self.hud.linea
        f = (mx - r.x) / max(r.w, 1)
        self.t = float(np.clip(f, 0, 1)) * self.plan.duracion

    def captura(self, ruta=None):
        os.makedirs(CARPETA_GRABACIONES, exist_ok=True)
        if ruta is None:
            ruta = os.path.join(CARPETA_GRABACIONES, time.strftime("captura_%Y-%m-%d_%H-%M-%S.png"))
        w, h = self.render.tam
        datos = self.ctx.screen.read(viewport=(0, 0, w, h), components=3)
        img = pygame.image.frombuffer(datos, (w, h), "RGB")
        pygame.image.save(pygame.transform.flip(img, False, True), ruta)
        return ruta

    def _eventos(self):
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                return False
            if e.type == pygame.VIDEORESIZE:
                self.tam = (e.w, e.h)
                self.render.redimensionar(self.tam)
                self.hud.redimensionar(self.render.tam)
            elif e.type == pygame.KEYDOWN:
                k = e.key
                if k == pygame.K_ESCAPE:
                    return False
                if k == pygame.K_SPACE:
                    if self.t >= self.plan.duracion - 1e-3:
                        self.t = 0.0
                        self.pausa = False
                    else:
                        self.pausa = not self.pausa
                elif k == pygame.K_RIGHT:
                    self.t = min(self.t + 5, self.plan.duracion)
                elif k == pygame.K_LEFT:
                    self.t = max(self.t - 5, 0)
                elif k == pygame.K_UP:
                    self.velocidad = min(self.velocidad * 2, 16)
                elif k == pygame.K_DOWN:
                    self.velocidad = max(self.velocidad / 2, 0.125)
                elif k == pygame.K_c:
                    self.camara.siguiente()
                elif k in (pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4, pygame.K_5):
                    self.camara.modo = MODOS[k - pygame.K_1]
                elif k == pygame.K_n:
                    paso = -1 if e.mod & pygame.KMOD_SHIFT else 1
                    self.camara.dron = (self.camara.dron + paso) % self.plan.n
                    self.camara.modo = "dron"
                elif k == pygame.K_t:
                    self.render.estelas = not self.render.estelas
                elif k == pygame.K_b:
                    self.render.cuerpos = not self.render.cuerpos
                elif k == pygame.K_h:
                    self.hud_visible = not self.hud_visible
                elif k == pygame.K_r:
                    self.t = 0.0
                    self.pausa = False
                elif k == pygame.K_F9:
                    self._grabar()
                elif k == pygame.K_F12:
                    self._captura_pendiente = True
                elif k in (pygame.K_PLUS, pygame.K_KP_PLUS, pygame.K_EQUALS):
                    self.render.exposicion = min(self.render.exposicion * 1.15, 4)
                elif k in (pygame.K_MINUS, pygame.K_KP_MINUS):
                    self.render.exposicion = max(self.render.exposicion / 1.15, 0.3)
            elif e.type == pygame.MOUSEBUTTONDOWN:
                if e.button == 1 and self.hud_visible and self.hud.rect_grabar.collidepoint(e.pos):
                    self._grabar()
                    self._hud_t = 0.0
                elif e.button == 1 and self.hud_visible and self.hud.linea.collidepoint(e.pos):
                    self.buscando = True
                    self._buscar(e.pos[0])
                elif e.button in (1, 3):
                    self.camara.a_libre()
                    self.arrastre = (e.button, e.pos)
                elif e.button in (4, 5):
                    self.camara.a_libre()
                    self.camara.dist *= 0.9 if e.button == 4 else 1.1
                    self.camara.dist = float(np.clip(self.camara.dist, 3, 3000))
            elif e.type == pygame.MOUSEBUTTONUP:
                self.buscando = False
                self.arrastre = None
            elif e.type == pygame.MOUSEMOTION:
                if self.buscando:
                    self._buscar(e.pos[0])
                elif self.arrastre:
                    boton, (x0, y0) = self.arrastre
                    dx, dy = e.pos[0] - x0, e.pos[1] - y0
                    cam = self.camara
                    if boton == 1:
                        cam.yaw -= dx * 0.005
                        cam.pitch = float(np.clip(cam.pitch + dy * 0.004, -0.2, 1.5))
                    else:
                        f = cam.dist * 0.0015
                        der = np.array([-math.sin(cam.yaw), math.cos(cam.yaw), 0])
                        cam.libre_obj += der * dx * f + np.array([0, 0, 1]) * dy * f
                    self.arrastre = (boton, e.pos)
        return True

    def _grabar(self):
        if self.grabador.grabando:
            self.grabador.detener()
            self.hud.mostrar_aviso(f"Video guardado en grabaciones\\{os.path.basename(self.grabador.archivo)}", self.reloj)
        else:
            try:
                w, h = self.render.tam
                self.grabador.iniciar(w, h)
                self.hud.mostrar_aviso("Grabando… (F9 para detener)", self.reloj)
            except RuntimeError as ex:
                self.hud.mostrar_aviso(str(ex), self.reloj)

    def cuadro(self, dt):
        self.reloj = time.perf_counter()
        if not self.pausa and not self.buscando:
            self.t += dt * self.velocidad
            if self.t >= self.plan.duracion:
                self.t = self.plan.duracion
                self.pausa = True
        pos, col, b, self.seg_i = self.plan.estado(self.t)
        fase = self.plan.seg[self.seg_i]["fase"]
        pos = self._ruido(pos, self.t)
        ejes = self._ejes(self.t, pos)
        self._foco(pos, b, dt)
        self._telemetria(pos, self.t, dt)
        cam = self.camara.actualizar(dt, self.foco, self.radio, pos, self.plan, self.t, fase)
        if self.hud_visible and (self.reloj - self._hud_t > 1 / 15):
            self._hud_t = self.reloj
            self.render.subir_hud(self.hud.dibujar(self))
        self.render.dibujar(cam, pos, col, b, ejes, self.reloj, self.hud_visible)
        if self.grabador.grabando and self.grabador.necesita_cuadro():
            w, h = self.render.tam
            self.grabador.cuadro(self.ctx.screen.read(viewport=(0, 0, w, h), components=3))

    def correr(self):
        reloj = pygame.time.Clock()
        self._captura_pendiente = False
        sigue = True
        while sigue:
            dt = min(reloj.tick(120) / 1000.0, 0.1)
            sigue = self._eventos()
            self.cuadro(dt)
            if self._captura_pendiente:
                self._captura_pendiente = False
                ruta = self.captura()
                self.hud.mostrar_aviso(f"Captura guardada: {os.path.basename(ruta)}", self.reloj)
            pygame.display.flip()
        self.grabador.detener(esperar=True)
        pygame.quit()

    def capturas(self, tiempos, carpeta, modo):
        os.makedirs(carpeta, exist_ok=True)
        self.camara.modo = modo
        rutas = []
        for i, tt in enumerate(tiempos):
            self.t = max(tt - 3.0, 0)
            self.pausa = False
            self.camara.primera = True
            for _ in range(int(3.0 * 30)):
                pygame.event.pump()
                self.cuadro(1 / 30)
                if self.t >= tt:
                    break
            self._hud_t = 0
            self.cuadro(1 / 30)
            rutas.append(self.captura(os.path.join(carpeta, f"captura_{i:02d}_{int(tt):03d}s_{modo}.png")))
            pygame.display.flip()
        pygame.quit()
        return rutas


def main():
    ap = argparse.ArgumentParser(description="Visor 3D del espectáculo de drones")
    ap.add_argument("plan", nargs="?", default=C.PLAN_ACTUAL)
    ap.add_argument("--camara", default="cine", choices=MODOS)
    ap.add_argument("--resolucion", default=None)
    ap.add_argument("--capturas", default=None, help="tiempos separados por coma")
    ap.add_argument("--salida", default=os.path.join(C.RAIZ, "grabaciones", "capturas"))
    a = ap.parse_args()
    ruta = a.plan
    if ruta.lower().endswith(".json"):
        import json
        with open(ruta, encoding="utf-8") as f:
            show = json.load(f)
        print("Calculando el plan de vuelo…")
        plan = PL.construir_show(show, avisar=print)
    else:
        if not os.path.exists(ruta):
            print("No hay plan calculado. Abre el diseñador (main.py) y presiona «Ver show en 3D».")
            sys.exit(1)
        plan = PL.Plan.cargar(ruta)
    tam = tuple(int(v) for v in a.resolucion.lower().split("x")) if a.resolucion else None
    v = Visor(plan, tam, a.camara)
    if a.capturas:
        for r in v.capturas([float(x) for x in a.capturas.split(",")], a.salida, a.camara):
            print(r)
    else:
        v.correr()


if __name__ == "__main__":
    main()
