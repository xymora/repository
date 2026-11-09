import glob
import json
import math
import os

import numpy as np

from terreno import AEROPUERTOS, BASE, altura

AQUI = os.path.dirname(os.path.abspath(__file__))
CARPETA = os.path.join(AQUI, "config_misiones")
NORTE = AEROPUERTOS[1]
PISTAS = {"BASE": BASE, "NORTE": NORTE}
PENDIENTE = math.tan(math.radians(3.0))

PUNTO, DESPEGUE, TOQUE, DETENER, BLANCO, ARRANQUE = range(6)
TIPO_SENSOR = np.array([PUNTO, DESPEGUE, TOQUE, DETENER, BLANCO, DESPEGUE])
COMBATE = 13


def _o(tipo, p=None, radio=300.0, vel=None, tren=None, pista=BASE, final=False, **extra):
    o = {"tipo": tipo, "p": None if p is None else np.asarray(p, dtype=np.float64), "radio": radio,
         "vel": vel, "tren": tren, "pista": pista, "final": final}
    o.update(extra)
    return o


def objetivo(tipo, **datos):
    return _o(tipo, **datos)


def _senda(pista, distancias, radios, vel=85.0):
    lista = []
    for d, r in zip(distancias, radios):
        p = pista.mundo(-d, 0, pista.elev + 15 + d * PENDIENTE)
        lista.append(_o(PUNTO, p, r, vel, True, pista))
    return lista


def _aterrizar(pista):
    return [_o(TOQUE, None, 0, 78.0, True, pista), _o(DETENER, None, 0, 0.0, True, pista)]


def _circuito():
    mejor = None
    for lado in (1, -1):
        pts = [BASE.mundo(s, l * lado) for s in np.linspace(-6000, BASE.largo + 4000, 40) for l in (3000, 3500, 4000)]
        h = max(float(altura(p[0], p[2])) for p in pts)
        if mejor is None or h < mejor[1]:
            mejor = (lado, h)
    return mejor[0], max(BASE.elev + 450, mejor[1] + 350)


LADO_CIRCUITO, ALT_CIRCUITO = _circuito()


def _leccion(numero, rng, sal):
    b = BASE
    rb = math.radians(b.rumbo)
    if numero == 0:
        inicio = dict(pos=b.mundo(40, 0, b.elev + 2.2), rumbo=rb, vel=0.0, tren=1.0, gases=0.0)
        sal["drones"] = [dict(pos=[rng.uniform(-9000, 9000), rng.uniform(2500, 4500), rng.uniform(-14000, 0)],
                              rumbo=rng.uniform(0, 6.28), vel=190.0, giro=float(rng.choice([-1, 1]) * 0.025),
                              evade=True)]
        obj = [_o(BLANCO, None, 0, 220, None)]
    elif numero == COMBATE:
        inicio = dict(pos=[rng.uniform(-3000, 3000), 4500.0, 9000.0], rumbo=0.0, vel=230.0, tren=0.0, gases=0.78)
        sal["drones"] = [dict(pos=[rng.uniform(-7000, 7000), 4500 + rng.normal(0, 700), -12000 + rng.normal(0, 2500)],
                              rumbo=math.pi + rng.normal(0, 0.3), vel=240.0, giro=0.0, hostil=True)
                         for _ in range(3)]
        obj = [_o(BLANCO, None, 0, 240, False)]
    elif numero == 1:
        inicio = dict(pos=b.mundo(40, 0, b.elev + 2.2), rumbo=rb, vel=0.0, tren=1.0, gases=0.0)
        obj = [_o(DESPEGUE, None, 0, 85.0, None, b),
               _o(PUNTO, b.mundo(b.largo + 4500, rng.normal(0, 150), b.elev + 450), 350, 160, False)]
    elif numero == 2:
        p = b.mundo(b.largo + 3000, 0, b.elev + 500)
        inicio = dict(pos=p, rumbo=rb, cabeceo=math.radians(8), vel=135.0, tren=0.0, gases=0.75)
        d = np.array([math.sin(rb), 0, -math.cos(rb)])
        obj = [_o(PUNTO, p + d * 12000 + [0, 3500, 0], 600, 230, False),
               _o(PUNTO, p + d * 22000 + [0, 3500 + rng.normal(0, 100), 0], 500, 230, False)]
    elif numero == 3:
        x0, z0 = rng.uniform(-6000, 6000), rng.uniform(-6000, 6000)
        r0 = rng.uniform(0, 2 * math.pi)
        y = 3200.0
        inicio = dict(pos=[x0, y, z0], rumbo=r0, vel=200.0, tren=0.0, gases=0.7)
        lista, x, z, r = [], x0, z0, r0
        for giro in (90, -90, 180, -120):
            x += math.sin(r) * 6000
            z -= math.cos(r) * 6000
            r += math.radians(giro + rng.normal(0, 15))
            px, pz = x + math.sin(r) * 4500, z - math.cos(r) * 4500
            px, pz = np.clip(px, -18000, 18000), np.clip(pz, -18000, 18000)
            lista.append(_o(PUNTO, [px, y + rng.normal(0, 200), pz], 450, 200, False))
            x, z = px, pz
        obj = lista
    elif numero == 4:
        p = b.mundo(b.largo + 2500, 0, b.elev + 700)
        inicio = dict(pos=p, rumbo=rb, vel=170.0, tren=0.0, gases=0.7)
        ruta = [(-4500, 1500, 900), (-6000, -4500, 1300), (-1000, -9500, 1500), (5000, -17500, 1300),
                (12500, -17000, 1000)]
        obj = [_o(PUNTO, [x + rng.normal(0, 200), max(h, float(altura(x, z)) + 500), z + rng.normal(0, 200)], 500,
                  190, False) for x, z, h in ruta]
        obj.append(_o(PUNTO, NORTE.mundo(-10500, 0, NORTE.elev + 115 + 10500 * PENDIENTE), 600, 120, None, NORTE))
        obj += _senda(NORTE, (7000, 3500, 1200), (450, 220, 120), 85) + _aterrizar(NORTE)
    elif numero == 5:
        d0 = rng.uniform(13000, 16000)
        p = b.mundo(-d0, rng.normal(0, 500), b.elev + 15 + d0 * PENDIENTE + rng.normal(0, 120))
        inicio = dict(pos=p, rumbo=rb + rng.normal(0, 0.12), vel=125.0, tren=1.0, gases=0.45)
        obj = _senda(b, (10000, 6500, 4000, 2200, 1000, 300), (700, 400, 220, 120, 70, 45), 85) + _aterrizar(b)
    elif numero == 6:
        d0 = rng.uniform(6500, 8000)
        p = b.mundo(-d0, rng.normal(0, 250), b.elev + 15 + d0 * PENDIENTE + rng.normal(0, 60))
        inicio = dict(pos=p, rumbo=rb + rng.normal(0, 0.06), vel=100.0, tren=1.0, gases=0.42)
        obj = _senda(b, (4500, 2500, 1100), (300, 140, 70), 82) + _aterrizar(b)
    elif numero == 7:
        inicio = dict(pos=b.mundo(40, 0, b.elev + 2.2), rumbo=rb, vel=0.0, tren=1.0, gases=0.0)
        lado = LADO_CIRCUITO
        a = ALT_CIRCUITO
        obj = [_o(DESPEGUE, None, 0, 85.0, None, b),
               _o(PUNTO, b.mundo(b.largo + 2500, 0, a), 350, 140, False),
               _o(PUNTO, b.mundo(b.largo + 3500, 3500 * lado, a), 400, 130, None),
               _o(PUNTO, b.mundo(b.largo / 2, 4000 * lado, a), 400, 120, None),
               _o(PUNTO, b.mundo(-5500, 3500 * lado, a), 400, 110, True),
               _o(PUNTO, b.mundo(-9000, 600 * lado, b.elev + 15 + 9000 * PENDIENTE), 450, 100, True)]
        obj += _senda(b, (4500, 2300, 1000), (280, 140, 70), 82) + _aterrizar(b)
    else:
        x0, z0 = rng.uniform(-5000, 5000), rng.uniform(-3000, 8000)
        r0 = rng.uniform(0, 2 * math.pi)
        inicio = dict(pos=[x0, 3500.0, z0], rumbo=r0, vel=230.0, tren=0.0, gases=0.75)
        dist = rng.uniform(12000, 18000)
        ang = r0 + rng.normal(0, 0.5)
        dp = [x0 + math.sin(ang) * dist, 3500 + rng.normal(0, 600), z0 - math.cos(ang) * dist]
        sal["drones"] = [dict(pos=dp, rumbo=r0 + math.pi + rng.normal(0, 0.8), vel=200.0,
                              giro=float(rng.choice([-1, 1]) * rng.uniform(0.0, 0.06)), evade=True)]
        obj = [_o(BLANCO, None, 0, 240, False)]
    return inicio, obj


def _pista(f):
    return PISTAS[f.get("pista", "BASE")]


def _fase_arranque(f, rng, sal):
    a = _pista(f)
    sal["frio"] = True
    inicio = dict(pos=a.mundo(40, 0, a.elev + 2.2), rumbo=math.radians(a.rumbo), vel=0.0, tren=1.0, gases=0.0)
    return inicio, [_o(ARRANQUE, None, 0, 0.0, True, a)]


def _fase_inicio_aire(f, rng, sal):
    if "pista" in f:
        a = _pista(f)
        p = a.mundo(f.get("s", a.largo + 2500), 0, a.elev + f.get("altura", 700))
        rumbo = math.radians(a.rumbo + f.get("rumbo_grados", 0.0))
    else:
        p = np.asarray(f["pos"], dtype=np.float64)
        rumbo = math.radians(f.get("rumbo_grados", 0.0))
    p = p + np.array([rng.normal(0, f.get("ruido", 0.0)), 0, rng.normal(0, f.get("ruido", 0.0))])
    return dict(pos=p, rumbo=rumbo + rng.normal(0, f.get("ruido_rumbo", 0.0)), vel=f.get("vel", 200.0), tren=0.0,
                gases=f.get("gases", 0.7)), []


def _fase_despegue(f, rng, sal):
    a = _pista(f)
    inicio = dict(pos=a.mundo(40, 0, a.elev + 2.2), rumbo=math.radians(a.rumbo), vel=0.0, tren=1.0, gases=0.0)
    obj = [_o(DESPEGUE, None, 0, 85.0, None, a),
           _o(PUNTO, a.mundo(a.largo + f.get("distancia", 4500), rng.normal(0, 150), a.elev + f.get("altura", 450)),
              350, f.get("vel", 160), False)]
    return inicio, obj


def _fase_ruta(f, rng, sal):
    ruido = f.get("ruido", 200.0)
    despeje = f.get("despeje", 500.0)
    obj = []
    for x, z, h in f["puntos"]:
        x, z = x + rng.normal(0, ruido), z + rng.normal(0, ruido)
        obj.append(_o(PUNTO, [x, max(h, float(altura(x, z)) + despeje), z], f.get("radio", 500.0),
                      f.get("vel", 190.0), False))
    return None, obj


def _fase_patrulla(f, rng, sal):
    cx, cz = f["centro"]
    alt = f.get("altura", 5000.0)
    r = math.radians(f.get("rumbo_grados", 90.0))
    u = np.array([math.sin(r), 0, -math.cos(r)])
    w = np.array([-u[2], 0, u[0]])
    c = np.array([cx, alt, cz])
    largo, ancho = f.get("largo", 12000.0) / 2, f.get("ancho", 5000.0) / 2
    obj = []
    for _ in range(f.get("vueltas", 1)):
        for a, b in ((largo, 0), (largo * 0.6, ancho), (-largo, ancho), (-largo * 0.6, 0), (largo * 0.2, -ancho * 0.2)):
            obj.append(_o(PUNTO, c + u * a + w * b + [0, rng.normal(0, 100), 0], f.get("radio", 700.0),
                          f.get("vel", 230.0), False))
    if f.get("intruso", False):
        ang = rng.uniform(0, 2 * math.pi)
        dp = c + np.array([math.sin(ang), 0, -math.cos(ang)]) * rng.uniform(12000, 16000)
        dp[0], dp[2] = np.clip(dp[0], -20000, 20000), np.clip(dp[2], -20000, 20000)
        dp[1] = alt + rng.normal(0, 500)
        sal["drones"].append(dict(pos=dp.tolist(), rumbo=ang + math.pi + rng.normal(0, 0.5), vel=200.0,
                                  giro=float(rng.choice([-1, 1]) * rng.uniform(0.0, 0.05)), evade=True))
        obj.append(_o(BLANCO, None, 0, 240, False))
    return None, obj


def _fase_aterrizaje(f, rng, sal):
    a = _pista(f)
    obj = []
    if f.get("circuito", False):
        lado = LADO_CIRCUITO
        h = ALT_CIRCUITO
        obj += [_o(PUNTO, a.mundo(a.largo + 3500, 3500 * lado, h), 500, 150, False),
                _o(PUNTO, a.mundo(a.largo / 2, 4000 * lado, h), 450, 120, None),
                _o(PUNTO, a.mundo(-5500, 3500 * lado, h), 400, 110, True),
                _o(PUNTO, a.mundo(-9000, 600 * lado, a.elev + 15 + 9000 * PENDIENTE), 450, 100, True)]
        obj += _senda(a, (4500, 2300, 1000), (280, 140, 70), 82)
    else:
        d = f.get("entrada", 10500.0)
        obj.append(_o(PUNTO, a.mundo(-d, 0, a.elev + 115 + d * PENDIENTE), 600, 120, None, a))
        obj += _senda(a, f.get("senda", (7000, 3500, 1200)), f.get("radios", (450, 220, 120)), 85)
    obj += _aterrizar(a)
    return None, obj


FASES = {"arranque": _fase_arranque, "inicio_aire": _fase_inicio_aire, "despegue": _fase_despegue,
         "ruta": _fase_ruta, "patrulla": _fase_patrulla, "aterrizaje": _fase_aterrizaje}


def _validar(m, archivo):
    for clave in ("numero", "id", "nombre", "fases"):
        if clave not in m:
            raise ValueError(f"{os.path.basename(archivo)}: falta «{clave}»")
    for f in m["fases"]:
        if f.get("tipo") != "leccion" and f.get("tipo") not in FASES:
            raise ValueError(f"{os.path.basename(archivo)}: fase desconocida «{f.get('tipo')}»")
    m.setdefault("descripcion", "")
    m.setdefault("duracion", 300)
    m.setdefault("ia", True)
    m.setdefault("curriculo", False)
    m.setdefault("orden", m["numero"])
    return m


def cargar(carpeta=CARPETA):
    misiones = {}
    for archivo in sorted(glob.glob(os.path.join(carpeta, "*.json"))):
        with open(archivo, encoding="utf-8") as fh:
            m = _validar(json.load(fh), archivo)
        if m["numero"] in misiones:
            raise ValueError(f"{os.path.basename(archivo)}: número {m['numero']} repetido")
        misiones[m["numero"]] = m
    if not misiones:
        raise FileNotFoundError(f"No hay misiones en {carpeta}")
    return misiones


MISIONES = cargar()
CURRICULO = [m["numero"] for m in sorted(MISIONES.values(), key=lambda m: m["orden"]) if m["curriculo"]]
LECCIONES = [k for k in CURRICULO if any(f.get("tipo") == "leccion" for f in MISIONES[k]["fases"])]


def mision(numero):
    return MISIONES.get(numero)


def nombre(numero):
    m = MISIONES.get(numero)
    return m["nombre"] if m else "Vuelo libre"


def descripcion(numero):
    m = MISIONES.get(numero)
    return m["descripcion"] if m else "Pista 34 de la Base Aérea Halcón con un dron blanco en la zona."


def duracion(numero):
    m = MISIONES.get(numero)
    return float(m["duracion"]) if m else 1e9


def buscar(clave):
    if clave is None:
        return None
    try:
        n = int(clave)
        return n if n in MISIONES or n == 0 else None
    except ValueError:
        pass
    for m in MISIONES.values():
        if m["id"] == clave:
            return m["numero"]
    return None


def escenario(numero, semilla):
    rng = np.random.default_rng(semilla)
    vto = rng.normal(0, 4, 3) * np.array([1, 0, 1])
    sal = {"viento": vto, "turbulencia": float(rng.uniform(0.2, 1.2)), "drones": [], "frio": False}
    m = MISIONES.get(numero)
    if m is None:
        inicio, obj = _leccion(0, rng, sal)
        sal["inicio"], sal["objetivos"] = inicio, obj
        return sal
    if "misiles" in m:
        sal["misiles"] = int(m["misiles"])
    inicio, obj = None, []
    for f in m["fases"]:
        if f["tipo"] == "leccion":
            ini, o = _leccion(f["numero"], rng, sal)
        else:
            ini, o = FASES[f["tipo"]](f, rng, sal)
        if inicio is None and ini is not None:
            inicio = ini
        obj += o
    if inicio is None:
        raise ValueError(f"La misión {numero} no define un inicio")
    sal["inicio"], sal["objetivos"] = inicio, obj
    return sal
