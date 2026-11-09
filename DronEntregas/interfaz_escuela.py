import math
import os
import threading
import tkinter as tk
from tkinter import messagebox

from PIL import ImageEnhance, ImageTk

import config as C
import estilo as E
from cerebro import DIRECCIONES, SALIDAS, sensores
from escuela import (CHOQUE, EXITO, NOMBRE_LECCION, TIEMPO, VOLANDO, Entrenador, Paralelo,
                     archivo_mejor, borrar_progreso, resumen_generacion)
from estilo import P
from grabador import BotonGrabar

COLOR = {
    "lider": P["acento"], "activo": P["cian"], "choque": P["rojo"], "exito": P["verde"],
    "tiempo": P["gris"], "grua": "#ff5252", "meta": P["acento"], "edificio": "#3a4558",
}
VELOCIDADES = (1, 2, 4, 8, 16, 32)
ANCHO_VISTA, ALTO_VISTA = 660, 384
ALTO_LADO = 150
ANCHO_PANEL = 392
OSCURO = "#0e1014"


class EscuelaVentana:

    def __init__(self, raiz, ciudad, plan, satelite, vehiculo=C.VEHICULO, continuar=False,
                 al_cerrar=None):
        self.raiz = raiz
        self.ciudad, self.plan, self.satelite = ciudad, plan, satelite
        self.vehiculo = vehiculo
        self.al_cerrar = al_cerrar
        self.pausa = False
        self.turbo = False
        self.vel_idx = 2
        self._acum = 0.0
        self.paralelo = None
        self._hilo = None
        self._esc_dibujado = None
        self._n_hist = -1
        self.cerrada = False
        raiz.title("Escuela de vuelo — el dron aprende con un algoritmo genético")
        raiz.configure(bg=P["fondo"])
        raiz.resizable(False, False)
        self.entrenador = Entrenador(ciudad, plan, vehiculo, continuar=continuar)
        self._construir()
        self._teclas()
        raiz.protocol("WM_DELETE_WINDOW", self.cerrar)
        raiz.after(C.FPS_MS, self._ciclo)

    def _construir(self):
        r = self.raiz
        cab = tk.Frame(r, bg=P["fondo"], height=54)
        cab.pack(fill="x", padx=12)
        cab.pack_propagate(False)
        titulo = tk.Frame(cab, bg=P["fondo"])
        titulo.pack(side="left")
        nombre = C.VEHICULOS[self.vehiculo]["nombre"]
        tk.Label(titulo, text="ESCUELA DE VUELO", bg=P["fondo"], fg=P["texto"],
                 font=(E.SEMI, 15)).pack(anchor="w")
        tk.Label(titulo, text=f"{nombre} · el dron aprende con un algoritmo genético",
                 bg=P["fondo"], fg=P["tenue"], font=E.F_CHICA).pack(anchor="w")
        der = tk.Frame(cab, bg=P["fondo"])
        der.pack(side="right")
        self.grabar = E.estilo_boton_grabar(
            BotonGrabar(der, self.raiz, fuente=E.F_BOTON)).pack(side="right")
        E.Boton(der, "⟲  Reiniciar", self._reiniciar).pack(side="right", padx=(0, 8))
        E.Boton(der, "Guardar", self._guardar, P["verde"], primario=True
                ).pack(side="right", padx=(0, 8))
        self.btn_turbo = E.Boton(der, "Turbo", self._turbo, ancho=7).pack(side="right",
                                                                          padx=(0, 8))
        self.btn_pausa = E.Boton(der, "Pausa", self._pausar, ancho=8).pack(side="right",
                                                                           padx=(0, 8))
        vel = tk.Frame(der, bg=P["borde"], padx=1, pady=1)
        vel.pack(side="right", padx=(0, 8))
        E.Boton(vel, "−", lambda: self._vel(-1)).pack(side="left")
        self.lbl_vel = tk.Label(vel, text="", bg=P["tarjeta"], fg=P["acento"], font=E.F_BOTON,
                                width=4, pady=6)
        self.lbl_vel.pack(side="left")
        E.Boton(vel, "+", lambda: self._vel(1)).pack(side="left")

        cuerpo = tk.Frame(r, bg=P["fondo"])
        cuerpo.pack(fill="both", padx=12, pady=(0, 12))
        izq = tk.Frame(cuerpo, bg=P["fondo"])
        izq.pack(side="left", fill="y")
        t, c = E.tarjeta(izq, "Vista desde arriba", self._chip_escena)
        t.pack(fill="x")
        self.vista = tk.Canvas(c, width=ANCHO_VISTA, height=ALTO_VISTA, bg=P["tarjeta2"],
                               highlightthickness=0)
        self.vista.pack()
        t, c = E.tarjeta(izq, "Vista de lado · distancia hacia la meta contra altura")
        t.pack(fill="x", pady=(8, 0))
        self.lado = tk.Canvas(c, width=ANCHO_VISTA, height=ALTO_LADO, bg=P["tarjeta"],
                              highlightthickness=0)
        self.lado.pack()
        ley = tk.Canvas(izq, width=ANCHO_VISTA + 26, height=20, bg=P["fondo"],
                        highlightthickness=0)
        ley.pack(anchor="w", pady=(6, 0))
        x = 2
        for col, txt in ((COLOR["lider"], "líder (mejor de la generación anterior)"),
                         (COLOR["activo"], "volando"), (COLOR["exito"], "aprobó"),
                         (COLOR["choque"], "chocó"), (COLOR["tiempo"], "sin tiempo"),
                         (COLOR["grua"], "grúa que el mapa no conoce")):
            ley.create_oval(x, 6, x + 9, 15, fill=col, outline="")
            t_ = ley.create_text(x + 14, 10, text=txt, anchor="w", fill=P["tenue"],
                                 font=E.F_CHICA)
            x = ley.bbox(t_)[2] + 14

        der = tk.Frame(cuerpo, bg=P["fondo"], width=ANCHO_PANEL)
        der.pack(side="left", fill="y", padx=(10, 0))
        t, c = E.tarjeta(der, "Plan de estudios")
        t.pack(fill="x")
        self.curso = tk.Canvas(c, width=ANCHO_PANEL - 26, height=58, bg=P["tarjeta"],
                               highlightthickness=0)
        self.curso.pack()
        self.mosaico = tk.Canvas(der, width=ANCHO_PANEL, height=96, bg=P["fondo"],
                                 highlightthickness=0)
        self.mosaico.pack(pady=(8, 0))
        t, c = E.tarjeta(der, "Récord · cerebro guardado")
        t.pack(fill="x", pady=(8, 0))
        self.lbl_record = tk.Label(c, text="", bg=P["tarjeta"], fg=P["texto"], font=E.F_CHICA,
                                   justify="left", anchor="w", wraplength=ANCHO_PANEL - 30)
        self.lbl_record.pack(fill="x")
        t, c = E.tarjeta(der, "Aptitud por generación", self._leyenda_grafica)
        t.pack(fill="x", pady=(8, 0))
        self.grafica = tk.Canvas(c, width=ANCHO_PANEL - 26, height=104, bg=P["tarjeta"],
                                 highlightthickness=0)
        self.grafica.pack()
        t, c = E.tarjeta(der, "Lo que siente y decide el líder")
        t.pack(fill="x", pady=(8, 0))
        self.mente = tk.Canvas(c, width=ANCHO_PANEL - 26, height=118, bg=P["tarjeta"],
                               highlightthickness=0)
        self.mente.pack()
        tk.Label(der, text="Espacio pausa · +/− velocidad · T turbo (todos los núcleos) · "
                           "G guardar · N reiniciar · Esc cerrar\nEl avance se guarda solo cada "
                           "generación y al cerrar; al volver a abrir continúa donde se "
                           "quedó. El simulador usa el mejor cerebro con «IA aprendida».", bg=P["fondo"], fg=P["sutil"],
                 font=(E.FAMILIA, 7), justify="left").pack(anchor="w", pady=(6, 0))

    def _chip_escena(self, padre):
        self.lbl_escena = tk.Label(padre, text="", bg=P["tarjeta"], fg=P["acento"],
                                   font=(E.SEMI, 9))
        return self.lbl_escena

    @staticmethod
    def _leyenda_grafica(padre):
        f = tk.Frame(padre, bg=P["tarjeta"])
        for col, txt in ((P["acento"], "mejor"), (P["azul"], "promedio")):
            tk.Label(f, text="━", bg=P["tarjeta"], fg=col, font=E.F_CHICA).pack(side="left")
            tk.Label(f, text=txt, bg=P["tarjeta"], fg=P["tenue"], font=E.F_CHICA).pack(
                side="left", padx=(2, 8))
        return f

    def _teclas(self):
        r = self.raiz
        r.bind("<space>", lambda e: self._pausar())
        for k in ("<t>", "<T>"):
            r.bind(k, lambda e: self._turbo())
        for k in ("<n>", "<N>"):
            r.bind(k, lambda e: self._reiniciar())
        for k in ("<g>", "<G>"):
            r.bind(k, lambda e: self._guardar())
        for k in ("<plus>", "<KP_Add>"):
            r.bind(k, lambda e: self._vel(1))
        for k in ("<minus>", "<KP_Subtract>"):
            r.bind(k, lambda e: self._vel(-1))
        r.bind("<Escape>", lambda e: self.cerrar())

    def _pausar(self):
        self.pausa = not self.pausa
        self.btn_pausa.texto("Continuar" if self.pausa else "Pausa")

    def _vel(self, d):
        self.vel_idx = max(0, min(len(VELOCIDADES) - 1, self.vel_idx + d))

    def _turbo(self):
        self.turbo = not self.turbo
        self.btn_turbo.texto("Animar" if self.turbo else "Turbo")
        if self.turbo and self.paralelo is None:
            self.lbl_escena.configure(text="Preparando los núcleos del procesador…")
            self.raiz.update_idletasks()
            self.paralelo = Paralelo(self.ciudad, self.vehiculo)

    def _reiniciar(self):
        if self._hilo is not None:
            return
        pausa, self.pausa = self.pausa, True
        ok = messagebox.askyesno(
            "Reiniciar desde cero",
            "Se borrará el avance y el cerebro guardado de este vehículo, y la escuela "
            "empezará otra vez en la generación 1 con drones de cerebro al azar.\n\n"
            "¿Continuar?", parent=self.raiz)
        self.pausa = pausa
        if not ok:
            return
        if os.path.exists(archivo_mejor(self.vehiculo)):
            os.remove(archivo_mejor(self.vehiculo))
        borrar_progreso(self.vehiculo)
        self.entrenador = Entrenador(self.ciudad, self.plan, self.vehiculo)
        self._esc_dibujado = None
        self._n_hist = -1
        print("\n=== Reinicio: la escuela empieza desde cero ===\n", flush=True)

    def _guardar_progreso(self):
        try:
            self.entrenador.guardar_progreso()
        except OSError as err:
            messagebox.showerror("Guardar", f"No se pudo guardar el avance:\n{err}",
                                 parent=self.raiz)
            return False
        return True

    def _guardar(self):
        if self._guardar_progreso():
            n = self.entrenador.num
            titulo = "Escuela de vuelo — el dron aprende con un algoritmo genético"
            self.raiz.title(f"✔ Avance guardado en la generación {n} — al volver a abrir "
                            "continúa desde aquí")
            self.raiz.after(3000, lambda: self.cerrada or self.raiz.title(titulo))
            print(f"Avance guardado (generación {n})", flush=True)

    def cerrar(self):
        if self.cerrada:
            return
        self.cerrada = True
        self._guardar_progreso()
        self.grabar.cerrar()
        if self.paralelo is not None:
            self.paralelo.cerrar()
        self.raiz.destroy()
        if self.al_cerrar:
            self.al_cerrar()

    def _preparar_escena(self):
        esc = self.entrenador.generacion.escenario
        self._esc_dibujado = esc
        xs = [esc.inicio[0], esc.meta[0]] + ([*esc.ruta.x] if esc.ruta else [])
        ys = [esc.inicio[1], esc.meta[1]] + ([*esc.ruta.y] if esc.ruta else [])
        cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
        w = max(max(xs) - min(xs) + 120, 160)
        h = max(max(ys) - min(ys) + 120, 100)
        self.esc_v = min(ANCHO_VISTA / w, ALTO_VISTA / h)
        self.x0 = cx - ANCHO_VISTA / 2 / self.esc_v
        self.y0 = cy - ALTO_VISTA / 2 / self.esc_v
        cv = self.vista
        cv.delete("all")
        mpp = self.ciudad.zona.m_por_px
        caja = (round(self.x0 / mpp), round(self.y0 / mpp),
                round((self.x0 + ANCHO_VISTA / self.esc_v) / mpp),
                round((self.y0 + ALTO_VISTA / self.esc_v) / mpp))
        img = self.satelite.crop(caja).resize((ANCHO_VISTA, ALTO_VISTA)).convert("RGB")
        img = ImageEnhance.Brightness(ImageEnhance.Color(img).enhance(0.7)).enhance(0.72)
        self._foto = ImageTk.PhotoImage(img)
        cv.create_image(0, 0, anchor="nw", image=self._foto)
        for e in self.ciudad.edificios_cerca(cx, cy, max(w, h) / 2 + 20):
            pts = [v for p in e.pts for v in self.v(*p)]
            alto = e.h >= 40
            cv.create_polygon(*pts, fill="#d32f2f" if alto else "", stipple="gray25",
                              outline="#ff8a80" if alto else "#8796aa")
            if e is esc.pad:
                cv.create_polygon(*pts, fill="", outline=COLOR["meta"], width=2)
        for z in self.ciudad.prohibidas:
            if z.distancia(cx, cy) < max(w, h):
                cv.create_polygon(*[v for p in z.anillo() for v in self.v(*p)], fill="#b71c1c",
                                  stipple="gray12", outline="#ff5252", width=2)
        for l in self.ciudad.lineas:
            cv.create_line(*self.v(l.x0, l.y0), *self.v(l.x1, l.y1), fill="#000000", width=3)
            cv.create_line(*self.v(l.x0, l.y0), *self.v(l.x1, l.y1), fill="#ffd23f", dash=(5, 3))
        if esc.ruta:
            pts = [v for p in zip(esc.ruta.x, esc.ruta.y) for v in self.v(*p)]
            cv.create_line(*pts, fill=OSCURO, width=5)
            cv.create_line(*pts, fill=P["cian"], dash=(6, 4), width=2)
        for ox, oy, r, hh in esc.obstaculos:
            sx, sy = self.v(ox, oy)
            rr = max(4, r * self.esc_v)
            cv.create_oval(sx - rr, sy - rr, sx + rr, sy + rr, fill=COLOR["grua"], outline="#fff",
                           width=2)
            E.chip(cv, sx, sy - rr - 6, f"grúa {hh:.0f} m", "#ff8a80", "s", (E.SEMI, 8))
        mx, my = self.v(esc.meta[0], esc.meta[1])
        cv.create_oval(mx - 13, my - 13, mx + 13, my + 13, outline=OSCURO, width=4)
        cv.create_oval(mx - 13, my - 13, mx + 13, my + 13, outline=COLOR["meta"], width=2)
        cv.create_text(mx, my, text="★", fill=COLOR["meta"], font=(E.SEMI, 12))
        sx, sy = self.v(esc.inicio[0], esc.inicio[1])
        cv.create_oval(sx - 6, sy - 6, sx + 6, sy + 6, outline="#fff", width=2)
        E.chip(cv, sx, sy + 10, "salida", P["texto"], "n", (E.SEMI, 7))
        sb = 50 * self.esc_v
        cv.create_rectangle(10, ALTO_VISTA - 28, 24 + sb, ALTO_VISTA - 8, fill=OSCURO, outline="")
        cv.create_line(17, ALTO_VISTA - 13, 17 + sb, ALTO_VISTA - 13, fill="#fff", width=2)
        cv.create_text(17 + sb / 2, ALTO_VISTA - 21, text="50 m", fill="#fff",
                       font=(E.FAMILIA, 7))
        self._preparar_lado(esc)

    def v(self, x, y):
        return (x - self.x0) * self.esc_v, (y - self.y0) * self.esc_v

    def _preparar_lado(self, esc):
        cv = self.lado
        cv.delete("all")
        if esc.ruta:
            pts = list(zip(esc.ruta.x, esc.ruta.y))
        else:
            pts = [(esc.inicio[0] + (esc.meta[0] - esc.inicio[0]) * k / 100,
                    esc.inicio[1] + (esc.meta[1] - esc.inicio[1]) * k / 100) for k in range(101)]
        self._linea_lado = pts
        largo = sum(math.dist(a, b) for a, b in zip(pts, pts[1:]))
        self._largo_lado = max(largo, 40.0)
        self._h_lado = max(70.0, esc.meta[2] + 30, esc.inicio[2] + 30,
                           max((o[3] for o in esc.obstaculos), default=0) + 10)
        for hh in range(0, int(self._h_lado) + 1, 20):
            y = self.l(0, hh)[1]
            cv.create_line(30, y, ANCHO_VISTA, y, fill=P["rejilla"])
            cv.create_text(24, y, text=f"{hh}", anchor="e", fill=P["sutil"], font=(E.FAMILIA, 7))
        s, prev = 0.0, pts[0]
        poli = [self.l(-10, 0)]
        for p in pts:
            s += math.dist(prev, p)
            prev = p
            poli += [self.l(s, self.plan.mapa.altura_sensor(*p))]
        poli += [self.l(self._largo_lado + 10, 0)]
        cv.create_polygon(*[v for p in poli for v in p], fill=COLOR["edificio"], outline="")
        for ox, oy, r, hh in esc.obstaculos:
            sx = self._s_de(ox, oy)
            cv.create_rectangle(*self.l(sx - r, 0), *self.l(sx + r, hh), fill=COLOR["grua"],
                                outline="")
        cv.create_text(*self.l(self._s_de(*esc.meta[:2]), esc.meta[2] + 4), text="★",
                       fill=COLOR["meta"], font=(E.SEMI, 12))
        cv.create_line(30, self.l(0, 0)[1], ANCHO_VISTA, self.l(0, 0)[1], fill=P["sutil"])
        cv.create_text(4, 4, text="m", anchor="nw", fill=P["sutil"], font=(E.FAMILIA, 7))

    def l(self, s, z):
        x = 36 + (ANCHO_VISTA - 56) * s / self._largo_lado
        y = ALTO_LADO - 10 - (ALTO_LADO - 22) * z / self._h_lado
        return x, y

    def _s_de(self, x, y):
        mejor, mejor_d, s, prev = 0.0, float("inf"), 0.0, self._linea_lado[0]
        for p in self._linea_lado:
            s += math.dist(prev, p)
            prev = p
            d = (p[0] - x) ** 2 + (p[1] - y) ** 2
            if d < mejor_d:
                mejor, mejor_d = s, d
        return mejor

    def _color(self, a):
        return {VOLANDO: COLOR["activo"], CHOQUE: COLOR["choque"], EXITO: COLOR["exito"],
                TIEMPO: COLOR["tiempo"]}[a.estado]

    def _dibujar_drones(self):
        gen = self.entrenador.generacion
        cv, cl = self.vista, self.lado
        cv.delete("dron")
        cl.delete("dron")
        for par, k, (bx, by, bz) in gen.entorno.aves.todas():
            sx, sy = self.v(bx, by)
            cv.create_oval(sx - 2, sy - 2, sx + 2, sy + 2, fill="#e6ddd6", outline="", tags="dron")
        lider = gen.alumnos[0]
        if len(lider.estela) > 1:
            pts = [v for p in lider.estela for v in self.v(p[0], p[1])]
            cv.create_line(*pts, fill=OSCURO, width=4, tags="dron")
            cv.create_line(*pts, fill=COLOR["lider"], width=2, tags="dron")
            cl.create_line(*[v for p in lider.estela for v in self.l(self._s_de(p[0], p[1]), p[2])],
                           fill=COLOR["lider"], width=2, tags="dron")
        for a in reversed(gen.alumnos):
            if a.dron is None:
                continue
            x, y, z = a.dron.pos
            sx, sy = self.v(x, y)
            es_lider = a is lider
            col = COLOR["lider"] if es_lider else self._color(a)
            r = 6 if es_lider else 3.5
            lx, ly = self.l(self._s_de(x, y), z)
            for c, (px, py) in ((cv, (sx, sy)), (cl, (lx, ly))):
                if es_lider:
                    c.create_oval(px - 11, py - 11, px + 11, py + 11, fill=col, outline="",
                                  stipple="gray25", tags="dron")
                c.create_oval(px - r, py - r, px + r, py + r, fill=col,
                              outline="#ffffff" if es_lider else OSCURO, tags="dron")
        cv.tag_raise("dron")

    def _dibujar_mente(self):
        cv = self.mente
        cv.delete("all")
        gen = self.entrenador.generacion
        a = gen.alumnos[0]
        if a.dron is None:
            return
        d = a.dron
        meta, aterrizar = a.objetivo()
        x, _ = sensores(d.pos, d.vel, d.pos, meta, aterrizar, gen.entorno, d.viento_est)
        cx, cy, R = 58, 62, 48
        for rr in (R, R * 0.66, R * 0.33):
            cv.create_oval(cx - rr, cy - rr, cx + rr, cy + rr, outline=P["rejilla"])
        for i, ang in enumerate(DIRECCIONES):
            prox = x[12 + i]
            dx, dy = math.sin(ang), -math.cos(ang)
            cv.create_line(cx, cy, cx + dx * R, cy + dy * R, fill=P["rejilla"])
            if prox > 0:
                rr = R * (1 - prox)
                cv.create_line(cx + dx * rr, cy + dy * rr, cx + dx * R, cy + dy * R,
                               fill=P["rojo"], width=5)
        cv.create_text(cx, cy - R - 6, text="meta ▲", fill=COLOR["meta"], font=(E.SEMI, 7))
        cv.create_oval(cx - 5, cy - 5, cx + 5, cy + 5, fill=COLOR["lider"], outline="")
        if x[24]:
            bx, by = x[21], x[22]
            cv.create_oval(cx + by * R - 3, cy - bx * R - 3, cx + by * R + 3, cy - bx * R + 3,
                           fill="#e6ddd6", outline="")
        w = int(cv["width"])
        x0, x1 = 196, w - 4
        mid = (x0 + x1) / 2
        cv.create_text(126, 6, anchor="nw", fill=P["sutil"], font=(E.SEMI, 7),
                       text="DECISIÓN (−1 … +1)" + ("  ·  ORDEN: ATERRIZAR" if aterrizar else ""))
        for k, (nombre, val) in enumerate(zip(SALIDAS, a.cerebro.salida)):
            yy = 34 + k * 24
            cv.create_text(126, yy, anchor="w", text=nombre, fill=P["texto"], font=E.F_CHICA)
            cv.create_rectangle(x0, yy - 5, x1, yy + 5, fill=P["rejilla"], outline="")
            col = P["cian"] if val >= 0 else P["morado"]
            cv.create_rectangle(mid, yy - 5, mid + (x1 - mid) * val, yy + 5, fill=col, outline="")
            cv.create_line(mid, yy - 8, mid, yy + 8, fill=P["sutil"])
        dz = meta[2] - d.pos[2]
        dist = math.hypot(meta[0] - d.pos[0], meta[1] - d.pos[1])
        cv.create_text(126, 108, anchor="w", fill=P["tenue"], font=E.F_CHICA,
                       text=f"meta a {dist:.1f} m · {dz:+.1f} m de altura · alt {d.pos[2]:.1f} m")

    def _dibujar_curso(self):
        e = self.entrenador
        cv = self.curso
        cv.delete("all")
        n = len(C.CURSO)
        w = int(cv["width"])
        paso = (w - 40) / (n - 1)
        for i, lec in enumerate(C.CURSO, 1):
            x = 20 + (i - 1) * paso
            hecho, actual = i < e.nivel, i == e.nivel
            if i < n:
                cv.create_line(x, 16, x + paso, 16, width=3,
                               fill=P["verde"] if i < e.nivel else P["rejilla"])
            col = P["verde"] if hecho else (P["acento"] if actual else P["tarjeta2"])
            if actual:
                cv.create_oval(x - 15, 1, x + 15, 31, fill=E.mezclar(P["acento"], P["tarjeta"], 0.75),
                               outline="")
            cv.create_oval(x - 11, 5, x + 11, 27, fill=col, outline=P["borde"] if not (
                hecho or actual) else col)
            cv.create_text(x, 16, text="✓" if hecho else str(i), font=(E.SEMI, 9),
                           fill=OSCURO if hecho or actual else P["tenue"])
            cv.create_text(min(max(x, 34), w - 34), 34, text=NOMBRE_LECCION[lec],
                           font=(E.SEMI, 7), width=paso - 6, justify="center", anchor="n",
                           fill=P["texto"] if actual else P["tenue"])

    def _actualizar_panel(self):
        e = self.entrenador
        gen = e.generacion
        self._dibujar_curso()
        c = gen.conteo()
        total = max(1, len(gen.alumnos))
        mejor = e.historial[-1]["mejor"] if e.historial else None
        E.indicadores(self.mosaico, [
            ("Generación", f"{e.num}", P["acento"], None),
            ("Volando", f"{c[VOLANDO]}", P["cian"], c[VOLANDO] / total),
            ("Aprobaron", f"{c[EXITO]}", P["verde"], c[EXITO] / total),
            ("Chocaron", f"{c[CHOQUE]}", P["rojo"], c[CHOQUE] / total),
            ("Sin tiempo", f"{c[TIEMPO]}", P["gris"], c[TIEMPO] / total),
            ("Mejor aptitud", "—" if mejor is None else f"{mejor:,.0f}".replace(",", " "),
             P["morado"], None),
        ], 3, ANCHO_PANEL, 45)
        r = e.record
        if r:
            txt = (f"Generación {r['generacion']} · nivel {r['nivel']} ({r['leccion']}) · "
                   f"aprobó {r['aprobados']}/{r['escenarios']} escenarios"
                   + ("  ·  ¡GRADUADO!" if r["graduado"] else "") + "\n"
                   + "\n".join(r["resultados"][-4:]))
        else:
            txt = "Todavía ninguno."
        if e.extinciones:
            txt += f"\nExtinciones: {e.extinciones}"
        self.lbl_record.configure(text=txt)
        self.lbl_vel.configure(text="turbo" if self.turbo else f"x{VELOCIDADES[self.vel_idx]}")
        if not self.turbo and not gen.terminada:
            self.lbl_escena.configure(
                text=f"{gen.escenario.nombre} · {gen.i_esc + 1}/{len(gen.escenarios)} · "
                     f"t {gen.t:4.1f} s")
        elif gen.terminada and not self.turbo:
            self.lbl_escena.configure(text="evaluando…")

    def _dibujar_grafica(self):
        hist = self.entrenador.historial[-150:]
        E.grafica(self.grafica, hist)
        cv = self.grafica
        if len(hist) >= 2:
            w, h = int(cv["width"]), int(cv["height"])
            for i, s in enumerate(hist):
                if s["subio"]:
                    x = 40 + i * (w - 50) / (len(hist) - 1)
                    cv.create_line(x, 10, x, h - 22, fill=P["verde"], dash=(2, 2))

    def _fin_generacion(self):
        s = self.entrenador.cerrar_generacion()
        print(resumen_generacion(s), flush=True)
        self._esc_dibujado = None
        self._dibujar_grafica()

    def _ciclo(self):
        if self.cerrada:
            return
        try:
            e = self.entrenador
            if self.turbo:
                if self._hilo is None and not self.pausa:
                    gen = e.generacion
                    self._hilo = threading.Thread(target=self.paralelo.evaluar, args=(gen,),
                                                  daemon=True)
                    self._hilo.start()
                    self.lbl_escena.configure(text=f"Turbo: evaluando la generación {e.num} en "
                                                   f"{self.paralelo.n} núcleos…")
                elif self._hilo is not None and not self._hilo.is_alive():
                    self._hilo = None
                    self._fin_generacion()
            elif self._hilo is None and not self.pausa:
                gen = e.generacion
                self._acum += VELOCIDADES[self.vel_idx] * C.FPS_MS / 1000
                pasos = 0
                while self._acum >= C.DT_ESCUELA and pasos < 400 and not gen.terminada:
                    i = gen.i_esc
                    gen.paso()
                    self._acum -= C.DT_ESCUELA
                    pasos += 1
                    if gen.i_esc != i:
                        break
                if gen.terminada:
                    self._fin_generacion()
            elif self._hilo is not None and not self._hilo.is_alive():
                self._hilo = None
                self._fin_generacion()
            gen = e.generacion
            if not self.turbo and self._hilo is None and not gen.terminada:
                if self._esc_dibujado is not gen.escenario:
                    self._preparar_escena()
                self._dibujar_drones()
                self._dibujar_mente()
            if self._n_hist != len(e.historial):
                self._n_hist = len(e.historial)
                self._dibujar_grafica()
            self._actualizar_panel()
        finally:
            if not self.cerrada:
                self.raiz.after(C.FPS_MS, self._ciclo)
