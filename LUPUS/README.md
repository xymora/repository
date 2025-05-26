# 🧬 LUPUS – Simulación de Intervenciones Inmunológicas

Este proyecto modela computacionalmente la evolución inmunológica en pacientes con **lupus eritematoso sistémico (LES)**, evaluando estrategias como:

- 💉 Vacuna tolerogénica  
- 🧬 siRNA anti-BAFF  
- 🧪 Anticuerpo anti-IFN-α  
- 🧫 Exosomas de MSCs  

El sistema simula dinámicas inmunes y genera gráficas clínicas, científicas y comparativas en formato publicación.

---

## 🗂️ Estructura del Proyecto

LUPUS/
│
├── constants.py 📌 Parámetros globales de simulación
├── data_logger.py 🗃️ Registro estructurado de resultados (opcional)
├── exosome_module.py 🧫 Simulación de IL-10 y M1/M2 por exosomas
├── helpers.py 🛠️ Funciones auxiliares
├── ifna_blockade_module.py 🧪 Bloqueo de IFN-α y sus efectos
├── main_simulation.py ▶️ Script principal de ejecución
├── model_config.yaml ⚙️ Configuración (formato YAML)
├── patient_profile.py 👤 Perfil base del paciente simulado
├── plot_article_multipanel.py 📊 Gráfica científica multipanel 2x2 (formato artículo)
├── plot_generator.py 📈 Generación de gráficas individuales y combinadas
├── plot_therapy_suspension.py 🔄 Comparación entre suspensión abrupta y escalonada
├── sensitivity_analysis.py 📉 Análisis de sensibilidad (opcional)
├── sirna_module.py 🧬 Simulación de siRNA sobre BAFF, IL-10, IFN-α
├── ui_launcher.py 🖥️ Lanzador de interfaz gráfica (opcional)
├── vaccine_module.py 💉 Simulación de vacuna tolerogénica
└── results/ 📂 Resultados generados automáticamente
├── simulation_output.csv 📄 Datos simulados en tabla
├── vaccine_response.png 💉 Gráfica: IL-10 en vacuna tolerogénica
├── sirna_response.png 🧬 Gráfica: BAFF con siRNA
├── ifna_blockade_response.png 🧪 Gráfica: IFN-α con anticuerpo
├── exosomes_response.png 🧫 Gráfica: IL-10 y M1/M2 con exosomas
├── combined_response.png 📈 Gráfica combinada de todas las variables
├── suspension_terapia.png 🔄 Comparación suspensión abrupta vs escalonada
└── immune_response_multipanel.png 📰 Gráfica tipo artículo científico (2x2)

---

## ⚙️ Requisitos

- Python 3.8 o superior
- Bibliotecas:

```bash
pip install numpy pandas matplotlib
🚀 Ejecución
Para ejecutar todo el sistema y generar resultados:


python main_simulation.py
Los archivos se guardarán automáticamente en la carpeta results/.
