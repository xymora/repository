import pygame

JUGADOR = (
    ".....rRRRr.....",
    "....rRRYRRr....",
    "...rRRRWRRRr...",
    "..KrRRRWRRRrK..",
    "..KRRRRWRRRRK..",
    "..KRRRrWrRRRK..",
    "...RRGGGGGRR...",
    "...RGgGGGGGR...",
    "...RGGGGGGGR...",
    "...RrGGGGGrR...",
    "...RRRRWRRRR...",
    "...RRRRWRRRR...",
    "...RRRRWRRRR...",
    "...RRRRWRRRR...",
    "...RrRRWRRrR...",
    "...RRGGGGGRR...",
    "...RRrGGGrRR...",
    "..KRRRRWRRRRK..",
    "..KRRRRWRRRRK..",
    "..KrRRRWRRRrK..",
    "..KrrRRWRRrrK..",
    "...rrrrrrrrr...",
    "..DDDDDDDDDDD..",
    "..DLLDDDDDLLD..",
    "...DDDDDDDDD...",
)
PAL_JUGADOR = {"R": (226, 38, 38), "r": (150, 18, 26), "W": (245, 245, 245), "Y": (255, 236, 140),
               "G": (28, 40, 70), "g": (120, 170, 230), "K": (18, 18, 22), "D": (40, 40, 48),
               "L": (255, 70, 70)}

SEDAN = (
    "....cCCCCCc....",
    "...cCCHHHCCc...",
    "..KCCCCCCCCCK..",
    "..KCCCCCCCCCK..",
    "..KcCCCCCCCcK..",
    "...CGGGGGGGC...",
    "...GgGGGGGGG...",
    "...GGGGGGGGG...",
    "...cCCCCCCCc...",
    "...CCCCCCCCC...",
    "...CCHHHHHCC...",
    "...CCCCCCCCC...",
    "...cCCCCCCCc...",
    "...GGGGGGGGG...",
    "...cGGGGGGGc...",
    "..KCCCCCCCCCK..",
    "..KCCCCCCCCCK..",
    "..KcCCCCCCCcK..",
    "...cccccccccc..",
    "...LLcccccLL...",
)
PAL_SEDAN = {"K": (18, 18, 22), "G": (30, 42, 66), "g": (140, 190, 240), "L": (255, 80, 60)}
COLORES_SEDAN = {
    "amarillo": ((250, 206, 56), (190, 140, 20), (255, 240, 170)),
    "azul": ((60, 130, 250), (30, 70, 170), (170, 210, 255)),
    "rojo": ((236, 64, 64), (160, 28, 28), (255, 170, 170)),
    "arcoiris": ((255, 120, 255), (180, 60, 180), (255, 220, 255)),
}

def _camion():
    filas = ["....cCCCCCCCc....",
             "...cCCHHHHHCCc...",
             "..KCCCCCCCCCCCK..",
             "..KCGGGGGGGGGCK..",
             "..KCGgGGGGGGGCK..",
             "...CCCCCCCCCCC...",
             "...cCCCCCCCCCc...",
             "....DDDDDDDDD....",
             "..BBBBBBBBBBBBB.."]
    for k in range(40):
        filas.append("..BbbbbbbbbbbbB.." if k % 5 == 0 else "..BTTTTTTTTTTTB..")
    filas += ["..KBBBBBBBBBBBK..", "..KTTTTTTTTTTTK..", "..KTTTTTTTTTTTK..",
              "..BBBBBBBBBBBBB..", "..LLDDDDDDDDDLL.."]
    return tuple(filas)


CAMION = _camion()
PAL_CAMION = {"C": (60, 150, 90), "c": (34, 96, 56), "H": (150, 220, 170), "K": (18, 18, 22),
              "G": (30, 42, 66), "g": (140, 190, 240), "D": (50, 50, 56), "B": (150, 156, 166),
              "b": (110, 114, 124), "T": (196, 200, 208), "L": (255, 80, 60)}

ARBOL = (
    ".....gGGGg......",
    "...gGGHHGGGg....",
    "..gGGHHHGGGGg...",
    ".gGGGHHGGGGGGg..",
    ".GGGGGGGGGGdGG..",
    "gGGGGGGGGGddGGg.",
    "GGGHGGGGGdddGGG.",
    "GGHHGGGGGGddGGG.",
    "gGGGGGGGGGGGGGg.",
    ".GGGGGGdGGGGGG..",
    ".gGGGGddGGGGGg..",
    "..gGGGGGGGGGg...",
    "...ggGGGGGgg....",
    "......TT........",
    "......TT........",
    ".....TTTT.......",
)
PAL_ARBOL = {"G": (44, 140, 52), "g": (28, 96, 36), "H": (110, 200, 90), "d": (24, 80, 30),
             "T": (110, 72, 40)}
PINO = (
    "......G.......",
    ".....GGG......",
    "....GGHGG.....",
    "...GGGGGGG....",
    ".....GGG......",
    "....GGHGGG....",
    "...GGGGGGGG...",
    "..GGGGGGGGGG..",
    "....GGGGGG....",
    "...GGHGGGGGG..",
    "..GGGGGGGGGGG.",
    ".GGGGGGGGGGGGG",
    "......TT......",
    "......TT......",
)
PAL_PINO = {"G": (30, 110, 70), "H": (90, 170, 110), "T": (100, 66, 40)}
PALMERA = (
    "..H.......H...",
    "...HH...HH....",
    ".HHHHHHHHHHH..",
    "HH..HHHHH..HH.",
    "H..HH.T.HH..H.",
    "..H...T...H...",
    "......T.......",
    ".....TT.......",
    ".....T........",
    ".....TT.......",
    "......T.......",
    "......TT......",
    ".......T......",
    "......TTT.....",
)
PAL_PALMERA = {"H": (40, 160, 70), "T": (150, 104, 56)}
ARBUSTO = (
    "..gGGGg...",
    ".gGHHGGg..",
    "gGGGGGdGg.",
    "GGGGGdddGg",
    ".ggGGGGgg.",
)
PAL_ARBUSTO = {"G": (52, 150, 56), "g": (32, 104, 40), "H": (120, 210, 100), "d": (26, 86, 32)}
ROCA = (
    "....aAAAa...",
    "..aAAHHAAAa.",
    ".aAAHHAAAAAa",
    "aAAAAAAAdAAa",
    "aAAAAAAddAAa",
    ".aAAAAdddAa.",
    "..aaaaaaaa..",
)
PAL_ROCA = {"A": (130, 122, 110), "a": (88, 82, 74), "H": (190, 182, 168), "d": (96, 90, 82)}
FLOR = (".Y.", "YOY", ".Y.")
PAL_FLOR = {"Y": (255, 230, 90), "O": (240, 120, 40)}
BOTE = (
    "...W...",
    "..WWW..",
    ".WWWWW.",
    ".BBBBB.",
    "BBBBBBB",
    ".BBBBB.",
    "..BBB..",
)
PAL_BOTE = {"W": (240, 240, 240), "B": (180, 70, 40)}
ACEITE = (
    "....kkkkk.....",
    "..kkkKKKkkkk..",
    ".kkKKKKKKKKkk.",
    "kkKKKSSKKKKKkk",
    "kKKKSSKKKKKKKk",
    "kkKKKKKKKKKKkk",
    ".kkKKKKKKKKkk.",
    "..kkkkKKkkkk..",
    ".....kkkk.....",
)
PAL_ACEITE = {"k": (26, 26, 32), "K": (12, 12, 16), "S": (90, 80, 140)}


BARRERA = (
    "K..............K",
    "WWRRWWRRWWRRWWRR",
    "WRRWWRRWWRRWWRRW",
    "RRWWRRWWRRWWRRWW",
    "K..............K",
    "K..............K",
)
PAL_BARRERA = {"W": (245, 245, 245), "R": (220, 40, 40), "K": (40, 40, 44)}
CONOS = (
    "...o......o......o..",
    "..oOo....oOo....oOo.",
    "..WWW....WWW....WWW.",
    ".oOOOo..oOOOo..oOOOo",
    ".WWWWW..WWWWW..WWWWW",
    "oOOOOOooOOOOOooOOOOO",
    "KKKKKKKKKKKKKKKKKKKK",
)
PAL_CONOS = {"o": (200, 90, 20), "O": (255, 130, 30), "W": (250, 250, 250), "K": (50, 50, 54)}
ROCA_GRANDE = (
    "....aaAAAaa.....",
    "..aAAAHHAAAAa...",
    ".aAAAHHHAAAAAa..",
    "aAAAAHAAAAAAdAa.",
    "aAAAAAAAAAAddAAa",
    "aAAAAAAAAAdddAAa",
    ".aAAAAAAAddddAa.",
    "..aaAAAAAAAAaa..",
    "....aaaaaaaa....",
)


def construir(plantilla, paleta):
    alto, ancho = len(plantilla), max(len(f) for f in plantilla)
    s = pygame.Surface((ancho, alto), pygame.SRCALPHA)
    for y, fila in enumerate(plantilla):
        for x, ch in enumerate(fila):
            if ch != "." and ch in paleta:
                s.set_at((x, y), paleta[ch])
    return s


def sedan(nombre):
    c, sombra, brillo = COLORES_SEDAN[nombre]
    pal = dict(PAL_SEDAN, C=c, c=sombra, H=brillo)
    return construir(SEDAN, pal)


def sedan_color(c, sombra, brillo):
    return construir(SEDAN, dict(PAL_SEDAN, C=c, c=sombra, H=brillo))


def fantasma(sprite, color=(170, 190, 215), alfa=90):
    s = sprite.copy()
    s.fill((0, 0, 0, 255), special_flags=pygame.BLEND_RGBA_MULT)
    s.fill(color + (0,), special_flags=pygame.BLEND_RGBA_ADD)
    s.set_alpha(alfa)
    return s


def tenir(sprite, color):
    s = sprite.copy()
    arr = pygame.PixelArray(s)
    for viejo, factor in ((PAL_JUGADOR["R"], 1.0), (PAL_JUGADOR["r"], 0.6)):
        nuevo = tuple(int(v * factor) for v in color)
        arr.replace(viejo, nuevo)
    del arr
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
