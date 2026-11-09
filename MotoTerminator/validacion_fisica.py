"""Validación de la física de MotoTerminator (MT-Bench).

Uso:
    python validacion_fisica.py                 # ~30-60 s, imprime tablas y guarda JSON
    python validacion_fisica.py --campeona 20   # además: efecto de MSC_ACTIVO sobre la
                                                # aptitud de mejor_moto.json en 20 pistas

Secciones
  A. Benchmark de la bicicleta de Whipple (Meijaard, Papadopoulos, Ruina & Schwab 2007,
     Proc. R. Soc. A 463:1955-1982, doi:10.1098/rspa.2007.1857): matrices M, C1, K0, K2
     calculadas desde los parámetros físicos (Apéndice A) contra los valores publicados,
     eigenvalores y velocidades de weave / capsize. Sirve como implementación de
     referencia del modelo lateral linealizado (roadmap) y como apéndice del paper.
  B. Eigenvalores del lazo lateral ACTUAL (orden reducido, fisica.py) contra la velocidad:
     muestra que es estable en lazo lineal a toda velocidad y que no depende de la
     dirección (no hay contradirección): la caída lenta sale de la saturación.
  C. Frecuencias de suspensión (analíticas, desde config).
  D. Frenada en recta sobre asfalto plano: desaceleración, cabeceo y vuelco, con y sin MSC.
  E. Convergencia temporal: SUBPASOS 6 / 12 / 24.

Resultados en resultados/validacion_fisica.json. No modifica mejor_moto.json,
poblacion.npz ni historial.csv.
"""
import argparse
import contextlib
import json
import os
import sys
import time

import numpy as np

AQUI = os.path.dirname(os.path.abspath(__file__))
if AQUI not in sys.path:
    sys.path.insert(0, AQUI)


def _en_proyecto(ruta):
    if not ruta:
        return ruta
    ruta = os.path.expanduser(str(ruta))
    return ruta if os.path.isabs(ruta) else os.path.join(AQUI, ruta)

import config as C
import fisica as F
import red as R
import terreno as T

PARAMS_BENCHMARK = dict(
    w=1.02, c=0.08, lam=np.pi / 10, g=9.81,
    rR=0.3, mR=2.0, IRxx=0.0603, IRyy=0.12,
    xB=0.3, zB=-0.9, mB=85.0, IB=((9.2, 0.0, 2.4), (0.0, 11.0, 0.0), (2.4, 0.0, 2.8)),
    xH=0.9, zH=-0.7, mH=4.0,
    IH=((0.05892, 0.0, -0.00756), (0.0, 0.06, 0.0), (-0.00756, 0.0, 0.00708)),
    rF=0.35, mF=3.0, IFxx=0.1405, IFyy=0.28,
)
M_PUB = np.array([[80.81722, 2.31941332208709], [2.31941332208709, 0.29784188199686]])
C1_PUB = np.array([[0.0, 33.86641391492494], [-0.85035641456978, 1.68540397397560]])
K0_PUB = np.array([[-80.95, -2.59951685249872], [-2.59951685249872, -0.80329488458618]])
K2_PUB = np.array([[0.0, 76.59734589573222], [0.0, 2.65431523794604]])
V_WEAVE_PUB = 4.292382536341
V_CAPSIZE_PUB = 6.024262015388
EIG_V2_PUB = np.array([-8.674, -3.072, 2.682 - 1.681j, 2.682 + 1.681j])


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


def matriz_estado(M, C1, K0, K2, v, g=9.81):
    Mi = np.linalg.inv(M)
    return np.block([[np.zeros((2, 2)), np.eye(2)], [-Mi @ (g * K0 + v * v * K2), -Mi @ (v * C1)]])


def eigen_whipple(mats, v):
    return np.linalg.eigvals(matriz_estado(*mats, v))


def velocidades_criticas(mats):
    from scipy.optimize import brentq

    def weave(v):
        e = eigen_whipple(mats, v)
        return e[np.abs(e.imag) > 1e-9].real.max()

    def capsize(v):
        e = eigen_whipple(mats, v)
        return e[np.abs(e.imag) <= 1e-9].real.max()

    return brentq(weave, 3.0, 5.0, xtol=1e-13), brentq(capsize, 5.0, 7.0, xtol=1e-13)


def seccion_a():
    mats = matrices_whipple(PARAMS_BENCHMARK)
    dif = max(float(np.abs(a - b).max()) for a, b in zip(mats, (M_PUB, C1_PUB, K0_PUB, K2_PUB)))
    vw, vc = velocidades_criticas(mats)
    e2 = np.sort_complex(eigen_whipple(mats, 2.0))
    err_e2 = float(np.abs(e2 - np.sort_complex(EIG_V2_PUB)).max())
    barrido = []
    for v in np.arange(0.0, 10.01, 1.0):
        e = eigen_whipple(mats, v)
        barrido.append({"v": float(v), "re_max": float(e.real.max()),
                        "eig": [[float(z.real), float(z.imag)] for z in np.sort_complex(e)]})
    return {"max_dif_matrices_vs_publicadas": dif,
            "v_weave": vw, "v_capsize": vc,
            "err_v_weave": abs(vw - V_WEAVE_PUB), "err_v_capsize": abs(vc - V_CAPSIZE_PUB),
            "eig_v2": [[float(z.real), float(z.imag)] for z in e2], "err_eig_v2_3dec": err_e2,
            "barrido": barrido}


def seccion_b():
    g_h = C.G / C.ALTURA_CG
    filas = []
    for kmh in (5, 10, 15, 20, 25, 30, 50, 80, 120):
        v = kmh / 3.6
        f = float(F.estabilidad(v))
        h = min(v / C.V_ESTABLE, 1.0) ** C.CMG_EXP
        K = -g_h + (C.GIRO_W ** 2 + g_h) * f + C.LASTRE_K + C.CMG_K
        D = 2 * C.GIRO_Z * C.GIRO_W * max(f, 0.1) + C.AMORT_DIRECCION * C.AMORTIGUADOR_ACTIVO \
            + C.LASTRE_D + C.CMG_D
        e = np.roots([1.0, D, K])
        filas.append({"kmh": kmh, "f_estab": f, "h_cmg": h, "cmg_max_rad_s2": C.CMG_MAX * h,
                      "eig": [[float(z.real), float(z.imag)] for z in e],
                      "re_max": float(np.max(e.real))})
    return {"V_CRITICA_kmh": C.V_CRITICA * 3.6, "filas": filas,
            "nota": "lazo lineal estable a toda velocidad; independiente de la dirección; "
                    "la caída a baja velocidad sale de la saturación (LASTRE_MAX, CMG_MAX·h)"}


def seccion_c():
    m_eje = C.MASA_CHASIS / 2
    k_serie = 1 / (1 / C.SUSP_K + 1 / C.SUELO_K)
    f_susp = np.sqrt(k_serie / m_eje) / (2 * np.pi)
    zeta = C.SUSP_C / (2 * np.sqrt(k_serie * m_eje))
    f_rueda = np.sqrt((C.SUSP_K + C.SUELO_K) / C.MASA_RUEDA) / (2 * np.pi)
    w_cont = np.sqrt((C.SUELO_K + C.TOPE_K) / C.MASA_RUEDA)
    return {"f_suspendida_Hz": float(f_susp), "zeta_suspendida": float(zeta),
            "f_no_suspendida_Hz": float(f_rueda), "omega_dt_contacto_con_tope": float(w_cont * C.DT)}


@contextlib.contextmanager
def subpasos(k):
    viejo = (C.SUBPASOS, C.DT, F._LIM_FRIC)
    C.SUBPASOS = k
    C.DT = C.DT_CONTROL / k
    F._LIM_FRIC = 1.0 / (C.DT * (1 / C.MASA_RUEDA + C.RADIO_RUEDA ** 2 / C.INERCIA_RUEDA))
    try:
        yield
    finally:
        C.SUBPASOS, C.DT, F._LIM_FRIC = viejo


@contextlib.contextmanager
def bandera(nombre, valor):
    viejo = getattr(C, nombre)
    setattr(C, nombre, valor)
    try:
        yield
    finally:
        setattr(C, nombre, viejo)


def pista_plana(mu=1.0):
    p = T.Pista(1, 0)
    p.hs[:] = 0.0
    p.kappa[:] = 0.0
    p.kmax[:] = 0.0
    p.mat[:] = 0
    p.mu = np.full(len(p.xs), mu)
    p.mu_min = p.mu.copy()
    p.rr = T.RR[p.mat]
    p.rugo = np.zeros(len(p.xs))
    return p


def maniobra(ctrl_fn, t_total, v0=20.0, t_asentar=1.0, mu=1.0):
    p = pista_plana(mu)
    s = F.Simulador(p, np.zeros((1, R.n_parametros(C.CAPAS))))
    s.vx[:] = v0
    s.wvx[:] = v0
    s.ws[:] = v0 / C.RADIO_RUEDA
    n = int(round(t_total / C.DT))
    out = np.zeros((n, 6))
    for k in range(n):
        t = k * C.DT
        s.ctrl = np.array([ctrl_fn(t)], dtype=float)
        s._fisica(0.0, 0.0)
        out[k] = (t, s.px[0], s.vx[0], s.th[0], s.fn[0, 0], s.fn[1, 0])
    return out


def frenada(nivel, t_asentar=1.0, v0=20.0):
    o = maniobra(lambda t: (0.0, 0.0, 0.0) if t < t_asentar else (-nivel, 0.0, 0.0), 8.0, v0)
    k0 = int(np.searchsorted(o[:, 0], t_asentar))
    x0, v1 = o[k0, 1], o[k0, 2]
    volteo = bool(np.any(np.abs(o[:, 3]) > C.CABECEO_MAX))
    parado = np.flatnonzero(o[k0:, 2] < 0.3)
    if volteo or len(parado) == 0:
        dist, decel = float("nan"), float("nan")
    else:
        ks = k0 + parado[0]
        dist = float(o[ks, 1] - x0)
        decel = float(v1 ** 2 / (2 * dist))
    return {"freno": nivel, "v_inicial": float(v1), "distancia_m": dist, "decel_m_s2": decel,
            "cabeceo_max_grados": float(np.degrees(np.abs(o[:, 3]).max())),
            "fn_trasera_min_N": float(o[k0:, 4].min()), "se_volteo": volteo}


def seccion_d():
    filas = []
    for msc in (False, True):
        with bandera("MSC_ACTIVO", msc):
            for nivel in (0.3, 0.5, 0.7, 0.85, 1.0):
                r = frenada(nivel)
                r["MSC"] = msc
                filas.append(r)
    h_cg = -C.EJES[1][1] + C.RADIO_RUEDA
    b = C.EJES[1][0]
    return {"filas": filas, "decel_vuelco_teorica_m_s2": C.G * b / h_cg,
            "nota": "decel teórica de vuelco con CG en el origen del chasís (aprox.)"}


def _aptitud_campeona(pesos, nivel=1, semilla=0):
    sim = F.Simulador(T.Pista(nivel, semilla), pesos, semilla_ruido=semilla)
    while not sim.terminado:
        sim.paso()
    return float(sim.aptitud()[0]), int(sim.motivo[0]), float(sim.t_fin[0])


def seccion_e(pesos):
    filas = []
    for k in (6, 12, 24):
        with subpasos(k):
            acel = maniobra(lambda t: (1.0, 0.0, 0.0), 4.0, v0=9.0)
            fr = frenada(0.5)
            fila = {"SUBPASOS": k, "acel_v_final": float(acel[-1, 2]), "acel_x_final": float(acel[-1, 1]),
                    "frenada05_dist": fr["distancia_m"], "frenada05_decel": fr["decel_m_s2"]}
            if pesos is not None:
                apt, mot, tf = _aptitud_campeona(pesos)
                fila.update({"campeona_aptitud_n1s0": apt, "campeona_motivo": F.MOTIVOS[mot],
                             "campeona_t_fin": tf})
            filas.append(fila)
    ref = filas[-1]
    for f in filas:
        f["err_rel_acel_v_vs24"] = abs(f["acel_v_final"] - ref["acel_v_final"]) / ref["acel_v_final"]
        f["err_rel_frenada_vs24"] = abs(f["frenada05_dist"] - ref["frenada05_dist"]) / ref["frenada05_dist"]
    return {"filas": filas}


def efecto_msc_campeona(pesos, n_pistas=20, niveles=(1, 2, 3)):
    res = {}
    for msc in (False, True):
        with bandera("MSC_ACTIVO", msc):
            apts, llegadas, limpias = [], 0, 0
            for j in range(n_pistas):
                nivel = niveles[j % len(niveles)]
                semilla = 2 ** 31 + 1000 * nivel + j
                sim = F.Simulador(T.Pista(nivel, semilla), pesos, semilla_ruido=semilla)
                while not sim.terminado:
                    sim.paso()
                apts.append(float(sim.aptitud()[0]))
                llegadas += int(sim.llegaron()[0])
                limpias += int(sim.llegadas_limpias()[0])
            res["MSC_on" if msc else "MSC_off"] = {
                "aptitud_media": float(np.mean(apts)), "aptitud_de": float(np.std(apts)),
                "llegadas": llegadas, "llegadas_limpias": limpias, "n": n_pistas,
                "aptitudes": apts}
    d = np.array(res["MSC_on"]["aptitudes"]) - np.array(res["MSC_off"]["aptitudes"])
    res["diferencia_pareada_media"] = float(d.mean())
    res["pistas_iguales"] = int(np.sum(np.abs(d) < 1e-9))
    return res


def cargar_campeona():
    ruta = os.path.join(AQUI, C.ARCHIVO_MEJOR)
    try:
        with open(ruta, encoding="utf-8") as fh:
            d = json.load(fh)
        if tuple(d.get("capas", ())) == tuple(C.CAPAS):
            return np.array(d["pesos"], dtype=float)[None]
    except (OSError, ValueError, KeyError):
        pass
    return None


def _imprimir(res):
    a = res["A_meijaard"]
    print("\nA. Benchmark Whipple (Meijaard et al. 2007)")
    print(f"   max |matrices calculadas − publicadas| = {a['max_dif_matrices_vs_publicadas']:.2e}")
    print(f"   v_weave   = {a['v_weave']:.10f} m/s (pub. {V_WEAVE_PUB}, err {a['err_v_weave']:.1e})")
    print(f"   v_capsize = {a['v_capsize']:.10f} m/s (pub. {V_CAPSIZE_PUB}, err {a['err_v_capsize']:.1e})")
    print("   eig(v=2) = " + ", ".join(f"{r:+.4f}{i:+.4f}j" for r, i in a["eig_v2"]))
    b = res["B_lazo_actual"]
    print(f"\nB. Lazo lateral actual (orden reducido), V_CRITICA = {b['V_CRITICA_kmh']:.1f} km/h")
    print("   km/h  f(v)   h_cmg  Re(eig) max  eigenvalores")
    for f in b["filas"]:
        ev = ", ".join(f"{r:+.2f}{i:+.2f}j" for r, i in f["eig"])
        print(f"   {f['kmh']:4d}  {f['f_estab']:.2f}   {f['h_cmg']:.2f}   {f['re_max']:+8.2f}    {ev}")
    c = res["C_suspension"]
    print(f"\nC. Suspensión: {c['f_suspendida_Hz']:.2f} Hz (ζ={c['zeta_suspendida']:.2f}), "
          f"rueda {c['f_no_suspendida_Hz']:.1f} Hz, ω·dt contacto+tope = {c['omega_dt_contacto_con_tope']:.2f}")
    d = res["D_frenada"]
    print(f"\nD. Frenada desde ~20 m/s en asfalto plano (vuelco teórico ≈ {d['decel_vuelco_teorica_m_s2']:.1f} m/s²)")
    print("   MSC   freno  dist[m]  decel[m/s²]  cabeceo máx[°]  Fn tras. mín[N]  ¿volteo?")
    for f in d["filas"]:
        print(f"   {'sí' if f['MSC'] else 'no':3s}   {f['freno']:.2f}   {f['distancia_m']:7.2f}  "
              f"{f['decel_m_s2']:9.2f}    {f['cabeceo_max_grados']:10.1f}    {f['fn_trasera_min_N']:10.0f}     "
              f"{'SÍ' if f['se_volteo'] else 'no'}")
    e = res["E_convergencia"]
    print("\nE. Convergencia temporal")
    for f in e["filas"]:
        extra = f"  campeona n1/s0: {f['campeona_aptitud_n1s0']:.2f}" if "campeona_aptitud_n1s0" in f else ""
        print(f"   SUBPASOS={f['SUBPASOS']:2d}  acel v={f['acel_v_final']:.3f} (err {f['err_rel_acel_v_vs24']:.1e})"
              f"  frenada 0.5: {f['frenada05_dist']:.2f} m (err {f['err_rel_frenada_vs24']:.1e}){extra}")
    if "F_msc_campeona" in res:
        m = res["F_msc_campeona"]
        print("\nF. Efecto de MSC_ACTIVO sobre mejor_moto.json (pistas de prueba reservadas)")
        for k in ("MSC_off", "MSC_on"):
            r = m[k]
            print(f"   {k}: aptitud {r['aptitud_media']:.2f} ± {r['aptitud_de']:.2f}, "
                  f"llegadas {r['llegadas']}/{r['n']}, limpias {r['llegadas_limpias']}/{r['n']}")
        print(f"   diferencia pareada media = {m['diferencia_pareada_media']:+.3f}; "
              f"pistas idénticas: {m['pistas_iguales']}/{m['MSC_on']['n']}")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--campeona", type=int, default=0,
                    help="N pistas para medir el efecto de MSC sobre mejor_moto.json (0 = no)")
    ap.add_argument("--salida", default=os.path.join(AQUI, "resultados", "validacion_fisica.json"))
    args = ap.parse_args(argv)
    args.salida = _en_proyecto(args.salida)
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    t0 = time.time()
    pesos = cargar_campeona()
    res = {"A_meijaard": seccion_a(), "B_lazo_actual": seccion_b(), "C_suspension": seccion_c(),
           "D_frenada": seccion_d(), "E_convergencia": seccion_e(pesos)}
    if args.campeona and pesos is not None:
        res["F_msc_campeona"] = efecto_msc_campeona(pesos, args.campeona)
    res["segundos"] = time.time() - t0
    _imprimir(res)
    os.makedirs(os.path.dirname(args.salida), exist_ok=True)
    with open(args.salida, "w", encoding="utf-8") as fh:
        json.dump(res, fh, indent=1, ensure_ascii=False)
    print(f"\nGuardado en {args.salida} ({res['segundos']:.1f} s)")
    return res


if __name__ == "__main__":
    main()
