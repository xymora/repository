from collections import deque

import numpy as np

import config as C
import red as R

_LF = None
_CL = None

VIVO, META, VOLTEO, CAIDA, FUERA, CHOQUE, ATASCADO, TIEMPO = range(8)
ROTURA = 8
MOTIVOS = {VIVO: "en carrera", META: "llegó a la meta", VOLTEO: "se volteó",
           CAIDA: "se cayó de lado", FUERA: "se salió del camino", CHOQUE: "chocó el chasís",
           ATASCADO: "se atascó", TIEMPO: "se acabó el tiempo",
           ROTURA: "rompió la suspensión al caer"}
CLAVES_TRAZA = ("t", "x", "v", "lat", "phi", "th", "cmg_sat", "v_segura", "en_suelo", "invasion")
_MASA_TOTAL = C.MASA_CHASIS + 2 * C.MASA_RUEDA

_MX = np.array([e[0] for e in C.EJES])[:, None]
_MY = np.array([e[1] for e in C.EJES])[:, None]
_OFFS = np.linspace(-C.RADIO_RUEDA, C.RADIO_RUEDA, C.PUNTOS_CONTACTO)
_PCX = np.array([p[0] for p in C.PUNTOS_CHASIS])[:, None]
_PCY = np.array([p[1] for p in C.PUNTOS_CHASIS])[:, None]
_LIDAR = np.array(C.DIST_LIDAR)[:, None]
_FRENO = np.array(C.REPARTO_FRENO)[:, None]
_LIM_FRIC = 1.0 / (C.DT * (1 / C.MASA_RUEDA + C.RADIO_RUEDA ** 2 / C.INERCIA_RUEDA))
_INV_MU_SUSP = 1.0 / C.MASA_RUEDA + 2.0 / C.MASA_CHASIS

_ESTADO = ("px", "py", "th", "vx", "vy", "om", "wx", "wy", "wvx", "wvy", "ws", "ang", "fn", "slip",
           "comp", "phi", "wob", "wobd", "cmg_sat", "derrape", "dirc", "psi", "lat", "dir_obj", "incl",
           "incld", "ctrl", "latx", "contra_x", "contra_y", "phi_moto")
ERRORES = (CAIDA, FUERA, VOLTEO, CHOQUE, ROTURA)

_CAMPOS = ("ids", "px", "py", "th", "vx", "vy", "om", "wx", "wy", "wvx", "wvy", "ws", "ang",
           "fn", "slip", "comp", "phi", "wob", "wobd", "lastre", "cmg", "cmg_sat", "tcs", "abs_", "desliz", "derrape", "dirc", "psi", "lat", "mejor_x", "t_mejora",
           "dir_obj", "incl", "incld", "balanceo", "carril", "peso_carril", "invasion",
           "ctrl", "latx", "contra_x", "par_actitud", "contra_y", "phi_moto", "uso_max")


def estabilidad(v):
    x = np.clip((np.abs(v) - C.V_SIN_EQUILIBRIO) / (C.V_ESTABLE - C.V_SIN_EQUILIBRIO), 0.0, 1.0)
    return x ** C.EXP_EQUILIBRIO


def _tope_direccion(v):
    return np.minimum(C.DIR_MAX, np.arctan(C.A_LAT_MAX * C.DISTANCIA_EJES / np.maximum(v * v, 1e-3)))


class Simulador:

    def __init__(self, pista, pesos, semilla_ruido=0, *, max_reintentos=None,
                 ruido_por_moto=False, filtro_obs=None, controlador=None, n=None,
                 registrar=False, clima=None):
        self.observadores = []
        self._ultimo_regreso = None
        self.clima = None
        self.viento_actual = (0.0, 0.0)
        self._efx = None
        self._viento = None
        if clima is not None:
            global _CL
            if _CL is None:
                import clima as _modc
                _CL = _modc
            self.clima = _CL.crear(clima, 0 if isinstance(clima, _CL.Clima)
                                   else int(getattr(pista, "semilla", 0) or 0))
            if getattr(pista, "clima", None) != self.clima or not hasattr(pista, "charco"):
                pista = _CL.preparar_pista(pista, self.clima)
        self.pista = pista
        if pesos is None:
            if n is None or controlador is None:
                raise ValueError("Sin pesos hay que dar `controlador` y `n`.")
            self.red = None
        else:
            pesos = np.atleast_2d(pesos)
            n = pesos.shape[0]
            self.red = R.desempacar(pesos, C.CAPAS)
        self.n_total = n
        self.max_reintentos = C.MAX_REINTENTOS if max_reintentos is None else int(max_reintentos)
        self.ruido_por_moto = bool(ruido_por_moto)
        self.filtro_obs = filtro_obs
        self.controlador = controlador
        self.registrar = bool(registrar)
        self.traza = {k: [] for k in CLAVES_TRAZA} if self.registrar else None
        self.ruido = np.random.default_rng(semilla_ruido)
        self._v_segura = None
        self._en_suelo = None
        self.t = 0.0
        self.terminado = False

        self.motivo = np.zeros(n, dtype=np.int64)
        self.progreso = np.zeros(n)
        self.balanceo_medio = np.zeros(n)
        self.carril_medio = np.zeros(n)
        self.reintentos = np.zeros(n, dtype=np.int64)
        self.eventos = []
        self.t_fin = np.zeros(n)
        self.pos_final = np.zeros((n, 3))

        x0 = pista.salida
        h0 = pista.altura(x0)
        self.ids = np.arange(n)
        self.px = np.full(n, x0)
        self.py = np.full(n, h0 + C.RADIO_RUEDA + 0.5 - 0.04)
        self.th = np.zeros(n)
        self.vx = np.full(n, C.V_INICIAL)
        self.vy = np.zeros(n)
        self.om = np.zeros(n)
        self.wx = self.px + _MX
        self.wy = self.py + _MY
        self.wvx = np.full((2, n), C.V_INICIAL)
        self.wvy = np.zeros((2, n))
        self.ws = np.full((2, n), C.V_INICIAL / C.RADIO_RUEDA)
        self.ang = np.zeros((2, n))
        self.fn = np.zeros((2, n))
        self.slip = np.zeros((2, n))
        self.comp = np.zeros((2, n))
        self.phi = np.zeros(n)
        self.wob = np.zeros(n)
        self.wobd = np.zeros(n)
        self.lastre = np.zeros(n)
        self.contra_x = np.zeros(n)
        self.par_actitud = np.zeros(n)
        self.contra_y = np.zeros(n)
        self.phi_moto = np.zeros(n)
        self.uso_max = np.zeros(n)
        self.carga = np.zeros((2, n))
        self.tcs = np.zeros(n)
        self.abs_ = np.zeros(n)
        self.desliz = np.zeros((2, n))
        self.cmg = np.zeros(n)
        self.cmg_sat = np.zeros(n)
        self.derrape = np.zeros(n)
        self.dirc = np.zeros(n)
        self.dir_obj = np.zeros(n)
        self.incl = np.zeros(n)
        self.incld = np.zeros(n)
        self.balanceo = np.zeros(n)
        self.carril = np.zeros(n)
        self.peso_carril = np.zeros(n)
        self.invasion = np.zeros(n)
        self.invasion_frac = np.zeros(n)
        self.psi = np.zeros(n)
        self.lat = np.full(n, C.LAT_CARRIL)
        self.mejor_x = self.px.copy()
        self.t_mejora = np.zeros(n)
        self.ctrl = np.zeros((n, 3))
        self.latx = np.zeros((6, n))
        if self.clima is not None:
            self._efx = _CL.EfectosClima(self.clima, pista, n, self.ruido_por_moto)
        self._fotos = deque(maxlen=int(C.SEG_RETROCESO) + 3)
        self._pasos = 0
        self._tomar_foto()

    def observar(self):
        p = self.pista
        c = 1.0
        v = self.vx * np.cos(self.th) + self.vy * np.sin(self.th)
        h_aqui = p.altura(self.px)
        lidar = (p.altura(self.px + _LIDAR) - h_aqui) / 2.0
        i_aqui = p.indice(self.wx[0])
        i_frente = p.indice(self.px + 5.0)
        av = np.abs(v)
        k1 = p.kappa[p.indice(self.px + np.maximum(4.0, 0.6 * av))]
        k2 = p.kappa[p.indice(self.px + np.maximum(10.0, 1.5 * av))]
        k3 = p.kappa[p.indice(self.px + np.maximum(20.0, 3.0 * av))]
        i_px = p.indice(self.px)
        kmax = p.kmax[i_px]
        a_posible = np.minimum(C.A_LAT_MAX, 0.85 * p.mu_min[i_px] * C.G)
        v_segura = np.minimum(np.sqrt(a_posible / np.maximum(kmax, 1e-3)), 30.0)
        self._v_segura = v_segura
        obs = np.stack([
            v / 15.0,
            self.vy / 8.0,
            self.th / 1.2,
            self.om / 4.0,
            self.phi / 0.5,
            self.incld / 2.0,
            self.cmg_sat,
            self.derrape / C.DERRAPE_MAX,
            self.dirc / _tope_direccion(v),
            self.lat / (C.ANCHO_CAMINO / 2),
            (self.lat - C.LAT_CARRIL) / 1.0,
            np.clip((self.lat + v * np.sin(self.psi) * 0.8 - C.LAT_CARRIL) / 1.5, -2, 2),
            np.clip(np.arctan(p.kappa[p.indice(self.px + 0.3 * av)] * C.DISTANCIA_EJES)
                    / _tope_direccion(v), -2, 2),
            self.psi / 0.5,
            v * np.sin(self.psi) / 3.0,
            (self.fn[0] > 0) * c,
            (self.fn[1] > 0) * c,
            np.clip(self.slip[0] / 5.0, -1, 1),
            np.clip(self.slip[1] / 5.0, -1, 1),
            self.comp[0] / C.RECORRIDO,
            self.comp[1] / C.RECORRIDO,
            p.mu[i_aqui],
            p.mu[i_frente],
            p.rr[i_frente] * 5.0,
            k1 * 10.0,
            k2 * 10.0,
            k3 * 10.0,
            np.clip((av - v_segura) / 10.0, -1.5, 1.5),
            np.clip((av - C.V_ESTABLE) / 5.0, -2, 2),
            *np.clip(lidar, -2, 2),
        ], axis=1)
        if self._efx is not None and self._efx.charcos:
            obs[:, 21] = obs[:, 21] * _CL.factor_aquaplaning(v, p.charco[i_aqui])
            obs[:, 22] = obs[:, 22] * _CL.factor_aquaplaning(v, p.charco[i_frente])
        return obs

    def paso(self, ctrl=None):
        if self.terminado:
            return
        if ctrl is not None:
            ctrl = np.asarray(ctrl, dtype=float)
            if ctrl.shape[0] == self.n_total and len(self.ids) < self.n_total:
                ctrl = ctrl[self.ids]
            self.observar()
            self.ctrl = np.clip(ctrl, -1.0, 1.0)
        else:
            obs = self.observar()
            if self._efx is not None:
                obs = self._efx.degradar(obs, self.ids)
            if self.filtro_obs is not None:
                obs = self.filtro_obs(obs, self)
            if self.controlador is not None:
                self.ctrl = np.clip(np.asarray(self.controlador(obs, self), dtype=float), -1.0, 1.0)
            else:
                motor = self._motor_fisica()
                ctrl = motor.red(self.red, self.ids, obs) if motor is not None else None
                if ctrl is None:
                    red = [(W[self.ids], b[self.ids]) for W, b in self.red] \
                        if len(self.ids) < self.n_total else self.red
                    ctrl = R.adelante(red, obs)
                self.ctrl = ctrl
        rugo = self.pista.rugo[self.pista.indice(self.px)]
        if self.ruido_por_moto:
            z1 = self.ruido.normal(size=self.n_total)[self.ids]
            z2 = self.ruido.normal(size=self.n_total)[self.ids]
        else:
            z1 = self.ruido.normal()
            z2 = None
        if C.RUIDO_SQRT_DT:
            v_real = self.vx * np.cos(self.th) + self.vy * np.sin(self.th)
            escala = np.sqrt(C.DT_REF_RUIDO / C.DT_CONTROL)
            empujon = (C.PERTURBACION * rugo * np.abs(v_real) + C.RUIDO_LATERAL) * escala * z1
        else:
            empujon = (C.PERTURBACION * rugo * np.abs(self.vx) + C.RUIDO_LATERAL) * z1
        deriva = self.ruido.normal() if z2 is None else z2
        if C.RUIDO_SQRT_DT:
            deriva = deriva * escala
        if self._efx is not None:
            self._viento = self._efx.fuerzas(self)
            self.viento_actual = self._efx.viento_actual()
        self.carga = np.zeros((2, len(self.ids)))
        motor = self._motor_fisica()
        if motor is not None:
            motor.subpasos(np.broadcast_to(empujon, (len(self.ids),)), deriva)
        else:
            for _ in range(C.SUBPASOS):
                self._fisica(empujon, deriva)
        if self.registrar:
            self._registrar()
        self.ang = self.ang + self.ws * C.DT_CONTROL
        v = self.vx * np.cos(self.th) + self.vy * np.sin(self.th)
        necesaria = np.arctan(v * v * self.pista.kappa[self.pista.indice(self.px)] / C.G)
        self.balanceo = self.balanceo + np.abs(self.phi - necesaria) * C.DT_CONTROL
        k_aqui = np.abs(self.pista.kappa[self.pista.indice(self.px)])
        peso = 1.0 + C.PESO_CURVA * np.minimum(k_aqui / 0.03, 1.0)
        self.carril = self.carril + peso * np.abs(self.lat - C.LAT_CARRIL) * C.DT_CONTROL
        self.peso_carril = self.peso_carril + peso * C.DT_CONTROL
        self.invasion = self.invasion + (self.lat > 0) * C.DT_CONTROL
        self.t += C.DT_CONTROL
        self._revisar()
        self._pasos += 1
        if self._pasos % round(1 / C.DT_CONTROL) == 0 and not self.terminado:
            self._tomar_foto()
        for o in self.observadores:
            if callable(o):
                o(self)

    def uso_estructura(self):
        cg = getattr(self, "carga", None)
        if cg is None or cg.shape[1] != len(self.ids):
            return np.zeros(len(self.ids))
        return np.maximum(cg[0] / C.CARGA_LIMITE[0], cg[1] / C.CARGA_LIMITE[1])

    def _motor_fisica(self):
        m = getattr(self, "_motor", False)
        if m is False:
            m = None
            try:
                import aceleracion as A
                tipo = A.elegir(self.n_total)
                if tipo != "numpy":
                    import fisica_acelerada as FA
                    m = FA.Motor(self, "gpu" if tipo == "gpu" else "cpu")
            except Exception as ex:
                import warnings
                warnings.warn(f"física acelerada no disponible ({ex!r}); se usa numpy")
                m = None
            self._motor = m
            self.motor_fisica = "numpy" if m is None else m.dispositivo.replace("cpu", "numba")
        return m

    def correr(self, pasos):
        for _ in range(pasos):
            if self.terminado:
                break
            self.paso()

    def _fisica(self, empujon, deriva=0.0):
        p = self.pista
        dt = C.DT
        acel, cab, dirc_cmd = self.ctrl[:, 0], self.ctrl[:, 1], self.ctrl[:, 2]
        c, s = np.cos(self.th), np.sin(self.th)

        rx = c * _MX - s * _MY
        ry = s * _MX + c * _MY
        ex = self.wx - (self.px + rx)
        ey = self.wy - (self.py + ry)
        evx = self.wvx - (self.vx - self.om * ry)
        evy = self.wvy - (self.vy + self.om * rx)
        elx, ely = c * ex + s * ey, -s * ex + c * ey
        evlx, evly = c * evx + s * evy, -s * evx + c * evy
        flx = -C.SUSP_KX * elx - C.SUSP_CX * evlx
        if C.SUSPENSION_REALISTA:
            tope = np.maximum(ely - C.RECORRIDO, 0)
            amort = np.where(evly > 0, C.SUSP_C + np.where(tope > 0, C.TOPE_C, 0.0), C.SUSP_C_REBOTE)
            amort = amort / (1.0 + dt * amort * _INV_MU_SUSP)
            resorte = C.SUSP_K * ely * (1.0 + C.SUSP_PROGRESION
                                        * (np.maximum(ely, 0.0) / C.RECORRIDO) ** 2)
            fly = -resorte - amort * evly
            fly -= C.TOPE_K * (np.where(evly > 0, 1.0, C.TOPE_RETORNO) * tope
                               + np.minimum(ely + C.EXTENSION, 0))
            cg = getattr(self, "carga", None)
            if cg is None or cg.shape != fly.shape:
                cg = np.zeros(fly.shape)
            self.carga = np.maximum(cg, np.abs(fly))
        else:
            fly = -C.SUSP_K * ely - C.SUSP_C * evly
            fly -= C.TOPE_K * (np.maximum(ely - C.RECORRIDO, 0) + np.minimum(ely + C.EXTENSION, 0))
        fx = c * flx - s * fly
        fy = s * flx + c * fly
        self.comp = ely

        xs = self.wx[..., None] + _OFFS
        dy = self.wy[..., None] - p.altura(xs)
        dist = np.sqrt(_OFFS ** 2 + dy ** 2)
        pen = np.where(dy > 0, C.RADIO_RUEDA - dist, C.RADIO_RUEDA - dy)
        k = np.argmax(pen, axis=-1)
        plano = k.ravel() + np.arange(k.size) * C.PUNTOS_CONTACTO
        pen = pen.ravel()[plano].reshape(k.shape)
        dyk = dy.ravel()[plano].reshape(k.shape)
        distk = dist.ravel()[plano].reshape(k.shape)
        sobre = dyk > 1e-6
        nx = np.where(sobre, -_OFFS[k] / np.maximum(distk, 1e-6), 0.0)
        ny = np.where(sobre, dyk / np.maximum(distk, 1e-6), 1.0)
        contacto = pen > 0
        vn = self.wvx * nx + self.wvy * ny
        if C.SUSPENSION_REALISTA:
            k_pen = C.SUELO_K * pen + C.RIN_K * np.maximum(pen - C.NEUMATICO_DEFLEX_MAX, 0.0)
        else:
            k_pen = C.SUELO_K * pen
        fn = np.where(contacto, np.maximum(k_pen - C.SUELO_C * vn, 0.0), 0.0)
        tx, ty = ny, -nx
        slip = self.wvx * tx + self.wvy * ty - self.ws * C.RADIO_RUEDA
        i = p.indice(self.wx)
        mu_i = p.mu[i]
        if self._efx is not None and self._efx.charcos:
            mu_i = mu_i * _CL.factor_aquaplaning(self.vx * c + self.vy * s, p.charco[i])
        self._mu_i = mu_i
        vt = slip + self.ws * C.RADIO_RUEDA
        desliz = slip / np.maximum(np.abs(vt), 1.0)
        self.desliz = desliz
        caida = 1.0 - C.PERDIDA_DESLIZ * np.clip((np.abs(desliz) - C.DESLIZ_PICO) / 0.6, 0.0, 1.0)
        ft = -np.sign(slip) * np.minimum(mu_i * fn * caida * np.tanh(np.abs(slip) / C.V_DESLIZ),
                                         np.abs(slip) * _LIM_FRIC)
        self.fn, self.slip = fn, slip

        gas = np.maximum(acel, 0)
        freno = np.maximum(-acel, 0)
        par_motor = gas * np.minimum(C.PAR_MOTOR, C.POTENCIA / np.maximum(np.abs(self.ws[0]), 1.0))
        if C.TCS_ACTIVO:
            patina = np.where(contacto[0], np.maximum(-desliz[0], 0.0), 0.0)
            f_tcs = np.clip(1.0 - (patina - C.TCS_OBJ) / C.TCS_RANGO, 0.1, 1.0)
            par_motor = par_motor * f_tcs
            self.tcs = np.where(gas > 0.05, 1.0 - f_tcs, 0.0)
        freno_rueda = freno * C.PAR_FRENO * _FRENO
        if C.CONTRAPESO_ACTIVO:
            aire, e, e_pred = self._actitud(p, contacto)
            self._att = (aire, e, e_pred)
            sobra = e_pred - C.ATT_NARIZ
            gas_aire = np.clip(-(sobra + 0.05) / 0.25, 0.0, 1.0)
            par_max = np.minimum(C.PAR_MOTOR, C.POTENCIA / np.maximum(np.abs(self.ws[0]), 1.0))
            par_motor = np.where(aire, np.maximum(par_motor * np.clip(1.0 - sobra / 0.25, 0.0, 1.0),
                                                  gas_aire * par_max), par_motor)
            caballito = np.where(contacto[1], 0.0, np.maximum(e_pred - C.ATT_CABALLITO, 0.0))
            par_motor = par_motor * np.clip(1.0 - caballito / 0.15, 0.0, 1.0)
            freno_rueda = freno_rueda.copy()
            freno_rueda[0] = np.where(aire, np.clip((sobra - 0.08) / 0.25, 0.0, 1.0) * 0.6 * C.PAR_FRENO,
                                      freno_rueda[0])
        if C.MSC_ACTIVO and C.FRENADA_MEJORADA:
            reparto = np.where(contacto, fn, 0.0) / np.maximum(np.where(contacto, fn, 0.0).sum(0), 1.0)
            freno_rueda = freno * C.PAR_FRENO_MEJORADA * reparto
        if C.MSC_ACTIVO:
            mu_m = np.maximum(mu_i.max(0), 0.05)
            uso_lat = np.minimum(np.abs(np.tan(self.phi)) / mu_m, 1.0)
            f_incl = np.maximum(np.sqrt(1.0 - uso_lat ** 2), C.MSC_MIN_INCL)
            f_aw = np.clip(1.0 - (self.th - C.MSC_TH_WHEELIE) / C.MSC_WHEELIE_RANGO, 0.0, 1.0)
            par_motor = par_motor * np.where(contacto[0], f_aw * f_incl, 1.0)
            f_fn = np.clip(fn[0] / (C.MSC_FN_TRASERA * _MASA_TOTAL * C.G), 0.0, 1.0)
            f_om = np.clip(1.0 - (-self.om - C.MSC_OM_PICADO) / C.MSC_OM_RANGO, 0.0, 1.0)
            f_th = np.clip(1.0 - (-self.th - C.MSC_TH_PICADO) / C.MSC_TH_RANGO, 0.0, 1.0)
            f_rlp = np.where(contacto[1], np.minimum(np.minimum(f_fn, f_om), f_th), 1.0)
            freno_rueda = freno_rueda * f_incl
            freno_rueda[1] = freno_rueda[1] * f_rlp
        if C.ABS_ACTIVO:
            bloqueo = np.where(contacto, np.maximum(desliz, 0.0), 0.0)
            f_abs = np.clip(1.0 - (bloqueo - C.ABS_OBJ) / C.ABS_RANGO, 0.1, 1.0)
            freno_rueda = freno_rueda * f_abs
            self.abs_ = np.where(freno > 0.05, 1.0 - f_abs.min(0), 0.0)
        par_freno = np.sign(self.ws) * np.minimum(freno_rueda,
                                                  np.abs(self.ws) * C.INERCIA_RUEDA / dt)
        par_rodar = -p.rr[i] * fn * C.RADIO_RUEDA * np.tanh(self.ws)
        par = -par_freno - C.RADIO_RUEDA * ft + par_rodar
        par[0] += par_motor
        self.ws = self.ws + dt * par / C.INERCIA_RUEDA

        fwx = fx + fn * nx + ft * tx
        fwy = fy + fn * ny + ft * ty - C.MASA_RUEDA * C.G
        self.wvx = self.wvx + dt * fwx / C.MASA_RUEDA
        self.wvy = self.wvy + dt * fwy / C.MASA_RUEDA
        self.wx = self.wx + dt * self.wvx
        self.wy = self.wy + dt * self.wvy

        rapidez = np.hypot(self.vx, self.vy)
        if self._viento is not None:
            vrx = self.vx - self._viento[2]
            fcx = -fx.sum(0) - C.ARRASTRE * np.hypot(vrx, self.vy) * vrx
        else:
            fcx = -fx.sum(0) - C.ARRASTRE * rapidez * self.vx
        fcy = -fy.sum(0) - C.ARRASTRE * rapidez * self.vy - C.MASA_CHASIS * C.G
        tau = (rx * -fy - ry * -fx).sum(0) + par_motor - par_freno.sum(0) + cab * C.PAR_CABECEO
        if C.CONTRAPESO_ACTIVO:
            tau = tau + self._contrapeso(contacto, dt)
        self.vx = self.vx + dt * fcx / C.MASA_CHASIS
        self.vy = self.vy + dt * fcy / C.MASA_CHASIS
        self.om = self.om + dt * tau / C.INERCIA_CHASIS
        self.px = self.px + dt * self.vx
        self.py = self.py + dt * self.vy
        self.th = self.th + dt * self.om

        en_suelo = contacto.any(0)
        self._en_suelo = en_suelo
        v = self.vx * c + self.vy * s
        if C.MODELO_LATERAL == "fisico":
            self._lateral_fisico(p, i, contacto, fn, ft, v, dirc_cmd, empujon, deriva, en_suelo, dt)
            return
        tope = _tope_direccion(v)
        self.dir_obj = self.dir_obj + (dirc_cmd * tope - self.dir_obj) * (dt / C.TAU_DIRECCION)
        self.dirc = self.dirc + np.clip(self.dir_obj - self.dirc,
                                        -C.DIR_VEL * dt, C.DIR_VEL * dt)
        giro = v * np.tan(self.dirc) / C.DISTANCIA_EJES
        if C.CONTRAPESO_ACTIVO:
            giro, recupera, activo = self._contra_derrape(giro, v, en_suelo, dt)
        else:
            recupera, activo = C.RECUPERA_DERRAPE, None
        perdida = np.where(contacto, np.clip((np.abs(self.desliz) - 0.2) / 0.5, 0.0, 1.0), 0.0).max(0)
        if C.FRICCION_COMBINADA:
            perd_i = np.where(contacto, np.clip((np.abs(self.desliz) - 0.2) / 0.5, 0.0, 1.0), 0.0)
            fy_max = np.sqrt(np.maximum((self._mu_i * fn) ** 2 - ft ** 2, 0.0)) \
                * (1.0 - C.PERDIDA_LATERAL * perd_i)
            agarre = fy_max.sum(0) / _MASA_TOTAL
        else:
            agarre = self._mu_i.max(0) * C.G * (1.0 - C.PERDIDA_LATERAL * perdida)
        a_lat = np.abs(v * giro)
        exceso = np.where(en_suelo, np.maximum(a_lat - agarre, 0.0), 0.0)
        self.derrape = np.maximum(self.derrape + dt * (exceso - recupera), 0.0)
        giro = np.where(exceso > 0, np.sign(giro) * agarre / np.maximum(np.abs(v), 0.5), giro)
        kappa = p.kappa[p.indice(self.px)]
        f = estabilidad(v)
        self.psi = self.psi + dt * (np.where(en_suelo, giro, 0.0) - v * kappa
                                    + (1.0 - f) * C.DERIVA_LENTA * deriva
                                    * (1.0 - C.DAMPER_DERIVA * C.AMORTIGUADOR_ACTIVO))
        if self._viento is not None:
            self.psi = self.psi + dt * self._viento[0] / np.maximum(np.abs(v), 3.0)
        self.lat = self.lat + dt * v * np.sin(self.psi)

        caida = C.G / C.ALTURA_CG
        estabiliza = (C.GIRO_W ** 2 + caida) * f
        amortigua = 2 * C.GIRO_Z * C.GIRO_W * np.maximum(f, 0.1) \
            + C.AMORT_DIRECCION * C.AMORTIGUADOR_ACTIVO
        sacudida = empujon * (1.0 + C.AMPLIF_LENTA * (1.0 - f))
        self.lastre = np.clip(-(C.LASTRE_K * self.wob + C.LASTRE_D * self.wobd),
                              -C.LASTRE_MAX, C.LASTRE_MAX)
        if activo is not None:
            self.lastre = np.clip(self.lastre - C.CONTRA_LASTRE * activo * np.sign(self.phi),
                                  -C.LASTRE_MAX, C.LASTRE_MAX)
        h = np.clip(np.abs(v) / C.V_ESTABLE, 0.0, 1.0) ** C.CMG_EXP
        pedido = -(C.CMG_K * self.wob + C.CMG_D * self.wobd)
        self.cmg = np.clip(pedido, -C.CMG_MAX * h, C.CMG_MAX * h) * (1.0 - self.cmg_sat ** 2)
        self.cmg_sat = np.clip(self.cmg_sat + dt * (self.cmg / (C.CMG_CAPACIDAD * np.maximum(h, 0.05))
                                                    - C.CMG_RECENTRADO * self.cmg_sat), -1.0, 1.0)
        wobdd = np.where(en_suelo, caida * np.sin(self.wob) - estabiliza * self.wob + sacudida
                         + self.lastre + self.cmg, 0.0) - amortigua * self.wobd
        if self._viento is not None:
            wobdd = wobdd + self._viento[1]
        self.wobd = self.wobd + dt * wobdd
        self.wob = self.wob + dt * self.wobd
        objetivo = np.arctan(v * giro / C.G)
        w = C.INCL_W
        if C.CONTRAPESO_ACTIVO:
            saliendo = (np.abs(objetivo) < np.abs(self.incl)) * np.abs(self.contra_y) / C.CONTRA_Y_MAX
            w = C.INCL_W * (1.0 + C.CONTRA_SALIDA * saliendo)
        incldd = np.where(en_suelo, w ** 2 * (objetivo - self.incl), 0.0) \
            - 2 * C.INCL_Z * w * self.incld
        self.incld = self.incld + dt * incldd
        self.incl = self.incl + dt * self.incld
        self.phi = self.incl + self.wob
        if C.CONTRAPESO_ACTIVO:
            y_obj = -np.sign(self.incl) * C.CONTRA_Y_MAX \
                * np.clip(np.abs(self.incl) / C.CONTRA_INCL_REF, 0.0, 1.0)
            y_obj = np.where(en_suelo, y_obj, self.contra_y)
            paso = C.CONTRA_Y_VEL * dt
            self.contra_y = self.contra_y + np.clip(y_obj - self.contra_y, -paso, paso)
            self.phi_moto = self.phi - C.MASA_LASTRE * self.contra_y / (_MASA_TOTAL * C.ALTURA_CG)
        else:
            self.phi_moto = self.phi

    def _actitud(self, p, contacto):
        aire = ~(contacto[0] | contacto[1])
        sobre = np.maximum(self.py - p.altura(self.px) + C.EJES[0][1] - C.RADIO_RUEDA, 0.0)
        t_caida = np.minimum((self.vy + np.sqrt(self.vy ** 2 + 2 * C.G * sobre)) / C.G, 1.5)
        x_ref = np.where(aire, self.px + self.vx * t_caida, self.px)
        pend = np.arctan((p.altura(x_ref + 0.8) - p.altura(x_ref - 0.8)) / 1.6)
        e = self.th - pend
        return aire, e, e + 0.15 * self.om

    def _contrapeso(self, contacto, dt):
        tras, dela = contacto[0], contacto[1]
        aire, e, e_pred = self._att
        I = C.INERCIA_CHASIS
        k, d = I * C.ATT_W ** 2, 2 * C.ATT_Z * C.ATT_W * I
        caballito = np.where(dela, 0.0, np.maximum(e_pred - C.ATT_CABALLITO, 0.0))
        picado = np.where(tras, 0.0, np.minimum(e_pred + C.ATT_PICADO, 0.0))
        en_limite = (caballito > 0) | (picado < 0)
        bajando = tras & ~dela & (self.om < 0) & ~en_limite
        par = np.where(aire, -k * (e - C.ATT_NARIZ) - d * self.om,
                       np.where(en_limite, -k * (caballito + picado) - d * self.om,
                                np.where(bajando, -C.ATT_ATERRIZAJE * d * self.om, 0.0)))
        par = np.clip(par, -C.ATT_PAR_MAX, C.ATT_PAR_MAX)
        x_obj = np.where(aire | bajando, -0.7, np.clip(e_pred / C.ATT_CABALLITO, -1.0, 1.0)) * C.CONTRA_X_MAX
        paso = C.CONTRA_VEL * dt
        self.contra_x = self.contra_x + np.clip(x_obj - self.contra_x, -paso, paso)
        par = par + np.where(aire, 0.0, -C.MASA_LASTRE * C.G * self.contra_x * np.cos(self.th))
        self.par_actitud = par
        return par

    def _contra_derrape(self, giro, v, en_suelo, dt):
        activo = np.where(en_suelo, np.clip(self.derrape / 0.5, 0.0, 1.0), 0.0)
        h = np.clip(np.abs(v) / C.V_ESTABLE, 0.0, 1.0) ** C.CMG_EXP
        libre = h * (1.0 - self.cmg_sat ** 2)
        recupera = C.RECUPERA_DERRAPE + C.CONTRA_RECUPERA * activo * libre
        signo = np.where(self.cmg_sat >= 0, 1.0, -1.0)
        self.cmg_sat = signo * np.minimum(np.abs(self.cmg_sat) + dt * C.CONTRA_COSTO * activo, 1.0)
        return giro * (1.0 - C.CONTRA_CEDE * activo), recupera, activo

    def _lateral_fisico(self, p, i, contacto, fn, ft, v, dirc_cmd, empujon, deriva, en_suelo, dt):
        global _LF
        if _LF is None:
            import lateral_fisico as _mod
            _LF = _mod
        LF = _LF.modelo()
        I = LF.I_roll
        k_max = np.minimum(C.A_LAT_MAX / np.maximum(v * v, 1e-3),
                           np.tan(C.DIR_MAX) / C.DISTANCIA_EJES)
        self.dir_obj = self.dir_obj + (dirc_cmd * k_max - self.dir_obj) * (dt / C.TAU_DIRECCION)
        h = np.clip(np.abs(v) / C.V_ESTABLE, 0.0, 1.0) ** C.CMG_EXP

        def limitar_alabeo(t_pedido):
            t_prev = self.lastre * I
            paso_max = C.MASA_LASTRE * C.G * C.LF_VEL_LASTRE * dt
            t_lastre = np.clip(np.clip(t_pedido, -C.LASTRE_MAX * I, C.LASTRE_MAX * I),
                               t_prev - paso_max, t_prev + paso_max)
            cmg = np.clip((t_pedido - t_lastre) / I, -C.CMG_MAX * h, C.CMG_MAX * h) \
                * (1.0 - self.cmg_sat ** 2)
            self.cmg_sat = np.clip(self.cmg_sat + dt * (cmg / (C.CMG_CAPACIDAD * np.maximum(h, 0.05))
                                                        - C.CMG_RECENTRADO * self.cmg_sat), -1.0, 1.0)
            self.lastre = t_lastre / I
            self.cmg = cmg
            return t_lastre + cmg * I

        n = len(v)
        t_pert = np.stack([np.broadcast_to(empujon * I * C.LF_RUIDO_ROLL, (n,)),
                           np.broadcast_to(deriva * C.LF_RUIDO_DIR, (n,))]).astype(float)
        if self._viento is not None:
            t_pert[0] = t_pert[0] + self._viento[1] * I
        self.latx, _ = LF.paso(self.latx, self.dir_obj, v, t_pert, limitar_alabeo, dt, en_suelo)
        x = self.latx
        self.dirc = x[1]
        giro = LF.guinada(x, v)
        recupera = C.RECUPERA_DERRAPE
        if C.CONTRAPESO_ACTIVO:
            giro, recupera, _ = self._contra_derrape(giro, v, en_suelo, dt)
        perdida = np.where(contacto, np.clip((np.abs(self.desliz) - 0.2) / 0.5, 0.0, 1.0), 0.0).max(0)
        if C.FRICCION_COMBINADA:
            perd_i = np.where(contacto, np.clip((np.abs(self.desliz) - 0.2) / 0.5, 0.0, 1.0), 0.0)
            fy_max = np.sqrt(np.maximum((self._mu_i * fn) ** 2 - ft ** 2, 0.0)) \
                * (1.0 - C.PERDIDA_LATERAL * perd_i)
            agarre = fy_max.sum(0) / _MASA_TOTAL
        else:
            agarre = self._mu_i.max(0) * C.G * (1.0 - C.PERDIDA_LATERAL * perdida)
        a_lat = np.abs(v * giro)
        exceso = np.where(en_suelo, np.maximum(a_lat - agarre, 0.0), 0.0)
        self.derrape = np.maximum(self.derrape + dt * (exceso - recupera), 0.0)
        giro = np.where(exceso > 0, np.sign(giro) * agarre / np.maximum(np.abs(v), 0.5), giro)
        kappa = p.kappa[p.indice(self.px)]
        self.psi = self.psi + dt * (np.where(en_suelo, giro, 0.0) - v * kappa)
        if self._viento is not None:
            self.psi = self.psi + dt * self._viento[0] / np.maximum(np.abs(v), 3.0)
        self.lat = self.lat + dt * v * np.sin(self.psi)
        phi_eq = LF._interp(LF.xs_t[:, 0], v) * self.dir_obj
        self.phi = x[0]
        self.phi_moto = x[0]
        self.incl = phi_eq
        self.wob = x[0] - phi_eq
        self.incld = x[2]
        self.wobd = x[2]

    def _revisar(self):
        p = self.pista
        c, s = np.cos(self.th), np.sin(self.th)
        bx = self.px + c * _PCX - s * _PCY
        by = self.py + s * _PCX + c * _PCY
        motivo = np.zeros(len(self.ids), dtype=np.int64)
        mejora = self.px > self.mejor_x + 0.3
        self.mejor_x = np.where(mejora, self.px, self.mejor_x)
        self.t_mejora = np.where(mejora, self.t, self.t_mejora)

        motivo[self.t >= p.tiempo_max] = TIEMPO
        motivo[self.t - self.t_mejora > C.SEG_ATASCADO] = ATASCADO
        motivo[np.abs(self.lat) > C.ANCHO_CAMINO / 2] = FUERA
        motivo[(np.abs(self.phi) > C.ALABEO_MAX) | (self.derrape > C.DERRAPE_MAX)] = CAIDA
        if C.CONTRAPESO_ACTIVO:
            motivo[np.abs(self.phi_moto) > C.ALABEO_MOTO_MAX] = CAIDA
        motivo[(by < p.altura(bx)).any(0)] = CHOQUE
        if C.SUSPENSION_REALISTA:
            uso = self.uso_estructura()
            if len(uso) == len(motivo):
                self.uso_max = np.maximum(self.uso_max, uso)
                motivo[uso > 1.0] = ROTURA
        motivo[np.abs(self.th) > C.CABECEO_MAX] = VOLTEO
        motivo[~np.isfinite(self.px + self.py + self.th)] = VOLTEO
        motivo[self.px >= p.meta] = META

        regresa = np.isin(motivo, ERRORES) & (self.reintentos[self.ids] < self.max_reintentos)
        if regresa.any():
            self._regresar(np.flatnonzero(regresa), motivo)
            motivo[regresa] = VIVO

        fin = motivo != VIVO
        if fin.any():
            ids = self.ids[fin]
            self.motivo[ids] = motivo[fin]
            self.progreso[ids] = np.clip(np.where(motivo[fin] == META, p.meta, self.mejor_x[fin])
                                         - p.salida, 0, None)
            self.t_fin[ids] = self.t
            self.balanceo_medio[ids] = np.degrees(self.balanceo[fin] / max(self.t, C.DT_CONTROL))
            self.carril_medio[ids] = self.carril[fin] / np.maximum(self.peso_carril[fin], C.DT_CONTROL)
            self.invasion_frac[ids] = self.invasion[fin] / max(self.t, C.DT_CONTROL)
            self.pos_final[ids] = np.stack([self.px[fin], self.py[fin], self.th[fin]], axis=1)
            self._quedarse(~fin)

    def _tomar_foto(self):
        foto = {"t": self.t}
        n = self.n_total
        for campo in _ESTADO:
            arr = getattr(self, campo)
            if arr.ndim == 1:
                completo = np.zeros(n)
                completo[self.ids] = arr
            elif campo == "ctrl":
                completo = np.zeros((n, arr.shape[1]))
                completo[self.ids] = arr
            else:
                completo = np.zeros((arr.shape[0], n))
                completo[:, self.ids] = arr
            foto[campo] = completo
        self._fotos.append(foto)

    def _regresar(self, k, motivo):
        foto = self._fotos[0]
        for f in reversed(self._fotos):
            if self.t - f["t"] >= C.SEG_RETROCESO:
                foto = f
                break
        ids = self.ids[k]
        x_error = self.px[k].copy()
        for campo in _ESTADO:
            arr = getattr(self, campo)
            if arr.ndim == 1 or campo == "ctrl":
                arr[k] = foto[campo][ids]
            else:
                arr[:, k] = foto[campo][:, ids]
        self.reintentos[ids] += 1
        self.t_mejora[k] = self.t
        for i, xe, xr, m in zip(ids, x_error, self.px[k], motivo[k]):
            self.eventos.append((int(i), float(xe), float(xr), int(m)))
        if self.observadores:
            self._ultimo_regreso = (ids.copy(), float(foto["t"]))
            for o in self.observadores:
                if hasattr(o, "al_regresar"):
                    o.al_regresar(self, ids.copy(), float(foto["t"]))

    def _quedarse(self, mascara):
        for campo in _CAMPOS:
            arr = getattr(self, campo)
            setattr(self, campo, arr[mascara] if arr.ndim == 1 or campo == "ctrl"
                    else arr[:, mascara])
        if len(self.ids) == 0:
            self.terminado = True

    def aptitud(self):
        if C.APTITUD_ESTRICTA:
            return sum(self.componentes_aptitud().values())
        largo = self.pista.meta - self.pista.salida
        f = (100.0 * self.progreso / largo - C.PENAL_BALANCEO * self.balanceo_medio
             - C.PENAL_CARRIL * self.carril_medio - C.PENAL_INVASION * self.invasion_frac)
        meta = self.motivo == META
        t_ref = largo / C.V_REFERENCIA
        rapidez = np.minimum(t_ref / np.maximum(self.t_fin, 1e-3), C.RAPIDEZ_MAX)
        f += np.where(meta, C.PREMIO_LLEGADA + C.PREMIO_RAPIDEZ * rapidez, 0.0)
        f -= np.where((self.motivo != META) & (self.motivo != TIEMPO), C.CASTIGO_CHOQUE, 0.0)
        f -= C.CASTIGO_CHOQUE * self.reintentos
        return f

    def componentes_aptitud(self):
        largo = self.pista.meta - self.pista.salida
        meta = self.motivo == META
        t_ref = largo / C.V_REFERENCIA
        rapidez = np.minimum(t_ref / np.maximum(self.t_fin, 1e-3), C.RAPIDEZ_MAX)
        if C.APTITUD_ESTRICTA:
            castigo = C.CASTIGO_CHOQUE_ESTRICTO
            limpia = meta & (self.reintentos == 0)
            premio_rapidez = np.where(limpia, C.PREMIO_RAPIDEZ * rapidez, 0.0)
            final_malo = self.motivo != META
        else:
            castigo = C.CASTIGO_CHOQUE
            premio_rapidez = np.where(meta, C.PREMIO_RAPIDEZ * rapidez, 0.0)
            final_malo = (self.motivo != META) & (self.motivo != TIEMPO)
        return {
            "progreso": 100.0 * self.progreso / largo,
            "balanceo": -C.PENAL_BALANCEO * self.balanceo_medio,
            "carril": -C.PENAL_CARRIL * self.carril_medio,
            "invasion": -C.PENAL_INVASION * self.invasion_frac,
            "llegada": np.where(meta, C.PREMIO_LLEGADA, 0.0),
            "rapidez": premio_rapidez,
            "fin_error": -np.where(final_malo, castigo, 0.0),
            "reintentos": -castigo * self.reintentos.astype(float),
        }

    def llegaron(self):
        return self.motivo == META

    def llegadas_limpias(self):
        return (self.motivo == META) & (self.reintentos == 0)

    def distancia_km(self):
        d = self.progreso.copy()
        vivas = self.motivo == VIVO
        if len(self.ids) and vivas.any():
            actual = np.zeros(self.n_total)
            actual[self.ids] = np.clip(self.mejor_x - self.pista.salida, 0, None)
            d = np.where(vivas, actual, d)
        return d / 1000.0

    def _registrar(self):
        n = self.n_total
        ids = self.ids
        v = self.vx * np.cos(self.th) + self.vy * np.sin(self.th)
        vals = {"x": self.px, "v": v, "lat": self.lat, "phi": self.phi, "th": self.th,
                "cmg_sat": self.cmg_sat,
                "v_segura": self._v_segura if self._v_segura is not None else np.full(len(ids), np.nan),
                "en_suelo": self._en_suelo if self._en_suelo is not None else np.ones(len(ids)),
                "invasion": self.lat > 0}
        self.traza["t"].append(np.full(n, self.t + C.DT_CONTROL))
        for k, a in vals.items():
            fila = np.full(n, np.nan)
            fila[ids] = a
            self.traza[k].append(fila)

    def traza_arrays(self):
        if self.traza is None:
            return {}
        return {k: (np.array(v) if v else np.zeros((0, self.n_total))) for k, v in self.traza.items()}
