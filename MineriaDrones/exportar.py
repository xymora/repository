import csv
import json
import math
import os
import struct

import numpy as np
from PIL import Image

import config as C
import geo as G
import terreno as T


def escribir_las(ruta, georef, prod):
    x, y, z = prod["x"].astype(np.float64), prod["y"].astype(np.float64), prod["z"].astype(np.float64)
    e, n = georef.a_utm(x, y)
    epsg = G.epsg_utm(georef.zona_utm)
    escala = 0.001
    off = (math.floor(e.min()), math.floor(n.min()), math.floor(z.min()))
    X = np.round((e - off[0]) / escala).astype(np.int32)
    Y = np.round((n - off[1]) / escala).astype(np.int32)
    Z = np.round((z - off[2]) / escala).astype(np.int32)
    claves = [1, 1, 0, 3, 1024, 0, 1, 1, 1025, 0, 1, 1, 3072, 0, 1, epsg]
    vlr_datos = struct.pack("<" + "H" * len(claves), *claves)
    vlr = struct.pack("<H16sHH32s", 0, b"LASF_Projection", 34735, len(vlr_datos), b"GeoKeyDirectoryTag") + vlr_datos
    n_pts = len(X)
    cabecera = 227
    offset_datos = cabecera + len(vlr)
    ret = (prod["r"].astype(np.uint8) & 7) | ((prod["n"].astype(np.uint8) & 7) << 3)
    dt = np.dtype([("x", "<i4"), ("y", "<i4"), ("z", "<i4"), ("i", "<u2"), ("r", "u1"), ("c", "u1"), ("a", "i1"),
                   ("u", "u1"), ("p", "<u2")])
    reg = np.zeros(n_pts, dtype=dt)
    reg["x"], reg["y"], reg["z"], reg["i"], reg["r"], reg["c"] = X, Y, Z, prod["i"], ret, prod["clase"]
    por_ret = [int((prod["r"] == k).sum()) for k in range(1, 6)]
    h = bytearray()
    h += b"LASF"
    h += struct.pack("<HH", 0, 0)
    h += struct.pack("<IHH8s", 0, 0, 0, b"\0" * 8)
    h += struct.pack("<BB", 1, 2)
    h += b"MineriaDrones".ljust(32, b"\0")
    h += b"MineriaDrones simulador".ljust(32, b"\0")
    import datetime
    hoy = datetime.date.today()
    h += struct.pack("<HH", hoy.timetuple().tm_yday, hoy.year)
    h += struct.pack("<HIIBHI", cabecera, offset_datos, 1, 0, 20, n_pts)
    h += struct.pack("<5I", *por_ret)
    h += struct.pack("<3d", escala, escala, escala)
    h += struct.pack("<3d", *map(float, off))
    h += struct.pack("<6d", float(e.max()), float(e.min()), float(n.max()), float(n.min()), float(z.max()), float(z.min()))
    assert len(h) == cabecera
    with open(ruta, "wb") as f:
        f.write(h)
        f.write(vlr)
        f.write(reg.tobytes())
    with open(os.path.splitext(ruta)[0] + ".prj", "w") as f:
        f.write(f"EPSG:{epsg}")
    return ruta


def escribir_asc(ruta, sitio, arr, nodata=-9999.0):
    a = np.where(np.isfinite(arr), arr, nodata)
    with open(ruta, "w") as f:
        f.write(f"ncols {sitio.nx}\nnrows {sitio.ny}\nxllcorner 0\nyllcorner 0\ncellsize {sitio.res:.6f}\nNODATA_value {nodata}\n")
        np.savetxt(f, a, fmt="%.3f")
    with open(os.path.splitext(ruta)[0] + ".prj", "w") as f:
        f.write(sitio.georef.wkt())
    return ruta


def escribir_obj(ruta, sitio, dtm, textura, paso=4, exag=1.0):
    base = os.path.splitext(ruta)[0]
    nombre = os.path.basename(base)
    d = dtm[::paso, ::paso]
    ny, nx = d.shape
    X, Y = sitio.malla()
    xs, ys = X[::paso, ::paso], Y[::paso, ::paso]
    Image.fromarray(textura).save(base + "_textura.jpg", quality=90)
    with open(base + ".mtl", "w") as f:
        f.write(f"newmtl terreno\nKa 1 1 1\nKd 1 1 1\nmap_Kd {nombre}_textura.jpg\n")
    z0 = float(d.min())
    with open(ruta, "w") as f:
        f.write(f"mtllib {nombre}.mtl\no terreno\n")
        v = np.column_stack([xs.ravel(), (d.ravel() - z0) * exag, -ys.ravel()])
        np.savetxt(f, v, fmt="v %.2f %.2f %.2f")
        u = (np.arange(nx) * paso + 0.5) / sitio.nx
        w = 1 - (np.arange(ny) * paso + 0.5) / sitio.ny
        U, W = np.meshgrid(u, w)
        np.savetxt(f, np.column_stack([U.ravel(), W.ravel()]), fmt="vt %.5f %.5f")
        f.write("usemtl terreno\n")
        i = np.arange(ny - 1)[:, None] * nx + np.arange(nx - 1)[None, :] + 1
        a, b, c, e = i.ravel(), (i + 1).ravel(), (i + nx).ravel(), (i + nx + 1).ravel()
        caras = np.column_stack([a, a, c, c, b, b, b, b, c, c, e, e]).reshape(-1, 6)
        np.savetxt(f, caras, fmt="f %d/%d %d/%d %d/%d")
    with open(base + "_origen.txt", "w", encoding="utf-8") as f:
        f.write(f"Modelo en metros (X este, Y arriba, Z sur). Elevación = Y + {z0:.2f} m. Proyección: {sitio.georef.wkt()}\n")
    return ruta


def _feature(geom, props):
    return {"type": "Feature", "geometry": geom, "properties": props}


def _ll(georef, pts):
    p = np.asarray(pts, dtype=float)
    lat, lon = georef.a_latlon(p[:, 0], p[:, 1])
    return np.column_stack([lon, lat]).round(7).tolist()


def escribir_geojson(ruta, sitio, alertas=(), curvas=(), plan=None, comparacion=None):
    g = sitio.georef
    feats = []
    filas = {f["nombre"]: f for f in (comparacion or {}).get("zonas", [])}
    for z in sitio.zonas:
        anillo = _ll(g, z["puntos"] + [z["puntos"][0]])
        props = {"nombre": z["nombre"], "tipo": C.TIPOS_ZONA[z["tipo"]][0], "cota_piso": z.get("cota_piso"),
                 "area_m2": round(T.area_poligono(z["puntos"]), 1)}
        if z["nombre"] in filas:
            props.update({k: round(v, 1) for k, v in filas[z["nombre"]].items() if isinstance(v, float)})
        feats.append(_feature({"type": "Polygon", "coordinates": [anillo]}, props))
    for a in alertas:
        feats.append(_feature({"type": "Point", "coordinates": _ll(g, [[a["x"], a["y"]]])[0]},
                              {"alerta": a["titulo"], "severidad": a["severidad"], "detalle": a.get("detalle", ""),
                               "fuente": a.get("fuente", "")}))
    for nivel, l in curvas:
        feats.append(_feature({"type": "LineString", "coordinates": _ll(g, l)}, {"curva_m": nivel}))
    if plan:
        for r in plan["rutas"]:
            for k, vu in enumerate(r["vuelos"]):
                feats.append(_feature({"type": "LineString", "coordinates": _ll(g, vu["puntos"][:, :2])},
                                      {"dron": r["dron"], "vuelo": k + 1, "tipo": plan["tipo"]}))
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump({"type": "FeatureCollection", "features": feats}, f, ensure_ascii=False)
    return ruta


def escribir_waypoints(carpeta, sitio, plan, superficie):
    rutas = []
    for r in plan["rutas"]:
        for k, vu in enumerate(r["vuelos"]):
            p = vu["puntos"]
            sel = [0]
            for i in range(1, len(p) - 1):
                a, b = p[sel[-1]], p[i]
                if np.linalg.norm(b[:2] - a[:2]) > 40 or abs(b[2] - a[2]) > 3:
                    sel.append(i)
            sel.append(len(p) - 1)
            q = p[sel]
            lat, lon = sitio.georef.a_latlon(q[:, 0], q[:, 1])
            suelo = sitio.muestrear(superficie, q[:, 0], q[:, 1])
            ruta = os.path.join(carpeta, f"waypoints_{plan['tipo']}_dron{r['dron']}_vuelo{k + 1}.csv")
            with open(ruta, "w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(["n", "latitud", "longitud", "altitud_msnm", "altura_sobre_terreno", "velocidad_ms", "accion"])
                for n, (la, lo, zz, sg) in enumerate(zip(lat, lon, q[:, 2], suelo)):
                    w.writerow([n + 1, f"{la:.7f}", f"{lo:.7f}", f"{zz:.1f}", f"{zz - sg:.1f}", plan["stats"]["velocidad"],
                                "disparo por distancia" if plan["camara"] else "lidar"])
            rutas.append(ruta)
    return rutas


def escribir_reporte(ruta, sitio, comparacion, alertas, precisiones):
    with open(ruta, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["Sitio", sitio.nombre])
        lat, lon = sitio.georef.lat, sitio.georef.lon
        w.writerow(["Centro (lat, lon)", f"{lat:.6f}", f"{lon:.6f}"])
        w.writerow([])
        for ep, p in (precisiones or {}).items():
            if p:
                w.writerow([f"Precisión época {ep}", f"RMSE Z {p['rmse_z']:.3f} m", f"RMSE XY {p['rmse_h']:.3f} m",
                            f"{p['n']} puntos de control"])
        if comparacion:
            w.writerow([])
            w.writerow(["Zona", "Tipo", "Corte m3", "Relleno m3", "Neto m3", "Toneladas", "Área con cambio m2",
                        "Vol. acopio A m3", "Vol. acopio B m3", "Bajo cota m2"])
            for z in comparacion["zonas"]:
                w.writerow([z["nombre"], C.TIPOS_ZONA[z["tipo"]][0], round(z["corte"], 1), round(z["relleno"], 1),
                            round(z["neto"], 1), round(z["ton"], 1), round(z["area"], 1), round(z.get("vol_a", 0), 1),
                            round(z.get("vol_b", 0), 1), round(z.get("bajo_cota_area", 0), 1)])
            w.writerow(["Total sitio", "", round(comparacion["corte"], 1), round(comparacion["relleno"], 1), "", "", "", "", "", ""])
            w.writerow(["Fuera de zonas autorizadas", "", round(comparacion["fuera"], 1)])
            w.writerow(["Nivel de detección (m)", round(comparacion["lod"], 3)])
        w.writerow([])
        w.writerow(["Severidad", "Alerta", "Detalle", "Fuente", "Latitud", "Longitud", "UTM E", "UTM N"])
        for a in alertas:
            la, lo = sitio.georef.a_latlon(a["x"], a["y"])
            e, n = sitio.georef.a_utm(a["x"], a["y"])
            w.writerow([a["severidad"], a["titulo"], a.get("detalle", ""), a.get("fuente", ""), f"{float(la):.7f}",
                        f"{float(lo):.7f}", f"{float(e):.2f}", f"{float(n):.2f}"])
    return ruta
