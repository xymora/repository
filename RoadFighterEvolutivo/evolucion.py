import csv
import json
import os

import numpy as np

import cerebro as B
import config as C
from pista import Pista
from simulacion import Carrera

AQUI = os.path.dirname(os.path.abspath(__file__))
COLUMNAS = ["generacion", "nivel", "pista", "mejor", "promedio", "media_theta", "llegaron_pct",
            "lider_llego", "vel_lider_kmh", "choques_lider", "sigma", "arcoiris_lider",
            "arcoiris_prom", "rebases_lider", "rebases_prom"]
FORMATO = 2


def carpeta_datos(dir_datos=None):
    d = dir_datos or os.path.join(AQUI, C.CARPETA_DATOS)
    d = d if os.path.isabs(d) else os.path.join(AQUI, d)
    os.makedirs(d, exist_ok=True)
    return d


def _atomico(archivo, escribir, binario=False):
    tmp = archivo + ".tmp"
    with open(tmp, "wb" if binario else "w", **({} if binario else {"encoding": "utf-8", "newline": ""})) as f:
        escribir(f)
    os.replace(tmp, archivo)


def cargar_mejor(dir_datos=None):
    archivo = os.path.join(carpeta_datos(dir_datos), C.ARCHIVO_MEJOR)
    try:
        with open(archivo, encoding="utf-8") as f:
            d = json.load(f)
        w = np.array(d["pesos"], dtype=float)
        if len(w) != B.N_PARAM:
            return None
        return w, d, B.Normalizador.desde(np.array(d["normalizador"]))
    except (OSError, ValueError, KeyError):
        return None


def cargar_salon(dir_datos=None):
    archivo = os.path.join(carpeta_datos(dir_datos), C.ARCHIVO_SALON)
    try:
        with np.load(archivo) as z:
            d = {k: z[k] for k in z.files}
        return d if d["pesos"].shape[1] == B.N_PARAM else None
    except (OSError, ValueError, KeyError):
        return None


def elegir_generaciones(salon, k=6):
    n = len(salon["generacion"])
    if n == 0:
        return []
    return np.unique(np.round(np.linspace(0, n - 1, min(k, n))).astype(int)).tolist()


def resumen_generacion(r):
    txt = (f"Gen {r['generacion']:4d} · {r['pista']} (nivel {r['nivel']}) · mejor {r['mejor']:7.1f}"
           f" · prom {r['promedio']:6.1f} · llegaron {r['llegaron']:5.1f} %")
    if r["lider_llego"]:
        txt += f" · líder a {r['vel_lider']:.0f} km/h"
    txt += f" · arcoíris líder {r['arcoiris_lider']}/{r['arcoiris_pista']} (prom {r['arcoiris_prom']:.1f})"
    txt += f" · rebases líder {r['rebases_lider']} (prom {r['rebases_prom']:.0f})"
    if r.get("campeona_anterior") is not None:
        txt += f" · {r['mejor'] - r['campeona_anterior']:+.1f} vs élite"
    if r.get("subio"):
        txt += f"  >>> SUBE A {C.NIVELES[r['nivel_nuevo'] - 1][0].upper()}"
    return txt


def rangos_centrados(x):
    r = np.empty(len(x))
    r[np.argsort(x)] = np.arange(len(x))
    return r / max(len(x) - 1, 1) - 0.5


class Entrenador:
    def __init__(self, n=C.POBLACION, continuar=True, semilla=None, dir_datos=None, guardar=True,
                 algoritmo=None):
        self.dir = carpeta_datos(dir_datos)
        self.algoritmo = algoritmo or C.ALGORITMO
        self.n = int(n)
        if self.algoritmo == "es" and self.n % 2:
            self.n += 1
        self.n_param = B.N_PARAM
        self.rng = np.random.default_rng(semilla)
        self.guardar = guardar
        self.generacion = 1
        self.nivel = 1
        self.racha = 0
        self.historial = []
        self.salon = {"generacion": [], "nivel": [], "aptitud": [], "pesos": [], "normalizador": []}
        self.norm = B.Normalizador()
        self.maestro = False
        self.theta = B.aleatorios(1, self.rng)[0]
        self.elite = self.theta.copy()
        self.adam_m = np.zeros(self.n_param)
        self.adam_v = np.zeros(self.n_param)
        self.adam_t = 0
        self.sigma = C.ES_SIGMA if self.algoritmo == "es" else C.SIGMA_MUTACION
        self.pob = B.aleatorios(self.n, self.rng)
        self.hay_campeon = False
        if continuar:
            self._cargar()
        self._preparar()

    def ruta(self, nombre):
        return os.path.join(self.dir, nombre)

    def _cargar(self):
        try:
            with np.load(self.ruta(C.ARCHIVO_POBLACION)) as z:
                if int(z["formato"]) != FORMATO or str(z["algoritmo"]) != self.algoritmo \
                        or z["theta"].shape[0] != self.n_param:
                    raise ValueError("otro formato")
                self.generacion, self.nivel = int(z["generacion"]), int(z["nivel"])
                self.racha, self.sigma = int(z["racha"]), float(z["sigma"])
                self.theta, self.elite = z["theta"].copy(), z["elite"].copy()
                self.adam_m, self.adam_v, self.adam_t = z["adam_m"].copy(), z["adam_v"].copy(), int(z["adam_t"])
                self.norm = B.Normalizador.desde(z["normalizador"])
                self.maestro = bool(z["maestro"]) if "maestro" in z.files else False
                pob = z["pob"]
                if len(pob) >= self.n:
                    self.pob = pob[:self.n].copy()
                else:
                    self.pob[:len(pob)] = pob
                self.hay_campeon = True
        except (OSError, KeyError, ValueError):
            pass
        s = cargar_salon(self.dir)
        if s is not None:
            self.salon = {k: list(v) for k, v in s.items()}
        try:
            with open(self.ruta(C.ARCHIVO_HISTORIAL), encoding="utf-8") as f:
                for fila in csv.DictReader(f):
                    self.historial.append({"generacion": int(fila["generacion"]),
                                           "nivel": int(fila["nivel"]),
                                           "mejor": float(fila["mejor"]),
                                           "promedio": float(fila["promedio"]),
                                           "llegaron": float(fila["llegaron_pct"]),
                                           "arcoiris_lider": int(fila.get("arcoiris_lider") or 0),
                                           "arcoiris_prom": float(fila.get("arcoiris_prom") or 0)})
        except (OSError, KeyError, ValueError):
            pass

    def _guardar(self, resumen, pesos_lider):
        info = {"generacion": resumen["generacion"], "nivel": resumen["nivel"],
                "aptitud": resumen["mejor"], "algoritmo": self.algoritmo,
                "normalizador": self.norm.estado().tolist(), "pesos": pesos_lider.tolist()}
        _atomico(self.ruta(C.ARCHIVO_MEJOR), lambda f: json.dump(info, f))
        self._guardar_poblacion(self.generacion + 1)
        sal = {k: np.array(v) for k, v in self.salon.items()}
        _atomico(self.ruta(C.ARCHIVO_SALON), lambda f: np.savez(f, **sal), binario=True)
        archivo = self.ruta(C.ARCHIVO_HISTORIAL)
        nuevo = not os.path.exists(archivo) or resumen["generacion"] == 1
        if not nuevo:
            with open(archivo, encoding="utf-8", newline="") as f:
                filas = list(csv.reader(f))
            if filas and filas[0] != COLUMNAS:
                viejas = [dict(zip(filas[0], r)) for r in filas[1:] if r]
                with open(archivo, "w", encoding="utf-8", newline="") as f:
                    w = csv.writer(f)
                    w.writerow(COLUMNAS)
                    for d in viejas:
                        w.writerow([d.get(k, "") for k in COLUMNAS])
        with open(archivo, "w" if nuevo else "a", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            if nuevo:
                w.writerow(COLUMNAS)
            w.writerow([resumen["generacion"], resumen["nivel"], resumen["pista"],
                        f"{resumen['mejor']:.2f}", f"{resumen['promedio']:.2f}",
                        f"{resumen['media_theta']:.2f}", f"{resumen['llegaron']:.1f}",
                        int(resumen["lider_llego"]), f"{resumen['vel_lider']:.1f}",
                        resumen["choques_lider"], f"{self.sigma:.4f}", resumen["arcoiris_lider"],
                        f"{resumen['arcoiris_prom']:.2f}", resumen["rebases_lider"],
                        f"{resumen['rebases_prom']:.1f}"])

    def _guardar_poblacion(self, generacion):
        _atomico(self.ruta(C.ARCHIVO_POBLACION),
                 lambda f: np.savez(f, formato=FORMATO, algoritmo=self.algoritmo,
                                    generacion=generacion, nivel=self.nivel,
                                    racha=self.racha, sigma=self.sigma, theta=self.theta,
                                    elite=self.elite, adam_m=self.adam_m, adam_v=self.adam_v,
                                    adam_t=self.adam_t, normalizador=self.norm.estado(),
                                    pob=self.pob, maestro=self.maestro), binario=True)

    @property
    def necesita_maestro(self):
        return bool(getattr(C, "APRENDER_DEL_MAESTRO", False)) and not self.maestro

    def aplicar_maestro(self, theta, norm):
        import shutil
        import time as _t
        if self.guardar and any(os.path.exists(self.ruta(f)) for f in
                                (C.ARCHIVO_POBLACION, C.ARCHIVO_MEJOR, C.ARCHIVO_HISTORIAL)):
            destino = self.dir.rstrip("\\/") + _t.strftime("_respaldo_%Y%m%d_%H%M%S")
            shutil.copytree(self.dir, destino)
        rng = self.rng
        self.theta = np.array(theta, dtype=float)
        self.elite = self.theta.copy()
        self.norm = norm
        self.adam_m = np.zeros(self.n_param)
        self.adam_v = np.zeros(self.n_param)
        self.adam_t = 0
        if self.algoritmo == "es":
            self.sigma = C.ES_SIGMA
        else:
            self.pob = self.theta + rng.normal(0, 0.02, (self.n, self.n_param))
            self.pob[0] = self.theta
        self.maestro = True
        self.hay_campeon = True
        self._preparar()
        if self.guardar:
            self._guardar_poblacion(self.generacion)

    def guardar_avance(self):
        if self.guardar:
            self._guardar_poblacion(self.generacion)

    def reiniciar(self):
        for nombre in (C.ARCHIVO_MEJOR, C.ARCHIVO_POBLACION, C.ARCHIVO_HISTORIAL, C.ARCHIVO_SALON):
            try:
                os.remove(self.ruta(nombre))
            except OSError:
                pass
        self.__init__(self.n, continuar=False, dir_datos=self.dir, guardar=self.guardar,
                      algoritmo=self.algoritmo)

    def _poblacion_es(self):
        k = (self.n - 2) // 2
        self.eps = self.rng.standard_normal((k, self.n_param))
        pert = np.empty((2 * k, self.n_param))
        pert[0::2] = self.theta + self.sigma * self.eps
        pert[1::2] = self.theta - self.sigma * self.eps
        return np.vstack([self.theta, self.elite, pert])

    def _preparar(self):
        semilla = int(self.rng.integers(1 << 30))
        self.pista = Pista(self.nivel, semilla)
        if self.algoritmo == "es":
            self.pob = self._poblacion_es()
        self.carrera = Carrera(self.pista, self.pob, normalizador=self.norm)

    def avanzar(self, pasos):
        self.carrera.correr(pasos)
        if self.carrera.terminado:
            return self._evolucionar()
        return None

    def correr_generacion(self):
        while True:
            r = self.avanzar(10_000)
            if r is not None:
                return r

    def _evolucionar(self):
        c = self.carrera
        apt = c.aptitud()
        orden = np.argsort(-apt)
        lider = int(orden[0])
        llego = bool(c.llegaron()[lider])
        resumen = {
            "generacion": self.generacion, "nivel": self.nivel, "pista": self.pista.nombre,
            "mejor": float(apt[lider]), "promedio": float(apt.mean()),
            "media_theta": float(apt[0]),
            "llegaron": 100.0 * float(c.llegaron().mean()), "lider_llego": llego,
            "vel_lider": float(c.velocidad_media_kmh()[lider]),
            "choques_lider": int(c.choques[lider]),
            "arcoiris_lider": int(c.arcoiris_n[lider]),
            "arcoiris_prom": float(c.arcoiris_n.mean()),
            "rebases_lider": int(c.rebases[lider]),
            "rebases_prom": float(c.rebases.mean()),
            "arcoiris_pista": int((self.pista.t_tipo == C.ARCOIRIS).sum()),
            "campeona_anterior": (float(apt[1]) if self.algoritmo == "es" else float(apt[0]))
            if self.hay_campeon else None,
            "subio": False, "algoritmo": self.algoritmo,
        }
        if llego:
            self.racha += 1
            if self.racha >= C.RACHA_PARA_SUBIR and self.nivel < C.NIVEL_MAX:
                self.nivel += 1
                self.racha = 0
                resumen["subio"] = True
                resumen["nivel_nuevo"] = self.nivel
        else:
            self.racha = 0
        pesos_lider = self.pob[lider].copy()
        for k, v in (("generacion", self.generacion), ("nivel", resumen["nivel"]),
                     ("aptitud", resumen["mejor"]), ("pesos", pesos_lider),
                     ("normalizador", self.norm.estado())):
            self.salon[k].append(v)
        if self.algoritmo == "es":
            self._paso_es(apt, pesos_lider)
        else:
            self._paso_ga(apt, orden)
        self.hay_campeon = True
        if c.muestras:
            self.norm.actualizar(np.concatenate(c.muestras))
        self.historial.append({"generacion": self.generacion, "nivel": resumen["nivel"],
                               "mejor": resumen["mejor"], "promedio": resumen["promedio"],
                               "llegaron": resumen["llegaron"],
                               "arcoiris_lider": resumen["arcoiris_lider"],
                               "arcoiris_prom": resumen["arcoiris_prom"]})
        if self.guardar:
            self._guardar(resumen, pesos_lider)
        self.generacion += 1
        self._preparar()
        return resumen

    def _paso_es(self, apt, pesos_lider):
        u = rangos_centrados(apt[2:])
        g = ((u[0::2] - u[1::2])[:, None] * self.eps).sum(0) / (2 * len(self.eps) * self.sigma)
        b1, b2 = C.ES_BETAS
        self.adam_t += 1
        self.adam_m = b1 * self.adam_m + (1 - b1) * g
        self.adam_v = b2 * self.adam_v + (1 - b2) * g * g
        mh = self.adam_m / (1 - b1 ** self.adam_t)
        vh = self.adam_v / (1 - b2 ** self.adam_t)
        self.theta = self.theta + C.ES_LR * (mh / (np.sqrt(vh) + 1e-8) - C.ES_DECAIMIENTO * self.theta)
        self.elite = pesos_lider

    def _torneo(self, apt):
        idx = self.rng.integers(self.n, size=C.TORNEO)
        return self.pob[idx[np.argmax(apt[idx])]]

    def _paso_ga(self, apt, orden):
        previos = [h["mejor"] for h in self.historial if h["nivel"] == self.nivel]
        if len(previos) >= 20 and np.mean(previos[-10:]) <= np.mean(previos[-20:-10]):
            self.sigma = min(self.sigma * 1.1, C.SIGMA_MAX)
        else:
            self.sigma = max(self.sigma * 0.97, C.SIGMA_MUTACION)
        nueva = [self.pob[i].copy() for i in orden[:C.ELITE]]
        n_inmig = int(round(C.INMIGRANTES * self.n))
        while len(nueva) < self.n - n_inmig:
            a = self._torneo(apt)
            if self.rng.random() < C.PROB_CRUCE:
                b = self._torneo(apt)
                hijo = np.where(self.rng.random(self.n_param) < 0.5, a, b)
            else:
                hijo = a.copy()
            muta = self.rng.random(self.n_param) < C.PROB_MUTACION
            nueva.append(hijo + muta * self.rng.normal(0, self.sigma, self.n_param))
        if n_inmig:
            nueva.extend(B.aleatorios(n_inmig, self.rng))
        self.pob = np.array(nueva)
