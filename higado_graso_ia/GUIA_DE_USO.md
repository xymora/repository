# Guía de uso: IA para detección y gradación de hígado graso en ecografía

Esta guía explica cómo **usar la IA para diagnosticar** a partir de una imagen o de una serie de imágenes de un paciente y, si se desea, cómo **volver a entrenar el modelo**. No se necesitan conocimientos de programación para usar el programa con ventanas.

> **Aviso.** Es una herramienta de investigación y no sustituye el juicio clínico. Se entrenó con 55 adultos con obesidad grave, con imágenes de un solo equipo (GE Vivid E9, sonda sectorial de 2.5 MHz) y con la biopsia como referencia. No se ha validado en otros equipos ni en otras poblaciones.

**El modelo ya viene entrenado.** Para hacer un diagnóstico no hace falta entrenar nada: instale una vez (sección 1), abra el programa (sección 2) y cargue las imágenes (sección 3).

---

## 1. Instalación (una sola vez)

Se necesita una computadora con **Windows 10 u 11** y **conexión a internet** durante la instalación. No hace falta tener Python instalado ni permisos de administrador.

1. Guarde la carpeta del proyecto **donde prefiera**: Descargas, Documentos, Escritorio, una carpeta de OneDrive o una memoria USB. Funciona aunque la ruta tenga espacios, acentos, «ñ» o paréntesis (por ejemplo `C:\Users\José Pérez\Mis Documentos (2026)\IA hígado`). La única condición es que la ruta de la carpeta no pase de unos 115 caracteres; si la pasa, el instalador lo avisa y basta con moverla a un lugar menos profundo.
2. Haga **doble clic en `Instalar.bat`**. Se abre una ventana negra que muestra el avance en cuatro pasos:
   1. **Python**: si la computadora no lo tiene, lo descarga del sitio oficial (python.org) y lo instala solo.
   2. **Entorno**: crea la carpeta `venv` dentro del proyecto, donde quedan Python y las librerías.
   3. **Librerías**: descarga e instala PyTorch y las demás librerías. Si la computadora tiene tarjeta gráfica NVIDIA, instala la versión que la aprovecha (≈ 2.5 GB); si no, la versión para procesador (≈ 300 MB).
   4. **Comprobación**: verifica que todo funcione y crea en el escritorio el ícono **«IA Higado Graso»**.
3. Al ver el mensaje «Instalación terminada», pulse cualquier tecla para cerrar la ventana.

Según la velocidad de internet, la instalación tarda de 5 a 20 minutos. Solo se hace una vez; después el programa funciona sin conexión.

Para diagnosticar no se necesita tarjeta gráfica: el análisis de un paciente tarda unos segundos en cualquier computadora. Si la computadora tiene tarjeta NVIDIA pero solo se va a diagnosticar, se puede ahorrar espacio ejecutando `Instalar.bat cpu` desde una terminal.

**Sin internet:** el programa no incluye una versión sin conexión. En ese caso, Python 3.10–3.12 y las librerías de `requirements.txt` deben instalarse por otro medio (por ejemplo, con ayuda del área de sistemas del hospital).

---

## 2. Abrir el programa

Haga **doble clic en el ícono «IA Higado Graso» del escritorio** o en `Iniciar_IA_Higado_Graso.bat`, dentro de la carpeta del proyecto. Primero aparece durante unos segundos una ventana negra con un aviso sobre el entrenamiento (sección 4) y después se abre el programa. Si el ícono se borró, `Crear_acceso_directo.bat` lo vuelve a crear.

**Mover la carpeta después de instalar:** si la carpeta se mueve a otro lugar de la misma computadora (por ejemplo, de Descargas a Documentos), el programa sigue funcionando sin reinstalar. Solo el ícono del escritorio apunta todavía al lugar anterior: ejecute `Crear_acceso_directo.bat` desde la nueva ubicación para actualizarlo.

El programa tiene tres pestañas:

| Pestaña | Para qué sirve |
|---|---|
| **1. Diagnóstico** | Cargar las imágenes de un paciente y obtener el grado de esteatosis |
| **2. Entrenar modelo** | Volver a entrenar la IA con las imágenes incluidas o con imágenes propias (opcional) |
| **Ayuda** | Resumen de estas instrucciones |

---

## 3. Hacer un diagnóstico

1. Abra la pestaña **1. Diagnóstico**.
2. Cargue las imágenes de **un solo paciente** de una de estas dos formas:
   - **Elegir imágenes…**: seleccione una imagen, o varias manteniendo `Ctrl` o `Shift`.
   - **Elegir carpeta del estudio…**: toma todas las imágenes de una carpeta.

   Formatos aceptados: PNG, JPG, BMP, TIFF y **DICOM**, incluidos los cine-loops multicuadro. Si un estudio tiene más de 60 cuadros, se toman 60 repartidos de manera uniforme. **Limpiar** borra la selección para empezar con otro paciente.
3. Pulse **ANALIZAR**.
4. Interprete el resultado:

| Resultado | Significado (biopsia, sistema NASH-CRN) |
|---|---|
| **S0**: sin esteatosis | < 5 % de hepatocitos con grasa |
| **S1**: hígado graso leve | 5-33 % |
| **S2**: hígado graso moderado | 34-66 % |
| **S3**: hígado graso grave | > 66 % |

   - **Probabilidad de hígado graso**: suma de las probabilidades de S1, S2 y S3. Si es ≥ 50 %, el estudio se clasifica como hígado graso y se asigna el grado más probable entre S1 y S3.
   - **Barras S0-S3**: probabilidad promedio de cada grado en todas las imágenes.
   - **Acuerdo entre imágenes**: porcentaje de imágenes que coinciden con el diagnóstico global. Si es **menor de 70 %**, revise la calidad de las imágenes o agregue más cortes del hígado.
   - **Mapas de calor (Grad-CAM)**: las zonas rojas son las que más pesaron en la decisión. Deben caer sobre el parénquima hepático y no sobre textos o bordes. Debajo de cada imagen aparece el grado que le asignó la IA.
5. **Guardar reporte (HTML para imprimir)** crea una página con el resultado, la tabla por imagen y los mapas de calor, con espacios para el nombre del paciente y del médico. Se abre en el navegador y desde ahí se imprime o se guarda como PDF.

**Recomendaciones para las imágenes:** use modo B (no Doppler ni elastografía), con un corte que incluya el parénquima del lóbulo derecho y, de preferencia, la corteza del riñón derecho. Con **5 a 10 cortes por paciente** el resultado es más estable que con una sola imagen.

**Qué tan confiable es:** en la validación con pacientes que el modelo no había visto, detectó la presencia de hígado graso con un AUC de 0.91 (sensibilidad 89.5 %, especificidad 70.6 %). Acertó el grado exacto en el 53 % de los pacientes y el grado ± 1 en el 89 %. La detección (si hay o no hígado graso) es más confiable que la asignación del grado exacto, sobre todo entre S2 y S3.

---

## 4. Volver a entrenar el modelo (opcional)

Solo es necesario si se quiere reproducir el experimento del artículo o entrenar con imágenes propias. **El entrenamiento reemplaza el modelo y los resultados actuales**; si quiere conservarlos, copie antes las carpetas `modelos\` y `resultados\`.

### 4.1 Con los datos incluidos

La carpeta `datos\imagenes\` ya contiene las 550 ecografías (55 pacientes) organizadas por grado.

1. Abra la pestaña **2. Entrenar modelo**.
2. Deje **«Épocas por modelo» en 25**, el valor que viene por defecto y la configuración del artículo. Marque **Prueba rápida** si solo quiere comprobar que todo funciona (2 épocas por modelo, unos 8 minutos con tarjeta gráfica).
3. Pulse **INICIAR ENTRENAMIENTO** y confirme. El recuadro negro muestra el avance de cada partición y cada época; **Detener** lo interrumpe.
4. Duración: unos **90 minutos con tarjeta gráfica NVIDIA** (86 min medidos en una RTX 2060) y varias horas sin ella.

**Las 150 épocas.** El entrenamiento correcto completo son **150 épocas en total**, pero no se escriben 150 en la casilla: el programa entrena 6 modelos y la casilla indica las épocas de cada uno.

| Modelo | Épocas |
|---|---|
| 5 modelos de validación cruzada (miden el desempeño con pacientes no vistos) | 5 × 25 = 125 |
| 1 modelo final con todos los pacientes (el que usa el diagnóstico) | 25 |
| **Total** | **150** |

Junto a la casilla, el programa muestra el total calculado. Si se escribe otro número, lo indica en naranja y pide confirmación. Más épocas no mejoran el modelo: con 55 pacientes empieza a memorizar los datos de entrenamiento (sobreajuste) hacia la época 5. Con 150 en la casilla se harían 900 épocas en total, unas 9 horas con tarjeta gráfica, y el resultado sería peor.
5. Al terminar se generan:
   - `modelos\modelo_higado_graso.pt`: el modelo que usa la pestaña de diagnóstico.
   - `resultados\metricas.json`, `tabla_resultados.csv` y `resumen_resultados.md`: las métricas.
   - `resultados\predicciones_por_imagen.csv` y `predicciones_por_paciente.csv`.
   - `resultados\figuras\`: curvas ROC, matriz de confusión, mapas Grad-CAM y curvas de aprendizaje.

   El botón **Abrir carpeta de resultados** abre esa carpeta.

### 4.2 Con imágenes propias

Organice las imágenes según el grado de la biopsia y nombre cada archivo `PACIENTE_cuadro`:

```
mis_datos\
└── imagenes\
    ├── S0\   P01_c01.png  P01_c02.png  P02_c01.png …
    ├── S1\   P10_c01.png …
    ├── S2\   …
    └── S3\   …
```

En la pestaña de entrenamiento, pulse **Cambiar…** junto a «Carpeta de datos» y elija `mis_datos`. Si no existe un archivo `metadatos.csv`, el programa lo crea solo. Como en ese caso no conoce el porcentaje exacto de grasa, usa el valor medio de cada grado, y la correlación de Spearman resulta aproximada. Si conoce el porcentaje por biopsia, cree `metadatos.csv` con las columnas `ruta, paciente, cuadro, esteatosis_pct, grado, higado_graso`, igual que `datos\metadatos.csv`.

**Importante:** todas las imágenes de un mismo paciente deben llevar el mismo prefijo (`P07_…`). La validación usa ese prefijo para que nunca haya imágenes del mismo paciente a la vez en entrenamiento y en prueba.

### 4.3 Qué hace el entrenamiento

- **Tipo de aprendizaje: supervisado.** Cada imagen tiene una etiqueta conocida (el grado por biopsia) y la red aprende a reproducirla. Un análisis no supervisado de comparación (`extras\analisis_no_supervisado.py`) mostró que, sin etiquetas, los grupos que forma la red casi no coinciden con la biopsia.
- **Red:** EfficientNet-B0 preentrenada en ImageNet (transferencia de aprendizaje), con 4 millones de parámetros y una capa final de 4 salidas (S0-S3).
- **Validación cruzada de 5 particiones agrupada por paciente:** se entrenan 5 modelos y cada uno se evalúa con pacientes que nunca vio. Después se entrena un **modelo final** con todos los pacientes, que es el que usa el programa.
- **Preprocesamiento:** una máscara automática borra el ECG, la hora y los textos del equipo para que la IA aprenda del hígado y no de esas marcas.

---

## 5. Organización de la carpeta

| Ubicación | Contenido |
|---|---|
| Carpeta principal | Lo que se usa con doble clic: `Instalar.bat`, `Iniciar_IA_Higado_Graso.bat` y `Crear_acceso_directo.bat`, además de esta guía, `LEEME.md` y `requirements.txt` (la lista de librerías que descarga el instalador; no lo borre ni lo mueva) |
| `programa\` | El código del programa: `IA_Higado_Graso.py` (las ventanas) y los archivos que necesita para diagnosticar y entrenar (`comun.py`, `inferencia.py`, `entrenar.py`, `metricas.py`, `figuras.py`). No lo modifique ni lo borre |
| `venv\` | Python y las librerías; la crea `Instalar.bat`. Si se borra, vuelva a ejecutar el instalador |
| `modelos\` | El modelo entrenado. **No lo borre**: sin él no se puede diagnosticar |
| `datos\` | Las 550 imágenes de entrenamiento y sus tablas |
| `resultados\` | Métricas, predicciones, figuras y registro del entrenamiento |
| `extras\` | Herramientas opcionales para usuarios avanzados (sección 6); el programa funciona sin ellas, salvo el botón «Descargar datos públicos», que usa `extras\preparar_datos.py` |

Para usar el programa en otra computadora, copie la carpeta completa **sin la carpeta `venv`**, que solo funciona en la computadora donde se creó, y ejecute `Instalar.bat` en la nueva (sección 1).

---

## 6. Opciones para usuarios avanzados (línea de comandos)

Active primero el entorno (`venv\Scripts\activate`). Los scripts funcionan desde cualquier carpeta.

```bat
python programa\entrenar.py                         :: entrenamiento completo (artículo)
python programa\entrenar.py --rapido                :: prueba de 2 épocas
python programa\entrenar.py --epocas 40 --lote 8 --datos mis_datos

python extras\predecir.py estudio\*.png             :: diagnóstico de una serie de imágenes
python extras\predecir.py carpeta_del_paciente      :: todas las imágenes de una carpeta
python extras\predecir.py estudio.dcm --mapas salida\   :: DICOM + guarda los mapas de calor
python extras\predecir.py imagen.png --json         :: resultado en formato JSON

python extras\app.py                                :: versión web en http://127.0.0.1:7860
python extras\app.py --compartir                    :: enlace público temporal (no lo use con datos reales de pacientes)

python extras\preparar_datos.py                     :: descarga los datos de Zenodo y exporta las imágenes por grado
python extras\figura_metodologia.py                 :: figura 1 del artículo (diagrama metodológico)
python extras\analisis_no_supervisado.py            :: análisis no supervisado de comparación (figura S2)
```

Para entrenar en Google Colab sin tarjeta gráfica propia, use `extras\Entrenar_en_Colab.ipynb` (instrucciones en `LEEME.md`).

---

## 7. Problemas frecuentes

| Problema | Solución |
|---|---|
| «No se encontró el modelo entrenado» | Falta el archivo `modelos\modelo_higado_graso.pt`: cópielo de nuevo desde la carpeta original, elija otro `.pt` con **Cambiar…** o entrene (sección 4) |
| «No se encontró Python con las librerías necesarias» al abrir el programa | Falta la instalación: ejecute `Instalar.bat` |
| El instalador dice que la ruta es demasiado larga | Mueva la carpeta a un lugar menos profundo (por ejemplo directamente en Documentos o en `C:\IA_Higado_Graso`) y vuelva a ejecutarlo |
| El ícono del escritorio dejó de funcionar | La carpeta se movió: ejecute `Crear_acceso_directo.bat` desde la nueva ubicación |
| El instalador no puede descargar | Revise la conexión a internet; en redes de hospital puede haber un proxy o firewall que bloquee python.org o download.pytorch.org |
| La instalación se interrumpió a medias | Vuelva a ejecutar `Instalar.bat`: reutiliza lo ya descargado. Si sigue fallando, borre la carpeta `venv` e inténtelo de nuevo |
| `No module named torch` | Ejecute de nuevo `Instalar.bat` |
| El entrenamiento es muy lento | Sin tarjeta NVIDIA tarda varias horas; use la *Prueba rápida* o Google Colab (`extras\Entrenar_en_Colab.ipynb`) |
| Una imagen DICOM no se lee | Verifique que sea modo B y que el archivo no esté comprimido con un códec no soportado; expórtela a PNG |
| Acuerdo entre imágenes bajo | Las imágenes son de baja calidad o de otra región; repita con cortes del lóbulo derecho |
