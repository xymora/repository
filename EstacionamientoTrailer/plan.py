import math
import random

import config as C

GENES_POR_MANIOBRA = 4 + C.PUNTOS_VOLANTE
TAM_GENOMA = C.MAX_MANIOBRAS * GENES_POR_MANIOBRA


def genoma_aleatorio():
    return [random.uniform(-1, 1) for _ in range(TAM_GENOMA)]


def _escala(g, minimo, maximo):
    g = max(-1.0, min(1.0, g))
    return minimo + (g + 1) / 2 * (maximo - minimo)


class Maniobra:
    __slots__ = ("marcha", "distancia", "velocidad", "volantes")

    def __init__(self, genes):
        _, marcha, distancia, velocidad = genes[:4]
        self.marcha = 1 if marcha > 0 else -1
        self.distancia = _escala(distancia, C.DIST_MIN, C.DIST_MAX)
        tope = C.V_MAX if self.marcha > 0 else C.V_REVERSA
        self.velocidad = _escala(velocidad, C.V_MIN_MANIOBRA, tope)
        self.volantes = tuple(max(-1.0, min(1.0, v)) for v in genes[4:])

    def volante_en(self, fraccion):
        puntos = self.volantes
        t = max(0.0, min(1.0, fraccion)) * (len(puntos) - 1)
        i = min(int(t), len(puntos) - 2)
        return puntos[i] + (puntos[i + 1] - puntos[i]) * (t - i)

    def describir(self):
        if self.marcha < 0 and C.ASISTENTE_REVERSA:
            def ang(v):
                g = v * math.degrees(C.ARTICULACION_PLAN)
                return "  0°" if abs(g) < 0.5 else f"{'←' if g < 0 else '→'}{abs(g):2.0f}°"
            return (f"R {self.distancia:4.1f} m {self.velocidad:3.1f} m/s  remolque "
                    f"{' '.join(ang(v) for v in self.volantes)}")

        def vol(v):
            if abs(v) < 0.05:
                return "  0%"
            return f"{'←' if v < 0 else '→'}{abs(v) * 100:3.0f}%"
        return (f"{'D' if self.marcha > 0 else 'R'} {self.distancia:4.1f} m "
                f"{self.velocidad:3.1f} m/s  volante {' '.join(vol(v) for v in self.volantes)}")


def decodificar(genoma):
    plan = []
    for i in range(0, len(genoma), GENES_POR_MANIOBRA):
        genes = genoma[i:i + GENES_POR_MANIOBRA]
        if genes[0] > 0:
            plan.append(Maniobra(genes))
    return plan
