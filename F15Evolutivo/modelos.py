import math

import numpy as np

GRIS_A = (0.56, 0.60, 0.65)
GRIS_B = (0.44, 0.48, 0.53)
GRIS_C = (0.34, 0.36, 0.40)
METAL = (0.30, 0.29, 0.28)
NEGRO = (0.06, 0.06, 0.07)
CRISTAL = (0.08, 0.10, 0.12)
BLANCO = (0.86, 0.86, 0.84)
RADOMO = (0.50, 0.53, 0.56)
CAUCHO = (0.05, 0.05, 0.05)


class Malla:
    def __init__(self):
        self.p, self.n, self.c, self.m = [], [], [], []

    def tri(self, a, b, c, color, mat=0.0, normal=None):
        a, b, c = np.asarray(a, float), np.asarray(b, float), np.asarray(c, float)
        if normal is None:
            nn = np.cross(b - a, c - a)
            ln = np.linalg.norm(nn)
            if ln < 1e-12:
                return
            nn = nn / ln
            normal = (nn, nn, nn)
        for v, nv in zip((a, b, c), normal):
            self.p.append(v)
            self.n.append(nv)
            self.c.append(color)
            self.m.append(mat)

    def quad(self, a, b, c, d, color, mat=0.0):
        self.tri(a, b, c, color, mat)
        self.tri(a, c, d, color, mat)

    def doble(self, a, b, c, d, color, mat=0.0):
        self.quad(a, b, c, d, color, mat)
        self.quad(d, c, b, a, color, mat)

    def unir(self, otra):
        self.p += otra.p
        self.n += otra.n
        self.c += otra.c
        self.m += otra.m

    def arreglo(self):
        if not self.p:
            return np.zeros((0, 10), np.float32)
        return np.concatenate([np.array(self.p), np.array(self.n), np.array(self.c),
                               np.array(self.m)[:, None]], 1).astype(np.float32)


def _anillo(x, cy, cz, a, bt, bb, k, n, plano=0.0):
    pts = []
    for i in range(n):
        t = 2 * math.pi * i / n
        c, s = math.cos(t), math.sin(t)
        e = 2.0 / k
        y = math.copysign(abs(s) ** e, s) * (bt if s > 0 else bb)
        z = math.copysign(abs(c) ** e, c) * a
        if plano and s > 0:
            y = min(y, bt * (1 - plano * 0.0))
        pts.append((x, cy + y, cz + z))
    return pts


def loft(m, secciones, color, n=24, mat=0.0, tapa_ini=True, tapa_fin=True, colores=None):
    anillos = [_anillo(*s, n) for s in secciones]
    centros = []
    for s in secciones:
        centros.append(np.array([s[0], s[1], s[2]]))
    for k in range(len(anillos) - 1):
        a, b = anillos[k], anillos[k + 1]
        col = colores[k] if colores else color
        ca, cb = centros[k], centros[k + 1]
        for i in range(n):
            j = (i + 1) % n
            pa, pb, pc, pd = map(np.array, (a[i], a[j], b[j], b[i]))
            na = _normal_radial(pa, ca, secciones[k])
            nb = _normal_radial(pb, ca, secciones[k])
            nc = _normal_radial(pc, cb, secciones[k + 1])
            nd = _normal_radial(pd, cb, secciones[k + 1])
            m.tri(pa, pc, pb, col, mat, (na, nc, nb))
            m.tri(pa, pd, pc, col, mat, (na, nd, nc))
    if tapa_ini:
        c = centros[0]
        for i in range(n):
            m.tri(c, anillos[0][i], anillos[0][(i + 1) % n], color, mat)
    if tapa_fin:
        c = centros[-1]
        for i in range(n):
            m.tri(c, anillos[-1][(i + 1) % n], anillos[-1][i], color, mat)


def _normal_radial(p, c, s):
    _, _, _, a, bt, bb, _ = s
    d = p - c
    b = bt if d[1] > 0 else bb
    nv = np.array([0.0, d[1] / max(b * b, 1e-4), d[2] / max(a * a, 1e-4)])
    ln = np.linalg.norm(nv)
    return nv / ln if ln > 1e-9 else np.array([1.0, 0, 0])


def superficie_ala(m, raiz, punta, espesor_r, espesor_p, color, mat=0.0, lado=1, diedro=0.0, vertical=False):
    perfil = [(0.0, 0.0), (0.12, 0.85), (0.35, 1.0), (0.7, 0.6), (1.0, 0.05)]

    def punto(base, t, f, sup):
        le, te, pos = base
        x = le + (te - le) * t
        off = f * (1 if sup else -1)
        if vertical:
            return np.array([x, pos[0], pos[1] + off * lado])
        return np.array([x, pos[0] + off, pos[1]])

    r = (raiz[0], raiz[1], raiz[2])
    p = (punta[0], punta[1], punta[2])
    for sup in (True, False):
        for k in range(len(perfil) - 1):
            t0, f0 = perfil[k]
            t1, f1 = perfil[k + 1]
            a = punto(r, t0, f0 * espesor_r / 2, sup)
            b = punto(r, t1, f1 * espesor_r / 2, sup)
            c = punto(p, t1, f1 * espesor_p / 2, sup)
            d = punto(p, t0, f0 * espesor_p / 2, sup)
            orden = (sup ^ (lado < 0)) if not vertical else (sup ^ (lado < 0))
            if orden:
                m.quad(a, d, c, b, color, mat)
            else:
                m.quad(a, b, c, d, color, mat)
    for t0, f0, t1, f1 in [(perfil[k][0], perfil[k][1], perfil[k + 1][0], perfil[k + 1][1])
                           for k in range(len(perfil) - 1)]:
        a = punto(p, t0, f0 * espesor_p / 2, True)
        b = punto(p, t1, f1 * espesor_p / 2, True)
        c = punto(p, t1, f1 * espesor_p / 2, False)
        d = punto(p, t0, f0 * espesor_p / 2, False)
        m.doble(a, b, c, d, color, mat)


def caja(m, x0, x1, y0, y1, z0, z1, color, mat=0.0, inclina=0.0):
    v = [np.array(p, float) for p in [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0 - inclina, y1, z0),
                                       (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0 - inclina, y1, z1)]]
    caras = [(0, 1, 2, 3), (5, 4, 7, 6), (4, 0, 3, 7), (1, 5, 6, 2), (3, 2, 6, 7), (4, 5, 1, 0)]
    for a, b, c, d in caras:
        m.quad(v[a], v[b], v[c], v[d], color, mat)


def cilindro(m, x0, x1, r0, r1, cy, cz, color, n=16, mat=0.0, eje=0, tapas=True):
    def p(x, r, t):
        if eje == 0:
            return np.array([x, cy + r * math.sin(t), cz + r * math.cos(t)])
        if eje == 1:
            return np.array([cy + r * math.cos(t), x, cz + r * math.sin(t)])
        return np.array([cy + r * math.cos(t), cz + r * math.sin(t), x])

    for i in range(n):
        t0, t1 = 2 * math.pi * i / n, 2 * math.pi * (i + 1) / n
        a, b, c, d = p(x0, r0, t0), p(x0, r0, t1), p(x1, r1, t1), p(x1, r1, t0)
        ca, cb = p(x0, 0, 0), p(x1, 0, 0)
        na = (a - ca) / max(np.linalg.norm(a - ca), 1e-6)
        nb = (b - ca) / max(np.linalg.norm(b - ca), 1e-6)
        m.tri(a, c, b, color, mat, (na, nb * 0 + (c - cb) / max(np.linalg.norm(c - cb), 1e-6), nb))
        m.tri(a, d, c, color, mat, (na, (d - cb) / max(np.linalg.norm(d - cb), 1e-6),
                                    (c - cb) / max(np.linalg.norm(c - cb), 1e-6)))
        if tapas:
            m.tri(ca, b, a, color, mat)
            m.tri(cb, d, c, color, mat)


def _misil(m, x0, largo, r, cy, cz, color=BLANCO, aletas=True):
    cilindro(m, x0, x0 + largo * 0.85, r, r, cy, cz, color, 10, 0.3, tapas=False)
    cilindro(m, x0 + largo * 0.85, x0 + largo, r, r * 0.15, cy, cz, (0.7, 0.68, 0.6), 10, 0.3, tapas=False)
    cilindro(m, x0 - 0.01, x0, 0.0, r, cy, cz, NEGRO, 10, tapas=False)
    if aletas:
        for ang in (0, math.pi / 2, math.pi, 3 * math.pi / 2):
            dy, dz = math.sin(ang), math.cos(ang)
            a = np.array([x0, cy + dy * r, cz + dz * r])
            b = np.array([x0 + 0.35, cy + dy * r, cz + dz * r])
            c = np.array([x0 + 0.05, cy + dy * (r + 0.22), cz + dz * (r + 0.22)])
            m.tri(a, b, c, color, 0.3)
            m.tri(a, c, b, color, 0.3)


class Pieza:
    def __init__(self, nombre, pivote=(0, 0, 0), eje=(0, 0, 1)):
        self.nombre = nombre
        self.malla = Malla()
        self.pivote = np.array(pivote, float)
        self.eje = np.array(eje, float) / np.linalg.norm(eje)


def f15():
    piezas = {}

    def nueva(nombre, pivote=(0, 0, 0), eje=(0, 0, 1)):
        piezas[nombre] = Pieza(nombre, pivote, eje)
        return piezas[nombre].malla

    cu = nueva("cuerpo")
    nariz = [(9.75, 0.05, 0, 0.02, 0.02, 0.02, 2.0), (9.3, 0.08, 0, 0.2, 0.2, 0.2, 2.0),
             (8.6, 0.12, 0, 0.38, 0.38, 0.38, 2.0), (7.8, 0.16, 0, 0.5, 0.52, 0.5, 2.1)]
    loft(cu, nariz, RADOMO, 24, 0.15, tapa_fin=False)
    loft(cu, [(7.8, 0.16, 0, 0.5, 0.52, 0.5, 2.1), (6.6, 0.2, 0, 0.63, 0.71, 0.59, 2.3)], GRIS_A, 24, 0.2,
         tapa_ini=False, tapa_fin=False)
    frente = [(6.6, 0.2, 0, 0.63, 0.71, 0.59, 2.3), (5.6, 0.22, 0, 0.7, 0.78, 0.62, 2.5),
              (4.4, 0.24, 0, 0.76, 0.8, 0.66, 2.7), (3.4, 0.24, 0, 0.82, 0.78, 0.68, 3.0)]
    loft(nueva("frente"), frente, GRIS_A, 24, 0.2, tapa_ini=False, tapa_fin=False)
    baja = [(6.6, 0.2, 0, 0.63, 0.44, 0.59, 2.3), (5.6, 0.22, 0, 0.7, 0.4, 0.62, 2.5),
            (4.4, 0.24, 0, 0.76, 0.4, 0.66, 2.7), (3.4, 0.24, 0, 0.82, 0.5, 0.68, 3.0)]
    loft(nueva("frente_baja"), baja, GRIS_A, 24, 0.2, tapa_ini=False, tapa_fin=False)
    centro = [(3.4, 0.24, 0, 0.82, 0.78, 0.68, 3.0), (2.0, 0.2, 0, 1.25, 0.72, 0.78, 4.0),
              (0.0, 0.18, 0, 1.55, 0.7, 0.8, 5.0), (-3.0, 0.15, 0, 1.6, 0.68, 0.72, 5.0),
              (-5.5, 0.12, 0, 1.45, 0.62, 0.62, 4.5), (-7.4, 0.1, 0, 1.25, 0.55, 0.55, 3.5),
              (-8.4, 0.08, 0, 1.15, 0.48, 0.48, 3.0)]
    loft(cu, centro, GRIS_B, 28, 0.2, tapa_ini=False, tapa_fin=True)
    for lado in (-1, 1):
        z0, z1 = 0.95 * lado, 1.82 * lado
        zi, zo = min(z0, z1), max(z0, z1)
        caja(cu, -0.5, 4.3, -0.85, 0.32, zi, zo, GRIS_B, 0.2, inclina=-0.6)
        caja(cu, 4.28, 4.32, -0.8, 0.27, zi + 0.06, zo - 0.06, NEGRO)
        caja(cu, 3.4, 4.35, 0.32, 0.4, zi, zo, GRIS_C, 0.2)
        cilindro(cu, -9.55, -8.3, 0.5, 0.56, 0.08, 0.64 * lado, METAL, 18, 0.5, tapas=False)
        cilindro(cu, -9.56, -9.5, 0.0, 0.5, 0.08, 0.64 * lado, (0.12, 0.1, 0.09), 18, 0.2, tapas=False)
        caja(cu, -8.4, -5.0, -0.1, 0.25, 0.6 * lado - 0.1, 0.6 * lado + 0.1, GRIS_C, 0.2)
    dorso = [(3.2, 0.95, 0, 0.42, 0.28, 0.05, 2.5), (0.5, 0.92, 0, 0.6, 0.22, 0.05, 3.0),
             (-4.5, 0.82, 0, 0.62, 0.14, 0.05, 3.0), (-7.0, 0.7, 0, 0.5, 0.08, 0.05, 3.0)]
    loft(cu, dorso, GRIS_A, 20, 0.2)
    for lado in (-1, 1):
        raiz = (2.4, -4.4, (0.24, 1.6 * lado))
        punta = (-2.05, -3.7, (0.12, 6.45 * lado))
        superficie_ala(cu, (raiz[0], -1.2, raiz[2]), (punta[0], -2.6, punta[2]), 0.34, 0.09, GRIS_A, 0.2, lado)
        caja(cu, -1.6, -0.4, -0.05, 0.25, 3.25 * lado - 0.06, 3.25 * lado + 0.06, GRIS_C)
        pt = (-6.1, -9.0, (0.02, 1.8 * lado))
        cola_raiz = (-5.25, -8.95, (0.65, 1.55 * lado))
        cola_punta = (-7.55, -8.95, (3.55, 1.62 * lado))
        superficie_ala(cu, (cola_raiz[0], -7.95, cola_raiz[2]), (cola_punta[0], -8.3, cola_punta[2]),
                       0.24, 0.07, GRIS_B, 0.2, lado, vertical=True)
        caja(cu, -9.05, -8.6, 3.45, 3.62, 1.56 * lado - 0.08, 1.56 * lado + 0.08, GRIS_C)

        al = nueva("aleron_" + ("i" if lado < 0 else "d"), (-3.0, 0.15, 5.0 * lado), (0.24 * lado, 0, 1.0))
        superficie_ala(al, (-3.05, -3.75, (0.16, 4.2 * lado)), (-3.4, -3.75, (0.12, 6.05 * lado)), 0.1, 0.06,
                       GRIS_A, 0.2, lado)
        fl = nueva("flap_" + ("i" if lado < 0 else "d"), (-3.3, 0.2, 2.8 * lado), (0, 0, 1.0))
        superficie_ala(fl, (-3.3, -4.4, (0.22, 1.7 * lado)), (-3.25, -3.95, (0.16, 4.1 * lado)), 0.14, 0.1,
                       GRIS_A, 0.2, lado)
        es = nueva("estab_" + ("i" if lado < 0 else "d"), (-7.55, 0.02, 2.5 * lado), (0, 0, 1.0))
        superficie_ala(es, (pt[0], pt[1], pt[2]), (-8.2, -9.45, (0.02, 4.35 * lado)), 0.2, 0.06, GRIS_B, 0.2, lado)
        ti = nueva("timon_" + ("i" if lado < 0 else "d"), (-8.0, 1.2, 1.57 * lado), (0.25, 1.0, 0.0))
        superficie_ala(ti, (-8.0, -8.95, (0.95, 1.56 * lado)), (-8.35, -8.95, (2.55, 1.6 * lado)), 0.1, 0.06,
                       GRIS_C, 0.2, lado, vertical=True)
        for k, (xm, zm) in enumerate(((-1.4, 3.25), )):
            mi = nueva(f"misil_ala_{'i' if lado < 0 else 'd'}")
            _misil(mi, xm - 1.0, 2.9, 0.065, -0.15, zm * lado + 0.28 * lado)
            mi2 = nueva(f"misil_ala2_{'i' if lado < 0 else 'd'}")
            _misil(mi2, xm - 1.0, 2.9, 0.065, -0.15, zm * lado - 0.28 * lado)
        for k, xm in enumerate((1.0, -4.2)):
            mf = nueva(f"misil_f{k}_{'i' if lado < 0 else 'd'}")
            _misil(mf, xm - 1.8, 3.65, 0.09, -0.93, 1.25 * lado, (0.82, 0.82, 0.8))
    can = nueva("canopy")
    cupula = [(6.95, 0.95, 0, 0.14, 0.06, 0.02, 2.0), (6.3, 1.0, 0, 0.44, 0.46, 0.02, 2.0),
              (5.2, 1.0, 0, 0.53, 0.66, 0.02, 2.0), (4.0, 1.0, 0, 0.53, 0.6, 0.02, 2.0),
              (2.9, 1.0, 0, 0.44, 0.3, 0.02, 2.0)]
    loft(can, cupula, CRISTAL, 22, 1.0)
    af = nueva("aerofreno", (1.4, 1.12, 0), (0, 0, 1.0))
    caja(af, -1.1, 1.4, 1.1, 1.16, -0.55, 0.55, GRIS_A, 0.2)

    tn = nueva("tren_n", (5.6, -0.35, 0), (0, 0, 1.0))
    cilindro(tn, -0.4, -1.85, 0.07, 0.06, 5.1, 0.0, METAL, 8, 0.4, eje=1)
    cilindro(tn, -0.09, 0.09, 0.34, 0.34, 5.05, -1.82, CAUCHO, 14, eje=2)
    caja(tn, 5.25, 5.95, -0.9, -0.4, -0.05, 0.05, GRIS_C)
    for lado, nombre in ((-1, "tren_i"), (1, "tren_d")):
        tm = nueva(nombre, (-0.65, -0.55, 1.1 * lado), (1.0, 0, 0))
        cilindro(tm, -0.5, -1.75, 0.09, 0.08, -0.65, 1.38 * lado, METAL, 8, 0.4, eje=1)
        cilindro(tm, 1.38 * lado - 0.14, 1.38 * lado + 0.14, 0.42, 0.42, -0.65, -1.73, CAUCHO, 16, eje=2)
        caja(tm, -1.6, -0.2, -0.6, -0.55, 1.0 * lado - 0.25, 1.0 * lado + 0.25, GRIS_C)
    return piezas


def estatico(piezas, tren=True, quitar=("frente_baja",)):
    m = Malla()
    for nombre, p in piezas.items():
        if nombre in quitar:
            continue
        if nombre.startswith("tren") and not tren:
            continue
        m.unir(p.malla)
    return m.arreglo()


def arbol():
    m = Malla()
    cilindro(m, 0, 3.5, 0.35, 0.25, 0, 0, (0.30, 0.22, 0.14), 6, eje=1, tapas=False)
    n = 8
    for k, (y0, y1, r) in enumerate(((2.5, 9.0, 3.2), (6.0, 13.0, 2.4), (10.0, 16.0, 1.4))):
        for i in range(n):
            t0, t1 = 2 * math.pi * i / n, 2 * math.pi * (i + 1) / n
            a = np.array([r * math.cos(t0), y0, r * math.sin(t0)])
            b = np.array([r * math.cos(t1), y0, r * math.sin(t1)])
            c = np.array([0, y1, 0])
            na = np.array([math.cos(t0), 0.55, math.sin(t0)])
            nb = np.array([math.cos(t1), 0.55, math.sin(t1)])
            nc = np.array([0, 1.0, 0])
            m.tri(a, c, b, (0.16, 0.30, 0.12), 0, (na / np.linalg.norm(na), nc, nb / np.linalg.norm(nb)))
            m.tri(a, b, np.array([0, y0, 0]), (0.12, 0.22, 0.09), 0)
    return m.arreglo()


def edificio():
    m = Malla()
    caja(m, -0.5, 0.5, 0, 1, -0.5, 0.5, (0.72, 0.70, 0.66))
    return m.arreglo()


def hangar():
    m = Malla()
    n = 10
    for i in range(n):
        t0, t1 = math.pi * i / n, math.pi * (i + 1) / n
        a = np.array([-0.5, 0.55 + 0.45 * math.sin(t0), 0.5 * math.cos(t0)])
        b = np.array([-0.5, 0.55 + 0.45 * math.sin(t1), 0.5 * math.cos(t1)])
        c = np.array([0.5, 0.55 + 0.45 * math.sin(t1), 0.5 * math.cos(t1)])
        d = np.array([0.5, 0.55 + 0.45 * math.sin(t0), 0.5 * math.cos(t0)])
        m.quad(a, d, c, b, (0.55, 0.58, 0.55), 0.3)
        m.tri(np.array([-0.5, 0.55, 0]), a, b, (0.45, 0.47, 0.45))
        m.tri(np.array([0.5, 0.55, 0]), c, d, (0.2, 0.2, 0.22))
    caja(m, -0.5, 0.5, 0, 0.55, -0.5, 0.5, (0.5, 0.52, 0.5), 0.2)
    caja(m, 0.5, 0.51, 0.02, 0.85, -0.42, 0.42, (0.15, 0.16, 0.18))
    return m.arreglo()


def torre():
    m = Malla()
    caja(m, -0.3, 0.3, 0, 0.82, -0.3, 0.3, (0.78, 0.76, 0.72))
    caja(m, -0.5, 0.5, 0.82, 0.95, -0.5, 0.5, (0.1, 0.18, 0.22), 1.0)
    caja(m, -0.55, 0.55, 0.95, 1.0, -0.55, 0.55, (0.6, 0.6, 0.6))
    return m.arreglo()


def dron():
    m = Malla()
    loft(m, [(3.0, 0, 0, 0.02, 0.02, 0.02, 2), (2.2, 0, 0, 0.3, 0.3, 0.3, 2), (-2.5, 0, 0, 0.35, 0.35, 0.35, 2),
             (-3.2, 0, 0, 0.25, 0.25, 0.25, 2)], (0.85, 0.3, 0.12), 16, 0.3)
    for lado in (-1, 1):
        superficie_ala(m, (0.6, -0.9, (0.0, 0.3 * lado)), (-0.3, -0.8, (0.0, 2.6 * lado)), 0.12, 0.05,
                       (0.9, 0.9, 0.88), 0.3, lado)
        superficie_ala(m, (-2.3, -3.1, (0.0, 0.3 * lado)), (-2.9, -3.2, (0.0, 1.1 * lado)), 0.08, 0.04,
                       (0.85, 0.3, 0.12), 0.3, lado)
    superficie_ala(m, (-2.2, -3.15, (0.3, 0.0)), (-2.9, -3.25, (1.2, 0.0)), 0.08, 0.04, (0.85, 0.3, 0.12), 0.3,
                   1, vertical=True)
    return m.arreglo()


def misil_suelto():
    m = Malla()
    _misil(m, -1.8, 3.65, 0.09, 0, 0)
    return m.arreglo()


def cabina():
    m = Malla()
    tablero = (0.10, 0.11, 0.12)
    gris = (0.20, 0.21, 0.22)
    caja(m, 5.72, 5.95, 0.30, 0.76, -0.47, 0.47, tablero)
    caja(m, 5.80, 6.08, 0.74, 0.80, -0.30, 0.30, (0.05, 0.05, 0.06), inclina=0.0)
    caja(m, 5.92, 6.02, 0.80, 0.83, -0.12, 0.12, gris)
    for lado in (-1, 1):
        caja(m, 5.97, 6.0, 0.80, 1.22, 0.185 * lado - 0.008, 0.185 * lado + 0.008, gris)
    for lado in (-1, 1):
        z0, z1 = sorted((0.32 * lado, 0.52 * lado))
        caja(m, 4.20, 5.40, 0.24, 0.47, z0, z1, gris)
        z0, z1 = sorted((0.50 * lado, 0.56 * lado))
        caja(m, 3.6, 5.9, 0.56, 0.70, z0, z1, (0.16, 0.17, 0.18))
    caja(m, 3.5, 5.95, 0.1, 0.32, -0.56, 0.56, (0.08, 0.08, 0.09))
    caja(m, 3.85, 4.15, 0.25, 1.62, -0.24, 0.24, (0.12, 0.12, 0.10))
    caja(m, 3.9, 4.2, 1.2, 1.55, -0.16, 0.16, (0.20, 0.16, 0.10))
    marco = (0.12, 0.13, 0.14)
    for i in range(14):
        t0 = math.pi * i / 14
        t1 = math.pi * (i + 1) / 14
        for x, ry, rz, cy in ((6.45, 0.5, 0.45, 0.86), (3.95, 0.62, 0.52, 0.86)):
            a = np.array([x, cy + ry * math.sin(t0), rz * math.cos(t0)])
            b = np.array([x, cy + ry * math.sin(t1), rz * math.cos(t1)])
            d = np.array([0.022, 0, 0])
            n0 = np.array([0, math.sin(t0), math.cos(t0)]) * 0.02
            n1 = np.array([0, math.sin(t1), math.cos(t1)]) * 0.02
            m.quad(a - d, b - d, b + d, a + d, marco)
            m.quad(a + d, b + d, b + d + n1, a + d + n0, marco)
            m.quad(a - d + n0, b - d + n1, b - d, a - d, marco)
    for lado in (-1, 1):
        a = np.array([6.32, 0.86, 0.46 * lado])
        b = np.array([3.95, 0.86, 0.52 * lado])
        caja(m, 3.95, 6.32, 0.66, 0.72, min(0.5 * lado, 0.55 * lado), max(0.5 * lado, 0.55 * lado), marco)
    for z in (-0.18, 0.0, 0.18):
        caja(m, 6.28, 6.31, 1.33, 1.37, z - 0.07, z + 0.07, (0.5, 0.55, 0.6), 1.0)
    a = m.arreglo()
    a[:, 1] += ALZA
    return a


ALZA = 0.3
OJO = np.array([5.02, 1.36, 0.0])
PALANCA_PIVOTE = np.array([5.42, 0.42, 0.0])


def palanca():
    m = Malla()
    cilindro(m, 0.0, 0.42, 0.018, 0.016, 5.35, 0.0, (0.08, 0.08, 0.08), 8, eje=1)
    cilindro(m, 0.42, 0.56, 0.03, 0.028, 5.35, 0.0, (0.1, 0.09, 0.08), 8, eje=1)
    caja(m, 5.32, 5.38, 0.52, 0.58, -0.005, 0.005, (0.6, 0.1, 0.05))
    a = m.arreglo()
    a[:, 0] -= PALANCA_PIVOTE[0]
    a[:, 1] -= 0.0
    return a


ACELERADOR_PIVOTE = np.array([5.0, 0.56 + ALZA, -0.43])


def acelerador():
    m = Malla()
    caja(m, -0.03, 0.03, 0.0, 0.16, -0.025, 0.025, (0.12, 0.12, 0.12))
    caja(m, -0.06, 0.06, 0.14, 0.2, -0.04, 0.04, (0.18, 0.16, 0.12))
    return m.arreglo()
