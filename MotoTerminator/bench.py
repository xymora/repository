"""Benchmark de rendimiento de MT-Bench (no escribe nada en la carpeta del usuario).

    python bench.py                 tabla completa (~30-60 s)
    python bench.py --rapido        versión corta (~10 s, la que usa la CI)
    python bench.py --json salida.json

Mide:
  * µs por subpaso de física y por moto, con N = 1, 10, 80, 320 (costo fijo vs marginal);
  * µs por paso de control (observar + red + 6 subpasos + reglas);
  * pasos-moto por segundo (rendimiento real del simulador);
  * segundos por generación del entrenamiento (población 80, 3 pistas, nivel 1, semilla fija).
"""
import argparse
import json
import os
import platform
import sys
import tempfile
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
import red as R
from fisica import Simulador
from terreno import Pista


def medir_fisica(ns=(1, 10, 80, 320), pasos=40):
    pista = Pista(3, 5)
    rng = np.random.default_rng(0)
    filas = []
    for n in ns:
        s = Simulador(pista, R.aleatorios(n, C.CAPAS, rng), semilla_ruido=1)
        s.ctrl = np.zeros((n, 3))
        s._fisica(0.0, 0.0)
        t = time.perf_counter()
        for _ in range(pasos * C.SUBPASOS):
            s._fisica(0.0, 0.0)
        us_sub = (time.perf_counter() - t) / (pasos * C.SUBPASOS) * 1e6
        s = Simulador(pista, R.aleatorios(n, C.CAPAS, rng), semilla_ruido=1)
        t = time.perf_counter()
        k = 0
        while k < pasos and not s.terminado:
            vivos = len(s.ids)
            s.paso()
            k += 1
        dt = (time.perf_counter() - t) / max(k, 1)
        filas.append({"n": n, "us_subpaso": round(us_sub, 1), "us_subpaso_por_moto": round(us_sub / n, 2),
                      "us_paso_control": round(dt * 1e6, 1),
                      "pasos_moto_por_s": round(vivos / dt, 0)})
    return filas


def _entrenador_temporal(dir_tmp, poblacion, semilla):
    import evolucion as E
    try:
        return E.Entrenador(poblacion, continuar=False, semilla=semilla, dir_datos=dir_tmp, guardar=False)
    except TypeError:
        E.AQUI = dir_tmp
        return E.Entrenador(poblacion, continuar=False, semilla=semilla)


def medir_generacion(generaciones=2, poblacion=C.POBLACION, semilla=1):
    with tempfile.TemporaryDirectory() as d:
        e = _entrenador_temporal(d, poblacion, semilla)
        tiempos = []
        for _ in range(generaciones):
            t = time.perf_counter()
            e.correr_generacion()
            tiempos.append(time.perf_counter() - t)
    return {"poblacion": poblacion, "pistas_por_gen": C.PISTAS_POR_GENERACION,
            "s_por_generacion": [round(x, 2) for x in tiempos],
            "s_por_generacion_media": round(float(np.mean(tiempos)), 2)}


def principal(argv=None):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--rapido", action="store_true")
    ap.add_argument("--json", metavar="RUTA")
    a = ap.parse_args(argv)
    info = {"fecha": time.strftime("%Y-%m-%d %H:%M:%S"), "python": platform.python_version(),
            "numpy": np.__version__, "cpu": platform.processor() or platform.machine(),
            "nucleos": os.cpu_count(), "SUBPASOS": C.SUBPASOS}
    print(f"MT-Bench · Python {info['python']} · numpy {info['numpy']} · {info['nucleos']} núcleos · "
          f"SUBPASOS={C.SUBPASOS}")
    fis = medir_fisica(ns=(1, 80) if a.rapido else (1, 10, 80, 320), pasos=15 if a.rapido else 40)
    print(f"\n{'N':>5} {'µs/subpaso':>11} {'µs/sub/moto':>12} {'µs/paso ctrl':>13} {'pasos-moto/s':>13}")
    for f in fis:
        print(f"{f['n']:5d} {f['us_subpaso']:11.1f} {f['us_subpaso_por_moto']:12.2f} "
              f"{f['us_paso_control']:13.1f} {f['pasos_moto_por_s']:13.0f}")
    gen = medir_generacion(generaciones=1 if a.rapido else 2,
                           poblacion=20 if a.rapido else C.POBLACION)
    print(f"\nGeneración (población {gen['poblacion']}, {gen['pistas_por_gen']} pistas, nivel 1): "
          f"{gen['s_por_generacion_media']:.2f} s  {gen['s_por_generacion']}")
    res = {"info": info, "fisica": fis, "generacion": gen}
    if a.json:
        with open(_en_proyecto(a.json), "w", encoding="utf-8") as f:
            json.dump(res, f, indent=2, ensure_ascii=False)
    return res


if __name__ == "__main__":
    principal()
