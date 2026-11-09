import tkinter as tk
import tkinter.font as tkfont

from grabador import BotonGrabar

FONDO = "#121211"
SUPERFICIE = "#1a1a19"
BANDA = ("#1d1d1c", "#222220")
REJILLA = "#2e2e2c"
TEXTO = "#f0efec"
TEXTO_2 = "#c3c2b7"
TENUE = "#8a897f"
SERIE_1 = "#3987e5"
SERIE_2 = "#d95926"
BIEN = "#0ca30c"
PENDIENTE = "#5d5c57"
TIP = "#2b2b29"
FUENTE = "Segoe UI"


class Grafica:
    def __init__(self, titulo, todas, nombre):
        self.todas = list(todas)
        self.nombre = nombre
        self.historial = []
        self.campeones = {}
        self.accion = None
        self.vivo = True
        try:
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass
        self.raiz = tk.Tk()
        self.k = max(1.0, self.raiz.winfo_fpixels("1i") / 96)
        self.raiz.title(titulo)
        self.raiz.configure(bg=FONDO)
        ancho = min(int(1000 * self.k), self.raiz.winfo_screenwidth() - 80)
        alto = min(int(720 * self.k), self.raiz.winfo_screenheight() - int(110 * self.k))
        self.raiz.geometry(f"{ancho}x{alto}+{int(20 * self.k)}+{int(10 * self.k)}")
        self.raiz.minsize(int(640 * self.k), int(480 * self.k))
        self.raiz.protocol("WM_DELETE_WINDOW", self.salir)
        arriba = tk.Frame(self.raiz, bg=FONDO)
        arriba.pack(fill="x", padx=16, pady=(14, 6))
        tk.Label(arriba, text=titulo, bg=FONDO, fg=TEXTO, font=(FUENTE, 15, "bold")).pack(side="left")
        self.b_det = self._boton(arriba, "Detener y guardar", lambda: self._pedir("detener"))
        self.b_det.pack(side="right", padx=(8, 0))
        self.b_sim = self._boton(arriba, "Abrir el simulador gráfico", lambda: self._pedir("simulador"), True)
        self.b_sim.pack(side="right")
        self.grabar = BotonGrabar(arriba, self.raiz, lambda t: self.estado.configure(text=t),
                                  (FUENTE, 10, "bold")).pack(side="right", padx=(0, 8))
        self.estado = tk.Label(self.raiz, text="", bg=FONDO, fg=TEXTO_2, font=(FUENTE, 10), anchor="w", justify="left")
        self.estado.pack(fill="x", padx=16)
        self.linea = tk.Canvas(self.raiz, bg=SUPERFICIE, highlightthickness=0, height=300)
        self.linea.pack(fill="both", expand=True, padx=16, pady=(10, 6))
        self.barras = tk.Canvas(self.raiz, bg=SUPERFICIE, highlightthickness=0, height=260)
        self.barras.pack(fill="both", expand=True, padx=16, pady=(6, 14))
        for c in (self.linea, self.barras):
            c.bind("<Configure>", lambda ev: self.dibujar())
        self.linea.bind("<Motion>", self._sobre_linea)
        self.linea.bind("<Leave>", lambda ev: self.linea.delete("tip"))
        self.barras.bind("<Motion>", self._sobre_barras)
        self.barras.bind("<Leave>", lambda ev: self.barras.delete("tip"))
        self.zonas_linea = None
        self.zonas_barras = []
        self.bombear()

    def _boton(self, padre, texto, orden, principal=False):
        return tk.Button(padre, text=texto, command=orden, relief="flat", bd=0, padx=14, pady=6, cursor="hand2",
                         font=(FUENTE, 10, "bold" if principal else "normal"),
                         bg=SERIE_1 if principal else "#2b2b29", fg="#ffffff" if principal else TEXTO,
                         activebackground="#5598e7" if principal else "#3a3a37", activeforeground="#ffffff")

    def _pedir(self, accion):
        self.accion = accion
        texto = "Abriendo el simulador…" if accion == "simulador" else "Deteniendo…"
        self.estado.configure(text=texto + " se guarda lo aprendido hasta la última generación completa.")

    def salir(self):
        if not self.accion:
            self.accion = "detener"
        self.cerrar()

    def cerrar(self):
        self.vivo = False
        self.grabar.cerrar()
        try:
            self.raiz.destroy()
        except tk.TclError:
            pass

    def bombear(self):
        if not self.vivo:
            return
        try:
            self.raiz.update()
        except tk.TclError:
            self.vivo = False

    def actualizar(self, historial, campeones, estado):
        if not self.vivo:
            return
        self.historial = list(historial)
        self.campeones = dict(campeones)
        self.estado.configure(text=estado)
        self.dibujar()
        self.bombear()

    def terminado(self, texto):
        if not self.vivo:
            return
        self.estado.configure(text=texto)
        self.b_det.configure(text="Cerrar", command=lambda: self._pedir("cerrar"))

    def dibujar(self):
        if not self.vivo:
            return
        self._dibujar_linea()
        self._dibujar_barras()

    def _marco(self, c, titulo, subtitulo):
        c.delete("all")
        w, h = c.winfo_width(), c.winfo_height()
        c.create_text(14 * self.k, 12 * self.k, text=titulo, anchor="nw", fill=TEXTO, font=(FUENTE, 11, "bold"))
        c.create_text(14 * self.k, 34 * self.k, text=subtitulo, anchor="nw", fill=TENUE, font=(FUENTE, 9))
        return w, h

    def _dibujar_linea(self):
        c = self.linea
        w, h = self._marco(c, "Avance por generación", "% de la misión que logra el mejor avión y % de aviones que la superan")
        x0, x1, y0, y1 = 48 * self.k, w - 118 * self.k, 66 * self.k, h - 30 * self.k
        if x1 - x0 < 60 or y1 - y0 < 40:
            return
        self._leyenda(c, w - 16 * self.k, 14 * self.k, [("Mejor avión", SERIE_1), ("Superaron", SERIE_2)])
        datos = self.historial
        n = len(datos)
        if n:
            def px(i):
                return x0 + (x1 - x0) * (i + 0.5) / n
            ancho = (x1 - x0) / n
            ini = 0
            k = 0
            for i in range(1, n + 1):
                if i == n or datos[i]["leccion"] != datos[ini]["leccion"]:
                    xa, xb = x0 + ancho * ini, x0 + ancho * i
                    c.create_rectangle(xa, y0, xb, y1, fill=BANDA[k % 2], width=0)
                    if xb - xa >= 18:
                        c.create_text((xa + xb) / 2, y0 + 4, text=str(datos[ini]["leccion"]), anchor="n", fill=TENUE,
                                      font=(FUENTE, 8))
                    ini = i
                    k += 1
        for v in (0, 25, 50, 75, 100):
            y = y1 - (y1 - y0) * v / 100
            c.create_line(x0, y, x1, y, fill=REJILLA)
            c.create_text(x0 - 6, y, text=f"{v}%", anchor="e", fill=TENUE, font=(FUENTE, 8))
        if not n:
            c.create_text((x0 + x1) / 2, (y0 + y1) / 2, text="Esperando la primera generación…", fill=TENUE,
                          font=(FUENTE, 10))
            self.zonas_linea = None
            return
        primera, ultima = datos[0]["generacion"], datos[-1]["generacion"]
        c.create_text(x0, y1 + 8 * self.k, text=f"gen. {primera}", anchor="nw", fill=TENUE, font=(FUENTE, 8))
        c.create_text(x1, y1 + 8 * self.k, text=f"gen. {ultima}", anchor="ne", fill=TENUE, font=(FUENTE, 8))
        c.create_text((x0 + x1) / 2, y1 + 8 * self.k, text="banda = misión que se entrenaba", anchor="n", fill=TENUE,
                      font=(FUENTE, 8))
        etiquetas = []
        for clave, color in (("superaron_pct", SERIE_2), ("mejor_progreso", SERIE_1)):
            pts = []
            for i, r in enumerate(datos):
                pts += [px(i), y1 - (y1 - y0) * min(max(float(r[clave]), 0), 100) / 100]
            if len(pts) >= 4:
                c.create_line(*pts, fill=color, width=2, capstyle="round", joinstyle="round")
            else:
                c.create_oval(pts[0] - 4, pts[1] - 4, pts[0] + 4, pts[1] + 4, fill=color, outline=SUPERFICIE, width=2)
            etiquetas.append((pts[-1], float(datos[-1][clave]), color, "Superaron" if clave == "superaron_pct" else "Mejor"))
        if abs(etiquetas[0][0] - etiquetas[1][0]) < 26 * self.k:
            medio = (etiquetas[0][0] + etiquetas[1][0]) / 2
            etiquetas = [(medio + 13 * self.k if e[0] >= medio else medio - 13 * self.k, *e[1:]) for e in etiquetas]
            if etiquetas[0][0] == etiquetas[1][0]:
                etiquetas[0] = (etiquetas[0][0] + 26 * self.k, *etiquetas[0][1:])
        for y, v, color, nombre in etiquetas:
            c.create_line(x1 + 4 * self.k, y, x1 + 12 * self.k, y, fill=color, width=2)
            c.create_text(x1 + 16 * self.k, y - 7 * self.k, text=nombre, anchor="w", fill=TEXTO_2, font=(FUENTE, 8))
            c.create_text(x1 + 16 * self.k, y + 7 * self.k, text=f"{v:.1f}%", anchor="w", fill=TEXTO, font=(FUENTE, 9, "bold"))
        self.zonas_linea = (x0, x1, y0, y1, n)

    def _sobre_linea(self, ev):
        c = self.linea
        c.delete("tip")
        if not self.zonas_linea:
            return
        x0, x1, y0, y1, n = self.zonas_linea
        if not (x0 <= ev.x <= x1 and y0 <= ev.y <= y1):
            return
        i = min(n - 1, max(0, int((ev.x - x0) / (x1 - x0) * n)))
        r = self.historial[i]
        x = x0 + (x1 - x0) * (i + 0.5) / n
        c.create_line(x, y0, x, y1, fill=TENUE, dash=(2, 3), tags="tip")
        for clave, color in (("mejor_progreso", SERIE_1), ("superaron_pct", SERIE_2)):
            y = y1 - (y1 - y0) * min(max(float(r[clave]), 0), 100) / 100
            c.create_oval(x - 5, y - 5, x + 5, y + 5, fill=color, outline=SUPERFICIE, width=2, tags="tip")
        lineas = [f"Generación {r['generacion']}", f"Misión {r['leccion']} · {r['nombre']}",
                  f"Mejor avión  {float(r['mejor_progreso']):.1f}%", f"Superaron  {float(r['superaron_pct']):.1f}%",
                  f"Caídos  {float(r['estrellados_pct']):.1f}%"]
        self._tip(c, x, y0 + 10, lineas, x1)

    def _dibujar_barras(self):
        c = self.barras
        w, h = self._marco(c, "Puntaje del campeón por misión", "Mejor puntaje guardado de cada misión")
        self._leyenda(c, w - 16 * self.k, 14 * self.k, [("Superada", BIEN), ("Aún no", PENDIENTE)])
        x0, x1, y0, y1 = 48 * self.k, w - 16 * self.k, 66 * self.k, h - 58 * self.k
        self.zonas_barras = []
        if x1 - x0 < 60 or y1 - y0 < 40:
            return
        valores = [self.campeones.get(k, {}).get("aptitud") for k in self.todas]
        tope = max([v for v in valores if v is not None] + [100.0])
        tope = 50 * (int(tope // 50) + 1)
        for v in range(0, int(tope) + 1, 50 if tope <= 250 else 100):
            y = y1 - (y1 - y0) * v / tope
            c.create_line(x0, y, x1, y, fill=REJILLA)
            c.create_text(x0 - 6, y, text=str(v), anchor="e", fill=TENUE, font=(FUENTE, 8))
        paso = (x1 - x0) / len(self.todas)
        ancho = max(6, min(46, paso - 10))
        total = 0.0
        superadas = 0
        for i, (k, v) in enumerate(zip(self.todas, valores)):
            cx = x0 + paso * (i + 0.5)
            c.create_text(cx, y1 + 8 * self.k, text=str(k), anchor="n", fill=TEXTO_2, font=(FUENTE, 9))
            camp = self.campeones.get(k)
            if camp is None:
                c.create_text(cx, y1 - 8, text="—", fill=TENUE, font=(FUENTE, 9))
                self.zonas_barras.append((cx - paso / 2, cx + paso / 2, k))
                continue
            sup = bool(camp.get("superada")) and bool(camp.get("verificada", True))
            total += v
            superadas += sup
            alto = (y1 - y0) * max(v, 0) / tope
            self._barra(c, cx - ancho / 2, y1 - alto, cx + ancho / 2, y1, BIEN if sup else PENDIENTE)
            if sup:
                c.create_text(cx, y1 - alto - 4, text="✓", anchor="s", fill=TEXTO_2, font=(FUENTE, 9, "bold"))
            self.zonas_barras.append((cx - paso / 2, cx + paso / 2, k))
        c.create_text(x0, h - 14 * self.k, text=f"Superadas {superadas}/{len(self.todas)}  ·  puntaje total {total:.1f}",
                      anchor="w", fill=TEXTO, font=(FUENTE, 10, "bold"))
        c.create_text(x1, h - 14 * self.k, text="pasa el ratón por una barra para ver el detalle", anchor="e", fill=TENUE,
                      font=(FUENTE, 8))
        self.y_barras = (y0, y1)

    def _barra(self, c, xa, ya, xb, yb, color):
        r = min(4, (xb - xa) / 2, max(yb - ya, 0))
        if yb - ya < 1:
            c.create_line(xa, yb, xb, yb, fill=color, width=2)
            return
        c.create_rectangle(xa, ya + r, xb, yb, fill=color, width=0)
        c.create_rectangle(xa + r, ya, xb - r, ya + r, fill=color, width=0)
        c.create_oval(xa, ya, xa + 2 * r, ya + 2 * r, fill=color, width=0)
        c.create_oval(xb - 2 * r, ya, xb, ya + 2 * r, fill=color, width=0)

    def _sobre_barras(self, ev):
        c = self.barras
        c.delete("tip")
        for xa, xb, k in self.zonas_barras:
            if xa <= ev.x <= xb:
                camp = self.campeones.get(k)
                lineas = [f"{k}. {self.nombre(k)}"]
                if camp is None:
                    lineas.append("Sin campeón todavía")
                else:
                    lineas += [f"Puntaje  {camp['aptitud']:.1f}",
                               f"Superada  {'sí' if camp.get('superada') else 'no'} ({100 * camp.get('sup_frac', 0):.0f}% de escenarios)",
                               f"Progreso  {100 * camp.get('progreso', 0):.0f}%",
                               f"Estabilidad  {camp.get('estabilidad', 0):.2f}",
                               f"Logrado en la gen. {camp.get('generacion', '?')}"]
                self._tip(c, (xa + xb) / 2, self.y_barras[0], lineas, c.winfo_width() - 16)
                return

    def _tip(self, c, x, y, lineas, limite):
        fuente = tkfont.Font(family=FUENTE, size=9, weight="bold")
        fila = fuente.metrics("linespace") + 4
        alto = fila * len(lineas) + 12
        ancho = max(fuente.measure(t) for t in lineas) + 22
        xa = x + 12 if x + 12 + ancho <= limite else x - 12 - ancho
        c.create_rectangle(xa, y, xa + ancho, y + alto, fill=TIP, outline=REJILLA, tags="tip")
        for j, t in enumerate(lineas):
            c.create_text(xa + 10, y + 7 + fila * j, text=t, anchor="nw", fill=TEXTO if j == 0 else TEXTO_2,
                          font=(FUENTE, 9, "bold" if j == 0 else "normal"), tags="tip")

    def _leyenda(self, c, x, y, items):
        fuente = tkfont.Font(family=FUENTE, size=9)
        lado = fuente.metrics("linespace") * 0.55
        for texto, color in reversed(items):
            ancho = fuente.measure(texto)
            c.create_text(x, y, text=texto, anchor="ne", fill=TEXTO_2, font=fuente)
            medio = y + fuente.metrics("linespace") / 2
            c.create_rectangle(x - ancho - 6 - lado, medio - lado / 2, x - ancho - 6, medio + lado / 2, fill=color, width=0)
            x -= ancho + lado + 22
