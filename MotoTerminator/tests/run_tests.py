import glob
import importlib.util
import inspect
import os
import pathlib
import shutil
import sys
import tempfile
import time
import traceback
import unittest

CARPETA = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(CARPETA)


def _con_pytest(args):
    import pytest
    return pytest.main([CARPETA, "-q", "-p", "no:cacheprovider", *args])


def _es_skip(exc):
    return isinstance(exc, unittest.SkipTest) or type(exc).__name__ in ("Skipped", "SkipTest")


def _propio():
    sys.path.insert(0, RAIZ)
    ok = fallas = saltadas = 0
    t0 = time.perf_counter()
    for archivo in sorted(glob.glob(os.path.join(CARPETA, "test_*.py"))):
        nombre = os.path.splitext(os.path.basename(archivo))[0]
        try:
            spec = importlib.util.spec_from_file_location(nombre, archivo)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
        except Exception as e:
            if _es_skip(e):
                print(f"s {nombre}: {e}")
                saltadas += 1
                continue
            print(f"E {nombre}: no se pudo importar\n{traceback.format_exc()}")
            fallas += 1
            continue
        suite = unittest.defaultTestLoader.loadTestsFromModule(mod)
        if suite.countTestCases():
            r = unittest.TextTestRunner(verbosity=1, stream=sys.stdout).run(suite)
            fallas += len(r.failures) + len(r.errors)
            saltadas += len(r.skipped)
            ok += r.testsRun - len(r.failures) - len(r.errors) - len(r.skipped)
        for fn_nombre, fn in inspect.getmembers(mod, inspect.isfunction):
            if not fn_nombre.startswith("test_") or fn.__module__ != mod.__name__:
                continue
            tmp = None
            try:
                kw = {}
                params = inspect.signature(fn).parameters
                if "tmp_path" in params:
                    tmp = tempfile.mkdtemp(prefix="mt_")
                    kw["tmp_path"] = pathlib.Path(tmp)
                if any(p not in ("tmp_path",) and params[p].default is inspect._empty for p in params):
                    print(f"s {nombre}::{fn_nombre} (fixtures de pytest no disponibles)")
                    saltadas += 1
                    continue
                fn(**kw)
                ok += 1
                print(f". {nombre}::{fn_nombre}")
            except Exception as e:
                if _es_skip(e):
                    saltadas += 1
                    print(f"s {nombre}::{fn_nombre}: {e}")
                else:
                    fallas += 1
                    print(f"F {nombre}::{fn_nombre}\n{traceback.format_exc()}")
            finally:
                if tmp:
                    shutil.rmtree(tmp, ignore_errors=True)
    print(f"\n{ok} pasaron, {fallas} fallaron, {saltadas} omitidas en {time.perf_counter() - t0:.1f} s")
    return 1 if fallas else 0


def main(argv=None):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    argv = list(sys.argv[1:] if argv is None else argv)
    if "--propio" not in argv:
        try:
            import pytest
            return _con_pytest(argv)
        except ImportError:
            print("pytest no está instalado: uso el ejecutor propio (pip install -r requirements-dev.txt)")
    return _propio()


if __name__ == "__main__":
    sys.exit(main())
