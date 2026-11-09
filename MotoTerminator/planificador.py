import threading
import tkinter as tk
import webbrowser
from tkinter import ttk

import calles as K
import graficos as G

FONDO = "#0a0d12"
TARJETA = "#121821"
BORDE = "#222c3a"
TEXTO = "#e3e8ef"
TENUE = "#7f8a9a"
ORO = "#ffc940"
VERDE = "#3ddc84"
ROJO = "#ff3b30"
AZUL = "#4fb3ff"
CIAN = "#39e5ff"
FUENTE = "Segoe UI"
ANCHO_MAPA, ALTO_MAPA = 820, 660


class Planificador(tk.Toplevel):
    def __init__(self, padre, red_actual, al_aceptar, ruta_actual=None):
        super().__init__(padre, bg=FONDO)
        self.title("Planificar ruta A → B por calles reales")
        self.resizable(True, True)
        self.state("zoomed")
        self.lift()
        self.focus_force()
        self.W, self.H = ANCHO_MAPA, ALTO_MAPA
        self.al_aceptar = al_aceptar
        self.red = None
        self.satelite = None
        self.a = self.b = None
        self.ruta = None
        self._largo = 0.0
        self._info_circuito = {}
        self.vista = None
        self._foto = None
        self._arrastre = None
        self._pendiente = False

        cuerpo = tk.Frame(self, bg=FONDO)
        cuerpo.pack(padx=12, pady=12, fill="both", expand=True)
        self.cv = tk.Canvas(cuerpo, width=self.W, height=self.H, bg="#0c1118",
                            highlightthickness=1, highlightbackground=BORDE, cursor="crosshair")
        lado = tk.Frame(cuerpo, bg=TARJETA, width=340, highlightthickness=1,
                        highlightbackground=BORDE)
        lado.pack(side="right", fill="y", padx=(10, 0))
        self.cv.pack(side="left", fill="both", expand=True)
        self.cv.bind("<Configure>", self._al_redimensionar)
        lado.pack_propagate(False)
        self._lateral(lado)

        self.cv.bind("<ButtonPress-1>", self._presionar)
        self.cv.bind("<B1-Motion>", self._mover)
        self.cv.bind("<ButtonRelease-1>", self._soltar)
        self.cv.bind("<Button-3>", lambda _: self._limpiar())
        self.cv.bind("<MouseWheel>", self._rueda)
        self.cv.bind("<Motion>", self._cursor)
        self.bind("<Escape>", lambda _: self.destroy())

        if ruta_actual and red_actual is not None:
            self._usar_red(red_actual, K.imagen_satelital(red_actual.zona, avisar=lambda _: None))
            vuelta = ruta_actual.get("circuito", "no")
            if vuelta in ("misma", "otra"):
                self.var_circuito.set(True)
                self.var_vuelta.set(vuelta)
            self.a, self.b = ruta_actual["a_xy"], ruta_actual["b_xy"]
            self._calcular()
        elif red_actual is not None:
            self._usar_red(red_actual, K.imagen_satelital(red_actual.zona, avisar=lambda _: None))
        else:
            self._dibujar()
        self.grab_set()

    def _al_redimensionar(self, ev):
        if (ev.width, ev.height) != (self.W, self.H):
            self.W, self.H = ev.width, ev.height
            self._redibujar_pronto()

    def _seccion(self, padre, texto):
        tk.Label(padre, text=texto, bg=TARJETA, fg=ORO, font=(FUENTE, 9, "bold")).pack(
            anchor="w", padx=14, pady=(10, 3))

    def _entrada(self, padre):
        e = tk.Entry(padre, bg="#0c1118", fg=TEXTO, insertbackground=TEXTO, relief="flat",
                     font=(FUENTE, 9), highlightthickness=1, highlightbackground=BORDE,
                     highlightcolor=AZUL)
        e.pack(fill="x", padx=14, ipady=4)
        return e

    def _boton(self, padre, texto, accion, color="#18202b", encima="#24303f", **kw):
        b = tk.Button(padre, text=texto, command=accion, bg=color, fg=TEXTO, bd=0, relief="flat",
                      activebackground=encima, activeforeground="white", cursor="hand2",
                      font=(FUENTE, 9, "bold"), padx=10, pady=6)
        b.bind("<Enter>", lambda _: b.config(bg=encima) if str(b["state"]) == "normal" else None)
        b.bind("<Leave>", lambda _: b.config(bg=color))
        b.pack(**kw)
        return b

    def _lateral(self, f):
        abajo = tk.Frame(f, bg=TARJETA)
        abajo.pack(side="bottom", fill="x", padx=14, pady=12)
        self.b_usar = self._boton(abajo, "✔  Usar esta ruta", self._aceptar, color="#14532d",
                                  encima="#1d6b3b", side="right")
        self._boton(abajo, "Cancelar", self.destroy, side="right", padx=(0, 6))
        self.b_gmaps = self._boton(f, "Comparar en Google Maps ↗", self._google, side="bottom",
                                   fill="x", padx=14)
        tk.Label(f, text="Ruta A → B", bg=TARJETA, fg=TEXTO, font=(FUENTE, 15, "bold")).pack(
            anchor="w", padx=14, pady=(14, 0))
        tk.Label(f, text="La moto seguirá esta ruta por calles reales,\nrespetando el sentido "
                         "de cada calle.", bg=TARJETA, fg=TENUE, justify="left",
                 font=(FUENTE, 8)).pack(anchor="w", padx=14)

        self._seccion(f, "1 · CIUDAD")
        self.var_ciudad = tk.StringVar(value=next(iter(K.ZONAS)))
        ttk.Combobox(f, textvariable=self.var_ciudad, values=list(K.ZONAS),
                     state="readonly").pack(fill="x", padx=14)
        tk.Label(f, text="o las coordenadas del centro (o un enlace de Google Maps):",
                 bg=TARJETA, fg=TENUE, font=(FUENTE, 8), wraplength=300,
                 justify="left").pack(anchor="w", padx=14, pady=(6, 2))
        self.e_ciudad = self._entrada(f)
        self._boton(f, "Cargar mapa", self._cargar_ciudad, fill="x", padx=14, pady=(6, 0))

        self._seccion(f, "2 · SALIDA (A) Y LLEGADA (B)")
        tk.Label(f, text="Haz clic en el mapa (1.º clic = A, 2.º = B), o escribe coordenadas "
                         "en cualquier formato, p. ej. 20° 07′ 18″ N, 98° 44′ 09″ O · "
                         "20.1217, -98.7358 · o un enlace de Google Maps:", bg=TARJETA, fg=TENUE,
                 justify="left", wraplength=300, font=(FUENTE, 8)).pack(anchor="w", padx=14)
        fila = tk.Frame(f, bg=TARJETA)
        fila.pack(fill="x", padx=14, pady=(4, 0))
        tk.Label(fila, text="A", bg=VERDE, fg="#04130a", width=2, font=(FUENTE, 9, "bold")).pack(
            side="left")
        self.e_a = tk.Entry(fila, bg="#0c1118", fg=TEXTO, insertbackground=TEXTO, relief="flat",
                            font=(FUENTE, 9))
        self.e_a.pack(side="left", fill="x", expand=True, ipady=4, padx=(4, 0))
        fila = tk.Frame(f, bg=TARJETA)
        fila.pack(fill="x", padx=14, pady=(4, 0))
        tk.Label(fila, text="B", bg=ROJO, fg="white", width=2, font=(FUENTE, 9, "bold")).pack(
            side="left")
        self.e_b = tk.Entry(fila, bg="#0c1118", fg=TEXTO, insertbackground=TEXTO, relief="flat",
                            font=(FUENTE, 9))
        self.e_b.pack(side="left", fill="x", expand=True, ipady=4, padx=(4, 0))
        self._boton(f, "Trazar con estas coordenadas", self._desde_coordenadas, fill="x",
                    padx=14, pady=(6, 0))

        self._seccion(f, "3 · RUTA")
        self.var_circuito = tk.BooleanVar(value=False)
        self.var_vuelta = tk.StringVar(value="otra")
        opciones = dict(bg=TARJETA, fg=TEXTO, selectcolor="#0c1118", activebackground=TARJETA,
                        activeforeground=TEXTO, font=(FUENTE, 9), anchor="w",
                        command=self._cambio_circuito)
        self.c_circuito = tk.Checkbutton(f, text="Circuito: regresar a A", variable=self.var_circuito,
                                         **opciones)
        self.c_circuito.pack(anchor="w", padx=10)
        fila = tk.Frame(f, bg=TARJETA)
        fila.pack(fill="x", padx=30, pady=(0, 4))
        self.r_vuelta = []
        for valor, texto in (("misma", "por la misma ruta"), ("otra", "por otra ruta")):
            r = tk.Radiobutton(fila, text=texto, value=valor, variable=self.var_vuelta, **opciones)
            r.pack(side="left", padx=(0, 8))
            self.r_vuelta.append(r)
        self.lbl_ruta = tk.Label(f, text="Marca A y B.", bg=TARJETA, fg=TEXTO, justify="left",
                                 wraplength=300, font=(FUENTE, 9), anchor="w")
        self.lbl_ruta.pack(fill="x", padx=14)
        self.lbl_estado = tk.Label(f, text="", bg=TARJETA, fg=AZUL, justify="left",
                                   wraplength=300, font=(FUENTE, 8), anchor="w")
        self.lbl_estado.pack(fill="x", padx=14, pady=(6, 0))

        self._estado_botones()

    def _circuito(self):
        return self.var_vuelta.get() if self.var_circuito.get() else "no"

    def _cambio_circuito(self):
        if self.red is not None and self.a and self.b:
            self._calcular()
        else:
            self._estado_botones()

    def _estado_botones(self):
        for r in getattr(self, "r_vuelta", ()):
            r.config(state="normal" if self.var_circuito.get() else "disabled")
        listo = self.ruta is not None
        self.b_usar.config(state="normal" if listo else "disabled")
        self.b_gmaps.config(state="normal" if listo else "disabled")

    def _avisar(self, texto, color=AZUL):
        self.lbl_estado.config(text=texto, fg=color)

    def _cargar_ciudad(self):
        texto = self.e_ciudad.get().strip()
        if texto:
            c = K.leer_coordenadas(texto)
            if c is None:
                self._avisar("No entendí esas coordenadas.", ROJO)
                return
            zona = K.Zona(f"Zona {c[0]:.4f}, {c[1]:.4f}", c)
        else:
            zona = K.zona_para(self.var_ciudad.get())
        self._cargar(zona)

    def _cargar(self, zona, despues=None):
        estado = {"avisos": [], "ok": None, "error": None}

        def trabajo():
            try:
                red = K.RedVial(zona, avisar=estado["avisos"].append)
                estado["ok"] = (red, K.imagen_satelital(zona, avisar=estado["avisos"].append))
            except Exception as e:
                estado["error"] = str(e)

        def revisar():
            if not self.winfo_exists():
                return
            if estado["avisos"]:
                self._avisar(estado["avisos"][-1])
            if estado["ok"] is None and estado["error"] is None:
                self.after(200, revisar)
                return
            if estado["error"]:
                self._avisar(estado["error"], ROJO)
                return
            self._usar_red(*estado["ok"])
            self._avisar(f"Mapa de {zona.nombre} listo.", VERDE)
            if despues:
                despues()

        self._avisar(f"Cargando {zona.nombre}… (la primera vez descarga calles e imagen)")
        threading.Thread(target=trabajo, daemon=True).start()
        self.after(200, revisar)

    def _usar_red(self, red, satelite):
        self.red, self.satelite = red, satelite
        self._reducida = satelite.reduce(4) if satelite is not None else None
        self.a = self.b = self.ruta = None
        z = red.zona
        self.vista = [z.ancho / 2, z.alto / 2, min(self.W / z.ancho, self.H / z.alto) * 1.6]
        self._estado_botones()
        self.lbl_ruta.config(text="Marca A y B.")
        self._dibujar()

    def _desde_coordenadas(self):
        a, b = K.leer_coordenadas(self.e_a.get()), K.leer_coordenadas(self.e_b.get())
        if a is None or b is None:
            self._avisar("Escribe A y B como «lat, lon» o pega enlaces de Google Maps.", ROJO)
            return

        def trazar():
            z = self.red.zona
            self.a, self.b = z.a_metros(*a), z.a_metros(*b)
            self._calcular()
            self._encuadrar()

        if self.red is not None and self.red.zona.contiene(*a, 200) and self.red.zona.contiene(*b, 200):
            trazar()
        else:
            self._cargar(K.zona_para_puntos(a, b), despues=trazar)

    def _calcular(self):
        self.ruta = None
        self._info_circuito = {}
        vuelta = self._circuito()
        try:
            if vuelta == "no":
                self.ruta = self.red.ruta_entre(self.a, self.b)
            elif not hasattr(self.red, "ruta_circuito"):
                raise RuntimeError("Esta versión de calles.py aún no sabe trazar circuitos.")
            else:
                self.ruta = self.red.ruta_circuito(self.a, self.b, vuelta)
        except RuntimeError as e:
            self.lbl_ruta.config(text=str(e), fg=ROJO)
        else:
            pts, nombres = self.ruta[0], self.ruta[1]
            largo = _largo(pts)
            calles = []
            for n in nombres:
                if not calles or calles[-1] != n:
                    calles.append(n)
            corto = lambda t: t if len(t) <= 34 else t[:33] + "…"
            if vuelta == "no":
                texto = (f"{largo / 1000:.2f} km  ·  {len(calles)} calles  ·  ~{largo / 8 / 60:.0f} min\n"
                         f"Sale por:  {corto(calles[0])}\nLlega por:  {corto(calles[-1])}")
            else:
                extra = (self.ruta[2] if len(self.ruta) > 2 else None) or {}
                x_b = extra.get("x_b")
                ida = extra.get("largo_ida", x_b if x_b is not None else largo / 2)
                regreso = extra.get("largo_vuelta", largo - ida)
                self._info_circuito = {"circuito": vuelta, "largo_ida": ida,
                                       "largo_vuelta": regreso, "vuelta": extra.get("vuelta", ""),
                                       "x_b": x_b}
                texto = (f"Circuito A → B → A  ·  {largo / 1000:.2f} km  ·  ~{largo / 8 / 60:.0f} min\n"
                         f"Ida A → B:  {ida / 1000:.2f} km   ·   vuelta B → A:  {regreso / 1000:.2f} km\n"
                         f"Sale por:  {corto(calles[0])}")
                if extra.get("vuelta"):
                    texto += f"\nRegreso: {extra['vuelta']}"
            self.lbl_ruta.config(text=texto, fg=TEXTO)
            self._largo = largo
            for e, p in ((self.e_a, self.a), (self.e_b, self.b)):
                lat, lon = self.red.zona.a_latlon(*p)
                e.delete(0, "end")
                e.insert(0, f"{lat:.6f}, {lon:.6f}")
        self._estado_botones()
        self._dibujar()

    def _encuadrar(self):
        if self.a and self.b:
            (ax, ay), (bx, by) = self.a, self.b
            self.vista[0], self.vista[1] = (ax + bx) / 2, (ay + by) / 2
            self.vista[2] = min(self.W / (abs(ax - bx) + 300), self.H / (abs(ay - by) + 300), 2.5)
            self._dibujar()

    def _limpiar(self):
        self.a = self.b = self.ruta = None
        self.lbl_ruta.config(text="Marca A y B.", fg=TEXTO)
        self._estado_botones()
        self._dibujar()

    def _google(self):
        if self.ruta is None:
            return
        (la, oa), (lb, ob) = self.red.zona.a_latlon(*self.a), self.red.zona.a_latlon(*self.b)
        webbrowser.open(f"https://www.google.com/maps/dir/?api=1&origin={la:.6f},{oa:.6f}"
                        f"&destination={lb:.6f},{ob:.6f}&travelmode=driving")

    def _aceptar(self):
        if self.ruta is None:
            return
        z = self.red.zona
        info = {"a_xy": self.a, "b_xy": self.b, "a": z.a_latlon(*self.a), "b": z.a_latlon(*self.b),
                "largo": self._largo, "circuito": "no"}
        info.update({k: v for k, v in self._info_circuito.items() if v is not None})
        self.destroy()
        self.al_aceptar(self.red, self.ruta, info)

    def _a_pantalla(self, x, y):
        cx, cy, s = self.vista
        return self.W / 2 + (x - cx) * s, self.H / 2 + (y - cy) * s

    def _a_metros(self, px, py):
        cx, cy, s = self.vista
        return cx + (px - self.W / 2) / s, cy + (py - self.H / 2) / s

    def _presionar(self, ev):
        self._arrastre = (ev.x, ev.y, self.vista[0], self.vista[1], False) if self.vista else None

    def _mover(self, ev):
        if not self._arrastre:
            return
        x0, y0, cx, cy, _ = self._arrastre
        if abs(ev.x - x0) + abs(ev.y - y0) > 4:
            self._arrastre = (x0, y0, cx, cy, True)
            self.vista[0] = cx - (ev.x - x0) / self.vista[2]
            self.vista[1] = cy - (ev.y - y0) / self.vista[2]
            self._redibujar_pronto()

    def _soltar(self, ev):
        if not self._arrastre:
            return
        movido = self._arrastre[4]
        self._arrastre = None
        if movido or self.red is None:
            return
        p = self._a_metros(ev.x, ev.y)
        if self.a is None or self.b is not None:
            self.a, self.b, self.ruta = p, None, None
            self.lbl_ruta.config(text="Ahora marca la llegada (B).", fg=TEXTO)
            self._estado_botones()
            self._dibujar()
        else:
            self.b = p
            self._calcular()

    def _rueda(self, ev):
        if not self.vista:
            return
        f = 1.25 if ev.delta > 0 else 1 / 1.25
        mx, my = self._a_metros(ev.x, ev.y)
        self.vista[2] = min(max(self.vista[2] * f, 0.08), 6.0)
        nx, ny = self._a_metros(ev.x, ev.y)
        self.vista[0] += mx - nx
        self.vista[1] += my - ny
        self._redibujar_pronto()

    def _cursor(self, ev):
        if self.red is None:
            return
        lat, lon = self.red.zona.a_latlon(*self._a_metros(ev.x, ev.y))
        self.cv.delete("cursor")
        self.cv.create_text(self.W - 8, self.H - 8, anchor="se", tags="cursor",
                            text=f"{lat:.5f}, {lon:.5f}", fill="white", font=("Consolas", 9))

    def _redibujar_pronto(self):
        if not self._pendiente:
            self._pendiente = True
            self.after(15, self._dibujar)

    def _dibujar(self):
        self._pendiente = False
        cv = self.cv
        cv.delete("all")
        if self.red is None:
            cv.create_text(self.W / 2, self.H / 2 - 10, fill=TEXTO, font=(FUENTE, 13, "bold"),
                           text="Elige una ciudad y pulsa «Cargar mapa»")
            cv.create_text(self.W / 2, self.H / 2 + 16, fill=TENUE, font=(FUENTE, 9),
                           text="o escribe las coordenadas de A y B directamente")
            return
        z = self.red.zona
        cx, cy, s = self.vista
        if self.satelite is not None:
            from PIL import Image, ImageTk
            fuente, mpp = self.satelite, z.m_por_px
            if s * mpp < 0.6:
                fuente, mpp = self._reducida, mpp * 4
            w, h = self.W / s / mpp, self.H / s / mpp
            caja = (int(cx / mpp - w / 2), int(cy / mpp - h / 2), int(cx / mpp + w / 2), int(cy / mpp + h / 2))
            img = fuente.crop(caja).resize((self.W, self.H), Image.BILINEAR)
            self._foto = ImageTk.PhotoImage(img)
            cv.create_image(0, 0, image=self._foto, anchor="nw")
        x0, y0 = self._a_metros(0, 0)
        x1, y1 = self._a_metros(self.W, self.H)
        if s > 0.35:
            for xs, ys in self.red.lineas:
                if max(xs) < x0 or min(xs) > x1 or max(ys) < y0 or min(ys) > y1:
                    continue
                cv.create_line(*[c for x, y in zip(xs, ys) for c in self._a_pantalla(x, y)],
                               fill="#7fb6ff", width=1)
        if self.ruta:
            ida, regreso = _partir(self.ruta[0], self._info_circuito)
            pts = [c for x, y in ida for c in self._a_pantalla(x, y)]
            cv.create_line(*pts, fill="#000000", width=8, capstyle="round", joinstyle="round",
                           tags="ruta")
            cv.create_line(*pts, fill=ORO, width=4, capstyle="round", joinstyle="round",
                           arrow="last" if regreso else "none", tags=("ruta", "ida"))
            if regreso:
                pts = [c for x, y in regreso for c in self._a_pantalla(x, y)]
                cv.create_line(*pts, fill="#000000", width=5, capstyle="round", joinstyle="round",
                               tags="ruta")
                cv.create_line(*pts, fill=CIAN, width=3, dash=(10, 6), capstyle="round",
                               joinstyle="round", arrow="last", tags=("ruta", "vuelta"))
        for p, letra, col in ((self.a, "A", VERDE), (self.b, "B", ROJO)):
            if p:
                px, py = self._a_pantalla(*p)
                cv.create_polygon(px, py, px - 9, py - 16, px + 9, py - 16, fill=col, outline="#000")
                cv.create_oval(px - 12, py - 36, px + 12, py - 12, fill=col, outline="#000", width=2)
                cv.create_text(px, py - 24, text=letra, fill="black" if letra == "A" else "white",
                               font=(FUENTE, 10, "bold"))
        t = cv.create_text(12, 12, anchor="nw", fill=TEXTO, font=(FUENTE, 9, "bold"), text=z.nombre)
        b = cv.bbox(t)
        G.rect_redondo(cv, b[0] - 7, b[1] - 4, b[2] + 7, b[3] + 4, r=6, fill="#0b0f15", outline=BORDE)
        cv.tag_raise(t)
        if self.ruta and self._info_circuito:
            x0, y0 = 12, b[3] + 14
            G.rect_redondo(cv, x0 - 7, y0 - 4, x0 + 220, y0 + 16, r=6, fill="#0b0f15",
                           outline=BORDE, tags="leyenda")
            cv.create_line(x0, y0 + 6, x0 + 22, y0 + 6, fill=ORO, width=4, tags="leyenda")
            cv.create_text(x0 + 28, y0 + 6, anchor="w", fill=TEXTO, font=(FUENTE, 8, "bold"),
                           text="ida A → B", tags="leyenda")
            cv.create_line(x0 + 108, y0 + 6, x0 + 130, y0 + 6, fill=CIAN, width=3, dash=(6, 4),
                           tags="leyenda")
            cv.create_text(x0 + 136, y0 + 6, anchor="w", fill=TEXTO, font=(FUENTE, 8, "bold"),
                           text="vuelta B → A", tags="leyenda")
        for k, texto in enumerate(("Rueda: zoom  ·  arrastrar: mover  ·  clic derecho: borrar A y B",
                                   K.ATRIBUCION)):
            t = cv.create_text(12, self.H - 10 - 18 * (1 - k), anchor="sw", fill="#d0d6dd",
                               font=(FUENTE, 7), text=texto)
            b = cv.bbox(t)
            cv.create_rectangle(b[0] - 4, b[1] - 1, b[2] + 4, b[3] + 1, fill="#0b0f15", outline="")
            cv.tag_raise(t)


def _largo(pts):
    return sum(((pts[i][0] - pts[i - 1][0]) ** 2 + (pts[i][1] - pts[i - 1][1]) ** 2) ** 0.5
               for i in range(1, len(pts)))


def _partir(pts, info=None):
    if not info:
        return pts, None
    x_b = info.get("x_b")
    if x_b is None:
        x_b = info.get("largo_ida")
    if x_b is None:
        return pts, None
    s = 0.0
    for i in range(1, len(pts)):
        (x0, y0), (x1, y1) = pts[i - 1], pts[i]
        d = ((x1 - x0) ** 2 + (y1 - y0) ** 2) ** 0.5
        if s + d >= x_b:
            f = (x_b - s) / d if d > 0 else 0.0
            p = (x0 + f * (x1 - x0), y0 + f * (y1 - y0))
            ida, vuelta = list(pts[:i]) + [p], [p] + list(pts[i:])
            return ida, (vuelta if len(vuelta) > 1 else None)
        s += d
    return pts, None
