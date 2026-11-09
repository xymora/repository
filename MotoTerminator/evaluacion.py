import argparse
import csv
import datetime as _dt
import hashlib
import inspect
import json
import math
import os
import sys
import time

import numpy as np

import config as C
import fisica as F
from terreno import Pista

AQUI = os.path.dirname(os.path.abspath(__file__))
DIR_RESULTADOS = os.path.join(AQUI, "resultados")
BASE_PRUEBA = 2 ** 31
CLAVES_TRAZA = ("t", "x", "v", "lat", "phi", "th", "cmg_sat", "v_segura", "en_suelo", "invasion")


def en_proyecto(ruta):
    if not ruta:
        return ruta
    ruta = os.path.expanduser(str(ruta))
    return ruta if os.path.isabs(ruta) else os.path.join(AQUI, ruta)


def clopper_pearson(k, n, conf=0.95):
    if n <= 0:
        return 0.0, 1.0
    a = 1.0 - conf
    try:
        from scipy.stats import beta
        lo = 0.0 if k == 0 else float(beta.ppf(a / 2, k, n - k + 1))
        hi = 1.0 if k == n else float(beta.ppf(1 - a / 2, k + 1, n - k))
        return lo, hi
    except ImportError:
        z = 1.959963984540054 if abs(conf - 0.95) < 1e-9 else _z(conf)
        p = k / n
        d = 1 + z * z / n
        c = (p + z * z / (2 * n)) / d
        h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
        return max(0.0, c - h), min(1.0, c + h)


def _z(conf):
    from statistics import NormalDist
    return NormalDist().inv_cdf(0.5 + conf / 2)


def garwood(k, exposicion, conf=0.95):
    if exposicion <= 0:
        return 0.0, float("inf")
    a = 1.0 - conf
    from scipy.stats import chi2
    lo = 0.0 if k == 0 else float(chi2.ppf(a / 2, 2 * k)) / 2
    hi = float(chi2.ppf(1 - a / 2, 2 * k + 2)) / 2
    return lo / exposicion, hi / exposicion


def n_para_afirmar(p_max, conf=0.95):
    return int(math.ceil(math.log(1 - conf) / math.log(1 - p_max)))


def semilla_pista_prueba(nivel, j):
    return BASE_PRUEBA + 1000 * int(nivel) + int(j)


def semilla_ruido_prueba(nivel, j):
    return BASE_PRUEBA + 7919 * (1000 * int(nivel) + int(j) + 1)


def cargar_pesos(modo="terreno", archivo=None):
    if archivo is None:
        base, ext = os.path.splitext(C.ARCHIVO_MEJOR)
        archivo = os.path.join(AQUI, f"{base}_ciudad{ext}" if modo == "ciudad" else C.ARCHIVO_MEJOR)
    archivo = en_proyecto(archivo)
    with open(archivo, encoding="utf-8") as f:
        d = json.load(f)
    if tuple(d["capas"]) != tuple(C.CAPAS):
        raise ValueError(f"{archivo}: capas {d['capas']} no coinciden con config {C.CAPAS}")
    return np.array(d["pesos"], dtype=float), {k: v for k, v in d.items() if k != "pesos"}


def red_vial_local(preferida=None, avisar=lambda *_: None):
    try:
        import calles
    except Exception:
        return None
    nombres = list(calles.ZONAS)
    if preferida in nombres:
        nombres.remove(preferida)
        nombres.insert(0, preferida)
    elif C.ZONA_CALLES in nombres:
        nombres.remove(C.ZONA_CALLES)
        nombres.insert(0, C.ZONA_CALLES)
    for nombre in nombres:
        z = calles.zona_para(nombre)
        if os.path.exists(z.archivo("osm.json")):
            try:
                return calles.RedVial(z, avisar)
            except Exception:
                continue
    return None


def hash_pesos(pesos):
    return hashlib.sha256(np.ascontiguousarray(np.asarray(pesos, dtype=np.float64)).tobytes()).hexdigest()[:16]


def hash_archivo(ruta):
    try:
        with open(ruta, "rb") as f:
            return hashlib.sha256(f.read()).hexdigest()[:16]
    except OSError:
        return None


def _contrato_disponible():
    try:
        params = inspect.signature(F.Simulador.__init__).parameters
    except (TypeError, ValueError):
        return False
    return all(k in params for k in ("max_reintentos", "ruido_por_moto", "filtro_obs", "registrar"))


def v_segura(pista, px, v):
    i = pista.indice(px)
    a_pos = np.minimum(C.A_LAT_MAX, 0.85 * pista.mu_min[i] * C.G)
    return np.minimum(np.sqrt(a_pos / np.maximum(pista.kmax[i], 1e-3)), 30.0)


class _RuidoPorMoto:

    def __init__(self, sim, semilla):
        self.sim, self.rng = sim, np.random.default_rng(semilla)

    def normal(self, *a, **k):
        return self.rng.normal(size=len(self.sim.ids))


class _SimCompat(F.Simulador):

    def __init__(self, pista, pesos, semilla_ruido=0, *, max_reintentos=None, ruido_por_moto=False,
                 filtro_obs=None, controlador=None, n=None, registrar=False):
        if controlador is not None:
            raise NotImplementedError("el fisica.py instalado aún no admite controlador=")
        self._max_r, self._filtro, self._registrar = max_reintentos, filtro_obs, registrar
        self.traza = {k: [] for k in CLAVES_TRAZA} if registrar else None
        super().__init__(pista, pesos, semilla_ruido)
        if ruido_por_moto:
            self.ruido = _RuidoPorMoto(self, semilla_ruido)

    def observar(self):
        obs = super().observar()
        return self._filtro(obs, self) if self._filtro is not None else obs

    def paso(self, ctrl=None):
        if self._max_r is None:
            return super().paso()
        viejo = C.MAX_REINTENTOS
        C.MAX_REINTENTOS = self._max_r
        try:
            super().paso()
        finally:
            C.MAX_REINTENTOS = viejo

    def _revisar(self):
        if self._registrar:
            self._grabar()
        super()._revisar()

    def _grabar(self):
        n, ids = self.n_total, self.ids
        v = self.vx * np.cos(self.th) + self.vy * np.sin(self.th)
        vals = {"x": self.px, "v": v, "lat": self.lat, "phi": self.phi, "th": self.th,
                "cmg_sat": self.cmg_sat, "v_segura": v_segura(self.pista, self.px, v),
                "en_suelo": (self.fn > 0).any(0).astype(float), "invasion": (self.lat > 0).astype(float)}
        self.traza["t"].append(np.full(n, self.t))
        for k, a in vals.items():
            full = np.full(n, np.nan)
            full[ids] = a
            self.traza[k].append(full)

    def traza_arrays(self):
        return {k: np.array(v, dtype=float).reshape(len(v), self.n_total) for k, v in self.traza.items()}

    def llegaron(self):
        return self.motivo == F.META

    def llegadas_limpias(self):
        return (self.motivo == F.META) & (self.reintentos == 0)

    def distancia_km(self):
        return self.progreso / 1000.0


def crear_simulador(pista, pesos, semilla_ruido=0, **kw):
    if _contrato_disponible():
        return F.Simulador(pista, pesos, semilla_ruido, **kw)
    return _SimCompat(pista, pesos, semilla_ruido, **kw)


def obtener_traza(sim):
    if hasattr(sim, "traza_arrays"):
        tr = sim.traza_arrays()
    else:
        tr = getattr(sim, "traza", None)
    if not tr:
        return None
    out = {k: np.asarray(v, dtype=float) for k, v in tr.items()}
    t = out.get("t")
    if t is not None and t.ndim == 1:
        out["t"] = t = np.repeat(t[:, None], sim.n_total if hasattr(sim, "n_total") else 1, 1)
    if t is not None and hasattr(sim, "t_fin"):
        fuera = t > (np.asarray(sim.t_fin)[None, :] + 1e-9)
        for k in out:
            if k != "t" and out[k].shape == t.shape:
                out[k] = np.where(fuera, np.nan, out[k])
    return out


def _texto_motivo(m):
    try:
        return F.MOTIVOS[int(m)]
    except (KeyError, IndexError, TypeError):
        return str(m)


def _seccion(pista, x):
    for x0, x1, rasgo, mat in getattr(pista, "secciones", ()):
        if x0 <= x < x1:
            return rasgo, mat
    return "?", "?"


def _correr(sim):
    while not sim.terminado:
        sim.correr(10_000)
    return sim


def tlc_min(traza, dt=C.DT_CONTROL):
    if traza is None or "lat" not in traza or len(traza["lat"]) < 2:
        return None
    lat = traza["lat"]
    vlat = np.gradient(lat, dt, axis=0)
    margen = np.maximum(C.ANCHO_CAMINO / 2 - np.abs(lat), 0.0)
    hacia = vlat * np.sign(lat)
    tlc = np.where(hacia > 1e-3, margen / np.maximum(hacia, 1e-3), np.inf)
    tlc = np.where(np.isnan(lat), np.inf, tlc)
    return np.min(tlc, axis=0)


def _nueva_pista(modo, nivel, semilla, red_vial):
    if modo == "ciudad":
        from calles import PistaCalle
        return PistaCalle(red_vial, nivel, semilla)
    return Pista(nivel, semilla)


def _filtro(sensores, semilla):
    if sensores is None or sensores == "ideal":
        return None
    if callable(sensores):
        return sensores(semilla)
    import sensores as S
    if isinstance(sensores, dict):
        return S.FiltroSensores(semilla=semilla, **sensores)
    return S.crear_filtro(sensores, semilla=semilla)


def _modulo_puntos():
    if not getattr(C, "PUNTOS_CONTROL", True):
        return None
    try:
        import puntos_control as PC
    except ImportError:
        return None
    return PC if hasattr(PC, "PuntosControl") else None


def _enganchar_puntos(PC, pista, sim, semilla):
    try:
        pc = PC.PuntosControl(pista, semilla=semilla)
        pc.enganchar(sim)
        return pc
    except Exception:
        return None


def _puntos_por_moto(PC, pc, sim):
    reg = np.asarray(pc.registrados, dtype=bool)
    total = reg.shape[1] if reg.ndim == 2 else 0
    pasados = reg.sum(1) if reg.ndim == 2 else np.zeros(len(sim.motivo), int)
    try:
        exitosa = np.asarray(pc.exitosas(sim) if hasattr(pc, "exitosas") else PC.exitosas(sim),
                             dtype=bool)
        if exitosa.shape != (len(sim.motivo),):
            raise ValueError
    except Exception:
        fal = np.asarray(getattr(pc, "fallados", np.zeros_like(reg)), dtype=bool)
        exitosa = (sim.motivo == F.META) & reg.all(1) & ~fal.any(1)
    return pasados, total, exitosa


def evaluar(pesos_o_controlador, modo="terreno", niveles=(1,), pistas=20, ruidos=5,
            sensores="ideal", max_reintentos=0, con_reintentos=True, registrar=True,
            red_vial=None, conf=0.95, guardar=True, dir_resultados=None, etiqueta=None,
            verbose=True, escudo=False):
    t0 = time.time()
    es_ctrl = callable(pesos_o_controlador)
    if not es_ctrl:
        w = np.asarray(pesos_o_controlador, dtype=float)
        lote = np.repeat(np.atleast_2d(w), ruidos, 0) if w.ndim == 1 else w
    if modo == "ciudad" and red_vial is None:
        red_vial = red_vial_local()
        if red_vial is None:
            raise RuntimeError("No hay red de calles descargada en disco; evaluación de ciudad omitida.")
    import stl as STL

    nombre_ctrl = (getattr(pesos_o_controlador, "__name__", type(pesos_o_controlador).__name__)
                   if es_ctrl else f"red_{hash_pesos(pesos_o_controlador)[:8]}")
    if escudo:
        nombre_ctrl += "+escudo"
    episodios, resumenes = [], {}
    PC = _modulo_puntos()
    for nivel in niveles:
        filas = []
        for j in range(pistas):
            sp = semilla_pista_prueba(nivel, j)
            pista = _nueva_pista(modo, nivel, sp, red_vial)
            pasadas = [("estricta", max_reintentos)] + ([("reintentos", None)] if con_reintentos else [])
            res = {}
            for nombre, mr in pasadas:
                kw = dict(max_reintentos=mr, ruido_por_moto=True, registrar=registrar and nombre == "estricta",
                          filtro_obs=_filtro(sensores, semilla_ruido_prueba(nivel, j) + 17))
                esc = None
                if escudo:
                    import escudo as ES
                    esc = ES.crear_escudo(pesos_o_controlador if es_ctrl else lote, escudo)
                    sim = crear_simulador(pista, None, semilla_ruido_prueba(nivel, j),
                                          controlador=esc, n=ruidos, **kw)
                elif es_ctrl:
                    sim = crear_simulador(pista, None, semilla_ruido_prueba(nivel, j),
                                          controlador=pesos_o_controlador, n=ruidos, **kw)
                else:
                    sim = crear_simulador(pista, lote, semilla_ruido_prueba(nivel, j), **kw)
                if nombre == "estricta":
                    pc = _enganchar_puntos(PC, pista, sim, None) if PC is not None else None
                res[nombre] = _correr(sim)
                if nombre == "estricta":
                    res_esc = esc.resumen() if esc is not None else None
            s = res["estricta"]
            traza = obtener_traza(s) if registrar else None
            rho = STL.evaluar_requisitos(traza, pista) if traza is not None else None
            tlc = tlc_min(traza)
            largo = pista.meta - pista.salida
            limpias = (s.motivo == F.META) & (s.reintentos == 0)
            dist = s.distancia_km() if hasattr(s, "distancia_km") else s.progreso / 1000.0
            r = res.get("reintentos")
            ptos = _puntos_por_moto(PC, pc, s) if pc is not None else None
            for k in range(len(s.motivo)):
                xf = float(s.pos_final[k, 0]) if hasattr(s, "pos_final") else s.progreso[k] + pista.salida
                rasgo, mat = _seccion(pista, xf) if not limpias[k] else ("", "")
                fila = {
                    "controlador": nombre_ctrl, "modo": modo, "nivel": nivel, "pista": j, "semilla_pista": sp, "ruido": k,
                    "motivo": int(s.motivo[k]), "motivo_texto": _texto_motivo(s.motivo[k]),
                    "llego": bool(r.motivo[k] == F.META) if r is not None else bool(s.motivo[k] == F.META),
                    "llego_limpio": bool(limpias[k]),
                    "llego_con_reintentos": bool(r.motivo[k] == F.META) if r is not None else None,
                    "reintentos_usados": int(r.reintentos[k]) if r is not None else None,
                    "progreso_m": float(s.progreso[k]), "largo_m": float(largo),
                    "distancia_km": float(dist[k]), "t_fin_s": float(s.t_fin[k]),
                    "vel_media_kmh": float(largo / max(s.t_fin[k], 1e-3) * 3.6) if limpias[k] else None,
                    "x_falla": None if limpias[k] else xf, "rasgo_falla": rasgo, "material_falla": mat,
                    "tlc_min_s": None if tlc is None or not np.isfinite(tlc[k]) else float(tlc[k]),
                }
                if ptos is not None:
                    fila["puntos"] = f"{int(ptos[0][k])}/{ptos[1]}"
                    fila["exitosa"] = bool(ptos[2][k])
                if res_esc:
                    fila["intervenciones"] = int(res_esc["intervenciones"][k])
                    fila["conmutaciones"] = int(res_esc["conmutaciones"][k])
                    fila["activaciones_cbf"] = int(res_esc["activaciones_cbf"][k])
                    fila["frac_respaldo"] = float(res_esc["frac_respaldo"][k])
                    fila["frac_cbf"] = float(res_esc["frac_cbf"][k])
                if rho is not None:
                    for req, d in rho.items():
                        fila[f"rho_{req}"] = float(d["rho"][k])
                filas.append(fila)
            if verbose:
                print(f"  nivel {nivel} pista {j + 1}/{pistas}: limpias {int(limpias.sum())}/{len(limpias)}"
                      + (f" · exitosas {int(ptos[2].sum())}/{len(limpias)}" if ptos is not None else ""),
                      flush=True)
        resumenes[nivel] = resumir(filas, conf)
        episodios += filas
        if verbose:
            _imprimir(nivel, resumenes[nivel])

    meta = {
        "fecha": _dt.datetime.now().isoformat(timespec="seconds"), "modo": modo,
        "niveles": list(niveles), "pistas": pistas, "ruidos": ruidos,
        "sensores": sensores if isinstance(sensores, (str, dict, type(None))) else "personalizado",
        "max_reintentos": max_reintentos, "conf": conf, "etiqueta": etiqueta,
        "escudo": escudo if isinstance(escudo, (bool, dict)) else True,
        "controlador": getattr(pesos_o_controlador, "__name__", type(pesos_o_controlador).__name__) if es_ctrl else None,
        "hash_pesos": None if es_ctrl else hash_pesos(pesos_o_controlador),
        "hash_config": hash_archivo(os.path.join(AQUI, "config.py")),
        "hash_fisica": hash_archivo(os.path.join(AQUI, "fisica.py")),
        "simulador": "contrato" if _contrato_disponible() else "adaptador",
        "semillas": "pista=2**31+1000*nivel+j; ruido=2**31+7919*(1000*nivel+j+1)",
        "zona": getattr(getattr(red_vial, "zona", None), "nombre", None),
        "segundos": round(time.time() - t0, 1),
    }
    out = {"meta": meta, "niveles": resumenes, "episodios": episodios}
    if guardar:
        out["archivos"] = guardar_resultados(out, dir_resultados)
    return out


def _resumen_escudo(filas, km, conf):
    if not filas or "intervenciones" not in filas[0]:
        return None
    k = sum(f["intervenciones"] for f in filas)
    lo, hi = garwood(k, km, conf)
    return {"intervenciones": k, "intervenciones_por_km": k / km if km > 0 else None,
            "ic": (lo, hi), "conmutaciones": sum(f["conmutaciones"] for f in filas),
            "activaciones_cbf": sum(f["activaciones_cbf"] for f in filas),
            "frac_respaldo_media": float(np.mean([f["frac_respaldo"] for f in filas])),
            "frac_cbf_media": float(np.mean([f["frac_cbf"] for f in filas]))}


def resumir(filas, conf=0.95):
    n = len(filas)
    k_l = sum(f["llego_limpio"] for f in filas)
    con_r = [f["llego_con_reintentos"] for f in filas if f["llego_con_reintentos"] is not None]
    km = sum(f["distancia_km"] for f in filas)
    fallas = n - k_l
    motivos = {}
    lugares = {}
    for f in filas:
        if not f["llego_limpio"]:
            motivos[f["motivo_texto"]] = motivos.get(f["motivo_texto"], 0) + 1
            clave = f"{f['rasgo_falla']}/{f['material_falla']}"
            lugares[clave] = lugares.get(clave, 0) + 1
    vel = [f["vel_media_kmh"] for f in filas if f["vel_media_kmh"] is not None]
    tlc = [f["tlc_min_s"] for f in filas if f["tlc_min_s"] is not None]
    lo, hi = clopper_pearson(k_l, n, conf)
    fl_lo, fl_hi = garwood(fallas, km, conf)
    stl = {}
    reqs = sorted({k[4:] for f in filas for k in f if k.startswith("rho_")})
    for req in reqs:
        v = np.array([f[f"rho_{req}"] for f in filas], dtype=float)
        v = v[np.isfinite(v)]
        if len(v):
            viol = int((v < 0).sum())
            stl[req] = {"violaciones": viol, "n": int(len(v)), "tasa": viol / len(v),
                        "ic": clopper_pearson(viol, len(v), conf),
                        "rho_min": float(v.min()), "rho_mediana": float(np.median(v))}
    p_falla_sup = clopper_pearson(fallas, n, conf)[1]
    ex = [f["exitosa"] for f in filas if f.get("exitosa") is not None]
    return {
        "n_episodios": n,
        "llegada_limpia": {"k": k_l, "tasa": k_l / n if n else 0.0, "ic": (lo, hi)},
        "exitosa": ({"k": int(sum(ex)), "n": len(ex), "tasa": sum(ex) / len(ex),
                     "ic": clopper_pearson(int(sum(ex)), len(ex), conf)} if ex else None),
        "llegada_con_reintentos": ({"k": int(sum(con_r)), "tasa": sum(con_r) / len(con_r),
                                    "ic": clopper_pearson(int(sum(con_r)), len(con_r), conf)}
                                   if con_r else None),
        "fallas": fallas, "km": km,
        "fallas_por_km": {"tasa": fallas / km if km > 0 else None, "ic": (fl_lo, fl_hi)},
        "taxonomia_motivo": dict(sorted(motivos.items(), key=lambda x: -x[1])),
        "taxonomia_lugar": dict(sorted(lugares.items(), key=lambda x: -x[1])),
        "vel_media_kmh": float(np.mean(vel)) if vel else None,
        "tlc_min_s": {"p05": float(np.percentile(tlc, 5)), "mediana": float(np.median(tlc))} if tlc else None,
        "stl": stl,
        "escudo": _resumen_escudo(filas, km, conf),
        "afirmacion": (f"Con {n} episodios y {fallas} fallas, P(falla por episodio) < {p_falla_sup:.3f} "
                       f"(cota superior {int(conf * 100)} %). Para afirmar < 1 % con 0 fallas harían "
                       f"falta {n_para_afirmar(0.01, conf)} episodios."),
    }


def _imprimir(nivel, r):
    ll = r["llegada_limpia"]
    t = (f"Nivel {nivel}: llegada limpia {ll['k']}/{r['n_episodios']} = {100 * ll['tasa']:.1f} % "
         f"[IC95 {100 * ll['ic'][0]:.1f}-{100 * ll['ic'][1]:.1f} %]")
    if r.get("exitosa"):
        e = r["exitosa"]
        t += (f" | exitosa (puntos de control) {100 * e['tasa']:.1f} % "
              f"[{100 * e['ic'][0]:.1f}-{100 * e['ic'][1]:.1f}]")
    if r["llegada_con_reintentos"]:
        c = r["llegada_con_reintentos"]
        t += f" | con reintentos {100 * c['tasa']:.1f} % [{100 * c['ic'][0]:.1f}-{100 * c['ic'][1]:.1f}]"
    fk = r["fallas_por_km"]
    if fk["tasa"] is not None:
        t += f" | fallas/km {fk['tasa']:.2f} [{fk['ic'][0]:.2f}-{fk['ic'][1]:.2f}]"
    print(t)
    if r["taxonomia_motivo"]:
        print("   fallas:", r["taxonomia_motivo"])
    if r.get("escudo"):
        e = r["escudo"]
        print(f"   escudo: {e['intervenciones']} intervenciones = {e['intervenciones_por_km']:.1f}/km "
              f"[{e['ic'][0]:.1f}-{e['ic'][1]:.1f}] (conmutaciones {e['conmutaciones']}, CBF "
              f"{e['activaciones_cbf']}); tiempo en respaldo {100 * e['frac_respaldo_media']:.1f} %")
    print("  ", r["afirmacion"])


def _json_seguro(o):
    if isinstance(o, dict):
        return {str(k): _json_seguro(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_json_seguro(v) for v in o]
    if isinstance(o, (np.floating, float)):
        return None if not np.isfinite(o) else float(o)
    if isinstance(o, np.integer):
        return int(o)
    if isinstance(o, np.bool_):
        return bool(o)
    return o


def guardar_resultados(out, dir_resultados=None, prefijo="evaluacion"):
    d = en_proyecto(dir_resultados) or DIR_RESULTADOS
    os.makedirs(d, exist_ok=True)
    sello = _dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    et = f"_{out['meta']['etiqueta']}" if out["meta"].get("etiqueta") else ""
    base = os.path.join(d, f"{prefijo}_{out['meta']['modo']}{et}_{sello}")
    with open(base + ".json", "w", encoding="utf-8") as f:
        json.dump(_json_seguro({k: v for k, v in out.items() if k != "archivos"}), f,
                  ensure_ascii=False, indent=1)
    if out["episodios"]:
        campos = list(dict.fromkeys(k for e in out["episodios"] for k in e))
        with open(base + "_episodios.csv", "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=campos)
            w.writeheader()
            w.writerows(out["episodios"])
    return {"json": base + ".json", "csv": base + "_episodios.csv"}


def main(argv=None):
    ap = argparse.ArgumentParser(description="MT-Bench: evaluación reservada con IC")
    ap.add_argument("--modo", choices=("terreno", "ciudad"), default="terreno")
    ap.add_argument("--niveles", type=int, nargs="+", default=[1])
    ap.add_argument("--pistas", type=int, default=20)
    ap.add_argument("--ruidos", type=int, default=5)
    ap.add_argument("--sensores", default="ideal", help="ideal | realista")
    ap.add_argument("--max-reintentos", type=int, default=0)
    ap.add_argument("--sin-reintentos", action="store_true", help="omite la 2.ª pasada con reintentos")
    ap.add_argument("--pesos", default=None, help="archivo JSON (por defecto mejor_moto*.json)")
    ap.add_argument("--etiqueta", default=None)
    ap.add_argument("--escudo", action="store_true", help="envuelve con escudo Simplex+CBF")
    ap.add_argument("--dir", default=None, help="carpeta de resultados")
    a = ap.parse_args(argv)
    pesos, info = cargar_pesos(a.modo, a.pesos)
    print(f"Evaluando {a.pesos or 'mejor_moto'} (gen {info.get('generacion')}, nivel de entrenamiento "
          f"{info.get('nivel')}) en pistas RESERVADAS, sin rebobinado…")
    out = evaluar(pesos, a.modo, tuple(a.niveles), a.pistas, a.ruidos, a.sensores,
                  a.max_reintentos, not a.sin_reintentos, etiqueta=a.etiqueta, dir_resultados=a.dir,
                  escudo=a.escudo)
    print("Resultados:", out.get("archivos"))
    return out


if __name__ == "__main__":
    main(sys.argv[1:])
