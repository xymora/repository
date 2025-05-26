# LUPUS SIM: Sistema de Simulación Computacional Cuatrimodal para LES

Este repositorio contiene el código completo de un modelo computacional *in silico* que simula la respuesta inmunológica en pacientes con lupus eritematoso sistémico (LES), bajo el efecto de una terapia cuatrimodal experimental compuesta por:

1. **Vacuna tolerogénica**
2. **siRNA anti-BAFF (BLyS)**
3. **Anticuerpo monoclonal anti-IFN-α**
4. **Exosomas derivados de células madre mesenquimales (MSCs)**

## Estructura de archivos

- `main_simulation.py`  
  Ejecuta el ciclo completo de simulación, integrando los cuatro módulos terapéuticos, carga configuración y exporta resultados.

- `vaccine_module.py`  
  Simula la acción de una vacuna tolerogénica sobre Treg, IL-10 y reducción de Th17.

- `sirna_module.py`  
  Modela el silenciamiento de BLyS/BAFF y su impacto en células B y producción de autoanticuerpos.

- `ifna_blockade_module.py`  
  Simula la neutralización de IFN-α y su efecto sobre células dendríticas plasmocitoides y el eje inflamatorio.

- `exosome_module.py`  
  Simula la reprogramación inmune inducida por exosomas MSCs (M1 → M2, IL-10↑, TNF-α↓).

- `patient_profile.py`  
  Genera perfiles clínicos personalizados: edad, IMC, sexo, evolución, actividad inmunológica inicial.

- `plot_generator.py`  
  Crea todas las gráficas científicas del sistema (e.g., evolución de citoquinas, efecto combinado, recaída).

- `sensitivity_analysis.py`  
  Permite identificar los parámetros más sensibles en el modelo y sus impactos sobre la respuesta proyectada.

- `data_logger.py`  
  Guarda resultados en archivos `.csv` para trazabilidad y análisis externo.

- `ui_launcher.py`  
  Interfaz local opcional para ejecutar simulaciones sin necesidad de usar consola.

- `constants.py`  
  Contiene constantes fisiológicas, cinéticas y estructurales utilizadas en todo el sistema.

- `helpers.py`  
  Funciones auxiliares reutilizables (clamp, decaimientos, modelos logísticos).

- `model_config.yaml`  
  Archivo editable donde se definen todos los parámetros iniciales de la simulación.

## Requisitos

- Python 3.9 o superior  
- Bibliotecas: `numpy`, `matplotlib`, `scipy`, `pandas`, `yaml`, `tkinter` (opcional)

## Ejecución básica

```bash
python main_simulation.py
