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
from etapas import BARRERA, NOMBRES, NUMERO_ETAPAS, VACIO, cargar_etapa
from evolucion import Entrenador, bajar_prioridad, evaluar
from grabador import BotonGrabar
from jefes import NOMBRES as NOMBRES_JEFES
from mundo import Partida
from sensores import GRUPOS

E = C.ESCALA
ANCHO_JUEGO, ALTO_JUEGO = C.ANCHO_VISTA * E, C.ALTO_VISTA * E
ANCHO_PANEL = 470
FONDO, TARJETA, TARJETA2, BORDE = TM.FONDO, TM.TARJETA, TM.TARJETA2, TM.BORDE
TEXTO, TENUE, SUTIL, REJILLA = TM.TEXTO, TM.TENUE, TM.SUTIL, TM.REJILLA
ORO, AZUL, VERDE, MORADO = TM.ORO, TM.AZUL, TM.VERDE, TM.MORADO
ROJO = "#ff4a3a"
COLOR_JUGADOR = ("#4f86ff", "#ff5a46")
FUENTE = TM.FAMILIA
SEMI = TM.SEMI
MONO = "Consolas"
PIXEL = "Consolas"
VELOCIDADES = (1, 2, 4, 8)
TECLAS = {"Left": "izquierda", "Right": "derecha", "Up": "arriba", "Down": "abajo",
          "z": "saltar", "Z": "saltar", "x": "disparar", "X": "disparar"}
NOMBRE_ARMA = {"N": "normal", "M": "ametralladora", "S": "dispersión", "L": "láser", "F": "fuego"}
VISTAS = {"mejor": "la mejor de la generación anterior", "campeona": "la campeona guardada",
          "humano": "tú (flechas, Z salta, X dispara) · la red aprende de tus jugadas"}


def mezcla(c1, c2, t):
    return G.mezclar(c1, c2, min(max(float(t), 0.0), 1.0))


class Aplicacion:
    def __init__(self, jugadores=1, nuevo=False, semilla=None, vista="mejor"):
        self.raiz = tk.Tk()
        self.raiz.title("Contra evolutivo — comandos que aprenden por generaciones")
        self.raiz.configure(bg=FONDO)
        self.raiz.resizable(False, False)
        self.semilla = semilla
        self.modo_nuevo = jugadores if nuevo else None
        self.entrenadores = {}
        self.modo = jugadores
        self.vista_tipo = vista
        self.etapa_vista = None
        self.teclas = set()
        self.pausa = self.turbo = False
        self.i_vel = 0
        self.aviso = ("", 0.0)
        self.registro = []
        self.fondos = {}
        self.fondo_actual = None
        self.items = []
        self.imagen_item = []
        self.visibles = 0
        self.pendiente = None
        self.fin_vista = None
        self.controles = []
        self.entrenador_vista = None
        self.t_panel = 0.0
        self.siguiente_cuadro = time.perf_counter()
        self.turbo_t0 = time.perf_counter()
        self.turbo_gens = 0
        self.pool = mp.Pool(C.PROCESOS, initializer=bajar_prioridad)
        self._cargar_sprites()
        self._construir()
        self._teclas()
        self._nueva_vista()
        self.raiz.after(C.CUADRO_MS, self._ciclo)

    @property
    def e(self):
        if self.modo not in self.entrenadores:
            nuevo = self.modo_nuevo == self.modo
            self.entrenadores[self.modo] = Entrenador(self.modo, not nuevo, self.semilla)
            if nuevo:
                self.entrenadores[self.modo].reiniciar()
        return self.entrenadores[self.modo]

    def _cargar_sprites(self):
        self.sprites, self.tam = {}, {}
        for nombre, img in G.generar_sprites().items():
            self.tam[nombre] = (img.shape[1], img.shape[0])
            self.sprites[nombre] = tk.PhotoImage(data=base64.b64encode(G.png(G.escalar(img, E))))

    def _fondo(self, numero):
        if numero not in self.fondos:
            if len(self.fondos) >= 2:
                self.fondos.pop(next(iter(self.fondos)))
            rgb = G.escalar(G.fondo(cargar_etapa(numero)), E)
            self.fondos[numero] = tk.PhotoImage(data=G.ppm(rgb))
        return self.fondos[numero]

    def _construir(self):
        izquierda = tk.Frame(self.raiz, bg=FONDO)
        izquierda.pack(side="left", anchor="n", padx=(14, 8), pady=12)
        self.juego = tk.Canvas(izquierda, width=ANCHO_JUEGO, height=ALTO_JUEGO, bg="#000000",
                               highlightthickness=1, highlightbackground=BORDE)
        self.juego.pack()
        self.item_fondo = self.juego.create_image(0, 0, anchor="nw")
        self.capa_textos = []
        self.pie = tk.Label(izquierda, bg=FONDO, fg=TENUE, font=(FUENTE, 9), anchor="w")
        self.pie.pack(fill="x", pady=(6, 0))

        derecha = tk.Frame(self.raiz, bg=FONDO)
        derecha.pack(side="left", anchor="n", padx=(8, 14), pady=12)
        titulo = tk.Canvas(derecha, width=ANCHO_PANEL, height=50, bg=FONDO, highlightthickness=0)
        titulo.pack(anchor="w")
        self._emblema(titulo, 2, 4)
        t = titulo.create_text(52, 0, anchor="nw", text="CONTRA", fill=ROJO, font=(SEMI, 22))
        titulo.create_text(titulo.bbox(t)[2] + 8, 9, anchor="nw", text="EVOLUTIVO", fill=TEXTO,
                           font=(SEMI, 13))
        capas = " › ".join(str(n) for n in B.CAPAS)
        titulo.create_text(53, 36, anchor="nw", fill=TENUE, font=(FUENTE, 8),
                           text=f"red {capas} por jugador · estrategias evolutivas · {C.PROCESOS} procesos")

        selector = tk.Frame(derecha, bg=BORDE, padx=2, pady=2)
        selector.pack(anchor="w", pady=(4, 8))
        self.btn_modo = {}
        for n, texto in ((1, "1 JUGADOR"), (2, "2 JUGADORES")):
            b = tk.Label(selector, text=texto, font=(SEMI, 10), padx=16, pady=5, cursor="hand2")
            b.pack(side="left", padx=(0 if n == 1 else 2, 0))
            b.bind("<Button-1>", lambda e, n=n: self.cambiar_modo(n))
            self.btn_modo[n] = b

        self.c_gen = self._tarjeta(derecha, 150)
        self.c_graf = self._tarjeta(derecha, 122)
        self.c_vista = self._tarjeta(derecha, 152)
        self.c_red = self._tarjeta(derecha, 78)
        self._controles(derecha)

    @staticmethod
    def _emblema(cv, x, y):
        cv.create_polygon(x + 20, y, x + 40, y + 8, x + 40, y + 24, x + 20, y + 40, x, y + 24, x, y + 8,
                          fill="#2a0d0b", outline=ROJO, width=2)
        cv.create_polygon(x + 20, y + 8, x + 23, y + 17, x + 32, y + 17, x + 25, y + 23, x + 28, y + 32,
                          x + 20, y + 26, x + 12, y + 32, x + 15, y + 23, x + 8, y + 17, x + 17, y + 17,
                          fill=ORO, outline="")

    def _tarjeta(self, padre, alto):
        cv = tk.Canvas(padre, width=ANCHO_PANEL, height=alto, bg=TARJETA, highlightthickness=1,
                       highlightbackground=BORDE)
        cv.pack(anchor="w", pady=(0, 8))
        return cv

    def _controles(self, padre):
        fila = tk.Frame(padre, bg=FONDO)
        fila.pack(anchor="w", fill="x")
        self.btn_pausa = TM.Boton(fila, "Pausa", self.alternar_pausa, ancho=7).pack(side="left")
        self.btn_turbo = TM.Boton(fila, "Turbo", self.alternar_turbo, ancho=7).pack(
            side="left", padx=(6, 0))
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
        self.btn_campeona = TM.Boton(fila, "Ver campeona", lambda: self.cambiar_vista("campeona"), ORO,
                                     True, ancho=13).pack(side="left")
        self.btn_humano = TM.Boton(fila, "Jugar tú", lambda: self.cambiar_vista("humano"), MORADO, True,
                                   ancho=12).pack(side="left", padx=(6, 0))
        self.grabar = TM.estilo_grabar(BotonGrabar(fila, self.raiz, self.avisar, (SEMI, 10)))
        self.grabar.pack(side="right")

        ayuda = ("Espacio pausa · T turbo · +/− velocidad · 1/2 jugadores · C campeona (←/→ etapa)\n"
                 "J jugar tú: flechas mueven y apuntan, Z salta, X dispara · G guardar · N reiniciar · Esc salir")
        tk.Label(padre, text=ayuda, bg=FONDO, fg=SUTIL, font=(FUENTE, 8), justify="left").pack(anchor="w", pady=(8, 0))

    def _teclas(self):
        r = self.raiz
        r.bind("<KeyPress>", self._tecla_abajo)
        r.bind("<KeyRelease>", self._tecla_arriba)
        r.bind("<FocusOut>", lambda ev: self.teclas.clear())
        r.protocol("WM_DELETE_WINDOW", self.salir)

    def _tecla_abajo(self, ev):
        if ev.keysym in TECLAS:
            self.teclas.add(TECLAS[ev.keysym])
        humano = self.vista_tipo == "humano"
        acciones = {
            "space": self.alternar_pausa, "Escape": self.salir,
            "plus": lambda: self.cambiar_vel(1), "equal": lambda: self.cambiar_vel(1),
            "KP_Add": lambda: self.cambiar_vel(1), "minus": lambda: self.cambiar_vel(-1),
            "KP_Subtract": lambda: self.cambiar_vel(-1), "1": lambda: self.cambiar_modo(1),
            "2": lambda: self.cambiar_modo(2),
        }
        if not humano:
            acciones.update({"t": self.alternar_turbo, "c": lambda: self.cambiar_vista("campeona"),
                             "j": lambda: self.cambiar_vista("humano"), "n": self.reiniciar,
                             "g": self.guardar,
                             "Left": lambda: self.cambiar_etapa_vista(-1),
                             "Right": lambda: self.cambiar_etapa_vista(1)})
        else:
            acciones["j"] = lambda: self.cambiar_vista("humano")
        accion = acciones.get(ev.keysym) or acciones.get(ev.keysym.lower())
        if accion:
            accion()

    def _tecla_arriba(self, ev):
        if ev.keysym in TECLAS:
            self.teclas.discard(TECLAS[ev.keysym])

    def avisar(self, texto, *_):
        self.aviso = (texto, time.perf_counter())

    def _guardar_todo(self):
        for e in self.entrenadores.values():
            e._guardar()

    def guardar(self):
        try:
            self._guardar_todo()
        except OSError as err:
            self.avisar(f"No se pudo guardar: {err}")
            return
        self.avisar(f"Avance guardado en la generación {self.e.generacion}: al reabrir continúa aquí")

    def salir(self):
        try:
            self._aprender_humano()
            self._guardar_todo()
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

    def cambiar_vel(self, delta):
        self.i_vel = max(0, min(len(VELOCIDADES) - 1, self.i_vel + delta))

    def cambiar_modo(self, n):
        if n != self.modo:
            self.modo = n
            self.etapa_vista = None
            self._nueva_vista()
            self.avisar(f"Modo {n} jugador{'es' if n > 1 else ''}: se entrena su propia población")

    def cambiar_vista(self, tipo):
        self.vista_tipo = "mejor" if self.vista_tipo == tipo else tipo
        self.etapa_vista = None
        self.teclas.clear()
        if self.vista_tipo != "mejor":
            self.turbo = False
        self._nueva_vista()

    def cambiar_etapa_vista(self, delta):
        if self.vista_tipo != "campeona":
            return
        actual = self.etapa_vista or self.vista.numero
        self.etapa_vista = max(1, min(NUMERO_ETAPAS, actual + delta))
        self._nueva_vista()

    def reiniciar(self):
        pausa_previa, self.pausa = self.pausa, True
        ok = messagebox.askyesno(
            "Reiniciar desde cero",
            f"Se borrará lo aprendido en el modo de {self.modo} jugador{'es' if self.modo > 1 else ''} "
            "(estado, campeones e historial) y empezará otra vez en la generación 1.\n\n¿Continuar?",
            parent=self.raiz)
        self.pausa = pausa_previa
        if ok:
            if self.controles and isinstance(self.controles[0], ControladorTeclado):
                self.controles[0].demo = []
            self.e.reiniciar()
            if self.pendiente and self.pendiente[0] is self.e:
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
        e = self.entrenador_vista
        e.aprender_de_humano(*datos, etapa=self.vista.numero)
        if self.pendiente and self.pendiente[0] is e:
            self.pendiente = None
        return len(datos[0])

    def _fin_vista(self, v):
        if self.vista_tipo != "humano":
            return
        aprendidas = self._aprender_humano(v.motivo == "sin vidas")
        if v.superada:
            siguiente = v.numero % NUMERO_ETAPAS + 1
            self.etapa_vista = siguiente
            self._fondo(siguiente)
            texto = f"¡{v.etapa.nombre} superada! Siguiente: {NOMBRES[siguiente - 1]}"
        else:
            texto = "Otra vez la misma etapa"
        if aprendidas:
            texto += f" · la red aprendió de {aprendidas} jugadas"
        self.avisar(texto)

    def _nueva_vista(self):
        aprendidas = self._aprender_humano()
        if aprendidas:
            self.avisar(f"La red aprendió de {aprendidas} jugadas tuyas")
        e = self.e
        if self.vista_tipo == "campeona":
            etapa = self.etapa_vista or e.etapa_actual
            campeon = e.campeon(etapa)
            pesos = campeon[0] if campeon else e.mejores_pesos()
            self.info_vista = campeon[1] if campeon else None
        else:
            etapa = (self.etapa_vista if self.vista_tipo == "humano" else None) or e.etapa_actual
            pesos = e.mejores_pesos()
            self.info_vista = None
        controles = [ControladorRed(w) for w in pesos]
        if self.vista_tipo == "humano":
            controles[0] = ControladorTeclado(self.teclas)
        self.vista = Partida(etapa, controles, random.randrange(1 << 30), limites=self.vista_tipo != "humano")
        self.controles = controles
        self.entrenador_vista = e
        self.fin_vista = None

    def _lanzar(self):
        e = self.e
        tareas = e.tareas()
        self.pendiente = (e, self.pool.imap_unordered(evaluar, tareas), [], len(tareas))

    def _recolectar(self):
        if self.pendiente is None:
            self._lanzar()
            return
        entrenador, iterador, resultados, total = self.pendiente
        while len(resultados) < total:
            try:
                resultados.append(iterador.next(timeout=0))
            except mp.TimeoutError:
                break
        if len(resultados) < total:
            return
        r = entrenador.terminar(resultados)
        r["jugadores"] = entrenador.jugadores
        self.registro = (self.registro + [r])[-14:]
        self.turbo_gens += 1
        print(f"[{entrenador.jugadores}J] gen {r['generacion']:5d} · etapa {r['etapa']} {r['nombre']:<18} · "
              f"mejor {r['mejor_progreso']:5.1f} % · promedio {r['promedio_progreso']:5.1f} % · "
              f"superaron {r['superaron_pct']:4.1f} % · {r['motivo_lider']}", flush=True)
        if r["subio"]:
            siguiente = entrenador.etapa_actual
            texto = ("¡Campaña completa! Ahora repasa todas las etapas" if entrenador.completada
                     else f"¡{r['nombre']} superada! Siguiente: {NOMBRES[siguiente - 1]}")
            self.avisar(texto)
        self.pendiente = None
        self._lanzar()

    def _ciclo(self):
        ahora = time.perf_counter()
        try:
            self._recolectar()
            v = self.vista
            if not self.pausa and not self.turbo:
                if v.terminada:
                    if self.fin_vista is None:
                        self.fin_vista = ahora
                        self._fin_vista(v)
                    elif ahora - self.fin_vista > 2.0:
                        self._nueva_vista()
                else:
                    for _ in range(VELOCIDADES[self.i_vel]):
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
        v = self.vista
        for t in self.capa_textos:
            cv.delete(t)
        self.capa_textos = []
        if self.turbo:
            cv.itemconfigure(self.item_fondo, state="hidden")
            for i in range(self.visibles):
                cv.itemconfigure(self.items[i], state="hidden")
            self.visibles = 0
            self._pantalla_turbo()
            return
        fondo = self._fondo(v.numero)
        if fondo is not self.fondo_actual:
            cv.itemconfigure(self.item_fondo, image=fondo)
            self.fondo_actual = fondo
        cv.itemconfigure(self.item_fondo, state="normal")
        cv.coords(self.item_fondo, -round(v.cam_x * E), -round(v.cam_y * E))
        lista = self._dibujables(v)
        for i, (nombre, x, y) in enumerate(lista):
            item = self._item(i)
            if self.imagen_item[i] != nombre:
                cv.itemconfigure(item, image=self.sprites[nombre])
                self.imagen_item[i] = nombre
            cv.coords(item, round(x * E), round(y * E))
            if i >= self.visibles:
                cv.itemconfigure(item, state="normal")
        for i in range(len(lista), self.visibles):
            cv.itemconfigure(self.items[i], state="hidden")
        self.visibles = len(lista)
        self._hud(v)

    def _texto(self, x, y, texto, color=TEXTO, tam=12, ancla="nw", peso="bold"):
        cv = self.juego
        fuente = (PIXEL, tam, peso)
        for dx, dy in ((2, 2), (-1, 0), (1, 0), (0, -1), (0, 1)):
            self.capa_textos.append(cv.create_text(x + dx, y + dy, text=texto, fill="#000000", font=fuente,
                                                   anchor=ancla))
        self.capa_textos.append(cv.create_text(x, y, text=texto, fill=color, font=fuente, anchor=ancla))

    def _franja(self, y0, y1):
        cv = self.juego
        self.capa_textos.append(cv.create_rectangle(0, y0, ANCHO_JUEGO, y1, fill="#000000", outline="",
                                                    stipple="gray50"))
        for y in (y0, y1):
            self.capa_textos.append(cv.create_line(0, y, ANCHO_JUEGO, y, fill=ORO))

    def _imagen(self, nombre, x, y, ancla="nw"):
        self.capa_textos.append(self.juego.create_image(x, y, image=self.sprites[nombre], anchor=ancla))

    def _hud(self, v):
        cv = self.juego
        for j in v.jugadores:
            derecha = j.indice == 1
            color = COLOR_JUGADOR[j.indice]
            x = ANCHO_JUEGO - 12 if derecha else 12
            ancla = "ne" if derecha else "nw"
            signo = -1 if derecha else 1
            self._texto(x, 8, f"{j.indice + 1}P", color, 15, ancla)
            xm = x + signo * 44
            if j.fuera:
                self._texto(xm, 10, "GAME OVER", ROJO, 12, ancla)
            else:
                vidas = max(j.vidas - (0 if j.muerto else 1), 0)
                for k in range(min(vidas, 6)):
                    self._imagen(f"medalla_{j.indice + 1}", xm + signo * k * 30, 6, ancla)
                xa = xm + signo * (min(vidas, 6) * 30 + 4)
                letra = j.arma + ("R" if j.rapido else "")
                t = cv.create_text(xa + signo * 6, 22, text=letra, fill="#0e1014", font=(PIXEL, 11, "bold"),
                                   anchor="e" if derecha else "w")
                x0, y0, x1, y1 = cv.bbox(t)
                caja = cv.create_rectangle(x0 - 5, y0 - 1, x1 + 5, y1 + 1, fill=ORO, outline="#000000")
                cv.tag_lower(caja, t)
                self.capa_textos += [caja, t]
            self._texto(x, 46, f"{j.puntos:07d}", TEXTO, 11, ancla)
        centro = ANCHO_JUEGO / 2
        if v.jefe_activo and not v.jefe_vencido:
            partes = [e for e in v.enemigos if e.tipo == "parte" and getattr(e, "hp_max", 0) > 0]
            total = sum(e.hp_max for e in partes)
            if total:
                vida = sum(max(e.hp, 0) for e in partes) / total
                w, y = 300, 30
                self._texto(centro, y - 14, NOMBRES_JEFES[v.etapa.jefe].upper(), ROJO, 10, "center")
                self.capa_textos.append(cv.create_rectangle(centro - w / 2 - 3, y - 3, centro + w / 2 + 3, y + 9,
                                                            fill="#000000", outline=TEXTO))
                if vida > 0:
                    self.capa_textos.append(cv.create_rectangle(centro - w / 2, y, centro - w / 2 + w * vida,
                                                                y + 6, fill=ROJO, outline=""))
        if v.t < 75:
            self._franja(228, 318)
            self._texto(centro, 255, f"ETAPA {v.numero}", ORO, 26, "center")
            self._texto(centro, 295, v.etapa.nombre.upper(), TEXTO, 16, "center")
        if v.terminada:
            texto = "ETAPA SUPERADA" if v.superada else ("GAME OVER" if v.motivo == "sin vidas" else v.motivo.upper())
            self._franja(ALTO_JUEGO / 2 - 30, ALTO_JUEGO / 2 + 30)
            self._texto(centro, ALTO_JUEGO / 2, texto, ORO if v.superada else ROJO, 26, "center")
        texto, t0 = self.aviso
        if texto and time.perf_counter() - t0 < 4:
            self._franja(ALTO_JUEGO - 58, ALTO_JUEGO - 22)
            self._texto(centro, ALTO_JUEGO - 40, texto, ORO, 13, "center")
        if self.pausa:
            self._franja(ALTO_JUEGO / 2 - 82, ALTO_JUEGO / 2 - 18)
            self._texto(centro, ALTO_JUEGO / 2 - 50, "PAUSA", AZUL, 24, "center")

    def _pantalla_turbo(self):
        cv = self.juego
        c = self.capa_textos
        c.append(cv.create_rectangle(0, 0, ANCHO_JUEGO, ALTO_JUEGO, fill=FONDO, outline=""))
        c.append(cv.create_rectangle(24, 24, ANCHO_JUEGO - 24, ALTO_JUEGO - 24, fill=TARJETA, outline=BORDE))
        c.append(cv.create_text(50, 64, anchor="w", text="MODO TURBO", fill=ORO, font=(SEMI, 24)))
        c.append(cv.create_text(50, 96, anchor="w", fill=TENUE, font=(FUENTE, 10),
                                text="entrenando sin animar · T para volver a ver"))
        minutos = max(time.perf_counter() - self.turbo_t0, 1e-6) / 60
        e = self.e
        datos = (("JUGADORES", str(e.jugadores), COLOR_JUGADOR[0]), ("GENERACIÓN", str(e.generacion), ORO),
                 ("ETAPA", f"{e.etapa_actual} · {NOMBRES[e.etapa_actual - 1]}", TEXTO),
                 ("RITMO", f"{self.turbo_gens / minutos:.1f} gen/min", AZUL))
        ancho = (ANCHO_JUEGO - 100 - 3 * 8) / 4
        for k, (etq, valor, color) in enumerate(datos):
            x = 50 + k * (ancho + 8)
            c.append(cv.create_rectangle(x, 122, x + ancho, 178, fill=TARJETA2, outline=""))
            c.append(cv.create_rectangle(x, 122, x + 3, 178, fill=color, outline=""))
            c.append(cv.create_text(x + 12, 136, anchor="w", text=etq, fill=TENUE, font=(SEMI, 7)))
            c.append(cv.create_text(x + 12, 160, anchor="w", text=valor, fill=TEXTO, font=(SEMI, 12)))
        columnas = (("GEN", 50), ("MODO", 128), ("ETAPA", 190), ("MEJOR", 430), ("PROM.", 520), ("SUPERAN", 610))
        c.append(cv.create_rectangle(42, 202, ANCHO_JUEGO - 42, 226, fill=TARJETA2, outline=""))
        for nombre, x in columnas:
            c.append(cv.create_text(x, 214, anchor="w", text=nombre, fill=TENUE, font=(SEMI, 8)))
        for k, r in enumerate(reversed(self.registro)):
            y = 244 + k * 26
            if k % 2:
                c.append(cv.create_rectangle(42, y - 13, ANCHO_JUEGO - 42, y + 13, fill="#191c24", outline=""))
            color = ORO if r["subio"] else (VERDE if r["superaron_pct"] > 0 else TEXTO)
            valores = (r["generacion"], f"{r['jugadores']}J", f"{r['etapa']} {r['nombre']}",
                       f"{r['mejor_progreso']:.0f} %", f"{r['promedio_progreso']:.0f} %",
                       f"{r['superaron_pct']:.0f} %" + ("  ▲" if r["subio"] else ""))
            for (_, x), valor in zip(columnas, valores):
                c.append(cv.create_text(x, y, anchor="w", text=str(valor), fill=color, font=(FUENTE, 10)))
        if not self.registro:
            c.append(cv.create_text(ANCHO_JUEGO / 2, 300, text="aquí aparece cada generación al terminar",
                                    fill=SUTIL, font=(FUENTE, 10)))

    def _dibujables(self, p):
        lista = []
        cam_x, cam_y = p.cam_x, p.cam_y
        t = p.t

        def poner(nombre, x, y):
            if nombre in self.sprites:
                w, h = self.tam[nombre]
                if x - cam_x < C.ANCHO_VISTA + 8 and x - cam_x + w > -8 and y - cam_y < C.ALTO_VISTA + 8 \
                        and y - cam_y + h > -8:
                    lista.append((nombre, x - cam_x, y - cam_y))

        def centrar(nombre, cx, cy):
            if nombre in self.tam:
                w, h = self.tam[nombre]
                poner(nombre, cx - w / 2, cy - h / 2)

        def apoyar(nombre, cx, pie):
            if nombre in self.tam:
                w, h = self.tam[nombre]
                poner(nombre, cx - w / 2, pie - h)

        original = p.etapa.tiles
        for celdas in p.grupos.values():
            for fila, col in celdas:
                if p.mapa[fila][col] != VACIO:
                    nombre = f"barrera{(t // 4 + fila) % 2}" if original[fila, col] == BARRERA else "puente"
                    poner(nombre, col * C.TILE, fila * C.TILE)
        for it in p.items:
            if it.vida > 120 or (t // 3) % 2:
                apoyar(f"item_{it.letra}", it.cx, it.y + it.h)
        for e in p.enemigos:
            self._enemigo(e, t, p, poner, centrar, apoyar)
        for j in p.jugadores:
            self._jugador(j, t, poner, centrar, apoyar)
        for b in p.balas:
            if b.dueno is not None:
                if b.tipo == "L":
                    centrar(f"laser{round(math.atan2(b.vy, b.vx) / (math.pi / 4)) % 8}", b.x, b.y)
                else:
                    centrar(f"bala_{b.tipo}", b.x, b.y)
            elif b.tipo == "g":
                centrar("granada", b.x, b.y)
            elif b.tipo == "d":
                centrar(f"disco{(t // 3) % 2}", b.x, b.y)
            else:
                centrar("bala_e", b.x, b.y)
        for x, y, tipo, t0 in p.efectos:
            edad = t - t0
            if tipo in ("explosion", "muerte"):
                centrar(f"explosion{min(3, edad // 5)}", x, y)
            elif edad < 10:
                centrar("chispa", x, y)
        return lista

    def _enemigo(self, e, t, p, poner, centrar, apoyar):
        lado = "" if e.mirando > 0 else "_izq"
        k = e.tipo
        if k == "soldado":
            apoyar(f"soldado{(t // 4) % 2}{lado}", e.cx, e.y + e.h)
        elif k == "francotirador":
            apoyar(f"francotirador{lado}", e.cx, e.y + e.h)
        elif k == "granadero":
            lanzando = 30 <= (t - e.t0) % 55 < 40
            apoyar(f"granadero{int(lanzando)}{lado}", e.cx, e.y + e.h)
        elif k in ("torreta", "canon"):
            centrar(f"{k}{e.angulo}", e.cx, e.cy)
        elif k == "capsula":
            centrar(f"capsula{(t // 4) % 2}", e.cx, e.cy)
        elif k == "caja":
            centrar(f"caja{int(e.vulnerable)}", e.cx, e.cy)
        elif k == "roca":
            centrar("roca", e.cx, e.cy)
        elif k == "llama":
            arriba = e.datos.get("orientacion") == "arriba"
            if e.contacto:
                for n in range(int(e.h // C.TILE)):
                    y = e.y + n * C.TILE
                    poner(f"llama{(t // 3 + n) % 2}", e.cx - 7, y)
            poner("boquilla", e.cx - 8, e.y0 - 6 if arriba else e.y0)
        elif k == "prensa":
            for y in range(int(e.y0), int(e.y), C.TILE):
                poner("piston", e.cx - 6, y)
            poner("prensa", e.cx - 16, e.y)
        elif k == "nucleo":
            centrar(f"nucleo{(t // 6) % 2}", e.cx, e.cy)
        elif k == "larva":
            centrar(f"larva{(t // 5) % 2}", e.cx, e.cy)
        elif k == "boca":
            centrar(f"boca{int((t - e.t0) % 70 > 25)}", e.cx, e.cy)
        elif k == "parte":
            nombre = e.datos["sprite"]
            if nombre == "torreta_jefe":
                obj = p.objetivo(e)
                angulo = round(math.atan2(obj.cy - e.cy, obj.cx - e.cx) / (math.pi / 6)) % 12 if obj else 3
                nombre = f"torreta_jefe{angulo}"
            elif nombre + "0" in self.sprites:
                nombre = f"{nombre}{(t // 8) % 2}"
            if e.hp < e.hp_max and (t - p.ultimo_dano_jefe) < 2 and (t // 2) % 2:
                return
            centrar(nombre, e.cx, e.cy)

    def _jugador(self, j, t, poner, centrar, apoyar):
        pal = f"j{j.indice + 1}"
        if j.fuera:
            return
        if j.muerto:
            apoyar(f"{pal}_muerto", j.cx, j.y + j.h)
            return
        if (j.invulnerable > 0 or j.barrera > 0) and (t // 2) % 2:
            return
        dx, dy = j.apunte
        if j.girando and not j.en_suelo:
            centrar(f"{pal}_salto{(t // 2) % 4}", j.cx, j.cy)
        elif j.buceando:
            apoyar("buceo", j.cx, j.y + j.h + 2)
        elif j.en_agua:
            apunte = "arriba" if dx == 0 and dy < 0 else ("diag_arr" if dy < 0 else "h")
            nombre = f"{pal}_agua_{apunte}"
            w, _ = self.tam[nombre]
            superficie = j.y + j.h - 2
            poner(nombre + ("" if j.mirando > 0 else "_izq"), j.cx - (13 if j.mirando > 0 else w - 13),
                  superficie - 16)
        elif j.agachado:
            nombre = f"{pal}_agachado"
            w, h = self.tam[nombre]
            x = j.cx - 26 if j.mirando > 0 else j.cx - (w - 26)
            poner(nombre + ("" if j.mirando > 0 else "_izq"), x, j.y + j.h - h)
        else:
            if not j.en_suelo:
                piernas = "c1"
            elif j.vx == 0:
                piernas = "quieto"
            else:
                piernas = f"c{int(j.paso_anim // 9) % 4}"
            if dx == 0 and dy < 0:
                apunte = "arriba"
            elif dy < 0:
                apunte = "diag_arr"
            elif dy > 0 and dx != 0:
                apunte = "diag_ab"
            else:
                apunte = "h"
            nombre = f"{pal}_{piernas}_{apunte}" + ("" if j.mirando > 0 else "_izq")
            w, h = self.tam[nombre]
            poner(nombre, j.cx - (13 if j.mirando > 0 else w - 13), j.y + j.h - h)

    def _dibujar_panel(self):
        self._panel_generacion()
        self._grafica()
        self._panel_vista()
        self._panel_red()
        for n, b in self.btn_modo.items():
            activo = n == self.modo
            b.configure(bg=ROJO if activo else TARJETA2, fg="#ffffff" if activo else TENUE)
        self.btn_pausa.texto("Seguir" if self.pausa else "Pausa")
        self.btn_turbo.texto("Animar" if self.turbo else "Turbo")
        self.btn_campeona.texto("Ver la mejor" if self.vista_tipo == "campeona" else "Ver campeona")
        self.btn_humano.texto("Dejar de jugar" if self.vista_tipo == "humano" else "Jugar tú")
        self.lbl_vel.configure(text=f"x{VELOCIDADES[self.i_vel]}")
        v = self.vista
        self.pie.configure(text=f"En pantalla: {VISTAS[self.vista_tipo]} · etapa {v.numero} {v.etapa.nombre}"
                                f" · {v.etapa.descripcion}")

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
        self._encabezado(cv, f"ENTRENAMIENTO · {e.jugadores} JUGADOR{'ES' if e.jugadores > 1 else ''}",
                         f"σ = {e.sigma:.3f}")
        h = e.historial[-1] if e.historial else None
        datos = (("GENERACIÓN", str(e.generacion), ORO),
                 ("MEJOR AVANCE", f"{h['mejor_progreso']:.0f} %" if h else "—", VERDE),
                 ("PROMEDIO", f"{h['promedio_progreso']:.0f} %" if h else "—", AZUL),
                 ("SUPERARON", f"{h['superaron_pct']:.0f} %" if h else "—", MORADO))
        ancho = (ANCHO_PANEL - 28 - 18) / 4
        for k, (etq, valor, color) in enumerate(datos):
            self._ficha(cv, 14 + k * (ancho + 6), 26, ancho, etq, valor, color)
        etapa = e.etapa_actual
        y = 90
        cv.create_text(14, y, anchor="w", text=f"Etapa {etapa}: {NOMBRES[etapa - 1]}", fill=TEXTO,
                       font=(SEMI, 10))
        for k in range(NUMERO_ETAPAS):
            x = 214 + k * 18
            superada = e.completada or k + 1 < e.etapa
            col = VERDE if superada else (ORO if k + 1 == etapa else REJILLA)
            cv.create_oval(x - 5, y - 5, x + 5, y + 5, fill=col, outline="")
        cv.create_text(ANCHO_PANEL - 12, y, anchor="e", fill=TENUE, font=(FUENTE, 8),
                       text="campaña completa" if e.completada else f"racha {e.racha}/{C.RACHA_PARA_SUBIR}")
        hechas = len(self.pendiente[2]) if self.pendiente and self.pendiente[0] is e else 0
        cv.create_text(14, 111, anchor="w", text=f"partidas evaluadas {hechas}/{e.n}", fill=TEXTO,
                       font=(FUENTE, 9))
        self._barra(cv, 170, 108, ANCHO_PANEL - 184, hechas / e.n, AZUL)
        if h:
            cv.create_text(14, 132, anchor="w", fill=TENUE, font=(FUENTE, 8),
                           text=f"muertes promedio {h['muertes_promedio']:.1f} · esquivó "
                                f"{h.get('esquives_lider', 0)} balas · terminó: {h['motivo_lider']}")

    def _grafica(self):
        cv = self.c_graf
        cv.delete("all")
        self._encabezado(cv, "AVANCE EN LA ETAPA POR GENERACIÓN")
        xl = ANCHO_PANEL - 12
        for texto, color in (("promedio", AZUL), ("mejor", ORO)):
            t = cv.create_text(xl, 14, anchor="e", text=texto, fill=TENUE, font=(FUENTE, 8))
            x0 = cv.bbox(t)[0]
            cv.create_line(x0 - 18, 14, x0 - 5, 14, fill=color, width=2)
            xl = x0 - 26
        datos = self.e.historial[-150:]
        x0, y0, x1, y1 = 40, 30, ANCHO_PANEL - 12, 102
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
            if datos[i]["etapa"] != datos[i - 1]["etapa"]:
                x = punto(i, 0)[0]
                cv.create_line(x, y0, x, y1, fill=SUTIL, dash=(2, 3))
                if x - ultima > 18:
                    cv.create_text(x + 3, y0, anchor="nw", text=f"E{datos[i]['etapa']}", fill=TENUE,
                                   font=(FUENTE, 7))
                    ultima = x
        mejor = [punto(i, r["mejor_progreso"]) for i, r in enumerate(datos)]
        area = [(x0, y1)] + mejor + [(x1, y1)]
        cv.create_polygon(*[c for q in area for c in q], fill=TM.mezcla(ORO, TARJETA, 0.88), outline="")
        cv.create_line(*[c for i, r in enumerate(datos) for c in punto(i, r["promedio_progreso"])], fill=AZUL,
                       width=2)
        cv.create_line(*[c for q in mejor for c in q], fill=ORO, width=2)
        xu, yu = mejor[-1]
        cv.create_oval(xu - 3, yu - 3, xu + 3, yu + 3, fill=ORO, outline=TARJETA)
        cv.create_text(x0, y1 + 11, anchor="w", text=f"gen {datos[0]['generacion']}", fill=SUTIL,
                       font=(FUENTE, 7))
        cv.create_text(x1, y1 + 11, anchor="e", text=f"gen {datos[-1]['generacion']}", fill=SUTIL,
                       font=(FUENTE, 7))

    def _panel_vista(self):
        cv = self.c_vista
        cv.delete("all")
        v = self.vista
        detalle = ""
        if self.info_vista:
            i = self.info_vista
            logro = "la superó" if i["superada"] else f"llegó al {100 * i['progreso']:.0f} %"
            detalle = f"campeona de la gen. {i['generacion']} ({logro})"
        self._encabezado(cv, f"EN PANTALLA · ETAPA {v.numero}", detalle)
        progreso = v.progreso()
        cv.create_text(14, 34, anchor="w", text="avance", fill=TENUE, font=(FUENTE, 8))
        self._barra(cv, 60, 31, ANCHO_PANEL - 120, progreso, ORO)
        cv.create_text(ANCHO_PANEL - 12, 34, anchor="e", text=f"{100 * progreso:.0f} %", fill=TEXTO,
                       font=(SEMI, 9))
        for j, control in zip(v.jugadores, self.controles):
            x = 14 + j.indice * 230
            color = COLOR_JUGADOR[j.indice]
            quien = "tú" if isinstance(control, ControladorTeclado) else "red"
            cv.create_rectangle(x, 47, x + 3, 61, fill=color, outline="")
            cv.create_text(x + 10, 54, anchor="w", text=f"JUGADOR {j.indice + 1} · {quien}", fill=color,
                           font=(SEMI, 9))
            estado = "fuera" if j.fuera else ("cayó" if j.muerto else "en combate")
            self._fila(cv, x, 74, "vidas · estado", f"{max(j.vidas, 0)} · {estado}", TEXTO, 210)
            arma = NOMBRE_ARMA[j.arma] + (" +R" if j.rapido else "")
            self._fila(cv, x, 91, "arma", arma, ORO, 210)
            self._fila(cv, x, 108, "bajas · puntos", f"{j.bajas} · {j.puntos}", TEXTO, 210)
            if isinstance(control, ControladorRed):
                for k, nombre in enumerate(B.NOMBRES_SALIDAS):
                    y = 122 + k * 6
                    valor = float(control.salida[k])
                    centro = x + 140
                    cv.create_rectangle(centro - 70, y - 2, centro + 70, y + 2, fill=REJILLA, outline="")
                    cv.create_rectangle(centro, y - 2, centro + 70 * valor, y + 2, outline="",
                                        fill=ORO if valor > 0 else AZUL)
                cv.create_text(x, 134, anchor="w", text="decisión", fill=TENUE, font=(FUENTE, 8))
                cv.create_line(x + 140, 118, x + 140, 148, fill=SUTIL)
        if len(v.jugadores) == 1:
            cv.create_text(250, 90, anchor="w", fill=SUTIL, font=(FUENTE, 9), justify="left",
                           text="Modo de 1 jugador.\nCon «2 JUGADORES» se entrena\nuna pareja con dos redes propias.")

    def _panel_red(self):
        cv = self.c_red
        cv.delete("all")
        self._encabezado(cv, "LO QUE VE CADA RED · ENTRADAS EN VIVO")
        for j, control in zip(self.vista.jugadores, self.controles):
            y = 28 + j.indice * 20
            cv.create_text(14, y + 6, anchor="w", text=f"{j.indice + 1}P", fill=COLOR_JUGADOR[j.indice],
                           font=(SEMI, 8))
            if not isinstance(control, ControladorRed):
                cv.create_text(40, y + 6, anchor="w", text="control humano", fill=TENUE, font=(FUENTE, 8))
                continue
            entradas = control.entradas
            ancho = (ANCHO_PANEL - 52) / len(entradas)
            cv.create_rectangle(40, y, ANCHO_PANEL - 12, y + 12, fill=REJILLA, outline="")
            for k, valor in enumerate(entradas):
                valor = max(-1.0, min(1.0, float(valor)))
                if abs(valor) < 0.02:
                    continue
                color = mezcla(REJILLA, ORO if valor > 0 else AZUL, abs(valor))
                x = 40 + k * ancho
                cv.create_rectangle(x, y, x + ancho, y + 12, fill=color, outline="")
        x = 40
        otros = None
        for nombre, n in GRUPOS:
            ancho = (ANCHO_PANEL - 52) / B.CAPAS[0] * n
            cv.create_line(x, 26, x, 76, fill=SUTIL)
            if ancho >= 30:
                cv.create_text(x + 3, 74, anchor="sw", text=nombre, fill=TENUE, font=(FUENTE, 7))
            elif otros is None:
                otros = x
            x += ancho
        if otros is not None:
            cv.create_text(otros + 3, 74, anchor="sw", text="otros", fill=TENUE, font=(FUENTE, 7))

    def ejecutar(self):
        self.raiz.mainloop()
