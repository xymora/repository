import csv
import json
import os

import numpy as np

import catalogo as K
import cerebro as B
import config as C
from misiones import CURRICULO, Episodio, nombre
from piloto import Instructor
from sensores import N_ENTRADAS, observar

AQUI = os.path.dirname(os.path.abspath(__file__))
COLUMNAS = ["generacion", "leccion", "nombre", "mejor_progreso", "promedio_progreso", "superaron_pct",
            "mejor_aptitud", "promedio_aptitud", "estrellados_pct", "sigma", "racha", "subio", "motivo_lider",
            "perdida", "curriculo", "repaso", "volvio"]
MODOS = ("secuencial", "mezcla", "fija")


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


def iniciar_trabajador():
    bajar_prioridad()
    import signal
    signal.signal(signal.SIGINT, signal.SIG_IGN)


def evaluar(tarea):
    indice, numero, pesos, semilla = tarea
    ep = Episodio(numero, len(pesos), semilla)
    pilotos = B.Pilotos(pesos)
    acc = None
    k = 0
    while not ep.acabado:
        if k % C.DECIDIR_CADA == 0:
            acc = pilotos.decidir(ep)
        ep.paso(acc)
        k += 1
    return indice, [ep.resumen(j) for j in range(ep.n)]


def demos_instructor(numero, semillas, por_semilla=6):
    xs, ys = [], []
    for semilla in semillas:
        ep = Episodio(numero, por_semilla, int(semilla))
        ins = Instructor(por_semilla)
        ruido = np.random.default_rng(int(semilla) + 3)
        traza_x, traza_y, vivos = [], [], []
        k = 0
        while not ep.acabado:
            if k % C.DECIDIR_CADA == 0:
                acc = ins.decidir(ep)
                x = observar(ep)
                traza_x.append(x)
                traza_y.append(B.objetivo_imitacion(acc))
                vivos.append(~ep.terminado & ~ep.arranque.bloqueo())
                for clave in ("elev", "alabeo", "timon"):
                    acc[clave] = np.clip(acc[clave] + ruido.normal(0, 0.15, ep.n) * (np.arange(ep.n) > 0), -1, 1)
            ep.paso(acc)
            k += 1
        ok = ep.exito | (ep.progreso() > 0.8)
        for x, y, v in zip(traza_x, traza_y, vivos):
            sel = v & ok
            if sel.any():
                xs.append(x[sel])
                ys.append(y[sel])
    if not xs:
        return None
    return np.concatenate(xs), np.concatenate(ys)


def imitar_tarea(tarea):
    theta, x, y, e, epocas, semilla, archivo = tarea
    if archivo:
        tmp = archivo.replace(".npz", ".tmp.npz")
        np.savez(tmp, x=x, y=y, e=e)
        os.replace(tmp, archivo)
    return B.imitar(theta, x, y, epocas, np.random.default_rng(semilla))


def demos_tarea(tarea):
    return demos_instructor(*tarea)


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
    def __init__(self, continuar=True, semilla=None, dir_datos=None, poblacion=C.POBLACION, curriculo=None):
        self.curriculo = list(curriculo or CURRICULO)
        self.rng = np.random.default_rng(semilla)
        self.dir = dir_datos or os.path.join(AQUI, C.CARPETA_DATOS)
        os.makedirs(self.dir, exist_ok=True)
        self.k = max(1, (poblacion - 3) // 2)
        self.n = 2 * self.k + 3
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
        self.leccion = self.curriculo[0]
        self.completada = False
        self.ajena = None
        self.modo = "secuencial"
        self.mision_fija = None
        self.perdida = None
        self.racha = 0
        self.elite = None
        self.historial = []
        self.campeones = {}
        self.record = 0.0
        self.sin_mejora = 0
        self.demo_x = np.zeros((0, N_ENTRADAS))
        self.demo_y = np.zeros((0, B.N_SALIDAS))
        self.demo_e = np.zeros(0, dtype=np.int64)
        self.clases = {}
        self.victorias = {}
        self.verif = {}
        self.repasos = {}
        self.pendientes = []

    def necesita_clase(self):
        if self.pendientes:
            return self.pendientes[0]
        if self.completada and self.modo != "fija":
            return None
        n = self.leccion_actual
        ultima = self.clases.get(n)
        if int((self.demo_e == n).sum()) < C.MIN_DEMOS_LECCION and ultima is None:
            return n
        if ultima is not None and self.sin_mejora >= C.GENS_CLASE and self.generacion - ultima >= C.GENS_CLASE:
            return n
        return None

    def superada(self, numero):
        c = self.campeones.get(numero, {})
        return bool(c.get("superada")) and bool(c.get("verificada", True))

    def saltar_superadas(self):
        if self.modo == "fija" or self.completada or self.leccion not in self.curriculo:
            return False
        k = self.curriculo.index(self.leccion)
        pendientes = [m for m in self.curriculo[k:] if not self.superada(m)]
        if pendientes and pendientes[0] == self.leccion:
            return False
        if pendientes:
            self.leccion = pendientes[0]
        else:
            self.leccion = self.curriculo[-1]
            self.completada = True
        self.ajena = None
        self.racha = 0
        self.sigma = C.SIGMA
        self.record = 0.0
        self.sin_mejora = 0
        return True

    def anotar_clase(self, n):
        self.clases[n] = self.generacion
        if n in self.pendientes:
            self.pendientes.remove(n)

    def _adoptar(self, pesos):
        self.theta = np.array(pesos, dtype=np.float64).copy()
        self.elite = self.theta.copy()
        self.m[:] = 0
        self.v[:] = 0
        self.t_adam = 0
        self.sigma = C.SIGMA
        self.victorias = {}

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
        if not meta or arrays["theta"].shape != (B.N_PARAM,):
            return
        self.theta, self.m, self.v = arrays["theta"], arrays["m"], arrays["v"]
        self.elite = arrays["elite"] if "elite" in arrays.files else None
        for clave in ("t_adam", "sigma", "generacion", "leccion", "completada", "racha", "historial", "record",
                      "sin_mejora"):
            setattr(self, clave, meta[clave])
        self.clases = {int(k): v for k, v in meta.get("clases", {}).items()}
        self.victorias = {int(k): v for k, v in meta.get("victorias", {}).items()}
        self.verif = {int(k): v for k, v in meta.get("verif", {}).items()}
        self.repasos = {int(k): v for k, v in meta.get("repasos", {}).items()}
        self.pendientes = [int(k) for k in meta.get("pendientes", [])]
        self.modo = meta.get("modo", "secuencial") if meta.get("modo") in MODOS else "secuencial"
        self.mision_fija = meta.get("mision_fija")
        self.perdida = meta.get("perdida")
        if self.leccion not in self.curriculo:
            self.ajena = (self.leccion, self.completada)
            orden = K.MISIONES.get(self.leccion, {}).get("orden", 0)
            siguientes = [k for k in self.curriculo if K.MISIONES[k]["orden"] >= orden]
            self.leccion = siguientes[0] if siguientes else self.curriculo[-1]
            self.completada = self.completada or not siguientes
        if self.mision_fija not in self.curriculo:
            self.mision_fija = None
            if self.modo == "fija":
                self.modo = "secuencial"
        campeones = _leer_json(os.path.join(self.dir, "campeones.json")) or {}
        self.campeones = {int(k): v for k, v in campeones.items()}
        try:
            d = np.load(os.path.join(self.dir, "demos.npz"))
            if d["x"].shape[1] == N_ENTRADAS:
                self.demo_x, self.demo_y, self.demo_e = d["x"], d["y"], d["e"]
        except (OSError, ValueError, KeyError):
            pass

    def guardar(self):
        arrays = {"theta": self.theta, "m": self.m, "v": self.v}
        if self.elite is not None:
            arrays["elite"] = self.elite
        tmp = os.path.join(self.dir, "estado.tmp.npz")
        np.savez(tmp, **arrays)
        os.replace(tmp, os.path.join(self.dir, "estado.npz"))
        _guardar_json(os.path.join(self.dir, "estado.json"), {
            "t_adam": self.t_adam, "sigma": self.sigma, "generacion": self.generacion,
            "leccion": self.ajena[0] if self.ajena else self.leccion,
            "completada": self.ajena[1] if self.ajena else self.completada, "racha": self.racha, "record": self.record,
            "sin_mejora": self.sin_mejora, "historial": self.historial[-C.HISTORIAL_EN_MEMORIA:],
            "clases": {str(k): v for k, v in self.clases.items()},
            "victorias": {str(k): v for k, v in self.victorias.items()},
            "verif": {str(k): v for k, v in self.verif.items()},
            "repasos": {str(k): v for k, v in self.repasos.items()}, "pendientes": self.pendientes,
            "modo": self.modo, "mision_fija": self.mision_fija, "perdida": self.perdida,
        })
        _guardar_json(os.path.join(self.dir, "campeones.json"), {str(k): v for k, v in self.campeones.items()})

    def _anotar(self, resumen):
        archivo = os.path.join(self.dir, "historial.csv")
        nuevo = not os.path.exists(archivo)
        columnas = COLUMNAS
        if not nuevo:
            with open(archivo, encoding="utf-8", newline="") as f:
                cabecera = next(csv.reader(f), None)
            columnas = cabecera or COLUMNAS
        with open(archivo, "a", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=columnas, extrasaction="ignore")
            if nuevo:
                w.writeheader()
            w.writerow(resumen)

    @property
    def leccion_actual(self):
        if self.modo == "fija" and self.mision_fija is not None:
            return self.mision_fija
        if self.completada:
            return self.curriculo[(self.generacion - 1) % len(self.curriculo)]
        return self.leccion

    def fijar_modo(self, modo, mision=None):
        self.modo = modo
        self.mision_fija = mision if modo == "fija" else None
        self.sin_mejora = 0
        self.record = 0.0
        self.racha = 0
        self.guardar()

    def misiones_tarea(self):
        actual = self.leccion_actual
        lista = [actual] * C.ESCENARIOS
        if self.modo == "mezcla" and C.ESCENARIOS > 1:
            previas = self.curriculo[:self.curriculo.index(actual)] if actual in self.curriculo else []
            if previas:
                for j in range(1, max(1, C.ESCENARIOS // 3) + 1):
                    lista[-j] = int(self.rng.choice(previas))
        return lista

    def mejores_pesos(self):
        return (self.theta if self.elite is None else self.elite).copy()

    def campeon(self, numero):
        if numero in self.campeones:
            c = self.campeones[numero]
        else:
            previos = [k for k in self.campeones if k <= numero]
            if not previos:
                return None
            c = self.campeones[max(previos)]
        return np.array(c["pesos"]), c

    def tareas(self):
        self.eps = self.rng.standard_normal((self.k, B.N_PARAM))
        elite = self.theta if self.elite is None else self.elite
        self.leccion_evaluada = self.leccion_actual
        camp = self.campeones.get(self.leccion_evaluada)
        self.con_campeon = camp is not None
        fijo = np.array(camp["pesos"]) if self.con_campeon else self.theta
        self.poblacion = np.vstack([self.theta, elite, fijo, self.theta + self.sigma * self.eps,
                                    self.theta - self.sigma * self.eps])
        self.misiones_evaluadas = self.misiones_tarea()
        self.semillas = [int(s) for s in self.rng.integers(1, 1 << 30, C.ESCENARIOS)]
        return [(i, m, self.poblacion, s) for i, (m, s) in enumerate(zip(self.misiones_evaluadas, self.semillas))]

    def _paso_adam(self, gradiente):
        b1, b2 = 0.9, 0.999
        self.t_adam += 1
        self.m = b1 * self.m + (1 - b1) * gradiente
        self.v = b2 * self.v + (1 - b2) * gradiente ** 2
        m = self.m / (1 - b1 ** self.t_adam)
        v = self.v / (1 - b2 ** self.t_adam)
        self.theta = self.theta + C.TASA * m / (np.sqrt(v) + 1e-8)

    def _repasar(self, numero, misiones=()):
        if not len(self.demo_x):
            return
        de_leccion = np.isin(self.demo_e, list({numero, *misiones}))
        idx = np.flatnonzero(de_leccion) if de_leccion.sum() >= C.MIN_DEMOS_LECCION else np.arange(len(self.demo_x))
        self.theta = B.imitar(self.theta, self.demo_x[idx], self.demo_y[idx], 1, self.rng, max_lotes=C.LOTES_REPASO)
        self.perdida = B.perdida(self.theta, self.demo_x[idx], self.demo_y[idx], self.rng, 512)

    def preparar_aprendizaje(self, x, y, numero):
        self.demo_x = np.concatenate([self.demo_x, x])[-C.MAX_DEMOS:]
        self.demo_y = np.concatenate([self.demo_y, y])[-C.MAX_DEMOS:]
        self.demo_e = np.concatenate([self.demo_e, np.full(len(x), numero, dtype=np.int64)])[-C.MAX_DEMOS:]
        epocas = max(2, min(C.EPOCAS_IMITACION, 200000 // len(self.demo_x)))
        return (self.theta.copy(), self.demo_x, self.demo_y, self.demo_e, epocas, int(self.rng.integers(1 << 30)),
                os.path.join(self.dir, "demos.npz"))

    def aprender(self, x, y, numero):
        return self.aplicar_aprendizaje(imitar_tarea(self.preparar_aprendizaje(x, y, numero)))

    def aplicar_aprendizaje(self, theta):
        self.theta = theta
        self.elite = None
        self.m[:] = 0
        self.v[:] = 0
        self.t_adam = 0
        self.sigma = max(self.sigma, C.SIGMA)
        self.perdida = B.perdida(self.theta, self.demo_x, self.demo_y, self.rng, 512)
        self.guardar()
        return len(self.demo_x)

    def terminar(self, resultados):
        por_esc = [r for _, r in sorted(resultados, key=lambda x: x[0])]
        numero = self.leccion_evaluada
        misiones = getattr(self, "misiones_evaluadas", [numero] * len(por_esc))
        propios = [rs for rs, m in zip(por_esc, misiones) if m == numero] or por_esc
        aptitud = np.mean([[r["aptitud"] for r in rs] for rs in propios], 0)
        progreso = np.mean([[r["progreso"] for r in rs] for rs in propios], 0)
        sup_frac = np.mean([[r["superada"] and r.get("estabilidad", 1.0) >= C.ESTABILIDAD_MIN for r in rs]
                            for rs in propios], 0)
        estabilidad = np.mean([[r.get("estabilidad", 1.0) for r in rs] for rs in propios], 0)
        cae = np.mean([[r["estrellado"] for r in rs] for rs in propios], 0)
        superada = sup_frac >= C.UMBRAL_SUPERADA + 1e-9
        if len(propios) == len(por_esc):
            u = rangos_centrados(aptitud[3:])
        else:
            u = np.mean([rangos_centrados(np.array([r["aptitud"] for r in rs])[3:]) for rs in por_esc], 0)
        gradiente = (u[:self.k] - u[self.k:]) @ self.eps / (2 * self.k * self.sigma)
        self._paso_adam(gradiente - C.DECAIMIENTO_PESOS * self.theta)
        self.sigma = max(C.SIGMA_MIN, self.sigma * C.SIGMA_DECAE)
        self._repasar(numero, misiones)
        for rs, m in zip(por_esc, misiones):
            if m == numero:
                continue
            ok = bool(rs[0]["superada"] and rs[0].get("estabilidad", 1.0) >= C.ESTABILIDAD_MIN)
            v = (self.repasos.get(m, []) + [ok])[-C.REPASOS_VIGILAR:]
            self.repasos[m] = v
            if len(v) >= C.REPASOS_VIGILAR and not any(v) and self.superada(m) and m not in self.pendientes                     and self.generacion - self.clases.get(m, -10 ** 9) >= C.GENS_CLASE:
                self.pendientes.append(m)
                self.repasos[m] = []

        puntos = aptitud + 1000 * sup_frac
        lider = int(np.argmax(puntos))
        self.elite = self.poblacion[lider].copy()
        previo = self.campeones.get(numero)
        volvio = ""
        if self.con_campeon and previo is not None:
            gana = bool(puntos[2] >= np.delete(puntos, 2).max())
            v = (self.victorias.get(numero, []) + [gana])[-C.GENS_VOLVER:]
            self.victorias[numero] = v
            if len(v) >= C.GENS_VOLVER and sum(v) >= C.VICTORIAS_VOLVER:
                volvio = previo["generacion"]
                self.theta = self.poblacion[2].copy()
                self.elite = self.theta.copy()
                self.m[:] = 0
                self.v[:] = 0
                self.t_adam = 0
                self.sigma = C.SIGMA
                self.victorias[numero] = []
        clave = (float(sup_frac[lider]), float(aptitud[lider]))
        if previo is not None and "estabilidad" not in previo:
            previo_clave = (previo.get("sup_frac", float(previo["superada"])), -np.inf)
        else:
            previo_clave = (previo.get("sup_frac", float(previo["superada"])), previo["aptitud"]) if previo else None
        mismo = lider == 2 and self.con_campeon and previo is not None
        nuevo = False
        if previo is None or clave > previo_clave:
            nuevo = not mismo
            self.campeones[numero] = {
                "pesos": self.poblacion[lider].tolist(), "aptitud": float(aptitud[lider]),
                "progreso": float(progreso[lider]), "superada": bool(superada[lider]),
                "sup_frac": float(sup_frac[lider]), "estabilidad": float(estabilidad[lider]),
                "generacion": previo["generacion"] if mismo else self.generacion,
                "verificada": bool(previo.get("verificada", True)) if mismo else False,
            }
        camp = self.campeones[numero]
        curso = self.modo == "fija" or not self.completada
        if nuevo:
            self.verif[numero] = [bool(superada[lider])]
            if camp["superada"] and curso:
                self._adoptar(camp["pesos"])
                volvio = self.generacion
        elif self.con_campeon and camp["superada"] and not camp.get("verificada", True):
            self.verif[numero] = (self.verif.get(numero, []) + [bool(superada[2])])[-C.VERIFICAR_GENS:]
        if camp["superada"] and not camp.get("verificada", True) and sum(self.verif.get(numero, [])) >= C.VERIFICAR_OK:
            camp["verificada"] = True

        logro = progreso + sup_frac
        sigue = not self.completada or self.modo == "fija"
        if sigue and logro.max() > self.record + 0.01:
            self.record = float(logro.max())
            self.sin_mejora = 0
        elif sigue:
            self.sin_mejora += 1
            if self.sin_mejora >= C.GENS_SIN_MEJORA:
                self.sin_mejora = 0
                self.sigma = C.SIGMA_REAVIVAR

        subio = False
        if self.modo == "fija":
            self.racha = self.racha + 1 if superada.any() else 0
        elif not self.completada:
            self.racha = self.racha + 1 if superada.any() else 0
            if self.racha >= C.RACHA_PARA_SUBIR or self.superada(self.leccion):
                subio = True
                if camp["superada"]:
                    self._adoptar(camp["pesos"])
                self.ajena = None
                self.racha = 0
                self.sigma = C.SIGMA
                self.record = 0.0
                self.sin_mejora = 0
                k = self.curriculo.index(self.leccion)
                if k + 1 < len(self.curriculo):
                    self.leccion = self.curriculo[k + 1]
                else:
                    self.completada = True
                self.saltar_superadas()

        resumen = {
            "generacion": self.generacion, "leccion": numero, "nombre": nombre(numero),
            "mejor_progreso": round(100 * float(progreso.max()), 1),
            "promedio_progreso": round(100 * float(progreso.mean()), 1),
            "superaron_pct": round(100 * float(superada.mean()), 1),
            "mejor_aptitud": round(float(aptitud.max()), 1),
            "promedio_aptitud": round(float(aptitud.mean()), 1),
            "estrellados_pct": round(100 * float(cae.mean()), 1),
            "sigma": round(self.sigma, 4), "racha": self.racha, "subio": subio,
            "motivo_lider": propios[0][lider]["motivo"],
            "perdida": None if self.perdida is None else round(self.perdida, 5), "curriculo": self.modo,
            "repaso": next((m for m in misiones if m != numero), ""), "volvio": volvio,
        }
        self.historial.append(resumen)
        self.historial = self.historial[-C.HISTORIAL_EN_MEMORIA:]
        self.generacion += 1
        if subio or self.generacion % C.GUARDAR_CADA == 0:
            self.guardar()
        self._anotar(resumen)
        return resumen
