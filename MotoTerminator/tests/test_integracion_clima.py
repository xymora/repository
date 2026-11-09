import json
import os
import shutil
import sys
import tempfile

import numpy as np
import pytest

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
if RAIZ not in sys.path:
    sys.path.insert(0, RAIZ)

import config as C
import evolucion as E

ARCHIVOS_USUARIO = ("mejor_moto.json", "mejor_moto_ciudad.json", "poblacion.npz",
                    "poblacion_ciudad.npz", "historial.csv", "historial_ciudad.csv",
                    "sesion.json", "campeones_terreno.json", "campeones_ciudad.json")


def huella():
    out = {}
    for f in ARCHIVOS_USUARIO:
        p = os.path.join(RAIZ, f)
        out[f] = (os.path.getmtime(p), os.path.getsize(p)) if os.path.exists(p) else None
    return out


def clima_mod():
    try:
        import clima
    except ImportError:
        pytest.skip("aún no existe clima.py")
    for k in ("PRESETS", "Clima", "crear", "clima_aleatorio", "preparar_pista"):
        if not hasattr(clima, k):
            pytest.skip(f"clima.{k} aún no existe")
    return clima


def requiere_config_clima():
    clima_mod()
    if not hasattr(C, "CLIMA_AUTOMATICO") or not hasattr(C, "CLIMA_MANUAL"):
        pytest.skip("config.CLIMA_AUTOMATICO / CLIMA_MANUAL aún no existen")


def requiere_campeones():
    if not hasattr(E, "cargar_campeones") or not hasattr(E, "mejor_campeon"):
        pytest.skip("evolucion.cargar_campeones / mejor_campeon aún no existen")


class Banderas:

    def __init__(self, **kw):
        self.kw, self.viejos = kw, {}

    def __enter__(self):
        for k, v in self.kw.items():
            self.viejos[k] = getattr(C, k, "<falta>")
            setattr(C, k, v)
        return self

    def __exit__(self, *exc):
        for k, v in self.viejos.items():
            if v == "<falta>":
                delattr(C, k)
            else:
                setattr(C, k, v)


@pytest.fixture
def tmp():
    d = tempfile.mkdtemp(prefix="mt_qa12_")
    antes = huella()
    yield d
    shutil.rmtree(d, ignore_errors=True)
    assert huella() == antes, "la prueba modificó archivos reales del usuario"


def es_despejado(c):
    if c is None:
        return True
    if isinstance(c, str):
        return c == "despejado"
    if getattr(c, "nombre", None) == "despejado":
        return True
    return (float(getattr(c, "lluvia", 0) or 0) == 0 and not getattr(c, "granizo", False)
            and float(getattr(c, "niebla", 0) or 0) == 0
            and float(getattr(c, "viento_medio", 0) or 0) == 0
            and float(getattr(c, "rafagas", 0) or 0) == 0
            and float(getattr(c, "charcos", 0) or 0) == 0)


def firma_clima(c):
    if c is None:
        return None
    if isinstance(c, str):
        return c
    if isinstance(c, dict):
        return tuple(sorted((k, repr(v)) for k, v in c.items()))
    campos = ("nombre", "lluvia", "granizo", "niebla", "viento_medio", "direccion_viento",
              "rafagas", "charcos", "semilla")
    return tuple(repr(getattr(c, k, None)) for k in campos)


def climas_de(e):
    clima = clima_mod()
    out = []
    for i, p in enumerate(e.pistas):
        c = getattr(p, "clima", "<sin>")
        if c == "<sin>":
            for nombre in ("climas_obj", "climas", "climas_pistas"):
                lista = getattr(e, nombre, None)
                if lista is not None:
                    c = lista[i]
                    break
        if c == "<sin>":
            spec = e._spec(i)
            cand = [x for x in spec if isinstance(x, (clima.Clima, dict))
                    or (isinstance(x, str) and x in clima.PRESETS)]
            c = cand[0] if cand else "<sin>"
        if c == "<sin>":
            pytest.skip("no se encuentra el clima de las pistas del entrenador "
                        "(pista.clima / e.climas / spec)")
        out.append(c)
    return out


def correr(e, gens):
    res = []
    for _ in range(gens):
        r = e.correr_generacion()
        res.append([r["mejor"], r["promedio"], r["llegaron"], r["terminadas_lider"], r["nivel"]])
    return np.array(res, dtype=float)


def test_clima_aleatorio_determinista_y_30_por_ciento_despejado():
    clima = clima_mod()
    for nivel in (1, 4, C.NIVEL_MAX):
        for etapa in (0, 3):
            a = [clima.clima_aleatorio(np.random.default_rng(s), nivel, etapa) for s in range(300)]
            b = [clima.clima_aleatorio(np.random.default_rng(s), nivel, etapa) for s in range(300)]
            assert [firma_clima(x) for x in a] == [firma_clima(x) for x in b], \
                "clima_aleatorio no es determinista por semilla"
            frac = np.mean([es_despejado(x) for x in a])
            assert frac >= 0.22, f"nivel {nivel} etapa {etapa}: sólo {frac:.0%} despejado"
    alto = [clima.clima_aleatorio(np.random.default_rng(s), C.NIVEL_MAX, 3) for s in range(300)]
    frac = np.mean([es_despejado(x) for x in alto])
    assert frac <= 0.6, f"nivel máximo: {frac:.0%} despejado (casi nunca hay clima)"


def test_preparar_pista_no_muta_la_original():
    clima = clima_mod()
    from terreno import Pista
    p = Pista(4, 99)
    antes = {k: np.array(getattr(p, k), copy=True) for k in ("mu", "mu_min", "rr", "rugo")
             if hasattr(p, k)}
    c = clima.crear("tormenta", 3)
    m = clima.preparar_pista(p, c)
    for k, v in antes.items():
        assert np.array_equal(getattr(p, k), v), f"preparar_pista mutó pista.{k}"
    assert m is not p
    assert np.mean(m.mu) < np.mean(p.mu), "la tormenta no reduce el agarre"


def test_clima_automatico_en_entrenamiento_es_determinista(tmp):
    requiere_config_clima()
    with Banderas(CLIMA_AUTOMATICO=True, CLIMA_MANUAL=None, PISTAS_POR_GENERACION=12):
        a = E.Entrenador(4, semilla=21, dir_datos=os.path.join(tmp, "a"), guardar=False)
        b = E.Entrenador(4, semilla=21, dir_datos=os.path.join(tmp, "b"), guardar=False)
        ca, cb = climas_de(a), climas_de(b)
    assert [firma_clima(x) for x in ca] == [firma_clima(x) for x in cb]
    assert len(ca) == 12


def test_clima_automatico_mezcla_despejado_y_clima(tmp):
    requiere_config_clima()
    with Banderas(CLIMA_AUTOMATICO=True, CLIMA_MANUAL=None, PISTAS_POR_GENERACION=40):
        e = E.Entrenador(2, semilla=5, dir_datos=tmp, guardar=False)
        e.nivel = C.NIVEL_MAX
        e._preparar_generacion()
        cs = climas_de(e)
    frac = np.mean([es_despejado(c) for c in cs])
    assert 0.1 <= frac <= 0.75, f"{frac:.0%} de pistas despejadas en nivel máximo"


def test_clima_manual_fija_todas_las_pistas(tmp):
    requiere_config_clima()
    clima = clima_mod()
    nombre = "lluvia" if "lluvia" in clima.PRESETS else sorted(clima.PRESETS)[1]
    with Banderas(CLIMA_AUTOMATICO=True, CLIMA_MANUAL=nombre, PISTAS_POR_GENERACION=6):
        e = E.Entrenador(2, semilla=8, dir_datos=tmp, guardar=False)
        cs = climas_de(e)
    for c in cs:
        n = c if isinstance(c, str) else (c.get("nombre") if isinstance(c, dict) else c.nombre)
        assert n == nombre, f"CLIMA_MANUAL={nombre} pero una pista tiene {n}"


def test_sin_clima_es_bit_a_bit_igual(tmp):
    requiere_config_clima()
    from fisica import Simulador
    import paralelo as P
    with Banderas(CLIMA_AUTOMATICO=False, CLIMA_MANUAL=None):
        e = E.Entrenador(6, semilla=4, dir_datos=tmp, guardar=False)
        pob = e.pob.copy()
        pistas = list(e.pistas)
        for c in climas_de(e):
            assert es_despejado(c)
        apt = []
        for i in range(len(pistas)):
            assert getattr(e.sim, "clima", None) is None
            while not e.sim.terminado:
                e.sim.correr(10_000)
            apt.append(P.resultados(e.sim)["aptitud"])
            e.avanzar(1)
    for i, p in enumerate(pistas):
        sim = Simulador(p, pob, semilla_ruido=p.semilla)
        while not sim.terminado:
            sim.correr(10_000)
        assert np.array_equal(apt[i], P.resultados(sim)["aptitud"]),             f"pista {i}: difiere de v12 sin clima"


@pytest.mark.parametrize("manual", [None, "tormenta_con_rafagas"])
def test_serie_igual_a_paralelo_con_clima(tmp, manual):
    requiere_config_clima()
    clima = clima_mod()
    if manual is not None and manual not in clima.PRESETS:
        pytest.skip(f"no existe el preset {manual}")
    with Banderas(CLIMA_AUTOMATICO=True, CLIMA_MANUAL=manual, PISTAS_POR_GENERACION=4):
        a = E.Entrenador(8, semilla=13, dir_datos=os.path.join(tmp, "s"), guardar=False)
        hay_clima = not all(es_despejado(c) for c in climas_de(a))
        ra = correr(a, 2)
        b = E.Entrenador(8, semilla=13, dir_datos=os.path.join(tmp, "p"), guardar=False,
                         procesos=2)
        try:
            rb = correr(b, 2)
        finally:
            b.cerrar()
    assert hay_clima or manual is None
    assert np.array_equal(ra, rb), (ra, rb)
    assert np.array_equal(a.pob, b.pob)


def _copiar_checkpoint(tmp, modo):
    suf = "_ciudad" if modo == "ciudad" else ""
    n = 0
    for base in ("poblacion{}.npz", "mejor_moto{}.json", "historial{}.csv"):
        f = base.format(suf)
        if os.path.exists(os.path.join(RAIZ, f)):
            shutil.copy2(os.path.join(RAIZ, f), os.path.join(tmp, f))
            n += 1
    if not os.path.exists(os.path.join(tmp, f"poblacion{suf}.npz")):
        pytest.skip(f"no hay poblacion{suf}.npz del usuario")
    with np.load(os.path.join(tmp, f"poblacion{suf}.npz")) as d:
        return int(d["generacion"])


def _red_local():
    import calles
    try:
        return calles.RedVial(calles.Zona("Zona 20.1217, -98.7358",
                                          (20.121666666666666, -98.73583333333333)),
                              avisar=lambda *a, **k: None)
    except Exception as ex:
        pytest.skip(f"no hay red de calles local: {ex!r}")


def test_checkpoint_real_terreno_carga_sin_bajar_generacion(tmp):
    gen = _copiar_checkpoint(tmp, "terreno")
    with Banderas(CLIMA_AUTOMATICO=True, CLIMA_MANUAL=None) if hasattr(C, "CLIMA_AUTOMATICO") \
            else Banderas():
        e = E.Entrenador(C.POBLACION, continuar=True, dir_datos=tmp, guardar=False)
    assert e.generacion == gen + 1
    with np.load(os.path.join(tmp, "poblacion.npz")) as d:
        assert np.array_equal(e.pob[0], d["pob"][0]), "la campeona no se cargó intacta"


def test_checkpoint_real_ciudad_no_baja_al_cambiar_clima_y_superficie(tmp):
    gen = _copiar_checkpoint(tmp, "ciudad")
    red = _red_local()
    e = E.Entrenador(C.POBLACION, continuar=True, modo="ciudad", red_vial=red, dir_datos=tmp,
                     guardar=False)
    assert e.generacion == gen + 1
    g0, nivel0 = e.generacion, e.nivel
    e.fijar_etapa(False, "irregular", "misma")
    e.fijar_etapa(False, "variado", "no")
    e.fijar_etapa(True)
    assert (e.generacion, e.nivel) == (g0, nivel0)
    if hasattr(C, "CLIMA_MANUAL"):
        clima = clima_mod()
        for preset in list(clima.PRESETS)[:4] + [None]:
            with Banderas(CLIMA_MANUAL=preset):
                for metodo in ("fijar_clima", "cambiar_clima"):
                    if hasattr(e, metodo):
                        getattr(e, metodo)(preset)
                e2 = E.Entrenador(C.POBLACION, continuar=True, modo="ciudad", red_vial=red,
                                  dir_datos=tmp, guardar=False)
                assert e2.generacion == gen + 1, f"clima {preset}: generación {e2.generacion}"
            assert e.generacion == g0
    e3 = E.Entrenador(C.POBLACION, continuar=True, modo="ciudad", red_vial=red, dir_datos=tmp,
                      guardar=True)
    e3._guardar_poblacion()
    with np.load(os.path.join(tmp, "poblacion_ciudad.npz")) as d:
        assert int(d["generacion"]) >= gen


def _cargar_campeones(modo, dd):
    try:
        return E.cargar_campeones(modo, dir_datos=dd)
    except TypeError:
        pytest.skip("cargar_campeones(modo) no acepta dir_datos: no se puede probar sin "
                    "tocar los archivos del usuario")


def _mejor_campeon(modo, dd):
    try:
        return E.mejor_campeon(modo, dir_datos=dd)
    except TypeError:
        pytest.skip("mejor_campeon(modo) no acepta dir_datos")


def _clave(c):
    return (c.get("etapa", 0) or 0, c.get("nivel", 0) or 0, c.get("llegadas_limpias", 0) or 0,
            c.get("aptitud", 0) or 0)


def test_salon_se_siembra_desde_mejor_moto(tmp):
    requiere_campeones()
    for modo, f in (("terreno", "mejor_moto.json"), ("ciudad", "mejor_moto_ciudad.json")):
        if not os.path.exists(os.path.join(RAIZ, f)):
            continue
        shutil.copy2(os.path.join(RAIZ, f), os.path.join(tmp, f))
        with open(os.path.join(RAIZ, f), encoding="utf-8") as fh:
            d = json.load(fh)
        lista = _cargar_campeones(modo, tmp)
        assert lista, f"{modo}: el salón no se sembró con {f}"
        gens = [int(c["generacion"]) for c in lista]
        assert int(d["generacion"]) in gens
        c = lista[gens.index(int(d["generacion"]))]
        for k in ("generacion", "modo", "etapa", "nivel", "aptitud", "llegadas_limpias", "pesos"):
            assert k in c, f"{modo}: falta {k} en el campeón"
        assert np.allclose(np.asarray(c["pesos"], float), d["pesos"])
        m = _mejor_campeon(modo, tmp)
        assert m is not None and int(m["generacion"]) == int(d["generacion"])


def test_salon_orden_tope_distintas_generaciones_y_atomico(tmp):
    requiere_campeones()
    with Banderas(PISTAS_POR_GENERACION=1, **({"CLIMA_AUTOMATICO": False, "CLIMA_MANUAL": None}
                                              if hasattr(C, "CLIMA_AUTOMATICO") else {})):
        e = E.Entrenador(4, semilla=3, dir_datos=tmp)
        for _ in range(14):
            e.correr_generacion()
    lista = _cargar_campeones("terreno", tmp)
    assert 1 <= len(lista) <= 12, len(lista)
    gens = [int(c["generacion"]) for c in lista]
    assert len(set(gens)) == len(gens), f"generaciones repetidas en el salón: {gens}"
    claves = [_clave(c) for c in lista]
    assert claves == sorted(claves, reverse=True), f"salón desordenado: {claves}"
    assert _mejor_campeon("terreno", tmp)["generacion"] == lista[0]["generacion"]
    archivos = os.listdir(tmp)
    assert "campeones_terreno.json" in archivos, archivos
    assert not [a for a in archivos if a.endswith(".tmp")], archivos
    with open(os.path.join(tmp, "campeones_terreno.json"), encoding="utf-8") as f:
        json.load(f)
    import inspect
    src = inspect.getsource(E)
    i = src.find("campeones")
    assert "_escribir_atomico" in src[i:] or "os.replace" in src[i:], \
        "el salón de la fama no parece escribirse de forma atómica"


def test_salon_escritura_atomica_ante_fallo(tmp, monkeypatch):
    requiere_campeones()
    shutil.copy2(os.path.join(RAIZ, "mejor_moto.json"), os.path.join(tmp, "mejor_moto.json"))
    with Banderas(PISTAS_POR_GENERACION=1):
        e = E.Entrenador(4, semilla=9, dir_datos=tmp, continuar=True)
        e.correr_generacion()
        arch = os.path.join(tmp, "campeones_terreno.json")
        if not os.path.exists(arch):
            pytest.skip("el salón no se escribió tras una generación")
        with open(arch, "rb") as f:
            antes = f.read()

        def falla(*a, **k):
            raise OSError("disco lleno (simulado)")
        monkeypatch.setattr(E.os, "replace", falla)
        try:
            e.correr_generacion()
        except OSError:
            pass
        monkeypatch.undo()
    with open(arch, "rb") as f:
        assert f.read() == antes, "un fallo al escribir dejó el salón dañado/cambiado"
    json.loads(antes.decode("utf-8"))


def test_clima_despejado_es_bit_a_bit_igual_a_none():
    clima = clima_mod()
    from fisica import Simulador
    from terreno import Pista
    w = np.array(json.load(open(os.path.join(RAIZ, "mejor_moto.json"), encoding="utf-8"))["pesos"])
    for nivel, s in ((2, 11), (6, 12)):
        out = []
        for c in (None, "despejado", clima.crear("despejado", s)):
            sim = Simulador(Pista(nivel, s), np.repeat(w[None], 2, 0), s, ruido_por_moto=True,
                            clima=c)
            while not sim.terminado:
                sim.correr(10_000)
            out.append(sim.aptitud())
        assert np.array_equal(out[0], out[1]) and np.array_equal(out[0], out[2])


def test_sin_aquaplaning_a_la_velocidad_minima():
    clima = clima_mod()
    if not hasattr(clima, "factor_aquaplaning"):
        pytest.skip("clima.factor_aquaplaning no existe")
    for prof in (2.0, 5.0, 8.0, 10.0):
        f = np.asarray(clima.factor_aquaplaning(np.array([30 / 3.6, 40 / 3.6]), prof))
        assert np.all(f >= 0.999), f"charco de {prof} mm a 30-40 km/h: factor {f}"


@pytest.mark.parametrize("nivel", [1, 4, 8])
def test_toda_curva_factible_a_30_kmh_con_cualquier_clima(nivel):
    clima = clima_mod()
    from terreno import Pista
    for s in range(4):
        p = Pista(nivel, 300 + s)
        kappa = np.abs(np.asarray(p.kappa, float))
        necesario = np.minimum(kappa * C.V_ESTABLE ** 2 / (0.85 * C.G), np.asarray(p.mu))
        for nombre in clima.PRESETS:
            m = clima.preparar_pista(p, clima.crear(nombre, s))
            falta = necesario - np.asarray(m.mu)
            assert falta.max() <= 1e-9, (f"{nombre} nivel {nivel} semilla {300 + s}: falta agarre "
                                         f"{falta.max():.3f} en x={p.xs[int(falta.argmax())]:.0f} m")


def test_viento_peor_caso_no_supera_al_estabilizador():
    clima = clima_mod()
    if not all(hasattr(clima, k) for k in ("RHO_AIRE", "CDA_LATERAL", "H_PRESION",
                                           "INERCIA_ALABEO")):
        pytest.skip("constantes del viento no expuestas")
    peor = 0.0
    for nombre, par in clima.PRESETS.items():
        W, r = par.get("viento_medio", 0.0), par.get("rafagas", 0.0)
        pico = W + r * (0.6 * W + 4.0) + 3 * r * (0.2 * W + 1.0) + 30 / 3.6
        f = 0.5 * clima.RHO_AIRE * clima.CDA_LATERAL * pico ** 2
        peor = max(peor, f * clima.H_PRESION / clima.INERCIA_ALABEO)
    assert peor < C.CMG_MAX, f"alabeo del viento {peor:.2f} rad/s² >= CMG_MAX {C.CMG_MAX}"


def test_puntos_control_no_cambian_el_entrenamiento(tmp):
    if not hasattr(C, "PUNTOS_CONTROL"):
        pytest.skip("config.PUNTOS_CONTROL aún no existe")
    try:
        import puntos_control
    except ImportError:
        pytest.skip("aún no existe puntos_control.py")
    extra = {"CLIMA_AUTOMATICO": True, "CLIMA_MANUAL": None} if hasattr(C, "CLIMA_AUTOMATICO") else {}
    res, pobs, resumenes = [], [], []
    for activo in (False, True):
        with Banderas(PUNTOS_CONTROL=activo, PISTAS_POR_GENERACION=3, **extra):
            e = E.Entrenador(8, semilla=17, dir_datos=os.path.join(tmp, str(activo)), guardar=False)
            r = [e.correr_generacion() for _ in range(2)]
        res.append(np.array([[x["mejor"], x["promedio"], x["llegaron"], x["terminadas_lider"]]
                             for x in r]))
        pobs.append(e.pob.copy())
        resumenes.append(r)
    assert np.array_equal(res[0], res[1]), res
    assert np.array_equal(pobs[0], pobs[1])
    assert resumenes[1][-1].get("puntos_lider") is not None, "el resumen no trae puntos_lider"
    assert resumenes[0][-1].get("puntos_lider") is None


def test_puntos_control_campeona_exitosa_si_llega_limpia():
    try:
        import puntos_control as PC
    except ImportError:
        pytest.skip("aún no existe puntos_control.py")
    from fisica import Simulador
    from terreno import Pista
    w = np.array(json.load(open(os.path.join(RAIZ, "mejor_moto.json"), encoding="utf-8"))["pesos"])
    limpias = exitosas = 0
    for nivel, s in ((2, 7001), (5, 7004), (7, 7006), (8, 7007)):
        sim = Simulador(Pista(nivel, s), np.repeat(w[None], 2, 0), s, ruido_por_moto=True)
        pc = PC.PuntosControl(sim.pista)
        pc.enganchar(sim)
        while not sim.terminado:
            sim.correr(10_000)
        lim = np.asarray(sim.llegadas_limpias(), bool)
        ex = pc.exitosas(sim)
        limpias += int(lim.sum())
        exitosas += int((lim & ex).sum())
        for i in range(2):
            reg = np.flatnonzero(pc.registrados[i])
            if len(reg):
                assert pc.X[reg].max() <= max(sim.mejor_x[i] if hasattr(sim, "mejor_x") and
                                              np.ndim(sim.mejor_x) and len(sim.mejor_x) > i
                                              else np.inf, sim.pista.meta) + 1e-6
    assert limpias > 0, "la campeona no llegó limpia en ninguna pista de prueba"
    assert exitosas == limpias, f"{limpias - exitosas} llegadas limpias sin todos los puntos"
