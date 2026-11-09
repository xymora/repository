from collections import deque
from functools import lru_cache

import numpy as np

import config as C

W, H = C.ANCHO, C.ALTO
DIRS = np.array(((-1, 0), (0, -1), (1, 0), (0, 1)))
OPUESTA = np.array((2, 3, 0, 1))
ARRIBA, IZQUIERDA, ABAJO, DERECHA = range(4)

HY = 10
FILA_ANILLO_SUP, FILA_ANILLO_INF = HY + 1, HY + 7
FILA_TUNEL = HY + 4
CASA_FILAS = (HY + 2, HY + 6)
CASA_COLS = (10, 17)
CASA_CENTRO = (HY + 4, 13)
SALIDA_CASA = (HY + 1, 13)
PUERTA = ((HY + 2, 13), (HY + 2, 14))

XS_OPCIONES = ((1, 5, 9, 12), (1, 4, 9, 12), (1, 6, 9, 12), (1, 4, 7, 9, 12), (1, 3, 6, 9, 12),
               (1, 5, 7, 9, 12))
YS_ARRIBA = ((1, 5, 8, 11), (1, 4, 8, 11), (1, 4, 7, 11), (1, 3, 6, 8, 11))
YS_ABAJO = ((17, 20, 23, 26, 29), (17, 21, 25, 29), (17, 20, 24, 27, 29), (17, 19, 23, 26, 29),
            (17, 20, 23, 25, 29))
TEMAS = (
    ((33, 33, 222), (110, 130, 255), (255, 184, 151), "azul"),
    ((222, 60, 160), (255, 150, 210), (255, 220, 200), "rosa"),
    ((230, 120, 30), (255, 190, 110), (230, 230, 255), "naranja"),
    ((20, 190, 210), (140, 240, 250), (255, 230, 120), "cian"),
    ((210, 40, 30), (255, 140, 100), (255, 230, 150), "volcán"),
    ((140, 70, 230), (200, 160, 255), (255, 255, 255), "violeta"),
)


def _espejo(c):
    return W - 1 - c


def _en_casa(r, c):
    return CASA_FILAS[0] <= r <= CASA_FILAS[1] and CASA_COLS[0] <= c <= CASA_COLS[1]


def generar(semilla):
    rng = np.random.default_rng(semilla)
    for _ in range(200):
        g = _intentar(rng)
        if g is not None:
            return g
    raise RuntimeError("no se pudo generar el laberinto")


def _intentar(rng):
    xs_izq = XS_OPCIONES[rng.integers(len(XS_OPCIONES))]
    xs = sorted(set(xs_izq) | {_espejo(c) for c in xs_izq})
    ys = sorted(set(YS_ARRIBA[rng.integers(len(YS_ARRIBA))]) | {FILA_TUNEL}
                | set(YS_ABAJO[rng.integers(len(YS_ABAJO))]))
    nodos = {(r, c) for r in ys for c in xs if not _en_casa(r, c)}
    segs = set()
    for r in ys:
        fila = sorted(c for (rr, c) in nodos if rr == r)
        for a, b in zip(fila, fila[1:]):
            if not any(_en_casa(r, c) for c in range(a, b + 1)):
                segs.add(((r, a), (r, b)))
    for c in xs:
        col = sorted(r for (r, cc) in nodos if cc == c)
        for a, b in zip(col, col[1:]):
            if not any(_en_casa(r, c) for r in range(a, b + 1)):
                segs.add(((a, c), (b, c)))
    tuneles = {FILA_TUNEL}
    otras = [r for r in ys if r not in (FILA_TUNEL, ys[0], ys[-1], FILA_ANILLO_SUP, FILA_ANILLO_INF)]
    if otras and rng.random() < 0.4:
        tuneles.add(int(rng.choice(otras)))
    abajo = [r for r in ys if r > FILA_ANILLO_INF]
    fila_inicio = abajo[1] if len(abajo) > 2 else abajo[0]
    centro_izq, centro_der = max(c for c in xs if c < W // 2), min(c for c in xs if c >= W // 2)

    def forzado(s):
        (r1, c1), (r2, c2) = s
        if r1 == r2 and r1 in (FILA_ANILLO_SUP, FILA_ANILLO_INF) and 9 <= c1 and c2 <= _espejo(9):
            return True
        if c1 == c2 and c1 in (9, _espejo(9)) and FILA_ANILLO_SUP <= r1 and r2 <= FILA_ANILLO_INF:
            return True
        if r1 == r2 == fila_inicio and (c1, c2) == (centro_izq, centro_der):
            return True
        return False

    def espejo_seg(s):
        (r1, c1), (r2, c2) = s
        a, b = (r1, _espejo(c1)), (r2, _espejo(c2))
        return (min(a, b), max(a, b))

    def grados(conj):
        g = dict.fromkeys(nodos, 0)
        for a, b in conj:
            g[a] += 1
            g[b] += 1
        for r in tuneles:
            g[(r, xs[0])] += 1
            g[(r, xs[-1])] += 1
        return g

    def conectado(conj):
        ady = {n: [] for n in nodos}
        for a, b in conj:
            ady[a].append(b)
            ady[b].append(a)
        for r in tuneles:
            ady[(r, xs[0])].append((r, xs[-1]))
            ady[(r, xs[-1])].append((r, xs[0]))
        inicio = next(iter(nodos))
        vistos, cola = {inicio}, [inicio]
        while cola:
            n = cola.pop()
            for m in ady[n]:
                if m not in vistos:
                    vistos.add(m)
                    cola.append(m)
        return len(vistos) == len(nodos)

    if min(grados(segs).values()) < 2 or not conectado(segs):
        return None
    nf, nc = len(ys) - 1, len(xs) - 1
    FUERA = nf * nc
    padre = list(range(FUERA + 1))
    tam = [1] * FUERA + [0]

    def raiz(a):
        while padre[a] != a:
            padre[a] = padre[padre[a]]
            a = padre[a]
        return a

    def unir(a, b, padre=padre, tam=tam):
        a, b = raiz(a), raiz(b)
        if a != b:
            if b == FUERA:
                a, b = b, a
            padre[b] = a
            tam[a] += tam[b]

    casa = {i * nc + j for i in range(nf) for j in range(nc)
            if ys[i] < CASA_FILAS[1] and ys[i + 1] > CASA_FILAS[0]
            and xs[j] < CASA_COLS[1] and xs[j + 1] > CASA_COLS[0]}

    def celdas(s):
        (r1, c1), (r2, c2) = s
        if r1 == r2:
            if c1 not in xs or xs.index(c1) + 1 >= len(xs) or xs[xs.index(c1) + 1] != c2:
                return None
            j, i = xs.index(c1), ys.index(r1)
            return ((i - 1) * nc + j if i > 0 else FUERA, i * nc + j if i < nf else FUERA)
        if r1 not in ys or ys.index(r1) + 1 >= len(ys) or ys[ys.index(r1) + 1] != r2:
            return None
        i, j = ys.index(r1), xs.index(c1)
        return (i * nc + j - 1 if j > 0 else FUERA, i * nc + j if j < nc else FUERA)

    for i in range(nf):
        for j in range(nc):
            k = i * nc + j
            if j + 1 < nc and ((ys[i], xs[j + 1]), (ys[i + 1], xs[j + 1])) not in segs:
                unir(k, k + 1)
            if i + 1 < nf and ((ys[i + 1], xs[j]), (ys[i + 1], xs[j + 1])) not in segs:
                unir(k, k + nc)
    raiz_casa = {raiz(k) for k in casa}
    max_bloque = int(rng.integers(3, 5))

    candidatos = [s for s in segs if not forzado(s) and s[0][1] <= W // 2 - 1 and celdas(s)]
    rng.shuffle(candidatos)
    meta = int(round(C.QUITAR_PASILLOS * len(candidatos)))
    quitados = 0
    for s in candidatos:
        if quitados >= meta:
            break
        par = {s, espejo_seg(s)}
        if not par <= segs:
            continue
        p2, t2 = padre[:], tam[:]
        valido = True
        for q in par:
            a, b = celdas(q)

            def r_(x):
                while p2[x] != x:
                    x = p2[x]
                return x
            ra, rb = r_(a), r_(b)
            if ra == rb:
                valido = False
                break
            if ra in raiz_casa or rb in raiz_casa:
                valido = False
                break
            if FUERA in (ra, rb):
                otro = rb if ra == FUERA else ra
                if t2[otro] > 2:
                    valido = False
                    break
                p2[otro] = FUERA
            else:
                if t2[ra] + t2[rb] > max_bloque:
                    valido = False
                    break
                p2[rb] = ra
                t2[ra] += t2[rb]
        if not valido:
            continue
        prueba = segs - par
        gr = grados(prueba)
        if min(gr[n] for p in par for n in p) < 2 or not conectado(prueba):
            continue
        segs = prueba
        padre[:], tam[:] = p2, t2
        quitados += 1
    g = [["#"] * W for _ in range(H)]
    for (r1, c1), (r2, c2) in segs:
        for r in range(r1, r2 + 1):
            for c in range(c1, c2 + 1):
                g[r][c] = "."
    for r in tuneles:
        for c in range(0, xs[0]):
            g[r][c] = " "
        for c in range(xs[-1] + 1, W):
            g[r][c] = " "
    for r in range(CASA_FILAS[0], CASA_FILAS[1] + 1):
        for c in range(CASA_COLS[0], CASA_COLS[1] + 1):
            borde = r in CASA_FILAS or c in CASA_COLS
            g[r][c] = "#" if borde else "H"
    for r, c in PUERTA:
        g[r][c] = "-"
    for r in range(FILA_ANILLO_SUP, FILA_ANILLO_INF + 1):
        for c in range(7, W - 7):
            if g[r][c] == ".":
                g[r][c] = " "
    for r in tuneles:
        for c in list(range(0, 6)) + list(range(W - 6, W)):
            if g[r][c] == ".":
                g[r][c] = " "
    g[fila_inicio][13] = g[fila_inicio][14] = " "
    arriba = [r for r in ys if r < FILA_ANILLO_SUP]
    for r in (arriba[1] if len(arriba) > 2 else arriba[0], abajo[-2]):
        for c in (xs[0], xs[-1]):
            g[r][c] = "o"
    return ["".join(f) for f in g]


class Laberinto:

    def __init__(self, semilla, tema=0):
        self.semilla = int(semilla)
        self.tema = int(tema) % len(TEMAS)
        self.grid = generar(self.semilla)
        g = self.grid
        idx = -np.ones((H, W), dtype=np.int32)
        rc = []
        for r in range(H):
            for c in range(W):
                if g[r][c] != "#":
                    idx[r, c] = len(rc)
                    rc.append((r, c))
        self.idx = idx
        self.rc = np.array(rc, dtype=np.int32)
        self.T = T = len(rc)
        es_casa = np.array([g[r][c] in "H-" for r, c in rc])
        es_puerta = np.array([g[r][c] == "-" for r, c in rc])
        self.es_casa = es_casa

        def tabla(permitido):
            v = -np.ones((T, 4), dtype=np.int32)
            for t, (r, c) in enumerate(rc):
                if not permitido[t]:
                    continue
                for d, (dr, dc) in enumerate(DIRS):
                    rr, cc = r + dr, (c + dc) % W
                    if 0 <= rr < H and idx[rr, cc] >= 0 and permitido[idx[rr, cc]]:
                        v[t, d] = idx[rr, cc]
            return v

        self.vec_pac = tabla(~es_casa)
        self.vec_fuera = self.vec_pac
        v = tabla(np.ones(T, bool))
        for t in np.flatnonzero(es_puerta):
            v[t, IZQUIERDA] = v[t, DERECHA] = -1
        for t in range(T):
            for d in (IZQUIERDA, DERECHA):
                if v[t, d] >= 0 and es_puerta[v[t, d]]:
                    v[t, d] = -1
        self.vec_casa = v
        self.D = self._distancias(v)
        self.puntos0 = np.array([g[r][c] == "." for r, c in rc])
        self.energ0 = np.array([g[r][c] == "o" for r, c in rc])
        self.n_puntos = int(self.puntos0.sum() + self.energ0.sum())
        r_t = self.rc[:, 0]
        c_t = self.rc[:, 1]
        filas_tunel = {r for r in range(H) if g[r][0] != "#"}
        self.tunel = np.array([r in filas_tunel and (c <= 5 or c >= W - 6) for r, c in rc])
        self.filas_tunel = sorted(filas_tunel)
        self.t_salida = int(idx[SALIDA_CASA])
        self.t_centro = int(idx[CASA_CENTRO])
        self.t_fruta = int(idx[FILA_ANILLO_INF, 13])
        fila_inicio = next(r for r in range(FILA_ANILLO_INF + 1, H)
                           if g[r][13] == " " and g[r][14] == " ")
        self.t_pac = int(idx[fila_inicio, 13])
        self.t_fant0 = np.array([self.t_salida, self.t_centro, idx[CASA_CENTRO[0], 11],
                                 idx[CASA_CENTRO[0], 16]], dtype=np.int32)
        self.dir_fant0 = np.array([IZQUIERDA, ABAJO, ARRIBA, ARRIBA])
        self.grado = (self.vec_pac >= 0).sum(1)
        self._cruces()
        self.r_t, self.c_t = r_t, c_t

    @staticmethod
    def _distancias(v):
        T = len(v)
        D = np.full((T, T), 9999, dtype=np.int16)
        for s in range(T):
            fila = D[s]
            fila[s] = 0
            cola = deque([s])
            while cola:
                t = cola.popleft()
                dd = fila[t] + 1
                for n in v[t]:
                    if n >= 0 and fila[n] > dd:
                        fila[n] = dd
                        cola.append(n)
        return D

    def _cruces(self):
        T = self.T
        cruce = -np.ones((T, 4), dtype=np.int32)
        largo = np.zeros((T, 4), dtype=np.int16)
        v = self.vec_pac
        for t in range(T):
            for d in range(4):
                n = v[t, d]
                if n < 0:
                    continue
                prev, cur, k = t, n, 1
                while self.grado[cur] == 2 and k < 200:
                    sig = [m for m in v[cur] if m >= 0 and m != prev]
                    if not sig:
                        break
                    prev, cur, k = cur, sig[0], k + 1
                cruce[t, d] = cur
                largo[t, d] = k
        self.cruce, self.largo = cruce, largo

    def validar(self):
        pac = ~self.es_casa
        assert (self.grado[pac] >= 2).all(), "hay callejones sin salida"
        assert (self.D[self.t_pac][pac] < 9999).all(), "el laberinto no está conectado"
        assert (self.D[self.t_fant0][:, self.t_salida] < 9999).all(), "la casa no tiene salida"
        assert self.n_puntos > 100
        return True


@lru_cache(maxsize=16)
def cargar(semilla, tema=0):
    return Laberinto(semilla, tema)


class Nivel:

    def __init__(self, nivel, semilla_extra=0, semilla_lab=None, numero=None):
        self.nivel = int(nivel)
        (self.nombre, sem, tema, self.n_fantasmas, self.v_pac, self.v_pac_susto, self.v_fant,
         self.v_fant_susto, self.v_tunel, self.t_susto, self.elroy, horario) = C.NIVELES[self.nivel - 1]
        if sem is None:
            semilla = int(semilla_lab) if semilla_lab is not None else 1000 + int(semilla_extra) % 100000
            if numero is not None:
                self.nombre = f"{self.nombre} #{numero}"
                tema = tema + numero - 1
        else:
            semilla = sem
        self.semilla_lab = semilla
        self.lab = cargar(semilla, tema)
        self.horario = C.HORARIOS[horario]
        self.semilla = int(semilla_extra)
