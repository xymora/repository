# Archivo: install_dependencies.py
# Descripción: Instala todas las librerías necesarias para ejecutar el modelo LUPUS SIM.

import subprocess
import sys

# Lista de paquetes requeridos por los módulos
required_packages = [
    "pandas",
    "matplotlib",
    "pyyaml"
]

# Instala cada paquete usando pip
for package in required_packages:
    try:
        __import__(package)
        print(f"[✔] {package} ya está instalado.")
    except ImportError:
        print(f"[→] Instalando {package}...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", package])
