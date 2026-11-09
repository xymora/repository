import math
import struct
import zlib

import numpy as np

import config as C

E = C.ESCALA
ANGULOS = 16
OCEANO = {
    "dia": ("#1b4d8c", "#2a6cb3", "#8fc3f0"),
    "tormenta": ("#22344a", "#344d68", "#9fb2c8"),
    "noche": ("#08142b", "#11264a", "#5a7fb8"),
    "atardecer": ("#2d3f78", "#4a5a99", "#f0a070"),
}
LUZ = {"dia": 1.0, "tormenta": 0.8, "noche": 0.55, "atardecer": 0.85}


def rgb(color):
    return np.array([int(color[i:i + 2], 16) for i in (1, 3, 5)], np.float32)


def png(img):
    alto, ancho = img.shape[:2]
    crudo = b"".join(b"\x00" + img[y].tobytes() for y in range(alto))

    def bloque(tipo, datos):
        return (struct.pack(">I", len(datos)) + tipo + datos
                + struct.pack(">I", zlib.crc32(tipo + datos) & 0xFFFFFFFF))

    return (b"\x89PNG\r\n\x1a\n" + bloque(b"IHDR", struct.pack(">IIBBBBB", ancho, alto, 8, 6, 0, 0, 0))
            + bloque(b"IDAT", zlib.compress(crudo, 6)) + bloque(b"IEND", b""))


def ppm(img):
    alto, ancho = img.shape[:2]
    return f"P6 {ancho} {alto} 255\n".encode() + np.ascontiguousarray(np.clip(img, 0, 255), np.uint8).tobytes()


class Lienzo:
    def __init__(self, ancho, alto, angulo=0.0, ex=1.0, ss=3):
        self.w, self.h, self.ss = int(round(ancho * E)), int(round(alto * E)), ss
        py, px = np.mgrid[0:self.h * ss, 0:self.w * ss].astype(np.float32)
        lx = ((px + 0.5) / ss - self.w / 2) / E
        ly = ((py + 0.5) / ss - self.h / 2) / E
        c, s = math.cos(angulo), math.sin(angulo)
        self.u = (c * lx + s * ly) / max(ex, 1e-3)
        self.v = -s * lx + c * ly
        self.p = np.zeros((self.h * ss, self.w * ss, 3), np.float32)
        self.a = np.zeros((self.h * ss, self.w * ss), np.float32)

    def _pintar(self, mascara, color, alfa, sombreado, cx, cy, rx, ry):
        a = mascara.astype(np.float32) * alfa
        col = rgb(color) if isinstance(color, str) else np.asarray(color, np.float32)
        if sombreado:
            f = 1 + sombreado * (-(self.u - cx) / rx * 0.35 - (self.v - cy) / ry * 0.65)
            col = col[None, None, :] * np.clip(f, 0.4, 1.8)[..., None]
        self.p = self.p * (1 - a)[..., None] + col * a[..., None]
        self.a = self.a * (1 - a) + a

    def elipse(self, cx, cy, rx, ry, color, alfa=1.0, sombreado=0.0):
        m = ((self.u - cx) / rx) ** 2 + ((self.v - cy) / ry) ** 2 <= 1
        self._pintar(m, color, alfa, sombreado, cx, cy, rx, ry)

    def poligono(self, puntos, color, alfa=1.0, sombreado=0.0):
        u, v = self.u, self.v
        dentro = np.zeros(u.shape, bool)
        n = len(puntos)
        for i in range(n):
            x1, y1 = puntos[i]
            x2, y2 = puntos[(i + 1) % n]
            if y1 == y2:
                continue
            cruza = ((y1 > v) != (y2 > v)) & (u < (x2 - x1) * (v - y1) / (y2 - y1) + x1)
            dentro ^= cruza
        xs, ys = [p[0] for p in puntos], [p[1] for p in puntos]
        cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
        rx, ry = max((max(xs) - min(xs)) / 2, 1), max((max(ys) - min(ys)) / 2, 1)
        self._pintar(dentro, color, alfa, sombreado, cx, cy, rx, ry)

    def rect(self, x0, y0, x1, y1, color, alfa=1.0, sombreado=0.0):
        self.poligono([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], color, alfa, sombreado)

    def resultado(self, contorno="#11141a"):
        ss = self.ss
        p = self.p.reshape(self.h, ss, self.w, ss, 3).mean((1, 3))
        a = self.a.reshape(self.h, ss, self.w, ss).mean((1, 3))
        col = p / np.maximum(a, 1e-6)[..., None]
        if contorno:
            solido = a > 0.5
            dil = solido.copy()
            dil[1:] |= solido[:-1]
            dil[:-1] |= solido[1:]
            dil[:, 1:] |= solido[:, :-1]
            dil[:, :-1] |= solido[:, 1:]
            borde = dil & ~solido
            col[borde] = rgb(contorno)
            a = np.where(borde, np.maximum(a, 0.85), a)
        return np.dstack([np.clip(col, 0, 255), np.clip(a * 255, 0, 255)]).astype(np.uint8)


def sombra(img, alfa=0.33):
    s = np.zeros_like(img)
    s[..., 3] = (img[..., 3].astype(np.float32) * alfa).astype(np.uint8)
    return s


def blanco(img):
    b = img.copy()
    b[..., :3] = (b[..., :3].astype(np.float32) * 0.3 + 255 * 0.7).astype(np.uint8)
    return b


def jugador(fase=0, giro=0.0):
    ex = abs(math.cos(giro)) * 0.85 + 0.15 if giro else 1.0
    escala = 1 + 0.25 * math.sin(giro / 2) ** 2 if giro else 1.0
    panza = giro and math.cos(giro) < 0
    plata = "#8d97a8" if panza else "#c9d2df"
    acento = "#2c55b8" if panza else "#3f73e0"
    L = Lienzo(34 * escala, 30 * escala, 0.0, ex)
    k = escala
    L.poligono([(-16 * k, -2 * k), (16 * k, -2 * k), (14 * k, 3 * k), (-14 * k, 3 * k)], plata, sombreado=0.8)
    for x in (-6.5, 6.5):
        L.rect((x - 1.6) * k, -6 * k, (x + 1.6) * k, 11 * k, plata, sombreado=0.7)
        L.elipse(x * k, -6 * k, 2.6 * k, 5 * k, plata, sombreado=0.9)
        L.rect((x - 1.6) * k, -1 * k, (x + 1.6) * k, 1 * k, acento)
        L.elipse(x * k, -11.2 * k, 5 * k, 1.2 * k, "#d6dde8", alfa=0.35 + 0.15 * fase)
        if not fase:
            L.rect((x - 4.5) * k, -11.6 * k, (x + 4.5) * k, -10.8 * k, "#2a2f38", alfa=0.8)
        else:
            L.rect((x - 0.5) * k, -14 * k, (x + 0.5) * k, -8.5 * k, "#2a2f38", alfa=0.8)
    L.rect(-8 * k, 9 * k, 8 * k, 11.5 * k, plata, sombreado=0.6)
    L.elipse(0, -2 * k, 2.8 * k, 7 * k, plata, sombreado=1.0)
    L.elipse(0, -4 * k, 1.6 * k, 2.8 * k, "#7fc4ff", sombreado=1.2)
    L.elipse(-0.5 * k, -5 * k, 0.6 * k, 1 * k, "#ffffff", alfa=0.8)
    L.rect(-15 * k, -1.2 * k, -11 * k, 0.6 * k, acento)
    L.rect(11 * k, -1.2 * k, 15 * k, 0.6 * k, acento)
    return L.resultado()


def escolta():
    L = Lienzo(16, 14)
    L.poligono([(-7, -1), (7, -1), (6, 2), (-6, 2)], "#c9d2df", sombreado=0.8)
    L.elipse(0, 0, 1.6, 5.5, "#c9d2df", sombreado=1.0)
    L.elipse(0, -1.5, 0.9, 1.6, "#7fc4ff")
    L.rect(-3.5, 4, 3.5, 5.2, "#c9d2df")
    L.elipse(0, -5.8, 3, 0.8, "#d6dde8", alfa=0.4)
    return L.resultado()


def caza(angulo, color="#4f7a3a", panel="#3c5e2c"):
    L = Lienzo(22, 22, angulo + math.pi / 2)
    L.poligono([(-9, -0.5), (9, -0.5), (8, 2.5), (-8, 2.5)], color, sombreado=0.8)
    L.elipse(-8.5, 1, 1.2, 1.5, color)
    L.elipse(8.5, 1, 1.2, 1.5, color)
    L.rect(-9, 0.4, 9, 1.0, panel)
    L.poligono([(-3.5, 6), (3.5, 6), (3, 7.6), (-3, 7.6)], color, sombreado=0.6)
    L.elipse(0, 0.5, 1.9, 7.5, color, sombreado=1.0)
    L.elipse(0, -5.6, 1.9, 1.5, "#2b2b2b")
    L.elipse(0, -1, 1.1, 2, "#9fd2e8", sombreado=1.0)
    L.elipse(0, -7.8, 3.6, 0.8, "#d8d8d8", alfa=0.35)
    return L.resultado()


def bombardero(color="#77804e"):
    L = Lienzo(40, 32, math.pi)
    L.poligono([(-18, -2), (18, -2), (17, 3), (-17, 3)], color, sombreado=0.8)
    for x in (-8, 8):
        L.elipse(x, -3, 2.4, 6, color, sombreado=0.9)
        L.elipse(x, -9.4, 4.5, 1, "#d8d8d8", alfa=0.35)
    L.poligono([(-7, 11), (7, 11), (6, 13.5), (-6, 13.5)], color, sombreado=0.6)
    L.elipse(0, 1, 2.8, 13, color, sombreado=1.0)
    L.elipse(0, -9, 1.8, 3, "#9fd2e8", sombreado=1.1)
    L.rect(-18, 0, 18, 0.9, "#5b6238")
    return L.resultado()


def pesado(color="#6a7566"):
    L = Lienzo(64, 46, 0.0)
    L.poligono([(-30, -3), (30, -3), (27, 4), (-27, 4)], color, sombreado=0.8)
    for x in (-19, -9, 9, 19):
        L.elipse(x, -4, 2.6, 6.5, color, sombreado=0.9)
        L.elipse(x, -10.8, 4.6, 1, "#d8d8d8", alfa=0.35)
    L.poligono([(-11, 15), (11, 15), (9, 18.5), (-9, 18.5)], color, sombreado=0.6)
    L.elipse(0, 2, 3.8, 18, color, sombreado=1.0)
    L.elipse(0, -11, 2.2, 3.6, "#9fd2e8", sombreado=1.1)
    for x in (-24, 24):
        L.rect(x - 2.5, -1, x + 2.5, 1, "#c8b048")
    return L.resultado()


def jefe(color="#4d5564", franja="#b03a3a"):
    L = Lienzo(108, 68, math.pi)
    L.poligono([(-50, -4), (50, -4), (44, 8), (-44, 8)], color, sombreado=0.8)
    L.poligono([(-50, -4), (-44, 8), (-38, 8), (-46, -4)], franja)
    L.poligono([(50, -4), (44, 8), (38, 8), (46, -4)], franja)
    for x in (-34, -22, -10, 10, 22, 34):
        L.elipse(x, -6, 3.2, 8.5, color, sombreado=0.9)
        L.elipse(x, -15, 6, 1.2, "#d8d8d8", alfa=0.35)
    L.poligono([(-16, 22), (16, 22), (13, 27), (-13, 27)], color, sombreado=0.6)
    L.rect(-1.2, 16, 1.2, 30, color)
    L.elipse(0, 4, 6, 27, color, sombreado=1.0)
    L.rect(-6, 10, 6, 12, franja)
    L.elipse(0, -16, 3.4, 5, "#9fd2e8", sombreado=1.2)
    return L.resultado()


def torreta(angulo):
    L = Lienzo(18, 18, angulo + math.pi / 2)
    L.rect(-1.1, -8, 1.1, 0, "#2b2f36")
    L.elipse(0, 0, 4.6, 4.6, "#6b7383", sombreado=1.2)
    L.elipse(-1.2, -1.4, 1.4, 1.2, "#e0e6ef", alfa=0.6)
    return L.resultado()


def bala_jugador():
    L = Lienzo(6, 12)
    L.elipse(0, 0, 2.6, 5.6, "#ffcf4a", alfa=0.35)
    L.elipse(0, 0, 1.3, 4.2, "#fff2a8")
    return L.resultado(None)


def bala_enemiga():
    L = Lienzo(10, 10)
    L.elipse(0, 0, 4.4, 4.4, "#ff6a3a", alfa=0.35)
    L.elipse(0, 0, 2.8, 2.8, "#ff7b4a")
    L.elipse(-0.4, -0.4, 1.3, 1.3, "#fff3d0")
    return L.resultado(None)


_LETRAS = {
    "P": ("111", "101", "111", "100", "100"),
    "O": ("111", "101", "101", "101", "111"),
    "W": ("101", "101", "111", "111", "101"),
}


def pow_(color, brillo):
    L = Lienzo(18, 18)
    L.elipse(0, 0, 8.5, 8.5, "#ffffff", alfa=0.25 + 0.25 * brillo)
    L.elipse(0, 0, 7, 7, color, sombreado=1.0)
    img = L.resultado()
    paso = E
    x0 = img.shape[1] // 2 - 6 * paso
    y0 = img.shape[0] // 2 - 3 * paso
    for k, letra in enumerate("POW"):
        for f, fila in enumerate(_LETRAS[letra]):
            for c, bit in enumerate(fila):
                if bit == "1":
                    y, x = y0 + f * paso + paso // 2, x0 + k * 4 * paso + c * paso + paso // 2
                    img[y:y + paso, x:x + paso] = (255, 255, 255, 255)
    return img


def explosion(radio, n, semilla=0):
    rng = np.random.default_rng(semilla)
    lado = int(radio * 2 * E)
    yy, xx = np.mgrid[0:lado, 0:lado].astype(np.float32)
    d = np.hypot(xx - lado / 2, yy - lado / 2) / (lado / 2)
    ruido = _ruido(lado, lado, 2.0, rng) * 0.6
    cuadros = []
    for k in range(n):
        t = (k + 1) / n
        r = 0.35 + 0.65 * t ** 0.6
        borde = d / r + ruido * 0.25
        cuerpo = np.clip(1 - borde, 0, 1)
        calor = np.clip(1 - t * 1.3, 0, 1)
        fuego = np.array([255, 230, 120], np.float32) * calor + np.array([255, 110, 40], np.float32) * (1 - calor)
        humo = np.array([90, 88, 92], np.float32)
        mezcla = np.clip(t * 1.4 - 0.3, 0, 1)
        col = fuego * (1 - mezcla) + humo * mezcla
        col = col[None, None, :] * (0.75 + 0.5 * np.clip(1 - d / r, 0, 1))[..., None]
        alfa = np.clip(cuerpo * 3, 0, 1) * (1 - t ** 3) * 255
        cuadros.append(np.dstack([np.clip(col, 0, 255), alfa]).astype(np.uint8))
    return cuadros


def _ruido(alto, ancho, escala, rng, periodico=False):
    blanco_ = rng.standard_normal((alto, ancho))
    ky = np.fft.fftfreq(alto)[:, None]
    kx = np.fft.fftfreq(ancho)[None, :]
    filtro = np.exp(-(kx ** 2 + ky ** 2) * (escala * 10) ** 2)
    r = np.real(np.fft.ifft2(np.fft.fft2(blanco_) * filtro))
    return (r - r.mean()) / (r.std() + 1e-9)


def oceano(tema, semilla=5):
    rng = np.random.default_rng(semilla)
    ancho, alto = C.ANCHO_VISTA * E, C.ALTO_VISTA * E
    hondo, medio, espuma = (rgb(c) for c in OCEANO[tema])
    n1 = _ruido(alto, ancho, 9.0, rng)
    n2 = _ruido(alto, ancho, 2.6, rng)
    t = np.clip(0.5 + 0.22 * n1, 0, 1)[..., None]
    img = hondo * (1 - t) + medio * t
    yy, xx = np.mgrid[0:alto, 0:ancho].astype(np.float32)
    ondas = np.sin(yy * 2 * math.pi * 16 / alto + n2 * 2.2 + np.sin(xx / 53) * 1.4)
    cresta = np.clip((ondas - 0.9) * 6, 0, 1) * np.clip(0.3 + 0.35 * n1, 0, 1)
    img = img * (1 - cresta[..., None] * 0.35) + espuma * cresta[..., None] * 0.35
    img = img * (1 + 0.05 * np.sin(yy * 2 * math.pi * 40 / alto + n1))[..., None]
    return np.clip(img * LUZ[tema] ** 0.5, 0, 255)


def isla(variante, pista, tema, semilla=0):
    rng = np.random.default_rng(100 + variante * 7 + semilla)
    tam = ((150, 110), (110, 90), (190, 120), (90, 120))[variante]
    ancho, alto = int(tam[0] * E), int(tam[1] * E)
    yy, xx = np.mgrid[0:alto, 0:ancho].astype(np.float32)
    r = np.hypot((xx - ancho / 2) / (ancho * 0.36), (yy - alto / 2) / (alto * 0.36))
    n = _ruido(alto, ancho, 7.0, rng)
    nivel = 1 - r + 0.18 * n
    tierra = nivel > 0.2
    arena = (nivel > 0.12) & ~tierra
    bajo = (nivel > -0.08) & ~tierra & ~arena
    img = np.zeros((alto, ancho, 3), np.float32)
    alfa = np.zeros((alto, ancho), np.float32)
    img[bajo] = rgb("#4fb8c8")
    alfa[bajo] = np.clip((nivel[bajo] + 0.08) / 0.2, 0, 1) * 0.55
    img[arena] = rgb("#e2d29a")
    alfa[arena] = 1
    n2 = _ruido(alto, ancho, 1.4, rng)
    verde = rgb("#2f7a3a") * (1 - np.clip(0.5 + 0.25 * n2, 0, 1)[..., None]) + rgb("#4f9a3f") * np.clip(
        0.5 + 0.25 * n2, 0, 1)[..., None]
    altura = np.clip((nivel - 0.2) * 2.5, 0, 1)
    verde = verde * (0.8 + 0.35 * altura)[..., None]
    img[tierra] = verde[tierra]
    alfa[tierra] = 1
    for _ in range(int(ancho * alto / 1400)):
        y, x = int(rng.integers(alto)), int(rng.integers(ancho))
        if tierra[y, x] and nivel[y, x] < 0.5:
            m = np.hypot(xx - x, yy - y) < 2.4 * E
            img[m & tierra] = rgb("#1d5527")
    if pista:
        y0 = alto // 2 - 6 * E
        franja = (yy > y0) & (yy < y0 + 12 * E) & (xx > ancho * 0.22) & (xx < ancho * 0.78) & tierra
        img[franja] = rgb("#8b8a82")
        linea = franja & (np.abs(yy - (y0 + 6 * E)) < 1) & ((xx // (6 * E)) % 2 == 0)
        img[linea] = rgb("#f2f2ea")
    img *= LUZ[tema]
    return np.dstack([np.clip(img, 0, 255), alfa * 255]).astype(np.uint8)


def nube(variante, tema, semilla=0):
    rng = np.random.default_rng(300 + variante + semilla)
    ancho, alto = int((110, 80, 140)[variante] * E), int((60, 46, 70)[variante] * E)
    yy, xx = np.mgrid[0:alto, 0:ancho].astype(np.float32)
    r = np.hypot((xx - ancho / 2) / (ancho * 0.42), (yy - alto / 2) / (alto * 0.42))
    n = _ruido(alto, ancho, 5.0, rng)
    fino = _ruido(alto, ancho, 1.5, rng)
    d = np.clip((1 - r + 0.3 * n + 0.06 * fino) * 1.6, 0, 1) ** 1.3
    borde = np.minimum(np.minimum(xx, ancho - 1 - xx) / (ancho * 0.12), np.minimum(yy, alto - 1 - yy) / (alto * 0.18))
    d = d * np.clip(borde, 0, 1)
    base = rgb("#5d6878") if tema == "tormenta" else rgb("#f4f7fb")
    sombra_ = np.clip((yy / alto - 0.4) * 1.2, 0, 0.35)
    col = base[None, None, :] * (1 - sombra_)[..., None] * LUZ[tema]
    alfa = d * (0.62 if tema != "tormenta" else 0.7) * 255
    return np.dstack([np.clip(col, 0, 255), alfa]).astype(np.uint8)


def portaaviones():
    L = Lienzo(46, 190)
    L.poligono([(-14, -88), (14, -88), (18, -60), (18, 80), (10, 94), (-10, 94), (-18, 80), (-18, -60)],
               "#5f6670", sombreado=0.5)
    L.poligono([(-12, -84), (12, -84), (15, -58), (15, 86), (-15, 86), (-15, -58)], "#7b7266")
    for y in range(-80, 84, 12):
        L.rect(-0.6, y, 0.6, y + 6, "#f0eadc")
    L.rect(-15, 70, 15, 71, "#f0eadc")
    L.rect(17, -10, 23, 20, "#4b525c", sombreado=0.8)
    L.rect(18, -2, 22, 4, "#2b2f36")
    return L.resultado()


def icono_vida():
    L = Lienzo(14, 12)
    L.poligono([(-6.5, -1), (6.5, -1), (6, 1.5), (-6, 1.5)], "#c9d2df")
    for x in (-2.8, 2.8):
        L.rect(x - 0.8, -3, x + 0.8, 4.5, "#c9d2df")
    L.elipse(0, -0.5, 1.3, 3.5, "#c9d2df")
    L.rect(-3.5, 4, 3.5, 5, "#c9d2df")
    return L.resultado()


def icono_rizo():
    L = Lienzo(12, 12)
    L.elipse(0, 0, 5, 5, "#f5b400", sombreado=1.0)
    L.elipse(0, 0, 3.2, 3.2, "#11141a")
    L.elipse(0, 0, 2.4, 2.4, "#f5b400")
    L.rect(-0.8, -6, 5.5, 0, "#11141a")
    return L.resultado()


def generar():
    s = {}
    for f in (0, 1):
        s[f"jugador{f}"] = jugador(f)
    for k in range(8):
        s[f"rizo{k}"] = jugador(k % 2, 2 * math.pi * (k + 0.5) / 8)
    s["escolta"] = escolta()
    fantasma = s["jugador0"].copy()
    fantasma[..., :3] = (fantasma[..., :3].astype(np.float32) * 0.55 + np.array([120, 200, 255]) * 0.45).astype(np.uint8)
    fantasma[..., 3] = (fantasma[..., 3].astype(np.float32) * 0.42).astype(np.uint8)
    s["fantasma"] = fantasma
    for k in range(ANGULOS):
        a = 2 * math.pi * k / ANGULOS
        s[f"caza{k}"] = caza(a)
        s[f"rojo{k}"] = caza(a, "#c8402f", "#9b2c22")
        s[f"torreta{k}"] = torreta(a)
    s["bombardero"] = bombardero()
    s["pesado"] = pesado()
    s["jefe"] = jefe()
    for nombre in ("bombardero", "pesado", "jefe"):
        s[nombre + "_golpe"] = blanco(s[nombre])
    for nombre in list(s):
        if nombre.startswith(("jugador", "rizo", "caza", "rojo", "bombardero", "pesado", "jefe", "escolta")) \
                and not nombre.endswith("_golpe"):
            s["sombra_" + nombre] = sombra(s[nombre])
    s["bala_j"] = bala_jugador()
    s["bala_e"] = bala_enemiga()
    for letra, color in (("A", "#d8402f"), ("E", "#2fa84f"), ("R", "#d8a320")):
        for b in (0, 1):
            s[f"pow_{letra}{b}"] = pow_(color, b)
    for k, img in enumerate(explosion(12, 6, 1)):
        s[f"chica{k}"] = img
    for k, img in enumerate(explosion(26, 8, 2)):
        s[f"grande{k}"] = img
    s["portaaviones"] = portaaviones()
    s["sombra_portaaviones"] = sombra(s["portaaviones"], 0.25)
    s["vida"] = icono_vida()
    s["icono_rizo"] = icono_rizo()
    return s


def escenario(tema):
    s = {"oceano": oceano(tema)}
    for v in range(4):
        for pista in (False, True):
            s[f"isla{v}{int(pista)}"] = isla(v, pista, tema)
    for v in range(3):
        s[f"nube{v}"] = nube(v, tema)
    return s
