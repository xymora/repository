# IA para detección y gradación de hígado graso en ecografía

> Instrucciones paso a paso para personal de salud: **[GUIA_DE_USO.md](GUIA_DE_USO.md)**.

Código del artículo *"Detección y gradación automatizada de la esteatosis hepática en ecografía modo B mediante aprendizaje profundo con referencia histológica"* (número especial de IA en Salud, Gaceta Médica de México).

El modelo clasifica un estudio ecográfico en:

| Grado | % de hepatocitos con grasa (biopsia, NASH-CRN) | Resultado que muestra el programa |
|---|---|---|
| S0 | < 5 % | Sin esteatosis (hígado normal) |
| S1 | 5–33 % | Hígado graso grado 1, leve |
| S2 | 34–66 % | Hígado graso grado 2, moderado |
| S3 | > 66 % | Hígado graso grado 3, grave |

**El modelo ya viene entrenado** (`modelos/modelo_higado_graso.pt`). Para diagnosticar basta con instalar una vez (`Instalar.bat`), abrir el programa (`Iniciar_IA_Higado_Graso.bat`) y cargar las imágenes del paciente; no hay que entrenar antes.

## Estructura de la carpeta

```
higado_graso_ia/
├── Instalar.bat                  instala Python y las librerías desde internet (una sola vez)
├── Iniciar_IA_Higado_Graso.bat   doble clic para abrir el programa
├── Crear_acceso_directo.bat      crea el ícono «IA Higado Graso» en el escritorio
├── requirements.txt              librerías que instala Instalar.bat (versiones exactas probadas)
├── LEEME.md                      este archivo
├── GUIA_DE_USO.md                guía para personal de salud
├── Higado_graso_IA.docx          artículo científico (manuscrito)
├── Higado_graso_IA_divulgacion.docx  artículo de divulgación
├── programa/                     código principal
│   ├── IA_Higado_Graso.py        programa con ventanas: diagnóstico y entrenamiento
│   ├── comun.py                  lectura de imágenes/DICOM, máscara, red neuronal, Grad-CAM
│   ├── inferencia.py             diagnóstico de un paciente a partir de una o varias imágenes
│   ├── entrenar.py               entrenamiento y validación cruzada
│   ├── metricas.py               AUC, sensibilidad, kappa, bootstrap…
│   └── figuras.py                figuras de resultados (3, 4, 5 y S1)
├── modelos/                      modelo entrenado (.pt) y su configuración (.json)
├── datos/
│   ├── imagenes/S0, S1, S2, S3/  550 ecografías PNG separadas por grado
│   ├── metadatos.csv             una fila por imagen (incluye el % de grasa por biopsia)
│   ├── pacientes.csv             una fila por paciente
│   ├── LEEME.txt                 cita y licencia del conjunto de datos
│   └── crudo/                    archivo .mat original de Zenodo
├── resultados/                   métricas, predicciones, registro del entrenamiento y figuras
└── extras/                       herramientas opcionales (no se necesitan para diagnosticar ni entrenar)
    ├── preparar_datos.py         descarga los datos de Zenodo y los exporta a datos/
    ├── predecir.py               diagnóstico por línea de comandos
    ├── app.py                    versión web del diagnóstico (Gradio)
    ├── figura_metodologia.py     figura 1 del artículo (diagrama del método)
    ├── analisis_no_supervisado.py  análisis de comparación sin etiquetas (figura S2)
    └── Entrenar_en_Colab.ipynb   cuaderno para entrenar en Google Colab
```

Al ejecutar `Instalar.bat` se crea además la carpeta `venv/`, con Python y las librerías del proyecto.

| Para… | Se necesita |
|---|---|
| Instalar | `Instalar.bat`, `requirements.txt` y conexión a internet |
| Diagnosticar | `Iniciar_IA_Higado_Graso.bat`, `programa/IA_Higado_Graso.py`, `programa/comun.py`, `programa/inferencia.py` y `modelos/` |
| Reentrenar | Lo anterior más `programa/entrenar.py`, `programa/metricas.py`, `programa/figuras.py` y `datos/` |

## Imágenes incluidas

La carpeta `datos/imagenes/` trae las **550 ecografías reales** (PNG, 434 × 636 px) del conjunto público de Byra et al., separadas por grado según la biopsia:

| Carpeta | Pacientes | Imágenes | Esteatosis |
|---|---|---|---|
| `S0/` | 17 | 170 | < 5 % (normal) |
| `S1/` | 20 | 200 | 5–33 % |
| `S2/` | 8 | 80 | 34–66 % |
| `S3/` | 10 | 100 | > 66 % |

Nombre de archivo: `P07_c03.png` = paciente 7, cuadro 3. Antes de entrar al modelo, cada imagen pasa por una máscara automática que borra el ECG, la frecuencia cardiaca, la hora y las escalas (`enmascarar_abanico` en `programa/comun.py`), para que la IA aprenda del hígado y no de esas marcas.

## Instalación

Requisitos: Windows 10 u 11 de 64 bits y **conexión a internet** durante la instalación. No se necesitan permisos de administrador.

1. Guarde la carpeta en cualquier ubicación: Descargas, Documentos, Escritorio, OneDrive o una memoria USB. Las rutas con espacios, acentos, «ñ» o paréntesis funcionan. El único límite es la longitud: la ruta de la carpeta no debe pasar de 115 caracteres, porque la instalación crea archivos con rutas relativas de hasta 140 caracteres y Windows limita las rutas completas a 260. El instalador lo comprueba y avisa.
2. Doble clic en **`Instalar.bat`**. El instalador:
   1. Busca Python 3.10, 3.11 o 3.12. Si no lo encuentra, instala Python 3.11 para el usuario actual con `winget` o, si no está disponible, descargando el instalador oficial de python.org. Antes de ejecutarlo verifica la firma digital de Python Software Foundation.
   2. Crea el entorno virtual `venv\` dentro de la carpeta del proyecto.
   3. Instala PyTorch 2.5.1: la versión con CUDA (≈ 2.5 GB) si detecta una tarjeta NVIDIA, o la versión para procesador (≈ 300 MB) si no la hay. Después instala el resto de `requirements.txt`.
   4. Comprueba que todas las librerías carguen y crea el acceso directo «IA Higado Graso» en el escritorio.

   Con `Instalar.bat cpu` (desde una terminal) se fuerza la versión para procesador aunque haya tarjeta NVIDIA. Basta para diagnosticar y ahorra unos 2 GB.

Instalación manual equivalente:

```bat
python -m venv venv
venv\Scripts\activate
pip install torch==2.5.1 torchvision==0.20.1 --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements.txt
```

Para tarjeta NVIDIA, cambie `whl/cpu` por `whl/cu121`. `requirements.txt` incluye también `gradio`, que solo usa la versión web (`extras\app.py`).

Si la computadora no tiene internet, Python y las librerías deben instalarse por otro medio; el proyecto no incluye una versión sin conexión.

Ningún archivo usa rutas fijas: los `.bat` trabajan desde su propia carpeta y los scripts de Python calculan todas las rutas (`datos/`, `modelos/`, `resultados/`, `programa/`) a partir de su ubicación. Por eso la carpeta ya instalada se puede **mover dentro de la misma computadora** sin reinstalar; solo hay que ejecutar `Crear_acceso_directo.bat` para que el ícono apunte a la nueva ubicación. Para llevar el proyecto a **otra computadora**, cópielo sin la carpeta `venv`, que depende del Python de la computadora donde se creó, y ejecute `Instalar.bat` en la nueva.

`Iniciar_IA_Higado_Graso.bat` muestra unos segundos un aviso sobre el entrenamiento (150 épocas en total, véase «Reentrenar») y abre el programa con el Python de `venv\` o, si no existe, con el de `%USERPROFILE%\.venvs\higado_graso_ia`. Si no encuentra ninguno, pide ejecutar `Instalar.bat`.

## Uso

### Programa con ventanas (recomendado)

Doble clic en `Iniciar_IA_Higado_Graso.bat`, o bien `python programa\IA_Higado_Graso.py`. La pestaña **Diagnóstico** analiza una o varias imágenes de un paciente (PNG, JPG, BMP, TIFF o DICOM, incluidos cine-loops) y guarda un reporte HTML imprimible. La pestaña **Entrenar modelo** reentrena la IA. Detalles en [GUIA_DE_USO.md](GUIA_DE_USO.md).

### Línea de comandos

Active antes el entorno con `venv\Scripts\activate`. Todos los scripts se pueden ejecutar desde cualquier carpeta: encuentran solos `datos/`, `modelos/` y `resultados/`.

```bat
python programa\entrenar.py                     :: validación cruzada + modelo final (configuración del artículo)
python programa\entrenar.py --rapido            :: prueba de humo, 2 épocas

python extras\preparar_datos.py                 :: descarga los datos (52 MB) y exporta los PNG por grado
python extras\preparar_datos.py --mat archivo.mat   :: usa un .mat descargado a mano
python extras\predecir.py estudio\*.png --mapas mapas\   :: diagnóstico de una serie de imágenes
python extras\predecir.py carpeta_del_paciente  :: diagnóstico de todas las imágenes de una carpeta
python extras\app.py                            :: versión web en http://127.0.0.1:7860
python extras\figura_metodologia.py             :: figura 1
python extras\analisis_no_supervisado.py        :: análisis no supervisado y figura S2
```

Si la descarga automática falla, baje a mano `dataset_liver_bmodes_steatosis_assessment_IJCARS.mat` desde <https://doi.org/10.5281/zenodo.1009146>.

### Google Colab (sin tarjeta gráfica propia)

1. Comprima la carpeta del proyecto en un ZIP.
2. En <https://colab.research.google.com>: *Archivo → Subir cuaderno* → `extras/Entrenar_en_Colab.ipynb`.
3. *Entorno de ejecución → Cambiar tipo → GPU T4* y ejecute las celdas en orden; el cuaderno pide subir el ZIP.
4. Al final se descarga `resultados_y_modelo.zip` con las métricas, las figuras y el modelo entrenado.

## Qué genera cada script

| Script | Salida |
|---|---|
| `programa/entrenar.py` | `modelos/modelo_higado_graso.pt` y `.json`; en `resultados/`: `metricas.json`, `tabla_resultados.csv`, `resumen_resultados.md`, `predicciones_por_imagen.csv`, `predicciones_por_paciente.csv`; figuras 3, 4, 5 y S1 |
| `extras/preparar_datos.py` | `datos/imagenes/S0..S3/*.png`, `datos/metadatos.csv`, `datos/pacientes.csv`, `datos/LEEME.txt`, figura 2 (con `--zip archivo.zip` también empaqueta las imágenes) |
| `extras/figura_metodologia.py` | `resultados/figuras/fig1_flujo_metodologico.png` |
| `extras/analisis_no_supervisado.py` | `resultados/no_supervisado.json`, `resultados/figuras/figS2_no_supervisado.png` |

El registro completo del entrenamiento incluido está en `resultados/registro_entrenamiento.txt`.

## Resultados del modelo incluido

Validación cruzada de 5 particiones agrupada por paciente (55 pacientes; ningún paciente aparece a la vez en entrenamiento y prueba). Entrenamiento en GPU NVIDIA RTX 2060: 86 min.

| Métrica (por paciente) | Valor (IC 95 %) |
|---|---|
| AUC hígado graso (S1-S3 vs. S0) | 0.907 (0.818-0.975) |
| Sensibilidad / especificidad | 89.5 % / 70.6 % |
| Exactitud del grado S0-S3 | 52.7 % (89.1 % con ± 1 grado) |
| Kappa ponderada cuadrática | 0.65 (0.49-0.78) |
| Rho de Spearman vs. % de biopsia | 0.78 (0.64-0.86) |

El manuscrito (`Higado_graso_IA.docx`) ya contiene estas cifras y las figuras. Si se reentrena el modelo, los nuevos valores quedan en `resultados/metricas.json` y deben actualizarse a mano en el manuscrito.

## Reentrenar: 150 épocas en total

El entrenamiento correcto completo son **150 épocas en total**, repartidas en 6 modelos de 25 épocas:

| Modelo | Épocas |
|---|---|
| 5 modelos de validación cruzada (estiman el desempeño con pacientes no vistos) | 5 × 25 = 125 |
| 1 modelo final con los 55 pacientes (el que usa el diagnóstico) | 25 |
| **Total** | **150** |

El parámetro `--epocas` de `programa/entrenar.py` y la casilla «Épocas por modelo» del programa indican las épocas **de cada modelo** y deben quedar en 25. El programa muestra el total junto a la casilla y pide confirmación si se usa otro valor. Con más épocas no mejora: las curvas de aprendizaje (`resultados/figuras/figS1_curvas_aprendizaje.png`) muestran sobreajuste a partir de la época 3-5, y 150 por modelo serían 900 épocas en total.

## Añadir imágenes propias (validación externa o reentrenamiento)

Organice las imágenes en `imagenes/S0`, `S1`, `S2` y `S3` según la biopsia (o PDFF por resonancia), con nombres `PACIENTE_cuadro.png`, y entrene desde la pestaña **Entrenar modelo** o con `python programa\entrenar.py --datos carpeta`. Si falta `metadatos.csv`, el programa con ventanas lo crea (columnas `ruta, paciente, cuadro, esteatosis_pct, grado, higado_graso`); sin el porcentaje real de grasa usa el valor medio de cada grado.

## Advertencias

* **Herramienta de investigación, no es un dispositivo médico.** Solo tiene validación interna, con 55 pacientes con obesidad grave, un solo equipo (GE Vivid E9) y un solo centro (Polonia).
* El paciente es la unidad de análisis: las imágenes de un mismo paciente nunca se reparten entre entrenamiento y prueba.
* Los hiperparámetros se fijaron de antemano. No los ajuste mirando los resultados de prueba; si los cambia, declárelo en el artículo.

## Citar los datos

Byra M, et al. Transfer learning with deep convolutional neural network for liver steatosis assessment in ultrasound images. *Int J Comput Assist Radiol Surg.* 2018;13:1895-903. Datos: doi:10.5281/zenodo.1009146 (CC BY 4.0).
