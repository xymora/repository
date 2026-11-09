import math

import config as C


def vector_rumbo(rumbo_grados):
    a = math.radians(rumbo_grados)
    return math.sin(a), -math.cos(a)


PUNTOS_CARDINALES = ("N", "NE", "E", "SE", "S", "SO", "O", "NO")


def cardinal(rumbo_grados):
    return PUNTOS_CARDINALES[int(((rumbo_grados % 360) + 22.5) // 45) % 8]


class Viento:

    def __init__(self, rnd, velocidad=C.VIENTO, direccion=C.VIENTO_DIRECCION,
                 rafagas=C.RAFAGAS):
        self.rnd = rnd
        self.velocidad, self.direccion, self.rafagas = velocidad, direccion, rafagas
        self.turb = [0.0, 0.0, 0.0]
        self.rafaga = None
        self.t_proxima = rnd.expovariate(1 / C.RAFAGA_CADA) + 15

    def _base(self):
        hacia_x, hacia_y = vector_rumbo(self.direccion + 180)
        return hacia_x * self.velocidad, hacia_y * self.velocidad

    def actualizar(self, dt, t):
        sigma, tau = 0.12 * self.velocidad + 0.25, 3.0
        a = math.exp(-dt / tau)
        b = sigma * math.sqrt(1 - a * a)
        self.turb = [self.turb[0] * a + b * self.rnd.gauss(0, 1),
                     self.turb[1] * a + b * self.rnd.gauss(0, 1),
                     self.turb[2] * a + 0.4 * b * self.rnd.gauss(0, 1)]
        if self.rafaga:
            self.rafaga["t"] += dt
            if self.rafaga["t"] > self.rafaga["dur"]:
                self.rafaga = None
        if self.rafagas and t >= self.t_proxima:
            self.iniciar_rafaga(self.rnd.uniform(0.35, 1.0) * C.RAFAGA_MAX)
            self.t_proxima = t + self.rnd.expovariate(1 / C.RAFAGA_CADA) + 5

    def iniciar_rafaga(self, amp):
        ang = self.direccion + 180 + self.rnd.uniform(-40, 40)
        dx, dy = vector_rumbo(ang)
        self.rafaga = dict(t=0.0, dur=self.rnd.uniform(4.0, 7.0), amp=amp, dx=dx, dy=dy)

    def intensidad_rafaga(self):
        r = self.rafaga
        if not r:
            return 0.0
        subida, bajada = 1.2, 2.0
        f = min(1.0, r["t"] / subida, (r["dur"] - r["t"]) / bajada)
        return r["amp"] * max(0.0, f)

    def en(self, x, y, z):
        f = (max(z, 3.0) / 10.0) ** 0.16
        bx, by = self._base()
        wx, wy = bx * f + self.turb[0], by * f + self.turb[1]
        g = self.intensidad_rafaga()
        if g:
            wx += self.rafaga["dx"] * g
            wy += self.rafaga["dy"] * g
        return wx, wy, self.turb[2]


class Parvada:

    def __init__(self, rnd, x, y, z, rumbo, n, dirigida=0.0):
        self.rnd = rnd
        self.x, self.y, self.z = x, y, z
        self.rumbo = rumbo
        self.vel = rnd.uniform(8.0, 13.0)
        self.z_obj = z
        self.dirigida = dirigida
        self.offsets = [(rnd.uniform(-7, 7), rnd.uniform(-7, 7), rnd.uniform(-2.5, 2.5))
                        for _ in range(n)]
        self.fase = rnd.uniform(0, 6.28)
        self.activas = [True] * n
        dx, dy = vector_rumbo(rumbo)
        self.vx, self.vy = dx * self.vel, dy * self.vel

    def actualizar(self, dt, ancho, alto):
        if self.dirigida > 0:
            self.dirigida -= dt
        else:
            self.rumbo += self.rnd.gauss(0, 18) * dt
            if self.rnd.random() < dt / 20:
                self.z_obj = self.rnd.uniform(18, 95)
        self.z += max(-1.5 * dt, min(1.5 * dt, self.z_obj - self.z))
        dx, dy = vector_rumbo(self.rumbo)
        self.vx, self.vy = dx * self.vel, dy * self.vel
        self.x += self.vx * dt
        self.y += self.vy * dt
        if not (50 < self.x < ancho - 50 and 50 < self.y < alto - 50):
            self.rumbo = math.degrees(math.atan2(ancho / 2 - self.x, -(alto / 2 - self.y)))
            self.dirigida = 0.0
        self.fase += dt

    def aves(self):
        c, s = math.cos(math.radians(self.rumbo)), math.sin(math.radians(self.rumbo))
        for k, (ox, oy, oz) in enumerate(self.offsets):
            if self.activas[k]:
                ond = 1.2 * math.sin(self.fase * 1.7 + k)
                yield k, (self.x + ox * c - oy * s, self.y + ox * s + oy * c,
                          self.z + oz + ond)


class Aves:
    def __init__(self, rnd, ciudad, activas=True):
        self.rnd = rnd
        self.activas = activas
        self.parvadas = []
        if not activas:
            return
        for _ in range(C.NUM_PARVADAS - C.PARVADAS_EN_RUTA):
            x, y = rnd.uniform(100, ciudad.ancho - 100), rnd.uniform(100, ciudad.alto - 100)
            self.parvadas.append(Parvada(rnd, x, y, rnd.uniform(20, 90), rnd.uniform(0, 360),
                                         rnd.randint(3, 7)))

    def cruce(self, x, y, z, rumbo_ruta, segundos):
        rnd = self.rnd
        lado = rnd.choice((-90, 90)) + rnd.uniform(-25, 25)
        rumbo = rumbo_ruta + lado
        p = Parvada(rnd, x, y, z, rumbo + 180, rnd.randint(3, 7), dirigida=segundos + 6)
        dx, dy = vector_rumbo(rumbo)
        p.x, p.y = x + dx * p.vel * segundos, y + dy * p.vel * segundos
        self.parvadas.append(p)
        if len(self.parvadas) > C.NUM_PARVADAS + 4:
            self.parvadas.pop(0)

    def actualizar(self, dt, ciudad):
        for p in self.parvadas:
            p.actualizar(dt, ciudad.ancho, ciudad.alto)

    def todas(self):
        for p in self.parvadas:
            for k, pos in p.aves():
                yield p, k, pos

    def cercanas(self, x, y, z, r):
        for p in self.parvadas:
            if abs(p.x - x) > r + 15 or abs(p.y - y) > r + 15:
                continue
            for k, pos in p.aves():
                if math.dist(pos, (x, y, z)) < r:
                    yield p, k, pos
