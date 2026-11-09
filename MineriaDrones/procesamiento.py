import math

import numpy as np
from scipy.ndimage import (binary_dilation, gaussian_filter, grey_opening, label, maximum_filter, median_filter,
                           uniform_filter, zoom)

import config as C
import terreno as T


def rellenar(valores, valido):
    v = np.where(valido, valores, 0).astype(np.float64)
    m = valido.astype(np.float64)
    res = np.where(valido, valores, np.nan).astype(np.float64)
    falta = ~valido
    for sigma in (1, 2, 4, 8, 16, 32, 64, 128):
        if not falta.any():
            break
        num = gaussian_filter(v, sigma)
        den = gaussian_filter(m, sigma)
        ok = falta & (den > 1e-3)
        res[ok] = num[ok] / den[ok]
        falta &= ~ok
    if falta.any():
        res[falta] = np.nanmean(res)
    return res.astype(np.float32)


def sombreado(dtm, res, az=315.0, alt=45.0, exag=1.0):
    return T._sombreado(dtm * exag, res, az, alt)


def pendiente(dtm, res, base=1.0):
    d = gaussian_filter(dtm, base / res) if base > res else dtm
    gy, gx = np.gradient(d, res)
    return np.degrees(np.arctan(np.hypot(gx, gy))).astype(np.float32)


def puntos_control(sitio, n, semilla=5, excluir_cambios=True):
    rng = np.random.default_rng(semilla)
    A, B = sitio.epocas["A"], sitio.epocas["B"]
    estable = (np.abs(A["dtm"] - B["dtm"]) < 0.05) & (A["veg"] < 0.2) & (B["veg"] < 0.2) & (A["objetos_h"] < 0.1) & ~A["agua"] & ~B["agua"]
    estable &= maximum_filter(pendiente(A["dtm"], sitio.res, 2.0), size=max(3, int(10 / sitio.res))) < 8
    estable &= maximum_filter(np.maximum(A["veg"], B["veg"]) + A["objetos_h"], size=max(3, int(10 / sitio.res))) < 0.2
    margen = int(0.06 * sitio.nx)
    estable[:margen], estable[-margen:], estable[:, :margen], estable[:, -margen:] = False, False, False, False
    ii, jj = np.nonzero(estable)
    if not len(ii):
        return []
    elegidos = []
    k = rng.integers(len(ii))
    elegidos.append(k)
    xs, ys = sitio.a_xy(ii, jj)
    dmin = np.full(len(ii), np.inf)
    for _ in range(n - 1):
        dmin = np.minimum(dmin, np.hypot(xs - xs[elegidos[-1]], ys - ys[elegidos[-1]]))
        elegidos.append(int(np.argmax(dmin * rng.uniform(0.85, 1.0, len(dmin)))))
    return [{"x": float(xs[k]), "y": float(ys[k]), "z": float(A["dtm"][ii[k], jj[k]]), "id": f"P{n_ + 1}"}
            for n_, k in enumerate(elegidos)]


def _corregir_sesgos(resultado, n_gcp, rng):
    sesgos = np.array(resultado["sesgos"]) if resultado["sesgos"] else np.zeros((1, 3))
    if n_gcp >= 3:
        est = sesgos + rng.normal(0, 0.025 / math.sqrt(n_gcp / 3), sesgos.shape)
    else:
        est = np.zeros_like(sesgos)
    return sesgos, est


def _pmf(superficie, res, ventanas=(3, 5, 9, 17, 33)):
    gy, gx = np.gradient(gaussian_filter(superficie, 5.0 / res), res)
    t = np.clip(np.hypot(gx, gy), 0, 4)
    suelo = np.ones(superficie.shape, bool)
    actual = superficie.copy()
    for w_m in ventanas:
        w = max(3, int(round(w_m / res)) | 1)
        abierto = grey_opening(actual, size=(w, w))
        dh = np.minimum(2.6 + 25 * t, 0.3 + (0.08 + 0.9 * t) * (w * res - 1) * 0.5)
        suelo &= (actual - abierto) <= dh
        actual = abierto
    return suelo


def procesar_lidar(sitio, resultado, n_gcp=6, semilla=3, avisar=print):
    rng = np.random.default_rng(semilla)
    nube = resultado["nube"]
    if nube is None or not len(nube["x"]):
        raise ValueError("Ese vuelo no tiene nube de puntos LiDAR")
    avisar(f"Procesando nube LiDAR: {len(nube['x']):,} puntos…".replace(",", " "))
    sesgos, est = _corregir_sesgos(resultado, n_gcp, rng)
    d = nube["d"].astype(int)
    x = nube["x"] - est[d, 0]
    y = nube["y"] - est[d, 1]
    z = nube["z"] - est[d, 2]
    res = sitio.res
    nx = ny = sitio.nx
    j = np.clip((x / res).astype(np.int64), 0, nx - 1)
    i = np.clip(((sitio.ancho - y) / res).astype(np.int64), 0, ny - 1)
    idx = i * nx + j
    cuenta = np.bincount(idx, minlength=nx * ny).reshape(ny, nx)
    zmin = np.full(nx * ny, np.inf, np.float32)
    zmax = np.full(nx * ny, -np.inf, np.float32)
    np.minimum.at(zmin, idx, z)
    np.maximum.at(zmax, idx, z)
    zmin, zmax = zmin.reshape(ny, nx), zmax.reshape(ny, nx)
    multi = np.bincount(idx, weights=(nube["n"] > 1).astype(float), minlength=nx * ny).reshape(ny, nx)
    hay = cuenta > 0
    avisar("Clasificando suelo (filtro morfológico progresivo)…")
    base = rellenar(np.where(hay, zmin, 0), hay)
    suelo = _pmf(base, res) & hay
    grueso = rellenar(np.where(suelo, zmin, 0), suelo)
    grueso = gaussian_filter(grueso, 1.0)
    gy, gx = np.gradient(grueso, res)
    xc = (j + 0.5) * res
    yc = sitio.ancho - (i + 0.5) * res
    zc = z - (gx[i, j] * (x - xc) - gy[i, j] * (y - yc))
    bajo = zc <= grueso[i, j] + 0.6
    for _ in range(2):
        suma = np.bincount(idx[bajo], weights=zc[bajo], minlength=nx * ny).reshape(ny, nx)
        nbajo = np.bincount(idx[bajo], minlength=nx * ny).reshape(ny, nx)
        media = np.where(nbajo > 0, suma / np.maximum(nbajo, 1), grueso)
        bajo = np.abs(zc - media.ravel()[idx]) <= 0.2
    zsuelo = media
    dtm = rellenar(np.where(suelo & (nbajo > 0), zsuelo, 0), suelo & (nbajo > 0))
    dtm = (0.7 * dtm + 0.3 * gaussian_filter(dtm, 0.7)).astype(np.float32)
    dsm = rellenar(np.where(hay, zmax, 0), hay)
    avisar("Clasificando puntos (suelo, vegetación, estructuras)…")
    hz = z - dtm[i, j]
    clase = np.ones(len(z), np.uint8)
    clase[hz <= 0.3] = 2
    alto = hz > 0.3
    es_veg = multi.ravel()[idx] > 0
    clase[alto & es_veg & (hz <= 2)] = 3
    clase[alto & es_veg & (hz > 2) & (hz <= 5)] = 4
    clase[alto & es_veg & (hz > 5)] = 5
    clase[alto & ~es_veg & (hz > 1.5)] = 6
    clase[hz < -1.2] = 7
    densidad = uniform_filter(cuenta.astype(np.float32), size=max(3, int(3 / res) | 1)) / (res * res)
    k = max(3, int(4 / res) | 1)
    vacio = uniform_filter(hay.astype(np.float32), size=k) < 0.02
    return {"metodo": "LiDAR", "dtm": dtm, "dsm": dsm.astype(np.float32), "densidad": densidad.astype(np.float32),
            "sin_retorno": vacio, "clase": clase, "x": x.astype(np.float32), "y": y.astype(np.float32),
            "z": z.astype(np.float32), "i": nube["i"], "r": nube["r"], "n": nube["n"],
            "sesgos": sesgos, "sesgos_est": est, "n_gcp": n_gcp,
            "sigma_pos_h": C.POSICIONAMIENTO[resultado["posicionamiento"]]["h"]}


def _cobertura_1m(sitio, cob):
    f = sitio.nx / cob.shape[0]
    return zoom(cob, f, order=0)[:sitio.ny, :sitio.nx]


def procesar_fotos(sitio, resultado, n_gcp=6, semilla=4, avisar=print):
    rng = np.random.default_rng(semilla)
    caps = [c for c in resultado["capturas"] if c["tipo"] == "linea"] or resultado["capturas"]
    if not caps:
        raise ValueError("Ese vuelo no tomó fotos")
    avisar(f"Alineando {len(caps)} fotos y generando nube densa…")
    e = sitio.epocas[resultado["epoca"]]
    cob = _cobertura_1m(sitio, resultado["cobertura"]).astype(np.float32)
    gmin = _cobertura_1m(sitio, resultado["gsd_min"])
    sesgos, est = _corregir_sesgos(resultado, n_gcp, rng)
    usados = np.array([c["salida"] for c in caps])
    residuo = (sesgos - est)[usados].mean(axis=0) if len(usados) else np.zeros(3)
    verdad = e["dtm"] + e["veg"] + e["objetos_h"]
    pend = pendiente(verdad, sitio.res, 2.0)
    g = np.where(np.isfinite(gmin), gmin, 0.05)
    sigma = 1.6 * g * (1 + 2.5 * np.clip(pend / 70, 0, 1)) * np.where(cob >= 4, 1.0, 1.8)
    ruido = gaussian_filter(rng.standard_normal(verdad.shape).astype(np.float32), 1.2) * 2.2
    dz = sitio.res
    sx, sy = residuo[0] / dz, -residuo[1] / dz
    desplazado = np.roll(np.roll(verdad, int(round(sy)), axis=0), int(round(sx)), axis=1)
    dsm = desplazado + residuo[2] + ruido * sigma
    valido = (cob >= 2) & ~e["agua"]
    dsm = rellenar(np.where(valido, dsm, 0), valido)
    avisar("Generando ortomosaico y modelo de terreno fotogramétrico…")
    suelo = valido & _pmf(dsm, sitio.res, (5, 9, 17, 33))
    dtm = rellenar(np.where(suelo, dsm, 0), suelo)
    color = e["color"].astype(np.float32)
    color = np.roll(np.roll(color, int(round(sy)), axis=0), int(round(sx)), axis=1)
    orto = np.where((cob >= 1)[..., None], color, color * 0.18 + 10)
    return {"metodo": "Fotogrametría", "dtm": dtm, "dsm": dsm.astype(np.float32), "orto": np.clip(orto, 0, 255).astype(np.uint8),
            "cobertura": cob, "gsd": gmin, "sin_retorno": ~valido, "sesgos": sesgos, "sesgos_est": est, "n_gcp": n_gcp,
            "residuo": residuo, "sigma_pos_h": C.POSICIONAMIENTO[resultado["posicionamiento"]]["h"]}


def precision(sitio, producto, epoca, checkpoints):
    if not checkpoints:
        return None
    e = sitio.epocas[epoca]
    xs = np.array([c["x"] for c in checkpoints])
    ys = np.array([c["y"] for c in checkpoints])
    zv = sitio.muestrear(e["dtm"], xs, ys)
    zm = sitio.muestrear(producto["dtm"], xs, ys)
    err = zm - zv
    res_h = producto["sesgos"] - producto["sesgos_est"]
    eh = np.hypot(res_h[:, 0], res_h[:, 1])
    return {"rmse_z": float(np.sqrt(np.mean(err ** 2))), "media_z": float(err.mean()), "max_z": float(np.abs(err).max()),
            "rmse_h": float(np.sqrt((np.mean(eh ** 2) if len(eh) else 0.0) + producto.get("sigma_pos_h", 0.0) ** 2)), "n": len(err),
            "errores": [{"id": c["id"], "x": c["x"], "y": c["y"], "dz": float(d)} for c, d in zip(checkpoints, err)]}


def curvas(dtm, sitio, intervalo=5.0, paso=2):
    import contourpy
    d = gaussian_filter(dtm, 1.0)[::paso, ::paso]
    X, Y = sitio.malla()
    gen = contourpy.contour_generator(X[::paso, ::paso], Y[::paso, ::paso], d)
    z0 = math.ceil(float(d.min()) / intervalo) * intervalo
    res = []
    for nivel in np.arange(z0, float(d.max()), intervalo):
        for l in gen.lines(nivel):
            if len(l) > 3:
                res.append((float(nivel), l[::2] if len(l) > 40 else l))
    return res


def _volumen_acopio(sitio, dtm, puntos):
    m = sitio.mascara(puntos)
    if m.sum() < 10:
        return 0.0, 0.0
    borde = binary_dilation(m, iterations=2) & ~m
    ii, jj = np.nonzero(borde)
    xs, ys = sitio.a_xy(ii, jj)
    A = np.column_stack([xs, ys, np.ones(len(xs))])
    coef, *_ = np.linalg.lstsq(A, dtm[ii, jj], rcond=None)
    X, Y = sitio.malla()
    plano = coef[0] * X + coef[1] * Y + coef[2]
    h = np.where(m, dtm - plano, 0)
    return float(np.clip(h, 0, None).sum() * sitio.res ** 2), float(h.max())


def comparar(sitio, prod_a, prod_b, prec_a=None, prec_b=None):
    dod = (prod_b["dtm"] - prod_a["dtm"]).astype(np.float32)
    sa = prec_a["rmse_z"] if prec_a else 0.1
    sb = prec_b["rmse_z"] if prec_b else 0.1
    lod = max(0.15, 1.96 * math.sqrt(sa * sa + sb * sb))
    sin_dato = binary_dilation(prod_a["sin_retorno"] | prod_b["sin_retorno"], iterations=max(1, int(5 / sitio.res)))
    ha = prec_a["rmse_h"] if prec_a else 0.05
    hb = prec_b["rmse_h"] if prec_b else 0.05
    tan_p = np.tan(np.radians(np.minimum(pendiente(prod_a["dtm"], sitio.res, 1.5), 85)))
    lod_mapa = lod + (1.96 * math.sqrt(ha * ha + hb * hb) + 0.5 * sitio.res) * tan_p
    sig = (np.abs(dod) > lod_mapa) & ~sin_dato
    celda = sitio.res ** 2
    zonas = []
    autorizada = np.zeros_like(sig)
    acopios = np.zeros_like(sig)
    for z in sitio.zonas:
        if z["tipo"] == "vuelo":
            continue
        m = sitio.mascara(z["puntos"])
        if z["tipo"] == "extraccion":
            autorizada |= m
        if z["tipo"] == "acopio":
            acopios |= m
        corte = float(-dod[m & sig & (dod < 0)].sum() * celda)
        relleno = float(dod[m & sig & (dod > 0)].sum() * celda)
        fila = {"nombre": z["nombre"], "tipo": z["tipo"], "corte": corte, "relleno": relleno, "neto": relleno - corte,
                "area": float((m & sig).sum() * celda), "ton": corte * C.DENSIDAD_ROCA}
        if z["tipo"] == "acopio":
            va, ha = _volumen_acopio(sitio, prod_a["dtm"], z["puntos"])
            vb, hb = _volumen_acopio(sitio, prod_b["dtm"], z["puntos"])
            fila.update(vol_a=va, vol_b=vb, alto_b=hb)
        if z["tipo"] == "extraccion" and z.get("cota_piso") is not None:
            bajo = m & (prod_b["dtm"] < z["cota_piso"])
            fila["bajo_cota_area"] = float(bajo.sum() * celda)
            fila["bajo_cota_vol"] = float((z["cota_piso"] - prod_b["dtm"])[bajo].sum() * celda)
            fila["piso_b"] = float(prod_b["dtm"][m].min())
        zonas.append(fila)
    fuera = sig & (dod < 0) & ~autorizada & ~acopios
    lab, n = label(binary_dilation(fuera, iterations=max(2, int(6 / sitio.res))) & ~autorizada & ~acopios)
    alertas = []
    if max(sa, sb) > 0.25:
        alertas.append({"tipo": "precision", "titulo": "Precisión vertical insuficiente para comparar", "x": sitio.ancho / 2,
                        "y": sitio.ancho / 2, "severidad": "media", "fuente": "Puntos de control",
                        "detalle": f"RMSE A {sa:.2f} m · B {sb:.2f} m: sólo se distinguen cambios mayores a {lod:.2f} m; "
                                   "vuela con RTK o PPK"})
    if n:
        for k in range(1, n + 1):
            mk = (lab == k) & fuera
            area = mk.sum() * celda
            if area < 40:
                continue
            vol = float(-dod[mk].sum() * celda)
            prof = float(-dod[mk].min())
            media = vol / max(area, 1)
            if vol < 1000 and (vol < 60 or prof < max(1.0, 3 * lod)):
                continue
            if prof < 2 * lod and media < 1.5 * lod:
                continue
            ii, jj = np.nonzero(mk)
            cx, cy = sitio.a_xy(ii.mean(), jj.mean())
            alertas.append({"tipo": "fuera_zona", "titulo": "Extracción fuera de la zona autorizada", "x": float(cx), "y": float(cy),
                            "severidad": "crítica", "fuente": "Comparación A/B",
                            "detalle": f"{vol:,.0f} m³ ({vol * C.DENSIDAD_ROCA:,.0f} t) en {area:,.0f} m², prof. máx. "
                                       f"{prof:.1f} m".replace(",", " ")})
    for z, fila in zip([z for z in sitio.zonas if z["tipo"] != "vuelo"], zonas):
        if fila.get("bajo_cota_area", 0) > 20:
            m = sitio.mascara(z["puntos"]) & (prod_b["dtm"] < z["cota_piso"])
            ii, jj = np.nonzero(m)
            cx, cy = sitio.a_xy(ii.mean(), jj.mean())
            alertas.append({"tipo": "bajo_cota", "titulo": "Excavación por debajo de la cota de diseño", "x": float(cx), "y": float(cy),
                            "severidad": "alta", "fuente": "Comparación A/B",
                            "detalle": f"{z['nombre']}: {fila['bajo_cota_area']:.0f} m² bajo la cota {z['cota_piso']:.1f} m "
                                       f"(piso medido {fila['piso_b']:.1f} m)"})
        if z["tipo"] == "restringida" and max(fila["corte"], fila["relleno"]) > 500:
            cx, cy = T.centroide(z["puntos"])
            alertas.append({"tipo": "restringida", "titulo": f"Movimiento de material en {z['nombre']}", "x": cx, "y": cy,
                            "severidad": "alta", "fuente": "Comparación A/B",
                            "detalle": f"Corte {fila['corte']:.0f} m³ · relleno {fila['relleno']:.0f} m³"})
    total_corte = float(-dod[sig & (dod < 0)].sum() * celda)
    total_relleno = float(dod[sig & (dod > 0)].sum() * celda)
    return {"dod": dod, "lod": lod, "zonas": zonas, "alertas": alertas, "corte": total_corte, "relleno": total_relleno,
            "fuera": float(-dod[fuera].sum() * celda), "metodos": (prod_a["metodo"], prod_b["metodo"])}


def _capturas_sobre(capturas, x, y):
    res = []
    for c in capturas:
        dx, dy = x - c["cx"], y - c["cy"]
        cc, ss = math.cos(c["rumbo"]), math.sin(c["rumbo"])
        u, v = dx * cc + dy * ss, -dx * ss + dy * cc
        if abs(u) <= c["ra"] and abs(v) <= c["rb"]:
            res.append(c)
    return res


def termografia(sitio, resultado, umbral=15.0, semilla=8):
    rng = np.random.default_rng(semilla)
    e = sitio.epocas[resultado["epoca"]]
    Tv = T.temperatura(sitio, resultado["epoca"])
    cob = _cobertura_1m(sitio, resultado["cobertura"])
    netd = resultado["plan"]["camara"].get("netd", 0.05)
    mapa = np.where(cob >= 1, Tv + rng.normal(0, netd * 4, Tv.shape), np.nan).astype(np.float32)
    candidatos = [dict(h, origen="hallazgo") for h in e["hallazgos"] if h["tipo"] == "termico"]
    for o in e["objetos"]:
        if o.get("temp", 0) >= 60 and o["tipo"] in ("camion", "pala", "perforadora", "trituradora"):
            candidatos.append({"tipo": "equipo", "titulo": o["nombre"], "x": o["x"], "y": o["y"], "tam": max(1.5, o["w"] * 0.4),
                               "temp": o["temp"], "origen": "equipo"})
    alertas = []
    caps = resultado["capturas"]
    for c in candidatos:
        sobre = _capturas_sobre(caps, c["x"], c["y"])
        if not sobre:
            continue
        mejor = min(sobre, key=lambda q: q["gsd"])
        px = c["tam"] / mejor["gsd"]
        fondo = float(np.nanmedian(Tv[max(0, int(sitio.a_ij(c["x"], c["y"])[0]) - 15):int(sitio.a_ij(c["x"], c["y"])[0]) + 15,
                                      max(0, int(sitio.a_ij(c["x"], c["y"])[1]) - 15):int(sitio.a_ij(c["x"], c["y"])[1]) + 15]))
        mezcla = min(1.0, (px / 3.0) ** 2)
        aparente = fondo + (c["temp"] - fondo) * mezcla + rng.normal(0, 0.6)
        if aparente - fondo < umbral or aparente < 45:
            continue
        if c["origen"] == "equipo" and c["temp"] < 85:
            sev, titulo = "info", f"{c['titulo']}: motor en operación"
        else:
            sev = "crítica" if aparente >= 100 else "alta" if aparente >= 80 else "media"
            titulo = c["titulo"]
        alertas.append({"tipo": "termico", "titulo": titulo, "x": c["x"], "y": c["y"], "severidad": sev,
                        "fuente": f"Térmica (GSD {mejor['gsd'] * 100:.1f} cm, {px:.0f} px)", "temp": round(aparente, 1),
                        "detalle": f"{aparente:.0f} °C medidos (fondo {fondo:.0f} °C, ΔT {aparente - fondo:.0f} °C)"
                                   + ("" if mezcla >= 1 else " · objeto pequeño: temperatura subestimada, acerca el dron")})
    return {"mapa": mapa, "alertas": alertas, "cobertura": cob}


def inspeccion_visual(sitio, resultado, semilla=9):
    rng = np.random.default_rng(semilla)
    e = sitio.epocas[resultado["epoca"]]
    caps = resultado["capturas"]
    alertas = []
    for h in e["hallazgos"]:
        if h["tipo"] == "termico":
            continue
        sobre = _capturas_sobre(caps, h["x"], h["y"])
        if not sobre:
            continue
        mejor = min(sobre, key=lambda q: q["gsd"])
        px = h["tam"] / mejor["gsd"]
        requerido = 6.0 if h["tipo"] == "grieta" else 4.0
        prob = 1 - math.exp(-(px / requerido) ** 2) * (1 if len(sobre) < 3 else 0.6)
        if rng.uniform() > prob:
            continue
        alertas.append({"tipo": h["tipo"], "titulo": h["titulo"], "x": h["x"], "y": h["y"], "severidad": h["severidad"],
                        "fuente": f"Visual (GSD {mejor['gsd'] * 100:.1f} cm · {len(sobre)} fotos · confianza {prob * 100:.0f}%)",
                        "detalle": h["detalle"], "puntos": h.get("puntos")})
    return {"alertas": alertas}


def analisis_geometrico(sitio, prod, epoca, prod_previo=None):
    alertas = []
    res = sitio.res
    talud = pendiente(prod["dtm"], res, 6.0)
    for z in sitio.zonas_de("extraccion"):
        m = sitio.mascara(z["puntos"])
        exceso = m & (talud > C.TALUD_DISENO + 5)
        lab, n = label(exceso)
        if n:
            areas = np.bincount(lab.ravel())[1:] * res * res
            for k in np.argsort(-areas)[:3]:
                if areas[k] < 150:
                    continue
                mk = lab == k + 1
                ii, jj = np.nonzero(mk)
                cx, cy = sitio.a_xy(ii.mean(), jj.mean())
                alertas.append({"tipo": "talud", "titulo": "Talud más inclinado que el diseño", "x": float(cx), "y": float(cy),
                                "severidad": "alta", "fuente": f"Geometría ({prod['metodo']})",
                                "detalle": f"Ángulo interrampa hasta {talud[mk].max():.0f}° (diseño {C.TALUD_DISENO:.0f}°) en {areas[k]:.0f} m²"})
    caminos = np.zeros((sitio.ny, sitio.nx), bool)
    for cam in sitio.caminos:
        p = np.asarray(cam["puntos"], dtype=float)
        for a, b in zip(p[:-1], p[1:]):
            n = int(np.hypot(*(b - a)) / res) + 2
            t = np.linspace(0, 1, n)[:, None]
            q = a + (b - a) * t
            i, j = sitio.a_ij(q[:, 0], q[:, 1])
            ok = (i >= 0) & (i < sitio.ny) & (j >= 0) & (j < sitio.nx)
            caminos[i[ok].astype(int), j[ok].astype(int)] = True
    caminos = binary_dilation(caminos, iterations=max(1, int(6 / res)))
    residuo = prod["dtm"] - median_filter(prod["dtm"], size=max(5, int(9 / res)) | 1)
    bulto = caminos & (residuo > 0.6)
    if prod_previo is not None:
        bulto |= caminos & ((prod["dtm"] - prod_previo["dtm"]) > 0.8)
    lab, n = label(bulto)
    if n:
        areas = np.bincount(lab.ravel())[1:] * res * res
        for k in np.flatnonzero(areas >= 12)[:4]:
            mk = lab == k + 1
            ii, jj = np.nonzero(mk)
            cx, cy = sitio.a_xy(ii.mean(), jj.mean())
            alertas.append({"tipo": "derrumbe", "titulo": "Obstrucción en camino de acarreo", "x": float(cx), "y": float(cy),
                            "severidad": "media", "fuente": f"Geometría ({prod['metodo']})",
                            "detalle": f"Bulto de {residuo[mk].max():.1f} m sobre la vía en {areas[k]:.0f} m²"})
    if prod["metodo"] == "LiDAR":
        for z in sitio.zonas_de("extraccion"):
            m = sitio.mascara(z["puntos"])
            hueco = m & prod["sin_retorno"] & (pendiente(prod["dtm"], res, 3.0) < 6)
            hueco = binary_dilation(hueco, iterations=1)
            lab, n = label(hueco)
            if n:
                areas = np.bincount(lab.ravel())[1:] * res * res
                for k in np.flatnonzero(areas >= 80)[:3]:
                    mk = lab == k + 1
                    ii, jj = np.nonzero(mk)
                    cx, cy = sitio.a_xy(ii.mean(), jj.mean())
                    alertas.append({"tipo": "agua", "titulo": "Posible agua acumulada (sin retornos LiDAR)", "x": float(cx),
                                    "y": float(cy), "severidad": "media", "fuente": "LiDAR",
                                    "detalle": f"Área plana sin retornos de {areas[k]:.0f} m² en {z['nombre']}"})
            surco = m & (residuo < -0.45) & (prod["densidad"] > 1.0)
            lab, n = label(surco, structure=np.ones((3, 3)))
            if n:
                tam = np.bincount(lab.ravel())[1:]
                for k in np.flatnonzero(tam >= int(18 / res)):
                    mk = lab == k + 1
                    ii, jj = np.nonzero(mk)
                    largo = math.hypot(np.ptp(ii), np.ptp(jj)) * res
                    if largo < 15 or tam[k] * res * res / max(largo, 1) > 3.0:
                        continue
                    cx, cy = sitio.a_xy(ii.mean(), jj.mean())
                    alertas.append({"tipo": "grieta", "titulo": "Posible grieta de tensión (LiDAR)", "x": float(cx), "y": float(cy),
                                    "severidad": "alta", "fuente": "LiDAR (residuo del DTM)",
                                    "detalle": f"Surco lineal de {largo:.0f} m y {-residuo[mk].min():.1f} m de profundidad"})
    objetos = sitio.epocas[epoca]["objetos"]
    for z in sitio.zonas_de("exclusion"):
        for o in objetos:
            if o["tipo"] in ("persona", "camioneta") and T.Path(np.asarray(z["puntos"])).contains_point((o["x"], o["y"])):
                o["_en_zona"] = z["nombre"]
    return {"alertas": alertas, "talud": talud}


def deduplicar(alertas, radio=25.0):
    orden = {"crítica": 0, "alta": 1, "media": 2, "info": 3}
    res = []
    for a in sorted(alertas, key=lambda a: orden.get(a["severidad"], 4)):
        r = radio * (2.5 if a["tipo"] in ("agua", "derrumbe", "grieta") else 1.0)
        dup = next((b for b in res if b["tipo"] == a["tipo"] and math.hypot(a["x"] - b["x"], a["y"] - b["y"]) < r), None)
        if dup is None:
            res.append(dict(a, fuentes=[a.get("fuente", "")]))
        elif a.get("fuente") and a["fuente"] not in dup["fuentes"]:
            dup["fuentes"].append(a["fuente"])
            dup["fuente"] = " + ".join(dup["fuentes"])
    return res
