import os
import sys
import tempfile

import numpy as np

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
if RAIZ not in sys.path:
    sys.path.insert(0, RAIZ)

import config as C
import evaluacion as E
import red as R
import sensores as S
import stl as STL
from terreno import Pista


def _pesos():
    try:
        return E.cargar_pesos()[0]
    except (OSError, ValueError, KeyError):
        return R.aleatorios(1, C.CAPAS, np.random.default_rng(0))[0]


def test_clopper_pearson_valores_conocidos():
    lo, hi = E.clopper_pearson(8, 8)
    assert abs(lo - 0.6306) < 1e-3 and hi == 1.0
    lo, hi = E.clopper_pearson(0, 10)
    assert lo == 0.0 and abs(hi - 0.3085) < 1e-3
    lo, hi = E.clopper_pearson(5, 10)
    assert abs(lo - 0.1871) < 1e-3 and abs(hi - 0.8129) < 1e-3


def test_garwood_y_regla_del_tres():
    lo, hi = E.garwood(0, 1.0)
    assert lo == 0.0 and abs(hi - 3.689) < 1e-2
    lo, hi = E.garwood(10, 2.0)
    assert lo < 5.0 < hi
    assert E.n_para_afirmar(0.01) == 299


def test_semillas_disjuntas_del_entrenamiento():
    assert E.semilla_pista_prueba(1, 0) >= 2 ** 31
    assert E.semilla_pista_prueba(8, 999) < E.semilla_pista_prueba(9, 0)
    import falsificador as Fa
    assert Fa.semilla_pista_fals(8, 999) != E.semilla_pista_prueba(8, 999)


def test_stl_operadores():
    rho = np.array([[1.0, -1.0], [0.5, 2.0], [np.nan, 3.0]])
    assert np.allclose(STL.siempre(rho), [0.5, -1.0])
    assert np.allclose(STL.eventualmente(rho), [1.0, 3.0])
    vm = STL.ventana_max(np.array([[0.0], [1.0], [-2.0], [-3.0]]), 1)
    assert np.allclose(vm[:, 0], [1.0, 1.0, -2.0, -3.0])
    assert np.allclose(STL.implica(np.array([1.0]), np.array([-0.5])), [-0.5])


def test_stl_requisitos_traza_sintetica():
    pista = Pista(1, 123)
    T, n = 120, 2
    t = np.repeat((np.arange(T) * C.DT_CONTROL)[:, None], n, 1)
    lat = np.full((T, n), C.LAT_CARRIL)
    lat[60:100, 1] = 0.5
    lat[100:, 1] = 2.5
    traza = {"t": t, "x": np.repeat(np.linspace(0, pista.meta + 1, T)[:, None], n, 1),
             "v": np.full((T, n), 10.0), "lat": lat, "phi": np.zeros((T, n)),
             "th": np.zeros((T, n)), "cmg_sat": np.zeros((T, n)),
             "v_segura": np.full((T, n), 20.0)}
    r = STL.evaluar_requisitos(traza, pista)
    assert r["R1"]["rho"][0] > 0 and r["R1"]["rho"][1] < 0
    assert r["R2"]["rho"][0] > 0 and r["R2"]["rho"][1] < 0
    assert r["R3"]["rho"][0] > 0 and r["R8"]["rho"][0] > 0
    assert r["R5"]["rho"][1] < 0
    assert np.all(STL.robustez_normalizada(r)[1] < 0)


class _SimFalso:
    def __init__(self, n):
        self.ids, self.n_total, self.t = np.arange(n), n, 0.0
        self.pista = Pista(1, 5)
        self.px = np.full(n, 20.0)


def test_sensores_ideal_es_identidad_y_latencia_retrasa():
    assert S.crear_filtro("ideal") is None
    f = S.FiltroSensores(latencia=2)
    sim = _SimFalso(3)
    salidas = [f(np.full((3, C.N_ENTRADAS), float(k)), sim)[0, 0] for k in range(5)]
    assert salidas == [0.0, 0.0, 0.0, 1.0, 2.0]
    g = S.FiltroSensores(mu_factor=1.3)
    o = np.zeros((3, C.N_ENTRADAS))
    o[:, 21] = 0.5
    assert np.allclose(g(o, sim)[:, 21], 0.65)
    r = S.crear_filtro("realista", semilla=1)
    o2 = r(np.zeros((3, C.N_ENTRADAS)), _SimFalso(3))
    assert o2.shape == (3, C.N_ENTRADAS) and np.any(o2 != 0)


def test_evaluar_corrida_corta_y_estricta_no_supera_reintentos():
    with tempfile.TemporaryDirectory() as d:
        out = E.evaluar(_pesos(), "terreno", (1,), pistas=2, ruidos=2, dir_resultados=d, verbose=False)
        s = out["niveles"][1]
        assert s["n_episodios"] == 4
        assert s["llegada_limpia"]["k"] <= s["llegada_con_reintentos"]["k"]
        assert 0 <= s["llegada_limpia"]["ic"][0] <= s["llegada_limpia"]["tasa"] <= s["llegada_limpia"]["ic"][1]
        assert os.path.exists(out["archivos"]["json"]) and os.path.exists(out["archivos"]["csv"])
        assert set(s["stl"]) >= {"R1", "R2", "R3", "R8", "R9"}
        import csv
        with open(out["archivos"]["csv"], encoding="utf-8") as f:
            cols = next(csv.reader(f))
        assert {"controlador", "nivel", "llego", "llego_limpio", "motivo", "distancia_km"} <= set(cols)
        assert "episodios" in os.path.basename(out["archivos"]["csv"])
        frag = S.barrido_fragilidad(_pesos(), 1, pistas=1, ruidos=2, ejes={"latencia": [0, 3]},
                                    verbose=False, dir_resultados=d)
        assert [f["valor"] for f in frag["latencia"]] == [0, 3]
        assert any(n.startswith("fragilidad") and n.endswith(".json") for n in os.listdir(d))
        import reporte_seguridad as RS
        filas = RS.tabla_kpis(out)
        assert filas[0]["n"] == 4 and filas[0]["ic_lo"] <= filas[0]["llegada_limpia_pct"]
        assert os.path.exists(RS.guardar_kpis(filas, os.path.join(d, "kpis.csv")))


def test_evaluar_es_reproducible():
    a = E.evaluar(_pesos(), "terreno", (1,), pistas=1, ruidos=2, guardar=False, verbose=False,
                  con_reintentos=False)
    b = E.evaluar(_pesos(), "terreno", (1,), pistas=1, ruidos=2, guardar=False, verbose=False,
                  con_reintentos=False)
    assert [e["t_fin_s"] for e in a["episodios"]] == [e["t_fin_s"] for e in b["episodios"]]


def test_dominio_aleatorio_restaura_config_y_pista():
    pista = Pista(1, 77)
    antes = {k: getattr(C, k) for k in S.RANGOS_DOMINIO if hasattr(C, k)}
    inercia, mu0 = C.INERCIA_CHASIS, pista.mu.copy()
    dr = S.dominio_para_pista(pista, escala=1.0)
    with dr.contexto(pista):
        assert C.PAR_MOTOR == antes["PAR_MOTOR"] * dr.factores["PAR_MOTOR"]
        assert np.allclose(pista.mu, mu0 * dr.factores["mu"])
        sim = E.crear_simulador(pista, np.atleast_2d(_pesos()), 1)
        sim.correr(30)
    assert {k: getattr(C, k) for k in antes} == antes and C.INERCIA_CHASIS == inercia
    assert np.array_equal(pista.mu, mu0)
    assert S.dominio_para_pista(pista).factores == dr.factores


def test_monitor_online_coincide_con_offline():
    pista = Pista(1, E.semilla_pista_prueba(1, 0))
    mon = STL.MonitorSTL(2)
    sim = E.crear_simulador(pista, np.repeat(_pesos()[None], 2, 0), 5, max_reintentos=0,
                            ruido_por_moto=True, registrar=True, filtro_obs=mon.como_filtro())
    E._correr(sim)
    off = STL.evaluar_requisitos(E.obtener_traza(sim), pista)
    for r in ("R1", "R6", "R9"):
        assert np.all(mon.rho[r] >= off[r]["rho"] - 1e-9)
        assert np.allclose(mon.rho[r], off[r]["rho"], atol=0.05)


def test_controlador_y_falsificador_humo():
    import falsificador as Fa

    def frena_siempre(obs, sim):
        u = np.zeros((obs.shape[0], 3))
        u[:, 0] = -1.0
        return u

    if E._contrato_disponible():
        out = E.evaluar(frena_siempre, "terreno", (1,), pistas=1, ruidos=2, guardar=False,
                        verbose=False, con_reintentos=False)
        assert out["niveles"][1]["llegada_limpia"]["k"] == 0
    f = Fa.falsificar(_pesos(), 1, pistas=1, poblacion=8, iteraciones=2, n_is=8, guardar=False,
                      verbose=False)
    p = f["pistas"][0]
    assert p["mc_nominal"]["n"] == 8 and p["ess_is"] is not None


if __name__ == "__main__":
    import time
    fallos = 0
    for nombre, fn in list(globals().items()):
        if nombre.startswith("test_") and callable(fn):
            t0 = time.time()
            try:
                fn()
                print(f"ok    {nombre} ({time.time() - t0:.1f} s)")
            except Exception as e:
                fallos += 1
                print(f"FALLA {nombre}: {type(e).__name__}: {e}")
    sys.exit(1 if fallos else 0)
