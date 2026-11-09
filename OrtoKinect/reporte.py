import io
import os
from datetime import datetime

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, KeepTogether

from datos import edad_de, dias_desde, imc
from pruebas import CATALOGO, puntos_evolucion, nombre_serie, unidad, referencia
from biomecanica import NOMBRE_LADO

AZUL = colors.HexColor("#1f6f9f")
GRIS = colors.HexColor("#5b6475")
CLARO = colors.HexColor("#eef3f8")


def _fuentes():
    base = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts")
    for normal, negrita in (("segoeui.ttf", "segoeuib.ttf"), ("arial.ttf", "arialbd.ttf")):
        a, b = os.path.join(base, normal), os.path.join(base, negrita)
        if os.path.exists(a) and os.path.exists(b):
            try:
                pdfmetrics.registerFont(TTFont("Texto", a))
                pdfmetrics.registerFont(TTFont("Texto-B", b))
                pdfmetrics.registerFontFamily("Texto", normal="Texto", bold="Texto-B", italic="Texto", boldItalic="Texto-B")
                return "Texto", "Texto-B"
            except Exception:
                pass
    return "Helvetica", "Helvetica-Bold"


def _fecha(s):
    try:
        return datetime.fromisoformat(s)
    except (TypeError, ValueError):
        return None


def _grafica(clave, pts):
    pid, lado = clave
    fig, ax = plt.subplots(figsize=(4.2, 2.3), dpi=150)
    xs = [_fecha(p[0]) for p in pts]
    ys = [p[1] for p in pts]
    ax.plot(xs, ys, "-o", color="#1f6f9f", lw=2, ms=4)
    ref, et = referencia(pid, pts[-1][2])
    if ref:
        ax.axhline(ref, color="#2e9e5b", ls="--", lw=1.2, label=et)
        ax.legend(fontsize=7, loc="lower right", frameon=False)
    ax.set_title(nombre_serie(clave), fontsize=9, loc="left")
    ax.set_ylabel(unidad(pid), fontsize=8)
    ax.tick_params(labelsize=7)
    ax.grid(alpha=0.25)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%d/%m"))
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    fig.tight_layout()
    b = io.BytesIO()
    fig.savefig(b, format="png")
    plt.close(fig)
    b.seek(0)
    return Image(b, width=8.6 * cm, height=4.7 * cm)


def generar(almacen, pid, ruta):
    p = almacen.obtener(pid) or {}
    regs = almacen.registros(pid)
    f, fb = _fuentes()
    st = {
        "t": ParagraphStyle("t", fontName=fb, fontSize=18, leading=23, textColor=AZUL, spaceAfter=2),
        "s": ParagraphStyle("s", fontName=f, fontSize=9, textColor=GRIS, spaceAfter=10),
        "h": ParagraphStyle("h", fontName=fb, fontSize=12, textColor=AZUL, spaceBefore=10, spaceAfter=5),
        "n": ParagraphStyle("n", fontName=f, fontSize=9, leading=12),
        "c": ParagraphStyle("c", fontName=f, fontSize=8, leading=10),
        "pie": ParagraphStyle("pie", fontName=f, fontSize=7, textColor=GRIS, leading=9),
    }
    doc = SimpleDocTemplate(ruta, pagesize=letter, leftMargin=1.6 * cm, rightMargin=1.6 * cm, topMargin=1.4 * cm, bottomMargin=1.4 * cm,
                            title=f"Reporte OrtoKinect — {p.get('nombre', '')}")
    E = [Paragraph("Reporte de evaluación funcional", st["t"]),
         Paragraph(f"OrtoKinect · Traumatología, Ortopedia y Rehabilitación · {datetime.now():%d/%m/%Y %H:%M}", st["s"])]
    edad = edad_de(p.get("nacimiento"))
    ev = dias_desde(p.get("fecha_evento"))
    i = imc(p)
    filas = [
        ["Paciente", p.get("nombre", "—"), "Expediente", p.get("expediente", "—") or "—"],
        ["Edad", f"{edad} años" if edad is not None else "—", "Sexo", {"F": "Femenino", "M": "Masculino"}.get(p.get("sexo"), "—")],
        ["Estatura", f"{p.get('estatura_cm')} cm" if p.get("estatura_cm") else "—", "Peso / IMC",
         (f"{p.get('peso_kg')} kg" if p.get("peso_kg") else "—") + (f" · IMC {i:.1f}" if i else "")],
        ["Diagnóstico", Paragraph(p.get("diagnostico", "—") or "—", st["c"]), "Tipo", p.get("tipo", "—") or "—"],
        ["Lado afectado", NOMBRE_LADO.get(p.get("lado_afectado"), p.get("lado_afectado") or "—"), "Evolución",
         f"{ev} días ({ev // 7} semanas) desde {p.get('fecha_evento')}" if ev is not None else "—"],
        ["Médico / terapeuta", p.get("medico", "—") or "—", "Evaluaciones", str(len(regs))],
    ]
    t = Table(filas, colWidths=[3.1 * cm, 6.0 * cm, 2.9 * cm, 6.2 * cm])
    t.setStyle(TableStyle([("FONT", (0, 0), (-1, -1), f, 8.5), ("FONT", (0, 0), (0, -1), fb, 8.5), ("FONT", (2, 0), (2, -1), fb, 8.5),
                           ("TEXTCOLOR", (0, 0), (0, -1), GRIS), ("TEXTCOLOR", (2, 0), (2, -1), GRIS),
                           ("BACKGROUND", (0, 0), (-1, -1), CLARO), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                           ("LINEBELOW", (0, 0), (-1, -2), 0.3, colors.white), ("TOPPADDING", (0, 0), (-1, -1), 4)]))
    E.append(t)
    if p.get("objetivos"):
        E += [Paragraph("Objetivos terapéuticos", st["h"]), Paragraph(p["objetivos"].replace("\n", "<br/>"), st["n"])]
    serie = puntos_evolucion(regs)
    if serie:
        E.append(Paragraph("Resumen por prueba (última medición y evolución)", st["h"]))
        cab = ["Prueba", "Primera", "Última", "Cambio", "Referencia", "Dolor (EVA)"]
        filas = [cab]
        for clave in sorted(serie, key=lambda k: (CATALOGO[k[0]]["region"], k[0], str(k[1]))):
            pts = serie[clave]
            u = unidad(clave[0])
            ref, _ = referencia(clave[0], pts[-1][2])
            pr, ul = pts[0][1], pts[-1][1]
            cambio = ul - pr
            if u == "m/s":
                fm = lambda v: f"{v:.2f}"
            elif u in ("°", "rep"):
                fm = lambda v: f"{v:.0f}"
            else:
                fm = lambda v: f"{v:.0f}" if abs(v) >= 10 else f"{v:.1f}"
            sep = "" if u == "°" else " "
            filas.append([Paragraph(nombre_serie(clave), st["c"]), f"{fm(pr)}{sep}{u}", f"{fm(ul)}{sep}{u}",
                          ("+" if cambio >= 0 else "") + f"{fm(cambio)}{sep}{u}" if len(pts) > 1 else "—",
                          f"{fm(ref)}{sep}{u}" if ref else "—", "" if pts[-1][2].get("dolor") is None else f"{pts[-1][2]['dolor']}/10"])
        t = Table(filas, colWidths=[6.2 * cm, 2.2 * cm, 2.2 * cm, 2.3 * cm, 2.6 * cm, 2.3 * cm], repeatRows=1)
        t.setStyle(TableStyle([("FONT", (0, 0), (-1, -1), f, 8), ("FONT", (0, 0), (-1, 0), fb, 8), ("BACKGROUND", (0, 0), (-1, 0), AZUL),
                               ("TEXTCOLOR", (0, 0), (-1, 0), colors.white), ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, CLARO]),
                               ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("ALIGN", (1, 0), (-1, -1), "CENTER")]))
        E.append(t)
        graf = [_grafica(k, v) for k, v in sorted(serie.items(), key=lambda kv: (CATALOGO[kv[0][0]]["region"], kv[0][0], str(kv[0][1])))
                if len(v) >= 2]
        if graf:
            E.append(Paragraph("Evolución", st["h"]))
            filas = [graf[i:i + 2] + ([""] if len(graf[i:i + 2]) == 1 else []) for i in range(0, len(graf), 2)]
            t = Table(filas, colWidths=[8.9 * cm, 8.9 * cm])
            t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
            E.append(t)
    if regs:
        ult = regs[-1]["fecha"][:10]
        hoy = [r for r in regs if r["fecha"][:10] == ult]
        E.append(Paragraph(f"Hallazgos de la última sesión ({datetime.fromisoformat(regs[-1]['fecha']):%d/%m/%Y})", st["h"]))
        for r in hoy:
            sp = CATALOGO.get(r["prueba"], {})
            lado = NOMBRE_LADO.get(r.get("lado"), "")
            bloque = [Paragraph(f"<b>{sp.get('nombre', r['prueba'])}</b>" + (f" · {lado}" if lado and sp.get("tipo") in ("rom", "equilibrio") else "")
                                + (f" · dolor {r['dolor']}/10" if r.get("dolor") is not None else ""), st["n"])]
            for h in r.get("hallazgos", []):
                bloque.append(Paragraph("• " + h, st["c"]))
            if r.get("nota"):
                bloque.append(Paragraph("<i>Nota: " + r["nota"] + "</i>", st["c"]))
            bloque.append(Spacer(1, 4))
            E.append(KeepTogether(bloque))
    if p.get("notas"):
        E += [Paragraph("Notas clínicas", st["h"]), Paragraph(p["notas"].replace("\n", "<br/>"), st["n"])]
    E += [Spacer(1, 12), Paragraph(
        "Mediciones obtenidas por visión (Kinect: cámara y profundidad) con estimación de pose. Son una herramienta de apoyo para "
        "seguimiento y no sustituyen la exploración clínica, la goniometría manual ni los estudios de imagen. Las referencias de "
        "normalidad: rangos articulares AAOS, apoyo unipodal (Springer 2007), sentarse y pararse 30 s (Rikli y Jones) y velocidad de marcha.",
        st["pie"])]
    doc.build(E)
    return ruta
