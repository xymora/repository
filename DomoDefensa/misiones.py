import math

import config as C
import mundo as M

M_POR_GRADO = 6378137.0 * math.pi / 180
MAX_LUGARES = 6
RADIO_LUGARES = 15000.0


def _o(t, tipo, n, cada, modo="zonas", p_zona=1.0, frente="norte"):
    return {"t": t, "tipo": tipo, "n": n, "cada": cada, "modo": modo, "p_zona": p_zona, "frente": frente}


MISIONES = [
    {
        "nombre": "Primera alerta",
        "descripcion": "Salvas de cohetes cortos contra San Ciro. Intercepta todo lo que caiga en la ciudad.",
        "bateria": (40, 39), "zonas": ["San Ciro"], "frentes": ["norte"], "duracion": 230, "recargas": 0,
        "oleadas": [_o(10, "corto", 6, 3.0), _o(80, "corto", 8, 2.0), _o(150, "corto", 10, 1.2)],
    },
    {
        "nombre": "Campo abierto",
        "descripcion": "Muchos cohetes caerán en el campo. No gastes interceptores en lo que no amenaza.",
        "bateria": (42, 37), "zonas": ["San Ciro", "Roca Blanca"], "frentes": ["norte"], "duracion": 260,
        "recargas": 0,
        "oleadas": [_o(10, "corto", 10, 2.5, "mixto", 0.35), _o(90, "corto", 12, 1.5, "mixto", 0.35),
                    _o(170, "corto", 14, 1.0, "mixto", 0.3)],
    },
    {
        "nombre": "Saturación",
        "descripcion": "Salvas densas de cohetes cortos y medios sobre dos ciudades y la propia batería.",
        "bateria": (42, 37), "zonas": ["San Ciro", "Roca Blanca"], "frentes": ["norte"],
        "duracion": 300, "recargas": 1,
        "oleadas": [_o(10, "corto", 14, 0.6, "mixto", 0.5), _o(14, "medio", 5, 1.5, "mixto", 0.6),
                    _o(120, "corto", 18, 0.5, "mixto", 0.45), _o(125, "medio", 8, 1.0, "mixto", 0.5),
                    _o(220, "corto", 16, 0.4, "mixto", 0.5)],
    },
    {
        "nombre": "Morteros en la frontera",
        "descripcion": "Fuego de mortero de vuelo corto contra Puesto Norte, con cohetes hacia San Ciro.",
        "bateria": (37, 45), "zonas": ["Puesto Norte", "San Ciro"], "frentes": ["norte"], "duracion": 280,
        "recargas": 0,
        "oleadas": [_o(10, "mortero", 8, 4.0, "mixto", 0.6), _o(60, "corto", 8, 2.0, "mixto", 0.5),
                    _o(120, "mortero", 12, 2.0, "mixto", 0.55), _o(190, "corto", 10, 1.0, "mixto", 0.5),
                    _o(200, "mortero", 8, 1.5, "mixto", 0.6)],
    },
    {
        "nombre": "Enjambre",
        "descripcion": "Drones lentos que buscan la batería y las ciudades mientras caen cohetes.",
        "bateria": (42, 37), "zonas": ["San Ciro", "Roca Blanca"], "frentes": ["norte"], "duracion": 520,
        "recargas": 0,
        "oleadas": [_o(5, "dron", 4, 25.0, "bateria"), _o(20, "dron", 6, 15.0, "mixto", 0.7),
                    _o(120, "corto", 12, 1.5, "mixto", 0.5), _o(300, "corto", 14, 1.0, "mixto", 0.45)],
    },
    {
        "nombre": "Dos frentes",
        "descripcion": "Ataques simultáneos del norte y del este contra el oriente del valle.",
        "bateria": (56, 28), "zonas": ["Mirasol", "Nueva Aurora", "Roca Blanca"], "frentes": ["norte", "este"],
        "duracion": 320, "recargas": 1,
        "oleadas": [_o(10, "medio", 8, 2.0, "mixto", 0.5), _o(12, "corto", 10, 1.5, "mixto", 0.5, "este"),
                    _o(130, "corto", 14, 0.8, "mixto", 0.45, "este"), _o(135, "medio", 10, 1.2, "mixto", 0.5),
                    _o(240, "corto", 12, 0.6, "mixto", 0.5, "este")],
    },
    {
        "nombre": "Reubicación",
        "descripcion": "Protege San Ciro, luego la batería se traslada a cubrir Puerto Lumen.",
        "bateria": (40, 39), "zonas": ["San Ciro", ("Puerto Lumen", False)], "frentes": ["norte"],
        "duracion": 1760, "recargas": 1,
        "oleadas": [_o(10, "corto", 10, 2.0, "mixto", 0.5), _o(70, "corto", 10, 1.0, "mixto", 0.5),
                    _o(1500, "medio", 12, 2.0, "mixto", 0.6), _o(1600, "medio", 14, 1.0, "mixto", 0.55)],
        "eventos": [{"t": 120, "accion": "activar", "zona": "Puerto Lumen"},
                    {"t": 120, "accion": "desactivar", "zona": "San Ciro"},
                    {"t": 121, "accion": "cubrir"}],
    },
    {
        "nombre": "Tormenta",
        "descripcion": "Todo a la vez: cohetes, morteros y drones desde dos direcciones con pocas recargas.",
        "bateria": (31, 43), "zonas": ["San Ciro", "Valle Alto", "Puesto Norte"],
        "frentes": ["norte", "noreste"], "duracion": 460, "recargas": 2,
        "oleadas": [_o(5, "dron", 6, 12.0, "mixto", 0.7), _o(15, "corto", 16, 0.7, "mixto", 0.45),
                    _o(20, "medio", 6, 2.0, "mixto", 0.5, "noreste"), _o(110, "mortero", 10, 1.5, "mixto", 0.6),
                    _o(170, "corto", 20, 0.4, "mixto", 0.45), _o(175, "medio", 8, 1.0, "mixto", 0.5, "noreste"),
                    _o(300, "corto", 18, 0.5, "mixto", 0.45), _o(305, "dron", 4, 8.0, "bateria")],
    },
]

MISIONES += [
    {
        "nombre": "Red de baterías",
        "descripcion": "Cinco poblaciones separadas: tres baterías se reparten la cobertura y comparten el fuego.",
        "bateria": (31, 43), "n_baterias": 3,
        "zonas": ["Valle Alto", "San Ciro", "Roca Blanca", "Cerro Verde", "Puesto Norte"], "frentes": ["norte"],
        "duracion": 360, "recargas": 1,
        "oleadas": [_o(10, "corto", 14, 0.8, "mixto", 0.5), _o(15, "medio", 8, 1.5, "mixto", 0.55),
                    _o(120, "mortero", 8, 2.0, "mixto", 0.6), _o(150, "corto", 18, 0.5, "mixto", 0.45),
                    _o(160, "medio", 10, 0.8, "mixto", 0.5), _o(260, "corto", 16, 0.5, "mixto", 0.5)],
    },
    {
        "nombre": "Defensa en profundidad",
        "descripcion": "Dos frentes y drones que cazan baterías: si una cae, las otras deben cubrir sus zonas.",
        "bateria": (56, 28), "n_baterias": 3,
        "zonas": ["Mirasol", "Nueva Aurora", "Roca Blanca", "Puerto Lumen"], "frentes": ["norte", "este"],
        "duracion": 480, "recargas": 1,
        "oleadas": [_o(5, "dron", 6, 10.0, "bateria"), _o(15, "medio", 10, 1.2, "mixto", 0.5),
                    _o(20, "corto", 12, 1.0, "mixto", 0.5, "este"), _o(150, "dron", 4, 8.0, "bateria"),
                    _o(170, "medio", 14, 0.7, "mixto", 0.5), _o(180, "corto", 14, 0.6, "mixto", 0.5, "este"),
                    _o(320, "medio", 12, 0.6, "mixto", 0.5), _o(330, "corto", 12, 0.5, "mixto", 0.5, "este")],
    },
]

NUMERO_MISIONES = len(MISIONES)
NOMBRES = [m["nombre"] for m in MISIONES]


def zonas_de(mision):
    zonas = []
    for z in mision["zonas"]:
        activa = True
        if isinstance(z, (tuple, list)):
            z, activa = z
        if isinstance(z, str):
            zz = M.pueblo(z)
        else:
            zz = z.copia()
        zz.activa = activa
        zonas.append(zz)
    return zonas


def mision(numero):
    return MISIONES[(int(numero) - 1) % NUMERO_MISIONES]


def libre(zonas, bateria, duracion=600, frentes=("norte", "este", "noreste"), lanzadores=3):
    if bateria and isinstance(bateria[0], (tuple, list)):
        bateria = bateria[0]
    return {"nombre": "Comandante", "descripcion": "Zonas y despliegue definidos por ti. Oleadas continuas.",
            "bateria": (bateria[0] / 1000, bateria[1] / 1000), "zonas": [z.copia() for z in zonas],
            "frentes": list(frentes), "duracion": duracion, "recargas": 99, "oleadas": [],
            "lanzadores": int(lanzadores),
            "continuo": True}


def ancla(mision):
    zonas = zonas_de(mision)
    activas = [z for z in zonas if z.activa] or zonas
    peso = sum(z.valor for z in activas)
    return sum(z.x * z.valor for z in activas) / peso, sum(z.y * z.valor for z in activas) / peso


def relativas(lugares):
    lat0, lon0 = lugares[0]["lat"], lugares[0]["lon"]
    k = M_POR_GRADO * math.cos(math.radians(lat0))
    return [((l["lon"] - lon0) * k, (l["lat"] - lat0) * M_POR_GRADO) for l in lugares]


def zonas_lugar(mision, lugares):
    rel = relativas(lugares)
    pesos = [max(float(l.get("valor", 2)), 0.1) for l in lugares]
    cx = sum(p * x for p, (x, _) in zip(pesos, rel)) / sum(pesos)
    cy = sum(p * y for p, (_, y) in zip(pesos, rel)) / sum(pesos)
    ax, ay = ancla(mision)
    zonas = [M.Zona(l["nombre"], ax + x - cx, ay + y - cy, l["r"], l.get("valor", 2), "area")
             for l, (x, y) in zip(lugares, rel)]
    frentes = mision.get("frentes", ["norte"])
    lo_x, hi_x, lo_y, hi_y = 4000.0, C.MAPA_W - 4000, 4000.0, C.MAPA_H - 4000
    margen = 3000.0
    if "norte" in frentes or "noreste" in frentes:
        hi_y = min(hi_y, M.FRENTES["norte"][1] - margen)
    if "sur" in frentes:
        lo_y = max(lo_y, M.FRENTES["sur"][3] + margen)
    if "este" in frentes:
        hi_x = min(hi_x, M.FRENTES["este"][0] - margen)
    if "oeste" in frentes:
        lo_x = max(lo_x, M.FRENTES["oeste"][2] + margen)
    dx = dy = 0.0
    x0, x1 = min(z.x - z.r for z in zonas), max(z.x + z.r for z in zonas)
    y0, y1 = min(z.y - z.r for z in zonas), max(z.y + z.r for z in zonas)
    if x1 > hi_x:
        dx = hi_x - x1
    if x0 + dx < lo_x:
        dx = lo_x - x0
    if y1 > hi_y:
        dy = hi_y - y1
    if y0 + dy < lo_y:
        dy = lo_y - y0
    for z in zonas:
        z.x += dx
        z.y += dy
    return zonas


DESCRIPCION_REAL = {
    "Morteros en la frontera": "Fuego de mortero de vuelo corto y cohetes contra el área protegida.",
    "Reubicación": "Una primera tanda de cohetes y, mucho después, una segunda de cohetes medios.",
    "Red de baterías": "Tres baterías se reparten la cobertura y comparten el fuego.",
}


def con_lugar(mision, lugares):
    m = dict(mision)
    m["eventos"] = [e for e in mision.get("eventos", []) if e["accion"] not in ("activar", "desactivar")]
    nombres = ", ".join(l["nombre"] for l in lugares[:3]) + ("…" if len(lugares) > 3 else "")
    desc = DESCRIPCION_REAL.get(mision["nombre"], mision["descripcion"])
    for n, *_ in M.PUEBLOS:
        desc = desc.replace(n, "el área protegida")
    m["descripcion"] = f"En el mapa real: {nombres}. " + desc.replace("dos ciudades", "las áreas")
    m["lugar"] = True
    return m


def preparar(numero, cfg=None):
    cfg = cfg or {}
    mis = mision(numero)
    extra = {"n_baterias": cfg.get("baterias") or None, "lanzadores": cfg.get("lanzadores") or None}
    lugares = cfg.get("lugares")
    if lugares:
        extra["zonas"] = zonas_lugar(mis, lugares)
        extra["n_baterias"] = extra["n_baterias"] or mis.get("n_baterias") or 1
        mis = con_lugar(mis, lugares)
    return mis, extra
