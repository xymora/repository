# Kinect Distancia

**Semáforo de proximidad** con el Kinect de Xbox 360 (modelo 1414): detecta personas u
objetos que se acercan, mide a qué distancia están y a qué velocidad vienen, y avisa en
verde / amarillo / rojo con pitido tipo sensor de reversa y el LED del propio Kinect.

Funciona de día y a oscuras: muestra **dos pantallas** (luz ambiente e infrarrojo de
profundidad) y cambia sola al infrarrojo cuando se apaga la luz. Usa un driver USB propio
(`kinect.py`), sin SDK de Microsoft ni libfreenect.

## Ejecutar

Doble clic en **`ejecutar.bat`**, o sin Kinect en **`ejecutar_simulado.bat`**:

```bash
pip install -r requirements.txt
python app.py              # con el Kinect conectado
python app.py --simulado   # sin Kinect: una figura se acerca y se aleja y la luz se apaga cada rato
```

Si el Kinect no responde, la app arranca en modo simulado y lo indica en la ventana.
Requisitos: Kinect conectado con su fuente de 12 V y el dispositivo de cámara
(USB `045E:02AE`) accesible por libusb.

## Uso

- **Pantalla 1 · Imagen:** `Automático` (pasa a infrarrojo cuando está oscuro y cada 10 s
  vuelve a comprobar si ya hay luz), `Luz ambiente` o `Infrarrojo`.
- **Pantalla 2 · Profundidad:** el Kinect proyecta su propia luz infrarroja, así que mide
  igual con luz o sin ella.
- **Zona vigilada:** arrastra con el ratón sobre cualquiera de las pantallas; clic derecho
  la borra.
- **Umbrales:** deslizadores de *Amarillo a menos de* (2.0 m), *Rojo a menos de* (1.0 m) y
  *Vigilar hasta* (4.0 m).
- **Opciones:** pitido, LED del Kinect con el color de la alerta, y *sólo lo nuevo o lo
  que se mueve* (aprende el fondo e ignora muebles). Botones *Volver a aprender el fondo*,
  *Borrar zona* y *Reiniciar IDs*.
- Abajo: **radar** visto desde arriba, **lista** de objetos con ID, distancia y velocidad, y
  **gráfica** de los últimos 20 s (clic para cambiar entre distancia y velocidad).

## Teclas

`↑`/`↓` inclinar el Kinect · `S` sonido · `Esc` salir.

## Cómo funciona

- **Profundidad a 3D** (`detector.py`): la imagen se reduce a 320×240 y cada píxel se
  convierte a coordenadas en metros.
- **Piso:** se ajusta con RANSAC + SVD sobre la mitad inferior y se descarta, para que el
  suelo no cuente como obstáculo.
- **Fondo:** modelo que guarda la profundidad más lejana vista y la olvida poco a poco;
  sólo se considera lo que queda claramente delante de él.
- **Segmentación** por saltos de profundidad y **seguimiento** de cada objeto con
  asignación húngara (si está scipy), IDs confirmados tras 3 cuadros, predicción cuando
  algo queda tapado y separación de objetos que se juntan.
- **Velocidad** de acercamiento medida en ventana de 0.8 s y tiempo estimado de llegada.
- **Alerta** con histéresis (6 cm) para que el semáforo no parpadee en el límite; el
  pitido se acelera conforme el objeto se acerca.

## Archivos

`app.py` (ventana tkinter, fuentes real y simulada, sonido) · `detector.py` (piso, fondo,
segmentación, seguimiento) · `kinect.py` (driver USB: profundidad 11 bits, color, IR 10
bits, LED y motor) · `requirements.txt` · `ejecutar.bat` · `ejecutar_simulado.bat`.
