import threading

import numpy as np

TASA = 44100
MAX_LATENCIA = int(TASA * 0.15)
PREBUFER = int(TASA * 0.05)


class Altavoz:
    def __init__(self, volumen=0.7):
        self.volumen = volumen
        self.activo = True
        self.cerrojo = threading.Lock()
        self.bufer = np.zeros((0, 2), dtype=np.float32)
        self.error = None
        self.llenando = True
        self.empujadas = 0
        self.cortes = 0
        self.flujo = None
        try:
            import sounddevice as sd
            self.flujo = sd.OutputStream(samplerate=TASA, channels=2, dtype="float32", blocksize=512,
                                         latency="low", callback=self._llamada)
            self.flujo.start()
        except Exception as e:
            self.error = str(e)

    @property
    def disponible(self):
        return self.flujo is not None

    def _llamada(self, salida, cuadros, tiempo, estado):
        with self.cerrojo:
            if self.llenando and len(self.bufer) < PREBUFER:
                salida[:] = 0
                return
            self.llenando = len(self.bufer) < cuadros
            if self.llenando:
                self.cortes += 1
            n = min(cuadros, len(self.bufer))
            salida[:n] = self.bufer[:n]
            self.bufer = self.bufer[n:]
        salida[n:] = 0

    def empujar(self, muestras):
        if muestras is None or not self.disponible:
            return
        if not self.activo:
            return
        x = np.clip(muestras * self.volumen, -1, 1).astype(np.float32)
        with self.cerrojo:
            self.empujadas += len(x)
            self.bufer = np.concatenate([self.bufer, x])
            if len(self.bufer) > MAX_LATENCIA:
                self.bufer = self.bufer[-MAX_LATENCIA // 2:]

    def vaciar(self):
        with self.cerrojo:
            self.bufer = np.zeros((0, 2), dtype=np.float32)
            self.llenando = True

    def cerrar(self):
        if self.flujo is not None:
            try:
                self.flujo.stop()
                self.flujo.close()
            except Exception:
                pass
            self.flujo = None
