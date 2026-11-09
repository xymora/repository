import argparse
import sys

import config as C


def lugares(ciudad):
    z = ciudad.zona
    print(f"Zona: {z.nombre} ({z.ancho / 1000:.1f} × {z.alto / 1000:.1f} km)")
    print("Orígenes:")
    for i, o in enumerate(ciudad.origenes, 1):
        lat, lon = z.a_latlon(o.x, o.y)
        print(f"  {i}. {o.nombre} ({o.carga.lower()}) · {lat:.5f}, {lon:.5f}")
    print("Destinos:")
    for i, d in enumerate(ciudad.destinos, 1):
        lat, lon = z.a_latlon(d.x, d.y)
        print(f"  {i}. {d.nombre} (azotea a {d.h:.0f} m) · {lat:.5f}, {lon:.5f}")


def zona_de(args):
    import geo
    tamano = getattr(args, "tamano", 1.0)
    if args.zona in C.ZONAS:
        return geo.Zona(args.zona, tamano=tamano)
    coords = geo.leer_coordenadas(args.zona)
    if coords is None:
        raise SystemExit(f"Zona desconocida: {args.zona}. Usa una de: {', '.join(C.ZONAS)} "
                         'o coordenadas "lat,lon".')
    lat, lon = coords
    return geo.Zona(f"Zona {lat:.4f}, {lon:.4f}", (lat, lon), tamano)


def puntos_latlon(texto, zona):
    return [zona.a_metros(*(float(v) for v in p.split(","))) for p in texto.split(";")]


def volar_consola(args):
    from ciudad import Ciudad
    from navegacion import Planificador
    from simulacion import EVENTOS, Mision

    ciudad = Ciudad(zona_de(args))
    if args.lugares:
        lugares(ciudad)
        return
    if not (1 <= args.origen <= len(ciudad.origenes) and 1 <= args.destino <= len(ciudad.destinos)):
        raise SystemExit("Origen o destino fuera de la lista; usa --lugares para verla.")
    plan = Planificador(ciudad)
    origen = ciudad.origenes[args.origen - 1]
    destino = ciudad.destinos[args.destino - 1]
    eventos = [e for e in (args.eventos or "").split(",") if e]
    for e in eventos:
        if e not in EVENTOS:
            raise SystemExit(f"Evento desconocido: {e}. Usa: {', '.join(EVENTOS)}")
    objetivo = destino.objetivo(True)
    z0 = origen.h + C.ALTURA_DESPEGUE
    if args.puntos:
        puntos = puntos_latlon(args.puntos, ciudad.zona)
        ruta, avisos = plan.ruta_manual(origen.x, origen.y, z0, puntos, objetivo,
                                        args.vehiculo)
        for a in avisos:
            print("Aviso:", a)
    else:
        ruta = plan.ruta_auto(origen.x, origen.y, z0, objetivo, vehiculo=args.vehiculo)
    m = Mision(ciudad, plan, origen, destino, ruta, viento=args.viento,
               direccion=args.direccion, rafagas=not args.sin_rafagas,
               aves=not args.sin_aves, eventos=eventos, semilla=args.semilla,
               bateria=args.bateria / 100, vehiculo=args.vehiculo,
               piloto_ia=args.piloto == "ia")
    impresos = 0
    while not m.terminada:
        m.correr(200)
        for t, texto, _ in m.registro[impresos:]:
            print(f"[{int(t // 60):02d}:{t % 60:04.1f}] {texto}", flush=True)
        impresos = len(m.registro)
        m.nuevos.clear()
    print()
    print(m.resumen())


def entrenar_consola(args, generaciones):
    from ciudad import Ciudad
    from escuela import Entrenador, Paralelo, archivo_mejor, resumen_generacion
    from navegacion import Planificador

    ciudad = Ciudad(zona_de(args))
    plan = Planificador(ciudad)
    e = Entrenador(ciudad, plan, args.vehiculo, args.poblacion, args.continuar)
    par = Paralelo(ciudad, args.vehiculo)
    print(f"Escuela de vuelo: {generaciones} generaciones de {args.poblacion} "
          f"{C.VEHICULOS[args.vehiculo]['nombre'].lower()}s en {ciudad.zona.nombre} "
          f"({par.n} núcleos).\n")
    try:
        for _ in range(generaciones):
            par.evaluar(e.generacion)
            print(resumen_generacion(e.cerrar_generacion()), flush=True)
    finally:
        par.cerrar()
    r = e.record
    if r:
        print(f"\nMejor cerebro: generación {r['generacion']}, nivel {r['nivel']} "
              f"({r['leccion']}), aprobó {r['aprobados']}/{r['escenarios']}"
              + (" — ¡GRADUADO!" if r["graduado"] else ""))
        for linea in r["resultados"]:
            print("  " + linea)
    print(f"Cerebro guardado en: {archivo_mejor(args.vehiculo)}")


def abrir_escuela(args):
    import tkinter as tk

    import geo
    from ciudad import Ciudad
    from interfaz_escuela import EscuelaVentana
    from navegacion import Planificador

    zona = zona_de(args)
    ciudad = Ciudad(zona)
    plan = Planificador(ciudad)
    satelite = geo.imagen_satelital(zona)
    raiz = tk.Tk()
    EscuelaVentana(raiz, ciudad, plan, satelite, args.vehiculo, args.continuar)
    raiz.mainloop()


def main():
    for flujo in (sys.stdout, sys.stderr):
        if hasattr(flujo, "reconfigure"):
            flujo.reconfigure(encoding="utf-8")

    p = argparse.ArgumentParser(description="Simulador de dron de entregas")
    p.add_argument("--origen", type=int, default=1,
                   help="número de farmacia o restaurante (ver --lugares)")
    p.add_argument("--destino", type=int, default=1, help="número de cliente (ver --lugares)")
    p.add_argument("--viento", type=float, default=C.VIENTO, help="m/s a 10 m de altura")
    p.add_argument("--direccion", type=float, default=C.VIENTO_DIRECCION,
                   help="de dónde sopla el viento, en grados (225 = suroeste)")
    p.add_argument("--sin-rafagas", action="store_true")
    p.add_argument("--sin-aves", action="store_true")
    p.add_argument("--eventos", help="fallas programadas: gps,motor,bateria")
    p.add_argument("--bateria", type=float, default=100.0, help="carga inicial en %%")
    p.add_argument("--puntos", help='ruta manual: "lat,lon;lat,lon;..."')
    p.add_argument("--descargar", action="store_true",
                   help="volver a descargar datos de OpenStreetMap e imagen satelital")
    p.add_argument("--sin-gui", action="store_true", help="volar en consola, sin ventana")
    p.add_argument("--lugares", action="store_true", help="listar orígenes y destinos")
    p.add_argument("--semilla", type=int, help="semilla aleatoria (reproducible)")
    p.add_argument("--vehiculo", choices=tuple(C.VEHICULOS), default=C.VEHICULO,
                   help="multirotor (hexacóptero) o avion (avión VTOL de ala fija)")
    p.add_argument("--zona", default=C.ZONA,
                   help=f'ciudad/zona: {", ".join(C.ZONAS)} o coordenadas "lat,lon"')
    p.add_argument("--tamano", type=float, default=1.0,
                   help="tamaño de la zona: 1 = 5.2×3.6 km, 2 = 10×7 km, 3 = 16×11 km "
                        "(para vuelos más largos)")
    p.add_argument("--piloto", choices=("clasico", "ia"), default="clasico",
                   help="clasico (reglas programadas) o ia (cerebro aprendido en la escuela)")
    p.add_argument("--entrenar", nargs="?", const=-1, type=int, metavar="N",
                   help="abrir la escuela de vuelo; con --sin-gui entrena N generaciones")
    p.add_argument("--continuar", action="store_true",
                   help="la escuela parte del mejor cerebro guardado")
    p.add_argument("--poblacion", type=int, default=C.POBLACION)
    args = p.parse_args()
    if args.semilla is not None:
        import random
        random.seed(args.semilla)

    if args.descargar:
        import os
        import geo
        zona = zona_de(args)
        for suf in ("osm.json", "satelite.jpg"):
            if os.path.exists(zona.archivo(suf)):
                os.remove(zona.archivo(suf))
        geo.datos_osm(zona)
        geo.imagen_satelital(zona)
        print("Listo.")
        return
    try:
        import PIL
    except ImportError:
        raise SystemExit("Falta Pillow (para la imagen satelital). Instálalo con:\n"
                         "    python -m pip install pillow")
    if args.entrenar is not None:
        if args.sin_gui:
            entrenar_consola(args, args.entrenar if args.entrenar > 0 else 200)
        else:
            abrir_escuela(args)
        return
    if args.sin_gui or args.lugares:
        volar_consola(args)
        return

    from interfaz import Aplicacion
    args.zona_obj = zona_de(args)
    Aplicacion(args).ejecutar()


if __name__ == "__main__":
    main()
