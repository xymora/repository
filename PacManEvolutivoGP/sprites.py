import math

import numpy as np
import pygame

AMARILLO_PAC = (255, 226, 30)
COLORES_FANTASMA = ((255, 40, 40), (255, 150, 220), (40, 230, 255), (255, 170, 60))
AZUL_SUSTO = (36, 50, 230)
BLANCO_SUSTO = (240, 240, 255)


def construir(plantilla, paleta):
    alto, ancho = len(plantilla), max(len(f) for f in plantilla)
    s = pygame.Surface((ancho, alto), pygame.SRCALPHA)
    for y, fila in enumerate(plantilla):
        for x, ch in enumerate(fila):
            if ch != "." and ch in paleta:
                s.set_at((x, y), paleta[ch])
    return s


def _de_arreglo(rgba):
    h, w = rgba.shape[:2]
    s = pygame.Surface((w, h), pygame.SRCALPHA)
    pygame.surfarray.pixels3d(s)[:] = rgba[..., :3].transpose(1, 0, 2)
    pygame.surfarray.pixels_alpha(s)[:] = rgba[..., 3].T
    return s


TAM_PAC = 15


def comecocos(apertura, direccion, color=AMARILLO_PAC, tam=TAM_PAC):
    c = (tam - 1) / 2
    y, x = np.mgrid[0:tam, 0:tam].astype(float)
    dx, dy = x - c, y - c
    r = np.hypot(dx, dy)
    dentro = r <= c + 0.35
    ang_boca = {0: -math.pi / 2, 1: math.pi, 2: math.pi / 2, 3: 0.0}[direccion]
    ang = np.arctan2(dy, dx) - ang_boca
    ang = (ang + math.pi) % (2 * math.pi) - math.pi
    boca = (np.abs(ang) < apertura) & (r > 0.6)
    m = dentro & ~boca
    luz = np.clip(((-dx - dy) / (c * 1.6) + 1) / 2, 0, 1)
    borde = r > c - 0.9
    rgba = np.zeros((tam, tam, 4), dtype=np.uint8)
    col = np.array(color, dtype=float)
    tono = col[None, None] * (0.80 + 0.25 * luz[..., None])
    tono[borde] *= 0.82
    rgba[..., :3] = np.clip(tono, 0, 255).astype(np.uint8)
    rgba[..., 3] = np.where(m, 255, 0)
    return _de_arreglo(rgba)


def cuadros_comecocos(color=AMARILLO_PAC):
    aperturas = (0.08, 0.45, 0.85, 0.45)
    return {d: [comecocos(a, d, color) for a in aperturas] for d in range(4)}


def cuadros_muerte(color=AMARILLO_PAC, n=14):
    return [comecocos(0.1 + (math.pi - 0.05) * k / (n - 1), 0, color) for k in range(n)]


CUERPO = (
    ".....####.....",
    "...########...",
    "..##########..",
    ".############.",
    ".############.",
    ".############.",
    "##############",
    "##############",
    "##############",
    "##############",
    "##############",
    "##############",
)
FALDA = (("##.###..###.##", "#...##..##...#"),
         ("####.####.####", ".##...##...##."))
OJOS = ((2, 3), (8, 3))
PUPILA = {0: (1, 0), 1: (0, 2), 2: (1, 3), 3: (2, 2)}
OFFSET_OJO = {0: (0, -1), 1: (-1, 0), 2: (0, 1), 3: (1, 0)}


def _cuerpo(color, cuadro):
    filas = CUERPO + FALDA[cuadro]
    claro = tuple(min(255, int(v * 1.0 + 40)) for v in color)
    s = construir(filas, {"#": color})
    for (x, y) in ((4, 1), (3, 2), (2, 3), (2, 4)):
        s.set_at((x, y), claro)
    return s


def _ojos(s, direccion, solo=False):
    ox, oy = OFFSET_OJO[direccion]
    for (x, y) in OJOS:
        x, y = x + ox, y + oy
        blanco = (250, 250, 255)
        pygame.draw.rect(s, blanco, (x + 1, y, 2, 1))
        pygame.draw.rect(s, blanco, (x, y + 1, 4, 3))
        pygame.draw.rect(s, blanco, (x + 1, y + 4, 2, 1))
        px, py = PUPILA[direccion]
        pygame.draw.rect(s, (30, 40, 200), (x + px, y + py, 2, 2))


def fantasma(color, direccion, cuadro):
    s = _cuerpo(color, cuadro)
    _ojos(s, direccion)
    return s


def fantasma_susto(cuadro, blanco=False):
    cuerpo = BLANCO_SUSTO if blanco else AZUL_SUSTO
    cara = (255, 40, 40) if blanco else (255, 200, 170)
    s = _cuerpo(cuerpo, cuadro)
    for x in (4, 9):
        pygame.draw.rect(s, cara, (x, 5, 2, 2))
    boca = ((2, 10), (3, 9), (4, 9), (5, 10), (6, 10), (7, 9), (8, 9), (9, 10), (10, 10), (11, 9))
    for (x, y) in boca:
        s.set_at((x, y), cara)
    return s


def solo_ojos(direccion):
    s = pygame.Surface((14, 14), pygame.SRCALPHA)
    _ojos(s, direccion)
    return s


FRUTAS = (
    ("cereza", (
        ".......gg...",
        "......g.g...",
        ".....g..g...",
        "....g...g...",
        "..RRg..g....",
        ".RRRRRRRR...",
        ".RWRRRRWRR..",
        ".RRRRRRRRR..",
        "..RRRRRRRR..",
        "...RR..RR...",
    ), {"R": (230, 20, 40), "W": (255, 200, 200), "g": (120, 200, 60)}),
    ("fresa", (
        "....gGGg....",
        "..RRgGGgRR..",
        ".RRRRRRRRRR.",
        ".RyRRRyRRyR.",
        ".RRRRRRRRRR.",
        "..RyRRyRRR..",
        "..RRRRRRyR..",
        "...RRyRRR...",
        "....RRRR....",
        ".....RR.....",
    ), {"R": (240, 40, 60), "y": (255, 240, 160), "g": (60, 160, 50), "G": (120, 220, 80)}),
    ("naranja", (
        ".....gG.....",
        "....gGGg....",
        "..OOOOOOOO..",
        ".OOWOOOOOOO.",
        ".OWOOOOOOOO.",
        ".OOOOOOOOOO.",
        ".OOOOOOOOoO.",
        "..OOOOOOoO..",
        "...OOOOOO...",
    ), {"O": (255, 150, 30), "o": (220, 110, 20), "W": (255, 220, 150), "g": (50, 140, 50),
        "G": (110, 210, 80)}),
    ("manzana", (
        "......b.....",
        ".....b.GG...",
        "..RRRbRRG...",
        ".RRRRRRRRR..",
        ".RWRRRRRRR..",
        ".RWRRRRRRR..",
        ".RRRRRRRRR..",
        "..RRRRRRR...",
        "...RR.RR....",
    ), {"R": (220, 30, 30), "W": (255, 190, 190), "b": (130, 80, 30), "G": (90, 200, 70)}),
    ("uvas", (
        ".....gG.....",
        "....g.......",
        "..PpPpPp....",
        ".PpPpPpPp...",
        "..PpPpPp....",
        "...PpPpP....",
        "....PpP.....",
        ".....P......",
    ), {"P": (150, 60, 200), "p": (200, 130, 240), "g": (60, 150, 50), "G": (120, 210, 80)}),
    ("campana", (
        ".....YY.....",
        "....YYYY....",
        "...YWYYYY...",
        "...YWYYYY...",
        "..YYYYYYYY..",
        "..YYYYYYYY..",
        ".YYYYYYYYYY.",
        ".BBBBBBBBBB.",
        ".....CC.....",
    ), {"Y": (255, 210, 40), "W": (255, 250, 200), "B": (80, 160, 255), "C": (230, 230, 240)}),
    ("llave", (
        "...CCCCC....",
        "..CC...CC...",
        "..CC...CC...",
        "...CCCCC....",
        ".....C......",
        ".....CC.....",
        ".....C......",
        ".....CC.....",
        ".....C......",
    ), {"C": (120, 220, 255)}),
)


def frutas():
    return [construir(p, pal) for _, p, pal in FRUTAS]


def _disco(r):
    k = int(math.ceil(r))
    return [(dx, dy) for dx in range(-k, k + 1) for dy in range(-k, k + 1) if dx * dx + dy * dy <= r * r]


def _erosion(m, r, fuera=True):
    h, w = m.shape
    k = int(math.ceil(r))
    p = np.pad(m, k, constant_values=fuera)
    out = np.ones_like(m)
    for dx, dy in _disco(r):
        out &= p[k + dy:k + dy + h, k + dx:k + dx + w]
    return out


def _dilatacion(m, r):
    return ~_erosion(~m, r, fuera=False)


def paredes(grid, ts, color, claro, fondo=(0, 0, 0)):
    filas, cols = len(grid), len(grid[0])
    pared = np.array([[ch in "#H-" for ch in fila] for fila in grid])
    m = np.repeat(np.repeat(pared, ts, 0), ts, 1)
    adentro = _erosion(m, ts * 0.3)
    abierto = _dilatacion(_erosion(adentro, 2.0), 2.0)
    delgado = adentro & ~_dilatacion(abierto, 2.0)
    region = abierto | delgado
    linea = region & ~_erosion(region, 1.0)
    brillo = _dilatacion(linea, 1.5) & ~linea
    h, w = m.shape
    img = np.zeros((h, w, 3), dtype=float)
    img[:] = fondo
    col, cl = np.array(color, float), np.array(claro, float)
    img[region] = img[region] * 0.4 + col * 0.13
    img[brillo] = img[brillo] * 0.5 + col * 0.45
    img[linea] = cl * 0.55 + col * 0.45
    s = pygame.Surface((w, h))
    pygame.surfarray.blit_array(s, np.clip(img, 0, 255).astype(np.uint8).transpose(1, 0, 2))
    casa = [(r, c) for r, fila in enumerate(grid) for c, ch in enumerate(fila) if ch == "H"]
    if casa:
        r0, r1 = min(r for r, _ in casa), max(r for r, _ in casa)
        c0, c1 = min(c for _, c in casa), max(c for _, c in casa)
        caja = pygame.Rect(c0 * ts - 3, r0 * ts - 3, (c1 - c0 + 1) * ts + 6, (r1 - r0 + 1) * ts + 6)
        pygame.draw.rect(s, fondo, caja)
        linea_col = tuple(int(v) for v in np.clip(cl * 0.55 + col * 0.45, 0, 255))
        pygame.draw.rect(s, linea_col, caja, 1, border_radius=2)
        pygame.draw.rect(s, linea_col, caja.inflate(-4, -4), 1, border_radius=1)
    for r, fila in enumerate(grid):
        for c, ch in enumerate(fila):
            if ch == "-":
                pygame.draw.rect(s, fondo, (c * ts, r * ts, ts, ts))
                pygame.draw.rect(s, (255, 184, 222), (c * ts, r * ts + ts - 6, ts, 3))
    return s


_GLIFOS = {
    "0": ("01110", "10001", "10011", "10101", "11001", "10001", "01110"),
    "1": ("00100", "01100", "00100", "00100", "00100", "00100", "01110"),
    "2": ("01110", "10001", "00001", "00110", "01000", "10000", "11111"),
    "3": ("11110", "00001", "00001", "01110", "00001", "00001", "11110"),
    "4": ("00010", "00110", "01010", "10010", "11111", "00010", "00010"),
    "5": ("11111", "10000", "11110", "00001", "00001", "10001", "01110"),
    "6": ("00110", "01000", "10000", "11110", "10001", "10001", "01110"),
    "7": ("11111", "00001", "00010", "00100", "01000", "01000", "01000"),
    "8": ("01110", "10001", "10001", "01110", "10001", "10001", "01110"),
    "9": ("01110", "10001", "10001", "01111", "00001", "00010", "01100"),
    "A": ("01110", "10001", "10001", "11111", "10001", "10001", "10001"),
    "B": ("11110", "10001", "10001", "11110", "10001", "10001", "11110"),
    "C": ("01110", "10001", "10000", "10000", "10000", "10001", "01110"),
    "D": ("11100", "10010", "10001", "10001", "10001", "10010", "11100"),
    "E": ("11111", "10000", "10000", "11110", "10000", "10000", "11111"),
    "F": ("11111", "10000", "10000", "11110", "10000", "10000", "10000"),
    "G": ("01110", "10001", "10000", "10111", "10001", "10001", "01111"),
    "H": ("10001", "10001", "10001", "11111", "10001", "10001", "10001"),
    "I": ("01110", "00100", "00100", "00100", "00100", "00100", "01110"),
    "J": ("00111", "00010", "00010", "00010", "00010", "10010", "01100"),
    "K": ("10001", "10010", "10100", "11000", "10100", "10010", "10001"),
    "L": ("10000", "10000", "10000", "10000", "10000", "10000", "11111"),
    "M": ("10001", "11011", "10101", "10101", "10001", "10001", "10001"),
    "N": ("10001", "10001", "11001", "10101", "10011", "10001", "10001"),
    "O": ("01110", "10001", "10001", "10001", "10001", "10001", "01110"),
    "P": ("11110", "10001", "10001", "11110", "10000", "10000", "10000"),
    "Q": ("01110", "10001", "10001", "10001", "10101", "10010", "01101"),
    "R": ("11110", "10001", "10001", "11110", "10100", "10010", "10001"),
    "S": ("01111", "10000", "10000", "01110", "00001", "00001", "11110"),
    "T": ("11111", "00100", "00100", "00100", "00100", "00100", "00100"),
    "U": ("10001", "10001", "10001", "10001", "10001", "10001", "01110"),
    "V": ("10001", "10001", "10001", "10001", "10001", "01010", "00100"),
    "W": ("10001", "10001", "10001", "10101", "10101", "10101", "01010"),
    "X": ("10001", "10001", "01010", "00100", "01010", "10001", "10001"),
    "Y": ("10001", "10001", "01010", "00100", "00100", "00100", "00100"),
    "Z": ("11111", "00001", "00010", "00100", "01000", "10000", "11111"),
    " ": ("00000",) * 7,
    ".": ("00000", "00000", "00000", "00000", "00000", "01100", "01100"),
    ":": ("00000", "01100", "01100", "00000", "01100", "01100", "00000"),
    "-": ("00000", "00000", "00000", "11111", "00000", "00000", "00000"),
    "+": ("00000", "00100", "00100", "11111", "00100", "00100", "00000"),
    "/": ("00001", "00010", "00010", "00100", "01000", "01000", "10000"),
    "%": ("11001", "11010", "00010", "00100", "01000", "01011", "10011"),
    "!": ("00100", "00100", "00100", "00100", "00100", "00000", "00100"),
    "#": ("01010", "11111", "01010", "01010", "01010", "11111", "01010"),
    "*": ("00000", "10101", "01110", "11111", "01110", "10101", "00000"),
    "<": ("00010", "00100", "01000", "10000", "01000", "00100", "00010"),
    ">": ("01000", "00100", "00010", "00001", "00010", "00100", "01000"),
    "?": ("01110", "10001", "00001", "00110", "00100", "00000", "00100"),
}
_ACENTOS = str.maketrans("ÁÉÍÓÚÜÑáéíóúüñ", "AEIOUUNAEIOUUN")


class FuentePixel:

    def __init__(self):
        self._cache = {}

    def texto(self, s, color, escala=1, sombra=(0, 0, 0)):
        s = str(s).translate(_ACENTOS).upper()
        clave = (s, color, escala, sombra)
        if clave in self._cache:
            return self._cache[clave]
        ancho = max(1, len(s) * 6 - 1)
        surf = pygame.Surface((ancho + 1, 8), pygame.SRCALPHA)
        for i, ch in enumerate(s):
            g = _GLIFOS.get(ch, _GLIFOS["?"])
            for y, fila in enumerate(g):
                for x, b in enumerate(fila):
                    if b == "1":
                        if sombra is not None:
                            surf.set_at((i * 6 + x + 1, y + 1), sombra)
                        surf.set_at((i * 6 + x, y), color)
        if escala != 1:
            surf = pygame.transform.scale(surf, (surf.get_width() * escala, surf.get_height() * escala))
        if len(self._cache) > 600:
            self._cache.clear()
        self._cache[clave] = surf
        return surf
