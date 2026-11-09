import math
import os
import random
import tkinter as tk
from tkinter import messagebox

import config as C
import escena as V
import estilo as E
from camara import BORDE, FONDO, VEHICULO
from estilo import P
from evolucion import (Entrenador, archivo_mejor, borrar_progreso, cargar_mejor,
                       resumen_generacion)
from fisica import Escenario, cajones_posibles
from grabador import CARPETA_GRABACIONES, BotonGrabar
from navegacion import MapaCosto
from simulacion import APTITUD_EXITO, BUSCANDO, CHOQUE, ESTACIONADO, Generacion

ANCHO_PANEL = 360
VELOCIDADES = (1, 2, 4, 8, 16)
NOMBRE_MODO = {"frente": "de frente", "reversa": "en reversa"}
NOMBRE_LUGAR = {"asignado": "Asignado", "camara": "Buscar con cámara"}
ASFALTO = E.hexa(V.ASFALTO)
COLOR_ESTADO = {
    "activo": E.mezclar(P["azul"], ASFALTO, 0.2),
    CHOQUE: E.mezclar(P["rojo"], ASFALTO, 0.5),
    ESTACIONADO: P["verde"],
    "otro": E.mezclar(P["gris"], ASFALTO, 0.45),
}
COLOR_RAYO = {FONDO: E.mezclar(P["cian"], ASFALTO, 0.45), VEHICULO: E.mezclar(P["naranja"], ASFALTO, 0.55),
              BORDE: E.mezclar(P["gris"], ASFALTO, 0.6), "nada": E.mezclar(P["gris"], ASFALTO, 0.7)}


class Aplicacion:
    def __init__(self, demo=False, continuar=True, poblacion=C.POBLACION,
                 modo=C.MODO_ESTACIONAR, lugar=C.LUGAR, objetivo=None):
        self.demo = demo
        self.modo = modo
        self.lugar = lugar
        self.poblacion = poblacion
        self.raiz = tk.Tk()
        self.raiz.title("Estacionamiento evolutivo — algoritmo genético en Python")
        self.raiz.configure(bg=P["fondo"])
        self.raiz.resizable(False, False)

        self.pausa = False
        self.turbo = False
        self.vel_idx = 1
        self.aviso = ""
        self._aviso_gens = 0
        self._sprites = {}
        self._escenario_dibujado = None

        if demo:
            self.record = cargar_mejor(modo)
            if not self.record:
                raise SystemExit(f"No hay plan guardado para estacionarse "
                                 f"{NOMBRE_MODO[modo]}. Entrena primero: "
                                 f"python main.py --modo {modo}")
            self.entrenador = None
            posibles = cajones_posibles(modo)
            self.objetivo = objetivo if objetivo in posibles else random.choice(posibles)
            self._preparar_demo()
        else:
            self.entrenador = Entrenador(poblacion, continuar, modo, lugar, objetivo)
            self.objetivo = self.entrenador.objetivo
            self.generacion = self.entrenador.generacion

        self._construir()
        self._crear_autos()
        self._teclas()
        if not demo:
            self._dibujar_grafica()
        self.raiz.after(C.FPS_MS, self._ciclo)

    @property
    def escenario(self):
        return self.generacion.escenario

    def _preparar_demo(self):
        self.mapa = MapaCosto(Escenario(self.modo))
        self.generacion = self._generacion_demo()

    def _generacion_demo(self):
        if self.lugar == "camara":
            self.objetivo = random.choice(cajones_posibles(self.modo))
        return Generacion([self.record["genoma"]], Escenario(self.modo, self.objetivo),
                          self.mapa, busqueda=self.lugar == "camara")

    def _construir(self):
        izquierda = tk.Frame(self.raiz, bg=P["fondo"])
        izquierda.grid(row=0, column=0, sticky="n", padx=(14, 10), pady=14)
        self.lienzo = tk.Canvas(izquierda, width=V.ANCHO, height=V.ALTO, bg=P["fondo"],
                                highlightthickness=0)
        self.lienzo.pack()
        self.foto_base = V.fondo()
        self.foto_fondo = tk.PhotoImage(width=V.ANCHO, height=V.ALTO)
        self.lienzo.create_image(0, 0, image=self.foto_fondo, anchor="nw", tags="fondo")
        self.lienzo.bind("<Button-1>", self._clic_lote)
        self.ley = tk.Canvas(izquierda, width=V.ANCHO, height=22, bg=P["fondo"],
                             highlightthickness=0)
        self.ley.pack(pady=(6, 0))
        self._leyenda()

        abajo = tk.Frame(izquierda, bg=P["fondo"])
        abajo.pack(fill="x", pady=(6, 0))
        ancho = (V.ANCHO - 20) // 3
        alto = 158
        marco, cuerpo = E.tarjeta(abajo, "Tablero del líder")
        marco.pack(side="left", anchor="n")
        self.tablero = tk.Canvas(cuerpo, width=ancho - 26, height=alto, bg=P["tarjeta"],
                                 highlightthickness=0)
        self.tablero.pack()
        marco, cuerpo = E.tarjeta(abajo, "Cámara lateral")
        marco.pack(side="left", anchor="n", padx=10)
        self.vista_camara = tk.Canvas(cuerpo, width=ancho - 26, height=alto, bg=P["tarjeta"],
                                      highlightthickness=0)
        self.vista_camara.pack()
        marco, cuerpo = E.tarjeta(abajo, "Plan de maniobras del líder (su genoma)")
        marco.pack(side="left", anchor="n")
        self.plan = tk.Canvas(cuerpo, width=V.ANCHO - 2 * ancho - 20 - 26, height=alto,
                              bg=P["tarjeta"], highlightthickness=0)
        self.plan.pack()

        panel = tk.Frame(self.raiz, bg=P["fondo"], width=ANCHO_PANEL)
        panel.grid(row=0, column=1, sticky="n", padx=(0, 14), pady=14)
        tk.Label(panel, text="ESTACIONAMIENTO EVOLUTIVO", bg=P["fondo"], fg=P["acento"],
                 font=E.F_SECCION).pack(anchor="w")
        titulo = tk.Frame(panel, bg=P["fondo"])
        titulo.pack(fill="x", pady=(0, 8))
        tk.Label(titulo, text="Demostración" if self.demo else "Evolución",
                 bg=P["fondo"], fg=P["texto"], font=E.F_TITULO).pack(side="left")
        sub = ("mejor plan guardado" if self.demo else
               f"algoritmo genético · {self.poblacion} autos")
        tk.Label(titulo, text=sub, bg=P["fondo"], fg=P["tenue"], font=E.F_TEXTO
                 ).pack(side="left", padx=(10, 0), pady=(8, 0))

        marco, cuerpo = E.tarjeta(panel, "Configuración")
        marco.pack(fill="x")
        self.sel_modo = self._fila(cuerpo, "Estacionarse",
                                   [(m, NOMBRE_MODO[m].capitalize()) for m in C.MODOS],
                                   self.modo, self._cambiar_modo)
        self.sel_lugar = self._fila(cuerpo, "Lugar", [(l, NOMBRE_LUGAR[l]) for l in C.LUGARES],
                                    self.lugar, self._cambiar_lugar)
        fila = tk.Frame(cuerpo, bg=P["tarjeta"])
        fila.pack(fill="x", pady=(6, 0))
        self.lbl_lugar = tk.Label(fila, bg=P["tarjeta"], fg=P["tenue"], font=E.F_CHICA,
                                  justify="left", anchor="w")
        self.lbl_lugar.pack(side="left")
        E.Boton(fila, "Al azar", self._lugar_al_azar).pack(side="right")

        self.indicadores = tk.Canvas(panel, width=ANCHO_PANEL, height=94, bg=P["fondo"],
                                     highlightthickness=0)
        self.indicadores.pack(pady=(8, 0))
        self.franja = tk.Canvas(panel, width=ANCHO_PANEL, height=28, bg=P["fondo"],
                                highlightthickness=0)
        self.franja.pack(pady=(8, 0))

        marco, cuerpo = E.tarjeta(panel, "Récord")
        marco.pack(fill="x", pady=(8, 0))
        self.lienzo_record = tk.Canvas(cuerpo, width=ANCHO_PANEL - 26, height=62,
                                       bg=P["tarjeta"], highlightthickness=0)
        self.lienzo_record.pack()

        if not self.demo:
            ley = lambda cab: tk.Label(cab, text="━ mejor   ━ promedio", bg=P["tarjeta"],
                                       fg=P["sutil"], font=E.F_CHICA)
            marco, cuerpo = E.tarjeta(panel, "Aptitud por generación", ley)
            marco.pack(fill="x", pady=(8, 0))
            self.grafica = tk.Canvas(cuerpo, width=ANCHO_PANEL - 26, height=104,
                                     bg=P["tarjeta"], highlightthickness=0)
            self.grafica.pack()
            E.grafica(self.grafica, [])

        botones = tk.Frame(panel, bg=P["fondo"])
        botones.pack(fill="x", pady=(10, 0))
        self.btn_pausa = E.Boton(botones, "Pausa", self._pausar, P["azul"], 8, True)
        self.btn_pausa.pack(side="left")
        if not self.demo:
            self.btn_turbo = E.Boton(botones, "Turbo", self._turbo, P["acento"], 7, True)
            self.btn_turbo.pack(side="left", padx=(6, 0))
        E.Boton(botones, "−", lambda: self._vel(-1)).pack(side="left", padx=(6, 0))
        E.Boton(botones, "+", lambda: self._vel(1)).pack(side="left", padx=(2, 0))

        fila = tk.Frame(panel, bg=P["fondo"])
        fila.pack(fill="x", pady=(6, 0))
        self.grabar = E.estilo_boton_grabar(
            BotonGrabar(fila, self.raiz, self._avisar, E.F_BOTON)).pack(side="left")
        if not self.demo:
            E.Boton(fila, "⟲ Reiniciar", self._reiniciar, P["tarjeta2"]).pack(side="right")
            E.Boton(fila, "Guardar", self._guardar, P["verde"], primario=True
                    ).pack(side="right", padx=(0, 6))
        ayuda = ("Espacio pausa · +/− velocidad"
                 + ("" if self.demo else " · T turbo · G guardar · N reiniciar")
                 + " · Esc salir")
        tk.Label(panel, text=ayuda, bg=P["fondo"], fg=P["sutil"], font=E.F_CHICA,
                 justify="left").pack(anchor="w", pady=(6, 0))

    def _fila(self, padre, texto, opciones, valor, comando):
        fila = tk.Frame(padre, bg=P["tarjeta"])
        fila.pack(fill="x", pady=(2, 3))
        tk.Label(fila, text=texto, bg=P["tarjeta"], fg=P["texto"], font=E.F_TEXTO, width=11,
                 anchor="w").pack(side="left")
        return E.Segmentado(fila, opciones, valor, comando).pack(side="left")

    def _leyenda(self):
        cv = self.ley
        x = 2
        for texto, color, borde in (("Líder (mejor de la generación anterior)", P["acento"], False),
                                    ("En movimiento", COLOR_ESTADO["activo"], True),
                                    ("Chocó", COLOR_ESTADO[CHOQUE], True),
                                    ("Estacionado", COLOR_ESTADO[ESTACIONADO], True),
                                    ("Terminó sin lograrlo", COLOR_ESTADO["otro"], True),
                                    ("Rayos de la cámara", P["cian"], False)):
            if borde:
                cv.create_rectangle(x, 6, x + 20, 16, outline=color, width=2)
            else:
                cv.create_rectangle(x, 6, x + 20, 16, fill=color, outline="")
            item = cv.create_text(x + 27, 11, text=texto, anchor="w", fill=P["tenue"],
                                  font=E.F_CHICA)
            x = cv.bbox(item)[2] + 18

    def _teclas(self):
        r = self.raiz
        r.bind("<space>", lambda e: self._pausar())
        if not self.demo:
            for k in ("<n>", "<N>"):
                r.bind(k, lambda e: self._reiniciar())
            for k in ("<t>", "<T>"):
                r.bind(k, lambda e: self._turbo())
            for k in ("<g>", "<G>"):
                r.bind(k, lambda e: self._guardar())
        for k in ("<plus>", "<KP_Add>"):
            r.bind(k, lambda e: self._vel(1))
        for k in ("<minus>", "<KP_Subtract>"):
            r.bind(k, lambda e: self._vel(-1))
        r.bind("<Escape>", lambda e: self._salir())
        r.protocol("WM_DELETE_WINDOW", self._salir)

    def _avisar(self, texto, nivel="info"):
        texto = texto.replace(CARPETA_GRABACIONES + os.sep, "grabaciones\\")
        self.aviso, self._aviso_gens = texto, 0

    def _guardar_progreso(self):
        if self.demo or self.entrenador is None or getattr(self, "preparando", False):
            return False
        try:
            self.entrenador.guardar_progreso()
        except OSError as err:
            self.aviso, self._aviso_gens = f"No se pudo guardar el avance: {err}", 2
            return False
        return True

    def _guardar(self):
        if self._guardar_progreso():
            self.aviso = (f"Avance guardado en la generación {self.entrenador.num}: al "
                          "volver a abrir el simulador continúa desde aquí.")
            self._aviso_gens = 2
            print(f"Avance guardado (generación {self.entrenador.num})", flush=True)

    def _salir(self):
        self._guardar_progreso()
        self.grabar.cerrar()
        self.raiz.destroy()

    def _vel(self, d):
        self.vel_idx = max(0, min(len(VELOCIDADES) - 1, self.vel_idx + d))

    def _turbo(self):
        if self.demo:
            return
        self.turbo = not self.turbo
        if not self.turbo:
            self._crear_autos()
        self._sincronizar_botones()

    def _pausar(self):
        self.pausa = not self.pausa
        self._sincronizar_botones()

    def _sincronizar_botones(self):
        self.btn_pausa.texto("Continuar" if self.pausa else "Pausa")
        if not self.demo:
            self.btn_turbo.texto("Animar" if self.turbo else "Turbo")

    def _cambiar_lugar(self, lugar):
        if lugar == self.lugar:
            return
        self.lugar = lugar
        self.sel_lugar.poner(lugar)
        self._reiniciar_lugar()

    def _asignar(self, cajon):
        if cajon not in cajones_posibles(self.modo):
            self.aviso = "Ese cajón no deja espacio para maniobrar desde el pasillo."
            self._aviso_gens = 2
            return
        self.lugar, self.objetivo = "asignado", cajon
        self.sel_lugar.poner(self.lugar)
        self._reiniciar_lugar(cajon)

    def _lugar_al_azar(self):
        otros = [i for i in cajones_posibles(self.modo) if i != self.objetivo]
        self._asignar(random.choice(otros))

    def _reiniciar_lugar(self, cajon=None):
        if self.demo:
            self.generacion = self._generacion_demo()
        else:
            self.entrenador.reiniciar_generacion(self.lugar, cajon)
            self.objetivo = self.entrenador.objetivo
            self.generacion = self.entrenador.generacion
        self._crear_autos()

    def _clic_lote(self, evento):
        x, y = V.a_metros(evento.x, evento.y)
        if not 0 <= y <= C.CAJON_FONDO:
            return
        for i, (x0, _, x1, _) in enumerate(self.escenario.cajones):
            if x0 <= x < x1:
                self._asignar(i)
                return

    def _reiniciar(self):
        pausa_previa, self.pausa = self.pausa, True
        ok = messagebox.askyesno(
            "Reiniciar desde cero",
            f"Se borrará el avance guardado y el mejor plan para estacionarse "
            f"{NOMBRE_MODO[self.modo]}, y la evolución empezará otra "
            "vez en la generación 1 con autos al azar.\n\n¿Continuar?",
            parent=self.raiz)
        if not ok:
            self.pausa = pausa_previa
            return
        if os.path.exists(archivo_mejor(self.modo)):
            os.remove(archivo_mejor(self.modo))
        borrar_progreso(self.modo)
        self._nueva_evolucion(continuar=False)
        print("\n=== Reinicio: la evolución empieza desde cero ===\n", flush=True)

    def _nueva_evolucion(self, continuar=True):
        self.entrenador = Entrenador(self.poblacion, continuar, modo=self.modo,
                                     lugar=self.lugar, objetivo=self.objetivo)
        self.objetivo = self.entrenador.objetivo
        self.generacion = self.entrenador.generacion
        self.pausa = self.turbo = False
        self.aviso, self._aviso_gens = "", 0
        self._crear_autos()
        self._dibujar_grafica()
        self._sincronizar_botones()

    def _cambiar_modo(self, nuevo):
        if nuevo == self.modo:
            return
        if self.demo:
            record = cargar_mejor(nuevo)
            if not record:
                self.aviso = (f"No hay plan guardado para estacionarse "
                              f"{NOMBRE_MODO[nuevo]}. Entrénalo primero.")
                return
            self.modo, self.record, self.aviso = nuevo, record, ""
            self.sel_modo.poner(nuevo)
            self._preparar_demo()
            self._crear_autos()
            return
        pausa_previa, self.pausa = self.pausa, True
        ok = messagebox.askyesno(
            "Cambiar forma de estacionarse",
            f"Se guarda el avance actual y la evolución sigue donde se quedó para "
            f"estacionarse {NOMBRE_MODO[nuevo]} (o empieza en la generación 1 si "
            "nunca lo ha entrenado).\n(Cada modo guarda su propio avance.)\n\n"
            "¿Continuar?", parent=self.raiz)
        if not ok:
            self.pausa = pausa_previa
            return
        self._guardar_progreso()
        self.modo = nuevo
        self.sel_modo.poner(nuevo)
        self._nueva_evolucion()
        print(f"\n=== Ahora aprende a estacionarse {NOMBRE_MODO[nuevo]} ===\n", flush=True)

    def _sprite(self, clave, crear):
        if clave not in self._sprites:
            self._sprites[clave] = crear()
        return self._sprites[clave]

    def _pegar(self, foto, x, y):
        self.foto_fondo.tk.call(self.foto_fondo, "copy", foto, "-to", int(round(x)),
                                int(round(y)), "-compositingrule", "overlay")

    def _dibujar_escenario(self):
        cv, esc = self.lienzo, self.escenario
        cv.delete("lote")
        self.foto_fondo.tk.call(self.foto_fondo, "copy", self.foto_base,
                                "-compositingrule", "set")
        for cajon, poli in zip(esc.ocupados, esc.estacionados):
            (x0, y0), _, (x1, y1), _ = poli
            color = V.COLORES_ESTACIONADOS[cajon % len(V.COLORES_ESTACIONADOS)]
            arriba = cajon % 3 != 1
            foto = self._sprite(("auto", color, arriba), lambda: V.sprite_auto(color, arriba))
            x, y = V.px((x0 + x1) / 2, (y0 + y1) / 2)
            self._pegar(foto, x - foto.width() / 2, y - foto.height() / 2)
        visible = self.lugar == "asignado"
        if visible:
            x0, y0, _, _ = esc.cajon
            foto = self._sprite(("objetivo", self.modo), lambda: V.sprite_objetivo(self.modo))
            self._pegar(foto, *V.px(x0, y0))
        for i, (x0, _, x1, y1) in enumerate(esc.cajones):
            marcado = visible and i == esc.objetivo
            cv.create_text(*V.px((x0 + x1) / 2, y1 + 0.42), text=f"{i + 1:02d}",
                           fill=P["verde"] if marcado else E.mezclar(P["tenue"], ASFALTO, 0.35),
                           font=(E.SEMI, 8), tags="lote")
        sx, sy, _ = esc.inicio
        cv.create_text(*V.px(sx - 1.6, sy + 2.2), text="ENTRADA", anchor="w",
                       fill=E.mezclar(P["tenue"], ASFALTO, 0.4), font=(E.SEMI, 7), tags="lote")
        cv.tag_raise("lote", "fondo")
        self._escenario_dibujado = esc

    def _marco_cajon(self, color):
        cv = self.lienzo
        x0, y0, x1, y1 = self.escenario.cajon
        a0, b0 = V.px(x0, y0)
        a1, b1 = V.px(x1, y1)
        k = 12
        for (x, y, dx, dy) in ((a0, b0, 1, 1), (a1, b0, -1, 1), (a0, b1, 1, -1), (a1, b1, -1, -1)):
            cv.create_line(x, y + dy * k, x, y, x + dx * k, y, fill=color, width=3,
                           tags="marco")

    def _crear_autos(self):
        cv = self.lienzo
        cv.delete("auto", "rastro", "rayo", "marco", "hud")
        self._dibujar_escenario()
        self.rastro_explorador = cv.create_line(0, 0, 0, 0, tags="rastro", dash=(2, 4),
                                                fill=E.mezclar(P["acento"], ASFALTO, 0.5))
        self.rastro = cv.create_line(0, 0, 0, 0, tags="rastro", fill=P["acento"], width=2,
                                     smooth=True)
        self.rayos = [cv.create_line(0, 0, 0, 0, tags="rayo") for _ in range(C.CAMARA["rayos"])]
        self.fantasmas = []
        self._quietos = set()
        agentes = self.generacion.agentes
        for idx in range(len(agentes) - 1, 0, -1):
            self.fantasmas.append((idx, V.Fantasma(cv)))
        self.lider = V.Lider(cv)
        self.hud = cv.create_text(V.ANCHO / 2, V.ALTO - V.MARGEN / 2, fill=P["texto"],
                                  font=(E.SEMI, 9), tags="hud")
        self._hud_fondo = cv.create_rectangle(0, 0, 0, 0, fill="#141820", outline=P["borde"],
                                              tags="hud")
        cv.tag_lower(self._hud_fondo, self.hud)
        self._marco_visible = None

    def _color_estado(self, a):
        if a.estado == CHOQUE:
            return COLOR_ESTADO[CHOQUE]
        if a.estado == ESTACIONADO:
            return COLOR_ESTADO[ESTACIONADO]
        return COLOR_ESTADO["activo"] if a.activo else COLOR_ESTADO["otro"]

    def _actualizar_autos(self):
        cv, g = self.lienzo, self.generacion
        ex = g.explorador
        if g.llegando:
            for _, f in self.fantasmas:
                f.ocultar()
            self.lider.actualizar(ex.auto, ex.controles[1], camara=True)
            if len(ex.rastro) > 1:
                cv.coords(self.rastro_explorador, *[c for p in ex.rastro for c in V.px(*p)])
            self._actualizar_rayos(ex.estado == BUSCANDO)
        else:
            for idx, f in self.fantasmas:
                if idx in self._quietos:
                    continue
                a = g.agentes[idx]
                if not a.activo:
                    self._quietos.add(idx)
                f.actualizar(a.auto, self._color_estado(a))
            lider = g.agentes[0]
            borde = None if lider.activo else self._color_estado(lider)
            self.lider.actualizar(lider.auto, lider.controles[1], borde)
            if len(lider.rastro) > 1:
                cv.coords(self.rastro, *[c for p in lider.rastro for c in V.px(*p)])
            self._actualizar_rayos(False)
        marco = None
        if self.lugar == "asignado":
            marco = P["acento"]
        elif ex.cajon is not None:
            marco = P["verde"]
        if marco != self._marco_visible:
            cv.delete("marco")
            if marco:
                self._marco_cajon(marco)
            self._marco_visible = marco
        cv.tag_raise("rayo")
        cv.tag_raise("auto")
        cv.tag_raise("marco")

    def _actualizar_rayos(self, visibles):
        cv = self.lienzo
        camara = self.generacion.explorador.camara
        if not visibles or camara is None:
            if self.rayos and cv.coords(self.rayos[0]) != [0, 0, 0, 0]:
                for r in self.rayos:
                    cv.coords(r, 0, 0, 0, 0)
            return
        for r, (x0, y0, x1, y1, _, tipo, cuenta) in zip(self.rayos, camara.lecturas):
            cv.coords(r, *V.px(x0, y0), *V.px(x1, y1))
            cv.itemconfigure(r, fill=P["verde"] if cuenta else COLOR_RAYO[tipo],
                             width=2 if cuenta else 1)

    def _actualizar_hud(self):
        g = self.generacion
        ex = g.explorador
        if self.demo:
            pre = "DEMOSTRACIÓN"
        else:
            pre = f"GENERACIÓN {self.entrenador.num}"
        if ex.estado == BUSCANDO:
            fase = "buscando un lugar libre con la cámara"
        elif g.llegando:
            fase = f"lugar {ex.cajon + 1:02d} {'localizado' if ex.camara else 'asignado'}: " \
                   "yendo a la pose de inicio"
        elif g.terminada:
            fase = "generación terminada"
        else:
            fase = f"ejecutando los planes en el cajón {g.escenario.objetivo + 1:02d}"
        cv = self.lienzo
        cv.itemconfigure(self.hud, text=f"{pre}  ·  {fase.upper()}")
        x0, y0, x1, y1 = cv.bbox(self.hud)
        cv.coords(self._hud_fondo, x0 - 10, y0 - 2, x1 + 10, y1 + 2)
        cv.tag_raise("hud")

    def _actualizar_tablero(self):
        cv = self.tablero
        cv.delete("all")
        g = self.generacion
        if g.llegando:
            auto, (acel, freno, _, _) = g.explorador.auto, g.explorador.controles
        else:
            lider = g.agentes[0]
            auto, (acel, freno, _, _) = lider.auto, lider.controles
        kmh = abs(auto.v) * 3.6
        E.velocimetro(cv, 58, 70, 52, kmh, 12, f"{kmh:.1f}", "km/h",
                      P["naranja"] if auto.marcha < 0 else P["azul"])
        giro = auto.giro / C.GIRO_MAX
        E.volante(cv, 158, 64, 34, giro * math.radians(240), P["acento"])
        lado = "izq." if giro < -0.02 else "der." if giro > 0.02 else "centro"
        cv.create_text(158, 116, text=f"llantas {abs(math.degrees(auto.giro)):.0f}° {lado}",
                       fill=P["tenue"], font=E.F_CHICA)
        x = int(cv["width"]) - 112
        E.pedal(cv, x, 26, 16, 86, acel, P["verde"], "ACEL.")
        E.pedal(cv, x + 38, 26, 16, 86, freno, P["rojo"], "FRENO")
        E.palanca(cv, x + 80, 40, auto.marcha)
        estado = g.explorador.estado if g.llegando else g.agentes[0].estado
        cv.create_text(6, int(cv["height"]) - 6, text=f"Estado: {estado}", anchor="sw",
                       fill=P["tenue"], font=E.F_CHICA)

    def _actualizar_camara(self):
        cv = self.vista_camara
        cv.delete("all")
        w, h = int(cv["width"]), int(cv["height"])
        g = self.generacion
        ex = g.explorador
        cam = ex.camara
        cx, cy = w / 2, h - 52
        r = min(cy - 6, w / 2 - 8)
        cv.create_arc(cx - r, cy - r, cx + r, cy + r, start=0, extent=180, style="pieslice",
                      fill=P["tarjeta2"], outline="")
        for k in (0.33, 0.66):
            rr = r * k
            cv.create_arc(cx - rr, cy - rr, cx + rr, cy + rr, start=0, extent=180, style="arc",
                          outline=P["rejilla"])
        if cam is not None and cam.lecturas:
            n = len(cam.lecturas)
            for k, (_, _, _, _, d, tipo, cuenta) in enumerate(cam.lecturas):
                a = math.radians(180 - 180 * k / (n - 1))
                largo = r * d / C.CAMARA["alcance"]
                color = P["verde"] if cuenta else {FONDO: P["cian"], VEHICULO: P["naranja"]}.get(
                    tipo, P["sutil"])
                cv.create_line(cx, cy, cx + largo * math.cos(a), cy - largo * math.sin(a),
                               fill=color, width=2 if cuenta else 1)
        elif cam is None:
            cv.create_text(cx, cy - 46, text="Cámara en espera", fill=P["sutil"], font=E.F_TEXTO)
            cv.create_text(cx, cy - 28, text="(el lugar está asignado)", fill=P["sutil"],
                           font=E.F_CHICA)
        cv.create_oval(cx - 4, cy - 4, cx + 4, cy + 4, fill=P["cian"], outline="")
        cv.create_text(cx - r, cy + 2, text="atrás", anchor="nw", fill=P["sutil"], font=E.F_CHICA)
        cv.create_text(cx + r, cy + 2, text="adelante", anchor="ne", fill=P["sutil"],
                       font=E.F_CHICA)
        n = len(self.escenario.cajones)
        celda = (w - 4) / n
        y = h - 34
        for i in range(n):
            x = 2 + i * celda
            votos = cam.evidencia.get(i, 0) if cam else 0
            frac = min(1.0, votos / C.EVIDENCIA_LUGAR)
            elegido = (ex.cajon == i) if cam else (self.lugar == "asignado" and i == self.objetivo)
            cv.create_rectangle(x + 1, y, x + celda - 1, y + 16, fill=P["tarjeta2"], outline="")
            if frac > 0:
                cv.create_rectangle(x + 1, y + 16 - 16 * frac, x + celda - 1, y + 16,
                                    fill=E.mezclar(P["verde"], P["tarjeta"], 0.35), outline="")
            if elegido:
                cv.create_rectangle(x + 1, y, x + celda - 1, y + 16,
                                    outline=P["verde"] if cam else P["acento"], width=2)
            cv.create_text(x + celda / 2, y + 8, text=str(i + 1), fill=P["texto"],
                           font=(E.SEMI, 7))
        if cam is None:
            txt = f"Lugar asignado: cajón {self.objetivo + 1:02d}"
        elif ex.cajon is None:
            txt = "Buscando: rayos que llegan al fondo de cada cajón"
        else:
            txt = f"Cajón {ex.cajon + 1:02d} libre: {cam.evidencia.get(ex.cajon, 0)} rayos al fondo"
        cv.create_text(w / 2, h - 2, text=txt, fill=P["tenue"], font=E.F_CHICA, anchor="s")

    def _actualizar_plan(self):
        cv = self.plan
        cv.delete("all")
        w = int(cv["width"])
        g = self.generacion
        a = g.agentes[0]
        if not a.plan:
            cv.create_text(w / 2, 60, text="(plan vacío)", fill=P["sutil"], font=E.F_TEXTO)
            return
        actual = a.conductor.indice
        for i, m in enumerate(a.plan):
            y = 4 + i * 24
            en_curso = i == actual and a.activo and not g.llegando
            hecho = i < actual
            if en_curso:
                cv.create_rectangle(0, y - 2, w, y + 20, fill=P["tarjeta2"], outline="")
                cv.create_rectangle(0, y - 2, 3, y + 20, fill=P["acento"], outline="")
            marca = "✓" if hecho else str(i + 1)
            cv.create_text(16, y + 9, text=marca, font=(E.SEMI, 9),
                           fill=P["verde"] if hecho else P["tenue"])
            adelante = m.marcha > 0
            E.ficha(cv, 30, y + 1, "D" if adelante else "R",
                    P["verde"] if adelante else P["naranja"], en_curso or hecho)
            cv.create_text(62, y + 9, text=f"{m.distancia:4.1f} m", anchor="w", fill=P["texto"],
                           font=E.F_MONO)
            cv.create_text(122, y + 9, text=f"{m.velocidad:3.1f} m/s", anchor="w",
                           fill=P["tenue"], font=E.F_MONO)
            x0, x1 = 196, w - 64
            cv.create_line(x0, y + 9, x1, y + 9, fill=P["rejilla"])
            pts = [c for k, v in enumerate(m.volantes)
                   for c in (x0 + k * (x1 - x0) / (len(m.volantes) - 1), y + 9 + v * 8)]
            cv.create_line(*pts, fill=P["cian"] if en_curso else P["sutil"], width=2)
            if en_curso:
                frac = min(1.0, a.conductor.recorrido / m.distancia)
                cv.create_rectangle(w - 56, y + 6, w - 6, y + 12, fill=P["rejilla"], outline="")
                cv.create_rectangle(w - 56, y + 6, w - 56 + 50 * frac, y + 12,
                                    fill=P["acento"], outline="")
        y = 4 + len(a.plan) * 24 + 4
        cv.create_text(4, y + 6, text="marcha · distancia · velocidad · volante (izq. arriba, "
                       "der. abajo) · avance", anchor="w", fill=P["sutil"], font=(E.FAMILIA, 7))

    def _actualizar_panel(self):
        g = self.generacion
        conteo = g.conteo()
        pasos = max(a.pasos for a in g.agentes)
        vel = "TURBO" if self.turbo else f"x{VELOCIDADES[self.vel_idx]}"
        if self.demo:
            a = g.agentes[0]
            datos = [("Estado", a.estado if not g.llegando else g.explorador.estado, P["acento"], None),
                     ("Tiempo", f"{a.pasos * C.DT:.1f} s", P["azul"], a.pasos / C.PASOS_MAX),
                     ("Maniobras", str(a.maniobras), P["cian"], None),
                     ("Del centro", f"{a.desvio_lateral() * 100:.1f} cm", P["verde"], None),
                     ("Inclinación", f"{math.degrees(a.error_angulo()):.2f}°", P["verde"], None),
                     ("Velocidad", vel, P["morado"], None)]
        else:
            e = self.entrenador
            datos = [("Generación", str(e.num), P["acento"], None),
                     ("Tiempo", f"{pasos * C.DT:4.1f} s", P["azul"], pasos / C.PASOS_MAX),
                     ("En marcha", str(conteo["activo"]), P["cian"], conteo["activo"] / len(g.agentes)),
                     ("Estacionados", str(conteo["estacionado"]), P["verde"], None),
                     ("Chocaron", str(conteo["chocó"]), P["rojo"], None),
                     ("Velocidad", vel + (" · pausa" if self.pausa else ""), P["morado"], None)]
        E.indicadores(self.indicadores, datos, 3, ANCHO_PANEL, 44)

        cv = self.franja
        cv.delete("all")
        if self.aviso:
            texto, color = self.aviso, P["naranja"]
        elif not self.demo and self.entrenador.extinciones:
            texto, color = f"Extinciones hasta ahora: {self.entrenador.extinciones}", P["sutil"]
        else:
            texto, color = "Todo en orden", P["sutil"]
        cv.create_rectangle(0, 0, ANCHO_PANEL - 1, 27, fill=P["tarjeta"], outline=P["borde"])
        cv.create_rectangle(0, 0, 3, 27, fill=color, outline="")
        cv.create_text(12, 14, text=texto, anchor="w", fill=P["texto"] if self.aviso else color,
                       font=E.F_CHICA, width=ANCHO_PANEL - 20)

        if self.lugar == "asignado":
            self.lbl_lugar.configure(text=f"Cajón {self.objetivo + 1:02d} · haz clic en otro "
                                          "cajón para asignarlo")
        else:
            self.lbl_lugar.configure(text="Cada generación queda libre un cajón al azar\n"
                                          "y el auto lo busca con su cámara")
        self._actualizar_record()

    def _actualizar_record(self):
        cv = self.lienzo_record
        cv.delete("all")
        w = int(cv["width"])
        r = self.record if self.demo else self.entrenador.record
        if not r:
            cv.create_text(w / 2, 43, text="Sin datos todavía", fill=P["sutil"], font=E.F_TEXTO)
            return
        if not r.get("estacionado"):
            cv.create_text(0, 14, text="Aún no logra estacionarse", anchor="w", fill=P["texto"],
                           font=(E.SEMI, 11))
            cv.create_text(0, 38, text=f"Mejor aptitud {r['aptitud']:.0f} · generación "
                           f"{r['generacion']}", anchor="w", fill=P["tenue"], font=E.F_TEXTO)
            return
        cv.create_text(0, 10, text="✓ Estacionado perfecto", anchor="w", fill=P["verde"],
                       font=(E.SEMI, 11))
        cv.create_text(w, 10, text=f"gen {r['generacion']} · {r['segundos']} s · "
                       f"{r['maniobras']} maniobra(s)", anchor="e", fill=P["tenue"], font=E.F_CHICA)
        filas = (("Del centro", r.get("desvio_cm", 0), C.TOL_CENTRO * 100, "cm"),
                 ("Inclinación", r.get("error_grados", 0), math.degrees(C.TOL_ANGULO), "°"))
        for k, (etq, valor, tope, u) in enumerate(filas):
            y = 34 + k * 22
            cv.create_text(0, y, text=etq, anchor="w", fill=P["tenue"], font=E.F_CHICA)
            x0, x1 = 80, w - 92
            cv.create_rectangle(x0, y - 3, x1, y + 3, fill=P["rejilla"], outline="")
            frac = min(1.0, float(valor) / tope) if tope else 0
            cv.create_rectangle(x0, y - 3, x0 + (x1 - x0) * frac, y + 3, fill=P["verde"], outline="")
            cv.create_text(w, y, text=f"{valor} {u} (máx. {tope:.0f})", anchor="e",
                           fill=P["texto"], font=E.F_CHICA)
        cv.create_text(0, 78, text=f"A la línea: {r.get('espacio_linea_cm', '?')} cm libres",
                       anchor="w", fill=P["tenue"], font=E.F_CHICA)

    def _dibujar_grafica(self):
        E.grafica(self.grafica, self.entrenador.historial[-150:], APTITUD_EXITO,
                  "estaciona perfecto")

    def _fin_generacion(self):
        if self.demo:
            self.generacion = self._generacion_demo()
            self._crear_autos()
            return
        stats = self.entrenador.cerrar_generacion()
        self.generacion = self.entrenador.generacion
        self.objetivo = self.entrenador.objetivo
        if stats["extincion"]:
            self.aviso = ("¡Extinción! La población se atascó en una mala estrategia; "
                          "se renueva para explorar otras.")
            self._aviso_gens = 3
        elif self._aviso_gens:
            self._aviso_gens -= 1
            if not self._aviso_gens:
                self.aviso = ""
        print(resumen_generacion(stats), flush=True)
        self._dibujar_grafica()
        if not self.turbo:
            self._crear_autos()

    def _refrescar(self):
        self._cuadro = getattr(self, "_cuadro", 0) + 1
        par = self._cuadro % 2 == 0
        if not self.turbo:
            self._actualizar_autos()
            if par:
                self._actualizar_tablero()
                self._actualizar_plan()
            else:
                self._actualizar_camara()
        elif self._escenario_dibujado is not self.escenario:
            self._crear_autos()
        self._actualizar_hud()
        if not par or self.turbo:
            self._actualizar_panel()

    def _ciclo(self):
        try:
            if not self.pausa:
                pasos = 60 if self.turbo else VELOCIDADES[self.vel_idx]
                for _ in range(pasos):
                    self.generacion.paso()
                    if self.generacion.terminada:
                        if self.demo:
                            self._refrescar()
                            self.raiz.after(2000, self._ciclo_tras_demo)
                            return
                        self._fin_generacion()
                        break
            self._refrescar()
            self.raiz.after(C.FPS_MS, self._ciclo)
        except tk.TclError:
            pass

    def _ciclo_tras_demo(self):
        self._fin_generacion()
        self._ciclo()

    def ejecutar(self):
        self.raiz.mainloop()
