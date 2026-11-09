import json
import os
import shutil
import tempfile
import warnings
import sys
import unittest

import numpy as np

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
sys.path.insert(0, RAIZ)

import config as C
import optimizadores as O
import red as R

ESC = O.escala_genes(C.CAPAS)
N = len(ESC)
CENTRO = np.random.default_rng(123).choice([-1.0, 1.0], N) * ESC


def sphere(X):
    y = (X - CENTRO) / ESC
    return -(y ** 2).sum(1)


def rastrigin(X):
    y = (X - CENTRO) / ESC
    return -(10 * N + (y ** 2 - 10 * np.cos(2 * np.pi * y)).sum(1))


def descriptores(X):
    return np.c_[X[:, 0] / ESC[0] * 20 + 45, (X[:, 1] / ESC[1] + 2) / 4]


def correr(opt, f, generaciones):
    X = opt.ask()
    a = f(X)
    inicial = float(a.max())
    for _ in range(generaciones):
        kw = {"descriptores": descriptores(X)} if isinstance(opt, O.MAPElites) else {}
        opt.tell(X, a, **kw)
        X = opt.ask()
        a = f(X)
    return inicial, opt.mejor[1]


UMBRAL = {
    "sphere": {"ga": 0.999, "ga_v2": 0.7, "sep_cma": 0.2, "es": 0.2, "pgpe": 0.4,
               "map_elites": 0.95},
    "rastrigin": {"ga": 0.999, "ga_v2": 0.8, "sep_cma": 0.9, "es": 0.5, "pgpe": 0.5,
                  "map_elites": 0.97},
}


class TestConvergencia(unittest.TestCase):
    GENS = 300

    def _probar(self, nombre, fn):
        f = {"sphere": sphere, "rastrigin": rastrigin}[fn]
        ini, fin = correr(O.crear(nombre, pop=40, semilla=0), f, self.GENS)
        ratio = fin / ini
        self.assertLess(ratio, UMBRAL[fn][nombre],
                        f"{nombre} en {fn}: costo {-ini:.1f} -> {-fin:.1f} (razón {ratio:.3f})")

    def test_sphere(self):
        for nombre in O.OPTIMIZADORES:
            with self.subTest(nombre=nombre):
                self._probar(nombre, "sphere")

    def test_rastrigin(self):
        for nombre in O.OPTIMIZADORES:
            with self.subTest(nombre=nombre):
                self._probar(nombre, "rastrigin")


class TestEstado(unittest.TestCase):
    def test_cargar_estado_reproduce_siguiente_ask(self):
        for nombre in O.OPTIMIZADORES:
            for antes_de_tell in (False, True):
                with self.subTest(nombre=nombre, antes_de_tell=antes_de_tell):
                    opt = O.crear(nombre, pop=21, semilla=7)
                    X = opt.ask()
                    for _ in range(5):
                        kw = {"descriptores": descriptores(X)} if nombre == "map_elites" else {}
                        opt.tell(X, sphere(X), **kw)
                        X = opt.ask()
                    if not antes_de_tell:
                        kw = {"descriptores": descriptores(X)} if nombre == "map_elites" else {}
                        opt.tell(X, sphere(X), **kw)
                    d = json.loads(json.dumps(opt.estado()))
                    sig1 = opt.ask()
                    otro = O.desde_estado(d)
                    sig2 = otro.ask()
                    np.testing.assert_array_equal(sig1, sig2)
                    kw = {"descriptores": descriptores(sig1)} if nombre == "map_elites" else {}
                    opt.tell(sig1, sphere(sig1), **kw)
                    otro.tell(sig2, sphere(sig2), **kw)
                    np.testing.assert_array_equal(opt.ask(), otro.ask())

    def test_ask_idempotente(self):
        for nombre in O.OPTIMIZADORES:
            with self.subTest(nombre=nombre):
                opt = O.crear(nombre, pop=11, semilla=1)
                np.testing.assert_array_equal(opt.ask(), opt.ask())


class TestTestigo(unittest.TestCase):

    NUEVOS = [n for n in O.OPTIMIZADORES if n != "ga"]

    def test_campeona_en_fila_0(self):
        for nombre in O.OPTIMIZADORES:
            with self.subTest(nombre=nombre):
                opt = O.crear(nombre, pop=15, semilla=3)
                X = opt.ask()
                for _ in range(3):
                    a = sphere(X)
                    kw = {"descriptores": descriptores(X)} if nombre == "map_elites" else {}
                    opt.tell(X, a, **kw)
                    mejor = X[int(np.argmax(a))]
                    X = opt.ask()
                    np.testing.assert_array_equal(X[0], mejor)
                    np.testing.assert_array_equal(opt.mejor[0], mejor)

    def test_testigo_no_influye(self):
        for nombre in self.NUEVOS:
            with self.subTest(nombre=nombre):
                a_opt, b_opt = O.crear(nombre, pop=15, semilla=4), O.crear(nombre, pop=15, semilla=4)
                X = a_opt.ask()
                np.testing.assert_array_equal(X, b_opt.ask())
                apt = sphere(X)
                apt_a, apt_b = apt.copy(), apt.copy()
                apt_a[0] = apt.min() - 5.0
                apt_b[0] = apt.min() - 500.0
                kw = {"descriptores": descriptores(X)} if nombre == "map_elites" else {}
                a_opt.tell(X, apt_a, **kw)
                b_opt.tell(X, apt_b, **kw)
                np.testing.assert_array_equal(a_opt.ask()[1:], b_opt.ask()[1:])


class TestCompatibilidad(unittest.TestCase):
    def test_inicializacion_como_red(self):
        for nombre in ("ga_v2", "sep_cma", "es", "pgpe", "map_elites"):
            with self.subTest(nombre=nombre):
                opt = O.crear(nombre, pop=11, semilla=9)
                esperado = R.aleatorios(1, C.CAPAS, np.random.default_rng(9))[0]
                np.testing.assert_allclose(opt.ask()[0], esperado, rtol=0, atol=1e-12)

    def test_ga_igual_a_entrenador(self):
        import evolucion as E
        if getattr(C, "GA_V2", False) or getattr(C, "SIGMA_AUTOADAPTATIVA", False) \
                or getattr(C, "MUTACION_RELATIVA", False):
            self.skipTest("config no está en modo v9")
        nicho = getattr(C, "NICHO_RAPIDAS", 0)
        C.NICHO_RAPIDAS = 0
        self.addCleanup(setattr, C, "NICHO_RAPIDAS", nicho)
        n = 40
        ga = O.GA(pop=n, rng=np.random.default_rng(11))
        ent = object.__new__(E.Entrenador)
        ent.rng = np.random.default_rng(11)
        ent.n, ent.n_param = n, R.n_parametros(C.CAPAS)
        ent.pob = R.aleatorios(n, C.CAPAS, ent.rng)
        ent.sigma, ent.sigmas, ent.hay_campeon = C.SIGMA_MUTACION, None, False
        np.testing.assert_array_equal(ga.ask(), ent.pob)
        params = E.parametros_ga()
        hist = []
        f_rng = np.random.default_rng(0)
        for g in range(30):
            apt = f_rng.normal(size=n) if g < 10 else np.full(n, -1.0) + 1e-3 * f_rng.normal(size=n)
            orden = np.argsort(-apt)
            previos = [m for m in hist]
            if len(previos) >= 20 and np.mean(previos[-10:]) <= np.mean(previos[-20:-10]):
                ent.sigma = min(ent.sigma * 1.1, params["sigma_max"])
            else:
                ent.sigma = max(ent.sigma * 0.97, params["sigma_min"])
            ent._nueva_poblacion(apt, orden, params)
            hist.append(float(apt[orden[0]]))
            ga.tell(ga.ask(), apt, nivel=1)
            np.testing.assert_array_equal(ga.ask(), ent.pob, err_msg=f"generación {g}")
            self.assertEqual(ga.sigma, ent.sigma)


class TestErrores(unittest.TestCase):
    def test_map_elites_sin_descriptores(self):
        opt = O.crear("map_elites", pop=11, semilla=0, exigir_descriptores=True)
        X = opt.ask()
        with self.assertRaises(ValueError):
            opt.tell(X, sphere(X))
        opt = O.crear("map_elites", pop=11, semilla=0)
        X = opt.ask()
        with self.assertWarns(UserWarning):
            opt.tell(X, sphere(X))
        self.assertGreater(len(opt.ocupadas), 0)

    def test_convencion_entrenador(self):
        pob = R.aleatorios(12, C.CAPAS, np.random.default_rng(2))
        for nombre in ("ga_v2", "sepcma", "es", "pgpe", "map_elites", "ga"):
            with self.subTest(nombre=nombre):
                opt = O.crear(nombre, n=12, n_param=pob.shape[1], capas=C.CAPAS,
                              rng=np.random.default_rng(3), x0=pob.copy(), pob=pob.copy(), semilla=5)
                X = opt.ask()
                self.assertEqual(X.shape, pob.shape)
                np.testing.assert_array_equal(X[0], pob[0])
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    opt.tell(sphere(X))
                self.assertEqual(opt.ask().shape, pob.shape)

    def test_nombre_desconocido(self):
        with self.assertRaises(ValueError):
            O.crear("nada")

    def test_aptitud_no_finita(self):
        opt = O.crear("sep_cma", pop=11, semilla=0)
        X = opt.ask()
        a = sphere(X)
        a[3] = np.nan
        a[5] = np.inf * -1
        opt.tell(X, a)
        self.assertTrue(np.isfinite(opt.ask()).all())


class TestIntegracionEntrenador(unittest.TestCase):

    def test_entrenar_y_continuar(self):
        import evolucion as E
        antes = getattr(C, "OPTIMIZADOR", "ga")
        try:
            for nombre in ("ga_v2", "sep_cma", "es", "pgpe", "map_elites"):
                with self.subTest(nombre=nombre):
                    C.OPTIMIZADOR = nombre
                    d = tempfile.mkdtemp(prefix="opt_")
                    try:
                        with warnings.catch_warnings():
                            warnings.simplefilter("ignore")
                            e = E.Entrenador(poblacion=10, semilla=1, dir_datos=d, guardar=True)
                            for _ in range(2):
                                e.correr_generacion()
                            e2 = E.Entrenador(poblacion=10, semilla=99, continuar=True,
                                              dir_datos=d, guardar=False)
                        self.assertIsNotNone(e.opt)
                        np.testing.assert_array_equal(e.pob, e2.pob)
                        np.testing.assert_array_equal(e.pob[0], e.opt.mejor[0])
                    finally:
                        for x in (locals().get("e"), locals().get("e2")):
                            if x is not None and hasattr(x, "cerrar"):
                                x.cerrar()
                        shutil.rmtree(d, ignore_errors=True)
        finally:
            C.OPTIMIZADOR = antes


if __name__ == "__main__":
    unittest.main(verbosity=2)
