import argparse
import random
import sys

import config as C

NOMBRE_MODO = {"frente": "de frente", "reversa": "en reversa"}


def entrenar_consola(generaciones, poblacion, continuar, modo, lugar, cajon):
    from evolucion import Entrenador, archivo_mejor, resumen_generacion

    e = Entrenador(poblacion, continuar, modo, lugar, cajon)
    print(f"Entrenando {generaciones} generaciones de {poblacion} autos para "
          f"estacionarse {NOMBRE_MODO[modo]}...\n")
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
    print(f"Plan guardado en: {archivo_mejor(modo)}")


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    p = argparse.ArgumentParser(description="Estacionamiento evolutivo")
    p.add_argument("--modo", choices=C.MODOS, default=C.MODO_ESTACIONAR,
                   help="estacionarse de frente o en reversa (también se elige en la ventana)")
    p.add_argument("--lugar", choices=C.LUGARES, default=C.LUGAR,
                   help="asignado: el lugar se elige; camara: queda libre uno al azar y "
                        "el auto lo busca con su cámara")
    p.add_argument("--cajon", type=int, metavar="N",
                   help=f"cajón libre asignado (1..{C.NUM_CAJONES})")
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
        entrenar_consola(args.sin_gui, args.poblacion, not args.nuevo, args.modo, lugar, cajon)
        return

    from interfaz import Aplicacion
    Aplicacion(demo=args.demo, continuar=not args.nuevo, poblacion=args.poblacion,
               modo=args.modo, lugar=lugar, objetivo=cajon).ejecutar()


if __name__ == "__main__":
    main()
