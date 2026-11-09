import math

import numpy as np
import pygame

import config as C
import terreno as T
from misiones import BLANCO, DESPEGUE, DETENER, PENDIENTE, PUNTO, TOQUE

VERDE = (60, 255, 110)
VERDE_T = (60, 255, 110, 70)
AMBAR = (255, 176, 40)
ROJO = (255, 60, 50)
BLANCO = (235, 235, 230)
GRIS = (120, 124, 128)
KT = 1.94384
FT = 3.28084


def _fuente(tam, negrita=False, mono=True):
    pygame.font.init()
    nombres = "consolas,couriernew,dejavusansmono" if mono else "segoeui,arial,dejavusans"
    return pygame.font.SysFont(nombres, tam, bold=negrita)


def _texto(s, f, txt, color, pos, centro=False, der=False):
    img = f.render(txt, True, color)
    r = img.get_rect()
    if centro:
        r.center = pos
    elif der:
        r.topright = pos
    else:
        r.topleft = pos
    s.blit(img, r)
    return r


def _mapa_isla(tam=320):
    h = T.ALTURAS
    paso = max(1, h.shape[0] // tam)
    m = h[::paso, ::paso][:tam, :tam]
    alturas = [0, 150, 600, 1200, 1800, 2300]
    paleta = np.array([(46, 96, 44), (70, 120, 52), (140, 128, 76), (120, 100, 80), (200, 200, 196),
                       (240, 240, 240)], float)
    img = np.stack([np.interp(m, alturas, paleta[:, k]) for k in range(3)], -1)
    img[m < 0] = (12, 40, 72)
    sup = pygame.surfarray.make_surface(img.swapaxes(0, 1).astype(np.uint8))
    return sup, T.MITAD * 2 / sup.get_width()


class Panel:
    W, H = 1024, 512

    def __init__(self):
        self.s = pygame.Surface((self.W, self.H), pygame.SRCALPHA)
        self.f_peq = _fuente(13)
        self.f_med = _fuente(17, True)
        self.f_gr = _fuente(24, True)
        self.f_et = _fuente(11, False, False)
        self.mapa, self.m_px = _mapa_isla()
        self.m_por_px = 110.0
        z = self.m_px / self.m_por_px
        self.mapa_z = pygame.transform.smoothscale(self.mapa, (int(self.mapa.get_width() * z),
                                                               int(self.mapa.get_height() * z)))
        self.fondo = self._fondo()

    def _fondo(self):
        s = pygame.Surface((self.W, self.H), pygame.SRCALPHA)
        s.fill((34, 37, 40, 0))
        rng = np.random.default_rng(2)
        for _ in range(1600):
            x, y = rng.integers(0, self.W), rng.integers(0, self.H)
            c = int(rng.integers(30, 44))
            s.set_at((int(x), int(y)), (c, c + 2, c + 4, 0))
        for r in ((14, 14, 292, 270), (586, 14, 292, 270)):
            pygame.draw.rect(s, (22, 23, 25, 0), r, border_radius=10)
            pygame.draw.rect(s, (60, 63, 66, 0), r, 2, border_radius=10)
            for k in range(5):
                bx = r[0] + 26 + k * 56
                pygame.draw.rect(s, (55, 58, 60, 0), (bx, r[1] + 4, 30, 9), border_radius=2)
                pygame.draw.rect(s, (55, 58, 60, 0), (bx, r[1] + r[3] - 13, 30, 9), border_radius=2)
        for cx, cy, rad in ((443, 140, 118), (443, 398, 100), (110, 392, 82), (676, 392, 82), (850, 392, 66)):
            pygame.draw.circle(s, (18, 19, 20, 0), (cx, cy), rad + 6)
            pygame.draw.circle(s, (70, 72, 75, 0), (cx, cy), rad + 6, 2)
        for x, y in ((8, 8), (1010, 8), (8, 498), (1010, 498), (512, 8), (512, 498)):
            pygame.draw.circle(s, (80, 82, 85, 0), (x, y), 4)
        for txt, pos in (("RADAR", (125, 290)), ("MAPA", (705, 290)), ("ADI", (430, 2)), ("HSI", (430, 282)),
                         ("VEL", (98, 300)), ("ALT", (664, 300)), ("VVI", (838, 318)), ("MOTOR", (920, 14)),
                         ("TREN", (930, 330))):
            _texto(s, self.f_et, txt, (200, 200, 195, 0), pos)
        return s

    def _aguja(self, s, c, r, ang, color=BLANCO, ancho=3):
        x = c[0] + r * math.sin(ang)
        y = c[1] - r * math.cos(ang)
        pygame.draw.line(s, color, c, (x, y), ancho)

    def _dial(self, s, c, r, marcas, etiquetas, valor_ang, titulo=""):
        pygame.draw.circle(s, (8, 8, 9, 255), c, r)
        for k in range(marcas):
            a = 2 * math.pi * k / marcas
            r0 = r - (10 if k % (marcas // len(etiquetas)) == 0 else 5)
            pygame.draw.line(s, BLANCO + (255,), (c[0] + r0 * math.sin(a), c[1] - r0 * math.cos(a)),
                             (c[0] + (r - 2) * math.sin(a), c[1] - (r - 2) * math.cos(a)), 2)
        for k, et in enumerate(etiquetas):
            a = 2 * math.pi * k / len(etiquetas)
            _texto(s, self.f_peq, et, BLANCO, (c[0] + (r - 22) * math.sin(a), c[1] - (r - 22) * math.cos(a)), True)
        if titulo:
            _texto(s, self.f_peq, titulo, GRIS, (c[0], c[1] + r * 0.42), True)
        self._aguja(s, c, r - 12, valor_ang, (250, 250, 245, 255), 4)
        pygame.draw.circle(s, (60, 60, 60, 255), c, 5)

    def _adi(self, s, c, r, cab, alab):
        sub = pygame.Surface((2 * r, 2 * r), pygame.SRCALPHA)
        esc = r / math.radians(35)
        off = cab * esc
        grande = pygame.Surface((4 * r, 4 * r), pygame.SRCALPHA)
        g = 2 * r
        pygame.draw.rect(grande, (40, 110, 200, 255), (0, 0, 4 * r, g + off))
        pygame.draw.rect(grande, (120, 75, 35, 255), (0, g + off, 4 * r, 4 * r))
        pygame.draw.line(grande, (255, 255, 255, 255), (0, g + off), (4 * r, g + off), 2)
        for k in range(-6, 7):
            if k == 0:
                continue
            y = g + off - k * math.radians(10) * esc
            w = 40 if k % 2 == 0 else 22
            pygame.draw.line(grande, (255, 255, 255, 255), (g - w, y), (g + w, y), 2)
            if k % 2 == 0:
                _texto(grande, self.f_peq, str(abs(k * 10)), (255, 255, 255), (g + w + 14, y), True)
        rot = pygame.transform.rotate(grande, math.degrees(alab))
        rr = rot.get_rect(center=(r, r))
        sub.blit(rot, rr)
        mascara = pygame.Surface((2 * r, 2 * r), pygame.SRCALPHA)
        pygame.draw.circle(mascara, (255, 255, 255, 255), (r, r), r)
        sub.blit(mascara, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
        s.blit(sub, (c[0] - r, c[1] - r))
        pygame.draw.line(s, AMBAR + (255,), (c[0] - 60, c[1]), (c[0] - 18, c[1]), 5)
        pygame.draw.line(s, AMBAR + (255,), (c[0] + 18, c[1]), (c[0] + 60, c[1]), 5)
        pygame.draw.circle(s, AMBAR + (255,), c, 5)
        for a in (-60, -45, -30, -20, -10, 0, 10, 20, 30, 45, 60):
            t = math.radians(a)
            pygame.draw.line(s, BLANCO + (255,), (c[0] + (r - 2) * math.sin(t), c[1] - (r - 2) * math.cos(t)),
                             (c[0] + (r - 12) * math.sin(t), c[1] - (r - 12) * math.cos(t)), 2)
        t = -alab
        pygame.draw.polygon(s, AMBAR + (255,), [(c[0] + (r - 14) * math.sin(t), c[1] - (r - 14) * math.cos(t)),
                                                (c[0] + (r - 26) * math.sin(t - 0.06), c[1] - (r - 26) * math.cos(t - 0.06)),
                                                (c[0] + (r - 26) * math.sin(t + 0.06), c[1] - (r - 26) * math.cos(t + 0.06))])

    def _hsi(self, s, c, r, rumbo, rumbo_obj, dist):
        pygame.draw.circle(s, (8, 8, 9, 255), c, r)
        for k in range(72):
            a = math.radians(k * 5) - rumbo
            l = 12 if k % 6 == 0 else 6
            pygame.draw.line(s, BLANCO + (255,), (c[0] + (r - l) * math.sin(a), c[1] - (r - l) * math.cos(a)),
                             (c[0] + r * math.sin(a), c[1] - r * math.cos(a)), 2)
            if k % 6 == 0:
                txt = {0: "N", 18: "E", 36: "S", 54: "W"}.get(k, str(k // 2))
                _texto(s, self.f_peq, txt, BLANCO, (c[0] + (r - 24) * math.sin(a), c[1] - (r - 24) * math.cos(a)), True)
        if rumbo_obj is not None:
            a = rumbo_obj - rumbo
            p1 = (c[0] + (r - 30) * math.sin(a), c[1] - (r - 30) * math.cos(a))
            p0 = (c[0] - (r - 30) * math.sin(a), c[1] + (r - 30) * math.cos(a))
            pygame.draw.line(s, (255, 0, 255, 255), p0, p1, 4)
            pygame.draw.circle(s, (255, 0, 255, 255), (int(p1[0]), int(p1[1])), 6)
        pygame.draw.polygon(s, AMBAR + (255,), [(c[0], c[1] - 18), (c[0] - 12, c[1] + 12), (c[0], c[1] + 6),
                                                (c[0] + 12, c[1] + 12)])
        _texto(s, self.f_med, f"{math.degrees(rumbo) % 360:03.0f}", BLANCO, (c[0], c[1] - r - 2), True)
        if dist is not None:
            _texto(s, self.f_peq, f"{dist / 1852:5.1f} NM", (255, 0, 255), (c[0], c[1] + 40), True)

    def _radar(self, s, r, e):
        x0, y0, w, h = r
        pygame.draw.rect(s, (4, 14, 6, 255), (x0 + 12, y0 + 18, w - 24, h - 36))
        alcance = 40000.0
        for k in range(1, 4):
            y = y0 + 18 + (h - 36) * k / 4
            pygame.draw.line(s, (30, 90, 40, 255), (x0 + 12, y), (x0 + w - 12, y), 1)
        for k in (-2, -1, 0, 1, 2):
            x = x0 + w / 2 + k * (w - 24) / 6
            pygame.draw.line(s, (30, 90, 40, 255), (x, y0 + 18), (x, y0 + h - 18), 1)
        _texto(s, self.f_peq, "40", VERDE, (x0 + 16, y0 + 20))
        _texto(s, self.f_peq, "RWS", VERDE, (x0 + w - 50, y0 + 20))
        barrido = (math.sin(e["t"] * 1.3) * 0.5 + 0.5)
        xb = x0 + 12 + (w - 24) * barrido
        pygame.draw.line(s, (40, 160, 60, 255), (xb, y0 + h - 22), (xb, y0 + h - 30), 3)
        for b in e.get("blancos", []):
            az, d, fijado = b
            if d > alcance or abs(az) > math.radians(60):
                continue
            x = x0 + w / 2 + az / math.radians(60) * (w - 24) / 2
            y = y0 + h - 18 - d / alcance * (h - 36)
            col = (255, 255, 255, 255) if fijado else VERDE + (255,)
            pygame.draw.rect(s, col, (x - 5, y - 5, 10, 10), 0 if fijado else 2)
            if fijado:
                pygame.draw.rect(s, VERDE + (255,), (x - 10, y - 10, 20, 20), 2)
        if e.get("misil_enemigo") and int(e["t"] * 4) % 2 == 0:
            pygame.draw.rect(s, ROJO + (255,), (x0 + 60, y0 + 20, 90, 18))
            _texto(s, self.f_peq, "MISIL", (20, 0, 0), (x0 + 105, y0 + 29), True)
        _texto(s, self.f_peq, f"MSL {e.get('misiles', 0)}  CAÑ {e.get('municion', 0)}  BNG {e.get('bengalas', 0)}", VERDE,
               (x0 + w / 2, y0 + h - 14), True)

    def _mapa(self, s, r, e):
        x0, y0, w, h = r
        area = pygame.Rect(x0 + 12, y0 + 18, w - 24, h - 36)
        sub = pygame.Surface(area.size, pygame.SRCALPHA)
        sub.fill((5, 10, 15, 255))
        px, pz = e["pos"][0], e["pos"][2]
        rumbo = e["rumbo"]
        m_por_px = self.m_por_px
        c, sn = math.cos(rumbo), math.sin(rumbo)
        mz = self.mapa_z
        ux = (px + T.MITAD) / m_por_px
        uy = (pz + T.MITAD) / m_por_px
        lado = 360
        recorte = pygame.Surface((lado, lado))
        recorte.fill((12, 40, 72))
        recorte.blit(mz, (lado / 2 - ux, lado / 2 - uy))
        img = pygame.transform.rotate(recorte, math.degrees(rumbo))
        rect = img.get_rect(center=(area.w / 2, area.h * 0.65))
        sub.blit(img, rect)

        def a_pant(x, z):
            ddx, ddz = (x - px) / m_por_px, (z - pz) / m_por_px
            return (area.w / 2 + ddx * c + ddz * sn, area.h * 0.65 - ddx * sn + ddz * c)

        for a in T.AEROPUERTOS:
            p0 = a.mundo(0, 0)
            p1 = a.mundo(a.largo, 0)
            pygame.draw.line(sub, (240, 240, 240, 255), a_pant(p0[0], p0[2]), a_pant(p1[0], p1[2]), 4)
        ruta = e.get("ruta", [])
        pts = [a_pant(p[0], p[2]) for p in ruta]
        if len(pts) > 1:
            pygame.draw.lines(sub, (255, 0, 255, 255), False, pts, 2)
        for i, p in enumerate(pts):
            pygame.draw.circle(sub, (255, 0, 255, 255), (int(p[0]), int(p[1])), 5 if i else 7, 0 if i == 0 else 2)
        for b in e.get("drones_pos", []):
            q = a_pant(b[0], b[2])
            pygame.draw.polygon(sub, ROJO + (255,), [(q[0], q[1] - 6), (q[0] - 5, q[1] + 4), (q[0] + 5, q[1] + 4)])
        cxa, cya = area.w / 2, area.h * 0.65
        pygame.draw.polygon(sub, (255, 255, 255, 255), [(cxa, cya - 9), (cxa - 7, cya + 7), (cxa + 7, cya + 7)])
        s.blit(sub, area.topleft)
        _texto(s, self.f_peq, "10 NM", VERDE, (x0 + 18, y0 + 20))
        _texto(s, self.f_peq, f"{math.degrees(rumbo) % 360:03.0f}°", VERDE, (x0 + w - 60, y0 + 20))

    def dibujar(self, e):
        s = self.s
        s.blit(self.fondo, (0, 0))
        self._radar(s, (14, 14, 292, 270), e)
        self._mapa(s, (586, 14, 292, 270), e)
        self._adi(s, (443, 140), 118, e["cabeceo"], e["alabeo"])
        self._hsi(s, (443, 398), 100, e["rumbo"], e.get("rumbo_obj"), e.get("dist_obj"))
        kt = e["vel"] * KT
        ang = min(kt, 800) / 800 * 2 * math.pi * 0.92
        self._dial(s, (110, 392), 82, 40, ["0", "100", "200", "300", "400", "500", "600", "700"], ang)
        _texto(s, self.f_med, f"{kt:3.0f}", BLANCO + (255,), (110, 420), True)
        _texto(s, self.f_peq, f"M{e['mach']:.2f}", AMBAR, (110, 438), True)
        ft = e["alt"] * FT
        self._dial(s, (676, 392), 82, 50, [str(k) for k in range(10)], (ft % 1000) / 1000 * 2 * math.pi)
        pygame.draw.rect(s, (0, 0, 0, 255), (636, 420, 80, 22))
        _texto(s, self.f_med, f"{ft:6.0f}", BLANCO + (255,), (676, 431), True)
        vvi = max(-6000, min(6000, e["vs"] * FT * 60))
        self._dial(s, (850, 392), 66, 24, ["0", "1", "2", "4", "6", "4", "2", "1"],
                   -math.pi / 2 + vvi / 6000 * math.pi * 0.85)
        pygame.draw.rect(s, (10, 10, 10, 255), (225, 300, 36, 190))
        aoa = max(0, min(45, math.degrees(e["alfa"]) * 1.4))
        for k in range(0, 46, 5):
            y = 485 - k * 4
            pygame.draw.line(s, BLANCO + (255,), (228, y), (236 if k % 10 else 242, y), 1)
        pygame.draw.rect(s, (40, 200, 60, 255), (244, 485 - 26 * 4, 12, 6 * 4))
        pygame.draw.polygon(s, AMBAR + (255,), [(258, 485 - aoa * 4), (248, 480 - aoa * 4), (248, 490 - aoa * 4)])
        _texto(s, self.f_peq, "AOA", GRIS, (243, 304), True)
        for k, (nombre, val) in enumerate((("RPM I", e.get("rpm_i", e["rpm"])), ("RPM D", e.get("rpm_d", e["rpm"])))):
            x = 905 + k * 52
            pygame.draw.rect(s, (8, 8, 9, 255), (x, 34, 40, 150))
            h = int(146 * min(1, val))
            pygame.draw.rect(s, (60, 220, 90, 255) if val < 1.0 else (255, 160, 40, 255), (x + 2, 182 - h, 36, h))
            _texto(s, self.f_peq, nombre, BLANCO + (255,), (x + 20, 188), True)
        if e.get("pq", 0) > 0.05:
            pygame.draw.rect(s, (255, 140, 30, 255), (905, 208, 92, 20), border_radius=3)
            _texto(s, self.f_peq, "POSTQUEMADOR", (20, 10, 0), (951, 218), True)
        _texto(s, self.f_peq, f"COMB {e['comb']:5.0f} KG", BLANCO + (255,), (951, 240), True)
        _texto(s, self.f_peq, f"FLUJO {e['flujo']:4.1f}", BLANCO + (255,), (951, 258), True)
        _texto(s, self.f_peq, f"G {e['g']:+.1f}  MAX {e['gmax']:.1f}", BLANCO + (255,), (951, 280), True)
        tren = e["tren"]
        for k, (dx, dy) in enumerate(((0, 0), (-24, 34), (24, 34))):
            c = (60, 230, 80, 255) if tren > 0.97 else ((230, 40, 30, 255) if tren > 0.03 else (25, 25, 25, 255))
            pygame.draw.circle(s, c, (950 + dx, 360 + dy), 11)
        pygame.draw.rect(s, (70, 70, 72, 255), (928, 412, 44, 70), border_radius=4)
        ty = 470 if e["cmd_tren"] else 424
        pygame.draw.circle(s, (230, 230, 230, 255), (950, ty), 12)
        _texto(s, self.f_peq, "ABAJO" if e["cmd_tren"] else "ARRIBA", BLANCO + (255,), (950, 492), True)
        luces = [("FLAPS", e["flaps"] > 0.5, (80, 200, 255)), ("AEROFR", e["aerofreno"] > 0.1, (80, 200, 255)),
                 ("FRENOS", e["freno"] > 0.1, AMBAR), ("PERDIDA", e["perdida"], ROJO),
                 ("PRECAUC", e["precaucion"], AMBAR), ("TREN", e["dano_tren"], ROJO)]
        for k, (txt, on, col) in enumerate(luces):
            rect = pygame.Rect(266, 300 + k * 31, 70, 26)
            pygame.draw.rect(s, (col + (255,)) if on else (28, 28, 30, 0), rect, border_radius=3)
            pygame.draw.rect(s, (70, 70, 72, 0), rect, 1, border_radius=3)
            _texto(s, self.f_et, txt, (15, 15, 15) if on else (90, 90, 90), rect.center, True)
        if not e.get("energia", True):
            for r in ((26, 32, 268, 234), (598, 32, 268, 234)):
                pygame.draw.rect(s, (6, 7, 8, 255), r)
            for c, rad in (((443, 140), 118), ((443, 398), 100)):
                pygame.draw.circle(s, (6, 7, 8, 255), c, rad)
            _texto(s, self.f_med, "SIN ENERGÍA", (90, 90, 90), (160, 150), True)
            _texto(s, self.f_med, "SIN ENERGÍA", (90, 90, 90), (732, 150), True)
        return s
