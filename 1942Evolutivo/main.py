import argparse
import multiprocessing as mp
import sys

import config as C


def main():
    ap = argparse.ArgumentParser(description="1942 evolutivo: pilotos que aprenden por generaciones")
    ap.add_argument("--nuevo", action="store_true", help="empezar la evolución desde cero")
    ap.add_argument("--campeona", action="store_true", help="abrir viendo a la campeona guardada")
    ap.add_argument("--jugar", action="store_true", help="abrir pilotando tú")
    ap.add_argument("--turbo", action="store_true", help="abrir entrenando sin animación")
    ap.add_argument("--poblacion", type=int, default=C.POBLACION)
    ap.add_argument("--semilla", type=int, default=None)
    a = ap.parse_args()
    for flujo in (sys.stdout, sys.stderr):
        try:
            flujo.reconfigure(errors="replace")
        except (AttributeError, ValueError):
            pass

    from evolucion import Entrenador
    from interfaz import Aplicacion
    entrenador = Entrenador(continuar=not a.nuevo, semilla=a.semilla, poblacion=a.poblacion)
    if a.nuevo:
        entrenador.reiniciar()
    vista = "humano" if a.jugar else ("campeona" if a.campeona else "generacion")
    Aplicacion(entrenador, vista=vista, turbo=a.turbo).ejecutar()


if __name__ == "__main__":
    mp.freeze_support()
    main()
