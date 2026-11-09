import json
import os
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox

import numpy as np

import cerebro
import config as C
import instrucciones as INS
import roms as ROMS
import tema as TM
from agente import Juego, Memoria, clave_celda, ram_vista
from consola import BITS
from grabador import BotonGrabar
from sonido import Altavoz
from tema import (AZUL, BORDE, FONDO, MONO, MORADO, NARANJA, ORO, REJILLA, ROJO, SEMI, SUTIL, TARJETA,
                  TARJETA2, TENUE, TEXTO, VERDE, FAMILIA)

try:
    from PIL import Image, ImageTk
except ImportError:
    Image = None

TECLAS = {"Up": "arriba", "Down": "abajo", "Left": "izquierda", "Right": "derecha",
          "x": "A", "X": "A", "a": "A", "A": "A", "space": "A", "z": "B", "Z": "B", "s": "B", "S": "B",
          "Return": "START", "BackSpace": "SELECT", "Shift_R": "SELECT"}
MOSAICO = 6
ESTADOS_FIN = {"pasos": "tiempo", "vida": "perdió vida", "quieto": "se atoró", "bucle": "dio vueltas"}
ULTIMA = os.path.join(C.CARPETA_DATOS, "ultima_rom.json")


def popcount(v):
    return bin(v).count("1")


def accion_cercana(mascaras, h):
    return max(range(len(mascaras)), key=lambda i: 2 * popcount(mascaras[i] & h) - popcount(mascaras[i] ^ h))


class Tarjeta(tk.Frame):
    def __init__(self, padre, titulo, **kw):
        super().__init__(padre, bg=TARJETA, highlightthickness=1, highlightbackground=BORDE, **kw)
        cab = tk.Frame(self, bg=TARJETA)
        cab.pack(fill="x", padx=12, pady=(10, 4))
        tk.Frame(cab, bg=ORO, width=3, height=14).pack(side="left", padx=(0, 8))
        tk.Label(cab, text=titulo, bg=TARJETA, fg=TEXTO, font=(SEMI, 11)).pack(side="left")
        self.cuerpo = tk.Frame(self, bg=TARJETA)
        self.cuerpo.pack(fill="both", expand=True, padx=12, pady=(0, 10))


class Aplicacion:
    def __init__(self, rom=None, vista="ia", nuevo=False, entrenar=False):
        self.raiz = tk.Tk()
        self.raiz.title("Emulador GBC · IA que aprende a jugar")
        self.raiz.configure(bg=FONDO)
        sw, sh = self.raiz.winfo_screenwidth(), self.raiz.winfo_screenheight()
        self.escala = C.ESCALA if sh >= 900 and sw >= 1400 else 2
        self.ancho, self.alto = 160 * self.escala, 144 * self.escala
        self.compacto = self.escala < 3
        w, h = min(1400, sw - 20), min(880, sh - 70)
        self.raiz.geometry(f"{w}x{h}+{max(0, (sw - w) // 2)}+0")
        self.ent = None
        self.jugador = None
        self.ia = None
        self.modo = vista
        self.cargando = False
        self.nuevo = nuevo
        self.entrenar_al_cargar = entrenar
        self.teclas = set()
        self.rapido = False
        self.pausa = False
        self.velocidad_ia = 1
        self.deuda = 0.0
        self.reloj = time.perf_counter()
        self.cuadro_n = 0
        self.fps_real = 0.0
        self._fps_cuenta = (time.perf_counter(), 0)
        self.foto = None
        self.demos = {"obs": [], "prev": [], "ultima": [], "quieto": [], "accion": [], "rasgos": []}
        self.paso_humano = {"previo": None, "ultima": -1, "quieto": 0, "clave": None, "vistas": Memoria(),
                            "sin_novedad": 0, "n": 0}
        self.paso_ia = {"previo": None, "ultima": -1, "quieto": 0, "clave": None, "probs": None, "vistas": Memoria(),
                        "sin_novedad": 0}
        self.politica = None
        self.politica_t = 0.0
        self.rng_ia = np.random.default_rng()
        self.control = False
        self.mensajes = []
        self.ultimo_panel = 0.0
        self.altavoz = Altavoz()
        self.ajustes = self._leer_ajustes()
        self.altavoz.activo = self.ajustes.get("sonido", True)
        self.mosaico = None
        self._construir()
        self.raiz.protocol("WM_DELETE_WINDOW", self.cerrar)
        self.raiz.bind("<KeyPress>", self._tecla_abajo)
        self.raiz.bind("<KeyRelease>", self._tecla_arriba)
        self.refrescar_biblioteca()
        ruta = rom
        if ruta and os.path.exists(ruta) and os.path.dirname(os.path.abspath(ruta)) != os.path.abspath(C.CARPETA_ROMS):
            try:
                ruta = ROMS.agregar(ruta)
            except Exception as e:
                self.avisar(f"No pude abrir {ruta}: {e}")
                ruta = None
        if not ruta:
            try:
                with open(ULTIMA, encoding="utf-8") as f:
                    ruta = json.load(f).get("ruta")
            except (OSError, ValueError):
                ruta = None
        if ruta and os.path.exists(ruta):
            self.cargar_rom(ruta)
        self.raiz.after(20, self.tick)

    def _construir(self):
        r = self.raiz
        cab = tk.Canvas(r, bg=FONDO, height=62, highlightthickness=0)
        cab.pack(fill="x", padx=16, pady=(10, 0))
        TM.logo(cab, 4, 6, 1.1)
        cab.create_text(52, 18, text="Emulador Game Boy Color", anchor="w", fill=TEXTO, font=(SEMI, 17))
        cab.create_text(52, 44, text="una IA que lee las instrucciones, explora y aprende a jugar",
                        anchor="w", fill=TENUE, font=(FAMILIA, 10))
        self.cab = cab
        cab.bind("<Configure>", lambda e: cab.coords(self.chip_juego, e.width - 4, 30))
        self.chip_juego = cab.create_text(1380, 30, text="sin juego", anchor="e", fill=ORO, font=(SEMI, 12))

        cuerpo = tk.Frame(r, bg=FONDO)
        cuerpo.pack(fill="both", expand=True, padx=16, pady=12)
        izq = tk.Frame(cuerpo, bg=FONDO, width=250 if self.compacto else 300)
        izq.pack(side="left", fill="y")
        izq.pack_propagate(False)
        der = tk.Frame(cuerpo, bg=FONDO, width=340 if self.compacto else 380)
        der.pack(side="right", fill="y")
        der.pack_propagate(False)
        centro = tk.Frame(cuerpo, bg=FONDO)
        centro.pack(side="left", fill="both", expand=True, padx=14)

        bib = Tarjeta(izq, "Biblioteca de ROMs")
        bib.pack(fill="both", expand=True)
        tk.Label(bib.cuerpo, text="Se copian a la carpeta roms y se quedan hasta que tú las borres",
                 bg=TARJETA, fg=TENUE, font=(FAMILIA, 9), wraplength=220 if self.compacto else 260, justify="left").pack(anchor="w")
        self.lista = tk.Listbox(bib.cuerpo, bg=TARJETA2, fg=TEXTO, selectbackground=ORO, selectforeground=FONDO,
                                highlightthickness=0, bd=0, font=(FAMILIA, 10), activestyle="none")
        self.lista.pack(fill="both", expand=True, pady=6)
        self.lista.bind("<Double-Button-1>", lambda e: self._abrir_seleccion())
        fila = tk.Frame(bib.cuerpo, bg=TARJETA)
        fila.pack(fill="x")
        TM.Boton(fila, "Abrir", self._abrir_seleccion, color=ORO, primario=True).pack(side="left")
        TM.Boton(fila, "Agregar ROM…", self.agregar_rom).pack(side="left", padx=6)
        TM.Boton(fila, "Borrar", self.borrar_rom, color=TARJETA2).pack(side="left")
        fila2 = tk.Frame(bib.cuerpo, bg=TARJETA)
        fila2.pack(fill="x", pady=(6, 0))
        TM.Boton(fila2, "Carpeta roms", lambda: os.startfile(C.CARPETA_ROMS)).pack(side="left")

        ins = Tarjeta(izq, "Instrucciones del juego")
        ins.pack(fill="x", pady=(12, 0))
        self.lbl_ins = tk.Label(ins.cuerpo, text="Carga un juego", bg=TARJETA, fg=TEXTO, font=(FAMILIA, 9),
                                justify="left", anchor="w", wraplength=220 if self.compacto else 260)
        self.lbl_ins.pack(fill="x")
        fila = tk.Frame(ins.cuerpo, bg=TARJETA)
        fila.pack(fill="x", pady=(8, 0))
        TM.Boton(fila, "Editar / pegar", self.editar_instrucciones).pack(side="left")
        TM.Boton(fila, "Cargar archivo…", self.cargar_instrucciones).pack(side="left", padx=6)

        marco = tk.Frame(centro, bg="#05060a", highlightthickness=1, highlightbackground=BORDE)
        marco.pack(pady=(0, 10))
        self.pantalla = tk.Canvas(marco, width=self.ancho, height=self.alto, bg="#05060a", highlightthickness=0)
        self.pantalla.pack(padx=10, pady=10)
        self.img_id = self.pantalla.create_image(0, 0, anchor="nw")
        self.txt_pantalla = self.pantalla.create_text(self.ancho // 2, self.alto // 2, text="Abre una ROM de la biblioteca",
                                                      fill=TENUE, font=(SEMI, 14))

        modos = tk.Frame(centro, bg=FONDO)
        modos.pack()
        self.b_modos = {
            "jugar": TM.Boton(modos, "🎮 Jugar tú", lambda: self.cambiar_modo("jugar"), ancho=11),
            "ia": TM.Boton(modos, "🤖 Ver a la IA", lambda: self.cambiar_modo("ia"), ancho=11),
            "generacion": TM.Boton(modos, "👥 Generación", lambda: self.cambiar_modo("generacion"), ancho=11),
            "turbo": TM.Boton(modos, "⚡ Turbo", lambda: self.cambiar_modo("turbo"), ancho=11),
        }
        for b in self.b_modos.values():
            b.pack(side="left", padx=4)

        acc = tk.Frame(centro, bg=FONDO)
        acc.pack(pady=(10, 4))
        acc2 = tk.Frame(centro, bg=FONDO)
        acc2.pack(pady=(0, 8))
        self.b_entrenar = TM.Boton(acc, "▶ Entrenar", self.alternar_entrenamiento, color=VERDE, primario=True, ancho=12)
        self.b_entrenar.pack(side="left", padx=4)
        TM.Boton(acc, "💾 Guardar", self.guardar).pack(side="left", padx=4)
        TM.Boton(acc, "📍 Fijar inicio aquí", self.fijar_inicio).pack(side="left", padx=4)
        self.b_control = TM.Boton(acc, "🕹 Tomar control", self.alternar_control, color=MORADO, ancho=16)
        self.b_control.pack(side="left", padx=4)
        self.b_vel = TM.Boton(acc2, "IA ×1", self.cambiar_velocidad, ancho=6)
        self.b_vel.pack(side="left", padx=4)
        TM.Boton(acc2, "↺ Reiniciar IA", self.reiniciar_ia, color=TARJETA2).pack(side="left", padx=4)
        self.b_sonido = TM.Boton(acc2, "", self.alternar_sonido, ancho=11)
        self.b_sonido.pack(side="left", padx=4)
        self.grabar = TM.estilo_grabar(BotonGrabar(acc2, self.raiz, self.avisar, (SEMI, 10)))
        self.grabar.pack(side="left", padx=4)

        self.lbl_ayuda = tk.Label(centro, bg=FONDO, fg=TENUE, font=(FAMILIA, 9), justify="center", wraplength=520,
                                  text="Flechas · A / X / Espacio = botón A · S / Z = botón B · Enter = Start · "
                                       "Retroceso = Select · Tab = rápido · P = pausa · M = sonido · "
                                       "T = tomar / devolver el control a la IA · F1/F2 = guardar/cargar estado · F5 = guardar IA")
        self.lbl_ayuda.pack()

        est = Tarjeta(der, "Entrenamiento")
        est.pack(fill="x")
        self.datos = {}
        rej = tk.Frame(est.cuerpo, bg=TARJETA)
        rej.pack(fill="x")
        campos = [("gen", "Generación", ORO), ("apt", "Aptitud de la IA", VERDE), ("max", "Mejor individuo", AZUL),
                  ("celdas", "Pantallas descubiertas", MORADO), ("archivo", "Puntos de control", NARANJA),
                  ("seg", "Seg. / generación", TENUE), ("vidas", "Vidas (RAM)", ROJO),
                  ("puntos", "Puntos (RAM)", ORO), ("pos", "Posición / mapa (RAM)", VERDE),
                  ("avance", "Avance (historia)", NARANJA), ("demos", "Tus jugadas", AZUL),
                  ("fps", "Cuadros / s", TENUE)]
        for i, (k, t, color) in enumerate(campos):
            c = tk.Frame(rej, bg=TARJETA2)
            c.grid(row=i // 2, column=i % 2, sticky="nsew", padx=3, pady=3)
            tk.Frame(c, bg=color, width=3).pack(side="left", fill="y")
            tk.Label(c, text=t, bg=TARJETA2, fg=TENUE, font=(FAMILIA, 8)).pack(anchor="w", padx=8, pady=(4, 0))
            v = tk.Label(c, text="—", bg=TARJETA2, fg=TEXTO, font=(SEMI, 12))
            v.pack(anchor="w", padx=8, pady=(0, 4))
            self.datos[k] = v
        rej.columnconfigure(0, weight=1)
        rej.columnconfigure(1, weight=1)

        graf = Tarjeta(der, "Aptitud por generación")
        graf.pack(fill="x", pady=(12, 0))
        self.alto_graf = 110 if self.compacto else 150
        self.grafica = tk.Canvas(graf.cuerpo, width=310 if self.compacto else 350, height=self.alto_graf, bg=TARJETA, highlightthickness=0)
        self.grafica.pack()

        pien = Tarjeta(der, "Lo que piensa la IA")
        pien.pack(fill="x", pady=(12, 0))
        self.barras = tk.Canvas(pien.cuerpo, width=310 if self.compacto else 350, height=120, bg=TARJETA, highlightthickness=0)
        self.barras.pack()

        men = Tarjeta(der, "Avisos")
        men.pack(fill="both", expand=True, pady=(12, 0))
        self.lbl_men = tk.Label(men.cuerpo, text="", bg=TARJETA, fg=TEXTO, font=(FAMILIA, 9), justify="left",
                                anchor="nw", wraplength=300 if self.compacto else 340)
        self.lbl_men.pack(fill="both", expand=True)
        self._pintar_modos()

    def avisar(self, texto):
        self.mensajes.append(time.strftime("%H:%M ") + texto)
        self.mensajes = self.mensajes[-7:]
        try:
            self.lbl_men.configure(text="\n".join(self.mensajes))
        except tk.TclError:
            pass

    def refrescar_biblioteca(self):
        self.libros = ROMS.biblioteca()
        sel = self.lista.curselection()
        self.lista.delete(0, "end")
        for b in self.libros:
            color = "CGB" if b.get("cgb") else "DMG"
            self.lista.insert("end", f"{b['titulo'][:22]:22}  {color}")
        if sel and sel[0] < len(self.libros):
            self.lista.selection_set(sel[0])

    def _abrir_seleccion(self):
        sel = self.lista.curselection()
        if not sel:
            return
        b = self.libros[sel[0]]
        if b.get("id") is None:
            messagebox.showerror("ROM ilegible", b.get("error", "no se pudo leer"))
            return
        self.cargar_rom(b["ruta"])

    def agregar_rom(self):
        rutas = filedialog.askopenfilenames(title="Elige ROMs de Game Boy / Game Boy Color",
                                            filetypes=[("ROMs", "*.gb *.gbc *.cgb *.zip"), ("Todos", "*.*")])
        for ruta in rutas:
            try:
                destino = ROMS.agregar(ruta)
                self.avisar(f"Agregada {os.path.basename(destino)}")
            except Exception as e:
                messagebox.showerror("No es una ROM válida", f"{os.path.basename(ruta)}: {e}")
        self.refrescar_biblioteca()

    def borrar_rom(self):
        sel = self.lista.curselection()
        if not sel:
            return
        b = self.libros[sel[0]]
        if not messagebox.askyesno("Borrar ROM", f"¿Borrar {b['archivo']} ahora? Lo aprendido por la IA se conserva."):
            return
        if self.ent and os.path.abspath(self.ent.ruta_rom) == os.path.abspath(b["ruta"]):
            self.descargar_juego("La ROM se borró; lo aprendido queda guardado")
        ROMS.borrar(b["archivo"])
        self.refrescar_biblioteca()

    def cargar_rom(self, ruta):
        if self.cargando:
            return
        self.cargando = True
        self.pantalla.itemconfigure(self.txt_pantalla, text="Cargando y compilando el emulador…", state="normal")
        viejo = self.ent
        self._enviar_demos(esperar=True)
        if self.jugador:
            self.jugador.gb.guardar_bateria()
        self.ent = None
        resultado = {}

        def trabajo():
            try:
                if viejo:
                    viejo.cerrar()
                e = __import__("entrenador").Entrenador(ruta, continuar=not self.nuevo)
                if self.nuevo:
                    e.reiniciar()
                    self.nuevo = False
                resultado["ent"] = e
            except Exception as ex:
                resultado["error"] = ex

        hilo = threading.Thread(target=trabajo, daemon=True)
        hilo.start()

        def esperar():
            if hilo.is_alive():
                self.raiz.after(100, esperar)
                return
            self.cargando = False
            if "error" in resultado:
                self.pantalla.itemconfigure(self.txt_pantalla, text="No se pudo cargar")
                messagebox.showerror("Error al cargar", str(resultado["error"]))
                return
            self._preparar(resultado["ent"], ruta)

        esperar()

    def _preparar(self, ent, ruta):
        self.ent = ent
        for m in ent.mensajes:
            self.avisar(m)
        ent.mensajes.clear()
        self.jugador = Juego(ruta, ent.acciones, ent.perfil, ruta_sav=ent.ruta_sav)
        self.ia = Juego(ruta, ent.acciones, ent.perfil)
        self.jugador.gb.sonido(True)
        self.ia.gb.sonido(True)
        self.mosaico = None
        self._reiniciar_pasos()
        self._nuevo_episodio_ia(avisar=False)
        self.politica = None
        self.pantalla.itemconfigure(self.txt_pantalla, state="hidden")
        info = ent.info
        self.cab.itemconfigure(self.chip_juego, text=f"{info['titulo']}  ·  {'Color' if info['cgb'] else 'Game Boy'}"
                                                     f"  ·  MBC{info['mbc']}")
        self.raiz.title(f"{info['titulo']} · Emulador GBC con IA")
        self._pintar_instrucciones()
        os.makedirs(C.CARPETA_DATOS, exist_ok=True)
        with open(ULTIMA, "w", encoding="utf-8") as f:
            json.dump({"ruta": ruta}, f)
        self.avisar(f"Listo: {info['titulo']} ({len(ent.acciones)} acciones para la IA)")
        if self.entrenar_al_cargar or self.modo == "turbo":
            self.entrenar_al_cargar = False
            ent.iniciar()
        self._pintar_modos()

    def descargar_juego(self, motivo):
        if self.ent:
            self._enviar_demos(esperar=True)
            if self.jugador:
                self.jugador.gb.guardar_bateria()
            self.ent.cerrar()
        self.ent = self.jugador = self.ia = None
        self.mosaico = None
        self.pantalla.itemconfigure(self.img_id, image="")
        self.pantalla.itemconfigure(self.txt_pantalla, text=motivo, state="normal")
        self.cab.itemconfigure(self.chip_juego, text="sin juego")
        self.avisar(motivo)
        self._pintar_modos()

    def _reiniciar_pasos(self):
        for p in (self.paso_humano, self.paso_ia):
            p.update({"previo": None, "ultima": -1, "quieto": 0, "clave": None, "vistas": Memoria(), "sin_novedad": 0})

    def _sincronizar(self, j):
        if self.ent:
            j.configurar(self.ent.acciones, self.ent.perfil, self.ent.mascara_banderas())

    def _novedad(self, p, j, obs, ram):
        etapa = j.avance(ram)[0] if j.con_avance else 0
        k = clave_celda(obs, j.extra(ram))
        kp = j.clave_pos(ram, etapa)
        nuevo = False
        for kk in (k, kp):
            if kk is not None and kk not in p["vistas"]:
                p["vistas"].add(kk)
                nuevo = True
        p["sin_novedad"] = 0 if nuevo else p["sin_novedad"] + 1
        return k, kp, etapa

    def _pintar_instrucciones(self):
        if not self.ent:
            return
        a = self.ent.analisis
        lineas = INS.resumen(a)
        lineas.append("Botones: " + " ".join(INS.nombre_accion(x) for x in self.ent.acciones))
        self.lbl_ins.configure(text="\n".join(lineas))

    def editar_instrucciones(self):
        if not self.ent:
            return
        v = tk.Toplevel(self.raiz, bg=FONDO)
        v.title("Instrucciones · " + self.ent.info["titulo"])
        v.geometry("640x520")
        tk.Label(v, text="Pega aquí el manual o las instrucciones (español o inglés). La IA busca qué hace cada "
                         "botón, cuántas vidas hay y qué hay que juntar.", bg=FONDO, fg=TENUE, font=(FAMILIA, 9),
                 wraplength=600, justify="left").pack(anchor="w", padx=12, pady=(10, 4))
        t = tk.Text(v, bg=TARJETA2, fg=TEXTO, insertbackground=TEXTO, font=(FAMILIA, 10), wrap="word", bd=0)
        t.pack(fill="both", expand=True, padx=12)
        t.insert("1.0", self.ent.texto)
        fila = tk.Frame(v, bg=FONDO)
        fila.pack(fill="x", padx=12, pady=10)

        def guardar():
            self.aplicar_instrucciones(t.get("1.0", "end").strip())
            v.destroy()

        TM.Boton(fila, "Guardar y analizar", guardar, color=ORO, primario=True).pack(side="right")

    def cargar_instrucciones(self):
        if not self.ent:
            return
        ruta = filedialog.askopenfilename(title="Instrucciones del juego",
                                          filetypes=[("Texto o PDF", "*.txt *.md *.pdf"), ("Todos", "*.*")])
        if not ruta:
            return
        try:
            self.aplicar_instrucciones(INS.leer_archivo(ruta))
        except Exception as e:
            messagebox.showerror("No se pudo leer", str(e))

    def aplicar_instrucciones(self, texto):
        ent = self.ent
        seguia = ent.corriendo
        self.b_entrenar.texto("…")

        def trabajo():
            ent.detener(esperar=True)
            with ent.cerrojo:
                ent.leer_instrucciones(texto)

        hilo = threading.Thread(target=trabajo, daemon=True)
        hilo.start()

        def esperar():
            if hilo.is_alive():
                self.raiz.after(100, esperar)
                return
            for j in (self.jugador, self.ia):
                self._sincronizar(j)
            self.mosaico = None
            self._reiniciar_pasos()
            self.politica = None
            self._pintar_instrucciones()
            self.avisar("Instrucciones analizadas")
            if seguia:
                ent.iniciar()
            self._pintar_modos()

        esperar()

    def alternar_control(self):
        if not self.ent or not self.ia or self.cargando:
            return
        if self.control:
            self.control = False
            self.ia.gb.pulsar(0)
            self.teclas.clear()
            self._enviar_demos()
            self.paso_ia.update({"previo": None, "ultima": -1, "quieto": 0, "clave": None, "vistas": Memoria(),
                                 "sin_novedad": 0, "paso": 0, "racha": 0})
            self.avisar("La IA retoma el control desde aquí y aprende de lo que hiciste")
        else:
            if self.modo != "ia":
                self.cambiar_modo("ia")
            self.control = True
            self.teclas.clear()
            self.paso_humano.update({"previo": None, "ultima": -1, "quieto": 0, "clave": None, "vistas": Memoria(),
                                     "sin_novedad": 0, "n": 0})
            self.avisar("Tienes el control: la IA sigue entrenando, graba tus jugadas y aprende de ellas "
                        "(T o el botón para devolverlo)")
        self.altavoz.vaciar()
        self.deuda = 0.0
        self._pintar_modos()

    def cambiar_modo(self, modo):
        if modo == self.modo:
            return
        if self.control and modo != "ia":
            self.alternar_control()
        if self.modo == "jugar":
            self._enviar_demos()
            if self.jugador:
                self.jugador.gb.pulsar(0)
        self.modo = modo
        if modo == "turbo" and self.ent and not self.ent.corriendo:
            self.ent.iniciar()
        if modo != "generacion":
            self.pantalla.delete("mosaico")
            self.pantalla.configure(width=self.ancho)
            self.pantalla.coords(self.txt_pantalla, self.ancho // 2, self.alto // 2)
        else:
            self.pantalla.configure(width=max(self.ancho, 480))
        self.altavoz.vaciar()
        self.deuda = 0.0
        self._pintar_modos()

    def _pintar_modos(self):
        for k, b in self.b_modos.items():
            b.color = ORO if k == self.modo else TARJETA2
            b.w.configure(bg=b.color, fg=FONDO if k == self.modo else TEXTO)
        corriendo = bool(self.ent and self.ent.corriendo)
        self.b_entrenar.color = ROJO if corriendo else VERDE
        self.b_entrenar.w.configure(bg=self.b_entrenar.color)
        self.b_entrenar.texto("⏸ Pausar IA" if corriendo else "▶ Entrenar")
        self.b_control.color = ROJO if self.control else MORADO
        self.b_control.w.configure(bg=self.b_control.color)
        self.b_control.texto("🤖 Devolver control" if self.control else "🕹 Tomar control")
        if not self.altavoz.disponible:
            self.b_sonido.texto("🔇 Sin audio")
        else:
            self.b_sonido.texto("🔊 Sonido" if self.altavoz.activo else "🔇 Silencio")

    def alternar_entrenamiento(self):
        if not self.ent:
            return
        if self.ent.corriendo:
            self.ent.detener()
            self.avisar("El entrenamiento se detiene al terminar la generación en curso")
        else:
            self.ent.iniciar()
            self.avisar(f"Entrenando con {self.ent.procesos} procesos")
        self._pintar_modos()

    def _leer_ajustes(self):
        try:
            with open(os.path.join(C.CARPETA_DATOS, "ajustes.json"), encoding="utf-8") as f:
                return json.load(f)
        except (OSError, ValueError):
            return {}

    def _guardar_ajustes(self):
        os.makedirs(C.CARPETA_DATOS, exist_ok=True)
        with open(os.path.join(C.CARPETA_DATOS, "ajustes.json"), "w", encoding="utf-8") as f:
            json.dump(self.ajustes, f)

    def alternar_sonido(self):
        if not self.altavoz.disponible:
            self.avisar("No hay salida de audio: " + (self.altavoz.error or "instala sounddevice"))
            return
        self.altavoz.activo = not self.altavoz.activo
        self.altavoz.vaciar()
        self.ajustes["sonido"] = self.altavoz.activo
        self._guardar_ajustes()
        self._pintar_modos()

    def cambiar_velocidad(self):
        self.velocidad_ia = {1: 2, 2: 4, 4: 8, 8: 1}[self.velocidad_ia]
        self.b_vel.texto(f"IA ×{self.velocidad_ia}")

    def guardar(self):
        if not self.ent:
            return
        self._enviar_demos(esperar=True)
        self.ent.guardar()
        if self.jugador:
            self.jugador.gb.guardar_bateria()
        self.avisar(f"Guardado en la generación {self.ent.generacion}")

    def fijar_inicio(self):
        if not self.ent:
            return
        fuente = self.jugador if self.modo == "jugar" else self.ia
        self.ent.fijar_inicio(fuente.gb.estado())
        self.avisar("La IA empezará a entrenar desde este momento del juego")

    def reiniciar_ia(self):
        if not self.ent:
            return
        if not messagebox.askyesno("Reiniciar IA", "¿Borrar lo aprendido por la IA en este juego? "
                                                   "Tus jugadas grabadas y tu partida se conservan."):
            return
        ent = self.ent

        def trabajo():
            ent.reiniciar()
            if len(ent.demos["accion"]):
                with ent.cerrojo:
                    ent.imitar(C.PASOS_IMITACION)

        threading.Thread(target=trabajo, daemon=True).start()
        self.politica = None
        self._reiniciar_pasos()
        self._nuevo_episodio_ia(avisar=False)
        self._pintar_modos()

    def _tecla_abajo(self, e):
        if isinstance(e.widget, tk.Text):
            return
        k = e.keysym
        if k == "Tab":
            self.rapido = True
            return "break"
        if k in ("p", "P"):
            self.pausa = not self.pausa
        elif k == "F1":
            self._estado_rapido(True)
        elif k == "F2":
            self._estado_rapido(False)
        elif k == "F5":
            self.guardar()
        elif k in ("m", "M"):
            self.alternar_sonido()
        elif k in ("t", "T"):
            self.alternar_control()
        if k in TECLAS:
            self.teclas.add(TECLAS[k])

    def _tecla_arriba(self, e):
        k = e.keysym
        if k == "Tab":
            self.rapido = False
        if k in TECLAS:
            self.teclas.discard(TECLAS[k])

    def _estado_rapido(self, guardar):
        if not self.ent or not self.jugador:
            return
        ruta = os.path.join(self.ent.dir, "rapido.state")
        if guardar:
            with open(ruta, "wb") as f:
                f.write(self.jugador.gb.estado())
            self.avisar("Estado guardado (F2 para volver)")
        elif os.path.exists(ruta):
            with open(ruta, "rb") as f:
                self.jugador.gb.restaurar(f.read())
            self.paso_humano.update({"previo": None, "ultima": -1, "quieto": 0})
            self.avisar("Estado cargado")

    def _mascara_humana(self):
        m = 0
        for t in self.teclas:
            m |= BITS[t]
        return m

    def _paso_humano(self, j=None):
        j, p = j or self.jugador, self.paso_humano
        obs = j.gb.observar().copy()
        if p["previo"] is None:
            p["previo"] = obs
        p["n"] = p.get("n", 0) + 1
        if p["n"] % 150 == 1:
            self._sincronizar(j)
        h = self._mascara_humana()
        a = accion_cercana(j.mascaras, h)
        ram = ram_vista(j.gb)
        conocidas = self.ent.conocidas if self.ent else set()
        etapa = j.avance(ram)[0] if j.con_avance else 0
        p["vistas"].mover(j, ram, p["ultima"], etapa)
        rasgos = j.rasgos(ram, etapa, conocidas, p["vistas"], p["sin_novedad"])
        if not h:
            k, kp, etapa = self._novedad(p, j, obs, ram)
            p["quieto"] = p["quieto"] + 1 if k == p["clave"] else 0
            p["clave"] = k
            p["previo"] = obs
            p["ultima"] = a
            return
        d = self.demos
        d["obs"].append((obs.ravel() * 255).astype(np.uint8))
        d["prev"].append((p["previo"].ravel() * 255).astype(np.uint8))
        d["ultima"].append(p["ultima"])
        d["quieto"].append(min(p["quieto"] / C.QUIETO_MAX, 1.0))
        d["accion"].append(a)
        d["rasgos"].append(rasgos.astype(np.float16))
        k, kp, etapa = self._novedad(p, j, obs, ram)
        if self.ent and kp is None and k not in self.ent.conocidas:
            self.ent.agregar_celda(k, j.gb.estado(), avance=j.puntaje(ram))
        elif self.ent and kp is not None and kp not in self.ent.conocidas:
            self.ent.agregar_celda(kp, j.gb.estado(), avance=j.puntaje(ram))
        p["quieto"] = p["quieto"] + 1 if k == p["clave"] else 0
        p["clave"] = k
        p["previo"] = obs
        p["ultima"] = a
        if len(d["accion"]) >= 900:
            self._enviar_demos()

    def _enviar_demos(self, esperar=False):
        d = self.demos
        if not self.ent or len(d["accion"]) < 20:
            return
        lote = {k: np.array(v) for k, v in d.items()}
        self.demos = {k: [] for k in d}
        ent = self.ent
        hilo = threading.Thread(target=ent.agregar_demos,
                                args=(lote["obs"], lote["prev"], lote["ultima"], lote["quieto"], lote["accion"],
                                      lote["rasgos"]),
                                daemon=True)
        hilo.start()
        if esperar:
            hilo.join()
        self.politica = None

    def _nuevo_episodio_ia(self, fin=None, avisar=True):
        p = self.paso_ia
        n = p.get("episodio", -1) + 1
        inicio, avance = self.ent.inicio_para_ver(n)
        self.ia.gb.restaurar(inicio or self.ent.inicio)
        p.update({"previo": None, "ultima": -1, "quieto": 0, "clave": None, "vistas": Memoria(), "sin_novedad": 0,
                  "paso": 0, "racha": 0, "episodio": n})
        if avisar:
            donde = "desde el inicio" if avance is None else f"desde un punto de control (avance {avance:.0f})"
            self.avisar(f"Ver IA: {ESTADOS_FIN.get(fin, fin)}; episodio {n + 1} {donde}")

    def _paso_ia(self):
        j, p = self.ia, self.paso_ia
        if self.politica is None or time.time() - self.politica_t > 3:
            with self.ent.cerrojo:
                theta = self.ent.theta.copy()
            if len(theta) == cerebro.tamano(j.n, C.OCULTAS):
                self.politica = cerebro.Politica(theta, j.n, C.OCULTAS)
                self.politica_t = time.time()
                self._sincronizar(j)
        obs = j.gb.observar().copy()
        if p["previo"] is None:
            p["previo"] = obs
        ram = ram_vista(j.gb)
        k, kp, etapa = self._novedad(p, j, obs, ram)
        p["vistas"].mover(j, ram, p["ultima"], etapa)
        x = j.entrada(obs, p["previo"], p["ultima"], p["quieto"], ram, self.ent.conocidas, p["vistas"],
                      p["sin_novedad"], etapa)
        probs = self.politica.probabilidades(x) if self.politica else np.full(j.n, 1.0 / j.n)
        a, p["racha"] = j.decidir(lambda: np.log(probs + 1e-12), self.rng_ia, p["ultima"], p.get("racha", 0),
                                  p["quieto"], C.EPSILON)
        p["probs"] = probs
        p["paso"] = p.get("paso", 0) + 1
        p["quieto"] = p["quieto"] + 1 if k == p["clave"] else 0
        p["clave"] = k
        p["previo"] = obs
        p["ultima"] = a
        j.gb.pulsar(j.mascaras[a])
        con_pos = j.i_pos is not None
        fin = None
        if p["quieto"] >= C.QUIETO_MAX:
            fin = "quieto"
        elif p["sin_novedad"] >= (C.SIN_NOVEDAD_POS if con_pos else C.SIN_NOVEDAD_MAX):
            fin = "bucle"
        elif p["paso"] >= (C.PASOS_EPISODIO_POS if con_pos else C.PASOS_EPISODIO):
            fin = "pasos"
        if fin:
            self._nuevo_episodio_ia(fin)

    def tick(self):
        ahora = time.perf_counter()
        dt = min(ahora - self.reloj, 0.1)
        self.reloj = ahora
        hubo = False
        if self.ent and not self.cargando and not self.pausa and self.modo == "generacion":
            self.deuda += dt * C.FPS * self.velocidad_ia
            n = min(int(self.deuda), 8 * self.velocidad_ia)
            self.deuda -= n
            if self.deuda > 4 * self.velocidad_ia:
                self.deuda = 0.0
            if n:
                self._avanzar_mosaico(n)
        elif self.ent and not self.cargando and not self.pausa and self.modo != "turbo":
            humano = self.modo == "jugar" or (self.control and self.modo == "ia")
            vel = (4 if self.rapido else 1) if humano else self.velocidad_ia
            self.deuda += dt * C.FPS * vel
            n = min(int(self.deuda), 8 * vel)
            self.deuda -= n
            if vel == 1 and not self.rapido and self.altavoz.activo and self.altavoz.disponible:
                lleno = len(self.altavoz.bufer)
                if lleno < 1500 and n == 0:
                    n = 1
                    self.deuda -= 1
                elif lleno > 5000 and n > 0:
                    n -= 1
                    self.deuda += 1
            if self.deuda > 4 * vel:
                self.deuda = 0.0
            j = self.jugador if self.modo == "jugar" else self.ia
            for _ in range(n):
                if self.cuadro_n % C.ACCION_CADA == 0:
                    if humano:
                        self._paso_humano(j)
                    else:
                        self._paso_ia()
                if humano:
                    j.gb.pulsar(self._mascara_humana())
                j.gb.cuadros(1)
                self.cuadro_n += 1
                hubo = True
            muestras = j.gb.audio()
            if vel == 1 and not self.rapido:
                self.altavoz.empujar(muestras)
            if hubo:
                self._mostrar(j.gb.fb)
                t0, c0 = self._fps_cuenta
                c0 += n
                if ahora - t0 >= 1.0:
                    self.fps_real = c0 / (ahora - t0)
                    self._fps_cuenta = (ahora, 0)
                else:
                    self._fps_cuenta = (t0, c0)
        if ahora - self.ultimo_panel > 0.4:
            self.ultimo_panel = ahora
            self._panel()
        self.raiz.after(4, self.tick)

    def _nuevo_mosaico(self):
        ent = self.ent
        g = ent.vista_generacion()
        n = len(ent.theta)
        if self.mosaico and len(self.mosaico["juegos"]) == MOSAICO:
            juegos = self.mosaico["juegos"]
        else:
            juegos = [Juego(ent.ruta_rom, ent.acciones, ent.perfil) for _ in range(MOSAICO)]
        fichas = []
        for k in range(MOSAICO):
            par, signo = k // 2, (1 if k % 2 == 0 else -1)
            ruido = np.random.default_rng(g["semillas"][par % len(g["semillas"])]).standard_normal(n).astype(np.float32)
            theta = g["theta"] + signo * g["sigma"] * ruido
            j = juegos[k]
            j.configurar(ent.acciones, ent.perfil, ent.mascara_banderas())
            j.gb.restaurar(g["inicio"])
            fichas.append({"juego": j, "pol": cerebro.Politica(theta, j.n, C.OCULTAS), "i": k,
                           "rng": np.random.default_rng(g["semilla_juego"]), "previo": None, "ultima": -1,
                           "quieto": 0, "sin_novedad": 0, "clave": None, "vistas": Memoria(), "nuevas": 0, "paso": 0, "fin": None,
                           "ram": None})
        self.mosaico = {"gen": g["gen"], "juegos": juegos, "fichas": fichas, "previa": g.get("vista_previa", False)}

    def _paso_ficha(self, f):
        j = f["juego"]
        obs = j.gb.observar().copy()
        ram = ram_vista(j.gb)
        if f["previo"] is not None:
            k = clave_celda(obs, j.extra(ram))
            novedad = False
            if j.con_avance:
                etapa, valor, niveles, exp = j.avance(ram)
                marca = (valor, niveles, exp)
                if f.get("marca") is not None and marca > f["marca"]:
                    novedad = True
                f["marca"] = max(marca, f.get("marca") or marca)
            else:
                etapa = 0
            f["etapa"] = etapa
            f["vistas"].mover(j, ram, f["ultima"], etapa)
            for kk in (k, j.clave_pos(ram, etapa)):
                if kk is not None and kk not in f["vistas"]:
                    f["vistas"].add(kk)
                    novedad = True
                    if kk not in self.ent.conocidas and (kk != k or j.i_pos is None):
                        f["nuevas"] += 1
            f["sin_novedad"] = 0 if novedad else f["sin_novedad"] + 1
            f["quieto"] = f["quieto"] + 1 if k == f["clave"] else 0
            f["clave"] = k
            if j.i_vidas is not None and f["ram"] is not None and ram[j.i_vidas] < f["ram"][j.i_vidas]:
                f["fin"] = "vida"
            elif f["quieto"] >= C.QUIETO_MAX:
                f["fin"] = "quieto"
            elif f["sin_novedad"] >= (C.SIN_NOVEDAD_POS if j.i_pos is not None else C.SIN_NOVEDAD_MAX):
                f["fin"] = "bucle"
            elif f["paso"] >= (C.PASOS_EPISODIO_POS if j.i_pos is not None else C.PASOS_EPISODIO):
                f["fin"] = "pasos"
            if f["fin"]:
                j.gb.pulsar(0)
                return
        else:
            f["previo"] = obs
        f["ram"] = ram
        x = j.entrada(obs, f["previo"], f["ultima"], f["quieto"], ram, self.ent.conocidas, f["vistas"],
                      f["sin_novedad"], f.get("etapa"))
        a, f["racha"] = j.decidir(lambda: f["pol"].logits(x), f["rng"], f["ultima"], f.get("racha", 0),
                                  f["quieto"], C.EPSILON)
        f["previo"] = obs
        f["ultima"] = a
        f["paso"] += 1
        j.gb.pulsar(j.mascaras[a])

    def _avanzar_mosaico(self, n):
        if self.mosaico is None:
            self._nuevo_mosaico()
        m = self.mosaico
        for f in m["fichas"]:
            if f["fin"]:
                continue
            for _ in range(n):
                if f["fin"]:
                    break
                if self.cuadro_n % C.ACCION_CADA == 0 or f["previo"] is None:
                    self._paso_ficha(f)
                    if f["fin"]:
                        break
                f["juego"].gb.cuadros(1)
            f["juego"].gb.audio()
        self.cuadro_n += n
        self._mostrar_mosaico()
        if all(f["fin"] for f in m["fichas"]):
            m.setdefault("terminado", time.time())
            if time.time() - m["terminado"] > 2.5:
                self._nuevo_mosaico()

    def _mostrar_mosaico(self):
        m = self.mosaico
        cols, filas = 3, 2
        ancho = max(self.ancho, 480)
        tw = ancho // cols
        th = min(self.alto // filas, tw * 144 // 160 + 6)
        y0 = (self.alto - th * filas) // 2
        if Image is not None:
            lienzo = Image.new("RGB", (ancho, self.alto), (5, 6, 10))
            for f in m["fichas"]:
                c, r = f["i"] % cols, f["i"] // cols
                img = Image.fromarray(f["juego"].gb.fb).resize((tw - 6, th - 6), Image.NEAREST)
                if f["fin"]:
                    img = img.point(lambda v: v * 2 // 5)
                lienzo.paste(img, (c * tw + 3, y0 + r * th + 3))
            self.foto = ImageTk.PhotoImage(lienzo)
            self.pantalla.itemconfigure(self.img_id, image=self.foto)
        cv = self.pantalla
        cv.delete("mosaico")
        apt = self.ent.ultimas_aptitudes if self.ent else None
        oficial = apt is not None and apt["gen"] == m["gen"]
        mejor = int(np.argmax(apt["aptitudes"][:MOSAICO])) if oficial else -1
        for f in m["fichas"]:
            c, r = f["i"] % cols, f["i"] // cols
            x0, y1 = c * tw + 3, y0 + r * th + 3
            if f["i"] == mejor:
                cv.create_rectangle(x0 - 2, y1 - 2, x0 + tw - 4, y1 + th - 4, outline=ORO, width=2, tags="mosaico")
            signo = "+" if f["i"] % 2 == 0 else "−"
            cv.create_text(x0 + 4, y1 + 3, anchor="nw", text=f"#{f['i'] + 1} ({f['i'] // 2 + 1}{signo})",
                           fill=ORO, font=(SEMI, 8), tags="mosaico")
            if oficial:
                cv.create_text(x0 + tw - 10, y1 + 3, anchor="ne", text=f"apt {apt['aptitudes'][f['i']]:.1f}",
                               fill=VERDE, font=(SEMI, 8), tags="mosaico")
            cv.create_text(x0 + 4, y1 + th - 9, anchor="sw", text=f"nuevas {f['nuevas']}", fill=TEXTO,
                           font=(FAMILIA, 8), tags="mosaico")
            if f["fin"]:
                cv.create_text(x0 + (tw - 6) / 2, y1 + (th - 6) / 2, text=ESTADOS_FIN[f["fin"]], fill=TEXTO,
                               font=(SEMI, 10), tags="mosaico")
        cab = f"Generación {m['gen']}" + (" (vista previa: aún no entrena)" if m["previa"] else "")
        if self.ent and self.ent.corriendo and self.ent.generacion + 1 != m["gen"]:
            cab += f"  ·  el entrenamiento va en la {self.ent.generacion + 1}"
        if y0 > 14:
            cv.create_text(ancho // 2, y0 - 6, anchor="s", text=cab, fill=TENUE, font=(SEMI, 9), tags="mosaico")

    def _mostrar(self, fb):
        if Image is not None:
            img = Image.fromarray(fb).resize((self.ancho, self.alto), Image.NEAREST)
            if self.modo == "turbo":
                img = img.point(lambda v: v // 3)
            self.foto = ImageTk.PhotoImage(img)
        else:
            self.foto = TM.foto(np.repeat(np.repeat(fb, self.escala, 0), self.escala, 1))
        self.pantalla.itemconfigure(self.img_id, image=self.foto)

    def _panel(self):
        ent = self.ent
        if ent:
            for m in ent.mensajes:
                self.avisar(m)
            ent.mensajes.clear()
        h = ent.historial[-1] if ent and ent.historial else None
        d = self.datos
        if ent and ent.corriendo and ent.progreso[1]:
            d["gen"].configure(text=f"{ent.generacion + 1} · {ent.progreso[0]}/{ent.progreso[1]}")
        else:
            d["gen"].configure(text=str(ent.generacion) if ent else "—")
        d["apt"].configure(text=f"{h['centro']:.1f}" if h else "—")
        d["max"].configure(text=f"{h['max']:.1f}" if h else "—")
        d["celdas"].configure(text=str(len(ent.conocidas)) if ent else "—")
        d["archivo"].configure(text=str(len(ent.archivo)) if ent else "—")
        d["seg"].configure(text=f"{h['segundos']:.1f}" if h else "—")
        if ent:
            v = ent.perfil.get("vidas")
            nada = "no aplica" if ent.perfil.get("posicion") else "buscando…"
            d["vidas"].configure(text=f"0x{v:04X}" if v is not None else nada)
            pts = ent.perfil.get("puntos") or []
            d["puntos"].configure(text=" ".join(f"{x:04X}" for x in pts[:3]) if pts else nada)
            pos, mapa = ent.perfil.get("posicion"), ent.perfil.get("mapa") or []
            d["pos"].configure(text=(f"{pos[0]:04X}/{pos[1]:04X}" + (f" · {mapa[0]:04X}" if mapa else ""))
                               if pos else "buscando…")
            d["avance"].configure(text=f"{ent.avance_maximo():.0f}" if ent.archivo else "—")
            d["demos"].configure(text=str(len(ent.demos["accion"]) + len(self.demos["accion"])))
        d["fps"].configure(text=f"{self.fps_real:.0f}" if self.modo != "turbo" else "turbo")
        self._pintar_modos()
        self._grafica()
        self._barras()
        if self.modo == "generacion":
            self.pantalla.itemconfigure(self.txt_pantalla, state="hidden")
        elif self.modo == "turbo" and self.ent and self.ia:
            self._mostrar(self.ia.gb.fb)
            self.pantalla.itemconfigure(self.txt_pantalla, state="normal",
                                        text=f"Entrenando en turbo…\ngeneración {ent.generacion}")
        elif self.ent and not self.cargando:
            self.pantalla.itemconfigure(self.txt_pantalla, state="hidden")

    def _grafica(self):
        cv = self.grafica
        cv.delete("all")
        w, hgt = int(self.grafica.cget("width")), self.alto_graf
        ml, mb = 34, 18
        hist = self.ent.historial if self.ent else []
        for i in range(5):
            y = 6 + (hgt - mb - 6) * i / 4
            cv.create_line(ml, y, w - 4, y, fill=REJILLA)
        if len(hist) < 2:
            cv.create_text(w / 2, hgt / 2, text="Las generaciones aparecerán aquí", fill=SUTIL, font=(FAMILIA, 9))
            return
        series = [("max", AZUL), ("centro", VERDE), ("media", ORO)]
        vals = np.array([[x[k] for k, _ in series] for x in hist[-200:]])
        lo, hi = float(vals.min()), float(vals.max())
        if hi - lo < 1e-6:
            hi = lo + 1
        for i in range(5):
            y = 6 + (hgt - mb - 6) * i / 4
            cv.create_text(ml - 4, y, text=f"{hi - (hi - lo) * i / 4:.0f}", anchor="e", fill=SUTIL, font=(MONO, 7))
        n = len(vals)
        for c, (k, color) in enumerate(series):
            pts = []
            for i, v in enumerate(vals[:, c]):
                pts += [ml + (w - 4 - ml) * i / (n - 1), 6 + (hgt - mb - 6) * (1 - (v - lo) / (hi - lo))]
            if c == 1:
                cv.create_polygon([ml, hgt - mb] + pts + [w - 4, hgt - mb], fill=TM.mezcla(color, TARJETA, 0.8),
                                  outline="")
            cv.create_line(*pts, fill=color, width=2 if c == 1 else 1)
        g0 = hist[-200:][0]["gen"]
        cv.create_text(ml, hgt - 4, text=str(g0), anchor="sw", fill=SUTIL, font=(MONO, 7))
        cv.create_text(w - 4, hgt - 4, text=str(hist[-1]["gen"]), anchor="se", fill=SUTIL, font=(MONO, 7))
        x = ml + 60
        for k, color in series:
            nombre = {"max": "mejor", "centro": "IA", "media": "media"}[k]
            cv.create_rectangle(x, hgt - 12, x + 8, hgt - 4, fill=color, outline="")
            cv.create_text(x + 12, hgt - 8, text=nombre, anchor="w", fill=TENUE, font=(FAMILIA, 8))
            x += 70

    def _barras(self):
        cv = self.barras
        cv.delete("all")
        if not self.ia or self.modo != "ia" or self.paso_ia["probs"] is None:
            cv.create_text(int(cv.cget("width")) // 2, 60, text="Mira a la IA para ver qué botón quiere apretar", fill=SUTIL,
                           font=(FAMILIA, 9))
            return
        probs = self.paso_ia["probs"]
        n = len(probs)
        ancho = int(cv.cget("width")) / n
        elegido = int(np.argmax(probs))
        for i, p in enumerate(probs):
            x0 = i * ancho + 2
            alto = 86 * float(p)
            color = ORO if i == elegido else TM.mezcla(AZUL, TARJETA, 0.35)
            cv.create_rectangle(x0, 92 - alto, x0 + ancho - 4, 92, fill=color, outline="")
            cv.create_text(x0 + (ancho - 4) / 2, 106, text=INS.nombre_accion(self.ia.acciones[i]), fill=TENUE,
                           font=(FAMILIA, 7))

    def cerrar(self):
        self.pantalla.itemconfigure(self.txt_pantalla, text="Guardando…", state="normal")
        self.raiz.update()
        try:
            self.grabar.cerrar()
        except Exception:
            pass
        if self.ent:
            self._enviar_demos(esperar=True)
            if self.jugador:
                self.jugador.gb.guardar_bateria()
            self.ent.cerrar()
        self.altavoz.cerrar()
        self.raiz.destroy()

    def ejecutar(self):
        self.raiz.mainloop()
