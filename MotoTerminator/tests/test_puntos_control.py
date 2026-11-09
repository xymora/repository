import json
import os
import sys
import time

import numpy as np

AQUI = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if AQUI not in sys.path:
    sys.path.insert(0, AQUI)

import config as C
import fisica as F
import puntos_control as PC
import red as R
import terreno

_CACHE = {}
N_PISTAS = 12


def _silencio(*a, **k):
    pass


def _pesos(nombre):
    if nombre not in _CACHE:
        with open(os.path.join(AQUI, nombre), encoding="utf-8") as f:
            _CACHE[nombre] = np.array(json.load(f)["pesos"], dtype=float)
    return _CACHE[nombre]


def _red_mty():
    if "mty" not in _CACHE:
        import calles
        _CACHE["mty"] = calles.RedVial(calles.zona_para("Monterrey · Centro"), avisar=_silencio)
    return _CACHE["mty"]


def _calle(nivel, semilla, **kw):
    import calles
    return calles.PistaCalle(_red_mty(), nivel, semilla, superficie="pavimento", **kw)


def _correr(pista, pesos, n=3, semilla=0, con_puntos=True, **kw):
    sim = F.Simulador(pista, np.repeat(np.atleast_2d(pesos), n, 0), semilla_ruido=semilla,
                      ruido_por_moto=True, **kw)
    pc = PC.PuntosControl(pista).enganchar(sim) if con_puntos else None
    while not sim.terminado:
        sim.paso()
    return sim, pc


class PistaRecta:

    def __init__(self, largo=300.0, loma=None, semilla=1):
        self.xs = np.arange(0.0, largo, 0.1)
        self.hs = np.zeros_like(self.xs)
        if loma is not None:
            x0, alto, ancho = loma
            self.hs = alto * np.exp(-0.5 * ((self.xs - x0) / ancho) ** 2)
        self.kappa = np.zeros_like(self.xs)
        self.rumbo = np.zeros_like(self.xs)
        self.mapa_x = self.xs.copy()
        self.mapa_y = np.zeros_like(self.xs)
        self.salida, self.meta, self.semilla = 6.0, largo - 15.0, semilla
        self.longitud = self.xs[-1]

    def altura(self, x):
        return np.interp(x, self.xs, self.hs)

    def indice(self, x):
        return np.clip((np.asarray(x) * 10).astype(np.int64), 0, len(self.xs) - 1)


class SimFalso:

    def __init__(self, pista, n, v=10.0, con_observadores=True):
        self.pista, self.n_total = pista, n
        self.ids = np.arange(n)
        self.px = np.full(n, pista.salida)
        self.lat = np.full(n, C.LAT_CARRIL)
        self.psi = np.zeros(n)
        self.phi = np.zeros(n)
        self.derrape = np.zeros(n)
        self.vx = np.full(n, v)
        self.vy = np.zeros(n)
        self.th = np.zeros(n)
        self.t = 0.0
        self.reintentos = np.zeros(n, dtype=np.int64)
        self.motivo = np.zeros(n, dtype=np.int64)
        self.terminado = False
        if con_observadores:
            self.observadores = []

    def llegaron(self):
        return self.motivo == F.META

    def paso(self):
        self.px = self.px + self.vx * C.DT_CONTROL
        self.t += C.DT_CONTROL
        self.motivo[self.ids[self.px >= self.pista.meta]] = F.META
        if getattr(self, "regreso", None):
            self.regreso(self)
            self.regreso = None
        for o in getattr(self, "observadores", []):
            o(self)


def _distancias_de_fijado(pista, pc, sim, hasta):
    d = {}
    while sim.px[0] < hasta:
        antes = pc.fijado[0]
        sim.paso()
        if pc.fijado[0] and not antes:
            d[int(pc.siguiente[0])] = float(pc.X[pc.siguiente[0]] - sim.px[0])
    return d


def test_determinismo_y_colocacion():
    for s in range(20):
        for nivel in (1, 2, 5, 8):
            p = terreno.Pista(nivel, s)
            a, b = PC.PuntosControl(p), PC.PuntosControl(terreno.Pista(nivel, s))
            assert np.array_equal(a.X, b.X) and np.array_equal(a.lado, b.lado)
            assert np.array_equal(a.altura, b.altura) and np.array_equal(a.lateral, b.lateral)
            assert a.K >= 3
            assert a.X[0] >= p.salida + PC.MARGEN_SALIDA - 1e-9
            assert a.X[-1] <= p.meta - PC.MARGEN_META + 1e-9
            assert np.all(np.diff(a.X) > 35.0)
            assert set(np.unique(a.lado)) <= {-1, 1}
            assert np.all((a.lateral >= 2.5) & (a.lateral <= 3.5))
            assert np.all((a.altura >= 1.0) & (a.altura <= 1.5))
    assert not np.array_equal(PC.PuntosControl(terreno.Pista(2, 1)).X,
                              PC.PuntosControl(terreno.Pista(2, 2)).X)


def test_separacion_en_calles():
    seps = []
    for s in range(8):
        p = _calle(3, s)
        pc = PC.PuntosControl(p)
        seps += np.diff(pc.X).tolist()
        assert pc.K >= 3 and pc.X[0] > p.salida and pc.X[-1] < p.meta
    seps = np.array(seps)
    assert 60.0 <= np.median(seps) <= 150.0, np.median(seps)
    assert seps.min() > 40.0 and seps.max() < 200.0


def test_pistas_bit_a_bit_iguales():
    estado = np.random.get_state()[1].copy()
    for s in range(6):
        p1 = terreno.Pista(3, s)
        PC.PuntosControl(p1)
        p2 = terreno.Pista(3, s)
        for campo in ("hs", "xs", "kappa", "rumbo", "mapa_x", "mapa_y", "mu", "rr", "rugo"):
            assert np.array_equal(getattr(p1, campo), getattr(p2, campo)), campo
        c1 = _calle(2, s)
        PC.PuntosControl(c1)
        c2 = _calle(2, s)
        for campo in ("hs", "xs", "kappa", "rumbo", "mapa_x", "mapa_y"):
            assert np.array_equal(getattr(c1, campo), getattr(c2, campo)), campo
    assert np.array_equal(np.random.get_state()[1], estado)


def test_circuito_tiene_punto_en_b():
    vistos = 0
    for s in range(6):
        p = _calle(3, 40 + s, circuito="otra")
        if p.x_b is None:
            continue
        vistos += 1
        pc = PC.PuntosControl(p)
        assert pc.es_b.sum() == 1
        kb = int(np.flatnonzero(pc.es_b)[0])
        assert abs(pc.X[kb] - p.x_b) < 1e-9
        assert 0 < kb < pc.K - 1
        sim, pc = _correr(p, _pesos("mejor_moto_ciudad.json"), n=2, semilla=s)
        limpias = sim.llegadas_limpias()
        assert np.all(pc.registrados[limpias].all(1)), pc.resumen()
        assert np.array_equal(PC.exitosas(sim)[limpias], np.ones(limpias.sum(), bool))
    assert vistos >= 3


def test_misma_aptitud_con_y_sin_puntos():
    rng = np.random.default_rng(0)
    w = _pesos("mejor_moto.json")
    pob = w[None] + rng.normal(0, 0.05, (12, w.size))
    wc = _pesos("mejor_moto_ciudad.json")
    pobc = wc[None] + rng.normal(0, 0.05, (12, wc.size))
    for pista, pesos in ((terreno.Pista(2, 3), pob), (terreno.Pista(6, 4), pob),
                         (_calle(3, 5), pobc)):
        res = []
        for con in (False, True):
            sim = F.Simulador(pista, pesos, semilla_ruido=7)
            if con:
                PC.PuntosControl(pista).enganchar(sim)
            while not sim.terminado:
                sim.paso()
            res.append((sim.aptitud(), sim.motivo.copy(), sim.t_fin.copy(), sim.reintentos.copy()))
        for x, y in zip(*res):
            assert np.array_equal(x, y)


def tabla_campeona(n_motos=3):
    if ("tabla", n_motos) in _CACHE:
        return _CACHE[("tabla", n_motos)]
    filas = _CACHE[("tabla", n_motos)] = []
    wt, wc = _pesos("mejor_moto.json"), _pesos("mejor_moto_ciudad.json")
    casos = [("terreno n2", terreno.Pista(2, s), wt, s) for s in range(N_PISTAS)]
    casos += [("Monterrey n2", _calle(2, s), wc, s) for s in range(N_PISTAS)]
    for nombre, p, w, s in casos:
        sim, pc = _correr(p, w, n=n_motos, semilla=s)
        limpias = sim.llegadas_limpias()
        filas.append({"pista": f"{nombre} s{s}", "K": pc.K, "llegan": int(sim.llegaron().sum()),
                      "limpias": int(limpias.sum()),
                      "limpias_todos": int(pc.registrados[limpias].all(1).sum()),
                      "registros": int(pc.registrados.sum()), "fallos": int(pc.fallados.sum()),
                      "exitosas": int(PC.exitosas(sim).sum()), "n": n_motos})
    return filas


def test_campeona_registra_todos_si_llega_limpia():
    filas = tabla_campeona()
    for f in filas:
        assert f["limpias_todos"] == f["limpias"], f
    assert sum(f["limpias"] for f in filas) >= len(filas)


def test_orden_obligatorio_y_moto_fuera_o_caida():
    p = PistaRecta()
    sim = SimFalso(p, 3)
    pc = PC.PuntosControl(p).enganchar(sim)
    K = pc.K
    while sim.px[0] < p.meta:
        x = sim.px
        sim.lat[1] = 2.6 if abs(x[1] - pc.X[0]) < 1.0 else C.LAT_CARRIL
        sim.phi[2] = 1.3 if abs(x[2] - pc.X[1]) < 1.0 else 0.0
        sim.paso()
    assert pc.registrados[0].all() and not pc.fallados[0].any()
    assert np.all(np.isfinite(pc.tiempos[0])) and np.all(np.diff(pc.tiempos[0]) > 0)
    assert not pc.registrados[1].any() and pc.fallados[1].all()
    assert pc.registrados[2, 0] and not pc.registrados[2, 1:].any() and pc.fallados[2, 1:].all()
    ex = PC.exitosas(sim)
    assert ex.tolist() == [True, False, False]
    r = pc.resumen()
    assert r["motos"][0]["pasados"] == K and r["motos"][0]["exitosa"]
    assert r["motos"][2]["detalles"][1]["estado"] == "fallado"
    t_esperado = (pc.X[0] - p.salida) / 10.0
    assert abs(pc.tiempos[0, 0] - t_esperado) < 1e-6


def test_moto_real_que_se_sale_no_registra_los_siguientes():
    p = _calle(2, 3)
    w = _pesos("mejor_moto_ciudad.json")
    capas = R.desempacar(np.atleast_2d(w), C.CAPAS)
    pc_ref = PC.PuntosControl(p)
    x_salir = pc_ref.X[0] + 8.0

    def ctrl(obs, sim):
        u = R.adelante([(W[sim.ids], b[sim.ids]) for W, b in capas], obs)
        u[sim.px > x_salir, 2] = 1.0
        return u
    sim = F.Simulador(p, None, semilla_ruido=0, controlador=ctrl, n=1, max_reintentos=0)
    pc = PC.PuntosControl(p).enganchar(sim)
    while not sim.terminado:
        sim.paso()
    assert sim.motivo[0] in (F.FUERA, F.CAIDA)
    assert pc.registrados[0, 0] and not pc.registrados[0, 1:].any()
    assert not PC.exitosas(sim)[0]


def test_linea_de_vista_loma_tapa_el_haz():
    libre = PistaRecta()
    pc0 = PC.PuntosControl(libre)
    x1 = pc0.X[1]
    assert _distancias_de_fijado(libre, pc0, _enganchar(pc0, libre), x1 + 1)[1] > 28.0
    chica = PistaRecta(loma=(x1 - 15.0, 0.3, 2.0))
    pc1 = PC.PuntosControl(chica)
    assert _distancias_de_fijado(chica, pc1, _enganchar(pc1, chica), x1 + 1)[1] > 28.0
    loma = PistaRecta(loma=(x1 - 12.0, 5.0, 2.0))
    pc2 = PC.PuntosControl(loma)
    sim = _enganchar(pc2, loma)
    d = _distancias_de_fijado(loma, pc2, sim, x1 + 1)
    assert d[1] < 14.0, d
    assert pc2.registrados[0, :2].all()


def _enganchar(pc, pista):
    sim = SimFalso(pista, 1)
    pc.enganchar(sim)
    return sim


def test_cono_moto_de_reversa_no_fija():
    p = PistaRecta()
    sim = SimFalso(p, 2)
    pc = PC.PuntosControl(p).enganchar(sim)
    sim.psi[1] = np.pi
    while sim.px[0] < pc.X[0] + 1:
        sim.paso()
    assert pc.registrados[0, 0] and pc.fallados[1, 0]


def test_haces_para_dibujar():
    p = PistaRecta()
    sim = SimFalso(p, 2)
    pc = PC.PuntosControl(p).enganchar(sim)
    while sim.px[0] < pc.X[0] - 15:
        sim.paso()
    h = pc.haces
    assert {i for i, _, _ in h} == {0, 1}
    assert all(k == 0 and 0 < a <= 1 for _, k, a in h)
    assert all(0 <= j < 3 for _, _, j, _ in pc.haces_detalle)


def test_rebobinado_deshace_y_vuelve_a_registrar():
    p = _calle(2, 3)
    w = _pesos("mejor_moto_ciudad.json")
    capas = R.desempacar(np.atleast_2d(w), C.CAPAS)
    pc_ref = PC.PuntosControl(p)
    x_err = pc_ref.X[1] + 4.0

    def ctrl(obs, sim):
        u = R.adelante([(W[sim.ids], b[sim.ids]) for W, b in capas], obs)
        error = (sim.px > x_err) & (sim.reintentos[sim.ids] == 0)
        u[error, 2] = 1.0
        return u
    sim = F.Simulador(p, None, semilla_ruido=0, controlador=ctrl, n=1)
    pc = PC.PuntosControl(p).enganchar(sim)
    t_primero, deshecho = None, False
    while not sim.terminado:
        sim.paso()
        if pc.registrados[0, 1] and t_primero is None:
            t_primero = pc.tiempos[0, 1]
        if t_primero is not None and not pc.registrados[0, 1]:
            deshecho = True
            assert not pc.fallados[0, 1] and np.isnan(pc.tiempos[0, 1])
    assert sim.reintentos[0] == 1 and len(sim.eventos) == 1
    assert sim.eventos[0][2] < pc.X[1]
    assert deshecho
    assert pc.registrados[0, 1] and pc.tiempos[0, 1] > t_primero
    assert pc.registrados[0, 0] and pc.tiempos[0, 0] < t_primero
    if sim.motivo[0] == F.META:
        assert pc.registrados[0].all() and PC.exitosas(sim)[0]


def test_compatibilidad_sin_observadores():
    p = PistaRecta()
    sim = SimFalso(p, 2, con_observadores=False)
    pc = PC.PuntosControl(p).enganchar(sim)
    assert sim.puntos_control is pc
    hecho = False
    while sim.px[0] < p.meta:
        if not hecho and sim.px[1] > pc.X[1] + 3.0:
            hecho = True

            def regreso(sm):
                sm.px[1] = pc.X[1] - 20.0
                sm.reintentos[1] += 1
            assert pc.registrados[1, 1]
            sim.regreso = regreso
            sim.paso()
            assert pc.registrados[1, 0] and not pc.registrados[1, 1:].any()
            assert pc.siguiente[1] == 1
            continue
        sim.paso()
    assert hecho and pc.registrados.all()


def test_costo_por_paso_80_motos():
    us = medir_costo()
    assert us < 1500.0, us


def medir_costo(n=80, pasos=450):
    w = _pesos("mejor_moto.json")
    pob = w[None] + np.random.default_rng(1).normal(0, 0.05, (n, w.size))
    p = terreno.Pista(2, 7)
    sim = F.Simulador(p, pob, semilla_ruido=3)
    pc = PC.PuntosControl(p).enganchar(sim)
    sim.observadores.remove(pc)
    sim.observadores.append(type("Reg", (), {"al_regresar": lambda s, *a: pc.al_regresar(*a),
                                             "__call__": lambda s, sim: None})())
    tt, k = 0.0, 0
    while not sim.terminado and k < pasos:
        sim.paso()
        t0 = time.perf_counter()
        pc.observar(sim)
        tt += time.perf_counter() - t0
        k += 1
    return tt / k * 1e6


if __name__ == "__main__":
    import inspect
    pruebas = [(n, f) for n, f in sorted(globals().items())
               if n.startswith("test_") and inspect.isfunction(f)]
    fallas = 0
    for n, f in pruebas:
        t0 = time.time()
        try:
            f()
            print(f"OK    {n}  ({time.time() - t0:.1f} s)")
        except Exception as e:
            fallas += 1
            print(f"FALLA {n}: {type(e).__name__}: {e}")
    print("\nCampeona (3 motos con ruido propio por pista):")
    print(f"{'pista':<18}{'K':>3}{'llegan':>8}{'limpias':>9}{'limpias c/todos':>17}"
          f"{'registros':>11}{'fallos':>8}{'exitosas':>10}")
    for r in tabla_campeona():
        print(f"{r['pista']:<18}{r['K']:>3}{r['llegan']:>6}/{r['n']}{r['limpias']:>7}/{r['n']}"
              f"{r['limpias_todos']:>15}/{r['limpias']}{r['registros']:>11}{r['fallos']:>8}"
              f"{r['exitosas']:>8}/{r['n']}")
    print(f"\nCosto del observador: {medir_costo():.0f} µs/paso con 80 motos")
    print(f"\n{len(pruebas) - fallas}/{len(pruebas)} pruebas OK")
    sys.exit(1 if fallas else 0)
