import copy
import json
import math
import os
import queue
import subprocess
import sys
import threading
import time
import tkinter as tk
from tkinter import colorchooser, filedialog, messagebox

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageTk

import config as C
import estilo as E
import formaciones as F
from grabador import BotonGrabar
import planificador as PL

P = E.P

BASE = {"duracion": 10, "movimiento": "fija", "efecto": "ninguno", "ancho": 0}
NUEVA = {
    "texto": dict(BASE, tipo="texto", nombre="Texto", texto="HOLA", fuente="Arial Black", trazo="relleno", capas=1,
                  color="por_letra", colores=["#ff3b6b", "#ffd23b", "#3bd1ff"]),
    "imagen": dict(BASE, tipo="imagen", nombre="Imagen", ruta="ejemplos/logo_estrella.png", umbral=60,
                   invertir=False, trazo="relleno", capas=1, color="imagen",
                   colores=["#ffffff", "#f5b400", "#3dd6f5"]),
    "figura": dict(BASE, tipo="figura", nombre="Figura 3D", figura="corazon", color="figura",
                   colores=["#ff2b4b", "#ffd23b", "#3dd6f5"], movimiento="girar", duracion=14),
}

SHOW_EJEMPLO = {
    "nombre": "Noche de drones 2026", "drones": 400, "separacion": C.SEPARACION, "altura": C.ALTURA_CENTRO,
    "vel_max": C.VEL_H,
    "escenas": [
        dict(NUEVA["texto"], nombre="Bienvenida", texto="HOLA", efecto="destellos", duracion=9),
        dict(NUEVA["figura"], nombre="Corazón", figura="corazon", movimiento="girar", efecto="respirar", duracion=14),
        dict(NUEVA["imagen"], nombre="Logo", duracion=9),
        dict(NUEVA["figura"], nombre="Planeta", figura="planeta", movimiento="girar", efecto="ninguno", duracion=14),
        dict(NUEVA["texto"], nombre="Despedida", texto="GRACIAS", color="degradado",
             colores=["#3dd6f5", "#ff3df0", "#ffffff"], movimiento="ola", efecto="barrido", duracion=11),
    ],
}

TIPOS = {"texto": ("Texto", P["azul"], "T"), "imagen": ("Imagen", P["verde"], "◩"), "figura": ("Figura 3D", P["morado"], "◆")}
COLOR_POR_TIPO = {
    "texto": ["unico", "por_letra", "degradado", "tres", "vertical", "arcoiris"],
    "imagen": ["imagen", "unico", "degradado", "tres", "vertical", "arcoiris"],
    "figura": ["figura", "unico", "degradado", "vertical", "arcoiris"],
}
COLORES_USADOS = {"unico": 1, "degradado": 2, "vertical": 2, "tres": 3, "por_letra": 3}


def _entrada(padre, var, ancho=None):
    e = tk.Entry(padre, textvariable=var, bg=P["tarjeta2"], fg=P["texto"], insertbackground=P["texto"],
                 relief="flat", font=E.F_TEXTO, highlightthickness=1, highlightbackground=P["borde"],
                 highlightcolor=P["acento"], width=ancho or 10)
    return e


class Desplazable(tk.Frame):
    def __init__(self, padre, **kw):
        super().__init__(padre, bg=P["tarjeta"], **kw)
        self.cv = tk.Canvas(self, bg=P["tarjeta"], highlightthickness=0)
        self.barra = tk.Scrollbar(self, orient="vertical", command=self.cv.yview, width=10)
        self.cuerpo = tk.Frame(self.cv, bg=P["tarjeta"])
        self.cuerpo.bind("<Configure>", lambda e: self.cv.configure(scrollregion=self.cv.bbox("all")))
        self.ventana = self.cv.create_window(0, 0, anchor="nw", window=self.cuerpo)
        self.cv.bind("<Configure>", lambda e: self.cv.itemconfigure(self.ventana, width=e.width))
        self.cv.configure(yscrollcommand=self.barra.set)
        self.cv.pack(side="left", fill="both", expand=True)
        self.barra.pack(side="right", fill="y")
        self.bind_all("<MouseWheel>", self._rueda, add="+")

    def _rueda(self, e):
        w = self.winfo_containing(e.x_root, e.y_root)
        while w is not None:
            if w is self:
                if self.cuerpo.winfo_height() > self.cv.winfo_height():
                    self.cv.yview_scroll(int(-e.delta / 120), "units")
                return
            w = w.master


class Editor(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Diseñador de espectáculos de drones")
        self.configure(bg=P["fondo"])
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        w, h = min(1500, sw - 60), min(920, sh - 90)
        self.geometry(f"{w}x{h}+{max((sw - w) // 2, 0)}+{max((sh - h) // 2 - 20, 0)}")
        self.minsize(1180, 720)
        self.fuentes = F.fuentes_disponibles()
        self.show = self._cargar_inicial()
        self.sel = 0
        self.cache = {}
        self.tareas = queue.Queue()
        self.salida = queue.Queue()
        self.gen_prev = 0
        self.gen_plan = 0
        self.plan = None
        self.plan_gen = -1
        self.fo_prev = None
        self.error_prev = ""
        self.ang = 0.0
        self.ultimo = time.perf_counter()
        self._prev_id = None
        self._guardar_id = None
        self._fondo = None
        self.ocupado = ""
        self._construir()
        threading.Thread(target=self._trabajador, daemon=True).start()
        self._seleccionar(0)
        self.after(60, self._sondear)
        self.after(50, self._animar)
        self.protocol("WM_DELETE_WINDOW", self._cerrar)

    def _cargar_inicial(self):
        try:
            with open(C.SHOW_ACTUAL, encoding="utf-8") as f:
                s = json.load(f)
            if s.get("escenas"):
                return PL.normalizar_show(s)
        except (OSError, ValueError):
            pass
        return PL.normalizar_show(copy.deepcopy(SHOW_EJEMPLO))

    def _construir(self):
        cab = tk.Frame(self, bg=P["fondo"])
        cab.pack(fill="x", padx=18, pady=(14, 10))
        izq = tk.Frame(cab, bg=P["fondo"])
        izq.pack(side="left")
        tk.Label(izq, text="Diseñador de espectáculos de drones", bg=P["fondo"], fg=P["texto"],
                 font=E.F_TITULO).pack(anchor="w")
        tk.Label(izq, text="Despegue  ·  figuras en el aire con texto, imagen o 3D  ·  aterrizaje",
                 bg=P["fondo"], fg=P["tenue"], font=E.F_TEXTO).pack(anchor="w")
        der = tk.Frame(cab, bg=P["fondo"])
        der.pack(side="right")
        E.Boton(der, "▶  Ver show en 3D", self._ver, color=P["acento"], primario=True).pack(side="right", padx=(8, 0))
        E.Boton(der, "Exportar trayectorias", self._exportar).pack(side="right", padx=(8, 0))
        E.Boton(der, "Guardar", self._guardar_como).pack(side="right", padx=(8, 0))
        E.Boton(der, "Abrir", self._abrir).pack(side="right", padx=(8, 0))
        E.Boton(der, "Nuevo", self._nuevo).pack(side="right")
        self.grabar = E.estilo_boton_grabar(BotonGrabar(der, self, self._mensaje)).pack(side="right", padx=(0, 8))

        cuerpo = tk.Frame(self, bg=P["fondo"])
        cuerpo.pack(fill="both", expand=True, padx=18, pady=(0, 16))
        cuerpo.columnconfigure(1, weight=1)
        cuerpo.rowconfigure(0, weight=1)

        col_i = tk.Frame(cuerpo, bg=P["fondo"], width=300)
        col_i.grid(row=0, column=0, sticky="nsw", padx=(0, 12))
        col_i.grid_propagate(False)
        col_i.pack_propagate(False)
        m, c = E.tarjeta(col_i, "Show")
        m.pack(fill="x")
        self.v_nombre = tk.StringVar(value=self.show["nombre"])
        _entrada(c, self.v_nombre).pack(fill="x", ipady=4)
        self.v_nombre.trace_add("write", lambda *a: self._cambio_show("nombre", self.v_nombre.get()))

        m, c = E.tarjeta(col_i, "Secuencia de escenas")
        m.pack(fill="both", expand=True, pady=(10, 0))
        self.lista = tk.Canvas(c, bg=P["tarjeta"], highlightthickness=0, height=200)
        self.lista.pack(fill="both", expand=True)
        self.lista.bind("<Button-1>", self._clic_lista)
        self.lista.bind("<Configure>", lambda e: self._pintar_lista())
        self.lista.bind("<MouseWheel>", lambda e: self.lista.yview_scroll(int(-e.delta / 120), "units"))
        fila = tk.Frame(c, bg=P["tarjeta"])
        fila.pack(fill="x", pady=(8, 0))
        for i, (t, txt) in enumerate((("texto", "+ Texto"), ("imagen", "+ Imagen"), ("figura", "+ Figura 3D"))):
            b = E.Boton(fila, txt, lambda t=t: self._agregar(t), color=E.oscurecer(TIPOS[t][1], 0.55))
            b.w.grid(row=0, column=i, sticky="ew", padx=(0 if i == 0 else 4, 0))
            fila.columnconfigure(i, weight=1)
        fila = tk.Frame(c, bg=P["tarjeta"])
        fila.pack(fill="x", pady=(6, 0))
        for i, (txt, fn) in enumerate((("▲", lambda: self._mover(-1)), ("▼", lambda: self._mover(1)),
                                        ("Duplicar", self._duplicar), ("Eliminar", self._eliminar))):
            b = E.Boton(fila, txt, fn)
            b.w.grid(row=0, column=i, sticky="ew", padx=(0 if i == 0 else 4, 0))
            fila.columnconfigure(i, weight=1 if i > 1 else 0)

        m, c = E.tarjeta(col_i, "Flota")
        m.pack(fill="x", pady=(10, 0))
        self.desl = {}
        for clave, etq, lo, hi, paso, fmt, uni in (
                ("drones", "Número de drones", C.DRONES_MIN, C.DRONES_MAX, 10, "{:.0f}", ""),
                ("separacion", "Separación mínima", 1.5, 4.0, 0.1, "{:.1f}", " m"),
                ("altura", "Altura del centro", 30, 120, 5, "{:.0f}", " m"),
                ("vel_max", "Velocidad máxima", 3, 12, 0.5, "{:.1f}", " m/s")):
            E.etiqueta(c, etq).pack(anchor="w")
            v = tk.DoubleVar(value=float(self.show[clave]))
            d = E.Deslizador(c, v, lo, hi, paso, lambda k=clave, v=v: self._cambio_show(k, v.get(), flota=True),
                             ancho=272, formato=fmt, unidad=uni)
            d.pack(anchor="w", pady=(0, 2))
            self.desl[clave] = (v, d)

        col_c = tk.Frame(cuerpo, bg=P["fondo"])
        col_c.grid(row=0, column=1, sticky="nsew")
        col_c.rowconfigure(0, weight=1)
        col_c.columnconfigure(0, weight=1)
        m, c = E.tarjeta(col_c, "Vista previa de la formación")
        m.grid(row=0, column=0, sticky="nsew")
        self.previa = tk.Canvas(c, bg="#05070c", highlightthickness=0)
        self.previa.pack(fill="both", expand=True)
        self.img_prev = self.previa.create_image(0, 0, anchor="nw")
        self.previa.bind("<Configure>", lambda e: self._dibujar_previa(forzar=True))

        m, c = E.tarjeta(col_c, "Plan de vuelo", derecha=lambda p: E.Boton(p, "Calcular y verificar", self._calcular).w)
        m.grid(row=1, column=0, sticky="ew", pady=(10, 0))
        self.ind = tk.Canvas(c, bg=P["tarjeta"], highlightthickness=0, height=50)
        self.ind.pack(fill="x")
        self.ind.bind("<Configure>", lambda e: self._pintar_plan())
        self.linea = tk.Canvas(c, bg=P["tarjeta"], highlightthickness=0, height=44)
        self.linea.pack(fill="x", pady=(8, 0))
        self.estado = tk.Label(c, text="", bg=P["tarjeta"], fg=P["tenue"], font=E.F_CHICA, anchor="w")
        self.estado.pack(fill="x", pady=(4, 0))

        col_d = tk.Frame(cuerpo, bg=P["fondo"], width=350)
        col_d.grid(row=0, column=2, sticky="nse", padx=(12, 0))
        col_d.pack_propagate(False)
        m, c = E.tarjeta(col_d, "Escena seleccionada")
        m.pack(fill="both", expand=True)
        self.panel = Desplazable(c)
        self.panel.pack(fill="both", expand=True)

    def _pintar_lista(self):
        cv = self.lista
        cv.delete("all")
        w = max(cv.winfo_width(), 100)
        alto = 52
        for i, esc in enumerate(self.show["escenas"]):
            y = i * (alto + 6)
            sel = i == self.sel
            nombre_t, col, icono = TIPOS.get(esc["tipo"], TIPOS["texto"])
            cv.create_rectangle(0, y, w, y + alto, fill=P["tarjeta2"] if sel else P["tarjeta"],
                                outline=P["acento"] if sel else P["borde"])
            if sel:
                cv.create_rectangle(0, y, 3, y + alto, fill=P["acento"], outline="")
            cv.create_oval(12, y + 12, 40, y + 40, fill=E.oscurecer(col, 0.6), outline=col)
            cv.create_text(26, y + 26, text=str(i + 1), fill=P["texto"], font=(E.SEMI, 10))
            nombre = esc.get("nombre") or nombre_t
            cv.create_text(52, y + 17, text=nombre[:26], anchor="w", fill=P["texto"], font=(E.SEMI, 10))
            if esc["tipo"] == "texto":
                det = "“" + esc.get("texto", "").replace("\n", " ")[:16] + "”"
            elif esc["tipo"] == "imagen":
                det = os.path.basename(esc.get("ruta", "") or "sin imagen")[:18]
            else:
                det = C.FIGURAS.get(esc.get("figura"), "")
            cv.create_text(52, y + 36, text=f"{nombre_t} · {det}", anchor="w", fill=P["tenue"], font=E.F_CHICA)
            cv.create_text(w - 10, y + 17, text=f"{esc.get('duracion', 10):.0f} s", anchor="e", fill=P["tenue"],
                           font=E.F_CHICA)
            mov = C.MOVIMIENTOS.get(esc.get("movimiento", "fija"), "")
            if esc.get("movimiento", "fija") != "fija":
                cv.create_text(w - 10, y + 36, text=mov.split()[0], anchor="e", fill=P["sutil"], font=E.F_CHICA)
        total = len(self.show["escenas"]) * (alto + 6)
        cv.configure(scrollregion=(0, 0, w, max(total, cv.winfo_height())))

    def _clic_lista(self, e):
        y = self.lista.canvasy(e.y)
        i = int(y // 58)
        if 0 <= i < len(self.show["escenas"]):
            self._seleccionar(i)

    def _seleccionar(self, i):
        if not self.show["escenas"]:
            self.sel = -1
        else:
            self.sel = max(0, min(i, len(self.show["escenas"]) - 1))
        self._pintar_lista()
        self._construir_panel()
        self._pedir_previa(inmediato=True)

    def _esc(self):
        if 0 <= self.sel < len(self.show["escenas"]):
            return self.show["escenas"][self.sel]
        return None

    def _agregar(self, tipo):
        esc = copy.deepcopy(NUEVA[tipo])
        k = sum(1 for e in self.show["escenas"] if e["tipo"] == tipo) + 1
        esc["nombre"] = f"{esc['nombre']} {k}"
        self.show["escenas"].insert(self.sel + 1, esc)
        self._modificado()
        self._seleccionar(self.sel + 1)

    def _mover(self, d):
        es = self.show["escenas"]
        j = self.sel + d
        if self._esc() is None or not 0 <= j < len(es):
            return
        es[self.sel], es[j] = es[j], es[self.sel]
        self.sel = j
        self._modificado()
        self._pintar_lista()

    def _duplicar(self):
        esc = self._esc()
        if esc is None:
            return
        nueva = copy.deepcopy(esc)
        nueva["nombre"] = esc.get("nombre", "") + " (copia)"
        self.show["escenas"].insert(self.sel + 1, nueva)
        self._modificado()
        self._seleccionar(self.sel + 1)

    def _eliminar(self):
        if self._esc() is None:
            return
        if len(self.show["escenas"]) == 1:
            messagebox.showinfo("Escenas", "El show necesita al menos una escena.", parent=self)
            return
        del self.show["escenas"][self.sel]
        self._modificado()
        self._seleccionar(min(self.sel, len(self.show["escenas"]) - 1))

    def _limpiar_panel(self):
        for w in self.panel.cuerpo.winfo_children():
            w.destroy()

    def _titulo(self, padre, texto, arriba=12):
        E.etiqueta(padre, texto.upper(), fuente=E.F_SECCION).pack(anchor="w", pady=(arriba, 4))

    def _construir_panel(self):
        self._limpiar_panel()
        esc = self._esc()
        p = self.panel.cuerpo
        if esc is None:
            return
        tipo = esc["tipo"]
        nombre_t, col, _ = TIPOS[tipo]
        cab = tk.Frame(p, bg=P["tarjeta"])
        cab.pack(fill="x")
        tk.Label(cab, text=nombre_t.upper(), bg=E.oscurecer(col, 0.55), fg=col, font=(E.SEMI, 8), padx=8,
                 pady=2).pack(side="left")
        tk.Label(cab, text=f"Escena {self.sel + 1} de {len(self.show['escenas'])}", bg=P["tarjeta"],
                 fg=P["tenue"], font=E.F_CHICA).pack(side="left", padx=8)

        self._titulo(p, "Nombre")
        v = tk.StringVar(value=esc.get("nombre", ""))
        _entrada(p, v).pack(fill="x", ipady=3)
        v.trace_add("write", lambda *a: self._cambio("nombre", v.get(), previa=False))

        if tipo == "texto":
            self._titulo(p, "Texto (Enter = nueva línea)")
            t = tk.Text(p, height=3, bg=P["tarjeta2"], fg=P["texto"], insertbackground=P["texto"], relief="flat",
                        font=(E.SEMI, 12), highlightthickness=1, highlightbackground=P["borde"],
                        highlightcolor=P["acento"], wrap="none", padx=6, pady=4)
            t.insert("1.0", esc.get("texto", ""))
            t.pack(fill="x")
            t.bind("<KeyRelease>", lambda e: self._cambio("texto", t.get("1.0", "end-1c")))
            self._titulo(p, "Fuente")
            vf = tk.StringVar(value=esc.get("fuente", self.fuentes[0]))
            E.Menu(p, vf, self.fuentes, lambda: self._cambio("fuente", vf.get()), ancho=30).pack(anchor="w")
            self._trazo_capas(p, esc)
        elif tipo == "imagen":
            self._titulo(p, "Imagen")
            fila = tk.Frame(p, bg=P["tarjeta"])
            fila.pack(fill="x")
            ruta = esc.get("ruta", "")
            self.lbl_ruta = tk.Label(fila, text=os.path.basename(ruta) or "Sin imagen", bg=P["tarjeta2"],
                                     fg=P["texto"], font=E.F_TEXTO, anchor="w", padx=8, pady=4)
            self.lbl_ruta.pack(side="left", fill="x", expand=True)
            E.Boton(fila, "Elegir…", self._elegir_imagen).pack(side="left", padx=(6, 0))
            E.etiqueta(p, "PNG con fondo transparente o imagen con fondo liso.", color=P["sutil"]).pack(anchor="w", pady=(4, 0))
            self._titulo(p, "Sensibilidad para separar el fondo")
            vu = tk.DoubleVar(value=float(esc.get("umbral", 60)))
            E.Deslizador(p, vu, 10, 220, 5, lambda: self._cambio("umbral", vu.get()), ancho=280, formato="{:.0f}").pack(anchor="w")
            vi = tk.BooleanVar(value=bool(esc.get("invertir", False)))
            E.Interruptor(p, "Invertir figura y fondo", vi, lambda: self._cambio("invertir", bool(vi.get()))).pack(anchor="w", pady=(6, 0))
            self._trazo_capas(p, esc)
        else:
            self._titulo(p, "Figura")
            nombres = list(C.FIGURAS.values())
            vfig = tk.StringVar(value=C.FIGURAS.get(esc.get("figura", "esfera")))
            inv = {v: k for k, v in C.FIGURAS.items()}

            def cambiar_fig():
                esc["figura"] = inv[vfig.get()]
                self._modificado()
                self._pintar_lista()
                self._pedir_previa()
            E.Menu(p, vfig, nombres, cambiar_fig, ancho=30).pack(anchor="w")

        self._titulo(p, "Colores de los LED", 16)
        modos = COLOR_POR_TIPO[tipo]
        if esc.get("color") not in modos:
            esc["color"] = modos[0]
        vm = tk.StringVar(value=C.MODOS_COLOR[esc["color"]])
        inv_m = {C.MODOS_COLOR[k]: k for k in modos}

        def cambiar_modo():
            self._cambio("color", inv_m[vm.get()])
            self._pintar_muestras()
        E.Menu(p, vm, [C.MODOS_COLOR[k] for k in modos], cambiar_modo, ancho=30).pack(anchor="w")
        self.muestras = tk.Canvas(p, bg=P["tarjeta"], highlightthickness=0, height=44)
        self.muestras.pack(fill="x", pady=(8, 0))
        self.muestras.bind("<Button-1>", self._clic_muestra)
        self.muestras.bind("<Configure>", lambda e: self._pintar_muestras())

        self._titulo(p, "Movimiento en el aire", 16)
        vmov = tk.StringVar(value=C.MOVIMIENTOS.get(esc.get("movimiento", "fija")))
        inv_mov = {v: k for k, v in C.MOVIMIENTOS.items()}
        E.Menu(p, vmov, list(C.MOVIMIENTOS.values()),
               lambda: self._cambio("movimiento", inv_mov[vmov.get()], previa=False), ancho=30).pack(anchor="w")
        self._titulo(p, "Efecto de luz")
        vef = tk.StringVar(value=C.EFECTOS.get(esc.get("efecto", "ninguno")))
        inv_ef = {v: k for k, v in C.EFECTOS.items()}
        E.Menu(p, vef, list(C.EFECTOS.values()),
               lambda: self._cambio("efecto", inv_ef[vef.get()], previa=False), ancho=30).pack(anchor="w")
        self._titulo(p, "Tiempo en el aire")
        vd = tk.DoubleVar(value=float(esc.get("duracion", 10)))
        E.Deslizador(p, vd, 3, 60, 1, lambda: self._cambio("duracion", vd.get(), previa=False), ancho=280,
                     formato="{:.0f}", unidad=" s").pack(anchor="w")
        self._titulo(p, "Ancho mínimo (0 = automático)")
        va = tk.DoubleVar(value=float(esc.get("ancho", 0)))
        E.Deslizador(p, va, 0, 200, 5, lambda: self._cambio("ancho", va.get()), ancho=280,
                     formato="{:.0f}", unidad=" m").pack(anchor="w")
        E.etiqueta(p, "El tamaño se calcula para respetar la separación mínima entre drones.",
                   color=P["sutil"], wraplength=280, justify="left").pack(anchor="w", pady=(2, 8))

    def _trazo_capas(self, p, esc):
        self._titulo(p, "Trazo")
        seg = E.Segmentado(p, [("relleno", "Relleno"), ("contorno", "Contorno")], esc.get("trazo", "relleno"),
                           lambda v: (seg.poner(v), self._cambio("trazo", v)))
        seg.pack(anchor="w")
        self._titulo(p, "Profundidad 3D (capas)")
        seg2 = E.Segmentado(p, [(1, "Plano"), (2, "2 capas"), (3, "3 capas")], int(esc.get("capas", 1)),
                            lambda v: (seg2.poner(v), self._cambio("capas", v)))
        seg2.pack(anchor="w")

    def _pintar_muestras(self):
        esc = self._esc()
        cv = getattr(self, "muestras", None)
        if esc is None or cv is None or not cv.winfo_exists():
            return
        cv.delete("all")
        usados = COLORES_USADOS.get(esc.get("color"), 0)
        cols = (esc.get("colores", []) + ["#ffffff"] * 3)[:3]
        if usados == 0:
            txt = {"imagen": "Cada dron toma el color de su punto en la imagen.",
                   "figura": "Paleta propia de la figura.",
                   "arcoiris": "Espectro completo de izquierda a derecha."}.get(esc.get("color"), "")
            cv.create_text(0, 22, text=txt, anchor="w", fill=P["tenue"], font=E.F_CHICA)
            return
        etiquetas = {"degradado": ["Izquierda", "Derecha"], "vertical": ["Abajo", "Arriba"],
                     "tres": ["Izquierda", "Centro", "Derecha"], "por_letra": ["Letra 1", "Letra 2", "Letra 3"],
                     "unico": ["Color"]}.get(esc.get("color"), ["Color"] * 3)
        for i in range(usados):
            x = i * 96
            cv.create_rectangle(x, 4, x + 30, 34, fill=cols[i], outline=P["borde"], width=1, tags=(f"m{i}",))
            cv.create_text(x + 38, 13, text=etiquetas[i], anchor="w", fill=P["tenue"], font=E.F_CHICA, tags=(f"m{i}",))
            cv.create_text(x + 38, 27, text=cols[i].upper(), anchor="w", fill=P["texto"], font=(E.SEMI, 8), tags=(f"m{i}",))

    def _clic_muestra(self, e):
        esc = self._esc()
        usados = COLORES_USADOS.get(esc.get("color"), 0)
        i = int(e.x // 96)
        if i >= usados:
            return
        cols = (esc.get("colores", []) + ["#ffffff"] * 3)[:3]
        r = colorchooser.askcolor(color=cols[i], parent=self, title="Color de los LED")
        if r and r[1]:
            cols[i] = r[1]
            self._cambio("colores", cols)
            self._pintar_muestras()

    def _elegir_imagen(self):
        r = filedialog.askopenfilename(parent=self, title="Elegir imagen",
                                       initialdir=C.EJEMPLOS,
                                       filetypes=[("Imágenes", "*.png *.jpg *.jpeg *.bmp *.gif *.webp"), ("Todos", "*.*")])
        if r:
            self._cambio("ruta", r)
            self.lbl_ruta.configure(text=os.path.basename(r))
            if not self._esc().get("nombre") or self._esc()["nombre"].startswith("Imagen"):
                self._esc()["nombre"] = os.path.splitext(os.path.basename(r))[0][:24]
            self._pintar_lista()

    def _cambio(self, clave, valor, previa=True):
        esc = self._esc()
        if esc is None or esc.get(clave) == valor:
            return
        esc[clave] = valor
        self._modificado()
        self._pintar_lista()
        if previa:
            self._pedir_previa()

    def _cambio_show(self, clave, valor, flota=False):
        if clave == "drones":
            valor = int(valor)
        self.show[clave] = valor
        self._modificado()
        if flota:
            self._pedir_previa()

    def _modificado(self):
        self.gen_plan += 1
        self._pintar_plan()
        if self._guardar_id:
            self.after_cancel(self._guardar_id)
        self._guardar_id = self.after(800, self._autoguardar)

    def _autoguardar(self):
        self._guardar_id = None
        try:
            os.makedirs(C.DATOS, exist_ok=True)
            with open(C.SHOW_ACTUAL, "w", encoding="utf-8") as f:
                json.dump(self.show, f, ensure_ascii=False, indent=1)
        except OSError:
            pass

    def _pedir_previa(self, inmediato=False):
        if self._prev_id:
            self.after_cancel(self._prev_id)
        self._prev_id = self.after(1 if inmediato else 380, self._enviar_previa)

    def _enviar_previa(self):
        self._prev_id = None
        esc = self._esc()
        if esc is None:
            return
        self.gen_prev += 1
        self.error_prev = ""
        self.tareas.put(("previa", self.gen_prev, copy.deepcopy(esc), int(self.show["drones"]),
                         float(self.show["separacion"])))
        self._mensaje("Generando formación…")

    def _trabajador(self):
        while True:
            t = self.tareas.get()
            try:
                if t[0] == "previa":
                    _, gen, esc, n, sep = t
                    if gen != self.gen_prev:
                        continue
                    clave = PL.clave_escena(esc, n, sep)
                    if clave not in self.cache:
                        self.cache[clave] = F.generar(esc, n, sep)
                    self.salida.put(("previa", gen, self.cache[clave]))
                elif t[0] == "plan":
                    _, gen, show, accion = t
                    plan = PL.construir_show(show, self.cache, avisar=lambda m: self.salida.put(("estado", m)))
                    plan.guardar(C.PLAN_ACTUAL)
                    self.salida.put(("plan", gen, plan, accion))
                elif t[0] == "exportar":
                    carpeta = t[1].exportar(avisar=lambda m: self.salida.put(("estado", m)))
                    self.salida.put(("exportado", carpeta))
            except Exception as ex:
                self.salida.put(("error", t[0], t[1] if len(t) > 1 else 0, str(ex)))

    def _sondear(self):
        try:
            while True:
                m = self.salida.get_nowait()
                if m[0] == "previa" and m[1] == self.gen_prev:
                    self.fo_prev = m[2]
                    self.error_prev = ""
                    self._mensaje("")
                    self._dibujar_previa(forzar=True)
                elif m[0] == "estado":
                    self._mensaje(m[1])
                elif m[0] == "plan":
                    _, gen, plan, accion = m
                    self.ocupado = ""
                    if gen == self.gen_plan:
                        self.plan, self.plan_gen = plan, gen
                    self._pintar_plan()
                    s = plan.stats
                    self._mensaje(("✓ Plan verificado: " if s["seguro"] else "⚠ Revisa: ")
                                  + f"separación mínima {s['min_sep']:.2f} m en {s['t_min_sep']:.0f} s · "
                                  + f"recorrido medio {s['recorrido_medio']:.0f} m por dron")
                    if accion == "ver":
                        self._lanzar_visor()
                    elif accion == "exportar":
                        self._exportar()
                elif m[0] == "exportado":
                    self.ocupado = ""
                    self._mensaje(f"Trayectorias exportadas en {m[1]}")
                    try:
                        os.startfile(m[1])
                    except OSError:
                        pass
                elif m[0] == "error":
                    if m[1] == "previa":
                        if m[2] == self.gen_prev:
                            self.error_prev = m[3]
                            self.fo_prev = None
                            self._dibujar_previa(forzar=True)
                            self._mensaje("")
                    else:
                        self.ocupado = ""
                        self._mensaje(f"Error: {m[3]}")
                        messagebox.showerror("Espectáculo de drones", m[3], parent=self)
        except queue.Empty:
            pass
        self.after(60, self._sondear)

    def _mensaje(self, txt):
        self.estado.configure(text=txt)

    def _calcular(self, accion=None):
        if self.ocupado:
            return
        if self.plan is not None and self.plan_gen == self.gen_plan and accion is not None:
            if accion == "ver":
                self._lanzar_visor()
            return
        self.ocupado = "plan"
        self._mensaje("Calculando plan de vuelo…")
        self.tareas.put(("plan", self.gen_plan, copy.deepcopy(self.show), accion))

    def _ver(self):
        self._autoguardar()
        self._calcular("ver")

    def _lanzar_visor(self):
        visor = os.path.join(C.RAIZ, "visor.py")
        exe = sys.executable
        if exe.lower().endswith("pythonw.exe"):
            exe = exe[:-5] + ".exe" if os.path.exists(exe[:-5] + ".exe") else exe
        subprocess.Popen([exe, visor, C.PLAN_ACTUAL], cwd=C.RAIZ)
        self._mensaje("Abriendo el visor 3D… (Espacio pausa · C cambia la cámara · F9 graba video)")

    def _exportar(self):
        if self.ocupado:
            return
        if self.plan is None or self.plan_gen != self.gen_plan:
            self._calcular("exportar")
            return
        self.ocupado = "exportar"
        self.tareas.put(("exportar", self.plan))

    def _nuevo(self):
        if not messagebox.askyesno("Nuevo show", "¿Empezar un show nuevo con el ejemplo?", parent=self):
            return
        self._poner_show(copy.deepcopy(SHOW_EJEMPLO))

    def _poner_show(self, show):
        self.show = PL.normalizar_show(show)
        self.v_nombre.set(self.show["nombre"])
        for k, (v, d) in self.desl.items():
            v.set(float(self.show[k]))
            d._pintar()
        self.plan = None
        self._modificado()
        self._seleccionar(0)

    def _abrir(self):
        r = filedialog.askopenfilename(parent=self, title="Abrir show", initialdir=C.SHOWS,
                                       filetypes=[("Show de drones", "*.json")])
        if not r:
            return
        try:
            with open(r, encoding="utf-8") as f:
                self._poner_show(json.load(f))
        except (OSError, ValueError) as ex:
            messagebox.showerror("Abrir show", str(ex), parent=self)

    def _guardar_como(self):
        os.makedirs(C.SHOWS, exist_ok=True)
        nombre = "".join(ch for ch in self.show["nombre"] if ch.isalnum() or ch in " -_").strip() or "show"
        r = filedialog.asksaveasfilename(parent=self, title="Guardar show", initialdir=C.SHOWS,
                                         initialfile=nombre + ".json", defaultextension=".json",
                                         filetypes=[("Show de drones", "*.json")])
        if r:
            with open(r, "w", encoding="utf-8") as f:
                json.dump(self.show, f, ensure_ascii=False, indent=1)
            self._mensaje(f"Show guardado en {r}")

    def _pintar_plan(self):
        cv = self.ind
        w = max(cv.winfo_width(), 200)
        valido = self.plan is not None and self.plan_gen == self.gen_plan
        s = self.plan.stats if self.plan is not None else {}
        n = int(self.show["drones"])
        est = sum(e.get("duracion", 10) for e in self.show["escenas"])
        if valido:
            datos = [("Duración", PL_mmss(s["duracion"]), P["acento"], None),
                     ("Drones", f"{s['drones']}", P["azul"], None),
                     ("Sep. mínima", f"{s['min_sep']:.2f} m", P["verde"] if s["seguro"] else P["rojo"], None),
                     ("Vel. máxima", f"{s['vel_max']:.1f} m/s", P["morado"], None),
                     ("Altitud máx.", f"{s['alt_max']:.0f} m", P["cian"], None),
                     ("Batería final", f"{s['bateria_final']:.0f} %", P["verde"] if s["bateria_final"] > 25 else P["rojo"],
                      s["bateria_final"] / 100)]
        else:
            datos = [("Duración", "—", P["sutil"], None), ("Drones", f"{n}", P["azul"], None),
                     ("Sep. mínima", "—", P["sutil"], None), ("Vel. máxima", "—", P["sutil"], None),
                     ("Altitud máx.", "—", P["sutil"], None), ("En escenas", PL_mmss(est), P["sutil"], None)]
        E.indicadores(cv, datos, 6, w)
        lc = self.linea
        lc.delete("all")
        lw = max(lc.winfo_width(), 200)
        if valido:
            dur = self.plan.duracion
            for sg in self.plan.seg:
                x0 = lw * sg["t0"] / dur
                x1 = lw * sg["t1"] / dur
                col = C.FASES.get(sg["fase"], ("", P["gris"]))[1]
                lc.create_rectangle(x0, 22, max(x1 - 1, x0 + 1), 34, fill=col, outline="")
                if sg["fase"] == "formacion" and x1 - x0 > 30:
                    lc.create_text((x0 + x1) / 2, 12, text=sg["nombre"][:int((x1 - x0) / 7)], fill=P["texto"],
                                   font=E.F_CHICA)
            for k in range(0, int(dur) + 1, 30):
                lc.create_text(lw * k / dur, 42, text=PL_mmss(k), fill=P["sutil"], font=(E.FAMILIA, 7), anchor="n")
        else:
            lc.create_text(lw / 2, 22, text="Presiona «Calcular y verificar» o «Ver show en 3D» para generar el plan",
                           fill=P["sutil"], font=E.F_CHICA)

    def _fondo_prev(self, W, H):
        if self._fondo is not None and self._fondo.size == (W, H):
            return self._fondo
        y = np.linspace(0, 1, H)[:, None]
        top = np.array([4, 6, 14])
        bot = np.array([22, 18, 34])
        g = (top + (bot - top) * y ** 1.6)[:, None, :] * np.ones((1, W, 1))
        rng = np.random.default_rng(3)
        img = g.astype(np.uint8)
        for _ in range(int(W * H / 2500)):
            x, yy = rng.integers(0, W), rng.integers(0, int(H * 0.8))
            v = int(rng.uniform(60, 180))
            img[yy, x] = (v, v, min(255, v + 20))
        self._fondo = Image.fromarray(img, "RGB")
        return self._fondo

    def _animar(self):
        ahora = time.perf_counter()
        dt = ahora - self.ultimo
        self.ultimo = ahora
        fo = self.fo_prev
        esc = self._esc()
        if fo is not None and esc is not None and (not fo["plano"]):
            self.ang += dt * 0.6
            self._dibujar_previa()
        self.after(45, self._animar)

    def _dibujar_previa(self, forzar=False):
        cv = self.previa
        W, H = max(cv.winfo_width(), 50), max(cv.winfo_height(), 50)
        base = self._fondo_prev(W, H).copy()
        fo = self.fo_prev
        cv.delete("chip")
        if fo is None:
            self._foto = ImageTk.PhotoImage(base)
            cv.itemconfigure(self.img_prev, image=self._foto)
            if self.error_prev:
                _chip(cv, W / 2, H / 2, "⚠  " + self.error_prev, P["rojo"], centro=True)
            else:
                _chip(cv, W / 2, H / 2, "Generando formación…", P["tenue"], centro=True)
            return
        pos, col = fo["pos"], fo["col"]
        if fo["plano"]:
            yaw, pitch = 0.0, 0.0
        else:
            yaw, pitch = self.ang, 0.22
        cy, sy = math.cos(yaw), math.sin(yaw)
        x = pos[:, 0] * cy - pos[:, 1] * sy
        y = pos[:, 0] * sy + pos[:, 1] * cy
        cp, sp = math.cos(pitch), math.sin(pitch)
        z = pos[:, 2] * cp - y * sp
        prof = y * cp + pos[:, 2] * sp
        if fo["plano"]:
            ancho = np.ptp(pos[:, 0]) + 4
        else:
            ancho = 2 * float(np.max(np.hypot(pos[:, 0], pos[:, 1]))) + 4
        alto = float(np.max(np.linalg.norm(pos, axis=1))) * 2 + 4 if not fo["plano"] else np.ptp(pos[:, 2]) + 4
        esc_px = min((W - 70) / ancho, (H - 80) / alto)
        px = W / 2 + x * esc_px
        py = H / 2 + 10 - z * esc_px
        orden = np.argsort(-prof)
        r = float(np.clip(float(self.show["separacion"]) * esc_px * 0.2, 1.3, 4.5))
        brillo = Image.new("RGB", (W, H))
        db = ImageDraw.Draw(brillo)
        c255 = np.clip(col * 255, 0, 255).astype(int)
        rg = r * 2.6
        for i in orden:
            c = c255[i]
            db.ellipse((px[i] - rg, py[i] - rg, px[i] + rg, py[i] + rg), fill=(int(c[0] * 0.55), int(c[1] * 0.55), int(c[2] * 0.55)))
        brillo = brillo.filter(ImageFilter.GaussianBlur(r * 1.8))
        img = ImageChops.add(base, brillo)
        d = ImageDraw.Draw(img)
        for i in orden:
            c = c255[i]
            cc = (min(255, int(c[0] * 0.75 + 70)), min(255, int(c[1] * 0.75 + 70)), min(255, int(c[2] * 0.75 + 70)))
            d.ellipse((px[i] - r, py[i] - r, px[i] + r, py[i] + r), fill=cc)
        self._foto = ImageTk.PhotoImage(img)
        cv.itemconfigure(self.img_prev, image=self._foto)
        tw, th, tp = fo["tam"]
        xx = 12
        for txt, color in ((f"{len(pos)} drones", P["azul"]),
                           (f"{tw:.0f} × {th:.0f} × {tp:.0f} m", P["texto"]),
                           (f"separación mín. {fo['min_sep']:.2f} m", P["verde"] if fo["min_sep"] >= C.SEP_SEGURA else P["rojo"]),
                           ("3D · girando" if not fo["plano"] else "Plano frente al público", P["tenue"])):
            xx += _chip(cv, xx, 12, txt, color) + 6

    def _cerrar(self):
        self.grabar.cerrar()
        self._autoguardar()
        self.destroy()


def _chip(cv, x, y, texto, color, centro=False):
    t = cv.create_text(x, y, text=texto, fill=color, font=(E.SEMI, 9), anchor="center" if centro else "nw",
                       tags=("chip",))
    x0, y0, x1, y1 = cv.bbox(t)
    r = cv.create_rectangle(x0 - 8, y0 - 4, x1 + 8, y1 + 4, fill="#0e1014", outline=E.mezclar(color, "#0e1014", 0.4),
                            tags=("chip",))
    cv.tag_lower(r, t)
    if not centro:
        cv.move(t, 8, 4)
        cv.move(r, 8, 4)
    return x1 - x0 + 16


def PL_mmss(t):
    t = max(0, int(round(t)))
    return f"{t // 60}:{t % 60:02d}"


def main():
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass
    app = Editor()
    app.mainloop()


if __name__ == "__main__":
    main()
