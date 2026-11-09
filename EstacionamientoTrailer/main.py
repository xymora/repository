import argparse
import random
import sys

import config as C

NOMBRE_MODO = {"frente": "de frente", "reversa": "en reversa"}
NOMBRE_REM = {1: "1 remolque", 2: "2 remolques"}


def entrenar_consola(generaciones, poblacion, continuar, modo, remolques, lugar, cajon,
                     tamano):
    from evolucion import Entrenador, archivo_mejor, resumen_generacion

    e = Entrenador(poblacion, continuar, modo, remolques, lugar, cajon, tamano)
    print(f"Entrenando {generaciones} generaciones de {poblacion} tractocamiones con "
          f"{NOMBRE_REM[remolques]} para estacionarse {NOMBRE_MODO[modo]}...\n")
    for _ in range(generaciones):
        e.generacion.correr()
        s = e.cerrar_generacion()
        print(resumen_generacion(s), flush=True)
    r = e.record
    print()
    if r and r["estacionado"]:
        print(f"Mejor resultado (generación {r['generacion']}): se estaciona "
              f"{NOMBRE_MODO[modo]} en {r['segundos']} s con {r['maniobras']} maniobra(s), "
              f"a {r['desvio_cm']} cm del centro y {r['error_grados']}° de inclinación.")
        print("Plan de maniobras:")
        for i, m in enumerate(r.get("plan", []), 1):
            print(f"  {i}. {m}")
    else:
        print("Todavía no logra estacionarse; prueba con más generaciones.")
    print(f"Plan guardado en: {archivo_mejor(modo, remolques)}")


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    p = argparse.ArgumentParser(description="Estacionamiento evolutivo de tractocamión")
    p.add_argument("--remolques", type=int, choices=C.OPCIONES_REMOLQUES,
                   default=C.NUM_REMOLQUES, help="1 o 2 remolques (también en la ventana)")
    p.add_argument("--modo", choices=C.MODOS, default=C.MODO_ESTACIONAR,
                   help="estacionarse de frente o en reversa (también en la ventana)")
    p.add_argument("--tamano", choices=C.OPCIONES_TAMANO, default=C.TAMANO,
                   help="tamaño del cajón: chico, normal, grande o azar (cambia cada generación)")
    p.add_argument("--lugar", choices=C.LUGARES, default=C.LUGAR,
                   help="asignado: el lugar se elige; camara: queda libre uno al azar y "
                        "el camión lo busca con su cámara")
    p.add_argument("--cajon", type=int, metavar="N", help="cajón libre asignado (1, 2, ...)")
    p.add_argument("--demo", action="store_true", help="ver el mejor plan guardado")
    p.add_argument("--continuar", action="store_true",
                   help="seguir donde se quedó (es lo predeterminado)")
    p.add_argument("--nuevo", action="store_true",
                   help="empezar la evolución desde la generación 1 (ignora el avance guardado)")
    p.add_argument("--sin-gui", type=int, metavar="N",
                   help="entrenar N generaciones sin ventana")
    p.add_argument("--poblacion", type=int, default=C.POBLACION)
    p.add_argument("--semilla", type=int, help="semilla aleatoria (reproducible)")
    args = p.parse_args()

    if args.semilla is not None:
        random.seed(args.semilla)

    cajon = None if args.cajon is None else args.cajon - 1
    lugar = "asignado" if cajon is not None else args.lugar
    if args.sin_gui:
        entrenar_consola(args.sin_gui, args.poblacion, not args.nuevo, args.modo,
                         args.remolques, lugar, cajon, args.tamano)
        return

    from interfaz import Aplicacion
    Aplicacion(demo=args.demo, continuar=not args.nuevo, poblacion=args.poblacion,
               modo=args.modo, remolques=args.remolques, lugar=lugar, objetivo=cajon,
               tamano=args.tamano).ejecutar()


if __name__ == "__main__":
    main()
