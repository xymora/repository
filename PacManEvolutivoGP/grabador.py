import ctypes
import datetime
import os
import shutil
import subprocess
import threading
import time
import tkinter as tk
from ctypes import wintypes

CARPETA_GRABACIONES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "grabaciones")
FPS = 30
CRF = 16
PW_CLIENTONLY, PW_RENDERFULLCONTENT = 1, 2


def ruta_ffmpeg():
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return shutil.which("ffmpeg")


class _BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [("biSize", wintypes.DWORD), ("biWidth", wintypes.LONG),
                ("biHeight", wintypes.LONG), ("biPlanes", wintypes.WORD),
                ("biBitCount", wintypes.WORD), ("biCompression", wintypes.DWORD),
                ("biSizeImage", wintypes.DWORD), ("biXPelsPerMeter", wintypes.LONG),
                ("biYPelsPerMeter", wintypes.LONG), ("biClrUsed", wintypes.DWORD),
                ("biClrImportant", wintypes.DWORD)]


class _Captura:

    def __init__(self, hwnd):
        u, g = ctypes.windll.user32, ctypes.windll.gdi32
        for f, res, args in (
                (u.GetDC, wintypes.HDC, [wintypes.HWND]),
                (u.ReleaseDC, ctypes.c_int, [wintypes.HWND, wintypes.HDC]),
                (u.PrintWindow, wintypes.BOOL, [wintypes.HWND, wintypes.HDC, wintypes.UINT]),
                (g.CreateCompatibleDC, wintypes.HDC, [wintypes.HDC]),
                (g.CreateCompatibleBitmap, wintypes.HBITMAP,
                 [wintypes.HDC, ctypes.c_int, ctypes.c_int]),
                (g.SelectObject, wintypes.HGDIOBJ, [wintypes.HDC, wintypes.HGDIOBJ]),
                (g.DeleteObject, wintypes.BOOL, [wintypes.HGDIOBJ]),
                (g.DeleteDC, wintypes.BOOL, [wintypes.HDC]),
                (g.GetDIBits, ctypes.c_int, [wintypes.HDC, wintypes.HBITMAP, wintypes.UINT,
                                             wintypes.UINT, ctypes.c_void_p, ctypes.c_void_p,
                                             wintypes.UINT])):
            f.restype, f.argtypes = res, args
        self.u, self.g, self.hwnd = u, g, hwnd
        r = wintypes.RECT()
        u.GetClientRect(hwnd, ctypes.byref(r))
        self.ancho, self.alto = r.right - r.left, r.bottom - r.top
        if self.ancho < 2 or self.alto < 2:
            raise RuntimeError("la ventana está minimizada")
        dc = u.GetDC(hwnd)
        self.mem = g.CreateCompatibleDC(dc)
        self.bmp = g.CreateCompatibleBitmap(dc, self.ancho, self.alto)
        u.ReleaseDC(hwnd, dc)
        self.info = _BITMAPINFOHEADER(ctypes.sizeof(_BITMAPINFOHEADER), self.ancho,
                                      -self.alto, 1, 32, 0, 0, 0, 0, 0, 0)
        self.bufer = ctypes.create_string_buffer(self.ancho * self.alto * 4)

    def cuadro(self):
        viejo = self.g.SelectObject(self.mem, self.bmp)
        ok = self.u.PrintWindow(self.hwnd, self.mem, PW_CLIENTONLY | PW_RENDERFULLCONTENT)
        self.g.SelectObject(self.mem, viejo)
        if not ok:
            return None
        self.g.GetDIBits(self.mem, self.bmp, 0, self.alto, self.bufer,
                         ctypes.byref(self.info), 0)
        return self.bufer.raw

    def cerrar(self):
        self.g.DeleteObject(self.bmp)
        self.g.DeleteDC(self.mem)


class Grabador:
    def __init__(self, raiz):
        self.raiz = raiz
        self.archivo = None
        self.error = None
        self.inicio = 0.0
        self._parar = threading.Event()
        self._sin_captura = threading.Event()
        self._hilo = None

    @property
    def grabando(self):
        return self._hilo is not None and self._hilo.is_alive() and not self._parar.is_set()

    @property
    def ocupado(self):
        return self._hilo is not None and self._hilo.is_alive()

    def iniciar(self):
        exe = ruta_ffmpeg()
        if not exe:
            raise RuntimeError("falta ffmpeg: ejecuta  python -m pip install imageio-ffmpeg")
        self.raiz.update_idletasks()
        cap = _Captura(int(self.raiz.wm_frame(), 16))
        os.makedirs(CARPETA_GRABACIONES, exist_ok=True)
        sello = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        self.archivo = os.path.join(CARPETA_GRABACIONES, f"grabacion_{sello}.mp4")
        cmd = [exe, "-y", "-loglevel", "error",
               "-f", "rawvideo", "-pix_fmt", "bgra", "-s", f"{cap.ancho}x{cap.alto}",
               "-framerate", str(FPS), "-i", "-",
               "-vf", "crop=trunc(iw/2)*2:trunc(ih/2)*2",
               "-c:v", "libx264", "-preset", "fast", "-crf", str(CRF), "-tune", "animation",
               "-pix_fmt", "yuv420p", "-movflags", "+faststart", self.archivo]
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
                                stderr=subprocess.PIPE,
                                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        self.error = None
        self._parar.clear()
        self._sin_captura.clear()
        self.inicio = time.perf_counter()
        self._hilo = threading.Thread(target=self._bucle, args=(cap, proc), daemon=False)
        self._hilo.start()

    def _bucle(self, cap, proc):
        escritos = 0
        datos = None
        try:
            while not self._parar.is_set():
                datos = cap.cuadro()
                if datos is None:
                    break
                debidos = int((time.perf_counter() - self.inicio) * FPS) + 1 - escritos
                for _ in range(max(debidos, 0)):
                    proc.stdin.write(datos)
                    escritos += 1
                espera = self.inicio + escritos / FPS - time.perf_counter()
                if espera > 0:
                    self._parar.wait(espera)
            if datos is not None:
                for _ in range(int((time.perf_counter() - self.inicio) * FPS) + 1 - escritos):
                    proc.stdin.write(datos)
                    escritos += 1
        except OSError:
            pass
        finally:
            self._sin_captura.set()
            cap.cerrar()
            try:
                proc.stdin.close()
            except OSError:
                pass
            err = proc.stderr.read().decode("utf-8", "replace").strip()
            if proc.wait() != 0 or escritos == 0:
                self.error = err or "ffmpeg no pudo crear el video"

    def detener(self, esperar=False):
        self._parar.set()
        if esperar and self._hilo is not None:
            limite = time.perf_counter() + 3
            while not self._sin_captura.is_set() and time.perf_counter() < limite:
                try:
                    self.raiz.update()
                except tk.TclError:
                    break
                time.sleep(0.01)


class BotonGrabar:

    def __init__(self, padre, raiz, avisar=None, fuente=("Segoe UI", 9, "bold")):
        self.raiz = raiz
        self.avisar = avisar or (lambda texto, nivel="info": print(texto, flush=True))
        self.grabador = Grabador(raiz)
        self._sesion = False
        self.boton = tk.Button(padre, command=self.alternar, fg="#111", font=fuente,
                               relief="flat", bd=0, padx=8, pady=3, cursor="hand2",
                               takefocus=0)
        self._estilo(False)

    def pack(self, **kw):
        self.boton.pack(**kw)
        return self

    def _estilo(self, grabando, texto=None):
        color = "#ef5350" if grabando else "#ffab91"
        self.boton.configure(text=texto or ("⏹ Stop" if grabando else "⏺ Grabar pantalla"),
                             bg=color, activebackground=color)

    def alternar(self):
        g = self.grabador
        if g.grabando:
            g.detener()
            self._guardando()
            return
        if g.ocupado:
            return
        try:
            g.iniciar()
        except Exception as e:
            self.avisar(f"No se pudo grabar: {e}", "peligro")
            return
        self._sesion = True
        self.avisar("Grabando la pantalla… (pulsa ⏹ Stop para terminar)", "info")
        self._reloj()

    def _reloj(self):
        g = self.grabador
        if g.grabando:
            s = int(time.perf_counter() - g.inicio)
            self._estilo(True, f"⏹ Stop  ● {s // 60:02d}:{s % 60:02d}")
            self.raiz.after(500, self._reloj)
        else:
            self._guardando()

    def _guardando(self):
        if not self._sesion:
            return
        self._sesion = False
        self._estilo(False, "Guardando…")
        self.boton.configure(state="disabled")
        self._esperar_guardado()

    def _esperar_guardado(self):
        g = self.grabador
        if g.ocupado:
            self.raiz.after(150, self._esperar_guardado)
            return
        self.boton.configure(state="normal")
        self._estilo(False)
        if g.error:
            self.avisar(f"Error al guardar el video: {g.error}", "peligro")
        else:
            self.avisar(f"Video guardado: {g.archivo}", "exito")

    def cerrar(self):
        self.grabador.detener(esperar=True)


class GrabadorPygame:

    def __init__(self):
        self.archivo = None
        self.error = None
        self.inicio = 0.0
        self.mensaje = ("", 0.0)
        self._ultimo = None
        self._t_cuadro = 0.0
        self._parar = threading.Event()
        self._hilo = None
        self._guardando = False

    @property
    def grabando(self):
        return self._hilo is not None and self._hilo.is_alive() and not self._parar.is_set()

    @property
    def ocupado(self):
        return self._hilo is not None and self._hilo.is_alive()

    def _avisar(self, texto):
        print(texto, flush=True)
        self.mensaje = (texto, time.perf_counter())

    def alternar(self, superficie):
        if self.grabando:
            self._parar.set()
            self._guardando = True
            return
        if self.ocupado:
            return
        try:
            self._iniciar(superficie.get_size())
        except Exception as e:
            self._avisar(f"No se pudo grabar: {e}")
            return
        self.cuadro(superficie)
        self._avisar("Grabando la pantalla… (pulsa Stop para terminar)")

    def _iniciar(self, tam):
        exe = ruta_ffmpeg()
        if not exe:
            raise RuntimeError("falta ffmpeg: ejecuta  python -m pip install imageio-ffmpeg")
        os.makedirs(CARPETA_GRABACIONES, exist_ok=True)
        sello = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        self.archivo = os.path.join(CARPETA_GRABACIONES, f"grabacion_{sello}.mp4")
        cmd = [exe, "-y", "-loglevel", "error",
               "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{tam[0]}x{tam[1]}",
               "-framerate", str(FPS), "-i", "-",
               "-vf", "crop=trunc(iw/2)*2:trunc(ih/2)*2",
               "-c:v", "libx264", "-preset", "fast", "-crf", str(CRF), "-tune", "animation",
               "-pix_fmt", "yuv420p", "-movflags", "+faststart", self.archivo]
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
                                stderr=subprocess.PIPE,
                                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        self.error = None
        self._ultimo = None
        self._t_cuadro = 0.0
        self._guardando = False
        self._parar.clear()
        self.inicio = time.perf_counter()
        self._hilo = threading.Thread(target=self._bucle, args=(proc,), daemon=False)
        self._hilo.start()

    def cuadro(self, superficie):
        if self.grabando:
            ahora = time.perf_counter()
            if self._ultimo is None or ahora - self._t_cuadro >= 0.9 / FPS:
                import pygame
                self._ultimo = pygame.image.tobytes(superficie, "RGB")
                self._t_cuadro = ahora
        elif self._guardando and not self.ocupado:
            self._guardando = False
            if self.error:
                self._avisar(f"Error al guardar el video: {self.error}")
            else:
                self._avisar(f"Video guardado: grabaciones\\{os.path.basename(self.archivo)}")

    def _bucle(self, proc):
        escritos = 0
        datos = None
        try:
            while not self._parar.is_set():
                datos = self._ultimo
                if datos is None:
                    self._parar.wait(0.01)
                    continue
                debidos = int((time.perf_counter() - self.inicio) * FPS) + 1 - escritos
                for _ in range(max(debidos, 0)):
                    proc.stdin.write(datos)
                    escritos += 1
                espera = self.inicio + escritos / FPS - time.perf_counter()
                if espera > 0:
                    self._parar.wait(espera)
            if datos is not None:
                for _ in range(int((time.perf_counter() - self.inicio) * FPS) + 1 - escritos):
                    proc.stdin.write(datos)
                    escritos += 1
        except OSError:
            pass
        finally:
            try:
                proc.stdin.close()
            except OSError:
                pass
            err = proc.stderr.read().decode("utf-8", "replace").strip()
            if proc.wait() != 0 or escritos == 0:
                self.error = err or "ffmpeg no pudo crear el video"

    def texto(self):
        if self.grabando:
            s = int(time.perf_counter() - self.inicio)
            return f"Stop  {s // 60:02d}:{s % 60:02d}"
        return "Guardando…" if self.ocupado else "Grabar pantalla"

    def cerrar(self):
        self._parar.set()
        if self._hilo is not None:
            self._hilo.join(10)
