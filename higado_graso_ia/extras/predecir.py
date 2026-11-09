from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from PIL import Image


RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "programa"))

from comun import cargar_modelo, leer_imagenes
from inferencia import analizar_estudio


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("imagenes", nargs="+", type=Path)
    ap.add_argument("--modelo", type=Path, default=RAIZ / "modelos" / "modelo_higado_graso.pt")
    ap.add_argument("--mapas", type=Path, default=None, help="Carpeta donde guardar los Grad-CAM")
    ap.add_argument("--json", action="store_true", help="Imprime el resultado en JSON")
    a = ap.parse_args()

    rutas = []
    for r in a.imagenes:
        if r.is_dir():
            rutas += sorted(p for p in r.iterdir() if p.is_file())
        elif any(ch in str(r) for ch in "*?["):
            rutas += sorted(Path(r.anchor or ".").glob(str(r.relative_to(r.anchor)) if r.anchor else str(r)))
        else:
            rutas.append(r)
    if not rutas:
        raise SystemExit("No se encontraron imágenes.")
    modelo, cfg = cargar_modelo(a.modelo)
    imgs, nombres = [], []
    for ruta in rutas:
        cuadros = leer_imagenes(ruta)
        imgs += cuadros
        nombres += [f"{ruta.stem}_{i + 1:02d}" for i in range(len(cuadros))]
    r = analizar_estudio(modelo, cfg, imgs, con_mapas=a.mapas is not None)
    if a.mapas:
        a.mapas.mkdir(parents=True, exist_ok=True)
        for m, n in zip(r["mapas"], nombres):
            Image.fromarray(m).save(a.mapas / f"{n}_gradcam.png")
    r.pop("mapas")
    if a.json:
        print(json.dumps(r, indent=2, ensure_ascii=False))
    else:
        print(f"\nResultado: {r['diagnostico']}")
        print(f"Probabilidad de hígado graso: {r['p_higado_graso']:.1%}  ({len(imgs)} imágenes)")
        for c, p in r["probabilidades"].items():
            print(f"  {c}: {p:.1%}")


if __name__ == "__main__":
    main()
