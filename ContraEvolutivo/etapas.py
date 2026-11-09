from dataclasses import dataclass, field
from functools import lru_cache

import numpy as np

import config as C

VACIO, SOLIDO, PLATAFORMA, AGUA, PINCHO, PUENTE, BARRERA = range(7)
FILAS = C.ALTO_VISTA // C.TILE


@dataclass
class Aparicion:
    activar: float
    tipo: str
    x: float
    y: float
    datos: dict


@dataclass
class Oleada:
    desde: float
    hasta: float
    periodo: int
    tipo: str
    lado: int


@dataclass
class Etapa:
    numero: int
    nombre: str
    tema: str
    descripcion: str
    vertical: bool
    tiles: np.ndarray
    inicio: tuple
    apariciones: list
    oleadas: list
    grupos: dict
    jefe: str

    @property
    def ancho_px(self):
        return self.tiles.shape[1] * C.TILE

    @property
    def alto_px(self):
        return self.tiles.shape[0] * C.TILE

    @property
    def recorrido(self):
        if self.vertical:
            return self.alto_px - C.ALTO_VISTA
        return self.ancho_px - C.ANCHO_VISTA


class Constructor:
    def __init__(self, columnas, filas=FILAS):
        self.filas = filas
        self.t = np.zeros((filas, columnas), dtype=np.uint8)
        self.enemigos = []
        self.oleadas = []
        self.grupos = {}

    def suelo(self, c0, c1, alto, tipo=SOLIDO):
        self.t[self.filas - alto:, c0:c1] = tipo

    def bloque(self, c0, f0, ancho, alto, tipo=SOLIDO):
        self.t[f0:f0 + alto, c0:c0 + ancho] = tipo

    def plataforma(self, c0, c1, fila):
        self.t[fila, c0:c1] = PLATAFORMA

    def agua(self, c0, c1):
        self.t[self.filas - 2:, c0:c1] = AGUA

    def puente(self, c0, c1, fila, grupo):
        self.t[fila, c0:c1] = PUENTE
        self.grupos[grupo] = [(fila, c) for c in range(c0, c1)]

    def barrera(self, col, f0, f1, grupo):
        self.t[f0:f1, col] = BARRERA
        self.grupos[grupo] = [(f, col) for f in range(f0, f1)]

    def enemigo(self, tipo, col, fila, **datos):
        self.enemigos.append((tipo, col * C.TILE + C.TILE / 2, fila * C.TILE, datos))

    def oleada(self, desde, hasta, periodo, tipo="soldado", lado=1):
        self.oleadas.append(Oleada(desde * C.TILE, hasta * C.TILE, periodo, tipo, lado))

    def etapa(self, numero, nombre, tema, descripcion, jefe, inicio, vertical=False):
        alto_px = self.filas * C.TILE
        base = alto_px - C.ALTO_VISTA
        apariciones = []
        for tipo, x, y, datos in self.enemigos:
            activar = base - y + 24 if vertical else x - C.ANCHO_VISTA - 24
            apariciones.append(Aparicion(max(activar, 0), tipo, x, y, datos))
        apariciones.sort(key=lambda a: a.activar)
        col, fila = inicio
        return Etapa(numero, nombre, tema, descripcion, vertical, self.t, (col * C.TILE + 8, fila * C.TILE),
                     apariciones, self.oleadas, self.grupos, jefe)


def _jungla():
    b = Constructor(200)
    b.agua(0, 200)
    b.suelo(0, 24, 4)
    b.plataforma(13, 20, 6)
    b.suelo(26, 34, 5)
    b.puente(34, 42, 9, 1)
    b.suelo(42, 58, 5)
    b.plataforma(46, 54, 6)
    b.plataforma(59, 60, 10)
    b.suelo(60, 68, 7)
    b.suelo(68, 78, 4)
    b.puente(78, 86, 10, 2)
    b.suelo(86, 108, 4)
    b.plataforma(92, 100, 7)
    b.plataforma(101, 107, 4)
    b.suelo(111, 124, 5)
    b.suelo(127, 140, 4)
    b.plataforma(131, 138, 7)
    b.plataforma(141, 142, 10)
    b.suelo(142, 160, 6)
    b.plataforma(148, 156, 5)
    b.suelo(162, 200, 4)
    b.bloque(196, 0, 4, 10)
    for col, fila in ((10, 10), (17, 6), (50, 6), (64, 7), (95, 7), (104, 4), (135, 7), (152, 5), (170, 10)):
        b.enemigo("francotirador", col, fila)
    b.enemigo("torreta", 118, 9)
    b.enemigo("torreta", 146, 8)
    b.enemigo("canon", 157, 8)
    b.enemigo("canon", 75, 10)
    for col, fila, letra in ((20, 4, "M"), (70, 4, "S"), (115, 3, "L"), (150, 3, "F")):
        b.enemigo("capsula", col, fila, letra=letra)
    b.enemigo("caja", 55, 9, letra="R")
    b.enemigo("caja", 90, 10, letra="S")
    b.oleada(0, 164, 55)
    b.oleada(50, 140, 150, lado=-1)
    return b.etapa(1, "Jungla", "jungla", "selva, río y puentes que explotan", "muro", (3, 10))


def _base(numero, nombre, columnas, barreras, plataformas, jefe, cajas):
    b = Constructor(columnas)
    b.bloque(0, 0, columnas, 2)
    b.suelo(0, columnas, 2)
    for c0, c1, fila in plataformas:
        b.plataforma(c0, c1, fila)
    for k, col in enumerate(barreras, start=1):
        b.barrera(col, 2, 12, k)
        b.enemigo("nucleo", col, 12, grupo=k)
        b.enemigo("torreta", col - 8, 3, colgada=True)
        b.enemigo("francotirador", col - 14, 12)
    for c0, c1, fila in plataformas[::2]:
        b.enemigo("francotirador", (c0 + c1) // 2, fila)
    for col, letra in cajas:
        b.enemigo("caja", col, 12, letra=letra)
    b.bloque(columnas - 2, 2, 2, 10)
    b.oleada(0, columnas - 18, 60)
    b.oleada(20, columnas - 30, 160, lado=-1)
    return b.etapa(numero, nombre, "base", "pasillos de la base: destruye cada núcleo para abrir la barrera",
                   jefe, (3, 12))


def _cascada():
    b = Constructor(16, filas=104)
    b.suelo(0, 16, 2)
    b.bloque(0, 0, 1, 104)
    b.bloque(15, 0, 1, 104)
    patrones = ([(1, 7), (9, 15)], [(4, 12)], [(1, 6), (10, 15)], [(6, 13)], [(1, 9)], [(7, 15)])
    for i, fila in enumerate(range(99, 14, -3)):
        for c0, c1 in patrones[i % len(patrones)]:
            b.plataforma(c0, c1, fila)
        if i % 4 == 2:
            c0, c1 = patrones[i % len(patrones)][0]
            b.enemigo("francotirador", c0 + 1, fila)
        if i % 5 == 3:
            b.enemigo("torreta", 14 if i % 2 else 1, fila)
    b.plataforma(1, 15, 12)
    b.enemigo("capsula", 0, 70, letra="M")
    b.enemigo("capsula", 0, 45, letra="S")
    b.enemigo("capsula", 0, 25, letra="L")
    b.oleada(8, 88, 75, tipo="roca")
    return b.etapa(3, "Cascada", "cascada", "escala la cascada esquivando rocas", "cabeza", (3, 102), vertical=True)


def _nieve():
    b = Constructor(220)
    b.suelo(0, 30, 3)
    b.plataforma(10, 18, 8)
    b.suelo(33, 50, 4)
    b.suelo(53, 70, 3)
    b.plataforma(58, 66, 8)
    b.suelo(73, 80, 5)
    b.suelo(80, 100, 3)
    b.plataforma(86, 94, 8)
    b.plataforma(95, 100, 5)
    b.suelo(103, 125, 4)
    b.suelo(128, 150, 3)
    b.plataforma(134, 142, 8)
    b.suelo(153, 170, 5)
    b.suelo(172, 220, 3)
    for col, fila in ((40, 10), (90, 11), (140, 11), (160, 9), (115, 10)):
        b.enemigo("granadero", col, fila)
    for col, fila in ((14, 8), (62, 8), (77, 9), (97, 5), (138, 8), (185, 11)):
        b.enemigo("francotirador", col, fila)
    b.enemigo("torreta", 46, 10)
    b.enemigo("torreta", 120, 10)
    b.enemigo("canon", 165, 9)
    for col, fila, letra in ((25, 4, "S"), (85, 4, "M"), (145, 3, "L")):
        b.enemigo("capsula", col, fila, letra=letra)
    b.enemigo("caja", 105, 10, letra="F")
    b.oleada(0, 190, 60)
    b.oleada(60, 170, 170, lado=-1)
    return b.etapa(5, "Nieve", "nieve", "campo nevado con granaderos y precipicios", "tanque", (3, 11))


def _energia():
    b = Constructor(200)
    b.bloque(0, 0, 200, 2)
    for c0, c1 in ((0, 40), (43, 80), (83, 120), (123, 160), (163, 200)):
        b.suelo(c0, c1, 2)
    for c0, c1 in ((20, 28), (60, 68), (100, 108), (140, 148)):
        b.plataforma(c0, c1, 9)
    for col in (14, 34, 52, 74, 92, 112, 130, 150):
        b.enemigo("llama", col, 2, orientacion="abajo", largo=8, desfase=col * 3)
    for col in (25, 65, 105, 145):
        b.enemigo("llama", col, 12, orientacion="arriba", largo=3, desfase=col * 5)
    for col in (30, 90, 135):
        b.enemigo("canon", col, 12)
    for col in (45, 118, 170):
        b.enemigo("torreta", col, 3, colgada=True)
    for col, fila in ((24, 9), (64, 9), (104, 9), (144, 9)):
        b.enemigo("francotirador", col, fila)
    b.enemigo("capsula", 18, 4, letra="L")
    b.enemigo("capsula", 98, 4, letra="S")
    b.enemigo("caja", 56, 12, letra="M")
    b.bloque(198, 2, 2, 8)
    b.oleada(0, 182, 65)
    return b.etapa(6, "Zona de energía", "energia", "lanzallamas en techo y piso, saltos sobre el vacío",
                   "gigante", (3, 12))


def _hangar():
    b = Constructor(210)
    b.bloque(0, 0, 210, 2)
    b.suelo(0, 210, 2)
    for c0, c1, fila in ((12, 20, 9), (40, 48, 9), (70, 78, 9), (100, 110, 9), (130, 138, 9), (160, 168, 9)):
        b.plataforma(c0, c1, fila)
        b.enemigo("francotirador", (c0 + c1) // 2, fila)
    for col in (28, 56, 86, 118, 148, 178):
        b.enemigo("prensa", col, 2, desfase=col * 2)
    for col in (35, 95, 155):
        b.enemigo("torreta", col, 3, colgada=True)
    for col in (65, 125):
        b.enemigo("canon", col, 12)
    b.enemigo("capsula", 22, 4, letra="S")
    b.enemigo("capsula", 110, 4, letra="M")
    b.enemigo("caja", 80, 12, letra="L")
    b.bloque(208, 2, 2, 10)
    b.oleada(0, 192, 55)
    b.oleada(30, 170, 150, lado=-1)
    return b.etapa(7, "Hangar", "hangar", "prensas hidráulicas y torretas del hangar", "nave", (3, 12))


def _guarida():
    b = Constructor(190)
    b.suelo(0, 190, 3)
    techo = (2, 3, 2, 1, 2, 3, 3, 2, 1, 2)
    for k, c0 in enumerate(range(0, 190, 19)):
        b.bloque(c0, 0, 19, techo[k % len(techo)])
    for c0, alto in ((24, 4), (52, 5), (80, 4), (110, 5), (140, 4)):
        b.suelo(c0, c0 + 8, alto)
    for c0, c1, fila in ((32, 40, 7), (60, 68, 7), (90, 98, 7), (120, 128, 7), (150, 158, 7)):
        b.plataforma(c0, c1, fila)
    for col, fila in ((30, 5), (70, 5), (100, 4), (132, 5), (165, 5)):
        b.enemigo("boca", col, fila)
    for col in (45, 85, 125):
        b.enemigo("francotirador", col, 11)
    b.enemigo("capsula", 20, 6, letra="S")
    b.enemigo("capsula", 105, 6, letra="L")
    b.enemigo("caja", 72, 11, letra="M")
    b.bloque(188, 0, 2, 11)
    b.oleada(0, 172, 45, tipo="larva")
    b.oleada(40, 160, 120, tipo="larva", lado=-1)
    return b.etapa(8, "Guarida alienígena", "guarida", "el nido del alien: larvas y bocas que las escupen",
                   "corazon", (3, 11))


CONSTRUCTORES = (
    _jungla,
    lambda: _base(2, "Base 1", 180, (38, 76, 114, 152),
                  [(8, 14, 9), (22, 30, 8), (48, 56, 9), (60, 66, 8), (86, 94, 9), (100, 106, 8),
                   (124, 132, 9), (138, 144, 8)], "ojo", ((20, "M"), (95, "S"), (130, "L"))),
    _cascada,
    lambda: _base(4, "Base 2", 200, (30, 64, 98, 132, 166),
                  [(10, 18, 8), (40, 48, 9), (52, 58, 7), (74, 82, 8), (108, 116, 9), (120, 126, 7),
                   (142, 150, 8), (154, 160, 7)], "gemelos", ((16, "S"), (84, "F"), (146, "M"))),
    _nieve,
    _energia,
    _hangar,
    _guarida,
)
NUMERO_ETAPAS = len(CONSTRUCTORES)
NOMBRES = ("Jungla", "Base 1", "Cascada", "Base 2", "Nieve", "Zona de energía", "Hangar", "Guarida alienígena")


@lru_cache(maxsize=None)
def cargar_etapa(numero):
    return CONSTRUCTORES[max(1, min(numero, NUMERO_ETAPAS)) - 1]()
