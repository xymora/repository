from dataclasses import dataclass
import zlib

import numpy as np

import config as C

ALCANCE = 40.0
DETECCION = 60.0
APUNTADO = 0.4
DESTELLOS_HZ = 5.0
DESTELLO_DURACION = 0.3
CONO = np.radians(35.0)
APUNTADORES = np.radians([40.0, -40.0, 0.0])
NOMBRES_APUNTADORES = ("frontal-izq", "frontal-der", "frontal")
ALTURA_LASER = 1.0
PHI_PIE = np.radians(60.0)
SEP_MIN, SEP_MAX = 60.0, 150.0
MIN_PUNTOS = 3
MARGEN_SALIDA = 25.0
MARGEN_META = 20.0
LATERAL = (2.5, 3.5)
ALTURA = (1.0, 1.5)
_N_LOS = 12
_PREFILTRO = ALCANCE * 1.5
_S = np.linspace(0.0, 1.0, _N_LOS + 2)[1:-1]
_SAL = 0x50C7


@dataclass(frozen=True)
class PuntoControl:
    x: float
    lado: int
    lateral: float
    altura: float
    indice: int
    es_b: bool = False


def _entropia(semilla):
    def ints(s):
        if s is None:
            return []
        if isinstance(s, (bool, np.bool_)):
            return [int(s)]
        if isinstance(s, (int, np.integer)):
            return [int(s) % (1 << 63)]
        if isinstance(s, (float, np.floating)):
            return [int(abs(float(s)) * 1000) % (1 << 63)]
        if isinstance(s, (tuple, list, np.ndarray)):
            out = []
            for e in s:
                out += ints(e)
            return out
        return [zlib.crc32(str(s).encode("utf-8"))]
    return ints(semilla) + [_SAL]


def _tramo(rng, a, b, fijo_a, fijo_b, minimo):
    L = max(b - a, 1.0)
    n_min = int(np.ceil(L / SEP_MAX)) + 1
    n_max = max(n_min, int(np.floor(L / SEP_MIN)) + 1)
    k = max(int(rng.integers(n_min, n_max + 1)), minimo)
    base = a + L * np.arange(k) / (k - 1)
    s = L / (k - 1)
    jit = rng.uniform(-0.2, 0.2, size=k) * s
    jit[0] = 0.0 if fijo_a else abs(jit[0])
    jit[-1] = 0.0 if fijo_b else -abs(jit[-1])
    return base + jit


class PuntosControl:

    def __init__(self, pista, semilla=None, n=None):
        self.pista = pista
        if semilla is None:
            semilla = getattr(pista, "semilla", None)
        self.semilla = semilla
        rng = np.random.default_rng(_entropia(semilla))
        a = float(pista.salida) + MARGEN_SALIDA
        b = float(pista.meta) - MARGEN_META
        if b - a < 30.0:
            a, b = float(pista.salida) + 0.3 * (pista.meta - pista.salida), \
                float(pista.meta) - 0.1 * (pista.meta - pista.salida)
        x_b = getattr(pista, "x_b", None)
        circuito = getattr(pista, "circuito", "no") not in (None, "no", False) and x_b is not None
        if n is not None:
            xs = a + (b - a) * np.arange(int(n)) / max(int(n) - 1, 1)
            if circuito:
                xs[np.argmin(np.abs(xs - x_b))] = x_b
            xs = np.unique(np.round(xs, 3))
            jit = rng.uniform(-0.1, 0.1, size=len(xs)) * ((b - a) / max(len(xs) - 1, 1))
            jit[0], jit[-1] = abs(jit[0]), -abs(jit[-1])
            if circuito:
                jit[np.isclose(xs, x_b)] = 0.0
            xs = xs + jit
        elif circuito and a + 15.0 < x_b < b - 15.0:
            ida = _tramo(rng, a, float(x_b), False, True, 2)
            vuelta = _tramo(rng, float(x_b), b, True, False, 2)
            xs = np.concatenate([ida, vuelta[1:]])
        else:
            xs = _tramo(rng, a, b, False, False, MIN_PUNTOS)
        xs = np.sort(np.asarray(xs, dtype=float))
        K = len(xs)
        lado = np.where(rng.random(K) < 0.5, 1, -1)
        lateral = rng.uniform(*LATERAL, size=K)
        altura = rng.uniform(*ALTURA, size=K)
        es_b = np.zeros(K, dtype=bool)
        if circuito:
            es_b[np.argmin(np.abs(xs - x_b))] = True

        self.K = K
        self.X = xs
        self.lado = lado.astype(np.int64)
        self.lateral = lateral
        self.altura = altura
        self.es_b = es_b
        self.puntos = [PuntoControl(float(xs[k]), int(lado[k]), float(lateral[k]),
                                    float(altura[k]), k, bool(es_b[k])) for k in range(K)]
        i = pista.indice(xs)
        r = pista.rumbo[i]
        d = lado * lateral
        self.mapa_xy = np.stack([pista.mapa_x[i] - d * np.sin(r),
                                 pista.mapa_y[i] + d * np.cos(r)], axis=1)
        self.z_reflector = np.asarray(pista.altura(xs), dtype=float) + altura
        self._Xc = np.append(xs, np.inf)
        self.sim = None
        self._reiniciar(0)

    def _reiniciar(self, n):
        K = self.K
        self.n_total = n
        self.registrados = np.zeros((n, K), dtype=bool)
        self.fallados = np.zeros((n, K), dtype=bool)
        self.tiempos = np.full((n, K), np.nan)
        self.velocidades = np.full((n, K), np.nan)
        self.laterales = np.full((n, K), np.nan)
        self.inclinaciones = np.full((n, K), np.nan)
        self.siguiente = np.zeros(n, dtype=np.int64)
        self.fijado = np.zeros(n, dtype=bool)
        self.iluminado = np.zeros((n, K), dtype=bool)
        self.detectado = np.zeros((n, K), dtype=bool)
        self.t_fijado = np.full(n, np.inf)
        self._x_prev = np.zeros(n)

    def posicion_mapa(self, k):
        return float(self.mapa_xy[k, 0]), float(self.mapa_xy[k, 1])

    def altura_reflector(self, k):
        return float(self.z_reflector[k])

    def enganchar(self, sim):
        self.sim = sim
        self._reiniciar(sim.n_total)
        self._x_prev[sim.ids] = sim.px
        sim.puntos_control = self
        if hasattr(sim, "observadores"):
            if self not in sim.observadores:
                sim.observadores.append(self)
            return self
        paso_orig = sim.paso
        pc = self

        def paso(*args, **kw):
            antes = sim.reintentos.copy()
            r = paso_orig(*args, **kw)
            reg = np.flatnonzero(sim.reintentos > antes)
            if len(reg):
                reg = reg[np.isin(reg, sim.ids)]
                if len(reg):
                    pc.al_regresar(sim, reg, None)
            pc.observar(sim)
            return r
        sim.paso = paso
        return self

    def __call__(self, sim):
        self.observar(sim)

    def al_regresar(self, sim, ids, t_restaurado=None):
        ids = np.asarray(ids, dtype=np.int64)
        if len(ids) == 0 or self.K == 0:
            return
        pos = np.searchsorted(sim.ids, ids)
        x = sim.px[pos]
        delante = self.X[None, :] > x[:, None]
        for arr, vacio in ((self.registrados, False), (self.fallados, False), (self.iluminado, False),
                           (self.detectado, False),
                           (self.tiempos, np.nan), (self.velocidades, np.nan),
                           (self.laterales, np.nan), (self.inclinaciones, np.nan)):
            sub = arr[ids]
            sub[delante] = vacio
            arr[ids] = sub
        self.siguiente[ids] = np.searchsorted(self.X, x, side="right")
        self.fijado[ids] = False
        self.t_fijado[ids] = np.inf
        self._x_prev[ids] = x

    def _laser(self, sim, pos, k, seguir=False):
        p = self.pista
        xc = sim.px[pos]
        ic = p.indice(xc)
        r = p.rumbo[ic]
        lat = sim.lat[pos]
        dxm = self.mapa_xy[k, 0] - (p.mapa_x[ic] - lat * np.sin(r))
        dym = self.mapa_xy[k, 1] - (p.mapa_y[ic] + lat * np.cos(r))
        z0 = p.altura(xc) + ALTURA_LASER
        z1 = self.z_reflector[k]
        dist = np.sqrt(dxm * dxm + dym * dym + (z1 - z0) ** 2)
        rel = np.arctan2(dym, dxm) - (r + sim.psi[pos])
        dif = np.abs((rel[:, None] - APUNTADORES[None, :] + np.pi) % (2 * np.pi) - np.pi)
        ok = (dist <= ALCANCE) & ((dif <= CONO).any(1) | seguir)
        if ok.any():
            w = np.flatnonzero(ok)
            xm = xc[w, None] + _S[None, :] * (self.X[k[w]] - xc[w])[:, None]
            haz = z0[w, None] + _S[None, :] * (z1[w] - z0[w])[:, None]
            ok[w] = ~(p.altura(xm) > haz).any(1)
        return ok, np.argmin(dif, axis=1), dist

    def observar(self, sim):
        ids = sim.ids
        if len(ids) == 0 or self.K == 0:
            return
        px = sim.px
        kp = self.siguiente[ids]
        xk = self._Xc[kp]
        ahead = xk - px

        det = np.flatnonzero((ahead > 0) & (ahead <= DETECCION))
        if len(det):
            self.detectado[ids[det], kp[det]] = True
        cand = np.flatnonzero((ahead > 0) & (ahead <= ALCANCE) & ~self.fijado[ids])
        if len(cand):
            ok, _, _ = self._laser(sim, cand, kp[cand])
            if ok.any():
                self.fijado[ids[cand[ok]]] = True
                self.t_fijado[ids[cand[ok]]] = sim.t
                self.detectado[ids[cand[ok]], kp[cand[ok]]] = True
        esp = np.flatnonzero(self.fijado[ids] & (kp < self.K)
                             & (sim.t - self.t_fijado[ids] >= APUNTADO))
        if len(esp):
            esp = esp[~self.iluminado[ids[esp], kp[esp]]]
            esp = esp[self.destello(sim.t, kp[esp])]
            if len(esp):
                ok, _, _ = self._laser(sim, esp, kp[esp], seguir=True)
                self.iluminado[ids[esp[ok]], kp[esp[ok]]] = True

        x0 = self._x_prev[ids]
        cruza = (px >= xk) & (x0 < xk)
        if cruza.any():
            c = np.flatnonzero(cruza)
            g = ids[c]
            k = kp[c]
            phi = sim.phi[c]
            lat = sim.lat[c]
            en_pie = (np.abs(phi) < PHI_PIE) & (sim.derrape[c] <= C.DERRAPE_MAX) \
                & np.isfinite(phi)
            dentro = np.abs(lat) <= C.ANCHO_CAMINO / 2
            previos = np.arange(self.K)[None, :] < k[:, None]
            en_orden = ~(previos & ~self.registrados[g]).any(1)
            bien = self.fijado[g] & en_pie & dentro & en_orden
            frac = np.clip((px[c] - self.X[k]) / np.maximum(px[c] - x0[c], 1e-9), 0.0, 1.0)
            v = sim.vx[c] * np.cos(sim.th[c]) + sim.vy[c] * np.sin(sim.th[c])
            gb, kb = g[bien], k[bien]
            self.registrados[gb, kb] = True
            self.tiempos[gb, kb] = (sim.t - frac * C.DT_CONTROL)[bien]
            self.velocidades[gb, kb] = v[bien]
            self.laterales[gb, kb] = lat[bien]
            self.inclinaciones[gb, kb] = phi[bien]
            self.fallados[g[~bien], k[~bien]] = True
            self.siguiente[g] = k + 1
            self.fijado[g] = False
            self.t_fijado[g] = np.inf
        self._x_prev[ids] = px

    def _haces(self):
        sim = self.sim
        if sim is None or len(sim.ids) == 0 or self.K == 0:
            return []
        pos = np.flatnonzero(self.fijado[sim.ids] & (sim.t - self.t_fijado[sim.ids] >= APUNTADO))
        if len(pos) == 0:
            return []
        k = self.siguiente[sim.ids[pos]]
        vivos = k < self.K
        pos, k = pos[vivos], k[vivos]
        ok, j, dist = self._laser(sim, pos, k, seguir=True)
        inten = np.clip(1.0 - dist / ALCANCE, 0.0, 1.0) * 0.8 + 0.2
        return list(zip(sim.ids[pos][ok].tolist(), k[ok].tolist(), j[ok].tolist(),
                        inten[ok].tolist()))

    def destello(self, t, k):
        return (t * DESTELLOS_HZ + 0.37 * k) % 1.0 < DESTELLO_DURACION

    @property
    def haces(self):
        return [(i, k, a) for i, k, _, a in self._haces()]

    @property
    def haces_detalle(self):
        return self._haces()

    def pasados(self):
        return self.registrados.sum(1)

    def exitosas(self, sim=None):
        sim = sim or self.sim
        llegaron = (sim.llegaron() if sim is not None else np.ones(self.n_total, bool))
        return llegaron & self.registrados.all(1) & ~self.fallados.any(1)

    def resumen(self, ids=None):
        ex = self.exitosas()
        ids = range(self.n_total) if ids is None else np.atleast_1d(ids).tolist()
        motos = {}
        for i in ids:
            det = []
            for k in range(self.K):
                estado = ("registrado" if self.registrados[i, k] else
                          "fallado" if self.fallados[i, k] else "pendiente")
                d = {"k": k, "x": float(self.X[k]), "es_b": bool(self.es_b[k]), "estado": estado}
                if estado == "registrado":
                    d.update(t=float(self.tiempos[i, k]), v=float(self.velocidades[i, k]),
                             lat=float(self.laterales[i, k]),
                             phi=float(self.inclinaciones[i, k]))
                det.append(d)
            motos[int(i)] = {"pasados": int(self.registrados[i].sum()), "total": self.K,
                             "fallados": int(self.fallados[i].sum()),
                             "exitosa": bool(ex[i]), "detalles": det}
        return {"total": self.K,
                "puntos": [{"k": q.indice, "x": q.x, "lado": q.lado, "lateral": q.lateral,
                            "altura": q.altura, "es_b": q.es_b} for q in self.puntos],
                "exitosas": int(ex.sum()), "motos": motos}


def exitosas(sim):
    pc = getattr(sim, "puntos_control", None)
    if pc is None:
        return sim.llegaron()
    return pc.exitosas(sim)
