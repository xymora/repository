from __future__ import annotations

import base64
import csv
import io
import os
import queue
import subprocess
import sys
import threading
import webbrowser
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from PIL import Image, ImageTk

CODIGO = Path(__file__).resolve().parent
RAIZ = CODIGO.parent
os.chdir(RAIZ)
sys.path.insert(0, str(CODIGO))

MODELO_POR_DEFECTO = RAIZ / "modelos" / "modelo_higado_graso.pt"
EXTENSIONES = (".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff", ".dcm", ".dicom")
COLOR = {"S0": "#2e7d32", "S1": "#f9a825", "S2": "#ef6c00", "S3": "#c62828"}
PCT_MEDIO = {"S0": 2.5, "S1": 19.0, "S2": 50.0, "S3": 83.0}
AVISO = ("Herramienta de investigación: no sustituye el juicio clínico. Entrenada con 55 pacientes adultos con "
         "obesidad grave (un solo equipo, GE Vivid E9). Use imágenes B-mode del parénquima hepático, de "
         "preferencia con la corteza del riñón derecho.")


class Aplicacion(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("IA – Hígado graso por ecografía")
        self.geometry("1100x760")
        self.minsize(900, 620)
        self.modelo = None
        self.cfg = None
        self.ruta_modelo = tk.StringVar(value=str(MODELO_POR_DEFECTO))
        self.archivos: list[Path] = []
        self.resultado = None
        self.miniaturas = []
        self.cola = queue.Queue()
        self.proceso = None

        estilo = ttk.Style(self)
        if "vista" in estilo.theme_names():
            estilo.theme_use("vista")
        estilo.configure("Grande.TButton", font=("Segoe UI", 11, "bold"), padding=8)
        estilo.configure("TLabel", font=("Segoe UI", 10))

        pestanas = ttk.Notebook(self)
        pestanas.pack(fill="both", expand=True, padx=8, pady=8)
        self.p_diag = ttk.Frame(pestanas, padding=10)
        self.p_ent = ttk.Frame(pestanas, padding=10)
        self.p_ayuda = ttk.Frame(pestanas, padding=10)
        pestanas.add(self.p_diag, text="  1. Diagnóstico  ")
        pestanas.add(self.p_ent, text="  2. Entrenar modelo  ")
        pestanas.add(self.p_ayuda, text="  Ayuda  ")
        self._pestana_diagnostico()
        self._pestana_entrenamiento()
        self._pestana_ayuda()
        self.after(150, self._leer_cola)

    def _pestana_diagnostico(self):
        f = self.p_diag
        ttk.Label(f, text=AVISO, wraplength=1040, foreground="#555").pack(anchor="w", pady=(0, 8))

        fila = ttk.Frame(f)
        fila.pack(fill="x")
        ttk.Button(fila, text="Elegir imágenes…", style="Grande.TButton", command=self._elegir_imagenes).pack(side="left")
        ttk.Button(fila, text="Elegir carpeta del estudio…", style="Grande.TButton",
                   command=self._elegir_carpeta).pack(side="left", padx=6)
        ttk.Button(fila, text="Limpiar", command=self._limpiar).pack(side="left", padx=6)
        self.mapas = tk.BooleanVar(value=True)
        ttk.Checkbutton(fila, text="Mostrar mapas de calor", variable=self.mapas).pack(side="left", padx=12)
        self.b_analizar = ttk.Button(fila, text="ANALIZAR", style="Grande.TButton", command=self._analizar)
        self.b_analizar.pack(side="right")

        self.l_archivos = ttk.Label(f, text="Ninguna imagen seleccionada. Todas las imágenes deben ser del MISMO paciente.")
        self.l_archivos.pack(anchor="w", pady=6)

        cuerpo = ttk.Frame(f)
        cuerpo.pack(fill="both", expand=True)
        izq = ttk.Frame(cuerpo, width=360)
        izq.pack(side="left", fill="y", padx=(0, 10))
        izq.pack_propagate(False)
        self.l_diag = tk.Label(izq, text="", font=("Segoe UI", 15, "bold"), wraplength=340, justify="left")
        self.l_diag.pack(anchor="w", pady=(4, 6))
        self.l_detalle = ttk.Label(izq, text="", wraplength=340, justify="left")
        self.l_detalle.pack(anchor="w")
        self.barras, self.etiquetas = {}, {}
        for c in ["S0", "S1", "S2", "S3"]:
            self.etiquetas[c] = ttk.Label(izq, text=c)
            self.etiquetas[c].pack(anchor="w", pady=(8, 0))
            b = ttk.Progressbar(izq, length=330, maximum=100)
            b.pack(anchor="w")
            self.barras[c] = b
        self.b_guardar = ttk.Button(izq, text="Guardar reporte (HTML para imprimir)", command=self._guardar_reporte,
                                    state="disabled")
        self.b_guardar.pack(anchor="w", pady=16)

        der = ttk.Frame(cuerpo)
        der.pack(side="left", fill="both", expand=True)
        self.lienzo = tk.Canvas(der, background="#fafafa", highlightthickness=0)
        barra = ttk.Scrollbar(der, orient="vertical", command=self.lienzo.yview)
        self.galeria = ttk.Frame(self.lienzo)
        self.galeria.bind("<Configure>", lambda e: self.lienzo.configure(scrollregion=self.lienzo.bbox("all")))
        self.lienzo.create_window((0, 0), window=self.galeria, anchor="nw")
        self.lienzo.configure(yscrollcommand=barra.set)
        self.lienzo.pack(side="left", fill="both", expand=True)
        barra.pack(side="right", fill="y")

        pie = ttk.Frame(f)
        pie.pack(fill="x", pady=(6, 0))
        ttk.Label(pie, text="Modelo:").pack(side="left")
        ttk.Entry(pie, textvariable=self.ruta_modelo, width=90).pack(side="left", padx=4)
        ttk.Button(pie, text="Cambiar…", command=self._elegir_modelo).pack(side="left")

    def _elegir_imagenes(self):
        rutas = filedialog.askopenfilenames(title="Imágenes del estudio (un solo paciente)",
                                            filetypes=[("Imágenes y DICOM", " ".join(f"*{e}" for e in EXTENSIONES)),
                                                       ("Todos los archivos", "*.*")])
        if rutas:
            self.archivos += [Path(r) for r in rutas]
            self._mostrar_archivos()

    def _elegir_carpeta(self):
        d = filedialog.askdirectory(title="Carpeta con las imágenes de un paciente")
        if d:
            self.archivos += sorted(p for p in Path(d).iterdir() if p.suffix.lower() in EXTENSIONES)
            self._mostrar_archivos()

    def _mostrar_archivos(self):
        n = len(self.archivos)
        nombres = ", ".join(p.name for p in self.archivos[:6]) + (" …" if n > 6 else "")
        self.l_archivos.config(text=f"{n} archivo(s): {nombres}")

    def _limpiar(self):
        self.archivos, self.resultado = [], None
        self.l_archivos.config(text="Ninguna imagen seleccionada. Todas las imágenes deben ser del MISMO paciente.")
        self.l_diag.config(text="")
        self.l_detalle.config(text="")
        for k, b in self.barras.items():
            b["value"] = 0
            self.etiquetas[k].config(text=k)
        for w in self.galeria.winfo_children():
            w.destroy()
        self.b_guardar.config(state="disabled")

    def _elegir_modelo(self):
        r = filedialog.askopenfilename(title="Archivo del modelo", filetypes=[("Modelo PyTorch", "*.pt")])
        if r:
            self.ruta_modelo.set(r)
            self.modelo = None

    def _analizar(self):
        if not self.archivos:
            messagebox.showinfo("Faltan imágenes", "Primero elija las imágenes o la carpeta del estudio.")
            return
        if not Path(self.ruta_modelo.get()).exists():
            messagebox.showwarning("Sin modelo", "No se encontró el modelo entrenado.\n\n"
                                   "Vaya a la pestaña «2. Entrenar modelo» o elija un archivo .pt con «Cambiar…».")
            return
        self.b_analizar.config(state="disabled", text="Analizando…")
        self.l_diag.config(text="Analizando, espere…", fg="#333")
        threading.Thread(target=self._trabajo_analisis, args=(list(self.archivos), self.mapas.get()), daemon=True).start()

    def _trabajo_analisis(self, archivos, con_mapas):
        try:
            import torch
            from comun import cargar_modelo, leer_imagenes
            from inferencia import analizar_estudio

            disp = "cuda" if torch.cuda.is_available() else "cpu"
            if self.modelo is None:
                self.modelo, self.cfg = cargar_modelo(self.ruta_modelo.get(), disp)
            imagenes, nombres, errores = [], [], []
            for ruta in archivos:
                try:
                    cuadros = leer_imagenes(ruta)
                    imagenes += cuadros
                    nombres += [ruta.name + (f" [{i + 1}]" if len(cuadros) > 1 else "") for i in range(len(cuadros))]
                except Exception as e:
                    errores.append(f"{ruta.name}: {e}")
            if not imagenes:
                raise RuntimeError("No se pudo leer ninguna imagen.\n" + "\n".join(errores))
            if len(imagenes) > 60:
                sel = [int(i * len(imagenes) / 60) for i in range(60)]
                imagenes, nombres = [imagenes[i] for i in sel], [nombres[i] for i in sel]
            r = analizar_estudio(self.modelo, self.cfg, imagenes, con_mapas=con_mapas,
                                 dispositivo=next(self.modelo.parameters()).device)
            r["nombres"], r["errores"], r["originales"] = nombres, errores, imagenes
            self.cola.put(("resultado", r))
        except Exception as e:
            self.cola.put(("error", str(e)))

    def _pintar_resultado(self, r):
        self.resultado = r
        c = r["clase"]
        self.l_diag.config(text=r["diagnostico"], fg=COLOR[c])
        texto = (f"Probabilidad de hígado graso (S1-S3): {r['p_higado_graso']:.0%}\n"
                 f"Imágenes analizadas: {len(r['nombres'])}\n"
                 f"Acuerdo entre imágenes: {r['acuerdo_entre_imagenes']:.0%}")
        if r["acuerdo_entre_imagenes"] < 0.7:
            texto += "\n\n⚠ Las imágenes discrepan entre sí: revise su calidad o agregue más cortes del hígado."
        if r["errores"]:
            texto += "\n\nNo se pudieron leer: " + "; ".join(r["errores"])
        self.l_detalle.config(text=texto)
        for k, b in self.barras.items():
            b["value"] = 100 * r["probabilidades"].get(k, 0)
            self.etiquetas[k].config(text=f"{k}: {r['probabilidades'].get(k, 0):.1%}")
        for w in self.galeria.winfo_children():
            w.destroy()
        self.miniaturas = []
        fuentes = r["mapas"] or r["originales"]
        for i, (img, nombre, clase) in enumerate(zip(fuentes, r["nombres"], r["clases_por_imagen"])):
            im = Image.fromarray(img)
            im.thumbnail((230, 160))
            foto = ImageTk.PhotoImage(im)
            self.miniaturas.append(foto)
            celda = ttk.Frame(self.galeria, padding=4)
            celda.grid(row=i // 3, column=i % 3, sticky="n")
            tk.Label(celda, image=foto).pack()
            tk.Label(celda, text=f"{nombre}\n→ {clase}", fg=COLOR[clase], font=("Segoe UI", 9)).pack()
        self.b_guardar.config(state="normal")

    def _guardar_reporte(self):
        r = self.resultado
        if not r:
            return
        ruta = filedialog.asksaveasfilename(title="Guardar reporte", defaultextension=".html",
                                            initialfile=f"reporte_higado_{datetime.now():%Y%m%d_%H%M}.html",
                                            filetypes=[("Página web", "*.html")])
        if not ruta:
            return

        def b64(arr):
            buf = io.BytesIO()
            Image.fromarray(arr).save(buf, format="PNG")
            return base64.b64encode(buf.getvalue()).decode()

        filas = "".join(f"<tr><td>{n}</td>" + "".join(f"<td>{v:.2f}</td>" for v in p) + f"<td><b>{c}</b></td></tr>"
                        for n, p, c in zip(r["nombres"], r["probabilidades_por_imagen"], r["clases_por_imagen"]))
        fotos = "".join(f"<figure><img src='data:image/png;base64,{b64(m)}'><figcaption>{n} → {c}</figcaption></figure>"
                        for m, n, c in zip(r["mapas"] or r["originales"], r["nombres"], r["clases_por_imagen"]))
        probs = "".join(f"<li>{k}: {v:.1%}</li>" for k, v in r["probabilidades"].items())
        html = f"""<!doctype html><html lang="es"><head><meta charset="utf-8"><title>Reporte hígado graso</title>
<style>body{{font-family:Segoe UI,Arial,sans-serif;margin:24px;color:#222}}h1{{color:{COLOR[r['clase']]}}}
table{{border-collapse:collapse}}td,th{{border:1px solid #ccc;padding:4px 8px;text-align:center}}
figure{{display:inline-block;margin:6px;text-align:center;font-size:12px}}img{{max-width:300px}}
.aviso{{color:#666;font-size:12px}}</style></head><body>
<p>Fecha: {datetime.now():%d/%m/%Y %H:%M} · Paciente: ____________________ · Médico: ____________________</p>
<h1>{r['diagnostico']}</h1>
<p>Probabilidad de hígado graso (S1-S3): <b>{r['p_higado_graso']:.0%}</b> · Imágenes: {len(r['nombres'])} ·
Acuerdo entre imágenes: {r['acuerdo_entre_imagenes']:.0%}</p><ul>{probs}</ul>
<table><tr><th>Imagen</th><th>S0</th><th>S1</th><th>S2</th><th>S3</th><th>Grado</th></tr>{filas}</table>
<h3>Mapas de calor</h3>{fotos}<p class="aviso">{AVISO}</p></body></html>"""
        Path(ruta).write_text(html, encoding="utf-8")
        webbrowser.open(Path(ruta).as_uri())

    def _pestana_entrenamiento(self):
        f = self.p_ent
        ttk.Label(f, wraplength=1040, justify="left", text=(
            "Entrena (o reentrena) la IA. La carpeta de datos debe contener una subcarpeta «imagenes» con las "
            "carpetas S0, S1, S2 y S3, y dentro de cada una las imágenes de cada paciente nombradas "
            "PACIENTE_cuadro.png (por ejemplo P07_c03.png). Si no existe el archivo metadatos.csv, el programa lo "
            "crea solo.\n\nEl entrenamiento completo son 150 épocas en total: 5 modelos de validación cruzada × 25 "
            "épocas + 1 modelo final × 25 épocas. Deje «Épocas por modelo» en 25 (configuración del artículo); más "
            "épocas no mejoran el modelo, lo sobreajustan. Con tarjeta gráfica NVIDIA tarda unos 90 minutos; sin "
            "ella, varias horas.")).pack(anchor="w")

        opciones = ttk.Frame(f)
        opciones.pack(fill="x", pady=10)
        self.carpeta_datos = tk.StringVar(value=str(RAIZ / "datos"))
        self.epocas = tk.IntVar(value=25)
        self.rapido = tk.BooleanVar(value=False)
        ttk.Label(opciones, text="Carpeta de datos:").grid(row=0, column=0, sticky="w")
        ttk.Entry(opciones, textvariable=self.carpeta_datos, width=80).grid(row=0, column=1, padx=4)
        ttk.Button(opciones, text="Cambiar…",
                   command=lambda: self.carpeta_datos.set(filedialog.askdirectory() or self.carpeta_datos.get())
                   ).grid(row=0, column=2)
        ttk.Label(opciones, text="Épocas por modelo:").grid(row=1, column=0, sticky="w", pady=6)
        fila_epocas = ttk.Frame(opciones)
        fila_epocas.grid(row=1, column=1, sticky="w", padx=4)
        ttk.Spinbox(fila_epocas, from_=2, to=200, textvariable=self.epocas, width=8).pack(side="left")
        self.l_total = ttk.Label(fila_epocas, text="")
        self.l_total.pack(side="left", padx=10)
        ttk.Checkbutton(opciones, text="Prueba rápida (2 épocas por modelo, solo para comprobar que todo funciona)",
                        variable=self.rapido).grid(row=2, column=1, sticky="w", padx=4)
        self.epocas.trace_add("write", lambda *_: self._mostrar_total())
        self.rapido.trace_add("write", lambda *_: self._mostrar_total())
        self._mostrar_total()

        botones = ttk.Frame(f)
        botones.pack(fill="x")
        self.b_descargar = ttk.Button(botones, text="Descargar datos públicos (Zenodo)", command=self._descargar)
        self.b_descargar.pack(side="left")
        self.b_entrenar = ttk.Button(botones, text="INICIAR ENTRENAMIENTO", style="Grande.TButton",
                                     command=self._entrenar)
        self.b_entrenar.pack(side="left", padx=8)
        self.b_detener = ttk.Button(botones, text="Detener", command=self._detener, state="disabled")
        self.b_detener.pack(side="left")
        ttk.Button(botones, text="Abrir carpeta de resultados",
                   command=lambda: os.startfile(RAIZ / "resultados") if (RAIZ / "resultados").exists() else None
                   ).pack(side="right")

        self.progreso = ttk.Progressbar(f, mode="indeterminate")
        self.progreso.pack(fill="x", pady=8)
        self.registro = tk.Text(f, height=24, font=("Consolas", 9), background="#111", foreground="#ddd")
        self.registro.pack(fill="both", expand=True)

    def _preparar_metadatos(self, datos: Path) -> bool:
        if (datos / "metadatos.csv").exists():
            return True
        filas = []
        for grado in ["S0", "S1", "S2", "S3"]:
            for img in sorted((datos / "imagenes" / grado).glob("*")):
                if img.suffix.lower() in EXTENSIONES[:-2]:
                    filas.append({"ruta": img.relative_to(datos).as_posix(), "paciente": img.stem.split("_")[0],
                                  "cuadro": len(filas) + 1, "esteatosis_pct": PCT_MEDIO[grado], "grado": grado,
                                  "higado_graso": int(grado != "S0")})
        if not filas:
            messagebox.showerror("Sin imágenes", f"No hay imágenes en {datos / 'imagenes'}\\S0…S3.")
            return False
        with open(datos / "metadatos.csv", "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=list(filas[0]))
            w.writeheader()
            w.writerows(filas)
        self._escribir(f"Se creó metadatos.csv con {len(filas)} imágenes. Como no hay % de biopsia, se usó el "
                       "valor medio de cada grado (la correlación de Spearman será aproximada).\n")
        return True

    def _ejecutar(self, args):
        self.registro.delete("1.0", "end")
        self.b_entrenar.config(state="disabled")
        self.b_descargar.config(state="disabled")
        self.b_detener.config(state="normal")
        self.progreso.start(12)
        entorno = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUNBUFFERED="1")

        def hilo():
            try:
                self.proceso = subprocess.Popen([sys.executable, *args], cwd=RAIZ, stdout=subprocess.PIPE,
                                                stderr=subprocess.STDOUT, text=True, encoding="utf-8",
                                                errors="replace", env=entorno,
                                                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                for linea in self.proceso.stdout:
                    self.cola.put(("log", linea))
                self.cola.put(("fin", self.proceso.wait()))
            except Exception as e:
                self.cola.put(("log", f"ERROR: {e}\n"))
                self.cola.put(("fin", 1))

        threading.Thread(target=hilo, daemon=True).start()

    def _descargar(self):
        self._ejecutar([str(RAIZ / "extras" / "preparar_datos.py"), "--salida", self.carpeta_datos.get()])

    def _epocas_por_modelo(self):
        if self.rapido.get():
            return 2
        try:
            return int(self.epocas.get())
        except (tk.TclError, ValueError):
            return None

    def _mostrar_total(self):
        e = self._epocas_por_modelo()
        if e is None:
            self.l_total.config(text="escriba un número", foreground="#c62828")
        elif e == 25 or self.rapido.get():
            self.l_total.config(text=f"= {6 * e} épocas en total (5 particiones + modelo final)", foreground="#2e7d32")
        else:
            self.l_total.config(text=f"= {6 * e} épocas en total. Lo recomendado es 25 por modelo (150 en total)",
                                foreground="#ef6c00")

    def _entrenar(self):
        datos = Path(self.carpeta_datos.get())
        e = self._epocas_por_modelo()
        if e is None:
            messagebox.showwarning("Épocas", "Escriba un número de épocas por modelo (recomendado: 25).")
            return
        if not self._preparar_metadatos(datos):
            return
        aviso = "" if e == 25 or self.rapido.get() else (
            f"\n\nAtención: eligió {e} épocas por modelo ({6 * e} en total). La configuración validada del artículo "
            "es 25 por modelo (150 en total).")
        if not messagebox.askyesno("Entrenar", f"Se entrenarán {6 * e} épocas en total (5 modelos de validación × "
                                   f"{e} + modelo final × {e}). Puede tardar horas y reemplaza el modelo y los "
                                   f"resultados actuales.{aviso}\n\n¿Continuar?"):
            return
        args = [str(CODIGO / "entrenar.py"), "--datos", str(datos), "--epocas", str(e),
                "--trabajadores", "0"]
        if self.rapido.get():
            args.append("--rapido")
        self._ejecutar(args)

    def _detener(self):
        if self.proceso and self.proceso.poll() is None:
            self.proceso.terminate()
            self._escribir("\nEntrenamiento detenido por el usuario.\n")

    def _escribir(self, texto):
        self.registro.insert("end", texto)
        self.registro.see("end")

    def _leer_cola(self):
        try:
            while True:
                tipo, dato = self.cola.get_nowait()
                if tipo == "log":
                    self._escribir(dato)
                elif tipo == "fin":
                    self.progreso.stop()
                    self.b_entrenar.config(state="normal")
                    self.b_descargar.config(state="normal")
                    self.b_detener.config(state="disabled")
                    self.modelo = None
                    if dato == 0:
                        messagebox.showinfo("Listo", "Proceso terminado correctamente.")
                    else:
                        messagebox.showwarning("Atención", "El proceso terminó con errores; revise el registro.")
                elif tipo == "resultado":
                    self.b_analizar.config(state="normal", text="ANALIZAR")
                    self._pintar_resultado(dato)
                elif tipo == "error":
                    self.b_analizar.config(state="normal", text="ANALIZAR")
                    self.l_diag.config(text="")
                    messagebox.showerror("Error", dato)
        except queue.Empty:
            pass
        self.after(150, self._leer_cola)

    def _pestana_ayuda(self):
        t = tk.Text(self.p_ayuda, wrap="word", font=("Segoe UI", 10), relief="flat", background="#fcfcfc")
        t.pack(fill="both", expand=True)
        t.insert("1.0", (
            "CÓMO HACER UN DIAGNÓSTICO\n"
            "1. Pestaña «1. Diagnóstico».\n"
            "2. Pulse «Elegir imágenes…» (puede seleccionar una o varias con Ctrl o Shift) o «Elegir carpeta del "
            "estudio…». Formatos: PNG, JPG, BMP, TIFF y DICOM (incluidos cine-loops).\n"
            "3. Todas las imágenes deben ser del MISMO paciente. Con 5-10 cortes del hígado el resultado es más "
            "estable que con una sola imagen.\n"
            "4. Pulse «ANALIZAR». Verá el grado (S0 normal, S1 leve, S2 moderado, S3 grave), la probabilidad de cada "
            "grado y los mapas de calor: las zonas rojas son las que más pesaron en la decisión.\n"
            "5. «Guardar reporte» crea una página que se abre en el navegador y se puede imprimir o guardar en PDF.\n\n"
            "CÓMO ENTRENAR\n"
            "1. Pestaña «2. Entrenar modelo».\n"
            "2. Con los datos incluidos basta pulsar «INICIAR ENTRENAMIENTO». El entrenamiento completo son 150 épocas "
            "en total (5 modelos de validación × 25 + modelo final × 25): deje «Épocas por modelo» en 25. Con tarjeta "
            "NVIDIA tarda unos 90 minutos. Para usar imágenes propias, organícelas "
            "en datos\\imagenes\\S0, S1, S2, S3 según la biopsia y nombre cada archivo PACIENTE_cuadro.png.\n"
            "3. Al terminar, el modelo nuevo queda en modelos\\modelo_higado_graso.pt y las métricas y figuras en la "
            "carpeta resultados.\n\n"
            "INTERPRETACIÓN\n"
            "Si el «acuerdo entre imágenes» es menor de 70 %, las imágenes dan resultados distintos entre sí: revise "
            "su calidad. El resultado es orientativo y no sustituye la valoración médica.\n"))
        t.config(state="disabled")


if __name__ == "__main__":
    Aplicacion().mainloop()
