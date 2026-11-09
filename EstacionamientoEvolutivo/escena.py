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
ASFALTO = (50, 53, 59)
PINTURA = (226, 228, 222)
COLORES_ESTACIONADOS = ["#c0392b", "#2d5d9f", "#d9dde3", "#3a3f47", "#7d8a96", "#1f6f5c",
                        "#8e5a2b", "#b8b2a7", "#5b3f8c"]
HL, HW = C.AUTO_LARGO / 2, C.AUTO_ANCHO / 2
EJE = C.DIST_EJES / 2


def px(x, y):
    return MARGEN + x * ESC, MARGEN + y * ESC


def a_metros(sx, sy):
    return (sx - MARGEN) / ESC, (sy - MARGEN) / ESC


def fondo():
    al = random.Random(7)
    p = E.Pintor(ANCHO, ALTO)
    p.textura(0, 0, ANCHO, ALTO, (52, 84, 52), 26, grano=0.9, escala=10, semilla=1, manchas=0.8)
    x0, y0 = px(0, 0)
    x1, y1 = px(C.LOTE_ANCHO, C.LOTE_ALTO)
    p.rect(x0 - 9, y0 - 9, x1 + 9, y1 + 9, (0, 0, 0), alfa=0.45, suave=6)
    p.rect(x0 - 7, y0 - 7, x1 + 7, y1 + 7, (168, 168, 160), radio=3)
    p.rect(x0 - 2, y0 - 2, x1 + 2, y1 + 2, (120, 120, 116))
    p.textura(x0, y0, x1, y1, ASFALTO, 9, grano=1.1, escala=40, semilla=2, manchas=0.7)

    for _ in range(30):
        x, y = al.uniform(x0, x1), al.uniform(y0 + 6.2 * ESC, y1)
        p.circulo(x, y, al.uniform(4, 16), (30, 32, 36), alfa=al.uniform(0.12, 0.25),
                  suave=al.uniform(6, 12))
    lista = cajones()
    for cx0, _, cx1, cy1 in lista:
        x, y = px((cx0 + cx1) / 2, cy1 - 2.5)
        p.circulo(x + al.uniform(-6, 6), y, al.uniform(10, 18), (28, 29, 32), alfa=0.3,
                  suave=14)
    for k in range(5):
        yy = px(0, 7.6 + k * 0.9 + al.uniform(-0.2, 0.2))[1]
        p.linea(x0 + 40, yy, x1 - 40, yy + al.uniform(-8, 8), 5, (38, 40, 44), alfa=0.18,
                suave=4)

    g = max(2.0, C.LINEA_ANCHO * ESC)
    for cx0, cy0, cx1, cy1 in lista:
        for xx in (cx0, cx1):
            xa, ya = px(xx, cy0)
            _, yb = px(xx, cy1)
            p.rect(xa - g / 2, ya, xa + g / 2, yb, PINTURA, alfa=0.92)
    for _ in range(700):
        cx0, cy0, cx1, cy1 = lista[al.randrange(len(lista))]
        xa, _ = px(al.choice((cx0, cx1)), 0)
        _, yy = px(0, al.uniform(cy0, cy1))
        p.circulo(xa + al.uniform(-g / 2, g / 2), yy, al.uniform(0.4, 1.0), ASFALTO,
                  alfa=al.uniform(0.2, 0.5), suave=1)

    for cx0, _, cx1, _ in lista:
        xa, ya = px(cx0 + 0.5, 0.55)
        xb, yb = px(cx1 - 0.5, 0.75)
        p.rect(xa, ya + 3, xb, yb + 3, (0, 0, 0), radio=3, alfa=0.4, suave=3)
        p.rect(xa, ya, xb, yb, (196, 190, 170), radio=3)
        p.rect(xa, ya, xb, ya + 2, (226, 220, 200), radio=1, alfa=0.7)

    for xm in (C.LOTE_ANCHO / 2 - 1.6, C.LOTE_ANCHO - 4.6):
        xa, ya = px(xm, 11.6)
        xb, _ = px(xm + 3.2, 11.6)
        p.rect(xa, ya - 0.16 * ESC, xb - 1.2 * ESC, ya + 0.16 * ESC, PINTURA, alfa=0.45)
        p.poligono([(xb - 1.25 * ESC, ya - 0.6 * ESC), (xb, ya), (xb - 1.25 * ESC, ya + 0.6 * ESC)],
                   PINTURA, alfa=0.45)

    for x, y, r in ((MARGEN * 0.5, MARGEN * 0.6, 20), (ANCHO - MARGEN * 0.4, MARGEN * 0.5, 24),
                    (MARGEN * 0.4, ALTO - MARGEN * 0.5, 22),
                    (ANCHO - MARGEN * 0.5, ALTO - MARGEN * 0.4, 18)):
        p.circulo(x + 6, y + 8, r, (0, 0, 0), alfa=0.45, suave=10)
        p.circulo(x, y, r, (40, 92, 46))
        p.circulo(x - r * 0.25, y - r * 0.25, r * 0.65, (66, 128, 62), alfa=0.8, suave=r * 0.5)
        p.circulo(x - r * 0.35, y - r * 0.4, r * 0.25, (110, 170, 90), alfa=0.6, suave=r * 0.3)
    return p.foto()


def sprite_auto(color, nariz_arriba):
    s = ESC
    w, h = int((C.AUTO_ANCHO + 1.0) * s), int((C.AUTO_LARGO + 1.0) * s)
    p = E.Pintor(w, h, transparente=True)
    cx, cy = w / 2, h / 2
    d = -1 if nariz_arriba else 1

    def Y(u):
        return cy + d * u * s

    def caja(u0, u1, v0, v1, *a, **k):
        ya, yb = sorted((Y(u0), Y(u1)))
        p.rect(cx + v0 * s, ya, cx + v1 * s, yb, *a, **k)

    def poli(puntos, *a, **k):
        p.poligono([(cx + v * s, Y(u)) for u, v in puntos], *a, **k)

    pintura = E.rgb(color)
    oscuro = E.rgb(E.oscurecer(color, 0.35))
    claro = E.rgb(E.aclarar(color, 0.18))
    p.rect(cx - (HW + 0.06) * s + 4, cy - (HL + 0.06) * s + 6, cx + (HW + 0.06) * s + 4,
           cy + (HL + 0.06) * s + 6, (0, 0, 0), radio=0.5 * s, alfa=0.55, suave=0.4 * s)
    for u in (EJE, -EJE):
        for v in (-HW - 0.04, HW - 0.22):
            caja(u - 0.36, u + 0.36, v, v + 0.26, (18, 18, 20), radio=0.08 * s)
    caja(-HL, HL, -HW, HW, oscuro, radio=0.45 * s)
    caja(-HL + 0.05, HL - 0.05, -HW + 0.06, HW - 0.06, pintura, radio=0.42 * s, suave=2.5)
    caja(-HL + 0.3, HL - 0.3, -HW + 0.45, HW - 0.45, claro, radio=0.3 * s, alfa=0.35,
         suave=0.25 * s)
    vidrio = (34, 42, 54)
    poli([(1.12, -0.74), (1.12, 0.74), (0.48, 0.82), (0.48, -0.82)], vidrio)
    poli([(-1.22, -0.76), (-1.22, 0.76), (-1.62, 0.68), (-1.62, -0.68)], vidrio)
    caja(-1.2, 0.46, -0.8, 0.8, oscuro, radio=0.12 * s)
    caja(-1.12, 0.38, -0.7, 0.7, claro, radio=0.12 * s, suave=1.5)
    p.linea(cx - 0.55 * s, Y(1.0), cx + 0.2 * s, Y(0.6), 2.2, (255, 255, 255), alfa=0.18)
    for v in (-HW - 0.12, HW - 0.02):
        caja(0.42, 0.58, v, v + 0.14, oscuro, radio=0.05 * s)
    for v in (-HW + 0.12, HW - 0.5):
        caja(HL - 0.16, HL - 0.03, v, v + 0.38, (236, 238, 226), radio=0.05 * s)
        caja(-HL + 0.03, -HL + 0.16, v, v + 0.38, (150, 24, 28), radio=0.05 * s)
    return p.foto()


def sprite_objetivo(modo):
    s = ESC
    w, h = int(C.CAJON_ANCHO * s), int(C.CAJON_FONDO * s)
    p = E.Pintor(w, h, (56, 196, 140), transparente=True)
    g = C.LINEA_ANCHO * s
    p.rect(g, 0, w - g, h, (56, 196, 140), alfa=0.14)
    cx = w / 2
    cola, punta = (4.2 * s, 1.3 * s) if modo == "frente" else (1.5 * s, 4.4 * s)
    d = 1 if punta > cola else -1
    base = punta - d * 1.2 * s
    p.rect(cx - 0.16 * s, min(cola, base), cx + 0.16 * s, max(cola, base), PINTURA, alfa=0.6)
    p.poligono([(cx - 0.7 * s, base), (cx, punta), (cx + 0.7 * s, base)], PINTURA, alfa=0.6)
    return p.foto()


def contorno(hl, hw, radio, pasos=4):
    puntos = []
    for (sx, sy), a0 in (((1, -1), -90), ((1, 1), 0), ((-1, 1), 90), ((-1, -1), 180)):
        cx, cy = sx * (hl - radio), sy * (hw - radio)
        for k in range(pasos + 1):
            a = math.radians(a0 + 90 * k / pasos)
            puntos.append((cx + radio * math.cos(a), cy + radio * math.sin(a)))
    return puntos


CUERPO = contorno(HL, HW, 0.42)
CUERPO_FANTASMA = contorno(HL, HW, 0.4, 2)
SOMBRA = contorno(HL + 0.06, HW + 0.06, 0.5)
TECHO = [(x - 0.37, y) for x, y in contorno(0.83, 0.74, 0.14, 2)]
PARABRISAS = ((1.12, -0.74), (1.12, 0.74), (0.48, 0.82), (0.48, -0.82))
MEDALLON = ((-1.22, -0.76), (-1.22, 0.76), (-1.62, 0.68), (-1.62, -0.68))
RUEDA = ((0.36, -0.13), (0.36, 0.13), (-0.36, 0.13), (-0.36, -0.13))
FAROS = [((HL - 0.03, y0), (HL - 0.03, y0 + 0.38), (HL - 0.16, y0 + 0.38), (HL - 0.16, y0))
         for y0 in (-HW + 0.12, HW - 0.5)]
CALAVERAS = [((-HL + 0.16, y0), (-HL + 0.16, y0 + 0.38), (-HL + 0.03, y0 + 0.38),
              (-HL + 0.03, y0)) for y0 in (-HW + 0.12, HW - 0.5)]
ESPEJOS = [((0.58, y0), (0.58, y0 + 0.14), (0.42, y0 + 0.14), (0.42, y0))
           for y0 in (-HW - 0.12, HW - 0.02)]
DESTELLO = ((0.98, -0.55), (1.05, -0.42), (0.62, 0.25), (0.55, 0.12))
CAMARA = ((C.CAMARA["x"] + 0.1, C.CAMARA["y"] - 0.06), (C.CAMARA["x"] + 0.1, C.CAMARA["y"] + 0.1),
          (C.CAMARA["x"] - 0.1, C.CAMARA["y"] + 0.1), (C.CAMARA["x"] - 0.1, C.CAMARA["y"] - 0.06))


def transformar(x, y, ang, puntos, dx=0.0, dy=0.0):
    c, s = math.cos(ang), math.sin(ang)
    return [v for lx, ly in puntos
            for v in px(x + lx * c - ly * s + dx, y + lx * s + ly * c + dy)]


def _rueda(x, y, ang, u, v, giro):
    c, s = math.cos(giro), math.sin(giro)
    pts = [(u + a * c - b * s, v + a * s + b * c) for a, b in RUEDA]
    return transformar(x, y, ang, pts)


class Lider:

    def __init__(self, cv, color=P["acento"]):
        self.cv = cv
        self.color = color
        nuevo = lambda **k: cv.create_polygon(0, 0, 0, 0, 0, 0, tags="auto", **k)
        self.sombra = nuevo(fill="#202226", outline="")
        self.ruedas = [nuevo(fill="#0c0d0f", outline="") for _ in range(4)]
        self.cuerpo = nuevo(fill=color, outline=E.oscurecer(color, 0.45), width=2)
        self.techo = nuevo(fill=E.aclarar(color, 0.22), outline=E.oscurecer(color, 0.2))
        self.cristales = [nuevo(fill="#1d2532", outline="") for _ in range(2)]
        self.destello = nuevo(fill="#36435a", outline="")
        self.espejos = [nuevo(fill=E.oscurecer(color, 0.3), outline="") for _ in range(2)]
        self.faros = [nuevo(fill="#f4f1dc", outline="") for _ in range(2)]
        self.calaveras = [nuevo(fill="#8c1a1f", outline="") for _ in range(2)]
        self.camara = nuevo(fill=P["cian"], outline="")

    def actualizar(self, auto, freno, borde=None, camara=False):
        cv, x, y, a = self.cv, auto.x, auto.y, auto.ang
        cv.coords(self.sombra, *transformar(x, y, a, SOMBRA, 0.14, 0.2))
        for item, (u, v) in zip(self.ruedas, ((EJE, -HW + 0.1), (EJE, HW - 0.1),
                                              (-EJE, -HW + 0.1), (-EJE, HW - 0.1))):
            cv.coords(item, *_rueda(x, y, a, u, v, auto.giro if u > 0 else 0.0))
        cv.coords(self.cuerpo, *transformar(x, y, a, CUERPO))
        cv.itemconfigure(self.cuerpo, outline=borde or E.oscurecer(self.color, 0.45))
        cv.coords(self.techo, *transformar(x, y, a, TECHO))
        cv.coords(self.cristales[0], *transformar(x, y, a, PARABRISAS))
        cv.coords(self.cristales[1], *transformar(x, y, a, MEDALLON))
        cv.coords(self.destello, *transformar(x, y, a, DESTELLO))
        for item, forma in zip(self.espejos, ESPEJOS):
            cv.coords(item, *transformar(x, y, a, forma))
        for item, forma in zip(self.faros, FAROS):
            cv.coords(item, *transformar(x, y, a, forma))
        luz = "#f2f4f8" if auto.marcha < 0 else ("#ff2b3a" if freno > 0.05 else "#8c1a1f")
        for item, forma in zip(self.calaveras, CALAVERAS):
            cv.coords(item, *transformar(x, y, a, forma))
            cv.itemconfigure(item, fill=luz)
        cv.coords(self.camara, *(transformar(x, y, a, CAMARA) if camara else (0, 0, 0, 0, 0, 0)))


class Fantasma:

    def __init__(self, cv):
        self.cv = cv
        self.cuerpo = cv.create_polygon(0, 0, 0, 0, 0, 0, tags="auto", fill="", width=1)
        self.frente = cv.create_line(0, 0, 0, 0, tags="auto", width=2)
        self.color = None

    def ocultar(self):
        self.cv.coords(self.cuerpo, 0, 0, 0, 0, 0, 0)
        self.cv.coords(self.frente, 0, 0, 0, 0)

    def actualizar(self, auto, color):
        cv, x, y, a = self.cv, auto.x, auto.y, auto.ang
        cv.coords(self.cuerpo, *transformar(x, y, a, CUERPO_FANTASMA))
        cv.coords(self.frente, *transformar(x, y, a, ((0.95, -0.7), (0.95, 0.7))))
        if color != self.color:
            self.color = color
            cv.itemconfigure(self.cuerpo, outline=color)
            cv.itemconfigure(self.frente, fill=color)
