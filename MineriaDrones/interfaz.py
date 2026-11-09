import datetime
import json
import math
import os
import queue
import subprocess
import sys
import threading
import time
import tkinter as tk
import traceback
import webbrowser
from tkinter import filedialog, ttk

import numpy as np
from PIL import Image, ImageTk

import capas as CA
import config as C
import estilo as E
import exportar as EX
import geo as G
from grabador import BotonGrabar
import planificador as PL
import procesamiento as PR
import sensores as SE
import terreno as T
import visor3d as V3

P = E.P
MISION_CORTA = [("fotogrametria", "Foto"), ("lidar", "LiDAR"), ("termica", "Térmica"), ("visual", "Visual")]
GOOGLE = "Google Maps (satélite)"
CAPAS = ["Imagen del sitio", GOOGLE, "Ortomosaico (dron)", "Relieve sombreado", "Hipsométrico (DTM)", "Pendientes",
         "Densidad LiDAR", "Cobertura de fotos", "Diferencia A/B", "Térmica"]
SEV_COLOR = {"crítica": P["rojo"], "alta": P["naranja"], "media": P["acento"], "info": P["gris"]}
ORDEN_SEV = {"crítica": 0, "alta": 1, "media": 2, "info": 3}


def _clave(nombre):
    return "".join(c if c.isalnum() else "_" for c in nombre.lower())[:40].strip("_")


class Desplazable:
    def __init__(self, padre, ancho):
        self.cv = tk.Canvas(padre, bg=P["fondo"], highlightthickness=0, width=ancho)
        self.barra = ttk.Scrollbar(padre, orient="vertical", command=self.cv.yview)
        self.cuerpo = tk.Frame(self.cv, bg=P["fondo"])
        self.ventana = self.cv.create_window(0, 0, window=self.cuerpo, anchor="nw", width=ancho)
        self.cv.configure(yscrollcommand=self.barra.set)
        self.cuerpo.bind("<Configure>", lambda e: self.cv.configure(scrollregion=self.cv.bbox("all")))
        self.cv.bind("<Configure>", lambda e: self.cv.itemconfigure(self.ventana, width=e.width))
        for w in (self.cv, self.cuerpo):
            w.bind("<Enter>", lambda e: self.cv.bind_all("<MouseWheel>", self._rueda))
            w.bind("<Leave>", lambda e: self.cv.unbind_all("<MouseWheel>"))

    def _rueda(self, e):
        self.cv.yview_scroll(-1 if e.delta > 0 else 1, "units")

    def pack(self, **kw):
        self.barra.pack(side="right", fill="y")
        self.cv.pack(**kw)


class App:
    def __init__(self, dir_proyectos=None):
        try:
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass
        if dir_proyectos:
            C.CARPETA_PROYECTOS = dir_proyectos
        self.raiz = tk.Tk()
        self.raiz.title("Minería con drones — topografía, LiDAR, modelos 3D e inspección")
        self.raiz.configure(bg=P["fondo"])
        w, h = self.raiz.winfo_screenwidth(), self.raiz.winfo_screenheight()
        self.raiz.geometry(f"{min(1640, w - 40)}x{min(960, h - 80)}+10+10")
        self.raiz.minsize(1280, 760)
        self._estilos()
        self.cola = queue.Queue()
        self.ocupado = False
        self.sitio = None
        self.carpeta = None
        self.plan = None
        self.sim = None
        self.pausa = False
        self.vuelos = {}
        self.prod = {}
        self.prec = {}
        self.termica = {}
        self.visual = {}
        self.geom = {}
        self.comp = None
        self.checkpoints = []
        self.curvas = {}
        self._cache = {}
        self.vista = None
        self.dibujando = None
        self.seleccion = None
        self.google = {}
        self.var = {
            "mina": tk.StringVar(value="La Caridad, Sonora"), "lugar": tk.StringVar(),
            "tamano": tk.StringVar(value=C.MINAS["La Caridad, Sonora"][2]), "clave": tk.StringVar(value=G.clave_google()),
            "osm": tk.BooleanVar(value=True), "fuera": tk.BooleanVar(value=True), "sobre": tk.BooleanVar(value=False),
            "mision": "lidar", "epoca": "B", "sensor": tk.StringVar(value=next(iter(C.LIDAR))),
            "altura": tk.DoubleVar(value=90), "velocidad": tk.DoubleVar(value=10), "tf": tk.DoubleVar(value=80),
            "tl": tk.DoubleVar(value=45), "drones": tk.DoubleVar(value=2), "densidad": tk.DoubleVar(value=3),
            "seguir": tk.BooleanVar(value=True), "auto_rumbo": tk.BooleanVar(value=True), "rumbo": tk.DoubleVar(value=0),
            "posicion": tk.StringVar(value="RTK"), "area": tk.StringVar(value="Todo el sitio"),
            "gcp": tk.DoubleVar(value=6), "cps": tk.DoubleVar(value=20), "intervalo": 5.0,
            "capa": tk.StringVar(value=CAPAS[0]), "ver_epoca": "B", "multi": 30,
            "ov_zonas": tk.BooleanVar(value=True), "ov_plan": tk.BooleanVar(value=True), "ov_alertas": tk.BooleanVar(value=True),
            "ov_curvas": tk.BooleanVar(value=False), "ov_control": tk.BooleanVar(value=False),
            "tipo_zona": tk.StringVar(value=C.TIPOS_ZONA["extraccion"][0]), "nombre_zona": tk.StringVar(value=""),
            "cota": tk.StringVar(value=""), "proyecto": tk.StringVar(value=""), "densidad_roca": tk.DoubleVar(value=C.DENSIDAD_ROCA),
        }
        self._construir()
        self.raiz.after(60, self._bucle)
        self.raiz.after(200, self._inicio)

    def _estilos(self):
        st = ttk.Style(self.raiz)
        st.theme_use("clam")
        st.configure("Treeview", background=P["tarjeta"], fieldbackground=P["tarjeta"], foreground=P["texto"],
                     bordercolor=P["borde"], lightcolor=P["borde"], darkcolor=P["borde"], rowheight=24, font=E.F_CHICA,
                     borderwidth=0)
        st.configure("Treeview.Heading", background=P["tarjeta2"], foreground=P["tenue"], bordercolor=P["borde"],
                     lightcolor=P["tarjeta2"], darkcolor=P["tarjeta2"], relief="flat", font=(E.SEMI, 8))
        st.map("Treeview.Heading", background=[("active", P["tarjeta2"])])
        st.map("Treeview", background=[("selected", E.mezclar(P["tarjeta"], P["acento"], 0.22))], foreground=[("selected", P["texto"])])
        st.layout("Treeview", [("Treeview.treearea", {"sticky": "nswe"})])
        st.configure("Vertical.TScrollbar", background=P["tarjeta2"], troughcolor=P["fondo"], bordercolor=P["fondo"],
                     arrowcolor=P["tenue"], lightcolor=P["tarjeta2"], darkcolor=P["tarjeta2"])
        st.configure("TEntry", fieldbackground=P["tarjeta2"], foreground=P["texto"], bordercolor=P["borde"],
                     lightcolor=P["borde"], darkcolor=P["borde"], insertcolor=P["texto"])

    def _entrada(self, padre, var, ancho=30):
        e = tk.Entry(padre, textvariable=var, bg=P["tarjeta2"], fg=P["texto"], insertbackground=P["texto"], relief="flat",
                     font=E.F_TEXTO, highlightthickness=1, highlightbackground=P["borde"], highlightcolor=P["acento"], width=ancho)
        return e

    def _fila(self, padre, texto):
        f = tk.Frame(padre, bg=P["tarjeta"])
        f.pack(fill="x", pady=(6, 0))
        tk.Label(f, text=texto, bg=P["tarjeta"], fg=P["tenue"], font=E.F_CHICA, anchor="w").pack(fill="x")
        return f

    def _construir(self):
        r = self.raiz
        cab = tk.Frame(r, bg=P["fondo"])
        cab.pack(fill="x", padx=14, pady=(10, 6))
        izq = tk.Frame(cab, bg=P["fondo"])
        izq.pack(side="left")
        tk.Label(izq, text="Minería con drones", bg=P["fondo"], fg=P["texto"], font=E.F_TITULO).pack(anchor="w")
        self.l_sitio = tk.Label(izq, text="Sin sitio", bg=P["fondo"], fg=P["tenue"], font=E.F_TEXTO)
        self.l_sitio.pack(anchor="w")
        der = tk.Frame(cab, bg=P["fondo"])
        der.pack(side="right")
        E.Boton(der, "Exportar todo", self.exportar_todo, primario=True, color=P["acento"]).pack(side="right", padx=(6, 0))
        E.Boton(der, "Modelo 3D", self.modelo_3d).pack(side="right", padx=(6, 0))
        E.Boton(der, "Google Earth", self.google_earth).pack(side="right", padx=(6, 0))
        E.Boton(der, "Google Maps", self.google_maps).pack(side="right", padx=(6, 0))
        self.grabar = E.estilo_boton_grabar(BotonGrabar(der, r, lambda t: self.log(t))).pack(side="right", padx=(6, 0))
        cuerpo = tk.Frame(r, bg=P["fondo"])
        cuerpo.pack(fill="both", expand=True, padx=14, pady=(0, 10))
        lado = tk.Frame(cuerpo, bg=P["fondo"], width=380)
        lado.pack(side="left", fill="y")
        lado.pack_propagate(False)
        self.tabs = E.Segmentado(lado, [("sitio", "Sitio"), ("vuelo", "Vuelo"), ("procesar", "Procesar"), ("analisis", "Análisis")],
                                 "sitio", self._tab)
        self.tabs.pack(fill="x", pady=(0, 8))
        self.desp = Desplazable(lado, 360)
        self.desp.pack(side="left", fill="both", expand=True)
        self.paneles = {}
        for k in ("sitio", "vuelo", "procesar", "analisis"):
            self.paneles[k] = tk.Frame(self.desp.cuerpo, bg=P["fondo"])
        self._panel_sitio(self.paneles["sitio"])
        self._panel_vuelo(self.paneles["vuelo"])
        self._panel_procesar(self.paneles["procesar"])
        self._panel_analisis(self.paneles["analisis"])
        self._tab("sitio")
        derecha = tk.Frame(cuerpo, bg=P["fondo"], width=410)
        derecha.pack(side="right", fill="y", padx=(10, 0))
        derecha.pack_propagate(False)
        self._panel_derecho(derecha)
        centro = tk.Frame(cuerpo, bg=P["fondo"])
        centro.pack(side="left", fill="both", expand=True, padx=(10, 0))
        self._panel_mapa(centro)

    def _tab(self, k):
        self.tabs.poner(k)
        for n, f in self.paneles.items():
            f.pack_forget()
        self.paneles[k].pack(fill="both", expand=True)
        self.desp.cv.yview_moveto(0)

    def _panel_sitio(self, p):
        m, c = E.tarjeta(p, "Mina o lugar")
        m.pack(fill="x", pady=(0, 8))
        f = self._fila(c, "Mina predefinida")
        E.Menu(f, self.var["mina"], list(C.MINAS), self._elegir_mina, 34).pack(fill="x")
        f = self._fila(c, "…o busca: ciudad, mina, coordenadas o enlace de Google Maps")
        e = self._entrada(f, self.var["lugar"], 34)
        e.pack(fill="x", ipady=4)
        e.bind("<Return>", lambda ev: self.crear_sitio(buscar=True))
        f = self._fila(c, "Tamaño del levantamiento")
        E.Menu(f, self.var["tamano"], list(C.TAMANOS), lambda: None, 16).pack(anchor="w")
        tk.Frame(c, bg=P["tarjeta"], height=6).pack()
        E.Interruptor(c, "Capas geoespaciales de OpenStreetMap", self.var["osm"]).pack(anchor="w", pady=2)
        E.Interruptor(c, "Simular extracción fuera de zona en B", self.var["fuera"]).pack(anchor="w", pady=2)
        E.Interruptor(c, "Simular sobre-excavación bajo cota", self.var["sobre"]).pack(anchor="w", pady=2)
        b = tk.Frame(c, bg=P["tarjeta"])
        b.pack(fill="x", pady=(10, 0))
        E.Boton(b, "Crear sitio", lambda: self.crear_sitio(False), primario=True, color=P["acento"]).pack(side="left")
        E.Boton(b, "Buscar lugar", lambda: self.crear_sitio(True)).pack(side="left", padx=6)
        E.etiqueta(c, "Elige una mina o busca un lugar y el sistema trabaja sobre su mapa satelital real (Esri, o Google con "
                      "tu clave) y su elevación real (AWS Terrain Tiles). «Google Earth» abre Google Earth en el sitio (Google "
                      "Earth Pro con el KML si lo tienes instalado); «Modelo 3D» es el visor propio con tus levantamientos.", wraplength=320, justify="left").pack(anchor="w", pady=(8, 0))
        m, c = E.tarjeta(p, "Google Maps dentro del programa")
        m.pack(fill="x", pady=(0, 8))
        E.etiqueta(c, "Sin clave, «Google Maps» abre el mapa oficial de Google del sitio en una ventana del programa. "
                      "Opcional: con una clave de Google Maps Platform (Map Tiles API) el satélite de Google también se "
                      "usa como fondo del mapa de trabajo y del modelo 3D.",
                   wraplength=320, justify="left").pack(anchor="w")
        f = self._fila(c, "Clave de API")
        self.e_clave = self._entrada(f, self.var["clave"], 34)
        self.e_clave.configure(show="•")
        self.e_clave.pack(fill="x", ipady=4)
        b = tk.Frame(c, bg=P["tarjeta"])
        b.pack(fill="x", pady=(8, 0))
        E.Boton(b, "Guardar y cargar", self._guardar_clave).pack(side="left")
        E.Boton(b, "Obtener una clave", lambda: webbrowser.open(
            "https://console.cloud.google.com/apis/library/tile.googleapis.com")).pack(side="left", padx=6)
        m, c = E.tarjeta(p, "Proyectos guardados")
        m.pack(fill="x", pady=(0, 8))
        self.m_proy = E.Menu(c, self.var["proyecto"], [], lambda: None, 30)
        self.m_proy.pack(fill="x")
        E.Boton(c, "Abrir proyecto", self.abrir_proyecto).pack(anchor="w", pady=(8, 0))
        m, c = E.tarjeta(p, "Zonas geoespaciales")
        m.pack(fill="x", pady=(0, 8))
        self.t_zonas = ttk.Treeview(c, columns=("tipo", "area"), show="tree headings", height=6, selectmode="browse")
        self.t_zonas.heading("#0", text="Zona", anchor="w")
        self.t_zonas.heading("tipo", text="Tipo", anchor="w")
        self.t_zonas.heading("area", text="ha", anchor="e")
        self.t_zonas.column("#0", width=130)
        self.t_zonas.column("tipo", width=110)
        self.t_zonas.column("area", width=50, anchor="e")
        self.t_zonas.pack(fill="x")
        self.t_zonas.bind("<<TreeviewSelect>>", self._zona_elegida)
        f = self._fila(c, "Tipo de zona nueva")
        E.Menu(f, self.var["tipo_zona"], [v[0] for v in C.TIPOS_ZONA.values()], lambda: None, 26).pack(fill="x")
        f = self._fila(c, "Nombre (opcional) y cota de piso de diseño en m (extracción)")
        g = tk.Frame(f, bg=P["tarjeta"])
        g.pack(fill="x")
        self._entrada(g, self.var["nombre_zona"], 20).pack(side="left", ipady=3)
        self._entrada(g, self.var["cota"], 9).pack(side="left", padx=6, ipady=3)
        b = tk.Frame(c, bg=P["tarjeta"])
        b.pack(fill="x", pady=(8, 0))
        self.b_dibujar = E.Boton(b, "Dibujar en el mapa", self.dibujar_zona)
        self.b_dibujar.pack(side="left")
        E.Boton(b, "Eliminar", self.eliminar_zona).pack(side="left", padx=6)
        b = tk.Frame(c, bg=P["tarjeta"])
        b.pack(fill="x", pady=(6, 0))
        E.Boton(b, "Importar GeoJSON", self.importar_geojson).pack(side="left")
        E.Boton(b, "Aplicar cota", self.aplicar_cota).pack(side="left", padx=6)
        E.etiqueta(c, "Dibujar: clic para cada vértice, doble clic o clic derecho para cerrar, Esc cancela.",
                   wraplength=320, justify="left").pack(anchor="w", pady=(6, 0))

    def _panel_vuelo(self, p):
        m, c = E.tarjeta(p, "Misión")
        m.pack(fill="x", pady=(0, 8))
        self.seg_mision = E.Segmentado(c, MISION_CORTA, "lidar", self._mision)
        self.seg_mision.pack(fill="x")
        f = self._fila(c, "Época del levantamiento")
        self.seg_epoca = E.Segmentado(f, [("A", "A · anterior"), ("B", "B · actual")], "B", self._epoca_vuelo)
        self.seg_epoca.pack(anchor="w")
        f = self._fila(c, "Sensor")
        self.m_sensor = E.Menu(f, self.var["sensor"], list(C.LIDAR), self.replanear, 30)
        self.m_sensor.pack(fill="x")
        f = self._fila(c, "Posicionamiento")
        E.Menu(f, self.var["posicion"], list(C.POSICIONAMIENTO), self.replanear, 16).pack(anchor="w")
        f = self._fila(c, "Área de vuelo")
        self.m_area = E.Menu(f, self.var["area"], ["Todo el sitio"], self.replanear, 30)
        self.m_area.pack(fill="x")
        m, c = E.tarjeta(p, "Parámetros")
        m.pack(fill="x", pady=(0, 8))
        self.deslizadores = {}
        for clave, txt, a, b, paso, fmt, uni in (("altura", "Altura sobre el terreno", 30, 160, 5, "{:.0f}", " m"),
                                                ("velocidad", "Velocidad", 3, 15, 0.5, "{:.1f}", " m/s"),
                                                ("tf", "Traslape frontal", 50, 90, 5, "{:.0f}", " %"),
                                                ("tl", "Traslape lateral / entre franjas", 10, 85, 5, "{:.0f}", " %"),
                                                ("drones", "Drones simultáneos", 1, 4, 1, "{:.0f}", ""),
                                                ("densidad", "Densidad simulada (para tu PC)", 1, 8, 0.5, "{:.1f}", " pts/m²"),
                                                ("rumbo", "Rumbo de las líneas", 0, 175, 5, "{:.0f}", "°")):
            f = self._fila(c, txt)
            self.deslizadores[clave] = E.Deslizador(f, self.var[clave], a, b, paso, self.replanear, 320, fmt, uni).pack(anchor="w")
        E.Interruptor(c, "Rumbo automático (menos líneas)", self.var["auto_rumbo"], self.replanear).pack(anchor="w", pady=(6, 2))
        E.Interruptor(c, "Seguir el terreno (altura constante)", self.var["seguir"], self.replanear).pack(anchor="w", pady=2)
        m, c = E.tarjeta(p, "Plan")
        m.pack(fill="x", pady=(0, 8))
        self.l_plan = tk.Label(c, text="Crea un sitio para planear", bg=P["tarjeta"], fg=P["texto"], font=E.F_CHICA,
                               justify="left", anchor="w", wraplength=320)
        self.l_plan.pack(fill="x")
        b = tk.Frame(c, bg=P["tarjeta"])
        b.pack(fill="x", pady=(10, 0))
        self.b_volar = E.Boton(b, "Volar", self.volar, primario=True, color=P["acento"])
        self.b_volar.pack(side="left")
        self.b_pausa = E.Boton(b, "Pausa", self._pausa)
        self.b_pausa.pack(side="left", padx=6)
        E.Boton(b, "Terminar ya", self.terminar_vuelo).pack(side="left")
        f = self._fila(c, "Velocidad de la simulación")
        self.seg_multi = E.Segmentado(f, [(10, "×10"), (30, "×30"), (100, "×100"), (300, "×300")], 30, self._multi)
        self.seg_multi.pack(anchor="w")
        E.Boton(c, "Exportar waypoints (CSV)", self.exportar_waypoints).pack(anchor="w", pady=(10, 0))

    def _panel_procesar(self, p):
        m, c = E.tarjeta(p, "Georreferenciación")
        m.pack(fill="x", pady=(0, 8))
        f = self._fila(c, "Puntos de control en tierra (GCP)")
        E.Deslizador(f, self.var["gcp"], 0, 12, 1, lambda: None, 320, "{:.0f}", "").pack(anchor="w")
        f = self._fila(c, "Puntos de verificación (checkpoints)")
        E.Deslizador(f, self.var["cps"], 8, 40, 2, self._nuevos_cps, 320, "{:.0f}", "").pack(anchor="w")
        E.Boton(c, "Reprocesar todo", self.reprocesar).pack(anchor="w", pady=(10, 0))
        m, c = E.tarjeta(p, "Productos")
        m.pack(fill="x", pady=(0, 8))
        self.l_productos = tk.Label(c, text="Aún no hay vuelos", bg=P["tarjeta"], fg=P["texto"], font=E.F_CHICA, justify="left",
                                    anchor="w", wraplength=320)
        self.l_productos.pack(fill="x")
        f = self._fila(c, "Curvas de nivel cada")
        self.seg_curvas = E.Segmentado(f, [(1.0, "1 m"), (2.0, "2 m"), (5.0, "5 m"), (10.0, "10 m")], 5.0, self._intervalo)
        self.seg_curvas.pack(anchor="w")
        E.etiqueta(c, "El LiDAR se clasifica con un filtro morfológico progresivo (suelo, vegetación baja/media/alta, "
                      "estructuras, ruido). La fotogrametría no ve el suelo bajo la vegetación. Con GNSS estándar sin "
                      "GCP los modelos tienen error de metros.", wraplength=320, justify="left").pack(anchor="w", pady=(8, 0))

    def _panel_analisis(self, p):
        m, c = E.tarjeta(p, "Comparación de épocas")
        m.pack(fill="x", pady=(0, 8))
        E.etiqueta(c, "Compara el modelo A con el B contra las zonas autorizadas, la cota de diseño, las zonas "
                      "restringidas y los acopios.", wraplength=320, justify="left").pack(anchor="w")
        f = self._fila(c, "Densidad del material")
        E.Deslizador(f, self.var["densidad_roca"], 1.4, 3.2, 0.05, lambda: None, 320, "{:.2f}", " t/m³").pack(anchor="w")
        E.Boton(c, "Comparar A vs B", self.comparar, primario=True, color=P["acento"]).pack(anchor="w", pady=(10, 0))
        m, c = E.tarjeta(p, "Seguridad operativa")
        m.pack(fill="x", pady=(0, 8))
        self.l_seguridad = tk.Label(c, text="Vuela Térmica y Visual en la época B para inspeccionar.", bg=P["tarjeta"],
                                    fg=P["texto"], font=E.F_CHICA, justify="left", anchor="w", wraplength=320)
        self.l_seguridad.pack(fill="x")
        E.Boton(c, "Analizar geometría", self.analizar_geometria).pack(anchor="w", pady=(8, 0))
        E.etiqueta(c, "Taludes más inclinados que el diseño, obstrucciones en caminos, agua sin retornos LiDAR y grietas.",
                   wraplength=320, justify="left").pack(anchor="w", pady=(6, 0))
        m, c = E.tarjeta(p, "Salidas")
        m.pack(fill="x", pady=(0, 8))
        for txt, fn in (("Exportar todo", self.exportar_todo), ("Abrir en Google Earth (KML)", self.google_earth),
                        ("Ver modelo 3D", self.modelo_3d), ("Abrir carpeta de exportaciones", self.abrir_exportaciones)):
            E.Boton(c, txt, fn).pack(anchor="w", pady=(0, 6))
        E.etiqueta(c, "Nube LAS (UTM), DTM/DSM/diferencia ASC, modelo 3D OBJ texturizado, GeoJSON, KML, waypoints CSV, "
                      "reporte de volúmenes y alertas, mapas PNG.", wraplength=320, justify="left").pack(anchor="w")

    def _panel_mapa(self, p):
        m, c = E.tarjeta(p)
        m.pack(fill="both", expand=True)
        barra = tk.Frame(c, bg=P["tarjeta"])
        barra.pack(fill="x", pady=(0, 6))
        E.Menu(barra, self.var["capa"], CAPAS, self._capa, 20).pack(side="left")
        self.seg_ver = E.Segmentado(barra, [("A", "A"), ("B", "B")], "B", self._ver_epoca)
        self.seg_ver.pack(side="left", padx=8)
        for clave, txt in (("ov_zonas", "Zonas"), ("ov_plan", "Vuelo"), ("ov_alertas", "Alertas"), ("ov_curvas", "Curvas"),
                           ("ov_control", "GCP")):
            E.Interruptor(barra, txt, self.var[clave], self.redibujar).pack(side="left", padx=(6, 0))
        E.Boton(barra, "⤢", self.ajustar).pack(side="right")
        self.cv = tk.Canvas(c, bg="#0b0d10", highlightthickness=0, cursor="crosshair")
        self.cv.pack(fill="both", expand=True)
        self.cv.bind("<Configure>", lambda e: self.redibujar(True))
        self.cv.bind("<MouseWheel>", self._zoom)
        self.cv.bind("<ButtonPress-1>", self._presionar)
        self.cv.bind("<B1-Motion>", self._arrastrar)
        self.cv.bind("<ButtonRelease-1>", self._soltar)
        self.cv.bind("<Double-Button-1>", lambda e: self._cerrar_zona())
        self.cv.bind("<Button-3>", lambda e: self._cerrar_zona())
        self.cv.bind("<Motion>", self._mover)
        self.raiz.bind("<Escape>", lambda e: self._cancelar_dibujo())
        pie = tk.Frame(c, bg=P["tarjeta"])
        pie.pack(fill="x", pady=(6, 0))
        self.l_estado = tk.Label(pie, text="", bg=P["tarjeta"], fg=P["tenue"], font=E.F_CHICA, anchor="w")
        self.l_estado.pack(side="left", fill="x", expand=True)
        self.l_coord = tk.Label(pie, text="", bg=P["tarjeta"], fg=P["tenue"], font=E.F_MONO, anchor="e")
        self.l_coord.pack(side="right")
        self.cv_prog = tk.Canvas(c, height=4, bg=P["tarjeta"], highlightthickness=0)
        self.cv_prog.pack(fill="x", pady=(4, 0))

    def _panel_derecho(self, p):
        m, c = E.tarjeta(p, "Indicadores")
        m.pack(fill="x", pady=(0, 8))
        self.cv_ind = tk.Canvas(c, height=170, bg=P["tarjeta"], highlightthickness=0)
        self.cv_ind.pack(fill="x")
        self.cv_ind.bind("<Configure>", lambda e: self._indicadores())
        m, c = E.tarjeta(p, "Resultados")
        m.pack(fill="both", expand=True, pady=(0, 8))
        self.seg_res = E.Segmentado(c, [("alertas", "Alertas"), ("volumenes", "Volúmenes"), ("precision", "Precisión")],
                                    "alertas", self._vista_resultados)
        self.seg_res.pack(fill="x", pady=(0, 6))
        self.tabla = ttk.Treeview(c, columns=("a", "b", "c"), show="headings", height=12, selectmode="browse")
        self.tabla.pack(fill="both", expand=True)
        self.tabla.bind("<<TreeviewSelect>>", self._fila_elegida)
        for sev, col in SEV_COLOR.items():
            self.tabla.tag_configure(sev, foreground=col)
        self.l_detalle = tk.Label(c, text="", bg=P["tarjeta"], fg=P["texto"], font=E.F_CHICA, justify="left", anchor="nw",
                                  wraplength=370, height=5)
        self.l_detalle.pack(fill="x", pady=(6, 0))
        m, c = E.tarjeta(p, "Bitácora")
        m.pack(fill="x")
        self.t_log = tk.Text(c, height=7, bg=P["tarjeta"], fg=P["tenue"], font=E.F_CHICA, relief="flat", wrap="word",
                             highlightthickness=0)
        self.t_log.pack(fill="x")
        self.t_log.configure(state="disabled")

    def log(self, texto, color=None):
        self.t_log.configure(state="normal")
        self.t_log.insert("end", time.strftime("%H:%M:%S  ") + texto + "\n")
        self.t_log.see("end")
        self.t_log.configure(state="disabled")
        self.l_estado.configure(text=texto, fg=color or P["tenue"])

    def _tarea(self, texto, fn, al_terminar=None):
        if self.ocupado:
            self.log("Espera a que termine la tarea en curso", P["naranja"])
            return
        self.ocupado = True
        self.log(texto)

        def correr():
            try:
                res = fn(lambda m: self.cola.put(("log", m)))
                self.cola.put(("hecho", al_terminar, res))
            except Exception as ex:
                traceback.print_exc()
                self.cola.put(("error", str(ex)))
        threading.Thread(target=correr, daemon=True).start()

    def _bucle(self):
        try:
            while True:
                tipo, *datos = self.cola.get_nowait()
                if tipo == "log":
                    self.log(datos[0])
                elif tipo == "previa":
                    self._mostrar_previa(*datos)
                elif tipo == "hecho":
                    self.ocupado = False
                    if datos[0]:
                        datos[0](datos[1])
                elif tipo == "error":
                    self.ocupado = False
                    if getattr(self, "_previa", None) is not None:
                        self._previa = None
                        self.redibujar(True)
                    self.log("Error: " + datos[0], P["rojo"])
        except queue.Empty:
            pass
        if self.sim is not None and not self.pausa and not self.sim.terminada:
            self.sim.avanzar(0.06 * self.var["multi"])
            self._dibujar_drones()
            self._progreso(self.sim.t / max(self.sim.duracion, 1))
            if self.sim.terminada:
                self._fin_vuelo()
        self.raiz.after(60, self._bucle)

    def _mostrar_previa(self, georef, rgb):
        self._previa = (georef, Image.fromarray(rgb))
        cv = self.cv
        w, h = max(cv.winfo_width(), 50), max(cv.winfo_height(), 50)
        lado = min(w, h) - 8
        self._foto_previa = ImageTk.PhotoImage(self._previa[1].resize((lado, lado), Image.BILINEAR))
        cv.delete("all")
        cv.create_image(w / 2, h / 2, image=self._foto_previa, tags="fondo")
        self._cajas = []
        coords = f"{georef.lat:.5f}, {georef.lon:.5f}"
        nombre = georef.nombre if georef.nombre and georef.nombre != coords else ""
        self._chip(w / 2, 14, (nombre + " · " if nombre else "") + coords + " · preparando el sitio…",
                   P["acento"], "n", tags=("previa",))
        self.log("Imagen satelital lista; terminando la elevación y las capas…", P["verde"])

    def _progreso(self, f):
        self.cv_prog.delete("all")
        w = self.cv_prog.winfo_width()
        self.cv_prog.create_rectangle(0, 0, w * max(0, min(1, f)), 4, fill=P["acento"], outline="")

    def _inicio(self):
        self._listar_proyectos()
        ultimo = os.path.join(C.CARPETA_PROYECTOS, "ultimo.txt")
        try:
            with open(ultimo, encoding="utf-8") as f:
                carpeta = f.read().strip()
            if os.path.exists(os.path.join(carpeta, "sitio.json")):
                self._abrir(carpeta)
                return
        except OSError:
            pass
        self.crear_sitio(False, respaldo=True)

    def _listar_proyectos(self):
        os.makedirs(C.CARPETA_PROYECTOS, exist_ok=True)
        nombres = sorted(d for d in os.listdir(C.CARPETA_PROYECTOS) if os.path.exists(os.path.join(C.CARPETA_PROYECTOS, d, "sitio.json")))
        self.m_proy.opciones(nombres)
        if nombres and not self.var["proyecto"].get():
            self.var["proyecto"].set(nombres[0])

    def _elegir_mina(self):
        v = C.MINAS[self.var["mina"].get()]
        if v:
            self.var["tamano"].set(v[2])
            self.var["lugar"].set("")

    def crear_sitio(self, buscar=False, respaldo=False):
        texto = self.var["lugar"].get().strip()
        mina = self.var["mina"].get()
        tam = C.TAMANOS[self.var["tamano"].get()]
        opciones = {"fuera_de_zona": self.var["fuera"].get(), "sobre_excavacion": self.var["sobre"].get()}
        osm = self.var["osm"].get()

        def guardar(sitio):
            carpeta = os.path.join(C.CARPETA_PROYECTOS, _clave(sitio.nombre) + f"_{int(sitio.ancho)}")
            self.cola.put(("log", "Guardando el proyecto…"))
            sitio.guardar(carpeta)
            return sitio, carpeta

        def tarea(avisar):
            previa = lambda georef, rgb: self.cola.put(("previa", georef, rgb))
            if buscar and texto:
                lugar = G.buscar_lugar(texto)
                avisar(f"Lugar: {lugar['nombre']} ({lugar['lat']:.5f}, {lugar['lon']:.5f})")
                s = T.crear_real(lugar["lat"], lugar["lon"], lugar["nombre"], tam, avisar=avisar, opciones=opciones,
                                 usar_osm=osm, previa=previa)
                return guardar(s)
            v = C.MINAS.get(mina)
            if v is None:
                return guardar(T.crear_demo(tam, avisar=avisar, opciones=opciones))
            try:
                return guardar(T.crear_real(v[0], v[1], mina, tam, avisar=avisar, opciones=opciones, usar_osm=osm, previa=previa))
            except Exception as ex:
                if not respaldo:
                    raise
                avisar(f"No se pudo descargar {mina} ({ex}); se crea la mina demostración")
                return guardar(T.crear_demo(C.TAMANOS[C.TAMANO_DEFECTO], avisar=avisar, opciones=opciones))

        def fin(res):
            sitio, carpeta = res
            self._previa = None
            self._activar(sitio, carpeta)
            self.log(f"Sitio listo: {sitio.nombre}", P["verde"])
            self._listar_proyectos()
            if sitio.real and G.clave_google():
                self.raiz.after(100, self.google_maps)

        self._tarea("Creando sitio…" if not (buscar and texto) else f"Buscando «{texto}»…", tarea, fin)

    def abrir_proyecto(self):
        n = self.var["proyecto"].get()
        if n:
            self._abrir(os.path.join(C.CARPETA_PROYECTOS, n))

    def _abrir(self, carpeta):
        def tarea(avisar):
            avisar("Abriendo proyecto…")
            s = T.Sitio.cargar(carpeta)
            return s, self._cargar_productos(carpeta)

        def fin(res):
            s, guardado = res
            self._activar(s, carpeta)
            if guardado:
                self.prod, self.prec, self.termica, self.visual, self.geom, self.comp = guardado
                self._despues_de_procesar()
            self.log(f"Proyecto abierto: {s.nombre}", P["verde"])
        self._tarea("Abriendo proyecto…", tarea, fin)

    def _activar(self, sitio, carpeta):
        self.sitio, self.carpeta = sitio, carpeta
        with open(os.path.join(C.CARPETA_PROYECTOS, "ultimo.txt"), "w", encoding="utf-8") as f:
            f.write(carpeta)
        self.vuelos, self.prod, self.prec, self.termica, self.visual, self.geom = {}, {}, {}, {}, {}, {}
        self.comp, self.sim, self.curvas, self._cache, self.seleccion = None, None, {}, {}, None
        self.checkpoints = PR.puntos_control(sitio, int(self.var["cps"].get()), 11)
        self.gcps = PR.puntos_control(sitio, 12, 23)
        g = sitio.georef
        e, n = g.a_utm(g.ancho / 2, g.alto / 2)
        zona = f"{g.zona_utm[0]}{'N' if g.zona_utm[1] else 'S'}"
        self.l_sitio.configure(text=f"{sitio.nombre} · {g.lat:.5f}, {g.lon:.5f} · UTM {zona} {float(e):.0f} E {float(n):.0f} N · "
                                    f"{sitio.ancho / 1000:.1f} × {sitio.ancho / 1000:.1f} km · celda {sitio.res:.2f} m")
        for nota in sitio.notas:
            self.log(nota, P["acento"])
        self._zonas_tabla()
        self.vista = None
        self.replanear()
        self.redibujar(True)
        self._indicadores()
        self._vista_resultados(self.seg_res.valor)
        self._productos_texto()

    def _zonas_tabla(self):
        self.t_zonas.delete(*self.t_zonas.get_children())
        for k, z in enumerate(self.sitio.zonas):
            self.t_zonas.insert("", "end", iid=str(k), text=z["nombre"], values=(C.TIPOS_ZONA[z["tipo"]][0], f"{T.area_poligono(z['puntos']) / 1e4:.1f}"))
        self.m_area.opciones(["Todo el sitio"] + [z["nombre"] for z in self.sitio.zonas])
        if self.var["area"].get() not in ["Todo el sitio"] + [z["nombre"] for z in self.sitio.zonas]:
            self.var["area"].set("Todo el sitio")

    def _zona_elegida(self, e=None):
        sel = self.t_zonas.selection()
        if not sel:
            return
        z = self.sitio.zonas[int(sel[0])]
        self.var["nombre_zona"].set(z["nombre"])
        self.var["cota"].set("" if z.get("cota_piso") is None else f"{z['cota_piso']:.1f}")
        self.seleccion = ("zona", int(sel[0]))
        self.redibujar()

    def dibujar_zona(self):
        if self.sitio is None:
            return
        self.dibujando = []
        self.b_dibujar.texto("Dibujando… (clic derecho cierra)")
        self.log("Haz clic en el mapa para cada vértice; doble clic o clic derecho para cerrar", P["acento"])

    def _cancelar_dibujo(self):
        if self.dibujando is not None:
            self.dibujando = None
            self.b_dibujar.texto("Dibujar en el mapa")
            self.redibujar()

    def _cerrar_zona(self):
        if self.dibujando is None:
            return
        pts = self.dibujando
        self.dibujando = None
        self.b_dibujar.texto("Dibujar en el mapa")
        if len(pts) < 3:
            self.log("Se necesitan al menos 3 vértices", P["naranja"])
            self.redibujar()
            return
        tipo = next(k for k, v in C.TIPOS_ZONA.items() if v[0] == self.var["tipo_zona"].get())
        nombre = self.var["nombre_zona"].get().strip() or f"{C.TIPOS_ZONA[tipo][0]} {len(self.sitio.zonas) + 1}"
        z = {"nombre": nombre, "tipo": tipo, "puntos": [list(map(float, p)) for p in pts]}
        if tipo == "extraccion":
            try:
                z["cota_piso"] = float(self.var["cota"].get())
            except ValueError:
                m = self.sitio.mascara(z["puntos"])
                z["cota_piso"] = round(float(self.sitio.epocas["A"]["dtm"][m].min()) - 15, 1) if m.any() else None
        self.sitio.zonas.append(z)
        self.sitio.guardar(self.carpeta)
        self._zonas_tabla()
        self.log(f"Zona agregada: {nombre} ({T.area_poligono(z['puntos']) / 1e4:.2f} ha)", P["verde"])
        self.redibujar()

    def eliminar_zona(self):
        sel = self.t_zonas.selection()
        if not sel or self.sitio is None:
            return
        z = self.sitio.zonas.pop(int(sel[0]))
        self.sitio.guardar(self.carpeta)
        self._zonas_tabla()
        self.seleccion = None
        self.log(f"Zona eliminada: {z['nombre']}")
        self.redibujar()

    def aplicar_cota(self):
        sel = self.t_zonas.selection()
        if not sel:
            return
        z = self.sitio.zonas[int(sel[0])]
        try:
            z["cota_piso"] = float(self.var["cota"].get())
        except ValueError:
            self.log("Escribe la cota en metros", P["naranja"])
            return
        nombre = self.var["nombre_zona"].get().strip()
        if nombre:
            z["nombre"] = nombre
        self.sitio.guardar(self.carpeta)
        self._zonas_tabla()
        self.log(f"{z['nombre']}: cota de diseño {z['cota_piso']:.1f} m")

    def importar_geojson(self):
        if self.sitio is None:
            return
        ruta = filedialog.askopenfilename(filetypes=[("GeoJSON", "*.geojson *.json")])
        if not ruta:
            return
        with open(ruta, encoding="utf-8") as f:
            datos = json.load(f)
        n = 0
        for ft in datos.get("features", []):
            g = ft.get("geometry") or {}
            polis = [g["coordinates"]] if g.get("type") == "Polygon" else g.get("coordinates", []) if g.get("type") == "MultiPolygon" else []
            for pol in polis:
                anillo = np.asarray(pol[0], dtype=float)
                x, y = self.sitio.georef.a_local(anillo[:, 1], anillo[:, 0])
                props = ft.get("properties") or {}
                tipo = next((k for k, v in C.TIPOS_ZONA.items() if v[0] == props.get("tipo") or k == props.get("tipo")), "extraccion")
                z = {"nombre": props.get("nombre") or props.get("name") or f"Zona importada {n + 1}", "tipo": tipo,
                     "puntos": np.column_stack([x, y])[:-1].round(2).tolist()}
                if props.get("cota_piso") is not None:
                    z["cota_piso"] = float(props["cota_piso"])
                self.sitio.zonas.append(z)
                n += 1
        self.sitio.guardar(self.carpeta)
        self._zonas_tabla()
        self.redibujar()
        self.log(f"{n} zonas importadas de {os.path.basename(ruta)}", P["verde"])

    def _mision(self, m):
        self.seg_mision.poner(m)
        self.var["mision"] = m
        if m == "lidar":
            opciones = list(C.LIDAR)
            alt, tl = 90, 45
        else:
            opciones = [k for k, v in C.CAMARAS.items() if (v["tipo"] == "termica") == (m == "termica")]
            alt, tl = {"fotogrametria": (100, 70), "termica": (100, 60), "visual": (60, 60)}[m]
        self.m_sensor.opciones(opciones)
        if self.var["sensor"].get() not in opciones:
            self.var["sensor"].set(opciones[0])
        self.var["altura"].set(alt)
        self.var["tl"].set(tl)
        for d in self.deslizadores.values():
            d._pintar()
        if m in ("termica", "visual"):
            self.seg_epoca.poner("B")
            self.var["epoca"] = "B"
        self.replanear()

    def _epoca_vuelo(self, e):
        self.seg_epoca.poner(e)
        self.var["epoca"] = e
        self.replanear()

    def _multi(self, v):
        self.seg_multi.poner(v)
        self.var["multi"] = v

    def _params(self):
        area = None
        nombre = self.var["area"].get()
        if nombre != "Todo el sitio":
            z = next((z for z in self.sitio.zonas if z["nombre"] == nombre), None)
            if z:
                area = z["puntos"]
        return {"altura": self.var["altura"].get(), "velocidad": self.var["velocidad"].get(), "traslape_f": self.var["tf"].get() / 100,
                "traslape_l": self.var["tl"].get() / 100, "drones": int(self.var["drones"].get()), "sensor": self.var["sensor"].get(),
                "seguir_terreno": self.var["seguir"].get(), "angulo": None if self.var["auto_rumbo"].get() else self.var["rumbo"].get(),
                "area": area}

    def replanear(self):
        if self.sitio is None or self.sim is not None and not self.sim.terminada:
            return
        try:
            self.plan = PL.planear(self.sitio, self.var["epoca"], self.var["mision"], self._params())
        except Exception as ex:
            self.l_plan.configure(text=f"No se pudo planear: {ex}")
            return
        texto = "\n".join(PL.resumen(self.plan))
        if self.var["mision"] == "lidar":
            st = self.plan["stats"]
            texto += f"\nSimulación: {self.var['densidad'].get():.1f} pts/m² (≈ {st['area_ha'] * 1e4 * self.var['densidad'].get() / 1e6:.1f} M puntos)"
        self.l_plan.configure(text=texto)
        self.redibujar()

    def volar(self):
        if self.sitio is None or self.plan is None or self.ocupado:
            return
        if self.sim is not None and not self.sim.terminada:
            return
        self.sim = SE.Simulacion(self.sitio, self.plan, self.var["epoca"], self.var["posicion"].get(), self.var["densidad"].get(),
                                 semilla=int(time.time()) % 10000)
        self.pausa = False
        self.log(f"Despegue: {C.MISIONES[self.plan['tipo']]} · época {self.var['epoca']} · {len(self.sim.salidas)} vuelos")
        self.var["ov_plan"].set(True)

    def _pausa(self):
        self.pausa = not self.pausa
        self.b_pausa.texto("Seguir" if self.pausa else "Pausa")

    def terminar_vuelo(self):
        if self.sim is None or self.sim.terminada or self.ocupado:
            return
        sim = self.sim

        def tarea(avisar):
            sim.terminar(lambda f: avisar(f"Completando vuelo… {f * 100:.0f}%"))
            return True
        self._tarea("Completando el vuelo sin animación…", tarea, lambda r: self._fin_vuelo())

    def _fin_vuelo(self):
        sim = self.sim
        r = sim.resultado()
        ep, tipo = r["epoca"], r["tipo"]
        self.vuelos[(ep, tipo)] = r
        extra = f" · {sim.n_puntos:,} puntos".replace(",", " ") if sim.lidar is not None else f" · {len(sim.capturas)} fotos"
        self.log(f"Vuelo terminado ({sim.duracion / 60:.0f} min de operación){extra}", P["verde"])
        self._progreso(1.0)
        self._dibujar_drones()
        self.procesar(ep, tipo)

    def _nuevos_cps(self):
        if self.sitio is not None:
            self.checkpoints = PR.puntos_control(self.sitio, int(self.var["cps"].get()), 11)
            self.redibujar()

    def procesar(self, ep, tipo, encadenar=None):
        r = self.vuelos.get((ep, tipo))
        if r is None:
            return
        gcp = int(self.var["gcp"].get())
        sitio = self.sitio
        cps = self.checkpoints

        def tarea(avisar):
            if tipo == "lidar":
                prod = PR.procesar_lidar(sitio, r, gcp, avisar=avisar)
                return ("lidar", prod, PR.precision(sitio, prod, ep, cps))
            if tipo == "fotogrametria":
                prod = PR.procesar_fotos(sitio, r, gcp, avisar=avisar)
                return ("foto", prod, PR.precision(sitio, prod, ep, cps))
            if tipo == "termica":
                avisar("Analizando termografía…")
                return ("termica", PR.termografia(sitio, r), None)
            avisar("Analizando fotos de inspección…")
            return ("visual", PR.inspeccion_visual(sitio, r), None)

        def fin(res):
            clase, prod, prec = res
            if clase in ("lidar", "foto"):
                self.prod[(ep, clase)] = prod
                self.prec[(ep, clase)] = prec
                self.curvas.pop(ep, None)
                if prec:
                    self.log(f"Modelo {prod['metodo']} época {ep}: RMSE Z {prec['rmse_z'] * 100:.1f} cm · XY {prec['rmse_h'] * 100:.1f} cm "
                             f"({prec['n']} checkpoints, {gcp} GCP)", P["verde"])
                if ("A", "lidar") in self.prod or ("A", "foto") in self.prod:
                    if ("B", "lidar") in self.prod or ("B", "foto") in self.prod:
                        self.comp = None
            elif clase == "termica":
                self.termica[ep] = prod
                n = sum(a["severidad"] != "info" for a in prod["alertas"])
                self.log(f"Termografía: {n} anomalías, {len(prod['alertas']) - n} equipos en operación", P["verde"])
            else:
                self.visual[ep] = prod
                self.log(f"Inspección visual: {len(prod['alertas'])} hallazgos", P["verde"])
            self._despues_de_procesar()
            self._guardar_productos()
            if encadenar:
                encadenar()
        self._tarea(f"Procesando {C.MISIONES[tipo].lower()} de la época {ep}…", tarea, fin)

    def reprocesar(self):
        pendientes = [k for k in self.vuelos]

        def siguiente():
            if pendientes:
                ep, tipo = pendientes.pop(0)
                self.procesar(ep, tipo, siguiente)
        siguiente()

    def _mejor(self, ep):
        return self.prod.get((ep, "lidar")) or self.prod.get((ep, "foto"))

    def _mejor_prec(self, ep):
        return self.prec.get((ep, "lidar")) if (ep, "lidar") in self.prod else self.prec.get((ep, "foto"))

    def comparar(self):
        a, b = self._mejor("A"), self._mejor("B")
        if a is None or b is None:
            faltan = [e for e, p in (("A", a), ("B", b)) if p is None]
            self.log(f"Falta el levantamiento de la época {' y '.join(faltan)} (vuela LiDAR o fotogrametría)", P["naranja"])
            self._tab("vuelo")
            if faltan:
                self._epoca_vuelo(faltan[0])
            return
        C.DENSIDAD_ROCA = self.var["densidad_roca"].get()
        sitio = self.sitio
        pa, pb = self._mejor_prec("A"), self._mejor_prec("B")

        def tarea(avisar):
            avisar("Calculando diferencia de modelos y volúmenes…")
            comp = PR.comparar(sitio, a, b, pa, pb)
            avisar("Revisando taludes, caminos, agua y grietas…")
            geom = PR.analisis_geometrico(sitio, b, "B", a)
            return comp, geom

        def fin(res):
            self.comp, self.geom["B"] = res
            ext = sum(z["corte"] for z in self.comp["zonas"] if z["tipo"] == "extraccion")
            self.log(f"Comparación lista: {ext:,.0f} m³ extraídos en zonas autorizadas · {self.comp['fuera']:,.0f} m³ fuera · "
                     f"nivel de detección {self.comp['lod']:.2f} m".replace(",", " "), P["verde"])
            self.var["capa"].set("Diferencia A/B")
            self._cache.clear()
            self._despues_de_procesar()
            self._guardar_productos()
            self._vista_resultados("volumenes")
        self._tarea("Comparando épocas…", tarea, fin)

    def analizar_geometria(self):
        p = self._mejor("B")
        if p is None:
            self.log("Primero vuela LiDAR o fotogrametría en la época B", P["naranja"])
            return
        sitio = self.sitio
        previo = self._mejor("A")
        self._tarea("Analizando geometría…", lambda av: PR.analisis_geometrico(sitio, p, "B", previo),
                    lambda g: (self.geom.__setitem__("B", g), self._despues_de_procesar(), self._guardar_productos()))

    def alertas(self):
        lista = []
        for d in (self.visual.get("B"), self.termica.get("B"), self.geom.get("B")):
            if d:
                lista += d["alertas"]
        if self.comp:
            lista += self.comp["alertas"]
        return sorted(PR.deduplicar(lista), key=lambda a: ORDEN_SEV.get(a["severidad"], 9))

    def _despues_de_procesar(self):
        self._cache.clear()
        self._productos_texto()
        self._seguridad_texto()
        self._indicadores()
        self._vista_resultados(self.seg_res.valor)
        self.redibujar(True)

    def _productos_texto(self):
        if self.sitio is None:
            return
        lineas = []
        for ep in ("A", "B"):
            partes = []
            for clase, nombre in (("lidar", "LiDAR"), ("foto", "Fotogrametría")):
                p, pr = self.prod.get((ep, clase)), self.prec.get((ep, clase))
                if p is None:
                    continue
                t = nombre
                if clase == "lidar" and "x" in p:
                    t += f" {len(p['x']) / 1e6:.1f} M pts, {float(np.median(p['densidad'][p['densidad'] > 0])):.1f} pts/m²"
                if pr:
                    t += f" · RMSE Z {pr['rmse_z'] * 100:.1f} cm"
                partes.append(t)
            if ep in self.termica:
                partes.append("térmica")
            if ep in self.visual:
                partes.append("visual")
            lineas.append(f"Época {ep}: " + (" · ".join(partes) if partes else "sin vuelos"))
        self.l_productos.configure(text="\n".join(lineas))

    def _seguridad_texto(self):
        al = self.alertas()
        if not al:
            self.l_seguridad.configure(text="Sin alertas todavía. Vuela Térmica y Visual en B y compara épocas.")
            return
        cuenta = {}
        for a in al:
            cuenta[a["severidad"]] = cuenta.get(a["severidad"], 0) + 1
        self.l_seguridad.configure(text=" · ".join(f"{v} {k}" for k, v in sorted(cuenta.items(), key=lambda kv: ORDEN_SEV.get(kv[0], 9)))
                                   + "\nLa lista completa está en el panel de resultados.")

    def _indicadores(self):
        cv = self.cv_ind
        w = cv.winfo_width()
        if w < 50 or self.sitio is None:
            return
        s = self.sitio
        dtm = s.epocas["B"]["dtm"]
        b = self._mejor("B")
        pr = self._mejor_prec("B")
        al = self.alertas()
        criticas = sum(a["severidad"] == "crítica" for a in al)
        ext = sum(z["corte"] for z in self.comp["zonas"] if z["tipo"] == "extraccion") if self.comp else None
        datos = [("Área", f"{s.ancho ** 2 / 1e4:.0f} ha", P["azul"], None),
                 ("Desnivel", f"{float(np.ptp(dtm)):.0f} m", P["cian"], None),
                 ("Puntos LiDAR B", f"{len(b['x']) / 1e6:.1f} M" if b is not None and "x" in b else "—", P["morado"], None),
                 ("RMSE Z (B)", f"{pr['rmse_z'] * 100:.1f} cm" if pr else "—",
                  P["verde"] if pr and pr["rmse_z"] < 0.1 else P["naranja"], None),
                 ("Extraído A→B", f"{ext / 1000:,.1f} mil m³".replace(",", " ") if ext is not None else "—", P["acento"], None),
                 ("Alertas", f"{len(al)} ({criticas} críticas)" if al else "—", P["rojo"] if criticas else P["gris"], None)]
        E.indicadores(cv, datos, 2, w, 50)

    def _vista_resultados(self, v):
        self.seg_res.poner(v)
        t = self.tabla
        t.delete(*t.get_children())
        self.l_detalle.configure(text="")
        if v == "alertas":
            cols = (("a", "Severidad", 70), ("b", "Alerta", 210), ("c", "Fuente", 110))
            self._filas = self.alertas()
            for k, a in enumerate(self._filas):
                t.insert("", "end", iid=str(k), values=(a["severidad"], a["titulo"], a.get("fuente", "").split(" (")[0]),
                         tags=(a["severidad"],))
        elif v == "volumenes":
            cols = (("a", "Zona", 160), ("b", "Corte / relleno m³", 140), ("c", "Toneladas", 90))
            self._filas = []
            if self.comp:
                for z in self.comp["zonas"]:
                    vol = f"−{z['corte']:,.0f} / +{z['relleno']:,.0f}".replace(",", " ")
                    if z["tipo"] == "acopio":
                        vol = f"{z['vol_a']:,.0f} → {z['vol_b']:,.0f}".replace(",", " ")
                    ton = "—" if z["tipo"] == "acopio" else f"{max(0.0, z['ton']):,.0f}".replace(",", " ")
                    t.insert("", "end", iid=str(len(self._filas)), values=(z["nombre"], vol, ton))
                    self._filas.append(("zona", z))
                t.insert("", "end", iid=str(len(self._filas)),
                         values=("Total del sitio", f"−{self.comp['corte']:,.0f} / +{self.comp['relleno']:,.0f}".replace(",", " "), ""))
                self._filas.append(("total", self.comp))
        else:
            cols = (("a", "Época / método", 140), ("b", "RMSE Z · XY", 140), ("c", "Puntos", 80))
            self._filas = []
            for (ep, clase), pr in sorted(self.prec.items()):
                if pr:
                    t.insert("", "end", iid=str(len(self._filas)), values=(f"{ep} · {self.prod[(ep, clase)]['metodo']}",
                                                                             f"{pr['rmse_z'] * 100:.1f} · {pr['rmse_h'] * 100:.1f} cm", pr["n"]))
                    self._filas.append(("prec", pr))
        for c, txt, w in cols:
            t.heading(c, text=txt, anchor="w")
            t.column(c, width=w, anchor="w")

    def _fila_elegida(self, e=None):
        sel = self.tabla.selection()
        if not sel:
            return
        f = self._filas[int(sel[0])]
        if self.seg_res.valor == "alertas":
            a = f
            la, lo = self.sitio.georef.a_latlon(a["x"], a["y"])
            ee, nn = self.sitio.georef.a_utm(a["x"], a["y"])
            self.l_detalle.configure(text=f"{a['titulo']}\n{a.get('detalle', '')}\nFuente: {a.get('fuente', '')}\n"
                                          f"{float(la):.6f}, {float(lo):.6f} · UTM {float(ee):.1f} E {float(nn):.1f} N")
            self.seleccion = ("alerta", a)
            self._centrar(a["x"], a["y"], 4.0)
        elif f[0] == "zona":
            z = f[1]
            txt = f"{z['nombre']} ({C.TIPOS_ZONA[z['tipo']][0]})\nCorte {z['corte']:,.0f} m³ · relleno {z['relleno']:,.0f} m³ · neto {z['neto']:,.0f} m³\n"
            if "bajo_cota_area" in z:
                txt += f"Piso medido {z['piso_b']:.1f} m · bajo cota: {z['bajo_cota_area']:.0f} m²\n"
            if "vol_a" in z:
                txt += f"Volumen del acopio: A {z['vol_a']:,.0f} m³ → B {z['vol_b']:,.0f} m³ (altura {z['alto_b']:.1f} m)\n"
            self.l_detalle.configure(text=txt.replace(",", " "))
        elif f[0] == "total":
            c = f[1]
            self.l_detalle.configure(text=(f"Corte total {c['corte']:,.0f} m³ · relleno {c['relleno']:,.0f} m³\n"
                                           f"Fuera de zonas autorizadas: {c['fuera']:,.0f} m³\nNivel de detección: {c['lod']:.2f} m · "
                                           f"modelos {c['metodos'][0]} → {c['metodos'][1]}").replace(",", " "))
        else:
            pr = f[1]
            peores = sorted(pr["errores"], key=lambda e: -abs(e["dz"]))[:4]
            self.l_detalle.configure(text=f"Media Z {pr['media_z'] * 100:+.1f} cm · máx {pr['max_z'] * 100:.1f} cm\nPeores: "
                                          + ", ".join(f"{e['id']} {e['dz'] * 100:+.1f} cm" for e in peores))
        self.redibujar()

    def _capa_rgb(self, nombre, ep):
        clave = (nombre, ep)
        if clave in self._cache:
            return self._cache[clave]
        s = self.sitio
        p = self._mejor(ep)
        rgb, aviso = None, None
        if nombre == "Imagen del sitio":
            rgb = s.epocas[ep]["color"]
        elif nombre == GOOGLE:
            g = self.google.get(self.carpeta)
            if g is not None:
                rgb = g[0]
            elif not s.real:
                aviso = "La mina demostración es ficticia: elige una mina real o busca un lugar en la pestaña Sitio"
            else:
                aviso = "Presiona «Google Maps» arriba para cargar el satélite de Google"
        elif nombre == "Ortomosaico (dron)":
            f = self.prod.get((ep, "foto"))
            rgb, aviso = (f["orto"], None) if f else (None, "Vuela fotogrametría para el ortomosaico")
        elif nombre in ("Relieve sombreado", "Hipsométrico (DTM)", "Pendientes"):
            dtm = p["dtm"] if p is not None else s.epocas[ep]["dtm"]
            if p is None:
                aviso = "Mostrando el terreno de referencia: vuela LiDAR o fotogrametría para el modelo medido"
            if nombre == "Relieve sombreado":
                rgb = CA.sombreado(s, dtm)
            elif nombre == "Hipsométrico (DTM)":
                rgb = CA.hipsometrico(s, dtm)
            else:
                rgb = CA.pendiente(s, dtm)[0]
        elif nombre == "Densidad LiDAR":
            l = self.prod.get((ep, "lidar"))
            rgb, aviso = (CA.densidad(l["densidad"])[0], None) if l else (None, "Vuela LiDAR para ver la densidad")
        elif nombre == "Cobertura de fotos":
            r = next((self.vuelos.get((ep, t)) for t in ("fotogrametria", "visual", "termica") if (ep, t) in self.vuelos), None)
            if r is not None:
                rgb = CA.cobertura(np.kron(r["cobertura"], np.ones((4, 4), np.uint16))[:s.ny, :s.nx].astype(np.float32))
            else:
                aviso = "Vuela una misión con cámara para ver la cobertura"
        elif nombre == "Diferencia A/B":
            if self.comp:
                rgb = CA.diferencia(s, self.comp["dod"], self._mejor("B")["dtm"], lod=self.comp["lod"])[0]
            else:
                aviso = "Compara las épocas en la pestaña Análisis"
        elif nombre == "Térmica":
            t = self.termica.get(ep)
            if t:
                rgb = CA.termico(t["mapa"])[0]
            else:
                aviso = f"Vuela la misión térmica en la época {ep}"
        if rgb is None:
            rgb = (s.epocas[ep]["color"].astype(np.float32) * 0.35).astype(np.uint8)
        img = Image.fromarray(rgb)
        self._cache[clave] = (img, aviso)
        return img, aviso

    def _capa(self):
        self.redibujar(True)

    def _ver_epoca(self, e):
        self.seg_ver.poner(e)
        self.var["ver_epoca"] = e
        self.redibujar(True)

    def _intervalo(self, v):
        self.seg_curvas.poner(v)
        self.var["intervalo"] = v
        self.curvas.clear()
        self.var["ov_curvas"].set(True)
        self.redibujar()

    def ajustar(self):
        self.vista = None
        self.redibujar(True)

    def _vista(self):
        w, h = max(self.cv.winfo_width(), 50), max(self.cv.winfo_height(), 50)
        if self.vista is None:
            esc = min(w, h) / self.sitio.ancho * 0.98
            self.vista = [self.sitio.ancho / 2, self.sitio.ancho / 2, esc]
        return w, h

    def a_canvas(self, x, y):
        w, h = self._vista()
        cx, cy, esc = self.vista
        return (np.asarray(x) - cx) * esc + w / 2, -(np.asarray(y) - cy) * esc + h / 2

    def a_mundo(self, px, py):
        w, h = self._vista()
        cx, cy, esc = self.vista
        return (px - w / 2) / esc + cx, -(py - h / 2) / esc + cy

    def _centrar(self, x, y, zoom=None):
        self._vista()
        self.vista[0], self.vista[1] = x, y
        if zoom:
            w, h = self._vista()
            self.vista[2] = max(self.vista[2], min(w, h) / self.sitio.ancho * zoom)
        self.redibujar(True)

    def _zoom(self, e):
        if self.sitio is None:
            return
        x, y = self.a_mundo(e.x, e.y)
        f = 1.2 if e.delta > 0 else 1 / 1.2
        w, h = self._vista()
        minimo = min(w, h) / self.sitio.ancho * 0.6
        self.vista[2] = float(np.clip(self.vista[2] * f, minimo, 12.0))
        nx, ny = self.a_mundo(e.x, e.y)
        self.vista[0] += x - nx
        self.vista[1] += y - ny
        self.redibujar(True)

    def _presionar(self, e):
        self._arr = (e.x, e.y, list(self.vista) if self.vista else None, False)

    def _arrastrar(self, e):
        if self.sitio is None or not getattr(self, "_arr", None) or self._arr[2] is None:
            return
        x0, y0, v0, _ = self._arr
        if abs(e.x - x0) + abs(e.y - y0) > 3:
            self._arr = (x0, y0, v0, True)
            self.vista[0] = v0[0] - (e.x - x0) / v0[2]
            self.vista[1] = v0[1] + (e.y - y0) / v0[2]
            self.redibujar(True)

    def _soltar(self, e):
        arr = getattr(self, "_arr", None)
        self._arr = None
        if self.sitio is None or (arr and arr[3]):
            return
        x, y = self.a_mundo(e.x, e.y)
        if self.dibujando is not None:
            self.dibujando.append((x, y))
            self.redibujar()
            return
        al = self.alertas() if self.var["ov_alertas"].get() else []
        if al:
            px, py = self.a_canvas(np.array([a["x"] for a in al]), np.array([a["y"] for a in al]))
            d = np.hypot(px - e.x, py - e.y)
            k = int(np.argmin(d))
            if d[k] < 14:
                self._vista_resultados("alertas")
                idx = next(i for i, a in enumerate(self._filas) if a is al[k] or (a["titulo"] == al[k]["titulo"] and a["x"] == al[k]["x"]))
                self.tabla.selection_set(str(idx))
                self.tabla.see(str(idx))

    def _mover(self, e):
        if self.sitio is None:
            return
        x, y = self.a_mundo(e.x, e.y)
        if not (0 <= x <= self.sitio.ancho and 0 <= y <= self.sitio.ancho):
            self.l_coord.configure(text="")
            return
        la, lo = self.sitio.georef.a_latlon(x, y)
        ep = self.var["ver_epoca"]
        p = self._mejor(ep)
        z = float(self.sitio.muestrear(p["dtm"] if p is not None else self.sitio.epocas[ep]["dtm"], x, y)[0])
        extra = ""
        if self.var["capa"].get() == "Diferencia A/B" and self.comp:
            extra = f" · Δ {float(self.sitio.muestrear(self.comp['dod'], x, y)[0]):+.2f} m"
        elif self.var["capa"].get() == "Térmica" and ep in self.termica:
            tv = float(self.sitio.muestrear(np.nan_to_num(self.termica[ep]["mapa"], nan=0), x, y)[0])
            extra = f" · {tv:.1f} °C"
        self.l_coord.configure(text=f"{float(la):.6f}, {float(lo):.6f} · z {z:.1f} m{extra}")
        if self.dibujando:
            self.cv.delete("borrador")
            px, py = self.a_canvas(*self.dibujando[-1])
            self.cv.create_line(px, py, e.x, e.y, fill=P["acento"], dash=(4, 3), tags="borrador")

    def _chip(self, x, y, texto, color, ancla="nw", fuente=(E.SEMI, 9), tags=("capa",), evitar=False):
        cv = self.cv
        t = cv.create_text(x, y, text=texto, fill=color, font=fuente, anchor=ancla, tags=tags)
        x0, y0, x1, y1 = cv.bbox(t)
        x0, y0, x1, y1 = x0 - 7, y0 - 3, x1 + 7, y1 + 3
        w, h = max(cv.winfo_width(), 50), max(cv.winfo_height(), 50)
        dx = max(0, 2 - x0) - max(0, x1 - (w - 2))
        dy = max(0, 2 - y0) - max(0, y1 - (h - 2))
        if evitar:
            for _ in range(8):
                choca = next((c for c in self._cajas if x0 + dx < c[2] and x1 + dx > c[0] and y0 + dy < c[3] and y1 + dy > c[1]), None)
                if choca is None:
                    break
                dy += choca[3] - (y0 + dy) + 2
            self._cajas.append((x0 + dx, y0 + dy, x1 + dx, y1 + dy))
        r = cv.create_rectangle(x0, y0, x1, y1, fill="#0e1014", outline=E.mezclar(color, "#0e1014", 0.35), tags=tags)
        cv.tag_lower(r, t)
        cv.move(t, dx, dy)
        cv.move(r, dx, dy)

    def redibujar(self, fondo=False):
        cv = self.cv
        self._cajas = []
        if self.sitio is None or getattr(self, "_previa", None) is not None:
            return
        w, h = self._vista()
        s = self.sitio
        if fondo or not cv.find_withtag("fondo"):
            ep = self.var["ver_epoca"]
            img, aviso = self._capa_rgb(self.var["capa"].get(), ep)
            cx, cy, esc = self.vista
            x0, y1 = self.a_mundo(0, 0)
            x1, y0 = self.a_mundo(w, h)
            px0, py0 = x0 / s.res, (s.ancho - y1) / s.res
            px1, py1 = x1 / s.res, (s.ancho - y0) / s.res
            vista = img.transform((w, h), Image.EXTENT, (px0, py0, px1, py1),
                                  Image.BILINEAR if esc * s.res < 1.5 else Image.NEAREST, fillcolor=(11, 13, 16))
            self._foto = ImageTk.PhotoImage(vista)
            cv.delete("all")
            cv.create_image(0, 0, image=self._foto, anchor="nw", tags="fondo")
            if aviso:
                self._chip(w / 2, 14, aviso, P["acento"], "n", tags=("aviso",))
            if self.var["capa"].get() == GOOGLE and self.carpeta in self.google:
                self._chip(w - 8, h - 8, self.google[self.carpeta][1], P["texto"], "se", (E.FAMILIA, 8), tags=("aviso",))
                self._chip(w - 8, h - 32, "Google", "#ffffff", "se", (E.SEMI, 11), tags=("aviso",))
        else:
            cv.delete("capa")
        if self.var["ov_curvas"].get():
            self._dibujar_curvas()
        if self.var["ov_zonas"].get():
            for k, z in enumerate(s.zonas):
                col = C.TIPOS_ZONA[z["tipo"]][1]
                p = np.asarray(z["puntos"], dtype=float)
                px, py = self.a_canvas(p[:, 0], p[:, 1])
                coords = np.column_stack([px, py]).ravel().tolist()
                sel = self.seleccion == ("zona", k)
                cv.create_polygon(*coords, outline=col, fill="", width=3 if sel else 2, dash=() if z["tipo"] != "vuelo" else (6, 4),
                                  tags="capa")
                tx, ty = float(px.mean()), float(py.min())
                etq = z["nombre"] + (f" · piso {z['cota_piso']:.0f} m" if z.get("cota_piso") is not None and z["tipo"] == "extraccion" else "")
                self._chip(tx, ty - 4, etq, col, "s", (E.SEMI, 8), evitar=True)
        if self.var["ov_plan"].get() and self.plan is not None:
            colores = [P["cian"], P["morado"], P["verde"], P["naranja"]]
            for r in self.plan["rutas"]:
                col = colores[(r["dron"] - 1) % 4]
                for vu in r["vuelos"]:
                    q = vu["puntos"][::3]
                    px, py = self.a_canvas(q[:, 0], q[:, 1])
                    cv.create_line(*np.column_stack([px, py]).ravel().tolist(), fill=col, width=1, tags="capa")
            bx, by = self.a_canvas(*s.base)
            cv.create_rectangle(bx - 7, by - 7, bx + 7, by + 7, outline=P["acento"], width=2, tags="capa")
            self._chip(bx + 10, by, "Base de drones", P["acento"], "w", (E.SEMI, 8), evitar=True)
        if self.var["ov_control"].get():
            for c_, col, etq in ((self.gcps[:int(self.var["gcp"].get())], P["acento"], "GCP"), (self.checkpoints, P["cian"], "CP")):
                for p_ in c_:
                    px, py = self.a_canvas(p_["x"], p_["y"])
                    cv.create_polygon(px, py - 7, px + 6, py + 4, px - 6, py + 4, outline=col, fill="", width=2, tags="capa")
        if self.var["ov_alertas"].get():
            sel = self.seleccion[1] if self.seleccion and self.seleccion[0] == "alerta" else None
            for a in self.alertas():
                px, py = self.a_canvas(a["x"], a["y"])
                col = SEV_COLOR.get(a["severidad"], P["gris"])
                r = 9 if a is sel or (sel and a["titulo"] == sel["titulo"] and a["x"] == sel["x"]) else 6
                if a.get("puntos"):
                    q = np.asarray(a["puntos"])
                    qx, qy = self.a_canvas(q[:, 0], q[:, 1])
                    cv.create_line(*np.column_stack([qx, qy]).ravel().tolist(), fill=col, width=2, tags="capa")
                cv.create_oval(px - r, py - r, px + r, py + r, outline="#0e1014", fill=col, width=2, tags="capa")
                if r == 9:
                    self._chip(px + 12, py, a["titulo"], col, "w", (E.SEMI, 9))
        if self.dibujando:
            p = self.dibujando
            px, py = self.a_canvas(np.array([q[0] for q in p]), np.array([q[1] for q in p]))
            if len(p) > 1:
                cv.create_line(*np.column_stack([px, py]).ravel().tolist(), fill=P["acento"], width=2, tags="capa")
            for x, y in zip(px, py):
                cv.create_oval(x - 4, y - 4, x + 4, y + 4, fill=P["acento"], outline="", tags="capa")
        self._escala()
        self._dibujar_drones()

    def _dibujar_curvas(self):
        ep = self.var["ver_epoca"]
        p = self._mejor(ep)
        dtm = p["dtm"] if p is not None else self.sitio.epocas[ep]["dtm"]
        clave = (ep, self.var["intervalo"], p is not None)
        if self.curvas.get(ep, (None,))[0] != clave:
            self.curvas[ep] = (clave, PR.curvas(dtm, self.sitio, self.var["intervalo"], 2 if self.sitio.res < 2 else 1))
        lineas = self.curvas[ep][1]
        maestra = self.var["intervalo"] * 5
        w, h = self._vista()
        for nivel, l in lineas:
            px, py = self.a_canvas(l[:, 0], l[:, 1])
            if px.max() < 0 or px.min() > w or py.max() < 0 or py.min() > h:
                continue
            m = abs(nivel / maestra - round(nivel / maestra)) < 1e-6
            self.cv.create_line(*np.column_stack([px, py]).ravel().tolist(), fill="#f2e7c9" if m else "#b9ad8f",
                                width=1.4 if m else 0.7, tags="capa")

    def _escala(self):
        w, h = self._vista()
        esc = self.vista[2]
        objetivo = 120 / esc
        paso = 10 ** math.floor(math.log10(objetivo))
        for f in (1, 2, 5, 10):
            if paso * f >= objetivo * 0.6:
                paso *= f
                break
        largo = paso * esc
        x0, y0 = 16, h - 20
        self.cv.create_rectangle(x0 - 6, y0 - 18, x0 + largo + 6, y0 + 8, fill="#0e1014", outline="", tags="capa")
        self.cv.create_line(x0, y0, x0 + largo, y0, fill=P["texto"], width=2, tags="capa")
        self.cv.create_text(x0 + largo / 2, y0 - 9, text=f"{paso:g} m" if paso < 1000 else f"{paso / 1000:g} km", fill=P["texto"],
                            font=(E.SEMI, 8), tags="capa")
        self.cv.create_text(w - 18, 18, text="N ▲", fill=P["texto"], font=(E.SEMI, 10), tags="capa")

    def _dibujar_drones(self):
        cv = self.cv
        cv.delete("dron")
        if self.sim is None or self.sitio is None or self.sim.terminada:
            return
        colores = [P["cian"], P["morado"], P["verde"], P["naranja"]]
        textos = []
        for d in self.sim.estado():
            col = colores[(d["dron"] - 1) % 4]
            px, py = self.a_canvas(d["x"], d["y"])
            if d.get("z") is not None:
                a = d["rumbo"]
                if self.sim.lidar is not None and d["estado"] == "Escaneando":
                    zg = float(self.sitio.muestrear(self.sim.dsm, d["x"], d["y"])[0])
                    medio = (d["z"] - zg) * math.tan(self.sim.fov / 2)
                    for sgn in (-1, 1):
                        qx, qy = self.a_canvas(d["x"] - math.sin(a) * medio * sgn, d["y"] + math.cos(a) * medio * sgn)
                        cv.create_line(px, py, qx, qy, fill=col, width=2, tags="dron")
                elif self.sim.camara is not None:
                    zg = float(self.sitio.muestrear(self.sim.dsm, d["x"], d["y"])[0])
                    an, la = PL.huella(self.sim.camara, max(5, d["z"] - zg))
                    c, s = math.cos(a), math.sin(a)
                    esq = [(la / 2, an / 2), (la / 2, -an / 2), (-la / 2, -an / 2), (-la / 2, an / 2)]
                    pts = []
                    for u, v in esq:
                        qx, qy = self.a_canvas(d["x"] + u * c - v * s, d["y"] + u * s + v * c)
                        pts += [qx, qy]
                    cv.create_polygon(*pts, outline=col, fill="", width=1.5, tags="dron")
                tri = [(9, 0), (-6, 5), (-6, -5)]
                pts = []
                for u, v in tri:
                    pts += [px + u * math.cos(a) + v * math.sin(a), py - (u * math.sin(a) - v * math.cos(a))]
                cv.create_polygon(*pts, fill=col, outline="#0e1014", width=1.5, tags="dron")
            textos.append(f"Dron {d['dron']}: {d['estado']}" + (f" · vuelo {d['vuelo']}/{d.get('de', d['vuelo'])} · batería {d['bateria'] * 100:.0f}%"
                                                                 if d.get("z") is not None else ""))
        t = self.sim.t
        cab = f"Vuelo {t / 60:.0f}/{self.sim.duracion / 60:.0f} min"
        if self.sim.lidar is not None:
            cab += f" · {self.sim.n_puntos / 1e6:.2f} M puntos"
        else:
            cab += f" · {len(self.sim.capturas)} fotos"
        y = 40
        for k, txt in enumerate([cab] + textos):
            self._chip(12, y, txt, P["texto"] if k == 0 else colores[(k - 1) % 4], "nw", (E.SEMI, 9), tags=("dron",))
            y += 24

    def _guardar_productos(self):
        if self.carpeta is None:
            return
        try:
            arrays = {}
            for (ep, clase), p in self.prod.items():
                for campo in ("dtm", "dsm", "densidad", "sin_retorno", "orto", "cobertura", "gsd"):
                    if campo in p:
                        arrays[f"{ep}_{clase}_{campo}"] = p[campo]
            for ep, t in self.termica.items():
                arrays[f"{ep}_termica_mapa"] = t["mapa"]
            if self.comp:
                arrays["dod"] = self.comp["dod"]
            np.savez_compressed(os.path.join(self.carpeta, "productos.npz"), **arrays)
            meta = {"prod": {f"{ep}|{c}": {k: v for k, v in p.items() if isinstance(v, (str, int, float))} for (ep, c), p in self.prod.items()},
                    "prec": {f"{ep}|{c}": v for (ep, c), v in self.prec.items()},
                    "termica": {ep: t["alertas"] for ep, t in self.termica.items()},
                    "visual": {ep: v["alertas"] for ep, v in self.visual.items()},
                    "geom": {ep: g["alertas"] for ep, g in self.geom.items()},
                    "comp": {k: v for k, v in self.comp.items() if k != "dod"} if self.comp else None,
                    "sesgos": {f"{ep}|{c}": [np.asarray(p["sesgos"]).tolist(), np.asarray(p["sesgos_est"]).tolist()] for (ep, c), p in self.prod.items()}}
            with open(os.path.join(self.carpeta, "productos.json"), "w", encoding="utf-8") as f:
                json.dump(meta, f, ensure_ascii=False, default=float)
        except Exception as ex:
            self.log(f"No se pudo guardar el avance: {ex}", P["naranja"])

    def _cargar_productos(self, carpeta):
        try:
            with open(os.path.join(carpeta, "productos.json"), encoding="utf-8") as f:
                meta = json.load(f)
            d = np.load(os.path.join(carpeta, "productos.npz"))
        except (OSError, ValueError):
            return None
        prod, prec = {}, {}
        for clave, info in meta["prod"].items():
            ep, c = clave.split("|")
            p = dict(info)
            for campo in ("dtm", "dsm", "densidad", "sin_retorno", "orto", "cobertura", "gsd"):
                if f"{ep}_{c}_{campo}" in d.files:
                    p[campo] = d[f"{ep}_{c}_{campo}"]
            s, e = meta["sesgos"][clave]
            p["sesgos"], p["sesgos_est"] = np.array(s), np.array(e)
            prod[(ep, c)] = p
        for clave, v in meta["prec"].items():
            ep, c = clave.split("|")
            prec[(ep, c)] = v
        termica = {ep: {"alertas": al, "mapa": d[f"{ep}_termica_mapa"]} for ep, al in meta["termica"].items() if f"{ep}_termica_mapa" in d.files}
        visual = {ep: {"alertas": al} for ep, al in meta["visual"].items()}
        geom = {ep: {"alertas": al} for ep, al in meta["geom"].items()}
        comp = None
        if meta.get("comp") and "dod" in d.files:
            comp = dict(meta["comp"], dod=d["dod"])
        return prod, prec, termica, visual, geom, comp

    def _guardar_clave(self):
        G.guardar_clave_google(self.var["clave"].get())
        self.google.clear()
        self.log("Clave de Google Maps guardada en config_local.json", P["verde"])
        self.google_maps()

    def _cargar_google(self, al_terminar=None):
        s, carpeta = self.sitio, self.carpeta
        clave = G.clave_google()

        def fin(res):
            self.google[carpeta] = (res[0], res[1])
            self._cache = {k: v for k, v in self._cache.items() if k[0] != GOOGLE}
            self.log(f"Satélite de Google cargado ({res[1]})", P["verde"])
            if al_terminar:
                al_terminar()
        self._tarea("Descargando el satélite de Google…", lambda av: G.imagen_google(s.georef, s.nx, s.ny, clave, av), fin)

    def _requisitos_google(self):
        if self.sitio is None:
            return False
        if not self.sitio.real:
            self._tab("sitio")
            self.log("La mina demostración es ficticia: elige una mina real o busca una ciudad/mina y presiona «Crear sitio»",
                     P["acento"])
            return False
        return True

    def google_maps(self):
        if not self._requisitos_google():
            return
        if not G.clave_google():
            s = self.sitio
            x, y = (self.vista[0], self.vista[1]) if self.vista else (s.ancho / 2, s.ancho / 2)
            la, lo = s.georef.a_latlon(x, y)
            subprocess.Popen([sys.executable, os.path.join(C.RAIZ, "main.py"), "--google", f"{float(la):.6f}", f"{float(lo):.6f}",
                              "--nombre", s.nombre, "--ancho", f"{s.ancho:.0f}"], cwd=C.RAIZ)
            self.log("Google Maps abierto en una ventana del programa (satélite, híbrido, mapa y relieve)", P["verde"])
            return

        def mostrar():
            self.var["capa"].set(GOOGLE)
            self.redibujar(True)
        if self.carpeta in self.google:
            mostrar()
        else:
            self._cargar_google(mostrar)

    def _carpeta_salida(self):
        carpeta = os.path.join(C.CARPETA_EXPORTACIONES, _clave(self.sitio.nombre) + datetime.datetime.now().strftime("_%Y%m%d_%H%M%S"))
        os.makedirs(carpeta, exist_ok=True)
        return carpeta

    def _kml(self, carpeta):
        s = self.sitio
        img, _ = self._capa_rgb(self.var["capa"].get(), self.var["ver_epoca"])
        nombre_img = "capa_" + _clave(self.var["capa"].get()) + ".jpg"
        img.save(os.path.join(carpeta, nombre_img), quality=88)
        rutas = []
        if self.plan:
            for r in self.plan["rutas"]:
                for k, vu in enumerate(r["vuelos"]):
                    rutas.append((f"Dron {r['dron']} · vuelo {k + 1}", vu["puntos"][::4]))
        return G.exportar_kml(s.georef, os.path.join(carpeta, "sitio.kml"), s.nombre, s.zonas, rutas, self.alertas(),
                              (nombre_img, self.var["capa"].get()))

    def google_earth(self):
        if self.sitio is None:
            return
        carpeta = self._carpeta_salida()
        ruta = self._kml(carpeta)
        exe = G.google_earth_pro()
        if exe:
            subprocess.Popen([exe, ruta])
            self.log(f"Abriendo en Google Earth Pro con zonas, vuelos y alertas: {ruta}", P["verde"])
            return
        if not self.sitio.real:
            self.log("La mina demostración es ficticia: Google Earth mostraría otro lugar. Elige una mina real o busca un lugar",
                     P["acento"])
            self._tab("sitio")
            return
        x, y = (self.vista[0], self.vista[1]) if self.vista else (self.sitio.ancho / 2, self.sitio.ancho / 2)
        la, lo = self.sitio.georef.a_latlon(x, y)
        elev = float(np.median(self.sitio.epocas["B"]["dtm"]))
        webbrowser.open(G.url_google_earth(float(la), float(lo), elev, self.sitio.ancho * 1.3))
        self.log(f"Google Earth abierto en el sitio. Para ver zonas, vuelos y alertas: en Google Earth usa Proyectos → "
                 f"Nuevo proyecto → Importar archivo KML y elige {ruta}", P["verde"])

    def exportar_waypoints(self):
        if self.plan is None:
            return
        carpeta = self._carpeta_salida()
        rutas = EX.escribir_waypoints(carpeta, self.sitio, self.plan, self.sitio.superficie("A"))
        self.log(f"{len(rutas)} archivos de waypoints en {carpeta}", P["verde"])

    def exportar_todo(self):
        if self.sitio is None:
            return
        s = self.sitio
        carpeta = self._carpeta_salida()
        vuelos, prod, comp, plan = dict(self.vuelos), dict(self.prod), self.comp, self.plan
        alertas = self.alertas()
        precs = {ep: self._mejor_prec(ep) for ep in ("A", "B")}
        capas_img = {}
        for nombre in CAPAS:
            img, aviso = self._capa_rgb(nombre, "B")
            if not aviso:
                capas_img[nombre] = img
        kml = self._kml(carpeta)

        def tarea(avisar):
            hechos = [os.path.basename(kml)]
            for ep in ("A", "B"):
                l = prod.get((ep, "lidar"))
                if l is not None and "x" in l:
                    avisar(f"Escribiendo nube LAS de la época {ep}…")
                    EX.escribir_las(os.path.join(carpeta, f"nube_{ep}.las"), s.georef, l)
                    hechos.append(f"nube_{ep}.las")
                p = prod.get((ep, "lidar")) or prod.get((ep, "foto"))
                if p is not None:
                    avisar(f"Escribiendo modelos de elevación {ep}…")
                    EX.escribir_asc(os.path.join(carpeta, f"dtm_{ep}.asc"), s, p["dtm"])
                    EX.escribir_asc(os.path.join(carpeta, f"dsm_{ep}.asc"), s, p["dsm"])
                    tex = prod[(ep, "foto")]["orto"] if (ep, "foto") in prod else s.epocas[ep]["color"]
                    EX.escribir_obj(os.path.join(carpeta, f"modelo3d_{ep}.obj"), s, p["dtm"], tex, paso=max(2, int(4 / s.res)))
                    hechos += [f"dtm_{ep}.asc", f"dsm_{ep}.asc", f"modelo3d_{ep}.obj"]
            if comp:
                EX.escribir_asc(os.path.join(carpeta, "diferencia_A_B.asc"), s, comp["dod"])
                hechos.append("diferencia_A_B.asc")
            pb = prod.get(("B", "lidar")) or prod.get(("B", "foto"))
            dtm = pb["dtm"] if pb is not None else s.epocas["B"]["dtm"]
            avisar("Escribiendo GeoJSON (zonas, alertas, curvas, vuelos)…")
            EX.escribir_geojson(os.path.join(carpeta, "zonas_alertas.geojson"), s, alertas, (), plan, comp)
            EX.escribir_geojson(os.path.join(carpeta, "curvas_nivel.geojson"), s, (), PR.curvas(dtm, s, 5.0), None, None)
            EX.escribir_reporte(os.path.join(carpeta, "reporte.csv"), s, comp, alertas, precs)
            hechos += ["zonas_alertas.geojson", "curvas_nivel.geojson", "reporte.csv"]
            if plan:
                hechos += [os.path.basename(r) for r in EX.escribir_waypoints(carpeta, s, plan, s.superficie("A"))]
            for nombre, img in capas_img.items():
                img.save(os.path.join(carpeta, "mapa_" + _clave(nombre) + ".png"))
            return carpeta, hechos

        def fin(res):
            carpeta, hechos = res
            self.log(f"Exportados {len(hechos)} archivos en {carpeta}", P["verde"])
            try:
                os.startfile(carpeta)
            except (AttributeError, OSError):
                pass
        self._tarea("Exportando…", tarea, fin)

    def abrir_exportaciones(self):
        os.makedirs(C.CARPETA_EXPORTACIONES, exist_ok=True)
        try:
            os.startfile(C.CARPETA_EXPORTACIONES)
        except (AttributeError, OSError):
            pass

    def preparar_3d(self, ruta=None):
        s = self.sitio
        ep = self.var["ver_epoca"]
        p = self._mejor(ep)
        dtm = p["dtm"] if p is not None else s.epocas[ep]["dtm"]
        capas = [("Imagen", (self.prod[(ep, "foto")]["orto"] if (ep, "foto") in self.prod else s.epocas[ep]["color"])),
                 ("Hipsométrico", CA.hipsometrico(s, dtm)), ("Pendientes", CA.pendiente(s, dtm)[0])]
        if self.carpeta in self.google:
            capas.insert(0, ("Google Maps", self.google[self.carpeta][0]))
        if self.comp:
            capas.append(("Diferencia A/B", CA.diferencia(s, self.comp["dod"], dtm, lod=self.comp["lod"])[0]))
        if ep in self.termica:
            capas.append(("Térmica", CA.termico(self.termica[ep]["mapa"])[0]))
        l = self.prod.get((ep, "lidar"))
        nube = l if l is not None and "x" in l else None
        rutas = []
        if self.plan:
            rutas = [vu["puntos"][::2] for r in self.plan["rutas"] for vu in r["vuelos"]]
        zonas = [(z["puntos"], [int(C.TIPOS_ZONA[z["tipo"]][1][i:i + 2], 16) / 255 for i in (1, 3, 5)]) for z in s.zonas]
        ruta = ruta or os.path.join(self.carpeta, "vista3d.npz")
        alertas = [a for a in self.alertas() if a["severidad"] != "info"] if ep == "B" else []
        return V3.preparar(ruta, s, capas, dtm, nube, rutas, zonas, alertas)

    def modelo_3d(self):
        if self.sitio is None:
            return

        def tarea(avisar):
            avisar("Preparando el modelo 3D…")
            return self.preparar_3d()

        def fin(ruta):
            subprocess.Popen([sys.executable, os.path.join(C.RAIZ, "main.py"), "--visor", ruta], cwd=C.RAIZ)
            self.log("Visor 3D abierto: arrastra para girar, rueda para acercar, 1–5 cambia la capa, F9 graba video", P["verde"])
        self._tarea("Preparando el modelo 3D…", tarea, fin)

    def _salir(self):
        self.grabar.cerrar()
        self.raiz.destroy()

    def correr(self):
        self.raiz.protocol("WM_DELETE_WINDOW", self._salir)
        self.raiz.mainloop()
