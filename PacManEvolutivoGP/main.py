import argparse

import config as C


def main():
    ap = argparse.ArgumentParser(description="Pac-Man evolutivo GP (programación genética)")
    ap.add_argument("--rapido", action="store_true", help="abrir en modo rápido (sin animación)")
    ap.add_argument("--nuevo", action="store_true", help="empezar la evolución desde cero")
    ap.add_argument("--demo", action="store_true", help="ver a la mejor guardada")
    ap.add_argument("--generaciones", action="store_true", help="carrera de generaciones")
    ap.add_argument("--poblacion", type=int, default=C.POBLACION)
    ap.add_argument("--semilla", type=int, default=None)
    a = ap.parse_args()

    from evolucion import Entrenador
    import juego
    e = Entrenador(a.poblacion, continuar=not a.nuevo, semilla=a.semilla)
    juego.ejecutar(e, demo=a.demo, generaciones=a.generaciones, rapido=a.rapido)


if __name__ == "__main__":
    main()
