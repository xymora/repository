from __future__ import annotations

import argparse
import contextlib
import json
import platform
import time
from pathlib import Path

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from PIL import Image
from sklearn.model_selection import StratifiedGroupKFold
from torch.utils.data import DataLoader, Dataset

import figuras
import metricas as M
from comun import (CLASES, GradCAM, TAM_ENTRADA, capa_objetivo_gradcam, construir_modelo, enmascarar_abanico,
                   fijar_semillas, guardar_modelo, superponer_mapa, transformaciones)

RAIZ = Path(__file__).resolve().parent.parent


class ImagenesHigado(Dataset):
    def __init__(self, df: pd.DataFrame, raiz: Path, entrenamiento: bool):
        self.df = df.reset_index(drop=True)
        self.raiz = raiz
        self.tf = transformaciones(entrenamiento)

    def __len__(self):
        return len(self.df)

    def __getitem__(self, i):
        fila = self.df.iloc[i]
        gris = enmascarar_abanico(np.array(Image.open(self.raiz / fila["ruta"]).convert("L")))
        return self.tf(Image.fromarray(gris)), int(fila["y"]), i


def pesos_clase(y: np.ndarray) -> torch.Tensor:
    conteo = np.bincount(y, minlength=len(CLASES)).astype(float)
    w = np.where(conteo > 0, conteo.sum() / (len(CLASES) * np.maximum(conteo, 1)), 0.0)
    return torch.tensor(w / w[w > 0].mean(), dtype=torch.float32)


def autocast(disp):
    return torch.autocast(device_type="cuda") if disp.type == "cuda" else contextlib.nullcontext()


@torch.no_grad()
def perdida_evaluacion(modelo, cargador, criterio, disp):
    modelo.eval()
    total, n = 0.0, 0
    for x, y, _ in cargador:
        x, y = x.to(disp), y.to(disp)
        with autocast(disp):
            total += criterio(modelo(x).float(), y).item() * len(y)
        n += len(y)
    return total / max(n, 1)


@torch.no_grad()
def predecir(modelo, cargador, disp):
    modelo.eval()
    probs, idx = [], []
    for x, _, i in cargador:
        with autocast(disp):
            probs.append(torch.softmax(modelo(x.to(disp)).float(), 1).cpu().numpy())
        idx.append(i.numpy())
    return np.concatenate(probs), np.concatenate(idx)


def entrenar(df_tr, df_te, args, disp, raiz, etiqueta=""):
    fijar_semillas(args.semilla)
    modelo = construir_modelo(args.arquitectura, preentrenado=True).to(disp)
    g = torch.Generator().manual_seed(args.semilla)
    ld_tr = DataLoader(ImagenesHigado(df_tr, raiz, True), batch_size=args.lote, shuffle=True,
                       num_workers=args.trabajadores, generator=g, drop_last=len(df_tr) > args.lote)
    ld_te = (DataLoader(ImagenesHigado(df_te, raiz, False), batch_size=args.lote, shuffle=False,
                        num_workers=args.trabajadores) if df_te is not None else None)
    w = pesos_clase(df_tr["y"].to_numpy()).to(disp)
    criterio = nn.CrossEntropyLoss(weight=w, label_smoothing=0.05)
    criterio_monitoreo = nn.CrossEntropyLoss(label_smoothing=0.05)
    opt = torch.optim.AdamW(modelo.parameters(), lr=args.lr, weight_decay=args.decaimiento)
    sched = torch.optim.lr_scheduler.OneCycleLR(opt, max_lr=args.lr, total_steps=args.epocas * len(ld_tr),
                                                pct_start=0.15, anneal_strategy="cos")
    escalador = torch.amp.GradScaler(enabled=disp.type == "cuda")

    historial = {"perdida_entrenamiento": [], "perdida_prueba": []}
    for ep in range(1, args.epocas + 1):
        t0 = time.time()
        modelo.train()
        total, n = 0.0, 0
        for x, y, _ in ld_tr:
            x, y = x.to(disp, non_blocking=True), y.to(disp, non_blocking=True)
            with autocast(disp):
                perdida = criterio(modelo(x), y)
            opt.zero_grad(set_to_none=True)
            escalador.scale(perdida).backward()
            escalador.step(opt)
            escalador.update()
            sched.step()
            total += perdida.item() * len(y)
            n += len(y)
        historial["perdida_entrenamiento"].append(total / n)
        msg = f"{etiqueta} época {ep:02d}/{args.epocas}  pérdida_ent={total / n:.4f}"
        if ld_te is not None:
            pt = perdida_evaluacion(modelo, ld_te, criterio_monitoreo, disp)
            historial["perdida_prueba"].append(pt)
            msg += f"  pérdida_prueba(monitoreo)={pt:.4f}"
        print(msg + f"  ({time.time() - t0:.0f}s)")
    return modelo, ld_te, historial


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--datos", type=Path, default=RAIZ / "datos")
    ap.add_argument("--resultados", type=Path, default=RAIZ / "resultados")
    ap.add_argument("--modelo", type=Path, default=RAIZ / "modelos" / "modelo_higado_graso.pt")
    ap.add_argument("--arquitectura", default="efficientnet_b0", choices=["efficientnet_b0", "resnet50"])
    ap.add_argument("--epocas", type=int, default=25)
    ap.add_argument("--lote", type=int, default=16)
    ap.add_argument("--lr", type=float, default=3e-4)
    ap.add_argument("--decaimiento", type=float, default=1e-4)
    ap.add_argument("--particiones", type=int, default=5)
    ap.add_argument("--semilla", type=int, default=42)
    ap.add_argument("--umbral", type=float, default=0.5, help="Umbral de P(hígado graso)")
    ap.add_argument("--bootstrap", type=int, default=2000)
    ap.add_argument("--trabajadores", type=int, default=2)
    ap.add_argument("--rapido", action="store_true", help="Prueba de humo: 2 épocas, 100 bootstrap")
    ap.add_argument("--sin-modelo-final", action="store_true")
    args = ap.parse_args()
    if args.rapido:
        args.epocas, args.bootstrap = 2, 100

    t_inicio = time.time()
    fijar_semillas(args.semilla)
    disp = torch.device("cuda" if torch.cuda.is_available() else
                        "mps" if torch.backends.mps.is_available() else "cpu")
    print(f"Dispositivo: {disp}")
    figs = args.resultados / "figuras"
    figs.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(args.datos / "metadatos.csv")
    df["y"] = df["grado"].map({c: i for i, c in enumerate(CLASES)}).astype(int)
    pac = df.groupby("paciente")["y"].first()
    print("Pacientes por grado:", {CLASES[k]: int(v) for k, v in pac.value_counts().sort_index().items()})

    sgkf = StratifiedGroupKFold(n_splits=args.particiones, shuffle=True, random_state=args.semilla)
    df["particion"] = -1
    for k, (_, te) in enumerate(sgkf.split(df, df["y"], groups=df["paciente"])):
        df.loc[df.index[te], "particion"] = k
    for k in range(args.particiones):
        assert not set(df[df.particion == k].paciente) & set(df[df.particion != k].paciente), "Fuga de pacientes"

    oof = np.zeros((len(df), len(CLASES)), dtype=np.float32)
    historiales, ejemplos_cam = [], {}
    for k in range(args.particiones):
        tr, te = df[df.particion != k], df[df.particion == k]
        print(f"\n=== Partición {k + 1}/{args.particiones}: {tr.paciente.nunique()} pacientes entrenamiento, "
              f"{te.paciente.nunique()} prueba ===")
        modelo, ld_te, hist = entrenar(tr, te, args, disp, args.datos, etiqueta=f"[P{k + 1}]")
        historiales.append(hist)
        probs, idx = predecir(modelo, ld_te, disp)
        oof[te.index[idx]] = probs

        cam = GradCAM(modelo, capa_objetivo_gradcam(modelo, args.arquitectura))
        tf = transformaciones(False)
        for g in sorted(te["y"].unique()):
            if CLASES[g] in ejemplos_cam:
                continue
            fila = te[te.y == g].iloc[0]
            gris = enmascarar_abanico(np.array(Image.open(args.datos / fila["ruta"]).convert("L")))
            x = tf(Image.fromarray(gris)).unsqueeze(0).to(disp)
            p = oof[fila.name]
            k_pred = 1 + int(p[1:].argmax()) if 1 - p[0] >= args.umbral else 0
            mapa = cam(x, k_pred)
            ejemplos_cam[CLASES[g]] = {
                "gris": np.array(Image.fromarray(gris).resize(TAM_ENTRADA[::-1])),
                "mapa": superponer_mapa(gris, mapa), "grado_real": CLASES[g],
                "grado_pred": CLASES[k_pred], "prob": float(p[k_pred])}
        cam.cerrar()
        del modelo
        if disp.type == "cuda":
            torch.cuda.empty_cache()

    for j, c in enumerate(CLASES):
        df[f"p_{c}"] = oof[:, j]
    df_img = M.completar_predicciones(df, args.umbral)
    df_pac = M.agregar_por_paciente(df, args.umbral)

    m_pac = M.metricas_puntuales(df_pac, args.umbral)
    m_img = M.metricas_puntuales(df_img, args.umbral)
    ic_pac = M.bootstrap_ic(df_pac, args.umbral, n=args.bootstrap, semilla=args.semilla)
    youden = M.umbral_youden(df_pac)
    m_youden = M.metricas_puntuales(df_pac, youden)

    df_img.to_csv(args.resultados / "predicciones_por_imagen.csv", index=False)
    df_pac.to_csv(args.resultados / "predicciones_por_paciente.csv", index=False)

    figuras.fig_roc(df_pac, df_img, m_pac, ic_pac, figs / "fig3_curvas_roc.png")
    figuras.fig_confusion(M.matriz_confusion(df_pac), M.matriz_confusion(df_img), figs / "fig4_matriz_confusion.png")
    figuras.fig_gradcam(list(ejemplos_cam.values()), figs / "fig5_gradcam.png")
    figuras.fig_curvas(historiales, figs / "figS1_curvas_aprendizaje.png")

    resumen = {
        "configuracion": {k: (str(v) if isinstance(v, Path) else v) for k, v in vars(args).items()},
        "entorno": {"python": platform.python_version(), "torch": torch.__version__,
                    "torchvision": __import__("torchvision").__version__, "dispositivo": str(disp),
                    "gpu": torch.cuda.get_device_name(0) if disp.type == "cuda" else None,
                    "so": platform.platform()},
        "datos": {"pacientes": int(df.paciente.nunique()), "imagenes": int(len(df)),
                  "pacientes_por_grado": {CLASES[k]: int(v) for k, v in pac.value_counts().sort_index().items()}},
        "por_paciente": m_pac, "ic95_por_paciente": ic_pac, "por_imagen": m_img,
        "umbral_youden_paciente": youden, "por_paciente_umbral_youden_OPTIMISTA": m_youden,
        "matriz_confusion_paciente": M.matriz_confusion(df_pac).tolist(),
        "matriz_confusion_imagen": M.matriz_confusion(df_img).tolist(),
    }

    if not args.sin_modelo_final:
        print("\n=== Entrenando modelo final con todos los pacientes ===")
        modelo, _, _ = entrenar(df, None, args, disp, args.datos, etiqueta="[Final]")
        guardar_modelo(modelo.cpu(), args.modelo, {
            "arquitectura": args.arquitectura, "clases": CLASES, "tam_entrada": list(TAM_ENTRADA),
            "umbral_higado_graso": args.umbral, "epocas": args.epocas, "semilla": args.semilla,
            "datos_entrenamiento": "Byra et al. 2018, doi:10.5281/zenodo.1009146 (55 pacientes, 550 imágenes)",
            "desempeno_validacion_cruzada_paciente": {k: m_pac[k] for k in
                ("auc_graso", "sensibilidad_graso", "especificidad_graso", "exactitud_grado",
                 "kappa_cuadratica_grado")},
        })
        print(f"[OK] Modelo guardado en {args.modelo}")

    resumen["tiempo_total_min"] = round((time.time() - t_inicio) / 60, 1)
    (args.resultados / "metricas.json").write_text(json.dumps(resumen, indent=2, ensure_ascii=False), encoding="utf-8")
    escribir_tabla_y_resumen(resumen, args.resultados)
    print(f"\n[OK] Resultados en {args.resultados}/  ({resumen['tiempo_total_min']} min)")
    print((args.resultados / "resumen_resultados.md").read_text(encoding="utf-8"))


def escribir_tabla_y_resumen(r: dict, salida: Path):
    p, ic, im = r["por_paciente"], r["ic95_por_paciente"], r["por_imagen"]
    f = lambda v: f"{v:.3f}" if np.isfinite(v) else "NA"
    fic = lambda k: f"{f(p[k])} ({f(ic[k][0])}-{f(ic[k][1])})" if k in ic else f(p[k])
    filas = [
        ("Detección de hígado graso (S1-S3 vs. S0)", "AUC-ROC", fic("auc_graso"), f(im["auc_graso"])),
        ("", "Sensibilidad", fic("sensibilidad_graso"), f(im["sensibilidad_graso"])),
        ("", "Especificidad", fic("especificidad_graso"), f(im["especificidad_graso"])),
        ("", "VPP", f(p["vpp_graso"]), f(im["vpp_graso"])),
        ("", "VPN", f(p["vpn_graso"]), f(im["vpn_graso"])),
        ("", "Exactitud", fic("exactitud_graso"), f(im["exactitud_graso"])),
        ("Clasificación del grado (S0-S3)", "Exactitud", fic("exactitud_grado"), f(im["exactitud_grado"])),
        ("", "Exactitud ±1 grado", f(p["exactitud_grado_mas_menos_1"]), f(im["exactitud_grado_mas_menos_1"])),
        ("", "F1 macro", fic("f1_macro_grado"), f(im["f1_macro_grado"])),
        ("", "Kappa ponderada cuadrática", fic("kappa_cuadratica_grado"), f(im["kappa_cuadratica_grado"])),
        ("", "Rho de Spearman vs. % biopsia", fic("spearman_rho_vs_biopsia"), f(im["spearman_rho_vs_biopsia"])),
    ] + [("", f"AUC {c} vs. resto", f(p[f"auc_{c}_vs_resto"]), f(im[f"auc_{c}_vs_resto"])) for c in CLASES]
    pd.DataFrame(filas, columns=["Tarea", "Métrica", f"Por paciente (n = {p['n']}), IC 95 %",
                                 f"Por imagen (n = {im['n']})"]).to_csv(salida / "tabla_resultados.csv", index=False)
    md = ["# Resumen de resultados (validación cruzada agrupada por paciente)", "",
          f"Pacientes por grado: {r['datos']['pacientes_por_grado']}", "",
          f"- AUC hígado graso (paciente): {fic('auc_graso')}",
          f"- Sensibilidad / especificidad (umbral {r['configuracion']['umbral']}): "
          f"{fic('sensibilidad_graso')} / {fic('especificidad_graso')}",
          f"- Exactitud del grado: {fic('exactitud_grado')}; kappa cuadrática: {fic('kappa_cuadratica_grado')}",
          f"- Spearman vs. % biopsia: {fic('spearman_rho_vs_biopsia')} (p = {p['spearman_p']:.2g})",
          f"- Matriz de confusión (filas = biopsia S0-S3; columnas = IA): {r['matriz_confusion_paciente']}",
          "", f"Entorno: {r['entorno']}"]
    (salida / "resumen_resultados.md").write_text("\n".join(md), encoding="utf-8")


if __name__ == "__main__":
    main()
