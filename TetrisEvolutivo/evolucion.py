import csv
import json
import math
import os

import numpy as np

import config as C
from motor import N_CARACT, Juego
from niveles import NIVELES, nivel as obtener_nivel

AQUI = os.path.dirname(os.path.abspath(__file__))
COLUMNAS = ["generacion", "nivel", "nombre", "mejor_lineas", "promedio_lineas", "mejor_aptitud",
            "promedio_aptitud", "superaron_pct", "sigma", "racha", "subio"]
ESCALA = np.array([4.0, 4.0, 10.0, 10.0, 3.0, 3.0, 8.0, 3.0])


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
    indice, numero, pesos, semillas = tarea
    resultados = [Juego(obtener_nivel(numero), s).jugar(pesos) for s in semillas]
    return indice, {
        "aptitud": float(np.mean([r["aptitud"] for r in resultados])),
        "lineas": float(np.mean([r["lineas"] for r in resultados])),
        "piezas": float(np.mean([r["piezas"] for r in resultados])),
        "superados": sum(r["superado"] for r in resultados),
        "motivo": resultados[0]["motivo"],
    }


def unitario(v):
    n = np.linalg.norm(v)
    return v / n if n > 1e-12 else v


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


class CMA:
    def __init__(self, n, poblacion, rng):
        self.n, self.lam = n, poblacion
        self.mu = poblacion // 2
        w = math.log(self.mu + 0.5) - np.log(np.arange(1, self.mu + 1))
        self.w = w / w.sum()
        self.mueff = 1 / (self.w ** 2).sum()
        self.cc = (4 + self.mueff / n) / (n + 4 + 2 * self.mueff / n)
        self.cs = (self.mueff + 2) / (n + self.mueff + 5)
        self.c1 = 2 / ((n + 1.3) ** 2 + self.mueff)
        self.cmu = min(1 - self.c1, 2 * (self.mueff - 2 + 1 / self.mueff) / ((n + 2) ** 2 + self.mueff))
        self.damps = 1 + 2 * max(0.0, math.sqrt((self.mueff - 1) / (n + 1)) - 1) + self.cs
        self.chi = math.sqrt(n) * (1 - 1 / (4 * n) + 1 / (21 * n * n))
        self.m = unitario(rng.normal(size=n))
        self.sigma = C.SIGMA_INICIAL
        self.cov = np.eye(n)
        self.pc = np.zeros(n)
        self.ps = np.zeros(n)
        self.g = 0

    def _base(self):
        self.cov = (self.cov + self.cov.T) / 2
        d2, b = np.linalg.eigh(self.cov)
        return b, np.sqrt(np.maximum(d2, 1e-20))

    def muestrear(self, rng):
        b, d = self._base()
        self.z = rng.standard_normal((self.lam, self.n))
        self.y = (self.z * d) @ b.T
        return self.m + self.sigma * self.y

    def actualizar(self, aptitud):
        orden = np.argsort(-aptitud, kind="stable")[:self.mu]
        yw = self.w @ self.y[orden]
        b, d = self._base()
        self.m = self.m + self.sigma * yw
        inv_raiz = b @ np.diag(1 / d) @ b.T
        self.ps = (1 - self.cs) * self.ps + math.sqrt(self.cs * (2 - self.cs) * self.mueff) * inv_raiz @ yw
        self.g += 1
        hsig = (np.linalg.norm(self.ps) / math.sqrt(1 - (1 - self.cs) ** (2 * self.g)) / self.chi
                < 1.4 + 2 / (self.n + 1))
        self.pc = (1 - self.cc) * self.pc + hsig * math.sqrt(self.cc * (2 - self.cc) * self.mueff) * yw
        rango_mu = (self.y[orden].T * self.w) @ self.y[orden]
        self.cov = ((1 - self.c1 - self.cmu) * self.cov
                    + self.c1 * (np.outer(self.pc, self.pc) + (1 - hsig) * self.cc * (2 - self.cc) * self.cov)
                    + self.cmu * rango_mu)
        self.sigma *= math.exp(self.cs / self.damps * (np.linalg.norm(self.ps) / self.chi - 1))
        self.normalizar()

    def normalizar(self):
        k = np.linalg.norm(self.m)
        if k > 1e-9:
            self.m = self.m / k
            self.sigma = self.sigma / k
        self.sigma = float(min(max(self.sigma, C.SIGMA_MIN), C.SIGMA_MAX))

    def estado(self):
        return {"m": self.m.tolist(), "sigma": self.sigma, "cov": self.cov.tolist(), "pc": self.pc.tolist(),
                "ps": self.ps.tolist(), "g": self.g}

    def cargar(self, d):
        self.m, self.sigma = np.array(d["m"]), float(d["sigma"])
        self.cov, self.pc, self.ps = np.array(d["cov"]), np.array(d["pc"]), np.array(d["ps"])
        self.g = int(d["g"])


def ajustar_a_humano(m, F, mascara, elegidas, pasos, tasa):
    fs = F / ESCALA
    v = unitario(m * ESCALA) * 3
    v0 = v.copy()
    filas = np.arange(len(fs))
    for _ in range(pasos):
        s = np.where(mascara, fs @ v, -np.inf)
        s -= s.max(1, keepdims=True)
        p = np.exp(s)
        p /= p.sum(1, keepdims=True)
        g = (fs[filas, elegidas] - np.einsum("dk,dkf->df", p, fs)).mean(0) - 0.02 * (v - v0)
        v += tasa * g / max(np.abs(g).max(), 1e-9) * 0.3
    return unitario(v / ESCALA)


class Entrenador:
    def __init__(self, continuar=True, semilla=None, dir_datos=None, poblacion=C.POBLACION):
        self.rng = np.random.default_rng(semilla)
        self.dir = dir_datos or os.path.join(AQUI, C.CARPETA_DATOS)
        os.makedirs(self.dir, exist_ok=True)
        self.poblacion = poblacion
        self._desde_cero()
        if continuar:
            self._cargar()

    def _desde_cero(self):
        self.cma = CMA(N_CARACT, self.poblacion, self.rng)
        self.generacion = 1
        self.nivel = 1
        self.completada = False
        self.racha = 0
        self.elite = None
        self.ultimas_aptitudes = []
        self.historial = []
        self.campeones = {}
        self.demo_f = np.zeros((0, C.MAX_CANDIDATOS, N_CARACT))
        self.demo_m = np.zeros((0, C.MAX_CANDIDATOS), bool)
        self.demo_k = np.zeros(0, np.int64)

    def reiniciar(self):
        self._desde_cero()
        for nombre in ("estado.json", "campeones.json", "historial.csv", "demos.npz"):
            try:
                os.remove(os.path.join(self.dir, nombre))
            except OSError:
                pass

    def _cargar(self):
        meta = _leer_json(os.path.join(self.dir, "estado.json"))
        if not meta or len(meta["cma"]["m"]) != N_CARACT:
            return
        self.cma.cargar(meta["cma"])
        for clave in ("generacion", "nivel", "completada", "racha", "historial"):
            setattr(self, clave, meta[clave])
        self.elite = np.array(meta["elite"]) if meta.get("elite") else None
        self.ultimas_aptitudes = meta.get("ultimas_aptitudes", [])
        campeones = _leer_json(os.path.join(self.dir, "campeones.json")) or {}
        self.campeones = {int(k): v for k, v in campeones.items()}
        try:
            d = np.load(os.path.join(self.dir, "demos.npz"))
            self.demo_f, self.demo_m, self.demo_k = d["f"], d["m"], d["k"]
        except (OSError, ValueError, KeyError):
            pass

    def _guardar(self):
        _guardar_json(os.path.join(self.dir, "estado.json"), {
            "cma": self.cma.estado(), "generacion": self.generacion, "nivel": self.nivel,
            "completada": self.completada, "racha": self.racha,
            "elite": None if self.elite is None else self.elite.tolist(),
            "ultimas_aptitudes": self.ultimas_aptitudes,
            "historial": self.historial[-C.HISTORIAL_EN_MEMORIA:],
        })
        _guardar_json(os.path.join(self.dir, "campeones.json"), {str(k): v for k, v in self.campeones.items()})

    def _anotar(self, resumen):
        archivo = os.path.join(self.dir, "historial.csv")
        nuevo = not os.path.exists(archivo)
        with open(archivo, "a", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=COLUMNAS, extrasaction="ignore")
            if nuevo:
                w.writeheader()
            w.writerow(resumen)

    @property
    def nivel_actual(self):
        if self.completada:
            return (self.generacion - 1) % len(NIVELES) + 1
        return self.nivel

    def mejores_pesos(self):
        return self.cma.m.copy() if self.elite is None else self.elite.copy()

    def campeon(self, numero):
        if numero in self.campeones:
            return np.array(self.campeones[numero]["pesos"]), self.campeones[numero]
        previos = [k for k in self.campeones if k <= numero]
        if previos:
            c = self.campeones[max(previos)]
            return np.array(c["pesos"]), c
        return None

    def tareas(self):
        self.x = self.cma.muestrear(self.rng)
        self.nivel_evaluado = self.nivel_actual
        semillas = [int(s) for s in self.rng.integers(1 << 31, size=C.JUEGOS)]
        return [(i, self.nivel_evaluado, self.x[i], semillas) for i in range(len(self.x))]

    def terminar(self, resultados):
        resultados = [r for _, r in sorted(resultados, key=lambda a: a[0])]
        aptitud = np.array([r["aptitud"] for r in resultados])
        lineas = np.array([r["lineas"] for r in resultados])
        superados = np.array([r["superados"] for r in resultados])
        self.cma.actualizar(aptitud)
        self._repasar()
        lider = int(np.argmax(aptitud))
        self.elite = unitario(self.x[lider])
        self.ultimas_aptitudes = sorted(aptitud.tolist(), reverse=True)
        numero = self.nivel_evaluado
        meta = obtener_nivel(numero).meta
        todo = bool(superados[lider] == C.JUEGOS)
        previo = self.campeones.get(numero)
        if previo is None or (todo, float(aptitud[lider])) > (previo["superado"], previo["aptitud"]):
            self.campeones[numero] = {"pesos": self.elite.tolist(), "aptitud": float(aptitud[lider]),
                                      "lineas": float(lineas[lider]), "superado": todo,
                                      "generacion": self.generacion}
        subio = False
        if not self.completada:
            self.racha = self.racha + 1 if todo else 0
            if self.racha >= C.RACHA_PARA_SUBIR:
                subio = True
                self.racha = 0
                self.cma.sigma = max(self.cma.sigma, C.SIGMA_TRAS_SUBIR)
                if self.nivel < len(NIVELES):
                    self.nivel += 1
                else:
                    self.completada = True
        resumen = {
            "generacion": self.generacion, "nivel": numero, "nombre": obtener_nivel(numero).nombre,
            "meta": meta, "mejor_lineas": round(float(lineas.max()), 1),
            "promedio_lineas": round(float(lineas.mean()), 1),
            "mejor_aptitud": round(float(aptitud.max()), 1), "promedio_aptitud": round(float(aptitud.mean()), 1),
            "superaron_pct": round(100 * float((superados == C.JUEGOS).mean()), 1),
            "sigma": round(self.cma.sigma, 4), "racha": self.racha, "subio": subio,
            "motivo_lider": resultados[lider]["motivo"],
        }
        self.historial.append(resumen)
        self.historial = self.historial[-C.HISTORIAL_EN_MEMORIA:]
        self.generacion += 1
        if subio or self.generacion % C.GUARDAR_CADA == 0:
            self._guardar()
        self._anotar(resumen)
        return resumen

    def _repasar(self):
        if not len(self.demo_k):
            return
        idx = self.rng.choice(len(self.demo_k), min(500, len(self.demo_k)), replace=False)
        nuevo = ajustar_a_humano(self.cma.m, self.demo_f[idx], self.demo_m[idx], self.demo_k[idx],
                                 C.PASOS_REPASO, C.TASA_IMITACION)
        self.cma.m = nuevo
        self.cma.normalizar()

    def aprender_de_humano(self, decisiones):
        n = len(decisiones)
        f = np.zeros((n, C.MAX_CANDIDATOS, N_CARACT))
        m = np.zeros((n, C.MAX_CANDIDATOS), bool)
        k = np.zeros(n, np.int64)
        for i, (feats, elegida) in enumerate(decisiones):
            q = min(len(feats), C.MAX_CANDIDATOS)
            f[i, :q], m[i, :q], k[i] = feats[:q], True, elegida
        self.demo_f = np.concatenate([self.demo_f, f])[-C.MAX_DEMOS:]
        self.demo_m = np.concatenate([self.demo_m, m])[-C.MAX_DEMOS:]
        self.demo_k = np.concatenate([self.demo_k, k])[-C.MAX_DEMOS:]
        tmp = os.path.join(self.dir, "demos.tmp.npz")
        np.savez(tmp, f=self.demo_f, m=self.demo_m, k=self.demo_k)
        os.replace(tmp, os.path.join(self.dir, "demos.npz"))
        self.cma.m = ajustar_a_humano(self.cma.m, self.demo_f, self.demo_m, self.demo_k, C.PASOS_IMITACION,
                                      C.TASA_IMITACION)
        self.cma.sigma = max(self.cma.sigma, C.SIGMA_TRAS_SUBIR)
        self.cma.normalizar()
        self.cma.pc[:] = 0
        self.cma.ps[:] = 0
        self.elite = None
        self._guardar()
        return len(self.demo_k)
