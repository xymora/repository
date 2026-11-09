import os

import config as C

_CACHE = {}


def hilos():
    return os.cpu_count() or 1


def hay_numba():
    if "numba" not in _CACHE:
        try:
            import numba
            _CACHE["numba"] = True
        except Exception:
            _CACHE["numba"] = False
    return _CACHE["numba"]


def gpu():
    if "gpu" not in _CACHE:
        info = None
        if hay_numba() and getattr(C, "MOTOR_FISICA", "auto") != "numpy":
            try:
                from numba import cuda
                if cuda.is_available():
                    dev = cuda.get_current_device()
                    libre, total = cuda.current_context().get_memory_info()
                    nombre = dev.name.decode() if isinstance(dev.name, bytes) else str(dev.name)
                    info = {"nombre": nombre, "vram_total_mb": total // 2 ** 20,
                            "vram_libre_mb": libre // 2 ** 20}
            except Exception:
                info = None
        _CACHE["gpu"] = info
    return _CACHE["gpu"]


def vram_libre_mb():
    g = gpu()
    if g is None:
        return 0
    try:
        from numba import cuda
        return cuda.current_context().get_memory_info()[0] // 2 ** 20
    except Exception:
        return g["vram_libre_mb"]


def mb_necesarios(n, largo_pista=4000):
    return (n * 75 * 8 + 6 * largo_pista * 8) / 2 ** 20 + 64


def elegir(n, en_proceso_hijo=False):
    pedido = getattr(C, "MOTOR_FISICA", "auto")
    if getattr(C, "MODELO_LATERAL", "reducido") != "reducido":
        return "numpy"
    if pedido == "numpy" or not hay_numba():
        return "numpy"
    if pedido in ("auto", "gpu") and gpu() is not None:
        grande = n >= int(getattr(C, "GPU_MIN_MOTOS", 2500))
        if (pedido == "gpu" or grande) and vram_libre_mb() > mb_necesarios(n):
            return "gpu"
    return "numba"


def resumen():
    partes = [f"CPU {hilos()} hilos"]
    partes.append("numba: sí" if hay_numba() else "numba no instalado (física numpy)")
    g = gpu()
    if g is not None:
        partes.append(f"GPU {g['nombre']} · {vram_libre_mb() / 1024:.1f} de "
                      f"{g['vram_total_mb'] / 1024:.1f} GB libres")
    else:
        partes.append("sin GPU CUDA")
    return "  ·  ".join(partes)
