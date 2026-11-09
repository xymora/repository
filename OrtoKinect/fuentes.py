import math
import time

import numpy as np
import cv2

from vision import Cuadro, Registro, C_K, D_K, PW, PH

X = np.array((1.0, 0.0, 0.0))
Y = np.array((0.0, 1.0, 0.0))
Z = np.array((0.0, 0.0, 1.0))


def ir_a_bgr(ir):
    f = ir[::4, ::4].astype(np.float32)
    tope = max(40.0, float(np.percentile(f, 99.5)))
    v = np.clip(ir.astype(np.float32) / tope, 0, 1) ** 0.6
    g = cv2.medianBlur((v * 255).astype(np.uint8), 3)
    return cv2.cvtColor(g, cv2.COLOR_GRAY2BGR)


class FuenteKinect:
    nombre = "Kinect"
    tiene_profundidad = True

    def __init__(self):
        from kinect import Kinect, crudo_a_metros
        self._metros = crudo_a_metros
        self.k = Kinect()
        try:
            self.k.abrir()
            self.k.iniciar()
        except Exception:
            self.k.cerrar()
            raise
        self.reg = Registro()
        self.prof_d = None
        self.prof_c = None
        self.abajo = None
        self.t_acel = 0.0
        self.angulo = 0
        est = self.k.estado_motor()
        if est and est["angulo"] is not None:
            self.angulo = int(round(est["angulo"]))
        self._acel()

    @property
    def ir(self):
        return self.k.video_ir

    def _acel(self):
        est = self.k.estado_motor()
        if est:
            a = np.array(est["acel"], np.float32)
            if 0.6 < np.linalg.norm(a) < 1.4:
                self.abajo = a

    def leer(self):
        t = time.time()
        if t - self.t_acel > 2.0:
            self.t_acel = t
            self._acel()
        p = self.k.profundidad()
        if p is not None:
            self.prof_d = self._metros(p[::2, ::2])
            self.prof_c = None
        if self.k.video_ir:
            ir = self.k.infrarrojo()
            if ir is None:
                return None
            img = ir_a_bgr(ir[:480])
            return Cuadro(img, self.prof_d, D_K, "ir", t, abajo=self.abajo)
        c = self.k.color()
        if c is None:
            return None
        img = cv2.cvtColor(c, cv2.COLOR_BayerGB2BGR)
        if self.prof_d is not None and self.prof_c is None:
            self.prof_c = self.reg.a_color(self.prof_d)
        return Cuadro(img, self.prof_c, C_K, "color", t, abajo=self.abajo)

    def modo_video(self, ir):
        try:
            self.k.modo_video(ir)
        except Exception as e:
            print("No se pudo cambiar el modo de video:", e)

    def led(self, nombre):
        self.k.led(nombre)

    def inclinar(self, d):
        self.angulo = max(-27, min(27, self.angulo + d))
        self.k.inclinar(self.angulo)

    def programa(self, *a):
        pass

    def cerrar(self):
        self.k.cerrar()


class FuenteCamara:
    nombre = "Cámara web (sin profundidad)"
    tiene_profundidad = False
    ir = False

    def __init__(self, indice=0):
        self.cap = cv2.VideoCapture(indice, cv2.CAP_DSHOW)
        if not self.cap.isOpened():
            raise RuntimeError("No hay cámara web disponible")
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    def leer(self):
        ok, img = self.cap.read()
        if not ok:
            return None
        img = cv2.resize(img, (640, 480))
        return Cuadro(img, None, C_K, "color", time.time())

    def modo_video(self, ir):
        pass

    def led(self, n):
        pass

    def inclinar(self, d):
        pass

    def programa(self, *a):
        pass

    def cerrar(self):
        self.cap.release()


def _rot(v, k, ang):
    k = k / (np.linalg.norm(k) + 1e-12)
    c, s = math.cos(ang), math.sin(ang)
    return v * c + np.cross(k, v) * s + k * np.dot(k, v) * (1 - c)


def _n(v):
    return v / (np.linalg.norm(v) + 1e-12)


class ModeloHumano:
    def __init__(self, estatura=1.70):
        h = estatura
        self.h = h
        self.tronco = 0.288 * h
        self.hombro = 0.13 * h
        self.cadera = 0.088 * h
        self.brazo = 0.186 * h
        self.antebrazo = 0.146 * h
        self.mano = 0.08 * h
        self.muslo = 0.245 * h
        self.pierna = 0.246 * h
        self.tobillo = 0.039 * h
        self.pelvis_pie = 0.53 * h

    def _pierna_ik(self, H, A, l1, l2):
        d = A - H
        dist = min(float(np.linalg.norm(d)), l1 + l2 - 1e-4)
        u = _n(d)
        a = math.acos(max(-1.0, min(1.0, (l1 * l1 + dist * dist - l2 * l2) / (2 * l1 * dist))))
        pf = _n(Z - np.dot(Z, u) * u)
        return H + l1 * (u * math.cos(a) + pf * math.sin(a))

    def puntos(self, q):
        g = lambda k, d=0.0: q.get(k, d)
        r = math.radians
        P = np.zeros((33, 3))
        pel = np.array(g("pelvis", (0.0, self.pelvis_pie, 0.0)), float)
        tl, tf = r(g("tl")), r(g("tf"))
        U = _n(np.array((math.sin(tl), math.cos(tl), 0.0)) * math.cos(tf) + Z * math.sin(tf))
        Lt = _n(X - np.dot(X, U) * U)
        F = np.cross(Lt, U)
        mh = pel + U * self.tronco
        P[11] = mh + Lt * self.hombro
        P[12] = mh - Lt * self.hombro
        P[12] += U * g("elev_d") / 100
        P[11] += U * g("elev_i") / 100
        for lado, s, ih, ic, im in (("i", 1, 11, 13, 15), ("d", -1, 12, 14, 16)):
            out = Lt * s
            d = -U * math.cos(r(g("hf_" + lado))) + F * math.sin(r(g("hf_" + lado)))
            d = _rot(d, F * s, r(g("ha_" + lado)))
            k = np.cross(d, F)
            if np.linalg.norm(k) < 1e-6:
                k = -Lt
            E = P[ih] + d * self.brazo
            fa = _rot(d, k, r(g("co_" + lado)))
            W = E + fa * self.antebrazo
            P[ic], P[im] = E, W
            P[im + 2] = W + fa * self.mano * 0.9 + out * 0.02
            P[im + 4] = W + fa * self.mano + F * 0.01
            P[im + 6] = W + fa * self.mano * 0.5 + F * 0.03
        ci = r(g("cabeza"))
        Uh = _n(U * math.cos(ci) + Lt * math.sin(ci))
        Lh = _n(np.cross(Uh, F))
        base = mh + U * 0.035 * self.h
        P[0] = base + Uh * 0.075 * self.h + F * 0.055 * self.h
        for i, lat in ((1, 0.012), (2, 0.018), (3, 0.026), (4, -0.012), (5, -0.018), (6, -0.026)):
            P[i] = base + Uh * 0.088 * self.h + F * 0.045 * self.h + Lh * lat * self.h * 1.0
        P[7] = base + Uh * 0.08 * self.h + Lh * 0.045 * self.h
        P[8] = base + Uh * 0.08 * self.h - Lh * 0.045 * self.h
        P[9] = base + Uh * 0.055 * self.h + F * 0.05 * self.h + Lh * 0.012 * self.h
        P[10] = base + Uh * 0.055 * self.h + F * 0.05 * self.h - Lh * 0.012 * self.h
        self.cima = base + Uh * 0.147 * self.h
        for lado, s, ih, ik, ia in (("i", 1, 23, 25, 27), ("d", -1, 24, 26, 28)):
            H = pel + X * self.cadera * s
            P[ih] = H
            if ("tob_" + lado) in q:
                A = np.array(q["tob_" + lado], float)
                K = np.array(q["rod_" + lado], float) if ("rod_" + lado) in q else self._pierna_ik(H, A, self.muslo, self.pierna)
            else:
                v = r(g("valgo_" + lado))
                d = -Y * math.cos(r(g("cf_" + lado))) + Z * math.sin(r(g("cf_" + lado)))
                d = _rot(d, Z * s, r(g("ca_" + lado)) - v / 2)
                K = H + d * self.muslo
                sh = _rot(d, np.cross(Z, d), r(g("ro_" + lado)))
                sh = _rot(sh, Z * s, v)
                A = K + sh * self.pierna
            P[ik], P[ia] = K, A
            sh = _n(A - K)
            pie = np.cross(sh, X)
            if np.linalg.norm(pie) < 1e-6:
                pie = Z
            pie = _n(pie)
            P[ia + 2] = A + sh * self.tobillo * 0.9 - pie * 0.045
            P[ia + 4] = A + sh * self.tobillo * 0.9 + pie * 0.15 + X * 0.01 * s
        return P


class FuenteSimulada:
    nombre = "Paciente simulado"
    tiene_profundidad = True

    def __init__(self, estatura=1.70):
        self.m = ModeloHumano(estatura)
        self.t0 = time.time()
        self.t_ult = 0.0
        self.ir = False
        self.rng = np.random.default_rng(7)
        self.hc = 0.85
        self.prog = ("reposo", "izq")
        self.t_prog = 0.0
        self.verdad = {}
        self.silla = False
        self._fondos()

    def _fondos(self):
        fx, fy, cx, cy = C_K
        v, u = np.mgrid[0:480, 0:640].astype(np.float32)
        img = np.zeros((480, 640, 3), np.float32)
        pared = np.array((178, 186, 192), np.float32)
        img[:] = pared * (0.85 + 0.15 * (1 - v / 480))[..., None]
        zf = self.hc * fy / np.maximum(v - cy, 1e-3)
        piso = (v > cy + 1) & (zf < 5.2)
        madera = np.array((70, 110, 150), np.float32) * (0.9 + 0.1 * np.sin(u / 9.0))[..., None]
        img[piso] = madera[piso]
        xf = (u - cx) * zf / fx
        tapete = piso & (np.abs(xf) < 0.8) & (zf > 1.2) & (zf < 4.4)
        img[tapete] = (120, 95, 60)
        img[(v < 60) & (np.abs(u - 320) < 150)] *= 1.08
        self.fondo = np.clip(img, 0, 255).astype(np.uint8)
        vh, uh = np.mgrid[0:PH, 0:PW].astype(np.float32)
        zfh = self.hc * fy / np.maximum(vh * 2 - cy, 1e-3)
        prof = np.full((PH, PW), 5.2, np.float32)
        ph = (vh * 2 > cy + 1) & (zfh < 5.2)
        prof[ph] = zfh[ph]
        self.prof_fondo = prof

    def programa(self, prueba, lado):
        self.prog = (prueba, lado)
        self.t_prog = time.time() - self.t0

    def modo_video(self, ir):
        self.ir = bool(ir)

    def led(self, n):
        pass

    def inclinar(self, d):
        pass

    def cerrar(self):
        pass

    def _rom(self, t, pico, n=None):
        ciclo = 4.0
        if t < 1.0:
            return 0.0, 0
        k = int((t - 1.0) // ciclo)
        f = ((t - 1.0) % ciclo) / ciclo
        var = 1.0 + 0.03 * math.sin(k * 2.3)
        if f < 0.35:
            s = 0.5 - 0.5 * math.cos(math.pi * f / 0.35)
        elif f < 0.45:
            s = 1.0
        elif f < 0.85:
            s = 0.5 + 0.5 * math.cos(math.pi * (f - 0.45) / 0.4)
        else:
            s = 0.0
        return pico * var * s, k

    def _pose(self, t):
        prueba, lado = self.prog
        tp = t - self.t_prog
        q = {}
        lados = ("izq", "der") if lado == "ambos" else (lado,)
        fac = {"izq": 0.96, "der": 0.72}
        respira = 0.004 * math.sin(t * 1.6)
        q["pelvis"] = (0.0, self.m.pelvis_pie + respira * 0.2, 0.0)
        z0, x0, yaw = 2.7, 0.0, 0.0
        self.silla = False
        mapa = {"hombro_flex": "hf", "hombro_abd": "ha", "codo_flex": "co", "cadera_flex": "cf", "cadera_abd": "ca", "rodilla_flex": "ro"}
        normal = {"hombro_flex": 180, "hombro_abd": 180, "codo_flex": 150, "cadera_flex": 120, "cadera_abd": 45, "rodilla_flex": 135,
                  "tronco_lat": 35}
        verdad = {}
        if prueba in mapa:
            for l in lados:
                v, _ = self._rom(tp, normal[prueba] * fac[l])
                c = "i" if l == "izq" else "d"
                q[f"{mapa[prueba]}_{c}"] = v
                verdad[l] = v
                if prueba == "cadera_flex":
                    q[f"ro_{c}"] = v * 0.9
                if prueba == "hombro_abd" and l == "der":
                    q["tl"] = q.get("tl", 0) + 11.0 * v / max(1, normal[prueba] * fac[l])
                if prueba == "cadera_abd" and l == "der":
                    q["tl"] = q.get("tl", 0) + 9.0 * v / max(1, normal[prueba] * fac[l])
        elif prueba == "tronco_lat":
            l = lados[0] if len(lados) == 1 else ("izq" if int(tp // 4) % 2 == 0 else "der")
            v, _ = self._rom(tp, 35 * fac[l])
            q["tl"] = v if l == "izq" else -v
            verdad[l] = v
            q["ha_i"], q["ha_d"] = 8 + max(0, q["tl"]) * 0.3, 8 + max(0, -q["tl"]) * 0.3
        elif prueba == "sentadilla":
            k, _ = self._rom(tp, 105)
            q.update(self._sentadilla(k, {"izq": 3.0, "der": 13.0}))
            verdad = {"izq": k, "der": k}
        elif prueba == "postura":
            q["elev_d"] = -2.2
            q["tl"] = -2.5
            q["cabeza"] = -5.0
            q["valgo_d"] = 9.0
            q["ha_i"] = q["ha_d"] = 6
        elif prueba == "antropometria":
            q["ha_i"] = q["ha_d"] = 90
        elif prueba == "equilibrio":
            apoyo = lado if lado in ("izq", "der") else "izq"
            libre = "d" if apoyo == "izq" else "i"
            dur = 30.0 if apoyo == "izq" else 11.0
            if 2.0 < tp < 2.0 + dur:
                q[f"cf_{libre}"] = 30
                q[f"ro_{libre}"] = 75
                s = 1 if apoyo == "izq" else -1
                amp = 0.012 if apoyo == "izq" else 0.025
                q["pelvis"] = (s * 0.03 + amp * math.sin(tp * 1.7) + amp * 0.6 * math.sin(tp * 4.3),
                               self.m.pelvis_pie, 0.008 * math.sin(tp * 1.1))
                q["tl"] = -s * 2.0 + 2.5 * math.sin(tp * 1.3)
            q["ha_i"] = q["ha_d"] = 25
            q["co_i"] = q["co_d"] = 80
        elif prueba == "sts30":
            self.silla = True
            q.update(self._sts(tp))
            z0 = 2.9
        elif prueba == "marcha":
            z0, x0 = self._marcha(tp, q)
        elif prueba == "goniometro":
            q["hf_i"] = 80 + 70 * math.sin(tp * 0.6)
            q["co_d"] = 70 + 60 * math.sin(tp * 0.9)
            q["ha_d"] = 20
            q["cf_d"] = 15 + 15 * math.sin(tp * 0.5)
            q["ro_d"] = 20 + 20 * math.sin(tp * 0.5)
        self.verdad = verdad
        return q, z0, x0, yaw

    def _sentadilla(self, k, valgo):
        q = {}
        m = self.m
        r = math.radians
        a, b = r(k * 0.45), r(k * 0.55)
        hs = []
        for lado, s in (("i", 1), ("d", -1)):
            A = np.array((m.cadera * s, m.tobillo, 0.0))
            v = r(valgo["izq" if s == 1 else "der"] * k / 105)
            K = A + m.pierna * (Y * math.cos(a) + Z * math.sin(a)) - X * s * m.pierna * math.sin(v) * 0.5
            H = K + m.muslo * (Y * math.cos(b) - Z * math.sin(b))
            q["tob_" + lado], q["rod_" + lado] = A.tolist(), K.tolist()
            hs.append(H)
        pel = (hs[0] + hs[1]) / 2
        pel[0] = 0.0
        q["pelvis"] = tuple(pel)
        q["tf"] = k * 0.32
        q["hf_i"] = q["hf_d"] = min(90, k * 0.85)
        return q

    def _sts(self, tp):
        m = self.m
        if tp < 2.0:
            f = 0.0
        else:
            per = 2.75
            ph = ((tp - 2.0) % per) / per
            f = 0.5 - 0.5 * math.cos(2 * math.pi * ph)
        sent = np.array((0.0, 0.47, -0.22))
        pie = np.array((0.0, m.pelvis_pie, 0.02))
        pel = sent + (pie - sent) * f
        q = {"pelvis": tuple(pel), "tf": 35 * math.sin(math.pi * min(1, f * 1.3)) * (1 - f * 0.6) + 6 * (1 - f)}
        for lado, s in (("i", 1), ("d", -1)):
            q["tob_" + lado] = (m.cadera * s, m.tobillo, 0.18)
        q["hf_i"] = q["hf_d"] = 10
        q["ha_i"] = q["ha_d"] = 15
        q["co_i"] = q["co_d"] = 120
        return q

    def _marcha(self, tp, q):
        m = self.m
        vel, paso = 0.95, {"i": 0.60, "d": 0.50}
        z_ini, z_fin = 4.3, 1.2
        if tp < 2.0:
            s = 0.0
        else:
            s = min(z_ini - z_fin, (tp - 2.0) * vel)
        zancada = paso["i"] + paso["d"]
        pel_y = m.pelvis_pie - 0.025
        q["pelvis"] = (0.0, pel_y + 0.012 * math.cos(4 * math.pi * s / zancada), s)
        for lado, s_off, sg in (("i", 0.0, 1), ("d", paso["d"], -1)):
            if s <= 0:
                pos, alto = 0.0, 0.0
            else:
                u = ((s - s_off) % zancada) / zancada
                p0 = s - u * zancada
                if u < 0.62:
                    pos, alto = p0 + 0.25, 0.0
                else:
                    w = (u - 0.62) / 0.38
                    w2 = 0.5 - 0.5 * math.cos(math.pi * w)
                    pos, alto = p0 + 0.25 + zancada * w2, 0.09 * math.sin(math.pi * w)
            q["tob_" + lado] = (m.cadera * sg * 1.05, m.tobillo + alto, pos)
        osc = math.sin(2 * math.pi * s / zancada)
        q["hf_i"], q["hf_d"] = 18 * osc, -18 * osc
        q["ha_i"] = q["ha_d"] = 6
        q["co_i"] = q["co_d"] = 20
        return z_ini, 0.1

    def _a_camara(self, P, z0, x0, yaw):
        c, s = math.cos(yaw), math.sin(yaw)
        bx = P[:, 0] * c + P[:, 2] * s
        bz = -P[:, 0] * s + P[:, 2] * c
        return np.stack((x0 + bx, self.hc - P[:, 1], z0 - bz), 1)

    def leer(self):
        t = time.time() - self.t0
        if t - self.t_ult < 1 / 30:
            return None
        self.t_ult = t
        q, z0, x0, yaw = self._pose(t)
        Pb = self.m.puntos(q)
        P = self._a_camara(Pb, z0, x0, yaw)
        cima = self._a_camara(self.m.cima[None], z0, x0, yaw)[0]
        img, prof = self._render(P, cima, z0, x0, yaw)
        ruido = self.rng.normal(0, 0.005, P.shape)
        vis = np.full(33, 0.98, np.float32)
        return Cuadro(img, prof, C_K, "ir" if self.ir else "color", time.time(), lm=(P + ruido).astype(np.float32), vis=vis,
                      abajo=(0.0, 1.0, 0.0))

    def _proy(self, p, esc=1.0):
        fx, fy, cx, cy = C_K
        z = max(0.2, float(p[2]))
        return (int(round((p[0] * fx / z + cx) * esc)), int(round((p[1] * fy / z + cy) * esc))), z

    def _render(self, P, cima, z0, x0, yaw):
        img = self.fondo.copy()
        prof = self.prof_fondo.copy()
        fx = C_K[0]
        piel, camisa, pantalon, tenis = (140, 170, 215), (150, 120, 40), (90, 60, 45), (230, 230, 235)
        segs = []
        if self.silla:
            silla = [np.array((x, self.hc - y, z0 + 0.22 - zz)) for x, y, zz in
                     ((-0.24, 0.45, -0.2), (0.24, 0.45, -0.2), (0.24, 0.45, 0.25), (-0.24, 0.45, 0.25))]
            respaldo = [np.array((x, self.hc - y, z0 + 0.47)) for x, y in ((-0.24, 0.45), (0.24, 0.45), (0.24, 0.95), (-0.24, 0.95))]
            for poly, col in ((respaldo, (60, 60, 70)), (silla, (75, 75, 88))):
                pts = np.array([self._proy(p)[0] for p in poly], np.int32)
                cv2.fillPoly(img, [pts], col)
                pts2 = np.array([self._proy(p, 0.5)[0] for p in poly], np.int32)
                cv2.fillPoly(prof, [pts2], float(np.mean([p[2] for p in poly])))
        def seg(a, b, ancho, col):
            segs.append(((P[a][2] + P[b][2]) / 2, "l", P[a], P[b], ancho, col))
        for a, b, w, col in ((11, 13, 0.095, camisa), (13, 15, 0.075, piel), (12, 14, 0.095, camisa), (14, 16, 0.075, piel),
                             (23, 25, 0.15, pantalon), (25, 27, 0.11, pantalon), (24, 26, 0.15, pantalon), (26, 28, 0.11, pantalon),
                             (29, 31, 0.08, tenis), (30, 32, 0.08, tenis), (15, 19, 0.06, piel), (16, 20, 0.06, piel)):
            seg(a, b, w, col)
        tz = float(np.mean(P[[11, 12, 23, 24], 2]))
        segs.append((tz, "t", None, None, 0, camisa))
        cab = (P[7] + P[8]) / 2 * 0.6 + cima * 0.4
        segs.append((float(cab[2]), "c", cab, None, 0.105, piel))
        segs.sort(key=lambda s: -s[0])
        for z, tipo, a, b, w, col in segs:
            if tipo == "l":
                (pa, za), (pb, zb) = self._proy(a), self._proy(b)
                g = max(2, int(w * fx / ((za + zb) / 2)))
                cv2.line(img, pa, pb, col, g, cv2.LINE_AA)
                (qa, _), (qb, _) = self._proy(a, 0.5), self._proy(b, 0.5)
                cv2.line(prof, qa, qb, float(z - w / 3), max(1, g // 2))
            elif tipo == "t":
                quad = [P[11] + (P[11] - P[12]) * 0.08, P[12] + (P[12] - P[11]) * 0.08, P[24], P[23]]
                pts = np.array([self._proy(p)[0] for p in quad], np.int32)
                cv2.fillPoly(img, [pts], col, cv2.LINE_AA)
                cuello = [self._proy(p)[0] for p in ((P[11] + P[12]) / 2, cab)]
                cv2.line(img, cuello[0], cuello[1], piel, max(2, int(0.08 * fx / z)), cv2.LINE_AA)
                pts2 = np.array([self._proy(p, 0.5)[0] for p in quad], np.int32)
                cv2.fillPoly(prof, [pts2], float(z - 0.1))
                c2 = [self._proy(p, 0.5)[0] for p in ((P[11] + P[12]) / 2, cab)]
                cv2.line(prof, c2[0], c2[1], float(z - 0.05), max(1, int(0.04 * fx / z)))
            else:
                (pc, zc) = self._proy(a)
                rr = max(3, int(w * fx / zc))
                cv2.circle(img, pc, rr, col, -1, cv2.LINE_AA)
                cv2.ellipse(img, (pc[0], pc[1] - rr // 3), (rr, int(rr * 0.75)), 0, 180, 360, (40, 45, 55), -1, cv2.LINE_AA)
                (qc, _) = self._proy(a, 0.5)
                cv2.circle(prof, qc, max(2, rr // 2), float(zc - 0.06), -1)
        prof += (self.rng.normal(0, 0.004, prof.shape) * prof).astype(np.float32)
        if self.ir:
            g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).astype(np.float32)
            g = g * 0.5 + 60 + self.rng.normal(0, 18, g.shape)
            img = cv2.cvtColor(np.clip(g, 0, 255).astype(np.uint8), cv2.COLOR_GRAY2BGR)
        else:
            img = np.clip(img.astype(np.int16) + self.rng.integers(-5, 6, img.shape, dtype=np.int16), 0, 255).astype(np.uint8)
        return img, prof
