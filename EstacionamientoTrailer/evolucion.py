import csv
import json
import math
import os
import random

import config as C
from fisica import Escenario, cajones_posibles, huella
from navegacion import MapaCosto
from plan import GENES_POR_MANIOBRA, TAM_GENOMA, genoma_aleatorio
from simulacion import ESTACIONADO, Generacion

CARPETA = os.path.dirname(os.path.abspath(__file__))
ARCHIVO_HISTORIAL = os.path.join(CARPETA, "historial.csv")


def archivo_mejor(modo, remolques):
    return os.path.join(CARPETA, f"plan_{modo}_{remolques}r.json")


def archivo_progreso(modo, remolques):
    return os.path.join(CARPETA, f"progreso_{modo}_{remolques}r.json")


def _recortar(g):
    return [max(-1.0, min(1.0, w)) for w in g]


class AlgoritmoGenetico:
    def __init__(self, tam=C.POBLACION):
        self.tam = tam
        self.sigma = C.SIGMA_MUTACION
        self.prob_mut = C.PROB_MUTACION

    def _torneo(self, evaluados):
        return max(random.sample(evaluados, C.TORNEO), key=lambda e: e[0])[1]

    def _cruzar(self, a, b):
        if random.random() > C.PROB_CRUCE:
            return list(a)
        if random.random() < 0.5:
            hijo = []
            for i in range(0, len(a), GENES_POR_MANIOBRA):
                hijo.extend((a if random.random() < 0.5 else b)[i:i + GENES_POR_MANIOBRA])
            return hijo
        alfa = random.random()
        return [alfa * x + (1 - alfa) * y for x, y in zip(a, b)]

    def _mutar(self, g):
        for i in range(len(g)):
            r = random.random()
            if r < self.prob_mut:
                g[i] += random.gauss(0, self.sigma)
            elif r < self.prob_mut + 0.01:
                g[i] = random.uniform(-1, 1)
        return _recortar(g)

    def siguiente(self, evaluados):
        evaluados = sorted(evaluados, key=lambda e: e[0], reverse=True)
        nuevos = [list(g) for _, g in evaluados[:C.ELITE]]
        n_afinados = int(self.tam * C.FRACCION_AFINADOS)
        for i in range(n_afinados):
            base = evaluados[i % C.ELITE][1]
            nuevos.append(_recortar([w + random.gauss(0, C.SIGMA_AFINADO) for w in base]))
        n_frescos = int(self.tam * C.FRACCION_NUEVOS)
        while len(nuevos) < self.tam - n_frescos:
            hijo = self._cruzar(self._torneo(evaluados), self._torneo(evaluados))
            nuevos.append(self._mutar(hijo))
        while len(nuevos) < self.tam:
            nuevos.append(genoma_aleatorio())
        return nuevos

    def extincion(self):
        self.sigma = C.SIGMA_MUTACION
        return [genoma_aleatorio() for _ in range(self.tam)]


class Entrenador:

    def __init__(self, tam=C.POBLACION, continuar=False, modo=C.MODO_ESTACIONAR,
                 remolques=C.NUM_REMOLQUES, lugar=C.LUGAR, objetivo=None, tamano=C.TAMANO):
        self.modo = modo
        self._objetivo_pedido = objetivo
        self.remolques = remolques
        self.lugar = lugar
        self.tamano = tamano
        self.objetivo = objetivo
        self.mapas = {}
        self.escenario = self._nuevo_escenario()
        self.ag = AlgoritmoGenetico(tam)
        self.num = 1
        self.historial = []
        self.record = None
        self.extinciones = 0
        self._sin_mejora = 0
        self._atascado = 0
        self._mejor_aptitud = float("-inf")
        self._referencia = float("-inf")

        genomas = [genoma_aleatorio() for _ in range(tam)]
        guardado = cargar_mejor(modo, remolques)
        self._aptitud_guardada = guardado["aptitud"] if guardado else float("-inf")
        progreso = cargar_progreso(modo, remolques) if continuar else None
        if progreso:
            genomas = self._restaurar(progreso, tam)
        elif continuar and guardado:
            self.record = guardado
            self._mejor_aptitud = self._referencia = guardado["aptitud"]
            base = guardado["genoma"]
            genomas = [list(base)] + [self.ag._mutar(list(base)) for _ in range(tam // 2)]
            genomas += [genoma_aleatorio() for _ in range(tam - len(genomas))]
        self.generacion = self._generacion(genomas)

        if progreso and os.path.exists(ARCHIVO_HISTORIAL):
            return
        with open(ARCHIVO_HISTORIAL, "w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(
                ["generacion", "mejor_aptitud", "aptitud_promedio", "estacionados",
                 "chocaron", "mejor_pasos", "mejor_maniobras", "sigma", "extincion"])

    def mapa(self, tamano):
        if tamano not in self.mapas:
            self.mapas[tamano] = MapaCosto(Escenario(self.modo, self.remolques, tamano=tamano))
        return self.mapas[tamano]

    def _restaurar(self, p, tam):
        self.num = p["num"]
        self.historial = p.get("historial", [])
        self.record = p.get("record")
        self.extinciones = p.get("extinciones", 0)
        self._sin_mejora = p.get("sin_mejora", 0)
        self._atascado = p.get("atascado", 0)
        self._mejor_aptitud = p.get("mejor_aptitud", float("-inf"))
        self._referencia = p.get("referencia", float("-inf"))
        self.ag.sigma = p.get("sigma", self.ag.sigma)
        if self._objetivo_pedido is None and p.get("objetivo") is not None:
            self.objetivo = p["objetivo"]
            self.escenario = self._nuevo_escenario()
        genomas = [list(g) for g in p["genomas"] if len(g) == TAM_GENOMA][:tam]
        return genomas + [genoma_aleatorio() for _ in range(tam - len(genomas))]

    def guardar_progreso(self):
        datos = {
            "huella": huella(self.modo, self.remolques),
            "tam_genoma": TAM_GENOMA,
            "num": self.num,
            "sigma": self.ag.sigma,
            "extinciones": self.extinciones,
            "sin_mejora": self._sin_mejora,
            "atascado": self._atascado,
            "mejor_aptitud": self._mejor_aptitud,
            "referencia": self._referencia,
            "objetivo": self.objetivo,
            "record": self.record,
            "historial": self.historial[-2000:],
            "genomas": [a.genoma for a in self.generacion.agentes],
        }
        archivo = archivo_progreso(self.modo, self.remolques)
        with open(archivo + ".tmp", "w", encoding="utf-8") as f:
            json.dump(datos, f, ensure_ascii=False)
        os.replace(archivo + ".tmp", archivo)

    def _nuevo_escenario(self):
        tamano = random.choice(list(C.TAMANOS)) if self.tamano == "azar" else self.tamano
        posibles = cajones_posibles(self.modo, self.remolques, tamano)
        if self.lugar == "camara" or self.objetivo not in posibles:
            self.objetivo = random.choice(posibles)
        return Escenario(self.modo, self.remolques, self.objetivo, tamano)

    def _generacion(self, genomas):
        return Generacion(genomas, self.escenario, self.mapa(self.escenario.tamano),
                          busqueda=self.lugar == "camara")

    def reiniciar_generacion(self, lugar=None, objetivo=None, tamano=None):
        if lugar is not None:
            self.lugar = lugar
        if tamano is not None:
            self.tamano = tamano
        if objetivo is not None:
            self.objetivo = objetivo
            self.escenario = Escenario(self.modo, self.remolques, objetivo, self.escenario.tamano)
        else:
            self.escenario = self._nuevo_escenario()
        self.generacion = self._generacion([a.genoma for a in self.generacion.agentes])

    @property
    def ya_se_estaciono(self):
        return bool(self.record and self.record.get("estacionado"))

    def cerrar_generacion(self):
        agentes = self.generacion.agentes
        evaluados = [(a.aptitud(), a.genoma) for a in agentes]
        conteo = self.generacion.conteo()
        mejor_ag = max(agentes, key=lambda a: a.aptitud())
        mejor_apt = mejor_ag.aptitud()
        exito = mejor_ag.estado == ESTACIONADO

        stats = {
            "generacion": self.num,
            "mejor": mejor_apt,
            "promedio": sum(e[0] for e in evaluados) / len(evaluados),
            "estacionados": conteo[ESTACIONADO],
            "chocaron": conteo["chocó"],
            "tijeras": conteo["tijera"],
            "pasos": mejor_ag.pasos if exito else None,
            "maniobras": mejor_ag.maniobras if exito else None,
            "sigma": self.ag.sigma,
            "extincion": False,
        }

        if mejor_apt > self._mejor_aptitud + 1e-6:
            self._mejor_aptitud = mejor_apt
            self._sin_mejora = 0
            self.ag.sigma = max(0.08, self.ag.sigma * 0.95)
            self._registrar_record(mejor_ag, mejor_apt)
        else:
            self._sin_mejora += 1
            if self._sin_mejora >= C.ESTANCAMIENTO:
                self.ag.sigma = min(1.0, self.ag.sigma * 1.5)
                self._sin_mejora = 0

        if mejor_apt > self._referencia + C.MEJORA_NOTABLE:
            self._referencia = mejor_apt
            self._atascado = 0
        else:
            self._atascado += 1
        if not self.ya_se_estaciono and self._atascado >= C.EXTINCION:
            stats["extincion"] = True
            self.extinciones += 1
            self._atascado = 0
            nuevos = self.ag.extincion()
            self._mejor_aptitud = self._referencia = float("-inf")
        else:
            nuevos = self.ag.siguiente(evaluados)

        self.historial.append(stats)
        with open(ARCHIVO_HISTORIAL, "a", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow([
                stats["generacion"], round(stats["mejor"], 2), round(stats["promedio"], 2),
                stats["estacionados"], stats["chocaron"], stats["pasos"] or "",
                stats["maniobras"] or "", round(stats["sigma"], 3),
                "sí" if stats["extincion"] else ""])

        self.num += 1
        self.escenario = self._nuevo_escenario()
        self.generacion = self._generacion(nuevos)
        self.guardar_progreso()
        return stats

    def _registrar_record(self, ag, aptitud):
        self.record = {
            "aptitud": aptitud,
            "generacion": self.num,
            "estacionado": ag.estado == ESTACIONADO,
            "pasos": ag.pasos,
            "segundos": round(ag.pasos * C.DT, 1),
            "maniobras": ag.maniobras,
            "modo": self.modo,
            "remolques": self.remolques,
            "cajon": self.escenario.objetivo,
            "tamano": self.escenario.tamano,
            "lugar": self.lugar,
            "huella": self.escenario.huella,
            "espacio_linea_cm": round(ag.espacio_a_lineas() * 100),
            "desvio_cm": round(ag.desvio_lateral() * 100, 1),
            "error_grados": round(math.degrees(ag.error_angulo()), 2),
            "plan": [m.describir() for m in ag.plan],
            "genoma": ag.genoma,
        }
        if aptitud > self._aptitud_guardada:
            self._aptitud_guardada = aptitud
            guardar_mejor(self.record, self.modo, self.remolques)


def guardar_mejor(record, modo, remolques):
    with open(archivo_mejor(modo, remolques), "w", encoding="utf-8") as f:
        json.dump(record, f, ensure_ascii=False)


def cargar_mejor(modo, remolques):
    archivo = archivo_mejor(modo, remolques)
    if not os.path.exists(archivo):
        return None
    with open(archivo, encoding="utf-8") as f:
        datos = json.load(f)
    if len(datos.get("genoma", [])) != TAM_GENOMA:
        return None
    if datos.get("huella") != huella(modo, remolques):
        return None
    return datos


def cargar_progreso(modo, remolques):
    try:
        with open(archivo_progreso(modo, remolques), encoding="utf-8") as f:
            datos = json.load(f)
    except (OSError, ValueError):
        return None
    if datos.get("tam_genoma") != TAM_GENOMA or datos.get("huella") != huella(modo, remolques):
        return None
    return datos


def borrar_progreso(modo, remolques):
    try:
        os.remove(archivo_progreso(modo, remolques))
    except OSError:
        pass


def resumen_generacion(s):
    p = f"{s['pasos'] * C.DT:.1f} s, {s['maniobras']} maniobra(s)" if s["pasos"] else "—"
    extra = "  << EXTINCIÓN: población renovada" if s["extincion"] else ""
    return (f"Gen {s['generacion']:4d} | mejor {s['mejor']:7.1f} | prom {s['promedio']:7.1f} | "
            f"estacionados {s['estacionados']:3d} | chocaron {s['chocaron']:3d} | "
            f"tijera {s['tijeras']:3d} | {p}{extra}")
