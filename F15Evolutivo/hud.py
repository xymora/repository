import math

import numpy as np
import pygame

import config as C
import modelos as MD
from cabina import AMBAR, FT, KT, ROJO, _fuente, _texto

VERDE = (70, 255, 120)
COMBINADOR = [(5.98, 1.11, -0.18), (5.98, 1.11, 0.18), (5.98, 1.52, 0.18), (5.98, 1.52, -0.18)]


class Proyector:
    def __init__(self, cam, adelante, arriba, fov, ancho, alto):
        self.cam = np.asarray(cam, float)
        f = adelante / np.linalg.norm(adelante)
        r = np.cross(f, arriba)
        r /= np.linalg.norm(r)
        self.f, self.r, self.u = f, r, np.cross(r, f)
        self.t = math.tan(math.radians(fov) / 2)
        self.W, self.H = ancho, alto
        self.asp = ancho / alto

    def dir(self, v):
        z = float(np.dot(v, self.f))
        if z <= 1e-3:
            return None
        x = float(np.dot(v, self.r)) / z / (self.t * self.asp)
        y = float(np.dot(v, self.u)) / z / self.t
        return ((x + 1) / 2 * self.W, (1 - y) / 2 * self.H)

    def punto(self, p):
        return self.dir(np.asarray(p, float) - self.cam)


class HUD:
    def __init__(self):
        self.f = _fuente(16, True)
        self.f_peq = _fuente(13, True)
        self.f_gr = _fuente(20, True)

    def _linea(self, s, a, b, ancho=2, color=VERDE):
        if a is None or b is None:
            return
        pygame.draw.line(s, color + (60,), a, b, ancho + 3)
        pygame.draw.line(s, color + (235,), a, b, ancho)

    def _txt(self, s, txt, pos, centro=True, f=None, color=VERDE, der=False):
        f = f or self.f
        _texto(s, f, txt, color + (80,), (pos[0] + 1, pos[1] + 1), centro, der)
        _texto(s, f, txt, color, pos, centro, der)

    def dibujar(self, s, pr, e):
        R = e["R"]
        pos = e["pos"]
        ojo = pos + R @ MD.OJO
        esq = [pr.punto(pos + R @ np.array(c)) for c in COMBINADOR]
        if any(p is None for p in esq):
            return
        xs, ys = [p[0] for p in esq], [p[1] for p in esq]
        clip = pygame.Rect(min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys))
        if clip.w < 40 or clip.h < 40:
            return
        s.set_clip(clip)
        fwd = R[:, 0]
        h = np.array([fwd[0], 0.0, fwd[2]])
        if np.linalg.norm(h) < 1e-4:
            h = np.array([R[0, 1], 0, R[2, 1]]) * -1
        h /= np.linalg.norm(h)
        der_h = np.cross(h, np.array([0, 1.0, 0]))
        arriba = np.array([0, 1.0, 0])
        cab = e["cabeceo"]
        for grados in range(-90, 91, 5):
            a = math.radians(grados)
            if abs(a - cab) > math.radians(28):
                continue
            centro = math.cos(a) * h + math.sin(a) * arriba
            ancho = math.radians(4.5 if grados else 14)
            hueco = math.radians(1.6)
            for lado in (-1, 1):
                p0 = pr.dir(centro + der_h * math.tan(hueco) * lado)
                p1 = pr.dir(centro + der_h * math.tan(ancho) * lado)
                if p0 is None or p1 is None:
                    continue
                if grados < 0:
                    for k in range(3):
                        q0 = (p0[0] + (p1[0] - p0[0]) * k / 3, p0[1] + (p1[1] - p0[1]) * k / 3)
                        q1 = (p0[0] + (p1[0] - p0[0]) * (k + 0.6) / 3, p0[1] + (p1[1] - p0[1]) * (k + 0.6) / 3)
                        self._linea(s, q0, q1)
                else:
                    self._linea(s, p0, p1)
                if grados:
                    pt = pr.dir(centro + der_h * math.tan(ancho) * lado - arriba * 0.012 * np.sign(grados))
                    if pt:
                        self._linea(s, p1, pt)
                    pl = pr.dir(centro + der_h * math.tan(ancho + math.radians(1.6)) * lado)
                    if pl:
                        self._txt(s, str(abs(grados)), pl, f=self.f_peq)
        mira = pr.dir(fwd)
        if mira:
            x, y = mira
            for dx, dy in ((-14, 0), (14, 0), (0, -10)):
                self._linea(s, (x + dx * 0.4, y + dy * 0.4), (x + dx, y + dy))
        v = e["vel_vec"]
        if np.linalg.norm(v) > 15:
            fpm = pr.dir(v / np.linalg.norm(v))
            if fpm:
                x, y = int(fpm[0]), int(fpm[1])
                pygame.draw.circle(s, VERDE + (235,), (x, y), 9, 2)
                self._linea(s, (x - 22, y), (x - 9, y))
                self._linea(s, (x + 9, y), (x + 22, y))
                self._linea(s, (x, y - 9), (x, y - 17))
        cx = clip.centerx
        top = clip.top + 22
        rumbo = math.degrees(e["rumbo"])
        for k in range(-30, 31, 5):
            g = (round(rumbo / 5) * 5 + k) % 360
            dx = ((g - rumbo + 540) % 360 - 180) * 7
            if abs(dx) > clip.w * 0.36:
                continue
            alto = 9 if g % 10 == 0 else 5
            self._linea(s, (cx + dx, top), (cx + dx, top + alto), 1)
            if g % 10 == 0:
                self._txt(s, f"{g // 10:02d}", (cx + dx, top - 10), f=self.f_peq)
        pygame.draw.polygon(s, VERDE + (230,), [(cx, top + 12), (cx - 6, top + 20), (cx + 6, top + 20)], 2)
        if e.get("rumbo_obj") is not None:
            dxo = ((math.degrees(e["rumbo_obj"]) - rumbo + 540) % 360 - 180) * 7
            dxo = max(-clip.w * 0.36, min(clip.w * 0.36, dxo))
            self._linea(s, (cx + dxo, top + 12), (cx + dxo, top + 22), 3)
        midy = clip.centery + 10
        kt = e["vel"] * KT
        izq = clip.left + clip.w * 0.16
        der = clip.right - clip.w * 0.16
        pygame.draw.rect(s, VERDE + (230,), (izq - 40, midy - 13, 74, 26), 2)
        self._txt(s, f"{kt:4.0f}", (izq - 3, midy))
        ft = e["alt"] * FT
        pygame.draw.rect(s, VERDE + (230,), (der - 36, midy - 13, 84, 26), 2)
        self._txt(s, f"{ft:6.0f}", (der + 6, midy))
        self._txt(s, f"M {e['mach']:.2f}", (izq - 3, midy + 26), f=self.f_peq)
        self._txt(s, f"G {e['g']:.1f}", (izq - 3, midy + 42), f=self.f_peq)
        self._txt(s, f"α {math.degrees(e['alfa']):4.1f}", (izq - 3, midy + 58), f=self.f_peq)
        if e["agl"] * FT < 5000:
            self._txt(s, f"R {e['agl'] * FT:5.0f}", (der + 6, midy + 26), f=self.f_peq)
        self._txt(s, f"VS {e['vs'] * FT * 60:+6.0f}", (der + 6, midy + 42), f=self.f_peq)
        thr = e["gases"]
        txt_thr = f"PQ {int((thr - 0.8) / 0.2 * 100):3d}%" if thr > 0.8 else f"MIL {int(thr / 0.8 * 100):3d}%"
        if e["tren"] > 0.03:
            txt_thr += "   TREN" if e["tren"] > 0.97 else "   TREN ↕"
        self._txt(s, txt_thr, (izq - 3 - 30, midy + 74), centro=False, f=self.f_peq)

        if e.get("obj_pos") is not None:
            q = pr.punto(e["obj_pos"])
            if q:
                x, y = q
                pygame.draw.polygon(s, VERDE + (230,), [(x, y - 9), (x + 9, y), (x, y + 9), (x - 9, y)], 2)
        if e.get("ils"):
            loc, gs = e["ils"]
            c = (clip.centerx, clip.centery)
            xl = c[0] + max(-1, min(1, loc)) * clip.w * 0.25
            yg = c[1] + max(-1, min(1, gs)) * clip.h * 0.25
            self._linea(s, (xl, c[1] - clip.h * 0.22), (xl, c[1] + clip.h * 0.22), 2, AMBAR)
            self._linea(s, (c[0] - clip.w * 0.22, yg), (c[0] + clip.w * 0.22, yg), 2, AMBAR)
        if e.get("blanco") is not None:
            b = e["blanco"]
            q = pr.punto(b["pos"])
            if q:
                x, y = q
                lado = 16
                col = VERDE
                pygame.draw.rect(s, col + (235,), (x - lado, y - lado, 2 * lado, 2 * lado), 2)
                if b["fijado_ir"]:
                    pygame.draw.circle(s, col + (235,), (int(x), int(y)), 26, 2)
                self._txt(s, f"{b['dist'] / 1852:4.1f}", (x, y + lado + 10), f=self.f_peq)
            if b["disparo"]:
                self._txt(s, "DISPARO", (clip.centerx, clip.centery - 40), f=self.f_gr)
            self._txt(s, b["arma"], (clip.left + 12, top + 34), centro=False, f=self.f_peq)
        s.set_clip(None)

        avisos = []
        t = e["t"]
        if e.get("misil_enemigo"):
            avisos.append(("¡MISIL! · Q BENGALAS", ROJO))
        elif e.get("fijado_enemigo"):
            avisos.append(("TE TIENEN FIJADO", AMBAR))
        if e.get("tierra"):
            avisos.append(("¡ARRIBA! TERRENO", ROJO))
        if e.get("perdida"):
            avisos.append(("PÉRDIDA", ROJO))
        if e.get("solucion_canon"):
            self._txt(s, "CAÑÓN · EN SOLUCIÓN", (clip.centerx, clip.bottom - 24), f=self.f_gr, color=VERDE)
        if e.get("sobre_g"):
            avisos.append((f"SOBRE-G · ESTRUCTURA {100 * min(e.get('fatiga', 0) / C.FATIGA_ROTURA, 1):.0f}%", ROJO))
        if e.get("aviso_tren"):
            avisos.append(("TREN", AMBAR))
        if e.get("bingo"):
            avisos.append(("COMBUSTIBLE", AMBAR))
        if avisos and int(t * 3) % 2 == 0:
            for k, (txt, col) in enumerate(avisos):
                self._txt(s, txt, (clip.centerx, clip.centery + 60 + k * 24), f=self.f_gr, color=col)


def vineta(s, carga, nube, intensidad_g):
    W, H = s.get_size()
    if intensidad_g > 0.02:
        capa = pygame.Surface((W, H), pygame.SRCALPHA)
        rojo = carga < 0
        col = (120, 0, 0) if rojo else (0, 0, 0)
        for k in range(10):
            a = int(min(255, intensidad_g * 255 * (k + 1) / 10))
            r = int(max(W, H) * (0.95 - k * 0.07) * (1.15 - intensidad_g * 0.6))
            pygame.draw.circle(capa, col + (min(255, a // 3),), (W // 2, H // 2), r, max(8, r // 6))
        if intensidad_g > 0.85:
            capa.fill(col + (int(255 * min(1, (intensidad_g - 0.85) / 0.15)),), special_flags=pygame.BLEND_RGBA_MAX)
        s.blit(capa, (0, 0))
    if nube > 0.01:
        s.fill((235, 238, 242, int(220 * nube)), special_flags=pygame.BLEND_RGBA_MAX)
