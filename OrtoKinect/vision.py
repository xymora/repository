import math
import os
import threading
import time

import numpy as np
import cv2

D_K = (594.21, 591.04, 339.31, 242.74)
C_K = (529.22, 525.56, 328.94, 267.48)
T_DC = np.array([0.01999, -0.00074, -0.01092], np.float32)
PW, PH = 320, 240
N_PUNTOS = 33
RADIO_ARTICULACION = 0.035
TORSO = (11, 12, 23, 24)


def _parche_protobuf():
    try:
        from google.protobuf import symbol_database, message_factory
    except Exception:
        return
    if not hasattr(symbol_database.SymbolDatabase, "GetPrototype") and hasattr(message_factory, "GetMessageClass"):
        symbol_database.SymbolDatabase.GetPrototype = lambda self, d: message_factory.GetMessageClass(d)


class Cuadro:
    __slots__ = ("img", "prof", "K", "tipo", "t", "lm", "vis", "abajo")

    def __init__(self, img, prof, K, tipo, t, lm=None, vis=None, abajo=None):
        self.img = img
        self.prof = prof
        self.K = K
        self.tipo = tipo
        self.t = t
        self.lm = lm
        self.vis = vis
        self.abajo = abajo


class Registro:
    def __init__(self):
        v, u = np.mgrid[0:480:2, 0:640:2].astype(np.float32)
        self.rx = (u - D_K[2]) / D_K[0]
        self.ry = (v - D_K[3]) / D_K[1]

    def a_color(self, z):
        ok = z > 0.3
        zz = z[ok]
        X = self.rx[ok] * zz + T_DC[0]
        Y = self.ry[ok] * zz + T_DC[1]
        Z = zz + T_DC[2]
        iu = np.rint((X * C_K[0] / Z + C_K[2]) * 0.5).astype(np.int32)
        iv = np.rint((Y * C_K[1] / Z + C_K[3]) * 0.5).astype(np.int32)
        bien = (iu >= 0) & (iu < PW) & (iv >= 0) & (iv < PH)
        iu, iv, Z = iu[bien], iv[bien], Z[bien]
        orden = np.argsort(-Z)
        out = np.zeros((PH, PW), np.float32)
        out[iv[orden], iu[orden]] = Z[orden]
        hueco = out == 0
        rell = cv2.erode(np.where(hueco, 99.0, out).astype(np.float32), np.ones((3, 3), np.uint8))
        out[hueco & (rell < 99)] = rell[hueco & (rell < 99)]
        return out


class FiltroEuro:
    def __init__(self, min_corte=1.2, beta=6.0, d_corte=1.0):
        self.min_corte = min_corte
        self.beta = beta
        self.d_corte = d_corte
        self.x = None
        self.dx = None
        self.t = None

    @staticmethod
    def _alfa(corte, dt):
        tau = 1.0 / (2 * math.pi * corte)
        return 1.0 / (1.0 + tau / dt)

    def __call__(self, x, t):
        if self.x is None or t - self.t > 0.5:
            self.x, self.dx, self.t = x.copy(), np.zeros_like(x), t
            return x.copy()
        dt = max(1e-3, t - self.t)
        self.t = t
        dx = (x - self.x) / dt
        ad = self._alfa(self.d_corte, dt)
        self.dx = self.dx + ad * (dx - self.dx)
        vel = np.linalg.norm(self.dx, axis=-1, keepdims=True)
        corte = self.min_corte + self.beta * vel
        a = 1.0 / (1.0 + 1.0 / (2 * math.pi * corte * dt))
        self.x = self.x + a * (x - self.x)
        return self.x.copy()

    def reiniciar(self):
        self.x = None


def _ventana(prof, u, v, r=3):
    i, j = int(round(v * PH / 480.0)), int(round(u * PW / 640.0))
    if i < 0 or i >= PH or j < 0 or j >= PW:
        return np.zeros(0, np.float32)
    w = prof[max(0, i - r):i + r + 1, max(0, j - r):j + r + 1]
    return w[w > 0.3]


def fusionar(px, mundo, vis, prof, K):
    fx, fy, cx, cy = K
    P = np.zeros((N_PUNTOS, 3), np.float32)
    medido = np.zeros(N_PUNTOS, bool)
    zt = []
    for i in TORSO:
        if vis[i] > 0.5:
            w = _ventana(prof, px[i, 0], px[i, 1], 2)
            if w.size >= 4:
                zt.append(float(np.median(w)))
    if len(zt) < 2:
        return None, medido
    zc = float(np.median(zt))
    mz = float(np.mean(mundo[list(TORSO), 2]))
    for i in range(N_PUNTOS):
        zesp = zc + float(mundo[i, 2]) - mz
        w = _ventana(prof, px[i, 0], px[i, 1], 3)
        w = w[np.abs(w - zesp) < 0.28] if w.size else w
        if w.size >= 3:
            z = float(np.percentile(w, 40)) + RADIO_ARTICULACION
            medido[i] = True
        else:
            z = zesp + RADIO_ARTICULACION
        u, v = float(px[i, 0]), float(px[i, 1])
        P[i] = ((u - cx) * z / fx, (v - cy) * z / fy, z)
    return P, medido


def cima_cabeza(prof, K, px_nariz, z_cabeza):
    fx, fy, cx, cy = K
    j = int(round(px_nariz[0] * PW / 640.0))
    i = int(round(px_nariz[1] * PH / 480.0))
    if not (0 <= j < PW and 0 <= i < PH):
        return None
    banda = prof[:, max(0, j - 3):j + 4]
    ultimo, fallos = None, 0
    for fila in range(i, -1, -1):
        w = banda[fila]
        if np.any((w > 0.3) & (np.abs(w - z_cabeza) < 0.22)):
            ultimo, fallos = fila, 0
        else:
            fallos += 1
            if fallos > 3:
                break
    if ultimo is None:
        return None
    v = (ultimo + 0.5) * 480.0 / PH
    z = z_cabeza
    return np.array(((px_nariz[0] - cx) * z / fx, (v - cy) * z / fy, z), np.float32)


def plano_suelo(prof, K, abajo):
    fx, fy, cx, cy = K
    v, u = np.mgrid[PH // 3:PH:2, 0:PW:2]
    z = prof[PH // 3:PH:2, 0:PW:2]
    ok = (z > 0.5) & (z < 5.5)
    if ok.sum() < 300:
        return None
    uu = u[ok] * 640.0 / PW
    vv = v[ok] * 480.0 / PH
    zz = z[ok]
    P = np.stack(((uu - cx) * zz / fx, (vv - cy) * zz / fy, zz), 1)
    g = np.asarray(abajo, np.float64)
    g = g / np.linalg.norm(g)
    h = P @ g
    bins = np.arange(0.3, 2.6, 0.02)
    cnt, ed = np.histogram(h, bins)
    minimo = max(120, int(0.015 * len(h)))
    idx = [k for k in range(1, len(cnt) - 1) if cnt[k] >= minimo and cnt[k] >= cnt[k - 1] and cnt[k] >= cnt[k + 1]]
    if not idx:
        return None
    k = max(idx)
    h0 = (ed[k] + ed[k + 1]) / 2
    sel = P[np.abs(h - h0) < 0.04]
    if len(sel) < minimo:
        return None
    c = sel.mean(0)
    _, _, vt = np.linalg.svd(sel - c, full_matrices=False)
    n = vt[2]
    if np.dot(n, g) < 0:
        n = -n
    if np.dot(n, g) < math.cos(math.radians(8)):
        n = g
    sel = P[np.abs(P @ n - float(c @ n)) < 0.03]
    hh = float(np.median(sel @ n)) if len(sel) else float(c @ n)
    if hh < 0.3 or hh > 2.5:
        return None
    return n.astype(np.float32), hh


class Estimador:
    def __init__(self, complejidad=1):
        self.complejidad = complejidad
        self.lock = threading.Lock()
        self.evento = threading.Event()
        self.pendiente = None
        self.resultado = None
        self.vivo = True
        self.listo = False
        self.error = None
        self.ms = 0.0
        self.hilo = threading.Thread(target=self._bucle, daemon=True)
        self.hilo.start()

    def _bucle(self):
        try:
            os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "3")
            _parche_protobuf()
            import mediapipe as mp
            pose = mp.solutions.pose.Pose(model_complexity=self.complejidad, smooth_landmarks=True,
                                          min_detection_confidence=0.5, min_tracking_confidence=0.5)
        except Exception as e:
            self.error = f"No se pudo cargar el estimador de pose: {e}"
            return
        self.listo = True
        while self.vivo:
            if not self.evento.wait(0.2):
                continue
            with self.lock:
                cuadro, self.pendiente = self.pendiente, None
                self.evento.clear()
            if cuadro is None:
                continue
            t0 = time.perf_counter()
            img = cuadro.img
            if cuadro.tipo == "ir":
                g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
                g = cv2.createCLAHE(2.0, (8, 8)).apply(g)
                rgb = cv2.cvtColor(g, cv2.COLOR_GRAY2RGB)
            else:
                rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            try:
                r = pose.process(rgb)
            except Exception as e:
                self.error = str(e)
                continue
            self.ms = self.ms * 0.8 + (time.perf_counter() - t0) * 1000 * 0.2
            if r.pose_landmarks is None:
                with self.lock:
                    self.resultado = (cuadro, None, None, None)
                continue
            h, w = img.shape[:2]
            px = np.array([(l.x * w, l.y * h) for l in r.pose_landmarks.landmark], np.float32)
            vis = np.array([l.visibility for l in r.pose_landmarks.landmark], np.float32)
            mundo = np.array([(l.x, l.y, l.z) for l in r.pose_world_landmarks.landmark], np.float32)
            with self.lock:
                self.resultado = (cuadro, px, vis, mundo)

    def enviar(self, cuadro):
        with self.lock:
            self.pendiente = cuadro
            self.evento.set()

    def tomar(self):
        with self.lock:
            r, self.resultado = self.resultado, None
        return r

    def cerrar(self):
        self.vivo = False


class Rastreador:
    def __init__(self, complejidad=1):
        self.est = None
        self.complejidad = complejidad
        self.filtro = FiltroEuro()
        self.filtro_px = FiltroEuro(min_corte=1.5, beta=0.05)
        self.P = None
        self.px = None
        self.vis = None
        self.medido = None
        self.cabeza = None
        self.t = 0.0
        self.suelo = None
        self.t_suelo = -10.0
        self.abajo = np.array((0, 1, 0), np.float32)
        self.distancia = None
        self.modo3d = "—"
        self.nuevo = False

    def _estimador(self):
        if self.est is None:
            self.est = Estimador(self.complejidad)
        return self.est

    def procesar(self, cuadro):
        if cuadro.abajo is not None:
            a = np.asarray(cuadro.abajo, np.float32)
            n = np.linalg.norm(a)
            if n > 0.5:
                a = a / n
                if float(np.dot(a, self.abajo)) < math.cos(math.radians(2.5)):
                    self.suelo = None
                    self.abajo = a
                else:
                    self.abajo = self.abajo * 0.9 + a * 0.1
                    self.abajo /= np.linalg.norm(self.abajo)
        if cuadro.prof is not None and cuadro.t - self.t_suelo > 1.0:
            self.t_suelo = cuadro.t
            s = plano_suelo(cuadro.prof, cuadro.K, self.abajo)
            if s is not None:
                if self.suelo is None or s[1] > self.suelo[1] + 0.04:
                    self.suelo = s
                elif s[1] > self.suelo[1] - 0.04:
                    n = self.suelo[0] * 0.8 + s[0] * 0.2
                    self.suelo = (n / np.linalg.norm(n), self.suelo[1] * 0.8 + s[1] * 0.2)
        if cuadro.lm is not None:
            self._aceptar(cuadro, cuadro.lm, cuadro.vis, None, True)
            return
        est = self._estimador()
        est.enviar(cuadro)
        r = est.tomar()
        if r is None:
            return
        c, px, vis, mundo = r
        if px is None:
            if c.t - self.t > 0.6:
                self.P = None
                self.px = None
                self.filtro.reiniciar()
                self.filtro_px.reiniciar()
            return
        px = self.filtro_px(px, c.t)
        P, medido = (None, None)
        if c.prof is not None:
            P, medido = fusionar(px, mundo, vis, c.prof, c.K)
        if P is None:
            P = mundo + np.array((0, 0, 2.5), np.float32)
            medido = np.zeros(N_PUNTOS, bool)
            self.modo3d = "modelo (sin profundidad)"
        else:
            self.modo3d = "profundidad Kinect"
        self._aceptar(c, P, vis, px, False, medido)

    def _aceptar(self, c, P, vis, px, directo, medido=None):
        fx, fy, cx, cy = c.K
        P = np.asarray(P, np.float32)
        if px is None:
            z = np.maximum(P[:, 2], 0.2)
            px = np.stack((P[:, 0] * fx / z + cx, P[:, 1] * fy / z + cy), 1)
        self.P = P if directo else self.filtro(P, c.t)
        self.px = px
        self.vis = np.asarray(vis, np.float32)
        self.medido = np.ones(N_PUNTOS, bool) if medido is None else medido
        if directo:
            self.modo3d = "simulado"
        self.t = c.t
        self.cabeza = None
        if c.prof is not None:
            zc = float(self.P[0, 2]) - RADIO_ARTICULACION
            self.cabeza = cima_cabeza(c.prof, c.K, px[0], zc)
        self.distancia = float(np.mean(self.P[[23, 24], 2]))
        self.nuevo = True

    def olvidar_suelo(self):
        self.suelo = None

    def cerrar(self):
        if self.est is not None:
            self.est.cerrar()
