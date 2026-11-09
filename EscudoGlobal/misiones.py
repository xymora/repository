import config as C
import mundo as M


def _o(t, tipo, n, cada, origen="corea", p_zona=0.7, objetivos=None, ojivas=1, senuelos=0, modo="mixto"):
    o = {"t": t, "tipo": tipo, "n": n, "cada": cada, "origen": origen, "p_zona": p_zona, "ojivas": ojivas,
         "senuelos": senuelos, "modo": modo}
    if objetivos:
        o["objetivos"] = list(objetivos)
    return o


ALASKA = (64.0, -145.7)
CALIFORNIA = (34.7, -120.6)
ALEUTIANAS = (52.7, 174.1)
OKINAWA = (26.3, 127.8)


def _ob(t, tipo, n, cada, bando, contra=None, objetivos=None, ojivas=1, senuelos=0, p_zona=0.75):
    o = _o(t, tipo, n, cada, p_zona=p_zona, objetivos=objetivos, ojivas=ojivas, senuelos=senuelos)
    o.pop("origen")
    o["bando"] = bando
    o["auto_tipo"] = True
    if contra:
        o["contra"] = list(contra)
    return o


RUSIA = {"nombre": "Rusia", "ciudades": ["Moscú", "San Petersburgo", "Kaliningrado", "Novosibirsk"],
         "origenes": ["rusia_oeste", "siberia", "barents"], "ataca": ["OTAN"],
         "tipos": [("exo", 2), ("radar", None), ("alta", 3), ("alta", 3), ("alta", 2)]}
OTAN = {"nombre": "OTAN", "ciudades": ["Washington", "Nueva York", "Londres", "París", "Berlín", "Varsovia", "Vilna"],
        "origenes": ["eeuu", "atlantico", "europa"], "ataca": ["Rusia"],
        "tipos": [("exo", 2), ("exo", 2), ("radar", None), ("buque", 2), ("alta", 3), ("alta", 3), ("alta", 3),
                  ("alta", 3)]}
INDIA = {"nombre": "India", "ciudades": ["Delhi", "Bombay"], "origenes": ["india"], "ataca": ["Pakistán"],
         "tipos": [("alta", 3), ("alta", 2)]}
PAKISTAN = {"nombre": "Pakistán", "ciudades": ["Islamabad", "Karachi", "Lahore"], "origenes": ["pakistan"],
            "ataca": ["India"], "tipos": [("alta", 3), ("alta", 2)]}
COREA_N = {"nombre": "Corea del Norte", "ciudades": [], "origenes": ["corea"], "ataca": ["Corea del Sur y Japón"],
           "activos": []}
ALIADOS_ASIA = {"nombre": "Corea del Sur y Japón", "ciudades": ["Seúl", "Busan", "Tokio", "Osaka"], "origenes": [],
                "ataca": [], "tipos": [("buque", 2), ("alta", 3), ("alta", 3)]}

MISIONES = [
    {
        "nombre": "Primera prueba",
        "descripcion": "Misiles balísticos cortos contra Seúl y Busan. Aprende las capas de gran altitud y terminal.",
        "ciudades": ["Seúl", "Busan"], "origenes": ["corea"], "duracion": 1000, "recargas": 0,
        "activos": [("alta", 36.9, 127.6, 3), ("terminal", 37.45, 127.1, 3), ("terminal", 35.25, 128.95, 2)],
        "oleadas": [_o(30, "corto", 6, 40), _o(400, "corto", 8, 20, p_zona=0.6), _o(700, "corto", 6, 10)],
    },
    {
        "nombre": "Fase de impulso",
        "descripcion": "Misiles medios hacia Tokio y Osaka. El buque los puede derribar mientras todavía suben.",
        "ciudades": ["Tokio", "Osaka"], "origenes": ["corea"], "duracion": 1600, "recargas": 0,
        "activos": [("buque", 40.0, 131.5, 2), ("alta", 35.2, 137.5, 3), ("terminal", 35.65, 139.7, 3)],
        "oleadas": [_o(30, "medio", 6, 60), _o(700, "medio", 8, 25, p_zona=0.6)],
    },
    {
        "nombre": "Rumbo a Guam",
        "descripcion": "Misiles intermedios hacia Guam: la base exoatmosférica intercepta en el espacio.",
        "ciudades": ["Guam", "Naha"], "origenes": ["corea"], "duracion": 2200, "recargas": 0,
        "activos": [("exo", *OKINAWA, 2), ("alta", 13.5, 144.85, 3), ("terminal", 13.45, 144.75, 2),
                    ("terminal", 26.2, 127.7, 2)],
        "oleadas": [_o(30, "intermedio", 5, 90, objetivos=["Guam"]), _o(900, "medio", 6, 40, objetivos=["Naha"]),
                    _o(1200, "intermedio", 4, 40, objetivos=["Guam"])],
    },
    {
        "nombre": "Señuelos",
        "descripcion": "Cada misil suelta señuelos en el espacio. El radar de discriminación distingue la ojiva real.",
        "ciudades": ["Guam", "Tokio"], "origenes": ["corea"], "duracion": 2300, "recargas": 0,
        "activos": [("radar", 35.3, 135.9), ("exo", *OKINAWA, 2), ("alta", 13.5, 144.85, 3),
                    ("terminal", 13.45, 144.75, 2), ("alta", 35.4, 138.6, 3), ("terminal", 35.65, 139.7, 2)],
        "oleadas": [_o(30, "intermedio", 4, 120, objetivos=["Guam"], senuelos=3),
                    _o(600, "medio", 4, 60, objetivos=["Tokio"], senuelos=2),
                    _o(1300, "intermedio", 3, 50, objetivos=["Guam"], senuelos=3)],
    },
    {
        "nombre": "Ojivas múltiples",
        "descripcion": "El objetivo se divide en varias ojivas antes de caer: derríbalo mientras sube o prepárate para muchas.",
        "ciudades": ["Tokio", "Osaka", "Sapporo"], "origenes": ["corea"], "duracion": 1800, "recargas": 1,
        "activos": [("buque", 40.0, 131.5, 2), ("alta", 35.2, 137.5, 3), ("alta", 42.8, 141.6, 2),
                    ("terminal", 35.65, 139.7, 3), ("terminal", 34.7, 135.5, 2)],
        "oleadas": [_o(30, "medio", 4, 120, ojivas=3, senuelos=1), _o(800, "medio", 4, 60, ojivas=2, senuelos=2)],
    },
    {
        "nombre": "Hawái",
        "descripcion": "Intercontinentales contra Honolulu: casi media hora de vuelo, defensa en el espacio y en la reentrada.",
        "ciudades": ["Honolulu", "Anchorage"], "origenes": ["corea"], "duracion": 3600, "recargas": 0,
        "activos": [("exo", *ALASKA, 2), ("radar", *ALEUTIANAS), ("alta", 21.4, -158.0, 3),
                    ("terminal", 21.3, -157.9, 2), ("terminal", 61.2, -149.8, 2)],
        "oleadas": [_o(30, "icbm", 4, 120, objetivos=["Honolulu"], senuelos=2),
                    _o(1200, "icbm", 3, 90, objetivos=["Honolulu", "Anchorage"], senuelos=2)],
    },
    {
        "nombre": "Planeador hipersónico",
        "descripcion": "Planeadores que vuelan bajo y maniobran: el radar los ve tarde y sólo las capas bajas los alcanzan.",
        "ciudades": ["Guam", "Naha", "Taipéi"], "origenes": ["corea"], "duracion": 2000, "recargas": 1,
        "activos": [("alta", 13.5, 144.85, 3), ("terminal", 13.45, 144.75, 2), ("alta", 26.0, 127.0, 3),
                    ("terminal", 26.2, 127.7, 2), ("alta", 24.75, 121.2, 2), ("terminal", 25.05, 121.55, 2)],
        "oleadas": [_o(30, "planeador", 4, 90, objetivos=["Naha", "Taipéi"]),
                    _o(500, "planeador", 4, 80, objetivos=["Guam"]), _o(900, "medio", 6, 30, objetivos=["Naha", "Taipéi"])],
    },
    {
        "nombre": "Costa del Pacífico",
        "descripcion": "Intercontinentales con 3 ojivas y 3 señuelos contra Seattle, San Francisco y Los Ángeles.",
        "ciudades": ["Seattle", "San Francisco", "Los Ángeles"], "origenes": ["corea"], "duracion": 4000,
        "recargas": 1,
        "activos": [("exo", *ALASKA, 2), ("exo", *CALIFORNIA, 2), ("radar", *ALEUTIANAS),
                    ("alta", 34.1, -118.4, 3), ("alta", 37.6, -122.2, 3), ("terminal", 34.05, -118.25, 2),
                    ("terminal", 37.75, -122.4, 2), ("terminal", 47.6, -122.3, 2)],
        "oleadas": [_o(30, "icbm", 3, 200, ojivas=3, senuelos=3), _o(1500, "icbm", 3, 120, ojivas=2, senuelos=2)],
    },
    {
        "nombre": "Submarino frente a México",
        "descripcion": "Un submarino lanza desde el Pacífico contra Ciudad de México, Pachuca y Guadalajara: hay muy poco tiempo.",
        "ciudades": ["Ciudad de México", "Pachuca", "Guadalajara"], "origenes": ["pac_este"], "duracion": 1500,
        "recargas": 1,
        "activos": [("buque", 16.5, -108.0, 2), ("radar", 19.1, -104.3), ("alta", 19.8, -99.4, 3),
                    ("alta", 20.6, -103.2, 2), ("terminal", 19.43, -99.13, 3), ("terminal", 20.1, -98.76, 2),
                    ("terminal", 20.66, -103.35, 2)],
        "oleadas": [_o(30, "medio", 5, 40, origen="pac_este", p_zona=0.8),
                    _o(600, "medio", 4, 60, origen="pac_este", ojivas=2, senuelos=2)],
    },
    {
        "nombre": "Tormenta global",
        "descripcion": "Todo a la vez desde tres orígenes: intercontinentales con ojivas múltiples, submarinos y planeadores.",
        "ciudades": ["Los Ángeles", "San Francisco", "Seattle", "Honolulu", "Ciudad de México", "Pachuca",
                     "Guadalajara"], "origenes": ["corea", "pac_norte", "pac_este"], "duracion": 4200, "recargas": 1,
        "activos": [("exo", *ALASKA, 2), ("exo", *CALIFORNIA, 2), ("radar", *ALEUTIANAS), ("radar", 19.1, -104.3),
                    ("buque", 16.5, -108.0, 2), ("alta", 34.1, -118.4, 3), ("alta", 37.6, -122.2, 2),
                    ("alta", 21.4, -158.0, 2), ("alta", 19.8, -99.4, 3), ("terminal", 34.05, -118.25, 2),
                    ("terminal", 19.43, -99.13, 3), ("terminal", 21.3, -157.9, 2), ("terminal", 20.66, -103.35, 2)],
        "oleadas": [_o(30, "icbm", 3, 200, objetivos=["Los Ángeles", "San Francisco", "Seattle"], ojivas=3, senuelos=2),
                    _o(300, "intermedio", 3, 120, origen="pac_norte", objetivos=["Honolulu", "Seattle"], senuelos=2),
                    _o(900, "medio", 4, 60, origen="pac_este", objetivos=["Ciudad de México", "Pachuca", "Guadalajara"]),
                    _o(1400, "planeador", 2, 150, objetivos=["Honolulu"]),
                    _o(2000, "icbm", 3, 150, objetivos=["Ciudad de México", "Guadalajara", "Los Ángeles"], ojivas=2,
                       senuelos=2)],
    },
]

def _fuera_de_ciudades(m):
    zonas = zonas_de(m)
    activos = []
    for k, a in enumerate(m["activos"]):
        lat, lon = a[1], a[2]
        for z in zonas:
            if z.distancia(lat, lon) < z.r + 4:
                lat, lon = M.destino(z.lat, z.lon, 200.0 + 75.0 * k, z.r + 7)
        activos.append((a[0], lat, lon, *a[3:]))
    m["activos"] = activos


MISIONES += [
    {
        "nombre": "Rusia contra la OTAN",
        "descripcion": "Intercambio mutuo: Rusia ataca a la OTAN y la OTAN responde. Cada bando defiende sus ciudades.",
        "bandos": [RUSIA, OTAN], "duracion": 3600, "recargas": 1,
        "oleadas": [_ob(30, "icbm", 4, 150, "Rusia", objetivos=["Washington", "Nueva York"], ojivas=3, senuelos=3),
                    _ob(60, "intermedio", 6, 60, "Rusia", objetivos=["Londres", "París", "Berlín"], ojivas=2, senuelos=2),
                    _ob(90, "medio", 6, 40, "Rusia", objetivos=["Varsovia", "Vilna", "Berlín"]),
                    _ob(400, "icbm", 4, 120, "OTAN", objetivos=["Moscú", "San Petersburgo", "Novosibirsk"], ojivas=3, senuelos=2),
                    _ob(500, "intermedio", 4, 90, "OTAN", objetivos=["Moscú", "Kaliningrado"], senuelos=2),
                    _ob(1500, "icbm", 3, 100, "Rusia", ojivas=2, senuelos=2), _ob(1700, "icbm", 3, 100, "OTAN", ojivas=2, senuelos=2)],
    },
    {
        "nombre": "Guerra global",
        "descripcion": "Varios conflictos a la vez: Rusia y la OTAN, India y Pakistán, Corea del Norte contra sus vecinos.",
        "bandos": [RUSIA, OTAN, INDIA, PAKISTAN, COREA_N, ALIADOS_ASIA], "duracion": 3600, "recargas": 1,
        "oleadas": [_ob(30, "icbm", 3, 200, "Rusia", ojivas=3, senuelos=2), _ob(60, "intermedio", 4, 80, "Rusia", ojivas=2, senuelos=1),
                    _ob(300, "icbm", 3, 180, "OTAN", ojivas=3, senuelos=2), _ob(40, "medio", 6, 50, "India"),
                    _ob(70, "medio", 6, 50, "Pakistán"), _ob(100, "corto", 6, 40, "Corea del Norte"),
                    _ob(500, "medio", 5, 60, "Corea del Norte", objetivos=["Tokio", "Osaka"], ojivas=2, senuelos=2),
                    _ob(900, "corto", 6, 30, "India"), _ob(950, "corto", 6, 30, "Pakistán")],
    },
]

def _def(ciudades, tipos):
    return {"nombre": "Defensa", "ciudades": list(ciudades), "origenes": [], "ataca": [], "activos": None,
            "tipos": list(tipos)}


def _atk(nombre, origenes):
    return {"nombre": nombre, "ciudades": [], "origenes": list(origenes), "ataca": ["Defensa"], "activos": []}


def _pais(nombre):
    if nombre in M.ZONAS_PAIS:
        return _atk(nombre, M.ZONAS_PAIS[nombre])
    lat, lon, r = M.PAISES[nombre]
    return _atk(nombre, [M.origen_propio(nombre, lat, lon, r)])


MISIONES += [
    {
        "nombre": "Cuba contra México",
        "descripcion": "Misiles cortos y medios desde muy cerca: hay pocos minutos para reaccionar.",
        "bandos": [_def(["Ciudad de México", "Monterrey", "Guadalajara", "Pachuca"], [("alta", 3), ("alta", 3), ("radar", None)]),
                   _pais("Cuba")], "duracion": 1400, "recargas": 1,
        "oleadas": [_ob(30, "medio", 8, 25, "Cuba"), _ob(400, "corto", 10, 15, "Cuba", objetivos=["Monterrey"]),
                    _ob(800, "medio", 10, 12, "Cuba", ojivas=2, senuelos=1)],
    },
    {
        "nombre": "Irán contra Europa",
        "descripcion": "Misiles intermedios con señuelos contra cuatro capitales europeas.",
        "bandos": [_def(["Roma", "Madrid", "París", "Berlín"], [("exo", 2), ("radar", None), ("buque", 2), ("alta", 3), ("alta", 3)]),
                   _pais("Irán")], "duracion": 2000, "recargas": 1,
        "oleadas": [_ob(30, "intermedio", 6, 60, "Irán", senuelos=3), _ob(700, "medio", 8, 30, "Irán", senuelos=2),
                    _ob(1200, "intermedio", 6, 40, "Irán", ojivas=2, senuelos=2)],
    },
    {
        "nombre": "Estrecho de Taiwán",
        "descripcion": "China lanza misiles medios y planeadores hipersónicos contra Taipéi, Naha y Manila.",
        "bandos": [_def(["Taipéi", "Naha", "Manila"], [("alta", 3), ("alta", 3), ("alta", 3), ("radar", None)]),
                   _pais("China")], "duracion": 1800, "recargas": 1,
        "oleadas": [_ob(30, "medio", 10, 20, "China", objetivos=["Taipéi"]), _ob(300, "planeador", 4, 60, "China"),
                    _ob(700, "medio", 8, 25, "China", ojivas=2, senuelos=2), _ob(1100, "planeador", 4, 40, "China")],
    },
    {
        "nombre": "Corea del Norte contra Estados Unidos",
        "descripcion": "Intercontinentales con ojivas múltiples sobre el este y el oeste de Estados Unidos.",
        "bandos": [_def(["Washington", "Nueva York", "Chicago", "Los Ángeles"],
                        [("exo", 2), ("exo", 2), ("radar", None), ("radar", None), ("alta", 3), ("alta", 3)]),
                   _pais("Corea del Norte")], "duracion": 3600, "recargas": 1,
        "oleadas": [_ob(30, "icbm", 4, 150, "Corea del Norte", ojivas=3, senuelos=2),
                    _ob(1200, "icbm", 4, 100, "Corea del Norte", ojivas=2, senuelos=3)],
    },
    {
        "nombre": "Frontera oriental de Europa",
        "descripcion": "Saturación de misiles cortos desde Rusia y Bielorrusia contra Varsovia y el Báltico.",
        "bandos": [_def(["Varsovia", "Vilna", "Riga", "Tallin", "Helsinki"], [("alta", 3), ("alta", 3), ("alta", 3)]),
                   _pais("Rusia"), _pais("Bielorrusia")], "duracion": 1500, "recargas": 2,
        "oleadas": [_ob(30, "corto", 14, 8, "Bielorrusia"), _ob(60, "medio", 10, 15, "Rusia"),
                    _ob(600, "corto", 16, 6, "Bielorrusia"), _ob(650, "medio", 12, 10, "Rusia", ojivas=2, senuelos=1)],
    },
    {
        "nombre": "Submarinos en el Atlántico",
        "descripcion": "Lanzamientos desde el mar muy cerca de la costa: casi no hay tiempo de rastreo.",
        "bandos": [_def(["Nueva York", "Washington", "Londres"], [("alta", 3), ("alta", 3), ("buque", 2), ("radar", None)]),
                   _atk("Submarinos", ["atlantico"])], "duracion": 1500, "recargas": 1,
        "oleadas": [_ob(30, "medio", 8, 30, "Submarinos"), _ob(500, "intermedio", 6, 40, "Submarinos", senuelos=2),
                    _ob(1000, "medio", 8, 20, "Submarinos", ojivas=2, senuelos=1)],
    },
    {
        "nombre": "Varios frentes sobre el Pacífico",
        "descripcion": "China, Rusia y Corea del Norte atacan a la vez la costa oeste de Norteamérica.",
        "bandos": [_def(["Seattle", "San Francisco", "Los Ángeles", "Anchorage"],
                        [("exo", 2), ("exo", 2), ("radar", None), ("alta", 3), ("alta", 3), ("alta", 3)]),
                   _pais("China"), _pais("Rusia"), _pais("Corea del Norte")], "duracion": 3600, "recargas": 1,
        "oleadas": [_ob(30, "icbm", 3, 150, "China", ojivas=3, senuelos=2), _ob(200, "icbm", 3, 150, "Rusia", ojivas=2, senuelos=3),
                    _ob(400, "icbm", 3, 120, "Corea del Norte", senuelos=2), _ob(800, "planeador", 3, 90, "China")],
    },
    {
        "nombre": "Saturación total",
        "descripcion": "Cuatro atacantes a la vez contra cinco capitales del mundo: la prueba final.",
        "bandos": [_def(["Londres", "París", "Tokio", "Washington", "Ciudad de México"],
                        [("exo", 2), ("exo", 2), ("radar", None), ("radar", None), ("buque", 2), ("alta", 3), ("alta", 3),
                         ("alta", 3), ("alta", 3), ("alta", 3)]),
                   _pais("Rusia"), _pais("China"), _pais("Irán"), _pais("Corea del Norte")], "duracion": 3600, "recargas": 2,
        "oleadas": [_ob(30, "icbm", 4, 120, "Rusia", ojivas=3, senuelos=3), _ob(100, "intermedio", 6, 60, "Irán", senuelos=2),
                    _ob(300, "icbm", 4, 120, "China", ojivas=2, senuelos=2), _ob(500, "medio", 6, 50, "Corea del Norte"),
                    _ob(1500, "icbm", 4, 90, "Rusia", ojivas=2, senuelos=2), _ob(1600, "planeador", 3, 80, "China")],
    },
]

def _nuc(o, p):
    o["nuclear"] = p
    return o


MISIONES += [
    {
        "nombre": "Amenaza nuclear de Corea del Norte",
        "descripcion": "Algunos misiles llevan ojiva nuclear: si uno cae, la ciudad queda arrasada. Hay que derribarlos todos.",
        "bandos": [_def(["Seúl", "Busan", "Tokio", "Osaka"], [("alta", 3), ("alta", 3), ("exo", 2), ("radar", None)]),
                   _pais("Corea del Norte")], "duracion": 1800, "recargas": 1,
        "oleadas": [_nuc(_ob(30, "medio", 6, 40, "Corea del Norte"), 0.3),
                    _nuc(_ob(600, "intermedio", 4, 60, "Corea del Norte", senuelos=2), 0.5),
                    _nuc(_ob(1100, "medio", 6, 25, "Corea del Norte", ojivas=2, senuelos=1), 0.3)],
    },
    {
        "nombre": "Ojiva nuclear entre señuelos",
        "descripcion": "Intercontinentales que esconden ojivas nucleares entre muchos señuelos: discriminar es vital.",
        "bandos": [_def(["Washington", "Nueva York", "Chicago"],
                        [("exo", 2), ("exo", 2), ("radar", None), ("radar", None), ("alta", 3), ("alta", 3)]),
                   _pais("Rusia")], "duracion": 3000, "recargas": 1,
        "oleadas": [_nuc(_ob(30, "icbm", 4, 150, "Rusia", ojivas=3, senuelos=4), 0.4),
                    _nuc(_ob(1200, "icbm", 3, 120, "Rusia", ojivas=2, senuelos=3), 0.4)],
    },
    {
        "nombre": "Ataque nuclear contra la OTAN",
        "descripcion": "Rusia lanza ojivas nucleares contra la OTAN. Si la OTAN derriba el 90 % o más, contraataca sola al final.",
        "bandos": [RUSIA, dict(OTAN, ataca=[])], "duracion": 3000, "recargas": 1,
        "oleadas": [_nuc(_ob(30, "icbm", 5, 150, "Rusia", objetivos=["Washington", "Nueva York"], ojivas=3, senuelos=3), 0.5),
                    _nuc(_ob(60, "intermedio", 6, 60, "Rusia", objetivos=["Londres", "París", "Berlín"], senuelos=2), 0.3),
                    _nuc(_ob(120, "medio", 8, 30, "Rusia", objetivos=["Varsovia", "Vilna"]), 0.2)],
    },
    {
        "nombre": "Guerra nuclear global",
        "descripcion": "Rusia, China y Corea del Norte lanzan ojivas nucleares a la vez. Sólo un escudo casi perfecto evita la catástrofe.",
        "bandos": [_def(["Washington", "Londres", "París", "Tokio", "Seúl"],
                        [("exo", 2), ("exo", 2), ("radar", None), ("radar", None), ("buque", 2), ("alta", 3), ("alta", 3),
                         ("alta", 3), ("alta", 3)]),
                   _pais("Rusia"), _pais("China"), _pais("Corea del Norte")], "duracion": 3600, "recargas": 2,
        "oleadas": [_nuc(_ob(30, "icbm", 4, 120, "Rusia", ojivas=3, senuelos=3), 0.5),
                    _nuc(_ob(200, "icbm", 4, 120, "China", ojivas=2, senuelos=2), 0.5),
                    _nuc(_ob(400, "medio", 6, 40, "Corea del Norte"), 0.4),
                    _nuc(_ob(1500, "planeador", 3, 80, "China"), 0.5)],
    },
]

NUMERO_MISIONES = len(MISIONES)
NOMBRES = [m["nombre"] for m in MISIONES]


def zonas_lista(ciudades, bando=""):
    zonas = []
    for c in ciudades or []:
        if isinstance(c, M.Zona):
            z = c.copia()
        elif isinstance(c, dict):
            z = M.Zona(c["nombre"], c["lat"], c["lon"], c.get("r", 15.0), c.get("valor", 2))
        elif isinstance(c, (tuple, list)):
            z = M.ciudad(c[0], c[1])
        else:
            z = M.ciudad(c)
        if bando:
            z.bando = bando
        zonas.append(z)
    return zonas


def zonas_de(mision):
    if mision.get("bandos"):
        return [z for b in bandos_de(mision) for z in zonas_lista(b["ciudades"], b["nombre"])]
    return zonas_lista(mision.get("ciudades", []))


def completar(m):
    activos = list(m["activos"])
    centros = [M.centro_origen(M.registrar_origen(o)) for o in m.get("origenes", [])]
    for z in zonas_de(m):
        o = min(centros, key=lambda q: M.distancia(z.lat, z.lon, *q)) if centros else M.destino(z.lat, z.lon, 270.0, 3000.0)
        rumbo = M.rumbo(z.lat, z.lon, *o)
        cerca = lambda tipo, d: any(a[0] == tipo and M.distancia(a[1], a[2], z.lat, z.lon) <= d for a in activos)
        if not cerca("alta", 0.8 * C.CAPAS["alta"]["alcance"]):
            activos.append(("alta", *M.destino(z.lat, z.lon, rumbo, 45.0), 2))
        if not cerca("terminal", 50.0):
            activos.append(("terminal", *M.destino(z.lat, z.lon, rumbo, min(z.r * 0.4 + 4.0, 18.0)), 2))
    m["activos"] = activos


for _m in MISIONES:
    if "activos" in _m:
        completar(_m)
        _fuera_de_ciudades(_m)


def mision(numero):
    return MISIONES[(int(numero) - 1) % NUMERO_MISIONES]


def libre(bandos, duracion=4 * 3600, mirv=True, nuclear=False):
    bandos = normalizar(bandos)
    partes = [f"{b['nombre']} → {', '.join(b['ataca'])}" for b in bandos if b["ataca"]]
    return {"nombre": "Comandante", "descripcion": ("Bandos: " + "; ".join(partes) if partes else "Nadie ataca todavía") +
            ". Oleadas continuas.", "bandos": bandos, "duracion": duracion, "recargas": 99, "oleadas": [],
            "continuo": True, "mirv": bool(mirv), "nuclear": C.P_NUCLEAR_LIBRE if nuclear else 0.0}


TIPOS_AUTO = [("alta", 3)]


def _plano(x):
    if isinstance(x, dict):
        return {k: _plano(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_plano(v) for v in x]
    return x


def _origenes_enemigos(b, bandos):
    return [o for x in bandos if b["nombre"] in x.get("ataca", []) for o in x.get("origenes", [])]


def normalizar(bandos):
    bandos = _plano(bandos)
    nombres = [b["nombre"] for b in bandos]
    for b in bandos:
        b["ciudades"] = [zona_a_dict(z) for z in zonas_lista(b.get("ciudades", []))]
        b["origenes"] = [o for o in b.get("origenes", []) if isinstance(o, dict) or o in M.ORIGENES]
        for o in b["origenes"]:
            M.registrar_origen(o)
        b["ataca"] = [x for x in b.get("ataca", []) if x in nombres and x != b["nombre"]]
    for b in bandos:
        if b.get("activos") is None:
            enemigos = [M.registrar_origen(o) for o in _origenes_enemigos(b, bandos)]
            tipos = [tuple(t) for t in (b.get("tipos") or TIPOS_AUTO)]
            b["activos"] = [list(a) + [None] * (4 - len(a)) for a in
                            desplegar(tipos, zonas_lista(b["ciudades"]), enemigos)]
        else:
            b["activos"] = [list(a) + [None] * (4 - len(a)) for a in b["activos"]]
    return bandos


def bandos_de(m):
    if m.get("bandos"):
        return normalizar(m["bandos"])
    orgs = list(m.get("origenes", []))
    nombre = M.ORIGENES[M.registrar_origen(orgs[0])]["nombre"] if len(orgs) == 1 else "Atacante"
    return normalizar([
        {"nombre": "Defensa", "ciudades": zonas_lista(m.get("ciudades", [])), "origenes": [], "ataca": [],
         "activos": [list(a) for a in m.get("activos", [])]},
        {"nombre": nombre, "ciudades": [], "origenes": orgs, "ataca": ["Defensa"], "activos": []},
    ])


def con_bandos(m, bandos):
    bandos = normalizar(bandos)
    m2 = dict(m)
    m2["bandos"] = bandos
    atacantes = [b for b in bandos if b["ataca"] and b["origenes"]]
    nombres_ciudad = {c["nombre"] for b in bandos for c in b["ciudades"]}
    olas = []
    base = list(m.get("oleadas", []))
    if atacantes and base:
        explicitos = {o.get("bando") for o in base}
        propios = all(b["nombre"] in explicitos for b in atacantes) and all(o.get("bando") in {a["nombre"] for a in atacantes} for o in base)
        total = max(len(base), len(atacantes))
        for i in range(total):
            o2 = dict(base[i % len(base)])
            if not propios or i >= len(base):
                o2["bando"] = atacantes[i % len(atacantes)]["nombre"]
                o2.pop("contra", None)
            if o2.get("objetivos"):
                o2["objetivos"] = [n for n in o2["objetivos"] if n in nombres_ciudad]
                if not o2["objetivos"]:
                    o2.pop("objetivos")
            o2["auto_tipo"] = True
            olas.append(o2)
    m2["oleadas"] = olas
    partes = []
    for b in bandos:
        if b["ataca"]:
            partes.append(f"{b['nombre']} ataca a {', '.join(b['ataca'])}")
    m2["descripcion"] = ("Bandos: " + "; ".join(partes) + ". " if partes else "Nadie ataca todavía. ") + \
        m["descripcion"].split(".")[0] + "."
    m2["personalizada"] = True
    return m2


def zona_de_dict(c):
    return M.Zona(c["nombre"], c["lat"], c["lon"], c.get("r", 15.0), c.get("valor", 2))


def zona_a_dict(z):
    return {"nombre": z.nombre, "lat": round(z.lat, 5), "lon": round(z.lon, 5), "r": round(z.r, 1), "valor": z.valor}


def _alejar_de_origen(lat, lon, hacia_lat, hacia_lon):
    for _ in range(60):
        if M.en_origen(lat, lon) is None:
            break
        lat, lon = M.hacia(lat, lon, hacia_lat, hacia_lon, 60.0)
    return lat, lon


def _lado(lat, lon, rumbo, k, paso):
    if k == 0:
        return lat, lon
    signo = 1 if k % 2 else -1
    return M.destino(lat, lon, rumbo + 90.0 * signo, paso * ((k + 1) // 2))


def desplegar(tipos, zonas, origenes):
    if not zonas:
        return []
    zonas = sorted(zonas, key=lambda z: -z.valor)
    c = M.centroide([(z.lat, z.lon) for z in zonas], [z.valor for z in zonas])
    claves = [M.registrar_origen(o) for o in origenes]
    centros = [M.centro_origen(o) for o in claves] or [M.destino(*c, 0.0, 3000.0)]
    cajas = [M.ORIGENES[o]["caja"] for o in claves] or [None]
    lejanos = [o for o in centros if M.distancia(*c, *o) > 2500]
    tipos = list(tipos)
    for tipo, lz in (("exo", 2), ("radar", None)):
        while sum(1 for t in tipos if t[0] == tipo) < min(len(lejanos), 4):
            tipos.append((tipo, lz))
    while sum(1 for t in tipos if t[0] == "terminal") < len(zonas):
        tipos.append(("terminal", 2))
    while sum(1 for t in tipos if t[0] == "alta") < len(zonas):
        tipos.append(("alta", 3))
    nz = len(zonas)
    activos = []
    cuenta = {}
    for tipo, lz in tipos:
        i = cuenta.get(tipo, 0)
        cuenta[tipo] = i + 1
        if tipo == "terminal":
            z = zonas[i % nz]
            k = i // nz
            o = min(centros, key=lambda q: M.distancia(z.lat, z.lon, *q))
            rumbo = M.rumbo(z.lat, z.lon, *o)
            giro = (0, 72, -72, 144, -144, 180, 36, -36, 108, -108)[k % 10]
            d = min(z.r * 0.5 + 6.0, 22.0) if k else min(z.r * 0.4 + 4.0, 18.0)
            lat, lon = M.destino(z.lat, z.lon, rumbo + giro, d)
        elif tipo == "alta":
            z = zonas[i % nz]
            k = i // nz
            o = centros[(i // nz) % len(centros)] if len(centros) > 1 else centros[0]
            dz = M.distancia(z.lat, z.lon, *o)
            rumbo = M.rumbo(z.lat, z.lon, *o)
            giro = (0, 30, -30, 60, -60, 90, -90)[k % 7]
            d = min(max(dz * 0.2, 35.0), 90.0)
            lat, lon = M.destino(z.lat, z.lon, rumbo + giro, d)
        elif tipo == "buque":
            j = i % len(centros)
            k = i // len(centros)
            o = centros[j]
            caja = cajas[j] if j < len(cajas) else None
            if caja is not None:
                la0, la1, lo0, lo1 = caja
                medio = 0.5 * M.distancia(la0, lo0, la1, lo1)
            else:
                medio = 300.0
            lat, lon = M.hacia(*o, *c, min(medio * 0.75, 600.0))
            lat, lon = _alejar_de_origen(lat, lon, *c)
            lat, lon = M.hacia(lat, lon, *c, 80.0)
            lat, lon = _lado(lat, lon, M.rumbo(*o, *c), k, 250.0)
        else:
            lista = lejanos or centros
            o = lista[i % len(lista)]
            k = i // len(lista)
            dc = M.distancia(*c, *o)
            frac = 0.45 if tipo == "radar" else 0.3
            d = min(dc * frac, 1500.0 if tipo == "radar" else 2200.0)
            lat, lon = M.hacia(*c, *o, d)
            lat, lon = _lado(lat, lon, M.rumbo(*c, *o), k, 400.0 if tipo == "radar" else 300.0)
            lat, lon = _alejar_de_origen(lat, lon, *c)
        activos.append((tipo, lat, lon) + ((lz,) if lz is not None else ()))
    return activos


def personalizar(m, ciudades=None, origenes=None):
    m2 = dict(m)
    zonas = [zona_de_dict(c) for c in ciudades] if ciudades else zonas_de(m)
    orgs = [M.registrar_origen(o) for o in (origenes or m["origenes"])]
    orgs = [o for o in orgs if o in M.ORIGENES] or list(m["origenes"])
    nombres = {z.nombre for z in zonas}
    olas = []
    for i, o in enumerate(m.get("oleadas", [])):
        o2 = dict(o)
        if o2.get("objetivos"):
            o2["objetivos"] = [n for n in o2["objetivos"] if n in nombres]
            if not o2["objetivos"]:
                o2.pop("objetivos")
        if o2.get("origen") not in orgs:
            o2["origen"] = orgs[i % len(orgs)]
        o2["auto_tipo"] = True
        olas.append(o2)
    m2["oleadas"] = olas
    m2["ciudades"] = zonas
    m2["origenes"] = orgs
    if ciudades or set(orgs) != set(m["origenes"]):
        tipos = [(a[0], a[3] if len(a) > 3 else None) for a in m["activos"]]
        m2["activos"] = desplegar(tipos, zonas, orgs)
    lista = ", ".join(z.nombre for z in zonas[:4]) + ("…" if len(zonas) > 4 else "")
    atacantes = ", ".join(M.ORIGENES[o]["nombre"] for o in orgs)
    m2["descripcion"] = f"Tu teatro: {lista} contra {atacantes}. " + m["descripcion"].split(".")[0] + "."
    m2["personalizada"] = True
    return m2


def preparar(numero, cfg=None):
    cfg = cfg or {}
    mis = dict(mision(numero))
    for clave in ("satelites", "salva"):
        if clave in cfg:
            mis[clave] = cfg[clave]
    if cfg.get("bandos"):
        return con_bandos(mis, cfg["bandos"]), {"lanzadores": cfg.get("lanzadores") or None}
    if cfg.get("ciudades") or cfg.get("origenes"):
        mis = personalizar(mis, cfg.get("ciudades"), cfg.get("origenes"))
    if cfg.get("activos"):
        mis = dict(mis)
        mis["activos"] = [tuple(a) if a[3] is not None else tuple(a[:3]) for a in cfg["activos"]]
    return mis, {"lanzadores": cfg.get("lanzadores") or None}
