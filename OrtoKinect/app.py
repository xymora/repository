import argparse
import math
import os
import threading
import time
import tkinter as tk
from collections import deque
from datetime import datetime
from tkinter import ttk, messagebox, filedialog

import numpy as np
import cv2

from vision import Rastreador
from biomecanica import Cuerpo, HUESOS, LADO_PUNTO, NOMBRE_LADO, LADOS, FEM
import pruebas as PR
from datos import Almacen, TIPOS, edad_de, dias_desde, imc, fecha_de
from fuentes import FuenteKinect, FuenteSimulada, FuenteCamara

try:
    import winsound
except ImportError:
    winsound = None

FONDO = "#0e1116"
PANEL = "#151a21"
TARJETA = "#1c222b"
TARJETA2 = "#262d38"
BORDE = "#323b49"
TEXTO = "#e8ecf2"
TENUE = "#8b95a7"
ACENTO = "#35b7c8"
VERDE = "#2fbf71"
AMARILLO = "#f0b429"
ROJO = "#e5534b"
COL_LADO = {"izq": "#4aa8ff", "der": "#ff9f43"}
BGR_LADO = {"izq": (255, 168, 74), "der": (67, 159, 255), None: (200, 200, 200)}
VW, VH = 640, 480
GH = 128
CUENTA = 3.0
SEXOS = [("F", "Femenino"), ("M", "Masculino")]
LADOS_AF = [("izq", "Izquierdo"), ("der", "Derecho"), ("bilateral", "Bilateral"), ("ninguno", "Ninguno")]
VISTAS = [("auto", "Automático"), ("color", "Color"), ("ir", "Infrarrojo"), ("prof", "Profundidad")]


def a_foto(bgr):
    h, w = bgr.shape[:2]
    return tk.PhotoImage(data=b"P6 %d %d 255 " % (w, h) + np.ascontiguousarray(bgr[..., ::-1]).tobytes(), format="PPM")


def pitar(frec=880, ms=90, veces=1):
    if winsound is None:
        return

    def f():
        for _ in range(veces):
            try:
                winsound.Beep(frec, ms)
            except RuntimeError:
                pass
            time.sleep(0.05)
    threading.Thread(target=f, daemon=True).start()


def color_pct(p):
    if p is None:
        return TENUE
    return VERDE if p >= 90 else (AMARILLO if p >= 66 else ROJO)


class App:
    def __init__(self, fuente, aviso=""):
        self.fuente = fuente
        self.sim = isinstance(fuente, FuenteSimulada)
        self.alm = Almacen()
        self.rast = Rastreador()
        if not self.sim:
            self.rast._estimador()
        self.raiz = tk.Tk()
        self.raiz.title("OrtoKinect — Traumatología, Ortopedia y Rehabilitación")
        self.raiz.configure(bg=FONDO)
        self.raiz.resizable(False, False)
        self.raiz.geometry("1492x759+8+8")
        self.paciente = None
        self.prueba_id = "hombro_abd"
        self.lado = tk.StringVar(value="izq")
        self.reps = tk.IntVar(value=5)
        self.prueba = None
        self.fase = "libre"
        self.t_cuenta = 0.0
        self.resultado = None
        self.vista = "auto"
        self.brillo = None
        self.t_oscuro = None
        self.t_ir = 0.0
        self.sondeo = None
        self.cuadro = None
        self.cuerpo = None
        self.foto = None
        self.flash = None
        self.hist = deque()
        self.fps = 0.0
        self.n_cuadros = 0
        self.t_fps = time.time()
        self.t_persona = 0.0
        self.led_actual = None
        self.vivo = True
        self.pagina = None
        self._estilo()
        self._construir()
        self.raiz.bind("<space>", lambda e: self._espacio(e))
        self.raiz.bind("<Escape>", lambda e: self.cancelar())
        self.raiz.bind("<Up>", lambda e: self._inclinar(3, e))
        self.raiz.bind("<Down>", lambda e: self._inclinar(-3, e))
        self.raiz.protocol("WM_DELETE_WINDOW", self.cerrar)
        pac = self.alm.listar()
        if pac:
            self.elegir_paciente(pac[0]["id"], cambiar=False)
        self.seleccionar_prueba(self.prueba_id)
        self.mostrar("eval")
        if aviso:
            self.lbl_aviso.configure(text=aviso)
        self.raiz.after(20, self.ciclo)

    def _estilo(self):
        s = ttk.Style(self.raiz)
        s.theme_use("clam")
        s.configure("TCombobox", fieldbackground=TARJETA2, background=TARJETA2, foreground=TEXTO, arrowcolor=TEXTO,
                    bordercolor=BORDE, lightcolor=TARJETA2, darkcolor=TARJETA2, selectbackground=TARJETA2, selectforeground=TEXTO)
        s.map("TCombobox", fieldbackground=[("readonly", TARJETA2)], foreground=[("readonly", TEXTO)])
        self.raiz.option_add("*TCombobox*Listbox.background", TARJETA2)
        self.raiz.option_add("*TCombobox*Listbox.foreground", TEXTO)
        self.raiz.option_add("*TCombobox*Listbox.selectBackground", ACENTO)
        s.configure("Treeview", background=TARJETA, fieldbackground=TARJETA, foreground=TEXTO, bordercolor=BORDE, rowheight=22,
                    font=("Segoe UI", 9))
        s.configure("Treeview.Heading", background=TARJETA2, foreground=TEXTO, font=("Segoe UI", 9, "bold"), bordercolor=BORDE)
        s.map("Treeview", background=[("selected", ACENTO)], foreground=[("selected", "#0b0d12")])
        s.configure("Vertical.TScrollbar", background=TARJETA2, troughcolor=TARJETA, bordercolor=TARJETA, arrowcolor=TEXTO)

    def _boton(self, padre, txt, cmd, primario=False, **kw):
        bg = ACENTO if primario else TARJETA2
        fg = "#071014" if primario else TEXTO
        b = tk.Button(padre, text=txt, command=cmd, bg=bg, fg=fg, activebackground=BORDE, activeforeground=TEXTO, relief="flat",
                      bd=0, padx=kw.pop("padx", 12), pady=kw.pop("pady", 5), font=kw.pop("font", ("Segoe UI", 9, "bold")),
                      cursor="hand2", **kw)
        b._prim = primario
        return b

    def _tarjeta(self, padre, **kw):
        return tk.Frame(padre, bg=TARJETA, padx=kw.pop("padx", 12), pady=kw.pop("pady", 10), **kw)

    def _titulo(self, padre, txt, sub=None):
        tk.Label(padre, text=txt, bg=padre["bg"], fg=TEXTO, font=("Segoe UI", 11, "bold"), anchor="w").pack(fill="x")
        if sub:
            tk.Label(padre, text=sub, bg=padre["bg"], fg=TENUE, font=("Segoe UI", 8), anchor="w").pack(fill="x")

    def _construir(self):
        r = self.raiz
        cab = tk.Frame(r, bg=PANEL, height=50)
        cab.pack(fill="x")
        cab.pack_propagate(False)
        logo = tk.Canvas(cab, width=34, height=34, bg=PANEL, highlightthickness=0)
        logo.pack(side="left", padx=(14, 6))
        logo.create_oval(2, 2, 32, 32, fill=ACENTO, outline="")
        logo.create_rectangle(14, 8, 20, 26, fill="#071014", outline="")
        logo.create_rectangle(8, 14, 26, 20, fill="#071014", outline="")
        tk.Label(cab, text="OrtoKinect", bg=PANEL, fg=TEXTO, font=("Segoe UI", 16, "bold")).pack(side="left")
        tk.Label(cab, text="  Traumatología · Ortopedia · Rehabilitación", bg=PANEL, fg=TENUE, font=("Segoe UI", 10)).pack(side="left", pady=(4, 0))
        self.lbl_fuente = tk.Label(cab, text="", bg=PANEL, fg=TENUE, font=("Segoe UI", 9))
        self.lbl_fuente.pack(side="right", padx=14)
        self.lbl_pac = tk.Label(cab, text="Sin paciente seleccionado", bg=TARJETA2, fg=TEXTO, font=("Segoe UI", 9, "bold"), padx=10, pady=4,
                                cursor="hand2")
        self.lbl_pac.pack(side="right", padx=6)
        self.lbl_pac.bind("<Button-1>", lambda e: self.mostrar("pac"))
        cuerpo = tk.Frame(r, bg=FONDO)
        cuerpo.pack(fill="both", expand=True)
        nav = tk.Frame(cuerpo, bg=PANEL, width=132)
        nav.pack(side="left", fill="y")
        nav.pack_propagate(False)
        self.nav = {}
        for clave, txt in (("pac", "Pacientes"), ("eval", "Evaluación"), ("prog", "Progreso")):
            b = tk.Button(nav, text=txt, anchor="w", command=lambda c=clave: self.mostrar(c), bg=PANEL, fg=TENUE,
                          activebackground=TARJETA2, activeforeground=TEXTO, relief="flat", bd=0, padx=16, pady=10,
                          font=("Segoe UI", 10, "bold"), cursor="hand2")
            b.pack(fill="x", pady=(12 if clave == "pac" else 2, 0))
            self.nav[clave] = b
        tk.Label(nav, text="Herramienta de apoyo.\nNo sustituye la\nvaloración clínica.", bg=PANEL, fg=TENUE, justify="left",
                 font=("Segoe UI", 7)).pack(side="bottom", anchor="w", padx=12, pady=10)
        self.cont = tk.Frame(cuerpo, bg=FONDO)
        self.cont.pack(side="left", fill="both", expand=True, padx=12, pady=10)
        self.paginas = {"eval": self._pag_eval(), "pac": self._pag_pacientes(), "prog": self._pag_progreso()}

    def mostrar(self, clave):
        for k, f in self.paginas.items():
            f.place_forget()
        self.paginas[clave].place(x=0, y=0, relwidth=1, relheight=1)
        for k, b in self.nav.items():
            b.configure(bg=TARJETA2 if k == clave else PANEL, fg=TEXTO if k == clave else TENUE)
        self.pagina = clave
        if clave == "prog":
            self.refrescar_progreso()
        if clave == "pac":
            self.refrescar_lista()

    def _pag_eval(self):
        pag = tk.Frame(self.cont, bg=FONDO)
        izq = tk.Frame(pag, bg=FONDO)
        izq.pack(side="left", anchor="n")
        self.video = tk.Canvas(izq, width=VW, height=VH, bg="#000000", highlightthickness=2, highlightbackground=BORDE)
        self.video.pack()
        self.img_id = self.video.create_image(0, 0, anchor="nw")
        barra = tk.Frame(izq, bg=FONDO)
        barra.pack(fill="x", pady=(6, 0))
        tk.Label(barra, text="Imagen", bg=FONDO, fg=TENUE, font=("Segoe UI", 9)).pack(side="left", padx=(0, 6))
        self.b_vista = {}
        for c, t in VISTAS:
            b = self._boton(barra, t, lambda c=c: self.poner_vista(c), padx=9, pady=3)
            b.pack(side="left", padx=(0, 4))
            self.b_vista[c] = b
        self.lbl_3d = tk.Label(barra, text="", bg=FONDO, fg=TENUE, font=("Segoe UI", 8))
        self.lbl_3d.pack(side="right")
        self.graf = tk.Canvas(izq, width=VW, height=GH, bg=TARJETA, highlightthickness=0)
        self.graf.pack(pady=(6, 0))
        der = tk.Frame(pag, bg=FONDO)
        der.pack(side="left", fill="both", expand=True, padx=(12, 0))
        sel = self._tarjeta(der, pady=8)
        sel.pack(fill="x")
        fila = tk.Frame(sel, bg=TARJETA)
        fila.pack(fill="x")
        self.b_region = {}
        for reg in PR.REGIONES:
            b = tk.Button(fila, text=reg, command=lambda g=reg: self.poner_region(g), bg=TARJETA, fg=TENUE, relief="flat", bd=0,
                          activebackground=TARJETA2, activeforeground=TEXTO, padx=7, pady=3, font=("Segoe UI", 9, "bold"), cursor="hand2")
            b.pack(side="left", padx=(0, 2))
            self.b_region[reg] = b
        self.fila_pruebas = tk.Frame(sel, bg=TARJETA)
        self.fila_pruebas.pack(fill="x", pady=(6, 0))
        fila2 = tk.Frame(sel, bg=TARJETA)
        fila2.pack(fill="x", pady=(8, 0))
        self.lbl_lado = tk.Label(fila2, text="Lado", bg=TARJETA, fg=TENUE, font=("Segoe UI", 9))
        self.lbl_lado.pack(side="left", padx=(0, 6))
        self.r_lado = {}
        for c, t in (("izq", "Izquierdo"), ("der", "Derecho"), ("ambos", "Ambos")):
            rb = tk.Radiobutton(fila2, text=t, value=c, variable=self.lado, command=self._cambio_lado, indicatoron=False, bg=TARJETA2,
                                fg=TEXTO, selectcolor=ACENTO, activebackground=BORDE, activeforeground=TEXTO, relief="flat", bd=0,
                                padx=10, pady=3, font=("Segoe UI", 9, "bold"), cursor="hand2")
            rb.pack(side="left", padx=(0, 3))
            self.r_lado[c] = rb
        self.f_reps = tk.Frame(fila2, bg=TARJETA)
        self.f_reps.pack(side="left", padx=(14, 0))
        tk.Label(self.f_reps, text="Repeticiones", bg=TARJETA, fg=TENUE, font=("Segoe UI", 9)).pack(side="left", padx=(0, 4))
        tk.Spinbox(self.f_reps, from_=1, to=15, textvariable=self.reps, width=3, bg=TARJETA2, fg=TEXTO, buttonbackground=TARJETA2,
                   relief="flat", font=("Segoe UI", 10), insertbackground=TEXTO).pack(side="left")
        self.b_rutina = self._boton(fila2, "Siguiente de la rutina ▶", self.siguiente_rutina, padx=8, pady=3)
        self.b_rutina.pack(side="right")
        self.lbl_instr = tk.Label(der, text="", bg=FONDO, fg=TEXTO, font=("Segoe UI", 9), justify="left", anchor="w", wraplength=640)
        self.lbl_instr.pack(fill="x", pady=(8, 6))
        self.vivo_c = tk.Canvas(der, width=660, height=190, bg=TARJETA, highlightthickness=0)
        self.vivo_c.pack(anchor="w")
        ctl = tk.Frame(der, bg=FONDO)
        ctl.pack(fill="x", pady=(8, 0))
        self.b_iniciar = self._boton(ctl, "▶  Iniciar prueba  (espacio)", self.iniciar, primario=True, padx=16, pady=7,
                                     font=("Segoe UI", 10, "bold"))
        self.b_iniciar.pack(side="left")
        self._boton(ctl, "■  Terminar", self.terminar, padx=12, pady=7).pack(side="left", padx=6)
        self._boton(ctl, "✕  Cancelar", self.cancelar, padx=12, pady=7).pack(side="left")
        self.lbl_aviso = tk.Label(ctl, text="", bg=FONDO, fg=TENUE, font=("Segoe UI", 8), wraplength=250, justify="left")
        self.lbl_aviso.pack(side="left", padx=10)
        res = self._tarjeta(der, pady=8)
        res.pack(fill="both", expand=True, pady=(8, 0))
        top = tk.Frame(res, bg=TARJETA)
        top.pack(fill="x")
        tk.Label(top, text="Resultado", bg=TARJETA, fg=TEXTO, font=("Segoe UI", 11, "bold")).pack(side="left")
        self.b_guardar = self._boton(top, "Guardar en el expediente", self.guardar, primario=True, padx=12, pady=4)
        self.b_guardar.pack(side="right")
        self.txt_res = tk.Text(res, height=6, bg=TARJETA, fg=TEXTO, relief="flat", font=("Segoe UI", 9), wrap="word",
                               highlightthickness=0, padx=2)
        self.txt_res.pack(fill="both", expand=True, pady=(4, 4))
        self.txt_res.tag_configure("b", font=("Segoe UI", 9, "bold"), foreground=ACENTO)
        self.txt_res.tag_configure("t", foreground=TENUE)
        pie = tk.Frame(res, bg=TARJETA)
        pie.pack(fill="x")
        tk.Label(pie, text="Dolor durante la prueba (EVA)", bg=TARJETA, fg=TENUE, font=("Segoe UI", 9)).pack(side="left")
        self.dolor = tk.IntVar(value=0)
        self.esc_dolor = tk.Scale(pie, from_=0, to=10, orient="horizontal", variable=self.dolor, length=170, bg=TARJETA, fg=TEXTO,
                                  troughcolor=TARJETA2, highlightthickness=0, bd=0, showvalue=True, font=("Segoe UI", 8))
        self.esc_dolor.pack(side="left", padx=(6, 10))
        tk.Label(pie, text="Nota", bg=TARJETA, fg=TENUE, font=("Segoe UI", 9)).pack(side="left")
        self.nota = tk.Entry(pie, bg=TARJETA2, fg=TEXTO, relief="flat", insertbackground=TEXTO, font=("Segoe UI", 9))
        self.nota.pack(side="left", fill="x", expand=True, padx=(6, 0), ipady=3)
        self._mostrar_resultado(None)
        return pag

    def poner_region(self, reg):
        for k, b in self.b_region.items():
            b.configure(bg=TARJETA2 if k == reg else TARJETA, fg=TEXTO if k == reg else TENUE)
        for w in self.fila_pruebas.winfo_children():
            w.destroy()
        for sp in PR.ROM + PR.OTRAS:
            if sp["region"] != reg:
                continue
            act = sp["id"] == self.prueba_id
            b = self._boton(self.fila_pruebas, sp["nombre"], lambda i=sp["id"]: self.seleccionar_prueba(i), primario=act, padx=9, pady=4)
            b.pack(side="left", padx=(0, 4))

    def seleccionar_prueba(self, pid):
        if self.fase in ("cuenta", "midiendo"):
            return
        self.prueba_id = pid
        sp = PR.CATALOGO[pid]
        self.poner_region(sp["region"])
        tipo = sp["tipo"]
        if "defecto" in sp:
            self.lado.set(sp["defecto"])
        elif tipo == "equilibrio" and self.lado.get() == "ambos":
            self.lado.set("izq")
        con_lado = tipo in PR.CON_LADO
        for c, rb in self.r_lado.items():
            rb.configure(state="normal" if con_lado and not (tipo == "equilibrio" and c == "ambos") else "disabled")
        self.lbl_lado.configure(text="Pierna de apoyo" if tipo == "equilibrio" else "Lado")
        if tipo == "rom":
            self.f_reps.pack(side="left", padx=(14, 0))
        else:
            self.f_reps.pack_forget()
        extra = ""
        if tipo == "rom":
            extra = f"   Normal: {sp['normal']}° · funcional: {sp['funcional']}°"
        self.lbl_instr.configure(text=sp["instr"] + extra)
        self.hist.clear()
        if self.fase == "resultado":
            self.fase = "libre"
        self.fuente.programa(pid, self.lado.get())
        self._rutina_lbl()

    def _cambio_lado(self):
        self.hist.clear()
        self.fuente.programa(self.prueba_id, self.lado.get())

    def _rutina(self):
        return [p for p in (self.paciente or {}).get("plan", []) if p in PR.CATALOGO]

    def _rutina_lbl(self):
        plan = self._rutina()
        if not plan:
            self.b_rutina.configure(text="Sin rutina asignada", state="disabled")
            return
        i = plan.index(self.prueba_id) + 1 if self.prueba_id in plan else 0
        sig = plan[i % len(plan)]
        self.b_rutina.configure(text=f"Rutina {min(i, len(plan))}/{len(plan)} · siguiente: {PR.CATALOGO[sig]['nombre']} ▶", state="normal")

    def siguiente_rutina(self):
        plan = self._rutina()
        if not plan:
            return
        i = plan.index(self.prueba_id) + 1 if self.prueba_id in plan else 0
        self.seleccionar_prueba(plan[i % len(plan)])

    def poner_vista(self, c):
        self.vista = c
        for k, b in self.b_vista.items():
            b.configure(bg=ACENTO if k == c else TARJETA2, fg="#071014" if k == c else TEXTO)
        self.sondeo = None
        if c == "color":
            self.fuente.modo_video(False)
        elif c == "ir":
            self.fuente.modo_video(True)
            self.t_ir = time.time()

    def _inclinar(self, d, e):
        if isinstance(e.widget, (tk.Entry, tk.Text, tk.Spinbox)):
            return
        self.fuente.inclinar(d)
        self.rast.olvidar_suelo()

    def _espacio(self, e):
        if isinstance(e.widget, (tk.Entry, tk.Text, tk.Spinbox, ttk.Combobox)) or self.pagina != "eval":
            return
        if self.fase in ("cuenta", "midiendo"):
            self.terminar()
        else:
            self.iniciar()

    def iniciar(self):
        if self.fase in ("cuenta", "midiendo"):
            return
        perfil = self.paciente or {}
        self.prueba = PR.crear(self.prueba_id, self.lado.get(), perfil, max(1, int(self.reps.get() or 5)))
        self.fase = "cuenta"
        self.t_cuenta = time.time()
        self.resultado = None
        self._mostrar_resultado(None)
        self.dolor.set(0)
        self.nota.delete(0, "end")
        self.hist.clear()
        pitar(660, 80)

    def terminar(self):
        if self.fase == "cuenta":
            self.cancelar()
        elif self.fase == "midiendo" and self.prueba is not None:
            self._finalizar()

    def cancelar(self):
        if self.fase in ("cuenta", "midiendo"):
            self.fase = "libre"
            self.prueba = None
            self.lbl_aviso.configure(text="Prueba cancelada")

    def _finalizar(self):
        self.resultado = self.prueba.resultado()
        self.resultado["prueba"] = self.prueba_id
        self.resultado["lado"] = self.lado.get()
        self.fase = "resultado"
        self._mostrar_resultado(self.resultado)
        pitar(1046, 120, 2)

    def _mostrar_resultado(self, r):
        t = self.txt_res
        t.configure(state="normal")
        t.delete("1.0", "end")
        if r is None:
            t.insert("end", "Elige una prueba, colócate frente al Kinect y pulsa Iniciar.\n", "t")
            t.insert("end", "Al terminar verás aquí los hallazgos; puedes anotar el dolor y guardarlos en el expediente del paciente.", "t")
            self.b_guardar.configure(state="disabled", bg=TARJETA2)
        else:
            sp = PR.CATALOGO[r["prueba"]]
            lado = NOMBRE_LADO.get(r["lado"], "") if sp["tipo"] in PR.CON_LADO else ""
            t.insert("end", f"{sp['nombre']}" + (f" · {lado}" if lado else "") + "\n", "b")
            for h in r["hallazgos"]:
                t.insert("end", "•  " + h + "\n")
            self.b_guardar.configure(state="normal", bg=ACENTO)
        t.configure(state="disabled")

    def guardar(self):
        if self.resultado is None:
            return
        if self.paciente is None:
            messagebox.showinfo("OrtoKinect", "Primero selecciona o crea un paciente en la sección Pacientes.", parent=self.raiz)
            self.mostrar("pac")
            return
        r = dict(self.resultado)
        r["nombre"] = PR.CATALOGO[r["prueba"]]["nombre"]
        r["dolor"] = int(self.dolor.get())
        r["nota"] = self.nota.get().strip()
        r["fuente"] = self.fuente.nombre
        r["modo3d"] = self.rast.modo3d
        self.alm.agregar(self.paciente["id"], r)
        self.lbl_aviso.configure(text=f"Guardado en el expediente de {self.paciente['nombre']} · {datetime.now():%H:%M}")
        self.b_guardar.configure(state="disabled", bg=TARJETA2)
        if r["prueba"] == "antropometria" and r["metricas"].get("estatura"):
            e = round(r["metricas"]["estatura"] * 100)
            if messagebox.askyesno("OrtoKinect", f"¿Actualizar la estatura del perfil a {e} cm?", parent=self.raiz):
                p = dict(self.paciente)
                p["estatura_cm"] = str(e)
                self.paciente = self.alm.guardar(p)
                self._chip()
        self.resultado = None
        self.fase = "libre"

    def _automatico(self, c, ahora):
        if self.vista != "auto" or not isinstance(self.fuente, FuenteKinect):
            return
        ocupado = self.fase in ("cuenta", "midiendo")
        if c.tipo == "color":
            g = cv2.cvtColor(c.img[::8, ::8], cv2.COLOR_BGR2GRAY)
            b = float(g.mean())
            self.brillo = b if self.brillo is None else self.brillo + (b - self.brillo) * 0.3
            if self.sondeo is not None:
                if ahora - self.sondeo > 1.0:
                    self.sondeo = None
                    if self.brillo < 40:
                        self.fuente.modo_video(True)
                        self.t_ir = ahora
                return
            if self.brillo < 28:
                self.t_oscuro = self.t_oscuro or ahora
                if ahora - self.t_oscuro > 1.5:
                    self.fuente.modo_video(True)
                    self.t_ir = ahora
                    self.t_oscuro = None
            else:
                self.t_oscuro = None
        elif c.tipo == "ir" and not ocupado and ahora - self.t_ir > 12 and self.cuerpo is None:
            self.sondeo = ahora
            self.brillo = None
            self.fuente.modo_video(False)

    def ciclo(self):
        if not self.vivo:
            return
        ahora = time.time()
        c = self.fuente.leer()
        if c is not None:
            self.cuadro = c
            self.n_cuadros += 1
            self._automatico(c, ahora)
            self.rast.procesar(c)
            if self.rast.nuevo:
                self.rast.nuevo = False
                if self.rast.P is not None:
                    self.cuerpo = Cuerpo(self.rast.P, self.rast.vis, self.rast.abajo, self.rast.suelo, self.rast.cabeza, self.rast.t)
                    self.t_persona = ahora
                    self._actualizar_prueba(ahora)
            if self.rast.P is None or ahora - self.t_persona > 0.8:
                self.cuerpo = None
            if self.pagina == "eval":
                self._dibujar_video()
        if self.fase == "cuenta" and ahora - self.t_cuenta >= CUENTA:
            self.fase = "midiendo"
            self.prueba.iniciar(ahora)
            self.fuente.programa(self.prueba_id, self.lado.get())
            pitar(988, 160)
        if ahora - self.t_fps > 1.0:
            self.fps = self.n_cuadros / (ahora - self.t_fps)
            self.n_cuadros = 0
            self.t_fps = ahora
            self._estado_fuente()
        if self.pagina == "eval":
            self._dibujar_vivo()
            self._dibujar_grafica()
        self._led()
        self.raiz.after(12, self.ciclo)

    def _actualizar_prueba(self, ahora):
        cu = self.cuerpo
        sp = PR.CATALOGO[self.prueba_id]
        vals = {}
        if sp["tipo"] == "rom":
            for l in (LADOS if self.lado.get() == "ambos" else (self.lado.get(),)):
                vals[l] = float(sp["metrica"](cu, l)) if cu.visible(sp["puntos"](l), 0.45) else None
        elif sp["tipo"] == "sts30":
            vals["rodilla"] = (cu.rodilla_flexion("izq") + cu.rodilla_flexion("der")) / 2
        elif sp["tipo"] == "marcha":
            vals["distancia"] = float(np.mean(cu.P[[23, 24], 2]))
        elif sp["tipo"] == "equilibrio":
            vals["pie"] = (cu.altura_pie(PR.OTRO[self.lado.get()] if self.lado.get() in LADOS else "der")) * 100
        elif sp["tipo"] == "postura":
            vals["hombros"] = cu.desnivel_hombros()
        self.hist.append((ahora, vals))
        while self.hist and ahora - self.hist[0][0] > 20:
            self.hist.popleft()
        if self.fase == "midiendo" and self.prueba is not None:
            self.prueba.actualizar(cu, ahora)
            while self.prueba.eventos:
                ev, l = self.prueba.eventos.popleft()
                if ev == "rep":
                    pitar(1318 if l != "der" else 1175, 70)
                    self.flash = (ahora, "¡Repetición!" if l is None else f"Repetición {NOMBRE_LADO[l].lower()}", COL_LADO.get(l, VERDE))
                elif ev == "inicio":
                    pitar(988, 100)
            if self.prueba.terminado:
                self._finalizar()

    def _proy(self, p):
        fx, fy, cx, cy = self.cuadro.K
        z = max(0.2, float(p[2]))
        return VW - 1 - (p[0] * fx / z + cx), p[1] * fy / z + cy

    def _dibujar_video(self):
        c = self.cuadro
        if self.vista == "prof" and c.prof is not None:
            v = np.clip((4.5 - c.prof) / 4.0, 0, 1)
            img = cv2.applyColorMap((v * 255).astype(np.uint8), cv2.COLORMAP_TURBO)
            img[c.prof <= 0.3] = 0
            img = cv2.resize(img, (VW, VH), interpolation=cv2.INTER_NEAREST)
        else:
            img = c.img
            if img.shape[:2] != (VH, VW):
                img = cv2.resize(img, (VW, VH))
            img = (img * 0.82).astype(np.uint8)
        img = np.ascontiguousarray(img[:, ::-1])
        cv = self.video
        cv.delete("capa")
        cu = self.cuerpo
        if cu is not None and self.rast.px is not None:
            px = self.rast.px.copy()
            px[:, 0] = VW - 1 - px[:, 0]
            vis = self.rast.vis
            for a, b in HUESOS:
                if vis[a] < 0.4 or vis[b] < 0.4:
                    continue
                col = BGR_LADO.get(LADO_PUNTO.get(a) if LADO_PUNTO.get(a) == LADO_PUNTO.get(b) else None, (200, 200, 200))
                cv2.line(img, tuple(np.int32(px[a])), tuple(np.int32(px[b])), col, 3, cv2.LINE_AA)
            for i in range(11, 33):
                if vis[i] >= 0.4 and i not in (17, 18, 19, 20, 21, 22):
                    cv2.circle(img, tuple(np.int32(px[i])), 5, (255, 255, 255), -1, cv2.LINE_AA)
                    cv2.circle(img, tuple(np.int32(px[i])), 5, BGR_LADO.get(LADO_PUNTO.get(i)), 2, cv2.LINE_AA)
            arcos = []
            if self.fase == "midiendo" and self.prueba is not None:
                arcos = self.prueba.dibujo(cu)
            elif PR.CATALOGO[self.prueba_id]["tipo"] == "rom":
                tmp = PR.crear(self.prueba_id, self.lado.get(), {})
                for l in tmp.lados:
                    if cu.visible(tmp.spec["puntos"](l), 0.45):
                        tmp.actual[l] = float(tmp.spec["metrica"](cu, l))
                arcos = tmp.dibujo(cu)
            elif PR.CATALOGO[self.prueba_id]["tipo"] == "goniometro":
                arcos = PR.PruebaGoniometro(PR.CATALOGO["goniometro"], "ambos", {}).dibujo(cu)
            capa = img.copy()
            etiquetas = []
            for vtx, ref, seg, val, l in arcos:
                pv, pr, ps = self._proy(vtx), self._proy(ref), self._proy(seg)
                a1 = math.degrees(math.atan2(pr[1] - pv[1], pr[0] - pv[0]))
                a2 = math.degrees(math.atan2(ps[1] - pv[1], ps[0] - pv[0]))
                d = (a2 - a1 + 540) % 360 - 180
                rr = 34
                centro = (int(pv[0]), int(pv[1]))
                cv2.ellipse(capa, centro, (rr, rr), 0, a1, a1 + d, BGR_LADO[l], -1, cv2.LINE_AA)
                cv2.line(img, centro, (int(pv[0] + (pr[0] - pv[0]) * 1.0), int(pv[1] + (pr[1] - pv[1]) * 1.0)), (235, 235, 235), 1, cv2.LINE_AA)
                m = math.radians(a1 + d / 2)
                etiquetas.append((pv[0] + math.cos(m) * (rr + 22), pv[1] + math.sin(m) * (rr + 22), f"{val:.0f}°", COL_LADO[l]))
            if arcos:
                img = cv2.addWeighted(capa, 0.45, img, 0.55, 0)
            self.foto = a_foto(img)
            cv.itemconfigure(self.img_id, image=self.foto)
            for x, y, t, col in etiquetas:
                cv.create_rectangle(x - 26, y - 12, x + 26, y + 12, fill="#0b0f14", outline=col, width=2, tags="capa")
                cv.create_text(x, y, text=t, fill=col, font=("Segoe UI", 12, "bold"), tags="capa")
        else:
            self.foto = a_foto(img)
            cv.itemconfigure(self.img_id, image=self.foto)
        self._guia()

    def _guia(self):
        cv = self.video
        cu = self.cuerpo
        ahora = time.time()
        msgs = []
        if self.rast.est is not None and not self.rast.est.listo:
            msgs.append(("Cargando el modelo de pose…" if self.rast.est.error is None else self.rast.est.error, AMARILLO))
        elif cu is None:
            msgs.append(("No detecto a nadie · colócate de frente a unos 2.5 m", AMARILLO))
        else:
            sp = PR.CATALOGO[self.prueba_id]
            d = self.rast.distancia or 0
            pies = cu.visible((27, 28), 0.5)
            if sp["tipo"] != "marcha":
                if d < 1.6:
                    msgs.append((f"Aléjate un poco · estás a {d:.1f} m", AMARILLO))
                elif d > 4.0:
                    msgs.append((f"Acércate · estás a {d:.1f} m", AMARILLO))
                if not pies and sp["region"] in ("Cadera", "Rodilla", "Postura", "Funcional"):
                    msgs.append(("No veo tus pies · aléjate o inclina el Kinect (flecha ↓)", AMARILLO))
            if self.prueba is not None and self.fase == "midiendo":
                for a in self.prueba.avisos[:2]:
                    msgs.append((a, ROJO))
        y = 18
        for t, col in msgs:
            w = 9 + len(t) * 7
            cv.create_rectangle(VW / 2 - w / 2, y - 13, VW / 2 + w / 2, y + 13, fill="#0b0f14", outline=col, width=2, tags="capa")
            cv.create_text(VW / 2, y, text=t, fill=col, font=("Segoe UI", 10, "bold"), tags="capa")
            y += 32
        if self.fase == "cuenta":
            n = max(1, math.ceil(CUENTA - (ahora - self.t_cuenta)))
            cv.create_oval(VW / 2 - 60, VH / 2 - 60, VW / 2 + 60, VH / 2 + 60, fill="#0b0f14", outline=ACENTO, width=4, tags="capa")
            cv.create_text(VW / 2, VH / 2, text=str(n), fill=ACENTO, font=("Segoe UI", 44, "bold"), tags="capa")
            cv.create_text(VW / 2, VH / 2 + 84, text="Prepárate", fill=TEXTO, font=("Segoe UI", 12, "bold"), tags="capa")
        if self.fase == "midiendo" and self.prueba is not None:
            cv.create_rectangle(8, VH - 34, VW - 8, VH - 8, fill="#0b0f14", outline=ACENTO, tags="capa")
            cv.create_oval(18, VH - 27, 30, VH - 15, fill=ROJO if int(ahora * 2) % 2 else "#5a1f1c", outline="", tags="capa")
            cv.create_text(38, VH - 21, text=self.prueba.estado, anchor="w", fill=TEXTO, font=("Segoe UI", 10, "bold"), tags="capa")
        if self.flash and ahora - self.flash[0] < 0.8:
            cv.create_text(VW / 2, VH - 64, text=self.flash[1], fill=self.flash[2], font=("Segoe UI", 20, "bold"), tags="capa")
        if cu is not None and self.rast.distancia:
            cv.create_text(VW - 10, VH - 44 if self.fase == "midiendo" else VH - 12, text=f"a {self.rast.distancia:.2f} m", anchor="e",
                           fill=TENUE, font=("Segoe UI", 9, "bold"), tags="capa")

    def _gauge(self, c, x, y, w, val, mx, normal, funcional, col, maximo=None):
        c.create_rectangle(x, y, x + w, y + 14, fill=TARJETA2, outline="")
        esc = lambda v: x + w * max(0.0, min(1.0, v / mx))
        c.create_rectangle(x, y, esc(funcional), y + 14, fill="#3a2422", outline="")
        c.create_rectangle(esc(funcional), y, esc(normal * 0.9), y + 14, fill="#3b321c", outline="")
        c.create_rectangle(esc(normal * 0.9), y, esc(mx), y + 14, fill="#1d3a2a", outline="")
        if val is not None:
            c.create_rectangle(x, y + 4, esc(val), y + 10, fill=col, outline="")
        if maximo is not None:
            c.create_line(esc(maximo), y - 4, esc(maximo), y + 18, fill="#ffffff", width=2)
        for v, t in ((funcional, f"{funcional}°"), (normal, f"{normal}°")):
            c.create_line(esc(v), y + 14, esc(v), y + 19, fill=TENUE)
            c.create_text(esc(v), y + 27, text=t, fill=TENUE, font=("Segoe UI", 7))

    def _dibujar_vivo(self):
        c = self.vivo_c
        c.delete("all")
        sp = PR.CATALOGO[self.prueba_id]
        W = int(c["width"])
        tipo = sp["tipo"]
        fase = {"libre": "VISTA PREVIA", "cuenta": "PREPÁRATE", "midiendo": "MIDIENDO", "resultado": "TERMINADO"}[self.fase]
        colf = {"libre": TENUE, "cuenta": AMARILLO, "midiendo": ROJO, "resultado": VERDE}[self.fase]
        c.create_text(14, 14, text=sp["nombre"].upper(), anchor="w", fill=TEXTO, font=("Segoe UI", 10, "bold"))
        c.create_text(W - 14, 14, text=fase, anchor="e", fill=colf, font=("Segoe UI", 9, "bold"))
        cu = self.cuerpo
        pr = self.prueba if self.fase in ("midiendo", "resultado") else None
        if tipo == "rom":
            lados = LADOS if self.lado.get() == "ambos" else (self.lado.get(),)
            for k, l in enumerate(lados):
                y0 = 40 + k * 74
                v = None
                if cu is not None and cu.visible(sp["puntos"](l), 0.45):
                    v = float(sp["metrica"](cu, l))
                cont = pr.cont.get(l) if isinstance(pr, PR.PruebaROM) else None
                mx = None if cont is None or not cont.reps else max(r["pico"] for r in cont.reps)
                c.create_text(14, y0 + 6, text=NOMBRE_LADO[l].upper(), anchor="w", fill=COL_LADO[l], font=("Segoe UI", 9, "bold"))
                c.create_text(14, y0 + 36, text="—" if v is None else f"{v:.0f}°", anchor="w", fill=TEXTO, font=("Segoe UI", 30, "bold"))
                pct = None if mx is None else mx / sp["normal"] * 100
                c.create_text(150, y0 + 6, text=("máximo " + (f"{mx:.0f}° · {pct:.0f}% de lo normal" if mx is not None else "—")),
                              anchor="w", fill=color_pct(pct) if pct else TENUE, font=("Segoe UI", 9, "bold"))
                n = 0 if cont is None else len(cont.reps)
                c.create_text(W - 14, y0 + 6, text=f"rep {n}/{self.reps.get()}" if pr else "", anchor="e", fill=TEXTO, font=("Segoe UI", 9, "bold"))
                self._gauge(c, 150, y0 + 22, W - 170, v, sp["normal"] * 1.08, sp["normal"], sp["funcional"], COL_LADO[l], mx)
            if len(lados) == 1:
                txt = "Pulsa Iniciar y realiza el movimiento completo; cada repetición se cuenta sola." if pr is None else ""
                c.create_text(14, 150, text=txt, anchor="w", fill=TENUE, font=("Segoe UI", 9))
        elif tipo == "equilibrio":
            t = pr.tiempo if isinstance(pr, PR.PruebaEquilibrio) else 0.0
            c.create_text(14, 70, text=f"{t:4.1f} s", anchor="w", fill=TEXTO, font=("Segoe UI", 34, "bold"))
            c.create_text(200, 52, text=f"Apoyo: pierna {FEM.get(self.lado.get(), '')}", anchor="w", fill=COL_LADO.get(self.lado.get(), TEXTO),
                          font=("Segoe UI", 10, "bold"))
            c.create_text(200, 76, text=(pr.estado if pr else "Pulsa Iniciar; el tiempo corre al levantar el pie"), anchor="w", fill=TENUE,
                          font=("Segoe UI", 9))
            c.create_rectangle(14, 120, W - 14, 136, fill=TARJETA2, outline="")
            c.create_rectangle(14, 120, 14 + (W - 28) * min(1, t / 30), 136, fill=VERDE if t >= 20 else (AMARILLO if t >= 10 else ROJO), outline="")
            for s in (10, 20, 30):
                x = 14 + (W - 28) * s / 30
                c.create_line(x, 116, x, 140, fill=TENUE)
                c.create_text(x, 152, text=f"{s} s", fill=TENUE, font=("Segoe UI", 8))
        elif tipo == "sts30":
            n = pr.reps if isinstance(pr, PR.PruebaSTS) else 0
            r = pr.transcurrido(time.time()) if isinstance(pr, PR.PruebaSTS) and pr.t0 else 0
            c.create_text(14, 74, text=f"{n}", anchor="w", fill=TEXTO, font=("Segoe UI", 40, "bold"))
            c.create_text(90, 84, text="repeticiones", anchor="w", fill=TENUE, font=("Segoe UI", 10))
            c.create_text(260, 60, text=f"Tiempo: {min(30, r):.0f} / 30 s", anchor="w", fill=TEXTO, font=("Segoe UI", 12, "bold"))
            c.create_rectangle(14, 128, W - 14, 142, fill=TARJETA2, outline="")
            c.create_rectangle(14, 128, 14 + (W - 28) * min(1, r / 30), 142, fill=ACENTO, outline="")
            if cu is not None:
                k = (cu.rodilla_flexion("izq") + cu.rodilla_flexion("der")) / 2
                c.create_text(260, 88, text=f"Rodillas a {k:.0f}° · {'de pie' if k < 30 else ('sentado' if k > 65 else 'en transición')}",
                              anchor="w", fill=TENUE, font=("Segoe UI", 10))
        elif tipo == "marcha":
            d = self.rast.distancia if cu is not None else None
            c.create_text(14, 74, text="—" if d is None else f"{d:.1f} m", anchor="w", fill=TEXTO, font=("Segoe UI", 34, "bold"))
            c.create_text(200, 60, text=pr.estado if pr else "Pulsa Iniciar y colócate a 4 m del Kinect", anchor="w", fill=TEXTO,
                          font=("Segoe UI", 11, "bold"))
            c.create_text(200, 86, text="Recorrido útil: de 4 m a 1.5 m, de frente a la cámara", anchor="w", fill=TENUE, font=("Segoe UI", 9))
            c.create_rectangle(14, 128, W - 14, 142, fill=TARJETA2, outline="")
            if d is not None:
                f = max(0.0, min(1.0, (4.2 - d) / 2.7))
                c.create_rectangle(14, 128, 14 + (W - 28) * f, 142, fill=ACENTO, outline="")
        elif tipo == "goniometro":
            if cu is None:
                c.create_text(14, 70, text="Sin persona", anchor="w", fill=TENUE, font=("Segoe UI", 12))
            else:
                a = cu.angulos()
                filas = [("Hombro flexión", "hombro_flex"), ("Hombro abducción", "hombro_abd"), ("Codo flexión", "codo_flex"),
                         ("Cadera flexión", "cadera_flex"), ("Cadera abducción", "cadera_abd"), ("Rodilla flexión", "rodilla_flex")]
                c.create_text(200, 36, text="Izquierdo", fill=COL_LADO["izq"], font=("Segoe UI", 9, "bold"))
                c.create_text(290, 36, text="Derecho", fill=COL_LADO["der"], font=("Segoe UI", 9, "bold"))
                for i, (n, k) in enumerate(filas):
                    y = 56 + i * 21
                    c.create_text(14, y, text=n, anchor="w", fill=TENUE, font=("Segoe UI", 9))
                    c.create_text(200, y, text=f"{a[k + '_izq']:.0f}°", fill=TEXTO, font=("Segoe UI", 11, "bold"))
                    c.create_text(290, y, text=f"{a[k + '_der']:.0f}°", fill=TEXTO, font=("Segoe UI", 11, "bold"))
                otros = [("Tronco lateral", f"{a['tronco_lateral']:+.0f}°"), ("Tronco flexión", f"{a['tronco_flexion']:+.0f}°"),
                         ("Cabeza", f"{a['cabeza_inclinacion']:+.0f}°"), ("Desnivel hombros", f"{a['desnivel_hombros']:+.1f} cm"),
                         ("Desnivel pelvis", f"{a['desnivel_pelvis']:+.1f} cm"), ("Valgo rodilla izq/der",
                                                                                 f"{a['rodilla_valgo_izq']:+.0f}° / {a['rodilla_valgo_der']:+.0f}°")]
                for i, (n, v) in enumerate(otros):
                    y = 56 + i * 21
                    c.create_text(360, y, text=n, anchor="w", fill=TENUE, font=("Segoe UI", 9))
                    c.create_text(W - 14, y, text=v, anchor="e", fill=TEXTO, font=("Segoe UI", 11, "bold"))
        else:
            c.create_text(14, 70, text=(pr.estado if pr else "Pulsa Iniciar y quédate quieto"), anchor="w", fill=TEXTO, font=("Segoe UI", 14, "bold"))
            if cu is not None:
                if tipo == "postura":
                    lineas = [f"Desnivel de hombros {cu.desnivel_hombros():+.1f} cm", f"Desnivel de pelvis {cu.desnivel_pelvis():+.1f} cm",
                              f"Tronco {cu.tronco_lateral():+.1f}° · cabeza {cu.cabeza_inclinacion():+.1f}°"]
                else:
                    lineas = [f"Estatura estimada {cu.estatura() * 100:.0f} cm",
                              f"Miembro inferior izq {cu.longitudes()['miembro_inf_izq'] * 100:.0f} cm · der {cu.longitudes()['miembro_inf_der'] * 100:.0f} cm",
                              "Brazos en cruz para medir la envergadura"]
                for i, t in enumerate(lineas):
                    c.create_text(14, 108 + i * 22, text=t, anchor="w", fill=TENUE, font=("Segoe UI", 10))
        if pr is not None and self.fase == "midiendo" and pr.avisos:
            c.create_text(14, 178, text="⚠ " + pr.avisos[0], anchor="w", fill=ROJO, font=("Segoe UI", 9, "bold"))

    def _dibujar_grafica(self):
        c = self.graf
        c.delete("all")
        sp = PR.CATALOGO[self.prueba_id]
        if sp["tipo"] in ("goniometro", "antropometria"):
            c.create_text(VW / 2, GH / 2, text="Esta prueba no tiene gráfica en vivo: los valores aparecen en el panel de la derecha", fill=TENUE,
                          font=("Segoe UI", 9))
            return
        if not self.hist:
            c.create_text(VW / 2, GH / 2, text="La gráfica en vivo aparece cuando hay una persona frente al Kinect", fill=TENUE,
                          font=("Segoe UI", 9))
            return
        claves = []
        for _, v in self.hist:
            for k in v:
                if k not in claves:
                    claves.append(k)
        if not claves:
            return
        if sp["tipo"] == "rom":
            lo, hi, u = -10.0, sp["normal"] * 1.1, "°"
        else:
            vs = [v[k] for _, v in self.hist for k in claves if v.get(k) is not None]
            lo, hi = (min(vs), max(vs)) if vs else (0, 1)
            pad = max(1.0, (hi - lo) * 0.15)
            lo, hi = lo - pad, hi + pad
            u = {"sts30": "°", "marcha": "m", "equilibrio": "cm", "postura": "cm"}.get(sp["tipo"], "")
        x0, x1, y0, y1 = 40, VW - 10, 18, GH - 14
        ym = lambda v: y1 - (y1 - y0) * (v - lo) / max(1e-6, hi - lo)
        etiqueta = {"rom": "Ángulo", "sts30": "Flexión de rodillas", "marcha": "Distancia al Kinect", "equilibrio": "Altura del pie libre",
                    "postura": "Desnivel de hombros"}.get(sp["tipo"], "")
        c.create_text(12, 9, text=f"{etiqueta} · últimos 20 s", anchor="w", fill=TENUE, font=("Segoe UI", 8))
        if sp["tipo"] == "rom":
            for v, col in ((sp["normal"], VERDE), (sp["funcional"], AMARILLO)):
                c.create_line(x0, ym(v), x1, ym(v), fill=col, dash=(4, 3))
                c.create_text(x0 - 4, ym(v), text=f"{v}", anchor="e", fill=col, font=("Segoe UI", 7))
            c.create_line(x0, ym(0), x1, ym(0), fill=BORDE)
            c.create_text(x0 - 4, ym(0), text="0", anchor="e", fill=TENUE, font=("Segoe UI", 7))
        else:
            for v in (lo + (hi - lo) * 0.15, hi - (hi - lo) * 0.15):
                c.create_line(x0, ym(v), x1, ym(v), fill=BORDE)
                c.create_text(x0 - 4, ym(v), text=f"{v:.1f}{u}" if abs(v) < 10 else f"{v:.0f}{u}", anchor="e", fill=TENUE, font=("Segoe UI", 7))
        ahora = time.time()
        for k in claves:
            pts = []
            for t, v in self.hist:
                if v.get(k) is None:
                    continue
                pts += [x1 - (ahora - t) / 20 * (x1 - x0), ym(v[k])]
            if len(pts) >= 4:
                c.create_line(*pts, fill=COL_LADO.get(k, ACENTO), width=2)

    def _estado_fuente(self):
        est = self.rast.est
        ms = f" · pose {est.ms:.0f} ms" if est is not None and est.listo else ""
        tipo = "" if self.cuadro is None else {"color": " · color", "ir": " · infrarrojo"}.get(self.cuadro.tipo, "")
        self.lbl_fuente.configure(text=f"● {self.fuente.nombre}{tipo} · {self.fps:.0f} fps{ms}", fg=VERDE if self.fps > 5 else ROJO)
        self.lbl_3d.configure(text=f"3D: {self.rast.modo3d}" + ("" if self.rast.suelo is None else f" · piso a {self.rast.suelo[1]:.2f} m"))
        for k, b in self.b_vista.items():
            act = k == self.vista
            b.configure(bg=ACENTO if act else TARJETA2, fg="#071014" if act else TEXTO)

    def _led(self):
        n = "amarillo" if self.cuerpo is None else ("parpadeo verde" if self.fase == "midiendo" else "verde")
        if n != self.led_actual:
            self.led_actual = n
            try:
                self.fuente.led(n)
            except Exception:
                pass

    def _pag_pacientes(self):
        pag = tk.Frame(self.cont, bg=FONDO)
        izq = self._tarjeta(pag)
        izq.pack(side="left", fill="y")
        self._titulo(izq, "Pacientes", "Busca por nombre o expediente")
        self.buscar = tk.Entry(izq, bg=TARJETA2, fg=TEXTO, relief="flat", insertbackground=TEXTO, font=("Segoe UI", 10), width=30)
        self.buscar.pack(fill="x", pady=(8, 6), ipady=4)
        self.buscar.bind("<KeyRelease>", lambda e: self.refrescar_lista())
        self.lista = tk.Listbox(izq, bg=TARJETA, fg=TEXTO, selectbackground=ACENTO, selectforeground="#071014", relief="flat",
                                highlightthickness=0, font=("Segoe UI", 10), activestyle="none", height=24)
        self.lista.pack(fill="both", expand=True)
        self.lista.bind("<<ListboxSelect>>", self._sel_lista)
        self.lista.bind("<Double-Button-1>", lambda e: (self._sel_lista(), self.mostrar("eval")))
        bots = tk.Frame(izq, bg=TARJETA)
        bots.pack(fill="x", pady=(8, 0))
        self._boton(bots, "+ Nuevo paciente", self.nuevo_paciente, primario=True).pack(side="left")
        self._boton(bots, "Eliminar", self.eliminar_paciente).pack(side="right")
        self.ids_lista = []
        med = self._tarjeta(pag)
        med.pack(side="left", fill="both", padx=12)
        self._titulo(med, "Perfil clínico", "Los campos con * son obligatorios. Fechas en formato AAAA-MM-DD.")
        form = tk.Frame(med, bg=TARJETA)
        form.pack(fill="x", pady=(8, 0))
        self.campos = {}

        def entrada(fila, col, clave, txt, ancho=24):
            tk.Label(form, text=txt, bg=TARJETA, fg=TENUE, font=("Segoe UI", 8), anchor="w").grid(row=fila * 2, column=col, sticky="w", padx=(0, 10))
            e = tk.Entry(form, bg=TARJETA2, fg=TEXTO, relief="flat", insertbackground=TEXTO, font=("Segoe UI", 10), width=ancho)
            e.grid(row=fila * 2 + 1, column=col, sticky="we", padx=(0, 10), pady=(0, 6), ipady=3)
            self.campos[clave] = e

        def combo(fila, col, clave, txt, valores):
            tk.Label(form, text=txt, bg=TARJETA, fg=TENUE, font=("Segoe UI", 8), anchor="w").grid(row=fila * 2, column=col, sticky="w")
            cb = ttk.Combobox(form, values=valores, state="readonly", width=22, font=("Segoe UI", 10))
            cb.grid(row=fila * 2 + 1, column=col, sticky="we", padx=(0, 10), pady=(0, 6))
            self.campos[clave] = cb

        entrada(0, 0, "nombre", "Nombre completo *")
        entrada(0, 1, "expediente", "Expediente")
        entrada(1, 0, "nacimiento", "Fecha de nacimiento")
        combo(1, 1, "sexo", "Sexo", [t for _, t in SEXOS])
        entrada(2, 0, "estatura_cm", "Estatura (cm)")
        entrada(2, 1, "peso_kg", "Peso (kg)")
        entrada(3, 0, "diagnostico", "Diagnóstico")
        combo(3, 1, "tipo", "Tipo de caso", TIPOS)
        combo(4, 0, "lado_afectado", "Lado afectado", [t for _, t in LADOS_AF])
        entrada(4, 1, "fecha_evento", "Fecha de cirugía o lesión")
        entrada(5, 0, "medico", "Médico / terapeuta")
        entrada(5, 1, "telefono", "Teléfono")
        tk.Label(form, text="Objetivos terapéuticos", bg=TARJETA, fg=TENUE, font=("Segoe UI", 8)).grid(row=12, column=0, sticky="w")
        tk.Label(form, text="Notas clínicas", bg=TARJETA, fg=TENUE, font=("Segoe UI", 8)).grid(row=12, column=1, sticky="w")
        for col, clave in ((0, "objetivos"), (1, "notas")):
            t = tk.Text(form, bg=TARJETA2, fg=TEXTO, relief="flat", insertbackground=TEXTO, font=("Segoe UI", 9), width=26, height=4,
                        wrap="word", highlightthickness=0)
            t.grid(row=13, column=col, sticky="we", padx=(0, 10), pady=(0, 6))
            self.campos[clave] = t
        tk.Label(med, text="Rutina de evaluación del paciente", bg=TARJETA, fg=TEXTO, font=("Segoe UI", 10, "bold"), anchor="w").pack(fill="x", pady=(6, 2))
        plan = tk.Frame(med, bg=TARJETA)
        plan.pack(fill="x")
        self.v_plan = {}
        for i, sp in enumerate(PR.ROM + PR.OTRAS):
            v = tk.BooleanVar(value=False)
            tk.Checkbutton(plan, text=sp["nombre"], variable=v, bg=TARJETA, fg=TEXTO, selectcolor=TARJETA2, activebackground=TARJETA,
                           activeforeground=TEXTO, font=("Segoe UI", 8), anchor="w").grid(row=i // 2, column=i % 2, sticky="w")
            self.v_plan[sp["id"]] = v
        bots = tk.Frame(med, bg=TARJETA)
        bots.pack(fill="x", pady=(10, 0))
        self._boton(bots, "Guardar perfil", self.guardar_paciente, primario=True).pack(side="left")
        self._boton(bots, "Evaluar a este paciente  →", self._evaluar_este).pack(side="left", padx=8)
        self.lbl_form = tk.Label(bots, text="", bg=TARJETA, fg=TENUE, font=("Segoe UI", 8))
        self.lbl_form.pack(side="left")
        der = self._tarjeta(pag)
        der.pack(side="left", fill="both", expand=True)
        self._titulo(der, "Resumen")
        self.resumen = tk.Canvas(der, width=340, height=610, bg=TARJETA, highlightthickness=0)
        self.resumen.pack(fill="both", expand=True, pady=(6, 0))
        self.form_id = None
        return pag

    def refrescar_lista(self):
        q = self.buscar.get().strip().lower()
        self.lista.delete(0, "end")
        self.ids_lista = []
        for p in self.alm.listar():
            txt = f"{p.get('nombre', '')}  {p.get('expediente', '')}"
            if q and q not in txt.lower():
                continue
            e = edad_de(p.get("nacimiento"))
            self.lista.insert("end", f"  {p.get('nombre', '')}" + (f" · {e} a" if e is not None else ""))
            self.ids_lista.append(p["id"])
            if self.paciente and p["id"] == self.paciente["id"]:
                self.lista.selection_set("end")
        if self.form_id is None and self.paciente:
            self._llenar_form(self.paciente)
        self._dibujar_resumen()

    def _sel_lista(self, e=None):
        s = self.lista.curselection()
        if not s:
            return
        self.elegir_paciente(self.ids_lista[s[0]])

    def elegir_paciente(self, pid, cambiar=True):
        p = self.alm.obtener(pid)
        if not p:
            return
        self.paciente = p
        self._llenar_form(p)
        self._chip()
        self._rutina_lbl()
        af = p.get("lado_afectado")
        if af in LADOS and PR.CATALOGO[self.prueba_id]["tipo"] == "rom" and self.fase == "libre":
            self.lado.set(af)
        self._dibujar_resumen()

    def _chip(self):
        p = self.paciente
        if not p:
            self.lbl_pac.configure(text="Sin paciente seleccionado")
            return
        e = edad_de(p.get("nacimiento"))
        dx = p.get("diagnostico") or ""
        dx = dx if len(dx) <= 36 else dx[:35] + "…"
        self.lbl_pac.configure(text=f"{p.get('nombre', '')}" + (f" · {e} años" if e is not None else "") + (f" · {dx}" if dx else ""))

    def _llenar_form(self, p):
        self.form_id = p.get("id")
        for k, w in self.campos.items():
            v = p.get(k, "") or ""
            if k == "sexo":
                v = dict(SEXOS).get(v, "")
            elif k == "lado_afectado":
                v = dict(LADOS_AF).get(v, "")
            if isinstance(w, tk.Text):
                w.delete("1.0", "end")
                w.insert("1.0", v)
            elif isinstance(w, ttk.Combobox):
                w.set(v)
            else:
                w.delete(0, "end")
                w.insert(0, str(v))
        plan = set(p.get("plan", []))
        for k, v in self.v_plan.items():
            v.set(k in plan)
        self.lbl_form.configure(text="")

    def _leer_form(self):
        p = {}
        for k, w in self.campos.items():
            if isinstance(w, tk.Text):
                p[k] = w.get("1.0", "end").strip()
            else:
                p[k] = w.get().strip()
        p["sexo"] = {t: c for c, t in SEXOS}.get(p["sexo"], "")
        p["lado_afectado"] = {t: c for c, t in LADOS_AF}.get(p["lado_afectado"], "")
        p["plan"] = [k for k, v in self.v_plan.items() if v.get()]
        return p

    def nuevo_paciente(self):
        self._llenar_form({})
        self.form_id = None
        self.lista.selection_clear(0, "end")
        self.campos["nombre"].focus_set()
        self.lbl_form.configure(text="Nuevo paciente: llena el perfil y pulsa Guardar")

    def guardar_paciente(self):
        p = self._leer_form()
        if not p["nombre"]:
            messagebox.showwarning("OrtoKinect", "Escribe el nombre del paciente.", parent=self.raiz)
            return
        for k, n in (("nacimiento", "fecha de nacimiento"), ("fecha_evento", "fecha de cirugía o lesión")):
            if p[k] and fecha_de(p[k]) is None:
                messagebox.showwarning("OrtoKinect", f"La {n} debe tener el formato AAAA-MM-DD (por ejemplo 1975-08-21).", parent=self.raiz)
                return
        for k, n in (("estatura_cm", "estatura"), ("peso_kg", "peso")):
            if p[k]:
                try:
                    float(p[k].replace(",", "."))
                    p[k] = p[k].replace(",", ".")
                except ValueError:
                    messagebox.showwarning("OrtoKinect", f"La {n} debe ser un número.", parent=self.raiz)
                    return
        if self.form_id:
            base = self.alm.obtener(self.form_id) or {}
            base.update(p)
            p = base
        p = self.alm.guardar(p)
        self.form_id = p["id"]
        self.paciente = p
        self._chip()
        self._rutina_lbl()
        self.refrescar_lista()
        self.lbl_form.configure(text=f"Guardado · {datetime.now():%H:%M:%S}")

    def eliminar_paciente(self):
        s = self.lista.curselection()
        if not s:
            return
        pid = self.ids_lista[s[0]]
        p = self.alm.obtener(pid) or {}
        if not messagebox.askyesno("OrtoKinect", f"¿Eliminar a {p.get('nombre', '')} y todas sus evaluaciones?\nSe moverá a la papelera de datos.",
                                   parent=self.raiz):
            return
        self.alm.eliminar(pid)
        if self.paciente and self.paciente["id"] == pid:
            self.paciente = None
            self._chip()
        self.form_id = None
        self._llenar_form({})
        self.form_id = None
        self.refrescar_lista()

    def _evaluar_este(self):
        if not self.form_id:
            self.guardar_paciente()
        if self.paciente:
            self.mostrar("eval")

    def _dibujar_resumen(self):
        c = self.resumen
        c.delete("all")
        p = self.paciente
        if not p:
            c.create_text(10, 20, text="Selecciona o crea un paciente.", anchor="nw", fill=TENUE, font=("Segoe UI", 10))
            return
        y = 6
        c.create_text(10, y, text=p.get("nombre", ""), anchor="nw", fill=TEXTO, font=("Segoe UI", 13, "bold"), width=320)
        y += 30
        e = edad_de(p.get("nacimiento"))
        i = imc(p)
        ev = dias_desde(p.get("fecha_evento"))
        datos = [("Edad", f"{e} años" if e is not None else "—"),
                 ("IMC", "—" if i is None else f"{i:.1f} · " + ("bajo peso" if i < 18.5 else "normal" if i < 25 else "sobrepeso" if i < 30 else "obesidad")),
                 ("Diagnóstico", p.get("diagnostico") or "—"), ("Lado afectado", dict(LADOS_AF).get(p.get("lado_afectado"), "—")),
                 ("Evolución", "—" if ev is None else f"día {ev} · semana {ev // 7 + 1}" + (" (posoperatorio)" if p.get("tipo") == "Postquirúrgico" else ""))]
        for k, v in datos:
            c.create_text(10, y, text=k, anchor="nw", fill=TENUE, font=("Segoe UI", 8))
            c.create_text(110, y, text=v, anchor="nw", fill=TEXTO, font=("Segoe UI", 9, "bold"), width=220)
            y += 22 if len(v) < 34 else 36
        regs = self.alm.registros(p["id"])
        y += 6
        c.create_line(10, y, 330, y, fill=BORDE)
        y += 8
        c.create_text(10, y, text=f"{len(regs)} evaluaciones guardadas", anchor="nw", fill=TEXTO, font=("Segoe UI", 10, "bold"))
        y += 22
        if regs:
            c.create_text(10, y, text=f"Última: {datetime.fromisoformat(regs[-1]['fecha']):%d/%m/%Y %H:%M}", anchor="nw", fill=TENUE,
                          font=("Segoe UI", 8))
            y += 22
        serie = PR.puntos_evolucion(regs)
        for clave, pts in sorted(serie.items(), key=lambda kv: kv[1][-1][0], reverse=True)[:9]:
            v = pts[-1][1]
            u = PR.unidad(clave[0])
            ref, _ = PR.referencia(clave[0], pts[-1][2])
            pct = None if not ref else v / ref * 100
            txt = f"{v:.2f} {u}" if u == "m/s" else f"{v:.0f} {u}"
            delta = ""
            if len(pts) > 1:
                dv = v - pts[0][1]
                delta = (" ▲" if dv > 0 else " ▼" if dv < 0 else " =") + (f"{abs(dv):.2f}" if u == "m/s" else f"{abs(dv):.0f}")
            nom = PR.nombre_serie(clave)
            c.create_text(10, y, text=nom, anchor="nw", fill=TENUE, font=("Segoe UI", 8), width=215)
            c.create_text(330, y, text=txt + delta, anchor="ne", fill=color_pct(pct) if pct and PR.CATALOGO[clave[0]]["tipo"] != "postura" else TEXTO,
                          font=("Segoe UI", 9, "bold"))
            y += 36 if len(nom) > 34 else 26
        plan = self._rutina()
        if plan:
            y += 4
            c.create_text(10, y, text="Rutina: " + ", ".join(PR.CATALOGO[k]["nombre"] for k in plan), anchor="nw", fill=TENUE,
                          font=("Segoe UI", 8), width=320)

    def _pag_progreso(self):
        from matplotlib.figure import Figure
        from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
        pag = tk.Frame(self.cont, bg=FONDO)
        top = self._tarjeta(pag, pady=8)
        top.pack(fill="x")
        self.lbl_prog = tk.Label(top, text="", bg=TARJETA, fg=TEXTO, font=("Segoe UI", 12, "bold"))
        self.lbl_prog.pack(side="left")
        self._boton(top, "Reporte PDF", self.reporte_pdf, primario=True).pack(side="right")
        self._boton(top, "Exportar CSV", self.exportar_csv).pack(side="right", padx=6)
        self._boton(top, "Eliminar registro", self.eliminar_registro).pack(side="right")
        tk.Label(top, text="Prueba", bg=TARJETA, fg=TENUE, font=("Segoe UI", 9)).pack(side="left", padx=(24, 6))
        self.cb_serie = ttk.Combobox(top, state="readonly", width=44, font=("Segoe UI", 10))
        self.cb_serie.pack(side="left")
        self.cb_serie.bind("<<ComboboxSelected>>", lambda e: self._dibujar_series())
        medio = tk.Frame(pag, bg=FONDO)
        medio.pack(fill="x", pady=(10, 0))
        plt_bg = TARJETA
        self.fig1 = Figure(figsize=(8.0, 3.3), dpi=96, facecolor=plt_bg)
        self.ax1 = self.fig1.add_subplot(111)
        self.canvas1 = FigureCanvasTkAgg(self.fig1, master=medio)
        self.canvas1.get_tk_widget().configure(bg=plt_bg, highlightthickness=0)
        self.canvas1.get_tk_widget().pack(side="left")
        self.fig2 = Figure(figsize=(5.55, 3.3), dpi=96, facecolor=plt_bg)
        self.ax2 = self.fig2.add_subplot(111)
        self.canvas2 = FigureCanvasTkAgg(self.fig2, master=medio)
        self.canvas2.get_tk_widget().configure(bg=plt_bg, highlightthickness=0)
        self.canvas2.get_tk_widget().pack(side="left", padx=(10, 0))
        abajo = tk.Frame(pag, bg=FONDO)
        abajo.pack(fill="both", expand=True, pady=(10, 0))
        cols = ("fecha", "prueba", "lado", "valor", "dolor", "hallazgo")
        self.tabla = ttk.Treeview(abajo, columns=cols, show="headings", height=9)
        for col, t, w in (("fecha", "Fecha", 120), ("prueba", "Prueba", 210), ("lado", "Lado", 80), ("valor", "Resultado", 110),
                          ("dolor", "Dolor", 55), ("hallazgo", "Hallazgo principal", 360)):
            self.tabla.heading(col, text=t)
            self.tabla.column(col, width=w, anchor="w" if col in ("prueba", "hallazgo") else "center")
        self.tabla.pack(side="left", fill="both")
        sb = ttk.Scrollbar(abajo, orient="vertical", command=self.tabla.yview)
        sb.pack(side="left", fill="y")
        self.tabla.configure(yscrollcommand=sb.set)
        self.tabla.bind("<<TreeviewSelect>>", self._detalle)
        self.detalle = tk.Text(abajo, bg=TARJETA, fg=TEXTO, relief="flat", font=("Segoe UI", 9), wrap="word", highlightthickness=0, padx=8, pady=6)
        self.detalle.pack(side="left", fill="both", expand=True, padx=(10, 0))
        self.detalle.tag_configure("b", font=("Segoe UI", 10, "bold"), foreground=ACENTO)
        self.series = {}
        self.regs = []
        return pag

    def refrescar_progreso(self):
        p = self.paciente
        self.tabla.delete(*self.tabla.get_children())
        if not p:
            self.lbl_prog.configure(text="Selecciona un paciente para ver su progreso")
            self.cb_serie.configure(values=[])
            self.cb_serie.set("")
            self.series, self.regs = {}, []
            self._dibujar_series()
            return
        self.lbl_prog.configure(text=f"Progreso · {p.get('nombre', '')}")
        self.regs = self.alm.registros(p["id"])
        self.series = PR.puntos_evolucion(self.regs)
        claves = sorted(self.series, key=lambda k: (PR.REGIONES.index(PR.CATALOGO[k[0]]["region"]), k[0], str(k[1])))
        self.claves = claves
        nombres = [f"{PR.nombre_serie(k)}  ({len(self.series[k])})" for k in claves]
        actual = self.cb_serie.get()
        self.cb_serie.configure(values=nombres)
        if nombres and actual not in nombres:
            self.cb_serie.current(0)
        elif not nombres:
            self.cb_serie.set("")
        for r in reversed(self.regs):
            sp = PR.CATALOGO.get(r["prueba"], {})
            v, u = PR.valor_principal(r)
            if sp.get("tipo") == "rom" and "lados" in r.get("metricas", {}):
                val = " / ".join(f"{d['rom_max']:.0f}°" if d.get("rom_max") is not None else "—" for d in r["metricas"]["lados"].values())
            elif v is None:
                val = "—"
            else:
                val = f"{v:.2f} {u}" if u == "m/s" else f"{v:.1f} {u}" if u in ("cm", "s") else f"{v:.0f} {u}"
            lado = NOMBRE_LADO.get(r.get("lado"), "") if sp.get("tipo") in PR.CON_LADO else "—"
            self.tabla.insert("", "end", iid=r["id"], values=(datetime.fromisoformat(r["fecha"]).strftime("%d/%m/%Y %H:%M"),
                                                               sp.get("nombre", r["prueba"]), lado, val,
                                                               "" if r.get("dolor") is None else f"{r['dolor']}/10",
                                                               " · ".join((r.get("hallazgos") or [""])[:2])))
        self._dibujar_series()
        self._detalle()

    def _estilo_ax(self, ax):
        ax.set_facecolor(TARJETA)
        for s in ("top", "right"):
            ax.spines[s].set_visible(False)
        for s in ("left", "bottom"):
            ax.spines[s].set_color(BORDE)
        ax.tick_params(colors=TENUE, labelsize=8)
        ax.grid(alpha=0.15, color="#ffffff")

    def _dibujar_series(self):
        import matplotlib.dates as mdates
        ax = self.ax1
        ax.clear()
        self._estilo_ax(ax)
        i = self.cb_serie.current() if self.cb_serie.get() else -1
        if i >= 0 and self.series:
            clave = self.claves[i]
            pts = self.series[clave]
            xs = [datetime.fromisoformat(p[0]) for p in pts]
            ys = [p[1] for p in pts]
            col = COL_LADO.get(clave[1], ACENTO)
            ax.plot(xs, ys, "-o", color=col, lw=2.2, ms=5, zorder=3)
            for x, yv in zip(xs, ys):
                ax.annotate(f"{yv:.2f}" if PR.unidad(clave[0]) == "m/s" else f"{yv:.0f}", (x, yv), textcoords="offset points", xytext=(0, 7),
                            ha="center", color=TEXTO, fontsize=7)
            ref, et = PR.referencia(clave[0], pts[-1][2])
            if ref:
                ax.axhline(ref, color=VERDE, ls="--", lw=1.2)
                ax.text(xs[0], ref, f"  {et} ({ref:g})", color=VERDE, fontsize=7, va="bottom")
            sp = PR.CATALOGO[clave[0]]
            if sp["tipo"] == "rom":
                ax.axhline(sp["funcional"], color=AMARILLO, ls=":", lw=1)
                ax.set_ylim(0, sp["normal"] * 1.12)
            dol = [(datetime.fromisoformat(p[0]), p[2].get("dolor")) for p in pts if p[2].get("dolor") is not None]
            if dol:
                ax2 = ax.twinx()
                ax2.bar([d[0] for d in dol], [d[1] for d in dol], width=0.35 if len(xs) > 1 else 0.05, color=ROJO, alpha=0.35, zorder=1)
                ax2.set_ylim(0, 30)
                ax2.set_yticks([])
                for s in ax2.spines.values():
                    s.set_visible(False)
            ax.set_title(f"{PR.nombre_serie(clave)} ({PR.unidad(clave[0])})  ·  barras rojas: dolor EVA", color=TEXTO, fontsize=10, loc="left")
            ax.xaxis.set_major_formatter(mdates.DateFormatter("%d/%m"))
            if len(xs) == 1:
                ax.set_xlim(xs[0] - (datetime(2000, 1, 2) - datetime(2000, 1, 1)), xs[0] + (datetime(2000, 1, 2) - datetime(2000, 1, 1)))
        else:
            ax.text(0.5, 0.5, "Sin evaluaciones guardadas todavía", transform=ax.transAxes, ha="center", color=TENUE)
        self.fig1.tight_layout()
        self.canvas1.draw_idle()
        ax = self.ax2
        ax.clear()
        self._estilo_ax(ax)
        barras = []
        for clave, pts in self.series.items():
            sp = PR.CATALOGO[clave[0]]
            if sp["tipo"] == "rom":
                barras.append((sp["nombre"].replace(" de ", "\nde ", 1) if len(sp["nombre"]) > 18 else sp["nombre"], clave[1],
                               pts[-1][1] / sp["normal"] * 100))
        if barras:
            nombres = sorted({b[0] for b in barras})
            for k, l in enumerate(("izq", "der")):
                xs = [nombres.index(b[0]) + (k - 0.5) * 0.38 for b in barras if b[1] == l]
                ys = [b[2] for b in barras if b[1] == l]
                ax.barh(xs, ys, height=0.36, color=COL_LADO[l], label=NOMBRE_LADO[l])
            ax.set_yticks(range(len(nombres)))
            ax.set_yticklabels(nombres, fontsize=7, color=TEXTO)
            ax.axvline(100, color=VERDE, ls="--", lw=1)
            ax.set_xlim(0, 115)
            ax.set_title("% del rango normal (última medición)", color=TEXTO, fontsize=10, loc="left")
            ax.legend(fontsize=7, frameon=False, labelcolor=TEXTO, loc="lower left", bbox_to_anchor=(0.0, -0.22), ncol=2)
        else:
            ax.text(0.5, 0.5, "Sin mediciones de rango articular", transform=ax.transAxes, ha="center", color=TENUE)
        self.fig2.tight_layout()
        self.canvas2.draw_idle()

    def _detalle(self, e=None):
        s = self.tabla.selection()
        t = self.detalle
        t.delete("1.0", "end")
        if not s:
            t.insert("end", "Selecciona un registro de la tabla para ver todos sus hallazgos, las compensaciones y las notas.")
            return
        r = next((x for x in self.regs if x["id"] == s[0]), None)
        if not r:
            return
        sp = PR.CATALOGO.get(r["prueba"], {})
        t.insert("end", f"{sp.get('nombre', r['prueba'])} · {datetime.fromisoformat(r['fecha']):%d/%m/%Y %H:%M}\n", "b")
        for h in r.get("hallazgos", []):
            t.insert("end", "•  " + h + "\n")
        if r.get("dolor") is not None:
            t.insert("end", f"\nDolor (EVA): {r['dolor']}/10\n")
        if r.get("nota"):
            t.insert("end", f"Nota: {r['nota']}\n")
        comp = r.get("metricas", {}).get("compensaciones")
        if comp:
            t.insert("end", "\nCompensaciones (% del tiempo):\n")
            for k, v in comp.items():
                t.insert("end", f"   {k}: {v:.0f}%\n")
        t.insert("end", f"\nFuente: {r.get('fuente', '—')} · 3D: {r.get('modo3d', '—')}")

    def eliminar_registro(self):
        s = self.tabla.selection()
        if not s or not self.paciente:
            return
        if messagebox.askyesno("OrtoKinect", "¿Eliminar el registro seleccionado?", parent=self.raiz):
            self.alm.eliminar_registro(self.paciente["id"], s[0])
            self.refrescar_progreso()

    def exportar_csv(self):
        if not self.paciente:
            return
        ini = f"{self.paciente.get('nombre', 'paciente').replace(' ', '_')}_{datetime.now():%Y%m%d}.csv"
        ruta = filedialog.asksaveasfilename(parent=self.raiz, defaultextension=".csv", initialfile=ini,
                                            initialdir=str(self.alm.carpeta(self.paciente["id"], "exportes")), filetypes=[("CSV", "*.csv")])
        if ruta:
            self.alm.exportar_csv(self.paciente["id"], ruta)
            messagebox.showinfo("OrtoKinect", f"Datos exportados a:\n{ruta}", parent=self.raiz)

    def reporte_pdf(self):
        if not self.paciente:
            return
        import reporte
        d = self.alm.carpeta(self.paciente["id"], "reportes")
        ruta = str(d / f"reporte_{datetime.now():%Y%m%d_%H%M%S}.pdf")
        try:
            reporte.generar(self.alm, self.paciente["id"], ruta)
        except Exception as e:
            messagebox.showerror("OrtoKinect", f"No se pudo generar el reporte:\n{e}", parent=self.raiz)
            return
        try:
            os.startfile(ruta)
        except OSError:
            messagebox.showinfo("OrtoKinect", f"Reporte guardado en:\n{ruta}", parent=self.raiz)

    def cerrar(self):
        self.vivo = False
        try:
            self.fuente.led("verde")
        except Exception:
            pass
        self.rast.cerrar()
        self.fuente.cerrar()
        self.raiz.destroy()

    def correr(self):
        self.raiz.mainloop()


def main():
    ap = argparse.ArgumentParser(description="OrtoKinect: evaluación en traumatología, ortopedia y rehabilitación con Kinect")
    ap.add_argument("--simulado", action="store_true", help="sin Kinect: paciente simulado que realiza cada prueba")
    ap.add_argument("--camara", action="store_true", help="usar una cámara web (sin profundidad)")
    a = ap.parse_args()
    aviso = ""
    if a.simulado:
        fuente = FuenteSimulada()
        import demo
        demo.asegurar(Almacen())
    elif a.camara:
        fuente = FuenteCamara()
    else:
        try:
            fuente = FuenteKinect()
        except Exception as e:
            aviso = f"No se pudo abrir el Kinect ({e}). Usando el paciente simulado."
            fuente = FuenteSimulada()
    App(fuente, aviso).correr()


if __name__ == "__main__":
    main()
