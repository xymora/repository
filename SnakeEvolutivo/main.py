import argparse

import config as C


def main():
    ap = argparse.ArgumentParser(description="Snake evolutivo: serpientes que aprenden por generaciones")
    ap.add_argument("--nuevo", action="store_true", help="empezar la evolución desde cero")
    ap.add_argument("--demo", action="store_true", help="abrir viendo a la campeona guardada")
    ap.add_argument("--turbo", action="store_true", help="abrir entrenando sin animación")
    ap.add_argument("--poblacion", type=int, default=C.POBLACION)
    ap.add_argument("--semilla", type=int, default=None)
    a = ap.parse_args()

    from evolucion import Entrenador
    from interfaz import Aplicacion
    entrenador = Entrenador(a.poblacion, continuar=not a.nuevo, semilla=a.semilla)
    if a.nuevo:
        entrenador.reiniciar()
    Aplicacion(entrenador, demo=a.demo, turbo=a.turbo).ejecutar()


if __name__ == "__main__":
    main()
