# -*- coding: utf-8 -*-
# Descarga YOLOv4-tiny (config y pesos) dentro de la carpeta modelos/.
# El modelo no se versiona en el repositorio; ejecuta este script una vez.
import os
import urllib.request

BASE = os.path.dirname(os.path.abspath(__file__))
MODELOS = os.path.join(BASE, "modelos")
ARCHIVOS = {
    "yolov4-tiny.cfg":
        "https://raw.githubusercontent.com/AlexeyAB/darknet/master/cfg/yolov4-tiny.cfg",
    "yolov4-tiny.weights":
        "https://github.com/AlexeyAB/darknet/releases/download/"
        "darknet_yolo_v4_pre/yolov4-tiny.weights",
}


def main():
    os.makedirs(MODELOS, exist_ok=True)
    for nombre, url in ARCHIVOS.items():
        destino = os.path.join(MODELOS, nombre)
        if os.path.exists(destino) and os.path.getsize(destino) > 0:
            print("ya existe:", nombre)
            continue
        print("descargando %s ..." % nombre)
        urllib.request.urlretrieve(url, destino)
        print("  guardado en", destino)
    print("Listo. Si falta el modelo, el programa usa HOG como respaldo.")


if __name__ == "__main__":
    main()
