from dataclasses import dataclass

import numpy as np

NORTE, ESTE, SUR, OESTE = range(4)


@dataclass(frozen=True)
class Nivel:
    numero: int
    nombre: str
    descripcion: str
    muros: np.ndarray
    inicio: tuple
    meta: int

    @property
    def alto(self):
        return self.muros.shape[0]

    @property
    def ancho(self):
        return self.muros.shape[1]

    @property
    def libres(self):
        return int((~self.muros).sum())

    @property
    def hambre_max(self):
        return int(0.8 * self.libres) + 40


def _nivel(numero, nombre, descripcion, ancho, alto, meta, bloques=(), inicio=None):
    muros = np.ones((alto + 2, ancho + 2), dtype=bool)
    muros[1:-1, 1:-1] = False
    for fila, col, h, w in bloques:
        muros[1 + fila:1 + fila + h, 1 + col:1 + col + w] = True
    fila, col = inicio or (alto // 2, 2)
    return Nivel(numero, nombre, descripcion, muros, (fila + 1, col + 1), meta)


NIVELES = (
    _nivel(1, "Jardín", "tablero chico y despejado", 10, 10, 15),
    _nivel(2, "Pradera", "más espacio, frutas más lejos", 14, 14, 25),
    _nivel(3, "Pilares", "cuatro columnas que esquivar", 16, 16, 30,
           [(2, 2, 2, 2), (2, 12, 2, 2), (12, 2, 2, 2), (12, 12, 2, 2)]),
    _nivel(4, "Muros", "dos paredes con pasos angostos", 18, 18, 35,
           [(5, 0, 1, 5), (5, 13, 1, 5), (12, 3, 1, 12)], inicio=(9, 2)),
    _nivel(5, "Cruz", "una cruz parte el tablero en cuartos", 18, 18, 35,
           [(1, 8, 5, 2), (12, 8, 5, 2), (8, 1, 2, 5), (8, 12, 2, 5)], inicio=(3, 2)),
    _nivel(6, "Habitaciones", "cuatro cuartos unidos por puertas", 20, 20, 40,
           [(0, 10, 4, 1), (6, 10, 4, 1), (11, 10, 3, 1), (16, 10, 4, 1),
            (10, 0, 1, 4), (10, 6, 1, 4), (10, 10, 1, 1), (10, 11, 1, 3), (10, 16, 1, 4)],
           inicio=(2, 2)),
    _nivel(7, "Serpentina", "pasillos en zigzag", 20, 20, 40,
           [(4, 0, 1, 16), (9, 4, 1, 16), (14, 0, 1, 16), (17, 9, 3, 2)], inicio=(1, 2)),
    _nivel(8, "Fortaleza", "un fuerte con cuatro puertas y obstáculos", 22, 22, 50,
           [(5, 5, 1, 4), (5, 13, 1, 4), (16, 5, 1, 4), (16, 13, 1, 4),
            (6, 5, 3, 1), (13, 5, 3, 1), (6, 16, 3, 1), (13, 16, 3, 1),
            (2, 2, 1, 2), (2, 18, 1, 2), (19, 2, 1, 2), (19, 18, 1, 2), (10, 10, 2, 2)],
           inicio=(1, 2)),
)


def nivel(numero):
    return NIVELES[max(1, min(numero, len(NIVELES))) - 1]
