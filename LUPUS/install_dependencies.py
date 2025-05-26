# Archivo: install_dependencies.py
# Descripción: Instala todas las librerías necesarias para ejecutar el modelo LUPUS SIM.

import subprocess
import sys

# Mapeo: nombre pip => nombre módulo
required_packages = {
    "pandas": "pandas",
    "matplotlib": "matplotlib",
    "pyyaml": "yaml"
}

print("📦 Iniciando verificación e instalación de dependencias...\n")

for pip_name, import_name in required_packages.items():
    try:
        __import__(import_name)
        print(f"[✔] {pip_name} ya está instalado.")
    except ImportError:
        print(f"[→] Instalando {pip_name}...")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", pip_name])
            print(f"[✓] {pip_name} instalado correctamente.\n")
        except subprocess.CalledProcessError:
            print(f"[✖] Error al instalar {pip_name}. Intenta instalarlo manualmente.")

print("\n✅ Proceso de instalación finalizado.")
