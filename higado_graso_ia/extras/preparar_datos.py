from __future__ import annotations

import argparse
import csv
import hashlib
import sys
import urllib.request
import zipfile
from pathlib import Path

import numpy as np
from PIL import Image


RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "programa"))

from comun import CLASES, grado_desde_porcentaje

URL = ("https://zenodo.org/records/1009146/files/"
       "dataset_liver_bmodes_steatosis_assessment_IJCARS.mat?download=1")
NOMBRE_MAT = "dataset_liver_bmodes_steatosis_assessment_IJCARS.mat"
MD5_ESPERADO = "c87da28a498eae0f0874408c7ac92524"


def md5(ruta: Path) -> str:
    h = hashlib.md5()
    with open(ruta, "rb") as f:
        for bloque in iter(lambda: f.read(1 << 20), b""):
            h.update(bloque)
    return h.hexdigest()


def descargar(destino: Path) -> Path:
    destino.parent.mkdir(parents=True, exist_ok=True)
    if destino.exists() and md5(destino) == MD5_ESPERADO:
        print(f"[OK] Ya existe {destino} (MD5 verificado)")
        return destino
    print(f"Descargando {URL}\n -> {destino} (≈52 MB)…")
    urllib.request.urlretrieve(URL, destino)
    return destino


def _campo(reg, *nombres):
    for n in nombres:
        if isinstance(reg, dict) and n in reg:
            return reg[n]
        if hasattr(reg, n):
            return getattr(reg, n)
    raise KeyError(f"No se encontró ninguno de los campos {nombres}. "
                   f"Campos disponibles: {list(reg.keys()) if isinstance(reg, dict) else dir(reg)}")


def _a_cuadros(imgs) -> list[np.ndarray]:
    arr = np.asarray(imgs)
    if arr.dtype == object:
        return [np.asarray(a) for a in arr.ravel()]
    if arr.ndim == 2:
        return [arr]
    if arr.ndim == 3:
        eje = int(np.argmin(arr.shape))
        return [np.take(arr, i, axis=eje) for i in range(arr.shape[eje])]
    raise ValueError(f"Forma de imágenes no esperada: {arr.shape}")


def leer_mat(ruta: Path) -> list[dict]:
    try:
        from scipy.io import loadmat

        mat = loadmat(str(ruta), simplify_cells=True)
    except NotImplementedError:
        sys.exit("El .mat está en formato v7.3; instale h5py y adapte leer_mat().")

    claves = [k for k in mat if not k.startswith("__")]
    datos = mat["data"] if "data" in mat else mat[claves[0]]
    if isinstance(datos, dict):
        n = len(np.atleast_1d(_campo(datos, "fat")))
        datos = [{k: (np.atleast_1d(v)[i] if np.ndim(v) else v) for k, v in datos.items()} for i in range(n)]
    datos = list(np.atleast_1d(datos))

    pacientes = []
    for i, reg in enumerate(datos, start=1):
        pct = float(np.squeeze(_campo(reg, "fat", "steatosis", "fat_percentage")))
        try:
            pid = int(np.squeeze(_campo(reg, "id", "ID")))
        except KeyError:
            pid = i
        cuadros = [c.astype(np.uint8) if c.max() <= 255 else
                   (255 * (c - c.min()) / (c.max() - c.min())).astype(np.uint8)
                   for c in _a_cuadros(_campo(reg, "images", "imgs", "image"))]
        pacientes.append({"id": pid, "pct": pct, "clase": grado_desde_porcentaje(pct), "cuadros": cuadros})
    return pacientes


def figura_distribucion(pacientes: list[dict], salida: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.ticker import MaxNLocator

    from comun import enmascarar_abanico

    conteo = [sum(p["clase"] == c for p in pacientes) for c in CLASES]
    fig = plt.figure(figsize=(10, 7.2), dpi=300)
    gs = fig.add_gridspec(2, 4, height_ratios=[1.15, 1], hspace=0.25)
    a1 = fig.add_subplot(gs[0, :2])
    a2 = fig.add_subplot(gs[0, 2:])
    a1.hist([p["pct"] for p in pacientes], bins=np.arange(0, 105, 5), color="#4C72B0", edgecolor="white")
    for x in (5, 33, 66):
        a1.axvline(x, ls="--", c="#C44E52", lw=1)
    a1.set_xlabel("Esteatosis por biopsia (% de hepatocitos)")
    a1.set_ylabel("Pacientes")
    a1.set_title("A. Distribución del porcentaje de esteatosis", loc="left", fontsize=10)
    barras = a2.bar(["S0\n(<5 %)", "S1\n(5-33 %)", "S2\n(34-66 %)", "S3\n(>66 %)"], conteo,
                    color=["#55A868", "#DDAA33", "#DD8452", "#C44E52"])
    a2.bar_label(barras, labels=[f"{c} ({c * 10} img)" for c in conteo], fontsize=8)
    a2.set_ylabel("Pacientes")
    a2.set_ylim(0, max(conteo) * 1.15)
    a2.set_title("B. Pacientes por grado (NASH-CRN)", loc="left", fontsize=10)
    for a in (a1, a2):
        a.spines[["top", "right"]].set_visible(False)
        a.yaxis.set_major_locator(MaxNLocator(integer=True))
    ejes = []
    for k, c in enumerate(CLASES):
        ax = fig.add_subplot(gs[1, k])
        ejes.append(ax)
        candidatos = sorted((p for p in pacientes if p["clase"] == c), key=lambda p: p["id"])
        if candidatos:
            p = candidatos[0]
            ax.imshow(enmascarar_abanico(p["cuadros"][0])[10:390, 20:616], cmap="gray")
            ax.set_title(f"{c}: esteatosis {p['pct']:.0f} %", fontsize=9)
        ax.axis("off")
    fig.canvas.draw()
    pos = ejes[0].get_position()
    fig.text(pos.x0, pos.y1 + 0.045, "C. Ejemplos de imágenes modo B por grado (tras la máscara del abanico)", fontsize=10)
    salida.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(salida, bbox_inches="tight")
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mat", type=Path, default=None, help="Ruta a un .mat ya descargado")
    ap.add_argument("--salida", type=Path, default=RAIZ / "datos")
    ap.add_argument("--zip", type=Path, default=None, help="Además empaqueta las imágenes en este ZIP")
    ap.add_argument("--espejo", action="store_true",
                    help="Invierte horizontalmente (riñón a la derecha, presentación convencional)")
    ap.add_argument("--sin-verificar-md5", action="store_true")
    args = ap.parse_args()

    ruta_mat = args.mat or descargar(args.salida / "crudo" / NOMBRE_MAT)
    if not args.sin_verificar_md5:
        h = md5(ruta_mat)
        if h != MD5_ESPERADO:
            sys.exit(f"MD5 incorrecto ({h}); el archivo está dañado o es otra versión.")
        print("[OK] MD5 verificado")

    pacientes = leer_mat(ruta_mat)
    print(f"Pacientes leídos: {len(pacientes)}; imágenes: {sum(len(p['cuadros']) for p in pacientes)}")

    dir_img = args.salida / "imagenes"
    filas, filas_pac = [], []
    for p in pacientes:
        (dir_img / p["clase"]).mkdir(parents=True, exist_ok=True)
        for j, cuadro in enumerate(p["cuadros"], start=1):
            if args.espejo:
                cuadro = cuadro[:, ::-1]
            rel = Path("imagenes") / p["clase"] / f"P{p['id']:02d}_c{j:02d}.png"
            Image.fromarray(cuadro).save(args.salida / rel)
            filas.append({"ruta": rel.as_posix(), "paciente": f"P{p['id']:02d}", "cuadro": j,
                          "esteatosis_pct": p["pct"], "grado": p["clase"],
                          "higado_graso": int(p["clase"] != "S0"),
                          "alto": cuadro.shape[0], "ancho": cuadro.shape[1]})
        filas_pac.append({"paciente": f"P{p['id']:02d}", "esteatosis_pct": p["pct"],
                          "grado": p["clase"], "n_imagenes": len(p["cuadros"])})

    for nombre, contenido in (("metadatos.csv", filas), ("pacientes.csv", filas_pac)):
        with open(args.salida / nombre, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(contenido[0]))
            w.writeheader()
            w.writerows(contenido)

    print("\nPacientes por grado:")
    for c in CLASES:
        n = sum(p["clase"] == c for p in pacientes)
        print(f"  {c}: {n:3d} pacientes ({n * 10} imágenes)")
    if any(sum(p["clase"] == c for p in pacientes) < 5 for c in CLASES):
        print("  ADVERTENCIA: algún grado tiene <5 pacientes; la validación cruzada de 5 particiones\n"
              "  no podrá incluirlo en todas, y sus métricas tendrán intervalos muy amplios.")

    figura_distribucion(pacientes, RAIZ / "resultados" / "figuras" / "fig2_distribucion_grados.png")

    leeme = ("Imágenes B-mode de hígado (Byra et al., 2018; doi:10.5281/zenodo.1009146; CC BY 4.0).\n"
             "Carpetas = grado de esteatosis por biopsia (NASH-CRN): S0 <5 %, S1 5-33 %, "
             "S2 34-66 %, S3 >66 %.\nCite: Byra M, et al. Int J Comput Assist Radiol Surg. "
             "2018;13(12):1895-1903.\n")
    (args.salida / "LEEME.txt").write_text(leeme, encoding="utf-8")
    if args.zip:
        with zipfile.ZipFile(args.zip, "w", zipfile.ZIP_DEFLATED) as z:
            for fila in filas:
                z.write(args.salida / fila["ruta"], fila["ruta"])
            z.write(args.salida / "metadatos.csv", "metadatos.csv")
            z.write(args.salida / "pacientes.csv", "pacientes.csv")
            z.writestr("LEEME.txt", leeme)
    print(f"\n[OK] Imágenes en {dir_img}/" + (f"  |  ZIP: {args.zip}" if args.zip else ""))


if __name__ == "__main__":
    main()
