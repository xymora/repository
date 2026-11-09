import datetime
import json
import math
import os

import numpy as np
from scipy.optimize import linear_sum_assignment
from scipy.spatial import cKDTree

import config as C
import formaciones as F


def minjerk(f):
    f = np.clip(f, 0.0, 1.0)
    return f ** 3 * (10 - 15 * f + 6 * f * f)


def rejilla_pads(n, paso):
    cols = int(math.ceil(math.sqrt(n)))
    filas = int(math.ceil(n / cols))
    xs = (np.arange(cols) - (cols - 1) / 2) * paso
    ys = (np.arange(filas) - (filas - 1) / 2) * paso
    pts = np.array([(x, y, 0.0) for y in ys for x in xs][:n])
    return pts, cols, filas


def _girar_color(col, ang):
    k = np.ones(3) / math.sqrt(3)
    c, s = math.cos(ang), math.sin(ang)
    return np.clip(col * c + np.cross(k, col) * s + np.outer(col @ k, k) * (1 - c), 0, 1)


def _fase_drones(n):
    return np.random.default_rng(17).uniform(0, 2 * math.pi, n)


def normalizar_show(show):
    s = dict(show)
    s.setdefault("nombre", "Espectáculo de drones")
    s["drones"] = int(np.clip(s.get("drones", C.DRONES_DEF), C.DRONES_MIN, C.DRONES_MAX))
    s.setdefault("separacion", C.SEPARACION)
    s.setdefault("altura", C.ALTURA_CENTRO)
    s.setdefault("vel_max", C.VEL_H)
    s.setdefault("escenas", [])
    return s


def clave_escena(esc, n, sep):
    e = {k: v for k, v in esc.items() if k not in ("nombre", "duracion", "movimiento", "efecto")}
    return json.dumps([e, int(n), round(float(sep), 3)], sort_keys=True, ensure_ascii=False)


class Plan:
    def __init__(self):
        self.seg = []
        self.n = 0
        self.pads = None
        self.cols = self.filas = 0
        self.show = {}
        self.stats = {}
        self.fase = None

    @property
    def duracion(self):
        return self.seg[-1]["t1"] if self.seg else 0.0

    def _agregar(self, **kw):
        t0 = self.seg[-1]["t1"] if self.seg else 0.0
        s = {"t0": t0, "t1": t0 + kw.pop("dur"), "mov": "fija", "efecto": "ninguno", "param": {},
             "nombre": "", "bA": 1.0, "bB": 1.0}
        s.update(kw)
        s.setdefault("B", s["A"])
        s.setdefault("cB", s["cA"])
        self.seg.append(s)
        return s

    def _buscar(self, t):
        if t <= 0:
            return 0
        for i, s in enumerate(self.seg):
            if t < s["t1"]:
                return i
        return len(self.seg) - 1

    def _anim(self, s, tau):
        A, c = s["A"], s["centro"]
        dur = s["t1"] - s["t0"]
        f = min(max(tau / dur, 0.0), 1.0)
        p = s["param"]
        mov = s["mov"]
        if mov in ("girar", "vaiven"):
            if mov == "girar" and "angulo" in p:
                ang = p["angulo"] * float(minjerk(f))
            else:
                ang = p.get("amp", 0.0) * math.sin(2 * math.pi * p.get("ciclos", 1) * f) * math.sin(math.pi * f)
            ca, sa = math.cos(ang), math.sin(ang)
            d = A - c
            out = np.empty_like(A)
            out[:, 0] = c[0] + d[:, 0] * ca - d[:, 1] * sa
            out[:, 1] = c[1] + d[:, 0] * sa + d[:, 1] * ca
            out[:, 2] = A[:, 2]
            return out
        if mov == "latido":
            k = 1 + p.get("amp", 0.0) * math.sin(math.pi * f * p.get("ciclos", 1)) ** 2 * math.sin(math.pi * f) ** 0.5
            return c + (A - c) * k
        if mov == "ola":
            v = math.sin(math.pi * f) ** 2
            fase = 2 * math.pi * ((A[:, 0] - c[0]) / p.get("lambda", 30.0) - p.get("ciclos", 1) * f)
            out = A.copy()
            out[:, 1] += p.get("amp", 0.0) * v * np.sin(fase)
            return out
        return A

    def _luz(self, s, tau, pos):
        dur = s["t1"] - s["t0"]
        f = min(max(tau / dur, 0.0), 1.0)
        col = s["cA"]
        b = np.full(self.n, s["bA"])
        ef = s["efecto"]
        w = min(1.0, 4 * f, 4 * (1 - f))
        if ef == "arcoiris":
            col = _girar_color(col, 2 * math.pi * max(1, round(dur / 6)) * f)
        elif ef == "destellos":
            chispa = np.maximum(0, np.sin(tau * 2.3 + self._fase * 7.0)) ** 16
            b = b * (1 + w * (1.4 * chispa - 0.25))
        elif ef == "respirar":
            b = b * (1 - 0.5 * w * (0.5 - 0.5 * math.cos(2 * math.pi * f * max(1, round(dur / 3)))))
        elif ef == "barrido":
            x = pos[:, 0]
            lo, hi = x.min(), x.max()
            u = (x - lo) / max(hi - lo, 1e-6)
            fr = (f * max(1, round(dur / 4)) * 1.0) % 1.0
            banda = np.exp(-((u - (fr * 1.4 - 0.2)) * 5.5) ** 2)
            b = b * (1 + w * (1.3 * banda - 0.35))
        elif ef == "prueba":
            tonos = np.array([[1, 0.15, 0.15], [0.15, 1, 0.25], [0.2, 0.4, 1], [1, 1, 1]])
            k = min(int(f * 4), 3)
            col = np.tile(tonos[k], (self.n, 1))
            onda = 0.5 + 0.5 * np.sin(2 * math.pi * (f * 4 % 1.0) - math.pi / 2)
            b = np.full(self.n, 0.25 + 0.75 * onda)
        return col, b

    def estado(self, t):
        i = self._buscar(t)
        s = self.seg[i]
        tau = min(max(t - s["t0"], 0.0), s["t1"] - s["t0"])
        dur = max(s["t1"] - s["t0"], 1e-9)
        if s["tipo"] == "formacion":
            pos = self._anim(s, tau)
            col, b = self._luz(s, tau, pos)
        elif s["tipo"] in ("mover", "quieto"):
            k = float(minjerk(tau / dur)) if s["tipo"] == "mover" else 0.0
            pos = s["A"] + (s["B"] - s["A"]) * k
            lineal = tau / dur
            if s.get("efecto") == "prueba":
                col, b = self._luz(s, tau, pos)
            else:
                col = s["cA"] + (s["cB"] - s["cA"]) * lineal
                b = np.full(self.n, s["bA"] + (s["bB"] - s["bA"]) * lineal)
        else:
            pos, col, b = s["A"], s["cA"], np.full(self.n, s["bA"])
        return pos, col, b, i

    def posiciones(self, t):
        return self.estado(t)[0]

    def construir(self, show, formaciones, avisar=None):
        show = normalizar_show(show)
        self.show = show
        n = show["drones"]
        self.n = n
        self._fase = _fase_drones(n)
        vh = float(show["vel_max"])
        self.pads, self.cols, self.filas = rejilla_pads(n, C.SEP_PADS)
        H = np.array([0, 0, C.ALTURA_DESPEGUE])
        blanco = np.tile([1.0, 1.0, 1.0], (n, 1))
        cal = np.tile([1.0, 0.86, 0.66], (n, 1))
        self.seg = []
        reposo = 0.06
        self._agregar(tipo="quieto", fase="tierra", dur=C.T_TIERRA, A=self.pads, cA=cal, bA=reposo, bB=reposo,
                      nombre="Preparación")
        self._agregar(tipo="quieto", fase="armado", dur=C.T_ARMADO, A=self.pads, cA=blanco, efecto="prueba",
                      nombre="Prueba de luces")
        alto = self.pads + H
        self._agregar(tipo="mover", fase="despegue", dur=self._duracion(self.pads, alto, vh), A=self.pads,
                      B=alto, cA=blanco, bA=0.35, bB=0.8, nombre="Despegue")
        self._agregar(tipo="quieto", fase="despegue", dur=C.T_PAUSA, A=alto, cA=blanco, bA=0.8, bB=0.8,
                      nombre="Estabilización")
        actual, col_act, b_act = alto, blanco, 0.8
        for k, esc in enumerate(show["escenas"]):
            fo = formaciones[k]
            obj, centro = self._colocar(fo["pos"], show)
            fila, colum = linear_sum_assignment(self._costo(actual, obj))
            destino = obj[colum]
            col_dest = fo["col"][colum]
            nombre = esc.get("nombre") or f"Escena {k + 1}"
            self._agregar(tipo="mover", fase="transicion", dur=self._duracion(actual, destino, vh), A=actual,
                          B=destino, cA=col_act, cB=col_dest, bA=b_act, bB=1.0, nombre=f"Hacia «{nombre}»",
                          escena=k)
            dur = float(np.clip(esc.get("duracion", 10), 2, 120))
            mov = esc.get("movimiento", "fija")
            param = self._parametros(mov, destino, centro, dur, vh, fo)
            self._agregar(tipo="formacion", fase="formacion", dur=dur, A=destino, cA=col_dest, centro=centro,
                          mov=mov, efecto=esc.get("efecto", "ninguno"), param=param, nombre=nombre, escena=k)
            s = self.seg[-1]
            actual = self._anim(s, dur)
            col_act, b_act = col_dest, 1.0
            if avisar:
                avisar(f"Plan: escena {k + 1} de {len(show['escenas'])}")
        fila, colum = linear_sum_assignment(self._costo(actual, alto))
        regreso = alto[colum]
        self._agregar(tipo="mover", fase="regreso", dur=self._duracion(actual, regreso, vh), A=actual, B=regreso,
                      cA=col_act, cB=blanco, bA=b_act, bB=0.7, nombre="Regreso a la base")
        self._agregar(tipo="quieto", fase="regreso", dur=C.T_PAUSA, A=regreso, cA=blanco, bA=0.7, bB=0.7,
                      nombre="Sobre la base")
        suelo = regreso - H
        self._agregar(tipo="mover", fase="aterrizaje", dur=self._duracion(regreso, suelo, vh), A=regreso,
                      B=suelo, cA=blanco, cB=cal, bA=0.7, bB=0.3, nombre="Aterrizaje")
        self._agregar(tipo="quieto", fase="fin", dur=C.T_APAGADO, A=suelo, cA=cal, bA=0.3, bB=reposo,
                      nombre="Motores apagados")
        if avisar:
            avisar("Verificando separaciones…")
        self.stats = self.verificar()
        return self

    def _costo(self, a, b):
        d = a[:, None, :] - b[None, :, :]
        return np.einsum("ijk,ijk->ij", d, d)

    def _colocar(self, pos, show):
        h = np.ptp(pos[:, 2])
        zc = max(float(show["altura"]), C.ALTURA_MIN_FORMACION + h / 2)
        centro = np.array([0.0, 0.0, zc])
        return pos + centro, centro

    def _duracion(self, A, B, vh):
        d = B - A
        hz = np.linalg.norm(d[:, :2], axis=1)
        dz = d[:, 2]
        req = np.maximum.reduce([hz / vh, np.maximum(dz, 0) / C.VEL_SUBIDA, np.maximum(-dz, 0) / C.VEL_BAJADA])
        return float(max(C.T_MIN_TRANSICION, math.ceil(C.FACTOR_MINJERK * req.max() * 2) / 2))

    def _parametros(self, mov, A, c, dur, vh, fo):
        r = float(np.max(np.linalg.norm((A - c)[:, :2], axis=1))) + 1e-6
        if mov == "girar":
            limite = 0.85 * vh * dur / (C.FACTOR_MINJERK * r)
            vueltas = math.floor(limite / (2 * math.pi))
            if vueltas >= 1:
                return {"angulo": 2 * math.pi * min(vueltas, 3)}
            if not fo.get("plano", True) and limite > 0.8:
                return {"angulo": limite}
            mov = "vaiven"
        if mov == "vaiven":
            ciclos = max(1, round(dur / 9))
            amp = min(0.5, 0.8 * vh * dur / (r * (2 * math.pi * ciclos + math.pi)))
            return {"amp": amp, "ciclos": ciclos}
        if mov == "latido":
            rr = float(np.max(np.linalg.norm(A - c, axis=1))) + 1e-6
            ciclos = max(2, round(dur / 1.1))
            amp = min(0.09, 0.7 * vh * dur / (rr * math.pi * ciclos))
            return {"amp": amp, "ciclos": ciclos}
        if mov == "ola":
            ancho = float(np.ptp(A[:, 0])) + 1
            ciclos = max(1, round(dur / 5))
            lam = max(ancho / 1.6, 10.0)
            amp = min(4.0, 0.7 * vh * dur / (2 * math.pi * ciclos))
            return {"amp": amp, "ciclos": ciclos, "lambda": lam}
        return {}

    def verificar(self):
        min_sep = math.inf
        t_min = 0.0
        vmax = 0.0
        alt = 0.0
        recorrido = np.zeros(self.n)
        for s in self.seg:
            dur = s["t1"] - s["t0"]
            if s["tipo"] == "quieto":
                ts = [0.0]
            else:
                ts = np.linspace(0, dur, C.MUESTRAS_VERIFICACION + 1)
            prev = None
            for tau in ts:
                p = self.estado(s["t0"] + tau)[0] if s["tipo"] != "quieto" else s["A"]
                if tau == ts[-1] and s["tipo"] != "quieto":
                    p = self.estado(s["t1"] - 1e-6)[0]
                d = cKDTree(p).query(p, k=2)[0][:, 1].min() if self.n > 1 else math.inf
                if d < min_sep:
                    min_sep, t_min = float(d), s["t0"] + float(tau)
                alt = max(alt, float(p[:, 2].max()))
                if prev is not None:
                    paso = np.linalg.norm(p - prev, axis=1)
                    recorrido += paso
                    vmax = max(vmax, float(paso.max() / (ts[1] - ts[0])))
                prev = p
        escenas = sum(1 for s in self.seg if s["tipo"] == "formacion")
        return {"duracion": self.duracion, "min_sep": min_sep, "t_min_sep": t_min, "vel_max": vmax,
                "alt_max": alt, "recorrido_medio": float(recorrido.mean()), "recorrido_max": float(recorrido.max()),
                "escenas": escenas, "drones": self.n, "seguro": bool(min_sep >= C.SEP_SEGURA),
                "bateria_final": float(bateria(self.duracion, recorrido.max()))}

    def guardar(self, ruta):
        meta = {"n": self.n, "cols": self.cols, "filas": self.filas, "show": self.show, "stats": self.stats,
                "seg": []}
        arrays = {"pads": self.pads.astype(np.float32)}
        for i, s in enumerate(self.seg):
            m = {k: v for k, v in s.items() if k not in ("A", "B", "cA", "cB", "centro")}
            meta["seg"].append(m)
            arrays[f"A{i}"] = s["A"].astype(np.float32)
            arrays[f"cA{i}"] = s["cA"].astype(np.float32)
            if s["B"] is not s["A"]:
                arrays[f"B{i}"] = s["B"].astype(np.float32)
            if s["cB"] is not s["cA"]:
                arrays[f"cB{i}"] = s["cB"].astype(np.float32)
            if "centro" in s:
                arrays[f"c{i}"] = np.asarray(s["centro"], np.float32)
        os.makedirs(os.path.dirname(ruta), exist_ok=True)
        np.savez_compressed(ruta, meta=np.frombuffer(json.dumps(meta, ensure_ascii=False).encode("utf-8"), np.uint8),
                            **arrays)

    @classmethod
    def cargar(cls, ruta):
        z = np.load(ruta)
        meta = json.loads(bytes(z["meta"]).decode("utf-8"))
        p = cls()
        p.n, p.cols, p.filas = meta["n"], meta["cols"], meta["filas"]
        p.show, p.stats = meta["show"], meta["stats"]
        p.pads = z["pads"].astype(float)
        p._fase = _fase_drones(p.n)
        for i, m in enumerate(meta["seg"]):
            s = dict(m)
            s["A"] = z[f"A{i}"].astype(float)
            s["cA"] = z[f"cA{i}"].astype(float)
            s["B"] = z[f"B{i}"].astype(float) if f"B{i}" in z else s["A"]
            s["cB"] = z[f"cB{i}"].astype(float) if f"cB{i}" in z else s["cA"]
            if f"c{i}" in z:
                s["centro"] = z[f"c{i}"].astype(float)
            p.seg.append(s)
        return p

    def exportar(self, carpeta=None, paso=0.25, avisar=None):
        sello = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        carpeta = carpeta or os.path.join(C.EXPORTACIONES, f"show_{sello}")
        os.makedirs(carpeta, exist_ok=True)
        ts = np.arange(0, self.duracion + 1e-9, paso)
        P = np.empty((len(ts), self.n, 3), np.float32)
        L = np.empty((len(ts), self.n, 3), np.uint8)
        for k, t in enumerate(ts):
            pos, col, b, _ = self.estado(t)
            P[k] = pos
            L[k] = np.clip(col * np.clip(b, 0, 1)[:, None] * 255, 0, 255)
        for d in range(self.n):
            datos = np.column_stack([ts, P[:, d, 0], P[:, d, 1], P[:, d, 2], L[:, d, 0], L[:, d, 1], L[:, d, 2]])
            np.savetxt(os.path.join(carpeta, f"dron_{d + 1:04d}.csv"), datos, delimiter=",",
                       fmt=["%.2f", "%.3f", "%.3f", "%.3f", "%d", "%d", "%d"],
                       header="tiempo_s,x_m,y_m,z_m,r,g,b", comments="")
            if avisar and d % 50 == 0:
                avisar(f"Exportando dron {d + 1} de {self.n}…")
        with open(os.path.join(carpeta, "resumen.json"), "w", encoding="utf-8") as f:
            json.dump({"show": self.show, "estadisticas": self.stats, "paso_s": paso,
                       "plataformas": self.pads.tolist(),
                       "fases": [{"fase": s["fase"], "nombre": s["nombre"], "inicio_s": round(s["t0"], 2),
                                  "fin_s": round(s["t1"], 2)} for s in self.seg]},
                      f, ensure_ascii=False, indent=1)
        return carpeta


def bateria(t, recorrido):
    return max(0.0, 100.0 - t * 0.055 - recorrido * 0.012)


def construir_show(show, cache=None, avisar=None):
    show = normalizar_show(show)
    cache = {} if cache is None else cache
    forms = []
    for k, esc in enumerate(show["escenas"]):
        clave = clave_escena(esc, show["drones"], show["separacion"])
        if clave not in cache:
            if avisar:
                avisar(f"Generando formación {k + 1} de {len(show['escenas'])}…")
            cache[clave] = F.generar(esc, show["drones"], float(show["separacion"]))
        forms.append(cache[clave])
    if not forms:
        raise ValueError("Agrega al menos una escena")
    return Plan().construir(show, forms, avisar)
