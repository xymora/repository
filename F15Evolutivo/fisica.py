import numpy as np

import config as C
from terreno import altura, superficie

G = C.GRAVEDAD
QREF = 5200.0
INERCIA = np.array([3.2e4, 1.85e5, 1.6e5])
RUEDAS = np.array([[5.05, -2.15, 0.0], [-0.65, -2.15, -1.38], [-0.65, -2.15, 1.38]])
CASCO = np.array([[9.7, 0.0, 0.0], [-9.4, 0.3, 0.0], [1.0, -1.05, 0.0], [-3.6, 0.0, -6.5], [-3.6, 0.0, 6.5],
                  [-8.3, 3.5, -1.55], [-8.3, 3.5, 1.55], [-0.65, -1.2, -1.38], [-0.65, -1.2, 1.38],
                  [-8.6, 0.0, -4.3], [-8.6, 0.0, 4.3]])
K_RUEDA = 2.7e5
D_RUEDA = 5.2e4
BRAZO_MOTOR = 0.64
N2_IDLE = 0.62
N2_ENCENDIDO = 0.18
MOTIVOS = ("", "impacto contra el terreno", "tren colapsado", "estructura rota por exceso de G",
           "amerizaje", "derribado", "salida de pista", "fuera de la zona")


def _suave(x):
    x = np.clip(x, 0.0, 1.0)
    return x * x * (3 - 2 * x)


def qmul(a, b):
    aw, ax, ay, az = a[..., 0], a[..., 1], a[..., 2], a[..., 3]
    bw, bx, by, bz = b[..., 0], b[..., 1], b[..., 2], b[..., 3]
    return np.stack([aw * bw - ax * bx - ay * by - az * bz, aw * bx + ax * bw + ay * bz - az * by,
                     aw * by - ax * bz + ay * bw + az * bx, aw * bz + ax * by - ay * bx + az * bw], -1)


def q_eje(eje, ang):
    eje = np.asarray(eje, dtype=np.float64)
    ang = np.asarray(ang, dtype=np.float64)
    s = np.sin(ang / 2)[..., None]
    return np.concatenate([np.cos(ang / 2)[..., None], eje * s], -1)


def q_euler(rumbo, cabeceo, alabeo):
    rumbo, cabeceo, alabeo = np.broadcast_arrays(*(np.asarray(v, dtype=np.float64)
                                                   for v in (rumbo, cabeceo, alabeo)))
    a = q_eje([0, 1, 0], np.pi / 2 - rumbo)
    b = q_eje([0, 0, 1], cabeceo)
    c = q_eje([1, 0, 0], alabeo)
    return qmul(qmul(a, b), c)


def matriz(q):
    w, x, y, z = q[..., 0], q[..., 1], q[..., 2], q[..., 3]
    return np.stack([
        np.stack([1 - 2 * (y * y + z * z), 2 * (x * y - w * z), 2 * (x * z + w * y)], -1),
        np.stack([2 * (x * y + w * z), 1 - 2 * (x * x + z * z), 2 * (y * z - w * x)], -1),
        np.stack([2 * (x * z - w * y), 2 * (y * z + w * x), 1 - 2 * (x * x + y * y)], -1)], -2)


def atmosfera(h):
    h = np.clip(h, -500, 20000)
    t = np.where(h < 11000, 288.15 - 0.0065 * h, 216.65)
    p = np.where(h < 11000, np.maximum(1 - 2.25577e-5 * h, 0.2) ** 5.25588, 0.22336 * np.exp(-(h - 11000) / 6341.6))
    rho = 1.225 * p * 288.15 / t
    return rho, np.sqrt(401.874 * t)


class Flota:
    def __init__(self, n):
        self.n = n
        self.pos = np.zeros((n, 3))
        self.vel = np.zeros((n, 3))
        self.q = np.tile([1.0, 0, 0, 0], (n, 1))
        self.w = np.zeros((n, 3))
        self.R = matriz(self.q)
        self.combustible = np.full(n, C.COMBUSTIBLE_MAX)
        self.motor = np.zeros(n)
        self.pq = np.zeros(n)
        self.tren = np.ones(n)
        self.flaps = np.zeros(n)
        self.aerofreno = np.zeros(n)
        self.viento = np.zeros((n, 3))
        self.rafaga = np.zeros((n, 3))
        self.vivo = np.ones(n, bool)
        self.motivo = np.zeros(n, int)
        self.en_suelo = np.zeros(n, bool)
        self.ruedas_suelo = np.zeros((n, 3), bool)
        self.carga = np.ones(n)
        self.g_max = np.ones(n)
        self.fatiga = np.zeros(n)
        self.sobre_g = np.zeros(n, bool)
        self.alfa = np.zeros(n)
        self.beta = np.zeros(n)
        self.v_aire = np.zeros(n)
        self.mach = np.zeros(n)
        self.qbar = np.zeros(n)
        self.empuje = np.zeros(n)
        self.toque_vy = np.zeros(n)
        self.tocando = np.zeros(n, bool)
        self.dano_tren = np.zeros(n, bool)
        self.entrada = {k: np.zeros(n) for k in ("elev", "alabeo", "timon", "gases", "freno")}
        self.cmd_tren = np.ones(n)
        self.cmd_flaps = np.zeros(n)
        self.cmd_aerofreno = np.zeros(n)
        self.n2 = np.full((n, 2), N2_IDLE)
        self.encendido = np.ones((n, 2), bool)
        self.arrancando = np.zeros((n, 2), bool)
        self.valvula = np.ones((n, 2), bool)
        self.jfs = np.zeros(n)
        self.jfs_on = np.zeros(n, bool)
        self.bombas = np.ones(n, bool)
        self.generadores = np.ones(n, bool)
        self.avionica = np.ones(n, bool)
        self.sas = np.ones(n, bool)
        self.canopy = np.ones(n)
        self.cmd_canopy = np.ones(n)
        self.t = 0.0

    def colocar(self, idx, pos, rumbo, cabeceo=0.0, alabeo=0.0, vel=0.0, tren=1.0, gases=0.0, combustible=None,
                frio=False):
        idx = np.atleast_1d(np.asarray(idx))
        forma = idx.shape
        q = q_euler(np.broadcast_to(rumbo, forma), np.broadcast_to(cabeceo, forma), np.broadcast_to(alabeo, forma))
        self.q[idx] = q
        self.R[idx] = matriz(q)
        self.pos[idx] = pos
        self.vel[idx] = self.R[idx][..., 0] * np.broadcast_to(np.asarray(vel, dtype=np.float64), forma)[:, None]
        self.w[idx] = 0
        self.tren[idx] = tren
        self.cmd_tren[idx] = tren
        self.flaps[idx] = tren
        self.cmd_flaps[idx] = tren
        self.aerofreno[idx] = 0
        self.cmd_aerofreno[idx] = 0
        self.motor[idx] = np.clip(np.asarray(gases, dtype=np.float64) / 0.8, 0, 1)
        self.entrada["gases"][idx] = gases
        self.pq[idx] = 0
        self.combustible[idx] = C.COMBUSTIBLE_MAX if combustible is None else combustible
        self.vivo[idx] = True
        self.motivo[idx] = 0
        self.g_max[idx] = 1
        self.fatiga[idx] = 0
        self.sobre_g[idx] = False
        self.dano_tren[idx] = False
        self.tocando[idx] = self.pos[idx, 1] - superficie(self.pos[idx, 0], self.pos[idx, 2]) < 3
        listo = not frio
        self.n2[idx] = (N2_IDLE + (1 - N2_IDLE) * self.motor[idx])[:, None] if listo else 0.0
        self.encendido[idx] = listo
        self.valvula[idx] = listo
        self.arrancando[idx] = False
        self.jfs[idx] = 0.0
        self.jfs_on[idx] = False
        for nombre in ("bombas", "generadores", "avionica", "sas"):
            getattr(self, nombre)[idx] = listo
        self.canopy[idx] = 1.0 if listo else 0.0
        self.cmd_canopy[idx] = self.canopy[idx]
        if frio:
            self.flaps[idx] = 0.0
            self.cmd_flaps[idx] = 0.0

    def sistemas(self, dt):
        self.canopy += np.clip(self.cmd_canopy - self.canopy, -dt / 5.0, dt / 5.0)
        self.jfs = np.clip(self.jfs + np.where(self.jfs_on, dt / 4.5, -dt / 3.0), 0, 1)
        alimenta = self.valvula & (self.combustible > 0)[:, None] & self.bombas[:, None]
        self.encendido &= alimenta
        crank = self.arrancando & (self.jfs > 0.9)[:, None] & ~self.encendido
        self.encendido |= crank & alimenta & (self.n2 >= N2_ENCENDIDO)
        self.arrancando &= ~(self.encendido & (self.n2 > N2_IDLE - 0.02))
        obj = np.where(self.encendido, N2_IDLE + (1 - N2_IDLE) * self.motor[:, None], np.where(crank, 0.24, 0.0))
        tasa = np.where(self.encendido & (self.n2 < N2_IDLE - 0.01), 0.05,
                        np.where(self.encendido, 0.6, np.where(crank, 0.035, 0.07)))
        self.n2 += np.clip(obj - self.n2, -tasa * dt, tasa * dt)

    def estrellar(self, mascara, motivo):
        nuevo = mascara & self.vivo
        if nuevo.any():
            self.vivo[nuevo] = False
            self.motivo[nuevo] = motivo
            self.vel[nuevo] = 0.0
            self.w[nuevo] = 0
        return nuevo

    @property
    def masa(self):
        return C.MASA_VACIO + self.combustible

    def euler(self):
        f, u, r = self.R[..., 0], self.R[..., 1], self.R[..., 2]
        rumbo = np.arctan2(f[:, 0], -f[:, 2]) % (2 * np.pi)
        cabeceo = np.arcsin(np.clip(f[:, 1], -1, 1))
        alabeo = np.arctan2(-r[:, 1], u[:, 1])
        return rumbo, cabeceo, alabeo

    def agl(self):
        return self.pos[:, 1] - superficie(self.pos[:, 0], self.pos[:, 2])

    def paso(self, dt=C.PASO):
        n = self.n
        vivo = self.vivo
        e = self.entrada
        R = self.R
        rho, a_son = atmosfera(self.pos[:, 1])
        vaire = self.vel - self.viento - self.rafaga
        vb = np.einsum("nji,nj->ni", R, vaire)
        V = np.linalg.norm(vb, axis=1)
        Vs = np.maximum(V, 1.0)
        alfa = np.where(V > 2, np.arctan2(-vb[:, 1], vb[:, 0]), 0.0)
        beta = np.where(V > 2, np.arcsin(np.clip(vb[:, 2] / Vs, -1, 1)), 0.0)
        qbar = 0.5 * rho * V * V
        mach = V / a_son
        aa = np.abs(alfa)
        sg = np.sign(alfa)

        self.tren += np.clip(self.cmd_tren - self.tren, -dt / 5.0, dt / 5.0) * ~self.dano_tren
        self.flaps += np.clip(self.cmd_flaps - self.flaps, -dt / 3.0, dt / 3.0)
        self.aerofreno += np.clip(self.cmd_aerofreno - self.aerofreno, -dt / 1.5, dt / 1.5)
        self.dano_tren |= (self.tren > 0.05) & (V > C.VEL_TREN_MAX + 25) & ~self.en_suelo & vivo

        cla = 4.6 * np.interp(mach, [0, 0.9, 1.1, 2.0, 3.0], [1.0, 1.22, 1.1, 0.75, 0.6])
        clmax = 1.62 + 0.28 * self.flaps
        a_s = 0.4
        lineal = clmax * np.tanh(cla * np.minimum(aa, a_s) / clmax)
        perdida = np.maximum(lineal - 2.3 * (aa - a_s), 0.85 * np.abs(np.sin(2 * aa)))
        cl = sg * np.where(aa < a_s, lineal, perdida) + 0.22 * self.flaps * (aa < 0.5)
        cl = np.where(aa > np.pi / 2, 0.6 * np.sin(2 * alfa), cl)
        cd0 = np.interp(mach, [0, 0.8, 0.95, 1.05, 1.3, 2.5], [0.021, 0.021, 0.03, 0.048, 0.042, 0.036])
        cd = (cd0 + 0.11 * cl * cl + 0.024 * self.tren + 0.04 * self.flaps + 0.075 * self.aerofreno
              + 1.35 * np.sin(aa) ** 2 * _suave((aa - 0.22) / 0.25) + 0.6 * np.sin(beta) ** 2)
        cy = -1.1 * beta
        vh = vb / Vs[:, None]
        ld = np.stack([-vh[:, 1], vh[:, 0], np.zeros(n)], 1)
        ld /= np.maximum(np.linalg.norm(ld, axis=1, keepdims=True), 1e-6)
        lado = np.zeros((n, 3))
        lado[:, 2] = 1.0
        fa = qbar[:, None] * C.AREA_ALA * (cl[:, None] * ld - cd[:, None] * vh + cy[:, None] * lado)

        self.sistemas(dt)
        con_comb = self.combustible > 0
        corre = self.encendido & (self.n2 > N2_IDLE - 0.03)
        frac_i, frac_d = corre[:, 0] * 0.5, corre[:, 1] * 0.5
        frac = frac_i + frac_d
        gases = np.clip(e["gases"], 0, 1)
        mil_cmd = np.where(con_comb, np.clip(gases / 0.8, 0, 1), 0.0)
        pq_cmd = np.where(con_comb & (self.motor > 0.95), np.clip((gases - 0.8) / 0.2, 0, 1), 0.0)
        self.motor += (mil_cmd - self.motor) * min(1.0, dt / 1.6)
        self.pq += (pq_cmd - self.pq) * min(1.0, dt / 0.7)
        nivel = np.where(con_comb, 0.06 + 0.94 * self.motor, 0.0)
        empuje = (C.EMPUJE_MIL * nivel + (C.EMPUJE_PQ - C.EMPUJE_MIL) * self.pq) * (rho / 1.225) ** 0.75 \
            * (1 + 0.28 * np.clip(mach, 0, 1.8))
        guinada = empuje * (frac_d - frac_i) * BRAZO_MOTOR
        empuje = empuje * frac
        self.combustible = np.maximum(
            self.combustible - ((0.25 + 1.55 * self.motor + 10.5 * self.pq) * frac + 0.04 * self.jfs_on)
            * dt * con_comb * vivo, 0)
        fb = fa.copy()
        fb[:, 0] += empuje
        masa = self.masa

        P = RUEDAS
        pw = self.pos[:, None, :] + np.einsum("nij,kj->nki", R, P)
        hs = superficie(pw[..., 0], pw[..., 2])
        pen = hs - pw[..., 1]
        wxp = np.cross(self.w[:, None, :], P[None])
        vp = self.vel[:, None, :] + np.einsum("nij,nkj->nki", R, wxp)
        contacto = (pen > 0) & (self.tren[:, None] > 0.97) & vivo[:, None]
        fn = np.clip(K_RUEDA * pen - D_RUEDA * vp[..., 1], 0, None) * contacto
        f = R[..., 0]
        fhn = np.maximum(np.hypot(f[:, 0], f[:, 2]), 1e-6)
        fx, fz = f[:, 0] / fhn, f[:, 2] / fhn
        rx, rz = -fz, fx
        dirige = np.clip(e["timon"], -1, 1) * 0.55 * np.clip(1.15 - Vs / 45.0, 0.08, 1.0)
        cd_, sd_ = np.cos(dirige), np.sin(dirige)
        dx = np.stack([fx * cd_ + rx * sd_, fx, fx], 1)
        dz = np.stack([fz * cd_ + rz * sd_, fz, fz], 1)
        sx, sz = -dz, dx
        vl = vp[..., 0] * dx + vp[..., 2] * dz
        vt = vp[..., 0] * sx + vp[..., 2] * sz
        fr_ = np.clip(e["freno"], 0, 1)
        mu_b = np.stack([np.zeros(n), 0.62 * fr_, 0.62 * fr_], 1)
        flong = -fn * (0.018 + mu_b) * np.tanh(vl / 0.4)
        flat = -fn * 0.75 * np.tanh(np.arctan2(vt, np.abs(vl) + 2.0) / 0.12)
        fr = np.stack([flong * dx + flat * sx, fn, flong * dz + flat * sz], -1)
        f_tren = fr.sum(1)
        frb = np.einsum("nji,nkj->nki", R, fr)
        torque = np.cross(P[None], frb).sum(1)
        tocando = contacto.any(1)
        nuevo_toque = tocando & ~self.tocando
        vy_toque = np.min(np.where(contacto, vp[..., 1], 0.0), 1)
        self.toque_vy = np.where(nuevo_toque, vy_toque, self.toque_vy)
        self.toco_ahora = nuevo_toque
        self.tocando = tocando
        self.ruedas_suelo = contacto
        self.en_suelo = tocando
        rompe = (contacto & (vp[..., 1] < -5.2)).any(1)

        auth = np.clip(qbar / QREF, 0, 1)
        auth_r = np.minimum(1.0, auth * 1.6)
        perd = 1 - 0.7 * _suave((aa - 0.42) / 0.25)
        wx, wy, wz = self.w[:, 0], self.w[:, 1], self.w[:, 2]
        cmd_p = np.clip(e["alabeo"], -1, 1) * 4.0 * (1 - 0.45 * self.tren) * perd
        dp = 4.5 * (cmd_p - wx) * auth_r - 0.4 * wx * (1 - auth_r)
        nz = fa[:, 1] / (masa * G)
        el = np.clip(e["elev"], -1, 1)
        cmd_q = np.where(el > 0, el * np.minimum(0.48, (C.G_MAX - 0.6) * G / Vs),
                         el * np.minimum(0.4, 4.0 * G / Vs))
        cmd_q = cmd_q - 2.5 * np.maximum(alfa - 0.55, 0) - 0.35 * np.maximum(nz - C.G_MAX, 0) \
            + 2.5 * np.maximum(-0.3 - alfa, 0) + 0.35 * np.maximum(-3.2 - nz, 0)
        dq = 4.2 * (cmd_q - wz) * auth_r - 1.2 * np.sin(alfa) * (1 - auth_r) * ~tocando \
            - 1.4 * np.maximum(aa - 0.6, 0) * sg * auth
        cmd_r = -np.clip(e["timon"], -1, 1) * 0.45 * auth_r
        dr = 3.2 * (cmd_r - wy) * auth_r - 3.0 * beta * auth - 0.3 * wy * (1 - auth_r)
        sas = np.where(self.sas, 1.0, 0.55)
        wdot = np.stack([dp * sas, dr * sas + guinada / INERCIA[1], dq * sas], 1) + torque / INERCIA

        acc = (np.einsum("nij,nj->ni", R, fb) + f_tren) / masa[:, None]
        acc[:, 1] -= G
        v = vivo[:, None]
        self.vel = np.where(v, self.vel + acc * dt, self.vel)
        self.pos = np.where(v, self.pos + self.vel * dt, self.pos)
        self.w = np.where(v, self.w + wdot * dt, self.w)
        wq = np.concatenate([np.zeros((n, 1)), self.w], 1)
        q = self.q + 0.5 * qmul(self.q, wq) * dt
        q /= np.linalg.norm(q, axis=1, keepdims=True)
        self.q = np.where(v, q, self.q)
        self.R = matriz(self.q)

        gv = np.array([0, G, 0])
        especifica = np.einsum("nji,nj->ni", R, acc + gv)
        self.carga = np.where(vivo, especifica[:, 1] / G, 1.0)
        self.g_max = np.maximum(self.g_max, np.abs(self.carga))
        limite = np.where(np.abs(self.w[:, 0]) > C.TASA_ALABEO_CARGA, C.G_LIMITE_ALABEO, C.G_MAX)
        exceso = np.maximum(self.carga - limite, 0) / limite + np.maximum(C.G_LIMITE_NEG - self.carga, 0) / -C.G_LIMITE_NEG
        self.sobre_g = vivo & (exceso > 0)
        self.fatiga += vivo * exceso * dt
        self.alfa, self.beta, self.v_aire, self.mach, self.qbar, self.empuje = alfa, beta, V, mach, qbar, empuje

        cp = self.pos[:, None, :] + np.einsum("nij,kj->nki", self.R, CASCO)
        golpe = (cp[..., 1] < superficie(cp[..., 0], cp[..., 2])).any(1)
        agua = tocando & (altura(self.pos[:, 0], self.pos[:, 2]) < 0.5)
        self.estrellar(rompe, 2)
        self.estrellar(golpe, 1)
        self.estrellar(agua, 4)
        self.estrellar((np.abs(self.carga) > C.G_ROTURA) | (self.fatiga > C.FATIGA_ROTURA), 3)
        self.t += dt
