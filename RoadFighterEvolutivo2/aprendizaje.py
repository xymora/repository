import csv
import json
import os
import threading

import numpy as np

import cerebro as B
import config as C
import maestro as MA
from pista import Pista
from simulacion import Carrera

AQUI = os.path.dirname(os.path.abspath(__file__))
N_IN, N_OUT = C.N_ENTRADAS, C.SALIDAS
COLUMNAS = ["generacion", "nivel", "pista", "mejor", "promedio", "llegaron_pct", "lider_llego",
            "vel_lider_kmh", "choques_lider", "arcoiris_lider", "arcoiris_prom", "rebases_lider",
            "rebases_prom", "beta_maestro", "sigma", "kl", "muestras"]
LOG2PI = np.log(2 * np.pi)


def red_nueva(n_in, n_out, ocultas, rng, escala_salida=1.0):
    capas, a = {}, n_in
    for i, b in enumerate(ocultas + (n_out,)):
        g = escala_salida if i == len(ocultas) else np.sqrt(2.0)
        capas[f"W{i}"] = (rng.standard_normal((a, b)) * g / np.sqrt(a)).astype(np.float64)
        capas[f"b{i}"] = np.zeros(b)
        a = b
    return capas


def red_adelante(p, x):
    n = len(p) // 2
    acts = [x]
    h = x
    for i in range(n):
        z = h @ p[f"W{i}"] + p[f"b{i}"]
        h = np.tanh(z) if i < n - 1 else z
        acts.append(h)
    return h, acts


def red_atras(p, acts, dsal):
    n = len(p) // 2
    g = {}
    d = dsal
    for i in reversed(range(n)):
        g[f"W{i}"] = acts[i].T @ d
        g[f"b{i}"] = d.sum(0)
        if i > 0:
            d = (d @ p[f"W{i}"].T) * (1.0 - acts[i] ** 2)
    return g


def plano(p):
    return np.concatenate([p[k].ravel() for k in sorted(p)])


def desde_plano(v, molde):
    out, i = {}, 0
    for k in sorted(molde):
        n = molde[k].size
        out[k] = np.asarray(v[i:i + n], dtype=np.float64).reshape(molde[k].shape)
        i += n
    return out


class Adam:
    def __init__(self, params, lr):
        self.lr = lr
        self.m = {k: np.zeros_like(v) for k, v in params.items()}
        self.v = {k: np.zeros_like(v) for k, v in params.items()}
        self.t = 0

    def paso(self, params, grads, clip=0.5):
        total = np.sqrt(sum(float((g ** 2).sum()) for g in grads.values()))
        f = min(1.0, clip / (total + 1e-8)) if clip else 1.0
        self.t += 1
        for k, g in grads.items():
            g = g * f
            self.m[k] = 0.9 * self.m[k] + 0.1 * g
            self.v[k] = 0.999 * self.v[k] + 0.001 * g * g
            mh = self.m[k] / (1 - 0.9 ** self.t)
            vh = self.v[k] / (1 - 0.999 ** self.t)
            params[k] -= self.lr * mh / (np.sqrt(vh) + 1e-8)


class Politica:

    def __init__(self, rng):
        oc = tuple(C.PPO_OCULTAS)
        self.actor = red_nueva(N_IN, N_OUT, oc, rng, escala_salida=0.01)
        self.actor["log_std"] = np.full(N_OUT, C.PPO_LOG_STD_INICIAL)
        self.critico = red_nueva(N_IN, 1, oc, rng, escala_salida=1.0)
        self.norm = B.Normalizador()

    def _red_actor(self):
        return {k: v for k, v in self.actor.items() if k != "log_std"}

    def media(self, obs):
        x = self.norm.aplicar(np.atleast_2d(obs))
        return red_adelante(self._red_actor(), x)[0]

    def valor(self, x_norm):
        return red_adelante(self.critico, x_norm)[0][:, 0]

    @property
    def sigma(self):
        return np.exp(self.actor["log_std"])


def actor_plano(pol):
    return plano(pol.actor)


def actor_desde(v, pol_molde):
    return desde_plano(v, pol_molde.actor)


class ControladorPPO:

    def __init__(self, pol, rng, beta, explorar=True):
        self.pol, self.rng, self.beta, self.explorar = pol, rng, beta, explorar
        self.X, self.A, self.LP, self.V, self.VIVO, self.APT, self.EXP = [], [], [], [], [], [], []

    def __call__(self, obs, sim):
        pol = self.pol
        x = pol.norm.aplicar(obs)
        mu = red_adelante(pol._red_actor(), x)[0]
        s = pol.sigma
        a = mu + s * self.rng.standard_normal(mu.shape) if self.explorar else mu
        logp = (-0.5 * ((a - mu) / s) ** 2 - pol.actor["log_std"] - 0.5 * LOG2PI).sum(1)
        self.X.append(x.astype(np.float32))
        self.A.append(a.astype(np.float32))
        self.LP.append(logp)
        self.V.append(pol.valor(x))
        self.VIVO.append(sim.vivo.copy())
        self.APT.append(sim.aptitud().copy())
        if self.beta > 0:
            self.EXP.append(MA.experto(obs).astype(np.float32))
        return np.clip(a, -1.0, 1.0)

    def datos(self, apt_final):
        V = np.array(self.V)
        vivo = np.array(self.VIVO)
        apt = np.vstack([np.array(self.APT), apt_final[None, :]])
        R = np.diff(apt, axis=0) / C.PPO_ESCALA_RECOMPENSA
        T, n = V.shape
        sigue = np.vstack([vivo[1:], np.zeros((1, n), dtype=bool)])
        adv = np.zeros((T, n))
        ultimo = np.zeros(n)
        g, lam = C.PPO_GAMMA, C.PPO_LAMBDA
        for t in reversed(range(T)):
            v_sig = np.where(sigue[t], V[t + 1] if t + 1 < T else 0.0, 0.0)
            delta = R[t] + g * v_sig - V[t]
            ultimo = delta + g * lam * np.where(sigue[t], ultimo, 0.0)
            adv[t] = ultimo
        ret = adv + V
        m = vivo
        d = {"X": np.array(self.X)[m], "A": np.array(self.A)[m], "LP": np.array(self.LP)[m],
             "ADV": adv[m], "RET": ret[m], "V": V[m]}
        if self.EXP:
            d["EXP"] = np.array(self.EXP)[m]
        return d


def actualizar(pol, opt_a, opt_c, d, beta, avisar=None, rng=None):
    rng = rng or np.random.default_rng()
    N = len(d["X"])
    if N > C.PPO_MAX_MUESTRAS:
        sel = rng.choice(N, C.PPO_MAX_MUESTRAS, replace=False)
        d = {k: v[sel] for k, v in d.items()}
        N = C.PPO_MAX_MUESTRAS
    adv = (d["ADV"] - d["ADV"].mean()) / (d["ADV"].std() + 1e-8)
    red_a = pol._red_actor()
    stats = {"kl": 0.0, "recorte": 0.0, "perdida_valor": 0.0, "imitacion": 0.0}
    lote = C.PPO_LOTE
    for ep in range(C.PPO_EPOCAS):
        orden = rng.permutation(N)
        kls = []
        for i in range(0, N, lote):
            idx = orden[i:i + lote]
            x = d["X"][idx].astype(np.float64)
            a = d["A"][idx].astype(np.float64)
            mu, acts = red_adelante(red_a, x)
            ls = pol.actor["log_std"]
            s = np.exp(ls)
            z = (a - mu) / s
            logp = (-0.5 * z ** 2 - ls - 0.5 * LOG2PI).sum(1)
            razon = np.exp(logp - d["LP"][idx])
            A = adv[idx]
            activo = ~(((razon > 1 + C.PPO_RECORTE) & (A > 0)) | ((razon < 1 - C.PPO_RECORTE) & (A < 0)))
            B_ = len(idx)
            dlogp = np.where(activo, -A * razon, 0.0) / B_
            dmu = dlogp[:, None] * z / s
            dls = (dlogp[:, None] * (z ** 2 - 1.0)).sum(0) - C.PPO_ENTROPIA
            if beta > 0 and "EXP" in d:
                err = mu - d["EXP"][idx]
                dmu = dmu + beta * 2.0 * err * np.array(C.PPO_PESO_IMITACION) / B_
                stats["imitacion"] = float((err ** 2).mean())
            ga = red_atras(red_a, acts, dmu)
            ga["log_std"] = dls
            pa = dict(red_a)
            pa["log_std"] = pol.actor["log_std"]
            opt_a.paso(pa, ga)
            pol.actor.update(pa)
            red_a = pol._red_actor()
            pol.actor["log_std"] = np.clip(pol.actor["log_std"], C.PPO_LOG_STD_MIN, C.PPO_LOG_STD_MAX)
            v, acts_c = red_adelante(pol.critico, x)
            err_v = v[:, 0] - d["RET"][idx]
            gc = red_atras(pol.critico, acts_c, (2.0 * err_v / B_)[:, None])
            opt_c.paso(pol.critico, gc)
            kls.append(float(((razon - 1) - np.log(razon)).mean()))
            stats["recorte"] = float((~activo).mean())
            stats["perdida_valor"] = float((err_v ** 2).mean())
            if kls[-1] > 1.5 * C.PPO_KL_MAX:
                break
        stats["kl"] = float(np.mean(kls))
        if avisar:
            avisar(f"PPO: pasada {ep + 1}/{C.PPO_EPOCAS} · KL {stats['kl']:.4f} · "
                   f"error del crítico {stats['perdida_valor']:.2f}"
                   + (f" · imitación {stats['imitacion']:.3f}" if beta > 0 else ""))
        if stats["kl"] > C.PPO_KL_MAX:
            break
    return stats


def preentrenar(pol, avisar=None, semilla=0):
    X, Y = MA.recolectar(semilla=semilla, avisar=avisar)
    pol.norm = B.Normalizador()
    pol.norm.actualizar(X)
    Xn = pol.norm.aplicar(X)
    red_a = pol._red_actor()
    opt = Adam(red_a, 3e-3)
    rng = np.random.default_rng(semilla)
    peso = np.array(C.PPO_PESO_IMITACION)
    epocas = 40
    if avisar:
        avisar(f"La red aprende de {len(X):,} situaciones del maestro...".replace(",", " "))
    for ep in range(epocas):
        orden = rng.permutation(len(Xn))
        tot = 0.0
        for i in range(0, len(orden), 1024):
            idx = orden[i:i + 1024]
            mu, acts = red_adelante(red_a, Xn[idx])
            err = (mu - Y[idx]) * peso
            tot += float((err ** 2).sum())
            opt.paso(red_a, red_atras(red_a, acts, 2 * err / len(idx)), clip=None)
        if avisar and ep % 10 == 9:
            avisar(f"imitación: época {ep + 1}/{epocas} · error {tot / len(Xn):.4f}")
    pol.actor.update(red_a)
    pol.actor["log_std"] = np.full(N_OUT, C.PPO_LOG_STD_TRAS_IMITAR)


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


def cargar_salon(dir_datos=None):
    archivo = os.path.join(carpeta_datos(dir_datos), C.ARCHIVO_SALON)
    try:
        with np.load(archivo) as z:
            return {k: z[k] for k in z.files}
    except (OSError, ValueError, KeyError):
        return None


def cargar_mejor(dir_datos=None):
    s = cargar_salon(dir_datos)
    if s is None or not len(s["generacion"]):
        return None
    i = len(s["generacion"]) - 1
    info = {"generacion": int(s["generacion"][i]), "nivel": int(s["nivel"][i])}
    return s["actor"][i], info, B.Normalizador.desde(s["normalizador"][i])


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
    txt += (f" · arcoíris {r['arcoiris_lider']}/{r['arcoiris_pista']} · rebases {r['rebases_lider']}"
            f" · β maestro {r['beta']:.2f} · σ {r['sigma']:.2f}")
    if r.get("subio"):
        txt += f"  >>> SUBE A {C.NIVELES[r['nivel_nuevo'] - 1][0].upper()}"
    return txt


class PoliticasFijas:

    def __init__(self, actores, normas, molde):
        self.redes = [{k: v for k, v in desde_plano(a, molde).items() if k != "log_std"} for a in actores]
        self.normas = normas

    def __call__(self, obs, sim):
        out = np.zeros((len(obs), N_OUT))
        for i, (r, z) in enumerate(zip(self.redes, self.normas)):
            out[i] = red_adelante(r, z.aplicar(obs[i:i + 1]))[0][0]
        return np.clip(out, -1, 1)


def carrera_campeonas(pista, actores, normas):
    molde = Politica(np.random.default_rng(0)).actor
    ctrl = PoliticasFijas(actores, normas, molde)
    c = Carrera(pista, None, controlador=ctrl, n=len(actores))
    c.politicas = ctrl
    return c


def vista_red(red, norm, obs_fila, n1=24, n2=16):
    W0, W1, W2 = red["W0"], red["W1"], red["W2"]
    s1 = np.sort(np.argsort(-np.abs(W1).sum(1))[:n1])
    s2 = np.sort(np.argsort(-np.abs(W2).sum(1))[:n2])
    x = norm.aplicar(np.atleast_2d(obs_fila))
    _, acts = red_adelante(red, x)
    return {"capas": (N_IN, n1, n2, N_OUT),
            "act": (np.tanh(x[0] / 2), acts[1][0][s1], acts[2][0][s2], np.tanh(acts[3][0])),
            "pesos": (W0[:, s1], W1[np.ix_(s1, s2)], W2[s2, :])}


class Entrenador:

    algoritmo = "ppo"

    def __init__(self, n=C.POBLACION, continuar=True, semilla=None, dir_datos=None, guardar=True,
                 algoritmo=None):
        self.dir = carpeta_datos(dir_datos)
        self.n = int(n)
        self.rng = np.random.default_rng(semilla)
        self.guardar = guardar
        self.generacion, self.nivel, self.racha = 1, 1, 0
        self.historial = []
        self.salon = {"generacion": [], "nivel": [], "aptitud": [], "actor": [], "normalizador": []}
        self.pol = Politica(self.rng)
        self.opt_a = Adam({**self.pol._red_actor(), "log_std": self.pol.actor["log_std"]}, C.PPO_LR_ACTOR)
        self.opt_c = Adam(self.pol.critico, C.PPO_LR_CRITICO)
        self.maestro = False
        self.actualizando = False
        self.msgs = []
        self._hilo = None
        if continuar:
            self._cargar()
        self._preparar()

    @property
    def sigma(self):
        return float(self.pol.sigma.mean())

    @property
    def beta(self):
        b = C.DAGGER_INICIAL * C.DAGGER_DECAE ** (self.generacion - 1)
        return b if b >= 0.01 else 0.0

    @property
    def necesita_maestro(self):
        return bool(getattr(C, "APRENDER_DEL_MAESTRO", True)) and not self.maestro

    def ruta(self, nombre):
        return os.path.join(self.dir, nombre)

    def _cargar(self):
        try:
            with np.load(self.ruta(C.ARCHIVO_MODELO)) as z:
                self.pol.actor = desde_plano(z["actor"], self.pol.actor)
                self.pol.critico = desde_plano(z["critico"], self.pol.critico)
                self.pol.norm = B.Normalizador.desde(z["normalizador"])
                self.generacion, self.nivel, self.racha = int(z["generacion"]), int(z["nivel"]), int(z["racha"])
                self.maestro = bool(z["maestro"])
                self.opt_a = Adam({**self.pol._red_actor(), "log_std": self.pol.actor["log_std"]}, C.PPO_LR_ACTOR)
                self.opt_c = Adam(self.pol.critico, C.PPO_LR_CRITICO)
        except (OSError, KeyError, ValueError):
            pass
        s = cargar_salon(self.dir)
        if s is not None:
            self.salon = {k: list(v) for k, v in s.items()}
        try:
            with open(self.ruta(C.ARCHIVO_HISTORIAL), encoding="utf-8") as f:
                for fila in csv.DictReader(f):
                    self.historial.append({"generacion": int(fila["generacion"]), "nivel": int(fila["nivel"]),
                                           "mejor": float(fila["mejor"]), "promedio": float(fila["promedio"]),
                                           "llegaron": float(fila["llegaron_pct"]),
                                           "arcoiris_lider": int(fila["arcoiris_lider"]),
                                           "arcoiris_prom": float(fila["arcoiris_prom"])})
        except (OSError, KeyError, ValueError):
            pass

    def _guardar_modelo(self):
        _atomico(self.ruta(C.ARCHIVO_MODELO),
                 lambda f: np.savez(f, actor=plano(self.pol.actor), critico=plano(self.pol.critico),
                                    normalizador=self.pol.norm.estado(), generacion=self.generacion,
                                    nivel=self.nivel, racha=self.racha, maestro=self.maestro), binario=True)

    def _guardar(self, r):
        self._guardar_modelo()
        sal = {k: np.array(v) for k, v in self.salon.items()}
        _atomico(self.ruta(C.ARCHIVO_SALON), lambda f: np.savez(f, **sal), binario=True)
        archivo = self.ruta(C.ARCHIVO_HISTORIAL)
        nuevo = not os.path.exists(archivo)
        with open(archivo, "a", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            if nuevo:
                w.writerow(COLUMNAS)
            w.writerow([r["generacion"], r["nivel"], r["pista"], f"{r['mejor']:.2f}", f"{r['promedio']:.2f}",
                        f"{r['llegaron']:.1f}", int(r["lider_llego"]), f"{r['vel_lider']:.1f}",
                        r["choques_lider"], r["arcoiris_lider"], f"{r['arcoiris_prom']:.2f}",
                        r["rebases_lider"], f"{r['rebases_prom']:.1f}", f"{r['beta']:.3f}",
                        f"{r['sigma']:.3f}", f"{r['kl']:.4f}", r["muestras"]])

    def guardar_avance(self):
        if self.guardar:
            self._guardar_modelo()

    def reiniciar(self):
        for nombre in (C.ARCHIVO_MODELO, C.ARCHIVO_HISTORIAL, C.ARCHIVO_SALON):
            try:
                os.remove(self.ruta(nombre))
            except OSError:
                pass
        self.__init__(self.n, continuar=False, dir_datos=self.dir, guardar=self.guardar)

    def preentrenar(self, avisar=None):
        preentrenar(self.pol, avisar=avisar, semilla=int(self.rng.integers(1 << 30)))

    def aplicar_maestro(self, *_):
        self.opt_a = Adam({**self.pol._red_actor(), "log_std": self.pol.actor["log_std"]}, C.PPO_LR_ACTOR)
        self.maestro = True
        self._preparar()
        if self.guardar:
            self._guardar_modelo()

    def _preparar(self):
        self.pista = Pista(self.nivel, int(self.rng.integers(1 << 30)))
        self.ctrl = ControladorPPO(self.pol, self.rng, self.beta)
        self.carrera = Carrera(self.pista, None, controlador=self.ctrl, n=self.n)
        self.carrera.politica = self.pol
        self.pob = np.zeros((self.n, 1))

    def avanzar(self, pasos):
        if self.actualizando:
            if self._hilo is not None and not self._hilo.is_alive():
                return self._terminar_generacion()
            return None
        self.carrera.correr(pasos)
        if self.carrera.terminado:
            self._empezar_aprendizaje()
        return None

    def correr_generacion(self):
        while True:
            r = self.avanzar(10_000)
            if r is not None:
                return r
            if self._hilo is not None:
                self._hilo.join()

    def _empezar_aprendizaje(self):
        c = self.carrera
        apt = c.aptitud()
        lider = int(np.argmax(apt))
        llego = bool(c.llegaron()[lider])
        self._resumen = {
            "generacion": self.generacion, "nivel": self.nivel, "pista": self.pista.nombre,
            "mejor": float(apt[lider]), "promedio": float(apt.mean()),
            "llegaron": 100.0 * float(c.llegaron().mean()), "lider_llego": llego,
            "vel_lider": float(c.velocidad_media_kmh()[lider]), "choques_lider": int(c.choques[lider]),
            "arcoiris_lider": int(c.arcoiris_n[lider]), "arcoiris_prom": float(c.arcoiris_n.mean()),
            "arcoiris_pista": int((self.pista.t_tipo == C.ARCOIRIS).sum()),
            "rebases_lider": int(c.rebases[lider]), "rebases_prom": float(c.rebases.mean()),
            "beta": self.beta, "campeona_anterior": None, "subio": False,
        }
        datos = self.ctrl.datos(apt)
        self._resumen["muestras"] = int(len(datos["X"]))
        muestras_norm = np.concatenate(c.muestras) if c.muestras else None
        self.actualizando = True
        self.msgs = [f"Aprendiendo de {len(datos['X']):,} decisiones de la generación {self.generacion}...".replace(",", " ")]

        def trabajo():
            st = actualizar(self.pol, self.opt_a, self.opt_c, datos, self.beta, avisar=self.msgs.append, rng=self.rng)
            self._stats = st
            if muestras_norm is not None and self.pol.norm.n_obs < 1:
                self.pol.norm.actualizar(muestras_norm[::4])

        self._hilo = threading.Thread(target=trabajo, daemon=True)
        self._hilo.start()

    def _terminar_generacion(self):
        self._hilo = None
        self.actualizando = False
        r = self._resumen
        r["sigma"] = self.sigma
        r["kl"] = float(getattr(self, "_stats", {}).get("kl", 0.0))
        if r["lider_llego"]:
            self.racha += 1
            if self.racha >= C.RACHA_PARA_SUBIR and self.nivel < C.NIVEL_MAX:
                self.nivel += 1
                self.racha = 0
                r["subio"] = True
                r["nivel_nuevo"] = self.nivel
        else:
            self.racha = 0
        for k, v in (("generacion", self.generacion), ("nivel", r["nivel"]), ("aptitud", r["mejor"]),
                     ("actor", plano(self.pol.actor)), ("normalizador", self.pol.norm.estado())):
            self.salon[k].append(v)
        self.historial.append({"generacion": self.generacion, "nivel": r["nivel"], "mejor": r["mejor"],
                               "promedio": r["promedio"], "llegaron": r["llegaron"],
                               "arcoiris_lider": r["arcoiris_lider"], "arcoiris_prom": r["arcoiris_prom"]})
        self.generacion += 1
        if self.guardar:
            self._guardar(r)
        self._preparar()
        return r
