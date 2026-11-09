import argparse
import multiprocessing as mp


def main():
    ap = argparse.ArgumentParser(description="Escudo Global: defensa antimisiles por capas con IA")
    ap.add_argument("--modo", default="entrenar", choices=["entrenar", "campeon", "jugar", "comandante"])
    ap.add_argument("--rapido", action="store_true", help="entrena sin gráficos en la consola (Ctrl+C detiene)")
    ap.add_argument("--rapido-gui", action="store_true", help="entrena sin gráficos en una ventana pequeña")
    ap.add_argument("--datos", default=None, help="carpeta del avance de la IA (por defecto datos\\)")
    ap.add_argument("--minutos", type=float, default=None)
    ap.add_argument("--generaciones", type=int, default=None)
    ap.add_argument("--sin-entrenar", action="store_true", help="abre la interfaz sin iniciar el entrenamiento")
    a = ap.parse_args()
    if a.rapido:
        import evolucion
        evolucion.entrenar_consola(a.minutos, a.generaciones, a.datos)
        return
    if a.rapido_gui:
        import rapido_gui
        rapido_gui.VentanaRapida(dir_datos=a.datos).correr()
        return
    import interfaz
    app = interfaz.App(a.modo, entrenar=not a.sin_entrenar, dir_datos=a.datos)
    if app.correr() == "rapido":
        import rapido_gui
        rapido_gui.VentanaRapida(app.ent, a.datos).correr()


if __name__ == "__main__":
    mp.freeze_support()
    main()
