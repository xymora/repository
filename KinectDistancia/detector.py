import math
from collections import deque

import numpy as np
import cv2

try:
    from scipy.optimize import linear_sum_assignment
except ImportError:
    linear_sum_assignment = None

VERDE, AMARILLO, ROJO = 0, 1, 2
W, H = 320, 240
FX = 290.0
CX0, CY0 = (W - 1) / 2, (H - 1) / 2
HISTERESIS = 0.06
OLVIDO_FONDO = 0.0002
AREA_MIN, AREA_MAX = 0.012, 2.6
UNIR_HUECO = 0.5
VIDA_PERDIDO = 1.6
VIDA_TENTATIVO = 0.35
CONFIRMAR = 3
VENTANA_VEL = 0.8
QUIETO = 0.12
COLORES_ID = ["#4fc3f7", "#ff8a65", "#ba68c8", "#81c784", "#ffd54f", "#f06292", "#4db6ac", "#9575cd", "#aed581", "#e57373"]

_V, _U = np.mgrid[0:H, 0:W].astype(np.float32)
_RX = (_U - CX0) / FX
_RY = (_V - CY0) / FX


def nivel_para(d, rojo, amarillo, actual):
    if d is None:
        return VERDE
    lim_r = rojo + (HISTERESIS if actual == ROJO else 0)
    lim_a = amarillo + (HISTERESIS if actual >= AMARILLO else 0)
    if d < lim_r:
        return ROJO
    if d < lim_a:
        return AMARILLO
    return VERDE


class Deteccion:
    __slots__ = ("pos", "ancho", "alto", "dist", "caja", "mascara", "area", "borde_i", "borde_d", "tapa_i", "tapa_d", "en_borde")


class Pista:
    def __init__(self, det, t):
        self.id = None
        self.pos = det.pos.copy()
        self.vel = np.zeros(3, np.float32)
        self.ancho, self.alto = det.ancho, det.alto
        self.dist = det.dist
        self.caja = det.caja
        self.mascara = det.mascara
        self.visto = t
        self.t_pos = t
        self.creado = t
        self.golpes = 1
        self.nivel = VERDE
        self.perdido = False
        self.rastro = deque(maxlen=60)
        self.hist = deque()
        self.muestras = deque()
        self.v = np.zeros(2, np.float32)
        self.rapidez = 0.0
        self.v_radial = 0.0
        self.v_max = 0.0
        self.v_valida = False
        self.muestras.append((t, float(self.pos[0]), float(self.pos[2]), float(self.dist)))
        self.rastro.append((float(self.pos[0]), float(self.pos[2])))

    def prediccion(self, t):
        return self.pos + self.vel * (t - self.t_pos)

    def actualizar(self, det, t):
        dt = max(1e-3, t - self.t_pos)
        lado = det.tapa_i != det.tapa_d and self.golpes >= 3 and det.ancho < 0.92 * self.ancho
        tapado = self.golpes >= 3 and ((det.tapa_i and det.tapa_d) or det.ancho < 0.3 * self.ancho or det.alto < 0.6 * self.alto)
        if lado and not tapado:
            x = det.borde_d - self.ancho / 2 if det.tapa_i else det.borde_i + self.ancho / 2
            nueva = np.array([x, det.pos[1], det.pos[2]], np.float32)
            v = np.clip((nueva - self.pos) / dt, -2.5, 2.5)
            v[2] = self.vel[2]
            if not det.en_borde or self.golpes > 8:
                self.vel = self.vel * 0.7 + v * 0.3
            self.pos = nueva
            self._muestra(t, det, solo_x=True)
        elif tapado:
            pr = self.prediccion(t)
            self.pos = np.array([pr[0], pr[1], pr[2]], np.float32)
        else:
            v = np.clip((det.pos - self.pos) / dt, -2.5, 2.5)
            v[2] = np.clip(v[2], -1.2, 1.2)
            if det.en_borde and self.golpes <= 8:
                v[0] = self.vel[0]
            self.vel = self.vel * 0.7 + v * 0.3 if self.golpes > 1 else v * 0.3
            self.pos = det.pos.copy()
            self.ancho += (det.ancho - self.ancho) * 0.2
            self.alto += (det.alto - self.alto) * 0.2
            self._muestra(t, det)
        self.t_pos = t
        self.dist = det.dist if abs(det.dist - self.dist) > 0.5 else self.dist + (det.dist - self.dist) * 0.5
        self.caja, self.mascara = det.caja, det.mascara
        self.visto = t
        self.golpes += 1
        self.perdido = False
        self.rastro.append((float(self.pos[0]), float(self.pos[2])))

    def _muestra(self, t, det, solo_x=False):
        z = self.muestras[-1][2] + float(self.vel[2]) * (t - self.muestras[-1][0]) if solo_x and self.muestras else float(self.pos[2])
        d = float(self.dist) if solo_x else float(det.dist)
        self.muestras.append((t, float(self.pos[0]), z, d))

    def medir_velocidad(self, t):
        while self.muestras and t - self.muestras[0][0] > VENTANA_VEL:
            self.muestras.popleft()
        if self.perdido or len(self.muestras) < 4 or self.muestras[-1][0] - self.muestras[0][0] < 0.3:
            if self.perdido:
                self.v_valida = False
            elif self.golpes >= CONFIRMAR + 6:
                vx, vz = float(self.vel[0]), float(self.vel[2])
                k = 0.2 if self.v_valida else 1.0
                self.v[0] += (vx - self.v[0]) * k
                self.v[1] += (vz - self.v[1]) * k
                self.v_radial += (vz - self.v_radial) * k
                self.rapidez = float(math.hypot(self.v[0], self.v[1]))
                if self.rapidez < QUIETO * 0.6:
                    self.rapidez = 0.0
                self.v_valida = True
            return
        a = np.array(self.muestras, np.float64)
        tt = a[:, 0] - a[:, 0].mean()
        den = float((tt * tt).sum())
        if den <= 1e-6:
            return
        pend = (tt[:, None] * (a[:, 1:] - a[:, 1:].mean(0))).sum(0) / den
        vx, vz, vd = (float(np.clip(x, -6, 6)) for x in pend)
        k = 0.35 if self.v_valida else 1.0
        self.v[0] += (vx - self.v[0]) * k
        self.v[1] += (vz - self.v[1]) * k
        self.v_radial += (vd - self.v_radial) * k
        self.rapidez = float(math.hypot(self.v[0], self.v[1]))
        if self.rapidez < QUIETO * 0.6:
            self.rapidez = 0.0
        self.v_valida = True
        self.v_max = max(self.v_max, self.rapidez)

    def llegada(self):
        if not self.v_valida or self.perdido or self.v_radial > -0.15:
            return None
        s = self.dist / -self.v_radial
        return s if s < 15 else None

    def color(self):
        return COLORES_ID[(self.id - 1) % len(COLORES_ID)] if self.id else "#9aa3b5"

    def velocidad_z(self):
        return float(self.vel[2])


class Resultado:
    __slots__ = ("pistas", "cercana", "distancia", "nivel", "muy_cerca", "piso")


class Detector:
    def __init__(self):
        self.zona = None
        self.ignorar_fondo = False
        self.fondo = None
        self.rojo = 1.0
        self.amarillo = 2.0
        self.alcance = 4.0
        self.base_inv = None
        self.plano = None
        self.n_cuadro = 0
        self.pistas = []
        self.sig_id = 1
        self.nivel = VERDE
        self.rng = np.random.default_rng(0)

    def aprender_fondo(self):
        self.fondo = None

    def reiniciar_ids(self):
        self.pistas = []
        self.sig_id = 1

    def poner_zona(self, x0, y0, x1, y1):
        x0, x1 = sorted((max(0.0, min(1.0, x0)), max(0.0, min(1.0, x1))))
        y0, y1 = sorted((max(0.0, min(1.0, y0)), max(0.0, min(1.0, y1))))
        self.zona = (x0, y0, x1, y1) if (x1 - x0) > 0.03 and (y1 - y0) > 0.03 else None

    def _mascara_zona(self):
        z = np.zeros((H, W), bool)
        if self.zona is None:
            z[:] = True
        else:
            x0, y0, x1, y1 = self.zona
            z[int(y0 * H):int(math.ceil(y1 * H)), int(x0 * W):int(math.ceil(x1 * W))] = True
        return z

    def _fondo(self, m, val):
        if self.fondo is None:
            self.fondo = np.where(val, m, 0).astype(np.float32)
            return np.zeros_like(val)
        f = self.fondo
        f -= OLVIDO_FONDO
        np.maximum(f, 0, out=f)
        sube = val & (m > f)
        f[sube] = m[sube]
        return (f <= 0) | (m < f - (0.1 + 0.015 * m * m))

    def _ajustar_piso(self, X, Y, Z, val):
        idx = np.flatnonzero(val[H // 2:, ::2].ravel())
        if idx.size < 300:
            return
        sub_v, sub_u = np.unravel_index(idx, (H - H // 2, (W + 1) // 2))
        vv, uu = sub_v + H // 2, sub_u * 2
        sel = self.rng.choice(idx.size, min(700, idx.size), replace=False)
        P = np.stack([X[vv[sel], uu[sel]], Y[vv[sel], uu[sel]], Z[vv[sel], uu[sel]]], 1)
        mejor, n_mejor = None, 0
        for _ in range(60):
            a, b, c = P[self.rng.choice(len(P), 3, replace=False)]
            n = np.cross(b - a, c - a)
            nn = np.linalg.norm(n)
            if nn < 1e-6:
                continue
            n /= nn
            if n[1] > 0:
                n = -n
            if -n[1] < 0.75:
                continue
            d = -float(n @ a)
            dentro = int((np.abs(P @ n + d) < 0.04).sum())
            if dentro > n_mejor:
                mejor, n_mejor = (n, d), dentro
        if mejor is not None and n_mejor > 0.25 * len(P):
            n, d = mejor
            ins = P[np.abs(P @ n + d) < 0.04]
            c = ins.mean(0)
            _, _, vt = np.linalg.svd(ins - c, full_matrices=False)
            n2 = vt[2] if vt[2][1] < 0 else -vt[2]
            if -n2[1] > 0.75:
                self.plano = (n2, -float(n2 @ c))

    def _segmentar(self, m, cand):
        dz_x = np.abs(np.diff(m, axis=1))
        dz_y = np.abs(np.diff(m, axis=0))
        lim = 0.05 + 0.025 * m * m
        borde = np.zeros((H, W), bool)
        bx = dz_x > lim[:, 1:]
        by = dz_y > lim[1:, :]
        borde[:, 1:] |= bx
        borde[:, :-1] |= bx
        borde[1:, :] |= by
        borde[:-1, :] |= by
        mk = (cand & ~borde).astype(np.uint8)
        mk = cv2.morphologyEx(mk, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
        n, lab, st, _ = cv2.connectedComponentsWithStats(mk, connectivity=4)
        if n <= 1:
            return lab, n, []
        validos = np.flatnonzero(st[1:, cv2.CC_STAT_AREA] >= 12) + 1
        padre = list(range(n))

        def raiz(a):
            while padre[a] != a:
                padre[a] = padre[padre[a]]
                a = padre[a]
            return a

        pares = {}
        for k in (2, 3):
            for la, lb, za, zb in ((lab[:, :-k], lab[:, k:], m[:, :-k], m[:, k:]), (lab[:-k, :], lab[k:, :], m[:-k, :], m[k:, :])):
                s = (la > 0) & (lb > 0) & (la != lb)
                if not s.any():
                    continue
                a, b = la[s], lb[s]
                dif = np.abs(za[s] - zb[s])
                clave = np.minimum(a, b).astype(np.int64) * n + np.maximum(a, b)
                orden = np.argsort(clave)
                clave, dif = clave[orden], dif[orden]
                u, ini, cnt = np.unique(clave, return_index=True, return_counts=True)
                for c, i0, ct in zip(u, ini, cnt):
                    pares.setdefault(int(c), []).append(dif[i0:i0 + ct])
        for c, difs in pares.items():
            d = np.concatenate(difs)
            if d.size >= 3 and float(np.median(d)) < UNIR_HUECO:
                a, b = raiz(c // n), raiz(c % n)
                if a != b:
                    padre[max(a, b)] = min(a, b)
        mapa = np.array([raiz(i) for i in range(n)], np.int32)
        mapa[0] = 0
        lab2 = mapa[lab]
        return lab2, n, sorted(set(int(mapa[v]) for v in validos))

    def detectar(self, m):
        val = (m > 0.4) & (m < self.alcance)
        Z = m
        X = _RX * Z
        Y = _RY * Z
        if self.n_cuadro % 10 == 0 or self.plano is None:
            self._ajustar_piso(X, Y, Z, (m > 0.4) & (m < 6.0))
        self.n_cuadro += 1
        piso = np.zeros((H, W), bool)
        if self.plano is not None:
            n, d = self.plano
            altura = X * n[0] + Y * n[1] + Z * n[2] + d
            piso = (m > 0.4) & (altura < 0.07)
        cand = val & ~piso & self._mascara_zona()
        if self.ignorar_fondo:
            cand &= self._fondo(m, m > 0.4)
        else:
            self.fondo = None
        lab, n, etiquetas = self._segmentar(m, cand)
        dets = []
        for k in etiquetas:
            mk = lab == k
            cnt = int(mk.sum())
            if cnt < 25:
                continue
            zs = Z[mk]
            zmed = float(np.median(zs))
            area = cnt * (zmed / FX) ** 2
            if area < AREA_MIN or area > AREA_MAX:
                continue
            ys, xs = np.nonzero(mk)
            det = Deteccion()
            det.pos = np.array([float(np.median(X[mk])), float(np.median(Y[mk])), zmed], np.float32)
            det.dist = float(np.percentile(zs, 5))
            x0, x1, y0, y1 = xs.min(), xs.max(), ys.min(), ys.max()
            det.ancho = (x1 - x0 + 1) * zmed / FX
            det.alto = (y1 - y0 + 1) * zmed / FX
            det.caja = (x0 / W, y0 / H, (x1 + 1) / W, (y1 + 1) / H)
            det.mascara = mk
            det.area = area
            det.borde_i = (x0 - CX0) * zmed / FX
            det.borde_d = (x1 + 1 - CX0) * zmed / FX
            det.tapa_i = self._tapado(m, x0 - 3, y0, y1, zmed)
            det.tapa_d = self._tapado(m, x1 + 3, y0, y1, zmed)
            det.en_borde = bool(x0 <= 2 or x1 >= W - 3)
            dets.append(det)
        return dets, piso

    def _dentro(self, p, d, t):
        pr = p.prediccion(t)
        return abs(float(pr[0] - d.pos[0])) < d.ancho / 2 + 0.15 and abs(float(pr[2] - d.pos[2])) < 0.6

    def _avanzar(self, p, t):
        rap = float(np.hypot(p.vel[0], p.vel[2]))
        if rap > 1.5:
            p.vel *= 1.5 / rap
        p.pos = p.prediccion(t)
        p.t_pos = t

    def _seguir_a_ciegas(self, p, d, t):
        self._avanzar(p, t)
        p.visto = t
        p.perdido = d is None
        if d is not None:
            p.caja, p.mascara = d.caja, d.mascara
            p.dist = p.dist + (d.dist - p.dist) * 0.3

    def _tapado(self, m, x, y0, y1, z):
        if x < 0 or x >= W:
            return True
        col = m[y0:y1 + 1, max(0, x - 1):min(W, x + 2)]
        cerca = ((col > 0.4) & (col < z - 0.3)).mean() if col.size else 0.0
        return bool(cerca > 0.35)

    def _asociar(self, dets, t):
        P = self.pistas
        if not P or not dets:
            return [], list(range(len(P))), list(range(len(dets)))
        C = np.full((len(P), len(dets)), 1e6)
        for i, p in enumerate(P):
            pr = p.prediccion(t)
            perdido = t - p.visto
            puerta = (0.55 if p.id else 0.4) + 0.8 * perdido + (0.35 if p.golpes <= 10 else 0.0)
            for j, d in enumerate(dets):
                dxz = math.hypot(float(pr[0] - d.pos[0]), float(pr[2] - d.pos[2]))
                c = dxz + 0.4 * abs(p.alto - d.alto) + 0.25 * abs(p.ancho - d.ancho)
                razon = max(p.alto, d.alto) / max(0.05, min(p.alto, d.alto))
                if dxz <= puerta and razon < 2.2:
                    C[i, j] = c
        pares = []
        if linear_sum_assignment is not None:
            fi, cj = linear_sum_assignment(C)
            pares = [(i, j) for i, j in zip(fi, cj) if C[i, j] < 1e5]
        else:
            usados_i, usados_j = set(), set()
            for c, i, j in sorted((C[i, j], i, j) for i in range(len(P)) for j in range(len(dets))):
                if c >= 1e5:
                    break
                if i not in usados_i and j not in usados_j:
                    pares.append((i, j))
                    usados_i.add(i)
                    usados_j.add(j)
        mi = {i for i, _ in pares}
        mj = {j for _, j in pares}
        return pares, [i for i in range(len(P)) if i not in mi], [j for j in range(len(dets)) if j not in mj]

    def medir(self, m, t):
        dets, piso = self.detectar(m)
        pares, sin_det, nuevas = self._asociar(dets, t)
        fusiones = []
        for i, j in pares:
            p, d = self.pistas[i], dets[j]
            otros = [q for k, q in enumerate(self.pistas) if k != i and q.id and k in sin_det and self._dentro(q, d, t)]
            if p.id and p.golpes >= CONFIRMAR and (otros or d.ancho > 1.45 * p.ancho) and d.ancho > 1.25 * p.ancho:
                self._seguir_a_ciegas(p, d, t)
                fusiones.append(d)
                continue
            p.actualizar(d, t)
            if p.id is None and p.golpes >= CONFIRMAR:
                p.id = self.sig_id
                self.sig_id += 1
        for i in sin_det:
            q = self.pistas[i]
            if q.id and any(self._dentro(q, d, t) for d in fusiones):
                self._seguir_a_ciegas(q, None, t)
        vivas = []
        for i, p in enumerate(self.pistas):
            if i in sin_det:
                limite = VIDA_PERDIDO if p.id else VIDA_TENTATIVO
                if t - p.visto > limite:
                    continue
                p.perdido = True
                self._avanzar(p, t)
                if t - p.visto > 0.8:
                    p.vel *= 0.97
            vivas.append(p)
        for j in nuevas:
            vivas.append(Pista(dets[j], t))
        self.pistas = vivas
        for p in self.pistas:
            p.nivel = nivel_para(None if p.perdido else p.dist, self.rojo, self.amarillo, p.nivel)
            p.medir_velocidad(t)
            if p.id:
                p.hist.append((t, None if p.perdido else p.dist, p.rapidez if p.v_valida else None))
                while p.hist and t - p.hist[0][0] > 20:
                    p.hist.popleft()
        zona = self._mascara_zona()
        invalido = ((m <= 0.3) & zona).sum() / max(1, zona.sum())
        if self.base_inv is None:
            self.base_inv = invalido
        muy_cerca = bool(invalido > max(0.55, self.base_inv + 0.35))
        if not muy_cerca:
            self.base_inv += (invalido - self.base_inv) * 0.02
        r = Resultado()
        r.pistas = [p for p in self.pistas if p.id]
        r.piso = piso
        visibles = [p for p in r.pistas if not p.perdido]
        r.cercana = min(visibles, key=lambda p: p.dist) if visibles else None
        r.muy_cerca = muy_cerca
        r.distancia = 0.45 if muy_cerca else (r.cercana.dist if r.cercana else None)
        self.nivel = ROJO if muy_cerca else (max(p.nivel for p in visibles) if visibles else VERDE)
        r.nivel = self.nivel
        return r
