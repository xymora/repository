import inspect
import json
import math
import os
import pickle
import subprocess
import sys
import tempfile
import textwrap
import unittest

import numpy as np

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
if RAIZ not in sys.path:
    sys.path.insert(0, RAIZ)

import calles
import config as C
from terreno import DX, M, MU

RESPALDO = os.path.join(os.path.dirname(RAIZ), "MotoTerminator_respaldo_v11_2026-10-09")
ZONA20 = ("Zona 20.1217, -98.7358", (20.121666666666666, -98.73583333333333))
LIM_KAPPA_ASFALTO = min(C.A_LAT_MAX, 0.85 * MU[M["asfalto"]] * C.G) / C.V_DISENO ** 2
_CACHE = {}


def _saltar(msg):
    raise unittest.SkipTest(msg)


def _silencio(*a, **k):
    pass


def red_mty():
    if "mty" not in _CACHE:
        _CACHE["mty"] = calles.RedVial(calles.zona_para("Monterrey · Centro"), avisar=_silencio)
    return _CACHE["mty"]


def red_z20():
    if "z20" not in _CACHE:
        _CACHE["z20"] = calles.RedVial(calles.Zona(*ZONA20), avisar=_silencio)
    return _CACHE["z20"]


def redes():
    return (("Monterrey", red_mty()), ("Zona20", red_z20()))


def requiere_circuito():
    if not hasattr(calles.RedVial, "ruta_circuito"):
        _saltar("aún no existe RedVial.ruta_circuito")
    if "circuito" not in inspect.signature(calles.PistaCalle.__init__).parameters:
        _saltar("PistaCalle aún no acepta circuito=")


def requiere_circuito_azar():
    requiere_circuito()
    if not hasattr(calles.RedVial, "circuito"):
        _saltar("aún no existe RedVial.circuito")


class _Config:

    def __init__(self, **kw):
        self.kw, self.antes = kw, {}

    def __enter__(self):
        for k, v in self.kw.items():
            self.antes[k] = getattr(C, k, _Config)
            setattr(C, k, v)

    def __exit__(self, *exc):
        for k, v in self.antes.items():
            if v is _Config:
                delattr(C, k)
            else:
                setattr(C, k, v)


def pares_ab(red, n, semilla, dmin=250.0, dmax=600.0):
    rng = np.random.default_rng(semilla)
    out = []
    for _ in range(400):
        a = red.pos[red.inicios[rng.integers(len(red.inicios))]]
        b = red.pos[red.inicios[rng.integers(len(red.inicios))]]
        if dmin <= math.dist(a, b) <= dmax:
            out.append((a, b))
            if len(out) == n:
                break
    return out


def largo_poli(pts):
    P = np.asarray(pts, float)
    return float(np.hypot(*np.diff(P, axis=0).T).sum())


def punto_a(pts, x):
    P = np.asarray(pts, float)
    s = np.r_[0.0, np.cumsum(np.hypot(*np.diff(P, axis=0).T))]
    return float(np.interp(x, s, P[:, 0])), float(np.interp(x, s, P[:, 1]))


def max_giro_en(pts, ventana=20.0):
    P = np.asarray(pts, float)
    d = np.diff(P, axis=0)
    seg = np.hypot(d[:, 0], d[:, 1])
    ok = seg > 1e-6
    d, seg = d[ok], seg[ok]
    if len(d) < 2:
        return 0.0, 0.0
    rumbo = np.arctan2(d[:, 1], d[:, 0])
    giro = (np.diff(rumbo) + math.pi) % (2 * math.pi) - math.pi
    giro[np.isclose(np.abs(giro), math.pi)] = math.pi
    acum = np.r_[0.0, np.cumsum(giro)]
    s_vert = np.r_[0.0, np.cumsum(seg)][1:]
    s_vert = s_vert[: len(acum) - 1]
    acum = acum[1:]
    peor, donde = 0.0, 0.0
    j = 0
    for i in range(len(s_vert)):
        j = max(j, i)
        while j + 1 < len(s_vert) and s_vert[j + 1] - s_vert[i] < ventana:
            j += 1
        base = acum[i - 1] if i > 0 else 0.0
        tramo = acum[i:j + 1] - base
        m = float(np.abs(tramo).max())
        if m > peor:
            peor, donde = m, float(s_vert[i])
    return math.degrees(peor), donde


def aristas(pts, desde=0.0, hasta=1e18):
    P = np.asarray(pts, float)
    s = np.r_[0.0, np.cumsum(np.hypot(*np.diff(P, axis=0).T))]
    out = set()
    for i in range(len(P) - 1):
        mid = 0.5 * (s[i] + s[i + 1])
        if desde <= mid <= hasta and s[i + 1] - s[i] > 1e-6:
            a = (round(P[i, 0], 1), round(P[i, 1], 1))
            b = (round(P[i + 1, 0], 1), round(P[i + 1, 1], 1))
            out.add((min(a, b), max(a, b)))
    return out


def largo_aristas(conj):
    return sum(math.dist(a, b) for a, b in conj)


def fraccion_compartida(pts, x_b):
    ida = aristas(pts, 0.0, x_b)
    vuelta = aristas(pts, x_b, 1e18)
    tot = largo_aristas(vuelta)
    return largo_aristas(vuelta & ida) / tot if tot else 1.0


def mapa_zona(pista, x):
    i = int(pista.indice(x))
    return float(pista.mapa_x[i]), float(-pista.mapa_y[i])


def limite_kappa(pista):
    mu = np.asarray(pista.mu, float)
    return np.minimum(C.A_LAT_MAX, 0.85 * mu * C.G) / C.V_DISENO ** 2


def revisar_kappa(pista, etiqueta=""):
    exceso = np.abs(pista.kappa) - limite_kappa(pista)
    i = int(np.argmax(exceso))
    assert exceso[i] <= 1e-9, (f"{etiqueta}: |kappa|={abs(pista.kappa[i]):.4f} 1/m en x={pista.xs[i]:.1f} m "
                               f"supera el agarre ({limite_kappa(pista)[i]:.4f} 1/m a V_DISENO)")


def circuitos_de_prueba(vuelta, n_por_red=3, semilla=11):
    clave = ("circ", vuelta, n_por_red, semilla)
    if clave in _CACHE:
        return _CACHE[clave]
    out, errores = [], []
    for nombre, red in redes():
        for k, (a, b) in enumerate(pares_ab(red, n_por_red * 3, semilla)):
            try:
                r = red.ruta_circuito(a, b, vuelta=vuelta)
            except RuntimeError as e:
                errores.append(f"{nombre}#{k}: {e}")
                continue
            out.append((f"{nombre}#{k}", red, a, b, r))
            if sum(1 for o in out if o[1] is red) >= n_por_red:
                break
    assert len(out) >= n_por_red, f"ruta_circuito('{vuelta}') falló en casi todos los pares: {errores[:5]}"
    _CACHE[clave] = out
    return out


def test_contrato_api():
    requiere_circuito_azar()
    assert getattr(C, "CALLES_CIRCUITO", None) == "no", "config.CALLES_CIRCUITO debe valer 'no' por omisión"
    params = inspect.signature(calles.PistaCalle.__init__).parameters
    assert list(params)[:7] == ["self", "red", "nivel", "semilla", "ruta", "superficie", "circuito"]
    for p in ("ruta", "superficie", "circuito"):
        assert params[p].default is None
    sig = inspect.signature(calles.RedVial.ruta_circuito).parameters
    assert sig["vuelta"].default == "otra"
    assert list(inspect.signature(calles.RedVial.circuito).parameters)[:5] == \
        ["self", "rng", "largo_min", "largo_max", "vuelta"]
    red = red_mty()
    _, _, a, b, (pts, nombres, extra) = circuitos_de_prueba("otra", 1)[0]
    assert len(nombres) == len(pts) - 1
    for k in ("x_b", "vuelta", "largo_ida", "largo_vuelta"):
        assert k in extra, f"falta extra[{k!r}]"
    assert isinstance(extra["vuelta"], str) and extra["vuelta"]
    p = calles.PistaCalle(red, 2, 0)
    assert p.circuito == "no" and p.x_b is None and p.extra is None


_SCRIPT_RESPALDO = textwrap.dedent(r"""
    import pickle, sys
    import numpy as np
    sys.path.insert(0, {raiz!r})
    import calles
    casos, salida = pickle.load(open({entrada!r}, "rb")), {{}}
    red = calles.RedVial(calles.zona_para("Monterrey · Centro"), avisar=lambda *a, **k: None)
    rutas = {{}}
    for clave, (nivel, semilla, sup, ab) in casos.items():
        ruta = red.ruta_entre(*ab) if ab is not None else None
        p = calles.PistaCalle(red, nivel, semilla, ruta=ruta, superficie=sup)
        salida[clave] = {{k: getattr(p, k) for k in {campos!r}}}
        rutas[clave] = ruta
    pickle.dump((salida, rutas), open({salida!r}, "wb"))
""")
CAMPOS = ("xs", "hs", "mat", "kappa", "kmax", "rumbo", "mapa_x", "mapa_y", "mu", "rr", "mu_min", "rugo",
          "secciones", "calles", "longitud", "salida", "meta", "tiempo_max", "superficie")


def _casos_bit_a_bit():
    casos = {}
    for sup in ("pavimento", "variado"):
        for nivel, semilla in ((1, 0), (2, 5), (3, 7), (5, 11), (8, 123), (6, 2024), (4, 13), (7, 77),
                               (2, 300), (3, 301), (5, 302), (1, 303)):
            casos[f"{sup}-{nivel}-{semilla}"] = (nivel, semilla, sup, None)
    red = red_mty()
    for k, (a, b) in enumerate(pares_ab(red, 4, 99)):
        for sup in ("pavimento", "variado"):
            casos[f"fija{k}-{sup}"] = (4, 31 + k, sup, (a, b))
    return casos


def respaldo_pistas():
    if "respaldo" in _CACHE:
        return _CACHE["respaldo"]
    if not os.path.isfile(os.path.join(RESPALDO, "calles.py")):
        _saltar(f"no está el respaldo {RESPALDO}")
    casos = _casos_bit_a_bit()
    with tempfile.TemporaryDirectory() as tmp:
        ent, sal = os.path.join(tmp, "casos.pkl"), os.path.join(tmp, "salida.pkl")
        with open(ent, "wb") as f:
            pickle.dump(casos, f)
        script = _SCRIPT_RESPALDO.format(raiz=RESPALDO, entrada=ent, salida=sal, campos=CAMPOS)
        env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONDONTWRITEBYTECODE="1")
        r = subprocess.run([sys.executable, "-c", script], cwd=RESPALDO, env=env, capture_output=True,
                           text=True, encoding="utf-8", errors="replace", timeout=600)
        assert r.returncode == 0, r.stderr[-3000:]
        with open(sal, "rb") as f:
            _CACHE["respaldo"] = (casos,) + pickle.load(f)
    return _CACHE["respaldo"]


def _igual(a, b):
    if isinstance(a, np.ndarray) or isinstance(b, np.ndarray):
        a, b = np.asarray(a), np.asarray(b)
        return a.shape == b.shape and a.dtype == b.dtype and a.tobytes() == b.tobytes()
    if isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)):
        return len(a) == len(b) and all(_igual(x, y) for x, y in zip(a, b))
    if isinstance(a, float) and isinstance(b, float):
        return a == b or (math.isnan(a) and math.isnan(b))
    return a == b


def valida_en_v11(clave):
    casos, viejas, rutas = respaldo_pistas()
    if float(np.abs(viejas[clave]["kappa"]).max()) > LIM_KAPPA_ASFALTO + 1e-9:
        return False
    ruta = rutas[clave]
    return ruta is None or max_giro_en(ruta[0], 20.0)[0] <= 150.0


def comparar_con_respaldo(superficies, campos, circuito_kw):
    casos, viejas, rutas = respaldo_pistas()
    red = red_mty()
    difs, n_val, n_inv = [], 0, 0
    for clave, (nivel, semilla, sup, ab) in casos.items():
        if sup not in superficies:
            continue
        if valida_en_v11(clave):
            n_val += 1
            ruta = rutas[clave]
            if ruta is not None:
                actual = red.ruta_entre(*ab)
                if not _igual(list(map(tuple, actual[0])), list(map(tuple, ruta[0]))) or actual[1] != ruta[1]:
                    difs.append(f"{clave}: ruta_entre ya no da la misma ruta")
            p = calles.PistaCalle(red, nivel, semilla, ruta=ruta, superficie=sup, **circuito_kw)
            for campo in campos:
                if not _igual(getattr(p, campo), viejas[clave][campo]):
                    difs.append(f"{clave}.{campo}")
        else:
            n_inv += 1
            ruta = red.ruta_entre(*ab) if ab is not None else None
            p = calles.PistaCalle(red, nivel, semilla, ruta=ruta, superficie=sup, **circuito_kw)
            exceso = float((np.abs(p.kappa) - limite_kappa(p)).max())
            if exceso > 1e-9:
                difs.append(f"{clave}: era inválida en v11 y sigue con |kappa| {exceso:.4f} sobre el límite")
            if ruta is not None and max_giro_en(ruta[0], 20.0)[0] > 150.0:
                difs.append(f"{clave}: era inválida en v11 y ruta_entre sigue con vuelta en U")
        if p.circuito != "no" or p.x_b is not None:
            difs.append(f"{clave}: circuito={p.circuito!r} x_b={p.x_b!r} (debía ser 'no'/None)")
    return difs, n_val, n_inv


def _comparar_con_respaldo(circuito_kw):
    difs, n_val, n_inv = comparar_con_respaldo(("pavimento", "variado"), CAMPOS, circuito_kw)
    print(f"\n  v11: {n_val} pistas válidas comparadas bit a bit, {n_inv} inválidas revisadas contra el límite")
    assert n_val >= 10, f"muy pocas pistas válidas en v11 para comparar ({n_val})"
    assert not difs, "difiere del respaldo v11: " + ", ".join(difs[:20])


def test_defaults_bit_a_bit_contra_respaldo_v11():
    requiere_circuito()
    with _Config(CALLES_CIRCUITO="no", CALLES_SUPERFICIE="pavimento"):
        _comparar_con_respaldo({})


def test_circuito_no_explicito_bit_a_bit():
    requiere_circuito()
    with _Config(CALLES_CIRCUITO="otra"):
        _comparar_con_respaldo({"circuito": "no"})


def test_superficie_por_omision_sigue_siendo_config():
    requiere_circuito()
    red = red_mty()
    with _Config(CALLES_CIRCUITO="no", CALLES_SUPERFICIE="variado"):
        a = calles.PistaCalle(red, 3, 7)
    b = calles.PistaCalle(red, 3, 7, superficie="variado", circuito="no")
    assert a.superficie == "variado" and _igual(a.hs, b.hs) and _igual(a.mat, b.mat)


def _revisar_circuito(vuelta):
    requiere_circuito()
    malos = []
    for etiqueta, red, a, b, (pts, nombres, extra) in circuitos_de_prueba(vuelta):
        total = largo_poli(pts)
        x_b = float(extra["x_b"])
        if math.dist(pts[0], a) > 1.0:
            malos.append(f"{etiqueta}: no empieza en A ({math.dist(pts[0], a):.1f} m)")
        if math.dist(pts[-1], a) > 30.0:
            malos.append(f"{etiqueta}: no termina en A ({math.dist(pts[-1], a):.1f} m)")
        if not 0.0 < x_b < total:
            malos.append(f"{etiqueta}: x_b={x_b:.1f} fuera de la ruta (0, {total:.1f})")
        if math.dist(punto_a(pts, x_b), b) > 30.0:
            malos.append(f"{etiqueta}: el punto en x_b está a {math.dist(punto_a(pts, x_b), b):.1f} m de B")
        if abs(extra["largo_ida"] + extra["largo_vuelta"] - total) > 0.02 * total + 1.0:
            malos.append(f"{etiqueta}: largo_ida+largo_vuelta={extra['largo_ida'] + extra['largo_vuelta']:.1f}"
                         f" != {total:.1f}")
        if abs(extra["largo_ida"] - x_b) > 0.02 * total + 1.0:
            malos.append(f"{etiqueta}: largo_ida={extra['largo_ida']:.1f} != x_b={x_b:.1f}")
        giro, donde = max_giro_en(pts, 20.0)
        if giro > 150.0:
            malos.append(f"{etiqueta}: vuelta en U de {giro:.0f}° en <20 m cerca de x={donde:.0f} m "
                         f"(x_b={x_b:.0f})")
        p = calles.PistaCalle(red, 3, 1, ruta=(pts, nombres, extra), superficie="pavimento", circuito=vuelta)
        if p.circuito != vuelta:
            malos.append(f"{etiqueta}: pista.circuito={p.circuito!r}")
        if p.x_b is None or not p.salida < p.x_b < p.meta:
            malos.append(f"{etiqueta}: pista.x_b={p.x_b!r} fuera de (salida, meta)")
        else:
            d_b = math.dist(mapa_zona(p, p.x_b), b)
            if d_b > 30.0:
                malos.append(f"{etiqueta}: el mapa de la pista en x_b queda a {d_b:.1f} m de B")
        d_a = math.dist(mapa_zona(p, p.meta), a)
        if d_a > 30.0:
            malos.append(f"{etiqueta}: el mapa de la pista en la meta queda a {d_a:.1f} m de A")
        exceso = np.abs(p.kappa) - LIM_KAPPA_ASFALTO
        if exceso.max() > 1e-9:
            i = int(np.argmax(exceso))
            malos.append(f"{etiqueta}: |kappa|={abs(p.kappa[i]):.4f} > {LIM_KAPPA_ASFALTO:.4f} en x={p.xs[i]:.0f} m")
        if not (np.isfinite(p.kappa).all() and np.isfinite(p.kmax).all()):
            malos.append(f"{etiqueta}: kappa/kmax no finitos")
    assert not malos, "\n".join(malos)


def test_ruta_circuito_misma():
    _revisar_circuito("misma")


def test_ruta_circuito_otra():
    _revisar_circuito("otra")


def test_otra_comparte_poco_con_la_ida():
    requiere_circuito()
    otra = [fraccion_compartida(r[0], r[2]["x_b"]) for *_, r in circuitos_de_prueba("otra")]
    misma = [fraccion_compartida(r[0], r[2]["x_b"]) for *_, r in circuitos_de_prueba("misma")]
    print(f"\n  fracción del regreso por calles de la ida: otra={np.round(otra, 2).tolist()} "
          f"misma={np.round(misma, 2).tolist()}")
    assert float(np.mean(otra)) < 0.35, f"'otra' comparte en promedio {np.mean(otra):.0%} con la ida"
    assert max(otra) < 0.6, f"algún regreso 'otra' comparte {max(otra):.0%} con la ida"


def test_misma_regresa_por_las_mismas_calles():
    requiere_circuito()
    for etiqueta, _, _, _, (pts, nombres, extra) in circuitos_de_prueba("misma"):
        f = fraccion_compartida(pts, extra["x_b"])
        assert f >= 0.4 or "altern" in extra["vuelta"].lower() or "sentido" in extra["vuelta"].lower(), \
            f"{etiqueta}: 'misma' sólo comparte {f:.0%} con la ida y extra['vuelta']={extra['vuelta']!r} no lo explica"


def _doble_sentido(red, pts):
    inv = {tuple(map(float, v)): k for k, v in red.pos.items()}
    nodos = [inv.get(tuple(map(float, p))) for p in pts]
    if any(n is None for n in nodos):
        return False
    return all(any(w == u for w, _, _ in red.vecinos.get(v, ())) for u, v in zip(nodos[:-1], nodos[1:]))


def test_misma_en_calles_de_doble_sentido():
    requiere_circuito()
    vistos = []
    for nombre, red in redes():
        for k, (a, b) in enumerate(pares_ab(red, 300, 4242, 200.0, 500.0)):
            try:
                ida = red.ruta_entre(a, b)
            except RuntimeError:
                continue
            if not _doble_sentido(red, ida[0]):
                continue
            try:
                pts, nombres, extra = red.ruta_circuito(a, b, vuelta="misma")
            except RuntimeError as e:
                vistos.append((f"{nombre}#{k}", None, str(e)))
                continue
            ida_a = aristas(pts, 0.0, extra["x_b"])
            cubierta = largo_aristas(ida_a & aristas(pts, extra["x_b"], 1e18)) / max(largo_aristas(ida_a), 1e-9)
            vistos.append((f"{nombre}#{k}", cubierta, extra["vuelta"]))
            if sum(1 for v in vistos if v[0].startswith(nombre)) >= 3:
                break
    if not vistos:
        _saltar("no encontré pares A-B con ida toda de doble sentido")
    print("\n  'misma' con ida de doble sentido: " + "; ".join(
        f"{e}: {'error' if f is None else f'{f:.0%}'}" for e, f, _ in vistos))
    malos = [f"{e}: el regreso sólo cubre {f:.0%} de la ida ({t})" if f is not None else f"{e}: RuntimeError {t}"
             for e, f, t in vistos if f is None or f < 0.6]
    assert not malos, "\n".join(malos)


def test_ruta_circuito_errores_claros():
    requiere_circuito()
    red = red_mty()
    a = red.pos[red.inicios[0]]
    for args in ((a, a), (a, (a[0] + 5.0, a[1])), (a, (-5000.0, -5000.0))):
        try:
            red.ruta_circuito(*args, vuelta="otra")
        except RuntimeError as e:
            assert str(e).strip(), "RuntimeError sin mensaje"
        else:
            raise AssertionError(f"ruta_circuito{args} debía lanzar RuntimeError")


def test_circuito_al_azar_respeta_largo():
    requiere_circuito_azar()
    malos = []
    for nombre, red in redes():
        for vuelta in ("misma", "otra"):
            for sem in range(4):
                lmin, lmax = ((200.0, 300.0), (300.0, 450.0), (500.0, 800.0), (760.0, 1140.0))[sem]
                pts, nombres, extra = red.circuito(np.random.default_rng(sem), lmin, lmax, vuelta)
                total = largo_poli(pts)
                fuera = not lmin - 1.0 <= total <= lmax + 1.0
                tolerado = (extra.get("aviso") and lmin * 0.95 - 1.0 <= total <= lmax * 1.05 + 1.0)
                if fuera and not tolerado:
                    malos.append(f"{nombre}/{vuelta}/{sem}: largo {total:.0f} fuera de [{lmin:.0f}, {lmax:.0f}]")
                if math.dist(pts[0], pts[-1]) > 30.0:
                    malos.append(f"{nombre}/{vuelta}/{sem}: no regresa a A ({math.dist(pts[0], pts[-1]):.0f} m)")
                giro, donde = max_giro_en(pts)
                if giro > 150.0:
                    malos.append(f"{nombre}/{vuelta}/{sem}: vuelta en U de {giro:.0f}° en x={donde:.0f}")
                if not 0 < extra["x_b"] < total:
                    malos.append(f"{nombre}/{vuelta}/{sem}: x_b={extra['x_b']}")
    assert not malos, "\n".join(malos)


def test_circuito_al_azar_determinista():
    requiere_circuito_azar()
    red = red_mty()
    a = red.circuito(np.random.default_rng(5), 400, 700, "otra")
    b = red.circuito(np.random.default_rng(5), 400, 700, "otra")
    assert _igual(list(map(tuple, a[0])), list(map(tuple, b[0]))) and a[1] == b[1]


def test_pista_circuito_al_azar_por_nivel():
    requiere_circuito_azar()
    malos = []
    for nombre, red in redes():
        for vuelta in ("misma", "otra"):
            for nivel in (1, 3, 5, 8):
                with _Config(CALLES_CIRCUITO=vuelta):
                    p = calles.PistaCalle(red, nivel, 100 + nivel, superficie="pavimento")
                q = calles.PistaCalle(red, nivel, 100 + nivel, superficie="pavimento", circuito=vuelta)
                et = f"{nombre}/{vuelta}/N{nivel}"
                if not _igual(p.kappa, q.kappa):
                    malos.append(f"{et}: circuito=None no usa C.CALLES_CIRCUITO")
                largo = calles.largo_ruta(nivel)
                if not 0.7 * largo <= p.longitud <= 1.3 * largo:
                    malos.append(f"{et}: longitud {p.longitud:.0f} lejos de largo_ruta={largo:.0f}")
                if p.circuito != vuelta or p.x_b is None or not p.salida < p.x_b < p.meta:
                    malos.append(f"{et}: circuito={p.circuito!r} x_b={p.x_b!r}")
                if math.dist(mapa_zona(p, 0.0), mapa_zona(p, p.meta)) > 30.0:
                    malos.append(f"{et}: la meta (mapa) queda a "
                                 f"{math.dist(mapa_zona(p, 0.0), mapa_zona(p, p.meta)):.0f} m de A")
                try:
                    revisar_kappa(p, et)
                except AssertionError as e:
                    malos.append(str(e))
    assert not malos, "\n".join(malos)


def test_config_y_cli():
    requiere_circuito()
    r = subprocess.run([sys.executable, os.path.join(RAIZ, "main.py"), "--help"], cwd=RAIZ,
                       env=dict(os.environ, PYTHONIOENCODING="utf-8"), capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=120)
    assert r.returncode == 0, r.stderr
    for op in ("--circuito", "--superficie", "misma", "otra", "irregular"):
        assert op in r.stdout, f"main.py --help no menciona {op}"


def test_sesion_guarda_circuito():
    requiere_circuito()
    original = calles.ARCHIVO_SESION
    with tempfile.TemporaryDirectory() as tmp:
        calles.ARCHIVO_SESION = os.path.join(tmp, "sesion.json")
        try:
            with _Config(CALLES_CIRCUITO="otra", CALLES_SUPERFICIE="irregular"):
                calles.guardar_sesion("ciudad", red_mty().zona, ((25.68, -100.31), (25.67, -100.30)))
            with open(calles.ARCHIVO_SESION, encoding="utf-8") as f:
                d = json.load(f)
            assert d.get("circuito") == "otra", d
            with _Config(CALLES_CIRCUITO="no", CALLES_SUPERFICIE="pavimento"):
                modo, zona, ruta = calles.cargar_sesion()
                assert modo == "ciudad" and zona is not None and ruta is not None
                assert C.CALLES_CIRCUITO == "otra" and C.CALLES_SUPERFICIE == "irregular"
        finally:
            calles.ARCHIVO_SESION = original
    assert os.path.abspath(calles.ARCHIVO_SESION) == os.path.join(RAIZ, "sesion.json")


def test_sin_pistas_por_encima_del_agarre():
    requiere_circuito()
    malos = []
    for nombre, red in redes():
        for s in range(60):
            p = calles.PistaCalle(red, s % 8 + 1, s, superficie="pavimento", circuito="no")
            k = float(np.abs(p.kappa).max())
            if k > LIM_KAPPA_ASFALTO + 1e-9:
                malos.append(f"{nombre} PistaCalle(red, {s % 8 + 1}, {s}): |kappa|={k:.4f}")
    assert not malos, f"{len(malos)} pistas con |kappa| > {LIM_KAPPA_ASFALTO:.5f}:\n" + "\n".join(malos)


def test_planificador_tiene_opcion_circuito():
    requiere_circuito()
    with open(os.path.join(RAIZ, "planificador.py"), encoding="utf-8") as f:
        src = f.read()
    assert "Circuito" in src and "misma" in src.lower() and "otra" in src.lower(), \
        "planificador.py no tiene la opción 'Circuito: regresar a A' (misma / otra ruta)"


def test_planificador_headless():
    requiere_circuito()
    try:
        import tkinter as tk
        raiz = tk.Tk()
    except Exception as e:
        _saltar(f"sin tkinter/pantalla: {e}")
    raiz.withdraw()
    try:
        import planificador as PL
        aceptado = []
        pl = PL.Planificador(raiz, None, lambda red, ruta, info: aceptado.append((ruta, info)))
        pl.withdraw()
        red = red_mty()
        pl._usar_red(red, None)
        a, b = circuitos_de_prueba("otra")[0][2:4]
        for vuelta in ("misma", "otra"):
            pl.a, pl.b = a, b
            pl.var_circuito.set(True)
            pl.var_vuelta.set(vuelta)
            pl._cambio_circuito()
            raiz.update_idletasks()
            assert pl.ruta is not None and len(pl.ruta) == 3, pl.lbl_ruta.cget("text")
            assert "Circuito" in pl.lbl_ruta.cget("text")
        pl.var_circuito.set(False)
        pl._cambio_circuito()
        assert len(pl.ruta) == 2
        pl.var_circuito.set(True)
        pl._cambio_circuito()
        pl._aceptar()
        assert aceptado, "al_aceptar no se llamó"
        ruta, info = aceptado[0]
        assert info["circuito"] == "otra" and info.get("x_b") and len(ruta) == 3, info
    finally:
        try:
            raiz.destroy()
        except Exception:
            pass


def _pesos(archivo):
    ruta = os.path.join(RAIZ, archivo)
    if not os.path.isfile(ruta):
        _saltar(f"no hay {archivo}")
    with open(ruta, encoding="utf-8") as f:
        d = json.load(f)
    if tuple(d["capas"]) != tuple(C.CAPAS):
        _saltar(f"{archivo} es de otra arquitectura")
    return np.array(d["pesos"], float)


def recorrer(pista, w, ruidos=3, semilla=0):
    import fisica as F
    sim = F.Simulador(pista, np.repeat(w[None], ruidos, 0), semilla, ruido_por_moto=True)
    pasos = 0
    while not sim.terminado and pasos < 200000:
        sim.paso()
        pasos += 1
    return sim, int((sim.motivo == F.META).sum())


def test_factibilidad_campeona_calles_en_circuitos_pavimentados():
    requiere_circuito_azar()
    import fisica as F
    w = _pesos("mejor_moto_ciudad.json")
    red = red_mty()
    lineas, total, llegaron = [], 0, 0
    for nivel in (1, 2, 3):
        for j, vuelta in enumerate(("misma", "otra", "misma", "otra")):
            p = calles.PistaCalle(red, nivel, 500 + 10 * nivel + j, superficie="pavimento", circuito=vuelta)
            sim, ok = recorrer(p, w, 3, 7 + j)
            total += 3
            llegaron += ok
            motivos = sorted({F.MOTIVOS[int(m)] for m in sim.motivo})
            lineas.append(f"N{nivel} {vuelta:5s} {p.longitud:5.0f} m: {ok}/3 llegaron "
                          f"(progreso medio {np.mean(sim.progreso):.0f} m; {', '.join(motivos)})")
    print("\n  campeona de calles en circuitos pavimentados:\n   " + "\n   ".join(lineas)
          + f"\n   total {llegaron}/{total}")
    assert llegaron > total / 2, f"sólo {llegaron}/{total} completaron el circuito:\n" + "\n".join(lineas)


if __name__ == "__main__":
    import time
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    pruebas = [(k, v) for k, v in list(globals().items()) if k.startswith("test_") and callable(v)]
    fallas = saltadas = 0
    t0 = time.time()
    for nombre, fn in pruebas:
        t = time.time()
        try:
            fn()
            print(f"ok    {nombre} ({time.time() - t:.1f} s)")
        except unittest.SkipTest as e:
            saltadas += 1
            print(f"skip  {nombre}: {e}")
        except Exception as e:
            fallas += 1
            print(f"FALLA {nombre}: {type(e).__name__}: {e}")
    print(f"\n{len(pruebas) - fallas - saltadas}/{len(pruebas)} pasaron, {saltadas} saltadas, "
          f"{fallas} fallas en {time.time() - t0:.1f} s")
    sys.exit(1 if fallas else 0)
