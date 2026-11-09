import heapq
import math
from array import array

import config as C

INF = float("inf")
BLOQUEO = 400.0
VECINOS = [(1, 0, 1.0), (-1, 0, 1.0), (0, 1, 1.0), (0, -1, 1.0),
           (1, 1, math.sqrt(2)), (1, -1, math.sqrt(2)), (-1, 1, math.sqrt(2)),
           (-1, -1, math.sqrt(2))]

TRAMOS = {
    "Salida": "#80cbc4", "Crucero": "#4fc3f7", "Ascenso": "#ffb74d",
    "Descenso": "#aed581", "Sobrevuelo alto": "#ff8a65", "Cruce de cables": "#fff176",
    "Rodeo de zona prohibida": "#ef5350", "Aproximación": "#ce93d8",
    "Transición a avión": "#a1887f", "Transición a vertical": "#f48fb1",
}


class Mapa:

    def __init__(self, ciudad):
        self.ciudad = ciudad
        self.nx = int(math.ceil(ciudad.ancho / C.CELDA))
        self.ny = int(math.ceil(ciudad.alto / C.CELDA))
        n = self.nx * self.ny
        self.obst = array("f", bytes(4 * n))
        self.cable = array("f", bytes(4 * n))
        self.req = array("f", bytes(4 * n))
        self.bloq = bytearray(n)
        self.cerca_zona = bytearray(n)
        sv = C.SEPARACION_VERTICAL
        self._rasterizar_edificios(ciudad)
        for a in ciudad.antenas:
            r = C.RADIO_ANTENA
            for c in self._celdas_caja(a.x - r, a.y - r, a.x + r, a.y + r):
                x, y = self.centro(c)
                if math.hypot(x - a.x, y - a.y) <= r and a.h > self.obst[c]:
                    self.obst[c] = a.h
        for l in ciudad.lineas:
            r = C.SEPARACION_HORIZONTAL
            for c in self._celdas_caja(min(l.x0, l.x1) - r, min(l.y0, l.y1) - r,
                                       max(l.x0, l.x1) + r, max(l.y0, l.y1) + r):
                x, y = self.centro(c)
                d, _ = l.cercania(x, y)
                if d <= r:
                    self.cable[c] = max(self.cable[c], l.altura)
                    if any(math.hypot(x - tx, y - ty) < r for tx, ty in l.torres):
                        self.obst[c] = max(self.obst[c], l.altura + 3)
        for i in range(n):
            self.req[i] = max(self.obst[i] + sv if self.obst[i] > 0 else 0.0,
                              self.cable[i] + C.SEPARACION_CABLES if self.cable[i] > 0 else 0.0)
            if self.req[i] > C.TECHO:
                self.bloq[i] = 1
        for z in ciudad.prohibidas:
            m = C.MARGEN_ZONA
            for c in self._celdas_caja(*z.caja(m + 80)):
                d = z.distancia(*self.centro(c))
                if d < m:
                    self.bloq[c] = 1
                if d < 80:
                    self.cerca_zona[c] = 1
        self.costo = array("f", (BLOQUEO if self.bloq[i] else
                                 1.0 + C.PESO_ALTURA * max(0.0, self.req[i] - C.ALTURA_CRUCERO) / 100
                                 for i in range(n)))

    def _rasterizar_edificios(self, ciudad):
        from PIL import Image, ImageChops, ImageDraw, ImageFilter

        f = C.CELDA / 2
        W, H = self.nx * 2, self.ny * 2
        edif = Image.new("L", (W, H), 0)
        d = ImageDraw.Draw(edif)
        for e in sorted(ciudad.edificios, key=lambda e: e.h):
            v = max(1, min(255, round(e.h)))
            d.polygon([(x / f, y / f) for x, y in e.pts], fill=v, outline=v)
        vista = edif.copy()
        d = ImageDraw.Draw(vista)
        for a in ciudad.antenas:
            v = max(1, min(255, round(a.h)))
            d.ellipse((a.x / f - 0.6, a.y / f - 0.6, a.x / f + 0.6, a.y / f + 0.6), fill=v)
        self.res_sensor, self.w_sensor, self.h_sensor = f, W, H
        self.alturas_sensor = vista.tobytes()
        base = Image.new("L", (W, H), round(C.ALTURA_SIN_MAPEAR))
        d = ImageDraw.Draw(base)
        for x0, y0, x1, y1, _ in ciudad.calles:
            d.line([(x0 / f, y0 / f), (x1 / f, y1 / f)], fill=0, width=max(1, round(C.ANCHO_CALLE / f)))
        for z in ciudad.zonas_seguras:
            d.polygon([(x / f, y / f) for x, y in z.pts], fill=0)
        total = ImageChops.lighter(edif, base)
        k = 2 * round(C.SEPARACION_HORIZONTAL / f) + 1
        total = total.filter(ImageFilter.MaxFilter(k))
        px = total.load()
        for j in range(self.ny):
            for i in range(self.nx):
                v = max(px[2 * i, 2 * j], px[2 * i + 1, 2 * j], px[2 * i, 2 * j + 1],
                        px[2 * i + 1, 2 * j + 1])
                if v:
                    self.obst[j * self.nx + i] = v

    def altura_sensor(self, x, y):
        i, j = int(x / self.res_sensor), int(y / self.res_sensor)
        if 0 <= i < self.w_sensor and 0 <= j < self.h_sensor:
            return self.alturas_sensor[j * self.w_sensor + i]
        return 0

    def _celdas_caja(self, x0, y0, x1, y1):
        i0, i1 = max(0, int(x0 // C.CELDA)), min(self.nx - 1, int(x1 // C.CELDA))
        j0, j1 = max(0, int(y0 // C.CELDA)), min(self.ny - 1, int(y1 // C.CELDA))
        for j in range(j0, j1 + 1):
            base = j * self.nx
            for i in range(i0, i1 + 1):
                yield base + i

    def celda(self, x, y):
        i = min(self.nx - 1, max(0, int(x // C.CELDA)))
        j = min(self.ny - 1, max(0, int(y // C.CELDA)))
        return j * self.nx + i

    def centro(self, c):
        return (c % self.nx + 0.5) * C.CELDA, (c // self.nx + 0.5) * C.CELDA

    def valor(self, c):
        return INF if self.bloq[c] else self.req[c]


class Ruta:

    def __init__(self, xs, ys, mapa, z0, zf, objetivo, nombre, vehiculo=C.VEHICULO):
        self.x, self.y = xs, ys
        self.vehiculo = vehiculo
        self.veh = C.VEHICULOS[vehiculo]
        self.avion = vehiculo == "avion"
        self.d_salida = 150.0 if self.avion else 0.0
        self.d_llegada = (self.veh["v_crucero"] ** 2 / (2 * 1.3) + 40) if self.avion else 0.0
        self.objetivo, self.nombre = objetivo, nombre
        n = len(xs)
        self.s = [0.0] * n
        for i in range(1, n):
            self.s[i] = self.s[i - 1] + math.hypot(xs[i] - xs[i - 1], ys[i] - ys[i - 1])
        self.longitud = self.s[-1]
        celdas = [mapa.celda(x, y) for x, y in zip(xs, ys)]
        self.obst = [mapa.obst[c] for c in celdas]
        self.cable = [mapa.cable[c] for c in celdas]
        self.req = [min(mapa.req[c], C.TECHO) for c in celdas]
        self.zona = [mapa.cerca_zona[c] for c in celdas]
        self.prohibida = any(mapa.bloq[c] for c in celdas[3:-3])
        self._perfil_altura(z0, zf)
        self._perfil_velocidad()
        self._tramos()
        self.t = [0.0] * n
        for i in range(1, n):
            v = max(0.5, (self.vel[i] + self.vel[i - 1]) / 2)
            self.t[i] = self.t[i - 1] + (self.s[i] - self.s[i - 1]) / v

    def _perfil_altura(self, z0, zf):
        n, L, rampa = len(self.x), self.longitud, 200.0
        alt = []
        for i in range(n):
            base = C.ALTURA_CRUCERO
            if self.s[i] < rampa:
                base = min(base, z0 + (C.ALTURA_CRUCERO - z0) * self.s[i] / rampa) \
                    if z0 < C.ALTURA_CRUCERO else max(C.ALTURA_CRUCERO, z0 - self.s[i] * C.PENDIENTE_BAJADA)
            if L - self.s[i] < rampa:
                base = min(base, zf + (C.ALTURA_CRUCERO - zf) * (L - self.s[i]) / rampa)
            alt.append(max(self.req[i], base))
        alt[0] = max(alt[0], z0)
        alt[-1] = max(alt[-1], zf)
        for i in range(n - 2, -1, -1):
            alt[i] = max(alt[i], alt[i + 1] - C.PENDIENTE_SUBIDA * (self.s[i + 1] - self.s[i]))
        for i in range(1, n):
            alt[i] = max(alt[i], alt[i - 1] - C.PENDIENTE_BAJADA * (self.s[i] - self.s[i - 1]))
        self.alt = [min(a, C.TECHO) for a in alt]

    def _perfil_velocidad(self):
        n = len(self.x)
        veh = self.veh
        v = [veh["v_crucero"]] * n
        for i in range(1, n - 1):
            a1 = math.atan2(self.y[i] - self.y[i - 1], self.x[i] - self.x[i - 1])
            a2 = math.atan2(self.y[i + 1] - self.y[i], self.x[i + 1] - self.x[i])
            giro = abs((a2 - a1 + math.pi) % (2 * math.pi) - math.pi)
            ds = max(1.0, (self.s[i + 1] - self.s[i - 1]) / 2)
            if giro > 1e-3:
                v[i] = min(v[i], math.sqrt(veh["a_lateral"] * ds / giro))
        for i in range(n - 1):
            ds = max(0.5, self.s[i + 1] - self.s[i])
            pend = (self.alt[i + 1] - self.alt[i]) / ds
            if pend > 0.01:
                v[i] = min(v[i], veh["v_subida"] / pend)
            elif pend < -0.01:
                v[i] = min(v[i], veh["v_bajada"] / -pend)
            if self.avion:
                continue
            if self.zona[i]:
                v[i] = min(v[i], C.V_ZONA)
            if self.cable[i] and self.alt[i] - self.cable[i] < 35:
                v[i] = min(v[i], C.V_CABLES)
        v[0], v[-1] = 2.0, 0.5
        for i in range(1, n):
            ds = self.s[i] - self.s[i - 1]
            v[i] = min(v[i], math.sqrt(v[i - 1] ** 2 + 2 * C.A_ACELERAR * ds))
        for i in range(n - 2, -1, -1):
            ds = self.s[i + 1] - self.s[i]
            v[i] = min(v[i], math.sqrt(v[i + 1] ** 2 + 2 * C.A_FRENAR * ds))
        if self.avion:
            vmin = veh["v_perdida"] + 2
            L = self.longitud
            v = [max(x, vmin) if self.d_salida <= self.s[i] <= L - self.d_llegada else x
                 for i, x in enumerate(v)]
        self.vel = [max(0.5, x) for x in v]

    def _tramos(self):
        n, L = len(self.x), self.longitud
        self.tramo = []
        for i in range(n):
            j = min(n - 1, i + 1)
            ds = max(0.5, self.s[j] - self.s[max(0, j - 1)])
            pend = (self.alt[j] - self.alt[max(0, j - 1)]) / ds
            if self.avion and self.s[i] < self.d_salida:
                t = "Transición a avión"
            elif self.avion and L - self.s[i] < self.d_llegada:
                t = "Transición a vertical"
            elif self.s[i] < 120:
                t = "Salida"
            elif L - self.s[i] < 200:
                t = "Aproximación"
            elif self.cable[i] and self.alt[i] - self.cable[i] < 35:
                t = "Cruce de cables"
            elif self.zona[i]:
                t = "Rodeo de zona prohibida"
            elif pend > 0.03:
                t = "Ascenso"
            elif pend < -0.03:
                t = "Descenso"
            elif self.alt[i] > 85:
                t = "Sobrevuelo alto"
            else:
                t = "Crucero"
            self.tramo.append(t)

    def indice(self, s):
        s = max(0.0, min(self.longitud, s))
        i = min(len(self.s) - 1, int(s / C.DS))
        while i + 1 < len(self.s) and self.s[i + 1] <= s:
            i += 1
        return i

    def proyectar(self, x, y, i0):
        mejor, mejor_d = i0, INF
        for i in range(max(0, i0 - 10), min(len(self.x), i0 + 80)):
            d = (self.x[i] - x) ** 2 + (self.y[i] - y) ** 2
            if d < mejor_d:
                mejor, mejor_d = i, d
        return mejor

    def tiempo_restante(self, i):
        return self.t[-1] - self.t[i]


class Planificador:
    def __init__(self, ciudad):
        self.ciudad = ciudad
        self.mapa = Mapa(ciudad)

    def _astar(self, sx, sy, gx, gy):
        m = self.mapa
        nx, ny, costo = m.nx, m.ny, m.costo
        ini, fin = m.celda(sx, sy), m.celda(gx, gy)
        fi, fj = fin % nx, fin // nx
        dist = array("d", [INF]) * (nx * ny)
        padre = array("i", [-1]) * (nx * ny)
        dist[ini] = 0.0
        heap = [(0.0, 0.0, ini)]
        cel = C.CELDA
        while heap:
            _, g, c = heapq.heappop(heap)
            if c == fin:
                break
            if g > dist[c]:
                continue
            ci, cj = c % nx, c // nx
            cc = costo[c]
            for di, dj, L in VECINOS:
                ni, nj = ci + di, cj + dj
                if 0 <= ni < nx and 0 <= nj < ny:
                    n = nj * nx + ni
                    ng = g + L * cel * (cc + costo[n]) * 0.5
                    if ng < dist[n]:
                        dist[n] = ng
                        padre[n] = c
                        heapq.heappush(heap, (ng + math.hypot(ni - fi, nj - fj) * cel, ng, n))
        camino, c = [], fin
        while c != -1:
            camino.append(c)
            c = padre[c]
        camino.reverse()
        if camino[0] != ini:
            return None
        return camino

    def _valores_linea(self, x0, y0, x1, y1):
        m = self.mapa
        L = math.hypot(x1 - x0, y1 - y0)
        k = max(1, int(L / (C.CELDA / 2)))
        extremos = (m.celda(x0, y0), m.celda(x1, y1))
        v = 0.0
        for t in range(k + 1):
            c = m.celda(x0 + (x1 - x0) * t / k, y0 + (y1 - y0) * t / k)
            if c not in extremos:
                v = max(v, m.valor(c))
        return v

    def _suavizar(self, pts):
        m = self.mapa
        vals = [m.valor(m.celda(x, y)) for x, y in pts]
        ultimo = len(pts) - 1
        res, i = [pts[0]], 0
        while i < ultimo:
            mejor, limite, j = i + 1, 0.0, i + 1
            if vals[i] != INF or i == 0:
                while j < ultimo:
                    j += 1
                    if vals[j] == INF and j != ultimo:
                        break
                    if vals[j - 1] != INF:
                        limite = max(limite, vals[j - 1])
                    if self._valores_linea(*pts[i], *pts[j]) <= limite + 3:
                        mejor = j
                    elif j - mejor > 12:
                        break
            res.append(pts[mejor])
            i = mejor
        return res

    def _camino(self, x0, y0, x1, y1):
        celdas = self._astar(x0, y0, x1, y1)
        pts = [(x0, y0)] + [self.mapa.centro(c) for c in celdas[1:-1]] + [(x1, y1)]
        return self._suavizar(pts)

    @staticmethod
    def _remuestrear(pts):
        xs, ys = [pts[0][0]], [pts[0][1]]
        resto = 0.0
        for (ax, ay), (bx, by) in zip(pts, pts[1:]):
            L = math.hypot(bx - ax, by - ay)
            if L < 1e-6:
                continue
            d = C.DS - resto
            while d <= L:
                xs.append(ax + (bx - ax) * d / L)
                ys.append(ay + (by - ay) * d / L)
                d += C.DS
            resto = L - (d - C.DS)
        if math.hypot(xs[-1] - pts[-1][0], ys[-1] - pts[-1][1]) > 0.5:
            xs.append(pts[-1][0])
            ys.append(pts[-1][1])
        return xs, ys

    def _libre_cercano(self, x, y):
        m = self.mapa
        if not m.bloq[m.celda(x, y)]:
            return x, y
        for r in range(1, 60):
            for k in range(8 * r):
                a = 2 * math.pi * k / (8 * r)
                px, py = x + r * C.CELDA * math.cos(a), y + r * C.CELDA * math.sin(a)
                if 0 < px < self.ciudad.ancho and 0 < py < self.ciudad.alto \
                        and not m.bloq[m.celda(px, py)]:
                    return px, py
        return x, y

    @staticmethod
    def _redondear(pts, veces=4):
        for _ in range(veces):
            nuevo = [pts[0]]
            for (ax, ay), (bx, by) in zip(pts, pts[1:]):
                nuevo.append((0.75 * ax + 0.25 * bx, 0.75 * ay + 0.25 * by))
                nuevo.append((0.25 * ax + 0.75 * bx, 0.25 * ay + 0.75 * by))
            nuevo.append(pts[-1])
            pts = nuevo
        return pts

    def _ruta(self, pts, z0, objetivo, nombre, vehiculo):
        if vehiculo == "avion" and len(pts) > 2:
            pts = self._redondear(pts)
        xs, ys = self._remuestrear(pts)
        return Ruta(xs, ys, self.mapa, z0, objetivo["z"] + C.ALTURA_APROX, objetivo, nombre,
                    vehiculo)

    def ruta_auto(self, x0, y0, z0, objetivo, nombre="Ruta automática (GPS)",
                  vehiculo=C.VEHICULO):
        pts = self._camino(x0, y0, objetivo["x"], objetivo["y"])
        return self._ruta(pts, z0, objetivo, nombre, vehiculo)

    def ruta_manual(self, x0, y0, z0, puntos, objetivo, vehiculo=C.VEHICULO):
        avisos, pts = [], [(x0, y0)]
        marcados = []
        for k, (x, y) in enumerate(puntos, 1):
            nx_, ny_ = self._libre_cercano(x, y)
            if (nx_, ny_) != (x, y):
                avisos.append(f"El punto {k} estaba en zona prohibida o sobre un obstáculo "
                              f"infranqueable: se movió {math.hypot(nx_ - x, ny_ - y):.0f} m.")
            marcados.append((nx_, ny_))
        marcados.append((objetivo["x"], objetivo["y"]))
        for k, (x, y) in enumerate(marcados, 1):
            ax, ay = pts[-1]
            if self._valores_linea(ax, ay, x, y) == INF and \
                    self._tramo_bloqueado(ax, ay, x, y):
                tramo = self._camino(ax, ay, x, y)
                pts.extend(tramo[1:])
                avisos.append(f"El tramo {k} cruzaba una zona prohibida u obstáculo: "
                              "se corrigió rodeándolo.")
            else:
                pts.append((x, y))
        return self._ruta(pts, z0, objetivo, "Ruta manual", vehiculo), avisos

    def _tramo_bloqueado(self, x0, y0, x1, y1):
        m = self.mapa
        L = math.hypot(x1 - x0, y1 - y0)
        k = max(1, int(L / (C.CELDA / 2)))
        ini, fin = m.celda(x0, y0), m.celda(x1, y1)
        for t in range(k + 1):
            c = m.celda(x0 + (x1 - x0) * t / k, y0 + (y1 - y0) * t / k)
            if m.bloq[c] and c not in (ini, fin):
                return True
        return False

    def altura_segura(self, x, y, r):
        m = self.mapa
        h = 0.0
        for c in m._celdas_caja(x - r, y - r, x + r, y + r):
            if m.req[c] > h:
                h = m.req[c]
        return min(h, C.TECHO)

    def altura_linea(self, x0, y0, x1, y1):
        m = self.mapa
        L = math.hypot(x1 - x0, y1 - y0)
        k = max(1, int(L / (C.CELDA / 2)))
        return min(C.TECHO, max(m.req[m.celda(x0 + (x1 - x0) * t / k, y0 + (y1 - y0) * t / k)]
                                for t in range(k + 1)))
