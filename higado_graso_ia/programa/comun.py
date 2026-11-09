from __future__ import annotations

import json
import random
from pathlib import Path

import numpy as np
from PIL import Image

CLASES = ["S0", "S1", "S2", "S3"]
NOMBRES_CLASES = {
    "S0": "Sin esteatosis (hígado normal, <5 %)",
    "S1": "Hígado graso grado 1 – leve (5-33 %)",
    "S2": "Hígado graso grado 2 – moderado (34-66 %)",
    "S3": "Hígado graso grado 3 – grave (>66 %)",
}

TAM_ENTRADA = (256, 384)
MEDIA_IMAGENET = [0.485, 0.456, 0.406]
DE_IMAGENET = [0.229, 0.224, 0.225]


def grado_desde_porcentaje(pct: float) -> str:
    pct = float(pct)
    if pct < 5:
        return "S0"
    if pct <= 33:
        return "S1"
    if pct <= 66:
        return "S2"
    return "S3"


def fijar_semillas(semilla: int = 42) -> None:
    random.seed(semilla)
    np.random.seed(semilla)
    try:
        import torch

        torch.manual_seed(semilla)
        torch.cuda.manual_seed_all(semilla)
        torch.backends.cudnn.deterministic = True
        torch.backends.cudnn.benchmark = False
    except ImportError:
        pass


def a_escala_grises_uint8(arr: np.ndarray) -> np.ndarray:
    arr = np.asarray(arr)
    if arr.ndim == 3 and arr.shape[-1] in (3, 4):
        arr = arr[..., :3].astype(np.float32) @ np.array([0.299, 0.587, 0.114], dtype=np.float32)
    arr = arr.astype(np.float32)
    if arr.max() > 255 or arr.min() < 0:
        lo, hi = np.percentile(arr, [0.5, 99.5])
        arr = np.clip((arr - lo) / max(hi - lo, 1e-6), 0, 1) * 255
    return np.clip(arr, 0, 255).astype(np.uint8)


def leer_imagenes(ruta: str | Path) -> list[np.ndarray]:
    ruta = Path(ruta)
    es_dicom = ruta.suffix.lower() in (".dcm", ".dicom", "")
    if es_dicom:
        try:
            import pydicom

            ds = pydicom.dcmread(str(ruta))
            px = ds.pixel_array
            if getattr(ds, "PhotometricInterpretation", "") == "MONOCHROME1":
                px = px.max() - px
            if px.ndim == 2:
                return [a_escala_grises_uint8(px)]
            if px.ndim == 3 and px.shape[-1] in (3, 4) and getattr(ds, "SamplesPerPixel", 1) > 1:
                return [a_escala_grises_uint8(px)]
            return [a_escala_grises_uint8(f) for f in px]
        except Exception:
            if ruta.suffix.lower() in (".dcm", ".dicom"):
                raise
    img = Image.open(ruta)
    cuadros = []
    try:
        i = 0
        while True:
            img.seek(i)
            cuadros.append(a_escala_grises_uint8(np.array(img.convert("RGB"))))
            i += 1
    except EOFError:
        pass
    return cuadros


def enmascarar_abanico(gris: np.ndarray, umbral: int = 4) -> np.ndarray:
    from scipy import ndimage as ndi

    binaria = ndi.binary_opening(gris > umbral, structure=np.ones((5, 5)))
    etiquetas, n = ndi.label(binaria)
    if n == 0:
        return gris
    tamanos = ndi.sum(binaria, etiquetas, index=range(1, n + 1))
    abanico = etiquetas == (1 + int(np.argmax(tamanos)))
    abanico = ndi.binary_closing(abanico, structure=np.ones((9, 9)), iterations=2)
    abanico = ndi.binary_fill_holes(abanico)
    if abanico.mean() < 0.15:
        return gris
    return np.where(abanico, gris, 0).astype(np.uint8)


def transformaciones(entrenamiento: bool):
    from torchvision import transforms as T

    base_final = [
        T.ToTensor(),
        T.Normalize(MEDIA_IMAGENET, DE_IMAGENET),
    ]
    if entrenamiento:
        return T.Compose([
            T.Grayscale(num_output_channels=3),
            T.Resize(TAM_ENTRADA),
            T.RandomAffine(degrees=8, translate=(0.04, 0.04), scale=(0.92, 1.08)),
            T.ColorJitter(brightness=0.15, contrast=0.15),
            *base_final,
        ])
    return T.Compose([
        T.Grayscale(num_output_channels=3),
        T.Resize(TAM_ENTRADA),
        *base_final,
    ])


def construir_modelo(arquitectura: str = "efficientnet_b0", preentrenado: bool = True, n_clases: int = 4):
    import torch.nn as nn
    from torchvision import models

    if arquitectura == "efficientnet_b0":
        pesos = models.EfficientNet_B0_Weights.IMAGENET1K_V1 if preentrenado else None
        m = models.efficientnet_b0(weights=pesos)
        m.classifier = nn.Sequential(nn.Dropout(0.3), nn.Linear(m.classifier[1].in_features, n_clases))
    elif arquitectura == "resnet50":
        pesos = models.ResNet50_Weights.IMAGENET1K_V2 if preentrenado else None
        m = models.resnet50(weights=pesos)
        m.fc = nn.Sequential(nn.Dropout(0.3), nn.Linear(m.fc.in_features, n_clases))
    else:
        raise ValueError(f"Arquitectura no soportada: {arquitectura}")
    return m


def capa_objetivo_gradcam(modelo, arquitectura: str):
    if arquitectura == "efficientnet_b0":
        return modelo.features[-1]
    if arquitectura == "resnet50":
        return modelo.layer4[-1]
    raise ValueError(arquitectura)


def guardar_modelo(modelo, ruta: Path, config: dict) -> None:
    import torch

    ruta.parent.mkdir(parents=True, exist_ok=True)
    torch.save({"state_dict": modelo.state_dict(), "config": config}, ruta)
    ruta.with_suffix(".json").write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8")


def cargar_modelo(ruta: str | Path, dispositivo="cpu"):
    import torch

    ckpt = torch.load(str(ruta), map_location=dispositivo, weights_only=False)
    cfg = ckpt["config"]
    m = construir_modelo(cfg["arquitectura"], preentrenado=False, n_clases=len(cfg["clases"]))
    m.load_state_dict(ckpt["state_dict"])
    m.eval().to(dispositivo)
    return m, cfg


class GradCAM:
    def __init__(self, modelo, capa):
        self.modelo = modelo
        self.act = None
        self.grad = None
        self._h1 = capa.register_forward_hook(self._guardar_act)

    def _guardar_act(self, _m, _i, salida):
        self.act = salida.detach()
        if salida.requires_grad:
            salida.register_hook(self._guardar_grad)

    def _guardar_grad(self, grad):
        self.grad = grad.detach()

    def __call__(self, x, clase: int):
        import torch
        import torch.nn.functional as F

        self.modelo.zero_grad(set_to_none=True)
        with torch.enable_grad():
            x = x.clone().requires_grad_(True)
            logits = self.modelo(x)
            logits[:, clase].sum().backward()
        pesos = self.grad.mean(dim=(2, 3), keepdim=True)
        cam = F.relu((pesos * self.act).sum(1, keepdim=True))
        cam = F.interpolate(cam, size=x.shape[-2:], mode="bilinear", align_corners=False)[0, 0]
        cam = cam - cam.min()
        cam = cam / (cam.max() + 1e-8)
        return cam.cpu().numpy()

    def cerrar(self):
        self._h1.remove()


def superponer_mapa(gris: np.ndarray, cam: np.ndarray, alfa: float = 0.4) -> np.ndarray:
    import matplotlib

    base = np.array(Image.fromarray(gris).resize((cam.shape[1], cam.shape[0]))).astype(np.float32) / 255
    color = matplotlib.colormaps["jet"](cam)[..., :3]
    mezcla = (1 - alfa) * np.stack([base] * 3, -1) + alfa * color
    return (np.clip(mezcla, 0, 1) * 255).astype(np.uint8)
