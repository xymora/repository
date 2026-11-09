import os
import struct
import time
import zipfile
import zlib

import numpy as np

import nucleo as N

ARRIBA, ABAJO, IZQUIERDA, DERECHA = "arriba", "abajo", "izquierda", "derecha"
BITS = {DERECHA: 0x01, IZQUIERDA: 0x02, ARRIBA: 0x04, ABAJO: 0x08,
        "A": 0x10, "B": 0x20, "SELECT": 0x40, "START": 0x80}
EXTENSIONES = (".gb", ".gbc", ".cgb", ".sgb")

TIPOS_MBC = {0x00: 0, 0x08: 0, 0x09: 0, 0x01: 1, 0x02: 1, 0x03: 1, 0x05: 2, 0x06: 2,
             0x0F: 3, 0x10: 3, 0x11: 3, 0x12: 3, 0x13: 3,
             0x19: 5, 0x1A: 5, 0x1B: 5, 0x1C: 5, 0x1D: 5, 0x1E: 5}
CON_BATERIA = {0x03, 0x06, 0x09, 0x0D, 0x0F, 0x10, 0x13, 0x1B, 0x1E}
TAM_RAM = {0: 0, 1: 0x800, 2: 0x2000, 3: 0x8000, 4: 0x20000, 5: 0x10000}


def leer_rom(ruta):
    if ruta.lower().endswith(".zip"):
        with zipfile.ZipFile(ruta) as z:
            for nombre in z.namelist():
                if nombre.lower().endswith(EXTENSIONES):
                    return z.read(nombre)
        raise ValueError("el zip no contiene ninguna ROM .gb/.gbc")
    with open(ruta, "rb") as f:
        return f.read()


def cabecera(datos):
    if len(datos) < 0x150:
        raise ValueError("el archivo es demasiado pequeño para ser una ROM")
    t = datos[0x134:0x144]
    cgb_flag = datos[0x143]
    if cgb_flag in (0x80, 0xC0):
        t = datos[0x134:0x143]
    titulo = bytes(c for c in t if 32 <= c < 127).decode("ascii", "ignore").strip()
    tipo = datos[0x147]
    suma = (datos[0x14E] << 8) | datos[0x14F]
    return {
        "titulo": titulo or "SIN TITULO",
        "cgb": cgb_flag in (0x80, 0xC0),
        "solo_cgb": cgb_flag == 0xC0,
        "tipo": tipo,
        "mbc": TIPOS_MBC.get(tipo, 5 if tipo > 0x13 else 1),
        "bateria": tipo in CON_BATERIA,
        "ram": 512 if TIPOS_MBC.get(tipo) == 2 else TAM_RAM.get(datos[0x149], 0x2000),
        "suma": suma,
        "id": "".join(ch if ch.isalnum() else "_" for ch in (titulo or "ROM")) + "_%04x" % suma,
    }


class GameBoy:
    def __init__(self, datos, ruta_sav=None, colores=None):
        self.info = cabecera(datos)
        n = max(2, 1 << int(np.ceil(np.log2(max(len(datos), 0x8000) / 0x4000))))
        self.rom = np.zeros(n * 0x4000, dtype=np.uint8)
        self.rom[:len(datos)] = np.frombuffer(datos, dtype=np.uint8)
        self.colores = np.array(colores if colores is not None else N.DMG_COLORES, dtype=np.uint8)
        self.st = np.zeros(N.TAM_ST, dtype=np.int64)
        self.R = np.zeros(N.TAM_R, dtype=np.uint8)
        self.fb = np.zeros((144, 160, 3), dtype=np.uint8)
        self.obs = np.zeros((18, 20), dtype=np.float32)
        self.aud = np.zeros((N.TAM_AUDIO, 2), dtype=np.float64)
        self.filtro = np.zeros(4, dtype=np.float64)
        self.con_sonido = False
        self.ruta_sav = ruta_sav
        self.botones = 0
        self.reiniciar()
        self.cargar_bateria()

    def reiniciar(self):
        st, R, info = self.st, self.R, self.info
        bat = R[N.ERAM:N.ERAM + 0x20000].copy()
        st[:] = 0
        R[:] = 0
        R[N.ERAM:N.ERAM + 0x20000] = bat
        cgb = 1 if info["cgb"] else 0
        st[N.CGB] = cgb
        if cgb:
            st[0], st[1], st[2], st[3], st[4], st[5], st[N.RF], st[N.RA] = 0, 0, 0xFF, 0x56, 0, 0x0D, 0x80, 0x11
        else:
            st[0], st[1], st[2], st[3], st[4], st[5], st[N.RF], st[N.RA] = 0, 0x13, 0, 0xD8, 1, 0x4D, 0xB0, 0x01
        st[N.SP], st[N.PC] = 0xFFFE, 0x100
        st[N.MBC] = info["mbc"]
        st[N.NBANCOS] = len(self.rom) // 0x4000
        st[N.TAMRAM] = info["ram"]
        st[N.BAJO], st[N.BANCO] = 1, 1
        st[N.WBANCO] = 1
        st[N.MODOPPU] = 2
        st[N.DIVC] = 0xABCC
        st[N.SEC_T] = 8192
        st[N.SONIDO] = 1 if self.con_sonido else 0
        io = {0x00: 0xCF, 0x05: 0, 0x06: 0, 0x07: 0xF8, 0x10: 0x80, 0x11: 0xBF, 0x12: 0xF3, 0x14: 0xBF,
              0x16: 0x3F, 0x19: 0xBF, 0x1A: 0x7F, 0x1B: 0xFF, 0x1C: 0x9F, 0x1E: 0xBF, 0x20: 0xFF,
              0x23: 0xBF, 0x24: 0x77, 0x25: 0xF3, 0x26: 0xF1, 0x40: 0x91, 0x41: 0x85, 0x47: 0xFC,
              0x48: 0xFF, 0x49: 0xFF, 0x0F: 0xE1, 0xFF: 0x00}
        for k, v in io.items():
            R[N.IO + k] = v
        if cgb:
            R[N.BGPAL:N.BGPAL + 64] = 0xFF
            R[N.BGPAL + 1:N.BGPAL + 64:2] = 0x7F
            R[N.OBPAL:N.OBPAL + 64] = 0xFF
            R[N.OBPAL + 1:N.OBPAL + 64:2] = 0x7F
        self.botones = 0

    def cargar_bateria(self):
        if self.ruta_sav and self.info["bateria"] and os.path.exists(self.ruta_sav):
            with open(self.ruta_sav, "rb") as f:
                datos = f.read()
            tam = max(self.info["ram"], 512)
            d = np.frombuffer(datos[:tam], dtype=np.uint8)
            self.R[N.ERAM:N.ERAM + len(d)] = d
            cola = datos[tam:]
            if len(cola) >= 20 and cola[:4] == b"RTC0":
                seg, cuando = struct.unpack("<qd", cola[4:20])
                self.st[N.RTCBASE] = seg + max(0, int(time.time() - cuando))

    def guardar_bateria(self):
        if not (self.ruta_sav and self.info["bateria"] and self.st[N.SUCIA]):
            return False
        tam = max(self.info["ram"], 512)
        os.makedirs(os.path.dirname(self.ruta_sav), exist_ok=True)
        with open(self.ruta_sav, "wb") as f:
            f.write(self.R[N.ERAM:N.ERAM + tam].tobytes())
            if self.info["mbc"] == 3:
                f.write(b"RTC0" + struct.pack("<qd", int(N.segundos_rtc(self.st)), time.time()))
        self.st[N.SUCIA] = 0
        return True

    def pulsar(self, mascara):
        nuevos = mascara & ~self.botones
        self.botones = mascara
        self.st[N.BOTONES] = mascara
        if nuevos:
            self.R[N.IO + 0x0F] |= 0x10

    def cuadros(self, n=1):
        N.correr_cuadros(self.st, self.rom, self.R, self.fb, n, self.colores, self.aud)
        return self.fb

    def sonido(self, si):
        self.con_sonido = bool(si)
        self.st[N.SONIDO] = 1 if si else 0
        self.st[N.N_AUDIO] = 0

    def audio(self):
        n = int(self.st[N.N_AUDIO])
        self.st[N.N_AUDIO] = 0
        if n == 0:
            return None
        N.paso_alto(self.aud, n, self.filtro)
        return (self.aud[:n] / 512.0).astype(np.float32)

    def observar(self):
        N.observar(self.fb, self.obs)
        return self.obs

    def ram_trabajo(self):
        return self.R[N.WRAM:N.WRAM + 0x2000]

    def hram(self):
        return self.R[N.IO + 0x80:N.IO + 0xFF]

    def serie(self):
        n = int(self.st[N.NSERIE])
        return bytes(self.R[N.SERIE:N.SERIE + n]).decode("latin-1")

    def estado(self):
        return zlib.compress(self.st.tobytes() + self.R.tobytes() + self.fb.tobytes(), 3)

    def restaurar(self, datos):
        b = zlib.decompress(datos)
        a = len(b) - N.TAM_R - 144 * 160 * 3
        st = np.frombuffer(b[:a], dtype=np.int64)
        self.st[:] = 0
        self.st[:len(st)] = st
        if len(st) < N.TAM_ST:
            self.st[N.SEC_T] = 8192
        self.st[N.SONIDO] = 1 if self.con_sonido else 0
        self.st[N.N_AUDIO] = 0
        self.R[:] = np.frombuffer(b[a:a + N.TAM_R], dtype=np.uint8)
        self.fb[:] = np.frombuffer(b[a + N.TAM_R:], dtype=np.uint8).reshape(144, 160, 3)
        self.botones = int(self.st[N.BOTONES])


def mascara(botones):
    m = 0
    for b in botones:
        m |= BITS[b]
    return m


def precompilar():
    datos = bytearray(0x8000)
    datos[0x100:0x104] = bytes([0x00, 0xC3, 0x50, 0x01])
    datos[0x150:0x153] = bytes([0x18, 0xFE, 0x00])
    datos[0x147] = 0
    gb = GameBoy(bytes(datos))
    gb.cuadros(1)
    gb.observar()
    return gb
