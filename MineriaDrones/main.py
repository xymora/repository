import argparse
import os
import sys


def main():
    ap = argparse.ArgumentParser(description="Minería con drones: topografía, LiDAR, modelos 3D, comparación e inspección")
    ap.add_argument("--visor", default=None, help="abre el visor 3D con un archivo vista3d.npz")
    ap.add_argument("--capturas", default=None, help="con --visor: guarda capturas de cada capa en esa carpeta y sale")
    ap.add_argument("--proyectos", default=None, help="carpeta de proyectos (por defecto proyectos\)")
    ap.add_argument("--google", nargs=2, type=float, metavar=("LAT", "LON"), help="abre el mapa de Google del sitio")
    ap.add_argument("--nombre", default="Sitio")
    ap.add_argument("--ancho", type=float, default=1600.0)
    a = ap.parse_args()
    if a.google:
        import mapa_google
        mapa_google.abrir(a.google[0], a.google[1], a.nombre, a.ancho, a.capturas)
        return
    if a.visor:
        import visor3d
        visor3d.main([a.visor] + (["--capturas", a.capturas] if a.capturas else []))
        return
    import interfaz
    interfaz.App(a.proyectos).correr()


if __name__ == "__main__":
    main()
