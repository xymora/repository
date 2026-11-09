import math

import numpy as np
from scipy.ndimage import maximum_filter

import config as C
import terreno as T


def _rotar(p, ang):
    c, s = math.cos(ang), math.sin(ang)
    p = np.asarray(p, dtype=float)
    return np.column_stack([p[:, 0] * c - p[:, 1] * s, p[:, 0] * s + p[:, 1] * c])


def _cortes_horizontales(pol, y):
    xs = []
    n = len(pol)
    for k in range(n):
        x0, y0 = pol[k]
        x1, y1 = pol[(k + 1) % n]
        if (y0 <= y < y1) or (y1 <= y < y0):
            xs.append(x0 + (y - y0) * (x1 - x0) / (y1 - y0))
    xs.sort()
    return [(xs[i], xs[i + 1]) for i in range(0, len(xs) - 1, 2)]


def lineas(pol, angulo, espaciado, extension=0.0):
    r = _rotar(pol, -angulo)
    y0, y1 = r[:, 1].min(), r[:, 1].max()
    n = max(1, int(math.ceil((y1 - y0) / espaciado)))
    paso = (y1 - y0) / n
    res = []
    for k in range(n + 1):
        y = min(y0 + k * paso, y1 - 1e-6) if k == n else y0 + k * paso + (1e-6 if k == 0 else 0)
        tramos = _cortes_horizontales(r, y)
        if not tramos:
            continue
        for a, b in tramos:
            if b - a < 2:
                continue
            seg = np.array([[a - extension, y], [b + extension, y]])
            if len(res) % 2:
                seg = seg[::-1]
            res.append(_rotar(seg, angulo))
    return res


def angulo_optimo(pol, espaciado):
    mejor = None
    for g in range(0, 180, 3):
        a = math.radians(g)
        r = _rotar(pol, -a)
        n = (r[:, 1].max() - r[:, 1].min()) / espaciado
        largo = r[:, 0].max() - r[:, 0].min()
        clave = (math.ceil(n), -largo)
        if mejor is None or clave < mejor[0]:
            mejor = (clave, a)
    return mejor[1]


def _densificar(p, paso):
    p = np.asarray(p, dtype=float)
    out = [p[:1]]
    for a, b in zip(p[:-1], p[1:]):
        d = np.linalg.norm(b[:2] - a[:2])
        n = max(1, int(math.ceil(d / paso)))
        t = np.linspace(0, 1, n + 1)[1:, None]
        out.append(a + (b - a) * t)
    return np.vstack(out)


def huella(camara, h):
    return camara["sensor_w"] / camara["focal"] * h, camara["sensor_h"] / camara["focal"] * h


def gsd(camara, h):
    return camara["sensor_w"] * h / (camara["focal"] * camara["px_w"])


def _poi(sitio, epoca, tipo):
    e = sitio.epocas[epoca]
    pois = []
    vistos = set()
    clases = ("trituradora", "subestacion", "pala", "perforadora", "tanque") if tipo == "termica" else \
        ("trituradora", "subestacion", "pala", "perforadora")
    for o in e["objetos"]:
        if o["tipo"] in clases and o["nombre"] not in vistos:
            pois.append((o["x"], o["y"], o["nombre"], 30.0))
            vistos.add(o["nombre"])
    bandas = [o for o in e["objetos"] if o["tipo"] == "banda"]
    if bandas:
        pois.append((float(np.mean([o["x"] for o in bandas])), float(np.mean([o["y"] for o in bandas])), "Banda transportadora", 45.0))
    for z in sitio.zonas_de("acopio"):
        cx, cy = T.centroide(z["puntos"])
        pois.append((cx, cy, z["nombre"], 40.0))
    return pois


def _orbita(cx, cy, radio, n=14):
    t = np.linspace(0, 2 * math.pi, n + 1)
    return np.column_stack([cx + radio * np.cos(t), cy + radio * np.sin(t)])


def planear(sitio, epoca, tipo, params):
    p = dict(params)
    h = float(p.get("altura", 80.0))
    v = float(p.get("velocidad", C.DRON["velocidad"]))
    sup = sitio.superficie("A")
    alto = maximum_filter(sup, size=max(3, int(30 / sitio.res)))
    area = p.get("area")
    if not area:
        m = 0.04 * sitio.ancho
        area = [(m, m), (sitio.ancho - m, m), (sitio.ancho - m, sitio.ancho - m), (m, sitio.ancho - m)]
    area = [tuple(q) for q in area]
    stats = {"tipo": tipo, "altura": h, "velocidad": v}
    camara = lidar = None
    if tipo == "lidar":
        lidar = C.LIDAR[p.get("sensor") or next(iter(C.LIDAR))]
        franja = 2 * h * math.tan(math.radians(lidar["fov"] / 2))
        espaciado = franja * (1 - p.get("traslape_l", 0.5))
        paso_disparo = None
        stats.update(franja=franja, espaciado=espaciado,
                     densidad_nominal=lidar["pps"] / (v * franja) / max(1 - p.get("traslape_l", 0.5), 0.05))
    else:
        nombre = p.get("sensor") or ("Térmica 640 (13 mm)" if tipo == "termica" else "RGB 20 MP (1\")")
        camara = C.CAMARAS[nombre]
        ancho, largo = huella(camara, h)
        espaciado = ancho * (1 - p.get("traslape_l", 0.7))
        paso_disparo = largo * (1 - p.get("traslape_f", 0.8))
        stats.update(huella=(ancho, largo), espaciado=espaciado, paso_disparo=paso_disparo, gsd=gsd(camara, h))
    ang = p.get("angulo")
    ang = angulo_optimo(area, espaciado) if ang is None else math.radians(ang)
    segs = lineas(area, ang, espaciado, extension=espaciado * 0.3 if tipo != "lidar" else 20.0)
    tramos = [{"xy": s, "tipo": "linea"} for s in segs]
    if tipo in ("termica", "visual"):
        for cx, cy, nombre, radio in _poi(sitio, epoca if epoca in sitio.epocas else "A", tipo):
            tramos.append({"xy": _orbita(cx, cy, radio), "tipo": "orbita", "centro": (cx, cy), "nombre": nombre,
                           "agl": max(25.0, h * 0.45)})
    if tipo == "visual":
        for z in sitio.zonas_de("extraccion"):
            pts = np.asarray(z["puntos"] + [z["puntos"][0]], dtype=float)
            tramos.append({"xy": pts, "tipo": "corona", "nombre": z["nombre"], "agl": max(30.0, h * 0.6)})
    seguir = p.get("seguir_terreno", True)
    for t in tramos:
        q = _densificar(t["xy"], 12.0)
        q[:, 0] = np.clip(q[:, 0], 1, sitio.ancho - 1)
        q[:, 1] = np.clip(q[:, 1], 1, sitio.ancho - 1)
        zt = sitio.muestrear(alto, q[:, 0], q[:, 1])
        agl = t.get("agl", h)
        if seguir or t["tipo"] != "linea":
            z = zt + agl
            k = max(1, int(60 / 12))
            z = np.convolve(np.pad(z, k, mode="edge"), np.ones(2 * k + 1) / (2 * k + 1), mode="valid")
            z = np.maximum(z, zt + agl * 0.85)
        else:
            z = np.full(len(q), zt.max() + agl)
        t["p"] = np.column_stack([q, z])
        t["largo"] = float(np.sum(np.linalg.norm(np.diff(q, axis=0), axis=1)))
    n_drones = max(1, int(p.get("drones", 1)))
    total = sum(t["largo"] for t in tramos)
    grupos, acum, meta = [[] for _ in range(n_drones)], 0.0, total / n_drones
    for t in tramos:
        g = min(n_drones - 1, int(acum / meta)) if meta > 0 else 0
        grupos[g].append(t)
        acum += t["largo"]
    base = np.array(sitio.base, dtype=float)
    zb = float(sitio.muestrear(sup, *base)[0])
    autonomia = C.DRON["bateria_min"] * 60 * (1 - C.DRON["reserva"])
    rutas = []
    for d, grupo in enumerate(grupos):
        vuelos = []
        actual, t_act = [], 0.0
        pos = np.array([base[0], base[1], zb + 30])

        def traslado(a, b):
            zt = max(a[2], b[2]) + 10
            return np.linalg.norm(b[:2] - a[:2]) / v + abs(zt - a[2]) / C.DRON["ascenso"] + abs(zt - b[2]) / C.DRON["ascenso"]

        inicio = np.array([base[0], base[1], zb + 30])
        for t in grupo:
            q = t["p"]
            ida = traslado(pos, q[0])
            dur = t["largo"] / v + C.DRON["giro_s"]
            vuelta = traslado(q[-1], inicio)
            if actual and t_act + ida + dur + vuelta > autonomia:
                vuelos.append(_cerrar(actual, inicio, zb, v))
                actual, t_act, pos = [], 0.0, inicio.copy()
                ida = traslado(pos, q[0])
            actual.append(t)
            t_act += ida + dur
            pos = q[-1]
        if actual:
            vuelos.append(_cerrar(actual, inicio, zb, v))
        rutas.append({"dron": d + 1, "vuelos": vuelos})
    capturas = []
    if camara is not None:
        for r in rutas:
            for k, vu in enumerate(r["vuelos"]):
                for t in vu["tramos"]:
                    q = t["p"]
                    if t["tipo"] == "linea":
                        paso = paso_disparo
                    else:
                        paso = max(6.0, paso_disparo * 0.5)
                    s = np.concatenate([[0], np.cumsum(np.linalg.norm(np.diff(q[:, :2], axis=0), axis=1))])
                    for d in np.arange(0, s[-1] + 1e-6, paso):
                        x = np.interp(d, s, q[:, 0])
                        y = np.interp(d, s, q[:, 1])
                        z = np.interp(d, s, q[:, 2])
                        i = min(len(q) - 2, int(np.searchsorted(s, d, side="right") - 1))
                        rumbo = math.atan2(q[i + 1, 1] - q[i, 1], q[i + 1, 0] - q[i, 0])
                        mira = t.get("centro")
                        capturas.append({"x": float(x), "y": float(y), "z": float(z), "rumbo": rumbo, "dron": r["dron"],
                                         "vuelo": k, "s": float(vu["s_inicio"][id(t)] + d), "tipo": t["tipo"],
                                         "mira": mira})
    tiempo = sum(vu["tiempo"] for r in rutas for vu in r["vuelos"])
    distancia = sum(vu["distancia"] for r in rutas for vu in r["vuelos"])
    stats.update(angulo=math.degrees(ang), n_lineas=len(segs), longitud=distancia, tiempo=tiempo,
                 tiempo_paralelo=max((sum(vu["tiempo"] for vu in r["vuelos"]) for r in rutas), default=0),
                 baterias=sum(len(r["vuelos"]) for r in rutas), n_capturas=len(capturas),
                 area_ha=T.area_poligono(area) / 1e4, drones=n_drones, n_orbitas=sum(t["tipo"] == "orbita" for t in tramos))
    if camara is not None:
        agls = [c["z"] - float(sitio.muestrear(sup, c["x"], c["y"])[0]) for c in capturas[:: max(1, len(capturas) // 400)]]
        stats["gsd_medio"] = float(np.mean([gsd(camara, max(a, 5)) for a in agls])) if agls else stats["gsd"]
    return {"tipo": tipo, "params": {k: v for k, v in p.items() if k != "area"}, "area": [list(q) for q in area],
            "rutas": rutas, "capturas": capturas, "stats": stats, "camara": camara, "lidar": lidar, "epoca": epoca}


def _cerrar(tramos, inicio, zb, v):
    pts = [np.array([[inicio[0], inicio[1], zb + 2], inicio])]
    s_inicio = {}
    largo = 0.0
    previo = inicio
    for t in tramos:
        q = t["p"]
        zt = max(previo[2], q[0, 2]) + 10
        enlace = np.array([[previo[0], previo[1], zt], [q[0, 0], q[0, 1], zt], q[0]])
        pts.append(enlace)
        largo += np.linalg.norm(q[0, :2] - previo[:2])
        s_inicio[id(t)] = None
        pts.append(q)
        previo = q[-1]
    zt = previo[2] + 10
    pts.append(np.array([[previo[0], previo[1], zt], [inicio[0], inicio[1], zt], [inicio[0], inicio[1], zb + 2]]))
    p = np.vstack(pts)
    s = np.concatenate([[0], np.cumsum(np.linalg.norm(np.diff(p, axis=0), axis=1))])
    k = 0
    acumulado = 0
    for t in tramos:
        q = t["p"]
        dist = np.linalg.norm(p[:, :3] - q[0], axis=1)
        idx = int(np.argmin(dist[k:]) + k)
        s_inicio[id(t)] = float(s[idx])
        k = idx
    tiempo = s[-1] / v + len(tramos) * C.DRON["giro_s"] + 60
    return {"puntos": p, "s": s, "tramos": tramos, "s_inicio": s_inicio, "tiempo": float(tiempo), "distancia": float(s[-1])}


def resumen(plan):
    st = plan["stats"]
    lineas_txt = [f"{C.MISIONES[plan['tipo']]}",
                  f"Altura {st['altura']:.0f} m sobre el terreno · {st['velocidad']:.0f} m/s · rumbo {st['angulo']:.0f}°",
                  f"{st['n_lineas']} líneas cada {st['espaciado']:.1f} m · {st['area_ha']:.1f} ha"]
    if plan["camara"] is not None:
        a, l = st["huella"]
        lineas_txt.append(f"GSD {st['gsd'] * 100:.2f} cm/px (medio {st.get('gsd_medio', st['gsd']) * 100:.2f}) · huella {a:.0f}×{l:.0f} m")
        lineas_txt.append(f"{st['n_capturas']} fotos (disparo cada {st['paso_disparo']:.1f} m)")
    else:
        lineas_txt.append(f"Franja {st['franja']:.0f} m · densidad nominal {st['densidad_nominal']:.0f} pts/m²")
    if st["n_orbitas"]:
        lineas_txt.append(f"{st['n_orbitas']} órbitas a puntos de interés")
    lineas_txt.append(f"{st['longitud'] / 1000:.1f} km · {st['tiempo'] / 60:.0f} min de vuelo · {st['baterias']} baterías · "
                      f"{st['drones']} dron(es) → {st['tiempo_paralelo'] / 60:.0f} min")
    return lineas_txt
