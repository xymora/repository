from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from sklearn.metrics import auc as area, roc_curve

from comun import CLASES

ETQ = ["S0", "S1", "S2", "S3"]
COLORES = ["#55A868", "#DDAA33", "#DD8452", "#C44E52"]


def _limpiar(ax):
    ax.spines[["top", "right"]].set_visible(False)


def fig_roc(df_pac, df_img, metr, ic, salida: Path):
    fig, ax = plt.subplots(1, 2, figsize=(10, 4.4), dpi=300)
    for df, estilo, nombre in ((df_pac, "-", "Por paciente"), (df_img, "--", "Por imagen")):
        yb = (df["y"].to_numpy() > 0).astype(int)
        fpr, tpr, _ = roc_curve(yb, df["p_graso"])
        ax[0].plot(fpr, tpr, estilo, lw=2 if estilo == "-" else 1.2,
                   label=f"{nombre}: AUC = {area(fpr, tpr):.3f}", color="#4C72B0" if estilo == "-" else "#8172B3")
    lo, hi = ic["auc_graso"]
    ax[0].plot([0, 1], [0, 1], ":", c="grey", lw=1)
    ax[0].set_title(f"A. Hígado graso (S1-S3) vs. normal (S0)\nAUC paciente IC 95 %: {lo:.3f}-{hi:.3f}",
                    loc="left", fontsize=10)
    for k, c in enumerate(CLASES):
        yk = (df_pac["y"].to_numpy() == k).astype(int)
        if 0 < yk.sum() < len(yk):
            fpr, tpr, _ = roc_curve(yk, df_pac[f"p_{c}"])
            ax[1].plot(fpr, tpr, lw=1.6, color=COLORES[k], label=f"{c} vs. resto: AUC = {area(fpr, tpr):.3f}")
    ax[1].plot([0, 1], [0, 1], ":", c="grey", lw=1)
    ax[1].set_title("B. Cada grado contra el resto (por paciente)", loc="left", fontsize=10)
    for a in ax:
        a.set_xlabel("1 - Especificidad")
        a.set_ylabel("Sensibilidad")
        a.legend(loc="lower right", fontsize=8, frameon=False)
        a.set_aspect("equal")
        _limpiar(a)
    fig.tight_layout()
    fig.savefig(salida)
    plt.close(fig)


def fig_confusion(cm_pac, cm_img, salida: Path):
    fig, ax = plt.subplots(1, 2, figsize=(9.5, 4.2), dpi=300)
    for a, cm, tit in ((ax[0], cm_pac, "A. Por paciente"), (ax[1], cm_img, "B. Por imagen")):
        norm = cm / np.maximum(cm.sum(1, keepdims=True), 1)
        a.imshow(norm, cmap="Blues", vmin=0, vmax=1)
        for i in range(cm.shape[0]):
            for j in range(cm.shape[1]):
                a.text(j, i, f"{cm[i, j]}\n({norm[i, j]:.0%})", ha="center", va="center", fontsize=8,
                       color="white" if norm[i, j] > 0.55 else "black")
        a.set_xticks(range(4), ETQ)
        a.set_yticks(range(4), ETQ)
        a.set_xlabel("Grado predicho por la IA")
        a.set_ylabel("Grado por biopsia")
        a.set_title(tit, loc="left", fontsize=10)
    fig.tight_layout()
    fig.savefig(salida)
    plt.close(fig)


def fig_curvas(historial: list[dict], salida: Path):
    fig, ax = plt.subplots(figsize=(6, 3.6), dpi=300)
    for h in historial:
        ax.plot(range(1, len(h["perdida_entrenamiento"]) + 1), h["perdida_entrenamiento"],
                lw=1, color="#4C72B0", alpha=0.7)
        ax.plot(range(1, len(h["perdida_prueba"]) + 1), h["perdida_prueba"],
                lw=1, color="#C44E52", alpha=0.7, ls="--")
    ax.plot([], [], c="#4C72B0", label="Entrenamiento")
    ax.plot([], [], c="#C44E52", ls="--", label="Partición de prueba (solo monitoreo)")
    ax.set_xlabel("Época")
    ax.set_ylabel("Pérdida (entropía cruzada)")
    ax.legend(frameon=False, fontsize=8)
    _limpiar(ax)
    fig.tight_layout()
    fig.savefig(salida)
    plt.close(fig)


def fig_gradcam(ejemplos: list[dict], salida: Path):
    ejemplos = sorted(ejemplos, key=lambda e: e["grado_real"])
    n = len(ejemplos)
    if n == 0:
        return
    fig, ax = plt.subplots(2, n, figsize=(3.2 * n, 4.6), dpi=300, squeeze=False)
    for j, e in enumerate(ejemplos):
        ax[0, j].imshow(e["gris"], cmap="gray")
        ax[0, j].set_title(f"Biopsia: {e['grado_real']}", fontsize=9)
        ax[1, j].imshow(e["mapa"])
        ax[1, j].set_title(f"IA: {e['grado_pred']} (p = {e['prob']:.2f})", fontsize=9)
        for i in range(2):
            ax[i, j].axis("off")
    fig.text(0.005, 0.74, "B-mode", rotation=90, fontsize=9, va="center")
    fig.text(0.005, 0.27, "Grad-CAM", rotation=90, fontsize=9, va="center")
    fig.tight_layout(rect=(0.015, 0, 1, 1))
    fig.savefig(salida)
    plt.close(fig)
