import numpy as np
import pygame

TASA = 22050


def _ruido(seg, rng, color=1.0):
    n = int(TASA * seg)
    w = rng.standard_normal(n)
    f = np.fft.rfft(w)
    k = np.arange(len(f)) + 1.0
    f /= k ** (color / 2)
    x = np.fft.irfft(f, n)
    return x / (np.abs(x).max() + 1e-9)


def _sonido(x, vol=1.0):
    x = np.clip(x * vol, -1, 1)
    a = (x * 32000).astype(np.int16)
    return pygame.sndarray.make_sound(np.ascontiguousarray(np.stack([a, a], -1)))


def _bucle(x, cruce=0.05):
    n = int(TASA * cruce)
    r = np.linspace(0, 1, n)
    x = x.copy()
    x[:n] = x[:n] * r + x[-n:] * (1 - r)
    return x[:-n]


class Sonido:
    def __init__(self):
        self.ok = False
        try:
            pygame.mixer.pre_init(TASA, -16, 2, 512)
            pygame.mixer.init(TASA, -16, 2, 512)
            pygame.mixer.set_num_channels(16)
        except pygame.error:
            return
        rng = np.random.default_rng(4)
        t = np.arange(int(TASA * 2.0)) / TASA
        rugido = _ruido(2.0, rng, 1.6)
        silbido = _ruido(2.0, rng, 0.2) * 0.25 + 0.35 * np.sin(2 * np.pi * 1850 * t) * (0.6 + 0.4 * np.sin(2 * np.pi * 3 * t))
        self.s_motor = _sonido(_bucle(rugido * 0.8 + silbido * 0.35), 0.9)
        pq = _ruido(2.0, rng, 1.9)
        pq = pq * (0.7 + 0.3 * np.abs(_ruido(2.0, rng, 2.2)))
        self.s_pq = _sonido(_bucle(pq), 1.0)
        self.s_viento = _sonido(_bucle(_ruido(2.0, rng, 1.0)), 0.6)
        rueda = _ruido(1.0, rng, 1.2) * (0.6 + 0.4 * (np.sin(2 * np.pi * 9 * t[:TASA]) > 0.9))
        self.s_rueda = _sonido(_bucle(rueda), 0.6)
        tt = np.arange(int(TASA * 0.5)) / TASA
        pita = np.sign(np.sin(2 * np.pi * 900 * tt)) * (tt < 0.25) * 0.4
        self.s_alarma = _sonido(pita, 0.6)
        gru = np.sin(2 * np.pi * (380 + 40 * np.sin(2 * np.pi * 7 * t[:TASA])) * t[:TASA]) * 0.35
        self.s_ir = _sonido(_bucle(gru), 0.7)
        tc = np.arange(int(TASA * 0.6)) / TASA
        golpe = _ruido(0.6, rng, 1.8) * np.exp(-tc * 9)
        self.s_toque = _sonido(golpe, 1.0)
        chirrido = np.sin(2 * np.pi * (1200 - 500 * tc) * tc) * np.exp(-tc * 6) * 0.5 + _ruido(0.6, rng, 0.3) * np.exp(-tc * 7) * 0.4
        self.s_chirrido = _sonido(chirrido, 0.8)
        te = np.arange(int(TASA * 2.5)) / TASA
        expl = _ruido(2.5, rng, 1.9) * np.exp(-te * 1.6)
        self.s_explosion = _sonido(expl, 1.0)
        tm = np.arange(int(TASA * 1.6)) / TASA
        misil = _ruido(1.6, rng, 0.9) * np.minimum(1, tm * 20) * np.exp(-tm * 1.2)
        self.s_misil = _sonido(misil, 0.9)
        tg = np.arange(int(TASA * 0.5)) / TASA
        cañon = _ruido(0.5, rng, 1.0) * (0.55 + 0.45 * np.sign(np.sin(2 * np.pi * 100 * tg)))
        self.s_cañon = _sonido(_bucle(cañon, 0.02), 0.8)
        th = np.arange(int(TASA * 3.0)) / TASA
        hid = np.sin(2 * np.pi * (220 + 30 * np.sin(th * 4)) * th) * 0.25 + _ruido(3.0, rng, 1.0) * 0.15
        self.s_tren = _sonido(hid * np.minimum(1, th * 3) * np.minimum(1, (3 - th) * 3), 0.6)
        tk = np.arange(int(TASA * 0.35)) / TASA
        self.s_clic = _sonido(np.sin(2 * np.pi * 1400 * tk) * np.exp(-tk * 25), 0.4)
        self.canales = {}
        for nombre, snd in (("motor", self.s_motor), ("pq", self.s_pq), ("viento", self.s_viento),
                            ("rueda", self.s_rueda), ("ir", self.s_ir), ("cañon", self.s_cañon)):
            ch = snd.play(-1)
            if ch:
                ch.set_volume(0)
            self.canales[nombre] = ch
        self.t_alarma = 0.0
        self.ok = True
        self.silencio = False

    def _vol(self, nombre, v):
        ch = self.canales.get(nombre)
        if ch:
            ch.set_volume(0 if self.silencio else float(np.clip(v, 0, 1)))

    def actualizar(self, e, dt):
        if not self.ok:
            return
        motor = e.get("rpm", 0)
        self._vol("motor", 0.12 + 0.45 * motor)
        self._vol("pq", 0.7 * e.get("pq", 0))
        v = e.get("vel", 0)
        self._vol("viento", min(1, (v / 300) ** 2) * 0.55 + e.get("aerofreno", 0) * 0.25 + e.get("buffet", 0) * 0.3)
        self._vol("rueda", min(1, v / 60) * 0.6 if e.get("suelo") else 0)
        self._vol("ir", 0.5 if e.get("tono_ir") else 0)
        self._vol("cañon", 0.8 if e.get("cañon") else 0)
        self.t_alarma -= dt
        if e.get("alarma") and self.t_alarma <= 0 and not self.silencio:
            self.s_alarma.play()
            self.t_alarma = 0.5

    def evento(self, nombre):
        if not self.ok or self.silencio:
            return
        s = {"toque": self.s_toque, "chirrido": self.s_chirrido, "explosion": self.s_explosion,
             "misil": self.s_misil, "tren": self.s_tren, "clic": self.s_clic}.get(nombre)
        if s:
            s.play()

    def callar(self):
        if not self.ok:
            return
        for ch in self.canales.values():
            if ch:
                ch.set_volume(0)
