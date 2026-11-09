import numpy as np

import config as C

DY = 1.0


def _suave(x, k):
    k = max(1, int(k))
    ker = np.ones(k) / k
    return np.convolve(np.pad(x, (k, k), mode="edge"), ker, mode="same")[k:-k]


class Pista:
    def __init__(self, nivel, semilla):
        nivel = max(1, min(int(nivel), C.NIVEL_MAX))
        self.nivel, self.semilla = nivel, int(semilla)
        rng = np.random.default_rng([self.semilla, nivel])
        (self.nombre, largo, hw_min, hw_max, amp, sep, probs, aceite_km) = C.NIVELES[nivel - 1]
        self.largo = float(largo)
        n = int((self.largo + C.LARGO_EXTRA) / DY) + 1
        self.ys = np.arange(n) * DY

        cx = np.zeros(n)
        for _ in range(3):
            lam = rng.uniform(250, 900)
            cx += amp / 3 * np.sin(2 * np.pi * self.ys / lam + rng.uniform(0, 2 * np.pi))
        cx += _suave(np.cumsum(rng.normal(0, 0.35, n)), 120) * (amp / 30)
        cx -= cx[0]
        cx[:150] *= np.linspace(0, 1, 150)
        cx = _suave(cx, 40)
        pend = np.max(np.abs(np.diff(cx))) / DY
        if pend > C.PENDIENTE_MAX[nivel - 1]:
            cx *= C.PENDIENTE_MAX[nivel - 1] / pend
        self.cx = cx

        hw = np.empty(n)
        y = 0
        ancho = hw_max
        while y < n:
            tramo = int(rng.uniform(180, 520))
            hw[y:y + tramo] = ancho
            y += tramo
            ancho = rng.uniform(hw_min, hw_max)
        hw[:250] = hw_max
        self.hw = _suave(hw, 90)

        v_t = C.V_TRANSITO_NIVEL[nivel - 1]
        sep0 = sep * (1.0 - v_t / C.V_ENCUENTRO)
        eventos = []
        y = 60.0
        hasta = self.largo * (1.0 - v_t / 55.0) + 150.0
        while y < hasta:
            y += rng.exponential(sep0) + 4.0
            eventos.append((y, int(rng.choice(4, p=np.array(probs) / sum(probs)))))
        cada = C.ARCOIRIS_CADA[nivel - 1] * (1.0 - v_t / C.V_ENCUENTRO)
        y = cada * 0.5
        while y < hasta:
            eventos.append((y + rng.uniform(-0.15, 0.15) * cada, C.ARCOIRIS))
            y += cada
        eventos.sort()
        K = len(C.CARRILES)
        fin = np.full(K, -1e9)
        ys0, tipos, carriles, dirs = [], [], [], []
        for y, t in eventos:
            largo = C.TIPOS[t][1]
            libres = [c for c in range(K) if y - largo / 2 - fin[c] >= C.HUECO_TRANSITO]
            ocupados_aqui = sum(1 for c in range(K) if y - largo / 2 - fin[c] < C.HUECO_TRANSITO + 2)
            if not libres or ocupados_aqui >= K - 1 and len(libres) <= 1:
                continue
            if t == C.CAMION:
                libres = [c for c in libres if c in (0, K - 1)] or libres
            c = int(rng.choice(libres))
            fin[c] = y + largo / 2
            ys0.append(y)
            tipos.append(t)
            carriles.append(c)
            dirs.append(-1 if c == K - 1 else (1 if c == 0 else int(rng.choice((-1, 1)))))
        self.t_y0 = np.array(ys0, dtype=float)
        self.t_tipo = np.array(tipos, dtype=np.int64)
        self.t_v = np.full(len(ys0), v_t)
        self.t_carril = np.array(carriles, dtype=np.int64)
        self.t_dir = np.array(dirs, dtype=np.int64)
        self.t_f0 = np.array(C.CARRILES)[self.t_carril] if len(ys0) else np.zeros(0)
        self.t_largo = np.array([C.TIPOS[t][1] for t in self.t_tipo])
        self.t_ancho = np.array([C.TIPOS[t][2] for t in self.t_tipo])
        orden = np.argsort(self.t_y0)
        pa, pb = [], []
        for a_i in range(len(orden)):
            a = orden[a_i]
            for b in orden[a_i + 1:]:
                if self.t_y0[b] - self.t_y0[a] > (self.t_largo[a] + self.t_largo[b]) / 2 + C.HUECO_TRANSITO:
                    break
                pa.append(a)
                pb.append(b)
        self.par_a = np.array(pa, dtype=np.int64)
        self.par_b = np.array(pb, dtype=np.int64)

        fijos = []
        for tipo, por_km in (("aceite", aceite_km), ("obstaculo", C.OBSTACULOS_KM[nivel - 1])):
            for _ in range(rng.poisson(por_km * self.largo / 1000.0)):
                for _intento in range(20):
                    y = rng.uniform(260, self.largo - 120)
                    if all(abs(y - f[0]) > C.SEPARACION_FIJOS for f in fijos):
                        fijos.append((y, int(rng.integers(K)), tipo))
                        break
        fijos.sort()
        ac = [(y, c) for y, c, t in fijos if t == "aceite"]
        ob = [(y, c) for y, c, t in fijos if t == "obstaculo"]
        self.a_y = np.array([y for y, _ in ac], dtype=float)
        self.a_f = np.array([C.CARRILES[c] for _, c in ac], dtype=float)
        self.o_y = np.array([y for y, _ in ob], dtype=float)
        self.o_carril = np.array([c for _, c in ob], dtype=np.int64)
        self.o_f = np.array([C.CARRILES[c] for c in self.o_carril], dtype=float)
        self.o_tipo = rng.integers(len(C.OBSTACULOS), size=len(ob))
        self.o_ancho = np.array([C.OBSTACULOS[t][1] for t in self.o_tipo], dtype=float)
        self.o_largo = np.array([C.OBSTACULOS[t][2] for t in self.o_tipo], dtype=float)

    def _interp(self, arr, y):
        return np.interp(y, self.ys, arr)

    def centro(self, y):
        return self._interp(self.cx, y)

    def semiancho(self, y):
        return self._interp(self.hw, y)

    def util(self, y):
        return self._interp(self.hw, y) - C.BORDILLO

    def x_carril(self, f, y):
        return self.centro(y) + f * self.util(y)

    def y_transito(self, t):
        return self.t_y0 + self.t_v * t

    def aceite_xy(self):
        return self.x_carril(self.a_f, self.a_y), self.a_y

    def obstaculos_xy(self):
        return self.x_carril(self.o_f, self.o_y), self.o_y

    @property
    def tiempo_max(self):
        return self.largo / C.V_TIEMPO_MAX
