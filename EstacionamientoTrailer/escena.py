import math
import random

import config as C
import estilo as E
from estilo import P
from fisica import cajones

ESC = C.ESCALA
MARGEN = 26
ANCHO = int(C.LOTE_ANCHO * ESC) + 2 * MARGEN
ALTO = int(C.LOTE_ALTO * ESC) + 2 * MARGEN
ASFALTO = (48, 51, 57)
CONCRETO = (86, 88, 90)
PINTURA = (226, 228, 222)
AMARILLO = (222, 186, 60)
COLORES_CAJAS = ["#e6e8ec", "#c9ced6", "#b23a32", "#2f5f9e", "#e6e8ec", "#5f6b78",
                 "#d9d2c3", "#1f6f5c"]


def px(x, y):
    return MARGEN + x * ESC, MARGEN + y * ESC


def a_metros(sx, sy):
    return (sx - MARGEN) / ESC, (sy - MARGEN) / ESC


def fondo(tamano):
    al = random.Random(11)
    p = E.Pintor(ANCHO, ALTO)
    p.textura(0, 0, ANCHO, ALTO, (52, 84, 52), 26, grano=0.9, escala=10, semilla=1, manchas=0.8)
    x0, y0 = px(0, 0)
    x1, y1 = px(C.LOTE_ANCHO, C.LOTE_ALTO)
    p.rect(x0 - 8, y0, x1 + 8, y1 + 8, (0, 0, 0), alfa=0.45, suave=6)
    p.rect(x0 - 6, y0, x1 + 6, y1 + 6, (168, 168, 160), radio=3)
    _, yf = px(0, C.CAJON_FONDO)
    p.textura(x0, y0, x1, yf, CONCRETO, 7, grano=0.9, escala=30, semilla=3, manchas=0.8)
    p.textura(x0, yf, x1, y1, ASFALTO, 9, grano=1.1, escala=40, semilla=2, manchas=0.7)
    for k in range(int(C.LOTE_ANCHO / 6) + 1):
        xx = px(k * 6.0, 0)[0]
        p.rect(xx - 0.5, y0, xx + 0.5, yf, (70, 72, 74), alfa=0.6)
    for k in range(1, 5):
        yy = px(0, k * 6.0)[1]
        p.rect(x0, yy - 0.5, x1, yy + 0.5, (70, 72, 74), alfa=0.6)
    p.rect(x0, yf - 3, x1, yf + 1, (30, 31, 34), alfa=0.6, suave=2)

    lista = cajones(tamano)
    for _ in range(40):
        x, y = al.uniform(x0, x1), al.uniform(yf + 10, y1)
        p.circulo(x, y, al.uniform(4, 14), (30, 32, 36), alfa=al.uniform(0.1, 0.22),
                  suave=al.uniform(6, 12))
    for cx0, _, cx1, _ in lista:
        x, y = px((cx0 + cx1) / 2, al.uniform(6, 20))
        p.circulo(x, y, al.uniform(6, 12), (52, 54, 56), alfa=0.35, suave=10)
    for k in range(6):
        yy = px(0, 33 + k * 3.2 + al.uniform(-0.6, 0.6))[1]
        p.linea(x0 + 30, yy, x1 - 30, yy + al.uniform(-10, 10), 7, (38, 40, 44), alfa=0.15,
                suave=5)

    g = max(1.6, C.LINEA_ANCHO * ESC)
    bordes = sorted({round(x, 3) for c in lista for x in (c[0], c[2])})
    for xx in bordes:
        xa, ya = px(xx, 0)
        _, yb = px(xx, C.CAJON_FONDO)
        p.rect(xa - g / 2, ya, xa + g / 2, yb, AMARILLO, alfa=0.9)
    for cx0, _, cx1, _ in lista:
        xa, _ = px(cx0, 0)
        xb, yb = px(cx1, C.CAJON_FONDO)
        p.rect(xa, yb - 1.2, xb, yb + 1.2, PINTURA, alfa=0.55)
    for _ in range(900):
        xx = al.choice(bordes)
        xa, _ = px(xx, 0)
        _, yy = px(0, al.uniform(0, C.CAJON_FONDO))
        p.circulo(xa + al.uniform(-g / 2, g / 2), yy, al.uniform(0.4, 1.0), CONCRETO,
                  alfa=al.uniform(0.2, 0.5), suave=1)

    p.rect(x0 - 6, 0, x1 + 6, y0, (74, 78, 86))
    for k in range(int((x1 - x0) / 6)):
        xx = x0 + k * 6
        p.rect(xx, 0, xx + 1, y0 - 4, (64, 68, 76))
    p.rect(x0 - 6, y0 - 5, x1 + 6, y0, (40, 42, 48))
    for cx0, _, cx1, _ in lista:
        cx = px((cx0 + cx1) / 2, 0)[0]
        mitad = min(1.5, (cx1 - cx0) / 2 - 0.5) * ESC
        p.rect(cx - mitad, 4, cx + mitad, y0 - 1, (28, 30, 34), radio=1)
        for k in range(4):
            yy = 6 + k * (y0 - 8) / 4
            p.rect(cx - mitad + 1, yy, cx + mitad - 1, yy + 1, (44, 46, 52))
        for lado in (-1, 1):
            p.rect(cx + lado * (mitad + 2) - 2, y0 - 6, cx + lado * (mitad + 2) + 2, y0 + 2,
                   (16, 16, 18), radio=1)
        p.circulo(cx, 2.5, 1.6, (255, 220, 140), alfa=0.9)
        p.circulo(cx, 6, 7, (255, 220, 140), alfa=0.08, suave=6)

    for xm in (C.LOTE_ANCHO * 0.42, C.LOTE_ANCHO * 0.78):
        xa, ya = px(xm, 49.0)
        xb, _ = px(xm + 7.0, 49.0)
        p.rect(xa, ya - 0.3 * ESC, xb - 2.6 * ESC, ya + 0.3 * ESC, PINTURA, alfa=0.45)
        p.poligono([(xb - 2.7 * ESC, ya - 1.2 * ESC), (xb, ya), (xb - 2.7 * ESC, ya + 1.2 * ESC)],
                   PINTURA, alfa=0.45)

    for x, y, r in ((MARGEN * 0.4, ALTO - MARGEN * 0.5, 20),
                    (ANCHO - MARGEN * 0.5, ALTO - MARGEN * 0.4, 18),
                    (ANCHO * 0.5, ALTO - MARGEN * 0.45, 14)):
        p.circulo(x + 5, y + 6, r, (0, 0, 0), alfa=0.45, suave=10)
        p.circulo(x, y, r, (40, 92, 46))
        p.circulo(x - r * 0.25, y - r * 0.25, r * 0.65, (66, 128, 62), alfa=0.8, suave=r * 0.5)
        p.circulo(x - r * 0.35, y - r * 0.4, r * 0.25, (110, 170, 90), alfa=0.6, suave=r * 0.3)
    return p.foto()


def sprite_doble(color):
    s = ESC
    cajas = C.ESTACIONADO_CAJAS
    largo = sum(cajas) + C.ESTACIONADO_SEPARACION
    m = 6
    w, h = int(2.6 * s) + 2 * m + 4, int(largo * s) + 2 * m + 6
    p = E.Pintor(w, h, transparente=True)
    pintura = E.rgb(color)
    oscuro = E.rgb(E.oscurecer(color, 0.3))
    x0, x1 = m, m + 2.6 * s
    cx = (x0 + x1) / 2
    p.rect(x0 + 3, m + 4, x1 + 3, m + largo * s + 4, (0, 0, 0), radio=3, alfa=0.5, suave=5)
    y = m
    for k, largo_caja in enumerate(cajas):
        if k:
            p.linea(cx, y - 1, cx, y + C.ESTACIONADO_SEPARACION * s + 1, 2.4, (26, 26, 28))
            yd = y + C.ESTACIONADO_SEPARACION * s * 0.55
            p.rect(cx - 0.9 * s, yd - 0.25 * s, cx + 0.9 * s, yd + 0.25 * s, (20, 20, 22), radio=1)
            y += C.ESTACIONADO_SEPARACION * s
        yb = y + largo_caja * s
        p.rect(x0, y, x1, yb, oscuro, radio=1.5)
        p.rect(x0 + 1, y + 1, x1 - 1, yb - 1, pintura, radio=1)
        p.rect(cx - 0.6 * s, y + 2, cx + 0.6 * s, yb - 2, (255, 255, 255), alfa=0.12, suave=4)
        k2 = 0.9 * s
        yy = y + k2
        while yy < yb - 2:
            p.rect(x0 + 1.5, yy, x1 - 1.5, yy + 1, oscuro, alfa=0.35)
            yy += k2
        p.rect(x0 + 1, yb - 2, x0 + 4, yb - 0.5, (170, 30, 30))
        p.rect(x1 - 4, yb - 2, x1 - 1, yb - 0.5, (170, 30, 30))
        y = yb
    return p.foto(), m


def sprite_objetivo(modo, tamano):
    s = ESC
    w, h = int(C.TAMANOS[tamano] * s), int(C.CAJON_FONDO * s)
    p = E.Pintor(w, h, (56, 196, 140), transparente=True)
    g = C.LINEA_ANCHO * s + 1
    p.rect(g, 0, w - g, h, (56, 196, 140), alfa=0.14)
    cx = w / 2
    cola, punta = (17.0 * s, 4.0 * s) if modo == "frente" else (4.0 * s, 17.0 * s)
    d = 1 if punta > cola else -1
    base = punta - d * 2.6 * s
    p.rect(cx - 0.3 * s, min(cola, base), cx + 0.3 * s, max(cola, base), PINTURA, alfa=0.6)
    p.poligono([(cx - 1.2 * s, base), (cx, punta), (cx + 1.2 * s, base)], PINTURA, alfa=0.6)
    return p.foto()


def transformar(x, y, ang, puntos):
    c, s = math.cos(ang), math.sin(ang)
    return [v for lx, ly in puntos for v in px(x + lx * c - ly * s, y + lx * s + ly * c)]


def caja(u0, u1, v0, v1):
    return ((u1, v0), (u1, v1), (u0, v1), (u0, v0))


T = C.TRACTOR
_FR, _HW = T["frente"], T["ancho"] / 2
CABINA = caja(_FR - 2.3, _FR, -_HW, _HW)
TECHO_CABINA = caja(_FR - 2.1, _FR - 0.75, -_HW + 0.2, _HW - 0.2)
PARABRISAS = ((_FR - 0.25, -1.02), (_FR - 0.25, 1.02), (_FR - 0.75, 1.1), (_FR - 0.75, -1.1))
CHASIS = caja(-T["atras"], _FR - 2.3, -0.55, 0.55)
FAROS = [caja(_FR - 0.12, _FR, v, v + 0.45) for v in (-_HW + 0.12, _HW - 0.57)]
ESPEJOS = [caja(_FR - 0.7, _FR - 0.5, v, v + 0.25) for v in (-_HW - 0.28, _HW + 0.03)]
ESCAPES = [caja(_FR - 2.55, _FR - 2.35, v, v + 0.2) for v in (-_HW + 0.05, _HW - 0.25)]
CAMARA = caja(C.CAMARA["x"] - 0.15, C.CAMARA["x"] + 0.15, C.CAMARA["y"] - 0.05, C.CAMARA["y"] + 0.2)
LLANTA = (0.55, 0.3)


def llantas_tractor(giro):
    res = []
    lu, lv = LLANTA
    c, s = math.cos(giro), math.sin(giro)
    for v in (-_HW + 0.15, _HW - 0.15):
        u = T["dist_ejes"]
        res.append([(u + a * c - b * s, v + a * s + b * c)
                    for a, b in ((lu, -lv / 2), (lu, lv / 2), (-lu, lv / 2), (-lu, -lv / 2))])
        for u in (-0.65, 0.65):
            res.append(caja(u - lu, u + lu, v - lv / 2 - 0.08, v + lv / 2 + 0.08))
    return res


def llantas_remolque(spec):
    lu, lv = LLANTA
    hw = spec["ancho"] / 2
    return [caja(u - lu, u + lu, v - lv / 2, v + lv / 2)
            for u in (-0.65, 0.65) for v in (-hw + 0.18, hw - 0.18)]


class Lider:

    def __init__(self, cv, specs, color=P["acento"]):
        self.cv = cv
        self.specs = specs
        nuevo = lambda **k: cv.create_polygon(0, 0, 0, 0, 0, 0, tags="camion", **k)
        linea = lambda **k: cv.create_line(0, 0, 0, 0, tags="camion", **k)
        self.sombras = [nuevo(fill="#202226", outline="") for _ in specs]
        self.lanzas = [linea(fill="#15161a", width=3) for _ in specs[1:]]
        self.llantas = [[nuevo(fill="#0c0d0f", outline="") for _ in
                         (llantas_tractor(0) if u == 0 else llantas_remolque(s))]
                        for u, s in enumerate(specs)]
        self.chasis = nuevo(fill="#2a2d33", outline="")
        self.quinta = cv.create_oval(0, 0, 0, 0, tags="camion", fill="#3a3d44", outline="#111")
        self.cuerpos = []
        self.costillas = []
        self.calaveras = []
        for u, s in enumerate(specs[1:], start=1):
            self.cuerpos.append(nuevo(fill="#e3e6eb", outline="#9aa1ab", width=1))
            n = int((s["frente"] + s["atras"]) / 1.1)
            self.costillas.append([linea(fill="#c2c7cf") for _ in range(n)])
            self.calaveras.append([nuevo(fill="#8c1a1f", outline="") for _ in range(2)])
        self.cabina = nuevo(fill=color, outline=E.oscurecer(color, 0.45), width=1)
        self.techo = nuevo(fill=E.aclarar(color, 0.22), outline="")
        self.parabrisas = nuevo(fill="#1d2532", outline="")
        self.faros = [nuevo(fill="#f4f1dc", outline="") for _ in range(2)]
        self.espejos = [nuevo(fill="#2a2d33", outline="") for _ in range(2)]
        self.escapes = [nuevo(fill="#b9bec7", outline="") for _ in range(2)]
        self.camara = nuevo(fill=P["cian"], outline="")

    def actualizar(self, cam, freno, borde=None, camara=False):
        cv = self.cv
        ejes, angs = cam.ejes(), cam.angulos
        for item, esq in zip(self.sombras, cam.carrocerias()):
            cv.coords(item, *[c for x, y in esq for c in px(x + 0.35, y + 0.45)])
        for item, (hx, hy), (ex, ey), a, s in zip(self.lanzas, cam.enganches(), ejes[1:],
                                                  angs[1:], self.specs[1:]):
            fx, fy = ex + s["frente"] * math.cos(a), ey + s["frente"] * math.sin(a)
            cv.coords(item, *px(hx, hy), *px(fx, fy))
        for u, items in enumerate(self.llantas):
            (x, y), a = ejes[u], angs[u]
            formas = llantas_tractor(cam.giro) if u == 0 else llantas_remolque(self.specs[u])
            for item, forma in zip(items, formas):
                cv.coords(item, *transformar(x, y, a, forma))
        (x, y), a = ejes[0], angs[0]
        cv.coords(self.chasis, *transformar(x, y, a, CHASIS))
        hx, hy = (cam.enganches() or [(x, y)])[0]
        r = 0.55 * ESC
        cx, cy = px(hx, hy)
        cv.coords(self.quinta, cx - r, cy - r, cx + r, cy + r)
        luz = "#f2f4f8" if cam.marcha < 0 else ("#ff2b3a" if freno > 0.05 else "#8c1a1f")
        for u, (cuerpo, costillas, calaveras) in enumerate(
                zip(self.cuerpos, self.costillas, self.calaveras), start=1):
            (x, y), a, s = ejes[u], angs[u], self.specs[u]
            hw = s["ancho"] / 2
            cv.coords(cuerpo, *transformar(x, y, a, caja(-s["atras"], s["frente"], -hw, hw)))
            cv.itemconfigure(cuerpo, outline=borde or "#9aa1ab", width=2 if borde else 1)
            paso = (s["frente"] + s["atras"]) / (len(costillas) + 1)
            for k, item in enumerate(costillas, start=1):
                u0 = -s["atras"] + k * paso
                cv.coords(item, *transformar(x, y, a, ((u0, -hw + 0.12), (u0, hw - 0.12))))
            for item, v in zip(calaveras, (-hw + 0.1, hw - 0.55)):
                cv.coords(item, *transformar(x, y, a, caja(-s["atras"], -s["atras"] + 0.15,
                                                           v, v + 0.45)))
                cv.itemconfigure(item, fill=luz)
        (x, y), a = ejes[0], angs[0]
        cv.coords(self.cabina, *transformar(x, y, a, CABINA))
        cv.itemconfigure(self.cabina, outline=borde or E.oscurecer(P["acento"], 0.45),
                         width=2 if borde else 1)
        cv.coords(self.techo, *transformar(x, y, a, TECHO_CABINA))
        cv.coords(self.parabrisas, *transformar(x, y, a, PARABRISAS))
        for grupo, formas in ((self.faros, FAROS), (self.espejos, ESPEJOS),
                              (self.escapes, ESCAPES)):
            for item, forma in zip(grupo, formas):
                cv.coords(item, *transformar(x, y, a, forma))
        cv.coords(self.camara, *(transformar(x, y, a, CAMARA) if camara else (0, 0, 0, 0, 0, 0)))


class Fantasma:

    def __init__(self, cv, unidades):
        self.cv = cv
        self.cuerpos = [cv.create_polygon(0, 0, 0, 0, 0, 0, tags="camion", fill="", width=1)
                        for _ in range(unidades)]
        self.frente = cv.create_line(0, 0, 0, 0, tags="camion", width=2)
        self.color = None

    def ocultar(self):
        for item in self.cuerpos:
            self.cv.coords(item, 0, 0, 0, 0, 0, 0)
        self.cv.coords(self.frente, 0, 0, 0, 0)

    def actualizar(self, cam, color):
        cv = self.cv
        for item, esq in zip(self.cuerpos, cam.carrocerias()):
            cv.coords(item, *[c for x, y in esq for c in px(x, y)])
        cv.coords(self.frente, *transformar(cam.x, cam.y, cam.ang,
                                            ((_FR - 2.3, -_HW + 0.2), (_FR - 2.3, _HW - 0.2))))
        if color != self.color:
            self.color = color
            for item in self.cuerpos:
                cv.itemconfigure(item, outline=color)
            cv.itemconfigure(self.frente, fill=color)
