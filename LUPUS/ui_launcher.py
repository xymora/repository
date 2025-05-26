# Archivo: ui_launcher.py
# Descripción: Interfaz gráfica simple para lanzar la simulación desde un botón.

import tkinter as tk
from main_simulation import run_simulation

# Define la función que se ejecutará al presionar el botón
def on_run():
    status_label.config(text="Ejecutando simulación...")
    root.update()
    run_simulation()
    status_label.config(text="Simulación finalizada. Resultados generados.")

# Crea la ventana principal
root = tk.Tk()
root.title("LUPUS SIM - Lanzador de Simulación")
root.geometry("400x200")

# Texto de encabezado
title = tk.Label(root, text="Modelo LUPUS SIM", font=("Helvetica", 16, "bold"))
title.pack(pady=10)

# Botón de ejecución
run_button = tk.Button(root, text="Ejecutar Simulación", command=on_run, font=("Helvetica", 12))
run_button.pack(pady=10)

# Área de estado
status_label = tk.Label(root, text="Esperando acción...", font=("Helvetica", 10), fg="blue")
status_label.pack(pady=20)

# Inicia la aplicación
root.mainloop()
