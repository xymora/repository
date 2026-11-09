import copy
import math
from dataclasses import dataclass, asdict, fields

import numpy as np

import config as C

RHO_AIRE = 1.2
CDA_LATERAL = 1.0 * 0.9
H_PRESION = 0.8
_MASA = C.MASA_CHASIS + 2 * C.MASA_RUEDA
INERCIA_ALABEO = _MASA * C.ALTURA_CG ** 2 + 30.0
TAU_TURBULENCIA = 2.0
MU_AQUA_MIN = 0.15
V_SEGURA_FACTIBLE = C.V_ESTABLE

_MOJADO = {
    "asfalto": (0.65, 0.002, 0.00),
    "tierra":  (0.56, 0.070, 0.05),
    "pasto":   (0.65, 0.020, 0.00),
    "grava":   (0.85, 0.005, 0.00),
    "arena":   (1.10, -0.050, 0.00),
    "lodo":    (0.78, 0.040, 0.03),
    "roca":    (0.65, 0.000, 0.00),
    "nieve":   (0.80, 0.020, 0.00),
    "hielo":   (0.67, 0.000, 0.00),
}

PRESETS = {
    "despejado":            dict(),
    "llovizna":             dict(lluvia=0.3, niebla=0.1, viento_medio=2.0, direccion_viento=1.0,
                                 rafagas=0.1),
    "lluvia":               dict(lluvia=0.7, charcos=0.35, niebla=0.15, viento_medio=4.0,
                                 direccion_viento=2.0, rafagas=0.25),
    "tormenta":             dict(lluvia=1.0, charcos=0.7, niebla=0.3, viento_medio=8.0,
                                 direccion_viento=2.2, rafagas=0.5),
    "granizo":              dict(lluvia=0.5, granizo=True, charcos=0.2, niebla=0.2,
                                 viento_medio=6.0, direccion_viento=-1.8, rafagas=0.4),
    "niebla":               dict(niebla=0.85, lluvia=0.05, viento_medio=1.0),
    "viento_cruzado":       dict(viento_medio=10.0, direccion_viento=math.pi / 2, rafagas=0.2),
    "rafagas":              dict(viento_medio=6.0, direccion_viento=-math.pi / 3, rafagas=0.85),
    "tormenta_con_rafagas": dict(lluvia=1.0, charcos=0.8, niebla=0.35, viento_medio=11.0,
                                 direccion_viento=1.9, rafagas=0.9),
}
NOMBRES = tuple(PRESETS)
_ETIQUETAS = {"despejado": "Despejado", "llovizna": "Llovizna", "lluvia": "Lluvia",
              "tormenta": "Tormenta", "granizo": "Granizo", "niebla": "Niebla",
              "viento_cruzado": "Viento cruzado", "rafagas": "Ráfagas",
              "tormenta_con_rafagas": "Tormenta con ráfagas"}


@dataclass
class Clima:
    nombre: str = "despejado"
    lluvia: float = 0.0
    granizo: bool = False
    niebla: float = 0.0
    viento_medio: float = 0.0
    direccion_viento: float = 0.0
    rafagas: float = 0.0
    charcos: float = 0.0
    semilla: int = 0

    @property
    def despejado(self):
        return (self.lluvia <= 0 and not self.granizo and self.niebla <= 0
                and self.viento_medio <= 0 and self.rafagas <= 0 and self.charcos <= 0)

    @property
    def hay_viento(self):
        return self.viento_medio > 0 or self.rafagas > 0

    def descripcion(self):
        base = _ETIQUETAS.get(self.nombre, self.nombre.replace("_", " ").capitalize())
        partes = []
        if self.lluvia > 0:
            partes.append(f"lluvia {self.lluvia:.0%}")
        if self.charcos > 0:
            partes.append(f"charcos {self.charcos:.0%}")
        if self.granizo:
            partes.append("granizo")
        if self.niebla > 0:
            partes.append(f"niebla {self.niebla:.0%}")
        if self.hay_viento:
            partes.append(f"viento {self.viento_medio * 3.6:.0f} km/h"
                          + (f" con ráfagas {self.rafagas:.0%}" if self.rafagas > 0 else ""))
        return base + (" · " + ", ".join(partes) if partes else "")

    def a_dict(self):
        d = asdict(self)
        d["granizo"] = bool(d["granizo"])
        return d

    @classmethod
    def de_dict(cls, d):
        validos = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in dict(d).items() if k in validos})


def crear(nombre_o_clima, semilla=0):
    if nombre_o_clima is None:
        return None
    if isinstance(nombre_o_clima, Clima):
        c = copy.copy(nombre_o_clima)
        if semilla is not None and semilla != 0:
            c.semilla = int(semilla)
        return c
    if isinstance(nombre_o_clima, dict):
        d = dict(nombre_o_clima)
        d.setdefault("semilla", int(semilla or 0))
        return Clima.de_dict(d)
    nombre = str(nombre_o_clima).strip().lower().replace(" ", "_")
    if nombre not in PRESETS:
        raise ValueError(f"Clima desconocido: {nombre_o_clima!r}. Opciones: {', '.join(NOMBRES)}")
    return Clima(nombre=nombre, semilla=int(semilla or 0), **PRESETS[nombre])


_SORTEO = (("llovizna", 0.17), ("lluvia", 0.15), ("niebla", 0.12), ("viento_cruzado", 0.12),
           ("rafagas", 0.12), ("tormenta", 0.12), ("granizo", 0.08), ("tormenta_con_rafagas", 0.12))
P_DESPEJADO = 0.30


def intensidad_para(nivel, etapa=0):
    return float(np.clip(0.45 + 0.55 * (int(nivel) - 1) / 7.0 + 0.1 * int(etapa), 0.3, 1.0))


def clima_aleatorio(rng, nivel, etapa=0):
    u_desp, u_preset, u_int, u_dir, u_sem = (float(x) for x in rng.random(5))
    semilla = int(u_sem * 2 ** 31)
    if u_desp < P_DESPEJADO:
        return Clima(nombre="despejado", semilla=semilla)
    s = intensidad_para(nivel, etapa)
    fuertes = {"tormenta", "granizo", "tormenta_con_rafagas"}
    pesos = np.array([p * (0.5 + s if n in fuertes else 1.0) for n, p in _SORTEO])
    pesos /= pesos.sum()
    k = int(np.searchsorted(np.cumsum(pesos), u_preset, side="right"))
    nombre = _SORTEO[min(k, len(_SORTEO) - 1)][0]
    escala = s * (0.7 + 0.3 * u_int)
    c = crear(nombre, semilla)
    c.lluvia *= escala
    c.niebla *= escala
    c.charcos *= escala
    c.viento_medio *= escala
    c.rafagas *= escala
    c.direccion_viento = (c.direccion_viento + (u_dir - 0.5) * math.pi) if c.hay_viento else 0.0
    return c


def _maximo_adelante(valores, n):
    import terreno
    return terreno.maximo_adelante(valores, n)


def es_calle(pista):
    return hasattr(pista, "zona") or hasattr(pista, "red")


def preparar_pista(pista, clima):
    clima = crear(clima) if not isinstance(clima, Clima) and clima is not None else clima
    p = copy.copy(pista)
    p.pista_seca = getattr(pista, "pista_seca", pista)
    p.clima = clima
    n = len(pista.mu)
    if clima is None or (clima.lluvia <= 0 and not clima.granizo and clima.charcos <= 0):
        p.charco = np.zeros(n)
        return p
    import terreno as T
    mat = np.asarray(pista.mat, dtype=np.int64)
    mu0 = np.asarray(pista.mu, dtype=float)
    lluvia = float(np.clip(max(clima.lluvia, 0.6 * clima.charcos, 0.3 if clima.granizo else 0.0),
                           0.0, 1.0))
    f_mu = np.ones(len(T.NOMBRES_MAT))
    d_rr = np.zeros(len(T.NOMBRES_MAT))
    d_rugo = np.zeros(len(T.NOMBRES_MAT))
    for nombre, (fm, drr, drg) in _MOJADO.items():
        k = T.M[nombre]
        f_mu[k] = 1.0 + (fm - 1.0) * lluvia
        d_rr[k] = drr * lluvia
        d_rugo[k] = drg * lluvia
    mu = mu0 * f_mu[mat]
    rr = np.maximum(np.asarray(pista.rr, dtype=float) + d_rr[mat], 0.005)
    rugo = np.asarray(pista.rugo, dtype=float) + d_rugo[mat]
    if clima.granizo:
        mu = mu * 0.75
        rugo = rugo + 0.12
        rr = rr + 0.01
    charco = np.zeros(n)
    if clima.charcos > 0:
        sp = int(getattr(pista, "semilla", 0) or 0) & 0xFFFFFFFF
        rng = np.random.default_rng([int(clima.semilla) & 0xFFFFFFFF, 2, sp])
        dx = float(pista.xs[1] - pista.xs[0]) if n > 1 else 0.1
        firmes = np.isin(mat, [T.M[m] for m in ("asfalto", "tierra", "grava", "roca", "pasto")])
        x = float(rng.uniform(10.0, 30.0))
        sep = 60.0 / (0.25 + clima.charcos)
        while x < pista.xs[-1] - 10:
            largo = float(rng.uniform(1.5, 7.0))
            prof = float(rng.uniform(2.0, 2.0 + 6.0 * clima.charcos))
            a, b = int(x / dx), int((x + largo) / dx)
            seg = slice(a, min(b, n))
            charco[seg] = np.where(firmes[seg], prof, 0.0)
            x += largo + float(rng.exponential(sep))
        mu = np.where(charco > 0, mu * 0.9, mu)
        rr = rr + 0.004 * charco
    kappa = np.abs(np.asarray(pista.kappa, dtype=float))
    mu_curva = kappa * V_SEGURA_FACTIBLE ** 2 / (0.85 * C.G) * 1.05
    hs = getattr(pista, "hs", None)
    if hs is not None and len(hs) == n and n > 31:
        n3 = 30
        pend = np.zeros(n)
        pend[:-n3] = np.abs(hs[n3:] - hs[:-n3]) / (n3 * (pista.xs[1] - pista.xs[0]))
        pend = _maximo_adelante(pend, n3)
        mu_pend = 2.0 * pend * 1.05
    else:
        mu_pend = 0.0
    piso = np.minimum(np.maximum(mu_curva, mu_pend), mu0)
    mu = np.maximum(mu, piso)
    p.mu = mu
    p.rr = rr
    p.rugo = rugo
    p.charco = charco
    dx = float(pista.xs[1] - pista.xs[0]) if n > 1 else 0.1
    p.mu_min = -_maximo_adelante(-mu, int(C.VENTANA_CURVAS / dx))
    return p


def factor_aquaplaning(v, prof_mm):
    v_kmh = np.abs(v) * 3.6
    v_ini = 85.0 - 3.0 * prof_mm
    s = np.clip((v_kmh - v_ini) / 25.0, 0.0, 1.0)
    s = s * s * (3.0 - 2.0 * s)
    return np.where(prof_mm > 0, 1.0 - (1.0 - MU_AQUA_MIN) * s, 1.0)


class ProcesoViento:

    def __init__(self, clima, dt=C.DT_CONTROL):
        self.clima = clima
        self.dt = float(dt)
        self.rng = np.random.default_rng([int(clima.semilla) & 0xFFFFFFFF, 0])
        W, r = float(clima.viento_medio), float(clima.rafagas)
        self.sigma_u = r * (0.2 * W + 1.0)
        self.sigma_v = 0.8 * self.sigma_u
        self.amp_max = r * (0.6 * W + 4.0)
        self.tasa = 0.12 * r
        self.a = math.exp(-self.dt / TAU_TURBULENCIA)
        self.b = math.sqrt(1.0 - self.a ** 2)
        self.k = 0
        self.u = self.sigma_u * float(self.rng.normal())
        self.v = self.sigma_v * float(self.rng.normal())
        self.rafaga = None
        self.valor = self._vector(0.0)

    def _vector(self, t):
        c = self.clima
        g = 0.0
        if self.rafaga is not None:
            t0, d, A = self.rafaga
            if t - t0 < d:
                g = 0.5 * A * (1.0 - math.cos(2 * math.pi * (t - t0) / d))
            else:
                self.rafaga = None
        U = c.viento_medio + self.u + g
        th = c.direccion_viento
        return (U * math.cos(th) - self.v * math.sin(th), U * math.sin(th) + self.v * math.cos(th))

    def en(self, t):
        k = int(round(t / self.dt))
        while self.k < k:
            self.k += 1
            z = self.rng.normal(size=2)
            self.u = self.a * self.u + self.sigma_u * self.b * float(z[0])
            self.v = self.a * self.v + self.sigma_v * self.b * float(z[1])
            ur = self.rng.random(3)
            if self.rafaga is None and ur[0] < self.tasa * self.dt:
                self.rafaga = (self.k * self.dt, 1.0 + 2.0 * float(ur[1]),
                               self.amp_max * (0.5 + 0.5 * float(ur[2])))
            self.valor = self._vector(self.k * self.dt)
        return self.valor


def viento_en_marco_camino(pista, wvec, px, absoluto):
    wx, wy = wvec
    if absoluto:
        r = pista.rumbo[pista.indice(px)]
        cr, sr = np.cos(r), np.sin(r)
        return wx * cr + wy * sr, -wx * sr + wy * cr
    n = np.shape(px)
    return np.full(n, wx), np.full(n, wy)


def ruido_observacion(clima):
    sig = np.zeros(C.N_ENTRADAS)
    fac = np.ones(C.N_ENTRADAS)
    nb, ll = float(clima.niebla), float(clima.lluvia)
    gr = 1.0 if clima.granizo else 0.0
    sig[24] = 0.05 * nb + 0.02 * ll
    sig[25] = 0.20 * nb + 0.04 * ll
    sig[26] = 0.45 * nb + 0.08 * ll
    fac[26] = 1.0 - 0.4 * nb
    fac[25] = 1.0 - 0.15 * nb
    sig[12] = 0.03 * nb
    sig[21] = 0.04 * ll + 0.05 * gr
    sig[22] = 0.08 * ll + 0.06 * nb + 0.08 * gr
    sig[23] = 0.02 * ll
    n_l = len(C.DIST_LIDAR)
    lejos = np.linspace(0.5, 1.0, n_l)
    sig[29:29 + n_l] = (0.03 * ll + 0.06 * gr + 0.08 * nb * lejos) / 2
    sig[9] = 0.02 * ll + 0.03 * nb
    sig[10] = 0.04 * ll + 0.06 * nb
    return sig, fac


class EfectosClima:

    def __init__(self, clima, pista, n_total, ruido_por_moto):
        self.clima = clima
        self.absoluto = es_calle(pista)
        self.viento = ProcesoViento(clima) if clima.hay_viento else None
        self.sig, self.fac = ruido_observacion(clima)
        self.canales = np.flatnonzero((self.sig > 0) | (self.fac != 1.0))
        self.rng_obs = np.random.default_rng([int(clima.semilla) & 0xFFFFFFFF, 1])
        self.n_total = n_total
        self.ruido_por_moto = ruido_por_moto
        self.charcos = bool(np.any(getattr(pista, "charco", 0) > 0))
        self.wvec = (0.0, 0.0)

    def degradar(self, obs, ids):
        if len(self.canales) == 0:
            return obs
        k = self.canales
        if self.ruido_por_moto:
            z = self.rng_obs.normal(size=(self.n_total, len(k)))[ids]
        else:
            z = self.rng_obs.normal(size=(1, len(k)))
        obs = obs.copy()
        obs[:, k] = obs[:, k] * self.fac[k] + z * self.sig[k]
        return obs

    def fuerzas(self, sim):
        if self.viento is None:
            self.wvec = (0.0, 0.0)
            return None
        self.wvec = self.viento.en(sim.t)
        w_par, w_perp = viento_en_marco_camino(sim.pista, self.wvec, sim.px, self.absoluto)
        v = sim.vx * np.cos(sim.th) + sim.vy * np.sin(sim.th)
        v_rel_lat = w_perp - v * np.sin(sim.psi)
        f_lat = 0.5 * RHO_AIRE * CDA_LATERAL * v_rel_lat * np.abs(v_rel_lat)
        a_lat = f_lat / _MASA
        alabeo = f_lat * H_PRESION / INERCIA_ALABEO
        return a_lat, alabeo, w_par

    def viento_actual(self):
        wx, wy = self.wvec
        return float(math.hypot(wx, wy)), float(math.atan2(wy, wx))
