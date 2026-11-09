import numpy as np

import config as C

VARS_DIR = ("punto", "densidad", "peligro", "escape", "comible", "energ", "fruta", "adelante", "reversa")
VARS_GLOB = ("susto", "quedan", "persec", "encasa")
VARIABLES = VARS_DIR + VARS_GLOB
DESCRIPCION = {
    "punto": "distancia al punto más cercano yendo por ahí",
    "densidad": "puntos cercanos en esa dirección",
    "peligro": "distancia al fantasma peligroso más cercano por ahí",
    "escape": "margen para llegar al siguiente cruce antes que un fantasma (−1..1)",
    "comible": "distancia al fantasma asustado más cercano por ahí",
    "energ": "distancia al energizante más cercano por ahí",
    "fruta": "distancia a la fruta por ahí",
    "adelante": "1 si es la dirección en la que ya va",
    "reversa": "1 si es dar media vuelta",
    "susto": "fracción del susto que queda",
    "quedan": "fracción de puntos que quedan",
    "persec": "1 si los fantasmas están en persecución",
    "encasa": "fracción de fantasmas en la casa",
}
FUNCIONES = {"+": 2, "-": 2, "*": 2, "/": 2, "min": 2, "max": 2, "si": 4}
_POR_ARIDAD = {k: [f for f, a in FUNCIONES.items() if a == k] for k in set(FUNCIONES.values())}


def _div(a, b):
    return a / b if abs(b) > 1e-6 else 1.0


def hoja(rng):
    if rng.random() < C.P_CONSTANTE:
        return ["c", round(float(rng.uniform(-2, 2)), 2)]
    return ["v", VARIABLES[rng.integers(len(VARIABLES))]]


def generar(rng, prof, completo):
    if prof <= 0 or (not completo and rng.random() < 0.3):
        return hoja(rng)
    f = list(FUNCIONES)[rng.integers(len(FUNCIONES))]
    return [f] + [generar(rng, prof - 1, completo) for _ in range(FUNCIONES[f])]


def poblacion_inicial(n, rng):
    p0, p1 = C.PROF_INICIAL
    out = []
    for k in range(n):
        while True:
            t = plegar(generar(rng, p0 + k % (p1 - p0 + 1), k % 2 == 0))
            if nodos(t) <= C.MAX_NODOS:
                break
        out.append(t)
    return out


def es_hoja(t):
    return t[0] in ("v", "c")


def nodos(t):
    return 1 if es_hoja(t) else 1 + sum(nodos(h) for h in t[1:])


def profundidad(t):
    return 0 if es_hoja(t) else 1 + max(profundidad(h) for h in t[1:])


def rutas(t, base=()):
    out = [base]
    if not es_hoja(t):
        for k, h in enumerate(t[1:], 1):
            out += rutas(h, base + (k,))
    return out


def obtener(t, ruta):
    for k in ruta:
        t = t[k]
    return t


def copiar(t):
    return list(t) if es_hoja(t) else [t[0]] + [copiar(h) for h in t[1:]]


def reemplazar(t, ruta, sub):
    if not ruta:
        return copiar(sub)
    t = copiar(t)
    padre = obtener(t, ruta[:-1])
    padre[ruta[-1]] = copiar(sub)
    return t


def _elegir_nodo(t, rng):
    rs = rutas(t)
    internos = [r for r in rs if not es_hoja(obtener(t, r))]
    if internos and rng.random() < 0.9:
        return internos[rng.integers(len(internos))]
    return rs[rng.integers(len(rs))]


def cruce(a, b, rng):
    return reemplazar(a, _elegir_nodo(a, rng), obtener(b, _elegir_nodo(b, rng)))


def mut_subarbol(a, rng):
    rs = rutas(a)
    return reemplazar(a, rs[rng.integers(len(rs))], generar(rng, int(rng.integers(1, 4)), False))


def mut_punto(a, rng):
    rs = rutas(a)
    r = rs[rng.integers(len(rs))]
    n = copiar(obtener(a, r))
    if n[0] == "c":
        n[1] = round(n[1] + float(rng.normal(0, 0.3)) * max(1.0, abs(n[1])), 2)
    elif n[0] == "v":
        n[1] = VARIABLES[rng.integers(len(VARIABLES))]
    else:
        otras = _POR_ARIDAD[FUNCIONES[n[0]]]
        n[0] = otras[rng.integers(len(otras))]
    return reemplazar(a, r, n)


def plegar(t):
    if es_hoja(t):
        return t
    hijos = [plegar(h) for h in t[1:]]
    f = t[0]
    if f == "si":
        a, b, c, d = hijos
        if a[0] == "c" and b[0] == "c":
            return c if a[1] > b[1] else d
        if a == b:
            return d
        if c == d:
            return c
        return [f] + hijos
    a, b = hijos
    if a[0] == "c" and b[0] == "c":
        return ["c", round(float(_aplicar(f, a[1], b[1])), 4)]
    if f == "-" and a == b:
        return ["c", 0.0]
    cero = lambda x: x[0] == "c" and x[1] == 0
    uno = lambda x: x[0] == "c" and x[1] == 1
    if f == "+" and cero(b) or f == "-" and cero(b) or f == "*" and uno(b) or f == "/" and uno(b):
        return a
    if f == "+" and cero(a) or f == "*" and uno(a):
        return b
    if f == "*" and (cero(a) or cero(b)):
        return ["c", 0.0]
    if f in ("min", "max") and a == b:
        return a
    return [f] + hijos


def _aplicar(f, a, b):
    if f == "+":
        return a + b
    if f == "-":
        return a - b
    if f == "*":
        return a * b
    if f == "/":
        return _div(a, b)
    if f == "min":
        return min(a, b)
    return max(a, b)


def fuente(t):
    k = t[0]
    if k == "v":
        return t[1]
    if k == "c":
        return repr(float(t[1]))
    if k == "si":
        a, b, c, d = (fuente(h) for h in t[1:])
        return f"(({c}) if ({a}) > ({b}) else ({d}))"
    a, b = fuente(t[1]), fuente(t[2])
    if k == "/":
        return f"_div({a}, {b})"
    if k in ("min", "max"):
        return f"{k}({a}, {b})"
    return f"({a} {k} {b})"


def compilar(t):
    return eval(f"lambda {', '.join(VARIABLES)}: {fuente(t)}", {"_div": _div})


def valor(t, env):
    k = t[0]
    if k == "v":
        return env[t[1]]
    if k == "c":
        return float(t[1])
    if k == "si":
        return valor(t[3], env) if valor(t[1], env) > valor(t[2], env) else valor(t[4], env)
    return _aplicar(k, valor(t[1], env), valor(t[2], env))


def entradas(obs, pac_d):
    k = len(obs)
    f = obs[:, :4 * C.SENSORES_DIR].reshape(k, 4, C.SENSORES_DIR)
    out = np.empty((k, 4, len(VARIABLES)))
    out[..., :7] = f[..., 1:8]
    dirs = np.arange(4)[None]
    out[..., 7] = dirs == pac_d[:, None]
    out[..., 8] = dirs == ((pac_d + 2) % 4)[:, None]
    g = obs[:, 4 * C.SENSORES_DIR + 4:4 * C.SENSORES_DIR + 8]
    out[..., 9:] = g[:, None, :]
    return out


class Bosque:

    def __init__(self, programas):
        self.programas = [copiar(p) for p in programas]
        self.f = [compilar(p) for p in self.programas]

    def __call__(self, partida, idx):
        F = entradas(partida.obs[idx], partida.pac_d[idx]).tolist()
        out = np.empty((len(idx), 4))
        for a, i in enumerate(idx):
            f = self.f[i]
            fila = F[a]
            try:
                out[a] = [f(*fila[0]), f(*fila[1]), f(*fila[2]), f(*fila[3])]
            except (OverflowError, ValueError):
                out[a] = 0.0
        return np.nan_to_num(out, nan=-1e9, posinf=1e9, neginf=-1e9)


def _num(x):
    return f"{x:.2f}".rstrip("0").rstrip(".") if abs(x) < 1000 else f"{x:.3g}"


def texto(t, arriba=True):
    k = t[0]
    if k == "v":
        return t[1]
    if k == "c":
        return _num(t[1])
    if k == "si":
        a, b, c, d = (texto(h) for h in t[1:])
        return f"[{a} > {b} ? {c} : {d}]"
    a, b = texto(t[1], False), texto(t[2], False)
    if k in ("min", "max"):
        return f"{k}({a}, {b})"
    if k in ("+", "-") and t[2][0] == "c" and t[2][1] < 0:
        k, b = ("-" if k == "+" else "+"), _num(-t[2][1])
    s = f"{a} {'×' if k == '*' else '÷' if k == '/' else k} {b}"
    return s if arriba else f"({s})"


def lineas(t, env=None, nivel=0, activo=True):
    if t[0] == "si":
        a, b, c, d = t[1:]
        cond = None if env is None else valor(a, env) > valor(b, env)
        out = [(nivel, f"SI {texto(a)} > {texto(b)}", cond, activo, "cond"),
               (nivel, "ENTONCES", None, activo and cond is not False, "rama")]
        out += lineas(c, env, nivel + 1, activo and cond is not False)
        out.append((nivel, "SI NO", None, activo and cond is not True, "rama"))
        out += lineas(d, env, nivel + 1, activo and cond is not True)
        return out
    return [(nivel, texto(t), None if env is None else valor(t, env), activo, "expr")]


def como_texto(t):
    return "\n".join("    " * s + txt for s, txt, *_ in lineas(t))
