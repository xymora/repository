import argparse
import os
import subprocess
import sys

import config as C


def main():
    ap = argparse.ArgumentParser(description="Espectáculo de drones: diseñador y visor 3D")
    ap.add_argument("--ver", metavar="SHOW_JSON", help="calcula el show indicado y lo abre en el visor 3D")
    ap.add_argument("--visor", action="store_true", help="abre el visor 3D con el último plan calculado")
    a, resto = ap.parse_known_args()
    if a.ver or a.visor:
        args = [sys.executable, os.path.join(C.RAIZ, "visor.py"), a.ver or C.PLAN_ACTUAL] + resto
        sys.exit(subprocess.call(args, cwd=C.RAIZ))
    import editor
    editor.main()


if __name__ == "__main__":
    main()
