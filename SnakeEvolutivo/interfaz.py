import time
import tkinter as tk
from tkinter import messagebox

import numpy as np

import cerebro as B
import config as C
import tema as T
from evolucion import cargar_campeon
from grabador import BotonGrabar
from niveles import NIVELES, nivel as obtener_nivel
from simulacion import CHOCO_CUERPO, CHOCO_MURO, HAMBRE, MOTIVOS, TIEMPO, Partida
from tema import (AZUL, BORDE, FAMILIA, FONDO, GRIS, MONO, MORADO, NARANJA, ORO, REJILLA, ROJO,
                  SEMI, SUTIL, TARJETA, TARJETA2, TENUE, TEXTO, VERDE, mezcla)

CABEZA = "#a6ffc9"
COLA = "#14784a"
LADO = 620
ANCHO_PANEL = 364
ANCHO_RED = 330
COLOR_MOTIVO = {CHOCO_MURO: ROJO, CHOCO_CUERPO: MORADO, HAMBRE: NARANJA, TIEMPO: GRIS}


class Aplicacion:
    def __init__(self, entrenador, demo=False, turbo=False):
        self.e = entrenador
        self.raiz = tk.Tk()
        self.raiz.title("Snake evolutivo — serpientes que aprenden por generaciones")
        self.raiz.configure(bg=FONDO)
        self.raiz.resizable(False, False)
        self.demo = demo
        self.turbo = turbo and not demo
        self.pausa = False
        self.i_vel = 0
        self.acum = 0.0
        self.espera = 0.0
        self.t_previo = time.perf_counter()
        self.t_panel = 0.0
        self.turbo_t0 = time.perf_counter()
        self.turbo_gens = 0
        self.seguido = 0
        self.aviso = ("", 0.0)
        self.registro = []
        self.nivel_demo = entrenador.nivel
        self.intentos_demo = 0
        self.nivel_dibujado = None
        self.clave_aristas = None
        self._construir()
        self._teclas()
        self._nueva_partida()
        self.raiz.after(C.CUADRO_MS, self._ciclo)

    def _canvas(self, padre, ancho, alto, fondo=TARJETA, pady=(0, 8)):
        cv = tk.Canvas(padre, width=ancho, height=alto, bg=fondo, highlightthickness=1,
                       highlightbackground=BORDE)
        cv.pack(anchor="w", pady=pady)
        return cv

    def _construir(self):
        izquierda = tk.Frame(self.raiz, bg=FONDO)
        izquierda.pack(side="left", anchor="n", padx=(16, 8), pady=12)
        self.cabecera = tk.Canvas(izquierda, width=LADO + 2, height=60, bg=FONDO,
                                  highlightthickness=0)
        self.cabecera.pack(anchor="w", pady=(0, 6))
        self.tablero = self._canvas(izquierda, LADO, LADO, "#090b0f", 0)

        centro = tk.Frame(self.raiz, bg=FONDO)
        centro.pack(side="left", anchor="n", padx=8, pady=12)
        self.titulo = tk.Canvas(centro, width=ANCHO_PANEL + 2, height=60, bg=FONDO,
                                highlightthickness=0)
        self.titulo.pack(anchor="w", pady=(0, 6))
        self._dibujar_titulo()
        self.c_gen = self._canvas(centro, ANCHO_PANEL, 178)
        self.c_graf = self._canvas(centro, ANCHO_PANEL, 162)
        self.c_pobl = self._canvas(centro, ANCHO_PANEL, 150)
        self._controles(centro)

        derecha = tk.Frame(self.raiz, bg=FONDO)
        derecha.pack(side="left", anchor="n", padx=(8, 16), pady=12)
        self.c_red = self._canvas(derecha, ANCHO_RED, 478)
        self.c_tele = self._canvas(derecha, ANCHO_RED, 196, pady=0)

    def _controles(self, padre):
        fila = tk.Frame(padre, bg=FONDO)
        fila.pack(anchor="w", fill="x")
        self.btn_pausa = T.Boton(fila, "Pausa", self.alternar_pausa, ancho=7).pack(side="left")
        self.btn_turbo = T.Boton(fila, "Turbo", self.alternar_turbo, ancho=7).pack(
            side="left", padx=(6, 0))
        vel = tk.Frame(fila, bg=BORDE, padx=1, pady=1)
        vel.pack(side="right")
        T.Boton(vel, "−", lambda: self.cambiar_vel(-1)).pack(side="left")
        self.lbl_vel = tk.Label(vel, text="x1", width=4, bg=TARJETA, fg=ORO, font=(SEMI, 10),
                                pady=6)
        self.lbl_vel.pack(side="left")
        T.Boton(vel, "+", lambda: self.cambiar_vel(1)).pack(side="left")

        fila = tk.Frame(padre, bg=FONDO)
        fila.pack(anchor="w", fill="x", pady=(6, 0))
        self.btn_campeona = T.Boton(fila, "Ver campeona", self.alternar_demo, ORO, True,
                                    ancho=15).pack(side="left")
        T.Boton(fila, "⟲ Reiniciar", self.reiniciar).pack(side="left", padx=(6, 0))
        T.Boton(fila, "Guardar", self.guardar, VERDE, True).pack(side="left", padx=(6, 0))
        self.grabar = T.estilo_grabar(BotonGrabar(fila, self.raiz, self.avisar, (SEMI, 10)))
        self.grabar.pack(side="right")

        ayuda = ("Espacio pausa · T turbo · +/− velocidad · C campeona\n"
                 "←/→ nivel de la campeona · G guardar · N reiniciar · Esc salir")
        tk.Label(padre, text=ayuda, bg=FONDO, fg=SUTIL, font=(FAMILIA, 8),
                 justify="left").pack(anchor="w", pady=(8, 0))

    def _teclas(self):
        r = self.raiz
        r.bind("<space>", lambda _: self.alternar_pausa())
        for tecla in ("t", "T"):
            r.bind(tecla, lambda _: self.alternar_turbo())
        for tecla in ("c", "C"):
            r.bind(tecla, lambda _: self.alternar_demo())
        for tecla in ("n", "N"):
            r.bind(tecla, lambda _: self.reiniciar())
        for tecla in ("g", "G"):
            r.bind(tecla, lambda _: self.guardar())
        for tecla in ("<plus>", "<KP_Add>", "="):
            r.bind(tecla, lambda _: self.cambiar_vel(1))
        for tecla in ("<minus>", "<KP_Subtract>"):
            r.bind(tecla, lambda _: self.cambiar_vel(-1))
        r.bind("<Left>", lambda _: self.cambiar_nivel_demo(-1))
        r.bind("<Right>", lambda _: self.cambiar_nivel_demo(1))
        r.bind("<Escape>", lambda _: self.salir())
        r.protocol("WM_DELETE_WINDOW", self.salir)

    def avisar(self, texto, *_):
        self.aviso = (texto, time.perf_counter())

    def guardar(self):
        try:
            self.e._guardar()
        except OSError as err:
            self.avisar(f"No se pudo guardar: {err}")
            return
        self.avisar(f"Avance guardado en la generación {self.e.generacion}: al reabrir continúa aquí")

    def salir(self):
        try:
            self.e._guardar()
        except OSError:
            pass
        self.grabar.cerrar()
        self.raiz.destroy()

    def alternar_pausa(self):
        self.pausa = not self.pausa

    def alternar_turbo(self):
        if self.demo:
            return
        self.turbo = not self.turbo
        self.turbo_t0 = time.perf_counter()
        self.turbo_gens = 0
        self.acum = 0.0

    def cambiar_vel(self, delta):
        self.i_vel = max(0, min(len(C.VELOCIDADES) - 1, self.i_vel + delta))

    def alternar_demo(self):
        self.demo = not self.demo
        self.turbo = False
        self.nivel_demo = self.e.nivel
        self.intentos_demo = 0
        self._nueva_partida()

    def cambiar_nivel_demo(self, delta):
        if not self.demo:
            return
        self.nivel_demo = max(1, min(len(NIVELES), self.nivel_demo + delta))
        self.intentos_demo = 0
        self._nueva_partida()

    def reiniciar(self):
        pausa_previa, self.pausa = self.pausa, True
        ok = messagebox.askyesno("Reiniciar desde cero",
                                 "Se borrará todo lo aprendido (estado, campeonas e historial) "
                                 "y la evolución empezará otra vez en la generación 1.\n\n¿Continuar?",
                                 parent=self.raiz)
        self.pausa = pausa_previa
        if ok:
            self.e.reiniciar()
            self.registro.clear()
            self.demo = False
            self._nueva_partida()
            self.avisar("Evolución reiniciada desde cero")

    def _nueva_partida(self):
        if self.demo:
            campeon = cargar_campeon(self.nivel_demo, self.e.dir)
            pesos = campeon[0] if campeon else self.e.theta
            self.info_campeon = campeon[1] if campeon else None
            semilla = int(np.random.default_rng().integers(1 << 31))
            self.partida = Partida(obtener_nivel(self.nivel_demo), pesos[None, :], semilla)
            self.intentos_demo += 1
        else:
            self.partida = self.e.nueva_partida()
        self.seguido = self.partida.lider()
        self.clave_aristas = None
        self.acum = 0.0
        if self.partida.nivel.numero != self.nivel_dibujado:
            self._dibujar_fijo()

    def _cerrar_partida(self):
        if not self.demo:
            r = self.e.terminar(self.partida)
            self.registro = (self.registro + [r])[-14:]
            self.turbo_gens += 1
            print(f"gen {r['generacion']:5d} · nivel {r['nivel']} {r['nombre']:<12} · "
                  f"mejor {r['mejor_frutas']:3d} · promedio {r['promedio_frutas']:6.2f} · "
                  f"racha {r['racha']}/{C.RACHA_PARA_SUBIR}", flush=True)
            if r["subio"]:
                self.avisar(f"¡{r['nombre']} superado! Siguiente nivel: {self.e.nivel_actual.nombre}")
        self._nueva_partida()

    def _ciclo(self):
        ahora = time.perf_counter()
        dt = min(ahora - self.t_previo, 0.1)
        self.t_previo = ahora
        try:
            if not self.pausa:
                if self.turbo:
                    self._avanzar_turbo()
                else:
                    self._avanzar(dt)
            self._dibujar_tablero()
            if ahora - self.t_panel > 0.1:
                self.t_panel = ahora
                self._dibujar_paneles()
            self.raiz.after(C.CUADRO_MS, self._ciclo)
        except tk.TclError:
            pass

    def _avanzar(self, dt):
        p = self.partida
        if p.terminada:
            self.espera -= dt
            if self.espera <= 0:
                self._cerrar_partida()
            return
        self.acum = min(self.acum + dt * C.PASOS_POR_SEGUNDO * C.VELOCIDADES[self.i_vel], 400)
        pasos = int(self.acum)
        self.acum -= pasos
        for _ in range(pasos):
            p.paso()
            if p.terminada:
                self.espera = 1.5 if self.demo else 0.6
                break
        self.seguido = p.lider(self.seguido)

    def _avanzar_turbo(self):
        limite = time.perf_counter() + C.PRESUPUESTO_TURBO
        while time.perf_counter() < limite:
            self.partida.paso()
            if self.partida.terminada:
                self._cerrar_partida()
        self.seguido = self.partida.lider(self.seguido)

    def _geometria(self, nivel):
        celda = LADO // max(nivel.alto, nivel.ancho)
        return celda, (LADO - celda * nivel.ancho) // 2, (LADO - celda * nivel.alto) // 2

    def _celda(self, fila, col, margen=0.0):
        c = self.celda
        x, y = self.ox + col * c, self.oy + fila * c
        return x + margen, y + margen, x + c - margen, y + c - margen

    def _dibujar_fijo(self):
        nv = self.partida.nivel
        self.celda, self.ox, self.oy = self._geometria(nv)
        cv = self.tablero
        cv.delete("all")
        self.foto_tablero = T.tablero(nv.muros, LADO, self.celda, self.ox, self.oy, nv.numero)
        cv.create_image(1, 1, anchor="nw", image=self.foto_tablero)
        self.nivel_dibujado = nv.numero

    def _centro(self, fila, col):
        return self.ox + (col + 0.5) * self.celda + 1, self.oy + (fila + 0.5) * self.celda + 1

    def _dibujar_fruta(self, fila, col):
        cv, c = self.tablero, self.celda
        cx, cy = self._centro(fila, col)
        r = c * 0.33
        pulso = 0.5 + 0.5 * np.sin(time.perf_counter() * 4)
        g = r * (1.55 + 0.15 * pulso)
        cv.create_oval(cx - g, cy - g, cx + g, cy + g, fill="#ff4d5e", outline="",
                       stipple="gray12", tags="dyn")
        cv.create_oval(cx - r * 0.9, cy + r * 0.7, cx + r * 0.9, cy + r * 1.15, fill="#000000",
                       outline="", stipple="gray50", tags="dyn")
        cv.create_oval(cx - r, cy - r * 0.85, cx + r, cy + r, fill="#c8102e", outline="#7a0a1c",
                       tags="dyn")
        cv.create_oval(cx - r * 0.86, cy - r * 0.8, cx + r * 0.7, cy + r * 0.72, fill="#ff3b4e",
                       outline="", tags="dyn")
        cv.create_oval(cx - r * 0.55, cy - r * 0.55, cx - r * 0.12, cy - r * 0.15, fill="#ffc9cf",
                       outline="", tags="dyn")
        cv.create_line(cx, cy - r * 0.75, cx + r * 0.12, cy - r * 1.25, fill="#6b3f17",
                       width=max(1, c // 14), capstyle="round", tags="dyn")
        cv.create_polygon(cx + r * 0.1, cy - r * 1.05, cx + r * 0.55, cy - r * 1.45,
                          cx + r * 0.85, cy - r * 1.05, cx + r * 0.45, cy - r * 0.85,
                          fill="#3ccf5a", outline="#1f7a33", smooth=True, tags="dyn")

    def _dibujar_serpiente(self, p, s):
        cv, c = self.tablero, self.celda
        cuerpo = p.cuerpo(s)
        if not len(cuerpo):
            return
        viva = p.vivo[s]
        n = len(cuerpo)
        inicio, fin = (CABEZA, COLA) if viva else ("#aeb6c2", "#3c4652")
        centros = [self._centro(f, k) for f, k in cuerpo]
        tramos = [[]]
        for i, (x, y) in enumerate(centros):
            if i and abs(x - centros[i - 1][0]) + abs(y - centros[i - 1][1]) > c * 1.5:
                tramos.append([])
            tramos[-1].append((x, y))
        ancho = c * 0.74
        for tr in tramos:
            pts = [v for q in tr for v in q] if len(tr) > 1 else [*tr[0], *tr[0]]
            sombra = [v + (c * 0.07 if k % 2 == 0 else c * 0.12) for k, v in enumerate(pts)]
            cv.create_line(*sombra, fill="#000000", width=ancho, capstyle="round",
                           joinstyle="round", stipple="gray50", tags="dyn")
            cv.create_line(*pts, fill="#06281a" if viva else "#1b2027", width=ancho + 3,
                           capstyle="round", joinstyle="round", tags="dyn")
        bandas = min(n, 14)
        k0 = 0
        for b in range(bandas):
            k1 = round((b + 1) * n / bandas)
            seg = centros[max(0, k0 - 1):k1 + 1] if b else centros[:k1 + 1]
            color = mezcla(inicio, fin, (k0 + k1) / 2 / max(n - 1, 1))
            pts = [v for q in seg for v in q]
            if len(seg) == 1:
                pts += pts
            cv.create_line(*pts, fill=color, width=ancho, capstyle="round", joinstyle="round",
                           tags="dyn")
            k0 = k1
        brillo = [v - c * 0.12 for q in centros[:max(2, n)] for v in q] if n > 1 else []
        if len(brillo) >= 4 and viva:
            cv.create_line(*brillo, fill=mezcla(inicio, "#ffffff", 0.25), width=max(1, c * 0.12),
                           capstyle="round", joinstyle="round", stipple="gray50", tags="dyn")
        fila, col = cuerpo[0]
        cx, cy = centros[0]
        r = c * 0.44
        cv.create_oval(cx - r, cy - r, cx + r, cy + r, fill=inicio,
                       outline="#06281a" if viva else "#1b2027", width=2, tags="dyn")
        self._dibujar_ojos(fila, col, p.dir[s], viva)

    def _dibujar_ojos(self, fila, col, direccion, viva):
        cv, c = self.tablero, self.celda
        cx, cy = self._centro(fila, col)
        fy, fx = ((-1, 0), (0, 1), (1, 0), (0, -1))[direccion]
        r = max(2.0, c * 0.13)
        if viva and int(time.perf_counter() * 2.5) % 3 == 0:
            tx, ty = cx + fx * c * 0.45, cy + fy * c * 0.45
            ux, uy = cx + fx * c * 0.68, cy + fy * c * 0.68
            cv.create_line(tx, ty, ux, uy, fill="#ff4d6d", width=max(1, c // 16), tags="dyn")
            for lado in (-1, 1):
                cv.create_line(ux, uy, ux + fx * c * 0.1 + fy * lado * c * 0.08,
                               uy + fy * c * 0.1 - fx * lado * c * 0.08, fill="#ff4d6d",
                               width=max(1, c // 16), tags="dyn")
        for lado in (-1, 1):
            ex = cx + fx * c * 0.16 + fy * lado * c * 0.2
            ey = cy + fy * c * 0.16 - fx * lado * c * 0.2
            if viva:
                cv.create_oval(ex - r, ey - r, ex + r, ey + r, fill="white", outline="#06281a",
                               tags="dyn")
                rp = r * 0.55
                px, py = ex + fx * r * 0.35, ey + fy * r * 0.35
                cv.create_oval(px - rp, py - rp, px + rp, py + rp, fill="#0e1014", outline="",
                               tags="dyn")
                cv.create_oval(px - rp * 0.2 - 1, py - rp * 0.6, px + rp * 0.2 - 1,
                               py - rp * 0.2, fill="white", outline="", tags="dyn")
            else:
                cv.create_line(ex - r, ey - r, ex + r, ey + r, fill="#0e1014", width=2, tags="dyn")
                cv.create_line(ex - r, ey + r, ex + r, ey - r, fill="#0e1014", width=2, tags="dyn")

    def _dibujar_tablero(self):
        cv = self.tablero
        cv.delete("dyn")
        p, s = self.partida, self.seguido
        if self.turbo:
            self._pantalla_turbo()
        else:
            if not self.demo:
                r = max(2.0, self.celda * 0.17)
                for k in np.nonzero(p.vivo)[0]:
                    if k != s:
                        x, y = self._centro(*p.cabeza[k])
                        cv.create_oval(x - r, y - r, x + r, y + r, fill="#2d6b4b", outline="",
                                       stipple="gray75", tags="dyn")
            self._dibujar_fruta(*p.fruta[s])
            self._dibujar_serpiente(p, s)
            if not p.vivo[s]:
                self._cartel(MOTIVOS[p.motivo[s]].upper(), COLOR_MOTIVO.get(p.motivo[s], TEXTO),
                             LADO / 2)
        texto, t0 = self.aviso
        if texto and time.perf_counter() - t0 < 4:
            self._cartel(texto, ORO, 40)
        if self.pausa:
            self._cartel("EN PAUSA · espacio para seguir", AZUL, LADO - 40)
        self._dibujar_cabecera()

    def _cartel(self, texto, color, y):
        cv = self.tablero
        t = cv.create_text(LADO / 2 + 6, y, text=texto, fill=TEXTO, font=(SEMI, 13), tags="dyn")
        x0, y0, x1, y1 = cv.bbox(t)
        cv.create_rectangle(x0 - 26 + 4, y0 - 10 + 5, x1 + 18 + 4, y1 + 10 + 5, fill="#000000",
                            outline="", stipple="gray50", tags="dyn")
        caja = cv.create_rectangle(x0 - 26, y0 - 10, x1 + 18, y1 + 10, fill=TARJETA,
                                   outline=BORDE, tags="dyn")
        franja = cv.create_rectangle(x0 - 26, y0 - 10, x0 - 22, y1 + 10, fill=color, outline="",
                                     tags="dyn")
        punto = cv.create_oval(x0 - 14, (y0 + y1) / 2 - 4, x0 - 6, (y0 + y1) / 2 + 4, fill=color,
                               outline="", tags="dyn")
        for item in (punto, franja, caja):
            cv.tag_lower(item, t)
        cv.tag_raise(franja, caja)
        cv.tag_raise(punto, caja)

    def _pantalla_turbo(self):
        cv = self.tablero
        cv.create_rectangle(0, 0, LADO + 2, LADO + 2, fill=FONDO, outline="", tags="dyn")
        cv.create_rectangle(24, 24, LADO - 22, LADO - 22, fill=TARJETA, outline=BORDE, tags="dyn")
        cv.create_text(48, 62, anchor="w", text="MODO TURBO", fill=ORO, font=(SEMI, 24), tags="dyn")
        cv.create_text(48, 94, anchor="w", text="entrenando sin animar el tablero · T para volver a ver",
                       fill=TENUE, font=(FAMILIA, 10), tags="dyn")
        p = self.partida
        nv = p.nivel
        minutos = max(time.perf_counter() - self.turbo_t0, 1e-6) / 60
        datos = (("GENERACIÓN", str(self.e.generacion), ORO),
                 ("NIVEL", f"{nv.numero} · {nv.nombre}", TEXTO),
                 ("RITMO", f"{self.turbo_gens / minutos:.0f} gen/min", AZUL),
                 ("VIVAS", f"{int(p.vivo.sum())}/{p.n}", VERDE))
        ancho = (LADO - 96 - 3 * 8) / 4
        for k, (etq, valor, color) in enumerate(datos):
            x = 48 + k * (ancho + 8)
            cv.create_rectangle(x, 120, x + ancho, 172, fill=TARJETA2, outline="", tags="dyn")
            cv.create_rectangle(x, 120, x + 3, 172, fill=color, outline="", tags="dyn")
            cv.create_text(x + 12, 133, anchor="w", text=etq, fill=TENUE, font=(SEMI, 7), tags="dyn")
            cv.create_text(x + 12, 155, anchor="w", text=valor, fill=TEXTO, font=(SEMI, 12),
                           tags="dyn")
        columnas = (("GEN", 48), ("NIVEL", 112), ("MEJOR", 252), ("PROMEDIO", 326), ("CHOQUES", 420),
                    ("RACHA", 508))
        cv.create_rectangle(40, 196, LADO - 38, 220, fill=TARJETA2, outline="", tags="dyn")
        for nombre, x in columnas:
            cv.create_text(x, 208, anchor="w", text=nombre, fill=TENUE, font=(SEMI, 8), tags="dyn")
        for k, r in enumerate(reversed(self.registro)):
            y = 236 + k * 24
            if k % 2:
                cv.create_rectangle(40, y - 12, LADO - 38, y + 12, fill="#191c24", outline="",
                                    tags="dyn")
            color = ORO if r["subio"] else (VERDE if r["mejor_frutas"] >= r["meta"] else TEXTO)
            valores = (r["generacion"], f"{r['nivel']} {r['nombre']}", r["mejor_frutas"],
                       f"{r['promedio_frutas']:.2f}", f"{r['choques_pct']:.0f} %",
                       f"{r['racha']}/{C.RACHA_PARA_SUBIR}" + ("  ▲ sube" if r["subio"] else ""))
            for (_, x), valor in zip(columnas, valores):
                cv.create_text(x, y, anchor="w", text=str(valor), fill=color, font=(FAMILIA, 10),
                               tags="dyn")
        if not self.registro:
            cv.create_text(LADO / 2, 300, text="aquí aparece cada generación al terminar",
                           fill=SUTIL, font=(FAMILIA, 10), tags="dyn")

    def _dibujar_titulo(self):
        cv = self.titulo
        T.logo(cv, 4, 6, 1.0)
        cv.create_text(62, 4, anchor="nw", text="SNAKE", fill=TEXTO, font=(SEMI, 20))
        cv.create_text(150, 9, anchor="nw", text="EVOLUTIVO", fill=VERDE, font=(SEMI, 13))
        capas = " › ".join(str(n) for n in B.CAPAS)
        cv.create_text(62, 40, anchor="nw", fill=TENUE, font=(FAMILIA, 9),
                       text=f"red {capas} · estrategias evolutivas (ES) con Adam")

    def _dibujar_cabecera(self):
        cv = self.cabecera
        cv.delete("all")
        p, s = self.partida, self.seguido
        nv = p.nivel
        etiqueta = "CAMPEONA" if self.demo else "NIVEL"
        color = MORADO if self.demo else ORO
        t = cv.create_text(14, 17, anchor="w", fill=FONDO, font=(SEMI, 9),
                           text=f"{etiqueta} {nv.numero}/{len(NIVELES)}")
        x0, y0, x1, y1 = cv.bbox(t)
        cv.tag_lower(cv.create_rectangle(2, y0 - 4, x1 + 10, y1 + 4, fill=color, outline=""), t)
        cv.create_text(x1 + 20, 17, anchor="w", fill=TEXTO, font=(SEMI, 16), text=nv.nombre)
        detalle = nv.descripcion
        if self.demo:
            info = self.info_campeon
            detalle = (f"la mejor guardada (gen. {info['generacion']}, récord {info['frutas']}) · intento "
                       f"{self.intentos_demo}" if info else "todavía no hay campeona: se ve la red media")
        else:
            detalle += f" · siguiendo a la serpiente #{s}"
        cv.create_text(2, 46, anchor="w", fill=TENUE, font=(FAMILIA, 9), text=detalle)
        meta = nv.meta
        x1, y = LADO, 17
        t = cv.create_text(x1, y, anchor="e", fill=VERDE, font=(SEMI, 22), text=str(p.frutas[s]))
        bx = cv.bbox(t)[0] - 8
        cv.create_text(bx, y + 4, anchor="e", fill=TENUE, font=(FAMILIA, 9), text="frutas")
        cv.create_text(x1, 44, anchor="e", fill=SUTIL, font=(FAMILIA, 8),
                       text=f"meta {meta} · récord {self.e.records.get(nv.numero, 0)}")
        ancho = 150
        frac = min(1.0, p.frutas[s] / max(1, meta))
        cv.create_rectangle(x1 - ancho, 55, x1, 58, fill=REJILLA, outline="")
        cv.create_rectangle(x1 - ancho, 55, x1 - ancho + ancho * frac, 58, fill=VERDE, outline="")

    def _dibujar_paneles(self):
        self._panel_generacion()
        self._grafica()
        self._poblacion()
        self._red()
        self._telemetria()
        self.btn_pausa.texto("Seguir" if self.pausa else "Pausa")
        self.btn_turbo.texto("Animar" if self.turbo else "Turbo")
        self.btn_turbo.habilitar(not self.demo)
        self.btn_campeona.texto("Volver a entrenar" if self.demo else "Ver campeona")
        self.lbl_vel.configure(text=f"x{C.VELOCIDADES[self.i_vel]}")

    def _encabezado(self, cv, texto, derecha="", color=TENUE):
        cv.create_text(14, 14, anchor="w", text=texto, fill=TENUE, font=(SEMI, 8))
        if derecha:
            cv.create_text(int(cv["width"]) - 12, 14, anchor="e", text=derecha, fill=color,
                           font=(FAMILIA, 8))

    def _fila(self, cv, y, etiqueta, valor, color=TEXTO):
        cv.create_text(14, y, anchor="w", text=etiqueta, fill=TENUE, font=(FAMILIA, 9))
        cv.create_text(int(cv["width"]) - 12, y, anchor="e", text=valor, fill=color, font=(SEMI, 9))

    def _barra(self, cv, x, y, ancho, valor, color, alto=6):
        cv.create_rectangle(x, y, x + ancho, y + alto, fill=REJILLA, outline="")
        if valor > 0:
            cv.create_rectangle(x, y, x + ancho * min(max(valor, 0), 1), y + alto, fill=color,
                                outline="")

    def _ficha(self, cv, x, y, w, etq, valor, color):
        cv.create_rectangle(x, y, x + w, y + 46, fill=TARJETA2, outline="")
        cv.create_rectangle(x, y, x + 3, y + 46, fill=color, outline="")
        cv.create_text(x + 11, y + 11, anchor="w", text=etq, fill=TENUE, font=(SEMI, 7))
        cv.create_text(x + 11, y + 31, anchor="w", text=valor, fill=TEXTO, font=(SEMI, 14))

    def _panel_generacion(self):
        cv = self.c_gen
        cv.delete("all")
        p = self.partida
        w = ANCHO_PANEL
        if self.demo:
            self._encabezado(cv, "CAMPEONA GUARDADA", "←/→ cambia de nivel")
            info = self.info_campeon
            ancho = (w - 28 - 12) / 3
            self._ficha(cv, 14, 28, ancho, "NIVEL", str(p.nivel.numero), MORADO)
            self._ficha(cv, 14 + ancho + 6, 28, ancho, "RÉCORD", f"{info['frutas']}" if info else "—",
                        ORO)
            self._ficha(cv, 14 + 2 * (ancho + 6), 28, ancho, "INTENTO", str(self.intentos_demo), AZUL)
            self._fila(cv, 98, "aprendido en la generación", str(info["generacion"]) if info else "—")
            self._fila(cv, 120, "frutas en este intento", str(p.frutas[0]), VERDE)
            self._fila(cv, 142, "meta del nivel", str(p.nivel.meta))
            return
        e = self.e
        self._encabezado(cv, "GENERACIÓN", f"σ = {e.sigma:.3f}")
        ancho = (w - 28 - 12) / 3
        vivas = int(p.vivo.sum())
        h = e.historial[-1] if e.historial else None
        self._ficha(cv, 14, 26, ancho, "GENERACIÓN", str(e.generacion), ORO)
        self._ficha(cv, 14 + ancho + 6, 26, ancho, "MEJOR ANTERIOR",
                    f"{h['mejor_frutas']}" if h else "—", VERDE)
        self._ficha(cv, 14 + 2 * (ancho + 6), 26, ancho, "PROMEDIO",
                    f"{h['promedio_frutas']:.2f}" if h else "—", AZUL)
        y = 90
        cv.create_text(14, y, anchor="w", text=e.nivel_actual.nombre, fill=TEXTO, font=(SEMI, 10))
        for k in range(len(NIVELES)):
            x = 130 + k * 17
            color = VERDE if k < e.nivel - 1 else (ORO if k == e.nivel - 1 else REJILLA)
            cv.create_oval(x - 5, y - 5, x + 5, y + 5, fill=color, outline="")
        cv.create_text(w - 12, y, anchor="e", fill=TENUE, font=(FAMILIA, 8),
                       text=f"racha {e.racha}/{C.RACHA_PARA_SUBIR}")
        cv.create_text(14, 112, anchor="w", text=f"vivas {vivas}/{p.n}", fill=TEXTO, font=(FAMILIA, 9))
        self._barra(cv, 110, 109, w - 124, vivas / p.n, AZUL)
        filas = (("la red media θ comió", str(h["frutas_media"]) if h else "—", TEXTO),
                 ("chocaron · murieron de hambre",
                  f"{h['choques_pct']:.0f} % · {h['hambre_pct']:.0f} %" if h else "—", NARANJA))
        for k, (etiqueta, valor, color) in enumerate(filas):
            self._fila(cv, 136 + k * 20, etiqueta, valor, color)

    def _grafica(self):
        cv = self.c_graf
        cv.delete("all")
        self._encabezado(cv, "FRUTAS POR GENERACIÓN")
        xl = ANCHO_PANEL - 12
        for texto, color, dash in (("meta", VERDE, (3, 2)), ("promedio", AZUL, None),
                                   ("mejor", ORO, None)):
            t = cv.create_text(xl, 14, anchor="e", text=texto, fill=TENUE, font=(FAMILIA, 8))
            x0 = cv.bbox(t)[0]
            cv.create_line(x0 - 18, 14, x0 - 5, 14, fill=color, width=2, dash=dash)
            xl = x0 - 26
        datos = self.e.historial[-150:]
        x0, y0, x1, y1 = 40, 32, ANCHO_PANEL - 12, 140
        if len(datos) < 2:
            cv.create_line(x0, y1, x1, y1, fill=REJILLA)
            cv.create_text((x0 + x1) / 2, (y0 + y1) / 2, text="la gráfica aparece al terminar\n"
                           "la segunda generación", fill=SUTIL, font=(FAMILIA, 9), justify="center")
            return
        tope = max(max(r["mejor_frutas"] for r in datos), max(r["meta"] for r in datos), 1)
        paso = T.paso_eje(tope, 4)
        tope = max(paso, np.ceil(tope / paso) * paso)

        def punto(i, valor):
            return x0 + (x1 - x0) * i / (len(datos) - 1), y1 - (y1 - y0) * valor / tope

        v = 0
        while v <= tope + 1e-9:
            y = punto(0, v)[1]
            cv.create_line(x0, y, x1, y, fill=REJILLA)
            cv.create_text(x0 - 6, y, anchor="e", text=f"{v:g}", fill=SUTIL, font=(FAMILIA, 7))
            v += paso
        ultima_etiqueta = -100
        for i in range(1, len(datos)):
            if datos[i]["nivel"] != datos[i - 1]["nivel"]:
                x = punto(i, 0)[0]
                cv.create_line(x, y0, x, y1, fill=SUTIL, dash=(2, 3))
                if x - ultima_etiqueta > 20:
                    cv.create_text(x + 3, y0 + 2, anchor="nw", text=f"N{datos[i]['nivel']}",
                                   fill=TENUE, font=(FAMILIA, 7))
                    ultima_etiqueta = x
        mejor = [punto(i, r["mejor_frutas"]) for i, r in enumerate(datos)]
        area = [(x0, y1)] + mejor + [(x1, y1)]
        cv.create_polygon(*[v for q in area for v in q], fill=mezcla(ORO, TARJETA, 0.88),
                          outline="")
        cv.create_line(*[c for i, r in enumerate(datos) for c in punto(i, r["meta"])],
                       fill=mezcla(VERDE, TARJETA, 0.3), dash=(3, 3))
        cv.create_line(*[c for i, r in enumerate(datos) for c in punto(i, r["promedio_frutas"])],
                       fill=AZUL, width=2)
        cv.create_line(*[v for q in mejor for v in q], fill=ORO, width=2)
        xu, yu = mejor[-1]
        cv.create_oval(xu - 3, yu - 3, xu + 3, yu + 3, fill=ORO, outline=TARJETA)
        cv.create_text(x0, y1 + 11, anchor="w", text=f"gen {datos[0]['generacion']}", fill=SUTIL,
                       font=(FAMILIA, 7))
        cv.create_text(x1, y1 + 11, anchor="e", text=f"gen {datos[-1]['generacion']}", fill=SUTIL,
                       font=(FAMILIA, 7))

    def _poblacion(self):
        cv = self.c_pobl
        cv.delete("all")
        p = self.partida
        self._encabezado(cv, "POBLACIÓN · CADA CUADRO ES UNA SERPIENTE")
        if self.demo:
            cv.create_text(ANCHO_PANEL / 2, 78, fill=SUTIL, font=(FAMILIA, 10), justify="center",
                           text="viendo sólo a la campeona guardada\n"
                                "la población sigue esperando en su generación")
            return
        columnas, lado, hueco = 26, 11, 2
        maximo = max(int(p.frutas.max()), 1)
        for k in range(p.n):
            x = 14 + (k % columnas) * (lado + hueco)
            y = 28 + (k // columnas) * (lado + hueco)
            if p.vivo[k]:
                color = mezcla("#1d4434", VERDE, p.frutas[k] / maximo)
            else:
                color = mezcla(COLOR_MOTIVO.get(p.motivo[k], GRIS), TARJETA, 0.35)
            cv.create_rectangle(x, y, x + lado, y + lado, fill=color, outline="")
            if k == self.seguido:
                cv.create_rectangle(x - 2, y - 2, x + lado + 2, y + lado + 2, outline=TEXTO, width=1.5)
        leyenda = (("viva", VERDE), ("muro", ROJO), ("se mordió", MORADO), ("hambre", NARANJA),
                   ("tiempo", GRIS))
        x = 14
        for texto, color in leyenda:
            cv.create_oval(x, 132, x + 8, 140, fill=color, outline="")
            t = cv.create_text(x + 12, 136, anchor="w", text=texto, fill=TENUE, font=(FAMILIA, 8))
            x = cv.bbox(t)[2] + 12

    def _posiciones_red(self):
        columnas = (96, 170, 226, 262)
        posiciones = []
        for x, n in zip(columnas, B.CAPAS):
            alto = 432 if n == B.N_ENTRADAS else min(432, n * 26)
            y0 = 36 + (432 - alto) / 2
            paso = alto / max(n - 1, 1) if n > 1 else 0
            posiciones.append([(x, y0 + i * paso + (alto / 2 if n == 1 else 0)) for i in range(n)])
        return posiciones

    def _red(self):
        cv = self.c_red
        p, s = self.partida, self.seguido
        capas = B.subconjunto(p.capas, [s])
        posiciones = self._posiciones_red()
        clave = (id(p), s)
        if clave != self.clave_aristas:
            self.clave_aristas = clave
            cv.delete("all")
            self._encabezado(cv, "RED NEURONAL DE LA SEGUIDA · EN VIVO")
            for k, (w, _) in enumerate(capas):
                pesos = w[0]
                limite = np.sort(np.abs(pesos).ravel())[-160] if pesos.size > 160 else 0.0
                escala = np.abs(pesos).max() or 1.0
                for i, j in zip(*np.nonzero(np.abs(pesos) >= limite)):
                    v = pesos[i, j] / escala
                    color = mezcla(TARJETA, AZUL if v > 0 else "#ff5c8a", abs(v) * 0.75)
                    (xa, ya), (xb, yb) = posiciones[k][i], posiciones[k + 1][j]
                    cv.create_line(xa, ya, xb, yb, fill=color)
            for i, nombre in enumerate(B.NOMBRES_ENTRADAS):
                x, y = posiciones[0][i]
                cv.create_text(x - 8, y, anchor="e", text=nombre, fill=TENUE, font=(FAMILIA, 7))
        cv.delete("nodo")
        salida, ocultas = B.activar(capas, p.entradas[s][None, :], con_ocultas=True)
        valores = [p.entradas[s], *[o[0] for o in ocultas], np.tanh(salida[0])]
        elegida = int(np.argmax(salida[0]))
        for k, (capa, fila) in enumerate(zip(posiciones, valores)):
            r = 4 if k == 0 else 5
            for i, (x, y) in enumerate(capa):
                v = float(fila[i])
                color = mezcla(TARJETA2, ORO if v >= 0 else AZUL, min(abs(v), 1.0))
                cv.create_oval(x - r, y - r, x + r, y + r, fill=color, outline=BORDE, tags="nodo")
        for i, nombre in enumerate(B.NOMBRES_SALIDAS):
            x, y = posiciones[-1][i]
            activa = i == elegida and p.vivo[s]
            color = ORO if activa else TENUE
            if activa:
                cv.create_oval(x - 10, y - 10, x + 10, y + 10, outline=ORO, width=2, tags="nodo")
            cv.create_text(x + 14, y - 6, anchor="w", text=nombre, fill=color, font=(SEMI, 8),
                           tags="nodo")
            cv.create_text(x + 14, y + 7, anchor="w", text=f"{salida[0][i]:+.2f}", fill=color,
                           font=(MONO, 8), tags="nodo")

    def _telemetria(self):
        cv = self.c_tele
        cv.delete("all")
        p, s = self.partida, self.seguido
        self._encabezado(cv, "TELEMETRÍA", f"serpiente #{s}")
        estado = MOTIVOS[p.motivo[s]]
        color = VERDE if p.vivo[s] else COLOR_MOTIVO.get(p.motivo[s], TEXTO)
        ancho = (ANCHO_RED - 28 - 12) / 3
        self._ficha(cv, 14, 26, ancho, "ESTADO", estado, color)
        self._ficha(cv, 14 + ancho + 6, 26, ancho, "FRUTAS · LARGO", f"{p.frutas[s]} · {p.largo[s]}", ORO)
        self._ficha(cv, 14 + 2 * (ancho + 6), 26, ancho, "PASOS", str(p.pasos[s]), AZUL)
        cv.create_text(14, 92, anchor="w", text="hambre", fill=TENUE, font=(FAMILIA, 9))
        hambre = p.hambre[s] / p.hambre_max
        self._barra(cv, 112, 89, ANCHO_RED - 126, hambre, mezcla(VERDE, ROJO, hambre))
        cv.create_text(14, 112, anchor="w", text="ocupa del tablero", fill=TENUE, font=(FAMILIA, 9))
        self._barra(cv, 112, 109, ANCHO_RED - 126, p.largo[s] / p.nivel.libres, AZUL)
        salida = p.salidas[s]
        probabilidad = np.exp(salida - salida.max())
        probabilidad /= probabilidad.sum()
        for i, nombre in enumerate(B.NOMBRES_SALIDAS):
            y = 138 + i * 19
            elegida = i == np.argmax(salida)
            cv.create_text(14, y, anchor="w", text=nombre.lower(), fill=TEXTO if elegida else TENUE,
                           font=(SEMI if elegida else FAMILIA, 9))
            self._barra(cv, 112, y - 3, ANCHO_RED - 172, probabilidad[i], ORO if elegida else SUTIL)
            cv.create_text(ANCHO_RED - 12, y, anchor="e", text=f"{100 * probabilidad[i]:.0f} %",
                           fill=TEXTO, font=(SEMI, 9))

    def ejecutar(self):
        self.raiz.mainloop()
