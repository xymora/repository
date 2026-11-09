from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.metrics import (accuracy_score, cohen_kappa_score, confusion_matrix,
                             f1_score, roc_auc_score, roc_curve)

from comun import CLASES

COLS_P = [f"p_{c}" for c in CLASES]


def agregar_por_paciente(df_img: pd.DataFrame, umbral: float = 0.5) -> pd.DataFrame:
    agg = df_img.groupby("paciente").agg(
        {**{c: "mean" for c in COLS_P}, "y": "first", "esteatosis_pct": "first", "particion": "first"}
    ).reset_index()
    return completar_predicciones(agg, umbral)


def completar_predicciones(df: pd.DataFrame, umbral: float = 0.5) -> pd.DataFrame:
    P = df[COLS_P].to_numpy()
    df = df.copy()
    df["p_graso"] = 1.0 - df["p_S0"]
    graso = df["p_graso"].to_numpy() >= umbral
    df["pred"] = np.where(graso, 1 + P[:, 1:].argmax(1), 0)
    df["grado_esperado"] = P @ np.arange(len(CLASES))
    return df


def _binarias(y_bin, score, umbral):
    pred = (score >= umbral).astype(int)
    tp = int(((pred == 1) & (y_bin == 1)).sum())
    tn = int(((pred == 0) & (y_bin == 0)).sum())
    fp = int(((pred == 1) & (y_bin == 0)).sum())
    fn = int(((pred == 0) & (y_bin == 1)).sum())
    div = lambda a, b: float(a / b) if b else float("nan")
    return {
        "sensibilidad": div(tp, tp + fn), "especificidad": div(tn, tn + fp),
        "vpp": div(tp, tp + fp), "vpn": div(tn, tn + fn),
        "exactitud": div(tp + tn, len(y_bin)), "f1": div(2 * tp, 2 * tp + fp + fn),
        "vp": tp, "vn": tn, "fp": fp, "fn": fn,
    }


def metricas_puntuales(df: pd.DataFrame, umbral: float = 0.5) -> dict:
    y = df["y"].to_numpy().astype(int)
    y_bin = (y > 0).astype(int)
    score = df["p_graso"].to_numpy()
    pred = df["pred"].to_numpy().astype(int)
    P = df[COLS_P].to_numpy()

    m = {"n": int(len(df))}
    m["auc_graso"] = float(roc_auc_score(y_bin, score)) if len(set(y_bin)) == 2 else float("nan")
    m.update({f"{k}_graso": v for k, v in _binarias(y_bin, score, umbral).items()})
    etiquetas = list(range(len(CLASES)))
    m["exactitud_grado"] = float(accuracy_score(y, pred))
    m["f1_macro_grado"] = float(f1_score(y, pred, labels=etiquetas, average="macro", zero_division=0))
    m["kappa_cuadratica_grado"] = float(cohen_kappa_score(y, pred, labels=etiquetas, weights="quadratic"))
    m["exactitud_grado_mas_menos_1"] = float(np.mean(np.abs(y - pred) <= 1))
    for k, c in enumerate(CLASES):
        yk = (y == k).astype(int)
        m[f"auc_{c}_vs_resto"] = float(roc_auc_score(yk, P[:, k])) if 0 < yk.sum() < len(yk) else float("nan")
        m[f"sensibilidad_{c}"] = float(((pred == k) & (y == k)).sum() / yk.sum()) if yk.sum() else float("nan")
    rho, p = spearmanr(df["grado_esperado"], df["esteatosis_pct"])
    m["spearman_rho_vs_biopsia"] = float(rho)
    m["spearman_p"] = float(p)
    return m


def bootstrap_ic(df: pd.DataFrame, umbral: float = 0.5, n: int = 2000, semilla: int = 42,
                 claves=("auc_graso", "sensibilidad_graso", "especificidad_graso", "exactitud_graso",
                         "exactitud_grado", "f1_macro_grado", "kappa_cuadratica_grado",
                         "spearman_rho_vs_biopsia")) -> dict:
    rng = np.random.default_rng(semilla)
    valores = {k: [] for k in claves}
    idx = np.arange(len(df))
    for _ in range(n):
        muestra = df.iloc[rng.choice(idx, size=len(idx), replace=True)]
        if muestra["y"].nunique() < 2:
            continue
        mm = metricas_puntuales(muestra, umbral)
        for k in claves:
            if np.isfinite(mm[k]):
                valores[k].append(mm[k])
    return {k: [float(np.percentile(v, 2.5)), float(np.percentile(v, 97.5))] if v else [float("nan")] * 2
            for k, v in valores.items()}


def matriz_confusion(df: pd.DataFrame) -> np.ndarray:
    return confusion_matrix(df["y"].astype(int), df["pred"].astype(int), labels=list(range(len(CLASES))))


def curva_roc(df: pd.DataFrame):
    y_bin = (df["y"].to_numpy() > 0).astype(int)
    return roc_curve(y_bin, df["p_graso"].to_numpy())


def umbral_youden(df: pd.DataFrame) -> float:
    fpr, tpr, thr = curva_roc(df)
    t = float(thr[int(np.argmax(tpr - fpr))])
    return min(t, 1.0) if np.isfinite(t) else 1.0
