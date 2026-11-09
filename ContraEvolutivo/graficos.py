import math
import struct
import zlib

import numpy as np

import config as C
from etapas import AGUA, PINCHO, PLATAFORMA, SOLIDO

T = C.TILE


def color(hexa, alfa=255):
    return (int(hexa[1:3], 16), int(hexa[3:5], 16), int(hexa[5:7], 16), alfa)


def mezclar(c1, c2, t):
    a, b = color(c1), color(c2)
    return "#%02x%02x%02x" % tuple(round(x + (y - x) * t) for x, y in zip(a[:3], b[:3]))


class Lienzo:
    def __init__(self, ancho, alto):
        self.a = np.zeros((alto, ancho, 4), dtype=np.uint8)

    @property
    def ancho(self):
        return self.a.shape[1]

    @property
    def alto(self):
        return self.a.shape[0]

    def rect(self, x, y, w, h, c):
        x0, y0 = max(int(x), 0), max(int(y), 0)
        x1, y1 = min(int(x + w), self.ancho), min(int(y + h), self.alto)
        if x1 > x0 and y1 > y0:
            self.a[y0:y1, x0:x1] = color(c) if isinstance(c, str) else c

    def px(self, x, y, c):
        self.rect(x, y, 1, 1, c)

    def linea(self, x0, y0, x1, y1, c, grosor=1):
        pasos = int(max(abs(x1 - x0), abs(y1 - y0))) + 1
        for k in range(pasos + 1):
            t = k / max(pasos, 1)
            x, y = x0 + (x1 - x0) * t, y0 + (y1 - y0) * t
            self.rect(round(x - (grosor - 1) / 2), round(y - (grosor - 1) / 2), grosor, grosor, c)

    def ovalo(self, cx, cy, rx, ry, c):
        yy, xx = np.mgrid[0:self.alto, 0:self.ancho]
        mascara = ((xx + 0.5 - cx) / max(rx, 0.1)) ** 2 + ((yy + 0.5 - cy) / max(ry, 0.1)) ** 2 <= 1
        self.a[mascara] = color(c)

    def contorno(self, c="#0b0d12"):
        lleno = self.a[..., 3] > 0
        borde = np.zeros_like(lleno)
        borde[1:] |= lleno[:-1]
        borde[:-1] |= lleno[1:]
        borde[:, 1:] |= lleno[:, :-1]
        borde[:, :-1] |= lleno[:, 1:]
        self.a[borde & ~lleno] = color(c)
        return self

    def imagen(self):
        return self.a.copy()


def espejo(img):
    return img[:, ::-1].copy()


def escalar(img, k):
    return np.repeat(np.repeat(img, k, axis=0), k, axis=1)


def png(img):
    alto, ancho = img.shape[:2]
    crudo = b"".join(b"\x00" + img[y].tobytes() for y in range(alto))

    def bloque(tipo, datos):
        return (struct.pack(">I", len(datos)) + tipo + datos
                + struct.pack(">I", zlib.crc32(tipo + datos) & 0xFFFFFFFF))

    return (b"\x89PNG\r\n\x1a\n" + bloque(b"IHDR", struct.pack(">IIBBBBB", ancho, alto, 8, 6, 0, 0, 0))
            + bloque(b"IDAT", zlib.compress(crudo, 3)) + bloque(b"IEND", b""))


def ppm(rgb):
    alto, ancho = rgb.shape[:2]
    return f"P6 {ancho} {alto} 255\n".encode() + np.ascontiguousarray(rgb, dtype=np.uint8).tobytes()


FUENTE = {
    "M": ("101", "111", "101", "101", "101"),
    "S": ("111", "100", "111", "001", "111"),
    "L": ("100", "100", "100", "100", "111"),
    "F": ("111", "100", "110", "100", "100"),
    "R": ("110", "101", "110", "101", "101"),
    "B": ("110", "101", "110", "101", "110"),
}

PALETAS = {
    "j1": dict(piel="#f0b07c", sombra="#c27e52", pelo="#4a2f1a", cinta="#e23b3b", torso=None,
               pantalon="#2e5bd6", pantalon2="#1d3c96", bota="#3a2a1c", arma="#b8c0c8", casco=None),
    "j2": dict(piel="#f0b07c", sombra="#c27e52", pelo="#2a1a10", cinta="#3b7be2", torso=None,
               pantalon="#d6402e", pantalon2="#93261b", bota="#3a2a1c", arma="#b8c0c8", casco=None),
    "soldado": dict(piel="#e0a070", sombra="#b07850", pelo="#3a2a1a", cinta=None, torso="#7d8a6a",
                    pantalon="#5f6b4e", pantalon2="#46503a", bota="#2b2b2b", arma="#6c7480", casco="#55603f"),
    "tirador": dict(piel="#e0a070", sombra="#b07850", pelo="#3a2a1a", cinta=None, torso="#8a6a4a",
                    pantalon="#6b4e35", pantalon2="#4d3826", bota="#2b2b2b", arma="#9aa3ad", casco="#5a4430"),
    "nieve": dict(piel="#e0a070", sombra="#b07850", pelo="#3a2a1a", cinta=None, torso="#dfe7ef",
                  pantalon="#b8c4d0", pantalon2="#8d9aa8", bota="#4a4f58", arma="#6c7480", casco="#e9eef4"),
}
PIERNAS = {
    "quieto": ((-3, 0, 0), (2, 0, 0)),
    "c0": ((-6, 0, 1), (4, -3, 0)),
    "c1": ((-2, -2, 0), (0, 0, 1)),
    "c2": ((3, -3, 0), (-5, 0, 1)),
    "c3": ((0, 0, 1), (-2, -2, 0)),
}
APUNTES = ("h", "arriba", "diag_arr", "diag_ab")


def comando(pal, piernas="quieto", apunte="h", con_arma=True):
    L = Lienzo(30, 40)
    cx, oy = 13, 6
    for dx, levanta, atras in PIERNAS[piernas]:
        tono = pal["pantalon2"] if atras else pal["pantalon"]
        L.rect(cx + dx, oy + 21, 4, 8 + levanta, tono)
        L.rect(cx + dx - (1 if dx < 0 else 0), oy + 29 + levanta, 5, 4, pal["bota"])
    if pal["torso"]:
        L.rect(cx - 4, oy + 11, 9, 10, pal["torso"])
        L.rect(cx - 4, oy + 11, 2, 10, mezclar(pal["torso"], "#000000", 0.25))
    else:
        L.rect(cx - 4, oy + 11, 9, 10, pal["piel"])
        L.rect(cx - 4, oy + 11, 2, 10, pal["sombra"])
        L.rect(cx - 1, oy + 14, 3, 1, pal["sombra"])
        L.rect(cx - 1, oy + 17, 3, 1, pal["sombra"])
    L.rect(cx - 4, oy + 19, 9, 2, "#2b2b2b")
    L.px(cx, oy + 19, "#d8b440")
    L.rect(cx - 1, oy + 10, 3, 1, pal["sombra"])
    L.rect(cx - 3, oy + 3, 7, 7, pal["piel"])
    L.rect(cx - 3, oy + 2, 7, 2, pal["pelo"])
    L.rect(cx - 3, oy + 3, 2, 4, pal["pelo"])
    L.px(cx + 2, oy + 6, "#1a1a1a")
    if pal["casco"]:
        L.rect(cx - 4, oy + 1, 9, 4, pal["casco"])
        L.rect(cx - 5, oy + 4, 11, 1, mezclar(pal["casco"], "#000000", 0.3))
    if pal["cinta"]:
        L.rect(cx - 3, oy + 4, 7, 2, pal["cinta"])
        L.rect(cx - 7, oy + 5, 4, 1, pal["cinta"])
        L.rect(cx - 8, oy + 6, 3, 1, pal["cinta"])
    hombro = (cx + 3, oy + 13)
    oscuro = mezclar(pal["arma"], "#000000", 0.45)
    brazo = pal["torso"] or pal["piel"]
    if apunte == "h":
        L.rect(cx + 1, oy + 12, 7, 3, brazo)
        if con_arma:
            L.rect(cx + 5, oy + 11, 12, 3, pal["arma"])
            L.rect(cx + 5, oy + 13, 4, 2, oscuro)
            L.px(cx + 16, oy + 11, oscuro)
    elif apunte == "arriba":
        L.rect(cx + 2, oy + 4, 3, 10, brazo)
        if con_arma:
            L.rect(cx + 2, oy - 6, 3, 12, pal["arma"])
            L.rect(cx + 4, oy + 1, 2, 4, oscuro)
    else:
        sentido = -1 if apunte == "diag_arr" else 1
        L.linea(hombro[0], hombro[1], hombro[0] + 5, hombro[1] + 5 * sentido, brazo, 3)
        if con_arma:
            L.linea(hombro[0] + 3, hombro[1] + 3 * sentido, hombro[0] + 11, hombro[1] + 11 * sentido,
                    pal["arma"], 3)
    return L.contorno().imagen()


def comando_agachado(pal):
    L = Lienzo(36, 14)
    L.rect(2, 8, 12, 4, pal["pantalon"])
    L.rect(0, 9, 3, 4, pal["bota"])
    L.rect(13, 6, 9, 6, pal["torso"] or pal["piel"])
    L.rect(13, 10, 9, 2, "#2b2b2b")
    L.rect(21, 3, 7, 7, pal["piel"])
    L.rect(21, 2, 7, 2, pal["pelo"])
    L.px(26, 5, "#1a1a1a")
    if pal["cinta"]:
        L.rect(21, 4, 7, 2, pal["cinta"])
    L.rect(22, 9, 8, 2, pal["piel"])
    L.rect(26, 8, 10, 3, pal["arma"])
    return L.contorno().imagen()


def comando_salto(pal, giro):
    L = Lienzo(18, 18)
    L.ovalo(9, 9, 7, 7, pal["pantalon"])
    L.ovalo(9, 9, 4, 4, pal["piel"])
    L.rect(7, 2, 5, 3, pal["piel"])
    L.rect(7, 2, 5, 1, pal["cinta"] or pal["pelo"])
    L.rect(12, 12, 4, 3, pal["bota"])
    L.rect(2, 7, 3, 4, pal["bota"])
    return np.rot90(L.contorno().imagen(), -giro).copy()


def comando_agua(pal, apunte):
    L = Lienzo(30, 22)
    L.rect(9, 10, 9, 6, pal["piel"])
    L.rect(10, 3, 7, 7, pal["piel"])
    L.rect(10, 2, 7, 2, pal["pelo"])
    L.px(15, 5, "#1a1a1a")
    if pal["cinta"]:
        L.rect(10, 4, 7, 2, pal["cinta"])
        L.rect(6, 5, 4, 1, pal["cinta"])
    if apunte == "arriba":
        L.rect(15, 0, 3, 12, pal["arma"])
    elif apunte == "diag_arr":
        L.linea(16, 11, 25, 2, pal["arma"], 3)
    else:
        L.rect(15, 10, 13, 3, pal["arma"])
    L.contorno()
    L.rect(2, 16, 26, 2, "#9fd2ff")
    L.rect(0, 18, 30, 4, "#3f7fd0")
    return L.imagen()


def ondas():
    L = Lienzo(22, 6)
    L.rect(2, 1, 18, 2, "#9fd2ff")
    L.rect(0, 3, 22, 3, "#3f7fd0")
    return L.imagen()


def comando_muerto(pal):
    L = Lienzo(34, 12)
    L.rect(2, 4, 12, 5, pal["pantalon"])
    L.rect(0, 5, 3, 4, pal["bota"])
    L.rect(13, 3, 10, 6, pal["torso"] or pal["piel"])
    L.rect(22, 2, 7, 7, pal["piel"])
    L.rect(22, 1, 7, 2, pal["pelo"])
    return L.contorno().imagen()


def torreta(angulo, base="#4a5160", luz="#ff5a4a"):
    L = Lienzo(20, 20)
    L.ovalo(10, 10, 9, 9, mezclar(base, "#000000", 0.35))
    L.ovalo(10, 10, 7, 7, base)
    L.ovalo(10, 10, 3, 3, luz)
    a = angulo * math.pi / 6
    L.linea(10, 10, 10 + math.cos(a) * 10, 10 + math.sin(a) * 10, "#c8d0d8", 3)
    return L.contorno().imagen()


def canon(angulo):
    L = Lienzo(24, 20)
    L.rect(2, 10, 20, 10, "#5a5f6a")
    L.rect(2, 10, 20, 2, "#8a909c")
    L.ovalo(12, 10, 6, 5, "#3e434c")
    a = angulo * math.pi / 6
    L.linea(12, 10, 12 + math.cos(a) * 12, 10 + math.sin(a) * 12, "#c8d0d8", 4)
    return L.contorno().imagen()


def capsula(cuadro):
    L = Lienzo(26, 16)
    ala = 3 if cuadro else 0
    L.rect(1, 4 + ala, 6, 3, "#c0c8d0")
    L.rect(19, 4 + ala, 6, 3, "#c0c8d0")
    L.ovalo(13, 9, 8, 5, "#8a95a3")
    L.ovalo(13, 8, 6, 3, "#c4ccd6")
    L.ovalo(13, 9, 2, 2, "#ff4848")
    return L.contorno().imagen()


def caja(abierta):
    L = Lienzo(24, 24)
    L.rect(1, 1, 22, 22, "#5d6470")
    L.rect(1, 1, 22, 3, "#8a929e")
    if abierta:
        L.rect(5, 6, 14, 14, "#2a0d0d")
        L.ovalo(12, 13, 5, 5, "#ff5040")
        L.ovalo(12, 13, 2, 2, "#ffd0c0")
    else:
        for y in range(6, 20, 3):
            L.rect(5, y, 14, 2, "#3e434c")
    return L.contorno().imagen()


def roca():
    L = Lienzo(18, 18)
    L.ovalo(9, 9, 8, 8, "#6b5a48")
    L.ovalo(7, 7, 5, 4, "#8a7660")
    L.px(11, 11, "#4a3d30")
    L.px(5, 12, "#4a3d30")
    return L.contorno().imagen()


def llama(cuadro):
    L = Lienzo(14, 16)
    desfase = 2 if cuadro else 0
    L.ovalo(7, 8, 6, 8, "#ff7a1a")
    L.ovalo(7 + (1 if cuadro else -1), 8 + desfase - 1, 4, 6, "#ffc23a")
    L.ovalo(7, 8, 2, 4, "#fff4c0")
    return L.imagen()


def boquilla():
    L = Lienzo(16, 6)
    L.rect(1, 0, 14, 6, "#6a6f7a")
    L.rect(4, 2, 8, 2, "#2a2d33")
    return L.contorno().imagen()


def prensa():
    L = Lienzo(32, 24)
    L.rect(1, 0, 30, 18, "#6d737f")
    L.rect(1, 0, 30, 3, "#a3aab6")
    for x in range(2, 30, 6):
        L.rect(x, 18, 4, 5, "#c8ced8")
        L.px(x + 1, 22, "#ffffff")
    L.rect(4, 7, 24, 3, "#f0c020")
    return L.contorno().imagen()


def piston():
    L = Lienzo(12, 16)
    L.rect(2, 0, 8, 16, "#8d939f")
    L.rect(2, 0, 2, 16, "#b8bec8")
    return L.imagen()


def nucleo(cuadro):
    L = Lienzo(18, 34)
    L.rect(1, 1, 16, 32, "#4a5160")
    L.rect(3, 3, 12, 28, "#1a1d24")
    brillo = "#ff6a3a" if cuadro else "#ffb04a"
    L.ovalo(9, 17, 5, 11, brillo)
    L.ovalo(9, 17, 2, 6, "#fff0c0")
    return L.contorno().imagen()


def larva(cuadro):
    L = Lienzo(14, 10)
    L.ovalo(7, 6, 6, 3 + cuadro, "#c8d86a")
    L.ovalo(11, 5, 2, 2, "#e8f0a0")
    for x in (3, 6, 9):
        L.px(x, 9, "#6a7a2a")
    return L.contorno().imagen()


def boca(abierta):
    L = Lienzo(26, 26)
    L.ovalo(13, 13, 12, 12, "#8a2a3a")
    L.ovalo(13, 13, 9, 9, "#b04050")
    if abierta:
        L.ovalo(13, 14, 6, 6, "#2a0a10")
        for x in (9, 13, 17):
            L.rect(x, 8, 1, 3, "#f0e8d0")
    else:
        L.rect(6, 13, 14, 2, "#2a0a10")
    return L.contorno().imagen()


def sensor(cuadro):
    L = Lienzo(24, 34)
    L.rect(1, 1, 22, 32, "#5a6270")
    L.rect(1, 1, 22, 3, "#9aa2ae")
    L.rect(4, 6, 16, 22, "#22262e")
    L.ovalo(12, 17, 7, 9, "#ff3030" if cuadro else "#c01818")
    L.ovalo(10, 14, 2, 3, "#ffb0b0")
    return L.contorno().imagen()


def canon_muro():
    L = Lienzo(22, 14)
    L.rect(6, 1, 15, 12, "#5a6270")
    L.rect(0, 5, 10, 4, "#c8d0d8")
    L.rect(14, 4, 4, 6, "#ff5a4a")
    return L.contorno().imagen()


def ojo(cuadro):
    L = Lienzo(42, 42)
    L.ovalo(21, 21, 20, 20, "#3e4450")
    L.ovalo(21, 21, 16, 16, "#e8e0d0")
    L.ovalo(21 - (3 if cuadro else 0), 21, 9, 9, "#c0282a")
    L.ovalo(21 - (3 if cuadro else 0), 21, 4, 4, "#1a0505")
    L.ovalo(16, 15, 3, 2, "#ffffff")
    return L.contorno().imagen()


def cabeza(cuadro):
    L = Lienzo(50, 42)
    L.ovalo(25, 18, 22, 17, "#7a8a5a")
    L.ovalo(25, 16, 18, 12, "#9aab72")
    L.ovalo(15, 18, 5, 4, "#1a1a10")
    L.ovalo(35, 18, 5, 4, "#1a1a10")
    L.ovalo(15, 18, 2, 2, "#ff4020")
    L.ovalo(35, 18, 2, 2, "#ff4020")
    L.ovalo(25, 33, 10, 6 + 2 * cuadro, "#3a0a10")
    for x in range(17, 34, 4):
        L.rect(x, 28, 2, 4, "#f0e8d0")
    return L.contorno().imagen()


def orbe():
    L = Lienzo(18, 18)
    L.ovalo(9, 9, 8, 8, "#6a7a4a")
    L.ovalo(9, 9, 5, 5, "#b0c070")
    L.ovalo(7, 7, 2, 2, "#f0f8c0")
    return L.contorno().imagen()


def gemelo(cuadro):
    L = Lienzo(30, 30)
    L.ovalo(15, 15, 14, 14, "#4a5466")
    L.ovalo(15, 15, 10, 10, "#7a8aa0")
    L.ovalo(15, 15, 6, 6, "#40e0ff" if cuadro else "#2090c0")
    L.ovalo(13, 13, 2, 2, "#e0faff")
    return L.contorno().imagen()


def tanque():
    L = Lienzo(58, 42)
    L.rect(2, 26, 54, 14, "#2e3238")
    for x in range(5, 54, 8):
        L.ovalo(x + 2, 33, 4, 4, "#5a5f68")
    L.rect(4, 14, 50, 13, "#5f6b4e")
    L.rect(4, 14, 50, 3, "#7d8a6a")
    L.rect(16, 4, 22, 11, "#4e593f")
    L.rect(0, 7, 18, 4, "#9aa3ad")
    L.ovalo(30, 9, 3, 3, "#ff5040")
    return L.contorno().imagen()


def gigante(cuadro):
    L = Lienzo(34, 58)
    L.rect(6, 36, 9, 20, "#4a4f5a")
    L.rect(19, 36, 9, 20, "#4a4f5a")
    L.rect(4, 14, 26, 23, "#6a7180")
    L.rect(4, 14, 26, 4, "#9aa2ae")
    L.rect(9, 2, 16, 13, "#5a606c")
    L.rect(11, 6, 12, 4, "#ff4a3a" if cuadro else "#c02a1a")
    L.rect(0, 16, 5, 16, "#5a606c")
    L.rect(29, 16, 5, 16 - 4 * cuadro, "#5a606c")
    return L.contorno().imagen()


def nave(cuadro):
    L = Lienzo(42, 42)
    L.rect(2, 2, 38, 38, "#4a5160")
    L.rect(2, 2, 38, 4, "#8a92a0")
    L.ovalo(21, 21, 14, 14, "#1a1d24")
    L.ovalo(21, 21, 11 - cuadro, 11 - cuadro, "#3ad0ff")
    L.ovalo(21, 21, 5, 5, "#e0faff")
    return L.contorno().imagen()


def corazon(cuadro):
    L = Lienzo(50, 58)
    r = 22 - 2 * cuadro
    L.ovalo(25, 30, r, r + 4, "#9a1a2a")
    L.ovalo(22, 26, r - 6, r - 4, "#c8283a")
    for x0, y0, x1, y1 in ((10, 10, 20, 30), (40, 14, 30, 34), (25, 50, 25, 36)):
        L.linea(x0, y0, x1, y1, "#5a0a14", 2)
    L.ovalo(18, 20, 3, 4, "#ff8090")
    return L.contorno().imagen()


def bala(c1, c2, lado):
    L = Lienzo(lado + 2, lado + 2)
    L.ovalo((lado + 2) / 2, (lado + 2) / 2, lado / 2, lado / 2, c1)
    L.ovalo((lado + 2) / 2 - 0.5, (lado + 2) / 2 - 0.5, lado / 4, lado / 4, c2)
    return L.imagen()


def laser(direccion):
    L = Lienzo(18, 18)
    a = direccion * math.pi / 4
    dx, dy = math.cos(a) * 8, math.sin(a) * 8
    L.linea(9 - dx, 9 - dy, 9 + dx, 9 + dy, "#4a8cff", 4)
    L.linea(9 - dx, 9 - dy, 9 + dx, 9 + dy, "#e0f0ff", 2)
    return L.imagen()


def granada():
    L = Lienzo(8, 8)
    L.ovalo(4, 4, 3, 3, "#3a4a2a")
    L.px(4, 1, "#ffcc40")
    return L.contorno().imagen()


def disco(cuadro):
    L = Lienzo(12, 12)
    L.ovalo(6, 6, 5, 5, "#c0c8d0")
    for k in range(4):
        a = k * math.pi / 2 + cuadro * math.pi / 4
        L.linea(6, 6, 6 + math.cos(a) * 6, 6 + math.sin(a) * 6, "#ffffff")
    return L.contorno().imagen()


def item(letra):
    L = Lienzo(20, 14)
    L.rect(0, 3, 6, 3, "#e8c040")
    L.rect(14, 3, 6, 3, "#e8c040")
    L.rect(1, 6, 4, 2, "#b08820")
    L.rect(15, 6, 4, 2, "#b08820")
    L.ovalo(10, 7, 6, 6, "#f0d050")
    L.ovalo(10, 7, 4, 5, "#fff0b0")
    for f, fila in enumerate(FUENTE[letra]):
        for c, valor in enumerate(fila):
            if valor == "1":
                L.px(9 + c, 5 + f, "#c01818")
    return L.contorno().imagen()


def explosion(cuadro):
    L = Lienzo(28, 28)
    r = 5 + cuadro * 3
    exterior = ("#ffd040", "#ff8a20", "#e05a18", "#7a3a20")[cuadro]
    interior = ("#ffffff", "#fff0a0", "#ffc040", None)[cuadro]
    L.ovalo(14, 14, r, r, exterior)
    if interior:
        L.ovalo(14, 14, r * 0.6, r * 0.6, interior)
    if cuadro >= 2:
        hueco = Lienzo(28, 28)
        hueco.ovalo(14, 14, r - 3 - cuadro, r - 3 - cuadro, "#000000")
        L.a[hueco.a[..., 3] > 0] = 0
    return L.imagen()


def chispa():
    L = Lienzo(10, 10)
    L.linea(1, 5, 9, 5, "#ffe080")
    L.linea(5, 1, 5, 9, "#ffe080")
    L.px(5, 5, "#ffffff")
    return L.imagen()


def puente():
    L = Lienzo(16, 16)
    L.rect(0, 0, 16, 6, "#8a6a42")
    L.rect(0, 0, 16, 2, "#b08a5a")
    for x in (0, 8):
        L.rect(x, 0, 1, 6, "#5a4228")
    L.rect(2, 6, 2, 8, "#5a4a3a")
    L.rect(12, 6, 2, 8, "#5a4a3a")
    return L.imagen()


def barrera(cuadro):
    L = Lienzo(16, 16)
    L.rect(2, 0, 12, 16, "#20304a")
    for y in range(0, 16, 4):
        x = 4 + ((y // 4 + cuadro) % 2) * 6
        L.linea(x, y, 10 - (x - 4), y + 4, "#7ae0ff", 1)
    L.rect(2, 0, 1, 16, "#5a7aa0")
    L.rect(13, 0, 1, 16, "#5a7aa0")
    return L.imagen()


def medalla(c):
    L = Lienzo(8, 14)
    L.rect(2, 0, 4, 5, c)
    L.ovalo(4, 9, 4, 4, "#e8c040")
    L.ovalo(4, 9, 2, 2, "#fff0b0")
    return L.contorno().imagen()


def generar_sprites():
    s = {}
    for nombre in ("j1", "j2"):
        pal = PALETAS[nombre]
        for piernas in PIERNAS:
            for apunte in APUNTES:
                s[f"{nombre}_{piernas}_{apunte}"] = comando(pal, piernas, apunte)
        s[f"{nombre}_agachado"] = comando_agachado(pal)
        for k in range(4):
            s[f"{nombre}_salto{k}"] = comando_salto(pal, k)
        for apunte in ("h", "arriba", "diag_arr"):
            s[f"{nombre}_agua_{apunte}"] = comando_agua(pal, apunte)
        s[f"{nombre}_muerto"] = comando_muerto(pal)
    s["buceo"] = ondas()
    for k, piernas in enumerate(("c0", "c2")):
        s[f"soldado{k}"] = comando(PALETAS["soldado"], piernas, "h", con_arma=False)
    s["francotirador"] = comando(PALETAS["tirador"], "quieto", "h")
    s["granadero0"] = comando(PALETAS["nieve"], "quieto", "h", con_arma=False)
    s["granadero1"] = comando(PALETAS["nieve"], "quieto", "arriba", con_arma=False)
    for a in range(12):
        s[f"torreta{a}"] = torreta(a)
        s[f"torreta_jefe{a}"] = torreta(a, "#5a3a4a", "#ffd040")
    for a in (5, 6, 7):
        s[f"canon{a}"] = canon(a)
    for k in range(2):
        s[f"capsula{k}"] = capsula(k)
        s[f"llama{k}"] = llama(k)
        s[f"nucleo{k}"] = nucleo(k)
        s[f"larva{k}"] = larva(k)
        s[f"boca{k}"] = boca(k)
        s[f"sensor{k}"] = sensor(k)
        s[f"ojo{k}"] = ojo(k)
        s[f"cabeza{k}"] = cabeza(k)
        s[f"gemelo{k}"] = gemelo(k)
        s[f"gigante{k}"] = gigante(k)
        s[f"nave{k}"] = nave(k)
        s[f"corazon{k}"] = corazon(k)
        s[f"disco{k}"] = disco(k)
        s[f"barrera{k}"] = barrera(k)
        s[f"caja{k}"] = caja(k)
    s["roca"] = roca()
    s["boquilla"] = boquilla()
    s["prensa"] = prensa()
    s["piston"] = piston()
    s["canon_muro"] = canon_muro()
    s["orbe"] = orbe()
    s["tanque"] = tanque()
    s["bala_N"] = bala("#fff6d0", "#ffffff", 4)
    s["bala_M"] = bala("#ffb040", "#fff0c0", 4)
    s["bala_S"] = bala("#ff4a3a", "#ffd0c0", 5)
    s["bala_F"] = bala("#ff7a1a", "#ffe080", 8)
    s["bala_e"] = bala("#ff70c0", "#ffffff", 4)
    for d in range(8):
        s[f"laser{d}"] = laser(d)
    s["granada"] = granada()
    for letra in FUENTE:
        s[f"item_{letra}"] = item(letra)
    for k in range(4):
        s[f"explosion{k}"] = explosion(k)
    s["chispa"] = chispa()
    s["puente"] = puente()
    s["medalla_1"] = medalla(PALETAS["j1"]["pantalon"])
    s["medalla_2"] = medalla(PALETAS["j2"]["pantalon"])
    for nombre in list(s):
        if nombre.startswith(("j1_", "j2_", "soldado", "francotirador", "granadero")):
            s[nombre + "_izq"] = espejo(s[nombre])
    return s


TEMAS = {
    "jungla": dict(cielo=("#0a1430", "#2a6a8a"), lejos="#1a3a52", medio="#173d26", tope="#5cbf3a",
                   cuerpo="#6d4c2f", detalle="#4a3322", plataforma="#3e8e41", agua=("#1e5aa8", "#5f9fe8")),
    "base": dict(cielo=("#10141c", "#1c2432"), lejos="#232c3c", medio="#2c3850", tope="#9aaec8",
                 cuerpo="#4e5c70", detalle="#36404e", plataforma="#7a8aa0", agua=("#1e5aa8", "#5f9fe8")),
    "cascada": dict(cielo=("#0b1e2c", "#16384e"), lejos="#2f78b8", medio="#8cc6f0", tope="#8a7a5a",
                    cuerpo="#5b4a3a", detalle="#40342a", plataforma="#7a6450", agua=("#1e5aa8", "#5f9fe8")),
    "nieve": dict(cielo=("#6f9ccc", "#d8e8f6"), lejos="#a8bcd4", medio="#2e4a3a", tope="#f4f8ff",
                  cuerpo="#6e88a6", detalle="#4e6480", plataforma="#cfe0f2", agua=("#1e5aa8", "#5f9fe8")),
    "energia": dict(cielo=("#0c0812", "#24142a"), lejos="#3a2030", medio="#5a3a2a", tope="#d09a3a",
                    cuerpo="#4b3f52", detalle="#30283a", plataforma="#a37a3a", agua=("#1e5aa8", "#5f9fe8")),
    "hangar": dict(cielo=("#0e1014", "#1c2028"), lejos="#262b34", medio="#323844", tope="#e8c030",
                   cuerpo="#3e4650", detalle="#2a3038", plataforma="#8a929e", agua=("#1e5aa8", "#5f9fe8")),
    "guarida": dict(cielo=("#1a0508", "#3a0a14"), lejos="#4a1020", medio="#6a1a2a", tope="#c0506a",
                    cuerpo="#7a2a35", detalle="#5a1a24", plataforma="#a03a4a", agua=("#1e5aa8", "#5f9fe8")),
}


def _rgb(hexa):
    return np.array(color(hexa)[:3], dtype=np.float64)


BAYER = np.array([[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]]) / 16.0
METALICOS = ("base", "hangar", "energia")


def _tramado(arriba, abajo, alto, ancho, niveles=10, y0=0):
    t = np.clip((np.arange(alto)[:, None] + y0) / max(alto - 1, 1), 0, 1) * np.ones((1, ancho))
    v = t * niveles
    base = np.floor(v)
    umbral = BAYER[(np.arange(alto)[:, None] + y0) % 4, np.arange(ancho)[None, :] % 4]
    q = np.minimum(base + (v - base > umbral), niveles) / niveles
    return arriba * (1 - q[..., None]) + abajo * q[..., None]


def _difuminar(m, r):
    if r < 1:
        return m
    k = 2 * r + 1
    p = np.pad(m, r, mode="edge")
    c = np.cumsum(np.cumsum(p, 0), 1)
    c = np.pad(c, ((1, 0), (1, 0)))
    return (c[k:, k:] - c[:-k, k:] - c[k:, :-k] + c[:-k, :-k]) / (k * k)


def _linea(img, x0, y0, x1, y1, c, grosor=1):
    alto, ancho = img.shape[:2]
    pasos = int(max(abs(x1 - x0), abs(y1 - y0))) + 1
    for k in range(pasos + 1):
        t = k / pasos
        x, y = int(round(x0 + (x1 - x0) * t)), int(round(y0 + (y1 - y0) * t))
        img[max(y, 0):min(y + grosor, alto), max(x, 0):min(x + grosor, ancho)] = c


def _disco(img, cx, cy, rx, ry, c):
    alto, ancho = img.shape[:2]
    y0, y1 = max(int(cy - ry) - 1, 0), min(int(cy + ry) + 2, alto)
    x0, x1 = max(int(cx - rx) - 1, 0), min(int(cx + rx) + 2, ancho)
    if y1 <= y0 or x1 <= x0:
        return None
    yy, xx = np.mgrid[y0:y1, x0:x1]
    m = ((xx + 0.5 - cx) / max(rx, 0.5)) ** 2 + ((yy + 0.5 - cy) / max(ry, 0.5)) ** 2 <= 1
    img[y0:y1, x0:x1][m] = c
    return m


def _textura_solida(tema, rng, tope):
    t = TEMAS[tema]
    cuerpo, detalle = _rgb(t["cuerpo"]), _rgb(t["detalle"])
    claro = _rgb(mezclar(t["cuerpo"], "#ffffff", 0.22))
    oscuro = _rgb(mezclar(t["cuerpo"], "#000000", 0.35))
    img = np.empty((T, T, 3))
    img[:] = cuerpo
    if tema in METALICOS:
        img[:] = _tramado(_rgb(mezclar(t["cuerpo"], "#ffffff", 0.08)),
                          _rgb(mezclar(t["cuerpo"], "#000000", 0.12)), T, T, 3)
        img[0, :] = img[:, 0] = claro
        img[-1, :] = img[:, -1] = oscuro
        img[1, 1:-1] = _rgb(mezclar(t["cuerpo"], "#ffffff", 0.1))
        for y, x in ((3, 3), (3, 11), (11, 3), (11, 11)):
            img[y:y + 2, x:x + 2] = detalle
            img[y, x] = claro
        if rng.random() < 0.5:
            img[7:9, 2:14] = _rgb(mezclar(t["cuerpo"], "#000000", 0.2))
            img[7, 2:14] = _rgb(mezclar(t["cuerpo"], "#000000", 0.32))
    else:
        ruido = rng.random((T, T))
        img[ruido > 0.9] = _rgb(mezclar(t["cuerpo"], "#000000", 0.12))
        img[ruido < 0.05] = _rgb(mezclar(t["cuerpo"], "#ffffff", 0.08))
        for _ in range(int(rng.integers(2, 4))):
            cx, cy = rng.uniform(2, T - 2), rng.uniform(6 if tope else 2, T - 2)
            rx, ry = rng.uniform(1.6, 3.2), rng.uniform(1.2, 2.2)
            m = _disco(img, cx, cy, rx, ry, detalle)
            if m is not None:
                ix, iy = int(cx - rx * 0.4), int(cy - ry * 0.5)
                if 0 <= iy < T and 0 <= ix < T:
                    img[iy, ix] = _rgb(mezclar(t["detalle"], "#ffffff", 0.3))
                bx, by = int(cx + rx * 0.6), int(cy + ry * 0.8)
                if 0 <= by < T and 0 <= bx < T:
                    img[by, max(bx - 1, 0):bx + 1] = _rgb(mezclar(t["detalle"], "#000000", 0.35))
    if tope:
        tc = _rgb(t["tope"])
        luz = _rgb(mezclar(t["tope"], "#ffffff", 0.45))
        sombra_t = _rgb(mezclar(t["tope"], "#000000", 0.35))
        if tema in METALICOS:
            img[:3] = tc
            img[0] = luz
            img[3] = sombra_t
            if tema == "hangar":
                for x in range(T):
                    if ((x + 2) // 4) % 2:
                        img[:3, x] = _rgb("#1a1a1a")
                img[0] = _rgb(mezclar("#e8c030", "#ffffff", 0.3))
        else:
            for x in range(T):
                largo = 3 + int(rng.integers(0, 3)) + (1 if x % 5 == 2 else 0)
                img[:largo, x] = tc
                img[largo - 1, x] = sombra_t
                img[largo, x] = _rgb(mezclar(t["cuerpo"], "#000000", 0.3))
            img[0] = luz
            for x in range(0, T, 3):
                img[1, x + int(rng.integers(0, 2)) if x + 1 < T else x] = luz
            if tema == "nieve":
                img[0:2] = _rgb("#ffffff")
    return img


def _textura_plataforma(tema):
    t = TEMAS[tema]
    img = np.full((T, T, 4), 0, dtype=np.float64)
    p = t["plataforma"]
    img[:5, :, :3] = _rgb(p)
    img[1:4, ::4, :3] = _rgb(mezclar(p, "#000000", 0.18))
    img[0, :, :3] = _rgb(mezclar(p, "#ffffff", 0.4))
    img[4, :, :3] = _rgb(mezclar(p, "#000000", 0.4))
    img[5, :, :3] = _rgb(mezclar(p, "#000000", 0.6))
    img[:6, :, 3] = 255
    for x0 in (3, 11):
        img[6:13, x0:x0 + 2, :3] = _rgb(mezclar(p, "#000000", 0.5))
        img[6:13, x0, :3] = _rgb(mezclar(p, "#000000", 0.3))
        img[6:13, x0:x0 + 2, 3] = 255
    return img


def _textura_agua(tema, superficie):
    t = TEMAS[tema]
    a0, a1 = _rgb(t["agua"][1]), _rgb(t["agua"][0])
    img = _tramado(_rgb(mezclar(t["agua"][0], t["agua"][1], 0.3)), _rgb(mezclar(t["agua"][0], "#000000",
                                                                                 0.25)), T, T, 4)
    if superficie:
        img[:3] = a0
        img[0, ::2] = _rgb("#ffffff")
        img[1, 1::4] = _rgb("#ffffff")
        img[3, ::3] = a0
    img[7, 2:7] = img[12, 9:14] = _rgb(mezclar(t["agua"][1], "#ffffff", 0.25))
    img[8, 3:5] = img[13, 10:12] = a1
    return img


def _cielo(tema, alto, ancho, vertical):
    t = TEMAS[tema]
    arriba, abajo = _rgb(t["cielo"][0]), _rgb(t["cielo"][1])
    banda = _tramado(arriba, abajo, C.ALTO_VISTA, ancho, 12)
    if vertical:
        veces = alto // C.ALTO_VISTA + 1
        img = np.concatenate([banda] * veces, 0)[:alto]
    else:
        img = banda
    return img.astype(np.float64)


def _estrellas(img, rng, densidad, hasta):
    alto, ancho = img.shape[:2]
    for _ in range(int(ancho * hasta * densidad)):
        x, y = int(rng.integers(0, ancho)), int(rng.integers(0, hasta))
        brillo = rng.uniform(0.35, 1.0)
        img[y, x] = img[y, x] * (1 - brillo) + 255 * brillo
        if brillo > 0.93 and 0 < x < ancho - 1 and 0 < y < alto - 1:
            img[y, x - 1] = img[y, x + 1] = img[y - 1, x] = img[y + 1, x] = img[y, x] * 0.55


def _nubes(img, rng, color_nube, y_min, y_max, cantidad):
    alto, ancho = img.shape[:2]
    c = _rgb(color_nube)
    for _ in range(cantidad):
        cx, cy = rng.uniform(0, ancho), rng.uniform(y_min, y_max)
        for k in range(int(rng.integers(3, 6))):
            _disco(img, cx + k * rng.uniform(5, 9) - 12, cy + rng.uniform(-3, 2), rng.uniform(7, 13),
                   rng.uniform(3, 6), c)
        base = int(cy + 3)
        if 0 <= base < alto:
            x0, x1 = max(int(cx - 20), 0), min(int(cx + 40), ancho)
            img[base:base + 2, x0:x1][img[base:base + 2, x0:x1].sum(-1) == c.sum()] = c * 0.88


def _monte(img, rng, base, amplitud, color_monte, color_cielo, niebla):
    alto, ancho = img.shape[:2]
    xs = np.arange(ancho)
    f1, f2, f3 = rng.uniform(25, 45), rng.uniform(9, 16), rng.uniform(4, 7)
    p1, p2 = rng.uniform(0, 6), rng.uniform(0, 6)
    h = base - amplitud * (0.6 * np.sin(xs / f1 + p1) + 0.3 * np.sin(xs / f2 + p2)
                           + 0.1 * np.sin(xs / f3)) - amplitud * 0.4
    c = _rgb(mezclar(color_monte, color_cielo, niebla))
    luz = _rgb(mezclar(mezclar(color_monte, color_cielo, niebla), "#ffffff", 0.18))
    sombra = _rgb(mezclar(mezclar(color_monte, color_cielo, niebla), "#000000", 0.18))
    pend = np.gradient(h)
    for x in range(ancho):
        y = int(h[x])
        if y >= alto:
            continue
        y = max(y, 0)
        img[y:, x] = c
        img[y, x] = luz
        if pend[x] > 0.15:
            img[y + 1:y + 6, x][(np.arange(min(5, alto - y - 1)) + x) % 2 == 0] = sombra
    return h


def _palmera(img, x, suelo, alto_t, color_t, color_h):
    curva = alto_t * 0.18
    pasos = int(alto_t)
    tope = (x, suelo)
    for k in range(pasos):
        t = k / pasos
        px = x + curva * t * t
        py = suelo - k
        img[int(py), int(px):int(px) + 2] = color_t
        if k % 4 == 0:
            img[int(py), int(px)] = color_t * 0.7
        tope = (px + 1, py)
    tx, ty = tope
    for ang, largo in ((-2.6, 15), (-2.0, 17), (-1.2, 14), (-0.45, 16), (0.2, 13), (0.85, 12), (-3.2, 11)):
        x1 = tx + math.cos(ang) * largo
        y1 = ty + math.sin(ang) * largo * 0.55 + largo * 0.35
        medio = ((tx + x1) / 2, (ty + y1) / 2 - 3)
        _linea(img, tx, ty, medio[0], medio[1], color_h, 2)
        _linea(img, medio[0], medio[1], x1, y1, color_h, 1)


def _decorado(tema, img, rng, vertical):
    alto, ancho = img.shape[:2]
    t = TEMAS[tema]
    xs = np.arange(ancho)
    cielo_bajo = t["cielo"][1]
    if tema == "cascada":
        roca = _rgb(t["lejos"])
        img[:] = _tramado(_rgb(mezclar("#16384e", "#000000", 0.2)), _rgb("#0b1e2c"), alto, ancho, 6)
        for x0 in (28, 84, 140, 196):
            w = int(rng.integers(20, 34))
            sub = img[:, x0:x0 + w]
            sub[:] = roca
            for k in range(0, alto, 2):
                for _ in range(2):
                    d = int(rng.integers(0, w))
                    largo = int(rng.integers(3, 9))
                    sub[k:k + largo, d] = _rgb(t["medio"])
            sub[:, :2] = _rgb(mezclar(t["lejos"], "#000000", 0.3))
            sub[:, -2:] = _rgb(mezclar(t["lejos"], "#ffffff", 0.25))
        _estrellas(img, rng, 0.003, alto)
        return img
    if tema in METALICOS:
        medio = t["medio"]
        img[:] = _tramado(_rgb(t["cielo"][0]), _rgb(t["cielo"][1]), alto, ancho, 6)
        panel = _rgb(mezclar(t["lejos"], "#000000", 0.1))
        for y in range(8, alto - 44, 48):
            for x in range(0, ancho - 62, 64):
                img[y:y + 44, x + 2:x + 62] = panel
                img[y, x + 2:x + 62] = _rgb(mezclar(t["lejos"], "#ffffff", 0.12))
                img[y:y + 44, x + 2] = _rgb(mezclar(t["lejos"], "#ffffff", 0.08))
                img[y + 43, x + 2:x + 62] = _rgb(mezclar(t["lejos"], "#000000", 0.35))
                img[y:y + 44, x + 61] = _rgb(mezclar(t["lejos"], "#000000", 0.3))
                for ry, rx in ((3, 5), (3, 57), (39, 5), (39, 57)):
                    img[y + ry, x + rx] = _rgb(mezclar(t["lejos"], "#ffffff", 0.3))
                if (x // 64 + y // 48) % 3 == 0:
                    img[y + 14:y + 30, x + 14:x + 50:4] = _rgb(mezclar(t["lejos"], "#000000", 0.3))
        for y in (40 + 48 * k for k in range(0, alto // 48, 2)):
            if y + 5 < alto:
                img[y:y + 6, :] = _rgb(medio)
                img[y, :] = _rgb(mezclar(medio, "#ffffff", 0.35))
                img[y + 1, :] = _rgb(mezclar(medio, "#ffffff", 0.15))
                img[y + 5, :] = _rgb(mezclar(medio, "#000000", 0.4))
                img[y:y + 6, ::40] = _rgb(mezclar(medio, "#000000", 0.25))
        luz = "#ff6a3a" if tema == "energia" else ("#ffd23a" if tema == "hangar" else "#3ad0ff")
        for x in range(20, ancho, 96):
            y = int(rng.integers(30, max(31, min(alto, 170) - 10)))
            yy, xx = np.mgrid[0:14, 0:18]
            halo = np.clip(1 - np.hypot((xx - 8.5) / 9, (yy - 6.5) / 7), 0, 1)
            umbral = BAYER[yy % 4, xx % 4]
            sub = img[y - 4:y + 10, x - 4:x + 14]
            if sub.shape[:2] == halo.shape:
                m = halo * 0.9 > umbral
                sub[m] = sub[m] * 0.5 + _rgb(luz) * 0.5
            img[y:y + 3, x:x + 10] = _rgb(luz)
            img[y, x:x + 10] = _rgb(mezclar(luz, "#ffffff", 0.5))
        if tema == "energia":
            for y in (70, 120):
                img[y:y + 8, :] = _rgb(t["lejos"])
                img[y + 2, :] = _rgb("#7a4a30")
                img[y + 3, ::6] = _rgb("#ff8a3a")
        return img
    if tema == "guarida":
        base = _rgb(t["cielo"][1])
        for _ in range(ancho // 9):
            cx, cy = rng.uniform(0, ancho), rng.uniform(0, alto)
            r = rng.uniform(5, 22)
            col = t["lejos"] if r > 12 else t["medio"]
            _disco(img, cx, cy, r + 1.5, r + 1.5, _rgb(mezclar(col, "#000000", 0.45)))
            _disco(img, cx, cy, r, r, _rgb(col))
            _disco(img, cx - r * 0.25, cy - r * 0.3, r * 0.55, r * 0.45, _rgb(mezclar(col, "#ffffff", 0.12)))
            _disco(img, cx - r * 0.4, cy - r * 0.45, max(1, r * 0.15), max(1, r * 0.12),
                   _rgb(mezclar(col, "#ffffff", 0.4)))
        for _ in range(ancho // 40):
            x, y = rng.uniform(0, ancho), rng.uniform(0, alto)
            ang = rng.uniform(0, math.tau)
            for k in range(30):
                ang += rng.uniform(-0.4, 0.4)
                nx, ny = x + math.cos(ang) * 2, y + math.sin(ang) * 2
                _linea(img, x, y, nx, ny, base * 0.6, 1)
                x, y = nx, ny
        return img
    if tema == "jungla":
        _estrellas(img, rng, 0.006, 90)
        _disco(img, 200, 34, 13, 13, _rgb("#e8eef8"))
        _disco(img, 205, 31, 11, 11, _rgb(mezclar(t["cielo"][0], t["cielo"][1], 0.15)))
        _nubes(img, rng, mezclar(t["cielo"][1], "#ffffff", 0.18), 40, 80, ancho // 70)
        _monte(img, rng, 132, 26, t["lejos"], cielo_bajo, 0.45)
        _monte(img, rng, 150, 18, t["lejos"], cielo_bajo, 0.0)
        hoja_lejos = _rgb(mezclar(t["medio"], cielo_bajo, 0.3))
        for x in range(0, ancho, 9):
            _disco(img, x + rng.uniform(0, 6), 150 + rng.uniform(-4, 4), rng.uniform(7, 12),
                   rng.uniform(5, 8), hoja_lejos)
        img[152:, :] = hoja_lejos
        tronco = _rgb(mezclar(t["medio"], "#000000", 0.35))
        hoja = _rgb(t["medio"])
        for x in range(4, ancho, 26):
            x0 = x + int(rng.integers(0, 12))
            _palmera(img, x0, min(alto - 1, 175), rng.uniform(48, 72), tronco, hoja)
        return img
    if tema == "nieve":
        _disco(img, 60, 30, 18, 18, _rgb(mezclar(t["cielo"][1], "#ffffff", 0.6)))
        _nubes(img, rng, "#ffffff", 20, 70, ancho // 60)
        h = _monte(img, rng, 128, 34, t["lejos"], cielo_bajo, 0.35)
        for x in range(ancho):
            y = int(h[x])
            if 0 <= y < alto:
                img[y:y + 4 + int(3 * math.sin(x / 7)), x] = _rgb("#ffffff")
        _monte(img, rng, 150, 16, mezclar(t["lejos"], "#000000", 0.15), cielo_bajo, 0.1)
        pino = _rgb(t["medio"])
        pino_luz = _rgb(mezclar(t["medio"], "#ffffff", 0.2))
        for x in range(0, ancho, 18):
            x0 = x + int(rng.integers(0, 10))
            alto_p = int(rng.integers(16, 28))
            base = 168
            for k in range(alto_p):
                ancho_k = (k * 0.42) + 1 - (2 if k % 6 == 5 else 0)
                y = base - alto_p + k
                img[y, max(int(x0 - ancho_k), 0):int(x0 + ancho_k) + 1] = pino
                img[y, max(int(x0 - ancho_k), 0)] = pino_luz
                if k % 6 == 0:
                    img[y, max(int(x0 - ancho_k), 0):int(x0) + 1] = _rgb("#ffffff")
            img[base:base + 3, x0:x0 + 2] = _rgb("#4a3a2a")
        img[170:, :] = _tramado(_rgb(mezclar(t["lejos"], "#000000", 0.25)),
                                _rgb(mezclar(t["lejos"], "#000000", 0.7)), alto - 170, ancho, 6)
        return img
    montes = 120 + 18 * np.sin(xs / 37.0) + 10 * np.sin(xs / 13.0 + 1.3)
    for x in range(ancho):
        img[int(montes[x]):, x] = _rgb(t["lejos"])
    return img


def fondo(etapa):
    rng = np.random.default_rng(etapa.numero)
    tiles = etapa.tiles
    filas, columnas = tiles.shape
    alto, ancho = filas * T, columnas * T
    img = _cielo(etapa.tema, alto, ancho, etapa.vertical)
    img = _decorado(etapa.tema, img, rng, etapa.vertical)
    texturas = {(k, v): _textura_solida(etapa.tema, np.random.default_rng(k * 7 + v), v) for k in range(6)
                for v in (False, True)}
    plataforma = _textura_plataforma(etapa.tema)
    agua = {v: _textura_agua(etapa.tema, v) for v in (False, True)}
    solido = np.zeros((alto, ancho), np.float64)
    for f in range(filas):
        for c in range(columnas):
            if tiles[f, c] in (SOLIDO, PLATAFORMA):
                solido[f * T:(f + 1) * T, c * T:(c + 1) * T] = 1 if tiles[f, c] == SOLIDO else 0
                if tiles[f, c] == PLATAFORMA:
                    solido[f * T:f * T + 6, c * T:(c + 1) * T] = 1
    sombra = _difuminar(np.roll(np.roll(solido, 5, 0), 3, 1), 4)
    fondo_libre = solido < 0.5
    img[fondo_libre] *= (1 - np.clip(sombra[fondo_libre], 0, 1) * 0.5)[:, None]
    oscuro = _rgb(mezclar(TEMAS[etapa.tema]["cuerpo"], "#000000", 0.55))
    prof = np.zeros((filas, columnas), int)
    for f in range(filas):
        for c in range(columnas):
            if tiles[f, c] == SOLIDO:
                prof[f, c] = prof[f - 1, c] + 1 if f > 0 and tiles[f - 1, c] == SOLIDO else 0
    for f in range(filas):
        for c in range(columnas):
            t = tiles[f, c]
            y, x = f * T, c * T
            if t == SOLIDO:
                tope = f == 0 or tiles[f - 1, c] not in (SOLIDO,)
                bloque = texturas[((f * 3 + c * 5) % 6, bool(tope))].copy()
                d = prof[f, c]
                if d and etapa.tema not in METALICOS:
                    factor = max(0.62, 1 - 0.06 * d)
                    bloque *= factor
                if c > 0 and tiles[f, c - 1] != SOLIDO:
                    bloque[:, 0] = oscuro
                    bloque[:, 1] = bloque[:, 1] * 0.8
                if c < columnas - 1 and tiles[f, c + 1] != SOLIDO:
                    bloque[:, -1] = oscuro
                if f < filas - 1 and tiles[f + 1, c] != SOLIDO and not tope:
                    bloque[-1] = oscuro
                img[y:y + T, x:x + T] = bloque
            elif t == PLATAFORMA:
                alfa = plataforma[..., 3:] / 255
                img[y:y + T, x:x + T] = img[y:y + T, x:x + T] * (1 - alfa) + plataforma[..., :3] * alfa
            elif t == AGUA:
                img[y:y + T, x:x + T] = agua[f == 0 or tiles[f - 1, c] != AGUA]
            elif t == PINCHO:
                for k in range(0, T, 4):
                    for n in range(8):
                        img[y + 8 + n, x + k + 2 - n // 4:x + k + 2 + max(1, n // 4)] = _rgb("#c8d0d8")
                    img[y + 8:y + T, x + k + 1] = _rgb("#8a94a0")
                    img[y + 8, x + k + 1:x + k + 3] = _rgb("#ffffff")
    return np.clip(img, 0, 255).astype(np.uint8)
