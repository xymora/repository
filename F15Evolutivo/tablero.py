import math

import numpy as np
import pygame

import cerebro as B
from arranque import ETIQUETAS, INTERRUPTORES, PASOS, VUELO
from cabina import _fuente, _texto
from catalogo import CURRICULO, nombre
from sensores import GRUPOS
from terreno import superficie

TARJETA = (22, 25, 32, 232)
BORDE = (38, 43, 54)
TEXTO = (232, 234, 238)
TENUE = (150, 156, 168)
ORO = (245, 180, 0)
AZUL = (90, 170, 255)
VERDE = (80, 220, 120)
ROJO = (255, 80, 60)
AMBAR = (255, 176, 40)
APAGADO = (52, 56, 66)
TECLAS = {"CANOPY": "1", "JFS": "2", "BOMBAS": "3", "ARR_D": "4", "COMB_D": "Shift+4", "ARR_I": "5",
          "COMB_I": "Shift+5", "GEN": "6", "AVIONICA": "7", "SAS": "8", "FLAPS": "F", "CHEQUEO": "9",
          "RODAJE": "0"}
NOMBRES_COMP = ("progreso", "calidad", "castigo", "vuelo brusco", "caída", "éxito")


def entropia_binaria(salida, vivos):
    if salida is None or not np.any(vivos):
        return 0.0
    p = np.clip((salida[vivos] > 0).mean(0), 1e-6, 1 - 1e-6)
    return float(np.mean(-(p * np.log2(p) + (1 - p) * np.log2(1 - p))))


def _tarjeta(s, r):
    pygame.draw.rect(s, TARJETA, r, border_radius=10)
    pygame.draw.rect(s, BORDE + (255,), r, 1, border_radius=10)


def _color_valor(v):
    v = max(-1.0, min(1.0, float(v)))
    if v >= 0:
        return (int(40 + 40 * v), int(60 + 160 * v), int(70 + 60 * v))
    return (int(60 + 190 * -v), int(60 + 30 * -v), int(50 + 10 * -v))


class Tablero:
    def __init__(self, escala=1.0):
        self.ajustar(escala)

    def ajustar(self, escala):
        self.k = escala
        e = escala
        self.f_tit = _fuente(int(15 * e), True, False)
        self.f_gr = _fuente(int(21 * e), True, False)
        self.f_med = _fuente(int(15 * e), False, False)
        self.f_med_b = _fuente(int(15 * e), True, False)
        self.f_peq = _fuente(int(12 * e), False, False)
        self.f_mono = _fuente(int(12 * e))

    def _seccion(self, s, txt, x, y, w):
        _texto(s, self.f_tit, txt, ORO, (x, y))
        pygame.draw.line(s, BORDE, (x, y + int(20 * self.k)), (x + w, y + int(20 * self.k)))
        return y + int(26 * self.k)

    def rl(self, s, app, x, y, w, alto_max):
        k = self.k
        e = app.e
        ep = app.ep
        j = app.seguido
        fila = int(19 * k)
        r = pygame.Rect(x, y, w, alto_max)
        _tarjeta(s, r)
        x0, ww = x + int(14 * k), w - int(28 * k)
        yy = y + int(10 * k)
        yy = self._seccion(s, "ENTRENAMIENTO EVOLUTIVO", x0, yy, ww)
        hist = e.historial
        u = hist[-1] if hist else {}
        gpm = 0.0
        if len(app.gen_t) > 1:
            gpm = 60 * (len(app.gen_t) - 1) / max(app.gen_t[-1] - app.gen_t[0], 1e-6)
        n_ev = e.leccion_actual
        pos = f"{CURRICULO.index(n_ev) + 1}/{len(CURRICULO)}" if n_ev in CURRICULO else "-"
        modo = {"secuencial": "secuencial", "mezcla": "mezcla con repaso", "fija": "fijo"}.get(e.modo, e.modo)
        for txt, col in ((f"Generación {e.generacion} · episodio en vivo {app.episodios}", TEXTO),
                         (f"Misión {n_ev} ({pos}) · {nombre(n_ev)}", AZUL),
                         (f"Currículo {modo} · {gpm:.1f} gen/min · {'entrenando' if app.entrenar else 'en pausa'}",
                          TENUE)):
            _texto(s, self.f_med_b if col == TEXTO else self.f_med, txt, col, (x0, yy))
            yy += fila + 2
        ult = [h for h in hist[-20:] if h.get("leccion") == n_ev]
        exito = np.mean([h["superaron_pct"] > 0 for h in ult]) * 100 if ult else 0.0
        vivos = ~ep.terminado
        salida = getattr(app.pilotos, "salida", None) if app.modo in ("ia", "campeon") else None
        ent = entropia_binaria(salida, vivos) if app.modo == "ia" else 0.0
        metr = [("σ exploración", f"{e.sigma:.4f}"), ("Entropía acciones", f"{ent:.2f} bits"),
                ("Pérdida imitación", "-" if e.perdida is None else f"{e.perdida:.4f}"),
                ("Éxito (20 gen)", f"{exito:.0f}%"),
                ("Aptitud mejor", f"{u.get('mejor_aptitud', 0):.1f}"),
                ("Aptitud prom.", f"{u.get('promedio_aptitud', 0):.1f}"),
                ("Estrellados", f"{u.get('estrellados_pct', 0):.0f}%"),
                ("Racha / sin mejora", f"{e.racha}/{e.sin_mejora}"),
                ("Estabilidad seguido", f"{100 * float(ep.estabilidad()[j]):.0f}%")]
        col_w = ww // 2
        for i, (a, b) in enumerate(metr):
            cx = x0 + (i % 2) * col_w
            cy = yy + (i // 2) * int(36 * k)
            _texto(s, self.f_peq, a, TENUE, (cx, cy))
            _texto(s, self.f_med_b, b, TEXTO, (cx, cy + int(14 * k)))
        yy += (len(metr) + 1) // 2 * int(36 * k) + int(4 * k)

        yy = self._seccion(s, "RECOMPENSA DEL AVIÓN SEGUIDO", x0, yy, ww)
        comp = ep.componentes(j)
        total = sum(comp.values())
        _texto(s, self.f_gr, f"{total:+.1f}", VERDE if total >= 0 else ROJO, (x0, yy))
        _texto(s, self.f_peq, f"fitness acumulado · progreso {comp['progreso']:.0f}%", TENUE,
               (x0 + int(90 * k), yy + int(6 * k)))
        yy += int(30 * k)
        escala = max(100.0, max(abs(v) for v in comp.values()))
        mitad = x0 + int(ww * 0.55)
        for nombre_c in NOMBRES_COMP:
            v = comp[nombre_c]
            _texto(s, self.f_peq, nombre_c, TENUE, (x0, yy))
            largo = int(abs(v) / escala * ww * 0.42)
            rr = pygame.Rect(mitad, yy + 2, largo, int(11 * k)) if v >= 0 else \
                pygame.Rect(mitad - largo, yy + 2, largo, int(11 * k))
            pygame.draw.rect(s, VERDE if v >= 0 else ROJO, rr, border_radius=3)
            pygame.draw.line(s, BORDE, (mitad, yy), (mitad, yy + int(14 * k)))
            _texto(s, self.f_mono, f"{v:+7.1f}", TEXTO, (x0 + ww, yy), der=True)
            yy += int(16 * k)
        yy += int(6 * k)

        hist_l = hist[-120:]
        if len(hist_l) > 1:
            yy = self._seccion(s, "APTITUD POR GENERACIÓN", x0, yy, ww)
            gh = int(70 * k)
            pygame.draw.rect(s, (14, 16, 20, 220), (x0, yy, ww, gh), border_radius=6)
            mx = max(max(h["mejor_aptitud"] for h in hist_l), 1.0)
            mn = min(min(h["promedio_aptitud"] for h in hist_l), 0.0)
            def pt(i, v):
                return (x0 + ww * i / (len(hist_l) - 1), yy + gh - gh * (v - mn) / max(mx - mn, 1e-6))
            pygame.draw.lines(s, ORO, False, [pt(i, h["mejor_aptitud"]) for i, h in enumerate(hist_l)], 2)
            pygame.draw.lines(s, AZUL, False, [pt(i, h["promedio_aptitud"]) for i, h in enumerate(hist_l)], 2)
            for i, h in enumerate(hist_l):
                if h.get("subio"):
                    xx = pt(i, 0)[0]
                    pygame.draw.line(s, VERDE, (xx, yy), (xx, yy + gh))
            _texto(s, self.f_peq, f"máx {mx:.0f}", ORO, (x0 + 4, yy + 2))
            yy += gh + int(8 * k)

        if app.modo in ("ia", "campeon") and y + alto_max - yy > int(150 * k):
            yy = self._seccion(s, "RED NEURONAL · SENSORES Y SALIDAS", x0, yy, ww)
            pil = app.pilotos
            jj = j if pil.entradas.shape[0] > j else 0
            ent_v = pil.entradas[jj]
            etq = int(92 * k)
            fila_r = int(14 * k)
            for nombre_g, a, b in GRUPOS:
                if yy > y + alto_max - int(70 * k):
                    break
                _texto(s, self.f_peq, nombre_g, TENUE, (x0, yy - 1))
                n = b - a
                cw = min(int(26 * k), (ww - etq) // max(n, 1))
                for i in range(n):
                    v = float(ent_v[a + i])
                    cx = x0 + etq + i * cw
                    pygame.draw.rect(s, (30, 33, 40), (cx, yy, cw - 3, fila_r - 3))
                    h = int(abs(max(-1, min(1, v))) * (cw - 3))
                    pygame.draw.rect(s, _color_valor(v), (cx, yy, h, fila_r - 3))
                yy += fila_r
            yy += int(4 * k)
            sal = pil.salida[jj]
            cw = ww // len(B.NOMBRES_SALIDAS)
            for i, nm in enumerate(B.NOMBRES_SALIDAS):
                v = float(sal[i])
                cx = x0 + i * cw
                hh = int(30 * k)
                pygame.draw.rect(s, (30, 33, 40), (cx + 2, yy, cw - 4, hh))
                lleno = int(abs(v) * hh / 2)
                if v >= 0:
                    pygame.draw.rect(s, _color_valor(v), (cx + 2, yy + hh // 2 - lleno, cw - 4, lleno))
                else:
                    pygame.draw.rect(s, _color_valor(v), (cx + 2, yy + hh // 2, cw - 4, lleno))
                _texto(s, self.f_peq, nm[:5], TENUE, (cx + cw // 2, yy + hh + int(8 * k)), True)
            yy += int(48 * k)
            for capa in pil.ocultas[:-1]:
                if yy > y + alto_max - int(16 * k):
                    break
                v = capa[jj]
                cw = ww / len(v)
                for i, a in enumerate(v):
                    pygame.draw.rect(s, _color_valor(a), (x0 + i * cw, yy, max(1, cw - 1), int(10 * k)))
                yy += int(14 * k)

    def arranque(self, s, ep, j, x, y, interactivo):
        k = self.k
        ar = ep.arranque
        f = ep.f
        w = int(440 * k)
        fila = int(20 * k)
        alto = int(10 * k) + int(26 * k) + len(PASOS) * fila + int(14 * k) + 5 * int(34 * k) + int(64 * k)
        y = max(10, y - alto)
        r = pygame.Rect(x, y, w, alto)
        _tarjeta(s, r)
        x0 = x + int(14 * k)
        yy = self._seccion(s, "ARRANQUE F-15 · LISTA DE COMPROBACIÓN", x0, y + int(10 * k), w - int(28 * k))
        e = int(ar.estado[j])
        parpadeo = int(pygame.time.get_ticks() / 350) % 2 == 0
        for i, (es, en, _) in enumerate(PASOS):
            cy = yy + i * fila + fila // 2
            if i < e:
                pygame.draw.circle(s, VERDE, (x0 + 7, cy), int(7 * k))
                pygame.draw.lines(s, (10, 30, 14), False, [(x0 + 3, cy), (x0 + 6, cy + 3), (x0 + 11, cy - 4)], 2)
                col = TENUE
            elif i == e:
                pygame.draw.circle(s, AMBAR if parpadeo else ORO, (x0 + 7, cy), int(7 * k))
                col = TEXTO
            else:
                pygame.draw.circle(s, APAGADO, (x0 + 7, cy), int(7 * k), 2)
                col = (110, 114, 124)
            _texto(s, self.f_med_b if i == e else self.f_med, f"{i + 1}. {es}", col, (x0 + int(22 * k), cy - int(9 * k)))
            _texto(s, self.f_peq, en, (95, 100, 112), (x0 + w - int(28 * k), cy - int(7 * k)), der=True)
        yy += len(PASOS) * fila + int(10 * k)
        pend = ar.pendiente(f, j)
        rects = []
        bw = (w - int(28 * k) - 2 * int(6 * k)) // 3
        bh = int(28 * k)
        for i, nm in enumerate(INTERRUPTORES):
            cx = x0 + (i % 3) * (bw + int(6 * k))
            cy = yy + (i // 3) * (bh + int(6 * k))
            rr = pygame.Rect(cx, cy, bw, bh)
            on = bool(ar.estado_interruptor(f, j, nm))
            if nm == pend and parpadeo:
                fondo = (120, 84, 10)
                borde = AMBAR
            else:
                fondo = (24, 78, 40) if on else (34, 37, 44)
                borde = VERDE if on else (70, 74, 84)
            sobre = interactivo and rr.collidepoint(pygame.mouse.get_pos())
            pygame.draw.rect(s, fondo + (255,), rr, border_radius=5)
            pygame.draw.rect(s, (255, 255, 255) if sobre else borde, rr, 2, border_radius=5)
            _texto(s, self.f_peq, ETIQUETAS[nm], TEXTO if on or nm == pend else TENUE,
                   (rr.x + int(6 * k), rr.y + int(2 * k)))
            if interactivo:
                _texto(s, self.f_peq, TECLAS[nm], (150, 156, 168), (rr.right - int(5 * k), rr.bottom - int(15 * k)),
                       der=True)
            rects.append((rr, nm))
        yy += 5 * (bh + int(6 * k)) + int(4 * k)
        barras = (("N2 I", f.n2[j, 0], f.encendido[j, 0]), ("N2 D", f.n2[j, 1], f.encendido[j, 1]),
                  ("JFS", f.jfs[j], f.jfs_on[j]), ("CARL", f.canopy[j], f.canopy[j] > 0.99))
        bw2 = (w - int(28 * k)) // 4
        for i, (nm, v, ok) in enumerate(barras):
            cx = x0 + i * bw2
            _texto(s, self.f_peq, f"{nm} {100 * v:3.0f}%", VERDE if ok else TENUE, (cx, yy))
            pygame.draw.rect(s, (30, 33, 40), (cx, yy + int(16 * k), bw2 - int(8 * k), int(9 * k)))
            pygame.draw.rect(s, VERDE if ok else AMBAR,
                             (cx, yy + int(16 * k), int((bw2 - int(8 * k)) * min(1, v)), int(9 * k)))
        yy += int(32 * k)
        if e == 7 and ar.solicitado[j] and not ar.autorizado[j]:
            txt, col = "TORRE: «Eagle 1, espere…»", AMBAR
        elif ar.autorizado[j] and e < VUELO:
            txt, col = "TORRE: «Eagle 1, autorizado a despegar pista 34»", VERDE
        elif pend:
            txt, col = f"Siguiente: {ETIQUETAS[pend]}" + (f"  (tecla {TECLAS[pend]})" if interactivo and pend in TECLAS
                                                        else ""), ORO
        elif e == 8:
            txt, col = "Suelta frenos, postquemador (Shift+W / E) y rota a 150 kt", ORO
        else:
            txt, col = "Esperando sistemas…", TENUE
        _texto(s, self.f_med_b, txt, col, (x0, yy))
        return rects

    def mandos(self, s, ep, j, acc, cx, y):
        k = self.k
        f = ep.f
        g = float(f.entrada["gases"][j])
        thr = f"PQ {int((g - 0.8) / 0.2 * 100)}%" if g > 0.8 else f"MIL {int(g / 0.8 * 100)}%"
        el, al, ti = (float(f.entrada[c][j]) for c in ("elev", "alabeo", "timon"))
        fuego = False
        if acc is not None and "fuego" in acc:
            a = np.atleast_1d(acc["fuego"])
            fuego = bool(a[j if len(a) > j else 0])
        chips = [("PALANCA", f"{el:+.1f} {al:+.1f}", abs(el) > 0.05 or abs(al) > 0.05),
                 ("TIMÓN", f"{ti:+.1f}", abs(ti) > 0.05), ("GASES", thr, g > 0.02),
                 ("PQ", "ON" if f.pq[j] > 0.05 else "", f.pq[j] > 0.05),
                 ("FRENOS", "", f.entrada["freno"][j] > 0.1), ("TREN", "ABAJO" if f.cmd_tren[j] > 0.5 else "ARRIBA",
                                                             f.cmd_tren[j] > 0.5),
                 ("FLAPS", "", f.cmd_flaps[j] > 0.5), ("AEROFR", "", f.cmd_aerofreno[j] > 0.5),
                 ("ARMAS", "", fuego or bool(ep.disparando[j])), ("BENGALA", str(int(ep.bengalas[j])),
                                                                  bool(ep.solto_bengala[j]))]
        cw, ch = int(76 * k), int(36 * k)
        x = cx - len(chips) * cw // 2
        for i, (nm, val, on) in enumerate(chips):
            rr = pygame.Rect(x + i * cw + 2, y, cw - 4, ch)
            pygame.draw.rect(s, ((24, 78, 40, 235) if on else (22, 25, 32, 200)), rr, border_radius=6)
            pygame.draw.rect(s, VERDE if on else (60, 64, 74), rr, 1, border_radius=6)
            _texto(s, self.f_peq, nm, TEXTO if on else TENUE, (rr.centerx, rr.y + int(10 * k)), True)
            if val:
                _texto(s, self.f_peq, val, VERDE if on else TENUE, (rr.centerx, rr.y + int(25 * k)), True)

    def rayos(self, s, pr, ep, j):
        f = ep.f
        vh = f.vel[j].copy()
        vh[1] = 0
        vn = np.linalg.norm(vh) + 1e-3
        ad = vh / vn * np.clip(vn, 60, 300)
        nariz = pr.punto(f.pos[j] + f.R[j] @ np.array([9.0, 0.0, 0.0]))
        for seg, col in ((6, AZUL), (14, (170, 120, 255))):
            p = f.pos[j] + ad * seg
            h = float(superficie(p[0], p[2]))
            q = pr.punto(np.array([p[0], h, p[2]]))
            libre = f.pos[j, 1] - h
            c = ROJO if libre < 150 else (AMBAR if libre < 400 else col)
            if q is None or not (0 <= q[0] < pr.W and 0 <= q[1] < pr.H):
                continue
            if nariz is not None:
                pygame.draw.line(s, c + (120,), nariz, q, 1)
            pygame.draw.circle(s, c, (int(q[0]), int(q[1])), 7, 2)
            _texto(s, self.f_peq, f"{seg}s {libre:.0f} m", c, (q[0] + 10, q[1] - 8))
