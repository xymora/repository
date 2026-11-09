import hashlib
from collections import deque

import numpy as np

import cerebro
import config as C
import nucleo as N
from consola import ABAJO, ARRIBA, DERECHA, IZQUIERDA, GameBoy, leer_rom, mascara

TAM_RAM_VISTA = 0x2000 + 0x7F


def _hash(b):
    return int.from_bytes(hashlib.blake2b(b, digest_size=8).digest(), "little") >> 1


def clave_celda(obs, extra=b""):
    a = obs.reshape(9, 2, 10, 2).mean((1, 3))
    q = np.minimum((a * 8).astype(np.uint8), 7)
    return _hash(q.tobytes() + extra)


def clave_lugar(mapa, x, y, etapa):
    return _hash(b"P" + mapa + b"|" + bytes((x & 255, y & 255)) + b"|" + int(etapa).to_bytes(2, "little"))


def ram_vista(gb):
    R, wb = gb.R, int(gb.st[N.WBANCO])
    return np.concatenate([R[N.WRAM:N.WRAM + 0x1000], R[N.WRAM + wb * 0x1000:N.WRAM + wb * 0x1000 + 0x1000],
                           R[N.IO + 0x80:N.IO + 0xFF]])


def direccion(i):
    return 0xC000 + i if i < 0x2000 else 0xFF80 + i - 0x2000


def indice(d):
    return d - 0xC000 if d < 0xFF00 else 0x2000 + d - 0xFF80


def bits(a):
    return int(np.unpackbits(np.asarray(a, dtype=np.uint8)).sum())


class Memoria(set):
    def __init__(self, *a):
        super().__init__(*a)
        self.bloqueados = set()
        self.sin_mover = 0
        self.ultimo = None
        self.empuje = 0
        self.dir = (0, 0)

    def mover(self, juego, ram, a, etapa):
        if juego.i_pos is None or a < 0:
            return
        m = juego._mapa(ram)
        x, y = int(ram[juego.i_pos[0]]), int(ram[juego.i_pos[1]])
        pos = (m, x, y)
        if pos != self.ultimo:
            self.ultimo = pos
            self.sin_mover = 0
            self.empuje = 0
            return
        self.sin_mover += 1
        d = juego.flechas[a]
        if d == (0, 0) or self.sin_mover > C.BRUJULA_APAGA:
            self.empuje = 0
            return
        if d == self.dir:
            self.empuje += 1
        else:
            self.dir = d
            self.empuje = 1
        if self.empuje >= C.EMPUJE_BLOQUEO:
            self.bloqueados.add(clave_lugar(m, x + d[0], y + d[1], etapa))
            self.empuje = 0


class Juego:
    def __init__(self, ruta_rom, acciones, perfil, ruta_sav=None):
        self.gb = GameBoy(leer_rom(ruta_rom), ruta_sav=ruta_sav)
        self.banderas = None
        self.configurar(acciones, perfil)

    def configurar(self, acciones, perfil, banderas=None):
        self.acciones = acciones
        self.mascaras = [mascara(a) for a in acciones]
        self.n = len(acciones)
        self.perfil = perfil
        self.i_vidas = indice(perfil["vidas"]) if perfil.get("vidas") is not None else None
        self.i_puntos = np.array([indice(d) for d in perfil.get("puntos", [])], dtype=np.int64)
        self.i_progreso = [indice(d) for d in perfil.get("progreso", [])]
        self.i_pos = [indice(d) for d in perfil["posicion"]] if perfil.get("posicion") else None
        self.i_mapa = [indice(d) for d in perfil.get("mapa", [])]
        self.i_niveles = [indice(d) for d in perfil.get("niveles", [])]
        self.i_exp = [indice(d) for d in perfil.get("experiencia", [])]
        self.i_equipo = indice(perfil["equipo"]) if perfil.get("equipo") else None
        self.metas = [(indice(m[0]), int(m[1]), float(m[2]), bool(m[3]) if len(m) > 3 else True)
                      for m in perfil.get("metas_bits", [])]
        if banderas is not None:
            self.banderas = banderas if len(banderas) else None
        self.con_avance = bool(self.i_niveles or self.metas or self.banderas is not None)
        self.direcciones = [((DERECHA in a) - (IZQUIERDA in a), (ABAJO in a) - (ARRIBA in a)) for a in acciones]
        self.es_menu = [("START" in a or "SELECT" in a) for a in acciones]
        self.flechas = [((DERECHA in a) - (IZQUIERDA in a), (ABAJO in a) - (ARRIBA in a)) if len(a) == 1 else (0, 0)
                        for a in acciones]
        self.utiles = np.array([i for i, a in enumerate(acciones) if a], dtype=np.int64)
        self.nada = [i for i, a in enumerate(acciones) if not a]

    def decidir(self, logits, rng, ultima, racha, quieto, eps):
        con_pos = self.i_pos is not None
        if racha > 0 and ultima >= 0:
            return ultima, racha - 1
        if con_pos and quieto >= C.QUIETO_AZAR and len(self.utiles):
            return int(self.utiles[int(rng.integers(len(self.utiles)))]), int(rng.integers(3, C.RACHA_AZAR))
        if rng.random() < eps:
            return int(rng.integers(self.n)), (int(rng.integers(0, C.RACHA_AZAR)) if con_pos else 0)
        z = np.array(logits(), dtype=np.float64)
        if con_pos and self.nada:
            z[self.nada] = -np.inf
        if C.TEMPERATURA > 0:
            z = (z - z.max()) / C.TEMPERATURA
            pr = np.exp(z)
            pr /= pr.sum()
            return int(rng.choice(self.n, p=pr)), 0
        return int(np.argmax(z)), 0

    def avance(self, ram):
        etapa = 0
        valor = 0.0
        for i, n, w, cuenta_etapa in self.metas:
            b = bits(ram[i:i + n])
            if cuenta_etapa:
                etapa += b
            valor += w * b
        if self.banderas is not None:
            b = bits(ram & self.banderas)
            etapa += b
            valor += C.PREMIO_BANDERA * b
        cuenta = len(self.i_niveles)
        if self.i_equipo is not None:
            cuenta = min(int(ram[self.i_equipo]), cuenta)
        niveles = sum(int(ram[i]) for i in self.i_niveles[:cuenta])
        exp = sum((int(ram[i]) << 16) | (int(ram[i + 1]) << 8) | int(ram[i + 2]) for i in self.i_exp[:cuenta])
        return etapa, valor, niveles, exp

    def puntaje(self, ram):
        if not self.con_avance:
            return 0.0
        etapa, valor, niveles, _ = self.avance(ram)
        return float(valor + niveles)

    def _mapa(self, ram):
        return bytes(int(ram[i]) for i in self.i_mapa)

    def clave_pos(self, ram, etapa=None):
        if self.i_pos is None:
            return None
        if etapa is None:
            etapa = self.avance(ram)[0] if self.con_avance else 0
        return clave_lugar(self._mapa(ram), int(ram[self.i_pos[0]]), int(ram[self.i_pos[1]]), etapa)

    def rasgos(self, ram, etapa, conocidas, vistas, sin_novedad):
        r = np.zeros(cerebro.RASGOS, np.float32)
        if self.i_pos is None:
            return r
        m = self._mapa(ram)
        x, y = int(ram[self.i_pos[0]]), int(ram[self.i_pos[1]])
        R, L = cerebro.RADIO, cerebro.LADO
        bloq = getattr(vistas, "bloqueados", ())
        ex = ey = gx = gy = 0.0
        k = 0
        for dy in range(-R, R + 1):
            for dx in range(-R, R + 1):
                c = clave_lugar(m, x + dx, y + dy, etapa)
                conocida = c in conocidas
                vista = c in vistas
                if conocida:
                    r[k] = 1.0
                if vista:
                    r[L * L + k] = 1.0
                if (dx or dy) and c not in bloq:
                    w = 1.0 / (dx * dx + dy * dy)
                    if not vista:
                        ex += w * dx
                        ey += w * dy
                    if not conocida:
                        gx += w * dx
                        gy += w * dy
                k += 1
        i = 2 * L * L
        r[i] = min(sin_novedad / C.SIN_NOVEDAD_POS, 1.0)
        r[i + 1] = 1.0
        apaga = max(0.0, 1.0 - getattr(vistas, "sin_mover", 0) / C.BRUJULA_APAGA)
        for j, (u, v) in enumerate(((ex, ey), (gx, gy))):
            n = (u * u + v * v) ** 0.5
            if n > 1e-9:
                r[i + 2 + 2 * j] = apaga * u / n
                r[i + 3 + 2 * j] = apaga * v / n
        return r

    def entrada(self, obs, previo, ultima, quieto, ram, conocidas, vistas, sin_novedad=0, etapa=None):
        if self.i_pos is None:
            return cerebro.vector(obs, previo, ultima, self.n, min(quieto / C.QUIETO_MAX, 1.0))
        if etapa is None:
            etapa = self.avance(ram)[0] if self.con_avance else 0
        return cerebro.vector(obs, previo, ultima, self.n, min(quieto / C.QUIETO_MAX, 1.0),
                              self.rasgos(ram, etapa, conocidas, vistas, sin_novedad))

    def extra(self, ram):
        if not self.i_progreso:
            return b""
        return bytes(int(ram[i]) for i in self.i_progreso)


def jugar(juego, theta, ocultas, pasos, rng, conocidas, eps=C.EPSILON, recoger=False, pesos=None, sonda=False):
    gb = juego.gb
    p = pesos or {}
    pol = cerebro.Politica(theta, juego.n, ocultas)
    obs = gb.observar().copy()
    previo = obs.copy()
    ram = ram_vista(gb)
    ram0 = ram.copy()
    ultima = -1
    vistas = Memoria()
    nuevas = []
    estados = []
    aptitud = 0.0
    celdas_nuevas = 0
    lugares_nuevos = 0
    eventos_puntos = 0
    vidas_perdidas = 0
    quieto = 0
    sin_novedad = 0
    clave_previa = None
    con_pos = juego.i_pos is not None
    tope_novedad = C.SIN_NOVEDAD_POS if con_pos else C.SIN_NOVEDAD_MAX
    if juego.con_avance:
        etapa, valor_max, niveles_max, exp_max = juego.avance(ram)
    else:
        etapa, valor_max, niveles_max, exp_max = 0, 0.0, 0, 0
    avance0 = valor_max + niveles_max
    logros = 0
    kp = juego.clave_pos(ram, etapa)
    if kp is not None:
        vistas.add(kp)
    premio_celda = p.get("celda_nueva", C.PREMIO_CELDA_NUEVA)
    premio_pantalla = premio_celda * (p.get("pantalla", C.FACTOR_PANTALLA) if con_pos else 1.0)
    final = "pasos"
    dir_h = dir_v = 0
    edad_h = edad_v = 99
    racha = 0
    encendidos = np.zeros(TAM_RAM_VISTA, np.uint8)
    apagados = np.zeros(TAM_RAM_VISTA, np.uint8)
    cambios = np.zeros(TAM_RAM_VISTA, np.int16)
    if recoger:
        inc = np.zeros(TAM_RAM_VISTA, np.int16)
        dec = np.zeros(TAM_RAM_VISTA, np.int16)
        dec1 = np.zeros(TAM_RAM_VISTA, np.int16)
        salto = np.zeros(TAM_RAM_VISTA, np.int16)
        hp = np.zeros(TAM_RAM_VISTA, np.int16)
        hn = np.zeros(TAM_RAM_VISTA, np.int16)
        h0 = np.zeros(TAM_RAM_VISTA, np.int16)
        vp = np.zeros(TAM_RAM_VISTA, np.int16)
        vn = np.zeros(TAM_RAM_VISTA, np.int16)
        v0 = np.zeros(TAM_RAM_VISTA, np.int16)
        en_salto = np.zeros(TAM_RAM_VISTA, np.int16)
        fuera_salto = np.zeros(TAM_RAM_VISTA, np.int16)
        saltos = 0
        cola = deque()
        ventana = -1
    for t in range(pasos):
        if sonda:
            a = ultima if ultima >= 0 and rng.random() < C.SONDA_PEGAJOSA else int(rng.integers(juego.n))
        else:
            a, racha = juego.decidir(
                lambda: pol.logits(juego.entrada(obs, previo, ultima, quieto, ram, conocidas, vistas, sin_novedad,
                                                 etapa)), rng, ultima, racha, quieto, eps)
        if con_pos and juego.es_menu[a] and a != ultima:
            aptitud -= p.get("menu", C.CASTIGO_MENU)
        gb.pulsar(juego.mascaras[a])
        previo = obs
        gb.cuadros(C.ACCION_CADA)
        obs = gb.observar().copy()
        ultima = a
        nueva_ram = ram_vista(gb)
        vistas.mover(juego, nueva_ram, a, etapa)
        encendidos |= nueva_ram & ~ram
        apagados |= ram & ~nueva_ram
        cambios += nueva_ram != ram
        h, v = juego.direcciones[a]
        if h:
            dir_h, edad_h = h, 0
        else:
            edad_h += 1
        if v:
            dir_v, edad_v = v, 0
        else:
            edad_v += 1
        if recoger:
            delta = nueva_ram.astype(np.int16) - ram.astype(np.int16)
            sube = delta > 0
            baja = delta < 0
            inc += sube
            dec += baja
            dec1 += delta == -1
            acarreo = delta == 1
            vecino = np.zeros_like(sube)
            vecino[1:] |= acarreo[:-1]
            vecino[:-1] |= acarreo[1:]
            salto += baja & ~vecino
            chico = np.abs(delta) == 1
            if chico.any():
                sg = np.sign(delta)
                if edad_h <= C.MEMORIA_DIRECCION:
                    hp += chico & (sg == dir_h)
                    hn += chico & (sg == -dir_h)
                else:
                    h0 += chico
                if edad_v <= C.MEMORIA_DIRECCION:
                    vp += chico & (sg == dir_v)
                    vn += chico & (sg == -dir_v)
                else:
                    v0 += chico
            if con_pos:
                cambio = delta != 0
                if np.abs(delta[juego.i_pos]).max() > 2:
                    saltos += 1
                    ventana = t + C.VENTANA_SALTO
                    while cola:
                        en_salto += cola.popleft()
                if t <= ventana:
                    en_salto += cambio
                else:
                    cola.append(cambio)
                    if len(cola) > C.VENTANA_SALTO:
                        fuera_salto += cola.popleft()
        novedad = False
        if juego.con_avance:
            etapa, valor, niveles, exp = juego.avance(nueva_ram)
            if valor > valor_max:
                aptitud += p.get("logro", 1.0) * (valor - valor_max)
                valor_max = valor
                logros += 1
                novedad = True
            if niveles > niveles_max:
                aptitud += p.get("nivel", C.PREMIO_NIVEL) * (niveles - niveles_max)
                niveles_max = niveles
                novedad = True
            if exp > exp_max:
                aptitud += p.get("experiencia", C.PREMIO_EXP)
                exp_max = exp
                novedad = True
        k = clave_celda(obs, juego.extra(nueva_ram))
        if k not in vistas:
            vistas.add(k)
            novedad = True
            if k not in conocidas:
                celdas_nuevas += 1
                aptitud += premio_pantalla
                nuevas.append(k)
                if not con_pos and len(estados) < 40:
                    estados.append((k, t, gb.estado(), valor_max + niveles_max))
            elif not con_pos:
                aptitud += p.get("celda_episodio", C.PREMIO_CELDA_EPISODIO)
        if con_pos:
            kp = juego.clave_pos(nueva_ram, etapa)
            if kp not in vistas:
                vistas.add(kp)
                novedad = True
                if kp not in conocidas:
                    lugares_nuevos += 1
                    aptitud += premio_celda
                    nuevas.append(kp)
                    if len(estados) < 40:
                        estados.append((kp, t, gb.estado(), valor_max + niveles_max))
                else:
                    aptitud += p.get("celda_episodio", C.PREMIO_CELDA_EPISODIO)
        sin_novedad = 0 if novedad else sin_novedad + 1
        if len(juego.i_puntos):
            if np.any(nueva_ram[juego.i_puntos] > ram[juego.i_puntos]):
                eventos_puntos += 1
                aptitud += p.get("puntos", C.PREMIO_PUNTOS)
        if juego.i_vidas is not None and nueva_ram[juego.i_vidas] < ram[juego.i_vidas]:
            vidas_perdidas += 1
            aptitud -= p.get("vida", C.CASTIGO_VIDA)
            ram = nueva_ram
            final = "vida"
            break
        quieto = quieto + 1 if k == clave_previa else 0
        clave_previa = k
        ram = nueva_ram
        if quieto >= C.QUIETO_MAX:
            aptitud -= p.get("quieto", C.CASTIGO_QUIETO)
            final = "quieto"
            break
        if sin_novedad >= tope_novedad:
            aptitud -= p.get("bucle", C.CASTIGO_BUCLE)
            final = "bucle"
            break
    if len(estados) > C.CELDAS_POR_EPISODIO:
        idx = sorted(set(np.linspace(0, len(estados) - 1, C.CELDAS_POR_EPISODIO).round().astype(int)))
        estados = [estados[i] for i in idx]
    res = {"aptitud": aptitud, "celdas": celdas_nuevas, "lugares": lugares_nuevos, "puntos": eventos_puntos,
           "vidas": vidas_perdidas, "pasos": t + 1, "final": final, "nuevas": nuevas, "estados": estados,
           "visitadas": len(vistas), "logros": logros, "avance": valor_max + niveles_max - avance0,
           "bits": (encendidos, apagados, cambios)}
    if recoger:
        res["stats"] = (ram0, inc, dec, dec1, salto, t + 1)
        res["mov"] = (hp, hn, h0, vp, vn, v0)
        if con_pos:
            res["saltos"] = (saltos, en_salto, fuera_salto)
    return res


_CACHE = {}


def evaluar(tarea):
    ruta = tarea["rom"]
    juego = _CACHE.get(ruta)
    if juego is None:
        juego = Juego(ruta, tarea["acciones"], tarea["perfil"])
        _CACHE.clear()
        _CACHE[ruta] = juego
    juego.configurar(tarea["acciones"], tarea["perfil"], tarea.get("banderas"))
    juego.gb.restaurar(tarea["inicio"])
    n = len(tarea["theta"])
    ruido = np.random.default_rng(tarea["semilla"]).standard_normal(n).astype(np.float32)
    theta = tarea["theta"] + tarea["signo"] * tarea["sigma"] * ruido
    rng = np.random.default_rng(tarea["semilla_juego"])
    conocidas = tarea["conocidas"]
    if not isinstance(conocidas, set):
        conocidas = set(conocidas.tolist())
        tarea["conocidas"] = conocidas
    res = jugar(juego, theta, tarea["ocultas"], tarea["pasos"], rng, conocidas,
                recoger=tarea.get("recoger", False), pesos=tarea.get("pesos"), sonda=tarea.get("sonda", False))
    res["i"] = tarea["i"]
    return res


def iniciar_trabajador():
    try:
        import ctypes
        ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), 0x4000)
    except Exception:
        pass
