import os
import sys

import numpy as np
import pytest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if RAIZ not in sys.path:
    sys.path.insert(0, RAIZ)

import aceleracion as A
import config as C
import fisica as F
import red as R
import terreno as T
import validacion_fisica as V


def _trayectoria(motor, pasos=30, n=24):
    viejo = C.MOTOR_FISICA
    C.MOTOR_FISICA = motor
    try:
        w = R.aleatorios(n, C.CAPAS, np.random.default_rng(1))
        s = F.Simulador(T.Pista(8, 5), w, semilla_ruido=2, max_reintentos=10 ** 6)
        estados = []
        for _ in range(pasos):
            s.paso()
            estados.append(np.stack([s.px, s.py, s.th, s.phi, s.lat, s.vx]))
        return estados, s.motor_fisica
    finally:
        C.MOTOR_FISICA = viejo


def test_numba_igual_a_numpy_a_corto_plazo():
    if not A.hay_numba():
        pytest.skip("numba no instalado")
    a, ma = _trayectoria("numpy")
    b, mb = _trayectoria("numba")
    assert (ma, mb) == ("numpy", "numba")
    for x, y in zip(a, b):
        assert np.max(np.abs(x - y)) < 1e-9


def test_gpu_igual_a_numba():
    if A.gpu() is None:
        pytest.skip("sin GPU CUDA en esta computadora")
    a, _ = _trayectoria("numba")
    b, mb = _trayectoria("gpu")
    assert mb == "gpu"
    for x, y in zip(a, b):
        assert np.max(np.abs(x - y)) < 1e-9


def test_eleccion_segun_lo_que_haya(monkeypatch):
    monkeypatch.setattr(C, "MOTOR_FISICA", "auto")
    monkeypatch.setitem(A._CACHE, "numba", False)
    assert A.elegir(80) == "numpy" and A.elegir(10 ** 5) == "numpy"
    monkeypatch.setitem(A._CACHE, "numba", True)
    monkeypatch.setitem(A._CACHE, "gpu", None)
    assert A.elegir(80) == "numba" and A.elegir(10 ** 5) == "numba"
    monkeypatch.setitem(A._CACHE, "gpu", {"nombre": "X", "vram_total_mb": 6144, "vram_libre_mb": 5000})
    monkeypatch.setattr(A, "vram_libre_mb", lambda: 5000)
    assert A.elegir(80) == "numba"
    assert A.elegir(C.GPU_MIN_MOTOS) == "gpu"
    monkeypatch.setattr(A, "vram_libre_mb", lambda: 10)
    assert A.elegir(C.GPU_MIN_MOTOS) == "numba"
    assert "hilos" in A.resumen()


def _caida(h):
    s = F.Simulador(V.pista_plana(), None, n=1, max_reintentos=0,
                    controlador=lambda o, sim: np.zeros((len(o), 3)))
    s.vx[:] = 0
    s.wvx[:] = 0
    s.ws[:] = 0
    for _ in range(int(2 / C.DT)):
        s._fisica(0.0, 0.0)
    y0 = s.py[0]
    s.py += h
    s.wy += h
    tocado = fondo = False
    sobre = aire = subida = 0.0
    for _ in range(int(3 / C.DT)):
        s.carga = np.zeros((2, 1))
        s._fisica(0.0, 0.0)
        c = (s.fn[:, 0] > 0).any()
        tocado = tocado or c
        if tocado:
            sobre = max(sobre, float(s.uso_estructura()[0]))
            aire += (not c) * C.DT
            fondo = fondo or s.vy[0] > 0
            if fondo:
                subida = max(subida, s.py[0] - y0)
    return sobre, aire, subida


def test_suspension_realista_no_rebota_y_se_rompe():
    if not C.SUSPENSION_REALISTA:
        pytest.skip("suspensión realista apagada")
    uso, aire, subida = _caida(1.0)
    assert uso < 0.3 and aire == 0.0 and subida < 0.05
    uso, _, _ = _caida(3.0)
    assert uso < 1.0
    uso, _, _ = _caida(6.0)
    assert uso > 1.0


def test_paso_converge():
    if not C.SUSPENSION_REALISTA:
        pytest.skip("suspensión realista apagada")
    base = _caida(1.5)
    with V.subpasos(2 * C.SUBPASOS):
        fino = _caida(1.5)
    assert abs(base[0] - fino[0]) < 0.1 and abs(base[2] - fino[2]) < 0.03
