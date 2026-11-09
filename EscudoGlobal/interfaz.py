import copy
import math
import os
import queue
import threading
import time
from collections import OrderedDict

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import numpy as np
import pygame

import cerebro as B
import config as C
import geo as G
import misiones as MS
import mundo as M
from doctrina import ControladorManual, Doctrina
from evolucion import Entrenador, HiloEntrenamiento
from grabador import CARPETA_GRABACIONES, Grabador
import satelites as SAT
from simulacion import Episodio

FONDO = (14, 16, 20)
TARJETA = (22, 25, 32)
TARJETA2 = (28, 32, 41)
BORDE = (38, 43, 54)
REJILLA = (35, 40, 53)
TEXTO = (232, 235, 241)
TENUE = (138, 147, 166)
SUTIL = (90, 98, 117)
ACENTO = (245, 180, 0)
AZUL = (78, 164, 255)
VERDE = (56, 211, 159)
ROJO = (255, 95, 95)
MORADO = (180, 140, 255)
NARANJA = (255, 160, 77)
CIAN = (61, 214, 245)
COLOR_LOG = {"rojo": ROJO, "ambar": NARANJA, "verde": VERDE, "cian": CIAN, "gris": SUTIL, "blanco": TEXTO}
ESTADOS = {"operativa": ("OPERATIVO", VERDE), "desplegando": ("REDESPLEGANDO", NARANJA),
           "destruida": ("FUERA DE COMBATE", ROJO)}
COLOR_TIPO = {"corto": (255, 95, 95), "medio": (255, 70, 150), "intermedio": (255, 150, 60), "icbm": (255, 50, 50),
              "planeador": (200, 120, 255)}
COLOR_CAPA = {"impulso": (255, 205, 80), "exo": (130, 160, 255), "alta": (61, 214, 245), "baja": (56, 211, 159)}
COLOR_ACTIVO = {"buque": COLOR_CAPA["impulso"], "exo": COLOR_CAPA["exo"], "alta": COLOR_CAPA["alta"],
                "terminal": COLOR_CAPA["baja"], "radar": (225, 225, 235)}
GRIS_SENUELO = (150, 150, 160)
AMARILLO_NUC = (255, 225, 60)
AZUL_CONTRA = (90, 170, 255)
PALETA_BANDOS = [CIAN, (255, 95, 95), VERDE, MORADO, NARANJA, AZUL, (255, 120, 200), ACENTO, (140, 230, 140),
                 (200, 200, 255)]
CIUDADES_RAPIDAS = ["Ciudad de México", "Pachuca", "Guadalajara", "Monterrey", "Los Ángeles", "Nueva York",
                    "Washington", "Londres", "París", "Berlín", "Madrid", "Tokio", "Seúl", "Moscú"]
MODOS = [("entrenar", "Entrenar IA"), ("campeon", "Campeón"), ("jugar", "Jugar tú"), ("comandante", "Comandante")]
VELOCIDADES = [1, 5, 10, 30, 60]
Y_MAX = M.merc_y(80.0)


def _fuente(archivo, tam):
    ruta = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts", archivo)
    try:
        return pygame.font.Font(ruta, max(8, tam))
    except (OSError, FileNotFoundError):
        return pygame.font.SysFont("segoeui", max(8, tam))


def mmss(t):
    t = max(0, int(t))
    if t >= 3600:
        return f"{t // 3600}:{t % 3600 // 60:02d}:{t % 60:02d}"
    return f"{t // 60:02d}:{t % 60:02d}"


def mezclar(a, b, t):
    return tuple(int(x + (y - x) * t) for x, y in zip(a, b))


def _limitar(p):
    return (max(-20000, min(20000, p[0])), max(-20000, min(20000, p[1])))


class Boton:
    def __init__(self, texto, accion, color=None, primario=False):
        self.texto, self.accion, self.color, self.primario = texto, accion, color, primario
        self.rect = pygame.Rect(0, 0, 0, 0)
        self.activo = True

    def dibujar(self, sup, f, mouse, sel=False):
        base = self.color or TARJETA2
        if sel or self.primario:
            base = self.color or ACENTO
        if not self.activo:
            base = mezclar(base, FONDO, 0.5)
        elif self.rect.collidepoint(mouse):
            base = mezclar(base, (255, 255, 255), 0.1)
        pygame.draw.rect(sup, base, self.rect, border_radius=6)
        col = FONDO if (sel or self.primario) and self.color is None else TEXTO
        if not self.activo:
            col = SUTIL
        img = f.render(self.texto, True, col)
        sup.blit(img, img.get_rect(center=self.rect.center))

    def clic(self, pos):
        if self.activo and self.rect.collidepoint(pos):
            self.accion()
            return True
        return False


class Campo:
    def __init__(self, etiqueta, valor, libre=False):
        self.etiqueta, self.valor, self.libre = etiqueta, str(valor), libre
        self.rect = pygame.Rect(0, 0, 0, 0)
        self.foco = False

    def tecla(self, e):
        if e.key == pygame.K_BACKSPACE:
            self.valor = self.valor[:-1]
        elif e.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_TAB):
            self.foco = False
        elif e.key == pygame.K_v and e.mod & pygame.KMOD_CTRL:
            try:
                pygame.scrap.init()
                pegado = pygame.scrap.get(pygame.SCRAP_TEXT)
                if pegado:
                    self.valor += pegado.decode("utf-8", "ignore").replace("\x00", "").strip()[:120]
            except Exception:
                pass
        elif e.unicode and e.unicode.isprintable() and len(self.valor) < 120:
            self.valor += e.unicode

    def dibujar(self, sup, f, fe):
        pygame.draw.rect(sup, TARJETA2, self.rect, border_radius=5)
        pygame.draw.rect(sup, ACENTO if self.foco else BORDE, self.rect, 1, border_radius=5)
        et = fe.render(self.etiqueta, True, TENUE)
        sup.blit(et, (self.rect.x + 8, self.rect.centery - et.get_height() // 2))
        txt = self.valor + ("|" if self.foco and int(time.time() * 2) % 2 == 0 else "")
        espacio = self.rect.w - et.get_width() - 26
        while txt and f.size(txt)[0] > espacio:
            txt = txt[1:]
        if not self.valor and not self.foco:
            img = fe.render("ciudad o «lat, lon»", True, SUTIL)
        else:
            img = f.render(txt, True, TEXTO)
        sup.blit(img, img.get_rect(midright=(self.rect.right - 8, self.rect.centery)))


class App:
    def __init__(self, modo="entrenar", entrenar=True, dir_datos=None):
        pygame.init()
        try:
            import ctypes
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass
        info = pygame.display.Info()
        tam = (min(1600, info.current_w - 60), min(900, info.current_h - 100))
        self.pantalla = pygame.display.set_mode(tam, pygame.RESIZABLE)
        pygame.display.set_caption("Escudo Global — defensa antimisiles por capas con IA")
        self.reloj = pygame.time.Clock()
        self.ent = Entrenador(dir_datos=dir_datos)
        self.hilo = HiloEntrenamiento(self.ent)
        self.entrenar_al_inicio = entrenar
        self.grabador = Grabador()
        self.velocidad = 10
        self.pausa = False
        self.verdad = False
        self.aviso = ("", 0.0)
        self.mision_n = self.ent.mision_actual
        self.control_cmd = "ia"
        self.cmd_bandos = None
        self.bando_sel = None
        self.ultimo_atacante = None
        self.ultimo_defensor = None
        self.controles = False
        self.asistente = None
        self.btn_asis_dyn = []
        self.btn_bandos_dyn = []
        self.btn_ataca_dyn = []
        self.mirv_cmd = True
        self.sat_modo = SAT._a_modo(self.ent.cfg.get("satelites", C.SAT_DEFECTO))
        self.borrar_t = 0.0
        self.salva = "doble" if self.ent.cfg.get("salva") == "doble" else "una"
        self.nuclear_cmd = False
        self.tipo_nuevo = "alta"
        self.punto = None
        cfg = self.ent.cfg
        if cfg.get("bandos"):
            self.teatro_bandos = copy.deepcopy(cfg["bandos"])
        elif cfg.get("ciudades") or cfg.get("origenes") or cfg.get("activos"):
            self.teatro_bandos = MS.bandos_de(MS.preparar(self.ent.mision_actual, cfg)[0])
        else:
            self.teatro_bandos = None
        self.act_sel = 0
        self._tabs = []
        self.ep = None
        self.ep_info = ""
        self.ep_gen = None
        self.acum = 0.0
        self.arrastre = None
        self.arrastre_act = None
        self._cursor = None
        self.hover = None
        self.seleccion = None
        self.vista = "tactico"
        self._teselas = OrderedDict()
        self._ver_teselas = 0
        self._faltan_teselas = 0
        self._cache_mapa = None
        self._circulos = {}
        self.cargador = G.CargadorTeselas()
        self.cola_geo = queue.Queue()
        self.ocupado_geo = ""
        self.campo_lugar = Campo("Lugar", "", libre=True)
        self.btn_vista = [Boton(G.NOMBRES_VISTA[v], lambda v=v: self._vista(v)) for v in G.VISTAS]
        self.btn_lugar = [Boton("Ir", lambda: self._buscar("ir"), primario=True),
                          Boton("Proteger ciudad", self._proteger_ciudad),
                          Boton("Activo aquí", lambda: self._buscar("activo")),
                          Boton("Quitar ciudades", self._quitar_ciudades)]
        self.btn_atacante = Boton("+ Atacante (escribe el país en «Lugar» o clic en el mapa)", self._agregar_atacante,
                                  color=(110, 40, 40))
        self.btn_restaurar = Boton("Misión original", self._restaurar)
        self.btn_rol = [Boton("Atacante", lambda: self._buscar("rol_atacante"), color=(150, 40, 40)),
                        Boton("Defensor", lambda: self._buscar("rol_defensor"), color=(30, 105, 150))]
        self.btn_auto = Boton("Automático", self._activos_auto)
        self.btn_bando_ops = [Boton("+ Bando", self._nuevo_bando), Boton("Renombrar", self._renombrar_bando),
                              Boton("Quitar bando", self._quitar_bando)]
        self.btn_controles = Boton("Opciones avanzadas", self._toggle_controles)
        self.btn_asistente = Boton("Elegir ciudad, atacante y defensa", self._asis_abrir, primario=True)
        self.btn_asis = {"atras": Boton("← Atrás", lambda: self._asis_paso(-1)),
                         "sig": Boton("Siguiente →", lambda: self._asis_paso(1), primario=True),
                         "listo": Boton("¡Listo, comenzar!", self._asis_listo, primario=True),
                         "cerrar": Boton("Cerrar", self._asis_cerrar),
                         "agregar": Boton("Agregar", self._asis_agregar),
                         "auto": Boton("Defensa automática", self._asis_auto),
                         "vaciar": Boton("Quitar todas", self._asis_vaciar)}
        self.btn_presets = [Boton("Pacífico", lambda: self._preset("pacifico")),
                            Boton("Rusia vs OTAN", lambda: self._preset("otan")),
                            Boton("Guerra global", lambda: self._preset("global")),
                            Boton("Vacío", lambda: self._preset("vacio"))]
        self.btn_modos = [Boton(t, lambda m=m: self.cambiar_modo(m)) for m, t in MODOS]
        self.btn_vel = [Boton(f"×{v}", lambda v=v: self._vel(v)) for v in VELOCIDADES]
        self.btn_pausa = Boton("Pausa", self._pausar)
        self.btn_grabar = Boton("Grabar pantalla", self._grabar)
        self.btn_mis = [Boton("‹", lambda: self._mision(-1)), Boton("›", lambda: self._mision(1))]
        self.btn_reiniciar = Boton("Reiniciar escenario", self._reiniciar_ep)
        self.btn_ent = [Boton("Pausar entrenamiento", self._pausar_ent), Boton("Guardar", self._guardar),
                        Boton("Clase del instructor", self._forzar_clase)]
        self.btn_borrar = Boton("Borrar lo aprendido", self._borrar)
        self.rep_n = self.ent.mision_actual
        self.rep_todas_t = 0.0
        self.btn_rep = [Boton("‹", lambda: self._rep_mover(-1)), Boton("›", lambda: self._rep_mover(1)),
                        Boton("Repetir esta misión", lambda: self._repetir(self.rep_n)),
                        Boton("Repetir todas", lambda: self._repetir(None))]
        self.btn_sat = Boton("Satélites", self._toggle_sat)
        self.btn_salva = Boton("Disparo", self._toggle_salva)
        self.btn_nuc = Boton("Ojivas nucleares: NO", self._toggle_nuc)
        self.btn_rapido = Boton("Entrenamiento rápido sin gráficos", self._a_rapido, primario=True)
        self.btn_cfg = [Boton("−", lambda: self._cfg(-1)), Boton("+", lambda: self._cfg(1))]
        self.btn_lanz = [Boton("−", lambda: self._lanzadores(-1)), Boton("+", lambda: self._lanzadores(1))]
        self.btn_mirv = Boton("Ojivas múltiples y señuelos: SÍ", self._toggle_mirv)
        self.btn_tipos = [Boton(C.ACTIVOS[t]["corto"], lambda t=t: self._tipo(t)) for t in C.ORDEN_ACTIVOS]
        self.btn_activos = [Boton("Poner en el punto", self._poner_activo, primario=True),
                            Boton("Quitar activo", self._quitar_activo)]
        self.btn_ctrl = [Boton("IA campeón", lambda: self._control("ia")), Boton("Doctrina", lambda: self._control("doctrina")),
                         Boton("Manual", lambda: self._control("manual"))]
        self.btn_comenzar = Boton("¡Comenzar ataque!", self._comenzar, primario=True)
        self.btn_perfil = [Boton("Todas", lambda: self._perfil(True)), Boton("Seleccionada", lambda: self._perfil(False))]
        self.perfil_todas = True
        self.salida = None
        self.preparando = False
        self.modo = None
        self._layout()
        self.cambiar_modo(modo)

    def _layout(self):
        W, H = self.pantalla.get_size()
        self.k = k = max(0.7, min(W / 1600, H / 900))
        self.f_mini = _fuente("seguisb.ttf", int(11 * k))
        self.f_chica = _fuente("segoeui.ttf", int(12 * k))
        self.f_texto = _fuente("segoeui.ttf", int(14 * k))
        self.f_semi = _fuente("seguisb.ttf", int(14 * k))
        self.f_titulo = _fuente("seguisb.ttf", int(20 * k))
        self.f_valor = _fuente("seguisb.ttf", int(19 * k))
        m = int(12 * k)
        self.m = m
        pw = int(450 * k)
        inf = int(210 * k)
        self.r_panel = pygame.Rect(W - pw - m, m, pw, H - 2 * m)
        self.r_mapa = pygame.Rect(m, m, W - pw - 3 * m, H - inf - 3 * m)
        mitad = (self.r_mapa.w - m) // 2
        self.r_log = pygame.Rect(m, self.r_mapa.bottom + m, mitad, inf)
        self.r_perfil = pygame.Rect(self.r_log.right + m, self.r_mapa.bottom + m, self.r_mapa.w - mitad - m, inf)
        self.esc_min = self.r_mapa.w / 360.0
        self.esc_max = self.r_mapa.w / 1.5
        if not hasattr(self, "esc"):
            self.esc = self.r_mapa.w / 120.0
            self.vx, self.vy = 180.0, M.merc_y(30.0)
        self.esc = min(max(self.esc, self.esc_min), self.esc_max)
        self._limitar_vista()
        self._cache_mapa = None

    def _limitar_vista(self):
        r = self.r_mapa
        mh = r.h / self.esc / 2
        self.vy = min(max(self.vy, -Y_MAX + mh), Y_MAX - mh) if mh < Y_MAX else 0.0
        self.vx = (self.vx + 180.0) % 360.0 - 180.0 if abs(self.vx) > 540 else self.vx

    def a_pantalla(self, lat, lon):
        r = self.r_mapa
        x = M.desenvolver(lon, self.vx)
        return (r.centerx + (x - self.vx) * self.esc, r.centery - (M.merc_y(lat) - self.vy) * self.esc)

    def a_mundo(self, px, py):
        r = self.r_mapa
        x = self.vx + (px - r.centerx) / self.esc
        y = self.vy - (py - r.centery) / self.esc
        return M.lat_de_y(y), (x + 180.0) % 360.0 - 180.0

    def _proy(self, lats, lons, ancla=None):
        lats = np.asarray(lats, dtype=float)
        lons = np.asarray(lons, dtype=float)
        if not len(lons):
            return []
        if ancla is None:
            X = np.degrees(np.unwrap(np.radians(lons)))
            ref = X[0]
        else:
            X = ancla + ((lons - ancla + 180.0) % 360.0 - 180.0)
            ref = ancla
        X = X + (M.desenvolver(ref, self.vx) - ref)
        r = self.r_mapa
        px = np.clip(r.centerx + (X - self.vx) * self.esc, -20000, 20000)
        py = np.clip(r.centery - (M.merc_y_vec(lats) - self.vy) * self.esc, -20000, 20000)
        return list(zip(px.tolist(), py.tolist()))

    def _km_px(self, km, lat):
        return self.esc * km / 111.32 / max(math.cos(math.radians(lat)), 0.05)

    def cambiar_modo(self, modo):
        if self.modo == "jugar" and self.ep is not None and modo != "jugar":
            self._enviar_demos()
        if self.modo == "comandante" and self.ep is not None:
            self._guardar_cmd()
        self.modo = modo
        self.seleccion = None
        if modo == "entrenar":
            self._sincronizar_cfg(aviso=False)
            if not self.hilo.activo:
                self.hilo.pausado = False
                self.hilo.iniciar()
            self.hilo.pausado = False
        elif self.hilo.activo and modo == "jugar":
            self.hilo.pausado = True
        if modo == "comandante" and self.cmd_bandos is None:
            self._preset("pacifico", rehacer=False)
        if modo in ("campeon", "jugar"):
            self.mision_n = min(max(self.mision_n, 1), MS.NUMERO_MISIONES)
        self._nuevo_ep()
        self._encuadrar()

    def _guardar_cmd(self):
        ep = self.ep
        if ep is None or not ep.continuo:
            return
        self.cmd_bandos = self._con_activos_de_ep(self.cmd_bandos)

    def _con_activos_de_ep(self, bandos):
        bandos = copy.deepcopy(bandos)
        for b in bandos:
            b["activos"] = [[a.tipo, round(a.lat, 4), round(a.lon, 4), len(a.misiles) if a.capa else None]
                            for a in self.ep.activos if a.bando == b["nombre"] and not a.destruida]
        return bandos

    def _preset(self, nombre, rehacer=True):
        if nombre == "otan":
            bandos = [copy.deepcopy(MS.RUSIA), copy.deepcopy(MS.OTAN)]
        elif nombre == "global":
            bandos = copy.deepcopy([MS.RUSIA, MS.OTAN, MS.INDIA, MS.PAKISTAN, MS.COREA_N, MS.ALIADOS_ASIA])
        elif nombre == "vacio":
            bandos = [{"nombre": "Bando 1", "ciudades": [], "origenes": [], "ataca": [], "activos": []}]
        else:
            bandos = [{"nombre": "Defensa", "ciudades": ["Ciudad de México", "Pachuca", "Guadalajara", "Los Ángeles"],
                       "origenes": [], "ataca": [], "manual": True,
                       "activos": [["exo", 34.7, -120.6, 2], ["radar", 19.1, -104.3, None], ["buque", 16.5, -108.0, 2],
                                   ["alta", 19.8, -99.4, 3], ["terminal", 19.2, -99.35, 3], ["alta", 34.1, -118.4, 3],
                                   ["terminal", 33.85, -118.5, 2]]},
                      {"nombre": "Atacante", "ciudades": [], "origenes": ["corea", "pac_este"], "ataca": ["Defensa"],
                       "activos": []}]
        self.cmd_bandos = bandos
        self.bando_sel = None
        if rehacer:
            self._nuevo_ep()
            self._encuadrar()
            self.ep.log(f"Escenario del Comandante: {nombre}", "ambar")

    def _pesos_campeon(self):
        c = self.ent.campeon(self.mision_n)
        if c is None:
            return self.ent.mejores_pesos(), f"Sin campeón aún · pesos actuales (gen {self.ent.generacion})"
        w, info = c
        return w, f"Campeón gen {info['generacion']} · protección {100 * info['proteccion']:.0f}%"

    def _ctl_cmd(self):
        if self.control_cmd == "doctrina":
            return Doctrina()
        if self.control_cmd == "manual":
            return ControladorManual(None)
        w, info = self._pesos_campeon()
        c = B.ControladorRed(w)
        c.info = info
        return c

    def _nuevo_ep(self):
        sem = int(np.random.randint(1 << 30))
        self.ep_gen = None
        if self.modo == "entrenar":
            inst = self.hilo.instantanea
            if inst is None:
                n, w, sem, g, cfg = self.ent.mision_actual, self.ent.mejores_pesos(), sem, self.ent.generacion, dict(self.ent.cfg)
            else:
                n, w, sem, g, _ = inst
                cfg = dict(self.ent.cfg)
            self.ep_gen = g
            self.mision_n = n
            mis, extra = MS.preparar(n, cfg)
            self.ep = Episodio(mis, B.ControladorRed(w), sem, bitacora=True, **extra)
            self.ep_info = f"Generación {g} · individuo central de la población"
        elif self.modo == "campeon":
            w, info = self._pesos_campeon()
            mis, extra = MS.preparar(self.mision_n, self._cfg_mision(self.ent.cfg))
            self.ep = Episodio(mis, B.ControladorRed(w), sem, bitacora=True, **extra)
            self.ep_info = info
        elif self.modo == "jugar":
            mis, extra = MS.preparar(self.mision_n, self._cfg_mision({}))
            self.ep = Episodio(mis, ControladorManual(None), sem, bitacora=True, demos=True, **extra)
            self.ep_info = "Tú eres el operador de control de tiro"
        else:
            mis = MS.libre(self.cmd_bandos, mirv=self.mirv_cmd)
            ctl = self._ctl_cmd()
            self.ep = Episodio(mis, ctl, sem, bitacora=True)
            self.ep_info = getattr(ctl, "info", ctl.nombre)
        self.ep.poner_satelites(self.sat_modo)
        self.ep.m["salva"] = self.salva
        if self.modo == "comandante":
            self.ep.m["nuclear"] = C.P_NUCLEAR_LIBRE if self.nuclear_cmd else 0.0
        self.act_sel = min(self.act_sel, max(len(self.ep.activos) - 1, 0))
        self.ep.log(f"Escenario: {self.ep.m['nombre']}", "ambar")
        self.ep.log(f"Satélites: {SAT.NOMBRES[self.sat_modo]}", "cian")
        self.preparando = self.modo == "jugar"
        if self.preparando:
            self.ep.log("Fase de despliegue: arrastra tus activos y presiona «Comenzar ataque» (Espacio)", "cian")

    def _cfg_mision(self, base):
        cfg = dict(base or {})
        for c in ("ciudades", "origenes", "activos"):
            cfg.pop(c, None)
        if self.teatro_bandos:
            cfg["bandos"] = copy.deepcopy(self.teatro_bandos)
        else:
            cfg.pop("bandos", None)
        return cfg

    def _sincronizar_cfg(self, aviso=True):
        with self.ent.bloqueo:
            antes = self.ent.cfg.get("bandos")
            for c in ("ciudades", "origenes", "activos"):
                self.ent.cfg.pop(c, None)
            if self.teatro_bandos:
                self.ent.cfg["bandos"] = copy.deepcopy(self.teatro_bandos)
            else:
                self.ent.cfg.pop("bandos", None)
            despues = self.ent.cfg.get("bandos")
        if aviso and antes != despues:
            self.avisar("La IA entrenará con tus bandos desde la próxima generación" if despues
                        else "La IA vuelve a entrenar con las misiones originales")

    def _bandos(self):
        if self.modo == "comandante":
            return copy.deepcopy(self.cmd_bandos)
        if self.teatro_bandos:
            return copy.deepcopy(self.teatro_bandos)
        return MS.bandos_de(MS.mision(self.mision_n))

    def _sel(self, bandos=None):
        nombres = [b["nombre"] for b in (bandos if bandos is not None else self.ep.bandos)]
        if self.bando_sel not in nombres:
            lista = bandos if bandos is not None else self.ep.bandos
            con = [b["nombre"] for b in lista if b.get("ciudades")]
            self.bando_sel = con[0] if con else (nombres[0] if nombres else None)
        return self.bando_sel

    def _bando(self, bandos, nombre):
        return next((b for b in bandos if b["nombre"] == nombre), None)

    def _auto(self, bandos):
        for b in bandos:
            if b.get("manual") or not b.get("ciudades"):
                continue
            if not b.get("tipos"):
                previos = [(a[0], a[3] if len(a) > 3 else None) for a in (b.get("activos") or []) if a[0] != "terminal"]
                b["tipos"] = previos or list(MS.TIPOS_AUTO)
            b["activos"] = None
        return bandos

    def _guardar_bandos(self, bandos, msg=None, rehacer=True, encuadrar=False):
        if self.modo == "comandante":
            self.cmd_bandos = bandos
        else:
            self.teatro_bandos = bandos
        if self.modo == "entrenar":
            self._sincronizar_cfg()
        if rehacer:
            if self.modo == "jugar":
                self._enviar_demos()
            sel = self.act_sel
            self._nuevo_ep()
            self.act_sel = min(sel, max(len(self.ep.activos) - 1, 0))
            if encuadrar:
                self._encuadrar()
        if msg:
            self.ep.log(msg, "ambar")
        self._cache_mapa = None

    def _teatro_cambio(self, msg):
        self._guardar_bandos(self._auto(self._bandos()), msg)

    def _toggle_ciudad(self, z):
        bandos = self._bandos()
        sel = self._sel(bandos)
        dueno = next((b for b in bandos if any(c if isinstance(c, str) else c["nombre"] for c in b["ciudades"]
                                                if (c if isinstance(c, str) else c["nombre"]) == z.nombre)), None)
        destino = self._bando(bandos, sel)
        if destino is None:
            return
        if dueno is not None:
            dueno["ciudades"] = [c for c in dueno["ciudades"] if (c if isinstance(c, str) else c["nombre"]) != z.nombre]
        if dueno is destino:
            msg = f"{z.nombre} ya no pertenece a {sel}"
        else:
            destino["ciudades"].append(MS.zona_a_dict(z))
            msg = f"{z.nombre} pasa a {sel}" if dueno is not None else f"{sel} protege {z.nombre}"
        self._guardar_bandos(self._auto(bandos), msg)

    def _toggle_origen(self, clave):
        bandos = self._bandos()
        sel = self._sel(bandos)
        destino = self._bando(bandos, sel)
        if destino is None:
            return
        dueno = next((b for b in bandos if clave in [M.clave_origen(o) for o in b["origenes"]]), None)
        if dueno is not None:
            dueno["origenes"] = [o for o in dueno["origenes"] if M.clave_origen(o) != clave]
        o = M.ORIGENES[clave]
        if dueno is destino:
            msg = f"{sel} ya no lanza desde {o['nombre']}"
        else:
            destino["origenes"].append(clave if not o.get("propio") else
                                       {"clave": clave, "nombre": o["nombre"], "caja": list(o["caja"])})
            msg = f"{sel} lanza desde {o['nombre']}"
        self._guardar_bandos(self._auto(bandos), msg)

    def _toggle_ataca(self, otro):
        bandos = self._bandos()
        b = self._bando(bandos, self._sel(bandos))
        if b is None:
            return
        if otro in b["ataca"]:
            b["ataca"].remove(otro)
            msg = f"{b['nombre']} deja de atacar a {otro}"
        else:
            b["ataca"].append(otro)
            msg = f"{b['nombre']} ataca a {otro}"
            if not b["origenes"]:
                self.avisar(f"{b['nombre']} necesita una zona de lanzamiento: clic en una zona del mapa o «Lanza desde aquí»")
        self._guardar_bandos(self._auto(bandos), msg)

    def _nuevo_bando(self):
        bandos = self._bandos()
        nombres = {b["nombre"] for b in bandos}
        texto = self.campo_lugar.valor.strip()
        nombre = texto if texto and G.leer_coordenadas(texto) is None and texto not in nombres else None
        k = len(bandos) + 1
        while nombre is None:
            if f"Bando {k}" not in nombres:
                nombre = f"Bando {k}"
            k += 1
        bandos.append({"nombre": nombre[:24], "ciudades": [], "origenes": [], "ataca": [], "activos": []})
        self.bando_sel = nombre[:24]
        self.campo_lugar.valor = ""
        self._guardar_bandos(bandos, f"Nuevo bando: {nombre[:24]} · elige sus ciudades, sus zonas de lanzamiento y a quién ataca")

    def _renombrar_bando(self):
        texto = self.campo_lugar.valor.strip()[:24]
        bandos = self._bandos()
        viejo = self._sel(bandos)
        if not texto or G.leer_coordenadas(texto) is not None or texto in {b["nombre"] for b in bandos}:
            self.avisar("Escribe el nuevo nombre del bando en «Lugar» y presiona «Renombrar»")
            return
        for b in bandos:
            if b["nombre"] == viejo:
                b["nombre"] = texto
            b["ataca"] = [texto if x == viejo else x for x in b["ataca"]]
        self.bando_sel = texto
        self.campo_lugar.valor = ""
        self._guardar_bandos(bandos, f"{viejo} ahora se llama {texto}")

    def _quitar_bando(self):
        bandos = self._bandos()
        if len(bandos) <= 1:
            self.avisar("Debe quedar al menos un bando")
            return
        sel = self._sel(bandos)
        bandos = [b for b in bandos if b["nombre"] != sel]
        for b in bandos:
            b["ataca"] = [x for x in b["ataca"] if x != sel]
        self.bando_sel = None
        self._guardar_bandos(self._auto(bandos), f"Se quitó el bando {sel}")

    def _toggle_controles(self):
        self.controles = not self.controles

    def _poner_atacante(self, nombre, lat, lon, radio_km):
        o = M.origen_propio(nombre, lat, lon, radio_km)
        la0, la1, lo0, lo1 = o["caja"]
        sel = self._sel()
        for z in self.ep.zonas:
            dentro = la0 <= z.lat <= la1 and lo0 <= M.desenvolver(z.lon, (lo0 + lo1) / 2) <= lo1
            if dentro and z.bando != sel:
                self.avisar(f"{z.nombre} ({z.bando}) quedaría dentro de la zona de lanzamiento: elige otro lugar")
                return
        bandos = self._bandos()
        destino = self._bando(bandos, self._sel(bandos))
        for b in bandos:
            b["origenes"] = [x for x in b["origenes"] if M.clave_origen(x) != o["clave"]]
        destino["origenes"].append(o)
        self._guardar_bandos(self._auto(bandos), f"{destino['nombre']} lanza desde {nombre}")

    def _activos_cambio(self, msg=None, bando=None):
        bandos = self._con_activos_de_ep(self._bandos())
        for b in bandos:
            if bando is None or b["nombre"] == bando:
                b["manual"] = True
        self._guardar_bandos(bandos, msg if self.modo in ("entrenar", "campeon") else None,
                             rehacer=self.modo in ("entrenar", "campeon"))

    def _activos_auto(self):
        bandos = self._bandos()
        b = self._bando(bandos, self._sel(bandos))
        if b is None or not b.get("ciudades"):
            self.avisar("El bando elegido no tiene ciudades que defender")
            return
        actuales = [(a.tipo, len(a.misiles) if a.capa else None) for a in self.ep.activos
                    if a.bando == b["nombre"] and not a.destruida]
        b["manual"] = False
        b["tipos"] = actuales or None
        b["activos"] = None
        self._guardar_bandos(bandos, f"Activos de {b['nombre']} acomodados donde sí alcanzan")

    def _restaurar(self):
        if self.modo == "comandante":
            self._preset("pacifico")
            return
        if not self.teatro_bandos:
            self.avisar("Ya estás en el escenario original de la misión")
            return
        self.teatro_bandos = None
        self.bando_sel = None
        self._guardar_bandos(None, "Escenario original de la misión", encuadrar=True)

    def _candidatas(self):
        nombres = {z.nombre for z in self.ep.zonas}
        return [M.ciudad(n, activa=False) for n in M.CIUDADES if n not in nombres]

    def _color_bando(self, nombre):
        nombres = [b["nombre"] for b in self.ep.bandos]
        i = nombres.index(nombre) if nombre in nombres else 0
        return PALETA_BANDOS[i % len(PALETA_BANDOS)]

    def _hostil(self, lat, lon, bando):
        clave = M.en_origen(lat, lon, self.ep.origenes)
        return clave is not None and self.ep.origen_bando.get(clave) != bando

    def _encuadrar(self):
        ep = self.ep
        pts = [(z.lat, z.lon) for z in ep.zonas if z.activa] + [(a.lat, a.lon) for a in ep.activos]
        for o in ep.origenes:
            la0, la1, lo0, lo1 = M.ORIGENES[o]["caja"]
            pts += [(la0, lo0), (la1, lo1)]
        if not pts:
            return
        ref = pts[0][1]
        xs = [M.desenvolver(lo, ref) for _, lo in pts]
        ys = [M.merc_y(la) for la, _ in pts]
        x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
        r = self.r_mapa
        ancho = max(x1 - x0, 8.0) * 1.25
        alto = max(y1 - y0, 6.0) * 1.35
        self.esc = min(max(min(r.w / ancho, r.h / alto), self.esc_min), self.esc_max)
        self.vx = (x0 + x1) / 2
        self.vy = (y0 + y1) / 2 + 0.04 * r.h / self.esc
        self._limitar_vista()
        self._cache_mapa = None

    def _vista(self, v):
        if v != self.vista:
            self.vista = v
            self._cache_mapa = None
            self.avisar(f"Vista del mapa: {G.NOMBRES_VISTA[v]}")

    def _perfil(self, todas):
        self.perfil_todas = todas

    def _vel(self, v):
        self.velocidad = v
        self.pausa = False

    def _pausar(self):
        self.pausa = not self.pausa

    def _mision(self, d):
        if self.modo in ("campeon", "jugar"):
            if self.modo == "jugar":
                self._enviar_demos()
            self.mision_n = (self.mision_n - 1 + d) % MS.NUMERO_MISIONES + 1
            self._nuevo_ep()
            self._encuadrar()

    def _reiniciar_ep(self):
        if self.modo == "jugar":
            self._enviar_demos()
        if self.modo == "comandante":
            self._guardar_cmd()
        self._nuevo_ep()

    def _pausar_ent(self):
        self.hilo.pausado = not self.hilo.pausado

    def _guardar(self):
        threading.Thread(target=self.ent.guardar, daemon=True).start()
        self.avisar("Avance de la IA guardado en datos\\")

    def _a_rapido(self):
        self.salida = "rapido"
        self.avisar("Guardando y pasando al entrenamiento rápido…")

    def _borrar(self):
        if time.time() - self.borrar_t > 5.0:
            self.borrar_t = time.time()
            self.avisar("¿Seguro? Presiona otra vez «Borrar lo aprendido» para borrar todo lo que aprendió la IA")
            return
        self.borrar_t = 0.0
        self.hilo.instantanea = None

        def tarea():
            self.ent.reiniciar()
            self.mision_n = self.ent.mision_actual
        threading.Thread(target=tarea, daemon=True).start()
        self.avisar("Se borró lo aprendido: la IA empieza desde cero en la misión 1 (tu teatro y ciudades se conservan)")

    def _rep_mover(self, d):
        self.rep_n = (self.rep_n - 1 + d) % MS.NUMERO_MISIONES + 1

    def _repetir(self, numero):
        if numero is None and time.time() - self.rep_todas_t > 5.0:
            self.rep_todas_t = time.time()
            self.avisar("¿Repetir todo el currículo? Presiona otra vez «Repetir todas» (la red no se borra)")
            return
        self.rep_todas_t = 0.0
        self.hilo.instantanea = None

        def tarea():
            self.ent.repetir(numero)
            self.mision_n = self.ent.mision_actual
        threading.Thread(target=tarea, daemon=True).start()
        if numero is None:
            self.avisar("Se repiten todas las misiones desde la 1 con la red actual")
        else:
            self.avisar(f"La IA vuelve a entrenar la misión {numero}. {MS.NOMBRES[numero - 1]} y luego sigue su currículo")
        if self.hilo.pausado:
            self.hilo.pausado = False

    def _toggle_sat(self):
        self.sat_modo = (self.sat_modo + 1) % 3
        with self.ent.bloqueo:
            self.ent.cfg["satelites"] = self.sat_modo
        if self.ep is not None:
            self.ep.poner_satelites(self.sat_modo)
        txt = {0: "Sin satélites: sólo los radares detectan los misiles",
               1: "Satélites de alerta temprana: detectan el lanzamiento por el calor del motor",
               2: "Alerta + seguimiento: detectan el lanzamiento y siguen ojivas y señuelos en el espacio"}[self.sat_modo]
        self.avisar(txt)
        if self.ep is not None:
            self.ep.log(txt, "cian")

    def _toggle_salva(self):
        self.salva = "doble" if self.salva == "una" else "una"
        with self.ent.bloqueo:
            self.ent.cfg["salva"] = self.salva
        if self.ep is not None:
            self.ep.m["salva"] = self.salva
        txt = ("Disparo doble en blancos críticos: máxima protección, gasta más interceptores" if self.salva == "doble" else
               "Un interceptor por objetivo, nunca dos: si falla, el blanco sigue fijado y se dispara otro")
        self.avisar(txt)
        if self.ep is not None:
            self.ep.log(txt, "cian")

    def _toggle_nuc(self):
        self.nuclear_cmd = not self.nuclear_cmd
        if self.ep is not None:
            self.ep.m["nuclear"] = C.P_NUCLEAR_LIBRE if self.nuclear_cmd else 0.0
        self.avisar("Los atacantes pueden usar ojivas nucleares" if self.nuclear_cmd else "Sin ojivas nucleares")

    def _fila_sat(self, tr, y, mouse):
        s, k = self.pantalla, self.k
        mitad = (tr.w - 30 * k) / 2
        self.btn_sat.texto = f"Satélites: {SAT.CORTOS[self.sat_modo]}"
        self.btn_sat.rect = pygame.Rect(tr.x + 12 * k, y, mitad, int(26 * k))
        self.btn_sat.dibujar(s, self.f_chica, mouse, self.sat_modo > 0)
        self.btn_salva.texto = "Disparo: 1 por objetivo" if self.salva == "una" else "Disparo: doble en críticos"
        self.btn_salva.rect = pygame.Rect(tr.x + 18 * k + mitad, y, mitad, int(26 * k))
        self.btn_salva.dibujar(s, self.f_chica, mouse, self.salva == "doble")
        return y + int(32 * k)

    def _forzar_clase(self):
        self.ent.clases.pop(self.ent.mision, None)
        self.avisar("Habrá clase del instructor en la siguiente generación")

    def _cfg(self, d):
        with self.ent.bloqueo:
            v = int(self.ent.cfg.get("lanzadores", 0)) + d
            self.ent.cfg["lanzadores"] = max(0, min(8, v))
        v = self.ent.cfg["lanzadores"]
        self.avisar(f"La IA entrenará con {v} lanzadores por activo" if v else "La IA entrenará con los lanzadores de cada misión")

    def avisar(self, txt):
        self.aviso = (txt, time.time())

    def _act(self):
        if not self.ep.activos:
            return None
        sel = self._sel()
        self.act_sel = max(0, min(self.act_sel, len(self.ep.activos) - 1))
        if self.ep.activos[self.act_sel].bando != sel:
            propios = [i for i, a in enumerate(self.ep.activos) if a.bando == sel]
            if not propios:
                return None
            self.act_sel = propios[0]
        return self.ep.activos[self.act_sel]

    def _lanzadores(self, d):
        a = self._act()
        if a is None or a.capa is None:
            self.avisar("Selecciona un activo con interceptores")
            return
        n = max(1, min(8, len(a.misiles) + d))
        if n == len(a.misiles):
            return
        while len(a.misiles) < n:
            a.misiles.append(a.por_lanzador)
            a.recarga_t.append(0.0)
        del a.misiles[n:]
        del a.recarga_t[n:]
        self.ep.log(f"{a.nombre}: {n} lanzador{'es' if n > 1 else ''} ({n * a.por_lanzador} interceptores)", "ambar")
        if self.modo != "comandante":
            self._activos_cambio(bando=a.bando)

    def _toggle_mirv(self):
        self.mirv_cmd = not self.mirv_cmd
        self.ep.m["mirv"] = self.mirv_cmd

    def _tipo(self, t):
        self.tipo_nuevo = t

    def _control(self, c):
        self.control_cmd = c
        if self.modo == "comandante" and self.ep is not None:
            self.ep.controlador = self._ctl_cmd()
            self.ep_info = getattr(self.ep.controlador, "info", self.ep.controlador.nombre)

    def _poner_activo(self):
        if self.punto is None:
            self.avisar("Haz clic en el mapa o escribe un lugar y usa «Activo aquí»")
            return
        self.bando_sel = self._bando_cercano(*self.punto)
        self._activo_en(*self.punto)

    def _activo_en(self, lat, lon, nombre=""):
        ep = self.ep
        sel = self._sel()
        if sel is None:
            return
        if self._hostil(lat, lon, sel):
            self.avisar("Ese punto está dentro de la zona de lanzamiento de otro bando")
            return
        a = ep.agregar_activo(self.tipo_nuevo, lat, lon, None, 99 if self.modo == "comandante" else None, bando=sel)
        self.act_sel = len(ep.activos) - 1
        msg = f"{sel} · {a.nombre}: {a.q['nombre']} en {nombre or f'({lat:.2f}, {lon:.2f})'}"
        ep.log(msg, "ambar")
        self._activos_cambio(msg, sel)

    def _quitar_activo(self, a=None):
        a = a or self._act()
        if a is None or a not in self.ep.activos:
            return
        self.ep.activos.remove(a)
        msg = f"Se retiró {a.nombre} ({a.q['nombre']}) de {a.bando}"
        self.ep.log(msg, "ambar")
        self._activos_cambio(msg, a.bando)

    def _quitar_ciudades(self):
        bandos = self._bandos()
        b = self._bando(bandos, self._sel(bandos))
        if b is None or not b["ciudades"]:
            self.avisar("El bando elegido no tiene ciudades")
            return
        b["ciudades"] = []
        self._guardar_bandos(self._auto(bandos), f"{b['nombre']} ya no protege ciudades")

    def _buscar(self, accion):
        texto = self.campo_lugar.valor.strip()
        if not texto:
            if accion == "activo" and self.punto is not None:
                self._activo_en(*self.punto)
                return
            if accion == "atacante" and self.punto is not None:
                self._poner_atacante(f"Zona ({self.punto[0]:.1f}, {self.punto[1]:.1f})", *self.punto, 300.0)
                return
            if accion.startswith("rol_") and self.punto is not None:
                self._rol(accion[4:], f"({self.punto[0]:.1f}, {self.punto[1]:.1f})", *self.punto, None)
                return
            self.avisar("Escribe una ciudad o coordenadas en «Lugar»")
            return
        self.ocupado_geo = f"Buscando «{texto}»…"

        def tarea():
            try:
                self.cola_geo.put(("ok", accion, G.buscar_lugar(texto)))
            except Exception as ex:
                self.cola_geo.put(("error", accion, str(ex)))
        threading.Thread(target=tarea, daemon=True).start()

    def _procesar_geo(self):
        for clave, img in self.cargador.recoger():
            brillo = {"satelite": 0.62, "hibrido": 0.7}.get(clave[0], 1.0)
            if brillo != 1.0:
                from PIL import ImageEnhance
                img = ImageEnhance.Brightness(img).enhance(brillo)
            self._teselas[clave] = pygame.image.fromstring(img.tobytes(), img.size, "RGB").convert()
            self._teselas.move_to_end(clave)
            while len(self._teselas) > 600:
                self._teselas.popitem(last=False)
            self._ver_teselas += 1
        while True:
            try:
                tipo, accion, res = self.cola_geo.get_nowait()
            except queue.Empty:
                break
            self.ocupado_geo = ""
            if tipo == "error":
                self.avisar(res)
                continue
            lat, lon, nombre = res["lat"], res["lon"], res["nombre"][:28]
            self.punto = (lat, lon)
            if accion == "ir":
                self.vx, self.vy = M.desenvolver(lon, self.vx), M.merc_y(lat)
                self.esc = max(self.esc, self.r_mapa.w / 30)
                self._limitar_vista()
                self._cache_mapa = None
                self.avisar(f"{nombre} ({lat:.3f}, {lon:.3f})")
            elif accion == "proteger":
                r = res.get("radio")
                r = min(max(r / 1000.0, 8.0), 40.0) if r else 15.0
                existente = next((z for z in self.ep.zonas + self._candidatas() if z.distancia(lat, lon) < z.r), None)
                if existente is not None and existente.activa and existente.bando == self._sel():
                    self.avisar(f"{existente.nombre} ya es de {existente.bando}")
                    continue
                self._toggle_ciudad(existente or M.Zona(nombre, lat, lon, r, 3))
            elif accion == "activo":
                self.bando_sel = self._bando_cercano(lat, lon)
                self._activo_en(lat, lon, nombre)
            elif accion == "atacante":
                r = res.get("radio")
                self._poner_atacante(nombre, lat, lon, r / 1000.0 if r else 300.0)
            elif accion == "asis_1":
                r = res.get("radio")
                r = min(max(r / 1000.0, 8.0), 40.0) if r else 15.0
                existente = next((z for z in self.ep.zonas + self._candidatas() if z.distancia(lat, lon) < z.r), None)
                self._asis_ciudad(existente or M.Zona(nombre, lat, lon, r, 3))
            elif accion == "asis_2":
                r = res.get("radio")
                self._asis_origen(M.origen_propio(nombre, lat, lon, r / 1000.0 if r else 300.0))
            elif accion.startswith("rol_"):
                r = res.get("radio")
                self._rol(accion[4:], nombre, lat, lon, r / 1000.0 if r else None)

    def _enviar_demos(self):
        ep = self.ep
        if ep is None or ep.demos_x is None or not isinstance(ep.controlador, ControladorManual):
            return
        X, Y = np.array(ep.demos_x), np.array(ep.demos_y)
        ep.demos_x, ep.demos_y = None, None
        if len(X) < 20 or not (Y[:, 0] > 0).any():
            return
        n = self.mision_n
        self.avisar(f"La IA está aprendiendo de tus {int((Y[:, 0] > 0).sum())} decisiones…")
        threading.Thread(target=lambda: self.ent.aprender_de_humano(X, Y, n), daemon=True).start()

    def _comenzar(self):
        if not self.preparando:
            return
        self.preparando = False
        self.pausa = False
        self.ep.log("¡Comienza el ataque!", "rojo")

    def _amenaza_en(self, pos):
        mejor, dmin = None, 14 * self.k
        for am in self.ep.activas:
            if not (am.detectada or self.verdad):
                continue
            la, lo, _ = am.latlon(self.ep.t)
            px, py = self.a_pantalla(la, lo)
            d = math.hypot(px - pos[0], py - pos[1])
            if d < dmin:
                mejor, dmin = am, d
        return mejor

    def _activo_en_pantalla(self, pos):
        mejor, dmin = None, 16 * self.k
        for i, a in enumerate(self.ep.activos):
            if a.destruida:
                continue
            p = self.a_pantalla(a.lat, a.lon)
            d = math.hypot(p[0] - pos[0], p[1] - pos[1])
            if d < dmin:
                mejor, dmin = i, d
        return mejor

    def _eventos(self):
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                return False
            if e.type == pygame.VIDEORESIZE:
                self.pantalla = pygame.display.set_mode((max(e.w, 1100), max(e.h, 680)), pygame.RESIZABLE)
                self._layout()
            elif e.type == pygame.KEYDOWN:
                if self.campo_lugar.foco and e.key != pygame.K_ESCAPE:
                    if e.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                        self.campo_lugar.foco = False
                        self._proteger_ciudad()
                    else:
                        self.campo_lugar.tecla(e)
                    continue
                if e.key == pygame.K_ESCAPE:
                    if self.campo_lugar.foco:
                        self.campo_lugar.foco = False
                        continue
                    return False
                if e.key == pygame.K_SPACE:
                    if self.preparando:
                        self._comenzar()
                    else:
                        self._pausar()
                elif e.key in (pygame.K_PLUS, pygame.K_KP_PLUS, pygame.K_EQUALS):
                    i = VELOCIDADES.index(self.velocidad) if self.velocidad in VELOCIDADES else 2
                    self.velocidad = VELOCIDADES[min(i + 1, len(VELOCIDADES) - 1)]
                elif e.key in (pygame.K_MINUS, pygame.K_KP_MINUS):
                    i = VELOCIDADES.index(self.velocidad) if self.velocidad in VELOCIDADES else 2
                    self.velocidad = VELOCIDADES[max(i - 1, 0)]
                elif e.key == pygame.K_v:
                    self.verdad = not self.verdad
                elif e.key == pygame.K_HOME:
                    self._encuadrar()
                elif e.key == pygame.K_F9:
                    self._grabar()
                elif e.key == pygame.K_F12:
                    self.captura()
                elif e.key == pygame.K_r:
                    self._reiniciar_ep()
            elif e.type == pygame.MOUSEBUTTONDOWN:
                if e.button in (4, 5) and self.r_mapa.collidepoint(e.pos):
                    la, lo = self.a_mundo(*e.pos)
                    x0, y0 = M.desenvolver(lo, self.vx), M.merc_y(la)
                    self.esc = min(max(self.esc * (1.25 if e.button == 4 else 1 / 1.25), self.esc_min), self.esc_max)
                    r = self.r_mapa
                    self.vx = x0 - (e.pos[0] - r.centerx) / self.esc
                    self.vy = y0 + (e.pos[1] - r.centery) / self.esc
                    self._limitar_vista()
                    self._cache_mapa = None
                elif e.button in (1, 3):
                    self._clic(e.pos, e.button, pygame.key.get_mods() & pygame.KMOD_SHIFT)
            elif e.type == pygame.MOUSEBUTTONUP:
                if e.button == 1 and self.arrastre_act is not None:
                    self._soltar_activo(e.pos)
                elif e.button == 1 and self.arrastre is not None:
                    if not self.arrastre[2]:
                        self._clic_mapa(self.arrastre[0], pygame.key.get_mods() & pygame.KMOD_SHIFT)
                    self.arrastre = None
            elif e.type == pygame.MOUSEMOTION and self.arrastre_act is not None:
                i, p0, movido = self.arrastre_act
                if movido or math.hypot(e.pos[0] - p0[0], e.pos[1] - p0[1]) > 5:
                    self.arrastre_act = (i, p0, True)
            elif e.type == pygame.MOUSEMOTION and self.arrastre is not None:
                p0, c0, movido = self.arrastre
                if movido or math.hypot(e.pos[0] - p0[0], e.pos[1] - p0[1]) > 5:
                    self.vx = c0[0] - (e.pos[0] - p0[0]) / self.esc
                    self.vy = c0[1] + (e.pos[1] - p0[1]) / self.esc
                    self._limitar_vista()
                    self._cache_mapa = None
                    self.arrastre = (p0, c0, True)
        return True

    def _clic(self, pos, boton, shift):
        self.campo_lugar.foco = False
        if boton == 1:
            botones = [self.btn_grabar] + self.btn_modos + self.btn_vel + [self.btn_pausa] + self.btn_vista
            botones += self.btn_ataca_dyn + [self.btn_atacante]
            botones += self.btn_lugar[:3] + [self.btn_restaurar if self.modo != "comandante" else self.btn_lugar[3]]
            botones += self.btn_tipos + self.btn_activos + [self.btn_auto]
            if self.preparando:
                botones = [self.btn_comenzar] + botones
            botones += self.btn_perfil
            if self.modo in ("campeon", "jugar"):
                botones += self.btn_mis
            botones.append(self.btn_reiniciar)
            botones += [self.btn_sat, self.btn_salva]
            if self.modo == "entrenar":
                botones += self.btn_ent + self.btn_cfg + [self.btn_rapido, self.btn_borrar] + self.btn_rep
            if self.modo in ("jugar", "comandante"):
                botones += self.btn_lanz
            if self.modo == "comandante":
                botones += self.btn_ctrl + [self.btn_mirv, self.btn_nuc] + self.btn_presets
            for rr, i in self._tabs:
                if rr.collidepoint(pos):
                    self.act_sel = i
                    return
            for b in botones:
                if b.clic(pos):
                    return
            if self.campo_lugar.rect.collidepoint(pos):
                self.campo_lugar.foco = True
                return
        if self.asistente and getattr(self, "_caja_asis", None) is not None and self._caja_asis.collidepoint(pos):
            return
        if self.r_mapa.collidepoint(pos):
            i = self._activo_en_pantalla(pos)
            if boton == 1 and i is not None:
                self.act_sel = i
                self.bando_sel = self.ep.activos[i].bando
                self.arrastre_act = (i, pos, False)
            elif boton == 1:
                self.arrastre = (pos, (self.vx, self.vy), False)
            elif i is not None:
                self._quitar_activo(self.ep.activos[i])
            elif self._amenaza_en(pos) is not None:
                self._clic_mapa(pos, True)
            else:
                lat, lon = self.a_mundo(*pos)
                self.punto = (lat, lon)
                self.bando_sel = self._bando_cercano(lat, lon)
                self._activo_en(lat, lon)

    def _soltar_activo(self, pos):
        i, p0, movido = self.arrastre_act
        self.arrastre_act = None
        if not movido or i >= len(self.ep.activos):
            return
        a = self.ep.activos[i]
        lat, lon = self.a_mundo(*pos)
        if self._hostil(lat, lon, a.bando):
            self.avisar("No se puede desplegar dentro de la zona de lanzamiento de otro bando")
            return
        inmediato = self.preparando or self.ep.t < 1.0 or self.modo in ("entrenar", "campeon")
        a.mover(lat, lon, inmediato)
        if inmediato:
            msg = f"{a.nombre} desplegado en ({lat:.2f}, {lon:.2f})"
        else:
            msg = f"{a.nombre} se redespliega en ({lat:.2f}, {lon:.2f}) · listo en {mmss(C.T_REDESPLIEGUE)}"
        self.ep.log(msg, "ambar")
        self._activos_cambio(msg, a.bando)

    def _clic_mapa(self, pos, doble):
        if self.asistente:
            if not doble or self.asistente == 3:
                self._asis_clic(pos)
            return
        am = self._amenaza_en(pos)
        manual = isinstance(self.ep.controlador, ControladorManual)
        if am is not None:
            self.seleccion = am.id
            if manual and am.detectada and not self.preparando:
                n = 2 if doble and self.salva == "doble" else 1
                self.ep.controlador.ordenar(am.id, n)
                self.ep.log(f"Orden: enfrentar #{am.id} con {n} interceptor{'es' if n > 1 else ''}", "cian")
            return
        i = self._activo_en_pantalla(pos)
        if i is not None:
            self.act_sel = i
            self.bando_sel = self.ep.activos[i].bando
            return
        lat, lon = self.a_mundo(*pos)
        for z in self.ep.zonas + self._candidatas():
            p = self.a_pantalla(z.lat, z.lon)
            if math.hypot(p[0] - pos[0], p[1] - pos[1]) <= max(self._km_px(z.r, z.lat), 7 * self.k):
                self._clic_ciudad(z)
                return
        clave = M.en_origen(lat, lon)
        if clave is not None and pygame.key.get_mods() & pygame.KMOD_CTRL == 0:
            self._asis_origen(clave if not M.ORIGENES[clave].get("propio") else
                              {"clave": clave, "nombre": M.ORIGENES[clave]["nombre"], "caja": list(M.ORIGENES[clave]["caja"])})
            return
        self.punto = (lat, lon)
        self.campo_lugar.valor = f"{lat:.4f}, {lon:.4f}"
        self.seleccion = None

    def _grabar(self):
        if self.grabador.grabando:
            self.grabador.detener()
            self.avisar(f"Video guardado: grabaciones\\{os.path.basename(self.grabador.archivo)}")
        else:
            try:
                self.grabador.iniciar(*self.pantalla.get_size())
                self.avisar("Grabando… F9 para detener")
            except RuntimeError as ex:
                self.avisar(str(ex))

    def captura(self, ruta=None):
        os.makedirs(CARPETA_GRABACIONES, exist_ok=True)
        ruta = ruta or os.path.join(CARPETA_GRABACIONES, time.strftime("captura_%Y-%m-%d_%H-%M-%S.png"))
        pygame.image.save(self.pantalla, ruta)
        self.avisar(f"Captura: {os.path.basename(ruta)}")
        return ruta

    def _actualizar_cursor(self):
        pos = pygame.mouse.get_pos()
        if self.arrastre_act is not None:
            deseado = pygame.SYSTEM_CURSOR_SIZEALL
        elif self.r_mapa.collidepoint(pos) and self._activo_en_pantalla(pos) is not None:
            deseado = pygame.SYSTEM_CURSOR_HAND
        else:
            deseado = pygame.SYSTEM_CURSOR_ARROW
        if deseado != self._cursor:
            try:
                pygame.mouse.set_system_cursor(deseado)
            except Exception:
                pass
            self._cursor = deseado

    def _avanzar(self, dt_real):
        ep = self.ep
        if self.preparando or self.pausa or self.asistente:
            return
        vel = self.velocidad
        if ep.calma:
            vel = max(vel, 120)
        self.acum += dt_real * vel
        limite = time.perf_counter() + 0.025
        while self.acum > 0 and not ep.terminado and time.perf_counter() < limite:
            t0 = ep.t
            ep.paso()
            self.acum -= ep.t - t0
            for am in ep.activas:
                if am.detectada and (not am.rastro or ep.t - am.rastro[-1][3] >= 4.0):
                    am.rastro.append((*am.latlon(ep.t), ep.t))
                    if len(am.rastro) > 160:
                        am.rastro.pop(0)
            for it in ep.interceptores:
                if ep.t >= it.t_lanz and (not it.rastro or ep.t - it.rastro[-1][3] >= 2.0):
                    it.rastro.append((*M.latlon(it.pos(ep.t)), ep.t))
                    if len(it.rastro) > 120:
                        it.rastro.pop(0)
        self.acum = min(self.acum, 4.0)
        if ep.terminado:
            if not hasattr(ep, "_fin"):
                ep._fin = time.time()
                r = ep.resumen()
                ep.log(f"Fin del escenario · protección {100 * r['proteccion']:.0f}% · "
                       f"{'SUPERADO' if r['superada'] else 'no superado'}", "verde" if r["superada"] else "rojo")
                if self.modo == "jugar":
                    self._enviar_demos()
            elif time.time() - ep._fin > 5.0 and self.modo != "comandante":
                self._nuevo_ep()

    def _tesela_o_padre(self, z, tx, ty):
        v = self.vista
        img = self._teselas.get((v, z, tx, ty))
        if img is not None:
            return img
        for d in range(1, 5):
            padre = self._teselas.get((v, z - d, tx >> d, ty >> d))
            if padre is not None:
                lado = 256 >> d
                return padre.subsurface(((tx - ((tx >> d) << d)) * lado, (ty - ((ty >> d) << d)) * lado, lado, lado))
        return None

    def _mapa_fondo(self):
        r = self.r_mapa
        clave = (round(self.vx, 4), round(self.vy, 4), round(self.esc, 5), r.size, self.vista, self._ver_teselas,
                 tuple(sorted(self.ep.origen_bando.items())), tuple(b["nombre"] for b in self.ep.bandos), len(M.ORIGENES))
        if self._cache_mapa is not None and self._cache_mapa[0] == clave:
            return self._cache_mapa[1]
        sup = pygame.Surface(r.size)
        sup.fill((9, 12, 17))
        xl = self.vx - r.w / 2 / self.esc
        xr = self.vx + r.w / 2 / self.esc
        yt = self.vy + r.h / 2 / self.esc
        yb = self.vy - r.h / 2 / self.esc
        z = int(min(max(math.ceil(math.log2(self.esc * 360 / 256) - 0.25), 1), G.ZOOM_MAX[self.vista]))
        while True:
            n = 2 ** z
            c0, c1 = math.floor((xl + 180) / 360 * n), math.floor((xr + 180) / 360 * n)
            f0 = max(0, math.floor((1 - min(yt, 180) / 180) / 2 * n))
            f1 = min(n - 1, math.floor((1 - max(yb, -180) / 180) / 2 * n))
            if (c1 - c0 + 1) * (f1 - f0 + 1) <= 140 or z <= 1:
                break
            z -= 1
        lado = 360.0 / n * self.esc
        faltan = 0
        for col in range(c0, c1 + 1):
            tx = col % n
            for fila in range(f0, f1 + 1):
                if (self.vista, z, tx, fila) not in self._teselas:
                    faltan += 1
                    self.cargador.pedir((self.vista, z, tx, fila))
                img = self._tesela_o_padre(z, tx, fila)
                if img is None:
                    continue
                X0 = col * 360.0 / n - 180.0
                Y0 = 180.0 * (1 - 2 * fila / n)
                px = r.w / 2 + (X0 - self.vx) * self.esc
                py = r.h / 2 - (Y0 - self.vy) * self.esc
                ix, iy = math.floor(px), math.floor(py)
                w = math.ceil(px + lado) - ix
                if w > 0 and w < 4000:
                    sup.blit(pygame.transform.smoothscale(img, (w, w)), (ix, iy))
        self._faltan_teselas = faltan
        capa = pygame.Surface(r.size, pygame.SRCALPHA)
        paso = 30 if self.esc < r.w / 90 else (10 if self.esc < r.w / 25 else (5 if self.esc < r.w / 8 else 1))
        for lo in range(int(math.floor(xl / paso) * paso), int(xr) + paso, paso):
            px = r.w / 2 + (lo - self.vx) * self.esc
            pygame.draw.line(capa, (255, 255, 255, 18), (px, 0), (px, r.h))
            et = (lo + 180) % 360 - 180
            img = self.f_mini.render(f"{abs(et)}°{'E' if et > 0 else ('O' if et < 0 else '')}", True, (170, 178, 195))
            capa.blit(img, (px + 3, r.h - img.get_height() - 2))
        for la in range(-80, 81, paso):
            py = r.h / 2 - (M.merc_y(la) - self.vy) * self.esc
            if 0 <= py <= r.h:
                pygame.draw.line(capa, (255, 255, 255, 18), (0, py), (r.w, py))
                img = self.f_mini.render(f"{abs(la)}°{'N' if la > 0 else ('S' if la < 0 else '')}", True, (170, 178, 195))
                capa.blit(img, (3, py - img.get_height() - 1))
        for clave_o, o in M.ORIGENES.items():
            activo = clave_o in self.ep.origenes
            dueno = self.ep.origen_bando.get(clave_o)
            cb = self._color_bando(dueno) if dueno else (170, 120, 120)
            la0, la1, lo0, lo1 = o["caja"]
            a = self.a_pantalla(la1, lo0)
            b = (a[0] + (lo1 - lo0) * self.esc, r.centery - (M.merc_y(la0) - self.vy) * self.esc)
            rr = pygame.Rect(a[0] - r.x, a[1] - r.y, b[0] - a[0], b[1] - a[1])
            pygame.draw.rect(capa, (*cb, 50 if activo else 12), rr)
            pygame.draw.rect(capa, (*cb, 170 if activo else 55), rr, 1)
            pa = int(10 * self.k)
            if activo:
                for d in range(-rr.h, rr.w, pa):
                    p1 = (rr.x + max(d, 0), rr.y + max(-d, 0))
                    p2 = (rr.x + min(d + rr.h, rr.w), rr.y + min(rr.h, rr.w - d))
                    pygame.draw.line(capa, (*cb, 60), p1, p2, 1)
            etq = o["nombre"].upper() + (f" · {dueno}" if dueno and dueno != o["nombre"] else "")
            img = self.f_mini.render(etq, True, mezclar(cb, (255, 255, 255), 0.3) if activo else (150, 120, 120))
            caja = img.get_rect(midtop=(rr.centerx, rr.y + 3))
            pygame.draw.rect(capa, (14, 16, 20, 200), caja.inflate(8, 2), border_radius=4)
            capa.blit(img, caja)
        sup.blit(capa, (0, 0))
        self._cache_mapa = (clave, sup)
        return sup

    def _circulo_geo(self, lat, lon, d):
        clave = (round(lat, 3), round(lon, 3), round(d))
        pts = self._circulos.get(clave)
        if pts is None:
            n = 240 if d > 1500 else 120
            pts = np.array(M.circulo(lat, lon, d, n))
            if len(self._circulos) > 300:
                self._circulos.clear()
            self._circulos[clave] = pts
        return self._proy(pts[:, 0], pts[:, 1], ancla=lon)

    def _linea_disc(self, sup, color, pts, paso=2, grosor=1):
        for i in range(0, len(pts) - 1, paso):
            a, b = pts[i], pts[i + 1]
            if abs(a[0] - b[0]) < 5000:
                pygame.draw.line(sup, color, a, b, grosor)

    def _coberturas(self, z):
        capas = []
        for a in self.ep.vivos():
            if a.capa is None or (z.bando and a.bando != z.bando):
                continue
            if M.distancia(a.lat, a.lon, z.lat, z.lon) <= C.CAPAS[a.capa]["alcance"] * 0.8 and a.capa not in capas:
                capas.append(a.capa)
        return [c for c in C.ORDEN_CAPAS if c in capas]

    def _dibujar_mapa(self):
        s = self.pantalla
        r = self.r_mapa
        ep = self.ep
        s.blit(self._mapa_fondo(), r.topleft)
        prev = s.get_clip()
        s.set_clip(r)
        capa = pygame.Surface(s.get_size(), pygame.SRCALPHA)
        k = self.k
        t = ep.t
        amenazadas = set()
        for am in ep.activas:
            if am.detectada and am.fijada:
                z = ep.zona_en(*am.impacto_est(), am.sigma() * 0.6, am.bando_obj)
                if z is not None:
                    amenazadas.add(z.nombre)
        sel = self._act()
        for a in ep.activos:
            if a.destruida:
                continue
            col = COLOR_ACTIVO[a.tipo]
            if a.capa is not None:
                pts = self._circulo_geo(a.lat, a.lon, C.CAPAS[a.capa]["alcance"])
                self._linea_disc(capa, (*col, 170 if a is sel else 75), pts, 1, max(1, int((2 if a is sel else 1.2) * k)))
            if a is sel or a.tipo == "radar":
                pts = self._circulo_geo(a.lat, a.lon, a.radar)
                self._linea_disc(capa, (255, 255, 255, 60 if a is sel else 30), pts, 2, 1)
        candidatas = self._candidatas()
        for z in ep.zonas + candidatas:
            c = self.a_pantalla(z.lat, z.lon)
            if not r.inflate(400, 400).collidepoint(c):
                continue
            rad = max(self._km_px(z.r, z.lat), 5 * k)
            if z.activa:
                col = ROJO if (z.nombre in amenazadas and int(time.time() * 3) % 2 == 0) else self._color_bando(z.bando)
                pygame.draw.circle(capa, (*col, 40), c, rad)
                pygame.draw.circle(capa, (*col, 230), c, rad, max(2, int(2 * k)))
                pygame.draw.circle(capa, (*col, 255), c, max(2, int(3 * k)))
            else:
                pygame.draw.circle(capa, (200, 200, 190, 25), c, rad)
                pygame.draw.circle(capa, (200, 200, 190, 90), c, rad, 1)
        for la, lo, ti, en_zona in ep.impactos:
            edad = t - ti
            if edad > 600:
                continue
            p = self.a_pantalla(la, lo)
            a = int(220 * (1 - edad / 600))
            col = (255, 80, 60, a) if en_zona else (150, 150, 150, a // 2)
            e = 5 * k
            pygame.draw.line(capa, col, (p[0] - e, p[1] - e), (p[0] + e, p[1] + e), 2)
            pygame.draw.line(capa, col, (p[0] - e, p[1] + e), (p[0] + e, p[1] - e), 2)
        etiquetas = sum(1 for a in ep.activas if a.detectada) <= 14 or self.esc > r.w / 25
        for am in ep.activas:
            if not (am.detectada or self.verdad):
                continue
            la, lo, alt = am.latlon(t)
            p = self.a_pantalla(la, lo)
            p_oj = am.p_ojiva()
            col = COLOR_TIPO[am.tipo] if p_oj >= 0.25 else GRIS_SENUELO
            if am.respuesta:
                col = AZUL_CONTRA
            if self.verdad and am.senuelo:
                col = GRIS_SENUELO
            if not am.detectada:
                pygame.draw.circle(capa, (*col, 90), p, 3 * k)
                continue
            if len(am.rastro) > 1:
                rs = np.array([(q[0], q[1]) for q in am.rastro] + [(la, lo)])
                pts = self._proy(rs[:, 0], rs[:, 1])
                pygame.draw.lines(capa, (*col, 130), False, pts, max(1, int(1.5 * k)))
            ilat, ilon = am.impacto_est()
            amenaza = am.fijada or ep.valor_amenaza(am) > 0
            cimp = (255, 80, 80, 200) if amenaza else (170, 170, 170, 120)
            if am.t_impacto - t > 2:
                ts = np.linspace(t, am.t_impacto, 90)
                fl, fo, _ = M.latlon_vec(am.pos_vec(ts))
                pts = self._proy(fl, fo)
                self._linea_disc(capa, (*cimp[:3], 100), pts, 2, 1)
                pi = pts[-1]
            else:
                pi = self.a_pantalla(ilat, ilon)
            radio = max(self._km_px(am.sigma(), ilat), 3 * k)
            pygame.draw.circle(capa, cimp, pi, radio, 1)
            e = 4 * k
            pygame.draw.line(capa, cimp, (pi[0] - e, pi[1] - e), (pi[0] + e, pi[1] + e), 2)
            pygame.draw.line(capa, cimp, (pi[0] - e, pi[1] + e), (pi[0] + e, pi[1] - e), 2)
            dx, dy = pi[0] - p[0], pi[1] - p[1]
            ang = math.atan2(dy, dx) if (dx or dy) else 0.0
            tam = 7 * k
            tri = [(p[0] + tam * math.cos(ang), p[1] + tam * math.sin(ang)),
                   (p[0] + tam * 0.6 * math.cos(ang + 2.5), p[1] + tam * 0.6 * math.sin(ang + 2.5)),
                   (p[0] + tam * 0.6 * math.cos(ang - 2.5), p[1] + tam * 0.6 * math.sin(ang - 2.5))]
            pygame.draw.polygon(capa, (*col, 255), tri)
            if am.fase(t) == "impulso":
                pygame.draw.circle(capa, (255, 220, 120, 160), p, 5 * k + 3 * k * abs(math.sin(time.time() * 6)), 1)
            if am.nuclear and p_oj >= 0.25:
                pygame.draw.circle(capa, (*AMARILLO_NUC, 230), p, 10 * k, max(1, int(2 * k)))
                pygame.draw.circle(capa, (20, 20, 20, 230), p, 8 * k, 1)
            if am.fijada:
                self._reticula(capa, p, t - (am.t_fijada or t), am.en_vuelo > 0)
            if am.id == self.seleccion or am is self.hover:
                pygame.draw.circle(capa, (255, 255, 255, 230), p, 15 * k, 2)
            if etiquetas:
                txt = f"#{am.id} {alt:.0f} km" + (" · NUCLEAR" if am.nuclear and p_oj >= 0.25 else "") + (" · CONTRAATAQUE" if am.respuesta else "")
                if am.racimo:
                    txt += f" · {100 * p_oj:.0f}% ojiva"
                capa.blit(self.f_mini.render(txt, True, col), (p[0] + 9 * k, p[1] - 6 * k))
        for it in ep.interceptores:
            if t < it.t_lanz:
                col = COLOR_CAPA[it.capa]
                la1, lo1, _ = M.latlon(it.apunte)
                a0 = it.activo_lanz
                n = 24
                u0, u1 = M.unitario(a0.lat, a0.lon), M.unitario(la1, lo1)
                om = max(math.acos(max(-1.0, min(1.0, float(np.dot(u0, u1))))), 1e-6)
                fs = np.linspace(0, 1, n)[:, None]
                U = (np.sin((1 - fs) * om) * u0 + np.sin(fs * om) * u1) / math.sin(om)
                gl, gn, _ = M.latlon_vec(U * M.R)
                pts = self._proy(gl, gn)
                self._linea_disc(capa, (*col, 170), pts, 2, max(1, int(1.5 * k)))
                pi_ = pts[-1]
                pygame.draw.circle(capa, (*col, 220), pi_, 5 * k, 1)
                p0 = self.a_pantalla(a0.lat, a0.lon)
                etq = self.f_mini.render(f"{a0.nombre} lanza en {mmss(it.t_lanz - t)}", True, col)
                capa.blit(etq, (p0[0] + 12 * k, p0[1] - 20 * k))
                continue
            col = COLOR_CAPA[it.capa]
            la, lo, _ = M.latlon(it.pos(t))
            p = self.a_pantalla(la, lo)
            if len(it.rastro) > 1:
                rs = np.array([(q[0], q[1]) for q in it.rastro] + [(la, lo)])
                pygame.draw.lines(capa, (*col, 190), False, self._proy(rs[:, 0], rs[:, 1]), max(1, int(1.5 * k)))
            pygame.draw.circle(capa, (235, 250, 255, 255), p, 3 * k)
        for la, lo, alt, te, tipo in ep.explosiones:
            edad = (t - te) / max(self.velocidad / 10, 0.5)
            if edad < 0 or edad > 4:
                continue
            p = self.a_pantalla(la, lo)
            f = edad / 4
            col, rmax = {"derribo": ((255, 240, 170), 30), "impacto": ((255, 110, 40), 36),
                         "nuclear": ((255, 250, 210), 110), "contra": ((90, 170, 255), 34),
                         "fallo": ((255, 170, 60), 14)}.get(tipo, ((150, 150, 150), 8))
            rad = max(2, int(rmax * k * (0.3 + f)))
            pygame.draw.circle(capa, (*col, int(230 * (1 - f))), p, rad, max(1, int(3 * k * (1 - f)) + 1))
            if f < 0.3:
                pygame.draw.circle(capa, (*col, int(200 * (1 - f / 0.3))), p, rad * 0.5)
        self._dibujar_satelites(capa)
        s.blit(capa, (0, 0))
        for i, a in enumerate(ep.activos):
            p = self.a_pantalla(a.lat, a.lon)
            if not r.inflate(60, 60).collidepoint(p):
                continue
            col = COLOR_ACTIVO[a.tipo] if not a.destruida else SUTIL
            if a.estado == "desplegando":
                col = NARANJA
            if len(ep.bandos) > 1:
                pygame.draw.circle(s, self._color_bando(a.bando), p, 12 * k, max(1, int(2 * k)))
            self._icono_activo(s, a.tipo, p, col)
            if a is sel:
                pygame.draw.circle(s, (255, 255, 255), p, 15 * k, 2)
            fuera = id(a) in self._sin_alcance()
            if self.esc >= r.w / 45 or a is sel or fuera:
                txt = a.nombre + (" · fuera de alcance" if fuera else "")
                img = self.f_mini.render(txt, True, (150, 150, 160) if fuera else (255, 255, 255))
                caja = img.get_rect(midleft=(p[0] + 11 * k, p[1] + 9 * k))
                pygame.draw.rect(s, (14, 16, 20), caja.inflate(8, 2), border_radius=4)
                s.blit(img, caja)
        ocupadas = []
        for z in sorted(ep.zonas, key=lambda z: -z.valor) + candidatas:
            if not z.activa and z in ep.zonas:
                c = self.a_pantalla(z.lat, z.lon)
                img = self.f_mini.render(z.nombre + " · ARRASADA", True, ROJO)
                caja = img.get_rect(midtop=(c[0], c[1] + max(self._km_px(z.r, z.lat), 5 * k) + 2 * k)).inflate(6, 2)
                pygame.draw.rect(s, (14, 16, 20), caja, border_radius=4)
                s.blit(img, img.get_rect(center=caja.center))
                continue
            if not z.activa:
                if self.esc > r.w / 60:
                    c = self.a_pantalla(z.lat, z.lon)
                    img = self.f_mini.render(z.nombre + f" · clic: a {self._sel() or ''}", True, (190, 190, 180))
                    s.blit(img, img.get_rect(midtop=(c[0], c[1] + self._km_px(z.r, z.lat) + 3)))
                continue
            c = self.a_pantalla(z.lat, z.lon)
            if not r.inflate(200, 200).collidepoint(c):
                continue
            caps = self._coberturas(z)
            col = VERDE if ("alta" in caps or "baja" in caps) else (NARANJA if caps else ROJO)
            if self.esc < r.w / 45:
                img = self.f_mini.render(z.nombre, True, self._color_bando(z.bando) if len(ep.bandos) > 1 else TEXTO)
                caja = img.get_rect(midtop=(c[0], c[1] + max(self._km_px(z.r, z.lat), 5 * k) + 2 * k)).inflate(6, 2)
                if any(caja.colliderect(o) for o in ocupadas):
                    continue
                ocupadas.append(caja)
                pygame.draw.rect(s, (14, 16, 20), caja, border_radius=4)
                pygame.draw.line(s, col, caja.bottomleft, caja.bottomright, 2)
                s.blit(img, img.get_rect(center=caja.center))
                continue
            l1 = self.f_semi.render(z.nombre, True, TEXTO)
            txt = "capas: " + " · ".join(C.CAPAS[cp]["corto"] for cp in caps) if caps else "SIN COBERTURA"
            quien = f"{z.bando} · " if len(ep.bandos) > 1 else ""
            l2 = self.f_mini.render(f"{quien}valor {int(z.valor)}/3 · {txt}", True, col)
            w = max(l1.get_width(), l2.get_width()) + int(18 * k)
            caja = pygame.Rect(0, 0, w, l1.get_height() + l2.get_height() + int(6 * k))
            caja.midtop = (c[0], c[1] + max(self._km_px(z.r, z.lat), 5 * k) + 5 * k)
            if any(caja.colliderect(o) for o in ocupadas):
                continue
            ocupadas.append(caja)
            pygame.draw.rect(s, (14, 16, 20), caja, border_radius=6)
            pygame.draw.rect(s, col, caja, 1, border_radius=6)
            s.blit(l1, l1.get_rect(midtop=(caja.centerx, caja.y + 2 * k)))
            s.blit(l2, l2.get_rect(midtop=(caja.centerx, caja.y + 2 * k + l1.get_height())))
        self.hover = self._amenaza_en(pygame.mouse.get_pos()) if r.collidepoint(pygame.mouse.get_pos()) else None
        elegida = self.hover or next((a for a in ep.activas if a.id == self.seleccion), None)
        if elegida is not None and elegida.detectada and self.arrastre_act is None:
            self._ficha_amenaza(elegida)
        if self.punto is not None:
            p = self.a_pantalla(*self.punto)
            e = 9 * k
            pygame.draw.circle(s, ACENTO, p, 6 * k, 2)
            pygame.draw.line(s, ACENTO, (p[0] - e, p[1]), (p[0] - 3 * k, p[1]), 2)
            pygame.draw.line(s, ACENTO, (p[0] + 3 * k, p[1]), (p[0] + e, p[1]), 2)
            pygame.draw.line(s, ACENTO, (p[0], p[1] - e), (p[0], p[1] - 3 * k), 2)
            pygame.draw.line(s, ACENTO, (p[0], p[1] + 3 * k), (p[0], p[1] + e), 2)
        self._vista_arrastre()
        s.set_clip(prev)
        pygame.draw.rect(s, BORDE, r, 1)
        self._barra_mapa()

    def _dibujar_satelites(self, capa):
        ep = self.ep
        sats = getattr(ep, "sats", None)
        if sats is None or not sats.modo:
            return
        k, r, t = self.k, self.r_mapa, ep.t
        subs = sats.subpuntos(t)
        n_ir = len(sats.ir)
        pos = [self.a_pantalla(la, lo) for _, la, lo, _ in subs]
        for am in ep.activas:
            sv = getattr(am, "sat_vis", None)
            if not am.detectada or sv is None or t - sv[2] > 2 * C.RADAR_PERIODO + 1:
                continue
            i = sv[1] if sv[0] == "ir" else n_ir + sv[1]
            if i >= len(pos):
                continue
            la, lo, _ = am.latlon(t)
            p1 = self.a_pantalla(la, lo)
            p0 = pos[i]
            if abs(p1[0] - p0[0]) > r.w * 0.6:
                continue
            col = (255, 214, 110, 150) if sv[0] == "ir" else (120, 220, 255, 130)
            pts = [(p0[0] + (p1[0] - p0[0]) * f / 24, p0[1] + (p1[1] - p0[1]) * f / 24) for f in range(25)]
            self._linea_disc(capa, col, pts, 2, 1)
        for (nombre, la, lo, clase), p in zip(subs, pos):
            if not r.inflate(40, 40).collidepoint(p):
                continue
            if clase == "ir":
                col = (255, 214, 110)
                pygame.draw.rect(capa, (*col, 230), (p[0] - 4 * k, p[1] - 3 * k, 8 * k, 6 * k))
                pygame.draw.line(capa, (*col, 230), (p[0] - 10 * k, p[1]), (p[0] + 10 * k, p[1]), max(1, int(2 * k)))
                if self.esc >= r.w / 300:
                    capa.blit(self.f_mini.render(nombre, True, col), (p[0] + 12 * k, p[1] - 6 * k))
            else:
                pygame.draw.circle(capa, (120, 220, 255, 170), p, max(2, int(2.5 * k)))

    def _sin_alcance(self):
        ep = self.ep
        clave = (id(ep), int(ep.t // 10))
        if getattr(self, "_alc_clave", None) == clave:
            return self._alc_set
        fijadas = [am for am in ep.activas if am.fijada and am.t_impacto - ep.t > 5]
        fuera = set()
        if fijadas:
            rutas = []
            for am in fijadas:
                ts = np.linspace(ep.t, am.t_impacto, 60)
                P = am.pos_vec(ts)
                rutas.append((am, ts, P, np.linalg.norm(P, axis=1) - M.R))
            for a in ep.activos:
                if a.capa is None or a.destruida:
                    continue
                c = C.CAPAS[a.capa]
                alcanza = False
                for am, ts, P, alt in rutas:
                    if a.bando not in ep.ayudan(am):
                        continue
                    ok = (np.linalg.norm(P - a.S, axis=1) <= c["alcance"]) & (alt >= c["alt"][0]) & (alt <= c["alt"][1])
                    if a.capa == "impulso":
                        ok &= ts < am.t_motor_fin
                    if ok.any():
                        alcanza = True
                        break
                if not alcanza:
                    fuera.add(id(a))
        self._alc_clave, self._alc_set = clave, fuera
        return fuera

    def _icono_activo(self, s, tipo, p, col):
        k = self.k
        x, y = p
        if tipo == "buque":
            pts = [(x - 10 * k, y - 2 * k), (x + 10 * k, y - 2 * k), (x + 6 * k, y + 5 * k), (x - 6 * k, y + 5 * k)]
            pygame.draw.polygon(s, col, pts)
            pygame.draw.rect(s, col, (x - 2 * k, y - 7 * k, 4 * k, 5 * k))
        elif tipo == "exo":
            rr = pygame.Rect(0, 0, 14 * k, 14 * k)
            rr.center = p
            pygame.draw.rect(s, col, rr, border_radius=2)
            pygame.draw.line(s, FONDO, (x, y - 5 * k), (x, y + 5 * k), 2)
        elif tipo == "radar":
            pygame.draw.circle(s, col, p, 6 * k)
            for rr in (9, 13):
                pygame.draw.arc(s, col, pygame.Rect(x - rr * k, y - rr * k, 2 * rr * k, 2 * rr * k), 0.6, 2.5, 2)
        else:
            tam = 9 if tipo == "alta" else 7
            tri = [(x, y - tam * k), (x - tam * 0.9 * k, y + tam * 0.7 * k), (x + tam * 0.9 * k, y + tam * 0.7 * k)]
            pygame.draw.polygon(s, col, tri)
        pygame.draw.circle(s, FONDO, p, 2 * k)

    def _reticula(self, capa, p, edad, enfrentada):
        k = self.k
        cierre = min(edad / 6.0, 1.0)
        tam = (22 - 8 * cierre) * k
        col = (61, 214, 245) if enfrentada else (255, 70, 60)
        a = 255 if cierre >= 1 or int(time.time() * 8) % 2 == 0 else 120
        g = max(2, int(2 * k))
        L = tam * 0.45
        for sx in (-1, 1):
            for sy in (-1, 1):
                cx, cy = p[0] + sx * tam, p[1] + sy * tam
                pygame.draw.line(capa, (*col, a), (cx, cy), (cx - sx * L, cy), g)
                pygame.draw.line(capa, (*col, a), (cx, cy), (cx, cy - sy * L), g)
        etq = self.f_mini.render("FIJADO" if not enfrentada else "EN TIRO", True, col)
        capa.blit(etq, etq.get_rect(midbottom=(p[0], p[1] - tam - 2 * k)))

    def _vista_arrastre(self):
        if self.arrastre_act is None or not self.arrastre_act[2]:
            return
        i = self.arrastre_act[0]
        if i >= len(self.ep.activos):
            return
        s, k = self.pantalla, self.k
        a = self.ep.activos[i]
        pos = pygame.mouse.get_pos()
        lat, lon = self.a_mundo(*pos)
        ok = not self._hostil(lat, lon, a.bando)
        col = (245, 180, 0) if ok else ROJO
        capa = pygame.Surface(s.get_size(), pygame.SRCALPHA)
        if a.capa is not None:
            self._linea_disc(capa, (*col, 200), self._circulo_geo(lat, lon, C.CAPAS[a.capa]["alcance"]), 2, max(1, int(2 * k)))
        o = self.a_pantalla(a.lat, a.lon)
        pygame.draw.line(capa, (*col, 200), o, pos, max(1, int(2 * k)))
        s.blit(capa, (0, 0))
        self._icono_activo(s, a.tipo, pos, col)
        cubre = [z.nombre for z in self.ep.zonas if z.activa and a.capa is not None and z.bando == a.bando
                 and M.distancia(lat, lon, z.lat, z.lon) <= C.CAPAS[a.capa]["alcance"] * 0.8]
        lineas = [f"{a.nombre} {a.q['nombre']} → ({lat:.2f}, {lon:.2f})",
                  "colocación inmediata" if self.preparando or self.ep.t < 1 else f"redespliegue de {mmss(C.T_REDESPLIEGUE)}"]
        if not ok:
            lineas.append("Dentro de una zona hostil")
        elif cubre:
            lineas.append("Cubre: " + ", ".join(cubre)[:52])
        w = max(self.f_chica.size(t)[0] for t in lineas) + 20
        rr = pygame.Rect(pos[0] + 18 * k, pos[1] - 10 * k, w, len(lineas) * int(17 * k) + 10)
        rr.clamp_ip(self.r_mapa)
        pygame.draw.rect(s, (14, 16, 20), rr, border_radius=6)
        pygame.draw.rect(s, col, rr, 1, border_radius=6)
        yy = rr.y + 5
        for t in lineas:
            s.blit(self.f_chica.render(t, True, TEXTO), (rr.x + 10, yy))
            yy += int(17 * k)

    def _ficha_amenaza(self, am):
        ep = self.ep
        la, lo, alt = am.latlon(ep.t)
        p = self.a_pantalla(la, lo)
        sol = ep.solucion(am)
        ilat, ilon = am.impacto_est()
        z = ep.zona_en(ilat, ilon, am.sigma() * 0.6, am.bando_obj)
        dest = z.nombre if z else ("un activo" if ep.valor_en(ilat, ilon, 0.0, am.bando_obj) else "campo abierto")
        fase = {"impulso": "subiendo (fase de impulso)", "media": "en el espacio (fase media)",
                "terminal": "reentrada (fase terminal)"}[am.fase(ep.t)]
        lineas = [(f"{am.nombre()} #{am.id} · {am.bando_atk} → {am.bando_obj} · desde {am.origen}", COLOR_TIPO[am.tipo]),
                  (f"Altitud {alt:.0f} km · {fase}", TEXTO),
                  (f"Impacto en {mmss(am.t_impacto - ep.t)} · {dest} (±{am.sigma():.0f} km)", ROJO if dest != "campo abierto" else TENUE),
                  (f"Calidad de traza {100 * am.calidad():.0f}%", TENUE)]
        if am.racimo:
            lineas.append((f"Probabilidad de ojiva real {100 * am.p_ojiva():.0f}% (racimo de {am.racimo[1]})", NARANJA))
        if am.mirv and am.final is None:
            lineas.append((f"Lleva {am.mirv[0]} ojivas y {am.mirv[1]} señuelos: se separa en {mmss(max(am.t_sep - ep.t, 0))}", ROJO))
        if am.fijada:
            lineas.append((f"Objetivo fijado desde hace {mmss(ep.t - am.t_fijada)}", ROJO))
        if sol:
            lineas.append((f"Solución {C.CAPAS[sol['capa']]['nombre']} ({sol['activo'].nombre}): Pk {100 * sol['pk']:.0f}% · "
                           f"ventana {mmss(max(sol['ventana'], 0))}", VERDE))
        else:
            lineas.append(("Sin solución de tiro por ahora", NARANJA))
        if isinstance(ep.controlador, ControladorManual):
            lineas.append(("Clic: 1 interceptor · Shift/clic der.: 2 · lo fijado se derriba solo", SUTIL))
        w = max(self.f_chica.size(t)[0] for t, _ in lineas) + 20
        h = len(lineas) * int(17 * self.k) + 12
        rr = pygame.Rect(p[0] + 18, p[1] - h // 2, w, h)
        if rr.right > self.r_mapa.right - 4:
            rr.right = p[0] - 18
        zona = self.r_mapa.copy()
        zona.top += int(50 * self.k)
        zona.height -= int(50 * self.k)
        rr.clamp_ip(zona)
        pygame.draw.rect(self.pantalla, (14, 16, 20), rr, border_radius=6)
        pygame.draw.rect(self.pantalla, BORDE, rr, 1, border_radius=6)
        y0 = rr.y + 6
        for t, c in lineas:
            self.pantalla.blit(self.f_chica.render(t, True, c), (rr.x + 10, y0))
            y0 += int(17 * self.k)

    def _barra_mapa(self):
        s = self.pantalla
        k = self.k
        r = self.r_mapa
        x = x0 = r.x + int(10 * k)
        y = r.y + int(10 * k)
        h = int(26 * k)
        fondo = pygame.Rect(x - 6, y - 6, int(470 * k), h + 12)
        pygame.draw.rect(s, (14, 16, 20), fondo, border_radius=8)
        pygame.draw.rect(s, BORDE, fondo, 1, border_radius=8)
        mouse = pygame.mouse.get_pos()
        self.btn_pausa.texto = "Seguir" if self.pausa else "Pausa"
        self.btn_pausa.rect = pygame.Rect(x, y, int(58 * k), h)
        self.btn_pausa.dibujar(s, self.f_semi, mouse, self.pausa)
        x += int(64 * k)
        for b, v in zip(self.btn_vel, VELOCIDADES):
            b.rect = pygame.Rect(x, y, int(40 * k), h)
            b.dibujar(s, self.f_semi, mouse, v == self.velocidad and not self.pausa)
            x += int(44 * k)
        img = self.f_valor.render(mmss(self.ep.t), True, TEXTO)
        s.blit(img, (x + int(8 * k), y + (h - img.get_height()) // 2))
        x += img.get_width() + int(16 * k)
        if self.ep.calma and not self.pausa and not self.preparando:
            img = self.f_mini.render("AVANCE RÁPIDO", True, ACENTO)
            s.blit(img, (x, y + (h - img.get_height()) // 2))
        self._boton_grabar(r, y, h, mouse)
        y += h + int(12 * k)
        g = int(6 * k)
        bw = int(92 * k)
        caja = pygame.Rect(x0 - 6, y - 6, 3 * bw + 2 * g + 12, h + 12)
        pygame.draw.rect(s, (14, 16, 20), caja, border_radius=8)
        pygame.draw.rect(s, BORDE, caja, 1, border_radius=8)
        for i, (b, v) in enumerate(zip(self.btn_vista, G.VISTAS)):
            b.rect = pygame.Rect(x0 + i * (bw + g), y, bw, h)
            b.dibujar(s, self.f_chica, mouse, v == self.vista)
        y += h + int(12 * k)
        self.asistente = None
        cmd = self.modo == "comandante"
        self.btn_bandos_dyn = []
        atacantes = [b for b in self.ep.bandos if b["origenes"] and b["ataca"]]
        chips = [(Boton(b["nombre"] + "  ×", lambda n=b["nombre"]: self._asis_quitar(n), color=(150, 40, 40)), None)
                 for b in atacantes]
        y = self._fila(s, "ATACANTES", y, h, g, x0, mouse, chips + [(self.btn_atacante, None)], "ataca")
        botones = self.btn_lugar[:3] + [self.btn_restaurar if not cmd else self.btn_lugar[3]]
        anchos = [int(44 * k), int(112 * k), int(92 * k), int(112 * k)]
        cw = int(260 * k)
        caja = pygame.Rect(x0 - 6, y - 6, cw + sum(anchos) + len(anchos) * g + 12, h + 12)
        pygame.draw.rect(s, (14, 16, 20), caja, border_radius=8)
        pygame.draw.rect(s, BORDE, caja, 1, border_radius=8)
        self.campo_lugar.rect = pygame.Rect(x0, y, cw, h)
        self.campo_lugar.dibujar(s, self.f_semi, self.f_chica)
        xb = x0 + cw + g
        for b, w in zip(botones, anchos):
            b.rect = pygame.Rect(xb, y, w, h)
            b.dibujar(s, self.f_chica, mouse)
            xb += w + g
        y += h + int(12 * k)
        img = self.f_mini.render("ACTIVO", True, TENUE)
        extra = [self.btn_activos[0], self.btn_activos[1], self.btn_auto]
        anchos_t = [int(62 * k)] * len(self.btn_tipos)
        anchos_e = [int(124 * k), int(104 * k), int(84 * k)][:len(extra)]
        caja = pygame.Rect(x0 - 6, y - 6, img.get_width() + sum(anchos_t) + sum(anchos_e) + (len(anchos_t) + len(anchos_e) + 1) * g + 12, h + 12)
        pygame.draw.rect(s, (14, 16, 20), caja, border_radius=8)
        pygame.draw.rect(s, BORDE, caja, 1, border_radius=8)
        s.blit(img, (x0, y + (h - img.get_height()) // 2))
        xb = x0 + img.get_width() + g
        for b, t, w in zip(self.btn_tipos, C.ORDEN_ACTIVOS, anchos_t):
            b.rect = pygame.Rect(xb, y, w, h)
            b.color = mezclar(COLOR_ACTIVO[t], FONDO, 0.3) if t == self.tipo_nuevo else None
            b.dibujar(s, self.f_mini, mouse)
            xb += w + g
        xb += g
        for b, w in zip(extra, anchos_e):
            b.rect = pygame.Rect(xb, y, w, h)
            b.dibujar(s, self.f_chica, mouse)
            xb += w + g
        y += h + int(10 * k)
        self._pie_barra(s, r, k, y, mouse)

    def _rol(self, rol, nombre, lat, lon, radio_km):
        nombre = nombre.strip()
        if not nombre or nombre.startswith("(") or G.leer_coordenadas(nombre) is not None:
            nombre = f"Punto ({lat:.2f}, {lon:.2f})"
        nombre = nombre[:24]
        bandos = self._bandos()
        b = self._bando(bandos, nombre)
        if b is None:
            b = {"nombre": nombre, "ciudades": [], "origenes": [], "ataca": [], "activos": []}
            bandos.append(b)
        nombres = [x["nombre"] for x in bandos]
        if rol == "atacante":
            o = M.origen_propio(nombre, lat, lon, radio_km or 300.0)
            for x in bandos:
                x["origenes"] = [q for q in x["origenes"] if M.clave_origen(q) != o["clave"]]
            b["origenes"].append(o)
            if self.ultimo_defensor in nombres and self.ultimo_defensor != nombre:
                destinos = [self.ultimo_defensor]
            else:
                destinos = [x["nombre"] for x in bandos if x["ciudades"] and x["nombre"] != nombre]
            for d in destinos:
                if d not in b["ataca"]:
                    b["ataca"].append(d)
            self.ultimo_atacante = nombre
            msg = (f"Atacante: {nombre} lanza desde ({lat:.2f}, {lon:.2f})" +
                   (f" contra {', '.join(destinos)}" if destinos else " · ahora elige un defensor"))
        else:
            r = min(max(radio_km or 15.0, 8.0), 60.0)
            for x in bandos:
                x["ciudades"] = [c for c in x["ciudades"] if (c if isinstance(c, str) else c["nombre"]) != nombre]
            b["ciudades"].append(MS.zona_a_dict(M.Zona(nombre, lat, lon, r, 3)))
            if not b.get("manual") and not b.get("activos"):
                b["activos"] = None
            if self.ultimo_atacante in nombres and self.ultimo_atacante != nombre:
                atacantes = [self.ultimo_atacante]
            else:
                atacantes = [x["nombre"] for x in bandos if x["origenes"] and not x["ataca"] and x["nombre"] != nombre]
            for x in bandos:
                if x["nombre"] in atacantes and nombre not in x["ataca"]:
                    x["ataca"].append(nombre)
            self.ultimo_defensor = nombre
            msg = (f"Defensor: {nombre} ({lat:.2f}, {lon:.2f}) · radio {r:.0f} km" +
                   (f" · lo ataca {', '.join(atacantes)}" if atacantes else " · ahora elige un atacante"))
        self.bando_sel = nombre
        self.campo_lugar.valor = ""
        self._guardar_bandos(self._auto(bandos), msg, encuadrar=True)
        self.avisar(msg)

    def _asis_abrir(self):
        if self.asistente:
            self._asis_cerrar()
            return
        self.asistente = 1
        self.punto = None
        self.bando_sel = "Defensa"
        self.campo_lugar.valor = ""
        self._guardar_bandos([{"nombre": "Defensa", "ciudades": [], "origenes": [], "ataca": [], "activos": None}],
                             "Paso 1: elige la ciudad que vas a defender")

    def _asis_cerrar(self):
        self.asistente = None

    def _asis_defensa(self, bandos):
        d = self._bando(bandos, "Defensa")
        if d is None:
            d = {"nombre": "Defensa", "ciudades": [], "origenes": [], "ataca": [], "activos": None}
            bandos.insert(0, d)
        return d

    def _asis_ciudades(self):
        d = next((b for b in self.ep.bandos if b["nombre"] == "Defensa"), None)
        return [c["nombre"] for c in d["ciudades"]] if d else []

    def _asis_ciudad(self, z):
        bandos = self._bandos()
        d = self._asis_defensa(bandos)
        nombres = [c if isinstance(c, str) else c["nombre"] for c in d["ciudades"]]
        if z.nombre in nombres:
            d["ciudades"] = [c for c in d["ciudades"] if (c if isinstance(c, str) else c["nombre"]) != z.nombre]
            msg = f"Ya no defiendes {z.nombre}"
        else:
            for b in bandos:
                if b is not d:
                    b["ciudades"] = [c for c in b["ciudades"] if (c if isinstance(c, str) else c["nombre"]) != z.nombre]
            d["ciudades"].append(MS.zona_a_dict(z))
            msg = f"Defiendes {z.nombre}"
        if not d.get("manual"):
            d["activos"] = None
        self.bando_sel = "Defensa"
        self._guardar_bandos(bandos, msg, encuadrar=True)

    def _asis_atacantes(self):
        return [b for b in self.ep.bandos if b["nombre"] != "Defensa" and b["origenes"]]

    def _asis_origen(self, o):
        clave = M.registrar_origen(o)
        bandos = self._bandos()
        d = self._bando(bandos, "Defensa")
        objetivos = ["Defensa"] if d else [b["nombre"] for b in bandos if b["ciudades"]]
        if not objetivos:
            d = self._asis_defensa(bandos)
            objetivos = ["Defensa"]
        la0, la1, lo0, lo1 = M.ORIGENES[clave]["caja"]
        for c in (d["ciudades"] if d else []):
            z = MS.zonas_lista([c])[0]
            if la0 <= z.lat <= la1 and lo0 <= M.desenvolver(z.lon, (lo0 + lo1) / 2) <= lo1:
                self.avisar(f"{z.nombre} quedaría dentro de la zona del atacante: elige otro")
                return
        dueno = next((b for b in bandos if b["nombre"] != "Defensa" and clave in [M.clave_origen(x) for x in b["origenes"]]), None)
        if dueno is not None and len(dueno["origenes"]) > 1:
            dueno["origenes"] = [x for x in dueno["origenes"] if M.clave_origen(x) != clave]
            msg = f"{dueno['nombre']} ya no lanza desde {M.ORIGENES[clave]['nombre']}"
        elif dueno is not None:
            bandos = [b for b in bandos if b is not dueno]
            msg = f"{dueno['nombre']} ya no ataca"
        else:
            nombre = M.ORIGENES[clave]["nombre"][:24]
            usados = {b["nombre"] for b in bandos}
            base, n = nombre, 2
            while nombre in usados:
                nombre = f"{base[:20]} {n}"
                n += 1
            bandos.append({"nombre": nombre, "ciudades": [], "origenes": [o], "ataca": objetivos, "activos": []})
            msg = f"{nombre} ataca a {', '.join(objetivos)}"
        if d and not d.get("manual"):
            d["activos"] = None
        self._guardar_bandos(self._auto(bandos), msg, encuadrar=True)

    def _asis_choca(self, d, cajas):
        for c in d["ciudades"]:
            z = MS.zonas_lista([c])[0]
            for la0, la1, lo0, lo1 in cajas:
                if la0 <= z.lat <= la1 and lo0 <= M.desenvolver(z.lon, (lo0 + lo1) / 2) <= lo1:
                    return z.nombre
        return None

    def _asis_quitar(self, nombre):
        bandos = [b for b in self._bandos() if b["nombre"] != nombre]
        for b in bandos:
            b["ataca"] = [x for x in b["ataca"] if x != nombre]
        self._guardar_bandos(self._auto(bandos), f"{nombre} ya no ataca")

    def _asis_pais(self, nombre):
        bandos = self._bandos()
        if self._bando(bandos, nombre) is not None and nombre != "Defensa":
            self._asis_quitar(nombre)
            return
        d = self._bando(bandos, "Defensa")
        objetivos = ["Defensa"] if d else [b["nombre"] for b in bandos if b["ciudades"]]
        if not objetivos:
            d = self._asis_defensa(bandos)
            objetivos = ["Defensa"]
        if nombre in M.ZONAS_PAIS:
            origenes = list(M.ZONAS_PAIS[nombre])
        else:
            lat, lon, r = M.PAISES[nombre]
            origenes = [M.origen_propio(nombre, lat, lon, r)]
        cajas = [M.ORIGENES[M.registrar_origen(o)]["caja"] for o in origenes]
        choque = self._asis_choca(d, cajas) if d else None
        if choque:
            self.avisar(f"{choque} está dentro de {nombre}: no puede atacarse a sí misma, quita esa ciudad o elige otro país")
            return
        bandos.append({"nombre": nombre, "ciudades": [], "origenes": origenes, "ataca": objetivos, "activos": []})
        if d and not d.get("manual"):
            d["activos"] = None
        self._guardar_bandos(self._auto(bandos), f"{nombre} ataca a {', '.join(objetivos)}", encuadrar=True)

    def _asis_agregar(self):
        if self.asistente not in (1, 2):
            return
        if not self.campo_lugar.valor.strip():
            self.avisar("Escribe una ciudad, un país o «lat, lon»")
            return
        self._buscar(f"asis_{self.asistente}")

    def _asis_paso(self, d):
        if d > 0 and self.asistente == 1 and not self._asis_ciudades():
            self.avisar("Primero elige al menos una ciudad para defender")
            return
        if d > 0 and self.asistente == 2 and not self._asis_atacantes():
            self.avisar("Primero elige al menos un atacante")
            return
        self.asistente = max(1, min(3, self.asistente + d))
        self.campo_lugar.valor = ""

    def _asis_auto(self):
        bandos = self._bandos()
        d = self._asis_defensa(bandos)
        d["manual"] = False
        d["tipos"] = None
        d["activos"] = None
        self._guardar_bandos(bandos, "Defensa acomodada automáticamente")

    def _asis_vaciar(self):
        bandos = self._bandos()
        d = self._asis_defensa(bandos)
        d["manual"] = True
        d["activos"] = []
        self._guardar_bandos(bandos, "Sin baterías: haz clic en el mapa para ponerlas")

    def _asis_listo(self):
        if not self._asis_ciudades() or not self._asis_atacantes():
            self.avisar("Faltan la ciudad a defender o el atacante")
            return
        self.asistente = None
        self._nuevo_ep()
        self._encuadrar()
        bat = sum(1 for a in self.ep.activos if a.bando == "Defensa")
        self.ep.log(f"Escenario listo: defiendes {', '.join(self._asis_ciudades())} de "
                    f"{', '.join(b['nombre'] for b in self._asis_atacantes())} con {bat} baterías", "verde")
        if self.preparando:
            self._comenzar()

    def _asis_clic(self, pos):
        lat, lon = self.a_mundo(*pos)
        if self.asistente == 1:
            for z in self.ep.zonas + self._candidatas():
                p = self.a_pantalla(z.lat, z.lon)
                if math.hypot(p[0] - pos[0], p[1] - pos[1]) <= max(self._km_px(z.r, z.lat), 9 * self.k):
                    self._asis_ciudad(z)
                    return
            self._asis_ciudad(M.Zona(f"Punto ({lat:.2f}, {lon:.2f})", lat, lon, 15.0, 3))
        elif self.asistente == 2:
            clave = M.en_origen(lat, lon)
            if clave is not None:
                self._asis_origen(clave if not M.ORIGENES[clave].get("propio") else
                                  {"clave": clave, "nombre": M.ORIGENES[clave]["nombre"], "caja": list(M.ORIGENES[clave]["caja"])})
            else:
                self._asis_origen(M.origen_propio(f"Atacante ({lat:.1f}, {lon:.1f})", lat, lon, 300.0))
        else:
            i = self._activo_en_pantalla(pos)
            if i is not None:
                self.act_sel = i
                return
            self.bando_sel = "Defensa"
            self._activo_en(lat, lon)

    def _dibujar_asistente(self, s, x0, y, h, g, mouse):
        k, r = self.k, self.r_mapa
        paso = self.asistente
        for b in self.btn_asis.values():
            b.rect = pygame.Rect(0, 0, 0, 0)
        self.btn_asis_dyn = []
        ancho = int(min(r.w - 24 * k, 860 * k))
        titulos = {1: "Paso 1 de 3 · ¿Qué ciudad vas a defender?", 2: "Paso 2 de 3 · ¿Quién te ataca?",
                   3: "Paso 3 de 3 · ¿Desde dónde defiendes?"}
        ayudas = {1: "Haz clic en una ciudad de la lista o del mapa. Si no está, escríbela abajo y presiona Enter. Puedes elegir varias.",
                  2: "Haz clic en uno o varios países de la lista. Si no está, escríbelo abajo y presiona Enter, o haz clic en el mapa donde quieras.",
                  3: "Ya puse baterías automáticas. Para cambiarlas: elige el tipo y haz clic en el mapa; clic derecho sobre una batería la quita."}
        items = []
        if paso == 1:
            elegidas = self._asis_ciudades()
            for n in CIUDADES_RAPIDAS + [c for c in elegidas if c not in CIUDADES_RAPIDAS]:
                sel = n in elegidas
                items.append(Boton(("• " if sel else "") + n, lambda n=n: self._asis_ciudad(
                    next((z for z in self.ep.zonas if z.nombre == n), None) or M.ciudad(n)), color=(30, 120, 90) if sel else None))
        elif paso == 2:
            atacantes = self._asis_atacantes()
            nombres = {x["nombre"] for x in atacantes}
            claves = {M.clave_origen(o) for x in atacantes for o in x["origenes"]}
            for n in sorted(M.PAISES):
                sel = n in nombres
                items.append(Boton(("• " if sel else "") + n, lambda n=n: self._asis_pais(n),
                                   color=(150, 40, 40) if sel else None))
            for c in ("pac_este", "pac_norte", "atlantico", "barents"):
                sel = c in claves
                items.append(Boton(("• " if sel else "") + M.ORIGENES[c]["nombre"].replace("Submarino · ", "Submarino "),
                                   lambda c=c: self._asis_origen(c), color=(150, 40, 40) if sel else None))
            for x in atacantes:
                if x["nombre"] not in M.PAISES and not any(M.clave_origen(o) in ("pac_este", "pac_norte", "atlantico", "barents") for o in x["origenes"]):
                    items.append(Boton("• " + x["nombre"], lambda n=x["nombre"]: self._asis_quitar(n), color=(150, 40, 40)))
        else:
            for t in C.ORDEN_ACTIVOS:
                b = self.btn_tipos[C.ORDEN_ACTIVOS.index(t)]
                b.color = mezclar(COLOR_ACTIVO[t], FONDO, 0.3) if t == self.tipo_nuevo else None
                items.append(b)
            items += [self.btn_asis["auto"], self.btn_asis["vaciar"]]
        filas, fila, xb = [], [], x0 + int(10 * k)
        for b in items:
            w = self.f_chica.size(b.texto)[0] + int(20 * k)
            if fila and xb + w > x0 + ancho - int(10 * k):
                filas.append(fila)
                fila, xb = [], x0 + int(10 * k)
            fila.append((b, xb, w))
            xb += w + g
        if fila:
            filas.append(fila)
        lineas = self._envolver(ayudas[paso], self.f_chica, ancho - 24 * k)
        alto = int(34 * k) + len(lineas) * int(17 * k) + len(filas) * (h + g) + (h + int(14 * k)) * (2 if paso < 3 else 1) + int(12 * k)
        caja = pygame.Rect(x0 - 6, y - 6, ancho, alto)
        self._caja_asis = caja
        pygame.draw.rect(s, (14, 16, 20), caja, border_radius=10)
        pygame.draw.rect(s, ACENTO, caja, 2, border_radius=10)
        yy = y + int(2 * k)
        s.blit(self.f_titulo.render(titulos[paso], True, ACENTO), (x0 + int(10 * k), yy))
        yy += int(32 * k)
        for l in lineas:
            s.blit(self.f_chica.render(l, True, TEXTO), (x0 + int(10 * k), yy))
            yy += int(17 * k)
        yy += int(4 * k)
        self.btn_asis_dyn = []
        for fila in filas:
            for b, xb, w in fila:
                b.rect = pygame.Rect(xb, yy, w, h)
                b.dibujar(s, self.f_chica, mouse)
                if b not in self.btn_tipos and b not in self.btn_asis.values():
                    self.btn_asis_dyn.append(b)
            yy += h + g
        yy += int(6 * k)
        if paso < 3:
            self.campo_lugar.rect = pygame.Rect(x0 + int(10 * k), yy, int(300 * k), h)
            self.campo_lugar.dibujar(s, self.f_semi, self.f_chica)
            self.btn_asis["agregar"].rect = pygame.Rect(self.campo_lugar.rect.right + g, yy, int(90 * k), h)
            self.btn_asis["agregar"].dibujar(s, self.f_chica, mouse)
            yy += h + int(14 * k)
        xb = x0 + int(10 * k)
        for clave in (["atras"] if paso > 1 else []) + (["sig"] if paso < 3 else ["listo"]) + ["cerrar"]:
            b = self.btn_asis[clave]
            w = self.f_semi.size(b.texto)[0] + int(28 * k)
            b.rect = pygame.Rect(xb, yy, w, h)
            b.dibujar(s, self.f_semi, mouse)
            xb += w + g
        return caja.bottom + int(12 * k)

    def _agregar_atacante(self):
        texto = self.campo_lugar.valor.strip()
        if not texto:
            if self.punto is None:
                self.avisar("Escribe el país atacante en «Lugar» (o haz clic en el mapa) y presiona «+ Atacante»")
                return
            lat, lon = self.punto
            self._asis_origen(M.origen_propio(f"Atacante ({lat:.1f}, {lon:.1f})", lat, lon, 300.0))
            return
        pais = next((p for p in M.PAISES if p.lower() == texto.lower()), None)
        if pais is not None:
            self.campo_lugar.valor = ""
            self._asis_pais(pais)
            return
        self._buscar("asis_2")

    def _proteger_ciudad(self):
        texto = self.campo_lugar.valor.strip()
        if not texto:
            if self.punto is None:
                self.avisar("Escribe la ciudad en «Lugar» (o haz clic en el mapa) y presiona «Proteger ciudad»")
                return
            lat, lon = self.punto
            self._asis_ciudad(M.Zona(f"Punto ({lat:.2f}, {lon:.2f})", lat, lon, 15.0, 3))
            return
        conocida = next((n for n in M.CIUDADES if n.lower() == texto.lower()), None)
        if conocida is not None:
            self.campo_lugar.valor = ""
            self._clic_ciudad(next((z for z in self.ep.zonas if z.nombre == conocida), None) or M.ciudad(conocida))
            return
        self._buscar("asis_1")

    def _clic_ciudad(self, z):
        if not any(b["nombre"] == "Defensa" for b in self.ep.bandos) and any(z2.bando for z2 in self.ep.zonas):
            self.bando_sel = z.bando if (z.activa and z.bando) else self._bando_cercano(z.lat, z.lon)
            self._toggle_ciudad(z)
            return
        self._asis_ciudad(z)

    def _bando_cercano(self, lat, lon):
        con = [z for z in self.ep.zonas if z.activa and z.bando]
        if not con:
            return self._sel()
        return min(con, key=lambda z: z.distancia(lat, lon)).bando

    def _guia_ataque(self, b):
        ep = self.ep
        if b is None:
            return "Escribe un país, ciudad o coordenadas en «Lugar» y presiona «Atacante» o «Defensor»", NARANJA
        n = b["nombre"]
        enemigos = [x["nombre"] for x in ep.bandos if n in x["ataca"] and x["origenes"]]
        if b["ciudades"] and not b["ataca"]:
            if enemigos:
                return (f"{n} se defiende de {', '.join(enemigos)}" +
                        (" · presiona «¡Comenzar ataque!»" if self.preparando else "") +
                        " · para que también ataque: «Lanza desde aquí» y marca al enemigo"), VERDE
            return f"Nadie ataca a {n} · escribe un país en «Lugar» y presiona «Atacante»", NARANJA
        if not b["origenes"]:
            return (f"Para que {n} ataque · paso 1: clic en una zona rayada del mapa (o escribe un país en «Lugar» "
                    f"y «Lanza desde aquí»)"), NARANJA
        if not b["ataca"]:
            return f"Para que {n} ataque · paso 2: en la fila «{n.upper()} ATACA A» haz clic en el enemigo (se pone rojo)", NARANJA
        sin = [x for x in b["ataca"] if not any(z.bando == x for z in ep.zonas)]
        if len(sin) == len(b["ataca"]):
            return (f"Paso 3: {', '.join(sin)} no tiene ciudades · elige ese bando en BANDO y haz clic en sus ciudades"), NARANJA
        fin = " · presiona «¡Comenzar ataque!»" if self.preparando else ""
        return f"Listo: {n} ataca a {', '.join(x for x in b['ataca'] if x not in sin)}{fin}", VERDE

    def _elegir_bando(self, nombre):
        self.bando_sel = nombre
        self._cache_mapa = None

    def _fila(self, s, titulo, y, h, g, x0, mouse, items, clave):
        k = self.k
        img = self.f_mini.render(titulo, True, TENUE)
        xb = x0 + img.get_width() + g
        botones = []
        for b, w in items:
            w = w or self.f_chica.size(b.texto)[0] + int(18 * k)
            b.rect = pygame.Rect(xb, y, w, h)
            botones.append(b)
            xb += w + g
        caja = pygame.Rect(x0 - 6, y - 6, xb - x0 + 6, h + 12)
        pygame.draw.rect(s, (14, 16, 20), caja, border_radius=8)
        pygame.draw.rect(s, BORDE, caja, 1, border_radius=8)
        s.blit(img, (x0, y + (h - img.get_height()) // 2))
        for b in botones:
            b.dibujar(s, self.f_chica, mouse)
        dinamicos = [b for b in botones if b not in self.btn_bando_ops and b is not self.btn_atacante]
        if clave == "bandos":
            self.btn_bandos_dyn = dinamicos
        else:
            self.btn_ataca_dyn = dinamicos
        return y + h + int(12 * k)

    def _pie_barra(self, s, r, k, y, mouse):
        x0 = r.x + int(10 * k)
        if self.ocupado_geo:
            img = self.f_chica.render(self.ocupado_geo, True, ACENTO)
            caja = img.get_rect(topleft=(x0, y))
            pygame.draw.rect(s, (14, 16, 20), caja.inflate(14, 8), border_radius=6)
            s.blit(img, caja)
            y += img.get_height() + int(8 * k)
        pie = (f"Arrastrar: mover mapa · rueda: zoom · Inicio: encuadrar · clic en amenaza: ficha"
               f"{' / disparar' if isinstance(self.ep.controlador, ControladorManual) else ''} · V: verdad {'ON' if self.verdad else 'OFF'}")
        img = self.f_mini.render(pie, True, (200, 205, 215))
        caja = img.get_rect(bottomright=(r.right - 8, r.bottom - 8 * k))
        pygame.draw.rect(s, (14, 16, 20), caja.inflate(12, 6), border_radius=5)
        s.blit(img, caja)
        img = self.f_mini.render(G.ATRIBUCIONES[self.vista], True, (200, 205, 215))
        caja2 = img.get_rect(bottomleft=(r.x + 10 * k, r.bottom - 8 * k))
        pygame.draw.rect(s, (14, 16, 20), caja2.inflate(10, 4), border_radius=4)
        s.blit(img, caja2)
        if self._faltan_teselas:
            img = self.f_mini.render(f"Cargando mapa… {self._faltan_teselas} teselas", True, ACENTO)
            s.blit(img, (caja2.x, caja2.y - img.get_height() - 4))
        mx, my = mouse
        if r.collidepoint(mx, my):
            la, lo = self.a_mundo(mx, my)
            img = self.f_semi.render(f"{abs(la):.3f}°{'N' if la >= 0 else 'S'}  {abs(lo):.3f}°{'E' if lo >= 0 else 'O'}", True, TEXTO)
            caja = img.get_rect(topright=(r.right - 10, self.btn_grabar.rect.bottom + int(14 * k)))
            pygame.draw.rect(s, (14, 16, 20), caja.inflate(14, 8), border_radius=6)
            s.blit(img, caja)
        if self.grabador.grabando:
            img = self.f_semi.render(f"● REC {mmss(time.perf_counter() - self.grabador.inicio)}", True, (255, 255, 255))
            caja = img.get_rect(midtop=(r.centerx, r.y + 12))
            pygame.draw.rect(s, (200, 40, 40), caja.inflate(16, 8), border_radius=10)
            s.blit(img, caja)
        txt, t0 = self.aviso
        if txt and time.time() - t0 < 4:
            img = self.f_semi.render(txt, True, TEXTO)
            caja = img.get_rect(midtop=(r.centerx, y + int(4 * k)))
            pygame.draw.rect(s, (14, 16, 20), caja.inflate(20, 10), border_radius=8)
            pygame.draw.rect(s, ACENTO, caja.inflate(20, 10), 1, border_radius=8)
            s.blit(img, caja)

    def _boton_grabar(self, r, y, h, mouse):
        s, k, b = self.pantalla, self.k, self.btn_grabar
        g = self.grabador
        b.rect = pygame.Rect(r.right - int(10 * k) - int(170 * k), y, int(170 * k), h)
        caja = b.rect.inflate(12, 12)
        pygame.draw.rect(s, (14, 16, 20), caja, border_radius=8)
        pygame.draw.rect(s, BORDE, caja, 1, border_radius=8)
        if g.grabando:
            b.texto = f"Stop  {mmss(time.perf_counter() - g.inicio)}"
            b.color = (176, 32, 36)
        else:
            b.texto = "Grabar pantalla"
            b.color = None
        b.dibujar(s, self.f_semi, mouse)
        pygame.draw.rect(s, (239, 83, 80), b.rect, 1, border_radius=6)
        cy = b.rect.centery
        if g.grabando:
            if int(time.perf_counter() * 2) % 2 == 0:
                lado = int(10 * k)
                pygame.draw.rect(s, (255, 255, 255), (b.rect.x + int(9 * k), cy - lado // 2, lado, lado))
        else:
            pygame.draw.circle(s, (239, 83, 80), (b.rect.x + int(14 * k), cy), int(6 * k))

    def _tarjeta(self, r, titulo=None):
        pygame.draw.rect(self.pantalla, TARJETA, r, border_radius=8)
        pygame.draw.rect(self.pantalla, BORDE, r, 1, border_radius=8)
        if titulo:
            self.pantalla.blit(self.f_mini.render(titulo.upper(), True, TENUE), (r.x + 12 * self.k, r.y + 8 * self.k))
        return r.y + int(28 * self.k)

    def _dibujar_log(self):
        r = self.r_log
        y = self._tarjeta(r, "Bitácora de combate")
        s = self.pantalla
        lh = int(17 * self.k)
        n = (r.bottom - y - 6) // lh
        prev = s.get_clip()
        s.set_clip(r.inflate(-8, -4))
        for t, txt, c in (self.ep.bitacora or [])[-n:]:
            s.blit(self.f_mini.render(mmss(t), True, SUTIL), (r.x + 12 * self.k, y + 2))
            s.blit(self.f_chica.render(txt, True, COLOR_LOG.get(c, TEXTO)), (r.x + 62 * self.k, y))
            y += lh
        s.set_clip(prev)

    def _dibujar_perfil(self):
        r = self.r_perfil
        ep = self.ep
        y0 = self._tarjeta(r, "Perfil de vuelo · altitud (km) contra distancia al impacto")
        s = self.pantalla
        k = self.k
        mouse = pygame.mouse.get_pos()
        bw = [int(52 * k), int(92 * k)]
        x = r.right - int(10 * k) - sum(bw) - int(4 * k)
        for b, w, sel in zip(self.btn_perfil, bw, (self.perfil_todas, not self.perfil_todas)):
            b.rect = pygame.Rect(x, r.y + int(5 * k), w, int(20 * k))
            b.dibujar(s, self.f_mini, mouse, sel)
            x += w + int(4 * k)
        g = pygame.Rect(r.x + int(48 * k), y0 + 4, r.w - int(60 * k), r.bottom - y0 - int(26 * k))
        dmin, dmax, zmax = 10.0, 15000.0, 1800.0

        def gx(d):
            return g.x + g.w * (math.log10(min(max(d, dmin), dmax)) - 1) / (math.log10(dmax) - 1)

        def gy(z):
            return g.bottom - g.h * math.sqrt(min(max(z, 0.0), zmax) / zmax)

        env = pygame.Surface(g.size, pygame.SRCALPHA)
        for capa in ("exo", "alta", "baja"):
            lo, hi = C.CAPAS[capa]["alt"]
            col = COLOR_CAPA[capa]
            pygame.draw.rect(env, (*col, 26), (0, gy(hi) - g.y, g.w, gy(lo) - gy(hi)))
        s.blit(env, g.topleft)
        for capa in ("exo", "alta", "baja"):
            lo, hi = C.CAPAS[capa]["alt"]
            img = self.f_mini.render(C.CAPAS[capa]["corto"], True, COLOR_CAPA[capa])
            s.blit(img, (g.right - img.get_width() - 4, (gy(lo) + gy(hi)) / 2 - img.get_height() / 2))
        for d in (10, 100, 1000, 10000):
            xx = gx(d)
            pygame.draw.line(s, REJILLA, (xx, g.y), (xx, g.bottom))
            s.blit(self.f_mini.render(f"{d:,} km".replace(",", " "), True, SUTIL), (xx + 2, g.bottom + 3))
        for zk in (10, 40, 90, 150, 500, 1000, 1800):
            yy = gy(zk)
            pygame.draw.line(s, REJILLA if zk != 90 else (90, 60, 60), (g.x, yy), (g.right, yy))
            s.blit(self.f_mini.render(f"{zk}", True, SUTIL), (r.x + 8 * k, yy - 7))
        elegida = next((a for a in ep.activas if a.id == self.seleccion), None)
        lista = [a for a in ep.activas if a.detectada]
        if not self.perfil_todas and elegida is not None:
            lista = [elegida]
        prev = s.get_clip()
        s.set_clip(g.inflate(8, 8))
        for am in lista:
            col = COLOR_TIPO[am.tipo] if am.p_ojiva() >= 0.25 else GRIS_SENUELO
            ilat, ilon = am.impacto_est()
            pts = [(gx(M.distancia(q[0], q[1], ilat, ilon)), gy(q[2])) for q in am.rastro[-60:]]
            la, lo, alt = am.latlon(ep.t)
            pts.append((gx(M.distancia(la, lo, ilat, ilon)), gy(alt)))
            if len(pts) > 1:
                pygame.draw.lines(s, mezclar(col, FONDO, 0.35), False, pts, 1)
            pygame.draw.circle(s, col, pts[-1], 3.5 * k)
            if am.fijada:
                pygame.draw.circle(s, ROJO, pts[-1], 6 * k, 1)
        for it in ep.interceptores:
            if ep.t < it.t_lanz or (not self.perfil_todas and it.am is not elegida):
                continue
            ilat, ilon = it.am.impacto_est()
            la, lo, alt = M.latlon(it.pos(ep.t))
            pts = [(gx(M.distancia(q[0], q[1], ilat, ilon)), gy(q[2])) for q in it.rastro[-40:]]
            pts.append((gx(M.distancia(la, lo, ilat, ilon)), gy(alt)))
            if len(pts) > 1:
                pygame.draw.lines(s, COLOR_CAPA[it.capa], False, pts, 1)
            pygame.draw.circle(s, (235, 250, 255), pts[-1], 2.5 * k)
        s.set_clip(prev)

    def _panel(self):
        s = self.pantalla
        k = self.k
        r = self.r_panel
        mouse = pygame.mouse.get_pos()
        ep = self.ep
        x, y = r.x, r.y
        img = self.f_titulo.render("Escudo Global", True, TEXTO)
        s.blit(img, (x, y))
        y += img.get_height()
        s.blit(self.f_chica.render("Defensa antimisiles por capas · control de tiro con IA", True, TENUE), (x, y))
        y += int(24 * k)
        bw = (r.w - 3 * int(6 * k)) // 4
        for i, (b, (m, _)) in enumerate(zip(self.btn_modos, MODOS)):
            b.rect = pygame.Rect(x + i * (bw + int(6 * k)), y, bw, int(30 * k))
            b.dibujar(s, self.f_semi, mouse, m == self.modo)
        y += int(40 * k)
        tr = pygame.Rect(x, y, r.w, int(96 * k))
        yy = self._tarjeta(tr, "Escenario")
        nombre = ep.m["nombre"] if ep.continuo else f"{self.mision_n}. {ep.m['nombre']}"
        s.blit(self.f_semi.render(nombre, True, TEXTO), (x + 12 * k, yy))
        if self.modo in ("campeon", "jugar"):
            for i, b in enumerate(self.btn_mis):
                b.rect = pygame.Rect(tr.right - int((70 - 34 * i) * k), tr.y + 6 * k, int(30 * k), int(24 * k))
                b.dibujar(s, self.f_semi, mouse)
        for i, l in enumerate(self._envolver(ep.m["descripcion"], self.f_chica, tr.w - 24 * k)[:2]):
            s.blit(self.f_chica.render(l, True, TENUE), (x + 12 * k, yy + int((20 + 15 * i) * k)))
        s.blit(self.f_mini.render(self.ep_info, True, ACENTO), (x + 12 * k, tr.bottom - 18 * k))
        y = tr.bottom + int(8 * k)
        a = self._act()
        sel_b = self._sel()
        n_l = len(a.misiles) if a is not None else 0
        por_fila = max(min(n_l, 4), 1)
        filas = (n_l + por_fila - 1) // por_fila if n_l else 1
        tr = pygame.Rect(x, y, r.w, int((112 + 28 * filas) * k))
        propios = [(i, v) for i, v in enumerate(ep.activos) if v.bando == sel_b]
        total = sum(sum(v.misiles) for _, v in propios if not v.destruida)
        vivos = sum(1 for _, v in propios if not v.destruida)
        titulo = f"Activos de {sel_b} · {vivos}/{len(propios)} · {total} interceptores" if len(ep.bandos) > 1 else \
            f"Activos · {vivos}/{len(propios)} operativos · {total} interceptores"
        yy = self._tarjeta(tr, titulo)
        self._tabs = []
        tx = x + 12 * k
        fila_tabs = 0
        if not propios:
            s.blit(self.f_chica.render("Sin activos: clic derecho en el mapa para poner el tipo elegido", True, TENUE), (tx, yy + 4 * k))
        for i, v in propios:
            col_t = COLOR_ACTIVO[v.tipo] if not v.destruida else ROJO
            if tx + 44 * k > tr.right - 8 * k:
                tx = x + 12 * k
                fila_tabs += 1
                if fila_tabs > 0:
                    break
            rr = pygame.Rect(tx, yy, int(40 * k), int(22 * k))
            elegido = v is a
            pygame.draw.rect(s, mezclar(col_t, FONDO, 0.15) if elegido else TARJETA2, rr, border_radius=5)
            pygame.draw.rect(s, col_t, rr, 1, border_radius=5)
            img = self.f_mini.render(v.nombre, True, FONDO if elegido else TEXTO)
            s.blit(img, img.get_rect(center=rr.center))
            self._tabs.append((rr, i))
            tx += int(44 * k)
        yy += int(30 * k)
        if a is not None:
            etq, col = ESTADOS[a.estado]
            chip = self.f_mini.render(etq, True, FONDO)
            cr = chip.get_rect(topright=(tr.right - 12 * k, tr.y + 7 * k)).inflate(14, 6)
            pygame.draw.rect(s, col, cr, border_radius=cr.h // 2)
            s.blit(chip, chip.get_rect(center=cr.center))
            info = f"{a.q['nombre']} · ({a.lat:.2f}, {a.lon:.2f})"
            if a.estado == "desplegando":
                info += f" · listo en {mmss(a.timer)}"
            s.blit(self.f_semi.render(info, True, COLOR_ACTIVO[a.tipo]), (x + 12 * k, yy))
            if a.capa is None:
                s.blit(self.f_chica.render("Sin interceptores: rastrea y discrimina ojivas de señuelos.", True, TENUE),
                       (x + 12 * k, yy + 24 * k))
            lw = (tr.w - 24 * k - (por_fila - 1) * 8 * k) / por_fila
            for i in range(n_l):
                lx = x + 12 * k + (i % por_fila) * (lw + 8 * k)
                ly = yy + 24 * k + (i // por_fila) * int(28 * k)
                frac = a.misiles[i] / max(a.por_lanzador, 1)
                s.blit(self.f_mini.render(f"Lanzador {i + 1}" if por_fila < 4 else f"L{i + 1}", True, TENUE), (lx, ly))
                txt = f"{a.misiles[i]}" if a.recarga_t[i] <= 0 else f"recarga {mmss(a.recarga_t[i])}"
                img = self.f_mini.render(txt, True, TEXTO)
                s.blit(img, (lx + lw - img.get_width(), ly))
                pygame.draw.rect(s, REJILLA, (lx, ly + 17 * k, lw, 6 * k), border_radius=3)
                pygame.draw.rect(s, COLOR_ACTIVO[a.tipo] if frac > 0.25 else NARANJA, (lx, ly + 17 * k, lw * frac, 6 * k), border_radius=3)
            capa = C.CAPAS[a.capa] if a.capa else None
            pie = (f"Radar {a.radar:.0f} km" + (f" · capa {capa['nombre']} · alcance {capa['alcance']:.0f} km · "
                                                   f"altitud {capa['alt'][0]:.0f}-{capa['alt'][1]:.0f} km" if capa else "")
                   + (f" · recargas {a.recargas if a.recargas < 90 else '∞'}" if capa else ""))
            s.blit(self.f_mini.render(pie, True, SUTIL), (x + 12 * k, tr.bottom - 18 * k))
        y = tr.bottom + int(8 * k)
        st = ep.st
        extra = st.get("nucleares", 0) or st.get("contra_lanzados", 0)
        tr = pygame.Rect(x, y, r.w, int((160 if extra else 118) * k))
        yy = self._tarjeta(tr, "Combate")
        datos = [("Detectadas", f"{st['detectadas']}", AZUL), ("Derribadas", f"{st['interceptadas']}", VERDE),
                 ("Impactos en zonas", f"{st['impactos_zona']}", ROJO if st['impactos_zona'] else TEXTO),
                 ("Señuelos (quemados)", f"{st['senuelos']} ({st['quemados']})", TENUE),
                 ("Interceptores", f"{st['usados']}", CIAN),
                 ("Desperdicio", f"{100 * ep.desperdicio():.0f}%", NARANJA if ep.desperdicio() > C.DESPERDICIO_MAX else TEXTO),
                 ("Protección", f"{100 * ep.proteccion():.0f}%", VERDE if ep.proteccion() >= C.PROTECCION_MIN else ROJO),
                 ("Fallos", f"{st['fallos']}", TEXTO)]
        if extra:
            datos += [("Nucleares (cayeron)", f"{st['nucleares']} ({st['nucleares_impacto']})",
                       ROJO if st["nucleares_impacto"] else AMARILLO_NUC),
                      ("Contraataque", f"{st['contra_impactos']}/{st['contra_lanzados']}", AZUL)]
        cw = (tr.w - 24 * k) / 4
        for i, (et, v, c) in enumerate(datos):
            cx = x + 12 * k + (i % 4) * cw
            cy = yy + (i // 4) * int(42 * k)
            s.blit(self.f_mini.render(et, True, TENUE), (cx, cy))
            s.blit(self.f_valor.render(v, True, c), (cx, cy + 13 * k))
        y = tr.bottom + int(8 * k)
        resto = pygame.Rect(x, y, r.w, r.bottom - y)
        if self.modo == "entrenar":
            self._panel_entrenar(resto, mouse)
        elif self.modo == "campeon":
            self._panel_ia(resto, mouse)
        elif self.modo == "jugar":
            self._panel_jugar(resto, mouse)
        else:
            self._panel_comandante(resto, mouse)

    def _envolver(self, texto, f, ancho):
        lineas, actual = [], ""
        for p in texto.split():
            prueba = (actual + " " + p).strip()
            if f.size(prueba)[0] > ancho and actual:
                lineas.append(actual)
                actual = p
            else:
                actual = prueba
        if actual:
            lineas.append(actual)
        return lineas

    def _pensamiento(self, tr, y):
        s = self.pantalla
        k = self.k
        ctl = self.ep.controlador
        ult = getattr(ctl, "ultima", None)
        s.blit(self.f_mini.render("LO QUE DECIDE LA RED (última evaluación)", True, TENUE), (tr.x + 12 * k, y))
        y += int(18 * k)
        if not ult or not isinstance(ctl, B.ControladorRed):
            s.blit(self.f_chica.render("Sin amenazas que evaluar", True, SUTIL), (tr.x + 12 * k, y))
            return y + int(20 * k)
        cands, X, Y = ult
        orden = np.argsort(-Y[:, 0])[:6]
        bw = int(100 * k)
        for i in orden:
            am, sol = cands[i]
            if y > tr.bottom - 22 * k:
                break
            ilat, ilon = am.impacto_est()
            z = self.ep.zona_en(ilat, ilon, am.sigma() * 0.6)
            dest = z.nombre if z else ("activo" if self.ep.valor_en(ilat, ilon) else "campo")
            capa = C.CAPAS[sol["capa"]]["corto"] if sol else "sin sol."
            txt = f"#{am.id} {am.nombre().split()[0]} → {dest} · {capa}"
            s.blit(self.f_chica.render(txt[:38], True, COLOR_TIPO[am.tipo] if am.viva else SUTIL), (tr.x + 12 * k, y))
            bx = tr.right - bw - 50 * k
            v = float(Y[i, 0])
            pygame.draw.rect(s, REJILLA, (bx, y + 5 * k, bw, 8 * k), border_radius=4)
            mid = bx + bw / 2
            col = VERDE if v > 0 else ROJO
            pygame.draw.rect(s, col, (min(mid, mid + v * bw / 2), y + 5 * k, abs(v) * bw / 2, 8 * k), border_radius=4)
            s.blit(self.f_mini.render("FUEGO" if v > 0 else "espera", True, col), (bx + bw + 6 * k, y + 1))
            y += int(20 * k)
        return y

    def _grafica(self, g):
        s = self.pantalla
        hist = self.ent.historial[-300:]
        pygame.draw.rect(s, TARJETA2, g, border_radius=4)
        for f in (0.25, 0.5, 0.75):
            yy = g.bottom - g.h * f
            pygame.draw.line(s, REJILLA, (g.x, yy), (g.right, yy))
        if len(hist) < 2:
            img = self.f_chica.render("La gráfica aparece tras 2 generaciones", True, SUTIL)
            s.blit(img, img.get_rect(center=g.center))
            return
        n = len(hist)
        tonos = [AZUL, MORADO, CIAN, NARANJA, VERDE, (255, 120, 200), ACENTO, ROJO, (120, 220, 120), (200, 200, 255)]
        ini = 0
        for i in range(1, n + 1):
            if i == n or hist[i]["mision"] != hist[ini]["mision"]:
                x0 = g.x + g.w * ini / (n - 1)
                x1 = g.x + g.w * (i - 1) / (n - 1)
                col = tonos[(hist[ini]["mision"] - 1) % len(tonos)]
                banda = pygame.Surface((max(1, int(x1 - x0) + 1), g.h), pygame.SRCALPHA)
                banda.fill((*col, 28))
                s.blit(banda, (x0, g.y))
                if x1 - x0 > 12:
                    s.blit(self.f_mini.render(str(hist[ini]["mision"]), True, col), (x0 + 3, g.y + 2))
                ini = i
        for clave, col in (("promedio_proteccion", (120, 130, 150)), ("mejor_proteccion", VERDE)):
            pts = [(g.x + g.w * i / (n - 1), g.bottom - g.h * h[clave] / 100) for i, h in enumerate(hist)]
            pygame.draw.lines(s, col, False, pts, 2)
        pts = [(g.x + g.w * i / (n - 1), g.bottom - g.h * h["superaron_pct"] / 100) for i, h in enumerate(hist)]
        pygame.draw.lines(s, ACENTO, False, pts, 1)

    def _panel_entrenar(self, tr, mouse):
        s = self.pantalla
        k = self.k
        y = self._tarjeta(tr, "Entrenamiento de la IA")
        ent, hilo = self.ent, self.hilo
        mis = ent.mision_actual
        teatro = "misiones originales"
        if ent.cfg.get("bandos"):
            rel = [f"{b['nombre']}→{'/'.join(b.get('ataca', []))}" for b in ent.cfg["bandos"] if b.get("ataca")]
            teatro = f"{len(ent.cfg['bandos'])} bandos: " + ", ".join(rel)
        filas = [("Generación", f"{ent.generacion}"),
                 ("Misión", f"{mis}. {MS.NOMBRES[mis - 1]}" if not ent.completada else "Currículo completo (repaso)"),
                 ("Estado", hilo.estado), ("Velocidad", f"{hilo.gens_por_min:.1f} gen/min · σ {ent.sigma:.4f}"),
                 ("Teatro", teatro[:46])]
        for et, v in filas:
            s.blit(self.f_chica.render(et, True, TENUE), (tr.x + 12 * k, y))
            img = self.f_semi.render(v, True, TEXTO)
            s.blit(img, (tr.right - 12 * k - img.get_width(), y))
            y += int(19 * k)
        y += int(4 * k)
        s.blit(self.f_mini.render("LANZADORES POR ACTIVO", True, TENUE), (tr.x + 12 * k, y + 6 * k))
        xb = tr.right - 12 * k - 112 * k
        v = int(ent.cfg.get("lanzadores", 0))
        self.btn_cfg[0].rect = pygame.Rect(xb, y, int(26 * k), int(24 * k))
        self.btn_cfg[0].dibujar(s, self.f_semi, mouse)
        img = self.f_semi.render(str(v) if v else "misión", True, TEXTO if v else ACENTO)
        s.blit(img, img.get_rect(center=(xb + 52 * k, y + 12 * k)))
        self.btn_cfg[1].rect = pygame.Rect(xb + 78 * k, y, int(26 * k), int(24 * k))
        self.btn_cfg[1].dibujar(s, self.f_semi, mouse)
        y += int(32 * k)
        alto_g = max(int(36 * k), min(int(90 * k), int(tr.bottom - y - 176 * k)))
        g = pygame.Rect(tr.x + 12 * k, y, tr.w - 24 * k, alto_g)
        self._grafica(g)
        y = g.bottom + int(4 * k)
        xx = tr.x + 12 * k
        for t, c in (("mejor protección", VERDE), ("promedio", (120, 130, 150)), ("% que superan", ACENTO)):
            pygame.draw.rect(s, c, (xx, y + 6 * k, 10 * k, 3 * k))
            img = self.f_mini.render(t, True, TENUE)
            s.blit(img, (xx + 14 * k, y))
            xx += img.get_width() + 30 * k
        y += int(20 * k)
        bw = (tr.w - 24 * k - 3 * 6 * k) / 4
        self.btn_ent[0].texto = "Reanudar" if hilo.pausado else "Pausar"
        self.btn_ent[2].texto = "Clase instructor"
        confirmar = time.time() - self.borrar_t <= 5.0
        self.btn_borrar.texto = "¿Seguro? Clic otra vez" if confirmar else "Borrar lo aprendido"
        for i, b in enumerate(self.btn_ent + [self.btn_borrar]):
            b.rect = pygame.Rect(tr.x + 12 * k + i * (bw + 6 * k), y, bw, int(28 * k))
            b.dibujar(s, self.f_chica, mouse, b is self.btn_borrar and confirmar)
        y += int(34 * k)
        self.btn_rapido.rect = pygame.Rect(tr.x + 12 * k, y, tr.w - 24 * k, int(28 * k))
        self.btn_rapido.dibujar(s, self.f_chica, mouse)
        y += int(34 * k)
        y = self._fila_sat(tr, y, mouse)
        x0 = tr.x + 12 * k
        s.blit(self.f_mini.render("REPETIR", True, TENUE), (x0, y + 7 * k))
        lx = x0 + 58 * k
        self.btn_rep[0].rect = pygame.Rect(lx, y, int(24 * k), int(26 * k))
        self.btn_rep[0].dibujar(s, self.f_semi, mouse)
        img = self.f_semi.render(str(self.rep_n), True, ACENTO)
        s.blit(img, img.get_rect(center=(lx + 41 * k, y + 13 * k)))
        self.btn_rep[1].rect = pygame.Rect(lx + 58 * k, y, int(24 * k), int(26 * k))
        self.btn_rep[1].dibujar(s, self.f_semi, mouse)
        bx = lx + 90 * k
        bw2 = (tr.right - 12 * k - bx - 6 * k) / 2
        self.btn_rep[2].rect = pygame.Rect(bx, y, bw2, int(26 * k))
        self.btn_rep[2].dibujar(s, self.f_chica, mouse)
        todas = time.time() - self.rep_todas_t <= 5.0
        self.btn_rep[3].texto = "¿Seguro? Clic otra vez" if todas else "Repetir todas"
        self.btn_rep[3].rect = pygame.Rect(bx + bw2 + 6 * k, y, bw2, int(26 * k))
        self.btn_rep[3].dibujar(s, self.f_chica, mouse, todas)
        y += int(30 * k)
        nombre = f"{self.rep_n}. {MS.NOMBRES[self.rep_n - 1]}"
        camp = self.ent.campeones.get(self.rep_n)
        estado = ("superada" if camp["superada"] else "sin superar") if camp else "sin campeón"
        s.blit(self.f_mini.render(f"{nombre[:40]} · {estado}", True, TENUE), (x0, y))
        y += int(20 * k)
        if y < tr.bottom - 60 * k:
            self._pensamiento(tr, y)

    def _panel_ia(self, tr, mouse):
        s = self.pantalla
        k = self.k
        y = self._tarjeta(tr, "Inteligencia artificial")
        for t in (f"Pesos: {self.ep_info}", f"Entrenamiento: generación {self.ent.generacion}, misión {self.ent.mision_actual}"):
            s.blit(self.f_chica.render(t, True, TEXTO), (tr.x + 12 * k, y))
            y += int(19 * k)
        self.btn_reiniciar.rect = pygame.Rect(tr.x + 12 * k, y + 4 * k, int(170 * k), int(28 * k))
        self.btn_reiniciar.dibujar(s, self.f_chica, mouse)
        y += int(40 * k)
        y = self._fila_sat(tr, y, mouse)
        self._pensamiento(tr, y)

    def _fila_lanzadores(self, tr, y, mouse):
        s, k = self.pantalla, self.k
        x0 = tr.x + 12 * k
        a = self._act()
        s.blit(self.f_mini.render(f"LANZADORES {a.nombre if a else ''}", True, TENUE), (x0, y + 6 * k))
        lx = x0 + 110 * k
        self.btn_lanz[0].rect = pygame.Rect(lx, y, int(28 * k), int(26 * k))
        self.btn_lanz[0].dibujar(s, self.f_semi, mouse)
        n = len(a.misiles) if a else 0
        img = self.f_valor.render(str(n), True, TEXTO)
        s.blit(img, img.get_rect(center=(lx + 46 * k, y + 13 * k)))
        self.btn_lanz[1].rect = pygame.Rect(lx + 64 * k, y, int(28 * k), int(26 * k))
        self.btn_lanz[1].dibujar(s, self.f_semi, mouse)
        if a is not None and a.capa:
            s.blit(self.f_mini.render(f"{n * a.por_lanzador} interceptores {C.CAPAS[a.capa]['corto']}", True, TENUE),
                   (lx + 102 * k, y + 5 * k))
        return y + int(36 * k)

    def _ayuda(self, tr, y, texto):
        for l in self._envolver(texto, self.f_chica, tr.w - 24 * self.k):
            if y > tr.bottom - 18 * self.k:
                break
            self.pantalla.blit(self.f_chica.render(l, True, TENUE), (tr.x + 12 * self.k, y))
            y += int(16 * self.k)

    def _panel_jugar(self, tr, mouse):
        s, k = self.pantalla, self.k
        y = self._tarjeta(tr, "Tu defensa")
        y = self._fila_lanzadores(tr, y, mouse)
        self.btn_reiniciar.rect = pygame.Rect(tr.x + 12 * k, y, int(170 * k), int(28 * k))
        self.btn_reiniciar.dibujar(s, self.f_chica, mouse)
        y += int(36 * k)
        y = self._fila_sat(tr, y, mouse)
        texto = ("1) Clic en una ciudad del mapa para defenderla (o escríbela en «Lugar» y Enter). "
                 "2) Escribe el país atacante en «Lugar» y presiona «+ Atacante» (o clic en una zona rayada). "
                 "3) Clic derecho en el mapa pone una batería del tipo elegido en «ACTIVO»; clic derecho sobre una la quita. "
                 "«Misión original» lo restablece. " +
                 ("Fase de despliegue: el reloj está detenido. Arrastra cada activo a donde quieras (el anillo es "
                  "el alcance de sus interceptores) y presiona «Comenzar ataque». " if self.preparando else "") +
                 "Lo que el radar fija como amenaza para una ciudad se derriba automáticamente con la mejor capa "
                 "disponible. Tú puedes adelantarte: clic sobre una amenaza para dispararle un interceptor, Shift+clic "
                 "o clic derecho para dos (sólo con «Disparo: doble»). Siempre va uno por objetivo; si falla, se dispara otro. Las capas van de arriba hacia abajo: impulso (mientras sube), exo (en el "
                 "espacio), gran altitud y terminal (en la reentrada). Los señuelos se queman al reentrar; dispararles "
                 "es desperdicio. Lo que decidas se usa para enseñar a la IA al terminar el escenario.")
        self._ayuda(tr, y, texto)

    def _panel_comandante(self, tr, mouse):
        s, k = self.pantalla, self.k
        y = self._tarjeta(tr, "Mando del teatro de operaciones")
        x0 = tr.x + 12 * k
        ancho = tr.w - 24 * k
        s.blit(self.f_mini.render("ESCENARIO", True, TENUE), (x0, y))
        y += int(16 * k)
        bw4 = (ancho - 18 * k) / 4
        for i, b in enumerate(self.btn_presets):
            b.rect = pygame.Rect(x0 + i * (bw4 + 6 * k), y, bw4, int(26 * k))
            b.dibujar(s, self.f_chica, mouse)
        y += int(34 * k)
        self.btn_mirv.texto = f"Ojivas múltiples y señuelos: {'SÍ' if self.mirv_cmd else 'NO'}"
        self.btn_mirv.rect = pygame.Rect(x0, y, ancho, int(26 * k))
        self.btn_mirv.dibujar(s, self.f_chica, mouse, self.mirv_cmd)
        y += int(32 * k)
        self.btn_nuc.texto = f"Ojivas nucleares: {'SÍ' if self.nuclear_cmd else 'NO'}"
        self.btn_nuc.rect = pygame.Rect(x0, y, ancho, int(26 * k))
        self.btn_nuc.dibujar(s, self.f_chica, mouse, self.nuclear_cmd)
        y += int(32 * k)
        y = self._fila_sat(tr, y, mouse)
        s.blit(self.f_mini.render("CONTROL DE TIRO", True, TENUE), (x0, y))
        y += int(16 * k)
        bw3 = (ancho - 12 * k) / 3
        for i, (b, c) in enumerate(zip(self.btn_ctrl, ("ia", "doctrina", "manual"))):
            b.rect = pygame.Rect(x0 + i * (bw3 + 6 * k), y, bw3, int(26 * k))
            b.dibujar(s, self.f_chica, mouse, c == self.control_cmd)
        y += int(34 * k)
        y = self._fila_lanzadores(tr, y, mouse)
        self._ayuda(tr, y, "1) Clic en una ciudad para defenderla. 2) Escribe el país en «Lugar» y «+ Atacante». "
                           "3) Clic derecho pone una batería; clic derecho sobre ella la quita. Arrastra un activo para "
                           "redesplegarlo (tarda "
                           f"{mmss(C.T_REDESPLIEGUE)}). " + G.atribucion(self.vista))

    def dibujar(self):
        self._actualizar_cursor()
        self.pantalla.fill(FONDO)
        self._dibujar_mapa()
        self._dibujar_log()
        self._dibujar_perfil()
        self._panel()
        if self.preparando and not self.asistente:
            self._banner_preparacion()

    def _banner_preparacion(self):
        s, k, r = self.pantalla, self.k, self.r_mapa
        mouse = pygame.mouse.get_pos()
        zonas = [z for z in self.ep.zonas if z.activa]
        cub = sum(1 for z in zonas if self._coberturas(z))
        col = VERDE if cub == len(zonas) else (NARANJA if cub else ROJO)
        caja = pygame.Rect(0, 0, int(min(r.w - 30 * k, 720 * k)), int(78 * k))
        caja.midbottom = (r.centerx, r.bottom - int(40 * k))
        pygame.draw.rect(s, (14, 16, 20), caja, border_radius=10)
        pygame.draw.rect(s, ACENTO, caja, 2, border_radius=10)
        bw = int(200 * k)
        self.btn_comenzar.rect = pygame.Rect(caja.right - bw - int(12 * k), caja.y + int(12 * k), bw, caja.h - int(32 * k))
        self.btn_comenzar.dibujar(s, self.f_semi, mouse)
        img = self.f_mini.render("o tecla ESPACIO", True, SUTIL)
        s.blit(img, img.get_rect(midtop=(self.btn_comenzar.rect.centerx, self.btn_comenzar.rect.bottom + 2)))
        ancho = self.btn_comenzar.rect.x - caja.x - int(26 * k)
        lineas = [(self.f_semi, "FASE DE DESPLIEGUE · el enemigo todavía no ataca", ACENTO),
                  (self.f_chica, "Clic en una ciudad para defenderla · país en «Lugar» + «+ Atacante» · clic derecho pone baterías", ACENTO),
                  (self.f_semi, f"{cub}/{len(zonas)} ciudades con al menos una capa de defensa", col)]
        y = caja.y + int(9 * k)
        prev = s.get_clip()
        s.set_clip(pygame.Rect(caja.x + int(14 * k), caja.y, ancho, caja.h))
        for f, t, c in lineas:
            img = f.render(t, True, c)
            s.blit(img, (caja.x + int(14 * k), y))
            y += img.get_height() + int(1 * k)
        s.set_clip(prev)

    def correr(self):
        if self.entrenar_al_inicio and self.modo == "entrenar":
            self.hilo.iniciar()
        sigue = True
        t_prev = time.perf_counter()
        while sigue:
            ahora = time.perf_counter()
            dt = min(ahora - t_prev, 0.1)
            t_prev = ahora
            sigue = self._eventos() and self.salida is None
            self._procesar_geo()
            self._avanzar(dt)
            if self.modo == "entrenar" and self.hilo.instantanea is not None:
                g = self.hilo.instantanea[3]
                if self.ep.terminado and getattr(self.ep, "_fin", time.time()) + 3 < time.time() and g != self.ep_gen:
                    self._nuevo_ep()
            self.dibujar()
            pygame.display.flip()
            if self.grabador.grabando and self.grabador.necesita_cuadro():
                self.grabador.cuadro(pygame.image.tobytes(self.pantalla, "RGB"))
            self.reloj.tick(60)
        if self.modo == "jugar":
            self._enviar_demos()
        self.grabador.detener(esperar=True)
        if self.hilo.activo:
            self.hilo.parar()
        else:
            self.ent.guardar()
        pygame.quit()
        return self.salida
