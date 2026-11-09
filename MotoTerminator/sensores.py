from collections import deque

import numpy as np

import config as C

N_OBS = C.N_ENTRADAS

SIGMA = np.zeros(N_OBS)
SIGMA[0] = 0.2 / 15
SIGMA[1] = 0.2 / 8
SIGMA[2] = np.radians(0.5) / 1.2
SIGMA[3] = 0.05 / 4
SIGMA[4] = np.radians(1.0) / 0.5
SIGMA[5] = 0.05 / 2
SIGMA[6] = 0.02
SIGMA[7] = 0.02
SIGMA[8] = 0.01
SIGMA[9] = 0.3 / 2
SIGMA[10] = 0.3
SIGMA[11] = 0.3 / 1.5
SIGMA[12] = 0.05
SIGMA[13] = np.radians(1.0) / 0.5
SIGMA[14] = 0.1 / 3
SIGMA[17:19] = 0.02
SIGMA[19:21] = 0.02
SIGMA[21:23] = 0.05
SIGMA[23] = 0.01
SIGMA[24:27] = 0.002 * 10
SIGMA[27] = 0.02
SIGMA[28] = 0.2 / 5
SIGMA[29:29 + len(C.DIST_LIDAR)] = 0.03 / 2

PERFILES = {
    "ideal": dict(escala_ruido=0.0, sesgo=0.0, latencia=0, mu_factor=1.0, mu_aleatorio=0.0, dropout=0.0),
    "realista": dict(escala_ruido=1.0, sesgo=1.0, latencia=2, mu_factor=1.0, mu_aleatorio=0.3, dropout=0.02),
}


def crear_filtro(perfil="realista", semilla=0, **ajustes):
    if perfil in (None, "ideal") and not ajustes:
        return None
    base = dict(PERFILES.get(perfil or "ideal", PERFILES["ideal"]))
    base.update(ajustes)
    return FiltroSensores(semilla=semilla, **base)


class RafagaLateral:

    def __init__(self, magnitud, t0, duracion=0.5):
        self.A = np.asarray(magnitud, dtype=float)
        self.t0 = np.asarray(t0, dtype=float)
        self.dur = float(duracion)

    def __call__(self, sim):
        if not hasattr(sim, "wobd"):
            return
        ids = getattr(sim, "ids", np.arange(len(self.A)))
        activa = (sim.t >= self.t0[ids]) & (sim.t < self.t0[ids] + self.dur)
        if activa.any():
            sim.wobd = sim.wobd + activa * self.A[ids] * C.DT_CONTROL
            if hasattr(sim, "psi"):
                sim.psi = sim.psi + activa * self.A[ids] * 0.05 * C.DT_CONTROL


class FiltroSensores:
    def __init__(self, escala_ruido=0.0, sesgo=0.0, latencia=0, mu_factor=1.0, mu_aleatorio=0.0,
                 dropout=0.0, semilla=0, sesgo_lat_m=None, sesgo_psi_rad=None, mu_por_moto=None,
                 perturbador=None):
        self.escala_ruido, self.sesgo, self.latencia = float(escala_ruido), float(sesgo), int(latencia)
        self.mu_factor, self.mu_aleatorio, self.dropout = float(mu_factor), float(mu_aleatorio), float(dropout)
        self.rng = np.random.default_rng(semilla)
        self._sesgo_lat, self._sesgo_psi, self._mu = sesgo_lat_m, sesgo_psi_rad, mu_por_moto
        self.perturbador = perturbador
        self._listo = False
        self._buf = deque(maxlen=self.latencia + 1)

    def _preparar(self, n):
        r = self.rng
        self.n = n
        self.b_lat = (np.asarray(self._sesgo_lat, float) if self._sesgo_lat is not None
                      else self.sesgo * r.normal(0, 0.3, n))
        self.b_psi = (np.asarray(self._sesgo_psi, float) if self._sesgo_psi is not None
                      else self.sesgo * r.normal(0, np.radians(0.5), n))
        self.b_phi = self.sesgo * r.normal(0, np.radians(0.5), n)
        if self._mu is not None:
            self.f_mu = np.asarray(self._mu, float)
        else:
            self.f_mu = self.mu_factor * (1 + self.mu_aleatorio * r.uniform(-1, 1, n))
        self._listo = True

    def __call__(self, obs, sim):
        ids = getattr(sim, "ids", np.arange(obs.shape[0]))
        if not self._listo:
            self._preparar(int(getattr(sim, "n_total", obs.shape[0])))
        if self.perturbador is not None:
            self.perturbador(sim)
        o = np.array(obs, dtype=float, copy=True)
        f = self.f_mu[ids]
        if np.any(f != 1.0):
            o[:, 21] *= f
            o[:, 22] *= f
            p = sim.pista
            i = p.indice(sim.px)
            av = np.abs(obs[:, 0]) * 15.0
            a_pos = np.minimum(C.A_LAT_MAX, 0.85 * f * p.mu_min[i] * C.G)
            vs = np.minimum(np.sqrt(a_pos / np.maximum(p.kmax[i], 1e-3)), 30.0)
            o[:, 27] = np.clip((av - vs) / 10.0, -1.5, 1.5)
        b = self.b_lat[ids]
        o[:, 9] += b / 2
        o[:, 10] += b
        o[:, 11] += b / 1.5
        o[:, 13] += self.b_psi[ids] / 0.5
        o[:, 4] += self.b_phi[ids] / 0.5
        if self.escala_ruido > 0:
            o += self.escala_ruido * SIGMA * self.rng.normal(size=o.shape)
        if self.dropout > 0:
            L = slice(29, 29 + len(C.DIST_LIDAR))
            perdidas = self.rng.random((o.shape[0], len(C.DIST_LIDAR))) < self.dropout
            o[:, L] = np.where(perdidas, 0.0, o[:, L])
        if self.latencia > 0:
            full = np.zeros((self.n, o.shape[1]))
            if self._buf:
                full[:] = self._buf[-1]
            full[ids] = o
            self._buf.append(full)
            o = self._buf[0][ids]
        return o


EJES_DEFECTO = {
    "escala_ruido": [0.0, 1.0, 2.0, 4.0],
    "latencia": [0, 1, 2, 3],
    "mu_factor": [0.7, 0.85, 1.0, 1.15, 1.3],
    "sesgo": [0.0, 1.0, 2.0],
}


def barrido_fragilidad(pesos, nivel=1, pistas=10, ruidos=3, ejes=None, modo="terreno", conf=0.95,
                       verbose=True, red_vial=None, guardar=True, dir_resultados=None):
    import evaluacion as E
    ejes = ejes or EJES_DEFECTO
    out = {}
    for eje, valores in ejes.items():
        filas = []
        for val in valores:
            ajustes = dict(PERFILES["ideal"])
            ajustes[eje] = val

            def fabrica(semilla, aj=ajustes):
                return FiltroSensores(semilla=semilla, **aj)

            r = E.evaluar(pesos, modo, (nivel,), pistas, ruidos, sensores=fabrica, con_reintentos=False,
                          registrar=False, guardar=False, verbose=False, red_vial=red_vial, conf=conf)
            s = r["niveles"][nivel]
            ll = s["llegada_limpia"]
            filas.append({"valor": val, "tasa": ll["tasa"], "ic": ll["ic"], "n": s["n_episodios"],
                          "fallas_por_km": s["fallas_por_km"]["tasa"]})
            if verbose:
                print(f"  fragilidad {eje}={val}: llegada limpia {100 * ll['tasa']:.1f} % "
                      f"[{100 * ll['ic'][0]:.1f}-{100 * ll['ic'][1]:.1f}]", flush=True)
        out[eje] = filas
    if guardar:
        import datetime as _dt
        import json
        import os
        d = E.en_proyecto(dir_resultados) or E.DIR_RESULTADOS
        os.makedirs(d, exist_ok=True)
        ruta = os.path.join(d, f"fragilidad_{modo}_n{nivel}_{_dt.datetime.now():%Y%m%d_%H%M%S}.json")
        meta = {"modo": modo, "nivel": nivel, "pistas": pistas, "ruidos": ruidos, "conf": conf,
                "hash_pesos": None if callable(pesos) else E.hash_pesos(pesos),
                "fecha": _dt.datetime.now().isoformat(timespec="seconds")}
        with open(ruta, "w", encoding="utf-8") as f:
            json.dump(E._json_seguro({"meta": meta, "fragilidad": out}), f, ensure_ascii=False, indent=1)
        if verbose:
            print("Fragilidad:", ruta)
    return out


RANGOS_DOMINIO = {
    "MASA_CHASIS": 0.10,
    "PAR_MOTOR": 0.15, "POTENCIA": 0.15, "PAR_FRENO": 0.15,
    "SUSP_K": 0.20, "SUSP_C": 0.20,
    "CMG_MAX": 0.25, "LASTRE_MAX": 0.25,
    "TAU_DIRECCION": 0.30, "ARRASTRE": 0.20,
    "PERTURBACION": 0.30, "RUIDO_LATERAL": 0.30,
    "mu": 0.15,
}


class AleatorizacionDominio:
    _activo = None

    def __init__(self, semilla, escala=1.0, rangos=None, sensores=None):
        self.semilla, self.escala = semilla, float(escala)
        self.rangos = dict(RANGOS_DOMINIO if rangos is None else rangos)
        self.sensores = sensores
        rng = np.random.default_rng(semilla)
        self.factores = {k: float(1.0 + r * self.escala * rng.uniform(-1, 1))
                         for k, r in sorted(self.rangos.items())}
        self._orig_c, self._orig_pista, self._pista = {}, None, None

    def activar(self, pista=None):
        if AleatorizacionDominio._activo is not None and AleatorizacionDominio._activo is not self:
            raise RuntimeError("ya hay un dominio aleatorio activo; restáuralo antes")
        if self._orig_c or self._orig_pista:
            return self
        for k, f in self.factores.items():
            if k == "mu" or not hasattr(C, k):
                continue
            self._orig_c[k] = getattr(C, k)
            setattr(C, k, getattr(C, k) * f)
        if "MASA_CHASIS" in self.factores and hasattr(C, "INERCIA_CHASIS"):
            self._orig_c["INERCIA_CHASIS"] = C.INERCIA_CHASIS
            C.INERCIA_CHASIS = C.INERCIA_CHASIS * self.factores["MASA_CHASIS"]
        if pista is not None and "mu" in self.factores:
            self._pista = pista
            self._orig_pista = (pista.mu, getattr(pista, "mu_min", None))
            pista.mu = pista.mu * self.factores["mu"]
            if self._orig_pista[1] is not None:
                pista.mu_min = self._orig_pista[1] * self.factores["mu"]
        AleatorizacionDominio._activo = self
        return self

    def restaurar(self):
        for k, v in self._orig_c.items():
            setattr(C, k, v)
        self._orig_c = {}
        if self._pista is not None and self._orig_pista is not None:
            self._pista.mu = self._orig_pista[0]
            if self._orig_pista[1] is not None:
                self._pista.mu_min = self._orig_pista[1]
        self._pista = self._orig_pista = None
        if AleatorizacionDominio._activo is self:
            AleatorizacionDominio._activo = None

    def contexto(self, pista=None):
        dr = self

        class _Ctx:
            def __enter__(self_):
                return dr.activar(pista)

            def __exit__(self_, *exc):
                dr.restaurar()
                return False
        return _Ctx()

    def filtro_obs(self):
        if self.sensores is None:
            return None
        if isinstance(self.sensores, dict):
            return FiltroSensores(semilla=self.semilla + 1, **self.sensores)
        return crear_filtro(self.sensores, semilla=self.semilla + 1)


def dominio_para_pista(pista, escala=1.0, sensores=None, rangos=None):
    return AleatorizacionDominio(int(getattr(pista, "semilla", 0)) + 424243, escala, rangos, sensores)


def restaurar_dominio():
    if AleatorizacionDominio._activo is not None:
        AleatorizacionDominio._activo.restaurar()
