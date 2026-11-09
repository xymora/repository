import functools
import math

import numpy as np

import config as C
from terreno import COLORES, NOMBRES_MAT


def hex_rgb(c):
    return tuple(int(c[i:i + 2], 16) for i in (1, 3, 5))


def mezclar(a, b, t):
    return _mezclar(a, b, round(float(t) * 128) / 128)


@functools.lru_cache(maxsize=16384)
def _mezclar(a, b, t):
    ra, rb = hex_rgb(a), hex_rgb(b)
    return "#%02x%02x%02x" % tuple(int(x + (y - x) * t) for x, y in zip(ra, rb))


def _azar(i, sal=0):
    return ((int(i) * 2654435761 + sal * 40503) % 4294967296) / 4294967296.0


def rect_redondo(cv, x0, y0, x1, y1, r=10, **kw):
    pts = (x0 + r, y0, x1 - r, y0, x1, y0, x1, y0 + r, x1, y1 - r, x1, y1, x1 - r, y1,
           x0 + r, y1, x0, y1, x0, y1 - r, x0, y0 + r, x0, y0)
    return cv.create_polygon(pts, smooth=True, **kw)


_SUPERFICIE = {
    "asfalto": "#2c3036", "tierra": "#a06a38", "pasto": "#5fa040", "grava": "#b3aa9b",
    "arena": "#ecd08a", "lodo": "#4a3420", "roca": "#8c8882", "nieve": "#ffffff", "hielo": "#d9f3fc",
}
_BORDE = {
    "asfalto": "#5b6169", "tierra": "#c08451", "pasto": "#8fd065", "grava": "#d6cfc2",
    "arena": "#fff0bd", "lodo": "#6d5434", "roca": "#b4b0aa", "nieve": "#ffffff", "hielo": "#ffffff",
}
COLOR_SUP = tuple(_SUPERFICIE[n] for n in NOMBRES_MAT)
COLOR_BORDE = tuple(_BORDE[n] for n in NOMBRES_MAT)
COLOR_PROFUNDO = tuple(mezclar(c, "#000000", 0.45) for c in COLORES)
COLOR_SOMBRA = tuple(mezclar(c, "#000000", 0.4) for c in COLOR_SUP)


CIELO_ARRIBA = "#0d1220"
CIELO_HORIZONTE = "#6a4a3a"


_CIELO = {}


def _imagen_cielo(ancho, alto):
    if (ancho, alto) not in _CIELO:
        try:
            from PIL import Image, ImageDraw, ImageFilter, ImageTk
        except ImportError:
            _CIELO[(ancho, alto)] = None
            return None
        arriba, horiz = np.array(hex_rgb(CIELO_ARRIBA)), np.array(hex_rgb(CIELO_HORIZONTE))
        t = np.clip(np.arange(alto) / (alto * 0.62), 0, 1)[:, None] ** 1.6
        filas = (arriba + (horiz - arriba) * t).astype(np.uint8)
        img = Image.fromarray(np.repeat(filas[:, None, :], ancho, axis=1), "RGB")
        halo = Image.new("L", (ancho, alto), 0)
        d = ImageDraw.Draw(halo)
        sx, sy = ancho * 0.78, alto * 0.30
        d.ellipse((sx - 95, sy - 95, sx + 95, sy + 95), fill=90)
        halo = halo.filter(ImageFilter.GaussianBlur(40))
        img = Image.composite(Image.new("RGB", (ancho, alto), (243, 200, 154)), img, halo)
        d = ImageDraw.Draw(img)
        d.ellipse((sx - 26, sy - 26, sx + 26, sy + 26), fill=(246, 214, 170))
        _CIELO[(ancho, alto)] = ImageTk.PhotoImage(img)
    return _CIELO[(ancho, alto)]


def dibujar_cielo(cv, ancho, alto, cam_x, escala):
    horizonte = alto * 0.62
    imagen = _imagen_cielo(ancho, alto)
    if imagen is not None:
        cv.create_image(0, 0, image=imagen, anchor="nw")
    else:
        bandas = 26
        for k in range(bandas):
            y0 = horizonte * k / bandas
            y1 = horizonte * (k + 1) / bandas + 1
            cv.create_rectangle(0, y0, ancho, y1, width=0,
                                fill=mezclar(CIELO_ARRIBA, CIELO_HORIZONTE, (k / (bandas - 1)) ** 1.6))
        cv.create_rectangle(0, horizonte, ancho, alto, fill=CIELO_HORIZONTE, width=0)
        sx, sy = ancho * 0.78, alto * 0.30
        for r, t in ((70, 0.18), (48, 0.35), (32, 0.6), (22, 0.85)):
            cv.create_oval(sx - r, sy - r, sx + r, sy + r, width=0,
                           fill=mezclar(mezclar(CIELO_ARRIBA, CIELO_HORIZONTE, 0.55), "#f3c89a", t))
    _silueta(cv, ancho, alto, cam_x * escala * 0.05, alto * 0.50, 38, 160,
             mezclar(CIELO_HORIZONTE, "#2a2533", 0.55))
    desfase = cam_x * escala * 0.16
    color = mezclar(CIELO_HORIZONTE, "#1b1a22", 0.75)
    ventana = mezclar(color, "#ff9a4a", 0.45)
    base = alto * 0.66
    k0 = int(desfase // 46) - 1
    for k in range(k0, k0 + int(ancho / 46) + 3):
        if _azar(k, 1) < 0.18:
            continue
        x = k * 46 - desfase
        w = 26 + 30 * _azar(k, 2)
        h = 40 + 150 * _azar(k, 3) ** 1.5
        roto = 14 * _azar(k, 4)
        cv.create_polygon(x, base, x, base - h, x + w * 0.4, base - h - roto * 0.3,
                          x + w * 0.6, base - h + roto, x + w, base - h + roto * 0.5, x + w, base,
                          fill=color, outline="")
        for f in range(int(h // 22)):
            if _azar(k * 31 + f, 5) < 0.12:
                yy = base - 12 - f * 22
                cv.create_rectangle(x + 6, yy, x + 10, yy + 5, fill=ventana, outline="")
    _silueta(cv, ancho, alto, cam_x * escala * 0.35, alto * 0.70, 24, 230,
             mezclar(CIELO_HORIZONTE, "#121319", 0.82))


def _silueta(cv, ancho, alto, desfase, base, amp, largo, color):
    pts = [0, alto]
    for px in range(0, ancho + 30, 30):
        u = (px + desfase) / largo
        pts += [px, base - amp * (math.sin(u) + 0.5 * math.sin(2.7 * u + 1.3)
                                  + 0.25 * math.sin(6.1 * u + 0.4))]
    pts += [ancho, alto]
    cv.create_polygon(pts, fill=color, outline="")



_PALETAS_MOJADAS = {}


def _paletas(mojado):
    k = int(round(min(max(mojado, 0.0), 1.0) * 4))
    if k not in _PALETAS_MOJADAS:
        t = 0.32 * k / 4
        osc = lambda cols: tuple(mezclar(c, "#06080c", t) for c in cols)
        _PALETAS_MOJADAS[k] = (osc(COLORES), osc(COLOR_PROFUNDO), osc(COLOR_SUP),
                               tuple(mezclar(c, "#9fb4c8", 0.35 * k / 4) for c in COLOR_BORDE))
    return _PALETAS_MOJADAS[k]


def dibujar_terreno(cv, p, x0, x1, a_pantalla, escala, alto, mojado=0.0, charcos=0.0):
    i0, i1 = p.indice(max(x0, 0)), p.indice(min(x1, p.longitud))
    idx = np.arange(i0, i1 + 1, 2)
    if len(idx) < 2:
        return
    colores, c_profundo, c_sup, c_borde = _paletas(mojado)
    xs, hs, mats = p.xs[idx], p.hs[idx], p.mat[idx]
    cortes = np.flatnonzero(np.diff(mats)) + 1
    capa = 0.22 * escala
    profundo = 0.9 * escala
    for a, b in zip(np.r_[0, cortes], np.r_[cortes, len(idx)]):
        b = min(b + 1, len(idx))
        m = mats[a]
        sup = []
        for x, h in zip(xs[a:b], hs[a:b]):
            sup += a_pantalla(x, h)
        if len(sup) < 4:
            continue
        bajo = [v + (capa if k % 2 else 0) for k, v in enumerate(sup)]
        hondo = [v + (profundo if k % 2 else 0) for k, v in enumerate(sup)]
        cv.create_polygon(sup[0], alto, *sup, sup[-2], alto, fill=colores[m], outline="")
        cv.create_polygon(hondo[0], alto, *hondo, hondo[-2], alto, fill=c_profundo[m], outline="")
        inversa = []
        for k in range(len(bajo) - 2, -1, -2):
            inversa += [bajo[k], bajo[k + 1]]
        cv.create_polygon(*sup, *inversa, fill=c_sup[m], outline="")
        cv.create_line(*sup, fill=c_borde[m], width=2)

    if charcos > 0.02:
        paso = 6
        for i in range(int(i0) - int(i0) % paso, int(i1), paso):
            if _azar(i, 31) > 0.30 * charcos:
                continue
            sx, sy = a_pantalla(p.xs[i], p.hs[i])
            w = (0.5 + 1.1 * _azar(i, 32)) * escala
            cv.create_oval(sx - w, sy - 1.5, sx + w, sy + 2.5, fill="#3c5266", outline="",
                           tags="charco")
            cv.create_line(sx - w * 0.5, sy - 0.5, sx + w * 0.3, sy - 0.5, fill="#a9c3d9",
                           tags="charco")

    for i in range(int(i0) - int(i0) % 4, int(i1), 4):
        r = _azar(i)
        m = int(p.mat[i])
        nombre = NOMBRES_MAT[m]
        sx, sy = a_pantalla(p.xs[i], p.hs[i])
        if r < 0.35:
            yy = sy + capa + (profundo * 1.6) * _azar(i, 7)
            rr = 1.5 + 2.5 * _azar(i, 8)
            cv.create_oval(sx - rr, yy - rr * 0.7, sx + rr, yy + rr * 0.7,
                           fill=mezclar(COLORES[m], "#000000", 0.25), outline="")
        if _azar(i, 9) > 0.45:
            continue
        _detalle(cv, nombre, sx, sy, i, capa)


def _detalle(cv, nombre, sx, sy, i, capa):
    r = _azar(i, 11)
    if nombre == "pasto":
        for d in (-3, 0, 3):
            alto = 4 + 6 * _azar(i + d, 12)
            cv.create_line(sx + d, sy, sx + d + 2 * (r - 0.5), sy - alto,
                           fill="#8fd065" if d else "#6fb048", width=1)
    elif nombre == "grava":
        for d in range(3):
            rr = 1.5 + 1.5 * _azar(i, 13 + d)
            xx = sx + 8 * (_azar(i, 16 + d) - 0.5)
            cv.create_oval(xx - rr, sy - rr, xx + rr, sy + rr * 0.6, fill="#d3cbbd", outline="#7d766b")
    elif nombre == "roca":
        t = 4 + 6 * r
        cv.create_polygon(sx - t, sy + 1, sx - t * 0.6, sy - t * 0.7, sx + t * 0.2, sy - t,
                          sx + t, sy - t * 0.4, sx + t * 0.9, sy + 1, fill="#9a968f", outline="#5f5b56")
        cv.create_line(sx - t * 0.5, sy - t * 0.6, sx + t * 0.2, sy - t * 0.9, fill="#c9c5be")
    elif nombre == "arena":
        for d in range(3):
            xx = sx + 10 * (_azar(i, 20 + d) - 0.5)
            yy = sy + 2 + capa * 0.8 * _azar(i, 23 + d)
            cv.create_oval(xx - 1, yy - 1, xx + 1, yy + 1, fill="#fff2c4", outline="")
    elif nombre == "lodo":
        w = 6 + 8 * r
        cv.create_oval(sx - w, sy - 1.5, sx + w, sy + 2.5, fill="#2e1f12", outline="")
        cv.create_line(sx - w * 0.5, sy - 0.5, sx + w * 0.2, sy - 0.5, fill="#8a7353")
    elif nombre == "nieve":
        w = 3 + 5 * r
        cv.create_oval(sx - w, sy - w * 0.5, sx + w, sy + w * 0.3, fill="#ffffff", outline="#dfe9f2")
    elif nombre == "hielo":
        cv.create_line(sx - 4, sy + capa * 0.9, sx + 4, sy + 3, fill="#ffffff", width=1)
    elif nombre == "tierra":
        cv.create_oval(sx - 2, sy + 3, sx + 2, sy + 5, fill="#6f4724", outline="")
    elif nombre == "asfalto" and r < 0.3:
        cv.create_line(sx - 6, sy + 3, sx + 6, sy + 3, fill="#3d424a")



MAX_GOTAS = 110
MAX_GRANIZO = 36


def dibujar_precipitacion(cv, estado, n_gotas, n_granizo, viento, ancho, alto, rng, quieto=False):
    deriva = max(-14.0, min(14.0, viento * 0.9))
    for clave, n, base in (("gotas", n_gotas, 15.0), ("granizo", n_granizo, 11.0)):
        lista = estado[clave]
        del lista[n:]
        while len(lista) < n:
            lista.append([rng.random() * (ancho + 80) - 40, rng.random() * alto,
                          base * (0.75 + 0.5 * rng.random())])
        for q in lista:
            if not quieto:
                q[0] += deriva * (0.6 if clave == "granizo" else 1.0)
                q[1] += q[2]
                if q[1] > alto or q[0] < -50 or q[0] > ancho + 50:
                    q[0] = rng.random() * (ancho + 80) - 40 - deriva * 4
                    q[1] = -rng.random() * 30
            x, y, v = q
            if clave == "gotas":
                k = 0.9
                cv.create_line(x, y, x - deriva * k, y - v * k, fill="#9fb8cf", tags="lluvia")
            else:
                cv.create_oval(x - 2, y - 2, x + 2, y + 2, fill="#f4f8fb", outline="",
                               tags="granizo")


def dibujar_niebla(cv, ancho, alto, niebla, y0=0):
    patron = "gray75" if niebla > 0.75 else "gray50" if niebla > 0.45 else "gray25" \
        if niebla > 0.2 else "gray12"
    cv.create_rectangle(0, y0, ancho, alto, fill="#b9c3cc", outline="", stipple=patron,
                        tags="niebla")
    if niebla > 0.3:
        cv.create_rectangle(0, y0, ancho, y0 + (alto - y0) * 0.45, fill="#c9d2da", outline="",
                            stipple="gray25", tags="niebla")


def dibujar_viento(cv, cx, cy, kmh, ang, rafaga, fondo="#0b0f15"):
    col = "#ffc940" if rafaga else "#9fd3ff"
    rect_redondo(cv, cx - 62, cy - 22, cx + 62, cy + 22, r=10, fill=fondo, outline="#222c3a",
                 tags="viento")
    ax, ay = cx - 40, cy
    dx, dy = -math.sin(ang), -math.cos(ang)
    largo = 15
    cv.create_oval(ax - 17, ay - 17, ax + 17, ay + 17, outline="#253042", tags="viento")
    cv.create_line(ax - dx * largo, ay - dy * largo, ax + dx * largo, ay + dy * largo,
                   fill=col, width=3, arrow="last", arrowshape=(8, 9, 4), tags="viento")
    cv.create_text(cx - 16, cy - 7, anchor="w", text=f"{kmh:.0f} km/h", fill="#e3e8ef",
                   font=("Segoe UI", 10, "bold"), tags="viento")
    cv.create_text(cx - 16, cy + 9, anchor="w", text="¡RÁFAGA!" if rafaga else "viento",
                   fill=col, font=("Segoe UI", 7, "bold" if rafaga else "normal"), tags="viento")


def dibujar_sombra(cv, p, x, a_pantalla, escala):
    m = p.mat[p.indice(x)]
    sx, sy = a_pantalla(x, p.altura(x))
    w = 1.15 * escala
    cv.create_oval(sx - w, sy - 3, sx + w, sy + 4, fill=COLOR_SOMBRA[m], outline="")



CUERPO = ((-1.10, 0.10), (-1.02, 0.30), (-0.70, 0.36), (-0.40, 0.26), (-0.05, 0.30),
          (0.25, 0.46), (0.62, 0.50), (0.92, 0.36), (1.12, 0.16), (1.02, -0.02), (0.70, -0.06),
          (0.40, -0.22), (-0.10, -0.30), (-0.50, -0.22), (-0.85, -0.06))
BLINDAJE = ((0.0, 0.30), (0.25, 0.44), (0.60, 0.48), (0.86, 0.36), (0.62, 0.26), (0.22, 0.22))
COLA = ((-1.02, 0.28), (-0.70, 0.34), (-0.42, 0.24), (-0.55, 0.15), (-0.95, 0.17))
MOTOR = ((-0.32, -0.26), (0.30, -0.28), (0.42, -0.04), (0.10, 0.06), (-0.30, 0.02))
ESCAPE = ((0.25, -0.22), (-0.30, -0.31), (-0.75, -0.19), (-1.06, 0.02))
FRANJA = ((-1.0, 0.22), (-0.62, 0.27), (-0.35, 0.18), (0.05, 0.22), (0.60, 0.40), (0.95, 0.28))
CABEZA = ((0.80, 0.30), (1.08, 0.22), (1.15, 0.10), (1.03, 0.01), (0.82, 0.08))
OJO = (1.02, 0.14)
ROJO = "#ff2a2a"


def _pts(local, puntos):
    out = []
    for x, y in puntos:
        out += local(x, y)
    return out


def rueda(cv, sx, sy, r, ang):
    pts = []
    for m in range(18):
        a = ang + m * 2 * math.pi / 18
        for da, rr in ((-0.075, 0.95), (-0.055, 1.03), (0.055, 1.03), (0.075, 0.95)):
            pts += (sx + math.cos(a + da) * r * rr, sy - math.sin(a + da) * r * rr)
    cv.create_polygon(pts, fill="#1f2125", outline="#050506", width=1)
    cv.create_oval(sx - r * 0.93, sy - r * 0.93, sx + r * 0.93, sy + r * 0.93, fill="#101113",
                   outline="")
    cv.create_oval(sx - r * 0.8, sy - r * 0.8, sx + r * 0.8, sy + r * 0.8, outline="#2a2d32", width=2)
    cv.create_oval(sx - r * 0.68, sy - r * 0.68, sx + r * 0.68, sy + r * 0.68,
                   fill="#16181c", outline="#c3cbd5", width=2)
    for m in range(5):
        a = ang + m * 2 * math.pi / 5
        pts = []
        for dd, rr in ((-0.12, 0.18), (-0.12, 0.64), (0.12, 0.64), (0.12, 0.18)):
            pts += (sx + math.cos(a + dd) * r * rr, sy - math.sin(a + dd) * r * rr)
        cv.create_polygon(pts, fill="", outline="#8f99a6", width=2)
    cv.create_oval(sx - r * 0.42, sy - r * 0.42, sx + r * 0.42, sy + r * 0.42, outline="#a8b1bc", width=2)
    cv.create_oval(sx - r * 0.15, sy - r * 0.15, sx + r * 0.15, sy + r * 0.15, fill="#e2e7ec", outline="#7d8692")


def dibujar_moto(cv, local, ruedas, angulos, r, gas=0.0, freno=0.0):
    if C.CG_ATRAS or C.CG_ABAJO:
        base = local
        local = lambda x, y: base(x + C.CG_ATRAS, y + C.CG_ABAJO)
    pivote = local(-0.12, -0.16)
    rx, ry = ruedas[0]
    cv.create_line(*pivote, rx, ry, fill="#2b3037", width=max(6, r * 0.42), capstyle="round")
    cv.create_line(*pivote, rx, ry, fill="#5a626d", width=2)
    arriba = local(-0.42, 0.20)
    medio = ((pivote[0] + rx) / 2, (pivote[1] + ry) / 2)
    cv.create_line(*arriba, *medio, fill="#aeb6c0", width=3)
    dx, dy = medio[0] - arriba[0], medio[1] - arriba[1]
    largo = math.hypot(dx, dy) or 1
    nx, ny = -dy / largo * 4, dx / largo * 4
    resorte = []
    for k in range(10):
        t = 0.15 + 0.7 * k / 9
        s = 1 if k % 2 else -1
        resorte += [arriba[0] + dx * t + nx * s, arriba[1] + dy * t + ny * s]
    cv.create_line(*resorte, fill="#d32f2f", width=2)

    for (sx, sy), a in zip(ruedas, angulos):
        rueda(cv, sx, sy, r, a)

    tope = local(0.62, 0.36)
    fx, fy = ruedas[1]
    cv.create_line(*tope, fx, fy, fill="#cfd6de", width=max(4, r * 0.24))
    cx = tope[0] + (fx - tope[0]) * 0.5
    cy = tope[1] + (fy - tope[1]) * 0.5
    cv.create_line(cx, cy, fx, fy, fill="#2a2e34", width=max(5, r * 0.32))

    cv.create_polygon(_pts(local, CUERPO), fill="#181b20", outline="#30353d", width=2)
    cv.create_polygon(_pts(local, MOTOR), fill="#474e58", outline="#7f8894", width=1)
    for x in (-0.18, -0.04, 0.10, 0.24):
        cv.create_line(*local(x, -0.25), *local(x + 0.05, 0.0), fill="#2d3239", width=2)
    escape = _pts(local, ESCAPE)
    cv.create_line(*escape, fill="#9aa3ad", width=max(4, r * 0.26), capstyle="round", smooth=True)
    cv.create_line(*escape, fill="#e6ebf0", width=1, smooth=True)
    cv.create_polygon(_pts(local, COLA), fill="#23272e", outline="#4a515b")
    cv.create_polygon(_pts(local, BLINDAJE), fill="#2c323b", outline="#66707c")
    cv.create_line(*_pts(local, ((0.05, 0.31), (0.25, 0.45), (0.60, 0.49))), fill="#a3adb9")
    cv.create_line(*_pts(local, FRANJA), fill="#c62828", width=2, smooth=True)
    cv.create_polygon(_pts(local, ((-1.11, 0.12), (-1.05, 0.12), (-1.03, 0.22), (-1.09, 0.22))),
                      fill="#ff3b30" if freno < 0.1 else "#ff8a80", outline="")
    cv.create_polygon(_pts(local, CABEZA), fill="#0e1013", outline="#454c55", width=1)
    ox, oy = local(*OJO)
    for rr, col in ((12, "#2a0d0d"), (8, "#6a1212"), (5, ROJO), (2, "#ffd9d9")):
        cv.create_oval(ox - rr, oy - rr, ox + rr, oy + rr, fill=col, outline="")
    if gas > 0.25:
        tx, ty = escape[-2], escape[-1]
        px, py = escape[-4], escape[-3]
        dx, dy = tx - px, ty - py
        d = math.hypot(dx, dy) or 1
        dx, dy = dx / d, dy / d
        largo = 8 + 18 * gas
        cv.create_polygon(tx - dy * 3, ty + dx * 3, tx + dx * largo, ty + dy * largo,
                          tx + dy * 3, ty - dx * 3, fill="#ff9f1c", outline="")
        cv.create_polygon(tx - dy * 1.5, ty + dx * 1.5, tx + dx * largo * 0.55, ty + dy * largo * 0.55,
                          tx + dy * 1.5, ty - dx * 1.5, fill="#fff3b0", outline="")


def dibujar_fantasma(cv, local, ruedas, r, color):
    for sx, sy in ruedas:
        cv.create_oval(sx - r, sy - r, sx + r, sy + r, outline=color, width=1)
    cv.create_polygon(_pts(local, CUERPO), fill="", outline=color, width=1)
    ox, oy = local(*OJO)
    cv.create_oval(ox - 2, oy - 2, ox + 2, oy + 2, fill="#a33", outline="")
