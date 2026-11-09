import inspect
import multiprocessing as mp
from concurrent.futures import ProcessPoolExecutor

import numpy as np

import config as C
from fisica import META, Simulador

_RED = None
_ACEPTA_CLIMA = None


def acepta_clima():
    global _ACEPTA_CLIMA
    if _ACEPTA_CLIMA is None:
        try:
            _ACEPTA_CLIMA = "clima" in inspect.signature(Simulador.__init__).parameters
        except (TypeError, ValueError):
            _ACEPTA_CLIMA = False
    return _ACEPTA_CLIMA


def _modulo_puntos():
    if not getattr(C, "PUNTOS_CONTROL", False):
        return None
    try:
        import puntos_control
        return puntos_control
    except ImportError:
        return None


def enganchar_puntos(sim, pista):
    K = _modulo_puntos()
    if K is None or not hasattr(sim, "observadores"):
        return sim
    pc = K.PuntosControl(pista, semilla=pista.semilla)
    pc.enganchar(sim)
    sim.puntos_control = pc
    return sim


def simulador(pista, pesos, semilla_ruido, clima=None):
    if clima is None or not acepta_clima():
        sim = Simulador(pista, pesos, semilla_ruido=semilla_ruido)
    else:
        sim = Simulador(pista, pesos, semilla_ruido=semilla_ruido, clima=clima)
    return enganchar_puntos(sim, pista)


def con_clima(spec, clima):
    if clima is None:
        return tuple(spec)
    spec = tuple(spec)[:6]
    return spec + (None,) * (6 - len(spec)) + (clima,)


def clima_de_spec(spec):
    return spec[6] if len(spec) > 6 else None


def foto_config():
    return {k: getattr(C, k) for k in dir(C) if k.isupper()
            and isinstance(getattr(C, k), (int, float, str, bool, tuple, list, type(None)))}


def _iniciar(red, config, hilos_numba=1):
    global _RED
    _RED = red
    for k, v in config.items():
        setattr(C, k, v)
    try:
        import numba
        numba.set_num_threads(max(1, min(int(hilos_numba), numba.config.NUMBA_NUM_THREADS)))
    except Exception:
        pass


def procesos_disponibles(pedido=None):
    import os
    pedido = getattr(C, "PROCESOS_TURBO", "auto") if pedido is None else pedido
    if isinstance(pedido, str):
        return max(1, (os.cpu_count() or 1) - 1)
    return max(1, int(pedido))


_GPU = []


def info_gpu():
    if not _GPU:
        try:
            import subprocess
            r = subprocess.run(["nvidia-smi", "--query-gpu=name,memory.total,memory.free",
                                "--format=csv,noheader,nounits"], capture_output=True, text=True,
                               timeout=5, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            nombre, total, libre = [x.strip() for x in r.stdout.strip().splitlines()[0].split(",")]
            _GPU.append((nombre, int(total), int(libre)))
        except Exception:
            _GPU.append(None)
    return _GPU[0]


def lanzar(pool, specs, pesos):
    pesos = np.asarray(pesos, dtype=float)
    return [pool.submit(_tarea, (s, pesos)) for s in specs]


def crear_pool(procesos, red_vial=None):
    import os
    hilos = max(1, (os.cpu_count() or 1) // max(1, procesos))
    return ProcessPoolExecutor(max_workers=procesos, mp_context=mp.get_context("spawn"),
                               initializer=_iniciar, initargs=(red_vial, foto_config(), hilos))


def construir_pista(spec, red=None):
    modo, nivel, semilla, ruta = spec[:4]
    if modo == "ciudad":
        red = red if red is not None else _RED
        if len(spec) > 4 and (spec[4] is not None or spec[5] is not None):
            from evolucion import pista_calle
            return pista_calle(red, nivel, semilla, ruta=ruta, superficie=spec[4],
                               circuito=spec[5])
        from calles import PistaCalle
        return PistaCalle(red, nivel, semilla, ruta=ruta)
    from terreno import Pista
    return Pista(nivel, semilla)


def resultados(sim):
    llegadas = sim.motivo == META
    if hasattr(sim, "llegadas_limpias"):
        limpias = np.asarray(sim.llegadas_limpias(), dtype=bool)
    else:
        limpias = llegadas & (sim.reintentos == 0)
    comps = None
    if hasattr(sim, "componentes_aptitud"):
        comps = {k: np.asarray(v, dtype=float) for k, v in sim.componentes_aptitud().items()}
    res = {"aptitud": np.asarray(sim.aptitud(), dtype=float), "llegadas": llegadas,
           "limpias": limpias, "reintentos": sim.reintentos.astype(float),
           "t_fin": sim.t_fin.copy(), "componentes": comps,
           "progreso": np.asarray(sim.progreso, dtype=float).copy()}
    pc = getattr(sim, "puntos_control", None)
    if pc is not None:
        import puntos_control as PC
        reg = np.asarray(pc.registrados, dtype=bool)
        res["puntos"] = reg.sum(axis=1).astype(float)
        res["total_puntos"] = int(reg.shape[1]) if reg.ndim == 2 else 0
        res["exitosas"] = np.asarray(PC.exitosas(sim), dtype=bool)
    return res


def evaluar_spec(spec, pesos, red=None):
    pista = construir_pista(spec, red)
    sim = simulador(pista, pesos, pista.semilla, clima_de_spec(spec))
    while not sim.terminado:
        sim.correr(10_000)
    return resultados(sim)


def _tarea(args):
    spec, pesos = args
    return evaluar_spec(spec, pesos)


def evaluar(pool, specs, pesos):
    pesos = np.asarray(pesos, dtype=float)
    return list(pool.map(_tarea, [(s, pesos) for s in specs]))
