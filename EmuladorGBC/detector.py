import numpy as np

from agente import direccion


def analizar(stats, pasos, vidas_texto=None, excluir=()):
    if len(stats) < 6:
        return None, []
    ram0 = stats[0][0].astype(np.int64)
    inc = np.stack([s[1] for s in stats]).astype(np.int64)
    dec = np.stack([s[2] for s in stats]).astype(np.int64)
    dec1 = np.stack([s[3] for s in stats]).astype(np.int64)
    salto = np.stack([s[4] for s in stats]).astype(np.int64)

    if vidas_texto:
        plausibles = np.isin(ram0, [vidas_texto, vidas_texto - 1])
    else:
        plausibles = (ram0 >= 1) & (ram0 <= 9)
    con_muerte = (dec1 > 0).sum(0)
    limpio = (dec == dec1).all(0) & (inc.sum(0) == 0) & (dec.max(0) <= 2)
    varia = (con_muerte > 0) & (con_muerte < len(stats))
    cand_vidas = np.flatnonzero(plausibles & limpio & varia)
    vidas = None
    if len(cand_vidas):
        orden = sorted(cand_vidas, key=lambda i: (-(vidas_texto is not None and ram0[i] == vidas_texto),
                                                 -con_muerte[i], i))
        vidas = direccion(int(orden[0]))

    episodios_con = (inc > 0).sum(0)
    varia_inc = inc.std(0) > 0
    sin_bajar = salto.sum(0) == 0
    raro = inc.max(0) <= max(2, pasos // 6)
    largo = np.array([s[5] if len(s) > 5 else pasos for s in stats], dtype=np.float64)[:, None]
    tasa = inc / largo
    activos = inc > 0
    n_act = np.maximum(activos.sum(0), 1)
    media_act = (tasa * activos).sum(0) / n_act
    desv_act = np.sqrt((((tasa - media_act) ** 2) * activos).sum(0) / n_act)
    reloj = (activos.sum(0) >= 3) & (desv_act < 0.2 * np.maximum(media_act, 1e-9))
    cand = np.flatnonzero(varia_inc & sin_bajar & raro & (episodios_con >= 2) & ~reloj)
    cand = [i for i in cand if i not in set(excluir)]
    cand = sorted(cand, key=lambda i: (-episodios_con[i], inc.mean(0)[i]))[:4]
    puntos = sorted(direccion(int(i)) for i in cand)
    return vidas, puntos


def _eje(pos, neg, nada, otro_pos, otro_neg, excluir, episodios):
    s = np.maximum(pos, neg)
    malo = np.minimum(pos, neg) + nada
    otro = np.maximum(otro_pos, otro_neg)
    ok = (s >= 16) & (malo <= 0.15 * s) & (otro <= 0.5 * s) & (episodios >= 3)
    ok[list(excluir)] = False
    cand = np.flatnonzero(ok)
    if not len(cand):
        return None
    return int(max(cand, key=lambda i: (s[i] - 3 * malo[i], -i)))


def analizar_posicion(movs, excluir=()):
    if len(movs) < 6:
        return None
    pila = [np.stack([m[k] for m in movs]).astype(np.int64) for k in range(6)]
    ep_h = ((pila[0] + pila[1]) > 0).sum(0)
    ep_v = ((pila[3] + pila[4]) > 0).sum(0)
    hp, hn, h0, vp, vn, v0 = (q.sum(0) for q in pila)
    x = _eje(hp, hn, h0, vp, vn, excluir, ep_h)
    if x is None:
        return None
    y = _eje(vp, vn, v0, hp, hn, set(excluir) | {x}, ep_v)
    if y is None:
        return None
    return [direccion(x), direccion(y)]


def analizar_mapa(saltos, excluir=()):
    n = sum(s[0] for s in saltos)
    if n < 2:
        return None
    en = np.stack([s[1] for s in saltos]).astype(np.int64).sum(0)
    fuera = np.stack([s[2] for s in saltos]).astype(np.int64).sum(0)
    ok = (en >= 2) & (fuera == 0)
    ok[list(excluir)] = False
    cand = sorted(np.flatnonzero(ok), key=lambda i: (-en[i], i))[:3]
    return sorted(direccion(int(i)) for i in cand) or None
