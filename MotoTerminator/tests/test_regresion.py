import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

import numpy as np

AQUI = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESPALDO = os.path.join(os.path.dirname(AQUI), "MotoTerminator_respaldo_v9_2026-10-08")
if AQUI not in sys.path:
    sys.path.insert(0, AQUI)

PISTAS = ((1, 101), (3, 303), (5, 505), (8, 808))

_SCRIPT = r"""
import sys, numpy as np
sys.path.insert(0, sys.argv[1])
import config as C
if hasattr(C, 'fisica_clasica'):
    C.fisica_clasica()          # v13+: compara con el contrapeso apagado
from fisica import Simulador
from terreno import Pista
pesos = np.load(sys.argv[2])["pesos"]
out = {}
for nivel, semilla in %r:
    s = Simulador(Pista(nivel, semilla), pesos, semilla_ruido=semilla)
    while not s.terminado:
        s.paso()
    k = f"n{nivel}_"
    out[k + "aptitud"] = s.aptitud()
    out[k + "motivo"] = s.motivo
    out[k + "reintentos"] = s.reintentos
    out[k + "t_fin"] = s.t_fin
    out[k + "progreso"] = s.progreso
np.savez(sys.argv[3], **out)
""" % (PISTAS,)


def _redes():
    import config as C
    import red as R
    rng = np.random.default_rng(2026)
    pesos = R.aleatorios(8, C.CAPAS, rng)
    try:
        with open(os.path.join(AQUI, C.ARCHIVO_MEJOR), encoding="utf-8") as f:
            w = np.array(json.load(f)["pesos"], dtype=float)
        if w.shape[0] == pesos.shape[1]:
            pesos[4:] = w + rng.normal(0, 0.02, (4, w.shape[0]))
    except (OSError, ValueError, KeyError):
        pass
    return pesos


def correr_en(dir_codigo, archivo_pesos, salida):
    return subprocess.Popen([sys.executable, "-B", "-c", _SCRIPT, dir_codigo, archivo_pesos, salida],
                            cwd=os.path.dirname(salida), stdout=subprocess.PIPE, stderr=subprocess.PIPE)


class TestParidadV9(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not os.path.isdir(RESPALDO):
            raise unittest.SkipTest(f"no existe el respaldo v9 en {RESPALDO}")
        cls.tmp = tempfile.mkdtemp(prefix="mt_regresion_")
        archivo = os.path.join(cls.tmp, "pesos.npz")
        np.savez(archivo, pesos=_redes())
        procs = {nombre: correr_en(d, archivo, os.path.join(cls.tmp, nombre + ".npz"))
                 for nombre, d in (("v9", RESPALDO), ("actual", AQUI))}
        cls.res = {}
        for nombre, p in procs.items():
            _, err = p.communicate(timeout=300)
            if p.returncode != 0:
                raise AssertionError(f"falló la simulación {nombre}:\n{err.decode(errors='replace')}")
            cls.res[nombre] = dict(np.load(os.path.join(cls.tmp, nombre + ".npz")))

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(getattr(cls, "tmp", ""), ignore_errors=True)

    def test_mismas_claves(self):
        self.assertEqual(sorted(self.res["v9"]), sorted(self.res["actual"]))

    def test_resultados_identicos_bit_a_bit(self):
        difs = []
        for k, v9 in self.res["v9"].items():
            act = self.res["actual"][k]
            if not np.array_equal(v9, act):
                difs.append(f"{k}: v9={np.round(v9, 4)} actual={np.round(act, 4)}")
        self.assertFalse(difs, "Los valores por defecto ya no reproducen v9:\n" + "\n".join(difs))

    def test_hay_variedad(self):
        motivos = np.concatenate([v for k, v in self.res["v9"].items() if k.endswith("motivo")])
        self.assertGreater(len(set(motivos.tolist())), 1)


class TestCheckpointsDelUsuario(unittest.TestCase):

    def setUp(self):
        import config as C
        self.C = C
        self.tmp = tempfile.mkdtemp(prefix="mt_ckpt_")
        self.hay = all(os.path.exists(os.path.join(AQUI, f)) for f in (C.ARCHIVO_MEJOR, C.ARCHIVO_POBLACION))
        if not self.hay:
            raise unittest.SkipTest("el usuario no tiene checkpoints guardados")
        for f in (C.ARCHIVO_MEJOR, C.ARCHIVO_POBLACION, C.ARCHIVO_HISTORIAL):
            if os.path.exists(os.path.join(AQUI, f)):
                shutil.copy(os.path.join(AQUI, f), self.tmp)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_mejor_moto_carga(self):
        import evolucion as E
        try:
            m = E.cargar_mejor("terreno", dir_datos=self.tmp)
        except TypeError:
            self.skipTest("evolucion sin dir_datos")
        self.assertIsNotNone(m, "mejor_moto.json ya no carga")
        pesos, datos = m
        self.assertEqual(len(pesos), sum(a * b + b for a, b in zip(self.C.CAPAS[:-1], self.C.CAPAS[1:])))

    def test_continuar_entrenamiento(self):
        import evolucion as E
        with open(os.path.join(self.tmp, self.C.ARCHIVO_MEJOR), encoding="utf-8") as f:
            guardado = json.load(f)
        pob = np.load(os.path.join(self.tmp, self.C.ARCHIVO_POBLACION))
        try:
            e = E.Entrenador(self.C.POBLACION, continuar=True, semilla=0, dir_datos=self.tmp, guardar=False)
        except TypeError:
            self.skipTest("evolucion sin dir_datos/guardar")
        self.assertEqual(e.generacion, int(pob["generacion"]) + 1)
        self.assertEqual(e.nivel, int(pob["nivel"]))
        self.assertTrue(np.allclose(e.pob[0], np.array(guardado["pesos"]), rtol=0, atol=1e-6),
                        "la campeona guardada no quedó en la posición 0")
        self.assertEqual(sorted(os.listdir(self.tmp)),
                         sorted(f for f in (self.C.ARCHIVO_MEJOR, self.C.ARCHIVO_POBLACION,
                                            self.C.ARCHIVO_HISTORIAL)
                                if os.path.exists(os.path.join(AQUI, f))))


if __name__ == "__main__":
    unittest.main()
