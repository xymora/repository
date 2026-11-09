# OrtoKinect

Evaluación en **traumatología, ortopedia y rehabilitación** con el Kinect de Xbox 360
(modelo 1414). Detecta el esqueleto con **MediaPipe**, lo corrige con la **profundidad**
real del Kinect y mide rangos de movimiento, postura, equilibrio, fuerza funcional y
marcha. Guarda expedientes por paciente, grafica su evolución y genera **reportes PDF**.

Herramienta de apoyo para el terapeuta; no sustituye la valoración clínica.

## Ejecutar

Doble clic en **`ejecutar.bat`**, o sin Kinect en **`ejecutar_simulado.bat`**:

```bash
pip install -r requirements.txt
python app.py              # con el Kinect (si falla, usa el paciente simulado)
python app.py --simulado   # paciente simulado que realiza cada prueba + paciente de demostración
python app.py --camara     # cámara web normal (sin profundidad)
```

Requiere `mediapipe==0.10.11`; `vision.py` incluye un parche para la incompatibilidad con
versiones nuevas de protobuf.

## Teclas

`Espacio` iniciar / terminar la prueba · `Esc` cancelar · `↑`/`↓` inclinar el Kinect.

## Pruebas

**Rango de movimiento** (cuenta repeticiones, ROM máximo, % del normal y del funcional, y
detecta compensaciones):

| Prueba | Normal | Compensaciones que vigila |
|---|---|---|
| Flexión de hombro | 180° | codo doblado, tronco hacia atrás |
| Abducción de hombro | 180° | codo doblado, inclinación lateral |
| Flexión de codo | 150° | brazo despegado |
| Flexión de cadera | 120° | tronco atrás o de lado |
| Abducción de cadera | 45° | inclinación, pierna al frente |
| Flexión de rodilla (de pie) | 135° | muslo que se mueve |
| Sentadilla | 135° | valgo de rodilla, tronco adelante |
| Inclinación lateral del tronco | 35° | flexión del tronco |

**Otras:** evaluación postural · medidas corporales (antropometría) · equilibrio en una
pierna (hasta 30 s, con normas por edad) · sentarse y pararse en 30 s (normas por edad y
sexo) · análisis de marcha (caminando de 4 m a 1.5 m del Kinect) · goniómetro libre.

Cada prueba trae sus instrucciones en pantalla, se puede hacer por lado (izquierdo,
derecho o ambos) y registra el dolor EVA.

## Pacientes y seguimiento

- **Expediente:** datos generales, estatura y peso (IMC), diagnóstico, tipo de caso
  (postquirúrgico, lesión aguda, dolor crónico, neurológico, adulto mayor, deportivo,
  preventivo), lado afectado, fecha de cirugía o lesión, objetivos y notas.
- **Rutina:** cada paciente puede tener un plan de pruebas que se recorre con el botón
  *siguiente*.
- **Progreso:** tabla de registros, series en el tiempo con el dolor EVA y comparación
  de lados como % del rango normal.
- **Exportar** a CSV y **reporte PDF** (reportlab + matplotlib).
- Todo se guarda en `datos\pacientes\<paciente>\` (`paciente.json`, registros, `reportes\`,
  `exportes\`); lo eliminado pasa a `datos\papelera\`.

## Cómo funciona

- **Visión** (`vision.py`): MediaPipe Pose en un hilo aparte; cada punto se lleva a 3D con
  la profundidad alineada a la cámara de color, se suaviza con filtro One-Euro y se
  calcula el plano del suelo y la cima de la cabeza.
- **Biomecánica** (`biomecanica.py`): ángulos articulares en los planos anatómicos.
- **Imagen:** automático entre color e infrarrojo según la luz, como en Kinect Distancia.

## Archivos

`app.py` (interfaz: Evaluar, Pacientes, Progreso) · `pruebas.py` (catálogo y lógica de
cada prueba) · `biomecanica.py` · `vision.py` · `fuentes.py` (Kinect, cámara web y
paciente simulado) · `kinect.py` (driver USB) · `datos.py` (almacén de pacientes) ·
`reporte.py` (PDF) · `demo.py` (paciente de demostración).
