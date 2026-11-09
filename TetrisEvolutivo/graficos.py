import struct
import zlib

import numpy as np

from tema import _difuminar, rgb

COLOR_NIVEL = ("#2fd3f5", "#3fe08a", "#ffd23f", "#ff9a36", "#4683ff", "#b065ff", "#ff4f64", "#f5b400")


def png(img):
    alto, ancho = img.shape[:2]
    crudo = b"".join(b"\x00" + img[y].tobytes() for y in range(alto))

    def bloque(tipo, datos):
        return (struct.pack(">I", len(datos)) + tipo + datos
                + struct.pack(">I", zlib.crc32(tipo + datos) & 0xFFFFFFFF))

    return (b"\x89PNG\r\n\x1a\n" + bloque(b"IHDR", struct.pack(">IIBBBBB", ancho, alto, 8, 6, 0, 0, 0))
            + bloque(b"IDAT", zlib.compress(crudo, 6)) + bloque(b"IEND", b""))


def ppm(img):
    alto, ancho = img.shape[:2]
    return f"P6 {ancho} {alto} 255\n".encode() + np.ascontiguousarray(np.clip(img, 0, 255), np.uint8).tobytes()


def _malla(s):
    yy, xx = np.mgrid[0:s, 0:s].astype(np.float32)
    return (xx + 0.5) / s, (yy + 0.5) / s


def _esquinas(s, radio):
    yy, xx = np.mgrid[0:s, 0:s].astype(np.float32) + 0.5
    cx = np.clip(xx, radio, s - radio)
    cy = np.clip(yy, radio, s - radio)
    d = np.hypot(xx - cx, yy - cy)
    return np.clip(radio - d + 0.5, 0, 1)


def bloque(color, s):
    u, v = _malla(s)
    base = np.array(rgb(color), np.float32)
    blanco, negro = np.full(3, 255, np.float32), np.zeros(3, np.float32)
    img = base * (1.18 - 0.36 * v)[..., None]
    bisel = max(2, round(s * 0.13)) / s
    arriba, abajo, izq, der = v, 1 - v, u, 1 - u
    borde = np.minimum(np.minimum(arriba, abajo), np.minimum(izq, der))
    en_bisel = borde < bisel
    luz = en_bisel & ((arriba == borde) | (izq == borde))
    sombra = en_bisel & ~luz
    img[luz] = img[luz] * 0.45 + blanco * 0.55 * (0.75 + 0.25 * (1 - v[luz]))[..., None]
    img[sombra] = img[sombra] * 0.55 + negro * 0.45
    cara = ~en_bisel
    brillo = np.exp(-(((u - 0.34) / 0.30) ** 2 + ((v - 0.28) / 0.20) ** 2))
    img[cara] += (brillo[cara] * 70)[..., None]
    reflejo = cara & (v < 0.5) & (u + v < 0.85)
    img[reflejo] += 14
    contorno = borde < 1.2 / s
    img[contorno] = img[contorno] * 0.35
    alfa = _esquinas(s, max(2, s * 0.12)) * 255
    return np.dstack([np.clip(img, 0, 255), alfa]).astype(np.uint8)


def fantasma(color, s):
    u, v = _malla(s)
    base = np.array(rgb(color), np.float32)
    borde = np.minimum(np.minimum(u, 1 - u), np.minimum(v, 1 - v)) * s
    alfa = np.where(borde < 2.2, 210, 46).astype(np.float32)
    img = np.broadcast_to(base * 1.1, (s, s, 3)).copy()
    alfa *= _esquinas(s, max(2, s * 0.12))
    return np.dstack([np.clip(img, 0, 255), alfa]).astype(np.uint8)


def destello(ancho, alto, intensidad):
    u, v = np.meshgrid(np.linspace(-1, 1, ancho), np.linspace(-1, 1, alto))
    nucleo = np.exp(-(v / 0.55) ** 2) * (1 - 0.35 * np.abs(u))
    img = np.empty((alto, ancho, 3), np.float32)
    img[:] = (255, 255, 255)
    alfa = np.clip(nucleo * 255 * intensidad, 0, 255)
    return np.dstack([img, alfa]).astype(np.uint8)


def chispa(color, s=6):
    u, v = _malla(s)
    d = np.hypot(u - 0.5, v - 0.5) * 2
    base = np.array(rgb(color), np.float32)
    img = base * 0.5 + 255 * 0.5 * np.clip(1 - d, 0, 1)[..., None]
    alfa = np.clip(1 - d, 0, 1) ** 0.8 * 255
    return np.dstack([np.clip(img, 0, 255), alfa]).astype(np.uint8)


def fondo(ancho, alto, pozo, filas, celda, acento, semilla=3):
    al = np.random.default_rng(semilla)
    yy, xx = np.mgrid[0:alto, 0:ancho].astype(np.float32)
    arriba, abajo = np.array(rgb("#0d1119"), np.float32), np.array(rgb("#090b10"), np.float32)
    t = (yy / alto)[..., None]
    img = arriba * (1 - t) + abajo * t
    img += al.normal(0, 1.6, (alto, ancho))[..., None]
    x0, y0, x1, y1 = pozo
    ac = np.array(rgb(acento), np.float32)
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    halo = np.exp(-(((xx - cx) / (ancho * 0.42)) ** 2 + ((yy - cy) / (alto * 0.55)) ** 2))
    img += halo[..., None] * ac * 0.10
    marco = np.zeros((alto, ancho), np.float32)
    marco[y0 - 3:y1 + 3, x0 - 3:x1 + 3] = 1
    marco[y0:y1, x0:x1] = 0
    resplandor = _difuminar(marco, 9)
    img += resplandor[..., None] * ac * 0.9
    dentro = (xx >= x0) & (xx < x1) & (yy >= y0) & (yy < y1)
    fx, fy = (xx - x0) % celda, (yy - y0) % celda
    pozo_img = np.empty_like(img)
    pozo_img[:] = rgb("#06080c")
    sombra = np.clip(1 - (yy - y0) / (celda * 3), 0, 1) * 0.55
    pozo_img *= (1 - sombra)[..., None]
    rejilla = (fx < 1) | (fy < 1)
    pozo_img[rejilla] = rgb("#121722")
    punto = (np.abs(fx - celda / 2) < 1) & (np.abs(fy - celda / 2) < 1)
    pozo_img[punto] = rgb("#1b2230")
    img[dentro] = pozo_img[dentro]
    linea = (marco > 0) & ~dentro
    img[linea] = ac * 0.55 + np.array(rgb("#ffffff"), np.float32) * 0.12
    if filas:
        techo = (yy >= y0 - 1) & (yy < y0 + 1) & (xx >= x0) & (xx < x1)
        img[techo] = ac * 0.8
    d = np.hypot(xx - ancho / 2, yy - alto / 2) / (ancho * 0.75)
    img *= (1 - np.clip(d, 0, 1) ** 2.2 * 0.45)[..., None]
    return img


def tarjeta(img, x0, y0, x1, y1, color="#141821", borde="#262b36", radio=8):
    alto, ancho = img.shape[:2]
    yy, xx = np.mgrid[0:alto, 0:ancho].astype(np.float32) + 0.5
    cx = np.clip(xx, x0 + radio, x1 - radio)
    cy = np.clip(yy, y0 + radio, y1 - radio)
    d = np.hypot(xx - cx, yy - cy)
    dentro = np.clip(radio - d, 0, 1)
    filo = np.clip(radio - d, 0, 1) - np.clip(radio - 1.2 - d, 0, 1)
    c = np.array(rgb(color), np.float32)
    b = np.array(rgb(borde), np.float32)
    img[:] = img * (1 - dentro[..., None] * 0.92) + c * dentro[..., None] * 0.92
    img[:] = img * (1 - filo[..., None]) + b * filo[..., None]
    return img
