from __future__ import annotations

import numpy as np
from PIL import Image

from comun import (NOMBRES_CLASES, GradCAM, capa_objetivo_gradcam, enmascarar_abanico, superponer_mapa,
                   transformaciones)


def analizar_estudio(modelo, cfg: dict, imagenes: list[np.ndarray], con_mapas: bool = True,
                     dispositivo="cpu") -> dict:
    import torch

    clases = cfg["clases"]
    imagenes = [enmascarar_abanico(g) for g in imagenes]
    tf = transformaciones(False)
    x = torch.stack([tf(Image.fromarray(g)) for g in imagenes]).to(dispositivo)
    with torch.no_grad():
        probs = np.concatenate([torch.softmax(modelo(x[i:i + 16]), 1).cpu().numpy()
                                for i in range(0, len(x), 16)])
    i_s0 = clases.index("S0")
    umbral = float(cfg.get("umbral_higado_graso", 0.5))

    def regla(p):
        if 1 - p[i_s0] < umbral:
            return i_s0
        return max((j for j in range(len(clases)) if j != i_s0), key=lambda j: p[j])

    p_estudio = probs.mean(0)
    p_graso = float(1 - p_estudio[i_s0])
    es_graso = p_graso >= umbral
    k = regla(p_estudio)
    k_por_imagen = [regla(p) for p in probs]

    mapas = []
    if con_mapas:
        cam = GradCAM(modelo, capa_objetivo_gradcam(modelo, cfg["arquitectura"]))
        for i, g in enumerate(imagenes):
            m = cam(x[i:i + 1], k_por_imagen[i])
            mapas.append(superponer_mapa(g, m))
        cam.cerrar()

    return {
        "clase": clases[k],
        "diagnostico": NOMBRES_CLASES[clases[k]],
        "higado_graso": bool(es_graso),
        "p_higado_graso": p_graso,
        "probabilidades": {c: float(p) for c, p in zip(clases, p_estudio)},
        "probabilidades_por_imagen": probs.tolist(),
        "clases_por_imagen": [clases[j] for j in k_por_imagen],
        "acuerdo_entre_imagenes": float(np.mean([(1 - p[i_s0] >= umbral) == es_graso for p in probs])),
        "mapas": mapas,
    }
