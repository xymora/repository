import math
import os
import sys

import numpy as np

AQUI = os.path.dirname(os.path.abspath(__file__))
if AQUI not in sys.path:
    sys.path.insert(0, AQUI)

import config as C
import fisica as F

try:
    import numba as _nb
    _ERROR = None
except Exception as _e:
    _nb = None
    _ERROR = _e


def _soportado():
    return (not getattr(C, "MSC_ACTIVO", False) and not getattr(C, "FRICCION_COMBINADA", False)
            and getattr(C, "MODELO_LATERAL", "reducido") != "fisico")


def _kernel_py(nsub, dt, dx, xs0, hs, mu, rr, kappa, offs, mx, my, freno_rep, ctrl, empujon, deriva,
               px, py, th, vx, vy, om, wx, wy, wvx, wvy, ws, fn_o, slip_o, comp_o, desliz_o,
               phi, wob, wobd, lastre, cmg, cmg_sat, derrape, dirc, dir_obj, psi, lat, incl, incld,
               tcs, abs_, en_suelo_o, prm, flags):
    (RADIO, SUELO_K, SUELO_C, SUSP_K, SUSP_C, SUSP_KX, SUSP_CX, TOPE_K, RECORRIDO, EXTENSION,
     PERD_DESLIZ, DESLIZ_PICO, V_DESLIZ, LIM_FRIC, PAR_MOTOR, POTENCIA, PAR_FRENO, TCS_OBJ, TCS_RANGO,
     ABS_OBJ, ABS_RANGO, INERCIA_RUEDA, MASA_RUEDA, G, ARRASTRE, MASA_CHASIS, PAR_CABECEO,
     INERCIA_CHASIS, DIR_MAX, A_LAT_MAX, DIST_EJES, TAU_DIR, DIR_VEL, PERD_LATERAL, RECUPERA,
     V_SIN_EQ, V_ESTABLE, EXP_EQ, DERIVA_LENTA, DAMPER, ALTURA_CG, GIRO_W, GIRO_Z, AMORT_DIR,
     AMPLIF_LENTA, LASTRE_K, LASTRE_D, LASTRE_MAX, CMG_K, CMG_D, CMG_MAX, CMG_CAP, CMG_RECENT,
     CMG_EXP, INCL_W, INCL_Z) = prm
    tcs_on, abs_on, amort_on = flags[0], flags[1], flags[2]
    n = px.shape[0]
    nh = hs.shape[0]
    nk = offs.shape[0]
    inv_dx = 1.0 / dx
    fx = np.zeros(2)
    fy = np.zeros(2)
    rxa = np.zeros(2)
    rya = np.zeros(2)
    nxa = np.zeros(2)
    nya = np.zeros(2)
    fna = np.zeros(2)
    fta = np.zeros(2)
    fr = np.zeros(2)
    cont = np.zeros(2, dtype=np.bool_)
    ia = np.zeros(2, dtype=np.int64)
    for j in range(n):
        acel = ctrl[j, 0]
        cab = ctrl[j, 1]
        dcmd = ctrl[j, 2]
        for _s in range(nsub):
            c = math.cos(th[j])
            s = math.sin(th[j])
            for r in range(2):
                rx = c * mx[r] - s * my[r]
                ry = s * mx[r] + c * my[r]
                rxa[r] = rx
                rya[r] = ry
                ex = wx[r, j] - (px[j] + rx)
                ey = wy[r, j] - (py[j] + ry)
                evx = wvx[r, j] - (vx[j] - om[j] * ry)
                evy = wvy[r, j] - (vy[j] + om[j] * rx)
                elx = c * ex + s * ey
                ely = -s * ex + c * ey
                evlx = c * evx + s * evy
                evly = -s * evx + c * evy
                flx = -SUSP_KX * elx - SUSP_CX * evlx
                fly = -SUSP_K * ely - SUSP_C * evly
                fly -= TOPE_K * (max(ely - RECORRIDO, 0.0) + min(ely + EXTENSION, 0.0))
                fx[r] = c * flx - s * fly
                fy[r] = s * flx + c * fly
                comp_o[r, j] = ely
                best = -1e300
                bdy = 0.0
                bd = 0.0
                bk = 0
                for k in range(nk):
                    x = wx[r, j] + offs[k]
                    u = (x - xs0) * inv_dx
                    if not (u > 0.0):
                        h = hs[0]
                    elif u >= nh - 1:
                        h = hs[nh - 1]
                    else:
                        i0 = int(u)
                        f = u - i0
                        h = hs[i0] + (hs[i0 + 1] - hs[i0]) * f
                    dy = wy[r, j] - h
                    d = math.sqrt(offs[k] * offs[k] + dy * dy)
                    pen = RADIO - d if dy > 0 else RADIO - dy
                    if pen > best:
                        best = pen
                        bdy = dy
                        bd = d
                        bk = k
                if bdy > 1e-6:
                    nx = -offs[bk] / max(bd, 1e-6)
                    ny = bdy / max(bd, 1e-6)
                else:
                    nx = 0.0
                    ny = 1.0
                nxa[r] = nx
                nya[r] = ny
                cont[r] = best > 0
                vn = wvx[r, j] * nx + wvy[r, j] * ny
                fnr = max(SUELO_K * best - SUELO_C * vn, 0.0) if best > 0 else 0.0
                tx = ny
                ty = -nx
                slip = wvx[r, j] * tx + wvy[r, j] * ty - ws[r, j] * RADIO
                xi = wx[r, j] * inv_dx
                ii = int(xi) if (xi == xi and abs(xi) < 9e18) else 0
                ii = min(max(ii, 0), nh - 1)
                ia[r] = ii
                vt = slip + ws[r, j] * RADIO
                desl = slip / max(abs(vt), 1.0)
                desliz_o[r, j] = desl
                caida = 1.0 - PERD_DESLIZ * min(max((abs(desl) - DESLIZ_PICO) / 0.6, 0.0), 1.0)
                sg = 1.0 if slip > 0 else (-1.0 if slip < 0 else 0.0)
                ft = -sg * min(mu[ii] * fnr * caida * math.tanh(abs(slip) / V_DESLIZ), abs(slip) * LIM_FRIC)
                fna[r] = fnr
                fta[r] = ft
                fn_o[r, j] = fnr
                slip_o[r, j] = slip
            gas = max(acel, 0.0)
            freno = max(-acel, 0.0)
            par_motor = gas * min(PAR_MOTOR, POTENCIA / max(abs(ws[0, j]), 1.0))
            if tcs_on:
                patina = max(-desliz_o[0, j], 0.0) if cont[0] else 0.0
                f_tcs = min(max(1.0 - (patina - TCS_OBJ) / TCS_RANGO, 0.1), 1.0)
                par_motor = par_motor * f_tcs
                tcs[j] = 1.0 - f_tcs if gas > 0.05 else 0.0
            for r in range(2):
                fr[r] = freno * PAR_FRENO * freno_rep[r]
            if abs_on:
                fmin = 1e300
                for r in range(2):
                    bloqueo = max(desliz_o[r, j], 0.0) if cont[r] else 0.0
                    f_abs = min(max(1.0 - (bloqueo - ABS_OBJ) / ABS_RANGO, 0.1), 1.0)
                    fr[r] = fr[r] * f_abs
                    fmin = min(fmin, f_abs)
                abs_[j] = 1.0 - fmin if freno > 0.05 else 0.0
            pf_sum = 0.0
            for r in range(2):
                w = ws[r, j]
                sw = 1.0 if w > 0 else (-1.0 if w < 0 else 0.0)
                par_freno = sw * min(fr[r], abs(w) * INERCIA_RUEDA / dt)
                pf_sum += par_freno
                par_rodar = -rr[ia[r]] * fna[r] * RADIO * math.tanh(w)
                par = -par_freno - RADIO * fta[r] + par_rodar
                if r == 0:
                    par += par_motor
                ws[r, j] = w + dt * par / INERCIA_RUEDA
            for r in range(2):
                tx = nya[r]
                ty = -nxa[r]
                fwx = fx[r] + fna[r] * nxa[r] + fta[r] * tx
                fwy = fy[r] + fna[r] * nya[r] + fta[r] * ty - MASA_RUEDA * G
                wvx[r, j] = wvx[r, j] + dt * fwx / MASA_RUEDA
                wvy[r, j] = wvy[r, j] + dt * fwy / MASA_RUEDA
                wx[r, j] = wx[r, j] + dt * wvx[r, j]
                wy[r, j] = wy[r, j] + dt * wvy[r, j]
            rapidez = math.hypot(vx[j], vy[j])
            fcx = -(fx[0] + fx[1]) - ARRASTRE * rapidez * vx[j]
            fcy = -(fy[0] + fy[1]) - ARRASTRE * rapidez * vy[j] - MASA_CHASIS * G
            tau = ((rxa[0] * -fy[0] - rya[0] * -fx[0]) + (rxa[1] * -fy[1] - rya[1] * -fx[1])
                   + par_motor - pf_sum + cab * PAR_CABECEO)
            vx[j] = vx[j] + dt * fcx / MASA_CHASIS
            vy[j] = vy[j] + dt * fcy / MASA_CHASIS
            om[j] = om[j] + dt * tau / INERCIA_CHASIS
            px[j] = px[j] + dt * vx[j]
            py[j] = py[j] + dt * vy[j]
            th[j] = th[j] + dt * om[j]
            en_suelo = cont[0] or cont[1]
            en_suelo_o[j] = en_suelo
            v = vx[j] * c + vy[j] * s
            tope = min(DIR_MAX, math.atan(A_LAT_MAX * DIST_EJES / max(v * v, 1e-3)))
            dir_obj[j] = dir_obj[j] + (dcmd * tope - dir_obj[j]) * (dt / TAU_DIR)
            dirc[j] = dirc[j] + min(max(dir_obj[j] - dirc[j], -DIR_VEL * dt), DIR_VEL * dt)
            giro = v * math.tan(dirc[j]) / DIST_EJES
            perdida = 0.0
            mu_max = -1e300
            for r in range(2):
                pr = min(max((abs(desliz_o[r, j]) - 0.2) / 0.5, 0.0), 1.0) if cont[r] else 0.0
                perdida = max(perdida, pr)
                mu_max = max(mu_max, mu[ia[r]])
            agarre = mu_max * G * (1.0 - PERD_LATERAL * perdida)
            a_lat = abs(v * giro)
            exceso = max(a_lat - agarre, 0.0) if en_suelo else 0.0
            derrape[j] = max(derrape[j] + dt * (exceso - RECUPERA), 0.0)
            if exceso > 0:
                sgg = 1.0 if giro > 0 else (-1.0 if giro < 0 else 0.0)
                giro = sgg * agarre / max(abs(v), 0.5)
            xp = px[j] * inv_dx
            ip = int(xp) if (xp == xp and abs(xp) < 9e18) else 0
            ip = min(max(ip, 0), nh - 1)
            kap = kappa[ip]
            fe = min(max((abs(v) - V_SIN_EQ) / (V_ESTABLE - V_SIN_EQ), 0.0), 1.0) ** EXP_EQ
            psi[j] = psi[j] + dt * ((giro if en_suelo else 0.0) - v * kap
                                    + (1.0 - fe) * DERIVA_LENTA * deriva[j]
                                    * (1.0 - DAMPER * amort_on))
            lat[j] = lat[j] + dt * v * math.sin(psi[j])
            caida_g = G / ALTURA_CG
            estabiliza = (GIRO_W ** 2 + caida_g) * fe
            amortigua = 2 * GIRO_Z * GIRO_W * max(fe, 0.1) + AMORT_DIR * amort_on
            sacudida = empujon[j] * (1.0 + AMPLIF_LENTA * (1.0 - fe))
            lastre[j] = min(max(-(LASTRE_K * wob[j] + LASTRE_D * wobd[j]), -LASTRE_MAX), LASTRE_MAX)
            hh = min(max(abs(v) / V_ESTABLE, 0.0), 1.0) ** CMG_EXP
            pedido = -(CMG_K * wob[j] + CMG_D * wobd[j])
            cmg[j] = min(max(pedido, -CMG_MAX * hh), CMG_MAX * hh) * (1.0 - cmg_sat[j] ** 2)
            cmg_sat[j] = min(max(cmg_sat[j] + dt * (cmg[j] / (CMG_CAP * max(hh, 0.05))
                                                    - CMG_RECENT * cmg_sat[j]), -1.0), 1.0)
            if en_suelo:
                wobdd = (caida_g * math.sin(wob[j]) - estabiliza * wob[j] + sacudida + lastre[j] + cmg[j]
                         - amortigua * wobd[j])
            else:
                wobdd = -amortigua * wobd[j]
            wobd[j] = wobd[j] + dt * wobdd
            wob[j] = wob[j] + dt * wobd[j]
            objetivo = math.atan(v * giro / G)
            incldd = (INCL_W ** 2 * (objetivo - incl[j]) if en_suelo else 0.0) - 2 * INCL_Z * INCL_W * incld[j]
            incld[j] = incld[j] + dt * incldd
            incl[j] = incl[j] + dt * incld[j]
            phi[j] = incl[j] + wob[j]


_kernel = None


def _compilar():
    global _kernel
    if _kernel is None:
        _kernel = _nb.njit(cache=True, fastmath=False, nogil=True)(_kernel_py)
    return _kernel


def disponible():
    if _nb is None or not _soportado():
        return False
    try:
        _compilar()
        return True
    except Exception:
        return False


def _parametros():
    lim_fric = 1.0 / (C.DT * (1 / C.MASA_RUEDA + C.RADIO_RUEDA ** 2 / C.INERCIA_RUEDA))
    prm = np.array([
        C.RADIO_RUEDA, C.SUELO_K, C.SUELO_C, C.SUSP_K, C.SUSP_C, C.SUSP_KX, C.SUSP_CX, C.TOPE_K, C.RECORRIDO,
        C.EXTENSION, C.PERDIDA_DESLIZ, C.DESLIZ_PICO, C.V_DESLIZ, lim_fric, C.PAR_MOTOR, C.POTENCIA,
        C.PAR_FRENO, C.TCS_OBJ, C.TCS_RANGO, C.ABS_OBJ, C.ABS_RANGO, C.INERCIA_RUEDA, C.MASA_RUEDA, C.G,
        C.ARRASTRE, C.MASA_CHASIS, C.PAR_CABECEO, C.INERCIA_CHASIS, C.DIR_MAX, C.A_LAT_MAX,
        C.DISTANCIA_EJES, C.TAU_DIRECCION, C.DIR_VEL, C.PERDIDA_LATERAL, C.RECUPERA_DERRAPE,
        C.V_SIN_EQUILIBRIO, C.V_ESTABLE, C.EXP_EQUILIBRIO, C.DERIVA_LENTA, C.DAMPER_DERIVA, C.ALTURA_CG,
        C.GIRO_W, C.GIRO_Z, C.AMORT_DIRECCION, C.AMPLIF_LENTA, C.LASTRE_K, C.LASTRE_D, C.LASTRE_MAX,
        C.CMG_K, C.CMG_D, C.CMG_MAX, C.CMG_CAPACIDAD, C.CMG_RECENTRADO, C.CMG_EXP, C.INCL_W, C.INCL_Z],
        dtype=np.float64)
    return tuple(float(x) for x in prm)


_CAMPOS_KERNEL = ("px", "py", "th", "vx", "vy", "om", "wx", "wy", "wvx", "wvy", "ws", "fn", "slip",
                  "comp", "desliz", "phi", "wob", "wobd", "lastre", "cmg", "cmg_sat", "derrape", "dirc",
                  "dir_obj", "psi", "lat", "incl", "incld", "tcs", "abs_")


class SimuladorNumba(F.Simulador):

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self._sub = 0
        p = self.pista
        self._pista_arr = (float(p.xs[1] - p.xs[0]), float(p.xs[0]),
                           *(np.ascontiguousarray(x, dtype=np.float64) for x in (p.hs, p.mu, p.rr, p.kappa)))
        self._prm = _parametros()
        self._flags = np.array([C.TCS_ACTIVO, C.ABS_ACTIVO, C.AMORTIGUADOR_ACTIVO], dtype=np.float64)
        self._numba = disponible()
        if not self._numba:
            print(f"Aviso: numba no disponible o configuración no soportada ({_ERROR}); se usa numpy.")

    def _fisica(self, empujon, deriva=0.0):
        if not self._numba:
            return super()._fisica(empujon, deriva)
        self._sub = (self._sub + 1) % C.SUBPASOS
        if self._sub != 1 and C.SUBPASOS > 1:
            return
        n = len(self.px)
        for campo in _CAMPOS_KERNEL:
            arr = getattr(self, campo)
            if not (isinstance(arr, np.ndarray) and arr.dtype == np.float64 and arr.flags.c_contiguous):
                setattr(self, campo, np.ascontiguousarray(arr, dtype=np.float64))
        en_suelo = np.zeros(n, dtype=np.bool_)
        dx, xs0, hs, mu, rr, kappa = self._pista_arr
        _compilar()(C.SUBPASOS, C.DT, dx, xs0, hs, mu, rr, kappa, F._OFFS, F._MX[:, 0].copy(),
                    F._MY[:, 0].copy(), F._FRENO[:, 0].copy(),
                    np.ascontiguousarray(self.ctrl, dtype=np.float64),
                    np.broadcast_to(np.asarray(empujon, dtype=np.float64), (n,)).copy(),
                    np.broadcast_to(np.asarray(deriva, dtype=np.float64), (n,)).copy(),
                    self.px, self.py, self.th, self.vx, self.vy, self.om, self.wx, self.wy, self.wvx,
                    self.wvy, self.ws, self.fn, self.slip, self.comp, self.desliz, self.phi, self.wob,
                    self.wobd, self.lastre, self.cmg, self.cmg_sat, self.derrape, self.dirc, self.dir_obj,
                    self.psi, self.lat, self.incl, self.incld, self.tcs, self.abs_, en_suelo,
                    self._prm, self._flags)
        self._en_suelo = en_suelo


def crear_simulador(*a, usar_numba=True, **kw):
    if usar_numba and disponible():
        return SimuladorNumba(*a, **kw)
    return F.Simulador(*a, **kw)


def _correr(clase, pista, pesos, semilla):
    s = clase(pista, pesos, semilla_ruido=semilla)
    while not s.terminado:
        s.paso()
    return s


def validar(n_pistas=12, n_redes=16, niveles=(1, 2, 3, 5), verbose=True):
    import json
    import time
    import red as R
    from terreno import Pista
    rng = np.random.default_rng(7)
    pesos = R.aleatorios(n_redes, C.CAPAS, rng)
    try:
        with open(os.path.join(AQUI, C.ARCHIVO_MEJOR), encoding="utf-8") as f:
            w = np.array(json.load(f)["pesos"], dtype=float)
        pesos[n_redes // 2:] = w + rng.normal(0, 0.03, (n_redes - n_redes // 2, w.shape[0]))
    except (OSError, ValueError, KeyError):
        pass
    pista = Pista(3, 11)
    a, b = F.Simulador(pista, pesos, semilla_ruido=3), SimuladorNumba(pista, pesos, semilla_ruido=3)
    for _ in range(30):
        a.paso()
    for campo in F._CAMPOS:
        setattr(b, campo, getattr(a, campo).copy())
    b.t, b.ruido = a.t, np.random.default_rng(99)
    a.ruido = np.random.default_rng(99)
    a.paso()
    b.paso()
    err = max(float(np.max(np.abs(getattr(a, c) - getattr(b, c)) / (1e-6 + np.abs(getattr(a, c)))))
              for c in ("px", "py", "th", "vx", "vy", "om", "ws", "wob", "lat", "psi") if len(getattr(a, c)))
    apt_np, apt_nb, ok_np, ok_nb = [], [], [], []
    t_np = t_nb = 0.0
    for nivel in niveles:
        for k in range(n_pistas):
            pista = Pista(nivel, 50_000 + 100 * nivel + k)
            t = time.perf_counter()
            s1 = _correr(F.Simulador, pista, pesos, k)
            t_np += time.perf_counter() - t
            t = time.perf_counter()
            s2 = _correr(SimuladorNumba, pista, pesos, k)
            t_nb += time.perf_counter() - t
            apt_np += s1.aptitud().tolist()
            apt_nb += s2.aptitud().tolist()
            ok_np += (s1.motivo == F.META).tolist()
            ok_nb += (s2.motivo == F.META).tolist()
    apt_np, apt_nb = np.array(apt_np), np.array(apt_nb)
    res = {"error_rel_un_paso": err, "episodios": len(apt_np),
           "aptitud_media_numpy": float(apt_np.mean()), "aptitud_media_numba": float(apt_nb.mean()),
           "llegada_numpy": float(np.mean(ok_np)), "llegada_numba": float(np.mean(ok_nb)),
           "identicos_pct": float(100 * np.mean(np.isclose(apt_np, apt_nb, rtol=1e-6, atol=1e-6))),
           "t_numpy_s": round(t_np, 2), "t_numba_s": round(t_nb, 2), "aceleracion": round(t_np / t_nb, 2)}
    try:
        from scipy.stats import ks_2samp, wilcoxon
        res["ks_p"] = float(ks_2samp(apt_np, apt_nb).pvalue)
        d = apt_np - apt_nb
        res["wilcoxon_p"] = float(wilcoxon(d).pvalue) if np.any(d != 0) else 1.0
    except ImportError:
        pass
    if verbose:
        for k, v in res.items():
            print(f"  {k:24s} {v}")
    return res


def benchmark(ns=(1, 80, 320), pasos=60):
    import time
    import red as R
    from terreno import Pista
    pista = Pista(3, 5)
    filas = []
    for n in ns:
        pesos = R.aleatorios(n, C.CAPAS, np.random.default_rng(0))
        t = {}
        for nombre, clase in (("numpy", F.Simulador), ("numba", SimuladorNumba)):
            s = clase(pista, pesos, semilla_ruido=1)
            s.ctrl = np.zeros((n, 3))
            s._fisica(0.0, 0.0)
            t0 = time.perf_counter()
            for _ in range(pasos):
                for _ in range(C.SUBPASOS):
                    s._fisica(0.0, 0.0)
            t[nombre] = (time.perf_counter() - t0) / pasos * 1e6
        filas.append({"n": n, "us_fisica_paso_numpy": round(t["numpy"], 1),
                      "us_fisica_paso_numba": round(t["numba"], 1),
                      "aceleracion": round(t["numpy"] / t["numba"], 1)})
    return filas


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if not disponible():
        sys.exit(f"numba no disponible o configuración no soportada: {_ERROR}")
    print("Física de un paso de control (6 subpasos), µs:")
    for f in benchmark():
        print(f"  N={f['n']:4d}  numpy {f['us_fisica_paso_numpy']:9.1f}  numba {f['us_fisica_paso_numba']:8.1f}"
              f"  ×{f['aceleracion']}")
    print("\nValidación contra numpy (episodios completos):")
    validar()
