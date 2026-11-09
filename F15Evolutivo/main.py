import argparse
import multiprocessing as mp
import sys

import config as C


def main():
    ap = argparse.ArgumentParser(description="F-15 Eagle evolutivo: simulador de vuelo desde la cabina")
    ap.add_argument("--nuevo", action="store_true", help="empezar la evolución desde cero")
    ap.add_argument("--jugar", action="store_true", help="abrir pilotando la lección 1")
    ap.add_argument("--libre", action="store_true", help="abrir en vuelo libre")
    ap.add_argument("--ia", action="store_true", help="abrir viendo a la IA aprender")
    ap.add_argument("--mision", default=None, help="abrir pilotando esta misión (número o id, ver --listar)")
    ap.add_argument("--ver", default=None, help="abrir viendo a la IA volar esta misión (número o id)")
    ap.add_argument("--curriculo", choices=("secuencial", "mezcla"), default=None,
                    help="cómo elige la IA qué misión entrenar")
    ap.add_argument("--entrenar", default=None, help="entrenar a la IA sólo en esta misión (número o id)")
    ap.add_argument("--listar", action="store_true", help="mostrar las misiones de config_misiones y salir")
    ap.add_argument("--rapido", action="store_true",
                    help="entrenar las 13 misiones sin gráficos (más opciones: python entrenar_rapido.py -h)")
    ap.add_argument("--ventana", action="store_true", help="ventana de 1280x720")
    ap.add_argument("--resolucion", default=None, help="tamaño de la ventana, p. ej. 1920x1080")
    ap.add_argument("--pantalla-completa", action="store_true", help="ocupar toda la pantalla sin bordes")
    ap.add_argument("--poblacion", type=int, default=C.POBLACION)
    ap.add_argument("--semilla", type=int, default=None)
    ap.add_argument("--datos", default=None, help=argparse.SUPPRESS)
    a = ap.parse_args()
    for flujo in (sys.stdout, sys.stderr):
        try:
            flujo.reconfigure(errors="replace")
        except (AttributeError, ValueError):
            pass

    import catalogo as K
    if a.listar:
        for m in sorted(K.MISIONES.values(), key=lambda m: m["orden"]):
            marca = "currículo IA" if m["curriculo"] else ("sólo humano" if not m["ia"] else "")
            print(f"{m['numero']:3d}  {m['id']:<16} {m['nombre']:<32} {m['duracion']:5.0f} s  {marca}")
        return
    resolucion = None
    if a.resolucion:
        try:
            resolucion = tuple(int(v) for v in a.resolucion.lower().split("x"))
            assert len(resolucion) == 2
        except (ValueError, AssertionError):
            ap.error("--resolucion debe ser ANCHOxALTO, p. ej. 1920x1080")
    for opcion in ("mision", "ver", "entrenar"):
        valor = getattr(a, opcion)
        if valor is not None and K.buscar(valor) is None:
            ap.error(f"--{opcion}: no existe la misión «{valor}» (usa --listar)")
    if a.entrenar is not None and K.buscar(a.entrenar) not in K.CURRICULO:
        ap.error("--entrenar: esa misión no está en el currículo de la IA")

    if a.rapido:
        from entrenar_rapido import entrenar
        if not entrenar(nuevo=a.nuevo, semilla=a.semilla, dir_datos=a.datos):
            return
        a.nuevo = False

    from evolucion import Entrenador
    from interfaz import Aplicacion
    entrenador = Entrenador(continuar=not a.nuevo, semilla=a.semilla, poblacion=a.poblacion, dir_datos=a.datos)
    if a.nuevo:
        entrenador.reiniciar()
    if a.entrenar is not None:
        entrenador.fijar_modo("fija", K.buscar(a.entrenar))
    elif a.curriculo:
        entrenador.fijar_modo(a.curriculo)
    mision = None
    if a.mision is not None:
        modo, mision = "humano", K.buscar(a.mision)
    elif a.ver is not None:
        modo, mision = "ver", K.buscar(a.ver)
    else:
        modo = "humano" if a.jugar else ("libre" if a.libre else ("ia" if a.ia else "menu"))
    while True:
        app = Aplicacion(entrenador, modo=modo, ventana=a.ventana, resolucion=resolucion,
                         completa=a.pantalla_completa, mision=mision)
        app.ejecutar()
        if not app.rapido:
            break
        from entrenar_rapido import entrenar
        if not entrenar(dir_datos=a.datos):
            break
        entrenador = Entrenador(continuar=True, semilla=a.semilla, poblacion=a.poblacion, dir_datos=a.datos)
        modo, mision = "menu", None


if __name__ == "__main__":
    mp.freeze_support()
    main()
