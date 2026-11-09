import os
import subprocess
import sys
import tkinter as tk
from tkinter import messagebox, ttk

import config as C
import misiones as MS
from evolucion import Entrenador, HiloEntrenamiento
import satelites as SAT
from vista_rapida import EpisodioVivo, PanelRed, PanelTeatro
from grabador import BotonGrabar

FONDO = "#0e1014"
TARJETA = "#161920"
TARJETA2 = "#1c2029"
BORDE = "#262b36"
REJILLA = "#262c39"
TEXTO = "#e8ebf1"
TENUE = "#8a93a6"
SUTIL = "#5a6275"
ACENTO = "#f5b400"
VERDE = "#38d39f"
GRIS = "#78829a"
NARANJA = "#ffa04d"
ROJO = "#ff5f5f"
TONOS = ["#4ea4ff", "#b48cff", "#3dd6f5", "#ffa04d", "#38d39f", "#ff78c8", "#f5b400", "#ff5f5f"]
FUENTE = "Segoe UI"


def mezclar(a, b, t):
    ca = [int(a[i:i + 2], 16) for i in (1, 3, 5)]
    cb = [int(b[i:i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(x + (y - x) * t):02x}" for x, y in zip(ca, cb))


def _dpi():
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        try:
            import ctypes
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


class VentanaRapida:
    def __init__(self, entrenador=None, dir_datos=None):
        _dpi()
        self.dir_datos = dir_datos
        self.ent = entrenador or Entrenador(dir_datos=dir_datos)
        self.hilo = HiloEntrenamiento(self.ent)
        self.cerrando = False
        self.raiz = tk.Tk()
        self.k = max(1.0, self.raiz.winfo_fpixels("1i") / 96)
        self.raiz.title("Escudo Global — entrenamiento rápido")
        self.raiz.configure(bg=FONDO)
        sw, sh = self.raiz.winfo_screenwidth(), self.raiz.winfo_screenheight()
        ancho, alto = min(int(1280 * self.k), sw - 40), min(int(800 * self.k), sh - 90)
        self.raiz.minsize(min(int(980 * self.k), ancho), min(int(600 * self.k), alto))
        self.raiz.geometry(f"{ancho}x{alto}+{max(0, (sw - ancho) // 2)}+8")
        self.vivo = EpisodioVivo(self.hilo)
        self.raiz.protocol("WM_DELETE_WINDOW", lambda: self._terminar(False))
        self._estilos()
        self._construir()
        self._firma_tabla = None
        self._firma_graf = None

    def _estilos(self):
        st = ttk.Style(self.raiz)
        st.theme_use("clam")
        st.configure("Treeview", background=TARJETA, fieldbackground=TARJETA, foreground=TEXTO, bordercolor=BORDE,
                     lightcolor=BORDE, darkcolor=BORDE, rowheight=int(22 * self.k), font=(FUENTE, 9), borderwidth=0)
        st.configure("Treeview.Heading", background=TARJETA2, foreground=TENUE, bordercolor=BORDE, lightcolor=TARJETA2,
                     darkcolor=TARJETA2, relief="flat", font=(FUENTE, 8, "bold"))
        st.map("Treeview.Heading", background=[("active", TARJETA2)])
        st.map("Treeview", background=[("selected", mezclar(TARJETA, ACENTO, 0.18))], foreground=[("selected", TEXTO)])
        st.layout("Treeview", [("Treeview.treearea", {"sticky": "nswe"})])

    def _boton(self, padre, texto, accion, primario=False):
        bg = ACENTO if primario else TARJETA2
        fg = FONDO if primario else TEXTO
        b = tk.Button(padre, text=texto, command=accion, bg=bg, fg=fg, activebackground=mezclar(bg, "#ffffff", 0.12),
                      activeforeground=fg, relief="flat", bd=0, highlightthickness=0, cursor="hand2",
                      font=(FUENTE, 10, "bold" if primario else "normal"), padx=14, pady=7,
                      disabledforeground=SUTIL)
        b.bind("<Enter>", lambda e: b.configure(bg=mezclar(bg, "#ffffff", 0.08)) if b["state"] == "normal" else None)
        b.bind("<Leave>", lambda e: b.configure(bg=bg))
        return b

    def _ficha(self, padre, col, titulo):
        f = tk.Frame(padre, bg=TARJETA, highlightbackground=BORDE, highlightthickness=1)
        f.grid(row=0, column=col, sticky="nsew", padx=(0 if col == 0 else 6, 0))
        tk.Label(f, text=titulo.upper(), bg=TARJETA, fg=TENUE, font=(FUENTE, 7, "bold")).pack(anchor="w", padx=10, pady=(7, 0))
        v = tk.Label(f, text="—", bg=TARJETA, fg=TEXTO, font=(FUENTE, 15, "bold"))
        v.pack(anchor="w", padx=10, pady=(0, 7))
        return v

    def _construir(self):
        r = self.raiz
        cab = tk.Frame(r, bg=FONDO)
        cab.pack(fill="x", padx=16, pady=(14, 8))
        fila = tk.Frame(cab, bg=FONDO)
        fila.pack(fill="x")
        tk.Label(fila, text="Entrenamiento rápido", bg=FONDO, fg=TEXTO, font=(FUENTE, 15, "bold")).pack(side="left")
        self.grabar = BotonGrabar(fila, r, fuente=(FUENTE, 9, "bold")).pack(side="right")
        tk.Label(cab, text=f"Sin gráficos · {self.hilo.procesos} procesos · datos en {self._carpeta()}", bg=FONDO,
                 fg=TENUE, font=(FUENTE, 9)).pack(anchor="w")

        pie = tk.Frame(r, bg=FONDO)
        pie.pack(side="bottom", fill="x", padx=16, pady=12)
        cuerpo = tk.Frame(r, bg=FONDO)
        cuerpo.pack(fill="both", expand=True)
        cuerpo.columnconfigure(0, weight=5, uniform="c")
        cuerpo.columnconfigure(1, weight=6, uniform="c")
        cuerpo.rowconfigure(0, weight=1)
        izq = tk.Frame(cuerpo, bg=FONDO)
        izq.grid(row=0, column=0, sticky="nsew")
        der = tk.Frame(cuerpo, bg=FONDO)
        der.grid(row=0, column=1, sticky="nsew", padx=(0, 16))
        caja_red = tk.Frame(der, bg=TARJETA, highlightbackground=BORDE, highlightthickness=1)
        caja_red.pack(fill="both", expand=True, pady=(0, 8))
        tk.Label(caja_red, text="RED NEURONAL EN VIVO · 24 ENTRADAS → 24 → 12 → 2 DECISIONES", bg=TARJETA, fg=TENUE,
                 font=(FUENTE, 7, "bold")).pack(anchor="w", padx=10, pady=(7, 0))
        self.lienzo_red = tk.Canvas(caja_red, bg=TARJETA2, highlightthickness=0, height=int(300 * self.k))
        self.lienzo_red.pack(fill="both", expand=True, padx=10, pady=(4, 8))
        caja_mapa = tk.Frame(der, bg=TARJETA, highlightbackground=BORDE, highlightthickness=1)
        caja_mapa.pack(fill="both", expand=True)
        tk.Label(caja_mapa, text="DÓNDE SE ESTÁ ENTRENANDO · ESCENARIO DE LA GENERACIÓN ACTUAL", bg=TARJETA, fg=TENUE,
                 font=(FUENTE, 7, "bold")).pack(anchor="w", padx=10, pady=(7, 0))
        self.lienzo_mapa = tk.Canvas(caja_mapa, bg="#12151c", highlightthickness=0, height=int(260 * self.k))
        self.lienzo_mapa.pack(fill="both", expand=True, padx=10, pady=(4, 8))
        self.panel_red = PanelRed(self.lienzo_red, self.vivo, self.k)
        self.panel_teatro = PanelTeatro(self.lienzo_mapa, self.vivo, self.k)

        fichas = tk.Frame(izq, bg=FONDO)
        fichas.pack(fill="x", padx=16)
        for i in range(4):
            fichas.columnconfigure(i, weight=1, uniform="f")
        self.v_gen = self._ficha(fichas, 0, "Generación")
        self.v_mis = self._ficha(fichas, 1, "Misión")
        self.v_gpm = self._ficha(fichas, 2, "Gen / min")
        self.v_sig = self._ficha(fichas, 3, "Sigma σ")
        linea = tk.Frame(izq, bg=FONDO)
        linea.pack(fill="x", padx=16, pady=(6, 0))
        self.v_nombre = tk.Label(linea, text="", bg=FONDO, fg=ACENTO, font=(FUENTE, 10, "bold"))
        self.v_nombre.pack(side="left")
        self.v_estado = tk.Label(linea, text="", bg=FONDO, fg=TENUE, font=(FUENTE, 9))
        self.v_estado.pack(side="right")

        caja = tk.Frame(izq, bg=TARJETA, highlightbackground=BORDE, highlightthickness=1)
        caja.pack(fill="both", expand=True, padx=16, pady=(8, 0))
        tk.Label(caja, text="PROTECCIÓN Y DESPERDICIO POR GENERACIÓN", bg=TARJETA, fg=TENUE,
                 font=(FUENTE, 7, "bold")).pack(anchor="w", padx=10, pady=(7, 0))
        self.lienzo = tk.Canvas(caja, bg=TARJETA2, highlightthickness=0, height=int(150 * self.k))
        self.lienzo.pack(fill="both", expand=True, padx=10, pady=(4, 2))
        self.lienzo.bind("<Configure>", lambda e: self._grafica(True))
        ley = tk.Frame(caja, bg=TARJETA)
        ley.pack(anchor="w", padx=10, pady=(0, 7))
        for t, c in (("mejor protección", VERDE), ("protección promedio", GRIS), ("desperdicio del líder", NARANJA)):
            tk.Frame(ley, bg=c, width=int(12 * self.k), height=int(3 * self.k)).pack(side="left", padx=(0, 5))
            tk.Label(ley, text=t, bg=TARJETA, fg=TENUE, font=(FUENTE, 8)).pack(side="left", padx=(0, 14))

        caja2 = tk.Frame(izq, bg=TARJETA, highlightbackground=BORDE, highlightthickness=1)
        caja2.pack(fill="both", expand=True, padx=16, pady=(8, 0))
        tk.Label(caja2, text="CAMPEONES POR MISIÓN", bg=TARJETA, fg=TENUE,
                 font=(FUENTE, 7, "bold")).pack(anchor="w", padx=10, pady=(7, 2))
        cols = (("n", "#", 34, "center"), ("nombre", "Misión", 190, "w"), ("sup", "Superada", 74, "center"),
                ("prot", "Protección", 82, "e"), ("apt", "Aptitud", 74, "e"), ("gen", "Gen.", 58, "e"))
        self.tabla = ttk.Treeview(caja2, columns=[c[0] for c in cols], show="headings", height=6, selectmode="browse")
        for c, t, w, a in cols:
            self.tabla.heading(c, text=t, anchor=a)
            self.tabla.column(c, width=int(w * self.k), anchor=a, stretch=c == "nombre")
        self.tabla.tag_configure("ok", foreground=VERDE)
        self.tabla.tag_configure("no", foreground=ACENTO)
        self.tabla.tag_configure("vacio", foreground=SUTIL)
        self.tabla.tag_configure("actual", background=TARJETA2)
        rep = tk.Frame(caja2, bg=TARJETA)
        rep.pack(side="bottom", fill="x", padx=10, pady=(0, 8))
        tk.Label(rep, text="REPETIR", bg=TARJETA, fg=TENUE, font=(FUENTE, 7, "bold")).pack(side="left", padx=(0, 6))
        self.v_rep = tk.StringVar(value=self._etiqueta_mision(self.ent.mision_actual))
        self.combo = ttk.Combobox(rep, textvariable=self.v_rep, state="readonly", width=32, font=(FUENTE, 9),
                                  values=[self._etiqueta_mision(n) for n in range(1, MS.NUMERO_MISIONES + 1)])
        self.combo.pack(side="left", padx=(0, 6))
        self._boton(rep, "Repetir esta misión", self._repetir_una).pack(side="left", padx=(0, 6))
        self._boton(rep, "Repetir todas", self._repetir_todas).pack(side="left")
        self.tabla.bind("<<TreeviewSelect>>", self._elegir_fila)
        barra = ttk.Scrollbar(caja2, orient="vertical", command=self.tabla.yview)
        self.tabla.configure(yscrollcommand=barra.set)
        barra.pack(side="right", fill="y", padx=(0, 4), pady=(0, 8))
        self.tabla.pack(fill="both", expand=True, padx=(10, 0), pady=(0, 8))
        for n in range(1, MS.NUMERO_MISIONES + 1):
            self.tabla.insert("", "end", iid=str(n), values=(n, MS.NOMBRES[n - 1], "—", "—", "—", "—"), tags=("vacio",))

        self.b_volver = self._boton(pie, "Volver al modo gráfico", lambda: self._terminar(True), primario=True)
        self.b_volver.pack(side="left")
        self.b_detener = self._boton(pie, "Detener y guardar", lambda: self._terminar(False))
        self.b_detener.pack(side="right")
        self.b_borrar = self._boton(pie, "Borrar lo aprendido", self._borrar)
        self.b_borrar.pack(side="right", padx=(0, 8))
        self.b_sat = self._boton(pie, "", self._satelites)
        self.b_sat.pack(side="right", padx=(0, 8))
        self.b_salva = self._boton(pie, "", self._salva)
        self.b_salva.pack(side="right", padx=(0, 8))
        self._texto_sat()

    def _etiqueta_mision(self, n):
        return f"{n}. {MS.NOMBRES[n - 1]}"

    def _elegir_fila(self, _e=None):
        sel = self.tabla.selection()
        if sel:
            self.v_rep.set(self._etiqueta_mision(int(sel[0])))

    def _repetir_una(self):
        try:
            n = int(self.v_rep.get().split(".")[0])
        except ValueError:
            return
        self.ent.repetir(n)
        self.hilo.instantanea = None
        self.vivo.reiniciar()
        self._firma_tabla = None
        self.v_estado.configure(text=f"Repitiendo la misión {n}: al superarla sigue con su currículo", fg=ACENTO)

    def _repetir_todas(self):
        if not messagebox.askyesno("Repetir todas", "¿Volver a entrenar todas las misiones desde la 1? "
                                   "La red conserva lo aprendido; sólo se reinician los campeones.", parent=self.raiz):
            return
        self.ent.repetir(None)
        self.hilo.instantanea = None
        self.vivo.reiniciar()
        self._firma_tabla = None

    def _texto_sat(self):
        modo = SAT._a_modo(self.ent.cfg.get("satelites", C.SAT_DEFECTO))
        self.b_sat.configure(text=f"Satélites: {SAT.CORTOS[modo]}")
        doble = self.ent.cfg.get("salva") == "doble"
        self.b_salva.configure(text="Disparo: doble en críticos" if doble else "Disparo: 1 por objetivo")

    def _salva(self):
        with self.ent.bloqueo:
            self.ent.cfg["salva"] = "una" if self.ent.cfg.get("salva") == "doble" else "doble"
        self._texto_sat()

    def _satelites(self):
        modo = (SAT._a_modo(self.ent.cfg.get("satelites", C.SAT_DEFECTO)) + 1) % 3
        with self.ent.bloqueo:
            self.ent.cfg["satelites"] = modo
        self._texto_sat()

    def _borrar(self):
        if self.cerrando:
            return
        if not messagebox.askyesno("Borrar lo aprendido", "¿Borrar todo lo que la IA ha aprendido? "
                                   "Se pierden los pesos, los campeones, el historial y tus demostraciones. "
                                   "El teatro y las ciudades configuradas se conservan.", parent=self.raiz):
            return
        self.ent.reiniciar()
        self.hilo.instantanea = None
        self.vivo.reiniciar()
        self._firma_tabla = None
        self.hilo.gens_por_min = 0.0
        self._grafica(True)

    def _carpeta(self):
        d = os.path.abspath(self.ent.dir)
        base = os.path.join(C.RAIZ, C.CARPETA_DATOS)
        if os.path.normcase(d) == os.path.normcase(os.path.abspath(base)):
            return C.CARPETA_DATOS + "\\"
        return "…\\" + os.path.basename(d) if len(d) > 40 else d

    def _grafica(self, forzar=False):
        hist = self.ent.historial[-300:]
        c = self.lienzo
        w, h = c.winfo_width(), c.winfo_height()
        firma = (len(self.ent.historial), hist[-1]["generacion"] if hist else 0, w, h)
        if not forzar and firma == self._firma_graf:
            return
        self._firma_graf = firma
        c.delete("all")
        k = self.k
        x0, y0, x1, y1 = 34 * k, 8 * k, w - 8 * k, h - 18 * k
        if x1 - x0 < 20 or y1 - y0 < 20:
            return
        n = len(hist)
        if n >= 2:
            ini = 0
            for i in range(1, n + 1):
                if i == n or hist[i]["mision"] != hist[ini]["mision"]:
                    a = x0 + (x1 - x0) * ini / (n - 1)
                    b = x0 + (x1 - x0) * (i - 1) / (n - 1)
                    tono = TONOS[(hist[ini]["mision"] - 1) % len(TONOS)]
                    c.create_rectangle(a, y0, max(b, a + 1), y1, fill=mezclar(TARJETA2, tono, 0.1), width=0)
                    if b - a > 14 * k:
                        c.create_text(a + 4 * k, y0 + 3 * k, text=str(hist[ini]["mision"]), anchor="nw", fill=tono,
                                      font=(FUENTE, 7, "bold"))
                    ini = i
        for p in (0, 25, 50, 75, 100):
            y = y1 - (y1 - y0) * p / 100
            c.create_line(x0, y, x1, y, fill=REJILLA)
            c.create_text(x0 - 5 * k, y, text=f"{p}%", anchor="e", fill=SUTIL, font=(FUENTE, 7))
        if n < 2:
            c.create_text((x0 + x1) / 2, (y0 + y1) / 2, text="La gráfica aparece tras 2 generaciones", fill=SUTIL,
                          font=(FUENTE, 9))
            return
        for clave, col, grosor in (("desperdicio_lider", NARANJA, 1.5), ("promedio_proteccion", GRIS, 1.5),
                                   ("mejor_proteccion", VERDE, 2)):
            pts = []
            for i, r in enumerate(hist):
                pts += [x0 + (x1 - x0) * i / (n - 1), y1 - (y1 - y0) * min(100.0, max(0.0, float(r[clave]))) / 100]
            c.create_line(*pts, fill=col, width=grosor * k)
        c.create_text(x0, y1 + 3 * k, text=f"gen {hist[0]['generacion']}", anchor="nw", fill=SUTIL, font=(FUENTE, 7))
        c.create_text(x1, y1 + 3 * k, text=f"gen {hist[-1]['generacion']}", anchor="ne", fill=SUTIL, font=(FUENTE, 7))

    def _tabla(self):
        with self.ent.bloqueo:
            camp = {n: (v["superada"], v["proteccion"], v["aptitud"], v["generacion"]) for n, v in self.ent.campeones.items()}
        actual = self.ent.mision_actual
        firma = (tuple(sorted(camp.items())), actual)
        if firma == self._firma_tabla:
            return
        self._firma_tabla = firma
        for n in range(1, MS.NUMERO_MISIONES + 1):
            tags = []
            if n in camp:
                sup, prot, apt, gen = camp[n]
                vals = (n, MS.NOMBRES[n - 1], "Sí" if sup else "No", f"{100 * prot:.1f}%", f"{apt:.1f}", gen)
                tags.append("ok" if sup else "no")
            else:
                vals = (n, MS.NOMBRES[n - 1], "—", "—", "—", "—")
                tags.append("vacio")
            if n == actual:
                tags.append("actual")
            self.tabla.item(str(n), values=vals, tags=tags)

    def _refrescar(self):
        if self.cerrando:
            return
        ent, hilo = self.ent, self.hilo
        mis = ent.mision_actual
        self.v_gen.configure(text=str(ent.generacion))
        self.v_mis.configure(text=f"{mis} / {MS.NUMERO_MISIONES}")
        self.v_gpm.configure(text=f"{hilo.gens_por_min:.1f}" if hilo.gens_por_min else "—")
        self.v_sig.configure(text=f"{ent.sigma:.4f}")
        self.v_nombre.configure(text=MS.NOMBRES[mis - 1] + (" · currículo completo (repaso)" if ent.completada else ""))
        estado = hilo.estado if hilo.activo else "Detenido — cierra la ventana o vuelve al modo gráfico"
        self.v_estado.configure(text=estado, fg=TENUE if hilo.activo else ROJO)
        self._grafica()
        self._tabla()
        self.raiz.after(500, self._refrescar)

    def _animar(self):
        if self.cerrando:
            return
        try:
            self.vivo.avanzar()
            self.panel_teatro.dibujar()
            self.panel_red.dibujar()
        except Exception as e:
            self.vivo.reiniciar()
            self.v_estado.configure(text=f"Vista en vivo: {e}", fg=ROJO)
        self.raiz.after(120, self._animar)

    def _terminar(self, volver):
        if self.cerrando:
            return
        self.cerrando = True
        for b in (self.b_volver, self.b_detener):
            b.configure(state="disabled", bg=TARJETA2, fg=SUTIL)
        self.v_estado.configure(text="Deteniendo y guardando…", fg=ACENTO)
        self.raiz.update_idletasks()
        self.grabar.cerrar()
        self.hilo.parar()
        if volver:
            orden = [sys.executable, os.path.join(C.RAIZ, "main.py"), "--modo", "entrenar"]
            if self.dir_datos:
                orden += ["--datos", self.dir_datos]
            subprocess.Popen(orden, cwd=C.RAIZ, creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0))
        self.raiz.destroy()

    def correr(self):
        self.hilo.iniciar()
        self.raiz.after(200, self._refrescar)
        self.raiz.after(400, self._animar)
        try:
            self.raiz.mainloop()
        except KeyboardInterrupt:
            pass
        if not self.cerrando:
            self.cerrando = True
            self.hilo.parar()
        return self.ent
