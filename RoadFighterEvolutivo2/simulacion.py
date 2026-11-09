import numpy as np

import cerebro as B
import config as C

VIVO, META, SIN_COMBUSTIBLE, ATASCADO, TIEMPO = range(5)
MOTIVOS = {VIVO: "en carrera", META: "llegó a la meta", SIN_COMBUSTIBLE: "sin combustible",
           ATASCADO: "se atascó", TIEMPO: "se acabó el tiempo"}

_SONDAS = np.array(C.SONDAS)
_MIRADAS = np.array(C.MIRADAS)
_DS = np.arange(C.PASO_ORILLA, C.ALCANCE + 1e-9, C.PASO_ORILLA)
_CARRILES = np.array(C.CARRILES)
_VENTANA = np.arange(48)
_LATERAL = _SONDAS != 0.0


def _carril_de(f):
    return np.argmin(np.abs(np.asarray(f)[..., None] - _CARRILES), axis=-1)


class Carrera:
    def __init__(self, pista, pesos=None, *, controlador=None, n=None, normalizador=None):
        self.pista = pista
        self.norm = normalizador if normalizador is not None else B.Normalizador()
        self.muestras = []
        self._pasos = 0
        if pesos is not None:
            pesos = np.atleast_2d(pesos)
            n = pesos.shape[0]
            self.pesos = pesos
            self.red = B.desempacar(pesos)
        else:
            if controlador is None or n is None:
                raise ValueError("sin pesos hay que dar controlador y n")
            self.red = None
            self.pesos = None
        self.controlador = controlador
        self.n = n
        M = len(pista.t_y0)
        self.t = 0.0
        self.terminado = False
        self.x = np.full(n, pista.centro(0.0))
        self.y = np.zeros(n)
        self.v = np.zeros(n)
        self.vx = np.zeros(n)
        self.alto = np.zeros(n, dtype=bool)
        self.combustible = np.full(n, C.COMBUSTIBLE_INICIAL)
        self.derrape_t = np.zeros(n)
        self.derrape_dir = np.zeros(n)
        self.choque_t = np.zeros(n)
        self.golpe_t = np.zeros(n)
        self.choques = np.zeros(n, dtype=np.int64)
        self.derrapes = np.zeros(n, dtype=np.int64)
        self.arcoiris_n = np.zeros(n, dtype=np.int64)
        self.rebases = np.zeros(n, dtype=np.int64)
        self.causas = {k: np.zeros(n, dtype=np.int64) for k in
                       ("golpe_lateral", "alcance", "aceite", "choque_orilla", "choque_obstaculo")}
        self._visto_adelante = np.zeros((n, M), dtype=bool)
        self._rebasado = np.zeros((n, M), dtype=bool)
        self.alineado = np.zeros(n)
        self._arc_actual = np.full(n, -1)
        self._arc_seg = np.zeros(n)
        self._arc_cerca = np.zeros(n, dtype=bool)
        self._arc_idx = np.full(n, -1)
        self.vivo = np.ones(n, dtype=bool)
        self.motivo = np.full(n, VIVO)
        self.t_fin = np.full(n, np.nan)
        self.y_mejor = np.zeros(n)
        self.t_mejora = np.zeros(n)
        self.ctrl = np.zeros((n, 3))
        self.h = np.zeros((n, B.N_H1))
        self.h2 = np.zeros((n, B.N_H2))
        self.obs = np.zeros((n, B.N_IN))
        self.carril = np.broadcast_to(pista.t_carril, (n, M)).copy()
        self.f = np.broadcast_to(pista.t_f0, (n, M)).copy()
        self.iniciado = np.zeros((n, M), dtype=bool)
        self.tomado = np.zeros((n, M), dtype=bool)
        self._es = {t: pista.t_tipo == t for t in range(len(C.TIPOS))}
        self._arcoiris = self._es[C.ARCOIRIS]
        self.ax, self.ay = pista.aceite_xy()
        self.ox, self.oy = pista.obstaculos_xy()

    def transito_xy(self, t=None):
        yt = self.pista.y_transito(self.t if t is None else t)
        c, h = self.pista.centro(yt), self.pista.util(yt)
        return c[None, :] + self.f * h[None, :], yt

    def _fijos(self):
        return (np.concatenate([self.ax, self.ox]), np.concatenate([self.ay, self.oy]),
                np.concatenate([np.full(len(self.ax), 2.4), self.pista.o_ancho]),
                np.concatenate([np.full(len(self.ax), 3.0), self.pista.o_largo]))

    def observar(self):
        p = self.pista
        n = self.n
        c0, h0 = p.centro(self.y), p.semiancho(self.y)
        partes = [self.v[:, None] / C.VMAX_HIGH,
                  np.where(self.alto, 1.0, -1.0)[:, None],
                  self.combustible[:, None] / C.COMBUSTIBLE_INICIAL,
                  (self.derrape_t > 0)[:, None].astype(float),
                  self.vx[:, None] / 10.0,
                  ((self.x - c0) / h0)[:, None]]
        ym = self.y[:, None] + _MIRADAS[None, :]
        partes.append((p.centro(ym) - self.x[:, None]) / 10.0)
        partes.append(p.semiancho(ym) / 10.0)

        X = self.x[:, None] + _SONDAS[None, :]
        xt, yt = self.transito_xy()
        M = len(yt)
        if M:
            i0 = np.searchsorted(yt, self.y - 2.0 - 12.0)
            idx = np.minimum(i0[:, None] + _VENTANA[None, :], M - 1)
            dy = yt[idx] - self.y[:, None]
            xw = np.take_along_axis(xt, idx, axis=1)
            mitad = (p.t_largo[idx] + C.AUTO_LARGO) / 2
            cerca = ~self._arcoiris[idx] & (dy > -mitad) & (dy < C.ALCANCE) \
                & (i0[:, None] + _VENTANA[None, :] < M)
            dist = np.maximum(dy - mitad, 0.0)
            adelante = (dy > -2.0)[:, None, :] | _LATERAL[None, :, None]
            cubre = cerca[:, None, :] & adelante & (np.abs(X[:, :, None] - xw[:, None, :])
                                                    < (p.t_ancho[idx][:, None, :] + C.AUTO_ANCHO) / 2)
            d_obs = np.where(cubre, dist[:, None, :], np.inf)
            d_min = d_obs.min(axis=2)
            v_rel = np.where(np.isfinite(d_min), (p.t_v[0] - self.v[:, None]) / 40.0, 0.0)
        else:
            d_min = np.full(X.shape, np.inf)
            v_rel = np.zeros(X.shape)
        fx, fy, fw, fl = self._fijos()
        if len(fy):
            dyf = fy[None, :] - self.y[:, None]
            mitad_f = (fl[None, :] + C.AUTO_LARGO) / 2
            cerca_f = (dyf > -mitad_f) & (dyf < C.ALCANCE)
            adelante_f = (dyf > -2.0)[:, None, :] | _LATERAL[None, :, None]
            cubre_f = cerca_f[:, None, :] & adelante_f & (np.abs(X[:, :, None] - fx[None, None, :])
                                                          < (fw[None, None, :] + C.AUTO_ANCHO) / 2)
            d_f = np.where(cubre_f, np.maximum(dyf - (fl[None, :] + C.AUTO_LARGO) / 2, 0.0)[:, None, :],
                           np.inf).min(axis=2)
            menor = d_f < d_min
            v_rel = np.where(menor, -self.v[:, None] / 40.0, v_rel)
            d_min = np.minimum(d_min, d_f)
        prox_obs = 1.0 - np.minimum(d_min, C.ALCANCE) / C.ALCANCE
        yd = self.y[:, None] + _DS[None, :]
        fuera = np.abs(X[:, :, None] - p.centro(yd)[:, None, :]) > (p.semiancho(yd)[:, None, :]
                                                                    - C.AUTO_ANCHO / 2)
        hay = fuera.any(axis=2)
        primera = np.argmax(fuera, axis=2)
        d_orilla = np.where(hay, _DS[primera], C.ALCANCE)
        ahora = np.abs(X - c0[:, None]) > (h0[:, None] - C.AUTO_ANCHO / 2)
        d_orilla = np.where(ahora, 0.0, d_orilla)
        prox_orilla = 1.0 - d_orilla / C.ALCANCE
        partes += [prox_obs, v_rel, prox_orilla]
        fila = np.arange(n)
        ia = np.flatnonzero(self._arcoiris)
        if len(ia):
            dya = yt[ia][None, :] - self.y[:, None]
            arc = ~self.tomado[:, ia] & (dya > 0) & (dya < C.ALCANCE_ARCOIRIS)
            d_arc = np.where(arc, dya, np.inf)
            j = np.argmin(d_arc, axis=1)
            hay_arc = np.isfinite(d_arc[fila, j])
            xa = xt[fila, ia[j]]
            ancho_c = 2.0 * p.util(self.y) / 3.0
            self._arc_cerca = hay_arc & (d_arc[fila, j] < C.DIST_ALINEADO) \
                & (np.abs(xa - self.x) < ancho_c / 2)
            self._arc_idx = np.where(hay_arc, ia[j], -1)
            ancho_carril = 2.0 * p.util(self.y) / 3.0
            partes.append(np.where(hay_arc, np.clip((xa - self.x) / ancho_carril, -2, 2), 0.0)[:, None])
            partes.append(np.where(hay_arc, 1.0 - d_arc[fila, j] / C.ALCANCE_ARCOIRIS, 0.0)[:, None])
        else:
            partes += [np.zeros((n, 1)), np.zeros((n, 1))]
        return np.concatenate(partes, axis=1)

    def paso(self):
        if self.terminado:
            return
        obs = self.observar()
        self.obs = obs
        self._pasos += 1
        if self._pasos % C.MUESTRA_NORMALIZADOR == 0 and self.vivo.any():
            self.muestras.append(obs[self.vivo][::3])
        if self.controlador is not None:
            self.ctrl = np.clip(np.asarray(self.controlador(obs, self), dtype=float), -1, 1)
        else:
            self.ctrl, self.h, self.h2 = B.adelante(self.red, self.norm.aplicar(obs), self.h)
        self._premio_alineado()
        self._decidir_transito()
        dt = C.DT / C.SUBPASOS
        for _ in range(C.SUBPASOS):
            self.t += dt
            self._mover_transito(dt)
            self._fisica(dt)
        self._contar_rebases()
        self._revisar()

    def _premio_alineado(self):
        al = self._arc_cerca & self.vivo & (self.choque_t <= 0)
        nuevo = al & (self._arc_idx != self._arc_actual)
        self._arc_actual = np.where(nuevo, self._arc_idx, self._arc_actual)
        self._arc_seg = np.where(nuevo, 0.0, self._arc_seg)
        suma = np.where(al, np.minimum(C.DT, C.ALINEADO_MAX_S - self._arc_seg), 0.0)
        suma = np.maximum(suma, 0.0)
        self._arc_seg += suma
        self.alineado += suma

    def _contar_rebases(self):
        p = self.pista
        if not len(p.t_y0):
            return
        dy = p.y_transito(self.t)[None, :] - self.y[:, None]
        self._visto_adelante |= dy > 0
        margen = (p.t_largo + C.AUTO_LARGO)[None, :] / 2
        nuevo = (self._visto_adelante & (dy < -margen) & ~self._rebasado
                 & ~self._arcoiris[None, :] & (self.vivo & (self.choque_t <= 0))[:, None])
        if nuevo.any():
            self.rebases += nuevo.sum(axis=1)
            self._rebasado |= nuevo

    def correr(self, pasos):
        for _ in range(pasos):
            if self.terminado:
                break
            self.paso()

    def _decidir_transito(self):
        p = self.pista
        if not len(p.t_y0):
            return
        K = len(C.CARRILES)
        yt = p.y_transito(self.t)
        dy = yt[None, :] - self.y[:, None]
        cerca = (dy > 0) & (dy < C.DIST_REACCION) & self.vivo[:, None]
        obj = self.carril.copy()
        azul = self._es[C.AZUL][None, :] & cerca & ~self.iniciado
        obj = np.where(azul, np.clip(self.carril + p.t_dir[None, :], 0, K - 1), obj)
        pf = (self.x - p.centro(self.y)) / p.util(self.y)
        mio = _carril_de(pf)[:, None]
        mitad = (p.t_largo + C.AUTO_LARGO)[None, :] / 2
        cada = max(1, int(round(C.REACCION_ROJO / C.DT)))
        turno = ((self._pasos + np.arange(len(yt))) % cada == 0)[None, :]
        rojo = self._es[C.ROJO][None, :] & cerca & (dy > mitad + 3.0) & turno
        if rojo.any():
            obj = np.where(rojo, self.carril + np.sign(mio - self.carril), obj)
        if len(p.o_y):
            adelante = (p.o_y[None, :] - yt[:, None] > 0) & (p.o_y[None, :] - yt[:, None] < C.DIST_ESQUIVAR)
            jj, oo = np.nonzero(adelante)
            if len(jj):
                tapado = obj[:, jj] == p.o_carril[oo][None, :]
                alterno = np.where(p.o_carril[oo] == 1, 1 + p.t_dir[jj], 1)
                alterno = np.clip(alterno, 0, K - 1)
                for k_i in np.flatnonzero(tapado.any(axis=0)):
                    filas = tapado[:, k_i]
                    obj[filas, jj[k_i]] = alterno[k_i]
        pide = obj != self.carril
        if not pide.any():
            return
        bloqueado = np.zeros(pide.shape, dtype=np.int64)
        if len(p.par_a):
            a, b = p.par_a, p.par_b
            ocup_a = _carril_de(self.f[:, a])
            ocup_b = _carril_de(self.f[:, b])
            choca_a = pide[:, a] & ((self.carril[:, b] == obj[:, a]) | (ocup_b == obj[:, a])
                                    | (pide[:, b] & (obj[:, b] == obj[:, a])))
            choca_b = pide[:, b] & ((self.carril[:, a] == obj[:, b]) | (ocup_a == obj[:, b])
                                    | (pide[:, a] & (obj[:, a] == obj[:, b])))
            r, k = np.nonzero(choca_a)
            bloqueado[r, a[k]] = 1
            r, k = np.nonzero(choca_b)
            bloqueado[r, b[k]] = 1
        a_la_par = np.abs(dy) < mitad + C.HOLGURA_PAR
        bloqueado = bloqueado + (pide & a_la_par & (obj == mio))
        acepta = pide & (bloqueado == 0)
        self.carril = np.where(acepta, obj, self.carril)
        self.iniciado |= azul & acepta

    def _mover_transito(self, dt):
        p = self.pista
        destino = _CARRILES[self.carril]
        vel = np.where(self._es[C.ROJO], C.VEL_CIERRE, C.VEL_CAMBIO_CARRIL)[None, :] * dt
        paso = np.clip(destino - self.f, -vel, vel)
        se_mueve = paso != 0
        if se_mueve.any() and len(p.t_y0):
            xt, yt = self.transito_xy()
            dy = yt[None, :] - self.y[:, None]
            dx = self.x[:, None] - xt
            cerca = (np.abs(dy) < (p.t_largo + C.AUTO_LARGO)[None, :] / 2 + 0.5) \
                & (np.abs(dx) < (p.t_ancho + C.AUTO_ANCHO)[None, :] / 2 + 0.6) \
                & (np.sign(dx) == np.sign(paso)) & (self.choque_t <= 0)[:, None]
            paso = np.where(cerca & se_mueve, 0.0, paso)
        self.f = self.f + paso

    def _fisica(self, dt):
        p = self.pista
        act = self.vivo
        en_choque = act & (self.choque_t > 0)
        if en_choque.any():
            self.choque_t = np.where(en_choque, self.choque_t - dt, self.choque_t)
            listo = en_choque & (self.choque_t <= 0)
            if listo.any():
                self._reaparecer(listo)
            self.vx = np.where(en_choque, 0.0, self.vx)
            self.v = np.where(en_choque, 0.0, self.v)
        mueve = act & (self.choque_t <= 0)
        volante, acel, marcha = self.ctrl[:, 0], self.ctrl[:, 1], self.ctrl[:, 2]
        self.alto = np.where(mueve, marcha > 0, self.alto)
        v = self.v
        motor = np.where(self.alto,
                         C.ACEL_HIGH * np.clip(v / C.V_PAR_HIGH, 0.12, 1.0) * (1.0 - v / C.VMAX_HIGH),
                         C.ACEL_LOW * (1.0 - v / C.VMAX_LOW))
        a = np.where(acel > 0, acel * motor, acel * C.FRENO) - 0.15
        a = np.where(~self.alto & (v > C.VMAX_LOW), np.minimum(a, -C.FRENO_MOTOR), a)
        reversa = (acel < -0.3) & (v <= 0.5)
        v_nueva = np.where(reversa, np.maximum(v + acel * C.ACEL_REVERSA * dt, -C.V_REVERSA),
                           np.where(v < 0, v + np.maximum(a, 0.0) * dt + 2.0 * dt,
                                    np.maximum(v + a * dt, 0.0)))
        rap = np.abs(v)
        vlat = np.minimum(C.VLAT_MAX, C.VLAT_BASE + C.VLAT_POR_V * rap) * np.minimum(rap / 3.0, 1.0)
        derrapa = self.derrape_t > 0
        objetivo = volante * vlat * np.where(derrapa, C.DERRAPE_VOLANTE, 1.0)
        vx = self.vx + (objetivo - self.vx) * min(dt / C.TAU_LAT, 1.0)
        vx = vx + np.where(derrapa, self.derrape_dir * C.DERRAPE_EMPUJE * dt, 0.0)
        contra = derrapa & (volante * self.derrape_dir < -0.3)
        derrape_t = self.derrape_t - dt * (1.0 + C.DERRAPE_RECUPERA * contra)
        self.v = np.where(mueve, v_nueva, self.v)
        self.vx = np.where(mueve, vx, self.vx)
        self.derrape_t = np.where(mueve, np.maximum(derrape_t, 0.0), self.derrape_t)
        self.x = np.where(mueve, self.x + self.vx * dt, self.x)
        self.y = np.where(mueve, self.y + self.v * dt, self.y)
        self.golpe_t = np.maximum(self.golpe_t - dt, 0.0)
        por_m = C.COMBUSTIBLE_POR_M * (1.0 + C.COMBUSTIBLE_VEL * (self.v / C.VMAX_HIGH) ** 2)
        gasto = por_m * np.abs(self.v) * dt + C.COMBUSTIBLE_POR_S * dt
        self.combustible = np.where(act, self.combustible - gasto, self.combustible)

        c, h = p.centro(self.y), p.semiancho(self.y)
        lim = h - C.AUTO_ANCHO / 2
        fuera = mueve & (np.abs(self.x - c) > lim)
        choca = fuera & (self.v > C.V_CHOQUE_ORILLA)
        roza = fuera & ~choca
        self.x = np.where(roza, c + np.clip(self.x - c, -lim, lim), self.x)
        self.v = np.where(roza, self.v * (1 - 2 * dt), self.v)
        self.vx = np.where(roza, 0.0, self.vx)
        if choca.any():
            self.causas["choque_orilla"] += choca
            self._chocar(choca)

        mueve = act & (self.choque_t <= 0)
        for _ in range(3):
            if not self._contacto_transito(mueve):
                break
        self._contacto_fijos(mueve)

    def _contacto_transito(self, mueve):
        p = self.pista
        if not len(p.t_y0):
            return False
        xt, yt = self.transito_xy()
        dx = xt - self.x[:, None]
        dy = yt[None, :] - self.y[:, None]
        px = (C.AUTO_ANCHO + p.t_ancho[None, :]) / 2 - np.abs(dx)
        py = (C.AUTO_LARGO + p.t_largo[None, :]) / 2 - np.abs(dy)
        toca = mueve[:, None] & (px > 0) & (py > 0) & ~self.tomado
        m = C.ARCOIRIS_MARGEN
        roza = mueve[:, None] & (px > -m) & (py > -m) & ~self.tomado & self._arcoiris[None, :]
        if not (toca.any() or roza.any()):
            return False
        arc = roza
        if arc.any():
            self.combustible = self.combustible + C.COMBUSTIBLE_ARCOIRIS * arc.sum(axis=1)
            self.arcoiris_n += arc.sum(axis=1)
            self.tomado |= arc
        golpe = toca & ~self._arcoiris[None, :]
        g = golpe.any(axis=1)
        if not g.any():
            return False
        fila = np.arange(self.n)
        j = np.argmax(np.where(golpe, np.minimum(px, py), -np.inf), axis=1)
        pxj, pyj, dxj, dyj = px[fila, j], py[fila, j], dx[fila, j], dy[fila, j]
        vt = p.t_v[j]
        frontal = g & (pyj < pxj)
        lateral = g & ~frontal
        nuevo = g & (self.golpe_t <= 0)
        detras = frontal & (dyj > 0)
        rel = self.v - vt
        self.y = np.where(detras, self.y - pyj - 0.02, self.y)
        self.v = np.where(detras, np.maximum(vt - 0.25 * np.maximum(rel, 0.0), 0.0), self.v)
        delante = frontal & (dyj <= 0)
        self.y = np.where(delante, self.y + pyj + 0.02, self.y)
        self.v = np.where(delante, np.maximum(self.v, vt), self.v)
        lado = -np.sign(dxj)
        lado = np.where(lado == 0, 1.0, lado)
        self.x = np.where(lateral, self.x + lado * (pxj + 0.02), self.x)
        self.vx = np.where(lateral, lado * C.REBOTE_LATERAL, self.vx)
        derrapa = nuevo & (lateral | (detras & (rel > C.REL_DERRAPE)))
        self.derrape_t = np.where(derrapa, C.DERRAPE_T, self.derrape_t)
        self.derrape_dir = np.where(derrapa, lado, self.derrape_dir)
        self.derrapes += derrapa
        self.causas["golpe_lateral"] += derrapa & lateral
        self.causas["alcance"] += derrapa & ~lateral
        self.golpe_t = np.where(nuevo, C.ENFRIAMIENTO_GOLPE, self.golpe_t)
        return True

    def _contacto_fijos(self, mueve):
        p = self.pista
        if len(self.ay):
            pisa = (mueve[:, None] & (self.derrape_t <= 0)[:, None]
                    & (np.abs(self.ax[None, :] - self.x[:, None]) < 1.2 + C.AUTO_ANCHO / 2)
                    & (np.abs(self.ay[None, :] - self.y[:, None]) < 1.5 + C.AUTO_LARGO / 2))
            a = pisa.any(axis=1)
            if a.any():
                self.derrape_t = np.where(a, C.DERRAPE_T, self.derrape_t)
                self.derrape_dir = np.where(a, np.where(self.vx >= 0, 1.0, -1.0), self.derrape_dir)
                self.derrapes += a
                self.causas["aceite"] += a
        if len(self.oy):
            dx = self.ox[None, :] - self.x[:, None]
            dy = self.oy[None, :] - self.y[:, None]
            px = (C.AUTO_ANCHO + p.o_ancho[None, :]) / 2 - np.abs(dx)
            py = (C.AUTO_LARGO + p.o_largo[None, :]) / 2 - np.abs(dy)
            toca = mueve[:, None] & (px > 0) & (py > 0)
            g = toca.any(axis=1)
            if g.any():
                rapido = g & (self.v > C.V_CHOQUE_OBSTACULO)
                if rapido.any():
                    self.causas["choque_obstaculo"] += rapido
                    self._chocar(rapido)
                lento = g & ~rapido
                if lento.any():
                    fila = np.arange(self.n)
                    j = np.argmax(np.where(toca, np.minimum(px, py), -np.inf), axis=1)
                    pxj, pyj, dxj, dyj = px[fila, j], py[fila, j], dx[fila, j], dy[fila, j]
                    frontal = lento & (pyj < pxj)
                    self.y = np.where(frontal, self.y - np.sign(dyj) * (pyj + 0.02), self.y)
                    self.v = np.where(frontal, 0.0, self.v)
                    lat = lento & ~frontal
                    self.x = np.where(lat, self.x - np.sign(dxj) * (pxj + 0.02), self.x)
                    self.vx = np.where(lat, 0.0, self.vx)

    def _reaparecer(self, listo):
        p = self.pista
        c, h = p.centro(self.y), p.util(self.y)
        xt, yt = self.transito_xy()
        mejor_x = np.full(self.n, np.nan)
        for f in (C.CARRILES[1], C.CARRILES[0], C.CARRILES[2]):
            xc = c + f * h
            cerca = (np.abs(xt - xc[:, None]) < (C.AUTO_ANCHO + p.t_ancho[None, :]) / 2 + 0.4)                 & (yt[None, :] - self.y[:, None] > -14.0) & (yt[None, :] - self.y[:, None] < 8.0)                 & ~self._arcoiris[None, :]
            libre = ~cerca.any(axis=1) & np.isnan(mejor_x)
            mejor_x = np.where(libre, xc, mejor_x)
        ok = listo & ~np.isnan(mejor_x)
        self.x = np.where(ok, mejor_x, self.x)
        self.choque_t = np.where(listo & ~ok, 0.2, self.choque_t)

    def _chocar(self, m):
        self.choque_t = np.where(m, C.CHOQUE_ESPERA, self.choque_t)
        self.combustible = np.where(m, self.combustible - C.CHOQUE_COMBUSTIBLE, self.combustible)
        self.choques += m
        self.v = np.where(m, 0.0, self.v)
        self.vx = np.where(m, 0.0, self.vx)
        self.derrape_t = np.where(m, 0.0, self.derrape_t)

    def _revisar(self):
        p = self.pista
        act = self.vivo
        mejora = self.y > self.y_mejor + 20.0
        self.y_mejor = np.where(mejora, self.y, self.y_mejor)
        self.t_mejora = np.where(mejora, self.t, self.t_mejora)
        motivo = np.full(self.n, VIVO)
        motivo[self.t - self.t_mejora > C.SEG_ATASCADO] = ATASCADO
        motivo[self.t >= p.tiempo_max] = TIEMPO
        motivo[self.combustible <= 0] = SIN_COMBUSTIBLE
        motivo[self.y >= p.largo] = META
        fin = act & (motivo != VIVO)
        if fin.any():
            self.motivo = np.where(fin, motivo, self.motivo)
            self.t_fin = np.where(fin, self.t, self.t_fin)
            self.vivo = act & ~fin
            self.v = np.where(fin, 0.0, self.v)
            self.vx = np.where(fin, 0.0, self.vx)
        self.terminado = not self.vivo.any()

    def progreso(self):
        return np.minimum(self.y, self.pista.largo)

    def llegaron(self):
        return self.motivo == META

    def aptitud(self):
        p = self.pista
        f = C.PUNTOS_POR_M * self.progreso()
        meta = self.llegaron()
        t_ref = p.largo / C.V_REFERENCIA
        f = f + np.where(meta, C.PREMIO_META + C.PREMIO_RAPIDEZ * t_ref / np.maximum(self.t_fin, 1e-3)
                         + C.PUNTOS_COMBUSTIBLE * np.maximum(self.combustible, 0.0), 0.0)
        f = f + C.PREMIO_ARCOIRIS * self.arcoiris_n
        f = f + C.PREMIO_ALINEADO_S * self.alineado
        f = f + C.PREMIO_REBASE * self.rebases
        return f - C.CASTIGO_CHOQUE * self.choques - C.CASTIGO_DERRAPE * self.derrapes

    def velocidad_media_kmh(self):
        t = np.where(np.isnan(self.t_fin), self.t, self.t_fin)
        return self.progreso() / np.maximum(t, 1e-3) * 3.6

    def lider(self):
        y = np.where(self.vivo, self.y, -1.0)
        return int(np.argmax(y)) if self.vivo.any() else int(np.argmax(self.y))
