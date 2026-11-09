from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import torch
from PIL import Image
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.manifold import TSNE
from sklearn.metrics import adjusted_rand_score, normalized_mutual_info_score
from sklearn.preprocessing import StandardScaler


RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "programa"))

from comun import CLASES, construir_modelo, enmascarar_abanico, fijar_semillas, transformaciones

COLORES = ["#55A868", "#DDAA33", "#DD8452", "#C44E52"]


@torch.no_grad()
def extraer(df, raiz, disp, lote=32):
    modelo = construir_modelo("efficientnet_b0", preentrenado=True).eval().to(disp)
    tf = transformaciones(False)
    salidas = []
    for i in range(0, len(df), lote):
        x = torch.stack([tf(Image.fromarray(enmascarar_abanico(np.array(Image.open(raiz / r).convert("L")))))
                         for r in df["ruta"].iloc[i:i + lote]]).to(disp)
        salidas.append(modelo.avgpool(modelo.features(x)).flatten(1).cpu().numpy())
    return np.concatenate(salidas)


def agrupar(z, y, k, semilla):
    etiquetas = KMeans(n_clusters=k, n_init=50, random_state=semilla).fit_predict(z)
    return etiquetas, float(adjusted_rand_score(y, etiquetas)), float(normalized_mutual_info_score(y, etiquetas))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--datos", type=Path, default=RAIZ / "datos")
    ap.add_argument("--resultados", type=Path, default=RAIZ / "resultados")
    ap.add_argument("--semilla", type=int, default=42)
    args = ap.parse_args()
    fijar_semillas(args.semilla)
    disp = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    df = pd.read_csv(args.datos / "metadatos.csv")
    df["y"] = df["grado"].map({c: i for i, c in enumerate(CLASES)})
    emb = extraer(df, args.datos, disp)
    print(f"Características: {emb.shape}")

    pac = df.groupby("paciente").agg(y=("y", "first"), pct=("esteatosis_pct", "first"))
    emb_pac = np.stack([emb[df.paciente.to_numpy() == p].mean(0) for p in pac.index])
    z_pac = StandardScaler().fit_transform(emb_pac)
    pca = PCA(n_components=10, random_state=args.semilla).fit(z_pac)
    zp = pca.transform(z_pac)
    z_img = PCA(n_components=10, random_state=args.semilla).fit_transform(StandardScaler().fit_transform(emb))

    y_pac, y_img = pac["y"].to_numpy(), df["y"].to_numpy()
    c4, ari4, nmi4 = agrupar(zp, y_pac, 4, args.semilla)
    _, ari2, nmi2 = agrupar(zp, (y_pac > 0).astype(int), 2, args.semilla)
    _, ari4_img, nmi4_img = agrupar(z_img, y_img, 4, args.semilla)
    rho_pc1 = float(pd.Series(zp[:, 0]).corr(pd.Series(pac["pct"].to_numpy()), method="spearman"))

    res = {
        "dimension_caracteristicas": int(emb.shape[1]),
        "varianza_explicada_10_componentes": float(pca.explained_variance_ratio_.sum()),
        "varianza_explicada_pc1_pc2": [float(v) for v in pca.explained_variance_ratio_[:2]],
        "kmeans4_paciente": {"ari": ari4, "nmi": nmi4},
        "kmeans2_paciente_graso_vs_normal": {"ari": ari2, "nmi": nmi2},
        "kmeans4_imagen": {"ari": ari4_img, "nmi": nmi4_img},
        "spearman_pc1_vs_pct_biopsia": rho_pc1,
        "tabla_contingencia_grupo_vs_grado": pd.crosstab(c4, y_pac).reindex(columns=range(4), fill_value=0).values.tolist(),
    }
    args.resultados.mkdir(parents=True, exist_ok=True)
    (args.resultados / "no_supervisado.json").write_text(json.dumps(res, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(res, indent=2, ensure_ascii=False))

    ts = TSNE(n_components=2, perplexity=30, init="pca", random_state=args.semilla).fit_transform(z_img)
    fig, ax = plt.subplots(1, 3, figsize=(13.5, 4.3), dpi=300)
    for k, c in enumerate(CLASES):
        s = y_pac == k
        ax[0].scatter(zp[s, 0], zp[s, 1], c=COLORES[k], s=34, label=c, edgecolor="white", lw=0.5)
        s = y_img == k
        ax[1].scatter(ts[s, 0], ts[s, 1], c=COLORES[k], s=7, label=c, alpha=0.8)
    v = pca.explained_variance_ratio_
    ax[0].set_xlabel(f"CP1 ({v[0]:.0%} de la varianza)")
    ax[0].set_ylabel(f"CP2 ({v[1]:.0%})")
    ax[0].set_title("A. ACP por paciente (características ImageNet)", loc="left", fontsize=10)
    ax[1].set_title("B. t-SNE por imagen", loc="left", fontsize=10)
    ax[1].set_xticks([])
    ax[1].set_yticks([])
    ct = np.array(res["tabla_contingencia_grupo_vs_grado"])
    ax[2].imshow(ct, cmap="Greys")
    for i in range(ct.shape[0]):
        for j in range(ct.shape[1]):
            ax[2].text(j, i, ct[i, j], ha="center", va="center", color="white" if ct[i, j] > ct.max() / 2 else "black")
    ax[2].set_xticks(range(4), CLASES)
    ax[2].set_yticks(range(ct.shape[0]), [f"Grupo {i + 1}" for i in range(ct.shape[0])])
    ax[2].set_xlabel("Grado por biopsia")
    ax[2].set_title(f"C. k-means (k = 4): ARI = {ari4:.2f}", loc="left", fontsize=10)
    ax[0].legend(frameon=False, fontsize=8)
    for a in ax[:2]:
        a.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(args.resultados / "figuras" / "figS2_no_supervisado.png")
    plt.close(fig)


if __name__ == "__main__":
    main()
