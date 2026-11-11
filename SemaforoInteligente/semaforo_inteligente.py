# -*- coding: utf-8 -*-
# Semaforo Inteligente IoT - cruce peatonal en bulevar dividido (dos calzadas + camellon).
#
# Geometria real: dos calzadas de dos carriles separadas por un camellon. El
# peaton cruza en DOS etapas usando el camellon como refugio. Hay DOS semaforos
# independientes (uno por calzada): mientras alguien cruza la calzada 1, la
# calzada 2 puede seguir en verde.
#
# Deteccion de personas con YOLOv4-tiny (OpenCV-DNN, CPU, sin torch); HOG de
# respaldo. El sistema detecta a uno o mas peatones y, por cada calzada, hace
# VERDE -> AMBAR -> ROJO y MANTIENE el rojo de esa calzada hasta que termina de
# cruzarse (nunca por un tiempo fijo), con un rojo minimo de despeje seguro.
#
# MULTICAMARA AUTOMATICO: al arrancar detecta cuantas camaras hay y se configura
#   1 camara  -> vista completa (5 zonas)
#   2 camaras -> una por calzada (lado A, lado B)
#   3 camaras -> calzada 1 | camellon | calzada 2
#
# Uso:  python semaforo_inteligente.py [COM6]
#       python semaforo_inteligente.py COM6 1,2       (forzar indices de camara)
#
# Teclas:  Z X orillas   C V camellon (solo 1 camara)   D deteccion
#          S simulacion(Arduino)   A B M botones   Q salir

import os
import sys
import time
import queue
import threading

import cv2
import numpy as np
from PIL import Image, ImageTk
import tkinter as tk

try:
    import serial
    import serial.tools.list_ports as list_ports
except Exception:
    serial = None
    list_ports = None

PUERTO = sys.argv[1] if len(sys.argv) > 1 else None
CAMS_FORZADAS = [int(x) for x in sys.argv[2].split(",")] if len(sys.argv) > 2 else None
ANCHO, ALTO = 640, 480
DETECTAR_CADA = 3
CONF_YOLO = 0.5
MODELOS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "modelos")
ESCALA_DET = 0.5
ALTO_MIN_REL = 0.18

# fronteras de la vista completa (1 camara), fraccion del ancho:
# A | calzada1 | camellon | calzada2 | B
ZA, ZM1, ZM2, ZB = 0.18, 0.40, 0.60, 0.82

# tiempos por calzada (segundos) - realistas de seguridad peatonal
VERDE_MIN = 6.0
AMBAR_T   = 3.0
ROJO_MIN  = 7.0                  # despeje garantizado para cruzar 2 carriles aunque falle la vision
DESPEJE   = 2.0
CUENTA    = 3.0
ROJO_MAX  = 30.0
CRUCE_SIM = 4.0

VERDE, AMBAR, ROJO_C = (60, 200, 60), (0, 190, 255), (60, 60, 230)
FONDO = "#15181d"
TXT = "#e6e6e6"


# ---------------------------------------------------------------- Arduino
class Enlace:
    def __init__(self, puerto):
        self.ser = None
        self.cola = queue.Queue()
        self.ult = {1: "", 2: ""}
        self.puerto = None
        if serial is None:
            return
        if puerto is None:
            puerto = self._autodetectar()
        if puerto is None:
            return
        try:
            self.ser = serial.Serial(puerto, 9600, timeout=0.2)
            time.sleep(2)
            self.ser.reset_input_buffer()
            self.puerto = puerto
            threading.Thread(target=self._leer, daemon=True).start()
        except Exception as e:
            print("Sin Arduino (%s); modo simulacion." % e)
            self.ser = None

    def _autodetectar(self):
        if list_ports is None:
            return None
        for p in list_ports.comports():
            d = (p.description or "").lower()
            if "bluetooth" in d:
                continue
            if any(k in d for k in ("arduino", "ch340", "usb serial", "usb-serial", "ftdi")):
                return p.device
        return None

    def _leer(self):
        buf = b""
        while self.ser:
            try:
                buf += self.ser.read(32)
            except Exception:
                break
            while b"\n" in buf:
                linea, buf = buf.split(b"\n", 1)
                t = linea.decode(errors="replace").strip()
                if t in ("A", "B", "M", "SA", "SB"):
                    self.cola.put(t)

    def _raw(self, s):
        if self.ser:
            try:
                self.ser.write(s.encode())
            except Exception:
                pass

    def cmd(self, c):
        self._raw(c + "\n")

    def luz(self, canal, estado):
        if estado != self.ult[canal]:
            self.ult[canal] = estado
            self._raw(estado + str(canal) + "\n")

    @property
    def real(self):
        return self.ser is not None


# ---------------------------------------------------------------- deteccion
class Detector:
    """YOLOv4-tiny por OpenCV-DNN (CPU, sin torch). HOG de respaldo si falta el modelo."""
    def __init__(self):
        self.tipo = "HOG"
        self.net = None
        cfg = os.path.join(MODELOS, "yolov4-tiny.cfg")
        pesos = os.path.join(MODELOS, "yolov4-tiny.weights")
        if os.path.exists(cfg) and os.path.exists(pesos):
            try:
                self.net = cv2.dnn.readNetFromDarknet(cfg, pesos)
                self.net.setPreferableBackend(cv2.dnn.DNN_BACKEND_OPENCV)
                self.net.setPreferableTarget(cv2.dnn.DNN_TARGET_CPU)
                ln = self.net.getLayerNames()
                self.salidas = [ln[i - 1] for i in self.net.getUnconnectedOutLayers().flatten()]
                self.tipo = "YOLOv4-tiny"
            except Exception as e:
                print("YOLO no cargo (%s); uso HOG." % e)
                self.net = None
        if self.net is None:
            self.hog = cv2.HOGDescriptor()
            self.hog.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())

    def personas(self, frame):
        return self._yolo(frame) if self.net is not None else self._hog(frame)

    def _yolo(self, frame):
        H, W = frame.shape[:2]
        blob = cv2.dnn.blobFromImage(frame, 1 / 255.0, (416, 416), swapRB=True, crop=False)
        self.net.setInput(blob)
        outs = self.net.forward(self.salidas)
        cajas, confs = [], []
        for o in outs:
            for det in o:
                sc = det[5:]
                cid = int(np.argmax(sc))
                conf = float(sc[cid])
                if cid == 0 and conf >= CONF_YOLO:
                    cx, cy, bw, bh = det[0] * W, det[1] * H, det[2] * W, det[3] * H
                    cajas.append([int(cx - bw / 2), int(cy - bh / 2), int(bw), int(bh)])
                    confs.append(conf)
        idx = cv2.dnn.NMSBoxes(cajas, confs, CONF_YOLO, 0.4)
        res = []
        if len(idx) > 0:
            for i in np.array(idx).flatten():
                x, y, w, h = cajas[i]
                res.append((max(0, x), max(0, y), w, h))
        return res

    def _hog(self, frame):
        chico = cv2.resize(frame, (0, 0), fx=ESCALA_DET, fy=ESCALA_DET)
        cajas, pesos = self.hog.detectMultiScale(chico, winStride=(8, 8),
                                                 padding=(8, 8), scale=1.05)
        salida, inv = [], 1.0 / ESCALA_DET
        hmin = ALTO_MIN_REL * frame.shape[0]
        for (x, y, w, h), p in zip(cajas, pesos):
            x, y, w, h = int(x * inv), int(y * inv), int(w * inv), int(h * inv)
            if h >= hmin and p >= 0.5:
                salida.append((x, y, w, h))
        return salida


# ---------------------------------------------------------------- semaforo de una calzada
class Semaforo:
    def __init__(self):
        self.estado = "VERDE"
        self.t0 = time.time()
        self.t_ocup = time.time()
        self.solicitud = False

    def _ir(self, e):
        self.estado = e
        self.t0 = time.time()

    def paso(self, espera, ocupado, boton):
        ahora = time.time()
        dt = ahora - self.t0
        activo = espera > 0 or ocupado > 0
        if activo:
            self.t_ocup = ahora
        if self.estado == "VERDE":
            if espera > 0 or boton:
                self.solicitud = True
            if self.solicitud and dt >= VERDE_MIN:
                self.solicitud = False
                self._ir("AMBAR")
        elif self.estado == "AMBAR":
            if dt >= AMBAR_T:
                self._ir("ROJO")
        elif self.estado == "ROJO":
            if dt >= ROJO_MIN:
                if (not activo and ahora - self.t_ocup >= DESPEJE) or dt >= ROJO_MAX:
                    self._ir("CUENTA")
        elif self.estado == "CUENTA":
            if ocupado > 0:
                self._ir("ROJO")
            elif dt >= CUENTA:
                self._ir("VERDE")
        return self.estado

    def codigo(self):
        return {"VERDE": "G", "AMBAR": "Y", "ROJO": "R", "CUENTA": "P"}[self.estado]

    @property
    def detenida(self):
        return self.estado in ("ROJO", "CUENTA")


# ---------------------------------------------------------------- peaton simulado (dos etapas)
class PeatonSim:
    def __init__(self, sentido):
        self.sentido = sentido
        self.plan = [("esp", 1), ("cruza", 1), ("esp", 2), ("cruza", 2)] if sentido == "AB" \
            else [("esp", 2), ("cruza", 2), ("esp", 1), ("cruza", 1)]
        self.i = 0
        self.prog = 0.0
        self.t = time.time()
        self.fin = False

    def actualizar(self, det1, det2):
        if self.fin:
            return
        accion, canal = self.plan[self.i]
        det = det1 if canal == 1 else det2
        ahora = time.time()
        if accion == "esp":
            if det:
                self.i += 1
                self.prog = 0.0
                self.t = ahora
        else:
            self.prog = min(1.0, (ahora - self.t) / CRUCE_SIM)
            if self.prog >= 1.0:
                self.i += 1
                self.prog = 0.0
                self.t = ahora
                if self.i >= len(self.plan):
                    self.fin = True

    def aporte(self):
        if self.fin:
            return (0, 0, 0, 0)
        accion, canal = self.plan[self.i]
        e1 = o1 = e2 = o2 = 0
        if canal == 1:
            if accion == "esp":
                e1 = 1
            else:
                o1 = 1
        else:
            if accion == "esp":
                e2 = 1
            else:
                o2 = 1
        return (e1, o1, e2, o2)

    def pos(self, cx):
        accion, canal = self.plan[self.i]
        y = int(ALTO * 0.60)
        if accion == "esp":
            x = cx["A"] if (canal == 1 and self.sentido == "AB") else \
                cx["B"] if (canal == 2 and self.sentido == "BA") else cx["M"]
            return int(x), y
        if canal == 1:
            ini, fin = (cx["A"], cx["M"]) if self.sentido == "AB" else (cx["M"], cx["A"])
        else:
            ini, fin = (cx["M"], cx["B"]) if self.sentido == "AB" else (cx["B"], cx["M"])
        return int(ini + (fin - ini) * self.prog), y


# ---------------------------------------------------------------- deteccion de camaras
def camaras_disponibles(maxn=4):
    """Prueba los indices 0..maxn-1 y devuelve los que entregan imagen."""
    encontradas = []
    for i in range(maxn):
        cap = cv2.VideoCapture(i, cv2.CAP_DSHOW)
        ok = False
        if cap.isOpened():
            ok, fr = cap.read()
            ok = ok and fr is not None
        cap.release()
        if ok:
            encontradas.append(i)
    return encontradas


ROLES = {1: ["completo"], 2: ["A", "B"], 3: ["A", "M", "B"]}


class CamaraFeed:
    """Una camara con su rol. Cada rol mapea las personas detectadas a la
    demanda/ocupacion de la calzada 1 y/o 2."""
    def __init__(self, index, rol, bounds):
        self.index = index
        self.rol = rol
        self.bounds = bounds           # referencia a [za, zm1, zm2, zb] (solo 'completo')
        self.cap = cv2.VideoCapture(index, cv2.CAP_DSHOW)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, ANCHO)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, ALTO)
        self.cajas = []
        self.frame = np.zeros((ALTO, ANCHO, 3), np.uint8)
        self.n = 0

    def leer(self, det, detectando):
        ok, fr = self.cap.read()
        if not ok or fr is None:
            self.frame = np.zeros((ALTO, ANCHO, 3), np.uint8)
            cv2.putText(self.frame, "sin senal cam %d" % self.index, (20, 40),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
            return
        fr = cv2.resize(fr, (ANCHO, ALTO))
        self.n += 1
        if detectando and self.n % DETECTAR_CADA == 0:
            self.cajas = det.personas(fr)
        self.frame = fr

    def _franjas(self, bordes, etiquetas, colores):
        capa = self.frame.copy()
        xs = [0] + [int(b * ANCHO) for b in bordes] + [ANCHO]
        for k in range(len(xs) - 1):
            cv2.rectangle(capa, (xs[k], 0), (xs[k + 1], ALTO), colores[k], -1)
        cv2.addWeighted(capa, 0.20, self.frame, 0.80, 0, self.frame)
        for b in bordes:
            x = int(b * ANCHO)
            cv2.line(self.frame, (x, 0), (x, ALTO), (210, 210, 210), 1)
        for k, t in enumerate(etiquetas):
            cxp = (xs[k] + xs[k + 1]) // 2
            cv2.putText(self.frame, t, (cxp - 34, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (235, 235, 235), 1)

    def procesar(self):
        """Dibuja zonas + cajas y devuelve (se1, oc1, se2, oc2)."""
        VERDEZ, CALZ, CAM = (90, 150, 90), (70, 70, 130), (60, 130, 60)
        se1 = oc1 = se2 = oc2 = 0
        f = [(x + w / 2) / ANCHO for (x, y, w, h) in self.cajas]

        if self.rol == "completo":
            za, zm1, zm2, zb = self.bounds
            self._franjas([za, zm1, zm2, zb],
                          ["BANQ A", "CALZADA 1", "CAMELLON", "CALZADA 2", "BANQ B"],
                          [VERDEZ, CALZ, CAM, CALZ, VERDEZ])
            for c in f:
                if c < za:
                    se1 += 1
                elif c < zm1:
                    se1 += 1; oc1 += 1
                elif c < zm2:
                    pass
                elif c < zb:
                    se2 += 1; oc2 += 1
                else:
                    se2 += 1
        elif self.rol == "A":
            self._franjas([0.5], ["BANQ A", "CALZADA 1"], [VERDEZ, CALZ])
            for c in f:
                if c < 0.5:
                    se1 += 1
                else:
                    se1 += 1; oc1 += 1
        elif self.rol == "B":
            self._franjas([0.5], ["CALZADA 2", "BANQ B"], [CALZ, VERDEZ])
            for c in f:
                if c < 0.5:
                    se2 += 1; oc2 += 1
                else:
                    se2 += 1
        elif self.rol == "M":
            self._franjas([0.5], ["-> CALZADA 1", "-> CALZADA 2"], [CAM, CAM])
            for c in f:
                if c < 0.5:
                    se1 += 1
                else:
                    se2 += 1

        for (x, y, w, h) in self.cajas:
            cv2.rectangle(self.frame, (x, y), (x + w, y + h), (0, 215, 255), 2)
        cv2.putText(self.frame, "cam %d  [%s]" % (self.index, self.rol), (8, ALTO - 12),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        return se1, oc1, se2, oc2

    def release(self):
        try:
            self.cap.release()
        except Exception:
            pass


# ---------------------------------------------------------------- aplicacion
class App:
    def __init__(self):
        self.enlace = Enlace(PUERTO)
        self.det = Detector()
        print("detector: %s" % self.det.tipo, flush=True)

        indices = CAMS_FORZADAS if CAMS_FORZADAS else camaras_disponibles()
        if not indices:
            print("No se encontro ninguna camara.", flush=True)
            indices = [0]
        indices = indices[:3]
        roles = ROLES[len(indices)]
        self.bounds = [ZA, ZM1, ZM2, ZB]
        self.feeds = [CamaraFeed(ix, roles[k], self.bounds) for k, ix in enumerate(indices)]
        print("camaras: %d  ->  %s" %
              (len(self.feeds), ", ".join("cam%d[%s]" % (f.index, f.rol) for f in self.feeds)), flush=True)

        self.s1 = Semaforo()
        self.s2 = Semaforo()
        self.detectando = True
        self.sims = []
        self.sim_on = False
        self.prev = ("", "")
        self.d = (0, 0, 0, 0)
        self.log = []

        self.root = tk.Tk()
        self.root.title("Semaforo Inteligente IoT - bulevar dividido (%d camara%s)" %
                        (len(self.feeds), "s" if len(self.feeds) > 1 else ""))
        self.root.configure(bg=FONDO)
        self.lienzo = tk.Label(self.root, bg="black")
        self.lienzo.grid(row=0, column=0, rowspan=2, padx=8, pady=8)
        self.panel = tk.Label(self.root, justify="left", anchor="nw", font=("Consolas", 12),
                              bg=FONDO, fg=TXT, width=36)
        self.panel.grid(row=0, column=1, sticky="nw", padx=(0, 8), pady=8)
        modo = "ARDUINO " + self.enlace.puerto if self.enlace.real else "SIMULACION (sin Arduino)"
        self.pie = tk.Label(self.root, text="modo: %s   Z X orillas  C V camellon  "
                            "D deteccion  S sim(Arduino)  A B M botones  Q salir" % modo,
                            bg=FONDO, fg="#8a93a0", font=("Consolas", 9))
        self.pie.grid(row=1, column=1, sticky="sw", padx=(0, 8), pady=8)

        self.root.bind("<Key>", self.tecla)
        self._anotar("camaras detectadas: %d" % len(self.feeds))
        if self.enlace.real:
            self.fijar_sim(True)
        self.loop()
        self.root.protocol("WM_DELETE_WINDOW", self.cerrar)
        self.root.mainloop()

    def _anotar(self, t):
        self.log.insert(0, time.strftime("%H:%M:%S ") + t)
        self.log = self.log[:7]

    def fijar_sim(self, on):
        self.sim_on = on
        self.enlace.cmd("S" if on else "N")
        self._anotar("simulacion Arduino: %s" % ("ON" if on else "OFF"))

    def tecla(self, e):
        k = e.keysym.lower()
        ch = e.char
        za, zm1, zm2, zb = self.bounds
        if k in ("q", "escape"):
            self.cerrar()
        elif ch == "z":
            self.bounds[0] = max(0.05, za - 0.02)
            self.bounds[3] = min(0.95, zb + 0.02)
        elif ch == "x":
            self.bounds[0] = min(zm1 - 0.04, za + 0.02)
            self.bounds[3] = max(zm2 + 0.04, zb - 0.02)
        elif ch == "c":
            self.bounds[1] = max(za + 0.04, zm1 - 0.02)
            self.bounds[2] = min(zb - 0.04, zm2 + 0.02)
        elif ch == "v":
            mid = (zm1 + zm2) / 2
            self.bounds[1] = min(mid - 0.03, zm1 + 0.02)
            self.bounds[2] = max(mid + 0.03, zm2 - 0.02)
        elif k == "d":
            self.detectando = not self.detectando
            for fe in self.feeds:
                fe.cajas = []
        elif k == "s":
            self.fijar_sim(not self.sim_on)
        elif k == "a":
            self.enlace.cola.put("A")
        elif k == "b":
            self.enlace.cola.put("B")
        elif k == "m":
            self.enlace.cola.put("M")

    def loop(self):
        for fe in self.feeds:
            fe.leer(self.det, self.detectando)

        se1 = oc1 = se2 = oc2 = 0
        total = 0
        for fe in self.feeds:
            a, b, c, d = fe.procesar()
            se1 += a; oc1 += b; se2 += c; oc2 += d
            total += len(fe.cajas)

        # eventos del Arduino: botones y peatones simulados
        b1 = b2 = False
        while not self.enlace.cola.empty():
            ev = self.enlace.cola.get()
            if ev == "A":
                b1 = True; self._anotar("boton banqueta A")
            elif ev == "B":
                b2 = True; self._anotar("boton banqueta B")
            elif ev == "M":
                b1 = b2 = True; self._anotar("boton camellon")
            elif ev in ("SA", "SB"):
                self.sims.append(PeatonSim("AB" if ev == "SA" else "BA"))
                self._anotar("Arduino: peaton simulado %s" % ("A->B" if ev == "SA" else "B->A"))

        det1, det2 = self.s1.detenida, self.s2.detenida
        vivos = []
        for p in self.sims:
            p.actualizar(det1, det2)
            a1, ao1, a2, ao2 = p.aporte()
            se1 += a1; oc1 += ao1; se2 += a2; oc2 += ao2
            if not p.fin:
                vivos.append(p)
        self.sims = vivos
        self.d = (se1, oc1, se2, oc2)

        est1 = self.s1.paso(se1, oc1, b1)
        est2 = self.s2.paso(se2, oc2, b2)
        self.enlace.luz(1, self.s1.codigo())
        self.enlace.luz(2, self.s2.codigo())
        if (est1, est2) != self.prev:
            print("[%s] calzada1=%-6s calzada2=%-6s  C1(esp%d/cru%d) C2(esp%d/cru%d)  cams=%d pers=%d" %
                  (time.strftime("%H:%M:%S"), est1, est2, se1, oc1, se2, oc2, len(self.feeds), total), flush=True)
            self.prev = (est1, est2)

        # peatones simulados dibujados solo en vista completa (1 camara)
        if len(self.feeds) == 1 and self.feeds[0].rol == "completo":
            za, zm1, zm2, zb = self.bounds
            cx = {"A": int(za * ANCHO) // 2,
                  "M": int((zm1 + zm2) * ANCHO) // 2,
                  "B": (int(zb * ANCHO) + ANCHO) // 2}
            fr = self.feeds[0].frame
            for p in self.sims:
                px, py = p.pos(cx)
                cruzando = p.plan[p.i][0] == "cruza"
                col = (0, 215, 255) if cruzando else (60, 220, 60)
                cv2.circle(fr, (px, py), 9, col, -1)
                cv2.circle(fr, (px, py), 9, (0, 0, 0), 1)
                cv2.putText(fr, "sim", (px - 11, py - 13), cv2.FONT_HERSHEY_SIMPLEX, 0.4, col, 1)

        comp = self.componer(est1, est2)
        img = Image.fromarray(cv2.cvtColor(comp, cv2.COLOR_BGR2RGB))
        self.tkimg = ImageTk.PhotoImage(img)
        self.lienzo.configure(image=self.tkimg)
        self.actualizar_panel(est1, est2, total)
        self.root.after(15, self.loop)

    def _dibujar_semaforo(self, img, ox, oy, estado, etiqueta):
        cv2.rectangle(img, (ox - 14, oy - 14), (ox + 14, oy + 74), (30, 30, 30), -1)
        for i, c in enumerate((ROJO_C, AMBAR, VERDE)):
            on = (estado in ("ROJO", "CUENTA") and i == 0) or (estado == "AMBAR" and i == 1) \
                or (estado == "VERDE" and i == 2)
            cv2.circle(img, (ox, oy + i * 29), 9, c if on else (26, 26, 26), -1)
        cv2.putText(img, etiqueta, (ox - 26, oy + 92), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (235, 235, 235), 1)

    def componer(self, est1, est2):
        w = 640 if len(self.feeds) == 1 else 430
        h = int(w * ALTO / ANCHO)
        imgs = [cv2.resize(fe.frame, (w, h)) for fe in self.feeds]
        comp = cv2.hconcat(imgs) if len(imgs) > 1 else imgs[0]
        # semaforos globales (una vez, sobre el compuesto)
        self._dibujar_semaforo(comp, 34, 30, est1, "calzada 1")
        self._dibujar_semaforo(comp, comp.shape[1] - 34, 30, est2, "calzada 2")
        return comp

    def actualizar_panel(self, est1, est2, total):
        se1, oc1, se2, oc2 = self.d
        def luz(e):
            return {"VERDE": "VERDE ", "AMBAR": "AMBAR ", "ROJO": "ROJO  ", "CUENTA": "ROJO* "}[e]
        t = ["  BULEVAR DIVIDIDO - DOS CALZADAS\n"]
        t.append("  camaras: %d" % len(self.feeds))
        t.append("   " + "  ".join("cam%d:%s" % (f.index, f.rol) for f in self.feeds) + "\n")
        t.append("  CALZADA 1  autos: %s" % luz(est1))
        t.append("    esperan %d  cruzan %d  %4.1fs" % (se1, oc1, time.time() - self.s1.t0))
        t.append("  CALZADA 2  autos: %s" % luz(est2))
        t.append("    esperan %d  cruzan %d  %4.1fs\n" % (se2, oc2, time.time() - self.s2.t0))
        t.append("  personas detectadas: %d" % total)
        t.append("  detector: %s  %s" % (self.det.tipo, "ON" if self.detectando else "OFF"))
        t.append("  simulacion Arduino: %s\n" % ("ON" if self.sim_on else "OFF"))
        t.append("  --- bitacora ---")
        t += ["   " + x for x in self.log]
        self.panel.configure(text="\n".join(t))

    def cerrar(self):
        self.enlace.luz(1, "G"); self.enlace.luz(2, "G")
        for fe in self.feeds:
            fe.release()
        self.root.destroy()


if __name__ == "__main__":
    App()
