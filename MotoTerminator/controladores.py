import numpy as np

import config as C

I_V, I_TH, I_OM = 0, 2, 3
I_DESVIO_PREV, I_FF_CURVA, I_PSI, I_VLAT = 11, 12, 13, 14
I_DESVIO = 10
I_EXCESO_SEGURA, I_EXCESO_ESTABLE = 27, 28


class ControladorPD:

    nombre = "PD"

    def __init__(self, k_lat=0.9, k_psi=1.2, k_vlat=0.4, margen_v=3.0, v_max=13.0,
                 k_v=0.35, k_th=2.0, k_om=0.6):
        self.k_lat, self.k_psi, self.k_vlat = k_lat, k_psi, k_vlat
        self.margen_v, self.v_max, self.k_v = margen_v, v_max, k_v
        self.k_th, self.k_om = k_th, k_om

    def __call__(self, obs, sim=None):
        obs = np.asarray(obs, dtype=float)
        v = obs[:, I_V] * 15.0
        v_segura = np.abs(v) - obs[:, I_EXCESO_SEGURA] * 10.0
        v_obj = np.clip(np.minimum(v_segura - self.margen_v, self.v_max),
                        C.V_ESTABLE + self.margen_v, None)
        acel = np.clip(self.k_v * (v_obj - v), -1.0, 1.0)
        cab = np.clip(-self.k_th * obs[:, I_TH] - self.k_om * obs[:, I_OM], -1.0, 1.0)
        direc = (obs[:, I_FF_CURVA]
                 - self.k_lat * obs[:, I_DESVIO]
                 - self.k_psi * obs[:, I_PSI] * 0.5
                 - self.k_vlat * obs[:, I_VLAT])
        return np.stack([acel, cab, np.clip(direc, -1.0, 1.0)], axis=1)


class ControladorAleatorio:

    nombre = "aleatorio"

    def __init__(self, semilla=0, sesgo_acel=0.3):
        self.rng = np.random.default_rng(semilla)
        self.sesgo_acel = sesgo_acel

    def __call__(self, obs, sim=None):
        n = len(obs)
        a = self.rng.uniform(-1.0, 1.0, (n, 3))
        a[:, 0] = np.clip(a[:, 0] + self.sesgo_acel, -1.0, 1.0)
        return a


class ControladorRed:

    nombre = "red"

    def __init__(self, pesos):
        import red as R
        self.red = R.desempacar(np.atleast_2d(pesos), C.CAPAS)

    def __call__(self, obs, sim=None):
        import red as R
        n = len(obs)
        red = [(W[:1].repeat(n, 0), b[:1].repeat(n, 0)) for W, b in self.red] \
            if self.red[0][0].shape[0] == 1 else self.red
        return R.adelante(red, obs)


CONTROLADORES = {"pd": ControladorPD, "aleatorio": ControladorAleatorio}


def crear(nombre, **kw):
    return CONTROLADORES[nombre](**kw)
