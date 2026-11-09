import numpy as np
import pygame

VOLUMEN = 0.9

DO5, MI5, SOL5, DO6, MI6, SOL6 = 523.25, 659.25, 783.99, 1046.5, 1318.5, 1568.0
LA4, RE5, FA5, SI4, SOL4, MI4, DO4 = 440.0, 587.33, 698.46, 493.88, 392.0, 329.63, 261.63


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
                "punto_a": self._tic(620, vol=0.16),
                "punto_b": self._tic(470, vol=0.16),
                "energ": self._campanas((SOL5, DO6, MI6), separacion=0.05, vol=0.45),
                "fantasma": self._barrido(300, 1400, 0.28, vol=0.40),
                "fruta": self._melodia(((MI5, 0.07), (SOL5, 0.07), (DO6, 0.18)), vol=0.40),
                "muerte": self._melodia(((SI4, 0.11), (SOL4, 0.11), (MI4, 0.11), (DO4, 0.30)), vol=0.45),
                "meta": self._melodia(((DO5, 0.10), (MI5, 0.10), (SOL5, 0.10), (DO6, 0.10),
                                       (SOL5, 0.10), (DO6, 0.40)), vol=0.50),
                "sube": self._melodia(((DO5, 0.12), (MI5, 0.12), (SOL5, 0.12), (DO6, 0.40)), vol=0.5),
                "gen": self._melodia(((SOL5, 0.10), (DO6, 0.28)), vol=0.32),
            }
            self.susto = self._tremolo()
            self.canal_susto = pygame.mixer.Channel(0)
            self.canal_punto = pygame.mixer.Channel(1)
            self.en_susto = False
            self.alterna = False
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

    def _eco(self, x, retardo=0.11, ganancia=0.28, veces=2):
        d = int(self.sr * retardo)
        y = np.concatenate([x, np.zeros(d * veces)])
        for k in range(1, veces + 1):
            y[d * k:d * k + len(x)] += x * ganancia ** k
        return y

    def _tic(self, f, vol):
        t = self._t(0.07)
        onda = np.sin(2 * np.pi * f * t) + 0.2 * np.sin(2 * np.pi * 2 * f * t)
        return self._a_sonido(onda * self._envolvente(len(t), 0.004, 0.04, decaimiento=0.05), vol)

    def _campana(self, f, dur=0.8):
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
        pos = 0
        total = int(self.sr * (sum(d for _, d in notas) + 0.5))
        y = np.zeros(total)
        for f, d in notas:
            m = self._marimba(f, d)
            fin = min(total, pos + len(m))
            y[pos:fin] += m[:fin - pos]
            pos += int(self.sr * d)
        return self._a_sonido(self._eco(y, 0.13, 0.22), vol)

    def _barrido(self, f0, f1, dur, vol):
        t = self._t(dur)
        f = f0 * (f1 / f0) ** (t / dur)
        fase = 2 * np.pi * np.cumsum(f) / self.sr
        onda = np.sin(fase) + 0.25 * np.sin(2 * fase)
        return self._a_sonido(self._eco(onda * self._envolvente(len(t), 0.005, 0.06), 0.09, 0.25), vol)

    def _tremolo(self):
        dur = 0.5
        t = self._t(dur)
        f = 180 + 60 * np.sin(2 * np.pi * 2 * t)
        fase = 2 * np.pi * np.cumsum(f) / self.sr
        onda = np.sin(fase) + 0.3 * np.sin(2 * fase)
        cruce = int(self.sr * 0.02)
        onda[:cruce] *= np.linspace(0, 1, cruce)
        onda[-cruce:] *= np.linspace(1, 0, cruce)
        return self._a_sonido(onda, 0.10)

    def _a_sonido(self, onda, vol):
        onda = np.asarray(onda, dtype=float)
        pico = np.max(np.abs(onda)) or 1.0
        onda = (np.clip(onda / pico * vol * VOLUMEN, -1, 1) * 32767).astype(np.int16)
        if self.canales > 1:
            onda = np.ascontiguousarray(np.repeat(onda[:, None], self.canales, axis=1))
        return pygame.sndarray.make_sound(onda)

    def tocar(self, nombre):
        if not self.activo or self.mudo:
            return
        if nombre == "punto":
            if not self.canal_punto.get_busy():
                self.alterna = not self.alterna
                self.canal_punto.play(self.s["punto_a" if self.alterna else "punto_b"])
            return
        self.s[nombre].play()

    def alternar(self):
        self.mudo = not self.mudo
        if not self.mudo:
            self.tocar("gen")
        elif self.activo:
            self.fondo(False)

    def fondo(self, susto):
        if not self.activo:
            return
        susto = bool(susto) and not self.mudo
        if susto and not self.en_susto:
            self.canal_susto.play(self.susto, loops=-1, fade_ms=120)
        elif not susto and self.en_susto:
            self.canal_susto.fadeout(250)
        self.en_susto = susto
