import math
from collections import deque

import numpy as np

from biomecanica import LADOS, NOMBRE_LADO, FEM, OTRO, HOMBRO, CODO, CADERA, RODILLA, TOBILLO, MUNECA


def _comp_codo(c, lado):
    v = c.codo_flexion(lado)
    return "Mantén el codo extendido" if v > 25 else None


def _comp_tronco_atras(c, lado):
    return "No eches el tronco hacia atrás" if c.tronco_flexion() < -10 else None


def _comp_tronco_lado(c, lado):
    return "Mantén el tronco recto, sin inclinarte de lado" if abs(c.tronco_lateral()) > 8 else None


def _comp_tronco_adelante(c, lado):
    return "Inclinas demasiado el tronco hacia adelante" if c.tronco_flexion() > 45 else None


def _comp_brazo_pegado(c, lado):
    return "Mantén el brazo pegado al cuerpo" if c.hombro_flexion(lado) > 35 or c.hombro_abduccion(lado) > 35 else None


def _comp_pierna_al_frente(c, lado):
    return "Lleva la pierna hacia el lado, no al frente" if c.cadera_flexion(lado) > 25 else None


def _comp_muslo(c, lado):
    return "Mantén el muslo vertical" if c.cadera_flexion(lado) > 30 else None


def _comp_valgo(c, lado):
    return "La rodilla se va hacia adentro (valgo)" if c.rodilla_valgo(lado) > 10 else None


def _comp_flexion_tronco(c, lado):
    return "Inclínate de lado, no hacia adelante" if abs(c.tronco_flexion()) > 15 else None


ROM = [
    dict(id="hombro_flex", nombre="Flexión de hombro", region="Hombro", normal=180, funcional=120, umbral=25,
         metrica=lambda c, l: c.hombro_flexion(l), vertice=HOMBRO, segmento=CODO, ref="abajo_tronco",
         puntos=lambda l: (HOMBRO[l], CODO[l], 23, 24),
         instr="De frente al Kinect. Con el codo recto y el pulgar hacia arriba, sube el brazo por delante hasta donde puedas y bájalo despacio.",
         comps=(_comp_codo, _comp_tronco_atras)),
    dict(id="hombro_abd", nombre="Abducción de hombro", region="Hombro", normal=180, funcional=120, umbral=25,
         metrica=lambda c, l: c.hombro_abduccion(l), vertice=HOMBRO, segmento=CODO, ref="abajo_tronco",
         puntos=lambda l: (HOMBRO[l], CODO[l], 23, 24),
         instr="De frente al Kinect. Con el codo recto y la palma al frente, separa el brazo por el lado hasta arriba y bájalo despacio.",
         comps=(_comp_codo, _comp_tronco_lado)),
    dict(id="codo_flex", nombre="Flexión de codo", region="Codo", normal=150, funcional=130, umbral=30,
         metrica=lambda c, l: c.codo_flexion(l), vertice=CODO, segmento=MUNECA, ref="brazo",
         puntos=lambda l: (HOMBRO[l], CODO[l], MUNECA[l]),
         instr="De frente o ligeramente de lado. Con el brazo pegado al cuerpo, dobla el codo llevando la mano al hombro y vuelve a estirar.",
         comps=(_comp_brazo_pegado,)),
    dict(id="cadera_flex", nombre="Flexión de cadera", region="Cadera", normal=120, funcional=90, umbral=20,
         metrica=lambda c, l: c.cadera_flexion(l), vertice=CADERA, segmento=RODILLA, ref="abajo_tronco",
         puntos=lambda l: (CADERA[l], RODILLA[l], 11, 12),
         instr="De pie, apóyate en una silla si lo necesitas. Sube la rodilla hacia el pecho y regresa. Mantén la espalda recta.",
         comps=(_comp_tronco_atras, _comp_tronco_lado)),
    dict(id="cadera_abd", nombre="Abducción de cadera", region="Cadera", normal=45, funcional=30, umbral=10,
         metrica=lambda c, l: c.cadera_abduccion(l), vertice=CADERA, segmento=RODILLA, ref="abajo_tronco",
         puntos=lambda l: (CADERA[l], RODILLA[l], 11, 12),
         instr="De pie y de frente, apóyate si lo necesitas. Con la rodilla recta, separa la pierna hacia el lado y regresa.",
         comps=(_comp_tronco_lado, _comp_pierna_al_frente)),
    dict(id="rodilla_flex", nombre="Flexión de rodilla (de pie)", region="Rodilla", normal=135, funcional=110, umbral=25,
         metrica=lambda c, l: c.rodilla_flexion(l), vertice=RODILLA, segmento=TOBILLO, ref="muslo",
         puntos=lambda l: (CADERA[l], RODILLA[l], TOBILLO[l]),
         instr="De pie y de lado al Kinect, apoyado en una silla. Lleva el talón hacia el glúteo sin mover el muslo y regresa.",
         comps=(_comp_muslo,)),
    dict(id="sentadilla", nombre="Sentadilla (control de rodilla)", region="Rodilla", normal=135, funcional=90, umbral=25,
         metrica=lambda c, l: c.rodilla_flexion(l), vertice=RODILLA, segmento=TOBILLO, ref="muslo",
         puntos=lambda l: (CADERA[l], RODILLA[l], TOBILLO[l]),
         instr="De frente, pies al ancho de la cadera. Baja como si te sentaras en una silla y sube. Las rodillas deben apuntar al frente.",
         comps=(_comp_valgo, _comp_tronco_adelante), defecto="ambos"),
    dict(id="tronco_lat", nombre="Inclinación lateral del tronco", region="Columna", normal=35, funcional=25, umbral=8,
         metrica=lambda c, l: c.tronco_lateral() * (1 if l == "izq" else -1), vertice=None, segmento=None, ref="vertical",
         puntos=lambda l: (11, 12, 23, 24),
         instr="De pie, de frente y con los brazos a los lados. Desliza la mano por el muslo inclinándote de lado y regresa al centro.",
         comps=(_comp_flexion_tronco,)),
]

OTRAS = [
    dict(id="postura", nombre="Evaluación postural", region="Postura", tipo="postura",
         instr="De pie, de frente al Kinect a unos 2.5 m, brazos relajados y mirada al frente. Quédate quieto 5 segundos."),
    dict(id="antropometria", nombre="Medidas corporales", region="Postura", tipo="antropometria",
         instr="De pie, de frente, talones juntos y brazos abiertos en cruz a la altura de los hombros. Quédate quieto 4 segundos."),
    dict(id="equilibrio", nombre="Equilibrio en una pierna", region="Funcional", tipo="equilibrio",
         instr="De frente, manos en la cintura. Levanta el pie contrario a la pierna de apoyo y mantén el equilibrio hasta 30 segundos."),
    dict(id="sts30", nombre="Sentarse y pararse (30 s)", region="Funcional", tipo="sts30",
         instr="Silla sin brazos de frente al Kinect, brazos cruzados al pecho. Levántate por completo y siéntate tantas veces como puedas en 30 s."),
    dict(id="marcha", nombre="Análisis de marcha", region="Funcional", tipo="marcha",
         instr="Colócate a unos 4 m frente al Kinect. Cuando se indique, camina hacia él a tu paso normal hasta 1.5 m."),
    dict(id="goniometro", nombre="Goniómetro libre", region="Funcional", tipo="goniometro",
         instr="Muestra todos los ángulos en vivo. Pulsa Iniciar y después Terminar para capturar los ángulos de ese momento y guardarlos."),
]
for p in ROM:
    p["tipo"] = "rom"
CATALOGO = {p["id"]: p for p in ROM + OTRAS}
REGIONES = ["Hombro", "Codo", "Cadera", "Rodilla", "Columna", "Postura", "Funcional"]
CON_LADO = {"rom", "equilibrio"}

EQUILIBRIO_NORMA = [(39, 43.5), (49, 40.4), (59, 36.0), (69, 26.9), (79, 15.0), (200, 6.2)]
STS_NORMA = {
    "F": [(64, 12, 17), (69, 11, 16), (74, 10, 15), (79, 10, 15), (84, 9, 14), (89, 8, 13), (200, 4, 11)],
    "M": [(64, 14, 19), (69, 12, 18), (74, 12, 17), (79, 11, 17), (84, 10, 15), (89, 8, 14), (200, 7, 12)],
}


def valor_principal(reg):
    m = reg.get("metricas", {})
    t = reg.get("prueba")
    tipo = CATALOGO.get(t, {}).get("tipo")
    if tipo == "rom":
        return m.get("rom_max"), "°"
    if tipo == "equilibrio":
        return m.get("tiempo"), "s"
    if tipo == "sts30":
        return m.get("repeticiones"), "rep"
    if tipo == "marcha":
        return m.get("velocidad"), "m/s"
    if tipo == "antropometria":
        v = m.get("estatura")
        return (None if v is None else v * 100), "cm"
    if tipo == "postura":
        return m.get("desnivel_hombros"), "cm"
    return None, ""


class Contador:
    def __init__(self, umbral):
        self.umbral = umbral
        self.base = None
        self.en_rep = False
        self.pico = -1e9
        self.t0 = 0.0
        self.reps = []
        self.comps = set()
        self.maximo = None
        self.ult = deque(maxlen=5)

    def paso(self, v, t, comps):
        self.ult.append(v)
        v = float(np.mean(self.ult))
        if self.base is None:
            self.base = v
        if self.maximo is None or v > self.maximo:
            self.maximo = v
        if not self.en_rep:
            if v < self.base + self.umbral * 0.5:
                self.base += (v - self.base) * 0.05
            if v > self.base + self.umbral:
                self.en_rep, self.pico, self.t0 = True, v, t
                self.comps = set(comps)
            return False
        self.pico = max(self.pico, v)
        self.comps.update(comps)
        if v < self.base + self.umbral * 0.45:
            self.en_rep = False
            if t - self.t0 >= 0.4 and self.pico - self.base >= self.umbral * 1.2:
                self.reps.append(dict(pico=round(float(self.pico), 1), base=round(float(self.base), 1),
                                      duracion=round(t - self.t0, 2), comps=sorted(self.comps)))
                return True
        return False


class Base:
    duracion = None

    def __init__(self, spec, lado, perfil):
        self.spec = spec
        self.lado = lado
        self.perfil = perfil or {}
        self.t0 = None
        self.terminado = False
        self.eventos = deque()
        self.avisos = []
        self.estado = "Esperando"
        self.serie = []
        self.t_serie = -1.0
        self.ultima = None

    def edad(self):
        from datos import edad_de
        return edad_de(self.perfil.get("nacimiento"))

    def iniciar(self, t):
        self.t0 = t

    def transcurrido(self, t):
        return 0.0 if self.t0 is None else t - self.t0

    def _guardar_serie(self, t, *vals):
        if t - self.t_serie >= 0.1:
            self.t_serie = t
            self.serie.append([round(t - self.t0, 2)] + [None if v is None else round(float(v), 2) for v in vals])

    def lineas_vivo(self):
        return []

    def dibujo(self, c):
        return []

    def valor_vivo(self):
        return None


class PruebaROM(Base):
    def __init__(self, spec, lado, perfil, reps_objetivo=5):
        super().__init__(spec, lado, perfil)
        self.lados = list(LADOS) if lado == "ambos" else [lado]
        self.cont = {l: Contador(spec["umbral"]) for l in self.lados}
        self.actual = {l: None for l in self.lados}
        self.reps_objetivo = reps_objetivo
        self.comp_cuadros = {}
        self.cuadros = 0

    def actualizar(self, c, t):
        self.avisos = []
        vals = []
        for l in self.lados:
            idx = self.spec["puntos"](l)
            if not c.visible(idx, 0.45):
                self.avisos.append(f"No veo bien el lado {NOMBRE_LADO[l].lower()}")
                self.actual[l] = None
                vals.append(None)
                continue
            v = float(self.spec["metrica"](c, l))
            self.actual[l] = v
            vals.append(v)
            comps = [m for m in (f(c, l) for f in self.spec["comps"]) if m]
            self.cuadros += 1
            for m in comps:
                self.comp_cuadros[m] = self.comp_cuadros.get(m, 0) + 1
            if self.cont[l].en_rep or v > (self.cont[l].base or v) + self.spec["umbral"]:
                self.avisos.extend(comps)
            if self.cont[l].paso(v, t, comps):
                self.eventos.append(("rep", l))
        self.avisos = list(dict.fromkeys(self.avisos))
        self._guardar_serie(t, *vals)
        n = min(len(self.cont[l].reps) for l in self.lados)
        self.estado = f"Repeticiones: " + " · ".join(f"{NOMBRE_LADO[l]} {len(self.cont[l].reps)}" for l in self.lados)
        if n >= self.reps_objetivo:
            self.terminado = True

    def valor_vivo(self):
        return {l: self.actual[l] for l in self.lados}

    def dibujo(self, c):
        out = []
        for l in self.lados:
            v = self.actual[l]
            if v is None or self.spec["vertice"] is None:
                continue
            vi, si = self.spec["vertice"][l], self.spec["segmento"][l]
            ref = self.spec["ref"]
            if ref == "abajo_tronco":
                r = c.P[vi] - c.U * 0.25
            elif ref == "brazo":
                r = c.P[vi] + (c.P[vi] - c.P[HOMBRO[l]])
            elif ref == "muslo":
                r = c.P[vi] + (c.P[vi] - c.P[CADERA[l]])
            else:
                r = c.P[vi] + c.abajo * 0.25
            out.append((c.P[vi], r, c.P[si], v, l))
        return out

    def resultado(self):
        sp = self.spec
        lados = {}
        for l in self.lados:
            reps = self.cont[l].reps
            picos = [r["pico"] for r in reps]
            mx = max(picos) if picos else (round(float(self.cont[l].maximo), 1) if self.cont[l].maximo is not None else None)
            prom = round(float(np.mean(picos)), 1) if picos else None
            cv = round(float(np.std(picos) / max(1e-6, np.mean(picos)) * 100), 1) if len(picos) >= 2 else None
            lados[l] = dict(repeticiones=len(reps), rom_max=mx, rom_prom=prom, variabilidad=cv,
                            pct_normal=None if mx is None else round(mx / sp["normal"] * 100, 1), reps=reps,
                            reps_con_comp=sum(1 for r in reps if r["comps"]))
        hall = []
        met = {}
        for l, d in lados.items():
            if d["rom_max"] is None:
                continue
            txt = f"{NOMBRE_LADO[l]}: {d['rom_max']:.0f}° de {sp['normal']}° normales ({d['pct_normal']:.0f}%)"
            if d["rom_max"] < sp["funcional"]:
                txt += " · por debajo del rango funcional"
            elif d["pct_normal"] < 90:
                txt += " · rango funcional, aún limitado"
            else:
                txt += " · rango completo"
            hall.append(txt)
            if d["reps_con_comp"]:
                hall.append(f"{NOMBRE_LADO[l]}: compensación en {d['reps_con_comp']} de {d['repeticiones']} repeticiones")
        if len(lados) == 2 and all(lados[l]["rom_max"] for l in lados):
            af = self.perfil.get("lado_afectado")
            if af in LADOS:
                lsi = lados[af]["rom_max"] / max(1e-6, lados[OTRO[af]]["rom_max"]) * 100
                met["lsi"] = round(lsi, 1)
                hall.append(f"Índice de simetría (afectado / sano): {lsi:.0f}%" + (" · asimetría relevante" if lsi < 90 else ""))
            else:
                a, b = lados["izq"]["rom_max"], lados["der"]["rom_max"]
                lsi = min(a, b) / max(a, b) * 100
                met["lsi"] = round(lsi, 1)
                hall.append(f"Simetría entre lados: {lsi:.0f}%" + (" · asimetría relevante" if lsi < 90 else ""))
        comps = sorted(self.comp_cuadros.items(), key=lambda kv: -kv[1])
        met["compensaciones"] = {k: round(v / max(1, self.cuadros) * 100, 1) for k, v in comps}
        if len(self.lados) == 1:
            met.update({k: v for k, v in lados[self.lados[0]].items() if k != "reps"})
            met["reps"] = lados[self.lados[0]]["reps"]
        else:
            met["lados"] = lados
            vals = [d["rom_max"] for d in lados.values() if d["rom_max"] is not None]
            met["rom_max"] = min(vals) if vals else None
        return dict(metricas=met, hallazgos=hall, columnas=["t"] + [f"{sp['id']}_{l}" for l in self.lados], serie=self.serie)


class PruebaPostura(Base):
    duracion = 5.0

    def __init__(self, spec, lado, perfil):
        super().__init__(spec, lado, perfil)
        self.muestras = []
        self.quieto_desde = None
        self.prev = None
        self.midiendo = False

    def actualizar(self, c, t):
        self.avisos = []
        if not c.visible((11, 12, 23, 24, 25, 26, 27, 28), 0.5):
            self.avisos.append("Necesito verte de cuerpo completo")
            self.quieto_desde = None
            return
        com = c.centro_masa()
        if self.prev is not None and np.linalg.norm(com - self.prev) > 0.02:
            self.quieto_desde = None
        self.prev = com
        if not self.midiendo:
            self.quieto_desde = self.quieto_desde or t
            self.estado = "Quédate quieto…"
            if t - self.quieto_desde > 1.0:
                self.midiendo = True
                self.t0 = t
            return
        self.muestras.append(dict(desnivel_hombros=c.desnivel_hombros(), desnivel_pelvis=c.desnivel_pelvis(),
                                  tronco_lateral=c.tronco_lateral(), tronco_flexion=c.tronco_flexion(),
                                  cabeza_inclinacion=c.cabeza_inclinacion(), valgo_izq=c.rodilla_valgo("izq"),
                                  valgo_der=c.rodilla_valgo("der"), desplazamiento_lateral=c.desplazamiento_lateral(),
                                  rodilla_flex_izq=c.rodilla_flexion("izq"), rodilla_flex_der=c.rodilla_flexion("der")))
        self._guardar_serie(t, c.desnivel_hombros(), c.desnivel_pelvis(), c.tronco_lateral())
        r = self.transcurrido(t)
        self.estado = f"Midiendo postura… {max(0.0, self.duracion - r):.1f} s"
        if r >= self.duracion:
            self.terminado = True

    def resultado(self):
        if not self.muestras:
            return dict(metricas={}, hallazgos=["Sin datos suficientes"], columnas=[], serie=[])
        m = {k: round(float(np.median([s[k] for s in self.muestras])), 1) for k in self.muestras[0]}
        h = []

        def lado_alto(v, a, b):
            return a if v > 0 else b

        for clave, nombre, leve, marc in (("desnivel_hombros", "Hombros", 1.5, 3.0), ("desnivel_pelvis", "Pelvis", 1.0, 2.0)):
            v = m[clave]
            if abs(v) >= leve:
                h.append(f"{nombre}: el {lado_alto(v, 'izquierdo', 'derecho')} está {abs(v):.1f} cm más alto · "
                         + ("desnivel marcado" if abs(v) >= marc else "desnivel leve"))
            else:
                h.append(f"{nombre}: nivelados ({abs(v):.1f} cm)")
        v = m["tronco_lateral"]
        h.append(f"Tronco: inclinado {abs(v):.1f}° hacia la {'izquierda' if v > 0 else 'derecha'}" if abs(v) >= 3 else f"Tronco: alineado ({abs(v):.1f}°)")
        v = m["cabeza_inclinacion"]
        h.append(f"Cabeza: inclinada {abs(v):.1f}° hacia la {'izquierda' if v > 0 else 'derecha'}" if abs(v) >= 4 else f"Cabeza: alineada ({abs(v):.1f}°)")
        for l in LADOS:
            v = m[f"valgo_{l}"]
            if v >= 8:
                h.append(f"Rodilla {FEM[l]}: tendencia a valgo ({v:.0f}°)")
            elif v <= -8:
                h.append(f"Rodilla {FEM[l]}: tendencia a varo ({abs(v):.0f}°)")
            if m[f"rodilla_flex_{l}"] > 12:
                h.append(f"Rodilla {FEM[l]}: no se extiende por completo ({m[f'rodilla_flex_{l}']:.0f}° de flexión)")
        v = m["desplazamiento_lateral"]
        if abs(v) >= 3:
            h.append(f"Carga desplazada {abs(v):.1f} cm hacia la {'izquierda' if v > 0 else 'derecha'}")
        return dict(metricas=m, hallazgos=h, columnas=["t", "desnivel_hombros", "desnivel_pelvis", "tronco_lateral"], serie=self.serie)


class PruebaAntropometria(Base):
    duracion = 4.0

    def __init__(self, spec, lado, perfil):
        super().__init__(spec, lado, perfil)
        self.muestras = []
        self.midiendo = False
        self.quieto_desde = None
        self.prev = None

    def actualizar(self, c, t):
        self.avisos = []
        if not c.visible((0, 11, 12, 15, 16, 23, 24, 27, 28, 29, 30), 0.5):
            self.avisos.append("Necesito verte completo, de la cabeza a los pies")
            self.quieto_desde = None
            return
        if c.cabeza is None:
            self.avisos.append("No distingo la parte alta de la cabeza: se estimará")
        com = c.centro_masa()
        if self.prev is not None and np.linalg.norm(com - self.prev) > 0.02:
            self.quieto_desde = None
        self.prev = com
        if not self.midiendo:
            self.quieto_desde = self.quieto_desde or t
            self.estado = "Quédate quieto…"
            if t - self.quieto_desde > 1.0:
                self.midiendo, self.t0 = True, t
            return
        d = c.longitudes()
        d["estatura"] = c.estatura()
        d["brazos_en_cruz"] = min(c.hombro_abduccion("izq"), c.hombro_abduccion("der"))
        self.muestras.append(d)
        r = self.transcurrido(t)
        self.estado = f"Midiendo… {max(0.0, self.duracion - r):.1f} s"
        if r >= self.duracion:
            self.terminado = True

    def resultado(self):
        if not self.muestras:
            return dict(metricas={}, hallazgos=["Sin datos suficientes"], columnas=[], serie=[])
        m = {k: float(np.median([s[k] for s in self.muestras])) for k in self.muestras[0]}
        cruz = m.pop("brazos_en_cruz")
        out = {k: round(v, 3) for k, v in m.items()}
        dif = (m["miembro_inf_izq"] - m["miembro_inf_der"]) * 100
        out["discrepancia_mi_cm"] = round(dif, 1)
        out["discrepancia_ms_cm"] = round((m["miembro_sup_izq"] - m["miembro_sup_der"]) * 100, 1)
        h = [f"Estatura estimada: {m['estatura'] * 100:.1f} cm",
             f"Miembro inferior: izq {m['miembro_inf_izq'] * 100:.1f} cm · der {m['miembro_inf_der'] * 100:.1f} cm (cadera a tobillo)"]
        if abs(dif) >= 1.5:
            h.append(f"Posible discrepancia de longitud: el {'izquierdo' if dif > 0 else 'derecho'} es {abs(dif):.1f} cm más largo · confirmar con cinta o radiografía")
        else:
            h.append(f"Sin discrepancia relevante de miembros inferiores ({abs(dif):.1f} cm)")
        if cruz > 70:
            h.append(f"Envergadura: {m['envergadura'] * 100:.0f} cm · relación con estatura {m['envergadura'] / max(0.5, m['estatura']):.2f}")
        else:
            out.pop("envergadura", None)
            h.append("Envergadura no medida: los brazos no estaban en cruz")
        return dict(metricas=out, hallazgos=h, columnas=[], serie=[])


class PruebaEquilibrio(Base):
    duracion = 30.0

    def __init__(self, spec, lado, perfil):
        super().__init__(spec, lado, perfil)
        self.apoyo = lado if lado in LADOS else "izq"
        self.libre = OTRO[self.apoyo]
        self.arriba_desde = None
        self.abajo_desde = None
        self.en_prueba = False
        self.pts = []
        self.tronco = []
        self.tiempo = 0.0
        self.ejes = None
        self.suave = deque(maxlen=6)

    def actualizar(self, c, t):
        self.avisos = []
        if not c.visible((23, 24, 27, 28), 0.4):
            self.avisos.append("Necesito ver tus piernas y pies")
            return
        h = c.altura_pie(self.libre)
        hb = c.altura_pie(self.apoyo)
        if not self.en_prueba:
            self.estado = f"Levanta el pie {NOMBRE_LADO[self.libre].lower()} para empezar"
            if h - hb > 0.06:
                self.arriba_desde = self.arriba_desde or t
                if t - self.arriba_desde > 0.2:
                    self.en_prueba, self.t0 = True, t
                    self.eventos.append(("inicio", None))
            else:
                self.arriba_desde = None
            return
        r = self.transcurrido(t)
        self.tiempo = r
        if self.ejes is None:
            self.ejes = (c.Lg.copy(), c.Fg.copy())
        com = c.centro_masa()
        self.suave.append(com)
        com = np.mean(self.suave, axis=0)
        p = (float(np.dot(com, self.ejes[0])), float(np.dot(com, self.ejes[1])))
        self.pts.append((r, p[0], p[1]))
        self.tronco.append(c.tronco_lateral())
        self._guardar_serie(t, p[0] * 100, p[1] * 100)
        self.estado = f"Equilibrio: {r:.1f} s de {self.duracion:.0f}"
        if h - hb < 0.03:
            self.abajo_desde = self.abajo_desde or t
            if t - self.abajo_desde > 0.25:
                self.tiempo = self.abajo_desde - self.t0
                self.terminado = True
        else:
            self.abajo_desde = None
        if r >= self.duracion:
            self.tiempo = self.duracion
            self.terminado = True

    def valor_vivo(self):
        return {"tiempo": self.tiempo}

    def resultado(self):
        m = dict(tiempo=round(self.tiempo, 1), pierna_apoyo=self.apoyo)
        h = []
        if len(self.pts) > 10:
            a = np.array(self.pts)
            a = a[a[:, 0] <= self.tiempo]
            xy = (a[:, 1:] - a[:, 1:].mean(0)) * 100
            m["oscilacion_ml_cm"] = round(float(np.sqrt((xy[:, 0] ** 2).mean())), 2)
            m["oscilacion_ap_cm"] = round(float(np.sqrt((xy[:, 1] ** 2).mean())), 2)
            ruta = float(np.linalg.norm(np.diff(xy, axis=0), axis=1).sum())
            m["velocidad_oscilacion_cm_s"] = round(ruta / max(0.5, self.tiempo), 2)
            if len(xy) > 3:
                ev = np.linalg.eigvalsh(np.cov(xy.T))
                m["area_elipse95_cm2"] = round(float(math.pi * 5.991 * math.sqrt(max(0.0, ev[0] * ev[1]))), 1)
            m["tronco_max"] = round(float(np.max(np.abs(self.tronco))), 1)
        edad = self.edad()
        h.append(f"Apoyo en pierna {FEM[self.apoyo]}: {self.tiempo:.1f} s")
        if edad is not None:
            norma = next(v for lim, v in EQUILIBRIO_NORMA if edad <= lim)
            esperado = min(self.duracion, norma)
            m["esperado"] = round(esperado, 1)
            if self.tiempo < esperado * 0.8:
                h.append(f"Por debajo de lo esperado para {edad} años (≈{esperado:.0f} s) · déficit de equilibrio")
            else:
                h.append(f"Dentro de lo esperado para {edad} años (≈{esperado:.0f} s)")
        if self.tiempo < 10:
            h.append("Menos de 10 s en apoyo unipodal: asociado a mayor riesgo de caídas")
        if m.get("velocidad_oscilacion_cm_s") is not None:
            h.append(f"Oscilación del centro de masa: {m['velocidad_oscilacion_cm_s']:.1f} cm/s · lateral {m['oscilacion_ml_cm']:.1f} cm, frontal {m['oscilacion_ap_cm']:.1f} cm")
        return dict(metricas=m, hallazgos=h, columnas=["t", "com_ml_cm", "com_ap_cm"], serie=self.serie)


class PruebaSTS(Base):
    duracion = 30.0

    def __init__(self, spec, lado, perfil):
        super().__init__(spec, lado, perfil)
        self.de_pie = None
        self.reps = 0
        self.tiempos = []
        self.cuenta = None

    def iniciar(self, t):
        self.t0 = t

    def actualizar(self, c, t):
        self.avisos = []
        if not c.visible((23, 24, 25, 26, 27, 28), 0.4):
            self.avisos.append("Necesito ver caderas, rodillas y tobillos")
            return
        k = (c.rodilla_flexion("izq") + c.rodilla_flexion("der")) / 2
        hip = (c.cadera_flexion("izq") + c.cadera_flexion("der")) / 2
        r = self.transcurrido(t)
        if self.de_pie is None:
            self.de_pie = k < 35
        if self.de_pie and k > 65:
            self.de_pie = False
        elif not self.de_pie and k < 30 and hip < 35:
            self.de_pie = True
            self.reps += 1
            self.tiempos.append(round(r, 2))
            self.eventos.append(("rep", None))
        self._guardar_serie(t, k)
        self.estado = f"{self.reps} repeticiones · quedan {max(0.0, self.duracion - r):.0f} s"
        if r >= self.duracion:
            self.terminado = True

    def valor_vivo(self):
        return {"reps": self.reps}

    def resultado(self):
        m = dict(repeticiones=self.reps)
        h = [f"{self.reps} repeticiones completas en 30 s"]
        if len(self.tiempos) >= 3:
            d = np.diff(self.tiempos)
            m["ritmo_s"] = round(float(np.mean(d)), 2)
            mitad = len(d) // 2
            if mitad >= 1:
                fat = (np.mean(d[mitad:]) - np.mean(d[:mitad])) / np.mean(d[:mitad]) * 100
                m["fatiga_pct"] = round(float(fat), 1)
                if fat > 20:
                    h.append(f"Las últimas repeticiones fueron {fat:.0f}% más lentas: fatiga")
        edad, sexo = self.edad(), self.perfil.get("sexo")
        if edad is not None and edad >= 60 and sexo in STS_NORMA:
            lim = next(x for x in STS_NORMA[sexo] if edad <= x[0])
            m["normal_min"], m["normal_max"] = lim[1], lim[2]
            if self.reps < lim[1]:
                h.append(f"Por debajo del rango normal para su edad ({lim[1]}–{lim[2]}): debilidad de miembros inferiores y riesgo de caídas")
            elif self.reps > lim[2]:
                h.append(f"Por encima del rango normal para su edad ({lim[1]}–{lim[2]})")
            else:
                h.append(f"Dentro del rango normal para su edad ({lim[1]}–{lim[2]})")
        elif edad is not None and edad < 60:
            h.append("Valores de referencia publicados para 60 años o más; útil para seguir la evolución")
        return dict(metricas=m, hallazgos=h, columnas=["t", "rodilla_flex_prom"], serie=self.serie)


class PruebaMarcha(Base):
    def __init__(self, spec, lado, perfil):
        super().__init__(spec, lado, perfil)
        self.fase = "colocar"
        self.zmax = 0.0
        self.datos = []
        self.ejes = None
        self.quieto = None

    def actualizar(self, c, t):
        self.avisos = []
        if not c.visible((23, 24, 27, 28), 0.4):
            self.avisos.append("No veo tus piernas completas")
            return
        z = float(np.mean(c.P[[23, 24], 2]))
        if self.ejes is None:
            ex = np.array((1.0, 0, 0)) - np.dot((1.0, 0, 0), c.arriba) * c.arriba
            ex /= np.linalg.norm(ex)
            ez = np.cross(c.arriba, ex)
            self.ejes = (ex, ez)
        ex, ez = self.ejes
        hz = lambda p: np.array((float(np.dot(p, ex)), float(np.dot(p, ez))))
        if self.fase == "colocar":
            self.estado = f"Colócate a 4 m (estás a {z:.1f} m)"
            if z > 3.2:
                self.fase = "listo"
                self.zmax = z
            return
        if self.fase == "listo":
            self.zmax = max(self.zmax, z)
            self.estado = "Camina hacia el Kinect a tu paso normal"
            if z < self.zmax - 0.15:
                self.fase = "caminando"
                self.t0 = t
                self.eventos.append(("inicio", None))
            else:
                return
        r = self.transcurrido(t)
        self.datos.append((r, *hz(c.centro_masa()), *hz(c.P[27]), *hz(c.P[28]), c.rodilla_flexion("izq"), c.rodilla_flexion("der"),
                           c.tronco_lateral()))
        self._guardar_serie(t, z)
        self.estado = f"Caminando… {r:.1f} s · a {z:.1f} m"
        if len(self.datos) > 5:
            a = np.array(self.datos[-8:])
            v = np.linalg.norm(a[-1, 1:3] - a[0, 1:3]) / max(1e-3, a[-1, 0] - a[0, 0])
            if v < 0.1 and r > 2:
                self.quieto = self.quieto or t
            else:
                self.quieto = None
        if z < 1.45 or (self.quieto and t - self.quieto > 1.2) or r > 20:
            self.terminado = True

    def resultado(self):
        if len(self.datos) < 15:
            return dict(metricas={}, hallazgos=["Recorrido muy corto para analizar la marcha"], columnas=[], serie=[])
        a = np.array(self.datos)
        t = a[:, 0]
        com = a[:, 1:3]
        d = com[-1] - com[0]
        dist = float(np.linalg.norm(d))
        u = d / max(1e-6, dist)
        n = np.array((-u[1], u[0]))
        s = com @ u
        vel = float(np.polyfit(t, s, 1)[0])
        sl, sr = a[:, 3:5] @ u, a[:, 5:7] @ u
        wl, wr = a[:, 3:5] @ n, a[:, 5:7] @ n
        dd = sl - sr
        k = np.ones(3) / 3
        dd = np.convolve(dd, k, mode="same")
        pasos = []
        ult = -1e9
        for i in range(2, len(dd) - 2):
            seg = dd[i - 2:i + 3]
            if (dd[i] == seg.max() and dd[i] > 0.12) or (dd[i] == seg.min() and dd[i] < -0.12):
                if t[i] - ult > 0.25 and (not pasos or np.sign(pasos[-1][1]) != np.sign(dd[i])):
                    pasos.append((t[i], float(dd[i]), abs(float(wl[i] - wr[i]))))
                    ult = t[i]
        m = dict(velocidad=round(vel, 2), distancia=round(dist, 2), duracion=round(float(t[-1] - t[0]), 2))
        h = [f"Velocidad de marcha: {vel:.2f} m/s en {dist:.1f} m"]
        if len(pasos) >= 3:
            tp = [p[0] for p in pasos]
            cad = (len(pasos) - 1) / max(1e-3, tp[-1] - tp[0]) * 60
            li = [abs(p[1]) for p in pasos if p[1] > 0]
            ld = [abs(p[1]) for p in pasos if p[1] < 0]
            m["cadencia"] = round(float(cad), 1)
            m["pasos"] = len(pasos)
            m["paso_izq"] = round(float(np.mean(li)), 3) if li else None
            m["paso_der"] = round(float(np.mean(ld)), 3) if ld else None
            m["base_sustentacion"] = round(float(np.median([p[2] for p in pasos])), 3)
            h.append(f"Cadencia: {cad:.0f} pasos/min · {len(pasos)} pasos detectados")
            if li and ld:
                asi = abs(np.mean(li) - np.mean(ld)) / np.mean(li + ld) * 100
                m["asimetria_paso_pct"] = round(float(asi), 1)
                h.append(f"Longitud de paso: izq {np.mean(li) * 100:.0f} cm · der {np.mean(ld) * 100:.0f} cm · asimetría {asi:.0f}%"
                         + (" (marcha asimétrica)" if asi > 10 else ""))
            h.append(f"Base de sustentación: {m['base_sustentacion'] * 100:.0f} cm")
        else:
            h.append("No se detectaron suficientes pasos: camina al menos 2.5 m de frente al Kinect")
        m["rodilla_max_izq"] = round(float(np.percentile(a[:, 7], 95)), 1)
        m["rodilla_max_der"] = round(float(np.percentile(a[:, 8], 95)), 1)
        m["tronco_oscilacion"] = round(float(np.std(a[:, 9])), 1)
        h.append(f"Flexión máxima de rodilla al caminar: izq {m['rodilla_max_izq']:.0f}° · der {m['rodilla_max_der']:.0f}°")
        if vel < 0.8:
            h.append("Velocidad menor a 0.8 m/s: marcha limitada, asociada a riesgo de caídas")
        elif vel < 1.0:
            h.append("Velocidad entre 0.8 y 1.0 m/s: marcha funcional con limitación")
        else:
            h.append("Velocidad de marcha normal para la comunidad (> 1.0 m/s)")
        return dict(metricas=m, hallazgos=h, columnas=["t", "distancia"], serie=self.serie)


class PruebaGoniometro(Base):
    def __init__(self, spec, lado, perfil):
        super().__init__(spec, lado, perfil)
        self.ang = {}

    def actualizar(self, c, t):
        self.avisos = []
        self.ang = c.angulos()
        self.estado = "Ángulos en vivo"

    def dibujo(self, c):
        out = []
        for l in LADOS:
            out.append((c.P[HOMBRO[l]], c.P[HOMBRO[l]] - c.U * 0.25, c.P[CODO[l]], c.hombro_elevacion(l), l))
            out.append((c.P[CODO[l]], c.P[CODO[l]] * 2 - c.P[HOMBRO[l]], c.P[MUNECA[l]], c.codo_flexion(l), l))
            out.append((c.P[RODILLA[l]], c.P[RODILLA[l]] * 2 - c.P[CADERA[l]], c.P[TOBILLO[l]], c.rodilla_flexion(l), l))
            out.append((c.P[CADERA[l]], c.P[CADERA[l]] - c.U * 0.25, c.P[RODILLA[l]], c.cadera_flexion(l), l))
        return out

    def resultado(self):
        return dict(metricas={k: round(float(v), 1) for k, v in self.ang.items()},
                    hallazgos=["Captura de ángulos del momento"], columnas=[], serie=[])


CLASES = {"rom": PruebaROM, "postura": PruebaPostura, "antropometria": PruebaAntropometria, "equilibrio": PruebaEquilibrio,
          "sts30": PruebaSTS, "marcha": PruebaMarcha, "goniometro": PruebaGoniometro}


def crear(prueba_id, lado, perfil, reps=5):
    spec = CATALOGO[prueba_id]
    cls = CLASES[spec["tipo"]]
    if cls is PruebaROM:
        return cls(spec, lado, perfil, reps)
    return cls(spec, lado, perfil)


def referencia(prueba_id, reg=None):
    sp = CATALOGO.get(prueba_id, {})
    t = sp.get("tipo")
    if t == "rom":
        return sp["normal"], "normal"
    if t == "equilibrio":
        return (reg or {}).get("metricas", {}).get("esperado", 30.0), "esperado para la edad"
    if t == "sts30":
        v = (reg or {}).get("metricas", {}).get("normal_min")
        return (v, "mínimo normal para la edad") if v else (None, "")
    if t == "marcha":
        return 1.0, "marcha comunitaria"
    return None, ""


def puntos_evolucion(regs):
    out = {}
    for r in regs:
        sp = CATALOGO.get(r.get("prueba"))
        if not sp or sp["tipo"] == "goniometro":
            continue
        m = r.get("metricas", {})
        if sp["tipo"] == "rom":
            if "lados" in m:
                for l, d in m["lados"].items():
                    if d.get("rom_max") is not None:
                        out.setdefault((sp["id"], l), []).append((r["fecha"], float(d["rom_max"]), r))
            elif m.get("rom_max") is not None:
                out.setdefault((sp["id"], r.get("lado")), []).append((r["fecha"], float(m["rom_max"]), r))
        elif sp["tipo"] == "equilibrio":
            if m.get("tiempo") is not None:
                out.setdefault((sp["id"], m.get("pierna_apoyo", r.get("lado"))), []).append((r["fecha"], float(m["tiempo"]), r))
        else:
            v, _ = valor_principal(r)
            if v is not None:
                out.setdefault((sp["id"], None), []).append((r["fecha"], float(v), r))
    return out


def nombre_serie(clave):
    pid, lado = clave
    n = CATALOGO[pid]["nombre"]
    if lado in NOMBRE_LADO and lado != "ambos":
        etiqueta = "apoyo " + NOMBRE_LADO[lado].lower() if CATALOGO[pid]["tipo"] == "equilibrio" else NOMBRE_LADO[lado].lower()
        return f"{n} · {etiqueta}"
    return n


def unidad(pid):
    return {"rom": "°", "equilibrio": "s", "sts30": "rep", "marcha": "m/s", "antropometria": "cm", "postura": "cm"}.get(CATALOGO[pid]["tipo"], "")
