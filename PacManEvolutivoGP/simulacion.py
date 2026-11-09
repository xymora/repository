import numpy as np

import config as C
from programa import Bosque
from laberinto import DIRS, IZQUIERDA, OPUESTA

VIVO, META, SIN_VIDAS, ATASCADO, TIEMPO = range(5)
MOTIVOS = ("EN JUEGO", "LIMPIO", "SIN VIDAS", "ATASCADO", "TIEMPO")
CASA, SALIENDO, FUERA, OJOS = range(4)
ACTIVOS = {1: (1, 0, 0, 0), 2: (1, 0, 0, 1), 3: (1, 1, 0, 1), 4: (1, 1, 1, 1)}
PUNTOS_FRUTA = (100, 300, 500, 500, 700, 1000, 2000, 5000)
LEJOS = 9999


class Partida:
    def __init__(self, nivel, programas=None, *, controlador=None, n=None):
        self.niv = nivel
        self.lab = lab = nivel.lab
        self.programas = None
        if programas is not None:
            self.controlador = Bosque(programas)
            self.programas = self.controlador.programas
            n = len(programas)
        else:
            self.controlador = controlador
        self.n = n = int(n)
        self.activo = np.array(ACTIVOS[nivel.n_fantasmas], dtype=bool)
        self.esquinas = np.array(C.ESQUINAS, dtype=float)
        self.t_ref = lab.n_puntos * C.T_REFERENCIA_POR_PUNTO
        self.puntos = np.repeat(lab.puntos0[None], n, 0)
        self.energ = np.repeat(lab.energ0[None], n, 0)
        self.restantes = np.full(n, lab.n_puntos)
        self.marcador = np.zeros(n)
        self.vidas = np.full(n, C.VIDAS)
        self.muertes = np.zeros(n, dtype=int)
        self.comidos = np.zeros(n, dtype=int)
        self.fant_comidos = np.zeros(n, dtype=int)
        self.frutas = np.zeros(n, dtype=int)
        self.fruta_t = np.zeros(n)
        self.frutas_salidas = np.zeros(n, dtype=int)
        self.vivo = np.ones(n, dtype=bool)
        self.motivo = np.zeros(n, dtype=int)
        self.t_fin = np.zeros(n)
        self.ult_punto = np.zeros(n)
        self.espera = np.full(n, C.INICIO_ESPERA)
        self.pendiente = np.zeros(n, dtype=bool)
        self.pac_t = np.zeros(n, dtype=np.int32)
        self.pac_d = np.zeros(n, dtype=np.int32)
        self.pac_p = np.zeros(n)
        self.deseo = np.zeros(n, dtype=np.int32)
        self.parado = np.zeros(n, dtype=bool)
        self.fant_t = np.zeros((n, 4), dtype=np.int32)
        self.fant_d = np.zeros((n, 4), dtype=np.int32)
        self.fant_p = np.zeros((n, 4))
        self.fant_e = np.zeros((n, 4), dtype=np.int32)
        self.asustado = np.zeros((n, 4), dtype=bool)
        self.t_susto = np.zeros(n)
        self.racha_f = np.zeros(n, dtype=int)
        self.modo_i = np.zeros(n, dtype=int)
        self.modo_t = np.zeros(n)
        self.t_vida = np.zeros(n)
        self.puntos_vida = np.zeros(n, dtype=int)
        self._reiniciar(np.ones(n, dtype=bool))
        self.ctrl = np.zeros((n, C.SALIDAS))
        self.obs = np.zeros((n, C.N_ENTRADAS))
        self.t = 0.0
        self.pasos = 0
        self.subpasos = 0
        self.terminado = False
        self.eventos = []

    def _reiniciar(self, m):
        lab = self.lab
        self.pac_t[m] = lab.t_pac
        self.pac_d[m] = IZQUIERDA
        self.pac_p[m] = 0.0
        self.deseo[m] = IZQUIERDA
        self.parado[m] = False
        self.fant_t[m] = lab.t_fant0
        self.fant_d[m] = lab.dir_fant0
        self.fant_p[m] = 0.0
        self.fant_e[m] = np.where(np.arange(4) == 0, FUERA, CASA)
        self.asustado[m] = False
        self.t_susto[m] = 0.0
        self.modo_i[m] = 0
        self.modo_t[m] = 0.0
        self.t_vida[m] = 0.0
        self.puntos_vida[m] = 0
        self.fruta_t[m] = 0.0
        self.pendiente[m] = False

    def pos_pac(self):
        rc = self.lab.rc[self.pac_t].astype(float)
        return rc + DIRS[self.pac_d] * self.pac_p[:, None]

    def pos_fant(self):
        rc = self.lab.rc[self.fant_t].astype(float)
        return rc + DIRS[self.fant_d] * self.fant_p[..., None]

    def casilla_pac(self):
        sig = self.lab.vec_casa[self.pac_t, self.pac_d]
        return np.where((self.pac_p >= 0.5) & (sig >= 0), sig, self.pac_t)

    def casilla_fant(self):
        sig = self.lab.vec_casa[self.fant_t, self.fant_d]
        return np.where((self.fant_p >= 0.5) & (sig >= 0), sig, self.fant_t)

    def persecucion(self):
        return self.modo_i % 2 == 1

    def observar(self, idx=None):
        lab = self.lab
        if idx is None:
            idx = np.arange(self.n)
        k = len(idx)
        out = np.zeros((k, C.N_ENTRADAS))
        if k == 0:
            return out
        tn = self.casilla_pac()[idx]
        nb = lab.vec_pac[tn]
        libre = nb >= 0
        nbs = np.where(libre, nb, tn[:, None])
        Dn = lab.D[nbs]
        Dp = lab.D[tn]
        hay = self.puntos[idx] | self.energ[idx]
        esc, dmax = C.DIST_ESCALA, C.DIST_MAX

        def dist(mask3):
            d = np.where(mask3, Dn, LEJOS).min(-1).astype(float) + 1
            return np.minimum(d / esc, dmax)

        f = np.zeros((k, 4, C.SENSORES_DIR))
        f[..., 0] = libre
        f[..., 1] = dist(hay[:, None, :])
        cerca = (Dp <= C.RADIO_DENSIDAD)[:, None, :] & hay[:, None, :]
        f[..., 2] = (cerca & (Dn == (Dp[:, None, :] - 1))).sum(-1) / C.RADIO_DENSIDAD
        gt = self.casilla_fant()[idx]
        est = self.fant_e[idx]
        asu = self.asustado[idx]
        peligro = self.activo[None] & ((est == FUERA) | (est == SALIENDO)) & ~asu
        comible = self.activo[None] & (est == FUERA) & asu
        dg = lab.D[nbs[:, :, None], gt[:, None, :]].astype(float) + 1
        f[..., 3] = np.minimum(np.where(peligro[:, None, :], dg, LEJOS).min(-1) / esc, dmax)
        J = np.where(libre, lab.cruce[tn], tn[:, None])
        L = lab.largo[tn].astype(float)
        dJ = lab.D[J[:, :, None], gt[:, None, :]].astype(float)
        dJ = np.where(peligro[:, None, :], dJ, LEJOS).min(-1)
        f[..., 4] = np.clip((dJ - L) / 10.0, -1.0, 1.0)
        f[..., 5] = np.minimum(np.where(comible[:, None, :], dg, LEJOS).min(-1) / esc, dmax)
        f[..., 6] = dist(self.energ[idx][:, None, :])
        fr = np.where(self.fruta_t[idx][:, None] > 0, lab.D[nbs, lab.t_fruta].astype(float) + 1, LEJOS)
        f[..., 7] = np.minimum(fr / esc, dmax)
        pared = ~libre
        f[..., 1:4][pared] = dmax
        f[..., 4][pared] = -1.0
        f[..., 5:8][pared] = dmax
        out[:, :4 * C.SENSORES_DIR] = f.reshape(k, -1)
        o = 4 * C.SENSORES_DIR
        out[np.arange(k), o + self.pac_d[idx]] = 1.0
        out[:, o + 4] = self.t_susto[idx] / max(self.niv.t_susto, 1.0)
        out[:, o + 5] = self.restantes[idx] / lab.n_puntos
        out[:, o + 6] = self.persecucion()[idx]
        out[:, o + 7] = ((est == CASA) & self.activo[None]).sum(1) / 4.0
        return out

    def paso(self):
        if self.terminado:
            return
        self.eventos = []
        decide = np.flatnonzero(self.vivo & (self.espera <= 0))
        if len(decide):
            self.obs[decide] = self.observar(decide)
            self.ctrl[decide] = self.controlador(self, decide)
            libre = self.obs[decide, 0:4 * C.SENSORES_DIR:C.SENSORES_DIR] > 0.5
            self.deseo[decide] = np.argmax(np.where(libre, self.ctrl[decide], -np.inf), axis=1)
        dt = C.DT / C.SUBPASOS
        for _ in range(C.SUBPASOS):
            self._sub(dt)
        self.t += C.DT
        self.pasos += 1
        self._revisar()

    def correr(self, pasos):
        for _ in range(pasos):
            if self.terminado:
                break
            self.paso()

    def _sub(self, dt):
        self.subpasos += 1
        esp = self.vivo & (self.espera > 0)
        if esp.any():
            self.espera[esp] -= dt
            fin = esp & (self.espera <= 0)
            reini = fin & self.pendiente & (self.vidas > 0)
            if reini.any():
                self._reiniciar(reini)
                self.ult_punto[reini] = self.t
            agotado = fin & (self.vidas <= 0)
            if agotado.any():
                self._terminar(agotado, SIN_VIDAS)
        act = self.vivo & (self.espera <= 0)
        if not act.any():
            return
        self.t_vida[act] += dt
        self.fruta_t[act] = np.maximum(self.fruta_t[act] - dt, 0.0)
        sus = act & (self.t_susto > 0)
        if sus.any():
            self.t_susto[sus] -= dt
            acabo = sus & (self.t_susto <= 0)
            self.t_susto[acabo] = 0.0
            self.asustado[acabo] = False
        hor = self.niv.horario
        corre = act & (self.t_susto <= 0) & (self.modo_i < len(hor))
        self.modo_t[corre] += dt
        lim = np.array(hor + (np.inf,))[self.modo_i]
        cambia = corre & (self.modo_t >= lim)
        if cambia.any():
            self.modo_i[cambia] += 1
            self.modo_t[cambia] = 0.0
            self._voltear(cambia)
        en_casa = act[:, None] & self.activo[None] & (self.fant_e == CASA)
        if en_casa.any():
            sale = en_casa & ((self.t_vida[:, None] >= np.array(C.SALIDA_SEG)[None])
                              | (self.puntos_vida[:, None] >= np.array(C.SALIDA_PUNTOS)[None]))
            self.fant_e[sale] = SALIENDO
        self._mover_pac(act, dt)
        self._comer(act)
        self._mover_fantasmas(act, dt)
        self._choques(act)

    def _voltear(self, m):
        lab = self.lab
        v = m[:, None] & (self.fant_e == FUERA)
        if not v.any():
            return
        i, g = np.nonzero(v)
        t, d, p = self.fant_t[i, g], self.fant_d[i, g], self.fant_p[i, g]
        en_medio = p > 0
        sig = lab.vec_casa[t, d]
        nt = np.where(en_medio & (sig >= 0), sig, t)
        nd = OPUESTA[d]
        ok = en_medio | (lab.vec_fuera[t, nd] >= 0)
        self.fant_t[i, g] = nt
        self.fant_d[i, g] = np.where(ok, nd, d)
        self.fant_p[i, g] = np.where(en_medio, 1.0 - p, p)

    def _elegir_pac(self, idx):
        v = self.lab.vec_pac
        t, d, w = self.pac_t[idx], self.pac_d[idx], self.deseo[idx]
        ok_w = v[t, w] >= 0
        ok_d = v[t, d] >= 0
        self.pac_d[idx] = np.where(ok_w, w, d)
        par = ~(ok_w | ok_d)
        self.parado[idx] = par
        self.pac_p[idx[par]] = 0.0

    def _mover_pac(self, act, dt):
        v = self.lab.vec_pac
        rev = act & (self.pac_p > 0) & (self.deseo == OPUESTA[self.pac_d])
        if rev.any():
            i = np.flatnonzero(rev)
            self.pac_t[i] = v[self.pac_t[i], self.pac_d[i]]
            self.pac_d[i] = self.deseo[i]
            self.pac_p[i] = 1.0 - self.pac_p[i]
        cen = np.flatnonzero(act & (self.pac_p == 0))
        if len(cen):
            self._elegir_pac(cen)
        niv = self.niv
        vel = np.where(self.t_susto > 0, niv.v_pac_susto, niv.v_pac) * C.VEL_BASE
        mov = act & ~self.parado
        self.pac_p[mov] += vel[mov] * dt
        cruza = np.flatnonzero(mov & (self.pac_p >= 1.0))
        if len(cruza):
            self.pac_t[cruza] = v[self.pac_t[cruza], self.pac_d[cruza]]
            self.pac_p[cruza] -= 1.0
            self._elegir_pac(cruza)

    def _comer(self, act):
        lab = self.lab
        tc = self.casilla_pac()
        i = np.flatnonzero(act)
        hay_p = self.puntos[i, tc[i]]
        hay_e = self.energ[i, tc[i]]
        come = i[hay_p | hay_e]
        if len(come):
            self.puntos[come, tc[come]] = False
            e = i[hay_e]
            self.energ[e, tc[e]] = False
            self.restantes[come] -= 1
            self.comidos[come] += 1
            self.puntos_vida[come] += 1
            self.ult_punto[come] = self.t
            self.marcador[i[hay_p]] += C.PUNTOS_PUNTO
            for j in i[hay_p]:
                self.eventos.append(("punto", int(j), 0))
            if len(e):
                self.marcador[e] += C.PUNTOS_ENERGIZANTE
                for j in e:
                    self.eventos.append(("energ", int(j), 0))
                me = np.zeros(self.n, dtype=bool)
                me[e] = True
                self._voltear(me)
                if self.niv.t_susto > 0:
                    self.t_susto[e] = self.niv.t_susto
                    self.racha_f[e] = 0
                    self.asustado[e] = self.activo[None] & (self.fant_e[e] != OJOS)
            sale = np.isin(self.comidos[come], C.FRUTA_EN_PUNTOS)
            for j in come[sale]:
                self.fruta_t[j] = C.FRUTA_DURA
                self.frutas_salidas[j] += 1
            limpio = come[self.restantes[come] <= 0]
            if len(limpio):
                m = np.zeros(self.n, dtype=bool)
                m[limpio] = True
                self._terminar(m, META)
                for j in limpio:
                    self.eventos.append(("meta", int(j), 0))
        fr = i[(self.fruta_t[i] > 0) & (tc[i] == lab.t_fruta)]
        if len(fr):
            pts = PUNTOS_FRUTA[min(self.niv.nivel, len(PUNTOS_FRUTA)) - 1]
            self.marcador[fr] += pts
            self.frutas[fr] += 1
            self.fruta_t[fr] = 0.0
            for j in fr:
                self.eventos.append(("fruta", int(j), pts))

    def _objetivos(self, i, g):
        lab = self.lab
        pac = lab.rc[self.casilla_pac()[i]].astype(float)
        dv = DIRS[self.pac_d[i]].astype(float)
        obj = self.esquinas[g].copy()
        caza = self.persecucion()[i]
        elroy = (g == 0) & (self.restantes[i] <= self.niv.elroy)
        caza = caza | elroy
        m = caza & (g == 0)
        obj[m] = pac[m]
        m = caza & (g == 1)
        obj[m] = pac[m] + 4 * dv[m]
        m = caza & (g == 2)
        if m.any():
            blinky = lab.rc[self.casilla_fant()[i[m], 0]].astype(float)
            obj[m] = 2 * (pac[m] + 2 * dv[m]) - blinky
        m = caza & (g == 3)
        if m.any():
            yo = lab.rc[self.casilla_fant()[i[m], 3]].astype(float)
            lejos = np.hypot(*(yo - pac[m]).T) > C.CLYDE_RADIO
            obj[np.flatnonzero(m)[lejos]] = pac[m][lejos]
        return obj

    def _decidir(self, i, g):
        lab = self.lab
        t, d, e = self.fant_t[i, g], self.fant_d[i, g], self.fant_e[i, g]
        nueva = d.copy()
        for estado, meta in ((OJOS, lab.t_centro), (SALIENDO, lab.t_salida)):
            m = e == estado
            if m.any():
                vec = lab.vec_casa[t[m]]
                dist = np.where(vec >= 0, lab.D[np.maximum(vec, 0), meta], LEJOS)
                nueva[m] = np.argmin(dist, axis=1)
        m = e == FUERA
        if m.any():
            im, gm, tm, dm = i[m], g[m], t[m], d[m]
            vec = lab.vec_fuera[tm]
            valido = (vec >= 0) & (np.arange(4)[None] != OPUESTA[dm][:, None])
            sin_salida = ~valido.any(1)
            asu = self.asustado[im, gm]
            obj = self._objetivos(im, gm)
            rc = lab.rc[np.maximum(vec, 0)].astype(float)
            costo = ((rc - obj[:, None, :]) ** 2).sum(-1)
            sem = (tm[:, None] * 12.9898 + np.arange(4)[None] * 78.233 + self.subpasos * 0.1373
                   + gm[:, None] * 37.719 + self.niv.semilla * 0.731)
            azar = np.modf(np.abs(np.sin(sem) * 43758.5453))[0]
            costo = np.where(asu[:, None], azar, costo)
            costo = np.where(valido, costo, np.inf)
            elegido = np.argmin(costo, axis=1)
            nueva[m] = np.where(sin_salida, OPUESTA[dm], elegido)
        self.fant_d[i, g] = nueva

    def _mover_fantasmas(self, act, dt):
        lab, niv = self.lab, self.niv
        mueve = act[:, None] & self.activo[None] & (self.fant_e != CASA)
        if not mueve.any():
            return
        i, g = np.nonzero(mueve)
        cen = self.fant_p[i, g] == 0
        if cen.any():
            self._decidir(i[cen], g[cen])
        e = self.fant_e[i, g]
        t = self.fant_t[i, g]
        vel = np.full(len(i), niv.v_fant)
        blinky = g == 0
        r = self.restantes[i]
        vel = np.where(blinky & (r <= niv.elroy), vel + 0.05, vel)
        vel = np.where(blinky & (r <= niv.elroy // 2), vel + 0.05, vel)
        vel = np.where(lab.tunel[t], niv.v_tunel, vel)
        vel = np.where(self.asustado[i, g], niv.v_fant_susto, vel)
        vel = np.where(e == OJOS, C.VEL_OJOS, vel)
        vel = np.where(e == SALIENDO, C.VEL_CASA, vel)
        p = self.fant_p[i, g] + vel * C.VEL_BASE * dt
        cruza = p >= 1.0
        d = self.fant_d[i, g]
        sig = lab.vec_casa[t, d]
        t = np.where(cruza & (sig >= 0), sig, t)
        p = np.where(cruza, np.where(sig >= 0, p - 1.0, 0.0), p)
        self.fant_t[i, g] = t
        self.fant_p[i, g] = p
        ojos = (e == OJOS) & (t == lab.t_centro) & cruza
        if ojos.any():
            self.fant_e[i[ojos], g[ojos]] = SALIENDO
        sale = (e == SALIENDO) & (t == lab.t_salida) & cruza
        if sale.any():
            self.fant_e[i[sale], g[sale]] = FUERA
            self.fant_d[i[sale], g[sale]] = IZQUIERDA
            self.fant_p[i[sale], g[sale]] = 0.0
        if cruza.any():
            self._decidir(i[cruza], g[cruza])

    def _choques(self, act):
        pp = self.pos_pac()
        pf = self.pos_fant()
        dif = np.abs(pf - pp[:, None, :])
        dif[..., 1] = np.minimum(dif[..., 1], C.ANCHO - dif[..., 1])
        cerca = (dif ** 2).sum(-1) < C.DIST_CHOQUE ** 2
        cerca &= act[:, None] & self.activo[None]
        come = cerca & self.asustado & ((self.fant_e == FUERA) | (self.fant_e == SALIENDO))
        if come.any():
            for i, g in zip(*np.nonzero(come)):
                pts = C.PUNTOS_FANTASMA[min(self.racha_f[i], 3)]
                self.racha_f[i] += 1
                self.marcador[i] += pts
                self.fant_comidos[i] += 1
                self.fant_e[i, g] = OJOS
                self.asustado[i, g] = False
                self.eventos.append(("fantasma", int(i), (int(g), pts)))
        mata = cerca & ~self.asustado & ((self.fant_e == FUERA) | (self.fant_e == SALIENDO))
        muere = mata.any(1)
        if muere.any():
            self.vidas[muere] -= 1
            self.muertes[muere] += 1
            self.espera[muere] = C.MUERTE_ESPERA
            self.pendiente[muere] = True
            for j in np.flatnonzero(muere):
                self.eventos.append(("muerte", int(j), 0))

    def _terminar(self, m, motivo):
        m = m & self.vivo
        self.vivo[m] = False
        self.motivo[m] = motivo
        self.t_fin[m] = self.t

    def _revisar(self):
        act = self.vivo & (self.espera <= 0)
        self._terminar(act & (self.t - self.ult_punto > C.SEG_ATASCADO), ATASCADO)
        self._terminar(self.vivo & (self.t >= C.T_MAX), TIEMPO)
        if not self.vivo.any():
            self.terminado = True

    def progreso(self):
        return 100.0 * (1.0 - self.restantes / self.lab.n_puntos)

    def llegaron(self):
        return self.motivo == META

    def aptitud(self):
        meta = self.motivo == META
        rapidez = np.minimum(1.5, self.t_ref / np.maximum(self.t_fin, 1e-3))
        return (self.marcador * C.PUNTOS_A_APTITUD
                + meta * (C.PREMIO_META + C.PREMIO_RAPIDEZ * rapidez + C.VIDA_SOBRANTE * self.vidas
                          + C.PREMIO_PERFECTO * (self.muertes == 0))
                - C.CASTIGO_MUERTE * self.muertes)

    def lider(self):
        a = self.aptitud()
        if self.vivo.any():
            a = np.where(self.vivo, a, -np.inf)
        return int(np.argmax(a))
