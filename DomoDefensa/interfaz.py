import math
import os
import queue
import threading
import time
import webbrowser
from collections import OrderedDict

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import numpy as np
import pygame
import pygame.gfxdraw

import cerebro as B
import config as C
import geo as G
import misiones as MS
import mundo as M
from doctrina import ControladorManual, Doctrina
from evolucion import Entrenador, HiloEntrenamiento
from grabador import CARPETA_GRABACIONES, Grabador
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
ESTADOS = {"operativa": ("OPERATIVA", VERDE), "plegando": ("PLEGANDO", NARANJA), "en_ruta": ("EN RUTA", NARANJA),
           "desplegando": ("DESPLEGANDO", NARANJA), "destruida": ("FUERA DE COMBATE", ROJO)}
COLOR_TIPO = {"corto": (255, 95, 95), "medio": (255, 70, 150), "mortero": (255, 160, 77), "dron": (200, 120, 255)}
MODOS = [("entrenar", "Entrenar IA"), ("campeon", "Campeón"), ("jugar", "Jugar tú"), ("comandante", "Comandante")]
VELOCIDADES = [1, 2, 4, 8, 16]


def _fuente(archivo, tam):
    ruta = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts", archivo)
    try:
        return pygame.font.Font(ruta, max(8, tam))
    except (OSError, FileNotFoundError):
        return pygame.font.SysFont("segoeui", max(8, tam))


def mmss(t):
    t = max(0, int(t))
    return f"{t // 60:02d}:{t % 60:02d}"


def mezclar(a, b, t):
    return tuple(int(x + (y - x) * t) for x, y in zip(a, b))


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

    def numero(self, defecto=0.0):
        try:
            return float(self.valor.replace(",", "."))
        except ValueError:
            return defecto

    def poner(self, v):
        self.valor = f"{v:.1f}" if isinstance(v, float) else str(v)

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
        elif self.libre and e.unicode and e.unicode.isprintable() and len(self.valor) < 120:
            self.valor += e.unicode
        elif e.unicode and (e.unicode.isdigit() or e.unicode in ".,-") and len(self.valor) < 8:
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
        if not self.valor and not self.foco and self.libre:
            img = fe.render("ciudad, «lat, lon» o enlace de Google Maps", True, SUTIL)
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
        pygame.display.set_caption("Domo de Defensa Móvil — simulador con IA")
        self.reloj = pygame.time.Clock()
        self.ent = Entrenador(dir_datos=dir_datos)
        self.hilo = HiloEntrenamiento(self.ent)
        self.entrenar_al_inicio = entrenar
        self.grabador = Grabador()
        self.velocidad = 1
        self.pausa = False
        self.verdad = False
        self.aviso = ("", 0.0)
        self.mision_n = self.ent.mision_actual
        self.apoyo = False
        self.control_cmd = "ia"
        self.zonas_cmd = None
        self.bats_cmd = None
        self.lanz_cmd = None
        self.bat_sel = 0
        self._tabs = []
        self.ep = None
        self.ep_info = ""
        self.ep_gen = None
        self.acum = 0.0
        self.arrastre = None
        self.arrastre_bat = None
        self._cursor = None
        self.hover = None
        self.seleccion = None
        self._terreno_base = self._crear_terreno()
        self._cache_mapa = None
        self.campos = [Campo("X km", "40.0"), Campo("Y km", "40.0"), Campo("Radio km", "2.0"), Campo("Valor 1-3", "2")]
        self.campo_lugar = Campo("Lugar", "", libre=True)
        self.mapa_real = False
        self.geo = None
        self.geo_cmd = None
        self.vista = "terreno"
        self._fondos = OrderedDict()
        self._pidiendo = set()
        self._teselas = OrderedDict()
        self._ver_teselas = 0
        self._faltan_teselas = 0
        self._buscando = False
        self._y_aviso = 0
        self.cargador = G.CargadorTeselas()
        self.lugares = [dict(l) for l in (self.ent.cfg.get("lugares") or [])]
        self.real_mis = bool(self.lugares)
        self.cola_geo = queue.Queue()
        self.ocupado_geo = ""
        self.lanzadores = 3
        self.frentes_cmd = ["norte", "este", "noreste"]
        self.btn_mapa = [Boton("Mapa ficticio", lambda: self._modo_mapa(False)),
                         Boton("Mapa real", lambda: self._modo_mapa(True))]
        self.btn_vista = [Boton(G.NOMBRES_VISTA[v], lambda v=v: self._vista(v)) for v in G.VISTAS]
        self.btn_lugar = [Boton("Proteger lugar", lambda: self._barra_lugar(0), primario=True),
                          Boton("+ Agregar", lambda: self._barra_lugar(1)), Boton("Quitar", lambda: self._barra_lugar(2))]
        self.btn_lanz = [Boton("−", lambda: self._lanzadores(-1)), Boton("+", lambda: self._lanzadores(1))]
        self.btn_frentes = [Boton(M.NOMBRES_FRENTES[f], lambda f=f: self._frente(f)) for f in ("norte", "este", "sur", "oeste")]
        self.btn_google = Boton("Abrir en Google Maps", self._google)
        self.btn_bats = [Boton("+ Automática", self._agregar_bateria), Boton("Batería aquí", self._bateria_aqui),
                         Boton("− Quitar", self._quitar_bateria)]
        self.btn_cfg = [Boton("−", lambda: self._cfg("baterias", -1)), Boton("+", lambda: self._cfg("baterias", 1)),
                        Boton("−", lambda: self._cfg("lanzadores", -1)), Boton("+", lambda: self._cfg("lanzadores", 1))]
        self.btn_modos = [Boton(t, lambda m=m: self.cambiar_modo(m)) for m, t in MODOS]
        self.btn_vel = [Boton(f"×{v}", lambda v=v: self._vel(v)) for v in VELOCIDADES]
        self.btn_pausa = Boton("Pausa", self._pausar)
        self.btn_grabar = Boton("Grabar pantalla", self._grabar)
        self.btn_mis = [Boton("‹", lambda: self._mision(-1)), Boton("›", lambda: self._mision(1))]
        self.btn_reiniciar = Boton("Reiniciar escenario", self._reiniciar_ep)
        self.btn_ent = [Boton("Pausar entrenamiento", self._pausar_ent), Boton("Guardar", self._guardar),
                        Boton("Clase del instructor", self._forzar_clase)]
        self.btn_rapido = Boton("Entrenamiento rápido sin gráficos", self._a_rapido, primario=True)
        self.salida = None
        self.preparando = False
        self.perfil_todas = True
        self.btn_perfil = [Boton("Todas", lambda: self._perfil(True)), Boton("Seleccionada", lambda: self._perfil(False))]
        self.btn_comenzar = Boton("¡Comenzar ataque!", self._comenzar, primario=True)
        self.areas_auto = True
        self.zonas_jugar = None
        self.btn_areas = [Boton("Automáticas", lambda: self._areas(True)), Boton("Las elijo yo", lambda: self._areas(False))]
        self.btn_desp = [Boton("Proteger área", self._proteger_area, primario=True),
                         Boton("Mover batería aquí", self._mover_bateria),
                         Boton("Posición óptima", self._optima), Boton("Quitar áreas", self._quitar_areas)]
        self.btn_ctrl = [Boton("IA campeón", lambda: self._control("ia")), Boton("Doctrina", lambda: self._control("doctrina")),
                         Boton("Manual", lambda: self._control("manual"))]
        self.btn_apoyo = Boton("Apoyo automático: NO", self._toggle_apoyo)
        self.modo = None
        self._layout()
        self.cambiar_modo(modo)

    def _crear_terreno(self):
        h = M.terreno(640, 480)
        gy, gx = np.gradient(h)
        luz = np.clip(0.75 + (gx * -0.9 + gy * 0.9) / 18.0, 0.35, 1.25)
        t = (h - h.min()) / np.ptp(h)
        bajo, medio, alto = np.array([24, 33, 28]), np.array([38, 46, 36]), np.array([64, 62, 52])
        col = np.where(t[..., None] < 0.5, bajo + (medio - bajo) * (t[..., None] / 0.5),
                       medio + (alto - medio) * ((t[..., None] - 0.5) / 0.5))
        col = col * luz[..., None]
        curvas = (np.abs((h % 80) - 40) > 38.5)
        col[curvas] *= 0.78
        img = np.clip(col, 0, 255).astype(np.uint8)
        sup = pygame.surfarray.make_surface(np.transpose(img, (1, 0, 2)))
        return pygame.transform.smoothscale(sup, (1600, 1200))

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
        self.s0 = min(self.r_mapa.w / C.MAPA_W, self.r_mapa.h / C.MAPA_H)
        if not hasattr(self, "esc"):
            self.esc = self.s0
            self.cx, self.cy = C.MAPA_W / 2, C.MAPA_H / 2
        self.esc = max(self.esc, self.s0)
        self._cache_mapa = None

    def a_pantalla(self, x, y):
        r = self.r_mapa
        return (r.centerx + (x - self.cx) * self.esc, r.centery - (y - self.cy) * self.esc)

    def a_mundo(self, px, py):
        r = self.r_mapa
        return (self.cx + (px - r.centerx) / self.esc, self.cy - (py - r.centery) / self.esc)

    def _limitar_vista(self):
        r = self.r_mapa
        mw, mh = r.w / self.esc / 2, r.h / self.esc / 2
        self.cx = min(max(self.cx, mw), max(C.MAPA_W - mw, mw)) if mw * 2 < C.MAPA_W else C.MAPA_W / 2
        self.cy = min(max(self.cy, mh), max(C.MAPA_H - mh, mh)) if mh * 2 < C.MAPA_H else C.MAPA_H / 2

    def cambiar_modo(self, modo):
        if self.modo == "jugar" and self.ep is not None and modo != "jugar":
            self._enviar_demos()
        self.modo = modo
        self.seleccion = None
        if modo == "comandante":
            self.geo = self.geo_cmd
        elif modo == "entrenar":
            self._sincronizar_cfg(aviso=False)
        if modo == "entrenar":
            if not self.hilo.activo:
                self.hilo.pausado = False
                self.hilo.iniciar()
            self.hilo.pausado = False
        elif self.hilo.activo and modo in ("jugar",):
            self.hilo.pausado = True
        if modo == "comandante" and self.zonas_cmd is None:
            self._zonas_ficticias()
        if modo in ("campeon", "jugar"):
            self.mision_n = min(max(self.mision_n, 1), MS.NUMERO_MISIONES)
        self._nuevo_ep()
        self._ajustar_zoom()

    def _ajustar_zoom(self):
        if not (self._real() and self.geo is not None) and self.esc > self.s0 * 10:
            self.esc = self.s0 * 10
            self._limitar_vista()
        self._cache_mapa = None

    def _zona_max(self):
        return max(self.s0 * 10, 2.2) if (self._real() and self.geo is not None) else self.s0 * 10

    def _vista(self, v):
        if v == self.vista:
            return
        self.vista = v
        self._cache_mapa = None
        if self.geo is not None:
            self._pedir_fondo(self.geo, v)
        self.avisar(f"Vista del mapa: {G.NOMBRES_VISTA[v]}" + (" · acerca con la rueda para ver calles y casas" if v != "terreno" else ""))

    def _superficie(self, img, vista):
        from PIL import ImageEnhance
        brillo, color = {"terreno": (0.73, 1.0), "hibrido": (0.8, 1.0), "calles": (0.64, 0.72)}.get(vista, (0.75, 1.0))
        img = ImageEnhance.Brightness(img).enhance(brillo)
        if color != 1.0:
            img = ImageEnhance.Color(img).enhance(color)
        return pygame.image.fromstring(img.tobytes(), img.size, "RGB").convert()

    def _guardar_fondo(self, clave, img):
        self._fondos[clave] = self._superficie(img, clave[1])
        self._fondos.move_to_end(clave)
        while len(self._fondos) > 8:
            self._fondos.popitem(last=False)
        self._cache_mapa = None

    def _pedir_fondo(self, geo, vista):
        clave = (geo.clave, vista)
        if clave in self._pidiendo or clave in self._fondos:
            return
        self._pidiendo.add(clave)

        def tarea():
            try:
                img = geo.imagen(avisar=lambda m: setattr(self, "ocupado_geo", m), vista=vista)
                self.cola_geo.put(("fondo", clave, img))
            except Exception as ex:
                self.cola_geo.put(("fondo_error", clave, str(ex)))
        self.ocupado_geo = f"Descargando mapa ({G.NOMBRES_VISTA[vista].lower()})…"
        threading.Thread(target=tarea, daemon=True).start()

    def _fondo_real(self):
        if self.geo is None:
            return None
        sup = self._fondos.get((self.geo.clave, self.vista))
        if sup is None:
            self._pedir_fondo(self.geo, self.vista)
            sup = next((v for (c, _), v in self._fondos.items() if c == self.geo.clave), None)
        return sup

    def _cfg_mision(self, base):
        cfg = dict(base or {})
        if self.real_mis and self.lugares:
            cfg["lugares"] = [dict(l) for l in self.lugares]
        else:
            cfg.pop("lugares", None)
        return cfg

    def _sincronizar_cfg(self, aviso=True):
        lug = [dict(l) for l in self.lugares] if (self.real_mis and self.lugares) else None
        with self.ent.bloqueo:
            antes = self.ent.cfg.get("lugares")
            if lug:
                self.ent.cfg["lugares"] = lug
            else:
                self.ent.cfg.pop("lugares", None)
        if aviso and antes != lug:
            self.avisar(f"La IA entrenará defendiendo {lug[0]['nombre']} (desde la próxima generación)" if lug
                        else "La IA vuelve a entrenar en el mapa ficticio")

    def _geo_mision(self):
        if self.real_mis and self.lugares and self.ep.m.get("lugar") and self.ep.zonas:
            l0, z0 = self.lugares[0], self.ep.zonas[0]
            g = G.MapaReal.anclado(l0["lat"], l0["lon"], z0.x, z0.y, l0["nombre"])
            if self.geo is None or self.geo.clave != g.clave:
                self.geo = g
                self._cache_mapa = None
                self._encuadrar(self.ep.zonas)
        else:
            self.geo = None

    def _lugares_cambiaron(self, msg=None):
        self._cache_mapa = None
        if self.modo == "jugar":
            self._enviar_demos()
        if self.modo == "entrenar":
            self._sincronizar_cfg()
        self._nuevo_ep()
        if msg:
            self.ep.log(msg, "ambar")
        if self.geo is not None and self.ep.zonas:
            self._encuadrar(self.ep.zonas)
        self._ajustar_zoom()

    def _encuadrar(self, zonas):
        x0, x1 = min(z.x - z.r for z in zonas), max(z.x + z.r for z in zonas)
        y0, y1 = min(z.y - z.r for z in zonas), max(z.y + z.r for z in zonas)
        r = self.r_mapa
        lado = max(x1 - x0, (y1 - y0) * r.w / r.h) + 2 * C.INT_ALCANCE
        self.esc = max(self.s0, min(r.w / lado, self._zona_max()))
        self.cx, self.cy = (x0 + x1) / 2, (y0 + y1) / 2
        self._limitar_vista()

    def _quitar_lugares(self):
        if not self.lugares:
            self.avisar("No hay lugares a proteger")
            return
        self.lugares = []
        self._lugares_cambiaron("Se quitaron los lugares del mapa real · se usan las áreas de la misión")
        self.avisar("Lugares quitados: busca otra ciudad o coordenadas")

    def _aplicar_lugar_mis(self, res, accion):
        if accion in ("mover", "bateria"):
            if self.geo is None or not self.geo.contiene(res["lat"], res["lon"], 1000):
                self.avisar("Ese lugar queda fuera del mapa de esta misión")
                return
            x, y = self.geo.a_metros(res["lat"], res["lon"])
            (self._mover_a if accion == "mover" else self._bateria_en)(x, y)
            return
        r = res.get("radio")
        r = min(max(r, 1000.0), 5000.0) if r else min(max(self.campos[2].numero(2.0), 0.3), 5.0) * 1000
        nuevo = {"nombre": res["nombre"][:28], "lat": round(res["lat"], 6), "lon": round(res["lon"], 6),
                 "r": round(r), "valor": 3}
        if accion == "lugar" or not self.lugares or not self.real_mis:
            self.lugares = [nuevo]
        else:
            nuevo["valor"] = int(min(max(self.campos[3].numero(2), 1), 3))
            d = math.hypot(*MS.relativas([self.lugares[0], nuevo])[1])
            cerca = [l for l in self.lugares if math.hypot(*MS.relativas([l, nuevo])[1]) < 400]
            if cerca:
                self.avisar(f"{cerca[0]['nombre']} ya está protegido")
                return
            if d > MS.RADIO_LUGARES:
                nuevo["valor"] = 3
                self.lugares = [nuevo]
                self.avisar(f"{nuevo['nombre']} está a {d / 1000:.0f} km del primer lugar: empieza una zona nueva "
                            f"(máximo {MS.RADIO_LUGARES / 1000:.0f} km entre lugares)")
            elif len(self.lugares) >= MS.MAX_LUGARES:
                self.avisar(f"Máximo {MS.MAX_LUGARES} lugares por misión")
                return
            else:
                self.lugares.append(nuevo)
        self.real_mis = True
        self._lugares_cambiaron(f"Lugar real a proteger: {nuevo['nombre']} ({nuevo['lat']:.4f}, {nuevo['lon']:.4f}) · "
                                f"radio {nuevo['r'] / 1000:.1f} km")

    def _zonas_ficticias(self):
        self.zonas_cmd = M.pueblos()
        for z in self.zonas_cmd:
            z.activa = z.nombre in ("San Ciro", "Roca Blanca")
        self.frentes_cmd = ["norte", "este", "noreste"]
        self.bats_cmd = [M.posicion_optima(self.zonas_cmd, self.frentes_cmd)]
        self.lanz_cmd = [3]
        self.bat_sel = 0

    def _modo_mapa(self, real):
        if real == self._real():
            return
        self._cache_mapa = None
        if self.modo != "comandante":
            self.real_mis = real
            if real and not self.lugares:
                self.avisar("Escribe una ciudad o coordenadas en «Lugar» (arriba del mapa) y presiona Enter")
            self._lugares_cambiaron()
            return
        self.mapa_real = real
        lanz = [len(b.misiles) for b in self.ep.baterias] if self.ep is not None else [3]
        self.ep = None
        if real:
            self.zonas_cmd = []
            self.frentes_cmd = ["norte"]
            self.bats_cmd = self._repartidas(len(lanz))
            self.lanz_cmd = lanz
            self.bat_sel = 0
            if self.geo is not None:
                self._colocar_directo = True
            if self.geo is None:
                self.avisar("Escribe una ciudad o coordenadas en «Lugar» (arriba del mapa) y presiona Enter")
        else:
            self._zonas_ficticias()
        self._nuevo_ep()
        self._ajustar_zoom()

    def _repartidas(self, n):
        return [(C.MAPA_W / 2 + 9000 * math.cos(2.4 * i) * (i > 0), C.MAPA_H / 2 + 9000 * math.sin(2.4 * i) * (i > 0))
                for i in range(n)]

    def _bat(self):
        self.bat_sel = max(0, min(self.bat_sel, len(self.ep.baterias) - 1))
        return self.ep.baterias[self.bat_sel]

    def _lanzadores(self, d):
        vieja = self._bat()
        n = max(1, min(8, len(vieja.misiles) + d))
        if n == len(vieja.misiles):
            return
        self.lanzadores = n
        from simulacion import Bateria
        nueva = Bateria(vieja.x, vieja.y, vieja.recargas // max(len(vieja.misiles), 1), n, vieja.nombre)
        nueva.estado, nueva.destino, nueva.timer, nueva.impactos = vieja.estado, vieja.destino, vieja.timer, vieja.impactos
        if self.modo == "comandante":
            nueva.recargas = 99 * n
        self.ep.baterias[self.bat_sel] = nueva
        self.ep.log(f"{nueva.nombre}: {n} lanzador{'es' if n > 1 else ''} ({n * C.MISILES_POR_LANZADOR} interceptores)", "ambar")

    def _agregar_bateria(self):
        ep = self.ep
        if len(ep.baterias) >= C.MAX_BATERIAS:
            self.avisar(f"Máximo {C.MAX_BATERIAS} baterías")
            return
        ocupadas = [b.destino or (b.x, b.y) for b in ep.vivas()]
        x, y = M.siguiente_posicion(ep.zonas, ocupadas, ep.frentes)
        rec = 99 if self.modo == "comandante" else None
        b = ep.agregar_bateria(x, y, self.lanzadores, rec)
        self.bat_sel = len(ep.baterias) - 1
        ep.log(f"Batería {b.nombre} desplegada en {self._texto_pos(x, y)} con {len(b.misiles)} lanzadores", "ambar")

    def _bateria_aqui(self):
        if self._real():
            self._buscar("bateria")
            return
        self._bateria_en(*self._coords())

    def _bateria_en(self, x, y):
        ep = self.ep
        if not (1000 <= x <= C.MAPA_W - 1000 and 1000 <= y <= C.MAPA_H - 1000):
            self.avisar("Ese punto queda fuera del mapa")
            return
        if M.distancia_frente(x, y, ep.frentes) < C.DISTANCIA_FRENTE_MIN:
            self.avisar(f"Demasiado cerca del frente (mínimo {C.DISTANCIA_FRENTE_MIN / 1000:.0f} km)")
            return
        solo = len(ep.baterias) == 1 and not any(z.tipo == "area" for z in ep.zonas) and self._real()
        if solo:
            b = ep.baterias[0]
            b.x, b.y, b.estado, b.destino = x, y, "operativa", None
            self._colocar_directo = False
        else:
            if len(ep.baterias) >= C.MAX_BATERIAS:
                self.avisar(f"Máximo {C.MAX_BATERIAS} baterías")
                return
            b = ep.agregar_bateria(x, y, self.lanzadores, 99 if self.modo == "comandante" else None)
        self.bat_sel = ep.baterias.index(b)
        ep.log(f"Batería {b.nombre} desplegada en {self._texto_pos(x, y)} con {len(b.misiles)} lanzadores", "ambar")

    def _quitar_bateria(self):
        ep = self.ep
        if len(ep.baterias) <= 1:
            self.avisar("Debe quedar al menos una batería")
            return
        b = ep.baterias.pop(self._bat_idx())
        for it in ep.interceptores:
            if getattr(it, "bateria", None) is b:
                it.bateria = None
        self.bat_sel = max(0, self.bat_sel - 1)
        ep.log(f"Batería {b.nombre} retirada", "ambar")

    def _bat_idx(self):
        self._bat()
        return self.bat_sel

    def _cfg(self, clave, d):
        ent = self.ent
        tope = C.MAX_BATERIAS if clave == "baterias" else 8
        with ent.bloqueo:
            ent.cfg[clave] = max(0, min(tope, int(ent.cfg.get(clave, 0)) + d))
        v = ent.cfg[clave]
        nombre = "Baterías" if clave == "baterias" else "Lanzadores por batería"
        self.avisar(f"{nombre} en el entrenamiento: {v if v else 'las de cada misión'} (desde la próxima generación)")

    def _cobertura_total(self, posiciones):
        activas = [z for z in self.ep.zonas if z.activa]
        return [max([M.cobertura(z, *p) for p in posiciones] or [0.0]) for z in activas]

    def _mover_una(self):
        ep = self.ep
        vivas = ep.vivas()
        actuales = [b.destino or (b.x, b.y) for b in vivas]
        mejor = None
        for i, b in enumerate(vivas):
            otras = actuales[:i] + actuales[i + 1:]
            p = M.siguiente_posicion(ep.zonas, otras, ep.frentes)
            cob = self._cobertura_total(otras + [p])
            clave = (min(cob or [1.0]) >= 0.9, sum(cob), -math.dist(p, actuales[i]))
            if mejor is None or clave > mejor[0]:
                mejor = (clave, b, p, otras)
        if mejor is None or not mejor[0][0]:
            return None
        _, b, p, otras = mejor
        if b.ordenar(*p):
            ep.log(f"{b.nombre} emplazada en {self._texto_pos(*p)}" if self.preparando else
                   f"{b.nombre} en marcha hacia {self._texto_pos(*p)} · llegada en {mmss(b.eta())} (las demás siguen en posición)",
                   "ambar")
        return otras + [p]

    def _reubicar_todas(self):
        ep = self.ep
        vivas = ep.vivas()
        if not vivas:
            return []
        objetivos = M.posiciones_optimas(ep.zonas, len(vivas), ep.frentes)
        plan = M.asignar([(b.x, b.y) for b in vivas], objetivos)
        for b, p in zip(vivas, plan):
            if p is not None and math.dist(p, (b.destino or (b.x, b.y))) > 1500 and b.ordenar(*p):
                ep.log(f"{b.nombre} emplazada en {self._texto_pos(*p)}" if self.preparando else
                       f"{b.nombre} en marcha hacia {self._texto_pos(*p)} · llegada en {mmss(b.eta())}", "ambar")
        return [p for p in plan if p is not None]

    def _frente(self, f):
        fr = list(self.ep.frentes)
        if f in fr:
            if len([x for x in fr if x != "noreste"]) == 1 and f != "noreste":
                self.avisar("Debe quedar al menos una dirección de amenaza")
                return
            fr.remove(f)
            if f == "norte" and "noreste" in fr:
                fr.remove("noreste")
        else:
            fr.append(f)
        self.frentes_cmd = fr
        self.ep.frentes = fr
        self.ep.m["frentes"] = fr
        self._cache_mapa = None
        self.ep.log("Amenazas desde: " + ", ".join(M.NOMBRES_FRENTES[x] for x in fr), "ambar")

    def _google(self):
        if self.geo is not None and self.mapa_real:
            lat, lon = self.geo.a_latlon(self._bat().x, self._bat().y)
        else:
            c = G.leer_coordenadas(self.campo_lugar.valor)
            if c is None:
                self.avisar("Carga primero un mapa real o escribe coordenadas")
                return
            lat, lon = c
        webbrowser.open(G.url_google_maps(lat, lon))

    def _barra_lugar(self, i):
        cmd = self.modo == "comandante"
        if i == 2:
            if cmd:
                self._quitar_areas()
            else:
                self._quitar_lugares()
            return
        if not self.campo_lugar.valor.strip():
            self.avisar("Escribe una ciudad, «lat, lon» o un enlace de Google Maps en «Lugar» (arriba del mapa)")
            self.campo_lugar.foco = True
            return
        if not self._real():
            self._modo_mapa(True)
        if cmd:
            self._buscar("proteger" if i == 0 else "bateria")
        else:
            self._buscar("lugar" if i == 0 else "proteger")

    def _buscar(self, accion):
        texto = self.campo_lugar.valor.strip()
        if not texto:
            self.avisar("Escribe una ciudad o coordenadas en «Lugar»")
            return
        if self._buscando:
            self.avisar("Espera: todavía se está buscando el lugar anterior")
            return
        self._buscando = True
        self.ocupado_geo = f"Buscando «{texto}»…"
        self.avisar(self.ocupado_geo)
        if self.modo != "comandante":
            def tarea_mision():
                try:
                    self.cola_geo.put(("lugar_mis", G.buscar_lugar(texto), accion))
                except Exception as ex:
                    self.cola_geo.put(("error", str(ex)))
            threading.Thread(target=tarea_mision, daemon=True).start()
            return
        vista = self.vista

        viejo = self.geo
        puntos = []
        if viejo is not None and self.ep is not None and self.ep.continuo:
            puntos = [viejo.a_latlon(z.x, z.y) for z in self.ep.zonas if z.tipo == "area"]
            puntos += [viejo.a_latlon(b.x, b.y) for b in self.ep.baterias]

        def tarea():
            try:
                res = G.buscar_lugar(texto)
                if self.geo is None or not self.geo.contiene(res["lat"], res["lon"], 9000):
                    self.ocupado_geo = "Descargando mapa satelital…"
                    mapa = None
                    conservar = False
                    if puntos:
                        todos = puntos + [(res["lat"], res["lon"])]
                        la = [p[0] for p in todos]
                        lo = [p[1] for p in todos]
                        prueba = G.MapaReal((min(la) + max(la)) / 2, (min(lo) + max(lo)) / 2, res["nombre"])
                        if all(prueba.contiene(a, b, 6000) for a, b in todos):
                            mapa, conservar = prueba, True
                    if mapa is None:
                        mapa = G.MapaReal(res["lat"], res["lon"], res["nombre"])
                    img = mapa.imagen(avisar=lambda m: setattr(self, "ocupado_geo", m), vista=vista)
                    self.cola_geo.put(("mapa", mapa, img, res, accion, viejo if conservar else None, vista))
                else:
                    self.cola_geo.put(("lugar", res, accion))
            except Exception as ex:
                self.cola_geo.put(("error", str(ex)))
        threading.Thread(target=tarea, daemon=True).start()

    def _procesar_geo(self):
        for clave, img in self.cargador.recoger():
            self._teselas[clave] = self._superficie(img, clave[0])
            self._ver_teselas += 1
        while len(self._teselas) > 400:
            self._teselas.popitem(last=False)
        try:
            while True:
                m = self.cola_geo.get_nowait()
                if m[0] in ("fondo", "fondo_error"):
                    self._pidiendo.discard(m[1])
                    if not self._pidiendo and not self._buscando:
                        self.ocupado_geo = ""
                    if m[0] == "fondo":
                        self._guardar_fondo(m[1], m[2])
                    else:
                        self.avisar(m[2])
                    continue
                self.ocupado_geo = ""
                self._buscando = False
                if m[0] == "error":
                    self.avisar(m[1])
                    continue
                if m[0] == "lugar_mis":
                    if self.modo != "comandante":
                        self._aplicar_lugar_mis(m[1], m[2])
                    continue
                if m[0] == "mapa":
                    _, mapa, img, res, accion, viejo, vista = m
                    self.geo_cmd = mapa
                    self._guardar_fondo((mapa.clave, vista), img)
                    if self.modo == "comandante":
                        self.geo = mapa
                    if self.modo == "comandante" and self.mapa_real:
                        ep = self.ep
                        lanz = [len(b.misiles) for b in ep.baterias] if ep is not None else (self.lanz_cmd or [3])
                        if viejo is not None and ep is not None:
                            zonas = []
                            for z in ep.zonas:
                                if z.tipo != "area":
                                    continue
                                nz = z.copia()
                                nz.x, nz.y = mapa.a_metros(*viejo.a_latlon(z.x, z.y))
                                zonas.append(nz)
                            self.zonas_cmd = zonas
                            self.bats_cmd = [mapa.a_metros(*viejo.a_latlon(b.x, b.y)) for b in ep.baterias]
                            self.lanz_cmd = lanz
                            self.ep = None
                            self._nuevo_ep()
                            self.ep.log(f"Mapa recentrado para incluir {res['nombre']} · se conservan áreas y baterías", "ambar")
                            self._colocar_directo = False
                        else:
                            self.zonas_cmd = []
                            self.bats_cmd = self._repartidas(len(lanz))
                            self.lanz_cmd = lanz
                            self.ep = None
                            self._nuevo_ep()
                            self.ep.log(f"Mapa real de {mapa.nombre} ({mapa.lat:.4f}, {mapa.lon:.4f}) · 80 × 60 km", "ambar")
                            self._colocar_directo = accion != "bateria"
                else:
                    _, res, accion = m
                if self.modo == "comandante" and self.mapa_real and self.geo is not None:
                    self._aplicar_lugar(res, accion)
        except queue.Empty:
            pass

    def _aplicar_lugar(self, res, accion):
        x, y = self.geo.a_metros(res["lat"], res["lon"])
        if accion == "mover":
            self._mover_a(x, y)
            return
        if accion == "bateria":
            self._bateria_en(x, y)
            return
        r = res.get("radio")
        r = min(max(r, 1000.0), 6000.0) if r else min(max(self.campos[2].numero(2.0), 0.3), 8.0) * 1000
        v = min(max(self.campos[3].numero(2), 1), 3)
        self._agregar_zona(res["nombre"][:28], x, y, r, v)

    def _pesos_campeon(self):
        c = self.ent.campeon(self.mision_n if self.modo != "comandante" else None)
        if c is None:
            return self.ent.mejores_pesos(), "IA actual (aún sin campeón)"
        w, info = c
        return w, f"Campeón gen {info['generacion']} · protección {100 * info['proteccion']:.0f}%"

    def _nuevo_ep(self):
        sem = int(np.random.default_rng().integers(1 << 30))
        self.acum = 0.0
        if self.modo == "entrenar":
            inst = self.hilo.instantanea
            if inst is None:
                n, w, sem, g, cfg = self.ent.mision_actual, self.ent.mejores_pesos(), sem, self.ent.generacion, dict(self.ent.cfg)
            else:
                n, w, sem, g, cfg = inst
            self.ep_gen = g
            self.mision_n = n
            mis, extra = MS.preparar(n, self._cfg_mision(cfg))
            self.ep = Episodio(mis, B.ControladorRed(w), sem, bitacora=True, **extra)
            self.ep_info = f"Generación {g} · individuo central de la población"
        elif self.modo == "campeon":
            w, info = self._pesos_campeon()
            mis, extra = MS.preparar(self.mision_n, self._cfg_mision(self.ent.cfg))
            self.ep = Episodio(mis, B.ControladorRed(w), sem, bitacora=True, **extra)
            self.ep_info = info
        elif self.modo == "jugar":
            ctl = ControladorManual(Doctrina() if self.apoyo else None)
            mis, extra = MS.preparar(self.mision_n, self._cfg_mision({}))
            mis = dict(mis)
            mis["lanzadores"] = self.lanzadores
            lugar = "zonas" in extra
            propias = None
            if not lugar and not self.areas_auto and self.zonas_jugar and self.zonas_jugar[0] == self.mision_n:
                propias = [z.copia() for z in self.zonas_jugar[1]]
            self.ep = Episodio(mis, ctl, sem, bitacora=True, demos=True, zonas=extra["zonas"] if lugar else propias,
                               n_baterias=extra["n_baterias"])
            if not lugar and not self.areas_auto and propias is None:
                self._zonas_a_elegir()
            self.ep_info = "Tú eres el operador de control de tiro"
        else:
            self.geo = self.geo_cmd
            if self.ep is not None and self.ep.continuo:
                self.zonas_cmd = self.ep.zonas
                self.bats_cmd = [(b.x, b.y) for b in self.ep.baterias]
                self.lanz_cmd = [len(b.misiles) for b in self.ep.baterias]
            ctl = self._ctl_cmd()
            mis = MS.libre(self.zonas_cmd, self.bats_cmd[0], duracion=3600, frentes=self.frentes_cmd,
                           lanzadores=self.lanzadores)
            if self.mapa_real:
                mis["nombre"] = f"Comandante · {self.geo.nombre}" if self.geo else "Comandante · mapa real"
                mis["descripcion"] = ("Mapa real de 80 × 60 km. Las zonas hostiles son franjas en los "
                                      "bordes que tú eliges.")
            self.ep = Episodio(mis, ctl, sem, zonas=self.zonas_cmd, baterias=self.bats_cmd, bitacora=True,
                               lanzadores=self.lanz_cmd)
            self.ep_info = getattr(ctl, "info", ctl.nombre)
        if self.modo != "comandante":
            self._geo_mision()
        self.ep.log(f"Escenario: {self.ep.m['nombre']}", "ambar")
        self.preparando = self.modo == "jugar"
        if self.preparando:
            self.ep.log("Fase de despliegue: coloca tus baterías y presiona «Comenzar ataque» (Espacio)", "cian")

    def _perfil(self, todas):
        self.perfil_todas = todas

    def _areas(self, auto):
        if self.modo != "jugar":
            return
        if self.ep.m.get("lugar"):
            self.avisar("En el mapa real se protegen los lugares que buscas (usa «Quitar áreas» para volver)")
            return
        if not self.preparando:
            self.avisar("Las áreas se eligen en la fase de despliegue (usa «Reiniciar escenario»)")
            return
        self.areas_auto = auto
        self.zonas_jugar = None
        self._nuevo_ep()

    def _zonas_a_elegir(self):
        ep = self.ep
        for z in ep.zonas:
            z.activa = False
        nombres = {z.nombre for z in ep.zonas}
        for z in M.pueblos():
            if z.nombre not in nombres and not M.en_frente(z.x, z.y, ep.frentes):
                z.activa = False
                ep.zonas.append(z)
        ep.log("Elige qué proteger: clic en un poblado o área del mapa, o «Proteger área» con X/Y", "cian")

    def _comenzar(self):
        if not self.preparando:
            return
        if not self.ep.zonas_activas():
            self.avisar("Elige al menos un área a proteger antes de comenzar")
            return
        if self.modo == "jugar" and not self.areas_auto:
            self.zonas_jugar = (self.mision_n, [z.copia() for z in self.ep.zonas])
        self._asentar()
        self.preparando = False
        self.pausa = False
        self.ep.log(f"¡Comienza el ataque! Cobertura inicial: {100 * self._cobertura_valor():.0f}% del valor", "rojo")

    def _asentar(self):
        for b in self.ep.baterias:
            if b.destruida:
                continue
            if b.destino is not None:
                b.x, b.y = b.destino
            b.estado, b.destino, b.timer = "operativa", None, 0.0

    def _coberturas(self):
        vivas = self.ep.vivas()
        return [(z, max([M.cobertura(z, b.x, b.y) for b in vivas] or [0.0])) for z in self.ep.zonas if z.activa]

    def _cobertura_valor(self):
        cz = self._coberturas()
        total = sum(z.valor for z, _ in cz)
        return sum(z.valor * c for z, c in cz) / total if total else 1.0

    def _ctl_cmd(self):
        if self.control_cmd == "doctrina":
            return Doctrina()
        if self.control_cmd == "manual":
            return ControladorManual(None)
        w, info = self._pesos_campeon()
        c = B.ControladorRed(w)
        c.info = info
        return c

    def _control(self, c):
        self.control_cmd = c
        if self.modo == "comandante" and self.ep is not None:
            self.ep.controlador = self._ctl_cmd()
            self.ep_info = getattr(self.ep.controlador, "info", self.ep.controlador.nombre)

    def _toggle_apoyo(self):
        self.apoyo = not self.apoyo
        if self.modo == "jugar" and isinstance(self.ep.controlador, ControladorManual):
            self.ep.controlador.apoyo = Doctrina() if self.apoyo else None

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

    def _reiniciar_ep(self):
        if self.modo == "jugar":
            self._enviar_demos()
        self._nuevo_ep()

    def _pausar_ent(self):
        self.hilo.pausado = not self.hilo.pausado

    def _guardar(self):
        threading.Thread(target=self.ent.guardar, daemon=True).start()
        self.avisar("Avance de la IA guardado en datos\\")

    def _a_rapido(self):
        self.salida = "rapido"
        self.avisar("Guardando y pasando al entrenamiento rápido…")

    def _forzar_clase(self):
        self.ent.clases.pop(self.ent.mision, None)
        self.avisar("Habrá clase del instructor en la siguiente generación")

    def avisar(self, txt):
        self.aviso = (txt, time.time())

    def _coords(self):
        x, y = self.campos[0].numero(40) * 1000, self.campos[1].numero(40) * 1000
        x = min(max(x, 0.0), C.MAPA_W)
        y = min(max(y, 0.0), C.MAPA_H)
        return x, y

    def _proteger_area(self):
        if self._real():
            self._buscar("proteger")
            return
        x, y = self._coords()
        r = min(max(self.campos[2].numero(2.0), 0.3), 8.0) * 1000
        v = min(max(self.campos[3].numero(2), 1), 3)
        n = sum(1 for z in self.ep.zonas if z.tipo == "area") + 1
        self._agregar_zona(f"Área {n}", x, y, r, v)

    def _real(self):
        return self.mapa_real if self.modo == "comandante" else self.real_mis

    def _agregar_zona(self, nombre, x, y, r, v):
        if not (0 <= x <= C.MAPA_W and 0 <= y <= C.MAPA_H):
            self.avisar("Ese punto queda fuera del mapa")
            return
        if M.en_frente(x, y, self.ep.frentes):
            self.avisar("Esas coordenadas están dentro de la zona hostil")
            return
        z = M.Zona(nombre, x, y, r, v, "area")
        self.ep.zonas.append(z)
        if getattr(self, "_colocar_directo", False):
            self._colocar_directo = False
            vivas = self.ep.vivas()
            for b, (bx, by) in zip(vivas, M.posiciones_optimas(self.ep.zonas, len(vivas), self.ep.frentes)):
                b.x, b.y, b.estado, b.destino = bx, by, "operativa", None
            self.ep.log(f"Nueva área protegida: {z.nombre} · {len(vivas)} batería(s) desplegada(s)", "ambar")
            return
        if any(M.cobertura(z, b.x, b.y) >= 0.9 for b in self.ep.vivas()):
            self.ep.log(f"Nueva área protegida: {z.nombre} en {self._texto_pos(x, y)} (ya tiene cobertura)", "ambar")
            return
        self.ep.log(f"Nueva área protegida: {z.nombre} en {self._texto_pos(x, y)}, radio {r / 1000:.1f} km", "ambar")
        destinos = self._mover_una() or self._reubicar_todas()
        fuera = [w.nombre for w in self.ep.zonas if w.activa and max([M.cobertura(w, *p) for p in destinos] or [0]) < 0.9]
        if fuera:
            self.ep.log("Sin cobertura: " + ", ".join(fuera) + " · agrega otra batería", "rojo")
            self.avisar("Faltan baterías para cubrir: " + ", ".join(fuera) + " (usa «+ Batería»)")

    def _texto_pos(self, x, y):
        if self._real() and self.geo is not None:
            lat, lon = self.geo.a_latlon(x, y)
            return f"({lat:.4f}, {lon:.4f})"
        return f"({x / 1000:.1f}, {y / 1000:.1f}) km"

    def _ir(self, x, y):
        b = self._bat()
        if not b.ordenar(x, y):
            return
        if self.preparando:
            self._asentar()
            self.ep.log(f"{b.nombre} emplazada en {self._texto_pos(b.x, b.y)}", "ambar")
        else:
            self.ep.log(f"{b.nombre} en marcha hacia {self._texto_pos(x, y)} · llegada en {mmss(b.eta())}", "ambar")

    def _optima(self):
        self._reubicar_todas()
        if self.preparando:
            self._asentar()

    def _mover_bateria(self):
        if self._real():
            self._buscar("mover")
            return
        self._mover_a(*self._coords())

    def _mover_a(self, x, y):
        if not (0 <= x <= C.MAPA_W and 0 <= y <= C.MAPA_H):
            self.avisar("Ese punto queda fuera del mapa")
            return
        if M.distancia_frente(x, y, self.ep.frentes) < C.DISTANCIA_FRENTE_MIN:
            self.avisar(f"Demasiado cerca del frente (mínimo {C.DISTANCIA_FRENTE_MIN / 1000:.0f} km)")
            return
        self._ir(x, y)

    def _quitar_areas(self):
        if self.modo != "comandante" and self._real():
            self._quitar_lugares()
            return
        self.ep.zonas[:] = [z for z in self.ep.zonas if z.tipo != "area"]
        for z in self.ep.zonas:
            z.activa = False
        self.ep.log("Se quitaron todas las áreas protegidas", "ambar")

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

    def _amenaza_en(self, pos):
        mejor, dmin = None, 14 * self.k
        for am in self.ep.activas:
            if not (am.detectada or self.verdad):
                continue
            x, y, _ = am.pos(self.ep.t)
            px, py = self.a_pantalla(x, y)
            d = math.hypot(px - pos[0], py - pos[1])
            if d < dmin:
                mejor, dmin = am, d
        return mejor

    def _eventos(self):
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                return False
            if e.type == pygame.VIDEORESIZE:
                self.pantalla = pygame.display.set_mode((max(e.w, 1100), max(e.h, 680)), pygame.RESIZABLE)
                self._layout()
            elif e.type == pygame.KEYDOWN:
                campos = self._campos_visibles()
                foco = next((c for c in campos if c.foco), None)
                if foco is not None and e.key != pygame.K_ESCAPE:
                    if e.key == pygame.K_TAB:
                        i = campos.index(foco)
                        foco.foco = False
                        campos[(i + 1) % len(campos)].foco = True
                    elif e.key in (pygame.K_RETURN, pygame.K_KP_ENTER) and foco is self.campo_lugar:
                        foco.foco = False
                        self._barra_lugar(0 if self.modo == "comandante" or not self.lugares else 1)
                    else:
                        foco.tecla(e)
                    continue
                if e.key == pygame.K_ESCAPE:
                    if foco is not None:
                        foco.foco = False
                        continue
                    return False
                if e.key == pygame.K_SPACE:
                    if self.preparando:
                        self._comenzar()
                    else:
                        self._pausar()
                elif e.key in (pygame.K_PLUS, pygame.K_KP_PLUS, pygame.K_EQUALS):
                    i = VELOCIDADES.index(self.velocidad)
                    self.velocidad = VELOCIDADES[min(i + 1, len(VELOCIDADES) - 1)]
                elif e.key in (pygame.K_MINUS, pygame.K_KP_MINUS):
                    i = VELOCIDADES.index(self.velocidad)
                    self.velocidad = VELOCIDADES[max(i - 1, 0)]
                elif e.key == pygame.K_v:
                    self.verdad = not self.verdad
                elif e.key == pygame.K_HOME:
                    self.esc, self.cx, self.cy = self.s0, C.MAPA_W / 2, C.MAPA_H / 2
                    self._cache_mapa = None
                elif e.key == pygame.K_F9:
                    self._grabar()
                elif e.key == pygame.K_F12:
                    self.captura()
                elif e.key == pygame.K_r:
                    self._reiniciar_ep()
            elif e.type == pygame.MOUSEBUTTONDOWN:
                if e.button in (4, 5) and self.r_mapa.collidepoint(e.pos):
                    wx, wy = self.a_mundo(*e.pos)
                    self.esc = min(max(self.esc * (1.2 if e.button == 4 else 1 / 1.2), self.s0), self._zona_max())
                    nx, ny = self.a_mundo(*e.pos)
                    self.cx += wx - nx
                    self.cy += wy - ny
                    self._limitar_vista()
                    self._cache_mapa = None
                elif e.button in (1, 3):
                    self._clic(e.pos, e.button, pygame.key.get_mods() & pygame.KMOD_SHIFT)
            elif e.type == pygame.MOUSEBUTTONUP:
                if e.button == 1 and self.arrastre_bat is not None:
                    self._soltar_bateria(e.pos)
                elif e.button == 1 and self.arrastre is not None:
                    if not self.arrastre[2]:
                        self._clic_mapa(self.arrastre[0], pygame.key.get_mods() & pygame.KMOD_SHIFT)
                    self.arrastre = None
            elif e.type == pygame.MOUSEMOTION and self.arrastre_bat is not None:
                i, p0, movido = self.arrastre_bat
                if movido or math.hypot(e.pos[0] - p0[0], e.pos[1] - p0[1]) > 5:
                    self.arrastre_bat = (i, p0, True)
            elif e.type == pygame.MOUSEMOTION and self.arrastre is not None:
                p0, c0, movido = self.arrastre
                if movido or math.hypot(e.pos[0] - p0[0], e.pos[1] - p0[1]) > 5:
                    self.cx = c0[0] - (e.pos[0] - p0[0]) / self.esc
                    self.cy = c0[1] + (e.pos[1] - p0[1]) / self.esc
                    self._limitar_vista()
                    self._cache_mapa = None
                    self.arrastre = (p0, c0, True)
        return True

    def _campos_visibles(self):
        if self.modo in ("entrenar", "campeon"):
            return [self.campo_lugar]
        if self._real():
            return [self.campo_lugar, self.campos[2], self.campos[3]]
        return [self.campo_lugar] + list(self.campos)

    def _clic(self, pos, boton, shift):
        for c in self.campos + [self.campo_lugar]:
            c.foco = False
        if boton == 1:
            botones = [self.btn_grabar] + self.btn_modos + self.btn_vel + [self.btn_pausa] + self.btn_mapa + self.btn_lugar
            if self._real():
                botones += self.btn_vista
            if self.preparando:
                botones = [self.btn_comenzar] + botones
            botones += self.btn_perfil
            if self.modo in ("campeon", "jugar"):
                botones += self.btn_mis
            botones.append(self.btn_reiniciar)
            if self.modo == "entrenar":
                botones += self.btn_ent
            if self.modo in ("jugar", "comandante"):
                botones += self.btn_desp
            if self.modo == "comandante":
                botones += self.btn_ctrl + self.btn_frentes + [self.btn_google]
            if self.modo in ("jugar", "comandante"):
                botones += self.btn_lanz + self.btn_bats
            if self.modo == "entrenar":
                botones += self.btn_cfg + [self.btn_rapido]
            for rr, i in self._tabs:
                if rr.collidepoint(pos):
                    self.bat_sel = i
                    return
            if self.modo == "jugar":
                botones.append(self.btn_apoyo)
                botones += self.btn_areas
            for b in botones:
                if b.clic(pos):
                    return
            if True:
                for c in self._campos_visibles():
                    if c.rect.collidepoint(pos):
                        c.foco = True
                        if not c.libre:
                            c.valor = ""
                        return
        if self.r_mapa.collidepoint(pos):
            i = self._bateria_en_pantalla(pos) if self.modo in ("jugar", "comandante") else None
            if boton == 1 and i is not None:
                self.bat_sel = i
                self.arrastre_bat = (i, pos, False)
            elif boton == 1:
                self.arrastre = (pos, (self.cx, self.cy), False)
            else:
                self._clic_mapa(pos, True)

    def _bateria_en_pantalla(self, pos):
        mejor, dmin = None, 16 * self.k
        for i, b in enumerate(self.ep.baterias):
            if b.destruida:
                continue
            bp = self.a_pantalla(b.x, b.y)
            d = math.hypot(bp[0] - pos[0], bp[1] - pos[1])
            if d < dmin:
                mejor, dmin = i, d
        return mejor

    def _destino_arrastre(self, pos):
        x, y = self.a_mundo(*pos)
        x = min(max(x, 1000.0), C.MAPA_W - 1000)
        y = min(max(y, 1000.0), C.MAPA_H - 1000)
        ok = M.distancia_frente(x, y, self.ep.frentes) >= C.DISTANCIA_FRENTE_MIN
        return x, y, ok

    def _soltar_bateria(self, pos):
        i, p0, movido = self.arrastre_bat
        self.arrastre_bat = None
        if not movido or i >= len(self.ep.baterias):
            return
        self.bat_sel = i
        x, y, ok = self._destino_arrastre(pos)
        if not ok:
            self.avisar(f"Demasiado cerca del frente (mínimo {C.DISTANCIA_FRENTE_MIN / 1000:.0f} km): no se movió")
            return
        if self._real() and self.geo is not None:
            lat, lon = self.geo.a_latlon(x, y)
            self.campo_lugar.valor = f"{lat:.5f}, {lon:.5f}"
        else:
            self.campos[0].poner(round(x / 1000, 1))
            self.campos[1].poner(round(y / 1000, 1))
        self._ir(x, y)

    def _vista_arrastre(self):
        if self.arrastre_bat is None or not self.arrastre_bat[2]:
            return
        i = self.arrastre_bat[0]
        if i >= len(self.ep.baterias):
            return
        s = self.pantalla
        k = self.k
        b = self.ep.baterias[i]
        pos = pygame.mouse.get_pos()
        x, y, ok = self._destino_arrastre(pos)
        col = (245, 180, 0) if ok else ROJO
        o = self.a_pantalla(b.x, b.y)
        d = self.a_pantalla(x, y)
        capa = pygame.Surface(s.get_size(), pygame.SRCALPHA)
        pygame.draw.circle(capa, (*col, 22), d, C.INT_ALCANCE * self.esc)
        self._circulo_disc(capa, (*col, 200), d, C.INT_ALCANCE * self.esc, 8 * k, max(1, int(2 * k)))
        n = max(2, int(math.dist(o, d) / (10 * k)))
        for j in range(0, n, 2):
            q0 = (o[0] + (d[0] - o[0]) * j / n, o[1] + (d[1] - o[1]) * j / n)
            q1 = (o[0] + (d[0] - o[0]) * (j + 1) / n, o[1] + (d[1] - o[1]) * (j + 1) / n)
            pygame.draw.line(capa, (*col, 230), q0, q1, max(1, int(2 * k)))
        tri = [(d[0], d[1] - 9 * k), (d[0] - 8 * k, d[1] + 6 * k), (d[0] + 8 * k, d[1] + 6 * k)]
        pygame.draw.polygon(capa, (*col, 160), tri)
        s.blit(capa, (0, 0))
        dist = math.hypot(x - b.x, y - b.y)
        eta = C.T_PLEGAR + dist / C.VEL_CONVOY + C.T_DESPLEGAR if b.operativa or b.estado == "desplegando" else dist / C.VEL_CONVOY + C.T_DESPLEGAR
        cubre = [z.nombre for z in self.ep.zonas if z.activa and M.cobertura(z, x, y) >= 0.9]
        lineas = [f"{b.nombre} → {self._texto_pos(x, y)}",
                  f"{dist / 1000:.1f} km · " + ("colocación inmediata (despliegue)" if self.preparando else f"listo en {mmss(eta)}")]
        if not ok:
            lineas.append("Demasiado cerca de la zona hostil")
        elif cubre:
            lineas.append("Cubre: " + ", ".join(cubre)[:48])
        w = max(self.f_chica.size(t)[0] for t in lineas) + 20
        rr = pygame.Rect(d[0] + 18 * k, d[1] - 10 * k, w, len(lineas) * int(17 * k) + 10)
        zona = self.r_mapa.copy()
        zona.top += int(50 * k)
        rr.clamp_ip(zona)
        pygame.draw.rect(s, (14, 16, 20), rr, border_radius=6)
        pygame.draw.rect(s, col, rr, 1, border_radius=6)
        yy = rr.y + 5
        for t in lineas:
            s.blit(self.f_chica.render(t, True, TEXTO), (rr.x + 10, yy))
            yy += int(17 * k)

    def _actualizar_cursor(self):
        pos = pygame.mouse.get_pos()
        if self.arrastre_bat is not None:
            deseado = pygame.SYSTEM_CURSOR_SIZEALL
        elif (self.modo in ("jugar", "comandante") and self.r_mapa.collidepoint(pos)
              and self._bateria_en_pantalla(pos) is not None):
            deseado = pygame.SYSTEM_CURSOR_HAND
        else:
            deseado = pygame.SYSTEM_CURSOR_ARROW
        if deseado != self._cursor:
            try:
                pygame.mouse.set_system_cursor(deseado)
            except Exception:
                pass
            self._cursor = deseado

    def _clic_mapa(self, pos, doble):
        am = self._amenaza_en(pos)
        manual = isinstance(self.ep.controlador, ControladorManual)
        if am is not None:
            self.seleccion = am.id
            if manual and am.detectada:
                self.ep.controlador.ordenar(am.id, 2 if doble else 1)
                self.ep.log(f"Orden: enfrentar #{am.id} con {2 if doble else 1} interceptor{'es' if doble else ''}", "cian")
            return
        for i, b in enumerate(self.ep.baterias):
            bp = self.a_pantalla(b.x, b.y)
            if math.hypot(bp[0] - pos[0], bp[1] - pos[1]) < 14 * self.k:
                self.bat_sel = i
                return
        x, y = self.a_mundo(*pos)
        eligiendo = self.modo == "jugar" and self.preparando and not self.areas_auto and not self.ep.m.get("lugar")
        if self.modo == "comandante" or eligiendo:
            for z in self.ep.zonas:
                if (z.tipo == "pueblo" or eligiendo) and z.contiene(x, y):
                    z.activa = not z.activa
                    self.ep.log(("Protegiendo " if z.activa else "Sin protección: ") + z.nombre, "ambar")
                    return
        if self._real() and self.geo is not None:
            lat, lon = self.geo.a_latlon(x, y)
            self.campo_lugar.valor = f"{lat:.5f}, {lon:.5f}"
        elif self.modo in ("jugar", "comandante"):
            self.campos[0].poner(round(x / 1000, 1))
            self.campos[1].poner(round(y / 1000, 1))
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

    def _avanzar(self, dt_real):
        ep = self.ep
        if self.preparando:
            self._asentar()
            return
        if self.pausa:
            return
        vel = self.velocidad
        if ep.calma and self.modo != "jugar":
            vel = max(vel, 30)
        elif ep.calma:
            vel = max(vel, 12)
        self.acum += dt_real * vel
        limite = time.perf_counter() + 0.02
        while self.acum > 0 and not ep.terminado and time.perf_counter() < limite:
            t0 = ep.t
            ep.paso()
            self.acum -= ep.t - t0
            for am in ep.activas:
                if am.detectada and (not am.rastro or ep.t - am.rastro[-1][3] >= 1.0):
                    am.rastro.append((*am.pos(ep.t), ep.t))
                    if len(am.rastro) > 80:
                        am.rastro.pop(0)
            for it in ep.interceptores:
                if ep.t >= it.t_lanz and (not it.rastro or ep.t - it.rastro[-1][3] >= 0.5):
                    it.rastro.append((it.x, it.y, it.z, ep.t))
                    if len(it.rastro) > 50:
                        it.rastro.pop(0)
        self.acum = min(self.acum, 2.0)
        if ep.terminado:
            if not hasattr(ep, "_fin"):
                ep._fin = time.time()
                r = ep.resumen()
                ep.log(f"Fin del escenario · protección {100 * r['proteccion']:.0f}% · "
                       f"{'SUPERADO' if r['superada'] else 'no superado'}", "verde" if r["superada"] else "rojo")
                if self.modo == "jugar":
                    self._enviar_demos()
            elif time.time() - ep._fin > 4.0 and self.modo != "comandante":
                self._nuevo_ep()

    def _mapa_fondo(self):
        real = self._real() and self.geo is not None
        base = self._fondo_real() if real else self._terreno_base
        frentes = tuple(self.ep.frentes)
        clave = (round(self.cx), round(self.cy), round(self.esc, 8), self.r_mapa.size, id(base), frentes,
                 real and self.vista, real and self.geo.clave, self._ver_teselas if real else 0)
        if self._cache_mapa is not None and self._cache_mapa[0] == clave:
            return self._cache_mapa[1]
        r = self.r_mapa
        x0, y1 = self.a_mundo(r.left, r.top)
        x1, y0 = self.a_mundo(r.right, r.bottom)
        sup = pygame.Surface(r.size)
        sup.fill((12, 14, 13))
        sx0, sx1 = max(x0, 0), min(x1, C.MAPA_W)
        sy0, sy1 = max(y0, 0), min(y1, C.MAPA_H)
        if base is not None and sx1 > sx0 and sy1 > sy0:
            bw, bh = base.get_size()
            fx, fy = bw / C.MAPA_W, bh / C.MAPA_H
            rect = pygame.Rect(int(sx0 * fx), int((C.MAPA_H - sy1) * fy), max(1, int((sx1 - sx0) * fx)),
                               max(1, int((sy1 - sy0) * fy)))
            rect = rect.clip(base.get_rect())
            trozo = base.subsurface(rect)
            dw, dh = int((sx1 - sx0) * self.esc), int((sy1 - sy0) * self.esc)
            px, py = self.a_pantalla(sx0, sy1)
            sup.blit(pygame.transform.smoothscale(trozo, (max(dw, 1), max(dh, 1))), (px - r.x, py - r.y))
        self._faltan_teselas = 0
        if real:
            self._detalle(sup, sx0, sx1, sy0, sy1)
        capa = pygame.Surface(r.size, pygame.SRCALPHA)
        for nombre, (fx0, fy0, fx1, fy1) in M.FRENTES.items():
            if nombre not in frentes:
                continue
            a = self.a_pantalla(fx0, fy1)
            b = self.a_pantalla(fx1, fy0)
            rr = pygame.Rect(a[0] - r.x, a[1] - r.y, b[0] - a[0], b[1] - a[1])
            pygame.draw.rect(capa, (200, 40, 40, 38), rr)
            paso = int(14 * self.k)
            for d in range(-rr.h, rr.w, paso):
                p1 = (rr.x + max(d, 0), rr.y + max(-d, 0))
                p2 = (rr.x + min(d + rr.h, rr.w), rr.y + min(rr.h, rr.w - d))
                pygame.draw.line(capa, (220, 60, 60, 40), p1, p2, 1)
        for a, b in (M.caminos() if base is self._terreno_base else []):
            pa, pb = self.a_pantalla(*a), self.a_pantalla(*b)
            pygame.draw.line(capa, (120, 120, 110, 110), (pa[0] - r.x, pa[1] - r.y), (pb[0] - r.x, pb[1] - r.y),
                             max(1, int(2 * self.k)))
        paso_km = 10 if self.esc < self.s0 * 2.5 else (5 if self.esc < self.s0 * 6 else 2)
        for xk in range(0, int(C.MAPA_W / 1000) + 1, paso_km):
            px, _ = self.a_pantalla(xk * 1000, 0)
            if r.left <= px <= r.right:
                pygame.draw.line(capa, (255, 255, 255, 22), (px - r.x, 0), (px - r.x, r.h))
                img = self.f_mini.render(str(xk), True, (200, 205, 215))
                capa.blit(img, (px - r.x + 3, r.h - img.get_height() - 2))
        for yk in range(0, int(C.MAPA_H / 1000) + 1, paso_km):
            _, py = self.a_pantalla(0, yk * 1000)
            if r.top <= py <= r.bottom:
                pygame.draw.line(capa, (255, 255, 255, 22), (0, py - r.y), (r.w, py - r.y))
                img = self.f_mini.render(str(yk), True, (200, 205, 215))
                capa.blit(img, (3, py - r.y - img.get_height() - 1))
        sup.blit(capa, (0, 0))
        for nombre, (fx0, fy0, fx1, fy1) in M.FRENTES.items():
            if nombre == "noreste" or nombre not in frentes:
                continue
            cxp, cyp = self.a_pantalla((fx0 + fx1) / 2, (fy0 + fy1) / 2)
            img = self.f_mini.render("ZONA HOSTIL", True, (255, 120, 120))
            if nombre in ("este", "oeste"):
                img = pygame.transform.rotate(img, 90)
            sup.blit(img, img.get_rect(center=(cxp - r.x, cyp - r.y)))
        self._cache_mapa = (clave, sup)
        return sup

    def _tesela_o_padre(self, vista, z, tx, ty):
        img = self._teselas.get((vista, z, tx, ty))
        if img is not None:
            self._teselas.move_to_end((vista, z, tx, ty))
            return img
        for d in range(1, 6):
            padre = self._teselas.get((vista, z - d, tx >> d, ty >> d))
            if padre is not None:
                lado = 256 >> d
                return padre.subsurface(((tx - ((tx >> d) << d)) * lado, (ty - ((ty >> d) << d)) * lado, lado, lado))
        return None

    def _detalle(self, sup, x0, x1, y0, y1):
        geo, r, vista = self.geo, self.r_mapa, self.vista
        z = G.zoom_para(1 / self.esc, geo.lat, vista)
        if z <= G.ZOOM or x1 <= x0 or y1 <= y0:
            return
        norte, oeste = geo.a_latlon(x0, y1)
        sur, este = geo.a_latlon(x1, y0)
        a, b = G._tesela(norte, oeste, z), G._tesela(sur, este, z)
        tx0, ty0, tx1, ty1 = int(a[0]), int(a[1]), int(b[0]), int(b[1])
        if (tx1 - tx0 + 1) * (ty1 - ty0 + 1) > 100:
            return
        pa, pb = self.a_pantalla(x0, y1), self.a_pantalla(x1, y0)
        sup.set_clip(pygame.Rect(int(pa[0] - r.x), int(pa[1] - r.y), int(pb[0] - pa[0]) + 1, int(pb[1] - pa[1]) + 1))
        cx, cy = (tx0 + tx1) / 2, (ty0 + ty1) / 2
        faltan = 0
        for tx, ty in sorted(((i, j) for i in range(tx0, tx1 + 1) for j in range(ty0, ty1 + 1)),
                             key=lambda t: -math.hypot(t[0] - cx, t[1] - cy)):
            if (vista, z, tx, ty) not in self._teselas:
                faltan += 1
                self.cargador.pedir((vista, z, tx, ty))
            img = self._tesela_o_padre(vista, z, tx, ty)
            if img is None:
                continue
            s_, o_, n_, e_ = G.limites_tesela(z, tx, ty)
            ax, ay = self.a_pantalla(*geo.a_metros(n_, o_))
            bx, by = self.a_pantalla(*geo.a_metros(s_, e_))
            ix, iy = math.floor(ax - r.x), math.floor(ay - r.y)
            w, h = math.ceil(bx - r.x) - ix, math.ceil(by - r.y) - iy
            if w > 0 and h > 0:
                sup.blit(pygame.transform.smoothscale(img, (w, h)), (ix, iy))
        sup.set_clip(None)
        self._faltan_teselas = faltan

    def _circulo_disc(self, sup, color, c, rad, paso=10, grosor=1):
        if rad < 3:
            return
        n = max(24, int(rad / paso) * 2)
        for i in range(0, n, 2):
            a0, a1 = 2 * math.pi * i / n, 2 * math.pi * (i + 1) / n
            pygame.draw.line(sup, color, (c[0] + rad * math.cos(a0), c[1] + rad * math.sin(a0)),
                             (c[0] + rad * math.cos(a1), c[1] + rad * math.sin(a1)), grosor)

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
        etiquetas = self.esc > self.s0 * 1.8 or sum(1 for a in ep.activas if a.detectada) <= 8
        for am in ep.activas:
            if am.detectada:
                ix, iy = am.impacto_est()
                z = ep.zona_en(ix, iy)
                if z is not None:
                    amenazadas.add(z.nombre)
                sobre = ep.sobrevuelo(am)
                if sobre:
                    amenazadas.add(sobre)
        cobs = {id(z): c for z, c in self._coberturas()}
        pulso = (time.time() * 0.8) % 1.0
        for z in ep.zonas:
            c = self.a_pantalla(z.x, z.y)
            rad = z.r * self.esc
            if z.activa:
                cob = cobs.get(id(z), 0.0)
                if z.nombre in amenazadas and int(time.time() * 3) % 2 == 0:
                    col = ROJO
                elif self.preparando:
                    col = VERDE if cob >= 0.9 else (NARANJA if cob > 0.3 else ROJO)
                else:
                    col = CIAN if cob >= 0.9 else NARANJA
                pygame.draw.circle(capa, (*col, 58 if self.esc < 0.12 else 22), c, rad)
                pygame.draw.circle(capa, (*col, 55), c, rad + 4 * k, max(2, int(4 * k)))
                pygame.draw.circle(capa, (*col, 235), c, rad, max(2, int(2.5 * k)))
                self._circulo_disc(capa, (*col, 120), c, rad * 0.55, 6 * k)
                pygame.draw.circle(capa, (*col, 255), c, max(2, int(3 * k)))
                if self.preparando:
                    pygame.draw.circle(capa, (*col, int(150 * (1 - pulso))), c, rad + (6 + 18 * pulso) * k,
                                       max(1, int(2 * k)))
            else:
                pygame.draw.circle(capa, (200, 200, 190, 18), c, rad)
                pygame.draw.circle(capa, (200, 200, 190, 70), c, rad, 1)
                if self.preparando and not self.areas_auto:
                    self._circulo_disc(capa, (255, 255, 255, 170), c, rad + 3 * k, 5 * k, max(1, int(1.5 * k)))
            if z.tipo == "pueblo":
                rng = np.random.default_rng(abs(hash(z.nombre)) % 1000)
                for _ in range(14):
                    a = rng.uniform(0, 2 * math.pi)
                    d = rng.uniform(0, 0.6) * rad
                    tam = max(2, int(rng.uniform(1.5, 3.5) * k))
                    pygame.draw.rect(capa, (210, 205, 180, 150), (c[0] + d * math.cos(a), c[1] + d * math.sin(a), tam, tam))
        sel = self._bat()
        alc = pygame.Surface(s.get_size(), pygame.SRCALPHA)
        for bat in ep.baterias:
            if not bat.destruida:
                cb = self.a_pantalla(bat.x, bat.y)
                pygame.draw.circle(alc, (61, 214, 245, 10), cb, C.INT_ALCANCE * self.esc)
                if self.preparando:
                    pygame.draw.circle(alc, (56, 211, 159, 26), cb, C.INT_ALCANCE * 0.8 * self.esc)
        for bat in ep.baterias:
            cb = self.a_pantalla(bat.x, bat.y)
            if not bat.destruida:
                if self.preparando:
                    self._circulo_disc(alc, (56, 211, 159, 150), cb, C.INT_ALCANCE * 0.8 * self.esc, 6 * k,
                                       max(1, int(1.5 * k)))
                fuerte = 110 if bat is sel else 70
                self._circulo_disc(alc, (61, 214, 245, fuerte), cb, C.INT_ALCANCE * self.esc, 8 * k, max(1, int(1.5 * k)))
                if bat is sel:
                    self._circulo_disc(alc, (255, 255, 255, 30), cb, C.RADAR_ALCANCE * self.esc, 14 * k)
                if bat.operativa:
                    ang = (time.time() * 1.6 + hash(bat.nombre) % 7) % (2 * math.pi)
                    L = C.INT_ALCANCE * 1.25 * self.esc
                    for i in range(8):
                        a = ang - i * 0.025
                        pygame.draw.line(alc, (61, 214, 245, 40 - i * 5), cb, (cb[0] + L * math.cos(a), cb[1] - L * math.sin(a)), 2)
            if bat.destino is not None:
                d = self.a_pantalla(*bat.destino)
                self._circulo_disc(capa, (245, 180, 0, 160), d, C.INT_ALCANCE * self.esc, 10 * k)
                n = max(2, int(math.dist(cb, d) / (10 * k)))
                for i in range(0, n, 2):
                    p0 = (cb[0] + (d[0] - cb[0]) * i / n, cb[1] + (d[1] - cb[1]) * i / n)
                    p1 = (cb[0] + (d[0] - cb[0]) * (i + 1) / n, cb[1] + (d[1] - cb[1]) * (i + 1) / n)
                    pygame.draw.line(capa, (245, 180, 0, 220), p0, p1, max(1, int(2 * k)))
                pygame.draw.circle(capa, (245, 180, 0, 230), d, 5 * k, 2)
        for x, y, ti, en_zona in ep.impactos:
            edad = t - ti
            if edad > 90:
                continue
            p = self.a_pantalla(x, y)
            a = int(200 * (1 - edad / 90))
            col = (255, 80, 60, a) if en_zona else (150, 150, 150, a // 2)
            e = 4 * k
            pygame.draw.line(capa, col, (p[0] - e, p[1] - e), (p[0] + e, p[1] + e), 2)
            pygame.draw.line(capa, col, (p[0] - e, p[1] + e), (p[0] + e, p[1] - e), 2)
        for am in ep.activas:
            if not (am.detectada or self.verdad):
                continue
            col = COLOR_TIPO[am.tipo]
            x, y, z = am.pos(t)
            p = self.a_pantalla(x, y)
            if not am.detectada:
                pygame.draw.circle(capa, (*col, 90), p, 3 * k)
                continue
            if len(am.rastro) > 1:
                pts = [self.a_pantalla(q[0], q[1]) for q in am.rastro] + [p]
                pygame.draw.lines(capa, (*col, 120), False, pts, max(1, int(1.5 * k)))
            ix, iy = am.impacto_est()
            pi = self.a_pantalla(ix, iy)
            amenaza = ep.valor_amenaza(am, am.sigma() * 0.8) > 0
            cimp = (255, 80, 80, 200) if amenaza else (170, 170, 170, 120)
            self._circulo_disc(capa, cimp, pi, max(am.sigma() * self.esc, 3 * k), 5 * k)
            e = 4 * k
            pygame.draw.line(capa, cimp, (pi[0] - e, pi[1] - e), (pi[0] + e, pi[1] + e), 2)
            pygame.draw.line(capa, cimp, (pi[0] - e, pi[1] + e), (pi[0] + e, pi[1] - e), 2)
            n = max(2, int(math.dist(p, pi) / (6 * k)))
            for i in range(0, n, 3):
                q0 = (p[0] + (pi[0] - p[0]) * i / n, p[1] + (pi[1] - p[1]) * i / n)
                q1 = (p[0] + (pi[0] - p[0]) * (i + 1) / n, p[1] + (pi[1] - p[1]) * (i + 1) / n)
                pygame.draw.line(capa, (*cimp[:3], 90), q0, q1, 1)
            dx, dy = am.bx - am.ax, am.by - am.ay
            ang = math.atan2(-dy, dx)
            tam = 7 * k
            tri = [(p[0] + tam * math.cos(ang), p[1] + tam * math.sin(ang)),
                   (p[0] + tam * 0.6 * math.cos(ang + 2.5), p[1] + tam * 0.6 * math.sin(ang + 2.5)),
                   (p[0] + tam * 0.6 * math.cos(ang - 2.5), p[1] + tam * 0.6 * math.sin(ang - 2.5))]
            pygame.draw.polygon(capa, (*col, 255), tri)
            if am.en_vuelo:
                pygame.draw.circle(capa, (61, 214, 245, 220), p, 10 * k, 1)
            if am.fijada:
                self._reticula(capa, p, t - (am.t_fijada or t), am.en_vuelo > 0)
            if am.id == self.seleccion or am is self.hover:
                pygame.draw.circle(capa, (255, 255, 255, 230), p, 13 * k, 2)
            if etiquetas:
                etq = self.f_mini.render(f"#{am.id} {z / 1000:.1f}km", True, (*col,))
                capa.blit(etq, (p[0] + 8 * k, p[1] - 6 * k))
        for it in ep.interceptores:
            if t < it.t_lanz:
                continue
            p = self.a_pantalla(it.x, it.y)
            if len(it.rastro) > 1:
                pts = [self.a_pantalla(q[0], q[1]) for q in it.rastro] + [p]
                pygame.draw.lines(capa, (61, 214, 245, 170), False, pts, max(1, int(1.5 * k)))
            pygame.draw.circle(capa, (200, 250, 255, 255), p, 3 * k)
        for ex, ey, ez, te, tipo in ep.explosiones:
            edad = t - te
            if edad < 0 or edad > 3:
                continue
            p = self.a_pantalla(ex, ey)
            f = edad / 3
            if tipo == "derribo":
                col, rmax = (255, 240, 170), 26
            elif tipo == "impacto":
                col, rmax = (255, 110, 40), 30
            elif tipo == "fallo":
                col, rmax = (255, 170, 60), 12
            else:
                col, rmax = (150, 150, 150), 8
            rad = max(2, int(rmax * k * (0.3 + f)))
            pygame.draw.circle(capa, (*col, int(230 * (1 - f))), p, rad, max(1, int(3 * k * (1 - f)) + 1))
            if f < 0.3:
                pygame.draw.circle(capa, (*col, int(200 * (1 - f / 0.3))), p, rad * 0.5)
        s.blit(alc, (0, 0))
        s.blit(capa, (0, 0))
        for bat in ep.baterias:
            cb = self.a_pantalla(bat.x, bat.y)
            for i, (lx, ly) in enumerate(bat.lanzadores()):
                lp = self.a_pantalla(lx, ly)
                if len(bat.misiles) > 1:
                    pygame.draw.line(s, (40, 70, 80), cb, lp, 1)
                rr = pygame.Rect(0, 0, 9 * k, 6 * k)
                rr.center = lp
                vivo = bat.misiles[i] > 0 and not bat.destruida
                pygame.draw.rect(s, (61, 214, 245) if vivo else SUTIL, rr, border_radius=2)
            tri = [(cb[0], cb[1] - 9 * k), (cb[0] - 8 * k, cb[1] + 6 * k), (cb[0] + 8 * k, cb[1] + 6 * k)]
            pygame.draw.polygon(s, ESTADOS[bat.estado][1], tri)
            pygame.draw.polygon(s, FONDO, tri, 2)
            if bat is sel and len(ep.baterias) > 1:
                pygame.draw.circle(s, (255, 255, 255), cb, 15 * k, 2)
            img = self.f_mini.render(bat.nombre, True, (255, 255, 255))
            caja = img.get_rect(midleft=(cb[0] + 12 * k, cb[1] + 10 * k))
            pygame.draw.rect(s, (14, 16, 20), caja.inflate(8, 2), border_radius=4)
            s.blit(img, caja)
        for z in ep.zonas:
            if not (z.activa or z.tipo == "pueblo"):
                continue
            c = self.a_pantalla(z.x, z.y)
            base_y = c[1] + z.r * self.esc + 6 * k
            if not z.activa:
                txt = z.nombre + (" · clic para proteger" if self.preparando and not self.areas_auto else "")
                img = self.f_mini.render(txt, True, (190, 190, 180))
                s.blit(img, img.get_rect(midtop=(c[0], base_y - 4 * k)))
                continue
            cob = cobs.get(id(z), 0.0)
            col = VERDE if cob >= 0.9 else (NARANJA if cob > 0.3 else ROJO)
            estado = "" if cob >= 0.9 else (" · SIN COBERTURA" if cob <= 0.3 else " · parcial")
            l1 = self.f_semi.render(z.nombre, True, TEXTO)
            l2 = self.f_mini.render(f"valor {int(z.valor)}/3 · cubierta {100 * cob:.0f}%{estado}", True, col)
            w = max(l1.get_width(), l2.get_width()) + int(18 * k)
            caja = pygame.Rect(0, 0, w, l1.get_height() + l2.get_height() + int(6 * k))
            caja.midtop = (c[0], base_y)
            pygame.draw.rect(s, (14, 16, 20), caja, border_radius=6)
            pygame.draw.rect(s, col, caja, 1, border_radius=6)
            pygame.draw.rect(s, col, (caja.x, caja.y + 4, max(3, int(3 * k)), caja.h - 8), border_radius=2)
            s.blit(l1, l1.get_rect(midtop=(caja.centerx + 2, caja.y + 2 * k)))
            s.blit(l2, l2.get_rect(midtop=(caja.centerx + 2, caja.y + 2 * k + l1.get_height())))
        self.hover = self._amenaza_en(pygame.mouse.get_pos()) if r.collidepoint(pygame.mouse.get_pos()) else None
        sel = self.hover or next((a for a in ep.activas if a.id == self.seleccion), None)
        if sel is not None and sel.detectada and self.arrastre_bat is None:
            self._ficha_amenaza(sel)
        self._vista_arrastre()
        s.set_clip(prev)
        pygame.draw.rect(s, BORDE, r, 1)
        self._barra_mapa()

    def _reticula(self, capa, p, edad, enfrentada):
        k = self.k
        cierre = min(edad / 1.2, 1.0)
        tam = (22 - 8 * cierre) * k
        col = (61, 214, 245) if enfrentada else (255, 70, 60)
        a = 255 if cierre >= 1 or int(edad * 8) % 2 == 0 else 120
        g = max(2, int(2 * k))
        L = tam * 0.45
        for sx in (-1, 1):
            for sy in (-1, 1):
                cx, cy = p[0] + sx * tam, p[1] + sy * tam
                pygame.draw.line(capa, (*col, a), (cx, cy), (cx - sx * L, cy), g)
                pygame.draw.line(capa, (*col, a), (cx, cy), (cx, cy - sy * L), g)
        if cierre >= 1:
            pygame.draw.line(capa, (*col, 160), (p[0] - tam * 0.35, p[1]), (p[0] + tam * 0.35, p[1]), 1)
            pygame.draw.line(capa, (*col, 160), (p[0], p[1] - tam * 0.35), (p[0], p[1] + tam * 0.35), 1)
        etq = self.f_mini.render("FIJADO" if not enfrentada else "EN TIRO", True, col)
        capa.blit(etq, etq.get_rect(midbottom=(p[0], p[1] - tam - 2 * k)))

    def _ficha_amenaza(self, am):
        ep = self.ep
        x, y, z = am.pos(ep.t)
        p = self.a_pantalla(x, y)
        sol = ep.solucion(am)
        ix, iy = am.impacto_est()
        zona = ep.zona_en(ix, iy)
        dest = zona.nombre if zona else ("la batería" if ep.valor_en(ix, iy) else "campo abierto")
        sobre = ep.sobrevuelo(am)
        lineas = [(f"{am.p['nombre']} #{am.id}", COLOR_TIPO[am.tipo]),
                  (f"Altitud {z / 1000:.2f} km · impacto en {am.t_impacto - ep.t:.0f} s", TEXTO),
                  (f"Impacto previsto: {dest} (±{am.sigma():.0f} m)", ROJO if dest != "campo abierto" else TENUE),
                  (f"Calidad de traza {100 * am.calidad():.0f}%", TENUE)]
        if sobre and dest == "campo abierto":
            lineas.insert(3, (f"Sobrevuela {sobre}: objetivo fijado", ROJO))
        elif am.fijada:
            lineas.insert(3, (f"Objetivo fijado desde hace {ep.t - am.t_fijada:.0f} s", ROJO))
        if sol:
            lineas.append((f"Solución de tiro: Pk {100 * sol[3]:.0f}% · ventana {sol[2]:.0f} s", VERDE))
        else:
            lineas.append(("Sin solución de tiro", NARANJA))
        if isinstance(ep.controlador, ControladorManual):
            lineas.append(("Clic: 1 interceptor · Shift/clic der.: 2", SUTIL))
            if am.fijada:
                lineas.append(("Fijado: se derriba automáticamente", SUTIL))
        w = max(self.f_chica.size(t)[0] for t, _ in lineas) + 20
        h = len(lineas) * int(17 * self.k) + 12
        rr = pygame.Rect(p[0] + 16, p[1] - h // 2, w, h)
        if rr.right > self.r_mapa.right - 4:
            rr.right = p[0] - 16
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
        x = x0_barra = r.x + int(10 * k)
        y = r.y + int(10 * k)
        h = int(26 * k)
        fondo = pygame.Rect(x - 6, y - 6, int(450 * k), h + 12)
        pygame.draw.rect(s, (14, 16, 20), fondo, border_radius=8)
        pygame.draw.rect(s, BORDE, fondo, 1, border_radius=8)
        self.btn_pausa.texto = "Seguir" if self.pausa else "Pausa"
        self.btn_pausa.rect = pygame.Rect(x, y, int(58 * k), h)
        mouse = pygame.mouse.get_pos()
        self.btn_pausa.dibujar(s, self.f_semi, mouse, self.pausa)
        x += int(64 * k)
        for b, v in zip(self.btn_vel, VELOCIDADES):
            b.rect = pygame.Rect(x, y, int(40 * k), h)
            b.dibujar(s, self.f_semi, mouse, v == self.velocidad and not self.pausa)
            x += int(44 * k)
        ep = self.ep
        img = self.f_valor.render(mmss(ep.t), True, TEXTO)
        s.blit(img, (x + int(8 * k), y + (h - img.get_height()) // 2))
        x += img.get_width() + int(16 * k)
        if ep.calma and not self.pausa:
            img = self.f_mini.render("AVANCE RÁPIDO", True, ACENTO)
            s.blit(img, (x, y + (h - img.get_height()) // 2))
        self._boton_grabar(r, y, h, mouse)
        y = self._barra_capas(x0_barra, y + h + int(12 * k), h, mouse)
        pie = f"Arrastra una batería para trasladarla · clic: coordenadas · arrastrar: mover mapa · rueda: zoom · V: verdad del terreno {'ON' if self.verdad else 'OFF'}"
        img = self.f_mini.render(pie, True, (200, 205, 215))
        caja = img.get_rect(bottomright=(r.right - 8, r.bottom - 22 * k))
        pygame.draw.rect(s, (14, 16, 20), caja.inflate(12, 6), border_radius=5)
        s.blit(img, caja)
        mx, my = pygame.mouse.get_pos()
        if r.collidepoint(mx, my):
            wx, wy = self.a_mundo(mx, my)
            txt = f"X {wx / 1000:5.1f} km   Y {wy / 1000:5.1f} km"
            if self._real() and self.geo is not None:
                lat, lon = self.geo.a_latlon(wx, wy)
                txt += f"   ·   {lat:.5f}, {lon:.5f}"
            img = self.f_semi.render(txt, True, TEXTO)
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
            caja = img.get_rect(midtop=(r.centerx, self._y_aviso))
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

    def _barra_capas(self, x, y, h, mouse):
        s, k, r = self.pantalla, self.k, self.r_mapa
        real = self._real()
        g = int(6 * k)
        bw = int(98 * k)
        ancho = 2 * bw + g + ((3 * (bw + g) + int(10 * k)) if real else 0)
        caja = pygame.Rect(x - 6, y - 6, ancho + 12, h + 12)
        pygame.draw.rect(s, (14, 16, 20), caja, border_radius=8)
        pygame.draw.rect(s, BORDE, caja, 1, border_radius=8)
        for i, (b, v) in enumerate(zip(self.btn_mapa, (False, True))):
            b.rect = pygame.Rect(x + i * (bw + g), y, bw, h)
            b.dibujar(s, self.f_chica, mouse, v == real)
        if real:
            xv = x + 2 * (bw + g) + int(10 * k)
            pygame.draw.line(s, BORDE, (xv - int(8 * k), y + 3), (xv - int(8 * k), y + h - 3))
            for i, (b, v) in enumerate(zip(self.btn_vista, G.VISTAS)):
                b.rect = pygame.Rect(xv + i * (bw + g), y, bw, h)
                b.dibujar(s, self.f_chica, mouse, v == self.vista)
        y += h + int(12 * k)
        if True:
            cmd = self.modo == "comandante"
            self.btn_lugar[1].texto = "Batería aquí" if cmd else "+ Agregar"
            cw = int(290 * k)
            anchos = (int(108 * k), int(84 * k), int(66 * k))
            caja = pygame.Rect(x - 6, y - 6, cw + sum(anchos) + 3 * g + 12, h + 12)
            pygame.draw.rect(s, (14, 16, 20), caja, border_radius=8)
            pygame.draw.rect(s, BORDE, caja, 1, border_radius=8)
            self.campo_lugar.rect = pygame.Rect(x, y, cw, h)
            self.campo_lugar.dibujar(s, self.f_semi, self.f_chica)
            xb = x + cw + g
            for b, w in zip(self.btn_lugar, anchos):
                b.rect = pygame.Rect(xb, y, w, h)
                b.dibujar(s, self.f_chica, mouse)
                xb += w + g
            y += h + int(12 * k)
            if not real:
                txt = "Escribe una ciudad, «lat, lon» o un enlace de Google Maps y presiona Enter: se abre el mapa real de ese lugar"
            elif cmd:
                areas = [z.nombre for z in self.ep.zonas if z.tipo == "area" and z.activa]
                txt = ("Protegiendo: " + ", ".join(areas)) if areas else \
                    "Enter o «Proteger lugar» lo protege; «Batería aquí» pone una batería en ese punto; clic en el mapa copia lat, lon"
            elif self.lugares:
                txt = "Protegiendo: " + ", ".join(f"{l['nombre']} ({l['r'] / 1000:.1f} km)" for l in self.lugares)
            else:
                txt = "Escribe una ciudad, «lat, lon» o un enlace de Google Maps y presiona Enter: la misión se jugará ahí"
            if self.modo == "entrenar" and self.lugares and real:
                txt += " · la IA entrena en este lugar"
            img = self.f_mini.render(txt[:150], True, ACENTO if txt.startswith("Protegiendo") else TEXTO)
            caja = img.get_rect(topleft=(x, y - int(4 * k)))
            pygame.draw.rect(s, (14, 16, 20), caja.inflate(12, 6), border_radius=5)
            s.blit(img, caja)
            y += img.get_height() + int(8 * k)
        if real and self.ocupado_geo:
            img = self.f_chica.render(self.ocupado_geo, True, ACENTO)
            caja = img.get_rect(topleft=(x, y - int(2 * k)))
            pygame.draw.rect(s, (14, 16, 20), caja.inflate(14, 8), border_radius=6)
            s.blit(img, caja)
            y += img.get_height() + int(10 * k)
        self._y_aviso = y + int(4 * k)
        if real and self.geo is not None:
            if self._fondo_real() is None and not self._faltan_teselas:
                img = self.f_semi.render("Descargando el mapa real…", True, TEXTO)
                s.blit(img, img.get_rect(center=r.center))
            yb = r.bottom - int(44 * k)
            img = self.f_mini.render(G.ATRIBUCIONES[self.vista], True, (200, 205, 215))
            caja = img.get_rect(bottomleft=(r.x + int(24 * k), yb))
            pygame.draw.rect(s, (14, 16, 20), caja.inflate(10, 4), border_radius=4)
            s.blit(img, caja)
            yb = caja.top - int(8 * k)
            for largo in (20, 50, 100, 200, 500, 1000, 2000, 5000, 10000, 20000):
                if largo * self.esc >= 70 * k:
                    break
            lx = largo * self.esc
            x0 = r.x + int(24 * k)
            pygame.draw.rect(s, (14, 16, 20), (x0 - 6, yb - int(18 * k), lx + 12 + int(60 * k), int(22 * k)), border_radius=4)
            pygame.draw.line(s, TEXTO, (x0, yb), (x0 + lx, yb), 2)
            for xx in (x0, x0 + lx):
                pygame.draw.line(s, TEXTO, (xx, yb - int(6 * k)), (xx, yb), 2)
            et = f"{largo / 1000:g} km" if largo >= 1000 else f"{largo} m"
            img = self.f_mini.render(et, True, TEXTO)
            s.blit(img, (x0 + lx + int(8 * k), yb - img.get_height() + 2))
            if self._faltan_teselas:
                img = self.f_mini.render(f"Cargando detalle del mapa… {self._faltan_teselas} teselas", True, ACENTO)
                s.blit(img, (x0, yb - int(20 * k) - img.get_height()))
        return y

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
        for t, txt, c in (self.ep.bitacora or [])[-n:]:
            s.blit(self.f_mini.render(mmss(t), True, SUTIL), (r.x + 12 * self.k, y + 2))
            img = self.f_chica.render(txt, True, COLOR_LOG.get(c, TEXTO))
            s.blit(img, (r.x + 58 * self.k, y))
            y += lh

    def _dibujar_perfil(self):
        r = self.r_perfil
        ep = self.ep
        vivas = [b for b in ep.baterias if not b.destruida] or ep.baterias[:1]
        todas = self.perfil_todas and len(vivas) > 1
        titulo = "Perfil vertical · " + ("todas las baterías (la más cercana)" if todas else f"distancia a {self._bat().nombre}")
        y0 = self._tarjeta(r, titulo)
        s = self.pantalla
        k = self.k
        mouse = pygame.mouse.get_pos()
        bw = [int(52 * k), int(92 * k)]
        x = r.right - int(10 * k) - sum(bw) - int(4 * k)
        for b, w, sel in zip(self.btn_perfil, bw, (self.perfil_todas, not self.perfil_todas)):
            b.rect = pygame.Rect(x, r.y + int(5 * k), w, int(20 * k))
            b.dibujar(s, self.f_mini, mouse, sel)
            x += w + int(4 * k)
        g = pygame.Rect(r.x + int(40 * k), y0 + 4, r.w - int(52 * k), r.bottom - y0 - int(26 * k))
        dmax, zmax = 50000.0, 12000.0
        for km in range(0, 51, 10):
            xx = g.x + g.w * km * 1000 / dmax
            pygame.draw.line(s, REJILLA, (xx, g.y), (xx, g.bottom))
            s.blit(self.f_mini.render(f"{km}", True, SUTIL), (xx - 4, g.bottom + 3))
        for zk in range(0, 13, 4):
            yy = g.bottom - g.h * zk * 1000 / zmax
            pygame.draw.line(s, REJILLA, (g.x, yy), (g.right, yy))
            s.blit(self.f_mini.render(f"{zk} km", True, SUTIL), (r.x + 6 * k, yy - 7))
        xa = g.x + g.w * C.INT_ALCANCE / dmax
        yt = g.bottom - g.h * C.INT_TECHO / zmax
        env = pygame.Surface(g.size, pygame.SRCALPHA)
        pygame.draw.rect(env, (61, 214, 245, 22), (0, yt - g.y, xa - g.x, g.bottom - yt))
        s.blit(env, g.topleft)
        pygame.draw.rect(s, (61, 214, 245), (g.x, yt, xa - g.x, g.bottom - yt), 1)
        tonos = [CIAN, ACENTO, MORADO, VERDE, (255, 120, 200), NARANJA]
        color_bat = {id(b): tonos[i % len(tonos)] for i, b in enumerate(ep.baterias)}
        sel = self._bat()

        def cercana(x, y):
            return min(vivas, key=lambda b: (x - b.x) ** 2 + (y - b.y) ** 2)

        def pp(x, y, z, b):
            d = math.hypot(x - b.x, y - b.y)
            return g.x + g.w * min(d, dmax) / dmax, g.bottom - g.h * min(z, zmax) / zmax

        detectadas = [am for am in ep.activas if am.detectada]
        etiquetas = todas and len(detectadas) <= 14
        for am in detectadas:
            col = COLOR_TIPO[am.tipo]
            ax, ay, az = am.pos(ep.t)
            b = cercana(ax, ay) if todas else sel
            pts = [pp(q[0], q[1], q[2], b) for q in am.rastro] + [pp(ax, ay, az, b)]
            if len(pts) > 1:
                pygame.draw.lines(s, mezclar(col, FONDO, 0.4), False, pts, 1)
            if todas:
                pygame.draw.circle(s, color_bat[id(b)], pts[-1], 5 * k, max(1, int(1.5 * k)))
            pygame.draw.circle(s, col, pts[-1], 3 * k)
            if etiquetas and g.collidepoint(pts[-1]):
                s.blit(self.f_mini.render(b.nombre, True, color_bat[id(b)]), (pts[-1][0] + 6 * k, pts[-1][1] - 14 * k))
        for it in ep.interceptores:
            if ep.t < it.t_lanz:
                continue
            b = getattr(it, "bateria", None) if todas else sel
            if b is None:
                b = cercana(it.x, it.y)
            col = color_bat.get(id(b), CIAN) if todas else (61, 214, 245)
            pts = [pp(q[0], q[1], q[2], b) for q in it.rastro] + [pp(it.x, it.y, it.z, b)]
            if len(pts) > 1:
                pygame.draw.lines(s, col, False, pts, 1)
            pygame.draw.circle(s, (220, 250, 255), pts[-1], 2.5 * k)
        if todas:
            xx = g.right - int(6 * k)
            for b in reversed(ep.baterias):
                img = self.f_mini.render(b.nombre, True, color_bat[id(b)] if not b.destruida else SUTIL)
                xx -= img.get_width()
                s.blit(img, (xx, g.y + int(3 * k)))
                pygame.draw.circle(s, color_bat[id(b)] if not b.destruida else SUTIL, (xx - 7 * k, g.y + 10 * k), 4 * k)
                xx -= int(18 * k)

    def _panel(self):
        s = self.pantalla
        k = self.k
        r = self.r_panel
        mouse = pygame.mouse.get_pos()
        ep = self.ep
        x = r.x
        y = r.y
        img = self.f_titulo.render("Domo de Defensa Móvil", True, TEXTO)
        s.blit(img, (x, y))
        y += img.get_height()
        s.blit(self.f_chica.render("Batería antiaérea simulada · control de tiro con IA", True, TENUE), (x, y))
        y += int(24 * k)
        bw = (r.w - 3 * int(6 * k)) // 4
        for i, (b, (m, _)) in enumerate(zip(self.btn_modos, MODOS)):
            b.rect = pygame.Rect(x + i * (bw + int(6 * k)), y, bw, int(30 * k))
            b.dibujar(s, self.f_semi, mouse, m == self.modo)
        y += int(40 * k)

        h = int(96 * k)
        tr = pygame.Rect(x, y, r.w, h)
        yy = self._tarjeta(tr, "Escenario")
        nombre = ep.m["nombre"]
        if self.modo in ("campeon", "jugar", "entrenar") and not ep.continuo:
            nombre = f"{self.mision_n}. {nombre}"
        s.blit(self.f_semi.render(nombre, True, TEXTO), (x + 12 * k, yy))
        if self.modo in ("campeon", "jugar"):
            for i, b in enumerate(self.btn_mis):
                b.rect = pygame.Rect(tr.right - int((70 - 34 * i) * k), tr.y + 6 * k, int(30 * k), int(24 * k))
                b.dibujar(s, self.f_semi, mouse)
        desc = ep.m["descripcion"]
        lineas = self._envolver(desc, self.f_chica, tr.w - 24 * k)[:2]
        for i, l in enumerate(lineas):
            s.blit(self.f_chica.render(l, True, TENUE), (x + 12 * k, yy + int((20 + 15 * i) * k)))
        s.blit(self.f_mini.render(self.ep_info, True, ACENTO), (x + 12 * k, tr.bottom - 18 * k))
        y = tr.bottom + int(8 * k)

        bat = self._bat()
        n_l = len(bat.misiles)
        por_fila = min(n_l, 4)
        filas = (n_l + por_fila - 1) // por_fila
        h = int((110 + 28 * filas) * k)
        tr = pygame.Rect(x, y, r.w, h)
        total = sum(sum(b.misiles) for b in ep.vivas())
        yy = self._tarjeta(tr, f"Baterías · {len(ep.vivas())}/{len(ep.baterias)} activas · {total} misiles")
        self._tabs = []
        tx = x + 12 * k
        for i, b in enumerate(ep.baterias):
            col_t = ESTADOS[b.estado][1]
            rr = pygame.Rect(tx, yy, int(46 * k), int(22 * k))
            elegido = b is bat
            pygame.draw.rect(s, mezclar(col_t, FONDO, 0.15) if elegido else TARJETA2, rr, border_radius=5)
            pygame.draw.rect(s, col_t, rr, 1, border_radius=5)
            img = self.f_mini.render(b.nombre, True, FONDO if elegido else TEXTO)
            s.blit(img, img.get_rect(center=rr.center))
            self._tabs.append((rr, i))
            tx += int(52 * k)
        yy += int(30 * k)
        yy -= int(0 * k)
        etq, col = ESTADOS[bat.estado]
        chip = self.f_mini.render(etq, True, FONDO)
        cr = chip.get_rect(topright=(tr.right - 12 * k, tr.y + 7 * k)).inflate(14, 6)
        pygame.draw.rect(s, col, cr, border_radius=cr.h // 2)
        s.blit(chip, chip.get_rect(center=cr.center))
        info = f"Posición {self._texto_pos(bat.x, bat.y)}"
        if bat.destino is not None:
            info += f" → {self._texto_pos(*bat.destino)} · listo en {mmss(bat.eta())}"
        s.blit(self.f_chica.render(info, True, TEXTO), (x + 12 * k, yy))
        lw = (tr.w - 24 * k - (por_fila - 1) * 8 * k) / por_fila
        for i in range(n_l):
            lx = x + 12 * k + (i % por_fila) * (lw + 8 * k)
            ly = yy + 24 * k + (i // por_fila) * int(28 * k)
            frac = bat.misiles[i] / C.MISILES_POR_LANZADOR
            s.blit(self.f_mini.render(f"L{i + 1}" if por_fila == 4 else f"Lanzador {i + 1}", True, TENUE), (lx, ly))
            txt = f"{bat.misiles[i]}" if bat.recarga_t[i] <= 0 else f"recarga {bat.recarga_t[i]:.0f}s"
            if por_fila == 4 and bat.recarga_t[i] > 0:
                txt = f"↻{bat.recarga_t[i]:.0f}s"
            img = self.f_mini.render(txt, True, TEXTO)
            s.blit(img, (lx + lw - img.get_width(), ly))
            pygame.draw.rect(s, REJILLA, (lx, ly + 17 * k, lw, 6 * k), border_radius=3)
            pygame.draw.rect(s, CIAN if frac > 0.25 else NARANJA, (lx, ly + 17 * k, lw * frac, 6 * k), border_radius=3)
        s.blit(self.f_mini.render(f"Recargas disponibles: {bat.recargas if bat.recargas < 90 else '∞'} · radar {'activo' if bat.operativa else 'apagado'} · alcance {C.INT_ALCANCE / 1000:.0f} km",
                                  True, SUTIL), (x + 12 * k, tr.bottom - 18 * k))
        y = tr.bottom + int(8 * k)

        h = int(118 * k)
        tr = pygame.Rect(x, y, r.w, h)
        yy = self._tarjeta(tr, "Combate")
        st = ep.st
        datos = [("Detectadas", f"{st['detectadas']}", AZUL), ("Interceptadas", f"{st['interceptadas']}", VERDE),
                 ("Impactos en zonas", f"{st['impactos_zona']}", ROJO if st['impactos_zona'] else TEXTO),
                 ("Ignoradas (campo)", f"{st['ignoradas_bien']}", TENUE),
                 ("Interceptores", f"{st['usados']}", CIAN), ("Desperdicio", f"{100 * ep.desperdicio():.0f}%",
                                                              NARANJA if ep.desperdicio() > C.DESPERDICIO_MAX else TEXTO),
                 ("Protección", f"{100 * ep.proteccion():.0f}%", VERDE if ep.proteccion() >= C.PROTECCION_MIN else ROJO),
                 ("Fallos", f"{st['fallos']}", TEXTO)]
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
            self._panel_despliegue(resto, mouse, jugar=True)
        else:
            self._panel_despliegue(resto, mouse, jugar=False)

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
        orden = np.argsort(-Y[:, 0])[:5]
        bw = int(110 * k)
        for i in orden:
            am, sol = cands[i]
            if y > tr.bottom - 22 * k:
                break
            ix, iy = am.impacto_est()
            z = self.ep.zona_en(ix, iy)
            dest = z.nombre if z else ("batería" if self.ep.valor_en(ix, iy) else "campo")
            if dest == "campo" and self.ep.sobrevuelo(am):
                dest = "sobrevuelo " + self.ep.sobrevuelo(am).replace("la batería ", "")
            txt = f"#{am.id} {C.TIPOS[am.tipo]['nombre'].split()[-1]} → {dest}"
            s.blit(self.f_chica.render(txt[:30], True, COLOR_TIPO[am.tipo] if am.viva else SUTIL), (tr.x + 12 * k, y))
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
        tonos = [AZUL, MORADO, CIAN, NARANJA, VERDE, (255, 120, 200), ACENTO, ROJO]
        ini = 0
        for i in range(1, n + 1):
            if i == n or hist[i]["mision"] != hist[ini]["mision"]:
                x0 = g.x + g.w * ini / (n - 1)
                x1 = g.x + g.w * (i - 1) / (n - 1)
                col = tonos[(hist[ini]["mision"] - 1) % len(tonos)]
                banda = pygame.Surface((max(1, int(x1 - x0) + 1), g.h), pygame.SRCALPHA)
                banda.fill((*col, 28))
                s.blit(banda, (x0, g.y))
                img = self.f_mini.render(str(hist[ini]["mision"]), True, col)
                if x1 - x0 > 12:
                    s.blit(img, (x0 + 3, g.y + 2))
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
        ent = self.ent
        hilo = self.hilo
        mis = ent.mision_actual
        filas = [("Generación", f"{ent.generacion}"), ("Misión", f"{mis}. {MS.NOMBRES[mis - 1]}" if not ent.completada else "Currículo completo (repaso)"),
                 ("Estado", hilo.estado), ("Velocidad", f"{hilo.gens_por_min:.1f} gen/min · σ {ent.sigma:.4f}")]
        lug = ent.cfg.get("lugares")
        filas.append(("Mapa", (f"real · {lug[0]['nombre']}" + (f" +{len(lug) - 1}" if len(lug) > 1 else "")) if lug else "ficticio"))
        for et, v in filas:
            s.blit(self.f_chica.render(et, True, TENUE), (tr.x + 12 * k, y))
            img = self.f_semi.render(v, True, TEXTO)
            s.blit(img, (tr.right - 12 * k - img.get_width(), y))
            y += int(19 * k)
        y += int(4 * k)
        mitad = (tr.w - 24 * k) / 2
        for j, (clave, etq) in enumerate((("baterias", "Baterías"), ("lanzadores", "Lanzadores c/u"))):
            bx = tr.x + 12 * k + j * mitad
            s.blit(self.f_mini.render(etq.upper(), True, TENUE), (bx, y + 6 * k))
            v = int(ent.cfg.get(clave, 0))
            xb = bx + mitad - 112 * k
            self.btn_cfg[2 * j].rect = pygame.Rect(xb, y, int(26 * k), int(24 * k))
            self.btn_cfg[2 * j].dibujar(s, self.f_semi, mouse)
            img = self.f_semi.render(str(v) if v else "misión", True, TEXTO if v else ACENTO)
            s.blit(img, img.get_rect(center=(xb + 52 * k, y + 12 * k)))
            self.btn_cfg[2 * j + 1].rect = pygame.Rect(xb + 78 * k, y, int(26 * k), int(24 * k))
            self.btn_cfg[2 * j + 1].dibujar(s, self.f_semi, mouse)
        y += int(32 * k)
        g = pygame.Rect(tr.x + 12 * k, y, tr.w - 24 * k, int(96 * k))
        self._grafica(g)
        y = g.bottom + int(4 * k)
        ley = [("mejor protección", VERDE), ("promedio", (120, 130, 150)), ("% que superan", ACENTO)]
        xx = tr.x + 12 * k
        for t, c in ley:
            pygame.draw.rect(s, c, (xx, y + 6 * k, 10 * k, 3 * k))
            img = self.f_mini.render(t, True, TENUE)
            s.blit(img, (xx + 14 * k, y))
            xx += img.get_width() + 30 * k
        y += int(20 * k)
        bw = (tr.w - 24 * k - 2 * 6 * k) / 3
        self.btn_ent[0].texto = "Reanudar" if hilo.pausado else "Pausar"
        for i, b in enumerate(self.btn_ent):
            b.rect = pygame.Rect(tr.x + 12 * k + i * (bw + 6 * k), y, bw, int(28 * k))
            b.dibujar(s, self.f_chica, mouse)
        y += int(34 * k)
        self.btn_rapido.rect = pygame.Rect(tr.x + 12 * k, y, tr.w - 24 * k, int(28 * k))
        self.btn_rapido.dibujar(s, self.f_chica, mouse)
        y += int(36 * k)
        if y < tr.bottom - 60 * k:
            self._pensamiento(tr, y)

    def _panel_ia(self, tr, mouse):
        s = self.pantalla
        k = self.k
        y = self._tarjeta(tr, "Inteligencia artificial")
        txt = [f"Pesos: {self.ep_info}", f"Entrenamiento: generación {self.ent.generacion}, misión {self.ent.mision_actual}"]
        for t in txt:
            s.blit(self.f_chica.render(t, True, TEXTO), (tr.x + 12 * k, y))
            y += int(19 * k)
        self.btn_reiniciar.rect = pygame.Rect(tr.x + 12 * k, y + 4 * k, int(170 * k), int(28 * k))
        self.btn_reiniciar.dibujar(s, self.f_chica, mouse)
        y += int(44 * k)
        self._pensamiento(tr, y)

    def _panel_despliegue(self, tr, mouse, jugar):
        s = self.pantalla
        k = self.k
        y = self._tarjeta(tr, "Despliegue por coordenadas")
        x0 = tr.x + 12 * k
        ancho = tr.w - 24 * k
        cw = (ancho - 6 * k) / 2
        bw = cw
        if self._real():
            s.blit(self.f_mini.render("El lugar se escribe en «Lugar», arriba del mapa", True, ACENTO), (x0, y))
            y += int(20 * k)
            for i, c in enumerate(self.campos[2:]):
                c.rect = pygame.Rect(x0 + i * (cw + 6 * k), y, cw, int(28 * k))
                c.dibujar(s, self.f_semi, self.f_chica)
            y += int(38 * k)
            self.btn_desp[0].texto = "Buscar y proteger"
            self.btn_desp[1].texto = "Mover batería al lugar"
        else:
            for i, c in enumerate(self.campos):
                c.rect = pygame.Rect(x0 + (i % 2) * (cw + 6 * k), y + (i // 2) * int(34 * k), cw, int(28 * k))
                c.dibujar(s, self.f_semi, self.f_chica)
            y += int(72 * k)
            self.btn_desp[0].texto = "Proteger área"
            self.btn_desp[1].texto = "Mover batería aquí"
        for i, b in enumerate(self.btn_desp):
            b.rect = pygame.Rect(tr.x + 12 * k + (i % 2) * (bw + 6 * k), y + (i // 2) * int(34 * k), bw, int(28 * k))
            b.dibujar(s, self.f_chica, mouse)
        y += int(70 * k)
        s.blit(self.f_mini.render(f"LANZADORES {self._bat().nombre}", True, TENUE), (x0, y + 6 * k))
        lx = x0 + 90 * k
        self.btn_lanz[0].rect = pygame.Rect(lx, y, int(28 * k), int(26 * k))
        self.btn_lanz[0].dibujar(s, self.f_semi, mouse)
        img = self.f_valor.render(str(len(self._bat().misiles)), True, TEXTO)
        s.blit(img, img.get_rect(center=(lx + 46 * k, y + 13 * k)))
        self.btn_lanz[1].rect = pygame.Rect(lx + 64 * k, y, int(28 * k), int(26 * k))
        self.btn_lanz[1].dibujar(s, self.f_semi, mouse)
        s.blit(self.f_mini.render(f"{self._bat().nombre} · {len(self._bat().misiles) * C.MISILES_POR_LANZADOR} misiles", True, TENUE),
               (lx + 102 * k, y + 5 * k))
        if not jugar:
            self.btn_google.rect = pygame.Rect(tr.right - 12 * k - int(140 * k), y, int(140 * k), int(26 * k))
            self.btn_google.dibujar(s, self.f_chica, mouse)
        y += int(34 * k)
        s.blit(self.f_mini.render("BATERÍAS", True, TENUE), (x0, y + 6 * k))
        bw2 = (ancho - 100 * k - 12 * k) / 3
        for i, b in enumerate(self.btn_bats):
            b.rect = pygame.Rect(x0 + 100 * k + i * (bw2 + 6 * k), y, bw2, int(26 * k))
            b.dibujar(s, self.f_chica, mouse)
        y += int(34 * k)
        if not jugar:
            s.blit(self.f_mini.render("AMENAZA DESDE", True, TENUE), (x0, y + 6 * k))
            fw = (ancho - 100 * k - 18 * k) / 4
            for i, (b, f) in enumerate(zip(self.btn_frentes, ("norte", "este", "sur", "oeste"))):
                b.rect = pygame.Rect(x0 + 100 * k + i * (fw + 6 * k), y, fw, int(26 * k))
                b.dibujar(s, self.f_chica, mouse, f in self.ep.frentes)
            y += int(34 * k)
        if jugar:
            s.blit(self.f_mini.render("ÁREAS A PROTEGER", True, TENUE), (x0, y + 6 * k))
            aw = (ancho - 100 * k - 6 * k) / 2
            for i, (b, auto) in enumerate(zip(self.btn_areas, (True, False))):
                b.rect = pygame.Rect(x0 + 100 * k + i * (aw + 6 * k), y, aw, int(26 * k))
                b.activo = self.preparando and not self.ep.m.get("lugar")
                b.dibujar(s, self.f_chica, mouse, auto == self.areas_auto and not self.ep.m.get("lugar"))
            y += int(34 * k)
            self.btn_apoyo.texto = f"Apoyo automático: {'SÍ' if self.apoyo else 'NO'}"
            self.btn_apoyo.rect = pygame.Rect(tr.x + 12 * k, y, bw, int(28 * k))
            self.btn_apoyo.dibujar(s, self.f_chica, mouse, self.apoyo)
            self.btn_reiniciar.rect = pygame.Rect(tr.x + 18 * k + bw, y, bw, int(28 * k))
            self.btn_reiniciar.dibujar(s, self.f_chica, mouse)
            y += int(38 * k)
            ayuda = (("Mapa real: escribe una ciudad o coordenadas en «Lugar» (arriba del mapa) y presiona Enter para jugar la "
                      "misión defendiendo ese lugar; «Quitar áreas» vuelve a las de la misión. " if self._real() else "") +
                     ("Fase de despliegue: el reloj está detenido. «Automáticas» usa las áreas de la misión; "
                      "«Las elijo yo» te deja marcar los poblados con clic o agregar áreas con X/Y. Arrastra cada "
                      "batería para cubrirlas (verde = cubierta, naranja = parcial, rojo = sin cobertura) y presiona "
                      "«Comenzar ataque». ")
                     if self.preparando else "") + ("Clic sobre una amenaza para dispararle un interceptor; "
                                                    "Shift+clic o clic derecho para dos. "
                     "Arrastra una batería para trasladarla. "
                     "Lo que decidas se usa para enseñar a la IA al terminar el escenario. "
                     "Las X rojas son impactos previstos en zonas protegidas; las grises caen en campo abierto.")
        else:
            s.blit(self.f_mini.render("CONTROL DE TIRO", True, TENUE), (tr.x + 12 * k, y))
            y += int(16 * k)
            bw3 = (tr.w - 24 * k - 12 * k) / 3
            for i, (b, c) in enumerate(zip(self.btn_ctrl, ("ia", "doctrina", "manual"))):
                b.rect = pygame.Rect(tr.x + 12 * k + i * (bw3 + 6 * k), y, bw3, int(28 * k))
                b.dibujar(s, self.f_chica, mouse, c == self.control_cmd)
            y += int(38 * k)
            if self._real():
                ayuda = ("Arrastra una batería para trasladarla. En «Lugar» (arriba del mapa) escribe una ciudad («Pachuca, Hidalgo»), coordenadas («20.1165, -98.7413») o pega un enlace "
                         "de Google Maps. Enter protege el lugar; «Batería aquí» pone una batería en ese punto (clic en "
                         "el mapa copia la latitud y longitud). Si queda fuera, el mapa se recentra conservando lo que "
                         "tienes, o se descarga uno nuevo. " + G.atribucion(self.vista))
            else:
                ayuda = ("Para usar una ciudad real escribe en «Lugar», arriba del mapa. "
                         "Arrastra una batería en el mapa para trasladarla. Escribe X/Y en km (o haz clic en el mapa) y "
                         "el radio; «Proteger área» la agrega y acomoda las baterías. Clic en un pueblo para protegerlo "
                         "o dejarlo. Una batería no dispara mientras se pliega, viaja o despliega.")
            if self.ocupado_geo:
                ayuda = self.ocupado_geo + " " + ayuda
        for l in self._envolver(ayuda, self.f_chica, tr.w - 24 * k):
            if y > tr.bottom - 18 * k:
                break
            s.blit(self.f_chica.render(l, True, TENUE), (tr.x + 12 * k, y))
            y += int(16 * k)

    def dibujar(self):
        self._actualizar_cursor()
        self.pantalla.fill(FONDO)
        self._dibujar_mapa()
        self._dibujar_log()
        self._dibujar_perfil()
        self._panel()
        if self.preparando:
            self._banner_preparacion()

    def _banner_preparacion(self):
        s, k, r = self.pantalla, self.k, self.r_mapa
        mouse = pygame.mouse.get_pos()
        cz = self._coberturas()
        cub = sum(1 for _, c in cz if c >= 0.9)
        pct = 100 * self._cobertura_valor()
        col = VERDE if cub == len(cz) else (NARANJA if pct >= 50 else ROJO)
        caja = pygame.Rect(0, 0, int(min(r.w - 30 * k, 720 * k)), int(78 * k))
        caja.midbottom = (r.centerx, r.bottom - int(46 * k))
        pygame.draw.rect(s, (14, 16, 20), caja, border_radius=10)
        pygame.draw.rect(s, ACENTO, caja, 2, border_radius=10)
        bw = int(200 * k)
        self.btn_comenzar.rect = pygame.Rect(caja.right - bw - int(12 * k), caja.y + int(12 * k), bw, caja.h - int(32 * k))
        self.btn_comenzar.dibujar(s, self.f_semi, mouse)
        img = self.f_mini.render("o tecla ESPACIO", True, SUTIL)
        s.blit(img, img.get_rect(midtop=(self.btn_comenzar.rect.centerx, self.btn_comenzar.rect.bottom + 2)))
        ancho = self.btn_comenzar.rect.x - caja.x - int(26 * k)
        frentes = ", ".join(M.NOMBRES_FRENTES[f] for f in self.ep.frentes if f in M.NOMBRES_FRENTES)
        guia = ("Clic en un poblado para protegerlo o dejarlo; luego arrastra tus baterías." if not self.areas_auto
                else "Arrastra tus baterías: se colocan al instante. El anillo verde es su alcance útil.")
        if cz:
            resumen = (f"Cobertura {pct:.0f}% del valor · {cub}/{len(cz)} áreas cubiertas"
                       + (f" · amenazas desde {frentes}" if frentes else ""))
        else:
            resumen, col = "Todavía no eliges ningún área a proteger", ROJO
        lineas = [(self.f_semi, "FASE DE DESPLIEGUE · el enemigo todavía no ataca", ACENTO),
                  (self.f_chica, guia, TENUE), (self.f_semi, resumen, col)]
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
        gen_vista = None
        while sigue:
            ahora = time.perf_counter()
            dt = min(ahora - t_prev, 0.1)
            t_prev = ahora
            sigue = self._eventos() and self.salida is None
            self._procesar_geo()
            self._avanzar(dt)
            if self.modo == "entrenar" and self.hilo.instantanea is not None:
                g = self.hilo.instantanea[3]
                if gen_vista is None:
                    gen_vista = g
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
