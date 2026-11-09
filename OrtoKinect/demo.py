from datetime import datetime, timedelta

from pruebas import CATALOGO

NOMBRE = "Paciente de demostración"


def _rom(pid, izq, der, dolor):
    n = CATALOGO[pid]["normal"]
    lados = {l: dict(repeticiones=5, rom_max=v, rom_prom=round(v * 0.96, 1), pct_normal=round(v / n * 100, 1), reps_con_comp=0)
             for l, v in (("izq", izq), ("der", der))}
    lsi = round(der / izq * 100, 1)
    return dict(prueba=pid, nombre=CATALOGO[pid]["nombre"], lado="ambos", dolor=dolor,
                metricas=dict(lados=lados, rom_max=min(izq, der), lsi=lsi),
                hallazgos=[f"Izquierdo: {izq:.0f}° de {n}° normales ({izq / n * 100:.0f}%)",
                           f"Derecho: {der:.0f}° de {n}° normales ({der / n * 100:.0f}%)",
                           f"Índice de simetría (afectado / sano): {lsi:.0f}%"])


def asegurar(alm):
    if any(p.get("nombre") == NOMBRE for p in alm.listar()):
        return
    hoy = datetime.now().replace(hour=10, minute=0, second=0, microsecond=0)
    cir = hoy - timedelta(days=52)
    p = alm.guardar(dict(nombre=NOMBRE, expediente="DEMO-001", nacimiento="1958-03-10", sexo="F", estatura_cm="162", peso_kg="68",
                         diagnostico="Reparación artroscópica de manguito rotador derecho", tipo="Postquirúrgico", lado_afectado="der",
                         fecha_evento=cir.strftime("%Y-%m-%d"), medico="Fisioterapia", telefono="",
                         objetivos="Recuperar abducción y flexión de hombro derecho > 150°.\nMejorar equilibrio y marcha para prevenir caídas.",
                         notas="Datos generados para demostrar el programa; no corresponden a una persona real.",
                         plan=["hombro_flex", "hombro_abd", "equilibrio", "sts30", "marcha"]))
    semanas = [(-35, 92, 88, 7, 9.0, 0.78, 8), (-28, 110, 104, 6, 12.5, 0.84, 9), (-21, 121, 117, 5, 15.0, 0.88, 10),
               (-14, 133, 128, 4, 18.5, 0.93, 11), (-7, 141, 138, 3, 21.0, 0.97, 12)]
    for d, abd, flex, dolor, eq, vel, sts in semanas:
        f = hoy + timedelta(days=d)
        regs = [
            _rom("hombro_abd", 172, abd, dolor),
            _rom("hombro_flex", 175, flex, max(0, dolor - 1)),
            dict(prueba="equilibrio", nombre=CATALOGO["equilibrio"]["nombre"], lado="der", dolor=0,
                 metricas=dict(tiempo=eq, pierna_apoyo="der", esperado=26.9),
                 hallazgos=[f"Apoyo en pierna derecha: {eq:.1f} s", "Por debajo de lo esperado para la edad (≈27 s)" if eq < 21.5 else
                            "Dentro de lo esperado para la edad (≈27 s)"]),
            dict(prueba="sts30", nombre=CATALOGO["sts30"]["nombre"], lado="ambos", dolor=0,
                 metricas=dict(repeticiones=sts, normal_min=11, normal_max=16),
                 hallazgos=[f"{sts} repeticiones completas en 30 s", "Por debajo del rango normal para su edad (11–16)" if sts < 11 else
                            "Dentro del rango normal para su edad (11–16)"]),
            dict(prueba="marcha", nombre=CATALOGO["marcha"]["nombre"], lado="ambos", dolor=0,
                 metricas=dict(velocidad=vel, cadencia=round(96 + vel * 8, 1)),
                 hallazgos=[f"Velocidad de marcha: {vel:.2f} m/s", "Velocidad menor a 0.8 m/s: marcha limitada" if vel < 0.8 else
                            "Velocidad entre 0.8 y 1.0 m/s: marcha funcional con limitación"]),
        ]
        for k, r in enumerate(regs):
            r["fecha"] = (f + timedelta(minutes=k * 6)).isoformat(timespec="seconds")
            r["id"] = f"demo{d}_{k}"
            r["fuente"] = "Demostración"
            alm.agregar(p["id"], r)
