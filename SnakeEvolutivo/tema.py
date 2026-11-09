import math
import tkinter as tk

import numpy as np

FONDO = "#0e1014"
TARJETA = "#161920"
TARJETA2 = "#1c2029"
BORDE = "#262b36"
REJILLA = "#232835"
TEXTO = "#e8ebf1"
TENUE = "#8a93a6"
SUTIL = "#5a6275"
ORO = "#f5b400"
AZUL = "#4ea4ff"
VERDE = "#38d39f"
ROJO = "#ff5f5f"
NARANJA = "#ffa04d"
MORADO = "#b48cff"
GRIS = "#7d8596"
FAMILIA = "Segoe UI"
SEMI = "Segoe UI Semibold"
MONO = "Consolas"


def rgb(color):
    return tuple(int(color[i:i + 2], 16) for i in (1, 3, 5))


def mezcla(c1, c2, t):
    t = min(max(float(t), 0.0), 1.0)
    a, b = rgb(c1), rgb(c2)
    return "#%02x%02x%02x" % tuple(round(x + (y - x) * t) for x, y in zip(a, b))


def foto(arreglo):
    a = np.clip(arreglo, 0, 255).astype(np.uint8)
    alto, ancho = a.shape[:2]
    return tk.PhotoImage(data=f"P6 {ancho} {alto} 255\n".encode() + a.tobytes())


def _difuminar(m, r):
    if r < 1:
        return m
    k = 2 * r + 1
    p = np.pad(m, r, mode="edge")
    c = np.cumsum(np.cumsum(p, 0), 1)
    c = np.pad(c, ((1, 0), (1, 0)))
    return (c[k:, k:] - c[:-k, k:] - c[k:, :-k] + c[:-k, :-k]) / (k * k)


def tablero(muros, lado, celda, ox, oy, semilla=7):
    al = np.random.default_rng(semilla)
    filas, cols = muros.shape
    img = np.zeros((lado, lado, 3), np.float32)
    img[:] = rgb("#090b0f")
    yy, xx = np.mgrid[0:lado, 0:lado]
    f = np.clip((yy - oy) // celda, 0, filas - 1)
    c = np.clip((xx - ox) // celda, 0, cols - 1)
    dentro = (yy >= oy) & (yy < oy + filas * celda) & (xx >= ox) & (xx < ox + cols * celda)
    es_muro = muros[f, c] & dentro
    piso = dentro & ~es_muro
    ux = ((xx - ox) % celda) / celda
    uy = ((yy - oy) % celda) / celda
    a, b = np.array(rgb("#141a23"), np.float32), np.array(rgb("#18202b"), np.float32)
    tono = np.where(((f + c) % 2 == 0)[..., None], a, b)
    luz = (1 - 0.5 * (ux + uy)) * 6
    bisel = np.minimum(np.minimum(ux, 1 - ux), np.minimum(uy, 1 - uy))
    junta = np.clip(1 - bisel * celda / 1.2, 0, 1) * 7
    grano = al.normal(0, 2.2, (lado, lado))
    capa = tono + (luz - junta + grano)[..., None]
    img[piso] = capa[piso]
    mm = np.zeros((lado, lado), np.float32)
    mm[es_muro] = 1
    sombra = _difuminar(np.roll(np.roll(mm, celda // 6, 0), celda // 8, 1), max(2, celda // 4))
    ao = _difuminar(mm, max(2, celda // 3))
    oscuro = np.clip(sombra * 0.55 + ao * 0.35, 0, 0.7)
    img[piso] *= (1 - oscuro[piso])[..., None]
    base = np.array(rgb("#2b3b57"), np.float32)
    borde = max(2, celda // 9)
    arriba = mm.copy()
    arriba[borde:] = mm[borde:] * (1 - mm[:-borde])
    arriba[:borde] = mm[:borde]
    izq = mm.copy()
    izq[:, borde:] = mm[:, borde:] * (1 - mm[:, :-borde])
    abajo = mm.copy()
    abajo[:-borde] = mm[:-borde] * (1 - mm[borde:])
    der = mm.copy()
    der[:, :-borde] = mm[:, :-borde] * (1 - mm[:, borde:])
    ladrillo = ((uy * 2) % 1 < 0.08) | (((ux + 0.5 * ((uy * 2) // 1)) * 2) % 1 < 0.05)
    m = es_muro
    tono_muro = base + (al.normal(0, 3, (lado, lado)) - ladrillo * 10)[..., None] \
        + ((1 - uy) * 10)[..., None]
    tono_muro = tono_muro + (np.maximum(arriba, izq) * 34)[..., None] \
        - (np.maximum(abajo, der) * 26)[..., None]
    img[m] = tono_muro[m]
    cx, cy = lado / 2, lado / 2
    d = np.hypot(xx - cx, yy - cy) / (lado * 0.72)
    img *= (1 - np.clip(d, 0, 1) ** 2.4 * 0.5)[..., None]
    return foto(img)


def logo(cv, x, y, s=1.0):
    pts = []
    for k in range(9):
        t = k / 8
        pts += [x + t * 44 * s, y + 18 * s + math.sin(t * math.pi * 2) * 8 * s]
    cv.create_line(*pts, fill="#0d3b25", width=13 * s, capstyle="round", smooth=True)
    cv.create_line(*pts, fill=VERDE, width=9 * s, capstyle="round", smooth=True)
    hx, hy = pts[-2], pts[-1]
    cv.create_oval(hx - 6 * s, hy - 6 * s, hx + 6 * s, hy + 6 * s, fill="#9dffc8", outline="")
    cv.create_oval(hx + 1 * s, hy - 3 * s, hx + 4 * s, hy, fill="#0e1014", outline="")


class Boton:
    def __init__(self, padre, texto, comando, color=None, primario=False, ancho=None):
        self.color = color or TARJETA2
        self.comando = comando
        self.activo = True
        self.w = tk.Label(padre, text=texto, bg=self.color, fg=FONDO if primario else TEXTO,
                          font=(SEMI, 10), padx=12, pady=6, cursor="hand2", width=ancho)
        self.w.bind("<Enter>", lambda e: self._pintar(True))
        self.w.bind("<Leave>", lambda e: self._pintar(False))
        self.w.bind("<Button-1>", lambda e: self.activo and self.comando())

    def _pintar(self, encima):
        self.w.configure(bg=mezcla(self.color, "#ffffff", 0.12) if encima and self.activo
                         else self.color)

    def texto(self, t):
        if self.w.cget("text") != t:
            self.w.configure(text=t)

    def habilitar(self, si):
        self.activo = si
        self.w.configure(fg=(FONDO if self.color != TARJETA2 else TEXTO) if si else SUTIL,
                         cursor="hand2" if si else "arrow")

    def pack(self, **kw):
        self.w.pack(**kw)
        return self


def estilo_grabar(boton_grabar):
    b = boton_grabar.boton
    b.configure(font=(SEMI, 10), padx=12, pady=6, relief="flat", bd=0, highlightthickness=0,
                disabledforeground=SUTIL)

    def _estilo(grabando, texto=None):
        color = "#d93636" if grabando else TARJETA2
        b.configure(text=texto or ("⏹ Stop" if grabando else "⏺ Grabar"), bg=color,
                    activebackground=mezcla(color, "#ffffff", 0.12),
                    fg="#ffffff" if grabando else "#ff6b6b",
                    activeforeground="#ffffff" if grabando else "#ff8a8a")

    boton_grabar._estilo = _estilo
    _estilo(False)
    return boton_grabar


def paso_eje(rango, divisiones=4):
    bruto = rango / divisiones
    mag = 10 ** math.floor(math.log10(bruto)) if bruto > 0 else 1
    for m in (1, 2, 2.5, 5, 10):
        if bruto <= m * mag:
            return m * mag
    return 10 * mag
