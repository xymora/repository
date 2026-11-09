import copy
import json
import os
import subprocess
import sys
import textwrap
import time

import numpy as np

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
if RAIZ not in sys.path:
    sys.path.insert(0, RAIZ)

import clima as CL
import config as C
import fisica as F
import red as R
import terreno as T

RESPALDO_V12 = os.path.join(os.path.dirname(RAIZ), "MotoTerminator_respaldo_v12_2026-10-09")


def _pesos(n=6, semilla=3):
    return R.aleatorios(n, C.CAPAS, np.random.default_rng(semilla))


def _correr(sim, pasos=None):
    k = 0
    while not sim.terminado and (pasos is None or k < pasos):
        sim.paso()
        k += 1
    return sim


def _red_monterrey():
    try:
        import calles
        return calles.RedVial(calles.zona_para('Monterrey · Centro'), avisar=lambda *a: None)
    except Exception:
        return None


def test_api_presets_y_crear():
    for nombre in ("despejado", "llovizna", "lluvia", "tormenta", "granizo", "niebla",
                   "viento_cruzado", "rafagas", "tormenta_con_rafagas"):
        assert nombre in CL.PRESETS
        c = CL.crear(nombre, 7)
        assert isinstance(c, CL.Clima) and c.nombre == nombre and c.semilla == 7
        assert isinstance(c.descripcion(), str) and c.descripcion()
        assert CL.Clima.de_dict(c.a_dict()) == c
    assert CL.crear("despejado").despejado
    assert CL.crear(None) is None
    c = CL.crear("lluvia", 1)
    assert CL.crear(c) == c
    try:
        CL.crear("huracan_de_fuego")
        raise AssertionError("debió fallar")
    except ValueError:
        pass


def test_clima_aleatorio_determinista_y_escala():
    a = [CL.clima_aleatorio(np.random.default_rng(s), 4, 0) for s in range(50)]
    b = [CL.clima_aleatorio(np.random.default_rng(s), 4, 0) for s in range(50)]
    assert a == b
    rng = np.random.default_rng(0)
    cs = [CL.clima_aleatorio(rng, 1) for _ in range(3000)]
    frac = np.mean([c.despejado for c in cs])
    assert 0.25 < frac < 0.35, frac
    lluvia1 = np.mean([c.lluvia for c in cs])
    rng = np.random.default_rng(0)
    cs8 = [CL.clima_aleatorio(rng, 8) for _ in range(3000)]
    assert 0.25 < np.mean([c.despejado for c in cs8]) < 0.35
    assert np.mean([c.lluvia for c in cs8]) > 1.5 * lluvia1
    assert np.mean([c.viento_medio for c in cs8]) > np.mean([c.viento_medio for c in cs])


def test_preparar_pista_no_muta_y_moja():
    p = T.Pista(5, 123)
    copia = {k: np.array(getattr(p, k)).copy() for k in ("mu", "mu_min", "rr", "rugo", "kappa")}
    q = CL.preparar_pista(p, CL.crear("tormenta", 4))
    for k, v in copia.items():
        assert np.array_equal(getattr(p, k), v), k
    assert not hasattr(p, "charco") and getattr(p, "clima", None) is None
    assert q is not p and q.pista_seca is p
    asf = p.mat == T.M["asfalto"]
    seco_charco = asf & (q.charco == 0)
    assert np.all(q.mu[seco_charco] < p.mu[seco_charco])
    r = q.mu[seco_charco] / p.mu[seco_charco]
    assert np.all((r >= 0.5) & (r <= 0.75)), (r.min(), r.max())
    assert (q.charco > 0).any()
    assert np.all(q.mu_min <= q.mu + 1e-12)
    tierra = p.mat == T.M["tierra"]
    if tierra.any():
        assert np.all(q.rr[tierra] > p.rr[tierra])
    g = CL.preparar_pista(p, CL.crear("granizo", 1))
    assert np.all(g.rugo > p.rugo)


def test_aquaplaning_depende_de_velocidad():
    f = CL.factor_aquaplaning(np.array([5.0, 15.0, 20.0, 25.0, 30.0, 40.0]), 6.0)
    assert f[0] == 1.0 and f[1] == 1.0
    assert np.all(np.diff(f) <= 0)
    assert f[-1] < 0.3
    assert CL.factor_aquaplaning(19.0, 8.0) < CL.factor_aquaplaning(19.0, 2.0)
    assert CL.factor_aquaplaning(40.0, 0.0) == 1.0


def test_none_igual_y_despejado_igual_que_sin_clima():
    p = T.Pista(3, 9)
    w = _pesos(5)
    a = _correr(F.Simulador(p, w, semilla_ruido=2))
    b = _correr(F.Simulador(p, w, semilla_ruido=2, clima=None))
    c = _correr(F.Simulador(p, w, semilla_ruido=2, clima="despejado"))
    for s in (b, c):
        assert np.array_equal(a.aptitud(), s.aptitud())
        assert np.array_equal(a.pos_final, s.pos_final)
    assert a.clima is None and a.viento_actual == (0.0, 0.0)


def test_simulador_no_muta_pista_y_determinista():
    p = T.Pista(4, 31)
    mu = p.mu.copy()
    w = _pesos(4)
    s1 = _correr(F.Simulador(p, w, semilla_ruido=1, clima=CL.crear("tormenta_con_rafagas", 5)))
    s2 = _correr(F.Simulador(p, w, semilla_ruido=1, clima=CL.crear("tormenta_con_rafagas", 5)))
    assert np.array_equal(p.mu, mu) and not hasattr(p, "charco")
    assert np.array_equal(s1.aptitud(), s2.aptitud())
    assert np.array_equal(s1.pos_final, s2.pos_final)
    assert s1.clima.nombre == "tormenta_con_rafagas"
    q = CL.preparar_pista(p, CL.crear("tormenta_con_rafagas", 5))
    s3 = _correr(F.Simulador(q, w, semilla_ruido=1, clima=CL.crear("tormenta_con_rafagas", 5)))
    assert s3.pista is q
    assert np.array_equal(s1.aptitud(), s3.aptitud())


def test_viento_igual_para_todas_las_motos_y_por_semilla():
    p = T.Pista(2, 4)
    cl = CL.crear("rafagas", 11)
    v1, v8 = [], []
    s1 = F.Simulador(p, _pesos(1), semilla_ruido=0, clima=cl)
    s8 = F.Simulador(p, _pesos(8, 9), semilla_ruido=3, clima=cl)
    for _ in range(150):
        if not s1.terminado:
            s1.paso()
            v1.append(s1.viento_actual)
        if not s8.terminado:
            s8.paso()
            v8.append(s8.viento_actual)
    m = min(len(v1), len(v8))
    assert m > 30
    assert v1[:m] == v8[:m]
    rap = np.array([v[0] for v in v1])
    assert rap.std() > 0.3 and rap.max() > 1.0
    s = F.Simulador(p, _pesos(6), clima=CL.crear("viento_cruzado", 2))
    s.paso()
    a_lat = s._viento[0]
    assert np.allclose(a_lat, a_lat[0])
    s2 = F.Simulador(p, _pesos(1), clima=CL.crear("rafagas", 12))
    _correr(s2, 100)
    assert s2.viento_actual != v1[99]


def test_viento_empuja_de_lado_y_frena_de_frente():
    p = T.Pista(1, 3)
    w = _pesos(1, 5)

    def ctrl_recto(obs, sim):
        return np.tile([0.3, 0.0, 0.0], (obs.shape[0], 1))
    lat = {}
    for nombre, d in (("izq", np.pi / 2), ("der", -np.pi / 2), ("nada", 0.0)):
        cl = CL.Clima(nombre=nombre, viento_medio=12.0 if nombre != "nada" else 0.0,
                      direccion_viento=d)
        s = F.Simulador(p, None, controlador=ctrl_recto, n=1, max_reintentos=0, clima=cl)
        _correr(s, 45)
        lat[nombre] = float(s.lat[0]) if len(s.lat) else float("nan")
    assert lat["izq"] > lat["nada"] > lat["der"], lat
    vf = {}
    for nombre, d in (("frente", np.pi), ("cola", 0.0)):
        cl = CL.Clima(nombre=nombre, viento_medio=15.0, direccion_viento=d)
        s = F.Simulador(p, None, controlador=ctrl_recto, n=1, max_reintentos=0, clima=cl)
        _correr(s, 90)
        vf[nombre] = float(s.vx[0])
    assert vf["cola"] > vf["frente"], vf


def test_calles_viento_absoluto_contra_rumbo():
    red = _red_monterrey()
    if red is None:
        return
    import calles
    p = calles.PistaCalle(red, 3, 7001, superficie="pavimento", circuito="no")
    assert CL.es_calle(p) and not CL.es_calle(T.Pista(1, 1))
    wp, wq = CL.viento_en_marco_camino(p, (10.0, 0.0), np.array([p.salida, p.salida + 50]), True)
    r = p.rumbo[p.indice(np.array([p.salida, p.salida + 50]))]
    assert np.allclose(wp, 10 * np.cos(r)) and np.allclose(wq, -10 * np.sin(r))
    s = _correr(F.Simulador(p, _pesos(3), clima=CL.crear("tormenta_con_rafagas", 3)), 200)
    assert np.all(np.isfinite(s.progreso))


def test_sin_nan_tormenta_nivel_8():
    p = T.Pista(8, 77)
    s = F.Simulador(p, _pesos(10, 21), semilla_ruido=4, clima=CL.crear("tormenta_con_rafagas", 8),
                    ruido_por_moto=True)
    while not s.terminado:
        s.paso()
        for k in ("px", "vx", "lat", "psi", "phi", "wob"):
            assert np.all(np.isfinite(getattr(s, k))), k
    assert np.all(np.isfinite(s.aptitud()))
    assert np.all(np.isfinite(s.pos_final))


def test_niebla_degrada_observacion_y_compone_con_filtro():
    p = T.Pista(2, 5)
    vistos = {}

    def filtro(obs, sim):
        vistos.setdefault(sim.clima.nombre if sim.clima else "none", []).append(obs.copy())
        return obs
    for cl in (None, CL.crear("niebla", 3)):
        s = F.Simulador(p, _pesos(2), filtro_obs=filtro, clima=cl)
        _correr(s, 5)
    limpio, niebla = np.array(vistos["none"]), np.array(vistos["niebla"])
    assert np.abs(niebla[..., 26] - limpio[..., 26]).max() > 0
    assert np.allclose(niebla[0, :, :5], limpio[0, :, :5])


def test_observadores_llamados_y_al_regresar():
    p = T.Pista(6, 2)

    class Obs:
        def __init__(self):
            self.n = 0
            self.regresos = []

        def __call__(self, sim):
            self.n += 1

        def al_regresar(self, sim, ids, t):
            self.regresos.append((list(ids), t))
    o = Obs()
    s = F.Simulador(p, _pesos(8, 1), semilla_ruido=0)
    assert s.observadores == []
    s.observadores.append(o)
    pasos = 0
    while not s.terminado:
        s.paso()
        pasos += 1
    assert o.n == pasos
    if s.eventos:
        assert o.regresos and s._ultimo_regreso is not None
        assert all(t <= s.t for _, t in o.regresos)
    s0 = _correr(F.Simulador(p, _pesos(8, 1), semilla_ruido=0))
    assert np.array_equal(s0.aptitud(), s.aptitud())


_GUION = textwrap.dedent(r'''
    import hashlib, importlib.util, json, sys
    raiz, fis = sys.argv[1], sys.argv[2]
    sys.path.insert(0, raiz)
    import numpy as np
    spec = importlib.util.spec_from_file_location("fisica", fis)
    F = importlib.util.module_from_spec(spec); sys.modules["fisica"] = F; spec.loader.exec_module(F)
    import config as C, red as R, terreno as T
    h = hashlib.sha256()
    w = R.aleatorios(8, C.CAPAS, np.random.default_rng(7))
    def correr(p, **kw):
        s = F.Simulador(p, w, semilla_ruido=int(p.semilla), **kw)
        while not s.terminado:
            s.paso()
        for a in (s.aptitud(), s.motivo, s.progreso, s.t_fin, s.reintentos, s.pos_final):
            h.update(np.ascontiguousarray(a).tobytes())
    for niv, sem in ((2, 11), (6, 33)):
        correr(T.Pista(niv, sem))
    correr(T.Pista(4, 5), ruido_por_moto=True)
    try:
        import calles
        red = calles.RedVial(calles.zona_para('Monterrey · Centro'), avisar=lambda *a: None)
        correr(calles.PistaCalle(red, 3, 1, superficie="pavimento", circuito="no"))
    except Exception:
        h.update(b"sin-calles")
    print(h.hexdigest())
''')


def test_bit_a_bit_contra_respaldo_v12():
    viejo = os.path.join(RESPALDO_V12, "fisica.py")
    if not os.path.exists(viejo):
        return
    hashes = []
    for fis in (viejo, os.path.join(RAIZ, "fisica.py")):
        r = subprocess.run([sys.executable, "-c", _GUION, RAIZ, fis], capture_output=True,
                           text=True, timeout=600, cwd=RAIZ)
        assert r.returncode == 0, r.stderr[-2000:]
        hashes.append(r.stdout.strip().splitlines()[-1])
    assert hashes[0] == hashes[1], hashes


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    pruebas = [(k, v) for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    fallas = 0
    t0 = time.time()
    for nombre, fn in pruebas:
        t = time.time()
        try:
            fn()
            print(f"ok    {nombre} ({time.time() - t:.1f} s)")
        except Exception as e:
            fallas += 1
            print(f"FALLA {nombre}: {type(e).__name__}: {e}")
    print(f"\n{len(pruebas) - fallas}/{len(pruebas)} pruebas pasaron en {time.time() - t0:.1f} s")
    sys.exit(1 if fallas else 0)
