import numpy as np

import procesamiento as PR

PALETAS = {
    "hipso": [(0.0, (38, 70, 110)), (0.18, (52, 120, 120)), (0.35, (98, 160, 92)), (0.55, (196, 190, 110)),
              (0.75, (176, 120, 70)), (0.9, (150, 110, 100)), (1.0, (240, 236, 232))],
    "pendiente": [(0.0, (40, 120, 70)), (0.3, (120, 190, 80)), (0.5, (245, 210, 60)), (0.7, (245, 130, 40)),
                  (0.85, (220, 50, 50)), (1.0, (120, 20, 60))],
    "termica": [(0.0, (0, 0, 4)), (0.15, (40, 11, 84)), (0.35, (101, 21, 110)), (0.55, (159, 42, 99)),
                (0.7, (212, 72, 66)), (0.85, (245, 125, 21)), (0.95, (250, 193, 39)), (1.0, (252, 255, 164))],
    "densidad": [(0.0, (68, 1, 84)), (0.25, (59, 82, 139)), (0.5, (33, 145, 140)), (0.75, (94, 201, 98)),
                 (1.0, (253, 231, 37))],
    "dod": [(0.0, (120, 10, 20)), (0.25, (220, 60, 50)), (0.45, (245, 190, 170)), (0.5, (236, 236, 236)),
            (0.55, (170, 200, 245)), (0.75, (50, 110, 220)), (1.0, (10, 30, 120))],
}


def lut(nombre, n=256):
    pts = PALETAS[nombre]
    xs = np.array([p[0] for p in pts])
    cs = np.array([p[1] for p in pts], dtype=np.float32)
    t = np.linspace(0, 1, n)
    return np.stack([np.interp(t, xs, cs[:, k]) for k in range(3)], axis=1).astype(np.uint8)


def aplicar(valores, nombre, vmin, vmax, nan=(22, 25, 32)):
    v = np.asarray(valores, dtype=np.float32)
    t = np.clip((v - vmin) / max(vmax - vmin, 1e-6), 0, 1)
    idx = np.nan_to_num(t * 255, nan=0).astype(np.int32)
    rgb = lut(nombre)[idx]
    rgb[~np.isfinite(v)] = nan
    return rgb


def con_sombra(rgb, sombra, fuerza=0.55):
    s = (1 - fuerza) + fuerza * 1.25 * sombra[..., None]
    return np.clip(rgb.astype(np.float32) * s, 0, 255).astype(np.uint8)


def hipsometrico(sitio, dtm):
    lo, hi = np.percentile(dtm, [1, 99.5])
    return con_sombra(aplicar(dtm, "hipso", lo, hi), PR.sombreado(dtm, sitio.res, exag=2.0))


def sombreado(sitio, dtm):
    s = PR.sombreado(dtm, sitio.res, exag=2.0)
    g = (40 + 205 * s).astype(np.uint8)
    return np.dstack([g, g, g])


def pendiente(sitio, dtm):
    p = PR.pendiente(dtm, sitio.res, 2.0)
    return con_sombra(aplicar(p, "pendiente", 0, 75), PR.sombreado(dtm, sitio.res), 0.35), p


def diferencia(sitio, dod, dtm, lim=None, lod=0.0):
    lim = lim or max(2.0, float(np.percentile(np.abs(dod), 99.5)))
    v = np.where(np.abs(dod) < lod, 0, dod)
    rgb = aplicar(v, "dod", -lim, lim)
    return con_sombra(rgb, PR.sombreado(dtm, sitio.res), 0.35), lim


def termico(mapa):
    v = mapa[np.isfinite(mapa)]
    lo, hi = (np.percentile(v, 1), max(np.percentile(v, 99.9), 60)) if len(v) else (0, 1)
    return aplicar(mapa, "termica", lo, hi), (lo, hi)


def densidad(dens):
    hi = max(1.0, float(np.percentile(dens[dens > 0], 98))) if (dens > 0).any() else 1
    return aplicar(np.where(dens > 0, dens, np.nan), "densidad", 0, hi), hi


def cobertura(cob):
    rgb = aplicar(np.where(cob > 0, cob, np.nan), "densidad", 0, max(6, float(np.percentile(cob[cob > 0], 98)) if (cob > 0).any() else 6))
    return rgb


def leyenda(nombre, n=160):
    return np.repeat(lut(nombre, n)[None], 10, axis=0)
