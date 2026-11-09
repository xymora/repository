import os
import shutil
import sys
import tempfile
import unittest

import numpy as np

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
for _p in (RAIZ, AQUI):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import calles
import config as C
from terreno import DX, M, MU, NOMBRES_MAT
from test_circuito import (_Config, comparar_con_respaldo, _igual, _saltar, limite_kappa, recorrer, red_mty, red_z20,
                           redes, requiere_circuito, respaldo_pistas, _pesos)

OBSTACULOS = {"rocas", "troncos", "escalones", "zanja", "rampa"}
MATERIALES_CALLE = {"asfalto", "tierra", "grava"}


def requiere_irregular():
    import superficies
    if "irregular" not in superficies.SUPERFICIES:
        _saltar("aún no existe SUPERFICIES['irregular']")


def pista(red, nivel, semilla, sup, circuito="no"):
    kw = {"circuito": circuito} if circuito != "no" else {}
    if circuito != "no":
        requiere_circuito()
    return calles.PistaCalle(red, nivel, semilla, superficie=sup, **kw)


def _irregulares():
    out = []
    for nombre, red in redes():
        for nivel in range(1, 9):
            for sem in (nivel, 40 + nivel):
                out.append((f"{nombre}/N{nivel}/s{sem}", nivel, pista(red, nivel, sem, "irregular")))
    return out


def test_superficies_en_orden():
    requiere_irregular()
    import superficies
    assert list(superficies.SUPERFICIES) == ["pavimento", "irregular", "variado"]
    for v in superficies.SUPERFICIES.values():
        assert isinstance(v, str) and v


def test_irregular_continua_sin_obstaculos_y_con_agarre():
    requiere_irregular()
    malos = []
    n3 = int(round(3 / DX))
    for et, nivel, p in _irregulares():
        n = len(p.xs)
        for campo in ("hs", "mat", "mu", "rr", "rugo", "kappa"):
            v = getattr(p, campo)
            if len(v) != n or not np.isfinite(np.asarray(v, float)).all():
                malos.append(f"{et}: {campo} de largo {len(v)} != {n} o no finito")
        salto = np.abs(np.diff(p.hs))
        if salto.max() > 0.05:
            i = int(np.argmax(salto))
            malos.append(f"{et}: salto de altura {salto[i] * 100:.1f} cm en x={p.xs[i]:.1f} m")
        rasgos = {s[2] for s in p.secciones}
        if rasgos & OBSTACULOS:
            malos.append(f"{et}: aparecen obstáculos {sorted(rasgos & OBSTACULOS)}")
        mats = {NOMBRES_MAT[m] for m in np.unique(p.mat)}
        if not mats <= MATERIALES_CALLE:
            malos.append(f"{et}: materiales que no son de calle {sorted(mats - MATERIALES_CALLE)}")
        if not np.array_equal(p.mu, MU[p.mat]):
            malos.append(f"{et}: mu no corresponde a mat")
        if n > n3:
            pend = np.abs(p.hs[n3:] - p.hs[:-n3]) / 3.0
            mu_tramo = np.maximum(p.mu[n3:], p.mu[:-n3])
            exceso = pend - 0.5 * mu_tramo
            if exceso.max() > 1e-9:
                i = int(np.argmax(exceso))
                malos.append(f"{et}: pendiente {pend[i]:.2f} > μ/2={0.5 * mu_tramo[i]:.2f} en x={p.xs[i]:.0f} m")
        i_sal, i_meta = int((p.salida + 5) / DX), int((p.meta - 5) / DX)
        if np.ptp(p.hs[:i_sal]) > 1e-9 or np.ptp(p.hs[i_meta:]) > 1e-9:
            malos.append(f"{et}: salida o meta no son planas")
        if (p.mat[:i_sal] != M["asfalto"]).any() or (p.mat[i_meta:] != M["asfalto"]).any():
            malos.append(f"{et}: salida o meta no son de asfalto")
        exceso_k = np.abs(p.kappa) - limite_kappa(p)
        if exceso_k.max() > 1e-9 and (np.abs(p.kappa) > limite_kappa(p) + 1e-9)[p.mat != M["asfalto"]].any():
            i = int(np.argmax(exceso_k))
            malos.append(f"{et}: material {NOMBRES_MAT[p.mat[i]]} no aguanta |kappa|={abs(p.kappa[i]):.3f} "
                         f"en x={p.xs[i]:.0f} m")
        if not np.allclose(p.altura(p.xs), p.hs):
            malos.append(f"{et}: altura(xs) != hs")
        if nivel >= 2 and np.ptp(p.hs) < 0.05:
            malos.append(f"{et}: casi plano (desnivel {np.ptp(p.hs):.3f} m): no hay relieve")
    assert not malos, "\n".join(malos[:30])


def test_irregular_tiene_relieve_de_terreno_y_crece_con_nivel():
    requiere_irregular()
    red = red_mty()
    rasgos_vistos, ptp = set(), {}
    for nivel in range(1, 9):
        vals = []
        for sem in range(6):
            p = pista(red, nivel, 300 + sem, "irregular")
            rasgos_vistos |= {s[2] for s in p.secciones}
            vals.append(np.abs(np.diff(p.hs)).sum() / max(p.longitud, 1.0))
        ptp[nivel] = float(np.mean(vals))
    print(f"\n  subida+bajada por metro según nivel: { {k: round(v, 4) for k, v in ptp.items()} }")
    print(f"  rasgos vistos: {sorted(rasgos_vistos)}")
    assert rasgos_vistos & {"colinas", "colinas_suaves", "baches", "pendiente"}, rasgos_vistos
    assert ptp[8] > ptp[1], "el relieve no crece con el nivel"


def test_irregular_determinista_y_distinto_de_variado():
    requiere_irregular()
    red = red_mty()
    a, b = pista(red, 5, 9, "irregular"), pista(red, 5, 9, "irregular")
    for campo in ("hs", "mat", "rugo", "kappa"):
        assert _igual(getattr(a, campo), getattr(b, campo)), campo
    assert a.secciones == b.secciones
    v = pista(red, 5, 9, "variado")
    assert _igual(a.kappa, v.kappa), "la superficie no debe cambiar la ruta"
    assert not _igual(a.hs, v.hs)
    assert a.resumen()


def test_irregular_en_circuito():
    requiere_irregular()
    requiere_circuito()
    malos = []
    for nombre, red in redes():
        for vuelta in ("misma", "otra"):
            for nivel in (2, 6):
                p = pista(red, nivel, 70 + nivel, "irregular", vuelta)
                et = f"{nombre}/{vuelta}/N{nivel}"
                if np.abs(np.diff(p.hs)).max() > 0.05:
                    malos.append(f"{et}: salto de altura")
                if (np.abs(p.kappa) - limite_kappa(p)).max() > 1e-9:
                    malos.append(f"{et}: |kappa| supera el agarre")
                if p.x_b is None:
                    malos.append(f"{et}: sin x_b")
    assert not malos, "\n".join(malos)


def test_variado_bit_a_bit_contra_respaldo_v11():
    requiere_circuito()
    difs, n_val, n_inv = comparar_con_respaldo(
        ("variado",), ("hs", "mat", "rugo", "mu", "mu_min", "secciones", "kappa", "mapa_x"), {"circuito": "no"})
    assert n_val >= 5, f"muy pocas pistas variado válidas en v11 ({n_val})"
    assert not difs, "variado difiere del v11: " + ", ".join(difs)


def test_simulador_sin_nan_en_circuito_irregular_nivel8():
    requiere_irregular()
    requiere_circuito()
    import fisica as F
    import red as R
    for nombre, red in redes():
        p = pista(red, 8, 2026, "irregular", "otra")
        w = R.aleatorios(10, C.CAPAS, np.random.default_rng(8))
        sim = F.Simulador(p, w, 3)
        pasos = 0
        while not sim.terminado and pasos < 60000:
            sim.paso()
            pasos += 1
            if pasos % 15 == 0 or sim.terminado:
                for k, v in vars(sim).items():
                    if isinstance(v, np.ndarray) and v.dtype.kind == "f":
                        assert np.isfinite(v).all(), f"{nombre}: {k} no finito en el paso {pasos}"
        assert sim.terminado, f"{nombre}: no terminó en {pasos} pasos"
        assert set(np.unique(sim.motivo)) <= set(F.MOTIVOS) - {F.VIVO}
        assert np.isfinite(sim.progreso).all() and (sim.progreso <= p.longitud + 1).all()


def _requiere_plan():
    import evolucion as E
    if not hasattr(C, "PLAN_AUTOMATICO") or not hasattr(C, "ETAPAS_CALLES"):
        _saltar("aún no existen C.PLAN_AUTOMATICO / C.ETAPAS_CALLES")
    return E


def _entrenador(E, d, continuar, semilla=1, modo="ciudad", n=6):
    return E.Entrenador(n, continuar=continuar, semilla=semilla, modo=modo,
                        red_vial=red_mty() if modo == "ciudad" else None, dir_datos=d)


def test_checkpoint_ciudad_unico_para_toda_superficie_y_circuito():
    import evolucion as E
    _requiere_plan()
    with tempfile.TemporaryDirectory() as d:
        esperado = os.path.join(d, "mejor_moto_ciudad.json")
        for sup in ("pavimento", "irregular", "variado"):
            for circ in ("no", "misma", "otra"):
                with _Config(CALLES_SUPERFICIE=sup, CALLES_CIRCUITO=circ):
                    assert E.ruta("mejor_moto.json", "ciudad", d) == esperado, (sup, circ)
                    assert E.ruta("mejor_moto.json", "ciudad", d, sup) == esperado, (sup, circ)
                    assert E.ruta("poblacion.npz", "terreno", d) == os.path.join(d, "poblacion.npz")


def test_plan_etapas_contrato():
    _requiere_plan()
    assert C.PLAN_AUTOMATICO is True
    assert tuple(map(tuple, C.ETAPAS_CALLES)) == (("pavimento", "no"), ("pavimento", "circuito"),
                                                  ("irregular", "mixto"), ("variado", "mixto"))


def test_generacion_continua_y_etapa_persiste():
    E = _requiere_plan()
    with tempfile.TemporaryDirectory() as d:
        e = _entrenador(E, d, False)
        assert hasattr(e, "etapa"), "Entrenador sin atributo etapa"
        assert e.etapa == 0 and e.generacion == 1
        e.generacion, e.nivel, e.etapa = 41, 3, 2
        e._guardar_poblacion()
        with np.load(os.path.join(d, "poblacion_ciudad.npz")) as z:
            assert "etapa" in z.files and int(z["etapa"]) == 2
        e2 = _entrenador(E, d, True, semilla=99)
        assert (e2.generacion, e2.nivel, e2.etapa) == (42, 3, 2)
        for sup, circ in (("variado", "otra"), ("pavimento", "no"), ("irregular", "misma")):
            with _Config(CALLES_SUPERFICIE=sup, CALLES_CIRCUITO=circ):
                e3 = _entrenador(E, d, True, semilla=5)
            assert e3.generacion == 42, (sup, circ, e3.generacion)
        for auto, sup, circ in ((False, "variado", "otra"), (False, "pavimento", "no"), (True, None, None)):
            e2.fijar_etapa(auto, sup, circ)
            assert e2.generacion == 42 and e2.nivel == 3, (auto, sup, circ, e2.generacion, e2.nivel)
        with _Config(PLAN_AUTOMATICO=False, CALLES_SUPERFICIE="irregular", CALLES_CIRCUITO="misma"):
            e4 = _entrenador(E, d, True, semilla=6)
        assert e4.generacion == 42 and e4.superficie == "irregular", (e4.generacion, e4.superficie)


def test_graduacion_de_etapa_no_reinicia_generacion():
    E = _requiere_plan()
    with tempfile.TemporaryDirectory() as d, _Config(PLAN_AUTOMATICO=True, VALIDAR_CAMPEONA=False):
        e = _entrenador(E, d, False)
        e.generacion, e.nivel, e.racha, e.etapa = 120, C.NIVEL_MAX, C.RACHA_PARA_SUBIR - 1, 1
        e._aplicar_etapa()
        e.aptitudes[:] = np.linspace(1, 2, e.n)
        e.llegadas[:] = True
        e.limpias[:] = True
        r = e._evolucionar()
        assert r.get("etapa_nueva") == 2, r
        assert (e.etapa, e.nivel, e.generacion) == (2, 1, 121), (e.etapa, e.nivel, e.generacion)
        assert e.superficie == C.ETAPAS_CALLES[2][0]
        with np.load(os.path.join(d, "poblacion_ciudad.npz")) as z:
            assert int(z["etapa"]) == 2 and int(z["generacion"]) == 120 and int(z["nivel"]) == 1
        e2 = _entrenador(E, d, True)
        assert (e2.etapa, e2.nivel, e2.generacion) == (2, 1, 121)
        if C.PISTAS_POR_GENERACION >= 2:
            rep = getattr(e2.pistas[-1], "repaso", None)
            assert rep is not None and 0 <= rep < 2, rep


def test_ciudad_etapa_mixta_serie_igual_a_paralelo():
    E = _requiere_plan()
    res = []
    with _Config(PLAN_AUTOMATICO=True, VALIDAR_CAMPEONA=False):
        for procesos in (1, 2):
            with tempfile.TemporaryDirectory() as d:
                e = _entrenador(E, d, False, semilla=21, n=8)
                e.procesos = procesos
                e.etapa = 2
                e._aplicar_etapa()
                e._preparar_generacion()
                try:
                    r = e.correr_generacion()
                finally:
                    if hasattr(e, "cerrar"):
                        e.cerrar()
                    elif getattr(e, "_pool", None) is not None:
                        e._pool.shutdown(wait=True)
                res.append((r["mejor"], r["promedio"], e.pob.copy(),
                            [(p.superficie, getattr(p, "circuito", None)) for p in e.pistas]))
    assert res[0][0] == res[1][0] and res[0][1] == res[1][1], (res[0][:2], res[1][:2])
    assert np.array_equal(res[0][2], res[1][2])


def test_terreno_a_calles_continua_la_generacion():
    E = _requiere_plan()
    with tempfile.TemporaryDirectory() as d:
        t = _entrenador(E, d, False, modo="terreno")
        t.generacion, t.nivel = 77, 8
        t._guardar_poblacion()
        c = _entrenador(E, d, True)
        assert c.generacion == 78, f"al pasar de terrenos a calles la generación es {c.generacion} (esperaba 78)"


def test_checkpoint_v2_real_sin_etapa_carga_en_etapa0_gen968():
    E = _requiere_plan()
    real = os.path.join(RAIZ, "poblacion_ciudad.npz")
    if not os.path.isfile(real):
        _saltar("no hay poblacion_ciudad.npz del usuario")
    with np.load(real) as z:
        if "etapa" in z.files:
            _saltar("el checkpoint real ya tiene etapa (alguien lo reescribió)")
        gen_real = int(z["generacion"])
    with tempfile.TemporaryDirectory() as d:
        shutil.copy2(real, os.path.join(d, "poblacion_ciudad.npz"))
        e = _entrenador(E, d, True, n=80)
        assert e.etapa == 0
        assert e.generacion == gen_real + 1 == 968, e.generacion
        assert e.nivel == 8


def test_factibilidad_campeona_terrenos_en_irregular():
    requiere_irregular()
    import fisica as F
    w = _pesos("mejor_moto.json")
    lineas, total, llegaron = [], 0, 0
    for nombre, red in redes():
        for nivel in (1, 2):
            for j in range(3):
                p = pista(red, nivel, 900 + 10 * nivel + j, "irregular")
                sim, ok = recorrer(p, w, 3, 11 + j)
                total += 3
                llegaron += ok
                motivos = sorted({F.MOTIVOS[int(m)] for m in sim.motivo})
                lineas.append(f"{nombre} N{nivel} {p.longitud:4.0f} m: {ok}/3 (progreso medio "
                              f"{np.mean(sim.progreso):.0f} m; {', '.join(motivos)})")
    print("\n  campeona de terrenos en calles irregulares:\n   " + "\n   ".join(lineas)
          + f"\n   total {llegaron}/{total}")
    assert llegaron > total / 2, f"sólo {llegaron}/{total}:\n" + "\n".join(lineas)


if __name__ == "__main__":
    import time
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    pruebas = [(k, v) for k, v in list(globals().items())
               if k.startswith("test_") and callable(v) and getattr(v, "__module__", "") == "__main__"]
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
