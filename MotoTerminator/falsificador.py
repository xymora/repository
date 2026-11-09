import argparse
import datetime as _dt
import json
import os
import sys

import numpy as np

import config as C
import evaluacion as E
import sensores as S
import stl as STL
from terreno import Pista

NOMBRES = ("sesgo_lat", "log_mu", "rafaga", "sesgo_psi")
SIGMA0 = np.array([0.15, 0.10, 1.0, 0.01])
BASE_FALS = 2 ** 31 + 500_000
DUR_RAFAGA = 0.5


def semilla_pista_fals(nivel, j):
    return BASE_FALS + 1000 * int(nivel) + int(j)


def _log_normal(x, mu, sigma):
    return np.sum(-0.5 * ((x - mu) / sigma) ** 2 - np.log(sigma) - 0.5 * np.log(2 * np.pi), axis=1)


def _correr_escenarios(pesos_o_ctrl, pista, theta, t0, requisitos, semilla_ruido):
    n = len(theta)
    filtro = S.FiltroSensores(semilla=0, sesgo_lat_m=theta[:, 0], sesgo_psi_rad=theta[:, 3],
                              mu_por_moto=np.exp(theta[:, 1]),
                              perturbador=S.RafagaLateral(theta[:, 2], t0, DUR_RAFAGA))
    kw = dict(max_reintentos=0, ruido_por_moto=False, filtro_obs=filtro, registrar=True)
    if callable(pesos_o_ctrl):
        sim = E.crear_simulador(pista, None, semilla_ruido, controlador=pesos_o_ctrl, n=n, **kw)
    else:
        w = np.asarray(pesos_o_ctrl, dtype=float)
        sim = E.crear_simulador(pista, np.repeat(w[None], n, 0), semilla_ruido, **kw)
    E._correr(sim)
    res = STL.evaluar_requisitos(E.obtener_traza(sim), pista)
    score = STL.robustez_normalizada(res, list(requisitos))
    limpias = np.asarray(sim.motivo) == E.F.META
    score = np.where(limpias, score, np.minimum(score, -1e-3))
    return score, np.asarray(sim.motivo).copy(), limpias


def falsificar(pesos_o_controlador, nivel=1, pistas=1, poblacion=64, iteraciones=5, elite=0.2,
               n_is=128, requisitos=("R1", "R2", "R3", "R6", "R9"), semilla=0,
               guardar=True, dir_resultados=None, verbose=True):
    rng = np.random.default_rng(semilla)
    salida, catalogo = [], []
    for j in range(pistas):
        sp = semilla_pista_fals(nivel, j)
        pista = Pista(nivel, sp)
        sr = sp + 99991
        mu, sig = np.zeros(4), SIGMA0.copy()
        t_hi = max(2.5, 0.6 * pista.tiempo_max)
        historia, vistos = [], []
        for it in range(iteraciones):
            th = mu + sig * rng.normal(size=(poblacion, 4))
            t0 = rng.uniform(2.0, t_hi, poblacion)
            score, motivo, limp = _correr_escenarios(pesos_o_controlador, pista, th, t0, requisitos, sr)
            if it == 0:
                k_mc = int((score < 0).sum())
                mc = {"k": k_mc, "n": poblacion, "p": k_mc / poblacion,
                      "ic": E.clopper_pearson(k_mc, poblacion)}
            for i in range(poblacion):
                vistos.append((float(score[i]), th[i].copy(), float(t0[i]), int(motivo[i])))
            k = max(2, int(np.ceil(elite * poblacion)))
            el = np.argsort(score)[:k]
            mu = 0.7 * th[el].mean(0) + 0.3 * mu
            sig = np.maximum(0.7 * th[el].std(0) + 0.3 * sig, 0.05 * SIGMA0)
            historia.append({"iter": it, "score_min": float(score.min()),
                             "score_mediana": float(np.median(score)),
                             "no_llegaron": int((~limp).sum()), "violaciones_stl": int((score < 0).sum()),
                             "n": poblacion,
                             "mu": mu.tolist(), "sigma": sig.tolist()})
            if verbose:
                print(f"  pista {sp} iter {it + 1}/{iteraciones}: rho_min {score.min():+.3f}, "
                      f"violan STL {int((score < 0).sum())}/{poblacion}, no llegaron {int((~limp).sum())}", flush=True)
        p_is = ee = nf = p_sn = ess = None
        if n_is:
            th = mu + sig * rng.normal(size=(n_is, 4))
            t0 = rng.uniform(2.0, t_hi, n_is)
            score, motivo, limp = _correr_escenarios(pesos_o_controlador, pista, th, t0, requisitos, sr)
            falla = (score < 0).astype(float)
            logw = _log_normal(th, 0.0, SIGMA0) - _log_normal(th, mu, sig)
            w = np.exp(logw)
            est = falla * w
            p_is, ee, nf = float(est.mean()), float(est.std(ddof=1) / np.sqrt(n_is)), int(falla.sum())
            p_sn = float(est.sum() / max(w.sum(), 1e-300))
            ess = float(w.sum() ** 2 / max((w ** 2).sum(), 1e-300))
            for i in range(n_is):
                vistos.append((float(score[i]), th[i].copy(), float(t0[i]), int(motivo[i])))
            if verbose:
                print(f"  IS: P(falla | nominal) ~ {p_is:.2e} +/- {ee:.1e} (EE); autonormalizado "
                      f"{p_sn:.2e}, ESS {ess:.0f}; {nf}/{n_is} violaciones bajo q", flush=True)
        if verbose:
            print(f"  MC nominal (iter 1): {mc['k']}/{mc['n']} violaciones, IC95 "
                  f"[{mc['ic'][0]:.3f}, {mc['ic'][1]:.3f}]", flush=True)
        vistos.sort(key=lambda v: v[0])
        peores = []
        for s, th_i, t0_i, m in vistos:
            if s >= 0 or len(peores) >= 20:
                break
            esc = {"nivel": nivel, "semilla_pista": sp, "semilla_ruido": sr,
                   "theta": dict(zip(NOMBRES, map(float, th_i))), "t_rafaga": t0_i,
                   "dur_rafaga": DUR_RAFAGA, "score": s, "motivo": m,
                   "motivo_texto": E._texto_motivo(m),
                   "z_nominal": float(np.sqrt(np.sum((th_i / SIGMA0) ** 2)))}
            peores.append(esc)
        catalogo += peores
        salida.append({"semilla_pista": sp, "mu_final": dict(zip(NOMBRES, mu.tolist())),
                       "sigma_final": dict(zip(NOMBRES, sig.tolist())), "historia": historia,
                       "p_falla_is": p_is, "ee_is": ee, "p_falla_is_autonorm": p_sn, "ess_is": ess,
                       "n_fallas_is": nf, "n_is": n_is, "mc_nominal": mc,
                       "peores": peores})
    out = {"meta": {"fecha": _dt.datetime.now().isoformat(timespec="seconds"), "nivel": nivel,
                    "poblacion": poblacion, "iteraciones": iteraciones, "requisitos": list(requisitos),
                    "sigma0": dict(zip(NOMBRES, SIGMA0.tolist())),
                    "hash_pesos": None if callable(pesos_o_controlador) else E.hash_pesos(pesos_o_controlador)},
           "pistas": salida, "catalogo": catalogo}
    if guardar:
        d = E.en_proyecto(dir_resultados) or E.DIR_RESULTADOS
        os.makedirs(d, exist_ok=True)
        ruta = os.path.join(d, f"escenarios_criticos_n{nivel}_{_dt.datetime.now():%Y%m%d_%H%M%S}.json")
        with open(ruta, "w", encoding="utf-8") as f:
            json.dump(E._json_seguro(out), f, ensure_ascii=False, indent=1)
        out["archivo"] = ruta
    return out


def reproducir(escenario, pesos_o_controlador):
    pista = Pista(escenario["nivel"], escenario["semilla_pista"])
    th = np.array([[escenario["theta"][k] for k in NOMBRES]])
    score, motivo, limp = _correr_escenarios(pesos_o_controlador, pista, th,
                                             np.array([escenario["t_rafaga"]]),
                                             ("R1", "R2", "R3", "R6", "R9"),
                                             escenario["semilla_ruido"])
    return {"score": float(score[0]), "motivo": int(motivo[0]), "llego_limpio": bool(limp[0])}


def main(argv=None):
    ap = argparse.ArgumentParser(description="Falsificación adversarial por entropía cruzada")
    ap.add_argument("--nivel", type=int, default=1)
    ap.add_argument("--pistas", type=int, default=1)
    ap.add_argument("--poblacion", type=int, default=64)
    ap.add_argument("--iteraciones", type=int, default=5)
    ap.add_argument("--n-is", type=int, default=128)
    ap.add_argument("--pesos", default=None)
    ap.add_argument("--semilla", type=int, default=0)
    a = ap.parse_args(argv)
    pesos, _ = E.cargar_pesos("terreno", a.pesos)
    out = falsificar(pesos, a.nivel, a.pistas, a.poblacion, a.iteraciones, n_is=a.n_is, semilla=a.semilla)
    print("Catalogo:", out.get("archivo"), "·", len(out["catalogo"]), "escenarios criticos")
    return out


if __name__ == "__main__":
    main(sys.argv[1:])
