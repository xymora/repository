import math
import os
import multiprocessing as mp
import time

import moderngl
import numpy as np
import pygame

import cerebro as B
import config as C
import modelos as MD
import render as RD
import terreno as T
from cabina import AMBAR, FT, KT, Panel, _fuente, _texto
from grabador import Grabador
from evolucion import bajar_prioridad, demos_tarea, evaluar, imitar_tarea
from hud import HUD, Proyector, vineta
import catalogo as K
from arranque import VUELO
from misiones import BLANCO, COMBATE, CURRICULO, DESPEGUE, DETENER, PENDIENTE, PUNTO, TOQUE, Episodio, descripcion, \
    nombre
from piloto import Instructor
from sensores import observar
from sonido import Sonido
from tablero import Tablero

FONDO = (14, 16, 20)
TARJETA = (22, 25, 32, 228)
BORDE = (38, 43, 54)
TEXTO = (232, 234, 238)
TENUE = (150, 156, 168)
ORO = (245, 180, 0)
AZUL = (90, 170, 255)
VERDE = (80, 220, 120)
ROJO = (255, 80, 60)
HORAS = list(RD.HORAS.keys())
NUBES = list(RD.NUBES.keys())
VELOCIDADES = (1, 2, 4, 8)
TAMANOS = ((1920, 1080), (1600, 900), (1280, 720))
TECLAS_ARRANQUE = {pygame.K_1: ("CANOPY", "CANOPY"), pygame.K_2: ("JFS", "JFS"), pygame.K_3: ("BOMBAS", "BOMBAS"),
                   pygame.K_4: ("ARR_D", "COMB_D"), pygame.K_5: ("ARR_I", "COMB_I"), pygame.K_6: ("GEN", "GEN"),
                   pygame.K_7: ("AVIONICA", "AVIONICA"), pygame.K_8: ("SAS", "SAS"),
                   pygame.K_9: ("CHEQUEO", "CHEQUEO"), pygame.K_0: ("RODAJE", "RODAJE")}


def _ang(a):
    return (a + math.pi) % (2 * math.pi) - math.pi


def _nlerp(q0, q1, t):
    if np.dot(q0, q1) < 0:
        q1 = -q1
    q = q0 * (1 - t) + q1 * t
    return q / np.linalg.norm(q)


def _mat_q(q):
    from fisica import matriz
    return matriz(q[None])[0]


class Particulas:
    def __init__(self):
        self.humo = np.zeros((0, 12))
        self.fuego = np.zeros((0, 12))

    def _agregar(self, cual, pos, vel, tam, crece, vida, color):
        n = len(pos)
        filas = np.zeros((n, 12))
        filas[:, 0:3] = pos
        filas[:, 3:6] = vel
        filas[:, 6] = tam
        filas[:, 7] = crece
        filas[:, 8] = vida
        filas[:, 9] = vida
        filas[:, 10] = color[0] if np.isscalar(color[0]) else 0
        filas[:, 11] = color[3] if len(color) > 3 else 1
        if cual == "humo":
            self.humo = np.concatenate([self.humo, filas])[-5000:]
        else:
            self.fuego = np.concatenate([self.fuego, filas])[-3000:]

    def explosion(self, p, rng, grande=1.0):
        n = int(40 * grande)
        d = rng.standard_normal((n, 3))
        self._agregar("fuego", p + d * 3 * grande, d * 25 * grande, 8 * grande, 18 * grande, 1.2, (1.0, 0, 0, 1))
        self._agregar("humo", p + d * 4, d * 10 + [0, 6, 0], 10 * grande, 14 * grande, 7.0, (0.18, 0, 0, 0.85))

    def estela(self, p, tam=2.5, vida=4.0, gris=0.85, alfa=0.55):
        self._agregar("humo", np.atleast_2d(p), np.zeros((len(np.atleast_2d(p)), 3)) + [0, 0.5, 0], tam, 2.5, vida,
                      (gris, 0, 0, alfa))

    def llamita(self, p, tam=1.5):
        self._agregar("fuego", np.atleast_2d(p), np.zeros((len(np.atleast_2d(p)), 3)), tam, -1.0, 0.12, (1, 0, 0, 1))

    def paso(self, dt):
        for nombre in ("humo", "fuego"):
            a = getattr(self, nombre)
            if not len(a):
                continue
            a[:, 0:3] += a[:, 3:6] * dt
            a[:, 3:6] *= (1 - 0.8 * dt)
            a[:, 6] += a[:, 7] * dt
            a[:, 8] -= dt
            setattr(self, nombre, a[(a[:, 8] > 0) & (a[:, 6] > 0.05)])

    def datos(self):
        h = self.humo
        hs = np.zeros((len(h), 8), "f4")
        if len(h):
            vida = h[:, 8] / h[:, 9]
            hs[:, 0:3] = h[:, 0:3]
            hs[:, 3] = h[:, 6]
            hs[:, 4:7] = h[:, 10:11]
            hs[:, 7] = h[:, 11] * np.minimum(1, vida * 2.5) * np.minimum(1, (1 - vida) * 8 + 0.3)
        f = self.fuego
        fs = np.zeros((len(f), 8), "f4")
        if len(f):
            vida = f[:, 8] / f[:, 9]
            fs[:, 0:3] = f[:, 0:3]
            fs[:, 3] = f[:, 6]
            fs[:, 4] = 1.0
            fs[:, 5] = 0.35 + 0.5 * vida
            fs[:, 6] = 0.08 + 0.3 * vida ** 2
            fs[:, 7] = vida
        return hs, fs


class Mandos:
    def __init__(self):
        self.elev = self.alabeo = self.timon = 0.0
        self.gases = 0.0
        self.freno = 0.0
        self.aerofreno = 0.0
        self.tren = True
        self.flaps = True
        self.fuego = False
        self.canon = False
        self.bengala = False

    def acciones(self):
        b = lambda v: np.array([v])
        return {"elev": b(self.elev), "alabeo": b(self.alabeo), "timon": b(self.timon), "gases": b(self.gases),
                "freno": b(self.freno), "aerofreno": b(self.aerofreno), "tren": b(self.tren),
                "flaps": b(self.flaps), "fuego": b(self.fuego), "canon": b(self.canon), "bengala": b(self.bengala)}


class Aplicacion:
    def __init__(self, entrenador, modo="menu", ventana=False, resolucion=None, completa=False, mision=None):
        self.e = entrenador
        pygame.init()
        pygame.display.gl_set_attribute(pygame.GL_MULTISAMPLEBUFFERS, 1)
        pygame.display.gl_set_attribute(pygame.GL_MULTISAMPLESAMPLES, 4)
        pygame.display.gl_set_attribute(pygame.GL_DEPTH_SIZE, 24)
        banderas = pygame.OPENGL | pygame.DOUBLEBUF | pygame.RESIZABLE
        info = pygame.display.Info()
        if completa:
            C.ANCHO, C.ALTO = info.current_w, info.current_h
            banderas = pygame.OPENGL | pygame.DOUBLEBUF | pygame.NOFRAME
            os.environ["SDL_VIDEO_WINDOW_POS"] = "0,0"
        elif resolucion:
            C.ANCHO, C.ALTO = resolucion
        elif not ventana:
            for w, h in TAMANOS:
                if info.current_w >= w and info.current_h - 70 >= h:
                    C.ANCHO, C.ALTO = w, h
                    break
        try:
            self.pantalla = pygame.display.set_mode((C.ANCHO, C.ALTO), banderas, vsync=1)
        except pygame.error:
            pygame.display.gl_set_attribute(pygame.GL_MULTISAMPLEBUFFERS, 0)
            pygame.display.gl_set_attribute(pygame.GL_MULTISAMPLESAMPLES, 0)
            self.pantalla = pygame.display.set_mode((C.ANCHO, C.ALTO), banderas)
        pygame.display.set_caption("F-15 Eagle evolutivo — simulador de vuelo desde la cabina")
        self.W, self.H = C.ANCHO, C.ALTO
        self.ctx = moderngl.create_context()
        self.r = RD.Renderizador(self.ctx, self.W, self.H)
        self.r.destino = self.ctx.screen
        self.capa = pygame.Surface((self.W, self.H), pygame.SRCALPHA)
        self.panel = Panel()
        self.hud = HUD()
        self.son = Sonido()
        self.part = Particulas()
        self.rng = np.random.default_rng()
        self.balas_p = np.zeros((0, 3))
        self.balas_v = np.zeros((0, 3))
        self.balas_t = np.zeros(0)
        self.acum_bala = 0.0
        self.tablero = Tablero()
        self._fuentes()
        pygame.joystick.init()
        self.joy = pygame.joystick.Joystick(0) if pygame.joystick.get_count() else None
        if self.joy:
            self.joy.init()
        self.reloj = pygame.time.Clock()
        self.hora_i = HORAS.index("tarde")
        self.nubes_i = 1
        self.entrenar = True
        self.pool = mp.Pool(C.PROCESOS, initializer=bajar_prioridad)
        self.pendiente = None
        self.pend_demos = None
        self.pend_imit = None
        self.demos_listas = None
        self.instantanea = None
        self.gen_t = []
        self.mensaje = ("", 0.0)
        self.modo = None
        self.menu_pila = []
        self.menu_sel = 0
        self.ayuda = False
        self.tarjeta = True
        self.mostrar_hud = True
        self.pausa = False
        self.i_vel = 0
        self.cabeza = [0.0, -9.0]
        self.fov = 72.0
        self.arrastre = False
        self.t = 0.0
        self.t_panel = 0.0
        self.panel_bytes = None
        self.mandos = Mandos()
        self.autopiloto = False
        self.demo = []
        self.demo_lista = None
        self.ep = None
        self.grab = Grabador()
        self.guardando_video = False
        self.rect_grabar = pygame.Rect(self.W - 196, self.H - 52, 182, 36)
        self.episodios = 0
        self.tablero_on = True
        self.arranque_frio = True
        self.toma = False
        self.demo_toma = []
        self.rects_arranque = []
        self.inicio = modo == "menu"
        self.rapido = False
        if self.inicio:
            self.iniciar_campeon(CURRICULO[0], aviso=False)
            self.menu_pila = ["principal"]
            self.menu_sel = 0
        else:
            self.lanzar()
            self.iniciar_ia()
        if modo == "humano":
            self.iniciar_humano(mision if mision is not None else 1)
        elif modo == "libre":
            self.iniciar_humano(0)
        elif modo == "ver" and mision is not None:
            self.iniciar_campeon(mision)
        if modo == "menu":
            self.aviso("Elige qué hacer · flechas y Enter o clic · F1 controles", 8)

    def _fuentes(self):
        k = max(0.8, min(1.6, self.H / 900))
        self.k = k
        self.f_tit = _fuente(int(30 * k), True, False)
        self.f_gr = _fuente(int(22 * k), True, False)
        self.f_med = _fuente(int(17 * k), False, False)
        self.f_med_b = _fuente(int(17 * k), True, False)
        self.f_peq = _fuente(int(14 * k), False, False)
        self.f_mono = _fuente(int(14 * k))
        self.tablero.ajustar(k)

    def redimensionar(self, w, h):
        w, h = max(800, int(w)), max(500, int(h))
        if (w, h) == (self.W, self.H):
            return
        if self.grab.grabando:
            self.grab.detener()
            self.guardando_video = True
        self.W, self.H = w, h
        C.ANCHO, C.ALTO = w, h
        self.ctx.screen.viewport = (0, 0, w, h)
        self.r.redimensionar(w, h)
        self.capa = pygame.Surface((w, h), pygame.SRCALPHA)
        self.rect_grabar = pygame.Rect(w - 196, h - 52, 182, 36)
        self.pbos = None
        self._fuentes()

    def aviso(self, txt, dur=4.0):
        self.mensaje = (txt, time.perf_counter() + dur)

    def lanzar(self):
        if self.inicio:
            return
        if self.pendiente is not None or self.pend_imit is not None:
            return
        if self.demos_listas is not None:
            x, y, n = self.demos_listas
            self.demos_listas = None
            self.pend_imit = (self.pool.apply_async(imitar_tarea, (self.e.preparar_aprendizaje(x, y, n),)), len(x))
            return
        if not self.entrenar or self.pend_demos is not None and self.pend_demos[2]:
            return
        tareas = self.e.tareas()
        self.instantanea = (self.e.poblacion.copy(), self.e.leccion_evaluada, self.e.semillas[0], self.e.generacion)
        self.pendiente = self.pool.map_async(evaluar, tareas)
        self.t_lanzo = time.perf_counter()

    def revisar_entrenamiento(self):
        if self.inicio:
            if self.menu_pila:
                return
            self.inicio = False
            self.lanzar()
        if self.pendiente is not None and self.pendiente.ready():
            try:
                res = self.pendiente.get()
            except Exception as ex:
                self.aviso(f"Error al evaluar: {ex}")
                self.pendiente = None
                return
            self.pendiente = None
            r = self.e.terminar(res)
            self.gen_t.append(time.perf_counter())
            self.gen_t = self.gen_t[-20:]
            print(f"gen {r['generacion']:5d} · lección {r['leccion']} {r['nombre']:<26} mejor {r['mejor_progreso']:5.1f}% "
                  f"prom {r['promedio_progreso']:5.1f}% superaron {r['superaron_pct']:5.1f}% caídos "
                  f"{r['estrellados_pct']:5.1f}% sigma {r['sigma']:.4f} · {r['motivo_lider']}", flush=True)
            if r["volvio"] != "":
                print(f"           la IA iba peor que su campeón: regresa a la generación {r['volvio']} y sigue desde ahí",
                      flush=True)
                self.aviso(f"La IA iba peor que su mejor versión: regresa a la generación {r['volvio']}", 6)
            if r["subio"]:
                self.aviso(f"¡La IA superó «{r['nombre']}»! Pasa a la siguiente lección", 6)
        if self.pend_demos is not None and self.pend_demos[0].ready():
            res, n, _ = self.pend_demos
            self.pend_demos = None
            partes = [p for p in res.get() if p is not None]
            datos = (np.concatenate([p[0] for p in partes]), np.concatenate([p[1] for p in partes])) if partes else None
            if datos is None:
                self.aviso("El instructor no logró una demostración válida")
            else:
                self.e.anotar_clase(n)
                self.demos_listas = (datos[0], datos[1], n)
                self.aviso(f"Clase lista: {len(datos[0])} ejemplos del instructor; la IA los estudiará ahora")
        if self.pend_imit is not None and self.pend_imit[0].ready():
            res, cuantos = self.pend_imit
            self.pend_imit = None
            try:
                total = self.e.aplicar_aprendizaje(res.get())
                self.aviso(f"La IA estudió {cuantos} ejemplos ({total} en su memoria de vuelo)")
            except Exception as ex:
                self.aviso(f"No se pudo estudiar la clase: {ex}")
        if self.entrenar and self.pend_demos is None and self.demos_listas is None:
            n = self.e.necesita_clase()
            if n is not None:
                self.e.anotar_clase(n)
                self.clase_instructor(n, auto=True)
        self.lanzar()

    def clase_instructor(self, numero=None, auto=False):
        if self.pend_demos is not None:
            if not auto:
                self.aviso("Ya hay una clase en curso")
            return
        n = numero or self.e.leccion_actual
        semillas = [int(s) for s in self.rng.integers(1, 1 << 30, 6)]
        self.pend_demos = (self.pool.map_async(demos_tarea, [(n, [s], 6) for s in semillas]), n, auto)
        motivo = "Clase automática: " if auto else ""
        self.aviso(f"{motivo}el instructor vuela «{nombre(n)}» 36 veces para enseñarle a la IA…", 7)

    def alternar_toma(self):
        if self.modo not in ("ia", "campeon") or self.ep is None:
            return
        j = self.seguido
        f = self.ep.f
        if self.toma:
            self.toma = False
            self.ep.libre[j] = False
            n = len(self.demo_toma)
            if not self.ep.terminado[j]:
                self.ep.duracion = max(self.ep.duracion, self.ep.t + C.MARGEN_TOMA)
            if f.vivo[j] and n > 20:
                x = np.array([d[0] for d in self.demo_toma])
                y = np.array([d[1] for d in self.demo_toma])
                self.demos_listas = (x, y, self.ep.numero)
                self.aviso(f"La IA retoma los mandos y estudiará tu corrección ({n} ejemplos)", 5)
            else:
                self.aviso("La IA retoma los mandos", 3)
            self.demo_toma = []
            return
        if not f.vivo[j] or self.ep.terminado[j] and not self.ep.rodando()[j]:
            self.aviso("Ese avión ya no vuela: elige otro con N, L o clic")
            return
        m = Mandos()
        a = self.acc_ia
        if a is not None:
            m.elev, m.alabeo, m.timon = float(a["elev"][j]), float(a["alabeo"][j]), float(a["timon"][j])
        m.gases = float(f.entrada["gases"][j])
        m.tren = bool(f.cmd_tren[j] > 0.5)
        m.flaps = bool(f.cmd_flaps[j] > 0.5)
        m.aerofreno = float(f.cmd_aerofreno[j])
        self.mandos = m
        self.toma = True
        self.ep.libre[j] = True
        self.aviso_rodaje = False
        self.demo_toma = []
        self.aviso("Tú pilotas este avión · J para devolverle los mandos a la IA", 5)

    def _soltar(self):
        if self.toma:
            self.alternar_toma()

    def iniciar_ia(self):
        self.toma = False
        if self.inicio:
            self.inicio = False
            self.lanzar()
        if self.instantanea is None:
            return
        pob, n, semilla, gen = self.instantanea
        self.modo = "ia"
        self.ep = Episodio(n, len(pob), semilla, frio=self.arranque_frio)
        self.pilotos = B.Pilotos(pob)
        self.gen_vista = gen
        self.episodios += 1
        self.seguido = 1
        self.t_caido = None
        self._reiniciar_vista()

    def iniciar_campeon(self, n, aviso=True):
        self.toma = False
        c = self.e.campeones.get(n)
        if c is None and n == COMBATE:
            c = self.e.campeones.get(9) or self.e.campeones.get(8)
        if c is not None:
            pesos, info = np.array(c["pesos"]), c
        else:
            pesos = self.e.mejores_pesos()
            info = {"generacion": self.e.generacion, "actual": True}
            if aviso:
                self.aviso(f"Sin campeón propio en «{nombre(n)}»: vuela la IA actual (gen. {self.e.generacion})")
        self.modo = "campeon"
        self.leccion_campeon = n
        self.ep = Episodio(n, 1, int(self.rng.integers(1, 1 << 30)), frio=self.arranque_frio)
        self.pilotos = B.Pilotos(pesos[None])
        self.seguido = 0
        self.info_campeon = info
        self._reiniciar_vista()
        return True

    def iniciar_humano(self, n):
        self.modo = "humano"
        self.leccion_humano = n
        self.ep = Episodio(n, 1, int(self.rng.integers(1, 1 << 30)), manual=True, frio=self.arranque_frio)
        self.seguido = 0
        self.mandos = Mandos()
        ini = self.ep.esc["inicio"]
        self.mandos.gases = ini["gases"]
        self.mandos.tren = ini["tren"] > 0.5
        self.mandos.flaps = ini["tren"] > 0.5 and not self.ep.esc["frio"]
        self.mandos.aerofreno = 0.0
        self.mandos.freno = 1.0 if ini["vel"] < 1 else 0.0
        self.instructor = Instructor(1)
        self.acc_auto = None
        self.autopiloto = False
        self.demo = []
        self.demo_lista = None
        self._reiniciar_vista()
        if n == COMBATE:
            self.aviso("¡Combate! 3 cazas enemigos al norte. Espacio misil · Ctrl cañón · Q bengalas", 8)
        elif self.ep.esc["frio"]:
            self.aviso("Cold & Dark: sigue la lista con las teclas 1–0 o con clic en el panel de arranque", 9)
        elif n:
            self.aviso(f"Misión {n}: {nombre(n)} — {descripcion(n)}", 7)
        else:
            self.aviso("Vuelo libre: pista 34 de la Base Aérea Halcón. Hay un dron blanco en la zona.", 7)

    def _reiniciar_vista(self):
        f = self.ep.f
        self.prev = (f.pos.copy(), f.q.copy())
        self.acum = 0.0
        self.paso_n = 0
        self.part = Particulas()
        self.acc_ia = None
        self.ultimo_vivo = f.vivo.copy()
        self.drones_vivos = self.ep.drones.vivo.copy()
        self.tocaba = f.tocando.copy()
        self.tren_cmd_prev = f.cmd_tren.copy()
        self.cabeza = [0.0, -9.0]

    def abrir_menu(self, cual="principal"):
        self.menu_pila = [cual]
        self.menu_sel = 0
        self.pausa_menu = True

    def opciones_menu(self):
        cual = self.menu_pila[-1] if self.menu_pila else None
        modo = {"secuencial": "secuencial", "mezcla": "mezcla con repaso",
                "fija": f"fijo en «{nombre(self.e.mision_fija)}»"}.get(self.e.modo, self.e.modo)
        if cual == "principal":
            return [("Misiones (pilotas tú)", "sub_misiones"),
                    ("Vuelo libre desde la pista", "libre"),
                    ("Ver a la IA aprender (generación en vivo)", "ia"),
                    ("Ver a la IA volar una misión", "sub_campeon"),
                    (f"Currículo de la IA: {modo}", "sub_curriculo"),
                    (f"Clase con el instructor para la IA ({nombre(self.e.leccion_actual)})", "clase"),
                    (f"Entrenamiento rápido sin gráficos ({len(K.MISIONES)} misiones)", "rapido"),
                    (f"Panel de entrenamiento: {'visible' if self.tablero_on else 'oculto'}", "tablero"),
                    (f"Arranque en frío al salir de la pista: {'sí' if self.arranque_frio else 'no'}", "frio"),
                    (f"Hora del día: {HORAS[self.hora_i]}", "hora"),
                    (f"Nubes: {NUBES[self.nubes_i]}", "nubes"),
                    (f"Entrenamiento en segundo plano: {'sí' if self.entrenar else 'no'}", "entrenar"),
                    ("Guardar progreso de la IA", "guardar"),
                    ("Reiniciar la IA desde cero", "reiniciar"),
                    *([] if self.inicio else [("Volver al vuelo", "volver")]),
                    ("Salir", "salir")]
        if cual == "sub_misiones":
            ops = [(f"{m['numero']}. {m['nombre']}", ("lec", m["numero"]))
                   for m in sorted(K.MISIONES.values(), key=lambda m: m["orden"])]
            return ops + [("← Volver", "atras")]
        if cual == "sub_campeon":
            ops = []
            for k in CURRICULO:
                c = self.e.campeones.get(k)
                extra = (("superada" if c.get("verificada", True) else "superada, por confirmar") if c["superada"] else f"progreso {round(100 * c['progreso'])}%") if c else \
                    "IA actual"
                ops.append((f"{k}. {nombre(k)}  · {extra}", ("camp", k)))
            c = self.e.campeones.get(COMBATE)
            extra = (("superada" if c.get("verificada", True) else "superada, por confirmar") if c["superada"] else f"progreso {round(100 * c['progreso'])}%") if c else                 "usa lo aprendido en cañón/intercepción"
            ops.append((f"{COMBATE}. {nombre(COMBATE)}  · {extra}", ("camp", COMBATE)))
            return ops + [("← Volver", "atras")]
        if cual == "sub_curriculo":
            return [("Secuencial: aprobar cada misión para pasar a la siguiente", ("modo", "secuencial")),
                    ("Mezcla: misión actual + repaso de una anterior", ("modo", "mezcla")),
                    ("Fijo: entrenar sólo una misión…", "sub_fija"),
                    ("← Volver", "atras")]
        if cual == "sub_fija":
            ops = [(f"{k}. {nombre(k)}", ("fija", k)) for k in CURRICULO]
            return ops + [("← Volver", "atras")]
        if cual == "confirmar":
            return [("Sí, borrar todo lo aprendido", "borrar"), ("No, cancelar", "atras")]
        return []

    def accion_menu(self, a):
        if a == "libre":
            self.iniciar_humano(0)
            self.menu_pila = []
        elif a in ("sub_misiones", "sub_campeon", "sub_curriculo", "sub_fija", "confirmar"):
            self.menu_pila.append(a)
            self.menu_sel = 0
        elif a == "ia":
            self.iniciar_ia()
            self.menu_pila = []
        elif a == "clase":
            self.clase_instructor()
        elif a == "rapido":
            self.rapido = True
            self.salir = True
        elif a == "tablero":
            self.tablero_on = not self.tablero_on
        elif a == "frio":
            self.arranque_frio = not self.arranque_frio
        elif a == "hora":
            self.hora_i = (self.hora_i + 1) % len(HORAS)
            self.r.configurar(HORAS[self.hora_i])
        elif a == "nubes":
            self.nubes_i = (self.nubes_i + 1) % len(NUBES)
            self.r.nubes(RD.NUBES[NUBES[self.nubes_i]])
        elif a == "entrenar":
            self.entrenar = not self.entrenar
        elif a == "guardar":
            self.e.guardar()
            self.aviso(f"Progreso guardado (generación {self.e.generacion}, misión {self.e.leccion_actual})")
        elif a == "reiniciar":
            self.menu_pila.append("confirmar")
            self.menu_sel = 1
        elif a == "borrar":
            if self.pendiente is not None:
                self.pendiente.wait()
                self.pendiente = None
            self.e.reiniciar()
            self.lanzar()
            self.iniciar_ia()
            self.menu_pila = ["principal"]
            self.aviso("La IA empieza desde cero")
        elif a == "volver":
            self.menu_pila = []
        elif a == "salir":
            self.salir = True
        elif a == "atras":
            self.menu_pila.pop()
            self.menu_sel = 0
        elif isinstance(a, tuple):
            if a[0] == "lec":
                self.iniciar_humano(a[1])
                self.menu_pila = []
            elif a[0] == "camp":
                if self.iniciar_campeon(a[1]):
                    self.menu_pila = []
            elif a[0] in ("modo", "fija"):
                modo, m = (a[1], None) if a[0] == "modo" else ("fija", a[1])
                self.e.fijar_modo(modo, m)
                self.menu_pila = ["principal"]
                self.menu_sel = 0
                self.aviso(f"Currículo de la IA: {modo}" + (f" · {nombre(m)}" if m else "") +
                           " (se aplica desde la próxima generación)", 6)

    def eventos(self):
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                self.salir = True
            elif ev.type == pygame.VIDEORESIZE:
                self.redimensionar(ev.w, ev.h)
            elif ev.type == getattr(pygame, "WINDOWSIZECHANGED", -1):
                self.redimensionar(*pygame.display.get_window_size())
            elif ev.type == pygame.KEYDOWN:
                self.tecla(ev)
            elif ev.type == pygame.MOUSEBUTTONDOWN:
                if ev.button == 3:
                    self.arrastre = True
                    pygame.mouse.get_rel()
                elif ev.button == 2:
                    self.cabeza = [0.0, -9.0]
                elif ev.button == 4:
                    self.fov = max(25.0, self.fov - 3)
                elif ev.button == 5:
                    self.fov = min(85.0, self.fov + 3)
                elif ev.button == 1 and self.rect_grabar.collidepoint(ev.pos):
                    self.alternar_grabacion()
                elif ev.button == 1 and not self.menu_pila and self.modo == "ia" and \
                        any(r.collidepoint(ev.pos) for r, _ in getattr(self, "rects_indiv", [])):
                    for rect, i in self.rects_indiv[::-1]:
                        if rect.collidepoint(ev.pos):
                            self._soltar()
                            self.seguido = i
                            self._reprev()
                            self.aviso(f"Cabina del individuo {i} · L vuelve al líder")
                            break
                elif ev.button == 1 and not self.menu_pila and self.modo == "humano" and self.rects_arranque:
                    for rect, nm in self.rects_arranque:
                        if rect.collidepoint(ev.pos):
                            self.interruptor(nm)
                            break
                elif ev.button == 1 and self.menu_pila:
                    for k, rect in enumerate(getattr(self, "rects_menu", [])):
                        if rect.collidepoint(ev.pos):
                            self.menu_sel = k
                            self.accion_menu(self.opciones_menu()[k][1])
                            break
            elif ev.type == pygame.MOUSEBUTTONUP and ev.button == 3:
                self.arrastre = False
            elif ev.type == pygame.MOUSEMOTION:
                if self.arrastre:
                    dx, dy = ev.rel
                    self.cabeza[0] = max(-170.0, min(170.0, self.cabeza[0] + dx * 0.25))
                    self.cabeza[1] = max(-60.0, min(85.0, self.cabeza[1] - dy * 0.25))
                elif self.menu_pila:
                    for k, rect in enumerate(getattr(self, "rects_menu", [])):
                        if rect.collidepoint(ev.pos):
                            self.menu_sel = k
            elif ev.type == pygame.JOYBUTTONDOWN and self.modo == "humano":
                if ev.button == 2:
                    self._tren()
                elif ev.button == 4:
                    self.mandos.flaps = not self.mandos.flaps

    def interruptor(self, nm):
        ep = self.ep
        if not ep.arranque.activo or ep.terminado[0]:
            return
        if nm == "FLAPS":
            self.mandos.flaps = not self.mandos.flaps
        else:
            ep.arranque.interruptor(ep.f, 0, nm)
        self.son.evento("clic")

    def _tren(self):
        if self.ep.f.en_suelo[self.seguido if self.toma else 0] and self.mandos.tren:
            self.aviso("El tren no se sube con el avión en tierra")
            return
        self.mandos.tren = not self.mandos.tren
        self.son.evento("tren")

    def alternar_grabacion(self):
        if self.grab.grabando:
            self.grab.detener()
            self.guardando_video = True
            return
        if self.grab.ocupado:
            return
        try:
            self.grab.iniciar(self.W, self.H)
        except Exception as ex:
            self.aviso(f"No se pudo grabar: {ex}")
            return
        self.aviso("Grabando la pantalla… (F9 o el botón para detener)", 3)

    def capturar_video(self):
        if not self.grab.grabando:
            self.pbo_lleno = [False, False]
            return
        if not self.grab.necesita_cuadro():
            return
        if getattr(self, "pbos", None) is None:
            self.pbos = [self.ctx.buffer(reserve=self.W * self.H * 3) for _ in range(2)]
            self.pbo_i = 0
            self.pbo_lleno = [False, False]
        i = self.pbo_i
        self.ctx.screen.read_into(self.pbos[i], viewport=(0, 0, self.W, self.H), components=3)
        self.pbo_lleno[i] = True
        j = 1 - i
        if self.pbo_lleno[j]:
            self.grab.cuadro(self.pbos[j].read())
        self.pbo_i = j

    def boton_grabar(self, s):
        r = self.rect_grabar
        g = self.grab
        if self.guardando_video and not g.ocupado:
            self.guardando_video = False
            if g.error:
                self.aviso(f"Error al guardar el video: {g.error}", 6)
            else:
                self.aviso(f"Video guardado: grabaciones\\{os.path.basename(g.archivo)}", 6)
        if g.grabando:
            seg = int(time.perf_counter() - g.inicio)
            color, texto = (239, 83, 80), f"Detener  {seg // 60:02d}:{seg % 60:02d}"
        elif g.ocupado:
            color, texto = (120, 120, 120), "Guardando…"
        else:
            color, texto = (255, 171, 145), "Grabar pantalla"
        sobre = r.collidepoint(pygame.mouse.get_pos())
        pygame.draw.rect(s, color + (255 if sobre else 225,), r, border_radius=8)
        cx, cy = r.x + 20, r.centery
        if g.grabando:
            if int(time.perf_counter() * 2) % 2 == 0:
                pygame.draw.rect(s, (255, 255, 255), (cx - 7, cy - 7, 14, 14), border_radius=2)
        else:
            pygame.draw.circle(s, (200, 30, 30) if not g.ocupado else (60, 60, 60), (cx, cy), 8)
        _texto(s, self.f_med_b, texto, (20, 20, 20), (r.x + 36, cy - 11))

    def tecla(self, ev):
        k = ev.key
        if k == pygame.K_F9:
            self.alternar_grabacion()
            return
        if self.menu_pila:
            ops = self.opciones_menu()
            if k in (pygame.K_UP, pygame.K_w):
                self.menu_sel = (self.menu_sel - 1) % len(ops)
            elif k in (pygame.K_DOWN, pygame.K_s):
                self.menu_sel = (self.menu_sel + 1) % len(ops)
            elif k in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_KP_ENTER):
                self.accion_menu(ops[self.menu_sel][1])
            elif k == pygame.K_ESCAPE:
                if len(self.menu_pila) > 1:
                    self.menu_pila.pop()
                    self.menu_sel = 0
                elif not self.inicio:
                    self.menu_pila = []
            self.son.evento("clic")
            return
        if k == pygame.K_ESCAPE:
            self.abrir_menu()
        elif k == pygame.K_F1:
            self.ayuda = not self.ayuda
        elif k == pygame.K_F5:
            self.e.guardar()
            self.aviso(f"Progreso guardado (generación {self.e.generacion})")
        elif k == pygame.K_p:
            self.pausa = not self.pausa
        elif k == pygame.K_h:
            self.mostrar_hud = not self.mostrar_hud
        elif k == pygame.K_m:
            self.son.silencio = not self.son.silencio
            if self.son.silencio:
                self.son.callar()
        elif k in (pygame.K_HOME, pygame.K_KP5):
            self.cabeza = [0.0, -9.0]
        elif k == pygame.K_TAB:
            self.tarjeta = not self.tarjeta
        elif k == pygame.K_F2:
            self.tablero_on = not self.tablero_on
        elif self.modo == "humano":
            m = self.mandos
            if k in TECLAS_ARRANQUE and self.ep.arranque.activo:
                shift = pygame.key.get_mods() & pygame.KMOD_SHIFT
                self.interruptor(TECLAS_ARRANQUE[k][1 if shift else 0])
            elif k == pygame.K_g:
                self._tren()
            elif k == pygame.K_f:
                m.flaps = not m.flaps
            elif k == pygame.K_v:
                m.aerofreno = 0.0 if m.aerofreno > 0.5 else 1.0
            elif k == pygame.K_r:
                self.iniciar_humano(self.leccion_humano)
            elif k == pygame.K_q:
                m.bengala = True
            elif k == pygame.K_i and self.leccion_humano:
                self.autopiloto = not self.autopiloto
                self.aviso("Instructor a los mandos (I para retomar)" if self.autopiloto else "Tienes los mandos")
            elif k == pygame.K_t and self.demo_lista is not None:
                x, y = self.demo_lista
                self.demo_lista = None
                self.demos_listas = (x, y, self.leccion_humano)
                self.aviso(f"La IA estudiará tu vuelo ({len(x)} ejemplos)")
            elif k == pygame.K_e and m.gases >= 0.8:
                m.gases = 1.0
        elif self.modo in ("ia", "campeon"):
            if k == pygame.K_j:
                self.alternar_toma()
                return
            if self.toma and k in (pygame.K_g, pygame.K_f, pygame.K_v, pygame.K_q, pygame.K_e):
                m = self.mandos
                if k == pygame.K_g:
                    self._tren()
                elif k == pygame.K_f:
                    m.flaps = not m.flaps
                elif k == pygame.K_v:
                    m.aerofreno = 0.0 if m.aerofreno > 0.5 else 1.0
                elif k == pygame.K_q:
                    m.bengala = True
                elif m.gases >= 0.8:
                    m.gases = 1.0
                return
            if self.toma and k in (pygame.K_n, pygame.K_l):
                self._soltar()
            if k == pygame.K_n and self.modo == "ia":
                vivos = np.flatnonzero(~self.ep.terminado)
                if len(vivos):
                    self.seguido = int(vivos[(np.searchsorted(vivos, self.seguido, "right")) % len(vivos)])
                    self._reprev()
            elif k == pygame.K_l and self.modo == "ia":
                self._seguir_lider()
            elif k == pygame.K_RIGHTBRACKET or k == pygame.K_PLUS or k == pygame.K_KP_PLUS:
                self.i_vel = min(len(VELOCIDADES) - 1, self.i_vel + 1)
            elif k == pygame.K_LEFTBRACKET or k == pygame.K_MINUS or k == pygame.K_KP_MINUS:
                self.i_vel = max(0, self.i_vel - 1)
            elif k == pygame.K_k:
                self.clase_instructor()
            elif k == pygame.K_c and self.modo == "ia":
                self.abrir_menu("sub_campeon")

    def _reprev(self):
        f = self.ep.f
        self.prev = (f.pos.copy(), f.q.copy())

    def _seguir_lider(self):
        self.seguido = int(np.argmax(self.ep.aptitudes() - 1000.0 * ~self.ep.f.vivo))
        self._reprev()

    def marcar_individuos(self, s, pr):
        ep = self.ep
        f = ep.f
        j = self.seguido
        self.rects_indiv = []
        apt = ep.aptitudes()
        vivos = np.flatnonzero(f.vivo & ~ep.terminado)
        if len(vivos) < 2:
            return
        orden = vivos[np.argsort(-apt[vivos])]
        puesto = {int(i): k for k, i in enumerate(orden)}
        k = self.k
        for i in orden[::-1]:
            i = int(i)
            if i == j:
                continue
            p = pr.punto(f.pos[i])
            d = float(np.linalg.norm(f.pos[i] - pr.cam))
            r = puesto[i]
            lider = r == 0
            fuera = p is None or not (0 <= p[0] <= self.W and 0 <= p[1] <= self.H)
            if fuera:
                if r >= 5:
                    continue
                v = f.pos[i] - pr.cam
                x, y = float(np.dot(v, pr.r)), float(np.dot(v, pr.u))
                if p is None and abs(x) + abs(y) < 1e-3:
                    y = -1.0
                n = max(abs(x) / (self.W / 2 - 60), abs(y) / (self.H / 2 - 60), 1e-6)
                p = (self.W / 2 + x / n, self.H / 2 - y / n)
            col = ORO if lider else ((90, 230, 120) if r < 5 else (150, 170, 200))
            alfa = 255 if r < 5 else 150
            t = int((11 if r < 5 else 7) * k)
            x, y = int(p[0]), int(p[1])
            puntos = [(x, y - t), (x + t, y), (x, y + t), (x - t, y)]
            pygame.draw.polygon(s, col + (alfa,), puntos, 2)
            if lider:
                pygame.draw.circle(s, col + (255,), (x, y), int(t * 1.7), 2)
            if r < 5:
                txt = ("LÍDER" if lider else f"#{r + 1}") + f" · {d / 1000:.1f} km" if d >= 1000 else \
                    ("LÍDER" if lider else f"#{r + 1}") + f" · {d:.0f} m"
                _texto(s, self.f_peq, txt, col, (x + t + 6, y - 8))
            self.rects_indiv.append((pygame.Rect(x - t - 6, y - t - 6, 2 * t + 12, 2 * t + 12), i))

    def leer_mandos(self, dt):
        m = self.mandos
        t = pygame.key.get_pressed()

        def eje(actual, neg, pos, vel=2.2, ret=3.5):
            obj = (1.0 if pos else 0.0) - (1.0 if neg else 0.0)
            v = ret if obj == 0 or obj * actual < 0 else vel
            paso = v * dt
            return actual + max(-paso, min(paso, obj - actual))

        m.elev = eje(m.elev, t[pygame.K_UP], t[pygame.K_DOWN])
        m.alabeo = eje(m.alabeo, t[pygame.K_LEFT], t[pygame.K_RIGHT], 2.6, 4.0)
        m.timon = eje(m.timon, t[pygame.K_a] or t[pygame.K_z], t[pygame.K_d] or t[pygame.K_x], 2.0, 3.0)
        d_g = (1 if (t[pygame.K_w] or t[pygame.K_PAGEUP] or t[pygame.K_KP_PLUS]) else 0) - \
            (1 if (t[pygame.K_s] or t[pygame.K_PAGEDOWN] or t[pygame.K_KP_MINUS]) else 0)
        nuevo = m.gases + d_g * 0.45 * dt
        if m.gases <= 0.8 < nuevo and d_g > 0 and not (t[pygame.K_LSHIFT] or t[pygame.K_RSHIFT]):
            nuevo = 0.8
        m.gases = max(0.0, min(1.0, nuevo))
        m.freno = 1.0 if t[pygame.K_b] else 0.0
        m.fuego = bool(t[pygame.K_SPACE])
        m.canon = bool(t[pygame.K_LCTRL] or t[pygame.K_RCTRL] or t[pygame.K_c])
        if self.joy:
            try:
                ax = [self.joy.get_axis(i) for i in range(self.joy.get_numaxes())]
                muerto = lambda v: 0.0 if abs(v) < 0.06 else v
                if len(ax) > 1 and (abs(ax[0]) > 0.06 or abs(ax[1]) > 0.06):
                    m.alabeo = muerto(ax[0])
                    m.elev = muerto(ax[1])
                if len(ax) > 3 and abs(ax[3]) > 0.1:
                    m.timon = muerto(ax[3])
                if len(ax) > 2 and getattr(self, "joy_gases_ok", False):
                    m.gases = (1 - ax[2]) / 2
                elif len(ax) > 2 and abs(ax[2]) > 0.2:
                    self.joy_gases_ok = True
                if self.joy.get_numbuttons() > 1:
                    m.fuego = m.fuego or self.joy.get_button(0)
                    m.canon = m.canon or self.joy.get_button(1)
                if self.joy.get_numbuttons() > 3 and self.joy.get_button(3):
                    m.freno = 1.0
            except pygame.error:
                pass
        if not self.arrastre:
            vista = (t[pygame.K_KP6] - t[pygame.K_KP4], t[pygame.K_KP8] - t[pygame.K_KP2])
            if any(vista):
                self.cabeza[0] = max(-170.0, min(170.0, self.cabeza[0] + vista[0] * 120 * dt))
                self.cabeza[1] = max(-60.0, min(85.0, self.cabeza[1] + vista[1] * 90 * dt))

    def simular(self, dt):
        if self.pausa or self.inicio or self.menu_pila and self.modo == "humano":
            return
        vel = VELOCIDADES[self.i_vel] if self.modo in ("ia", "campeon") and not self.toma else 1
        self.acum += dt * vel
        pasos = 0
        tope = 4 * vel
        while self.acum >= C.PASO and pasos < tope:
            self.acum -= C.PASO
            pasos += 1
            self._reprev()
            self._paso()
        if pasos == tope:
            self.acum = 0.0

    def _paso(self):
        ep = self.ep
        f = ep.f
        if self.modo == "humano":
            ep.libre[0] = not self.autopiloto
            if self.autopiloto and self.leccion_humano:
                if self.paso_n % C.DECIDIR_CADA == 0 or self.acc_auto is None:
                    self.acc_auto = self.instructor.decidir(ep)
                acc = self.acc_auto
                m = self.mandos
                m.elev, m.alabeo, m.timon = float(acc["elev"][0]), float(acc["alabeo"][0]), float(acc["timon"][0])
                m.gases = float(acc["gases"][0])
                m.tren = bool(acc["tren"][0])
                m.flaps = m.tren
                m.aerofreno = float(acc["aerofreno"][0])
                acc = dict(acc)
                acc["flaps"] = acc["tren"]
            else:
                acc = self.mandos.acciones()
                self.mandos.bengala = False
                if self.paso_n % C.DECIDIR_CADA == 0 and self.leccion_humano in CURRICULO and not ep.terminado[0] \
                        and not ep.arranque.bloqueo()[0]:
                    self.demo.append((observar(ep)[0], B.objetivo_imitacion(acc)[0]))
        else:
            decide = self.paso_n % C.DECIDIR_CADA == 0 or self.acc_ia is None
            if decide:
                self.acc_ia = self.pilotos.decidir(ep)
            acc = self.acc_ia
            if self.toma:
                acc = self._mezclar_mando(acc, decide)
        ep.paso(acc)
        self.paso_n += 1
        self._eventos_fisicos()

    def _mezclar_mando(self, acc, decide):
        ep = self.ep
        j = self.seguido
        if ep.terminado[j] and ep.rodando()[j]:
            if not getattr(self, "aviso_rodaje", False):
                self.aviso_rodaje = True
                self.aviso("¡Misión cumplida! Sigues a los mandos: aterriza y detén el avión", 6)
        elif not ep.f.vivo[j] or ep.terminado[j]:
            self.toma = False
            self.aviso_rodaje = False
            ep.libre[j] = False
            n = len(self.demo_toma)
            if ep.exito[j] and n > 20:
                x = np.array([d[0] for d in self.demo_toma])
                y = np.array([d[1] for d in self.demo_toma])
                self.demos_listas = (x, y, ep.numero)
                self.aviso(f"¡Misión cumplida! La IA estudiará tu vuelo ({n} ejemplos)", 6)
            else:
                self.aviso(f"Se perdió el avión que pilotabas: {ep.mensaje[j]}", 5)
            self.demo_toma = []
            return acc
        ep.duracion = max(ep.duracion, ep.t + C.MARGEN_TOMA)
        m = self.mandos
        h = m.acciones()
        m.bengala = False
        acc = {k: np.array(v, copy=True) for k, v in acc.items()}
        acc.setdefault("flaps", np.array(acc["tren"], copy=True))
        for clave in ("elev", "alabeo", "timon", "gases", "freno", "aerofreno", "tren", "flaps", "bengala"):
            if clave in acc:
                acc[clave][j] = h[clave][0]
        if "fuego" in acc:
            acc["fuego"][j] = bool(m.fuego)
        acc["canon"] = np.full(ep.n, -1.0)
        acc["canon"][j] = float(m.canon)
        self.acc_ia = {k: (np.array(v, copy=True) if k in ("elev", "alabeo", "timon") else self.acc_ia[k])
                       for k, v in self.acc_ia.items()}
        for clave in ("elev", "alabeo", "timon"):
            self.acc_ia[clave][j] = h[clave][0]
        if decide and not ep.arranque.bloqueo()[j]:
            x = getattr(self.pilotos, "entradas", None)
            if x is not None:
                self.demo_toma.append((x[j].copy(), B.objetivo_imitacion(h)[0]))
        return acc

    def _eventos_fisicos(self):
        ep = self.ep
        f = ep.f
        j = self.seguido
        caidos = self.ultimo_vivo & ~f.vivo
        for i in np.flatnonzero(caidos):
            if np.linalg.norm(f.pos[i] - f.pos[j]) < 20000:
                self.part.explosion(f.pos[i], self.rng, 1.6)
        if caidos[j]:
            self.son.evento("explosion")
            self.t_caido = time.perf_counter()
        self.ultimo_vivo = f.vivo.copy()
        if ep.drones.m:
            muertos = self.drones_vivos & ~ep.drones.vivo
            for k in np.flatnonzero(muertos[j]):
                p = ep.drones.pos[j, k]
                self.part.explosion(p, self.rng, 1.6)
                for _ in range(25):
                    self.part.estela(p + self.rng.normal(0, 6, 3) - [0, self.rng.uniform(0, 80), 0], 6, 9, 0.15, 0.7)
                if np.linalg.norm(p - f.pos[j]) < 30000:
                    self.son.evento("explosion")
                quedan = int(ep.drones.vivo[j].sum())
                self.aviso("¡Enemigo derribado!" + (f" Quedan {quedan}" if ep.numero == COMBATE and quedan else ""), 3)
            en = ep.enemigos
            for k in np.flatnonzero(en.activo[j]):
                self.part.estela(en.pos[j, k], 2.4, 5.0, 0.9, 0.6)
                if not en.senuelo[j, k] and en.t[j, k] < 4.5:
                    self.part.llamita(en.pos[j, k], 1.6)
            if en.explota[j].any():
                self.part.explosion(f.pos[j] + f.R[j] @ np.array([-12.0, 0, 0]), self.rng, 1.2)
            if en.disparan[j].any():
                self.son.evento("misil")
                self.aviso("¡MISIL ENEMIGO EN EL AIRE! Q bengalas y vira fuerte", 4)
            if ep.solto_bengala[j]:
                for lado in (-1, 1):
                    p = f.pos[j] + f.R[j] @ np.array([-6.0, -0.5, 1.5 * lado])
                    v = f.vel[j] * 0.6 + f.R[j] @ np.array([0, -25.0, 30.0 * lado])
                    self.part._agregar("fuego", np.array([p]), np.array([v]), 3.0, -0.5, 3.0, (1, 0, 0, 1))
                    self.part.estela(p, 2.0, 4.0, 0.95, 0.5)
            self.drones_vivos = ep.drones.vivo.copy()
            if self.modo == "humano" and self.leccion_humano == 0 and not ep.drones.vivo[0, 0]:
                if not hasattr(self, "t_respawn"):
                    self.t_respawn = ep.t + 20
                elif ep.t > self.t_respawn:
                    del self.t_respawn
                    d = ep.drones
                    ang = self.rng.uniform(0, 2 * math.pi)
                    d.pos[0, 0] = f.pos[0] + [math.sin(ang) * 15000, 0, -math.cos(ang) * 15000]
                    d.pos[0, 0, 1] = self.rng.uniform(2500, 5000)
                    d.vivo[0, 0] = True
                    self.drones_vivos = d.vivo.copy()
                    ep.i[0] = 0
                    ep.terminado[0] = False
                    self.aviso("Nuevo dron blanco en el radar")
            act = ep.misiles.activo[j]
            for k in np.flatnonzero(act):
                self.part.estela(ep.misiles.pos[j, k], 2.2, 5.0, 0.9, 0.6)
                self.part.llamita(ep.misiles.pos[j, k] - ep.misiles.vel[j, k] * 0.01, 1.4)
        if ep.lanzo[j]:
            self.son.evento("misil")
        nuevo_toque = f.tocando & ~self.tocaba
        if nuevo_toque[j] and abs(f.toque_vy[j]) > 0.4 and np.linalg.norm(f.vel[j]) > 30:
            self.son.evento("toque")
            self.son.evento("chirrido")
            for k in (1, 2):
                p = f.pos[j] + f.R[j] @ (np.array([-0.65, -2.1, 1.38 * (1 if k == 2 else -1)]))
                for _ in range(6):
                    self.part.estela(p + self.rng.normal(0, 0.4, 3), 1.5, 2.5, 0.85, 0.5)
        self.tocaba = f.tocando.copy()
        if f.vivo[j] and f.pos[j, 1] > 9000 and self.paso_n % 2 == 0:
            for lado in (-1, 1):
                self.part.estela(f.pos[j] + f.R[j] @ np.array([-11.0, 0.1, 0.64 * lado]), 1.8, 12.0, 0.95, 0.35)

    def estado_seguido(self, alfa):
        ep = self.ep
        f = ep.f
        j = self.seguido
        p0, q0 = self.prev
        pos = p0[j] * (1 - alfa) + f.pos[j] * alfa
        q = _nlerp(q0[j], f.q[j], alfa)
        R = _mat_q(q)
        return pos, R

    def camara(self, pos, R):
        f = self.ep.f
        j = self.seguido
        ojo = MD.OJO.copy()
        sacudida = np.zeros(3)
        if f.en_suelo[j] and f.vivo[j]:
            v = np.linalg.norm(f.vel[j])
            sacudida += self.rng.normal(0, 1, 3) * min(0.012, v * 0.00012)
        buffet = max(0.0, (abs(f.alfa[j]) - 0.33) * 3) * min(1.0, f.qbar[j] / 3000)
        sacudida += self.rng.normal(0, 1, 3) * 0.006 * buffet
        ojo[1] -= min(0.05, max(0.0, f.carga[j] - 1) * 0.006)
        if not f.vivo[j]:
            rumbo = self.ep.f.euler()[0][j]
            cam = pos + np.array([0.0, 60.0, 0.0]) - 140 * np.array([math.sin(rumbo), 0, -math.cos(rumbo)])
            adelante = pos - cam
            adelante /= np.linalg.norm(adelante)
            der = np.cross(adelante, [0, 1.0, 0])
            der /= np.linalg.norm(der)
            return cam, adelante, np.cross(der, adelante), 0.0
        cam = pos + R @ (ojo + sacudida)
        suelo = float(T.superficie(cam[0], cam[2])) + 1.2
        if cam[1] < suelo:
            cam = cam.copy()
            cam[1] = suelo
        y, p = math.radians(self.cabeza[0]), math.radians(self.cabeza[1])
        d = np.array([math.cos(p) * math.cos(y), math.sin(p), math.cos(p) * math.sin(y)])
        adelante = R @ d
        der = np.cross(adelante, R[:, 1])
        if np.linalg.norm(der) < 1e-3:
            der = R[:, 2]
        der /= np.linalg.norm(der)
        arriba = np.cross(der, adelante)
        return cam, adelante, arriba, buffet

    def escena(self, pos, R, cam, adelante, arriba):
        ep = self.ep
        f = ep.f
        j = self.seguido
        otros = []
        if ep.n > 1:
            dist = np.linalg.norm(f.pos - cam, axis=1)
            idx = np.flatnonzero(f.vivo & (np.arange(ep.n) != j) & (dist > 25) & (dist < 12000))
            idx = idx[np.argsort(dist[idx])][:120]
            p0, q0 = self.prev
            for i in idx:
                a = self.alfa_interp
                qi = _nlerp(q0[i], f.q[i], a)
                otros.append({"pos": p0[i] * (1 - a) + f.pos[i] * a, "R": _mat_q(qi), "tren": f.tren[i],
                              "pq": f.pq[i], "alfa": 0.5 if dist[i] > 60 else 0.3,
                              "tinte": 0.35 if ep.exito[i] else 0.0})
        drones = []
        if ep.drones.m:
            for k in range(ep.drones.m):
                if not ep.drones.vivo[j, k]:
                    continue
                hostil = ep.drones.hostil[j, k]
                v = ep.drones.vel[j, k]
                fw = v / (np.linalg.norm(v) + 1e-6)
                up = np.array([0, 1.0, 0])
                rt = np.cross(fw, up)
                rt /= np.linalg.norm(rt) + 1e-9
                up = np.cross(rt, fw)
                ab = ep.drones.alabeo[j, k]
                up2 = up * math.cos(ab) - rt * math.sin(ab)
                rt2 = np.cross(fw, up2)
                Rd = np.stack([fw, up2, rt2], 1)
                if hostil:
                    otros.append({"pos": ep.drones.pos[j, k], "R": Rd, "tren": 0.0, "pq": 0.45, "alfa": 1.0,
                                  "tinte": -0.45})
                else:
                    drones.append({"pos": ep.drones.pos[j, k], "R": Rd})
        misiles = []
        en = ep.enemigos
        for k in np.flatnonzero(en.activo[j]):
            v = en.vel[j, k]
            fw = v / (np.linalg.norm(v) + 1e-6)
            rt = np.cross(fw, [0, 1.0, 0])
            rt /= np.linalg.norm(rt) + 1e-9
            misiles.append({"pos": en.pos[j, k], "R": np.stack([fw, np.cross(rt, fw), rt], 1)})
        for k in np.flatnonzero(ep.misiles.activo[j]):
            v = ep.misiles.vel[j, k]
            fw = v / (np.linalg.norm(v) + 1e-6)
            rt = np.cross(fw, [0, 1.0, 0])
            rt /= np.linalg.norm(rt) + 1e-9
            misiles.append({"pos": ep.misiles.pos[j, k], "R": np.stack([fw, np.cross(rt, fw), rt], 1)})
        puntos = []
        noche = self.r.cielo_cfg["noche"] > 0.1 or self.r.cielo_cfg["luces"] > 0.8
        if noche:
            parpadeo = int(self.t * 1.2) % 2 == 0
            for o in otros[:60]:
                Ro = o["R"]
                puntos.append((*(o["pos"] + Ro @ np.array([-3.6, 0, -6.5])), 1.0, 0.1, 0.05, 0))
                puntos.append((*(o["pos"] + Ro @ np.array([-3.6, 0, 6.5])), 0.1, 1.0, 0.2, 0))
                if parpadeo:
                    puntos.append((*(o["pos"] + Ro @ np.array([-8.5, 3.6, 1.6])), 1.4, 1.4, 1.4, 0))
            puntos.append((*(pos + R @ np.array([-3.6, 0.05, -6.5])), 1.0, 0.1, 0.05, 0))
            puntos.append((*(pos + R @ np.array([-3.6, 0.05, 6.5])), 0.1, 1.0, 0.2, 0))
        for mi in misiles:
            puntos.append((*mi["pos"], 1.6, 1.3, 0.8, 0))
        hs, fs = self.part.datos()
        if len(self.balas_t):
            fs = np.vstack([fs, self.trazadoras(cam)])
        mando = self.mandos if self.modo == "humano" else None
        if mando is None:
            a = self.acc_ia
            mandos = {k: float(a[k][j]) for k in ("elev", "alabeo", "timon")} if a is not None else {}
        else:
            mandos = {"elev": mando.elev, "alabeo": mando.alabeo, "timon": mando.timon}
        propio = {"pos": pos, "R": R, "tren": f.tren[j], "flaps": f.flaps[j], "aerofreno": f.aerofreno[j],
                  "mandos": mandos, "misiles": int(ep.misiles_quedan[j]), "gases": float(f.entrada["gases"][j])}
        return {"t": self.t, "cam": cam, "adelante": adelante, "arriba": arriba, "fov": self.fov,
                "propio": propio if f.vivo[j] or self.t_caido_rel() < 0.15 else None, "otros": otros,
                "drones": drones, "misiles": misiles, "puntos": puntos, "humo": hs, "fuego": fs}

    def trazadoras(self, cam):
        u = self.balas_v / np.linalg.norm(self.balas_v, axis=1, keepdims=True)
        brillo = np.clip(1.2 - self.balas_t * 0.35, 0.4, 1.0)
        filas = []
        for c, paso in enumerate(np.linspace(0, 24, 7)):
            p = self.balas_p - u * paso
            d = np.linalg.norm(p - cam, axis=1)
            a = brillo * (1 - c * 0.12)
            filas.append(np.c_[p, np.maximum(0.9, d * 0.0035), np.full(len(p), 1.0), np.full(len(p), 0.78),
                               np.full(len(p), 0.32), a])
        return np.vstack(filas).astype("f4")

    def mover_balas(self, dt):
        if dt <= 0 or self.pausa:
            return
        ep = self.ep
        j = self.seguido
        if ep is not None and j < ep.n and ep.disparando[j] and ep.f.vivo[j]:
            self.acum_bala += dt * C.TRAZADORAS_POR_S
            k = int(self.acum_bala)
            self.acum_bala -= k
            if k:
                f = ep.f
                R = f.R[j]
                boca = f.pos[j] + R @ np.array([5.5, 0.5, 1.5])
                fase = self.rng.uniform(0, 1, k)
                disp = self.rng.normal(0, 0.0035, (k, 3))
                v = f.vel[j] + (R[:, 0] + disp) * C.VEL_BALA
                self.balas_p = np.vstack([self.balas_p, boca + v * (fase * dt)[:, None]])
                self.balas_v = np.vstack([self.balas_v, v])
                self.balas_t = np.concatenate([self.balas_t, fase * dt])
        if len(self.balas_t):
            self.balas_v[:, 1] -= C.GRAVEDAD * dt
            self.balas_p += self.balas_v * dt
            self.balas_t += dt
            vive = (self.balas_t < 2.2) & (self.balas_p[:, 1] > T.superficie(self.balas_p[:, 0], self.balas_p[:, 2]))
            self.balas_p, self.balas_v, self.balas_t = self.balas_p[vive], self.balas_v[vive], self.balas_t[vive]

    def t_caido_rel(self):
        return 0 if getattr(self, "t_caido", None) is None else time.perf_counter() - self.t_caido

    def datos_vuelo(self, pos, R):
        ep = self.ep
        f = ep.f
        j = self.seguido
        rumbo, cab, alab = (v[j] for v in f.euler())
        p = ep.punto_obj()[j]
        rel = p - f.pos[j]
        tipos = ep._tipos()
        o = ep.objetivo(ep.i[j])
        vs = f.vel[j, 1]
        agl = float(f.agl()[j])
        e = {"t": self.t, "R": R, "pos": pos, "cabeceo": cab, "alabeo": alab, "rumbo": rumbo,
             "vel": f.v_aire[j], "vel_vec": f.vel[j], "alt": f.pos[j, 1], "agl": agl, "vs": vs, "mach": f.mach[j],
             "g": f.carga[j], "gmax": f.g_max[j], "alfa": f.alfa[j], "gases": f.entrada["gases"][j],
             "tren": f.tren[j], "cmd_tren": f.cmd_tren[j] > 0.5, "flaps": f.flaps[j], "aerofreno": f.aerofreno[j],
             "freno": f.entrada["freno"][j], "rpm": float(f.n2[j].mean()), "rpm_i": float(f.n2[j, 0]),
             "rpm_d": float(f.n2[j, 1]), "energia": bool(f.generadores[j] and f.avionica[j]),
             "pq": f.pq[j], "comb": f.combustible[j], "flujo": 0.25 + 1.55 * f.motor[j] + 10.5 * f.pq[j],
             "dano_tren": f.dano_tren[j], "misiles": int(ep.misiles_quedan[j]), "municion": int(ep.municion[j])}
        e["perdida"] = abs(f.alfa[j]) > 0.45 and not f.en_suelo[j] and f.vivo[j]
        e["tierra"] = vs < -5 and agl / max(-vs, 1) < 7 and not (f.tren[j] > 0.9 and abs(vs) < 12) and f.vivo[j]
        e["aviso_tren"] = agl < 300 and vs < -2 and f.tren[j] < 0.5 and f.v_aire[j] < 120
        e["bingo"] = f.combustible[j] < 700
        e["sobre_g"] = bool(f.sobre_g[j])
        e["solucion_canon"] = bool(ep.solucion_canon[j])
        e["fatiga"] = float(f.fatiga[j])
        e["precaucion"] = e["bingo"] or e["aviso_tren"] or f.fatiga[j] > 0
        if not ep.terminado[j]:
            e["rumbo_obj"] = math.atan2(rel[0], -rel[2]) % (2 * math.pi)
            e["dist_obj"] = float(np.linalg.norm(rel))
            e["obj_pos"] = p if tipos[j] in (PUNTO, DESPEGUE, TOQUE) else None
        a = o["pista"]
        if tipos[j] in (TOQUE,) or (tipos[j] == PUNTO and o["tren"] is True):
            s, l = a.local(f.pos[j, 0], f.pos[j, 2])
            if s < 200:
                gs_alt = a.elev + 15 + max(-s, 0) * PENDIENTE
                e["ils"] = (-l / max(60.0, -s * 0.03), (f.pos[j, 1] - gs_alt) / max(15.0, -s * 0.012))
        ruta = [f.pos[j]] + [ob["p"] if ob["p"] is not None else ob["pista"].mundo(ob["pista"].largo * 0.3, 0)
                             for ob in ep.obj[ep.i[j]:]]
        e["ruta"] = ruta
        blancos = []
        if ep.drones.m and hasattr(ep, "dist_blanco"):
            for k in range(ep.drones.m):
                if not ep.drones.vivo[j, k]:
                    continue
                rb = ep.drones.pos[j, k] - f.pos[j]
                bl = R.T @ rb
                az = math.atan2(bl[2], bl[0])
                blancos.append((az, float(np.linalg.norm(rb)), bool(ep.fijado_radar[j]) and k == ep.blanco_idx[j]))
            e["drones_pos"] = [ep.drones.pos[j, k] for k in range(ep.drones.m) if ep.drones.vivo[j, k]]
            bi = int(ep.blanco_idx[j])
            if ep.drones.vivo[j, bi]:
                fij_ir, fij_r = bool(ep.fijado_ir[j]), bool(ep.fijado_radar[j])
                d = float(ep.dist_blanco[j])
                arma = "AIM-9 IR" if fij_ir else ("AIM-120 RADAR" if fij_r else "BUSCANDO")
                if d < 1500:
                    arma = "CAÑÓN"
                e["blanco"] = {"pos": ep.drones.pos[j, bi], "dist": d, "fijado_ir": fij_ir,
                               "disparo": (fij_ir or fij_r) and 800 < d < 25000 and ep.misiles_quedan[j] > 0 and not f.en_suelo[j],
                               "arma": f"{arma} · {int(ep.misiles_quedan[j])} MSL"}
        e["blancos"] = blancos
        e["misil_enemigo"] = bool(ep.enemigos.alerta[j])
        e["fijado_enemigo"] = bool(ep.enemigos.fijado[j])
        e["impactos"] = int(ep.enemigos.impactos[j])
        e["bengalas"] = int(ep.bengalas[j])
        return e

    def dibujar_tarjeta(self, s, x, y, w, h):
        pygame.draw.rect(s, TARJETA, (x, y, w, h), border_radius=10)
        pygame.draw.rect(s, BORDE + (255,), (x, y, w, h), 1, border_radius=10)

    def panel_ia(self, s):
        e = self.e
        x, y, w = 14, 14, int(420 * self.k)
        hist = e.historial[-120:]
        h = int((326 if hist else 200) * self.k)
        self.dibujar_tarjeta(s, x, y, w, h)
        n = self.ep.numero
        tit = "IA EN VIVO" if self.modo == "ia" else "CAMPEÓN"
        _texto(s, self.f_peq, tit, ORO, (x + 14, y + int(10 * self.k)))
        if self.modo == "ia":
            _texto(s, self.f_gr, f"Generación {self.gen_vista}", TEXTO, (x + 14, y + int(28 * self.k)))
        else:
            info = self.info_campeon
            _texto(s, self.f_gr, ("IA actual gen. " if info.get("actual") else "Campeón gen. ") +
                   str(info["generacion"]), TEXTO, (x + 14, y + int(28 * self.k)))
        _texto(s, self.f_med, f"Misión {n} · {nombre(n)}", AZUL, (x + 14, y + int(58 * self.k)))
        ep = self.ep
        j = self.seguido
        quien = ("centro" if j == 0 else ("élite" if j == 1 else f"mutante {j}")) if self.modo == "ia" else "campeón"
        estado = ep.mensaje[j] if ep.terminado[j] else f"objetivo {min(ep.i[j] + 1, ep.k)}/{ep.k}"
        _texto(s, self.f_med, f"Cabina de: {quien} · {estado}", TEXTO, (x + 14, y + int(82 * self.k)))
        prog = ep.progreso()
        vivos = int((~ep.terminado).sum())
        _texto(s, self.f_peq, f"en vuelo {vivos}/{ep.n} · logrado {int(ep.exito.sum())} · mejor {100 * prog.max():.0f}%",
               TENUE, (x + 14, y + int(106 * self.k)))
        gpm = 0.0
        if len(self.gen_t) > 1:
            gpm = 60 * (len(self.gen_t) - 1) / max(self.gen_t[-1] - self.gen_t[0], 1e-6)
        _texto(s, self.f_peq, f"Entrenando gen. {e.generacion} · misión {e.leccion_actual} · {gpm:.1f} gen/min · "
                              f"x{VELOCIDADES[self.i_vel]}", TENUE, (x + 14, y + int(126 * self.k)))
        if self.toma:
            _texto(s, self.f_med_b, "TÚ PILOTAS · J devuelve los mandos a la IA", ORO, (x + 14, y + h + int(8 * self.k)))
        else:
            _texto(s, self.f_peq, "J toma los mandos de este avión", TENUE, (x + 14, y + h + int(8 * self.k)))
        if hist:
            gx, gy, gw, gh = x + 14, y + int(150 * self.k), w - 28, int(110 * self.k)
            pygame.draw.rect(s, (14, 16, 20, 220), (gx, gy, gw, gh), border_radius=6)
            for k in range(1, 4):
                pygame.draw.line(s, (40, 44, 52), (gx, gy + gh * k / 4), (gx + gw, gy + gh * k / 4))
            pts_m = [(gx + gw * i / max(len(hist) - 1, 1), gy + gh - gh * r["mejor_progreso"] / 100)
                     for i, r in enumerate(hist)]
            pts_p = [(gx + gw * i / max(len(hist) - 1, 1), gy + gh - gh * r["promedio_progreso"] / 100)
                     for i, r in enumerate(hist)]
            if len(pts_m) > 1:
                pygame.draw.polygon(s, (245, 180, 0, 50), pts_m + [(gx + gw, gy + gh), (gx, gy + gh)])
                pygame.draw.lines(s, ORO, False, pts_m, 2)
                pygame.draw.lines(s, AZUL, False, pts_p, 2)
            for i, r in enumerate(hist):
                if r["subio"]:
                    xx = gx + gw * i / max(len(hist) - 1, 1)
                    pygame.draw.line(s, VERDE, (xx, gy), (xx, gy + gh), 1)
            u = hist[-1]
            _texto(s, self.f_peq, f"mejor {u['mejor_progreso']:.0f}%  prom {u['promedio_progreso']:.0f}%  "
                                  f"superaron {u['superaron_pct']:.0f}%  racha {u['racha']}/{C.RACHA_PARA_SUBIR}",
                   TENUE, (gx, gy + gh + 8))
        _texto(s, self.f_peq, "N sig. · L líder · clic marca · J pilotar · [ ] vel. · K clase · Esc", TENUE,
               (x + 14, y + h - int(22 * self.k)))

    def panel_humano(self, s):
        ep = self.ep
        n = self.leccion_humano
        x, y, w, h = 14, 14, int(400 * self.k), int(96 * self.k)
        self.dibujar_tarjeta(s, x, y, w, h)
        if n == COMBATE:
            _texto(s, self.f_peq, "COMBATE AÉREO", ROJO, (x + 14, y + int(10 * self.k)))
            _texto(s, self.f_med_b, f"Enemigos derribados {int(ep.bajas[0])}/{ep.drones.m}", TEXTO, (x + 14, y + int(28 * self.k)))
            estado = ep.mensaje[0] if ep.terminado[0] else \
                f"misiles {int(ep.misiles_quedan[0])} · bengalas {int(ep.bengalas[0])} · " \
                f"impactos recibidos {int(ep.enemigos.impactos[0])}/5"
        elif n:
            _texto(s, self.f_peq, f"MISIÓN {n}", ORO, (x + 14, y + int(10 * self.k)))
            _texto(s, self.f_med_b, nombre(n), TEXTO, (x + 14, y + int(28 * self.k)))
            estado = ep.mensaje[0] if ep.terminado[0] else f"objetivo {min(ep.i[0] + 1, ep.k)}/{ep.k} · " \
                                                           f"{100 * ep.progreso()[0]:.0f}% · {ep.t:.0f}/{ep.duracion:.0f} s"
        else:
            _texto(s, self.f_peq, "VUELO LIBRE", ORO, (x + 14, y + int(10 * self.k)))
            _texto(s, self.f_med_b, "Base Aérea Halcón · pista 34", TEXTO, (x + 14, y + int(28 * self.k)))
            estado = f"derribos {int(ep.bajas[0])} · " + ("blanco en zona" if ep.drones.vivo[0, 0] else "esperando blanco")
        _texto(s, self.f_med, estado, AZUL, (x + 14, y + int(52 * self.k)))
        extra = "INSTRUCTOR A LOS MANDOS · I para retomar" if self.autopiloto else "F1 controles · I instructor · R reiniciar"
        _texto(s, self.f_peq, extra, ORO if self.autopiloto else TENUE, (x + 14, y + int(74 * self.k)))
        if self.demo_lista is not None:
            self.dibujar_tarjeta(s, self.W // 2 - 260, self.H - 120, 520, 56)
            _texto(s, self.f_med_b, "¡Lección completada! Pulsa T para enseñarle este vuelo a la IA", ORO,
                   (self.W // 2, self.H - 92), True)

    def panel_ayuda(self, s):
        lineas = [("Mandos", ""), ("↑ / ↓", "empujar / tirar de la palanca"), ("← / →", "alabeo"),
                  ("A / D  (Z / X)", "timón y rueda de nariz"), ("W / S  (RePág / AvPág)", "gases"),
                  ("Shift + W", "pasar el tope al postquemador (E = máximo)"), ("G", "tren de aterrizaje"),
                  ("F", "flaps"), ("V", "aerofreno"), ("B (mantener)", "frenos de rueda"),
                  ("Espacio", "misil (IR o radar según blanco)"), ("Ctrl / C", "cañón"),
                  ("Q", "bengalas y señuelos contra misiles"),
                  ("Clic der. + ratón, teclado num.", "mirar alrededor en la cabina"),
                  ("Rueda / clic central / Inicio", "zoom / centrar la vista"), ("I", "instructor a los mandos"),
                  ("R", "reiniciar · P pausa · H HUD · M sonido"), ("F5", "guardar la IA · Esc menú"),
                  ("F9", "grabar video de la pantalla"), ("F2", "panel de entrenamiento y sensores"),
                  ("1 – 0  (Shift+4/5)", "interruptores del arranque en frío"),
                  ("Ventana", "redimensionable: arrastra el borde")]
        fila = int(24 * self.k)
        w, h = int(600 * self.k), 40 + fila * len(lineas)
        x, y = self.W // 2 - w // 2, max(10, self.H // 2 - h // 2)
        self.dibujar_tarjeta(s, x, y, w, h)
        for k, (a, b) in enumerate(lineas):
            if not b:
                _texto(s, self.f_gr, a, ORO, (x + 20, y + 14))
                continue
            _texto(s, self.f_med_b, a, TEXTO, (x + 20, y + 20 + fila * k))
            _texto(s, self.f_med, b, TENUE, (x + int(290 * self.k), y + 20 + fila * k))

    def dibujar_menu(self, s):
        ops = self.opciones_menu()
        fila = max(24, min(int(38 * self.k), (self.H - 200) // max(len(ops), 1)))
        w = int(640 * self.k)
        h = 140 + fila * len(ops)
        x, y = self.W // 2 - w // 2, max(20, self.H // 2 - h // 2)
        velo = pygame.Surface((self.W, self.H), pygame.SRCALPHA)
        velo.fill((8, 10, 14, 120))
        s.blit(velo, (0, 0))
        self.dibujar_tarjeta(s, x, y, w, h)
        _texto(s, self.f_tit, "F-15 EAGLE", ORO, (x + 28, y + 20))
        sub = {"principal": "Simulador de vuelo evolutivo · todo desde la cabina",
               "sub_misiones": "Elige una misión para pilotar (config_misiones/*.json)",
               "sub_campeon": "Ver el campeón de cada misión (o la IA actual)",
               "sub_curriculo": "Cómo elige la IA qué misión entrenar", "sub_fija": "Misión que entrenará la IA",
               "confirmar": "¿Borrar todo lo que la IA ha aprendido?"}.get(self.menu_pila[-1], "")
        _texto(s, self.f_med, sub, TENUE, (x + 30, y + 60))
        self.rects_menu = []
        for k, (txt, _) in enumerate(ops):
            r = pygame.Rect(x + 20, y + 98 + fila * k, w - 40, fila - 6)
            self.rects_menu.append(r)
            if k == self.menu_sel:
                pygame.draw.rect(s, (245, 180, 0, 40), r, border_radius=6)
                pygame.draw.rect(s, ORO + (255,), (r.x, r.y + 6, 3, r.h - 12))
            _texto(s, self.f_med_b if k == self.menu_sel else self.f_med, txt,
                   TEXTO if k == self.menu_sel else (200, 204, 212),
                   (r.x + 16, r.centery - self.f_med.get_height() // 2))
        pie = f"IA: generación {self.e.generacion} · misión {self.e.leccion_actual} · {self.e.modo} · " \
              f"{'empieza al elegir' if self.inicio and self.entrenar else 'entrenando' if self.entrenar else 'en pausa'}"
        _texto(s, self.f_peq, pie, TENUE, (x + 30, y + h - 26))

    def ejecutar(self):
        self.salir = False
        self.r.configurar(HORAS[self.hora_i])
        t_prev = time.perf_counter()
        while not self.salir:
            ahora = time.perf_counter()
            dt = min(0.1, ahora - t_prev)
            t_prev = ahora
            self.t += dt
            self.eventos()
            self.revisar_entrenamiento()
            if self.modo == "humano" and not self.autopiloto or self.toma:
                self.leer_mandos(dt)
            elif self.modo in ("ia", "campeon") and not self.arrastre:
                t = pygame.key.get_pressed()
                vista = (t[pygame.K_KP6] - t[pygame.K_KP4], t[pygame.K_KP8] - t[pygame.K_KP2])
                if any(vista):
                    self.cabeza[0] = max(-170.0, min(170.0, self.cabeza[0] + vista[0] * 120 * dt))
                    self.cabeza[1] = max(-60.0, min(85.0, self.cabeza[1] + vista[1] * 90 * dt))
            self.simular(dt)
            if not self.pausa:
                self.part.paso(dt * (VELOCIDADES[self.i_vel] if self.modo != "humano" else 1))
                self.mover_balas(dt * (VELOCIDADES[self.i_vel] if self.modo != "humano" else 1))
            self._mantener()
            self.alfa_interp = min(1.0, self.acum / C.PASO)
            pos, R = self.estado_seguido(self.alfa_interp)
            cam, adelante, arriba, buffet = self.camara(pos, R)
            e = self.datos_vuelo(pos, R)
            self.t_panel -= dt
            if self.t_panel <= 0:
                self.t_panel = 0.08
                self.r.subir_panel(self.panel.dibujar(e))
            esc = self.escena(pos, R, cam, adelante, arriba)
            esc["niebla"] = 1.0
            self.ctx.screen.use()
            self.ctx.clear(0, 0, 0)
            self.r.dibujar(esc)
            s = self.capa
            s.fill((0, 0, 0, 0))
            f = self.ep.f
            j = self.seguido
            pr = Proyector(cam, adelante, arriba, self.fov, self.W, self.H)
            if self.mostrar_hud and f.vivo[j] and e["energia"]:
                self.hud.dibujar(s, pr, e)
            if self.tablero_on and f.vivo[j] and not self.menu_pila:
                self.tablero.rayos(s, pr, self.ep, j)
            g = f.carga[j]
            if not hasattr(self, "g_acum"):
                self.g_acum = 0.0
            exceso = max(0.0, g - 7.0) / 3.0 + max(0.0, -g - 2.5) / 2.0
            self.g_acum = max(0.0, min(1.0, self.g_acum + (exceso * 0.6 - 0.25) * dt))
            vineta(s, g, self.r.dentro_nube(cam), self.g_acum)
            if not f.vivo[j]:
                caja = pygame.Rect(self.W // 2 - 240, self.H // 2 - 40, 480, 80)
                self.dibujar_tarjeta(s, *caja)
                _texto(s, self.f_gr, self.ep.mensaje[j].upper() or "DERRIBADO", ROJO, (caja.centerx, caja.y + 26), True)
                _texto(s, self.f_med, "R para reintentar · Esc menú" if self.modo == "humano" else
                       "la cabina pasa al líder en un momento", TENUE, (caja.centerx, caja.y + 56), True)
            self.rects_arranque = []
            self.rects_indiv = []
            if self.tarjeta and self.modo == "ia" and not self.menu_pila:
                self.marcar_individuos(s, pr)
            if self.tarjeta:
                if self.modo in ("ia", "campeon"):
                    self.panel_ia(s)
                elif self.modo == "humano":
                    self.panel_humano(s)
                ar = self.ep.arranque
                centro = self.W // 2
                if ar.activo and ar.estado[j] < VUELO and f.vivo[j]:
                    rects = self.tablero.arranque(s, self.ep, j, 14, self.H - 14, self.modo == "humano"
                                                  and not self.autopiloto)
                    if self.modo == "humano" and not self.autopiloto:
                        self.rects_arranque = rects
                    centro = max(centro, 14 + int(440 * self.k) + int(10 * 76 * self.k) // 2 + 8)
                acc = self.acc_ia if self.modo != "humano" else self.mandos.acciones()
                self.tablero.mandos(s, self.ep, j, acc, centro, self.H - int(48 * self.k))
            if self.tablero_on and self.modo in ("ia", "campeon") and not self.menu_pila:
                w_t = int(400 * self.k)
                self.tablero.rl(s, self, self.W - w_t - 14, 14, w_t, self.H - 84)
            txt, hasta = self.mensaje
            if txt and time.perf_counter() < hasta:
                img = self.f_med_b.render(txt, True, TEXTO)
                caja = img.get_rect(midtop=(self.W // 2, 16)).inflate(30, 16)
                if self.tablero_on and self.modo in ("ia", "campeon"):
                    caja.centerx = (14 + int(420 * self.k) + self.W - int(400 * self.k) - 14) // 2
                self.dibujar_tarjeta(s, *caja)
                s.blit(img, img.get_rect(center=caja.center))
            if self.pausa:
                _texto(s, self.f_tit, "PAUSA", ORO, (self.W // 2, self.H // 2 - 120), True)
            if self.ayuda:
                self.panel_ayuda(s)
            if self.menu_pila:
                self.dibujar_menu(s)
            _texto(s, self.f_peq, f"{self.reloj.get_fps():.0f} fps", (110, 115, 125), (self.W - 250, self.H - 42))
            self.boton_grabar(s)
            self.r.hud(s)
            self.capturar_video()
            self.son.actualizar({"rpm": e["rpm"] if f.vivo[j] else 0, "pq": e["pq"] if f.vivo[j] else 0,
                                 "vel": e["vel"], "aerofreno": e["aerofreno"], "buffet": buffet,
                                 "suelo": bool(f.en_suelo[j]), "tono_ir": e.get("blanco", {}).get("fijado_ir", False)
                                 if e.get("blanco") else False, "cañon": bool(self.ep.disparando[j]),
                                 "alarma": (e["perdida"] or e["tierra"] or e["aviso_tren"] or e["misil_enemigo"])
                                 and f.vivo[j]}, dt)
            pygame.display.flip()
            self.reloj.tick(120)
        self.cerrar()

    def _mantener(self):
        ep = self.ep
        if self.modo == "ia":
            j = self.seguido
            if ep.terminado[j] and not ep.rodando()[j] and getattr(self, "t_fin_seg", None) is None:
                self.t_fin_seg = time.perf_counter()
            if getattr(self, "t_fin_seg", None) is not None and time.perf_counter() - self.t_fin_seg > 3.0:
                self.t_fin_seg = None
                if not ep.acabado:
                    vivos = np.flatnonzero(~ep.terminado)
                    prog = ep.progreso()[vivos]
                    self.seguido = int(vivos[np.argmax(prog)])
                    self._reprev()
                    self.t_caido = None
            if ep.reposo:
                if not hasattr(self, "t_acabo"):
                    self.t_acabo = time.perf_counter()
                elif time.perf_counter() - self.t_acabo > 2.5:
                    del self.t_acabo
                    self.t_fin_seg = None
                    self.iniciar_ia()
        elif self.modo == "campeon":
            if ep.reposo:
                if not hasattr(self, "t_acabo"):
                    self.t_acabo = time.perf_counter()
                elif time.perf_counter() - self.t_acabo > 4.0:
                    del self.t_acabo
                    self.iniciar_campeon(self.leccion_campeon)
        elif self.modo == "humano":
            if ep.terminado[0] and self.leccion_humano and not getattr(self, "fin_anotado", False):
                self.fin_anotado = True
                if ep.exito[0] and not self.autopiloto and len(self.demo) > 20:
                    x = np.array([d[0] for d in self.demo])
                    y = np.array([d[1] for d in self.demo])
                    self.demo_lista = (x, y)
                self.aviso(ep.mensaje[0].capitalize() + (" — ¡bien volado!" if ep.exito[0] else ""), 6)
            if not ep.terminado[0]:
                self.fin_anotado = False

    def cerrar(self):
        self.grab.detener(esperar=True)
        try:
            self.e.guardar()
        except Exception:
            pass
        self.son.callar()
        self.pool.terminate()
        pygame.quit()
