import base64
import math
import multiprocessing as mp
import random
import time
import tkinter as tk
from tkinter import messagebox

import cerebro as B
import config as C
import graficos as G
import tema as TM
from cerebro import ControladorRed, ControladorTeclado
from evolucion import bajar_prioridad, evaluar
from grabador import BotonGrabar
from misiones import NOMBRES, NUMERO_MISIONES, cargar_mision
from mundo import Partida
from sensores import GRUPOS

E = C.ESCALA
W, H = C.ANCHO_VISTA, C.ALTO_VISTA
ANCHO_JUEGO, ALTO_JUEGO = W * E, H * E
ANCHO_PANEL = 470
FONDO, TARJETA, TARJETA2, BORDE = TM.FONDO, TM.TARJETA, TM.TARJETA2, TM.BORDE
TEXTO, TENUE, SUTIL, REJILLA = TM.TEXTO, TM.TENUE, TM.SUTIL, TM.REJILLA
ORO, AZUL, VERDE, MORADO = TM.ORO, TM.AZUL, TM.VERDE, TM.MORADO
ROJO = "#ff4a3a"
CIELO = "#7fc4ff"
FUENTE, SEMI, MONO = TM.FAMILIA, TM.SEMI, "Consolas"
VELOCIDADES = (1, 2, 4, 8)
TECLAS = {"Left": "izquierda", "Right": "derecha", "Up": "arriba", "Down": "abajo", "x": "disparar",
          "X": "disparar", "space": "disparar", "z": "rizo", "Z": "rizo"}
NOMBRE_ARMA = {1: "doble", 2: "cuádruple", 3: "abanico"}
VISTAS = {"generacion": "toda la generación en vivo: cada avión es un individuo",
          "campeona": "la campeona guardada",
          "humano": "tú · la red aprende de tus jugadas"}
SOMBRA = (9, 13)


class Aplicacion:
    def __init__(self, entrenador, vista="generacion", turbo=False):
        self.e = entrenador
        self.raiz = tk.Tk()
        self.raiz.title("1942 evolutivo — pilotos que aprenden por generaciones")
        self.raiz.configure(bg=FONDO)
        self.raiz.resizable(False, False)
        self.vista_tipo = vista
        self.turbo = turbo and vista != "humano"
        self.mision_vista = None
        self.teclas = set()
        self.pausa = False
        self.i_vel = 0
        self.aviso = ("", 0.0)
        self.registro = []
        self.escenarios = {}
        self.items = []
        self.imagen_item = []
        self.visibles = 0
        self.pendiente = None
        self.fin_vista = None
        self.controles = []
        self.capa = []
        self.mundos = []
        self.instantanea = None
        self.seguido = 0
        self.gen_vista = 0
        self.fx_fantasmas = []
        self.t_previo = time.perf_counter()
        self.acumulado = 0.0
        self.t_panel = 0.0
        self.siguiente_cuadro = time.perf_counter()
        self.turbo_t0 = time.perf_counter()
        self.turbo_gens = 0
        self.pool = mp.Pool(C.PROCESOS, initializer=bajar_prioridad)
        self._cargar_sprites()
        self._construir()
        self._teclas()
        self._lanzar()
        self._nueva_vista()
        self.raiz.after(C.CUADRO_MS, self._ciclo)

    def _foto(self, rgba):
        return tk.PhotoImage(data=base64.b64encode(G.png(rgba)))

    def _cargar_sprites(self):
        self.sprites, self.tam = {}, {}
        for nombre, img in G.generar().items():
            self.tam[nombre] = (img.shape[1] / E, img.shape[0] / E)
            self.sprites[nombre] = self._foto(img)

    def _escenario(self, tema):
        if tema not in self.escenarios:
            imgs = G.escenario(tema)
            fotos = {"oceano": tk.PhotoImage(data=G.ppm(imgs.pop("oceano")))}
            for nombre, img in imgs.items():
                self.tam[nombre] = (img.shape[1] / E, img.shape[0] / E)
                fotos[nombre] = self._foto(img)
            self.escenarios[tema] = fotos
        return self.escenarios[tema]

    def _construir(self):
        izquierda = tk.Frame(self.raiz, bg=FONDO)
        izquierda.pack(side="left", anchor="n", padx=(14, 8), pady=12)
        self.juego = tk.Canvas(izquierda, width=ANCHO_JUEGO, height=ALTO_JUEGO, bg="#0b1a33",
                               highlightthickness=1, highlightbackground=BORDE)
        self.juego.pack()
        self.mar = [self.juego.create_image(0, 0, anchor="nw") for _ in range(2)]
        self.pie = tk.Label(izquierda, bg=FONDO, fg=TENUE, font=(FUENTE, 9), anchor="w", justify="left",
                            wraplength=ANCHO_JUEGO, width=1)
        self.pie.pack(fill="x", pady=(6, 0))

        derecha = tk.Frame(self.raiz, bg=FONDO)
        derecha.pack(side="left", anchor="n", padx=(8, 14), pady=12)
        titulo = tk.Canvas(derecha, width=ANCHO_PANEL, height=50, bg=FONDO, highlightthickness=0)
        titulo.pack(anchor="w")
        titulo.create_image(24, 22, image=self.sprites["jugador0"])
        t = titulo.create_text(62, 0, anchor="nw", text="1942", fill=CIELO, font=(SEMI, 22))
        titulo.create_text(titulo.bbox(t)[2] + 8, 9, anchor="nw", text="EVOLUTIVO", fill=TEXTO, font=(SEMI, 13))
        capas = " › ".join(str(n) for n in B.CAPAS)
        titulo.create_text(63, 36, anchor="nw", fill=TENUE, font=(FUENTE, 8),
                           text=f"red {capas} · estrategias evolutivas · {C.PROCESOS} procesos")
        self.c_gen = self._tarjeta(derecha, 150)
        self.c_graf = self._tarjeta(derecha, 118)
        self.c_vista = self._tarjeta(derecha, 150)
        self.c_red = self._tarjeta(derecha, 62)
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
        ayuda = ("Espacio pausa · T turbo · +/− velocidad · S seguir al líder · C campeona (←/→ misión) · G guardar\n"
                 "N reiniciar · J jugar tú: flechas mueven, X o Espacio dispara, Z rizo, P pausa · Esc salir")
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
            if k in TECLAS:
                self.teclas.add(TECLAS[k])
            acciones = {"p": self.alternar_pausa, "P": self.alternar_pausa, "Escape": self.salir,
                        "j": lambda: self.cambiar_vista("humano"), "J": lambda: self.cambiar_vista("humano")}
        else:
            acciones = {
                "space": self.alternar_pausa, "Escape": self.salir, "t": self.alternar_turbo,
                "c": lambda: self.cambiar_vista("campeona"), "j": lambda: self.cambiar_vista("humano"),
                "n": self.reiniciar, "g": self.guardar, "plus": lambda: self.cambiar_vel(1),
                "equal": lambda: self.cambiar_vel(1), "KP_Add": lambda: self.cambiar_vel(1),
                "minus": lambda: self.cambiar_vel(-1), "KP_Subtract": lambda: self.cambiar_vel(-1),
                "Left": lambda: self.cambiar_mision_vista(-1), "Right": lambda: self.cambiar_mision_vista(1),
                "s": self.seguir_lider,
            }
        accion = acciones.get(k) or acciones.get(k.lower())
        if accion:
            accion()

    def _tecla_arriba(self, ev):
        if ev.keysym in TECLAS:
            self.teclas.discard(TECLAS[ev.keysym])

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
        self.t_previo = time.perf_counter()

    def alternar_turbo(self):
        self.turbo = not self.turbo
        self.turbo_t0 = time.perf_counter()
        self.turbo_gens = 0
        if self.turbo and self.vista_tipo == "humano":
            self.vista_tipo = "generacion"
            self._nueva_vista()

    def cambiar_vel(self, delta):
        self.i_vel = max(0, min(len(VELOCIDADES) - 1, self.i_vel + delta))

    def cambiar_vista(self, tipo):
        self.vista_tipo = "generacion" if self.vista_tipo == tipo else tipo
        self.mision_vista = None
        self.teclas.clear()
        if self.vista_tipo != "generacion":
            self.turbo = False
        self._nueva_vista()

    def cambiar_mision_vista(self, delta):
        if self.vista_tipo != "campeona":
            return
        actual = self.mision_vista or self.vista.numero
        self.mision_vista = max(1, min(NUMERO_MISIONES, actual + delta))
        self._nueva_vista()

    def reiniciar(self):
        pausa_previa, self.pausa = self.pausa, True
        ok = messagebox.askyesno("Reiniciar desde cero",
                                 "Se borrará todo lo aprendido (estado, campeonas, historial y tus jugadas) "
                                 "y la evolución empezará otra vez en la generación 1.\n\n¿Continuar?",
                                 parent=self.raiz)
        self.pausa = pausa_previa
        if ok:
            if self.controles and isinstance(self.controles[0], ControladorTeclado):
                self.controles[0].demo = []
            self.e.reiniciar()
            self.pendiente = None
            self.registro.clear()
            self._nueva_vista()
            self.avisar("Evolución reiniciada desde cero")

    def _aprender_humano(self, sin_vidas=False):
        control = self.controles[0] if self.controles else None
        if not isinstance(control, ControladorTeclado):
            return 0
        datos = control.muestras(sin_vidas)
        if datos is None or len(datos[0]) < 30:
            return 0
        self.e.aprender_de_humano(*datos, self.vista.numero)
        self.pendiente = None
        return len(datos[0])

    def _fin_vista(self, v):
        if self.vista_tipo != "humano":
            return
        aprendidas = self._aprender_humano(v.motivo == "derribado")
        if v.superada:
            siguiente = v.numero % NUMERO_MISIONES + 1
            self.mision_vista = siguiente
            self._escenario(cargar_mision(siguiente).tema)
            texto = f"¡{v.mision.nombre} cumplida! Siguiente: {NOMBRES[siguiente - 1]}"
        else:
            texto = "Otra vez la misma misión"
        if aprendidas:
            texto += f" · la red aprendió de {aprendidas} jugadas"
        self.avisar(texto)

    def _nueva_vista(self):
        aprendidas = self._aprender_humano()
        if aprendidas:
            self.avisar(f"La red aprendió de {aprendidas} jugadas tuyas")
        e = self.e
        self.info_vista = None
        self.mundos = []
        self.fx_fantasmas = []
        if self.vista_tipo == "generacion" and self.instantanea:
            ins = self.instantanea
            self.gen_vista = ins["gen"]
            self.mundos = [Partida(ins["mision"], [ControladorRed(w)], ins["semilla"]) for w in ins["pesos"]]
            self.muertes_previas = [0] * len(self.mundos)
            self.t_previo = time.perf_counter()
            self.acumulado = 0.0
            self._seguir(self.mundos[0])
            self.fin_vista = None
            return
        if self.vista_tipo == "campeona":
            numero = self.mision_vista or e.mision_actual
            campeon = e.campeon(numero)
            pesos = campeon[0] if campeon else e.mejores_pesos()
            self.info_vista = campeon[1] if campeon else None
        else:
            numero = (self.mision_vista if self.vista_tipo == "humano" else None) or e.mision_actual
            pesos = e.mejores_pesos()
        control = ControladorTeclado(self.teclas) if self.vista_tipo == "humano" else ControladorRed(pesos)
        self.controles = [control]
        self.vista = Partida(numero, self.controles, random.randrange(1 << 30), limites=self.vista_tipo != "humano")
        self.fin_vista = None

    def _lanzar(self):
        tareas = self.e.tareas()
        self.instantanea = {"gen": self.e.generacion, "mision": tareas[0][1], "semilla": tareas[0][3],
                            "pesos": [t[2].copy() for t in tareas]}
        self.pendiente = (self.pool.imap_unordered(evaluar, tareas), [], len(tareas))

    def _seguir(self, mundo):
        self.vista = mundo
        self.controles = mundo.controladores
        self.seguido = self.mundos.index(mundo) if mundo in self.mundos else 0

    @staticmethod
    def _merito(m):
        j = m.jugadores[0]
        return (j.activo, not m.terminada or m.superada, m.progreso(), j.vidas, j.puntos)

    def seguir_lider(self):
        if self.vista_tipo == "generacion" and self.mundos:
            self._seguir(max(self.mundos, key=self._merito))

    def vivos(self):
        return sum(1 for m in self.mundos if not m.terminada)

    def _avanzar_generacion(self, vel, ahora):
        dt = min(max(ahora - self.t_previo, 0.0), 0.1)
        self.t_previo = ahora
        self.acumulado = min(self.acumulado + dt * C.TICKS_POR_SEGUNDO * vel, vel * 3)
        pasos = int(self.acumulado)
        self.acumulado -= pasos
        if self.vivos() == 0:
            if self.fin_vista is None:
                self.fin_vista = ahora
            elif ahora - self.fin_vista > 2.5:
                self._nueva_vista()
            return
        limite = ahora + 0.024
        for _ in range(pasos):
            for k, m in enumerate(self.mundos):
                if m.terminada:
                    continue
                m.paso()
                if m is not self.vista:
                    j = m.jugadores[0]
                    if j.muertes != self.muertes_previas[k]:
                        self.muertes_previas[k] = j.muertes
                        self.fx_fantasmas.append([j.x, j.y, self.vista.t])
            if time.perf_counter() > limite:
                break
        v = self.vista
        if (v.terminada or v.jugadores[0].fuera) and self.vivos():
            self._seguir(max(self.mundos, key=self._merito))
        self.fx_fantasmas = [f for f in self.fx_fantasmas if self.vista.t - f[2] < 24]

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
            print(f"gen {r['generacion']:5d} · misión {r['mision']} {r['nombre']:<15} · mejor {r['mejor_progreso']:5.1f} % · "
                  f"promedio {r['promedio_progreso']:5.1f} % · cumplieron {r['superaron_pct']:4.1f} % · "
                  f"{r['motivo_lider']}", flush=True)
        except (OSError, ValueError):
            pass
        if r["subio"]:
            texto = ("¡Campaña completa! Ahora repasa todas las misiones" if self.e.completada
                     else f"¡{r['nombre']} cumplida! Siguiente: {NOMBRES[self.e.mision_actual - 1]}")
            self.avisar(texto)
        self.pendiente = None
        self._lanzar()

    def _ciclo(self):
        ahora = time.perf_counter()
        try:
            self._recolectar()
            v = self.vista
            if not self.pausa and not self.turbo and self.mundos:
                self._avanzar_generacion(VELOCIDADES[self.i_vel], ahora)
            elif not self.pausa and not self.turbo:
                if v.terminada:
                    if self.fin_vista is None:
                        self.fin_vista = ahora
                        self._fin_vista(v)
                    elif ahora - self.fin_vista > 2.5:
                        self._nueva_vista()
                else:
                    pasos = VELOCIDADES[self.i_vel] if self.vista_tipo != "humano" else 1
                    for _ in range(pasos):
                        v.paso()
                        if v.terminada:
                            break
            self._dibujar()
            if ahora - self.t_panel > 0.25:
                self.t_panel = ahora
                self._dibujar_panel()
            self.siguiente_cuadro = max(self.siguiente_cuadro + 1 / C.TICKS_POR_SEGUNDO, ahora - 0.1)
            espera = max(1, int((self.siguiente_cuadro - time.perf_counter()) * 1000))
            self.raiz.after(espera, self._ciclo)
        except tk.TclError:
            pass

    def _item(self, i):
        while len(self.items) <= i:
            self.items.append(self.juego.create_image(0, 0, anchor="nw", state="hidden"))
            self.imagen_item.append(None)
        return self.items[i]

    def _dibujar(self):
        cv = self.juego
        for t in self.capa:
            cv.delete(t)
        self.capa = []
        v = self.vista
        if self.turbo:
            for i in self.mar:
                cv.itemconfigure(i, state="hidden")
            for i in range(self.visibles):
                cv.itemconfigure(self.items[i], state="hidden")
            self.visibles = 0
            self._pantalla_turbo()
            return
        esc = self._escenario(v.mision.tema)
        desplazamiento = (v.scroll * E) % ALTO_JUEGO
        for k, i in enumerate(self.mar):
            cv.itemconfigure(i, image=esc["oceano"], state="normal")
            cv.coords(i, 0, round(desplazamiento - k * ALTO_JUEGO))
        lista = self._dibujables(v, esc)
        for i, (nombre, x, y) in enumerate(lista):
            item = self._item(i)
            if self.imagen_item[i] != nombre:
                imagen = esc[nombre] if nombre in esc else self.sprites[nombre]
                cv.itemconfigure(item, image=imagen)
                self.imagen_item[i] = nombre
            cv.coords(item, round(x * E), round(y * E))
            if i >= self.visibles:
                cv.itemconfigure(item, state="normal")
        for i in range(len(lista), self.visibles):
            cv.itemconfigure(self.items[i], state="hidden")
        self.visibles = len(lista)
        self._hud(v)

    def _dibujables(self, p, esc):
        lista = []
        t = p.t

        def centrar(nombre, x, y):
            w, h = self.tam[nombre]
            if -w < x + w / 2 and x - w / 2 < W + w and -h < y + h / 2 and y - h / 2 < H + h:
                lista.append((nombre, x - w / 2, y - h / 2))

        if p.scroll < H + 120:
            y = H + 25 + p.scroll
            centrar("sombra_portaaviones", W / 2 + 4, y + 6)
            centrar("portaaviones", W / 2, y)
        for yw, x, variante, pista in p.mision.islas:
            y = H + p.scroll - yw
            if -140 < y < H + 140:
                centrar(f"isla{variante}{int(pista)}", x, y)
        planos = []
        for e in p.enemigos:
            nombre = self._nombre_enemigo(e, p)
            if nombre:
                planos.append((nombre, e.x, e.y, e.tipo))
        j = p.jugadores[0]
        nombre_j = None
        if j.activo and not ((j.invulnerable > 0) and (t // 2) % 2):
            if j.rodando:
                k = min(7, (C.DURACION_RIZO - j.rodando) * 8 // C.DURACION_RIZO)
                nombre_j = f"rizo{k}"
            else:
                nombre_j = f"jugador{(t // 2) % 2}"
        for nombre, x, y, tipo in planos:
            if tipo != "torreta":
                d = 1.8 if tipo in ("jefe", "pesado") else 1.0
                centrar("sombra_" + nombre.replace("_golpe", ""), x + SOMBRA[0] * d, y + SOMBRA[1] * d)
        if nombre_j:
            centrar("sombra_" + nombre_j, j.x + SOMBRA[0] * 1.4, j.y + SOMBRA[1] * 1.4)
            for ex, ey in j.posiciones_escoltas():
                centrar("sombra_escolta", ex + SOMBRA[0] * 1.4, ey + SOMBRA[1] * 1.4)
        for yw, x, variante in p.mision.nubes:
            y = H + p.scroll * 1.6 - yw
            if -80 < y < H + 80:
                centrar(f"nube{variante}", x, y)
        for it in p.items:
            centrar(f"pow_{it.letra}{(t // 6) % 2}", it.x, it.y)
        for nombre, x, y, tipo in planos:
            if tipo != "torreta":
                centrar(nombre, x, y)
        for nombre, x, y, tipo in planos:
            if tipo == "torreta":
                centrar(nombre, x, y)
        for m in self.mundos:
            if m is not p and not m.terminada:
                o = m.jugadores[0]
                if o.activo:
                    centrar("fantasma", o.x, o.y)
        for x, y, t0 in self.fx_fantasmas:
            edad = t - t0
            if 0 <= edad < 24:
                centrar(f"chica{min(5, edad // 4)}", x, y)
        if nombre_j:
            for ex, ey in j.posiciones_escoltas():
                centrar("escolta", ex, ey)
            centrar(nombre_j, j.x, j.y)
        for b in p.balas:
            centrar("bala_j" if b.dueno is not None else "bala_e", b.x, b.y)
        for x, y, tipo, t0 in p.efectos:
            edad = t - t0
            if tipo == "grande":
                if edad < 32:
                    centrar(f"grande{min(7, edad // 4)}", x, y)
            elif tipo == "chica":
                if edad < 24:
                    centrar(f"chica{min(5, edad // 4)}", x, y)
            elif edad < 12:
                centrar(f"chica{min(5, edad // 2)}", x, y)
        return lista

    def _nombre_enemigo(self, e, p):
        if e.tipo == "caza":
            k = round(e.angulo / (2 * math.pi / G.ANGULOS)) % G.ANGULOS
            return f"{'rojo' if e.datos.get('roja') else 'caza'}{k}"
        if e.tipo == "torreta":
            obj = p.objetivo()
            a = math.atan2(obj.y - e.y, obj.x - e.x) if obj else math.pi / 2
            return f"torreta{round(a / (2 * math.pi / G.ANGULOS)) % G.ANGULOS}"
        return e.tipo + ("_golpe" if e.golpe and (p.t // 2) % 2 else "")

    def _texto(self, x, y, texto, color=TEXTO, tam=12, ancla="nw"):
        cv = self.juego
        fuente = (SEMI, tam)
        for dx, dy in ((2, 2), (-1, 0), (1, 0), (0, -1), (0, 1)):
            self.capa.append(cv.create_text(x + dx, y + dy, text=texto, fill="#000000", font=fuente, anchor=ancla))
        self.capa.append(cv.create_text(x, y, text=texto, fill=color, font=fuente, anchor=ancla))

    def _franja(self, y0, y1):
        cv = self.juego
        self.capa.append(cv.create_rectangle(0, y0, ANCHO_JUEGO, y1, fill="#000000", outline="", stipple="gray50"))
        for y in (y0, y1):
            self.capa.append(cv.create_line(0, y, ANCHO_JUEGO, y, fill=ORO))

    def _imagen(self, nombre, x, y, ancla="nw"):
        self.capa.append(self.juego.create_image(x, y, image=self.sprites[nombre], anchor=ancla))

    def _hud(self, v):
        cv = self.juego
        j = v.jugadores[0]
        self._texto(12, 8, "1UP", ROJO, 11)
        self._texto(52, 8, f"{j.puntos:08d}", TEXTO, 11)
        if self.mundos:
            self._texto(12, 30, f"GENERACIÓN {self.gen_vista} · {self.vivos()} DE {len(self.mundos)} EN VUELO",
                        CIELO, 9)
            self._texto(12, 48, f"cámara: individuo #{self.seguido + 1}", TENUE, 8)
        self._texto(ANCHO_JUEGO - 12, 8, f"MISIÓN {v.numero} · {v.mision.nombre.upper()}", ORO, 10, "ne")
        x0, x1, y = ANCHO_JUEGO - 162, ANCHO_JUEGO - 12, 30
        self.capa.append(cv.create_rectangle(x0 - 1, y - 1, x1 + 1, y + 5, fill="#000000", outline="#3a4150"))
        self.capa.append(cv.create_rectangle(x0, y, x0 + (x1 - x0) * v.progreso(), y + 4, fill=CIELO, outline=""))
        vidas = max(j.vidas - (0 if j.muerto or j.fuera else 1), 0)
        for k in range(min(vidas, 6)):
            self._imagen("vida", 12 + k * 30, ALTO_JUEGO - 30)
        for k in range(min(j.rizos, 6)):
            self._imagen("icono_rizo", 12 + k * 26, ALTO_JUEGO - 58)
        texto_arma = NOMBRE_ARMA[j.arma] + (f" · {j.escoltas} escoltas" if j.escoltas else "")
        self._texto(ANCHO_JUEGO - 12, ALTO_JUEGO - 30, f"ARMA {texto_arma.upper()}", TEXTO, 9, "ne")
        centro = ANCHO_JUEGO / 2
        if v.jefe_activo and not v.jefe_vencido and v.jefe is not None:
            vida = max(v.jefe.hp, 0) / v.jefe.hp_max
            w, y = 300, 62
            self._texto(centro, y - 16, v.mision.jefe["nombre"].upper(), ROJO, 10, "center")
            self.capa.append(cv.create_rectangle(centro - w / 2 - 3, y - 3, centro + w / 2 + 3, y + 9,
                                                 fill="#000000", outline=TEXTO))
            if vida > 0:
                self.capa.append(cv.create_rectangle(centro - w / 2, y, centro - w / 2 + w * vida, y + 6,
                                                     fill=ROJO, outline=""))
        if v.t < 90:
            self._franja(238, 330)
            self._texto(centro, 268, f"MISIÓN {v.numero}", ORO, 26, "center")
            self._texto(centro, 306, v.mision.nombre.upper(), TEXTO, 15, "center")
        if self.mundos and self.vivos() == 0:
            cumplieron = sum(m.superada for m in self.mundos)
            self._franja(ALTO_JUEGO / 2 - 34, ALTO_JUEGO / 2 + 34)
            self._texto(centro, ALTO_JUEGO / 2 - 6, f"FIN DE LA GENERACIÓN {self.gen_vista}", ORO, 20, "center")
            self._texto(centro, ALTO_JUEGO / 2 + 22, f"{cumplieron} de {len(self.mundos)} cumplieron la misión",
                        TEXTO, 10, "center")
        elif v.terminada and not self.mundos:
            texto = "MISIÓN CUMPLIDA" if v.superada else ("DERRIBADO" if v.motivo == "derribado" else v.motivo.upper())
            self._franja(ALTO_JUEGO / 2 - 34, ALTO_JUEGO / 2 + 34)
            self._texto(centro, ALTO_JUEGO / 2 - 6, texto, ORO if v.superada else ROJO, 24, "center")
            self._texto(centro, ALTO_JUEGO / 2 + 22, f"{j.bajas} derribos · {j.puntos} puntos", TEXTO, 10, "center")
        texto, t0 = self.aviso
        if texto and time.perf_counter() - t0 < 4:
            self._franja(ALTO_JUEGO - 112, ALTO_JUEGO - 76)
            self._texto(centro, ALTO_JUEGO - 94, texto, ORO, 12, "center")
        if self.pausa:
            self._franja(ALTO_JUEGO / 2 - 110, ALTO_JUEGO / 2 - 50)
            self._texto(centro, ALTO_JUEGO / 2 - 80, "PAUSA", AZUL, 24, "center")

    def _pantalla_turbo(self):
        cv = self.juego
        c = self.capa
        c.append(cv.create_rectangle(0, 0, ANCHO_JUEGO, ALTO_JUEGO, fill=FONDO, outline=""))
        c.append(cv.create_rectangle(20, 20, ANCHO_JUEGO - 20, ALTO_JUEGO - 20, fill=TARJETA, outline=BORDE))
        c.append(cv.create_text(44, 58, anchor="w", text="MODO TURBO", fill=ORO, font=(SEMI, 22)))
        c.append(cv.create_text(44, 88, anchor="w", fill=TENUE, font=(FUENTE, 10),
                                text="entrenando sin animar · T para volver a ver"))
        minutos = max(time.perf_counter() - self.turbo_t0, 1e-6) / 60
        e = self.e
        datos = (("GENERACIÓN", str(e.generacion), ORO),
                 ("MISIÓN", f"{e.mision_actual} · {NOMBRES[e.mision_actual - 1]}", TEXTO),
                 ("RITMO", f"{self.turbo_gens / minutos:.1f} gen/min", AZUL))
        ancho = (ANCHO_JUEGO - 88 - 2 * 8) / 3
        for k, (etq, valor, color) in enumerate(datos):
            x = 44 + k * (ancho + 8)
            c.append(cv.create_rectangle(x, 110, x + ancho, 166, fill=TARJETA2, outline=""))
            c.append(cv.create_rectangle(x, 110, x + 3, 166, fill=color, outline=""))
            c.append(cv.create_text(x + 12, 124, anchor="w", text=etq, fill=TENUE, font=(SEMI, 7)))
            c.append(cv.create_text(x + 12, 148, anchor="w", text=valor, fill=TEXTO, font=(SEMI, 11)))
        columnas = (("GEN", 44), ("MISIÓN", 104), ("MEJOR", 290), ("PROM.", 380), ("CUMPLEN", 470))
        c.append(cv.create_rectangle(36, 188, ANCHO_JUEGO - 36, 212, fill=TARJETA2, outline=""))
        for nombre, x in columnas:
            c.append(cv.create_text(x, 200, anchor="w", text=nombre, fill=TENUE, font=(SEMI, 8)))
        for k, r in enumerate(reversed(self.registro)):
            y = 230 + k * 26
            if k % 2:
                c.append(cv.create_rectangle(36, y - 13, ANCHO_JUEGO - 36, y + 13, fill="#191c24", outline=""))
            color = ORO if r["subio"] else (VERDE if r["superaron_pct"] > 0 else TEXTO)
            valores = (r["generacion"], f"{r['mision']} {r['nombre']}", f"{r['mejor_progreso']:.0f} %",
                       f"{r['promedio_progreso']:.0f} %", f"{r['superaron_pct']:.0f} %" + ("  ▲" if r["subio"] else ""))
            for (_, x), valor in zip(columnas, valores):
                c.append(cv.create_text(x, y, anchor="w", text=str(valor), fill=color, font=(FUENTE, 10)))
        if not self.registro:
            c.append(cv.create_text(ANCHO_JUEGO / 2, 300, text="aquí aparece cada generación al terminar",
                                    fill=SUTIL, font=(FUENTE, 10)))

    def _dibujar_panel(self):
        self._panel_generacion()
        self._grafica()
        self._panel_vista()
        self._panel_red()
        self.btn_pausa.texto("Seguir" if self.pausa else "Pausa")
        self.btn_turbo.texto("Animar" if self.turbo else "Turbo")
        self.btn_campeona.texto("Ver generación" if self.vista_tipo == "campeona" else "Ver campeona")
        self.btn_humano.texto("Dejar de jugar" if self.vista_tipo == "humano" else "Jugar tú")
        self.lbl_vel.configure(text=f"x{VELOCIDADES[self.i_vel]}")
        m = self.vista.mision
        self.pie.configure(text=f"En pantalla: {VISTAS[self.vista_tipo]} · misión {m.numero} {m.nombre} · "
                                f"{m.descripcion}")

    def _encabezado(self, cv, texto, derecha="", color=TENUE):
        cv.create_text(14, 14, anchor="w", text=texto, fill=TENUE, font=(SEMI, 8))
        if derecha:
            cv.create_text(ANCHO_PANEL - 12, 14, anchor="e", text=derecha, fill=color, font=(FUENTE, 8))

    def _fila(self, cv, x, y, etiqueta, valor, color=TEXTO, ancho=210):
        cv.create_text(x, y, anchor="w", text=etiqueta, fill=TENUE, font=(FUENTE, 9))
        cv.create_text(x + ancho, y, anchor="e", text=valor, fill=color, font=(SEMI, 9))

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
        self._encabezado(cv, "ENTRENAMIENTO · 1 PILOTO", f"σ = {e.sigma:.3f}")
        h = e.historial[-1] if e.historial else None
        datos = (("GENERACIÓN", str(e.generacion), ORO),
                 ("MEJOR AVANCE", f"{h['mejor_progreso']:.0f} %" if h else "—", VERDE),
                 ("PROMEDIO", f"{h['promedio_progreso']:.0f} %" if h else "—", AZUL),
                 ("CUMPLIERON", f"{h['superaron_pct']:.0f} %" if h else "—", MORADO))
        ancho = (ANCHO_PANEL - 28 - 18) / 4
        for k, (etq, valor, color) in enumerate(datos):
            self._ficha(cv, 14 + k * (ancho + 6), 26, ancho, etq, valor, color)
        numero = e.mision_actual
        y = 90
        cv.create_text(14, y, anchor="w", text=f"Misión {numero}: {NOMBRES[numero - 1]}", fill=TEXTO,
                       font=(SEMI, 10))
        for k in range(NUMERO_MISIONES):
            x = 214 + k * 18
            cumplida = e.completada or k + 1 < e.mision
            col = VERDE if cumplida else (ORO if k + 1 == numero else REJILLA)
            cv.create_oval(x - 5, y - 5, x + 5, y + 5, fill=col, outline="")
        cv.create_text(ANCHO_PANEL - 12, y, anchor="e", fill=TENUE, font=(FUENTE, 8),
                       text="campaña completa" if e.completada else f"racha {e.racha}/{C.RACHA_PARA_SUBIR}")
        hechas = len(self.pendiente[1]) if self.pendiente else 0
        cv.create_text(14, 111, anchor="w", text=f"partidas evaluadas {hechas}/{e.n}", fill=TEXTO, font=(FUENTE, 9))
        self._barra(cv, 170, 108, ANCHO_PANEL - 184, hechas / e.n, AZUL)
        if h:
            demos = len(e.demo_x)
            cv.create_text(14, 132, anchor="w", fill=TENUE, font=(FUENTE, 8),
                           text=f"muertes prom. {h['muertes_promedio']:.1f} · esquivó {h['esquives_lider']} balas · "
                                f"terminó: {h['motivo_lider']}" + (f" · {demos} jugadas tuyas" if demos else ""))

    def _grafica(self):
        cv = self.c_graf
        cv.delete("all")
        self._encabezado(cv, "AVANCE EN LA MISIÓN POR GENERACIÓN")
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

        def punto(i, valor):
            return x0 + (x1 - x0) * i / (len(datos) - 1), y1 - (y1 - y0) * valor / 100

        ultima = -100
        for i in range(1, len(datos)):
            if datos[i]["mision"] != datos[i - 1]["mision"]:
                x = punto(i, 0)[0]
                cv.create_line(x, y0, x, y1, fill=SUTIL, dash=(2, 3))
                if x - ultima > 18:
                    cv.create_text(x + 3, y0, anchor="nw", text=f"M{datos[i]['mision']}", fill=TENUE, font=(FUENTE, 7))
                    ultima = x
        mejor = [punto(i, r["mejor_progreso"]) for i, r in enumerate(datos)]
        area = [(x0, y1)] + mejor + [(x1, y1)]
        cv.create_polygon(*[c for q in area for c in q], fill=TM.mezcla(ORO, TARJETA, 0.88), outline="")
        cv.create_line(*[c for i, r in enumerate(datos) for c in punto(i, r["promedio_progreso"])], fill=AZUL, width=2)
        cv.create_line(*[c for q in mejor for c in q], fill=ORO, width=2)
        xu, yu = mejor[-1]
        cv.create_oval(xu - 3, yu - 3, xu + 3, yu + 3, fill=ORO, outline=TARJETA)
        cv.create_text(x0, y1 + 10, anchor="w", text=f"gen {datos[0]['generacion']}", fill=SUTIL, font=(FUENTE, 7))
        cv.create_text(x1, y1 + 10, anchor="e", text=f"gen {datos[-1]['generacion']}", fill=SUTIL, font=(FUENTE, 7))

    def _panel_vista(self):
        cv = self.c_vista
        cv.delete("all")
        v = self.vista
        detalle = ""
        if self.info_vista:
            i = self.info_vista
            logro = "la cumplió" if i["superada"] else f"llegó al {100 * i['progreso']:.0f} %"
            detalle = f"campeona de la gen. {i['generacion']} ({logro})"
        if self.mundos:
            detalle = f"generación {self.gen_vista} · {self.vivos()}/{len(self.mundos)} en vuelo · S sigue al líder"
        self._encabezado(cv, f"EN PANTALLA · MISIÓN {v.numero}", detalle)
        progreso = v.progreso()
        cv.create_text(14, 34, anchor="w", text="avance", fill=TENUE, font=(FUENTE, 8))
        self._barra(cv, 60, 31, ANCHO_PANEL - 120, progreso, ORO)
        cv.create_text(ANCHO_PANEL - 12, 34, anchor="e", text=f"{100 * progreso:.0f} %", fill=TEXTO, font=(SEMI, 9))
        j = v.jugadores[0]
        control = self.controles[0]
        quien = "tú" if isinstance(control, ControladorTeclado) else "red"
        cv.create_rectangle(14, 47, 17, 61, fill=CIELO, outline="")
        etiqueta = f"INDIVIDUO #{self.seguido + 1}" if self.mundos else "PILOTO"
        cv.create_text(24, 54, anchor="w", text=f"{etiqueta} · {quien}", fill=CIELO, font=(SEMI, 9))
        estado = "fuera" if j.fuera else ("derribado" if j.muerto else ("rizo" if j.rodando else "en combate"))
        self._fila(cv, 14, 74, "vidas · rizos · estado", f"{max(j.vidas, 0)} · {j.rizos} · {estado}", TEXTO, 210)
        self._fila(cv, 14, 91, "arma", NOMBRE_ARMA[j.arma] + (f" + {j.escoltas} escoltas" if j.escoltas else ""), ORO, 210)
        self._fila(cv, 14, 108, "derribos · puntos", f"{j.bajas} · {j.puntos}", TEXTO, 210)
        self._fila(cv, 14, 125, "balas esquivadas", f"{v.esquives}", TEXTO, 210)
        if isinstance(control, ControladorRed):
            cv.create_text(250, 54, anchor="w", text="decisión de la red", fill=TENUE, font=(FUENTE, 8))
            for k, nombre in enumerate(B.NOMBRES_SALIDAS):
                y = 76 + k * 17
                valor = float(control.salida[k])
                centro = 380
                cv.create_text(250, y, anchor="w", text=nombre.lower(), fill=TEXTO, font=(FUENTE, 8))
                cv.create_rectangle(centro - 70, y - 3, centro + 70, y + 3, fill=REJILLA, outline="")
                cv.create_rectangle(centro, y - 3, centro + 70 * valor, y + 3, outline="",
                                    fill=ORO if valor > 0 else AZUL)
            cv.create_line(380, 66, 380, 136, fill=SUTIL)
        else:
            cv.create_text(250, 90, anchor="w", fill=SUTIL, font=(FUENTE, 9), justify="left",
                           text="Estás pilotando tú.\nAl terminar la partida la red\ncopia tus decisiones.")

    def _panel_red(self):
        cv = self.c_red
        cv.delete("all")
        self._encabezado(cv, "LO QUE VE LA RED · ENTRADAS EN VIVO")
        control = self.controles[0]
        y = 26
        if isinstance(control, ControladorRed):
            entradas = control.entradas
            ancho = (ANCHO_PANEL - 28) / len(entradas)
            cv.create_rectangle(14, y, ANCHO_PANEL - 14, y + 14, fill=REJILLA, outline="")
            for k, valor in enumerate(entradas):
                valor = max(-1.0, min(1.0, float(valor)))
                if abs(valor) < 0.02:
                    continue
                color = TM.mezcla(REJILLA, ORO if valor > 0 else AZUL, abs(valor))
                x = 14 + k * ancho
                cv.create_rectangle(x, y, x + ancho, y + 14, fill=color, outline="")
        else:
            cv.create_text(14, y + 14, anchor="w", text="control humano: la red no está decidiendo ahora",
                           fill=TENUE, font=(FUENTE, 8))
            return
        x = 14
        for nombre, n in GRUPOS:
            ancho = (ANCHO_PANEL - 28) / B.CAPAS[0] * n
            cv.create_line(x, 24, x, 56, fill=SUTIL)
            if ancho >= 34:
                cv.create_text(x + 3, 54, anchor="sw", text=nombre, fill=TENUE, font=(FUENTE, 7))
            x += ancho

    def ejecutar(self):
        self.raiz.mainloop()
