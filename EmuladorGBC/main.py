import argparse
import multiprocessing as mp
import os
import sys


def main():
    ap = argparse.ArgumentParser(description="Emulador Game Boy Color con una IA que aprende a jugar")
    ap.add_argument("rom", nargs="?", help="ROM .gb/.gbc/.zip para abrir directamente")
    ap.add_argument("--nuevo", action="store_true", help="empezar la IA de este juego desde cero")
    ap.add_argument("--jugar", action="store_true", help="abrir jugando tú")
    ap.add_argument("--turbo", action="store_true", help="abrir entrenando sin animación")
    ap.add_argument("--entrenar", action="store_true", help="empezar a entrenar al abrir")
    a = ap.parse_args()
    for flujo in (sys.stdout, sys.stderr):
        try:
            flujo.reconfigure(errors="replace")
        except (AttributeError, ValueError):
            pass
    import config as C
    os.makedirs(C.CARPETA_ROMS, exist_ok=True)
    os.makedirs(C.CARPETA_DATOS, exist_ok=True)
    from interfaz import Aplicacion
    vista = "jugar" if a.jugar else ("turbo" if a.turbo else "ia")
    Aplicacion(rom=a.rom, vista=vista, nuevo=a.nuevo, entrenar=a.entrenar or a.turbo).ejecutar()


if __name__ == "__main__":
    mp.freeze_support()
    main()
