import datetime
import math
import os
import threading
import tkinter as tk
import webbrowser
from tkinter import simpledialog

from PIL import Image, ImageDraw, ImageEnhance, ImageTk

import config as C
import estilo as E
import geo
from ambiente import PUNTOS_CARDINALES, cardinal, vector_rumbo
from ciudad import Ciudad
from estilo import P
from grabador import BotonGrabar
from navegacion import TRAMOS, Planificador
from simulacion import Mision

CARPETA_VUELOS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "vuelos")

COLOR = {
    "fondo": P["fondo"], "panel": P["tarjeta"], "texto": P["texto"], "tenue": P["tenue"],
    "acento": P["acento"], "alerta": P["naranja"], "peligro": P["rojo"], "exito": P["verde"],
    "info": P["cian"], "decision": P["acento"], "prohibida": "#ff5252", "cable": "#ffd23f",
    "antena": "#ff5252", "ave": "#e6ddd6", "dron": "#3dd6f5", "dron_emergencia": P["naranja"],
    "estela": "#7fe9ff", "real": P["cian"],
}
OTRA_ZONA = "Otra zona (coordenadas)…"
ICONO = {"farmacia": ("+", "#2fbf71"), "restaurante": ("R", "#ff8c2e"),
         "casa": ("C", "#4ea4ff"), "edificio": ("E", "#b48cff"), "punto": ("•", "#26c6b0")}
MODOS_CLIC = (("salida", "Salida"), ("llegada", "Llegada"), ("paso", "Puntos de paso"))
VELOCIDADES = (1, 2, 4, 8, 16, 32)
ALTO_CABECERA = 54
ALTO_PERFIL = 124
ANCHO_LATERAL = 262
ANCHO_PANEL = 372
ANCHO_VISTA, ALTO_VISTA = ANCHO_PANEL - 26, 214
ESC_VISTA = 1.4
DIRECCIONES = {n: i * 45.0 for i, n in enumerate(PUNTOS_CARDINALES)}
OSCURO = "#0e1014"


def color_altura(h):
    for limite, col in ((12, "#3d4757"), (25, "#4b5a70"), (45, "#5d6f8a"),
                        (70, "#7286a4"), (100, "#8ea2c0")):
        if h < limite:
            return col
    return "#b9c8de"


def tiempo(t):
    return f"{int(t // 60):02d}:{int(t % 60):02d}"


def _rgb(col, alfa=255):
    return (*E.rgb(col), alfa)


class Aplicacion:
    def __init__(self, args):
        self.raiz = tk.Tk()
        self.raiz.title("Dron de entregas — simulador de vuelo urbano")
        self.raiz.configure(bg=P["fondo"])
        self.raiz.resizable(False, False)
        self.ciudad = Ciudad(args.zona_obj)
        self.zona = self.ciudad.zona
        self.plan = Planificador(self.ciudad)
        self.satelite = geo.imagen_satelital(self.zona)
        self._descarga = None

        sw, sh = self.raiz.winfo_screenwidth(), self.raiz.winfo_screenheight()
        alto_mapa = max(360, sh - 72 - ALTO_CABECERA - ALTO_PERFIL - 44)
        ancho_mapa = max(480, sw - ANCHO_LATERAL - ANCHO_PANEL - 60)
        self.esc = min(alto_mapa / self.ciudad.alto, ancho_mapa / self.ciudad.ancho)
        self.mw, self.mh = int(self.ciudad.ancho * self.esc), int(self.ciudad.alto * self.esc)

        self.mision = None
        self.ruta = None
        self.puntos = []
        self.pausa = False
        self.vel_idx = 2
        self._acum = 0.0
        self._version_ruta = -1
        self._perfil_ruta = None
        self._cuadro = 0
        self.semilla = args.semilla
        eventos = (args.eventos or "").split(",")

        io = min(max(args.origen, 1), len(self.ciudad.origenes)) - 1
        idd = min(max(args.destino, 1), len(self.ciudad.destinos)) - 1
        self.var_origen = tk.StringVar(value=self.ciudad.origenes[io].nombre)
        self.var_destino = tk.StringVar(value=self.ciudad.destinos[idd].nombre)
        self.var_modo = tk.StringVar(value="manual" if args.puntos else "auto")
        if args.puntos:
            self.puntos = [self.zona.a_metros(*(float(v) for v in p.split(",")))
                           for p in args.puntos.split(";")]
        self.var_viento = tk.DoubleVar(value=args.viento)
        self.var_dir = tk.StringVar(value=cardinal(args.direccion))
        self.var_rafagas = tk.BooleanVar(value=not args.sin_rafagas)
        self.var_aves = tk.BooleanVar(value=not args.sin_aves)
        self.var_ev = {e: tk.BooleanVar(value=e in eventos) for e in ("gps", "motor", "bateria")}
        self.var_alturas = tk.BooleanVar(value=False)
        self.var_sat_vista = tk.BooleanVar(value=True)
        self.bateria = args.bateria / 100
        self.var_zona = tk.StringVar(value=self.zona.nombre)
        self._centros = {self.zona.nombre: self.zona.centro}
        self._zonas = list(C.ZONAS)
        if self.zona.nombre not in self._zonas:
            self._zonas.append(self.zona.nombre)
        self.var_tamano = tk.StringVar(value=self._nombre_tamano(self.zona.tamano))
        self.var_clic = tk.StringVar(value="paso" if args.puntos else "llegada")
        self.var_vehiculo = tk.StringVar(value=args.vehiculo)
        self.var_piloto = tk.StringVar(value=getattr(args, "piloto", "clasico"))
        self.escuela = None

        self._construir()
        self._dibujar_ciudad()
        self._planear()
        self._teclas()
        self.raiz.after(C.FPS_MS, self._ciclo)

    def px(self, x, y):
        return x * self.esc, y * self.esc

    def origen(self):
        return next(o for o in self.ciudad.origenes if o.nombre == self.var_origen.get())

    def destino(self):
        return next(d for d in self.ciudad.destinos if d.nombre == self.var_destino.get())

    @property
    def volando(self):
        return self.mision is not None and not self.mision.terminada

    def _segmentado(self, padre, var, opciones, comando):
        seg = E.Segmentado(padre, opciones, var.get(), lambda v: (var.set(v), comando()))
        for l in seg.etiquetas.values():
            l.configure(padx=9, font=(E.SEMI, 9))
        var.trace_add("write", lambda *a: seg.poner(var.get()))
        return seg

    def _rotulo(self, padre, texto):
        return E.etiqueta(padre, texto.upper(), P["sutil"], (E.SEMI, 7))

    def _construir(self):
        r = self.raiz
        self._cabecera()
        cuerpo = tk.Frame(r, bg=P["fondo"])
        cuerpo.pack(fill="both", padx=10, pady=(0, 10))
        lateral = tk.Frame(cuerpo, bg=P["fondo"], width=ANCHO_LATERAL)
        lateral.pack(side="left", fill="y")
        lateral.pack_propagate(False)
        centro = tk.Frame(cuerpo, bg=P["fondo"])
        centro.pack(side="left", fill="y", padx=8)
        derecha = tk.Frame(cuerpo, bg=P["fondo"], width=ANCHO_PANEL)
        derecha.pack(side="left", fill="y")
        derecha.pack_propagate(False)
        self._lateral(lateral)

        marco = tk.Frame(centro, bg=P["borde"], padx=1, pady=1)
        marco.pack()
        self.mapa = tk.Canvas(marco, width=self.mw, height=self.mh, bg=P["tarjeta"],
                              highlightthickness=0, cursor="crosshair")
        self.mapa.pack()
        self.mapa.bind("<Button-1>", self._clic)
        self.mapa.bind("<Button-3>", self._clic_derecho)
        self.mapa.bind("<Motion>", self._mover_raton)
        self.mapa.bind("<Leave>", lambda e: self.mapa.delete("cursor"))

        tarj, c = E.tarjeta(centro, "Perfil de alturas de la ruta", self._botones_google)
        tarj.pack(fill="x", pady=(8, 0))
        self.perfil = tk.Canvas(c, width=self.mw - 26, height=ALTO_PERFIL - 30, bg=P["tarjeta"],
                                highlightthickness=0)
        self.perfil.pack()
        self._derecha(derecha)

    def _cabecera(self):
        cab = tk.Frame(self.raiz, bg=P["fondo"], height=ALTO_CABECERA)
        cab.pack(fill="x", padx=10)
        cab.pack_propagate(False)
        logo = tk.Canvas(cab, width=40, height=40, bg=P["fondo"], highlightthickness=0)
        logo.pack(side="left", pady=7)
        self._logo(logo)
        titulo = tk.Frame(cab, bg=P["fondo"])
        titulo.pack(side="left", padx=(8, 0))
        tk.Label(titulo, text="DRON DE ENTREGAS", bg=P["fondo"], fg=P["texto"],
                 font=(E.SEMI, 15)).pack(anchor="w")
        self.lbl_sub = tk.Label(titulo, text="", bg=P["fondo"], fg=P["tenue"], font=E.F_CHICA)
        self.lbl_sub.pack(anchor="w")

        estado = tk.Frame(cab, bg=P["tarjeta"], highlightthickness=1,
                          highlightbackground=P["borde"])
        estado.pack(side="left", padx=(28, 0), pady=9, fill="y")
        self.punto_fase = tk.Canvas(estado, width=12, height=12, bg=P["tarjeta"],
                                    highlightthickness=0)
        self.punto_fase.pack(side="left", padx=(12, 0))
        self.lbl_fase = tk.Label(estado, text="", bg=P["tarjeta"], fg=P["acento"],
                                 font=(E.SEMI, 11), width=34, anchor="w")
        self.lbl_fase.pack(side="left", padx=(8, 12))

        der = tk.Frame(cab, bg=P["fondo"])
        der.pack(side="right")
        self.grabar = E.estilo_boton_grabar(
            BotonGrabar(der, self.raiz, self._escribir, E.F_BOTON)).pack(side="right")
        self.btn_despegar = E.Boton(der, "▶  Despegar", self._despegar, P["acento"],
                                    primario=True).pack(side="right", padx=(0, 8))
        self.btn_pausa = E.Boton(der, "Pausa", self._pausar, ancho=8).pack(side="right",
                                                                          padx=(0, 8))
        vel = tk.Frame(der, bg=P["borde"], padx=1, pady=1)
        vel.pack(side="right", padx=(0, 8))
        E.Boton(vel, "−", lambda: self._vel(-1)).pack(side="left")
        self.lbl_vel = tk.Label(vel, text="", bg=P["tarjeta"], fg=P["acento"], font=E.F_BOTON,
                                width=4, pady=6)
        self.lbl_vel.pack(side="left")
        E.Boton(vel, "+", lambda: self._vel(1)).pack(side="left")
        tk.Label(der, text="VELOCIDAD", bg=P["fondo"], fg=P["sutil"],
                 font=(E.SEMI, 7)).pack(side="right", padx=(0, 6))
        E.Boton(der, "🎓  Escuela de vuelo", self._abrir_escuela).pack(side="right",
                                                                       padx=(0, 18))

    @staticmethod
    def _logo(cv):
        cv.create_oval(2, 2, 38, 38, fill=P["tarjeta2"], outline=P["borde"])
        for k in range(6):
            a = math.radians(30 + k * 60)
            x, y = 20 + 11 * math.cos(a), 20 + 11 * math.sin(a)
            cv.create_line(20, 20, x, y, fill=P["tenue"], width=2)
            cv.create_oval(x - 4, y - 4, x + 4, y + 4, outline=P["cian"], width=2)
        cv.create_oval(15, 15, 25, 25, fill=P["acento"], outline="")

    def _tarjeta(self, padre, titulo, pady=(0, 8)):
        t, c = E.tarjeta(padre, titulo)
        t.pack(fill="x", pady=pady)
        return c

    def _lateral(self, lat):
        c = self._tarjeta(lat, "Zona de vuelo")
        self.menu_zona = E.Menu(c, self.var_zona, self._zonas + [OTRA_ZONA],
                                self._cambio_zona, 27).pack(fill="x")
        fila = tk.Frame(c, bg=P["tarjeta"])
        fila.pack(fill="x", pady=(5, 0))
        self._rotulo(fila, "Tamaño de la zona").pack(side="left")
        E.Menu(fila, self.var_tamano, list(C.TAMANOS_ZONA), self._cambio_tamano, 10
               ).pack(side="right")

        c = self._tarjeta(lat, "Vehículo y piloto")
        self._segmentado(c, self.var_vehiculo, (("multirotor", "Hexacóptero"),
                                                ("avion", "Avión VTOL")), self._cambio
                         ).pack(anchor="w")
        self._segmentado(c, self.var_piloto, (("clasico", "Piloto clásico"),
                                              ("ia", "IA aprendida")),
                         self._cambio_piloto).pack(anchor="w", pady=(6, 0))

        c = self._tarjeta(lat, "Misión")
        self._rotulo(c, "Sale de").pack(anchor="w")
        self.menu_origen = E.Menu(c, self.var_origen, [o.nombre for o in self.ciudad.origenes],
                                  self._cambio, 27).pack(fill="x", pady=(1, 5))
        self._rotulo(c, "Entrega en").pack(anchor="w")
        self.menu_destino = E.Menu(c, self.var_destino, [d.nombre for d in self.ciudad.destinos],
                                   self._cambio, 27).pack(fill="x", pady=(1, 6))
        self._rotulo(c, "Ruta").pack(anchor="w")
        self._segmentado(c, self.var_modo, (("auto", "Automática (GPS)"),
                                            ("manual", "Con clics")), self._cambio
                         ).pack(anchor="w", pady=(1, 6))
        self._rotulo(c, "El clic en el mapa elige").pack(anchor="w")
        self._segmentado(c, self.var_clic, MODOS_CLIC, self._cambio_clic).pack(anchor="w",
                                                                               pady=(1, 7))
        fila = tk.Frame(c, bg=P["tarjeta"])
        fila.pack(fill="x")
        E.Interruptor(fila, "Alturas de edificios", self.var_alturas, self._fondo
                      ).pack(side="left")
        b = E.Boton(fila, "Borrar puntos", self._borrar_puntos).pack(side="right")
        b.w.configure(font=(E.SEMI, 9), padx=8, pady=2)

        c = self._tarjeta(lat, "Clima")
        fila = tk.Frame(c, bg=P["tarjeta"])
        fila.pack(fill="x")
        self._rotulo(fila, "Viento").pack(side="left")
        E.Menu(fila, self.var_dir, PUNTOS_CARDINALES, self._viento_vivo, 2).pack(side="right")
        self._rotulo(fila, "del").pack(side="right", padx=4)
        E.Deslizador(fila, self.var_viento, 0, 15, 0.5, self._viento_vivo, 140,
                     unidad=" m/s").pack(side="left", padx=(6, 0))
        fila = tk.Frame(c, bg=P["tarjeta"])
        fila.pack(fill="x", pady=(4, 0))
        E.Interruptor(fila, "Ráfagas", self.var_rafagas, self._viento_vivo).pack(side="left")
        E.Interruptor(fila, "Aves", self.var_aves).pack(side="left", padx=(16, 0))

        c = self._tarjeta(lat, "Fallas al azar en el vuelo", pady=0)
        fila = tk.Frame(c, bg=P["tarjeta"])
        fila.pack(fill="x")
        for k, (e, t) in enumerate((("gps", "GPS"), ("motor", "Motor"), ("bateria", "Batería"))):
            E.Interruptor(fila, t, self.var_ev[e]).pack(side="left", padx=(0 if k == 0 else 9, 0))

    def _botones_google(self, padre):
        f = tk.Frame(padre, bg=P["tarjeta"])
        for txt, cmd in (("Google Maps", self._google_maps), ("Google Earth 3D", self._google_earth)):
            b = E.Boton(f, txt, cmd, E.mezclar(P["verde"], P["tarjeta"], 0.82))
            b.w.configure(fg="#a8f0d4", font=(E.SEMI, 8), padx=8, pady=1)
            b.pack(side="right", padx=(4, 0))
        return f

    def _derecha(self, der):
        t, c = E.tarjeta(der, "Vista cercana", lambda f: E.Interruptor(
            f, "satélite", self.var_sat_vista).marco)
        t.pack(fill="x")
        self.vista = tk.Canvas(c, width=ANCHO_VISTA, height=ALTO_VISTA, bg=P["tarjeta2"],
                               highlightthickness=0)
        self.vista.pack()

        t, c = E.tarjeta(der, "Telemetría")
        t.pack(fill="x", pady=(8, 0))
        self.tele = tk.Canvas(c, width=ANCHO_VISTA, height=172, bg=P["tarjeta"],
                              highlightthickness=0)
        self.tele.pack()

        t, c = E.tarjeta(der, "Provocar en pleno vuelo")
        t.pack(fill="x", pady=(8, 0))
        fila = tk.Frame(c, bg=P["tarjeta"])
        fila.pack(fill="x")
        self.btn_gps = None
        for k, (ev, txt) in enumerate((("gps", "Cortar GPS"), ("motor", "Falla motor"),
                                       ("bateria", "Batería baja"), ("rafaga", "Ráfaga"))):
            b = E.Boton(fila, txt, lambda ev=ev: self._provocar(ev),
                        E.mezclar(P["rojo"], P["tarjeta"], 0.78))
            b.w.configure(fg="#ffb3b3", font=(E.SEMI, 9), padx=0, pady=4)
            b.w.grid(row=0, column=k, sticky="ew", padx=(0 if k == 0 else 4, 0))
            fila.columnconfigure(k, weight=1, uniform="p")
            if ev == "gps":
                self.btn_gps = b

        t, c = E.tarjeta(der, "Bitácora")
        t.pack(fill="both", expand=True, pady=(8, 0))
        marco = tk.Frame(c, bg=P["tarjeta"])
        marco.pack(fill="both", expand=True)
        self.log = tk.Text(marco, width=10, height=4, bg=P["tarjeta"], fg=P["texto"],
                           font=(E.FAMILIA, 9), wrap="word", bd=0, highlightthickness=0,
                           padx=0, pady=0, spacing1=1, spacing3=2, cursor="arrow")
        barra = tk.Scrollbar(marco, command=self.log.yview, width=10, bd=0, relief="flat",
                             troughcolor=P["tarjeta"], bg=P["borde"], activebackground=P["sutil"],
                             elementborderwidth=0)
        self.log.configure(yscrollcommand=barra.set, state="disabled")
        self.log.pack(side="left", fill="both", expand=True)
        barra.pack(side="right", fill="y")
        for nivel in ("info", "aviso", "peligro", "decision", "exito", "tenue"):
            col = {"aviso": "alerta"}.get(nivel, nivel)
            self.log.tag_configure(nivel, foreground=COLOR[col])
        self.log.tag_configure("hora", foreground=P["sutil"], font=("Consolas", 8))
        tk.Label(der, text="Espacio pausa · +/− velocidad · Enter despegar · Esc salir · "
                           "clic derecho borra el último punto", bg=P["fondo"], fg=P["sutil"],
                 font=(E.FAMILIA, 7)).pack(anchor="w", pady=(5, 0))

    def _teclas(self):
        r = self.raiz
        r.bind("<space>", lambda e: self._pausar())
        r.bind("<Return>", lambda e: self._despegar())
        for k in ("<plus>", "<KP_Add>"):
            r.bind(k, lambda e: self._vel(1))
        for k in ("<minus>", "<KP_Subtract>"):
            r.bind(k, lambda e: self._vel(-1))
        r.bind("<Escape>", lambda e: self._salir())
        r.protocol("WM_DELETE_WINDOW", self._salir)

    def _salir(self):
        if self.escuela is not None:
            self.escuela.grabar.cerrar()
        self.grabar.cerrar()
        self.raiz.destroy()

    def _escribir(self, texto, nivel="info", t=None):
        self.log.configure(state="normal")
        if t is not None:
            self.log.insert("end", f"{tiempo(t)}  ", "hora")
        self.log.insert("end", texto + "\n", nivel)
        self.log.see("end")
        self.log.configure(state="disabled")

    def _limpiar_log(self):
        self.log.configure(state="normal")
        self.log.delete("1.0", "end")
        self.log.configure(state="disabled")

    def _cambio(self):
        if self.volando:
            self._escribir("Termina o reinicia la misión antes de cambiar la ruta.", "aviso")
            if self.mision is not None:
                self.var_vehiculo.set(self.mision.dron.tipo)
            return
        self._planear()

    def _info_cerebro(self):
        from escuela import cargar_mejor
        return cargar_mejor(self.var_vehiculo.get())

    def _cambio_piloto(self):
        if self.var_piloto.get() == "ia":
            rec = self._info_cerebro()
            if rec is None:
                self._escribir("Todavía no hay un cerebro entrenado para el "
                               f"{C.VEHICULOS[self.var_vehiculo.get()]['nombre'].lower()}. "
                               "Ábrelo en «Escuela de vuelo» y déjalo aprender.", "aviso")
            else:
                self._escribir(f"Piloto IA: cerebro de la generación {rec['generacion']}, nivel "
                               f"{rec['nivel']} ({rec['leccion']}), aprobó {rec['aprobados']}/"
                               f"{rec['escenarios']} pruebas"
                               + (" · ¡graduado!" if rec.get("graduado") else
                                  " · aún no termina el curso: puede fallar") + ".", "decision")
        else:
            self._escribir("Piloto clásico: reglas programadas a mano.", "tenue")
        self._dibujar_telemetria()

    def _abrir_escuela(self):
        if self.escuela is not None:
            self.escuela.raiz.lift()
            return
        if self.volando:
            self.pausa = True
            self.btn_pausa.texto("Continuar")
        from interfaz_escuela import EscuelaVentana
        top = tk.Toplevel(self.raiz)

        def al_cerrar():
            self.escuela = None
            self._escribir("Escuela cerrada; el mejor cerebro quedó guardado.", "tenue")

        self.escuela = EscuelaVentana(top, self.ciudad, self.plan, self.satelite,
                                      self.var_vehiculo.get(), continuar=True,
                                      al_cerrar=al_cerrar)

    def _cambio_zona(self):
        nombre = self.var_zona.get()
        if self.volando or self._descarga is not None:
            self._escribir("Espera a que termine el vuelo (o la descarga) para cambiar de "
                           "ciudad.", "aviso")
            self.var_zona.set(self.zona.nombre)
            return
        if nombre == OTRA_ZONA:
            texto = simpledialog.askstring(
                "Otra zona", "Escribe la latitud y longitud del centro de la zona\n"
                "(por ejemplo 19.4326, -99.1332) o pega un enlace de Google Maps:",
                parent=self.raiz)
            self.var_zona.set(self.zona.nombre)
            coords = self._leer_coordenadas(texto or "")
            if coords is None:
                if texto:
                    self._escribir("No entendí esas coordenadas.", "aviso")
                return
            nombre = f"Zona {coords[0]:.4f}, {coords[1]:.4f}"
            self._centros[nombre] = coords
        elif nombre == self.zona.nombre:
            return
        elif nombre not in C.ZONAS and nombre not in self._centros:
            return
        self._preparar_zona(geo.Zona(nombre, self._centros.get(nombre), self._tamano()))

    @staticmethod
    def _nombre_tamano(tamano):
        return next((n for n, t in C.TAMANOS_ZONA.items() if t == tamano),
                    next(iter(C.TAMANOS_ZONA)))

    def _tamano(self):
        return C.TAMANOS_ZONA.get(self.var_tamano.get(), 1.0)

    def _cambio_tamano(self):
        if self.volando or self._descarga is not None:
            self._escribir("Espera a que termine el vuelo (o la descarga) para cambiar el "
                           "tamaño de la zona.", "aviso")
            self.var_tamano.set(self._nombre_tamano(self.zona.tamano))
            return
        if self._tamano() == self.zona.tamano:
            return
        self._preparar_zona(geo.Zona(self.zona.nombre, self.zona.centro, self._tamano()))

    @staticmethod
    def _leer_coordenadas(texto):
        return geo.leer_coordenadas(texto)

    def _preparar_zona(self, zona):
        avisos, resultado = [], {}

        def trabajo():
            try:
                ciudad = Ciudad(zona, avisar=avisos.append)
                plan = Planificador(ciudad)
                sat = geo.imagen_satelital(zona, avisar=avisos.append)
                resultado["ok"] = (ciudad, plan, sat)
            except Exception as error:
                resultado["error"] = error

        self._descarga = threading.Thread(target=trabajo, daemon=True)
        self._descarga.start()
        self._subtitulo(f"Preparando {zona.nombre}…")
        self._escribir(f"Preparando {zona.nombre}"
                       + ("" if zona.descargada() else
                          " (la primera vez descarga el mapa y la imagen satelital; tarda "
                          "uno o dos minutos)") + "…", "decision")

        def revisar():
            while avisos:
                self._escribir(avisos.pop(0).strip(), "tenue")
            if self._descarga.is_alive():
                self.raiz.after(200, revisar)
                return
            self._descarga = None
            self._subtitulo()
            if "error" in resultado:
                self._escribir(f"No se pudo preparar {zona.nombre}: {resultado['error']}",
                               "peligro")
                self.var_zona.set(self.zona.nombre)
                self.var_tamano.set(self._nombre_tamano(self.zona.tamano))
                return
            self.ciudad, self.plan, self.satelite = resultado["ok"]
            self.zona = zona
            self._nueva_zona()

        self.raiz.after(200, revisar)

    def _subtitulo(self, aviso=None):
        z = self.zona
        if aviso:
            self.lbl_sub.configure(text=aviso, fg=P["naranja"])
        else:
            self.lbl_sub.configure(text=f"{z.nombre} · {z.ancho / 1000:.1f} × {z.alto / 1000:.1f} km"
                                        " · simulador de vuelo urbano", fg=P["tenue"])

    def _nueva_zona(self):
        c = self.ciudad
        self.puntos = []
        self.esc = self.mw / c.ancho
        self.var_zona.set(self.zona.nombre)
        self.var_tamano.set(self._nombre_tamano(self.zona.tamano))
        if self.zona.nombre not in self._zonas:
            self._zonas.append(self.zona.nombre)
            self.menu_zona.opciones(self._zonas + [OTRA_ZONA])
        self.var_origen.set(c.origenes[0].nombre)
        self.var_destino.set(c.destinos[0].nombre)
        self._refrescar_origenes()
        self._refrescar_destinos()
        self._dibujar_ciudad()
        self._planear()
        self._escribir(f"Listo: {self.zona.nombre} ({self.zona.ancho / 1000:.1f} × "
                       f"{self.zona.alto / 1000:.1f} km) · {len(c.edificios)} edificios, "
                       f"{len(c.origenes)} farmacias/restaurantes, {len(c.prohibidas)} "
                       "zonas prohibidas.", "exito")

    def _borrar_puntos(self):
        if self.volando:
            return
        self.puntos = []
        self._planear()

    def _planear(self):
        self.mision = None
        self.pausa = False
        self.btn_pausa.texto("Pausa")
        self.mapa.delete("banner")
        o, d = self.origen(), self.destino()
        z0 = o.h + C.ALTURA_DESPEGUE
        self._limpiar_log()
        if self.var_modo.get() == "manual" and self.puntos:
            self.ruta, avisos = self.plan.ruta_manual(o.x, o.y, z0, self.puntos, d.objetivo(True),
                                                      self.var_vehiculo.get())
        else:
            self.ruta = self.plan.ruta_auto(o.x, o.y, z0, d.objetivo(True),
                                            vehiculo=self.var_vehiculo.get())
            avisos = []
        r = self.ruta
        dist = self._distancia(o, d)
        self._subtitulo()
        self._escribir(f"{o.nombre} ({o.carga.lower()}, {o.masa:.1f} kg) → {d.nombre} "
                       + (f"(azotea a {d.h:.0f} m)" if d.h > 0 else "(en el suelo)"), "decision")
        self._escribir(f"Distancia en línea recta: {self._texto_distancia(dist)} "
                       f"({dist:,.1f} m)", "decision")
        self._escribir(f"{r.nombre}: {r.longitud / 1000:.2f} km · ≈{r.t[-1] / 60:.1f} min · "
                       f"altura {min(r.alt):.0f}–{max(r.alt):.0f} m", "info")
        for a in avisos:
            self._escribir(a, "aviso")
        self._escribir(self._ayuda_clic(), "tenue")
        self._escribir("Pulsa ▶ Despegar (o Enter) para iniciar el vuelo.", "tenue")
        self._version_ruta = -1
        self.btn_despegar.texto("▶  Despegar")
        self._dibujar_dinamico()

    def _despegar(self):
        if self.volando:
            return
        if self.mision is not None:
            self._planear()
            return
        eventos = [e for e, v in self.var_ev.items() if v.get()]
        self.mision = Mision(self.ciudad, self.plan, self.origen(), self.destino(), self.ruta,
                             viento=self.var_viento.get(),
                             direccion=DIRECCIONES[self.var_dir.get()],
                             rafagas=self.var_rafagas.get(), aves=self.var_aves.get(),
                             eventos=eventos, semilla=self.semilla, bateria=self.bateria,
                             vehiculo=self.var_vehiculo.get(),
                             piloto_ia=self.var_piloto.get() == "ia")
        self._limpiar_log()
        self.pausa = False
        self._acum = 0.0
        self._version_ruta = -1
        self.btn_despegar.texto("⟲  Nueva misión")
        self.mapa.delete("banner")

    def _provocar(self, evento):
        if not self.volando:
            self._escribir("Primero despega el dron.", "aviso")
            return
        self.mision.provocar(evento)

    def _viento_vivo(self):
        if self.mision is not None:
            v = self.mision.viento
            v.velocidad = self.var_viento.get()
            v.direccion = DIRECCIONES[self.var_dir.get()]
            v.rafagas = self.var_rafagas.get()

    def _pausar(self):
        self.pausa = not self.pausa
        self.btn_pausa.texto("Continuar" if self.pausa else "Pausa")

    def _vel(self, d):
        self.vel_idx = max(0, min(len(VELOCIDADES) - 1, self.vel_idx + d))

    def _lugar_cercano(self, sx, sy):
        for l in self.ciudad.origenes + self.ciudad.destinos:
            lx, ly = self.px(l.x, l.y)
            if math.hypot(sx - lx, sy - ly) < 9:
                return l
        return None

    def _ayuda_clic(self):
        return {"salida": "Haz clic en el mapa donde sale el dron (una farmacia, un "
                          "restaurante, cualquier edificio o un punto en el suelo).",
                "llegada": "Haz clic en el mapa donde aterriza el dron (cualquier edificio, "
                           "casa o punto en el suelo). Para cambiar la salida elige «Salida».",
                "paso": "Haz clic en el mapa para marcar puntos de paso (clic derecho borra "
                        "el último). La ruta se corrige sola si cruza una zona prohibida."
                }[self.var_clic.get()]

    def _cambio_clic(self):
        if self.var_clic.get() == "paso" and self.var_modo.get() != "manual":
            self.var_modo.set("manual")
            self._cambio()
            return
        self._escribir(self._ayuda_clic(), "tenue")

    def _distancia(self, a, b):
        return geo.distancia_m(*self.zona.a_latlon(a.x, a.y), *self.zona.a_latlon(b.x, b.y))

    @staticmethod
    def _texto_distancia(m):
        return f"{m / 1000:.2f} km" if m >= 1000 else f"{m:.0f} m"

    def _agregar_lugar(self, lugar):
        lista = self.ciudad.origenes if lugar.rol == "origen" else self.ciudad.destinos
        existente = next((l for l in lista if math.hypot(l.x - lugar.x, l.y - lugar.y) < 1),
                         None)
        if existente is not None:
            return existente
        nombres = {l.nombre for l in lista}
        base, k = lugar.nombre, 2
        while lugar.nombre in nombres:
            lugar.nombre, k = f"{base} ({k})", k + 1
        lista.append(lugar)
        if lugar.rol == "origen":
            self._refrescar_origenes()
        else:
            self._refrescar_destinos()
        return lugar

    def _clic(self, ev):
        if self.volando:
            return
        modo = self.var_clic.get()
        x, y = ev.x / self.esc, ev.y / self.esc
        if modo == "paso":
            if self.var_modo.get() != "manual":
                self.var_modo.set("manual")
            if self.mision is not None:
                self.mision = None
            self.puntos.append((x, y))
            self._planear()
            return
        rol = "origen" if modo == "salida" else "destino"
        cercano = self._lugar_cercano(ev.x, ev.y)
        if cercano is not None and cercano.rol == rol:
            lugar = cercano
        else:
            if cercano is not None:
                x, y = cercano.x, cercano.y
            lugar = self.ciudad.lugar_en(x, y, rol)
            if lugar is None:
                self._escribir("Ese punto está dentro de una zona prohibida; elige otro.",
                               "aviso")
                return
            lugar = self._agregar_lugar(lugar)
        otro = self.destino() if rol == "origen" else self.origen()
        if math.hypot(lugar.x - otro.x, lugar.y - otro.y) < 30:
            self._escribir("La salida y la llegada están en el mismo lugar; elige otro punto.",
                           "aviso")
            return
        if rol == "origen":
            self.var_origen.set(lugar.nombre)
            self.var_clic.set("llegada")
        else:
            self.var_destino.set(lugar.nombre)
        self._planear()

    def _clic_derecho(self, ev):
        if self.volando or not self.puntos or self.var_modo.get() != "manual":
            return
        self.puntos.pop()
        self._planear()

    def _refrescar_origenes(self):
        self.menu_origen.opciones([o.nombre for o in self.ciudad.origenes])

    def _refrescar_destinos(self):
        self.menu_destino.opciones([d.nombre for d in self.ciudad.destinos])

    def _mover_raton(self, ev):
        x, y = ev.x / self.esc, ev.y / self.esc
        e = self.ciudad.edificio_en(x, y)
        lat, lon = self.zona.a_latlon(x, y)
        txt = f"{lat:.5f}, {lon:.5f}"
        if e:
            txt += (f"  ·  {e.nombre + ' · ' if e.nombre else ''}edificio de {e.h:.0f} m"
                    f"{' (estimada)' if e.estimada else ''}")
        z = self.ciudad.zona_prohibida(x, y)
        if z:
            txt += f"  ·  PROHIBIDO: {z.nombre}"
        o = self.origen()
        txt += ("  ·  a " + self._texto_distancia(geo.distancia_m(*self.zona.a_latlon(o.x, o.y),
                                                                  lat, lon)) + " de la salida")
        self.mapa.delete("cursor")
        E.chip(self.mapa, self.mw - 8, self.mh - 8, txt, P["peligro"] if z else P["texto"], "se",
               (E.FAMILIA, 8), tags=("cursor",))

    def _imagen_fondo(self):
        img = self.satelite.resize((self.mw, self.mh), Image.LANCZOS).convert("RGB")
        img = ImageEnhance.Color(img).enhance(0.78)
        img = ImageEnhance.Brightness(img).enhance(0.86)
        capa = Image.new("RGBA", img.size, (0, 0, 0, 0))
        d = ImageDraw.Draw(capa)
        if self.var_alturas.get():
            for e in sorted(self.ciudad.edificios, key=lambda e: e.h):
                d.polygon([self.px(x, y) for x, y in e.pts], fill=_rgb(color_altura(e.h), 215),
                          outline=(255, 82, 82, 255) if e.h + C.SEPARACION_VERTICAL > C.TECHO
                          else None)
        for z in self.ciudad.prohibidas:
            anillo = [self.px(*p) for p in z.anillo()]
            d.polygon(anillo, fill=(255, 82, 82, 46))
            d.line(anillo + anillo[:1], fill=(255, 82, 82, 230), width=2)
        w, h = img.size
        vin = Image.new("L", (64, 64), 0)
        dv = ImageDraw.Draw(vin)
        for k in range(32):
            dv.rectangle((k, k, 63 - k, 63 - k), fill=int(70 * (1 - k / 31) ** 2.2))
        capa = Image.alpha_composite(capa, Image.merge("RGBA", (
            *(Image.new("L", (w, h), 0),) * 3, vin.resize((w, h), Image.BILINEAR))))
        img = Image.alpha_composite(img.convert("RGBA"), capa).convert("RGB")
        return ImageTk.PhotoImage(img)

    def _fondo(self):
        self._foto_fondo = self._imagen_fondo()
        self.mapa.itemconfigure(self._item_fondo, image=self._foto_fondo)

    def _insignia(self, cv, sx, sy, letra, col, r=7, tags=()):
        cv.create_oval(sx - r + 1, sy - r + 2, sx + r + 1, sy + r + 2, fill="#000000",
                       outline="", stipple="gray50", tags=tags)
        cv.create_oval(sx - r, sy - r, sx + r, sy + r, fill=col, outline="#ffffff", width=1.5,
                       tags=tags)
        cv.create_text(sx, sy, text=letra, fill="#ffffff", font=(E.SEMI, 7), tags=tags)

    def _dibujar_ciudad(self):
        cv, c = self.mapa, self.ciudad
        cv.delete("all")
        self._foto_fondo = self._imagen_fondo()
        self._item_fondo = cv.create_image(0, 0, anchor="nw", image=self._foto_fondo)
        for z in c.prohibidas:
            if z.forma == "circulo":
                hx, hy = self.px(z.cx, z.cy)
                cv.create_oval(hx - 8, hy - 8, hx + 8, hy + 8, outline="#fff", fill="#c62828",
                               width=1.5)
                cv.create_text(hx, hy, text="H", fill="#fff", font=(E.SEMI, 8))
            tx, ty = self.px(z.cx, z.caja()[1])
            E.chip(cv, tx, max(12, ty - 9), "⛔ " + z.nombre, "#ff8a80", "center",
                   (E.SEMI, 7))
        for l in c.lineas:
            cv.create_line(*self.px(l.x0, l.y0), *self.px(l.x1, l.y1), fill="#000000", width=3)
            cv.create_line(*self.px(l.x0, l.y0), *self.px(l.x1, l.y1), fill=COLOR["cable"],
                           dash=(5, 3), width=1)
        for a in c.antenas:
            sx, sy = self.px(a.x, a.y)
            cv.create_polygon(sx, sy - 7, sx - 5, sy + 4, sx + 5, sy + 4, fill=COLOR["antena"],
                              outline="#fff")
        for l in c.origenes:
            letra, col = ICONO[l.tipo]
            self._insignia(cv, *self.px(l.x, l.y), letra, col)
        self._leyenda()
        self._brujula()
        t = cv.create_text(self.mw - 6, 5, anchor="ne", text=C.ATRIBUCION, fill="#b8c2cc",
                           font=(E.FAMILIA, 7))
        x0, y0, x1, y1 = cv.bbox(t)
        cv.tag_lower(cv.create_rectangle(x0 - 5, y0 - 2, x1 + 4, y1 + 1, fill=OSCURO,
                                         outline="", stipple="gray50"), t)
        cv.tag_raise(t)

    def _leyenda(self):
        cv = self.mapa
        items = [("farmacia", "farmacia"), ("restaurante", "restaurante"),
                 ("zona", "zona prohibida"), ("cable", "cables eléctricos"),
                 ("antena", "antena"), ("ave", "aves")]
        x, y = 10, self.mh - 10 - 17 * len(items) - 26
        cv.create_rectangle(x, y, x + 150, self.mh - 10, fill=OSCURO, outline=P["borde"])
        cv.create_text(x + 10, y + 11, text="LEYENDA", anchor="w", fill=P["sutil"],
                       font=(E.SEMI, 7))
        for k, (tipo, txt) in enumerate(items):
            yy = y + 30 + 17 * k
            sx = x + 17
            if tipo in ICONO:
                self._insignia(cv, sx, yy, *ICONO[tipo], r=6)
            elif tipo == "zona":
                cv.create_rectangle(sx - 6, yy - 5, sx + 6, yy + 5, fill="#5a1d22",
                                    outline=COLOR["prohibida"], width=1.5)
            elif tipo == "cable":
                cv.create_line(sx - 7, yy, sx + 7, yy, fill=COLOR["cable"], dash=(4, 2), width=2)
            elif tipo == "antena":
                cv.create_polygon(sx, yy - 6, sx - 5, yy + 4, sx + 5, yy + 4,
                                  fill=COLOR["antena"], outline="#fff")
            else:
                for dx in (-4, 0, 4):
                    cv.create_oval(sx + dx - 1.5, yy - 1.5 + abs(dx) / 3, sx + dx + 1.5,
                                   yy + 1.5 + abs(dx) / 3, fill=COLOR["ave"], outline="")
            cv.create_text(x + 32, yy, text=txt, fill=P["texto"], anchor="w",
                           font=(E.FAMILIA, 8))

    def _brujula(self):
        cv = self.mapa
        x, y = 12, 12
        cv.create_rectangle(x, y, x + 132, y + 40, fill=OSCURO, outline=P["borde"])
        cx, cy = x + 20, y + 20
        cv.create_polygon(cx, cy - 13, cx - 6, cy + 6, cx, cy + 2, fill=P["texto"], outline="")
        cv.create_polygon(cx, cy - 13, cx + 6, cy + 6, cx, cy + 2, fill=P["sutil"], outline="")
        cv.create_text(cx, cy + 13, text="N", fill=P["texto"], font=(E.SEMI, 7))
        metros = 1000 if self.esc * 1000 < 110 else 500
        if self.esc * metros > 90:
            metros = 250
        largo = metros * self.esc
        bx = x + 40
        cv.create_rectangle(bx, y + 22, bx + largo, y + 27, fill=P["texto"], outline="")
        cv.create_rectangle(bx + largo / 2, y + 22, bx + largo, y + 27, fill=P["sutil"],
                            outline="")
        cv.create_text(bx, y + 12, text="0", anchor="w", fill=P["tenue"], font=(E.FAMILIA, 7))
        cv.create_text(bx + largo, y + 12, anchor="e", fill=P["texto"], font=(E.SEMI, 7),
                       text=f"{metros / 1000:g} km" if metros >= 1000 else f"{metros} m")

    def _ruta_actual(self):
        return self.mision.ruta if self.mision is not None else self.ruta

    def _dibujar_rutas(self):
        cv = self.mapa
        cv.delete("ruta")
        m = self.mision
        if m is not None:
            for r in m.rutas_previas:
                cv.create_line(*[v for p in zip(r.x, r.y) for v in self.px(*p)],
                               fill="#9aa5b4", dash=(3, 3), tags="ruta")
        o, d = self.origen(), self.destino()
        (ox, oy), (dx, dy) = self.px(o.x, o.y), self.px(d.x, d.y)
        cv.create_line(ox, oy, dx, dy, fill="#ffffff", dash=(2, 5), tags="ruta")
        r = self._ruta_actual()
        if r is not None:
            todos = [v for p in zip(r.x, r.y) for v in self.px(*p)]
            if len(todos) >= 4:
                cv.create_line(*todos, fill=OSCURO, width=6, capstyle="round",
                               joinstyle="round", tags="ruta")
            ini = 0
            for i in range(1, len(r.x) + 1):
                if i == len(r.x) or r.tramo[i] != r.tramo[ini]:
                    pts = [v for k in range(ini, min(i + 1, len(r.x)))
                           for v in self.px(r.x[k], r.y[k])]
                    if len(pts) >= 4:
                        cv.create_line(*pts, fill=TRAMOS[r.tramo[ini]], width=3,
                                       capstyle="round", joinstyle="round", tags="ruta")
                    ini = i
        for k, (x, y) in enumerate(self.puntos, 1):
            if self.var_modo.get() != "manual":
                break
            self._insignia(cv, *self.px(x, y), str(k), "#37474f", r=8, tags="ruta")
        E.chip(cv, (ox + dx) / 2, (oy + dy) / 2,
               self._texto_distancia(self._distancia(o, d)) + " en línea recta", P["acento"],
               "center", (E.SEMI, 8), tags=("ruta", "etq"))
        for l, col, rol in ((o, P["verde"], "SALIDA"), (d, P["acento"], "ENTREGA")):
            sx, sy = self.px(l.x, l.y)
            cv.create_oval(sx - 13, sy - 13, sx + 13, sy + 13, outline=OSCURO, width=4,
                           tags="ruta")
            cv.create_oval(sx - 13, sy - 13, sx + 13, sy + 13, outline=col, width=2, tags="ruta")
            letra, c2 = ICONO[l.tipo]
            self._insignia(cv, sx, sy, letra, c2, tags="ruta")
            E.chip(cv, sx, sy - 18, f"{rol} · {l.nombre}", col, "s", (E.SEMI, 8),
                   tags=("ruta", "etq"))
        cv.tag_raise("ruta")
        cv.tag_raise("cursor")

    def _dibujar_dinamico(self):
        m = self.mision
        version = m.version_ruta if m else -2
        if version != self._version_ruta:
            self._version_ruta = version
            self._dibujar_rutas()
            self._dibujar_perfil_base()
        cv = self.mapa
        cv.delete("din")
        if m is None:
            self._dibujar_vista()
            self._dibujar_telemetria()
            self._fase("Planeando la ruta", P["acento"])
            return
        d, p = m.dron, m.piloto
        if len(m.estela) > 1:
            pts = [v for q in m.estela + [(d.pos[0], d.pos[1])] for v in self.px(*q)]
            cv.create_line(*pts, fill=OSCURO, width=4, tags="din")
            cv.create_line(*pts, fill=COLOR["estela"], width=2, tags="din")
        for par, k, (bx, by, bz) in m.aves.todas():
            sx, sy = self.px(bx, by)
            cv.create_oval(sx - 1.5, sy - 1.5, sx + 1.5, sy + 1.5, fill=COLOR["ave"],
                           outline="", tags="din")
        o = p.objetivo
        if o is not None and not o.get("es_destino"):
            sx, sy = self.px(o["x"], o["y"])
            cv.create_oval(sx - 10, sy - 10, sx + 10, sy + 10, outline=COLOR["dron_emergencia"],
                           width=2, dash=(3, 2), tags="din")
            E.chip(cv, sx, sy + 14, o["nombre"], COLOR["dron_emergencia"], "n", (E.SEMI, 8),
                   tags=("din",))
        sx, sy = self.px(d.pos[0], d.pos[1])
        if not d.gps_ok:
            r = d.incert * self.esc
            ex, ey = self.px(d.est[0], d.est[1])
            cv.create_oval(ex - r, ey - r, ex + r, ey + r, outline=COLOR["alerta"],
                           dash=(2, 2), tags="din")
        col = P["rojo"] if p.fase == "accidente" else (
            COLOR["dron_emergencia"] if p.emergencia or d.fallas() else COLOR["dron"])
        hx, hy = vector_rumbo(d.rumbo)
        lx, ly = -hy, hx
        cv.create_oval(sx - 14, sy - 14, sx + 14, sy + 14, fill=col, outline="",
                       stipple="gray25", tags=("din", "dmark"))
        cv.create_polygon(sx + hx * 15, sy + hy * 15, sx + lx * 6 + hx * 3, sy + ly * 6 + hy * 3,
                          sx - lx * 6 + hx * 3, sy - ly * 6 + hy * 3, fill="#ffffff",
                          outline=OSCURO, tags=("din", "dmark"))
        cv.create_oval(sx - 6, sy - 6, sx + 6, sy + 6, fill=col, outline="#ffffff", width=2,
                       tags=("din", "dmark"))
        cv.tag_raise("etq")
        cv.tag_raise("dmark")
        cv.tag_raise("banner")
        cv.tag_raise("cursor")
        self._dibujar_vista()
        self._dibujar_telemetria()
        self._dibujar_perfil_dinamico()
        fase = p.nombre_fase()
        col = {"accidente": P["rojo"], "en_tierra": P["verde"]}.get(
            p.fase, COLOR["dron_emergencia"] if p.emergencia else P["acento"])
        if p.fase == "en_tierra" and m.resultado and not m.resultado["exito"]:
            col = COLOR["dron_emergencia"]
        self._fase(("En pausa · " if self.pausa else "") + fase, col)

    def _fase(self, texto, col):
        self.lbl_fase.configure(text=texto, fg=col)
        cv = self.punto_fase
        cv.delete("all")
        cv.create_oval(1, 1, 11, 11, fill=col, outline="")

    def _banner(self):
        m = self.mision
        cv = self.mapa
        cv.delete("banner")
        r = m.resultado
        col = P["verde"] if r["exito"] else (P["rojo"] if r["accidente"]
                                             else COLOR["dron_emergencia"])
        titulo = ("ENTREGA COMPLETADA" if r["exito"] else
                  "ACCIDENTE" if r["accidente"] else "ATERRIZAJE DE EMERGENCIA")
        ancho = min(self.mw - 120, 560)
        cx, y = self.mw / 2, 66
        t = cv.create_text(cx - ancho / 2 + 22, y + 34, text=m.resumen(), fill=P["texto"],
                           font=(E.FAMILIA, 9), width=ancho - 40, anchor="nw", tags="banner")
        y1 = cv.bbox(t)[3] + 14
        cv.create_rectangle(cx - ancho / 2 + 4, y + 4, cx + ancho / 2 + 4, y1 + 4, fill="#000000",
                            outline="", stipple="gray50", tags="banner")
        cv.create_rectangle(cx - ancho / 2, y, cx + ancho / 2, y1, fill=P["tarjeta"],
                            outline=P["borde"], tags="banner")
        cv.create_rectangle(cx - ancho / 2, y, cx - ancho / 2 + 5, y1, fill=col, outline="",
                            tags="banner")
        icono = "✓" if r["exito"] else "!"
        cv.create_oval(cx - ancho / 2 + 20, y + 10, cx - ancho / 2 + 40, y + 30, fill=col,
                       outline="", tags="banner")
        cv.create_text(cx - ancho / 2 + 30, y + 20, text=icono, fill=OSCURO, font=(E.SEMI, 10),
                       tags="banner")
        cv.create_text(cx - ancho / 2 + 50, y + 20, text=titulo, fill=col, anchor="w",
                       font=(E.SEMI, 12), tags="banner")
        cv.tag_raise(t)

    def _dibujar_vista(self):
        cv = self.vista
        cv.delete("all")
        m = self.mision
        if m is not None:
            d = m.dron
            x, y, z = d.pos
        else:
            o = self.origen()
            x, y, z = o.x, o.y, o.h
            d = None
        W, H, e = ANCHO_VISTA, ALTO_VISTA, ESC_VISTA

        def v(px_, py_):
            return W / 2 + (px_ - x) * e, H / 2 + (py_ - y) * e

        r = max(W, H) / e / 2 + 10
        c = self.ciudad
        sat = self.var_sat_vista.get()
        if sat:
            mpp = self.zona.m_por_px
            caja = (round((x - W / 2 / e) / mpp), round((y - H / 2 / e) / mpp),
                    round((x + W / 2 / e) / mpp), round((y + H / 2 / e) / mpp))
            img = self.satelite.crop(caja).resize((W, H)).convert("RGB")
            img = ImageEnhance.Brightness(ImageEnhance.Color(img).enhance(0.75)).enhance(0.8)
            self._foto_vista = ImageTk.PhotoImage(img)
            cv.create_image(0, 0, anchor="nw", image=self._foto_vista)
        else:
            for k in range(0, W, 40):
                cv.create_line(k, 0, k, H, fill=P["rejilla"])
            for k in range(0, H, 40):
                cv.create_line(0, k, W, k, fill=P["rejilla"])
        for zp in c.prohibidas:
            if zp.distancia(x, y) < r * 1.5:
                cv.create_polygon(*[q for p_ in zp.anillo() for q in v(*p_)],
                                  outline=COLOR["prohibida"], width=2, fill=COLOR["prohibida"],
                                  stipple="gray12")
        for ed in c.edificios_cerca(x, y, r):
            pts = [q for p_ in ed.pts for q in v(*p_)]
            if ed.h > z:
                cv.create_polygon(*pts, fill="#d32f2f", stipple="gray50", outline="#ff6b6b",
                                  width=2)
            elif ed.h > z - 15:
                cv.create_polygon(*pts, fill="#ef6c00", stipple="gray25", outline="#ffb74d",
                                  width=1)
            elif sat:
                cv.create_polygon(*pts, fill="", outline="#9fb0c2")
            else:
                cv.create_polygon(*pts, fill=color_altura(ed.h), outline=P["borde"])
            x0, y0 = v(ed.x0, ed.y0)
            x1, y1 = v(ed.x1, ed.y1)
            if x1 - x0 > 34 and y1 - y0 > 18:
                cx_, cy_ = v(*ed.centro)
                cv.create_text(cx_ + 1, cy_ + 1, text=f"{ed.h:.0f} m", fill="#000000",
                               font=(E.SEMI, 7))
                cv.create_text(cx_, cy_, text=f"{ed.h:.0f} m", fill="#ffffff", font=(E.SEMI, 7))
        for l in c.lineas:
            dh, _ = l.cercania(x, y)
            if dh < r * 1.5:
                cv.create_line(*v(l.x0, l.y0), *v(l.x1, l.y1), fill="#000000", width=4)
                cv.create_line(*v(l.x0, l.y0), *v(l.x1, l.y1), fill=COLOR["cable"], width=2,
                               dash=(8, 3))
                for tx, ty in l.torres:
                    if abs(tx - x) < r and abs(ty - y) < r:
                        sx, sy = v(tx, ty)
                        cv.create_rectangle(sx - 4, sy - 4, sx + 4, sy + 4, outline=COLOR["cable"],
                                            width=2)
                dx, dy = l.x1 - l.x0, l.y1 - l.y0
                t = max(0, min(1, ((x - l.x0) * dx + (y - l.y0) * dy) / l.largo ** 2))
                sx, sy = v(l.x0 + dx * t, l.y0 + dy * t)
                E.chip(cv, sx + 6, sy - 6, f"cables {l.altura_cable(t * l.largo):.0f} m",
                       COLOR["cable"], "sw", (E.FAMILIA, 7))
        for a in c.antenas:
            if abs(a.x - x) < r and abs(a.y - y) < r:
                sx, sy = v(a.x, a.y)
                rr = C.RADIO_ANTENA * e
                cv.create_oval(sx - rr, sy - rr, sx + rr, sy + rr, outline=COLOR["antena"],
                               dash=(2, 3))
                cv.create_polygon(sx, sy - 7, sx - 5, sy + 4, sx + 5, sy + 4,
                                  fill=COLOR["antena"], outline="#fff")
                E.chip(cv, sx + 9, sy, f"antena {a.h:.0f} m", "#ff8a80", "w", (E.FAMILIA, 7))
        ruta = self._ruta_actual()
        if ruta is not None:
            i0 = 0 if m is None else max(0, m.piloto.idx - 60)
            pts = [q for k in range(i0, min(len(ruta.x), i0 + 120))
                   for q in v(ruta.x[k], ruta.y[k])]
            if len(pts) >= 4:
                cv.create_line(*pts, fill=OSCURO, width=4)
                cv.create_line(*pts, fill=P["cian"], dash=(6, 4), width=2)
        objetivos = [self.destino().objetivo(True)]
        if m is not None and m.piloto.objetivo is not None:
            objetivos.append(m.piloto.objetivo)
        for o in objetivos:
            sx, sy = v(o["x"], o["y"])
            rr = (1.6 if o["tipo"] == "plataforma" else 6) * e
            cv.create_oval(sx - rr, sy - rr, sx + rr, sy + rr, outline=OSCURO, width=4)
            cv.create_oval(sx - rr, sy - rr, sx + rr, sy + rr, outline=P["acento"], width=2)
            cv.create_text(sx, sy, text="H", fill=P["acento"], font=(E.SEMI, 9))
        if m is not None:
            for par, k, (bx, by, bz) in m.aves.cercanas(x, y, z, r * 1.2):
                sx, sy = v(bx, by)
                cerca = abs(bz - z) < 10
                col = "#ff7043" if cerca else COLOR["ave"]
                cv.create_oval(sx - 3, sy - 3, sx + 3, sy + 3, fill=col, outline=OSCURO)
                if k == 0:
                    E.chip(cv, sx + 7, sy - 7, f"aves {bz - z:+.0f} m", col, "sw",
                           (E.FAMILIA, 7))
            if not d.gps_ok or d.incert > 3:
                ex, ey = v(d.est[0], d.est[1])
                rr = d.incert * e
                cv.create_oval(ex - rr, ey - rr, ex + rr, ey + rr, outline=COLOR["alerta"],
                               dash=(2, 2))
                cv.create_oval(ex - 4, ey - 4, ex + 4, ey + 4, outline=COLOR["alerta"], width=2)
                E.chip(cv, ex + 8, ey + 8, "posición estimada", COLOR["alerta"], "nw",
                       (E.FAMILIA, 7))
            if d.es_avion:
                self._avion(W / 2, H / 2, d)
            else:
                self._hexacoptero(W / 2, H / 2, d)
        else:
            E.chip(cv, W / 2, H / 2 + 24, "plataforma de salida", P["verde"], "n",
                   (E.SEMI, 8))
        if m is not None:
            wx, wy, _ = m.viento.en(x, y, z)
            w = math.hypot(wx, wy)
            cx, cy = W - 34, 36
            cv.create_oval(cx - 26, cy - 26, cx + 26, cy + 26, fill=OSCURO, outline=P["borde"])
            for k in range(8):
                a = math.radians(k * 45)
                rr = 22 if k % 2 == 0 else 24
                cv.create_line(cx + rr * math.sin(a), cy - rr * math.cos(a),
                               cx + 26 * math.sin(a), cy - 26 * math.cos(a), fill=P["sutil"])
            cv.create_text(cx, cy - 17, text="N", fill=P["tenue"], font=(E.SEMI, 6))
            if w > 0.1:
                k = min(18, 3 + w * 1.4) / w
                cv.create_line(cx - wx * k, cy - wy * k, cx + wx * k, cy + wy * k,
                               fill=P["cian"], width=3, arrow="last", arrowshape=(8, 9, 4))
            E.chip(cv, cx, cy + 30, f"{w:.1f} m/s", P["cian"], "n", (E.SEMI, 7))
        sb = 50 * e
        cv.create_rectangle(10, H - 26, 22 + sb, H - 6, fill=OSCURO, outline="")
        cv.create_line(16, H - 11, 16 + sb, H - 11, fill=P["texto"], width=2)
        for xx in (16, 16 + sb):
            cv.create_line(xx, H - 15, xx, H - 8, fill=P["texto"], width=2)
        cv.create_text(16 + sb / 2, H - 19, text="50 m", fill=P["texto"], font=(E.FAMILIA, 7))
        E.chip(cv, 8, 8, f"ALTURA {z:.0f} m", P["texto"], "nw", (E.SEMI, 8))
        E.chip(cv, 8, 32, "rojo: más alto que el dron · naranja: menos de 15 m abajo",
               P["tenue"], "nw", (E.FAMILIA, 7))

    def _hexacoptero(self, cx, cy, d):
        cv = self.vista
        n = d.spec["motores"]
        cv.create_oval(cx - 18 + 5, cy - 18 + 7, cx + 18 + 5, cy + 18 + 7, fill="#000000",
                       outline="", stipple="gray25")
        for k in range(n):
            ang = d.rumbo + 180 / n + k * 360 / n
            ux, uy = vector_rumbo(ang)
            mx, my = cx + ux * 17, cy + uy * 17
            cv.create_line(cx, cy, mx, my, fill="#1b1f27", width=5)
            cv.create_line(cx, cy, mx, my, fill="#aab4c3", width=2)
        for k in range(n):
            ang = d.rumbo + 180 / n + k * 360 / n
            ux, uy = vector_rumbo(ang)
            mx, my = cx + ux * 17, cy + uy * 17
            sano = d.motores[k] >= 0.5
            col = P["verde"] if sano else P["rojo"]
            cv.create_oval(mx - 7, my - 7, mx + 7, my + 7, fill="#cfd8dc" if sano else "#5d1f1f",
                           stipple="gray25" if sano else "", outline=col, width=1.5)
            cv.create_oval(mx - 2, my - 2, mx + 2, my + 2, fill="#1b1f27", outline="")
            if not sano:
                cv.create_line(mx - 4, my - 4, mx + 4, my + 4, fill=col, width=2)
                cv.create_line(mx - 4, my + 4, mx + 4, my - 4, fill=col, width=2)
        ux, uy = vector_rumbo(d.rumbo)
        cv.create_oval(cx - 7, cy - 7, cx + 7, cy + 7, fill="#263040", outline="#ffffff",
                       width=1.5)
        cv.create_oval(cx - 3, cy - 3, cx + 3, cy + 3, fill=P["cian"], outline="")
        cv.create_line(cx + ux * 7, cy + uy * 7, cx + ux * 14, cy + uy * 14, fill="#ffffff",
                       width=2, arrow="last", arrowshape=(5, 6, 3))
        if d.paracaidas:
            cv.create_arc(cx - 28, cy - 36, cx + 28, cy + 10, start=0, extent=180,
                          outline=P["naranja"], width=2, style="arc")
            E.chip(cv, cx, cy - 40, "PARACAÍDAS", P["naranja"], "s", (E.SEMI, 7))

    def _avion(self, cx, cy, d):
        cv = self.vista
        fx, fy = vector_rumbo(d.rumbo)
        lx, ly = -fy, fx

        def pt(a, b):
            return cx + fx * a + lx * b, cy + fy * a + ly * b

        sombra = [pt(4, -24), pt(4, 24), pt(-3, 24), pt(-3, -24)]
        cv.create_polygon(*[q + 6 for p_ in sombra for q in p_], fill="#000000",
                          stipple="gray25", outline="")
        ala = [pt(5, -24), pt(5, 24), pt(-3, 24), pt(-3, -24)]
        cv.create_polygon(*[q for p_ in ala for q in p_], fill="#d9e0e8", outline="#7d8796")
        cola = [pt(-15, -9), pt(-15, 9), pt(-19, 9), pt(-19, -9)]
        cv.create_polygon(*[q for p_ in cola for q in p_], fill="#d9e0e8", outline="#7d8796")
        cv.create_line(*pt(15, 0), *pt(-19, 0), fill="#7d8796", width=7, capstyle="round")
        cv.create_line(*pt(15, 0), *pt(-19, 0), fill="#f1f4f8", width=5, capstyle="round")
        cv.create_line(*pt(14, 0), *pt(9, 0), fill=P["cian"], width=4, capstyle="round")
        rotores_on = d.modo == "rotor" and not d.apagado
        k = 0
        for b in (-13, 13):
            cv.create_line(*pt(14, b), *pt(-14, b), fill="#8a95a5", width=2)
        for b in (-13, 13):
            for a in (14, -14):
                for desp in (-3, 3):
                    if k >= len(d.motores):
                        break
                    sano = d.motores[k] >= 0.5
                    col = P["rojo"] if not sano else (P["verde"] if rotores_on else "#78909c")
                    x_, y_ = pt(a + desp * 0.4, b + desp)
                    cv.create_oval(x_ - 4, y_ - 4, x_ + 4, y_ + 4, outline=col, width=2,
                                   fill="#5d1f1f" if not sano else "")
                    k += 1
        col = P["rojo"] if not d.empuje_ok else (P["verde"] if d.modo == "ala" else "#78909c")
        cv.create_line(*pt(-21, -6), *pt(-21, 6), fill=col, width=3)
        E.chip(cv, cx, cy + 34, "como avión" if d.modo == "ala" else "como multirrotor",
               "#e1f5fe", "n", (E.SEMI, 7))
        if d.paracaidas:
            E.chip(cv, cx, cy - 36, "PARACAÍDAS", P["naranja"], "s", (E.SEMI, 7))

    def _mosaico(self, cv, datos):
        n, sep, alto = len(datos), 6, 54
        w = (ANCHO_VISTA - sep * (n - 1)) / n
        for k, (etq, valor, unidad, color, frac) in enumerate(datos):
            x = k * (w + sep)
            cv.create_rectangle(x, 0, x + w, alto, fill=P["tarjeta2"], outline="")
            cv.create_rectangle(x, 0, x + 3, alto, fill=color, outline="")
            cv.create_text(x + 11, 10, text=etq, anchor="w", fill=P["tenue"], font=(E.SEMI, 7))
            t = cv.create_text(x + 11, 31, text=valor, anchor="w", fill=P["texto"],
                               font=(E.SEMI, 14))
            if unidad:
                cv.create_text(cv.bbox(t)[2] + 3, 34, text=unidad, anchor="w", fill=P["tenue"],
                               font=(E.FAMILIA, 7))
            if frac is not None:
                E.barra(cv, x + 11, alto - 8, w - 20, 3, frac, color)

    def _filas(self, cv, filas, y0=64):
        for k, (et, val, col) in enumerate(filas):
            y = y0 + k * 19
            cv.create_text(0, y, anchor="nw", text=et.upper(), fill=P["sutil"], font=(E.SEMI, 7))
            if len(val) > 48:
                val = val[:47].rstrip() + "…"
            cv.create_text(74, y - 2, anchor="nw", text=val, fill=COLOR[col],
                           font=(E.FAMILIA, 9))

    def _dibujar_telemetria(self):
        cv = self.tele
        cv.delete("all")
        m = self.mision
        veh = C.VEHICULOS[self.var_vehiculo.get()]
        if m is None:
            r = self.ruta
            o, d = self.origen(), self.destino()
            self._mosaico(cv, [
                ("RUTA", f"{r.longitud / 1000:.2f}", "km", P["cian"], None),
                ("DURACIÓN", f"{r.t[-1] / 60:.1f}", "min", P["azul"], None),
                ("ALTURA MÁX.", f"{max(r.alt):.0f}", "m", P["morado"], max(r.alt) / C.TECHO),
                ("BATERÍA", f"{self.bateria * 100:.0f}", "%", P["verde"], self.bateria)])
            self._filas(cv, [
                ("Carga", f"{o.carga} · {o.masa:.1f} kg", "texto"),
                ("Cliente", f"{d.nombre}", "texto"),
                ("Azotea", f"{d.h:.0f} m ({d.detalle})", "texto"),
                ("Vehículo", veh["nombre"] + " · piloto "
                 + ("IA" if self.var_piloto.get() == "ia" else "clásico")
                 + f" · {veh['bateria_wh'] * self.bateria:.0f} Wh", "texto"),
                ("Viento", f"{self.var_viento.get():.1f} m/s del {self.var_dir.get()}"
                           f"{' con ráfagas' if self.var_rafagas.get() else ''}", "texto"),
                ("Destino", "{:.6f}, {:.6f}".format(*self.zona.a_latlon(d.x, d.y)), "texto")])
            return
        d, p = m.dron, m.piloto
        x, y, z = d.pos
        w = m.viento.en(x, y, z)
        vs = math.hypot(d.vel[0], d.vel[1])
        va = math.hypot(d.vel[0] - w[0], d.vel[1] - w[1])
        abajo = m.ciudad.altura_superficie(x, y)
        ruta = p.ruta
        rem = p.restante() if ruta is not None and p.fase == "ruta" else \
            math.hypot(p.objetivo["x"] - x, p.objetivo["y"] - y)
        eta = ruta.tiempo_restante(p.idx) if ruta is not None and p.fase == "ruta" else None
        gps = d.estado_gps()
        col_gps = {"OK": "exito", "VISIÓN": "exito", "DEGRADADO": "alerta"}.get(gps, "peligro")
        if d.gps_ok:
            gtxt = f"{gps} · {d.sats} satélites · ±{d.incert:.1f} m"
        else:
            gtxt = f"{gps} {d.t_sin_gps:.0f} s · ±{d.incert:.0f} m (inercial)"
        n_rot = d.spec["motores"]
        sanos = n_rot - d.rotores_fallados()
        if d.es_avion:
            motores = (f"rotores {sanos}/{n_rot} ({'encendidos' if d.modo == 'rotor' else 'apagados'})"
                       f" · hélice {'OK' if d.empuje_ok else 'FALLADA'}")
        else:
            motores = f"{sanos}/{n_rot} · empuje/peso {d.relacion_empuje():.2f} · {d.empuje:.0f} N"
        raf = m.viento.intensidad_rafaga()
        soc = d.soc
        colb = P["verde"] if soc > 0.3 else (P["naranja"] if soc > 0.15 else P["rojo"])
        total = ruta.longitud if ruta is not None and p.fase == "ruta" else None
        self._mosaico(cv, [
            ("ALTURA", f"{z:.0f}", f"m · {z - abajo:+.0f}", P["morado"], z / C.TECHO),
            ("VELOCIDAD", f"{vs * 3.6:.0f}", "km/h", P["azul"], vs / max(1.0, veh["v_max"])),
            ("BATERÍA", f"{soc * 100:.0f}", "%", colb, soc),
            ("LLEGA EN", tiempo(eta) if eta is not None else "--:--", "", P["cian"],
             1 - rem / total if total else None)])
        res = ANCHO_VISTA / 4 * 2 + 6 + 11 + (ANCHO_VISTA / 4 - 6 - 20) * C.RESERVA
        cv.create_line(res, 44, res, 50, fill=P["rojo"], width=2)
        self._filas(cv, [
            ("Tiempo", f"{tiempo(m.t)} · aire {va:.1f} m/s · vertical {d.vel[2]:+.1f} m/s · "
                       f"{d.voltaje:.1f} V {d.potencia:.0f} W", "texto"),
            ("Rumbo", f"{d.rumbo:03.0f}° ({cardinal(d.rumbo)}) · faltan {rem / 1000:.2f} km",
             "texto"),
            ("GPS", gtxt, col_gps),
            ("Motores", motores, "exito" if d.fallas() == 0 else "peligro"),
            ("Viento", f"{math.hypot(w[0], w[1]):.1f} m/s del {cardinal(m.viento.direccion)}"
                       + (f" · ráfaga +{raf:.1f}" if raf > 0.5 else ""),
             "alerta" if raf > 3 else "texto"),
            ("Carga", f"{m.origen.carga} {d.carga:.1f} kg → {p.objetivo['nombre']}", "texto")])

    def _escala_perfil(self, ruta):
        w, h = int(self.perfil["width"]), int(self.perfil["height"])
        x0, x1 = 30, w - 6
        y0, y1 = h - 16, 16
        hmax = 135.0
        L = max(ruta.longitud, 1.0)
        return (lambda s: x0 + (x1 - x0) * s / L), (lambda h_: y0 + (y1 - y0) * min(h_, hmax) / hmax)

    def _dibujar_perfil_base(self):
        cv = self.perfil
        cv.delete("all")
        w, h = int(cv["width"]), int(cv["height"])
        ruta = self._ruta_actual()
        if ruta is None:
            cv.create_text(w / 2, h / 2, fill=P["tenue"], font=E.F_TEXTO,
                           text="Aterrizaje forzoso: vuela directo al punto despejado.")
            return
        X, Y = self._escala_perfil(ruta)
        for hh in (0, 40, 80, 120):
            cv.create_line(30, Y(hh), w - 6, Y(hh), fill=P["rejilla"])
            cv.create_text(24, Y(hh), anchor="e", text=f"{hh}", fill=P["sutil"],
                           font=(E.FAMILIA, 7))
        paso = 0.5 if ruta.longitud < 6000 else 1.0 if ruta.longitud < 12000 else 2.0
        km = 0.0
        while km * 1000 <= ruta.longitud + 1:
            cv.create_text(X(km * 1000), h - 6, text=f"{km:g} km", fill=P["sutil"],
                           font=(E.FAMILIA, 7))
            km += paso
        n = len(ruta.x)
        pts = [X(0), Y(0)] + [v for i in range(n) for v in (X(ruta.s[i]), Y(ruta.obst[i]))] \
            + [X(ruta.longitud), Y(0)]
        cv.create_polygon(*pts, fill="#2a3240", outline="")
        bajo = [self.ciudad.altura_superficie(ruta.x[i], ruta.y[i]) for i in range(n)]
        pts = [X(0), Y(0)] + [v for i in range(n) for v in (X(ruta.s[i]), Y(bajo[i]))] \
            + [X(ruta.longitud), Y(0)]
        cv.create_polygon(*pts, fill="#4a5568", outline="")
        for i in range(n):
            if ruta.cable[i]:
                cv.create_line(X(ruta.s[i]) - 2, Y(ruta.cable[i]), X(ruta.s[i]) + 2,
                               Y(ruta.cable[i]), fill=COLOR["cable"], width=2)
            if ruta.zona[i]:
                cv.create_line(X(ruta.s[i]), Y(0), X(ruta.s[i]), Y(0) + 4,
                               fill=COLOR["prohibida"], width=2)
        cv.create_line(30, Y(C.TECHO), w - 6, Y(C.TECHO), fill=P["rojo"], dash=(6, 4))
        cv.create_text(w - 8, Y(C.TECHO) - 2, anchor="se", fill="#ff9a9a",
                       font=(E.FAMILIA, 7), text="techo legal 120 m")
        ini = 0
        for i in range(1, n + 1):
            if i == n or ruta.tramo[i] != ruta.tramo[ini]:
                seg = [v for k in range(ini, min(i + 1, n)) for v in (X(ruta.s[k]), Y(ruta.alt[k]))]
                if len(seg) >= 4:
                    cv.create_line(*seg, fill=TRAMOS[ruta.tramo[ini]], width=3, capstyle="round")
                ini = i
        xx = 32
        for nombre in TRAMOS:
            if nombre in ruta.tramo:
                cv.create_rectangle(xx, 2, xx + 10, 6, fill=TRAMOS[nombre], outline="")
                t = cv.create_text(xx + 14, 4, anchor="w", text=nombre, fill=P["tenue"],
                                   font=(E.FAMILIA, 7))
                xx = cv.bbox(t)[2] + 12
        cv.create_rectangle(xx, 0, xx + 10, 8, fill="#4a5568", outline="")
        t = cv.create_text(xx + 14, 4, anchor="w", text="edificios", fill=P["tenue"],
                           font=(E.FAMILIA, 7))
        xx = cv.bbox(t)[2] + 12
        cv.create_line(xx, 4, xx + 10, 4, fill=COLOR["cable"], width=2)
        cv.create_text(xx + 14, 4, anchor="w", text="cables", fill=P["tenue"], font=(E.FAMILIA, 7))

    def _dibujar_perfil_dinamico(self):
        cv = self.perfil
        cv.delete("pdin")
        m = self.mision
        ruta = m.ruta
        if ruta is None:
            return
        X, Y = self._escala_perfil(ruta)
        pts = [v for s, h in m.perfil_real for v in (X(s), Y(h))]
        p = m.piloto
        s = ruta.s[p.idx] if p.ruta is ruta else 0.0
        z = m.dron.pos[2]
        pts += [X(s), Y(z)]
        if len(pts) >= 4:
            cv.create_line(*pts, fill="#ffffff", width=1.5, tags="pdin")
        cv.create_line(X(s), Y(0), X(s), Y(z), fill=P["sutil"], dash=(2, 2), tags="pdin")
        cv.create_oval(X(s) - 5, Y(z) - 5, X(s) + 5, Y(z) + 5, fill="#ffffff", outline=P["cian"],
                       width=2, tags="pdin")
        E.chip(cv, X(s) + 9, Y(z), f"{z:.0f} m", P["texto"], "w", (E.SEMI, 7),
               fondo=P["tarjeta2"], tags=("pdin",))

    def _google_earth(self):
        m = self.mision
        o, d = self.origen(), self.destino()
        sello = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        archivo = os.path.join(CARPETA_VUELOS, f"vuelo_{sello}.kml")
        lugares = [(o.nombre, o.x, o.y, o.h), (d.nombre, d.x, d.y, d.h)]
        vuelo, previas, ruta = [], (), self.ruta
        descripcion = f"{o.nombre} → {d.nombre}"
        if m is not None:
            vuelo = list(m.traza)
            previas, ruta = m.rutas_previas, m.ruta
            if m.resultado:
                descripcion += " · " + m.resultado["texto"]
            ob = m.piloto.objetivo
            if ob and not ob.get("es_destino"):
                lugares.append((ob["nombre"], ob["x"], ob["y"], ob["z"]))
        zonas = [(z.nombre, z.anillo()) for z in self.ciudad.prohibidas]
        geo.exportar_kml(self.zona, archivo, "Dron de entregas — " + descripcion, ruta,
                         previas, vuelo, lugares, zonas, descripcion)
        self._escribir(f"Vuelo exportado a {archivo}. Se abre con Google Earth Pro; también "
                       "puedes arrastrarlo a earth.google.com (Proyectos → Importar archivo "
                       "KML) o importarlo en Google My Maps.", "exito")
        try:
            os.startfile(archivo)
        except (AttributeError, OSError):
            webbrowser.open("https://earth.google.com/web/")

    def _google_maps(self):
        if self.mision is not None:
            x, y = self.mision.dron.pos[0], self.mision.dron.pos[1]
        else:
            d = self.destino()
            x, y = d.x, d.y
        lat, lon = self.zona.a_latlon(x, y)
        webbrowser.open(geo.url_google_maps(lat, lon, satelite=True))

    def _ciclo(self):
        try:
            m = self.mision
            if m is not None and not self.pausa and not m.terminada:
                self._acum += VELOCIDADES[self.vel_idx] * C.FPS_MS / 1000
                pasos = 0
                while self._acum >= C.DT and pasos < 800 and not m.terminada:
                    m.paso()
                    self._acum -= C.DT
                    pasos += 1
                if m.terminada:
                    self._acum = 0.0
            if m is not None:
                for t, texto, nivel in m.nuevos:
                    self._escribir(texto, nivel, t)
                m.nuevos.clear()
                if m.terminada and not self.mapa.find_withtag("banner"):
                    self._banner()
            self.lbl_vel.configure(text=f"x{VELOCIDADES[self.vel_idx]}")
            texto = "Restaurar GPS" if m is not None and not m.dron.gps_ok else "Cortar GPS"
            if self.btn_gps.w.cget("text") != texto:
                self.btn_gps.texto(texto)
            self._dibujar_dinamico()
        finally:
            self.raiz.after(C.FPS_MS, self._ciclo)

    def ejecutar(self):
        self.raiz.mainloop()
