import numpy as np
from numba import njit

WRAM = 0x00000
VRAM = 0x08000
OAM = 0x0C000
IO = 0x0C100
BGPAL = 0x0C200
OBPAL = 0x0C240
LINEA = 0x0C280
SERIE = 0x0C800
ERAM = 0x10000
TAM_R = 0x30000

RA, RF, SP, PC = 7, 6, 8, 9
IME, HALT, EIP, BUGHALT = 10, 11, 12, 13
MBC, BANCO, BANCORAM, RAMON, MODO, NBANCOS, TAMRAM, ALTO, BAJO = 14, 15, 16, 17, 18, 19, 20, 21, 22
CGB, DOBLE, ARMADO, VBANCO, WBANCO = 23, 24, 25, 26, 27
DIVC, PUNTO, MODOPPU, LINEAV, CUADRO, CICLOS, APAGADO = 28, 29, 30, 31, 32, 33, 34
BOTONES, HDMA, HORIG, HDEST, HLARGO, LINEASTAT, NSERIE = 35, 36, 37, 38, 39, 40, 41
SUCIA, CUADROS, RTC, RTCLATCH, RTCBASE = 42, 43, 44, 49, 50
CANAL = 64
C_ON, C_LARGO, C_TIMER, C_POS, C_VOL, C_ENV, C_LFSR = 0, 1, 2, 3, 4, 5, 6
BARR_T, BARR_ON, BARR_SOMBRA = 104, 105, 106
SEC_T, SEC_PASO, MUESTRA_ACC, N_AUDIO, SONIDO = 107, 108, 109, 110, 111
TAM_ST = 128
TAM_AUDIO = 8192
TASA_AUDIO = 44100
CICLO_DUTY = np.array([0, 0, 0, 0, 0, 0, 0, 1, 1, 0, 0, 0, 0, 0, 0, 1,
                       1, 0, 0, 0, 0, 1, 1, 1, 0, 1, 1, 1, 1, 1, 1, 0], dtype=np.int64)

DMG_COLORES = np.array([[232, 248, 208], [140, 196, 116], [52, 104, 86], [8, 24, 32]], dtype=np.uint8)


@njit(cache=True)
def leer_eram(st, R, a):
    if st[RAMON] == 0:
        return 0xFF
    m = st[MBC]
    if m == 2:
        return int(R[ERAM + (a & 0x1FF)]) | 0xF0
    if m == 3 and st[BANCORAM] >= 8:
        i = st[BANCORAM] - 8
        if i < 5:
            return st[RTC + i]
        return 0xFF
    if st[TAMRAM] == 0:
        return 0xFF
    return int(R[ERAM + (st[BANCORAM] * 0x2000 + a - 0xA000) % st[TAMRAM]])


@njit(cache=True)
def leer_io(st, R, a):
    r = a & 0xFF
    if r == 0x00:
        v = int(R[IO])
        b = 0x0F
        if (v & 0x10) == 0:
            b &= ~(st[BOTONES] & 0x0F)
        if (v & 0x20) == 0:
            b &= ~((st[BOTONES] >> 4) & 0x0F)
        return 0xC0 | (v & 0x30) | (b & 0x0F)
    if r == 0x04:
        return (st[DIVC] >> 8) & 0xFF
    if r == 0x0F:
        return 0xE0 | int(R[IO + 0x0F])
    if r == 0x41:
        v = int(R[IO + 0x41]) & 0x78
        if R[IO + 0x44] == R[IO + 0x45]:
            v |= 4
        if R[IO + 0x40] & 0x80:
            v |= st[MODOPPU]
        return 0x80 | v
    if r == 0x26:
        v = 0x70 | (int(R[IO + 0x26]) & 0x80)
        for i in range(4):
            if st[CANAL + i * 10 + C_ON]:
                v |= 1 << i
        return v
    if st[CGB]:
        if r == 0x4D:
            return 0x7E | (st[DOBLE] << 7) | st[ARMADO]
        if r == 0x4F:
            return 0xFE | st[VBANCO]
        if r == 0x55:
            if st[HDMA]:
                return (st[HLARGO] - 1) & 0x7F
            return 0xFF
        if r == 0x69:
            return int(R[BGPAL + (R[IO + 0x68] & 0x3F)])
        if r == 0x6B:
            return int(R[OBPAL + (R[IO + 0x6A] & 0x3F)])
        if r == 0x70:
            return 0xF8 | st[WBANCO]
    return int(R[IO + r])


@njit(cache=True)
def rd(st, rom, R, a):
    if a < 0x4000:
        if st[MBC] == 1 and st[MODO] == 1:
            return int(rom[((st[ALTO] << 5) % st[NBANCOS]) * 0x4000 + a])
        return int(rom[a])
    if a < 0x8000:
        return int(rom[st[BANCO] * 0x4000 + a - 0x4000])
    if a < 0xA000:
        return int(R[VRAM + st[VBANCO] * 0x2000 + a - 0x8000])
    if a < 0xC000:
        return leer_eram(st, R, a)
    if a >= 0xE000 and a < 0xFE00:
        a -= 0x2000
    if a < 0xD000:
        return int(R[WRAM + a - 0xC000])
    if a < 0xE000:
        return int(R[WRAM + st[WBANCO] * 0x1000 + a - 0xD000])
    if a < 0xFEA0:
        return int(R[OAM + a - 0xFE00])
    if a < 0xFF00:
        return 0xFF
    return leer_io(st, R, a)


@njit(cache=True)
def ajustar_bancos(st):
    m = st[MBC]
    if m == 1:
        b = st[BAJO] | (st[ALTO] << 5)
        st[BANCO] = b % st[NBANCOS]
        st[BANCORAM] = st[ALTO] if st[MODO] == 1 else 0
    else:
        st[BANCO] = st[BAJO] % st[NBANCOS]


@njit(cache=True)
def segundos_rtc(st):
    return st[RTCBASE] + st[CUADROS] * 70224 // 4194304


@njit(cache=True)
def escribir_rtc(st, i, v):
    s = segundos_rtc(st)
    seg = s % 60
    mi = (s // 60) % 60
    h = (s // 3600) % 24
    d = (s // 86400) % 512
    if i == 0:
        seg = v % 60
    elif i == 1:
        mi = v % 60
    elif i == 2:
        h = v % 24
    elif i == 3:
        d = (d & 0x100) | v
    elif i == 4:
        d = (d & 0xFF) | ((v & 1) << 8)
    if i < 5:
        st[RTCBASE] += seg + 60 * mi + 3600 * h + 86400 * d - s
        st[RTC + i] = v


@njit(cache=True)
def escribir_mbc(st, a, v):
    m = st[MBC]
    if m == 1:
        if a < 0x2000:
            st[RAMON] = 1 if (v & 0x0F) == 0x0A else 0
        elif a < 0x4000:
            b = v & 0x1F
            st[BAJO] = 1 if b == 0 else b
        elif a < 0x6000:
            st[ALTO] = v & 3
        else:
            st[MODO] = v & 1
        ajustar_bancos(st)
    elif m == 2:
        if a < 0x4000:
            if a & 0x100:
                b = v & 0x0F
                st[BAJO] = 1 if b == 0 else b
                ajustar_bancos(st)
            else:
                st[RAMON] = 1 if (v & 0x0F) == 0x0A else 0
    elif m == 3:
        if a < 0x2000:
            st[RAMON] = 1 if (v & 0x0F) == 0x0A else 0
        elif a < 0x4000:
            b = v & 0x7F
            st[BAJO] = 1 if b == 0 else b
            ajustar_bancos(st)
        elif a < 0x6000:
            st[BANCORAM] = v if v >= 8 else (v & 3)
        else:
            if st[RTCLATCH] == 0 and v == 1:
                s = segundos_rtc(st)
                st[RTC] = s % 60
                st[RTC + 1] = (s // 60) % 60
                st[RTC + 2] = (s // 3600) % 24
                d = s // 86400
                st[RTC + 3] = d & 0xFF
                st[RTC + 4] = ((d >> 8) & 1) | (0x80 if d > 511 else 0)
            st[RTCLATCH] = v
    elif m == 5:
        if a < 0x2000:
            st[RAMON] = 1 if (v & 0x0F) == 0x0A else 0
        elif a < 0x3000:
            st[BAJO] = (st[BAJO] & 0x100) | v
            ajustar_bancos(st)
        elif a < 0x4000:
            st[BAJO] = (st[BAJO] & 0xFF) | ((v & 1) << 8)
            ajustar_bancos(st)
        elif a < 0x6000:
            st[BANCORAM] = v & 0x0F


@njit(cache=True)
def escribir_io(st, rom, R, a, v):
    r = a & 0xFF
    if r == 0x00:
        R[IO] = (v & 0x30) | (R[IO] & 0xCF)
    elif r == 0x02:
        if (v & 0x81) == 0x81:
            n = st[NSERIE]
            if n < 0x400:
                R[SERIE + n] = R[IO + 0x01]
                st[NSERIE] = n + 1
            R[IO + 0x01] = 0xFF
            R[IO + 0x02] = v & 0x7F
            R[IO + 0x0F] |= 8
        else:
            R[IO + 0x02] = v
    elif r == 0x04:
        st[DIVC] = 0
    elif r == 0x0F:
        R[IO + 0x0F] = v & 0x1F
    elif r == 0x40:
        antes = R[IO + 0x40] & 0x80
        R[IO + 0x40] = v
        if antes and (v & 0x80) == 0:
            R[IO + 0x44] = 0
            st[PUNTO] = 0
            st[MODOPPU] = 0
        elif antes == 0 and (v & 0x80):
            R[IO + 0x44] = 0
            st[PUNTO] = 0
            st[MODOPPU] = 2
            st[LINEAV] = 0
    elif r == 0x41:
        R[IO + 0x41] = (R[IO + 0x41] & 0x87) | (v & 0x78)
    elif r == 0x44:
        pass
    elif r == 0x46:
        base = v << 8
        for i in range(0xA0):
            R[OAM + i] = rd(st, rom, R, base + i)
        R[IO + 0x46] = v
    elif r == 0x4D:
        if st[CGB]:
            st[ARMADO] = v & 1
    elif r == 0x4F:
        if st[CGB]:
            st[VBANCO] = v & 1
    elif r == 0x55:
        if st[CGB]:
            if st[HDMA] and (v & 0x80) == 0:
                st[HDMA] = 0
            else:
                st[HORIG] = ((int(R[IO + 0x51]) << 8) | R[IO + 0x52]) & 0xFFF0
                st[HDEST] = (((int(R[IO + 0x53]) << 8) | R[IO + 0x54]) & 0x1FF0) | 0x8000
                largo = (v & 0x7F) + 1
                if v & 0x80:
                    st[HDMA] = 1
                    st[HLARGO] = largo
                else:
                    for i in range(largo * 16):
                        d = (st[HDEST] + i) & 0x1FFF
                        R[VRAM + st[VBANCO] * 0x2000 + d] = rd(st, rom, R, (st[HORIG] + i) & 0xFFFF)
                    st[CICLOS] += largo * 32
    elif r == 0x68:
        R[IO + 0x68] = v
    elif r == 0x69:
        c = R[IO + 0x68]
        R[BGPAL + (c & 0x3F)] = v
        if c & 0x80:
            R[IO + 0x68] = (c & 0x80) | ((c + 1) & 0x3F)
    elif r == 0x6A:
        R[IO + 0x6A] = v
    elif r == 0x6B:
        c = R[IO + 0x6A]
        R[OBPAL + (c & 0x3F)] = v
        if c & 0x80:
            R[IO + 0x6A] = (c & 0x80) | ((c + 1) & 0x3F)
    elif r == 0x70:
        if st[CGB]:
            b = v & 7
            st[WBANCO] = 1 if b == 0 else b
    elif 0x10 <= r <= 0x26:
        escribir_apu(st, R, r, v)
    else:
        R[IO + r] = v


@njit(cache=True)
def wr(st, rom, R, a, v):
    v &= 0xFF
    if a < 0x8000:
        escribir_mbc(st, a, v)
        return
    if a < 0xA000:
        R[VRAM + st[VBANCO] * 0x2000 + a - 0x8000] = v
        return
    if a < 0xC000:
        if st[RAMON] == 0:
            return
        m = st[MBC]
        if m == 2:
            R[ERAM + (a & 0x1FF)] = v & 0x0F
            st[SUCIA] = 1
        elif m == 3 and st[BANCORAM] >= 8:
            escribir_rtc(st, st[BANCORAM] - 8, v)
            st[SUCIA] = 1
        elif st[TAMRAM] > 0:
            R[ERAM + (st[BANCORAM] * 0x2000 + a - 0xA000) % st[TAMRAM]] = v
            st[SUCIA] = 1
        return
    if a >= 0xE000 and a < 0xFE00:
        a -= 0x2000
    if a < 0xD000:
        R[WRAM + a - 0xC000] = v
        return
    if a < 0xE000:
        R[WRAM + st[WBANCO] * 0x1000 + a - 0xD000] = v
        return
    if a < 0xFEA0:
        R[OAM + a - 0xFE00] = v
        return
    if a < 0xFF00:
        return
    escribir_io(st, rom, R, a, v)


@njit(cache=True)
def lee_pc(st, rom, R):
    pc = st[PC]
    v = rd(st, rom, R, pc)
    st[PC] = (pc + 1) & 0xFFFF
    return v


@njit(cache=True)
def lee_pc16(st, rom, R):
    lo = lee_pc(st, rom, R)
    return lo | (lee_pc(st, rom, R) << 8)


@njit(cache=True)
def empujar(st, rom, R, v):
    sp = (st[SP] - 1) & 0xFFFF
    wr(st, rom, R, sp, v >> 8)
    sp = (sp - 1) & 0xFFFF
    wr(st, rom, R, sp, v & 0xFF)
    st[SP] = sp


@njit(cache=True)
def sacar(st, rom, R):
    sp = st[SP]
    lo = rd(st, rom, R, sp)
    hi = rd(st, rom, R, (sp + 1) & 0xFFFF)
    st[SP] = (sp + 2) & 0xFFFF
    return lo | (hi << 8)


@njit(cache=True)
def get8(st, rom, R, i):
    if i == 6:
        return rd(st, rom, R, (st[4] << 8) | st[5])
    return st[i]


@njit(cache=True)
def set8(st, rom, R, i, v):
    if i == 6:
        wr(st, rom, R, (st[4] << 8) | st[5], v)
    else:
        st[i] = v & 0xFF


@njit(cache=True)
def get16(st, p):
    if p == 3:
        return st[SP]
    return (st[2 * p] << 8) | st[2 * p + 1]


@njit(cache=True)
def set16(st, p, v):
    v &= 0xFFFF
    if p == 3:
        st[SP] = v
    else:
        st[2 * p] = v >> 8
        st[2 * p + 1] = v & 0xFF


@njit(cache=True)
def condicion(st, c):
    f = st[RF]
    if c == 0:
        return (f & 0x80) == 0
    if c == 1:
        return (f & 0x80) != 0
    if c == 2:
        return (f & 0x10) == 0
    return (f & 0x10) != 0


@njit(cache=True)
def alu(st, op, v):
    a = st[RA]
    if op == 0:
        r = a + v
        f = (0x20 if (a & 0xF) + (v & 0xF) > 0xF else 0) | (0x10 if r > 0xFF else 0)
    elif op == 1:
        c = (st[RF] >> 4) & 1
        r = a + v + c
        f = (0x20 if (a & 0xF) + (v & 0xF) + c > 0xF else 0) | (0x10 if r > 0xFF else 0)
    elif op == 2 or op == 7:
        r = a - v
        f = 0x40 | (0x20 if (a & 0xF) < (v & 0xF) else 0) | (0x10 if r < 0 else 0)
    elif op == 3:
        c = (st[RF] >> 4) & 1
        r = a - v - c
        f = 0x40 | (0x20 if (a & 0xF) < (v & 0xF) + c else 0) | (0x10 if r < 0 else 0)
    elif op == 4:
        r = a & v
        f = 0x20
    elif op == 5:
        r = a ^ v
        f = 0
    else:
        r = a | v
        f = 0
    r &= 0xFF
    if r == 0:
        f |= 0x80
    st[RF] = f
    if op != 7:
        st[RA] = r


@njit(cache=True)
def prefijo_cb(st, rom, R):
    op = lee_pc(st, rom, R)
    x = op >> 6
    y = (op >> 3) & 7
    z = op & 7
    v = get8(st, rom, R, z)
    if x == 0:
        ci = (st[RF] >> 4) & 1
        if y == 0:
            c = v >> 7
            r = ((v << 1) | c) & 0xFF
        elif y == 1:
            c = v & 1
            r = (v >> 1) | (c << 7)
        elif y == 2:
            c = v >> 7
            r = ((v << 1) | ci) & 0xFF
        elif y == 3:
            c = v & 1
            r = (v >> 1) | (ci << 7)
        elif y == 4:
            c = v >> 7
            r = (v << 1) & 0xFF
        elif y == 5:
            c = v & 1
            r = (v >> 1) | (v & 0x80)
        elif y == 6:
            c = 0
            r = ((v & 0xF) << 4) | (v >> 4)
        else:
            c = v & 1
            r = v >> 1
        st[RF] = (0x80 if r == 0 else 0) | (c << 4)
        set8(st, rom, R, z, r)
        return 16 if z == 6 else 8
    if x == 1:
        st[RF] = (st[RF] & 0x10) | 0x20 | (0 if (v >> y) & 1 else 0x80)
        return 12 if z == 6 else 8
    if x == 2:
        set8(st, rom, R, z, v & ~(1 << y))
    else:
        set8(st, rom, R, z, v | (1 << y))
    return 16 if z == 6 else 8


@njit(cache=True)
def con_signo(n):
    return n - 256 if n > 127 else n


@njit(cache=True)
def paso(st, rom, R):
    pc = st[PC]
    op = rd(st, rom, R, pc)
    if st[BUGHALT]:
        st[BUGHALT] = 0
    else:
        st[PC] = (pc + 1) & 0xFFFF
    x = op >> 6
    y = (op >> 3) & 7
    z = op & 7
    if x == 1:
        if op == 0x76:
            if st[IME] == 0 and (R[IO + 0xFF] & R[IO + 0x0F] & 0x1F) != 0:
                st[BUGHALT] = 1
            else:
                st[HALT] = 1
            return 4
        set8(st, rom, R, y, get8(st, rom, R, z))
        return 8 if (y == 6 or z == 6) else 4
    if x == 2:
        alu(st, y, get8(st, rom, R, z))
        return 8 if z == 6 else 4
    p = y >> 1
    q = y & 1
    if x == 0:
        if z == 0:
            if y == 0:
                return 4
            if y == 1:
                nn = lee_pc16(st, rom, R)
                wr(st, rom, R, nn, st[SP] & 0xFF)
                wr(st, rom, R, (nn + 1) & 0xFFFF, st[SP] >> 8)
                return 20
            if y == 2:
                lee_pc(st, rom, R)
                if st[CGB] and st[ARMADO]:
                    st[DOBLE] ^= 1
                    st[ARMADO] = 0
                    st[DIVC] = 0
                return 4
            d = con_signo(lee_pc(st, rom, R))
            if y == 3 or condicion(st, y - 4):
                st[PC] = (st[PC] + d) & 0xFFFF
                return 12
            return 8
        if z == 1:
            if q == 0:
                set16(st, p, lee_pc16(st, rom, R))
                return 12
            hl = (st[4] << 8) | st[5]
            v = get16(st, p)
            r = hl + v
            st[RF] = (st[RF] & 0x80) | (0x20 if (hl & 0xFFF) + (v & 0xFFF) > 0xFFF else 0) | (0x10 if r > 0xFFFF else 0)
            set16(st, 2, r)
            return 8
        if z == 2:
            if p == 0:
                ad = (st[0] << 8) | st[1]
            elif p == 1:
                ad = (st[2] << 8) | st[3]
            else:
                ad = (st[4] << 8) | st[5]
                set16(st, 2, ad + 1 if p == 2 else ad - 1)
            if q == 0:
                wr(st, rom, R, ad, st[RA])
            else:
                st[RA] = rd(st, rom, R, ad)
            return 8
        if z == 3:
            set16(st, p, get16(st, p) + (1 if q == 0 else -1))
            return 8
        if z == 4:
            v = get8(st, rom, R, y)
            r = (v + 1) & 0xFF
            st[RF] = (st[RF] & 0x10) | (0x80 if r == 0 else 0) | (0x20 if (v & 0xF) == 0xF else 0)
            set8(st, rom, R, y, r)
            return 12 if y == 6 else 4
        if z == 5:
            v = get8(st, rom, R, y)
            r = (v - 1) & 0xFF
            st[RF] = (st[RF] & 0x10) | 0x40 | (0x80 if r == 0 else 0) | (0x20 if (v & 0xF) == 0 else 0)
            set8(st, rom, R, y, r)
            return 12 if y == 6 else 4
        if z == 6:
            set8(st, rom, R, y, lee_pc(st, rom, R))
            return 12 if y == 6 else 8
        a = st[RA]
        f = st[RF]
        if y == 0:
            c = a >> 7
            st[RA] = ((a << 1) | c) & 0xFF
            st[RF] = c << 4
        elif y == 1:
            c = a & 1
            st[RA] = (a >> 1) | (c << 7)
            st[RF] = c << 4
        elif y == 2:
            c = a >> 7
            st[RA] = ((a << 1) | ((f >> 4) & 1)) & 0xFF
            st[RF] = c << 4
        elif y == 3:
            c = a & 1
            st[RA] = (a >> 1) | (((f >> 4) & 1) << 7)
            st[RF] = c << 4
        elif y == 4:
            c = f & 0x10
            if f & 0x40:
                if c:
                    a -= 0x60
                if f & 0x20:
                    a -= 6
            else:
                if c or a > 0x99:
                    a += 0x60
                    c = 0x10
                if (f & 0x20) or (a & 0x0F) > 9:
                    a += 6
            a &= 0xFF
            st[RA] = a
            st[RF] = (f & 0x40) | c | (0x80 if a == 0 else 0)
        elif y == 5:
            st[RA] = a ^ 0xFF
            st[RF] = f | 0x60
        elif y == 6:
            st[RF] = (f & 0x80) | 0x10
        else:
            st[RF] = (f & 0x80) | ((f & 0x10) ^ 0x10)
        return 4
    if z == 0:
        if y < 4:
            if condicion(st, y):
                st[PC] = sacar(st, rom, R)
                return 20
            return 8
        if y == 4:
            wr(st, rom, R, 0xFF00 + lee_pc(st, rom, R), st[RA])
            return 12
        if y == 6:
            st[RA] = rd(st, rom, R, 0xFF00 + lee_pc(st, rom, R))
            return 12
        n = lee_pc(st, rom, R)
        sp = st[SP]
        r = (sp + con_signo(n)) & 0xFFFF
        st[RF] = (0x20 if (sp & 0xF) + (n & 0xF) > 0xF else 0) | (0x10 if (sp & 0xFF) + n > 0xFF else 0)
        if y == 5:
            st[SP] = r
            return 16
        set16(st, 2, r)
        return 12
    if z == 1:
        if q == 0:
            v = sacar(st, rom, R)
            if p == 3:
                st[RA] = v >> 8
                st[RF] = v & 0xF0
            else:
                set16(st, p, v)
            return 12
        if p == 0:
            st[PC] = sacar(st, rom, R)
            return 16
        if p == 1:
            st[PC] = sacar(st, rom, R)
            st[IME] = 1
            st[EIP] = 0
            return 16
        if p == 2:
            st[PC] = (st[4] << 8) | st[5]
            return 4
        st[SP] = (st[4] << 8) | st[5]
        return 8
    if z == 2:
        if y < 4:
            nn = lee_pc16(st, rom, R)
            if condicion(st, y):
                st[PC] = nn
                return 16
            return 12
        if y == 4:
            wr(st, rom, R, 0xFF00 + st[1], st[RA])
            return 8
        if y == 5:
            wr(st, rom, R, lee_pc16(st, rom, R), st[RA])
            return 16
        if y == 6:
            st[RA] = rd(st, rom, R, 0xFF00 + st[1])
            return 8
        st[RA] = rd(st, rom, R, lee_pc16(st, rom, R))
        return 16
    if z == 3:
        if y == 0:
            st[PC] = lee_pc16(st, rom, R)
            return 16
        if y == 1:
            return prefijo_cb(st, rom, R)
        if y == 6:
            st[IME] = 0
            st[EIP] = 0
            return 4
        if y == 7:
            st[EIP] = 1
            return 4
        return 4
    if z == 4:
        if y < 4:
            nn = lee_pc16(st, rom, R)
            if condicion(st, y):
                empujar(st, rom, R, st[PC])
                st[PC] = nn
                return 24
            return 12
        return 4
    if z == 5:
        if q == 0:
            if p == 3:
                empujar(st, rom, R, (st[RA] << 8) | st[RF])
            else:
                empujar(st, rom, R, get16(st, p))
            return 16
        if p == 0:
            nn = lee_pc16(st, rom, R)
            empujar(st, rom, R, st[PC])
            st[PC] = nn
            return 24
        return 4
    if z == 6:
        alu(st, y, lee_pc(st, rom, R))
        return 8
    empujar(st, rom, R, st[PC])
    st[PC] = y * 8
    return 16


@njit(cache=True)
def color_cgb(R, base, i, fb, ly, x):
    v = int(R[base + i]) | (int(R[base + i + 1]) << 8)
    r = v & 0x1F
    g = (v >> 5) & 0x1F
    b = (v >> 10) & 0x1F
    fb[ly, x, 0] = (r << 3) | (r >> 2)
    fb[ly, x, 1] = (g << 3) | (g >> 2)
    fb[ly, x, 2] = (b << 3) | (b >> 2)


@njit(cache=True)
def dibujar_linea(st, R, fb, ly, colores):
    lcdc = int(R[IO + 0x40])
    cgb = st[CGB]
    scy = int(R[IO + 0x42])
    scx = int(R[IO + 0x43])
    wy = int(R[IO + 0x4A])
    wx = int(R[IO + 0x4B]) - 7
    ventana = (lcdc & 0x20) != 0 and wy <= ly and wx < 160 and (cgb != 0 or (lcdc & 1) != 0)
    uso_ventana = False
    bgp = int(R[IO + 0x47])
    for x in range(160):
        if cgb == 0 and (lcdc & 1) == 0:
            R[LINEA + x] = 0
            R[LINEA + 160 + x] = 0
            R[LINEA + 320 + x] = 0
            for k in range(3):
                fb[ly, x, k] = colores[0, k]
            continue
        if ventana and x >= wx:
            px = x - wx
            py = st[LINEAV]
            mapa = 0x1C00 if lcdc & 0x40 else 0x1800
            uso_ventana = True
        else:
            px = (x + scx) & 0xFF
            py = (ly + scy) & 0xFF
            mapa = 0x1C00 if lcdc & 0x08 else 0x1800
        im = mapa + (py >> 3) * 32 + (px >> 3)
        t = int(R[VRAM + im])
        at = int(R[VRAM + 0x2000 + im]) if cgb else 0
        if lcdc & 0x10:
            d = t * 16
        else:
            d = 0x1000 + con_signo(t) * 16
        fila = py & 7
        if at & 0x40:
            fila = 7 - fila
        bit = (px & 7) if at & 0x20 else 7 - (px & 7)
        banco = 0x2000 if at & 8 else 0
        lo = int(R[VRAM + banco + d + fila * 2])
        hi = int(R[VRAM + banco + d + fila * 2 + 1])
        c = (((hi >> bit) & 1) << 1) | ((lo >> bit) & 1)
        R[LINEA + x] = c
        R[LINEA + 160 + x] = 1 if at & 0x80 else 0
        R[LINEA + 320 + x] = 0
        if cgb:
            color_cgb(R, BGPAL, (at & 7) * 8 + c * 2, fb, ly, x)
        else:
            s = (bgp >> (c * 2)) & 3
            for k in range(3):
                fb[ly, x, k] = colores[s, k]
    if uso_ventana:
        st[LINEAV] += 1
    if (lcdc & 2) == 0:
        return
    alto = 16 if lcdc & 4 else 8
    lista = np.empty(10, dtype=np.int64)
    n = 0
    for i in range(40):
        y = int(R[OAM + i * 4]) - 16
        if y <= ly < y + alto:
            lista[n] = i
            n += 1
            if n == 10:
                break
    if cgb == 0:
        for i in range(1, n):
            j = i
            while j > 0 and R[OAM + lista[j] * 4 + 1] < R[OAM + lista[j - 1] * 4 + 1]:
                tmp = lista[j]
                lista[j] = lista[j - 1]
                lista[j - 1] = tmp
                j -= 1
    for k in range(n):
        o = OAM + lista[k] * 4
        y = int(R[o]) - 16
        sx = int(R[o + 1]) - 8
        t = int(R[o + 2])
        at = int(R[o + 3])
        if alto == 16:
            t &= 0xFE
        fila = ly - y
        if at & 0x40:
            fila = alto - 1 - fila
        banco = 0x2000 if (cgb and (at & 8)) else 0
        d = VRAM + banco + t * 16 + fila * 2
        lo = int(R[d])
        hi = int(R[d + 1])
        for px in range(8):
            x = sx + px
            if x < 0 or x >= 160:
                continue
            if R[LINEA + 320 + x]:
                continue
            bit = px if at & 0x20 else 7 - px
            c = (((hi >> bit) & 1) << 1) | ((lo >> bit) & 1)
            if c == 0:
                continue
            R[LINEA + 320 + x] = 1
            fondo = R[LINEA + x]
            if cgb:
                if (lcdc & 1) and fondo != 0 and (R[LINEA + 160 + x] or (at & 0x80)):
                    continue
                color_cgb(R, OBPAL, (at & 7) * 8 + c * 2, fb, ly, x)
            else:
                if (at & 0x80) and fondo != 0:
                    continue
                pal = int(R[IO + 0x49]) if at & 0x10 else int(R[IO + 0x48])
                s = (pal >> (c * 2)) & 3
                for kk in range(3):
                    fb[ly, x, kk] = colores[s, kk]


@njit(cache=True)
def revisar_stat(st, R):
    s = R[IO + 0x41]
    ly = R[IO + 0x44]
    m = st[MODOPPU]
    linea = 0
    if (s & 0x40) != 0 and ly == R[IO + 0x45]:
        linea = 1
    elif (s & 0x08) != 0 and m == 0:
        linea = 1
    elif (s & 0x10) != 0 and m == 1:
        linea = 1
    elif (s & 0x20) != 0 and m == 2:
        linea = 1
    if linea and st[LINEASTAT] == 0:
        R[IO + 0x0F] |= 2
    st[LINEASTAT] = linea


@njit(cache=True)
def bloque_hdma(st, rom, R):
    for i in range(16):
        d = (st[HDEST] + i) & 0x1FFF
        R[VRAM + st[VBANCO] * 0x2000 + d] = rd(st, rom, R, (st[HORIG] + i) & 0xFFFF)
    st[HORIG] = (st[HORIG] + 16) & 0xFFFF
    st[HDEST] = ((st[HDEST] + 16) & 0x1FFF) | 0x8000
    st[HLARGO] -= 1
    if st[HLARGO] <= 0:
        st[HDMA] = 0


@njit(cache=True)
def ppu(st, rom, R, fb, puntos, colores):
    if (R[IO + 0x40] & 0x80) == 0:
        st[APAGADO] += puntos
        if st[APAGADO] >= 70224:
            st[APAGADO] -= 70224
            st[CUADRO] = 1
        return
    st[PUNTO] += puntos
    while True:
        ly = int(R[IO + 0x44])
        m = st[MODOPPU]
        d = st[PUNTO]
        if ly < 144:
            if m == 2 and d >= 80:
                st[MODOPPU] = 3
            elif m == 3 and d >= 252:
                st[MODOPPU] = 0
                dibujar_linea(st, R, fb, ly, colores)
                if st[HDMA] and st[HALT] == 0:
                    bloque_hdma(st, rom, R)
            elif m == 0 and d >= 456:
                st[PUNTO] = d - 456
                ly += 1
                R[IO + 0x44] = ly
                if ly == 144:
                    st[MODOPPU] = 1
                    R[IO + 0x0F] |= 1
                    st[CUADRO] = 1
                else:
                    st[MODOPPU] = 2
            else:
                break
        else:
            if d >= 456:
                st[PUNTO] = d - 456
                ly += 1
                if ly > 153:
                    ly = 0
                    st[MODOPPU] = 2
                    st[LINEAV] = 0
                R[IO + 0x44] = ly
            else:
                break
        revisar_stat(st, R)
    revisar_stat(st, R)


@njit(cache=True)
def periodo_ruido(R):
    v = int(R[IO + 0x22])
    d = v & 7
    return (8 if d == 0 else d * 16) << (v >> 4)


@njit(cache=True)
def calc_barrido(st, R):
    f = st[BARR_SOMBRA]
    d = f >> (int(R[IO + 0x10]) & 7)
    return f - d if R[IO + 0x10] & 8 else f + d


@njit(cache=True)
def disparar(st, R, i):
    b = CANAL + i * 10
    base = IO + 0x10 + 5 * i
    if st[b + C_LARGO] == 0:
        st[b + C_LARGO] = 256 if i == 2 else 64
    if i == 2:
        dac = R[IO + 0x1A] & 0x80
    else:
        dac = R[base + 2] & 0xF8
    st[b + C_ON] = 1 if dac else 0
    f = int(R[base + 3]) | ((int(R[base + 4]) & 7) << 8)
    if i < 2:
        st[b + C_TIMER] = (2048 - f) * 4
    elif i == 2:
        st[b + C_TIMER] = (2048 - f) * 2
        st[b + C_POS] = 0
    else:
        st[b + C_TIMER] = periodo_ruido(R)
        st[b + C_LFSR] = 0x7FFF
    if i != 2:
        st[b + C_VOL] = int(R[base + 2]) >> 4
        st[b + C_ENV] = int(R[base + 2]) & 7
    if i == 0:
        st[BARR_SOMBRA] = f
        p = (int(R[IO + 0x10]) >> 4) & 7
        sh = int(R[IO + 0x10]) & 7
        st[BARR_T] = p if p else 8
        st[BARR_ON] = 1 if (p != 0 or sh != 0) else 0
        if sh != 0 and calc_barrido(st, R) > 2047:
            st[b + C_ON] = 0


@njit(cache=True)
def escribir_apu(st, R, r, v):
    if r == 0x26:
        if (v & 0x80) == 0:
            for k in range(0x10, 0x26):
                R[IO + k] = 0
            for i in range(4):
                st[CANAL + i * 10 + C_ON] = 0
        R[IO + 0x26] = v & 0x80
        return
    if (R[IO + 0x26] & 0x80) == 0:
        return
    R[IO + r] = v
    if r > 0x23:
        return
    i = (r - 0x10) // 5
    k = (r - 0x10) % 5
    b = CANAL + i * 10
    if k == 1:
        st[b + C_LARGO] = 256 - v if i == 2 else 64 - (v & 63)
    elif k == 2 and i != 2:
        if (v & 0xF8) == 0:
            st[b + C_ON] = 0
    elif k == 0 and i == 2:
        if (v & 0x80) == 0:
            st[b + C_ON] = 0
    elif k == 4 and (v & 0x80) != 0:
        disparar(st, R, i)


@njit(cache=True)
def secuenciador(st, R, paso):
    if paso % 2 == 0:
        for i in range(4):
            b = CANAL + i * 10
            if (R[IO + 0x14 + 5 * i] & 0x40) != 0 and st[b + C_LARGO] > 0:
                st[b + C_LARGO] -= 1
                if st[b + C_LARGO] == 0:
                    st[b + C_ON] = 0
    if (paso == 2 or paso == 6) and st[BARR_ON] != 0:
        st[BARR_T] -= 1
        if st[BARR_T] <= 0:
            p = (int(R[IO + 0x10]) >> 4) & 7
            st[BARR_T] = p if p else 8
            if p:
                f = calc_barrido(st, R)
                if f > 2047:
                    st[CANAL + C_ON] = 0
                elif R[IO + 0x10] & 7:
                    st[BARR_SOMBRA] = f
                    R[IO + 0x13] = f & 0xFF
                    R[IO + 0x14] = (R[IO + 0x14] & 0xF8) | (f >> 8)
                    if calc_barrido(st, R) > 2047:
                        st[CANAL + C_ON] = 0
    if paso == 7:
        for i in (0, 1, 3):
            b = CANAL + i * 10
            nr2 = int(R[IO + 0x12 + 5 * i])
            p = nr2 & 7
            if p:
                st[b + C_ENV] -= 1
                if st[b + C_ENV] <= 0:
                    st[b + C_ENV] = p
                    if nr2 & 8:
                        if st[b + C_VOL] < 15:
                            st[b + C_VOL] += 1
                    elif st[b + C_VOL] > 0:
                        st[b + C_VOL] -= 1


@njit(cache=True)
def apu(st, R, aud, c):
    st[SEC_T] -= c
    while st[SEC_T] <= 0:
        st[SEC_T] += 8192
        st[SEC_PASO] = (st[SEC_PASO] + 1) & 7
        secuenciador(st, R, st[SEC_PASO])
    if st[SONIDO] == 0:
        return
    for i in range(4):
        b = CANAL + i * 10
        if st[b + C_ON] == 0:
            continue
        st[b + C_TIMER] -= c
        while st[b + C_TIMER] <= 0:
            base = IO + 0x10 + 5 * i
            if i == 3:
                st[b + C_TIMER] += periodo_ruido(R)
                l = st[b + C_LFSR]
                x = (l & 1) ^ ((l >> 1) & 1)
                l = (l >> 1) | (x << 14)
                if R[IO + 0x22] & 8:
                    l = (l & ~0x40) | (x << 6)
                st[b + C_LFSR] = l
            else:
                f = int(R[base + 3]) | ((int(R[base + 4]) & 7) << 8)
                if i == 2:
                    st[b + C_TIMER] += max(2, (2048 - f) * 2)
                    st[b + C_POS] = (st[b + C_POS] + 1) & 31
                else:
                    st[b + C_TIMER] += max(4, (2048 - f) * 4)
                    st[b + C_POS] = (st[b + C_POS] + 1) & 7
    st[MUESTRA_ACC] += c * TASA_AUDIO
    while st[MUESTRA_ACC] >= 4194304:
        st[MUESTRA_ACC] -= 4194304
        n = st[N_AUDIO]
        if n >= TAM_AUDIO:
            continue
        izq = 0
        der = 0
        if R[IO + 0x26] & 0x80:
            nr51 = int(R[IO + 0x25])
            for i in range(4):
                b = CANAL + i * 10
                if st[b + C_ON] == 0:
                    continue
                if i < 2:
                    duty = int(R[IO + 0x11 + 5 * i]) >> 6
                    o = st[b + C_VOL] if CICLO_DUTY[duty * 8 + st[b + C_POS]] else 0
                elif i == 2:
                    pw = st[b + C_POS]
                    mw = np.int64(R[IO + 0x30 + (pw >> 1)])
                    if (pw & 1) == 0:
                        mw = mw >> 4
                    else:
                        mw = mw & 0xF
                    cod = (np.int64(R[IO + 0x1C]) >> 5) & 3
                    o = 0
                    if cod != 0:
                        o = mw >> (cod - 1)
                else:
                    o = st[b + C_VOL] if (st[b + C_LFSR] & 1) == 0 else 0
                if nr51 & (16 << i):
                    izq += o
                if nr51 & (1 << i):
                    der += o
            nr50 = int(R[IO + 0x24])
            izq *= ((nr50 >> 4) & 7) + 1
            der *= (nr50 & 7) + 1
        aud[n, 0] = izq
        aud[n, 1] = der
        st[N_AUDIO] = n + 1


@njit(cache=True)
def paso_alto(x, n, est):
    for i in range(n):
        for k in range(2):
            y = x[i, k] - est[k] + 0.996 * est[2 + k]
            est[k] = x[i, k]
            est[2 + k] = y
            x[i, k] = y


@njit(cache=True)
def avanzar(st, rom, R, fb, c, colores, aud):
    viejo = st[DIVC]
    nuevo = viejo + c
    st[DIVC] = nuevo & 0xFFFF
    tac = R[IO + 0x07]
    if tac & 4:
        m = tac & 3
        b = 10 if m == 0 else (4 if m == 1 else (6 if m == 2 else 8))
        n = (nuevo >> b) - (viejo >> b)
        while n > 0:
            t = int(R[IO + 0x05]) + 1
            if t > 0xFF:
                t = R[IO + 0x06]
                R[IO + 0x0F] |= 4
            R[IO + 0x05] = t
            n -= 1
    st[CICLOS] += c
    d = c >> st[DOBLE]
    apu(st, R, aud, d)
    ppu(st, rom, R, fb, d, colores)


@njit(cache=True)
def correr_cuadros(st, rom, R, fb, n, colores, aud):
    for _ in range(n):
        st[CUADRO] = 0
        tope = 0
        while st[CUADRO] == 0 and tope < 400000:
            pend = R[IO + 0xFF] & R[IO + 0x0F] & 0x1F
            if pend:
                st[HALT] = 0
                if st[IME]:
                    st[IME] = 0
                    st[EIP] = 0
                    i = 0
                    while ((pend >> i) & 1) == 0:
                        i += 1
                    R[IO + 0x0F] &= ~(1 << i)
                    empujar(st, rom, R, st[PC])
                    st[PC] = 0x40 + 8 * i
                    avanzar(st, rom, R, fb, 20, colores, aud)
                    tope += 20
                    continue
            if st[HALT]:
                c = 4
            else:
                ei = st[EIP]
                c = paso(st, rom, R)
                if ei and st[EIP]:
                    st[IME] = 1
                    st[EIP] = 0
            avanzar(st, rom, R, fb, c, colores, aud)
            tope += c
        st[CUADROS] += 1


@njit(cache=True)
def observar(fb, obs):
    for i in range(18):
        for j in range(20):
            s = 0.0
            for y in range(i * 8, i * 8 + 8):
                for x in range(j * 8, j * 8 + 8):
                    s += 0.299 * fb[y, x, 0] + 0.587 * fb[y, x, 1] + 0.114 * fb[y, x, 2]
            obs[i, j] = s / (64.0 * 255.0)
