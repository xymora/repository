import numpy as np

import config as C

REQUISITOS = {
    "R1": ("Mantenerse a < 1 m del centro de su carril", "m", 1.0),
    "R2": ("Margen ≥ 0.3 m a la orilla del camino", "m", 1.7),
    "R3": ("Velocidad ≥ 30 km/h (tras 2 s)", "m/s", C.V_ESTABLE),
    "R4": ("No exceder la velocidad segura de la curva + 1 m/s", "m/s", 10.0),
    "R5": ("Toda invasión del carril contrario dura < 2 s", "m", 1.0),
    "R6": ("Inclinación lateral < 0.6 rad (34°)", "rad", 0.6),
    "R7": ("Reserva del giroscopio CMG: |saturación| < 0.9", "-", 0.9),
    "R8": ("Llegar a la meta", "m", 10.0),
    "R9": ("Cabeceo < 0.5 rad (29°)", "rad", 0.5),
}


def _todo_nan(a, axis=0):
    return np.all(np.isnan(a), axis=axis)


def siempre(rho):
    rho = np.asarray(rho, dtype=float)
    out = np.full(rho.shape[1:], np.inf)
    ok = ~_todo_nan(rho)
    out[ok] = np.nanmin(rho[:, ok], axis=0)
    return out


def eventualmente(rho):
    rho = np.asarray(rho, dtype=float)
    out = np.full(rho.shape[1:], -np.inf)
    ok = ~_todo_nan(rho)
    out[ok] = np.nanmax(rho[:, ok], axis=0)
    return out


def _ventana(rho, k, red):
    rho = np.asarray(rho, dtype=float)
    T = rho.shape[0]
    k = max(int(k), 0)
    relleno = np.full((k,) + rho.shape[1:], np.nan)
    ext = np.concatenate([rho, relleno], axis=0)
    from numpy.lib.stride_tricks import sliding_window_view
    vent = sliding_window_view(ext, k + 1, axis=0)[:T]
    with np.errstate(all="ignore"):
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            return red(vent, axis=-1)


def ventana_max(rho, k):
    return _ventana(rho, k, np.nanmax)


def ventana_min(rho, k):
    return _ventana(rho, k, np.nanmin)


def implica(rho_a, rho_b):
    return np.maximum(-np.asarray(rho_a), np.asarray(rho_b))


def _peor(rho, t, x):
    r = np.where(np.isnan(rho), np.inf, rho)
    i = np.argmin(r, axis=0)
    cols = np.arange(rho.shape[1])
    return t[i, cols], x[i, cols]


def evaluar_requisitos(traza, pista, dt=C.DT_CONTROL):
    lat, v, x = traza["lat"], traza["v"], traza["x"]
    t = traza["t"]
    if t.ndim == 1:
        t = np.repeat(t[:, None], lat.shape[1], 1)
    señales = {
        "R1": 1.0 - np.abs(lat - C.LAT_CARRIL),
        "R2": (C.ANCHO_CAMINO / 2 - 0.3) - np.abs(lat),
        "R3": np.where(t >= 2.0, v - C.V_ESTABLE, np.nan),
        "R4": traza["v_segura"] + 1.0 - v if "v_segura" in traza else None,
        "R5": ventana_max(-lat, int(round(2.0 / dt))),
        "R6": 0.6 - np.abs(traza["phi"]) if "phi" in traza else None,
        "R7": 0.9 - np.abs(traza["cmg_sat"]) if "cmg_sat" in traza else None,
        "R9": 0.5 - np.abs(traza["th"]) if "th" in traza else None,
    }
    señales["R5"] = np.where(np.isnan(lat), np.nan, implica(lat, señales["R5"]))
    out = {}
    for req, s in señales.items():
        if s is None:
            continue
        s = np.where(np.isnan(lat), np.nan, s)
        rho = siempre(s)
        tp, xp = _peor(s, t, x)
        out[req] = {"rho": rho, "t_peor": tp, "x_peor": xp,
                    "desc": REQUISITOS[req][0], "unidad": REQUISITOS[req][1]}
    s8 = x - pista.meta
    rho8 = eventualmente(s8)
    out["R8"] = {"rho": rho8, "t_peor": np.full(lat.shape[1], np.nan),
                 "x_peor": np.full(lat.shape[1], np.nan),
                 "desc": REQUISITOS["R8"][0], "unidad": REQUISITOS["R8"][1]}
    return dict(sorted(out.items()))


def robustez_normalizada(resultado, reqs=None):
    reqs = reqs or list(resultado)
    vals = [resultado[r]["rho"] / REQUISITOS[r][2] for r in reqs if r in resultado]
    return np.min(np.stack(vals), axis=0)


class MonitorSTL:

    REQS_G = ("R1", "R2", "R3", "R4", "R5", "R6", "R7", "R9")

    def __init__(self, n, al_violar=None, t_inicio_r3=2.0):
        self.n = int(n)
        self.rho = {r: np.full(self.n, np.inf) for r in self.REQS_G}
        self.rho["R8"] = np.full(self.n, -np.inf)
        self.t_invasion = np.zeros(self.n)
        self.eventos = []
        self._violado = {r: np.zeros(self.n, bool) for r in self.rho}
        self.al_violar, self.t_inicio_r3 = al_violar, t_inicio_r3
        self._t_ult = None

    def actualizar(self, sim):
        if self._t_ult is not None and sim.t == self._t_ult:
            return
        self._t_ult = sim.t
        ids = getattr(sim, "ids", np.arange(self.n))
        if len(ids) == 0:
            return
        p = sim.pista
        v = sim.vx * np.cos(sim.th) + sim.vy * np.sin(sim.th)
        i = p.indice(sim.px)
        a_pos = np.minimum(C.A_LAT_MAX, 0.85 * p.mu_min[i] * C.G)
        vseg = np.minimum(np.sqrt(a_pos / np.maximum(p.kmax[i], 1e-3)), 30.0)
        invade = sim.lat > 0
        self.t_invasion[ids] = np.where(invade, self.t_invasion[ids] + C.DT_CONTROL, 0.0)
        val = {
            "R1": 1.0 - np.abs(sim.lat - C.LAT_CARRIL),
            "R2": (C.ANCHO_CAMINO / 2 - 0.3) - np.abs(sim.lat),
            "R3": (v - C.V_ESTABLE) if sim.t >= self.t_inicio_r3 else None,
            "R4": vseg + 1.0 - v,
            "R5": 2.0 - self.t_invasion[ids],
            "R6": 0.6 - np.abs(sim.phi),
            "R7": 0.9 - np.abs(sim.cmg_sat),
            "R9": 0.5 - np.abs(sim.th),
        }
        for r, x in val.items():
            if x is None:
                continue
            self.rho[r][ids] = np.minimum(self.rho[r][ids], x)
            nuevo = (x < 0) & ~self._violado[r][ids]
            if nuevo.any():
                k = ids[nuevo]
                self._violado[r][k] = True
                for j, xv in zip(k, x[nuevo]):
                    self.eventos.append((float(sim.t), int(j), r, float(xv)))
                if self.al_violar is not None:
                    self.al_violar(r, k, float(sim.t), x[nuevo])
        self.rho["R8"][ids] = np.maximum(self.rho["R8"][ids], sim.px - p.meta)

    def como_filtro(self, filtro=None):
        def _f(obs, sim):
            self.actualizar(sim)
            return filtro(obs, sim) if filtro is not None else obs
        return _f

    def violado(self):
        out = {r: self.rho[r] < 0 for r in self.REQS_G}
        out["R8"] = self.rho["R8"] < 0
        return out

    @staticmethod
    def predecir(estado, horizonte=0.6):
        H = float(horizonte)
        lat_h = estado["lat"] + estado["vlat"] * H + 0.5 * estado.get("alat", 0.0) * H * H
        borde = C.ANCHO_CAMINO / 2 - 0.3
        out = {
            "R2": np.minimum(borde - np.abs(estado["lat"]), borde - np.abs(lat_h)),
            "R3": np.minimum(estado["v"], estado["v"] + estado["a_v"] * H) - C.V_ESTABLE,
            "R6": 0.6 - np.maximum(np.abs(estado["phi"]), np.abs(estado["phi"] + estado["phid"] * H)),
            "R9": 0.5 - np.maximum(np.abs(estado["th"]), np.abs(estado["th"] + estado["om"] * H)),
        }
        return out
