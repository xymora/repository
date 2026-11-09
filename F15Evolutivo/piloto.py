import math

import numpy as np

import config as C
from misiones import BLANCO, DESPEGUE, DETENER, PENDIENTE, PUNTO, TOQUE
from sensores import elevacion_pista
from terreno import superficie

G = C.GRAVEDAD


def _ang(a):
    return (a + np.pi) % (2 * np.pi) - np.pi


class Instructor:
    def __init__(self, n):
        self.n = n
        self.capturado = np.zeros(n, bool)

    def decidir(self, ep):
        f = ep.f
        n = ep.n
        rumbo, cab, alab = f.euler()
        V = np.maximum(f.v_aire, 1.0)
        agl = f.agl()
        tipos = ep._tipos()
        p = ep.punto_obj()
        if (tipos == BLANCO).any() and ep.drones.m:
            filas = np.arange(n)
            d_b = np.linalg.norm(p - f.pos, axis=1)
            tof = d_b / C.VEL_BALA
            guia = p + (ep.drones.vel[filas, ep.blanco_idx] - f.vel) * tof[:, None]
            guia[:, 1] += 0.5 * G * tof ** 2
            p = np.where(((tipos == BLANCO) & (d_b < 2500))[:, None], guia, p)
        rel = p - f.pos
        dh = np.hypot(rel[:, 0], rel[:, 2])
        rumbo_des = np.arctan2(rel[:, 0], -rel[:, 2])
        y_des = p[:, 1].copy()
        v_des = np.full(n, 200.0)
        tren = f.tren > 0.5
        lim_alab = np.full(n, math.radians(65))
        en_pista = np.zeros(n, bool)
        elev_p = elevacion_pista(ep)
        s_all = np.zeros(n)
        l_all = np.zeros(n)
        for k, o in enumerate(ep.obj):
            sel = ep.i == k
            if not sel.any():
                continue
            a = o["pista"]
            s, l = a.local(f.pos[sel, 0], f.pos[sel, 2])
            s_all[sel], l_all[sel] = s, l
            if o["vel"] is not None:
                v_des[sel] = o["vel"]
            if o["tren"] is not None:
                tren[sel] = o["tren"]
            t = o["tipo"]
            linea = t in (TOQUE, DETENER, DESPEGUE)
            alineado = np.ones(sel.sum(), bool)
            if t == PUNTO and o["tren"] is True:
                ps, pl = a.local(o["p"][0], o["p"][2])
                linea = abs(pl) < 1 and ps < 0
                if linea:
                    err_rw = np.abs(_ang(math.radians(a.rumbo) - rumbo[sel]))
                    entrada = np.full(len(s), ps - 3000)
                    alineado = ((np.abs(l) < 400) & (err_rw < 0.7) & (s < ps + 150)) | (s < entrada + 700)                         | self.capturado[sel]
                    self.capturado[sel] = alineado
                    ex = a.umbral[0] + a.ux * entrada
                    ez = a.umbral[1] + a.uz * entrada
                    idx = np.flatnonzero(sel)[~alineado]
                    rumbo_des[idx] = np.arctan2(ex[~alineado] - f.pos[idx, 0], -(ez[~alineado] - f.pos[idx, 2]))
            if not linea:
                self.capturado[sel] = False
            if linea:
                en_pista[sel] = alineado
                adelante = np.maximum(s + np.clip(V[sel] * 9, 300, 2500), 0 if t != PUNTO else -1e9)
                tx = a.umbral[0] + a.ux * adelante + a.px * 0
                tz = a.umbral[1] + a.uz * adelante + a.pz * 0
                desv = np.arctan2(tx - f.pos[sel, 0], -(tz - f.pos[sel, 2]))
                v_lat = f.vel[sel, 0] * a.px + f.vel[sel, 2] * a.pz
                corr = np.clip(-(l * 0.006 + v_lat * 0.045), -0.4, 0.4)
                rumbo_des[sel] = np.where(alineado, np.where(np.abs(l) < 250, math.radians(a.rumbo) + corr, desv),
                                          rumbo_des[sel])
                senda = a.elev + 15 + np.maximum(-s, 0) * PENDIENTE
                if t == TOQUE:
                    y_des[sel] = senda
                elif t == PUNTO:
                    y_des[sel] = np.where(alineado, senda, np.maximum(y_des[sel], senda))
                lim_alab[sel] = np.where(alineado, math.radians(30), math.radians(55))
            if t == DESPEGUE:
                tren[sel] = True
                v_des[sel] = 300
        vy_des = np.clip((y_des - f.pos[:, 1]) * 0.07, -40, 60)
        if True:
            sel = en_pista & np.isin(tipos, [PUNTO, TOQUE])
            vy_des = np.where(sel, -V * PENDIENTE + np.clip((y_des - f.pos[:, 1]) * 0.25, -8, 8), vy_des)
        vh = f.vel.copy()
        vh[:, 1] = 0
        vn = np.linalg.norm(vh, axis=1, keepdims=True) + 1e-3
        ad = vh / vn * np.clip(vn, 80, 300)
        h_ad = np.maximum(superficie(f.pos[:, 0] + ad[:, 0] * 8, f.pos[:, 2] + ad[:, 2] * 8),
                          superficie(f.pos[:, 0] + ad[:, 0] * 18, f.pos[:, 2] + ad[:, 2] * 18))
        libre = f.pos[:, 1] - h_ad
        peligro = (libre < 350) & ~en_pista & ~f.en_suelo
        vy_des = np.where(peligro, np.maximum(vy_des, np.minimum((400 - libre) * 0.1, 30)), vy_des)

        toque = tipos == TOQUE
        sobre = f.pos[:, 1] - elev_p
        flare = toque & (agl < 14)
        vy_des = np.where(flare, -0.6 - agl * 0.12, vy_des)

        gam = np.arcsin(np.clip(f.vel[:, 1] / V, -1, 1))
        gam_des = np.arcsin(np.clip(vy_des / V, -0.9, 0.9))
        err_r = _ang(rumbo_des - rumbo)
        err_r = np.where(np.abs(err_r) > 2.5, np.sign(alab + 1e-3) * np.abs(err_r), err_r)
        alab_des = np.clip(err_r * 2.2, -lim_alab, lim_alab)
        r_giro = V * V / (G * math.tan(math.radians(60)))
        dentro = (np.abs(err_r) > math.radians(70)) & (dh < 2.1 * r_giro) & ~en_pista
        alab_des = np.where(dentro, 0.0, alab_des)
        alab_des = np.where(flare | (agl < 25) & en_pista, np.clip(err_r * 1.5, -0.12, 0.12), alab_des)
        if (tipos == BLANCO).any():
            sel = tipos == BLANCO
            ang_b = np.arctan2(rel[:, 2], rel[:, 0])
            alab_des = np.where(sel, np.clip(err_r * 3, -1.35, 1.35), alab_des)
        ail = np.clip(2.6 * _ang(alab_des - alab) - 0.35 * f.w[:, 0], -1, 1)
        q_giro = G / V * np.tan(np.clip(alab, -1.3, 1.3)) * np.sin(alab) * np.cos(gam)
        q_des = 0.55 * (gam_des - gam) * np.cos(alab) + q_giro
        escala = np.where(q_des > 0, np.minimum(0.48, (C.G_MAX - 0.6) * G / V), np.minimum(0.4, 4.0 * G / V))
        elev = np.clip(q_des / escala + 1.2 * (q_des - f.w[:, 2]) - 0.25 * np.maximum(f.carga - 6, 0), -1, 1)
        gases = np.clip(0.55 + 0.025 * (v_des - V) + 0.004 * np.maximum(vy_des, 0), 0.05, 1.0)
        gases = np.where(toque & (agl < 10), 0.0, gases)
        freno = np.zeros(n)
        aerofreno = np.where(~f.en_suelo & (V > v_des + np.where(en_pista, 6, 30)), 1.0, 0.0)
        timon = np.zeros(n)

        suelo = f.en_suelo
        if suelo.any():
            err_p = np.zeros(n)
            for k, o in enumerate(ep.obj):
                sel = ep.i == k
                if sel.any():
                    err_p[sel] = _ang(math.radians(o["pista"].rumbo) - rumbo[sel])
            timon = np.where(suelo, np.clip(3.0 * err_p - 0.04 * l_all - 0.02 * np.tanh(f.w[:, 1]) * 0, -1, 1), timon)
            ail = np.where(suelo, np.clip(-1.5 * alab, -1, 1), ail)
            des = tipos == DESPEGUE
            rot = des & suelo & (V > 72)
            elev = np.where(des & suelo, np.where(rot, np.clip(3 * (math.radians(11) - cab) - f.w[:, 2], -1, 1), 0.0),
                            elev)
            gases = np.where(des, 1.0, gases)
            det = suelo & np.isin(tipos, [DETENER, TOQUE])
            gases = np.where(det, 0.0, gases)
            freno = np.where(det & (V < 75), 1.0, freno)
            aerofreno = np.where(det, 1.0, aerofreno)
            elev = np.where(det, np.clip(-0.4 * (cab - 0.0) - 0.05, -0.3, 0.2), elev)
        tren = np.where((agl > 40) & ~tren, False, tren | (agl < 40) & (tipos != PUNTO) & (tipos != BLANCO))
        tren = np.where(tipos == DESPEGUE, (agl < 8) | (f.vel[:, 1] < 2), tren)
        tren = tren & ((V < 135) | (f.tren > 0.97))
        fuego = (tipos == BLANCO) & (getattr(ep, "fijado_ir", np.zeros(n, bool)) |
                                    getattr(ep, "fijado_radar", np.zeros(n, bool)) & (dh < 20000))
        if (tipos == BLANCO).any() and ep.drones.m:
            d3 = np.linalg.norm(rel, axis=1)
            cerca = (tipos == BLANCO) & (d3 < C.ALCANCE_CANON)
            fuego = np.where(cerca, getattr(ep, "solucion_canon", np.zeros(n, bool)), fuego)
            duelo = (tipos == BLANCO) & (d3 < 5000) & (agl > 500)
            if duelo.any():
                direc = rel / np.maximum(d3, 1.0)[:, None]
                tb = np.einsum("nji,nj->ni", f.R, direc)
                fuera = np.arccos(np.clip(tb[:, 0], -1, 1))
                giro = np.arctan2(tb[:, 2], tb[:, 1])
                peso = np.clip(fuera / 0.06, 0, 1)
                ail_d = np.clip(2.2 * giro * peso - 0.3 * f.w[:, 0], -1, 1)
                plano = np.arctan2(np.hypot(tb[:, 1], tb[:, 2]) * np.sign(tb[:, 1] + 0.3 * np.abs(tb[:, 2])), tb[:, 0])
                elev_d = np.clip(4.0 * plano - 0.6 * f.w[:, 2] + 0.08 - 0.35 * np.maximum(f.carga - 6.0, 0)
                                 - 0.5 * f.sobre_g, -0.4, 1)
                v_obj = np.linalg.norm(ep.drones.vel[np.arange(n), ep.blanco_idx], axis=1) + \
                    np.clip((d3 - 500) / 15, -40, 70)
                gas_d = np.clip(0.6 + 0.03 * (v_obj - V), 0.2, 1.0)
                ail = np.where(duelo, ail_d, ail)
                elev = np.where(duelo, elev_d, elev)
                gases = np.where(duelo, gas_d, gases)
                aerofreno = np.where(duelo, (V > v_obj + 40).astype(float), aerofreno)
        bengala = ep.enemigos.alerta & (ep.t % 1.0 < C.PASO * 1.5)
        return {"elev": elev, "alabeo": ail, "timon": timon, "gases": gases, "freno": freno,
                "aerofreno": aerofreno, "tren": tren, "fuego": fuego, "bengala": bengala,
                "auto_arranque": True}
