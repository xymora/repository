import hashlib
import heapq
import math
import os
import pickle

import config as C
from fisica import angulo_normal, avanzar_pose, choca, esquinas_pose

CARPETA = os.path.dirname(os.path.abspath(__file__))
INF = float("inf")


def _firma(esc):
    datos = repr((esc.modo, esc.cajon, esc.estacionados, C.LOTE_ANCHO, C.LOTE_ALTO,
                  C.AUTO_LARGO, C.AUTO_ANCHO, C.DIST_EJES, C.GIRO_MAX,
                  C.MAPA_RES, C.MAPA_ANGULOS, C.MAPA_PASO, C.MAPA_COSTO_REVERSA,
                  ))
    return hashlib.sha1(datos.encode()).hexdigest()


class MapaCosto:
    def __init__(self, escenario, avisar=print):
        self.esc = escenario
        res = C.MAPA_RES
        cx, cy = escenario.centro_cajon
        self.x0 = cx % res
        self.y0 = cy % res
        self.nx = int((C.LOTE_ANCHO - self.x0) / res) + 1
        self.ny = int((C.LOTE_ALTO - self.y0) / res) + 1
        self.na = C.MAPA_ANGULOS

        firma = _firma(escenario)
        archivo = os.path.join(CARPETA, f"mapa_costo_{escenario.modo}.pkl")
        if os.path.exists(archivo):
            try:
                with open(archivo, "rb") as f:
                    guardado = pickle.load(f)
                if guardado.get("firma") == firma:
                    self.costo = guardado["costo"]
                    self.siguiente = guardado["siguiente"]
                    return
            except (OSError, pickle.UnpicklingError, EOFError, KeyError):
                pass
        avisar(f"Calculando el mapa de costo del modo '{escenario.modo}' "
               "(sólo la primera vez, unos segundos)...")
        self.costo, self.siguiente = self._calcular()
        try:
            with open(archivo, "wb") as f:
                pickle.dump({"firma": firma, "costo": self.costo,
                             "siguiente": self.siguiente}, f)
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

    def _calcular(self):
        esc = self.esc
        total = self.nx * self.ny * self.na
        libre = bytearray(total)
        for k in range(self.na):
            for j in range(self.ny):
                for i in range(self.nx):
                    if not choca(esc, esquinas_pose(*self._pose(i, j, k))):
                        libre[self._indice(i, j, k)] = 1

        maniobras = [(d, g) for d in (1, -1) for g in (-C.GIRO_MAX, 0.0, C.GIRO_MAX)]
        previas = [[] for _ in range(total)]
        for k in range(self.na):
            for j in range(self.ny):
                for i in range(self.nx):
                    origen = self._indice(i, j, k)
                    if not libre[origen]:
                        continue
                    x, y, a = self._pose(i, j, k)
                    for sentido, giro in maniobras:
                        dist = sentido * C.MAPA_PASO
                        mx, my, ma = avanzar_pose(x, y, a, dist / 2, giro)
                        nx_, ny_, na_ = avanzar_pose(mx, my, ma, dist / 2, giro)
                        celda = self._celda(nx_, ny_, na_)
                        if celda is None:
                            continue
                        destino = self._indice(*celda)
                        if destino == origen or not libre[destino]:
                            continue
                        if choca(esc, esquinas_pose(mx, my, ma)):
                            continue
                        costo = C.MAPA_PASO * (1.0 if sentido > 0 else C.MAPA_COSTO_REVERSA)
                        previas[destino].append((origen, costo))

        costo = [INF] * total
        siguiente = [-1] * total
        cola = []
        cx, cy = esc.centro_cajon
        for dy in (-0.4, 0.0, 0.4):
            celda = self._celda(cx, cy + dy, esc.angulo_objetivo)
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
                    siguiente[previo] = idx
                    heapq.heappush(cola, (nuevo, previo))
        return costo, siguiente

    def ruta_optima(self, x, y, ang):
        celda = self._celda(x, y, ang)
        if celda is None:
            return []
        idx = self._indice(*celda)
        ruta = []
        while idx != -1 and self.costo[idx] != INF:
            k, resto = divmod(idx, self.nx * self.ny)
            j, i = divmod(resto, self.nx)
            ruta.append((*self._pose(i, j, k), self.costo[idx]))
            idx = self.siguiente[idx]
        return ruta

    def consultar(self, x, y, ang):
        celda = self._celda(x, y, ang)
        if celda is None:
            return None
        c = self.costo[self._indice(*celda)]
        return None if c == INF else c


class MapaRelativo:

    def __init__(self, mapa, desplazamiento):
        self.mapa = mapa
        self.dx = desplazamiento

    def consultar(self, x, y, ang):
        return self.mapa.consultar(x - self.dx, y, ang)

    def ruta_optima(self, x, y, ang):
        return [(px + self.dx, py, pa, c) for px, py, pa, c in
                self.mapa.ruta_optima(x - self.dx, y, ang)]
