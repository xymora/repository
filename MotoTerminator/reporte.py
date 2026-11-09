"""Figuras del paper y del deck de MT-Bench a partir de resultados/.

Uso:
    python reporte.py                       # lee resultados/ y escribe docs/figuras/
    python reporte.py --resultados X --salida Y --bootstrap 10000

Lee en forma TOLERANTE (columnas o claves faltantes = se omite esa figura o ese dato) los
archivos que escriben experimentos.py, evaluacion.py y sensores.py:

  * curvas de aprendizaje: resultados/<lote>/semilla_<s>/curva.json (lista de dicts con
    generacion, mejor, promedio, [llegadas_limpias_pct]) o historial*.csv de cada semilla;
  * episodios de prueba: cualquier *episodios*.csv con columnas como
    controlador|condicion, nivel, limpia|llego_limpio, llego|llego_con_reintentos,
    motivo|motivo_texto, distancia_km;
  * fragilidad: un JSON con clave "fragilidad" o con la forma {eje: [{valor, tasa, ic, n}]}.

Genera (sólo las que tengan datos):
  docs/figuras/curvas_aprendizaje.png  media ± IC95 bootstrap entre semillas
  docs/figuras/tasa_limpia.png         llegada limpia por nivel y controlador, IC Clopper-Pearson
  docs/figuras/histograma_fallas.png   motivos de falla por controlador
  docs/figuras/fragilidad.png          tasa limpia contra la magnitud de cada perturbación
  docs/figuras/marcadores.json         valores calculados para los {{RESULTADO:...}} de docs/

No inventa nada: si no hay datos para una figura, avisa y la omite.
"""
import argparse
import csv
import glob
import json
import os
import re
import sys
from collections import Counter, defaultdict

import numpy as np

AQUI = os.path.dirname(os.path.abspath(__file__))


def _en_proyecto(ruta):
    if not ruta:
        return ruta
    ruta = os.path.expanduser(str(ruta))
    return ruta if os.path.isabs(ruta) else os.path.join(AQUI, ruta)


COLORES = {"ga": "#2a78d6", "pd": "#eb6834", "aleatorio": "#1baf7a"}
EXTRA = ["#eda100", "#e87ba4", "#008300", "#4a3aa7", "#e34948"]
TINTA, TINTA2, REJILLA, FONDO = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"
NOMBRE_CTRL = {"ga": "Política GA (red)", "pd": "Baseline PD", "aleatorio": "Aleatorio"}

MOTIVOS_RESPALDO = ("en carrera", "llegó a la meta", "se volteó", "se cayó de lado",
                    "se salió del camino", "chocó el chasís", "se atascó", "se acabó el tiempo")


def _bool(v):
    if isinstance(v, bool):
        return v
    if v is None:
        return None
    s = str(v).strip().lower()
    if s in ("true", "1", "1.0", "si", "sí", "yes"):
        return True
    if s in ("false", "0", "0.0", "no"):
        return False
    return None


def _num(v):
    try:
        x = float(v)
        return x if np.isfinite(x) else None
    except (TypeError, ValueError):
        return None


def _primero(d, claves):
    for k in claves:
        if k in d and d[k] not in (None, ""):
            return d[k]
    return None


def _leer_csv(ruta):
    try:
        with open(ruta, encoding="utf-8-sig", newline="") as f:
            return list(csv.DictReader(f))
    except (OSError, csv.Error, UnicodeDecodeError) as e:
        print(f"  aviso: no se pudo leer {ruta}: {e}")
        return []


def _leer_json(ruta):
    try:
        with open(ruta, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError, UnicodeDecodeError) as e:
        print(f"  aviso: no se pudo leer {ruta}: {e}")
        return None


def _motivos():
    try:
        sys.path.insert(0, AQUI)
        import fisica
        m = fisica.MOTIVOS
        return dict(m) if isinstance(m, dict) else dict(enumerate(m))
    except Exception:
        return dict(enumerate(MOTIVOS_RESPALDO))


def clave_ctrl(nombre):
    s = str(nombre or "").strip().lower()
    if s in ("red", "ga", "base", "neuro", "politica", "mejor_moto", "campeona") or "red" == s[:3]:
        return "ga"
    if "pd" in s or "pid" in s or "clasic" in s or "heur" in s:
        return "pd"
    if "aleat" in s or "random" in s:
        return "aleatorio"
    return s or "ga"


def clopper_pearson(k, n, conf=0.95):
    if n <= 0:
        return (float("nan"), float("nan"))
    a = 1 - conf
    try:
        from scipy.stats import beta
        lo = 0.0 if k == 0 else float(beta.ppf(a / 2, k, n - k + 1))
        hi = 1.0 if k == n else float(beta.ppf(1 - a / 2, k + 1, n - k))
        return lo, hi
    except ImportError:
        z = 1.959963984540054
        p = k / n
        c = (p + z * z / (2 * n)) / (1 + z * z / n)
        h = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
        return max(0.0, c - h), min(1.0, c + h)


def garwood(k, expo, conf=0.95):
    if expo <= 0:
        return (float("nan"), float("nan"))
    a = 1 - conf
    try:
        from scipy.stats import chi2
        lo = 0.0 if k == 0 else chi2.ppf(a / 2, 2 * k) / 2
        hi = chi2.ppf(1 - a / 2, 2 * k + 2) / 2
        return float(lo / expo), float(hi / expo)
    except ImportError:
        return (float("nan"), float("nan"))


def bootstrap_media(matriz, b=10000, conf=0.95, rng=None):
    rng = rng or np.random.default_rng(0)
    m = np.asarray(matriz, float)
    s = m.shape[0]
    media = np.nanmean(m, axis=0)
    if s < 2:
        return media, media * np.nan, media * np.nan
    idx = rng.integers(0, s, size=(b, s))
    with np.errstate(all="ignore"):
        boot = np.nanmean(m[idx], axis=1)
    a = (1 - conf) / 2
    return media, np.nanpercentile(boot, 100 * a, axis=0), np.nanpercentile(boot, 100 * (1 - a), axis=0)


def recolectar_curvas(raiz):
    curvas = defaultdict(dict)
    for ruta in glob.glob(os.path.join(raiz, "**", "curva.json"), recursive=True):
        datos = _leer_json(ruta)
        if not isinstance(datos, list):
            continue
        d_sem = os.path.dirname(ruta)
        sem = os.path.basename(d_sem)
        cond = re.sub(r"^\d{8}_\d{6}_?", "", os.path.basename(os.path.dirname(d_sem))) or "base"
        filas = []
        for i, r in enumerate(datos):
            if not isinstance(r, dict):
                continue
            filas.append((_num(r.get("generacion")) or i + 1, _num(r.get("mejor")),
                          _num(r.get("promedio")), _num(r.get("llegadas_limpias_pct"))))
        if filas:
            curvas[cond][sem] = filas
    for ruta in glob.glob(os.path.join(raiz, "**", "historial*.csv"), recursive=True):
        d_sem = os.path.dirname(ruta)
        sem = os.path.basename(d_sem)
        cond = re.sub(r"^\d{8}_\d{6}_?", "", os.path.basename(os.path.dirname(d_sem))) or "base"
        if sem in curvas.get(cond, {}):
            continue
        filas = [(_num(r.get("generacion")), _num(r.get("mejor")), _num(r.get("promedio")),
                  _num(r.get("llegadas_limpias_pct"))) for r in _leer_csv(ruta)]
        filas = [f for f in filas if f[0] is not None]
        if filas:
            curvas[cond][sem] = filas
    return curvas


def recolectar_episodios(raiz, motivos):
    eps = []
    for ruta in glob.glob(os.path.join(raiz, "**", "*episodios*.csv"), recursive=True):
        etiqueta = None
        j = re.sub(r"_episodios\.csv$", ".json", ruta)
        if j != ruta and os.path.exists(j):
            meta = (_leer_json(j) or {}).get("meta", {})
            etiqueta = meta.get("etiqueta") or meta.get("controlador")
        for r in _leer_csv(ruta):
            limpia = _bool(_primero(r, ("limpia", "llego_limpio", "llegada_limpia")))
            if limpia is None:
                continue
            nivel = _num(r.get("nivel"))
            m = _primero(r, ("motivo_texto",))
            if m is None:
                code = _num(r.get("motivo"))
                m = motivos.get(int(code), str(code)) if code is not None else None
            eps.append({
                "ctrl": clave_ctrl(_primero(r, ("controlador", "condicion")) or etiqueta or "red"),
                "nivel": int(nivel) if nivel is not None else None,
                "limpia": limpia,
                "con_reint": _bool(_primero(r, ("llego_con_reintentos", "llego"))),
                "motivo": m,
                "km": _num(_primero(r, ("distancia_km",))),
                "origen": os.path.relpath(ruta, raiz),
            })
    return eps


def recolectar_fragilidad(raiz):
    out = {}
    for ruta in sorted(glob.glob(os.path.join(raiz, "**", "*.json"), recursive=True)):
        d = _leer_json(ruta)
        if not isinstance(d, dict):
            continue
        d = d.get("fragilidad", d)
        if not isinstance(d, dict):
            continue
        for eje, filas in d.items():
            if not (isinstance(filas, list) and filas and isinstance(filas[0], dict)
                    and "valor" in filas[0] and "tasa" in filas[0]):
                continue
            pts = []
            for f in filas:
                v, t = _num(f.get("valor")), _num(f.get("tasa"))
                ic = f.get("ic") or [None, None]
                if v is None or t is None:
                    continue
                pts.append((v, t, _num(ic[0]), _num(ic[1]), _num(f.get("n"))))
            if pts:
                out[eje] = sorted(pts)
    return out


def _estilo(plt):
    plt.rcParams.update({
        "figure.facecolor": FONDO, "axes.facecolor": FONDO, "savefig.facecolor": FONDO,
        "axes.edgecolor": REJILLA, "axes.labelcolor": TINTA2, "xtick.color": TINTA2,
        "ytick.color": TINTA2, "text.color": TINTA, "axes.grid": True, "grid.color": REJILLA,
        "grid.linewidth": 0.8, "axes.spines.top": False, "axes.spines.right": False,
        "font.size": 10, "axes.titlesize": 11, "axes.titleweight": "bold", "lines.linewidth": 2,
        "legend.frameon": False,
    })


def orden_ctrls(ctrls):
    fijos = list(COLORES)
    return sorted(set(ctrls), key=lambda c: (fijos.index(c) if c in fijos else len(fijos), c))


def _color(ctrl, orden):
    return COLORES.get(ctrl) or EXTRA[orden.index(ctrl) % len(EXTRA)]


def fig_curvas(plt, curvas, salida, b, marc):
    if not curvas:
        print("  curvas de aprendizaje: sin datos (curva.json / historial.csv) -> omitida")
        return
    paneles = [("mejor", 1, "Aptitud del mejor"), ("promedio", 2, "Aptitud promedio")]
    if any(f[3] is not None for c in curvas.values() for s in c.values() for f in s):
        paneles.append(("limpias", 3, "Llegadas limpias (%)"))
    fig, ejes = plt.subplots(1, len(paneles), figsize=(4.2 * len(paneles), 3.4), squeeze=False)
    conds = sorted(curvas)
    for k, (nombre, col, titulo) in enumerate(paneles):
        ax = ejes[0, k]
        for i, cond in enumerate(conds):
            sems = curvas[cond]
            T = int(max(max(f[0] for f in s) for s in sems.values()))
            M = np.full((len(sems), T), np.nan)
            for r, s in enumerate(sems.values()):
                for f in s:
                    if f[col] is not None and 1 <= f[0] <= T:
                        M[r, int(f[0]) - 1] = f[col]
            media, lo, hi = bootstrap_media(M, b)
            g = np.arange(1, T + 1)
            c = EXTRA[i % len(EXTRA)] if len(conds) > 1 else COLORES["ga"]
            et = f"{cond} (n={len(sems)} semillas)"
            ax.plot(g, media, color=c, label=et)
            if np.isfinite(lo).any():
                ax.fill_between(g, lo, hi, color=c, alpha=0.18, linewidth=0)
            if nombre == "mejor" and i == 0:
                marc["n_semillas"] = len(sems)
                marc["n_generaciones"] = T
        ax.set_title(titulo)
        ax.set_xlabel("Generación")
    ejes[0, 0].legend(loc="lower right", fontsize=8)
    fig.suptitle("Curvas de aprendizaje: media ± IC 95 % bootstrap entre semillas", fontsize=11)
    fig.tight_layout()
    fig.savefig(os.path.join(salida, "curvas_aprendizaje.png"), dpi=200)
    plt.close(fig)
    print("  curvas_aprendizaje.png")


def tabla_tasas(eps):
    g = defaultdict(list)
    for e in eps:
        if e["nivel"] is not None:
            g[(e["ctrl"], e["nivel"])].append(e)
    out = {}
    for key, sub in g.items():
        n, k = len(sub), sum(e["limpia"] for e in sub)
        cr = [e["con_reint"] for e in sub if e["con_reint"] is not None]
        km = sum(e["km"] for e in sub if e["km"] is not None)
        lo, hi = clopper_pearson(k, n)
        out[key] = dict(k=k, n=n, tasa=k / n, lo=lo, hi=hi, k_r=sum(cr), n_r=len(cr),
                        fallas=n - k, km=km)
    return out


def fig_tasas(plt, tabla, salida, marc):
    if not tabla:
        print("  tasa limpia: sin episodios -> omitida")
        return
    ctrls = orden_ctrls(c for c, _ in tabla)
    niveles = sorted({nv for _, nv in tabla})
    fig, ax = plt.subplots(figsize=(max(6.0, 1.6 + 0.9 * len(niveles) * len(ctrls)), 4.0))
    ancho = 0.8 / len(ctrls)
    for i, c in enumerate(ctrls):
        xs, ys, el, eh = [], [], [], []
        for j, nv in enumerate(niveles):
            t = tabla.get((c, nv))
            if not t:
                continue
            xs.append(j + (i - (len(ctrls) - 1) / 2) * ancho)
            ys.append(100 * t["tasa"])
            el.append(100 * (t["tasa"] - t["lo"]))
            eh.append(100 * (t["hi"] - t["tasa"]))
            ax.annotate(f"n={t['n']}", (xs[-1], 100 * t["hi"] + 1.5), ha="center", va="bottom",
                        fontsize=7, color=TINTA2)
        ax.bar(xs, ys, width=ancho * 0.92, color=_color(c, ctrls), label=NOMBRE_CTRL.get(c, c),
               edgecolor=FONDO, linewidth=1.5)
        ax.errorbar(xs, ys, yerr=[el, eh], fmt="none", ecolor=TINTA, elinewidth=1, capsize=3)
    ax.set_xticks(range(len(niveles)))
    ax.set_xticklabels([f"Nivel {nv}" for nv in niveles])
    ax.set_ylim(0, 110)
    ax.set_ylabel("Llegada limpia (%)")
    ax.set_title("Llegada limpia en pistas reservadas (sin rebobinado)\n"
                 "barras de error: IC 95 % Clopper-Pearson", fontsize=10)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.1), ncol=len(ctrls), fontsize=8)
    ax.grid(axis="x", visible=False)
    fig.tight_layout()
    fig.savefig(os.path.join(salida, "tasa_limpia.png"), dpi=200)
    plt.close(fig)
    print("  tasa_limpia.png")
    for (c, nv), t in tabla.items():
        marc[f"tasa_limpia_nivel{nv}_{c}"] = f"{100 * t['tasa']:.1f} %"
        marc[f"ic95_nivel{nv}_{c}"] = f"{100 * t['lo']:.1f}–{100 * t['hi']:.1f} %"
        marc[f"n_episodios_nivel{nv}" if c == "ga" else f"n_episodios_nivel{nv}_{c}"] = t["n"]
        if t["n_r"]:
            marc[f"tasa_reintentos_nivel{nv}_{c}"] = f"{100 * t['k_r'] / t['n_r']:.1f} %"
            if c == "ga":
                marc[f"brecha_reintentos_nivel{nv}"] = \
                    f"{100 * (t['k_r'] / t['n_r'] - t['tasa']):.1f} puntos porcentuales"
        if t["km"] > 0:
            lo, hi = garwood(t["fallas"], t["km"])
            marc[f"fallas_km_nivel{nv}_{c}"] = f"{t['fallas'] / t['km']:.2f}"
            marc[f"ic95_fallas_km_nivel{nv}_{c}"] = f"{lo:.2f}–{hi:.2f}"


def fig_fallas(plt, eps, salida, marc):
    fallas = [e for e in eps if not e["limpia"] and e["motivo"]]
    if not fallas:
        print("  histograma de fallas: sin fallas registradas -> omitido")
        return
    ctrls = orden_ctrls(e["ctrl"] for e in fallas)
    total = Counter(e["motivo"] for e in fallas)
    motivos = [m for m, _ in total.most_common()]
    fig, ax = plt.subplots(figsize=(6.4, 0.5 + 0.45 * len(motivos) * max(1, len(ctrls)) / 1.5))
    alto = 0.8 / len(ctrls)
    for i, c in enumerate(ctrls):
        cnt = Counter(e["motivo"] for e in fallas if e["ctrl"] == c)
        n_c = sum(1 for e in eps if e["ctrl"] == c)
        ys = [j + (i - (len(ctrls) - 1) / 2) * alto for j in range(len(motivos))]
        vals = [100 * cnt.get(m, 0) / max(n_c, 1) for m in motivos]
        ax.barh(ys, vals, height=alto * 0.92, color=_color(c, ctrls), label=NOMBRE_CTRL.get(c, c),
                edgecolor=FONDO, linewidth=1.5)
    ax.set_yticks(range(len(motivos)))
    ax.set_yticklabels(motivos)
    ax.invert_yaxis()
    ax.set_xlabel("% de los episodios de ese controlador")
    ax.set_title("Motivo de falla (pistas reservadas, sin rebobinado)")
    ax.legend(loc="lower right", fontsize=8)
    ax.grid(axis="y", visible=False)
    fig.tight_layout()
    fig.savefig(os.path.join(salida, "histograma_fallas.png"), dpi=200)
    plt.close(fig)
    print("  histograma_fallas.png")
    ga = Counter(e["motivo"] for e in fallas if e["ctrl"] == "ga") or total
    m, k = ga.most_common(1)[0]
    marc["modo_falla_dominante"] = f"{m} ({k} de {sum(ga.values())} fallas)"


def fig_fragilidad(plt, frag, salida, marc):
    if not frag:
        print("  fragilidad: sin datos -> omitida")
        return
    ejes_n = list(frag)
    fig, ejes = plt.subplots(1, len(ejes_n), figsize=(3.2 * len(ejes_n), 3.2), squeeze=False,
                             sharey=True)
    for k, eje in enumerate(ejes_n):
        ax = ejes[0, k]
        pts = frag[eje]
        x = np.array([p[0] for p in pts])
        y = 100 * np.array([p[1] for p in pts])
        lo = np.array([np.nan if p[2] is None else 100 * p[2] for p in pts])
        hi = np.array([np.nan if p[3] is None else 100 * p[3] for p in pts])
        ax.plot(x, y, color=COLORES["ga"], marker="o", markersize=5)
        if np.isfinite(lo).any():
            ax.fill_between(x, lo, hi, color=COLORES["ga"], alpha=0.18, linewidth=0)
        ax.set_title(eje.replace("_", " "))
        ax.set_xlabel("magnitud")
        ax.set_ylim(0, 105)
        bajo = [p for p in pts if p[1] <= 0.5]
        if bajo:
            marc.setdefault("fragilidad_umbral_50", f"{bajo[0][0]:g}")
            marc.setdefault("fragilidad_perturbacion", eje)
    ejes[0, 0].set_ylabel("Llegada limpia (%)")
    fig.suptitle("Curvas de fragilidad (una perturbación a la vez) · banda = IC 95 %", fontsize=11)
    fig.tight_layout()
    fig.savefig(os.path.join(salida, "fragilidad.png"), dpi=200)
    plt.close(fig)
    print("  fragilidad.png")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--resultados", default=os.path.join(AQUI, "resultados"))
    ap.add_argument("--salida", default=os.path.join(AQUI, "docs", "figuras"))
    ap.add_argument("--bootstrap", type=int, default=10000)
    a = ap.parse_args(argv)
    a.resultados, a.salida = _en_proyecto(a.resultados), _en_proyecto(a.salida)
    if not os.path.isdir(a.resultados):
        print(f"No existe {a.resultados}: primero corre experimentos.py / evaluacion.py.")
        return 1
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("Falta matplotlib (pip install matplotlib).")
        return 1
    os.makedirs(a.salida, exist_ok=True)
    _estilo(plt)
    marc = {}
    print(f"Leyendo {a.resultados}")
    curvas = recolectar_curvas(a.resultados)
    eps = recolectar_episodios(a.resultados, _motivos())
    frag = recolectar_fragilidad(a.resultados)
    print(f"  {sum(len(v) for v in curvas.values())} curvas, {len(eps)} episodios, "
          f"{len(frag)} ejes de fragilidad")
    fig_curvas(plt, curvas, a.salida, a.bootstrap, marc)
    fig_tasas(plt, tabla_tasas(eps), a.salida, marc)
    fig_fallas(plt, eps, a.salida, marc)
    fig_fragilidad(plt, frag, a.salida, marc)
    marc["_fuentes"] = sorted({e["origen"] for e in eps})
    with open(os.path.join(a.salida, "marcadores.json"), "w", encoding="utf-8") as f:
        json.dump(marc, f, indent=2, ensure_ascii=False)
    print(f"  marcadores.json ({len(marc) - 1} valores) -> {a.salida}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
