import argparse
import math
import threading
import time
import tkinter as tk
from collections import deque

import numpy as np
import cv2

from detector import Detector, VERDE, AMARILLO, ROJO, W, H, FX, CX0, CY0, QUIETO

try:
    import winsound
except ImportError:
    winsound = None

FONDO = "#12141a"
TARJETA = "#1c1f28"
TARJETA2 = "#252a36"
BORDE = "#343a4a"
TEXTO = "#e6e9f0"
TENUE = "#8a92a6"
ACENTO = "#50beff"
NOCHE = "#7dff9a"
COLOR = {VERDE: "#22b35e", AMARILLO: "#f2c230", ROJO: "#e5413b"}
APAGADO = {VERDE: "#173826", AMARILLO: "#3d3417", ROJO: "#3d1a19"}
BGR = {VERDE: (94, 179, 34), AMARILLO: (48, 194, 242), ROJO: (59, 65, 229)}
ESTADO = {VERDE: "SEGURO", AMARILLO: "PRECAUCIÓN", ROJO: "¡PELIGRO!"}
DETALLE = {VERDE: "No hay nada cerca", AMARILLO: "Algo se está acercando", ROJO: "¡Objeto demasiado cerca!"}
LED = {VERDE: "verde", AMARILLO: "amarillo", ROJO: "rojo"}
MODOS = [("auto", "Automático"), ("color", "Luz ambiente"), ("ir", "Infrarrojo")]
PW, PH = 480, 360
MAX_D = 5.0
HIST_S = 20.0
MAX_V = 3.0
OSCURO, CLARO = 28.0, 40.0
T_OSCURO, T_SONDEO, DUR_SONDEO = 1.5, 10.0, 0.9


def flecha(p):
    if not p.v_valida or p.rapidez < QUIETO:
        return "•"
    ang = math.degrees(math.atan2(float(p.v[0]), float(p.v[1])))
    return "↑↗→↘↓↙←↖"[int(((ang + 22.5) % 360) // 45)]


def ir_a_bgr(ir):
    v = ir[:480].astype(np.float32)
    hi = float(np.percentile(v[::4, ::4], 99.5)) + 1.0
    g = (np.clip(v / hi, 0, 1) ** 0.55 * 255).astype(np.uint8)
    g = cv2.GaussianBlur(g, (0, 0), 1.6)
    g = cv2.equalizeHist(g)
    return np.dstack([(g * 0.45).astype(np.uint8), g, (g * 0.5).astype(np.uint8)])


class FuenteKinect:
    nombre = "Kinect"

    def __init__(self):
        from kinect import Kinect, crudo_a_metros
        self._metros = crudo_a_metros
        self.k = Kinect()
        try:
            self.k.abrir()
            self.k.iniciar()
        except Exception:
            self.k.cerrar()
            raise
        self.angulo = 0
        est = self.k.estado_motor()
        if est and est["angulo"] is not None:
            self.angulo = int(round(est["angulo"]))

    def leer(self):
        p = self.k.profundidad()
        m = None if p is None else np.ascontiguousarray(self._metros(p[::2, ::2])[:, ::-1])
        if self.k.video_ir:
            ir = self.k.infrarrojo()
            img = None if ir is None else np.ascontiguousarray(ir_a_bgr(ir)[:, ::-1])
            return m, img, "ir"
        c = self.k.color()
        img = None if c is None else np.ascontiguousarray(cv2.cvtColor(c, cv2.COLOR_BayerGB2BGR)[:, ::-1])
        return m, img, "color"

    def modo_video(self, ir):
        try:
            self.k.modo_video(ir)
        except Exception as e:
            print("No se pudo cambiar el modo de video:", e)

    def led(self, nombre):
        self.k.led(nombre)

    def inclinar(self, d):
        self.angulo = max(-27, min(27, self.angulo + d))
        self.k.inclinar(self.angulo)

    def cerrar(self):
        self.k.cerrar()


class FuenteSimulada:
    nombre = "Simulado (sin Kinect)"

    def __init__(self):
        self.t0 = time.time()
        self.t_ult = 0.0
        self.ir = False
        self.V, self.U = np.mgrid[0:H, 0:W].astype(np.float32)
        self.rng = np.random.default_rng(1)
        m = np.full((H, W), 4.8, np.float32)
        zf = 1.0 * FX / np.maximum(self.V - CY0, 1e-3)
        self.piso = (self.V > CY0 + 1) & (zf < 4.8)
        m[self.piso] = zf[self.piso]
        self.cuarto = m

    def modo_video(self, ir):
        self.ir = bool(ir)

    def fondo_vacio(self):
        return self.cuarto.copy()

    def luz(self, t):
        return 1.0 if (t % 40) < 24 else 0.06

    def objetos(self, t):
        tri = lambda T: 1 - abs((t % T) / T * 2 - 1)
        return [
            (-0.65 + 1.3 * tri(9), 1.5, 0.45, 1.7, (80, 140, 230)),
            (1.2 - 2.4 * tri(9), 3.0, 0.45, 1.75, (90, 200, 120)),
            (-0.45, 2.6 - 0.9 * tri(11), 0.4, 0.4, (40, 90, 200)),
        ]

    def leer(self):
        t = time.time() - self.t0
        if t - self.t_ult < 1 / 30:
            return None, None, "ir" if self.ir else "color"
        self.t_ult = t
        m = self.cuarto.copy()
        quien = np.full((H, W), -1, np.int8)
        objs = self.objetos(t)
        for k, (x, z, w, h, _) in enumerate(objs):
            u0, u1 = CX0 + FX * (x - w / 2) / z, CX0 + FX * (x + w / 2) / z
            v0, v1 = CY0 + FX * (1.0 - h) / z, CY0 + FX * 1.0 / z
            r = (self.U >= u0) & (self.U <= u1) & (self.V >= v0) & (self.V <= v1)
            zz = z + 0.08 * ((self.U - (u0 + u1) / 2) / max(1.0, (u1 - u0) / 2)) ** 2
            cerca = r & (zz < m)
            m[cerca] = zz[cerca]
            quien[cerca] = k
        m += (self.rng.normal(0, 0.004, m.shape) * m).astype(np.float32)
        m[self.rng.random(m.shape) < 0.01] = 0
        if self.ir:
            v = np.clip(1.6 / np.maximum(m, 0.5) ** 2, 0, 1) * (0.6 + 0.8 * (self.rng.random(m.shape) < 0.25))
            g = cv2.resize((np.clip(v, 0, 1) * 255).astype(np.uint8), (640, 480))
            img = ir_a_bgr(g.astype(np.uint16) * 4)
        else:
            img = np.zeros((H, W, 3), np.float32)
            img[:] = (150, 160, 170)
            img[self.piso] = (60, 90, 120)
            for k, o in enumerate(objs):
                img[quien == k] = o[4]
            img *= self.luz(t)
            img += self.rng.normal(0, 4, img.shape)
            img = cv2.resize(np.clip(img, 0, 255).astype(np.uint8), (640, 480))
        return m, img, "ir" if self.ir else "color"

    def led(self, nombre):
        pass

    def inclinar(self, d):
        pass

    def cerrar(self):
        pass


def hex_bgr(h):
    return np.array([int(h[5:7], 16), int(h[3:5], 16), int(h[1:3], 16)], np.float32)


def a_foto(bgr):
    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    datos = b"P6 %d %d 255\n" % (rgb.shape[1], rgb.shape[0]) + rgb.tobytes()
    return tk.PhotoImage(data=datos, format="PPM")


class App:
    def __init__(self, fuente, aviso=""):
        self.fuente = fuente
        self.det = Detector()
        self.raiz = tk.Tk()
        self.raiz.title("Kinect Distancia — semáforo de proximidad")
        self.raiz.configure(bg=FONDO)
        self.raiz.resizable(False, False)
        self.m = None
        self.img = None
        self.tipo = "color"
        self.res = None
        self.fotos = [None, None]
        self.historial = deque()
        self.ver_vel = False
        self.nivel_led = None
        self.cuadros = 0
        self.fps = 0.0
        self.t_fps = time.time()
        self.t_dato = 0.0
        self.arrastre = None
        self.raton = None
        self.vivo = True
        self.sonido_on = True
        self.dist_audio = None
        self.nivel_audio = VERDE
        self.modo = "auto"
        self.video_ir = False
        self.brillo = None
        self.t_oscuro = None
        self.t_ir = 0.0
        self.sondeo = None
        self.det.ignorar_fondo = True
        if hasattr(fuente, "fondo_vacio"):
            self.det.fondo = fuente.fondo_vacio()
        self._construir()
        self._teclas()
        self.poner_modo("auto")
        if aviso:
            self.estado_txt.set(aviso)
        threading.Thread(target=self._sonar, daemon=True).start()
        self.raiz.protocol("WM_DELETE_WINDOW", self.cerrar)
        self.raiz.after(10, self.ciclo)

    def _boton(self, padre, txt, cmd, **kw):
        return tk.Button(padre, text=txt, command=cmd, bg=TARJETA2, fg=TEXTO, activebackground=BORDE,
                         activeforeground=TEXTO, relief="flat", bd=0, padx=12, pady=5,
                         font=("Segoe UI", 9, "bold"), cursor="hand2", **kw)

    def _pantalla(self, padre, col):
        marco = tk.Frame(padre, bg=TARJETA, padx=8, pady=8)
        marco.grid(row=0, column=col, padx=(0, 12) if col == 0 else 0, sticky="n")
        titulo = tk.StringVar()
        tk.Label(marco, textvariable=titulo, bg=TARJETA, fg=TEXTO, font=("Segoe UI", 11, "bold"), anchor="w").pack(fill="x")
        sub = tk.StringVar()
        tk.Label(marco, textvariable=sub, bg=TARJETA, fg=TENUE, font=("Segoe UI", 9), anchor="w").pack(fill="x", pady=(0, 6))
        c = tk.Canvas(marco, width=PW, height=PH, bg="#000000", highlightthickness=3, highlightbackground=BORDE)
        c.pack()
        img_id = c.create_image(0, 0, anchor="nw")
        c.bind("<ButtonPress-1>", self._ini_zona)
        c.bind("<B1-Motion>", self._mover_zona)
        c.bind("<ButtonRelease-1>", self._fin_zona)
        c.bind("<Button-3>", lambda e: self.borrar_zona())
        c.bind("<Motion>", lambda e, c=c: setattr(self, "raton", (c, e.x, e.y)))
        c.bind("<Leave>", lambda e: setattr(self, "raton", None))
        pie = tk.Frame(marco, bg=TARJETA)
        pie.pack(fill="x", pady=(8, 0))
        return c, img_id, titulo, sub, pie

    def _construir(self):
        r = self.raiz
        cab = tk.Frame(r, bg=FONDO)
        cab.pack(fill="x", padx=16, pady=(12, 8))
        tk.Label(cab, text="Kinect Distancia", bg=FONDO, fg=TEXTO, font=("Segoe UI", 18, "bold")).pack(side="left")
        tk.Label(cab, text="  doble pantalla: luz ambiente e infrarrojo · avisa cuando algo se acerca", bg=FONDO,
                 fg=TENUE, font=("Segoe UI", 11)).pack(side="left", pady=(6, 0))
        self.lbl_fuente = tk.Label(cab, text="", bg=FONDO, fg=TENUE, font=("Segoe UI", 10))
        self.lbl_fuente.pack(side="right")
        cuerpo = tk.Frame(r, bg=FONDO)
        cuerpo.pack(padx=16, pady=(0, 14))
        izq = tk.Frame(cuerpo, bg=FONDO)
        izq.pack(side="left", anchor="n")
        fila = tk.Frame(izq, bg=FONDO)
        fila.pack()
        self.c1, self.i1, self.t1, self.s1, pie1 = self._pantalla(fila, 0)
        self.c2, self.i2, self.t2, self.s2, pie2 = self._pantalla(fila, 1)
        tk.Label(pie1, text="Imagen:", bg=TARJETA, fg=TENUE, font=("Segoe UI", 9)).pack(side="left", padx=(0, 6))
        self.botones_modo = {}
        for clave, txt in MODOS:
            b = self._boton(pie1, txt, lambda c=clave: self.poner_modo(c))
            b.pack(side="left", padx=(0, 6))
            self.botones_modo[clave] = b
        self.t2.set("PANTALLA 2 · INFRARROJO DE PROFUNDIDAD")
        self.s2.set("El Kinect proyecta luz infrarroja: mide igual con luz o a oscuras")
        tk.Label(pie2, text="Arrastra sobre cualquier pantalla para vigilar una zona · clic derecho la borra",
                 bg=TARJETA, fg=TENUE, font=("Segoe UI", 9)).pack(side="left")
        abajo = tk.Frame(izq, bg=FONDO)
        abajo.pack(fill="x", pady=(12, 0))
        self.radar = tk.Canvas(abajo, width=330, height=202, bg=TARJETA, highlightthickness=0)
        self.radar.pack(side="left")
        self.lista = tk.Canvas(abajo, width=300, height=202, bg=TARJETA, highlightthickness=0)
        self.lista.pack(side="left", padx=12)
        self.grafica = tk.Canvas(abajo, width=340, height=202, bg=TARJETA, highlightthickness=0)
        self.grafica.pack(side="left")
        self.grafica.bind("<Button-1>", lambda e: setattr(self, "ver_vel", not self.ver_vel))
        self.grafica.configure(cursor="hand2")
        der = tk.Frame(cuerpo, bg=FONDO)
        der.pack(side="left", anchor="n", padx=(14, 0))
        self.alerta = tk.Frame(der, bg=COLOR[VERDE], width=430, height=196)
        self.alerta.pack(fill="x")
        self.alerta.pack_propagate(False)
        self.lbl_estado = tk.Label(self.alerta, text=ESTADO[VERDE], bg=COLOR[VERDE], fg="#ffffff", font=("Segoe UI", 24, "bold"))
        self.lbl_estado.pack(pady=(8, 0))
        self.lbl_dist = tk.Label(self.alerta, text="—", bg=COLOR[VERDE], fg="#ffffff", font=("Segoe UI", 44, "bold"))
        self.lbl_dist.pack()
        self.lbl_vel = tk.Label(self.alerta, text="", bg=COLOR[VERDE], fg="#ffffff", font=("Segoe UI", 12, "bold"))
        self.lbl_vel.pack()
        self.lbl_det = tk.Label(self.alerta, text=DETALLE[VERDE], bg=COLOR[VERDE], fg="#ffffff", font=("Segoe UI", 10))
        self.lbl_det.pack()
        self.semaforo = tk.Canvas(der, width=430, height=78, bg=TARJETA, highlightthickness=0)
        self.semaforo.pack(fill="x", pady=(12, 0))
        self.luces = {}
        for i, n in enumerate((VERDE, AMARILLO, ROJO)):
            x = 85 + i * 130
            self.luces[n] = self.semaforo.create_oval(x - 28, 11, x + 28, 67, fill=APAGADO[n], outline="")
        ctl = tk.Frame(der, bg=TARJETA, padx=14, pady=10)
        ctl.pack(fill="x", pady=(12, 0))
        self.v_amar = tk.DoubleVar(value=self.det.amarillo)
        self.v_rojo = tk.DoubleVar(value=self.det.rojo)
        self.v_alc = tk.DoubleVar(value=self.det.alcance)
        for txt, var, lo, hi, col in (("Amarillo a menos de (m)", self.v_amar, 0.6, 4.5, COLOR[AMARILLO]),
                                      ("Rojo a menos de (m)", self.v_rojo, 0.4, 3.5, COLOR[ROJO]),
                                      ("Vigilar hasta (m)", self.v_alc, 1.5, 5.0, TEXTO)):
            f = tk.Frame(ctl, bg=TARJETA)
            f.pack(fill="x")
            tk.Label(f, text=txt, bg=TARJETA, fg=col, font=("Segoe UI", 10, "bold"), width=20, anchor="w").pack(side="left")
            tk.Scale(f, variable=var, from_=lo, to=hi, resolution=0.05, orient="horizontal", length=200,
                     bg=TARJETA, fg=TEXTO, troughcolor=TARJETA2, highlightthickness=0, bd=0,
                     command=lambda _=None: self._umbrales()).pack(side="left")
        opc = tk.Frame(ctl, bg=TARJETA)
        opc.pack(fill="x", pady=(6, 0))
        self.v_sonido = tk.BooleanVar(value=True)
        self.v_led = tk.BooleanVar(value=True)
        self.v_fondo = tk.BooleanVar(value=True)
        for txt, var in (("Pitido tipo sensor de reversa", self.v_sonido), ("LED del Kinect con el color de la alerta", self.v_led),
                         ("Sólo lo nuevo o lo que se mueve (ignora muebles)", self.v_fondo)):
            tk.Checkbutton(opc, text=txt, variable=var, bg=TARJETA, fg=TEXTO, selectcolor=TARJETA2,
                           activebackground=TARJETA, activeforeground=TEXTO, font=("Segoe UI", 10),
                           command=self._opciones).pack(anchor="w")
        bots = tk.Frame(ctl, bg=TARJETA)
        bots.pack(fill="x", pady=(8, 0))
        self._boton(bots, "Volver a aprender el fondo", self.reaprender).pack(side="left", padx=(0, 8))
        self._boton(bots, "Borrar zona", self.borrar_zona).pack(side="left", padx=(0, 8))
        self._boton(bots, "Reiniciar IDs", self.det.reiniciar_ids).pack(side="left")
        tk.Label(der, text="Teclas: ↑/↓ inclinar Kinect · S sonido · Esc salir", bg=FONDO, fg=TENUE,
                 font=("Segoe UI", 9)).pack(anchor="w", pady=(10, 0))
        self.estado_txt = tk.StringVar(value="")
        tk.Label(der, textvariable=self.estado_txt, bg=FONDO, fg=TENUE, font=("Segoe UI", 9), anchor="w",
                 justify="left", wraplength=430).pack(fill="x", pady=(4, 0))

    def _teclas(self):
        r = self.raiz
        r.bind("<Escape>", lambda e: self.cerrar())
        r.bind("<Up>", lambda e: self.fuente.inclinar(3))
        r.bind("<Down>", lambda e: self.fuente.inclinar(-3))
        r.bind("<s>", lambda e: (self.v_sonido.set(not self.v_sonido.get()), self._opciones()))

    def poner_modo(self, clave):
        self.modo = clave
        for c, b in self.botones_modo.items():
            act = c == clave
            b.configure(bg=ACENTO if act else TARJETA2, fg="#0b0d12" if act else TEXTO,
                        activebackground=ACENTO if act else BORDE)
        self.sondeo = None
        if clave == "color":
            self._video(False)
        elif clave == "ir":
            self._video(True)
        else:
            self.t_oscuro = None

    def _video(self, ir):
        if ir != self.video_ir:
            self.video_ir = ir
            self.fuente.modo_video(ir)
            if ir:
                self.t_ir = time.time()

    def _automatico(self, ahora):
        if self.modo != "auto":
            return
        if self.sondeo is not None:
            if ahora - self.sondeo >= DUR_SONDEO and self.tipo == "color" and self.brillo is not None:
                self.sondeo = None
                if self.brillo < CLARO:
                    self._video(True)
                else:
                    self.t_oscuro = None
            elif ahora - self.sondeo > DUR_SONDEO * 3:
                self.sondeo = None
                self._video(True)
            return
        if not self.video_ir:
            if self.brillo is not None and self.brillo < OSCURO:
                self.t_oscuro = self.t_oscuro or ahora
                if ahora - self.t_oscuro >= T_OSCURO:
                    self._video(True)
            else:
                self.t_oscuro = None
        elif ahora - self.t_ir >= T_SONDEO:
            self.sondeo = ahora
            self.brillo = None
            self._video(False)

    def _umbrales(self):
        rojo = self.v_rojo.get()
        amar = self.v_amar.get()
        if amar < rojo + 0.1:
            amar = rojo + 0.1
            self.v_amar.set(round(amar, 2))
        self.det.rojo, self.det.amarillo = rojo, amar
        self.det.alcance = self.v_alc.get()

    def _opciones(self):
        self.sonido_on = self.v_sonido.get()
        ig = self.v_fondo.get()
        if ig != self.det.ignorar_fondo:
            self.det.ignorar_fondo = ig
            self.det.aprender_fondo()
        if not self.v_led.get():
            self.fuente.led("apagado")
            self.nivel_led = None

    def reaprender(self):
        self.det.aprender_fondo()
        self.det.base_inv = None
        if not self.v_fondo.get():
            self.v_fondo.set(True)
            self.det.ignorar_fondo = True
        self.estado_txt.set("Fondo aprendido: lo que estaba en la imagen se ignora; sólo avisa de lo que se acerque o aparezca.")

    def borrar_zona(self):
        self.det.zona = None
        self.det.base_inv = None

    def _ini_zona(self, e):
        self.arrastre = (e.widget, e.x, e.y, e.x, e.y)

    def _mover_zona(self, e):
        if self.arrastre:
            self.arrastre = (self.arrastre[0], self.arrastre[1], self.arrastre[2], e.x, e.y)

    def _fin_zona(self, e):
        if self.arrastre:
            _, x0, y0, x1, y1 = self.arrastre
            self.det.poner_zona(x0 / PW, y0 / PH, x1 / PW, y1 / PH)
            self.det.base_inv = None
            self.arrastre = None

    def _sonar(self):
        while self.vivo:
            d, n = self.dist_audio, self.nivel_audio
            if winsound is None or not self.sonido_on or d is None or n == VERDE:
                time.sleep(0.08)
                continue
            if n == AMARILLO:
                frac = max(0.0, min(1.0, (d - self.det.rojo) / max(0.1, self.det.amarillo - self.det.rojo)))
                winsound.Beep(950, 80)
                time.sleep(0.15 + 0.6 * frac)
            else:
                frac = max(0.0, min(1.0, d / max(0.1, self.det.rojo)))
                winsound.Beep(1600, 110)
                time.sleep(0.02 + 0.16 * frac)

    def imagen_profundidad(self):
        m = self.m
        v = np.clip((4.5 - m) / 4.0, 0, 1)
        img = cv2.applyColorMap((v * 255).astype(np.uint8), cv2.COLORMAP_BONE)
        img[m <= 0.3] = (0, 0, 0)
        img = (img * 0.8).astype(np.uint8)
        res = self.res
        if res is not None:
            if res.piso is not None:
                img[res.piso] = (img[res.piso] * 0.5 + np.array((60, 45, 30)) * 0.5).astype(np.uint8)
            for p in res.pistas:
                if p.perdido or p.mascara is None:
                    continue
                c = hex_bgr(p.color())
                img[p.mascara] = (img[p.mascara] * 0.3 + c * 0.7).astype(np.uint8)
        return cv2.resize(img, (PW, PH), interpolation=cv2.INTER_NEAREST)

    def caja_de(self, p):
        if not p.perdido and p.caja is not None:
            return p.caja[0] * PW, p.caja[1] * PH, p.caja[2] * PW, p.caja[3] * PH
        x, y, z = (float(v) for v in p.pos)
        z = max(0.4, z)
        u0, u1 = CX0 + FX * (x - p.ancho / 2) / z, CX0 + FX * (x + p.ancho / 2) / z
        v0, v1 = CY0 + FX * (y - p.alto / 2) / z, CY0 + FX * (y + p.alto / 2) / z
        return u0 * PW / W, v0 * PH / H, u1 * PW / W, v1 * PH / H

    def capa(self, c, profundidad):
        c.delete("capa")
        res = self.res
        z = self.det.zona
        if z is not None:
            c.create_rectangle(z[0] * PW, z[1] * PH, z[2] * PW, z[3] * PH, outline="#ffffff", dash=(6, 4), width=2, tags="capa")
            c.create_text(z[0] * PW + 6, z[1] * PH + 4, text="zona vigilada", anchor="nw", fill="#ffffff",
                          font=("Segoe UI", 9, "bold"), tags="capa")
        if self.arrastre:
            _, x0, y0, x1, y1 = self.arrastre
            c.create_rectangle(x0, y0, x1, y1, outline=ACENTO, dash=(4, 3), width=2, tags="capa")
        if res is not None and not res.muy_cerca:
            for p in sorted(res.pistas, key=lambda q: -q.dist):
                x0, y0, x1, y1 = self.caja_de(p)
                cid = p.color()
                if p.perdido:
                    c.create_rectangle(x0, y0, x1, y1, outline=cid, width=2, dash=(5, 4), tags="capa")
                    c.create_text((x0 + x1) / 2, (y0 + y1) / 2, text=f"ID {p.id}\ntapado", fill=cid, justify="center",
                                  font=("Segoe UI", 10, "bold"), tags="capa")
                    continue
                col = COLOR[p.nivel]
                c.create_rectangle(x0, y0, x1, y1, outline=col, width=3, tags="capa")
                c.create_rectangle(x0 + 3, y0 + 3, x1 - 3, y1 - 3, outline=cid, width=1, tags="capa")
                ty = y0 - 13 if y0 > 28 else (y1 + 13 if y1 < PH - 28 else y0 + 16)
                cx = min(PW - 62, max(62, (x0 + x1) / 2))
                c.create_rectangle(cx - 60, ty - 12, cx - 22, ty + 12, fill=cid, outline="", tags="capa")
                c.create_text(cx - 41, ty, text=f"{p.id}", fill="#0b0d12", font=("Segoe UI", 11, "bold"), tags="capa")
                c.create_rectangle(cx - 22, ty - 12, cx + 60, ty + 12, fill=col, outline="", tags="capa")
                c.create_text(cx + 19, ty, text=f"{p.dist:.2f} m", fill="#0b0d12" if p.nivel == AMARILLO else "#ffffff",
                              font=("Segoe UI", 11, "bold"), tags="capa")
                vy = ty + 21 if ty < y1 - 30 else ty - 21
                if not p.v_valida:
                    vt = "…"
                elif p.rapidez < QUIETO:
                    vt = "quieto"
                else:
                    vt = f"{flecha(p)} {p.rapidez:.1f} m/s"
                c.create_rectangle(cx - 60, vy - 9, cx + 60, vy + 9, fill="#0b0d12", outline=cid, tags="capa")
                c.create_text(cx, vy, text=vt, fill=cid, font=("Segoe UI", 10, "bold"), tags="capa")
        if res is not None and res.muy_cerca:
            c.create_text(PW / 2, PH / 2, text="¡DEMASIADO CERCA!", fill=COLOR[ROJO], font=("Segoe UI", 22, "bold"), tags="capa")
        if self.raton and self.raton[0] is c and self.m is not None:
            _, x, y = self.raton
            px, py = min(W - 1, int(x * W / PW)), min(H - 1, int(y * H / PH))
            d = float(self.m[py, px])
            c.create_line(x - 10, y, x + 10, y, fill="#ffffff", tags="capa")
            c.create_line(x, y - 10, x, y + 10, fill="#ffffff", tags="capa")
            c.create_text(x + 12, y + 12, anchor="nw", text=f"{d:.2f} m" if d > 0.3 else "sin dato", fill="#ffffff",
                          font=("Segoe UI", 10, "bold"), tags="capa")
        if not profundidad and self.sondeo is not None:
            c.create_text(PW / 2, PH - 18, text="comprobando si ya hay luz…", fill="#ffffff", font=("Segoe UI", 10, "bold"), tags="capa")

    def titulos(self):
        if self.tipo == "ir":
            self.t1.set("PANTALLA 1 · INFRARROJO (visión nocturna)")
            self.s1.set("Cámara infrarroja del Kinect: ve aunque todo esté oscuro")
        else:
            b = "—" if self.brillo is None else f"{self.brillo / 2.55:.0f}%"
            self.t1.set("PANTALLA 1 · LUZ AMBIENTE (cámara de color)")
            self.s1.set(f"Luz del cuarto: {b}" + ("  ·  pasa a infrarrojo si oscurece" if self.modo == "auto" else ""))
        vivo = time.time() - self.t_dato < 1.0
        self.lbl_fuente.configure(text=f"{'●' if vivo else '○'} {self.fuente.nombre} · {self.fps:.0f} fps",
                                  fg=COLOR[VERDE] if vivo else COLOR[ROJO])

    def tablero(self):
        res = self.res
        n = res.nivel if res else VERDE
        d = res.distancia if res else None
        col = COLOR[n]
        if n == ROJO and int(time.time() * 4) % 2:
            col = "#9e1f1b"
        fg = "#15120a" if n == AMARILLO else "#ffffff"
        for w in (self.alerta, self.lbl_estado, self.lbl_dist, self.lbl_vel, self.lbl_det):
            w.configure(bg=col)
        for w in (self.lbl_estado, self.lbl_dist, self.lbl_vel, self.lbl_det):
            w.configure(fg=fg)
        visibles = [p for p in res.pistas if not p.perdido] if res else []
        cuantos = f"{len(visibles)} objeto{'s' if len(visibles) != 1 else ''} a la vista"
        if res is not None and res.muy_cerca:
            self.lbl_estado.configure(text=ESTADO[ROJO])
            self.lbl_dist.configure(text="< 0.5 m")
            self.lbl_vel.configure(text="")
            self.lbl_det.configure(text="Algo tapa al sensor")
        elif res is not None and res.cercana is not None:
            self.lbl_estado.configure(text=f"{ESTADO[n]}  ·  ID {res.cercana.id}")
            self.lbl_dist.configure(text=f"{d:.2f} m")
            q = res.cercana
            if not q.v_valida:
                vtxt = "midiendo velocidad…"
            elif q.rapidez < QUIETO:
                vtxt = "quieto"
            else:
                ll = q.llegada()
                rumbo = "se acerca" if q.v_radial < -0.15 else ("se aleja" if q.v_radial > 0.15 else "se mueve de lado")
                vtxt = f"{rumbo} a {q.rapidez:.2f} m/s ({q.rapidez * 3.6:.1f} km/h)" + (f" · llega en {ll:.1f} s" if ll else "")
            self.lbl_vel.configure(text=vtxt)
            self.lbl_det.configure(text=f"El más cercano es el ID {q.id}  ·  {cuantos}")
        else:
            self.lbl_estado.configure(text=ESTADO[VERDE])
            self.lbl_dist.configure(text="—")
            self.lbl_vel.configure(text="")
            self.lbl_det.configure(text="Nada detectado en la zona")
        borde = COLOR[n] if n != VERDE else BORDE
        self.c1.configure(highlightbackground=borde)
        self.c2.configure(highlightbackground=borde)
        for k, oid in self.luces.items():
            self.semaforo.itemconfigure(oid, fill=COLOR[k] if k == n else APAGADO[k])
        self._radar()
        self._lista()
        self._grafica()

    def _radar(self):
        c = self.radar
        c.delete("all")
        w, h = int(c["width"]), int(c["height"])
        ox, oy = w / 2, h - 16
        esc = (h - 40) / MAX_D
        c.create_text(10, 10, text="Vista desde arriba", anchor="w", fill=TENUE, font=("Segoe UI", 9))
        medio = math.radians(29)
        for r_m, col in ((MAX_D, APAGADO[VERDE]), (self.det.amarillo, APAGADO[AMARILLO]), (self.det.rojo, APAGADO[ROJO])):
            r = r_m * esc
            c.create_arc(ox - r, oy - r, ox + r, oy + r, start=90 - 29, extent=58, fill=col, outline="")
        for k in range(1, int(MAX_D) + 1):
            r = k * esc
            c.create_arc(ox - r, oy - r, ox + r, oy + r, start=90 - 29, extent=58, style="arc", outline=BORDE)
            c.create_text(ox + math.sin(medio) * r + 4, oy - math.cos(medio) * r, text=f"{k} m", anchor="w", fill=TENUE, font=("Segoe UI", 7))
        c.create_polygon(ox - 10, oy + 8, ox + 10, oy + 8, ox, oy - 4, fill=ACENTO, outline="")
        res = self.res
        if res is None:
            return
        for p in res.pistas:
            col = p.color()
            pts = []
            for x, z in p.rastro:
                pts += [ox + x * esc, oy - z * esc]
            if len(pts) >= 4:
                c.create_line(*pts, fill=col, width=2, smooth=True)
            x, z = float(p.pos[0]), float(p.pos[2])
            px, py = ox + x * esc, oy - z * esc
            r = 7
            if p.v_valida and p.rapidez >= QUIETO and not p.perdido:
                c.create_line(px, py, px + float(p.v[0]) * esc, py - float(p.v[1]) * esc, fill=col, width=3, arrow="last",
                              arrowshape=(9, 11, 4))
            if p.perdido:
                c.create_oval(px - r, py - r, px + r, py + r, outline=col, width=2, dash=(3, 2))
            else:
                c.create_oval(px - r, py - r, px + r, py + r, fill=col, outline="#ffffff")
            c.create_text(px, py - 14, text=str(p.id), fill=col, font=("Segoe UI", 9, "bold"))

    def _lista(self):
        c = self.lista
        c.delete("all")
        c.create_text(12, 10, text="Objetos detectados", anchor="w", fill=TENUE, font=("Segoe UI", 9))
        res = self.res
        filas = sorted(res.pistas, key=lambda p: (p.perdido, p.dist)) if res else []
        if not filas:
            c.create_text(150, 100, text="Nada en la zona vigilada", fill=TENUE, font=("Segoe UI", 10))
            return
        for i, p in enumerate(filas[:7]):
            y = 34 + i * 24
            c.create_rectangle(12, y - 10, 46, y + 10, fill=p.color(), outline="")
            c.create_text(29, y, text=str(p.id), fill="#0b0d12", font=("Segoe UI", 10, "bold"))
            if p.perdido:
                c.create_text(58, y, text="tapado / fuera de vista", anchor="w", fill=TENUE, font=("Segoe UI", 10))
                continue
            c.create_oval(58, y - 6, 70, y + 6, fill=COLOR[p.nivel], outline="")
            c.create_text(78, y, text=f"{p.dist:.2f} m", anchor="w", fill=TEXTO, font=("Segoe UI", 11, "bold"))
            if not p.v_valida:
                mov, mc, vt = "midiendo…", TENUE, ""
            elif p.rapidez < QUIETO:
                mov, mc, vt = "quieto", TENUE, ""
            else:
                vt = f"{p.rapidez:.2f} m/s"
                if p.v_radial < -0.15:
                    mov, mc = f"{flecha(p)} se acerca", COLOR[AMARILLO]
                elif p.v_radial > 0.15:
                    mov, mc = f"{flecha(p)} se aleja", TENUE
                else:
                    mov, mc = f"{flecha(p)} de lado", TENUE
            c.create_text(140, y, text=mov, anchor="w", fill=mc, font=("Segoe UI", 9))
            c.create_text(290, y - 4, text=vt, anchor="e", fill=TEXTO, font=("Segoe UI", 10, "bold"))
            c.create_text(290, y + 8, text=f"máx {p.v_max:.1f} m/s" if p.v_max >= QUIETO else "", anchor="e", fill=TENUE,
                          font=("Segoe UI", 7))
        if len(filas) > 7:
            c.create_text(150, 195, text=f"+{len(filas) - 7} más", fill=TENUE, font=("Segoe UI", 8))

    def _grafica(self):
        c = self.grafica
        c.delete("all")
        x0, x1, y0, y1 = 32, int(c["width"]) - 10, 26, int(c["height"]) - 14
        c.create_text(x1, 10, text="clic: ver " + ("distancia" if self.ver_vel else "velocidad"), anchor="e", fill=ACENTO,
                      font=("Segoe UI", 8))
        if self.ver_vel:
            self._grafica_vel(c, x0, x1, y0, y1)
            return
        c.create_text(12, 10, text=f"Distancia de cada ID (últimos {HIST_S:.0f} s)", anchor="w", fill=TENUE, font=("Segoe UI", 9))
        ym = lambda v: y1 - (y1 - y0) * min(MAX_D, max(0.0, v)) / MAX_D
        c.create_rectangle(x0, ym(self.det.rojo), x1, y1, fill=APAGADO[ROJO], outline="")
        c.create_rectangle(x0, ym(self.det.amarillo), x1, ym(self.det.rojo), fill=APAGADO[AMARILLO], outline="")
        c.create_rectangle(x0, y0, x1, ym(self.det.amarillo), fill=APAGADO[VERDE], outline="")
        for v in range(0, int(MAX_D) + 1):
            c.create_text(x0 - 6, ym(v), text=f"{v}", anchor="e", fill=TENUE, font=("Segoe UI", 8))
        res = self.res
        if res is None:
            return
        ahora = time.time()
        for p in res.pistas:
            pts = []
            for t, d, _ in p.hist:
                x = x1 - (ahora - t) / HIST_S * (x1 - x0)
                if d is None:
                    if len(pts) >= 4:
                        c.create_line(*pts, fill=p.color(), width=2)
                    pts = []
                    continue
                pts += [x, ym(d)]
            if len(pts) >= 4:
                c.create_line(*pts, fill=p.color(), width=2)

    def _grafica_vel(self, c, x0, x1, y0, y1):
        c.create_text(12, 10, text="Velocidad de cada ID (m/s)", anchor="w", fill=TENUE, font=("Segoe UI", 9))
        yv = lambda v: y1 - (y1 - y0) * min(MAX_V, max(0.0, v)) / MAX_V
        c.create_rectangle(x0, y0, x1, y1, fill=TARJETA2, outline="")
        for k in range(int(MAX_V) * 2 + 1):
            v = k / 2
            c.create_line(x0, yv(v), x1, yv(v), fill=BORDE)
            if k % 2 == 0:
                c.create_text(x0 - 6, yv(v), text=f"{v:.0f}", anchor="e", fill=TENUE, font=("Segoe UI", 8))
        res = self.res
        if res is None:
            return
        ahora = time.time()
        for p in res.pistas:
            pts = []
            for t, _, v in list(p.hist) + [(ahora, None, None)]:
                if v is None:
                    if len(pts) >= 4:
                        c.create_line(*pts, fill=p.color(), width=2)
                    pts = []
                    continue
                pts += [x1 - (ahora - t) / HIST_S * (x1 - x0), yv(v)]

    def ciclo(self):
        if not self.vivo:
            return
        ahora = time.time()
        m, img, tipo = self.fuente.leer()
        if img is not None:
            if tipo == "color":
                g = cv2.cvtColor(img[::8, ::8], cv2.COLOR_BGR2GRAY)
                b = float(g.mean())
                self.brillo = b if self.brillo is None else self.brillo + (b - self.brillo) * 0.3
            if self.sondeo is None or tipo == "ir":
                self.tipo = tipo
                self.img = img
                self.fotos[0] = a_foto(cv2.resize(img, (PW, PH), interpolation=cv2.INTER_AREA))
                self.c1.itemconfigure(self.i1, image=self.fotos[0])
        self._automatico(ahora)
        if m is not None:
            self.m = m
            self.t_dato = ahora
            self.cuadros += 1
            self.res = self.det.medir(m, ahora)
            self.dist_audio, self.nivel_audio = self.res.distancia, self.res.nivel
            if self.v_led.get() and self.res.nivel != self.nivel_led:
                self.nivel_led = self.res.nivel
                self.fuente.led(LED[self.res.nivel])
            self.fotos[1] = a_foto(self.imagen_profundidad())
            self.c2.itemconfigure(self.i2, image=self.fotos[1])
        if ahora - self.t_fps >= 1:
            self.fps = self.cuadros / (ahora - self.t_fps)
            self.cuadros = 0
            self.t_fps = ahora
        if self.m is not None:
            self.capa(self.c1, False)
            self.capa(self.c2, True)
            self.tablero()
        self.titulos()
        self.raiz.after(15, self.ciclo)

    def cerrar(self):
        if not self.vivo:
            return
        self.vivo = False
        try:
            self.fuente.cerrar()
        finally:
            self.raiz.destroy()

    def correr(self):
        self.raiz.mainloop()


def main():
    ap = argparse.ArgumentParser(description="Semáforo de proximidad con el Kinect, con luz ambiente e infrarrojo")
    ap.add_argument("--simulado", action="store_true", help="sin Kinect: una figura se acerca y se aleja y la luz se apaga cada rato")
    args = ap.parse_args()
    fuente, aviso = None, ""
    if not args.simulado:
        try:
            fuente = FuenteKinect()
        except Exception as e:
            print("Kinect no disponible:", e)
            aviso = f"Kinect no disponible ({e}). Mostrando modo simulado."
    if fuente is None:
        fuente = FuenteSimulada()
    App(fuente, aviso).correr()


if __name__ == "__main__":
    main()
