import csv
import json
import logging
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

import numpy as np

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
sys.path.insert(0, RAIZ)

import config as C
import evolucion as E

RESPALDO_V9 = os.path.join(os.path.dirname(RAIZ), "MotoTerminator_respaldo_v9_2026-10-08")

_V9 = r"""
import sys, os, numpy as np
d, gens, n, seed, out = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4]), sys.argv[5]
sys.path.insert(0, d); os.chdir(d)
import evolucion as E
e = E.Entrenador(n, continuar=False, semilla=seed)
res = []
for _ in range(gens):
    r = e.correr_generacion()
    res.append([r["mejor"], r["promedio"], r["llegaron"], r["terminadas_lider"], r["nivel"]])
np.savez(out, pob=e.pob, res=np.array(res, dtype=float), sigma=e.sigma)
"""


class Banderas:

    def __init__(self, **cambios):
        self.cambios, self.antes = cambios, {}

    def __enter__(self):
        for k, v in self.cambios.items():
            self.antes[k] = getattr(C, k, None)
            setattr(C, k, v)

    def __exit__(self, *a):
        for k, v in self.antes.items():
            setattr(C, k, v)


def correr(e, gens):
    res = []
    for _ in range(gens):
        r = e.correr_generacion()
        res.append([r["mejor"], r["promedio"], r["llegaron"], r["terminadas_lider"], r["nivel"]])
    return np.array(res, dtype=float)


class PruebasEvolucion(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="moto_evol_")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def dd(self, nombre):
        return os.path.join(self.tmp, nombre)

    @unittest.skipUnless(os.path.isdir(RESPALDO_V9), "no está el respaldo v9")
    def test_identico_a_v9(self):
        v9 = self.dd("v9")
        shutil.copytree(RESPALDO_V9, v9, ignore=shutil.ignore_patterns(
            "*.npz", "*.json", "*.csv", "__pycache__", "datos"))
        script = self.dd("v9.py")
        with open(script, "w", encoding="utf-8") as f:
            f.write(_V9)
        out = self.dd("o9.npz")
        subprocess.run([sys.executable, script, v9, "2", "16", "7", out], check=True,
                       cwd=self.tmp, timeout=300)
        with np.load(out) as z:
            ref = {k: z[k] for k in z.files}
        e = E.Entrenador(16, semilla=7, dir_datos=self.dd("v10"))
        res = correr(e, 2)
        self.assertTrue(np.array_equal(ref["res"], res), (ref["res"], res))
        self.assertTrue(np.array_equal(ref["pob"], e.pob))
        self.assertEqual(float(ref["sigma"]), e.sigma)

    def test_paralelo_igual_a_serie(self):
        a = E.Entrenador(16, semilla=11, dir_datos=self.dd("s"))
        ra = correr(a, 2)
        b = E.Entrenador(16, semilla=11, dir_datos=self.dd("p"), procesos=3)
        try:
            rb = correr(b, 2)
            va = a.evaluar_validacion(a.pob[:3])
            vb = b.evaluar_validacion(b.pob[:3])
        finally:
            b.cerrar()
        self.assertTrue(np.array_equal(ra, rb), (ra, rb))
        self.assertTrue(np.array_equal(a.pob, b.pob))
        self.assertTrue(np.array_equal(va[0], vb[0]) and np.array_equal(va[1], vb[1]))
        with open(os.path.join(self.dd("s"), C.ARCHIVO_HISTORIAL), encoding="utf-8") as f1, \
                open(os.path.join(self.dd("p"), C.ARCHIVO_HISTORIAL), encoding="utf-8") as f2:
            self.assertEqual(f1.read(), f2.read())

    def test_continuar_es_igual_a_no_detenerse(self):
        with Banderas(GA_V2=True):
            a = E.Entrenador(12, semilla=5, dir_datos=self.dd("a"))
            ra = correr(a, 2)
            b = E.Entrenador(12, semilla=5, dir_datos=self.dd("b"))
            rb1 = correr(b, 1)
            del b
            c = E.Entrenador(12, continuar=True, semilla=999, dir_datos=self.dd("b"))
            self.assertEqual(c.generacion, 2)
            rb2 = correr(c, 1)
        self.assertTrue(np.array_equal(ra, np.vstack([rb1, rb2])))
        self.assertTrue(np.array_equal(a.pob, c.pob))
        self.assertTrue(np.array_equal(a.sigmas, c.sigmas))
        self.assertEqual(a.sigma, c.sigma)
        with np.load(os.path.join(self.dd("b"), C.ARCHIVO_POBLACION)) as d:
            self.assertEqual(int(d["formato"]), 2)
            for k in ("sigma", "racha", "rng", "config_hash", "version"):
                self.assertIn(k, d.files)
        m = leer_json(os.path.join(self.dd("b"), C.ARCHIVO_MEJOR))
        self.assertEqual(m["formato"], 2)
        self.assertFalse([f for f in os.listdir(self.dd("b")) if f.endswith(".tmp")])

    def test_lee_formato_1_del_usuario(self):
        nombres = (C.ARCHIVO_MEJOR, C.ARCHIVO_POBLACION, C.ARCHIVO_HISTORIAL)
        carpeta = RESPALDO_V9 if all(os.path.exists(os.path.join(RESPALDO_V9, n))
                                     for n in nombres) else RAIZ
        origen = [os.path.join(carpeta, n) for n in nombres]
        if not all(os.path.exists(p) for p in origen):
            self.skipTest("no hay archivos guardados del usuario")
        d = self.dd("u")
        os.makedirs(d)
        for p in origen:
            shutil.copy(p, d)
        with np.load(os.path.join(d, C.ARCHIVO_POBLACION)) as z:
            viejo = {k: z[k] for k in z.files}
        if "formato" in viejo:
            self.skipTest("los archivos del usuario ya son formato 2")
        with open(os.path.join(d, C.ARCHIVO_HISTORIAL), encoding="utf-8") as f:
            filas_viejas = list(csv.DictReader(f))
        mejor = E.cargar_mejor("terreno", d)[0]
        e = E.Entrenador(len(viejo["pob"]), continuar=True, semilla=1, dir_datos=d)
        self.assertEqual(e.generacion, int(viejo["generacion"]) + 1)
        self.assertEqual(e.nivel, int(viejo["nivel"]))
        self.assertTrue(np.array_equal(e.pob[0], mejor))
        self.assertTrue(np.array_equal(e.pob[1:], viejo["pob"][1:]))
        self.assertEqual(len(e.historial), len(filas_viejas))
        e.pistas = e.pistas[:1]
        e._preparar_generacion = lambda: None
        e.aptitudes, e.llegadas = e.aptitudes[:1], e.llegadas[:1]
        e.limpias, e.reintentos = e.limpias[:1], e.reintentos[:1]
        e.velocidades, e.componentes = e.velocidades[:1], e.componentes[:1]
        e.correr_generacion()
        with open(os.path.join(d, C.ARCHIVO_HISTORIAL), encoding="utf-8") as f:
            filas = list(csv.DictReader(f))
        self.assertEqual(len(filas), len(filas_viejas) + 1)
        for a, b in zip(filas_viejas, filas):
            for k, v in a.items():
                self.assertEqual(b[k], v)
        self.assertIn("llegadas_limpias_pct", filas[-1])
        self.assertNotEqual(filas[-1]["llegadas_limpias_pct"], "")
        with np.load(os.path.join(d, C.ARCHIVO_POBLACION)) as z:
            self.assertEqual(int(z["formato"]), 2)

    def test_archivo_corrupto_se_registra(self):
        d = self.dd("c")
        os.makedirs(d)
        with open(os.path.join(d, C.ARCHIVO_POBLACION), "wb") as f:
            f.write(b"esto no es un npz")
        with self.assertLogs("moto.evolucion", level=logging.WARNING) as cm:
            e = E.Entrenador(6, continuar=True, semilla=1, dir_datos=d, guardar=False)
        self.assertTrue(any("poblacion" in m for m in cm.output))
        self.assertEqual(e.generacion, 1)

    def test_ga_v2(self):
        with Banderas(GA_V2=True):
            ga = E.parametros_ga()
            self.assertEqual((ga["prob_cruce"], ga["inmigrantes"], ga["sigma_min"]), (0.0, 0.0, 0.02))
            e = E.Entrenador(10, semilla=3, guardar=False)
            e.aptitudes[:] = np.arange(10)[None, :]
            e._evolucionar()
        self.assertEqual(len(e.sigmas), 10)
        self.assertTrue(np.all(e.sigmas >= 0.02) and np.all(e.sigmas <= 1.0))
        p = E.parametros_ga()
        self.assertEqual((p["prob_cruce"], p["sigma_min"], p["sigma_max"]),
                         (C.PROB_CRUCE, C.SIGMA_MUTACION, 2 * C.SIGMA_MUTACION))

    def test_subir_por_limpias(self):
        for bandera, racha in ((False, 1), (True, 0)):
            with Banderas(SUBIR_POR_LIMPIAS=bandera):
                e = E.Entrenador(6, semilla=2, guardar=False)
                e.llegadas[:] = True
                e.limpias[:] = False
                e._evolucionar()
                self.assertEqual(e.racha, racha)

    def test_campeona_validada(self):
        d = self.dd("v")
        with Banderas(VALIDAR_CAMPEONA=True, PISTAS_VALIDACION=2, TOP_VALIDAR=2, VALIDAR_CADA=10):
            e = E.Entrenador(6, semilla=4, dir_datos=d)
            self.assertEqual(e.semillas_validacion(1), [2 ** 30 + 1000, 2 ** 30 + 1001])
            r = correr_resumen(e)
            self.assertIn("validacion", r)
            self.assertTrue(r["validacion"]["reemplazo"])
            m = leer_json(os.path.join(d, C.ARCHIVO_MEJOR))
            self.assertIn("validacion", m)
            r2 = correr_resumen(e)
            self.assertNotIn("validacion", r2)
            m2 = leer_json(os.path.join(d, C.ARCHIVO_MEJOR))
            self.assertEqual(m["pesos"], m2["pesos"])


class _OptFalso:

    def __init__(self, n, n_param, rng, x0):
        self.n, self.rng, self.media, self.sigma = n, rng, x0[0].copy(), 0.1
        self.mejor = x0[0].copy()
        self._ult = None

    def ask(self):
        self._ult = self.media + self.sigma * self.rng.normal(size=(self.n, len(self.media)))
        self._ult[0] = self.mejor
        return self._ult

    def tell(self, apt):
        self.mejor = self._ult[int(np.argmax(apt))].copy()
        self.media = 0.5 * self.media + 0.5 * self.mejor
        self.sigma *= 0.9

    def estado(self):
        return {"media": self.media, "mejor": self.mejor, "ult": self._ult, "sigma": self.sigma,
                "rng": self.rng.bit_generator.state}

    def cargar_estado(self, e):
        self.media, self.mejor, self._ult = e["media"], e["mejor"], e["ult"]
        self.sigma = e["sigma"]
        self.rng.bit_generator.state = e["rng"]


class PruebaIntegracionOptimizador(unittest.TestCase):
    def test_optimizador_externo_y_continuar(self):
        import types
        falso = types.ModuleType("optimizadores")
        falso.crear = lambda nombre, n, n_param, rng, x0: _OptFalso(n, n_param, rng, x0)
        real = sys.modules.get("optimizadores")
        sys.modules["optimizadores"] = falso
        tmp = tempfile.mkdtemp(prefix="moto_opt_")
        try:
            with Banderas(OPTIMIZADOR="falso", PISTAS_POR_GENERACION=1):
                a = E.Entrenador(8, semilla=3, dir_datos=os.path.join(tmp, "a"))
                ra = correr(a, 2)
                b = E.Entrenador(8, semilla=3, dir_datos=os.path.join(tmp, "b"))
                rb = correr(b, 1)
                c = E.Entrenador(8, continuar=True, semilla=77, dir_datos=os.path.join(tmp, "b"))
                rc = correr(c, 1)
            self.assertIsInstance(a.opt, _OptFalso)
            self.assertTrue(np.array_equal(ra, np.vstack([rb, rc])))
            self.assertTrue(np.array_equal(a.pob, c.pob))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
            if real is None:
                sys.modules.pop("optimizadores", None)
            else:
                sys.modules["optimizadores"] = real


def leer_json(archivo):
    with open(archivo, encoding="utf-8") as f:
        return json.load(f)


def correr_resumen(e):
    return e.correr_generacion()


if __name__ == "__main__":
    unittest.main(verbosity=2)
