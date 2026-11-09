import math

import numpy as np

import catalogo as K
import config as C
from arranque import Arranque, CONTROLES, DESPEGUE as PASO_DESPEGUE
from catalogo import (ARRANQUE, BLANCO, COMBATE, CURRICULO, DESPEGUE, DETENER, LECCIONES, PENDIENTE, PUNTO, TOQUE,
                      descripcion, escenario, nombre)
from fisica import Flota, MOTIVOS
from terreno import AEROPUERTOS, MITAD, superficie

NORTE = AEROPUERTOS[1]
NUMERO_LECCIONES = len(LECCIONES)
NOMBRES = tuple(nombre(k) for k in LECCIONES)
DESCRIPCIONES = tuple(descripcion(k) for k in LECCIONES)
NOMBRE_COMBATE = nombre(COMBATE)


class Drones:
    def __init__(self, n, specs):
        self.m = len(specs)
        self.pos = np.zeros((n, self.m, 3))
        self.vel = np.zeros((n, self.m, 3))
        self.giro = np.zeros((n, self.m))
        self.vivo = np.ones((n, self.m), bool)
        self.evade = np.zeros((n, self.m), bool)
        self.t_evade = np.zeros((n, self.m))
        self.alabeo = np.zeros((n, self.m))
        self.hostil = np.zeros((n, self.m), bool)
        for j, s in enumerate(specs):
            self.hostil[:, j] = s.get("hostil", False)
            r = s["rumbo"]
            self.pos[:, j] = s["pos"]
            self.vel[:, j] = np.array([math.sin(r), 0, -math.cos(r)]) * s["vel"]
            self.giro[:, j] = s["giro"]
            self.evade[:, j] = s.get("evade", False)

    def _perseguir(self, dt, obj_pos, obj_vel):
        h = self.hostil & self.vivo
        if not h.any():
            return
        tgt = obj_pos[:, None, :] + obj_vel[:, None, :] * 1.5
        des = tgt - self.pos
        suelo = superficie(self.pos[..., 0], self.pos[..., 2]) + 500
        des[..., 1] += np.maximum(suelo - self.pos[..., 1], 0) * 8
        v = self.vel
        V = np.linalg.norm(v, axis=-1) + 1e-6
        vh = v / V[..., None]
        quiebre = np.cross(vh, np.array([0, 1.0, 0])) * np.where((np.arange(self.m) % 2) == 0, 1, -1)[None, :, None]
        des = np.where((self.t_evade > 0)[..., None], quiebre * 1000 + vh * 300, des)
        dn = des / (np.linalg.norm(des, axis=-1, keepdims=True) + 1e-6)
        cos = np.clip(np.sum(vh * dn, -1), -1, 1)
        ang = np.arccos(cos)
        paso = np.minimum(ang, 6.5 * C.GRAVEDAD / V * dt)
        perp = dn - vh * cos[..., None]
        perp /= np.linalg.norm(perp, axis=-1, keepdims=True) + 1e-9
        nuevo = vh * np.cos(paso)[..., None] + perp * np.sin(paso)[..., None]
        giro_y = np.cross(vh, nuevo)[..., 1] / dt
        Vn = V + (255 - V) * 0.3 * dt
        self.vel = np.where(h[..., None], nuevo * Vn[..., None], self.vel)
        self.alabeo = np.where(h, -np.arctan(-giro_y * V / C.GRAVEDAD), self.alabeo)

    def paso(self, dt, amenaza, rng_val, obj_pos=None, obj_vel=None):
        if not self.m:
            return
        g = self.giro + np.where(self.t_evade > 0, 0.22 * np.sign(self.giro + 1e-3), 0.0)
        self.t_evade = np.maximum(self.t_evade - dt, 0)
        self.t_evade = np.where(amenaza & (self.t_evade <= 0), 6.0, self.t_evade)
        c, s = np.cos(g * dt), np.sin(g * dt)
        vx, vz = self.vel[..., 0].copy(), self.vel[..., 2].copy()
        pasivo = ~self.hostil
        self.vel[..., 0] = np.where(pasivo, vx * c - vz * s, vx)
        self.vel[..., 2] = np.where(pasivo, vx * s + vz * c, vz)
        h = superficie(self.pos[..., 0], self.pos[..., 2])
        self.vel[..., 1] += pasivo * (np.clip((h + 900 - self.pos[..., 1]) * 0.02, 0, 30) - self.vel[..., 1] * 0.05) * dt
        borde = np.hypot(self.pos[..., 0], self.pos[..., 2]) > MITAD * 0.8
        self.giro = np.where(borde & (np.abs(self.giro) < 0.1), 0.12, self.giro)
        self.alabeo = np.where(pasivo, np.arctan(g * np.linalg.norm(self.vel, axis=-1) / C.GRAVEDAD), self.alabeo)
        if obj_pos is not None:
            self._perseguir(dt, obj_pos, obj_vel)
        self.pos += self.vel * dt * self.vivo[..., None]
        choca = self.vivo & (self.pos[..., 1] < superficie(self.pos[..., 0], self.pos[..., 2]))
        self.vivo &= ~choca


class Misiles:
    MAX = 4

    def __init__(self, n):
        self.n = n
        self.activo = np.zeros((n, self.MAX), bool)
        self.pos = np.zeros((n, self.MAX, 3))
        self.vel = np.zeros((n, self.MAX, 3))
        self.t = np.zeros((n, self.MAX))
        self.blanco = np.zeros((n, self.MAX), int)
        self.tipo = np.zeros((n, self.MAX), int)
        self.estela = []

    def lanzar(self, mascara, pos, vel, R, blanco, tipo):
        libre = ~self.activo
        hay = mascara & libre.any(1)
        k = np.argmax(libre, 1)
        idx = np.flatnonzero(hay)
        if not len(idx):
            return hay
        k = k[idx]
        self.activo[idx, k] = True
        self.pos[idx, k] = pos[idx] - R[idx][..., 1] * 1.2
        self.vel[idx, k] = vel[idx] + R[idx][..., 0] * 20 - R[idx][..., 1] * 6
        self.t[idx, k] = 0
        self.blanco[idx, k] = blanco[idx]
        self.tipo[idx, k] = tipo[idx]
        return hay

    def paso(self, dt, drones, rng):
        if not drones.m:
            self.activo[:] = False
            return np.zeros((self.n, 0), bool)
        if not self.activo.any():
            return np.zeros((self.n, drones.m), bool)
        idx_n = np.arange(self.n)[:, None]
        bp = drones.pos[idx_n, self.blanco]
        bv = drones.vel[idx_n, self.blanco]
        bvivo = drones.vivo[idx_n, self.blanco]
        rel = bp - self.pos
        d = np.linalg.norm(rel, axis=-1) + 1e-6
        vr = bv - self.vel
        los = rel / d[..., None]
        w = np.cross(rel, vr) / (d * d)[..., None]
        vc = -np.sum(los * vr, -1)
        V = np.linalg.norm(self.vel, axis=-1) + 1e-6
        vh = self.vel / V[..., None]
        acc = 4.0 * np.maximum(vc, 50)[..., None] * np.cross(w, vh)
        gmax = np.where(self.tipo == 0, 40, 30) * C.GRAVEDAD
        an = np.linalg.norm(acc, axis=-1, keepdims=True)
        acc = acc * np.minimum(1, gmax[..., None] / (an + 1e-6))
        motor = np.where(self.t < np.where(self.tipo == 0, 5.0, 8.0), 260.0, 0.0)
        acc += vh * (motor - 0.00012 * V * V)[..., None]
        acc[..., 1] -= C.GRAVEDAD * 0.3
        acc *= bvivo[..., None]
        self.vel += acc * dt
        prev = self.pos.copy()
        self.pos += self.vel * dt
        self.t += dt
        seg = self.pos - prev
        tt = np.clip(np.sum((bp - prev) * seg, -1) / (np.sum(seg * seg, -1) + 1e-6), 0, 1)
        dmin = np.linalg.norm(prev + seg * tt[..., None] - bp, axis=-1)
        impacto = self.activo & bvivo & (dmin < 18)
        efectivo = impacto & (rng.random(impacto.shape) < np.where(self.tipo == 0, 0.8, 0.6))
        self.explota = impacto
        golpe = np.zeros((self.n, drones.m), bool)
        for j in range(drones.m):
            golpe[:, j] = (efectivo & (self.blanco == j)).any(1)
        suelo = self.pos[..., 1] < superficie(self.pos[..., 0], self.pos[..., 2])
        self.activo &= ~impacto & ~suelo & (self.t < 40) & ((V > 150) | (self.t < 3))
        return golpe


class ArmasEnemigas:
    MAX = 6

    def __init__(self, n, m, rng):
        self.n, self.m = n, m
        self.activo = np.zeros((n, self.MAX), bool)
        self.pos = np.zeros((n, self.MAX, 3))
        self.vel = np.zeros((n, self.MAX, 3))
        self.t = np.zeros((n, self.MAX))
        self.senuelo = np.zeros((n, self.MAX), bool)
        self.espera = rng.uniform(14, 28, (n, m))
        self.quedan = np.full((n, m), 2)
        self.impactos = np.zeros(n, int)
        self.alerta = np.zeros(n, bool)
        self.fijado = np.zeros(n, bool)
        self.disparan = np.zeros((n, m), bool)
        self.explota = np.zeros((n, self.MAX), bool)

    def bengalas(self, mascara, f, rng):
        cerca = self.activo & (np.linalg.norm(self.pos - f.pos[:, None, :], axis=-1) < 6000) & mascara[:, None]
        self.senuelo |= cerca & (rng.random(cerca.shape) < 0.6)

    def paso(self, dt, drones, f, rng):
        derribo = np.zeros(self.n, bool)
        self.explota = np.zeros((self.n, self.MAX), bool)
        if not drones.m or not drones.hostil.any():
            return derribo
        rel = f.pos[:, None, :] - drones.pos
        d = np.linalg.norm(rel, axis=-1) + 1e-6
        fw = drones.vel / (np.linalg.norm(drones.vel, axis=-1, keepdims=True) + 1e-6)
        adel = np.sum(rel * fw, -1) / d
        listo = drones.hostil & drones.vivo & f.vivo[:, None]
        self.fijado = (listo & (d < 12000) & (adel > 0.8)).any(1)
        self.espera -= dt
        puede = listo & (d < 9000) & (d > 1200) & (adel > math.cos(math.radians(25))) & (self.espera <= 0) & \
            (self.quedan > 0)
        for i, k in np.argwhere(puede):
            libre = np.flatnonzero(~self.activo[i])
            if not len(libre):
                continue
            s = libre[0]
            self.activo[i, s] = True
            self.senuelo[i, s] = False
            self.pos[i, s] = drones.pos[i, k] - fw[i, k] * 4
            self.vel[i, s] = drones.vel[i, k] + fw[i, k] * 20
            self.t[i, s] = 0
            self.espera[i, k] = rng.uniform(9, 16)
            self.quedan[i, k] -= 1
        self.disparan = puede
        if self.activo.any():
            bp = f.pos[:, None, :]
            bv = f.vel[:, None, :]
            r = bp - self.pos
            dm = np.linalg.norm(r, axis=-1) + 1e-6
            vr = bv - self.vel
            w = np.cross(r, vr) / (dm * dm)[..., None]
            vc = -np.sum(r / dm[..., None] * vr, -1)
            V = np.linalg.norm(self.vel, axis=-1) + 1e-6
            vh = self.vel / V[..., None]
            acc = 4.0 * np.maximum(vc, 50)[..., None] * np.cross(w, vh)
            an = np.linalg.norm(acc, axis=-1, keepdims=True)
            acc = acc * np.minimum(1, 28 * C.GRAVEDAD / (an + 1e-6)) * ~self.senuelo[..., None]
            acc += vh * (np.where(self.t < 4.5, 240.0, 0.0) - 0.00013 * V * V)[..., None]
            acc[..., 1] -= C.GRAVEDAD * np.where(self.senuelo, 1.0, 0.3)
            prev = self.pos.copy()
            self.vel += acc * dt
            self.pos += self.vel * dt
            self.t += dt
            seg = self.pos - prev
            tt = np.clip(np.sum((bp - prev) * seg, -1) / (np.sum(seg * seg, -1) + 1e-6), 0, 1)
            dmin = np.linalg.norm(prev + seg * tt[..., None] - bp, axis=-1)
            fuera = np.sum(vh * r / dm[..., None], -1) < 0.3
            self.senuelo |= self.activo & fuera & (self.t > 1.5)
            golpe = self.activo & ~self.senuelo & (dmin < 15) & f.vivo[:, None]
            self.explota = golpe
            derribo |= (golpe & (rng.random(golpe.shape) < 0.6)).any(1)
            suelo = self.pos[..., 1] < superficie(self.pos[..., 0], self.pos[..., 2])
            self.activo &= ~golpe & ~suelo & (self.t < 30) & ((V > 170) | (self.t < 3))
        cerca = np.linalg.norm(self.pos - f.pos[:, None, :], axis=-1) < 9000
        self.alerta = (self.activo & ~self.senuelo & cerca).any(1)
        cañon = listo & (d < 900) & (adel > 0.996)
        tiro = cañon & (rng.random(cañon.shape) < 0.35 * dt)
        self.impactos += tiro.sum(1)
        derribo |= self.impactos >= 5
        return derribo


class Episodio:
    def __init__(self, numero, n, semilla, demora_fin=0.0, manual=False, frio=False):
        self.numero = numero
        self.manual = manual
        self.n = n
        self.semilla = semilla
        self.rng = np.random.default_rng(semilla + 7)
        esc = escenario(numero, semilla)
        extra = 0.0
        if frio and not esc["frio"] and esc["inicio"]["vel"] < 1:
            pista = next((o["pista"] for o in esc["objetivos"] if o["tipo"] == DESPEGUE), K.BASE)
            esc["objetivos"] = [K.objetivo(ARRANQUE, pista=pista, radio=0, vel=0.0, tren=True)] + esc["objetivos"]
            esc["frio"] = True
            extra = C.DURACION_ARRANQUE
        self.esc = esc
        self.obj = esc["objetivos"]
        self.k = len(self.obj)
        self.f = Flota(n)
        ini = esc["inicio"]
        idx = np.arange(n)
        self.f.colocar(idx, np.tile(ini["pos"], (n, 1)), ini["rumbo"], ini.get("cabeceo", 0.0), 0.0,
                       ini["vel"], ini["tren"], ini["gases"], frio=esc["frio"])
        self.arranque = Arranque(n, esc["frio"])
        self.f.viento[:] = esc["viento"]
        self.turb = esc["turbulencia"]
        self.fase = self.rng.uniform(0, 100, 3)
        self.drones = Drones(n, esc["drones"])
        self.misiles = Misiles(n)
        self.enemigos = ArmasEnemigas(n, self.drones.m, self.rng)
        self.blanco_idx = np.zeros(n, int)
        self.bengalas = np.full(n, 30)
        self.solto_bengala = np.zeros(n, bool)
        self.fijado_radar = np.zeros(n, bool)
        self.fijado_ir = np.zeros(n, bool)
        self.dist_blanco = np.full(n, 1e9)
        self.misiles_quedan = np.full(n, int(esc.get("misiles", 4)))
        self.municion = np.full(n, 940)
        self.enfriar = np.zeros(n)
        self.disparando = np.zeros(n, bool)
        self.solucion_canon = np.zeros(n, bool)
        self.impactos_canon = np.zeros(n, int)
        self.i = np.zeros(n, int)
        self.d0 = np.ones(n)
        self.mejor = np.zeros(n)
        self.terminado = np.zeros(n, bool)
        self.exito = np.zeros(n, bool)
        self.cayo = np.zeros(n, bool)
        self.libre = np.zeros(n, bool)
        self.t = 0.0
        self.t_fin = np.zeros(n)
        self.duracion = K.duracion(numero) + extra
        self.calidad = np.zeros(n)
        self.castigo = np.zeros(n)
        self.brusco = np.zeros(n)
        self.t_aire = np.zeros(n)
        self.t_exceso = np.zeros(n)
        self.mando_prev = None
        self.toque_ok = np.zeros(n, bool)
        self.toque_vy = np.zeros(n)
        self.mensaje = [""] * n
        self.bajas = np.zeros(n, int)
        self.tiempo_obj = np.zeros(n)
        self.demora_fin = demora_fin
        self.aterriza = bool(self.obj[-1].get("final")) or self.obj[-1]["tipo"] in (TOQUE, DETENER)
        self._activar(np.ones(n, bool))

    def objetivo(self, i):
        return self.obj[min(i, self.k - 1)]

    def punto_obj(self):
        p = np.zeros((self.n, 3))
        for k, o in enumerate(self.obj):
            sel = self.i == k
            if not sel.any():
                continue
            if o["tipo"] == PUNTO:
                p[sel] = o["p"]
            elif o["tipo"] == BLANCO:
                p[sel] = self.drones.pos[sel, self.blanco_idx[sel]]
            elif o["tipo"] in (DESPEGUE, ARRANQUE):
                a = o["pista"]
                p[sel] = a.mundo(a.largo * 0.7, 0, a.elev + 120)
            elif o["tipo"] == TOQUE:
                a = o["pista"]
                p[sel] = a.mundo(380, 0, a.elev)
            else:
                a = o["pista"]
                s, _ = a.local(self.f.pos[sel, 0], self.f.pos[sel, 2])
                p[sel] = np.stack([a.umbral[0] + a.ux * (s + 60), np.full(len(s), a.elev),
                                   a.umbral[1] + a.uz * (s + 60)], 1)
        return p

    def _activar(self, mascara):
        if not mascara.any():
            return
        p = self.punto_obj()
        d = np.linalg.norm(p - self.f.pos, axis=1)
        v = np.maximum(self.f.v_aire, np.linalg.norm(self.f.vel, axis=1))
        self.d0 = np.where(mascara, np.maximum(np.where(self._tipos() == DETENER, v, d), 1.0), self.d0)
        self.mejor = np.where(mascara, 0.0, self.mejor)
        self.tiempo_obj = np.where(mascara, 0.0, self.tiempo_obj)

    def _tipos(self):
        return np.array([o["tipo"] for o in self.obj])[np.minimum(self.i, self.k - 1)]

    def progreso(self):
        return np.clip((self.i + self.mejor) / self.k, 0, 1)

    def avanzar(self, mascara):
        mascara = mascara & ~self.terminado
        if not mascara.any():
            return
        self.calidad += mascara * 1.0
        self.i = self.i + mascara
        fin = mascara & (self.i >= self.k)
        self.exito |= fin
        self._cerrar(fin, "lección completada")
        self.i = np.minimum(self.i, self.k)
        self._activar(mascara & ~fin)

    def _cerrar(self, mascara, texto):
        mascara = mascara & ~self.terminado
        self.terminado |= mascara
        self.t_fin = np.where(mascara, self.t, self.t_fin)
        for j in np.flatnonzero(mascara):
            self.mensaje[j] = texto

    def punteria(self, filas, bi):
        f = self.f
        rel = self.drones.pos[filas, bi] - f.pos
        tof = np.linalg.norm(rel, axis=1) / C.VEL_BALA
        mira = rel + (self.drones.vel[filas, bi] - f.vel) * tof[:, None]
        mira[:, 1] += 0.5 * C.GRAVEDAD * tof ** 2
        return np.einsum("ni,ni->n", mira, f.R[..., 0]) / (np.linalg.norm(mira, axis=1) + 1e-6)

    def armas(self, fuego, canon=None):
        f = self.f
        manual = np.zeros(self.n, bool) if canon is None else np.asarray(canon, float) >= 0
        pide = np.zeros(self.n, bool) if canon is None else np.asarray(canon, float) > 0
        if not self.drones.m:
            self.disparando = manual & pide & (self.municion > 0) & f.vivo
            self.municion = np.maximum(self.municion - self.disparando * C.BALAS_POR_PASO, 0)
            return
        rel_t = self.drones.pos - f.pos[:, None, :]
        d_t = np.linalg.norm(rel_t, axis=-1) + 1e-6
        adel_t = np.einsum("nki,ni->nk", rel_t, f.R[..., 0]) / d_t
        puntaje = np.where(self.drones.vivo, d_t * (2.2 - adel_t), np.inf)
        self.blanco_idx = np.argmin(puntaje, 1)
        filas = np.arange(self.n)
        bi = self.blanco_idx
        d = d_t[filas, bi]
        adel = adel_t[filas, bi]
        vivo_b = self.drones.vivo[filas, bi]
        self.fijado_radar = vivo_b & (d < 30000) & (adel > math.cos(math.radians(60)))
        self.fijado_ir = vivo_b & (d < 9000) & (adel > math.cos(math.radians(22)))
        self.dist_blanco = d
        self.frente_blanco = adel
        self.enfriar = np.maximum(self.enfriar - C.PASO, 0)
        zona = vivo_b & (d < C.ALCANCE_CANON)
        gatillo = np.where(manual, pide, fuego & (zona | (self.misiles_quedan <= 0)))
        apunta = self.punteria(filas, bi)
        self.solucion_canon = zona & (apunta > C.CONO_CANON)
        cañon = gatillo & vivo_b & (apunta > C.CONO_CANON) & (self.municion > 0) & f.vivo
        self.disparando = gatillo & (self.municion > 0) & f.vivo
        self.municion = np.maximum(self.municion - self.disparando * C.BALAS_POR_PASO, 0)
        prob = np.clip(0.09 * np.exp(-1.2 * d / C.ALCANCE_CANON) * (apunta - C.CONO_CANON) / (1 - C.CONO_CANON), 0, 0.12)
        derribo_c = cañon & (self.rng.random(self.n) < prob)
        self.impactos_canon += derribo_c
        lanza = fuego & (self.enfriar <= 0) & (self.misiles_quedan > 0) & f.vivo & \
            (self.fijado_ir | self.fijado_radar) & (d > 800)
        lanza &= ~(zona & ~manual)
        tipo = np.where(self.fijado_ir, 0, 1)
        ok = self.misiles.lanzar(lanza, f.pos, f.vel, f.R, bi, tipo)
        self.misiles_quedan -= ok
        self.enfriar = np.where(ok, 2.5, self.enfriar)
        self.lanzo = ok
        g = np.zeros((self.n, self.drones.m), bool)
        g[filas, bi] = derribo_c
        self._derribar(g)

    def _derribar(self, golpe):
        nuevo = golpe & self.drones.vivo
        self.drones.vivo &= ~nuevo
        self.bajas += nuevo.sum(1)
        self.ultimo_derribo = nuevo.any(1)

    def paso(self, acciones=None):
        f = self.f
        dt = C.PASO
        self.lanzo = np.zeros(self.n, bool)
        self.ultimo_derribo = np.zeros(self.n, bool)
        if acciones is not None:
            for clave in ("elev", "alabeo", "timon", "gases", "freno"):
                f.entrada[clave] = np.where(self.terminado & ~self.libre, f.entrada[clave], acciones[clave])
            if "tren" in acciones:
                f.cmd_tren = np.where(acciones["tren"], 1.0, 0.0)
                f.cmd_flaps = np.where(acciones.get("flaps", acciones["tren"]), 1.0, 0.0)
            if "aerofreno" in acciones:
                f.cmd_aerofreno = np.asarray(acciones["aerofreno"], dtype=np.float64)
            fuego = acciones.get("fuego", np.zeros(self.n, bool))
        else:
            fuego = np.zeros(self.n, bool)
        self._piloto_fin()
        auto = not self.manual or acciones is not None and bool(np.any(acciones.get("auto_arranque", False)))
        self._bloquear(auto)
        tt = self.t + self.fase
        f.rafaga[:] = self.turb * np.array([np.sin(tt[0] * 0.7) + 0.5 * np.sin(tt[0] * 2.3),
                                             0.6 * np.sin(tt[1] * 1.1) + 0.3 * np.sin(tt[1] * 3.1),
                                             np.sin(tt[2] * 0.9) + 0.5 * np.sin(tt[2] * 1.9)])
        quieto = self.terminado & f.en_suelo
        if quieto.any():
            f.entrada["gases"][quieto] = 0
            f.entrada["freno"][quieto] = 1
        f.paso(dt)
        self.arranque.paso(f, dt, f.entrada)
        amenaza = np.zeros((self.n, self.drones.m), bool)
        if self.drones.m:
            dist = np.linalg.norm(self.misiles.pos[:, :, None, :] - self.drones.pos[:, None, :, :], axis=-1)
            amenaza = (self.misiles.activo[..., None] & (dist < 4000)).any(1)
        self.drones.paso(dt, amenaza, self.rng, f.pos, f.vel)
        self.armas(fuego, acciones.get("canon") if acciones is not None else None)
        self._derribar(self.misiles.paso(dt, self.drones, self.rng))
        if acciones is not None and "bengala" in acciones:
            suelta = np.asarray(acciones["bengala"], bool) & (self.bengalas > 0) & f.vivo
            self.bengalas -= suelta
            self.solto_bengala = suelta
            self.enemigos.bengalas(suelta, f, self.rng)
        else:
            self.solto_bengala = np.zeros(self.n, bool)
        f.estrellar(self.enemigos.paso(dt, self.drones, f, self.rng), 5)
        self.t += dt
        self._evaluar()

    def _piloto_fin(self):
        f = self.f
        sel = self.terminado & self.exito & f.vivo & ~f.en_suelo & ~self.libre
        if not sel.any():
            return
        _, cab, alab = f.euler()
        V = np.maximum(f.v_aire, 1.0)
        agl = f.agl()
        aterriza = self.aterriza
        if aterriza:
            vy_des = np.where(agl < 14, -0.6 - agl * 0.12, -V * PENDIENTE)
            v_des = 80.0
        else:
            vy_des = np.clip((agl < 600) * (600 - agl) * 0.05, 0, 20)
            v_des = 200.0
        gam = np.arcsin(np.clip(f.vel[:, 1] / V, -1, 1))
        gam_des = np.arcsin(np.clip(vy_des / V, -0.9, 0.9))
        q_des = 0.55 * (gam_des - gam) * np.cos(alab)
        escala = np.where(q_des > 0, np.minimum(0.48, (C.G_MAX - 0.6) * C.GRAVEDAD / V), np.minimum(0.4, 4.0 * C.GRAVEDAD / V))
        elev = np.clip(q_des / escala + 1.2 * (q_des - f.w[:, 2]), -1, 1)
        ail = np.clip(-2.6 * alab - 0.35 * f.w[:, 0], -1, 1)
        gases = np.clip(0.55 + 0.025 * (v_des - V), 0.05, 1.0)
        if aterriza:
            gases = np.where(agl < 10, 0.0, gases)
        f.entrada["elev"] = np.where(sel, elev, f.entrada["elev"])
        f.entrada["alabeo"] = np.where(sel, ail, f.entrada["alabeo"])
        f.entrada["timon"] = np.where(sel, 0.0, f.entrada["timon"])
        f.entrada["gases"] = np.where(sel, gases, f.entrada["gases"])
        if aterriza:
            f.cmd_tren = np.where(sel, 1.0, f.cmd_tren)
            f.cmd_flaps = np.where(sel, 1.0, f.cmd_flaps)
            f.cmd_aerofreno = np.where(sel, 0.0, f.cmd_aerofreno)

    def _bloquear(self, auto):
        ar = self.arranque
        bloq = ar.bloqueo() & ~self.terminado
        if not np.any(bloq):
            return
        f = self.f
        if auto:
            ar.automata(f, bloq)
            f.cmd_flaps = np.where(bloq, (ar.estado >= CONTROLES).astype(float), f.cmd_flaps)
        f.entrada["gases"] = np.where(bloq, 0.0, f.entrada["gases"])
        f.entrada["freno"] = np.where(bloq, 1.0, f.entrada["freno"])
        f.cmd_tren = np.where(bloq, 1.0, f.cmd_tren)
        f.cmd_aerofreno = np.where(bloq, 0.0, f.cmd_aerofreno)
        if auto:
            for clave in ("elev", "alabeo", "timon"):
                f.entrada[clave] = np.where(bloq, 0.0, f.entrada[clave])
        for j in np.flatnonzero(bloq & (ar.t_bit >= 0)):
            b = ar.barrido(j)
            if b is not None:
                f.entrada[b[0]][j] = b[1]

    def _evaluar(self):
        f = self.f
        dt = C.PASO
        activo = ~self.terminado
        caido = activo & ~f.vivo
        for j in np.flatnonzero(caido):
            self.mensaje[j] = MOTIVOS[f.motivo[j]]
        self.terminado |= caido
        self.cayo |= caido
        self.t_fin = np.where(caido, self.t, self.t_fin)
        activo = ~self.terminado
        fuera = activo & (np.maximum(np.abs(f.pos[:, 0]), np.abs(f.pos[:, 2])) > MITAD * 1.1) & \
            (self.numero not in (0, COMBATE))
        self._cerrar(fuera, MOTIVOS[7])
        self.castigo += fuera * 15
        tiempo = activo & (self.t >= self.duracion)
        self._cerrar(tiempo, "tiempo agotado")
        activo = ~self.terminado
        self.tiempo_obj += dt
        V = f.v_aire
        agl = f.agl()
        tipos = self._tipos()
        p = self.punto_obj()
        d = np.linalg.norm(p - f.pos, axis=1)
        avanza = np.zeros(self.n, bool)
        parcial = np.zeros(self.n)
        for k, o in enumerate(self.obj):
            sel = activo & (self.i == k)
            if not sel.any():
                continue
            t = o["tipo"]
            a = o["pista"]
            if t == PUNTO:
                parcial[sel] = np.clip(1 - d[sel] / self.d0[sel], 0, 1) * 0.9
                hd = np.hypot(p[:, 0] - f.pos[:, 0], p[:, 2] - f.pos[:, 2])
                ok = sel & (hd < o["radio"]) & (np.abs(p[:, 1] - f.pos[:, 1]) < max(o["radio"], 60))
                if o["tren"] is False:
                    ok &= f.tren < 0.05
                    self.castigo += (sel & (f.tren > 0.5) & (self.tiempo_obj > 25)) * dt * 0.3
                if o["vel"] is not None:
                    self.calidad += sel * np.exp(-np.abs(V - o["vel"]) / 30) * dt * 0.02
                avanza |= ok
            elif t == ARRANQUE:
                parcial = np.where(sel, np.minimum(self.arranque.estado, PASO_DESPEGUE) / PASO_DESPEGUE * 0.9, parcial)
                avanza |= sel & (self.arranque.estado >= PASO_DESPEGUE)
            elif t == DESPEGUE:
                s, l = a.local(f.pos[:, 0], f.pos[:, 2])
                parcial = np.where(sel, np.clip(V / 85, 0, 1) * 0.5 + np.clip(agl / 40, 0, 1) * 0.4, parcial)
                sale = sel & f.en_suelo & ~a.en_pista(f.pos[:, 0], f.pos[:, 2], 4)
                self._cerrar(sale, MOTIVOS[6])
                self.castigo += sale * 10
                self.calidad -= sel * f.en_suelo * np.abs(l) / 22 * dt * 0.05
                avanza |= sel & ~f.en_suelo & (agl > 35) & (V > 80)
            elif t == TOQUE:
                s, l = a.local(f.pos[:, 0], f.pos[:, 2])
                cerca = np.clip(1 - np.hypot(np.maximum(-s, 0), l) / 3000, 0, 1)
                parcial = np.where(sel, cerca * 0.6 + np.clip(1 - agl / 60, 0, 1) * 0.3 * cerca, parcial)
                toco = sel & f.en_suelo
                en_pista = a.en_pista(f.pos[:, 0], f.pos[:, 2])
                malo = toco & (~en_pista | (s > a.largo * 0.6))
                self._cerrar(malo, "toque fuera de la pista")
                self.castigo += malo * 8
                bueno = toco & ~malo
                vy = -f.toque_vy
                self.toque_vy = np.where(bueno, vy, self.toque_vy)
                self.calidad += bueno * (np.exp(-np.maximum(vy - 0.8, 0) / 1.5) * 3 + np.exp(-np.abs(l) / 6) * 2
                                         + np.exp(-np.abs(s - 400) / 300) * 2)
                avanza |= bueno
                pasado = sel & (s > a.largo) & ~f.en_suelo
                self._cerrar(pasado, "se pasó de la pista")
            elif t == DETENER:
                s, l = a.local(f.pos[:, 0], f.pos[:, 2])
                vs = np.linalg.norm(f.vel, axis=1)
                parcial = np.where(sel, np.clip(1 - vs / self.d0, 0, 1) * 0.95, parcial)
                sale = sel & ~a.en_pista(f.pos[:, 0], f.pos[:, 2], 6)
                self._cerrar(sale, MOTIVOS[6])
                self.castigo += sale * 6
                rebote = sel & ~f.en_suelo & (agl > 6)
                self.castigo += rebote * dt * 2
                avanza |= sel & (vs < 3) & f.en_suelo
            else:
                rel = np.clip(1 - d / self.d0, 0, 1)
                caidos = self.bajas / max(self.drones.m, 1)
                parcial = np.where(sel, np.minimum(caidos + rel * 0.7 * (1 - caidos), 0.95), parcial)
                avanza |= sel & ~self.drones.vivo.any(1)
        self.mejor = np.where(activo, np.maximum(self.mejor, parcial), self.mejor)
        self.castigo += (activo & (f.carga > C.G_MAX + 0.5)) * dt * 0.5
        self._actitud(activo, p, agl, tipos, dt)
        self.castigo += (activo & f.dano_tren) * dt * 0.2
        self.avanzar(avanza)

    def _actitud(self, activo, p, agl, tipos, dt):
        f = self.f
        aire = activo & ~f.en_suelo & (agl > 15) & ~self.arranque.bloqueo()
        mando = np.stack([f.entrada["elev"], f.entrada["alabeo"]], 1)
        cambio = np.zeros(self.n) if self.mando_prev is None else np.abs(mando - self.mando_prev).sum(1) / dt
        self.mando_prev = mando
        if not aire.any():
            return
        rumbo, _, alabeo = f.euler()
        rumbo_obj = np.arctan2(p[:, 0] - f.pos[:, 0], -(p[:, 2] - f.pos[:, 2]))
        error = np.abs((rumbo_obj - rumbo + np.pi) % (2 * np.pi) - np.pi)
        maniobra = np.isin(tipos, (BLANCO,))
        permitido = np.where(maniobra, C.ALABEO_MAX, np.clip(error * C.ALABEO_POR_ERROR, C.ALABEO_LIBRE, C.ALABEO_MAX))
        exceso = np.maximum(np.abs(alabeo) - permitido, 0)
        self.t_exceso = np.where(aire & (exceso > 0.05), self.t_exceso + dt, 0.0)
        exceso = exceso * (self.t_exceso > C.ALABEO_TOLERANCIA)
        invertido = (f.R[:, 1, 1] < 0) & ~maniobra
        actividad = np.abs(f.w[:, 0]) * ~maniobra
        cabeceo = np.abs(f.w[:, 2]) * ~maniobra
        trato = np.maximum(f.carga - np.where(maniobra, C.G_COMBATE, C.G_COMODO), 0) * 0.3 + \
            np.maximum(C.G_NEG_COMODO - f.carga, 0)
        malo = exceso + 1.5 * invertido + actividad + 0.5 * cabeceo + C.PESO_MANDO * cambio * np.where(maniobra, 0.5, 1.0) + trato + 4 * f.sobre_g
        self.brusco += aire * malo * dt
        self.t_aire += aire * dt

    def sobrante(self):
        return np.maximum(self.brusco - C.BRUSCO_LIBRE * self.t_aire, 0)

    def estabilidad(self):
        return np.exp(-self.sobrante() / np.maximum(self.t_aire, 20.0) / C.ESTABILIDAD_ESCALA)

    @property
    def acabado(self):
        return bool(self.terminado.all())

    def rodando(self):
        f = self.f
        if not self.aterriza:
            return np.zeros(self.n, bool)
        parado = f.en_suelo & (np.linalg.norm(f.vel, axis=1) < 3)
        return self.terminado & self.exito & f.vivo & ~parado & (self.t - self.t_fin < 150)

    @property
    def reposo(self):
        return self.acabado and not self.rodando().any()

    def componentes(self, j):
        t = float(self.t_fin[j]) if self.terminado[j] else self.t
        return {"progreso": 100 * float(self.progreso()[j]), "calidad": 4 * float(self.calidad[j]),
                "castigo": -float(self.castigo[j]), "vuelo brusco": -C.PESO_BRUSCO * float(self.sobrante()[j]),
                "caída": -20.0 if self.cayo[j] else 0.0,
                "éxito": 60 + 20 * max(0.0, 1 - t / self.duracion) if self.exito[j] else 0.0}

    def aptitudes(self):
        t = np.where(self.terminado, self.t_fin, self.t)
        return 100 * self.progreso() + 4 * self.calidad - self.castigo - C.PESO_BRUSCO * self.sobrante() - \
            20.0 * self.cayo + self.exito * (60 + 20 * np.maximum(0.0, 1 - t / self.duracion))

    def resumen(self, j):
        prog = float(self.progreso()[j])
        cae = bool(self.cayo[j])
        apt = sum(self.componentes(j).values())
        return {"aptitud": apt, "progreso": prog, "superada": bool(self.exito[j]), "estrellado": cae,
                "motivo": self.mensaje[j] or "", "bajas": int(self.bajas[j]), "g_max": float(self.f.g_max[j]),
                "toque_vy": float(self.toque_vy[j]), "estabilidad": float(self.estabilidad()[j])}
