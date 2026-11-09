import csv
import json
import multiprocessing as mp
import os
import pickle
import threading
import time

import numpy as np

import cerebro
import config as C
import detector
import instrucciones as INS
import perfiles
from agente import TAM_RAM_VISTA, Juego, bits, evaluar, indice, iniciar_trabajador, ram_vista
from consola import cabecera, leer_rom


def _escribir_json(ruta, datos):
    tmp = ruta + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False, indent=1)
    os.replace(tmp, ruta)


def _leer_json(ruta, defecto):
    try:
        with open(ruta, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return defecto


class Entrenador:
    def __init__(self, ruta_rom, continuar=True, poblacion=C.POBLACION, semilla=None, procesos=C.PROCESOS):
        self.ruta_rom = ruta_rom
        self.info = cabecera(leer_rom(ruta_rom))
        self.id = self.info["id"]
        self.dir = os.path.join(C.CARPETA_DATOS, self.id)
        os.makedirs(self.dir, exist_ok=True)
        self.ruta_sav = os.path.join(self.dir, "partida.sav")
        self.poblacion = poblacion + poblacion % 2
        self.procesos = procesos
        self.rng = np.random.default_rng(semilla)
        self.cerrojo = threading.RLock()
        self.pool = None
        self.hilo = None
        self.corriendo = False
        self.mensajes = []
        self.texto = INS.buscar(self.id, ruta_rom)
        self.leer_instrucciones(self.texto, guardar=False)
        self.perfil = _leer_json(os.path.join(self.dir, "perfil.json"),
                                 {"vidas": None, "puntos": [], "progreso": [], "auto": True, "pesos": {},
                                  "version": C.VERSION_PERFIL})
        self.candidatos = []
        self.candidatos_pos = []
        self.candidatos_mapa = []
        self.limpiar_archivo = False
        self.rehacer_archivo = False
        self.bits_enc = np.zeros(TAM_RAM_VISTA, np.uint8)
        self.bits_apa = np.zeros(TAM_RAM_VISTA, np.uint8)
        self.bits_gens = 0
        self.bits_cambios = np.zeros(TAM_RAM_VISTA, np.int64)
        self.bits_eps = 0
        self.banderas = None
        version = self.perfil.get("version", 1)
        if version < C.VERSION_PERFIL:
            if self.perfil.get("auto", True):
                if version < 2:
                    self.perfil.update({"vidas": None, "puntos": [], "posicion": None, "mapa": [], "busquedas": 0})
                    self.limpiar_archivo = True
                else:
                    self.perfil["mapa"] = []
                    self.rehacer_archivo = True
            self.perfil["version"] = C.VERSION_PERFIL
        nombre, conocido = perfiles.buscar(self.info["titulo"])
        if conocido and self.perfil.get("auto", True) and self.perfil.get("conocido") != nombre:
            self.perfil.update(json.loads(json.dumps(conocido)))
            self.perfil["conocido"] = nombre
            self.rehacer_archivo = True
            self.avisar(f"Perfil conocido de {nombre}: posición, mapa, nivel, experiencia, medallas y Pokédex "
                        "se leen directo de la memoria")
        self.progreso = (0, 0)
        self.gen_actual = None
        self.ultimas_aptitudes = None
        self._nuevo()
        if continuar:
            self.cargar()
        if self.limpiar_archivo:
            demos = self.demos
            self._nuevo(conservar_archivo=True)
            self.demos = demos
            self.archivo = {}
            if len(demos["accion"]) >= 32:
                self.imitar(C.PASOS_IMITACION)
            self.guardar_perfil()
            self.avisar("Perfil del juego actualizado: la red empieza de nuevo (imitando tus jugadas) y se buscan "
                        "otra vez vidas, puntos y posición; ya no se premian las pantallas de menú")
        elif self.rehacer_archivo:
            if self.perfil.get("banderas_rango"):
                self.banderas = self._mascara_rango()
            self.rehacer_claves()
            self.guardar_perfil()
        self.preparar_inicio()

    def mascara_banderas(self):
        return self.banderas if self.banderas is not None else np.zeros(0, np.uint8)

    def _juego_local(self):
        j = getattr(self, "_juego", None)
        if j is None:
            j = self._juego = Juego(self.ruta_rom, self.acciones, self.perfil)
        j.configurar(self.acciones, self.perfil, self.banderas if self.banderas is not None else np.zeros(0, np.uint8))
        return j

    def rehacer_claves(self):
        with self.cerrojo:
            j = self._juego_local()
            nuevo = {}
            for k, c in self.archivo.items():
                j.gb.restaurar(c["estado"])
                ram = ram_vista(j.gb)
                kp = j.clave_pos(ram)
                clave = k if kp is None else kp
                c = {**c, "avance": j.puntaje(ram), "elegida": 0}
                if clave not in nuevo or c["avance"] > nuevo[clave]["avance"]:
                    nuevo[clave] = c
                self.conocidas.add(clave)
            self.archivo = nuevo
            if nuevo:
                self.avisar(f"Puntos de control reorganizados por lugar y avance: {len(nuevo)}")

    def leer_instrucciones(self, texto, guardar=True):
        self.texto = texto
        if guardar:
            INS.guardar(self.id, texto)
        self.analisis = INS.analizar(texto)
        nuevas = self.analisis["acciones"]
        if getattr(self, "acciones", None) is not None and nuevas != self.acciones:
            self.acciones = nuevas
            self._nuevo(conservar_archivo=True)
            self.avisar("Instrucciones nuevas: cambian las acciones, la red empieza de nuevo")
        self.acciones = nuevas

    def _nuevo(self, conservar_archivo=False):
        n = len(self.acciones)
        self.theta = cerebro.inicial(n, C.OCULTAS, self.rng, self._flechas())
        self.adam = cerebro.Adam(len(self.theta))
        self.generacion = 0
        self.historial = []
        self.mejor = None
        self.mejor_theta = self.theta.copy()
        self.sigma = C.SIGMA
        if not conservar_archivo:
            self.archivo = {}
            self.conocidas = set()
            self.inicio = None
        self.demos = {"obs": np.zeros((0, 360), np.uint8), "prev": np.zeros((0, 360), np.uint8),
                      "ultima": np.zeros(0, np.int16), "quieto": np.zeros(0, np.float32),
                      "accion": np.zeros(0, np.int16), "rasgos": np.zeros((0, cerebro.RASGOS), np.float16)}

    def _flechas(self):
        from consola import ABAJO, ARRIBA, DERECHA, IZQUIERDA
        return [((DERECHA in a) - (IZQUIERDA in a), (ABAJO in a) - (ARRIBA in a)) if len(a) == 1 else (0, 0)
                for a in self.acciones]

    def _decaimiento(self):
        m = np.full(len(self.theta), 0.005, np.float32)
        m[-cerebro.BRUJULA * len(self.acciones):] = 0.0
        return m

    def limpiar_demos(self):
        d = self.demos
        nada = [i for i, a in enumerate(self.acciones) if not a]
        if not len(d["accion"]) or not nada:
            return
        es_nada = np.isin(d["accion"], nada)
        if es_nada.mean() <= C.MAX_NADA_DEMOS:
            return
        quedan = ~es_nada
        idx = np.flatnonzero(es_nada)
        n_max = int(C.MAX_NADA_DEMOS * quedan.sum() / (1 - C.MAX_NADA_DEMOS))
        quedan[self.rng.permutation(idx)[:n_max]] = True
        quitadas = int((~quedan).sum())
        self.demos = {k: v[quedan] for k, v in d.items()}
        self.avisar(f"Jugadas grabadas: quité {quitadas} pasos en los que no apretabas nada")

    def avisar(self, texto):
        self.mensajes.append(texto)
        print(texto, flush=True)

    def preparar_inicio(self):
        if self.inicio is not None:
            return
        j = Juego(self.ruta_rom, self.acciones, self.perfil, ruta_sav=self.ruta_sav)
        j.gb.cuadros(90)
        self.inicio = j.gb.estado()

    def fijar_inicio(self, estado):
        with self.cerrojo:
            self.inicio = estado
            self.avisar("Nuevo punto de inicio fijado")

    def agregar_celda(self, clave, estado, gen=None, avance=0.0):
        with self.cerrojo:
            self.conocidas.add(clave)
            celda = {"estado": estado, "elegida": 0, "gen": self.generacion if gen is None else gen,
                     "avance": float(avance)}
            if clave in self.archivo:
                if avance > self.archivo[clave].get("avance", 0.0):
                    self.archivo[clave] = celda
            elif len(self.archivo) < C.MAX_CELDAS:
                self.archivo[clave] = celda
            else:
                peor = min(self.archivo, key=lambda k: (self.archivo[k].get("avance", 0.0)
                                                        - np.log1p(self.archivo[k]["elegida"]), self.archivo[k]["gen"]))
                if self.archivo[peor].get("avance", 0.0) <= avance or self.archivo[peor]["elegida"] > 0:
                    del self.archivo[peor]
                    self.archivo[clave] = celda

    def avance_maximo(self):
        return max((c.get("avance", 0.0) for c in self.archivo.values()), default=0.0)

    def elegir_inicio(self):
        prob = C.PROB_INICIO if len(self.archivo) < 20 else C.PROB_INICIO_AVANZADO
        if not self.archivo or self.rng.random() < prob:
            return self.inicio, None
        claves = list(self.archivo)
        tope = self.avance_maximo()
        if self.rng.random() < C.PROB_FRONTERA:
            claves = [k for k in claves if self.archivo[k].get("avance", 0.0) >= tope - 1e-6]
        w = np.array([np.exp((self.archivo[k].get("avance", 0.0) - tope) / C.TEMP_AVANCE)
                      / np.sqrt(1 + self.archivo[k]["elegida"])
                      * (1 + 0.5 * (self.archivo[k]["gen"] >= self.generacion - 5)) for k in claves])
        k = claves[int(self.rng.choice(len(claves), p=w / w.sum()))]
        self.archivo[k]["elegida"] += 1
        return self.archivo[k]["estado"], k

    def inicio_para_ver(self, n):
        with self.cerrojo:
            if not self.archivo or n % 4 == 3:
                return self.inicio, None
            celdas = list(self.archivo.values())
            tope = self.avance_maximo()
            if n % 2 == 0:
                celdas = [c for c in celdas if c.get("avance", 0.0) >= tope - 1e-6]
            c = celdas[int(self.rng.integers(len(celdas)))]
            return c["estado"], c.get("avance", 0.0)

    def _pool(self):
        if self.pool is None:
            self.pool = mp.get_context("spawn").Pool(self.procesos, initializer=iniciar_trabajador)
        return self.pool

    def paso_generacion(self):
        with self.cerrojo:
            inicio, celda = self.elegir_inicio()
            theta = self.theta.copy()
            conocidas = np.fromiter(self.conocidas, dtype=np.int64, count=len(self.conocidas))
            pf = self.perfil
            n_busq = pf.get("busquedas", 0)
            falta_vp = not pf.get("posicion") and (pf.get("vidas") is None or not pf.get("puntos"))
            falta_pos = not pf.get("posicion") or not pf.get("mapa")
            recoger = pf.get("auto", True) and self.generacion >= C.DETECTAR_DESDE and \
                ((falta_vp and n_busq < C.MAX_BUSQUEDAS) or (falta_pos and n_busq < 4 * C.MAX_BUSQUEDAS))
            if recoger:
                pf["busquedas"] = n_busq + 1
            revisar = bool(pf.get("auto", True) and not pf.get("conocido") and pf.get("mapa")
                           and self.generacion % C.REVISAR_MAPA == 0)
            banderas = self.banderas if self.banderas is not None else np.zeros(0, np.uint8)
            pasos = C.PASOS_EPISODIO_POS if pf.get("posicion") else C.PASOS_EPISODIO
            tareas = []
            semilla_juego = int(self.rng.integers(1 << 30))
            mitad = self.poblacion // 2
            semillas = self.rng.integers(1 << 30, size=mitad)
            for i in range(self.poblacion):
                tareas.append({"rom": self.ruta_rom, "acciones": self.acciones, "perfil": self.perfil,
                               "inicio": inicio, "theta": theta, "sigma": self.sigma,
                               "semilla": int(semillas[i // 2]), "signo": 1 if i % 2 == 0 else -1,
                               "semilla_juego": semilla_juego, "conocidas": conocidas, "ocultas": C.OCULTAS,
                               "pasos": pasos, "recoger": recoger, "i": i, "banderas": banderas,
                               "pesos": self.perfil.get("pesos", {})})
            tareas.append({**tareas[0], "signo": 0, "i": self.poblacion, "recoger": False})
            if recoger or revisar:
                for s in range(C.SONDAS):
                    ini, _ = self.elegir_inicio() if s % 2 else (self.inicio, None)
                    tareas.append({**tareas[0], "inicio": ini, "sonda": True, "recoger": True,
                                   "semilla_juego": int(self.rng.integers(1 << 30)), "i": self.poblacion + 1 + s})
            self.gen_actual = {"gen": self.generacion + 1, "theta": theta, "sigma": self.sigma,
                               "semillas": [int(x) for x in semillas], "inicio": inicio,
                               "semilla_juego": semilla_juego}
        t0 = time.time()
        self.progreso = (0, len(tareas))
        res = []
        for r in self._pool().imap_unordered(evaluar, tareas, chunksize=1):
            res.append(r)
            self.progreso = (len(res), len(tareas))
        res.sort(key=lambda r: r["i"])
        dt = time.time() - t0
        sondas = res[self.poblacion + 1:]
        res = res[:self.poblacion + 1]
        centro = res.pop()
        apt = np.array([r["aptitud"] for r in res])
        rangos = np.empty(len(apt))
        rangos[np.argsort(apt)] = np.arange(len(apt))
        rangos = rangos / (len(apt) - 1) - 0.5
        n = len(theta)
        grad = np.zeros(n, dtype=np.float32)
        for k in range(mitad):
            ruido = np.random.default_rng(int(semillas[k])).standard_normal(n).astype(np.float32)
            grad += (rangos[2 * k] - rangos[2 * k + 1]) * ruido
        grad /= (self.poblacion * self.sigma)
        if apt.std() < 1e-6:
            self.sigma = min(self.sigma * C.SIGMA_SUBE, C.SIGMA_MAX)
        else:
            self.sigma = max(C.SIGMA, self.sigma * C.SIGMA_BAJA)
        with self.cerrojo:
            self.theta -= self.adam.paso(-grad + self._decaimiento() * self.theta, C.TASA)
            for r in res + [centro]:
                for k in r["nuevas"]:
                    self.conocidas.add(k)
                for k, t, est, av in r["estados"]:
                    self.agregar_celda(k, est, avance=av)
            for r in res + [centro] + sondas:
                enc, apa, camb = r["bits"]
                self.bits_enc |= enc
                self.bits_apa |= apa
                self.bits_cambios += camb
                self.bits_eps += 1
            self.bits_gens += 1
            self.actualizar_banderas()
            if revisar:
                self.validar_mapa([r["saltos"] for r in sondas if "saltos" in r])
            if self.mejor is None or centro["aptitud"] >= self.mejor:
                self.mejor = centro["aptitud"]
                self.mejor_theta = self.theta.copy()
            self.ultimas_aptitudes = {"gen": self.generacion + 1, "aptitudes": apt.tolist(),
                                      "finales": [r["final"] for r in res]}
            if recoger:
                self.detectar([r["stats"] for r in res if "stats" in r])
                self.detectar_posicion([r["mov"] for r in res + sondas if "mov" in r],
                                       [r["saltos"] for r in res + sondas if "saltos" in r])
            self.repasar_demos()
            self.generacion += 1
            fila = {"gen": self.generacion, "media": float(apt.mean()), "max": float(apt.max()),
                    "centro": float(centro["aptitud"]), "celdas": len(self.conocidas), "archivo": len(self.archivo),
                    "lugares": int(sum(r.get("lugares", 0) for r in res + [centro])),
                    "bucles": int(sum(r["final"] == "bucle" for r in res)),
                    "logros": int(sum(r.get("logros", 0) for r in res + [centro])),
                    "avance": round(float(max(r.get("avance", 0.0) for r in res + [centro])), 2),
                    "tope": round(self.avance_maximo(), 2),
                    "puntos": int(max(r["puntos"] for r in res)), "vidas": float(np.mean([r["vidas"] for r in res])),
                    "segundos": round(dt, 1), "desde_celda": celda is not None, "sigma": round(self.sigma, 4)}
            self.historial.append(fila)
            self.historial = self.historial[-C.HISTORIAL_EN_MEMORIA:]
            self._anotar_csv(fila)
        print(f"gen {self.generacion:4d}  media {fila['media']:7.2f}  máx {fila['max']:7.2f}  "
              f"centro {fila['centro']:7.2f}  celdas {fila['celdas']:6d}  archivo {fila['archivo']:4d}  "
              f"avance {fila['tope']:6.1f}  "
              f"{dt:5.1f}s{'  (desde celda)' if celda is not None else ''}", flush=True)
        if self.generacion % C.GUARDAR_CADA == 0:
            self.guardar()
        return fila

    def vista_generacion(self):
        with self.cerrojo:
            if self.gen_actual is not None and self.gen_actual["gen"] >= self.generacion:
                return self.gen_actual
            return {"gen": self.generacion + 1, "theta": self.theta.copy(), "sigma": self.sigma,
                    "semillas": [int(x) for x in self.rng.integers(1 << 30, size=max(3, self.poblacion // 2))],
                    "inicio": self.inicio, "semilla_juego": int(self.rng.integers(1 << 30)), "vista_previa": True}

    def detectar(self, stats):
        pos = {indice(d) for d in (self.perfil.get("posicion") or []) + (self.perfil.get("mapa") or [])}
        vidas, puntos = detector.analizar(stats, C.PASOS_EPISODIO, self.analisis.get("vidas"), pos)
        self.candidatos.append((vidas, tuple(puntos)))
        self.candidatos = self.candidatos[-3:]
        if len(self.candidatos) < 2:
            return
        a, b = self.candidatos[-2], self.candidatos[-1]
        cambio = False
        busca_vidas = not self.analisis.get("hay_texto") or "vidas" in self.analisis.get("objetivos", [])
        if busca_vidas and not self.perfil.get("posicion") and self.perfil.get("vidas") is None and a[0] is not None and a[0] == b[0]:
            self.perfil["vidas"] = a[0]
            self.avisar(f"Detector: las vidas parecen estar en 0x{a[0]:04X}")
            cambio = True
        comunes = sorted(set(a[1]) & set(b[1]))
        if not self.perfil.get("puntos") and comunes and not self.perfil.get("posicion"):
            self.perfil["puntos"] = comunes
            self.avisar("Detector: contadores de puntos en " + ", ".join(f"0x{d:04X}" for d in comunes))
            cambio = True
        if cambio:
            self.guardar_perfil()

    def _bytes_propios(self):
        pf = self.perfil
        fuera = set()
        for d in (pf.get("posicion") or []) + (pf.get("mapa") or []) + (pf.get("niveles") or []):
            fuera.add(indice(d))
        for d in pf.get("experiencia") or []:
            fuera.update(indice(d) + k for k in range(3))
        if pf.get("equipo"):
            fuera.add(indice(pf["equipo"]))
        for m in pf.get("metas_bits") or []:
            fuera.update(indice(m[0]) + k for k in range(int(m[1])))
        return fuera

    def _mascara_rango(self):
        a, b = self.perfil["banderas_rango"]
        m = np.zeros(TAM_RAM_VISTA, np.uint8)
        m[indice(a):indice(b)] = 0xFF
        return m & ~self.bits_apa

    def actualizar_banderas(self):
        if self.perfil.get("banderas_rango"):
            if self.banderas is None or self.bits_gens % C.BANDERAS_REVISAR == 0:
                m = self._mascara_rango()
                if self.banderas is None or not np.array_equal(m, self.banderas):
                    primera = self.banderas is None
                    self.banderas = m
                    if primera:
                        self.avisar("Banderas de eventos de la historia activas: cada evento nuevo se premia")
                    self.rehacer_claves()
            return
        if self.banderas is None:
            if self.bits_gens < C.BANDERAS_DESDE:
                return
            m = self.bits_enc & ~self.bits_apa
            m[self.bits_cambios > C.BANDERAS_CAMBIOS * max(self.bits_eps, 1)] = 0
            m[list(self._bytes_propios())] = 0
            m[0x2000:] = 0
            if bits(m) > C.BANDERAS_MAXIMAS:
                self.banderas = np.zeros(0, np.uint8)
                self.avisar(f"Detector: {bits(m)} bits candidatos a banderas, demasiados para ser fiables; no se usan")
                return
            self.banderas = m
            self.avisar(f"Detector: {bits(m)} banderas de eventos (bits que sólo se encienden); "
                        "cada evento nuevo se premia")
            self.rehacer_claves()
        elif len(self.banderas) and self.bits_gens % C.BANDERAS_REVISAR == 0:
            quitar = self.banderas & self.bits_apa
            if quitar.any():
                self.banderas = self.banderas & ~self.bits_apa
                self.avisar(f"Detector: {bits(quitar)} banderas descartadas por apagarse")
                self.rehacer_claves()

    def validar_mapa(self, saltos):
        if not saltos:
            return
        fuera = np.stack([s[2] for s in saltos]).astype(np.int64).sum(0)
        malos = [d for d in self.perfil.get("mapa") or [] if fuera[indice(d)] > 0]
        if malos:
            self.perfil["mapa"] = [d for d in self.perfil["mapa"] if d not in malos]
            self.avisar("Detector: descarto como mapa " + ", ".join(f"0x{d:04X}" for d in malos))
            self.guardar_perfil()
            self.rehacer_claves()

    def _excluidas(self):
        fuera = set(self.perfil.get("puntos") or [])
        if self.perfil.get("vidas") is not None:
            fuera.add(self.perfil["vidas"])
        return {indice(d) for d in fuera}

    def detectar_posicion(self, movs, saltos):
        if not self.perfil.get("posicion"):
            pos = detector.analizar_posicion(movs, self._excluidas())
            self.candidatos_pos = (self.candidatos_pos + [pos])[-2:]
            if pos and len(self.candidatos_pos) == 2 and self.candidatos_pos[0] == pos:
                self.perfil["posicion"] = pos
                self.perfil["mapa"] = []
                if self.perfil.get("auto", True):
                    self.perfil["puntos"] = []
                    self.perfil["vidas"] = None
                self.archivo = {}
                self.avisar(f"Detector: posición del jugador en X=0x{pos[0]:04X}, Y=0x{pos[1]:04X}; "
                            "ahora premia lugares nuevos del mundo, no pantallas de menú")
                self.guardar_perfil()
        elif not self.perfil.get("mapa") and saltos:
            fuera = self._excluidas() | {indice(d) for d in self.perfil["posicion"]}
            mapa = detector.analizar_mapa(saltos, fuera)
            self.candidatos_mapa = (self.candidatos_mapa + [mapa])[-2:]
            if mapa and len(self.candidatos_mapa) == 2 and self.candidatos_mapa[0] == mapa:
                self.perfil["mapa"] = mapa
                self.avisar("Detector: número de mapa en " + ", ".join(f"0x{d:04X}" for d in mapa))
                self.guardar_perfil()

    def guardar_perfil(self):
        _escribir_json(os.path.join(self.dir, "perfil.json"), self.perfil)

    def agregar_demos(self, obs, prev, ultima, quieto, accion, rasgos=None):
        if not len(accion):
            return
        if rasgos is None or len(rasgos) != len(accion):
            rasgos = np.zeros((len(accion), cerebro.RASGOS), np.float16)
        with self.cerrojo:
            d = self.demos
            for k, v in (("obs", obs), ("prev", prev), ("ultima", ultima), ("quieto", quieto), ("accion", accion),
                         ("rasgos", rasgos)):
                d[k] = np.concatenate([d[k], np.asarray(v, dtype=d[k].dtype)])[-C.MAX_DEMOS:]
            perdida, acierto = self.imitar(C.PASOS_IMITACION)
        self.avisar(f"Imitación: {len(accion)} jugadas nuevas, acierto {acierto * 100:.0f}%")
        self.guardar()

    def _lote(self, tam):
        d = self.demos
        m = len(d["accion"])
        idx = self.rng.integers(m, size=min(tam, m))
        n = len(self.acciones)
        X = np.zeros((len(idx), cerebro.entradas(n)), np.float32)
        o = d["obs"][idx].astype(np.float32) / 255
        X[:, :360] = o - 0.5
        X[:, 360:720] = (o - d["prev"][idx].astype(np.float32) / 255) * 4
        u = d["ultima"][idx]
        ok = (u >= 0) & (u < n)
        X[np.flatnonzero(ok), 720 + u[ok]] = 1
        X[:, 720 + n] = d["quieto"][idx]
        X[:, 721 + n:] = d["rasgos"][idx].astype(np.float32)
        Y = np.clip(d["accion"][idx].astype(np.int64), 0, n - 1)
        return X, Y

    def imitar(self, pasos, tam=128):
        if not len(self.demos["accion"]):
            return 0.0, 0.0
        adam = cerebro.Adam(len(self.theta))
        perdida = acierto = 0.0
        for _ in range(pasos):
            X, Y = self._lote(tam)
            perdida, acierto = cerebro.paso_imitacion(self.theta, X, Y, len(self.acciones), C.OCULTAS,
                                                      C.TASA_IMITACION, adam)
        self.mejor_theta = self.theta.copy()
        return perdida, acierto

    def repasar_demos(self):
        if len(self.demos["accion"]) >= 32:
            for _ in range(C.REPASO_POR_GENERACION):
                X, Y = self._lote(64)
                cerebro.paso_imitacion(self.theta, X, Y, len(self.acciones), C.OCULTAS, C.TASA_IMITACION * 0.5)

    def _anotar_csv(self, fila):
        ruta = os.path.join(self.dir, "historial.csv")
        nuevo = not os.path.exists(ruta)
        if not nuevo:
            with open(ruta, encoding="utf-8") as f:
                cab = f.readline().strip().split(",")
            if cab != list(fila):
                os.replace(ruta, os.path.join(self.dir, "historial_anterior.csv"))
                nuevo = True
        with open(ruta, "a", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(fila))
            if nuevo:
                w.writeheader()
            w.writerow(fila)

    def guardar(self):
        with self.cerrojo:
            np.savez(os.path.join(self.dir, "modelo.npz"), theta=self.theta, mejor=self.mejor_theta,
                     m=self.adam.m, v=self.adam.v, t=self.adam.t)
            _escribir_json(os.path.join(self.dir, "estado.json"), {
                "generacion": self.generacion, "sigma": self.sigma, "mejor": self.mejor,
                "acciones": self.acciones, "historial": self.historial, "titulo": self.info["titulo"],
                "guardado": time.strftime("%Y-%m-%d %H:%M:%S")})
            with open(os.path.join(self.dir, "archivo.pkl.tmp"), "wb") as f:
                pickle.dump({"archivo": self.archivo, "conocidas": self.conocidas, "inicio": self.inicio,
                             "bits": (self.bits_enc, self.bits_apa, self.bits_gens, self.banderas,
                                      self.bits_cambios, self.bits_eps)}, f)
            os.replace(os.path.join(self.dir, "archivo.pkl.tmp"), os.path.join(self.dir, "archivo.pkl"))
            np.savez_compressed(os.path.join(self.dir, "demos.npz"), **self.demos)
            self.guardar_perfil()

    def cargar(self):
        e = _leer_json(os.path.join(self.dir, "estado.json"), None)
        if e and e.get("acciones") == self.acciones and os.path.exists(os.path.join(self.dir, "modelo.npz")):
            m = np.load(os.path.join(self.dir, "modelo.npz"))
            n = len(self.acciones)
            theta = cerebro.migrar(m["theta"].astype(np.float32), n, C.OCULTAS, self._flechas())
            if theta is not None:
                migrada = len(m["theta"]) != len(theta)
                self.theta = theta
                self.mejor_theta = cerebro.migrar(m["mejor"].astype(np.float32), n, C.OCULTAS, self._flechas())
                if migrada:
                    self.avisar("Red ampliada con el mapa de lo explorado y la brújula de exploración "
                                "(se conserva lo aprendido)")
                else:
                    self.adam.m, self.adam.v, self.adam.t = m["m"], m["v"], int(m["t"])
                self.generacion = e["generacion"]
                self.sigma = e.get("sigma", C.SIGMA)
                self.mejor = e.get("mejor")
                self.historial = e.get("historial", [])
                self.avisar(f"Reanudando {self.info['titulo']} en la generación {self.generacion + 1}")
        ruta = os.path.join(self.dir, "archivo.pkl")
        if os.path.exists(ruta):
            with open(ruta, "rb") as f:
                a = pickle.load(f)
            self.archivo, self.conocidas, self.inicio = a["archivo"], a["conocidas"], a["inicio"]
            if "bits" in a and len(a["bits"]) == 6:
                (self.bits_enc, self.bits_apa, self.bits_gens, self.banderas,
                 self.bits_cambios, self.bits_eps) = a["bits"]
        ruta = os.path.join(self.dir, "demos.npz")
        if os.path.exists(ruta):
            d = np.load(ruta)
            if all(k in d for k in ("obs", "prev", "ultima", "quieto", "accion")):
                demos = {k: d[k] for k in self.demos if k in d}
                m = len(demos["accion"])
                if "rasgos" not in demos or len(demos["rasgos"]) != m:
                    demos["rasgos"] = np.zeros((m, cerebro.RASGOS), np.float16)
                r = demos["rasgos"]
                if r.shape[1] != cerebro.RASGOS:
                    nr = np.zeros((m, cerebro.RASGOS), np.float16)
                    w = min(r.shape[1], cerebro.RASGOS)
                    nr[:, :w] = r[:, :w]
                    demos["rasgos"] = nr
                self.demos = demos
                self.limpiar_demos()

    def reiniciar(self):
        self.detener(esperar=True)
        with self.cerrojo:
            inicio, demos = self.inicio, self.demos
            self._nuevo()
            self.demos = demos
            self.inicio = inicio
            for f in ("modelo.npz", "estado.json", "archivo.pkl", "historial.csv"):
                try:
                    os.remove(os.path.join(self.dir, f))
                except OSError:
                    pass
            self.preparar_inicio()
        self.avisar("IA reiniciada desde cero (tus jugadas grabadas se conservan)")

    def _bucle(self):
        while self.corriendo:
            try:
                self.paso_generacion()
            except Exception as e:
                self.avisar(f"Error en la generación: {e}")
                self.corriendo = False

    def iniciar(self):
        if self.corriendo:
            return
        self.corriendo = True
        self.hilo = threading.Thread(target=self._bucle, daemon=True)
        self.hilo.start()

    def detener(self, esperar=False):
        self.corriendo = False
        if esperar and self.hilo is not None:
            self.hilo.join()

    def cerrar(self):
        self.detener(esperar=True)
        self.guardar()
        if self.pool is not None:
            self.pool.terminate()
            self.pool = None
