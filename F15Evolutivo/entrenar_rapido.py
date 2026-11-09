import argparse
import multiprocessing as mp
import os
import sys
import time

import numpy as np

import catalogo as K
import config as C

TODAS = [m["numero"] for m in sorted(K.MISIONES.values(), key=lambda m: m["orden"])]
PACIENCIA = 20 * len(TODAS)
ESPERA = 7 * 86400
POBLACION = 128
NUCLEOS = max(3, (os.cpu_count() or 2) // 2)


def _hms(s):
    s = int(s)
    return f"{s // 3600:d}:{s // 60 % 60:02d}:{s % 60:02d}"


def _clave(c):
    return None if c is None else (round(c.get("sup_frac", float(c["superada"])), 4), round(c["aptitud"], 2))


def tabla(e):
    print("\n  #  Misión                           Superada  Éxito  Puntaje  Estab.  Gen.", flush=True)
    total, superadas = 0.0, 0
    for n in TODAS:
        c = e.campeones.get(n)
        if c is None:
            print(f"{n:3d}  {K.nombre(n):<32} {'—':>8}", flush=True)
            continue
        total += c["aptitud"]
        superadas += e.superada(n)
        estado = ("sí" if e.superada(n) else "a prueba") if c["superada"] else "no"
        print(f"{n:3d}  {K.nombre(n):<32} {estado:>8} {100 * c.get('sup_frac', 0):5.0f}% "
              f"{c['aptitud']:8.1f} {c.get('estabilidad', 0):7.2f} {c['generacion']:5d}", flush=True)
    print(f"     Superadas {superadas}/{len(TODAS)} · puntaje total {total:.1f}\n", flush=True)
    return superadas, total


class Detener(Exception):
    pass


def _esperar(res, g):
    while g is not None and g.vivo and not res.ready():
        g.bombear()
        if g.accion:
            raise Detener
        res.wait(0.05)
    return res.get(ESPERA)


def _estado(e, t0, gen0, ultima=None):
    hechas = e.generacion - gen0
    trans = time.perf_counter() - t0
    ritmo = f" · {3600 * hechas / trans:.0f} gen/hora" if hechas and trans > 1 else ""
    extra = f" · última generación {ultima:.0f} s" if ultima else ""
    return (f"Generación {e.generacion} · ahora: misión {e.leccion_actual} «{K.nombre(e.leccion_actual)}» · "
            f"currículo {e.modo}\nEntrenando hace {_hms(trans)} · {hechas} generaciones{ritmo}{extra}")


def _clase(e, pool, n, rng, procesos, g=None):
    semillas = [int(s) for s in rng.integers(1, 1 << 30, max(6, procesos))]
    print(f"  clase del instructor: «{K.nombre(n)}» ({len(semillas) * 6} vuelos)…", end="", flush=True)
    t = time.perf_counter()
    from evolucion import demos_tarea, imitar_tarea
    partes = [p for p in _esperar(pool.map_async(demos_tarea, [(n, [s], 6) for s in semillas]), g) if p is not None]
    if not partes:
        print(" sin demostración válida", flush=True)
        return
    x, y = np.concatenate([p[0] for p in partes]), np.concatenate([p[1] for p in partes])
    theta = _esperar(pool.apply_async(imitar_tarea, (e.preparar_aprendizaje(x, y, n),)), g)
    total = e.aplicar_aprendizaje(theta)
    print(f" {len(x)} ejemplos ({total} en memoria) · {time.perf_counter() - t:.0f} s", flush=True)


def entrenar(nuevo=False, poblacion=POBLACION, semilla=None, minutos=None, generaciones=None, paciencia=PACIENCIA,
             escenarios=None, procesos=None, modo="mezcla", dir_datos=None, grafica=True):
    from evolucion import Entrenador, evaluar, iniciar_trabajador
    for flujo in (sys.stdout, sys.stderr):
        try:
            flujo.reconfigure(errors="replace")
        except (AttributeError, ValueError):
            pass
    C.ESCENARIOS = max(1, escenarios or NUCLEOS)
    procesos = procesos or min(C.ESCENARIOS, max(1, (os.cpu_count() or 2) - 1))
    e = Entrenador(continuar=not nuevo, semilla=semilla, poblacion=poblacion, dir_datos=dir_datos, curriculo=TODAS)
    if nuevo:
        e.reiniciar()
    faltan = [k for k in TODAS if not e.superada(k)]
    if e.completada and faltan and e.modo != "fija":
        e.completada = False
        e.leccion = faltan[0]
        e.racha = 0
    if modo and e.modo != modo:
        e.fijar_modo(modo)
    if e.saltar_superadas():
        e.guardar()
    rng = np.random.default_rng(semilla)
    print("=" * 78)
    print(f"F-15 · entrenamiento rápido sin gráficos · {len(TODAS)} misiones")
    print(f"población {e.n} · {C.ESCENARIOS} escenarios por generación · {procesos} procesos · currículo {e.modo}")
    print(f"empieza en la generación {e.generacion}, misión {e.leccion_actual} «{K.nombre(e.leccion_actual)}»")
    print("Ctrl+C detiene y guarda. El simulador gráfico usa lo aprendido (mismos datos).")
    if grafica:
        print("En la ventana de la gráfica: «Abrir el simulador gráfico» detiene, guarda y vuelve a la vista 3D.")
    print("=" * 78, flush=True)
    tabla(e)
    g = None
    if grafica:
        try:
            from grafica import Grafica
            g = Grafica("F-15 · entrenamiento rápido", TODAS, K.nombre)
        except Exception as ex:
            print(f"(sin ventana de gráfica: {ex})", flush=True)
    pool = mp.Pool(procesos, initializer=iniciar_trabajador)
    t0 = time.perf_counter()
    gen0 = e.generacion
    if g:
        g.actualizar(e.historial, e.campeones, _estado(e, t0, gen0))
    ultima_mejora = e.generacion
    motivo = ""
    try:
        while True:
            n = e.necesita_clase()
            if n is not None:
                e.anotar_clase(n)
                if g:
                    g.estado.configure(text=f"Clase del instructor: «{K.nombre(n)}»…")
                _clase(e, pool, n, rng, procesos, g)
            antes = {k: _clave(e.campeones.get(k)) for k in TODAS}
            t = time.perf_counter()
            r = e.terminar(_esperar(pool.map_async(evaluar, e.tareas()), g))
            mejoro = [k for k in TODAS if _clave(e.campeones.get(k)) != antes[k]]
            if mejoro:
                ultima_mejora = e.generacion
            print(f"gen {r['generacion']:5d} · {r['leccion']:2d} {r['nombre']:<26} mejor {r['mejor_progreso']:5.1f}% "
                  f"superaron {r['superaron_pct']:5.1f}% caídos {r['estrellados_pct']:5.1f}% "
                  f"apt {r['mejor_aptitud']:6.1f} · {time.perf_counter() - t:4.1f} s"
                  + (" · ¡nuevo récord!" if mejoro else "") + (" · ¡SUPERADA!" if r["subio"] else "")
                  + (f" · regresa al campeón de la gen. {r['volvio']}" if r["volvio"] != "" else ""), flush=True)
            if g:
                g.actualizar(e.historial, e.campeones, _estado(e, t0, gen0, time.perf_counter() - t))
            if r["subio"] or (e.generacion - gen0) % 50 == 0:
                tabla(e)
                e.guardar()
            hechas = e.generacion - gen0
            todas = all(e.superada(k) for k in TODAS)
            if minutos and time.perf_counter() - t0 >= minutos * 60:
                motivo = f"se cumplieron {minutos:g} minutos"
            elif generaciones and hechas >= generaciones:
                motivo = f"se cumplieron {generaciones} generaciones"
            elif paciencia and e.completada and todas and e.generacion - ultima_mejora >= paciencia:
                motivo = f"objetivo alcanzado: las {len(TODAS)} misiones superadas y sin mejorar en {paciencia} generaciones"
            if motivo:
                break
    except (KeyboardInterrupt, Detener):
        motivo = "abrir el simulador gráfico" if g and g.accion == "simulador" else "detenido por el usuario"
    finally:
        pool.terminate()
        e.guardar()
    print(f"\nFin: {motivo} · {e.generacion - gen0} generaciones en {_hms(time.perf_counter() - t0)}", flush=True)
    tabla(e)
    if g and g.vivo and not g.accion:
        g.actualizar(e.historial, e.campeones, _estado(e, t0, gen0))
        g.terminado(f"Terminado: {motivo}. Todo quedó guardado.")
        try:
            while g.vivo and not g.accion:
                g.bombear()
                time.sleep(0.05)
        except KeyboardInterrupt:
            pass
    volver = bool(g and g.accion == "simulador")
    if g:
        g.cerrar()
    return volver


def main(argv=None):
    ap = argparse.ArgumentParser(description="F-15 evolutivo: entrenamiento rápido sin gráficos de las 13 misiones")
    ap.add_argument("--nuevo", action="store_true", help="empezar la evolución desde cero")
    ap.add_argument("--minutos", type=float, default=None, help="detener tras estos minutos")
    ap.add_argument("--generaciones", type=int, default=None, help="detener tras estas generaciones")
    ap.add_argument("--paciencia", type=int, default=PACIENCIA,
                    help="con todas superadas, detener tras estas generaciones sin récord nuevo (0 = nunca)")
    ap.add_argument("--escenarios", type=int, default=None, help="escenarios por generación (por omisión, uno por núcleo)")
    ap.add_argument("--procesos", type=int, default=None)
    ap.add_argument("--curriculo", choices=("secuencial", "mezcla"), default="mezcla")
    ap.add_argument("--poblacion", type=int, default=POBLACION)
    ap.add_argument("--semilla", type=int, default=None)
    ap.add_argument("--sin-grafica", action="store_true", help="no abrir la ventana con la gráfica del avance")
    ap.add_argument("--datos", default=None, help=argparse.SUPPRESS)
    a = ap.parse_args(argv)
    if entrenar(nuevo=a.nuevo, poblacion=a.poblacion, semilla=a.semilla, minutos=a.minutos, generaciones=a.generaciones,
                paciencia=a.paciencia, escenarios=a.escenarios, procesos=a.procesos, modo=a.curriculo,
                dir_datos=a.datos, grafica=not a.sin_grafica):
        import subprocess
        args = [sys.executable, os.path.join(os.path.dirname(os.path.abspath(__file__)), "main.py")]
        subprocess.call(args + (["--datos", a.datos] if a.datos else []))


if __name__ == "__main__":
    mp.freeze_support()
    main()
