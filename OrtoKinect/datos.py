import csv
import json
import os
import re
import shutil
import time
import unicodedata
from datetime import date, datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parent / "datos"
PACIENTES = RAIZ / "pacientes"
PAPELERA = RAIZ / "papelera"

CAMPOS = [
    ("nombre", "Nombre completo"), ("expediente", "Expediente"), ("nacimiento", "Fecha de nacimiento (AAAA-MM-DD)"),
    ("sexo", "Sexo"), ("estatura_cm", "Estatura (cm)"), ("peso_kg", "Peso (kg)"), ("telefono", "Teléfono"),
    ("diagnostico", "Diagnóstico"), ("tipo", "Tipo de caso"), ("lado_afectado", "Lado afectado"),
    ("fecha_evento", "Fecha de cirugía o lesión (AAAA-MM-DD)"), ("medico", "Médico / terapeuta"),
    ("objetivos", "Objetivos"), ("notas", "Notas clínicas"),
]
TIPOS = ["Postquirúrgico", "Lesión aguda", "Dolor crónico", "Neurológico", "Adulto mayor / caídas", "Deportivo", "Preventivo"]


def _slug(s):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")[:30] or "paciente"


def fecha_de(s):
    try:
        return datetime.strptime(str(s).strip(), "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


def edad_de(s):
    d = fecha_de(s)
    if d is None:
        return None
    h = date.today()
    return h.year - d.year - ((h.month, h.day) < (d.month, d.day))


def dias_desde(s):
    d = fecha_de(s)
    return None if d is None else (date.today() - d).days


def imc(p):
    try:
        e = float(p.get("estatura_cm")) / 100
        return float(p.get("peso_kg")) / (e * e)
    except (TypeError, ValueError, ZeroDivisionError):
        return None


def _escribir(ruta, obj):
    tmp = ruta.with_suffix(ruta.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
    os.replace(tmp, ruta)


class Almacen:
    def __init__(self, raiz=None):
        self.base = Path(raiz) if raiz else PACIENTES
        self.base.mkdir(parents=True, exist_ok=True)

    def _dir(self, pid):
        return self.base / pid

    def listar(self):
        out = []
        for d in self.base.iterdir():
            f = d / "paciente.json"
            if f.exists():
                try:
                    out.append(json.loads(f.read_text(encoding="utf-8")))
                except (OSError, json.JSONDecodeError):
                    pass
        return sorted(out, key=lambda p: p.get("nombre", "").lower())

    def obtener(self, pid):
        f = self._dir(pid) / "paciente.json"
        return json.loads(f.read_text(encoding="utf-8")) if f.exists() else None

    def guardar(self, p):
        p = dict(p)
        if not p.get("id"):
            p["id"] = f"{_slug(p.get('nombre', ''))}_{int(time.time())}"
            p["creado"] = datetime.now().isoformat(timespec="seconds")
        p["modificado"] = datetime.now().isoformat(timespec="seconds")
        d = self._dir(p["id"])
        d.mkdir(parents=True, exist_ok=True)
        _escribir(d / "paciente.json", p)
        return p

    def eliminar(self, pid):
        d = self._dir(pid)
        if d.exists():
            PAPELERA.mkdir(parents=True, exist_ok=True)
            shutil.move(str(d), str(PAPELERA / f"{pid}_{int(time.time())}"))

    def registros(self, pid):
        f = self._dir(pid) / "registros.jsonl"
        if not f.exists():
            return []
        out = []
        for linea in f.read_text(encoding="utf-8").splitlines():
            if linea.strip():
                try:
                    out.append(json.loads(linea))
                except json.JSONDecodeError:
                    pass
        return sorted(out, key=lambda r: r.get("fecha", ""))

    def agregar(self, pid, reg):
        reg = dict(reg)
        reg.setdefault("id", f"r{int(time.time() * 1000)}")
        reg.setdefault("fecha", datetime.now().isoformat(timespec="seconds"))
        d = self._dir(pid)
        d.mkdir(parents=True, exist_ok=True)
        with open(d / "registros.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps(reg, ensure_ascii=False) + "\n")
        return reg

    def eliminar_registro(self, pid, rid):
        regs = [r for r in self.registros(pid) if r.get("id") != rid]
        d = self._dir(pid)
        tmp = d / "registros.jsonl.tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            for r in regs:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        os.replace(tmp, d / "registros.jsonl")

    def carpeta(self, pid, sub=""):
        d = self._dir(pid) / sub if sub else self._dir(pid)
        d.mkdir(parents=True, exist_ok=True)
        return d

    def exportar_csv(self, pid, ruta):
        from pruebas import valor_principal, CATALOGO
        regs = self.registros(pid)
        p = self.obtener(pid) or {}
        claves = []
        for r in regs:
            for k, v in r.get("metricas", {}).items():
                if isinstance(v, (int, float, str)) and k not in claves:
                    claves.append(k)
        with open(ruta, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f)
            w.writerow(["paciente", "expediente", "fecha", "prueba", "lado", "valor_principal", "unidad", "dolor_eva", "nota", "hallazgos"] + claves)
            for r in regs:
                v, u = valor_principal(r)
                m = r.get("metricas", {})
                w.writerow([p.get("nombre", ""), p.get("expediente", ""), r.get("fecha", ""),
                            CATALOGO.get(r.get("prueba"), {}).get("nombre", r.get("prueba")), r.get("lado", ""),
                            "" if v is None else v, u, r.get("dolor", ""), r.get("nota", ""), " | ".join(r.get("hallazgos", []))]
                           + [m.get(k, "") if isinstance(m.get(k, ""), (int, float, str)) else "" for k in claves])
        return ruta
