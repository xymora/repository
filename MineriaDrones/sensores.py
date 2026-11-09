import math

import numpy as np

import config as C
import planificador as PL

CAMBIO_BATERIA = 90.0


class Simulacion:
    def __init__(self, sitio, plan, epoca, posicionamiento="RTK", densidad_sim=3.0, semilla=1):
        self.sitio, self.plan, self.epoca = sitio, plan, epoca
        self.rng = np.random.default_rng(semilla)
        self.pos = C.POSICIONAMIENTO[posicionamiento]
        self.posicionamiento = posicionamiento
        self.v = plan["stats"]["velocidad"]
        e = sitio.epocas[epoca]
        self.dtm = e["dtm"]
        self.dsm = e["dtm"] + e["veg"] + e["objetos_h"]
        self.veg = e["veg"]
        self.agua = e["agua"]
        self.lum = e["color"].astype(np.float32).mean(axis=2) / 255.0
        self.t = 0.0
        self.salidas = []
        for r in plan["rutas"]:
            t0 = 0.0
            for k, vu in enumerate(r["vuelos"]):
                activos = [(vu["s_inicio"][id(t)], vu["s_inicio"][id(t)] + t["largo"]) for t in vu["tramos"]
                           if t["tipo"] == "linea"]
                ang = self.rng.uniform(0, 2 * math.pi)
                sesgo = np.array([self.pos["sesgo_h"] * math.cos(ang), self.pos["sesgo_h"] * math.sin(ang),
                                  self.pos["sesgo_v"] * self.rng.choice([-1, 1]) * self.rng.uniform(0.6, 1.0)])
                self.salidas.append({"idx": len(self.salidas), "dron": r["dron"], "k": k, "vuelo": vu, "t0": t0, "t1": t0 + vu["tiempo"],
                                     "activos": np.array(activos) if activos else np.zeros((0, 2)), "sesgo": sesgo,
                                     "fases": self.rng.uniform(0, 2 * math.pi, (3, 3)),
                                     "periodos": self.rng.uniform([15, 50, 150], [30, 90, 300], (3, 3))})
                t0 += vu["tiempo"] + CAMBIO_BATERIA
        self.duracion = max((s["t1"] for s in self.salidas), default=0.0)
        self.lidar = plan["lidar"]
        self.camara = plan["camara"]
        if self.lidar is not None:
            st = plan["stats"]
            self.pps = max(50.0, densidad_sim * self.v * st["espaciado"])
            self.fov = math.radians(self.lidar["fov"])
        self.puntos = []
        self.n_puntos = 0
        self.capturas = []
        self._pend = sorted(plan["capturas"], key=lambda c: (c["dron"], c["vuelo"], c["s"]))
        self._cap_idx = {}
        for c in self._pend:
            self._cap_idx.setdefault((c["dron"], c["vuelo"]), []).append(c)
        self._cap_hechas = {k: 0 for k in self._cap_idx}
        n = sitio.nx // 4
        self.cobertura = np.zeros((n, n), dtype=np.uint16)
        self.gsd_min = np.full((n, n), np.inf, dtype=np.float32)
        self.terminada = self.duracion <= 0

    def _xyz(self, salida, s):
        vu = salida["vuelo"]
        p, ss = vu["puntos"], vu["s"]
        s = np.clip(s, 0, ss[-1])
        return np.column_stack([np.interp(s, ss, p[:, 0]), np.interp(s, ss, p[:, 1]), np.interp(s, ss, p[:, 2])])

    def estado(self):
        res = []
        for d in sorted({s["dron"] for s in self.salidas}):
            mias = [s for s in self.salidas if s["dron"] == d]
            actual = next((s for s in mias if s["t0"] <= self.t <= s["t1"]), None)
            if actual is None:
                previa = [s for s in mias if s["t1"] < self.t]
                if previa and previa[-1] is not mias[-1]:
                    x, y = self.sitio.base
                    res.append({"dron": d, "x": x, "y": y, "z": None, "estado": "Cambio de batería", "bateria": 1.0, "vuelo": len(previa)})
                elif previa:
                    x, y = self.sitio.base
                    res.append({"dron": d, "x": x, "y": y, "z": None, "estado": "Terminado", "bateria": 1.0, "vuelo": len(mias)})
                else:
                    x, y = self.sitio.base
                    res.append({"dron": d, "x": x, "y": y, "z": None, "estado": "En espera", "bateria": 1.0, "vuelo": 0})
                continue
            s = (self.t - actual["t0"]) * self.v
            q = self._xyz(actual, np.array([s, s + 2.0]))
            frac = (self.t - actual["t0"]) / (C.DRON["bateria_min"] * 60)
            activo = any(a <= s <= b for a, b in actual["activos"]) if len(actual["activos"]) else False
            res.append({"dron": d, "x": float(q[0, 0]), "y": float(q[0, 1]), "z": float(q[0, 2]),
                        "rumbo": math.atan2(q[1, 1] - q[0, 1], q[1, 0] - q[0, 0]),
                        "estado": "Escaneando" if activo else "En vuelo", "bateria": max(0.0, 1 - frac),
                        "vuelo": actual["k"] + 1, "de": len(mias)})
        return res

    def avanzar(self, dt):
        if self.terminada:
            return
        t0, t1 = self.t, min(self.duracion, self.t + dt)
        for sal in self.salidas:
            a, b = max(t0, sal["t0"]), min(t1, sal["t1"])
            if b <= a:
                continue
            s0, s1 = (a - sal["t0"]) * self.v, (b - sal["t0"]) * self.v
            if self.lidar is not None:
                self._lidar(sal, s0, s1, b - a)
            if self.camara is not None:
                self._fotos(sal, s0, s1)
        self.t = t1
        if self.t >= self.duracion - 1e-6:
            self.terminada = True

    def terminar(self, avisar=None):
        paso = 30.0
        while not self.terminada:
            self.avanzar(paso)
            if avisar and int(self.t / paso) % 20 == 0:
                avisar(self.t / max(self.duracion, 1))

    def _lidar(self, sal, s0, s1, dt):
        act = sal["activos"]
        if not len(act):
            return
        n = int(self.pps * dt)
        if n <= 0:
            return
        sitio = self.sitio
        for ini in range(0, n, 400000):
            m = min(400000, n - ini)
            s = np.sort(self.rng.uniform(s0, s1, m))
            on = np.zeros(m, bool)
            for a, b in act:
                on |= (s >= a) & (s <= b)
            s = s[on]
            if not len(s):
                continue
            o = self._xyz(sal, s)
            o2 = self._xyz(sal, s + 1.0)
            dirh = o2[:, :2] - o[:, :2]
            nrm = np.linalg.norm(dirh, axis=1, keepdims=True)
            dirh = dirh / np.maximum(nrm, 1e-6)
            trav = np.column_stack([-dirh[:, 1], dirh[:, 0]])
            fase = (s / self.v) * 80.0 + self.rng.uniform(0, 1, len(s)) * 0.05
            tri = 2 * np.abs(2 * (fase - np.floor(fase + 0.5))) - 1
            th = tri * self.fov / 2
            dx, dy, dz = trav[:, 0] * np.sin(th), trav[:, 1] * np.sin(th), -np.cos(th)
            xi, yi = o[:, 0], o[:, 1]
            zg = sitio.muestrear(self.dsm, xi, yi)
            for _ in range(7):
                r = (o[:, 2] - zg) / np.maximum(-dz, 0.05)
                xi = o[:, 0] + dx * r
                yi = o[:, 1] + dy * r
                xi = np.clip(xi, 0, sitio.ancho - 0.01)
                yi = np.clip(yi, 0, sitio.ancho - 0.01)
                zg = sitio.muestrear(self.dsm, xi, yi)
            rango = np.sqrt((xi - o[:, 0]) ** 2 + (yi - o[:, 1]) ** 2 + (zg - o[:, 2]) ** 2)
            i, j = sitio.a_ij(xi, yi)
            ii = np.clip(i.astype(int), 0, sitio.ny - 1)
            jj = np.clip(j.astype(int), 0, sitio.nx - 1)
            agua = self.agua[ii, jj]
            ok = (rango < self.lidar["alcance"]) & ~agua
            veg = self.veg[ii, jj]
            lum = self.lum[ii, jj]
            ruido = self.rng.normal(0, self.lidar["sigma"], len(s))
            xs, ys, zs = xi + dx * ruido, yi + dy * ruido, zg + dz * ruido
            inten = np.clip((lum * 900 + 120) * np.abs(dz) * np.where(veg > 0.5, 0.6, 1.0) + self.rng.normal(0, 30, len(s)), 1, 4000)
            pasa = ok & (veg > 0.5) & (self.rng.uniform(0, 1, len(s)) < 0.42)
            ret = np.ones(len(s), np.uint8)
            nret = np.where(pasa, 2, 1).astype(np.uint8)
            px, py, pz, pin, pr, pn = [xs[ok]], [ys[ok]], [zs[ok]], [inten[ok]], [ret[ok]], [nret[ok]]
            if pasa.any():
                zg2 = sitio.muestrear(self.dtm, xi[pasa], yi[pasa])
                rr = (o[pasa, 2] - zg2) / np.maximum(-dz[pasa], 0.05)
                gx = o[pasa, 0] + dx[pasa] * rr
                gy = o[pasa, 1] + dy[pasa] * rr
                gz = sitio.muestrear(self.dtm, gx, gy) + self.rng.normal(0, self.lidar["sigma"], pasa.sum())
                px.append(gx)
                py.append(gy)
                pz.append(gz)
                pin.append(inten[pasa] * 0.5)
                pr.append(np.full(pasa.sum(), 2, np.uint8))
                pn.append(np.full(pasa.sum(), 2, np.uint8))
            X, Y, Z = np.concatenate(px), np.concatenate(py), np.concatenate(pz)
            k = len(X)
            tp = np.concatenate([s[ok], s[pasa]]) / self.v
            deriva = self._deriva(sal, tp)
            X = X + sal["sesgo"][0] + deriva[0]
            Y = Y + sal["sesgo"][1] + deriva[1]
            Z = Z + sal["sesgo"][2] + deriva[2]
            self.puntos.append({"x": X.astype(np.float32), "y": Y.astype(np.float32), "z": Z.astype(np.float32),
                                "i": np.concatenate(pin).astype(np.uint16), "r": np.concatenate(pr),
                                "n": np.concatenate(pn), "d": np.full(k, sal["idx"], np.uint8)})
            self.n_puntos += k

    def _deriva(self, sal, t):
        t = np.atleast_1d(t)
        res = []
        for eje, sigma in enumerate((self.pos["h"], self.pos["h"], self.pos["v"])):
            onda = sum(np.sin(2 * math.pi * t / sal["periodos"][eje, k] + sal["fases"][eje, k]) for k in range(3))
            res.append(sigma * onda / math.sqrt(1.5))
        return res

    def _fotos(self, sal, s0, s1):
        clave = (sal["dron"], sal["k"])
        lista = self._cap_idx.get(clave, [])
        h = self._cap_hechas.get(clave, 0)
        sitio = self.sitio
        cam = self.camara
        f = 4 * sitio.res
        n = self.cobertura.shape[0]
        while h < len(lista) and lista[h]["s"] <= s1:
            c = lista[h]
            h += 1
            if c["s"] < s0 - 1e-6:
                continue
            zg = float(sitio.muestrear(self.dsm, c["x"], c["y"])[0])
            if c["mira"] is not None:
                mx, my = c["mira"]
                zm = float(sitio.muestrear(self.dsm, mx, my)[0])
                dist = math.sqrt((c["x"] - mx) ** 2 + (c["y"] - my) ** 2 + (c["z"] - zm) ** 2)
                g = PL.gsd(cam, dist)
                cx, cy, ra, rb, rumbo = mx, my, PL.huella(cam, dist)[0] * 0.35, PL.huella(cam, dist)[1] * 0.35, c["rumbo"]
            else:
                agl = max(5.0, c["z"] - zg)
                g = PL.gsd(cam, agl)
                ancho, largo = PL.huella(cam, agl)
                cx, cy, ra, rb, rumbo = c["x"], c["y"], largo / 2, ancho / 2, c["rumbo"]
            r = math.hypot(ra, rb)
            j0, j1 = max(0, int((cx - r) / f)), min(n, int((cx + r) / f) + 1)
            i0, i1 = max(0, int((sitio.ancho - cy - r) / f)), min(n, int((sitio.ancho - cy + r) / f) + 1)
            if j1 > j0 and i1 > i0:
                xs = (np.arange(j0, j1) + 0.5) * f
                ys = sitio.ancho - (np.arange(i0, i1) + 0.5) * f
                X, Y = np.meshgrid(xs, ys)
                cc, ss = math.cos(rumbo), math.sin(rumbo)
                u, v = (X - cx) * cc + (Y - cy) * ss, -(X - cx) * ss + (Y - cy) * cc
                dentro = (np.abs(u) <= ra) & (np.abs(v) <= rb)
                self.cobertura[i0:i1, j0:j1] += dentro.astype(np.uint16)
                bloque = self.gsd_min[i0:i1, j0:j1]
                self.gsd_min[i0:i1, j0:j1] = np.where(dentro, np.minimum(bloque, g), bloque)
            ruido = [float(v[0]) for v in self._deriva(sal, c["s"] / self.v)]
            self.capturas.append({"x": c["x"] + sal["sesgo"][0] + ruido[0], "y": c["y"] + sal["sesgo"][1] + ruido[1],
                                  "z": c["z"] + sal["sesgo"][2], "x_real": c["x"], "y_real": c["y"], "rumbo": rumbo,
                                  "gsd": g, "cx": cx, "cy": cy, "ra": ra, "rb": rb, "tipo": c["tipo"], "dron": sal["dron"],
                                  "sesgo": sal["sesgo"].tolist(), "salida": sal["idx"]})
        self._cap_hechas[clave] = h

    def nube(self):
        if not self.puntos:
            return {k: np.zeros(0, t) for k, t in (("x", np.float32), ("y", np.float32), ("z", np.float32),
                                                    ("i", np.uint16), ("r", np.uint8), ("n", np.uint8), ("d", np.uint8))}
        return {k: np.concatenate([p[k] for p in self.puntos]) for k in self.puntos[0]}

    def resultado(self):
        return {"tipo": self.plan["tipo"], "epoca": self.epoca, "plan": self.plan, "posicionamiento": self.posicionamiento,
                "nube": self.nube() if self.lidar is not None else None, "capturas": self.capturas,
                "cobertura": self.cobertura, "gsd_min": self.gsd_min, "duracion": self.duracion,
                "sesgos": [s["sesgo"].tolist() for s in self.salidas]}
