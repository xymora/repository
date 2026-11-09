import csv
import json
import os

import numpy as np

import cerebro as B
import config as C
from niveles import NIVELES, nivel as obtener_nivel
from simulacion import CHOCO_CUERPO, CHOCO_MURO, HAMBRE, Partida

AQUI = os.path.dirname(os.path.abspath(__file__))
ARCHIVO_ESTADO = "estado.json"
ARCHIVO_CAMPEONES = "campeones.json"
ARCHIVO_HISTORIAL = "historial.csv"
COLUMNAS = ["generacion", "nivel", "nombre", "mejor_frutas", "promedio_frutas", "frutas_media",
            "mejor_aptitud", "promedio_aptitud", "choques_pct", "hambre_pct", "sigma", "subio"]


def carpeta_datos(dir_datos=None):
    d = dir_datos or os.path.join(AQUI, C.CARPETA_DATOS)
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
    rangos[np.argsort(valores)] = np.arange(len(valores))
    return rangos / max(len(valores) - 1, 1) - 0.5


def cargar_campeones(dir_datos=None):
    datos = _leer_json(os.path.join(carpeta_datos(dir_datos), ARCHIVO_CAMPEONES)) or {}
    return {int(k): v for k, v in datos.items() if len(v.get("pesos", ())) == B.N_PARAM}


def cargar_campeon(numero, dir_datos=None):
    campeones = cargar_campeones(dir_datos)
    candidatos = [k for k in campeones if k <= numero] or sorted(campeones)
    if not candidatos:
        return None
    elegido = campeones[max(candidatos)]
    return np.array(elegido["pesos"]), elegido


class Entrenador:
    def __init__(self, poblacion=C.POBLACION, continuar=True, semilla=None, dir_datos=None):
        self.rng = np.random.default_rng(semilla)
        self.dir = carpeta_datos(dir_datos)
        self.k = max(1, (poblacion - 2) // 2)
        self.n = 2 * self.k + 2
        self._desde_cero()
        if continuar:
            self._cargar()

    def _desde_cero(self):
        self.theta = B.pesos_iniciales(self.rng)
        self.m = np.zeros(B.N_PARAM)
        self.v = np.zeros(B.N_PARAM)
        self.t_adam = 0
        self.sigma = C.SIGMA
        self.generacion = 1
        self.nivel = 1
        self.racha = 0
        self.elite = None
        self.historial = []
        self.records = {}
        self.campeones = {}

    def reiniciar(self):
        self._desde_cero()
        for nombre in (ARCHIVO_ESTADO, ARCHIVO_CAMPEONES, ARCHIVO_HISTORIAL):
            try:
                os.remove(os.path.join(self.dir, nombre))
            except OSError:
                pass

    def _cargar(self):
        d = _leer_json(os.path.join(self.dir, ARCHIVO_ESTADO))
        if not d or len(d.get("theta", ())) != B.N_PARAM:
            return
        self.theta = np.array(d["theta"])
        self.m = np.array(d["m"])
        self.v = np.array(d["v"])
        self.t_adam = d["t_adam"]
        self.sigma = d["sigma"]
        self.generacion = d["generacion"]
        self.nivel = d["nivel"]
        self.racha = d["racha"]
        self.elite = np.array(d["elite"]) if d.get("elite") else None
        self.historial = d.get("historial", [])
        self.records = {int(k): v for k, v in d.get("records", {}).items()}
        self.campeones = cargar_campeones(self.dir)

    def _guardar(self):
        _guardar_json(os.path.join(self.dir, ARCHIVO_ESTADO), {
            "theta": self.theta.tolist(), "m": self.m.tolist(), "v": self.v.tolist(),
            "t_adam": self.t_adam, "sigma": self.sigma, "generacion": self.generacion,
            "nivel": self.nivel, "racha": self.racha,
            "elite": None if self.elite is None else self.elite.tolist(),
            "historial": self.historial[-C.HISTORIAL_EN_MEMORIA:], "records": self.records,
        })
        _guardar_json(os.path.join(self.dir, ARCHIVO_CAMPEONES),
                      {str(k): v for k, v in self.campeones.items()})

    def _anotar(self, resumen):
        archivo = os.path.join(self.dir, ARCHIVO_HISTORIAL)
        nuevo = not os.path.exists(archivo)
        with open(archivo, "a", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=COLUMNAS, extrasaction="ignore")
            if nuevo:
                w.writeheader()
            w.writerow(resumen)

    @property
    def nivel_actual(self):
        return obtener_nivel(self.nivel)

    def nueva_partida(self):
        self.eps = self.rng.standard_normal((self.k, B.N_PARAM))
        elite = self.theta if self.elite is None else self.elite
        self.poblacion = np.vstack([self.theta, elite, self.theta + self.sigma * self.eps,
                                    self.theta - self.sigma * self.eps])
        return Partida(self.nivel_actual, self.poblacion, int(self.rng.integers(1 << 31)))

    def _paso_adam(self, gradiente):
        b1, b2 = 0.9, 0.999
        self.t_adam += 1
        self.m = b1 * self.m + (1 - b1) * gradiente
        self.v = b2 * self.v + (1 - b2) * gradiente ** 2
        m = self.m / (1 - b1 ** self.t_adam)
        v = self.v / (1 - b2 ** self.t_adam)
        self.theta = self.theta + C.TASA * m / (np.sqrt(v) + 1e-8)

    def terminar(self, partida):
        aptitud = partida.aptitud()
        u = rangos_centrados(aptitud[2:])
        gradiente = (u[:self.k] - u[self.k:]) @ self.eps / (2 * self.k * self.sigma)
        self._paso_adam(gradiente - C.DECAIMIENTO_PESOS * self.theta)
        self.sigma = max(C.SIGMA_MIN, self.sigma * C.SIGMA_DECAE)

        mejor = int(np.argmax(aptitud))
        self.elite = self.poblacion[mejor].copy()
        frutas = partida.frutas
        lider = int(np.argmax(frutas * 1e6 + aptitud))
        nv = self.nivel_actual
        if frutas[lider] > self.records.get(nv.numero, -1):
            self.records[nv.numero] = int(frutas[lider])
            self.campeones[nv.numero] = {"pesos": self.poblacion[lider].tolist(),
                                         "frutas": int(frutas[lider]),
                                         "generacion": self.generacion}

        self.racha = self.racha + 1 if frutas.max() >= nv.meta else 0
        subio = self.racha >= C.RACHA_PARA_SUBIR and self.nivel < len(NIVELES)
        resumen = {
            "generacion": self.generacion, "nivel": nv.numero, "nombre": nv.nombre,
            "mejor_frutas": int(frutas.max()), "promedio_frutas": round(float(frutas.mean()), 2),
            "frutas_media": int(frutas[0]),
            "mejor_aptitud": round(float(aptitud.max()), 2),
            "promedio_aptitud": round(float(aptitud.mean()), 2),
            "choques_pct": round(100 * float(np.isin(partida.motivo, (CHOCO_MURO, CHOCO_CUERPO)).mean()), 1),
            "hambre_pct": round(100 * float((partida.motivo == HAMBRE).mean()), 1),
            "sigma": round(self.sigma, 4), "racha": self.racha, "meta": nv.meta,
            "record": self.records[nv.numero], "subio": subio,
        }
        if subio:
            self.nivel += 1
            self.racha = 0
            self.sigma = C.SIGMA
        self.historial.append(resumen)
        self.historial = self.historial[-C.HISTORIAL_EN_MEMORIA:]
        self.generacion += 1
        self._guardar()
        self._anotar(resumen)
        return resumen
