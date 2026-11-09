import csv
import json
import multiprocessing as mp
import os
import threading
import time

import numpy as np

import cerebro as B
import config as C
import misiones as MS
from doctrina import Doctrina
from simulacion import Episodio

COLUMNAS = ["generacion", "mision", "nombre", "mejor_proteccion", "promedio_proteccion", "superaron_pct",
            "mejor_aptitud", "promedio_aptitud", "desperdicio_lider", "usados_lider", "sigma", "racha", "subio",
            "clase"]
SEMILLAS_POR_INDIVIDUO = 2


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


def combinar(resumenes):
    r = dict(resumenes[0])
    for k in ("aptitud", "proteccion", "desperdicio_frac", "usados", "dano", "salvado"):
        r[k] = float(np.mean([x[k] for x in resumenes]))
    r["superada"] = all(x["superada"] for x in resumenes)
    r["destruida"] = any(x["destruida"] for x in resumenes)
    return r


def evaluar(tarea):
    indice, numero, pesos, semillas, cfg = tarea
    mis, extra = MS.preparar(numero, cfg)
    res = [Episodio(mis, B.ControladorRed(pesos), s, **extra).correr() for s in semillas]
    return indice, combinar(res)


def clase(tarea):
    numero, semilla, cfg = tarea
    mis, extra = MS.preparar(numero, cfg)
    ep = Episodio(mis, Doctrina(), semilla, demos=True, **extra)
    ep.correr()
    if not ep.demos_x:
        return np.zeros((0, B.N_ENTRADAS)), np.zeros((0, 2))
    return np.array(ep.demos_x), np.array(ep.demos_y)


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
    def __init__(self, continuar=True, semilla=None, dir_datos=None, poblacion=C.POBLACION):
        self.rng = np.random.default_rng(semilla)
        self.dir = dir_datos or os.path.join(C.RAIZ, C.CARPETA_DATOS)
        os.makedirs(self.dir, exist_ok=True)
        self.k = max(1, (poblacion - 2) // 2)
        self.n = 2 * self.k + 2
        self.bloqueo = threading.Lock()
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
        self.mision = 1
        self.completada = False
        self.racha = 0
        self.elite = None
        self.historial = []
        self.campeones = {}
        self.record = -1e9
        self.sin_mejora = 0
        self.clases = {}
        self.cfg = {"baterias": 0, "lanzadores": 0}
        self.demo_x = np.zeros((0, B.N_ENTRADAS))
        self.demo_y = np.zeros((0, 2))
        self.demo_e = np.zeros(0, dtype=np.int64)

    def reiniciar(self):
        with self.bloqueo:
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
        if not meta or arrays["theta"].shape != (B.N_PARAM,):
            return
        self.theta, self.m, self.v = arrays["theta"], arrays["m"], arrays["v"]
        self.elite = arrays["elite"] if "elite" in arrays.files else None
        for clave in ("t_adam", "sigma", "generacion", "mision", "completada", "racha", "historial", "record",
                      "sin_mejora"):
            setattr(self, clave, meta[clave])
        self.clases = {int(k): v for k, v in meta.get("clases", {}).items()}
        campeones = _leer_json(os.path.join(self.dir, "campeones.json")) or {}
        self.campeones = {int(k): v for k, v in campeones.items()}
        self.cfg.update(meta.get("cfg", {}))
        faltan = [n for n in range(1, MS.NUMERO_MISIONES + 1) if n not in self.campeones]
        if self.completada and faltan:
            self.completada = False
            self.mision = faltan[0]
            self.racha = 0
            self.sin_mejora = 0
            self.record = -1e9

        try:
            d = np.load(os.path.join(self.dir, "demos.npz"))
            if d["x"].shape[1] == B.N_ENTRADAS:
                self.demo_x, self.demo_y, self.demo_e = d["x"], d["y"], d["e"]
        except (OSError, ValueError, KeyError):
            pass

    def guardar(self):
        with self.bloqueo:
            self._guardar()

    def _guardar(self):
        arrays = {"theta": self.theta, "m": self.m, "v": self.v}
        if self.elite is not None:
            arrays["elite"] = self.elite
        tmp = os.path.join(self.dir, "estado.tmp.npz")
        np.savez(tmp, **arrays)
        os.replace(tmp, os.path.join(self.dir, "estado.npz"))
        _guardar_json(os.path.join(self.dir, "estado.json"), {
            "t_adam": self.t_adam, "sigma": self.sigma, "generacion": self.generacion, "mision": self.mision,
            "completada": self.completada, "racha": self.racha, "record": self.record,
            "sin_mejora": self.sin_mejora, "historial": self.historial[-C.HISTORIAL_EN_MEMORIA:],
            "clases": {str(k): v for k, v in self.clases.items()}, "cfg": self.cfg,
        })
        _guardar_json(os.path.join(self.dir, "campeones.json"), {str(k): v for k, v in self.campeones.items()})
        tmp = os.path.join(self.dir, "demos.tmp.npz")
        np.savez(tmp, x=self.demo_x, y=self.demo_y, e=self.demo_e)
        os.replace(tmp, os.path.join(self.dir, "demos.npz"))

    def _anotar(self, resumen):
        archivo = os.path.join(self.dir, "historial.csv")
        nuevo = not os.path.exists(archivo)
        with open(archivo, "a", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=COLUMNAS, extrasaction="ignore")
            if nuevo:
                w.writeheader()
            w.writerow(resumen)

    @property
    def mision_actual(self):
        if self.completada:
            return (self.generacion - 1) % MS.NUMERO_MISIONES + 1
        return self.mision

    def mejores_pesos(self):
        return (self.theta if self.elite is None else self.elite).copy()

    def campeon(self, numero=None):
        if not self.campeones:
            return None
        if numero is None:
            numero = max(self.campeones)
        if numero not in self.campeones:
            previos = [k for k in self.campeones if k <= numero] or list(self.campeones)
            numero = max(previos)
        c = self.campeones[numero]
        return np.array(c["pesos"]), c

    def necesita_clase(self):
        if self.completada:
            return False
        numero = self.mision
        ultima = self.clases.get(numero)
        if ultima is None:
            return True
        return self.sin_mejora > 0 and self.sin_mejora % C.GENS_CLASE == 0 and self.generacion - ultima >= C.GENS_CLASE

    def tareas_clase(self):
        return [(self.mision, int(self.rng.integers(1 << 30)), dict(self.cfg)) for _ in range(C.EPISODIOS_CLASE)]

    def aplicar_clase(self, lotes):
        X = [x for x, _ in lotes if len(x)]
        if not X:
            return 0
        X = np.vstack(X)
        Y = np.vstack([y for _, y in lotes if len(y)])
        with self.bloqueo:
            self.clases[self.mision] = self.generacion
            self._agregar_demos(X, Y, self.mision)
            de_mision = self.demo_e == self.mision
            self.theta = B.imitar(self.theta, self.demo_x[de_mision], self.demo_y[de_mision], 25, self.rng)
            self.elite = None
            self.m[:] = 0
            self.v[:] = 0
            self.t_adam = 0
            self.sigma = max(self.sigma, C.SIGMA)
        return len(X)

    def _agregar_demos(self, X, Y, numero):
        self.demo_x = np.concatenate([self.demo_x, X])[-C.MAX_DEMOS:]
        self.demo_y = np.concatenate([self.demo_y, Y])[-C.MAX_DEMOS:]
        self.demo_e = np.concatenate([self.demo_e, np.full(len(X), numero, dtype=np.int64)])[-C.MAX_DEMOS:]

    def aprender_de_humano(self, X, Y, numero):
        with self.bloqueo:
            self._agregar_demos(X, Y, numero)
            epocas = max(2, min(C.EPOCAS_IMITACION, 120000 // max(len(self.demo_x), 1)))
            self.theta = B.imitar(self.theta, self.demo_x, self.demo_y, epocas, self.rng)
            self.elite = None
            self.m[:] = 0
            self.v[:] = 0
            self.t_adam = 0
            self.sigma = max(self.sigma, C.SIGMA)
            self._guardar()
        return len(self.demo_x)

    def tareas(self):
        with self.bloqueo:
            self.eps = self.rng.standard_normal((self.k, B.N_PARAM))
            elite = self.theta if self.elite is None else self.elite
            self.poblacion = np.vstack([self.theta, elite, self.theta + self.sigma * self.eps,
                                        self.theta - self.sigma * self.eps])
            self.mision_evaluada = self.mision_actual
            self.semillas = [int(s) for s in self.rng.integers(1 << 30, size=SEMILLAS_POR_INDIVIDUO)]
            cfg = dict(self.cfg)
            return [(i, self.mision_evaluada, w, self.semillas, cfg) for i, w in enumerate(self.poblacion)]

    def _paso_adam(self, gradiente):
        b1, b2 = 0.9, 0.999
        self.t_adam += 1
        self.m = b1 * self.m + (1 - b1) * gradiente
        self.v = b2 * self.v + (1 - b2) * gradiente ** 2
        m = self.m / (1 - b1 ** self.t_adam)
        v = self.v / (1 - b2 ** self.t_adam)
        self.theta = self.theta + C.TASA * m / (np.sqrt(v) + 1e-8)

    def _repasar(self, numero):
        if not len(self.demo_x):
            return
        de_mision = self.demo_e == numero
        idx = np.flatnonzero(de_mision) if de_mision.sum() >= 200 else np.arange(len(self.demo_x))
        self.theta = B.imitar(self.theta, self.demo_x[idx], self.demo_y[idx], 1, self.rng, max_lotes=C.LOTES_REPASO)

    def terminar(self, resultados, hubo_clase=False):
        with self.bloqueo:
            return self._terminar(resultados, hubo_clase)

    def _terminar(self, resultados, hubo_clase):
        resultados = [r for _, r in sorted(resultados, key=lambda x: x[0])]
        aptitud = np.array([r["aptitud"] for r in resultados])
        prot = np.array([r["proteccion"] for r in resultados])
        superada = np.array([r["superada"] for r in resultados])
        u = rangos_centrados(aptitud[2:])
        gradiente = (u[:self.k] - u[self.k:]) @ self.eps / (2 * self.k * self.sigma)
        self._paso_adam(gradiente - C.DECAIMIENTO_PESOS * self.theta)
        self.sigma = max(C.SIGMA_MIN, self.sigma * C.SIGMA_DECAE)
        numero = self.mision_evaluada
        self._repasar(numero)

        lider = int(np.argmax(aptitud + 1000 * superada))
        self.elite = self.poblacion[lider].copy()
        previo = self.campeones.get(numero)
        clave = (bool(superada[lider]), float(aptitud[lider]))
        if previo is None or clave > (previo["superada"], previo["aptitud"]):
            self.campeones[numero] = {
                "pesos": self.poblacion[lider].tolist(), "aptitud": float(aptitud[lider]),
                "proteccion": float(prot[lider]), "superada": bool(superada[lider]),
                "generacion": self.generacion,
            }
        logro = float(aptitud.max())
        if not self.completada and logro > self.record + 0.5:
            self.record = logro
            self.sin_mejora = 0
        elif not self.completada:
            self.sin_mejora += 1
            if self.sin_mejora % C.GENS_SIN_MEJORA == 0:
                self.sigma = C.SIGMA_REAVIVAR

        subio = False
        if not self.completada:
            self.racha = self.racha + 1 if superada.any() else 0
            if self.racha >= C.RACHA_PARA_SUBIR:
                subio = True
                self.racha = 0
                self.sigma = C.SIGMA
                self.record = -1e9
                self.sin_mejora = 0
                if self.mision < MS.NUMERO_MISIONES:
                    self.mision += 1
                else:
                    self.completada = True

        resumen = {
            "generacion": self.generacion, "mision": numero, "nombre": MS.NOMBRES[numero - 1],
            "mejor_proteccion": round(100 * float(prot.max()), 1),
            "promedio_proteccion": round(100 * float(prot.mean()), 1),
            "superaron_pct": round(100 * float(superada.mean()), 1),
            "mejor_aptitud": round(float(aptitud.max()), 1),
            "promedio_aptitud": round(float(aptitud.mean()), 1),
            "desperdicio_lider": round(100 * resultados[lider]["desperdicio_frac"], 1),
            "usados_lider": round(resultados[lider]["usados"], 1),
            "sigma": round(self.sigma, 4), "racha": self.racha, "subio": subio, "clase": hubo_clase,
        }
        self.historial.append(resumen)
        self.historial = self.historial[-C.HISTORIAL_EN_MEMORIA:]
        self.generacion += 1
        if subio or self.generacion % C.GUARDAR_CADA == 0:
            self._guardar()
        self._anotar(resumen)
        return resumen


class HiloEntrenamiento:
    def __init__(self, entrenador, procesos=None, al_terminar=None):
        self.ent = entrenador
        self.procesos = procesos or max(1, (os.cpu_count() or 2) - 1)
        self.al_terminar = al_terminar
        self.activo = False
        self.pausado = False
        self.detener = False
        self.estado = "Listo"
        self.instantanea = None
        self.ultimo = None
        self._hilo = None
        self._pool = None
        self.gens_por_min = 0.0

    def iniciar(self):
        if self._hilo is not None and self._hilo.is_alive():
            return
        self.detener = False
        self.activo = True
        self._hilo = threading.Thread(target=self._bucle, daemon=True)
        self._hilo.start()

    def _bucle(self):
        self._pool = mp.Pool(self.procesos, initializer=bajar_prioridad)
        tiempos = []
        try:
            while not self.detener:
                if self.pausado:
                    self.estado = "En pausa"
                    time.sleep(0.2)
                    continue
                hubo = False
                if self.ent.necesita_clase():
                    self.estado = f"Clase del instructor · misión {self.ent.mision}"
                    lotes = self._mapa(clase, self.ent.tareas_clase())
                    if lotes is None:
                        break
                    self.ent.aplicar_clase(lotes)
                    hubo = True
                t0 = time.perf_counter()
                tareas = self.ent.tareas()
                self.instantanea = (self.ent.mision_evaluada, tareas[0][2].copy(), self.ent.semillas[0],
                                    self.ent.generacion, tareas[0][4])
                self.estado = f"Evaluando generación {self.ent.generacion}"
                res = self._mapa(evaluar, tareas, chunksize=2)
                if res is None or self.detener:
                    break
                self.ultimo = self.ent.terminar(res, hubo)
                tiempos.append(time.perf_counter() - t0)
                tiempos = tiempos[-10:]
                self.gens_por_min = 60 / max(np.mean(tiempos), 1e-6)
                if self.al_terminar:
                    self.al_terminar(self.ultimo)
        finally:
            self._pool.terminate()
            self._pool = None
            self.activo = False
            self.estado = "Detenido"

    def _mapa(self, funcion, tareas, chunksize=1):
        r = self._pool.map_async(funcion, tareas, chunksize=chunksize)
        while not r.ready():
            if self.detener:
                return None
            r.wait(0.1)
        return r.get()

    def parar(self, esperar=True):
        self.detener = True
        if esperar and self._hilo is not None:
            self._hilo.join(timeout=30)
        self.ent.guardar()


def entrenar_consola(minutos=None, generaciones=None, dir_datos=None):
    import sys
    try:
        sys.stdout.reconfigure(errors="replace")
    except Exception:
        pass
    ent = Entrenador(dir_datos=dir_datos)
    hilo = HiloEntrenamiento(ent, al_terminar=lambda r: print(
        f"gen {r['generacion']:5d} · misión {r['mision']} {r['nombre'][:22]:22s} · protección mejor "
        f"{r['mejor_proteccion']:5.1f}% prom {r['promedio_proteccion']:5.1f}% · superaron {r['superaron_pct']:5.1f}% · "
        f"desperdicio {r['desperdicio_lider']:4.1f}% · σ {r['sigma']:.4f}{' · CLASE' if r['clase'] else ''}"
        f"{' · ¡SUBE DE MISIÓN!' if r['subio'] else ''}", flush=True))
    print(f"Entrenando con {hilo.procesos} procesos. Ctrl+C para detener y guardar.", flush=True)
    hilo.iniciar()
    t0 = time.time()
    try:
        while hilo.activo:
            time.sleep(0.5)
            if minutos and time.time() - t0 > minutos * 60:
                break
            if generaciones and ent.generacion > generaciones:
                break
    except KeyboardInterrupt:
        pass
    print("Deteniendo y guardando…", flush=True)
    hilo.parar()
    return ent
