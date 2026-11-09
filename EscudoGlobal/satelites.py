import math

import numpy as np

import config as C
import mundo as M

NOMBRES = ("Sin satélites", "Alerta temprana", "Alerta + seguimiento")
CORTOS = ("NO", "ALERTA", "ALERTA + SEGUIMIENTO")


def _a_modo(v):
    if isinstance(v, bool):
        return 1 if v else 0
    try:
        return max(0, min(2, int(v)))
    except (TypeError, ValueError):
        return C.SAT_DEFECTO


def _libre(S, P, rango=None):
    if not len(S) or not len(P):
        return np.zeros((len(P), len(S)), dtype=bool)
    D = P[:, None, :] - S[None, :, :]
    L2 = np.maximum(np.einsum("ijk,ijk->ij", D, D), 1e-9)
    u = np.clip(-np.einsum("jk,ijk->ij", S, D) / L2, 0.0, 1.0)
    Q = S[None, :, :] + u[:, :, None] * D
    ok = np.linalg.norm(Q, axis=2) >= C.R_TIERRA - 2.0
    if rango is not None:
        ok &= np.sqrt(L2) <= rango
    return ok


class Constelacion:
    def __init__(self, modo):
        self.modo = _a_modo(modo)
        self.ir = []
        if self.modo >= 1:
            for i, lon in enumerate(C.SAT_GEO_LON):
                self.ir.append((f"Alerta GEO-{i + 1}", 0.0, lon, C.SAT_GEO_ALT))
            for i, lon in enumerate(C.SAT_HEO_LON):
                self.ir.append((f"Alerta polar-{i + 1}", C.SAT_HEO_LAT, lon, C.SAT_HEO_ALT))
        self.S_ir = np.array([M.ecef(la, lo, h) for _, la, lo, h in self.ir]) if self.ir else np.zeros((0, 3))
        self.planos = C.SAT_LEO_PLANOS if self.modo >= 2 else 0
        self.por_plano = C.SAT_LEO_POR_PLANO if self.modo >= 2 else 0
        self.n_leo = self.planos * self.por_plano
        r = C.R_TIERRA + C.SAT_LEO_ALT
        self.w = math.sqrt(398600.0 / r ** 3)
        self.r = r
        if self.n_leo:
            p = np.repeat(np.arange(self.planos), self.por_plano)
            q = np.tile(np.arange(self.por_plano), self.planos)
            self.raan = 2 * math.pi * p / self.planos
            self.fase = 2 * math.pi * (q + 0.5 * (p % 2)) / self.por_plano
        else:
            self.raan = self.fase = np.zeros(0)
        self.inc = math.radians(C.SAT_LEO_INC)

    def leo(self, t):
        if not self.n_leo:
            return np.zeros((0, 3))
        u = self.fase + self.w * t
        cu, su = np.cos(u), np.sin(u)
        co, so = np.cos(self.raan), np.sin(self.raan)
        ci, si = math.cos(self.inc), math.sin(self.inc)
        return self.r * np.stack([co * cu - so * su * ci, so * cu + co * su * ci, su * si], axis=1)

    def ver(self, P, t):
        P = np.asarray(P, dtype=float).reshape(-1, 3)
        vi = _libre(self.S_ir, P)
        vl = _libre(self.leo(t), P, C.SAT_LEO_RANGO)
        ir = vi.argmax(axis=1) if vi.shape[1] else np.zeros(len(P), dtype=int)
        lo = vl.argmax(axis=1) if vl.shape[1] else np.zeros(len(P), dtype=int)
        hay_ir = vi.any(axis=1) if vi.shape[1] else np.zeros(len(P), dtype=bool)
        hay_lo = vl.any(axis=1) if vl.shape[1] else np.zeros(len(P), dtype=bool)
        return hay_ir, ir, hay_lo, lo

    def subpuntos(self, t):
        fijos = [(n, la, lo, "ir") for n, la, lo, _ in self.ir]
        moviles = []
        for i, v in enumerate(self.leo(t)):
            la, lo, _ = M.latlon(v)
            moviles.append((f"Seguimiento {i + 1}", la, lo, "leo"))
        return fijos + moviles
