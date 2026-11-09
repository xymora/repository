import csv
import hashlib
import inspect
import json
import logging
import os

import numpy as np

import config as C
import paralelo as P
import red as R
from calles import PistaCalle, descripcion_nivel_ciudad
from fisica import Simulador
from terreno import Pista, descripcion_nivel

AQUI = os.path.dirname(os.path.abspath(__file__))
VERSION = "v10"
FORMATO = 2
log = logging.getLogger("moto.evolucion")

COLUMNAS_V9 = ["generacion", "nivel", "mejor", "promedio", "llegaron_%", "terminadas_lider",
               "sigma", "vel_lider_kmh"]
COLUMNAS_V10 = ["llegadas_limpias_pct", "reintentos_lider", "terminadas_limpias_lider"]
COLUMNAS_PUNTOS = ["puntos_lider", "exitosas_pct"]
COLUMNAS_NICHO = ["vel_rapida_kmh"]


def carpeta_datos(dir_datos=None):
    if not dir_datos:
        return AQUI
    dir_datos = os.fspath(dir_datos)
    return dir_datos if os.path.isabs(dir_datos) else os.path.normpath(os.path.join(AQUI, dir_datos))


def ruta(nombre, modo="terreno", dir_datos=None, superficie=None):
    if modo == "ciudad":
        base, ext = os.path.splitext(nombre)
        nombre = f"{base}_ciudad{ext}"
    return os.path.join(carpeta_datos(dir_datos), nombre)


ETAPAS_POR_DEFECTO = (("pavimento", "no"), ("pavimento", "circuito"), ("irregular", "mixto"),
                      ("variado", "mixto"))
NOMBRE_RECORRIDO = {"no": "sólo ida", "misma": "circuito por la misma ruta",
                    "otra": "circuito por otra ruta", "circuito": "circuito", "mixto": "mixto"}


def etapas_calles():
    return tuple(getattr(C, "ETAPAS_CALLES", ETAPAS_POR_DEFECTO)) or ETAPAS_POR_DEFECTO


def etapa_de(superficie, circuito):
    etapas = etapas_calles()
    hay_circ = circuito not in (None, "no")
    for k, (sup, rec) in enumerate(etapas):
        if sup == superficie and (rec != "no") == hay_circ:
            return k
    for k, (sup, _) in enumerate(etapas):
        if sup == superficie:
            return k
    return 0


def recorrido_pista(recorrido, semilla):
    if recorrido == "circuito":
        return ("misma", "otra")[semilla % 2]
    if recorrido == "mixto":
        return ("no", "no", "misma", "otra")[semilla % 4]
    return recorrido if recorrido in ("misma", "otra") else "no"


def texto_etapa(etapa, superficie=None, recorrido=None, automatico=True):
    etapas = etapas_calles()
    sup, rec = etapas[min(etapa, len(etapas) - 1)]
    sup, rec = superficie or sup, recorrido or rec
    return (f"Etapa {etapa + 1}/{len(etapas)}: {sup} · {NOMBRE_RECORRIDO.get(rec, rec)}"
            + ("" if automatico else " (manual)"))


def cargar_mejor(modo="terreno", dir_datos=None, superficie=None):
    archivo = ruta(C.ARCHIVO_MEJOR, modo, dir_datos, superficie)
    if not os.path.exists(archivo):
        return None
    try:
        with open(archivo, encoding="utf-8") as f:
            d = json.load(f)
        pesos = np.array(d["pesos"], dtype=float)
        if tuple(d["capas"]) != tuple(C.CAPAS):
            log.warning("%s es de otra arquitectura %s (actual %s): se ignora",
                        archivo, d["capas"], list(C.CAPAS))
            return None
        return pesos, d
    except (OSError, ValueError, KeyError) as ex:
        log.warning("no se pudo leer %s: %r", archivo, ex)
        return None


_FUERA_DEL_HASH = {"CAMPEONES_MAX", "PUNTOS_CONTROL", "CLIMA_AUTOMATICO", "CLIMA_MANUAL",
                   "CALLES_SUPERFICIE", "CALLES_CIRCUITO", "PLAN_AUTOMATICO", "ZONA_CALLES"}


def hash_config():
    datos = {k: getattr(C, k) for k in sorted(dir(C)) if k.isupper() and k not in _FUERA_DEL_HASH
             and isinstance(getattr(C, k), (int, float, str, bool, tuple, list, type(None)))}
    return hashlib.sha256(json.dumps(datos, sort_keys=True, default=str).encode()).hexdigest()[:16]


SAL_CLIMA = 0xC11A7E
_aviso_clima = []


def _modulo_clima():
    try:
        import clima
        return clima
    except ImportError as ex:
        if not _aviso_clima:
            _aviso_clima.append(1)
            log.warning("clima activo en config.py pero no se pudo importar clima.py (%r): "
                        "se entrena sin clima", ex)
        return None


def clima_activo():
    manual = getattr(C, "CLIMA_MANUAL", None)
    return bool(getattr(C, "CLIMA_AUTOMATICO", False)) or manual not in (None, "")


def es_despejado(clima):
    if clima is None:
        return True
    if getattr(clima, "granizo", False):
        return False
    return all(abs(float(getattr(clima, k, 0.0) or 0.0)) < 1e-12
               for k in ("lluvia", "niebla", "viento_medio", "rafagas", "charcos"))


def nombre_clima(clima):
    return "despejado" if clima is None else str(getattr(clima, "nombre", "clima"))


def clima_de_pista(semilla, nivel, etapa=0):
    if not clima_activo():
        return None
    K = _modulo_clima()
    if K is None:
        return None
    manual = getattr(C, "CLIMA_MANUAL", None)
    if manual not in (None, ""):
        c = K.crear(manual, int(semilla))
    else:
        rng = np.random.default_rng([int(semilla) & 0xFFFFFFFFFFFF, SAL_CLIMA])
        c = K.clima_aleatorio(rng, int(nivel), int(etapa))
    return None if es_despejado(c) else c


def ruta_campeones(modo="terreno", dir_datos=None):
    return os.path.join(carpeta_datos(dir_datos), f"campeones_{'ciudad' if modo == 'ciudad' else 'terreno'}.json")


def clave_campeon(c):
    etapa = 0 if c.get("plan") == "manual" else int(c.get("etapa", 0) or 0)
    return (etapa, int(c.get("nivel", 1) or 1),
            int(c.get("limpias", c.get("llegadas_limpias", 0)) or 0),
            int(c.get("exitosas", 0) or 0), float(c.get("aptitud", 0.0)))


def _etapa_guardada(modo, dir_datos):
    try:
        with np.load(ruta(C.ARCHIVO_POBLACION, modo, dir_datos), allow_pickle=False) as d:
            return int(d["etapa"]) if "etapa" in d.files else 0
    except (OSError, KeyError, ValueError):
        return 0


def _sembrar_campeones(modo, dir_datos=None):
    carpeta = carpeta_datos(dir_datos)
    base, ext = os.path.splitext(C.ARCHIVO_MEJOR)
    principal = os.path.basename(ruta(C.ARCHIVO_MEJOR, modo, dir_datos))
    try:
        nombres = [principal] if os.path.exists(os.path.join(carpeta, principal)) else []
    except OSError:
        return []
    lista = []
    for nombre in nombres:
        try:
            with open(os.path.join(carpeta, nombre), encoding="utf-8") as f:
                d = json.load(f)
            if tuple(d["capas"]) != tuple(C.CAPAS) or d.get("modo", modo) != modo:
                continue
            if "etapa" in d:
                etapa = int(d["etapa"])
            else:
                etapa = _etapa_guardada(modo, dir_datos) if modo == "ciudad" else 0
            lista.append({"generacion": int(d.get("generacion", 0)), "modo": modo, "etapa": etapa,
                          "plan": d.get("plan", "automatico"),
                          "nivel": int(d.get("nivel", 1)), "aptitud": float(d.get("aptitud", 0.0)),
                          "limpias": int(d.get("pistas_terminadas_limpias",
                                               d.get("pistas_terminadas", 0)) or 0),
                          "exitosas": int(d.get("exitosas", 0) or 0),
                          "terminadas": int(d.get("pistas_terminadas", 0) or 0),
                          "clima_visto": d.get("clima_visto", []), "origen": nombre,
                          "pesos": [float(w) for w in d["pesos"]]})
        except (OSError, ValueError, KeyError, TypeError) as ex:
            log.warning("no se pudo leer %s para el salón de la fama: %r", nombre, ex)
    for c in lista:
        c["llegadas_limpias"] = c["limpias"]
    lista.sort(key=clave_campeon, reverse=True)
    return lista[:int(getattr(C, "CAMPEONES_MAX", 12))]


def cargar_campeones(modo="terreno", dir_datos=None):
    archivo = ruta_campeones(modo, dir_datos)
    if not os.path.exists(archivo):
        return _sembrar_campeones(modo, dir_datos)
    try:
        with open(archivo, encoding="utf-8") as f:
            d = json.load(f)
        lista = d.get("campeones", []) if isinstance(d, dict) else list(d)
        lista = [c for c in lista if len(c.get("pesos", ())) == R.n_parametros(C.CAPAS)]
    except (OSError, ValueError, TypeError, AttributeError) as ex:
        log.warning("no se pudo leer %s: %r (se siembra desde mejor_moto)", archivo, ex)
        return _sembrar_campeones(modo, dir_datos)
    for c in lista:
        c.setdefault("limpias", c.get("llegadas_limpias", 0))
        c.setdefault("llegadas_limpias", c["limpias"])
    lista.sort(key=clave_campeon, reverse=True)
    return lista


def mejor_campeon(modo="terreno", dir_datos=None):
    lista = cargar_campeones(modo, dir_datos)
    return lista[0] if lista else None


def actualizar_campeones(lista, nuevo, maximo=None, separacion=5):
    maximo = int(maximo or getattr(C, "CAMPEONES_MAX", 12))
    k_nuevo = clave_campeon(nuevo)
    gen = int(nuevo["generacion"])
    rivales = [c for c in lista if int(c.get("generacion", -1)) == gen or (
        int(c.get("etapa", 0)) == int(nuevo["etapa"]) and int(c.get("nivel", 1)) == int(nuevo["nivel"])
        and abs(int(c.get("generacion", 0)) - gen) < separacion)]
    if rivales:
        if not all(k_nuevo > clave_campeon(c) for c in rivales):
            return None
        lista = [c for c in lista if not any(c is x for x in rivales)]
    lista = sorted(lista + [nuevo], key=clave_campeon, reverse=True)
    if not any(c is nuevo for c in lista[:maximo]):
        return None
    return lista[:maximo]


def _escribir_atomico(archivo, escribir, binario=False):
    tmp = archivo + ".tmp"
    if binario:
        with open(tmp, "wb") as f:
            escribir(f)
    else:
        with open(tmp, "w", encoding="utf-8", newline="") as f:
            escribir(f)
    os.replace(tmp, archivo)


def _escribir_csv(archivo, columnas, filas):
    def escribir(f):
        w = csv.DictWriter(f, fieldnames=columnas, restval="")
        w.writeheader()
        w.writerows(filas)
    _escribir_atomico(archivo, escribir)


def parametros_ga():
    g = getattr
    p = {
        "prob_cruce": C.PROB_CRUCE,
        "prob_mutacion": C.PROB_MUTACION,
        "inmigrantes": C.INMIGRANTES,
        "sigma0": C.SIGMA_MUTACION,
        "sigma_min": g(C, "SIGMA_MIN", None),
        "sigma_max": g(C, "SIGMA_MAX", None),
        "relativa": g(C, "MUTACION_RELATIVA", False),
        "autoadaptativa": g(C, "SIGMA_AUTOADAPTATIVA", False),
    }
    if g(C, "GA_V2", False):
        p.update(prob_cruce=0.0, prob_mutacion=1.0, inmigrantes=0.0, relativa=True,
                 autoadaptativa=True, sigma0=g(C, "SIGMA_INICIAL_V2", 0.3),
                 sigma_min=g(C, "SIGMA_MIN_V2", 0.02), sigma_max=g(C, "SIGMA_MAX_V2", 1.0))
    if p["sigma_min"] is None:
        p["sigma_min"] = p["sigma0"]
    if p["sigma_max"] is None:
        p["sigma_max"] = 2 * p["sigma0"]
    return p


def escala_genes(capas):
    partes = []
    for a, b in zip(capas[:-1], capas[1:]):
        partes.append(np.full(a * b, 1 / np.sqrt(a)))
        partes.append(np.full(b, 0.2))
    return np.concatenate(partes)


class Entrenador:
    def __init__(self, poblacion=C.POBLACION, continuar=False, semilla=None, modo="terreno",
                 red_vial=None, ruta=None, dir_datos=None, procesos=1, guardar=True):
        self.modo, self.red_vial = modo, red_vial
        self.plan_automatico = bool(getattr(C, "PLAN_AUTOMATICO", True))
        self.etapa = 0
        self.superficie = getattr(C, "CALLES_SUPERFICIE", "pavimento")
        self.circuito = getattr(C, "CALLES_CIRCUITO", "no")
        self.ruta_fija = ruta if modo == "ciudad" else None
        self.semilla = semilla
        dir_datos = carpeta_datos(dir_datos) if dir_datos else None
        self.dir_datos = dir_datos
        self.procesos = max(1, int(procesos or 1))
        self.guardar = guardar
        if dir_datos and guardar:
            os.makedirs(dir_datos, exist_ok=True)
        self.rng = np.random.default_rng(semilla)
        self.n = poblacion
        self.n_param = R.n_parametros(C.CAPAS)
        self.generacion = 1
        self.nivel = 1
        self.racha = 0
        self.sigma = parametros_ga()["sigma0"]
        self.sigmas = None
        self.historial = []
        self.desde_terreno = False
        self.hay_campeon = False
        self.validada = None
        self._pool = None
        self._foto_pool = None
        self.opt = None
        self._estado_opt = None
        self.pob = R.aleatorios(self.n, C.CAPAS, self.rng)
        if continuar:
            self._cargar()
        self._campeones_semilla = None
        if guardar and not os.path.exists(ruta_campeones(modo, dir_datos)):
            self._campeones_semilla = cargar_campeones(modo, dir_datos) if continuar else []
        if modo == "ciudad" and not self.plan_automatico:
            self.etapa = etapa_de(self.superficie, self.circuito)
        self._aplicar_etapa()
        self._iniciar_optimizador()
        self._preparar_generacion()

    def ruta(self, nombre):
        return ruta(nombre, self.modo, self.dir_datos, self.superficie)

    def _aplicar_etapa(self):
        etapas = etapas_calles()
        self.etapa = max(0, min(int(self.etapa), len(etapas) - 1))
        if self.plan_automatico:
            self.superficie, self.circuito = etapas[self.etapa]

    def config_pista(self, semilla, etapa=None):
        if etapa is None or etapa == self.etapa:
            return self.superficie, recorrido_pista(self.circuito, semilla)
        sup, rec = etapas_calles()[etapa]
        return sup, recorrido_pista(rec, semilla)

    def fijar_etapa(self, automatico=True, superficie=None, circuito=None):
        self.plan_automatico = bool(automatico)
        if not automatico:
            self.superficie = superficie or self.superficie
            self.circuito = circuito or "no"
            self.etapa = etapa_de(self.superficie, self.circuito)
        self._aplicar_etapa()

    def texto_etapa(self):
        return texto_etapa(self.etapa, self.superficie, self.circuito, self.plan_automatico)

    def _cargar(self):
        archivo = self.ruta(C.ARCHIVO_POBLACION)
        if os.path.exists(archivo):
            try:
                with np.load(archivo, allow_pickle=False) as d:
                    pob = d["pob"]
                    if pob.shape[1] == self.n_param:
                        self._cargar_poblacion(d, pob)
                        return
                log.warning("%s tiene %d parámetros por moto (se esperaban %d): se ignora",
                            archivo, pob.shape[1], self.n_param)
            except (OSError, KeyError, ValueError) as ex:
                log.warning("no se pudo leer %s: %r", archivo, ex)
        m = cargar_mejor(self.modo, self.dir_datos, self.superficie)
        if m is not None:
            pesos, d = m
            self.pob[0] = pesos
            self.hay_campeon = True
            self.pob[1:self.n // 2] = pesos + self.rng.normal(0, 0.05, (self.n // 2 - 1, self.n_param))
            self.nivel = int(d.get("nivel", 1))
            self.generacion = int(d.get("generacion", 0)) + 1
        elif self.modo == "ciudad":
            archivo_t = ruta(C.ARCHIVO_POBLACION, "terreno", self.dir_datos)
            if os.path.exists(archivo_t):
                try:
                    with np.load(archivo_t) as d:
                        pob = d["pob"]
                        gen_t = int(d["generacion"]) if "generacion" in d.files else 0
                    if pob.shape[1] == self.n_param:
                        k = min(len(pob), self.n)
                        self.pob[:k] = pob[:k]
                        self.desde_terreno = True
                        self.generacion = gen_t + 1
                except (OSError, KeyError, ValueError) as ex:
                    log.warning("no se pudo leer %s: %r", archivo_t, ex)
            if not self.desde_terreno:
                m = cargar_mejor("terreno", self.dir_datos)
                if m is not None:
                    pesos, d = m
                    self.pob[0] = pesos
                    self.pob[1:self.n // 2] = pesos + self.rng.normal(
                        0, 0.05, (self.n // 2 - 1, self.n_param))
                    self.desde_terreno = True
                    self.generacion = int(d.get("generacion", 0)) + 1

    def _cargar_poblacion(self, d, pob):
        k = min(len(pob), self.n)
        self.pob[:k] = pob[:k]
        self.generacion = int(d["generacion"]) + 1
        self.nivel = int(d["nivel"])
        if "etapa" in d.files:
            self.etapa = int(d["etapa"])
        formato = int(d["formato"]) if "formato" in d.files else 1
        self._cargar_historial()
        if formato >= 2:
            self.sigma = float(d["sigma"])
            self.racha = int(d["racha"])
            self.hay_campeon = bool(d["hay_campeon"]) if "hay_campeon" in d.files else True
            if "sigmas" in d.files:
                self.sigmas = np.full(self.n, self.sigma)
                m = min(k, len(d["sigmas"]))
                self.sigmas[:m] = d["sigmas"][:m]
            if "rng" in d.files:
                try:
                    self.rng.bit_generator.state = json.loads(str(d["rng"]))
                except (ValueError, TypeError, KeyError) as ex:
                    log.warning("no se pudo restaurar el estado del generador: %r", ex)
            if "validada" in d.files:
                self.validada = json.loads(str(d["validada"])) or None
            self._estado_opt = _leer_estado_opt(d)
            if "hist_generacion" in d.files:
                exactos = dict(zip(d["hist_generacion"].tolist(), d["hist_mejor"].tolist()))
                for h in self.historial:
                    if h["generacion"] in exactos:
                        h["mejor"] = exactos[h["generacion"]]
            h = str(d["config_hash"]) if "config_hash" in d.files else None
            if h and h != hash_config():
                log.warning("la población se entrenó con otra configuración (hash %s, actual %s)",
                            h, hash_config())
            return
        m = cargar_mejor(self.modo, self.dir_datos, self.superficie)
        if m is not None and len(m[0]) == self.n_param:
            self.pob[0] = m[0]
            self.hay_campeon = True

    def _cargar_historial(self):
        archivo = self.ruta(C.ARCHIVO_HISTORIAL)
        if not os.path.exists(archivo):
            return
        try:
            with open(archivo, encoding="utf-8") as f:
                for fila in csv.DictReader(f):
                    h = {"generacion": int(fila["generacion"]), "nivel": int(fila["nivel"]),
                         "mejor": float(fila["mejor"]), "promedio": float(fila["promedio"]),
                         "llegaron": float(fila["llegaron_%"]),
                         "terminadas_lider": int(fila["terminadas_lider"]),
                         "vel_lider": float(fila.get("vel_lider_kmh") or 0),
                         "vel_rapida": float(fila.get("vel_rapida_kmh") or 0),
                         "pistas": C.PISTAS_POR_GENERACION}
                    if fila.get("llegadas_limpias_pct"):
                        h["llegadas_limpias"] = float(fila["llegadas_limpias_pct"])
                    if fila.get("reintentos_lider"):
                        h["reintentos_lider"] = float(fila["reintentos_lider"])
                    if fila.get("terminadas_limpias_lider"):
                        h["terminadas_limpias_lider"] = int(fila["terminadas_limpias_lider"])
                    if fila.get("puntos_lider"):
                        h["puntos_lider"] = fila["puntos_lider"]
                    if fila.get("exitosas_pct"):
                        h["exitosas_pct"] = float(fila["exitosas_pct"])
                    self.historial.append(h)
        except (OSError, ValueError, KeyError) as ex:
            log.warning("no se pudo leer %s: %r (el historial empieza vacío)", archivo, ex)
            self.historial = []

    def _guardar_mejor(self, pesos, resumen, extra=None):
        d = {"capas": list(C.CAPAS), "generacion": self.generacion, "modo": self.modo,
             "nivel": resumen["nivel"], "aptitud": resumen["mejor"],
             "pistas_terminadas": resumen["terminadas_lider"],
             "pistas_terminadas_limpias": resumen["terminadas_limpias_lider"],
             "formato": FORMATO, "version": VERSION, "config_hash": hash_config()}
        if self.modo == "ciudad":
            d["etapa"] = self.etapa
            d["plan"] = "automatico" if self.plan_automatico else "manual"
        if clima_activo():
            d["clima_visto"] = sorted(set(getattr(self, "climas", [])))
        if extra:
            d.update(extra)
        d["pesos"] = [round(float(w), 6) for w in pesos]
        _escribir_atomico(self.ruta(C.ARCHIVO_MEJOR), lambda f: json.dump(d, f))

    def _guardar_poblacion(self):
        datos = dict(pob=self.pob, generacion=self.generacion, nivel=self.nivel,
                     formato=FORMATO, version=VERSION, config_hash=hash_config(),
                     sigma=self.sigma, racha=self.racha, hay_campeon=self.hay_campeon,
                     rng=json.dumps(self.rng.bit_generator.state),
                     validada=json.dumps(self.validada or {}),
                     hist_generacion=np.array([h["generacion"] for h in self.historial],
                                              dtype=np.int64),
                     hist_mejor=np.array([h["mejor"] for h in self.historial], dtype=float))
        if self.sigmas is not None:
            datos["sigmas"] = self.sigmas
        if self.modo == "ciudad":
            datos["etapa"] = self.etapa
        if self.opt is not None:
            datos.update(_empacar_estado_opt(self.opt, self.nombre_opt))
        _escribir_atomico(self.ruta(C.ARCHIVO_POBLACION), lambda f: np.savez(f, **datos),
                          binario=True)

    def _guardar_historial(self, resumen):
        archivo = self.ruta(C.ARCHIVO_HISTORIAL)
        comps = sorted(resumen.get("componentes_lider") or {})
        columnas = COLUMNAS_V9 + COLUMNAS_V10 + [f"comp_{k}" for k in comps]
        fila = {"generacion": self.generacion, "nivel": resumen["nivel"],
                "mejor": f"{resumen['mejor']:.2f}", "promedio": f"{resumen['promedio']:.2f}",
                "llegaron_%": f"{resumen['llegaron']:.1f}",
                "terminadas_lider": resumen["terminadas_lider"],
                "sigma": f"{resumen['sigma']:.3f}",
                "vel_lider_kmh": f"{resumen['vel_lider']:.1f}",
                "llegadas_limpias_pct": f"{resumen['llegadas_limpias']:.1f}",
                "reintentos_lider": f"{resumen['reintentos_lider']:.2f}",
                "terminadas_limpias_lider": resumen["terminadas_limpias_lider"]}
        for k in comps:
            fila[f"comp_{k}"] = f"{resumen['componentes_lider'][k]:.3f}"
        if resumen.get("puntos_lider") is not None:
            columnas = columnas + COLUMNAS_PUNTOS
            fila["puntos_lider"] = resumen["puntos_lider"]
            fila["exitosas_pct"] = f"{resumen['exitosas_pct']:.1f}"
        if getattr(C, "NICHO_RAPIDAS", 0):
            columnas = columnas + COLUMNAS_NICHO
            fila["vel_rapida_kmh"] = f"{resumen.get('vel_rapida', 0.0):.1f}"
        if not os.path.exists(archivo) or self.generacion == 1:
            _escribir_csv(archivo, columnas, [fila])
            return
        with open(archivo, encoding="utf-8", newline="") as f:
            filas = list(csv.reader(f))
        cabecera = filas[0] if filas else []
        if cabecera == columnas:
            with open(archivo, "a", newline="", encoding="utf-8") as f:
                csv.DictWriter(f, fieldnames=columnas, restval="").writerow(fila)
            return
        union = cabecera + [c for c in columnas if c not in cabecera]
        viejas = [dict(zip(cabecera, r)) for r in filas[1:] if r]
        _escribir_csv(archivo, union, viejas + [fila])

    def _guardar_campeon(self, pesos, resumen, etapa):
        try:
            nuevo = {"generacion": int(resumen["generacion"]), "modo": self.modo,
                     "etapa": int(etapa) if self.modo == "ciudad" else 0,
                     "plan": ("automatico" if self.plan_automatico or self.modo != "ciudad"
                              else "manual"),
                     "nivel": int(resumen["nivel"]), "aptitud": float(resumen["mejor"]),
                     "limpias": int(resumen["terminadas_limpias_lider"]),
                     "llegadas_limpias": int(resumen["terminadas_limpias_lider"]),
                     "terminadas": int(resumen["terminadas_lider"]),
                     "exitosas": int(resumen.get("exitosas_lider", 0)),
                     "puntos": resumen.get("puntos_lider"),
                     "pistas": int(resumen["pistas"]),
                     "clima_visto": list(getattr(self, "climas", [])),
                     "pesos": [round(float(w), 6) for w in pesos]}
            archivo = ruta_campeones(self.modo, self.dir_datos)
            previa = (self._campeones_semilla if self._campeones_semilla is not None
                      and not os.path.exists(archivo) else cargar_campeones(self.modo, self.dir_datos))
            lista = actualizar_campeones(previa, nuevo)
            if lista is None:
                if os.path.exists(archivo) or not previa:
                    return
                lista = previa
            d = {"formato": 1, "capas": list(C.CAPAS), "modo": self.modo, "campeones": lista}
            _escribir_atomico(archivo, lambda f: json.dump(d, f, ensure_ascii=False))
            self._campeones_semilla = None
            resumen["salon_fama"] = next((1 + i for i, c in enumerate(lista) if c is nuevo), None)
        except (OSError, ValueError, TypeError, KeyError) as ex:
            log.warning("no se pudo actualizar el salón de la fama: %r", ex)

    def reiniciar(self):
        for nombre in (C.ARCHIVO_MEJOR, C.ARCHIVO_POBLACION, C.ARCHIVO_HISTORIAL):
            try:
                os.remove(self.ruta(nombre))
            except FileNotFoundError:
                pass
            except OSError as ex:
                log.warning("no se pudo borrar %s: %r", self.ruta(nombre), ex)
        self.cerrar()
        self.__init__(self.n, continuar=False, modo=self.modo, red_vial=self.red_vial,
                      ruta=self.ruta_fija, dir_datos=self.dir_datos, procesos=self.procesos,
                      guardar=self.guardar)

    def _pool_listo(self):
        foto = P.foto_config()
        if self._pool is not None and foto != self._foto_pool:
            self.cerrar()
        if self._pool is None:
            self._pool = P.crear_pool(self.procesos, self.red_vial)
            self._foto_pool = foto
        return self._pool

    def cerrar(self):
        pendiente = getattr(self, "_futuros", None) is not None
        self._futuros = None
        if getattr(self, "_pool", None) is not None:
            self._pool.shutdown(wait=not pendiente, cancel_futures=True)
            self._pool = None

    def __del__(self):
        try:
            self.cerrar()
        except Exception:
            pass

    def _spec(self, i):
        p = self.pistas[i]
        if isinstance(p, PistaCalle):
            sup, circ = getattr(p, "_pedido", (p.superficie, getattr(p, "circuito", "no")))
            spec = ("ciudad", p.nivel, p.semilla, self.ruta_fija if p.personalizada else None,
                    sup, circ)
        else:
            spec = ("terreno", p.nivel, p.semilla, None)
        return P.con_clima(spec, self.climas_obj[i])

    def _preparar_generacion(self):
        base = int(self.rng.integers(1 << 30))
        self.pistas = [self.nueva_pista(self.nivel, base + i) for i in range(C.PISTAS_POR_GENERACION)]
        if self.ruta_fija is not None:
            self.pistas[0] = pista_calle(self.red_vial, self.nivel, base, ruta=self.ruta_fija,
                                         superficie=self.superficie)
        k = len(self.pistas)
        if self.modo == "ciudad" and self.etapa >= 1 and k >= 2:
            semilla = base + k - 1
            sup, circ = self.config_pista(semilla, semilla % self.etapa)
            self.pistas[-1] = pista_calle(self.red_vial, self.nivel, semilla, superficie=sup,
                                          circuito=circ)
            self.pistas[-1].repaso = semilla % self.etapa
        k = len(self.pistas)
        self.climas_obj = [clima_de_pista(p.semilla, p.nivel, self._etapa_de_pista(p))
                           for p in self.pistas]
        self.climas = [nombre_clima(c) for c in self.climas_obj]
        self.aptitudes = np.zeros((k, self.n))
        self.llegadas = np.zeros((k, self.n), dtype=bool)
        self.limpias = np.zeros((k, self.n), dtype=bool)
        self.reintentos = np.zeros((k, self.n))
        self.velocidades = np.zeros((k, self.n))
        self.vel_avance = np.zeros((k, self.n))
        self.componentes = [None] * k
        self.exitosas = np.zeros((k, self.n), dtype=bool)
        self.puntos = np.zeros((k, self.n))
        self.total_puntos = [None] * k
        self.i_pista = 0
        self.sim = P.simulador(self.pistas[0], self.pob, base, self.climas_obj[0])

    def _etapa_de_pista(self, p):
        if self.modo != "ciudad":
            return 0
        return int(getattr(p, "repaso", self.etapa))

    def nueva_pista(self, nivel, semilla):
        if self.modo == "ciudad":
            sup, circ = self.config_pista(semilla)
            return pista_calle(self.red_vial, nivel, semilla, superficie=sup, circuito=circ)
        return Pista(nivel, semilla)

    def _registrar(self, i, res):
        self.aptitudes[i] = res["aptitud"]
        self.llegadas[i] = res["llegadas"]
        self.limpias[i] = res["limpias"]
        self.reintentos[i] = res["reintentos"]
        p = self.pistas[i]
        self.velocidades[i] = np.where(res["llegadas"],
                                       (p.meta - p.salida) / np.maximum(res["t_fin"], 1e-3) * 3.6, 0.0)
        self.componentes[i] = res["componentes"]
        if "progreso" in res:
            largo = max(p.meta - p.salida, 1e-3)
            avance = np.clip(res["progreso"] / largo, 0.0, 1.0)
            self.vel_avance[i] = res["progreso"] / np.maximum(res["t_fin"], 1e-3) * 3.6 * avance
        if "exitosas" in res:
            self.exitosas[i] = res["exitosas"]
            self.puntos[i] = res["puntos"]
            self.total_puntos[i] = int(res["total_puntos"])

    def avanzar_turbo(self):
        futuros = getattr(self, "_futuros", None)
        if futuros is None:
            n = min(P.procesos_disponibles(),
                    max(len(self.pistas), int(getattr(C, "PISTAS_VALIDACION", 10))
                        if getattr(C, "VALIDAR_CAMPEONA", False) else len(self.pistas)))
            if n <= 1 or self.i_pista != 0 or self.sim.t > 0:
                return self.avanzar(25)
            if self.procesos < n:
                self.cerrar()
                self.procesos = n
            specs = [self._spec(i) for i in range(len(self.pistas))]
            self._futuros = P.lanzar(self._pool_listo(), specs, self.pob)
            return None
        if not all(f.done() for f in futuros):
            return None
        self._futuros = None
        for i, f in enumerate(futuros):
            self._registrar(i, f.result())
        self.i_pista = len(self.pistas)
        return self._evolucionar()

    def en_paralelo(self):
        return self.procesos if getattr(self, "_futuros", None) is not None else 0

    def avanzar(self, pasos):
        if getattr(self, "_futuros", None) is not None:
            return self.avanzar_turbo()
        self.sim.correr(pasos)
        if not self.sim.terminado:
            return None
        self._registrar(self.i_pista, P.resultados(self.sim))
        self.i_pista += 1
        if self.i_pista < len(self.pistas):
            self.sim = P.simulador(self.pistas[self.i_pista], self.pob,
                                   self.pistas[self.i_pista].semilla, self.climas_obj[self.i_pista])
            return "pista"
        return self._evolucionar()

    def correr_generacion(self):
        if self.procesos > 1 and self.i_pista == 0:
            specs = [self._spec(i) for i in range(len(self.pistas))]
            for i, res in enumerate(P.evaluar(self._pool_listo(), specs, self.pob)):
                self._registrar(i, res)
            self.i_pista = len(self.pistas)
            return self._evolucionar()
        while True:
            r = self.avanzar(10_000)
            if isinstance(r, dict):
                return r

    def semillas_validacion(self, nivel=None):
        nivel = self.nivel if nivel is None else nivel
        return [2 ** 30 + 1000 * nivel + j for j in range(int(getattr(C, "PISTAS_VALIDACION", 10)))]

    def evaluar_validacion(self, pesos, nivel=None):
        nivel = self.nivel if nivel is None else nivel
        pesos = np.atleast_2d(pesos)
        if self.modo == "ciudad":
            specs = [(self.modo, nivel, s, None) + self.config_pista(s)
                     for s in self.semillas_validacion(nivel)]
        else:
            specs = [(self.modo, nivel, s, None) for s in self.semillas_validacion(nivel)]
        etapa = self.etapa if self.modo == "ciudad" else 0
        specs = [P.con_clima(sp, clima_de_pista(sp[2], nivel, etapa)) for sp in specs]
        if self.procesos > 1:
            res = P.evaluar(self._pool_listo(), specs, pesos)
        else:
            res = [P.evaluar_spec(s, pesos, self.red_vial) for s in specs]
        apt = np.mean([r["aptitud"] for r in res], axis=0)
        limpias = np.mean([r["limpias"] for r in res], axis=0)
        return apt, limpias

    def _validar(self, orden, resumen):
        cand = [int(i) for i in orden[:int(getattr(C, "TOP_VALIDAR", 5))]]
        pesos = [self.pob[i] for i in cand]
        guardada = cargar_mejor(self.modo, self.dir_datos, self.superficie) if self.guardar else None
        if guardada is not None and len(guardada[0]) == self.n_param:
            pesos.append(guardada[0])
        else:
            guardada = None
        apt, limpias = self.evaluar_validacion(np.array(pesos))
        j = int(np.argmax(apt[:len(cand)]))
        ref = float(apt[-1]) if guardada is not None else None
        reemplazo = ref is None or apt[j] > ref
        resumen["validacion"] = {"aptitud": float(apt[j]), "limpias_pct": 100 * float(limpias[j]),
                                 "aptitud_guardada": ref, "reemplazo": bool(reemplazo),
                                 "nivel": self.nivel}
        if reemplazo:
            self.validada = {"aptitud": float(apt[j]), "limpias_pct": 100 * float(limpias[j]),
                             "nivel": self.nivel, "generacion": self.generacion,
                             "pistas": len(self.semillas_validacion())}
            if self.guardar:
                self._guardar_mejor(self.pob[cand[j]], resumen, {"validacion": self.validada})
        elif self.validada is not None:
            self.validada["nivel"] = self.nivel

    def _iniciar_optimizador(self):
        nombre = str(getattr(C, "OPTIMIZADOR", "ga")).lower()
        self.nombre_opt = nombre
        if nombre == "ga":
            return
        try:
            import optimizadores
        except ImportError as ex:
            raise RuntimeError(f"OPTIMIZADOR={nombre!r} necesita optimizadores.py: {ex}") from ex
        self.opt = _llamar(optimizadores.crear, nombre=nombre, n=self.n, n_param=self.n_param,
                           capas=C.CAPAS, rng=self.rng, x0=self.pob.copy(),
                           pob=self.pob.copy(), semilla=self.semilla)
        est = self._estado_opt
        if est is not None and est.get("_nombre") == nombre:
            est = {k: v for k, v in est.items() if k != "_nombre"}
            self.opt.cargar_estado(est)
            self.sigma = float(getattr(self.opt, "sigma", self.sigma))
            return
        if est is not None:
            log.warning("el checkpoint es del optimizador %r; se empieza %r desde la población",
                        est.get("_nombre"), nombre)
        self.pob = np.asarray(self.opt.ask(), dtype=float)
        self.sigma = float(getattr(self.opt, "sigma", self.sigma))

    def _torneo(self, apt):
        idx = self.rng.integers(self.n, size=C.TORNEO)
        g = int(idx[np.argmax(apt[idx])])
        return self.pob[g], g

    def _evolucionar(self):
        apt = self.aptitudes.mean(0)
        orden = np.argsort(-apt)
        lider = int(orden[0])
        pesos_lider = self.pob[lider].copy()
        etapa_lider = self.etapa
        terminadas = int(self.llegadas[:, lider].sum())
        terminadas_limpias = int(self.limpias[:, lider].sum())
        vel = self.velocidades[:, lider][self.llegadas[:, lider]]
        comps = None
        if all(c is not None for c in self.componentes):
            comps = {k: float(np.mean([c[k][lider] for c in self.componentes]))
                     for k in self.componentes[0]}
        resumen = {
            "campeon_anterior": float(apt[0]) if self.hay_campeon else None,
            "vel_lider": float(vel.mean()) if len(vel) else 0.0,
            "generacion": self.generacion, "nivel": self.nivel,
            "mejor": float(apt[lider]), "promedio": float(apt.mean()),
            "llegaron": 100.0 * float(self.llegadas.mean()),
            "llegadas_limpias": 100.0 * float(self.limpias.mean()),
            "terminadas_lider": terminadas, "terminadas_limpias_lider": terminadas_limpias,
            "reintentos_lider": float(self.reintentos[:, lider].mean()),
            "componentes_lider": comps,
            "sigma": self.sigma,
            "vel_rapida": self._vel_rapida(),
            "pistas": len(self.pistas),
            "subio": False,
        }
        if all(t is not None for t in self.total_puntos):
            resumen["puntos_lider"] = f"{int(self.puntos[:, lider].sum())}/{int(sum(self.total_puntos))}"
            resumen["exitosas_pct"] = 100.0 * float(self.exitosas.mean())
            resumen["exitosas_lider"] = int(self.exitosas[:, lider].sum())
        cuenta = terminadas_limpias if getattr(C, "SUBIR_POR_LIMPIAS", False) else terminadas
        if cuenta == len(self.pistas):
            self.racha += 1
            if self.racha >= C.RACHA_PARA_SUBIR and self.nivel < C.NIVEL_MAX:
                self.nivel += 1
                self.racha = 0
                resumen["subio"] = True
                resumen["texto_nivel"] = (descripcion_nivel_ciudad(self.nivel) if self.modo == "ciudad"
                                          else descripcion_nivel(self.nivel))
        else:
            self.racha = 0
        resumen["graduado"] = (self.modo == "terreno" and self.nivel == C.NIVEL_MAX
                               and self.racha >= C.RACHA_PARA_SUBIR)
        if self.modo == "ciudad":
            resumen["etapa"] = self.etapa
            if (self.plan_automatico and self.nivel == C.NIVEL_MAX
                    and self.racha >= C.RACHA_PARA_SUBIR and self.etapa < len(etapas_calles()) - 1):
                self.etapa += 1
                self.nivel, self.racha = 1, 0
                self._aplicar_etapa()
                resumen["etapa_nueva"] = self.etapa
                resumen["texto_etapa"] = self.texto_etapa()

        if getattr(C, "VALIDAR_CAMPEONA", False):
            cada = max(1, int(getattr(C, "VALIDAR_CADA", 10)))
            if (self.generacion % cada == 0 or resumen["subio"] or resumen["graduado"]
                    or self.validada is None or self.validada.get("nivel") != self.nivel):
                self._validar(orden, resumen)
        elif self.guardar:
            self._guardar_mejor(self.pob[lider], resumen)

        if self.opt is not None:
            self.opt.tell(apt)
            self.pob = np.asarray(self.opt.ask(), dtype=float)
            self.hay_campeon = True
            self.sigma = float(getattr(self.opt, "sigma", self.sigma))
        else:
            ga = parametros_ga()
            previos = [h["mejor"] for h in self.historial if h["nivel"] == self.nivel]
            if len(previos) >= 20 and np.mean(previos[-10:]) <= np.mean(previos[-20:-10]):
                self.sigma = min(self.sigma * 1.1, ga["sigma_max"])
            else:
                self.sigma = max(self.sigma * 0.97, ga["sigma_min"])
            self._nueva_poblacion(apt, orden, ga)

        self.historial.append(resumen)
        if self.guardar:
            self._guardar_historial(resumen)
            self._guardar_poblacion()
            self._guardar_campeon(pesos_lider, resumen, etapa_lider)
        self.generacion += 1
        self._preparar_generacion()
        return resumen

    def _vel_rapida(self):
        todas = self.llegadas.all(0)
        return float(self.velocidades.mean(0)[todas].max()) if todas.any() else 0.0

    def _aptitud_rapida(self, apt):
        return apt + getattr(C, "PESO_VEL_NICHO", 3.0) * self.vel_avance.mean(0)

    def _nueva_poblacion(self, apt, orden, ga):
        n_param = self.n_param
        auto = ga["autoadaptativa"]
        escala = escala_genes(C.CAPAS) if ga["relativa"] else 1.0
        if auto and (self.sigmas is None or len(self.sigmas) != self.n):
            self.sigmas = np.full(self.n, self.sigma)
        tau = 1.0 / np.sqrt(2.0 * np.sqrt(n_param))
        elite = list(orden[:C.ELITE])
        frac_rap = float(getattr(C, "NICHO_RAPIDAS", 0.0) or 0.0)
        rapida = self._aptitud_rapida(apt) if frac_rap > 0 else None
        if rapida is not None:
            extra = [int(i) for i in np.argsort(-rapida) if int(i) not in elite]
            elite += extra[:int(getattr(C, "ELITE_RAPIDAS", 0))]
        nueva = [self.pob[i].copy() for i in elite]
        sig_nueva = [float(self.sigmas[i]) for i in elite] if auto else None
        self.hay_campeon = True
        n_inmig = int(round(ga["inmigrantes"] * self.n))
        n_hijos = self.n - n_inmig - len(nueva)
        n_rap = int(round(frac_rap * n_hijos)) if rapida is not None else 0
        while len(nueva) < self.n - n_inmig:
            sel = rapida if len(nueva) >= self.n - n_inmig - n_rap else apt
            a, ia = self._torneo(sel)
            if self.rng.random() < ga["prob_cruce"]:
                b, _ = self._torneo(sel)
                mezcla = self.rng.random(n_param) < 0.5
                hijo = np.where(mezcla, a, b)
            else:
                hijo = a.copy()
            if auto:
                s = float(np.clip(self.sigmas[ia] * np.exp(tau * self.rng.normal()),
                                  ga["sigma_min"], ga["sigma_max"]))
                sig_nueva.append(s)
            else:
                s = self.sigma
            if ga["prob_mutacion"] >= 1.0:
                hijo = hijo + self.rng.normal(0, 1.0, n_param) * (s * escala)
            elif ga["relativa"]:
                muta = self.rng.random(n_param) < ga["prob_mutacion"]
                hijo = hijo + muta * self.rng.normal(0, 1.0, n_param) * (s * escala)
            else:
                muta = self.rng.random(n_param) < ga["prob_mutacion"]
                hijo = hijo + muta * self.rng.normal(0, s, n_param)
            nueva.append(hijo)
        if n_inmig:
            nueva.extend(R.aleatorios(n_inmig, C.CAPAS, self.rng))
            if auto:
                sig_nueva.extend([ga["sigma0"]] * n_inmig)
        self.pob = np.array(nueva)
        if auto:
            self.sigmas = np.array(sig_nueva, dtype=float)
            self.sigma = float(np.median(self.sigmas))


def _llamar(f, **kwargs):
    import inspect
    params = inspect.signature(f).parameters
    if any(p.kind == p.VAR_KEYWORD for p in params.values()):
        return f(**kwargs)
    return f(**{k: v for k, v in kwargs.items() if k in params})


def _empacar_estado_opt(opt, nombre):
    datos, resto = {}, {"_nombre": nombre}
    for k, v in (opt.estado() or {}).items():
        a = np.asarray(v) if isinstance(v, (np.ndarray, list, tuple)) else None
        if a is not None and a.dtype.kind in "biuf" and a.ndim >= 1:
            datos["opt__" + k] = a
        elif isinstance(v, np.generic):
            resto[k] = v.item()
        else:
            resto[k] = v
    datos["opt_json"] = json.dumps(resto, default=lambda o: o.tolist() if hasattr(o, "tolist") else str(o))
    return datos


def _leer_estado_opt(d):
    if "opt_json" not in d.files:
        return None
    est = json.loads(str(d["opt_json"]))
    for k in d.files:
        if k.startswith("opt__"):
            est[k[5:]] = d[k]
    return est


def _acepta_circuito():
    try:
        return "circuito" in inspect.signature(PistaCalle.__init__).parameters
    except (TypeError, ValueError):
        return False


def pista_calle(red, nivel, semilla, ruta=None, superficie=None, circuito=None):
    if ruta is not None:
        circuito = "no"
    elif circuito not in ("no", "misma", "otra"):
        circuito = recorrido_pista(circuito or getattr(C, "CALLES_CIRCUITO", "no"), semilla)
    superficie = superficie or getattr(C, "CALLES_SUPERFICIE", "pavimento")
    if _acepta_circuito():
        p = PistaCalle(red, nivel, semilla, ruta=ruta, superficie=superficie, circuito=circuito)
    else:
        if ruta is not None and len(ruta) > 2:
            ruta = tuple(ruta[:2])
        p = PistaCalle(red, nivel, semilla, ruta=ruta, superficie=superficie)
    p._pedido = (superficie, circuito)
    return p


def hay_entrenamiento_de_calles(dir_datos=None):
    return os.path.exists(ruta(C.ARCHIVO_POBLACION, "ciudad", dir_datos))


def resumen_generacion(r):
    t = (f"Gen {r['generacion']:4d} | nivel {r['nivel']} | mejor {r['mejor']:7.2f} | "
         f"promedio {r['promedio']:6.2f} | llegaron {r['llegaron']:5.1f}% | "
         f"líder terminó {r['terminadas_lider']}/{r['pistas']}")
    if r.get("vel_lider"):
        t += f" a {r['vel_lider']:.0f} km/h"
    if r.get("terminadas_lider") and r.get("terminadas_limpias_lider") is not None:
        t += f" ({r['terminadas_limpias_lider']} sin errores)"
    if r.get("puntos_lider") is not None:
        t += f" | puntos de control {r['puntos_lider']}, exitosas {r['exitosas_pct']:.0f}%"
    if r.get("campeon_anterior") is not None:
        t += f" | +{r['mejor'] - r['campeon_anterior']:.1f} sobre la campeona anterior"
    if r.get("validacion"):
        v = r["validacion"]
        t += (f"\n   validación (nivel {v['nivel']}): {v['aptitud']:.1f}, "
              f"{v['limpias_pct']:.0f} % llegadas limpias"
              + (" -> nueva campeona guardada" if v["reemplazo"] else " -> se conserva la guardada"))
    if r.get("subio"):
        t += f"\n   >>> ¡SUBE DE NIVEL! {r['texto_nivel']}"
    if r.get("graduado"):
        t += "\n   >>> ¡DOMINÓ TODOS LOS TERRENOS! Lista para calles reales."
    if r.get("etapa_nueva") is not None:
        t += f"\n   >>> ¡DOMINÓ LA ETAPA! Pasa a la {r['texto_etapa']} (nivel 1)"
    return t
