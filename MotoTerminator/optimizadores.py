import math

import numpy as np

import config as C
import red as R

__all__ = ["Optimizador", "GA", "GAV2", "SepCMAES", "ESAdam", "PGPE", "MAPElites",
           "OPTIMIZADORES", "crear", "desde_estado", "escala_genes"]


def escala_genes(capas):
    partes = []
    for a, b in zip(capas[:-1], capas[1:]):
        partes.append(np.full(a * b, 1 / np.sqrt(a)))
        partes.append(np.full(b, 0.2))
    return np.concatenate(partes)


def _js(x):
    if x is None:
        return None
    if isinstance(x, np.ndarray):
        return x.tolist()
    if isinstance(x, (np.floating, np.integer, np.bool_)):
        return x.item()
    return x


def _arr(x, dtype=float):
    return None if x is None else np.array(x, dtype=dtype)


def _limpiar(apt):
    apt = np.asarray(apt, dtype=float).copy()
    malo = ~np.isfinite(apt)
    if malo.any():
        apt[malo] = (apt[~malo].min() - 1e9) if (~malo).any() else -1e9
    return apt


def _rangos_centrados(f):
    n = len(f)
    r = np.empty(n)
    r[np.argsort(f, kind="stable")] = np.arange(n)
    return r / max(n - 1, 1) - 0.5


class Optimizador:
    nombre = "base"

    def __init__(self, pop=None, semilla=None, capas=None, rng=None, x0=None, dim=None):
        self.capas = tuple(capas or C.CAPAS)
        self.dim = int(dim or R.n_parametros(self.capas))
        self.pop = int(pop or C.POBLACION)
        if self.pop < 3:
            raise ValueError("pop debe ser ≥ 3 (fila 0 testigo + al menos 2 muestras)")
        self.rng = rng if rng is not None else np.random.default_rng(semilla)
        self.escala = escala_genes(self.capas) if dim is None or self.dim == R.n_parametros(self.capas) \
            else np.full(self.dim, 0.2)
        if x0 is None:
            x0 = R.aleatorios(1, self.capas, self.rng)[0] if self.dim == R.n_parametros(self.capas) \
                else self.rng.normal(0, 0.2, self.dim)
        self.x0 = np.array(x0, dtype=float).reshape(self.dim)
        self.generacion = 0
        self.campeona = None
        self.apt_campeona = None
        self._lote = None

    def ask(self):
        if self._lote is None:
            self._lote = self._muestrear()
            self._lote[0] = self.campeona if self.campeona is not None else self._centro()
        return self._lote.copy()

    def tell(self, pesos, aptitudes=None, descriptores=None, **kw):
        if aptitudes is None:
            if self._lote is None:
                raise RuntimeError("tell(aptitudes) sin ask() previo: pasa también los pesos")
            pesos, aptitudes = self._lote, pesos
        pesos = np.asarray(pesos, dtype=float)
        apt = _limpiar(aptitudes)
        if pesos.shape != (self.pop, self.dim) or apt.shape != (self.pop,):
            raise ValueError(f"se esperaban pesos {(self.pop, self.dim)} y aptitudes ({self.pop},)")
        if self._lote is None:
            self._lote = pesos.copy()
        desc = None if descriptores is None else np.asarray(descriptores, dtype=float)
        self._actualizar(pesos[1:], apt[1:], None if desc is None else desc[1:], **kw)
        i = int(np.argmax(apt))
        self.campeona, self.apt_campeona = pesos[i].copy(), float(apt[i])
        self.generacion += 1
        self._lote = None

    @property
    def mejor(self):
        if self.campeona is None:
            return None
        return self.campeona.copy(), self.apt_campeona

    def estado(self):
        d = {"clase": self.nombre, "pop": self.pop, "dim": self.dim, "capas": list(self.capas),
             "generacion": self.generacion, "rng": self.rng.bit_generator.state,
             "x0": _js(self.x0), "campeona": _js(self.campeona), "apt_campeona": self.apt_campeona,
             "lote": _js(self._lote)}
        d.update({k: _js(v) for k, v in self._estado_propio().items()})
        return d

    def cargar_estado(self, d):
        if d.get("clase") != self.nombre:
            raise ValueError(f"estado de {d.get('clase')!r}, se esperaba {self.nombre!r}")
        if int(d["dim"]) != self.dim or int(d["pop"]) != self.pop:
            raise ValueError("dim/pop del estado no coinciden con el optimizador")
        self.generacion = int(d["generacion"])
        self.rng.bit_generator.state = d["rng"]
        self.x0 = _arr(d["x0"])
        self.campeona = _arr(d["campeona"])
        self.apt_campeona = d["apt_campeona"]
        self._lote = _arr(d["lote"])
        self._cargar_propio(d)
        return self

    def _centro(self):
        return self.x0.copy()

    def _muestrear(self):
        raise NotImplementedError

    def _actualizar(self, pesos, apt, desc, **kw):
        raise NotImplementedError

    def _estado_propio(self):
        return {}

    def _cargar_propio(self, d):
        pass


class GA(Optimizador):
    nombre = "ga"

    def __init__(self, pop=None, semilla=None, capas=None, rng=None, poblacion_inicial=None,
                 elite=None, torneo=None, prob_cruce=None, prob_mutacion=None, sigma0=None,
                 inmigrantes=None, sigma_min=None, sigma_max=None, x0=None, dim=None):
        self.capas = tuple(capas or C.CAPAS)
        self.dim = int(dim or R.n_parametros(self.capas))
        self.pop = int(pop or C.POBLACION)
        self.rng = rng if rng is not None else np.random.default_rng(semilla)
        self.escala = escala_genes(self.capas)
        self.elite = C.ELITE if elite is None else int(elite)
        self.torneo = C.TORNEO if torneo is None else int(torneo)
        self.prob_cruce = C.PROB_CRUCE if prob_cruce is None else float(prob_cruce)
        self.prob_mutacion = C.PROB_MUTACION if prob_mutacion is None else float(prob_mutacion)
        self.sigma0 = C.SIGMA_MUTACION if sigma0 is None else float(sigma0)
        self.inmigrantes = C.INMIGRANTES if inmigrantes is None else float(inmigrantes)
        self.sigma_min = self.sigma0 if sigma_min is None else float(sigma_min)
        self.sigma_max = 2 * self.sigma0 if sigma_max is None else float(sigma_max)
        self.sigma = self.sigma0
        if poblacion_inicial is not None:
            self.pob = np.array(poblacion_inicial, dtype=float)
        else:
            self.pob = R.aleatorios(self.pop, self.capas, self.rng) if self.dim == R.n_parametros(self.capas) \
                else self.rng.normal(0, 0.2, (self.pop, self.dim))
        self.x0 = self.pob[0].copy()
        self.historial = []
        self.generacion = 0
        self.campeona, self.apt_campeona, self._lote = None, None, None

    def ask(self):
        return self.pob.copy()

    def tell(self, pesos, aptitudes=None, descriptores=None, nivel=0, **kw):
        if aptitudes is None:
            aptitudes = pesos
        apt = _limpiar(aptitudes)
        if apt.shape != (self.pop,):
            raise ValueError(f"se esperaban aptitudes ({self.pop},)")
        orden = np.argsort(-apt)
        lider = int(orden[0])
        self.campeona, self.apt_campeona = self.pob[lider].copy(), float(apt[lider])
        previos = [m for nv, m in self.historial if nv == nivel]
        if len(previos) >= 20 and np.mean(previos[-10:]) <= np.mean(previos[-20:-10]):
            self.sigma = min(self.sigma * 1.1, self.sigma_max)
        else:
            self.sigma = max(self.sigma * 0.97, self.sigma_min)
        rng, n = self.rng, self.dim
        nueva = [self.pob[i].copy() for i in orden[:self.elite]]
        n_inmig = int(round(self.inmigrantes * self.pop))
        while len(nueva) < self.pop - n_inmig:
            idx = rng.integers(self.pop, size=self.torneo)
            a = self.pob[int(idx[np.argmax(apt[idx])])]
            if rng.random() < self.prob_cruce:
                idx = rng.integers(self.pop, size=self.torneo)
                b = self.pob[int(idx[np.argmax(apt[idx])])]
                hijo = np.where(rng.random(n) < 0.5, a, b)
            else:
                hijo = a.copy()
            muta = rng.random(n) < self.prob_mutacion
            nueva.append(hijo + muta * rng.normal(0, self.sigma, n))
        if n_inmig:
            nueva.extend(R.aleatorios(n_inmig, self.capas, rng))
        self.pob = np.array(nueva)
        self.historial.append((nivel, float(apt[lider])))
        self.generacion += 1

    def estado(self):
        return {"clase": self.nombre, "pop": self.pop, "dim": self.dim, "capas": list(self.capas),
                "generacion": self.generacion, "rng": self.rng.bit_generator.state,
                "pob": _js(self.pob), "sigma": self.sigma, "historial": self.historial,
                "campeona": _js(self.campeona), "apt_campeona": self.apt_campeona,
                "params": dict(elite=self.elite, torneo=self.torneo, prob_cruce=self.prob_cruce,
                               prob_mutacion=self.prob_mutacion, sigma0=self.sigma0,
                               inmigrantes=self.inmigrantes, sigma_min=self.sigma_min,
                               sigma_max=self.sigma_max)}

    def cargar_estado(self, d):
        if d.get("clase") != self.nombre:
            raise ValueError(f"estado de {d.get('clase')!r}, se esperaba {self.nombre!r}")
        self.generacion = int(d["generacion"])
        self.rng.bit_generator.state = d["rng"]
        self.pob = _arr(d["pob"])
        self.sigma = float(d["sigma"])
        self.historial = [(int(a), float(b)) for a, b in d["historial"]]
        self.campeona = _arr(d["campeona"])
        self.apt_campeona = d["apt_campeona"]
        for k, v in d.get("params", {}).items():
            setattr(self, k, v)
        return self


class GAV2(Optimizador):
    nombre = "ga_v2"

    def __init__(self, pop=None, semilla=None, capas=None, rng=None, x0=None, dim=None,
                 elite=4, truncamiento=0.2, sigma0=0.3, sigma_min=0.02, sigma_max=1.0):
        super().__init__(pop, semilla, capas, rng, x0, dim)
        self.elite = int(elite)
        self.truncamiento = float(truncamiento)
        self.sigma0, self.sigma_min, self.sigma_max = float(sigma0), float(sigma_min), float(sigma_max)
        self.tau = 1.0 / math.sqrt(2.0 * math.sqrt(self.dim))
        m = self.pop - 1
        self.sigmas = np.full(m, self.sigma0)
        self.pob = self.x0 + self.rng.normal(0, 1, (m, self.dim)) * (self.sigma0 * self.escala)

    @property
    def sigma(self):
        return float(np.median(self.sigmas))

    def _muestrear(self):
        return np.vstack([self._centro()[None], self.pob])

    def _actualizar(self, pesos, apt, desc, **kw):
        m = self.pop - 1
        orden = np.argsort(-apt, kind="stable")
        n_padres = max(1, int(round(self.truncamiento * m)))
        padres = orden[:n_padres]
        e = min(max(self.elite - 1, 0), m)
        nueva = [pesos[i].copy() for i in orden[:e]]
        sig = [float(self.sigmas[i]) for i in orden[:e]]
        while len(nueva) < m:
            p = int(padres[self.rng.integers(n_padres)])
            s = float(np.clip(self.sigmas[p] * math.exp(self.tau * self.rng.normal()),
                              self.sigma_min, self.sigma_max))
            nueva.append(pesos[p] + self.rng.normal(0, 1, self.dim) * (s * self.escala))
            sig.append(s)
        self.pob, self.sigmas = np.array(nueva), np.array(sig)

    def _estado_propio(self):
        return {"pob": self.pob, "sigmas": self.sigmas}

    def _cargar_propio(self, d):
        self.pob, self.sigmas = _arr(d["pob"]), _arr(d["sigmas"])


class SepCMAES(Optimizador):
    nombre = "sep_cma"

    def __init__(self, pop=None, semilla=None, capas=None, rng=None, x0=None, dim=None,
                 sigma0=0.3):
        super().__init__(pop, semilla, capas, rng, x0, dim)
        n, lam = self.dim, self.pop - 1
        self.lam = lam
        self.mu = lam // 2
        w = np.log(self.mu + 0.5) - np.log(np.arange(1, self.mu + 1))
        self.w = w / w.sum()
        self.mueff = 1.0 / np.sum(self.w ** 2)
        mueff = self.mueff
        self.cs = (mueff + 2) / (n + mueff + 5)
        self.ds = 1 + 2 * max(0.0, math.sqrt((mueff - 1) / (n + 1)) - 1) + self.cs
        self.cc = (4 + mueff / n) / (n + 4 + 2 * mueff / n)
        c1 = 2 / ((n + 1.3) ** 2 + mueff)
        cmu = min(1 - c1, 2 * (mueff - 2 + 1 / mueff) / ((n + 2) ** 2 + mueff))
        f = (n + 2) / 3.0
        self.c1, self.cmu = c1 * f, cmu * f
        if self.c1 + self.cmu > 1:
            s = 1.0 / (self.c1 + self.cmu)
            self.c1, self.cmu = self.c1 * s, self.cmu * s
        self.chi = math.sqrt(n) * (1 - 1 / (4 * n) + 1 / (21 * n * n))
        self.m = self.x0 / self.escala
        self.sigma = float(sigma0)
        self.C = np.ones(n)
        self.ps = np.zeros(n)
        self.pc = np.zeros(n)
        self._z = None

    def _centro(self):
        return self.m * self.escala

    def _muestrear(self):
        self._z = self.rng.normal(0, 1, (self.lam, self.dim))
        x = self.m + self.sigma * np.sqrt(self.C) * self._z
        return np.vstack([self._centro()[None], x * self.escala])

    def _actualizar(self, pesos, apt, desc, **kw):
        if self._z is None:
            raise RuntimeError("tell() sin ask() previo")
        n = self.dim
        orden = np.argsort(-apt, kind="stable")[:self.mu]
        z = self._z[orden]
        y = np.sqrt(self.C) * z
        zw, yw = self.w @ z, self.w @ y
        self.m = self.m + self.sigma * yw
        self.ps = (1 - self.cs) * self.ps + math.sqrt(self.cs * (2 - self.cs) * self.mueff) * zw
        g = self.generacion + 1
        hs = float(np.linalg.norm(self.ps) / math.sqrt(1 - (1 - self.cs) ** (2 * g))
                   < (1.4 + 2 / (n + 1)) * self.chi)
        self.pc = (1 - self.cc) * self.pc + hs * math.sqrt(self.cc * (2 - self.cc) * self.mueff) * yw
        self.C = ((1 - self.c1 - self.cmu) * self.C
                  + self.c1 * (self.pc ** 2 + (1 - hs) * self.cc * (2 - self.cc) * self.C)
                  + self.cmu * (self.w @ (y ** 2)))
        self.C = np.maximum(self.C, 1e-20)
        self.sigma *= math.exp(min(1.0, (self.cs / self.ds) * (np.linalg.norm(self.ps) / self.chi - 1)))
        self._z = None

    def _estado_propio(self):
        return {"m": self.m, "sigma": self.sigma, "C": self.C, "ps": self.ps, "pc": self.pc,
                "z": self._z}

    def _cargar_propio(self, d):
        self.m, self.sigma, self.C = _arr(d["m"]), float(d["sigma"]), _arr(d["C"])
        self.ps, self.pc, self._z = _arr(d["ps"]), _arr(d["pc"]), _arr(d["z"])


class ESAdam(Optimizador):
    nombre = "es"

    def __init__(self, pop=None, semilla=None, capas=None, rng=None, x0=None, dim=None,
                 sigma=0.1, lr=0.03, beta1=0.9, beta2=0.999, decaimiento=0.0):
        super().__init__(pop, semilla, capas, rng, x0, dim)
        self.sigma, self.lr = float(sigma), float(lr)
        self.beta1, self.beta2, self.decaimiento = float(beta1), float(beta2), float(decaimiento)
        self.theta = self.x0 / self.escala
        self.m_adam = np.zeros(self.dim)
        self.v_adam = np.zeros(self.dim)
        self.t_adam = 0
        self.pares = (self.pop - 1) // 2
        self._eps = None

    def _centro(self):
        return self.theta * self.escala

    def _muestrear(self):
        self._eps = self.rng.normal(0, 1, (self.pares, self.dim))
        x = np.concatenate([self.theta + self.sigma * self._eps, self.theta - self.sigma * self._eps])
        filas = [self._centro()[None], x * self.escala]
        if (self.pop - 1) % 2:
            filas.append(self._centro()[None])
        return np.vstack(filas)

    def _actualizar(self, pesos, apt, desc, **kw):
        if self._eps is None:
            raise RuntimeError("tell() sin ask() previo")
        k = self.pares
        f = _rangos_centrados(apt[:2 * k])
        g = ((f[:k] - f[k:]) @ self._eps) / (2 * k * self.sigma)
        g = g - self.decaimiento * self.theta
        self.t_adam += 1
        self.m_adam = self.beta1 * self.m_adam + (1 - self.beta1) * g
        self.v_adam = self.beta2 * self.v_adam + (1 - self.beta2) * g * g
        mh = self.m_adam / (1 - self.beta1 ** self.t_adam)
        vh = self.v_adam / (1 - self.beta2 ** self.t_adam)
        self.theta = self.theta + self.lr * mh / (np.sqrt(vh) + 1e-8)
        self._eps = None

    def _estado_propio(self):
        return {"theta": self.theta, "m_adam": self.m_adam, "v_adam": self.v_adam,
                "t_adam": self.t_adam, "eps": self._eps, "sigma": self.sigma}

    def _cargar_propio(self, d):
        self.theta, self.m_adam, self.v_adam = _arr(d["theta"]), _arr(d["m_adam"]), _arr(d["v_adam"])
        self.t_adam, self._eps, self.sigma = int(d["t_adam"]), _arr(d["eps"]), float(d["sigma"])


class PGPE(Optimizador):
    nombre = "pgpe"

    def __init__(self, pop=None, semilla=None, capas=None, rng=None, x0=None, dim=None,
                 sigma0=0.1, vmax=None, alfa=None, momento=0.9, lr_sigma=0.1,
                 cambio_max_sigma=0.2):
        super().__init__(pop, semilla, capas, rng, x0, dim)
        self.mu = self.x0 / self.escala
        self.s = np.full(self.dim, float(sigma0))
        self.vmax = float(vmax) if vmax is not None else float(sigma0) * math.sqrt(self.dim) / 15.0
        self.alfa = float(alfa) if alfa is not None else self.vmax / 2
        self.momento, self.lr_sigma, self.cambio_max = float(momento), float(lr_sigma), float(cambio_max_sigma)
        self.v = np.zeros(self.dim)
        self.pares = (self.pop - 1) // 2
        self._eps = None

    @property
    def sigma(self):
        return float(np.mean(self.s))

    def _centro(self):
        return self.mu * self.escala

    def _muestrear(self):
        self._eps = self.rng.normal(0, 1, (self.pares, self.dim)) * self.s
        x = np.concatenate([self.mu + self._eps, self.mu - self._eps])
        filas = [self._centro()[None], x * self.escala]
        if (self.pop - 1) % 2:
            filas.append(self._centro()[None])
        return np.vstack(filas)

    def _actualizar(self, pesos, apt, desc, **kw):
        if self._eps is None:
            raise RuntimeError("tell() sin ask() previo")
        k = self.pares
        f = _rangos_centrados(apt[:2 * k])
        fp, fm = f[:k], f[k:]
        eps = self._eps
        g_mu = ((fp - fm) / 2) @ eps / k
        b = 0.0
        g_s = (((fp + fm) / 2 - b) @ ((eps ** 2 - self.s ** 2) / self.s)) / k
        ng = np.linalg.norm(g_mu)
        if ng > 0:
            self.v = self.momento * self.v + self.alfa * g_mu / ng
            nv = np.linalg.norm(self.v)
            if nv > self.vmax:
                self.v *= self.vmax / nv
        self.mu = self.mu + self.v
        rel = np.clip(self.lr_sigma * g_s / self.s, -self.cambio_max, self.cambio_max)
        self.s = np.maximum(self.s * (1 + rel), 1e-8)
        self._eps = None

    def _estado_propio(self):
        return {"mu_c": self.mu, "s": self.s, "v": self.v, "eps": self._eps}

    def _cargar_propio(self, d):
        self.mu, self.s, self.v, self._eps = _arr(d["mu_c"]), _arr(d["s"]), _arr(d["v"]), _arr(d["eps"])


class MAPElites(Optimizador):
    nombre = "map_elites"

    def __init__(self, pop=None, semilla=None, capas=None, rng=None, x0=None, dim=None,
                 bins=(10, 10), limites=((0.0, 90.0), (0.0, 1.0)), sigma_iso=0.1,
                 sigma_linea=0.2, sigma_inicial=0.5, exigir_descriptores=False):
        super().__init__(pop, semilla, capas, rng, x0, dim)
        self.exigir_descriptores = bool(exigir_descriptores)
        self._avisado = False
        self.bins = tuple(int(b) for b in bins)
        self.limites = np.array(limites, dtype=float)
        if self.limites.shape != (len(self.bins), 2):
            raise ValueError("limites debe tener un (min, max) por descriptor")
        self.sigma_iso, self.sigma_linea = float(sigma_iso), float(sigma_linea)
        self.sigma_inicial = float(sigma_inicial)
        celdas = int(np.prod(self.bins))
        self.arch_x = np.zeros((celdas, self.dim))
        self.arch_f = np.full(celdas, -np.inf)
        self.arch_d = np.zeros((celdas, len(self.bins)))

    @property
    def ocupadas(self):
        return np.flatnonzero(np.isfinite(self.arch_f))

    @property
    def cobertura(self):
        return len(self.ocupadas) / len(self.arch_f)

    def celda(self, d):
        d = np.atleast_2d(d)
        lo, hi = self.limites[:, 0], self.limites[:, 1]
        u = np.clip((d - lo) / np.maximum(hi - lo, 1e-12), 0, 1 - 1e-12)
        idx = np.floor(u * np.array(self.bins)).astype(int)
        return np.ravel_multi_index(idx.T, self.bins)

    def descriptor_genotipo(self, pesos):
        pesos = np.atleast_2d(pesos)
        k = len(self.bins)
        z = pesos[:, -3:][:, [0, 2, 1][:k]] / 0.5
        lo, hi = self.limites[:, 0], self.limites[:, 1]
        return lo + (hi - lo) * (0.5 + 0.5 * np.tanh(z))

    def _muestrear(self):
        m = self.pop - 1
        occ = self.ocupadas
        if len(occ) == 0:
            x = self.x0 + self.rng.normal(0, 1, (m, self.dim)) * (self.sigma_inicial * self.escala)
        else:
            i = occ[self.rng.integers(len(occ), size=m)]
            j = occ[self.rng.integers(len(occ), size=m)]
            xi, xj = self.arch_x[i], self.arch_x[j]
            x = (xi + self.rng.normal(0, 1, (m, self.dim)) * (self.sigma_iso * self.escala)
                 + self.sigma_linea * (xj - xi) * self.rng.normal(0, 1, (m, 1)))
        return np.vstack([self._centro()[None], x])

    def _centro(self):
        return self.x0.copy() if self.campeona is None else self.campeona.copy()

    def _actualizar(self, pesos, apt, desc, **kw):
        if desc is None:
            if self.exigir_descriptores:
                raise ValueError("MAP-Elites necesita tell(..., descriptores=ndarray (pop, %d))"
                                 % len(self.bins))
            if not self._avisado:
                import warnings
                warnings.warn("MAP-Elites sin descriptores de conducta: se usa un descriptor "
                              "GENOTÍPICO de respaldo (sesgos de acelerador y dirección). Pasa "
                              "descriptores=(vel_media_kmh, invasion) para el MAP-Elites real.")
                self._avisado = True
            desc = self.descriptor_genotipo(pesos)
        cel = self.celda(desc)
        for k in np.argsort(-apt, kind="stable"):
            c = cel[k]
            if apt[k] > self.arch_f[c]:
                self.arch_f[c], self.arch_x[c], self.arch_d[c] = apt[k], pesos[k], desc[k]

    def _estado_propio(self):
        occ = self.ocupadas
        return {"bins": list(self.bins), "limites": self.limites, "celdas": occ,
                "arch_x": self.arch_x[occ], "arch_f": self.arch_f[occ], "arch_d": self.arch_d[occ]}

    def _cargar_propio(self, d):
        self.arch_f[:] = -np.inf
        occ = np.array(d["celdas"], dtype=int)
        if len(occ):
            self.arch_x[occ], self.arch_f[occ], self.arch_d[occ] = \
                _arr(d["arch_x"]), _arr(d["arch_f"]), _arr(d["arch_d"])


OPTIMIZADORES = {c.nombre: c for c in (GA, GAV2, SepCMAES, ESAdam, PGPE, MAPElites)}


ALIAS = {"sepcma": "sep_cma", "sep-cma": "sep_cma", "cma": "sep_cma",
         "gav2": "ga_v2", "ga-v2": "ga_v2",
         "mapelites": "map_elites", "map-elites": "map_elites", "me": "map_elites"}


def crear(nombre, **kw):
    clave = str(nombre).lower().strip()
    clave = ALIAS.get(clave, clave)
    try:
        cls = OPTIMIZADORES[clave]
    except KeyError:
        raise ValueError(f"optimizador desconocido {nombre!r}; opciones: {sorted(OPTIMIZADORES)}")
    if "n" in kw:
        kw.setdefault("pop", kw.pop("n"))
    if "n_param" in kw:
        kw.setdefault("dim", kw.pop("n_param"))
    pob = kw.pop("pob", None)
    x0 = kw.get("x0")
    if x0 is not None and np.ndim(x0) == 2:
        kw["x0"] = np.asarray(x0, dtype=float)[0]
    if cls is GA:
        if pob is not None:
            kw.setdefault("poblacion_inicial", pob)
    elif pob is not None and kw.get("x0") is None:
        kw["x0"] = np.asarray(pob, dtype=float)[0]
    if kw.get("rng") is not None:
        kw.pop("semilla", None)
    return cls(**kw)


def desde_estado(d, rng=None, **kw):
    cls = OPTIMIZADORES[d["clase"]]
    if cls is GA:
        opt = GA(pop=d["pop"], capas=d["capas"], rng=rng or np.random.default_rng(),
                 poblacion_inicial=d["pob"], **kw)
    else:
        opt = cls(pop=d["pop"], capas=d["capas"], rng=rng or np.random.default_rng(),
                  x0=d["x0"], **kw)
    return opt.cargar_estado(d)
