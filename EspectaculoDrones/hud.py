import os
import time

import pygame

import config as C

FONDO = (14, 16, 20)
TARJETA = (14, 16, 20, 205)
BORDE = (38, 43, 54, 255)
TEXTO = (232, 235, 241)
TENUE = (138, 147, 166)
SUTIL = (90, 98, 117)
ACENTO = (245, 180, 0)
VERDE = (56, 211, 159)
ROJO = (255, 95, 95)
AZUL = (78, 164, 255)


def _hex(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def _fuente(archivo, tam):
    ruta = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts", archivo)
    try:
        return pygame.font.Font(ruta, tam)
    except (OSError, FileNotFoundError):
        return pygame.font.SysFont("segoeui", tam)


def mmss(t):
    t = max(0, int(t))
    return f"{t // 60:02d}:{t % 60:02d}"


class Hud:
    def __init__(self, tam):
        self.tam = None
        self.redimensionar(tam)
        self.linea = pygame.Rect(0, 0, 0, 0)
        self.rect_grabar = pygame.Rect(0, 0, 0, 0)
        self.aviso = ""
        self.aviso_t = 0.0

    def redimensionar(self, tam):
        if tam == self.tam:
            return
        self.tam = tam
        self.k = max(0.75, min(tam[1] / 900, 1.6))
        k = self.k
        self.f_mini = _fuente("seguisb.ttf", int(11 * k))
        self.f_chica = _fuente("segoeui.ttf", int(13 * k))
        self.f_texto = _fuente("segoeui.ttf", int(15 * k))
        self.f_semi = _fuente("seguisb.ttf", int(15 * k))
        self.f_titulo = _fuente("seguisb.ttf", int(22 * k))
        self.f_valor = _fuente("seguisb.ttf", int(17 * k))
        self.sup = pygame.Surface(tam, pygame.SRCALPHA)

    def mostrar_aviso(self, texto, t):
        self.aviso, self.aviso_t = texto, t

    def _tarjeta(self, r):
        s = self.sup
        pygame.draw.rect(s, TARJETA, r, border_radius=int(10 * self.k))
        pygame.draw.rect(s, BORDE, r, 1, border_radius=int(10 * self.k))

    def _txt(self, f, texto, color, pos, ancla="topleft"):
        img = f.render(texto, True, color)
        r = img.get_rect(**{ancla: pos})
        self.sup.blit(img, r)
        return r

    def _chip(self, texto, color, pos, ancla="topleft", relleno=False):
        k = self.k
        img = self.f_mini.render(texto, True, FONDO if relleno else color)
        r = img.get_rect()
        caja = pygame.Rect(0, 0, r.w + int(18 * k), r.h + int(8 * k))
        setattr(caja, ancla, pos)
        if relleno:
            pygame.draw.rect(self.sup, (*color, 240), caja, border_radius=caja.h // 2)
        else:
            pygame.draw.rect(self.sup, (14, 16, 20, 225), caja, border_radius=caja.h // 2)
            pygame.draw.rect(self.sup, (*color, 170), caja, 1, border_radius=caja.h // 2)
        self.sup.blit(img, img.get_rect(center=caja.center))
        return caja

    def dibujar(self, v):
        s = self.sup
        s.fill((0, 0, 0, 0))
        k = self.k
        W, H = self.tam
        m = int(18 * k)
        plan = v.plan
        seg = plan.seg[v.seg_i]
        nombre_fase, color_fase = C.FASES.get(seg["fase"], ("", "#ffffff"))
        cf = _hex(color_fase)

        r = pygame.Rect(m, m, int(400 * k), int(132 * k))
        self._tarjeta(r)
        x, y = r.x + int(16 * k), r.y + int(12 * k)
        self._txt(self.f_mini, "ESPECTÁCULO DE DRONES", TENUE, (x, y))
        y += int(18 * k)
        titulo = plan.show.get("nombre", "Espectáculo")
        while self.f_titulo.size(titulo)[0] > r.w - 32 * k and len(titulo) > 4:
            titulo = titulo[:-2] + "…" if not titulo.endswith("…") else titulo[:-3] + "…"
        self._txt(self.f_titulo, titulo, TEXTO, (x, y))
        y += int(36 * k)
        caja = self._chip(nombre_fase.upper(), cf, (x, y), relleno=True)
        detalle = seg["nombre"] if seg["fase"] in ("formacion", "transicion") else ""
        if seg["fase"] == "formacion":
            n_esc = plan.stats.get("escenas", 0)
            detalle = f"{seg.get('escena', 0) + 1} de {n_esc} · {seg['nombre']}"
        if detalle:
            while self.f_semi.size(detalle)[0] > r.right - caja.right - 24 * k and len(detalle) > 4:
                detalle = detalle[:-2] + "…"
            self._txt(self.f_semi, detalle, TEXTO, (caja.right + int(10 * k), caja.centery), "midleft")
        y += caja.h + int(10 * k)
        self._txt(self.f_valor, mmss(v.t), TEXTO, (x, y))
        self._txt(self.f_chica, f"/ {mmss(plan.duracion)}", TENUE, (x + self.f_valor.size(mmss(v.t))[0] + int(6 * k), y + int(3 * k)))
        estado = "EN PAUSA" if v.pausa else f"×{v.velocidad:g}"
        self._chip(estado, ACENTO if v.pausa else TENUE, (r.right - int(16 * k), y + int(2 * k)), "topright")

        r2 = pygame.Rect(W - m - int(300 * k), m, int(300 * k), int(240 * k))
        self._tarjeta(r2)
        x, y = r2.x + int(16 * k), r2.y + int(12 * k)
        self._txt(self.f_mini, "TELEMETRÍA DE LA FLOTA", TENUE, (x, y))
        y += int(24 * k)
        t = v.telemetria
        filas = [
            ("Drones en el aire", f"{t['aire']} / {plan.n}", TEXTO),
            ("Altitud media", f"{t['alt_media']:.1f} m", TEXTO),
            ("Altitud máxima", f"{t['alt_max']:.1f} m", TEXTO),
            ("Velocidad máxima", f"{t['vel']:.1f} m/s", TEXTO),
            ("Separación mínima", f"{t['sep']:.2f} m" if t['sep'] < 1e6 else "—",
             VERDE if t['sep'] >= C.SEP_SEGURA else ROJO),
            ("Viento", f"{t['viento']:.1f} m/s", TEXTO),
        ]
        for etq, val, col in filas:
            self._txt(self.f_chica, etq, TENUE, (x, y))
            self._txt(self.f_semi, val, col, (r2.right - int(16 * k), y - int(1 * k)), "topright")
            y += int(24 * k)
        y += int(4 * k)
        self._txt(self.f_chica, "Batería estimada", TENUE, (x, y))
        bat = t["bateria"]
        self._txt(self.f_semi, f"{bat:.0f} %", VERDE if bat > 30 else ROJO, (r2.right - int(16 * k), y - int(1 * k)), "topright")
        y += int(24 * k)
        bw = r2.w - int(32 * k)
        pygame.draw.rect(s, (35, 40, 53, 255), (x, y, bw, int(6 * k)), border_radius=3)
        pygame.draw.rect(s, (*(VERDE if bat > 30 else ROJO), 255), (x, y, int(bw * bat / 100), int(6 * k)), border_radius=3)

        r3 = pygame.Rect(W - m - int(300 * k), r2.bottom + int(10 * k), int(300 * k), int(64 * k))
        self._tarjeta(r3)
        x, y = r3.x + int(16 * k), r3.y + int(10 * k)
        self._txt(self.f_mini, "CÁMARA", TENUE, (x, y))
        self._txt(self.f_semi, v.camara.nombre(), TEXTO, (x, y + int(18 * k)))
        chips_x = r3.right - int(14 * k)
        for etq, on in (("ESTELAS", v.render.estelas), ("DRONES", v.render.cuerpos)):
            c = self._chip(etq, ACENTO if on else SUTIL, (chips_x, r3.centery), "midright", relleno=on)
            chips_x = c.left - int(6 * k)

        rg = pygame.Rect(r3.right - int(182 * k), r3.bottom + int(10 * k), int(182 * k), int(36 * k))
        self.rect_grabar = rg
        sobre = rg.collidepoint(pygame.mouse.get_pos())
        if v.grabador.grabando:
            pygame.draw.rect(s, (200, 40, 44, 235) if sobre else (176, 32, 36, 225), rg, border_radius=int(8 * k))
            if int(time.perf_counter() * 2) % 2 == 0:
                pygame.draw.rect(s, (255, 255, 255, 255), (rg.x + int(13 * k), rg.centery - int(6 * k), int(12 * k), int(12 * k)))
            etiqueta = f"Stop  {mmss(int(v.reloj - v.grabador.inicio))}"
        else:
            pygame.draw.rect(s, (40, 46, 60, 235) if sobre else TARJETA, rg, border_radius=int(8 * k))
            pygame.draw.circle(s, (239, 83, 80, 255), (rg.x + int(19 * k), rg.centery), int(7 * k))
            etiqueta = "Grabar pantalla"
        pygame.draw.rect(s, (239, 83, 80, 255), rg, 1, border_radius=int(8 * k))
        self._txt(self.f_semi, etiqueta, TEXTO, (rg.x + int(34 * k), rg.centery), "midleft")

        alto_l = int(78 * k)
        r4 = pygame.Rect(m, H - m - alto_l, W - 2 * m, alto_l)
        self._tarjeta(r4)
        bx = r4.x + int(16 * k)
        bw = r4.w - int(32 * k)
        by = r4.y + int(34 * k)
        bh = int(12 * k)
        self.linea = pygame.Rect(bx, by - int(14 * k), bw, bh + int(28 * k))
        dur = max(plan.duracion, 1e-6)
        for sg in plan.seg:
            x0 = bx + int(bw * sg["t0"] / dur)
            x1 = bx + int(bw * sg["t1"] / dur)
            col = _hex(C.FASES.get(sg["fase"], ("", "#7d8596"))[1])
            hecho = v.t >= sg["t1"]
            a = 255 if hecho or sg is seg else 120
            pygame.draw.rect(s, (*col, a), (x0, by, max(x1 - x0 - 1, 1), bh), border_radius=int(3 * k))
            if sg["fase"] == "formacion" and x1 - x0 > 40 * k:
                etq = sg["nombre"]
                while self.f_mini.size(etq)[0] > x1 - x0 - 6 and len(etq) > 3:
                    etq = etq[:-2] + "…"
                self._txt(self.f_mini, etq, TEXTO if hecho or sg is seg else TENUE, ((x0 + x1) // 2, by - int(4 * k)), "midbottom")
        px = bx + int(bw * min(v.t / dur, 1.0))
        pygame.draw.line(s, (255, 255, 255, 255), (px, by - int(6 * k)), (px, by + bh + int(6 * k)), max(2, int(2 * k)))
        pygame.draw.circle(s, (255, 255, 255, 255), (px, by - int(6 * k)), int(4 * k))
        ayuda = "Espacio pausa · ←/→ ±5 s · ↑/↓ velocidad · C cámara · arrastrar: girar · rueda: zoom · T estelas · B drones · H interfaz · F9 grabar · F12 captura · R reiniciar · Esc salir"
        while self.f_chica.size(ayuda)[0] > bw and " · " in ayuda:
            ayuda = ayuda.rsplit(" · ", 1)[0]
        self._txt(self.f_chica, ayuda, SUTIL, (bx, by + bh + int(10 * k)))
        mx, my = pygame.mouse.get_pos()
        if self.linea.collidepoint(mx, my):
            tt = (mx - bx) / bw * dur
            self._chip(mmss(tt), TEXTO, (mx, by - int(20 * k)), "midbottom")

        if v.grabador.grabando:
            seg_rec = int(v.reloj - v.grabador.inicio)
            self._chip(f"●  REC  {mmss(seg_rec)}", ROJO, (W // 2, m), "midtop", relleno=True)
        if self.aviso and v.reloj - self.aviso_t < 3.5:
            self._chip(self.aviso, TEXTO, (W // 2, m + int(36 * k)), "midtop")
        return pygame.image.tobytes(s, "RGBA", True)
