from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch


def caja(ax, x, y, w, h, titulo, texto, color):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.012,rounding_size=0.02",
                                fc=color, ec="#33415c", lw=1))
    ax.text(x + w / 2, y + h - 0.035, titulo, ha="center", va="top", fontsize=8.6, weight="bold", color="#1b263b")
    ax.text(x + w / 2, y + h - 0.085, texto, ha="center", va="top", fontsize=7.4, color="#1b263b", linespacing=1.35)


def flecha(ax, x1, y1, x2, y2):
    ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle="-|>", mutation_scale=12, lw=1.2, color="#33415c"))


def generar(salida: Path = Path(__file__).resolve().parent.parent / "resultados" / "figuras" / "fig1_flujo_metodologico.png"):
    fig, ax = plt.subplots(figsize=(12.5, 6.2), dpi=300)
    ax.set_xlim(-0.01, 1.01)
    ax.set_ylim(0.02, 0.96)
    ax.axis("off")
    az, ve, am, ro = "#dbe9f6", "#e3f1df", "#fdf1d6", "#f8dedd"
    w, h = 0.215, 0.36
    fila_y = 0.56
    xs = [0.01, 0.262, 0.514, 0.766]
    caja(ax, xs[0], fila_y, w, h, "1. Datos", "Byra et al. 2018 (Zenodo, CC BY 4.0)\n55 pacientes con obesidad grave\n"
         "10 cuadros B-mode por paciente\n(550 imágenes, 434 × 636 px)\nReferencia: biopsia hepática\n"
         "Grados NASH-CRN: S0 <5 %,\nS1 5-33 %, S2 34-66 %, S3 >66 %", az)
    caja(ax, xs[1], fila_y, w, h, "2. Preprocesamiento", "Máscara del abanico: se eliminan\nECG, FC, hora, escalas y textos\nEscala de grises → 3 canales\nRedimensión a 256 × 384 px\n"
         "Normalización ImageNet\nAumentos (solo entrenamiento):\nrotación ±8°, traslación 4 %,\n"
         "escala ±8 %, brillo/contraste ±15 %", az)
    caja(ax, xs[2], fila_y, w, h, "3. Modelo", "EfficientNet-B0 preentrenada\n(ImageNet, transferencia)\n"
         "Cabeza: Dropout 0.3 + lineal (4 clases)\nEntropía cruzada ponderada\n(suavizado 0.05)\n"
         "AdamW, LR 3×10⁻⁴, one-cycle\n25 épocas, lote 16, semilla 42", ve)
    caja(ax, xs[3], fila_y, w, h, "4. Validación", "Validación cruzada de 5 particiones\nestratificada y AGRUPADA POR PACIENTE\n"
         "Hiperparámetros fijados a priori\nPredicción por paciente = promedio\nde las probabilidades de sus imágenes\n"
         "IC 95 %: bootstrap por paciente\n(2000 remuestreos)", ve)
    for i in range(3):
        flecha(ax, xs[i] + w + 0.004, fila_y + h / 2, xs[i + 1] - 0.004, fila_y + h / 2)

    h2 = 0.36
    y2 = 0.06
    caja(ax, 0.01, y2, 0.30, h2, "5. Regla de decisión jerárquica",
         "P(hígado graso) = P(S1) + P(S2) + P(S3)\n\nSi P(hígado graso) ≥ 0.5:\n  grado = el más probable entre S1-S3\n"
         "Si no: S0 (sin esteatosis)", am)
    caja(ax, 0.35, y2, 0.30, h2, "6. Métricas (por paciente e imagen)",
         "Detección (S1-S3 vs. S0): AUC-ROC,\nsensibilidad, especificidad, VPP, VPN\n\n"
         "Gradación (S0-S3): exactitud, F1 macro,\nkappa ponderada cuadrática,\nrho de Spearman vs. % de biopsia\n"
         "Explicabilidad: Grad-CAM", am)
    caja(ax, 0.69, y2, 0.30, h2, "7. Modelo final y aplicación",
         "Reentrenamiento con los 55 pacientes\n(mismos hiperparámetros)\n\nAplicación web (Gradio):\n"
         "carga PNG/JPG/DICOM de un estudio →\ndiagnóstico, grado, probabilidades\ny mapas de calor", ro)
    flecha(ax, xs[3] + w / 2, fila_y - 0.006, 0.84, y2 + h2 + 0.006)
    flecha(ax, xs[3] + w / 2 - 0.03, fila_y - 0.006, 0.16, y2 + h2 + 0.006)
    flecha(ax, 0.31 + 0.004, y2 + h2 / 2, 0.35 - 0.004, y2 + h2 / 2)
    salida.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(salida, bbox_inches="tight")
    plt.close(fig)
    return salida


if __name__ == "__main__":
    print(generar())
