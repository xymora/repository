import base64
import math
import random
import struct
import tkinter as tk
import zlib

PALETA = {
    "fondo": "#0e1014", "tarjeta": "#161920", "tarjeta2": "#1c2029", "borde": "#262b36",
    "rejilla": "#232835", "texto": "#e8ebf1", "tenue": "#8a93a6", "sutil": "#5a6275",
    "acento": "#f5b400", "azul": "#4ea4ff", "verde": "#38d39f", "rojo": "#ff5f5f",
    "morado": "#b48cff", "naranja": "#ffa04d", "gris": "#7d8596", "cian": "#3dd6f5",
}
P = PALETA
FAMILIA = "Segoe UI"
SEMI = "Segoe UI Semibold"
F_TITULO = (SEMI, 17)
F_SECCION = (SEMI, 9)
F_TEXTO = (FAMILIA, 10)
F_CHICA = (FAMILIA, 8)
F_VALOR = (SEMI, 15)
F_BOTON = (SEMI, 10)
F_MONO = ("Consolas", 10)


def rgb(color):
    color = color.lstrip("#")
    return tuple(int(color[i:i + 2], 16) for i in (0, 2, 4))


def hexa(c):
    return "#%02x%02x%02x" % tuple(max(0, min(255, int(round(v)))) for v in c)


def mezclar(a, b, t):
    a = rgb(a) if isinstance(a, str) else a
    b = rgb(b) if isinstance(b, str) else b
    return hexa(tuple(x + (y - x) * t for x, y in zip(a, b)))


def aclarar(c, t):
    return mezclar(c, "#ffffff", t)


def oscurecer(c, t):
    return mezclar(c, "#000000", t)


def _cobertura(d, suave):
    v = 0.5 - d / suave
    return 0.0 if v <= 0 else (1.0 if v >= 1 else v * v * (3 - 2 * v) if suave > 1.5 else v)


class Pintor:

    def __init__(self, ancho, alto, color=(0, 0, 0), transparente=False):
        self.ancho, self.alto = ancho, alto
        self.n = 4 if transparente else 3
        r, g, b = rgb(color) if isinstance(color, str) else color
        self.px = ([r, g, b, 0] if transparente else [r, g, b]) * (ancho * alto)

    def _region(self, x0, y0, x1, y1):
        return (max(0, int(math.floor(x0))), max(0, int(math.floor(y0))),
                min(self.ancho, int(math.ceil(x1)) + 1), min(self.alto, int(math.ceil(y1)) + 1))

    def _mezcla(self, i, r, g, b, a):
        px = self.px
        if self.n == 3:
            if a >= 0.999:
                px[i], px[i + 1], px[i + 2] = r, g, b
            else:
                px[i] += (r - px[i]) * a
                px[i + 1] += (g - px[i + 1]) * a
                px[i + 2] += (b - px[i + 2]) * a
            return
        fondo = px[i + 3] / 255.0
        total = a + fondo * (1 - a)
        if total <= 0:
            return
        k = a / total
        px[i] += (r - px[i]) * k
        px[i + 1] += (g - px[i + 1]) * k
        px[i + 2] += (b - px[i + 2]) * k
        px[i + 3] = total * 255.0

    def _pintar(self, caja, distancia, color, alfa, suave, interior=None):
        r, g, b = rgb(color) if isinstance(color, str) else color
        px, ancho, n, mezcla = self.px, self.ancho, self.n, self._mezcla
        x0, y0, x1, y1 = self._region(*caja)
        ix0 = ix1 = iy0 = iy1 = 0
        if interior:
            ix0, iy0 = max(x0, int(math.ceil(interior[0]))), max(y0, int(math.ceil(interior[1])))
            ix1, iy1 = min(x1, int(interior[2])), min(y1, int(interior[3]))
        lleno = [r, g, b] if n == 3 else [r, g, b, 255]
        for y in range(y0, y1):
            fila = y * ancho
            cy = y + 0.5
            if iy0 <= y < iy1 and ix0 < ix1:
                tramos = ((x0, ix0), (ix1, x1))
                i0, i1 = (fila + ix0) * n, (fila + ix1) * n
                if alfa >= 0.999:
                    px[i0:i1] = lleno * (ix1 - ix0)
                else:
                    for i in range(i0, i1, n):
                        mezcla(i, r, g, b, alfa)
            else:
                tramos = ((x0, x1),)
            for xa, xb in tramos:
                for x in range(xa, xb):
                    a = _cobertura(distancia(x + 0.5, cy), suave)
                    if a > 0:
                        mezcla((fila + x) * n, r, g, b, a * alfa)

    def rect(self, x0, y0, x1, y1, color, radio=0.0, alfa=1.0, suave=1.0):
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        hx, hy = (x1 - x0) / 2 - radio, (y1 - y0) / 2 - radio

        def d(x, y):
            qx, qy = abs(x - cx) - hx, abs(y - cy) - hy
            fuera = math.hypot(max(qx, 0.0), max(qy, 0.0))
            return fuera + min(max(qx, qy), 0.0) - radio

        m, k = suave, radio * 0.3 + suave
        self._pintar((x0 - m, y0 - m, x1 + m, y1 + m), d, color, alfa, suave,
                     (x0 + k, y0 + k, x1 - k, y1 - k))

    def circulo(self, cx, cy, r, color, alfa=1.0, suave=1.0):
        m, k = suave, r * 0.7 - suave
        self._pintar((cx - r - m, cy - r - m, cx + r + m, cy + r + m),
                     lambda x, y: math.hypot(x - cx, y - cy) - r, color, alfa, suave,
                     (cx - k, cy - k, cx + k, cy + k) if k > 2 else None)

    def linea(self, xa, ya, xb, yb, grosor, color, alfa=1.0, suave=1.0):
        dx, dy = xb - xa, yb - ya
        largo2 = dx * dx + dy * dy or 1e-9
        r = grosor / 2

        def d(x, y):
            t = max(0.0, min(1.0, ((x - xa) * dx + (y - ya) * dy) / largo2))
            return math.hypot(x - xa - t * dx, y - ya - t * dy) - r

        m = r + suave
        self._pintar((min(xa, xb) - m, min(ya, yb) - m, max(xa, xb) + m, max(ya, yb) + m),
                     d, color, alfa, suave)

    def poligono(self, puntos, color, alfa=1.0, suave=1.0):
        aristas = []
        n = len(puntos)
        for i in range(n):
            (xa, ya), (xb, yb) = puntos[i], puntos[(i + 1) % n]
            nx, ny = yb - ya, xa - xb
            l = math.hypot(nx, ny) or 1e-9
            aristas.append((nx / l, ny / l, xa, ya))
        if sum((puntos[(i + 1) % n][0] - puntos[i][0]) * (puntos[(i + 1) % n][1] + puntos[i][1])
               for i in range(n)) < 0:
            aristas = [(-nx, -ny, xa, ya) for nx, ny, xa, ya in aristas]

        def d(x, y):
            return max(nx * (x - xa) + ny * (y - ya) for nx, ny, xa, ya in aristas)

        xs, ys = [p[0] for p in puntos], [p[1] for p in puntos]
        m = suave
        self._pintar((min(xs) - m, min(ys) - m, max(xs) + m, max(ys) + m), d, color, alfa, suave)

    def textura(self, x0, y0, x1, y1, base, variacion, grano=1.0, escala=24, semilla=0,
                manchas=0.0):
        al = random.Random(semilla)
        br, bg, bb = rgb(base) if isinstance(base, str) else base
        x0, y0, x1, y1 = self._region(x0, y0, x1 - 1, y1 - 1)
        cols = (x1 - x0) // escala + 2
        filas = (y1 - y0) // escala + 2
        malla = [[al.uniform(-1, 1) for _ in range(cols + 1)] for _ in range(filas + 1)]
        px, ancho = self.px, self.ancho
        rnd = al.random
        for y in range(y0, y1):
            fy = (y - y0) / escala
            j = int(fy)
            ty = fy - j
            ty = ty * ty * (3 - 2 * ty)
            fa, fb = malla[j], malla[j + 1]
            fila = y * ancho
            for x in range(x0, x1):
                fx = (x - x0) / escala
                i = int(fx)
                tx = fx - i
                tx = tx * tx * (3 - 2 * tx)
                arriba = fa[i] + (fa[i + 1] - fa[i]) * tx
                abajo = fb[i] + (fb[i + 1] - fb[i]) * tx
                v = (arriba + (abajo - arriba) * ty) * variacion * manchas \
                    + (rnd() - 0.5) * variacion * grano
                k = (fila + x) * 3
                px[k] = 0 if br + v < 0 else (255 if br + v > 255 else br + v)
                px[k + 1] = 0 if bg + v < 0 else (255 if bg + v > 255 else bg + v)
                px[k + 2] = 0 if bb + v < 0 else (255 if bb + v > 255 else bb + v)

    def foto(self):
        if self.n == 3:
            datos = bytes(map(int, self.px))
            return tk.PhotoImage(data=f"P6 {self.ancho} {self.alto} 255\n".encode() + datos)
        fila = self.ancho * 4
        crudo = bytes(map(int, self.px))
        filas = b"".join(b"\x00" + crudo[y * fila:(y + 1) * fila] for y in range(self.alto))

        def bloque(tipo, datos):
            return (struct.pack(">I", len(datos)) + tipo + datos
                    + struct.pack(">I", zlib.crc32(tipo + datos) & 0xFFFFFFFF))

        png = (b"\x89PNG\r\n\x1a\n"
               + bloque(b"IHDR", struct.pack(">IIBBBBB", self.ancho, self.alto, 8, 6, 0, 0, 0))
               + bloque(b"IDAT", zlib.compress(filas, 3)) + bloque(b"IEND", b""))
        return tk.PhotoImage(data=base64.b64encode(png))


def tarjeta(padre, titulo=None, derecha=None, **kw):
    marco = tk.Frame(padre, bg=P["tarjeta"], highlightthickness=1,
                     highlightbackground=P["borde"], **kw)
    if titulo:
        cab = tk.Frame(marco, bg=P["tarjeta"])
        cab.pack(fill="x", padx=12, pady=(9, 0))
        tk.Label(cab, text=titulo.upper(), bg=P["tarjeta"], fg=P["tenue"],
                 font=F_SECCION).pack(side="left")
        if derecha is not None:
            derecha(cab).pack(side="right")
    cuerpo = tk.Frame(marco, bg=P["tarjeta"])
    cuerpo.pack(fill="both", expand=True, padx=12, pady=(6, 10))
    return marco, cuerpo


class Boton:

    def __init__(self, padre, texto, comando, color=None, ancho=None, primario=False):
        self.color = color or P["tarjeta2"]
        self.comando = comando
        self.activo = True
        fg = "#0e1014" if primario else P["texto"]
        self.w = tk.Label(padre, text=texto, bg=self.color, fg=fg, font=F_BOTON,
                          padx=12, pady=6, cursor="hand2", width=ancho)
        self.w.bind("<Enter>", lambda e: self._pintar(True))
        self.w.bind("<Leave>", lambda e: self._pintar(False))
        self.w.bind("<Button-1>", lambda e: self.activo and self.comando())

    def _pintar(self, encima):
        self.w.configure(bg=aclarar(self.color, 0.12) if encima and self.activo else self.color)

    def texto(self, t):
        self.w.configure(text=t)

    def pack(self, **kw):
        self.w.pack(**kw)
        return self

    def grid(self, **kw):
        self.w.grid(**kw)
        return self


class Segmentado:

    def __init__(self, padre, opciones, valor, al_cambiar):
        self.marco = tk.Frame(padre, bg=P["borde"], padx=2, pady=2)
        self.valor = valor
        self.al_cambiar = al_cambiar
        self.etiquetas = {}
        for v, texto in opciones:
            l = tk.Label(self.marco, text=texto, font=F_BOTON, padx=12, pady=4, cursor="hand2")
            l.pack(side="left", padx=(0 if not self.etiquetas else 2, 0))
            l.bind("<Button-1>", lambda e, v=v: self.al_cambiar(v))
            self.etiquetas[v] = l
        self.poner(valor)

    def poner(self, valor):
        self.valor = valor
        for v, l in self.etiquetas.items():
            sel = v == valor
            l.configure(bg=P["acento"] if sel else P["tarjeta2"],
                        fg="#0e1014" if sel else P["tenue"])

    def pack(self, **kw):
        self.marco.pack(**kw)
        return self


def estilo_boton_grabar(boton_grabar):
    b = boton_grabar.boton
    b.configure(font=F_BOTON, padx=12, pady=6, relief="flat", bd=0,
                highlightthickness=0, disabledforeground=P["sutil"])

    def _estilo(grabando, texto=None):
        color = "#d93636" if grabando else P["tarjeta2"]
        b.configure(text=texto or ("⏹ Stop" if grabando else "⏺ Grabar"), bg=color,
                    activebackground=aclarar(color, 0.12),
                    fg="#ffffff" if grabando else "#ff6b6b",
                    activeforeground="#ffffff" if grabando else "#ff8a8a")

    boton_grabar._estilo = _estilo
    _estilo(False)
    return boton_grabar


def indicadores(cv, datos, columnas, ancho, alto_celda=50):
    cv.delete("all")
    sep = 6
    w = (ancho - sep * (columnas - 1)) / columnas
    for k, (etq, valor, color, frac) in enumerate(datos):
        c, f = k % columnas, k // columnas
        x, y = c * (w + sep), f * (alto_celda + sep)
        cv.create_rectangle(x, y, x + w, y + alto_celda, fill=P["tarjeta2"], outline="")
        cv.create_rectangle(x, y, x + 3, y + alto_celda, fill=color, outline="")
        cv.create_text(x + 12, y + 11, text=etq.upper(), anchor="w", fill=P["tenue"],
                       font=(SEMI, 7))
        cv.create_text(x + 12, y + alto_celda - 18, text=valor, anchor="w", fill=P["texto"],
                       font=F_VALOR)
        if frac is not None:
            yb = y + alto_celda - 6
            cv.create_rectangle(x + 12, yb, x + w - 10, yb + 2, fill=P["rejilla"], outline="")
            cv.create_rectangle(x + 12, yb, x + 12 + (w - 22) * max(0.0, min(1.0, frac)), yb + 2,
                                fill=color, outline="")


def _paso_eje(rango, divisiones=4):
    bruto = rango / divisiones
    mag = 10 ** math.floor(math.log10(bruto)) if bruto > 0 else 1
    for m in (1, 2, 2.5, 5, 10):
        if bruto <= m * mag:
            return m * mag
    return 10 * mag


def grafica(cv, hist, meta=None, etiqueta_meta=""):
    cv.delete("all")
    w, h = int(cv["width"]), int(cv["height"])
    izq, der, arr, aba = 40, 10, 10, 22
    if len(hist) < 2:
        cv.create_text(w / 2, h / 2, text="La gráfica aparece al terminar\nla primera generación",
                       fill=P["sutil"], font=F_TEXTO, justify="center")
        return
    tope = max(s["mejor"] for s in hist)
    piso = min(0.0, min(s["promedio"] for s in hist))
    paso = _paso_eje((tope - piso) or 1, max(2, (h - arr - aba) // 26))
    piso = math.floor(piso / paso) * paso
    tope = math.ceil(tope / paso) * paso
    if tope <= piso:
        tope = piso + paso
    ancho, alto = w - izq - der, h - arr - aba
    n = len(hist)

    def X(i):
        return izq + i * ancho / (n - 1)

    def Y(v):
        return arr + alto - (v - piso) / (tope - piso) * alto

    v = piso
    while v <= tope + 1e-9:
        y = Y(v)
        cv.create_line(izq, y, w - der, y, fill=P["rejilla"])
        cv.create_text(izq - 6, y, text=f"{v:,.0f}".replace(",", " "), anchor="e",
                       fill=P["sutil"], font=F_CHICA)
        v += paso
    for s_i in range(n):
        if hist[s_i].get("extincion"):
            cv.create_line(X(s_i), arr, X(s_i), arr + alto, fill=mezclar(P["naranja"],
                           P["tarjeta"], 0.45), dash=(2, 3))
    mejor = [(X(i), Y(s["mejor"])) for i, s in enumerate(hist)]
    area = [(izq, arr + alto)] + mejor + [(w - der, arr + alto)]
    cv.create_polygon(*[c for p in area for c in p],
                      fill=mezclar(P["acento"], P["tarjeta"], 0.9), outline="")
    if meta is not None and piso < meta < tope:
        y = Y(meta)
        cv.create_line(izq, y, w - der, y, fill=mezclar(P["verde"], P["tarjeta"], 0.3), dash=(5, 4))
        cv.create_text(w - der - 2, y - 7, text=etiqueta_meta, anchor="e", fill=P["verde"],
                       font=F_CHICA)
    prom = [c for i, s in enumerate(hist) for c in (X(i), Y(s["promedio"]))]
    cv.create_line(*prom, fill=P["azul"], width=2, smooth=n > 3)
    cv.create_line(*[c for p in mejor for c in p], fill=P["acento"], width=2)
    xu, yu = mejor[-1]
    cv.create_oval(xu - 3, yu - 3, xu + 3, yu + 3, fill=P["acento"], outline=P["tarjeta"])
    cv.create_text(izq, h - 6, text=f"gen {hist[0]['generacion']}", anchor="sw",
                   fill=P["sutil"], font=F_CHICA)
    cv.create_text(w - der, h - 6, text=f"gen {hist[-1]['generacion']}", anchor="se",
                   fill=P["sutil"], font=F_CHICA)


def arco(cv, cx, cy, r, desde, hasta, color, grosor):
    if abs(hasta - desde) < 0.5:
        return
    cv.create_arc(cx - r, cy - r, cx + r, cy + r, start=desde, extent=hasta - desde,
                  style="arc", outline=color, width=grosor)


def velocimetro(cv, cx, cy, r, valor, maximo, texto, unidad, color):
    ini, total = 210, -240
    arco(cv, cx, cy, r, ini, ini + total, P["rejilla"], 6)
    frac = max(0.0, min(1.0, valor / maximo)) if maximo else 0
    arco(cv, cx, cy, r, ini, ini + total * frac, color, 6)
    for k in range(int(maximo) + 1):
        a = math.radians(ini + total * k / maximo)
        x0, y0 = cx + (r - 10) * math.cos(a), cy - (r - 10) * math.sin(a)
        x1, y1 = cx + (r - 15) * math.cos(a), cy - (r - 15) * math.sin(a)
        cv.create_line(x0, y0, x1, y1, fill=P["sutil"], width=1)
    a = math.radians(ini + total * frac)
    cv.create_line(cx, cy, cx + (r - 8) * math.cos(a), cy - (r - 8) * math.sin(a),
                   fill=P["texto"], width=2)
    cv.create_oval(cx - 4, cy - 4, cx + 4, cy + 4, fill=P["texto"], outline="")
    cv.create_text(cx, cy + r * 0.42, text=texto, fill=P["texto"], font=(SEMI, 14))
    cv.create_text(cx, cy + r * 0.42 + 16, text=unidad, fill=P["tenue"], font=F_CHICA)


def volante(cv, cx, cy, r, angulo, color):
    cv.create_oval(cx - r, cy - r, cx + r, cy + r, outline=P["sutil"], width=5)
    cv.create_oval(cx - r * 0.28, cy - r * 0.28, cx + r * 0.28, cy + r * 0.28,
                   fill=P["tarjeta2"], outline=P["sutil"], width=2)
    for base in (math.pi, 0.0, math.pi / 2):
        a = base + angulo
        cv.create_line(cx + r * 0.28 * math.cos(a), cy + r * 0.28 * math.sin(a),
                       cx + (r - 2) * math.cos(a), cy + (r - 2) * math.sin(a),
                       fill=P["sutil"], width=4)
    a = -math.pi / 2 + angulo
    cv.create_line(cx + (r - 6) * math.cos(a), cy + (r - 6) * math.sin(a),
                   cx + (r + 3) * math.cos(a), cy + (r + 3) * math.sin(a), fill=color, width=5)


def pedal(cv, x, y, ancho, alto, valor, color, etiqueta):
    cv.create_rectangle(x, y, x + ancho, y + alto, fill=P["rejilla"], outline="")
    lleno = alto * max(0.0, min(1.0, valor))
    if lleno > 0.5:
        cv.create_rectangle(x, y + alto - lleno, x + ancho, y + alto, fill=color, outline="")
    cv.create_text(x + ancho / 2, y + alto + 11, text=etiqueta, fill=P["tenue"], font=(SEMI, 7))
    cv.create_text(x + ancho / 2, y - 9, text=f"{valor * 100:.0f}%", fill=P["texto"],
                   font=F_CHICA)


def palanca(cv, x, y, marcha):
    for i, (letra, valor) in enumerate((("D", 1), ("R", -1))):
        activa = marcha == valor
        yy = y + i * 30
        color = P["verde"] if valor == 1 else P["naranja"]
        cv.create_rectangle(x, yy, x + 26, yy + 24, fill=color if activa else P["tarjeta2"],
                            outline="" if activa else P["borde"])
        cv.create_text(x + 13, yy + 12, text=letra, font=(SEMI, 11),
                       fill="#0e1014" if activa else P["sutil"])


def dial_angulo(cv, cx, cy, r, angulo, limite, alerta, etiqueta):
    arco(cv, cx, cy, r, 180, 0, P["rejilla"], 5)
    zona = math.degrees(alerta) / math.degrees(limite) * 90
    arco(cv, cx, cy, r, 180, 180 - (90 - zona), mezclar(P["rojo"], P["tarjeta"], 0.45), 5)
    arco(cv, cx, cy, r, 0, 90 - zona, mezclar(P["rojo"], P["tarjeta"], 0.45), 5)
    frac = max(-1.0, min(1.0, angulo / limite))
    peligro = abs(angulo) > alerta
    color = P["rojo"] if peligro else P["naranja"]
    arco(cv, cx, cy, r, 90, 90 - 90 * frac, color, 5)
    a = math.radians(90 - 90 * frac)
    cv.create_line(cx, cy, cx + (r - 5) * math.cos(a), cy - (r - 5) * math.sin(a),
                   fill=P["texto"], width=2)
    cv.create_oval(cx - 3, cy - 3, cx + 3, cy + 3, fill=P["texto"], outline="")
    cv.create_text(cx, cy + 10, text=f"{abs(math.degrees(angulo)):.0f}°", fill=color,
                   font=(SEMI, 10))
    cv.create_text(cx, cy + 23, text=etiqueta, fill=P["tenue"], font=(SEMI, 7))


def ficha(cv, x, y, texto, color, relleno=True):
    w = 8 + 7 * len(texto)
    cv.create_rectangle(x, y, x + w, y + 16, fill=color if relleno else "",
                        outline="" if relleno else color)
    cv.create_text(x + w / 2, y + 8, text=texto, font=(SEMI, 8),
                   fill="#0e1014" if relleno else color)
    return w


class Menu:

    def __init__(self, padre, var, opciones, al_cambiar, ancho=20):
        self.var = var
        self.al_cambiar = al_cambiar
        self.ancho = ancho
        self.w = tk.Menubutton(padre, bg=P["tarjeta2"], fg=P["texto"],
                               activebackground=aclarar(P["tarjeta2"], 0.08),
                               activeforeground=P["texto"], font=F_TEXTO, relief="flat", bd=0,
                               highlightthickness=1, highlightbackground=P["borde"],
                               indicatoron=False, anchor="w", padx=10, pady=3, cursor="hand2",
                               width=ancho + 2, takefocus=0)
        self.menu = tk.Menu(self.w, tearoff=0, bg=P["tarjeta2"], fg=P["texto"],
                            activebackground=P["acento"], activeforeground="#0e1014",
                            font=F_TEXTO, bd=0, relief="flat")
        self.w["menu"] = self.menu
        self.opciones(opciones)
        self.flecha = tk.Label(self.w, text="▾", bg=P["tarjeta2"], fg=P["tenue"], font=F_TEXTO)
        self.flecha.place(relx=1.0, rely=0.5, x=-6, anchor="e")
        self.flecha.bind("<Button-1>", lambda e: self.w.event_generate("<Button-1>"))
        var.trace_add("write", lambda *a: self._mostrar())
        self._mostrar()

    def _mostrar(self):
        t = str(self.var.get())
        self.w.configure(text=t if len(t) <= self.ancho else t[:self.ancho - 1].rstrip() + "…")

    def opciones(self, opciones):
        self.menu.delete(0, "end")
        for o in opciones:
            self.menu.add_command(label=o, command=lambda o=o: self._elegir(o))

    def _elegir(self, o):
        self.var.set(o)
        self.al_cambiar()

    def pack(self, **kw):
        self.w.pack(**kw)
        return self

    def grid(self, **kw):
        self.w.grid(**kw)
        return self


class Interruptor:

    def __init__(self, padre, texto, var, al_cambiar=None, fondo=None):
        self.var = var
        self.al_cambiar = al_cambiar
        bg = fondo or P["tarjeta"]
        self.marco = tk.Frame(padre, bg=bg, cursor="hand2")
        self.cv = tk.Canvas(self.marco, width=30, height=16, bg=bg, highlightthickness=0)
        self.cv.pack(side="left")
        self.lbl = tk.Label(self.marco, text=texto, bg=bg, fg=P["texto"], font=F_TEXTO)
        self.lbl.pack(side="left", padx=(6, 0))
        for w in (self.marco, self.cv, self.lbl):
            w.bind("<Button-1>", self._clic)
        var.trace_add("write", lambda *a: self._pintar())
        self._pintar()

    def _clic(self, _):
        self.var.set(not self.var.get())
        if self.al_cambiar:
            self.al_cambiar()

    def _pintar(self):
        cv, on = self.cv, bool(self.var.get())
        cv.delete("all")
        col = P["acento"] if on else P["borde"]
        cv.create_oval(1, 1, 15, 15, fill=col, outline=col)
        cv.create_oval(15, 1, 29, 15, fill=col, outline=col)
        cv.create_rectangle(8, 1, 22, 15, fill=col, outline=col)
        x = 22 if on else 8
        cv.create_oval(x - 5, 3, x + 5, 13, fill="#0e1014" if on else P["tenue"], outline="")
        self.lbl.configure(fg=P["texto"] if on else P["tenue"])

    def pack(self, **kw):
        self.marco.pack(**kw)
        return self

    def grid(self, **kw):
        self.marco.grid(**kw)
        return self


class Deslizador:

    def __init__(self, padre, var, desde, hasta, paso, al_cambiar, ancho=200, formato="{:.1f}",
                 unidad=""):
        self.var, self.desde, self.hasta, self.paso = var, desde, hasta, paso
        self.al_cambiar, self.formato, self.unidad = al_cambiar, formato, unidad
        self.ancho = ancho
        self.cv = tk.Canvas(padre, width=ancho, height=26, bg=P["tarjeta"], highlightthickness=0,
                            cursor="hand2")
        self.cv.bind("<Button-1>", self._mover)
        self.cv.bind("<B1-Motion>", self._mover)
        self._pintar()

    def _x(self, v):
        return 8 + (self.ancho - 70) * (v - self.desde) / (self.hasta - self.desde)

    def _mover(self, ev):
        f = (ev.x - 8) / (self.ancho - 70)
        v = self.desde + max(0.0, min(1.0, f)) * (self.hasta - self.desde)
        v = round(v / self.paso) * self.paso
        if v != self.var.get():
            self.var.set(v)
            self._pintar()
            self.al_cambiar()

    def _pintar(self):
        cv = self.cv
        cv.delete("all")
        y, x = 13, self._x(self.var.get())
        cv.create_line(8, y, self.ancho - 62, y, fill=P["borde"], width=4, capstyle="round")
        cv.create_line(8, y, x, y, fill=P["acento"], width=4, capstyle="round")
        cv.create_oval(x - 7, y - 7, x + 7, y + 7, fill=P["texto"], outline=P["acento"], width=2)
        cv.create_text(self.ancho - 2, y, anchor="e", fill=P["texto"], font=(SEMI, 10),
                       text=self.formato.format(self.var.get()) + self.unidad)

    def pack(self, **kw):
        self.cv.pack(**kw)
        return self


def etiqueta(padre, texto, color=None, fuente=None, fondo=None, **kw):
    return tk.Label(padre, text=texto, fg=color or P["tenue"], bg=fondo or P["tarjeta"],
                    font=fuente or F_CHICA, **kw)


def chip(cv, x, y, texto, color, ancla="nw", fuente=None, fondo=None, tags=()):
    fuente = fuente or (SEMI, 9)
    t = cv.create_text(x, y, text=texto, fill=color, font=fuente, anchor=ancla, tags=tags)
    x0, y0, x1, y1 = cv.bbox(t)
    r = cv.create_rectangle(x0 - 7, y0 - 3, x1 + 7, y1 + 3, fill=fondo or "#0e1014",
                            outline=mezclar(color, "#0e1014", 0.35), tags=tags)
    cv.tag_lower(r, t)
    dx = {"nw": 7, "w": 7, "sw": 7, "ne": -7, "e": -7, "se": -7}.get(ancla, 0)
    dy = {"nw": 3, "n": 3, "ne": 3, "sw": -3, "s": -3, "se": -3}.get(ancla, 0)
    try:
        ancho = int(cv["width"])
    except (tk.TclError, ValueError):
        ancho = 0
    if ancho:
        dx += max(0, 2 - (x0 - 7 + dx)) - max(0, x1 + 7 + dx - (ancho - 2))
    cv.move(t, dx, dy)
    cv.move(r, dx, dy)
    return x1 - x0 + 14


def barra(cv, x, y, ancho, alto, frac, color, fondo=None):
    cv.create_rectangle(x, y, x + ancho, y + alto, fill=fondo or P["rejilla"], outline="")
    if frac > 0:
        cv.create_rectangle(x, y, x + ancho * max(0.0, min(1.0, frac)), y + alto, fill=color,
                            outline="")
