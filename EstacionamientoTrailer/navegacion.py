import hashlib
import heapq
import math
import os
import pickle

import config as C
from fisica import angulo_normal, caja_orientada, choca

CARPETA = os.path.dirname(os.path.abspath(__file__))
INF = float("inf")
MARGEN_FONDO = 0.8


def dimensiones_guia(modo, remolques):
    spec = C.TRACTOR if modo == "frente" else C.REMOLQUES[remolques][-1]
    return spec["frente"] + spec["atras"], spec["ancho"]


def _arco(x, y, ang, distancia, curvatura):
    if abs(curvatura) < 1e-9:
        return x + distancia * math.cos(ang), y + distancia * math.sin(ang), ang
    nuevo = ang + distancia * curvatura
    r = 1 / curvatura
    return (x + r * (math.sin(nuevo) - math.sin(ang)),
            y - r * (math.cos(nuevo) - math.cos(ang)), angulo_normal(nuevo))


class MapaCosto:
    def __init__(self, escenario, avisar=print, solo_revisar=False):
        self.esc = escenario
        self.largo, self.ancho = dimensiones_guia(escenario.modo, escenario.remolques)
        self.radio = C.MAPA_RADIO[escenario.modo]
        res = C.MAPA_RES
        cx, _ = escenario.centro_cajon
        self.meta = (cx, MARGEN_FONDO + self.largo / 2, -math.pi / 2)
        self.x0 = cx % res
        self.y0 = self.meta[1] % res
        self.nx = int((C.LOTE_ANCHO - self.x0) / res) + 1
        self.ny = int((C.LOTE_ALTO - self.y0) / res) + 1
        self.na = C.MAPA_ANGULOS

        firma = hashlib.sha1(repr((
            escenario.modo, escenario.remolques, escenario.cajon, escenario.estacionados,
            escenario.tamano,
            C.LOTE_ANCHO, C.LOTE_ALTO, self.largo, self.ancho, self.radio, MARGEN_FONDO,
            C.MAPA_RES, C.MAPA_ANGULOS, C.MAPA_PASO, C.MAPA_COSTO_REVERSA)).encode()).hexdigest()
        archivo = os.path.join(CARPETA, f"mapa_costo_{escenario.modo}_{escenario.remolques}r_"
                                        f"{escenario.tamano}.pkl")
        if os.path.exists(archivo):
            try:
                with open(archivo, "rb") as f:
                    guardado = pickle.load(f)
                if guardado.get("firma") == firma:
                    self.costo = guardado["costo"]
                    return
            except (OSError, pickle.UnpicklingError, EOFError, KeyError):
                pass
        if solo_revisar:
            self.costo = None
            return
        avisar(f"Calculando el mapa de costo ({escenario.modo}, {escenario.remolques} "
               f"remolque(s), cajón {escenario.tamano}); sólo la primera vez, puede tardar "
               "~30 s...")
        self.costo = self._calcular()
        try:
            with open(archivo, "wb") as f:
                pickle.dump({"firma": firma, "costo": self.costo}, f)
        except OSError:
            pass

    def _indice(self, i, j, k):
        return (k * self.ny + j) * self.nx + i

    def _pose(self, i, j, k):
        return (self.x0 + i * C.MAPA_RES, self.y0 + j * C.MAPA_RES,
                angulo_normal(k * 2 * math.pi / self.na))

    def _celda(self, x, y, ang):
        i = round((x - self.x0) / C.MAPA_RES)
        j = round((y - self.y0) / C.MAPA_RES)
        k = round(angulo_normal(ang) / (2 * math.pi) * self.na) % self.na
        if 0 <= i < self.nx and 0 <= j < self.ny:
            return i, j, k
        return None

    def _choca(self, x, y, ang):
        mitad = self.largo / 2
        return choca(self.esc, caja_orientada(x, y, ang, mitad, mitad, self.ancho))

    def _calcular(self):
        total = self.nx * self.ny * self.na
        libre = bytearray(total)
        for k in range(self.na):
            for j in range(self.ny):
                for i in range(self.nx):
                    if not self._choca(*self._pose(i, j, k)):
                        libre[self._indice(i, j, k)] = 1

        curv = 1 / self.radio
        maniobras = [(d, g) for d in (1, -1) for g in (-curv, 0.0, curv)]
        previas = [[] for _ in range(total)]
        for k in range(self.na):
            for j in range(self.ny):
                for i in range(self.nx):
                    origen = self._indice(i, j, k)
                    if not libre[origen]:
                        continue
                    x, y, a = self._pose(i, j, k)
                    for sentido, cv in maniobras:
                        dist = sentido * C.MAPA_PASO
                        mx, my, ma = _arco(x, y, a, dist / 2, cv)
                        fx, fy, fa = _arco(mx, my, ma, dist / 2, cv)
                        celda = self._celda(fx, fy, fa)
                        if celda is None:
                            continue
                        destino = self._indice(*celda)
                        if destino == origen or not libre[destino] or self._choca(mx, my, ma):
                            continue
                        costo = C.MAPA_PASO * (1.0 if sentido > 0 else C.MAPA_COSTO_REVERSA)
                        previas[destino].append((origen, costo))

        costo = [INF] * total
        cola = []
        mx, my, ma = self.meta
        for dy in (-1.0, -0.5, 0.0, 0.5, 1.0):
            celda = self._celda(mx, my + dy, ma)
            if celda and libre[self._indice(*celda)]:
                idx = self._indice(*celda)
                costo[idx] = 0.0
                heapq.heappush(cola, (0.0, idx))
        while cola:
            c, idx = heapq.heappop(cola)
            if c > costo[idx]:
                continue
            for previo, paso in previas[idx]:
                nuevo = c + paso
                if nuevo < costo[previo]:
                    costo[previo] = nuevo
                    heapq.heappush(cola, (nuevo, previo))
        return costo

    def consultar(self, x, y, ang):
        celda = self._celda(x, y, ang)
        if celda is None:
            return None
        c = self.costo[self._indice(*celda)]
        return None if c == INF else c


def mapa_listo(escenario):
    return MapaCosto(escenario, solo_revisar=True).costo is not None


def precalcular(modo, remolques, tamanos):
    from fisica import Escenario
    for tamano in tamanos:
        MapaCosto(Escenario(modo, remolques, tamano=tamano))


class MapaRelativo:

    def __init__(self, mapa, desplazamiento):
        self.mapa = mapa
        self.dx = desplazamiento

    def consultar(self, x, y, ang):
        return self.mapa.consultar(x - self.dx, y, ang)
