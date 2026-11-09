"""MT-Bench: lotes de experimentos multi-semilla y comparación de controladores.

Todo se escribe bajo resultados/<fecha>_<nombre>/ con su propio dir_datos, así que NUNCA
toca mejor_moto.json / poblacion.npz / historial.csv del usuario.

Uso (también vía main.py --experimento / --comparar):
    python experimentos.py lote --nombre base --semillas 0-4 --generaciones 20 --procesos 5
    python experimentos.py lote --nombre sin_cruce --set PROB_CRUCE=0 --semillas 0-4
    python experimentos.py comparar --nivel 3 --pistas 10 --procesos 8

Protocolo:
  * presupuesto fijo en generaciones (= evaluaciones de episodio: gens × población × pistas/gen);
  * al final, la campeona de cada semilla se evalúa en la suite de PRUEBA reservada
    (semillas 2**31 + 1000·nivel + j, nunca vistas en entrenamiento) contando sólo
    LLEGADAS LIMPIAS (sin ningún error: equivale a max_reintentos = 0);
  * el resumen reporta media y su IC 95 % por bootstrap sobre semillas, y la tasa agregada
    con IC de Clopper-Pearson (o Wilson si no hay scipy).
"""
import argparse
import csv
import json
import math
import os
import platform
import sys
import time
from concurrent.futures import ProcessPoolExecutor

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

SEMILLA_PRUEBA = 2 ** 31
SEMILLA_RUIDO_PRUEBA = 2 ** 31


def rango_semillas(texto):
    out = []
    for parte in str(texto).split(","):
        if "-" in parte:
            a, b = parte.split("-")
            out += list(range(int(a), int(b) + 1))
        elif parte.strip():
            out.append(int(parte))
    return out


def ic_bootstrap(valores, reps=10_000, nivel=0.95, semilla=0):
    v = np.asarray(valores, dtype=float)
    if len(v) == 0:
        return (float("nan"),) * 3
    if len(v) == 1:
        return float(v[0]), float(v[0]), float(v[0])
    rng = np.random.default_rng(semilla)
    medias = v[rng.integers(len(v), size=(reps, len(v)))].mean(1)
    a = (1 - nivel) / 2
    return float(v.mean()), float(np.quantile(medias, a)), float(np.quantile(medias, 1 - a))


def ic_proporcion(k, n, nivel=0.95):
    if n == 0:
        return float("nan"), float("nan")
    a = 1 - nivel
    try:
        from scipy.stats import beta
        lo = 0.0 if k == 0 else float(beta.ppf(a / 2, k, n - k + 1))
        hi = 1.0 if k == n else float(beta.ppf(1 - a / 2, k + 1, n - k))
        return lo, hi
    except ImportError:
        z = 1.959963984540054
        p = k / n
        d = 1 + z * z / n
        c = (p + z * z / (2 * n)) / d
        h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
        return max(0.0, c - h), min(1.0, c + h)


def _simulador(pista, pesos, semilla_ruido, controlador=None):
    import fisica as F
    if controlador is None:
        return F.Simulador(pista, pesos, semilla_ruido=semilla_ruido)
    try:
        return F.Simulador(pista, None, semilla_ruido=semilla_ruido, controlador=controlador, n=1)
    except TypeError:
        pass

    class _Adaptado(F.Simulador):
        def paso(self):
            if self.terminado:
                return
            original = F.R.adelante
            F.R.adelante = lambda red, obs: controlador(obs, self)
            try:
                super().paso()
            finally:
                F.R.adelante = original

    return _Adaptado(pista, np.zeros((1, sum(a * b + b for a, b in zip(C.CAPAS[:-1], C.CAPAS[1:])))),
                     semilla_ruido=semilla_ruido)


def nueva_pista(nivel, semilla, modo="terreno", red_vial=None):
    if modo == "ciudad":
        from calles import PistaCalle
        return PistaCalle(red_vial, nivel, semilla)
    from terreno import Pista
    return Pista(nivel, semilla)


def _crear_controlador(tipo, pesos=None, semilla=0):
    import controladores as K
    if tipo == "red":
        return None
    if tipo == "pd":
        return K.ControladorPD()
    if tipo == "aleatorio":
        return K.ControladorAleatorio(semilla=semilla)
    raise ValueError(tipo)


def episodio(tipo, nivel, j, ruido=0, pesos=None):
    from fisica import META
    semilla = SEMILLA_PRUEBA + 1000 * nivel + j
    pista = nueva_pista(nivel, semilla)
    ctl = _crear_controlador(tipo, pesos, semilla=semilla + 17 * ruido)
    s = _simulador(pista, pesos if tipo == "red" else None, SEMILLA_RUIDO_PRUEBA + 7919 * ruido + j, ctl)
    while not s.terminado:
        s.paso()
    llego = bool(s.motivo[0] == META)
    largo = pista.meta - pista.salida
    return {"controlador": tipo, "nivel": nivel, "pista": j, "ruido": ruido,
            "llego": llego, "limpia": bool(llego and s.reintentos[0] == 0),
            "reintentos": int(s.reintentos[0]), "motivo": int(s.motivo[0]),
            "progreso_pct": float(100 * s.progreso[0] / largo), "t": float(s.t_fin[0]),
            "km_h": float(largo / max(s.t_fin[0], 1e-3) * 3.6) if llego else 0.0,
            "aptitud": float(s.aptitud()[0])}


def _episodio_tupla(args):
    return episodio(*args)


def evaluar_suite(tipo, niveles, pistas, ruidos=1, pesos=None, procesos=1):
    tareas = [(tipo, nv, j, k, pesos) for nv in niveles for j in range(pistas) for k in range(ruidos)]
    if procesos > 1:
        with ProcessPoolExecutor(max_workers=procesos) as ex:
            return list(ex.map(_episodio_tupla, tareas, chunksize=max(1, len(tareas) // (4 * procesos))))
    return [episodio(*t) for t in tareas]


def resumir_episodios(filas):
    out = {}
    for tipo in dict.fromkeys(f["controlador"] for f in filas):
        sub = [f for f in filas if f["controlador"] == tipo]
        k, n = sum(f["limpia"] for f in sub), len(sub)
        lo, hi = ic_proporcion(k, n)
        out[tipo] = {"episodios": n, "llegadas_limpias": k, "tasa_limpia": k / n,
                     "ic95": [lo, hi], "tasa_con_reintentos": sum(f["llego"] for f in sub) / n,
                     "progreso_medio_pct": float(np.mean([f["progreso_pct"] for f in sub])),
                     "aptitud_media": (float(np.mean(apt)) if (apt := [f["aptitud"] for f in sub
                                                                        if np.isfinite(f["aptitud"])])
                                       else None)}
    return out


def _suite_oficial(args):
    tipo, nivel, pistas, ruidos, sensores, pesos = args
    import evaluacion as EV
    obj = pesos if tipo == "red" else _crear_controlador(tipo, semilla=SEMILLA_PRUEBA + nivel)
    out = EV.evaluar(obj, "terreno", (nivel,), pistas, ruidos, sensores, guardar=False, verbose=False,
                     registrar=False, etiqueta=tipo)
    return [{"controlador": tipo, "nivel": nivel, "pista": f["pista"], "ruido": f["ruido"],
             "llego": bool(f.get("llego_con_reintentos")), "limpia": bool(f["llego_limpio"]),
             "motivo": f["motivo"], "progreso_pct": 100 * f["progreso_m"] / max(f["largo_m"], 1e-9),
             "km_h": f.get("vel_media_kmh") or 0.0, "aptitud": float("nan")}
            for f in out["episodios"]]


def comparar(nivel=None, pistas=10, ruidos=1, procesos=1, salida=None, modo="terreno",
             sensores="ideal"):
    from evolucion import cargar_mejor
    if modo != "terreno":
        print("Aviso: --comparar usa por ahora pistas de terreno.")
    niveles = [nivel] if nivel else list(range(1, C.NIVEL_MAX + 1))
    filas = []
    m = cargar_mejor("terreno")
    tipos = (["red"] if m is not None else []) + ["pd", "aleatorio"]
    if m is None:
        print("No hay mejor_moto.json: se comparan sólo PD y aleatorio.")
    t0 = time.perf_counter()
    try:
        import evaluacion
        oficial = True
    except Exception as err:
        print(f"Aviso: evaluacion.py no disponible ({err}); uso el evaluador interno.")
        oficial = False
    if oficial:
        tareas = [(t, nv, pistas, ruidos, sensores, m[0] if (m and t == "red") else None)
                  for t in tipos for nv in niveles]
        if procesos > 1:
            with ProcessPoolExecutor(max_workers=min(procesos, len(tareas))) as ex:
                for f in ex.map(_suite_oficial, tareas):
                    filas += f
        else:
            for t in tareas:
                filas += _suite_oficial(t)
    else:
        for tipo in tipos:
            filas += evaluar_suite(tipo, niveles, pistas, ruidos,
                                   m[0] if (m and tipo == "red") else None, procesos)
    res = resumir_episodios(filas)
    print(f"\nSuite de prueba reservada · niveles {niveles} · {pistas} pistas × {ruidos} ruido(s) "
          f"· {time.perf_counter() - t0:.1f} s")
    print(f"{'controlador':12s} {'llegada limpia':>15s} {'IC 95 %':>17s} {'con reintentos':>15s} {'progreso':>9s}")
    for tipo, r in res.items():
        print(f"{tipo:12s} {r['llegadas_limpias']:5d}/{r['episodios']:<4d} {100 * r['tasa_limpia']:5.1f}% "
              f"[{100 * r['ic95'][0]:5.1f}, {100 * r['ic95'][1]:5.1f}] {100 * r['tasa_con_reintentos']:13.1f}% "
              f"{r['progreso_medio_pct']:8.1f}%")
    if salida:
        salida = _en_proyecto(salida)
        os.makedirs(salida, exist_ok=True)
        _escribir_csv(os.path.join(salida, "comparacion_episodios.csv"), filas)
        with open(os.path.join(salida, "comparacion_resumen.json"), "w", encoding="utf-8") as f:
            json.dump({"niveles": niveles, "pistas": pistas, "ruidos": ruidos, "resultados": res,
                       "meta": metadatos()}, f, indent=2, ensure_ascii=False)
        print(f"Guardado en {salida}")
    return res


def metadatos():
    import hashlib
    d = {"fecha": time.strftime("%Y-%m-%d %H:%M:%S"), "python": platform.python_version(),
         "numpy": np.__version__, "plataforma": platform.platform(), "cpu": os.cpu_count()}
    try:
        with open(os.path.join(AQUI, "config.py"), "rb") as f:
            d["config_sha256"] = hashlib.sha256(f.read()).hexdigest()[:16]
    except OSError:
        pass
    return d


def _entrenador(poblacion, semilla, dir_datos, procesos):
    import evolucion as E
    try:
        return E.Entrenador(poblacion, continuar=False, semilla=semilla, dir_datos=dir_datos,
                            procesos=procesos)
    except TypeError:
        E.AQUI = dir_datos
        return E.Entrenador(poblacion, continuar=False, semilla=semilla)


def correr_semilla(args):
    nombre, semilla, generaciones, poblacion, overrides, dir_base, niveles_eval, pistas_eval = args
    for k, v in overrides.items():
        if not hasattr(C, k):
            raise KeyError(f"config no tiene {k}")
        setattr(C, k, v)
    d = os.path.join(dir_base, f"semilla_{semilla}")
    os.makedirs(d, exist_ok=True)
    e = _entrenador(poblacion, semilla, d, 1)
    t0 = time.perf_counter()
    curva = []
    for _ in range(generaciones):
        r = e.correr_generacion()
        curva.append({k: r.get(k) for k in ("generacion", "nivel", "mejor", "promedio", "llegaron",
                                            "terminadas_lider", "vel_lider")})
        if "llegadas_limpias_pct" in r:
            curva[-1]["llegadas_limpias_pct"] = r["llegadas_limpias_pct"]
    t_entreno = time.perf_counter() - t0
    campeona = e.pob[0].copy()
    np.save(os.path.join(d, "campeona.npy"), campeona)
    niveles = niveles_eval or sorted({1, e.nivel})
    filas = evaluar_suite("red", niveles, pistas_eval, 1, campeona, 1)
    for f in filas:
        f.update(condicion=nombre, semilla=semilla)
    fila = {"condicion": nombre, "semilla": semilla, "generaciones": generaciones,
            "poblacion": poblacion, "nivel_final": e.nivel, "mejor_final": curva[-1]["mejor"],
            "tiempo_entreno_s": round(t_entreno, 2),
            "s_por_generacion": round(t_entreno / max(generaciones, 1), 3),
            "episodios_entreno": generaciones * poblacion * C.PISTAS_POR_GENERACION}
    for nv in niveles:
        sub = [f for f in filas if f["nivel"] == nv]
        fila[f"limpia_prueba_n{nv}"] = sum(f["limpia"] for f in sub) / len(sub)
    with open(os.path.join(d, "curva.json"), "w", encoding="utf-8") as f:
        json.dump(curva, f)
    return fila, filas


def lote(nombre="base", semillas=(0, 1, 2), generaciones=20, poblacion=C.POBLACION,
         overrides=None, procesos=1, niveles_eval=None, pistas_eval=10, raiz=None):
    overrides = overrides or {}
    raiz = _en_proyecto(raiz) or os.path.join(AQUI, "resultados")
    dir_base = os.path.join(raiz, f"{time.strftime('%Y%m%d_%H%M%S')}_{nombre}")
    os.makedirs(dir_base, exist_ok=True)
    meta = dict(metadatos(), nombre=nombre, semillas=list(semillas), generaciones=generaciones,
                poblacion=poblacion, overrides=overrides, pistas_eval=pistas_eval,
                niveles_eval=niveles_eval, semilla_prueba=SEMILLA_PRUEBA)
    with open(os.path.join(dir_base, "experimento.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)
    tareas = [(nombre, s, generaciones, poblacion, overrides, dir_base, niveles_eval, pistas_eval)
              for s in semillas]
    print(f"Lote «{nombre}»: {len(tareas)} semillas × {generaciones} generaciones × {poblacion} motos "
          f"→ {dir_base}", flush=True)
    filas, episodios = [], []
    with ProcessPoolExecutor(max_workers=max(1, min(procesos, len(tareas)))) as ex:
        for fila, eps in ex.map(correr_semilla, tareas):
            print(f"  semilla {fila['semilla']}: nivel {fila['nivel_final']} · mejor {fila['mejor_final']:.1f} "
                  f"· {fila['s_por_generacion']:.2f} s/gen", flush=True)
            filas.append(fila)
            episodios += eps
    _escribir_csv(os.path.join(dir_base, "semillas.csv"), filas)
    _escribir_csv(os.path.join(dir_base, "episodios_prueba.csv"), episodios)
    resumen = {"nombre": nombre, "n_semillas": len(filas)}
    for clave in [k for k in filas[0] if k.startswith(("nivel_final", "mejor_final", "limpia_prueba",
                                                       "s_por_generacion"))]:
        vals = [f[clave] for f in filas if f.get(clave) is not None]
        m, lo, hi = ic_bootstrap(vals)
        resumen[clave] = {"media": m, "ic95_bootstrap": [lo, hi], "valores": vals}
    k = sum(e["limpia"] for e in episodios)
    resumen["llegada_limpia_agregada"] = {"k": k, "n": len(episodios),
                                          "ic95": list(ic_proporcion(k, len(episodios)))}
    with open(os.path.join(dir_base, "resumen.json"), "w", encoding="utf-8") as f:
        json.dump(resumen, f, indent=2, ensure_ascii=False)
    print(f"Resumen en {os.path.join(dir_base, 'resumen.json')}")
    return dir_base, resumen


def _escribir_csv(ruta, filas):
    if not filas:
        return
    claves = list(dict.fromkeys(k for f in filas for k in f))
    with open(ruta, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=claves)
        w.writeheader()
        w.writerows(filas)


def _valor(texto):
    for tipo in (int, float):
        try:
            return tipo(texto)
        except ValueError:
            pass
    return {"true": True, "false": False}.get(texto.lower(), texto)


def principal(argv=None):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap =argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("lote", help="entrenar varias semillas con presupuesto fijo")
    a.add_argument("--nombre", default="base")
    a.add_argument("--semillas", default="0-4")
    a.add_argument("--generaciones", type=int, default=20)
    a.add_argument("--poblacion", type=int, default=C.POBLACION)
    a.add_argument("--procesos", type=int, default=min(5, os.cpu_count() or 1))
    a.add_argument("--set", action="append", default=[], metavar="CLAVE=VALOR",
                   help="override de config.py (repetible), p. ej. --set PROB_CRUCE=0")
    a.add_argument("--niveles-eval", default=None, help="niveles de la suite de prueba, p. ej. 1-3")
    a.add_argument("--pistas-eval", type=int, default=10)
    a.add_argument("--salida", default=None, help="carpeta raíz (por defecto resultados/)")
    b = sub.add_parser("comparar", help="red vs PD vs aleatorio en la suite reservada")
    b.add_argument("--nivel", type=int)
    b.add_argument("--pistas", type=int, default=10)
    b.add_argument("--ruidos", type=int, default=1)
    b.add_argument("--procesos", type=int, default=os.cpu_count() or 1)
    b.add_argument("--salida", default=None)
    b.add_argument("--sensores", default="ideal", help="ideal | realista")
    x = ap.parse_args(argv)
    x.salida = _en_proyecto(x.salida)
    if x.cmd == "lote":
        ov = dict(kv.split("=", 1) for kv in x.set)
        lote(x.nombre, rango_semillas(x.semillas), x.generaciones, x.poblacion,
             {k: _valor(v) for k, v in ov.items()}, x.procesos,
             rango_semillas(x.niveles_eval) if x.niveles_eval else None, x.pistas_eval, x.salida)
    else:
        comparar(x.nivel, x.pistas, x.ruidos, x.procesos,
                 x.salida or os.path.join(AQUI, "resultados", time.strftime("%Y%m%d_%H%M%S") + "_comparar"),
                 sensores=x.sensores)


if __name__ == "__main__":
    principal()
