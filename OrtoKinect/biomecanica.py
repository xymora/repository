import math

import numpy as np

NARIZ = 0
OREJA = {"izq": 7, "der": 8}
HOMBRO = {"izq": 11, "der": 12}
CODO = {"izq": 13, "der": 14}
MUNECA = {"izq": 15, "der": 16}
CADERA = {"izq": 23, "der": 24}
RODILLA = {"izq": 25, "der": 26}
TOBILLO = {"izq": 27, "der": 28}
TALON = {"izq": 29, "der": 30}
PIE = {"izq": 31, "der": 32}
LADOS = ("izq", "der")
NOMBRE_LADO = {"izq": "Izquierdo", "der": "Derecho", "ambos": "Ambos"}
FEM = {"izq": "izquierda", "der": "derecha"}
OTRO = {"izq": "der", "der": "izq"}

HUESOS = [
    (11, 12), (11, 23), (12, 24), (23, 24),
    (11, 13), (13, 15), (12, 14), (14, 16),
    (23, 25), (25, 27), (24, 26), (26, 28),
    (27, 29), (29, 31), (27, 31), (28, 30), (30, 32), (28, 32),
    (15, 17), (15, 19), (16, 18), (16, 20), (7, 0), (8, 0),
]
LADO_PUNTO = {i: ("izq" if i % 2 == 1 else "der") for i in range(11, 33)}


def _u(v):
    n = float(np.linalg.norm(v))
    return v / n if n > 1e-9 else v * 0


def _ang3(a, b, c):
    u, v = _u(a - b), _u(c - b)
    return math.degrees(math.acos(max(-1.0, min(1.0, float(np.dot(u, v))))))


def _plano(v, eje_a, eje_b):
    return math.degrees(math.atan2(float(np.dot(v, eje_b)), float(np.dot(v, eje_a))))


class Cuerpo:
    def __init__(self, P, vis, abajo, suelo=None, cabeza=None, t=0.0):
        self.P = np.asarray(P, np.float64)
        self.vis = vis
        self.t = t
        g = _u(np.asarray(abajo, np.float64))
        if suelo is not None:
            g = _u(np.asarray(suelo[0], np.float64))
        self.abajo = g
        self.arriba = -g
        P = self.P
        self.mid_h = (P[11] + P[12]) / 2
        self.mid_c = (P[23] + P[24]) / 2
        lat = (P[11] - P[12]) + (P[23] - P[24])
        lat = lat - np.dot(lat, self.arriba) * self.arriba
        self.Lg = _u(lat)
        self.Fg = _u(np.cross(self.Lg, self.arriba))
        self.U = _u(self.mid_h - self.mid_c)
        lt = P[11] - P[12]
        self.Lt = _u(lt - np.dot(lt, self.U) * self.U)
        self.Ft = _u(np.cross(self.Lt, self.U))
        lp = P[23] - P[24]
        self.Lp = _u(lp - np.dot(lp, self.U) * self.U)
        self.Fp = _u(np.cross(self.Lp, self.U))
        lpr = _u(P[23] - P[24])
        self.Up = _u(self.arriba - np.dot(self.arriba, lpr) * lpr)
        self.Lpv = lpr
        pies = max(float(np.dot(P[i], g)) for i in (29, 30, 31, 32))
        if suelo is not None and pies < float(suelo[1]) + 0.08:
            self.h_suelo = float(suelo[1])
        else:
            self.h_suelo = pies + 0.01
        self.cabeza = None if cabeza is None else np.asarray(cabeza, np.float64)

    def altura(self, p):
        return self.h_suelo - float(np.dot(p, self.abajo))

    def visible(self, idx, umbral=0.5):
        return all(self.vis[i] >= umbral for i in idx)

    def hombro_flexion(self, lado):
        a = self.P[CODO[lado]] - self.P[HOMBRO[lado]]
        v = _plano(a, -self.U, self.Ft)
        return v + 360 if v < -100 else v

    def hombro_abduccion(self, lado):
        out = self.Lt if lado == "izq" else -self.Lt
        a = self.P[CODO[lado]] - self.P[HOMBRO[lado]]
        v = _plano(a, -self.U, out)
        return v + 360 if v < -100 else v

    def hombro_elevacion(self, lado):
        a = self.P[CODO[lado]] - self.P[HOMBRO[lado]]
        return _ang3(self.P[HOMBRO[lado]] + a, self.P[HOMBRO[lado]], self.P[HOMBRO[lado]] - self.U)

    def codo_flexion(self, lado):
        return 180.0 - _ang3(self.P[HOMBRO[lado]], self.P[CODO[lado]], self.P[MUNECA[lado]])

    def cadera_flexion(self, lado):
        t = self.P[RODILLA[lado]] - self.P[CADERA[lado]]
        v = _plano(t, -self.U, self.Fp)
        return v + 360 if v < -100 else v

    def cadera_abduccion(self, lado):
        out = self.Lpv if lado == "izq" else -self.Lpv
        t = self.P[RODILLA[lado]] - self.P[CADERA[lado]]
        return _plano(t, -self.Up, out)

    def rodilla_flexion(self, lado):
        return 180.0 - _ang3(self.P[CADERA[lado]], self.P[RODILLA[lado]], self.P[TOBILLO[lado]])

    def rodilla_valgo(self, lado):
        out = self.Lg if lado == "izq" else -self.Lg
        c, r, t = self.P[CADERA[lado]], self.P[RODILLA[lado]], self.P[TOBILLO[lado]]
        q = lambda p: np.array((float(np.dot(p, out)), float(np.dot(p, self.arriba))))
        c2, r2, t2 = q(c), q(r), q(t)
        a, b = c2 - r2, t2 - r2
        ang = math.degrees(math.acos(max(-1.0, min(1.0, float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-9))))))
        dev = 180.0 - ang
        linea = c2 + (t2 - c2) * ((r2[1] - c2[1]) / (t2[1] - c2[1] + 1e-9))
        medial = r2[0] < linea[0]
        return dev if medial else -dev

    def tronco_lateral(self):
        return _plano(self.U, self.arriba, self.Lg)

    def tronco_flexion(self):
        return _plano(self.U, self.arriba, self.Fg)

    def desnivel_hombros(self):
        return (self.altura(self.P[11]) - self.altura(self.P[12])) * 100

    def desnivel_pelvis(self):
        return (self.altura(self.P[23]) - self.altura(self.P[24])) * 100

    def cabeza_inclinacion(self):
        e = self.P[7] - self.P[8]
        return math.degrees(math.atan2(-float(np.dot(e, self.arriba)), float(np.dot(e, self.Lg))))

    def desplazamiento_lateral(self):
        pies = (self.P[27] + self.P[28]) / 2
        return float(np.dot(self.mid_h - pies, self.Lg)) * 100

    def centro_masa(self):
        return self.mid_c + 0.12 * (self.mid_h - self.mid_c)

    def horizontal(self, p):
        return np.array((float(np.dot(p, self.Lg)), float(np.dot(p, self.Fg))))

    def elevacion_hombro(self, lado):
        return self.altura(self.P[HOMBRO[lado]]) * 100

    def altura_pie(self, lado):
        return min(self.altura(self.P[TOBILLO[lado]]) - 0.07, self.altura(self.P[TALON[lado]]), self.altura(self.P[PIE[lado]]))

    def estatura(self):
        if self.cabeza is not None:
            return self.altura(self.cabeza)
        oj = (self.P[7] + self.P[8]) / 2
        return self.altura(oj) + 0.12

    def longitudes(self):
        P = self.P
        d = lambda a, b: float(np.linalg.norm(P[a] - P[b]))
        r = {}
        for lado in LADOS:
            r[f"brazo_{lado}"] = d(HOMBRO[lado], CODO[lado])
            r[f"antebrazo_{lado}"] = d(CODO[lado], MUNECA[lado])
            r[f"muslo_{lado}"] = d(CADERA[lado], RODILLA[lado])
            r[f"pierna_{lado}"] = d(RODILLA[lado], TOBILLO[lado])
            r[f"miembro_inf_{lado}"] = r[f"muslo_{lado}"] + r[f"pierna_{lado}"]
            r[f"miembro_sup_{lado}"] = r[f"brazo_{lado}"] + r[f"antebrazo_{lado}"]
        r["ancho_hombros"] = d(11, 12)
        r["ancho_cadera"] = d(23, 24)
        r["envergadura"] = d(15, 16) + 0.2
        return r

    def angulos(self):
        r = {}
        for lado in LADOS:
            r[f"hombro_flex_{lado}"] = self.hombro_flexion(lado)
            r[f"hombro_abd_{lado}"] = self.hombro_abduccion(lado)
            r[f"codo_flex_{lado}"] = self.codo_flexion(lado)
            r[f"cadera_flex_{lado}"] = self.cadera_flexion(lado)
            r[f"cadera_abd_{lado}"] = self.cadera_abduccion(lado)
            r[f"rodilla_flex_{lado}"] = self.rodilla_flexion(lado)
            r[f"rodilla_valgo_{lado}"] = self.rodilla_valgo(lado)
        r["tronco_lateral"] = self.tronco_lateral()
        r["tronco_flexion"] = self.tronco_flexion()
        r["cabeza_inclinacion"] = self.cabeza_inclinacion()
        r["desnivel_hombros"] = self.desnivel_hombros()
        r["desnivel_pelvis"] = self.desnivel_pelvis()
        return r
