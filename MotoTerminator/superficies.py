import numpy as np

import config as C
from terreno import DX, M, MU, RASGOS, RUGO, datos_nivel, maximo_adelante

SUPERFICIES = {"pavimento": "Calles pavimentadas (asfalto liso)",
               "irregular": "Calles con relieve irregular (colinas, baches, pendientes)",
               "variado": "Terreno variado y obstáculos (según el nivel)"}
_RASGOS_DE_RECTA = {"rampa", "escalones", "zanja"}
_MATERIAL_FIJO = {"rocas": ("roca", "grava"), "escalones": ("asfalto", "roca"),
                  "rampa": ("tierra", "asfalto")}


def _variado(self, rng, nivel, nombres, idx):
    rasgos, mats, amp, _, _ = datos_nivel(nivel)
    n = len(self.xs)
    hs = np.zeros(n)
    mat = np.full(n, M["asfalto"], dtype=np.int64)
    self.secciones = []
    curva = maximo_adelante(np.abs(self.kappa), int(10 / DX))
    i = min(int(15 / DX), n)
    fin = max(i, min(n, int((self.meta - 12) / DX)))
    self.secciones.append((0.0, i * DX, "salida", "asfalto"))
    h = 0.0
    n3 = int(3 / DX)
    while i < fin:
        calle = nombres[idx[i]]
        if rng.random() < 0.35:
            off, rasgo, m = np.zeros(int(rng.uniform(15, 40) / DX)), calle, "asfalto"
        else:
            rasgo = rasgos[rng.integers(len(rasgos))]
            off = RASGOS[rasgo](rng, amp)
            k_tramo = float(curva[i:min(i + len(off), n)].max())
            if rasgo in _RASGOS_DE_RECTA and k_tramo > 0.02:
                rasgo = "baches" if "baches" in rasgos else rasgos[0]
                off = RASGOS[rasgo](rng, amp)
                k_tramo = float(curva[i:min(i + len(off), n)].max())
            pend = float(np.max(np.abs(off[n3:] - off[:-n3])) / 3) if len(off) > n3 else 0.0
            opciones = [x for x in _MATERIAL_FIJO.get(rasgo, mats) if x in mats] or mats
            viables = [x for x in opciones if MU[M[x]] * 0.5 >= pend and
                       min(C.A_LAT_MAX, 0.85 * MU[M[x]] * C.G) >= k_tramo * C.V_DISENO ** 2]
            if viables:
                m = viables[rng.integers(len(viables))]
            elif MU[M["asfalto"]] * 0.5 >= pend:
                m = "asfalto"
            else:
                off, rasgo, m = np.zeros(len(off)), calle, "asfalto"
        j = min(i + len(off), fin)
        hs[i:j] = h + off[:j - i]
        mat[i:j] = M[m]
        h = hs[j - 1]
        self.secciones.append((i * DX, j * DX, rasgo, m))
        i = j
    hs[fin:] = h
    self.secciones.append((fin * DX, n * DX, "meta", "asfalto"))
    self.hs = hs
    self.mat = mat
    self.rugo = RUGO[mat] * np.where(mat == M["asfalto"], 0.5, 1.0)


_RASGOS_RELIEVE = ("plano", "colinas_suaves", "colinas", "baches", "pendiente")
_MATS_CALLE = ("tierra", "grava")
_NIVEL_MATS_CALLE = 5
_PEND_LOCAL = 0.42


def _irregular(self, rng, nivel, nombres, idx):
    rasgos, mats, amp, _, _ = datos_nivel(nivel)
    relieve = [r for r in _RASGOS_RELIEVE if r in rasgos or r in ("plano", "colinas_suaves")]
    calle_mats = [x for x in _MATS_CALLE if x in mats] if nivel >= _NIVEL_MATS_CALLE else []
    n = len(self.xs)
    hs = np.zeros(n)
    mat = np.full(n, M["asfalto"], dtype=np.int64)
    self.secciones = []
    curva = maximo_adelante(np.abs(self.kappa), int(10 / DX))
    i = min(int(15 / DX), n)
    fin = max(i, min(n, int((self.meta - 12) / DX)))
    self.secciones.append((0.0, i * DX, "salida", "asfalto"))
    h = 0.0
    n3 = int(3 / DX)
    lim_asf = MU[M["asfalto"]] * 0.5
    while i < fin:
        rasgo = "plano" if rng.random() < 0.2 else relieve[rng.integers(len(relieve))]
        off = RASGOS[rasgo](rng, amp)
        if rasgo != "baches" and rng.random() < 0.5:
            off = off + _ondas(rng, amp, len(off))
        if abs(h) > 3 * amp and h * off[-1] > 0:
            off = -off
        k_tramo = float(curva[i:min(i + len(off), n)].max())
        if rasgo == "baches" and k_tramo > 0.03:
            off = 0.5 * off
        pend = float(np.max(np.abs(off[n3:] - off[:-n3])) / 3) if len(off) > n3 else 0.0
        if pend > lim_asf:
            off = off * (0.95 * lim_asf / pend)
            pend = 0.95 * lim_asf
        m = "asfalto"
        if calle_mats and rng.random() < 0.3:
            viables = [x for x in calle_mats if MU[M[x]] * 0.5 >= pend and
                       min(C.A_LAT_MAX, 0.85 * MU[M[x]] * C.G) >= k_tramo * C.V_DISENO ** 2]
            if viables:
                m = viables[rng.integers(len(viables))]
        j = min(i + len(off), fin)
        i0 = max(0, i - n3)
        lim = 0.5 * MU[np.r_[mat[i0:i], np.full(j - i, M[m])]]
        for _ in range(8):
            seg = np.r_[hs[i0:i], h + off[:j - i]]
            if j <= i:
                break
            exceso = (float(np.max(np.abs(seg[n3:] - seg[:-n3]) / 3 / lim[:-n3]))
                      if len(seg) > n3 else 0.0)
            exceso = max(exceso, float(np.max(np.abs(np.diff(np.r_[h, h + off[:j - i]]))))
                         / (_PEND_LOCAL * DX))
            if exceso <= 1.0:
                break
            off = off * (0.95 / exceso)
        hs[i:j] = h + off[:j - i]
        mat[i:j] = M[m]
        h = hs[j - 1]
        self.secciones.append((i * DX, j * DX, "ondulado" if rasgo == "plano" else rasgo, m))
        i = j
    hs[fin:] = h
    self.secciones.append((fin * DX, n * DX, "meta", "asfalto"))
    self.hs = hs
    self.mat = mat
    self.rugo = RUGO[mat] * np.where(mat == M["asfalto"], 0.75, 1.0)


def _ondas(rng, amp, largo):
    u = np.arange(1, largo + 1) * DX
    off = np.zeros(largo)
    for _ in range(3):
        a, lam, f = rng.uniform(0.01, 0.025) * amp, rng.uniform(5, 12), rng.uniform(0, 6.3)
        off += a * (np.sin(2 * np.pi * u / lam + f) - np.sin(f))
    return off


def generar(pista, rng, nivel, nombres, idx, tipo):
    if tipo == "irregular":
        return _irregular(pista, rng, nivel, nombres, idx)
    if tipo == "variado":
        return _variado(pista, rng, nivel, nombres, idx)
    raise ValueError(f"superficie desconocida: {tipo!r}")
