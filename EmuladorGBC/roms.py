import os
import shutil

import config as C
from consola import EXTENSIONES, cabecera, leer_rom


def es_rom(nombre):
    n = nombre.lower()
    return n.endswith(EXTENSIONES) or n.endswith(".zip")


def biblioteca():
    lista = []
    if not os.path.isdir(C.CARPETA_ROMS):
        return lista
    for n in sorted(os.listdir(C.CARPETA_ROMS), key=str.lower):
        if not es_rom(n):
            continue
        ruta = os.path.join(C.CARPETA_ROMS, n)
        try:
            info = cabecera(leer_rom(ruta))
        except Exception as e:
            info = {"titulo": "ilegible", "id": None, "error": str(e), "cgb": False}
        lista.append({"archivo": n, "ruta": ruta, **info})
    return lista


def agregar(ruta_origen):
    os.makedirs(C.CARPETA_ROMS, exist_ok=True)
    cabecera(leer_rom(ruta_origen))
    destino = os.path.join(C.CARPETA_ROMS, os.path.basename(ruta_origen))
    if os.path.abspath(destino) != os.path.abspath(ruta_origen):
        shutil.copy2(ruta_origen, destino)
    return destino


def borrar(nombre):
    try:
        os.remove(os.path.join(C.CARPETA_ROMS, nombre))
    except OSError:
        pass
