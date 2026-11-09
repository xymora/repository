"""Moto autónoma evolutiva (estilo Moto-Terminator): aprende sola a andar en cualquier terreno.

Uso:
    python main.py                  entrenar viendo la animación (continúa lo guardado)
    python main.py --nuevo          empezar la evolución desde cero
    python main.py --demo           ver a la mejor moto guardada en pistas nuevas
    python main.py --demo --nivel 6 ...en pistas de un nivel en particular
    python main.py --recorrido      elegir un recorrido (terreno / calles / clima) y verlo con
                                    la mejor moto del salón de la fama
    python main.py --clima lluvia   clima fijo en TODAS las pistas (preset de clima.py; "auto" =
                                    clima automático al azar, el de config.py por defecto)
    python main.py --sin-gui 150    entrenar 150 generaciones en consola (rápido)
    python main.py --ciudad "Monterrey · Centro"   manejar por calles reales (o "lat, lon")
    python main.py --desde "25.676, -100.315" --hasta "25.670, -100.300"   ruta A → B
    python main.py --desde ... --hasta ... --circuito otra   circuito A → B → A (regresa por otra ruta)
    python main.py --ciudad "Monterrey · Centro" --circuito misma --superficie irregular
                    (sin --superficie/--circuito las calles siguen el plan de estudios automático)
    python main.py --poblacion 120  cambiar el tamaño de la población
    python main.py --semilla 4      resultados reproducibles

MT-Bench (evaluación y experimentos; nada de esto toca lo que entrenas en la ventana):
    python main.py --evaluar [--nivel 3] [--pistas 20] [--ruidos 5] [--modo terreno|ciudad]
                   [--sensores ideal|realista]      suite de prueba RESERVADA, sin rebobinado, con IC
    python main.py --comparar [--nivel 3] [--pistas 10]   red guardada vs PD vs aleatorio
    python main.py --sin-gui 50 --procesos 3        evalúa las pistas de cada generación en paralelo
    python main.py --sin-gui 20 --dir-datos resultados/mi_corrida   entrena en otra carpeta
    python main.py --experimento base --semillas 0-4 --generaciones 20   lote multi-semilla
    python main.py --bench          rendimiento (s/generación, µs/subpaso, pasos-moto/s)
    python main.py --reporte        reporte de seguridad a partir de los resultados
"""
import argparse
import os
import sys

import config as C

AQUI = os.path.dirname(os.path.abspath(__file__))


def en_proyecto(ruta):
    return ruta if os.path.isabs(ruta) else os.path.normpath(os.path.join(AQUI, ruta))


def red_de_calles(texto):
    import calles as K
    if texto in K.ZONAS:
        zona = K.zona_para(texto)
    else:
        coords = K.leer_coordenadas(texto)
        if coords is None:
            sys.exit(f"No reconozco la zona «{texto}». Opciones: {', '.join(K.ZONAS)} o 'lat, lon'.")
        zona = K.Zona(f"Zona {coords[0]:.4f}, {coords[1]:.4f}", coords)
    try:
        red = K.RedVial(zona)
        K.imagen_satelital(zona)
    except RuntimeError as e:
        sys.exit(f"No se pudieron preparar las calles de {zona.nombre}:\n{e}")
    return red


def _largo(pts):
    return sum(((p[0] - q[0]) ** 2 + (p[1] - q[1]) ** 2) ** 0.5 for p, q in zip(pts[1:], pts[:-1]))


def trazar_ruta(red, a, b, circuito="no"):
    zona = red.zona
    a_xy, b_xy = zona.a_metros(*a), zona.a_metros(*b)
    circuito = circuito if circuito in ("misma", "otra") else "no"
    if circuito != "no":
        if not hasattr(red, "ruta_circuito"):
            raise RuntimeError("Esta versión de calles.py aún no sabe trazar circuitos.")
        ruta = red.ruta_circuito(a_xy, b_xy, circuito)
    else:
        ruta = red.ruta_entre(a_xy, b_xy)
    info = {"a_xy": a_xy, "b_xy": b_xy, "a": a, "b": b, "largo": _largo(ruta[0]),
            "circuito": circuito}
    if circuito != "no" and len(ruta) > 2 and ruta[2]:
        info["largo_ida"] = ruta[2].get("largo_ida")
        info["largo_vuelta"] = ruta[2].get("largo_vuelta")
        info["vuelta"] = ruta[2].get("vuelta")
    return ruta, info


def ruta_a_b(desde, hasta, circuito="no"):
    import calles as K
    a, b = K.leer_coordenadas(desde), K.leer_coordenadas(hasta)
    if a is None or b is None:
        sys.exit("Escribe --desde y --hasta como 'lat, lon' o enlaces de Google Maps.")
    zona = K.zona_para_puntos(a, b)
    try:
        red = K.RedVial(zona)
        K.imagen_satelital(zona)
        ruta, info = trazar_ruta(red, a, b, circuito)
    except RuntimeError as e:
        sys.exit(f"No se pudo trazar la ruta: {e}")
    print(f"Ruta A → B{' → A' if info['circuito'] != 'no' else ''} en {zona.nombre}: "
          + " → ".join(dict.fromkeys(ruta[1])))
    if info.get("vuelta"):
        print(f"Regreso: {info['vuelta']}")
    return red, ruta, info


def ultima_sesion():
    import calles as K
    modo, zona, puntos = K.cargar_sesion()
    if modo != "ciudad" or zona is None:
        from evolucion import hay_entrenamiento_de_calles
        if not (getattr(C, "PLAN_AUTOMATICO", False) and hay_entrenamiento_de_calles()):
            return None, None, None
        zona, puntos = K.zona_para(C.ZONA_CALLES), None
    try:
        red = K.RedVial(zona)
    except Exception as e:
        print(f"No se pudo reabrir {zona.nombre} ({e}); se abre en terrenos.")
        return None, None, None
    print(f"Reabriendo la última sesión: calles reales de {zona.nombre}.")
    if not puntos:
        return red, None, None
    a, b = puntos[0], puntos[1]
    vuelta = puntos[2] if len(puntos) > 2 else "no"
    try:
        ruta, info = trazar_ruta(red, a, b, vuelta)
    except Exception:
        return red, None, None
    return red, ruta, info


def _extras_entrenador(dir_datos=None, procesos=1):
    kw = {}
    if dir_datos:
        kw["dir_datos"] = en_proyecto(dir_datos)
    if procesos and procesos > 1:
        kw["procesos"] = procesos
    return kw


def entrenar_consola(generaciones, poblacion, nuevo, semilla, red=None, ruta=None,
                     dir_datos=None, procesos=1):
    from evolucion import Entrenador, resumen_generacion

    extra = _extras_entrenador(dir_datos, procesos)
    e = Entrenador(poblacion, continuar=not nuevo, semilla=semilla,
                   modo="ciudad" if red else "terreno", red_vial=red, ruta=ruta, **extra)
    print(f"Entrenando {generaciones} generaciones de {e.n} motos "
          f"(desde la generación {e.generacion}, nivel {e.nivel})"
          + (f" con {procesos} procesos" if procesos > 1 else "") + "...\n")
    for _ in range(generaciones):
        r = e.correr_generacion()
        print(resumen_generacion(r), flush=True)
        if r.get("graduado") and e.modo == "terreno" and C.PASAR_A_CALLES:
            from evolucion import hay_entrenamiento_de_calles
            try:
                ya_hay = hay_entrenamiento_de_calles(**({"dir_datos": extra["dir_datos"]}
                                                       if "dir_datos" in extra else {}))
            except TypeError:
                ya_hay = hay_entrenamiento_de_calles()
            if not ya_hay:
                print(f"\n=== Pasa a calles reales de {C.ZONA_CALLES} ===\n", flush=True)
                e = Entrenador(poblacion, continuar=True, semilla=semilla, modo="ciudad",
                               red_vial=red_de_calles(C.ZONA_CALLES), **extra)
    from evolucion import ruta as archivo
    try:
        destino = archivo(C.ARCHIVO_MEJOR, e.modo, extra.get("dir_datos"))
    except TypeError:
        destino = archivo(C.ARCHIVO_MEJOR, e.modo)
    print(f"\nMejor moto guardada en: {destino}")
    print("Para verla: agrega --demo a las mismas opciones de este comando.")


def evaluar(a):
    import json
    try:
        import evaluacion
    except ImportError as err:
        sys.exit(f"Falta evaluacion.py ({err}).")
    argv = ["--modo", a.modo, "--pistas", str(a.pistas), "--ruidos", str(a.ruidos),
            "--sensores", a.sensores]
    niveles = [a.nivel] if a.nivel else None
    archivo = None
    if a.dir_datos:
        nombre = C.ARCHIVO_MEJOR if a.modo == "terreno" else \
            C.ARCHIVO_MEJOR.replace(".json", "_ciudad.json")
        archivo = os.path.join(en_proyecto(a.dir_datos), nombre)
        argv += ["--pesos", archivo]
    if niveles is None:
        try:
            ruta = archivo or os.path.join(AQUI,
                                           C.ARCHIVO_MEJOR if a.modo == "terreno"
                                           else C.ARCHIVO_MEJOR.replace(".json", "_ciudad.json"))
            with open(ruta, encoding="utf-8") as f:
                niveles = [max(1, int(json.load(f).get("nivel", 1)))]
        except (OSError, ValueError):
            niveles = [1]
    argv += ["--niveles", *map(str, niveles)]
    return evaluacion.main(argv)


def comparar(a):
    import experimentos as X
    return X.comparar(a.nivel, a.pistas, a.ruidos, a.procesos if a.procesos > 1 else (os.cpu_count() or 1),
                      (en_proyecto(a.dir_datos) if a.dir_datos else None) or os.path.join(X.AQUI, "resultados",
                                                  __import__("time").strftime("%Y%m%d_%H%M%S") + "_comparar"),
                      modo=a.modo, sensores=a.sensores)


def experimento(a):
    import experimentos as X
    X.lote(a.experimento, X.rango_semillas(a.semillas), a.generaciones, a.poblacion,
           procesos=a.procesos if a.procesos > 1 else min(5, os.cpu_count() or 1),
           pistas_eval=a.pistas if a.pistas_dado else 10,
           niveles_eval=[a.nivel] if a.nivel else None, raiz=en_proyecto(a.dir_datos) if a.dir_datos else None)


def reporte(a):
    try:
        import reporte_seguridad as RS
    except ImportError as err:
        sys.exit(f"Falta reporte_seguridad.py ({err}).")
    for nombre in ("main", "principal", "generar"):
        f = getattr(RS, nombre, None)
        if callable(f):
            return f([]) if nombre != "generar" else f()
    sys.exit("reporte_seguridad.py no expone main()/generar().")


def _acepta(f, nombre):
    import inspect
    try:
        return nombre in inspect.signature(f).parameters
    except (TypeError, ValueError):
        return False


def fijar_clima(texto):
    texto = texto.strip().lower().replace(" ", "_")
    if texto in ("auto", "automatico", "automático"):
        C.CLIMA_MANUAL = None
        C.CLIMA_AUTOMATICO = True
        return
    try:
        import clima
    except ImportError as err:
        sys.exit(f"Falta clima.py ({err}).")
    presets = list(getattr(clima, "PRESETS", {}))
    if presets and texto not in presets:
        sys.exit(f"No conozco el clima «{texto}». Opciones: auto, {', '.join(presets)}.")
    if texto == "despejado":
        C.CLIMA_AUTOMATICO, C.CLIMA_MANUAL = False, None
    else:
        C.CLIMA_AUTOMATICO, C.CLIMA_MANUAL = False, texto


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--sin-gui", type=int, metavar="N", help="entrenar N generaciones en consola")
    ap.add_argument("--demo", action="store_true", help="ver a la mejor moto guardada")
    ap.add_argument("--recorrido", action="store_true",
                    help="abrir directo el diálogo de recorrido (mejor moto del salón de la fama)")
    ap.add_argument("--clima", metavar="PRESET",
                    help="clima fijo para todas las pistas (preset de clima.py) o 'auto'")
    ap.add_argument("--nivel", type=int, help="nivel de las pistas de la demo / evaluación (1-8)")
    ap.add_argument("--nuevo", action="store_true", help="empezar desde cero")
    ap.add_argument("--poblacion", type=int, default=C.POBLACION)
    ap.add_argument("--semilla", type=int)
    ap.add_argument("--ciudad", metavar="ZONA", help="calles reales: nombre de la lista o 'lat, lon'")
    ap.add_argument("--desde", metavar="A", help="ruta A → B: punto de salida ('lat, lon' o enlace)")
    ap.add_argument("--hasta", metavar="B", help="ruta A → B: punto de llegada")
    ap.add_argument("--superficie", choices=("pavimento", "irregular", "variado"),
                    help="calles reales (fija a mano; sin esto: plan de estudios automático): "
                         "asfalto liso, relieve irregular sin obstáculos o terreno variado")
    ap.add_argument("--circuito", choices=("no", "misma", "otra"),
                    help="calles reales (fija a mano): sólo ida (no) o circuito A → B → A "
                         "regresando por la misma ruta o por otra (también --desde/--hasta)")
    g = ap.add_argument_group("MT-Bench")
    g.add_argument("--evaluar", action="store_true", help="suite de prueba reservada con IC")
    g.add_argument("--comparar", action="store_true", help="red vs PD vs aleatorio en la suite")
    g.add_argument("--pistas", type=int, default=None, help="pistas por nivel (evaluar: 20, comparar: 10)")
    g.add_argument("--ruidos", type=int, default=None, help="realizaciones de ruido por pista (evaluar: 5)")
    g.add_argument("--modo", choices=("terreno", "ciudad"), default="terreno")
    g.add_argument("--sensores", choices=("ideal", "realista"), default="ideal")
    g.add_argument("--procesos", type=int, default=0,
                   help="procesos en paralelo (0 = automático: hilos de la CPU − 1)")
    g.add_argument("--dir-datos", metavar="RUTA", help="carpeta de checkpoints/resultados alterna")
    g.add_argument("--experimento", nargs="?", const="base", metavar="NOMBRE",
                   help="lote multi-semilla (ver experimentos.py)")
    g.add_argument("--semillas", default="0-4", help="semillas del experimento, p. ej. 0-4 o 1,3,5")
    g.add_argument("--generaciones", type=int, default=20, help="generaciones por semilla del experimento")
    g.add_argument("--bench", action="store_true", help="medir rendimiento")
    g.add_argument("--reporte", action="store_true", help="reporte de seguridad")
    a = ap.parse_args()
    a.pistas_dado = a.pistas is not None
    if a.clima:
        fijar_clima(a.clima)
    if a.bench:
        import bench
        bench.principal([])
        return
    if a.reporte:
        reporte(a)
        return
    if a.evaluar:
        a.pistas, a.ruidos = a.pistas or 20, a.ruidos or 5
        evaluar(a)
        return
    if a.comparar:
        a.pistas, a.ruidos = a.pistas or 10, a.ruidos or 1
        comparar(a)
        return
    if a.experimento:
        experimento(a)
        return

    red = ruta = info = None
    if a.desde or a.hasta:
        if not (a.desde and a.hasta):
            sys.exit("Para una ruta A → B se necesitan --desde y --hasta.")
        red, ruta, info = ruta_a_b(a.desde, a.hasta, a.circuito or "no")
    elif a.ciudad:
        red = red_de_calles(a.ciudad)
    elif not a.sin_gui and not a.nuevo:
        red, ruta, info = ultima_sesion()
    if a.clima:
        fijar_clima(a.clima)
    if a.sin_gui or a.nuevo:
        C.PLAN_AUTOMATICO = True
    if a.superficie or a.circuito:
        C.PLAN_AUTOMATICO = False
        if a.superficie:
            C.CALLES_SUPERFICIE = a.superficie
        if a.circuito:
            C.CALLES_CIRCUITO = a.circuito

    if a.sin_gui:
        import paralelo as P
        entrenar_consola(a.sin_gui, a.poblacion, a.nuevo, a.semilla, red, ruta,
                         a.dir_datos, a.procesos or P.procesos_disponibles())
        return

    import interfaz
    if a.recorrido:
        kw = dict(red_vial=red, ruta=(dict(info, ruta=ruta, red=red) if ruta else None))
        if _acepta(interfaz.ejecutar, "recorrido"):
            interfaz.ejecutar(recorrido=True, **kw)
        else:
            interfaz.ejecutar(demo=True, nivel_demo=a.nivel, **kw)
        return
    if a.demo:
        interfaz.ejecutar(demo=True, nivel_demo=a.nivel, red_vial=red,
                          ruta=(dict(info, ruta=ruta, red=red) if ruta else None))
        return
    from evolucion import Entrenador
    e = Entrenador(a.poblacion, continuar=not a.nuevo, semilla=a.semilla,
                   modo="ciudad" if red else "terreno", red_vial=red, ruta=ruta,
                   **_extras_entrenador(a.dir_datos, 1))
    if e.generacion > 1:
        print(f"Continuando la evolución guardada: generación {e.generacion}, nivel {e.nivel}.")
    interfaz.ejecutar(entrenador=e, ruta=(dict(info, ruta=ruta, red=red) if ruta else None))


if __name__ == "__main__":
    main()
