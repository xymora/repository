import base64
import multiprocessing as mp
import random
import time
import tkinter as tk
from tkinter import messagebox

import numpy as np

import config as C
import graficos as G
import tema as TM
from evolucion import ESCALA, bajar_prioridad, evaluar
from grabador import BotonGrabar
from motor import CARACTERISTICAS, Juego
from niveles import NIVELES, nivel as obtener_nivel
from piezas import COLORES, MIN_FILA, NOMBRES, ROTACIONES, celdas

S = C.CELDA
ANCHO_JUEGO, ALTO_JUEGO = 600, 640
POZO_X0, POZO_Y1 = 160, 616
POZO_X1 = POZO_X0 + C.ANCHO * S
MINI = 20
ANCHO_PANEL = 470
FONDO, TARJETA, TARJETA2, BORDE = TM.FONDO, TM.TARJETA, TM.TARJETA2, TM.BORDE
TEXTO, TENUE, SUTIL, REJILLA = TM.TEXTO, TM.TENUE, TM.SUTIL, TM.REJILLA
ORO, AZUL, VERDE, MORADO, ROJO = TM.ORO, TM.AZUL, TM.VERDE, TM.MORADO, TM.ROJO
FUENTE, SEMI, MONO = TM.FAMILIA, TM.SEMI, TM.MONO
VELOCIDADES = (1, 2, 4, 8, 30)
COSTO_APARECER, COSTO_GIRO, COSTO_MOVER, COSTO_CAER, COSTO_ASENTAR = 6, 5, 4, 1, 8
FRAMES_LIMPIEZA = 26
FRAMES_FIN = 120
RETARDO_FIJAR = 30
VISTAS = {"mejor": "la mejor de la generación anterior", "campeona": "la campeona guardada del nivel",
          "humano": "tú · la IA aprende de tus jugadas"}
NOMBRE_LINEAS = {2: "DOBLE", 3: "TRIPLE", 4: "¡TETRIS!"}
CORTO = ("aterrizaje", "erosión", "trans. filas", "trans. columnas", "huecos", "pozos", "prof. huecos",
         "filas c/huecos")


class Aplicacion:
    def __init__(self, entrenador, vista="mejor", turbo=False):
        self.e = entrenador
        self.raiz = tk.Tk()
        self.raiz.title("Tetris evolutivo — una IA que aprende a jugar con CMA-ES")
        self.raiz.configure(bg=FONDO)
        self.raiz.resizable(False, False)
        self.vista_tipo = vista
        self.turbo = turbo and vista != "humano"
        self.pausa = False
        self.i_vel = 0
        self.nivel_vista = None
        self.teclas = set()
        self.aviso = ("", 0.0)
        self.registro = []
        self.pendiente = None
        self.fondos = {}
        self.maqueta = None
        self.t_panel = 0.0
        self.turbo_t0 = time.perf_counter()
        self.turbo_gens = 0
        self.siguiente_cuadro = time.perf_counter()
        self.decisiones = []
        self.particulas = []
        self.emergentes = []
        self.capa = []
        self.pool = mp.Pool(C.PROCESOS, initializer=bajar_prioridad)
        self._sprites()
        self._construir()
        self._teclas()
        self._nueva_vista()
        self.raiz.after(C.CUADRO_MS, self._ciclo)

    def _foto(self, rgba):
        return tk.PhotoImage(data=base64.b64encode(G.png(rgba)))

    def _sprites(self):
        self.bloques = [None] + [self._foto(G.bloque(c, S)) for c in COLORES[1:]]
        self.minis = [None] + [self._foto(G.bloque(c, MINI)) for c in COLORES[1:]]
        self.fantasmas = [None] + [self._foto(G.fantasma(c, S)) for c in COLORES[1:]]
        self.destellos = [self._foto(G.destello(C.ANCHO * S, S, k / 6)) for k in range(1, 7)]
        self.chispas = [None] + [self._foto(G.chispa(c)) for c in COLORES[1:]]

    def _construir(self):
        izquierda = tk.Frame(self.raiz, bg=FONDO)
        izquierda.pack(side="left", anchor="n", padx=(14, 8), pady=12)
        self.cv = tk.Canvas(izquierda, width=ANCHO_JUEGO, height=ALTO_JUEGO, bg="#090b10",
                            highlightthickness=1, highlightbackground=BORDE)
        self.cv.pack()
        self.pie = tk.Label(izquierda, bg=FONDO, fg=TENUE, font=(FUENTE, 9), anchor="w")
        self.pie.pack(fill="x", pady=(6, 0))

        derecha = tk.Frame(self.raiz, bg=FONDO)
        derecha.pack(side="left", anchor="n", padx=(8, 14), pady=12)
        titulo = tk.Canvas(derecha, width=ANCHO_PANEL, height=50, bg=FONDO, highlightthickness=0)
        titulo.pack(anchor="w")
        TM.logo(titulo, 4, 4, 1.0)
        t = titulo.create_text(56, 0, anchor="nw", text="TETRIS", fill=TM.MORADO, font=(SEMI, 22))
        titulo.create_text(titulo.bbox(t)[2] + 8, 9, anchor="nw", text="EVOLUTIVO", fill=TEXTO, font=(SEMI, 13))
        titulo.create_text(57, 36, anchor="nw", fill=TENUE, font=(FUENTE, 8),
                           text=f"8 características BCTS · CMA-ES · población {self.e.poblacion} · "
                                f"{C.JUEGOS} partidas c/u · {C.PROCESOS} procesos")
        self.c_gen = self._tarjeta(derecha, 150)
        self.c_graf = self._tarjeta(derecha, 118)
        self.c_pesos = self._tarjeta(derecha, 150)
        self.c_pobl = self._tarjeta(derecha, 74)
        self._controles(derecha)

    def _tarjeta(self, padre, alto):
        cv = tk.Canvas(padre, width=ANCHO_PANEL, height=alto, bg=TARJETA, highlightthickness=1,
                       highlightbackground=BORDE)
        cv.pack(anchor="w", pady=(0, 8))
        return cv

    def _controles(self, padre):
        fila = tk.Frame(padre, bg=FONDO)
        fila.pack(anchor="w", fill="x")
        self.btn_pausa = TM.Boton(fila, "Pausa", self.alternar_pausa, ancho=7).pack(side="left")
        self.btn_turbo = TM.Boton(fila, "Turbo", self.alternar_turbo, ancho=7).pack(side="left", padx=(6, 0))
        vel = tk.Frame(fila, bg=BORDE, padx=1, pady=1)
        vel.pack(side="left", padx=(6, 0))
        TM.Boton(vel, "−", lambda: self.cambiar_vel(-1)).pack(side="left")
        self.lbl_vel = tk.Label(vel, text="x1", width=4, bg=TARJETA, fg=ORO, font=(SEMI, 10), pady=6)
        self.lbl_vel.pack(side="left")
        TM.Boton(vel, "+", lambda: self.cambiar_vel(1)).pack(side="left")
        TM.Boton(fila, "⟲ Reiniciar", self.reiniciar).pack(side="right")
        TM.Boton(fila, "Guardar", self.guardar, VERDE, True).pack(side="right", padx=(0, 6))

        fila = tk.Frame(padre, bg=FONDO)
        fila.pack(anchor="w", fill="x", pady=(6, 0))
        self.btn_campeona = TM.Boton(fila, "Ver campeona", lambda: self.cambiar_vista("campeona"), ORO, True,
                                     ancho=13).pack(side="left")
        self.btn_humano = TM.Boton(fila, "Jugar tú", lambda: self.cambiar_vista("humano"), MORADO, True,
                                   ancho=12).pack(side="left", padx=(6, 0))
        self.grabar = TM.estilo_grabar(BotonGrabar(fila, self.raiz, self.avisar, (SEMI, 10)))
        self.grabar.pack(side="right")
        ayuda = ("Espacio pausa · T turbo · +/− velocidad · C campeona (←/→ nivel) · G guardar · N reiniciar\n"
                 "J jugar tú: ←/→ mover, ↑ o X girar, Z girar al revés, ↓ bajar, Espacio soltar, P pausa · Esc salir")
        tk.Label(padre, text=ayuda, bg=FONDO, fg=SUTIL, font=(FUENTE, 8), justify="left").pack(anchor="w",
                                                                                              pady=(8, 0))

    def _teclas(self):
        r = self.raiz
        r.bind("<KeyPress>", self._tecla_abajo)
        r.bind("<KeyRelease>", self._tecla_arriba)
        r.bind("<FocusOut>", lambda ev: self.teclas.clear())
        r.protocol("WM_DELETE_WINDOW", self.salir)

    def _tecla_abajo(self, ev):
        k = ev.keysym
        if self.vista_tipo == "humano":
            self.teclas.add(k)
            juego = {"Left": lambda: self._mover(-1), "Right": lambda: self._mover(1),
                     "Up": lambda: self._girar(1), "x": lambda: self._girar(1), "X": lambda: self._girar(1),
                     "z": lambda: self._girar(-1), "Z": lambda: self._girar(-1), "space": self._soltar}
            otras = {"p": self.alternar_pausa, "P": self.alternar_pausa, "j": lambda: self.cambiar_vista("humano"),
                     "J": lambda: self.cambiar_vista("humano"), "Escape": self.salir}
            if k in juego and not self.pausa:
                juego[k]()
            elif k in otras:
                otras[k]()
            return
        acciones = {
            "space": self.alternar_pausa, "Escape": self.salir, "t": self.alternar_turbo,
            "c": lambda: self.cambiar_vista("campeona"), "j": lambda: self.cambiar_vista("humano"),
            "n": self.reiniciar, "g": self.guardar, "plus": lambda: self.cambiar_vel(1),
            "equal": lambda: self.cambiar_vel(1), "KP_Add": lambda: self.cambiar_vel(1),
            "minus": lambda: self.cambiar_vel(-1), "KP_Subtract": lambda: self.cambiar_vel(-1),
            "Left": lambda: self.cambiar_nivel_vista(-1), "Right": lambda: self.cambiar_nivel_vista(1),
        }
        accion = acciones.get(k) or acciones.get(k.lower())
        if accion:
            accion()

    def _tecla_arriba(self, ev):
        self.teclas.discard(ev.keysym)

    def avisar(self, texto, *_):
        self.aviso = (texto, time.perf_counter())

    def guardar(self):
        try:
            self.e._guardar()
        except OSError as err:
            self.avisar(f"No se pudo guardar: {err}")
            return
        self.avisar(f"Avance guardado en la generación {self.e.generacion}")

    def salir(self):
        try:
            self._aprender_humano()
            self.e._guardar()
        except OSError:
            pass
        self.grabar.cerrar()
        self.pool.terminate()
        self.raiz.destroy()

    def alternar_pausa(self):
        self.pausa = not self.pausa

    def alternar_turbo(self):
        self.turbo = not self.turbo
        self.turbo_t0 = time.perf_counter()
        self.turbo_gens = 0
        if self.turbo and self.vista_tipo == "humano":
            self.vista_tipo = "mejor"
            self._nueva_vista()
        if not self.turbo:
            self.maqueta = None

    def cambiar_vel(self, delta):
        self.i_vel = max(0, min(len(VELOCIDADES) - 1, self.i_vel + delta))

    def cambiar_vista(self, tipo):
        self.vista_tipo = "mejor" if self.vista_tipo == tipo else tipo
        self.nivel_vista = None
        self.teclas.clear()
        if self.vista_tipo != "mejor":
            self.turbo = False
            self.maqueta = None
        self._nueva_vista()

    def cambiar_nivel_vista(self, delta):
        if self.vista_tipo != "campeona":
            return
        actual = self.nivel_vista or self.juego.nivel.numero
        self.nivel_vista = max(1, min(len(NIVELES), actual + delta))
        self._nueva_vista()

    def reiniciar(self):
        pausa_previa, self.pausa = self.pausa, True
        ok = messagebox.askyesno("Reiniciar desde cero",
                                 "Se borrará todo lo aprendido (estado, campeonas, historial y tus jugadas) "
                                 "y la evolución empezará otra vez en la generación 1.\n\n¿Continuar?",
                                 parent=self.raiz)
        self.pausa = pausa_previa
        if ok:
            self.decisiones = []
            self.e.reiniciar()
            self.pendiente = None
            self.registro.clear()
            self._nueva_vista()
            self.avisar("Evolución reiniciada desde cero")

    def _aprender_humano(self):
        decisiones, self.decisiones = self.decisiones, []
        if len(decisiones) < 5:
            return 0
        self.e.aprender_de_humano(decisiones)
        self.pendiente = None
        return len(decisiones)

    def _nueva_vista(self):
        aprendidas = self._aprender_humano()
        if aprendidas:
            self.avisar(f"La IA aprendió de {aprendidas} jugadas tuyas")
        e = self.e
        self.info_vista = None
        if self.vista_tipo == "campeona":
            numero = self.nivel_vista or e.nivel_actual
            campeon = e.campeon(numero)
            self.pesos = campeon[0] if campeon else e.mejores_pesos()
            self.info_vista = campeon[1] if campeon else None
        else:
            numero = (self.nivel_vista if self.vista_tipo == "humano" else None) or e.nivel_actual
            self.pesos = e.mejores_pesos()
        self.juego = Juego(obtener_nivel(numero), random.randrange(1 << 30))
        self.ruta = None
        self.pos = None
        self.objetivo = None
        self.presupuesto = 0.0
        self.limpieza = None
        self.fin_t = None
        self.h = None
        self.n_candidatos = 0
        self.particulas_borrar()
        if not self.juego.terminado:
            self._nueva_pieza()

    def particulas_borrar(self):
        for p in self.particulas:
            self.cv.delete(p[5])
        for item, _ in self.emergentes:
            for i in item:
                self.cv.delete(i)
        self.particulas, self.emergentes = [], []

    def _lanzar(self):
        tareas = self.e.tareas()
        self.pendiente = (self.pool.imap_unordered(evaluar, tareas), [], len(tareas))

    def _recolectar(self):
        if self.pendiente is None:
            self._lanzar()
            return
        iterador, resultados, total = self.pendiente
        while len(resultados) < total:
            try:
                resultados.append(iterador.next(timeout=0))
            except mp.TimeoutError:
                break
        if len(resultados) < total:
            return
        r = self.e.terminar(resultados)
        self.registro = (self.registro + [r])[-14:]
        self.turbo_gens += 1
        try:
            print(f"gen {r['generacion']:5d} · nivel {r['nivel']} {r['nombre']:<16} · mejor {r['mejor_lineas']:7.1f} · "
                  f"promedio {r['promedio_lineas']:7.1f} líneas (meta {r['meta']}) · superan {r['superaron_pct']:5.1f} % · "
                  f"sigma {r['sigma']:.3f}", flush=True)
        except (OSError, ValueError):
            pass
        if r["subio"]:
            texto = ("¡Campaña completa! Ahora repasa todos los niveles" if self.e.completada
                     else f"¡{r['nombre']} superado! Siguiente: {obtener_nivel(self.e.nivel).nombre}")
            self.avisar(texto)
        self.pendiente = None
        self._lanzar()

    def _ciclo(self):
        ahora = time.perf_counter()
        try:
            self._recolectar()
            if not self.pausa and not self.turbo:
                self._avanzar(VELOCIDADES[self.i_vel] if self.vista_tipo != "humano" else 1)
            self._dibujar()
            if ahora - self.t_panel > 0.25:
                self.t_panel = ahora
                self._dibujar_panel()
            self.siguiente_cuadro = max(self.siguiente_cuadro + C.CUADRO_MS / 1000, ahora - 0.1)
            espera = max(1, int((self.siguiente_cuadro - time.perf_counter()) * 1000))
            self.raiz.after(espera, self._ciclo)
        except tk.TclError:
            pass

    def _avanzar(self, vel):
        j = self.juego
        self._animar_efectos(vel)
        if j.terminado:
            if self.fin_t is None:
                self.fin_t = 0
                self._fin_vista()
            self.fin_t += 1
            if self.fin_t > FRAMES_FIN:
                self._nueva_vista()
            return
        if self.limpieza is not None:
            self.limpieza["t"] += vel
            if self.limpieza["t"] >= FRAMES_LIMPIEZA:
                filas, cols = self.limpieza["celdas"]
                self.limpieza = None
                j.fijar(filas, cols)
                self._nueva_pieza()
            return
        if self.vista_tipo == "humano":
            self._humano()
        else:
            self._ia(vel)

    def _fin_vista(self):
        j = self.juego
        if self.vista_tipo != "humano":
            return
        aprendidas = self._aprender_humano()
        if j.superado:
            siguiente = j.nivel.numero % len(NIVELES) + 1
            self.nivel_vista = siguiente
            texto = f"¡{j.nivel.nombre} superado! Siguiente: {obtener_nivel(siguiente).nombre}"
        else:
            texto = "Otra vez el mismo nivel"
        if aprendidas:
            texto += f" · la IA aprendió de {aprendidas} jugadas"
        self.avisar(texto)

    def _nueva_pieza(self):
        j = self.juego
        self.ruta = None
        self.pos = None
        if j.terminado:
            return
        c = j.candidatos()
        self.n_candidatos = 0 if c is None else len(c["rot"])
        if self.vista_tipo == "humano":
            rot, bx, by = j.salida()
            if not j.libre(rot, bx, by):
                j._terminar("tablero lleno")
                return
            self.pos = (rot, bx, by)
            self.h = {"caida": 0, "fijar": 0}

    def _ia(self, vel):
        j = self.juego
        self.presupuesto = min(self.presupuesto + vel, 400)
        while self.presupuesto >= 1 and not j.terminado and self.limpieza is None:
            if self.ruta is None:
                self._planear()
                if j.terminado:
                    break
            if self.ruta:
                rot, bx, by, costo = self.ruta[0]
                if self.presupuesto < costo:
                    break
                self.presupuesto -= costo
                self.pos = (rot, bx, by)
                self.ruta.pop(0)
            else:
                self.presupuesto -= 1
                c = j.candidatos()
                self._fijar(c["filas"][self.objetivo], c["cols"][self.objetivo])

    def _planear(self):
        j = self.juego
        i = j.elegir(self.pesos)
        if i is None:
            j._terminar("tablero lleno")
            return
        self.objetivo = i
        rot_t, bx_t, by_t = j.destino(i)
        p = j.actual
        _, bx, by = j.salida()
        ruta = [(0, bx, by, COSTO_APARECER)]
        for r in range(1, rot_t + 1):
            ruta.append((r, bx, -MIN_FILA[p][r], COSTO_GIRO))
        y = -MIN_FILA[p][rot_t]
        paso = 1 if bx_t > bx else -1
        for x in range(bx + paso, bx_t + paso, paso):
            ruta.append((rot_t, x, y, COSTO_MOVER))
        for yy in range(y + 1, by_t + 1):
            ruta.append((rot_t, bx_t, yy, COSTO_CAER))
        ruta.append((rot_t, bx_t, by_t, COSTO_ASENTAR))
        self.ruta = ruta
        self.pos = ruta[0][:3]

    def _fijar(self, filas, cols):
        j = self.juego
        filas, cols = np.asarray(filas), np.asarray(cols)
        tmp = j.tablero.copy()
        tmp[filas, cols] = True
        llenas = np.flatnonzero(tmp.all(1))
        self.ruta = None
        self.pos = None
        if not len(llenas):
            j.fijar(filas, cols)
            self._nueva_pieza()
            return
        color = j.color.copy()
        color[filas, cols] = NOMBRES.index(j.actual) + 1
        self.limpieza = {"t": 0, "filas": llenas.tolist(), "color": color, "celdas": (filas, cols)}
        y0 = POZO_Y1 - j.alto * S
        for f in llenas:
            for c in range(C.ANCHO):
                for _ in range(2):
                    self._particula(POZO_X0 + c * S + S / 2, y0 + f * S + S / 2, int(color[f, c]))
        if len(llenas) >= 2:
            self._emergente(NOMBRE_LINEAS[len(llenas)], y0 + llenas.mean() * S,
                            ORO if len(llenas) == 4 else TEXTO)

    def _particula(self, x, y, color):
        if len(self.particulas) > 260 or not color:
            return
        item = self.cv.create_image(x, y, image=self.chispas[color])
        ang = random.uniform(0, 2 * np.pi)
        vel = random.uniform(1.0, 4.5)
        self.particulas.append([x, y, np.cos(ang) * vel, np.sin(ang) * vel - 2, random.randint(24, 46), item])

    def _emergente(self, texto, y, color):
        cv = self.cv
        x = (POZO_X0 + POZO_X1) / 2
        items = [cv.create_text(x + dx, y + dy, text=texto, fill="#000000", font=(SEMI, 22))
                 for dx, dy in ((2, 2), (-1, 0), (1, 0), (0, -1), (0, 1))]
        items.append(cv.create_text(x, y, text=texto, fill=color, font=(SEMI, 22)))
        self.emergentes.append((items, 50))

    def _animar_efectos(self, vel):
        cv = self.cv
        vivas = []
        for p in self.particulas:
            for _ in range(min(vel, 4)):
                p[0] += p[2]
                p[1] += p[3]
                p[3] += 0.25
                p[4] -= 1
            if p[4] > 0:
                cv.coords(p[5], p[0], p[1])
                vivas.append(p)
            else:
                cv.delete(p[5])
        self.particulas = vivas
        quedan = []
        for items, vida in self.emergentes:
            vida -= min(vel, 4)
            if vida > 0:
                for i in items:
                    cv.move(i, 0, -0.8 * min(vel, 4))
                quedan.append((items, vida))
            else:
                for i in items:
                    cv.delete(i)
        self.emergentes = quedan

    def _humano(self):
        j = self.juego
        if self.pos is None:
            return
        rot, bx, by = self.pos
        h = self.h
        gravedad = 2 if "Down" in self.teclas else max(4, 40 - 3 * (j.lineas // 10))
        h["caida"] += 1
        if j.libre(rot, bx, by + 1):
            h["fijar"] = 0
            if h["caida"] >= gravedad:
                h["caida"] = 0
                self.pos = (rot, bx, by + 1)
        else:
            h["fijar"] += 1
            if h["fijar"] >= RETARDO_FIJAR:
                self._fijar_humano()

    def _mover(self, d):
        if self.pos is None or self.limpieza is not None or self.juego.terminado:
            return
        rot, bx, by = self.pos
        if self.juego.libre(rot, bx + d, by):
            self.pos = (rot, bx + d, by)

    def _girar(self, sentido):
        if self.pos is None or self.limpieza is not None or self.juego.terminado:
            return
        nuevo = self.juego.girar(*self.pos, sentido)
        if nuevo:
            self.pos = nuevo

    def _soltar(self):
        if self.pos is None or self.limpieza is not None or self.juego.terminado:
            return
        rot, bx, by = self.pos
        self.pos = (rot, bx, self.juego.caida(rot, bx, by))
        self._fijar_humano()

    def _fijar_humano(self):
        j = self.juego
        rot, bx, by = self.pos
        cs = celdas(j.actual, rot, bx, by)
        filas, cols = [f for f, _ in cs], [c for _, c in cs]
        i = j.indice_de(filas, cols)
        if i is not None:
            self.decisiones.append((j.candidatos()["feats"].copy(), i))
        self._fijar(filas, cols)

    def _fondo(self, nivel):
        clave = (nivel.numero, nivel.filas)
        if clave not in self.fondos:
            y0 = POZO_Y1 - nivel.filas * S
            img = G.fondo(ANCHO_JUEGO, ALTO_JUEGO, (POZO_X0, y0, POZO_X1, POZO_Y1), nivel.filas < 20, S,
                          G.COLOR_NIVEL[nivel.numero - 1])
            for x0, y0c, x1, y1 in ((14, 56, 146, 156), (14, 166, 146, 222), (14, 232, 146, 288),
                                    (14, 298, 146, 354), (14, 364, 146, 616), (454, 56, 586, 296),
                                    (454, 306, 586, 436), (454, 446, 586, 616)):
                G.tarjeta(img, x0, y0c, x1, y1)
            self.fondos[clave] = tk.PhotoImage(data=G.ppm(img))
        return self.fondos[clave]

    def _maquetar(self):
        j = self.juego
        cv = self.cv
        self.particulas_borrar()
        cv.delete("all")
        self.capa = []
        nivel = j.nivel
        acento = G.COLOR_NIVEL[nivel.numero - 1]
        cv.create_image(0, 0, anchor="nw", image=self._fondo(nivel))
        y0 = POZO_Y1 - j.alto * S
        self.y0 = y0

        def etiqueta(x, y, texto, color=TENUE):
            cv.create_text(x, y, anchor="w", text=texto, fill=color, font=(SEMI, 8))

        etiqueta(26, 72, "LÍNEAS")
        etiqueta(26, 182, "PIEZAS")
        etiqueta(26, 248, "PUNTOS")
        etiqueta(26, 314, "TETRIS")
        etiqueta(26, 380, "JUEGA")
        etiqueta(466, 72, "SIGUIENTES")
        etiqueta(466, 322, "NIVEL")
        etiqueta(466, 462, "CEREBRO")
        self.t_lineas = cv.create_text(26, 106, anchor="w", fill=TEXTO, font=(MONO, 26, "bold"))
        self.t_meta = cv.create_text(26, 134, anchor="w", fill=TENUE, font=(FUENTE, 8))
        cv.create_rectangle(26, 143, 134, 147, fill=REJILLA, outline="")
        self.barra = cv.create_rectangle(26, 143, 26, 147, fill=acento, outline="")
        self.t_piezas = cv.create_text(26, 204, anchor="w", fill=TEXTO, font=(MONO, 16, "bold"))
        self.t_puntos = cv.create_text(26, 270, anchor="w", fill=TEXTO, font=(MONO, 16, "bold"))
        self.t_tetris = cv.create_text(26, 336, anchor="w", fill=ORO, font=(MONO, 16, "bold"))
        self.t_quien = cv.create_text(26, 404, anchor="w", fill=TEXTO, font=(SEMI, 14))
        self.t_quien2 = cv.create_text(26, 424, anchor="nw", fill=TENUE, font=(FUENTE, 8), width=112)
        self.t_ayuda = cv.create_text(26, 484, anchor="nw", fill=SUTIL, font=(FUENTE, 8), width=112)
        cv.create_text(466, 350, anchor="w", fill=acento, font=(SEMI, 22), text=f"{nivel.numero}")
        cv.create_text(496, 352, anchor="w", fill=TENUE, font=(FUENTE, 9), text=f"de {len(NIVELES)}")
        cv.create_text(466, 378, anchor="w", fill=TEXTO, font=(SEMI, 11), text=nivel.nombre)
        cv.create_text(466, 394, anchor="nw", fill=TENUE, font=(FUENTE, 8), text=nivel.descripcion, width=112)
        self.t_cerebro = cv.create_text(466, 490, anchor="w", fill=TEXTO, font=(MONO, 20, "bold"))
        self.t_cerebro2 = cv.create_text(466, 510, anchor="nw", fill=TENUE, font=(FUENTE, 8), width=112)
        self.t_basura = cv.create_text(466, 580, anchor="w", fill=ROJO, font=(SEMI, 9))
        cv.create_text(ANCHO_JUEGO / 2, 26, fill=acento, font=(SEMI, 15),
                       text=f"NIVEL {nivel.numero} · {nivel.nombre.upper()}")
        self.celdas = [[cv.create_image(POZO_X0 + c * S, y0 + f * S, anchor="nw", state="hidden")
                        for c in range(C.ANCHO)] for f in range(j.alto)]
        self.mostrado = np.full((j.alto, C.ANCHO), -1, np.int16)
        self.items_fantasma = [cv.create_image(0, 0, anchor="nw", state="hidden") for _ in range(4)]
        self.items_pieza = [cv.create_image(0, 0, anchor="nw", state="hidden") for _ in range(4)]
        self.items_previa = [[cv.create_image(0, 0, anchor="nw", state="hidden") for _ in range(4)]
                             for _ in range(3)]
        self.items_destello = []
        self.maqueta = (j, nivel.numero)

    def _dibujar(self):
        cv = self.cv
        for t in self.capa:
            cv.delete(t)
        self.capa = []
        if self.turbo:
            if self.maqueta != "turbo":
                self.particulas_borrar()
                cv.delete("all")
                self.maqueta = "turbo"
            self._pantalla_turbo()
            return
        j = self.juego
        if self.maqueta != (j, j.nivel.numero):
            self._maquetar()
        color = self.limpieza["color"] if self.limpieza else j.color
        cambios = np.argwhere(color != self.mostrado)
        for f, c in cambios:
            k = int(color[f, c])
            item = self.celdas[f][c]
            if k:
                cv.itemconfigure(item, image=self.bloques[k], state="normal")
            else:
                cv.itemconfigure(item, state="hidden")
            self.mostrado[f, c] = k
        self._dibujar_pieza()
        self._dibujar_previas()
        self._dibujar_destellos()
        self._textos()
        self._superposiciones()

    def _dibujar_pieza(self):
        j = self.juego
        cv = self.cv
        if self.pos is None or j.terminado or self.limpieza is not None:
            for i in self.items_pieza + self.items_fantasma:
                cv.itemconfigure(i, state="hidden")
            return
        k = NOMBRES.index(j.actual) + 1
        rot, bx, by = self.pos
        if self.vista_tipo == "humano":
            fantasma = (rot, bx, j.caida(rot, bx, by))
        else:
            fantasma = j.destino(self.objetivo) if self.objetivo is not None and self.ruta else None
        for items, estado, sprites in ((self.items_fantasma, fantasma, self.fantasmas),
                                       (self.items_pieza, self.pos, self.bloques)):
            if estado is None:
                for i in items:
                    cv.itemconfigure(i, state="hidden")
                continue
            for i, (f, c) in zip(items, celdas(j.actual, *estado)):
                if f < 0:
                    cv.itemconfigure(i, state="hidden")
                    continue
                cv.coords(i, POZO_X0 + c * S, self.y0 + f * S)
                cv.itemconfigure(i, image=sprites[k], state="normal")

    def _dibujar_previas(self):
        cv = self.cv
        for slot, (items, p) in enumerate(zip(self.items_previa, self.juego.proximas(3))):
            cs = ROTACIONES[p][0]
            f0, c0 = min(f for f, _ in cs), min(c for _, c in cs)
            ancho = max(c for _, c in cs) - c0 + 1
            alto = max(f for f, _ in cs) - f0 + 1
            cx, cy = 520, 120 + slot * 66
            k = NOMBRES.index(p) + 1
            for i, (f, c) in zip(items, cs):
                cv.coords(i, cx - ancho * MINI / 2 + (c - c0) * MINI, cy - alto * MINI / 2 + (f - f0) * MINI)
                cv.itemconfigure(i, image=self.minis[k], state="normal")

    def _dibujar_destellos(self):
        cv = self.cv
        if self.limpieza is None:
            for i in self.items_destello:
                cv.delete(i)
            self.items_destello = []
            return
        t = self.limpieza["t"] / FRAMES_LIMPIEZA
        nivel = int(min(5, max(0, (1 - abs(1 - 2 * t)) * 6)))
        if not self.items_destello:
            self.items_destello = [cv.create_image(POZO_X0, self.y0 + f * S, anchor="nw")
                                   for f in self.limpieza["filas"]]
        for i in self.items_destello:
            cv.itemconfigure(i, image=self.destellos[nivel])

    def _textos(self):
        j = self.juego
        cv = self.cv
        cv.itemconfigure(self.t_lineas, text=f"{j.lineas}")
        cv.itemconfigure(self.t_meta, text=f"meta {j.nivel.meta} líneas")
        cv.coords(self.barra, 26, 143, 26 + 108 * min(1.0, j.lineas / j.nivel.meta), 147)
        cv.itemconfigure(self.t_piezas, text=f"{j.piezas}")
        cv.itemconfigure(self.t_puntos, text=f"{j.puntos:07d}")
        cv.itemconfigure(self.t_tetris, text=f"{j.tetris}")
        if self.vista_tipo == "humano":
            cv.itemconfigure(self.t_quien, text="TÚ", fill=MORADO)
            cv.itemconfigure(self.t_quien2, text="la IA copia tus decisiones al terminar la partida")
            cv.itemconfigure(self.t_ayuda, text="CONTROLES\n\n←  →  mover\n↑ / X  girar\nZ  girar al revés\n"
                                                 "↓  bajar rápido\nEspacio  soltar\nP  pausa\nJ  dejar de jugar")
            cv.itemconfigure(self.t_cerebro, text=f"{len(self.decisiones)}")
            cv.itemconfigure(self.t_cerebro2, text="jugadas tuyas registradas para enseñarle a la IA")
        else:
            campeona = self.vista_tipo == "campeona"
            cv.itemconfigure(self.t_quien, text="CAMPEONA" if campeona else "LA MEJOR", fill=ORO if campeona else AZUL)
            if campeona and self.info_vista:
                i = self.info_vista
                extra = f"de la gen. {i['generacion']} · " + ("superó el nivel" if i["superado"]
                                                             else f"{i['lineas']:.0f} líneas")
            elif campeona:
                extra = "aún no hay campeona: juega la mejor actual"
            else:
                extra = f"de la generación {self.e.generacion - 1}" if self.e.generacion > 1 else "pesos al azar"
            cv.itemconfigure(self.t_quien2, text=extra)
            cv.itemconfigure(self.t_ayuda, text="Para cada pieza la IA prueba todas las posiciones y giros, "
                                                 "mide 8 características del tablero resultante y elige la de "
                                                 "mayor puntaje según sus pesos." +
                                                 ("\n\n←/→ cambian de nivel" if campeona else ""))
            cv.itemconfigure(self.t_cerebro, text=f"{self.n_candidatos}")
            cv.itemconfigure(self.t_cerebro2, text="jugadas posibles evaluadas para esta pieza")
        cada = j.nivel.basura_cada
        cv.itemconfigure(self.t_basura, text=f"basura en {cada - j.piezas % cada} piezas" if cada else "")

    def _texto(self, x, y, texto, color=TEXTO, tam=12, ancla="center"):
        cv = self.cv
        fuente = (SEMI, tam)
        for dx, dy in ((2, 2), (-1, 0), (1, 0), (0, -1), (0, 1)):
            self.capa.append(cv.create_text(x + dx, y + dy, text=texto, fill="#000000", font=fuente, anchor=ancla))
        self.capa.append(cv.create_text(x, y, text=texto, fill=color, font=fuente, anchor=ancla))

    def _franja(self, y0, y1, x0=POZO_X0, x1=POZO_X1):
        cv = self.cv
        self.capa.append(cv.create_rectangle(x0, y0, x1, y1, fill="#000000", outline="", stipple="gray50"))
        for y in (y0, y1):
            self.capa.append(cv.create_line(x0, y, x1, y, fill=ORO))

    def _superposiciones(self):
        j = self.juego
        cx = (POZO_X0 + POZO_X1) / 2
        cy = (self.y0 + POZO_Y1) / 2
        if j.terminado:
            if j.superado:
                titulo, color = "¡META!", ORO
            else:
                titulo, color = "FIN", ROJO
            self._franja(cy - 44, cy + 44)
            self._texto(cx, cy - 12, titulo, color, 26)
            self._texto(cx, cy + 22, f"{j.lineas} líneas · {j.motivo}", TEXTO, 10)
        elif j.piezas == 0 and self.limpieza is None and (self.fin_t is None):
            self._franja(cy - 34, cy + 34)
            self._texto(cx, cy - 8, f"NIVEL {j.nivel.numero}", G.COLOR_NIVEL[j.nivel.numero - 1], 20)
            self._texto(cx, cy + 18, j.nivel.nombre.upper(), TEXTO, 11)
        if self.pausa:
            self._franja(cy - 90, cy - 40)
            self._texto(cx, cy - 65, "PAUSA", AZUL, 20)
        texto, t0 = self.aviso
        if texto and time.perf_counter() - t0 < 4:
            self._franja(ALTO_JUEGO - 60, ALTO_JUEGO - 24, 6, ANCHO_JUEGO - 6)
            self._texto(ANCHO_JUEGO / 2, ALTO_JUEGO - 42, texto, ORO, 11)

    def _pantalla_turbo(self):
        cv = self.cv
        c = self.capa
        c.append(cv.create_rectangle(0, 0, ANCHO_JUEGO, ALTO_JUEGO, fill=FONDO, outline=""))
        c.append(cv.create_rectangle(20, 20, ANCHO_JUEGO - 20, ALTO_JUEGO - 20, fill=TARJETA, outline=BORDE))
        c.append(cv.create_text(44, 58, anchor="w", text="MODO TURBO", fill=ORO, font=(SEMI, 22)))
        c.append(cv.create_text(44, 88, anchor="w", fill=TENUE, font=(FUENTE, 10),
                                text="entrenando sin animar · T para volver a ver"))
        minutos = max(time.perf_counter() - self.turbo_t0, 1e-6) / 60
        e = self.e
        datos = (("GENERACIÓN", str(e.generacion), ORO), ("NIVEL", f"{e.nivel_actual} · {obtener_nivel(e.nivel_actual).nombre}", TEXTO),
                 ("RITMO", f"{self.turbo_gens / minutos:.1f} gen/min", AZUL))
        ancho = (ANCHO_JUEGO - 88 - 2 * 8) / 3
        for k, (etq, valor, color) in enumerate(datos):
            x = 44 + k * (ancho + 8)
            c.append(cv.create_rectangle(x, 110, x + ancho, 166, fill=TARJETA2, outline=""))
            c.append(cv.create_rectangle(x, 110, x + 3, 166, fill=color, outline=""))
            c.append(cv.create_text(x + 12, 124, anchor="w", text=etq, fill=TENUE, font=(SEMI, 7)))
            c.append(cv.create_text(x + 12, 148, anchor="w", text=valor, fill=TEXTO, font=(SEMI, 11)))
        columnas = (("GEN", 44), ("NIVEL", 104), ("MEJOR", 290), ("PROM.", 380), ("SUPERAN", 470))
        c.append(cv.create_rectangle(36, 188, ANCHO_JUEGO - 36, 212, fill=TARJETA2, outline=""))
        for nombre, x in columnas:
            c.append(cv.create_text(x, 200, anchor="w", text=nombre, fill=TENUE, font=(SEMI, 8)))
        for k, r in enumerate(reversed(self.registro)):
            y = 230 + k * 26
            if k % 2:
                c.append(cv.create_rectangle(36, y - 13, ANCHO_JUEGO - 36, y + 13, fill="#191c24", outline=""))
            color = ORO if r["subio"] else (VERDE if r["superaron_pct"] > 0 else TEXTO)
            valores = (r["generacion"], f"{r['nivel']} {r['nombre']}", f"{r['mejor_lineas']:.0f} / {r['meta']}",
                       f"{r['promedio_lineas']:.0f}", f"{r['superaron_pct']:.0f} %" + ("  ▲" if r["subio"] else ""))
            for (_, x), valor in zip(columnas, valores):
                c.append(cv.create_text(x, y, anchor="w", text=str(valor), fill=color, font=(FUENTE, 10)))
        if not self.registro:
            c.append(cv.create_text(ANCHO_JUEGO / 2, 300, text="aquí aparece cada generación al terminar",
                                    fill=SUTIL, font=(FUENTE, 10)))

    def _dibujar_panel(self):
        self._panel_generacion()
        self._grafica()
        self._panel_pesos()
        self._panel_poblacion()
        self.btn_pausa.texto("Seguir" if self.pausa else "Pausa")
        self.btn_turbo.texto("Animar" if self.turbo else "Turbo")
        self.btn_campeona.texto("Ver la mejor" if self.vista_tipo == "campeona" else "Ver campeona")
        self.btn_humano.texto("Dejar de jugar" if self.vista_tipo == "humano" else "Jugar tú")
        self.lbl_vel.configure(text=f"x{VELOCIDADES[self.i_vel]}")
        n = self.juego.nivel
        self.pie.configure(text=f"En pantalla: {VISTAS[self.vista_tipo]} · nivel {n.numero} {n.nombre} · "
                                f"{n.descripcion}")

    def _encabezado(self, cv, texto, derecha="", color=TENUE):
        cv.create_text(14, 14, anchor="w", text=texto, fill=TENUE, font=(SEMI, 8))
        if derecha:
            cv.create_text(ANCHO_PANEL - 12, 14, anchor="e", text=derecha, fill=color, font=(FUENTE, 8))

    def _barra(self, cv, x, y, ancho, valor, color, alto=6):
        cv.create_rectangle(x, y, x + ancho, y + alto, fill=REJILLA, outline="")
        if valor > 0:
            cv.create_rectangle(x, y, x + ancho * min(max(valor, 0.0), 1.0), y + alto, fill=color, outline="")

    def _ficha(self, cv, x, y, w, etq, valor, color, alto=46):
        cv.create_rectangle(x, y, x + w, y + alto, fill=TARJETA2, outline="")
        cv.create_rectangle(x, y, x + 3, y + alto, fill=color, outline="")
        cv.create_text(x + 11, y + 11, anchor="w", text=etq, fill=TENUE, font=(SEMI, 7))
        cv.create_text(x + 11, y + 31, anchor="w", text=valor, fill=TEXTO, font=(SEMI, 14))

    def _panel_generacion(self):
        cv = self.c_gen
        cv.delete("all")
        e = self.e
        self._encabezado(cv, "ENTRENAMIENTO · CMA-ES", f"σ = {e.cma.sigma:.3f}")
        h = e.historial[-1] if e.historial else None
        datos = (("GENERACIÓN", str(e.generacion), ORO),
                 ("MEJOR", f"{h['mejor_lineas']:.0f} / {h['meta']}" if h else "—", VERDE),
                 ("PROMEDIO", f"{h['promedio_lineas']:.0f}" if h else "—", AZUL),
                 ("SUPERAN", f"{h['superaron_pct']:.0f} %" if h else "—", MORADO))
        ancho = (ANCHO_PANEL - 28 - 18) / 4
        for k, (etq, valor, color) in enumerate(datos):
            self._ficha(cv, 14 + k * (ancho + 6), 26, ancho, etq, valor, color)
        numero = e.nivel_actual
        y = 90
        cv.create_text(14, y, anchor="w", text=f"Nivel {numero}: {obtener_nivel(numero).nombre}", fill=TEXTO,
                       font=(SEMI, 10))
        for k in range(len(NIVELES)):
            x = 214 + k * 18
            superado = e.completada or k + 1 < e.nivel
            col = VERDE if superado else (ORO if k + 1 == numero else REJILLA)
            cv.create_oval(x - 5, y - 5, x + 5, y + 5, fill=col, outline="")
        cv.create_text(ANCHO_PANEL - 12, y, anchor="e", fill=TENUE, font=(FUENTE, 8),
                       text="campaña completa" if e.completada else f"racha {e.racha}/{C.RACHA_PARA_SUBIR}")
        hechas = len(self.pendiente[1]) if self.pendiente else 0
        total = self.pendiente[2] if self.pendiente else e.poblacion
        cv.create_text(14, 111, anchor="w", text=f"individuos evaluados {hechas}/{total}", fill=TEXTO,
                       font=(FUENTE, 9))
        self._barra(cv, 170, 108, ANCHO_PANEL - 184, hechas / max(total, 1), AZUL)
        if h:
            demos = len(e.demo_k)
            cv.create_text(14, 132, anchor="w", fill=TENUE, font=(FUENTE, 8),
                           text=f"la mejor terminó así: {h['motivo_lider']}"
                                + (f" · {demos} jugadas tuyas en la memoria" if demos else ""))

    def _grafica(self):
        cv = self.c_graf
        cv.delete("all")
        self._encabezado(cv, "LÍNEAS POR GENERACIÓN (% DE LA META DEL NIVEL)")
        xl = ANCHO_PANEL - 12
        for texto, color in (("promedio", AZUL), ("mejor", ORO)):
            t = cv.create_text(xl, 14, anchor="e", text=texto, fill=TENUE, font=(FUENTE, 8))
            x0 = cv.bbox(t)[0]
            cv.create_line(x0 - 18, 14, x0 - 5, 14, fill=color, width=2)
            xl = x0 - 26
        datos = self.e.historial[-150:]
        x0, y0, x1, y1 = 40, 30, ANCHO_PANEL - 12, 98
        for valor in (0, 50, 100):
            y = y1 - (y1 - y0) * valor / 100
            cv.create_line(x0, y, x1, y, fill=REJILLA)
            cv.create_text(x0 - 6, y, anchor="e", text=f"{valor}%", fill=SUTIL, font=(FUENTE, 7))
        if len(datos) < 2:
            cv.create_text((x0 + x1) / 2, (y0 + y1) / 2, text="la gráfica aparece al terminar generaciones",
                           fill=SUTIL, font=(FUENTE, 9))
            return

        def punto(i, valor, meta):
            return x0 + (x1 - x0) * i / (len(datos) - 1), y1 - (y1 - y0) * min(valor / meta, 1.0)

        ultima = -100
        for i in range(1, len(datos)):
            if datos[i]["nivel"] != datos[i - 1]["nivel"]:
                x = punto(i, 0, 1)[0]
                cv.create_line(x, y0, x, y1, fill=SUTIL, dash=(2, 3))
                if x - ultima > 18:
                    cv.create_text(x + 3, y0, anchor="nw", text=f"N{datos[i]['nivel']}", fill=TENUE, font=(FUENTE, 7))
                    ultima = x
        mejor = [punto(i, r["mejor_lineas"], r["meta"]) for i, r in enumerate(datos)]
        area = [(x0, y1)] + mejor + [(x1, y1)]
        cv.create_polygon(*[c for q in area for c in q], fill=TM.mezcla(ORO, TARJETA, 0.88), outline="")
        cv.create_line(*[c for i, r in enumerate(datos) for c in punto(i, r["promedio_lineas"], r["meta"])],
                       fill=AZUL, width=2)
        cv.create_line(*[c for q in mejor for c in q], fill=ORO, width=2)
        xu, yu = mejor[-1]
        cv.create_oval(xu - 3, yu - 3, xu + 3, yu + 3, fill=ORO, outline=TARJETA)
        cv.create_text(x0, y1 + 10, anchor="w", text=f"gen {datos[0]['generacion']}", fill=SUTIL, font=(FUENTE, 7))
        cv.create_text(x1, y1 + 10, anchor="e", text=f"gen {datos[-1]['generacion']}", fill=SUTIL, font=(FUENTE, 7))

    def _panel_pesos(self):
        cv = self.c_pesos
        cv.delete("all")
        humano = self.vista_tipo == "humano"
        pesos = self.e.cma.m if humano else self.pesos
        self._encabezado(cv, "LO QUE VALORA LA IA" + (" (MEDIA ACTUAL)" if humano else " EN PANTALLA"),
                         "◀ evita   busca ▶")
        imp = pesos * ESCALA
        imp = imp / max(np.abs(imp).max(), 1e-9)
        centro = 290
        for k, (nombre, valor) in enumerate(zip(CORTO, imp)):
            y = 34 + k * 14.5
            cv.create_text(14, y, anchor="w", text=nombre, fill=TEXTO, font=(FUENTE, 8))
            cv.create_rectangle(centro - 108, y - 4, centro + 108, y + 4, fill=REJILLA, outline="")
            color = VERDE if valor > 0 else ROJO
            cv.create_rectangle(centro, y - 4, centro + 108 * valor, y + 4, fill=color, outline="")
            cv.create_text(ANCHO_PANEL - 12, y, anchor="e", text=f"{pesos[k]:+.3f}", fill=TENUE, font=(MONO, 8))
        cv.create_line(centro, 26, centro, 142, fill=SUTIL)

    def _panel_poblacion(self):
        cv = self.c_pobl
        cv.delete("all")
        e = self.e
        apt = e.ultimas_aptitudes
        self._encabezado(cv, "POBLACIÓN · APTITUD", f"oro: los {e.cma.mu} que guían la siguiente generación")
        if not apt:
            cv.create_text(ANCHO_PANEL / 2, 46, text="aún no termina la primera generación", fill=SUTIL,
                           font=(FUENTE, 9))
            return
        maximo = max(max(apt), 1e-9)
        ancho = (ANCHO_PANEL - 28) / len(apt)
        for k, a in enumerate(apt):
            x = 14 + k * ancho
            alto = 38 * max(a, 0) / maximo
            color = ORO if k < e.cma.mu else TM.mezcla(AZUL, TARJETA, 0.35)
            cv.create_rectangle(x + 1, 66 - alto, x + ancho - 2, 66, fill=color, outline="")

    def ejecutar(self):
        self.raiz.mainloop()
