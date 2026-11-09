import csv
import json
import os

import numpy as np

import cerebro as B
import config as C
from etapas import NOMBRES, NUMERO_ETAPAS
from mundo import Partida

AQUI = os.path.dirname(os.path.abspath(__file__))
COLUMNAS = ["generacion", "etapa", "nombre", "mejor_progreso", "promedio_progreso", "superaron_pct",
            "mejor_aptitud", "promedio_aptitud", "bajas_lider", "muertes_promedio", "sigma", "racha", "subio"]


def bajar_prioridad():
    try:
        if os.name == "nt":
            import ctypes
            k = ctypes.windll.kernel32
            k.GetCurrentProcess.restype = ctypes.c_void_p
            k.SetPriorityClass.argtypes = [ctypes.c_void_p, ctypes.c_uint]
            k.SetPriorityClass(k.GetCurrentProcess(), 0x4000)
        else:
            os.nice(10)
    except Exception:
        pass


def evaluar(tarea):
    indice, numero, pesos, semilla = tarea
    partida = Partida(numero, [B.ControladorRed(w) for w in pesos], semilla)
    while not partida.terminada:
        partida.paso()
    return indice, partida.resumen()


def carpeta_datos(jugadores, dir_datos=None):
    base = dir_datos or os.path.join(AQUI, C.CARPETA_DATOS)
    d = os.path.join(base, f"{jugadores}_jugador" + ("es" if jugadores > 1 else ""))
    os.makedirs(d, exist_ok=True)
    return d


def _guardar_json(archivo, datos):
    tmp = archivo + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(datos, f)
    os.replace(tmp, archivo)


def _leer_json(archivo):
    try:
        with open(archivo, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def rangos_centrados(valores):
    rangos = np.empty(len(valores))
    rangos[np.argsort(valores, kind="stable")] = np.arange(len(valores))
    return rangos / max(len(valores) - 1, 1) - 0.5


class Entrenador:
    def __init__(self, jugadores=1, continuar=True, semilla=None, dir_datos=None, poblacion=C.POBLACION):
        self.jugadores = jugadores
        self.rng = np.random.default_rng(semilla)
        self.dir = carpeta_datos(jugadores, dir_datos)
        self.k = max(1, (poblacion - 2) // 2)
        self.n = 2 * self.k + 2
        self.dim = B.N_PARAM * jugadores
        self._desde_cero()
        if continuar:
            self._cargar()

    def _desde_cero(self):
        self.theta = np.concatenate([B.pesos_iniciales(self.rng) for _ in range(self.jugadores)])
        self.m = np.zeros(self.dim)
        self.v = np.zeros(self.dim)
        self.t_adam = 0
        self.sigma = C.SIGMA
        self.generacion = 1
        self.etapa = 1
        self.completada = False
        self.racha = 0
        self.elite = None
        self.historial = []
        self.campeones = {}
        self.record_etapa = 0.0
        self.sin_mejora = 0
        self.demo_x = np.zeros((0, B.N_ENTRADAS))
        self.demo_y = np.zeros((0, len(B.NOMBRES_SALIDAS)))
        self.demo_e = np.zeros(0, dtype=np.int64)

    def reiniciar(self):
        self._desde_cero()
        for nombre in ("estado.json", "estado.npz", "campeones.json", "historial.csv", "demos.npz"):
            try:
                os.remove(os.path.join(self.dir, nombre))
            except OSError:
                pass

    def _cargar(self):
        meta = _leer_json(os.path.join(self.dir, "estado.json"))
        try:
            arrays = np.load(os.path.join(self.dir, "estado.npz"))
        except (OSError, ValueError):
            return
        if not meta:
            return
        if arrays["theta"].shape == (self.dim,):
            self.theta, self.m, self.v = arrays["theta"], arrays["m"], arrays["v"]
            self.elite = arrays["elite"] if "elite" in arrays.files else None
        else:
            theta = B.migrar(arrays["theta"], self.jugadores)
            if theta is None:
                return
            self.theta = theta
            self.t_adam = -1
            self.elite = B.migrar(arrays["elite"], self.jugadores) if "elite" in arrays.files else None
        migrada = self.t_adam == -1
        for clave in ("t_adam", "sigma", "generacion", "etapa", "completada", "racha", "historial"):
            setattr(self, clave, meta[clave])
        if migrada:
            self.t_adam = 0
            self.sigma = max(self.sigma, C.SIGMA)
        self.record_etapa = meta.get("record_etapa", 0.0)
        self.sin_mejora = meta.get("sin_mejora", 0)
        campeones = _leer_json(os.path.join(self.dir, "campeones.json")) or {}
        self.campeones = {}
        for k, c in campeones.items():
            pesos = [np.asarray(w) for w in c["pesos"]]
            if any(len(w) != B.N_PARAM for w in pesos):
                nuevos = B.migrar(np.concatenate(pesos), len(pesos))
                if nuevos is None:
                    continue
                c["pesos"] = [w.tolist() for w in np.split(nuevos, len(pesos))]
            self.campeones[int(k)] = c
        try:
            demos = np.load(os.path.join(self.dir, "demos.npz"))
            x = demos["x"]
            if 0 < x.shape[1] < B.N_ENTRADAS:
                x = np.hstack([x, np.zeros((len(x), B.N_ENTRADAS - x.shape[1]))])
            if x.shape[1] == B.N_ENTRADAS:
                self.demo_x, self.demo_y = x, demos["y"]
                self.demo_e = demos["e"] if "e" in demos.files else np.zeros(len(x), dtype=np.int64)
        except (OSError, ValueError, KeyError):
            pass

    def _guardar(self):
        arrays = {"theta": self.theta, "m": self.m, "v": self.v}
        if self.elite is not None:
            arrays["elite"] = self.elite
        tmp = os.path.join(self.dir, "estado.tmp.npz")
        np.savez(tmp, **arrays)
        os.replace(tmp, os.path.join(self.dir, "estado.npz"))
        _guardar_json(os.path.join(self.dir, "estado.json"), {
            "t_adam": self.t_adam, "sigma": self.sigma, "generacion": self.generacion, "etapa": self.etapa,
            "completada": self.completada, "racha": self.racha,
            "record_etapa": self.record_etapa, "sin_mejora": self.sin_mejora,
            "historial": self.historial[-C.HISTORIAL_EN_MEMORIA:],
        })
        _guardar_json(os.path.join(self.dir, "campeones.json"), {str(k): v for k, v in self.campeones.items()})

    def aprender_de_humano(self, x, y, etapa=0):
        self.demo_x = np.concatenate([self.demo_x, x])[-C.MAX_DEMOS:]
        self.demo_y = np.concatenate([self.demo_y, y])[-C.MAX_DEMOS:]
        self.demo_e = np.concatenate([self.demo_e, np.full(len(x), etapa, dtype=np.int64)])[-C.MAX_DEMOS:]
        tmp = os.path.join(self.dir, "demos.tmp.npz")
        np.savez(tmp, x=self.demo_x, y=self.demo_y, e=self.demo_e)
        os.replace(tmp, os.path.join(self.dir, "demos.npz"))
        self.theta = self.theta.copy()
        self.theta[:B.N_PARAM] = B.imitar(self.theta[:B.N_PARAM], self.demo_x, self.demo_y,
                                          max(2, min(C.EPOCAS_IMITACION, 160000 // len(self.demo_x))),
                                          self.rng)
        self.elite = None
        self.m[:] = 0
        self.v[:] = 0
        self.t_adam = 0
        self.sigma = max(self.sigma, C.SIGMA)
        self._guardar()
        return len(self.demo_x)

    def _repasar(self, etapa):
        if not len(self.demo_x):
            return
        de_etapa = self.demo_e == etapa
        idx = np.flatnonzero(de_etapa) if de_etapa.sum() >= C.MIN_DEMOS_ETAPA else np.arange(len(self.demo_x))
        self.theta = self.theta.copy()
        self.theta[:B.N_PARAM] = B.imitar(self.theta[:B.N_PARAM], self.demo_x[idx], self.demo_y[idx], 1,
                                          self.rng, max_lotes=C.LOTES_REPASO)

    def _anotar(self, resumen):
        archivo = os.path.join(self.dir, "historial.csv")
        nuevo = not os.path.exists(archivo)
        with open(archivo, "a", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=COLUMNAS, extrasaction="ignore")
            if nuevo:
                w.writeheader()
            w.writerow(resumen)

    def separar(self, pesos):
        return [pesos[i * B.N_PARAM:(i + 1) * B.N_PARAM] for i in range(self.jugadores)]

    @property
    def etapa_actual(self):
        if self.completada:
            return (self.generacion - 1) % NUMERO_ETAPAS + 1
        return self.etapa

    def mejores_pesos(self):
        return self.separar(self.theta if self.elite is None else self.elite)

    def campeon(self, etapa):
        candidatos = [k for k in self.campeones if k <= etapa] or sorted(self.campeones)
        if not candidatos:
            return None
        elegido = self.campeones[etapa] if etapa in self.campeones else self.campeones[max(candidatos)]
        return [np.array(w) for w in elegido["pesos"]], elegido

    def tareas(self):
        self.eps = self.rng.standard_normal((self.k, self.dim))
        elite = self.theta if self.elite is None else self.elite
        self.poblacion = np.vstack([self.theta, elite, self.theta + self.sigma * self.eps,
                                    self.theta - self.sigma * self.eps])
        self.etapa_evaluada = self.etapa_actual
        semilla = int(self.rng.integers(1 << 31))
        return [(i, self.etapa_evaluada, self.separar(w), semilla) for i, w in enumerate(self.poblacion)]

    def _paso_adam(self, gradiente):
        b1, b2 = 0.9, 0.999
        self.t_adam += 1
        self.m = b1 * self.m + (1 - b1) * gradiente
        self.v = b2 * self.v + (1 - b2) * gradiente ** 2
        m = self.m / (1 - b1 ** self.t_adam)
        v = self.v / (1 - b2 ** self.t_adam)
        self.theta = self.theta + C.TASA * m / (np.sqrt(v) + 1e-8)

    def terminar(self, resultados):
        resultados = [r for _, r in sorted(resultados, key=lambda x: x[0])]
        aptitud = np.array([r["aptitud"] for r in resultados])
        progreso = np.array([r["progreso"] for r in resultados])
        superada = np.array([r["superada"] for r in resultados])
        logro = progreso + np.array([r["dano_jefe"] for r in resultados]) / 100 + superada
        u = rangos_centrados(aptitud[2:])
        gradiente = (u[:self.k] - u[self.k:]) @ self.eps / (2 * self.k * self.sigma)
        self._paso_adam(gradiente - C.DECAIMIENTO_PESOS * self.theta)
        self._repasar(self.etapa_evaluada)
        self.sigma = max(C.SIGMA_MIN, self.sigma * C.SIGMA_DECAE)

        lider = int(np.argmax(aptitud))
        self.elite = self.poblacion[lider].copy()
        etapa = self.etapa_evaluada
        previo = self.campeones.get(etapa)
        clave = (bool(superada[lider]), float(aptitud[lider]))
        if previo is None or clave > (previo["superada"], previo["aptitud"]):
            self.campeones[etapa] = {
                "pesos": [w.tolist() for w in self.separar(self.poblacion[lider])],
                "aptitud": float(aptitud[lider]), "progreso": float(progreso[lider]),
                "superada": bool(superada[lider]), "generacion": self.generacion,
            }

        if not self.completada and logro.max() > self.record_etapa + 0.01:
            self.record_etapa = float(logro.max())
            self.sin_mejora = 0
        elif not self.completada:
            self.sin_mejora += 1
            if self.sin_mejora >= C.GENS_SIN_MEJORA:
                self.sin_mejora = 0
                self.sigma = C.SIGMA_REAVIVAR

        subio = False
        if not self.completada:
            self.racha = self.racha + 1 if superada.any() else 0
            if self.racha >= C.RACHA_PARA_SUBIR:
                subio = True
                self.racha = 0
                self.sigma = C.SIGMA
                self.record_etapa = 0.0
                self.sin_mejora = 0
                if self.etapa < NUMERO_ETAPAS:
                    self.etapa += 1
                else:
                    self.completada = True

        resumen = {
            "generacion": self.generacion, "etapa": etapa, "nombre": NOMBRES[etapa - 1],
            "mejor_progreso": round(100 * float(progreso.max()), 1),
            "promedio_progreso": round(100 * float(progreso.mean()), 1),
            "superaron_pct": round(100 * float(superada.mean()), 1),
            "mejor_aptitud": round(float(aptitud.max()), 1),
            "promedio_aptitud": round(float(aptitud.mean()), 1),
            "bajas_lider": int(resultados[lider]["bajas"]),
            "muertes_promedio": round(float(np.mean([r["muertes"] for r in resultados])), 2),
            "sigma": round(self.sigma, 4), "racha": self.racha, "subio": subio,
            "motivo_lider": resultados[lider]["motivo"],
            "esquives_lider": int(resultados[lider]["esquives"]),
        }
        self.historial.append(resumen)
        self.historial = self.historial[-C.HISTORIAL_EN_MEMORIA:]
        self.generacion += 1
        if subio or self.generacion % C.GUARDAR_CADA == 0:
            self._guardar()
        self._anotar(resumen)
        return resumen
