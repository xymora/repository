import colorsys
import math
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageOps
from scipy import ndimage
from scipy.spatial import cKDTree

import config as C


def hex_a_rgb(h):
    h = str(h).lstrip("#")
    if len(h) != 6:
        return np.array([1.0, 1.0, 1.0])
    return np.array([int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4)])


def ruta_fuente(nombre):
    archivo = C.FUENTES.get(nombre, nombre)
    for base in (os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts"), C.RAIZ, C.EJEMPLOS):
        r = os.path.join(base, archivo)
        if os.path.exists(r):
            return r
    if os.path.exists(str(nombre)):
        return nombre
    return None


def fuentes_disponibles():
    return [n for n in C.FUENTES if ruta_fuente(n)] or ["Arial Black"]


def _recortar(m, *capas, margen=3):
    vv, uu = np.nonzero(m)
    if len(vv) == 0:
        raise ValueError("La figura quedó vacía")
    v0, v1 = max(vv.min() - margen, 0), min(vv.max() + margen + 1, m.shape[0])
    u0, u1 = max(uu.min() - margen, 0), min(uu.max() + margen + 1, m.shape[1])
    return (m[v0:v1, u0:u1],) + tuple(c[v0:v1, u0:u1] for c in capas)


def _limpiar(m):
    m = ndimage.binary_opening(m, iterations=1)
    lab, k = ndimage.label(m)
    if k > 1:
        tam = ndimage.sum(m, lab, range(1, k + 1))
        quitar = np.nonzero(tam < max(12, 0.002 * m.size))[0] + 1
        m = m & ~np.isin(lab, quitar)
    return m


def mascara_texto(texto, fuente, alto=210):
    lineas = str(texto).replace("\r", "").split("\n")
    while lineas and not lineas[-1].strip():
        lineas.pop()
    while lineas and not lineas[0].strip():
        lineas.pop(0)
    if not lineas:
        raise ValueError("Escribe el texto de la escena")
    ruta = ruta_fuente(fuente)
    f = ImageFont.truetype(ruta, alto) if ruta else ImageFont.load_default()
    asc, desc = f.getmetrics()
    alto_linea = int((asc + desc) * 1.02)
    anchos = [f.getlength(l) for l in lineas]
    W = int(max(anchos)) + 60
    H = alto_linea * len(lineas) + 60
    img = Image.new("L", (W, H), 0)
    d = ImageDraw.Draw(img)
    etiquetas = np.full((H, W), -1, int)
    k = 0
    for i, l in enumerate(lineas):
        x0 = 30 + (W - 60 - anchos[i]) / 2
        y0 = 30 + i * alto_linea
        d.text((x0, y0), l, font=f, fill=255)
        for j, ch in enumerate(l):
            if ch.isspace():
                continue
            a = int(x0 + f.getlength(l[:j]))
            b = int(math.ceil(x0 + f.getlength(l[:j + 1])))
            etiquetas[y0:y0 + alto_linea, a:b] = k
            k += 1
    m = np.asarray(img) > 127
    if not m.any():
        raise ValueError("La fuente no tiene esos caracteres")
    vacio = etiquetas < 0
    if vacio.any() and (~vacio).any():
        _, (iv, iu) = ndimage.distance_transform_edt(vacio, return_indices=True)
        etiquetas = etiquetas[iv, iu]
    return _recortar(m, etiquetas)


def resolver_ruta(ruta):
    if ruta and not os.path.isabs(ruta):
        return os.path.join(C.RAIZ, ruta)
    return ruta


def mascara_imagen(ruta, umbral=60, invertir=False):
    ruta = resolver_ruta(ruta)
    if not ruta or not os.path.exists(ruta):
        raise ValueError("Elige una imagen")
    im = Image.open(ruta)
    im = ImageOps.exif_transpose(im).convert("RGBA")
    im.thumbnail((440, 440), Image.LANCZOS)
    a = np.asarray(im).astype(float)
    rgb, al = a[..., :3] / 255.0, a[..., 3]
    if (al < 250).mean() > 0.02:
        m = al > 127
    else:
        borde = np.concatenate([rgb[0], rgb[-1], rgb[:, 0], rgb[:, -1]])
        fondo = np.median(borde, axis=0)
        dif = np.linalg.norm(rgb - fondo, axis=2) * 255
        m = dif > float(umbral)
    if invertir:
        m = ~m
    rgb = np.stack([ndimage.median_filter(rgb[..., k], size=5) for k in range(3)], axis=2)
    m = np.pad(m, 4)
    rgb = np.pad(rgb, ((4, 4), (4, 4), (0, 0)), mode="edge")
    m = _limpiar(m)
    if m.sum() < 60:
        raise ValueError("No se distingue la figura de la imagen: ajusta el umbral o usa Invertir")
    return _recortar(m, rgb)


def contorno(m, grosor=None):
    g = grosor or max(2, int(round(max(m.shape) / 95)))
    mp = np.pad(m, 2)
    borde = mp & ~ndimage.binary_erosion(mp, iterations=g)
    return borde[2:-2, 2:-2]


def _fps(cand, n, rng):
    sub = cand if len(cand) <= 24000 else cand[rng.choice(len(cand), 24000, replace=False)]
    idx = np.empty(n, int)
    idx[0] = rng.integers(len(sub))
    d = np.sum((sub - sub[idx[0]]) ** 2, axis=1)
    for i in range(1, n):
        idx[i] = int(np.argmax(d))
        d = np.minimum(d, np.sum((sub - sub[idx[i]]) ** 2, axis=1))
    return sub[idx].copy()


def uniformizar(cand, n, iters=14, semilla=7):
    rng = np.random.default_rng(semilla)
    cand = np.asarray(cand, float)
    m, dim = cand.shape
    if m == 0:
        raise ValueError("La figura quedó vacía")
    if m <= n:
        extra = cand[rng.integers(0, m, n - m)] + rng.normal(0, 0.3, (n - m, dim))
        return np.vstack([cand, extra])
    p = _fps(cand, n, rng)
    for _ in range(iters):
        _, asig = cKDTree(p).query(cand)
        cnt = np.bincount(asig, minlength=n).astype(float)
        suma = np.stack([np.bincount(asig, weights=cand[:, k], minlength=n) for k in range(dim)], 1)
        ok = cnt > 0
        p[ok] = suma[ok] / cnt[ok, None]
        if (~ok).any():
            p[~ok] = cand[rng.integers(0, m, int((~ok).sum()))]
    arbol = cKDTree(cand)
    muestra = cand[rng.choice(m, min(m, 3000), replace=False)]
    paso = np.median(arbol.query(muestra, k=2)[0][:, 1])
    d, j = arbol.query(p)
    lejos = d > 1.5 * paso
    p[lejos] = cand[j[lejos]]
    return p


def espaciar(p, sep, iters=80):
    p = np.asarray(p, float).copy()
    if len(p) < 2:
        return p
    nn = cKDTree(p).query(p, k=2)[0][:, 1]
    ref = np.percentile(nn, 4)
    if ref <= 1e-9:
        ref = max(np.median(nn), 1e-6)
    p *= sep * 1.03 / ref
    rng = np.random.default_rng(3)
    for _ in range(iters):
        pares = cKDTree(p).query_pairs(sep, output_type="ndarray")
        if len(pares) == 0:
            break
        a, b = pares[:, 0], pares[:, 1]
        dv = p[b] - p[a]
        L = np.linalg.norm(dv, axis=1)
        cero = L < 1e-6
        if cero.any():
            dv[cero] = rng.normal(size=(int(cero.sum()), p.shape[1]))
            L[cero] = np.linalg.norm(dv[cero], axis=1)
        u = dv / L[:, None]
        e = ((sep * 1.02 - L) * 0.5)[:, None] * u
        acc = np.zeros_like(p)
        np.add.at(acc, a, -e)
        np.add.at(acc, b, e)
        p += acc * 0.9
    return p


def _rot(eje, ang):
    c, s = math.cos(ang), math.sin(ang)
    if eje == "x":
        return np.array([[1, 0, 0], [0, c, -s], [0, s, c]])
    if eje == "y":
        return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])


def _unitario(M, rng):
    v = rng.normal(size=(M, 3))
    return v / np.linalg.norm(v, axis=1, keepdims=True)


def _poligono_relleno(poly, M, rng):
    from matplotlib.path import Path
    poly = np.asarray(poly)
    lo, hi = poly.min(0), poly.max(0)
    pts = rng.uniform(lo, hi, (M * 3, 2))
    dentro = Path(poly).contains_points(pts)
    return pts[dentro][:M]


def _estrella_poly(puntas=5, r1=1.0, r2=0.42):
    a = np.arange(puntas * 2) * math.pi / puntas + math.pi / 2
    r = np.where(np.arange(puntas * 2) % 2 == 0, r1, r2)
    return np.column_stack([r * np.cos(a), r * np.sin(a)])


def _paleta_mezcla(t, colores):
    colores = [hex_a_rgb(c) if isinstance(c, str) else np.asarray(c, float) for c in colores]
    t = np.clip(t, 0, 1) * (len(colores) - 1)
    i = np.minimum(t.astype(int), len(colores) - 2)
    f = (t - i)[:, None]
    A = np.array([colores[k] for k in i])
    B = np.array([colores[k + 1] for k in i])
    return A * (1 - f) + B * f


def _ruido(p, s=3.0):
    return (np.sin(p[:, 0] * s + 1.3) * np.cos(p[:, 1] * s * 1.7 + 0.4) + np.sin(p[:, 2] * s * 1.3 + 2.1)
            + 0.5 * np.sin((p[:, 0] + p[:, 2]) * s * 2.3))


def fig_esfera(M, rng):
    c = _unitario(M, rng)
    return c, lambda p: _paleta_mezcla((p[:, 2] - p[:, 2].min()) / np.ptp(p[:, 2]), ["#2a6bff", "#38e0ff", "#e8fbff"])


def fig_toro(M, rng):
    R, r = 1.0, 0.42
    th = rng.uniform(0, 2 * math.pi, M * 3)
    ph = rng.uniform(0, 2 * math.pi, M * 3)
    w = (R + r * np.cos(ph)) / (R + r)
    k = rng.uniform(0, 1, M * 3) < w
    th, ph = th[k][:M], ph[k][:M]
    p = np.column_stack([(R + r * np.cos(ph)) * np.cos(th), r * np.sin(ph), (R + r * np.cos(ph)) * np.sin(th)])
    rot = _rot("x", -0.55)
    pr = p @ rot.T

    def paleta(q):
        loc = q @ rot
        ang = np.arctan2(loc[:, 1], np.hypot(loc[:, 0], loc[:, 2]) - R)
        glaseado = ang < 0.35
        col = np.where(glaseado[:, None], hex_a_rgb("#ff4fa3"), hex_a_rgb("#d9913f"))
        chispas = glaseado & (np.random.default_rng(5).uniform(0, 1, len(q)) < 0.16)
        tonos = np.array([hex_a_rgb(c) for c in ("#fff36b", "#5ef0ff", "#9dff6b", "#ffffff", "#b07bff")])
        col[chispas] = tonos[np.random.default_rng(9).integers(0, 5, int(chispas.sum()))]
        return col
    return pr, paleta


def fig_cubo(M, rng):
    cara = rng.integers(0, 6, M)
    uv = rng.uniform(-1, 1, (M, 2))
    p = np.zeros((M, 3))
    eje = cara // 2
    signo = np.where(cara % 2 == 0, 1.0, -1.0)
    for e in range(3):
        k = eje == e
        otros = [i for i in range(3) if i != e]
        p[k, e] = signo[k]
        p[k, otros[0]] = uv[k, 0]
        p[k, otros[1]] = uv[k, 1]
    rot = _rot("z", 0.62) @ _rot("x", 0.5)
    pr = p @ rot.T
    tonos = ["#ff4d6d", "#ffd166", "#06d6a0", "#118ab2", "#b48cff", "#ff9f1c"]

    def paleta(q):
        loc = q @ rot
        e = np.argmax(np.abs(loc), axis=1)
        s = (np.take_along_axis(loc, e[:, None], 1)[:, 0] > 0).astype(int)
        return np.array([hex_a_rgb(tonos[i]) for i in e * 2 + s])
    return pr, paleta


def _f_corazon(p):
    x, y, z = p[:, 0], p[:, 1], p[:, 2]
    return (x * x + 2.25 * y * y + z * z - 1) ** 3 - x * x * z ** 3 - 0.1125 * y * y * z ** 3


def fig_corazon(M, rng):
    pts = rng.uniform([-1.4, -0.9, -1.3], [1.4, 0.9, 1.5], (M * 40, 3))
    dentro = _f_corazon(pts) < 0
    afuera = _f_corazon(pts * 1.045) >= 0
    c = pts[dentro & afuera][:M]
    return c, lambda p: _paleta_mezcla(np.clip(0.5 + 0.35 * (p[:, 2] - p[:, 0] * 0.5), 0, 1), ["#a8001c", "#ff1f4b", "#ff9cb3"])


def fig_adn(M, rng):
    vueltas, alto, r = 1.6, 3.2, 0.85
    m1 = int(M * 0.62)
    t = rng.uniform(0, 1, m1)
    hebra = rng.integers(0, 2, m1)
    a = 2 * math.pi * vueltas * t + hebra * math.pi
    tubo = _unitario(m1, rng) * 0.16
    p1 = np.column_stack([r * np.cos(a), r * np.sin(a), alto * (t - 0.5)]) + tubo
    n_esc = 12
    m2 = M - m1
    k = rng.integers(0, n_esc, m2)
    tt = (k + 0.5) / n_esc
    s = rng.uniform(-1, 1, m2)
    a2 = 2 * math.pi * vueltas * tt
    p2 = np.column_stack([r * s * np.cos(a2), r * s * np.sin(a2), alto * (tt - 0.5)])
    c = np.vstack([p1, p2]) * 0.55

    def paleta(q):
        rr = np.hypot(q[:, 0], q[:, 1]) / (r * 0.55)
        z = q[:, 2] / 0.55 / alto + 0.5
        ang = np.arctan2(q[:, 1], q[:, 0]) - 2 * math.pi * vueltas * z
        lado = (np.cos(ang) > 0)
        col = np.where(lado[:, None], hex_a_rgb("#3d8bff"), hex_a_rgb("#ff3df0"))
        esc = rr < 0.86
        kk = np.round(z * n_esc - 0.5).astype(int)
        pares = np.array([hex_a_rgb(c) for c in ("#3dff8a", "#ffe23d", "#ff8a3d", "#3dfff0")])
        mitad = (np.cos(ang) > 0).astype(int)
        col[esc] = pares[(kk[esc] % 2) * 2 + mitad[esc]]
        return col
    return c, paleta


def fig_estrella(M, rng):
    poly = _estrella_poly()
    prof = 0.22
    mc = int(M * 0.36)
    fr = _poligono_relleno(poly, mc, rng)
    at = _poligono_relleno(poly, mc, rng)
    lados = M - 2 * mc
    seg = rng.integers(0, len(poly), lados)
    f = rng.uniform(0, 1, lados)
    a, b = poly[seg], poly[(seg + 1) % len(poly)]
    borde = a + (b - a) * f[:, None]
    yy = rng.uniform(-prof, prof, lados)
    c = np.vstack([
        np.column_stack([fr[:, 0], np.full(len(fr), -prof), fr[:, 1]]),
        np.column_stack([at[:, 0], np.full(len(at), prof), at[:, 1]]),
        np.column_stack([borde[:, 0], yy, borde[:, 1]]),
    ])
    rot = _rot("z", 0.35)
    return c @ rot.T, lambda p: _paleta_mezcla(np.clip(np.linalg.norm(p[:, [0, 2]], axis=1), 0, 1), ["#fff6c9", "#ffd23b", "#ff9a1f"])


def fig_piramide(M, rng):
    base = np.array([[-1, -1], [1, -1], [1, 1], [-1, 1]], float)
    cima = np.array([0, 0, 1.45])
    tri = []
    for i in range(4):
        a = np.array([*base[i], -0.6])
        b = np.array([*base[(i + 1) % 4], -0.6])
        tri.append((a, b, cima + [0, 0, -0.6]))
    k = rng.integers(0, 4, M)
    r1, r2 = rng.uniform(0, 1, M), rng.uniform(0, 1, M)
    voltear = r1 + r2 > 1
    r1[voltear], r2[voltear] = 1 - r1[voltear], 1 - r2[voltear]
    A = np.array([tri[i][0] for i in k])
    B = np.array([tri[i][1] for i in k])
    Cc = np.array([tri[i][2] for i in k])
    p = A + (B - A) * r1[:, None] + (Cc - A) * r2[:, None]
    rot = _rot("z", 0.45)
    pr = p @ rot.T
    return pr, lambda q: _paleta_mezcla((q[:, 2] - q[:, 2].min()) / np.ptp(q[:, 2]), ["#b5651d", "#ffb347", "#fff2b3"])


def fig_planeta(M, rng):
    ms = int(M * 0.66)
    esf = _unitario(ms, rng) * 0.8
    mr = M - ms
    rr = np.sqrt(rng.uniform(1.15 ** 2, 1.62 ** 2, mr))
    a = rng.uniform(0, 2 * math.pi, mr)
    anillo = np.column_stack([rr * np.cos(a), rr * np.sin(a), np.zeros(mr)])
    rot = _rot("x", 1.18) @ _rot("y", 0.32)
    anillo = anillo @ rot.T
    c = np.vstack([esf, anillo])

    def paleta(q):
        r = np.linalg.norm(q, axis=1)
        planeta = r < 0.98
        tierra = _ruido(q * 1.3, 2.6) > 0.45
        col = np.where(tierra[:, None], hex_a_rgb("#3ddc6a"), hex_a_rgb("#1f6bff"))
        polo = np.abs(q[:, 2]) > 0.68
        col[polo] = hex_a_rgb("#e9f6ff")
        bandas = _paleta_mezcla(((r - 1.15) / 0.47) % 1.0, ["#ffe2a8", "#c99a4b", "#fff3d6", "#d8a95b"])
        col[~planeta] = bandas[~planeta]
        return col
    return c, paleta


def fig_galaxia(M, rng):
    mn = int(M * 0.18)
    nucleo = rng.normal(0, [0.18, 0.18, 0.08], (mn, 3))
    mb = M - mn
    brazo = rng.integers(0, 2, mb)
    th = rng.uniform(0.3, 3.4 * math.pi / 2 + 1.2, mb)
    r = 0.12 * np.exp(0.36 * th)
    ang = th + brazo * math.pi
    dis = rng.normal(0, 1, (mb, 2)) * (0.06 + 0.03 * r)[:, None]
    p = np.column_stack([r * np.cos(ang) + dis[:, 0], r * np.sin(ang) + dis[:, 1], rng.normal(0, 0.03, mb)])
    c = np.vstack([nucleo, p])
    c /= np.abs(c).max()
    rot = _rot("x", -1.05)
    c = c @ rot.T

    def paleta(q):
        loc = q @ rot
        rr = np.clip(np.hypot(loc[:, 0], loc[:, 1]) / 0.9, 0, 1)
        col = _paleta_mezcla(rr, ["#fff4d6", "#ffd27a", "#9b7bff", "#3d7bff", "#3dd6f5"])
        rosa = (np.random.default_rng(4).uniform(0, 1, len(q)) < 0.07) & (rr > 0.3)
        col[rosa] = hex_a_rgb("#ff5fb8")
        return col
    return c, paleta


def fig_arbol(M, rng):
    mc = int(M * 0.84)
    h = np.sqrt(rng.uniform(0, 1, mc))
    a = rng.uniform(0, 2 * math.pi, mc)
    radio = 0.95 * h
    z = 1.25 - 2.2 * h
    cono = np.column_stack([radio * np.cos(a), radio * np.sin(a), z])
    me = int(M * 0.09)
    est = _poligono_relleno(_estrella_poly(5, 0.26, 0.11), me, rng)
    estrella = np.column_stack([est[:, 0], np.zeros(len(est)), est[:, 1] + 1.48])
    mt = M - mc - len(estrella)
    at = rng.uniform(0, 2 * math.pi, mt)
    tronco = np.column_stack([0.16 * np.cos(at), 0.16 * np.sin(at), rng.uniform(-1.3, -0.95, mt)])
    c = np.vstack([cono, estrella, tronco])

    def paleta(q):
        col = _paleta_mezcla(np.clip((q[:, 2] + 1) / 2.3, 0, 1), ["#0b8a3a", "#1fd16b"])
        g = np.random.default_rng(11)
        adorno = g.uniform(0, 1, len(q)) < 0.18
        tonos = np.array([hex_a_rgb(c) for c in ("#ff2b2b", "#ffd23b", "#3d8bff", "#ffffff", "#ff3df0")])
        col[adorno] = tonos[g.integers(0, 5, int(adorno.sum()))]
        col[q[:, 2] > 1.24] = hex_a_rgb("#ffd700")
        col[q[:, 2] < -0.97] = hex_a_rgb("#a0522d")
        return col
    return c, paleta


def fig_atomo(M, rng):
    mn = int(M * 0.2)
    nuc = _unitario(mn, rng) * 0.28
    mo = M - mn
    k = rng.integers(0, 3, mo)
    t = rng.uniform(0, 2 * math.pi, mo)
    e = np.column_stack([1.25 * np.cos(t), 0.42 * np.sin(t), np.zeros(mo)])
    out = np.zeros_like(e)
    for i in range(3):
        R = _rot("x", 1.2) @ _rot("z", i * math.pi / 3)
        s = k == i
        out[s] = e[s] @ R.T + _unitario(int(s.sum()), rng) * 0.07
    c = np.vstack([nuc, out])

    def paleta(q):
        r = np.linalg.norm(q, axis=1)
        col = np.tile(hex_a_rgb("#3dd6f5"), (len(q), 1))
        nucleo = r < 0.4
        g = np.random.default_rng(2)
        col[nucleo] = np.where(g.uniform(0, 1, int(nucleo.sum()))[:, None] < 0.5, hex_a_rgb("#ff3d3d"), hex_a_rgb("#f2f2ff"))
        return col
    return c, paleta


def fig_onda(M, rng):
    xy = rng.uniform(-1.4, 1.4, (M, 2))
    z = 0.32 * np.sin(2.2 * xy[:, 0]) * np.cos(2.2 * xy[:, 1])
    p = np.column_stack([xy[:, 0], xy[:, 1], z])
    rot = _rot("x", -0.62)
    pr = p @ rot.T

    def paleta(q):
        loc = q @ rot
        return _paleta_mezcla(np.clip(loc[:, 2] / 0.64 + 0.5, 0, 1), ["#1430ff", "#2ab7ff", "#bff6ff"])
    return pr, paleta


def fig_mariposa(M, rng):
    pts = rng.uniform([-1.6, -1.2], [1.6, 1.2], (M * 4, 2))
    x, z = np.abs(pts[:, 0]), pts[:, 1]
    sup = ((x - 0.78) / 0.75) ** 2 + ((z - 0.42) / 0.62) ** 2 < 1
    inf = ((x - 0.55) / 0.5) ** 2 + ((z + 0.5) / 0.55) ** 2 < 1
    cuerpo = (x < 0.07) & (np.abs(z) < 0.85)
    ok = (sup | inf | cuerpo) & ((x > 0.12) | cuerpo)
    q = pts[ok][:M]
    y = 0.45 * np.abs(q[:, 0])
    c = np.column_stack([q[:, 0], y, q[:, 1]])

    def paleta(p):
        x, z = np.abs(p[:, 0]), p[:, 2]
        e1 = ((x - 0.78) / 0.75) ** 2 + ((z - 0.42) / 0.62) ** 2
        e2 = ((x - 0.55) / 0.5) ** 2 + ((z + 0.5) / 0.55) ** 2
        e = np.minimum(e1, e2)
        col = _paleta_mezcla(np.clip(e, 0, 1), ["#ffcf3d", "#ff7a1f", "#c2185b"])
        manchas = (e > 0.78) & (np.random.default_rng(6).uniform(0, 1, len(p)) < 0.25)
        col[manchas] = hex_a_rgb("#ffffff")
        col[x < 0.1] = hex_a_rgb("#6b4cff")
        return col
    return c, paleta


def fig_cohete(M, rng):
    mc = int(M * 0.5)
    a = rng.uniform(0, 2 * math.pi, mc)
    zc = rng.uniform(-0.6, 0.85, mc)
    cuerpo = np.column_stack([0.3 * np.cos(a), 0.3 * np.sin(a), zc])
    mn = int(M * 0.14)
    h = np.sqrt(rng.uniform(0, 1, mn))
    an = rng.uniform(0, 2 * math.pi, mn)
    nariz = np.column_stack([0.3 * h * np.cos(an), 0.3 * h * np.sin(an), 1.4 - 0.55 * h])
    mf = int(M * 0.18)
    k = rng.integers(0, 3, mf)
    r1, r2 = rng.uniform(0, 1, mf), rng.uniform(0, 1, mf)
    v = r1 + r2 > 1
    r1[v], r2[v] = 1 - r1[v], 1 - r2[v]
    rr = 0.3 + 0.38 * r1
    zz = -0.62 + 0.5 * r2 * (1 - r1 * 0.5)
    af = k * 2 * math.pi / 3 + 0.4
    aletas = np.column_stack([rr * np.cos(af), rr * np.sin(af), zz])
    ml = M - mc - mn - mf
    hl = rng.uniform(0, 1, ml)
    al = rng.uniform(0, 2 * math.pi, ml)
    rl = 0.24 * (1 - hl) * np.sqrt(rng.uniform(0, 1, ml))
    llama = np.column_stack([rl * np.cos(al), rl * np.sin(al), -0.65 - 0.75 * hl])
    c = np.vstack([cuerpo, nariz, aletas, llama])
    rot = _rot("y", 0.5)
    c = c @ rot.T

    def paleta(q):
        loc = q @ rot
        r = np.hypot(loc[:, 0], loc[:, 1])
        z = loc[:, 2]
        col = np.tile(hex_a_rgb("#eef3ff"), (len(q), 1))
        col[z > 0.84] = hex_a_rgb("#ff2b3d")
        col[(r > 0.33) & (z < -0.1)] = hex_a_rgb("#ff2b3d")
        ventana = (np.abs(z - 0.45) < 0.12) & (np.arctan2(loc[:, 1], loc[:, 0]) < -0.6) & (np.arctan2(loc[:, 1], loc[:, 0]) > -2.4)
        col[ventana] = hex_a_rgb("#3dd6f5")
        fuego = z < -0.64
        col[fuego] = _paleta_mezcla(np.clip((-0.64 - z[fuego]) / 0.75, 0, 1), ["#fff6b0", "#ffb31f", "#ff3d00"])
        return col
    return c, paleta


GENERADORES = {
    "esfera": fig_esfera, "toro": fig_toro, "cubo": fig_cubo, "corazon": fig_corazon,
    "adn": fig_adn, "estrella": fig_estrella, "piramide": fig_piramide, "planeta": fig_planeta,
    "galaxia": fig_galaxia, "arbol": fig_arbol, "atomo": fig_atomo, "onda": fig_onda,
    "mariposa": fig_mariposa, "cohete": fig_cohete,
}


def arcoiris(t):
    t = np.asarray(t) % 1.0
    return np.array([colorsys.hsv_to_rgb(h, 0.9, 1.0) for h in t])


def colorear(modo, colores, unit, etiquetas=None, col_img=None, col_fig=None, plano=True):
    n = len(unit)
    cs = [hex_a_rgb(c) for c in (list(colores) + ["#ffffff"] * 3)[:3]]
    lo, hi = unit.min(0), unit.max(0)
    rango = np.where(hi - lo > 1e-9, hi - lo, 1.0)
    u = (unit[:, 0] - lo[0]) / rango[0]
    w = (unit[:, 2] - lo[2]) / rango[2]
    if modo == "degradado":
        col = _paleta_mezcla(u, cs[:2])
    elif modo == "tres":
        col = np.array([cs[min(int(x * 3), 2)] for x in u])
    elif modo == "vertical":
        col = _paleta_mezcla(w, cs[:2])
    elif modo == "arcoiris":
        if plano:
            col = arcoiris(u * 0.85)
        else:
            centro = (lo + hi) / 2
            ang = np.arctan2(unit[:, 1] - centro[1], unit[:, 0] - centro[0])
            col = arcoiris((ang + math.pi) / (2 * math.pi))
    elif modo == "por_letra" and etiquetas is not None:
        col = np.array([cs[int(e) % 3] for e in etiquetas])
    elif modo == "imagen" and col_img is not None:
        col = col_img.copy()
    elif modo == "figura" and col_fig is not None:
        col = col_fig.copy()
    else:
        col = np.tile(cs[0], (n, 1))
    v = col.max(1, keepdims=True)
    piso = 0.28
    col = np.where(v < piso, col + (piso - v), col)
    return np.clip(col, 0, 1)


def _capas(p2, capas, paso):
    if capas <= 1:
        return np.column_stack([p2[:, 0], np.zeros(len(p2)), p2[:, 1]])
    out = []
    for k in range(capas):
        y = (k - (capas - 1) / 2) * paso
        out.append(np.column_stack([p2[:, 0], np.full(len(p2), y), p2[:, 1]]))
    return np.vstack(out)


def generar(esc, n, sep=C.SEPARACION, semilla=7):
    n = int(n)
    tipo = esc.get("tipo", "texto")
    rng = np.random.default_rng(semilla)
    etiquetas = col_img = col_fig = None
    plano = True
    if tipo in ("texto", "imagen"):
        if tipo == "texto":
            m, lab = mascara_texto(esc.get("texto", ""), esc.get("fuente", "Arial Black"))
            img = None
        else:
            m, img = mascara_imagen(esc.get("ruta", ""), esc.get("umbral", 60), esc.get("invertir", False))
            lab = None
        if esc.get("trazo", "relleno") == "contorno":
            m = contorno(m)
        capas = int(np.clip(esc.get("capas", 1), 1, 3))
        por_capa = max(4, n // capas)
        vv, uu = np.nonzero(m)
        cand = np.column_stack([uu, -vv]).astype(float)
        if len(cand) > 80000:
            cand = cand[rng.choice(len(cand), 80000, replace=False)]
        p2 = uniformizar(cand, por_capa, semilla=semilla)
        iu = np.clip(np.round(p2[:, 0]).astype(int), 0, m.shape[1] - 1)
        iv = np.clip(np.round(-p2[:, 1]).astype(int), 0, m.shape[0] - 1)
        nn = np.median(cKDTree(p2).query(p2, k=2)[0][:, 1]) if len(p2) > 1 else 1.0
        unit = _capas(p2, capas, nn * 1.5)
        reps = len(unit) // len(p2)
        if lab is not None:
            etiquetas = np.tile(lab[iv, iu], reps)
        if img is not None:
            col_img = np.tile(img[iv, iu], (reps, 1))
        resto = n - len(unit)
        if resto > 0:
            j = rng.integers(0, len(unit), resto)
            unit = np.vstack([unit, unit[j] + rng.normal(0, nn * 0.3, (resto, 3)) * [1, 0, 1]])
            if etiquetas is not None:
                etiquetas = np.concatenate([etiquetas, etiquetas[j]])
            if col_img is not None:
                col_img = np.vstack([col_img, col_img[j]])
        plano = capas == 1
    else:
        nombre = esc.get("figura", "esfera")
        gen = GENERADORES.get(nombre, fig_esfera)
        M = int(np.clip(n * 28, 16000, 60000))
        cand, paleta = gen(M, rng)
        unit = uniformizar(cand, n, semilla=semilla)
        col_fig = paleta(unit)
        plano = False
    unit = unit[:n]
    pos = espaciar(unit, sep)
    ancho_min = float(esc.get("ancho", 0) or 0)
    ancho = np.ptp(pos[:, 0])
    if ancho_min > 0 and ancho < ancho_min:
        pos *= ancho_min / max(ancho, 1e-6)
    pos -= (pos.min(0) + pos.max(0)) / 2
    modo = esc.get("color", "unico")
    col = colorear(modo, esc.get("colores", ["#ffffff"]), unit, etiquetas, col_img, col_fig, plano)
    nn = cKDTree(pos).query(pos, k=2)[0][:, 1]
    return {"pos": pos, "col": col, "plano": plano, "min_sep": float(nn.min()),
            "tam": tuple(float(v) for v in np.ptp(pos, axis=0))}
