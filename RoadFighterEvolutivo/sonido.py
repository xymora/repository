import numpy as np
import pygame

import config as C

VOLUMEN = 0.9
VOLUMEN_MOTOR = 0.20

DO5, MI5, SOL5, DO6, MI6, SOL6 = 523.25, 659.25, 783.99, 1046.5, 1318.5, 1568.0
LA4, RE5, FA5 = 440.0, 587.33, 698.46


class Sonido:
    def __init__(self):
        self.activo = False
        self.mudo = False
        self.error = ""
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init()
            self.sr, _, self.canales = pygame.mixer.get_init()
            pygame.mixer.set_num_channels(16)
            self.s = {
                "fuel": self._campanas((DO6, MI6, SOL6), separacion=0.07, vol=0.55),
                "sube": self._melodia(((DO5, 0.12), (MI5, 0.12), (SOL5, 0.12), (DO6, 0.40)), vol=0.5),
                "gen": self._melodia(((SOL5, 0.10), (DO6, 0.28)), vol=0.32),
                "choque": self._golpe_sordo(vol=0.6),
                "derrape": self._soplido(vol=0.18),
                "cambio": self._melodia(((LA4, 0.05), (RE5, 0.10)), vol=0.22),
            }
            self.frenado = self._siseo()
            self.motor = [self._motor(52 + 7.5 * k) for k in range(14)]
            self.canales_motor = (pygame.mixer.Channel(0), pygame.mixer.Channel(1))
            self.canal_freno = pygame.mixer.Channel(2)
            self.i_canal = 0
            self.i_motor = -1
            self.frenando = False
            self.alto_prev = None
            self.gas = 0.0
            self.activo = True
        except Exception as ex:
            self.activo = False
            self.error = str(ex)[:60]

    def _t(self, dur):
        return np.arange(int(self.sr * dur)) / self.sr

    def _envolvente(self, n, ataque=0.008, salida=0.05, decaimiento=None):
        env = np.ones(n)
        a = max(1, int(self.sr * ataque))
        r = max(1, int(self.sr * salida))
        env[:a] *= np.linspace(0, 1, a) ** 2
        env[-r:] *= np.linspace(1, 0, r) ** 2
        if decaimiento:
            env *= np.exp(-np.arange(n) / self.sr / decaimiento)
        return env

    def _paso_bajo(self, x, corte_hz):
        a = np.exp(-2 * np.pi * corte_hz / self.sr)
        y = np.empty_like(x)
        acc = 0.0
        for i, v in enumerate(x):
            acc = (1 - a) * v + a * acc
            y[i] = acc
        return y

    def _eco(self, x, retardo=0.11, ganancia=0.28, veces=2):
        d = int(self.sr * retardo)
        y = np.concatenate([x, np.zeros(d * veces)])
        for k in range(1, veces + 1):
            y[d * k:d * k + len(x)] += x * ganancia ** k
        return y

    def _campana(self, f, dur=0.9):
        t = self._t(dur)
        onda = (np.sin(2 * np.pi * f * t) * np.exp(-t * 4.0)
                + 0.35 * np.sin(2 * np.pi * f * 2.0 * t) * np.exp(-t * 7.0)
                + 0.12 * np.sin(2 * np.pi * f * 3.01 * t) * np.exp(-t * 11.0))
        return onda * self._envolvente(len(t), 0.003, 0.08)

    def _marimba(self, f, dur):
        t = self._t(dur + 0.35)
        onda = (np.sin(2 * np.pi * f * t) + 0.25 * np.sin(2 * np.pi * f * 4.0 * t) * np.exp(-t * 18))
        return onda * self._envolvente(len(t), 0.004, 0.12, decaimiento=0.28)

    def _campanas(self, notas, separacion, vol):
        partes = [self._campana(f) for f in notas]
        d = int(self.sr * separacion)
        y = np.zeros(d * (len(partes) - 1) + max(len(p) for p in partes))
        for k, p in enumerate(partes):
            y[k * d:k * d + len(p)] += p
        return self._a_sonido(self._eco(y), vol)

    def _melodia(self, notas, vol):
        partes, pos = [], 0
        total = int(self.sr * (sum(d for _, d in notas) + 0.5))
        y = np.zeros(total)
        for f, d in notas:
            m = self._marimba(f, d)
            fin = min(total, pos + len(m))
            y[pos:fin] += m[:fin - pos]
            pos += int(self.sr * d)
        return self._a_sonido(self._eco(y, 0.13, 0.22), vol)

    def _golpe_sordo(self, vol):
        t = self._t(0.55)
        f = 120 * np.exp(-t * 5) + 45
        fase = 2 * np.pi * np.cumsum(f) / self.sr
        tum = np.sin(fase) * np.exp(-t * 7)
        ruido = self._paso_bajo(np.random.default_rng(2).uniform(-1, 1, len(t)), 700) * np.exp(-t * 9)
        return self._a_sonido((tum + 0.6 * ruido) * self._envolvente(len(t), 0.004, 0.1), vol)

    def _soplido(self, vol):
        t = self._t(0.35)
        r = self._paso_bajo(self._paso_bajo(np.random.default_rng(3).uniform(-1, 1, len(t)), 500), 500)
        env = np.sin(np.pi * np.clip(t / 0.35, 0, 1)) ** 2
        return self._a_sonido(r * env * 2.0, vol)

    def _siseo(self):
        n = int(self.sr * 1.0)
        r = np.random.default_rng(5).uniform(-1, 1, n)
        r = self._paso_bajo(self._paso_bajo(r, 1800), 1800)
        cruce = int(self.sr * 0.05)
        r[:cruce] = r[:cruce] * np.linspace(0, 1, cruce) + r[-cruce:] * np.linspace(1, 0, cruce)
        return self._a_sonido(r[:-cruce], 0.16)

    def _motor(self, f):
        ciclos = max(1, round(0.6 * f))
        dur = ciclos / f
        t = np.arange(int(round(self.sr * dur))) / self.sr
        onda = (np.sin(2 * np.pi * f * t) + 0.32 * np.sin(2 * np.pi * 2 * f * t)
                + 0.10 * np.sin(2 * np.pi * 3 * f * t))
        tremolo = 1.0 + 0.10 * np.sin(2 * np.pi * (round(6 * dur) / dur) * t)
        return self._a_sonido(onda * tremolo / 1.42, VOLUMEN_MOTOR / VOLUMEN)

    def _a_sonido(self, onda, vol):
        onda = np.asarray(onda, dtype=float)
        pico = np.max(np.abs(onda)) or 1.0
        onda = (np.clip(onda / pico * vol * VOLUMEN, -1, 1) * 32767).astype(np.int16)
        if self.canales > 1:
            onda = np.ascontiguousarray(np.repeat(onda[:, None], self.canales, axis=1))
        return pygame.sndarray.make_sound(onda)

    def tocar(self, nombre):
        if self.activo and not self.mudo:
            self.s[nombre].play()

    def alternar(self):
        self.mudo = not self.mudo
        if not self.mudo:
            self.tocar("gen")
        elif self.activo:
            for c in self.canales_motor:
                c.fadeout(200)
            self.canal_freno.fadeout(200)
            self.i_motor = -1
            self.frenando = False

    def motor_vel(self, v, acel=0.0, alto=False, en_marcha=True):
        if not self.activo:
            return
        if self.mudo or not en_marcha:
            if self.i_motor != -1:
                for c in self.canales_motor:
                    c.fadeout(250)
                self.i_motor = -1
            if self.frenando:
                self.canal_freno.fadeout(200)
                self.frenando = False
            return
        gas = max(float(acel), 0.0)
        self.gas += (gas - self.gas) * 0.15
        vmax = C.VMAX_HIGH if alto else C.VMAX_LOW
        rpm = np.clip(v / vmax, 0.0, 1.0) * 0.75 + 0.25 * self.gas
        k = int(np.clip(rpm * (len(self.motor) - 1), 0, len(self.motor) - 1))
        if k != self.i_motor:
            viejo = self.canales_motor[self.i_canal]
            self.i_canal = 1 - self.i_canal
            self.canales_motor[self.i_canal].play(self.motor[k], loops=-1, fade_ms=140)
            viejo.fadeout(140)
            self.i_motor = k
        self.canales_motor[self.i_canal].set_volume(0.45 + 0.55 * self.gas)
        if self.alto_prev is not None and bool(alto) != self.alto_prev:
            self.tocar("cambio")
        self.alto_prev = bool(alto)
        frena = acel < -0.35 and v > 6.0
        if frena and not self.frenando:
            self.canal_freno.play(self.frenado, loops=-1, fade_ms=120)
        elif not frena and self.frenando:
            self.canal_freno.fadeout(220)
        if frena:
            self.canal_freno.set_volume(min(1.0, -acel) * min(1.0, v / 30.0))
        self.frenando = frena
