import math

import numpy as np

import config as C

try:
    import numba
    from numba import njit, prange
    HAY_NUMBA = True
except Exception:
    HAY_NUMBA = False

_UNO = ("px", "py", "th", "vx", "vy", "om", "dir_obj", "dirc", "derrape", "psi", "lat",
        "lastre", "cmg", "cmg_sat", "wobd", "wob", "incld", "incl", "phi", "contra_y",
        "phi_moto", "contra_x", "par_actitud", "tcs", "abs_")
_DOS = ("wx", "wy", "wvx", "wvy", "ws", "comp", "fn", "slip", "desliz", "_mu_i", "carga")
_ENTRADAS = ("acel", "cab", "dirc_cmd", "empujon", "deriva", "v_lat", "v_alabeo", "v_par")
FILAS = {}
for _k in _UNO:
    FILAS[_k] = len(FILAS)
for _k in _DOS:
    FILAS[_k] = len(FILAS)
    FILAS[_k + "#1"] = len(FILAS)
for _k in _ENTRADAS:
    FILAS[_k] = len(FILAS)
FILAS["en_suelo"] = len(FILAS)
NS = len(FILAS)
(PX, PY, TH, VX, VY, OM, DIR_OBJ, DIRC, DERRAPE, PSI, LAT, LASTRE, CMG, CMG_SAT, WOBD, WOB,
 INCLD, INCL, PHI, CONTRA_Y, PHI_MOTO, CONTRA_X, PAR_ACTITUD, TCS, ABS_) = range(len(_UNO))
WX, WY, WVX, WVY, WS, COMP, FN, SLIP, DESLIZ, MU_I, CARGA = (FILAS[k] for k in _DOS)
ACEL, CAB, DIRC_CMD, EMPUJON, DERIVA, V_LAT, V_ALABEO, V_PAR = (FILAS[k] for k in _ENTRADAS)
EN_SUELO = FILAS["en_suelo"]

_NOMBRES_P = (
    "DT", "SUBPASOS", "G", "MASA_CHASIS", "MASA_RUEDA", "INERCIA_CHASIS", "INERCIA_RUEDA",
    "RADIO_RUEDA", "MX0", "MY0", "MX1", "MY1", "SUSP_K", "SUSP_C", "SUSP_KX", "SUSP_CX",
    "RECORRIDO", "EXTENSION", "TOPE_K", "SUSPENSION_REALISTA", "SUSP_C_REBOTE", "TOPE_C",
    "INV_MU_SUSP", "TOPE_RETORNO", "SUSP_PROGRESION", "NEUMATICO_DEFLEX_MAX", "RIN_K", "SUELO_K", "SUELO_C", "V_DESLIZ", "PERDIDA_DESLIZ",
    "DESLIZ_PICO", "LIM_FRIC", "PAR_MOTOR", "POTENCIA", "PAR_FRENO", "FRENO0", "FRENO1",
    "TCS_ACTIVO", "TCS_OBJ", "TCS_RANGO", "ABS_ACTIVO", "ABS_OBJ", "ABS_RANGO",
    "MSC_ACTIVO", "FRENADA_MEJORADA", "PAR_FRENO_MEJORADA", "MSC_FN_TRASERA", "MSC_OM_PICADO",
    "MSC_OM_RANGO", "MSC_TH_PICADO", "MSC_TH_RANGO", "MSC_TH_WHEELIE", "MSC_WHEELIE_RANGO",
    "MSC_MIN_INCL", "MASA_TOTAL", "ARRASTRE", "PAR_CABECEO",
    "CONTRAPESO_ACTIVO", "ATT_NARIZ", "ATT_W", "ATT_Z", "ATT_PAR_MAX", "ATT_CABALLITO",
    "ATT_PICADO", "ATT_ATERRIZAJE", "CONTRA_X_MAX", "CONTRA_VEL", "MASA_LASTRE", "CONTRA_RECUPERA",
    "CONTRA_CEDE", "CONTRA_LASTRE", "CONTRA_COSTO", "CONTRA_Y_MAX", "CONTRA_Y_VEL",
    "CONTRA_INCL_REF", "CONTRA_SALIDA", "EJE_Y0",
    "DIR_MAX", "A_LAT_MAX", "DISTANCIA_EJES", "TAU_DIRECCION", "DIR_VEL", "RECUPERA_DERRAPE",
    "FRICCION_COMBINADA", "PERDIDA_LATERAL", "V_ESTABLE", "V_SIN_EQUILIBRIO",
    "EXP_EQUILIBRIO", "DERIVA_LENTA", "DAMPER_DERIVA", "AMORTIGUADOR_ACTIVO",
    "ALTURA_CG", "GIRO_W", "GIRO_Z", "AMORT_DIRECCION", "AMPLIF_LENTA", "LASTRE_K",
    "LASTRE_D", "LASTRE_MAX", "CMG_K", "CMG_D", "CMG_MAX", "CMG_CAPACIDAD", "CMG_RECENTRADO",
    "CMG_EXP", "INCL_W", "INCL_Z", "VIENTO", "CHARCOS", "MU_AQUA_MIN", "DX", "N_PERFIL",
    "PUNTOS_CONTACTO")
for _i, _k in enumerate(_NOMBRES_P):
    globals()["P_" + _k] = _i
NP = len(_NOMBRES_P)


def parametros(viento=False, charcos=False, n_perfil=1):
    import fisica as F
    from terreno import DX
    try:
        import clima as CL
        mu_aqua = float(CL.MU_AQUA_MIN)
    except Exception:
        mu_aqua = 0.3
    g = lambda k, d=0.0: float(getattr(C, k, d))
    v = {k: g(k) for k in _NOMBRES_P if hasattr(C, k)}
    v.update(SUBPASOS=float(C.SUBPASOS), MX0=float(F._MX[0, 0]), MY0=float(F._MY[0, 0]),
             MX1=float(F._MX[1, 0]), MY1=float(F._MY[1, 0]), LIM_FRIC=float(F._LIM_FRIC),
             FRENO0=float(F._FRENO[0, 0]), FRENO1=float(F._FRENO[1, 0]),
             MASA_TOTAL=float(F._MASA_TOTAL), EJE_Y0=float(C.EJES[0][1]),
             INV_MU_SUSP=float(F._INV_MU_SUSP),
             VIENTO=1.0 if viento else 0.0, CHARCOS=1.0 if charcos else 0.0,
             MU_AQUA_MIN=mu_aqua, DX=float(DX), N_PERFIL=float(n_perfil),
             PUNTOS_CONTACTO=float(C.PUNTOS_CONTACTO))
    for k in ("TCS_ACTIVO", "ABS_ACTIVO", "MSC_ACTIVO", "FRENADA_MEJORADA", "CONTRAPESO_ACTIVO",
              "FRICCION_COMBINADA", "AMORTIGUADOR_ACTIVO", "SUSPENSION_REALISTA"):
        v[k] = 1.0 if getattr(C, k, False) else 0.0
    return np.array([v.get(k, 0.0) for k in _NOMBRES_P], dtype=np.float64)


if HAY_NUMBA:
    _jit = njit(cache=True, nogil=True)
else:
    def _jit(f):
        return f


@_jit
def _clip(x, a, b):
    return a if x < a else (b if x > b else x)


@_jit
def _signo(x):
    return 1.0 if x > 0 else (-1.0 if x < 0 else 0.0)


@_jit
def _indice(x, P, n):
    if not (x == x) or abs(x) > 1e15:
        return 0
    i = int(x * (1.0 / P[P_DX]))
    return 0 if i < 0 else (n - 1 if i > n - 1 else i)


@_jit
def _altura(x, xs, hs, P):
    n = hs.shape[0]
    if not (x == x):
        return x
    if x <= xs[0]:
        return hs[0]
    if x >= xs[n - 1]:
        return hs[n - 1]
    j = int(x / P[P_DX])
    if j > n - 2:
        j = n - 2
    while j > 0 and xs[j] > x:
        j -= 1
    while j < n - 2 and xs[j + 1] <= x:
        j += 1
    if xs[j] == x:
        return hs[j]
    return (hs[j + 1] - hs[j]) / (xs[j + 1] - xs[j]) * (x - xs[j]) + hs[j]


@_jit
def _moto(j, S, xs, hs, mu, rr, kappa, charco, P, offs):
    dt = P[P_DT]
    R = P[P_RADIO_RUEDA]
    G = P[P_G]
    npf = hs.shape[0]
    nmu = mu.shape[0]
    px = S[PX, j]; py = S[PY, j]; th = S[TH, j]; vx = S[VX, j]; vy = S[VY, j]; om = S[OM, j]
    wx0 = S[WX, j]; wx1 = S[WX + 1, j]; wy0 = S[WY, j]; wy1 = S[WY + 1, j]
    wvx0 = S[WVX, j]; wvx1 = S[WVX + 1, j]; wvy0 = S[WVY, j]; wvy1 = S[WVY + 1, j]
    ws0 = S[WS, j]; ws1 = S[WS + 1, j]
    dir_obj = S[DIR_OBJ, j]; dirc = S[DIRC, j]; derrape = S[DERRAPE, j]; psi = S[PSI, j]
    lat = S[LAT, j]; lastre = S[LASTRE, j]; cmg = S[CMG, j]; sat = S[CMG_SAT, j]
    wobd = S[WOBD, j]; wob = S[WOB, j]; incld = S[INCLD, j]; incl = S[INCL, j]
    phi = S[PHI, j]; contra_y = S[CONTRA_Y, j]; phi_moto = S[PHI_MOTO, j]
    contra_x = S[CONTRA_X, j]; par_act = S[PAR_ACTITUD, j]; tcs = S[TCS, j]; abs_ = S[ABS_, j]
    carga0 = 0.0
    carga1 = 0.0
    realista = P[P_SUSPENSION_REALISTA] > 0.5
    acel = S[ACEL, j]; cab = S[CAB, j]; dirc_cmd = S[DIRC_CMD, j]
    empujon = S[EMPUJON, j]; deriva = S[DERIVA, j]
    v_lat = S[V_LAT, j]; v_alabeo = S[V_ALABEO, j]; v_par = S[V_PAR, j]
    comp0 = 0.0; comp1 = 0.0; fn0 = 0.0; fn1 = 0.0; slip0 = 0.0; slip1 = 0.0
    dz0 = 0.0; dz1 = 0.0; mu0 = 0.0; mu1 = 0.0; en_suelo = False
    contrapeso = P[P_CONTRAPESO_ACTIVO] > 0.5
    for _paso in range(int(P[P_SUBPASOS])):
        c = math.cos(th)
        s = math.sin(th)
        rx0 = c * P[P_MX0] - s * P[P_MY0]
        ry0 = s * P[P_MX0] + c * P[P_MY0]
        rx1 = c * P[P_MX1] - s * P[P_MY1]
        ry1 = s * P[P_MX1] + c * P[P_MY1]
        fx0 = 0.0; fy0 = 0.0; fx1 = 0.0; fy1 = 0.0
        for w in range(2):
            if w == 0:
                rx = rx0; ry = ry0; wx = wx0; wy = wy0; wvx = wvx0; wvy = wvy0
            else:
                rx = rx1; ry = ry1; wx = wx1; wy = wy1; wvx = wvx1; wvy = wvy1
            ex = wx - (px + rx)
            ey = wy - (py + ry)
            evx = wvx - (vx - om * ry)
            evy = wvy - (vy + om * rx)
            elx = c * ex + s * ey
            ely = -s * ex + c * ey
            evlx = c * evx + s * evy
            evly = -s * evx + c * evy
            flx = -P[P_SUSP_KX] * elx - P[P_SUSP_CX] * evlx
            if realista:
                tope = max(ely - P[P_RECORRIDO], 0.0)
                if evly > 0:
                    amort = P[P_SUSP_C] + (P[P_TOPE_C] if tope > 0 else 0.0)
                else:
                    amort = P[P_SUSP_C_REBOTE]
                amort = amort / (1.0 + dt * amort * P[P_INV_MU_SUSP])
                xr = max(ely, 0.0) / P[P_RECORRIDO]
                fly = -P[P_SUSP_K] * ely * (1.0 + P[P_SUSP_PROGRESION] * xr * xr) - amort * evly
                fly -= P[P_TOPE_K] * ((1.0 if evly > 0 else P[P_TOPE_RETORNO]) * tope
                                      + min(ely + P[P_EXTENSION], 0.0))
                if w == 0:
                    if abs(fly) > carga0:
                        carga0 = abs(fly)
                elif abs(fly) > carga1:
                    carga1 = abs(fly)
            else:
                fly = -P[P_SUSP_K] * ely - P[P_SUSP_C] * evly
                fly -= P[P_TOPE_K] * (max(ely - P[P_RECORRIDO], 0.0) + min(ely + P[P_EXTENSION], 0.0))
            if w == 0:
                fx0 = c * flx - s * fly; fy0 = s * flx + c * fly; comp0 = ely
            else:
                fx1 = c * flx - s * fly; fy1 = s * flx + c * fly; comp1 = ely
        v_ini = vx * c + vy * s
        nx0 = 0.0; ny0 = 1.0; nx1 = 0.0; ny1 = 1.0; ct0 = False; ct1 = False
        ft0 = 0.0; ft1 = 0.0; i0 = 0; i1 = 0
        for w in range(2):
            if w == 0:
                wx = wx0; wy = wy0; wvx = wvx0; wvy = wvy0; ws = ws0
            else:
                wx = wx1; wy = wy1; wvx = wvx1; wvy = wvy1; ws = ws1
            mejor = -1e300; dyk = 0.0; distk = 0.0; offk = 0.0
            for o in range(offs.shape[0]):
                dy = wy - _altura(wx + offs[o], xs, hs, P)
                dist = math.sqrt(offs[o] * offs[o] + dy * dy)
                pen = R - dist if dy > 0 else R - dy
                if pen > mejor:
                    mejor = pen; dyk = dy; distk = dist; offk = offs[o]
            if dyk > 1e-6:
                nx = -offk / max(distk, 1e-6)
                ny = dyk / max(distk, 1e-6)
            else:
                nx = 0.0
                ny = 1.0
            ct = mejor > 0
            vn = wvx * nx + wvy * ny
            kp = P[P_SUELO_K] * mejor
            if realista and mejor > P[P_NEUMATICO_DEFLEX_MAX]:
                kp += P[P_RIN_K] * (mejor - P[P_NEUMATICO_DEFLEX_MAX])
            fn = max(kp - P[P_SUELO_C] * vn, 0.0) if ct else 0.0
            tx = ny
            ty = -nx
            slip = wvx * tx + wvy * ty - ws * R
            i = _indice(wx, P, nmu)
            mui = mu[i]
            if P[P_CHARCOS] > 0.5:
                prof = charco[i]
                if prof > 0:
                    sv = _clip((abs(v_ini) * 3.6 - (85.0 - 3.0 * prof)) / 25.0, 0.0, 1.0)
                    sv = sv * sv * (3.0 - 2.0 * sv)
                    mui = mui * (1.0 - (1.0 - P[P_MU_AQUA_MIN]) * sv)
            vt = slip + ws * R
            dz = slip / max(abs(vt), 1.0)
            caida = 1.0 - P[P_PERDIDA_DESLIZ] * _clip((abs(dz) - P[P_DESLIZ_PICO]) / 0.6, 0.0, 1.0)
            ft = -_signo(slip) * min(mui * fn * caida * math.tanh(abs(slip) / P[P_V_DESLIZ]),
                                     abs(slip) * P[P_LIM_FRIC])
            if w == 0:
                nx0 = nx; ny0 = ny; ct0 = ct; fn0 = fn; slip0 = slip; i0 = i; mu0 = mui
                dz0 = dz; ft0 = ft
            else:
                nx1 = nx; ny1 = ny; ct1 = ct; fn1 = fn; slip1 = slip; i1 = i; mu1 = mui
                dz1 = dz; ft1 = ft
        gas = max(acel, 0.0)
        freno = max(-acel, 0.0)
        par_max = min(P[P_PAR_MOTOR], P[P_POTENCIA] / max(abs(ws0), 1.0))
        par_motor = gas * par_max
        if P[P_TCS_ACTIVO] > 0.5:
            patina = max(-dz0, 0.0) if ct0 else 0.0
            f_tcs = _clip(1.0 - (patina - P[P_TCS_OBJ]) / P[P_TCS_RANGO], 0.1, 1.0)
            par_motor = par_motor * f_tcs
            tcs = 1.0 - f_tcs if gas > 0.05 else 0.0
        fr0 = freno * P[P_PAR_FRENO] * P[P_FRENO0]
        fr1 = freno * P[P_PAR_FRENO] * P[P_FRENO1]
        aire = not (ct0 or ct1)
        e = 0.0
        e_pred = 0.0
        if contrapeso:
            sobre = max(py - _altura(px, xs, hs, P) + P[P_EJE_Y0] - R, 0.0)
            t_caida = min((vy + math.sqrt(vy * vy + 2 * G * sobre)) / G, 1.5)
            x_ref = px + vx * t_caida if aire else px
            pend = math.atan((_altura(x_ref + 0.8, xs, hs, P) - _altura(x_ref - 0.8, xs, hs, P)) / 1.6)
            e = th - pend
            e_pred = e + 0.15 * om
            sobra = e_pred - P[P_ATT_NARIZ]
            if aire:
                gas_aire = _clip(-(sobra + 0.05) / 0.25, 0.0, 1.0)
                par_motor = max(par_motor * _clip(1.0 - sobra / 0.25, 0.0, 1.0), gas_aire * par_max)
            cab_m = 0.0 if ct1 else max(e_pred - P[P_ATT_CABALLITO], 0.0)
            par_motor = par_motor * _clip(1.0 - cab_m / 0.15, 0.0, 1.0)
            if aire:
                fr0 = _clip((sobra - 0.08) / 0.25, 0.0, 1.0) * 0.6 * P[P_PAR_FRENO]
        if P[P_MSC_ACTIVO] > 0.5 and P[P_FRENADA_MEJORADA] > 0.5:
            c0 = fn0 if ct0 else 0.0
            c1 = fn1 if ct1 else 0.0
            tot = max(c0 + c1, 1.0)
            fr0 = freno * P[P_PAR_FRENO_MEJORADA] * (c0 / tot)
            fr1 = freno * P[P_PAR_FRENO_MEJORADA] * (c1 / tot)
        if P[P_MSC_ACTIVO] > 0.5:
            mu_m = max(max(mu0, mu1), 0.05)
            uso_lat = min(abs(math.tan(phi)) / mu_m, 1.0)
            f_incl = max(math.sqrt(1.0 - uso_lat * uso_lat), P[P_MSC_MIN_INCL])
            f_aw = _clip(1.0 - (th - P[P_MSC_TH_WHEELIE]) / P[P_MSC_WHEELIE_RANGO], 0.0, 1.0)
            if ct0:
                par_motor = par_motor * (f_aw * f_incl)
            f_fn = _clip(fn0 / (P[P_MSC_FN_TRASERA] * P[P_MASA_TOTAL] * G), 0.0, 1.0)
            f_om = _clip(1.0 - (-om - P[P_MSC_OM_PICADO]) / P[P_MSC_OM_RANGO], 0.0, 1.0)
            f_th = _clip(1.0 - (-th - P[P_MSC_TH_PICADO]) / P[P_MSC_TH_RANGO], 0.0, 1.0)
            f_rlp = min(min(f_fn, f_om), f_th) if ct1 else 1.0
            fr0 = fr0 * f_incl
            fr1 = fr1 * f_incl * f_rlp
        if P[P_ABS_ACTIVO] > 0.5:
            b0 = max(dz0, 0.0) if ct0 else 0.0
            b1 = max(dz1, 0.0) if ct1 else 0.0
            fa0 = _clip(1.0 - (b0 - P[P_ABS_OBJ]) / P[P_ABS_RANGO], 0.1, 1.0)
            fa1 = _clip(1.0 - (b1 - P[P_ABS_OBJ]) / P[P_ABS_RANGO], 0.1, 1.0)
            fr0 = fr0 * fa0
            fr1 = fr1 * fa1
            abs_ = 1.0 - min(fa0, fa1) if freno > 0.05 else 0.0
        IR = P[P_INERCIA_RUEDA]
        pf0 = _signo(ws0) * min(fr0, abs(ws0) * IR / dt)
        pf1 = _signo(ws1) * min(fr1, abs(ws1) * IR / dt)
        pr0 = -rr[i0] * fn0 * R * math.tanh(ws0)
        pr1 = -rr[i1] * fn1 * R * math.tanh(ws1)
        ws0 = ws0 + dt * (-pf0 - R * ft0 + pr0 + par_motor) / IR
        ws1 = ws1 + dt * (-pf1 - R * ft1 + pr1) / IR
        mw = P[P_MASA_RUEDA]
        wvx0 = wvx0 + dt * (fx0 + fn0 * nx0 + ft0 * ny0) / mw
        wvy0 = wvy0 + dt * (fy0 + fn0 * ny0 + ft0 * -nx0 - mw * G) / mw
        wvx1 = wvx1 + dt * (fx1 + fn1 * nx1 + ft1 * ny1) / mw
        wvy1 = wvy1 + dt * (fy1 + fn1 * ny1 + ft1 * -nx1 - mw * G) / mw
        wx0 = wx0 + dt * wvx0
        wy0 = wy0 + dt * wvy0
        wx1 = wx1 + dt * wvx1
        wy1 = wy1 + dt * wvy1
        rapidez = math.hypot(vx, vy)
        if P[P_VIENTO] > 0.5:
            vrx = vx - v_par
            fcx = -(fx0 + fx1) - P[P_ARRASTRE] * math.hypot(vrx, vy) * vrx
        else:
            fcx = -(fx0 + fx1) - P[P_ARRASTRE] * rapidez * vx
        fcy = -(fy0 + fy1) - P[P_ARRASTRE] * rapidez * vy - P[P_MASA_CHASIS] * G
        tau = ((rx0 * -fy0 - ry0 * -fx0) + (rx1 * -fy1 - ry1 * -fx1)) + par_motor - (pf0 + pf1) \
            + cab * P[P_PAR_CABECEO]
        if contrapeso:
            I = P[P_INERCIA_CHASIS]
            k = I * P[P_ATT_W] ** 2
            d = 2 * P[P_ATT_Z] * P[P_ATT_W] * I
            cbl = 0.0 if ct1 else max(e_pred - P[P_ATT_CABALLITO], 0.0)
            pic = 0.0 if ct0 else min(e_pred + P[P_ATT_PICADO], 0.0)
            bajando = False
            if aire:
                par = -k * (e - P[P_ATT_NARIZ]) - d * om
            elif cbl > 0 or pic < 0:
                par = -k * (cbl + pic) - d * om
            elif ct0 and not ct1 and om < 0:
                bajando = True
                par = -P[P_ATT_ATERRIZAJE] * d * om
            else:
                par = 0.0
            par = _clip(par, -P[P_ATT_PAR_MAX], P[P_ATT_PAR_MAX])
            x_obj = (-0.7 if (aire or bajando) else _clip(e_pred / P[P_ATT_CABALLITO], -1.0, 1.0)) \
                * P[P_CONTRA_X_MAX]
            pv = P[P_CONTRA_VEL] * dt
            contra_x = contra_x + _clip(x_obj - contra_x, -pv, pv)
            if not aire:
                par = par + -P[P_MASA_LASTRE] * G * contra_x * math.cos(th)
            par_act = par
            tau = tau + par
        vx = vx + dt * fcx / P[P_MASA_CHASIS]
        vy = vy + dt * fcy / P[P_MASA_CHASIS]
        om = om + dt * tau / P[P_INERCIA_CHASIS]
        px = px + dt * vx
        py = py + dt * vy
        th = th + dt * om
        en_suelo = ct0 or ct1
        v = vx * c + vy * s
        tope = min(P[P_DIR_MAX], math.atan(P[P_A_LAT_MAX] * P[P_DISTANCIA_EJES] / max(v * v, 1e-3)))
        dir_obj = dir_obj + (dirc_cmd * tope - dir_obj) * (dt / P[P_TAU_DIRECCION])
        dirc = dirc + _clip(dir_obj - dirc, -P[P_DIR_VEL] * dt, P[P_DIR_VEL] * dt)
        giro = v * math.tan(dirc) / P[P_DISTANCIA_EJES]
        h = _clip(abs(v) / P[P_V_ESTABLE], 0.0, 1.0) ** P[P_CMG_EXP]
        activo = 0.0
        recupera = P[P_RECUPERA_DERRAPE]
        if contrapeso:
            activo = _clip(derrape / 0.5, 0.0, 1.0) if en_suelo else 0.0
            libre = h * (1.0 - sat * sat)
            recupera = recupera + P[P_CONTRA_RECUPERA] * activo * libre
            sg = 1.0 if sat >= 0 else -1.0
            sat = sg * min(abs(sat) + dt * P[P_CONTRA_COSTO] * activo, 1.0)
            giro = giro * (1.0 - P[P_CONTRA_CEDE] * activo)
        pd0 = _clip((abs(dz0) - 0.2) / 0.5, 0.0, 1.0) if ct0 else 0.0
        pd1 = _clip((abs(dz1) - 0.2) / 0.5, 0.0, 1.0) if ct1 else 0.0
        if P[P_FRICCION_COMBINADA] > 0.5:
            a0 = math.sqrt(max((mu0 * fn0) ** 2 - ft0 * ft0, 0.0)) * (1.0 - P[P_PERDIDA_LATERAL] * pd0)
            a1 = math.sqrt(max((mu1 * fn1) ** 2 - ft1 * ft1, 0.0)) * (1.0 - P[P_PERDIDA_LATERAL] * pd1)
            agarre = (a0 + a1) / P[P_MASA_TOTAL]
        else:
            agarre = max(mu0, mu1) * G * (1.0 - P[P_PERDIDA_LATERAL] * max(pd0, pd1))
        a_lat = abs(v * giro)
        exceso = max(a_lat - agarre, 0.0) if en_suelo else 0.0
        derrape = max(derrape + dt * (exceso - recupera), 0.0)
        if exceso > 0:
            giro = _signo(giro) * agarre / max(abs(v), 0.5)
        kap = kappa[_indice(px, P, kappa.shape[0])]
        f = _clip((abs(v) - P[P_V_SIN_EQUILIBRIO]) / (P[P_V_ESTABLE] - P[P_V_SIN_EQUILIBRIO]),
                  0.0, 1.0) ** P[P_EXP_EQUILIBRIO]
        psi = psi + dt * ((giro if en_suelo else 0.0) - v * kap
                          + (1.0 - f) * P[P_DERIVA_LENTA] * deriva
                          * (1.0 - P[P_DAMPER_DERIVA] * P[P_AMORTIGUADOR_ACTIVO]))
        if P[P_VIENTO] > 0.5:
            psi = psi + dt * v_lat / max(abs(v), 3.0)
        lat = lat + dt * v * math.sin(psi)
        caida_g = G / P[P_ALTURA_CG]
        estabiliza = (P[P_GIRO_W] ** 2 + caida_g) * f
        amortigua = 2 * P[P_GIRO_Z] * P[P_GIRO_W] * max(f, 0.1) \
            + P[P_AMORT_DIRECCION] * P[P_AMORTIGUADOR_ACTIVO]
        sacudida = empujon * (1.0 + P[P_AMPLIF_LENTA] * (1.0 - f))
        lastre = _clip(-(P[P_LASTRE_K] * wob + P[P_LASTRE_D] * wobd), -P[P_LASTRE_MAX], P[P_LASTRE_MAX])
        if contrapeso:
            lastre = _clip(lastre - P[P_CONTRA_LASTRE] * activo * _signo(phi),
                           -P[P_LASTRE_MAX], P[P_LASTRE_MAX])
        pedido = -(P[P_CMG_K] * wob + P[P_CMG_D] * wobd)
        cmg = _clip(pedido, -P[P_CMG_MAX] * h, P[P_CMG_MAX] * h) * (1.0 - sat * sat)
        sat = _clip(sat + dt * (cmg / (P[P_CMG_CAPACIDAD] * max(h, 0.05))
                                - P[P_CMG_RECENTRADO] * sat), -1.0, 1.0)
        if en_suelo:
            wobdd = caida_g * math.sin(wob) - estabiliza * wob + sacudida + lastre + cmg
        else:
            wobdd = 0.0
        wobdd = wobdd - amortigua * wobd
        if P[P_VIENTO] > 0.5:
            wobdd = wobdd + v_alabeo
        wobd = wobd + dt * wobdd
        wob = wob + dt * wobd
        objetivo = math.atan(v * giro / G)
        wi = P[P_INCL_W]
        if contrapeso:
            sal = (abs(contra_y) / P[P_CONTRA_Y_MAX]) if abs(objetivo) < abs(incl) else 0.0
            wi = P[P_INCL_W] * (1.0 + P[P_CONTRA_SALIDA] * sal)
        incldd = (wi * wi * (objetivo - incl) if en_suelo else 0.0) - 2 * P[P_INCL_Z] * wi * incld
        incld = incld + dt * incldd
        incl = incl + dt * incld
        phi = incl + wob
        if contrapeso:
            if en_suelo:
                y_obj = -_signo(incl) * P[P_CONTRA_Y_MAX] * _clip(abs(incl) / P[P_CONTRA_INCL_REF], 0.0, 1.0)
            else:
                y_obj = contra_y
            pv = P[P_CONTRA_Y_VEL] * dt
            contra_y = contra_y + _clip(y_obj - contra_y, -pv, pv)
            phi_moto = phi - P[P_MASA_LASTRE] * contra_y / (P[P_MASA_TOTAL] * P[P_ALTURA_CG])
        else:
            phi_moto = phi
    S[PX, j] = px; S[PY, j] = py; S[TH, j] = th; S[VX, j] = vx; S[VY, j] = vy; S[OM, j] = om
    S[WX, j] = wx0; S[WX + 1, j] = wx1; S[WY, j] = wy0; S[WY + 1, j] = wy1
    S[WVX, j] = wvx0; S[WVX + 1, j] = wvx1; S[WVY, j] = wvy0; S[WVY + 1, j] = wvy1
    S[WS, j] = ws0; S[WS + 1, j] = ws1
    S[DIR_OBJ, j] = dir_obj; S[DIRC, j] = dirc; S[DERRAPE, j] = derrape; S[PSI, j] = psi
    S[LAT, j] = lat; S[LASTRE, j] = lastre; S[CMG, j] = cmg; S[CMG_SAT, j] = sat
    S[WOBD, j] = wobd; S[WOB, j] = wob; S[INCLD, j] = incld; S[INCL, j] = incl
    S[PHI, j] = phi; S[CONTRA_Y, j] = contra_y; S[PHI_MOTO, j] = phi_moto
    S[CONTRA_X, j] = contra_x; S[PAR_ACTITUD, j] = par_act; S[TCS, j] = tcs; S[ABS_, j] = abs_
    S[CARGA, j] = max(S[CARGA, j], carga0)
    S[CARGA + 1, j] = max(S[CARGA + 1, j], carga1)
    S[COMP, j] = comp0; S[COMP + 1, j] = comp1; S[FN, j] = fn0; S[FN + 1, j] = fn1
    S[SLIP, j] = slip0; S[SLIP + 1, j] = slip1; S[DESLIZ, j] = dz0; S[DESLIZ + 1, j] = dz1
    S[MU_I, j] = mu0; S[MU_I + 1, j] = mu1
    S[EN_SUELO, j] = 1.0 if en_suelo else 0.0


@_jit
def _red_fila(r, g, x, W1, b1, W2, b2, out):
    a = W1.shape[1]
    o = W1.shape[2]
    q = W2.shape[2]
    for k in range(q):
        out[r, k] = b2[g, k]
    for m in range(o):
        z = b1[g, m]
        for i in range(a):
            z += x[r, i] * W1[g, i, m]
        hm = math.tanh(z)
        for k in range(q):
            out[r, k] += hm * W2[g, m, k]
    for k in range(q):
        out[r, k] = math.tanh(out[r, k])


_cpu = None
_gpu = None
_red_cpu = None
_red_gpu = None


def _compilar_red_cpu():
    global _red_cpu
    if _red_cpu is None:
        @njit(parallel=True, cache=True, nogil=True)
        def red(ids, x, W1, b1, W2, b2, out):
            for r in prange(x.shape[0]):
                _red_fila(r, ids[r], x, W1, b1, W2, b2, out)
        _red_cpu = red
    return _red_cpu


def _compilar_red_gpu():
    global _red_gpu
    if _red_gpu is None:
        from numba import cuda

        @cuda.jit
        def red(ids, x, W1, b1, W2, b2, out):
            r = cuda.grid(1)
            if r < x.shape[0]:
                _red_fila(r, ids[r], x, W1, b1, W2, b2, out)
        _red_gpu = red
    return _red_gpu


def _compilar_cpu():
    global _cpu
    if _cpu is None:
        @njit(parallel=True, cache=True, nogil=True)
        def todas(S, xs, hs, mu, rr, kappa, charco, P, offs):
            for j in prange(S.shape[1]):
                _moto(j, S, xs, hs, mu, rr, kappa, charco, P, offs)

        @njit(cache=True, nogil=True)
        def todas_serie(S, xs, hs, mu, rr, kappa, charco, P, offs):
            for j in range(S.shape[1]):
                _moto(j, S, xs, hs, mu, rr, kappa, charco, P, offs)
        _cpu = (todas, todas_serie)
    return _cpu


def _compilar_gpu():
    global _gpu
    if _gpu is None:
        from numba import cuda

        @cuda.jit
        def kernel(S, xs, hs, mu, rr, kappa, charco, P, offs):
            j = cuda.grid(1)
            if j < S.shape[1]:
                _moto(j, S, xs, hs, mu, rr, kappa, charco, P, offs)
        _gpu = kernel
    return _gpu


class Motor:

    def __init__(self, sim, dispositivo="cpu"):
        self.sim = sim
        self.dispositivo = dispositivo
        p = sim.pista
        self.xs = np.ascontiguousarray(p.xs, dtype=np.float64)
        hs = getattr(p, "hs", None)
        if hs is None or (getattr(p, "superficie", None) == "pavimento"):
            hs = np.zeros(len(self.xs))
        self.hs = np.ascontiguousarray(hs, dtype=np.float64)
        self.mu = np.ascontiguousarray(p.mu, dtype=np.float64)
        self.rr = np.ascontiguousarray(p.rr, dtype=np.float64)
        self.kappa = np.ascontiguousarray(p.kappa, dtype=np.float64)
        ch = getattr(p, "charco", None)
        self.charco = np.ascontiguousarray(ch if ch is not None else np.zeros(1), dtype=np.float64)
        import fisica as F
        self.offs = np.ascontiguousarray(F._OFFS, dtype=np.float64)
        self._S = None
        self._P = None
        self._red_d = None
        if dispositivo == "gpu":
            from numba import cuda
            self._cuda = cuda
            self._d_pista = [cuda.to_device(a) for a in (self.xs, self.hs, self.mu, self.rr,
                                                         self.kappa, self.charco, self.offs)]
            _compilar_gpu()
        else:
            _compilar_cpu()

    def _empacar(self, empujon, deriva):
        sim = self.sim
        n = len(sim.ids)
        if self._S is None or self._S.shape[1] != n:
            self._S = np.zeros((NS, n))
        S = self._S
        for k in _UNO:
            a = getattr(sim, k, None)
            S[FILAS[k]] = 0.0 if a is None or np.ndim(a) == 0 or len(a) != n else a
        for k in _DOS:
            a = getattr(sim, k, None)
            if a is None or np.shape(a) != (2, n):
                S[FILAS[k]] = 0.0
                S[FILAS[k] + 1] = 0.0
            else:
                S[FILAS[k]:FILAS[k] + 2] = a
        S[ACEL] = sim.ctrl[:, 0]
        S[CAB] = sim.ctrl[:, 1]
        S[DIRC_CMD] = sim.ctrl[:, 2]
        S[EMPUJON] = empujon
        S[DERIVA] = deriva
        vi = sim._viento
        if vi is not None:
            S[V_LAT], S[V_ALABEO], S[V_PAR] = vi[0], vi[1], vi[2]
        return S

    def _desempacar(self, S):
        sim = self.sim
        for k in _UNO:
            setattr(sim, k, S[FILAS[k]].copy())
        for k in _DOS:
            setattr(sim, k, S[FILAS[k]:FILAS[k] + 2].copy())
        sim._en_suelo = S[EN_SUELO] > 0.5
        sim._att = None

    def subpasos(self, empujon, deriva):
        sim = self.sim
        S = self._empacar(empujon, deriva)
        efx = sim._efx
        clave = (sim._viento is not None, bool(efx is not None and efx.charcos))
        if self._P is None or self._P[0] != clave:
            P = parametros(viento=clave[0], charcos=clave[1], n_perfil=len(self.hs))
            self._P = (clave, P, self._cuda.to_device(P) if self.dispositivo == "gpu" else None)
        P = self._P[1]
        if self.dispositivo == "gpu":
            cuda = self._cuda
            dS = cuda.to_device(S)
            hilos = 64
            bloques = (S.shape[1] + hilos - 1) // hilos
            _gpu[bloques, hilos](dS, *self._d_pista[:6], self._P[2], self._d_pista[6])
            dS.copy_to_host(S)
        else:
            todas, serie = _cpu
            (todas if S.shape[1] >= 64 else serie)(S, self.xs, self.hs, self.mu, self.rr,
                                                     self.kappa, self.charco, P, self.offs)
        self._desempacar(S)

    def red(self, capas, ids, obs):
        if len(capas) != 2:
            return None
        if self.dispositivo != "gpu" and len(ids) < int(getattr(C, "RED_ACELERADA_MIN", 512)):
            return None
        (W1, b1), (W2, b2) = capas
        x = np.ascontiguousarray(obs, dtype=np.float64)
        ids = np.ascontiguousarray(ids, dtype=np.int64)
        out = np.empty((x.shape[0], W2.shape[2]))
        if self.dispositivo == "gpu":
            cuda = self._cuda
            if self._red_d is None:
                self._red_d = [cuda.to_device(np.ascontiguousarray(a, dtype=np.float64))
                               for a in (W1, b1, W2, b2)]
                _compilar_red_gpu()
            d_out = cuda.device_array_like(out)
            hilos = 64
            _red_gpu[(len(x) + hilos - 1) // hilos, hilos](cuda.to_device(ids), cuda.to_device(x),
                                                            *self._red_d, d_out)
            d_out.copy_to_host(out)
        else:
            if self._red_d is None:
                self._red_d = [np.ascontiguousarray(a, dtype=np.float64) for a in (W1, b1, W2, b2)]
            _compilar_red_cpu()(ids, x, *self._red_d, out)
        return out
