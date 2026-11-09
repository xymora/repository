from dataclasses import dataclass
from functools import lru_cache

import numpy as np

import config as C

W, H = C.ANCHO_VISTA, C.ALTO_VISTA


@dataclass(frozen=True)
class Oleada:
    t: int
    patron: str
    x: float
    n: int
    roja: bool = False
    lado: int = 1


@dataclass
class Mision:
    numero: int
    nombre: str
    descripcion: str
    tema: str
    duracion: int
    vel: float
    fuego: float
    oleadas: list
    islas: list
    nubes: list
    jefe: dict

    @property
    def recorrido(self):
        return self.duracion


PATRONES = {
    1: (("picada", 4), ("curva", 3), ("lateral", 2)),
    2: (("picada", 3), ("curva", 3), ("rizo", 2), ("lateral", 2), ("bombardero", 1)),
    3: (("curva", 3), ("rizo", 3), ("trasera", 2), ("bombardero", 1)),
    4: (("picada", 3), ("rizo", 3), ("trasera", 2), ("lateral", 2), ("bombardero", 2)),
    5: (("curva", 3), ("rizo", 3), ("trasera", 3), ("bombardero", 2), ("pesado", 1)),
    6: (("picada", 3), ("rizo", 3), ("trasera", 3), ("lateral", 2), ("bombardero", 2), ("pesado", 1)),
    7: (("curva", 3), ("rizo", 3), ("trasera", 3), ("bombardero", 2), ("pesado", 2)),
    8: (("picada", 3), ("curva", 3), ("rizo", 3), ("trasera", 3), ("lateral", 2), ("bombardero", 2),
        ("pesado", 2)),
}

DATOS = (
    (1, "Despegue", "primer patrullaje sobre el atolón: cazas sueltos", "dia", 1500, 0.85, 0.5),
    (2, "Mar de coral", "llegan los primeros bombarderos", "dia", 1800, 0.95, 0.65),
    (3, "Atolones", "escuadrillas que atacan por la espalda", "dia", 2000, 1.0, 0.8),
    (4, "Tormenta", "nubes densas y cazas en rizo", "tormenta", 2200, 1.05, 0.9),
    (5, "Archipiélago", "aparecen los bombarderos pesados", "dia", 2400, 1.1, 1.0),
    (6, "Noche", "combate nocturno sobre el océano", "noche", 2500, 1.15, 1.1),
    (7, "Bahía", "la flota enemiga cubre el cielo", "atardecer", 2700, 1.2, 1.2),
    (8, "Ofensiva final", "todo lo que queda del enemigo", "atardecer", 3000, 1.3, 1.35),
)

JEFES = {
    1: {"nombre": "Fortaleza gris", "hp": 60, "torretas": 2, "ataque": "apuntado", "periodo": 40},
    2: {"nombre": "Halcón del mar", "hp": 80, "torretas": 2, "ataque": "abanico", "periodo": 45},
    3: {"nombre": "Coloso de hélice", "hp": 100, "torretas": 4, "ataque": "apuntado", "periodo": 34},
    4: {"nombre": "Señor de la tormenta", "hp": 110, "torretas": 4, "ataque": "anillo", "periodo": 60},
    5: {"nombre": "Ballena de acero", "hp": 130, "torretas": 4, "ataque": "abanico", "periodo": 40},
    6: {"nombre": "Sombra nocturna", "hp": 140, "torretas": 4, "ataque": "anillo", "periodo": 50},
    7: {"nombre": "Almirante", "hp": 160, "torretas": 6, "ataque": "abanico", "periodo": 36},
    8: {"nombre": "Último titán", "hp": 200, "torretas": 6, "ataque": "anillo", "periodo": 40},
}


def _construir(numero):
    numero, nombre, descripcion, tema, duracion, vel, fuego = DATOS[numero - 1]
    rng = np.random.default_rng(1942 + numero)
    catalogo = PATRONES[numero]
    patrones = [p for p, peso in catalogo for _ in range(peso)]
    oleadas = []
    t = 70
    hueco = max(34, 62 - 4 * numero)
    k = 0
    while t < duracion - 60:
        patron = patrones[int(rng.integers(len(patrones)))]
        x = float(rng.uniform(40, W - 40))
        lado = 1 if rng.random() < 0.5 else -1
        if patron in ("bombardero", "pesado"):
            n = 1 if patron == "pesado" else int(rng.integers(1, 3))
            oleadas.append(Oleada(t, patron, x, n, False, lado))
            t += hueco + (40 if patron == "pesado" else 20)
            continue
        roja = k % 4 == 3
        n = 5 if roja else int(rng.integers(2, 4 + numero // 3))
        oleadas.append(Oleada(t, patron, x, n, roja, lado))
        k += 1
        t += hueco + int(rng.integers(0, 24))
    islas = []
    y = 120.0
    while y < duracion * C.VEL_FONDO + H * 2:
        islas.append((y, float(rng.uniform(-20, W + 20)), int(rng.integers(4)), bool(rng.random() < 0.5)))
        y += float(rng.uniform(150, 320))
    nubes = []
    y = 60.0
    densidad = 70 if tema == "tormenta" else 140
    while y < duracion * C.VEL_FONDO * 1.6 + H * 3:
        nubes.append((y, float(rng.uniform(-40, W + 40)), int(rng.integers(3))))
        y += float(rng.uniform(densidad * 0.6, densidad * 1.4))
    return Mision(numero, nombre, descripcion, tema, duracion, vel, fuego, oleadas, islas, nubes, JEFES[numero])


@lru_cache(maxsize=None)
def cargar_mision(numero):
    return _construir(max(1, min(numero, len(DATOS))))


NUMERO_MISIONES = len(DATOS)
NOMBRES = tuple(d[1] for d in DATOS)
