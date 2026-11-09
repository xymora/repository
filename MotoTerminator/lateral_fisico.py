import numpy as np

import config as C


def matrices_whipple(p):
    w, c, lam = p["w"], p["c"], p["lam"]
    rR, mR, IRxx, IRyy = p["rR"], p["mR"], p["IRxx"], p["IRyy"]
    xB, zB, mB, IB = p["xB"], p["zB"], p["mB"], p["IB"]
    xH, zH, mH, IH = p["xH"], p["zH"], p["mH"], p["IH"]
    rF, mF, IFxx, IFyy = p["rF"], p["mF"], p["IFxx"], p["IFyy"]
    sl, cl = np.sin(lam), np.cos(lam)
    mT = mR + mB + mH + mF
    xT = (xB * mB + xH * mH + w * mF) / mT
    zT = (-rR * mR + zB * mB + zH * mH - rF * mF) / mT
    ITxx = IRxx + IB[0][0] + IH[0][0] + IFxx + mR * rR ** 2 + mB * zB ** 2 + mH * zH ** 2 + mF * rF ** 2
    ITxz = IB[0][2] + IH[0][2] - mB * xB * zB - mH * xH * zH + mF * w * rF
    ITzz = IRxx + IB[2][2] + IH[2][2] + IFxx + mB * xB ** 2 + mH * xH ** 2 + mF * w ** 2
    mA = mH + mF
    xA = (xH * mH + w * mF) / mA
    zA = (zH * mH - rF * mF) / mA
    IAxx = IH[0][0] + IFxx + mH * (zH - zA) ** 2 + mF * (rF + zA) ** 2
    IAxz = IH[0][2] - mH * (xH - xA) * (zH - zA) + mF * (w - xA) * (rF + zA)
    IAzz = IH[2][2] + IFxx + mH * (xH - xA) ** 2 + mF * (w - xA) ** 2
    uA = (xA - w - c) * cl - zA * sl
    IAll = mA * uA ** 2 + IAxx * sl ** 2 + 2 * IAxz * sl * cl + IAzz * cl ** 2
    IAlx = -mA * uA * zA + IAxx * sl + IAxz * cl
    IAlz = mA * uA * xA + IAxz * sl + IAzz * cl
    mu = c / w * cl
    SR, SF = IRyy / rR, IFyy / rF
    ST = SR + SF
    SA = mA * uA + mu * mT * xT
    M = np.array([[ITxx, IAlx + mu * ITxz], [IAlx + mu * ITxz, IAll + 2 * mu * IAlz + mu ** 2 * ITzz]])
    K0 = np.array([[mT * zT, -SA], [-SA, -SA * sl]])
    K2 = np.array([[0.0, (ST - mT * zT) / w * cl], [0.0, (SA + SF * sl) / w * cl]])
    C1 = np.array([[0.0, mu * ST + SF * cl + ITxz / w * cl - mu * mT * zT],
                   [-(mu * ST + SF * cl), IAlz / w * cl + mu * (SA + ITzz / w * cl)]])
    return M, C1, K0, K2


def params_moto():
    w = C.DISTANCIA_EJES
    m_h = C.LF_MASA_HORQUILLA
    i_rueda_diam = 0.5 * C.INERCIA_RUEDA
    return dict(
        w=w, c=C.LF_TRAIL, lam=C.LF_LANZAMIENTO, g=C.G,
        rR=C.RADIO_RUEDA, mR=C.MASA_RUEDA, IRxx=i_rueda_diam, IRyy=C.INERCIA_RUEDA,
        xB=-C.EJES[0][0], zB=-C.ALTURA_CG, mB=C.MASA_CHASIS - m_h, IB=C.LF_I_CHASIS,
        xH=C.LF_X_HORQUILLA, zH=-C.LF_Z_HORQUILLA, mH=m_h, IH=C.LF_I_HORQUILLA,
        rF=C.RADIO_RUEDA, mF=C.MASA_RUEDA, IFxx=i_rueda_diam, IFyy=C.INERCIA_RUEDA,
    )


def matriz_whipple(mats, v, g=C.G):
    M, C1, K0, K2 = mats
    Mi = np.linalg.inv(M)
    return np.block([[np.zeros((2, 2)), np.eye(2)], [-Mi @ (g * K0 + v * v * K2), -Mi @ (v * C1)]])


def _care_numpy(A, B, Q, R):
    n = A.shape[0]
    Ri = np.linalg.inv(R)
    H = np.block([[A, -B @ Ri @ B.T], [-Q, -A.T]])
    ev, V = np.linalg.eig(H)
    Vs = V[:, ev.real < 0]
    X1, X2 = Vs[:n], Vs[n:]
    P = np.real(X2 @ np.linalg.inv(X1))
    return 0.5 * (P + P.T)


def resolver_care(A, B, Q, R):
    try:
        from scipy.linalg import solve_continuous_are
        return solve_continuous_are(A, B, Q, R)
    except ImportError:
        return _care_numpy(A, B, Q, R)


class ModeloLateral:

    N = 6

    def __init__(self, params=None, v_tabla=None):
        self.p = params or params_moto()
        self.mats = matrices_whipple(self.p)
        self.M, self.C1, self.K0, self.K2 = self.mats
        self.Mi = np.linalg.inv(self.M)
        self.I_roll = float(self.M[0, 0])
        self.cos_l = np.cos(self.p["lam"])
        self.v_tabla = np.arange(0.5, 45.01, 0.5) if v_tabla is None else np.asarray(v_tabla)
        self._construir_tablas()

    def matrices(self, v):
        v = max(float(v), 1e-3)
        g, eta = C.G, C.LF_FRAC_CAMBER
        tau = C.LF_RELAJACION / v
        Cd = np.zeros((2, 2))
        Cd[1, 1] = C.LF_AMORT_DIR
        M, C1, K0, K2, Mi = self.M, self.C1, self.K0, self.K2, self.Mi
        A = np.zeros((6, 6))
        A[0:2, 2:4] = np.eye(2)
        A[2:4, 0:2] = -Mi @ (g * K0 + eta * v * v * K2)
        A[2:4, 2:4] = -Mi @ (eta * v * C1 + Cd)
        A[2:4, 4:6] = Mi
        A[4:6, 0:2] = -(1 - eta) * v * v * K2 / tau
        A[4:6, 2:4] = -(1 - eta) * v * C1 / tau
        A[4:6, 4:6] = -np.eye(2) / tau
        B = np.zeros((6, 2))
        B[2:4, :] = Mi
        return A, B

    def equilibrio(self, v):
        v = max(float(v), 1e-3)
        g, eta = C.G, C.LF_FRAC_CAMBER
        delta = self.p["w"] / self.cos_l
        phi = -(g * self.K0[0, 1] + v * v * self.K2[0, 1]) * delta / (g * self.K0[0, 0])
        q = np.array([phi, delta])
        z = -(1 - eta) * v * v * self.K2 @ q
        x = np.concatenate([q, [0.0, 0.0], z])
        u = (g * self.K0 + v * v * self.K2) @ q
        return x, u

    def _pesos_lqr(self):
        Q = np.diag([1 / 0.03 ** 2, 1 / 0.05 ** 2, 1 / 0.3 ** 2, 1 / 1.0 ** 2,
                     1 / 400.0 ** 2, 1 / 400.0 ** 2])
        R = np.diag([1 / 120.0 ** 2, 1 / C.LF_PAR_DIR_MAX ** 2])
        return Q, R

    def ganancia(self, v):
        A, B = self.matrices(v)
        Q, R = self._pesos_lqr()
        P = resolver_care(A, B, Q, R)
        return np.linalg.solve(R, B.T @ P)

    def _construir_tablas(self):
        nv = len(self.v_tabla)
        self.A_t = np.zeros((nv, 6, 6))
        self.K_t = np.zeros((nv, 2, 6))
        self.xs_t = np.zeros((nv, 6))
        self.us_t = np.zeros((nv, 2))
        for k, v in enumerate(self.v_tabla):
            A, B = self.matrices(v)
            self.A_t[k] = A
            self.K_t[k] = self.ganancia(v)
            self.xs_t[k], self.us_t[k] = self.equilibrio(v)
        self.B = self.matrices(1.0)[1]

    def _interp(self, tabla, v):
        vt = self.v_tabla
        vv = np.clip(np.abs(v), vt[0], vt[-1])
        i = np.minimum(np.searchsorted(vt, vv, side="right") - 1, len(vt) - 2)
        a = ((vv - vt[i]) / (vt[i + 1] - vt[i])).reshape((-1,) + (1,) * (tabla.ndim - 1))
        return tabla[i] * (1 - a) + tabla[i + 1] * a

    def eigen(self, v, lazo="abierto"):
        A, B = self.matrices(v)
        if lazo == "cerrado":
            A = A - B @ self.ganancia(v)
        return np.linalg.eigvals(A)

    def guinada(self, x, v):
        return (v * x[1] + self.p["c"] * x[3]) * self.cos_l / self.p["w"]

    def paso(self, x, kappa_ref, v, t_perturb, lim_roll, dt, en_suelo):
        A = self._interp(self.A_t, v)
        K = self._interp(self.K_t, v)
        xs = self._interp(self.xs_t, v).T * kappa_ref
        us = self._interp(self.us_t, v).T * kappa_ref
        u = us - np.einsum("nij,jn->in", K, x - xs)
        t_roll = lim_roll(u[0])
        t_dir = np.clip(u[1], -C.LF_PAR_DIR_MAX, C.LF_PAR_DIR_MAX)
        f = np.stack([t_roll + t_perturb[0], t_dir + t_perturb[1]])
        Bf = self.B @ f

        def deriv(xx):
            return np.einsum("nij,jn->in", A, xx) + Bf

        k1 = deriv(x)
        k2 = deriv(x + 0.5 * dt * k1)
        k3 = deriv(x + 0.5 * dt * k2)
        k4 = deriv(x + dt * k3)
        xn = x + dt / 6.0 * (k1 + 2 * k2 + 2 * k3 + k4)
        xn[3] = np.clip(xn[3], -C.DIR_VEL, C.DIR_VEL)
        tope = np.abs(xn[1]) >= C.DIR_MAX
        xn[1] = np.clip(xn[1], -C.DIR_MAX, C.DIR_MAX)
        xn[3] = np.where(tope & (np.sign(xn[3]) == np.sign(xn[1])), 0.0, xn[3])
        aire = ~en_suelo
        if aire.any():
            xn[:, aire] = x[:, aire]
            xn[0:2, aire] = x[0:2, aire] + dt * x[2:4, aire]
            xn[4:6, aire] = 0.0
        return xn, {"u_pedido": u, "t_roll": t_roll, "t_dir": t_dir}


_MODELO = None


def modelo():
    global _MODELO
    if _MODELO is None:
        _MODELO = ModeloLateral()
    return _MODELO


def reiniciar_modelo():
    global _MODELO
    _MODELO = None
    return modelo()
