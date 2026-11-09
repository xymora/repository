import struct
import threading
import time
import numpy as np
import usb1

VID = 0x045E
PID_CAMARA = (0x02AE, 0x02BF)
PID_MOTOR = 0x02B0

ANCHO, ALTO = 640, 480
BYTES_PROF = ANCHO * ALTO * 11 // 8
BYTES_RGB = ANCHO * ALTO
ALTO_IR = 488
BYTES_IR = ANCHO * ALTO_IR * 10 // 8
PAQUETE = 1920
PAQ_POR_TRANSF = 16
N_TRANSF = 8

LED = {"apagado": 0, "verde": 1, "rojo": 2, "amarillo": 3, "parpadeo verde": 4, "parpadeo rojo-amarillo": 6}


class ErrorKinect(Exception):
    pass


def desempacar_11bits(datos):
    b = np.frombuffer(datos, dtype=np.uint8).reshape(-1, 11).astype(np.uint16)
    p = np.empty((b.shape[0], 8), dtype=np.uint16)
    p[:, 0] = (b[:, 0] << 3) | (b[:, 1] >> 5)
    p[:, 1] = ((b[:, 1] & 0x1F) << 6) | (b[:, 2] >> 2)
    p[:, 2] = ((b[:, 2] & 0x03) << 9) | (b[:, 3] << 1) | (b[:, 4] >> 7)
    p[:, 3] = ((b[:, 4] & 0x7F) << 4) | (b[:, 5] >> 4)
    p[:, 4] = ((b[:, 5] & 0x0F) << 7) | (b[:, 6] >> 1)
    p[:, 5] = ((b[:, 6] & 0x01) << 10) | (b[:, 7] << 2) | (b[:, 8] >> 6)
    p[:, 6] = ((b[:, 8] & 0x3F) << 5) | (b[:, 9] >> 3)
    p[:, 7] = ((b[:, 9] & 0x07) << 8) | b[:, 10]
    return p.reshape(ALTO, ANCHO)


def desempacar_10bits(datos):
    b = np.frombuffer(datos, dtype=np.uint8).reshape(-1, 5).astype(np.uint16)
    p = np.empty((b.shape[0], 4), dtype=np.uint16)
    p[:, 0] = (b[:, 0] << 2) | (b[:, 1] >> 6)
    p[:, 1] = ((b[:, 1] & 0x3F) << 4) | (b[:, 2] >> 4)
    p[:, 2] = ((b[:, 2] & 0x0F) << 6) | (b[:, 3] >> 2)
    p[:, 3] = ((b[:, 3] & 0x03) << 8) | b[:, 4]
    return p.reshape(ALTO_IR, ANCHO)


def crudo_a_metros(crudo):
    c = crudo.astype(np.float32)
    m = 0.1236 * np.tan(c / 2842.5 + 1.1863)
    m[(crudo >= 2047) | (m <= 0) | (m > 10)] = 0
    return m


class Ensamblador:
    def __init__(self, bandera, tam_esperado):
        self.bandera = bandera
        self.tam = tam_esperado
        self.buf = bytearray()
        self.activo = False
        self.sig = 0
        self.ultimo = None
        self.frames = 0
        self.descartados = 0
        self.paquetes = 0
        self.lock = threading.Lock()

    def paquete(self, datos):
        if len(datos) < 12 or datos[0] != 0x52 or datos[1] != 0x42:
            return
        flag = datos[3]
        if flag & 0xF0 != self.bandera:
            return
        self.paquetes += 1
        tipo = flag & 0x0F
        seq = datos[5]
        cuerpo = datos[12:]
        if tipo == 1:
            self.buf = bytearray(cuerpo)
            self.activo = True
            self.sig = (seq + 1) & 0xFF
            return
        if not self.activo:
            return
        if seq != self.sig:
            self.activo = False
            self.descartados += 1
            return
        self.sig = (seq + 1) & 0xFF
        self.buf += cuerpo
        if tipo == 5:
            self.activo = False
            if len(self.buf) >= self.tam:
                with self.lock:
                    self.ultimo = bytes(self.buf[: self.tam])
                    self.frames += 1
            else:
                self.descartados += 1

    def tomar(self):
        with self.lock:
            d, self.ultimo = self.ultimo, None
        return d


class Kinect:
    def __init__(self):
        self.ctx = usb1.USBContext()
        self.ctx.open()
        self.cam = None
        self.motor = None
        self.info = {}
        self.etiqueta = 1
        self.corriendo = False
        self.transferencias = []
        self.prof = Ensamblador(0x70, BYTES_PROF)
        self.rgb = Ensamblador(0x80, BYTES_RGB)
        self.hilo = None
        self.video_ir = False

    def abrir(self):
        disp_cam = disp_motor = None
        for d in self.ctx.getDeviceList(skip_on_error=True):
            if d.getVendorID() != VID:
                continue
            if d.getProductID() in PID_CAMARA and disp_cam is None:
                disp_cam = d
            elif d.getProductID() == PID_MOTOR and disp_motor is None:
                disp_motor = d
        if disp_cam is None:
            raise ErrorKinect("No se encontró la cámara del Kinect (USB 045E:02AE). Revisa el cable y la fuente de 12 V.")
        self.cam = disp_cam.open()
        try:
            self.cam.claimInterface(0)
        except usb1.USBError as e:
            raise ErrorKinect(f"No se pudo reclamar la interfaz de la cámara: {e}")
        try:
            serie = self.cam.getSerialNumber()
        except usb1.USBError:
            serie = "?"
        self.info = {
            "id": f"{VID:04X}:{disp_cam.getProductID():04X}",
            "serie": serie,
            "bus": f"bus {disp_cam.getBusNumber()} dir {disp_cam.getDeviceAddress()}",
            "modelo": "Kinect Xbox 360 (1414)" if disp_cam.getProductID() == 0x02AE else "Kinect 1473 / Windows",
        }
        if disp_motor is not None:
            try:
                self.motor = disp_motor.open()
                self.motor.claimInterface(0)
            except usb1.USBError:
                self.motor = None

    def comando(self, cmd, palabras):
        cab = struct.pack("<2sHHH", b"GM", len(palabras), cmd, self.etiqueta)
        datos = cab + struct.pack("<%dH" % len(palabras), *palabras)
        self.cam.controlWrite(0x40, 0, 0, 0, datos, timeout=1000)
        for _ in range(100):
            r = self.cam.controlRead(0xC0, 0, 0, 0, 512, timeout=1000)
            if len(r) > 0:
                break
            time.sleep(0.005)
        else:
            raise ErrorKinect(f"Sin respuesta al comando {cmd:#x}")
        if len(r) < 8 or r[:2] != b"RB":
            raise ErrorKinect(f"Respuesta inválida: {bytes(r[:8]).hex()}")
        _, ln, rcmd, rtag = struct.unpack("<2sHHH", bytes(r[:8]))
        if rcmd != cmd or rtag != self.etiqueta:
            raise ErrorKinect("Respuesta desfasada del Kinect")
        self.etiqueta = (self.etiqueta + 1) & 0xFFFF
        return struct.unpack("<%dH" % ln, bytes(r[8 : 8 + 2 * ln]))

    def registro(self, reg, valor):
        r = self.comando(0x03, [reg, valor])
        if len(r) != 1 or r[0] != 0:
            raise ErrorKinect(f"Fallo al escribir registro {reg:#x}={valor:#x}: {r}")

    def _vaciar_respuestas(self):
        for _ in range(5):
            try:
                if not self.cam.controlRead(0xC0, 0, 0, 0, 512, timeout=50):
                    break
            except usb1.USBError:
                break

    def _cb(self, ensamblador):
        def cb(t):
            if t.getStatus() == usb1.TRANSFER_COMPLETED:
                for estado, buf in t.iterISO():
                    if estado == usb1.TRANSFER_COMPLETED and len(buf):
                        ensamblador.paquete(buf)
            if self.corriendo and t.getStatus() != usb1.TRANSFER_CANCELLED:
                try:
                    t.submit()
                except usb1.USBError:
                    pass
        return cb

    def _preparar(self, ep, ensamblador):
        for _ in range(N_TRANSF):
            t = self.cam.getTransfer(iso_packets=PAQ_POR_TRANSF)
            t.setIsochronous(ep, PAQUETE * PAQ_POR_TRANSF, callback=self._cb(ensamblador), timeout=0)
            self.transferencias.append(t)

    def iniciar(self):
        self._vaciar_respuestas()
        self.registro(0x105, 0x00)
        self.registro(0x06, 0x00)
        self.registro(0x05, 0x00)
        self.registro(0x12, 0x03)
        self.registro(0x13, 0x01)
        self.registro(0x14, 0x1E)
        self.registro(0x17, 0x00)
        self.registro(0x0C, 0x00)
        self.registro(0x0D, 0x01)
        self.registro(0x0E, 0x1E)
        self.registro(0x47, 0x00)
        self.registro(0x06, 0x02)
        self.registro(0x05, 0x01)
        self.corriendo = True
        self._preparar(0x82, self.prof)
        self._preparar(0x81, self.rgb)
        for t in self.transferencias:
            t.submit()
        self.hilo = threading.Thread(target=self._bucle, daemon=True)
        self.hilo.start()
        self.led("verde")

    def _bucle(self):
        while self.corriendo or any(t.isSubmitted() for t in self.transferencias):
            try:
                self.ctx.handleEventsTimeout(0.1)
            except usb1.USBError:
                pass

    def profundidad(self):
        d = self.prof.tomar()
        return None if d is None else desempacar_11bits(d)

    def color(self):
        if self.video_ir:
            return None
        d = self.rgb.tomar()
        if d is None or len(d) != BYTES_RGB:
            return None
        return np.frombuffer(d, dtype=np.uint8).reshape(ALTO, ANCHO)

    def infrarrojo(self):
        if not self.video_ir:
            return None
        d = self.rgb.tomar()
        if d is None or len(d) != BYTES_IR:
            return None
        return desempacar_10bits(d)

    def modo_video(self, ir):
        ir = bool(ir)
        if ir == self.video_ir:
            return
        self.registro(0x05, 0x00)
        with self.rgb.lock:
            self.rgb.tam = BYTES_IR if ir else BYTES_RGB
            self.rgb.activo = False
            self.rgb.ultimo = None
        self.video_ir = ir
        self.registro(0x0C, 0x00)
        self.registro(0x0D, 0x01)
        self.registro(0x0E, 0x1E)
        self.registro(0x47, 0x00)
        self.registro(0x05, 0x03 if ir else 0x01)

    def inclinar(self, grados):
        if self.motor is None:
            return
        g = int(max(-27, min(27, grados)))
        try:
            self.motor.controlWrite(0x40, 0x31, (g * 2) & 0xFFFF, 0, b"", timeout=500)
        except usb1.USBError:
            pass

    def led(self, nombre):
        if self.motor is None:
            return
        try:
            self.motor.controlWrite(0x40, 0x06, LED.get(nombre, 1), 0, b"", timeout=500)
        except usb1.USBError:
            pass

    def estado_motor(self):
        if self.motor is None:
            return None
        try:
            r = bytes(self.motor.controlRead(0xC0, 0x32, 0, 0, 10, timeout=200))
        except usb1.USBError:
            return None
        if len(r) < 10:
            return None
        ax, ay, az = struct.unpack(">hhh", r[2:8])
        ang = struct.unpack("b", r[8:9])[0]
        return {"acel": (ax / 819.0, ay / 819.0, az / 819.0), "angulo": None if ang == -128 else ang / 2.0}

    def cerrar(self):
        if self.cam is None:
            return
        self.corriendo = False
        for t in self.transferencias:
            try:
                if t.isSubmitted():
                    t.cancel()
            except usb1.USBError:
                pass
        if self.hilo:
            self.hilo.join(timeout=2)
        try:
            self.registro(0x06, 0x00)
            self.registro(0x05, 0x00)
        except Exception:
            pass
        self.led("parpadeo verde")
        for t in self.transferencias:
            try:
                t.close()
            except Exception:
                pass
        self.transferencias = []
        for h in (self.motor, self.cam):
            if h is not None:
                try:
                    h.releaseInterface(0)
                    h.close()
                except Exception:
                    pass
        self.cam = self.motor = None
        self.ctx.close()
