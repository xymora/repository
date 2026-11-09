import math
import threading
import time
import tkinter as tk
import webbrowser
from tkinter import messagebox, ttk

import numpy as np

import config as C
import calles as K
import graficos as G
from planificador import Planificador
import recorrido as REC
from evolucion import (Entrenador, cargar_mejor, hay_entrenamiento_de_calles, pista_calle,
                       resumen_generacion)
from fisica import META, MOTIVOS, Simulador
from grabador import BotonGrabar
from puntos_control import DESTELLOS_HZ, DESTELLO_DURACION
from terreno import COLORES, NOMBRES_MAT, Pista, datos_nivel

ANCHO_VISTA, ALTO_VISTA = 980, 390
ALTO_MAPA = 280
ANCHO_EQUILIBRIO = 420
ANCHO_MAPA = ANCHO_VISTA - ANCHO_EQUILIBRIO - 6
ANCHO_PANEL = 390
ESCALA = 34.0
ESCALA_MAPA = 3.2
VELOCIDADES = (1, 2, 4, 8, 16)

FONDO = "#0a0d12"
TARJETA = "#121821"
BORDE = "#222c3a"
TEXTO = "#e3e8ef"
TENUE = "#7f8a9a"
ACENTO = "#ff3b30"
ORO = "#ffc940"
VERDE = "#3ddc84"
ROJO_OBJETIVO = ACENTO
FALLADO = "#6e5a5a"
AZUL = "#4fb3ff"
CIAN = "#39e5ff"
FUENTE = "Segoe UI"
MONO = "Consolas"
NOMBRE_SUPERFICIE = {"pavimento": "asfalto liso", "irregular": "relieve irregular",
                     "variado": "terreno variado"}
CIRCUITOS = (("no", "Sólo ida (A → B)"), ("misma", "Circuito A → B → A por la misma ruta"),
             ("otra", "Circuito A → B → A por otra ruta"))
NOMBRE_CIRCUITO = {"no": "sólo ida", "misma": "circuito por la misma ruta",
                   "otra": "circuito por otra ruta"}


def ajustar_tamano(raiz):
    global ANCHO_VISTA, ALTO_VISTA, ALTO_MAPA, ANCHO_EQUILIBRIO, ANCHO_MAPA, ANCHO_PANEL, ESCALA
    f = min(1.0, (raiz.winfo_screenwidth() - 40) / 1400, (raiz.winfo_screenheight() - 170) / 700)
    if f < 1.0:
        ANCHO_VISTA, ALTO_VISTA = int(980 * f), int(390 * f)
        ALTO_MAPA = int(280 * f)
        ANCHO_EQUILIBRIO = int(420 * f)
        ANCHO_MAPA = ANCHO_VISTA - ANCHO_EQUILIBRIO - 6
        ANCHO_PANEL = int(390 * f)
        ESCALA = 34.0 * f


class App:
    def __init__(self, raiz, entrenador=None, demo=False, nivel_demo=None, red_vial=None,
                 ruta=None, recorrido=False):
        self.raiz = raiz
        raiz.title("Moto autónoma evolutiva — estilo Moto-Terminator")
        raiz.configure(bg=FONDO)
        raiz.resizable(True, True)
        self.e = entrenador
        self.zoom_mapa = 1.0
        self._tam = None
        self.pausa = False
        self.turbo = False
        self.i_vel = 0
        self.cam = None
        self.demo = None
        self.mensaje = ""
        self.t_mensaje = 0.0
        self.particulas = []
        self.red_vial = red_vial or (entrenador.red_vial if entrenador else None)
        self.modo = "ciudad" if self.red_vial else "terreno"
        self.satelite = None
        self._foto = None
        self._preparando = None

        self.ruta_usuario = ruta
        self._t_cuadros = []

        self._barra_superior(raiz)
        self._barra_estado(raiz)
        cuerpo = tk.Frame(raiz, bg=FONDO)
        cuerpo.pack(fill="both", expand=True, padx=10, pady=(8, 0))
        self.cuerpo = cuerpo
        izq = tk.Frame(cuerpo, bg=FONDO)
        izq.pack(side="left", padx=(0, 8))
        self.vista = tk.Canvas(izq, width=ANCHO_VISTA, height=ALTO_VISTA, bg=FONDO,
                               highlightthickness=1, highlightbackground=BORDE)
        self.vista.pack()
        abajo = tk.Frame(izq, bg=FONDO)
        abajo.pack(pady=(6, 0), fill="x")
        self.mapa = tk.Canvas(abajo, width=ANCHO_MAPA, height=ALTO_MAPA, bg="#111814",
                              highlightthickness=1, highlightbackground=BORDE)
        self.mapa.pack(side="left")
        self.equilibrio = tk.Canvas(abajo, width=ANCHO_EQUILIBRIO, height=ALTO_MAPA, bg=TARJETA,
                                    highlightthickness=1, highlightbackground=BORDE)
        self.equilibrio.pack(side="right")
        self.panel = tk.Canvas(cuerpo, width=ANCHO_PANEL, height=ALTO_VISTA + ALTO_MAPA + 8,
                               bg=FONDO, highlightthickness=0)
        self.panel.pack(side="left", anchor="n")
        cuerpo.bind("<Configure>", self._al_redimensionar)
        self.mapa.bind("<MouseWheel>", self._zoom_mapa)
        raiz.bind("<F11>", lambda _: raiz.attributes("-fullscreen",
                                                       not raiz.attributes("-fullscreen")))
        raiz.update_idletasks()
        raiz.minsize(min(1100, raiz.winfo_width()), min(640, raiz.winfo_height()))
        self._botones_modo()
        if self.red_vial:
            self._cargar_satelite()
        if not demo:
            self._recordar_sesion()

        raiz.bind("<space>", lambda _: self.alternar_pausa())
        raiz.bind("t", lambda _: self.alternar_turbo())
        raiz.bind("d", lambda _: self.alternar_demo())
        raiz.bind("n", lambda _: self.reiniciar())
        raiz.bind("g", lambda _: self.guardar())
        raiz.bind("+", lambda _: self.cambiar_vel(1))
        raiz.bind("=", lambda _: self.cambiar_vel(1))
        raiz.bind("-", lambda _: self.cambiar_vel(-1))
        raiz.bind("<Left>", lambda _: self.nivel_demo(-1))
        raiz.bind("<Right>", lambda _: self.nivel_demo(1))
        raiz.bind("c", lambda _: self.alternar_ciudad())
        raiz.bind("<Escape>", lambda _: raiz.attributes("-fullscreen", False)
                  if raiz.attributes("-fullscreen") else self.salir())
        raiz.protocol("WM_DELETE_WINDOW", self.salir)

        if demo:
            self.iniciar_demo(nivel_demo)
        elif recorrido:
            self.raiz.after(300, self.abrir_recorrido)
        self.raiz.after(30, self.ciclo)

    def _guardar_avance(self):
        e = getattr(self, "e", None)
        if e is None or not getattr(e, "guardar", False):
            return False
        g = e.generacion
        e.generacion = g - 1
        try:
            e._guardar_poblacion()
        finally:
            e.generacion = g
        return True

    def guardar(self):
        try:
            ok = self._guardar_avance()
        except OSError as ex:
            self.avisar(f"No se pudo guardar el avance: {ex}")
            return
        if ok:
            self.avisar(f"Avance guardado en la generación {self.e.generacion}: "
                        "al reabrir el simulador continúa desde aquí")

    def salir(self):
        try:
            self._guardar_avance()
        except OSError:
            pass
        self.grabar.cerrar()
        self.raiz.destroy()

    def _boton(self, padre, texto, accion, peligro=False, ciudad=False, expandir=True, padx=8):
        normal, encima = (("#2a1416", "#4a1c1f") if peligro else ("#13283a", "#1c3a55") if ciudad
                          else ("#18202b", "#24303f"))
        b = tk.Button(padre, text=texto, command=accion, bg=normal, fg=TEXTO, bd=0,
                      activebackground=encima, activeforeground="white", relief="flat",
                      disabledforeground="#4b5563", font=(FUENTE, 9, "bold"), padx=padx, pady=6,
                      cursor="hand2")
        b.colores = (normal, encima)
        b.bind("<Enter>", lambda _: b.config(bg=b.colores[1]) if str(b["state"]) == "normal" else None)
        b.bind("<Leave>", lambda _: b.config(bg=b.colores[0]))
        b.pack(side="left", expand=expandir, fill="x", padx=2)
        return b

    def _colorear(self, b, normal, encima):
        b.colores = (normal, encima)
        b.config(bg=normal)

    def _barra_superior(self, raiz):
        barra = tk.Frame(raiz, bg="#0d1117", highlightthickness=1, highlightbackground=BORDE)
        barra.pack(fill="x")
        logo = tk.Canvas(barra, width=318, height=46, bg="#0d1117", highlightthickness=0)
        logo.pack(side="left", padx=(10, 0))
        for r, col in ((13, "#2a0d0d"), (9, "#6a1212"), (6, "#ff2a2a"), (2, "#ffd9d9")):
            logo.create_oval(20 - r, 23 - r, 20 + r, 23 + r, fill=col, outline="")
        t = logo.create_text(42, 23, anchor="w", text="MOTO-T", fill=TEXTO, font=(FUENTE, 15, "bold"))
        x = logo.bbox(t)[2] + 12
        logo.create_line(x - 6, 12, x - 6, 34, fill=BORDE)
        logo.create_text(x, 16, anchor="w", text="IA de manejo autónomo", fill=TEXTO,
                         font=(FUENTE, 8, "bold"))
        logo.create_text(x, 31, anchor="w", text="neuroevolución",
                         fill=TENUE, font=(FUENTE, 7))

        seg = tk.Frame(barra, bg="#18202b", padx=2, pady=2)
        seg.pack(side="left", padx=16, pady=8)
        self.b_terreno = self._boton(seg, "▲  Terrenos", lambda: self.cambiar_a("terreno"),
                                     expandir=False, padx=14)
        self.b_calles = self._boton(seg, "◈  Calles reales", lambda: self.cambiar_a("ciudad"),
                                    expandir=False, padx=14)

        der = tk.Frame(barra, bg="#0d1117")
        der.pack(side="right", padx=8, pady=8)
        self.b_ruta = self._boton(der, "⚑  Ruta A → B", self.planificar_ruta, ciudad=True,
                                  expandir=False)
        self.b_quitar = self._boton(der, "✕", self.quitar_ruta, expandir=False, padx=8)
        self.b_zona = self._boton(der, "⌖  Zona", self.elegir_zona, expandir=False)
        tk.Frame(der, bg=BORDE, width=1, height=26).pack(side="left", padx=8)
        self.b_clima = self._boton(der, "☁  Clima: " + REC.texto_clima(clima_config()),
                                   self.menu_clima, expandir=False)
        self.b_demo = self._boton(der, "▶  Recorrido", self.alternar_demo, expandir=False)
        self.b_turbo = self._boton(der, "⚡  Turbo", self.alternar_turbo, expandir=False)
        self.b_pausa = self._boton(der, "❚❚  Pausa", self.alternar_pausa, expandir=False)
        tk.Frame(der, bg=BORDE, width=1, height=26).pack(side="left", padx=8)
        self._boton(der, "−", lambda: self.cambiar_vel(-1), expandir=False, padx=8)
        self.lbl_vel = tk.Label(der, text="x1", width=4, bg="#0d1117", fg=TEXTO,
                                font=(FUENTE, 9, "bold"))
        self.lbl_vel.pack(side="left")
        self._boton(der, "+", lambda: self.cambiar_vel(1), expandir=False, padx=8)
        tk.Frame(der, bg=BORDE, width=1, height=26).pack(side="left", padx=8)
        self.b_guardar = self._boton(der, "✔  Guardar", self.guardar, ciudad=True, expandir=False)
        self.b_reset = self._boton(der, "⟲  Desde cero", self.reiniciar, peligro=True, expandir=False)
        tk.Frame(der, bg=BORDE, width=1, height=26).pack(side="left", padx=8)
        self.grabar = BotonGrabar(der, raiz, lambda texto, nivel="info": self.avisar(texto),
                                  (FUENTE, 9, "bold"))
        self.grabar.boton.configure(pady=6, padx=10)

        def _estilo(grabando, texto=None, b=self.grabar.boton):
            normal, encima = ("#c62828", "#e53935") if grabando else ("#2a1416", "#4a1c1f")
            b.configure(text=texto or ("⏹  Stop" if grabando else "⏺  Grabar"), bg=normal,
                        activebackground=encima, fg="#ffffff" if grabando else "#ff6b6b",
                        activeforeground="#ffffff", disabledforeground="#4b5563")

        self.grabar._estilo = _estilo
        _estilo(False)
        self.grabar.pack(side="left", padx=2)

    def _al_redimensionar(self, ev):
        tam = (ev.width, ev.height)
        if self._tam is None:
            self._tam = tam
            return
        if abs(tam[0] - self._tam[0]) < 3 and abs(tam[1] - self._tam[1]) < 3:
            return
        self._tam = tam
        if getattr(self, "_pendiente_tam", None):
            self.raiz.after_cancel(self._pendiente_tam)
        self._pendiente_tam = self.raiz.after(60, self._aplicar_tamano)

    def _aplicar_tamano(self):
        global ANCHO_VISTA, ALTO_VISTA, ALTO_MAPA, ANCHO_EQUILIBRIO, ANCHO_MAPA, ESCALA
        self._pendiente_tam = None
        w, h = self._tam
        ANCHO_VISTA = max(600, w - ANCHO_PANEL - 8 - 2)
        alto = h - 2
        ALTO_MAPA = int(min(max(alto * 0.44, 220), 620))
        ALTO_VISTA = max(300, alto - ALTO_MAPA - 6 - 4)
        ANCHO_EQUILIBRIO = int(min(max(ANCHO_VISTA * 0.42, 400), 720))
        ANCHO_MAPA = ANCHO_VISTA - ANCHO_EQUILIBRIO - 8
        ESCALA = min(max(34.0 * ALTO_VISTA / 390, 26.0), 64.0)
        self.vista.config(width=ANCHO_VISTA, height=ALTO_VISTA)
        self.mapa.config(width=ANCHO_MAPA, height=ALTO_MAPA)
        self.equilibrio.config(width=ANCHO_EQUILIBRIO, height=ALTO_MAPA)
        self.panel.config(height=ALTO_VISTA + ALTO_MAPA + 8)
        if len(G._CIELO) > 4:
            G._CIELO.clear()
        self.cam = None
        if self.pausa:
            self.dibujar()
            self.dibujar_panel(self.sim_actual())

    def _zoom_mapa(self, ev):
        self.zoom_mapa = min(max(self.zoom_mapa * (1.2 if ev.delta > 0 else 1 / 1.2), 0.25), 5.0)
        self.avisar(f"Zoom del mapa x{self.zoom_mapa:.1f} (rueda del mouse sobre el mapa)", cartel=False)

    def _barra_estado(self, raiz):
        barra = tk.Frame(raiz, bg="#0d1117", highlightthickness=1, highlightbackground=BORDE)
        barra.pack(fill="x", side="bottom", pady=(8, 0))
        self.lbl_estado = tk.Label(barra, text="Listo.", bg="#0d1117", fg=TENUE, anchor="w",
                                   font=(FUENTE, 8))
        self.lbl_estado.pack(side="left", padx=10, pady=3)
        self.lbl_info = tk.Label(barra, text="", bg="#0d1117", fg=TENUE, anchor="e",
                                 font=(FUENTE, 8))
        self.lbl_info.pack(side="right", padx=10, pady=3)

    def avisar(self, texto, cartel=True):
        if cartel:
            self.mensaje, self.t_mensaje = texto, time.time()
        if hasattr(self, "lbl_estado"):
            self.lbl_estado.config(text=f"{time.strftime('%H:%M:%S')}   {texto}")

    def alternar_pausa(self):
        self.pausa = not self.pausa
        self.b_pausa.config(text="▶  Continuar" if self.pausa else "❚❚  Pausa")

    def alternar_turbo(self):
        if self.demo:
            return
        self.turbo = not self.turbo
        self.b_turbo.config(text="◉  Animar" if self.turbo else "⚡  Turbo")
        if self.turbo:
            self._colorear(self.b_turbo, "#4a3a0c", "#5c4a12")
        else:
            self._colorear(self.b_turbo, "#18202b", "#24303f")
        self.avisar("Turbo: entrenando sin animación" if self.turbo else "Animación completa activada",
                    cartel=False)
        self.cam = None

    def menu_clima(self):
        m = tk.Menu(self.raiz, tearoff=0, bg=TARJETA, fg=TEXTO, activebackground="#1c3a55",
                    activeforeground="white", font=(FUENTE, 9))
        self._var_clima = tk.StringVar(value=clima_config())
        for valor in opciones_clima():
            m.add_radiobutton(label=REC.texto_clima(valor) + ("  (sin clima)" if valor == "despejado"
                                                              else ""),
                              value=valor, variable=self._var_clima,
                              command=lambda v=valor: self.fijar_clima(v))
        self.menu_clima_tk = m
        try:
            m.tk_popup(self.b_clima.winfo_rootx(), self.b_clima.winfo_rooty() +
                       self.b_clima.winfo_height())
        finally:
            m.grab_release()

    def fijar_clima(self, valor, recrear=True):
        if valor == "automatico":
            C.CLIMA_AUTOMATICO, C.CLIMA_MANUAL = True, None
        elif valor in (None, "", "despejado"):
            C.CLIMA_AUTOMATICO, C.CLIMA_MANUAL = False, None
        else:
            C.CLIMA_AUTOMATICO, C.CLIMA_MANUAL = False, valor
        self.b_clima.config(text="☁  Clima: " + REC.texto_clima(clima_config()))
        if not recrear or self._preparando:
            return
        if self.e is not None:
            viejo = self.e
            self.e = Entrenador(continuar=True, modo=self.modo, red_vial=self.red_vial,
                                ruta=self._ruta_para(self.red_vial))
            if viejo is not self.e and hasattr(viejo, "cerrar"):
                viejo.cerrar()
            if not self.demo:
                self.cam, self.particulas = None, []
        self._recordar_sesion()
        gen = f" (la generación sigue en {self.e.generacion})" if self.e is not None else ""
        self.avisar(f"Clima del entrenamiento: {REC.texto_clima(clima_config())}{gen}")

    def cambiar_vel(self, d):
        self.i_vel = max(0, min(len(VELOCIDADES) - 1, self.i_vel + d))
        self.lbl_vel.config(text=f"x{VELOCIDADES[self.i_vel]}")
        self.avisar(f"Velocidad de la animación x{VELOCIDADES[self.i_vel]}", cartel=False)

    def alternar_demo(self):
        if self.demo:
            self.salir_recorrido()
        else:
            self.abrir_recorrido()

    def salir_recorrido(self):
        self._terminar_recorrido()
        self.demo = None
        self.cam, self.particulas = None, []
        self.b_demo.config(text="▶  Recorrido")
        if self.e is None:
            self.e = Entrenador(continuar=True, modo=self.modo, red_vial=self.red_vial,
                                ruta=self._ruta_para(self.red_vial))
        self.avisar(f"De vuelta al entrenamiento (generación {self.e.generacion})", cartel=False)

    def abrir_recorrido(self, al_cancelar=None):
        if self._preparando:
            return None
        self.dialogo_recorrido = REC.DialogoRecorrido(self, al_cancelar=al_cancelar)
        return self.dialogo_recorrido

    def _terminar_recorrido(self):
        d = self.demo
        if d and d.get("eleccion") is not None:
            d["eleccion"].cancelar()
        self._quitar_cartel()

    def iniciar_recorrido(self, cfg):
        self._terminar_recorrido()
        rng = np.random.default_rng()
        semilla = int(rng.integers(1 << 30))
        try:
            pista = REC.armar_pista(cfg, semilla)
        except Exception as ex:
            messagebox.showerror("No se pudo armar el recorrido", str(ex))
            return
        clima = REC.crear_clima(cfg["clima"], semilla, rng)
        cands = REC.candidatos(cfg["modo"])
        if not cands and cfg["modo"] == "ciudad":
            cands = REC.candidatos("terreno")
        if not cands:
            messagebox.showinfo("Sin moto entrenada", "Todavía no hay ninguna moto guardada.\n"
                                "Entrena al menos una generación.")
            return
        red = cfg.get("red")
        extra = None
        if red is not None and red is not self.red_vial:
            extra = lambda: K.imagen_satelital(red.zona, avisar=lambda _: None)
        semillas = [semilla + 101 * k for k in range(REC.SEMILLAS_PREEVALUACION)]
        self.demo = {"recorrido": cfg, "pista": pista, "clima": clima, "estado": "eligiendo",
                     "candidatos": cands,
                     "eleccion": REC.Eleccion(cands, pista, clima, semillas, extra),
                     "intentos": [], "nivel": cfg["nivel"], "sim": None, "fin": None,
                     "datos": {}, "rep": 0, "red": red, "satelite": None, "puntos": None,
                     "titulo": "", "descripcion": REC.describir(cfg)}
        self.b_demo.config(text="◆  Entrenar")
        if self.turbo:
            self.alternar_turbo()
        self.cam, self.particulas = None, []
        self.avisar(f"Recorrido: {self.demo['descripcion']} · "
                    f"{REC.texto_clima(REC.nombre_de(clima))} · eligiendo a la mejor de "
                    f"{len(cands)} motos…", cartel=False)

    def _eleccion_lista(self):
        d = self.demo
        el = d.pop("eleccion")
        if el.error or el.resultado is None:
            self.demo = None
            self.b_demo.config(text="▶  Recorrido")
            if el.error:
                messagebox.showerror("Recorrido", f"No se pudo evaluar a las motos:\n{el.error}")
            return
        if el.datos_extra is not None:
            d["satelite"] = el.datos_extra
        i, res = el.resultado
        c = d["candidatos"][i]
        d["pesos"], d["elegida"], d["resultados"] = c["pesos"], c, res
        d["datos"] = {"generacion": c["generacion"], "nivel": c["nivel"], "etapa": c["etapa"]}
        r = res[i]
        d["preeval"] = (f"elegida entre {len(res)}: llegó {r['llegadas']}/"
                        f"{REC.SEMILLAS_PREEVALUACION} ({r['limpias']} sin errores) en la "
                        f"prueba previa")
        clima = REC.texto_clima(REC.nombre_de(d["clima"]))
        etapa = f" · etapa {c['etapa'] + 1}" if d["recorrido"]["modo"] == "ciudad" else ""
        d["titulo"] = f"Generación {c['generacion']} · nivel {c['nivel']}{etapa} · {clima}"
        d["estado"] = "corriendo"
        self.avisar(f"Recorrido con la moto de la {d['titulo']}  ({d['preeval']})")
        self._nueva_pista_demo()

    def _cartel_recorrido(self):
        self._quitar_cartel()
        d = self.demo
        intentos = d["intentos"]
        ok = sum(i[1] for i in intentos)
        exitosos = sum(1 for i in intentos if i[3] is True)
        con_puntos = any(i[3] is not None for i in intentos)
        fondo = "#0b0f15"
        marco = tk.Frame(self.vista, bg=fondo, highlightthickness=2,
                         highlightbackground=VERDE if intentos and ok == len(intentos) else ORO)
        tk.Label(marco, text="RECORRIDO TERMINADO", bg=fondo, fg=ORO,
                 font=(FUENTE, 14, "bold")).pack(padx=18, pady=(12, 2))
        tk.Label(marco, text=d["titulo"], bg=fondo, fg=TENUE, font=(FUENTE, 9)).pack(padx=18)
        texto = f"Llegó a la meta {ok} de {len(intentos)} veces"
        if con_puntos:
            texto += f"  ·  recorridos exitosos {exitosos} de {len(intentos)}"
        self.lbl_resultado = tk.Label(marco, text=texto, bg=fondo, fg=VERDE if ok else ACENTO,
                                      font=(FUENTE, 11, "bold"))
        self.lbl_resultado.pack(padx=18, pady=(8, 0))
        if intentos:
            tk.Label(marco, text="Último: " + intentos[-1][2], bg=fondo, fg=TEXTO,
                     font=(FUENTE, 9)).pack(padx=18)
        fila = tk.Frame(marco, bg=fondo)
        fila.pack(fill="x", padx=12, pady=12)
        self.b_repetir = self._boton(fila, "⟲  Repetir", self.repetir_recorrido)
        self.b_otro = self._boton(fila, "▶  Otro recorrido", self.otro_recorrido, ciudad=True)
        self.b_volver = self._boton(fila, "◆  Volver al entrenamiento", self.salir_recorrido)
        marco.place(relx=0.5, rely=0.5, anchor="center")
        self.cartel = marco

    def _quitar_cartel(self):
        c = getattr(self, "cartel", None)
        if c is not None:
            try:
                c.destroy()
            except tk.TclError:
                pass
        self.cartel = None

    def repetir_recorrido(self):
        d = self.demo
        if not d or "recorrido" not in d or "pesos" not in d:
            return
        self._quitar_cartel()
        d["rep"], d["estado"], d["intentos"] = 0, "corriendo", []
        self._nueva_pista_demo()

    def otro_recorrido(self):
        self._quitar_cartel()

        def cancelado():
            if self.demo and self.demo.get("estado") == "fin":
                self._cartel_recorrido()

        self.abrir_recorrido(al_cancelar=cancelado)

    def iniciar_demo(self, nivel):
        m = cargar_mejor(self.modo)
        if m is None:
            messagebox.showinfo("Sin moto entrenada",
                                "Todavía no hay una moto guardada" +
                                (" para calles reales" if self.modo == "ciudad" else "") +
                                ".\nEntrena al menos una generación.")
            return
        pesos, datos = m
        self.demo = {"pesos": pesos, "datos": datos, "intentos": [],
                     "nivel": nivel or max(1, int(datos.get("nivel", 1))), "sim": None}
        self.b_demo.config(text="◆  Entrenar")
        self.turbo = False
        self.b_turbo.config(text="⚡  Turbo")
        self._nueva_pista_demo()

    def _nueva_pista_demo(self):
        d = self.demo
        semilla = int(np.random.default_rng().integers(1 << 30))
        if "recorrido" in d:
            d["sim"] = REC.simulador(d["pista"], d["pesos"], semilla, d["clima"])
            d["puntos"] = REC.enganchar_puntos(d["sim"])
            d["fin"] = None
            self.cam, self.particulas = None, []
            return
        if self.modo == "ciudad":
            sup = circ = None
            if self.e is not None and self.e.modo == "ciudad" and hasattr(self.e, "config_pista"):
                sup, circ = self.e.config_pista(semilla)
            pista = pista_calle(self.red_vial, d["nivel"], semilla,
                                ruta=self._ruta_para(self.red_vial), superficie=sup, circuito=circ)
        else:
            pista = Pista(d["nivel"], semilla)
        d["sim"] = Simulador(pista, d["pesos"], semilla_ruido=semilla)
        d["puntos"] = REC.enganchar_puntos(d["sim"])
        d["fin"] = None
        self.cam = None
        self.particulas = []

    def _botones_modo(self):
        activo, inactivo = ("#1f6feb", "#2f81f7"), ("#18202b", "#24303f")
        self._colorear(self.b_terreno, *(activo if self.modo == "terreno" else inactivo))
        self._colorear(self.b_calles, *(activo if self.modo == "ciudad" else inactivo))
        self.b_zona.config(state="normal" if self.modo == "ciudad" else "disabled")
        self.b_quitar.config(state="normal" if self.ruta_usuario else "disabled")
        self.b_ruta.config(text="⚑  Editar ruta" if self.ruta_usuario else "⚑  Ruta A → B")

    def cambiar_a(self, modo):
        if self._preparando or modo == self.modo:
            return
        if modo == "terreno":
            self._cambiar_modo("terreno", None)
        else:
            self.elegir_zona()

    def alternar_ciudad(self):
        self.cambiar_a("terreno" if self.modo == "ciudad" else "ciudad")

    def _ruta_para(self, red):
        r = self.ruta_usuario
        return r["ruta"] if (r and red is not None and r["red"] is red) else None

    def planificar_ruta(self):
        if self._preparando:
            return
        red = self.red_vial if self.modo == "ciudad" else None
        actual = self.ruta_usuario if (self.ruta_usuario and self.ruta_usuario["red"] is red) else None
        Planificador(self.raiz, red, self._ruta_aceptada, actual)

    def _ruta_aceptada(self, red, ruta, info):
        self.ruta_usuario = dict(info, ruta=ruta, red=red)
        self.ruta_usuario.setdefault("circuito", "no")
        self._cambiar_modo("ciudad", red, aviso=False)
        if self.ruta_usuario["circuito"] != "no":
            ida, vuelta = info.get("largo_ida"), info.get("largo_vuelta")
            partes = (f" (ida {ida / 1000:.2f} + vuelta {vuelta / 1000:.2f} km)"
                      if ida is not None and vuelta is not None else "")
            self.avisar(f"Circuito A → B → A {NOMBRE_CIRCUITO[self.ruta_usuario['circuito']][9:]} de "
                        f"{info['largo'] / 1000:.2f} km{partes}: la moto lo recorrerá en cada "
                        f"generación (pista 1) y en la demo  ·  {self._texto_calles()}")
        else:
            self.avisar(f"Ruta A → B de {info['largo'] / 1000:.2f} km: la moto la recorrerá en cada "
                        f"generación (pista 1) y en la demo  ·  {self._texto_calles()}")

    def _texto_calles(self):
        if self.e is not None and getattr(self.e, "modo", None) == "ciudad" and \
                hasattr(self.e, "texto_etapa"):
            return self.e.texto_etapa()
        sup = getattr(C, "CALLES_SUPERFICIE", "pavimento")
        circ = getattr(C, "CALLES_CIRCUITO", "no")
        if getattr(C, "PLAN_AUTOMATICO", True):
            return "plan de estudios automático"
        return (f"superficie: {NOMBRE_SUPERFICIE.get(sup, sup)}  ·  rutas de entrenamiento: "
                f"{NOMBRE_CIRCUITO.get(circ, circ)} (manual)")

    def quitar_ruta(self):
        if not self.ruta_usuario:
            return
        self.ruta_usuario = None
        self._cambiar_modo(self.modo, self.red_vial, aviso=False)
        self.avisar("Ruta A → B quitada: de nuevo rutas al azar")

    def elegir_zona(self, al_elegir=None):
        if self._preparando and al_elegir is None:
            return
        top = tk.Toplevel(self.raiz, bg=TARJETA)
        top.title("Calles reales")
        top.transient(self.raiz)
        top.resizable(False, False)
        tk.Label(top, text="¿En qué ciudad va a manejar la moto?", bg=TARJETA, fg=ORO,
                 font=(FUENTE, 11, "bold")).pack(anchor="w", padx=16, pady=(14, 6))
        var = tk.StringVar(value=(self.red_vial.zona.nombre if self.red_vial and
                                  self.red_vial.zona.nombre in K.ZONAS else next(iter(K.ZONAS))))
        combo = ttk.Combobox(top, textvariable=var, values=list(K.ZONAS), state="readonly", width=40)
        combo.pack(anchor="w", padx=16)
        tk.Label(top, text="…o escribe coordenadas (lat, lon) o pega un enlace de Google Maps:",
                 bg=TARJETA, fg=TENUE, font=(FUENTE, 9)).pack(anchor="w", padx=16, pady=(12, 4))
        entrada = tk.Entry(top, width=52, bg="#0c1118", fg=TEXTO, insertbackground=TEXTO,
                           relief="flat", font=(FUENTE, 10))
        entrada.pack(anchor="w", padx=16, ipady=4)
        estilo = dict(bg=TARJETA, fg=TEXTO, selectcolor="#0c1118", activebackground=TARJETA,
                      activeforeground=TEXTO, font=(FUENTE, 9), anchor="w")
        op = tk.Frame(top, bg=TARJETA)
        if al_elegir is None:
            op.pack(fill="x")
        plan = tk.StringVar(value="automatico" if getattr(C, "PLAN_AUTOMATICO", True) else "manual")
        tk.Label(op, text="Entrenamiento en calles:", bg=TARJETA, fg=TENUE,
                 font=(FUENTE, 9)).pack(anchor="w", padx=16, pady=(12, 2))
        tk.Radiobutton(op, text="Automático (plan de estudios): pavimento → circuitos → "
                                "relieve irregular → terreno variado", value="automatico",
                       variable=plan, **estilo).pack(anchor="w", padx=22)
        tk.Radiobutton(op, text="Elegir a mano (fija la etapa; no reinicia la generación):",
                       value="manual", variable=plan, **estilo).pack(anchor="w", padx=22)
        a_mano = lambda: plan.set("manual")
        tk.Label(op, text="Superficie de las calles:", bg=TARJETA, fg=TENUE,
                 font=(FUENTE, 9)).pack(anchor="w", padx=40, pady=(4, 0))
        sup = tk.StringVar(value=getattr(C, "CALLES_SUPERFICIE", "pavimento"))
        for clave, texto in K.SUPERFICIES.items():
            tk.Radiobutton(op, text=texto, value=clave, variable=sup, command=a_mano,
                           **estilo).pack(anchor="w", padx=46)
        tk.Label(op, text="Rutas de entrenamiento:", bg=TARJETA, fg=TENUE,
                 font=(FUENTE, 9)).pack(anchor="w", padx=40, pady=(4, 0))
        circ = tk.StringVar(value=getattr(C, "CALLES_CIRCUITO", "no"))
        for clave, texto in CIRCUITOS:
            tk.Radiobutton(op, text=texto, value=clave, variable=circ, command=a_mano,
                           **estilo).pack(anchor="w", padx=46)
        fila_clima = tk.Frame(op, bg=TARJETA)
        fila_clima.pack(anchor="w", padx=16, pady=(10, 0))
        tk.Label(fila_clima, text="Clima del entrenamiento:", bg=TARJETA, fg=TENUE,
                 font=(FUENTE, 9)).pack(side="left")
        climas = opciones_clima()
        clima = tk.StringVar(value=REC.texto_clima(clima_config()))
        ttk.Combobox(fila_clima, textvariable=clima, state="readonly", width=26,
                     values=[REC.texto_clima(c) for c in climas]).pack(side="left", padx=8)
        self._zona_vars = {"ciudad": var, "entrada": entrada, "plan": plan, "superficie": sup,
                           "circuito": circ, "clima": clima, "ventana": top}
        tk.Label(op, text="Las calles salen de OpenStreetMap y la imagen satelital de Esri; se\n"
                           "descargan una sola vez (si el proyecto del dron ya tiene la ciudad,\n"
                           "se reutiliza). Todas las superficies y circuitos comparten el mismo\n"
                           "entrenamiento: la generación nunca vuelve a 1 (sólo «Desde cero»).",
                 bg=TARJETA, fg=TENUE, justify="left", font=(FUENTE, 8)).pack(anchor="w", padx=16,
                                                                              pady=(10, 0))
        error = tk.Label(top, text="", bg=TARJETA, fg=ACENTO, font=(FUENTE, 9))
        error.pack(anchor="w", padx=16)

        def aceptar(_=None):
            texto = entrada.get().strip()
            if texto:
                coords = K.leer_coordenadas(texto)
                if coords is None:
                    error.config(text="No entendí esas coordenadas.")
                    return
                zona = K.Zona(f"Zona {coords[0]:.4f}, {coords[1]:.4f}", coords)
            else:
                zona = K.zona_para(var.get())
            top.destroy()
            if al_elegir is not None:
                al_elegir(zona)
                return
            C.PLAN_AUTOMATICO = plan.get() == "automatico"
            C.CALLES_SUPERFICIE = sup.get()
            C.CALLES_CIRCUITO = circ.get()
            elegido = next((c for c in climas if REC.texto_clima(c) == clima.get()), None)
            if elegido is not None:
                self.fijar_clima(elegido, recrear=False)
            self._preparar_ciudad(zona)

        fila = tk.Frame(top, bg=TARJETA)
        fila.pack(fill="x", padx=12, pady=12)
        self._boton(fila, "Cancelar", top.destroy)
        self._zona_vars["aceptar"] = self._boton(
            fila, "◈  Usar esta zona" if al_elegir else "◈  Manejar aquí", aceptar, ciudad=True)
        entrada.bind("<Return>", aceptar)
        top.grab_set()

    def _preparar_ciudad(self, zona):
        estado = {"avisos": [], "listo": None, "error": None}

        def trabajo():
            try:
                red = K.RedVial(zona, avisar=estado["avisos"].append)
                K.imagen_satelital(zona, avisar=estado["avisos"].append)
                estado["listo"] = red
            except Exception as e:
                estado["error"] = str(e)

        self._preparando = estado
        self.avisar(f"Preparando las calles de {zona.nombre}…")
        threading.Thread(target=trabajo, daemon=True).start()
        self.raiz.after(200, self._revisar_preparacion)

    def _revisar_preparacion(self):
        estado = self._preparando
        if estado["avisos"]:
            self.avisar(estado["avisos"][-1])
        if estado["listo"] is None and estado["error"] is None:
            self.raiz.after(200, self._revisar_preparacion)
            return
        self._preparando = None
        if estado["error"]:
            messagebox.showerror("No se pudieron preparar las calles", estado["error"])
            return
        self.ruta_usuario = None
        self._cambiar_modo("ciudad", estado["listo"])

    def _cambiar_modo(self, modo, red, aviso=True):
        if red is not self.red_vial or modo != "ciudad":
            self.satelite = None
        self.modo, self.red_vial = modo, red
        if red is not None and self.satelite is None:
            self._cargar_satelite()
        en_demo = self.demo is not None
        en_recorrido = en_demo and "recorrido" in self.demo
        self._terminar_recorrido()
        self.demo = None
        self.e = Entrenador(continuar=True, modo=modo, red_vial=red, ruta=self._ruta_para(red))
        self.cam, self.particulas = None, []
        self._botones_modo()
        self._recordar_sesion()
        if not aviso:
            pass
        elif modo == "ciudad":
            self.avisar(f"Calles reales: {red.zona.nombre}  ·  {self._texto_calles()}" +
                        ("  (parte de lo aprendido en terrenos)" if self.e.desde_terreno else ""))
        else:
            self.avisar("De vuelta a los terrenos")
        self.b_demo.config(text="▶  Recorrido")
        if en_demo and not en_recorrido:
            self.iniciar_demo(None)

    def _recordar_sesion(self):
        r = self.ruta_usuario
        ruta = ((r["a"], r["b"], r.get("circuito", "no"))
                if (r and r.get("red") is self.red_vial and self.red_vial) else None)
        K.guardar_sesion(self.modo, self.red_vial.zona if self.red_vial else None, ruta)

    def _cargar_satelite(self):
        try:
            self.satelite = K.imagen_satelital(self.red_vial.zona, avisar=lambda _: None)
        except Exception:
            self.satelite = None

    def abrir_google_maps(self, _=None):
        sim = self.sim_actual()
        if sim is None or not isinstance(sim.pista, K.PistaCalle):
            return
        lat, lon = sim.pista.latlon(self._lider(sim)[1])
        webbrowser.open(K.url_google_maps(lat, lon))

    def nivel_demo(self, d):
        if self.demo and "recorrido" not in self.demo:
            self.demo["nivel"] = max(1, min(C.NIVEL_MAX, self.demo["nivel"] + d))
            self._nueva_pista_demo()

    def reiniciar(self):
        if self.demo or self.e is None:
            return
        if messagebox.askyesno("Reiniciar desde cero",
                               "Se borrará la moto guardada, la población y el historial.\n"
                               "La evolución empezará en la generación 1 con motos al azar.\n\n¿Continuar?"):
            self.e.reiniciar()
            self.cam = None
            self.avisar("Evolución reiniciada desde cero")

    def ciclo(self):
        t0 = time.perf_counter()
        try:
            if not self.pausa:
                self.avanzar()
            self.dibujar()
            self._info_estado()
        finally:
            ms = (time.perf_counter() - t0) * 1000
            if ms < 14:
                self.raiz.after(int(16 - ms), self.ciclo)
            else:
                self.raiz.after_idle(self.raiz.after, 0, self.ciclo)

    def avanzar(self):
        if self.demo:
            d = self.demo
            if d.get("estado") == "eligiendo":
                if d["eleccion"].listo:
                    self._eleccion_lista()
                return
            if d.get("estado") == "fin":
                return
            sim = d["sim"]
            if sim.terminado:
                if d["fin"] is None:
                    d["fin"] = time.time()
                    ok = sim.motivo[0] == META
                    exitosa = REC.exitosa(d.get("puntos"), sim)
                    d["intentos"].append(
                        (sim.pista.nivel, ok,
                         f"llegó en {sim.t_fin[0]:.1f} s · "
                         f"{(sim.pista.meta - sim.pista.salida) / sim.t_fin[0] * 3.6:.0f} km/h promedio"
                         + (f" · {sim.reintentos[0]} error(es)" if sim.reintentos[0] else "")
                         if ok else
                         f"{MOTIVOS[sim.motivo[0]]} ({sim.progreso[0]:.0f} m)", exitosa))
                elif time.time() - d["fin"] > 2.5:
                    if "recorrido" in d:
                        d["rep"] += 1
                        if d["rep"] >= d["recorrido"]["repeticiones"]:
                            d["estado"] = "fin"
                            self._cartel_recorrido()
                            return
                    self._nueva_pista_demo()
                return
            sim.correr(VELOCIDADES[self.i_vel])
            self._avisar_errores(sim)
            return
        e = self.e
        if not self.turbo:
            sim = e.sim
            r = e.avanzar(VELOCIDADES[self.i_vel])
            self._avisar_errores(sim)
        else:
            limite = time.time() + 0.045
            r = e.avanzar_turbo()
            while r is None and not e.en_paralelo() and time.time() < limite:
                r = e.avanzar_turbo()
        if r == "pista":
            self.cam, self.particulas = None, []
            p = e.pistas[e.i_pista]
            nombre = "tu ruta A → B" if getattr(p, "personalizada", False) else f"pista {e.i_pista + 1}"
            self.avisar(f"Generación {e.generacion}: {nombre} de {len(e.pistas)}", cartel=not self.turbo)
        elif isinstance(r, dict):
            print(resumen_generacion(r), flush=True)
            if r.get("graduado") and self.modo == "terreno":
                self._graduar()
            elif r.get("etapa_nueva") is not None:
                self.avisar(f"¡DOMINÓ LA ETAPA!  Pasa a la {r['texto_etapa']}  (nivel 1; la "
                            f"generación sigue en {e.generacion})")
            elif r.get("subio"):
                self.avisar("¡SUBE DE NIVEL!  " + r["texto_nivel"])
            else:
                extra = (f" a {r['vel_lider']:.0f} km/h" if r.get("vel_lider") else "")
                if r.get("vel_rapida", 0) > r.get("vel_lider", 0) + 0.5:
                    extra += f" (la más rápida: {r['vel_rapida']:.0f} km/h)"
                if r.get("campeon_anterior") is not None:
                    extra += f" · +{r['mejor'] - r['campeon_anterior']:.1f} sobre la campeona anterior"
                self.avisar(f"Generación {r['generacion']} terminada · mejor {r['mejor']:.0f} · "
                            f"llegaron {r['llegaron']:.0f} %{_texto_limpias(r).replace('  ·  ', ' (')}"
                            f"{')' if _texto_limpias(r) else ''} · la líder terminó "
                            f"{r['terminadas_lider']}/{r['pistas']}{extra}", cartel=not self.turbo)
            self.cam = None
            self.particulas = []

    def _graduar(self):
        if not C.PASAR_A_CALLES or self._preparando:
            return
        if hay_entrenamiento_de_calles():
            self.avisar("¡Dominó todos los terrenos! (ya hay entrenamiento de calles guardado: "
                        "cámbiate con «Calles reales» cuando quieras)")
            return
        self.avisar(f"¡Dominó todos los terrenos! Pasa a calles reales de {C.ZONA_CALLES}…")
        red = self.red_vial
        if red is not None and self.ruta_usuario and self.ruta_usuario["red"] is red:
            self._cambiar_modo("ciudad", red)
        else:
            self._preparar_ciudad(K.zona_para(C.ZONA_CALLES))

    def _avisar_errores(self, sim):
        nuevos = sim.eventos[getattr(sim, "_avisados", 0):]
        sim._avisados = len(sim.eventos)
        if not nuevos:
            return
        lider = sim.ids[int(np.argmax(sim.px))] if len(sim.ids) else None
        for i, x_error, x_regreso, motivo in nuevos:
            if sim.n_total == 1 or i == lider:
                self.avisar(f"Error: {MOTIVOS[motivo]} a los {x_error - sim.pista.salida:.0f} m → "
                            f"regresa {x_error - x_regreso:.0f} m, a donde iba {C.SEG_RETROCESO:.0f} s "
                            f"antes  (error {sim.reintentos[i]} de {C.MAX_REINTENTOS})",
                            cartel=sim.n_total == 1)
                self.particulas = []

    def _info_estado(self):
        ahora = time.time()
        self._t_cuadros = [t for t in self._t_cuadros if ahora - t < 1.0] + [ahora]
        partes = [f"{len(self._t_cuadros)} cuadros/s", f"animación x{VELOCIDADES[self.i_vel]}"]
        if self.turbo:
            partes.append("TURBO")
        if self.pausa:
            partes.append("EN PAUSA")
        if self.modo == "ciudad":
            if self.e is not None and not self.demo and hasattr(self.e, "texto_etapa"):
                partes.insert(0, self.e.texto_etapa())
            partes.append(K.ATRIBUCION)
        self.lbl_info.config(text="   ·   ".join(partes))

    def sim_actual(self):
        if self.demo:
            return self.demo["sim"]
        return None if self.turbo else self.e.sim

    def dibujar(self):
        sim = self.sim_actual()
        cuadro = getattr(self, "_cuadro", 0)
        if sim is not None:
            todo = self.pausa or cuadro == 0
            self.dibujar_vista(sim)
            if cuadro % 2 == 0 or todo:
                self.dibujar_mapa(sim)
            if cuadro % 4 == 1 or todo:
                self.dibujar_equilibrio(sim)
        elif self.demo:
            self.dibujar_eligiendo()
        else:
            self.dibujar_turbo()
        self._cuadro = getattr(self, "_cuadro", 0) + 1
        if self._cuadro % 4 == 0 or self.pausa:
            self.dibujar_panel(sim)

    def _lider(self, sim):
        if len(sim.ids):
            j = int(np.argmax(sim.px))
            return j, sim.px[j], sim.py[j]
        k = 0 if (self.demo or sim.n_total == 1) else int(np.argmax(sim.progreso))
        x, y, _ = sim.pos_final[k]
        return None, x, y

    def dibujar_vista(self, sim):
        cv = self.vista
        cv.delete("all")
        p = sim.pista
        j, lx, ly = self._lider(sim)
        if self.cam is None:
            self.cam = [lx + 5, ly]
        self.cam[0] += (lx + 5 - self.cam[0]) * 0.3
        margen = ANCHO_VISTA * 0.25 / ESCALA
        self.cam[0] = min(max(self.cam[0], lx + 5 - margen), lx + 5 + margen)
        self.cam[1] += (ly - self.cam[1]) * 0.08
        cx, cy = self.cam

        def a_pantalla(x, y):
            return ANCHO_VISTA / 2 + (x - cx) * ESCALA, ALTO_VISTA * 0.70 - (y - cy) * ESCALA

        G.dibujar_cielo(cv, ANCHO_VISTA, ALTO_VISTA, cx, ESCALA)
        x0 = cx - ANCHO_VISTA / 2 / ESCALA - 1
        x1 = cx + ANCHO_VISTA / 2 / ESCALA + 1
        clima = getattr(sim, "clima", None)
        mojado = min(1.0, float(getattr(clima, "lluvia", 0.0) or 0.0) +
                     (0.4 if getattr(clima, "granizo", False) else 0.0)) if clima else 0.0
        G.dibujar_terreno(cv, p, x0, x1, a_pantalla, ESCALA, ALTO_VISTA, mojado=mojado,
                          charcos=float(getattr(clima, "charcos", 0.0) or 0.0) if clima else 0.0)

        for s0, _, rasgo, mat in p.secciones:
            if x0 - 20 < s0 < x1 and rasgo not in ("salida", "meta"):
                sx, sy = a_pantalla(s0, p.altura(s0))
                cv.create_line(sx, sy - 4, sx, sy - 104, fill="#8d97a6", dash=(2, 3))
                t = cv.create_text(sx + 8, sy - 104, anchor="w", fill=TEXTO, font=(FUENTE, 9, "bold"),
                                   text=f"{rasgo.replace('_', ' ').upper()}  ·  {mat}")
                b = cv.bbox(t)
                G.rect_redondo(cv, b[0] - 6, b[1] - 3, b[2] + 6, b[3] + 3, r=6,
                               fill="#0d1118", outline=COLORES[NOMBRES_MAT.index(mat)])
                cv.tag_raise(t)
        for xm, txt in ((p.salida, "SALIDA"), (p.meta, "META")):
            if x0 < xm < x1:
                self._bandera(cv, *a_pantalla(xm, p.altura(xm)), txt)
        pc = REC.puntos_de(sim)
        if pc is not None:
            self._puntos_vista(cv, sim, pc, j, a_pantalla, x0, x1)

        r = C.RADIO_RUEDA * ESCALA
        visibles = [k for k in np.argsort(-sim.px) if k != j and x0 - 2 < sim.px[k] < x1 + 2][:10]
        for k in visibles[::-1]:
            local = self._marco(sim.px[k], sim.py[k], sim.th[k], a_pantalla)
            ruedas = [a_pantalla(sim.wx[w, k], sim.wy[w, k]) for w in range(2)]
            G.dibujar_fantasma(cv, local, ruedas, r, "#5f6b7d")
        if j is not None:
            self._polvo(sim, j)
        self._dibujar_particulas(cv, a_pantalla)
        if j is not None:
            G.dibujar_sombra(cv, p, sim.px[j], a_pantalla, ESCALA)
            self._lidar(cv, sim, j, a_pantalla)
            local = self._marco(sim.px[j], sim.py[j], sim.th[j], a_pantalla)
            ruedas = [a_pantalla(sim.wx[w, j], sim.wy[w, j]) for w in range(2)]
            G.dibujar_moto(cv, local, ruedas, [-sim.ang[0, j], -sim.ang[1, j]], r,
                           gas=max(sim.ctrl[j, 0], 0), freno=max(-sim.ctrl[j, 0], 0))
            sx, sy = local(0.1, 1.0)
            texto = "MEJOR MOTO" if self.demo else "LÍDER"
            t = cv.create_text(sx, sy - 8, text=texto, fill="#111", font=(FUENTE, 8, "bold"))
            b = cv.bbox(t)
            G.rect_redondo(cv, b[0] - 7, b[1] - 2, b[2] + 7, b[3] + 2, r=6, fill=ORO, outline="")
            cv.create_polygon(sx - 5, b[3] + 2, sx + 5, b[3] + 2, sx, b[3] + 8, fill=ORO, outline="")
            cv.tag_raise(t)
        else:
            k = 0 if (self.demo or sim.n_total == 1) else int(np.argmax(sim.progreso))
            x, y, th = sim.pos_final[k]
            local = self._marco(x, y, th, a_pantalla)
            ruedas = [local(ex, ey) for ex, ey in C.EJES]
            G.dibujar_moto(cv, local, ruedas, [0, 0], r)
            if (self.demo or sim.n_total == 1) and not getattr(self, "cartel", None):
                ok = sim.motivo[0] == META
                exitosa = REC.exitosa(pc, sim) if pc is not None else None
                if ok and exitosa:
                    texto = f"RECORRIDO EXITOSO  ·  META EN {sim.t_fin[0]:.1f} s"
                elif ok and exitosa is False:
                    texto = f"LLEGÓ EN {sim.t_fin[0]:.1f} s, PERO FALLÓ PUNTOS DE CONTROL"
                elif ok:
                    texto = f"¡LLEGÓ A LA META EN {sim.t_fin[0]:.1f} s!"
                else:
                    texto = f"{MOTIVOS[sim.motivo[0]].upper()} A LOS {sim.progreso[0]:.0f} m"
                self._banner(cv, texto, VERDE if ok and exitosa is not False else
                             ORO if ok else ACENTO)

        if clima is not None:
            self._clima_vista(cv, sim, clima, lx)
        self._hud(cv, sim, j)

    def _fila_puntos(self, sim, j):
        if j is not None and len(sim.ids):
            return int(sim.ids[j])
        return 0 if (self.demo or sim.n_total == 1) else int(np.argmax(sim.progreso))

    def _estado_punto(self, pc, i, k):
        try:
            if pc.registrados[i, k]:
                return VERDE
            if pc.fallados[i, k]:
                return FALLADO
            if pc.iluminado[i, k]:
                return ORO
            if getattr(pc, "detectado", None) is not None and pc.detectado[i, k]:
                return ROJO_OBJETIVO
        except (IndexError, TypeError, AttributeError):
            pass
        return "#8d97a6"

    def _puntos_vista(self, cv, sim, pc, j, a_pantalla, x0, x1):
        i = self._fila_puntos(sim, j)
        reflectores = {}
        for k, pt in enumerate(REC.lista_puntos(pc)):
            x = float(getattr(pt, "x", 0.0))
            if not (x0 - 2 < x < x1 + 2):
                continue
            h = float(getattr(pt, "altura", 1.2) or 1.2)
            suelo = sim.pista.altura(x)
            sx, sy = a_pantalla(x, suelo)
            rx, ry = a_pantalla(x, suelo + h)
            col = self._estado_punto(pc, i, k)
            atras = getattr(pt, "lado", 1) < 0
            cv.create_line(sx, sy, rx, ry - 6, fill="#5d6876" if atras else "#c9d1db", width=3,
                           tags="punto")
            cv.create_rectangle(rx - 7, ry - 6, rx + 7, ry + 6, fill="#11161e", outline=col,
                                width=2, tags="punto")
            cv.create_oval(rx - 3, ry - 3, rx + 3, ry + 3, fill=col, outline="", tags="punto")
            cv.create_text(rx, ry - 14, text=f"P{k + 1}", fill=col, font=(FUENTE, 8, "bold"),
                           tags="punto")
            reflectores[k] = (rx, ry)
        if j is None:
            return
        local = self._marco(sim.px[j], sim.py[j], sim.th[j], a_pantalla)
        ox, oy = local(*G.OJO)
        for haz in (getattr(pc, "haces", None) or ()):
            try:
                ident, k, intensidad = haz[0], int(haz[1]), float(haz[2]) if len(haz) > 2 else 1.0
            except (TypeError, ValueError, IndexError):
                continue
            if int(ident) != i or k not in reflectores:
                continue
            if not pc.destello(sim.t, k):
                continue
            rx, ry = reflectores[k]
            col = G.mezclar("#3a0d0d", "#ff3b3b", min(max(intensidad, 0.4), 1))
            fase = (sim.t * DESTELLOS_HZ + 0.37 * k) % 1.0 / DESTELLO_DURACION
            for a in (fase * 0.5, 0.5 + fase * 0.5):
                b = min(a + 0.18, 1.0)
                cv.create_line(ox + (rx - ox) * a, oy + (ry - oy) * a,
                               ox + (rx - ox) * b, oy + (ry - oy) * b,
                               fill=col, width=2, tags="laser")
            for r, c in ((9, ORO), (4, "#fff3c4")):
                cv.create_oval(rx - r, ry - r, rx + r, ry + r, outline=c, width=1, tags="laser")

    def _clima_vista(self, cv, sim, clima, lx):
        lluvia = float(getattr(clima, "lluvia", 0.0) or 0.0)
        granizo = bool(getattr(clima, "granizo", False))
        niebla = float(getattr(clima, "niebla", 0.0) or 0.0)
        viento = REC.viento_relativo(sim, lx)
        empuje = (viento[0] / 3.6 * math.cos(viento[1])) if viento else 0.0
        estado = getattr(self, "_precip", None)
        if estado is None or estado.get("tam") != (ANCHO_VISTA, ALTO_VISTA):
            estado = self._precip = {"tam": (ANCHO_VISTA, ALTO_VISTA), "gotas": [], "granizo": []}
        rng = np.random.default_rng()
        quieto = self.pausa
        n_gotas = int(G.MAX_GOTAS * min(lluvia, 1.0)) if lluvia > 0.02 else 0
        n_gran = G.MAX_GRANIZO if granizo else 0
        G.dibujar_precipitacion(cv, estado, n_gotas, n_gran, empuje, ANCHO_VISTA, ALTO_VISTA,
                                rng, quieto)
        if niebla > 0.05:
            G.dibujar_niebla(cv, ANCHO_VISTA, ALTO_VISTA, niebla)
        if viento is not None:
            G.dibujar_viento(cv, ANCHO_VISTA - 72, 150, viento[0], viento[1], viento[2])

    @staticmethod
    def _marco(px, py, th, a_pantalla):
        c, s = math.cos(th), math.sin(th)
        return lambda x, y: a_pantalla(px + c * x - s * y, py + s * x + c * y)

    def _bandera(self, cv, sx, sy, texto):
        cv.create_line(sx, sy, sx, sy - 120, fill="#d9dde3", width=3)
        for k in range(4):
            for m in range(3):
                col = "#f5f5f5" if (k + m) % 2 == 0 else "#111111"
                cv.create_rectangle(sx + m * 9, sy - 120 + k * 8, sx + m * 9 + 9, sy - 112 + k * 8,
                                    fill=col, width=0)
        cv.create_text(sx + 2, sy - 132, text=texto, anchor="w", fill="white", font=(FUENTE, 10, "bold"))

    def _lidar(self, cv, sim, j, a_pantalla):
        local = self._marco(sim.px[j], sim.py[j], sim.th[j], a_pantalla)
        ox, oy = local(*G.OJO)
        for n, d in enumerate(C.DIST_LIDAR):
            tx = sim.px[j] + d
            sx, sy = a_pantalla(tx, sim.pista.altura(tx))
            col = G.mezclar("#ff4d4d", "#4a1a1a", n / len(C.DIST_LIDAR))
            cv.create_line(ox, oy, sx, sy, fill=col, dash=(4, 4))
            cv.create_oval(sx - 3, sy - 3, sx + 3, sy + 3, fill="#ff5a4f", outline="#ffd0cc")

    def _polvo(self, sim, j):
        if self.pausa:
            return
        p = sim.pista
        v = math.hypot(sim.vx[j], sim.vy[j])
        if sim.fn[0, j] <= 0 or v < 2.5:
            return
        m = NOMBRES_MAT[p.mat[p.indice(sim.wx[0, j])]]
        desliza = abs(sim.slip[0, j]) > 1.5
        if m in ("asfalto", "hielo") and not desliza:
            return
        color = "#9aa0a8" if m in ("asfalto", "hielo") else G.COLOR_SUP[NOMBRES_MAT.index(m)]
        rng = np.random.default_rng()
        for _ in range(1 + int(v / 7) + (2 if desliza else 0)):
            self.particulas.append([sim.wx[0, j] - 0.2, sim.wy[0, j] - C.RADIO_RUEDA + 0.05,
                                    -0.25 * v * rng.random() + sim.vx[j] * 0.3,
                                    0.6 + 1.6 * rng.random(), 0.6 + 0.5 * rng.random(), color])
        self.particulas = self.particulas[-40:]

    def _dibujar_particulas(self, cv, a_pantalla):
        vivas = []
        dt = 0.0 if self.pausa else C.DT_CONTROL * VELOCIDADES[self.i_vel] * 0.6
        for q in self.particulas:
            q[0] += q[2] * dt
            q[1] += q[3] * dt
            q[3] -= 4.0 * dt
            q[4] -= dt
            if q[4] <= 0:
                continue
            vivas.append(q)
            sx, sy = a_pantalla(q[0], q[1])
            rr = 1.5 + 3.5 * (1.1 - q[4])
            cv.create_oval(sx - rr, sy - rr, sx + rr, sy + rr, outline="",
                           fill=G.mezclar(q[5], G.CIELO_HORIZONTE, max(0.0, 1 - q[4])))
        self.particulas = vivas

    def _banner(self, cv, texto, color):
        y = ALTO_VISTA * 0.22
        t = cv.create_text(ANCHO_VISTA / 2, y, text=texto, fill=color, font=(FUENTE, 16, "bold"))
        b = cv.bbox(t)
        G.rect_redondo(cv, b[0] - 18, b[1] - 8, b[2] + 18, b[3] + 8, r=12, fill="#0b0f15", outline=color,
                       width=2)
        cv.tag_raise(t)

    def _hud(self, cv, sim, j):
        if self.demo and "recorrido" in self.demo:
            d = self.demo
            reps = d["recorrido"]["repeticiones"]
            t1 = cv.create_text(26, 18, anchor="nw", fill=ORO, font=(FUENTE, 13, "bold"),
                                text=f"RECORRIDO  ·  intento {min(d['rep'] + 1, reps)} de {reps}")
            t2 = cv.create_text(26, 42, anchor="nw", fill=TEXTO, font=(FUENTE, 8, "bold"),
                                text=d["titulo"])
            t3 = cv.create_text(26, 58, anchor="nw", fill=TENUE, font=(FUENTE, 8),
                                text=f"{_corto(d['descripcion'], 70)}  ·  t = {sim.t:4.1f} s")
            ancho = max(cv.bbox(t)[2] for t in (t1, t2, t3)) + 14
            fondo = G.rect_redondo(cv, 12, 10, max(340, ancho), 78, r=10, fill="#0b0f15",
                                   outline=BORDE)
            cv.tag_lower(fondo, t1)
            sub = None
        else:
            G.rect_redondo(cv, 12, 12, 340, 78, r=10, fill="#0b0f15", outline=BORDE)
        if self.demo and "recorrido" in self.demo:
            pass
        elif self.demo:
            cv.create_text(26, 22, anchor="nw", text="DEMOSTRACIÓN", fill=ORO, font=(FUENTE, 13, "bold"))
            sub = f"Pista de nivel {self.demo['nivel']}  ·  ← → cambia el nivel"
            if getattr(sim.pista, "personalizada", False):
                sub = "Recorriendo tu ruta A → B"
        else:
            cv.create_text(26, 20, anchor="nw", text=f"GENERACIÓN {self.e.generacion}", fill=TEXTO,
                           font=(FUENTE, 13, "bold"))
            e = self.e
            pista = ("tu ruta A → B" if getattr(sim.pista, "personalizada", False)
                     else f"pista {e.i_pista + 1} de {len(e.pistas)}")
            sub = f"Nivel {e.nivel}  ·  {pista}  ·  t = {sim.t:4.1f} s"
            if self.modo == "ciudad":
                sub = f"Calles reales  ·  nivel {e.nivel}  ·  {pista}  ·  t = {sim.t:4.1f} s"
        if sub is not None:
            cv.create_text(26, 52, anchor="nw", text=sub, fill=TENUE, font=(FUENTE, 8))

        if j is not None:
            v = abs(sim.vx[j] * math.cos(sim.th[j]) + sim.vy[j] * math.sin(sim.th[j])) * 3.6
            cx, cy, r = ANCHO_VISTA - 72, 72, 50
            cv.create_oval(cx - r - 8, cy - r - 8, cx + r + 8, cy + r + 8, fill="#0b0f15", outline=BORDE)
            cv.create_arc(cx - r, cy - r, cx + r, cy + r, start=-30, extent=240, style="arc",
                          outline="#253042", width=7)
            for v_zona, color in ((C.V_ESTABLE, "#5a4a1d"), (C.V_CRITICA, "#5a1d1d")):
                cv.create_arc(cx - r, cy - r, cx + r, cy + r, start=210,
                              extent=-240 * v_zona * 3.6 / 120.0, style="arc", outline=color, width=7)
            frac = min(v / 120.0, 1.0)
            col = (ACENTO if v < C.V_CRITICA * 3.6 else ORO if v < C.V_ESTABLE * 3.6
                   else VERDE if v < 90 else ACENTO)
            cv.create_arc(cx - r, cy - r, cx + r, cy + r, start=210, extent=-240 * frac, style="arc",
                          outline=col, width=7)
            cv.create_text(cx, cy - 4, text=f"{v:.0f}", fill=TEXTO, font=(FUENTE, 20, "bold"))
            cv.create_text(cx, cy + 20, text="km/h", fill=TENUE, font=(FUENTE, 8))

        p = sim.pista
        x0, x1, y = 20, ANCHO_VISTA - 20, ALTO_VISTA - 18
        largo = p.meta - p.salida
        G.rect_redondo(cv, x0 - 8, y - 14, x1 + 8, y + 10, r=8, fill="#0b0f15", outline=BORDE)
        for s0, s1, _, mat in p.secciones:
            a = x0 + (x1 - x0) * min(max((s0 - p.salida) / largo, 0), 1)
            b = x0 + (x1 - x0) * min(max((s1 - p.salida) / largo, 0), 1)
            if b > a:
                cv.create_rectangle(a, y - 3, b, y + 3, fill=COLORES[NOMBRES_MAT.index(mat)], outline="")
        marcas = {int(x0 + (x1 - x0) * min(max((sim.px[k] - p.salida) / largo, 0), 1))
                  for k in range(len(sim.ids)) if k != j}
        for xx in marcas:
            cv.create_line(xx, y - 8, xx, y - 4, fill="#c7cfda")
        if j is not None:
            xx = x0 + (x1 - x0) * min(max((sim.px[j] - p.salida) / largo, 0), 1)
            cv.create_polygon(xx - 6, y - 11, xx + 6, y - 11, xx, y - 3, fill=ORO, outline="")
        cv.create_text(x1, y - 12, anchor="se", fill=TENUE, font=(FUENTE, 7), text=f"{largo:.0f} m")

        if self.mensaje and time.time() - self.t_mensaje < 3.5:
            self._banner(cv, self.mensaje, ORO)

    def dibujar_mapa(self, sim):
        cv = self.mapa
        cv.delete("all")
        p = sim.pista
        if isinstance(p, K.PistaCalle):
            self.dibujar_mapa_ciudad(sim)
            return
        j, lx, _ = self._lider(sim)
        i_l = int(p.indice(lx))
        ang0 = p.rumbo[i_l]
        ca, sa = math.cos(-ang0), math.sin(-ang0)
        ox, oy = p.mapa_x[i_l], p.mapa_y[i_l]
        esc = ESCALA_MAPA * (ALTO_MAPA / 280) ** 0.5 * self.zoom_mapa

        def a_pantalla(mx, my):
            dx, dy = mx - ox, my - oy
            return (ANCHO_MAPA * 0.3 + (ca * dx - sa * dy) * esc,
                    ALTO_MAPA / 2 + 8 - (sa * dx + ca * dy) * esc)

        for gx in range(0, ANCHO_MAPA, 40):
            cv.create_line(gx, 0, gx, ALTO_MAPA, fill="#16211a")
        for gy in range(0, ALTO_MAPA, 40):
            cv.create_line(0, gy, ANCHO_MAPA, gy, fill="#16211a")
        a = p.indice(max(0.0, lx - ANCHO_MAPA * 0.3 / esc - 5))
        b = p.indice(lx + ANCHO_MAPA * 0.7 / esc + 5)
        idx = np.arange(a, b + 1, 10)
        ancho = max(3.0, C.ANCHO_CAMINO * esc)
        tramo = [a_pantalla(p.mapa_x[i], p.mapa_y[i]) for i in idx]
        if len(tramo) > 1:
            cv.create_line(*[c for q in tramo for c in q], fill="#060807", width=ancho + 5,
                           capstyle="round", joinstyle="round")
        n = 0
        while n < len(idx) - 1:
            m = n
            while m < len(idx) - 1 and p.mat[idx[m]] == p.mat[idx[n]]:
                m += 1
            cv.create_line(*[c for q in tramo[n:m + 1] for c in q], fill=COLORES[p.mat[idx[n]]],
                           width=ancho, capstyle="round", joinstyle="round")
            n = m
        for i in (p.indice(p.salida), p.indice(p.meta)):
            if a <= i <= b:
                h = p.rumbo[i]
                x1, y1 = a_pantalla(p.mapa_x[i] - math.sin(h) * 2.6, p.mapa_y[i] + math.cos(h) * 2.6)
                x2, y2 = a_pantalla(p.mapa_x[i] + math.sin(h) * 2.6, p.mapa_y[i] - math.cos(h) * 2.6)
                cv.create_line(x1, y1, x2, y2, fill="white", width=3)
        for k in range(len(sim.ids)):
            i = int(p.indice(sim.px[k]))
            h = p.rumbo[i]
            sx, sy = a_pantalla(p.mapa_x[i] - math.sin(h) * sim.lat[k],
                                p.mapa_y[i] + math.cos(h) * sim.lat[k])
            if k == j:
                hh = h + sim.psi[k] - ang0
                cv.create_polygon(sx + 10 * math.cos(hh), sy - 10 * math.sin(hh),
                                  sx + 6 * math.cos(hh + 2.4), sy - 6 * math.sin(hh + 2.4),
                                  sx + 6 * math.cos(hh - 2.4), sy - 6 * math.sin(hh - 2.4),
                                  fill=ORO, outline="#111")
            else:
                cv.create_oval(sx - 2, sy - 2, sx + 2, sy + 2, fill="#e7ecef", outline="")
        self._puntos_mapa(cv, sim, j, a_pantalla, lx - ANCHO_MAPA * 0.3 / esc - 5,
                          lx + ANCHO_MAPA * 0.7 / esc + 5)
        self._clima_mapa(cv, sim, lx)
        self._titulo(cv, "MAPA DESDE ARRIBA", "el camino y sus curvas  ·  rueda: zoom", "#111814")

    def _pos_mapa(self, p, x, lat):
        i = int(p.indice(x))
        h = p.rumbo[i]
        return p.mapa_x[i] - math.sin(h) * lat, p.mapa_y[i] + math.cos(h) * lat

    def _puntos_mapa(self, cv, sim, j, a_pantalla, x0=-1e18, x1=1e18):
        pc = REC.puntos_de(sim)
        if pc is None:
            return
        p = sim.pista
        i = self._fila_puntos(sim, j)
        pos = {}
        for k, pt in enumerate(REC.lista_puntos(pc)):
            x = float(getattr(pt, "x", 0.0))
            if not (x0 <= x <= x1):
                continue
            lat = float(getattr(pt, "lado", 1)) * abs(float(getattr(pt, "lateral", 2.5)))
            sx, sy = a_pantalla(*self._pos_mapa(p, x, lat))
            col = self._estado_punto(pc, i, k)
            cv.create_polygon(sx, sy - 6, sx + 6, sy, sx, sy + 6, sx - 6, sy, fill=col,
                              outline="#000", tags="punto")
            pos[k] = (sx, sy)
        if j is None or not pos:
            return
        mx, my = a_pantalla(*self._pos_mapa(p, sim.px[j], sim.lat[j]))
        for haz in (getattr(pc, "haces", None) or ()):
            try:
                ident, k = int(haz[0]), int(haz[1])
            except (TypeError, ValueError, IndexError):
                continue
            if ident == i and k in pos and pc.destello(sim.t, k):
                cv.create_line(mx, my, *pos[k], fill="#ff3b3b", width=1, dash=(3, 3),
                               tags="laser")
                sx, sy = pos[k]
                cv.create_oval(sx - 8, sy - 8, sx + 8, sy + 8, outline=ORO, width=1,
                               tags="laser")

    def _clima_mapa(self, cv, sim, lx):
        clima = getattr(sim, "clima", None)
        if clima is None:
            return
        lluvia = float(getattr(clima, "lluvia", 0.0) or 0.0)
        granizo = bool(getattr(clima, "granizo", False))
        n = int(40 * min(lluvia, 1.0)) + (14 if granizo else 0)
        if n:
            rng = np.random.default_rng()
            xs, ys = rng.random(n) * ANCHO_MAPA, rng.random(n) * ALTO_MAPA
            for k in range(n):
                if granizo and k >= n - 14:
                    cv.create_oval(xs[k] - 1.5, ys[k] - 1.5, xs[k] + 1.5, ys[k] + 1.5,
                                   fill="#f4f8fb", outline="", tags="lluvia")
                else:
                    cv.create_line(xs[k], ys[k], xs[k] - 3, ys[k] + 7, fill="#9fb8cf",
                                   tags="lluvia")
        niebla = float(getattr(clima, "niebla", 0.0) or 0.0)
        if niebla > 0.05:
            G.dibujar_niebla(cv, ANCHO_MAPA, ALTO_MAPA, niebla * 0.7)
        viento = REC.viento_relativo(sim, lx)
        if viento is not None:
            G.dibujar_viento(cv, 74, ALTO_MAPA - 56, *viento)

    def dibujar_mapa_ciudad(self, sim):
        cv = self.mapa
        p = sim.pista
        zona = p.zona
        j, lx, _ = self._lider(sim)
        i_l = int(p.indice(lx))
        cx, cy = p.mapa_x[i_l], p.mapa_y[i_l]
        esc = 1.7 * (ALTO_MAPA / 280) ** 0.5 * self.zoom_mapa

        def a_pantalla(mx, my):
            return ANCHO_MAPA / 2 + (mx - cx) * esc, ALTO_MAPA / 2 - (my - cy) * esc

        satelite, red = self.satelite, self.red_vial
        d = self.demo
        if d and d.get("red") is not None and d["red"] is not self.red_vial:
            satelite, red = d.get("satelite"), d["red"]
        if satelite is not None:
            from PIL import Image, ImageTk
            mpp = zona.m_por_px
            medio_w, medio_h = ANCHO_MAPA / 2 / esc / mpp, ALTO_MAPA / 2 / esc / mpp
            px, py = cx / mpp, -cy / mpp
            recorte = satelite.crop((int(px - medio_w), int(py - medio_h),
                                     int(px + medio_w), int(py + medio_h)))
            recorte = recorte.resize((ANCHO_MAPA, ALTO_MAPA), Image.BILINEAR)
            self._foto = ImageTk.PhotoImage(recorte)
            cv.create_image(0, 0, image=self._foto, anchor="nw")
        elif red is not None:
            x0, x1 = cx - ANCHO_MAPA / esc, cx + ANCHO_MAPA / esc
            for xs, ys in red.lineas:
                if max(xs) < x0 or min(xs) > x1:
                    continue
                pts = [c for x, y in zip(xs, ys) for c in a_pantalla(x, -y)]
                cv.create_line(*pts, fill="#3a4250", width=4)
        idx = np.arange(0, len(p.xs), 20)
        if len(idx) < 2:
            idx = np.array([0, len(p.xs) - 1])
        x_b = getattr(p, "x_b", None)

        def linea(sel, **kw):
            pts = [c for i in sel for c in a_pantalla(p.mapa_x[i], p.mapa_y[i])]
            if len(pts) >= 4:
                cv.create_line(*pts, capstyle="round", joinstyle="round", **kw)

        if x_b is None:
            linea(idx, fill="#000000", width=7, tags="ruta")
            linea(idx, fill=ORO, width=3, tags=("ruta", "ida"))
        else:
            i_b = int(p.indice(x_b))
            ida = np.r_[idx[idx < i_b], i_b]
            vuelta = np.r_[i_b, idx[idx > i_b]]
            linea(ida, fill="#000000", width=7, tags="ruta")
            linea(ida, fill=ORO, width=3, tags=("ruta", "ida"))
            linea(vuelta, fill="#000000", width=5, tags="ruta")
            linea(vuelta, fill=CIAN, width=3, dash=(8, 5), tags=("ruta", "vuelta"))
        linea([i for i in idx if p.xs[i] <= lx], fill=VERDE, width=3, tags="hecho")
        marcas = [(p.salida, "A", VERDE), (x_b if x_b is not None else p.meta, "B", ACENTO)]
        for xm, letra, col in marcas:
            sx, sy = a_pantalla(*(lambda i: (p.mapa_x[i], p.mapa_y[i]))(int(p.indice(xm))))
            if p.personalizada:
                cv.create_polygon(sx, sy, sx - 7, sy - 12, sx + 7, sy - 12, fill=col, outline="#000",
                                  tags=("marca", "marca_" + letra))
                cv.create_oval(sx - 10, sy - 30, sx + 10, sy - 10, fill=col, outline="#000", width=2,
                               tags=("marca", "marca_" + letra))
                cv.create_text(sx, sy - 20, text=letra, fill="#04130a" if letra == "A" else "white",
                               font=(FUENTE, 9, "bold"), tags=("marca", "marca_" + letra))
            else:
                cv.create_oval(sx - 7, sy - 7, sx + 7, sy + 7, fill=col, outline="#000", width=2,
                               tags=("marca", "marca_" + letra))
                cv.create_text(sx, sy, text=letra, fill="#04130a" if letra == "A" else "white",
                               font=(FUENTE, 7, "bold"), tags=("marca", "marca_" + letra))
        for k in range(len(sim.ids)):
            i = int(p.indice(sim.px[k]))
            h = p.rumbo[i]
            sx, sy = a_pantalla(p.mapa_x[i] - math.sin(h) * sim.lat[k],
                                p.mapa_y[i] + math.cos(h) * sim.lat[k])
            if k == j:
                hh = h + sim.psi[k]
                cv.create_polygon(sx + 11 * math.cos(hh), sy - 11 * math.sin(hh),
                                  sx + 7 * math.cos(hh + 2.4), sy - 7 * math.sin(hh + 2.4),
                                  sx + 7 * math.cos(hh - 2.4), sy - 7 * math.sin(hh - 2.4),
                                  fill=ORO, outline="#111", width=2)
            else:
                cv.create_oval(sx - 2.5, sy - 2.5, sx + 2.5, sy + 2.5, fill="#ffffff", outline="#111")
        self._puntos_mapa(cv, sim, j, a_pantalla)
        clima = getattr(sim, "clima", None)
        if clima is not None and float(getattr(clima, "lluvia", 0.0) or 0.0) > 0.25:
            cv.create_rectangle(0, 0, ANCHO_MAPA, ALTO_MAPA, fill="#06121f", outline="",
                                stipple="gray25", tags="mojado")
        self._clima_mapa(cv, sim, lx)
        self._titulo(cv, "CALLES REALES", f"{zona.nombre}  ·  rueda: zoom", "#0b0f15")
        if x_b is not None:
            lx0, ly0 = 12, ALTO_MAPA - 22
            G.rect_redondo(cv, lx0 - 6, ly0 - 8, lx0 + 196, ly0 + 9, r=6, fill="#0b0f15",
                           outline=BORDE, tags="leyenda")
            cv.create_line(lx0, ly0, lx0 + 18, ly0, fill=ORO, width=3, tags="leyenda")
            cv.create_text(lx0 + 23, ly0, anchor="w", text="ida A → B", fill=TEXTO,
                           font=(FUENTE, 7, "bold"), tags="leyenda")
            cv.create_line(lx0 + 92, ly0, lx0 + 110, ly0, fill=CIAN, width=3, dash=(5, 3),
                           tags="leyenda")
            cv.create_text(lx0 + 115, ly0, anchor="w", text="vuelta B → A", fill=TEXTO,
                           font=(FUENTE, 7, "bold"), tags="leyenda")
        t = cv.create_text(ANCHO_MAPA - 10, 10, anchor="ne", text="Abrir en Google Maps ↗",
                           fill=AZUL, font=(FUENTE, 8, "bold"), tags="gmaps")
        b = cv.bbox(t)
        G.rect_redondo(cv, b[0] - 6, b[1] - 3, b[2] + 6, b[3] + 3, r=6, fill="#0b0f15",
                       outline=AZUL, tags="gmaps")
        cv.tag_raise(t)
        cv.tag_bind("gmaps", "<Button-1>", self.abrir_google_maps)
        nx, ny = ANCHO_MAPA - 24, ALTO_MAPA - 26
        cv.create_oval(nx - 14, ny - 14, nx + 14, ny + 14, fill="#0b0f15", outline=BORDE)
        cv.create_polygon(nx, ny - 11, nx - 5, ny + 2, nx + 5, ny + 2, fill=ACENTO, outline="")
        cv.create_text(nx, ny + 7, text="N", fill="white", font=(FUENTE, 7, "bold"))

    def _titulo(self, cv, titulo, sub, fondo):
        t = cv.create_text(12, 10, anchor="nw", text=titulo, fill=ORO, font=(FUENTE, 8, "bold"))
        b = cv.bbox(t)
        t2 = cv.create_text(b[2] + 8, 10, anchor="nw", text=sub, fill=TENUE, font=(FUENTE, 8))
        b2 = cv.bbox(t2)
        G.rect_redondo(cv, 6, 5, b2[2] + 8, b2[3] + 4, r=6, fill=fondo, outline="")
        cv.tag_raise(t)
        cv.tag_raise(t2)

    def dibujar_equilibrio(self, sim):
        cv = self.equilibrio
        cv.delete("all")
        mitad = ANCHO_EQUILIBRIO // 2
        cv.create_line(mitad, 10, mitad, ALTO_MAPA - 10, fill=BORDE)
        cv.create_text(12, 10, anchor="nw", text="DESDE ATRÁS", fill=ORO, font=(FUENTE, 8, "bold"))
        cv.create_text(mitad + 12, 10, anchor="nw", text="DESDE ARRIBA", fill=ORO,
                       font=(FUENTE, 8, "bold"))
        j = self._lider(sim)[0]
        if j is None:
            cv.create_text(ANCHO_EQUILIBRIO / 2, ALTO_MAPA / 2, text="(sin moto en carrera)",
                           fill=TENUE, font=(FUENTE, 9))
            return
        phi, lat, psi, dirc = sim.phi[j], sim.lat[j], sim.psi[j], sim.dirc[j]
        phi_cg = phi
        phi = float(getattr(sim, "phi_moto", sim.phi)[j])

        e = min(0.34 * ALTO_MAPA, (ALTO_MAPA - 50) / 1.45)
        suelo = ALTO_MAPA - 22
        cx = mitad * 0.7
        p = sim.pista
        m = p.mat[p.indice(sim.px[j])]
        cv.create_rectangle(14, suelo, mitad - 14, suelo + 10, fill=G.COLOR_SUP[m], outline="")
        cv.create_line(14, suelo, mitad - 14, suelo, fill=G.COLOR_BORDE[m], width=2)
        cv.create_line(cx, suelo, cx, suelo - 1.45 * e, fill="#3a4659", dash=(2, 3))
        ux, uy = -math.sin(phi), -math.cos(phi)
        nx, ny = -uy, ux

        def mm(a, lado):
            return cx + ux * a * e + nx * lado * e, suelo + uy * a * e + ny * lado * e

        def poli(puntos, **kw):
            cv.create_polygon(*[c for q in puntos for c in mm(*q)], **kw)

        cv.create_oval(cx - 0.5 * e, suelo - 3, cx + 0.5 * e, suelo + 3, fill=G.COLOR_SOMBRA[m], outline="")
        cv.create_line(*mm(1.22, -0.40), *mm(1.22, 0.40), fill="#aeb6c0", width=3)
        for lado in (-1, 1):
            cv.create_line(*mm(1.22, 0.30 * lado), *mm(1.36, 0.36 * lado), fill="#5d6570", width=2)
            ex, ey = mm(1.38, 0.37 * lado)
            cv.create_oval(ex - 4, ey - 3, ex + 4, ey + 3, fill="#2c323b", outline="#9aa3ad")
        poli(((0.02, -0.12), (0.02, 0.12), (0.72, 0.12), (0.76, 0.06), (0.76, -0.06), (0.72, -0.12)),
             fill="#24262b", outline="#4a4e55", width=1)
        for k in range(1, 6):
            cv.create_line(*mm(0.12 * k, -0.10), *mm(0.12 * k + 0.04, 0.10), fill="#121316", width=2)
        poli(((0.66, -0.17), (0.66, 0.17), (0.84, 0.19), (0.84, -0.19)), fill="#23272e", outline="#4a515b")
        for lado in (-1, 1):
            ex, ey = mm(0.55, 0.30 * lado)
            cv.create_oval(ex - 6, ey - 6, ex + 6, ey + 6, fill="#9aa3ad", outline="#e3e8ee", width=2)
            cv.create_oval(ex - 3, ey - 3, ex + 3, ey + 3, fill="#1a1c20", outline="")
        poli(((0.84, -0.26), (0.84, 0.26), (1.06, 0.30), (1.16, 0.20), (1.16, -0.20), (1.06, -0.30)),
             fill="#1d2127", outline="#7d8794", width=2)
        poli(((0.90, -0.20), (0.90, 0.20), (0.97, 0.20), (0.97, -0.20)), fill="#ff3b30", outline="#ffb3ad")
        poli(((1.16, -0.16), (1.16, 0.16), (1.24, 0.12), (1.24, -0.12)), fill="#2c323b", outline="")
        cv.create_line(*mm(1.02, -0.27), *mm(1.12, -0.18), fill="#c62828", width=2)
        cv.create_line(*mm(1.02, 0.27), *mm(1.12, 0.18), fill="#c62828", width=2)
        if getattr(C, "CONTRAPESO_ACTIVO", False):
            yc = -float(sim.contra_y[j])
            cv.create_line(*mm(1.30, -0.45), *mm(1.30, 0.45), fill="#5d6570", width=2)
            poli(((1.26, yc - 0.13), (1.26, yc + 0.13), (1.48, yc + 0.10), (1.48, yc - 0.10)),
                 fill="#3b434e", outline="#ffb300", width=2)
            ox, oy = mm(1.40, yc)
            cv.create_oval(ox - 3, oy - 3, ox + 3, oy + 3, fill="#ff3b30", outline="")
        r = 1.05 * e
        grados = math.degrees(phi)
        riesgo = max(abs(phi_cg) / C.ALABEO_MAX,
                     abs(phi) / getattr(C, "ALABEO_MOTO_MAX", C.ALABEO_MAX))
        col = VERDE if riesgo < 0.5 else ORO if riesgo < 0.8 else ACENTO
        if abs(grados) > 0.5:
            cv.create_arc(cx - r, suelo - r, cx + r, suelo + r, start=90, extent=grados,
                          style="arc", outline=col, width=3)
        lado = "izq." if grados > 0.5 else "der." if grados < -0.5 else ""
        cv.create_text(12, 28, anchor="nw", text=f"{abs(grados):.1f}° {lado}", fill=col,
                       font=(FUENTE, 13, "bold"))
        cv.create_text(12, 56, anchor="nw", fill=TENUE, font=(FUENTE, 7),
                       text=f"inclinación  ·  CG {math.degrees(phi_cg):+.1f}°")
        cv.create_text(12, 72, anchor="nw", fill=TENUE, font=(FUENTE, 7),
                       text=f"bamboleo {math.degrees(sim.wob[j]):+.1f}°")
        cv.create_text(12, 88, anchor="nw", fill=TENUE, font=(FUENTE, 7),
                       text=f"se cae a {math.degrees(C.ALABEO_MAX):.0f}°")
        cv.create_text(12, 104, anchor="nw", fill=TENUE, font=(FUENTE, 7),
                       text=f"estable desde {C.V_ESTABLE * 3.6:.0f} km/h")
        if getattr(C, "SUSPENSION_REALISTA", False) and hasattr(sim, "uso_estructura"):
            try:
                uso = 100 * float(sim.uso_estructura()[j])
                pico = 100 * float(sim.uso_max[j])
            except (IndexError, TypeError, AttributeError):
                uso = pico = 0.0
            cv.create_text(12, 120, anchor="nw", font=(FUENTE, 7),
                           fill=VERDE if pico < 60 else ORO if pico < 90 else ACENTO,
                           text=f"estructura {uso:.0f} % · pico {pico:.0f} %")
        v = abs(sim.vx[j] * math.cos(sim.th[j]) + sim.vy[j] * math.sin(sim.th[j]))
        lx0, lx1, ly = 12, mitad * 0.42, ALTO_MAPA - 40
        contra = getattr(C, "CONTRAPESO_ACTIVO", False)
        cv.create_text(lx0, ly - 14, anchor="nw", fill=TENUE, font=(FUENTE, 7),
                       text=(f"contrapeso {abs(float(sim.contra_y[j])) * 100:.0f} cm "
                             f"· riel {float(sim.contra_x[j]) * 100:+.0f} cm") if contra else "lastre activo")
        cv.create_rectangle(lx0, ly, lx1, ly + 6, fill="#0c1118", outline="")
        medio = (lx0 + lx1) / 2
        carga = float(sim.contra_y[j]) / C.CONTRA_Y_MAX if contra else float(sim.lastre[j]) / C.LASTRE_MAX
        fin = medio - (lx1 - medio) * max(-1.0, min(1.0, carga))
        cv.create_rectangle(min(medio, fin), ly, max(medio, fin), ly + 6, fill=AZUL, outline="")
        cv.create_line(medio, ly - 2, medio, ly + 8, fill=TENUE)
        gy = ly - 34
        libre = 1.0 - abs(float(sim.cmg_sat[j]))
        cv.create_text(lx0, gy - 14, anchor="nw", fill=TENUE, font=(FUENTE, 7),
                       text=f"giroscopio {100 * libre:.0f} %")
        cv.create_rectangle(lx0, gy, lx1, gy + 6, fill="#0c1118", outline="")
        cv.create_rectangle(lx0, gy, lx0 + (lx1 - lx0) * libre, gy + 6, outline="",
                            fill=VERDE if libre > 0.6 else ORO if libre > 0.3 else ACENTO)
        if not (sim.fn[:, j] > 0).any():
            cv.create_text(mitad - 12, 10, anchor="ne", text="EN EL AIRE", fill=AZUL,
                           font=(FUENTE, 8, "bold"))
        elif v < C.V_ESTABLE:
            cv.create_text(mitad - 12, 10, anchor="ne", text="¡MUY LENTO!" if v < C.V_CRITICA else "LENTO: INESTABLE", fill=ACENTO,
                           font=(FUENTE, 8, "bold"))

        e2 = min(0.12 * ALTO_MAPA, (mitad - 125) / C.ANCHO_CAMINO)
        borde = C.ANCHO_CAMINO / 2 * e2
        ax = mitad + 14 + borde
        cv.create_rectangle(ax - borde - 6, 30, ax + borde + 6, ALTO_MAPA - 10,
                            fill=G.mezclar(G.COLOR_SUP[m], "#000000", 0.5), outline="")
        cv.create_rectangle(ax - borde, 30, ax + borde, ALTO_MAPA - 10, fill=COLORES[m], outline="")
        for xb in (ax - borde, ax + borde):
            cv.create_line(xb, 30, xb, ALTO_MAPA - 10, fill="#f2f2f2", width=2)
        avance = (sim.px[j] * e2) % 24
        cv.create_rectangle(ax, 30, ax + borde, ALTO_MAPA - 10,
                            fill=G.mezclar(COLORES[m], "#3ddc84", 0.18), outline="")
        for yy in range(30, ALTO_MAPA + 24, 24):
            y0 = yy + avance - 24
            if 30 <= y0 <= ALTO_MAPA - 22:
                cv.create_line(ax, y0, ax, y0 + 10, fill="#f2f2f2", width=2)
        bx, by = ax - lat * e2, ALTO_MAPA / 2 + 22
        dx, dy = -math.sin(psi), -math.cos(psi)
        rx, ry = -dy, dx

        def t(a, lado):
            return bx + dx * a * e2 + rx * lado * e2, by + dy * a * e2 + ry * lado * e2

        def poli2(puntos, **kw):
            cv.create_polygon(*[c for q in puntos for c in t(*q)], **kw)

        poli2(((-1.2, -0.09), (-0.44, -0.09), (-0.44, 0.09), (-1.2, 0.09)), fill="#101113", outline="#444")
        fx, fy = t(0.86, 0)
        gx, gy = -math.sin(psi + dirc) * 0.38 * e2, -math.cos(psi + dirc) * 0.38 * e2
        cv.create_line(fx - gx, fy - gy, fx + gx, fy + gy, fill="#101113", width=5)
        poli2(((1.08, 0), (0.6, 0.22), (-0.6, 0.2), (-1.02, 0.1), (-1.02, -0.1), (-0.6, -0.2),
               (0.6, -0.22)), fill="#1d2127", outline="#7d8794", width=2)
        poli2(((0.0, 0.08), (0.55, 0.12), (0.55, -0.12), (0.0, -0.08)), fill="#2c323b", outline="")
        hx, hy = t(0.62, 0)
        mx, my = math.cos(psi + dirc) * 0.45 * e2, -math.sin(psi + dirc) * 0.45 * e2
        cv.create_line(hx - mx, hy - my, hx + mx, hy + my, fill="#cfd6de", width=3)
        ox, oy = t(1.0, 0)
        cv.create_oval(ox - 3, oy - 3, ox + 3, oy + 3, fill="#ff2a2a", outline="")
        dev = lat - C.LAT_CARRIL
        lado = "izq." if dev > 0.05 else "der." if dev < -0.05 else "centrada"
        if lat > 0:
            cv.create_text(ANCHO_EQUILIBRIO - 10, 30 + 3 * 40 + 4, anchor="ne", fill=ACENTO,
                           text="INVADE EL\nOTRO CARRIL", font=(FUENTE, 8, "bold"), justify="right")
        else:
            cv.create_text(ANCHO_EQUILIBRIO - 10, 30 + 3 * 40 + 4, anchor="ne", fill=VERDE,
                           text="en su carril", font=(FUENTE, 8, "bold"))
        for n, (etq, val) in enumerate((("manubrio", f"{math.degrees(dirc):+.1f}°"),
                                        ("rumbo", f"{math.degrees(psi):+.1f}°"),
                                        ("desvío de su carril", f"{abs(dev):.2f} m {lado}"))):
            cv.create_text(ANCHO_EQUILIBRIO - 10, 30 + n * 40, anchor="ne", fill=TENUE,
                           font=(FUENTE, 7), text=etq)
            cv.create_text(ANCHO_EQUILIBRIO - 10, 43 + n * 40, anchor="ne", fill=TEXTO,
                           font=(FUENTE, 10, "bold"), text=val)

    def dibujar_turbo(self):
        self.mapa.delete("all")
        self.equilibrio.delete("all")
        cv = self.vista
        cv.delete("all")
        for k in range(20):
            cv.create_rectangle(0, ALTO_VISTA * k / 20, ANCHO_VISTA, ALTO_VISTA * (k + 1) / 20 + 1,
                                width=0, fill=G.mezclar("#0b1018", "#1a1420", k / 19))
        e = self.e
        sim = e.sim
        cx, cy = ANCHO_VISTA / 2, ALTO_VISTA / 2
        cv.create_text(cx, cy - 70, fill=ORO, font=(FUENTE, 26, "bold"),
                       text="⚡ TURBO" if self.turbo else f"PISTA {e.i_pista + 1} DE {len(e.pistas)}")
        cv.create_text(cx, cy - 32, fill=TEXTO, font=(FUENTE, 11),
                       text="Entrenando sin animación para ir más rápido" if self.turbo else
                       "Las demás pistas de la generación se simulan sin animación")
        w = 420
        paralelo = e.en_paralelo() if hasattr(e, "en_paralelo") else 0
        G.rect_redondo(cv, cx - w / 2, cy, cx + w / 2, cy + 16, r=8, fill="#1a2230", outline="")
        if paralelo:
            u = (time.time() * 0.8) % 2.0
            u = u if u < 1.0 else 2.0 - u
            G.rect_redondo(cv, cx - w / 2 + (w - 90) * u, cy, cx - w / 2 + (w - 90) * u + 90, cy + 16,
                           r=8, fill=ORO, outline="")
            texto = (f"Generación {e.generacion}  ·  {len(e.pistas)} pistas a la vez en "
                     f"{paralelo} procesos  ·  {len(e.pob)} motos")
        else:
            frac = (e.i_pista + min(sim.t / sim.pista.tiempo_max, 1.0)) / len(e.pistas)
            if frac > 0.02:
                G.rect_redondo(cv, cx - w / 2, cy, cx - w / 2 + w * frac, cy + 16, r=8, fill=ORO, outline="")
            texto = (f"Generación {e.generacion}  ·  pista {e.i_pista + 1}/{len(e.pistas)}  ·  "
                     f"{len(sim.ids)} motos en carrera  ·  t = {sim.t:4.1f} s")
        cv.create_text(cx, cy + 40, fill=TENUE, font=(FUENTE, 10), text=texto)
        if self.turbo:
            cv.create_text(cx, cy + 62, fill=TENUE, font=(FUENTE, 9), text=_texto_hardware())
        self._titulo(self.mapa, "MAPA DESDE ARRIBA", "(sin animación)", "#111814")

    def dibujar_eligiendo(self):
        self.mapa.delete("all")
        self.equilibrio.delete("all")
        cv = self.vista
        cv.delete("all")
        for k in range(20):
            cv.create_rectangle(0, ALTO_VISTA * k / 20, ANCHO_VISTA, ALTO_VISTA * (k + 1) / 20 + 1,
                                width=0, fill=G.mezclar("#0b1018", "#10202a", k / 19))
        d = self.demo
        cx, cy = ANCHO_VISTA / 2, ALTO_VISTA / 2
        puntos = "." * (1 + int(time.time() * 3) % 3)
        cv.create_text(cx, cy - 60, fill=ORO, font=(FUENTE, 24, "bold"),
                       text=f"Eligiendo al mejor{puntos}", tags="eligiendo")
        n = len(d.get("candidatos", ()))
        cv.create_text(cx, cy - 22, fill=TEXTO, font=(FUENTE, 11),
                       text=f"{n} motos del salón de la fama recorren {REC.SEMILLAS_PREEVALUACION} "
                            f"veces este recorrido sin animación")
        cv.create_text(cx, cy + 6, fill=TENUE, font=(FUENTE, 10),
                       text=f"{d.get('descripcion', '')}  ·  "
                            f"{REC.texto_clima(REC.nombre_de(d.get('clima')))}")
        cv.create_text(cx, cy + 34, fill=TENUE, font=(FUENTE, 9),
                       text="Gana: llegó sin errores > llegó > avanzó más > aptitud  ·  "
                            "el entrenamiento está en pausa")
        self._titulo(self.mapa, "RECORRIDO", "preparando…", "#111814")

    def _tarjeta(self, cv, y, h, titulo, extra=""):
        self._fondo = G.rect_redondo(cv, 2, y, ANCHO_PANEL - 2, y + h, r=12, fill=TARJETA,
                                     outline=BORDE)
        cv.create_text(16, y + 10, anchor="nw", text=titulo, fill=ORO, font=(FUENTE, 8, "bold"))
        if extra:
            cv.create_text(ANCHO_PANEL - 16, y + 10, anchor="ne", text=extra, fill=TENUE,
                           font=(FUENTE, 8))
        return y + 30

    def dibujar_panel(self, sim):
        cv = self.panel
        cv.delete("all")
        alto = int(cv["height"])
        y = 0

        recorrido = bool(self.demo) and "recorrido" in self.demo
        y0 = self._tarjeta(cv, y, 104, "ENTRENAMIENTO" if not self.demo else
                           "RECORRIDO" if recorrido else "DEMOSTRACIÓN",
                           f"velocidad x{VELOCIDADES[self.i_vel]}" + ("  ·  PAUSA" if self.pausa else ""))
        if recorrido:
            dd = self.demo
            intentos = dd["intentos"]
            reps = dd["recorrido"]["repeticiones"]
            mosaicos = (("GENERACIÓN", str(dd["datos"].get("generacion", "…"))),
                        ("NIVEL PISTA", str(dd["nivel"])),
                        ("INTENTO", f"{min(dd['rep'] + 1, reps)}/{reps}"),
                        ("LLEGARON", str(sum(i[1] for i in intentos))))
            pie = dd.get("preeval") or "Eligiendo a la mejor moto…"
            pie = _corto(pie, 64)
        elif self.demo:
            intentos = self.demo["intentos"]
            d = self.demo["datos"]
            mosaicos = (("NIVEL PISTA", str(self.demo["nivel"])),
                        ("INTENTOS", str(len(intentos))),
                        ("LLEGARON", str(sum(i[1] for i in intentos))),
                        ("GENERACIÓN", str(d.get("generacion", "?"))))
            pie = f"Mejor moto guardada, entrenada hasta el nivel {d.get('nivel', '?')}"
        else:
            e = self.e
            vivas = f"{len(sim.ids)}/{sim.n_total}" if sim is not None else "—"
            llegaron = str(int((sim.motivo == META).sum())) if sim is not None else "—"
            mosaicos = (("GENERACIÓN", str(e.generacion)), ("NIVEL", f"{e.nivel}/{C.NIVEL_MAX}"),
                        ("EN CARRERA", vivas), ("LLEGARON", llegaron))
            pie = f"{e.n} motos  ·  {len(e.pistas)} pistas por generación  ·  mutación σ {e.sigma:.2f}"
            if self.modo == "terreno" and C.PASAR_A_CALLES and not hay_entrenamiento_de_calles():
                pie = (f"Plan: terrenos → calles reales (al dominar el nivel {C.NIVEL_MAX})  ·  "
                       f"σ {e.sigma:.2f}")
        w = (ANCHO_PANEL - 32) / 4
        for n, (etq, val) in enumerate(mosaicos):
            x = 14 + n * w
            G.rect_redondo(cv, x, y0, x + w - 6, y0 + 46, r=8, fill="#0c1118", outline="")
            cv.create_text(x + (w - 6) / 2, y0 + 18, text=val, fill=TEXTO, font=(FUENTE, 14, "bold"))
            cv.create_text(x + (w - 6) / 2, y0 + 37, text=etq, fill=TENUE, font=(FUENTE, 7))
        cv.create_text(16, y0 + 54, anchor="nw", text=pie, fill=TENUE, font=(FUENTE, 8))
        y += 112

        nivel = self.demo["nivel"] if self.demo else self.e.nivel
        if sim is not None:
            en_calles = isinstance(sim.pista, K.PistaCalle)
        elif recorrido:
            en_calles = self.demo["recorrido"]["modo"] == "ciudad"
        else:
            en_calles = self.modo == "ciudad"
        if en_calles:
            y = self._tarjeta_ciudad(cv, sim, y, nivel)
        else:
            y = self._tarjeta_terrenos(cv, y, nivel)

        y = self._telemetria(cv, sim, y)

        self._tarjeta_final(cv, y, alto)

    def _tarjeta_ciudad(self, cv, sim, y, nivel):
        propia = sim is not None and getattr(sim.pista, "personalizada", False)
        pista = sim.pista if sim is not None and isinstance(sim.pista, K.PistaCalle) else None
        if pista is None and self.demo and "recorrido" in self.demo:
            pista = self.demo["pista"]
        zona = pista.zona if pista is not None else self.red_vial.zona
        sup = getattr(pista, "superficie", None) or (self.e.superficie if self.e is not None and
                                                     self.e.modo == "ciudad" else
                                                     getattr(C, "CALLES_SUPERFICIE", "pavimento"))
        circ = getattr(pista, "circuito", None) or (self.e.circuito if self.e is not None and
                                                    self.e.modo == "ciudad" else
                                                    getattr(C, "CALLES_CIRCUITO", "no"))
        circuito = getattr(pista, "x_b", None) is not None or (pista is None and circ != "no")
        titulo = (("TU CIRCUITO A → B → A" if circuito else "TU RUTA A → B") if propia else
                  f"CALLES REALES · NIVEL {nivel}" + ("  ·  CIRCUITO" if circuito else ""))
        y0 = self._tarjeta(cv, y, 100, titulo, NOMBRE_SUPERFICIE.get(sup, sup))
        fondo = self._fondo
        cv.create_text(16, y0, anchor="nw", text=_corto(zona.nombre, 26), fill=TEXTO,
                       font=(FUENTE, 10, "bold"))
        if not self.demo and self.e is not None and hasattr(self.e, "texto_etapa"):
            cv.create_text(ANCHO_PANEL - 16, y0 + 2, anchor="ne", fill=ORO, font=(FUENTE, 8),
                           text=_corto(self.e.texto_etapa(), 40), tags="etapa")
            if getattr(pista, "repaso", None) is not None:
                cv.create_text(ANCHO_PANEL - 16, y0 + 2, anchor="ne", fill=AZUL, font=(FUENTE, 8),
                               text=f"repaso de la etapa {pista.repaso + 1}", tags="repaso")
                cv.delete("etapa")
        texto = f"Rutas de unos {K.largo_ruta(nivel):.0f} m respetando los sentidos de las calles."
        if circ != "no" and pista is None:
            texto += f" {NOMBRE_CIRCUITO.get(circ, circ).capitalize()}."
        if pista is not None:
            if pista.x_b is not None if hasattr(pista, "x_b") else False:
                texto = (f"Circuito de {pista.meta - pista.salida:.0f} m (B a los "
                         f"{pista.x_b - pista.salida:.0f} m):  " + pista.resumen())
            else:
                texto = f"Ruta de {pista.meta - pista.salida:.0f} m:  " + pista.resumen()
        t = cv.create_text(16, y0 + 20, anchor="nw", width=ANCHO_PANEL - 32, fill=TENUE,
                           font=(FUENTE, 8), text=texto)
        b = cv.bbox(t)
        n = min(len(texto), 150)
        while b[3] > y0 + 62 and n > 20:
            cv.itemconfig(t, text=texto[:n].rstrip() + "…")
            b = cv.bbox(t)
            n -= 15
        abajo = b[3] + 10
        cv.delete(fondo)
        cv.tag_lower(G.rect_redondo(cv, 2, y, ANCHO_PANEL - 2, abajo, r=12, fill=TARJETA,
                                    outline=BORDE))
        return abajo + 8

    def _tarjeta_terrenos(self, cv, y, nivel):
        rasgos, mats, *_ = datos_nivel(nivel)
        y0 = self._tarjeta(cv, y, 100, f"TERRENOS DEL NIVEL {nivel}")
        fondo = self._fondo
        x = 16
        for m in mats:
            t = cv.create_text(x + 16, y0 + 8, anchor="w", text=m, fill=TEXTO, font=(FUENTE, 8))
            b = cv.bbox(t)
            if b[2] > ANCHO_PANEL - 16:
                x, y0 = 16, y0 + 22
                cv.coords(t, x + 16, y0 + 8)
                b = cv.bbox(t)
            G.rect_redondo(cv, x, y0, b[2] + 8, y0 + 17, r=8, fill="#0c1118", outline=BORDE)
            col = COLORES[NOMBRES_MAT.index(m)]
            cv.create_oval(x + 5, y0 + 4, x + 13, y0 + 12, fill=col, outline="")
            cv.tag_raise(t)
            x = b[2] + 14
        t = cv.create_text(16, y0 + 24, anchor="nw", width=ANCHO_PANEL - 32, fill=TENUE,
                           font=(FUENTE, 8), text=", ".join(r.replace("_", " ") for r in rasgos))
        abajo = cv.bbox(t)[3] + 10
        cv.delete(fondo)
        cv.tag_lower(G.rect_redondo(cv, 2, y, ANCHO_PANEL - 2, abajo, r=12, fill=TARJETA,
                                    outline=BORDE))
        return abajo + 8

    def _tarjeta_final(self, cv, y, alto):
        if self.demo:
            d = self.demo
            intentos = d["intentos"]
            y0 = self._tarjeta(cv, y, alto - y - 2, "ÚLTIMOS INTENTOS",
                               f"{sum(i[1] for i in intentos)} de {len(intentos)} llegaron")
            if "recorrido" in d and d.get("sim") is not None:
                y0 = self._lista_puntos(cv, d, y0, alto)
            for n, intento in enumerate(intentos[::-1]):
                niv, ok, txt = intento[:3]
                exitosa = intento[3] if len(intento) > 3 else None
                yy = y0 + n * 20
                if yy > alto - 24:
                    break
                cv.create_oval(16, yy + 4, 24, yy + 12, outline="",
                               fill=VERDE if ok and exitosa is not False else ORO if ok else ACENTO)
                extra = "  ·  EXITOSO" if exitosa else ""
                cv.create_text(32, yy, anchor="nw", fill=TEXTO, font=(FUENTE, 9),
                               text=_corto(f"Nivel {niv}:  {txt}{extra}", 58))
        else:
            self._grafica(cv, y, max(alto - y - 2, 60))

    def _lista_puntos(self, cv, d, y0, alto):
        sim, pc = d["sim"], d.get("puntos") or REC.puntos_de(d["sim"])
        filas = REC.detalle_puntos(pc, 0)
        if not filas:
            return y0
        if sim.terminado:
            ok = REC.exitosa(pc, sim)
            cv.create_text(16, y0, anchor="nw", font=(FUENTE, 9, "bold"),
                           fill=VERDE if ok else ACENTO, tags="exito",
                           text="RECORRIDO EXITOSO" if ok else "RECORRIDO NO EXITOSO")
            y0 += 18
        colw = (ANCHO_PANEL - 32) / 2
        mitad = (len(filas) + 1) // 2
        for n, (k, estado, t, kmh) in enumerate(filas):
            x = 16 + (n // mitad) * colw
            yy = y0 + (n % mitad) * 15
            if yy > alto - 60:
                continue
            col = VERDE if estado == "ok" else ACENTO if estado == "falló" else TENUE
            dato = (f"{t:.1f} s" + (f" · {kmh:.0f} km/h" if kmh is not None else "")
                    if estado == "ok" and t is not None else estado)
            cv.create_text(x, yy, anchor="nw", fill=col, font=(FUENTE, 8), tags="lista_puntos",
                           text=f"P{k + 1}  {dato}")
        return y0 + min(mitad, 12) * 15 + 8

    def _telemetria(self, cv, sim, y):
        y0 = self._tarjeta(cv, y, 190, "TELEMETRÍA" + (" DE LA LÍDER" if not self.demo else ""))
        if sim is None or len(sim.ids) == 0:
            cv.create_text(ANCHO_PANEL / 2, y0 + 50, fill=TENUE, font=(FUENTE, 9),
                           text="(sin moto en carrera)")
            self._linea_clima(cv, sim, y0 + 134)
            return y + 198
        k = int(np.argmax(sim.px))
        a, cab, dirc = sim.ctrl[k]
        luces = (("ABS", C.ABS_ACTIVO, sim.abs_[k] > 0.05),
                 ("TCS", C.TCS_ACTIVO, sim.tcs[k] > 0.05),
                 ("AMORT.", C.AMORTIGUADOR_ACTIVO, False))
        x = ANCHO_PANEL - 22
        for nombre, instalado, actua in reversed(luces):
            t = cv.create_text(x, y + 10, anchor="ne", text=nombre, font=(FUENTE, 7, "bold"),
                               fill="#111" if actua else (VERDE if instalado else "#4b5563"))
            b = cv.bbox(t)
            G.rect_redondo(cv, b[0] - 5, b[1] - 2, b[2] + 5, b[3] + 2, r=5,
                           fill=ORO if actua else "#0c1118", outline=VERDE if instalado else BORDE)
            cv.tag_raise(t)
            x = b[0] - 12
        p = sim.pista

        def barra(nombre, valor, centrada, color, yy):
            cv.create_text(16, yy, anchor="nw", text=nombre, fill=TENUE, font=(FUENTE, 8))
            x0, x1 = 92, ANCHO_PANEL - 62
            G.rect_redondo(cv, x0, yy + 3, x1, yy + 12, r=4, fill="#0c1118", outline="")
            if centrada:
                mid = (x0 + x1) / 2
                fin = mid + (x1 - mid) * max(-1.0, min(1.0, valor))
                if abs(fin - mid) > 1:
                    cv.create_rectangle(min(mid, fin), yy + 4, max(mid, fin), yy + 11, fill=color,
                                        outline="")
                cv.create_line(mid, yy + 1, mid, yy + 14, fill=TENUE)
            else:
                fin = x0 + (x1 - x0) * max(0.0, min(1.0, valor))
                if fin - x0 > 4:
                    G.rect_redondo(cv, x0, yy + 3, fin, yy + 12, r=4, fill=color, outline="")
            cv.create_text(ANCHO_PANEL - 16, yy, anchor="ne", text=f"{valor:+.2f}", fill=TEXTO,
                           font=(MONO, 8))

        barra("Acelerador", max(a, 0), False, VERDE, y0)
        barra("Freno", max(-a, 0), False, ACENTO, y0 + 18)
        barra("Cabeceo", cab, True, AZUL, y0 + 36)
        barra("Dirección", dirc, True, ORO, y0 + 54)
        barra("Derrape", sim.derrape[k] / C.DERRAPE_MAX, False, "#ff9f1c", y0 + 72)
        mat = NOMBRES_MAT[p.mat[p.indice(sim.wx[0, k])]]
        sec = next((r for s0, s1, r, _ in p.secciones if s0 <= sim.px[k] < s1), "")
        cv.create_text(16, y0 + 96, anchor="nw", fill=TEXTO, font=(FUENTE, 8),
                       text=f"Cabeceo {math.degrees(sim.th[k]):+.0f}°   ·   suelo: {mat}   ·   "
                            f"{max(sim.px[k] - p.salida, 0):.0f} de {p.meta - p.salida:.0f} m")
        cv.create_text(16, y0 + 114, anchor="nw", fill=TENUE, font=(FUENTE, 8),
                       text=f"Tramo: {_corto(sec.replace('_', ' '), 34)}   ·   "
                            f"errores {sim.reintentos[sim.ids[k]]}/{C.MAX_REINTENTOS}")
        self._linea_clima(cv, sim, y0 + 134, k)
        return y + 198

    def _linea_clima(self, cv, sim, yy, k=None):
        clima = getattr(sim, "clima", None) if sim is not None else (
            self.demo.get("clima") if self.demo else None)
        partes = [f"Clima: {REC.texto_clima(REC.nombre_de(clima))}"]
        if sim is not None:
            v = REC.viento_relativo(sim, sim.px[k] if k is not None else None)
            if v is not None:
                partes.append(f"viento {v[0]:.0f} km/h" + (" (ráfaga)" if v[2] else ""))
        cv.create_text(16, yy, anchor="nw", fill=AZUL if clima is not None else TENUE,
                       font=(FUENTE, 8, "bold"), text="  ·  ".join(partes), tags="clima")
        pc = REC.puntos_de(sim)
        if pc is not None:
            j = k if k is not None and len(sim.ids) else None
            i = self._fila_puntos(sim, j)
            try:
                hechos, total = int(np.sum(pc.registrados[i])), int(np.shape(pc.registrados)[1])
                fallos = int(np.sum(pc.fallados[i]))
            except (IndexError, TypeError, AttributeError):
                return
            cv.create_text(ANCHO_PANEL - 16, yy, anchor="ne", font=(FUENTE, 8, "bold"),
                           fill=ACENTO if fallos else VERDE if hechos == total else ORO,
                           text=f"Puntos de control {hechos}/{total}" +
                                (f" · {fallos} fallado(s)" if fallos else ""), tags="puntos")

    def _grafica(self, cv, y, h):
        y0 = self._tarjeta(cv, y, h, "APTITUD POR GENERACIÓN")
        cv.create_line(ANCHO_PANEL - 150, y + 16, ANCHO_PANEL - 136, y + 16, fill=ORO, width=2)
        cv.create_text(ANCHO_PANEL - 132, y + 16, anchor="w", text="mejor", fill=TENUE, font=(FUENTE, 8))
        cv.create_line(ANCHO_PANEL - 86, y + 16, ANCHO_PANEL - 72, y + 16, fill=AZUL, width=2)
        cv.create_text(ANCHO_PANEL - 68, y + 16, anchor="w", text="promedio", fill=TENUE,
                       font=(FUENTE, 8))
        x, w = 16, ANCHO_PANEL - 32
        hh = h - 58
        hist = self.e.historial[-200:]
        if len(hist) < 2 or hh < 30:
            cv.create_text(ANCHO_PANEL / 2, y0 + hh / 2, fill=TENUE, font=(FUENTE, 9),
                           text="La gráfica aparece tras 2 generaciones")
            return
        tope = max(180.0, max(r["mejor"] for r in hist))
        piso = min(0.0, min(r["promedio"] for r in hist))
        n = len(hist)

        def pt(i, val):
            return x + w * i / (n - 1), y0 + hh - hh * (val - piso) / (tope - piso)

        for v in (0, 50, 100, 150):
            if piso <= v <= tope:
                yy = pt(0, v)[1]
                cv.create_line(x, yy, x + w, yy, fill="#1b2431")
                cv.create_text(x + 2, yy - 1, anchor="sw", text=str(v), fill="#4b5768", font=(FUENTE, 7))
        for i in range(1, n):
            if hist[i]["nivel"] != hist[i - 1]["nivel"]:
                xx = pt(i, 0)[0]
                cv.create_line(xx, y0, xx, y0 + hh, fill="#3b4a5e", dash=(2, 2))
                if xx < x + w - 16:
                    cv.create_text(xx + 3, y0, anchor="nw", text=f"N{hist[i]['nivel']}",
                                   fill="#7f9bbd", font=(FUENTE, 7, "bold"))
        prom = [c for i, r in enumerate(hist) for c in pt(i, r["promedio"])]
        cv.create_polygon(x, y0 + hh, *prom, x + w, y0 + hh, fill="#132233", outline="")
        cv.create_line(*prom, fill=AZUL, width=1)
        mejores = np.array([r["mejor"] for r in hist])
        cv.create_line(*[c for i, v in enumerate(mejores) for c in pt(i, v)], fill="#6b5a2a")
        k = min(10, n)
        suave = np.convolve(np.r_[np.full(k - 1, mejores[0]), mejores], np.ones(k) / k, "valid")
        cv.create_line(*[c for i, v in enumerate(suave) for c in pt(i, v)], fill=ORO, width=2,
                       smooth=True)
        u = hist[-1]
        cv.create_text(16, y0 + hh + 8, anchor="nw", fill=TENUE, font=(FUENTE, 8),
                       text=f"Gen {u['generacion']}: mejor {u['mejor']:.0f}  ·  líder terminó "
                            f"{u['terminadas_lider']}/{u['pistas']}" +
                            (f"  a {u['vel_lider']:.0f} km/h" if u.get("vel_lider") else "") +
                            (f" · más rápida {u['vel_rapida']:.0f}"
                             if u.get("vel_rapida", 0) > u.get("vel_lider", 0) + 0.5 else "") +
                            _texto_limpias(u))


def _texto_hardware():
    import aceleracion as A
    import paralelo as P
    motor = A.elegir(C.POBLACION)
    nombre = {"gpu": "GPU (CUDA)", "numba": "numba en CPU", "numpy": "numpy (instala numba: ~9× más rápido)"}
    return (f"Física: {nombre[motor]}  ·  {P.procesos_disponibles()} procesos  ·  " + A.resumen())


def clima_config():
    manual = getattr(C, "CLIMA_MANUAL", None)
    if manual not in (None, ""):
        return str(manual)
    return "automatico" if getattr(C, "CLIMA_AUTOMATICO", False) else "despejado"


def opciones_clima():
    return ["automatico", "despejado"] + REC.presets_clima()


def _texto_limpias(r):
    try:
        v = r.get("llegadas_limpias_pct")
        return "" if v is None else f"  ·  limpias {float(v):.0f} %"
    except (AttributeError, TypeError, ValueError):
        return ""


def _corto(texto, n):
    return texto if len(texto) <= n else texto[:n - 1] + "…"


def nitidez_windows():
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except (AttributeError, OSError):
        pass


def ejecutar(entrenador=None, demo=False, nivel_demo=None, red_vial=None, ruta=None,
             recorrido=False):
    nitidez_windows()
    raiz = tk.Tk()
    ajustar_tamano(raiz)
    App(raiz, entrenador, demo, nivel_demo, red_vial, ruta, recorrido=recorrido)
    raiz.mainloop()
