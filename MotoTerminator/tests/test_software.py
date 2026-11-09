import os
import shutil
import subprocess
import sys
import tempfile
import unittest

import numpy as np

AQUI = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if AQUI not in sys.path:
    sys.path.insert(0, AQUI)

ARCHIVOS_USUARIO = ("mejor_moto.json", "poblacion.npz", "historial.csv")


def _huella():
    out = {}
    for f in ARCHIVOS_USUARIO:
        p = os.path.join(AQUI, f)
        out[f] = (os.path.getmtime(p), os.path.getsize(p)) if os.path.exists(p) else None
    return out


def _main(*args, timeout=120):
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    return subprocess.run([sys.executable, os.path.join(AQUI, "main.py"), *args], cwd=AQUI, env=env,
                          capture_output=True, text=True, encoding="utf-8", errors="replace",
                          timeout=timeout)


class TestCLI(unittest.TestCase):
    def test_ayuda_lista_comandos_viejos_y_nuevos(self):
        r = _main("--help")
        self.assertEqual(r.returncode, 0, r.stderr)
        for opcion in ("--sin-gui", "--demo", "--nivel", "--nuevo", "--poblacion", "--semilla", "--ciudad",
                       "--desde", "--hasta", "--evaluar", "--comparar", "--procesos", "--dir-datos",
                       "--experimento", "--bench", "--reporte", "--pistas", "--ruidos", "--sensores"):
            self.assertIn(opcion, r.stdout)

    def test_sin_gui_en_carpeta_aparte(self):
        antes = _huella()
        d = tempfile.mkdtemp(prefix="mt_cli_")
        try:
            r = _main("--sin-gui", "1", "--nuevo", "--semilla", "3", "--poblacion", "8", "--dir-datos", d)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn("Gen    1", r.stdout)
            self.assertTrue(os.path.exists(os.path.join(d, "mejor_moto.json")), os.listdir(d))
        finally:
            shutil.rmtree(d, ignore_errors=True)
        self.assertEqual(antes, _huella(), "se modificaron archivos del usuario")


class TestControladores(unittest.TestCase):
    def test_forma_y_rango(self):
        import controladores as K
        obs = np.random.default_rng(0).uniform(-2, 2, (7, 35))
        for ctl in (K.ControladorPD(), K.ControladorAleatorio(semilla=1)):
            a = ctl(obs, None)
            self.assertEqual(a.shape, (7, 3))
            self.assertTrue(np.all(np.abs(a) <= 1.0))

    def test_aleatorio_reproducible(self):
        import controladores as K
        obs = np.zeros((4, 35))
        self.assertTrue(np.array_equal(K.ControladorAleatorio(5)(obs), K.ControladorAleatorio(5)(obs)))

    def test_pd_corrige_hacia_su_carril(self):
        import controladores as K
        obs = np.zeros((2, 35))
        obs[0, K.I_DESVIO] = +1.0
        obs[1, K.I_DESVIO] = -1.0
        d = K.ControladorPD()(obs)[:, 2]
        self.assertLess(d[0], 0)
        self.assertGreater(d[1], 0)

    def test_pd_termina_pista_facil_de_prueba(self):
        import experimentos as X
        f = X.episodio("pd", 1, 0)
        self.assertTrue(f["limpia"], f)


class TestEstadistica(unittest.TestCase):
    def test_rango_semillas(self):
        import experimentos as X
        self.assertEqual(X.rango_semillas("0-3"), [0, 1, 2, 3])
        self.assertEqual(X.rango_semillas("1,4,6-7"), [1, 4, 6, 7])

    def test_ic_proporcion(self):
        import experimentos as X
        lo, hi = X.ic_proporcion(8, 8)
        self.assertAlmostEqual(lo, 0.631, places=2)
        self.assertEqual(hi, 1.0)
        lo, hi = X.ic_proporcion(0, 299)
        self.assertLess(hi, 0.0125)

    def test_ic_bootstrap(self):
        import experimentos as X
        m, lo, hi = X.ic_bootstrap([1.0, 2.0, 3.0, 4.0])
        self.assertAlmostEqual(m, 2.5)
        self.assertTrue(lo < m < hi)


class TestBench(unittest.TestCase):
    def test_bench_rapido(self):
        import bench
        fis = bench.medir_fisica(ns=(1, 8), pasos=3)
        self.assertEqual([f["n"] for f in fis], [1, 8])
        self.assertTrue(all(f["us_subpaso"] > 0 for f in fis))


class TestInterfazHumo(unittest.TestCase):

    def setUp(self):
        try:
            import tkinter as tk
            self.raiz = tk.Tk()
        except Exception as e:
            raise unittest.SkipTest(f"sin display: {e}")
        self.raiz.withdraw()
        self.tmp = tempfile.mkdtemp(prefix="mt_gui_")

    def tearDown(self):
        try:
            self.raiz.destroy()
        except Exception:
            pass
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_entrenamiento_dibuja(self):
        import evolucion as E
        import interfaz
        antes = _huella()
        e = E.Entrenador(6, continuar=False, semilla=1, dir_datos=self.tmp, guardar=False)
        app = interfaz.App(self.raiz, entrenador=e)
        for _ in range(5):
            app.avanzar()
        app.dibujar()
        app.dibujar_panel(app.sim_actual())
        app._info_estado()
        self.raiz.update_idletasks()
        for nombre in ("vista", "mapa", "equilibrio", "panel"):
            self.assertGreater(len(getattr(app, nombre).find_all()), 5, nombre)
        app.alternar_turbo()
        app.avanzar()
        app.dibujar()
        self.assertGreater(len(app.vista.find_all()), 0)
        app.alternar_turbo()
        app.alternar_pausa()
        app.alternar_pausa()
        self.assertEqual(antes, _huella(), "la interfaz modificó archivos del usuario")

    def test_texto_limpias(self):
        import interfaz
        self.assertEqual(interfaz._texto_limpias({}), "")
        self.assertIn("37", interfaz._texto_limpias({"llegadas_limpias_pct": 37.2}))


if __name__ == "__main__":
    unittest.main()
