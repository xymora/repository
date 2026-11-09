import argparse
import csv
import datetime as _dt
import json
import os
import sys

import evaluacion as E

COLUMNAS = ("modo", "nivel", "n", "llegada_limpia_pct", "ic_lo", "ic_hi", "llegada_reintentos_pct",
            "fallas", "km", "fallas_km", "fallas_km_lo", "fallas_km_hi", "p_falla_max", "vel_kmh",
            "tlc_p05_s", "falla_principal", "stl_violaciones", "hash_pesos")


def tabla_kpis(evaluacion):
    ev = evaluacion
    if isinstance(ev, str):
        with open(E.en_proyecto(ev), encoding="utf-8") as f:
            ev = json.load(f)
    m = ev["meta"]
    filas = []
    for nivel, s in ev["niveles"].items():
        ll, fk = s["llegada_limpia"], s["fallas_por_km"]
        c = s.get("llegada_con_reintentos")
        n = s["n_episodios"]
        tax = s.get("taxonomia_motivo") or {}
        filas.append({
            "modo": m.get("modo"), "nivel": int(nivel), "n": n,
            "llegada_limpia_pct": 100 * ll["tasa"], "ic_lo": 100 * ll["ic"][0], "ic_hi": 100 * ll["ic"][1],
            "llegada_reintentos_pct": 100 * c["tasa"] if c else None,
            "fallas": s["fallas"], "km": s["km"], "fallas_km": fk["tasa"],
            "fallas_km_lo": fk["ic"][0], "fallas_km_hi": fk["ic"][1],
            "p_falla_max": E.clopper_pearson(s["fallas"], n)[1],
            "vel_kmh": s.get("vel_media_kmh"),
            "tlc_p05_s": (s.get("tlc_min_s") or {}).get("p05"),
            "falla_principal": next(iter(tax), ""),
            "stl_violaciones": " ".join(f"{r}:{x['violaciones']}" for r, x in (s.get("stl") or {}).items()
                                        if x["violaciones"]),
            "hash_pesos": m.get("hash_pesos"),
        })
    return filas


def _f(v, fmt):
    return "-" if v is None else format(v, fmt)


def imprimir_kpis(filas):
    print(f"{'nivel':>5} {'n':>4} {'limpia %':>9} {'IC95':>13} {'c/reint %':>9} {'fallas/km':>9} "
          f"{'IC95':>13} {'Pfalla<':>8} {'km/h':>6} {'TLCp05':>7}  falla principal")
    for r in filas:
        print(f"{r['nivel']:>5} {r['n']:>4} {_f(r['llegada_limpia_pct'], '9.1f')} "
              f"{_f(r['ic_lo'], '6.1f')}-{_f(r['ic_hi'], '<6.1f')} {_f(r['llegada_reintentos_pct'], '9.1f')} "
              f"{_f(r['fallas_km'], '9.2f')} {_f(r['fallas_km_lo'], '6.2f')}-{_f(r['fallas_km_hi'], '<6.2f')} "
              f"{_f(r['p_falla_max'], '8.3f')} {_f(r['vel_kmh'], '6.1f')} {_f(r['tlc_p05_s'], '7.2f')}  "
              f"{r['falla_principal'].encode('ascii', 'replace').decode()}")


def guardar_kpis(filas, ruta=None):
    if ruta is None:
        os.makedirs(E.DIR_RESULTADOS, exist_ok=True)
        ruta = os.path.join(E.DIR_RESULTADOS, f"kpis_{_dt.datetime.now():%Y%m%d_%H%M%S}.csv")
    ruta = E.en_proyecto(ruta)
    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    with open(ruta, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNAS)
        w.writeheader()
        w.writerows(filas)
    return ruta


def main(argv=None):
    ap = argparse.ArgumentParser(description="Tabla de KPIs de seguridad")
    ap.add_argument("--desde", default=None, help="JSON de una evaluación ya hecha")
    ap.add_argument("--modo", choices=("terreno", "ciudad"), default="terreno")
    ap.add_argument("--niveles", type=int, nargs="+", default=[1])
    ap.add_argument("--pistas", type=int, default=20)
    ap.add_argument("--ruidos", type=int, default=5)
    ap.add_argument("--sensores", default="ideal")
    ap.add_argument("--pesos", default=None)
    a = ap.parse_args(argv)
    if a.desde:
        ev = a.desde
    else:
        pesos, _ = E.cargar_pesos(a.modo, a.pesos)
        ev = E.evaluar(pesos, a.modo, tuple(a.niveles), a.pistas, a.ruidos, a.sensores, verbose=False)
    filas = tabla_kpis(ev)
    imprimir_kpis(filas)
    print("CSV:", guardar_kpis(filas))
    return filas


if __name__ == "__main__":
    main(sys.argv[1:])
