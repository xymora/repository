import argparse
import multiprocessing as mp


def main():
    ap = argparse.ArgumentParser(description="Contra evolutivo: comandos que aprenden por generaciones")
    ap.add_argument("--jugadores", type=int, choices=(1, 2), default=1, help="modo con el que abre la ventana")
    ap.add_argument("--nuevo", action="store_true", help="empezar ese modo desde cero")
    ap.add_argument("--campeona", action="store_true", help="abrir viendo a la campeona guardada")
    ap.add_argument("--jugar", action="store_true", help="abrir jugando tú como jugador 1")
    ap.add_argument("--semilla", type=int, default=None)
    a = ap.parse_args()

    from interfaz import Aplicacion
    vista = "humano" if a.jugar else ("campeona" if a.campeona else "mejor")
    Aplicacion(a.jugadores, nuevo=a.nuevo, semilla=a.semilla, vista=vista).ejecutar()


if __name__ == "__main__":
    mp.freeze_support()
    main()
