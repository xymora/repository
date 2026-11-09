import os
import re
import unicodedata

import config as C
from consola import ABAJO, ARRIBA, DERECHA, IZQUIERDA

NUMEROS = {"un": 1, "una": 1, "uno": 1, "one": 1, "dos": 2, "two": 2, "tres": 3, "three": 3,
           "cuatro": 4, "four": 4, "cinco": 5, "five": 5, "seis": 6, "six": 6, "siete": 7,
           "seven": 7, "nueve": 9, "nine": 9, "ocho": 8, "eight": 8, "diez": 10, "ten": 10}

FUNCIONES = [
    ("saltar", r"salt|brinc|jump|hop"),
    ("disparar", r"dispar|fire|shoot|tir[ao]|lanz|throw|bomb"),
    ("atacar", r"atac|attack|golpe|punch|kick|patad|espad|sword|slash|hit"),
    ("correr", r"corre|run|dash|acelera|accelerat|turbo|speed"),
    ("frenar", r"fren|brake"),
    ("pausa", r"paus"),
    ("comenzar", r"comenz|empez|inici|start the|begin|start game|\bplay\b|jugar"),
    ("menú", r"men[uú]|inventar|item|objeto|mapa|map|seleccion"),
    ("confirmar", r"confirm|acept|accept|ok\b|habla|talk|examin|leer|read|interact|abrir|open"),
    ("cancelar", r"cancel|volver|back|regres"),
    ("cambiar", r"cambi|switch|change|altern|rot|gir"),
    ("agarrar", r"agarr|tom[ao]|grab|pick|lift|levant|carg"),
    ("defender", r"defen|bloq|block|escud|shield|guard"),
]

OBJETIVOS = [
    ("puntos", r"punt|score|points"),
    ("monedas", r"moned|coin|anill|ring|gema|gem|diamant|cristal"),
    ("vidas", r"vida|lives|\blife\b|intento"),
    ("tiempo", r"tiempo|time|reloj|clock|segundo"),
    ("enemigos", r"enemig|enem|monstru|monster|villan"),
    ("llaves", r"llave|\bkey"),
    ("jefe", r"jefe|\bboss"),
    ("niveles", r"nivel|level|stage|etapa|mundo|world|zona|zone|fase|round"),
    ("salud", r"salud|energ|health|\bhp\b|corazon|heart"),
]

PATRON_BOTON = re.compile(
    r"(?i:bot[oó]n|button|tecla|key|presiona(?:r|ndo)?|pulsa(?:r|ndo)?|oprime|aprieta|press(?:ing)?|push|tap|hold|mant[eé]n)"
    r"\s+(?i:el\s+|la\s+|the\s+)?[\"'«(]?(A|B|START|SELECT|Start|Select)\b"
    r"|\b(A|B|START|SELECT|Start|Select)[\"'»)]?\s*(?:(?i:button|bot[oó]n)|:|=|→|->|–|\+|-(?=\s))",
)


def _plano(t):
    t = unicodedata.normalize("NFKD", t)
    return "".join(c for c in t if not unicodedata.combining(c)).lower()


def leer_archivo(ruta):
    ext = os.path.splitext(ruta)[1].lower()
    if ext == ".pdf":
        try:
            from pypdf import PdfReader
        except ImportError:
            raise RuntimeError("para leer PDF instala pypdf (pip install pypdf) o guarda las instrucciones como .txt")
        return "\n".join((p.extract_text() or "") for p in PdfReader(ruta).pages)
    for cod in ("utf-8", "cp1252", "latin-1"):
        try:
            with open(ruta, encoding=cod) as f:
                return f.read()
        except UnicodeDecodeError:
            continue
    return ""


def ruta_guardada(id_juego):
    return os.path.join(C.CARPETA_INSTRUCCIONES, id_juego + ".txt")


def buscar(id_juego, ruta_rom=None):
    propia = ruta_guardada(id_juego)
    if os.path.exists(propia):
        return leer_archivo(propia)
    if ruta_rom:
        base = os.path.splitext(ruta_rom)[0]
        for ext in (".txt", ".md", ".pdf"):
            if os.path.exists(base + ext):
                try:
                    texto = leer_archivo(base + ext)
                except RuntimeError:
                    continue
                guardar(id_juego, texto)
                return texto
    return ""


def guardar(id_juego, texto):
    os.makedirs(C.CARPETA_INSTRUCCIONES, exist_ok=True)
    with open(ruta_guardada(id_juego), "w", encoding="utf-8") as f:
        f.write(texto)


def _funcion(frag):
    p = _plano(frag)
    for nombre, patron in FUNCIONES:
        if re.search(patron, p):
            return nombre
    return None


def analizar(texto):
    res = {"botones": {}, "vidas": None, "objetivos": [], "usa_select": False, "hay_texto": bool(texto.strip())}
    if not texto.strip():
        res["acciones"] = acciones(res)
        return res
    for m in PATRON_BOTON.finditer(texto):
        boton = (m.group(1) or m.group(2)).upper()
        fin = m.end()
        corte = re.search(r"[.\n;]", texto[fin:fin + 120])
        frag = texto[fin:fin + (corte.start() if corte else 120)]
        inicio = max(0, m.start() - 60)
        previo = texto[inicio:m.start()].split("\n")[-1].split(".")[-1]
        f = _funcion(frag) or _funcion(previo)
        if boton not in res["botones"] or (res["botones"][boton] is None and f):
            res["botones"][boton] = f
    plano = _plano(texto)
    m = re.search(r"\b(\d+|" + "|".join(NUMEROS) + r")\s+(?:vidas|lives|intentos|oportunidades|chances)", plano) or \
        re.search(r"(?:vidas|lives)\s*[:=x×]\s*(\d+)", plano)
    if m:
        v = m.group(1)
        res["vidas"] = int(v) if v.isdigit() else NUMEROS.get(v)
    for nombre, patron in OBJETIVOS:
        if re.search(patron, plano):
            res["objetivos"].append(nombre)
    res["usa_select"] = "SELECT" in res["botones"] and res["botones"]["SELECT"] not in (None, "pausa")
    res["acciones"] = acciones(res)
    return res


def acciones(res):
    b = res.get("botones", {})
    lista = [[], [DERECHA], [IZQUIERDA], [ARRIBA], [ABAJO],
             ["A"], [DERECHA, "A"], [IZQUIERDA, "A"],
             ["B"], [DERECHA, "B"], [IZQUIERDA, "B"],
             [ARRIBA, "A"], [ABAJO, "B"], ["START"]]
    if b.get("B") == "correr" or b.get("A") == "correr":
        lista += [[DERECHA, "A", "B"], [IZQUIERDA, "A", "B"]]
    if res.get("usa_select"):
        lista.append(["SELECT"])
    return lista


def nombre_accion(botones):
    flechas = {ARRIBA: "↑", ABAJO: "↓", IZQUIERDA: "←", DERECHA: "→"}
    if not botones:
        return "·"
    return "".join(flechas.get(x, "") for x in botones) + "".join(x[:2] if x in ("START", "SELECT") else x
                                                                   for x in botones if x not in flechas)


def resumen(res):
    lineas = []
    if not res["hay_texto"]:
        return ["Sin instrucciones: uso todos los botones y busco vidas/puntos solo."]
    for boton in ("A", "B", "START", "SELECT"):
        if boton in res["botones"]:
            lineas.append(f"{boton}: {res['botones'][boton] or 'mencionado'}")
    if res["vidas"]:
        lineas.append(f"Vidas iniciales: {res['vidas']}")
    if res["objetivos"]:
        lineas.append("Objetivos: " + ", ".join(res["objetivos"]))
    lineas.append(f"Acciones de la IA: {len(res['acciones'])}")
    return lineas
