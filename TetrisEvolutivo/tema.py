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


def logo(cv, x, y, s=1.0):
    celdas = ((0, 0, "#b065ff"), (0, 1, "#b065ff"), (0, 2, "#b065ff"), (1, 1, "#b065ff"),
              (1, 0, "#2fd3f5"), (2, 0, "#2fd3f5"), (2, 1, "#ffd23f"), (2, 2, "#ffd23f"), (1, 2, "#ffd23f"))
    lado = 13 * s
    for f, c, color in celdas:
        x0, y0 = x + c * (lado + 2 * s), y + f * (lado + 2 * s)
        cv.create_rectangle(x0, y0, x0 + lado, y0 + lado, fill=color, outline=mezcla(color, "#000000", 0.45))
        cv.create_line(x0 + 2 * s, y0 + 2 * s, x0 + lado - 2 * s, y0 + 2 * s, fill=mezcla(color, "#ffffff", 0.55))


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
