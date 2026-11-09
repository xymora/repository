import numpy as np

import config as C
import red as R
from stl import MonitorSTL

L = C.DISTANCIA_EJES
A_GAS, A_FRENO = 4.0, 8.0


def tope_direccion(v):
    return np.minimum(C.DIR_MAX, np.arctan(C.A_LAT_MAX * L / np.maximum(v * v, 1e-3)))


class _RedPesos:
    def __init__(self, pesos):
        self.red = R.desempacar(np.atleast_2d(np.asarray(pesos, dtype=float)), C.CAPAS)
        self.uno = self.red[0][0].shape[0] == 1

    def _v_cresta(self, obs):
        y = obs[:, 29:29 + len(C.DIST_LIDAR)] * 2.0
        d = np.asarray(C.DIST_LIDAR, dtype=float)
        A = np.stack([d * d, d], axis=1)
        coef = np.linalg.lstsq(A, y.T, rcond=None)[0]
        curv = -2.0 * coef[0]
        return np.where(curv > 1e-3, np.sqrt(C.G / np.maximum(curv, 1e-3)) * self.f_cresta, np.inf)

    def __call__(self, obs, sim):
        n = len(obs)
        if self.uno:
            red = [(W.repeat(n, 0), b.repeat(n, 0)) for W, b in self.red]
        else:
            ids = getattr(sim, "ids", np.arange(n))
            red = [(W[ids], b[ids]) for W, b in self.red]
        return R.adelante(red, obs)


class _PDPropio:

    def __call__(self, obs, sim=None):
        v = obs[:, 0] * 15.0
        v_seg = np.abs(v) - obs[:, 27] * 10.0
        v_obj = np.clip(np.minimum(v_seg - 2.0, 12.0), C.V_ESTABLE + 2.0, None)
        acel = np.clip(0.35 * (v_obj - v), -0.6, 1.0)
        cab = np.clip(-2.0 * obs[:, 2] - 0.6 * obs[:, 3], -1, 1)
        direc = obs[:, 12] - 0.9 * obs[:, 10] - 0.6 * obs[:, 13] - 0.4 * obs[:, 14]
        return np.stack([acel, cab, np.clip(direc, -1, 1)], axis=1)


def _respaldo_defecto():
    try:
        from controladores import ControladorPD
        return ControladorPD()
    except Exception:
        return _PDPropio()


class Escudo:
    nombre = "escudo"

    def __init__(self, nominal, respaldo=None, horizonte=0.6, t_min_respaldo=0.5, usar_simplex=True,
                 usar_cbf=True, k0=4.0, k1=4.0, alfa_v=1.5, margen_borde=0.4, b_hi=0.3,
                 margen_v_segura=1.0, margen_v_min=0.5, freno_max=0.6, th_max=0.35, umbral_cbf=0.05,
                 k_deficit=2.0, usar_cresta=True, f_cresta=1.0):
        self.k_deficit, self.usar_cresta, self.f_cresta = k_deficit, usar_cresta, f_cresta
        self.nominal = nominal if callable(nominal) else _RedPesos(nominal)
        self.respaldo = respaldo if respaldo is not None else _respaldo_defecto()
        self.horizonte, self.t_min = float(horizonte), float(t_min_respaldo)
        self.usar_simplex, self.usar_cbf = usar_simplex, usar_cbf
        self.k0, self.k1, self.alfa_v = k0, k1, alfa_v
        self.b_lo = -(C.ANCHO_CAMINO / 2 - margen_borde)
        self.b_hi = min(b_hi, C.ANCHO_CAMINO / 2 - margen_borde)
        self.margen_vs, self.margen_vm = margen_v_segura, margen_v_min
        self.freno_max, self.th_max, self.umbral = freno_max, th_max, umbral_cbf
        self.n = None

    def _preparar(self, n):
        self.n = n
        z = lambda: np.zeros(n)
        self.en_respaldo = np.zeros(n, bool)
        self.t_respaldo = z()
        self.cbf_previo = np.zeros(n, bool)
        self.v_prev = np.full(n, np.nan)
        self.vlat_prev = np.full(n, np.nan)
        self.conmutaciones, self.activaciones_cbf = z(), z()
        self.pasos_respaldo, self.pasos_cbf, self.pasos = z(), z(), z()

    def _estado(self, obs, ids):
        v = obs[:, 0] * 15.0
        vlat = obs[:, 14] * 3.0
        dt = C.DT_CONTROL
        a_v = np.where(np.isnan(self.v_prev[ids]), 0.0, (v - self.v_prev[ids]) / dt)
        alat = np.where(np.isnan(self.vlat_prev[ids]), 0.0, (vlat - self.vlat_prev[ids]) / dt)
        self.v_prev[ids], self.vlat_prev[ids] = v, vlat
        return {"lat": obs[:, 9] * (C.ANCHO_CAMINO / 2), "vlat": vlat, "alat": np.clip(alat, -10, 10),
                "v": v, "a_v": np.clip(a_v, -15, 15), "phi": obs[:, 4] * 0.5, "phid": obs[:, 5] * 2.0,
                "th": obs[:, 2] * 1.2, "om": obs[:, 3] * 4.0, "psi": obs[:, 13] * 0.5}

    def _cbf(self, u, obs, e):
        u = u.copy()
        v = np.maximum(np.abs(e["v"]), 1.0)
        tope = tope_direccion(v)
        kappa = np.tan(obs[:, 12] * tope) / L
        den = v * v * np.maximum(np.cos(e["psi"]), 0.2)
        h_hi = self.b_hi - e["lat"]
        h_lo = e["lat"] - self.b_lo
        t_hi = L * (kappa + (self.k0 * h_hi - self.k1 * e["vlat"]) / den)
        t_lo = L * (kappa - (self.k0 * h_lo + self.k1 * e["vlat"]) / den)
        cruzan = t_lo > t_hi
        urg_hi = h_hi < h_lo
        t_hi = np.where(cruzan & ~urg_hi, np.inf, t_hi)
        t_lo = np.where(cruzan & urg_hi, -np.inf, t_lo)
        u_hi = np.arctan(t_hi) / tope
        u_lo = np.arctan(t_lo) / tope
        u[:, 2] = np.clip(u[:, 2], u_lo, u_hi)
        deficit = np.maximum(np.maximum(u_lo - 1.0, -1.0 - u_hi), 0.0)
        v_seg = np.abs(e["v"]) - obs[:, 27] * 10.0
        if self.usar_cresta:
            v_seg = np.minimum(v_seg, self._v_cresta(obs))
        h_vs = v_seg + self.margen_vs - e["v"]
        h_vm = e["v"] - (C.V_ESTABLE + self.margen_vm)
        a_hi = self.alfa_v * h_vs
        a_lo = -self.alfa_v * h_vm
        sup = np.where(a_hi >= 0, a_hi / A_GAS, a_hi / A_FRENO)
        inf = np.where(a_lo >= 0, a_lo / A_GAS, a_lo / A_FRENO)
        inf = np.minimum(inf, sup)
        sup = np.where(deficit > 0, np.minimum(sup, -np.minimum(self.k_deficit * deficit, self.freno_max)), sup)
        u[:, 0] = np.clip(u[:, 0], np.minimum(inf, sup), sup)
        u[:, 0] = np.maximum(u[:, 0], inf)
        u[:, 0] = np.maximum(u[:, 0], -self.freno_max)
        malo = np.abs(e["th"]) > self.th_max
        u[:, 1] = np.where(malo, np.clip(-2.0 * obs[:, 2] - 0.6 * obs[:, 3], -1, 1), u[:, 1])
        return np.clip(u, -1.0, 1.0)

    def _v_cresta(self, obs):
        y = obs[:, 29:29 + len(C.DIST_LIDAR)] * 2.0
        d = np.asarray(C.DIST_LIDAR, dtype=float)
        A = np.stack([d * d, d], axis=1)
        coef = np.linalg.lstsq(A, y.T, rcond=None)[0]
        curv = -2.0 * coef[0]
        return np.where(curv > 1e-3, np.sqrt(C.G / np.maximum(curv, 1e-3)) * self.f_cresta, np.inf)

    def __call__(self, obs, sim):
        obs = np.asarray(obs, dtype=float)
        n_total = int(getattr(sim, "n_total", len(obs)))
        if self.n is None:
            self._preparar(n_total)
        ids = getattr(sim, "ids", np.arange(len(obs)))
        e = self._estado(obs, ids)
        u = np.asarray(self.nominal(obs, sim), dtype=float)
        self.pasos[ids] += 1
        if self.usar_simplex:
            pred = MonitorSTL.predecir(e, self.horizonte)
            peligro = np.zeros(len(ids), bool)
            margen = np.zeros(len(ids), bool) | True
            for r, esc in (("R2", 1.0), ("R3", C.V_ESTABLE), ("R6", 0.6), ("R9", 0.5)):
                peligro |= pred[r] < 0
                margen &= pred[r] / esc > 0.1
            antes = self.en_respaldo[ids].copy()
            self.t_respaldo[ids] = np.where(antes, self.t_respaldo[ids] + C.DT_CONTROL, 0.0)
            sale = antes & margen & (self.t_respaldo[ids] >= self.t_min)
            ahora = (antes & ~sale) | peligro
            self.conmutaciones[ids] += (ahora & ~antes)
            self.en_respaldo[ids] = ahora
            if ahora.any():
                ur = np.asarray(self.respaldo(obs, sim), dtype=float)
                u = np.where(ahora[:, None], ur, u)
            self.pasos_respaldo[ids] += ahora
        if self.usar_cbf:
            uf = self._cbf(u, obs, e)
            activo = np.max(np.abs(uf - u), axis=1) > self.umbral
            self.activaciones_cbf[ids] += activo & ~self.cbf_previo[ids]
            self.cbf_previo[ids] = activo
            self.pasos_cbf[ids] += activo
            u = uf
        return u

    def intervenciones(self):
        if self.n is None:
            return np.zeros(0)
        return self.conmutaciones + self.activaciones_cbf

    def resumen(self):
        if self.n is None:
            return {}
        p = np.maximum(self.pasos, 1)
        return {"conmutaciones": self.conmutaciones.copy(), "activaciones_cbf": self.activaciones_cbf.copy(),
                "intervenciones": self.intervenciones(), "frac_respaldo": self.pasos_respaldo / p,
                "frac_cbf": self.pasos_cbf / p}


def crear_escudo(nominal, config=True):
    if isinstance(config, dict):
        return Escudo(nominal, **config)
    return Escudo(nominal)
