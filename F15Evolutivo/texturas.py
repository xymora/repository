import math

import numpy as np
import pygame


def ruido_periodico(n, beta, rng):
    w = rng.standard_normal((n, n))
    f = np.fft.fft2(w)
    kx = np.fft.fftfreq(n)[:, None]
    ky = np.fft.fftfreq(n)[None, :]
    k = np.sqrt(kx * kx + ky * ky)
    k[0, 0] = 1
    f *= 1 / k ** beta
    f[0, 0] = 0
    r = np.real(np.fft.ifft2(f))
    r = (r - r.min()) / (r.max() - r.min())
    return r


def ruido_rgba(n=256, semilla=5):
    rng = np.random.default_rng(semilla)
    canales = [ruido_periodico(n, b, rng) for b in (1.6, 1.3, 1.1, 0.8)]
    return (np.stack(canales, -1) * 255).astype(np.uint8)


def mancha(n=128, semilla=3, bordes=0.5):
    rng = np.random.default_rng(semilla)
    y, x = np.mgrid[0:n, 0:n] / (n - 1) * 2 - 1
    r = np.sqrt(x * x + y * y)
    ruido = ruido_periodico(n, 1.4, rng)
    a = np.clip(1 - r - (ruido - 0.5) * bordes, 0, 1)
    a = a ** 1.4
    luz = np.clip(0.75 - y * 0.35 + (ruido - 0.5) * 0.5, 0, 1)
    img = np.stack([luz, luz, luz, a], -1)
    return (img * 255).astype(np.uint8)


def _digitos(texto, alto_px, ancho_px):
    pygame.font.init()
    f = pygame.font.SysFont("arial", 200, bold=True)
    s = f.render(texto, True, (255, 255, 255))
    s = pygame.transform.smoothscale(s, (ancho_px, alto_px))
    a = pygame.surfarray.array_alpha(s) if s.get_flags() & pygame.SRCALPHA else pygame.surfarray.array3d(s)[..., 0]
    return a.astype(np.float32) / 255.0


def pista(largo, ancho, numero, semilla=9, px_m=0.5):
    rng = np.random.default_rng(semilla)
    margen = 8.0
    W = int(round((ancho + 2 * margen) / px_m))
    H = int(round(largo / px_m))
    s = (np.arange(H) + 0.5) * px_m
    l = (np.arange(W) + 0.5) * px_m - (ancho / 2 + margen)
    L, S = np.meshgrid(l, s)
    base = 0.24 + 0.05 * (rng.random((H, W)) - 0.5)
    parche = np.kron(rng.random((H // 40 + 1, W // 40 + 1)), np.ones((40, 40)))[:H, :W]
    base += 0.035 * (parche - 0.5)
    lon = np.interp(s, np.linspace(0, largo, 30), 0.03 * rng.standard_normal(30))
    base += lon[:, None]
    for extremo in (S, largo - S):
        zona = np.exp(-((extremo - 520) / 330) ** 2) * np.exp(-(L / 8.0) ** 2)
        base -= 0.13 * zona * (0.6 + 0.4 * rng.random((H, W)))
    hombro = np.abs(L) > ancho / 2
    base = np.where(hombro, 0.33 + 0.04 * (rng.random((H, W)) - 0.5), base)
    pintura = np.zeros((H, W))
    borde = np.abs(np.abs(L) - (ancho / 2 - 0.6)) < 0.45
    pintura = np.maximum(pintura, borde)
    centro = (np.abs(L) < 0.45) & ((S % 60) < 36) & (S > 90) & (S < largo - 90)
    pintura = np.maximum(pintura, centro)
    for extremo in (S, largo - S):
        piano = (extremo > 6) & (extremo < 36) & (np.abs(L) > 1.5) & (np.abs(L) < ancho / 2 - 2.5) & \
            (((np.abs(L) - 1.5) % 3.6) < 1.8)
        pintura = np.maximum(pintura, piano)
        mira = (extremo > 400) & (extremo < 445) & (np.abs(L) > 6) & (np.abs(L) < 15)
        pintura = np.maximum(pintura, mira)
        for d, n_barras in ((150, 3), (300, 3), (600, 2), (750, 2), (900, 1)):
            for b in range(n_barras):
                lmin = 4 + b * 3.0
                tdz = (extremo > d) & (extremo < d + 22) & (np.abs(L) > lmin) & (np.abs(L) < lmin + 1.8)
                pintura = np.maximum(pintura, tdz)
        transversal = (extremo > 1.0) & (extremo < 4.0) & (np.abs(L) < ancho / 2 - 1)
        pintura = np.maximum(pintura, transversal)
    alto_d, ancho_d = int(18 / px_m), int(12 / px_m)
    for k, txt in enumerate((f"{numero:02d}", f"{(numero + 18 - 1) % 36 + 1:02d}")):
        d = _digitos(txt, alto_d, ancho_d).T
        d = d[::-1, :] if k == 0 else d[:, ::-1]
        s0 = int(48 / px_m) if k == 0 else H - int(48 / px_m) - alto_d
        c0 = W // 2 - ancho_d // 2
        pintura[s0:s0 + alto_d, c0:c0 + ancho_d] = np.maximum(pintura[s0:s0 + alto_d, c0:c0 + ancho_d], d)
    gastado = 0.75 + 0.25 * rng.random((H, W))
    color = np.stack([base, base, base * 1.02], -1)
    blanco = np.array([0.86, 0.86, 0.84])
    color = color * (1 - pintura[..., None] * gastado[..., None]) + blanco * (pintura * gastado)[..., None]
    img = (np.clip(color, 0, 1) * 255).astype(np.uint8)
    return img, margen


def concreto(n=256, semilla=4):
    rng = np.random.default_rng(semilla)
    r = ruido_periodico(n, 1.2, rng)
    juntas = np.zeros((n, n))
    juntas[::64, :] = 1
    juntas[:, ::64] = 1
    g = 0.42 + 0.12 * (r - 0.5) + 0.04 * (rng.random((n, n)) - 0.5) - 0.1 * juntas
    return (np.clip(np.stack([g, g * 0.99, g * 0.96], -1), 0, 1) * 255).astype(np.uint8)
