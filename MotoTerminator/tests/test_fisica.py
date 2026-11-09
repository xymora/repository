import json
import math
import os
import subprocess
import sys
import textwrap

import numpy as np
import pytest

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
if RAIZ not in sys.path:
    sys.path.insert(0, RAIZ)

import config as C
import fisica as F
import red as R
import terreno as T
import validacion_fisica as V

RESPALDO_V9 = os.path.join(os.path.dirname(RAIZ), "MotoTerminator_respaldo_v9_2026-10-08")


def _pesos(n=6, semilla=3):
    return R.aleatorios(n, C.CAPAS, np.random.default_rng(semilla))


def _correr(sim, pasos=None):
    k = 0
    while not sim.terminado and (pasos is None or k < pasos):
        sim.paso()
        k += 1
    return sim


def test_meijaard_matrices_y_velocidades_criticas():
    mats = V.matrices_whipple(V.PARAMS_BENCHMARK)
    for a, b in zip(mats, (V.M_PUB, V.C1_PUB, V.K0_PUB, V.K2_PUB)):
        assert np.allclose(a, b, atol=1e-10, rtol=0)
    vw, vc = V.velocidades_criticas(mats)
    assert abs(vw - V.V_WEAVE_PUB) < 1e-9
    assert abs(vc - V.V_CAPSIZE_PUB) < 1e-9
    e2 = np.sort_complex(V.eigen_whipple(mats, 2.0))
    assert np.abs(e2 - np.sort_complex(V.EIG_V2_PUB)).max() < 1e-3
    assert V.eigen_whipple(mats, 5.0).real.max() < 0
    assert V.eigen_whipple(mats, 3.0).real.max() > 0
    assert V.eigen_whipple(mats, 7.0).real.max() > 0


def test_motivos_es_dict_codigo_texto():
    assert isinstance(F.MOTIVOS, dict)
    assert set(F.MOTIVOS) == {F.VIVO, F.META, F.VOLTEO, F.CAIDA, F.FUERA, F.CHOQUE,
                              F.ATASCADO, F.TIEMPO, F.ROTURA}
    assert F.MOTIVOS[np.int64(F.META)] == "llegó a la meta"


def test_determinismo_y_lote_igual_a_individual():
    p = T.Pista(2, 11)
    w = _pesos(5)
    a = _correr(F.Simulador(p, w, semilla_ruido=4), 250)
    b = _correr(F.Simulador(p, w, semilla_ruido=4), 250)
    assert np.array_equal(a.px, b.px) and np.array_equal(a.phi, b.phi)
    c = _correr(F.Simulador(p, w, semilla_ruido=4))
    d = _correr(F.Simulador(p, w[2:3], semilla_ruido=4))
    assert c.aptitud()[2] == d.aptitud()[0]


def test_componentes_suman_aptitud_normal_y_estricta():
    p = T.Pista(3, 5)
    w = _pesos(8)
    sim = _correr(F.Simulador(p, w, semilla_ruido=5))
    comp = sim.componentes_aptitud()
    assert set(comp) >= {"progreso", "llegada", "rapidez", "reintentos"}
    assert all(v.shape == (8,) for v in comp.values())
    assert np.allclose(sum(comp.values()), sim.aptitud(), atol=1e-9, rtol=0)
    viejo = C.APTITUD_ESTRICTA
    try:
        C.APTITUD_ESTRICTA = True
        comp_e = sim.componentes_aptitud()
        assert np.allclose(sum(comp_e.values()), sim.aptitud(), atol=1e-9, rtol=0)
        assert np.all(sim.aptitud() <= sum(comp.values()) + 1e-9)
    finally:
        C.APTITUD_ESTRICTA = viejo


def test_llegadas_distancia_y_reintentos_cero():
    p = T.Pista(1, 2)
    w = _pesos(6)
    sim = _correr(F.Simulador(p, w, semilla_ruido=2, max_reintentos=0))
    assert np.all(sim.reintentos == 0)
    assert sim.llegaron().dtype == bool and sim.llegaron().shape == (6,)
    assert np.array_equal(sim.llegadas_limpias(), sim.llegaron())
    d = sim.distancia_km()
    assert d.shape == (6,) and np.all(d >= 0) and np.all(d <= (p.meta - p.salida) / 1000 + 1e-9)
    assert np.allclose(d, sim.progreso / 1000)
    sim3 = _correr(F.Simulador(p, w, semilla_ruido=2))
    assert np.all(sim3.llegadas_limpias() <= sim3.llegaron())
    assert np.array_equal(sim3.llegadas_limpias(), sim3.llegaron() & (sim3.reintentos == 0))


def test_controlador_y_paso_ctrl_equivalen_a_la_red():
    p = T.Pista(2, 8)
    w = _pesos(4)
    red = R.desempacar(w, C.CAPAS)

    def ctrl_red(obs, sim):
        return R.adelante([(W[sim.ids], b[sim.ids]) for W, b in red], obs)

    a = _correr(F.Simulador(p, w, semilla_ruido=8))
    b = _correr(F.Simulador(p, None, semilla_ruido=8, controlador=ctrl_red, n=4))
    assert np.array_equal(a.aptitud(), b.aptitud())
    c = _correr(F.Simulador(p, w, semilla_ruido=8, filtro_obs=lambda o, s: o))
    assert np.array_equal(a.aptitud(), c.aptitud())
    e = F.Simulador(p, w, semilla_ruido=8)
    while not e.terminado:
        obs = e.observar()
        e.paso(ctrl=ctrl_red(obs, e))
    assert np.array_equal(a.aptitud(), e.aptitud())


def test_sin_pesos_exige_controlador_y_n():
    try:
        F.Simulador(T.Pista(1, 0), None)
    except ValueError:
        return
    raise AssertionError("debía fallar sin pesos ni controlador")


def test_ruido_por_moto_determinista_y_distinto():
    p = T.Pista(3, 1)
    w = np.repeat(_pesos(1), 4, axis=0)
    kw = dict(semilla_ruido=9, registrar=True)
    a = _correr(F.Simulador(p, w, ruido_por_moto=True, **kw), 30).traza_arrays()["phi"][-1]
    b = _correr(F.Simulador(p, w, ruido_por_moto=True, **kw), 30).traza_arrays()["phi"][-1]
    c = _correr(F.Simulador(p, w, **kw), 30).traza_arrays()["phi"][-1]
    assert np.all(np.isfinite(a)) and np.array_equal(a, b)
    assert np.all(c == c[0])
    assert len(np.unique(a)) > 1


def test_traza():
    p = T.Pista(1, 3)
    w = _pesos(3)
    sim = _correr(F.Simulador(p, w, semilla_ruido=3, registrar=True), 120)
    tr = sim.traza_arrays()
    assert set(tr) == set(F.CLAVES_TRAZA)
    for k, a in tr.items():
        assert a.shape == (120, 3), k
    assert np.allclose(tr["t"][:, 0], (np.arange(120) + 1) * C.DT_CONTROL)
    assert np.all(np.isfinite(tr["v_segura"][0]))
    sin = F.Simulador(p, w, registrar=False)
    assert sin.traza is None and sin.traza_arrays() == {}


def test_equilibrio_estatico_de_la_suspension():
    s = F.Simulador(V.pista_plana(), np.zeros((1, R.n_parametros(C.CAPAS))))
    s.vx[:] = 0
    s.wvx[:] = 0
    s.ws[:] = 0
    for _ in range(int(3 / C.DT)):
        s._fisica(0.0, 0.0)
    m_total = C.MASA_CHASIS + 2 * C.MASA_RUEDA
    assert abs(s.fn[:, 0].sum() - m_total * C.G) / (m_total * C.G) < 1e-3
    (xt, _), (xd, _) = C.EJES
    reparto = np.array([xd, -xt]) / (xd - xt)
    esperado = C.MASA_CHASIS * C.G * reparto / C.SUSP_K
    assert np.all(np.abs(s.comp[:, 0] - esperado) / esperado < 0.05)


def test_caida_libre():
    s = F.Simulador(V.pista_plana(), np.zeros((1, R.n_parametros(C.CAPAS))))
    s.py += 10
    s.wy += 10
    s.vx[:] = 0
    s.wvx[:] = 0
    s.ws[:] = 0
    n = 54
    for _ in range(n):
        s._fisica(0.0, 0.0)
    m_total = C.MASA_CHASIS + 2 * C.MASA_RUEDA
    vcm = (C.MASA_CHASIS * s.vy[0] + C.MASA_RUEDA * s.wvy[:, 0].sum()) / m_total
    assert abs(vcm + C.G * n * C.DT) < 2e-3 * C.G * n * C.DT


def test_estabilidad_y_tope_direccion():
    v = np.linspace(0, 40, 200)
    f = F.estabilidad(v)
    assert np.all(np.diff(f) >= 0) and f[0] == 0 and f[-1] == 1
    tope = F._tope_direccion(v)
    assert np.all(tope <= C.DIR_MAX + 1e-12) and np.all(tope > 0)


def test_convergencia_aceleracion():
    vf = {}
    base = C.SUBPASOS
    for k in (base, 2 * base):
        with V.subpasos(k):
            vf[k] = V.maniobra(lambda t: (1.0, 0.0, 0.0), 3.0, v0=9.0)[-1, 2]
    assert abs(vf[base] - vf[2 * base]) / vf[2 * base] < 2e-3
    assert C.SUBPASOS == base and abs(C.DT - C.DT_CONTROL / base) < 1e-15


def test_msc_evita_vuelco_en_frenada_total():
    with V.bandera("MSC_ACTIVO", False):
        sin = V.frenada(1.0)
    with V.bandera("MSC_ACTIVO", True):
        con = V.frenada(1.0)
    assert sin["se_volteo"] == (C.CG_ATRAS == 0 and C.CG_ABAJO == 0)
    assert not con["se_volteo"] and con["cabeceo_max_grados"] < 15


def test_flags_activos_corren_sin_nan():
    p = T.Pista(5, 4)
    w = _pesos(6)
    nombres = ("MSC_ACTIVO", "FRICCION_COMBINADA", "RUIDO_SQRT_DT", "APTITUD_ESTRICTA")
    viejos = {k: getattr(C, k) for k in nombres}
    try:
        for k in nombres:
            setattr(C, k, True)
        sim = _correr(F.Simulador(p, w, semilla_ruido=4))
        assert np.all(np.isfinite(sim.aptitud()))
    finally:
        for k, v in viejos.items():
            setattr(C, k, v)


def test_flags_apagados_por_defecto():
    for k in ("MSC_ACTIVO", "FRICCION_COMBINADA", "RUIDO_SQRT_DT", "APTITUD_ESTRICTA"):
        assert getattr(C, k) is False, k


_SCRIPT_PARIDAD = textwrap.dedent("""
    import sys, os, json
    d = sys.argv[1]; sys.path.insert(0, d)
    import numpy as np, config as C, fisica as F, terreno as T, red as R
    w = R.aleatorios(12, C.CAPAS, np.random.default_rng(77))
    out = {}
    for niv, s in ((1, 0), (4, 3), (7, 9)):
        sim = F.Simulador(T.Pista(niv, s), w, semilla_ruido=s)
        while not sim.terminado:
            sim.paso()
        out[f"{niv}_{s}"] = [sim.aptitud().tolist(), sim.motivo.tolist(), sim.pos_final.tolist(),
                             sim.reintentos.tolist()]
    print(json.dumps(out))
""")


def test_paridad_bit_a_bit_con_v9():
    if not os.path.isdir(RESPALDO_V9):
        print("  (omitida: no existe el respaldo v9)")
        return
    res = []
    for d in (RESPALDO_V9, RAIZ):
        r = subprocess.run([sys.executable, "-I", "-c", _SCRIPT_PARIDAD, d], capture_output=True,
                           text=True, timeout=300, cwd=d)
        assert r.returncode == 0, r.stderr
        res.append(json.loads(r.stdout.strip().splitlines()[-1]))
    assert res[0] == res[1]


if __name__ == "__main__":
    import time
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
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


def _sin_cabeceo(obs, sim):
    import controladores as K
    u = K.ControladorPD()(obs, sim)
    u[:, 1] = 0.0
    return u


def test_contrapeso_aterriza_de_trasera_y_no_se_para():
    if not getattr(C, "CONTRAPESO_ACTIVO", False):
        pytest.skip("contrapeso apagado")
    primero, th_max = [], 0.0
    for semilla in range(6):
        p = T.Pista(5, 7500 + semilla)
        s = F.Simulador(p, None, n=1, semilla_ruido=semilla, controlador=_sin_cabeceo)
        aire = 0
        while not s.terminado:
            s.paso()
            if not len(s.ids):
                break
            c = s.fn[:, 0] > 0
            if not c.any():
                aire += 1
            else:
                if aire >= 12:
                    primero.append("trasera" if c[0] else "delantera")
                aire = 0
            th_max = max(th_max, abs(float(s.th[0])))
    assert primero and primero.count("delantera") <= len(primero) // 10
    assert th_max < math.radians(60)


def test_contrapeso_se_va_al_lado_contrario_de_la_curva():
    if not getattr(C, "CONTRAPESO_ACTIVO", False):
        pytest.skip("contrapeso apagado")
    s = F.Simulador(V.pista_plana(), None, n=1,
                    controlador=lambda o, sim: np.tile([0.3, 0.0, 0.5], (len(o), 1)))
    for _ in range(60):
        s.paso()
    assert abs(s.incl[0]) > 0.2
    assert np.sign(s.contra_y[0]) == -np.sign(s.incl[0])
    assert abs(s.phi_moto[0]) > abs(s.phi[0])
