# Dron de entregas sobre una ciudad real

Simulador en Python de un dron que lleva **medicamentos** (desde una farmacia) o
**comida** (desde un restaurante) a la azotea de un cliente, a unos **3 km**, sobre
una **ciudad real**: calles, edificios, farmacias, restaurantes, hospitales con
helipuerto, cables eléctricos y antenas salen de **OpenStreetMap**, y el fondo es una
**imagen satelital** real. Las coordenadas son latitud/longitud reales, y el vuelo se
puede ver en **Google Earth (3D)** y la posición del dron en **Google Maps**.

El dron tiene **dos pilotos**: uno **clásico** (reglas programadas) y uno de
**inteligencia artificial** cuyo cerebro (una red neuronal) **aprende solo** en la
**Escuela de vuelo** con un **algoritmo genético**, como el auto y el tráiler de los
proyectos de estacionamiento: generación tras generación aprende a despegar, volar a
un punto, aterrizar con precisión, esquivar obstáculos y hacer una entrega completa.

El dron **siempre llega del punto A al punto B**: ante viento, aves, pérdida de GPS,
falla de un motor o batería baja **se adapta** (velocidad, altura, modo de vuelo,
navegación, espera en el aterrizaje) pero nunca abandona la entrega.

## Ejecutar

Doble clic en **`Iniciar_Simulador.bat`** (el simulador) o en **`Escuela_de_Vuelo.bat`**
(ver a la IA aprender). Ambos instalan Pillow e imageio-ffmpeg si faltan. Desde una terminal:

```bash
python main.py                                   # abrir la ventana
python main.py --vehiculo avion                  # avión VTOL en vez del hexacóptero
python main.py --zona "Guadalajara · Centro"     # otra ciudad de la lista
python main.py --zona "19.4326,-99.1332"         # cualquier lugar por coordenadas
python main.py --lugares                         # farmacias/restaurantes y clientes
python main.py --origen 2 --destino 4            # elegirlos por número
python main.py --sin-gui --eventos gps,motor,bateria --viento 9   # en consola
python main.py --sin-gui --puntos "25.6800,-100.3100;25.6720,-100.2950"  # ruta manual
python main.py --descargar                       # volver a descargar la zona
python main.py --piloto ia                       # volar con el cerebro aprendido
python main.py --entrenar                        # escuela de vuelo (con animación)
python main.py --entrenar --continuar            # seguir entrenando el cerebro guardado
python main.py --entrenar 300 --sin-gui          # entrenar 300 generaciones en consola
python main.py --entrenar --vehiculo avion       # entrenar el cerebro del avión
```

Requiere Python 3.8+ (tkinter viene incluido en Windows) y **Pillow**
(`python -m pip install pillow`). Necesita internet **sólo la primera vez** que se usa
cada ciudad: descarga sus datos de OpenStreetMap (unos segundos) y su imagen satelital
(uno o dos minutos) y los guarda en `datos/`. Ya vienen descargadas **Monterrey** y
**Guadalajara**.

## Escuela de vuelo (la IA aprende)

**El cerebro** es una red neuronal pequeña (27 entradas → 10 neuronas → 3 salidas,
con conexiones directas): **sus pesos son el genoma**. Diez veces por segundo recibe
lo que miden los sensores del dron y decide a qué velocidad volar hacia adelante (hacia
su objetivo), de lado y en vertical; un control de bajo nivel convierte eso en empuje.

| Lo que siente (entradas) | |
|---|---|
| Objetivo | distancia horizontal (fina, media, lejana) y diferencia de altura |
| Movimiento | velocidad hacia adelante, de lado y vertical |
| Altura | sobre lo que tiene justo abajo (suelo o azotea) |
| Orden | ¿hay que aterrizar aquí? |
| 8 sensores de distancia | en 8 direcciones, hasta 42 m: edificios y antenas reales, grúas, cables, zonas prohibidas |
| Obstáculo delante | altura del más alto respecto a la del dron |
| Ave más cercana | posición relativa |
| Viento | adelante y de lado |

**Reflejos:** como un dron real, no puede pedir más velocidad de la prudente según lo
cerca que está de su meta (ni bajar rápido cerca de la azotea). El cerebro decide
hacia dónde y cuánto de esa velocidad usar.

**El plan de estudios** (sobre la ciudad real, 2 pruebas por lección, siempre iguales
para poder comparar generaciones):

| Nivel | Lección | Aprueba si… |
|---|---|---|
| 1 | Despegue | sube de la azotea a 25 m sobre ella y se queda quieto (±2 m) |
| 2 | Volar a un punto | llega a ~350 m y se detiene ahí (±4 m) |
| 3 | Aterrizaje de precisión | baja desde 20 m con viento (y ráfagas) y se posa a ≤ 50 cm del centro, suave |
| 4 | Esquivar obstáculos | llega con una **grúa nueva que el mapa no conoce** y una **parvada** atravesadas |
| 5 | Entrega completa | despega, sigue la ruta del GPS (~600 m) y aterriza en el cliente |

Al aprobar todas las pruebas de su nivel durante 2 generaciones seguidas, pasa al
siguiente **sin dejar de practicar las anteriores** (para no olvidarlas). Choca o falla
si golpea un edificio, una antena, cables, la grúa o un ave, rebasa los 120 m, entra a
una zona prohibida, se aleja o se le acaba el tiempo.

**Calificación (aptitud):** en cada prueba suma por acercarse a la meta, por la
**cercanía promedio durante toda la prueba** (premia llegar rápido y quedarse
exactamente ahí), y al aterrizar por lo centrado y lo suave del toque; aprobar da un
bono y aprobar rápido otro. Chocar resta 40.

**Algoritmo genético:** población de 40; los 3 mejores pasan intactos; 30 % son copias
de los mejores con ajustes diminutos; el resto, hijos por torneo con cruce (neuronas
completas de uno u otro padre, o mezcla) y mutación adaptativa (si no mejora en 15
generaciones explora más); 5 % nuevos al azar; extinción si al principio no avanza.

**La ventana de la escuela** (también con el botón **🎓 Escuela de vuelo** del simulador):
vista desde arriba sobre el satélite con todos los drones de la generación (amarillo:
el líder con su estela; azul volando, rojo chocó, verde aprobó, gris sin tiempo), vista
de lado (distancia vs. altura, con los edificios y la grúa), el **plan de estudios** como
una línea de pasos (✓ aprobadas, la lección actual resaltada), indicadores de la
generación (volando, aprobaron, chocaron, sin tiempo, mejor aptitud), récord, gráfica de
aptitud con rejilla (las líneas verdes marcan cuándo subió de lección) y **lo que siente
y decide el líder** (radar de sus 8 sensores y sus 3 decisiones). **Turbo** entrena con todos los núcleos del procesador
sin animar. `Espacio` pausa · `+`/`-` velocidad · `T` turbo · `N` reiniciar · `Esc` cerrar.

**Ya vienen entrenados** los cerebros del hexacóptero y del avión (se graduaron en
~13 generaciones). Examen fuera de la escuela, en entregas reales de 1.6 a 3.8 km con
viento de hasta 9 m/s:

| Cerebro | Examen | Resultado |
|---|---|---|
| Hexacóptero | Monterrey, sin fallas | 12/12 entregas |
| Hexacóptero | Monterrey, con fallas al azar (GPS, motor, batería) | 12/12 |
| Hexacóptero | **Guadalajara** (ciudad donde nunca entrenó), con fallas | 12/12 |
| Avión VTOL | Monterrey, con fallas | 11/12 (con las 3 fallas juntas se quedó sin batería y bajó en paracaídas) |

Aterrizajes a 2–30 cm del centro de la plataforma. Para verlo aprender desde cero:
abre la escuela y pulsa **⟲ Reiniciar desde cero** (borra el cerebro guardado).

El piloto IA, a diferencia del clásico, **no garantiza** llegar: hace lo que aprendió.
El clásico sigue disponible y siempre llega.

El mejor cerebro se guarda solo en `mejor_cerebro_<vehículo>.json` y el simulador lo
usa al elegir **IA aprendida**: la ruta del GPS le da la orden (el punto al
que ir o «aterriza aquí») y el cerebro decide cómo volar. Cada generación queda en
`historial.csv`.

## La ventana

Tema oscuro con tarjetas. Arriba, el **encabezado**: la ciudad, el **estado del vuelo**
(fase actual, con un punto de color), **🎓 Escuela de vuelo**, la velocidad de
simulación (− x4 +), **Pausa**, **▶ Despegar** / **⟲ Nueva misión** y **⏺ Grabar**.

**Barra lateral (izquierda):**

- **Zona de vuelo:** Monterrey, CDMX (Roma–Condesa y Polanco), Guadalajara, Puebla,
  Querétaro, Mérida, Madrid… o **«Otra zona (coordenadas)»**, donde se escribe
  `lat, lon` o se pega un enlace de Google Maps, y el **tamaño de la zona**
  (5.2 × 3.6 km por omisión). Se prepara en segundo plano mientras la ventana sigue
  funcionando.
- **Vehículo y piloto:** *Hexacóptero* o *Avión VTOL*; *Piloto clásico* (reglas
  programadas) o *IA aprendida* (el cerebro de la escuela).
- **Misión:** **Sale de / Entrega en** (farmacias y restaurantes reales y clientes
  sugeridos), **Ruta** *Automática (GPS)* o *Con clics* (cada clic marca un punto de
  paso; clic derecho borra el último; si un tramo cruza una zona prohibida o un edificio
  que rebasa el techo legal, se corrige solo), qué elige **el clic en el mapa** (salida,
  llegada o puntos de paso), **Alturas de edificios** (los pinta sobre el satélite según
  su altura; borde rojo = rebasan los 120 m) y **Borrar puntos**.
- **Clima:** viento (velocidad con la barra y dirección; se puede cambiar en pleno
  vuelo), **ráfagas** y **aves**.
- **Fallas al azar en el vuelo:** GPS, motor y batería, en algún momento del vuelo.

**Centro:** el **mapa satelital** (un poco apagado para que resalten las capas) con la
ruta coloreada por tramo y bordeada en oscuro, la salida y la entrega con su nombre, la
distancia en línea recta, la estela del vuelo, las aves, las zonas prohibidas, los
cables y las antenas. Tiene norte y barra de escala, leyenda, y abajo a la derecha las
coordenadas, el edificio bajo el cursor y la distancia a la salida. Al terminar aparece
una tarjeta con el resultado. Debajo, el **perfil de alturas** de la ruta (edificios
cercanos y justo debajo, cables, techo legal, altura planeada por tramo y la realmente
volada) con los botones **Google Maps** (abre la posición del dron en vista satelital)
y **Google Earth 3D** (exporta la ruta planeada, la volada a su altura real y las zonas
prohibidas a `vuelos/vuelo_*.kml` y lo abre con Google Earth Pro; si no lo tienes,
arrástralo a earth.google.com → Proyectos → Importar archivo KML).

**Panel derecho:**

- **Vista cercana** (satélite ampliado alrededor del dron; el interruptor *satélite* la
  cambia a plano): edificios en **rojo** si son más altos que el dron y en **naranja** si
  están a menos de 15 m por debajo, con su altura; cables, antenas, aves (con su altura
  relativa), la plataforma, la rosa del viento y el dron con sus rotores (verde =
  funcionando, rojo = fallado; en el avión, gris = rotores apagados volando como avión).
- **Telemetría:** cuatro indicadores (altura, velocidad, batería con la marca de la
  reserva y tiempo de llegada con el avance) y debajo tiempo, velocidad respecto al
  aire y vertical, voltaje y potencia, rumbo y distancia restante, GPS (satélites,
  incertidumbre), motores, viento y carga. Antes de despegar muestra el resumen de la
  ruta.
- **Provocar en pleno vuelo:** cortar/restaurar el GPS, fallar un motor, bajar la
  batería o soltar una ráfaga fuerte cuando tú quieras.
- **Bitácora** de todo lo que pasa y de cada **decisión** del piloto automático.
- **⏺ Grabar** graba en video la ventana del proyecto (también existe en la escuela de
  vuelo). El botón cambia a **⏹ Stop** con el tiempo transcurrido; al pulsarlo guarda un
  MP4 H.264 de alta calidad (resolución nativa de la ventana, 30 fps, CRF 16) en
  `grabaciones/`. Captura sólo esta ventana aunque otra la tape; si se cierra la ventana
  mientras graba, el video se guarda igual. Usa ffmpeg de `imageio-ffmpeg`.

**Teclas:** `Espacio` pausa · `+`/`-` velocidad de simulación · `Enter` despegar · `Esc` salir.

## Los dos vehículos

| | Hexacóptero | Avión VTOL (ala fija) |
|---|---|---|
| Cómo vuela | Siempre como helicóptero | Despega y aterriza vertical con 8 rotores; en crucero vuela como avión con su hélice trasera |
| Velocidad de crucero | 16 m/s (58 km/h) | 24 m/s (86 km/h); mínimo 15 m/s respecto al aire |
| Consumo en crucero | ~700 W (≈44 J por metro) | ~400 W (≈17 J por metro: el ala lo sostiene) |
| Batería | 222 Wh | 300 Wh |
| Curvas | Puede girar en el lugar | Se inclina; la ruta redondea las esquinas |

Un avión normal no puede aterrizar en una azotea, por eso el avión es **VTOL** (como
los de reparto de Wingcopter o Zipline). Sus fases: despegue vertical → **transición**
(acelera con los rotores hasta que el ala lo sostiene, contando la velocidad respecto al
aire) → crucero como avión → **transición a vuelo vertical** ~260 m antes del cliente
(enciende rotores y frena) → aterrizaje de precisión. Con viento de cola acelera más
respecto al suelo para no perder sustentación.

## El vuelo

- **Ruta automática:** A* sobre una cuadrícula de 10 m que guarda, para cada celda, la
  altura mínima para pasar: edificios (+20 m por encima, 15 m alrededor), antenas
  (radio de 25 m por los tirantes), cables (+15 m). Las celdas de zonas prohibidas o
  con obstáculos que obligarían a pasar del **techo legal de 120 m** quedan bloqueadas.
  Prefiere rodear antes que subir mucho. Donde el mapa no tiene edificios se suponen
  casas bajas (salvo en calles y parques).
- **Zonas prohibidas:** 300 m alrededor de cada **helipuerto** (hospitales), además de
  penales, zonas militares y estadios que aparezcan en el mapa.
- **Perfil de alturas:** crucero preferido a 50 m; sube **antes** de cada obstáculo y
  baja después, con pendientes que el vehículo puede volar.
- **Perfil de velocidades:** más lento en curvas, subidas, bajadas, junto a zonas
  prohibidas y cruzando cables (hexacóptero); acelera y frena de forma progresiva.
- **Aterrizaje de precisión:** se coloca sobre la plataforma a 20 m, la cámara reconoce
  su marcador (error de centímetros) y baja a 2 m/s, luego 0.8 m/s y los últimos 4 m a
  0.3 m/s, sólo si está centrado (±30 cm). Si una ráfaga lo mueve cerca de la azotea,
  **pausa el aterrizaje**, sube un poco, espera a que se calme y lo vuelve a intentar.

## Fallas y cómo se adapta (siempre llega)

| Situación | Qué hace |
|---|---|
| **Viento y ráfagas** | El viento crece con la altura y tiene turbulencia; el control lo compensa (con retraso, como uno real). En el aterrizaje espera a que pase la ráfaga. |
| **Aves** | Radar/cámara de 60 m: calcula el punto de máximo acercamiento y si va a pasar a menos de 12 m sube o baja y se abre a un lado. Si choca con un ave puede dañar una hélice. |
| **Pérdida de GPS** | Sigue con navegación inercial (la incertidumbre crece), baja la velocidad (el avión mantiene la suya), sube a una altura que libre todo en su radio de incertidumbre y cada 15 s compara la cámara con el mapa satelital para corregir la deriva. Cerca del cliente la cámara ve el marcador. |
| **Falla de un motor** | Hexacóptero: reparte el empuje en los 5 rotores sanos y vuela más lento. Avión volando como avión: falla la hélice trasera → enciende los rotores y sigue como multirrotor. El vehículo tiene redundancia para una falla de motor (no se provoca una segunda). |
| **Batería baja** (falla de una celda) | Calcula la energía que necesita y vuela a la velocidad que rinde más por kilómetro, sin subidas innecesarias, usando la reserva si hace falta. La celda dañada siempre deja energía suficiente para terminar aun en el peor caso. |

Si la batería se agotara por completo, el vehículo tiene paracaídas (no debería pasar:
en la prueba de 48 vuelos con todas las fallas y viento de hasta 12 m/s en Monterrey y
Guadalajara, los 48 entregaron).

## Física

- **Hexacóptero** (7.5 kg + carga, 6 × 34 N): el piloto pide una aceleración y se
  convierte en empuje con inclinación máxima de 35°; arrastre con el aire (no con el
  suelo). Potencia por teoría de cantidad de movimiento con avance (inducida + subida
  + parásita + electrónica).
- **Avión** como avión: el ala sostiene el peso; la hélice trasera (45 N) vence el
  arrastre (parásito + inducido); gira inclinándose hasta 35°; cerca de la velocidad
  de pérdida el ala deja de sostenerlo. Se mueve con la masa de aire.
- **Batería** con voltaje según carga y caída por corriente; 8 % de reserva.
- **Estimación de posición:** GPS (con rebotes entre edificios altos), inercial sin GPS,
  correcciones visuales y marcador de la plataforma; el piloto vuela con lo **estimado**
  y los choques se revisan con la posición **real**.

## Archivos

| Archivo | Contenido |
|---|---|
| `main.py` | Punto de entrada y opciones de línea de comandos |
| `config.py` | Todos los parámetros: zonas, vehículos, separaciones, viento, fallas |
| `geo.py` | Coordenadas reales, descarga de OpenStreetMap y del satélite, KML para Google Earth y enlace a Google Maps |
| `ciudad.py` | La ciudad real: edificios con altura, lugares, helipuertos, cables, antenas, calles |
| `navegacion.py` | Cuadrícula de alturas, A*, perfil de alturas y velocidades por tramo |
| `ambiente.py` | Viento, turbulencia, ráfagas y parvadas de aves |
| `dron.py` | Física del hexacóptero y del avión, motores, batería y estimación de posición |
| `piloto.py` | Piloto automático: seguimiento de ruta, transiciones, evasión, aterrizaje y decisiones |
| `simulacion.py` | La misión: fallas, choques, aterrizaje y resumen |
| `cerebro.py` | La red neuronal (el genoma), sus sensores y sus reflejos |
| `escuela.py` | Lecciones, alumnos, algoritmo genético, plan de estudios, guardado |
| `interfaz_escuela.py` | Ventana de la escuela de vuelo |
| `interfaz.py` | Ventana del simulador (tkinter + Pillow) |
| `estilo.py` | Tema visual y controles (tarjetas, botones, menús, interruptores, gráfica) |
| `grabador.py` | Botón ⏺ Grabar / ⏹ Stop: captura la ventana y la codifica con ffmpeg |
| `mejor_cerebro_<vehículo>.json` | El mejor cerebro aprendido (lo usa el piloto IA) |
| `historial.csv` | Estadísticas de cada generación de la escuela |
| `datos/` | Datos de OpenStreetMap e imagen satelital de cada zona usada |
| `vuelos/` | Archivos KML exportados para Google Earth |
| `grabaciones/` | Videos MP4 grabados con el botón ⏺ Grabar pantalla |

**Alturas:** OpenStreetMap trae la altura (o los pisos) de una parte de los edificios;
para los demás se estima según su tipo (casa, departamentos, oficinas…). En la ventana,
al pasar el cursor, se indica si la altura es del mapa o estimada.

Datos: © colaboradores de OpenStreetMap (ODbL). Imagen: Esri, Maxar, Earthstar
Geographics (World Imagery).
