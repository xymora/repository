import csv
import json
import os

import numpy as np

import config as C
import programa as PG
from laberinto import Nivel
from simulacion import Partida

AQUI = os.path.dirname(os.path.abspath(__file__))
COLUMNAS = ["generacion", "nivel", "laberinto", "mejor", "promedio", "campeona", "limpiaron_pct",
            "lider_limpio", "puntos_lider", "progreso_lider", "progreso_prom", "fantasmas_lider",
            "fantasmas_prom", "muertes_lider", "tiempo_lider", "nodos_lider", "nodos_prom",
            "programa_lider"]
FORMATO = 1


def carpeta_datos(dir_datos=None):
    d = dir_datos or os.path.join(AQUI, C.CARPETA_DATOS)
    d = d if os.path.isabs(d) else os.path.join(AQUI, d)
    os.makedirs(d, exist_ok=True)
    return d


def _atomico(archivo, escribir):
    tmp = archivo + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="") as f:
        escribir(f)
    os.replace(tmp, archivo)


def cargar_mejor(dir_datos=None):
    try:
        with open(os.path.join(carpeta_datos(dir_datos), C.ARCHIVO_MEJOR), encoding="utf-8") as f:
            d = json.load(f)
        return d["programa"], d
    except (OSError, ValueError, KeyError):
        return None


def cargar_salon(dir_datos=None):
    try:
        with open(os.path.join(carpeta_datos(dir_datos), C.ARCHIVO_SALON), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def elegir_generaciones(salon, k=6):
    n = len(salon)
    if n == 0:
        return []
    return np.unique(np.round(np.linspace(0, n - 1, min(k, n))).astype(int)).tolist()


def resumen_generacion(r):
    txt = (f"Gen {r['generacion']:4d} · {r['laberinto']} (nivel {r['nivel']}) · mejor {r['mejor']:7.1f}"
           f" · prom {r['promedio']:6.1f} · limpiaron {r['llegaron']:5.1f} %")
    txt += f" · líder {r['puntos_lider']:.0f} pts, {r['progreso_lider']:.0f} % de los puntos"
    if r["lider_llego"]:
        txt += f" en {r['tiempo_lider']:.0f} s"
    txt += f" · fantasmas líder {r['fantasmas_lider']} · programa {r['nodos_lider']} nodos"
    if r.get("campeona_anterior") is not None:
        txt += f" · {r['mejor'] - r['campeona_anterior']:+.1f} vs campeona"
    if r.get("subio"):
        txt += f"  >>> SUBE A {C.NIVELES[r['nivel_nuevo'] - 1][0].upper()}"
    if r.get("nuevo_laberinto"):
        txt += f"  >>> ¡LABERINTO PERFECTO! NUEVO LABERINTO #{r['numero_nuevo']}"
    return txt


class Entrenador:
    algoritmo = "gp"

    def __init__(self, n=C.POBLACION, continuar=True, semilla=None, dir_datos=None, guardar=True):
        self.dir = carpeta_datos(dir_datos)
        self.n = int(n)
        self.rng = np.random.default_rng(semilla)
        self.guardar = guardar
        self.generacion = 1
        self.nivel = 1
        self.racha = 0
        self.lab_num = 1
        self.semilla_lab = None
        self.usados = []
        self.historial = []
        self.salon = []
        self.pob = PG.poblacion_inicial(self.n, self.rng)
        self.hay_campeon = False
        if continuar:
            self._cargar()
        self._preparar()

    def ruta(self, nombre):
        return os.path.join(self.dir, nombre)

    def _cargar(self):
        try:
            with open(self.ruta(C.ARCHIVO_POBLACION), encoding="utf-8") as f:
                d = json.load(f)
            if d.get("formato") != FORMATO:
                raise ValueError("otro formato")
            self.generacion, self.nivel, self.racha = int(d["generacion"]), int(d["nivel"]), int(d["racha"])
            self.lab_num = int(d.get("lab_num", 1))
            self.semilla_lab = d.get("semilla_lab")
            self.usados = [int(u) for u in d.get("usados", [])]
            pob = d["pob"]
            self.pob = (pob + self.pob)[:self.n]
            self.hay_campeon = True
        except (OSError, KeyError, ValueError):
            pass
        self.salon = cargar_salon(self.dir) or []
        try:
            with open(self.ruta(C.ARCHIVO_HISTORIAL), encoding="utf-8") as f:
                for fila in csv.DictReader(f):
                    self.historial.append({"generacion": int(fila["generacion"]),
                                           "nivel": int(fila["nivel"]),
                                           "mejor": float(fila["mejor"]),
                                           "promedio": float(fila["promedio"]),
                                           "llegaron": float(fila["limpiaron_pct"]),
                                           "progreso_lider": float(fila["progreso_lider"]),
                                           "progreso_prom": float(fila["progreso_prom"]),
                                           "fantasmas_lider": int(fila["fantasmas_lider"]),
                                           "fantasmas_prom": float(fila["fantasmas_prom"]),
                                           "nodos_lider": int(fila["nodos_lider"]),
                                           "nodos_prom": float(fila["nodos_prom"])})
        except (OSError, KeyError, ValueError):
            pass

    def _guardar(self, resumen, lider):
        info = {"generacion": resumen["generacion"], "nivel": resumen["nivel"],
                "aptitud": resumen["mejor"], "nodos": PG.nodos(lider),
                "texto": PG.como_texto(lider), "programa": lider}
        _atomico(self.ruta(C.ARCHIVO_MEJOR), lambda f: json.dump(info, f, ensure_ascii=False, indent=1))
        self._guardar_poblacion(self.generacion + 1)
        _atomico(self.ruta(C.ARCHIVO_SALON), lambda f: json.dump(self.salon, f))
        archivo = self.ruta(C.ARCHIVO_HISTORIAL)
        nuevo = not os.path.exists(archivo) or resumen["generacion"] == 1
        with open(archivo, "w" if nuevo else "a", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            if nuevo:
                w.writerow(COLUMNAS)
            w.writerow([resumen["generacion"], resumen["nivel"], resumen["laberinto"],
                        f"{resumen['mejor']:.2f}", f"{resumen['promedio']:.2f}",
                        "" if resumen["campeona_anterior"] is None else f"{resumen['campeona_anterior']:.2f}",
                        f"{resumen['llegaron']:.1f}", int(resumen["lider_llego"]),
                        f"{resumen['puntos_lider']:.0f}", f"{resumen['progreso_lider']:.1f}",
                        f"{resumen['progreso_prom']:.1f}", resumen["fantasmas_lider"],
                        f"{resumen['fantasmas_prom']:.2f}", resumen["muertes_lider"],
                        f"{resumen['tiempo_lider']:.1f}", resumen["nodos_lider"],
                        f"{resumen['nodos_prom']:.1f}", PG.texto(lider)])

    def _guardar_poblacion(self, generacion):
        _atomico(self.ruta(C.ARCHIVO_POBLACION),
                 lambda f: json.dump({"formato": FORMATO, "generacion": generacion,
                                      "nivel": self.nivel, "racha": self.racha, "lab_num": self.lab_num,
                                      "semilla_lab": self.semilla_lab, "usados": self.usados,
                                      "pob": self.pob}, f))

    def guardar_avance(self):
        if self.guardar:
            self._guardar_poblacion(self.generacion)

    def reiniciar(self):
        for nombre in (C.ARCHIVO_MEJOR, C.ARCHIVO_POBLACION, C.ARCHIVO_HISTORIAL, C.ARCHIVO_SALON):
            try:
                os.remove(self.ruta(nombre))
            except OSError:
                pass
        self.__init__(self.n, continuar=False, dir_datos=self.dir, guardar=self.guardar)

    def infinito(self):
        return C.NIVELES[self.nivel - 1][1] is None

    def _nuevo_laberinto(self):
        from laberinto import generar
        huellas = self.__dict__.setdefault("_huellas", {})
        for s in self.usados:
            if s not in huellas:
                huellas[s] = hash(tuple(generar(s)))
        vistos = set(huellas.values())
        for _ in range(500):
            s = 1000 + int(self.rng.integers(1, 10_000_000))
            h = hash(tuple(generar(s)))
            if s not in huellas and h not in vistos:
                break
        huellas[s] = h
        self.semilla_lab = s
        self.usados.append(s)

    def _preparar(self):
        semilla = int(self.rng.integers(1 << 30))
        if self.infinito():
            if self.semilla_lab is None:
                self._nuevo_laberinto()
            self.niv = Nivel(self.nivel, semilla, semilla_lab=self.semilla_lab, numero=self.lab_num)
        else:
            self.niv = Nivel(self.nivel, semilla)
        self.partida = Partida(self.niv, self.pob)

    def avanzar(self, pasos):
        self.partida.correr(pasos)
        if self.partida.terminado:
            return self._evolucionar()
        return None

    def correr_generacion(self):
        while True:
            r = self.avanzar(10_000)
            if r is not None:
                return r

    def _evolucionar(self):
        c = self.partida
        apt = c.aptitud()
        tam = np.array([PG.nodos(p) for p in self.pob])
        orden = np.lexsort((tam, -apt))
        lider = int(orden[0])
        llego = bool(c.llegaron()[lider])
        resumen = {
            "generacion": self.generacion, "nivel": self.nivel, "laberinto": self.niv.nombre,
            "mejor": float(apt[lider]), "promedio": float(apt.mean()),
            "llegaron": 100.0 * float(c.llegaron().mean()), "lider_llego": llego,
            "puntos_lider": float(c.marcador[lider]),
            "progreso_lider": float(c.progreso()[lider]),
            "progreso_prom": float(c.progreso().mean()),
            "fantasmas_lider": int(c.fant_comidos[lider]),
            "fantasmas_prom": float(c.fant_comidos.mean()),
            "muertes_lider": int(c.muertes[lider]),
            "tiempo_lider": float(c.t_fin[lider]),
            "nodos_lider": int(tam[lider]), "nodos_prom": float(tam.mean()),
            "campeona_anterior": float(apt[0]) if self.hay_campeon else None,
            "subio": False, "algoritmo": "gp",
        }
        perfecto = c.llegaron() & (c.muertes <= C.PERFECTO_MAX_MUERTES)
        resumen["perfectos"] = int(perfecto.sum())
        if self.infinito():
            if perfecto.any():
                self.lab_num += 1
                self._nuevo_laberinto()
                resumen["nuevo_laberinto"] = True
                resumen["numero_nuevo"] = self.lab_num
        elif llego:
            self.racha += 1
            if self.racha >= C.RACHA_PARA_SUBIR and self.nivel < C.NIVEL_MAX:
                self.nivel += 1
                self.racha = 0
                resumen["subio"] = True
                resumen["nivel_nuevo"] = self.nivel
        else:
            self.racha = 0
        campeona = PG.copiar(self.pob[lider])
        self.salon.append({"generacion": self.generacion, "nivel": resumen["nivel"],
                           "aptitud": resumen["mejor"], "programa": campeona,
                           "semilla_lab": self.niv.semilla_lab})
        self._nueva_poblacion(apt, tam, orden)
        self.hay_campeon = True
        self.historial.append({k: resumen[k] for k in ("generacion", "nivel", "mejor", "promedio", "llegaron",
                                                        "progreso_lider", "progreso_prom", "fantasmas_lider",
                                                        "fantasmas_prom", "nodos_lider", "nodos_prom")})
        if self.guardar:
            self._guardar(resumen, campeona)
        self.generacion += 1
        self._preparar()
        return resumen

    def _torneo(self, sel):
        idx = self.rng.integers(self.n, size=C.TORNEO)
        return self.pob[idx[np.argmax(sel[idx])]]

    def _nueva_poblacion(self, apt, tam, orden):
        rng = self.rng
        sel = apt - C.PARSIMONIA * tam
        nueva = [PG.copiar(self.pob[i]) for i in orden[:C.ELITE]]
        n_inmig = int(round(C.INMIGRANTES * self.n))
        while len(nueva) < self.n - n_inmig:
            padre = self._torneo(sel)
            r = rng.random()
            if r < C.P_CRUCE:
                hijo = PG.cruce(padre, self._torneo(sel), rng)
            elif r < C.P_CRUCE + C.P_MUT_SUBARBOL:
                hijo = PG.mut_subarbol(padre, rng)
            elif r < C.P_CRUCE + C.P_MUT_SUBARBOL + C.P_MUT_PUNTO:
                hijo = PG.mut_punto(padre, rng)
            else:
                hijo = PG.copiar(padre)
            hijo = PG.plegar(hijo)
            if PG.profundidad(hijo) > C.MAX_PROF or PG.nodos(hijo) > C.MAX_NODOS:
                hijo = PG.copiar(padre)
            nueva.append(hijo)
        nueva += PG.poblacion_inicial(n_inmig, rng)
        self.pob = nueva
