from __future__ import annotations

import argparse
import sys
from pathlib import Path

import gradio as gr
import numpy as np
import torch


RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "programa"))

from comun import NOMBRES_CLASES, cargar_modelo, leer_imagenes
from inferencia import analizar_estudio

AVISO = (
    "**Herramienta de investigación – no sustituye el juicio clínico.** "
    "El modelo se entrenó con 55 pacientes adultos con obesidad grave, adquiridos con un solo equipo "
    "(GE Vivid E9, sonda sectorial de 2.5 MHz) y con biopsia como referencia. Su desempeño en otros "
    "equipos, protocolos o poblaciones no ha sido validado. Use imágenes B-mode que incluyan "
    "parénquima hepático y, de preferencia, la corteza del riñón derecho."
)

COLOR = {"S0": "#2e7d32", "S1": "#f9a825", "S2": "#ef6c00", "S3": "#c62828"}


def crear_interfaz(ruta_modelo: Path):
    disp = "cuda" if torch.cuda.is_available() else "cpu"
    modelo, cfg = cargar_modelo(ruta_modelo, disp)
    desempeno = cfg.get("desempeno_validacion_cruzada_paciente", {})

    def analizar(archivos, mostrar_mapas):
        if not archivos:
            return "Suba al menos una imagen del estudio.", {}, [], ""
        imagenes, nombres, errores = [], [], []
        for a in archivos:
            ruta = Path(a if isinstance(a, str) else a.name)
            try:
                cuadros = leer_imagenes(ruta)
                imagenes += cuadros
                nombres += [f"{ruta.name}" + (f" [{i + 1}]" if len(cuadros) > 1 else "") for i in range(len(cuadros))]
            except Exception as e:
                errores.append(f"{ruta.name}: {e}")
        if not imagenes:
            return "No se pudo leer ninguna imagen.\n\n" + "\n".join(errores), {}, [], ""
        if len(imagenes) > 60:
            paso = len(imagenes) / 60
            sel = [int(i * paso) for i in range(60)]
            imagenes, nombres = [imagenes[i] for i in sel], [nombres[i] for i in sel]

        r = analizar_estudio(modelo, cfg, imagenes, con_mapas=mostrar_mapas, dispositivo=disp)
        c = r["clase"]
        texto = (
            f"<div style='padding:14px;border-radius:10px;border-left:8px solid {COLOR[c]};"
            f"background:rgba(127,127,127,.08)'>"
            f"<h2 style='margin:0;color:{COLOR[c]}'>{r['diagnostico']}</h2>"
            f"<p style='margin:6px 0 0'>Probabilidad de hígado graso (S1-S3): "
            f"<b>{r['p_higado_graso']:.0%}</b> · imágenes analizadas: <b>{len(imagenes)}</b> · "
            f"acuerdo entre imágenes: <b>{r['acuerdo_entre_imagenes']:.0%}</b></p></div>"
        )
        if r["acuerdo_entre_imagenes"] < 0.7:
            texto += ("<p>⚠️ Las imágenes discrepan entre sí; revise su calidad o añada más cortes "
                      "del parénquima hepático.</p>")
        if errores:
            texto += "<p>Archivos no leídos: " + "; ".join(errores) + "</p>"
        etiquetas = {NOMBRES_CLASES[k]: v for k, v in r["probabilidades"].items()}
        galeria = [(m, f"{n} → {c_img}") for m, n, c_img in zip(r["mapas"], nombres, r["clases_por_imagen"])]
        detalle = "| Imagen | " + " | ".join(cfg["clases"]) + " |\n|---|" + "---|" * len(cfg["clases"]) + "\n"
        detalle += "\n".join(f"| {n} | " + " | ".join(f"{v:.2f}" for v in p) + " |"
                             for n, p in zip(nombres, r["probabilidades_por_imagen"]))
        return texto, etiquetas, galeria, detalle

    with gr.Blocks(title="IA – Hígado graso por ecografía", theme=gr.themes.Soft()) as demo:
        gr.Markdown("# Detección y gradación de hígado graso en ecografía B-mode")
        gr.Markdown(AVISO)
        if desempeno:
            gr.Markdown(
                f"Desempeño en validación cruzada por paciente: AUC {desempeno.get('auc_graso', float('nan')):.3f}; "
                f"sensibilidad {desempeno.get('sensibilidad_graso', float('nan')):.2f}; "
                f"especificidad {desempeno.get('especificidad_graso', float('nan')):.2f}; "
                f"exactitud del grado {desempeno.get('exactitud_grado', float('nan')):.2f}.")
        with gr.Row():
            with gr.Column(scale=1):
                archivos = gr.File(label="Imágenes del estudio (un solo paciente)", file_count="multiple",
                                   file_types=["image", ".dcm", ".dicom"])
                mapas = gr.Checkbox(value=True, label="Mostrar mapas de calor (Grad-CAM)")
                boton = gr.Button("Analizar estudio", variant="primary")
            with gr.Column(scale=1):
                salida = gr.HTML()
                probs = gr.Label(label="Probabilidad por grado (promedio del estudio)", num_top_classes=4)
        galeria = gr.Gallery(label="Regiones que más influyeron en la decisión", columns=4, height="auto")
        with gr.Accordion("Detalle por imagen", open=False):
            tabla = gr.Markdown()
        boton.click(analizar, [archivos, mapas], [salida, probs, galeria, tabla])
    return demo


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--modelo", type=Path, default=RAIZ / "modelos" / "modelo_higado_graso.pt")
    ap.add_argument("--puerto", type=int, default=7860)
    ap.add_argument("--compartir", action="store_true")
    a = ap.parse_args()
    if not a.modelo.exists():
        raise SystemExit(f"No existe {a.modelo}. Primero entrene el modelo con entrenar.py o con IA_Higado_Graso.py.")
    crear_interfaz(a.modelo).launch(server_port=a.puerto, share=a.compartir)
