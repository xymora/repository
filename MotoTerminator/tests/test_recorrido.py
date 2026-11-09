import json
import os
import shutil
import sys
import tempfile
import time

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
DONT_WAIT = 2


def huella():
    out = {}
    for f in ARCHIVOS_USUARIO:
        p = os.path.join(RAIZ, f)
        out[f] = (os.path.getmtime(p), os.path.getsize(p)) if os.path.exists(p) else None
    return out


def rec():
    try:
        import recorrido
    except ImportError as ex:
        pytest.skip(f"aún no existe recorrido.py: {ex!r}")
    for k in ("candidatos", "preevaluar", "armar_pista"):
        if not hasattr(recorrido, k):
            pytest.skip(f"recorrido.{k} aún no existe")
    return recorrido


def pesos_de(archivo):
    p = os.path.join(RAIZ, archivo)
    if not os.path.exists(p):
        pytest.skip(f"no hay {archivo}")
    with open(p, encoding="utf-8") as f:
        d = json.load(f)
    if tuple(d["capas"]) != tuple(C.CAPAS):
        pytest.skip(f"{archivo} es de otra arquitectura")
    return np.array(d["pesos"], float), d


@pytest.fixture
def tmp():
    d = tempfile.mkdtemp(prefix="mt_qa12_rec_")
    antes = huella()
    yield d
    shutil.rmtree(d, ignore_errors=True)
    assert huella() == antes, "la prueba modificó archivos reales del usuario"


def _salon(tmp, campeones):
    d = {"formato": 1, "capas": list(C.CAPAS), "modo": "terreno", "campeones": campeones}
    with open(os.path.join(tmp, "campeones_terreno.json"), "w", encoding="utf-8") as f:
        json.dump(d, f)


def _campeon(pesos, gen, nivel=8, aptitud=300.0, limpias=3):
    return {"generacion": gen, "modo": "terreno", "etapa": 0, "nivel": nivel,
            "aptitud": aptitud, "limpias": limpias, "llegadas_limpias": limpias,
            "pesos": [float(w) for w in pesos]}


def test_candidatos_salon_mas_mejor_moto_sin_repetir(tmp):
    R = rec()
    w, d = pesos_de("mejor_moto.json")
    shutil.copy2(os.path.join(RAIZ, "mejor_moto.json"), os.path.join(tmp, "mejor_moto.json"))
    malo = np.zeros_like(w)
    _salon(tmp, [_campeon(malo, 900), _campeon(w, int(d["generacion"]))])
    cands = R.candidatos("terreno", tmp)
    assert len(cands) == 2, f"se esperaban 2 candidatas sin repetir, hay {len(cands)}"
    gens = sorted(int(c["generacion"]) for c in cands)
    assert gens == sorted([900, int(d["generacion"])])


def test_elige_la_que_mejor_recorre_no_la_de_mas_generacion(tmp):
    R = rec()
    w, d = pesos_de("mejor_moto.json")
    malo = np.zeros_like(w)
    _salon(tmp, [_campeon(malo, 9999, aptitud=1e6, limpias=99),
                 _campeon(w, int(d["generacion"]), aptitud=1.0, limpias=0)])
    cands = R.candidatos("terreno", tmp)
    assert int(cands[0]["generacion"]) == 9999, "el salón de prueba no quedó en el orden esperado"
    cfg = {"modo": "terreno", "nivel": 3, "repeticiones": 1, "clima": "despejado"}
    pista = R.armar_pista(cfg, 77)
    out = R.preevaluar(cands, pista, None, [0, 1])
    assert out is not None
    i, res = out
    assert int(cands[i]["generacion"]) == int(d["generacion"]), (i, res)
    assert res[i]["progreso"] > res[1 - i]["progreso"] and res[i]["aptitud"] > res[1 - i]["aptitud"]


def test_elige_la_buena_tambien_con_clima(tmp):
    R = rec()
    try:
        import clima
    except ImportError:
        pytest.skip("aún no existe clima.py")
    if not hasattr(R, "crear_clima"):
        pytest.skip("recorrido.crear_clima aún no existe")
    w, d = pesos_de("mejor_moto.json")
    _salon(tmp, [_campeon(np.zeros_like(w), 9999, aptitud=1e6)])
    shutil.copy2(os.path.join(RAIZ, "mejor_moto.json"), os.path.join(tmp, "mejor_moto.json"))
    cands = R.candidatos("terreno", tmp)
    pista = R.armar_pista({"modo": "terreno", "nivel": 2}, 31)
    c = R.crear_clima("lluvia" if "lluvia" in clima.PRESETS else "despejado", 31)
    i, res = R.preevaluar(cands, pista, c, [0, 1])
    assert int(cands[i]["generacion"]) == int(d["generacion"]), res


def test_preevaluar_es_determinista_y_no_escribe(tmp):
    R = rec()
    w, _ = pesos_de("mejor_moto.json")
    cands = [{"pesos": w, "generacion": 1}, {"pesos": w * 0.5, "generacion": 2}]
    pista = R.armar_pista({"modo": "terreno", "nivel": 1}, 5)
    a = R.preevaluar(cands, pista, None, [3])
    b = R.preevaluar(cands, pista, None, [3])
    assert a == b
    assert os.listdir(tmp) == []


def test_preevaluar_se_puede_cancelar():
    R = rec()
    w, _ = pesos_de("mejor_moto.json")
    pista = R.armar_pista({"modo": "terreno", "nivel": 8}, 5)
    t0 = time.perf_counter()
    assert R.preevaluar([{"pesos": w}], pista, None, [0, 1, 2], lambda: True) is None
    assert time.perf_counter() - t0 < 5


@pytest.fixture
def gui(tmp, monkeypatch):
    try:
        import tkinter as tk
        raiz = tk.Tk()
    except Exception as ex:
        pytest.skip(f"sin tkinter/pantalla: {ex!r}")
    raiz.withdraw()
    import calles
    monkeypatch.setattr(calles, "ARCHIVO_SESION", os.path.join(tmp, "sesion.json"))
    import graficos
    if hasattr(graficos, "_CIELO"):
        graficos._CIELO.clear()
    import interfaz
    for k in ("messagebox",):
        if hasattr(interfaz, k):
            mb = getattr(interfaz, k)
            monkeypatch.setattr(mb, "showinfo", lambda *a, **kw: None)
            monkeypatch.setattr(mb, "showwarning", lambda *a, **kw: None)
            monkeypatch.setattr(mb, "showerror", lambda *a, **kw: None)
    e = E.Entrenador(6, continuar=False, semilla=2, dir_datos=os.path.join(tmp, "dd"),
                     guardar=False)
    app = interfaz.App(raiz, entrenador=e)
    raiz.withdraw()
    yield raiz, app, e
    try:
        e.cerrar()
        raiz.destroy()
    except Exception:
        pass
    if hasattr(graficos, "_CIELO"):
        graficos._CIELO.clear()


def bombear(raiz, segundos=0.3, hasta=None):
    t0 = time.perf_counter()
    while time.perf_counter() - t0 < segundos:
        raiz.update_idletasks()
        while raiz.tk.dooneevent(DONT_WAIT):
            pass
        if hasta is not None and hasta():
            return True
        time.sleep(0.01)
    return hasta() if hasta is not None else True


def toplevels(raiz):
    import tkinter as tk
    return [w for w in raiz.winfo_children() if isinstance(w, tk.Toplevel)]


def test_gui_boton_recorrido_y_selector_clima(gui):
    raiz, app, e = gui
    assert "Recorrido" in app.b_demo.cget("text"), app.b_demo.cget("text")
    assert "Demo" not in app.b_demo.cget("text") and "demo" not in app.b_demo.cget("text")
    b = getattr(app, "b_clima", None)
    if b is None:
        pytest.skip("aún no hay selector de clima en la barra superior")
    assert "Clima" in b.cget("text")


def _abrir_dialogo(raiz, app):
    import recorrido as R
    if not hasattr(R, "DialogoRecorrido") or not hasattr(app, "iniciar_recorrido"):
        pytest.skip("aún no está el diálogo de recorrido en la interfaz")
    app.b_demo.invoke()
    bombear(raiz, 0.3)
    dlg = [w for w in toplevels(raiz) if isinstance(w, R.DialogoRecorrido)]
    assert dlg, "el botón ▶ Recorrido no abrió el diálogo"
    dlg[0].withdraw()
    return dlg[0]


def test_gui_dialogo_cancelar_reanuda_sin_cambiar_generacion(gui):
    raiz, app, e = gui
    for _ in range(3):
        app.avanzar()
    gen, pausa0, t0 = e.generacion, app.pausa, e.sim.t
    dlg = _abrir_dialogo(raiz, app)
    bombear(raiz, 0.2)
    assert e.generacion == gen
    dlg.cancelar()
    bombear(raiz, 0.3)
    assert app.pausa == pausa0, "al cancelar el recorrido no se restauró la pausa"
    assert e.generacion == gen
    app.avanzar()
    assert e.sim.t > t0 or e.generacion > gen or e.i_pista > 0, "no se reanudó el entrenamiento"


def test_gui_recorrido_completo_terreno_con_clima(gui):
    raiz, app, e = gui
    import recorrido as R
    if not hasattr(app, "iniciar_recorrido"):
        pytest.skip("aún no existe App.iniciar_recorrido")
    pesos_de("mejor_moto.json")
    for _ in range(2):
        app.avanzar()
    gen, pob, pausa0, t0 = e.generacion, e.pob.copy(), app.pausa, e.sim.t
    climas = R.presets_clima() if hasattr(R, "presets_clima") else []
    cfg = {"modo": "terreno", "nivel": 1, "repeticiones": 1,
           "clima": "lluvia" if "lluvia" in climas else "despejado"}
    app.iniciar_recorrido(cfg)
    listo = bombear(raiz, 90, hasta=lambda: bool(app.demo) and app.demo.get("sim") is not None)
    assert listo, "la pre-evaluación no terminó en 90 s"
    for _ in range(20):
        app.avanzar()
    app.dibujar()
    app.dibujar_panel(app.sim_actual())
    raiz.update_idletasks()
    textos = " ".join(str(app.panel.itemcget(i, "text")) for i in app.panel.find_all()
                      if app.panel.type(i) == "text")
    textos += " " + " ".join(str(app.vista.itemcget(i, "text")) for i in app.vista.find_all()
                             if app.vista.type(i) == "text")
    assert "Generaci" in textos, "no se muestra «Generación N» del individuo elegido"
    if getattr(C, "PUNTOS_CONTROL", False) and app.demo.get("puntos") is not None:
        assert app.vista.find_withtag("punto") or app.mapa.find_withtag("punto"),             "no se dibujan los puntos de control"
    if cfg["clima"] == "lluvia":
        assert app.vista.find_withtag("lluvia") or app.mapa.find_withtag("lluvia"),             "con lluvia no se dibujan gotas"
    assert e.sim.t == t0 and np.array_equal(e.pob, pob), "el recorrido movió el entrenamiento"
    app.alternar_demo()
    bombear(raiz, 0.3)
    for w in toplevels(raiz):
        w.destroy()
    assert not app.demo
    assert app.pausa == pausa0 and e.generacion == gen
    app.avanzar()
    assert e.sim.t > t0 or e.i_pista > 0 or e.generacion > gen


def test_gui_turbo_multinucleo(gui, monkeypatch):
    import time
    import paralelo as P
    raiz, app, e = gui
    monkeypatch.setattr(C, "PROCESOS_TURBO", 3)
    gen = e.generacion
    app.alternar_turbo()
    vio_paralelo, limite = False, time.time() + 240
    try:
        while e.generacion == gen and time.time() < limite:
            t0 = time.time()
            app.avanzar()
            assert time.time() - t0 < 1.0, "el turbo bloqueó la interfaz"
            if e.en_paralelo():
                vio_paralelo = True
                app.dibujar_turbo()
                textos = " ".join(app.vista.itemcget(i, "text") for i in app.vista.find_all()
                                  if app.vista.type(i) == "text")
                assert "procesos" in textos and "CPU" in textos, textos
            time.sleep(0.01)
        assert vio_paralelo and e.generacion == gen + 1
    finally:
        e.cerrar()
